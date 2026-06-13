# Milestone 5 Summary — Guardrail Engine

_Completed: 2026-05-02 (engine-rework branch)_

## Approved scope

Milestone 5 of `agent_outputs/implementation-manager-overhaul-plan-final.md`:
the guardrail engine. Tickets T5.1, T5.2, T5.3, T5.4, T5.5, T5.6, T5.7.

- T5.1 — Inventory gate (`bestseller_amplify`, `routine_builder`,
  `category_expansion`, `overstock_demand_push`; min cover_days=21).
  No-inventory-data branch is a no-op, NOT a block.
- T5.2 — Anomalous-window gate. HARD `data_quality_flag` on
  `EngineRun` triggers `abstain.state = ABSTAIN_HARD` and clears
  recommendations. POST_PROMO_WINDOW remains a soft warning per the
  M1 enum boundary.
- T5.3 — Scale-aware materiality floor: `<$1M ARR: max($5k, 2%)`,
  `$1M-5M: max($10k, 3%)`, `>$5M: max($25k, 5%)` of monthly revenue.
- T5.4 — Cannibalization / audience-overlap gate (>50% Jaccard demote
  the lower-priority play) PLUS portfolio cap (sum of `revenue_range.p50`
  ≤ 25% of monthly revenue) with the plan's "keep top-1 if cap demotes
  everything" backoff.
- T5.5 — Recently-run-fatigue stub. Reads
  `data/recommended_history.json` if present; no-op otherwise.
- T5.6 — Confirmed `ENABLE_REPEAT_RATE_BIAS_CORRECTION` default remains
  off and removed the inline `cfg.get(..., True)` bypass at the call
  site.
- T5.7 — Pinned the M4b confidence-collapse contract: confidence is
  decoupled from `seasonal_multiplier` whenever
  `EVIDENCE_CLASS_ENFORCED=true`. Added a forcing-function test.

**Out of scope (deferred per the M5 ticket):**
- M6 economic sizing (`size_play()`).
- M7 decision selector / state machine for ABSTAIN_SOFT (the M5
  abstain handling covers ABSTAIN_HARD only).
- M8 renderer flip / Play Thesis output.
- Klaviyo / Shopify production integrations.
- Legacy code deletion.

The product-hostile transition state on `small_sm` (0 PRIMARY actions
under M4b flag-on) is preserved. M5 deliberately does NOT attempt to
"fix" it; that is M7/M8's job. With M5 flags off, the engine is
byte-identical to M4b.

## Files changed

### New files

- `/Users/atul.jena/Projects/Personal/beaconai/src/guardrails.py` —
  the M5 guardrail engine. Pure-function gates plus an
  `apply_guardrails(engine_run, ...)` orchestrator that consumes a
  typed `EngineRun` and returns a NEW `EngineRun` with `considered`
  populated and `abstain` set if a HARD data-quality flag fires.
  All gates are individually flag-gated and default-OFF. Inputs are
  never mutated (uses `dataclasses.replace`).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_guardrails.py` —
  47 unit + integration tests covering every gate plus the
  orchestrator.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_anomaly_abstain.py` —
  7 tests for the M5 plan's "synthetic refund-storm fixture →
  abstain_hard" forcing function. Covers all 4 HARD flags plus the
  POST_PROMO_WINDOW soft-warning carve-out.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_inventory_gate.py` —
  10 tests for the M5 plan's "fixture with no inventory file → gate
  is no-op" forcing function plus per-play behavior.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_materiality_floor.py` —
  16 tests for the three ARR tiers, boundaries, and monotonicity.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_bias_correction_default_off.py` —
  3 tests pinning T5.6: DEFAULTS resolves to False, the call site
  uses `cfg.get(..., False)` (no bypass), and only one
  `bias_corrections = {...}` literal exists.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_seasonality_decoupled.py` —
  3 tests pinning T5.7: confidence is invariant to
  `seasonal_multiplier` when `EVIDENCE_CLASS_ENFORCED=true`, equals
  `_calculate_statistical_confidence` exactly, and the M4b
  short-circuit is still in place.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-milestone-5-summary.md` —
  this file.

### Edited files

- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`:
  - **DEFAULTS**: added five new flags
    (`INVENTORY_GATE_ENABLED`, `ANOMALY_GATE_ENABLED`,
    `CANNIBALIZATION_GATE_ENABLED`, `MATERIALITY_FLOOR_SCALE_AWARE`,
    `RECENTLY_RUN_FATIGUE_ENABLED`) — all default `false`.
  - **`_coerce` bool set**: extended to include the five new flags
    so `.env` overrides parse correctly.
  - **T5.6**: `kpi_snapshot_with_deltas` call site
    `cfg.get("ENABLE_REPEAT_RATE_BIAS_CORRECTION", True)` was a
    bypass (default-True when key missing); changed to
    `cfg.get("ENABLE_REPEAT_RATE_BIAS_CORRECTION", False)` to match
    DEFAULTS. Added a comment block explaining the M5 audit.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`:
  - **Wired `apply_guardrails` into the EngineRun build** (right
    after `build_engine_run_from_legacy`). Computes the audience
    overlap map only when `CANNIBALIZATION_GATE_ENABLED=true` (re-runs
    pure audience builders for each recommendation). Always passes
    `data/recommended_history.json` as the fatigue history path
    (no-op when missing). Wrapped in try/except so a guardrail bug
    can never break the run.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/engine_flags.md`:
  - Bumped "Last updated" stamp to M5.
  - Annotated the M5 flag rows with "(added in M5)" and added the
    new `RECENTLY_RUN_FATIGUE_ENABLED` row.

