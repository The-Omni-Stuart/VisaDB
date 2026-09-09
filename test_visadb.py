#!/usr/bin/env python3
"""Invariant test suite for the VisaDB build output.

Runs OFFLINE against data/visa_data.db (no network). Two parts:

  A. Data integrity — value domains, referential integrity, and the semantic
     invariants the build must guarantee (e.g. a visa-free corridor is always
     transit-free; every valid_to is future-dated; days are positive when set).

  B. Merge-logic reference — a pure re-implementation of the APP's entry and
     transit merge (docs/app-merge-logic.md) to lock the SPEC before the app
     exists: benefits only relax the baseline, never lift a refusal, and
     best-of always picks the most privileged status.

Stdlib only. `python3 test_visadb.py` -> exit 0 if all pass, 1 otherwise.
"""
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).parent
DB = ROOT / "data" / "visa_data.db"
JSON = ROOT / "data" / "visa_data.json"

VALID_TYPES = ("refused", "visa-required", "e-visa", "visa-on-arrival",
               "eta", "visa-free", "freedom-of-movement")
VALID_TRANSIT = ("free", "required", "conditional", "unknown")
# visa_benefits carries BOTH entry benefits (entry-type values) and transit
# benefits ("transit-free"); they share one table, distinguished by `type`.
VALID_BENEFIT_TYPES = tuple(VALID_TYPES) + ("transit-free",)
NAT_SENTINELS = {"*", "EU-EEA"}

_RESULTS = []


def check(name, cond, detail=""):
    _RESULTS.append((name, bool(cond), detail))


def _in(vals):
    return ",".join("?" * len(vals)), tuple(vals)


