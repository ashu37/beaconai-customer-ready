# code-refactor-engineer — S-FE Phase 0: audience resolver hardening (DS lock 4, route (a))

**Ticket:** Handoff-layer Phase 0 — the only engine-side code change in the handoff plan.
**Authority:** `docs/handoff_architecture.md §7 lock 4` (DS DECISION 2026-06-01, route (a)).
**Scope:** Harden `src/audience_resolver.py` so the degraded path can no longer produce a mislabeled `MATERIALIZED` full-substrate CSV. DS-locked; no scope expansion.
**Deviation check:** none.

## Problem

`materialize_audience_csvs` had a degraded path that produced a MISLABELED CSV:

- Resolver absent (`audience_ids_resolver is None`): wrote the ENTIRE RFM substrate (every customer in the store) with only a stdout warning.
- Resolver present but raised per-play: fell through to the same full-substrate write.
- The status logic then counted rows > 1 and labeled the result `MATERIALIZED`.

Net: a full-substrate CSV got a green `MATERIALIZED` light, which would email the whole base under a targeted play (wrong customers, green light). Production `main.py` always passes a working resolver, so this was a latent tripwire for the future assembly-MCP caller — not a live bug. Route (a) hardens the resolver before the fixture is frozen.

## Fix

Both degraded triggers (resolver absent AND resolver raised) now write an **empty CSV with the standard header row** (via the existing `_write_empty_csv` helper) and report **`NOT_MATERIALIZED`**. Non-fatal degrade — no exception, no silent skip (honors D-S13.7-1 "never silent absence" + D-S13.7-2 non-fatal-on-write-failure).

`_write_audience_csv` now returns an authoritative status string for the empty-write cases (`SUPPRESSED_SUBSTRATE_REFUSED` for parquet absent/unreadable; `NOT_MATERIALIZED` for unresolved audience) and `None` for the normal resolved write path (caller still counts rows for `MATERIALIZED` vs zero-match). Only a successfully resolved set (incl. an empty set, preserving the prior zero-match behavior) licenses writing substrate rows.

The module's pure-side-effect-writer invariant is preserved: no `engine_run` list mutation, no guardrails calls. No `_MANIFEST_SCHEMA_VERSION` change, no `src/run_manifest.py` edit, no `audience_filtered` field. Route (b) and the L5 manifest version field remain deferred.

## Before / after status mapping (four branches)

| Branch | Trigger | Before | After |
|---|---|---|---|
| Parquet missing / unreadable | `rfm_df is None` | empty + header, `SUPPRESSED_SUBSTRATE_REFUSED` | **unchanged** — empty + header, `SUPPRESSED_SUBSTRATE_REFUSED` |
| Resolver absent | `audience_ids_resolver is None` | **full substrate** + header, labeled `MATERIALIZED` | empty + header, **`NOT_MATERIALIZED`** |
| Resolver raises | resolver passed, raises for play | **full substrate** + header, labeled `MATERIALIZED` | empty + header, **`NOT_MATERIALIZED`** |
| Happy path | parquet present, resolver returns set | filtered rows, `MATERIALIZED` | **byte-identical** — filtered rows, `MATERIALIZED` |

(Out-of-scope, behavior preserved: resolver returns an empty/zero-match set with parquet present → header-only CSV, `SUPPRESSED_SUBSTRATE_REFUSED`, as before — not one of the four hardened branches.)

## Files changed

| File | Change |
|---|---|
| `src/audience_resolver.py` | Module + function docstrings updated for the hardened degrade. `_write_audience_csv` signature `-> None` → `-> Optional[str]`; resolver-absent and resolver-raised branches now write empty + return `NOT_MATERIALIZED`; substrate-refused returns `SUPPRESSED_SUBSTRATE_REFUSED`; resolved path returns `None`. Caller uses the returned status for empty-write cases and falls back to row-counting only on the resolved path. Removed the full-substrate fallback write. |
| `tests/test_s13_7_t1_audience_resolver.py` | Rewrote the old `test_no_resolver_with_parquet_writes_all_rows_degraded_mode` (asserted full-substrate leak) into `test_no_resolver_with_parquet_writes_empty_not_materialized`. Added `test_resolver_raises_writes_empty_not_materialized`, `test_happy_path_status_is_materialized`, `test_parquet_missing_status_is_substrate_refused`. |

## Tests / checks run

- `tests/test_s13_7_t1_audience_resolver.py`: **10 passed** (6 prior-shape, including the rewritten degraded test + the 3 new branch tests).
- `tests/test_s13_7_t2_manifest.py` (downstream consumer of the status dict): **8 passed**. `NOT_MATERIALIZED` was already an allowed status value; no manifest change required.
- grep sweep: no remaining code path writes the full substrate; all "full substrate" strings are now refusal comments/logs or test docstrings.

