# Play Registry — Contract Reference (Milestone 2)

_Status: schema/config artifact only. NOT read at runtime in M2._

This document describes the typed Play Registry introduced in Milestone 2
(`src/play_registry.py`) and the per-play priors config
(`config/priors.yaml`).

The registry is the single source of truth for which plays the BeaconAI
Action Engine knows how to recommend, what audience builds them, what
metric (if any) is the measured effect, what default evidence class they
carry, and which priors they depend on for sizing.

## Design contract

- **Schema-only in M2.** The legacy decision logic in `_compute_candidates`
  still emits its own candidate dicts using inline constants. Nothing in
  M2 reads from this registry at engine runtime; nothing in M2 reads
  `config/priors.yaml` at runtime.
- **Leaf-level module.** `src/play_registry.py` does NOT import any other
  engine module, to avoid an import cycle when M3 wires the registry into
  candidate detection.
- **No merchant-facing rename.** The legacy plays `retention_mastery` and
  `journey_optimization` are still emitted by the engine and rendered in
  the briefing under their legacy display names. The new `play_id`s
  `at_risk_repeat_buyer_rescue` and `onsite_funnel_watch` are reserved in
  the registry per memory.md, but no merchant copy changes in M2.
- **Hard rule (PM-Q2):** `evidence_class_default == "targeting"` ⇒
  `measurement_metric is None`. Enforced at PlayDef construction.

## Open question (deferred to Phase 2)

`realization_factor` is mentioned in the implementation plan as input to
the calibration stub (M9). M2 does NOT define what shape that number
takes — ratio of realized-to-projected revenue, regression coefficient,
ITT estimate, or something else. Per the M0 plan QA, the call is
deferred. Flagged here so the M9 author re-opens the question with PM
before wiring `data/recommended_history.json`.

## PlayDef schema

```python
@dataclass(frozen=True)
class PlayDef:
    play_id: str
    display_name: str
    evidence_class_default: "measured" | "directional" | "targeting"
    requires_inventory: bool
    audience_builder_ref: str
    measurement_metric: Optional[str]
    vertical_applicable: FrozenSet[str]
    subvertical_applicable: Optional[FrozenSet[str]]
    prior_keys: List[str]
    targeting_disclaimer: Optional[str]
    notes: Optional[str]
```

`evidence_class_default` is the play's class **before** evidence is
evaluated. M4a/M4b can demote a candidate from `measured` to `directional`
or from either to `targeting` based on `n`, `consistency_across_windows`,
and the data quality flags. A play whose default is `targeting` cannot be
promoted upward — there is no measurement.

`requires_inventory == True` plays are gated by M5 against
stock-on-hand: a low-stock SKU cannot back a demand-generation
recommendation. M2 only records the bit; M5 enforces it.

`audience_builder_ref` is a free-text reference to the M3 audience
builder that will produce the candidate. M3 reads this; M2 just records.

## Per-play registry entries

The legacy plays (already emitted by `_compute_candidates`) plus the
three M2-T2.3 new entries.

### Legacy plays

#### `winback_21_45` — Winback 21-45

- **Definition.** Reactivation campaign for customers whose last purchase
  was 21–45 days ago.
- **Audience.** `audience.winback_21_45_inactive` — customers in the
  21–45-day inactivity band.
- **Measurement metric.** `reactivation_rate` (binary: did the customer
  purchase again within the post-window?).
- **Evidence class default.** `measured` (MVP-safe per memory.md when
  enough history exists).
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality`, `orders_per_customer` — all
  per vertical; see `config/priors.yaml`.

#### `bestseller_amplify` — Bestseller Amplify

- **Definition.** Promote the bestselling SKUs to recent buyers.
- **Audience.** `audience.bestseller_buyers`.
- **Measurement metric.** None — this is targeting only.
- **Evidence class default.** `targeting` (memory.md: "targeting only +
  inventory gate").
- **Inventory required?** YES. M5 must verify stock before recommending.
- **Priors.** `base_rate`, `incrementality`, `bundle_value` per vertical.

#### `discount_hygiene` — Discount Hygiene

- **Definition.** Detect and recover margin from over-discounted SKUs.
- **Audience.** `audience.discount_dependent_buyers`.
- **Measurement metric.** `margin_recovery_rate`.
- **Evidence class default.** `measured` (MVP-safe IF discount data is
  reliable).
- **Inventory required?** No.
- **Priors.** `margin_recovery_rate`, `incrementality` per vertical.

#### `subscription_nudge` — Subscription Nudge

- **Definition.** Nudge frequent reorderers of one SKU into a
  subscription.
- **Audience.** `audience.subscription_candidates`.
- **Measurement metric.** None.
- **Evidence class default.** `targeting`.
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality`, `subscription_multiplier`.
- **Open issue (memory.md, Phase 4.2 deferred).** Multiplier-vs-baseline-
  rate conflation + survivorship bias on the ≥3-SKU audience. Resolve
  before any merchant-facing dollar figure is published for this play.

