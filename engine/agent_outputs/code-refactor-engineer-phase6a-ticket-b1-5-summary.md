# Code Refactor Engineer — Phase 6A Ticket B1.5 Summary

_Date: 2026-05-05_
_Branch: `engine-rework`_
_Baseline: post-B1 working tree (unstaged on top of `bfa8eff`)._
_Scope: Phase 6A Ticket B1.5 ONLY — populate `opportunity_context` on
Recommended Experiment PlayCards using the existing Phase 5.1 builder._

## Approved Scope

Populate `opportunity_context` on Recommended Experiment PlayCards
produced by `_select_recommended_experiments` in `src/decide.py`, using
the existing Phase 5.1 opportunity-context builder
(`src.measurement_builder._build_opportunity_context`) so the renderer's
already-implemented opportunity-context block (shipped in Ticket B1)
surfaces on real V2 slate runs, not only in renderer unit tests.

This closes the gap explicitly flagged by the B1 summary:

> Future selector extension: populate `opportunity_context` on
> Recommended Experiment cards so the addressable-value block renders
> end-to-end on real fixtures (renderer is ready; producer wiring is a
> follow-on).

## Patch Summary

1. **`src/decide.py`** — additive selector + `decide()` plumbing:
   - Extended `_select_recommended_experiments(...)` with an additional
     keyword-only argument `aligned: Optional[Mapping[str, Any]] = None`.
   - Lazy-imports `src.measurement_builder._build_opportunity_context`
     inside the card-construction block (to avoid a top-level circular
     import) and calls it with `audience_size` and `aligned` plus
     `primary_window="L28"` — identical signature/usage to the Phase 5.6
     directional builder. The result is stamped onto each output
     PlayCard as `opportunity_context`. When the helper returns `None`
     (no `aligned`, empty dict, missing AOV, NaN, or non-positive AOV
     across L28 / L56 / L90), the field stays `None` and the card
     renders without the addressable-value sentence.
   - Extended `decide()` with a matching keyword-only argument
     `aligned: Optional[Mapping[str, Any]] = None` and forwards it to
     the selector. Default `None` preserves byte-stable behavior on
     every legacy / flag-off path.
   - Updated docstrings on both functions to describe the new
     parameter and its no-fabrication contract.

2. **`src/main.py`** — one-line wiring:
   - Updated the V2 decide call from
     `_v2_decide(engine_run, cfg=cfg, candidates=_phase5_cands_for_decide)`
     to additionally pass `aligned=aligned_for_template`. This is the
     same `aligned_for_template` dict the Phase 5.6 directional builder
     reads (built via `kpi_snapshot_with_deltas(...)` earlier in
     `run(...)`). Single source of truth — no re-computation, no new
     dict shape, no new field.
   - Added an inline comment block describing the B1.5 contract and the
     no-op semantics under `ENGINE_V2_SLATE=false`.

3. **`tests/test_recommended_experiment_opportunity_context.py` (NEW)** —
   15 tests pinning the B1.5 contract:
   - `test_real_selector_populates_opportunity_context_when_aov_available`
   - `test_real_selector_omits_opportunity_context_when_aligned_is_none`
   - `test_real_selector_omits_opportunity_context_when_aligned_empty`
   - `test_real_selector_omits_opportunity_context_when_aov_zero`
   - `test_real_selector_omits_opportunity_context_when_aov_nan`
   - `test_real_selector_falls_back_to_l56_then_l90`
   - `test_addressable_value_equals_audience_size_times_aov`
   - `test_aov_window_and_source_match_phase5_1_directional_builder`
     (differential test: cross-checks the selector's
     `opportunity_context` against the Phase 5.1 helper's output for
     the same `(audience, aligned)` input — the two paths MUST produce
     bit-identical dataclasses)
   - `test_revenue_range_remains_suppressed_after_opportunity_context_added_aov_present`
   - `test_revenue_range_remains_suppressed_after_opportunity_context_added_aov_missing`
   - `test_decide_plumbs_aligned_into_selector_when_slate_flag_on`
   - `test_decide_with_no_aligned_kwarg_omits_opportunity_context`
   - `test_decide_flag_off_keeps_recommended_experiments_empty_even_with_aligned`
   - `test_render_surfaces_opportunity_context_from_real_selector`
     (end-to-end render check using the real selector path)
   - `test_render_no_opportunity_context_block_when_aligned_missing`
     (scoped DOM check: when `aligned` is missing, the experiment
     section still renders but the opportunity-context block does NOT
     appear inside it)

