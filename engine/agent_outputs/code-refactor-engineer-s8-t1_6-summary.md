# S8-T1.6 — thread cfg=cfg into 4 prior-anchored builder callsites + harness coverage test + structural callsite pin

**Author:** code-refactor-engineer
**Date:** 2026-05-24
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `7df2399`
**Approved ticket:** S8-T1.6 — Per DS verdict 2026-05-24 (`agent_outputs/ecommerce-ds-architect-s8-t1-cfg-wiring-gap-verdict-2026-05-24.md`, Option B, §Q3 acceptance criteria). Surgical cfg-wiring fix that makes the `ENGINE_V2_TIER_CHIP` flag reach production. No behavior change at flag default OFF. Three deliverables in one atomic commit. T1.5 atomic flip is a separate later dispatch.

## 1. Approved scope

S8-T1 (commit `1372feb`) shipped the `EvidenceSourceChip` enum + `PlayCard.evidence_source` field + flag + producer gate correctly. But 4 of 5 callsites of `build_prior_anchored_recommendations` in `src/main.py` didn't thread `cfg=cfg`, leaving the producer gate unreachable from `main.run_action_engine`. T1.6 wires cfg through the 4 missing callsites + adds harness-level coverage + adds a structural callsite pin to prevent the bug class from recurring.

Three deliverables per DS verdict §Q3:

1. Add `cfg=cfg` kwarg to 4 callsites of `build_prior_anchored_recommendations` in `src/main.py` (winback ~L1332, replenishment_due ~L1378, journey_first_to_second ~L1426, discount_dependency_hygiene ~L1478). The 5th callsite (AOV bundle at L1557) already had `cfg=cfg` from S7.6-T5.
2. Harness-level pytest at `tests/test_v2_harness_cfg_gated_fields.py` that runs `main.run_action_engine` end-to-end on Beauty 240d at flag OFF vs ON and asserts `evidence_source` populates correctly.
3. Structural callsite pin: regex-walks `src/main.py`, asserts exactly 5 callsites of `build_prior_anchored_recommendations` exist, asserts each threads `cfg=cfg`. **Pattern-protects S8-T2 / S8-T3 / S13 from re-discovering the same bug class.** Converts "remember to thread cfg" from tribal knowledge into a CI gate.

## 2. Patch summary

Per DS verdict §Q2: kwarg-adding on existing callsites of pre-existing builder seams is WITHIN DS invariant 11 exception, no deviation sign-off needed. The kwarg is purely additive at the producer side (default `None` preserves prior behavior); no new `engine_run = _dc_replace(engine_run, recommendations=...)` mutation introduced.

DS invariant 16 (new, 2026-05-24, DS-locked): every flag-gated producer field MUST be exercised by at least one harness-level test that calls `main.run_action_engine` end-to-end with the flag forced ON and asserts the field populates on at least one rendered card. Canonical test home: `tests/test_v2_harness_cfg_gated_fields.py` (created this commit; T2/T3/T4 each append a parametrize row when they land).

Structural callsite pin opens `src/main.py`, finds every callsite of `build_prior_anchored_recommendations(`, slices forward to the closing `)` of the call (multi-line call handling required), asserts `cfg=cfg` appears within the call's kwarg list. Fails the test with a clear message naming the line number if any callsite is missing `cfg=cfg`.

## 3. Files changed

- `src/main.py` — added `cfg=cfg` kwarg (with explanatory comment) at 4 callsites of `build_prior_anchored_recommendations` (winback L1332, replenishment_due L1378, journey_first_to_second L1426, discount_dependency_hygiene L1478). 5th callsite (aov_lift_via_threshold_bundle L1536 / `cfg=cfg` at L1557) unchanged.
- `tests/test_v2_harness_cfg_gated_fields.py` — new file with 3 tests:
  - Parametrized harness test (flag OFF/ON) that runs `python -m src.main` on Beauty 240d via `tests/synthetic_harness.run_scenario` and asserts `evidence_source` per Tier-B Recommended card in `receipts/engine_run.json`.
  - Structural callsite pin that regex-walks `src/main.py`, asserts exactly 5 callsites of `build_prior_anchored_recommendations` exist, and asserts each threads `cfg=cfg`.

## 4. Tests/checks run

