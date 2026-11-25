"""Cross-check source: the passport-index dataset (imorte/passport-index-data).

Scraped from passportindex.org by its maintainer. We never publish these values
directly — they exist to confirm or dispute what Wikipedia says. Agreement
raises a cell's confidence; disagreement flags it for review.
"""

from __future__ import annotations

import csv
import io
import time
import urllib.error
import urllib.request

UA = {
    "User-Agent": "visadb/1.0 (open dataset; https://github.com/The-Omni-Stuart/VisaDB)"
}
CSV_URL = (
    "https://raw.githubusercontent.com/imorte/passport-index-data/"
    "main/passport-index-matrix-iso2.csv"
)


def normalise(raw: str):
    raw = raw.strip()
    low = raw.lower()
    if raw.isdigit():
        return {"type": "visa-free", "days": int(raw)}
    if low == "visa free":
        return {"type": "visa-free", "days": None}
    if low == "visa on arrival":
        return {"type": "visa-on-arrival", "days": None}
    if low == "e-visa":
        return {"type": "e-visa", "days": None}
    if low in ("eta", "e-ta"):  # electronic travel authorisation (ESTA, eTA…)
        return {"type": "eta", "days": None}
    if low in ("visa required", "covid ban", "no admission"):
        return {"type": "visa-required", "days": None}
    if low == "-1":  # self
        return None
    return {"type": "unknown", "days": None, "raw": raw}


def _get_text(url: str) -> str:
    """One fetch with the same backoff wikipedia._get uses."""
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, OSError, TimeoutError):
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")


def collect_all() -> dict:
    """Every passport in the matrix: iso2 -> {destination iso2 -> cell}"""
    rows = list(csv.reader(io.StringIO(_get_text(CSV_URL))))
    header = rows[0]
    out: dict = {}
    for row in rows[1:]:
        # An upstream column addition would otherwise IndexError the whole build.
        if len(row) != len(header):
            print(f"passport-index: skipping ragged row {row[0]!r}")
            continue
        cells = {}
        for i, dest in enumerate(header[1:], start=1):
            cell = normalise(row[i])
            if cell:
                cells[dest] = cell
        out[row[0]] = cells
    return out


def collect(passports: list) -> dict:
    """Subset view kept for callers that only need a few passports."""
    return {p: c for p, c in collect_all().items() if p in passports}


if __name__ == "__main__":
    data = collect(["US", "GB"])
    print("US destinations:", len(data["US"]))
    print("US->JP:", data["US"].get("JP"))
    print("US->TR:", data["US"].get("TR"))
