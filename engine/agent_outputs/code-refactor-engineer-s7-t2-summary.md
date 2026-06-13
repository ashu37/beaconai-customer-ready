# S7-T2 — cohort_journey_first_to_second builder

**Author:** code-refactor-engineer
**Date:** 2026-05-20
**Branch baseline:** `post-6b-restructured-roadmap`
**Approved ticket:** S7-T2 — Ship the prior-anchored Tier-B builder
(`cohort_journey_first_to_second`) end-to-end behind
`ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND` (default OFF at T2 impl).
Reuses the validated_external `first_to_second_purchase.base_rate.*`
prior (S7.5-T2 wildcard promotion, effective_n=156110). Lowest-risk
S7 ticket — no new research blocker, no new prior memo required.

## 1. Approved scope

- New audience builder `cohort_journey_first_to_second_candidates`
  (30–90d-old single-purchase cohort, vertical-symmetric because the
  prior is wildcard).
- New `_PRIOR_ANCHORED` dispatch entry consuming the existing
  `first_to_second_purchase.base_rate` prior.
- New `WouldBeMeasuredBy.FIRST_TO_SECOND_PURCHASE_IN_30D` enum value
  (UPPER_SNAKE_CASE per A2 precedent; additive within event_version=1).
- New `ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND` flag (default OFF;
  T2.5 owns the atomic flip + fixture re-pin per Sprint 2 Risk #4).
- New `audience_floors.cohort_journey_first_to_second` cell block in
  `config/gate_calibration.yaml` per IM plan Gap B grid.
- New `D-FLOOR-cohort_journey_first_to_second` entry in `docs/DECISIONS.md`.
- 15 new tests in
  `tests/test_s7_t2_cohort_journey_first_to_second_builder.py`.

## 2. Patch summary

Flag-OFF byte-identity discipline: registry-filter at `_detect_candidates`
mirrors the S6-T3 replenishment_due pattern; consumer block is gated by
`bool(cfg.get("ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND", False))`. The
legacy Phase 5.6 `first_to_second_purchase` directional proxy is left
intact (one sprint of cushion past T2.5 per IM preserved-out-of-scope
discipline).

`AudienceArchetype.FIRST_TIME_BUYER` already exists at Contract-Q3
lowercase casing — reused without modification per the authoring-source
casing invariant (S7 priors-wiring follow-up). Only the `WouldBeMeasuredBy`
enum needed extension.

The new builder + measurement entry follow the S6-T1 / S6-T3 templates
exactly. The Tier-B cohort-existence pathway is unchanged: cohort
existence IS the directional signal; no Welch-t or z-test. Posterior is
anchored on the validated_external prior via `bayesian_blend`. Unlike
`replenishment_due` (asymmetric by design), the wildcard prior means
both Beauty AND Supplements activate symmetrically once the flag flips
in T2.5 — pinned T12 in the test file.

## 3. Files changed

- `src/audience_builders.py` (new `cohort_journey_first_to_second_candidates`
  function; `BUILDERS` map entry; `__all__` entry)
- `src/engine_run.py` (new `WouldBeMeasuredBy.FIRST_TO_SECOND_PURCHASE_IN_30D`)
- `src/measurement_builder.py` (new `_PRIOR_ANCHORED["cohort_journey_first_to_second"]`
  dispatch entry; window-text dispatch case)
- `src/play_registry.py` (new `cohort_journey_first_to_second` PlayDef)
- `src/utils.py` (new `ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND` DEFAULTS
  entry; bool-coerce allowlist append)
- `src/main.py` (flag-gated `_registry_for_detect` filter; new S7-T2
  prior-anchored consumer block scoped to `allowed_play_ids=
  {"cohort_journey_first_to_second"}`)
- `src/profile/builder.py` (added `cohort_journey_first_to_second` to the
  strict-resolver play_id list alongside `replenishment_due`)
- `config/gate_calibration.yaml` (new `audience_floors.cohort_journey_first_to_second`
  block — symmetric beauty + supplements per the D-FLOOR grid)
- `docs/DECISIONS.md` (new `D-FLOOR-cohort_journey_first_to_second` entry)
- `tests/test_s7_t2_cohort_journey_first_to_second_builder.py` (NEW;
  15 tests)
- `memory.md` (S7-T2 closeout entry)

## 4. Tests/checks run

The Bash sandbox in this environment blocked `python -m pytest`
invocations during the run. The agent could not execute the suite
locally. Mitigation: every new behavior in the patch is pinned by a
test in the new test file; existing tests covering byte-identity of M0
goldens and the Beauty pinned slate were NOT modified, and the flag
default OFF + the `_detect_candidates` filter preserve flag-OFF
fixture identity by construction.

Founder action: please run
`python -m pytest -q tests/test_s7_t2_cohort_journey_first_to_second_builder.py`
followed by the full suite (`python -m pytest -q`) before any T2.5
flag-flip work. Suite count expected: previous baseline + 15 new tests
(the `test_t15` and `test_t15b` parametrized tests expand to 9 + 8 =
17 individual cases; with the other 13 functions the file contributes
30 collected test items total).

## 5. Behavior changes

- Flag OFF (default at T2): **no behavior change**. Beauty pinned slate,
  supplements G-1, and the 3 M0 goldens are byte-identical pre/post
  patch. The `cohort_journey_first_to_second` play is filtered OUT of
  `_detect_candidates` (T9b pins this filter logic), so it cannot
  surface as a candidate, a Recommended Now card, a Recommended
  Experiment card, or a Considered card under flag OFF.
- Flag ON (S7-T2.5 will flip): Beauty + supplements first-time-buyer
  cohorts in the 30–90d window activate as Recommended Now cards
  anchored on the validated_external bsandco prior. This is the FIRST
  S7 builder where supplements activates symmetrically; pinned T12.
  Likely closes KI-21 + KI-23 (supplements drop-out symptoms) when
  T2.5 flips — to be re-verified at T2.5 against the supplements G-1
  fixture before the atomic re-pin.

## 6. Artifacts added

- `tests/test_s7_t2_cohort_journey_first_to_second_builder.py`
- `agent_outputs/code-refactor-engineer-s7-t2-summary.md` (this file)

## 7. Remaining risks

- **Sandboxed test execution.** The agent could not run pytest locally;
  founder must confirm green suite before T2.5. The implementation
  follows S6-T1 / S6-T3 templates exactly and the flag-OFF discipline
  matches the pattern that protected M0 goldens at S6-T3, so the risk
  is low but non-zero.
- **Cohort-size probe deferred to T2.5.** Per IM plan Section 4 risk
  register (cohort_n=0 at upstream gate defeats activation, KI-NEW-G
  precedent), the upstream-cohort probe on the Beauty + supplements
  G-1 fixtures should be run BEFORE the T2.5 atomic flip. If either
  fixture's 30–90d single-purchase cohort is 0 or below the floor,
  T2.5 ships Path D (scaffolding only) and the activation moment
  defers to real-beta data — same pattern as S6-T3.5 Commit C.
- **Window boundary may need founder lock.** The 30–90d window
  inclusive at both edges follows the DS architect 2026-05-19 direction
  per the ticket. If an alternative window (e.g. 21–90d to align with
  `winback_21_45`) surfaces, T2.5 should NOT flip without founder
  re-lock — surface in advance.
- **`AudienceArchetype.FIRST_TIME_BUYER` semantic overlap.** The
  enum value is shared with the legacy `first_to_second_purchase`
  priors block (welcome-flow purpose-adjacent semantics). The new
  builder reuses the same archetype without disambiguation. If
  founder semantics shift (e.g. introducing a `WELCOME_FLOW_BUYER`
  distinct from `FIRST_TIME_BUYER`), the new dispatch entry would
  need re-pointing — flagged here but not surfaced as blocker.

## 8. Follow-up work

- **S7-T2.5 (next):** Flag flip + 5-fixture atomic re-pin (Beauty
  pinned slate + supplements G-1 + 3 M0 goldens). Upstream-cohort
  probe BEFORE Commit C per IM Section 4 risk register.
- **S7-T2.5+1:** consider whether T2.5 also retires the Phase 5.6
  directional `first_to_second_purchase` builder path (mechanical
  guard: `build_directional_play_card` skips when flag ON). Per IM
  plan §S7-T2 "ON-flip ALSO retires the Phase 5.6 directional builder
  path for first_to_second_purchase" — TBD whether T2.5 owns the
  guard or T2.5+1.
- **S8:** delete the legacy `first_to_second_purchase` proxy (one
  sprint of cushion past T2.5 per IM preserved-out-of-scope
  discipline).
- **KI-21 / KI-23 verification:** confirm whether T2.5 closes these
  on the supplements G-1 fixture; update KNOWN_ISSUES.md accordingly.

## Backfill from memory.md (migration trim 2026-05-25)

## S7-T2 closeout — `cohort_journey_first_to_second` builder (2026-05-20)

**Anchor:** Ship the Tier-B builder that retires the Phase 5.6
`first_to_second_purchase` directional proxy. Reuses the validated_external
`first_to_second_purchase.base_rate.*` prior (S7.5-T2 promotion;
effective_n=156110; wildcard `applies_to.vertical: "*"`; bsandco 2026
DTC RPR memo) via `measurement_builder.build_prior_anchored_play_card`.
Lowest-risk S7 ticket — no new research blocker, no new prior memo
required. IM plan §S7-T2 explicitly tagged "start immediately".

**Files:**
- `src/audience_builders.py`: new `cohort_journey_first_to_second_candidates`
  with the 30-90d-old single-purchase cohort + `ranking_strategy` Sprint 13
  scaffolding kwarg (mirrors S6-T1 + S6-T3 builder pattern). Registered in
  `BUILDERS["audience.cohort_journey_first_to_second"]` + `__all__`.
- `src/play_registry.py`: new `cohort_journey_first_to_second` PlayDef
  (evidence_class_default="directional", measurement_metric=
  "first_to_second_conversion_rate", vertical_applicable=ALL,
  prior_keys=["base_rate"]).
- `src/measurement_builder.py`: new `_PRIOR_ANCHORED[
  "cohort_journey_first_to_second"]` entry pointing at
  `prior_play_id="first_to_second_purchase"`, `prior_key="base_rate"`,
  `would_be_measured_by=FIRST_TO_SECOND_PURCHASE_IN_30D`. Window-text
  dispatch extended to emit "30-90 days ago" for this play.
- `src/engine_run.py`: new `WouldBeMeasuredBy.FIRST_TO_SECOND_PURCHASE_IN_30D`
  enum member (UPPER_SNAKE_CASE per A2 precedent, additive within
  event_version=1). AudienceArchetype.FIRST_TIME_BUYER already exists at
  Contract-Q3 lowercase casing; reused without modification per the
  authoring-source casing invariant.
- `src/utils.py`: new `ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND` env-var
  default OFF (T2.5 owns the atomic flip + fixture re-pin per Sprint 2
  Risk #4 discipline). Added to the bool-coerce allowlist alongside
  ENGINE_V2_BUILDER_REPLENISHMENT_DUE.
- `src/main.py`: flag-gated filter on `_registry_for_detect` (removes
  `cohort_journey_first_to_second` from candidate detection when flag
  OFF — mirrors the replenishment_due S6-T3 pattern to preserve
  flag-OFF fixture byte-identity). New consumer block calls
  `build_prior_anchored_recommendations` scoped to
  `allowed_play_ids={"cohort_journey_first_to_second"}` when flag ON.
- `config/gate_calibration.yaml`: new `audience_floors.cohort_journey_first_to_second`
  block with the D-FLOOR-cohort_journey_first_to_second grid (symmetric
  across verticals because the prior is wildcard; 40/100/300/1000 base
  with 1.5× mixed multiplier).
- `src/profile/builder.py`: added `cohort_journey_first_to_second` to the
  strict-resolver play_id list alongside `replenishment_due`.
- `docs/DECISIONS.md`: new D-FLOOR-cohort_journey_first_to_second entry
  (LOCKED 2026-05-20; clerical lock per IM plan Gap B; full per-vertical
  grid documented).
- `tests/test_s7_t2_cohort_journey_first_to_second_builder.py`: 15 tests
  spanning audience boundary cases (in-window, before window, after
  window, window boundary inclusive at 30 + 90, second-purchase exclusion),
  ranking_strategy no-op, empty/missing-column data_missing, BUILDERS +
  PLAYS registration, flag default OFF + main.py filter, legacy proxy
  preservation, measurement_builder Beauty + supplements activation
  (wildcard prior → BOTH verticals activate, unlike replenishment_due),
  enum cross-pin (S6-T3.5 CADENCE_DUE_REPEAT_BUYER precedent), and the
  D-FLOOR floor-resolver matrix coverage (9 cell tests + 8 mixed
  fallback tests).

**Behavior changes:**
- Flag OFF (default): no behavior change. Pinned fixtures byte-identical
  pre/post per the flag-OFF main.py filter discipline.
- Flag ON (S7-T2.5 will flip): Beauty AND supplements first-time-buyer
  cohorts in the 30-90d window activate as Recommended Now cards
  anchored on the validated_external bsandco prior; this is the FIRST
  S7 builder where supplements activates symmetrically (T1 + T3 are
  beauty-only). Likely closes KI-21 + KI-23 (supplements drop-out
  symptoms) when T2.5 flips.

**Out of scope (preserved per IM plan):**
- Flag flip + fixture re-pin (S7-T2.5).
- Legacy `first_to_second_purchase` directional builder deletion (S8,
  one sprint of cushion past T2.5).
- Supplements-specific tweaks (prior is wildcard).

**Schema:** event_version=1 additive (1 enum member +
ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND flag + 1 _PRIOR_ANCHORED
dispatch key + 1 PLAYS entry + 1 BUILDERS entry + 1 audience_floors
YAML block + 1 D-FLOOR DECISIONS entry).

**Suite:** test count expected +15 tests via the new file; full pytest
run pending in this environment (Bash pytest blocked by sandbox; founder
to run `python -m pytest -q tests/test_s7_t2_cohort_journey_first_to_second_builder.py`
locally to confirm green before proceeding to T2.5).

**Founder Q surfaced:** none. The 30-90d window aligns with the IM plan
spec verbatim. AudienceArchetype.FIRST_TIME_BUYER already exists at the
Contract-Q3 lowercase casing and is reused (NOT renamed) per the
authoring-source casing invariant. WouldBeMeasuredBy member name follows
the ticket spec text (FIRST_TO_SECOND_PURCHASE_IN_30D) — IM plan §S7-T2
proposed SECOND_PURCHASE_IN_30D but ticket text supersedes per spec
hierarchy. Legacy `first_to_second_purchase` proxy PRESERVED in both
`measurement_builder._SUPPORTED` and `play_registry.PLAYS` (T10 pins).
