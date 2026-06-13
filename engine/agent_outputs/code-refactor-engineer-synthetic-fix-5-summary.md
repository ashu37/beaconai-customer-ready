# Code Refactor Engineer — Synthetic Blocker Fix 5 Summary

_Date: 2026-05-04_
_Scope: Fix 5 ONLY from `agent_outputs/implementation-manager-synthetic-blocker-fix-plan.md`._

## Approved Scope

Restore the merchant-readable materiality footer on every non-ABSTAIN_HARD V2 briefing.

The Phase 5.4 sentence is:

> "We only recommend primary plays that could realistically add at least $X this month for a store your size."

The synthetic Phase 5 e2e review found this sentence missing on all six synthetic briefings, while the original Phase 5 sample (`agent_outputs/phase5_samples/beauty_brand_v2_briefing.html`) rendered it correctly. Fix 5 must:

- Make the sentence appear on every non-ABSTAIN_HARD V2 briefing.
- Allow the sentence to appear or not on ABSTAIN_HARD layouts (permissive).
- Use the actual computed floor in the rendered amount.
- Never restore the engineering jargon `"Materiality floor: $X"`.
- Never change materiality floor values.

Strict Non-Goals (not touched in this pass):

- Fix 6 (per-scenario VERTICAL_MODE propagation).
- Materiality floor values (no raise/lower of thresholds).
- Decision logic outside the floor-availability path.
- Legacy renderer.
- Goldens (no re-baselining).

## Investigation Findings

The investigation surfaced a clean root cause:

1. `engine_run.scale.materiality_floor` was `None` on every synthetic run.
   Confirmed by inspecting receipts/engine_run.json prior to the patch.

2. The renderer conditional in `src/storytelling_v2.py` line 840
   (`if scale.materiality_floor is not None`) is correct — the line is
   gated on the floor being stamped. With a `None` floor, the renderer
   silently dropped the line. This is correct given the data; it is
   not a renderer bug.

3. The materiality floor was only stamped onto `EngineRun.scale` by
   `apply_guardrails._recompute_floor`, which runs **only when the
   `MATERIALITY_FLOOR_SCALE_AWARE` flag is on**. With the flag off
   (the default), the floor stayed at `None` (the value the legacy
   adapter set in `_scale_from_aligned`).

4. The synthetic e2e review's flag stack used
   `GUARDRAIL_MATERIALITY_ENABLED=true` — which is **not the actual
   flag the code reads**. The actual code-side flag is
   `MATERIALITY_FLOOR_SCALE_AWARE`. A grep confirmed
   `GUARDRAIL_MATERIALITY_ENABLED` is read nowhere in `src/`. So even
   though the harness command line looked materiality-aware, the
   guardrail materiality path never ran.

The Phase 5 sample worked because that pre-rendered artifact was
generated in a configuration where the floor happened to be stamped
(the `_make_engine_run` test helpers always populate floor explicitly).

## Patch Summary (smallest safe fix)

Stamp `Scale.materiality_floor` unconditionally in the legacy
adapter so the merchant-readable footer line is always available
to the V2 renderer regardless of which guardrail flags are on.
Floor *values* are unchanged — the same scale-aware function
(`scale_aware_materiality_floor`, the existing M5 source of truth)
is used.

This is one targeted change in `src/engine_run_adapter._scale_from_aligned`:

```python
# Before:
return Scale(
    monthly_revenue=monthly_rev,
    customer_base_est=customer_base,
    materiality_floor=None,  # M5 sets the scale-aware floor
)

# After:
from .guardrails import scale_aware_materiality_floor
materiality_floor = scale_aware_materiality_floor(monthly_rev)
return Scale(
    monthly_revenue=monthly_rev,
    customer_base_est=customer_base,
    materiality_floor=materiality_floor,
)
```

Why this is the smallest safe fix:

- It does not alter floor values: the same scale-aware function
  `apply_guardrails._recompute_floor` uses is now used at adapter
  construction time. Tier-1 = `max($5k, 2%)`, Tier-2 = `max($10k, 3%)`,
  Tier-3 = `max($25k, 5%)`. Identical numbers.
