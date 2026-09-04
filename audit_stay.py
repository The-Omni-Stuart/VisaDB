"""Yield audit for the phase-2 stay/validity extraction (dry run).

Re-fetches (or loads from /tmp/wiki_texts.json) the Wikipedia visa pages, runs
the CURRENT parser (type + days) plus the PROPOSED new extraction (rolling
window period + expiry date), and reports how many corridors would gain each
field, with samples to eyeball extraction quality. Disposes after review.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, ".")
from sources import wikipedia  # noqa: E402

CACHE = "/tmp/wiki_texts.json"
EXCLUDED = {"IL"}

pages = {i: t for i, t in wikipedia.discover_pages().items() if i not in EXCLUDED}
titles = sorted(pages.values())

if pathlib.Path(CACHE).exists():
    texts = json.load(open(CACHE))
    print(f"loaded {len(texts)} pages from {CACHE}")
else:
    texts = wikipedia.fetch_many(titles)
    json.dump(texts, open(CACHE, "w"))
    print(f"fetched {len(texts)} pages, saved to {CACHE}")

row_re = re.compile(
    r"\{\{flag(?:icon|country)?\|([^}|]+)[^}]*\}\}(.*?)(?=\n\|-|\n\|\})", re.S
)

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def find_period(plain, days):
    """The window period (e.g. 180 in '90 days in 180' / '90/180')."""
    cands = []
    m = re.search(r"\bin\s+(?:any\s+)?(\d{2,4})\s*-?\s*day", plain, re.I)
    if m:
        cands.append((int(m.group(1)), m.group(0)))
    m = re.search(r"(\d+)\s*/\s*(\d+)", plain)
    if m:
        cands.append((int(m.group(2)), m.group(0)))
    m = re.search(r"(\d+)\s*days?\s*in\s+(\d{2,4})\b", plain, re.I)
    if m:
        cands.append((int(m.group(2)), m.group(0)))
    for p, frag in cands:
        if p > 60 and (days is None or p > days):
            return p, frag
    return None, None


def find_valid_to(plain):
    """An expiry date ('until 31 December 2026' -> 2026-12-31)."""
    m = re.search(r"\buntil\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", plain, re.I)
    if m:
        d, mon, y = int(m.group(1)), m.group(2).lower()[:3], int(m.group(3))
        if mon in MONTHS:
            return f"{y:04d}-{MONTHS[mon]:02d}-{d:02d}", m.group(0)
    m = re.search(r"\buntil\s+([A-Za-z]+)\s+(\d{4})", plain, re.I)
    if m:
        mon, y = m.group(1).lower()[:3], int(m.group(2))
        if mon in MONTHS and 2020 <= y <= 2035:
            return f"{y:04d}-{MONTHS[mon]:02d}-01", m.group(0)
    m = re.search(r"\buntil\s+(\d{4})\b", plain)
    if m:
        y = int(m.group(1))
        if 2020 <= y <= 2035:
            return f"{y:04d}-12-31", m.group(0)
    return None, None


total = 0
with_days = 0
with_period = 0
with_valid_to = 0
type_counts = {}
period_by_type = {}
valid_to_by_type = {}
period_dist = {}
period_samples = []
valid_to_samples = []

for iso2, title in sorted(pages.items()):
    wt = texts.get(title)
    if not wt:
        continue
    parsed = wikipedia.parse_page(wt)
    rests = {}
    for m in row_re.finditer(wt):
        rests.setdefault(m.group(1).strip(), m.group(2))
    for country, cell in parsed.items():
        total += 1
        t = cell["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
        if cell["days"]:
            with_days += 1
        rest_plain = " ".join(
            wikipedia.strip_markup(c) for c in rests.get(country, "").split("\n|")
        )
        p, pfrag = find_period(rest_plain, cell["days"])
        if p:
            with_period += 1
            period_by_type[t] = period_by_type.get(t, 0) + 1
            period_dist[(cell["days"], p)] = period_dist.get((cell["days"], p), 0) + 1
            if len(period_samples) < 45:
                period_samples.append(
                    (iso2, country, t, cell["days"], p, pfrag.strip()[:40]))
        v, vfrag = find_valid_to(rest_plain)
        if v:
            with_valid_to += 1
            valid_to_by_type[t] = valid_to_by_type.get(t, 0) + 1
            if len(valid_to_samples) < 45:
                valid_to_samples.append(
                    (iso2, country, t, cell["days"], v, vfrag.strip()[:45]))

print(f"\ntotal corridors parsed: {total}")
print(f"with days:               {with_days}")
print(f"with window_period:      {with_period}   (by type: {period_by_type})")
print(f"with valid_to:           {with_valid_to}   (by type: {valid_to_by_type})")
print(f"\ntype breakdown: {type_counts}")
print("\ntop (days, period) combos:")
for k, v in sorted(period_dist.items(), key=lambda x: -x[1])[:15]:
    print(f"   {k[0]}d / {k[1]}d : {v}")
print("\nwindow-period samples (passport -> dest  type  days/period  [matched])")
for s in period_samples:
    print(f"   {s[0]} -> {s[1]!r:28} {s[2]:<20} {s[3]}/{s[4]}  [{s[5]}]")
print("\nvalid_to samples (passport -> dest  type  days -> date  [matched])")
for s in valid_to_samples:
    print(f"   {s[0]} -> {s[1]!r:28} {s[2]:<20} {s[3]}d -> {s[4]}  [{s[5]}]")
