# S13.5-T1 — KI-NEW-L collapse summary

**Ticket:** S13.5-T1 — Collapse 5 V2 prior-anchored injection blocks → single `dispatch_prior_anchored_builders`
**Sprint:** S13.5 (single-ticket structural-cleanup window between S13-T4 and S14-T1)
**Date:** 2026-05-30
**Branch:** `post-6b-restructured-roadmap`
**Parent commit (pre-ticket):** `cee0e3c`
**Source-of-truth scope:** `KNOWN_ISSUES.md::KI-NEW-L` + `agent_outputs/implementation-manager-s13.5-s13.6-s13.7-plan.md` §4

---

## 1. Scope (DS-locked)

Collapse the **five V2 prior-anchored injection blocks** at the legacy
`src/main.py:1604-1898` zone (S6-T1 winback / S6-T3 replenishment /
S7-T2 cohort_journey_first_to_second / S7-T1 discount_dependency_hygiene /
S7-T3 aov_lift_via_threshold_bundle) plus the single S7.6-C2
`apply_guardrails_to_injected` block at L1900-1970 into one dispatch
function keyed by the `_PRIOR_ANCHORED` registry at
`src/measurement_builder.py:721`.

Forbidden-zone restriction at `src/main.py:1380-1597` is lifted FOR THIS
TICKET ONLY per `ROADMAP.md` §1 + KI-NEW-L.

Out-of-scope (untouched):
- `src/main.py:1972+` — S13-T2 PlayCard consumer-wiring callsite.
- `src/main.py:2040+` — S13-T3 month_2_delta callsite.
- `src/decide.py`, `src/sizing.py`, `src/engine_run.py`, `src/guardrails.py`.

---

## 2. Files changed

| Path | Change | Net lines |
|---|---|---|
| `src/dispatch_prior_anchored.py` | **NEW** — dispatch helper, registry-keyed | +291 / -0 (new file) |
| `src/main.py` | Collapse 5 blocks + guardrails block → 1 helper call | -367 / +51 (≈ -316 net) |
| `tests/test_s13_5_single_emission_point.py` | **NEW** — AST-aware single-emission-point pin | +180 / -0 (new file) |
| `tests/test_v2_harness_cfg_gated_fields.py` | Re-pointed cfg-threading scan from `src/main.py` to `src/dispatch_prior_anchored.py`; count 5 → 1; accept `cfg=cfg_local` | +37 / -22 |

No other files modified.

---

## 3. Implementation summary

**New module `src/dispatch_prior_anchored.py`:**