No other source files were modified. No `src/storytelling.py`, no
`src/storytelling_v2.py` (the renderer is already wired to surface the
block — that was Ticket B1), no `src/engine_run.py`, no
`src/measurement_builder.py`, no `src/utils.py`, no `config/priors.yaml`,
no `src/priors_loader.py`, no goldens, no fixtures.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py`
  - `_select_recommended_experiments(...)` signature: added
    `aligned: Optional[Mapping[str, Any]] = None` kwarg.
  - `_select_recommended_experiments(...)` body: lazy-imports
    `_build_opportunity_context` from `measurement_builder` and stamps
    `opportunity_context` on each output `PlayCard`.
  - `decide(...)` signature: added matching `aligned` kwarg.
  - `decide(...)` body: forwards `aligned=aligned` to the selector.
  - Docstrings updated on both functions.

- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`
  - V2 decide call updated to pass `aligned=aligned_for_template`.
  - Inline B1.5 comment block added.

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_recommended_experiment_opportunity_context.py` (NEW)
  - 15 tests across direct-helper coverage, decide-layer plumbing,
    flag-off invariant, end-to-end render, and the differential check
    against the Phase 5.1 directional path.

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-b1-5-summary.md` (NEW)
  - This summary.

## Source of AOV

The selector reads AOV from the same source the Phase 5.6 directional
path reads: `kpi_snapshot_with_deltas(...)` aligned dict, threaded
through `aligned_for_template` in `src/main.py:316` and consumed by
`src.measurement_builder._build_opportunity_context` (defined at
`src/measurement_builder.py:191-219`). The helper's resolution chain is
unchanged — `aligned[L28]['aov']`, falling back to `L56`, then `L90`,
returning `None` when no defensible positive AOV is present.

The Phase 5.6 directional pathway today consumes the same source via
`src/main.py:774` (`build_directional_recommendations(_phase5_cands,
aligned_for_template, ...)`). B1.5 mirrors this pattern: the same
`aligned_for_template` dict now also flows into `decide(...)` so the
Recommended Experiment selector can call the same helper.

There is exactly one canonical AOV path; B1.5 introduces no new path
and no new field on `aligned`.

## How `opportunity_context` Is Populated

Inside `_select_recommended_experiments(...)`, the card-construction
block now does:

```python
from .measurement_builder import _build_opportunity_context  # lazy import

# ...
audience_size = int(getattr(cand, "audience_size", 0) or 0)
# ...
opp_ctx = _build_opportunity_context(
    audience_size,
    aligned if isinstance(aligned, Mapping) else None,
    primary_window="L28",
)
cards.append(
    PlayCard(
        play_id=...,
        evidence_class=EvidenceClass.TARGETING,
        audience=audience,
        measurement=None,
        revenue_range=revenue_range,
        opportunity_context=opp_ctx,        # B1.5
        would_be_measured_by=metadata.would_be_measured_by,
    )
)
```

The math matches Phase 5.1 verbatim:
`addressable_value = audience_size * aov` (no realization factor, no
multipliers, no causal priors, no probability weighting). The
`OpportunityContext` dataclass is the same one the directional builder
emits, including the `aov_window` (`L28` / `L56` / `L90` depending on
fallback) and `aov_source = "store_observed"` provenance.

## Behavior When AOV Is Missing / Zero / NaN

`_build_opportunity_context` returns `None` in every "no defensible AOV"
branch:

- `aligned is None` → `None`
- `aligned == {}` (no windows) → `None`
- `aligned[L28]['aov']` is missing → falls through to L56 → L90 → `None`
- `aligned[L28]['aov'] == 0.0` (or any non-positive) → falls through →
  `None` if every window is unusable
- `aligned[L28]['aov']` is `NaN` → `_safe_float` returns `None` → falls
  through → `None` if every window is unusable
- `audience_size <= 0` → `None`

