#!/usr/bin/env python3
"""Generate the curated data/visa-benefits.json (the "permit" layer).

Source: VisaCheck (jasurshukurov/Passport-Power-Index-Visa-Checker,
visaBenefits.ts) seeded and then row-aware verified against English Wikipedia.
Each (holding, destination) benefit was checked against the DESTINATION's own
Wikipedia policy — a note in another country's row is that other country's
policy, not the destination's — so several VisaCheck entries were dropped or
corrected. The result is 13 holdings / 222 benefit rows. A row
individually re-verified after the bulk check carries a row-level `checked`;
`entry_type` (a comma list, absent = all entry types) restricts a benefit to
the entry types that qualify for it.

confidence:
  high   -> the destination's own policy documents the benefit
  medium -> fits the known "foreign visa/residence accepted" pattern but is not
            row-documented, or Wikipedia rows conflict (kept conservative)

Every benefit row also carries source_page + source_url: the destination's
"Visa policy of X" Wikipedia article (Schengen states share the single
"Visa policy of the Schengen Area" article). The VISAPOLICY map below is the
canonical-title lookup, resolved once via the Wikipedia API with redirects
applied, so each row re-verifies with one click.

Run from the repo root:  python3 gen_benefits.py
"""
import json
import pathlib

CHECKED = "2026-09-02"

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"

# Canonical "Visa policy of X" Wikipedia article per destination (redirects
# resolved). Schengen-area states share "Visa policy of the Schengen Area".
VISAPOLICY = {
    "AE": "Visa policy of the United Arab Emirates",
    "AG": "Visa policy of Antigua and Barbuda",
    "AL": "Visa policy of Albania",
    "AM": "Visa policy of Armenia",
    "AT": "Visa policy of the Schengen Area",
    "AU": "Visa policy of Australia",
    "AZ": "Visa policy of Azerbaijan",
    "BA": "Visa policy of Bosnia and Herzegovina",
    "BB": "Visa policy of Barbados",
    "BE": "Visa policy of the Schengen Area",
    "BG": "Visa policy of the Schengen Area",
    "BH": "Visa policy of Bahrain",
    "BN": "Visa policy of Brunei",
    "BS": "Visa policy of the Bahamas",
    "BZ": "Visa policy of Belize",
    "CA": "Visa policy of Canada",
    "CH": "Visa policy of the Schengen Area",
    "CL": "Visa policy of Chile",
    "CN": "Visa policy of mainland China",
    "CO": "Visa policy of Colombia",
    "CR": "Visa policy of Costa Rica",
    "CY": "Visa policy of the Schengen Area",
    "CZ": "Visa policy of the Schengen Area",
    "DE": "Visa policy of the Schengen Area",
    "DK": "Visa policy of the Schengen Area",
    "DO": "Visa policy of the Dominican Republic",
    "EE": "Visa policy of the Schengen Area",
    "EG": "Visa policy of Egypt",
    "ES": "Visa policy of the Schengen Area",
    "FI": "Visa policy of the Schengen Area",
    "FR": "Visa policy of the Schengen Area",
    "GE": "Visa policy of Georgia",
    "GR": "Visa policy of the Schengen Area",
    "GT": "Visa policy of Guatemala",
    "HK": "Visa policy of Hong Kong",
    "HN": "Visa policy of Honduras",
    "HR": "Visa policy of the Schengen Area",
    "HU": "Visa policy of the Schengen Area",
    "ID": "Visa policy of Indonesia",
    "IE": "Visa policy of Ireland",
    "IS": "Visa policy of the Schengen Area",
    "IT": "Visa policy of the Schengen Area",
    "JM": "Visa policy of Jamaica",
    "JP": "Visa policy of Japan",
    "KR": "Visa policy of South Korea",
    "KW": "Visa policy of Kuwait",
    "LI": "Visa policy of the Schengen Area",
    "LT": "Visa policy of the Schengen Area",
    "LU": "Visa policy of the Schengen Area",
    "LV": "Visa policy of the Schengen Area",
    "MA": "Visa policy of Morocco",
    "MD": "Visa policy of Moldova",
    "ME": "Visa policy of Montenegro",
    "MK": "Visa policy of North Macedonia",
    "MT": "Visa policy of the Schengen Area",
    "MX": "Visa policy of Mexico",
    "MY": "Visa policy of Malaysia",
    "NI": "Visa policy of Nicaragua",
    "NL": "Visa policy of the Schengen Area",
    "NO": "Visa policy of the Schengen Area",
    "NZ": "Visa policy of New Zealand",
    "OM": "Visa policy of Oman",
    "PA": "Visa policy of Panama",
    "PE": "Visa policy of Peru",
    "PG": "Visa policy of Papua New Guinea",
    "PH": "Visa policy of the Philippines",
    "PL": "Visa policy of the Schengen Area",
    "PT": "Visa policy of the Schengen Area",
    "QA": "Visa policy of Qatar",
    "RO": "Visa policy of the Schengen Area",
    "RS": "Visa policy of Serbia",
    "RU": "Visa policy of Russia",
    "SA": "Visa policy of Saudi Arabia",
    "SE": "Visa policy of the Schengen Area",
    "SG": "Visa policy of Singapore",
    "SI": "Visa policy of the Schengen Area",
    "SK": "Visa policy of the Schengen Area",
    "SV": "Visa policy of El Salvador",
    "TH": "Visa policy of Thailand",
    "TR": "Visa policy of Turkey",
    "TW": "Visa policy of Taiwan",
    "VN": "Visa policy of Vietnam",
    "XK": "Visa policy of Kosovo",
}


