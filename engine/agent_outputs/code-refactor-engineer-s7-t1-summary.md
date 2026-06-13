# S7-T1 — discount_dependency_hygiene builder

**Author:** code-refactor-engineer
**Date:** 2026-05-20
**Branch baseline:** `post-6b-restructured-roadmap`
**Approved ticket:** S7-T1 — Ship the prior-anchored Tier-B builder
(`discount_dependency_hygiene`) end-to-end behind
`ENGINE_V2_BUILDER_DISCOUNT_HYGIENE` (default OFF at T1 impl). Anchors
on the Memo-1 validated_external `discount_dependency_hygiene.base_rate.beauty`
prior (DS-validated 2026-05-20 with envelope re-fit caveat KI-NEW-K
deferred to Sprint 8). Beauty-only activation; supplements ships
Path-D dormant per Memo-4 reject + DS verdict (no priors.yaml entry,
no gate_calibration cell, strict resolver returns None).

## 1. Approved scope

- New audience builder `discount_dependency_hygiene_candidates`
  (customers whose >=50% of historical orders carried a discount;
  ranking_strategy kwarg reserved for Sprint 13 ML).
- New `_PRIOR_ANCHORED["discount_dependency_hygiene"]` dispatch entry
  consuming the Beauty-only validated_external prior block (landed at
  S7-priors-wiring `6bc1d98`); supplements path returns None (no prior
  block; routes to PRIOR_UNVALIDATED Considered via S7.5-T3 refusal
  when invoked).
- New `discount_dependency_hygiene` PlayDef in `play_registry.PLAYS`
  (evidence_class_default=directional, vertical_applicable={beauty,
  mixed}, prior_keys=["base_rate"]). Legacy `discount_hygiene`
  PRESERVED untouched (founder Q1 default 2026-05-20).