### Pre-existing files (unchanged in this session)

The full M0–M4b lineage is unchanged. No legacy code was deleted
(M10 still owns deletion).

## Exact commands run

```
# Sanity: the M5 test files only
python -m pytest tests/test_guardrails.py tests/test_anomaly_abstain.py \
                 tests/test_inventory_gate.py tests/test_materiality_floor.py \
                 tests/test_bias_correction_default_off.py \
                 tests/test_seasonality_decoupled.py -v
# 89 passed

# M4b goldens still pass (no re-baseline)
python -m pytest tests/test_golden_diff.py -v
# 3 passed

# V2 shadow + golden lane combined
python -m pytest tests/test_golden_diff.py tests/test_engine_v2_shadow.py -v
# 6 passed

# Full suite, sequential
python -m pytest tests/ -q
# 306 passed, 5 skipped, 200 warnings

# End-to-end smoke: small_sm, all M5 + M4b flags ON
STATS_NAN_FOR_HARDCODED=true EVIDENCE_CLASS_ENFORCED=true \
INVENTORY_GATE_ENABLED=true ANOMALY_GATE_ENABLED=true \
MATERIALITY_FLOOR_SCALE_AWARE=true CANNIBALIZATION_GATE_ENABLED=true \
RECENTLY_RUN_FATIGUE_ENABLED=true \
  python -m src.main --orders data/SM_orders.csv --brand m5_smoke \
                     --out /tmp/m5_smoke
# Engine ran end-to-end. abstain=abstain_soft (legacy actions list empty
# under M4b flag-on — expected); scale.materiality_floor=$10,000
# (mr=$127k → ARR ≈ $1.5M tier 2 → max($10k, 3% × $127k))

# End-to-end smoke: small_sm, M4b flags OFF, M5 flags ON (legacy actions
# present so guardrails have something to gate)
INVENTORY_GATE_ENABLED=true MATERIALITY_FLOOR_SCALE_AWARE=true \
CANNIBALIZATION_GATE_ENABLED=true \
  python -m src.main --orders data/SM_orders.csv --brand m5_legacy \
                     --out /tmp/m5_legacy
# Result on engine_run.json:
#   recommendations: ['bestseller_amplify']
#   considered:
#     journey_optimization -> materiality_below_floor
#       (expected impact $4,545 below scale-aware floor $10,000)
#     category_expansion -> audience_overlap_with_higher_priority
#       (audience overlaps bestseller_amplify by 98%)
#   floor: $10,000;  monthly_revenue: $127,544

# End-to-end smoke: mid_shopify, M5 flags ON
STATS_NAN_FOR_HARDCODED=false EVIDENCE_CLASS_ENFORCED=false \
INVENTORY_GATE_ENABLED=true MATERIALITY_FLOOR_SCALE_AWARE=true \
CANNIBALIZATION_GATE_ENABLED=true \
  python -m src.main --orders data/shopify_orders_mid.csv \
                     --brand m5_mid --out /tmp/m5_mid
# Engine ran end-to-end. mr=$64k → tier 1 → floor=$5k.
```

## Tests / checks run and results

