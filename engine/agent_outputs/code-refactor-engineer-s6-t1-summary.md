# S6-T1 — winback_dormant_cohort builder + ENGINE_V2_BUILDER_WINBACK_DORMANT flag (default OFF)

**Owner:** code-refactor-engineer (Sprint 6, ticket S6-T1)
**Date:** 2026-05-17
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-s6-tier-b-builders-plan.md](./implementation-manager-s6-tier-b-builders-plan.md) §2 (S6-T1)
**Design rationale:** `ARCHITECTURE_PLAN.md` Part I §B-1 (winback_dormant_cohort)
**Predecessor:** S7.5-T3.5 ([code-refactor-engineer-s7_5-t3_5-summary.md](./code-refactor-engineer-s7_5-t3_5-summary.md))
**Status:** Complete. Flag default OFF. The 5 pinned fixtures are byte-identical post-impl — no `PINNED_SHA256` updates required at T1. T1.5 owns the flag flip + atomic re-pin.

---

## 1. Approved scope

- Ship `winback_dormant_cohort` Tier-B builder per ARCHITECTURE_PLAN Part I §B-1 behind `ENGINE_V2_BUILDER_WINBACK_DORMANT` (default OFF).
- 3-part cohort definition: vertical-aware last-order recency window + ≥2 prior orders + no order in past 28 days.
- Measurement pathway anchors the PlayCard posterior on `winback_21_45.base_rate` via `bayesian_blend`.
- Validation-status routing (Sprint 7.5 contract): `validated_external` priors emit non-suppressed `BLEND`-sourced revenue ranges; `heuristic_unvalidated` priors route to Considered with `PRIOR_UNVALIDATED` (resolved via decide.py's existing `_route_prior_unvalidated_holds`).
- Forward-scaffolding (added at orchestrator direction, 2026-05-17): reserve `ranking_strategy` parameter on the audience builder and `PredictedSegment` / `ModelCardRef` typed slots on `PlayCard` for the Sprint 10–13 ML AUDIENCE layer.

Founder pre-locked (per orchestrator handoff, 2026-05-17):

- **Q1**: Beauty dormancy 21–45d; Supplements 60–120d; ≥2 prior orders required.
- **Q4**: Hard-stop discipline ACTIVE at T1.5 (not T1; T1 is impl-only).

Orchestrator resolutions (2026-05-17, after I flagged 4 scope tensions):

- **Lane for supplements winback card**: Considered with `PRIOR_UNVALIDATED` (NOT Recommended Now with suppressed range). IM plan reading wins over handoff.
- **Measurement-builder shape**: new `build_prior_anchored_play_card` pathway parallel to `build_directional_play_card`. Cold-start `observed_k=observed_n=0` → posterior collapses to prior.
- **L28-no-recent-activity filter**: implement as written. 3-part cohort.
- **Hard-stop on cohort < 500**: NOT a hard-stop. Routes to Considered with `AUDIENCE_TOO_SMALL`; re-pin still happens. Real hard-stops are math-anomaly / validation-gate-broken conditions.

## 2. Patch summary

### `src/audience_builders.py`

New `winback_dormant_cohort_candidates(g, aligned, cfg, *, ranking_strategy=None)`. Returns the standard `AudienceResult`. Vertical-aware window via `cfg["VERTICAL_MODE"]`:

- `beauty` → 21–45 days lapsed.
- `supplements` → 60–120 days lapsed.
- Anything else (including `mixed`) → 21–45 days (the more conservative cohort definition; the prior-side mixed blend is independently gated by `resolve_mixed_prior`'s KI-19 conservative-min rule, which already refuses heuristic-unvalidated blends at the measurement-builder seam).

Cohort algorithm:

1. `last_by_cust = gg.groupby("customer_id")["Created at"].max()`; recency = `(maxd - last_by_cust).dt.days`. Keep customers with `recency ∈ [wb_lo, wb_hi]`.
2. `order_counts = gg["customer_id"].value_counts()`; intersect with recency set keeping customers with ≥2 lifetime orders.
3. `l28_active = customers with any order in past 28d`; subtract from the running set.

Audience floor: 500 (architecture-plan default). Customers < 500 ⇒ `preliminary_rejection_reason="audience_too_small"` so downstream `populate_considered_from_candidates` routes the candidate to Considered with `AUDIENCE_TOO_SMALL`.

The L28-no-recent-activity filter is structurally **redundant** for the supplements 60–120d window (`days_since ≥ 60 > 28` for every cohort member) and only catches the [21, 28] day band on beauty. That is the correct narrow surface — `max(Created at)` per customer drives the recency filter, so L28-active customers are already excluded by the recency gate for everything except the 21–28d boundary. I left the explicit L28 filter in as written by the orchestrator; documenting its narrowness here so a future reader doesn't conclude it's broader than it is.

Registered as `audience.winback_dormant_cohort` in the `BUILDERS` dispatch dict.

### `src/measurement_builder.py`

New parallel pathway `build_prior_anchored_play_card(candidate, aligned, *, vertical, subvertical, primary_window, observed_k=0, observed_n=0)`. The existing `build_directional_play_card` is the **wrong template** for cohort-existence plays — it requires `aligned[primary].p[metric] < 0.05` + sign-stability across windows and hard-codes `revenue_range.suppressed=True`. The new pathway:

1. Looks up the prior via `get_prior(prior_play_id="winback_21_45", key="base_rate", vertical=...)` (or `resolve_mixed_prior` for vertical=mixed).
2. Computes the cold-start posterior: `bayesian_blend(prior_value, pseudo_n_for_status, store_value=prior_value, n_observed=0)` → posterior = prior. **This is not a no-op**; it's the cold-start state. Once Phase 9 outcomes flow back (Sprint 10+), `observed_k` / `observed_n` populate and the posterior drifts toward store reality.
3. Emits a typed `blend_provenance` driver block:
   ```json
   {
     "name": "blend_provenance",
     "source": "bayesian_blend",
     "prior_value": 0.08,
     "prior_source_class": "observational",
     "prior_validation_status": "validated_external",
     "prior_source_artifact": "config/priors_sources/winback_21_45__base_rate__beauty.md",
     "prior_effective_n": 30,
     "pseudo_n": 30,
     "observed_k": 0,
     "observed_n": 0,
     "store_data_status": "no_outcome_history",
     "posterior_value": 0.08,
     "posterior_ratio": "prior_dominant",
     "expected_calibration_path": "phase_9_outcome_loop",
     "applies_to": {"vertical": "beauty"}
   }
   ```
4. Validation-status routing (Sprint 7.5 contract):
   - `validated_*` / `elicited_expert` + AOV available → non-suppressed `RevenueRange` with `source=RevenueRangeSource.BLEND`. Range is `audience × posterior × aov` for p50; `audience × prior.range_p10 × aov` / `audience × prior.range_p90 × aov` for p10/p90.
   - `heuristic_unvalidated` / `placeholder` → suppressed range with `drivers[].reason="prior_unvalidated"`. decide.py's `_route_prior_unvalidated_holds` re-routes the PlayCard into Considered with `ReasonCode.PRIOR_UNVALIDATED`. This is how the supplements winback card lands in Considered without a second routing layer.
   - AOV missing on validated path → suppressed with `reason="aov_unavailable"` (store-side, not prior_unvalidated; play is NOT re-routed to PRIOR_UNVALIDATED).
5. PlayCard carries `evidence_class=DIRECTIONAL`, `confidence_label="Emerging"`, `would_be_measured_by=LAPSED_REACTIVATION_IN_30D`, and an `OpportunityContext` block via the existing `_build_opportunity_context` helper.

Companion `build_prior_anchored_recommendations(candidates, aligned, *, vertical, subvertical, existing_recommendation_ids, primary_window)` iterates candidates with the same `_PRIOR_ANCHORED` registry idiom as `build_directional_recommendations`.

### `src/main.py`

Wires `build_prior_anchored_recommendations` under `cfg.get("ENGINE_V2_BUILDER_WINBACK_DORMANT", False)`, inside the existing V2 decide branch, immediately after the directional rebuild. Gate-routed conditions (`ABSTAIN_HARD` or `ABSTAIN_SOFT + data-quality flags`) hold back the prior-anchored builder for the same reasons that hold back the directional builder.

### `src/play_registry.py`

New `winback_dormant_cohort` PlayDef: `evidence_class_default="directional"`, `audience_builder_ref="audience.winback_dormant_cohort"`, `measurement_metric="reactivation_rate"`, `vertical_applicable=_ALL_VERTICALS`, `prior_keys=["base_rate"]`. Notes block documents the 3-part cohort definition + the prior-anchored measurement pathway.

### `src/engine_run.py`

Three additive changes within `event_version=1` frozen contract:

1. `WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D = "LAPSED_REACTIVATION_IN_30D"` — UPPER_SNAKE_CASE per the A2 invariant.
2. `PredictedSegment(notes: Optional[str] = None)` — stub dataclass for the Sprint 10–13 ML AUDIENCE layer. Fields will be filled in by Sprint 13.
3. `ModelCardRef(notes: Optional[str] = None)` — stub dataclass for ML model lineage. Fields will be filled in by Sprint 13.
4. `PlayCard.predicted_segment: Optional[PredictedSegment] = None` + `PlayCard.model_card_ref: Optional[ModelCardRef] = None`. Round-trip wired via `_from_dict_predicted_segment` / `_from_dict_model_card_ref` (called from `_from_dict_play_card`).

These four are the **forward-scaffolding for the Sprint 10–13 ML AUDIENCE layer** the orchestrator added at the eleventh hour. They cost ~30 lines, zero behavior change, and prevent a future refactor when the Sprint 13 ML AUDIENCE layer lands.

### `src/utils.py`

New `ENGINE_V2_BUILDER_WINBACK_DORMANT` flag, default `false`. Added to the `_BOOL_FLAGS` typed-coercion set so env-var overrides work. T1.5 will flip the default to `true`.

### `tests/test_s6_t1_winback_dormant_cohort.py`

20 new tests across the audience-builder, measurement-builder, registry, flag, enum, ML scaffolding, and `detect_candidates` dispatch surfaces. Key cases:

- Beauty 21–45d window fires; supplements 60–120d window fires.
- Below-floor (100 customers) routes to `audience_too_small`.
- Single-purchase-only cohort excluded by ≥2-prior-orders filter.
- Self-reactivated (L28-active) customers excluded.
- Beauty prior-anchored card has non-suppressed BLEND-sourced revenue range with cold-start `blend_provenance`.
- Supplements prior-anchored card is suppressed with `prior_unvalidated` reason (routed to Considered downstream).
- Mixed vertical → KI-19 conservative-min refuses (suppressed + prior_unvalidated).
- Sprint 13 `ranking_strategy` parameter accepted as no-op; `PredictedSegment` / `ModelCardRef` round-trip cleanly.

### `tests/test_would_be_measured_by_enum.py` + `tests/test_engine_run_schema.py`

Both `WouldBeMeasuredBy` member-set pins updated 3 → 4 to reflect the additive `LAPSED_REACTIVATION_IN_30D` value. Per the Sprint 6 anchor memory note: additive only; no enum-narrowing.

## 3. Validation-status routing diagram

Under `ENGINE_V2_BUILDER_WINBACK_DORMANT=true` + `ENGINE_V2_PRIORS_VALIDATION=true` (the T1.5 default state):

| Vertical | Prior validation_status | PlayCard | RevenueRange | Final lane |
|---|---|---|---|---|
| beauty | `validated_external` (Klaviyo) | emitted | non-suppressed, `source=BLEND`, posterior=0.08 cold-start | Recommended Now |
| supplements | `heuristic_unvalidated` | emitted | suppressed, `drivers[].reason="prior_unvalidated"` | Considered with `PRIOR_UNVALIDATED` |
| mixed | `heuristic_unvalidated` (KI-19) | emitted | suppressed, `drivers[].reason="prior_unvalidated"` | Considered with `PRIOR_UNVALIDATED` |

When the audience cohort is below floor 500 on any vertical: builder returns `preliminary_rejection_reason="audience_too_small"`, no PlayCard emitted, candidate routes to Considered with `AUDIENCE_TOO_SMALL` via `populate_considered_from_candidates`.

## 4. Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s6_t1_winback_dormant_cohort.py` | 20/20 green |
| `tests/test_slate_regression_beauty_brand.py` | green (Beauty pinned slate byte-identical) |
| `tests/test_slate_regression_supplements_brand.py` | green (supplements G-1 sha256 `01f5feff84...` unchanged) |
| `tests/test_golden_diff.py` | 3/3 green (M0 goldens byte-identical) |
| `tests/test_engine_run_schema.py` | 13/13 green (round-trip incl. new ML scaffolding) |
| `tests/test_would_be_measured_by_enum.py` | green (4-member pin) |
| `tests/test_audience_builders.py` | green |
| `tests/test_play_registry.py` | green |
| Full suite | 1256 passed, 14 skipped, 1 failed (`test_inventory_updated_at_is_fresh`, pre-existing wall-clock drift, unrelated) |

## 5. Per-fixture card-count delta (flag OFF — the T1 contract)

| Fixture | Recommended Now | Recommended Experiment | Considered | Watching | abstain.state | abstain.mode |
|---|---|---|---|---|---|---|
| Beauty pinned slate | 1 (`first_to_second_purchase`) — UNCHANGED | 2 — UNCHANGED | 4 — UNCHANGED | 1 (`aov`) — UNCHANGED | publish | null |
| supplements G-1 | 0 — UNCHANGED | 0 — UNCHANGED | 6 — UNCHANGED | 1 — UNCHANGED | abstain_soft | `soft_awaiting_measurement` |
| M0 small_sm | (legacy path) — UNCHANGED | — | — | — | — | — |
| M0 mid_shopify | (legacy path) — UNCHANGED | — | — | — | — | — |
| M0 micro_coldstart | (legacy path) — UNCHANGED | — | — | — | — | — |

**Net merchant-visible behavior change: ZERO**. The flag is structurally inert at T1.

## 6. Risk register / what could go wrong at T1.5

These are the conditions T1.5 will exercise (hard-stop discipline per founder Q4):

| Condition | Hard-stop? | Resolution |
|---|---|---|
| Beauty cohort ≥ 500, posterior p50 inside [0.04, 0.14] | NO | Atomic re-pin; new Recommended Now card. |
| Beauty cohort < 500 | **NO** (per orchestrator 2026-05-17) | Card routes to Considered with `AUDIENCE_TOO_SMALL`. Re-pin still happens because a new Considered entry is a real engine_run.json change. |
| Beauty cohort ≥ 500, posterior p50 outside [0.04, 0.14] | **YES** | STOP, ping orchestrator. Should not happen given cold-start posterior collapses to prior=0.08 (mid-envelope). |
| Supplements winback card lands in Recommended Now (not Considered) | **YES** | STOP. Validation gate is broken. |
| Mixed-vertical KI-19 produces a `validated_*` posterior on a heuristic blend | **YES** | STOP. KI-19 contract broken. |
| M0 goldens shift unexpectedly | **YES** | STOP. The legacy `ENGINE_V2_SIZING=false` path is structurally unreachable by the new builder; if M0 shifts, something is wired wrong. |

## 7. Remaining risks / known limitations

- **Cold-start blend collapse is intentional.** A future reader looking at the T1.5 fixture and seeing `posterior_value == prior_value == 0.08` might conclude the `bayesian_blend` call is dead. It is not — `observed_n=0` is the correct cold-start input. The `store_data_status="no_outcome_history"` driver field documents this explicitly. Once Phase 9 imports outcomes (Sprint 10+), `observed_n` populates and the posterior moves.
- **Audience floor is hard-coded at 500.** Future ticket should route this through `get_audience_floor("winback_dormant_cohort", vertical)` via priors-metadata once Sprint 6 / 7 authors a `winback_dormant_cohort.metadata` block. Today the floor is a constant in the audience builder; raising it cannot be done by ops without code change.
- **The L28-no-recent-activity filter is narrowly active.** Only catches the [21, 28]-day band on beauty (supplements' 60-day floor is already > 28). Documented in §2 above.
- **The Sprint 13 forward-scaffolding has zero S6 consumers.** This was an orchestrator call, not in the IM plan. The two `PlayCard` slots default to `None` and round-trip clean; the stub classes carry only a `notes` field that future ML work will replace. The cost is ~30 lines + 1 test; the benefit is no schema-evolution work when Sprint 13 lands.

## 8. Rollback posture

Operator can flip back instantly with `ENGINE_V2_BUILDER_WINBACK_DORMANT=false` in env. The Sprint 2 Risk #4 rollback contract is preserved.

## 9. Schema status

`event_version=1` frozen contract intact. T1 additions are all `Optional` / additive:

- `WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D` (additive enum value).
- `PlayCard.predicted_segment` / `PlayCard.model_card_ref` (Optional fields defaulting to `None`).
- `PredictedSegment` / `ModelCardRef` (stub dataclasses).

No fixture re-pin triggered.

## 10. Artifacts added

- `agent_outputs/code-refactor-engineer-s6-t1-summary.md` (this file)
- `tests/test_s6_t1_winback_dormant_cohort.py`

## 11. Commit list

1. `a466811` — `S6-T1: winback_dormant_cohort builder + ENGINE_V2_BUILDER_WINBACK_DORMANT flag (default OFF)` (impl + tests, 9 files, 1005 insertions / 3 deletions)
2. `986283b` — `Document S6-T1 in repo memory.md`
3. _(this commit)_ — `S6-T1 summary`

## 12. Forward-scaffolding for Sprint 10–13 ML AUDIENCE layer

Per orchestrator direction (2026-05-17), two hooks were reserved at T1 so the Sprint 13 ML AUDIENCE layer can land without refactoring shipped code:

**Hook 1 — `ranking_strategy` parameter on the audience builder.**
`winback_dormant_cohort_candidates(g, aligned, cfg, *, ranking_strategy=None)`. Sprint 13 will populate `ranking_strategy` with a typed enum value from `{"predicted_ltv_desc", "p_alive_x_value_desc", "rfm_quintile"}` to rank the cohort BEFORE the audience floor / materiality gates apply. Today the parameter is accepted, type-validated (str-or-None), and ignored. The signature is reserved so a future refactor cannot silently drop it; a pin test (`test_audience_builder_accepts_ranking_strategy_param_no_op`) keeps the signature stable.

**Hook 2 — `PlayCard.predicted_segment` and `PlayCard.model_card_ref` typed slots.**
Two new `Optional[<TypeName>] = None` fields on `PlayCard`. Stub dataclasses `PredictedSegment(notes=None)` and `ModelCardRef(notes=None)` defined as minimal placeholders. The Sprint 13 ML AUDIENCE layer will replace `notes` with the real fields (`predicted_segment.top_decile_ltv`, `p_alive_summary`, `expected_recovered_revenue_range`; `model_card_ref.model_id`, `fit_date`, `training_window`, `holdout_mape`, `ModelFitStatus`). Default `None` keeps every existing fixture byte-identical; round-trip through `to_dict` / `from_dict` is pinned by `test_playcard_has_reserved_ml_scaffolding_slots`.

Both hooks follow the same forward-scaffolding pattern as Sprint 7.5-T3's `bayesian_blend` helper (which T1 now consumes): defined one sprint ahead of its consumer, pinned by a test so it cannot drift before the consumer arrives.

## 13. Hard constraints respected

- `engine_run.json` schema additive only (`event_version=1` intact).
- D-5: no Shopify / Klaviyo network calls.
- D-6: no banned ML modules (Sprint 13 scaffolding is type-only, no runtime ML code).
- D-8: vertical scope unchanged.
- All 5 pinned fixtures byte-identical under flag-OFF (today's default).
- B4 role-uniqueness invariant intact.
- B-5 Berkson invariant intact (no per-window cohort cross-comparison in the new builder).
- S-2 / S-3 / S-4 / S-5 / S-6 substrate write paths untouched.
- No new runtime dependencies.
- Sprint 2 schema freeze intact.
- Atomic flag-flip + fixture re-pin deferred to T1.5 per Sprint 2 Risk #4 discipline.

## 14. KI register status

KI register untouched at T1. T1.5 will revisit if the atomic re-pin surfaces any new observed-vs-pinned issues. KI-19 conservative-min on `mixed` is now exercised end-to-end on the winback card (test pins the suppression posture).

## 15. T1.5 readiness

T1.5 is unblocked. Next actions: flip `ENGINE_V2_BUILDER_WINBACK_DORMANT` default to `true` in `src/utils.py`, run the engine on Beauty + supplements + M0 fixtures with the new flag ON, capture the verbatim `engine_run.json` diffs, apply the hard-stop discipline (per §6), and either atomically re-pin OR stop and ping the orchestrator.

## Backfill from memory.md (migration trim 2026-05-25)

## S6-T1 closeout (2026-05-17)

Sprint 6 Ticket T1 — `winback_dormant_cohort` builder shipped behind `ENGINE_V2_BUILDER_WINBACK_DORMANT` (default OFF). Impl-only commit: ZERO merchant-facing behavior change on every pinned fixture under flag-OFF (Beauty pinned slate + supplements G-1 + 3 M0 goldens all byte-identical). Commit `a466811`.

**Patch surface:**

- `src/audience_builders.py`: new `winback_dormant_cohort_candidates`. 3-part cohort definition per founder Q1 (2026-05-17): vertical-aware last-order recency window (beauty 21–45d / supplements 60–120d), ≥2 prior orders, no order in past 28d. Audience floor 500 (architecture-plan default; merchant-facing threshold — do NOT lower). Registered as `audience.winback_dormant_cohort` in `BUILDERS`. The L28-no-recent-activity filter is structurally redundant for supplements (60–120d window guarantees no L28 activity) and only catches the [21, 28]-day band on beauty; that is the correct narrow surface — `max(Created at)` per customer drives the recency filter, so L28-active customers are already excluded by the recency gate for everything except the 21–28d boundary.
- `src/measurement_builder.py`: new `build_prior_anchored_play_card` pathway PARALLEL to `build_directional_play_card` (which gates on `aligned[primary].p[metric]<0.05` + sign-stability and is wrong for cohort-existence plays). The prior-anchored path bypasses p-value gates and anchors the PlayCard posterior on `winback_21_45.base_rate` via `bayesian_blend(prior, pseudo_n, store_value, n_observed)`. **Cold-start posture**: at T1.5 default state, no campaign outcomes exist (Phase 9 outcome loop is Sprint 10+), so `observed_k = observed_n = 0` and the posterior collapses to the prior. The `blend_provenance` driver block surfaces this honestly: `store_data_status="no_outcome_history"`, `posterior_ratio="prior_dominant"`, `expected_calibration_path="phase_9_outcome_loop"`. **NOT a no-op** — once Phase 9 imports outcomes, `observed_n` populates and the posterior drifts toward store reality.
- **Validation-status routing** (Sprint 7.5 contract): `validated_external` / `validated_internal` / `elicited_expert` priors emit non-suppressed `RevenueRange` with `source=BLEND`; `heuristic_unvalidated` / `placeholder` priors emit suppressed range with `drivers[].reason="prior_unvalidated"` so decide.py's `_route_prior_unvalidated_holds` re-routes the PlayCard into Considered with `ReasonCode.PRIOR_UNVALIDATED`. **Orchestrator decision (2026-05-17)**: supplements winback lands in Considered (not Recommended Now with suppressed range), per the S7.5 typed-reason contract. The handoff's original "Recommended Now with suppressed range" reading was wrong; the IM plan's "Considered with PRIOR_UNVALIDATED" reading wins.
- **Mixed vertical**: `resolve_mixed_prior` already applies KI-19 conservative-min on `validation_status`; the existing `winback_21_45.base_rate` mixed entry is `heuristic_unvalidated`, so the mixed posterior is refused at the measurement-builder seam (matches beauty's heuristic_unvalidated path).
- `src/main.py`: wires `build_prior_anchored_recommendations` under `ENGINE_V2_BUILDER_WINBACK_DORMANT`, inside the existing V2 decide branch after the directional rebuild. Gate-routed conditions (ABSTAIN_HARD or ABSTAIN_SOFT with data-quality flags) hold back the prior-anchored builder for the same reasons.
- `src/play_registry.py`: new `winback_dormant_cohort` PlayDef (`evidence_class_default="directional"`, `vertical_applicable=_ALL_VERTICALS`).
- `src/engine_run.py`: `WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D` added (additive within `event_version=1`).
- `src/utils.py`: `ENGINE_V2_BUILDER_WINBACK_DORMANT` flag (default OFF).

**Sprint 10–13 ML AUDIENCE layer forward-scaffolding** (added at orchestrator direction, 2026-05-17):

- `winback_dormant_cohort_candidates` accepts an optional `ranking_strategy: Optional[str]` kw-only parameter. No-op today; Sprint 13 will populate it with `{"predicted_ltv_desc", "p_alive_x_value_desc", "rfm_quintile"}` to rank the cohort BEFORE audience floor / materiality gates apply. Signature is reserved so a refactor cannot silently drop it.
- `PlayCard` gains two typed slots `predicted_segment: Optional[PredictedSegment] = None` and `model_card_ref: Optional[ModelCardRef] = None`. Stub dataclasses (`PredictedSegment(notes=None)`, `ModelCardRef(notes=None)`) defined as minimal placeholders; the Sprint 13 ML AUDIENCE layer will fill in real fields. Round-trip through `to_dict` / `from_dict` is pinned by a test. Default `None` keeps every existing fixture byte-identical.
- Rationale: avoids a future refactor when the ML layer lands — same forward-scaffolding pattern as S7.5-T3's `bayesian_blend` helper (added one sprint before its consumers).

**Tests:** new `tests/test_s6_t1_winback_dormant_cohort.py` (20 tests covering cohort definition, validation-status routing, mixed-vertical KI-19 refusal, flag default-OFF pin, ML scaffolding round-trip, detect_candidates dispatch). Suite: 1256 passed (was 1237 baseline + 19 new — one extra is the schema scaffolding test) / 14 skipped / 1 pre-existing wall-clock fail (`test_inventory_updated_at_is_fresh`, unrelated).

**Schema additions (all additive within `event_version=1`):** `WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D`; `PlayCard.predicted_segment`; `PlayCard.model_card_ref`; stub classes `PredictedSegment` and `ModelCardRef`. Two enum pin tests (`test_would_be_measured_by_has_exactly_three_members` → `_four_members`; `test_would_be_measured_by_enum_values_are_uppercase_snake`) updated to reflect the 4-member set.

**Fixtures:** ALL 5 pinned fixtures byte-identical under flag-OFF. NO `PINNED_SHA256` updates required at T1. T1.5 will exercise the atomic re-pin discipline when the flag flips.

**Caveats / next milestones:**

- T1.5 may discover that the synthetic Beauty fixture's winback cohort is < 500 (the audience floor). Per orchestrator decision (2026-05-17): if cohort < 500, the new card routes to Considered with `AUDIENCE_TOO_SMALL` — that is correct behavior, NOT a hard-stop. Re-pin still happens because a new Considered entry IS a real engine_run.json change.
- Real hard-stops remain: posterior p50 outside [0.04, 0.14] envelope WHEN audience ≥ 500; supplements card lands in Recommended Now (validation gate broken); mixed-vertical KI-19 produces a validated-tier posterior on a heuristic blend; M0 goldens shift unexpectedly.