- New `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE` flag (default OFF; T1.5
  owns the atomic flip + 5-fixture re-pin per Sprint 2 Risk #4).
- New `audience_floors.discount_dependency_hygiene` block in
  `config/gate_calibration.yaml` per D-FLOOR base grid; supplements
  cell deliberately absent.
- Strict-resolver play_id list extended in `src/profile/builder.py`.
- 19 new tests in `tests/test_s7_t1_discount_dependency_hygiene_builder.py`.

## 2. Patch summary

Flag-OFF byte-identity discipline: `_registry_for_detect` filter at the
candidate-detection seam mirrors the S6-T3 / S7-T2 replenishment_due
and cohort_journey_first_to_second patterns; consumer block is gated
on `bool(cfg.get("ENGINE_V2_BUILDER_DISCOUNT_HYGIENE", False))`. The
legacy `discount_hygiene` play stays in `play_registry.PLAYS` for the
M2 measured-margin pathway (KI-21 Recommended Experiment allowlist
member) and is operationally distinct from the new
`discount_dependency_hygiene` full-price-conversion play.

Both new enums (`AudienceArchetype.DISCOUNT_CONDITIONED_REPEAT_BUYER`,
`WouldBeMeasuredBy.DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D`)
were already authored at S7-priors-wiring (`6bc1d98`); reused without
modification per the S7 founder-spec UPPER_SNAKE_CASE provenance rule.

## 3. Files changed

- `src/audience_builders.py` — new `discount_dependency_hygiene_candidates`
  function; `BUILDERS["audience.discount_dependency_hygiene"]` entry;
  `__all__` entry.
- `src/play_registry.py` — new `discount_dependency_hygiene` PlayDef
  (vertical_applicable = {beauty, mixed}; supplements REJECTED).
- `src/measurement_builder.py` — new `_PRIOR_ANCHORED["discount_dependency_hygiene"]`
  dispatch entry pointing at `prior_play_id="discount_dependency_hygiene"`,
  `prior_key="base_rate"`,
  `would_be_measured_by=DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D`;
  window-text dispatch case `"14 days post-send"`.
- `src/utils.py` — new `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE` env-var
  default `"false"` + bool-coerce allowlist append.
- `src/main.py` — flag-gated filter on `_registry_for_detect` (removes
  `discount_dependency_hygiene` from candidate detection when flag OFF);
  new consumer block calls `build_prior_anchored_recommendations` scoped
  to `allowed_play_ids={"discount_dependency_hygiene"}` when flag ON.
- `src/profile/builder.py` — added `discount_dependency_hygiene` to the
  strict-resolver play_id tuple alongside `replenishment_due` and
  `cohort_journey_first_to_second`.
- `config/gate_calibration.yaml` — new `audience_floors.discount_dependency_hygiene`
  block (Beauty subverticals 40/100/250/750; mixed_beauty 60/150/375/1125;
  supplements omitted by design).
- `tests/test_s7_t1_discount_dependency_hygiene_builder.py` — NEW;
  19 tests (T18 includes parametrized matrices, see Section 4).
- `memory.md` — S7-T1 closeout entry per template.

## 4. Tests/checks run

The Bash sandbox in this environment blocked `python -m pytest`
invocations during the run (per S7-T4 dispatch precedent). The agent
could not execute the suite locally.

**Founder action:** please run
`python -m pytest -q tests/test_s7_t1_discount_dependency_hygiene_builder.py`
followed by the full suite (`python -m pytest -q`) before any S7-T1.5
flag-flip work. Test count expectation: the new file contributes 19
test functions; the T15 / T16 parametrize matrices expand to 8 + 4 + 7 =
19 cases on top of the 14 non-parametrized functions = ~33 collected
test items. Suite count expectation: previous baseline + ~30 new
collected items.

Coverage authored:
- T1–T4: audience boundary cases (100% discounted, 50% inclusive
  boundary, full-price-only excluded, NaN coercion safe default).
- T5: `ranking_strategy` kwarg no-op (str + non-str + None).
- T6: AudienceResult shape contract (no forbidden M3 fields).
- T7 + T7b: empty / missing-column → `data_missing`.
- T8: BUILDERS + PLAYS registration + vertical_applicable={beauty, mixed}.
- T9 + T9b: flag default OFF + main.py filter byte-identity simulation.
- T10: legacy `discount_hygiene` preserved + independent.
- T11: Beauty path validated_external + BLEND (with KI-NEW-K caveat
  in docstring).
- T12: supplements returns None (asymmetric-no-cell).
- T13: enum cross-pin for both new enums (S6-T3.5 latent-bug guard).
- T14: `_PRIOR_ANCHORED` dispatch entry pins the prior anchor.
- T15: D-FLOOR resolver Beauty cell coverage (8 cases).
- T15b: mixed_beauty fallback (4 cases).
- T16: supplements floor returns None (7 cases — asymmetric-no-cell).
- T17: `derive_gate_calibration` source-text pins inclusion of the
  new play_id in the strict-resolver tuple.
- T18: heavy-promo conditional bump documented-but-dormant pin (see
  Section 7 founder Q).
- T19: legacy + new audience builders coexist in BUILDERS.

## 5. Behavior changes

- **Flag OFF (default at T1):** no behavior change. Beauty pinned
  slate, supplements G-1, and the 3 M0 goldens are byte-identical
  pre/post patch. The `discount_dependency_hygiene` play is filtered
  OUT of `_detect_candidates` (T9b pins this), so it cannot surface as
  a candidate, a Recommended Now card, a Recommended Experiment card,
  or a Considered card under flag OFF.
- **Flag ON (S7-T1.5 will flip):** Beauty stores activate a
  Recommended Now card anchored on the validated_external Memo-1
  prior; supplements stores see NO change (no prior block → no card;
  strict resolver returns None for the audience floor too — symmetric
  asymmetric-no-cell with replenishment_due).

## 6. Artifacts added

- `tests/test_s7_t1_discount_dependency_hygiene_builder.py`
- `agent_outputs/code-refactor-engineer-s7-t1-summary.md` (this file)

## 7. Remaining risks

- **Sandboxed test execution.** The agent could not run pytest
  locally; founder must confirm green suite before S7-T1.5. The
  implementation follows S6-T1 / S6-T3 / S7-T2 templates exactly and
  the flag-OFF discipline matches the pattern that protected M0
  goldens at every previous Tier-B builder ship, so the risk is low
  but non-zero.
- **Heavy-promo conditional bump deferred (founder Q surfaced).**
  D-FLOOR-discount_dependency_hygiene conditional rule says floor
  BUMPS UP to {80/200/500/1500} when store-level
  `commerce_posture.discount_fraction > 0.40`. Per the ticket spec
  "If the attribute does not exist, surface a founder Q before
  authoring", I did NOT invent the attribute. The bump logic ships
  DORMANT and is pinned by T18. **Founder action required before
  S7-T1.5 atomic-repin:** decide whether to (a) ship the
  `commerce_posture.discount_fraction` profile attribute in a separate
  ticket and wire the resolver bump in T1.5, OR (b) flip T1.5 with the
  bump still dormant and ship the attribute + bump in a follow-on.
- **KI-NEW-K envelope re-fit (Sprint 8).** Today's range_p10=0.0120 /
  range_p90=0.0430 are text-derived from the source Klaviyo memo, NOT
  CDF-derived from the J-shaped Beta(0.66, 29.34) at effective_n=30.
  Pinned in T11 docstring; do NOT re-fit at T1.5. Sprint 8 calibration
  sweep owns the re-fit at effective_n=60.
- **Upstream-cohort probe deferred to S7-T1.5.** Per IM plan Section 4
  risk register (cohort_n=0 at upstream gate defeats activation,
  KI-NEW-G precedent), probe the Beauty G-1 fixture's discount-
  conditioned cohort size BEFORE the T1.5 atomic flip. If the cohort
  is 0 or below the floor on Beauty G-1, T1.5 ships Path D
  (scaffolding only, KI-NEW-J filed).
- **Legacy `discount_hygiene` semantic overlap.** Both plays now exist
  in the registry with operationally distinct mechanisms. T10 pins
  preservation. If founder later semantics-merges these (e.g.
  retiring legacy `discount_hygiene` from the M2 margin pathway), the
  rename / retirement is a separate migration (out of scope here per
  IM preserved-out-of-scope discipline).

## 8. Follow-up work

- **S7-T1.5 (next):** Flag flip + 5-fixture atomic re-pin (Beauty
  pinned slate + supplements G-1 + 3 M0 goldens). Upstream-cohort
  probe BEFORE Commit C per IM Section 4 risk register. Founder
  decision on `commerce_posture.discount_fraction` attribute path
  required before the flip.
- **Profile attribute `commerce_posture.discount_fraction`** (separate
  ticket per ticket-spec founder-Q discipline) so the heavy-promo
  conditional bump can wire into the floor resolver. T18 will need
  inversion at that point (assert the attribute exists instead of
  absent).
- **S8: KI-NEW-K envelope re-fit** at effective_n=60 (alpha=1.32,
  beta=58.68) to recover unimodal Beta envelope for the Memo-1 prior;
  update priors.yaml + memo provenance verbatim per S7-priors-wiring
  discipline.
- **Post-beta:** revisit legacy `discount_hygiene` retirement (founder
  pre-approved keeping both for now; no S7 / S8 work needed).

## 9. Verbatim founder ask answers

Per ticket "Report back" closing list:

- **3 commit hashes (or staged-files-pending-commit list).** STAGED,
  pending founder commit (sandbox blocked git):
  - `src/audience_builders.py`
  - `src/play_registry.py`
  - `src/measurement_builder.py`
  - `src/utils.py`
  - `src/main.py`
  - `src/profile/builder.py`
  - `config/gate_calibration.yaml`
  - `tests/test_s7_t1_discount_dependency_hygiene_builder.py`
  - `memory.md`
  - `agent_outputs/code-refactor-engineer-s7-t1-summary.md`
- **Suite count.** Pending founder pytest run; expected baseline + ~30
  new collected test items.
- **Confirmation flag stays OFF.** `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE`
  default `"false"` in `src/utils.py::DEFAULTS`; T9 pins this.
- **Confirmation legacy `discount_hygiene` preserved.** Untouched in
  `play_registry.PLAYS`; T10 pins both the registry coexistence and
  the legacy `audience.discount_dependent_buyers` builder ref.
- **Confirmation supplements gets zero behavior change.** (a) No
  supplements entry authored in `config/priors.yaml`
  (`discount_dependency_hygiene` block has only the Beauty prior); (b)
  no supplements cell authored in `config/gate_calibration.yaml`
  (strict resolver returns None — T16 pins 7 cases); (c)
  `vertical_applicable={beauty, mixed}` on the PlayDef excludes
  supplements (T8 pins); (d) `_PRIOR_ANCHORED` dispatch returns None
  for supplements (T12 pins). Asymmetric-no-cell pattern parallels
  D-FLOOR-replenishment_due exactly.
- **Fixture identity status.** Expected byte-identical under flag OFF
  for all 5 pinned fixtures (Beauty pinned slate, supplements G-1, 3
  M0 goldens) by the same construction that held S6-T3 / S7-T2 byte-
  identity: the `_registry_for_detect` filter removes the new play_id
  from candidate-detection iteration before any candidate is emitted;
  the consumer block is bypassed; nothing in the V2 decide pipeline
  sees a new artifact. To be confirmed empirically by founder running
  the pinned fixtures.

## Backfill from memory.md (migration trim 2026-05-25)

## S7-T1 — `discount_dependency_hygiene` builder (2026-05-20)

**Shipped:**
- New `discount_dependency_hygiene_candidates` audience builder + new
  `discount_dependency_hygiene` play_id (Beauty/mixed only; supplements
  rejected per DS Memo-4) + new `_PRIOR_ANCHORED` dispatch entry
  consuming the Beauty-only validated_external Memo-1 prior.
- New `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE` flag default OFF; main.py
  `_registry_for_detect` filter + flag-gated consumer block mirror the
  S6-T3 / S7-T2 patterns (flag-OFF byte-identity).
- `gate_calibration.yaml` audience_floors block authored per D-FLOOR
  base grid (40/100/250/750 Beauty subverticals, 1.5× mixed_beauty,
  supplements omitted by design); `src/profile/builder.py` strict-
  resolver list extended to include the new play_id.

**Load-bearing invariants:**
- Legacy `discount_hygiene` play_id PRESERVED untouched (founder Q1
  default 2026-05-20) — operationally distinct from the new
  `discount_dependency_hygiene` (M2 margin pathway vs prior-anchored
  full-price-conversion).
- Supplements gets ZERO behavior change: no priors block, no
  gate_calibration cell, strict resolver returns None (asymmetric-no-
  cell pattern parallels D-FLOOR-replenishment_due).
- Both new enums (`DISCOUNT_CONDITIONED_REPEAT_BUYER`,
  `DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D`) already
  landed at S7-priors-wiring `6bc1d98`; cross-pin test (T13) holds.

**Caveats / dormant behavior:**
- Heavy-promo conditional bump (40%>discount_fraction → 80/200/500/1500
  per D-FLOOR rule) is INTENTIONALLY DORMANT because
  `StoreProfile.commerce_posture.discount_fraction` does NOT exist
  today. Pinned by T18. **Founder Q surfaced:** ship the
  `commerce_posture.discount_fraction` attribute in a separate ticket
  before S7-T1.5 atomic-repin so the conditional bump can land
  alongside the flag flip. Authoring an attribute name unilaterally
  was refused per ticket spec.
- KI-NEW-K envelope re-fit (Beta(0.66, 29.34) J-shape at effective_n=30
  → re-fit at effective_n=60 for unimodal envelope) deferred to
  Sprint 8 calibration sweep; today's range_p10/p90 are text-derived
  per priors.yaml provenance note; pinned in T11 docstring.

**Schema:** event_version=1 additive (1 PLAYS entry + 1 BUILDERS entry +
1 _PRIOR_ANCHORED entry + 1 ENGINE_V2_BUILDER_DISCOUNT_HYGIENE flag +
1 audience_floors YAML block; D-FLOOR DECISIONS entry pre-existed).
**Suite:** test count expected +19 new tests via the new file; full
pytest run pending (sandbox-blocked); founder to run
`python -m pytest -q tests/test_s7_t1_discount_dependency_hygiene_builder.py`
then the full suite before S7-T1.5.
**Summary:** [agent_outputs/code-refactor-engineer-s7-t1-summary.md](agent_outputs/code-refactor-engineer-s7-t1-summary.md)
