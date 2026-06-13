# Milestone 6 Summary — Conservative Economic Sizing

_Completed: 2026-05-03 (engine-rework branch)_

## Approved scope

Milestone 6 of `agent_outputs/implementation-manager-overhaul-plan-final.md`:
the conservative economic-sizing layer. Tickets T6.1, T6.2, T6.3, T6.4,
T6.5, T6.6.

- T6.1 — `src/priors_loader.py`: cached, scope-resolving loader for
  `config/priors.yaml`.
- T6.2 — `src/sizing.py:size_play()`: audience x p_action x
  incremental_orders x AOV with no stacked multipliers.
- T6.3 — Suppression rules: cold-start AND targeting-with-non-causal
  prior force `revenue_range.suppressed=true`.
- T6.4 — `revenue_range.drivers[]` provenance: every driver named and
  source-labeled (store_observed | vertical_prior | default | sizing_v2).
- T6.5 — Deprecate `calculate_28d_revenue` only on the V2 path
  (legacy untouched, scheduled for M10 deletion).
- T6.6 — Shadow-compare receipts artifact `v2_sizing_shadow.json`
  per run.

**Out of scope (deferred per the M6 ticket):**

- M7 decision selector / `decide()` / state machine.
- M8 renderer flip / Play Thesis / merchant-facing dollar treatment.
- ML claims, calibrated factors, fake p-values / CIs / effects.
- Klaviyo / Shopify production integrations.
- Legacy code deletion (M10 owns).

## Files changed

### New files

- `/Users/atul.jena/Projects/Personal/beaconai/src/priors_loader.py` —
  T6.1 lazy loader. `load_priors`, `get_prior(play_id, vertical=,
  subvertical=, key=)`, `list_priors_for_play`, `clear_cache`,
  `schema_version`. Caches on first read; resolution preference is
  subvertical > vertical > wildcard. Returns `None` (or `{}`) on any
  failure — never raises.
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py` —
  T6.2/T6.3/T6.4. Pure-function `size_play(SizingInputs) -> RevenueRange`
  plus `shadow_compare(legacy_$, v2_range) -> dict`. Implements the
  conservative formula and the suppression policy.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_loader.py` —
  15 tests (load/cache/scope-resolution/malformed-input).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_sizing.py` —
  16 tests (formula, cold-start suppression, targeting suppression,
  drivers provenance, range invariants, shadow compare).
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/m6_sample_run/` —
  shadow-compare artifacts captured from the small_sm and BM
  fixtures plus the matching engine_run.json receipt.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-milestone-6-summary.md` —
  this file.

### Edited files

- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`:
  - DEFAULTS: added `ENGINE_V2_SIZING` (default false).
  - `_coerce` bool set: extended to include `ENGINE_V2_SIZING`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`:
  - Added a V2-sizing block immediately after `apply_guardrails` (and
    before `engine_run.json` write). Behind `ENGINE_V2_SIZING=true`
    only. Replaces each `PlayCard.revenue_range` with `size_play(...)`,
    sets `engine_run.cold_start` from the M3 `detect_cold_start`
    helper, and writes `receipts/v2_sizing_shadow.json`. Wrapped in
    try/except so the V2 sizing block can never break the run. The
    legacy `actions_log.json`, briefing renderer, and
    `calculate_28d_revenue` path are untouched.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/engine_flags.md`:
  - Last-updated stamp bumped to M6 (2026-05-03).
  - Added the `ENGINE_V2_SIZING` row.

### Pre-existing files (untouched in this milestone)

- `src/action_engine.py:calculate_28d_revenue` — preserved verbatim
  per T6.5; M10 owns deletion.
- `src/engine_run_adapter.py` — unchanged. Still produces the legacy
  `RevenueRange(p50=expected_$, drivers=[legacy_expected_dollars])`
  shape; the M6 V2 block in `main.py` overrides on the V2 path.
- `src/storytelling.py`, `src/briefing.py`, `src/copykit.py`, and any
  template — untouched.
- All other M0 -> M5 files — untouched.

## Exact commands run

