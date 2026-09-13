![Build status](https://github.com/The-Omni-Stuart/VisaDB/actions/workflows/release.yml/badge.svg)
![Licence: GPL v3](https://img.shields.io/github/license/The-Omni-Stuart/VisaDB)
![Latest release](https://img.shields.io/github/v/release/The-Omni-Stuart/VisaDB?label=latest%20release)

# VisaDB

VisaDB is a fork of [xpressmike/visa-matrix](https://github.com/xpressmike/visa-matrix), adapted to produce a machine-readable database of visa, transit, and travel-permit rules for every passport × destination, and serves as the data source for the Visa Vole Android application.

## Project Summary

203 passport codes are catalogued against 202 destination codes, giving 40,804 corridors after self-pairs are omitted. Each corridor records where its value came from and whether an independent source agrees, rather than taking a single number from one aggregator at face value.

```json
{
  "type": "visa-free",
  "days": 30,
  "source": "wikipedia",
  "checked": "2026-07-20",
  "confidence": "disputed",
  "dispute": {
    "wikipedia": "visa-free",
    "passport-index": "e-visa"
  }
}
```

When sources disagree, the row flags it as `disputed` rather than silently picking a winner.

Beyond the entry matrix, VisaDB models two things a bare passport-versus-destination grid cannot:

- **Transit**: whether you can transit a country airside. This is independent of whether you can enter it; visa-free entry does not always mean a visa-free airside connection, and vice versa.
- **Permits**: what a foreign travel document you also hold, such as a US green card, a Schengen residence card, or an APEC Business Travel Card, unlocks in addition to your passport.

The main file produced is `data/visa_data.db`, an SQLite database with the entry, transit, and permit data in one file. A nested JSON mirror, `data/visa_data.json`, is written alongside it so changes may be viewed as a readable diff.

## Current dataset

| Measure | Current value |
|---|---:|
| Passport codes | 203 |
| Destination codes | 202 |
| Corridors | 40,804 |
| Visa/residency benefit rows | 223 |
| Stay-rule rows | 33 |
| Transit-benefit rows | 9 |
| Mobility regimes | 15 |
| Manual corrections | 9 |

## Data model

`data/visa_data.db` contains nine tables:

| Table | Contents |
|---|---|
| `meta` | Dataset name, version, generation date, counts, and source notes |
| `countries` | Two-letter ISO code, name, and region for the 203 codes in the dataset |
| `visa_rules` | One row per corridor: entry `type`, `days`, `window_period_days`, `valid_to`, `confidence`, `source`, `checked`, `dispute` claims, `note`, and the transit axis (`transit` + `transit_note`) |
| `corrections` | Manual overrides applied after the scrape, for policy changes the sources still lag |
| `visa_holdings` | The 13 foreign travel documents modelled by the permit layer |
| `visa_benefits` | One row per holding/destination pair: what that document grants there |
| `mobility_regimes` | Country groups with free-movement or visa-free arrangements |
| `stay_rules` | Nationality-scoped stay allowances, such as rolling 90/180 windows |
| `transit_benefits` | Airport-only (airside) transit benefits granted by a holding at a hub |

`data/visa_data.json` mirrors the same data as a nested grid. Matrix cells carry both the entry status and the transit axis, with `countries`, `corrections`, `holdings`, `benefits`, `mobility_regimes`, `stay_rules`, and `transit_benefits` as top-level keys.

### Entry types

`visa_rules.type` can be:

- `visa-free`
- `freedom-of-movement`
- `eta` (electronic travel authorisation: ESTA, eTA, K-ETA, etc.)
- `visa-on-arrival`
- `e-visa`
- `visa-required`
- `refused`

Confidence values:

- `high`: the main source and the cross-check agree. An ETA is treated as compatible with a bare "visa-free" claim, because sources label that regime either way.
- `medium`: a single source documents the corridor.
- `disputed`: the sources disagree; both claims are stored in `dispute`.

`days` is the stay granted on entry. It is present only for regimes that grant entry up front (`visa-free`, `eta`, `visa-on-arrival`, `e-visa`, and `freedom-of-movement`) and never exceeds a year. Source prose can mix stay length with visa validity or age limits, so values over one year are rejected.

### Transit

Transit is a separate axis from entry. `visa_rules` carries `transit` (`free`, `required`, `conditional`, or `unknown`) and a `transit_note`.

The base rule is calculated, not stored: transit is `free` wherever entry is `visa-free` or `freedom-of-movement`, because airside transit is strictly less privileged than entry; if you can enter without a visa, you can remain in the international transit area. Every other corridor starts `unknown` and is filled from the checked, cited overlay in `data/transit.json` (37 policies plus 12 explicit corridor overrides), the same pattern as `limited-recognition.json`.

- `required`: a transit visa is needed even for an airside connection.
- `free`: no transit visa is needed despite a non-visa-free entry requirement, for example the Schengen airside transit privilege, the UK Direct Airside Transit Visa exemption, or the US C-1 / ESTA split.
- `conditional`: transit is permitted only with booked, legally approved onward travel to a third country, for example China 24 h / 240 h TWOV.
- `unknown`: no documented airside transit rule was found.

### Visa and residency holdings (permit layer)

A passport is not the only travel document that changes what you can enter. If you hold a US green card, a UK visa, an APEC Business Travel Card, or GCC residence, several destinations let you in on that document alone or relax the rule your passport alone would receive.

`visa_holdings` defines the 13 holdings:

```text
us-green-card   us-visa          schengen-visa     schengen-residence
uk-visa         ca-pr            ca-visa           au-pr
uae-residence   jp-visa          gcc-residence     sg-visa
apec-card
```

Each holding has a `category` (`residency`, `short_term_visa`, `long_term_visa`, or `special_permit`) and an `issuing_country`.

`visa_benefits` stores one row per holding/destination pair. Each row carries `type`, `days`, optional `entry_type` (comma list; absent = all entry types), optional `residence_min`, `confidence`, `source`, `checked` (bulk check date or row-level re-check date), a `note` with the supporting Wikipedia wording, and `source_page` + `source_url`. The source page is the destination's own "Visa policy of X" Wikipedia page; the 29 Schengen states plus Cyprus share the single "Visa policy of the Schengen Area" page.

The holdings were seeded from the list compiled by jasurshukurov for their [Visa-Checker application](https://github.com/jasurshukurov/Passport-Power-Index-Visa-Checker) (250 entries) and verified against the destination's own Wikipedia row before being kept. A note in another country's row describes that other country's policy, not the destination's, so an entry is only `confidence: "high"` when the destination's own row documents it. This check dropped about 27 seed entries (wrong direction, non-matrix territories, duplicates) and corrected the rest.

Two rules:

- A benefit only relaxes the underlying passport rule. It never removes the need for a valid passport or the destination's normal admissibility checks, such as proof of funds or an onward ticket.
- The app still merges each benefit against the traveller's passport result and keeps the easier outcome. A green card cannot make a `refused` corridor enterable.

`data/visa-benefits.json` is generated by `gen_benefits.py`; the curated holdings and benefits live in that script as the single source of truth. `build.py` loads it into the two tables.

### Stay rules and mobility regimes

`stay_rules` stores the facts the app needs to calculate how long a traveller may stay: `zone`, `window_type`, `window_days`, `window_period_days`, `extension`, `multiple_entry`, `nationalities`, `valid_from`, `valid_to`, `source`, and `note`. The app performs the calculation using the traveller's travel history; the database stores the rule, not the traveller's history.

`mobility_regimes` is explanatory. It records country groups and which members currently exercise each mobility right, using `members`, `associates`, and `deactivated`. This lets the app explain why a corridor is `visa-free` or `freedom-of-movement`. It does not change the passport-to-destination entry rule.

`transit_benefits` stores airport-only benefits by `holding` and `hub`, with `transit_type`, `note`, and `source_url`. The current hubs are the Schengen airport-transit-visa regime and the UK Direct Airside Transit regime.

## Files

| File or directory | Role |
|---|---|
| `data/visa_data.db` | Main SQLite form used by the app, with all axes in one file |
| `data/visa_data.json` | Nested text mirror of the DB, for diffing and inspection |
| `data/visa-matrix-iso2.csv`, `data/visa-matrix-tidy.csv` | Opt-in exports (`build.py --export all`); lossy convenience views of the entry grid |
| `data/countries-iso2.json`, `data/demonyms-iso2.json` | Inputs: country and demonym to ISO2 maps used to join the sources |
| `data/overrides.json` | Manual corrections applied after the scrape |
| `data/limited-recognition.json` | Hand-checked rules for states with limited recognition |
| `data/transit.json` | Checked, cited transit rules: policies plus corridor overrides |
| `data/visa-benefits.json` | Permit layer, generated by `gen_benefits.py` |
| `data/mobility-regimes.json` | Mobility-regime input, generated by `gen_mobility.py` |
| `data/stay-rules.json` | Stay-rule input, generated by `gen_stay_rules.py` |
| `data/transit-benefits.json` | Transit-benefit input, generated by `gen_transit_benefits.py` |
| `build.py` | Main stdlib-only build script |
| `sources/` | Scrapers for Wikipedia and passport-index.org |
| `gen_benefits.py`, `gen_mobility.py`, `gen_stay_rules.py`, `gen_transit_benefits.py` | Scripts that write the hand-checked data files |
| `test_visadb.py` | Tests for allowed values, referential integrity, the JSON mirror, and the app merge logic |
| `tools/release_gate.py` | Release sanity checks, normalised SHA256 data hash, and release metadata |
| `.github/workflows/release.yml` | Automated build and release workflow |

The DB and JSON are the committed product and are never gitignored. The CSV exports are generated on demand and are gitignored.

## Passport coverage

Passports with an English Wikipedia ["Visa requirements for X citizens"](https://en.wikipedia.org/wiki/Category:Visa_requirements_by_nationality) page (around 180 pages) use Wikipedia as the primary source for the corridors that page covers, with passport-index as the cross-check. Corridors a page does not list fall back to passport-index (`"source": "passport-index", "confidence": "medium"` until a second source confirms them).

States with limited recognition (Abkhazia, South Ossetia, Transnistria, Northern Cyprus) are carried as both passports and destinations, and the SADR passport is carried as a passport only. None has a full Wikipedia visa matrix, so their rules are hand-checked in `data/limited-recognition.json` and merged after the scrape. A de facto passport is `refused` where it is not accepted as a travel document (the app shows this grey); accepted but undocumented regimes are marked assumed `visa-required`. All such cells are single-source (Wikipedia) with `confidence: "medium"`.

## Sources

- Primary: English Wikipedia visa-requirements pages, community-maintained, cited per row (mostly Timatic and government pages), quick to reflect rule changes, and carrying machine-readable day counts.
- Cross-check / fallback: [imorte/passport-index-data](https://github.com/imorte/passport-index-data), scraped from [passportindex.org](https://www.passportindex.org).
- Country and demonym resolution: [mledoze/countries](https://github.com/mledoze/countries).

## Build and test

The project uses only the standard Python library.

```sh
python3 gen_benefits.py
python3 gen_mobility.py
python3 gen_stay_rules.py
python3 gen_transit_benefits.py
python3 build.py
# Or, for the optional CSV exports:
# python3 build.py --export all
python3 test_visadb.py
python3 tools/release_gate.py --dist dist
```

Run the `gen_*.py` scripts after changing the hand-checked data in those files. `build.py` scrapes the sources, applies the manual and generated layers, and writes the DB and JSON files. `test_visadb.py` checks allowed values, referential integrity, mirror consistency, and the app merge logic. `tools/release_gate.py` runs release sanity checks and writes the normalised data hash and release metadata.

Use `--date YYYY-MM-DD`, or set `BUILD_DATE`, to pin the generated/check dates for a reproducible build.

## Automated releases

`.github/workflows/release.yml` runs weekly, on pushes to `main`, and when manually triggered. Each run:

1. Builds the dataset with a fixed UTC build date.
2. Runs the test suite.
3. Runs the release check.
4. Compares the normalised SHA256 data hash with the latest data release.
5. Creates a GitHub Release only if the data hash changed.

The normalised hash ignores `meta.generated` and the per-row `checked` values, so a rebuild that only changes dates does not create a new release. If the build, tests, or release check fails, the workflow stops and no release is created.

Release assets include `visa_data.db`, `visa_data.json`, `SHA256SUMS`, `build-manifest.json`, and `data-hash.txt`.

## App integration

The Visa Vole app bundles `visa_data.db` as a read-only asset. It reads the passport rules, permit and transit benefits, stay rules, and country data, then combines them at runtime for the documents the traveller holds. When the bundled database is replaced, the app's `VisaDb.DB_VERSION` constant must be increased so existing installs copy the new file.

## Limits and contributions

VisaDB is reference data, not legal advice. Visa rules change often and can depend on nationality, document type, entry point, length of stay, and reason for travel. Always check the relevant official government source before travelling.

The dataset is maintained through regular rebuilds, and any and all community corrections and contributions are welcome through pull requests. Builds are checked by the test suite and the release check.

## Licence

[GPLv3](LICENSE). VisaDB is a fork of [xpressmike/visa-matrix](https://github.com/xpressmike/visa-matrix), re-licensed from CC BY-SA 4.0 to GPLv3 under the [CC BY-SA 4.0 → GPLv3 one-way compatibility declaration](https://creativecommons.org/2015/10/08/cc-by-sa-4-0-now-one-way-compatible-with-gplv3/). The original CC BY-SA 4.0 text is retained in `LICENSE-CC-BY-SA-4.0.txt`. For further notes on attribution, please see [NOTICE](NOTICE.md).
