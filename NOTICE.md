# VisaDB — Attribution & Licence

VisaDB is a fork of [visa-matrix](https://github.com/xpressmike/visa-matrix), created and maintained by xpressmike.

## Original

- Repository: [xpressmike/visa-matrix](https://github.com/xpressmike/visa-matrix)
- Author: xpressmike
- Licence: CC BY-SA 4.0 (original text kept in `LICENSE-CC-BY-SA-4.0.txt`)

## Fork (this repository)

- Maintainer: cbk-res
- Copyright (C) 2026 cbk-res (VisaDB fork)
- Licence: GNU GPL v3 (see `LICENSE`)

Thanks to xpressmike for building and openly sharing visa-matrix, the source-tracked, every-passport × every-destination visa-requirements dataset that this project builds upon.

This fork is re-licensed under the GNU GPL v3 (see `LICENSE`). That is permitted because CC BY-SA 4.0 is one-way compatible with GPLv3: an adaptation of a CC BY-SA 4.0 work may be released under GPLv3. Please see: [CC BY-SA 4.0 is now one-way compatible with GPLv3](https://creativecommons.org/2015/10/08/cc-by-sa-4-0-now-one-way-compatible-with-gplv3/).

## Changes from upstream

- Dataset exclusion: the Israeli Occupation (`IL`) is not carried in this fork — not as a passport, not as a destination, not in the `countries` table — and its Wikipedia passport page is skipped at collection time (never fetched). We do not recognise it. #Free Palestine
- Restructures the outputs around the database: the main product is `data/visa_data.db` (SQLite) plus a nested text mirror, `data/visa_data.json`, so changes show up as a readable diff. The old single-axis `visa-matrix.json` is retired and the two CSV exports are opt-in (`build.py --export all`). Build date is pinnable via `--date` / `$BUILD_DATE` for byte-reproducible builds.
- Adds states with limited recognition, hand-curated from their (stub) Wikipedia pages into `data/limited-recognition.json`: Abkhazia (`AB`), South Ossetia (`OS`), Transnistria (`TS`) and Northern Cyprus (`NC`) as both passports and destinations, plus the SADR passport (`EH`) as a passport only (no 'Visa policy of Western Sahara' page exists). A de facto passport is refused where it is not accepted as a travel document; accepted-but-undocumented regimes are marked assumed visa-required. All such cells are single-source (Wikipedia), `confidence=medium`.
- Adds a visa/residency permit layer (`data/visa-benefits.json`, written to the `visa_holdings` + `visa_benefits` tables): 13 common foreign visa/residency holdings and the destinations each unlocks. Seeded from the [Passport Power Index visa-checker's holdings list](https://github.com/jasurshukurov/Passport-Power-Index-Visa-Checker) and re-verified against each destination's own English Wikipedia row before being kept; ~27 of the 250 seed entries were dropped or corrected on that basis (wrong direction, non-matrix territories, duplicates). A benefit only relaxes the underlying passport rule — it never waives a valid passport or the destination's normal admissibility checks.
- Adds per-row source details to `visa_benefits`: every benefit row carries `source_page` + `source_url` pointing at the destination's own 'Visa policy of X' English Wikipedia page (the 29 Schengen members plus Cyprus share the single 'Visa policy of the Schengen Area' page) so each holding is one click away from re-verification. The 13 holdings / 223 rows are generated from `gen_benefits.py`, the single source of truth for `data/visa-benefits.json`.
- Adds a transit axis on `visa_rules` (`transit`, `transit_note`): `free` | `required` | `conditional` | `unknown`, separate from the entry status ladder. The base rule is computed, not scraped — transit is `free` wherever the entry type is `visa-free` or `freedom-of-movement` (airside transit is strictly less privileged than entry) and `unknown` otherwise; cited exceptions live in `data/transit.json` and are applied by `merge_transit()`.
- Adds an airport-only (airside) transit-benefit table (`transit_benefits`) for the Schengen airport-transit-visa regime and the UK Direct Airside Transit regime.
- Adds a mobility-regime table (`mobility_regimes`) for country groups with free-movement or visa-free arrangements.
- Adds a stay-rules table (`stay_rules`) for nationality-scoped stay allowances, such as rolling 90/180 windows.
- Adds a corrections table (`corrections`) for manual post-scrape fixes.
- Adds a test suite covering allowed values, referential integrity, the JSON mirror, and the app merge logic.
- Adds an automated GitHub release pipeline that publishes new data only when the normalised data hash changes.

## Data sources

- English Wikipedia "Visa requirements for X citizens" pages.
- passport-index.org, via the [imorte/passport-index-data](https://github.com/imorte/passport-index-data) project.
- Country and demonym data: [mledoze/countries](https://github.com/mledoze/countries).
- Passport Power Index visa-checker holdings seed: [jasurshukurov/Passport-Power-Index-Visa-Checker](https://github.com/jasurshukurov/Passport-Power-Index-Visa-Checker).

## Attribution

- xpressmike / [visa-matrix](https://github.com/xpressmike/visa-matrix)
- imorte / [passport-index-data](https://github.com/imorte/passport-index-data)
- mledoze / [countries](https://github.com/mledoze/countries)
- jasurshukurov / [Passport-Power-Index-Visa-Checker](https://github.com/jasurshukurov/Passport-Power-Index-Visa-Checker)