In every case, the selector stamps `opportunity_context = None` on the
output card. The renderer's `_render_opportunity_context_block` already
self-hides on `None` (B1 contract), so the experiment card simply
renders without the addressable-value sentence. No fabrication is
possible by construction — the helper never returns a synthetic value.

Pinned by:
- `test_real_selector_omits_opportunity_context_when_aligned_is_none`
- `test_real_selector_omits_opportunity_context_when_aligned_empty`
- `test_real_selector_omits_opportunity_context_when_aov_zero`
- `test_real_selector_omits_opportunity_context_when_aov_nan`
- `test_render_no_opportunity_context_block_when_aligned_missing`

## Confirmation `revenue_range.suppressed=true` Remains

Every output Recommended Experiment card stamps
`revenue_range = RevenueRange(suppressed=True,
drivers=[{"reason": "experiment_no_calibrated_lift"}])` exactly as the
Ticket A4 selector did. B1.5 added a sibling field
(`opportunity_context`) but did NOT touch the `revenue_range` stamp.

Pinned by:
- `test_revenue_range_remains_suppressed_after_opportunity_context_added_aov_present`
- `test_revenue_range_remains_suppressed_after_opportunity_context_added_aov_missing`

Each test asserts `card.revenue_range.suppressed is True` AND that the
drivers list still contains
`{"reason": "experiment_no_calibrated_lift"}`. The two states (present
opportunity_context + suppressed revenue) coexist by design: the
suppressed range is the trust signal that says "we are not projecting
causal lift"; `opportunity_context` is the audience-sizing context with
the explicit "not projected lift" disclaimer.

The B1 invariant (`test_revenue_range_suppressed_remains_true_on_experiment_cards`)
also continues to pass — `tests/test_render_recommended_experiment.py`
20/20 passed in the regression run.

## Confirmation No Forbidden Terms Were Added

- Renderer-level forbidden-token tests still pass:
  `tests/test_render_recommended_experiment.py::test_no_forbidden_statistical_strings_in_experiment_section`
  and `test_no_aura_or_beacon_score_in_experiment_section` — green.
- `tests/test_targeting_no_dollar_headline.py` — 6/6 passed.
- `tests/test_phase5_no_aura_beacon.py` — 4/4 passed.
- `tests/test_phase5_1_opportunity_context.py` (the Phase 5.1 forbidden
  / forecast token sweeps) — 25/25 passed.
- `tests/test_phase5_1_opportunity_context.py::test_opportunity_context_does_not_introduce_forecast_terms`
  pins that the helper output never carries `forecast`, `predicted`,
  `expected lift`, etc. The same helper now also produces the
  experiment-card opportunity_context, so this invariant transitively
  covers the new code path.

Manual smoke check on the rendered Beauty fixture confirms:

| Token            | Section count | Notes                                                  |
| ---------------- | ------------- | ------------------------------------------------------ |
| `expected lift`  | 0             |                                                        |
| `projected lift` | 1             | inside the negation disclaimer "not projected lift"    |
| `forecast`       | 0             |                                                        |
| `predicted`      | 0             |                                                        |
| `uplift`         | 0             |                                                        |
| `ATE`            | 0             |                                                        |
| `ITT`            | 0             |                                                        |
| `treatment effect` | 0           |                                                        |
| `p50`            | 0             |                                                        |
| `calibrated`     | 0             |                                                        |
| `p =`            | 0             |                                                        |
| `q =`            | 0             |                                                        |
| `confidence_score` | 0           |                                                        |
| `final_score`    | 0             |                                                        |

The single `projected lift` occurrence in the experiment section is the
literal "not projected lift" disclaimer carried by the Phase 5.1
helper. No new forbidden terms were introduced.

## Sample Rendered Behavior

End-to-end smoke run on `data/beauty_brand_orders.csv` with
`ENGINE_V2_OUTPUT=true ENGINE_V2_DECIDE=true ENGINE_V2_SLATE=true
ENGINE_V2_SIZING=true VERTICAL_MODE=beauty`:

