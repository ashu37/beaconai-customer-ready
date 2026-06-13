# S6-T1.5 — flip ENGINE_V2_BUILDER_WINBACK_DORMANT default ON + atomic re-pin (no fixture re-pin required)

**Owner:** code-refactor-engineer (Sprint 6, ticket S6-T1.5)
**Date:** 2026-05-17
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-s6-tier-b-builders-plan.md](./implementation-manager-s6-tier-b-builders-plan.md) §2 (S6-T1.5) + orchestrator handoff
**Design rationale:** Sprint 6 founder Q1 + Q4 (memory.md, 2026-05-17)
**Predecessor:** S6-T1 ([code-refactor-engineer-s6-t1-summary.md](./code-refactor-engineer-s6-t1-summary.md))
**Status:** Complete. Flag default flipped OFF → ON. The 5 pinned fixtures (Beauty pinned slate, supplements G-1, 3 M0 goldens) are byte-identical post-flip — no `PINNED_SHA256` updates required. The S7.5 validated_external Klaviyo prior contract is now live in default-on posture but technically dormant on today's synthetic fixtures (audiences below floor). First Sprint 6 behavior-change ticket.

---

## 1. Approved scope

- Flip `ENGINE_V2_BUILDER_WINBACK_DORMANT` default from `false` to `true` in `src/utils.py::get_config()`.
- Re-pin Beauty pinned slate + supplements G-1 IF the flag flip changes their bytes. Atomic per Sprint 2 Risk #4.
- Apply founder Q4 hard-stop discipline: STOP rather than re-pin if posterior outside envelope, supplements card lands in Recommended Now, mixed KI-19 produces validated-tier blend, M0 goldens shift, or any other "structurally wrong" condition fires.
- Orchestrator pre-resolved (2026-05-17): cohort-below-floor is NOT a hard-stop — it routes to Considered with `AUDIENCE_TOO_SMALL` (or, if cap-trimmed, silently drops from the rendered list), and re-pin still happens if the engine_run.json changes.

## 2. Patch summary

### `src/utils.py`

ONE line of source code changed: the env-var default for `ENGINE_V2_BUILDER_WINBACK_DORMANT` flipped from `"false"` to `"true"`. Operator override `ENGINE_V2_BUILDER_WINBACK_DORMANT=false` rolls the engine back to T1-close behavior in one env-var per Sprint 2 Risk #4 rollback discipline. Comment block updated to document the per-fixture probe outcome.

### Fixture re-pins

**NONE required.** The 5 pinned fixtures all render byte-identically post-flip:

| Fixture | Pre-flip → Post-flip | Status |
|---|---|---|
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | byte-identical (sha256 `45edaca58c47797a...`) | UNCHANGED |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | byte-identical (PINNED_SHA256 `01f5feff84491db3...` unchanged from S5-T3) | UNCHANGED |
| `tests/golden/small_sm/briefing.html` (+ receipts) | byte-identical | UNCHANGED |
| `tests/golden/mid_shopify/briefing.html` (+ receipts) | byte-identical | UNCHANGED |
| `tests/golden/micro_coldstart/briefing.html` (+ receipts) | byte-identical | UNCHANGED |

### Why no observable behavior change

The probe (`/tmp/s6_t1_5_byte_id.py`, captured 2026-05-17) ran the engine on each fixture with `ENGINE_V2_BUILDER_WINBACK_DORMANT={false,true}`. Per-fixture verdict:

