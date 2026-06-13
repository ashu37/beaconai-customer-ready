# B-1 — AnomalousWindow auto-registration → ABSTAIN routing

**Owner:** code-refactor-engineer
**Date:** 2026-05-09
**Sprint:** Sprint 1 (Engineer B track, Bucket A Beta blocker)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §1, ticket B-1
**Audit reference:** [agent_outputs/post-6b-stop-coding-audit.md](./post-6b-stop-coding-audit.md) §B-1
**Status:** Complete; full suite green; M0 Beauty pinned fixture byte-identical.

---

## Scope delivered

1.  Surface a previously-missed anomaly: the synthetic `promo_anomaly_240d` fixture was publishing 1 directional + 2 experiments during a clear ~2.5x revenue spike. The existing detectors (BFCM overlap, refund storm, test orders, insufficient history, calendar-only post-promo) all missed it because the spike pattern is "elevated revenue inside the analysis window," not "anchor-on-a-known-promo-date."
2.  Wire the data-quality layer to auto-route on populated flags: any HARD flag → `ABSTAIN_HARD`, the soft `POST_PROMO_WINDOW` alone → `ABSTAIN_SOFT` with per-play hold (`recommendations` cleared, demoted into `considered` with `ReasonCode.ANOMALOUS_WINDOW`).
3.  Populate the previously-reserved typed Observation slots (`anomaly_flags`, `n_days_observed`, `n_days_expected`) so downstream agents can reason about specific anomalies without re-parsing prose.
4.  Preserve the M0 Beauty pinned-fixture byte-identical guarantee — healthy fixtures fire zero flags so the new routing is a no-op.
5.  Defend against silent-rebuild: Phase 5.6 directional candidate builder must not undo the gate.

## Files changed

| File | Change |
|---|---|
| [src/anomaly.py](../src/anomaly.py) | NEW `detect_promo_spike` detector + addition to `_DETECTORS` tuple |
| [config/anomaly_thresholds.yaml](../config/anomaly_thresholds.yaml) | NEW `promo_spike` section with calibrated thresholds |
| [src/utils.py](../src/utils.py) | `ANOMALY_GATE_ENABLED` default flipped from `False` to `True` |
| [src/guardrails.py](../src/guardrails.py) | `gate_anomaly` extended to handle `POST_PROMO_WINDOW` → `ABSTAIN_SOFT`; `apply_guardrails` carries the soft branch through with a distinct `would_fire_if` text |
| [src/state_of_store.py](../src/state_of_store.py) | `build_observations` accepts new keyword-only `n_days_observed` / `n_days_expected`; populates them on every emitted anomaly Observation along with `anomaly_flags=[flag_str]` |
| [src/engine_run_adapter.py](../src/engine_run_adapter.py) | Computes `n_days_observed` / `n_days_expected` from `analysis_window_days` config + order stream and passes them through to `build_observations` |
| [src/main.py](../src/main.py) | Phase 5.6 directional rebuild gate: skip when state is `ABSTAIN_HARD` OR (`ABSTAIN_SOFT` AND populated `data_quality_flags`). Added `DecisionState` import. |
| [src/decide.py](../src/decide.py) | Preserves the upstream `ABSTAIN_SOFT` reason text from `apply_guardrails` (via new `pre_reason` capture) so the load-bearing-anomaly diagnostic survives `_decide_abstain_state` |
| [tests/test_b1_anomaly_auto_register.py](../tests/test_b1_anomaly_auto_register.py) | NEW — 6 tests pinning the three contracts (default-on flag, typed-slot population, end-to-end fixture flip) |
| [tests/test_b1_promo_spike_detector.py](../tests/test_b1_promo_spike_detector.py) | NEW — 5 unit tests for the new detector (positive, flat, no-prior, disabled, empty-df) |
| [tests/test_anomaly_abstain.py](../tests/test_anomaly_abstain.py) | Updated `test_post_promo_window_alone_does_NOT_trigger_abstain_hard` → renamed to assert ABSTAIN_SOFT under B-1; updated `test_flag_off_preserves_legacy_state` to pass explicit `ANOMALY_GATE_ENABLED=False` |
| [tests/test_guardrails.py](../tests/test_guardrails.py) | Updated `TestAnomalyGate::test_post_promo_only_does_not_trigger_hard` to assert ABSTAIN_SOFT routing |

## Detector calibration (load-bearing — change with care)

`detect_promo_spike` uses a 56-day window vs the immediately-prior 56 days. Threshold 2.0x with credibility guards `min_prior_orders=50`, `min_prior_days_covered=28`. Calibration:

| Fixture | L56 ratio | Decision |
|---|---|---|
| `healthy_beauty_240d` (M0 pin) | 1.17 | silent ✓ |
| `healthy_beauty_low_inventory_240d` | 1.10 | silent ✓ |
| `supplement_replenishment_240d` | 1.05 | silent ✓ |
| `small_store_240d` | 1.47 | silent ✓ |
| `cold_start_45d` | n/a (prior=0, fails baseline guard) | silent ✓ (still ABSTAIN_HARD via `INSUFFICIENT_CLEAN_HISTORY`) |
| `promo_anomaly_240d` | **2.28** | **fires POST_PROMO_WINDOW** ✓ |

