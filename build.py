#!/usr/bin/env python3
"""Build the visa-matrix dataset: Wikipedia primary + passport-index cross-check.

Every cell records where its value came from and whether an independent source
agrees. The dataset never invents a number: when sources disagree the cell says
so out loud instead of silently picking one.

  confidence "high"      — both sources agree on the status type
  confidence "medium"    — only Wikipedia covers the cell (or the other source
                           has no comparable value)
  confidence "disputed"  — sources disagree; `dispute` shows both claims

Outputs (in data/):
  visa-matrix.json        canonical nested form with provenance
  visa-matrix-iso2.csv    matrix form  (passports x destinations)
  visa-matrix-tidy.csv    long form    (passport,destination,type,days,confidence)
  visa_data.db            SQLite form  (meta, countries, visa_rules, corrections)

Determinism: pass --date YYYY-MM-DD (or set BUILD_DATE) to pin `checked` and
`generated`; the same inputs and date reproduce byte-identical output. Without
it, today's date is used.

Exclusions: countries in EXCLUDED are not carried at all — not as passports,
not as destinations, not in the countries table.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sources import passportindex, wikipedia  # noqa: E402

DATA = pathlib.Path(__file__).parent / "data"

# Wikipedia country display names -> ISO2, for joining the two sources.
# Only rows that resolve here make it into the dataset.
COUNTRY_ISO2 = json.load(open(DATA / "countries-iso2.json"))

# Statuses comparable across sources. freedom-of-movement (Wikipedia-only
# nuance) is treated as agreeing with a bare "visa free" claim.
AGREE = {
    ("visa-free", "visa-free"),
    ("freedom-of-movement", "visa-free"),
    # An ETA (ESTA, eTA, K-ETA…) is a pre-authorisation for otherwise
    # visa-free travel; sources label the same regime either way.
    ("eta", "visa-free"),
    ("visa-free", "eta"),
    ("eta", "eta"),
}


def compatible(wiki_type: str, pi_type: str) -> bool:
    return wiki_type == pi_type or (wiki_type, pi_type) in AGREE


# Countries this dataset does not carry — not as passports, not as
# destinations, not in the countries table. #Free Palestine
EXCLUDED = {"IL"}


# `days` means "stay granted on entry", so it only exists for regimes that
# grant entry up front. Under visa-required / refused the length of stay comes
# from the visa itself, not the corridor.
STAY_REGIMES = {"visa-free", "freedom-of-movement", "eta", "visa-on-arrival", "e-visa"}
# Source prose mixes stay length with visa validity and age limits ("males
# aged 18-45 require a visa", "10-year multiple entry"), which parse into
# absurd day counts. The longest real visa-free stay we know of is Georgia's
# 365 days, so anything past a year is noise, not data.
MAX_PLAUSIBLE_STAY = 366


def sanitise_days(kind: str, days):
    if days is None or kind not in STAY_REGIMES:
        return None
    if days <= 0 or days > MAX_PLAUSIBLE_STAY:
        return None
    return days


def canonical_country_names() -> dict[str, str]:
    """iso2 -> preferred display name, from the (aliased) name->iso2 map."""
    iso2_to_names: dict = {}
    for name, iso2 in COUNTRY_ISO2.items():
        iso2_to_names.setdefault(iso2, []).append(name)
    # One canonical name where a country appears under several aliases.
    prefer = {
        "MM": "Myanmar", "CV": "Cape Verde", "CI": "Côte d'Ivoire",
        "CD": "DR Congo", "CG": "Republic of the Congo", "FM": "Micronesia",
        "TL": "Timor-Leste", "MK": "North Macedonia", "MO": "Macau",
        "BS": "Bahamas", "GM": "Gambia", "SZ": "Eswatini", "TR": "Türkiye",
        "CN": "China", "VA": "Vatican City", "ST": "Sao Tome and Principe",
    }
    out: dict[str, str] = {}
    for iso2, names in iso2_to_names.items():
        if iso2 in prefer and prefer[iso2] in names:
            out[iso2] = prefer[iso2]
        elif len(names) == 1:
            out[iso2] = names[0]
        else:
            out[iso2] = sorted(names)[0]
    return out


def write_sqlite(dataset, matrix, passports, overrides) -> pathlib.Path:
    """Write the 4-table SQLite form: meta, countries, visa_rules, corrections."""
    db_path = DATA / "visa_data.db"
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE countries (
            iso2   TEXT PRIMARY KEY,
            name   TEXT,
            region TEXT
        );
        CREATE TABLE visa_rules (
            passport    TEXT NOT NULL,
            destination TEXT NOT NULL,
            type        TEXT NOT NULL,
            days        INTEGER,
            confidence  TEXT,
            source      TEXT,
            checked     TEXT,
            dispute     TEXT,
            note        TEXT,
            PRIMARY KEY (passport, destination)
        );
        CREATE TABLE corrections (
            passport    TEXT NOT NULL,
            destination TEXT NOT NULL,
            type        TEXT NOT NULL,
            days        INTEGER,
            since       TEXT,
            note        TEXT,
            PRIMARY KEY (passport, destination)
        );
        CREATE INDEX idx_visa_rules_destination ON visa_rules(destination);
        CREATE INDEX idx_visa_rules_type        ON visa_rules(type);
    """)

    meta = dataset["meta"]
    for k in ("name", "version", "generated", "passport_count", "corridor_count",
              "primary_source", "cross_check", "attribution", "license", "disclaimer"):
        if k in meta:
            cur.execute("INSERT INTO meta(key, value) VALUES (?, ?)", (k, str(meta[k])))

    names = canonical_country_names()
    iso2s = set(passports)
    for cells in matrix.values():
        iso2s.update(cells)
    for iso2 in sorted(iso2s):
        cur.execute("INSERT INTO countries(iso2, name, region) VALUES (?, ?, ?)",
                    (iso2, names.get(iso2), None))

    for nat in sorted(matrix):
        for dest in sorted(matrix[nat]):
            c = matrix[nat][dest]
            dispute = c.get("dispute")
            cur.execute(
                "INSERT INTO visa_rules(passport, destination, type, days, confidence,"
                " source, checked, dispute, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (nat, dest, c["type"], c.get("days"), c.get("confidence"),
                 c.get("source"), c.get("checked"),
                 json.dumps(dispute, ensure_ascii=False) if dispute else None,
                 c.get("note") or None),
            )

    for o in overrides:
        cur.execute(
            "INSERT OR REPLACE INTO corrections(passport, destination, type, days, since, note)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (o.get("nat"), o.get("dest"), o.get("type"), o.get("days"),
             o.get("since"), o.get("note")),
        )

    con.commit()
    con.close()
    return db_path


