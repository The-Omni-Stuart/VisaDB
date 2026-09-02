# Stay Rules (Verified) — Phase 1 Reference

> **Status:** working reference (phase 1). The collector currently records only
> `days` = stay granted on a single entry; it does **not** capture rolling
> windows (90/180), shared zones (CA-4), or extension caps. The rules below are
> recorded here to (a) cross-check whether the collector needs to change, and
> (b) become a `stay_rules` table in the DB later (phase 2).
>
> Stay rules are **nationality-dependent**. Where a rule varies by passport the
> relevant nationalities are noted; most rules were verified for the primary
> target passports (GB, US, EU/EEA, RU). Re-verify in phase 2 before this
> becomes a DB table.

## How to read these
- **X per entry** — up to X days per single entry.
- **X/Y rolling** — up to X days in any rolling Y-day window.
- **Zone** — the allowance is shared across the listed countries (total time in
  the zone counts against one pool).

## Europe
### Schengen Area (27 states)
90 days in any 180-day period (rolling). Applies to visa-exempt nationals.

### United Kingdom (GB)
Up to 180 days per entry (Standard Visitor).

### Western Balkans — Bosnia & Herz. (BA), Montenegro (ME), North Macedonia (MK), Serbia (RS)
90 days in any 180-day period (rolling).

### Ukraine (UA)
90 days in any 180-day period (rolling).

### Moldova (MD)
90 days in any 180-day period (rolling).

### Georgia (GE)
365 days per entry (for ~95 nationalities). Travel insurance mandatory from
2026-01-01.

### Albania (AL)
- UK / EU: 90 days in any 180-day period.
- US: 365 days.

## Middle East & Caucasus
### Türkiye (TR)
90 days in any 180-day period (rolling).

## North America
### United States (US) — Visa Waiver Programme
90 days (B-1/B-2); extensions up to 180 days at CBP officer discretion.

### Mexico (MX)
Up to 180 days per entry (FMM).

## Central America
### CA-4 zone — Guatemala (GT), El Salvador (SV), Honduras (HN), Nicaragua (NI)
The allowance is **shared across all four countries** (total time in the zone
counts against one pool):
- GT: 90 days
- NI: 90 days
- SV: 180 days (UK/US/EU/RU nationals)
- HN: 90 days (US nationals); **visa required for GB nationals since Aug 2024**

### Costa Rica (CR)
Up to 180 days, at officer discretion (Group 1). Not part of CA-4.

### Panama (PA)
90 days per entry. Not part of CA-4.

### Colombia (CO)
90 days per entry, extendable by +90; cap 180 days in any 12 months.

### Peru (PE)
90 days per entry, extendable; cap 183 days in a rolling 365-day period.

## Asia
### Japan (JP)
90 days per entry; multiple entry; extendable by +90 (UK nationals).

### South Korea (KR)
90 days per entry. K-ETA exemption for GB/US/etc. nationals expires 2026-12-31.

## Time-limited notes
- **K-ETA (KR):** exemption ends 2026-12-31.
- **China (CN):** 30-day visa-free — GB & AR until 2026-12-31; RU until 2027-12-31.
- **Montenegro (ME):** visa for Russian nationals from 2026-11-01.
- **Georgia (GE):** travel insurance mandatory from 2026-01-01.
- **Belarus (BY) / Mongolia (MN):** GB exemption ends 2026.

## Sources & verification
Verified against official government sources and English Wikipedia
visa-policy pages (per-corridor citations are in the Visa_Vole research notes).
To be re-verified in phase 2, after the collector is extended to capture stay
rules and zones natively.
