"""Generate data/transit-benefits.json — T4: foreign holdings that confer
transit (airside) rights at a hub.

This is the DB half of the "a holding confers transit" feature (backlog T4).
Entry is already per-holding (visa_benefits relaxes the *entry* ladder); this
layer relaxes the *transit* axis (visa_rules.transit) — e.g. a US green card
waives the Schengen airport transit visa even for a passport that would
otherwise need one.

Only VERIFIED benefits are stored, each with a source_url. A MISSING row means
"no documented transit benefit from that holding at that hub" — the corridor's
base transit rule applies. This is a deliberate, honest absence: where the
official position is unclear (e.g. most UK-DATV holdings after the 2024 rules
restructure) no row is written rather than guessing.

hub is a transit-regime id, not a country:
    'schengen'  = Schengen airport-transit-visa (ATV) regime (the 27-state zone)
    'uk'        = UK transit regime (Direct Airside Transit / Visitor in Transit)
The app resolves a transit airport to a regime before querying this table.

transit_type uses the same vocabulary as visa_rules.transit
(free | required | conditional | unknown):
    'free'        = the holding waives the transit visa (airside; see note)
    'conditional' = waived only under the stated conditions (the visa-based
                    Schengen exemptions require travel to/from the issuing
                    country, or the return leg immediately after using the visa)

Source of truth. Verified 2026-09-04 against the EU Visa Code (Reg (EC)
810/2009, as amended by (EU) 2019/1155, + Annex V; C(2024) 4319 Visa Code
Handbook; Germany AA FAQ; France-Visas) and gov.uk. Run:
    python3 gen_transit_benefits.py
"""
import json
import pathlib

DATA = pathlib.Path(__file__).parent / "data"

VC = ("https://eur-lex.europa.eu/legal-content/EN/TXT/?"
      "uri=CELEX:32009R0810")          # EU Visa Code (Art. 3, Annex IV/V)
ATV = ("https://home-affairs.ec.europa.eu/policies/schengen/visa-policy/"
       "applying-schengen-visa_en")    # EC ATV explainer + Annex 7A/7B
DATV = "https://www.gov.uk/transit-visa/direct-airside-transit-visa"

BENEFITS = [
    # ---- Schengen airport-transit-visa regime (hub: 'schengen') -------------
    {
        "holding": "schengen-visa", "hub": "schengen", "transit_type": "free",
        "note": ("A valid Schengen (uniform) visa, national long-stay visa, or "
                 "residence permit issued by a Member State — no airport "
                 "transit visa needed (full Schengen access includes transit)."),
        "source_url": VC,
    },
    {
        "holding": "schengen-residence", "hub": "schengen", "transit_type": "free",
        "note": "A valid residence permit issued by a Schengen/EU Member State — "
                "no airport transit visa needed.",
        "source_url": VC,
    },
    {
        "holding": "us-green-card", "hub": "schengen", "transit_type": "free",
        "note": ("A valid US permanent resident card (green card / I-551) "
                 "guarantees unconditional readmission, so no Schengen airport "
                 "transit visa is needed for airside transit. Airside only — "
                 "leaving the international transit area needs a Schengen "
                 "short-stay visa."),
        "source_url": VC,
    },
    {
        "holding": "ca-pr", "hub": "schengen", "transit_type": "free",
        "note": "A valid Canadian permanent resident card guarantees "
                "unconditional readmission, so no Schengen airport transit "
                "visa is needed for airside transit. Airside only.",
        "source_url": VC,
    },
    {
        "holding": "us-visa", "hub": "schengen", "transit_type": "conditional",
        "note": ("A valid US visa exempts from the Schengen airport transit "
                 "visa, but only when travelling to/from the US (or to another "
                 "third country, or returning from the US immediately after "
                 "using the visa). Airside only."),
        "source_url": VC,
    },
    {
        "holding": "ca-visa", "hub": "schengen", "transit_type": "conditional",
        "note": "A valid Canadian visa exempts from the Schengen airport "
                "transit visa, but only when travelling to/from Canada (or to "
                "another third country, or returning from Canada immediately "
                "after using the visa). Airside only.",
        "source_url": VC,
    },
    {
        "holding": "jp-visa", "hub": "schengen", "transit_type": "conditional",
        "note": "A valid Japanese visa exempts from the Schengen airport "
                "transit visa, but only when travelling to/from Japan (or to "
                "another third country, or returning from Japan immediately "
                "after using the visa). Airside only.",
        "source_url": VC,
    },
    {
        "holding": "uk-visa", "hub": "schengen", "transit_type": "conditional",
        "note": ("DISCREPANCY: a valid UK residence permit (BRP/ILR) is listed "
                 "as a Schengen airport-transit-visa exemption in the 2024 EU "
                 "Visa Code Handbook (point (c)) and French practice (must "
                 "guarantee unconditional readmission), but is NOT listed in "
                 "the 2019 Visa Code Annex V or Germany's FAQ. Applies to the "
                 "residence permit only — NOT a UK visitor visa. Airside only. "
                 "Verify with the specific transit state before travel."),
        "source_url": ATV,
    },

    # ---- UK transit regime (hub: 'uk') --------------------------------------
    {
        "holding": "uk-visa", "hub": "uk", "transit_type": "free",
        "note": ("A valid UK Standard Visitor visa is explicitly listed on "
                 "gov.uk as exempt from the UK Direct Airside Transit visa "
                 "(DATV). Airside only. A UK residence permit (BRP/ILR) holder "
                 "has leave to remain and can enter the UK, so a DATV is not "
                 "the applicable route. Note: the status of most OTHER foreign "
                 "holdings for the DATV is currently UNVERIFIED (the UK rules "
                 "were restructured and the relevant appendix is unpublished), "
                 "so no rows are written for them."),
        "source_url": DATV,
    },
]

doc = {
    "source": ("Transit-benefit layer (a `transit_benefits` table). T4: a "
               "foreign holding conferring transit (airside) rights at a hub, "
               "parallel to visa_benefits (which relaxes the entry ladder). "
               "Only verified benefits are stored, each with source_url; a "
               "missing row means 'no documented transit benefit from that "
               "holding at that hub'. Hubs are transit-regime ids "
               "('schengen' = airport-transit-visa regime, 'uk' = Direct "
               "Airside Transit regime). Verified 2026-09-04 against the EU "
               "Visa Code + C(2024) 4319 Handbook + Germany AA + France-Visas "
               "and gov.uk."),
    "checked": "2026-09-04",
    "note": ("hub: transit-regime id (the app resolves a transit airport to a "
             "regime before querying). transit_type shares the "
             "visa_rules.transit vocabulary: 'free' = the holding waives the "
             "transit visa (airside), 'conditional' = waived only under the "
             "stated conditions (the visa-based Schengen exemptions require "
             "travel to/from the issuing country or the immediate return leg). "
             "A missing (holding, hub) row = no documented benefit (base "
             "corridor transit rule applies), NOT a confirmed 'required'."),
    "benefits": BENEFITS,
}

out = DATA / "transit-benefits.json"
with open(out, "w") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"wrote {out} ({len(BENEFITS)} transit-benefit rows)")