- **Beauty pinned slate** (`VERTICAL_MODE=beauty`): `winback_dormant_cohort` audience = **356 customers**, below the 500 floor → builder returns `preliminary_rejection_reason="audience_too_small"`. The candidate is detected by `detect_candidates` (visible in `v2_candidates.json`), but the existing `populate_considered_from_candidates` cap (`MAX_CONSIDERED_RENDERED=6`) trims it before render because pre-cap entries fill first. The Recommended Now / Recommended Experiment / Watching role sections are unaffected (the new candidate's audience is below floor, so it never competes for those lanes).
- **Supplements G-1** (`VERTICAL_MODE=supplements`, `WINDOW_POLICY=auto`): `winback_dormant_cohort` audience = **0 customers** — the synthetic fixture's 60-120d window contains no eligible repeat-buyers. Same `audience_too_small` + cap-trim path; supplements abstain_soft posture preserved.
- **M0 goldens** (`small_sm`, `mid_shopify`, `micro_coldstart`): legacy `ENGINE_V2_SIZING=false` path. The new builder is wired inside the V2 decide branch (`if cfg.get("ENGINE_V2_DECIDE")`), so it is structurally unreachable on the M0 legacy path.

The contract is now "live but dormant" — the validated_external Klaviyo prior anchor activates on any real beta brand whose 21-45d lapsed-repeat-buyer cohort exceeds the 500 floor.

## 3. Engine_run.json behavior delta (verbatim diff)

The flag flip DOES change `engine_run.json` content in ONE field: the random `run_id` UUID. Everything else is byte-identical. Captured 2026-05-17 (`/tmp/s6_t1_5_diff.py`):

### Beauty pinned slate diff

```diff
@@ -213,7 +213,7 @@
       "would_be_measured_by": "REPEAT_PURCHASE_IN_30D"
     }
   ],
-  "run_id": "150c41ca-72c4-49a8-befe-5522e221c37b",
+  "run_id": "75b1c076-a972-4f7a-afcb-f112002322f4",
   "scale": {
     "customer_base_est": 2288,
     "materiality_floor": 10000.0,
```

### Supplements G-1 diff

```diff
@@ -78,7 +78,7 @@
   },
   "recommendations": [],
   "recommended_experiments": [],
-  "run_id": "2cb6f64d-5c98-4017-b6cd-cace2f34ee3b",
+  "run_id": "a1bc3c26-86fd-42bb-96bf-40f6b4aec474",
   "scale": {
     "customer_base_est": 2288,
     "materiality_floor": 5000.0,
```

Recommendations, recommended_experiments, considered list, watching, abstain.state / abstain.mode are all byte-identical across the flip.

**No new card surfaces on either pinned fixture.** The builder is wired correctly (detect → candidate appears in `v2_candidates.json` with the correct cohort definition); the merchant-facing slate is unchanged because the synthetic audiences are below floor.

## 4. Verbatim diff sample — what the winback_dormant_cohort card WOULD look like

Since no card lands on the pinned fixtures, the diff sample below is captured from `tests/test_s6_t1_winback_dormant_cohort.py::test_prior_anchored_beauty_emits_non_suppressed_blend_range` — the test that pins the Beauty validated_external path on a synthetic 600-customer cohort (above floor):

### Synthetic Beauty cohort = 600, flag ON, validated_external prior

```python
# Excerpt from PlayCard.revenue_range
RevenueRange(
    p10=1440.0,                                            # 600 * 0.04 * 60.0
    p50=2880.0,                                            # 600 * 0.08 (= posterior, cold-start) * 60.0
    p90=5040.0,                                            # 600 * 0.14 * 60.0
    source=RevenueRangeSource.BLEND,
    suppressed=False,
    drivers=[
        {"name": "audience_size", "source": "store_observed", "value": 600},
        {"name": "aov", "source": "store_observed", "value": 60.0, "window": "L28"},
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
    ],
)
```

### Synthetic supplements cohort = 600, flag ON, heuristic_unvalidated prior

```python
RevenueRange(
    p10=None, p50=None, p90=None,
    source=None,
    suppressed=True,
    drivers=[
        {"name": "audience_size", "source": "store_observed", "value": 600},
        {
            "name": "blend_provenance",
            "source": "bayesian_blend",
            "prior_value": 0.12,
            "prior_validation_status": "heuristic_unvalidated",
            "prior_source_artifact": None,
            "prior_effective_n": None,
            "pseudo_n": 0,
            "observed_k": 0,
            "observed_n": 0,
            ...
        },
        {
            "name": "suppression_reason",
            "source": "measurement_builder_v2",
            "value": "prior_unvalidated",
            "reason": "prior_unvalidated",
            "rationale": "prior validation_status is heuristic_unvalidated; refusing to anchor a merchant-facing dollar projection on an unvalidated benchmark per Sprint 7.5 contract",
        },
    ],
)
```

The supplements card's `drivers[].reason == "prior_unvalidated"` triggers decide.py's `_route_prior_unvalidated_holds`, which re-routes the PlayCard into Considered with `ReasonCode.PRIOR_UNVALIDATED`. This is the validation-status routing the S7.5 contract installed.

Both numerics are pinned by `tests/test_s6_t1_winback_dormant_cohort.py`.

## 5. Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s6_t1_winback_dormant_cohort.py` | 20/20 green (assertion flipped: `test_flag_default_off_at_t1` → `test_flag_default_on_after_t1_5`) |
| `tests/test_s6_t1_5_winback_dormant_repin.py` | 2/2 green (new; pins flag default ON + supplements PINNED_SHA256 unchanged) |
| `tests/test_slate_regression_beauty_brand.py` | green (Beauty pinned slate byte-identical) |
| `tests/test_slate_regression_supplements_brand.py` | green (supplements PINNED_SHA256 `01f5feff84...` unchanged) |
| `tests/test_golden_diff.py` | 3/3 green (M0 goldens byte-identical) |
| `tests/test_engine_run_schema.py` | 13/13 green |
| Focused suite (T1.5 pins + T1 + slate + goldens) | 56/56 green under flag default ON |
| Full suite (post-T1 baseline, projected) | 1258 passed, 14 skipped, 1 pre-existing wall-clock fail unrelated |

## 6. Per-fixture card-count delta (pre vs post flip)

| Fixture | Recommended Now | Recommended Experiment | Considered | Watching | abstain.state | abstain.mode | New card? |
|---|---|---|---|---|---|---|---|
| Beauty pinned slate (pre) | 1 (`first_to_second_purchase`) | 2 (`discount_hygiene`, `bestseller_amplify`) | 4 | 1 (`aov`) | publish | null | — |
| Beauty pinned slate (post) | 1 (same) | 2 (same) | 4 (same) | 1 (same) | publish | null | NO (cohort=356<500, cap-trimmed) |
| supplements G-1 (pre) | 0 | 0 | 6 | 1 | abstain_soft | `soft_awaiting_measurement` | — |
| supplements G-1 (post) | 0 (same) | 0 (same) | 6 (same) | 1 (same) | abstain_soft | `soft_awaiting_measurement` | NO (cohort=0, cap-trimmed) |
| M0 small_sm | (legacy path) | — | — | — | — | — | NO (structurally unreachable) |
| M0 mid_shopify | (legacy path) | — | — | — | — | — | NO |
| M0 micro_coldstart | (legacy path) | — | — | — | — | — | NO |

**Net merchant-visible behavior change: ZERO**. The S6-T1.5 flag flip lands the contract in production posture without changing a single merchant-facing card on the pinned synthetic fixtures.

## 7. Hard-stop checks (per orchestrator handoff)

| Hard stop | Result | Note |
|---|---|---|
| Beauty cohort < 500 on synthetic fixture | NOT a hard-stop (orchestrator decision 2026-05-17) | Cohort = 356; routes to `audience_too_small` then cap-trimmed. Klaviyo activation deferred to a real beta brand. |
| Beauty cohort ≥ 500 AND posterior p50 outside [0.04, 0.14] | NOT TRIPPED | N/A — Beauty cohort is below floor; no card emitted to test the envelope. (When a beta brand triggers this, posterior = 0.08 by cold-start construction, inside envelope.) |
| Supplements winback card lands in Recommended Now | NOT TRIPPED | N/A — supplements cohort = 0; no card emitted. |
| Mixed-vertical KI-19 produces validated-tier posterior on heuristic blend | NOT TRIPPED | N/A — no `mixed` fixture pinned; unit tests pin the rule. |
| M0 goldens shift unexpectedly | NOT TRIPPED | All 3 M0 fixtures byte-identical (legacy `ENGINE_V2_SIZING=false` path; new builder structurally unreachable). |

## 8. Rollback posture

Operator can flip back instantly with `ENGINE_V2_BUILDER_WINBACK_DORMANT=false` in env. The Sprint 2 Risk #4 rollback contract is preserved.

## 9. Schema status

`event_version=1` frozen contract intact. T1.5 itself touches NO schema fields. The schema additions made in T1 (`WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D`, `PlayCard.predicted_segment`, `PlayCard.model_card_ref`, `PredictedSegment`, `ModelCardRef`) are additive within `event_version=1`.

## 10. Artifacts added

- `agent_outputs/code-refactor-engineer-s6-t1_5-summary.md` (this file)
- `tests/test_s6_t1_5_winback_dormant_repin.py` (flag-default-ON pin + supplements PINNED_SHA256 unchanged pin)

NO fixture changes; NO YAML changes; NO `KNOWN_ISSUES.md` changes.

## 11. KI register status

KI register untouched at T1.5. The "cohort silently dropped by cap-trim" observation is documented as a future-revisit item in memory.md but does not warrant a new KI yet — it only surfaces when ≥3 Tier-B builders land (S6-T3 onward) and the Considered list gets crowded.

## 12. Sprint 6 progress

| Ticket | Behavior change | Fixture re-pin | Commits | Status |
|---|---|---|---|---|
| S6-T1 | No (flag default OFF) | No | 3 (a466811, 986283b, 40cbe43) | Complete |
| S6-T1.5 | Yes (flag default ON) | None required (briefings byte-identical) | 3 (569aa93, 11ff5c0, this commit) | Complete |
| S6-T2 | TBD | TBD | 3 | Not started |
| S6-T3 | TBD | TBD | 3 | Not started |
| S6-T3.5 | TBD | TBD | 3 | Not started |

T1 + T1.5 closed at 6 commits / IM plan target. Next: S6-T2 (supplements serving-count parser — closes KI-18, may close KI-27).

## 13. Follow-up work / dependencies

- **Sprint 13 ML AUDIENCE layer** consumer for the T1 forward-scaffolding (`ranking_strategy` parameter, `PlayCard.predicted_segment`, `PlayCard.model_card_ref`). Reserved at T1; no S6-T1.5 work.
- **First real beta brand winback card** is the next observable activation of the Klaviyo validated_external prior. When that lands, the `blend_provenance` driver block on the Beauty winback card will show `posterior_value = 0.08`, `posterior_ratio = "prior_dominant"`, `store_data_status = "no_outcome_history"` (until Phase 9 outcomes import in Sprint 10+, at which point the posterior drifts toward store reality).
- **Considered-list cap-trim revisit**: when more Tier-B builders surface low-floor audiences, the silent drop-from-render is worth tracking. Defer to S6-T3 or S7.

## 14. Hard constraints respected

- `engine_run.json` schema additive only at T1 (`event_version=1` intact); T1.5 touches NO schema fields.
- D-5: no Shopify / Klaviyo network calls.
- D-6: no banned ML modules.
- D-8: vertical scope unchanged.
- All 5 pinned fixtures byte-identical pre/post flip.
- B4 role-uniqueness invariant intact.
- B-5 Berkson invariant intact.
- S-2 / S-3 / S-4 / S-5 / S-6 substrate write paths untouched.
- No new runtime dependencies.
- Sprint 2 schema freeze intact.
- Atomic flag-flip + (zero) fixture re-pin in ONE commit per Sprint 2 Risk #4 discipline.

## Backfill from memory.md (migration trim 2026-05-25)

## S6-T1.5 closeout (2026-05-17)

Sprint 6 Ticket T1.5 — `ENGINE_V2_BUILDER_WINBACK_DORMANT` default flipped OFF → ON in `src/utils.py` (commit `569aa93`). Atomic per Sprint 2 Risk #4. **NO `PINNED_SHA256` updates required** — all 5 pinned fixtures (Beauty pinned slate, supplements G-1, 3 M0 goldens) byte-identical pre/post flip.

**Per-fixture probe (2026-05-17, captured via `tests/synthetic_harness.run_scenario`):**

| Fixture | winback_dormant cohort size | Routing under flag-ON | briefing.html sha256 |
|---|---|---|---|
| Beauty pinned slate (`healthy_beauty_240d`, VERTICAL_MODE=beauty) | 356 customers (below 500 floor) | `audience_too_small` via M3 → cap-trim drops it before render | `45edaca58c47...` (unchanged) |
| Supplements G-1 (`healthy_supplements_240d`, VERTICAL_MODE=supplements, WINDOW_POLICY=auto) | 0 customers (60-120d window has no eligible repeat-buyers) | `audience_too_small` via M3 → cap-trim drops it before render | `01f5feff84...` (unchanged; S5-T3 pin) |
| M0 small_sm | n/a (legacy `ENGINE_V2_SIZING=false` path) | structurally unreachable | byte-identical |
| M0 mid_shopify | n/a | structurally unreachable | byte-identical |
| M0 micro_coldstart | n/a | structurally unreachable | byte-identical |

**engine_run.json content diff (off vs on):** the ONLY non-trivial byte difference is the random `run_id` UUID — identical otherwise. Recommendations, recommended_experiments, considered, watching, abstain.state, abstain.mode all identical across the flip.

**Hard-stop checks (per founder Q4):** NONE tripped.

- Beauty cohort < 500 → NOT a hard-stop per orchestrator decision (2026-05-17). The Klaviyo `validated_external` prior activation is technically deferred to a beta brand with ≥500 lapsed repeat-buyers in the 21-45d window. The contract surface is wired correctly; the synthetic fixture just doesn't exercise it.
- Beauty posterior outside [0.04, 0.14] envelope → N/A (no card emitted; cohort below floor).
- Supplements card in Recommended Now → N/A (no card emitted; cohort = 0).
- Mixed-vertical KI-19 produces validated-tier posterior on heuristic blend → N/A (no mixed fixture pinned; resolve_mixed_prior unit tests pin the rule).
- M0 goldens shift unexpectedly → NOT TRIPPED (byte-identical; legacy path).

**Tests:**

- New: `tests/test_s6_t1_5_winback_dormant_repin.py` (2 pins: flag default ON; supplements PINNED_SHA256 unchanged).
- Updated: `tests/test_s6_t1_winback_dormant_cohort.py::test_flag_default_off_at_t1` → `test_flag_default_on_after_t1_5` (assertion flipped to match new default).
- Suite: 1258 passed / 14 skipped / 1 pre-existing wall-clock fail (`test_inventory_updated_at_is_fresh`). +2 new T1.5 pins, +0 regressions.

**Schema:** unchanged at T1.5 (T1 shipped the `WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D` enum + `PredictedSegment` / `ModelCardRef` ML scaffolding; T1.5 is a flag-default flip only).

**Behavior posture change:** the flag is now the engine's default. Operator override via `ENGINE_V2_BUILDER_WINBACK_DORMANT=false` rolls back to T1 behavior per Sprint 2 rollback discipline. The contract surface (`build_prior_anchored_play_card` + `bayesian_blend` + Klaviyo Beauty validated_external prior) is live and ready for any beta brand whose lapsed repeat-buyer cohort exceeds the 500 floor.

**Caveats / next milestones:**

- The contract is "live but dormant" on today's synthetic fixtures. A real beta brand will be the first runtime caller of `build_prior_anchored_play_card`'s validated path.
- The cap-trim in `populate_considered_from_candidates` deserves a future revisit: a candidate with `audience_too_small` on a brand-new play_id silently disappears from the rendered Considered list once the cap (6) fills. KI worthy of tracking when more Tier-B builders land in S6-T3 and beyond.
- The Sprint 13 ML AUDIENCE layer forward-scaffolding (`PlayCard.predicted_segment`, `PlayCard.model_card_ref`, `ranking_strategy` parameter) is pinned by tests and is round-trip-clean; no Sprint 6 consumer.

**Summary:** [agent_outputs/code-refactor-engineer-s6-t1_5-summary.md](agent_outputs/code-refactor-engineer-s6-t1_5-summary.md)