```html
<section class="recommended-experiment" aria-label="Recommended Experiment">
  <h2 class="section__title">Recommended Experiment</h2>
  <p class="section__lede">Plays we'd run as experiments. We will measure
    the result and learn whether they work for your store.</p>
  <div class="play-card-grid">
    <article class="play-card play-card--experiment"
             data-play-id="discount_hygiene"
             data-evidence-class="targeting">
      <h3 class="play-card__title">Discount Hygiene</h3>
      <div class="play-card__class-badge play-card__class-badge--experiment">
        Run as experiment</div>
      <div class="play-card-aud">
        <span class="play-card-aud__size"><strong>962</strong> people</span>
        <span class="play-card-aud__def">customers with discounted orders
          in last 28 days</span>
      </div>
      <p class="play-card__measured-by">We will measure email-attributed
        revenue in 7 days.</p>
      <div class="play-card-opportunity"
           data-aov-source="store_observed"
           data-aov-window="L28">
        <p class="play-card-opportunity__line">Opportunity context:
          <strong>962</strong> eligible customers &times;
          <strong>$69</strong> recent AOV (L28) =
          <strong>about $66.1k</strong> addressable order value.</p>
        <p class="play-card-opportunity__disclaimer">This is not
          projected lift; it shows the size of the audience if the play
          converts.</p>
      </div>
    </article>
  </div>
</section>
```

Pre-B1.5 (post-B1) on the same fixture: the `<section
class="recommended-experiment">` rendered with the audience and the
"We will measure email-attributed revenue in 7 days" line, but no
`<div class="play-card-opportunity">` block — the producer wiring was
absent. B1.5 fills that block in.

## Exact Commands Run

```bash
# Red-first capture (BEFORE the selector edit)
python -m pytest tests/test_recommended_experiment_opportunity_context.py -v
# -> 13 failed, 2 passed in 0.04s
#    Failures: TypeError: _select_recommended_experiments() got an
#    unexpected keyword argument 'aligned' (and downstream).
#    The 2 passing tests were no-aligned-kwarg cases that pass
#    trivially on the unchanged signature (the new tests intentionally
#    cover both signatures).

# Green (AFTER the selector + decide() + main.py edits)
python -m pytest tests/test_recommended_experiment_opportunity_context.py -v
# -> 15 passed in 0.25s

# Eligibility / wiring / renderer regression
python -m pytest \
    tests/test_recommended_experiment_eligibility.py \
    tests/test_recommended_experiment_main_wiring.py \
    tests/test_render_recommended_experiment.py \
    tests/test_targeting_no_dollar_headline.py \
    tests/test_render_v2.py -v
# -> 78 passed in 0.61s

# Schema / decide / priors / Phase 5 regression
python -m pytest \
    tests/test_engine_run_schema.py \
    tests/test_decide.py \
    tests/test_priors_metadata.py \
    tests/test_phase5_no_aura_beacon.py \
    tests/test_phase5_1_opportunity_context.py -v
# -> 91 passed in 0.63s

# Cross-cutting Fix 1-11 + A1/A2 invariants
python -m pytest \
    tests/test_targeting_no_dollar_headline.py \
    tests/test_phase5_no_aura_beacon.py \
    tests/test_targeting_measurement_invariant.py \
    tests/test_abstain_soft_no_recommendations.py \
    tests/test_inventory_blocked_in_considered.py \
    tests/test_materiality_footer_present.py \
    tests/test_matrix_vertical_propagation.py \
    tests/test_reporter_dom_only.py \
    tests/test_synthetic_fixtures_8_11.py \
    tests/test_watching_load_bearing_priority.py \
    tests/test_would_be_measured_by_enum.py -q
# -> 133 passed, 3 skipped in 5.23s

# Goldens (M0 byte-identical)
python -m pytest tests/test_golden_diff.py -v
# -> 3 passed, 0 re-baselined in 26.45s

# Full suite
python -m pytest tests/ -q
# -> 795 passed, 14 skipped, 0 failed in 119.05s
```

## Tests / Checks Run

