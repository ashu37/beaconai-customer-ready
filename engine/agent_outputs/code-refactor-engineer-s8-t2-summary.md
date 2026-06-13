# S8-T2 — Sensitivity typed dataclass + PlayCard.sensitivity field (flag OFF)

**Author:** code-refactor-engineer
**Date:** 2026-05-24
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `fcc87af`
**Approved ticket:** S8-T2 — Per IM S8 plan Part B S8-T2 + DS verdicts 2026-05-24 (Q7 §4 separate `ENGINE_V2_SENSITIVITY` flag override of IM bundling default; cfg-wiring §Q5 invariant 16 harness test discipline). Second of 3 S8 additive PlayCard fields per DS verdict §5 invariant 12. No behavior change at flag default OFF. T2.5 atomic flip is a separate later dispatch.

## 1. Approved scope

- New typed `Sensitivity` dataclass at `src/engine_run.py` (4 scenario fields: observed_n halved/doubled, prior ±25% shifted) + `pseudo_n_used: int` + `notes: List[str]` = 6-key block.
- New `PlayCard.sensitivity: Optional[Sensitivity] = None` field, additive within `event_version=1`.
- New `compute_sensitivity()` + private `_revenue_range_from_blend()` helpers in `src/sizing.py` that reuse `bayesian_blend` and the same `audience * posterior * aov` revenue formula the live `RevenueRange` uses. **NO parallel sizing math.**
- Producer-side population at `build_prior_anchored_play_card` alongside the existing `evidence_source` populate, behind a separate `ENGINE_V2_SENSITIVITY` cfg.get() branch. Gated on validated, non-suppressed BLEND path + positive `audience_size`/`aov`.
- New flag `ENGINE_V2_SENSITIVITY` at `src/utils.py` default OFF (separate from `ENGINE_V2_TIER_CHIP` per DS Q7 §4).
- Bool-coerce set update at `src/utils.py:1041` — defensive fix discovered during harness test (string `"false"` was leaking populated `sensitivity` at flag OFF in the subprocess harness).
- 25 new tests in `tests/test_s8_t2_sensitivity.py` + 2 new harness parametrize rows in `tests/test_v2_harness_cfg_gated_fields.py` (per DS invariant 16).

## 2. Patch summary

Prior-shift magnitude 25% chosen because IM spec was ambiguous on "±1σ" (no σ exists at the helper interface). Documented in commit body as a magnitude pick subject to future tuning if beta merchants want a different value.

Sensitivity helper reuses `bayesian_blend` end-to-end — no parallel sizing math. Producer populates only on the validated_external/internal/elicited_expert path (refusal at HEURISTIC_UNVALIDATED + PLACEHOLDER preserved per DS invariant 2).

**Caught and fixed a latent bool-coerce bug** at `src/utils.py:1041` — the bool-coerce set was missing `ENGINE_V2_SENSITIVITY`, so `os.getenv("ENGINE_V2_SENSITIVITY", "false")` returned the string `"false"` which Python evaluates as truthy. Adding to the coerce-set matches the existing pattern that already protects `ENGINE_V2_TIER_CHIP`. Without this fix, T2.5 would have observed pre-flip drift (sensitivity populated at flag OFF in subprocess harness).

## 3. Files changed

- `src/engine_run.py` — `Sensitivity` dataclass at lines ~525-595; `PlayCard.sensitivity` field at lines ~728-744; `_from_dict_sensitivity` helper at lines ~1083-1118; `_from_dict_play_card` wired at line ~1158.
- `src/sizing.py` — `_revenue_range_from_blend` and `compute_sensitivity` at lines ~182-345 (new section); `__all__` extended at line ~768.
- `src/measurement_builder.py` — `Sensitivity` import at L72; population block at lines ~2432-2462; constructor kwarg at line ~2483.
- `src/utils.py` — `ENGINE_V2_SENSITIVITY` flag at lines ~704-728 default OFF; bool-coerce set updated at line 1041 (defensive fix).
- `tests/test_s8_t2_sensitivity.py` — new file (25 tests).
- `tests/test_v2_harness_cfg_gated_fields.py` — new "Harness coverage — S8-T2 Sensitivity" block + 2 parametrized rows per DS invariant 16.

## 4. Tests/checks run

