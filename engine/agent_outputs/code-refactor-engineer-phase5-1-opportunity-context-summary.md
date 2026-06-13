# Phase 5.1 Opportunity Context Summary

_Completed: 2026-05-03 (engine-rework branch)_

## Approved scope

Small additive Phase 5.1 follow-up to the BeaconAI decision-core
overhaul (Phase 5 landed in commit cc06c8d). Goal: make V2 recommended
plays more commercially useful by showing **addressable opportunity
context** on cards where `revenue_range.suppressed=true`, without
claiming projected lift.

The block must show:
- audience size,
- recent AOV,
- addressable value = audience_size x recent AOV,
- explicit "not projected lift" disclaimer.

This is a contained additive change to V2 recommended-card rendering
only. No decision-logic changes. No V2 default flip. No causal priors.
No fake projections. `revenue_range.suppressed` remains true on the
Phase 5.6 directional card.

## Files changed

New files:
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_phase5_1_opportunity_context.py`
  - 20 tests covering: typed contract, render-block presence,
    not-projected-lift disclaimer, body-copy structure (not headline),
    AOV-missing fallback, suppressed-only render rule, forbidden
    tokens absent, forecast-term absent, revenue-range suppression
    preserved, range-chip absent, targeting-card invariant preserved,
    rounding helper at three magnitude bands plus bad-input handling,
    EngineRun round-trip preservation.

Edited files:
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py`
  - Added `OpportunityContext` dataclass with typed fields:
    `audience_size: int`, `aov: float`, `addressable_value: float`,
    `aov_window: str = "L28"`, `aov_source: str = "store_observed"`.
  - Added `PlayCard.opportunity_context: Optional[OpportunityContext] = None`.
  - Added `_from_dict_opportunity_context` and wired through
    `_from_dict_play_card` so the field round-trips through
    `EngineRun.to_dict()` / `EngineRun.from_dict()`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py`
  - Added `_resolve_aov_for_context(aligned, primary_window)` that
    reads a defensible store-observed AOV in priority L28, L56, L90.
    Returns `None` when no positive AOV is available.
  - Added `_build_opportunity_context(audience_size, aligned,
    primary_window)` returning `OpportunityContext` or `None`.
  - `build_directional_play_card` now populates
    `opportunity_context` on the directional PlayCard. Omits the
    field silently when audience or AOV is unavailable.
- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling_v2.py`
  - Added `OPPORTUNITY_CONTEXT_CLASS = "play-card-opportunity"` and
    `OPPORTUNITY_CONTEXT_DISCLAIMER` module constants.
  - Added `_round_addressable_value(value)` that produces "about $X"
    framing at three magnitude bands.
  - Added `_render_opportunity_context_block(opp, revenue_range)`
    that renders the block ONLY when `revenue_range` is suppressed
    or absent. Renders body-copy `<div>` containing two `<p>` lines:
    a sentence with audience x AOV = addressable, and the verbatim
    "not projected lift" disclaimer. Hides itself when a calibrated
    `revenue_range` is available (deferring to the range chip).
  - `_render_measured_card` now appends the opportunity-context block
    after `metric_summary` and before any range chip. Targeting-card
    renderer is unchanged so the M8 invariant cannot regress.
  - Inline CSS extended with three `.play-card-opportunity*` rules
    (muted background, smaller font than the headline, italic
    disclaimer line).

Untouched (intentionally):
- `src/decide.py` — no decision-logic change. AOV is read directly
  from `aligned` by the measurement builder.
- `src/sizing.py` — no sizing call on the Phase 5.6 directional card.
- `src/storytelling.py`, `templates/briefing.html.j2` — legacy
  renderer untouched.
- `src/main.py` — no orchestration change.
- `config/priors.yaml` — no priors added or relabeled.
- `tests/golden/` — no goldens re-baselined.

## Exact commands run