```
# T6.1 + T6.2/T6.3/T6.4 unit tests
python -m pytest tests/test_priors_loader.py tests/test_sizing.py -v
# 31 passed in 0.40s

# M2 priors-yaml schema test (asserts only priors_loader.py loads the YAML)
python -m pytest tests/test_priors_yaml.py -v
# 8 passed (still green; the assertion exempts priors_loader.py)

# Golden diff (M4b canonical)
python -m pytest tests/test_golden_diff.py -v
# 3 passed (no re-baseline)

# Full suite
python -m pytest tests/ -q
# 337 passed, 5 skipped

# End-to-end smoke: small_sm with V2 sizing on
ENGINE_V2_SIZING=true \
  python -m src.main --orders data/SM_orders.csv \
                     --brand m6_smoke --out /tmp/m6_smoke
# Shadow file written. All 3 legacy targeting plays correctly suppressed
# under V2 sizing because their priors are expert/observational, not causal.

# End-to-end smoke: BM_orders with V2 sizing on (M4b flags off so larger
# legacy action set surfaces)
ENGINE_V2_SIZING=true STATS_NAN_FOR_HARDCODED=false EVIDENCE_CLASS_ENFORCED=false \
  python -m src.main --orders data/BM_orders.csv \
                     --brand m6_bm --out /tmp/m6_bm
# Same outcome: all targeting plays suppressed; legacy_$ recorded for
# review.

# End-to-end smoke: cold-start fixture
ENGINE_V2_SIZING=true \
  python -m src.main --orders data/shopify_orders_micro_20250826_202615.csv \
                     --brand m6_coldstart --out /tmp/m6_coldstart
# Empty recommendations list; shadow file is empty records list (correct).

# Default flag-off run produces NO v2_sizing_shadow.json (verified)
python -m src.main --orders data/SM_orders.csv \
                  --brand m6_legacy --out /tmp/m6_legacy
# ls shows no v2_sizing_shadow.json under receipts/
```

## Tests / checks run and results

| Suite                                        | Result                  |
|----------------------------------------------|-------------------------|
| `tests/test_priors_loader.py`                | **15 passed**           |
| `tests/test_sizing.py`                       | **16 passed**           |
| M6 sub-total                                 | **31 new tests, 0 fail**|
| `tests/test_priors_yaml.py`                  | **8 passed** (M2 still green; loader carve-out honored) |
| `tests/test_golden_diff.py`                  | **3 passed** (M4b canonical, no re-baseline) |
| Full suite `python -m pytest tests/`         | **337 passed, 5 skipped** |

Full-suite count went from 306 (M5) -> 337 (M6) = +31 new tests. Zero
regressions. Zero golden re-baselines.

## Sizing formula implemented

```
revenue = audience x p_action x incremental_orders x AOV
```

- **`audience`**: `PlayCard.audience.size`, coerced to a non-negative int.
- **`p_action`**: probability that a customer in the audience takes the
  target action over the play's window.
  - measured / directional + `observed_effect` is not None:
    `p_action_p10 = p_action_p50 = p_action_p90 = observed_effect`.
    Driver: `<observed_metric_name>` (default `"observed_effect"`),
    `source = "store_observed"`, with `n` recorded.
  - else: pull `base_rate` prior under
    `(vertical[, subvertical])` from `config/priors.yaml`. The trio is
    `(range_p10, value, range_p90)`. Driver: `base_rate`,
    `source = "vertical_prior"`, `source_class` recorded.
- **`incremental_orders`**: `orders_per_customer` prior (if any) under
  `(play_id, vertical[, subvertical])`. Defaults to 1.0 across p10/p50/p90
  when no prior exists. Driver: `incremental_orders`,
  `source = "vertical_prior"` or `"default"`.
- **`AOV`**: store-level L28 AOV from the aligned KPI snapshot. Driver:
  `aov`, `source = "store_observed"`, `window = "L28"`.

The product is computed at p10, p50, p90 separately, then enforced
monotonic and rounded to cents. NO stacked multipliers (no incrementality,
no frequency-lift, no churn-reduction, no growth-acceleration); the M6
plan and memory.md explicitly forbid that. Each prior used is named in
`drivers[]` so the M9 ML hook can audit it.

`source` label on the resulting `RevenueRange`:

- `store_observed` — `p_action` from observed effect AND no prior used.
- `blend` — `p_action` from observed effect AND incremental_orders prior used.
- `vertical_prior` — `p_action` from base_rate prior.

## Priors loaded

The loader reads `config/priors.yaml` once per process and caches by
absolute path. M2 listed 14 plays; M6 reads the per-play `prior_keys`
the registry already declared.