- Defines `_DispatchEntry` frozen dataclass + ordered tuple `_DISPATCH_TABLE` with 5 entries in load-bearing order (winback → replenishment → journey → discount → AOV-bundle). Order preserved verbatim from the legacy block sequence for append-order byte-identity.
- Each entry carries `(play_id, builder_flag, observed_kwarg, observed_flag)` — the only per-play variation across the 5 legacy blocks.
- `dispatch_prior_anchored_builders(...)`:
  1. Short-circuits when `gate_routed=True` (matches every legacy `not _gate_routed` guard).
  2. Lazy-imports `build_prior_anchored_recommendations`, `apply_guardrails_to_injected`, `PLAYS`, `compute_audience_overlap`, `get_builder` (so legacy non-V2 paths don't pay the import cost).
  3. Takes the S7.6-T7-FIX pre-injection snapshot of `engine_run.recommendations[*].play_id`.
  4. Iterates `_DISPATCH_TABLE` in order. For each entry whose `builder_flag` is ON, calls `build_prior_anchored_recommendations` once with `allowed_play_ids={play_id}` + the play-specific observed-effect kwarg derived from `entry.observed_flag`. On success, appends results to `engine_run.recommendations`.
  5. Each builder call wrapped in `try/except` to preserve per-block failure isolation (legacy print-warning posture).
  6. After the loop, calls `apply_guardrails_to_injected` exactly **once** with the pre-injection snapshot + recomputed injected-overlap map. Wrapped in the same try/except shape as the legacy S7.6-C2 block.

**`src/main.py` rewrite:**

- L1604-1970 (367 lines) replaced with a 51-line block:
  - Comment block documenting the collapse + 3 preserved invariants.
  - Single import of `dispatch_prior_anchored_builders`.
  - Single call passing `engine_run` + all threaded context (`_phase5_cands`, `aligned_for_template`, `_vertical`, `_subvertical`, `_store_profile`, `_profile_flag_on`, `_gate_routed`, `g`, `inventory_metrics`, `store_dir`, `store_id`, `cfg`).

---

## 4. Tests/checks run

**Baseline (pre-edit) on parent `cee0e3c`:**

| Suite | Result |
|---|---|
| Full collect | 2142 tests collected |
| `tests/test_s7_6_c1_priority_prepend_invariant.py` + `tests/test_reason_code_precedence_invariant.py` | 12p / 2 xfailed |
| `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` + `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` | **2 failed (pre-existing KI-NEW-U)** |

**Post-edit:**

| Suite | Result |
|---|---|
| `tests/test_s7_6_c1_priority_prepend_invariant.py` + `tests/test_reason_code_precedence_invariant.py` | 12p / 2 xfailed (unchanged) |
| `tests/test_s13_5_single_emission_point.py` (NEW) | 5p / 0f |
| Pinned-fixture suite (`tests/test_slate_regression_beauty_brand.py`, `tests/test_slate_regression_supplements_brand.py`, `tests/test_s6_5_t5_atomic_repin.py`, `tests/test_s6_t1_5_winback_dormant_repin.py`, `tests/test_synthetic_fixtures_8_11.py`, `tests/test_s13_ml_fit_never_demotes.py`) | 61p / 2 xfailed / 2 xpassed / **1 failed = pre-existing KI-NEW-S wall-clock flake on `test_inventory_updated_at_is_fresh`** |
| `tests/test_v2_harness_cfg_gated_fields.py::test_every_build_prior_anchored_callsite_threads_cfg_kwarg` (re-pointed) | 1p / 0f |
| Full suite (excluding KI-NEW-S flake): | **2110p / 15 skipped / 4 xfailed / 2 xpassed / 3 failed** |

The 3 failing tests in the full run are all PRE-EXISTING on parent `cee0e3c`:
- `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` — KI-NEW-U.
- `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` — KI-NEW-U.
- `tests/test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` — KI-NEW-S (wall-clock flake; max age now 12 days vs static fixture; entirely unrelated to engine logic).

Pre-existence verified by `git stash` → run → `git stash pop`; same 2 KI-NEW-U failures reproduce on `cee0e3c`. KI-NEW-S documented in `ROADMAP.md` §1 follow-ups.

**Net delta from my changes: 0 new failures, 1 new test file with 5 new passes, 1 test file re-pointed and now passing.**

---

## 5. All 4 DS-locked invariants verified

| # | Invariant | Verification |
|---|---|---|
| 1 | **Single-demote-channel (Pivot 7).** All paths route through `apply_guardrails_to_injected`. New dispatch helper has exactly ONE call site. | `tests/test_s13_5_single_emission_point.py::test_main_py_does_not_call_apply_guardrails_to_injected` (AST: no call in `src/main.py`). Helper module contains exactly one `_apply_guardrails_to_injected(...)` call after the dispatch loop. |
| 2 | **Three-channel `priority_prepend`.** `eligibility_rejects`, `prior_unvalidated_rejects`, `window_disagreement_rejects` all prepended into Considered ahead of `pre_existing` so `MAX_CONSIDERED_RENDERED=6` truncation cannot silently drop them. | `tests/test_s7_6_c1_priority_prepend_invariant.py` — 12p (green). My change touched neither `src/decide.py` (where prepend lives) nor the 3 reject-channel producers. |
| 3 | **Observed-effect surfacing at `src/measurement_builder.py:2252-2270`.** Every Tier-B Recommended card populates `Measurement.observed_effect`, `Measurement.p_internal`, `Measurement.n` from `blend_provenance`. | `tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_recommended_cards_surface_observed_effect_on_beauty` — green. Per-builder `observed_*_enabled` kwargs threaded identically through the helper. |
| 4 | **Per-builder byte-identity on Beauty + supplements pinned slates.** | `tests/test_slate_regression_beauty_brand.py::test_pinned_fixture_sha256_matches` + `tests/test_slate_regression_supplements_brand.py::test_pinned_fixture_sha256_matches` both pass. `tests/test_s6_5_t5_atomic_repin.py::test_01_beauty_new_sha256_pin` + `test_supplements_sha256_pin_holds` pass. |

---

## 6. Beauty fixture SHA — before/after

Beauty pinned `briefing.html` sha256:
- **Before:** per `tests/fixtures/pinned_sha_ledger.json`: `f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3` (post_s13_t3_5).
- **After:** UNCHANGED. `tests/test_s6_5_t5_atomic_repin.py::test_01_beauty_new_sha256_pin` enforces this pin and passes post-edit.

## 7. Supplements fixture SHA — before/after

Supplements pinned `briefing.html` sha256:
- **Before:** per ledger: `13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344`.
- **After:** UNCHANGED. `tests/test_slate_regression_supplements_brand.py::test_pinned_fixture_sha256_matches` + `tests/test_s6_5_t5_atomic_repin.py` supplements pin both pass.

## 8. M0 goldens

Byte-identical. The pinned-fixture suite includes the M0 golden-replay tests and they pass unchanged.

---

## 9. Key risks encountered + mitigations

1. **Risk: append-order byte-drift.** The legacy 5 blocks fire in a specific order — re-ordering would re-order entries in `engine_run.recommendations` and change downstream rank / cap / truncation.
   - **Mitigation:** `_DISPATCH_TABLE` is an ordered tuple (not a dict iteration over `_PRIOR_ANCHORED.keys()`). Order pinned verbatim: winback → replenishment → journey → discount → AOV-bundle. Beauty + supplements SHA tests confirm zero drift.

2. **Risk: dropped audience-overlap recompute.** Legacy block at L1925-1954 recomputed the audience-overlap map across the post-injection recs before calling `apply_guardrails_to_injected`. Missing this would cause silent cannibalization-gate misses.
   - **Mitigation:** Recompute block ported verbatim into the helper (same `_compute_overlap` + `_get_audience_builder` invocation pattern, same `CANNIBALIZATION_GATE_ENABLED` gate).

3. **Risk: stale structural test in `test_v2_harness_cfg_gated_fields.py`.** That test enforced "every callsite in `src/main.py` threads `cfg=cfg`" with `EXPECTED_CALLSITE_COUNT=5`. Post-collapse, callsites moved to the helper.
   - **Mitigation:** Test re-pointed to scan `src/dispatch_prior_anchored.py`; count updated to 1; accepts `cfg=cfg_local` (the helper's normalized local alias). The DS-locked cfg-threading invariant remains enforced — only the location moved. No invariant relaxation.

4. **Risk: per-block failure isolation lost.** Each legacy block had its own `try/except` with a play-id-tagged print warning. A naive collapse could lose this isolation (one builder raising would skip downstream builders).
   - **Mitigation:** Helper wraps each per-entry call in its own `try/except` with a play-id-tagged warning (`[V2 prior-anchored dispatch:{play_id}] Warning: ...`). Single-pass isolation preserved.

5. **Risk: forbidden-zone deviation.** The S13-T2 PlayCard consumer wiring at `src/main.py:1972-2038` and S13-T3 month_2_delta callsite at `src/main.py:2040+` are explicitly out of scope.
   - **Mitigation:** Edit boundaries verified: my Edit replaced exactly L1604-1970. Read of L2024+ post-edit confirmed the consumer-wiring block is structurally intact.

---

## 10. Key learnings (terse)

- The legacy 5 blocks differ only in `(builder_flag, observed_kwarg, observed_flag, play_id)` — every other kwarg is identical. The collapse is a textbook table-driven refactor.
- AST-aware tests (modeled on `tests/test_reason_code_precedence_invariant.py`) are cheap to write and pin the structural invariant much more durably than a regex scan.
- Pre-existing failures on `cee0e3c` must be characterized explicitly (KI-NEW-S, KI-NEW-U) so the orchestrator's DS review doesn't mis-attribute them to this ticket.

---

## 11. Deviation check

**None.** The collapse follows the DS-locked spec verbatim: registry-keyed dispatch + single `apply_guardrails_to_injected` call + 4 invariants preserved + byte-identical pinned slates. The one in-scope test re-point (`test_v2_harness_cfg_gated_fields.py::test_every_build_prior_anchored_callsite_threads_cfg_kwarg`) is mechanical and preserves the cfg-threading invariant — only the file the test scans moves with the code.

---

## 12. Proposed commit message (for orchestrator)

```
S13.5-T1: Collapse 5 V2 prior-anchored injection blocks → single dispatch_prior_anchored_builders (KI-NEW-L)

Collapse the five legacy V2 prior-anchored injection blocks
(winback_dormant_cohort, replenishment_due, cohort_journey_first_to_second,
discount_dependency_hygiene, aov_lift_via_threshold_bundle) plus the
single S7.6-C2 apply_guardrails_to_injected call at src/main.py:1604-1970
into a new dispatch helper at src/dispatch_prior_anchored.py keyed by an
ordered _DISPATCH_TABLE that mirrors the _PRIOR_ANCHORED registry at
src/measurement_builder.py:721. The 5-block sequence + single guardrails
re-invocation collapse from 367 lines in main.py to 51 lines + a 291-line
isolated module.

Invariants preserved (DS-locked):
- Single-demote-channel (Pivot 7) — single apply_guardrails_to_injected call site
- 3-channel priority_prepend — eligibility/prior_unvalidated/window_disagreement
- Observed-effect surfacing at src/measurement_builder.py:2252-2270
- Per-builder byte-identity on Beauty + supplements pinned fixtures

Tests: 2110p/15s/4x/2xp/3f (pre-existing KI-NEW-S wall-clock + 2 KI-NEW-U
stale-default failures; verified pre-existing on parent cee0e3c via stash)
+ NEW tests/test_s13_5_single_emission_point.py (5p) + re-pointed
tests/test_v2_harness_cfg_gated_fields.py cfg-threading scan to the
dispatch helper (1p).

Beauty briefing.html SHA: f8676c9f...3a3 (unchanged)
Supplements briefing.html SHA: 13a91e6c...344 (unchanged)
M0 goldens: byte-identical

Deviation check: none
```

---

## 13. Follow-up work / next milestone dependencies

- **S13.6-T1a** (next): strip prose bundle. Unblocked by this ticket — no dependency loop.
- **Watch:** KI-NEW-U (stale `ENGINE_V2_ML_RFM` + `ENGINE_V2_ML_RETENTION` flag-default-off tests) is still red on parent and on this branch; the IM plan §6 S13.7-T4 sprint-close or a maintenance pass should sweep them per ROADMAP §1 follow-ups.
- **Watch:** KI-NEW-S (wall-clock flake on inventory `Updated At`) — synthetic fixture maintenance pass post-beta.

*End of summary.*