```
# Per-step iterative testing during implementation:
python -m pytest tests/test_phase5_1_opportunity_context.py -v
# 20 passed in 0.23s

# Combined V2 / Phase 5 / golden suite (no regressions check):
python -m pytest tests/test_phase5_measured_pathway.py \
                 tests/test_targeting_no_dollar_headline.py \
                 tests/test_render_v2.py \
                 tests/test_golden_diff.py \
                 tests/test_phase5_no_aura_beacon.py \
                 tests/test_phase5_abstain_copy.py \
                 tests/test_phase5_considered_always.py \
                 tests/test_phase5_watching_signals.py \
                 tests/test_phase5_materiality_copy.py \
                 tests/test_phase5_journey_optimization_suppressed.py -q
# 86 passed

# Full suite:
python -m pytest tests/ -q
# 507 passed, 5 skipped, 200 warnings

# End-to-end on Beauty Brand (full V2 stack):
ENGINE_V2_OUTPUT=true ENGINE_V2_DECIDE=true ENGINE_V2_SIZING=true \
STATS_NAN_FOR_HARDCODED=true EVIDENCE_CLASS_ENFORCED=true \
TARGETING_RECLASSIFY_PLAYS=true MATERIALITY_FLOOR_SCALE_AWARE=true \
CANNIBALIZATION_GATE_ENABLED=true ANOMALY_GATE_ENABLED=true \
VERTICAL_MODE=beauty \
  python -m src.main --orders data/beauty_brand_orders.csv \
                     --brand beauty_brand_phase5_1 \
                     --out /tmp/phase5_1_beauty

# End-to-end on small_sm (V2 stack, ABSTAIN_SOFT, no directional card):
ENGINE_V2_OUTPUT=true ENGINE_V2_DECIDE=true ENGINE_V2_SIZING=true \
STATS_NAN_FOR_HARDCODED=true EVIDENCE_CLASS_ENFORCED=true \
TARGETING_RECLASSIFY_PLAYS=true MATERIALITY_FLOOR_SCALE_AWARE=true \
CANNIBALIZATION_GATE_ENABLED=true ANOMALY_GATE_ENABLED=true \
  python -m src.main --orders data/SM_orders.csv \
                     --brand sm_phase5_1 \
                     --out /tmp/phase5_1_sm

# Default-mode (no V2 flags) regression check:
python -m pytest tests/test_golden_diff.py -v
# 3 passed
```

## Tests / checks run and counts

| Suite                                                 | Count          |
|-------------------------------------------------------|----------------|
| `tests/test_phase5_1_opportunity_context.py`          | 20 passed      |
| `tests/test_phase5_measured_pathway.py`               | 14 passed      |
| `tests/test_targeting_no_dollar_headline.py`          | 6 passed       |
| `tests/test_render_v2.py`                             | 24 passed      |
| `tests/test_golden_diff.py`                           | 3 passed       |
| `tests/test_phase5_*.py` (other Phase 5 suites)       | 39 passed      |
| **Full suite `python -m pytest tests/`**              | **507 passed, 5 skipped** |

Phase 5 baseline was 487 passed. +20 new tests. Zero regressions.

## How addressable value is calculated

Formula:
```
addressable_value = audience_size * recent_aov
```

No realization factor, no probability weighting, no causal claim. The
copy explicitly frames this as "the size of the audience if the play
converts" — not as an expected outcome.

Rounding (in `_round_addressable_value`):
- value < $10,000 -> nearest $100, e.g. `about $4,200`
- $10k <= value < $1M -> one decimal of $1k, e.g. `about $19.7k`
- value >= $1M -> one decimal of $1M, e.g. `about $1.2M`

The "about" framing is mandatory at every band so a merchant cannot
read it as a precise dollar projection. Non-positive or NaN inputs
return the empty string, which causes the block to be omitted rather
than render with a placeholder.

## Where AOV comes from

AOV is read directly from the existing `aligned` KPI snapshot that
Phase 5.6 already passes into `build_directional_play_card`. The
source field is `aligned[primary_window]["aov"]`, which is the same
AOV that:

