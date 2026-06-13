# code-refactor-engineer — S-FE-rfm-segment-distribution

**Ticket:** FOUNDER-AUTHORIZED additive — aggregate `segment_distribution` on the RFM ModelCard (the 2.1.0 additive candidate per `docs/evidence_layer.md` §7 L-EV-17). Unblocks the merchant-facing RFM segment-distribution chart.
**Deviation check:** none.
**Status:** implemented, unstaged (left for orchestrator + DS review).

## Band shape (aggregate-only conformance)

`SegmentBand` (in `src/predictive/model_card.py`) carries exactly three fields:

```
segment_name: str    # one of the 11 canonical named segments
n: int               # observed customer count in this segment
share: float         # n / n_customers (fraction of analyzed base)
```

AGGREGATE-ONLY + DESCRIPTIVE (L-EV-17/20). NO per-customer rows, NO monetary magnitude, NO dollar/lift/rate/projected field. The schema `$defs.SegmentBand` has `required: [segment_name, n, share]` and no other properties. A dedicated test (`test_segment_band_shape_is_aggregate_only`) asserts the field set is exactly `{segment_name, n, share}` and scans for forbidden monetary/per-customer substrings.

## Population source + ordering

- Source: `rfm_table["segment_name"].value_counts()` — the data was already computed in `fit_rfm` Step 4 and previously reduced to `n_segments_observed` then discarded (the L-EV-18 discarded-series diagnosis applied to RFM). No new computation, no per-customer monetary surfaced.
- Computed by the new pure helper `src/predictive/rfm.py::_compute_segment_distribution(segment_name: pd.Series) -> List[SegmentBand]` (computes only from its own `rfm_table`; no new cross-module coupling).
- `total = len(segment_name)` (the analyzed base = `n_observed`); `share = n / total`.
- **Ordering convention:** `n` DESCENDING, ties broken by canonical LTV rank (`SEGMENT_LTV_RANK_ORDER`, Champions first) for stable deterministic output. Documented in the helper docstring.
- Only observed segments produce a band (≤ 11); a zero-count segment is omitted, never emitted as `n=0`.

## RULE-A typed suppression (VALIDATED/PROVISIONAL-only gate)

- Populated ONLY when RFM `fit_status ∈ {VALIDATED, PROVISIONAL}` (the segmentation cleared its inferential gate). RFM has no descriptive twin (L-EV-15) → it suppresses **as a unit**.
- On the 7 short-circuit `ModelCard` returns in `fit_rfm` (REFUSED / INSUFFICIENT_DATA): `segment_distribution=None` + `segment_distribution_suppression_reason=RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED`. Never a fabricated/partial distribution.
- `RfmSegmentDistributionSuppressionReason(str, Enum)` — closed 2-member set: `FIT_NOT_VALIDATED` / `FLAG_OFF` (lowercase string values, mirroring `DescriptiveDistributionSuppressionReason`).
- RFM-SCOPED: only the `rfm` ModelCard populates this. Other substrate cards (bgnbd / gamma_gamma / survival / cf) have no named-segment concept and leave both fields `None` (additive optional default).

## Serialization / back-compat

- Round-trips via the existing `_to_jsonable` recursion on `EngineRun.to_dict()` — `asdict` reaches `SegmentBand`, the paired enum unwraps to its string value.
- `EngineRun.from_dict` passes `predictive_models` through as-is (existing seam, unchanged). Older runs / non-RFM cards have no `segment_distribution` key → `None` (additive optional field; from_dict tolerance).
- Schema regenerated via `tools/generate_schema.py` (registered `SegmentBand` in `_EXTRA_DATACLASSES` + the enum in `_EXTRA_ENUMS`). Diff is purely additive (+53 lines); title stays `EngineRun v2.1.0` (NO second version bump — the 2.1.0 literal was already set by the descriptive-distribution change).
- CHANGELOG: appended a `v2.1.0 addendum — 2026-06-03` block to `src/engine_run.py` (additive within existing 2.1.0; no `schema_version` literal change).

## Files changed