Entries actually consumed by `size_play` today:

| play_id                 | base_rate prior | orders_per_customer prior |
|-------------------------|---|---|
| `winback_21_45`         | yes (observational, per-vertical) | yes (observational, "*") |
| `bestseller_amplify`    | yes (expert, per-vertical) | no |
| `discount_hygiene`      | yes (expert, "*") + `margin_recovery_rate` (observational) | no |
| `subscription_nudge`    | yes (expert, per-vertical) | no |
| `routine_builder`       | yes (expert, per-vertical) | no |
| `empty_bottle`          | yes (observational, "*") | no |
| `frequency_accelerator` | yes (observational, per-vertical) | no |
| `aov_momentum`          | yes (expert, per-vertical) | no |
| `retention_mastery`     | yes (expert, per-vertical) | no |
| `journey_optimization`  | yes (expert, per-vertical) | no |
| `category_expansion`    | yes (expert, per-vertical) | no |
| `first_to_second_purchase` | yes (expert, "*") | no |
| `at_risk_repeat_buyer_rescue` | yes (expert, "*") | no |
| `onsite_funnel_watch`   | none (registered with empty list — explicitly suppressed) | no |

`incrementality`, `subscription_multiplier`, `frequency_lift`,
`churn_reduction`, `conversion_improvement`, `expansion_rate`,
`growth_acceleration`, `bundle_value`, `margin_recovery_rate`,
`second_purchase_lift` are present in priors.yaml but NOT used by
`size_play` to widen `p_action` or stack multipliers. They remain in the
YAML for traceability and future use; M6 deliberately ignores them.

## Suppression behavior (T6.3)

`size_play` returns `revenue_range.suppressed = True` (and `p10/p50/p90 = None`,
`source = None`) when ANY of the following hold:

1. `cold_start = True` (T6.3 cold-start rule). Driver
   `suppression_reason = "cold_start"`.
2. `audience_size <= 0`. Driver `suppression_reason = "audience_zero"`.
3. `aov <= 0`. Driver `suppression_reason = "aov_zero"`.
4. `evidence_class == "targeting"` AND the resolved `base_rate` prior's
   `source_class != "causal"` AND
   `allow_targeting_unsuppressed=False` (the prod default). Driver
   `suppression_reason = "targeting_non_causal_prior"`. The prior itself
   is still recorded in `drivers[]` (named `base_rate` with the
   `source_class` and `applies_to` fields) so the receipts file shows
   what would have been used.
5. No `base_rate` prior is registered for `(play_id, scope)`. Driver
   `suppression_reason = "no_prior_base_rate"`.
6. `observed_effect` is non-numeric / negative on a measured/directional
   call. Driver `suppression_reason = "observed_effect_invalid"`.

In every suppressed case the `drivers[]` list still carries
`audience_size` and `aov` (so receipts and M9 calibration can audit the
inputs), plus the rule-specific `suppression_reason` driver.

The cold-start engine-level flag is set on `EngineRun.cold_start` from
`detect.detect_cold_start(g, cfg)` (M3 helper, threshold 90 days of clean
data). Until M6 the EngineRun field was hardcoded False; the V2 sizing
block now populates it correctly, also behind `ENGINE_V2_SIZING`.

### Targeting suppression rationale

Per memory.md and the M6 plan, every targeting prior in
`config/priors.yaml` is currently `expert` or `observational`, NOT
`causal`. Today there are zero causal priors. So in practice every
targeting play under V2 sizing is suppressed — exactly as intended.
This is the conservative outcome the M6 ticket calls for: "make impact
estimates more honest, not more impressive."

A test (`test_targeting_with_causal_prior_is_not_suppressed`) uses a
fixture YAML to verify that IF a causal prior were registered, the
targeting suppression would lift. There is also a tests-only escape
hatch (`SizingInputs.allow_targeting_unsuppressed=True`) used by
`test_targeting_unsuppressed_via_test_escape_hatch` to demonstrate the
non-suppressed path.

## Drivers provenance examples (T6.4)

### Measured play with observed effect (winback_21_45)