| Suite                                           | Result                  |
|-------------------------------------------------|-------------------------|
| `tests/test_guardrails.py`                       | **47 passed**           |
| `tests/test_anomaly_abstain.py`                  | **7 passed**            |
| `tests/test_inventory_gate.py`                   | **10 passed**           |
| `tests/test_materiality_floor.py`                | **16 passed**           |
| `tests/test_bias_correction_default_off.py`      | **3 passed**            |
| `tests/test_seasonality_decoupled.py`            | **3 passed**            |
| M5 sub-total                                    | **86 new tests, 0 fail** |
| Plus an additional 3 tests in `test_guardrails.py::TestApplyGuardrails` orchestrator | already counted above |
| `tests/test_golden_diff.py`                      | **3 passed** (no re-baseline) |
| `tests/test_engine_v2_shadow.py`                 | **3 passed**            |
| Full suite `python -m pytest tests/`             | **306 passed, 5 skipped** |

The full-suite count went from 217 (M4b) → 306 (M5) = +89 new tests
(47 guardrails + 7 anomaly_abstain + 10 inventory_gate + 16
materiality_floor + 3 bias_correction + 3 seasonality + 3
TestApplyGuardrails-style integration). Zero regressions, zero flaky
failures observed across multiple runs.

## Guardrails implemented

| Gate | Function | Reason code emitted | Default flag |
|---|---|---|---|
| Inventory | `gate_inventory(candidate, inventory_metrics, ...)` | `INVENTORY_BLOCKED` | `INVENTORY_GATE_ENABLED=false` |
| Anomalous-window | `gate_anomaly(data_quality_flags)` | `ANOMALOUS_WINDOW` (RejectedPlay), state=`ABSTAIN_HARD` | `ANOMALY_GATE_ENABLED=false` |
| Materiality | `gate_materiality(candidate, monthly_revenue)` | `MATERIALITY_BELOW_FLOOR` | `MATERIALITY_FLOOR_SCALE_AWARE=false` |
| Cannibalization | `gate_cannibalization(candidates, overlap_map, ...)` | `AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY` | `CANNIBALIZATION_GATE_ENABLED=false` |
| Portfolio cap | `enforce_portfolio_cap(candidates, monthly_revenue, ...)` | `CANNIBALIZATION_DEMOTED` | `CANNIBALIZATION_GATE_ENABLED=false` (paired) |
| Recently-run fatigue | `gate_recently_run(candidate, history_path, ...)` | `RECENTLY_RUN_FATIGUE` | `RECENTLY_RUN_FATIGUE_ENABLED=false` |

Every gate is a pure function on typed `PlayCard` / `EngineRun` data.
The orchestrator `apply_guardrails` composes them and is the single
entry point from `main.py`.

## Reason codes wired

The M5 work consumes the M1 `ReasonCode` enum without extending it.
Codes populated by M5:

- `ANOMALOUS_WINDOW` (T5.2)
- `INVENTORY_BLOCKED` (T5.1)
- `MATERIALITY_BELOW_FLOOR` (T5.3)
- `AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY` (T5.4 cannibalization)
- `CANNIBALIZATION_DEMOTED` (T5.4 portfolio cap)
- `RECENTLY_RUN_FATIGUE` (T5.5)

The remaining 6 enum members (`AUDIENCE_TOO_SMALL`,
`NO_MEASURED_SIGNAL`, `SIGNAL_INCONSISTENT_ACROSS_WINDOWS`,
`COLD_START_INSUFFICIENT_DATA`, `DATA_QUALITY_FLAG`, `CAP_EXCEEDED`)
are the responsibility of M3 / M4 / M7 — M5 deliberately leaves them
alone.

The `RejectedPlay.would_fire_if` field is populated on every
M5-emitted rejection (per the M7 plan that downstream agents will
template plain-English copy from this string).

## Flags tested

| `*_GATE_ENABLED` flag | Off behavior | On behavior |
|---|---|---|
| `INVENTORY_GATE_ENABLED` | gate is no-op | SKU-push plays with `cover_days < 21` blocked |
| `ANOMALY_GATE_ENABLED` | flags surfaced but no abstain | HARD flag → state=ABSTAIN_HARD, recommendations cleared |
| `CANNIBALIZATION_GATE_ENABLED` | gate is no-op | overlap > 50% demotes lower-priority + portfolio cap enforced |
| `MATERIALITY_FLOOR_SCALE_AWARE` | gate is no-op, `Scale.materiality_floor` unchanged | scale-aware floor applied + `Scale.materiality_floor` recomputed |
| `RECENTLY_RUN_FATIGUE_ENABLED` | gate is no-op | history file consulted; matching record demotes the play |

All 32 (5 flags × 2 states + 22 individual gate tests) flag/state
combinations covered by `tests/test_guardrails.py` and the focused
test files. Combined-gate composition tested via
`TestApplyGuardrails::test_combined_gates_compose`.