def _fallback_page(dest: str) -> str:
    inv = {v: k for k, v in json.load(open(DATA / "countries-iso2.json")).items()}
    return "Visa policy of " + inv.get(dest, dest)


def e(dest, typ, days, conf, note=None, entry_type=None, residence_min=None, checked=None):
    page = VISAPOLICY.get(dest) or _fallback_page(dest)
    row = {"destination": dest, "type": typ, "days": days, "confidence": conf}
    if checked:
        row["checked"] = checked
    if entry_type:
        row["entry_type"] = entry_type
    if residence_min:
        row["residence_min"] = residence_min
    row["note"] = note
    row["source_page"] = page
    row["source_url"] = "https://en.wikipedia.org/wiki/" + page.replace(" ", "_")
    return row


HOLDINGS = [
    ("us-green-card", "US Permanent Residency (Green Card)", "residency", "US",
     "US Lawful Permanent Resident (green card)"),
    ("us-visa", "Valid US Visa (B1/B2, F1, H1B, etc.)", "short_term_visa", "US",
     "Any valid, unexpired US visa"),
    ("schengen-visa", "Schengen Visa", "short_term_visa", "EU",
     "Valid Schengen Area short-stay (Type C) visa"),
    ("schengen-residence", "Schengen/EU Residence Permit", "residency", "EU",
     "Residence permit from a Schengen/EU member state"),
    ("uk-visa", "Valid UK Visa / BRP", "short_term_visa", "GB",
     "Valid UK visa or Biometric Residence Permit"),
    ("ca-pr", "Canadian Permanent Residency", "residency", "CA",
     "Canadian Permanent Resident card"),
    ("ca-visa", "Valid Canadian Visa", "short_term_visa", "CA",
     "Valid Canadian temporary resident visa"),
    ("au-pr", "Australian Permanent Residency", "residency", "AU",
     "Australian Permanent Resident visa"),
    ("uae-residence", "UAE Residence Visa", "residency", "AE",
     "UAE residence visa / permit"),
    ("jp-visa", "Valid Japanese Visa", "short_term_visa", "JP",
     "Valid Japanese visa or residence card"),
    ("gcc-residence", "GCC Residency (SA/QA/OM/BH/KW)", "residency", "SA",
     "Residence permit from a GCC member state"),
    ("sg-visa", "Singapore Work/Residence Permit", "long_term_visa", "SG",
     "Singapore Employment Pass, S Pass, or PR"),
    ("apec-card", "APEC Business Travel Card", "special_permit", "XX",
     "APEC Business Travel Card (ABTC) for expedited border crossing"),
]

SCHENGEN = ["AT", "BE", "BG", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IT",
            "LV", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "CH", "LI"]

B = {}