- New module isolated: `pytest tests/test_v2_harness_cfg_gated_fields.py` → 3/3 passed in 39.96s.
- Targeted regression sweep: `pytest tests/test_s8_t1_evidence_source_chip.py tests/test_s7_6_c1_priority_prepend_invariant.py tests/test_s6_t3_y_audience_floor_sensitivity.py tests/test_slate_regression_beauty_brand.py tests/test_slate_regression_supplements_brand.py` → 73 passed, 2 xfailed, 2 xpassed, 0 failed.
- Full suite: `pytest` → **1795 → 1798 passed**, 14 skipped, 4 xfailed, 2 xpassed, 0 failed in 1069s (+3 new tests, matches expectation).
- Byte-identity shasum verification for all 5 pinned fixtures (Beauty `f8676c9f...`, Supplements `13a91e6c...`, M0 `40bf24ea...`, `380b2c5d...`, `2191b251...`) → all unchanged.

## 5. Behavior changes

None at flag default OFF. With `cfg` now threaded but `ENGINE_V2_TIER_CHIP=false` (default), `cfg.get("ENGINE_V2_TIER_CHIP", False)` returns `False`, the producer's `if` branch is not entered, and `evidence_source` stays `None` on every PlayCard — byte-identical to pre-T1.6.

With the flag forced ON via env, the 3 Beauty Tier-B Recommended cards (winback_dormant_cohort, discount_dependency_hygiene, cohort_journey_first_to_second) now correctly carry `evidence_source = "STORE_OBSERVED"` in `receipts/engine_run.json` — empirically verified by the new harness test passing at flag ON. T1.5 atomic flip (separate later dispatch) will flip the default.

## 6. Artifacts added

- `tests/test_v2_harness_cfg_gated_fields.py` — canonical home of DS invariant 16. T2/T3/T4/S13 each append a parametrize row when they land.
- `agent_outputs/code-refactor-engineer-s8-t1_6-summary.md` (this file; backfilled 2026-05-25).

## 7. Remaining risks

- **The structural pin hardcodes `EXPECTED_CALLSITE_COUNT = 5`.** If a future builder block is added, the pin fails until both the new callsite threads `cfg=cfg` AND the count is incremented — intentional gate, but adds a small ergonomic cost. Documented in the failure message.
- **The harness test takes ~40s per run** because it spawns two `python -m src.main` subprocesses on Beauty 240d. Acceptable for invariant-16 coverage; future tickets adding rows multiply this.
- **T1.5 atomic flip is now unblocked but not landed.** Beauty + Supplements pinned fixtures will need re-pin under T1.5 if the chip surfaces in HTML (it does not per founder ack 2026-05-24, so likely byte-identical).

## 8. Follow-up work

- **S8-T1.5** (next dispatch): atomic default flip of `ENGINE_V2_TIER_CHIP` from `false` → `true` per S7.6 atomic-flip discipline. Now unblocked.
- **Single doc sweep** (orchestrator-owned, after T1.5): update memory.md + ARCHITECTURE_PLAN.md + sprint-table to record T1 Done* + T1.6 Done + T1.5 Done + new DS invariant 16 per Q6 sprint-tracking discipline.
- **S8-T2 / S8-T3 / S13** (later): each adds a new flag-gated producer field on the same seam; each must append a parametrize row to the harness test per invariant 16. The structural callsite pin already protects them from cfg-threading regression.

## 9. Verbatim founder ask answers

- **Exact line numbers in `src/main.py`:** 4 callsites edited at L1332, L1378, L1426, L1478; 5th (AOV bundle L1557) verified-but-not-touched.
- **New test file path:** `tests/test_v2_harness_cfg_gated_fields.py`.
- **Test count added:** 3 (1 parametrized harness + 1 structural callsite pin + 1 parametrize variant).
- **Suite count before/after:** 1795 → 1798.
- **M0 + Beauty + Supplements sha256 byte-identical:** confirmed.
- **Harness test at flag ON empirical output:** 3 Beauty Tier-B Recommended cards' `evidence_source = "STORE_OBSERVED"` (winback, discount_dependency_hygiene, cohort_journey_first_to_second).
- **Structural callsite pin test result:** PASS — asserts all 5 callsites thread `cfg=cfg`.
- **S7.6 tripwire tests:** PASS unmodified.
- **S8-T1 25 tests:** PASS unmodified.
- **Commit sha:** `7df2399`.