# --------------------------------------------------------------------------
# A. Data integrity
# --------------------------------------------------------------------------
def test_data_integrity(con):
    gen = con.execute("SELECT value FROM meta WHERE key='generated'").fetchone()["value"]
    iso2 = {r["iso2"] for r in con.execute("SELECT iso2 FROM countries")}
    ph, args = _in(VALID_TYPES)
    check("A1 visa_rules.type in domain",
          con.execute(f"SELECT COUNT(*) FROM visa_rules WHERE type NOT IN ({ph})", args).fetchone()[0] == 0)
    ph, args = _in(VALID_TRANSIT)
    check("A2 visa_rules.transit in domain",
          con.execute(f"SELECT COUNT(*) FROM visa_rules WHERE transit NOT IN ({ph})", args).fetchone()[0] == 0)
    check("A3 corridor passport is a known ISO2",
          con.execute("SELECT COUNT(*) FROM visa_rules v WHERE v.passport NOT IN (SELECT iso2 FROM countries)").fetchone()[0] == 0)
    check("A4 corridor destination is a known ISO2",
          con.execute("SELECT COUNT(*) FROM visa_rules v WHERE v.destination NOT IN (SELECT iso2 FROM countries)").fetchone()[0] == 0)

    # referential integrity
    check("A5 visa_benefits.holding -> visa_holdings",
          con.execute("SELECT COUNT(*) FROM visa_benefits vb WHERE vb.holding NOT IN (SELECT id FROM visa_holdings)").fetchone()[0] == 0)
    check("A6 transit_benefits.holding -> visa_holdings",
          con.execute("SELECT COUNT(*) FROM transit_benefits tb WHERE tb.holding NOT IN (SELECT id FROM visa_holdings)").fetchone()[0] == 0)
    check("A7 visa_benefits.destination is a known ISO2",
          con.execute("SELECT COUNT(*) FROM visa_benefits vb WHERE vb.destination NOT IN (SELECT iso2 FROM countries)").fetchone()[0] == 0)

    # benefit value domains (entry types + transit benefits share the table)
    ph, args = _in(VALID_BENEFIT_TYPES)
    check("A8 visa_benefits.type in domain",
          con.execute(f"SELECT COUNT(*) FROM visa_benefits WHERE type NOT IN ({ph})", args).fetchone()[0] == 0)
    ph, args = _in(VALID_TRANSIT)
    check("A9 transit_benefits.transit_type in domain",
          con.execute(f"SELECT COUNT(*) FROM transit_benefits WHERE transit_type NOT IN ({ph})", args).fetchone()[0] == 0)

    # day-count sanity
    check("A10 days>0 when present",
          con.execute("SELECT COUNT(*) FROM visa_rules WHERE days IS NOT NULL AND days <= 0").fetchone()[0] == 0)
    check("A11 visa-required/refused have no stay days",
          con.execute("SELECT COUNT(*) FROM visa_rules WHERE type IN ('visa-required','refused') AND days IS NOT NULL").fetchone()[0] == 0)

    # KEY semantic invariant: airside transit is strictly less privileged than
    # entry, so a corridor you may ENTER freely must let you TRANSIT freely.
    check("A12 visa-free / freedom-of-movement => transit free",
          con.execute("SELECT COUNT(*) FROM visa_rules WHERE type IN ('visa-free','freedom-of-movement') AND transit != 'free'").fetchone()[0] == 0)

    # validity windows
    check("A13 valid_to is future-dated (no lapsed rows)",
          con.execute("SELECT COUNT(*) FROM visa_rules WHERE valid_to IS NOT NULL AND valid_to < ?", (gen,)).fetchone()[0] == 0)
    check("A14 window_period_days >= days when both set",
          con.execute("SELECT COUNT(*) FROM visa_rules WHERE window_period_days IS NOT NULL AND days IS NOT NULL AND window_period_days < days").fetchone()[0] == 0)

    # stay_rules internal consistency
    check("A15 stay_rules.window_type in domain",
          con.execute("SELECT COUNT(*) FROM stay_rules WHERE window_type NOT IN ('per-entry','rolling')").fetchone()[0] == 0)
    check("A16 rolling stay_rules have both window days set",
          con.execute("SELECT COUNT(*) FROM stay_rules WHERE window_type='rolling' AND (window_days IS NULL OR window_period_days IS NULL)").fetchone()[0] == 0)
    check("A17 per-entry stay_rules carry no window period",
          con.execute("SELECT COUNT(*) FROM stay_rules WHERE window_type='per-entry' AND window_period_days IS NOT NULL").fetchone()[0] == 0)
    check("A18 stay_rules.window_days>0",
          con.execute("SELECT COUNT(*) FROM stay_rules WHERE window_days IS NULL OR window_days <= 0").fetchone()[0] == 0)

    # stay_rules references: every country a real ISO2; every nationality an
    # ISO2 or a documented sentinel.
    bad_country = bad_nat = 0
    for row in con.execute("SELECT countries, nationalities FROM stay_rules"):
        for c in json.loads(row["countries"]):
            if c not in iso2:
                bad_country += 1
        for n in json.loads(row["nationalities"]):
            if n not in iso2 and n not in NAT_SENTINELS:
                bad_nat += 1
    check("A19 stay_rules countries are known ISO2", bad_country == 0, f"{bad_country} bad")
    check("A20 stay_rules nationalities are ISO2 or sentinel", bad_nat == 0, f"{bad_nat} bad")

    # a zone groups related stay rules (e.g. Schengen/EAC are single shared
    # pools; CA-4 is a family of per-country rows). Rows sharing a zone id must
    # at minimum share one zone_name (a grouping-label consistency check).
    zones = {}
    for z, zn in con.execute("SELECT zone, zone_name FROM stay_rules WHERE zone IS NOT NULL"):
        zones.setdefault(z, set()).add(zn)
    check("A21 rows in one zone share one zone_name",
          all(len(v) == 1 for v in zones.values()),
          "; ".join(f"{z}={sorted(v)}" for z, v in zones.items() if len(v) > 1) or "ok")

    # required meta keys (DB meta table naming)
    keys = {r["key"] for r in con.execute("SELECT key FROM meta")}
    need = {"generated", "passport_count", "corridor_count", "visa_benefits", "stay_rules", "transit_benefits"}
    check("A22 meta has required keys", need <= keys, ", ".join(sorted(need - keys)) or "ok")


def test_json_mirror(con):
    j = json.loads(JSON.read_text())
    db_corridors = con.execute("SELECT COUNT(*) FROM visa_rules").fetchone()[0]
    json_corridors = sum(len(v) for v in j["matrix"].values())
    check("B-mirror corridors: JSON == DB count",
          json_corridors == db_corridors, f"json={json_corridors} db={db_corridors}")
    for label, key, tbl in (
        ("holdings", "holdings", "visa_holdings"),
        ("benefits", "benefits", "visa_benefits"),
        ("stay_rules", "stay_rules", "stay_rules"),
        ("transit_benefits", "transit_benefits", "transit_benefits"),
    ):
        dbn = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        check(f"B-mirror {label}: JSON == DB count", len(j[key]) == dbn, f"json={len(j[key])} db={dbn}")