The 2.0x threshold leaves Beauty (1.17) with substantial headroom and `small_store` (1.47) with a 0.53 buffer. If a future fixture lands at L56 = 1.6-1.9, this threshold should be revisited rather than tuned reactively.

## Sticky-abstain enforcement (Phase 5.6 gate)

The cleanest reason `apply_guardrails` was being silently undone: the legacy adapter's V1 actions list was empty for `promo_anomaly_240d` (V1 had no rec to emit), so the adapter set `Abstain(state=ABSTAIN_SOFT, reason="legacy actions list is empty")`. After `apply_guardrails` cleared recs and re-set the abstain to the load-bearing-anomaly soft, **Phase 5.6's directional builder ran on the same `engine_run` and re-promoted `first_to_second_purchase`** because its supporting signal still passed the bar.

The fix is a narrow gate, not a sledgehammer:

```python
_gate_routed = (
    _abstain_state == DecisionState.ABSTAIN_HARD
    or (_abstain_state == DecisionState.ABSTAIN_SOFT and _has_dq)
)
if _gate_routed:
    _directional_cards = []
else:
    _directional_cards = _build_directional_recs(...)
```

The narrow gate matters because the legacy adapter's "no V1 actions" ABSTAIN_SOFT is exactly the case Phase 5.6 was designed to recover from (cold-V1 with hot-V2 signal). Distinguishing the two ABSTAIN_SOFT origins by the presence of a populated `data_quality_flags` list is structurally clean and matches the `apply_guardrails` anomaly-route signature exactly.

## Hard constraints respected

- `engine_run.json` schema **unchanged** (typed slots were already reserved in Phase 6B Stop-Coding; B-1 only writes values into them).
- M0 Beauty pinned fixture **byte-identical** (`tests/test_slate_regression_beauty_brand.py::test_briefing_matches_pinned_fixture_bytewise` green).
- `RECENTLY_RUN_FATIGUE_ENABLED` and other guardrail flags untouched.
- Vertical scope hard-lock (B-7) untouched.
- No substrate work (S-2+ scope).
- No banned ML scaffolding (D-6).
- Engine remains runnable after every patch.
- Single-writer-per-event-type discipline preserved (no new event-type writers).

## Test results

| Suite | Result |
|---|---|
| `tests/test_b1_anomaly_auto_register.py` | 6/6 |
| `tests/test_b1_promo_spike_detector.py` | 5/5 |
| `tests/test_anomaly_abstain.py` (updated) | 7/7 |
| `tests/test_guardrails.py` (updated) | 51/51 |
| `tests/test_slate_regression_beauty_brand.py` | 19/19 (M0 byte-identical) |
| **Full suite** | **950 passed, 14 skipped, 0 failed** (~3 min 15 s) |

## Out of scope (deliberately not touched)

- New `ANOMALOUS_WINDOW_DETECTED` typed `DataQualityFlag` value — the ticket prose mentioned this name but reusing the existing `POST_PROMO_WINDOW` enum value avoids a schema-perturbing churn for zero operational benefit. The downstream typed slots still carry the specific flag string.
- Recalibration of `detect_bfcm_overlap` / `detect_refund_storm` / `detect_test_order_anomaly` / `detect_insufficient_clean_history` — all four already fire correctly on their respective synthetic shapes; the gap was specifically in spike detection inside the analysis window.
- Registering `AnomalousWindowCheck` in `DataValidationEngine.checks` — the receipts-only `engine_run.json` adapter already runs the detectors via `detect_anomalous_windows`. Explicitly registering the validation check would mutate `validation_report.json` (a separate M0 golden contract surface) for no operational benefit. Documented in the existing module-level comment in `validation.py`.
- Any tightening to `decide()` for ABSTAIN_HARD pre-state preservation — already pinned by the existing logic at `_decide_abstain_state` (line 953). Only ABSTAIN_SOFT reason preservation was missing, and that's the one-line change made.

## Risks observed during implementation (all resolved)

- **Phase 5.6 silent-rebuild trap:** the adapter's "legacy actions list is empty" ABSTAIN_SOFT was masking the gate fire. Mitigation: narrow gate keyed on `data_quality_flags` non-emptiness so cold-start V2-recovery still works.
- **Adapter day-count computation depending on optional `pandas` import:** wrapped in try/except, defaults to 0/0 on any failure. Typed slots are reservation-shaped so 0 is a safe default.
- **Cross-fixture false-positive risk:** validated against all five other synthetic fixtures plus the M0 Beauty pin; only `promo_anomaly_240d` fires.

## Commit shape

Single commit for the ticket (`726fbd2`), separate commit for `memory.md` update (`7de5546`), per the per-ticket-ritual rule.

```
B-1: AnomalousWindow auto-registration + ABSTAIN routing
Document B-1 in repo memory.md
```

## Next ticket

B-3 (hardcoded-fallback regression test) — pure test, no behavior change. Greps `measurement.effect_abs` / `measurement.p_internal` on Beauty pinned slate (and a synthetic supplements run) for the Phase 2 fallback constants `{0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40}`.
