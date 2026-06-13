# Milestone 3 Summary — Candidate Detection Surface (Shadow Mode)

Status: complete, shadow-only, M0 goldens held in default mode.

## Scope (approved)

Implement the M3 candidate detector as a shadow surface behind `ENGINE_V2_SHADOW=true`:

- T3.1: AudienceResult / `audience_builders.py` — pure per-play audience rules
  ported from legacy `_compute_candidates` with no statistics, no scoring, no
  revenue.
- T3.2: `detect.py` Candidate schema + `detect_candidates()` iterator over the
  M2 `play_registry.PLAYS` registry.
- T3.3: `src/main.py` shadow wiring — flag-gated write to
  `receipts/v2_candidates.json`; default mode produces no v2 artifacts and the
  legacy CSV->HTML briefing path is byte-identical to the M0 goldens.
- T3.4: `detect_cold_start(g, cfg)` — logged-only flag stamped on every
  candidate; never gates or filters in M3.
- T3.5: `compute_audience_overlap(audiences)` — pairwise Jaccard; attached to
  every emitted candidate.
- M3 forbidden-fields enforcement: `Candidate` carries no `p_value`,
  `q_value`, `confidence`, `revenue`, `ci_low`, `ci_high`, `measured_effect`,
  `score`, `rank`, or `recommended`. The deny-list is codified as
  `FORBIDDEN_CANDIDATE_FIELDS` in `src/detect.py` and asserted by
  `tests/test_detect_candidates.py` and `tests/test_audience_builders.py`.

Out of scope (intentionally deferred): scoring, gating, filtering, evidence
classification, priors, and any merchant-facing changes. M5 owns gates; M4a/M4b
own evidence classification.

## Files changed

New files:

- `/Users/atul.jena/Projects/Personal/beaconai/src/audience_builders.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/detect.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_audience_builders.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_audience_overlap.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_detect_candidates.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_engine_v2_shadow.py`

Edited files:

- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` — adds the
  ENGINE_V2_SHADOW-gated block (lines 560-604) that calls
  `detect_candidates()` and writes `receipts/v2_candidates.json`. Block is a
  total no-op when the flag is unset/false.

## Commands run

```
python -m pytest tests/test_audience_builders.py
python -m pytest tests/test_audience_overlap.py
python -m pytest tests/test_detect_candidates.py
python -m pytest tests/test_engine_v2_shadow.py

# Sample shadow-mode artifact generation against M0 micro_coldstart fixture:
ENGINE_V2_SHADOW=true python -c "<freeze_golden._run_engine on micro_coldstart>"
```

The shadow invocation routed through `scripts/freeze_golden.py::_run_engine`,
which calls `src.main.run(csv_path, brand, out_dir)` end-to-end with
`ENGINE_V2_SHADOW=true` in the process environment.

## Tests / checks run

| Suite                                 | Result    |
| ------------------------------------- | --------- |
| `tests/test_audience_builders.py`     | 28 passed |
| `tests/test_audience_overlap.py`      | 14 passed |
| `tests/test_detect_candidates.py`     | 12 passed |
| `tests/test_engine_v2_shadow.py`      | 3 passed (one per M0 fixture: `micro_coldstart`, `small_sm`, `mid_shopify`) |

Total: 57 passed, 0 failed across the M3 suites. The shadow integration test
runs the full engine on each of the three M0 fixtures with
`ENGINE_V2_SHADOW=true`, validates that `receipts/v2_candidates.json` is
written and conforms to the slim schema, and re-runs the M0 golden byte-diff
under shadow mode to prove the legacy pipeline did not drift.

## Artifacts created

Sample shadow-mode receipt (real artifact from micro_coldstart fixture run):

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/m3_sample_run/receipts/v2_candidates.json`

The full sample run output tree (briefing HTML, charts, segments, all
receipts) lives under
`/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/m3_sample_run/` for
spot-checks. The receipt contains 14 candidate entries — one per play in the
M2 registry — with audience size, segment definition, data fields used,
preliminary rejection reason, cold-start flag, and pairwise audience overlap.

## Default-mode confirmation

When `ENGINE_V2_SHADOW` is unset or set to any falsey value (`false`, `0`,
`no`, `off`, empty), `src/main.py` lines 568-604 short-circuit at the
`if _shadow in (...)` guard. No imports from `src.detect` or
`src.play_registry` execute, no `v2_candidates.json` is written, and the
legacy CSV->HTML briefing pipeline is bit-for-bit unchanged.

