# App Merge Logic — to implement in Visa_Vole

Working spec for the Visa Vole app. The database is the **source of truth for
atomic facts**; the *derivation* (turning facts + the user's holdings into a
single answer) is **app logic**, not stored in the DB. This documents that
split and the rules the app must apply. **Revisit before launch.**

## What the DB gives you (read-only inputs)

- `visa_rules(passport, destination)` → one atomic row: `type`, `days`,
  `confidence`, `dispute`, `transit`, `transit_note`.
  - `type` ∈ `refused | visa-required | e-visa | visa-on-arrival | eta | visa-free | freedom-of-movement`.
   - `transit` ∈ `free | required | conditional | unknown` (base rule already
     applied: `free` wherever `type` is `visa-free`/`freedom-of-movement`).
- `visa_holdings` → the 13 known foreign holdings (`id`, `name`, `country`).
- `visa_benefits(holding, destination)` → for one holding, the *relaxed* `type`
  + `days` it confers at the destination (+ `source_page`/`source_url`).
- `corrections` → cited manual corrections (already folded into `visa_rules` at
  build time — the app does not re-apply them).
- `meta` → dataset descriptions (entry semantics, transit semantics, license).

The DB deliberately does **not** store a merged "effective" status: that depends
on which holdings *this* user has (unbounded combinations), so it must be
computed at query time.

## What the app must implement (NOT in the DB)

1. **Entry-status ladder** — an ordering used to pick the "better" of two
   statuses (worst → most privileged):

   ```
   refused < visa-required < e-visa < visa-on-arrival < eta < visa-free < freedom-of-movement
   ```

   The endpoints are firm (`refused` worst, `freedom-of-movement` best). The
   middle three (`e-visa` / `visa-on-arrival` / `eta`) are a *proposed*
   convention — confirm the ordering you prefer before launch.

2. **Baseline** — look up `visa_rules(passport, destination)`; that is the
   traveler's passport status.

3. **Benefits** — for each holding the user has selected, look up
   `visa_benefits(holding, destination)` and collect the applicable relaxed
   statuses for that destination.

4. **Best-of merge** — the effective status is the **highest** status on the
   ladder among `{baseline} ∪ {applicable benefits}`; use the `days` of the
   winning row.

5. **Invariants the merge must preserve:**
   - A benefit only **relaxes** the baseline (moves it up the ladder); it never
     makes the outcome worse than the passport alone.
   - A benefit never **waives a valid, accepted passport** or the destination's
     normal admissibility checks.
   - A benefit does **not lift a `refused` baseline** — if the passport is not
     accepted as a travel document, a foreign visa/residency does not change
     that.

6. **Custom permits** — let users add their own holdings in-app; treat them
   exactly like a `visa_holdings` row at query time (they need not exist in the
   DB).

7. **Transit** — a separate axis, read from the corridor (`transit` +
   `transit_note`); the base rule is already in the DB. (Future: a holding may
   itself confer transit rights — not modeled yet.)

8. **Provenance surfacing** — show `dispute` (sources disagree) and
   `confidence` (single-source / medium) so the app can flag uncertain cells,
   and link out via the benefit's `source_url`.

## Status / to revisit

- Confirm the ladder's middle ordering.
- Decide whether any holdings confer transit, and model it if so.
- Stay rules (rolling 90/180 windows, shared zones like CA-4) are **not** in the
  DB yet — see `docs/stay-rules-verified.md` (phase 1 reference; phase 2 is a
  `stay_rules` table).
