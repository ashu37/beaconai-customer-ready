# Code Refactor Engineer — S13.7-T1 Summary

**Ticket:** S13.7-T1 — Audience Customer-ID Resolver
**Date:** 2026-06-01
**Status:** SHIPPED

---

## Approved Scope

Materialize one CSV per PlayCard audience after the engine run completes, at:
`data/<store_id>/runs/<run_id>/audiences/<audience_definition_id>.csv`
Columns: `customer_id`, `aov_individual`, `predicted_segment`, `rank_score`.
SUBSTRATE_REFUSED branch: empty CSV with header row, never silent absence.
`segments.py` hard retirement. `CustomerIdsNullReason` enum declared.

---

## Files Changed

| File | Change |
|---|---|
| `src/audience_resolver.py` | NEW — public `materialize_audience_csvs()` function |
| `src/engine_run.py` | ADD `CustomerIdsNullReason` enum (2 members); update registry comment; add to `__all__` |
| `src/main.py` | REMOVE `from .segments import build_segments` and call site; WIRE `materialize_audience_csvs` after `engine_run.json` write (line ~2003); replace `seg_files` with `[]` |
| `src/segments.py` | RETIRE — `raise NotImplementedError("Retired at S13.7-T1; use audience_resolver")` |
| `tests/test_s13_7_t1_audience_resolver.py` | NEW — 6 tests |
| `tests/test_null_reason_registry.py` | UPDATE — assert `CustomerIdsNullReason` EXISTS (was: assert does NOT exist) |
| `tests/golden/micro_coldstart/receipts/run_summary.json` | RE-PIN — `"segments": []` (was: list of legacy CSV paths) |
| `tests/golden/mid_shopify/receipts/run_summary.json` | RE-PIN — `"segments": []` |
| `tests/golden/small_sm/receipts/run_summary.json` | RE-PIN — `"segments": []` |

---

## Wiring Location in main.py

The resolver call is inserted at what was line 2003 in `src/main.py`, immediately after the immutable snapshot write block (`write_immutable_snapshot`) and before the S-3 substrate event emission block (`_emit_substrate_events`). This is AFTER guardrails are applied and AFTER `engine_run.json` is written.

Variables in scope at wire location: `engine_run`, `store_id`, `store_dir`, `cfg` (for `DATA_DIR`), `g`, `aligned_for_template` (for the inline audience resolver). The `run_id` is read from `engine_run.run_id`.

---

## segments.py Importers Audit

AST grep result:
```
grep -r "from src.segments|import segments|from src import segments" . --include="*.py"
grep -r "from .segments|build_segments" src/ --include="*.py"
```

Single importer found: `src/main.py` (line 24 `from .segments import build_segments` + line 708 call site).

Action taken:
- Import line removed; replaced with a comment documenting the retirement.
- Call site (`build_segments(g, ...)`) removed; `seg_files = []` substituted.
- `segments.py` now raises `NotImplementedError` at module-top (import-time).
- Three golden `run_summary.json` files re-pinned from legacy segment paths to `[]`.

No other importers existed. The `audience_builders.py` references to `segments.py` are doc-comments only (not import calls) — left unchanged.

---

## Parquet Path

`src/audience_resolver.py` uses: `data/<store_id>/predictive/rfm.parquet`

This matches exactly what `src/predictive/consumer_wiring.py` uses (line 280: `"data/<store_id>/predictive/rfm.parquet"`) and what `src/main.py` builds at the S13-T2 consumer-wiring call site (lines 1712-1716):
```python
_rfm_parquet = (
    Path(cfg.get("DATA_DIR", "data"))
    / store_id
    / "predictive"
    / "rfm.parquet"
)
```

The resolver uses the same `cfg.get("DATA_DIR", "data")` pattern.

---

## Assumptions and Gaps Documented

1. **`aov_individual = 0.0`**: RFM parquet schema v1 does not store per-customer AOV (only `r_quintile`, `f_quintile`, `m_quintile`, `segment_name`). `aov_individual` is set to `0.0` per spec ("0.0 if unavailable"). Future parquet schema extension can populate this.

2. **`rank_score` derived from `m_quintile`**: `(m_quintile - 1) / 4` gives [0.0, 1.0] range. Falls back to `0.5` when `m_quintile` column is absent.

3. **`audience_definition_id` derived from `PlayCard.audience.id` or `play_id`**: Mirrors the `_audience_definition_id` resolver in `main.py` (same fallback chain). No new field added to `Audience` dataclass (schema v2.0.0 frozen).

4. **TODO(S13.7-T2)**: `audience_materialization_status: "SUPPRESSED_SUBSTRATE_REFUSED"` in `manifest.json` is marked with a TODO comment in `audience_resolver.py`. Manifest generation is T2's responsibility.

5. **`CustomerIdsNullReason.AUDIENCE_RESOLVER_NOT_INVOKED`** is declared for forward-compat; not yet wired to any field (field pairing deferred to S13.7-T7b, Audience dataclass not extended).

---

## Test Results

```
tests/test_s13_7_t1_audience_resolver.py: 6 passed
tests/test_null_reason_registry.py: 1 passed
tests/test_s13_6_t7a_no_silent_nulls.py: 8 passed
tests/test_engine_v2_shadow.py: 15 passed (all 3 merchants)
Full suite: 1 pre-existing failure (test_phase5_considered_always — "Would fire" text 
  was stripped in S13.6-T1a; confirmed pre-existing by stash verification)
```

---

## Behavior Changes

- `data/<store_id>/runs/<run_id>/audiences/<audience_definition_id>.csv` now written after every engine run (one per PlayCard in recommendations + recommended_experiments).
- SUBSTRATE_REFUSED (parquet missing/unreadable): empty CSV with header row, never silent absence.
- Legacy `out_dir/segments/` CSVs are NO LONGER written. `run_summary.json["segments"]` is `[]`.
- `src/segments.py` raises `NotImplementedError` on import.
- `CustomerIdsNullReason` enum is now declared in `engine_run.py` and exported via `__all__`.
- `engine_run.json` content is unchanged (resolver is a pure side-effect; no PlayCard mutation).

---

## Single-Demote-Channel Invariant

Preserved structurally. `materialize_audience_csvs` is a pure side-effect writer:
- Does NOT append to `engine_run.recommendations`.
- Does NOT append to `engine_run.considered`.
- Does NOT call `apply_guardrails_to_injected`.
- Does NOT set any `ReasonCode`.

`Deviation check: none`

---

## Remaining Risks

1. **`aov_individual` always 0.0**: Acceptable per spec but limits Klaviyo operator utility for value-based segmentation. Resolve at parquet schema v2 when `monetary` column is added to the RFM parquet artifact.
2. **Audience resolver re-runs builders**: The inline `_mat_resolve_audience_ids` in `main.py` re-invokes audience builders (same pattern as S13-T2 consumer-wiring). On large stores this doubles audience-builder runtime. Acceptable for local CSV workflow; flag for future optimization.
3. **`"segments"` key in `run_summary.json` is now `[]`**: Any downstream consumer of `run_summary.json` that read the legacy segment file paths must be updated. Known consumers: `briefing.html` renderer (dev-only, non-product-contract). No `engine_run.json` consumers affected.

---

## Next Milestone Dependencies

- **S13.7-T2**: `manifest.json` per run — complete the `audience_materialization_status: "SUPPRESSED_SUBSTRATE_REFUSED"` annotation referenced in the TODO comment in `audience_resolver.py`.
- **S13.7-T7b**: Wire `PlayCard.audience.customer_ids_null_reason` field using `CustomerIdsNullReason` (now declared).
