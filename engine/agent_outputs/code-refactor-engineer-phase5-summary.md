# Phase 5 Summary — Useful V2 on Beauty Brand

_Completed: 2026-05-03 (engine-rework branch)_

## Approved scope

Phase 5 of the BeaconAI decision-core overhaul (per the engineering brief
and `agent_outputs/legacy-vs-v2-final-recommendation.md`):

- 5.1 Rewrite ABSTAIN_SOFT copy.
- 5.2 Populate the considered list during ABSTAIN_SOFT.
- 5.3 Extend Watching schema (returning_customer_share, net_sales, stable
  load-bearing render, repeat-rate not-computed handling).
- 5.4 Make materiality footer merchant-readable.
- 5.5 Ensure Aura / Beacon score does not appear in V2.
- 5.6 Wire one measured/directional pathway from M3 into V2 (chosen play:
  `first_to_second_purchase`, supported by the `returning_customer_share`
  signal, with revenue suppressed).
- 5.7 Defensive cleanup: suppress `journey_optimization` from the V2
  considered/recommendation paths.

Out of scope (and intentionally NOT done):

- M10 cleanup, V2 default flip.
- Removing legacy emitter code.
- Lowering materiality floor.
- Adding fake p-values, CIs, confidence_score, final_score.
- Restoring Aura/Beacon score in V2.
- Klaviyo / Shopify integration.
- Adding any causal prior. The wired Phase 5.6 pathway uses an existing
  expert prior path AND suppresses the revenue range explicitly; no
  prior was relabeled as causal.

## Files changed

New files:
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py`
  — Phase 5.6 directional PlayCard builder. Pure function.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_phase5_abstain_copy.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_phase5_considered_always.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_phase5_watching_signals.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_phase5_materiality_copy.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_phase5_no_aura_beacon.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_phase5_measured_pathway.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_phase5_journey_optimization_suppressed.py`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/phase5_samples/beauty_brand_v2_briefing.html`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/phase5_samples/beauty_brand_engine_run.json`

Edited files:
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py`
  - Added `ABSTAIN_SOFT_DEFAULT_REASON` + `ABSTAIN_SOFT_REASONS` map.
  - Added `_abstain_soft_reason_text(considered)` to pick the merchant-
    readable reason from the dominant gate.
  - Updated `_decide_abstain_state` to accept `considered` and use it.
  - Replaced `_WOULD_FIRE_IF_TEMPLATE` strings with the merchant-readable
    "Would fire if ..." sentences from the brief.
  - Added `populate_considered_from_candidates()` (Phase 5.2): maps M3
    Candidates to `RejectedPlay` entries with reason_code, reason_text,
    evidence_snapshot, and would_fire_if.
  - Added `_LOAD_BEARING_WATCH_METRICS` and softened `build_watching` to
    surface flat load-bearing metrics as `trend="flat"` (Phase 5.3).
  - Extended `_threshold_text` with `returning_customer_share` and
    `net_sales` thresholds.
  - Added `PHASE5_V2_SUPPRESS_PLAY_IDS` (Phase 5.7) and filtered
    `journey_optimization` out of both considered and recommendations.
- `/Users/atul.jena/Projects/Personal/beaconai/src/state_of_store.py`
  - Added `_has_identified_customers` guard.
  - Added `returning_customer_share` and `net_sales` Observations.
  - Suppressed `repeat_rate_within_window` with a "not computed" label
    when no identified customers exist (Phase 5.3).
  - Relaxed observation cap from 5 to 7 to fit the new metrics.
- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling_v2.py`
  - Replaced ABSTAIN_SOFT callout label/copy with merchant-readable
    "No primary play this month." + the decide()-supplied reason
    (Phase 5.1).
  - Replaced "Materiality floor: $X" footer line with merchant-readable
    "We only recommend primary plays that could realistically add at
    least $X this month for a store your size." (Phase 5.4). The exact
    numeric floor remains in `receipts/debug.html` for engineering
    review.
  - Updated header subtitle to "What we evaluated this month and what
    we are watching." for ABSTAIN_SOFT.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`
  - Added a Phase 5.2/5.6 wiring block (behind `ENGINE_V2_DECIDE` only)
    that runs `detect_candidates`, calls
    `build_directional_recommendations`, appends the resulting card to
    `recommendations`, then calls `populate_considered_from_candidates`
    BEFORE `decide()` so the abstain reason text reflects the dominant
    gate. Failure is non-fatal (try/except wraps the entire block).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_render_v2.py`
  - Updated two ABSTAIN_SOFT assertions to look for the new "No primary
    play this month" label rather than the old "No measured opportunities
    cleared" (Phase 5.1).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_decide.py`
  - Updated `test_targeting_only_yields_abstain_soft` to assert the
    merchant-readable reason text (no jargon).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_observations.py`
  - Renamed `test_returns_at_most_five_observations` to
    `test_returns_at_most_seven_observations` to reflect the Phase 5.3
    relaxed cap.

Untouched (intentionally):
- `src/storytelling.py`, `templates/briefing.html.j2` — legacy renderer.
- `src/action_engine.py` — legacy emitter.
- `src/sizing.py` — Phase 5.6 explicitly does NOT call `size_play` for
  the directional card; revenue is suppressed at the
  `measurement_builder` boundary.
- `config/priors.yaml` — no priors added or changed; no causal relabel.
- `tests/golden/` — no goldens re-baselined.

## Exact commands run

```
# Per-subtask test runs (interleaved with implementation):
python -m pytest tests/test_phase5_abstain_copy.py -v
python -m pytest tests/test_phase5_considered_always.py -v
python -m pytest tests/test_phase5_watching_signals.py -v
python -m pytest tests/test_phase5_materiality_copy.py -v
python -m pytest tests/test_phase5_no_aura_beacon.py -v
python -m pytest tests/test_phase5_measured_pathway.py -v
python -m pytest tests/test_phase5_journey_optimization_suppressed.py -v