```json
{
  "p10": 672.0,
  "p50": 832.0,
  "p90": 1056.0,
  "source": "blend",
  "suppressed": false,
  "drivers": [
    {"name": "audience_size", "source": "store_observed", "value": 200},
    {"name": "aov", "source": "store_observed", "value": 80.0, "window": "L28"},
    {"name": "reactivation_rate", "source": "store_observed", "value": 0.04, "n": 200},
    {"name": "incremental_orders", "source": "vertical_prior",
     "source_class": "observational", "value": 1.3, "p10": 1.05, "p90": 1.65,
     "applies_to": {"vertical": "*"}}
  ]
}
```

### Targeting play, suppressed (bestseller_amplify, beauty)

```json
{
  "p10": null,
  "p50": null,
  "p90": null,
  "source": null,
  "suppressed": true,
  "drivers": [
    {"name": "audience_size", "source": "store_observed", "value": 500},
    {"name": "aov", "source": "store_observed", "value": 60.0, "window": "L28"},
    {"name": "base_rate", "source": "vertical_prior",
     "source_class": "expert", "value": 0.18, "applies_to": {"vertical": "beauty"}},
    {"name": "suppression_reason", "source": "sizing_v2",
     "reason": "targeting_non_causal_prior"}
  ]
}
```

### Cold-start, measured play

```json
{
  "p10": null,
  "p50": null,
  "p90": null,
  "source": null,
  "suppressed": true,
  "drivers": [
    {"name": "audience_size", "source": "store_observed", "value": 200},
    {"name": "aov", "source": "store_observed", "value": 80.0, "window": "L28"},
    {"name": "suppression_reason", "source": "sizing_v2", "reason": "cold_start"}
  ]
}
```

Every driver carries `name` and `source`. The forcing-function test
`test_drivers_are_named_and_source_labeled` asserts this for all
drivers, including suppression-reason rows.

## Shadow comparison vs legacy expected_$ (T6.6)

Each V2 run writes `receipts/v2_sizing_shadow.json` keyed by play_id.
Per-record fields:

```
{
  "play_id":              "<id>",
  "evidence_class":       "<measured|directional|targeting|weak>",
  "audience_size":        <int>,
  "aov":                  <float>,
  "cold_start":           <bool>,
  "legacy_expected_dollars": <legacy expected_$>,
  "v2_p10":               <float|null>,
  "v2_p50":               <float|null>,
  "v2_p90":               <float|null>,
  "v2_source":            "store_observed|vertical_prior|blend|null",
  "v2_suppressed":        <bool>,
  "ratio_v2_over_legacy": <v2_p50/legacy_$, or null>
}
```

### Captured artifacts

`agent_outputs/m6_sample_run/v2_sizing_shadow_small_sm.json` (small_sm,
M4b flags ON, beauty vertical):

| play_id              | legacy_$  | v2_p50 | v2_suppressed | reason                          |
|----------------------|-----------|--------|---------------|---------------------------------|
| journey_optimization | $4,545    | null   | true          | targeting_non_causal_prior      |
| bestseller_amplify   | $22,422   | null   | true          | targeting_non_causal_prior      |
| category_expansion   | $55,184   | null   | true          | targeting_non_causal_prior      |

`agent_outputs/m6_sample_run/v2_sizing_shadow_BM.json` (BM, M4b flags OFF):

| play_id              | legacy_$  | v2_p50 | v2_suppressed |
|----------------------|-----------|--------|---------------|
| journey_optimization | $4,337    | null   | true          |
| category_expansion   | $58,151   | null   | true          |
| bestseller_amplify   | $20,092   | null   | true          |

The M6 acceptance criterion was: "V2 p50 should be smaller than legacy
on heuristic plays (because legacy multiplied by Klaviyo benchmarks);
approximately equal on measured plays."

In the current runtime no legacy action carries an `evidence_class`
declaration (the M1 adapter defaults targeting unless the legacy emitter
supplies one, which today none of them do). Every action that surfaces
at the EngineRun layer is therefore classified targeting, the priors
are all expert/observational, and V2 sizing correctly suppresses them.
Legacy `expected_$` continues to flow through the legacy
`actions_log.json` and the legacy briefing untouched (T6.5 contract
preserved). The shadow file shows what V2 would emit instead.

When a measured/directional play does land in `EngineRun.recommendations`
with a non-null `Measurement.observed_effect` (M7's job to wire
canonically), `size_play` will produce a non-suppressed range whose p50
matches `audience x observed_effect x AOV`. The
`test_winback_measured_with_observed_effect` test pins the formula at
`200 x 0.04 x 1.30 x 80 = $832`.