## Behavior changes

- Resolver-absent and resolver-raised paths: full-substrate `MATERIALIZED` CSV → empty header-only `NOT_MATERIALIZED` CSV.
- Happy path and parquet-missing path: unchanged. Production `main.py` always passes a working resolver, so a real fixture run is unaffected.

## Remaining risks

- This fixes only the full-substrate-leak instance. `MATERIALIZED` is still NOT general proof of correct audience (`aov_individual=0.0`; CSV `predicted_segment` bypasses the D-S13-2 modal-segment floor — lock 6). The assembly brief (Phase 4) must keep lock 4's standing sentence.
- The zero-match resolved case (resolver returns empty set, parquet present) still maps to `SUPPRESSED_SUBSTRATE_REFUSED` via row-counting — pre-existing, out of scope, deliberately left unchanged.

## DS review round 2 (2026-06-01) — APPROVE WITH CHANGES (docs/comment/test hygiene)

Logic stayed as-is; DS required three hygiene fixes + a summary update before commit (Deviation check: none — DS-locked scope):

1. **Reworded the misleading comment + log in the `audience_ids is None` branch** (`_write_audience_csv`). The old comment said the branch covers "empty play_id, or resolver returned None" and the log said the resolver "yielded no audience set" — which reads like the zero-match (empty SET) case. It is NOT: an empty set falls through to the filter and is counted as zero matched rows. New comment/log substance: *resolution could not RUN (resolver returned None, or play_id was empty); this is NOT zero-match — a resolver that returns an empty set is counted as zero matched rows downstream.*
   - New log line: `audience resolution could not run for play_id=<…> (resolver returned None, or play_id was empty); writing empty CSV (NOT_MATERIALIZED) rather than the full substrate (DS lock 4, route (a)). This is NOT zero-match: a resolver that returns an empty set is counted as zero matched rows downstream.`

2. **Documented the empty-`play_id` third NOT_MATERIALIZED trigger.** Beyond the two triggers the DS lock named (resolver-absent, resolver-raised), a falsy `play_id` also routes to NOT_MATERIALIZED because the resolver call is gated on `if play_id:`, so `audience_ids` stays None and the card falls into the degraded branch. Added a one-line note to both the `_write_audience_csv` docstring and the `materialize_audience_csvs` NOT_MATERIALIZED status doc: *NOT_MATERIALIZED also covers a falsy `play_id` (resolution cannot run without a play id).*

3. **Added two tests** (`tests/test_s13_7_t1_audience_resolver.py`):
   - `test_resolver_returns_empty_set_status_is_substrate_refused` — resolver returns `set()`, parquet present ⇒ header-only CSV + `SUPPRESSED_SUBSTRATE_REFUSED` (pins current row-count fallback behavior). Guards against a future `if resolved is not None` → `if resolved:` collapse that would silently relabel every zero-match audience as NOT_MATERIALIZED.
   - `test_empty_play_id_status_is_not_materialized` — falsy `play_id`, resolver present, parquet present ⇒ header-only CSV + `NOT_MATERIALIZED` (CSV keyed on `"unknown"` via the `play_id or "unknown"` fallback). The resolver returns a real set, so a regression that DID call it would leak substrate and fail the header-only assertion.
   - File now: **12 passed** (10 prior + 2 new).

**Flagged for the orchestrator (do NOT self-edit per DS):**

- **lock-4 doc note:** `docs/handoff_architecture.md §7 lock 4` should get a one-line addition — *empty `play_id` ⇒ NOT_MATERIALIZED* — documenting the third trigger alongside resolver-absent and resolver-raised. (DS asked me not to touch `docs/handoff_architecture.md` or `docs/DECISIONS.md`.)
- **KNOWN_ISSUES line:** pre-existing reverse-mislabel — a production resolver that returns `set()` on its OWN internal failure (rather than raising) is indistinguishable from a legitimate zero-match audience, so it currently maps to `SUPPRESSED_SUBSTRATE_REFUSED` via the row-count fallback. A future MCP caller must NOT inherit this blind: a resolver-internal failure should surface as a distinct status, not be absorbed into "substrate refused." Logged for the orchestrator to file in `KNOWN_ISSUES.md`.

## Follow-up / dependencies

- Phase 0 fixture (mcp-integration-engineer) must still exercise a `SUPPRESSED_SUBSTRATE_REFUSED` audience (DS §6). The new `NOT_MATERIALIZED` degrade is unreachable in a normal fixture run (resolver is always present) and need not be fixture-exercised.
- Route (b) + manifest `audience_definition_version` (L5) remain deferred (additive `1.0.0 → 1.1.0` if ever needed).
- Phase 4 assembly brief inherits lock 4's standing "MATERIALIZED ≠ correct" constraint + lock 6.
