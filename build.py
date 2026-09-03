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
  visa_data.db            SQLite form  (meta, countries, visa_rules, corrections,
                                        visa_holdings, visa_benefits)

Determinism: pass --date YYYY-MM-DD (or set BUILD_DATE) to pin `checked` and
`generated`; the same inputs and date reproduce byte-identical output. Without
it, today's date is used.

Exclusions: countries in EXCLUDED are not carried at all — not as passports,
not as destinations, not in the countries table.

Limited recognition: Abkhazia, South Ossetia, Transnistria, Northern Cyprus
and the SADR have no full Wikipedia visa matrix — their pages are stubs.
Their rules are hand-curated in data/limited-recognition.json and merged in
by merge_limited_recognition() after the scrape and overrides.

Visa/residency holdings: a separate "permit" layer for the common situation
where a traveller holds a foreign visa or residence permit (US green card,
Schengen visa/residence, UK BRP, APEC card, ...) that relaxes the passport
rule in some destinations. Hand-curated in data/visa-benefits.json from
VisaCheck's holdings list and verified against the destination's own Wikipedia
row (a note in another country's row is that other country's policy, not the
destination's). Written to the visa_holdings + visa_benefits tables by
merge_visa_benefits() after the scrape and overrides. A benefit only ever
RELAXES the underlying passport rule — it never removes the need for a valid
passport or normal admissibility checks — so the app still merges each benefit
against the passport result and keeps the better outcome. Every benefit row also
carries its own source_page + source_url — the destination's "Visa policy of X"
Wikipedia page (Schengen states share the "Visa policy of the Schengen Area"
page) — so any row can be re-verified with one click.

Transit: a separate axis stored on visa_rules (transit, transit_note) with
values free | required | unknown. It is distinct from the entry status ladder —
a visa-free corridor is always transit-free, but a visa-required corridor may
allow airside transit or require a transit visa. The base rule is computed, not
scraped: transit is "free" wherever the entry type is visa-free or
freedom-of-movement (airside transit is strictly less privileged than entry)
and "unknown" otherwise; cited exceptions live in data/transit.json and are
applied by merge_transit().
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


def merge_limited_recognition(matrix, passports, build_date):
    """Merge hand-curated rules for states that have no full Wikipedia visa
    matrix (data/limited-recognition.json): Abkhazia (AB), South Ossetia (OS),
    Transnistria (TS), Northern Cyprus (NC) and the SADR (EH).

    Their 'Visa requirements for X citizens' pages are stubs: a short list of
    where the passport is accepted — everywhere else it is simply not accepted
    (refused). Their 'Visa policy of X' pages give a simple destination regime:
    explicit exemptions plus a default. All cells are single-source (Wikipedia),
    so confidence is "medium" throughout.

    The SADR (EH) is passport-only: no 'Visa policy of Western Sahara' page
    exists, so it is not a destination.

    Returns the extended passport list and iso2 -> name for the new entries.
    """
    path = DATA / "limited-recognition.json"
    if not path.exists():
        return passports, {}
    spec = json.load(open(path))
    today = build_date

    def cell(c):
        out = {
            "type": c["type"],
            "days": c.get("days"),
            "source": "wikipedia",
            "checked": today,
            "confidence": "medium",
        }
        if c.get("note"):
            out["note"] = c["note"]
        return out

    new_passports = set(spec)
    new_dests = {code for code, e in spec.items() if e.get("destination")}

    # Destination columns: one cell for every passport, minus self.
    for code, e in spec.items():
        if not e.get("destination"):
            continue
        default = e["destination_default"]
        explicit = e.get("destination_row", {})
        for nat in sorted(set(passports) | new_passports):
            if nat == code:
                continue
            matrix.setdefault(nat, {})[code] = cell(explicit.get(nat, default))

    # Passport rows: one cell for every destination, minus self.
    all_dests = new_dests | {d for cells in matrix.values() for d in cells}
    for code, e in spec.items():
        default = e["passport_default"]
        explicit = e.get("passport_row", {})
        row = {}
        for dest in sorted(all_dests):
            if dest == code:
                continue
            row[dest] = cell(explicit.get(dest, default))
        matrix[code] = dict(sorted(row.items()))

    passports = sorted(set(passports) | new_passports)
    for nat in matrix:
        matrix[nat] = dict(sorted(matrix[nat].items()))
    names = {code: e["name"] for code, e in spec.items()}
    return passports, names


def merge_visa_benefits(cur, known_iso2):
    """Load the curated holdings/benefits and write the two permit-layer tables.

    Benefits whose destination is not a known country in this build (e.g. a
    British Overseas Territory that the matrix does not carry) are skipped. A
    benefit only relaxes the passport rule — the app re-merges it against the
    passport result and keeps the better outcome — so it is safe to store it
    for every destination that documents it.
    """
    path = DATA / "visa-benefits.json"
    if not path.exists():
        return 0, 0
    spec = json.load(open(path))
    checked = spec.get("checked")
    n_holdings = 0
    n_benefits = 0
    for h in spec.get("holdings", []):
        cur.execute(
            "INSERT OR REPLACE INTO visa_holdings"
            "(id, name, category, issuing_country, note) VALUES (?, ?, ?, ?, ?)",
            (h["id"], h["name"], h["category"], h.get("issuing_country"), h.get("note")),
        )
        n_holdings += 1
    for holding in sorted(spec.get("benefits", {})):
        for b in spec["benefits"][holding]:
            dest = b["destination"]
            if dest not in known_iso2:
                continue
            src = "wikipedia" if b.get("confidence") == "high" else "visa-check"
            cur.execute(
                "INSERT OR REPLACE INTO visa_benefits"
                "(holding, destination, type, days, confidence, source, checked, note,"
                " source_page, source_url)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (holding, dest, b["type"], b.get("days"), b.get("confidence"),
                 src, checked, b.get("note"),
                 b.get("source_page"), b.get("source_url")),
            )
            n_benefits += 1
    print(f"visa holdings: {n_holdings}  visa benefits: {n_benefits}")
    return n_holdings, n_benefits