# ── us-green-card (28 kept; dropped BM AI KY TC CW BQ SX KR PH DO) ──
B["us-green-card"] = [
    e("MX", "visa-free", 180, "high", "FMM tourist card on arrival; US permanent residence accepted"),
    e("CA", "visa-free", 180, "high", "US LPRs enter Canada visa-free; up to 6 months at officer discretion"),
    e("CR", "visa-free", 90, "high", "Wikipedia: 90 days for US permanent residence permit (VisaCheck lists 30)"),
    e("PA", "visa-free", 30, "medium", "Valid US residency document required (unverified)"),
    e("BS", "visa-free", 30, "high", "Valid passport and green card required"),
    e("BZ", "visa-free", 30, "medium", "Wikipedia rows conflict (visa-free 30 vs visa-on-arrival); verify"),
    e("SV", "visa-free", 90, "high", "Valid passport and green card"),
    e("GT", "visa-free", 90, "high", "CA-4 Central American agreement; 90 days shared with HN/SV/NI"),
    e("HN", "visa-free", 90, "medium", "CA-4 Central American agreement; 90 days shared with GT/SV/NI (unverified)"),
    e("NI", "visa-free", 90, "high", "CA-4 Central American agreement"),
    e("JM", "visa-free", 30, "high", "Valid passport and return ticket required"),
    e("AG", "visa-free", 30, "high", "Valid passport required"),
    e("GE", "visa-free", 90, "high", "Valid green card must be presented"),
    e("AL", "visa-free", 90, "high", "Multiple-entry green card qualifies"),
    e("BA", "visa-free", 30, "medium", "Wikipedia: 15 days (ID page) vs 30 days; valid green card required"),
    e("ME", "visa-free", 30, "medium", "Valid green card required (unverified)"),
    e("RS", "visa-free", 90, "high", "Valid green card required"),
    e("TR", "e-visa", 30, "high", "Simplified e-visa for US permanent residence"),
    e("MA", "e-visa", 30, "high", "Wikipedia: e-Visa 30 days (VisaCheck lists visa-free 90)"),
    e("TW", "visa-free", 14, "high", "Wikipedia: ETA form gives 14 days visa-free (VisaCheck lists 30)"),
    e("SG", "e-visa", None, "medium", "Not visa-free: e-Service via local sponsor/agent required; also 96h visa-free transit"),
    e("MY", "visa-free", 30, "medium", "Valid green card and passport required (not documented on Wikipedia)"),
    e("AM", "visa-on-arrival", 120, "high", "Wikipedia: VoA 120 days for US permanent resident permit (VisaCheck lists visa-free 180)"),
    e("BH", "visa-on-arrival", 14, "high", "US green card among accepted documents for VoA"),
    e("QA", "visa-on-arrival", 30, "medium", "Valid green card required (not documented on Wikipedia)"),
    e("OM", "visa-on-arrival", 14, "medium", "14-day e-Visa / VoA for US residence (Wikipedia rows vary 14 visa-free vs e-Visa)"),
    e("AE", "visa-on-arrival", 14, "high", "Wikipedia: VoA 14 days (100 AED) + 14-day extension, or 60-day option (VisaCheck lists visa-free 30)"),
    e("CL", "visa-free", 90, "medium", "Green card substitutes the Chilean national visa (6+ months validity)"),
]

# ── us-visa (19 kept; dropped DO AW BM) ──
B["us-visa"] = [
    e("MX", "visa-free", 180, "high", "Used/unused multiple-entry US visas accepted; FMM tourist card required"),
    e("CA", "eta", 180, "high", "eTA required by air (US non-immigrant B/F/M/J/H/L visa); visa required by land/sea"),
    e("PA", "visa-free", 30, "high", "Valid US visa with 2+ prior US entries"),
    e("CR", "visa-free", 90, "high", "Wikipedia: 90 days for multiple-entry US visa (VisaCheck lists 30)"),
    e("AL", "visa-free", 90, "high", "Multiple-entry US visa used at least once before arrival"),
    e("GE", "visa-free", 90, "high", "Valid US visa required"),
    e("TR", "e-visa", 30, "high", "E-visa available online for valid US visa"),
    e("CO", "visa-free", 90, "high", "US visa substitutes the Colombian national visa"),
    e("GT", "visa-free", 90, "high", "CA-4 agreement; valid US visa required"),
    e("HN", "visa-free", 90, "medium", "CA-4 agreement; valid US visa required (unverified)"),
    e("SV", "visa-free", 90, "high", "CA-4 agreement; valid US visa required"),
    e("NI", "visa-free", 90, "high", "CA-4 agreement; valid US visa required"),
    e("BS", "visa-free", 30, "medium", "Valid US visa required (unverified)"),
    e("BA", "visa-free", 30, "medium", "Wikipedia: 15 days (ID page) vs 30 days; multiple-entry US visa required"),
    e("ME", "visa-free", 30, "high", "Valid US visa required"),
    e("RS", "visa-free", 90, "high", "Valid US visa required"),
    e("MK", "visa-free", 15, "medium", "Multiple-entry US visa required (unverified)"),
    e("AE", "visa-on-arrival", 14, "high", "Wikipedia: VoA 14 days (or 60-day option) for US visa; nationality restrictions apply"),
    e("SG", "transit-free", 4, "high", "96-hour Visa Free Transit Facility (Chinese/Indian nationals transiting by air with US visa)"),
]

