# S7 flips rollup — atomic flag-flip closeouts (T1.5, T2.5, T3.5, T4.5)

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commits covered:** `9ec1595` (T1.5), `41f9d81` (T2.5), `276d398` (T3.5), `c9e4884` (T4.5)
**Note:** This is a rollup-style summary for four mechanically-identical Sprint 2 Risk #4 atomic flag-flip commits. Per the 2026-05-25 backfill discipline, each flip ticket on its own would have produced an individual file under the S6/S7 precedent; bundling here is a backfill compaction, not the standard.

---

## 1. Ticket scope

Four atomic flag flips, each closing the corresponding S7 builder ticket by flipping the default OFF -> ON for the builder it ships and re-pinning fixtures atomically (Sprint 2 Risk #4 contract). Operator override `<FLAG>=false` in `.env` rolls back to the pre-flip baseline in one variable.

- **T1.5 (9ec1595)** — flip `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE` ON. `discount_dependency_hygiene` activates end-to-end on Beauty as a Recommended Now card; under the cap=3 slate, `first_to_second_purchase` is displaced from Recommended Now (remains in engine_run). Supplements ships Path-D dormant per DS Memo-4 REJECT (no priors block, no gate_calibration cell). Heavy-promo conditional bump stays DORMANT (DS verdict (c) 2026-05-21; commerce_posture.discount_fraction attribute belongs to Sprint 8).
- **T2.5 (41f9d81)** — flip `ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND` ON + atomic Beauty re-pin. `cohort_journey_first_to_second` anchors on the wildcard-vertical `first_to_second_purchase.base_rate` validated_external prior and surfaces as the LEAD Recommended Now card on Beauty. Supplements remains in ABSTAIN_SOFT (upstream gate, not vertical asymmetry); supplements pinned slate byte-identical.
- **T3.5 (276d398)** — flip `ENGINE_V2_BUILDER_AOV_BUNDLE` ON. Beauty anchors on Memo-2 validated_external prior (pseudo_n=30); supplements anchors on Memo-3 elicited_expert DOWNGRADED prior (pseudo_n=10, alpha=0.095, beta=9.905) per DS verdict + KI-NEW-J cross-vertical evidence laundering safeguard. The builder is wired correctly through `_registry_for_detect` but does not surface on either synthetic fixture under the observed candidate set + gate stack at flip time. DS-predicted supplements Recommended Now activation awaits Sprint 8 commerce_posture work + KI-NEW-K Beta re-fit.
- **T4.5 (c9e4884)** — flip `ENGINE_V2_ABSTAIN_4STATE` ON. Pure contract flip (renderer reads `state`, not `mode`, per D-S6.5-20 Stop-Coding adjacency). `_compute_abstain_mode` applies the DS-locked Gap F majority-with-tiebreak precedence over four modes (SOFT_AWAITING_MEASUREMENT, SOFT_PRIOR_UNVALIDATED, SOFT_BELOW_FLOOR, SOFT_AUDIENCE_TOO_SMALL); `TARGETING_HELD_UNDER_ABSTAIN` excluded from the count. No re-pin attached (expected shape of a contract-only flip).

## 2. Files changed

- **T1.5 (9ec1595, 7 files):** `src/utils.py`; `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`; `tests/test_slate_regression_beauty_brand.py`; `tests/test_s5_t2_supplement_cadence_abstain.py`; `tests/test_s6_t3_y_audience_floor_sensitivity.py`; `tests/test_s6_t3_z_considered_render.py`; `tests/test_s7_t1_discount_dependency_hygiene_builder.py`.
- **T2.5 (41f9d81, 6 files):** `src/utils.py`; `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`; `tests/test_slate_regression_beauty_brand.py`; `tests/test_s7_t2_cohort_journey_first_to_second_builder.py`; `tests/test_s6_t3_y_audience_floor_sensitivity.py`; `tests/test_s6_t3_z_considered_render.py`.
- **T3.5 (276d398, 2 files):** `src/utils.py`; `tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py`.
- **T4.5 (c9e4884, 1 file):** `src/utils.py` (DEFAULTS + `_coerce` boolean key set).

## 3. Behavior change

- **T1.5:** Beauty Recommended Now slate now contains `discount_dependency_hygiene` (drops `first_to_second_purchase` under cap=3). Beauty pinned sha256 `3d7ef3d725...` -> `158bf726f5...`. Supplements + M0 byte-identical.
- **T2.5:** Beauty Recommended Now expands 2 -> 3 cards with `cohort_journey_first_to_second` leading. Considered/Experiments/Watching memberships unchanged. Beauty pinned sha256 `cacb6691...` -> `3d7ef3d725...`. Supplements G-1 + M0 byte-identical.
- **T3.5:** All 5 pinned fixtures byte-identical. Builder is now eligible end-to-end but inert on current synthetic fixtures (DS-predicted activation deferred to Sprint 8).
- **T4.5:** All 5 pinned fixtures byte-identical (contract-surface-only flip). `Abstain.mode` now populated per the 4-state precedence on downstream contract consumers; renderer unchanged.

## 4. Tests added / modified

- **T1.5:** test renames (FTSP stay-in-Recommended -> FTSP displaced); `test_t9_default_flag_off_at_t1` inverted to `test_t9_default_flag_on_post_t1_5`; sha re-pins in 2 pinned-fixture sha tests.
- **T2.5:** `EXPECTED_RECOMMENDED_PLAY_IDS` gains `cohort_journey_first_to_second`; `EXPECTED_RECOMMENDED_COUNT` 2 -> 3; `test_t9_default_flag_off_at_t2` -> `test_t9_default_flag_on_post_t2_5`; sha re-pins.
- **T3.5:** `test_t10_default_flag_off_at_t3` inverted to assert True (no fixture sha changes).
- **T4.5:** none — DEFAULTS change only.

Suite at each flip: 1646 passed / 14 skipped / 3 xfailed / 1 xpassed / 0 failed (T1.5 / T2.5 / T4.5 reported identically; T3.5 same baseline).

## 5. Risks + mitigations

- **T1.5 — heavy-promo conditional bump dormant.** D-FLOOR conditional rule (`commerce_posture.discount_fraction > 0.40` bumps floor to {80/200/500/1500}) ships dormant per DS verdict (c). Bump logic + attribute deferred to Sprint 8. T18 pins the absence (will need inversion when attribute lands).
- **T1.5 — KI-NEW-K Beauty Beta envelope re-fit deferred** to Sprint 8 (effective_n=60). Today's range_p10/range_p90 text-derived from source memo, not CDF-derived from J-shaped Beta. Resolved at S8-T0 (commit `77086fd`).
- **T3.5 — builder inert on current fixtures.** Eligibility wiring is correct (`_registry_for_detect` includes the play_id) but no Recommended Now card emerges on either synthetic vertical at flip time. Sprint 8 commerce_posture + KI-NEW-K re-fit + S7.6 observed-effect gate together unlock honest surface placement; the S7.6 sprint subsequently demoted aov_bundle to Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` on Beauty (joint-fail), exactly the placement the gate was designed for.
- **T4.5 — `Abstain.mode` not yet rendered.** Structured slot for downstream agents only; renderer continues to read `state`. Document deferral; no merchant-facing change.

## 6. Follow-ups / known-issues opened

- **From T1.5:** `commerce_posture.discount_fraction` profile attribute (Sprint 8); KI-NEW-K Beauty envelope re-fit (closed at S8-T0).
- **From T2.5:** none — clean close.
- **From T3.5:** Sprint 8 commerce_posture + the S7.6 observed-effect eligibility gate unblock honest aov_bundle placement.
- **From T4.5:** Eventual renderer surfacing of `Abstain.mode` (when copy ladder owns it); meanwhile the mode flows into memory.db reason fan-out and engine_run consumers only.

## 7. Commit ref

- T1.5 — `9ec1595`
- T2.5 — `41f9d81`
- T3.5 — `276d398`
- T4.5 — `c9e4884`

Sprint 7 closeout: all four S7 builder flags (DISCOUNT_HYGIENE, JOURNEY_FIRST_TO_SECOND, AOV_BUNDLE, ABSTAIN_4STATE) default ON post-T3.5.