#### `routine_builder` — Routine Builder

- **Definition.** Cross-sell a complementary SKU to single-category
  buyers (e.g., serum buyers → moisturizer).
- **Audience.** `audience.routine_completion_candidates`.
- **Measurement metric.** None.
- **Evidence class default.** `targeting` (memory.md: "targeting only").
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality`, `bundle_value`.
- **Open issue (memory.md, Phase 4.2 deferred).** Welch-t produces a
  p-value only; no measured effect without unit-coherence design work.

#### `empty_bottle` — Replenishment Reminder

- **Definition.** Remind customers near predicted product depletion to
  reorder.
- **Audience.** `audience.depletion_window_buyers`.
- **Measurement metric.** `reorder_rate` (two-proportion z-test against
  non-depleted cohort runs in legacy emitter today).
- **Evidence class default.** `directional`. M4a/M4b will demote to
  `targeting` when `n` is below the directional threshold.
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality`.

#### `frequency_accelerator` — Frequency Accelerator

- **Definition.** Push repeat customers to buy more often.
- **Audience.** `audience.repeat_cohort`.
- **Measurement metric.** `orders_per_customer`.
- **Evidence class default.** `measured` (MVP-safe with caveats per
  memory.md).
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality`, `frequency_lift`.
- **M4a note.** Remove the assumed lift exposure from merchant-facing
  output; report only the observed cohort effect.

#### `aov_momentum` — AOV Momentum

- **Definition.** Capitalize on observed AOV growth in a recent window.
- **Audience.** `audience.aov_growth_cohort`.
- **Measurement metric.** `aov_growth_rate`.
- **Evidence class default.** `directional` only (memory.md: "do not
  forecast lift from observed AOV drift").
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality`, `growth_acceleration`.

#### `retention_mastery` — Retention Mastery (legacy)

- **Definition.** Re-engage at-risk repeat buyers.
- **Audience.** `audience.retention_at_risk`.
- **Measurement metric.** None — legacy assumed-churn-reduction must be
  removed.