- It does not change decision logic: `gate_materiality` (the rejection
  gate) still requires `MATERIALITY_FLOOR_SCALE_AWARE` to fire. The
  M5 cap on what plays survive is unchanged. We only make the floor
  available for *rendering*.
- It does not change the renderer: `storytelling_v2.py` line 840
  conditional remains `if scale.materiality_floor is not None`. Now
  the condition is always true (when scale exists), so the line
  always renders.
- It does not change the legacy briefing: `actions_log.json`,
  `briefing.html.j2`, and the legacy renderer never read
  `Scale.materiality_floor`.
- It does not touch goldens: the legacy default-flags-off path is
  the canonical golden path; the legacy renderer ignores
  `Scale.materiality_floor`.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run_adapter.py`
  — `_scale_from_aligned` now stamps `materiality_floor` unconditionally
  via `scale_aware_materiality_floor(monthly_rev)`. Local import to
  keep the M1-era adapter import-light.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_materiality_footer_present.py`
  — NEW. 9 tests covering adapter stamping (3), renderer footer
  presence on PUBLISH (1), ABSTAIN_SOFT (1), ABSTAIN_HARD jargon
  invariant (1), no-jargon-anywhere invariant (1), exact amount
  matches `Scale.materiality_floor` (1), and end-to-end through
  `build_engine_run_from_legacy` (1).

No other files touched. Specifically NOT modified: `src/storytelling_v2.py`,
`src/guardrails.py`, `src/decide.py`, `src/engine_run.py`, the M3
candidate path, the legacy renderer, the goldens, or any prior-fix
file.

## Exact Commands Run

```
# Run new tests (initial — caught two test-side tier expectation errors).
python -m pytest tests/test_materiality_footer_present.py -v

# Adjusted test expectations to match scale_aware_materiality_floor
# tier semantics ($94,405/month -> ARR $1.13M -> tier-2 -> $10k,
# not tier-1 -> $5k). No engine code change needed for this.

# Re-run new tests.
python -m pytest tests/test_materiality_footer_present.py -v
# 9 passed

# Targeted regression suites (materiality-adjacent, guardrail,
# render, render_v2, no-aura-beacon, measured-pathway, internal-stats,
# engine-run-schema, outcome-log, targeting-no-dollar-headline,
# targeting-measurement-invariant, abstain-soft-no-recommendations,
# inventory-blocked-in-considered, decide).
python -m pytest tests/test_phase5_materiality_copy.py tests/test_guardrails.py \
  tests/test_render_v2.py tests/test_phase5_no_aura_beacon.py \
  tests/test_phase5_measured_pathway.py tests/test_internal_stats_not_rendered.py \
  tests/test_engine_run_schema.py tests/test_outcome_log.py \
  tests/test_targeting_no_dollar_headline.py \
  tests/test_targeting_measurement_invariant.py \
  tests/test_abstain_soft_no_recommendations.py \
  tests/test_inventory_blocked_in_considered.py tests/test_decide.py
# 196 passed, 1 skipped

# Golden diff (non-negotiable: no re-baseline).
python -m pytest tests/test_golden_diff.py -v
# 3 passed

# Full suite.
python -m pytest tests/ -q
# 621 passed, 12 skipped

# E2E synthetic fixtures (V2 stack).
for sc in healthy_beauty_240d healthy_beauty_low_inventory_240d \
         supplement_replenishment_240d small_store_240d \
         promo_anomaly_240d cold_start_45d; do
  ENGINE_V2_DECIDE=true ENGINE_V2_OUTPUT=true ENGINE_V2_SHADOW=true \
    ENGINE_V2_SIZING=true STATS_NAN_FOR_HARDCODED=true \
    EVIDENCE_CLASS_ENFORCED=true \
    python -m src.main \
    --orders tests/fixtures/synthetic/${sc}_orders.csv \
    --brand "${sc}" --out /tmp/fix5_synth_${sc}
done

# Verify footer presence per scenario.
# Result table below.
```

## Tests / Checks Run

