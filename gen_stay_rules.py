"""Generate data/stay-rules.json — the curated stay-rule facts (rolling
windows, shared zones/pools, extensions, multiple-entry, validity).

This is the DB half of the stay-rules feature: it stores the *facts* (the
window type and size, whether the allowance is a shared pool, extension caps,
which nationalities it applies to, and when it starts/ends). The *computation*
of "how many days do I have left" is app logic — it needs the user's own travel
history, which the DB never sees.

Source of truth (like transit.json / mobility-regimes.json). Run:
    python3 gen_stay_rules.py
"""
import json
import pathlib

DATA = pathlib.Path(__file__).parent / "data"

# nationalities sentinels (documented, resolved by the app):
#   "*"     -> all visa-exempt nationals at that destination
#   "EU-EEA"-> EU/EEA nationals (the standard European visa-exempt group).
#              Kept as a literal token (not a 2-letter ISO2) so the merge can
#              tell sentinels apart from real country codes.

RULES = [
    # --- shared pools (zones) -------------------------------------------------
    {
        "id": "schengen",
        "zone": "schengen",
        "zone_name": "Schengen Area",
        "countries": ["AT", "BE", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "HU",
                      "IS", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL",
                      "PT", "RO", "SK", "SI", "ES", "SE", "CH"],
        "window_type": "rolling",
        "window_days": 90,
        "window_period_days": 180,
        "extension": None,
        "multiple_entry": 1,
        "nationalities": ["*"],
        "valid_from": None,
        "valid_to": None,
        "source": "Schengen Area (Visa policy of the Schengen Area)",
        "note": ("90 days in any 180-day period (rolling). The 90 days are a "
                 "single shared pool across all 27 member states: time spent in "
                 "one member counts against the same allowance as in another."),
    },
    # CA-4: a shared pool, but each member grants a different per-entry allowance.
    {
        "id": "ca4-gt", "zone": "ca4", "zone_name": "CA-4 (Central America)",
        "countries": ["GT"], "window_type": "per-entry", "window_days": 90,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "CA-4 Border Control Agreement (Guatemala)",
        "note": ("CA-4: the allowance is shared across all four countries "
                 "(GT/SV/HN/NI); total time in the zone counts against one pool."),
    },
    {
        "id": "ca4-ni", "zone": "ca4", "zone_name": "CA-4 (Central America)",
        "countries": ["NI"], "window_type": "per-entry", "window_days": 90,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "CA-4 Border Control Agreement (Nicaragua)",
        "note": "CA-4: shared pool (GT/SV/HN/NI).",
    },
    {
        "id": "ca4-sv", "zone": "ca4", "zone_name": "CA-4 (Central America)",
        "countries": ["SV"], "window_type": "per-entry", "window_days": 180,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["GB", "US", "EU-EEA", "RU"], "valid_from": None, "valid_to": None,
        "source": "CA-4 Border Control Agreement (El Salvador)",
        "note": "CA-4: 180 days (UK/US/EU/RU nationals); shared pool (GT/SV/HN/NI).",
    },
    {
        "id": "ca4-hn", "zone": "ca4", "zone_name": "CA-4 (Central America)",
        "countries": ["HN"], "window_type": "per-entry", "window_days": 90,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["US"], "valid_from": None, "valid_to": None,
        "source": "CA-4 Border Control Agreement (Honduras)",
        "note": ("CA-4: 90 days (US nationals); GB requires a visa since Aug 2024; "
                 "shared pool (GT/SV/HN/NI)."),
    },
    # --- single-destination rules --------------------------------------------
    {
        "id": "gb", "zone": None, "zone_name": None,
        "countries": ["GB"], "window_type": "per-entry", "window_days": 180,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of the United Kingdom (Standard Visitor)",
        "note": "Up to 180 days per entry (Standard Visitor).",
    },
    {
        "id": "western-balkans", "zone": None, "zone_name": None,
        "countries": ["BA", "ME", "MK", "RS"], "window_type": "rolling",
        "window_days": 90, "window_period_days": 180, "extension": None,
        "multiple_entry": 0, "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Bosnia & Herzegovina / Montenegro / North Macedonia / Serbia",
        "note": ("90 days in any 180-day period (rolling). The same rule for all "
                 "four Western Balkan states; this is NOT a shared pool (unlike "
                 "CA-4/Schengen). Montenegro will require a visa for Russian "
                 "nationals from 2026-11-01."),
    },
    {
        "id": "ua", "zone": None, "zone_name": None,
        "countries": ["UA"], "window_type": "rolling", "window_days": 90,
        "window_period_days": 180, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Ukraine",
        "note": "90 days in any 180-day period (rolling).",
    },
    {
        "id": "md", "zone": None, "zone_name": None,
        "countries": ["MD"], "window_type": "rolling", "window_days": 90,
        "window_period_days": 180, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Moldova",
        "note": "90 days in any 180-day period (rolling).",
    },
    {
        "id": "ge", "zone": None, "zone_name": None,
        "countries": ["GE"], "window_type": "per-entry", "window_days": 365,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Georgia",
        "note": "365 days per entry for ~95 nationalities; travel insurance mandatory from 2026-01-01.",
    },
    {
        "id": "al-90180", "zone": None, "zone_name": None,
        "countries": ["AL"], "window_type": "rolling", "window_days": 90,
        "window_period_days": 180, "extension": None, "multiple_entry": 0,
        "nationalities": ["GB", "EU-EEA"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Albania",
        "note": "UK/EU: 90 days in any 180-day period.",
    },
    {
        "id": "al-us-365", "zone": None, "zone_name": None,
        "countries": ["AL"], "window_type": "per-entry", "window_days": 365,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["US"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Albania",
        "note": "US: 365 days.",
    },
    {
        "id": "tr", "zone": None, "zone_name": None,
        "countries": ["TR"], "window_type": "rolling", "window_days": 90,
        "window_period_days": 180, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Turkiye",
        "note": "90 days in any 180-day period (rolling).",
    },
    {
        "id": "us", "zone": None, "zone_name": None,
        "countries": ["US"], "window_type": "per-entry", "window_days": 90,
        "window_period_days": None, "extension": 90, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa Waiver Programme (United States)",
        "note": "90 days (VWP B-1/B-2); extensions up to 180 days at CBP officer discretion.",
    },
    {
        "id": "mx", "zone": None, "zone_name": None,
        "countries": ["MX"], "window_type": "per-entry", "window_days": 180,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Mexico (FMM)",
        "note": "Up to 180 days per entry (FMM).",
    },
    {
        "id": "cr", "zone": None, "zone_name": None,
        "countries": ["CR"], "window_type": "per-entry", "window_days": 180,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Costa Rica",
        "note": "Up to 180 days at officer discretion (Group 1). Not part of CA-4.",
    },
    {
        "id": "pa", "zone": None, "zone_name": None,
        "countries": ["PA"], "window_type": "per-entry", "window_days": 90,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Panama",
        "note": "90 days per entry. Not part of CA-4.",
    },
    {
        "id": "co", "zone": None, "zone_name": None,
        "countries": ["CO"], "window_type": "per-entry", "window_days": 90,
        "window_period_days": None, "extension": 90, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Colombia",
        "note": "90 days per entry, extendable by +90; cap 180 days in any 12 months.",
    },
    {
        "id": "pe", "zone": None, "zone_name": None,
        "countries": ["PE"], "window_type": "per-entry", "window_days": 90,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Peru",
        "note": "90 days per entry, extendable; cap 183 days in a rolling 365-day period.",
    },
    {
        "id": "jp", "zone": None, "zone_name": None,
        "countries": ["JP"], "window_type": "per-entry", "window_days": 90,
        "window_period_days": None, "extension": 90, "multiple_entry": 1,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Japan",
        "note": "90 days per entry; multiple entry; extendable by +90 (UK nationals).",
    },
    {
        "id": "kr", "zone": None, "zone_name": None,
        "countries": ["KR"], "window_type": "per-entry", "window_days": 90,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of South Korea",
        "note": ("90 days per entry. K-ETA exemption for GB/US/etc. nationals "
                 "expires 2026-12-31 (an entry requirement, not a stay cap)."),
    },
    # --- time-limited stay grants (T3: validity) -----------------------------
    {
        "id": "cn-gb-ar", "zone": None, "zone_name": None,
        "countries": ["CN"], "window_type": "per-entry", "window_days": 30,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["GB", "AR"], "valid_from": None, "valid_to": "2026-12-31",
        "source": "Visa policy of China",
        "note": "30-day visa-free for GB & AR, until 2026-12-31.",
    },
    {
        "id": "cn-ru", "zone": None, "zone_name": None,
        "countries": ["CN"], "window_type": "per-entry", "window_days": 30,
        "window_period_days": None, "extension": None, "multiple_entry": 0,
        "nationalities": ["RU"], "valid_from": None, "valid_to": "2027-12-31",
        "source": "Visa policy of China",
        "note": "30-day visa-free for RU, until 2027-12-31.",
    },
    # --- phase-2 expansions (verified against official sources 2026-09-05) ----
    # EAC: a shared pool (the unique value of this layer) — a single 90-day
    # (3-month) tourist-visa validity, multiple entry, shared across KE/UG/RW.
    {
        "id": "eac", "zone": "eac", "zone_name": "East African Community (EATV)",
        "countries": ["KE", "UG", "RW"], "window_type": "rolling",
        "window_days": 90, "window_period_days": 90, "extension": None,
        "multiple_entry": 1, "nationalities": ["*"], "valid_from": None,
        "valid_to": None,
        "source": "East African Tourist Visa (Uganda NCIC)",
        "note": ("East African Tourist Visa (EATV): a single 90-day / 3-month "
                 "validity from date of issue, shared across KE/UG/RW — time in "
                 "one state counts against the same allowance as another. "
                 "Multiple entry, tourism only (employment prohibited), not "
                 "extendable, not renewable, ~USD 100. Visa-based (a paid "
                 "tourist visa), so it applies to nationalities that otherwise "
                 "require a visa; the issuing country should be the first "
                 "entry point."),
    },
    # Thailand: the 60-day visa-exemption (revised 2024-07-15) is non-trivial
    # because it carries a +30 extension and a specific effective date.
    {
        "id": "th", "zone": None, "zone_name": None,
        "countries": ["TH"], "window_type": "per-entry", "window_days": 60,
        "window_period_days": None, "extension": 30, "multiple_entry": 0,
        "nationalities": ["*"], "valid_from": "2024-07-15", "valid_to": None,
        "source": "Thailand MFA visa-exemption (revised 16 Jul 2024)",
        "note": ("60 days per entry (visa exemption), extendable by +30 days at "
                 "immigration discretion; rule revised effective 2024-07-15 "
                 "(widely applicable — 93+ nationalities)."),
    },
    # Brazil for EU/EEA: a rolling 90/180 window (non-trivial vs a bare count).
    {
        "id": "br-eu-90180", "zone": None, "zone_name": None,
        "countries": ["BR"], "window_type": "rolling", "window_days": 90,
        "window_period_days": 180, "extension": None, "multiple_entry": 0,
        "nationalities": ["EU-EEA"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Brazil (MRE)",
        "note": "EU/EEA nationals: 90 days in any 180-day period (visa-exempt "
                "visitor stay).",
    },
    # Argentina for IN: nationality-scoped bilateral with multiple-entry + a
    # multi-year visa validity (non-trivial structure).
    {
        "id": "ar-in-bilateral", "zone": None, "zone_name": None,
        "countries": ["AR"], "window_type": "per-entry", "window_days": 90,
        "window_period_days": None, "extension": None, "multiple_entry": 1,
        "nationalities": ["IN"], "valid_from": None, "valid_to": None,
        "source": "Visa policy of Argentina (Cancillería, AR-IN bilateral)",
        "note": "Indian nationals: 90 days per entry under the Argentina-India "
                "bilateral tourist/business agreement; multiple-entry visa "
                "valid up to 5 years.",
    },
]

doc = {
    "source": ("Stay-rule FACTS layer (a `stay_rules` table). Stores the "
               "nationality-scoped stay allowances: window type (rolling vs "
               "per-entry), window size (X/Y), whether the allowance is a shared "
               "pool/zone, extension caps, multiple-entry, which nationalities it "
               "applies to, and valid_from/valid_to. The 'how many days do I have "
               "left' computation is APP logic (needs the user's travel history), "
               "never stored here. Phase-1 seed curated from "
               "docs/stay-rules-verified.md; phase-2 additions (EAC shared pool, "
               "Thailand, Brazil-EU, Argentina-India) verified against official "
               "sources 2026-09-05. Re-verify per rule before relying on it."),
    "checked": "2026-09-05",
    "note": ("window_type: 'per-entry' (up to window_days each entry) or "
             "'rolling' (up to window_days in any window_period_days). zone: "
             "shared pool id — rows sharing a zone pool their allowances "
             "(Schengen: one 90/180 pool across 27 states; CA-4: one pool across "
             "GT/SV/HN/NI with per-country allowances). nationalities may contain "
             "the sentinels '*' (all visa-exempt nationals) and 'EU-EEA' "
              "(EU/EEA nationals); the app resolves them. valid_from/valid_to "
              "bound when the grant applies. DB stores facts; the app computes "
              "the balance."),
    "rules": RULES,
}

out = DATA / "stay-rules.json"
with open(out, "w") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"wrote {out} ({len(RULES)} stay-rule grants)")