- the legacy briefing renders in the state-of-store paragraph,
- `src/sizing.py` consumes as `aov` in `SizingInputs`,
- `src/utils.py` documents at `kpi_snapshot_with_deltas`'s docstring
  (line 1444: ``aligned["L7"]["net_sales"|"orders"|"aov"|...]``).

Window selection is done by `_resolve_aov_for_context` with priority
L28 (default primary), L56, L90. The first window with a positive
numeric AOV wins. If none are available, the function returns `None`
and the opportunity context block is omitted entirely. No
vertical-prior AOV, no fabricated default, no global fallback.

`OpportunityContext.aov_source` is hard-coded to
`"store_observed"` because today the only source is the per-store
aligned snapshot. `aov_window` records the actual window picked
(typically `"L28"`) for receipts / debug.html.

## Beauty Brand before / after card copy

### Before (Phase 5 baseline, commit cc06c8d)

```html
<article class="play-card play-card--directional"
         data-play-id="first_to_second_purchase"
         data-evidence-class="directional">
  <h3 class="play-card__title">First To Second Purchase</h3>
  <div class="play-card__class-badge play-card__class-badge--directional">Emerging</div>
  <p class="play-card__recommendation">Send a structured first-to-second purchase nudge to single-purchase customers.</p>
  <p class="play-card__why-now"><strong>Why now:</strong> Returning-customer share moved up 6.6% on L28 with consistent direction across L56/L90 windows. The retention trend supports a measured first-to-second nudge to the single-purchase cohort.</p>
  <div class="play-card-aud">
    <span class="play-card-aud__size"><strong>286</strong> people</span>
    <span class="play-card-aud__def">customers with exactly one historical order</span>
  </div>
  <div class="play-card-metric">Observed: <strong>returning customer share</strong> (direction agrees across 3 windows).</div>
</article>
```

(No economic context. The merchant sees an audience size and a metric
note but cannot judge the size of the opportunity.)

### After (Phase 5.1 follow-up)

```html
<article class="play-card play-card--directional"
         data-play-id="first_to_second_purchase"
         data-evidence-class="directional">
  <h3 class="play-card__title">First To Second Purchase</h3>
  <div class="play-card__class-badge play-card__class-badge--directional">Emerging</div>
  <p class="play-card__recommendation">Send a structured first-to-second purchase nudge to single-purchase customers.</p>
  <p class="play-card__why-now"><strong>Why now:</strong> Returning-customer share moved up 6.6% on L28 with consistent direction across L56/L90 windows. ...</p>
  <div class="play-card-aud">
    <span class="play-card-aud__size"><strong>286</strong> people</span>
    <span class="play-card-aud__def">customers with exactly one historical order</span>
  </div>
  <div class="play-card-metric">Observed: <strong>returning customer share</strong> (direction agrees across 3 windows).</div>
  <div class="play-card-opportunity"
       data-aov-source="store_observed"
       data-aov-window="L28">
    <p class="play-card-opportunity__line">
      Opportunity context: <strong>286</strong> eligible customers
      &times; <strong>$69</strong> recent AOV (L28) =
      <strong>about $19.7k</strong> addressable order value.
    </p>
    <p class="play-card-opportunity__disclaimer">
      This is not projected lift; it shows the size of the audience
      if the play converts.
    </p>
  </div>
</article>
```

The merchant now sees:
- Opportunity context: **286** eligible customers x **$69** recent
  AOV (L28) = **about $19.7k** addressable order value.
- This is not projected lift; it shows the size of the audience if
  the play converts.

## Confirmation: revenue_range.suppressed remains true

Direct read from the Beauty Brand `engine_run.json`:

```json
"recommendations": [
  {
    "play_id": "first_to_second_purchase",
    "evidence_class": "directional",
    "revenue_range": {
      "p10": null,
      "p50": null,
      "p90": null,
      "source": null,
      "suppressed": true,
      "drivers": [
        {"name": "suppression_reason", "value": "directional_no_intervention_effect", ...},
        {"name": "returning_customer_share", "value": 0.915, ...}
      ]
    },
    "opportunity_context": {
      "audience_size": 286,
      "aov": 68.7081077147016,
      "addressable_value": 19650.518806404656,
      "aov_window": "L28",
      "aov_source": "store_observed"
    }
  }
]
```