def test_benefits_generator_drift(con):
    # D. Generator drift — data/visa-benefits.json is produced by
    # gen_benefits.py, and the DB must stay in step with that curated source.
    source = json.loads((ROOT / "data" / "visa-benefits.json").read_text())
    import gen_benefits
    check("D1 gen_benefits payload matches data/visa-benefits.json",
          gen_benefits.build_payload() == source,
          "run `python3 gen_benefits.py` after editing the curated benefit rows")

    iso2 = {r["iso2"] for r in con.execute("SELECT iso2 FROM countries")}
    holdings = {r["id"] for r in con.execute("SELECT id FROM visa_holdings")}
    top_checked = source.get("checked")
    src_rows, skipped = {}, []
    for holding, rows in source.get("benefits", {}).items():
        for row in rows:
            key = (holding, row["destination"])
            if holding not in holdings or row["destination"] not in iso2:
                skipped.append(key)
                continue
            src_rows[key] = row
    db_rows = {
        (r["holding"], r["destination"]): dict(r)
        for r in con.execute(
            "SELECT holding, destination, type, days, entry_type, confidence,"
            " source, checked, note, source_page, source_url FROM visa_benefits")
    }
    check("D2a no visa-benefits source row is silently skipped",
          not skipped, ", ".join(str(s) for s in sorted(skipped)[:5]) or "ok")
    check("D2b visa_benefits DB and source have the same rows",
          set(src_rows) == set(db_rows), f"src={len(src_rows)} db={len(db_rows)}")
    mismatch, details = 0, []
    for key, s in src_rows.items():
        d = db_rows.get(key)
        if d is None:
            mismatch += 1
            details.append(f"{key[0]}/{key[1]} missing in DB")
            continue
        expected = {
            "type": s["type"],
            "days": s.get("days"),
            "entry_type": s.get("entry_type"),
            "confidence": s.get("confidence"),
            "source": "wikipedia" if s.get("confidence") == "high" else "visa-check",
            "checked": s.get("checked", top_checked),
            "note": s.get("note"),
            "source_page": s.get("source_page"),
            "source_url": s.get("source_url"),
        }
        actual = {k: d[k] for k in expected}
        if actual != expected:
            mismatch += 1
            details.append(f"{key[0]}/{key[1]} differs")
    check("D2c visa_benefits DB rows match the curated source",
          mismatch == 0, "; ".join(details[:3]) or "ok")


# --------------------------------------------------------------------------
# B. Merge-logic reference (the app spec, as a pure function)
# --------------------------------------------------------------------------
LADDER = list(VALID_TYPES)  # refused ... freedom-of-movement, worst -> best
RANK = {t: i for i, t in enumerate(LADDER)}


def best_of(a, b):
    return a if RANK[a] >= RANK[b] else b


def merge_entry(baseline, benefit_types):
    """A holding's entry benefit only relaxes the baseline; a refusal is sticky."""
    if baseline == "refused":
        return baseline
    return max([baseline, *benefit_types], key=lambda t: RANK[t])


# Transit axis: worst -> best. "unknown" means no published info, so it is the
# floor and any concrete benefit relaxes it.
TRANSIT_LADDER = ["unknown", "required", "conditional", "free"]
TRANK = {t: i for i, t in enumerate(TRANSIT_LADDER)}


def merge_transit(base, benefit_types):
    """Relax-only: a transit benefit never makes the base status worse."""
    concrete = [b for b in benefit_types if b != "unknown"]
    if base != "unknown":
        return max([base] + concrete, key=lambda t: TRANK[t])
    return max(concrete, key=lambda t: TRANK[t]) if concrete else "unknown"


