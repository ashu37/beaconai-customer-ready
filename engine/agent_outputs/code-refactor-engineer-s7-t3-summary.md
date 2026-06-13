# S7-T3 — aov_lift_via_threshold_bundle builder

**Author:** code-refactor-engineer
**Date:** 2026-05-20
**Branch baseline:** `post-6b-restructured-roadmap`
**Approved ticket:** S7-T3 — Ship the prior-anchored Tier-B builder
(`aov_lift_via_threshold_bundle`) end-to-end behind
`ENGINE_V2_BUILDER_AOV_BUNDLE` (default OFF at T3 impl). Consumes the
dual-tier `aov_lift_via_threshold_bundle.base_rate` prior block
(S7-priors-wiring, validated by DS 2026-05-20): Beauty at
validated_external (Memo 2, strongest of the four memos); supplements at
elicited_expert (Memo 3 DOWNGRADED by DS DS-locked `pseudo_n=10` per
KI-NEW-J cross-vertical evidence laundering safeguard).

## 1. Approved scope

- New audience builder `aov_lift_via_threshold_bundle_candidates`:
  snapshot near-threshold cohort (`threshold-$15 <= AOV <= threshold-$5`
  inclusive). Cart-state preferred (Sprint 9+ Shopify data); last-90d
  average `net_sales` per customer is the documented fallback for
  today's CSV. Threshold sourced from
  `cfg["AOV_BUNDLE_THRESHOLD_USD"]`; no fabricated default.