def build(build_date: str):
    wiki = wikipedia.collect()
    pindex = passportindex.collect_all()
    # Full index: every passport either source knows about, minus excluded.
    passports = sorted((set(pindex) | set(wiki)) - EXCLUDED)
    today = build_date

    matrix: dict = {}
    disputes = 0
    for nat in passports:
        cells = {}
        # Wikipedia rows (keyed by country display name) -> iso2.
        w_cells = {}
        for country_name, w in wiki.get(nat, {}).items():
            iso2 = COUNTRY_ISO2.get(country_name)
            if iso2 and iso2 != nat:
                w_cells[iso2] = w
        dests = set(w_cells) | set(pindex.get(nat, {}))
        for iso2 in dests:
            if iso2 == nat or iso2 in EXCLUDED:
                continue
            w = w_cells.get(iso2)
            p = pindex.get(nat, {}).get(iso2)
            if p and p["type"] == "unknown":
                p = None
            if w:  # Wikipedia is primary where it covers the corridor
                cell = {
                    "type": w["type"],
                    "days": sanitise_days(w["type"], w["days"]),
                    "source": "wikipedia",
                    "checked": today,
                }
                if p:
                    if compatible(w["type"], p["type"]):
                        cell["confidence"] = "high"
                        # passport-index sometimes has the day count Wikipedia lacks
                        filled = sanitise_days(w["type"], p.get("days"))
                        if cell["days"] is None and filled:
                            cell["days"] = filled
                            cell["days_source"] = "passport-index"
                    else:
                        cell["confidence"] = "disputed"
                        cell["dispute"] = {
                            "wikipedia": w["type"],
                            "passport-index": p["type"],
                        }
                        disputes += 1
                else:
                    cell["confidence"] = "medium"
            elif p:  # passport-index only — full coverage, single-source
                cell = {
                    "type": p["type"],
                    "days": sanitise_days(p["type"], p.get("days")),
                    "source": "passport-index",
                    "checked": today,
                    "confidence": "medium",
                }
            else:
                continue
            cells[iso2] = cell
        if cells:
            matrix[nat] = dict(sorted(cells.items()))

    # Manual corrections — applied AFTER the scrape so a confirmed policy change
    # the upstream sources still lag (e.g. a reversion Wikipedia hasn't caught)
    # survives every weekly rebuild instead of being reverted. Each override
    # wins over both sources and is stamped source=manual-correction with a note.
    ov_path = DATA / "overrides.json"
    overrides = json.load(open(ov_path)).get("overrides", []) if ov_path.exists() else []
    applied = 0
    for o in overrides:
        nat, dest = o.get("nat"), o.get("dest")
        if not nat or not dest or nat not in matrix:
            continue
        matrix[nat][dest] = {
            "type": o["type"],
            "days": o.get("days"),
            "source": "manual-correction",
            "checked": today,
            "confidence": "high",
            "note": o.get("note", ""),
        }
        matrix[nat] = dict(sorted(matrix[nat].items()))
        applied += 1
    print(f"overrides applied: {applied}/{len(overrides)}")

    total_corridors = sum(len(c) for c in matrix.values())
    dataset = {
        "meta": {
            "name": "visa-matrix",
            "version": "1",
            "generated": today,
            "passports": passports,
            "passport_count": len(passports),
            "corridor_count": total_corridors,
            "primary_source": (
                "English Wikipedia 'Visa requirements for X citizens' pages "
                "(per-corridor citations, day counts); corridors those pages "
                "don't cover fall back to passport-index"
            ),
            "cross_check": "imorte/passport-index-data (scraped from passportindex.org)",
            "attribution": "xpressmike/visa-matrix (CC BY-SA 4.0)",
            "license": "GPLv3 — VisaDB fork of visa-matrix; see LICENSE and NOTICE",
            "disclaimer": (
                "General information, not legal advice. Rules change; always "
                "verify with the destination's official government source "
                "before booking."
            ),
        },
        "matrix": matrix,
    }

    DATA.mkdir(exist_ok=True)
    with open(DATA / "visa-matrix.json", "w") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=1)

    # Matrix CSV: one row per passport, one column per destination.
    dests = sorted({d for cells in matrix.values() for d in cells})
    with open(DATA / "visa-matrix-iso2.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Passport"] + dests)
        for nat in passports:
            row = [nat]
            for d in dests:
                c = matrix.get(nat, {}).get(d)
                if not c:
                    row.append("")
                elif c["type"] == "visa-free" and c["days"]:
                    row.append(str(c["days"]))
                else:
                    row.append(c["type"])
            w.writerow(row)

    # Tidy CSV: one row per corridor.
    with open(DATA / "visa-matrix-tidy.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["passport", "destination", "type", "days", "confidence"])
        for nat in passports:
            for d, c in matrix.get(nat, {}).items():
                w.writerow([nat, d, c["type"], c["days"] or "", c["confidence"]])

    # SQLite: the machine-readable form the app consumes.
    write_sqlite(dataset, matrix, passports, overrides)

    print(f"passports: {len(passports)}  corridors: {total_corridors}  disputed: {disputes}")
    print(f"wrote {DATA / 'visa_data.db'}")
    return dataset


def parse_args():
    p = argparse.ArgumentParser(description="Build the visa-matrix dataset.")
    p.add_argument(
        "--date",
        help="pin `checked`/`generated` to this date (YYYY-MM-DD); "
             "defaults to $BUILD_DATE, then today",
    )
    return p.parse_args()


def resolve_build_date(args) -> str:
    raw = args.date or os.environ.get("BUILD_DATE") or dt.date.today().isoformat()
    dt.date.fromisoformat(raw)  # validate the format
    return raw


if __name__ == "__main__":
    build(resolve_build_date(parse_args()))
