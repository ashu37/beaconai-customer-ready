# S7.6-T1 — B-1 winback observed-effect wiring (flag OFF)

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `e8864d8`

---

## 1. Ticket scope

Wire the first observed-effect consumer of the T0 helper: `compute_winback_observed_effect` in `src/measurement_builder.py`. For each of {L28, L56, L90} anchors, builds the historical dormant cohort under the SAME M3 rule (last-order in [wb_lo, wb_hi], >=2 priors, no orders in pre-28d window) at `maxd-W` and at `maxd-2W`, then routes recent-vs-prior recovery counts through the T0 helper to produce a two-proportion observed-effect plus multi-window sign-agreement.

`build_prior_anchored_play_card` + `build_prior_anchored_recommendations` gain `(orders_df, observed_effect_enabled)` kwargs. When `ENGINE_V2_OBSERVED_EFFECT_WINBACK` is ON, `main.py` threads `g` as `orders_df` into the winback-scoped prior-anchored call; the (L28 k, n) flow into the existing `bayesian_blend` seam in `src/sizing.py`. EB blend math untouched.

Flag default OFF. T1.5 flips atomically post-probe.

## 2. Files changed

- `src/main.py` — flag-gated kwarg plumbing at the winback prior-anchored block (+9 lines).
- `src/measurement_builder.py` — `compute_winback_observed_effect` helper + kwarg signature extension (+263 lines).
- `src/utils.py` — `ENGINE_V2_OBSERVED_EFFECT_WINBACK` default `"false"` + bool-coerce allowlist (+17 lines).
- `tests/test_s7_6_t1_winback_observed_effect.py` (new, 269 lines).

## 3. Behavior change

None at flag-OFF default. `orders_df` ignored downstream, cold-start `observed_k=observed_n=0` preserved. M0, Beauty, Supplements byte-identical.

Under flag-ON: winback card carries observed-effect numerics flowing into the bayesian_blend seam at the L28 anchor.

## 4. Tests added / modified

6 new tests in `tests/test_s7_6_t1_winback_observed_effect.py`. Suite 1669p/14s/3xf/1xp/0f (was 1663 at T0; +6 = clean).

## 5. Risks + mitigations

- **EB blend math untouched** — T0 helpers feed observed_k/n into the existing seam; no new sizing arithmetic added in this ticket.
- **Flag default OFF** — atomic flip at T1.5 is preceded by tripwire probe (founder threshold observed_n>=30).

## 6. Follow-ups / known-issues opened

- T1.5 atomic flag flip + probe (landed at `28e4859`).

## 7. Commit ref

`e8864d8`

## Backfill from memory.md (migration trim 2026-05-25)

## S7.6-T1.5 — Winback observed-effect activation (2026-05-21)

**Shipped:**
- T0 helper `src/measurement_observed.py` extracts per-store
  `(observed_k, observed_n)` from candidate cohorts; T1 plumbs the
  pair through measurement_builder → main.py → `bayesian_blend` for
  `winback_dormant_cohort`; T1.5 atomic flip activated the observed-
  effect blend on Beauty.
- Tripwire result: Beauty `observed_n=334`; posterior shifted from
  prior `0.08` → `0.16` (store-dominant blend at this `n`); 3/3 sign
  agreement across L28 / L56 / L90 windows.

**Load-bearing invariants:**
- Cold-start (`observed_n=0`) remains prior-dominant by construction
  in `bayesian_blend`; do NOT alter the `n=0` short-circuit.
- `src/measurement_observed.py` is the single seam for observed-effect
  extraction; future builders consume the same helper.

**Caveats / dormant behavior:** none for winback. Commit refs
`713493b` (T0), `e8864d8` (T1), `28e4859` (T1.5).

**Schema:** unchanged.
**Suite:** Beauty + Supplements + M0 byte-identical; suite green.