# Full suite (post-Phase 5):
python -m pytest tests/ -q
# 487 passed, 5 skipped

# Golden diff (legacy unchanged):
python -m pytest tests/test_golden_diff.py -v
# 3 passed (no re-baseline)

# Targeting no-dollar-headline invariant (M8 contract):
python -m pytest tests/test_targeting_no_dollar_headline.py -v
# 6 passed

# End-to-end on Beauty Brand (full V2 stack):
ENGINE_V2_OUTPUT=true ENGINE_V2_DECIDE=true ENGINE_V2_SIZING=true \
STATS_NAN_FOR_HARDCODED=true EVIDENCE_CLASS_ENFORCED=true \
TARGETING_RECLASSIFY_PLAYS=true MATERIALITY_FLOOR_SCALE_AWARE=true \
CANNIBALIZATION_GATE_ENABLED=true ANOMALY_GATE_ENABLED=true \
VERTICAL_MODE=beauty \
  python -m src.main --orders data/beauty_brand_orders.csv \
                     --brand beauty_brand_phase5_final \
                     --out /tmp/phase5_final

# Default-mode (no V2 flags) regression check:
python -m src.main --orders data/SM_orders.csv \
                  --brand sm_default --out /tmp/phase5_default

# V2 stack on small_sm and mid_shopify:
... (same env stack) python -m src.main --orders data/SM_orders.csv ...
... (same env stack) python -m src.main --orders data/shopify_orders_mid.csv ...
```

## Tests / checks run and results

| Suite                                                         | Result                |
|---------------------------------------------------------------|-----------------------|
| `tests/test_phase5_abstain_copy.py`                           | 8 passed              |
| `tests/test_phase5_considered_always.py`                      | 10 passed             |
| `tests/test_phase5_watching_signals.py`                       | 9 passed              |
| `tests/test_phase5_materiality_copy.py`                       | 4 passed              |
| `tests/test_phase5_no_aura_beacon.py`                         | 4 passed              |
| `tests/test_phase5_measured_pathway.py`                       | 14 passed             |
| `tests/test_phase5_journey_optimization_suppressed.py`        | 4 passed              |
| `tests/test_decide.py`                                        | 34 passed (1 updated) |
| `tests/test_render_v2.py`                                     | 24 passed (2 updated) |
| `tests/test_observations.py`                                  | 8 passed (1 updated)  |
| `tests/test_targeting_no_dollar_headline.py`                  | 6 passed              |
| `tests/test_golden_diff.py`                                   | 3 passed              |
| **Full suite `python -m pytest tests/`**                      | **487 passed, 5 skipped** |

Pre-Phase-5 baseline: 434 passed, 5 skipped. New tests: +53 (8+10+9+4+4+14+4).

## What was implemented

### 5.1 — Merchant-readable ABSTAIN_SOFT copy

- New `decide.ABSTAIN_SOFT_DEFAULT_REASON`: "Your store is healthy this
  month. We did not find a play with strong enough evidence to recommend
  as a primary action. Here is what we evaluated and what we are
  watching."
- Three keyed alternates (`materiality`, `overlap`, `no_measured`) selected
  by `_abstain_soft_reason_text(considered)` based on the dominant
  upstream rejection gate.
- V2 callout label is now "No primary play this month." (not "No
  measured opportunities cleared").
- Old jargon ("materiality + cannibalization gating") cannot leak into
  the briefing or the EngineRun.

### 5.2 — Considered list always populated

- New `decide.populate_considered_from_candidates(engine_run, candidates,
  registry, vertical, subvertical)` returns a new `EngineRun` with
  `considered[]` populated from M3 candidates that did not become
  recommendations.
- Each item carries `play_id`, `reason_code`, `reason_text`,
  `evidence_snapshot` (audience size + segment definition), and
  `would_fire_if`.
- M3's `preliminary_rejection_reason` is mapped via `_PRELIM_REASON_MAP`
  to typed `ReasonCode`s. Unmapped registry entries default to
  `NO_MEASURED_SIGNAL` for targeting plays (until calibration data
  exists).
- Caps at `MAX_CONSIDERED_RENDERED = 6`.
- Wired in `main.py` behind `ENGINE_V2_DECIDE=true`.

### 5.3 — Watching schema extended

- Added `returning_customer_share` and `net_sales` thresholds to
  `_threshold_text`.
- Added `_LOAD_BEARING_WATCH_METRICS = {orders, net_sales,
  returning_customer_share, repeat_rate_within_window}`. HELD
  observations on these metrics with zero/missing change still surface
  with `trend="flat"` so the page is not empty on a healthy store.
- `state_of_store.build_observations` now emits
  `returning_customer_share` and `net_sales` Observations and the cap is
  relaxed from 5 to 7.
- `repeat_rate_within_window` is rendered as "Repeat rate (L28): not
  computed (no identified customers in the window)" rather than
  "0.0%" when `meta.identified_recent` is zero.

### 5.4 — Merchant-readable materiality footer

- Replaced the V2 footer line "Materiality floor: $X" with "We only
  recommend primary plays that could realistically add at least $X this
  month for a store your size."
- The exact internal floor value is preserved verbatim in
  `receipts/debug.html` for engineering review (not surfaced to
  merchants).

### 5.5 — Aura / Beacon score forbidden

- New test file `test_phase5_no_aura_beacon.py` with four tests covering
  PUBLISH, ABSTAIN_SOFT, ABSTAIN_HARD, and composite-phrase variations.
- Forbidden tokens: `Aura`, `Beacon Score`, `health_score`, `aura_score`,
  `Aura Score`, `Health Score`, `/100`, `(healthy)`, `(at risk)`,
  `tier:`, `composite score`. None appear in any V2 layout.
- Legacy code that computes Aura/beacon score is intentionally NOT
  removed; it is simply not read by the V2 renderer.

### 5.6 — One directional pathway wired

- New module `src/measurement_builder.py`. Two public functions:
  - `build_directional_play_card(candidate, aligned, ...)` returns a
    typed `PlayCard` with `evidence_class=DIRECTIONAL` for the wired
    play `first_to_second_purchase` when:
    - the candidate's audience cleared the M3 minimum-N gate
    - L28 `returning_customer_share` p < `PHASE5_DIRECTIONAL_P_MAX`
      (default 0.05)
    - sign agreement across windows >= `PHASE5_DIRECTIONAL_MIN_CONSISTENCY`
      (default 2)
  - `build_directional_recommendations(candidates, aligned,
    existing_recommendation_ids, primary_window)` iterates and skips
    candidates already in recommendations.
- The card carries a typed `Measurement(metric="returning_customer_share",
  observed_effect=L28 delta, n=identified_recent, primary_window="L28",
  consistency_across_windows=N, p_internal=L28 p)` — `p_internal` is
  internal only and never rendered.
- The card's `revenue_range.suppressed = True`. Drivers list documents
  the reason ("directional_no_intervention_effect") and carries the
  metric value + delta + consistency for receipts/debug.html.
- Wired in `main.py` BEFORE `populate_considered_from_candidates` and
  BEFORE `decide()`. The directional card flows through the M5
  guardrails, the M7 abstain state machine, and the M8 renderer
  unmodified.
- This pathway intentionally does NOT call `src.sizing.size_play` with
  the supporting metric as `observed_effect`. The supporting metric is
  a state statistic (per-window fraction of customers with prior
  history), not an intervention effect; using it to size revenue would
  be sizing fabrication. `revenue_range.suppressed=True` is the safer,
  spec-aligned choice.
- The wired play `first_to_second_purchase` uses the existing M2
  `expert` prior in `config/priors.yaml`. NO causal prior was added.

### 5.7 — journey_optimization defensively suppressed in V2

- `decide.PHASE5_V2_SUPPRESS_PLAY_IDS = frozenset({"journey_optimization"})`.
- Filter applied in both `populate_considered_from_candidates` and
  `decide()` before ranking. Even if a future legacy adapter accidentally
  surfaces `journey_optimization` with measured-class evidence, the V2
  pipeline drops it before it can render.
- Legacy emitter is NOT modified (memory.md, hard prohibitions, golden
  invariants).

## What was skipped and why

- **M10 cleanup**: explicitly out of scope for Phase 5.
- **Removing legacy emitter code for journey_optimization**: hard
  prohibition. Defensive 5.7 suppression handles the V2 risk surface.
- **Lowering materiality floor**: hard prohibition.
- **Adding a causal prior**: hard caution. Phase 5.6 chose the safer
  "directional with suppressed revenue" path so no expert prior is
  relabeled as causal. The Phase 5.6 pathway can later be promoted to
  measured + non-suppressed revenue once campaign realization data
  exists (M9 `materiality_overrides` / `prior_overrides` is the home).
- **Adding `vertical_not_applicable` ReasonCode**: minor scope, not
  needed for Phase 5 acceptance. The current `populate_considered`
  function quietly suppresses non-applicable plays rather than rendering
  a confusing "Held: vertical_not_applicable" card. Can be added later
  if PM wants visible "we considered this but it does not apply".
- **Removing "BeaconAI" product name**: the product name is allowed
  (test only forbids the score variants `Aura`, `Beacon Score`,
  `health_score`).

## Beauty Brand before / after

### Before (start of Phase 5, M0–M9 baseline)

- decision_state: `abstain_soft`
- abstain.reason: "no measured or directional recommendation cleared
  materiality + cannibalization gating"
- recommendations: 0
- considered: 0
- watching: 0
- briefing.html: ~50 lines, three empty-state placeholders, jargon
  callout, "Materiality floor: $10,000" footer.

### After (Phase 5.1–5.7)

- decision_state: `publish`
- abstain.reason: None (PUBLISH)
- recommendations: 1 (`first_to_second_purchase`, evidence_class=
  `directional`, audience=286, measurement carries
  `returning_customer_share` +6.6% / consistency=3 / n=962 /
  p_internal=9.5e-05, revenue_range.suppressed=True)
- considered: 6 (winback_21_45, bestseller_amplify, discount_hygiene,
  subscription_nudge, routine_builder, empty_bottle — each with
  `reason_code`, `reason_text`, `evidence_snapshot`, `would_fire_if`)
- watching: 2 (`net_sales` up; `orders` flat — both with thresholds)
- briefing.html: still 50 lines (compact CSS + small content), but
  populated content between state-of-store and footer:
  - State of store paragraph with 5 facts including the new
    `returning-customer share (L28): 91.5% (+6.6% vs prior)` and
    `net sales (L28): $94,405 (+1.7% vs prior)`.
  - One Recommended directional card with title + Emerging badge +
    recommendation + why_now + audience block + observed metric line +
    fixed disclaimer. No $ headline.
  - Six Considered cards with merchant-readable reason summaries +
    detail lines + would-fire-if templates.
  - Watching list with two rows.
  - Merchant-readable materiality footer.
- ZERO forbidden statistical strings (verified mechanically):
  no `p =`, `q =`, `CI`, `confidence_score`, `final_score`, `p_internal`,
  `ci_internal`, `Aura`, `Beacon Score`, `/100`, `materiality +
  cannibalization gating`, `Materiality floor:`.

### Other fixtures

- **small_sm**: ABSTAIN_SOFT, recs=0, considered=6, watching=1
  (returning_customer_share flat). Page is now populated.
- **mid_shopify**: ABSTAIN_SOFT, recs=0, considered=6, watching=4
  (net_sales down, orders down, repeat_rate flat,
  returning_customer_share flat). Page is now populated.

## Is V2 useful enough for manual testing now?

**Yes.** All three real fixtures now produce briefings with populated
content:

- `briefing.html` is no longer near-empty on Beauty Brand (it now has
  one populated Recommended directional card).
- Considered list explains what was evaluated on every fixture.
- Watching list has 1+ entries on every fixture.
- ABSTAIN_SOFT (when it fires) reads as merchant English, not jargon.
- Forbidden-string contract holds.
- Targeting no-dollar-headline invariant holds.
- Legacy CSV -> HTML default workflow byte-equivalent.

The Phase 5 acceptance criteria from the engineering brief are all met:
- Considered renders >= 3 entries on Beauty Brand: 6 (passes >=3).
- Watching renders >= 1 entry on Beauty Brand: 2 (passes >=1).
- Recommended renders 1 defensible directional card on Beauty Brand.
- Forbidden statistical strings sweep: 0 leaks.
- Targeting cards still suppress dollar headlines.
- recommended_history.json writes safely without PII.

## Was a causal prior added?

**No.** Phase 5.6 explicitly chose the conservative "directional with
suppressed revenue" pathway to avoid relabeling any expert prior as
causal. The wired play uses the existing `expert` prior in
`config/priors.yaml`, and the directional card's revenue range is
suppressed by the `measurement_builder` boundary so no calibrated lift
estimate is implied.

## Whether full tests pass

**Yes.** 487 passed, 5 skipped (the 5 skips are M4a-era unrelated
suspended cases; same as the M9 baseline).

## Remaining risks

1. **`returning_customer_share` is a state statistic, not an
   intervention effect.** The Phase 5.6 directional card is
   defensible because the metric is sign-stable across windows with
   p < 0.05 — but a future agent could be tempted to promote it to
   measured + non-suppressed revenue. The
   `measurement_builder._SupportingSignal.rationale` docstring + the
   `revenue_range.drivers` suppression note are the forcing function
   that prevent this without explicit calibration data.

2. **`evidence_class=DIRECTIONAL` with `consistency_across_windows=3`
   could theoretically flow through to a "Strong" badge if a future
   change loosens the renderer's class-to-label mapping.** Today
   `_render_measured_card` maps DIRECTIONAL -> "Emerging", which is
   correct. The forbidden-string sweep + the test
   `test_v2_briefing_renders_directional_recommended_card` pin the
   "Emerging" label.

3. **Phase 5.7 suppresses `journey_optimization` only on the V2 path.**
   The legacy emitter still produces it. If a future agent flips
   `ENGINE_V2_OUTPUT=true` as the default before M10 and there is a
   bug in the V2 wiring, journey_optimization could re-leak via the
   legacy adapter. The defense in `decide()` filters it again before
   ranking, but the deeper fix (delete from the legacy emitter) is
   M10 work.

4. **The Phase 5.2 considered-list filter on `vertical_applicable`
   silently suppresses non-applicable plays.** If PM later wants the
   merchant to see "we considered this but it does not apply", we will
   need to add a `VERTICAL_NOT_APPLICABLE` ReasonCode and surface it
   in the considered card. Today this is a hidden subset.

5. **The V2 directional path runs M3 detect on every V2-flag run.**
   This is a re-run of the same audience builders the legacy adapter
   may have already run, plus the cannibalization-gate path that
   `main.py` runs when `CANNIBALIZATION_GATE_ENABLED=true`. The cost is
   small but not zero. If runtime becomes a concern, the M3
   detect_candidates result can be cached on the run.

6. **state_of_store cap is relaxed from 5 to 7.** Synthetic tests
   updated; the M1 contract docstring still says 3-5. This drift is
   intentional but documented in the test rename. A follow-up PR
   should sync the docstring.

## Recommendation

**Proceed to manual testing.** The V2 briefing on Beauty Brand is now
substantively useful (1 directional + 6 considered + 2 watching +
merchant-readable copy + zero forbidden strings). The two other real
fixtures (small_sm, mid_shopify) also have populated content under
ABSTAIN_SOFT.

If manual testing confirms the directional copy reads well, the next
follow-on work is:

- Wire `at_risk_repeat_buyer_rescue` similarly when its M3 audience
  builder lands (currently `no_builder`).
- Author one calibrated causal prior for `first_to_second_purchase`
  using campaign realization data once it exists, then promote to
  measured + non-suppressed revenue.
- Defer M10 default flip until at least one more brand fixture has
  been validated in manual testing.

Phase 5 work is shippable independently of M10.
