# S8-T1.5 — flip ENGINE_V2_TIER_CHIP ON (evidence_source = STORE_OBSERVED activates on 3 Beauty Tier-B Recommended cards)

**Author:** code-refactor-engineer
**Date:** 2026-05-24
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `98dad72`
**Approved ticket:** S8-T1.5 — Per IM S8 plan Part B S8-T1 atomic-flip half + DS verdict 2026-05-24 §4 (separate per-ticket atomic flip discipline; cf. S8-T1.5 follows the cfg-wiring fix landed at S8-T1.6 commit `7df2399`). Pure default-flip ticket; no other S8 flags touched.

## 1. Approved scope

- Flip `ENGINE_V2_TIER_CHIP` default from `false` to `true` at `src/utils.py:702`.
- Re-pin any pinned fixture whose `engine_run.json` (or `briefing.html`) shape changes. Predict-then-verify per CLAUDE.md "instrument-over-predict" lesson.
- Empirical tripwire: 3 Beauty Tier-B Recommended cards each carry `evidence_source = STORE_OBSERVED` post-flip without env override.

## 2. Patch summary

Single one-line edit at `src/utils.py:702` changing the `os.getenv` fallback from `"false"` to `"true"`. Env-override path preserved. No re-pin needed — Beauty HTML byte-identical because the renderer does not surface `evidence_source` (founder ack 2026-05-24: `briefing.html` is debug-only retiring; inspection via `engine_run.json` directly).

## 3. Files changed

- `src/utils.py` — line 702 default change (`"false"` → `"true"`). Env-override path at the same site preserved (the change is to the `os.getenv("ENGINE_V2_TIER_CHIP", "<DEFAULT>")` fallback string only).

## 4. Tests/checks run

- Empirical tripwire via `scripts/s8_t1_5_probe.py` (pre-flip with env=ON): 3 Beauty Tier-B Recommended cards carry `STORE_OBSERVED` with `measurement.n` = 448 / 224077 / 603 as predicted; Supplements has no Tier-B Recommended cards (all 3 land in Considered with `evidence_source=None`).
- `tests/test_v2_harness_cfg_gated_fields.py`: both parametrized branches pass post-flip without env override path.
- `tests/test_s8_t1_evidence_source_chip.py`: 25 tests pass; flag-OFF parametrized branches set env explicitly and continue to pass.
- `tests/test_slate_regression_beauty_brand.py`, `tests/test_slate_regression_supplements_brand.py`, `tests/test_synthetic_fixtures.py`, `tests/test_synthetic_fixtures_8_11.py`: all pass; HTML byte-identical confirmed.
- Full suite: **1798 passed**, 14 skipped, 4 xfailed, 2 xpassed (identical to pre-flip 7df2399 baseline).

## 5. Behavior changes

- Default operation now populates `PlayCard.evidence_source = "STORE_OBSERVED"` on Tier-B Recommended cards routed through `build_prior_anchored_recommendations` (currently 3 cards on Beauty; 0 on Supplements/M0).
- The field surfaces in `engine_run.json` (not in `briefing.html`).
- Operators can still set `ENGINE_V2_TIER_CHIP=false` to restore the prior `None` behavior.

## 6. Artifacts added

- `scripts/s8_t1_5_probe.py` (untracked from the pre-work pipeline; later archived to `scripts/archive/s8_probes/` in doc-sweep commit `6462c5a`).
- `agent_outputs/code-refactor-engineer-s8-t1_5-summary.md` (this file; backfilled 2026-05-25).

## 7. Remaining risks

- **T7.5-deferred posture means `aov_lift_via_threshold_bundle` lands in Considered on Beauty;** the chip producer fires for it but the harness contract pins Recommended only. If a future ticket promotes aov_bundle to Recommended without verifying chip population, the harness test `_WIRED_TIER_B_RECOMMENDED_ON_BEAUTY` set may need updating.
- **Test `test_pinned_fixtures_byte_identical_under_s8_t1_flag_off`** retains its flag-OFF name but now runs with default flag-ON (the byte-identity assertion still holds because the renderer is invisible). Docstring slightly stale but the contract it pins (HTML byte-identity regardless of flag state) is intact and correct.

## 8. Follow-up work

- Orchestrator doc sweep covering T1 + T1.6 + T1.5 together (T1-trio precedent style: bundle into single LOAD-BEARING UPDATE block).
- S8-T2 (`ENGINE_V2_SENSITIVITY`) is a separate ticket per DS Q7 verdict 2026-05-24 §4; not in scope here.

## 9. Verbatim founder ask answers

- **Edited line:** `src/utils.py:702` (`"false"` → `"true"`).
- **Pin-test file path:** none — Beauty HTML pin is byte-identical (renderer does not surface chip).
- **Beauty pinned slate sha256:** `f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3` (unchanged).
- **Supplements pinned slate sha256:** `13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344` (unchanged).
- **M0 byte-identical:** confirmed (small_sm `40bf24ea...`, mid_shopify `380b2c5d...`, micro_coldstart `2191b251...`).
- **Empirical tripwire (Beauty, ENGINE_V2_TIER_CHIP=true):** winback `STORE_OBSERVED` n=448; discount_dependency_hygiene `STORE_OBSERVED` n=224077; cohort_journey_first_to_second `STORE_OBSERVED` n=603.
- **T1.6 harness test:** PASS (both flag_off and flag_on parametrized branches).
- **S7.6 CLI fix tripwire test:** PASS unmodified.
- **S8-T1 25 tests:** PASS (flag-ON, flag-OFF, pinned-byte-identity all green).
- **Suite count:** 1798 → 1798 (no change).
- **Commit sha:** `98dad72`.