| Check                                                                  | Result                              | Notes                                                         |
| ---------------------------------------------------------------------- | ----------------------------------- | ------------------------------------------------------------- |
| `tests/test_recommended_experiment_opportunity_context.py` (NEW)       | **15 passed**                       | Red-first failure captured before the selector edit landed    |
| `tests/test_recommended_experiment_eligibility.py`                     | 22 passed                           | A4 contract intact                                            |
| `tests/test_recommended_experiment_main_wiring.py`                     | 5 passed                            | A4.5 contract intact (kwarg pin still green)                  |
| `tests/test_render_recommended_experiment.py`                          | 20 passed                           | B1 renderer contract intact                                   |
| `tests/test_render_v2.py`                                              | 25 passed                           | M8 / A1 contract intact                                       |
| `tests/test_targeting_no_dollar_headline.py`                           | 6 passed                            | DS QA Change 4 / M8 invariant intact                          |
| `tests/test_engine_run_schema.py`                                      | 12 passed                           | Schema round-trip intact                                      |
| `tests/test_decide.py`                                                 | 34 passed                           | M7 contract intact                                             |
| `tests/test_priors_metadata.py`                                        | 21 passed                           | A3 loader intact                                              |
| `tests/test_phase5_no_aura_beacon.py`                                  | 4 passed                            | Phase 5.5 forbidden-token sweep intact                        |
| `tests/test_phase5_1_opportunity_context.py`                           | 25 passed                           | Phase 5.1 helper invariants intact (opportunity_context, no forecast tokens, suppressed range, etc.) |
| `tests/test_would_be_measured_by_enum.py`                              | 14 passed                           | A2 contract intact                                            |
| `tests/test_targeting_measurement_invariant.py`                        | green                               | Fix 2                                                         |
| `tests/test_abstain_soft_no_recommendations.py`                        | green                               | Fix 3                                                         |
| `tests/test_inventory_blocked_in_considered.py`                        | green                               | Fix 4                                                         |
| `tests/test_materiality_footer_present.py`                             | green                               | Fix 5                                                         |
| `tests/test_matrix_vertical_propagation.py`                            | green                               | Fix 6                                                         |
| `tests/test_reporter_dom_only.py`                                      | green                               | Fix 7                                                         |
| `tests/test_synthetic_fixtures_8_11.py`                                | green                               | Fixes 8-11                                                    |
| `tests/test_watching_load_bearing_priority.py`                         | 5 passed                            | A1 load-bearing pin intact                                    |
| `tests/test_golden_diff.py`                                            | **3 passed (no re-baseline)**       | M0 byte-identical                                             |
| Full suite `pytest tests/ -q`                                          | **795 passed, 14 skipped, 0 failed** | Pre-B1.5 baseline 780 passed; +15 = exactly the new test file |

## Did The New Tests FAIL Before The Fix?

**Yes — red-first evidence captured.** Before any change to
`src/decide.py` or `src/main.py`,
`python -m pytest tests/test_recommended_experiment_opportunity_context.py -v`
produced **13 failed, 2 passed** with the following verbatim signatures
(condensed; the same shape repeats for each failed test):

```
FAILED tests/test_recommended_experiment_opportunity_context.py::test_real_selector_populates_opportunity_context_when_aov_available
  TypeError: _select_recommended_experiments() got an unexpected keyword argument 'aligned'

FAILED tests/test_recommended_experiment_opportunity_context.py::test_real_selector_omits_opportunity_context_when_aligned_is_none
  TypeError: _select_recommended_experiments() got an unexpected keyword argument 'aligned'

FAILED tests/test_recommended_experiment_opportunity_context.py::test_real_selector_omits_opportunity_context_when_aligned_empty
  TypeError: _select_recommended_experiments() got an unexpected keyword argument 'aligned'

FAILED tests/test_recommended_experiment_opportunity_context.py::test_real_selector_omits_opportunity_context_when_aov_zero
FAILED tests/test_recommended_experiment_opportunity_context.py::test_real_selector_omits_opportunity_context_when_aov_nan
FAILED tests/test_recommended_experiment_opportunity_context.py::test_real_selector_falls_back_to_l56_then_l90
FAILED tests/test_recommended_experiment_opportunity_context.py::test_addressable_value_equals_audience_size_times_aov
FAILED tests/test_recommended_experiment_opportunity_context.py::test_aov_window_and_source_match_phase5_1_directional_builder
FAILED tests/test_recommended_experiment_opportunity_context.py::test_revenue_range_remains_suppressed_after_opportunity_context_added_aov_present
FAILED tests/test_recommended_experiment_opportunity_context.py::test_revenue_range_remains_suppressed_after_opportunity_context_added_aov_missing
FAILED tests/test_recommended_experiment_opportunity_context.py::test_decide_plumbs_aligned_into_selector_when_slate_flag_on
  TypeError: decide() got an unexpected keyword argument 'aligned'

FAILED tests/test_recommended_experiment_opportunity_context.py::test_decide_flag_off_keeps_recommended_experiments_empty_even_with_aligned
  TypeError: decide() got an unexpected keyword argument 'aligned'

FAILED tests/test_recommended_experiment_opportunity_context.py::test_render_surfaces_opportunity_context_from_real_selector
  TypeError: decide() got an unexpected keyword argument 'aligned'
```