## Impact on current fixtures

### `small_sm` under M4b flag-on (canonical M5 baseline state)

- `recommendations`: 0 (already empty under M4b — the documented
  product-hostile transition state). V2 sizing has nothing to size.
- `cold_start` engine_run field: False (clean L28 data > 90 days).
- `v2_sizing_shadow.json`: not created (the V2 block writes only when
  `ENGINE_V2_SIZING=true`).
- With `ENGINE_V2_SIZING=true`: same 0 recommendations -> empty
  `records[]` in shadow.

### `small_sm` under M4b flags OFF + `ENGINE_V2_SIZING=true`

- 3 legacy targeting actions surface through the M1 adapter.
- All 3 are suppressed by `size_play` because their priors are
  expert/observational.
- Shadow file captures `legacy_expected_dollars` of $4.5K / $22.4K /
  $55.2K vs `v2_p50 = null`.
- `engine_run.json` shows the same 3 PlayCards, now with a
  `revenue_range.suppressed = true` and a 4-element `drivers[]` list per
  card.

### `mid_shopify` and `micro_coldstart`

- Both fixtures already produce 0 recommendations under M4b flag-on.
- Under V2 sizing the shadow file has an empty `records[]`.
- `cold_start` flag flips True/False based on the underlying CSV data
  range; the M3 detector decides.

### `BM_orders` (large fixture)

- 3 legacy targeting plays, same suppression outcome as small_sm.
- Demonstrates that V2 sizing is robust to a 5-figure legacy
  `expected_$` (the BM `category_expansion` legacy estimate is $58K).

## Whether goldens still pass

**Yes. Zero goldens re-baselined.** `tests/test_golden_diff.py`
runs unmodified; it does NOT set `ENGINE_V2_SIZING=true`, so the V2
sizing block is a no-op. M4b canonical goldens remain byte-identical.

`receipts/engine_run.json` is intentionally NOT in the golden tree
(documented in the M0 summary). M6 changes the engine_run.json contents
ONLY when `ENGINE_V2_SIZING=true`. With the flag off, the receipt is
identical to the M5 output.

`receipts/v2_sizing_shadow.json` is a new artifact, only created when
`ENGINE_V2_SIZING=true`. It is not in the golden tree. No legacy
artifact (actions_log.json, validation_report.json, qa_report.json,
briefing HTML) changes shape under M6.

## Skipped items / accepted deviations

None of the listed M6 tickets are skipped.

Accepted notes:

- **No causal priors today.** Every prior in `config/priors.yaml` is
  `expert` or `observational`. As a consequence, every targeting play
  is suppressed under V2 sizing in production. This is by design and
  matches memory.md's "M6 should make impact estimates more honest,
  not more impressive." A causal prior pathway exists; the test
  `test_targeting_with_causal_prior_is_not_suppressed` proves the
  un-suppression branch fires when one is registered.
- **Cold-start detection wired only on the V2 path.** M6's V2 sizing
  block populates `EngineRun.cold_start` from `detect.detect_cold_start`
  (M3 helper). The legacy adapter still hardcodes False; the M5
  `Scale.materiality_floor` field remains tier-aware regardless. M7 will
  wire cold-start at the decide() step.
- **Legacy `calculate_28d_revenue` untouched.** Per T6.5 it remains in
  `src/action_engine.py` and is used by every legacy action emitter.
  M10 deletes it.
- **Drivers `applies_to` payload is preserved as a dict.** M9's
  `recommended_history.json` writer can serialize this as-is. The
  `applies_to` dict can be empty (`{}`) when no scope was registered;
  this is not the same as `None` (which would mean "field omitted").
- **No renderer changes.** `briefing.html` still reads the legacy
  actions list; targeting cards still display merchant-facing dollar
  numbers from the legacy heuristic. M8 owns the renderer flip and
  the targeting `$X,XXX`-headline test (Change 4). Per the M6 ticket
  "What must not change yet — HTML briefing".

## Remaining risks and dependencies for Milestone 7

1. **EngineRun targeting plays do not carry observed effects today.**
   The M1 adapter intentionally drops `Measurement` when
   `evidence_class == "targeting"`. M7's `decide()` is the milestone
   that re-builds plays from the M3 candidate detector with the right
   evidence_class and (where possible) measurement. Until then, V2
   sizing surfaces "all targeting -> all suppressed", which is correct
   but not yet rich. M7 should wire measured/directional plays
   (winback, frequency_accelerator, discount_hygiene, empty_bottle)
   through the new path.