# ── schengen-visa (42 kept; dropped DO; RO/BG de-duplicated into the 29 states) ──
B["schengen-visa"] = [
    e(s, "visa-free", 90, "high", "Within the 90/180-day rule") for s in SCHENGEN
] + [
    e("AL", "visa-free", 90, "high", "Multiple-entry Schengen visa used at least once in Schengen before arrival"),
    e("BA", "visa-free", 30, "medium",
      "Multiple-entry Schengen visa required; max 30 days per entry, max 90 days "
      "within any 6-month period; not applicable to Kosovo passport",
      entry_type="multiple", checked="2026-09-09"),
    e("ME", "visa-free", 30, "high", "Valid Schengen visa required"),
    e("MK", "visa-free", 15, "high", "Valid Schengen visa required"),
    e("RS", "visa-free", 90, "high",
      "Multiple-entry Schengen visa required; 90 days within any 180-day period; "
      "visa must remain valid for the entire stay",
      entry_type="multiple", checked="2026-09-09"),
    e("XK", "visa-free", 15, "high",
      "Multiple-entry Schengen visa required; up to 15 days",
      entry_type="multiple", checked="2026-09-09"),
    e("GE", "visa-free", 90, "high", "Valid Schengen visa or residence permit required"),
    e("TR", "e-visa", 30, "high", "E-visa available online; valid Schengen visa simplifies it"),
    e("CO", "visa-free", 90, "high", "Schengen visa with 180+ days validity on arrival"),
    e("PA", "visa-free", 30, "high", "Valid Schengen visa required"),
    e("CR", "visa-free", 30, "medium", "Valid multiple-entry Schengen visa required (unverified)"),
    e("CY", "visa-free", 90, "high",
      "Cyprus: only via a double- or multiple-entry Schengen visa",
      entry_type="double,multiple"),
    e("AM", "visa-on-arrival", 120, "high", "Wikipedia: VoA 120 days for valid Schengen visa (VisaCheck lists visa-free 180)"),
]

# ── schengen-residence (42 kept; CY/IE dropped — not a Schengen-area benefit) ──
B["schengen-residence"] = [
    e(s, "visa-free", 90, "high", "Valid EU/Schengen residence permit; 90/180-day rule for Schengen travel") for s in SCHENGEN
] + [
    e("AL", "visa-free", 90, "high", "Valid Schengen residence permit required"),
    e("BA", "visa-free", 30, "medium",
      "Schengen residence permit required; max 30 days per entry, max 90 days "
      "within any 6-month period; not applicable to Kosovo passport",
      checked="2026-09-09"),
    e("ME", "visa-free", 30, "high", "Valid Schengen residence permit required"),
    e("RS", "visa-free", 90, "high",
      "Schengen residence permit required; 90 days within any 180-day period",
      checked="2026-09-09"),
    e("MK", "visa-free", 15, "high", "Valid Schengen residence permit required"),
    e("GE", "visa-free", 90, "high", "Valid Schengen residence permit required"),
    e("CO", "visa-free", 90, "high", "Accepts both temporary and permanent Schengen residence permits"),
    e("MX", "visa-free", 180, "high", "Wikipedia: 180 days for PERMANENT residence permits only (temporary permits may be refused)", residence_min="permanent"),
    e("TR", "e-visa", 30, "high", "E-visa available online with valid Schengen residence permit"),
    e("PA", "visa-free", 30, "medium", "Valid Schengen residence permit required (unverified)"),
    e("CR", "visa-free", 90, "high", "Wikipedia: 90 days for residence permits (VisaCheck lists 30)"),
    e("AM", "visa-on-arrival", 120, "high", "Wikipedia: VoA 120 days for Schengen/EU residence permit (VisaCheck lists visa-free 180)"),
    e("XK", "visa-free", 15, "high",
      "Schengen residence permit required; up to 15 days",
      checked="2026-09-09"),
]