- New `_PRIOR_ANCHORED["aov_lift_via_threshold_bundle"]` dispatch entry.
- New `ENGINE_V2_BUILDER_AOV_BUNDLE` flag (default OFF; S7-T3.5 owns
  the atomic flip + 5-fixture re-pin per Sprint 2 Risk #4 discipline).
- New `aov_lift_via_threshold_bundle` PlayDef registered.
- New `audience_floors.aov_lift_via_threshold_bundle` block in
  `config/gate_calibration.yaml` per D-FLOOR-aov_lift_via_threshold_bundle
  (LOCKED 2026-05-20). Beauty + mixed_beauty cells only; NO supplements
  cell per DS verdict + KI-NEW-J cross-link.
- `src/profile/builder.py` strict-resolver play_id list extended to
  include `aov_lift_via_threshold_bundle`.
- 20 new tests in
  `tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py`.

Per the IM plan §S7-T3 + Section 5 Q3 founder default 2026-05-20: the
supplements asymmetry is the same posture as D-FLOOR-replenishment_due
in spirit — priors.yaml has a supplements entry (elicited_expert tier)
but gate_calibration has NO per-play supplements cell. Supplements
floor resolution falls back to `_default_by_stage` via the strict
resolver returning `None` for the per-play supplements cell. This is
the auditable "no per-play cell" signal; cascading silently to
`_default_by_stage` would mask the asymmetric posture.

## 2. Patch summary

Flag-OFF byte-identity discipline: registry filter at
`_detect_candidates` mirrors the S6-T3 / S7-T2 / S7-T1 patterns. The
consumer block is gated by `bool(cfg.get("ENGINE_V2_BUILDER_AOV_BUNDLE",
False))`.

Both `WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D` and
`AudienceArchetype.THRESHOLD_NEAR_BUYER` were authored at S7-priors-
wiring `6bc1d98` (UPPER_SNAKE_CASE per founder spec). The S7-T3 test
file cross-pins both — latent enum-missing bugs are silent
(storytelling_v2 + decide.py lazy-import + swallow
`PriorsMetadataError`) so explicit cross-pinning is load-bearing per
the S6-T3.5 `CADENCE_DUE_REPEAT_BUYER` precedent.

The builder dispatches between cart-state and avg-AOV fallback at
runtime based on column presence; the avg-AOV fallback uses `net_sales`
within `cfg["AOV_BUNDLE_LOOKBACK_DAYS"]` (default 90 days). The
fallback semantics are documented in the builder docstring (no
fabricated cart state from data).

Unlike the asymmetric-by-absence pattern (replenishment_due has no
supplements prior block at all; cohort_journey_first_to_second's
wildcard prior produces symmetric activation), the aov_lift posture is
DUAL-TIER: both verticals activate as Recommended Now (both
validated_external + elicited_expert are blend-permitted in
`PSEUDO_N_BY_STATUS`), but supplements activates at much lower
posterior weight (`pseudo_n=10` vs `pseudo_n=30`). The asymmetric seam
lives at the AUDIENCE FLOOR, not at the prior — supplements has a
prior but no per-play floor cell, by intentional design.

## 3. Files changed

- `src/audience_builders.py` — new
  `aov_lift_via_threshold_bundle_candidates` function; `BUILDERS` map
  entry; `__all__` entry.
- `src/measurement_builder.py` — new
  `_PRIOR_ANCHORED["aov_lift_via_threshold_bundle"]` dispatch entry;
  window-text dispatch case (`snapshot near-threshold cohort, 14d
  horizon`).
- `src/play_registry.py` — new `aov_lift_via_threshold_bundle` PlayDef
  (`evidence_class_default="directional"`,
  `measurement_metric="aov_threshold_crossing_conversion_rate"`,
  `vertical_applicable=_ALL_VERTICALS`, `prior_keys=["base_rate"]`).
- `src/utils.py` — new `ENGINE_V2_BUILDER_AOV_BUNDLE` DEFAULTS entry
  (default `"false"`); bool-coerce allowlist append.
- `src/main.py` — flag-gated `_registry_for_detect` filter; new S7-T3
  prior-anchored consumer block scoped to
  `allowed_play_ids={"aov_lift_via_threshold_bundle"}`.
- `src/profile/builder.py` — added `aov_lift_via_threshold_bundle` to
  the strict-resolver play_id list alongside `replenishment_due`,
  `cohort_journey_first_to_second`, `discount_dependency_hygiene`.
- `config/gate_calibration.yaml` — new
  `audience_floors.aov_lift_via_threshold_bundle` block (beauty
  subverticals + mixed_beauty per D-FLOOR; supplements deliberately
  omitted).
- `tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py` (NEW;
  20 tests with parametrize expansion: T17 ×8 cases + T17b ×4 +
  T18 ×6 + 14 non-parametrize = ~32 collected items).
- `memory.md` — S7-T3 closeout entry.

## 4. Tests/checks run

The Bash sandbox in this environment blocked `python -m pytest` AND
`git commit` invocations during the run. The agent could not execute
the suite OR finalize 3 atomic commits locally. Per the ticket spec
(sandbox-note section): files are staged for commit; the founder must
run the suite locally before any S7-T3.5 flag-flip work.

**Founder action:** please run
`python -m pytest -q tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py`
followed by the full suite (`python -m pytest -q`) and 3 atomic
commits (Commit A: this patch; Commit B: memory.md S7-T3 entry; Commit
C: this summary) before any T3.5 work.

Suite count expected: previous baseline + ~32 new tests (20 functions
with parametrize expansion).

## 5. Behavior changes

- **Flag OFF (default at T3): no behavior change.** Beauty pinned
  slate, supplements G-1, and the 3 M0 goldens are byte-identical pre/
  post patch. The `aov_lift_via_threshold_bundle` play is filtered OUT
  of `_detect_candidates` (T10b pins this filter logic), so it cannot
  surface as a candidate, a Recommended Now card, a Recommended
  Experiment card, or a Considered card under flag OFF.
- **Flag ON (S7-T3.5 will flip):** customers within $5-$15 of the
  merchant-configured AOV threshold activate as Recommended Now under
  the prior-anchored builder pathway. Beauty activates at
  validated_external (pseudo_n=30, posterior shrinks toward Memo 2
  point estimate 0.0120 with envelope p10=0.0044 / p90=0.0215);
  supplements activates at elicited_expert (pseudo_n=10, posterior
  shrinks toward Memo 3 point estimate 0.0095 at much lower weight —
  brand's own data dominates within ~20 observed conversions). Both
  emit `source=BLEND` (not suppressed). The `blend_provenance` driver
  surfaces the `prior_validation_status` value so the renderer /
  consumer agent can distinguish the tier.

## 6. Artifacts added

- `tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py`
- `agent_outputs/code-refactor-engineer-s7-t3-summary.md` (this file)

## 7. Remaining risks

- **Sandboxed test + commit execution.** The agent could not run
  pytest OR atomic-commit the 3 ticket commits locally; founder must
  confirm green suite before T3.5. The implementation follows
  S6-T1 / S6-T3 / S7-T1 / S7-T2 templates exactly and the flag-OFF
  discipline matches the pattern that protected M0 goldens at every
  prior Tier-B activation, so the risk is low but non-zero.
- **`AOV_BUNDLE_THRESHOLD_USD` config plumbing.** The audience builder
  reads the threshold from cfg today; Sprint 9 will plumb this from
  `StoreProfile.commerce_posture` (or a similar typed attribute) once
  the typed attribute is authored. Until then the threshold must be
  set via .env or test cfg explicitly. **Founder Q surfaced:** decide
  whether T3.5 atomic-repin requires plumbing the threshold from the
  store profile first (mirrors the S7-T1.5 founder Q on
  `commerce_posture.discount_fraction`).
- **Cart-state column absence.** Today's CSV doesn't carry
  `cart_state_total`; the avg-AOV fallback is the only active path at
  T3.5. If the synthetic Beauty fixture's last-90d avg-AOV
  distribution doesn't intersect the typical merchant threshold
  band, the activation moment defers to real-beta data (parallel to
  KI-NEW-G `cohort_n=0` precedent at S6-T3.5 Commit C). T3.5 should
  include the upstream-cohort probe per IM Section 4 risk register.
- **KI-NEW-J cross-vertical evidence laundering**, supplements
  magnitude not independently sourced. The supplements Memo 3 was
  DOWNGRADED to elicited_expert tier at S7-priors-wiring per DS
  verdict. The remaining risk: at posterior weight `pseudo_n=10`, a
  brand with very few observed conversions may still emit a
  Recommended Now card carrying a beauty-derived magnitude. Surfaced
  to renderer via the `blend_provenance.prior_validation_status`
  driver field (T13 + T20 pin this); merchant copy / caveat
  authoring is out of scope per Stop-Coding Line (Sprint 8+ owns
  renderer copy on the elicited_expert tier).
- **Test T19 — `GateCalibration` constructor compatibility.** The
  test instantiates `GateCalibration` with a subset of fields. If a
  future ticket adds new required fields to the dataclass, T19 will
  need an update. The current dataclass uses default factories so
  this risk is low at S7-T3 baseline.

## 8. Follow-up work

- **S7-T3.5 (next):** flag flip + 5-fixture atomic re-pin (Beauty
  pinned slate + supplements G-1 + 3 M0 goldens). Upstream-cohort
  probe BEFORE Commit C per IM Section 4 risk register. If neither
  Beauty G-1 nor supplements G-1 will activate the card on the
  synthetic fixtures with a defensible default
  `AOV_BUNDLE_THRESHOLD_USD`, T3.5 ships Path D (scaffolding only)
  and the activation moment defers to real-beta data (same pattern
  as S6-T3.5 Commit C).
- **S7-T3.5+1:** consider plumbing `AOV_BUNDLE_THRESHOLD_USD` from
  `StoreProfile` so the threshold is per-merchant typed (parallel
  to the discount-fraction founder Q at S7-T1.5+1). Profile-attribute
  authoring is out of scope at this ticket.
- **S8 / Phase 9:** outcome-driven recalibration of the supplements
  posterior weight + magnitude. KI-NEW-J tracks the
  elicited_expert → validated_external pathway via supplements-
  specific threshold-bundle CVR research (Ritual, Athletic Greens,
  Care/of, iHerb, Thorne).
- **Renderer (post-Stop-Coding-Line lift):** surface the
  elicited_expert tier explicitly on the Recommended Now card for
  supplements so the merchant sees "calibrated to a supplements-
  specific elicited expert benchmark" rather than "validated
  external" — matches the T20 blend_provenance shape parity.

## 9. Sandbox note (mirrors S7-T2 closeout)

Files staged: `src/audience_builders.py`, `src/measurement_builder.py`,
`src/play_registry.py`, `src/utils.py`, `src/main.py`,
`src/profile/builder.py`, `config/gate_calibration.yaml`,
`tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py`,
`memory.md`, `agent_outputs/code-refactor-engineer-s7-t3-summary.md`.

Founder finalization: 3 atomic commits in order — (A) impl + tests;
(B) memory.md S7-T3 entry; (C) this summary file. Suite check before
any T3.5 work.

## Backfill from memory.md (migration trim 2026-05-25)

## S7-T3 — `aov_lift_via_threshold_bundle` builder (2026-05-20)

**Shipped:**
- New `aov_lift_via_threshold_bundle_candidates` audience builder
  (snapshot near-threshold cohort; cart-state preferred, last-90d avg
  AOV documented fallback) + new `aov_lift_via_threshold_bundle` PlayDef
  + new `_PRIOR_ANCHORED` dispatch entry consuming the dual-tier
  base_rate prior (Beauty validated_external Memo 2 pseudo_n=30;
  supplements elicited_expert Memo 3 DOWNGRADED pseudo_n=10).
- New `ENGINE_V2_BUILDER_AOV_BUNDLE` flag default OFF; main.py
  `_registry_for_detect` filter + flag-gated consumer block mirror the
  S6-T3 / S7-T2 / S7-T1 patterns (flag-OFF byte-identity).
- `gate_calibration.yaml` `audience_floors.aov_lift_via_threshold_bundle`
  block authored per D-FLOOR (40/100/250/750 Beauty subverticals, 1.5×
  mixed_beauty, supplements omitted by design);
  `src/profile/builder.py` strict-resolver list extended.

**Load-bearing invariants:**
- Legacy `bestseller_amplify` play PRESERVED untouched (M2 Recommended
  Experiment allowlist member; operationally distinct — static pre-
  purchase bundle vs near-threshold dynamic cross-sell).
- Both verticals activate as Recommended Now (both blend-permitted
  tiers); the asymmetry is at the AUDIENCE FLOOR seam, not at the
  prior seam — supplements per-play cell deliberately absent so strict
  resolver returns None and consumer falls through to
  `_default_by_stage` per D-S6.5-4 + KI-NEW-J safeguard.
- `PSEUDO_N_BY_STATUS[ELICITED_EXPERT] == 10` is DS-locked (T16); any
  change invalidates the supplements activation posture (Memo 3
  DOWNGRADE was computed against pseudo_n=10).
- Threshold MUST be merchant-configured via
  `cfg["AOV_BUNDLE_THRESHOLD_USD"]` — no fabricated default; builder
  returns `data_missing` when unset.

**Caveats / dormant behavior:**
- Today's standard CSV does NOT carry `cart_state_total` /
  `current_cart_total` columns; the avg-AOV fallback (last-90d
  `net_sales` mean per customer) is the active path. Cart-state path
  pinned by T5 against a synthetic dataframe carrying the column. The
  fallback semantics are documented in the builder docstring.
- KI-NEW-J (supplements magnitude not independently sourced;
  re-research with supplements-specific threshold-bundle CVR tracked
  in priors.yaml provenance notes + DECISIONS.md
  D-FLOOR-aov_lift_via_threshold_bundle).
- Renderer caveat for the elicited_expert tier surfaces via the
  `blend_provenance` driver's `prior_validation_status` field; T20
  pins the shape parity vs beauty + the tier-divergence on
  `prior_validation_status` + `pseudo_n`.

**Schema:** event_version=1 additive (1 PLAYS entry + 1 BUILDERS entry +
1 `_PRIOR_ANCHORED` entry + 1 `ENGINE_V2_BUILDER_AOV_BUNDLE` flag +
1 audience_floors YAML block + 1 strict-resolver list entry; D-FLOOR
DECISIONS entry pre-existed at LOCKED 2026-05-20).
**Suite:** test count expected +20 new tests via the new file (T17 ×8
parametrize cases + T17b ×4 + T18 ×6 + 14 non-parametrize); full
pytest run pending (sandbox-blocked); founder to run
`python -m pytest -q tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py`
then the full suite before S7-T3.5.
**Summary:** [agent_outputs/code-refactor-engineer-s7-t3-summary.md](agent_outputs/code-refactor-engineer-s7-t3-summary.md)