- `tests/test_s8_t2_sensitivity.py`: 25 passed.
- `tests/test_v2_harness_cfg_gated_fields.py`: 5 passed (3 pre-existing + 2 new S8-T2 rows).
- `tests/test_s8_t1_evidence_source_chip.py`: 25 passed unmodified.
- `tests/test_s7_6_c1_priority_prepend_invariant.py`: 8 passed + 2 xfailed unmodified.
- `tests/test_slate_regression_beauty_brand.py`: 18 passed + 1 xpassed (Beauty sha `f8676c9f...` byte-identical).
- `tests/test_slate_regression_supplements_brand.py`: 11 passed + 1 xpassed (Supplements sha `13a91e6c...` byte-identical).
- Full suite: **1798 → 1825 passed**, 14 skipped, 4 xfailed, 2 xpassed, 0 failed (+27 = +25 unit + 2 harness).

## 5. Behavior changes

- Flag OFF default: zero behavior change. Every `PlayCard.sensitivity` is `None`; every existing fixture sha is unchanged.
- Flag ON (only via explicit `ENGINE_V2_SENSITIVITY=true` env override, not yet enabled): the 4 wired Tier-B builders on the validated, non-suppressed BLEND path populate `sensitivity` with a 6-key block computed from the same `bayesian_blend` the live `revenue_range` uses. Verified live on 3 Beauty Tier-B Recommended cards via the harness test.

## 6. Artifacts added

- `tests/test_s8_t2_sensitivity.py` (new, 25 tests).
- New typed schema: `Sensitivity` dataclass + `PlayCard.sensitivity` Optional field, additive within `event_version=1`.
- `agent_outputs/code-refactor-engineer-s8-t2-summary.md` (this file; backfilled 2026-05-25).

## 7. Remaining risks

- **Prior-shift magnitude documented as 25%** (IM spec was ambiguous on "±1σ" — no σ exists at the helper interface). If beta merchants want a different magnitude, this is a 1-line edit; could be filed as a KI for future tuning.
- **T2.5 atomic flip (separate later dispatch)** will re-pin Beauty + Supplements `engine_run.json` to encode the populated `sensitivity` block on the 3 Tier-B Recommended cards. M0 byte-identical (no Tier-B activation on M0).
- **The bool-coerce set fix at `src/utils.py:1041`** was a defensive add discovered during the harness test — same coerce list that already protects `ENGINE_V2_TIER_CHIP`. Pattern-protection for future flag additions: every new `ENGINE_V2_*` flag must be added to this set.

## 8. Follow-up work

- **S8-T2.5** (separate dispatch): atomic flip `ENGINE_V2_SENSITIVITY` default OFF → ON + Beauty/Supplements `engine_run.json` re-pin per S7.6 atomic-flip discipline. Pattern mirrors S8-T1.5 commit `98dad72`.
- **S8-T3**: EB blend layer in `sizing.py` + `provenance` field (third + final S8 additive PlayCard field, completes invariant 12 cap).
- **S8-T4**: Play Library wave 1 (refactor; zero-re-pin target).

## 9. Verbatim founder ask answers

- **Exact line numbers in `src/engine_run.py`:** Sensitivity dataclass at ~525-595; PlayCard.sensitivity at ~728-744; `_from_dict_sensitivity` at ~1083-1118; round-trip wired in `_from_dict_play_card` at ~1158.
- **Exact location in `src/sizing.py`:** `_revenue_range_from_blend` and `compute_sensitivity` at ~182-345. Scenario names: observed_n halved/doubled, prior shifted ±25%.
- **Exact line numbers in `src/measurement_builder.py`:** import L72; population L2432-2462; constructor kwarg L2483.
- **Flag location + default in `src/utils.py`:** ~704-728 (default `"false"`); bool-coerce set updated at line 1041.
- **New test file name + count:** `tests/test_s8_t2_sensitivity.py` (25 tests).
- **New parametrize rows in `tests/test_v2_harness_cfg_gated_fields.py`:** 2 (per DS invariant 16, flag ON/OFF).
- **Suite count:** 1798 → 1825 (+27).
- **M0 + Beauty + Supplements sha256 byte-identical:** confirmed.
- **S8-T1 25 tests + T1.6 harness test + S7.6 CLI fix tripwire + S7.6 priority_prepend invariant tests:** all pass unmodified.
- **Commit sha:** `fcc87af`.