# ── uk-visa (16 kept; dropped GI AI AW BM) ──
B["uk-visa"] = [
    e("AL", "visa-free", 90, "high", "UK visa used once in issuing country before arrival"),
    e("GE", "visa-free", 90, "high", "Valid UK visa / residence permit required"),
    e("ME", "visa-free", 90, "medium", "Valid UK BRP / eVisa required (unverified)"),
    e("RS", "visa-free", 90, "medium", "Valid UK BRP / eVisa required (unverified)"),
    e("MK", "visa-free", 15, "medium", "Valid UK BRP / eVisa required (unverified)"),
    e("MX", "visa-free", 180, "high", "FMM form required; one of the longest visa-free stays"),
    e("PA", "visa-free", 90, "medium", "Valid UK BRP / eVisa required (unverified)"),
    e("BB", "visa-free", 180, "medium", "Tourism only (unverified)"),
    e("AG", "visa-free", 30, "medium", "Tourism only; proof of accommodation required (unverified)"),
    e("BS", "visa-free", 90, "medium", "Tourism/business; return ticket required (unverified)"),
    e("JM", "visa-free", 90, "medium", "Tourism only; return ticket required (unverified)"),
    e("AM", "visa-on-arrival", 120, "medium", "Wikipedia: VoA 120 days (UK in the accepted list); nationality must not separately require a visa"),
    e("TR", "e-visa", 30, "high", "E-visa required; apply online"),
    e("BH", "e-visa", 14, "high", "e-Visa for UK visa holders (VisaCheck lists 14 days)"),
    e("AE", "visa-on-arrival", 14, "high", "Wikipedia: VoA 14 days (or 60-day option) for UK visa; some nationalities excluded"),
    e("IE", "visa-free", 90, "medium", "British-Irish Visa Scheme (BIVS) — select nationalities"),
]

# ── ca-pr (9 kept; dropped AW CW BQ SX AI BM KY) ──
B["ca-pr"] = [
    e("MX", "visa-free", 180, "high", "FMM tourist card required; valid Canadian PR card and passport"),
    e("CR", "visa-free", 90, "medium", "Wikipedia: 90 days for residence permits (VisaCheck lists 30)"),
    e("PA", "visa-free", 30, "medium", "Valid Canadian PR card required (unverified)"),
    e("BS", "visa-free", 30, "high", "Valid passport and PR card"),
    e("AG", "visa-free", 30, "high", "Valid passport and PR card"),
    e("BZ", "visa-free", 30, "medium", "Valid passport and PR card (unverified)"),
    e("AM", "visa-on-arrival", 120, "high", "Wikipedia: VoA 120 days for Canadian permanent resident permit (VisaCheck lists visa-free 90)"),
    e("GE", "visa-free", 90, "high", "Valid Canadian PR card required"),
    e("MD", "visa-free", 90, "medium", "Valid Canadian PR card required (unverified)"),
]

# ── ca-visa (10 kept; none dropped) ──
B["ca-visa"] = [
    e("MX", "visa-free", 180, "high", "Valid Canadian visa"),
    e("CR", "visa-free", 30, "medium", "Valid Canadian visa (unverified)"),
    e("PA", "visa-free", 30, "high", "Valid Canadian visa"),
    e("GE", "visa-free", 90, "high", "Valid Canadian visa"),
    e("GT", "visa-free", 90, "medium", "CA-4 agreement; valid Canadian visa (unverified)"),
    e("HN", "visa-free", 90, "medium", "CA-4 agreement; valid Canadian visa (unverified)"),
    e("SV", "visa-free", 90, "medium", "CA-4 agreement; valid Canadian visa (unverified)"),
    e("NI", "visa-free", 90, "medium", "CA-4 agreement; valid Canadian visa (unverified)"),
    e("AL", "visa-free", 90, "medium", "Valid Canadian visa (unverified)"),
    e("DO", "visa-free", 30, "medium", "Valid Canadian visa (not row-documented; verify)"),
]