- **Evidence class default.** `targeting` (memory.md: "remove assumed
  churn reduction"; rename target is `at_risk_repeat_buyer_rescue`).
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality`, and (legacy)
  `churn_reduction` — kept in `priors.yaml` for traceability; M4a NaN's
  the merchant-facing exposure.

#### `journey_optimization` — Journey Optimization (legacy)

- **Definition.** Guide customers through the early-funnel journey.
- **Audience.** `audience.journey_one_purchase_cohort`.
- **Measurement metric.** None — onsite funnel data is not available
  from the local CSV pipeline.
- **Evidence class default.** `targeting` (memory.md: "rename or demote
  until onsite funnel data exists"). The new ID `onsite_funnel_watch` is
  reserved for the M7 watching list; no engine logic in M2.
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality`, `conversion_improvement` —
  the latter is kept for traceability and is gated to be unmeasured.

#### `category_expansion` — Category Expansion

- **Definition.** Cross-sell into a new category.
- **Audience.** `audience.single_category_buyers`.
- **Measurement metric.** None.
- **Evidence class default.** `targeting` (memory.md: "targeting only;
  remove fabricated stats").
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality`, `expansion_rate`.

### M2-T2.3 new entries

#### `first_to_second_purchase` — First-to-Second Purchase

- **Definition.** Prompt single-purchase customers to a second purchase.
- **Audience.** `audience.single_purchase_cohort`.
- **Measurement metric.** `second_purchase_rate` — binary first→second
  conversion, computable from CSV history alone.
- **Evidence class default.** `measured` (memory.md: "MVP-safe and
  preferred replacement for Journey Optimization").
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality`, `second_purchase_lift` —
  placeholder priors only; M3 computes observational baseline from CSV.
- **M2 status.** Reserved play_id; no engine logic yet.

#### `at_risk_repeat_buyer_rescue` — At-Risk Repeat Buyer Rescue

- **Definition.** Rescue repeat buyers who are drifting toward churn.
- **Audience.** `audience.at_risk_repeat_buyers`.
- **Measurement metric.** None.
- **Evidence class default.** `targeting` (memory.md: "remove assumed
  churn reduction"; targeting until a defensible measurement design is
  in place).
- **Inventory required?** No.
- **Priors.** `base_rate`, `incrementality` — intentionally NO
  `churn_reduction` prior (per memory.md).
- **M2 status.** Reserved play_id; legacy `retention_mastery` emitter
  still produces output today.

#### `onsite_funnel_watch` — Onsite Funnel Watch

- **Definition.** Watching-only signal for storefront funnel anomalies.
- **Audience.** `audience.onsite_funnel_observation`.
- **Measurement metric.** None — onsite data is not available locally.
- **Evidence class default.** `targeting` (per T2.3: "Mark the latter as
  evidence_class_default='targeting' until onsite data exists").
- **Inventory required?** No.
- **Priors.** None today; reserved for future onsite integration.
- **M2 status.** Reserved play_id; M7 will use this on the watching list.

## Priors config (`config/priors.yaml`)

Schema per entry:

| Key            | Type                                         | Notes                                           |
|----------------|----------------------------------------------|-------------------------------------------------|
| `name`         | string                                       | Matches a key in `PlayDef.prior_keys`.          |
| `value`        | number                                       | Point estimate (legacy inline constant).        |
| `range_p10`    | number                                       | Conservative low bound.                         |
| `range_p90`    | number                                       | Conservative high bound.                        |
| `source_class` | `observational` \| `causal` \| `expert`      | See "Source class" below.                       |
| `last_updated` | ISO date string                              | When the value was set or reviewed.             |
| `applies_to`   | `{ vertical, subvertical?, business_stage? }`| Scope. `vertical: "*"` means all verticals.     |
| `notes`        | string (optional)                            | Free-text caveats.                              |

### Source class

- **observational** — derived from the engine's CSV-only observational
  analyses (no randomized counterfactual). Use for base rates and
  conversion that come from cohort-level history.
- **causal** — derived from a randomized or quasi-experimental study.
  None today; reserved for the future.
- **expert** — SME judgement / industry benchmark / heuristic. The
  conservative fallback.

When uncertain, prefer the more conservative class:
**expert** > **observational** > **causal** (more conservative = less
specific evidence). Most M2 entries are labeled `expert`; only base
rates with at least some CSV-derived support are labeled `observational`.

## Sanity tests

- `tests/test_play_registry.py` — every legacy emitted `play_id` is
  registered; PlayDef schema invariants hold; the three new T2.3 entries
  are present.
- `tests/test_priors_yaml.py` — schema keys present, `source_class` is
  one of the three allowed values, ranges are ordered, value is inside
  the range, runtime modules do NOT load `priors.yaml` (M2 invariant).

## Migration roadmap

| Milestone | What changes for the registry / priors |
|-----------|----------------------------------------|
| M2        | Schema + config landed; not read at runtime. |
| M3        | `detect_candidates(...)` reads `PLAYS` to gate `play_id` and look up `audience_builder_ref`. Inline constants in `action_engine.py` still drive sizing. |
| M4a       | Targeting plays' p/q/CI/measured-effect fields NaN'd when classified as targeting (per `evidence_class_default`). |
| M4b       | Combiner reroute reads `evidence_class_default` to decide which combiner branch a candidate flows through. |
| M6        | New `src/priors_loader.py` reads `config/priors.yaml`. `revenue_range` is computed from priors with `drivers[]` provenance. |
| M10       | Inline `get_conversion_rates` / `get_incrementality_factors` / `get_effect_params` constants are deleted from `action_engine.py`; only `priors.yaml` remains. |
