# winback_dormant_cohort — display + mechanism copy

**Status (wave 1):** documentation-only. The renderer still reads display
name and mechanism text from the legacy locations:

- `src/play_registry.py::PLAYS["winback_dormant_cohort"].display_name`
- `src/measurement_builder.py::_PRIOR_ANCHORED["winback_dormant_cohort"]`
  (`recommendation_text`, `why_now_template`, `mechanism_text`)

Future waves will route the renderer through `plays/<play_id>/copy.md`.

## Display name

> Dormant repeat-buyer winback

## Recommendation text

> Send a winback nudge to the dormant repeat-buyer cohort.

## Why-now template

> {audience} repeat-buyers placed their last order {window}; none have
> purchased in the past 28 days. Calibrated to a validated reactivation
> benchmark.

## Mechanism text

> Email the dormant repeat-buyer cohort with a structured winback offer;
> measure reactivation within 30 days.

## Would-be-measured-by

`LAPSED_REACTIVATION_IN_30D`