# ── au-pr (6 kept; none dropped) ──
B["au-pr"] = [
    e("NZ", "visa-free", 90, "high", "Trans-Tasman: NZ Resident Visa on arrival possible; NZeTA required for non-Australian passports"),
    e("SG", "transit-free", 4, "high", "96-hour Visa Free Transit Facility (Chinese/Indian nationals with Australian visa, transiting by air)"),
    e("AL", "visa-free", 90, "medium", "Multiple-entry Australian visa used at least once (unverified)"),
    e("GE", "visa-free", 90, "medium", "Valid Australian visa or residence permit required (unverified)"),
    e("TR", "e-visa", 30, "medium", "E-visa available for valid Australian visa (unverified)"),
    e("MX", "visa-free", 180, "medium", "Valid Australian PR accepted; FMM tourist card required (unverified)"),
]

# ── uae-residence (13 kept; none dropped) ──
B["uae-residence"] = [
    e("GE", "visa-free", 90, "high", "Multiple-entry UAE residence permit valid 1+ year on entry (stricter rules from May 2025)", residence_min="long_term"),
    e("OM", "visa-free", 14, "high", "GCC member — UAE residents enter Oman visa-free"),
    e("TR", "visa-free", 90, "high", "UAE residents enjoy visa-free access, 90/180"),
    e("AL", "visa-free", 90, "high", "Wikipedia: 90 days for 10-year UAE residence permit", residence_min="long_term"),
    e("BA", "visa-free", 30, "medium", "Valid UAE residence permit required (unverified)"),
    e("RS", "visa-free", 30, "medium", "Valid UAE residence permit required (unverified)"),
    e("ME", "visa-free", 10, "medium", "Wikipedia: 10 days for UAE residence (VisaCheck lists 30)"),
    e("AM", "visa-on-arrival", 120, "high", "Wikipedia: VoA 120 days for GCC/UAE residence permit (VisaCheck lists visa-free 90)"),
    e("AZ", "visa-on-arrival", 30, "high", "Wikipedia: 30-day tourist visa on arrival for UAE residents"),
    e("BH", "visa-free", 14, "high", "GCC member — inter-GCC travel facilitated"),
    e("KW", "visa-free", 90, "high", "GCC member — some profession restrictions may apply"),
    e("QA", "visa-free", 30, "high", "GCC member — inter-GCC travel facilitated"),
    e("SA", "e-visa", 90, "high", "GCC member — e-Visa available for GCC residents"),
]

# ── jp-visa (4 kept; none dropped) ──
B["jp-visa"] = [
    e("AL", "visa-free", 90, "medium", "Multiple-entry Japan visa used at least once (unverified)"),
    e("GE", "visa-free", 90, "medium", "Valid Japan visa or residence permit required (unverified)"),
    e("TR", "e-visa", 30, "medium", "E-visa available for Japan visa holders (unverified)"),
    e("SG", "transit-free", 4, "high", "96-hour Visa Free Transit Facility (Chinese/Indian nationals with Japan visa, transiting by air)"),
]

# ── gcc-residence (11 kept; none dropped) ──
B["gcc-residence"] = [
    e("GE", "visa-free", 90, "high", "Wikipedia: 90 days for GCC residence valid 1+ year (VisaCheck lists 365)", residence_min="long_term"),
    e("TR", "e-visa", 30, "high", "E-visa available online for GCC residents"),
    e("AL", "visa-free", 90, "medium", "Valid GCC residence permit required; must have been used (unverified)"),
    e("BA", "visa-free", 30, "medium", "Valid GCC residence permit required (unverified)"),
    e("AE", "visa-free", 30, "high", "Inter-GCC travel — GCC residents from other GCC states can enter"),
    e("BH", "visa-free", 14, "high", "Inter-GCC travel facilitated"),
    e("KW", "visa-free", 90, "high", "Inter-GCC travel; some profession restrictions"),
    e("OM", "visa-free", 14, "medium", "Inter-GCC travel; approved-professions list may apply"),
    e("QA", "visa-free", 30, "high", "Inter-GCC travel facilitated"),
    e("SA", "e-visa", 90, "high", "Inter-GCC travel; e-Visa available (profession/salary requirements may apply)"),
    e("EG", "visa-on-arrival", 30, "medium", "Wikipedia: VoA 30 days for GCC residents (VisaCheck lists 30)"),
]

# ── sg-visa (3 kept; none dropped) ──
B["sg-visa"] = [
    e("KR", "transit-free", 30, "medium", "Transit with Singapore work permit (unverified)"),
    e("GE", "visa-free", 90, "medium", "Singapore residence permit (unverified)"),
    e("TR", "e-visa", 30, "medium", "Singapore permit enables e-Visa (unverified)"),
]