The 2 trivially-passing tests pre-fix were:
- `test_decide_with_no_aligned_kwarg_omits_opportunity_context` — calls
  `decide(...)` without `aligned=` and asserts `opportunity_context is
  None`. Trivially true on the pre-fix signature because the field
  defaulted to `None` already.
- `test_render_no_opportunity_context_block_when_aligned_missing` —
  same shape; the renderer's self-hiding behavior was already in place
  from B1.

After the selector and `decide()` edits and the `main.py` wiring,
all 15 tests passed on first run.

## Goldens

- `tests/test_golden_diff.py` → **3 passed, 0 re-baselined**.
- M0 legacy goldens
  (`tests/golden/{small_sm, mid_shopify, micro_coldstart}/*`):
  byte-identical.
- Expected outcome because (a) goldens are produced under default flags
  (`ENGINE_V2_OUTPUT=false`, `ENGINE_V2_SLATE=false`), (b)
  `recommended_experiments` stays `[]` when the slate flag is off, so
  the new `aligned` kwarg has zero observable effect, (c) the legacy
  renderer (`src/storytelling.py`) is unchanged.

## Confirmation A1 + A2 + A3 + A4 + A4.5 + B1 Behavior Is Intact

**A1 (Watching cap=4 + load-bearing pin):**
- `src/storytelling_v2.py` not modified by B1.5.
- `MAX_WATCHING_RENDERED = 4` unchanged.
- `_LOAD_BEARING_WATCH_METRICS` unchanged.
- `tests/test_watching_load_bearing_priority.py` 5/5 passed.
- `tests/test_render_v2.py` 25/25 passed.

**A2 (`would_be_measured_by` enum + PlayCard field):**
- `src/engine_run.py` not modified by B1.5.
- `WouldBeMeasuredBy` enum unchanged.
- `PlayCard.would_be_measured_by` field unchanged.
- `tests/test_would_be_measured_by_enum.py` 14/14 passed.
- `tests/test_engine_run_schema.py` 12/12 passed.

**A3 (priors metadata schema + loader):**
- `config/priors.yaml` unchanged.
- `src/priors_loader.py` unchanged.
- `AudienceArchetype`, `PlayMetadata`, `PriorsMetadataError`,
  `get_play_metadata` unchanged.
- `tests/test_priors_metadata.py` 21/21 passed.

**A4 (Recommended Experiment eligibility filter):**
- `_select_recommended_experiments(...)` signature gained an additive
  `aligned` kwarg (default `None`); default-call behavior is unchanged.
- `MAX_RECOMMENDED_EXPERIMENT`,
  `RECOMMENDED_EXPERIMENT_ALLOWLIST`,
  `RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD` unchanged.
- All 12 eligibility rules unchanged.
- `revenue_range = RevenueRange(suppressed=True,
  drivers=[{"reason": "experiment_no_calibrated_lift"}])` stamp
  unchanged.
- `evidence_class = TARGETING` stamp unchanged.
- `would_be_measured_by` stamp unchanged.
- `tests/test_recommended_experiment_eligibility.py` 22/22 passed.

**A4.5 (candidate plumbing into decide):**
- `_phase5_cands_for_decide` hoist + bind + kwarg pin unchanged.
- The structural source-text test
  (`test_main_module_v2_decide_call_passes_candidates`) reads
  `src/main.py` as text and checks for `candidates=` on every
  `_v2_decide(...)` call site. B1.5 added an additional `aligned=`
  kwarg on the same call but did NOT remove or rename `candidates=`.
  The test scans for the literal `candidates=` substring and remains
  green.
- `tests/test_recommended_experiment_main_wiring.py` 5/5 passed.