This is asserted in two layers:

1. `tests/test_golden_diff.py` — exercises the default path against all three
   M0 fixtures and diffs the captured outputs against `tests/golden/`.
2. `tests/test_engine_v2_shadow.py` — runs the engine with the flag ON, then
   re-applies the freeze normalization and compares against the same
   `tests/golden/` tree, proving the shadow code path also doesn't perturb
   legacy outputs.

## Pre-existing flake — out of scope

`tests/test_golden_diff.py` is unrelated to M3 but flakes intermittently
(~40% on `small_sm` standalone) due to legacy ULP-level float drift in
`engine_validation_report.json` and `run_summary.json`. Drifting fields
observed:

- `effect_size`
- `ci_high`
- `expected_$`
- `final_score`

These values are written by the legacy `src/action_engine.py` (and the
multi-window engine validator), not by any M3 code. The shadow detector
writes only the four new fields in `Candidate.to_dict()` and never touches
the legacy receipt files. We confirmed the drift reproduces with M3 code
removed (the M0 freeze workflow has the same float-stability issue), so it
predates this milestone.

Recommendation: file a separate "golden-test float stability" ticket to
canonicalize the legacy float-precision serialization (round at write time,
or shrink the small_sm fixture to a deterministic subset). It should not
block M3 sign-off and should not touch `src/action_engine.py` ahead of M4a.

## Candidate coverage table

Every legacy `play_id` ever emitted by `_compute_candidates` is covered by an
M3 audience builder. The two reserved-but-unbuilt registry entries from M2
T2.3 are intentionally surfaced as `preliminary_rejection_reason="no_builder"`
candidates — the registry is the source of truth, and "no builder yet" is a
visible signal rather than a silent omission.

| Registry play_id              | Audience builder ref                       | Builder fn                        | Status      |
| ----------------------------- | ------------------------------------------ | --------------------------------- | ----------- |
| `winback_21_45`               | `audience.winback_21_45_inactive`          | `winback_21_45`                   | covered     |
| `bestseller_amplify`          | `audience.bestseller_buyers`               | `bestseller_buyers`               | covered     |
| `discount_hygiene`            | `audience.discount_dependent_buyers`       | `discount_dependent_buyers`       | covered     |
| `subscription_nudge`          | `audience.subscription_candidates`         | `subscription_candidates`         | covered     |
| `routine_builder`             | `audience.routine_completion_candidates`   | `routine_completion_candidates`   | covered     |
| `empty_bottle`                | `audience.depletion_window_buyers`         | `depletion_window_buyers`         | covered     |
| `frequency_accelerator`       | `audience.repeat_cohort`                   | `repeat_cohort`                   | covered     |
| `aov_momentum`                | `audience.aov_growth_cohort`               | `aov_growth_cohort`               | covered     |
| `retention_mastery`           | `audience.retention_at_risk`               | `retention_at_risk`               | covered     |
| `journey_optimization`        | `audience.journey_one_purchase_cohort`     | `journey_one_purchase_cohort`     | covered     |
| `category_expansion`          | `audience.single_category_buyers`          | `single_category_buyers`          | covered     |
| `first_to_second_purchase`    | `audience.single_purchase_cohort`          | `single_purchase_cohort`          | covered     |
| `at_risk_repeat_buyer_rescue` | `audience.at_risk_repeat_buyers`           | (none)                            | skipped     |
| `onsite_funnel_watch`         | `audience.onsite_funnel_observation`       | (none)                            | skipped     |

Skipped, with rationale:

- `at_risk_repeat_buyer_rescue` — M2 T2.3 reserved this `play_id` as the
  rename target for `retention_mastery` once "remove assumed churn reduction"
  lands (per memory.md). Until that copy/measurement work happens, the legacy
  `retention_mastery` builder still fully covers the audience surface; adding
  a second builder now would emit a duplicate audience and mislead M5/M6.
- `onsite_funnel_watch` — M2 T2.3 demoted from `journey_optimization` and
  flagged as a watching-only signal that requires onsite funnel data not
  available in the local CSV pipeline. Out of scope for M3, which only reads
  CSV-derivable cohorts.