# ── apec-card (19 kept; none dropped) ──
B["apec-card"] = [
    e("AU", "visa-free", 90, "high", "Pre-cleared ABTC holders; business purposes; fast-track lanes"),
    e("BN", "visa-free", 90, "high", "Pre-cleared ABTC holders; business purposes"),
    e("CL", "visa-free", 90, "high", "Pre-cleared ABTC holders; business purposes (not row-documented)"),
    e("CN", "visa-free", 60, "high", "Pre-cleared ABTC holders; business purposes"),
    e("HK", "visa-free", 60, "high", "Pre-cleared ABTC holders; business purposes (not row-documented)"),
    e("ID", "visa-free", 60, "high", "Pre-cleared ABTC holders; business purposes"),
    e("JP", "visa-free", 90, "high", "Pre-cleared ABTC holders; fast-track lanes (not row-documented)"),
    e("KR", "visa-free", 90, "high", "Pre-cleared ABTC holders; business purposes (not row-documented)"),
    e("MY", "visa-free", 90, "high", "Wikipedia: up to 90 days for ABTC with pre-clearance (VisaCheck lists 60)"),
    e("MX", "visa-free", 90, "high", "Pre-cleared ABTC holders; business purposes"),
    e("NZ", "visa-free", 90, "high", "Pre-cleared ABTC holders; business purposes (not row-documented)"),
    e("PG", "visa-free", 60, "high", "Pre-cleared ABTC holders; business purposes"),
    e("PE", "visa-free", 90, "high", "Pre-cleared ABTC holders; business purposes (not row-documented)"),
    e("PH", "visa-free", 59, "high", "Pre-cleared ABTC holders; business purposes (not row-documented)"),
    e("RU", "visa-free", 90, "medium", "Pre-cleared ABTC holders; participation may be affected by sanctions — verify current status"),
    e("SG", "visa-free", 60, "high", "Wikipedia: up to 60 days for ABTC with pre-clearance"),
    e("TW", "visa-free", 90, "high", "Wikipedia: up to 90 days for ABTC with pre-clearance"),
    e("TH", "visa-free", 90, "high", "Pre-cleared ABTC holders; business purposes"),
    e("VN", "visa-free", 90, "high", "Wikipedia: up to 90 days for ABTC with pre-clearance (VisaCheck lists 60)"),
]


def build_payload():
    return {
        "source": ("Curated from VisaCheck (jasurshukurov/Passport-Power-Index-Visa-Checker, "
                   "visaBenefits.ts, 13 holdings, single 2026-02-15 commit, co-authored with an "
                   "LLM — no per-entry provenance) and row-aware verified against English Wikipedia. "
                   "Each (holding, destination) benefit was checked against the DESTINATION's own "
                   "policy: a note in another country's row is that other country's policy, not the "
                   "destination's — several VisaCheck entries were dropped or corrected on that basis. "
                   "Each row carries source_page + source_url (the destination's 'Visa policy of X' "
                   "Wikipedia page) for one-click re-verification."),
        "checked": CHECKED,
        "confidence_key": {
            "high": "destination's own policy documents the benefit (may still override "
                    "VisaCheck's day count where Wikipedia is more current)",
            "medium": "fits the known 'foreign visa/residence accepted' pattern but is not "
                      "row-documented, or Wikipedia rows conflict — kept at a conservative value",
        },
        "golden_rule": "The passport still matters. These holdings relax (never eliminate) the "
                       "underlying passport rule: the traveller must still hold a valid passport, "
                       "meet normal admissibility checks, and the holding only helps where the "
                       "destination's own policy documents it.",
        "holdings": [
            {"id": hid, "name": name, "category": cat, "issuing_country": iso, "note": note}
            for (hid, name, cat, iso, note) in HOLDINGS
        ],
        "benefits": B,
    }


def build():
    out = build_payload()
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / "visa-benefits.json"
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    total = sum(len(v) for v in B.values())
    print(f"wrote {path}")
    print(f"holdings: {len(HOLDINGS)}  total benefit entries: {total}")
    for hid in [h[0] for h in HOLDINGS]:
        print(f"  {hid}: {len(B[hid])}")


if __name__ == "__main__":
    build()