`suppressed=true`, `p10/p50/p90=null`, drivers list intact. The
addressable value 19650 corresponds to "about $19.7k" via the
rounding helper.

The pinned test `test_revenue_range_remains_suppressed_with_opportunity_context`
mechanically enforces this for synthetic fixtures too.

## Confirmation: no forbidden strings or fake projections added

Verified mechanically in the rendered Beauty Brand briefing.html:

| Token                | Count |
|----------------------|-------|
| `p =`                | 0     |
| `q =`                | 0     |
| `CI`                 | 0     |
| `confidence_score`   | 0     |
| `final_score`        | 0     |
| `p_internal`         | 0     |
| `ci_internal`        | 0     |
| `expected revenue`   | 0     |
| `expected impact`    | 0     |
| `p50`                | 0     |
| `forecast`           | 0     |
| `predicted`          | 0     |

Affirmative-claim tokens absent; the only occurrence of `projected
lift` in the entire page is inside the **negation** disclaimer:
"This is **not** projected lift". Pinned by
`test_opportunity_context_does_not_introduce_forecast_terms` in the
new test file.

The `OPPORTUNITY_CONTEXT_DISCLAIMER` module constant is the canonical
source of truth for the merchant-facing copy and is asserted by
`test_opportunity_context_disclaimer_is_the_module_constant`.

## Whether full tests pass

**Yes.** 507 passed, 5 skipped (the 5 skips are M4a-era unrelated
suspended cases; same as the M9/Phase 5 baseline).

Specifically:
- All 487 prior Phase-5 tests still pass byte-for-byte.
- 20 new Phase 5.1 tests pass.
- M0 golden-diff legacy lane: 3 passed (legacy CSV->HTML byte-identical).
- M8 targeting-no-dollar-headline invariant: 6 passed.

## Fallback path taken if AOV unavailable

For Beauty Brand, AOV is available on L28 (`$68.71`). The block
renders as designed with `aov_window="L28"` and
`aov_source="store_observed"`.

If the brief had encountered a fixture where L28 AOV was missing or
zero, `_resolve_aov_for_context` would have stepped through L56 then
L90. If all three were unusable, it would have returned `None` and
the block would have been omitted entirely with NO placeholder.

This fallback path is exercised in
`test_opportunity_context_omitted_when_aov_unavailable`, which
constructs an aligned snapshot with all three windows missing/zero
AOV and verifies the rendered HTML carries no
`class="play-card-opportunity"` attribute and no fabricated value.

## Why the block does not appear on targeting cards

Two layers of defense:

1. **Targeting-card renderer (`_render_targeting_card`) does not call
   the helper.** Only `_render_measured_card` does. So even if a
   targeting card carried a populated `opportunity_context` (e.g. a
   future change wires it through), the renderer will not surface it.
2. **The M8 invariant test
   `tests/test_targeting_no_dollar_headline.py` continues to pass
   unchanged.** Pinned by `test_existing_targeting_no_dollar_headline_invariant_still_passes`
   in the new test file (re-runs the M8 invariant inline against an
   `EngineRun` whose targeting card carries opportunity_context).

This preserves the Phase 5 product contract that targeting cards
either show a clearly-labeled range chip OR show no dollar amount
at all — body copy from `OpportunityContext` is not allowed to
become a backdoor dollar headline.

## Behavior changes

Visible behavior changes (V2 stack only):

- **Beauty Brand (PUBLISH state)**: directional `first_to_second_purchase`
  card now carries an "Opportunity context" block with audience x AOV
  = about $19.7k addressable order value, plus the "not projected
  lift" disclaimer.
- **small_sm (ABSTAIN_SOFT)**: no directional card, so no block
  appears. Briefing is unchanged from Phase 5.
- **mid_shopify (ABSTAIN_SOFT)**: same as small_sm.
- **micro_coldstart (ABSTAIN_SOFT)**: same.

