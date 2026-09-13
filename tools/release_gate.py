#!/usr/bin/env python3
"""Validate a freshly built VisaDB dataset and emit release metadata.

This is the gate that decides whether a build is safe to publish. It checks the
SQLite artifact directly, computes a normalized data hash (ignoring only the
build timestamp and per-row `checked` stamps, so a rebuild with no real data
change hashes identically), and writes the files a release step needs:

  dist/data-hash.txt        normalized SHA256 of the DB content
  dist/build-manifest.json  counts + hash + build metadata
  dist/SHA256SUMS           raw artifact hashes for data/visa_data.db + .json
  dist/RELEASE_NOTES.md     human-readable release notes

Stdlib only. Exits 0 if the build passes, 1 if it should not be released.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

REQUIRED_TABLES = {
    "meta",
    "countries",
    "visa_rules",
    "corrections",
    "visa_holdings",
    "visa_benefits",
    "mobility_regimes",
    "stay_rules",
    "transit_benefits",
}
VALID_TYPES = (
    "refused",
    "visa-required",
    "e-visa",
    "visa-on-arrival",
    "eta",
    "visa-free",
    "freedom-of-movement",
)
VALID_CONFIDENCE = {"high", "medium", "low", "disputed"}
REQUIRED_JSON_KEYS = {
    "meta",
    "countries",
    "matrix",
    "corrections",
    "holdings",
    "benefits",
    "mobility_regimes",
    "stay_rules",
    "transit_benefits",
}


def fail(msg: str) -> None:
    print(f"release-gate: FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def meta_value(con: sqlite3.Connection, key: str) -> str | None:
    row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def normalized_hash(con: sqlite3.Connection) -> str:
    """SHA256 over all DB rows, excluding meta.generated and `checked` columns.

    Row order is normalized away. Any substantive schema or data change alters
    the hash; a timestamp-only rebuild does not.
    """
    tables = {
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    missing = REQUIRED_TABLES - tables
    if missing:
        fail(f"missing required tables: {', '.join(sorted(missing))}")

    normalized: dict[str, list[dict]] = {}
    for table in sorted(tables):
        cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
        if table == "meta":
            rows = [
                {"key": k, "value": v}
                for k, v in con.execute("SELECT key, value FROM meta")
                if k != "generated"
            ]
        else:
            keep = [c for c in cols if c != "checked"]
            if not keep:
                rows = []
            else:
                col_sql = ",".join(f'"{c}"' for c in keep)
                rows = [
                    {c: row[i] for i, c in enumerate(keep)}
                    for row in con.execute(f'SELECT {col_sql} FROM "{table}"')
                ]
        rows.sort(key=lambda r: json.dumps(r, sort_keys=True, default=str, ensure_ascii=False))
        normalized[table] = rows

    canonical = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def count_by(con: sqlite3.Connection, column: str) -> dict[str, int]:
    rows = con.execute(
        f'SELECT "{column}", COUNT(*) FROM visa_rules GROUP BY "{column}" ORDER BY "{column}"'
    ).fetchall()
    return {k: v for k, v in rows}


def sanity_checks(con: sqlite3.Connection, json_path: pathlib.Path) -> dict:
    generated = meta_value(con, "generated")
    if not generated:
        fail("meta.generated is missing")
    try:
        dt.date.fromisoformat(generated)
    except ValueError:
        fail(f"meta.generated is not an ISO date: {generated!r}")

    def int_meta(key: str) -> int:
        raw = meta_value(con, key)
        if raw is None:
            fail(f"meta.{key} is missing")
        try:
            return int(raw)
        except ValueError:
            fail(f"meta.{key} is not an integer: {raw!r}")

    passport_count = int_meta("passport_count")
    corridor_count = int_meta("corridor_count")
    db_corridors = con.execute("SELECT COUNT(*) FROM visa_rules").fetchone()[0]
    countries_count = con.execute("SELECT COUNT(*) FROM countries").fetchone()[0]

    if not 150 <= passport_count <= 260:
        fail(f"passport_count out of sanity bounds: {passport_count}")
    if not 20_000 <= corridor_count <= 60_000:
        fail(f"corridor_count out of sanity bounds: {corridor_count}")
    if db_corridors != corridor_count:
        fail(f"meta.corridor_count={corridor_count} but visa_rules has {db_corridors} rows")
    if countries_count < passport_count:
        fail(f"countries table has {countries_count} rows, fewer than passport_count={passport_count}")

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"JSON mirror not found: {json_path}")
    except json.JSONDecodeError as e:
        fail(f"JSON mirror is not valid JSON: {e}")
    missing_json = REQUIRED_JSON_KEYS - payload.keys()
    if missing_json:
        fail(f"JSON mirror missing keys: {', '.join(sorted(missing_json))}")
    json_corridors = sum(len(v) for v in payload.get("matrix", {}).values())
    if json_corridors != corridor_count:
        fail(f"JSON matrix has {json_corridors} corridors, meta says {corridor_count}")

    ph = ",".join("?" * len(VALID_TYPES))
    bad_type = con.execute(
        f"SELECT COUNT(*) FROM visa_rules WHERE type NOT IN ({ph})", VALID_TYPES
    ).fetchone()[0]
    if bad_type:
        fail(f"{bad_type} visa_rules rows have an invalid type")

    bad_confidence = con.execute(
        "SELECT COUNT(*) FROM visa_rules WHERE confidence IS NULL OR confidence NOT IN ('high','medium','low','disputed')"
    ).fetchone()[0]
    if bad_confidence:
        fail(f"{bad_confidence} visa_rules rows have invalid confidence")

    self_corridors = con.execute(
        "SELECT COUNT(*) FROM visa_rules WHERE passport = destination"
    ).fetchone()[0]
    if self_corridors:
        fail(f"{self_corridors} self-corridors present (passport = destination)")

    lapsed = con.execute(
        "SELECT COUNT(*) FROM visa_rules WHERE valid_to IS NOT NULL AND valid_to < ?",
        (generated,),
    ).fetchone()[0]
    if lapsed:
        fail(f"{lapsed} visa_rules rows have a lapsed valid_to date")

    disputed = con.execute(
        "SELECT COUNT(*) FROM visa_rules WHERE confidence = 'disputed'"
    ).fetchone()[0]
    if disputed > corridor_count * 0.35:
        fail(
            "disputed-corridor ratio is implausibly high "
            f"({disputed}/{corridor_count} = {disputed / corridor_count:.1%})"
        )

    return {
        "generated": generated,
        "passport_count": passport_count,
        "corridor_count": corridor_count,
        "countries_count": countries_count,
        "disputed": disputed,
    }


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_outputs(
    dist: pathlib.Path,
    db_path: pathlib.Path,
    json_path: pathlib.Path,
    con: sqlite3.Connection,
    data_hash: str,
    stats: dict,
    args: argparse.Namespace,
) -> None:
    dist.mkdir(parents=True, exist_ok=True)

    status_counts = count_by(con, "type")
    confidence_counts = count_by(con, "confidence")
    transit_counts = count_by(con, "transit")

    manifest = {
        "schema": "visadb/1",
        "data_sha256": data_hash,
        "generated": stats["generated"],
        "build_date": args.build_date or stats["generated"],
        "source_commit": args.source_commit,
        "source_ref": args.source_ref,
        "passport_count": stats["passport_count"],
        "corridor_count": stats["corridor_count"],
        "countries_count": stats["countries_count"],
        "disputed_corridors": stats["disputed"],
        "status_counts": status_counts,
        "confidence_counts": confidence_counts,
        "transit_counts": transit_counts,
        "artifacts": {
            "visa_data.db": sha256_file(db_path),
            "visa_data.json": sha256_file(json_path),
        },
    }

    (dist / "data-hash.txt").write_text(f"{data_hash}\n", encoding="utf-8")
    (dist / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (dist / "SHA256SUMS").write_text(
        "\n".join(
            [
                f"{manifest['artifacts']['visa_data.db']}  visa_data.db",
                f"{manifest['artifacts']['visa_data.json']}  visa_data.json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    notes = [
        f"# VisaDB data {stats['generated']}",
        "",
        f"- data hash: `{data_hash}`",
        f"- passports: {stats['passport_count']}",
        f"- corridors: {stats['corridor_count']}",
        f"- countries: {stats['countries_count']}",
        f"- disputed corridors: {stats['disputed']}",
    ]
    if args.source_commit:
        notes.append(f"- source commit: `{args.source_commit}`")
    if args.source_ref:
        notes.append(f"- source ref: `{args.source_ref}`")
    notes += ["", "## Entry status", ""]
    notes += [f"- {k}: {v}" for k, v in sorted(status_counts.items())]
    notes += ["", "## Confidence", ""]
    notes += [f"- {k}: {v}" for k, v in sorted(confidence_counts.items())]
    notes += ["", "## Transit", ""]
    notes += [f"- {k}: {v}" for k, v in sorted(transit_counts.items())]
    notes += [
        "",
        "## Artifacts",
        "",
        "```text",
        (dist / "SHA256SUMS").read_text(encoding="utf-8").strip(),
        "```",
        "",
        "This release was built automatically. The data hash excludes only the",
        "build timestamp and per-row `checked` stamps, so timestamp-only rebuilds",
        "do not create new releases.",
    ]
    (dist / "RELEASE_NOTES.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    print(
        "release-gate: OK "
        f"hash={data_hash[:12]} passports={stats['passport_count']} "
        f"corridors={stats['corridor_count']} disputed={stats['disputed']}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(ROOT / "data" / "visa_data.db"))
    p.add_argument("--json", default=str(ROOT / "data" / "visa_data.json"))
    p.add_argument("--dist", default=str(ROOT / "dist"))
    p.add_argument("--build-date", default="")
    p.add_argument("--source-commit", default="")
    p.add_argument("--source-ref", default="")
    args = p.parse_args()

    db_path = pathlib.Path(args.db)
    json_path = pathlib.Path(args.json)
    dist = pathlib.Path(args.dist)

    if not db_path.exists():
        fail(f"DB not found: {db_path}")
    con = sqlite3.connect(db_path)
    try:
        stats = sanity_checks(con, json_path)
        data_hash = normalized_hash(con)
        write_outputs(dist, db_path, json_path, con, data_hash, stats, args)
    finally:
        con.close()


if __name__ == "__main__":
    main()
