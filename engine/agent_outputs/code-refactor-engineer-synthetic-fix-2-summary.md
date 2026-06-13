# Code Refactor Engineer — Synthetic Blocker Fix 2 Summary

_Date: 2026-05-04_
_Scope: Fix 2 ONLY from `agent_outputs/implementation-manager-synthetic-blocker-fix-plan.md`._

## Approved Scope

Targeting-measurement invariant: any `PlayCard` whose `evidence_class == "targeting"` MUST have `measurement is None` structurally on `EngineRun` / receipts, not merely hidden at render time. Enforce at the legacy adapter terminal step (`_action_to_play_card`). Land structural tests first (TDD), watch them fail, then ship the post-hoc clear with assertion.

Strict Non-Goals (not touched in this pass):
- Fix 3 / Fix 4 / Fix 5 / Fix 6 / Fix 7.
- ABSTAIN_SOFT behavior (Fix 3 owns it).
- Renderer behavior.
- Materiality floors.
- Recommendation tiers.
- Goldens — no re-baselining.
- `p` / `q` / CI / `confidence` / `final_score` exposure.
- M3 Candidate contract.
- `measurement_builder._SUPPORTED` map.

## Patch Summary

The leak path the synthetic Phase 5 e2e review surfaced:

- A legacy action enters the adapter with populated `p` / `effect_abs` / `n` / `ci_low` / `ci_high` etc., but WITHOUT an `evidence_class` field on the action dict.
- `_coerce_evidence(None)` defaults the PlayCard to `EvidenceClass.TARGETING`.
- `_build_measurement_from_legacy(action)` only short-circuits when `str(action.get("evidence_class") or "").lower() == "targeting"`. With no stamp, that check is falsy (empty string), so it builds a full `Measurement` carrying saturated `p_internal` (e.g., the `promo_anomaly` fixture's 1.6e-72).
- The resulting PlayCard has `evidence_class=TARGETING` AND a non-null `Measurement` — the invariant is violated on receipts even though M8 hides it from the merchant briefing.

Fix: post-hoc clear with assertion at the terminal `_action_to_play_card` step. After the PlayCard is constructed, if `evidence_class == TARGETING`, set `measurement = None` and `assert card.measurement is None`. This closes the gap regardless of upstream stamping behavior, because every legacy candidate funnels through this single seam on its way to `EngineRun.recommendations[]`.

The `_build_measurement_from_legacy` early-return at line 112 is left in place; the post-hoc clear is additive and reinforces the invariant defensively, per the plan's preferred "post-hoc clear with assertion".

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run_adapter.py` — invariant enforcement added in `_action_to_play_card` (lines 219-246; the post-hoc clear with `assert`).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_targeting_measurement_invariant.py` — NEW. 6 unit tests (1 leak-path repro, 1 explicit-stamp pin, 2 negative tests for measured/directional, 1 end-to-end through `build_engine_run_from_legacy`, 1 defensive direct-construction repro) + 1 matrix-wide regression test (skipped — see below).

No other files touched. `measurement_builder.py`, `decide.py`, `storytelling_v2.py`, `evidence.py`, the M3 Candidate path, and `engine_run.py` schema were intentionally not modified.

## Exact Commands Run

```
python -m pytest tests/test_targeting_measurement_invariant.py -v        # pre-fix: 3 failed, 3 passed, 1 skipped
# (apply src/engine_run_adapter.py patch)
python -m pytest tests/test_targeting_measurement_invariant.py -v        # post-fix: 6 passed, 1 skipped
python -m pytest tests/test_targeting_no_dollar_headline.py tests/test_golden_diff.py -v
python -m pytest tests/test_phase5_abstain_copy.py tests/test_render_v2.py tests/test_phase5_measured_pathway.py tests/test_phase5_1_opportunity_context.py tests/test_internal_stats_not_rendered.py tests/test_engine_run_schema.py -q
python -m pytest tests/
mkdir -p /tmp/fix2_smoke
python -m src.main --orders data/SM_orders.csv --brand fix2_smoke --out /tmp/fix2_smoke
# Inline inspection of /tmp/fix2_smoke/receipts/engine_run.json for leak count.
```

## Tests / Checks Run

| Check | Result |
|---|---|
| `tests/test_targeting_measurement_invariant.py` (new) — pre-fix | 3 FAILED, 3 passed, 1 skipped (failure pinned the leak) |
| `tests/test_targeting_measurement_invariant.py` (new) — post-fix | 6 passed, 1 skipped |
| `tests/test_targeting_no_dollar_headline.py` | 6 passed |
| `tests/test_golden_diff.py` | 3 passed (no goldens re-baselined) |
| V2 / forbidden-string / engine-run-schema cluster | 80 passed |
| Full suite `pytest tests/` | 589 passed, 12 skipped, 0 failed |
| Smoke run on `data/SM_orders.csv` | Briefing produced; receipts/engine_run.json shows 3 targeting recommendations, 0 leaks |

Pre-Fix-2 baseline (from Fix 1 summary) was 583 passed + 11 skipped. Post-fix is 589 passed + 12 skipped — exactly the +6 unit tests + 1 matrix-skip that Fix 2 added. No previously-passing test moved.

## Did The New Test FAIL Before The Fix?

Yes. Captured failure summary from the pre-fix run:

```
FAILED tests/test_targeting_measurement_invariant.py::test_action_to_play_card_clears_measurement_when_targeting_no_evidence_stamp
FAILED tests/test_targeting_measurement_invariant.py::test_build_engine_run_targeting_recommendations_have_no_measurement
FAILED tests/test_targeting_measurement_invariant.py::test_terminal_adapter_clears_measurement_on_pre_built_targeting_card
==================== 3 failed, 3 passed, 1 skipped in 0.61s ====================
```

Excerpt of the pinned failure for `test_terminal_adapter_clears_measurement_on_pre_built_targeting_card` (matches the `promo_anomaly` synthetic fixture's saturated `p_internal`):

```
AssertionError: Adapter terminal step must structurally clear measurement on
targeting cards. Found: Measurement(metric=None, observed_effect=None, n=1234,
primary_window=None, consistency_across_windows=None, p_internal=1.6e-72,
ci_internal=None)
```

Excerpt for the end-to-end leak via `build_engine_run_from_legacy`:

```
AssertionError: PlayCard 'leaky_targeting' violates the targeting-measurement
invariant: evidence_class=TARGETING but
measurement=Measurement(metric='saturated', observed_effect=0.05, n=200,
primary_window='L28', consistency_across_windows=None, p_internal=0.0,
ci_internal=None).
```

The 3 negative-control tests (`test_action_to_play_card_explicit_targeting_stamp_keeps_measurement_none`, `test_action_to_play_card_measured_keeps_measurement`, `test_action_to_play_card_directional_keeps_measurement`) passed both before and after the fix, confirming the structural clear does not over-fire onto measured/directional cards or break the existing explicit-stamp early-return path.

## Where The Invariant Is Enforced

`/Users/atul.jena/Projects/Personal/beaconai/src/engine_run_adapter.py`, function `_action_to_play_card`, lines 219-246. Excerpt:

```python
# Synthetic Blocker Fix 2: targeting-measurement structural invariant.
# ...
if card.evidence_class == EvidenceClass.TARGETING:
    card.measurement = None
    assert card.measurement is None, (
        "Targeting PlayCard structural invariant violated for play_id="
        f"{card.play_id!r}: measurement must be None after the "
        "post-hoc clear. This indicates a programming error in the "
        "adapter terminal step."
    )
return card
```

This is the canonical legacy → EngineRun seam. Every PlayCard in `EngineRun.recommendations[]` produced by `build_engine_run_from_legacy` flows through this function. The M3-derived V2 path produces directional cards via `measurement_builder.py`, which never assigns `evidence_class=TARGETING` with a measurement (the `_SUPPORTED` map only contains directional plays); that path remains untouched per the Non-Goals.

## Proof That Targeting Measurement Is None After The Fix

1. Unit-level — `tests/test_targeting_measurement_invariant.py::test_action_to_play_card_clears_measurement_when_targeting_no_evidence_stamp` constructs the exact leak shape (no `evidence_class` stamp, populated `p=1.6e-72`, `effect_abs=0.0`, `n=1234`, `ci_low=0.0`, `ci_high=0.0`, `consistency_across_windows=3`). After the fix the assertion `card.measurement is None` passes.

2. End-to-end via the adapter — `tests/test_targeting_measurement_invariant.py::test_build_engine_run_targeting_recommendations_have_no_measurement` puts two leak-shaped actions through `build_engine_run_from_legacy(...)` and walks `EngineRun.recommendations[]`. Every targeting PlayCard has `measurement is None`.

3. Smoke run on a real fixture — ran `python -m src.main --orders data/SM_orders.csv --brand fix2_smoke --out /tmp/fix2_smoke`, then inline-inspected `receipts/engine_run.json`:

```
Targeting cards in receipts: 3
Considered targeting cards: 0
Total recommendations: 3
Leak count: 0
OK: no targeting card carries non-null measurement.
```

The 3 targeting cards small_sm produces are all structurally measurement-clean on the EngineRun receipts after Fix 2.

## Goldens

`tests/test_golden_diff.py` passed: 3 fixtures (`small_sm`, `mid_shopify`, `micro_coldstart`) all match the pinned golden tree byte-for-byte. No file under `tests/golden/` was modified. No `--baseline` / `--regenerate` invocation was used.

The legacy `actions_log.json` writer reads from the legacy `actions_bundle`, which the adapter does not mutate; the EngineRun-side post-hoc clear cannot affect legacy output. The legacy default-flags-off renderer remains the canonical path for the goldens.

## Skipped Matrix-Wide Test (And Why)

`tests/test_targeting_measurement_invariant.py::test_matrix_no_targeting_with_measurement` is skipped with the reason:

> No synthetic-matrix engine_run.json artifacts on disk yet (Fix 6/7 will produce them). Unit tests in this file pin the invariant at the adapter level in the meantime.

I searched for durable per-scenario `engine_run.json` files under `tests/fixtures/synthetic_runs/` and `tests/fixtures/synthetic/` — none exist in the repo (the synthetic matrix runner is what Fix 7 rewrites and what produces those artifacts). Per the plan: _"the matrix-wide regression test depends on the matrix runner producing engine_run.json for each fixture; this lands after Fix 7 (reporter / harness has been rewritten and the matrix is honest), but the unit test alone can land before Fix 7 and is enough to validate the engine-level fix."_

The matrix-wide test is in place and will activate automatically once Fix 7 produces the artifacts (no test-file edit will be required at that point). The unit-level guarantee is sufficient for the engine-level invariant: `_action_to_play_card` is the only seam through which legacy candidates become PlayCards on `EngineRun.recommendations[]`, so a passing unit test mathematically forecloses the leak on all matrix scenarios produced by the legacy adapter.

## Behavior Changes

- `EngineRun.recommendations[]` PlayCards with `evidence_class == TARGETING` now have `measurement = None` on receipts, regardless of whether the upstream legacy action carried `p` / `effect_abs` / CI / consistency fields.
- Internal receipts (`engine_run.json`, `debug.html`, outcome log) for those cards no longer carry a saturated `p_internal` or any other measurement field.
- Renderer behavior unchanged — M8 was already hiding measurement on targeting cards; this fix removes it structurally upstream.
- Decide / abstain / Considered list / Watching / sizing / materiality logic unchanged.
- Default-flags-off path on the M0 goldens: byte-identical.
- Measured / directional PlayCards: untouched. Their Measurement objects continue to round-trip end-to-end (verified by `test_measurement_persistence.py` and the negative-control tests in this PR).

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_targeting_measurement_invariant.py`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-synthetic-fix-2-summary.md` (this file)

## Remaining Risks

- **No Fix-3-side enforcement yet.** Under ABSTAIN_SOFT, the current `decide()` may still leave 2 targeting cards in `recommendations[]` (Fix 3 will set `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 0` and route them to Considered). Those cards are structurally measurement-clean after Fix 2, so the leak is closed; but the contradictory page (ABSTAIN_SOFT callout + 2 Recommended cards) is a separate Fix-3 concern.
- **Matrix-wide test is dormant until Fix 7.** It will activate on its own as soon as Fix 7's reporter produces durable per-scenario `engine_run.json` files. Fix 2 does not write those files.
- **The post-hoc clear is silently destructive.** If, in some future refactor, a directional or measured card is mis-stamped as TARGETING upstream, this clear will erase its Measurement and the engine will not raise (the `assert` only fires after the clear). The intentional choice — per the plan: _"acceptable degraded form per DS: ship post-hoc clear alone if the M3 early-return guard is more than a few lines"_ — is to coerce rather than raise on a wrong-class arrival, because raising at this seam would block the legacy CSV → HTML workflow on any regression. The classifier (`evidence.py` + M4b reclassification list) is the upstream forcing function for correct stamping.
- **`measurement_builder` not touched.** Per Non-Goals. The Phase 5.6 directional pathway is unaffected; targeting cards never arrive from that path because `_SUPPORTED` only contains directional plays.

## Readiness Assessment For Fix 3

Ready. Specifically:

- Full suite (589 passed, 12 skipped) is clean, so Fix 3's `tests/test_abstain_soft_no_recommendations.py` can land against a known-green baseline.
- `decide()` and `storytelling_v2.MAX_ABSTAIN_SOFT_TARGETING_CARDS` are untouched by Fix 2; Fix 3 will modify them as the plan specifies.
- Legacy goldens still pass; Fix 3's contract change is V2-side only and should not affect the M0 byte-identical goldens.
- The M3 Candidate contract is intact, the renderer is intact, and the materiality floor is unchanged — all explicit Fix-3 preconditions are satisfied.
- The new structural invariant in this PR is compatible with Fix 3's plan: when Fix 3 routes held targeting cards into `engine_run.considered`, the structural rule that targeting cards have `measurement is None` continues to hold (`considered` carries `RejectedPlay`, which has no `measurement` field, and recommendations created by the adapter are already clean).

No code-level discovery from Fix 2 changes the planned shape of Fix 3.