Both will surface in `v2_candidates.json` with
`preliminary_rejection_reason="no_builder"` so downstream debug tooling can
see them, and `tests/test_detect_candidates.py::test_detect_candidates_covers_full_registry`
asserts the registry-vs-builders relationship is exactly this set.

## Forbidden-fields enforcement

`Candidate` (defined in `src/detect.py`) declares only these fields:

- `play_id: str`
- `audience_size: int`
- `segment_definition: str`
- `data_used: List[str]`
- `preliminary_rejection_reason: Optional[str]`
- `cold_start: bool`
- `audience_overlap: Dict[str, float]`

The deny-list `FORBIDDEN_CANDIDATE_FIELDS` (frozen set in `src/detect.py`)
contains every statistical, scoring, or recommendation field name that
M4a/M4b might be tempted to smuggle through this surface:

```
p_value, p, q_value, q, confidence, confidence_label, confidence_score,
revenue, expected_$, expected_dollars, ci_low, ci_high, ci_internal,
measured_effect, observed_effect, effect_abs, effect_size, score,
final_score, rank, recommended
```

Three test-suite enforcements:

1. `tests/test_audience_builders.py::test_audience_result_carries_no_forbidden_fields`
   — every `AudienceResult` produced by every builder is checked against the
   deny-list.
2. `tests/test_detect_candidates.py::test_detect_candidates_no_forbidden_fields`
   — every `Candidate.to_dict()` output is checked.
3. `tests/test_engine_v2_shadow.py` — the integration test re-checks the
   serialized `receipts/v2_candidates.json` payload for the same forbidden
   keys after a real fixture run.

If any future milestone tries to add a banned field to `Candidate` or to an
audience builder's return value, all three tests fail and the diff lights up
the deny-list.

## Behavior changes

- Default mode (`ENGINE_V2_SHADOW` unset/false): no behavior change. CSV->HTML
  briefing identical to M0 goldens; no new files written.
- Shadow mode (`ENGINE_V2_SHADOW=true`): one additional file
  `receipts/v2_candidates.json` written per run. Legacy briefing and receipts
  unchanged. Stdout includes a single line of the form
  `[ENGINE_V2_SHADOW] candidates=N both=[...] only_legacy=[...] only_v2=[...]`
  for diffing the v2 detector against the legacy emitted set.

## Remaining risks

- The two `no_builder` candidates surface as a known visible signal and will
  be wired in their own milestones (`at_risk_repeat_buyer_rescue` blocked on
  the retention-rename + measurement design; `onsite_funnel_watch` blocked on
  onsite funnel data).
- The legacy ULP-level float drift in `tests/test_golden_diff.py` is
  pre-existing and orthogonal to M3; it should be tracked separately.
- M3 is shadow-only by design — `v2_candidates.json` is currently consumed by
  no downstream code. M4a is the first consumer.

## Readiness for Milestone 4a

Milestone 4a (evidence classification: measured / directional / targeting +
fabricated-stat removal in legacy emitters) can begin against this M3 surface
with no further M3 work. M4a will:

- Read `Candidate` objects via `detect_candidates()` (already stable).
- Look up `evidence_class_default` via `play_registry.PLAYS[play_id]`
  (already stable from M2).
- Decide per-candidate evidence class without touching `Candidate` itself
  (forbidden-fields contract holds — evidence lives on a wrapper, not on
  Candidate).
- Continue running shadow-only behind `ENGINE_V2_SHADOW=true` per the
  milestone plan.

The slim Candidate schema, deterministic registry iteration, and pairwise
overlap surface are all the dependencies the M4a ticket needs. M3 is ready
to hand off.

## Follow-up work

- M4a (next): evidence classification + remove fabricated stats in legacy
  category_expansion / subscription_nudge / routine_builder /
  discount_hygiene fallback emitters.
- Separate ticket: "golden-test float stability" — canonicalize float
  serialization in `src/action_engine.py` and `src/engine_validator.py` so
  `tests/test_golden_diff.py` is bit-stable across runs.
- Future milestone (post-M5): wire `audience.at_risk_repeat_buyers` builder
  once the retention-rename + churn-reduction-removal lands.
- Future milestone (blocked on integration scope): wire
  `audience.onsite_funnel_observation` once onsite funnel data is available.