2. **`Scale.materiality_floor` and `revenue_range.p50` are now in
   different units of measurement.** M5's portfolio cap was written
   against legacy `expected_$` mapped to p50; M6 V2 path collapses p50
   to None for suppressed plays. The cap defensively skips suppressed
   ranges already (the cap walks PlayCards with a numeric p50). No
   action item, but M7 reviewers should confirm the cap is still
   well-defined when only a subset of plays carry numeric p50s.

3. **`detect_cold_start` is computed on `g`, not on the underlying
   order-level `df`.** This matches the M3 contract; the M3 detector
   uses the feature-frame's `Created at` range. Until M7 wires a
   single canonical cold-start computation into `decide()`, the V2
   path's cold-start field can in theory differ from a future
   adapter-level field. Today M1 hardcodes False, so the V2 path is
   strictly more accurate.

4. **Shadow file is per-run.** No multi-run aggregation yet. M9 owns
   the time-series outcome log; the M6 shadow file is a snapshot for
   the current run only.

5. **`ENGINE_V2_SIZING` is still default-OFF in `.env` distributions.**
   M7 should NOT flip the default; the renderer gating the merchant
   contract is M8's responsibility.

## Readiness for Milestone 7

**Green to start M7.** M6 acceptance criteria are met:

- For every recommended play in V2, when not suppressed,
  `revenue_range.p10 < revenue_range.p50 < revenue_range.p90` (or all
  equal in the collapsed-range case where no incremental_orders prior
  exists), and `revenue_range.source` is in
  `{store_observed, vertical_prior, blend}`. Verified in
  `test_p10_le_p50_le_p90_for_non_suppressed`.
- Cold-start fixture: every play has `revenue_range.suppressed = true`.
  Verified in `test_cold_start_suppression_for_measured`,
  `test_cold_start_suppression_for_targeting`.
- Measured plays (winback) with observed effect produce
  `source = "store_observed"` (or `"blend"` when an
  `orders_per_customer` prior exists), with the observed metric
  recorded as a single named driver. Verified in
  `test_winback_measured_with_observed_effect`,
  `test_directional_with_observed_effect_no_prior_orders`.
- Targeting plays without a causal prior are suppressed; with a
  causal prior they pass through. Verified in
  `test_targeting_with_expert_prior_is_suppressed`,
  `test_targeting_with_causal_prior_is_not_suppressed`.
- Drivers are always named and source-labeled. Verified in
  `test_drivers_are_named_and_source_labeled`.
- Legacy `calculate_28d_revenue` is untouched; legacy actions log,
  legacy briefing template, and the M0 golden tree are byte-identical
  under flag-off.
- Shadow-compare artifact is produced under `ENGINE_V2_SIZING=true`;
  examples saved under `agent_outputs/m6_sample_run/`.

**M7 prerequisites that M6 satisfies:**

- `size_play(SizingInputs) -> RevenueRange` is a pure function ready
  to call from `src/decide.py`.
- `priors_loader.get_prior` is the canonical accessor; the cache lives
  for the process, so per-play repeated lookups are O(1).
- `EngineRun.cold_start` is now populated correctly under V2; M7's
  abstain logic can read it.
- Drivers schema is locked: `name` (str), `source` (str), plus
  arbitrary key/value extras. M9 calibration can append realized
  factors against these drivers without schema changes.

## Validation summary

- **31 new tests** across 2 new test files. Zero existing tests
  modified.
- **0 regressions** in the 306-test M5 baseline.
- **0 goldens re-baselined.** All 3 M0/M4b fixtures still pass
  byte-identical with the V2 sizing flag off.
- **1 new env flag** added (`ENGINE_V2_SIZING`); default off.
- **2 new modules** added: `src/priors_loader.py`,
  `src/sizing.py`. Both are leaf modules; only `main.py` imports
  them.
- **3 end-to-end smoke runs** (small_sm with V2 on, BM with V2 on +
  M4b off, micro cold-start) confirm the V2 path runs end-to-end and
  produces the expected receipts.
- **Renderer untouched. Briefing template untouched. Legacy
  `calculate_28d_revenue` untouched.** Per the M6 hard NOT-IN-SCOPE
  rule.