**B1 (Recommended Experiment renderer):**
- `src/storytelling_v2.py` not modified by B1.5.
- `RECOMMENDED_EXPERIMENT_SECTION_CLASS`,
  `RECOMMENDED_EXPERIMENT_LEDE`,
  `_WOULD_BE_MEASURED_BY_DISPLAY_COPY` unchanged.
- `_render_recommended_experiment_card`,
  `render_recommended_experiment_section` unchanged.
- DOM order unchanged
  (state-of-store → recommended → recommended-experiment → considered
   → watching → dq-footer).
- The pre-existing renderer `_render_opportunity_context_block` call
  inside `_render_recommended_experiment_card` was already wired in
  B1; B1.5 simply makes the producer populate the field that the
  renderer already reads. No renderer signature change.
- `tests/test_render_recommended_experiment.py` 20/20 passed.

## Behavior Changes

Under default flags (`ENGINE_V2_SLATE=false`) — **no merchant-facing
change**. Legacy briefing is unchanged. V2 receipts on the unchanged
flag-off path are unchanged.

Under the full V2 + slate stack (`ENGINE_V2_OUTPUT=true` AND
`ENGINE_V2_DECIDE=true` AND `ENGINE_V2_SLATE=true`) on a real fixture
where the selector emits at least one experiment card AND a defensible
L28 AOV is available:

- **Pre-B1.5 (post-B1):** The Recommended Experiment section rendered
  with title, lede, audience block, "we will measure ..." line, and
  the "Run as experiment" badge — but no addressable-value sentence
  and no "not projected lift" disclaimer (because the producer left
  `opportunity_context = None`).
- **Post-B1.5:** The same section now also renders the Phase 5.1
  opportunity-context block on each experiment card, including the
  "Opportunity context: N eligible customers × $X recent AOV (L28) =
  about $Yk addressable order value." sentence and the "This is not
  projected lift; it shows the size of the audience if the play
  converts." disclaimer. The math, copy, classes, and DOM shape are
  byte-identical to the Phase 5.1 block already shipped on the
  Recommended Now / directional path.

Under the full V2 + slate stack on a fixture where AOV is missing /
zero / NaN — the experiment cards render WITHOUT the addressable-value
block (the renderer self-hides on `None`). Cards still show audience
and the measured-by line; `revenue_range.suppressed=True` remains.

Smoke-tested on `data/beauty_brand_orders.csv` (Beauty Brand): the
experiment card for `discount_hygiene` (audience 962, L28 AOV $69)
renders the addressable value `about $66.1k` with the disclaimer.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_recommended_experiment_opportunity_context.py`
  — 15 tests pinning the B1.5 contract: real-selector
  opportunity_context population, AOV missing/zero/NaN omission, AOV
  fallback chain (L28 → L56 → L90), addressable-value math,
  selector vs Phase 5.1 differential, suppressed-range invariant,
  decide-layer plumbing, flag-off invariant, end-to-end render with
  real selector, and DOM-scoped block-absence when aligned is missing.

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-b1-5-summary.md`
  — this summary.

No new sample HTML, fixtures, or goldens. No CSS additions. No
changes to `src/storytelling.py` (legacy renderer), `src/storytelling_v2.py`
(V2 renderer — already wired in B1), `src/engine_run.py`,
`src/measurement_builder.py` (the helper is reused as-is),
`src/utils.py`, `config/priors.yaml`, or `src/priors_loader.py`.

## Remaining Risks

1. **Lazy import of `_build_opportunity_context` from a `_`-prefixed
   API.** The B1.5 call site reads
   `from .measurement_builder import _build_opportunity_context`. A
   future refactor that renames or relocates this helper would silently
   break the experiment-card opportunity_context. Two mitigations: the
   differential test
   (`test_aov_window_and_source_match_phase5_1_directional_builder`)
   directly imports the same helper and would surface the rename
   failure; if a rename is needed, both call sites update in lockstep.
   A future ticket could promote `_build_opportunity_context` to a
   public name in `measurement_builder.__all__` to make this contract
   explicit.