Invisible behavior changes:

- `EngineRun.recommendations[].opportunity_context` is now populated
  on directional cards built by `measurement_builder` when audience
  size > 0 and a positive recent AOV exists. Receipts / debug.html
  expose this for engineering review.

No behavior change in:

- Legacy renderer (default mode).
- Decision logic (`src/decide.py`).
- Sizing (`src/sizing.py`).
- Guardrails / cannibalization / inventory gates.
- ABSTAIN_SOFT / ABSTAIN_HARD layout.
- Targeting-card visual treatment.
- Considered list / Watching list.
- Outcome log writer.

## Artifacts added

- `src/engine_run.py:OpportunityContext` (typed dataclass).
- `src/engine_run.py:PlayCard.opportunity_context` (typed field).
- `src/measurement_builder.py:_resolve_aov_for_context`,
  `_build_opportunity_context` (new helpers).
- `src/storytelling_v2.py:OPPORTUNITY_CONTEXT_CLASS`,
  `OPPORTUNITY_CONTEXT_DISCLAIMER`, `_round_addressable_value`,
  `_render_opportunity_context_block` (new module-level constants
  and helpers).
- `tests/test_phase5_1_opportunity_context.py` (20 tests).
- This summary.

## Remaining risks

1. **AOV definition leak.** The block reads
   `aligned[primary_window]["aov"]` directly. If a future change to
   `kpi_snapshot_with_deltas` redefines `aov` (e.g. switches to a
   margin-adjusted figure), the merchant-facing addressable value will
   silently shift. Recommend pinning the AOV-definition contract in a
   docs/ note before any change to the snapshot's AOV computation.

2. **No vertical / play-specific addressable model.** The current
   block always shows `audience_size * aov`. For plays where the
   target action is not a single full-AOV order (e.g. subscription
   uplift, replenishment), this overstates the addressable value.
   Phase 5.1 only wires the helper for `first_to_second_purchase`,
   which is single-purchase to first-repeat, so the simple model is
   defensible. If future plays surface as directional, the helper
   should accept a per-play "addressable order multiplier" before
   re-using.

3. **No explicit per-card opportunity-context cap.** Today only one
   directional card surfaces per run on real fixtures, so the page
   never accumulates many addressable-value lines. If a future change
   wires multiple directional pathways at once, the page may risk
   reading like a stacked-projection list. Mitigation today is the
   M7 top-3 cap; if that loosens, the renderer should add a
   per-section "addressable values do not aggregate" footnote.

4. **`OpportunityContext.aov` is a raw float, not rounded.** This
   means the receipts / debug.html will see precise per-store AOV
   (e.g. 68.7081077147016 for Beauty Brand). The rendered block uses
   `_fmt_money` (`$69`) and `_round_addressable_value`
   (`about $19.7k`) so merchants see rounded numbers. The unrounded
   precision is fine for receipts but could be surprising in
   debug.html consumers; document if needed.

5. **Range chip vs opportunity context fallback ordering.** The
   helper hides the opportunity-context block when
   `revenue_range.suppressed=False`. If a future change adds a
   measured pathway with both a calibrated range AND a populated
   `opportunity_context`, the calibrated range wins. This is
   intentional but worth flagging if calibration data ever lands.

## Follow-up work

- Wire `at_risk_repeat_buyer_rescue` similarly when its M3 audience
  builder lands. Reuse `_build_opportunity_context` directly.
- When campaign realization data lets us promote a directional card
  to measured + non-suppressed range, the Phase 5.1 block will hide
  itself automatically — no renderer change needed. The
  calibrated-range path is the better surface once it exists.
- Add a per-play `addressable_order_multiplier` if a future
  directional play has a target action that is not a single
  full-AOV order.
- Consider exposing `opportunity_context` in `receipts/debug.html`
  for engineering inspection (today the merchant briefing is the
  only consumer).
- Sync docstrings: the M1 `Observation` cap docstring (3-5) is
  already known to be stale (Phase 5 raised it to 7). Phase 5.1
  adds no new cap to drift.
