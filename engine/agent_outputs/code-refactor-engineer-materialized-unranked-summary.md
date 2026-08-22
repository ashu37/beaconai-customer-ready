# code-refactor-engineer — MATERIALIZED_UNRANKED

Ticket: DS-adjudicated fix to `_write_audience_csv` — when the RFM predictive
substrate is absent, stop throwing away a valid order-history-derived audience.
The substrate only supplies RANKING (`rank_score` / `predicted_segment`), never
MEMBERSHIP. Membership is order-history-derived and already computed by the
`audience_ids_resolver`. Emit those customer_ids so recommended plays remain
sendable, under a new status `MATERIALIZED_UNRANKED`.

## Files changed

- `engine/src/audience_resolver.py`
  - Replaced the `rfm_df is None` branch in `_write_audience_csv` (previously an
    unconditional empty-CSV + `SUPPRESSED_SUBSTRATE_REFUSED`) with the four-case
    branch below.
  - Added `MATERIALIZED_UNRANKED` to the two docstring status vocabularies
    (`materialize_audience_csvs` docstring; `_write_audience_csv` docstring) with
    the DS-specified verbatim semantics.
- `engine/src/run_manifest.py`
  - Added `MATERIALIZED_UNRANKED` to the "Audience materialization status values"
    docstring vocab (verbatim semantics).
- `engine/tests/test_s13_7_t1_audience_resolver.py`
  - Added focused tests for all four new-branch outcomes (see Test added).
  - Superseded `test_parquet_missing_status_is_substrate_refused` (which encoded
    the pre-narrowing behavior) with
    `test_parquet_missing_with_resolver_status_is_materialized_unranked`.
- `engine/tests/test_s13_7_t2_manifest.py`
  - Updated `test_materialize_audience_csvs_returns_status_for_each_card` (no
    parquet + no resolver) from expecting `SUPPRESSED_SUBSTRATE_REFUSED` to
    expecting `NOT_MATERIALIZED`, matching the DS-specified degraded-path status.

Not touched: `schemas/engine_run.v2.json` (status is a free string in
manifest.json, zero matches in the frozen schema — confirmed by grep — so no
schema change and no version bump). The recommend lane, guardrails, engine math,
and the resolved (parquet-present) write path are unchanged.

## Exact branch logic (new `rfm_df is None` behavior)

1. `audience_ids_resolver is None` OR `play_id` falsy → write empty CSV, return
   `NOT_MATERIALIZED`. (Genuinely-unrunnable degraded path — unchanged intent.)
2. resolver raises → warn, write empty CSV, return `NOT_MATERIALIZED`.
3. resolver returns `None` → write empty CSV, return `NOT_MATERIALIZED`.
4. resolver returns a non-empty scoped id set → write header + one row per
   customer_id (`customer_id` populated; `aov_individual` / `predicted_segment` /
   `rank_score` written as empty since there is no substrate), return
   `MATERIALIZED_UNRANKED`.
5. resolver returns an empty set → write empty CSV, return `NOT_MATERIALIZED`
   (honest zero-match; no fabricated members).

`MATERIALIZED_UNRANKED` is returned as an authoritative (non-None) status, so the
caller in `materialize_audience_csvs` records it directly and does not re-count
rows. The `SUPPRESSED_SUBSTRATE_REFUSED` string now originates only from the
caller's row-count fallback on the resolved (parquet-present, empty-result) path.

## Guardrails G1–G4 and how each is enforced

- G1 (ids from the play's resolved cohort, never rfm_df unfiltered / never full
  base): ids come solely from `audience_ids_resolver(play_id)`. `rfm_df` is
  `None` here so it cannot be a source. Resolver absent / raised / `None` all
  keep the empty + `NOT_MATERIALIZED` refusal. Verified by
  `test_..._no_resolver...` and `test_..._resolver_raises...`.
- G2 (empty resolved cohort → honest zero, not fabricated): empty set →
  empty CSV + `NOT_MATERIALIZED`. Verified by
  `test_parquet_missing_empty_resolver_status_is_not_materialized`.
- G3 (no silent absence — every PlayCard gets a CSV + recorded status): every
  branch calls `_write_empty_csv` or writes rows, then returns a status the
  caller records. Verified: every test asserts `expected_path.exists()`.
- G4 (`MATERIALIZED_UNRANKED` fires ONLY when ids were written AND rfm absent;
  couldn't-run stays `NOT_MATERIALIZED`): the status is returned only inside the
  non-empty-set write block within the `rfm_df is None` guard. Verified by the
  four discriminating tests (non-empty → `MATERIALIZED_UNRANKED`; absent /
  raised / empty → `NOT_MATERIALIZED`).

## Test added

In `test_s13_7_t1_audience_resolver.py`:
- `test_parquet_missing_with_resolver_status_is_materialized_unranked` — non-empty
  resolver, no parquet: asserts exactly the resolved ids are written, the
  substrate columns are empty, and status is `MATERIALIZED_UNRANKED`.
- `test_parquet_missing_empty_resolver_status_is_not_materialized`
- `test_parquet_missing_no_resolver_status_is_not_materialized`
- `test_parquet_missing_resolver_raises_status_is_not_materialized`

## Test results

`python -m pytest tests/test_s13_7_t1_audience_resolver.py tests/test_s13_7_t2_manifest.py -q`
→ 23 passed.

Also green with narration suites included:
`... tests/test_narration_mcp_locks.py tests/test_narration_mcp_smoke.py`
→ 41 passed, 6 skipped.

(The full `pytest` run was not completed to green within the session because
unrelated suites fit models and exceed the tool timeout; only the contract-status
suites are affected by this change, and they pass. Grep confirmed the only
source/test files referencing the changed symbols are `audience_resolver.py`,
`run_manifest.py`, and the two updated test files.)

## Invariants / scope

- Pivot 7 (single-demote-channel): untouched. `_write_audience_csv` remains a
  pure file writer — no append to `engine_run.recommendations`, no
  `apply_guardrails_to_injected`, no `ReasonCode`.
- RULE B: honored and narrowed exactly as DS specified — membership-validity is
  now distinguished from ranking-validity; membership stays auditable and
  cohort-scoped; no silent absence.
- Filesystem-only handoff (D-S13.7-5): unchanged.
- Cross-cohort / customer-level de-dup: NOT added. Per DS re-check, no such de-dup
  exists at v2 materialization and RFM was never the de-dup mechanism; that is a
  send-time concern out of scope for this ticket.

Deviation check: none