def merge_transit(cur):
    """Apply the curated, cited transit overrides from data/transit.json.

    The base rule (free for visa-free / freedom-of-movement, else unknown) is
    already set on each visa_rules row during the insert; this only overrides
    the corridors named in data/transit.json (a confirmed 'free' or 'required'
    with a note). Corridors not named keep the base rule.
    """
    path = DATA / "transit.json"
    if not path.exists():
        return 0
    spec = json.load(open(path))
    n = 0
    for o in spec.get("overrides", []):
        p, d = o.get("passport"), o.get("destination")
        if not p or not d:
            continue
        cur.execute(
            "UPDATE visa_rules SET transit = ?, transit_note = ?"
            " WHERE passport = ? AND destination = ?",
            (o.get("transit"), o.get("note"), p, d),
        )
        n += cur.rowcount
    if n:
        print(f"transit overrides applied: {n}")
    return n


def write_sqlite(dataset, matrix, passports, overrides, extra_names=None) -> pathlib.Path:
    """Write the 6-table SQLite form: meta, countries, visa_rules, corrections,
    visa_holdings, visa_benefits."""
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
            -- transit axis: separate from the entry `type` ladder (not a visa
            -- status). Values: free | required | unknown. Base rule (set in the
            -- insert): free for visa-free / freedom-of-movement, unknown
            -- otherwise; cited overrides from data/transit.json.
            transit      TEXT,
            transit_note TEXT,
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
        CREATE TABLE visa_holdings (
            id               TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            category         TEXT NOT NULL,
            issuing_country  TEXT,
            note             TEXT
        );
        CREATE TABLE visa_benefits (
            holding     TEXT NOT NULL,
            destination TEXT NOT NULL,
            type        TEXT NOT NULL,
            days        INTEGER,
            confidence  TEXT,
            source      TEXT,
            checked     TEXT,
            note        TEXT,
            source_page TEXT,
            source_url  TEXT,
            PRIMARY KEY (holding, destination)
        );
        CREATE INDEX idx_visa_rules_destination  ON visa_rules(destination);
        CREATE INDEX idx_visa_rules_type         ON visa_rules(type);
        CREATE INDEX idx_visa_benefits_holding   ON visa_benefits(holding);
        CREATE INDEX idx_visa_benefits_dest      ON visa_benefits(destination);
    """)

    meta = dataset["meta"]
    for k in ("name", "version", "generated", "passport_count", "corridor_count",
              "primary_source", "cross_check", "limited_recognition",
              "visa_benefits", "transit", "attribution", "license", "disclaimer"):
        if k in meta:
            cur.execute("INSERT INTO meta(key, value) VALUES (?, ?)", (k, str(meta[k])))

    names = canonical_country_names()
    if extra_names:
        names.update(extra_names)
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
            # base transit rule (computed, not scraped): airside transit is
            # strictly less privileged than entry, so a visa-free /
            # freedom-of-movement corridor is transit-free; every other
            # corridor is unknown until a cited override confirms otherwise.
            transit = "free" if c["type"] in ("visa-free", "freedom-of-movement") else "unknown"
            cur.execute(
                "INSERT INTO visa_rules(passport, destination, type, days, confidence,"
                " source, checked, dispute, note, transit, transit_note)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (nat, dest, c["type"], c.get("days"), c.get("confidence"),
                 c.get("source"), c.get("checked"),
                 json.dumps(dispute, ensure_ascii=False) if dispute else None,
                 c.get("note") or None, transit, None),
            )

    merge_transit(cur)

    for o in overrides:
        cur.execute(
            "INSERT OR REPLACE INTO corrections(passport, destination, type, days, since, note)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (o.get("nat"), o.get("dest"), o.get("type"), o.get("days"),
             o.get("since"), o.get("note")),
        )

    merge_visa_benefits(cur, iso2s)

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

    # States with limited recognition — hand-curated from Wikipedia stub
    # pages; applied after the scrape and overrides (see the module docstring).
    passports, lr_names = merge_limited_recognition(matrix, passports, today)
    if lr_names:
        print(f"limited-recognition entities merged: {', '.join(sorted(lr_names))}")

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
            "limited_recognition": (
                "Abkhazia (AB), South Ossetia (OS), Transnistria (TS) and "
                "Northern Cyprus (NC) plus the SADR passport (EH, not a "
                "destination — no visa policy page exists) are hand-curated "
                "from Wikipedia stub pages in data/limited-recognition.json. "
                "A de facto passport is refused where it is not accepted as a "
                "travel document; accepted-but-undocumented regimes are marked "
                "assumed visa-required. Single-source: confidence=medium."
            ),
            "visa_benefits": (
                "visa_holdings + visa_benefits (from data/visa-benefits.json) "
                "are a permit layer: 13 common foreign visa/residency holdings "
                "(US green card, US visa, Schengen visa/residence, UK BRP, "
                "Canada PR/visa, Australia PR, UAE residence, Japan visa, GCC "
                "residence, Singapore permit, APEC card) and the destinations "
                "each one unlocks. Curated from VisaCheck and verified against "
                "the destination's own Wikipedia row (a note in another "
                "country's row is that other country's policy, not the "
                "destination's — several VisaCheck entries were dropped or "
                "corrected on that basis). confidence=high means the "
                "destination's row documents it; medium means it fits the "
                "'foreign visa/residence accepted' pattern but is not row-"
                "documented. A benefit only RELAXES the underlying passport "
                "rule (passport + admissibility still required); the app "
                "re-merges each against the passport result and keeps the "
                "better outcome. Each row carries source_page + source_url "
                "(the destination's 'Visa policy of X' Wikipedia page; "
                "Schengen states share 'Visa policy of the Schengen Area') "
                "for one-click re-verification."
            ),
            "transit": (
                "Separate axis on visa_rules (transit, transit_note): free | "
                "required | unknown. Base rule — computed, not scraped — sets "
                "transit=free wherever the entry type is visa-free or "
                "freedom-of-movement (airside transit is strictly less "
                "privileged than entry) and unknown for every other corridor; "
                "cited exceptions live in data/transit.json and are applied by "
                "merge_transit(). Distinct from the entry ladder: a visa-free "
                "corridor is always transit-free, but a visa-required corridor "
                "may allow airside transit or may require a transit visa."
            ),
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
    write_sqlite(dataset, matrix, passports, overrides, lr_names)

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