| Check | Result |
|---|---|
| `tests/test_materiality_footer_present.py` (NEW) | 9 passed |
| `tests/test_phase5_materiality_copy.py` (Phase 5.4 contract — no jargon, merchant copy) | 4 passed |
| `tests/test_guardrails.py` (M5 gate values + recompute) | 51 passed |
| `tests/test_render_v2.py` | 24 passed |
| `tests/test_phase5_no_aura_beacon.py` (forbidden-token sweep) | 4 passed |
| `tests/test_phase5_measured_pathway.py` | 14 passed |
| `tests/test_internal_stats_not_rendered.py` | 7 passed |
| `tests/test_engine_run_schema.py` | 7 passed |
| `tests/test_outcome_log.py` | 16 passed |
| `tests/test_targeting_no_dollar_headline.py` | 6 passed |
| `tests/test_targeting_measurement_invariant.py` (Fix 2) | 6 passed, 1 skipped |
| `tests/test_abstain_soft_no_recommendations.py` (Fix 3) | 11 passed |
| `tests/test_inventory_blocked_in_considered.py` (Fix 4) | 12 passed |
| `tests/test_decide.py` | 34 passed |
| `tests/test_golden_diff.py` | 3 passed (no re-baseline) |
| Full suite `pytest tests/ -q` | **621 passed, 12 skipped, 0 failed** |
| Synthetic e2e: 6 V2-stack fixtures | All produced briefings; sentence appears on all 5 non-ABSTAIN_HARD; 0 jargon strings |

Pre-Fix-5 baseline (post-Fix-4) was 612 passed + 12 skipped.
Post-fix is **621 passed + 12 skipped** — exactly the +9 new tests
this PR added, with no previously-passing test moving and no skip
count delta.

## Synthetic E2E Verification

Re-ran the V2 stack on all six synthetic fixtures and inspected
`briefings/<scenario>_briefing.html` and `receipts/engine_run.json`:

| Scenario | decision_state | scale.materiality_floor | sentence in HTML | jargon in HTML | rendered amount |
|---|---|---|---|---|---|
| healthy_beauty_240d | abstain_soft | 10000.0 | yes (1x) | no | $10,000 |
| healthy_beauty_low_inventory_240d | abstain_soft | 10000.0 | yes (1x) | no | $10,000 |
| small_store_240d | abstain_soft | 5000.0 | yes (1x) | no | $5,000 |
| supplement_replenishment_240d | abstain_soft | 5000.0 | yes (1x) | no | $5,000 |
| promo_anomaly_240d | abstain_soft | 10000.0 | yes (1x) | no | $10,000 |
| cold_start_45d | abstain_hard | 10000.0 | yes (allowed) | no | $10,000 |