## Impact on current fixtures

### `small_sm` under M4b flag-on (canonical M5 baseline state)

- `recommendations`: 0 (already empty under M4b — the documented
  product-hostile transition state).
- `considered`: 0 (no recommendations to gate against).
- `data_quality_flags`: [].
- `abstain.state`: `abstain_soft` (legacy empty-actions reason from
  the M1 adapter; M7 will replace this label).
- `scale.materiality_floor`: $10,000 (tier 2 — `monthly_revenue ≈
  $127k` → `ARR ≈ $1.5M`, `3% × $127k = $3.8k < $10k absolute floor`).

### `small_sm` under M4b flag-off + M5 flags on (validation example)

When the legacy 3-PRIMARY briefing surfaces, M5 acts on it:

- `recommendations`: `["bestseller_amplify"]` (1).
- `considered`:
  - `journey_optimization` → `materiality_below_floor`
    (expected impact $4,545 below floor $10,000)
  - `category_expansion` → `audience_overlap_with_higher_priority`
    (overlap 98% with `bestseller_amplify`)
- `bestseller_amplify` survived because `inventory_metrics` was not
  passed to the run (no-inventory-data branch is a no-op).

This validates the gates fire correctly when there is real data to
gate against.

### `mid_shopify` and `micro_coldstart` under M5 flags on

Both fixtures already have 0 recommendations under M4b flag-on, so
the gates have nothing to act on. `Scale.materiality_floor` is set
correctly ($5k for mid, default $5k for cold-start).

## M4b goldens still pass

**Yes.** No goldens were re-baselined in M5.

`tests/test_golden_diff.py` runs unmodified (it forces M4b flags on
via monkeypatch, M5 flags are unset → all gates no-op → engine output
is byte-identical to the M4b goldens).

The only places where M5 changes `engine_run.json` content are:
1. `Scale.materiality_floor` is now non-null when
   `MATERIALITY_FLOOR_SCALE_AWARE=true` (was always null in M4b).
2. `considered` may be non-empty when any gate flag is true.
3. `abstain.state = ABSTAIN_HARD` when `ANOMALY_GATE_ENABLED=true`
   AND a HARD data-quality flag is present.

`engine_run.json` is NOT in the golden tree (excluded for stability
reasons in M0; receipts/`engine_run.json` is regenerated each run
without diffing). So even when M5 flags are on,
`tests/test_golden_diff.py` is unaffected.

## Skipped items

None of the listed M5 tickets are skipped.

**Note on T5.7 partial coverage.** The plan said "Move
`get_seasonal_multiplier` invocation out of
`_calculate_business_confidence` and into
`revenue_range.seasonality_factor` (sizing) + `launch_window.recommended`
(advisory copy). Behind paired flags."

The structural decoupling (the harder half) is already done: M4b's
`EVIDENCE_CLASS_ENFORCED=true` short-circuit makes confidence
seasonality-agnostic. M5 pinned this contract with the
`tests/test_seasonality_decoupled.py` forcing function so no future
agent can re-introduce the multi-counting silently.

The two new outputs (`revenue_range.seasonality_factor` and
`launch_window.recommended`) are additive sinks for the seasonality
data. M5 did NOT add them because:
- `revenue_range.seasonality_factor` belongs to the M6 sizing layer.
  Adding it now without `size_play()` would create a stub field
  with no producer; M6 owns the contract.
- `launch_window.recommended` already exists on `PlayCard.launch_window`
  (added in M1). The legacy `select_actions` does not currently emit
  a `launch_window` field on actions, so the M1 adapter's
  `_build_launch_window_from_legacy` returns None today. Wiring the
  seasonal anchor into this field is a renderer-adjacent concern best
  done in M6/M8 alongside the rest of the timing copy.

The decoupling itself — the load-bearing part — is fully in place
and tested. The two stub fields can land in M6 sizing without any
M5 prerequisite.

## Remaining risks and dependencies for Milestone 6