def test_merge_reference():
    check("B1 ladder is strictly ordered",
          all(RANK[LADDER[i]] < RANK[LADDER[i + 1]] for i in range(len(LADDER) - 1)))
    check("B2 best_of never drops below the higher input",
          all(RANK[best_of(a, b)] == max(RANK[a], RANK[b]) for a in LADDER for b in LADDER))
    check("B3 an entry benefit never worsens the baseline",
          all(RANK[merge_entry(base, [b])] >= RANK[base] for base in LADDER for b in LADDER))
    check("B4 an entry benefit never lifts a refusal",
          all(merge_entry("refused", [b]) == "refused" for b in LADDER))

    con = sqlite3.connect(DB)
    # --- real-data ENTRY merge (entry-type benefits only) ---
    base_by_dest = {}
    for d, t in con.execute("SELECT DISTINCT destination, type FROM visa_rules"):
        base_by_dest.setdefault(d, set()).add(t)
    entry_ph, entry_args = _in(VALID_TYPES)
    ben_by_dest = {}
    for d, t in con.execute(
            f"SELECT DISTINCT destination, type FROM visa_benefits WHERE type IN ({entry_ph})", entry_args):
        ben_by_dest.setdefault(d, set()).add(t)
    worsen = lifted = seen = 0
    for d, bset in ben_by_dest.items():
        for t in base_by_dest.get(d, set()):
            for bt in bset:
                seen += 1
                out = merge_entry(t, [bt])
                if RANK[out] < RANK[t]:
                    worsen += 1
                if t == "refused" and out != "refused":
                    lifted += 1
    check("B5 real-data entry merge never worsens", worsen == 0, f"{worsen}/{seen} worsened")
    check("B6 real-data entry merge never lifts a refusal", lifted == 0, f"{lifted} lifted")

    # --- transit ladder + real-data TRANSIT merge ---
    check("B7 transit ladder is strictly ordered",
          all(TRANK[TRANSIT_LADDER[i]] < TRANK[TRANSIT_LADDER[i + 1]] for i in range(len(TRANSIT_LADDER) - 1)))
    check("B8 a transit benefit never worsens the base",
          all(TRANK[merge_transit(base, [b])] >= TRANK[base] for base in TRANSIT_LADDER for b in TRANSIT_LADDER))
    tbase_by_dest = {}
    for d, t in con.execute("SELECT DISTINCT destination, transit FROM visa_rules"):
        tbase_by_dest.setdefault(d, set()).add(t)
    tworsen = tseen = 0
    for d, bt in con.execute(
            "SELECT DISTINCT destination, type FROM visa_benefits WHERE type = 'transit-free'"):
        grant = "free"  # a "transit-free" benefit confers free transit
        for t in tbase_by_dest.get(d, set()):
            tseen += 1
            if TRANK[merge_transit(t, [grant])] < TRANK[t]:
                tworsen += 1
    check("B9 real-data transit merge never worsens", tworsen == 0, f"{tworsen}/{tseen} worsened")
    con.close()


def test_parser_subrow():
    # C. Parser — a sub-territory exception row that reuses the parent's flag
    # must NOT overwrite the parent's main status row. Regression for GB->IR,
    # which was scraped as visa-free because Wikipedia's "Kish Island" row
    # (a visa-free island off Iran) reuses {{flagicon|Iran}} and used to clobber
    # Iran's main "Visa required" row.
    from sources.wikipedia import parse_page
    wt = (
        "| {{flag|Austria}}\n"
        "| {{yes|Visa not required}}\n"
        "|-\n"
        "| {{flag|Iran}}\n"
        "| {{no|Visa required}}<ref>{{Timatic|nationality=GB|destination=IR}}</ref>\n"
        "| style=\"background:#FFC7C7;|\n"
        "* British citizens must have their visa stamped in their passport in "
        "advance of arrival in Iran.\n"
        "|-\n"
        "| {{flagicon|Iran}} [[Kish Island]]\n"
        "| {{yes|Visa not required}}\n"
        "| Tourists for [[Kish Island]] do not require a visa.\n"
        "|-\n"
    )
    rows = parse_page(wt)
    check("C1 main status row wins over a sub-territory exception row",
          rows.get("Iran", {}).get("type") == "visa-required",
          f"Iran={rows.get('Iran')}")
    check("C2 an ordinary (single-row) country still parses",
          rows.get("Austria", {}).get("type") == "visa-free",
          f"Austria={rows.get('Austria')}")


def main():
    if not DB.exists():
        print(f"FAIL: {DB} not found — run `python3 build.py` first.", file=sys.stderr)
        return 1
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    test_data_integrity(con)
    test_json_mirror(con)
    test_benefits_generator_drift(con)
    test_merge_reference()
    test_parser_subrow()
    con.close()

    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    failed = [(n, d) for n, ok, d in _RESULTS if not ok]
    for name, ok, detail in _RESULTS:
        print(f"  {'ok ' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))
    print(f"\n{passed}/{len(_RESULTS)} invariants passed.")
    if failed:
        print(f"FAILED: {len(failed)} invariant(s):")
        for n, d in failed:
            print(f"  - {n}  {d}")
        return 1
    print("ALL INVARIANTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