- `src/predictive/model_card.py` — `SegmentBand` dataclass, `RfmSegmentDistributionSuppressionReason` enum, two new `ModelCard` fields, `__all__` update.
- `src/predictive/rfm.py` — import update, `_compute_segment_distribution` helper, populated VALIDATED/PROVISIONAL card, RULE-A reason on the 7 short-circuit returns.
- `src/engine_run.py` — CHANGELOG addendum only (no code change to the contract dataclasses; ModelCard is re-exported from model_card.py).
- `tools/generate_schema.py` — registered `SegmentBand` + the enum.
- `schemas/engine_run.v2.json` — regenerated (additive).
- `tests/test_s_fe_rfm_segment_distribution.py` — NEW (11 tests).
- `tests/fixtures/pinned_sha_ledger.json` — `_meta.post_s_fe_rfm_segment_distribution_definition` note (documentation; no sha re-pin).
- `agent_outputs/code-refactor-engineer-s-fe-rfm-segment-distribution-summary.md` — this file.

## Tests / checks

- NEW `tests/test_s_fe_rfm_segment_distribution.py`: 11 passed. Covers SegmentBand aggregate-only shape, serialize/deserialize, pure-aggregator count/share/ordering/tie-break/empty, populated-on-VALIDATED (bands sum to `n_observed`, shares ~1.0, n-descending), RULE-A suppression on INSUFFICIENT_DATA + REFUSED-degenerate, EngineRun serialization + enum unwrap, from_dict absence tolerance.
- Regression suites run green: `test_s12_t1_rfm_fit` (minus the pre-existing stale failure below), `test_s12_t1_5_rfm_rollback`, `test_s12_t1_rfm_threshold_loader`, `test_s10_t1_model_card`, `test_model_card_metrics_dict_shape`, `test_engine_run_schema`, `test_s13_7_t2_schema_generator`, `test_s13_6_t5_schema_version_2_0_0`, `test_null_reason_registry`, `test_s_fe_descriptive_distribution` (33 passed in the descriptive/schema-version slice).
- Schema validation: a real VALIDATED RFM run with `segment_distribution` validates against the regenerated `schemas/engine_run.v2.json` (jsonschema.validate PASS).
- End-to-end smoke: `fit_rfm` on the monotone DGP → VALIDATED, 11 bands, n descending, sum=`n_observed`=1150, shares sum=1.0, suppression_reason=None.

**Pre-existing failure (NOT introduced by this ticket):** `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` asserts `ENGINE_V2_ML_RFM` default is `False`, but the flag was flipped ON at S12-T1.5 (`src/utils.py:1003` defaults `"true"`). The test is a stale T1-era assertion; it fails on a clean tree. Out of this ticket's scope — flag KI for the orchestrator.

## Re-pins

None. Following the `post_s_fe_descriptive_distribution` precedent: the synthetic `engine_run.json` shas in `pinned_sha_ledger.json` are NOT byte-stable (wall-clock `fit_timestamp` per `engine_run_json_sha_caveat`) and are not re-pinned; the load-bearing gates are the structural/serialize/round-trip tests + schema-validate. The ledger received a documentation note only. `briefing.html` is unchanged (the renderer does not consume the new field).

## Remaining risks / follow-up

- The new bands surface in `engine_run.json` only when `ENGINE_V2_ML_RFM` is ON (default-ON since T1.5) AND RFM reaches VALIDATED/PROVISIONAL on the merchant's data. On REFUSED/INSUFFICIENT_DATA stores the chart consumer must render the typed `FIT_NOT_VALIDATED` reason, never a chart.
- No PlayCard consumes `segment_distribution` (RFM remains an operator/Intelligence-page surface per L-EV-16); the frontend Intelligence-page wiring (L-EV-16) and the per-mechanism selection map (L-EV-17 frontend half) are downstream Phase-3 frontend work, out of this ticket.
- The `FLAG_OFF` enum member is declared for completeness but not currently emitted by `fit_rfm` (when the flag is OFF the RFM substrate does not run at all, so no card is produced). It is reserved for a future producer path that constructs an rfm card under flag-OFF; harmless if unused.