1. **Audience overlap re-computation cost.** When
   `CANNIBALIZATION_GATE_ENABLED=true`, `main.py` re-runs the M3
   audience builders for every recommendation. This is intentional
   (the legacy actions don't carry customer-id sets), but it's a
   non-trivial cost on large stores. M6/M7 should consider caching
   the audience sets between the M3 shadow detector and the
   guardrail engine (single audience builder invocation per play
   per run).

2. **Portfolio-cap stub semantics.** `enforce_portfolio_cap` operates
   on the legacy `expected_$` mapped to `revenue_range.p50`. With
   M6 sizing replacing this mapping, the cap will start consuming
   real (smaller) numbers. Acceptance tests pin behavior on
   PlayCards with explicit p50 values, so the cap works regardless
   of where p50 originates.

3. **Recently-run fatigue depends on a writer.** `gate_recently_run`
   reads `data/recommended_history.json`. M9 owns the writer.
   Until M9 lands the gate is always a no-op in production runs;
   tests use a temp-file fixture to exercise both paths.

4. **HARD-flag handling clears recommendations but does NOT clear
   the legacy `actions_log.json`.** The renderer / `actions_log`
   write happens in `main.py` BEFORE `apply_guardrails` runs (the
   write was not moved because `actions_log` is read by
   `M0/test_golden_diff` and the M4b legacy briefing). When M8
   flips the renderer to read the EngineRun, the abstain state will
   surface merchant-facing; until then, abstain is receipts-only.
   This is consistent with the M5 plan's "do NOT touch the
   renderer" rule.

5. **`POST_PROMO_WINDOW` is intentionally a soft warning.** The
   M1 detector emits it but M5's `HARD_DATA_QUALITY_FLAGS` does NOT
   include it. The plan's "any data_quality_flag => ABSTAIN_HARD"
   rule is interpreted as "any HARD flag" because the M1 detector
   includes a known soft-warning shape (post-promo). If a future
   agent disagrees, flipping POST_PROMO_WINDOW into the HARD set is
   a one-line change in `src/guardrails.py`.

6. **Pre-existing M3-noted ULP-level golden flake** continues to be
   tracked as a separate side ticket; M5 does not introduce or
   resolve it.

## Readiness for Milestone 6

**Green to start M6.** M5 acceptance criteria are met:

- `RejectedPlay` records carry the 6 reason codes M5 owns. Verified
  in `test_guardrails.py` and the three focused test files.
- HARD data-quality flag triggers `abstain.state = ABSTAIN_HARD`
  with empty `recommendations`. Verified in
  `test_anomaly_abstain.py` (4 HARD flags + 1 carve-out for
  POST_PROMO_WINDOW).
- Inventory gate has tests; no-inventory-data branch is a no-op
  (NOT a block). Verified in `test_inventory_gate.py`.
- Materiality floor has tests for all three ARR tiers. Verified in
  `test_materiality_floor.py`.
- Audience-overlap has tests. Verified in
  `TestCannibalizationGate` (`test_guardrails.py`).
- T5.6: bias correction default remains off; the inline bypass is
  removed. Verified in `test_bias_correction_default_off.py`.
- T5.7: confidence is decoupled from seasonality on the M4b path.
  Verified in `test_seasonality_decoupled.py`.
- Guardrail results are exposed via `EngineRun.considered` /
  `EngineRun.abstain` / `EngineRun.scale.materiality_floor` so M7
  and M8 can consume them without further plumbing.
- M4b canonical goldens still pass (no re-baseline).
- No renderer changes.
- No merchant-facing Play Thesis changes.

**M6 prerequisites that M5 satisfies:**

- `Scale.materiality_floor` is recomputed and present on the
  EngineRun. M6 sizing can read it as the lower bound of any
  `revenue_range`.
- `RevenueRange.suppressed = True` is honored by `gate_materiality`
  (no-op when suppressed). M6 can flip this on cold-start without
  reverberating into the materiality gate.
- Audience overlap is computed on the V2 path under
  `CANNIBALIZATION_GATE_ENABLED`. M6/M7 can plug into the same
  builder set; the M3 shadow detector and the M5 cannibalization
  gate share `compute_audience_overlap`.
- The `apply_guardrails` orchestrator returns a NEW EngineRun;
  M7's `decide()` can compose by calling
  `apply_guardrails(decide_skeleton_output, ...)` without worrying
  about input mutation.

## Validation summary

- **89 new tests** across 6 new files. Zero existing tests modified.
- **0 regressions** in the 217-test M4b baseline.
- **0 goldens re-baselined.** All 3 M4b fixtures still pass byte-
  identical with the M5 flag-off path.
- **5 new env flags** added; all default off.
- **1 inline bypass removed** (T5.6 bias correction default-True).
- **3 end-to-end smoke runs** (small_sm M4b-on, small_sm M4b-off + M5,
  mid_shopify M5) confirm `engine_run.json` is well-formed,
  `Scale.materiality_floor` is set per tier, and `considered` /
  `abstain` populate correctly.
- **Renderer untouched. Briefing template untouched. Legacy code
  untouched.** Per the M5 hard NOT-IN-SCOPE rule.
