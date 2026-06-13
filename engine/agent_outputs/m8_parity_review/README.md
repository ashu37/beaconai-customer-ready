# M8 V2 Renderer Parity Review (T8.8)

Side-by-side V2 vs legacy briefing samples for the three pinned merchant
fixtures. Generated on 2026-05-03 (engine-rework branch) with the full V2
flag stack:

```
ENGINE_V2_OUTPUT=true
ENGINE_V2_DECIDE=true
ENGINE_V2_SIZING=true
STATS_NAN_FOR_HARDCODED=true
EVIDENCE_CLASS_ENFORCED=true
MATERIALITY_FLOOR_SCALE_AWARE=true
CANNIBALIZATION_GATE_ENABLED=true
ANOMALY_GATE_ENABLED=true
```

## Files

- `small_sm_v2_briefing.html` — V2 render for `small_sm` (~$1.5M ARR).
  Decision state: ABSTAIN_SOFT. Targeting card surfaced; range chip
  hidden because the prior is non-causal under M6 sizing.
- `small_sm_legacy_briefing.html` — legacy render for the same fixture
  with the V2 output flag OFF. Confirms the legacy path still produces
  the existing layout byte-equivalent to M7 baseline.
- `mid_shopify_v2_briefing.html` — V2 render for `mid_shopify`.
  Decision state: ABSTAIN_SOFT.
- `micro_coldstart_v2_briefing.html` — V2 render for `micro_coldstart`.
  Decision state: ABSTAIN_SOFT.

## Forbidden-string sweep

Every V2 sample contains zero occurrences of: `p =`, `q =`, `p-value`,
`q-value`, `confidence_score`, `final_score`, `p_internal`, `ci_internal`.

Verified via:

```
grep -cE 'p =|q =|p-value|q-value|confidence_score|final_score|p_internal|ci_internal' agent_outputs/m8_parity_review/*v2*.html
# all results: 0
```

## Notes

- The V2 path produces ABSTAIN_SOFT for all three fixtures today. This is
  expected: with M4b reclassification + M6 conservative sizing, all
  current legacy plays surface as targeting and the M7 abstain rule
  prevents a targeting-only PUBLISH. The V2 renderer correctly displays
  the "no measured opportunities cleared" callout, watching signals
  where available, and the targeting card with no $ headline.
- The legacy renderer is preserved untouched. With the flag OFF, the
  M0/M4b/M5/M6/M7 goldens remain byte-identical (3 passed in
  test_golden_diff.py).
- No PUBLISH-state V2 sample is included here because no current
  fixture produces a measured/directional play under the V2 stack.
  Synthetic PUBLISH cases are exercised by `tests/test_render_v2.py`.
- No ABSTAIN_HARD V2 sample is included here because no current
  fixture triggers a HARD data-quality flag in the M3 anomaly window.
  Synthetic ABSTAIN_HARD cases are exercised by `tests/test_render_v2.py`.