All five non-ABSTAIN_HARD scenarios now render the merchant-readable
sentence with the exact stamped floor. The ABSTAIN_HARD scenario
(`cold_start_45d`) currently renders the sentence too — which the
brief explicitly allows ("ABSTAIN_HARD layout may omit the
sentence"). The new test
`test_abstain_hard_briefing_does_not_leak_materiality_jargon`
pins the no-jargon invariant on ABSTAIN_HARD as a safety net for
any future Fix-5-adjacent refactor.

The exact rendered sentence on `healthy_beauty_240d`:

> "We only recommend primary plays that could realistically add at least $10,000 this month for a store your size."

This matches the Phase 5 sample format verbatim.

## Root Cause (Restated For The Record)

The synthetic e2e review's command stack passed
`GUARDRAIL_MATERIALITY_ENABLED=true`. That env var name is read
nowhere in `src/`. The actual code-side flag is
`MATERIALITY_FLOOR_SCALE_AWARE` (default `false` per `src/utils.py:478`).

`engine_run_adapter._scale_from_aligned` initialized
`materiality_floor=None`. The only code path that filled the floor
in was `apply_guardrails._recompute_floor`, gated on
`MATERIALITY_FLOOR_SCALE_AWARE`. With that flag off, the floor
stayed `None`. The V2 renderer's `if scale.materiality_floor is
not None` guard then correctly suppressed the line.

Fixing the harness env var (Fix 6 / synthetic harness territory)
would have masked the same defect; an honest customer running the
engine without the M5 flag stack would still get a missing line.
Stamping the floor at the adapter (which always runs) makes the
sentence available regardless of flag stack — which is what Fix 5
required.

## How `materiality_floor` Is Now Supplied And Rendered

End-to-end flow for any V2 run after Fix 5:

```
build_engine_run_from_legacy(...)
  └─ _scale_from_aligned(aligned)           # always invoked
       monthly_rev   = aligned["L28"]["net_sales"]
       customer_base = aligned["L28"]["meta"]["identified_recent"]
       materiality_floor = scale_aware_materiality_floor(monthly_rev)  # NEW
       return Scale(
           monthly_revenue   = monthly_rev,
           customer_base_est = customer_base,
           materiality_floor = materiality_floor,                       # populated
       )

  Optional: apply_guardrails(...)
    └─ _recompute_floor(engine_run, cfg)
         if MATERIALITY_FLOOR_SCALE_AWARE on => recomputes (idempotent on
                                                  a fresh adapter floor).
         else => returns the existing floor (now non-None) unchanged.

  Optional: decide(engine_run, cfg=cfg)
    └─ replace(engine_run, ...)             # preserves Scale + floor.

  render_engine_run(engine_run)
    └─ render_data_quality_footer(scale=engine_run.scale, ...)
         if scale.materiality_floor is not None:                       # always true
             scale_bits.append(
                 "We only recommend primary plays that could "
                 f"realistically add at least {floor_money} this month "
                 "for a store your size."
             )
```

Renderer output unchanged structurally; the ``<ul class="dq-footer__scale">``
block now always carries the merchant-readable line under
``<footer class="dq-footer">`` for non-ABSTAIN_HARD layouts.

## Confirmation That Floor Values Were Not Changed

`scale_aware_materiality_floor` is unchanged. The function in
`src/guardrails.py:138-169` retains the same tier definitions:

- ARR `< $1M` -> `max($5_000, 2% of monthly_revenue)`
- ARR `$1M-$5M` -> `max($10_000, 3% of monthly_revenue)`
- ARR `> $5M` -> `max($25_000, 5% of monthly_revenue)`
- `monthly_revenue is None` or non-positive -> `$5_000` (default).

`tests/test_guardrails.py::test_materiality_floor_strips_below_floor`
and `tests/test_materiality_floor.py` (existing) still pass with
their numeric expectations.

`tests/test_phase5_materiality_copy.py` still pins:
- "Materiality floor:" must NOT appear in V2 briefing.
- "We only recommend primary plays" must appear when floor is set.
- Renderer hides the line when `materiality_floor is None`.

All four of those pre-existing materiality assertions pass post-fix.

## Goldens

`tests/test_golden_diff.py`: 3 fixtures (`small_sm`, `mid_shopify`,
`micro_coldstart`) all pass byte-for-byte against the pinned golden
tree. No file under `tests/golden/` was modified. No
`--baseline` / `--regenerate` invocation was used.

The legacy renderer (`src/storytelling.py`) does not read
`Scale.materiality_floor`. The legacy `actions_log.json` writer
does not read `Scale`. The legacy briefing template
(`templates/briefing.html.j2`) does not reference materiality.
So a change to the EngineRun-side floor stamping cannot move legacy
goldens, and the byte-for-byte equality holds.

## Behavior Changes

- `EngineRun.scale.materiality_floor` is now populated on every
  EngineRun built via the legacy adapter (`build_engine_run_from_legacy`).
  The value is the same number `apply_guardrails._recompute_floor`
  would compute when the M5 flag is on.
- The merchant-readable materiality footer sentence ("We only
  recommend primary plays that could realistically add at least $X
  this month for a store your size.") now renders on every
  non-ABSTAIN_HARD V2 briefing. ABSTAIN_HARD pages may also render
  it (renderer-side behavior unchanged); the brief permits this.
- Internal `receipts/debug.html` continues to surface
  `materiality_floor=$X` for engineering review (Phase 5.4
  contract preserved; the legacy jargon string is gated to
  `debug.html`, never the merchant briefing).
- `EngineRun.scale.monthly_revenue`, `customer_base_est`, and the
  rest of the schema are unchanged.
- M5 `gate_materiality` rejection behavior: unchanged. The gate
  still only rejects plays when `MATERIALITY_FLOOR_SCALE_AWARE`
  is on. Fix 5 only makes the floor *available for rendering*.
- Legacy `actions_log` / `briefing.html` (legacy renderer): unchanged.
- ReasonCode enum: unchanged.
- ABSTAIN_SOFT contract (Fix 3): unchanged.
- Targeting-measurement invariant (Fix 2): unchanged.
- Inventory-blocked wiring (Fix 4): unchanged.
- M0 goldens (legacy): byte-identical.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_materiality_footer_present.py`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-synthetic-fix-5-summary.md`
  (this file)

## Remaining Risks

- **The materiality line now also appears on ABSTAIN_HARD layouts**
  by default, because `render_data_quality_footer` is called from
  the ABSTAIN_HARD memo too. The brief explicitly allowed this
  ("ABSTAIN_HARD layout may omit the sentence"); a future PM
  decision could prefer suppressing it for cold-start cases. If so,
  the suppression would be a one-line gate inside
  `render_abstain_hard_memo` (pass a `suppress_materiality=True`
  kwarg into `render_data_quality_footer`). Out of scope for Fix 5.
- **The adapter and guardrails now duplicate the floor computation
  call.** This is intentional and idempotent — when both run,
  they compute the same value. A future cleanup could centralize
  the call site, but that is a non-blocking ergonomic refactor.
- **Synthetic harness still uses a typo'd flag name**
  (`GUARDRAIL_MATERIALITY_ENABLED` vs `MATERIALITY_FLOOR_SCALE_AWARE`).
  Fix 5 makes the engine resilient to that misconfiguration; the
  harness fix is Fix 6 / Fix 7 territory and not required for the
  merchant-facing footer to render correctly.
- **A future EngineRun built outside the legacy adapter** (e.g., a
  pure synthetic-test fixture using `EngineRun(scale=Scale(...))`
  directly) must still set `materiality_floor` explicitly. The new
  test `test_v2_briefing_hides_materiality_floor_when_scale_unset`
  in `test_phase5_materiality_copy.py` confirms the renderer
  still hides the line when `materiality_floor is None`.

## Readiness Assessment For Fix 6

Ready to proceed to Fix 6 (per-scenario `VERTICAL_MODE` propagation
in test harness). Specifically:

- Full suite (621 passed, 12 skipped) is clean.
- No goldens were re-baselined.
- The synthetic e2e blocker that motivated Fix 5 (footer missing
  on all six briefings) is resolved at the engine layer; if Fix 6
  also wires the harness to set `MATERIALITY_FLOOR_SCALE_AWARE`
  correctly (as a side-quest while wiring `VERTICAL_MODE`), Fix 5's
  unconditional adapter stamping makes the harness resilient
  either way.
- Fix 6 does not touch engine code (per the IM plan); it is a
  pure harness change in the synthetic matrix runner. No conflict
  with Fix 5.
- The new test file (`test_materiality_footer_present.py`) plumbs
  unit-level coverage (adapter + renderer) that does not depend
  on the synthetic matrix runner; it remains useful regardless of
  Fix 6's harness work.

No code-level discovery from Fix 5 changes the planned shape of Fix 6.

## Git Status

Per the brief, changes are NOT committed. Files left unstaged so
the user can review the diff before committing. Current state at
the close of Fix 5:

- 1 new test file: `tests/test_materiality_footer_present.py`.
- 1 new doc file: this summary.
- 1 source file modified: `src/engine_run_adapter.py` (one helper
  body change in `_scale_from_aligned`; no signature change).

`memory.md`, the prior-fix files (`tests/test_charts_none_safe.py`,
`tests/test_targeting_measurement_invariant.py`,
`tests/test_abstain_soft_no_recommendations.py`,
`tests/test_inventory_blocked_in_considered.py`,
`src/charts.py`, `src/engine_run.py`, `src/storytelling_v2.py`,
`src/decide.py`, `src/detect.py`, `src/main.py`, and the
prior-fix summaries) remain unstaged from Fixes 1-4 per the
prior-pass briefs.