2. **AOV source coupling.** Both Phase 5.6 and B1.5 read
   `aligned[L28]['aov']` via the same helper. A future change to the
   AOV computation in `kpi_snapshot_with_deltas(...)` would silently
   shift both the directional Recommended Now card and the experiment
   card's addressable_value at the same time. This is the intended
   behavior — single source of truth — but worth noting because the
   downstream B6 Beauty Brand pinned slate regression will be the
   first byte-stable check on this number.

3. **B1.5 does not change main.py's exception handling.** The Phase 5
   try/except block already catches every exception and defaults
   `_phase5_cands_for_decide = None`. B1.5's added `aligned` kwarg
   reads `aligned_for_template`, which is built earlier in `run(...)`
   well before the V2 try blocks; if `kpi_snapshot_with_deltas(...)`
   itself failed earlier, the entire run would have failed before
   reaching the V2 decide block. This is unchanged from the prior
   behavior.

4. **`Mapping` runtime check uses `isinstance(aligned, Mapping)`.** A
   future caller passing a `dict`-like proxy that is not a
   `collections.abc.Mapping` subclass (rare) would be coerced to
   `None` defensively. The standard `dict` returned by
   `kpi_snapshot_with_deltas` IS a `Mapping` subclass, so this is a
   no-op for the canonical path. Pinned by
   `test_real_selector_populates_opportunity_context_when_aov_available`.

5. **Empty-state message for "we have a slate but no AOV".** B1.5
   intentionally surfaces no inline copy when `opportunity_context` is
   omitted — the experiment card just renders without the block. A
   future product tweak might want to render a small "We will size
   this once a recent AOV is available" line for trust transparency.
   Out of scope for B1.5; the contract path is "render only what is
   defensible".

6. **Selector loops `_build_opportunity_context` per card.** Trivial
   cost (each call is O(1) over a small windows dict). Only matters
   if the cap ever rises above 2; the helper is already idempotent
   per `(audience_size, aligned)` so the loop is correct as-is.

## Readiness for Ticket B2

**Ready.** B2 (forbidden-token sweep extension on Recommended
Experiment) can rely on:

- The Recommended Experiment section now renders with the
  opportunity-context block populated, so B2's scoped sweep on
  `section.recommended-experiment` exercises the full body copy
  including the disclaimer literal "This is not projected lift".
- `OPPORTUNITY_CONTEXT_DISCLAIMER` remains a stable module constant
  in `src/storytelling_v2.py`; B2 can import it to allowlist the
  single permitted occurrence of "projected lift" inside the
  negation.
- The Phase 5.1 helper `_build_opportunity_context` is the single
  producer; B2 does not need to scan multiple AOV paths.
- 15 new B1.5 tests pin the producer contract; B2's sweep can rely on
  consistent rendered output.
- Full suite green at 795 passed, 14 skipped — clean baseline.

B1.5 is also a clean prerequisite for B3 (ABSTAIN_SOFT held-card-to-
Considered routing extension), B4 (role-uniqueness invariant), and B6
(Beauty Brand pinned slate regression). B6 in particular benefits
because the addressable-value sentence is now part of the rendered
output and can be pinned in the slate regression fixture.

## Git Status

Per project convention, changes are NOT committed. Files left unstaged
for review on top of the post-B1 working tree:

B1.5-specific:
- `src/decide.py` (modified): selector + `decide()` gain `aligned`
  kwarg; selector stamps `opportunity_context`.
- `src/main.py` (modified): one-line wiring to pass
  `aligned=aligned_for_template` into `_v2_decide(...)`.
- `tests/test_recommended_experiment_opportunity_context.py` (new): 15 tests.
- `agent_outputs/code-refactor-engineer-phase6a-ticket-b1-5-summary.md`
  (new): this summary.

Pre-existing post-B1 unstaged files (carry-over from prior tickets,
unchanged in B1.5):
- `memory.md`
- `src/storytelling_v2.py` (B1 renderer)
- `tests/test_render_recommended_experiment.py` (B1 tests)
- `agent_outputs/code-refactor-engineer-phase6a-ticket-b1-summary.md`
  (B1 summary)

No goldens modified. No `src/storytelling.py` (legacy renderer)
modified. No `src/engine_run.py` modified in B1.5. No
`src/measurement_builder.py` modified — the helper is reused as-is. No
`config/priors.yaml` or `src/priors_loader.py` modified.
