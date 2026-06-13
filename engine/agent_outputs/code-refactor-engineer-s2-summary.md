# S-2 — SQLite memory.db substrate + lineage_id helper + inspect/export CLIs

**Owner:** code-refactor-engineer (Engineer A)
**Date:** 2026-05-09
**Sprint:** Sprint 2 (Engineer A track)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §2, ticket S-2
**Founder decisions consulted:** D-1 (audience_definition_version policy), D-2 (keep forever), D-3 (full wipe only), D-4 (full JSON export), D-6 (banned ML scaffolding), D-8 (vertical hard-lock).
**Status:** Complete. Substrate stands alone — zero engine code changes. Full suite green. M0 Beauty pinned fixture byte-identical.

---

## Scope delivered

1. Per-merchant SQLite event log at `data/<store_id>/memory.db` with WAL mode + `PRAGMA user_version` migrations.
2. `compute_lineage_id(store_id, play_id, audience_definition_id, audience_definition_version) -> sha1 hex` with all four args required (D-1).
3. `tools/inspect_memory.py` CLI for hand-inspection.
4. `tools/export_store.py` CLI implementing D-4's full per-store JSON export, with import + round-trip acceptance test.
5. Substrate isolation: nothing under `src/` outside `src/memory/` was touched.

## Files added

| File | Purpose |
|---|---|
| [src/memory/__init__.py](../src/memory/__init__.py) | NEW — re-exports `open_memory`, `MemoryStore`, `compute_lineage_id` |
| [src/memory/store.py](../src/memory/store.py) | NEW — `MemoryStore` class, `open_memory(store_id)`, schema, migrations |
| [src/memory/lineage.py](../src/memory/lineage.py) | NEW — `compute_lineage_id` (sha1, length-prefixed components, D-1) |
| [tools/__init__.py](../tools/__init__.py) | NEW — empty; makes `tools/` importable |
| [tools/inspect_memory.py](../tools/inspect_memory.py) | NEW — CLI: human-readable table or NDJSON |
| [tools/export_store.py](../tools/export_store.py) | NEW — full per-store JSON export + import + round-trip |
| [tests/test_lineage.py](../tests/test_lineage.py) | NEW — 10 tests on `compute_lineage_id` contract |
| [tests/test_memory_store.py](../tests/test_memory_store.py) | NEW — 13 tests: 1000-event ordering, migration idempotency, downgrade refusal, query filters, payload canonicalisation, per-store isolation, monotonic seq |
| [tests/test_memory_concurrent.py](../tests/test_memory_concurrent.py) | NEW — 1 test: 2 procs × 100 events → 200 distinct event_ids, distinct PIDs, monotonic `created_seq`, zero corruption |
| [tests/test_export_roundtrip.py](../tests/test_export_roundtrip.py) | NEW — 6 tests: shape, byte-identical round trip, refuses overwrite, refuses bad format/version, history preserved |

## Hard constraints respected

- `engine_run.json` schema **unchanged** (substrate is purely additive; no field added or removed).
- M0 Beauty pinned fixture **byte-identical** (`tests/test_slate_regression_beauty_brand.py`: 19/19 green).
- Full suite green: **1037 passed, 14 skipped, 0 failed** (was 975p/14s/0f baseline; +35 of the +62 are this ticket, the rest were intervening Sprint 1 reconciliation).
- Per-store `data/<store_id>/memory.db` is the deletion unit (D-3): no row-level delete API.
- No retention/cleanup logic (D-2: keep forever).
- No banned ML scaffolding (D-6): `src/memory/` exposes only event-log primitives — nothing model-shaped.
- Vertical hard-lock untouched (D-8): the substrate doesn't even know about verticals; `compute_lineage_id` is vertical-agnostic by design.

## Schema (user_version = 1)

```sql
CREATE TABLE events (
    event_id                    TEXT PRIMARY KEY,         -- uuid4 hex
    event_type                  TEXT NOT NULL,
    lineage_id                  TEXT,                     -- nullable; not all events tied to a play
    run_id                      TEXT,
    store_id                    TEXT NOT NULL,
    play_id                     TEXT,
    audience_definition_id      TEXT,
    audience_definition_version INTEGER,
    event_version               INTEGER NOT NULL DEFAULT 1,
    created_at                  TEXT NOT NULL,            -- microsecond UTC ISO-8601
    created_seq                 INTEGER NOT NULL,         -- monotonic, transaction-safe
    payload_json                TEXT NOT NULL             -- canonical sort_keys JSON
);
CREATE INDEX ix_events_lineage_seq  ON events (lineage_id, created_seq);
CREATE INDEX ix_events_run          ON events (run_id);
CREATE INDEX ix_events_type_seq     ON events (event_type, created_seq);

CREATE TABLE event_seq (
    rowid INTEGER PRIMARY KEY CHECK (rowid = 1),
    next_seq INTEGER NOT NULL
);
INSERT OR IGNORE INTO event_seq (rowid, next_seq) VALUES (1, 1);
```

## Key design decisions (judgment calls)

1. **`created_seq` (monotonic counter table) is the canonical ordering field, not `created_at`.** Wall-clock collisions on fast systems would break the 1000-event ordering acceptance test on a slow CI runner. The counter is bumped via `UPDATE ... RETURNING next_seq - 1` inside the same transaction as the event INSERT, so even racing writers cannot collide. Requires SQLite ≥ 3.35; we have 3.53.

2. **sha1 (not sha256) for `lineage_id`.** Lineage_id is a partition key with bounded cardinality (3 verticals × O(20) plays × O(50) audience definitions); 160 bits is overkill already. sha256 would be vanity; the only argument for it is "people expect sha256 in 2026," which isn't a technical reason.

3. **Length-prefixed components in `compute_lineage_id`.** Belt-and-braces alongside the unit-separator (`\x1f`). The unit separator alone would prevent collision in normal data, but length-prefixing also covers a hostile or escape-stripped input. The unit test pins the contract.

4. **`MemoryStore` carries a `threading.Lock` even though SQLite has its own.** Within a single Python process, `sqlite3` connection objects are thread-safe per-connection, but multiple in-flight `append_event` calls on the same connection could interleave their `UPDATE event_seq` and `INSERT events` statements without an explicit lock. The lock makes the intra-process append atomic and is cheap (microseconds). Across processes, WAL + busy_timeout handle it without the lock.

5. **Downgrade refusal at open time, not silent migration backwards.** A future Beacon build writing `user_version=2` then someone running today's build against that db would silently lose the v2 features. Refusing with a clear `RuntimeError` is louder than wrong.

6. **Export bundle includes `snapshots` (full content), not just `snapshot_index` (filenames).** D-4 says full export. A merchant restoring from a bundle to a fresh dir wants the snapshots back, not just a list of names. Doubles bundle size for the trade of complete data sufficiency.

7. **`import_store` refuses to overwrite a populated store.** D-3 says full wipe only; the operator is responsible for `rm -rf data/<store_id>/` before import. The CLI doesn't do it for them — destructive defaults are a footgun.

8. **CLIs ship under `tools/` with an `__init__.py`.** `python -m tools.inspect_memory` works from the repo root. The alternative (a `bin/` directory with shebangs) ties path resolution to the install, which we don't have.

9. **`time.gmtime` instead of `datetime.now(timezone.utc)`.** The latter has churned across Python 3.10 → 3.12+ (utcnow deprecated; tz-aware constructors changed). The former has been stable since Python 1.x and yields the same byte-shape ISO-8601 string we want.

## Acceptance test results

| Acceptance criterion | Test | Result |
|---|---|---|
| 1000-event append + query-by-lineage_id ordering | `test_memory_store.py::test_append_and_query_by_lineage_preserves_insertion_order` | green |
| Concurrent-write (2 procs × 100 events, zero corruption) | `test_memory_concurrent.py::test_two_processes_one_hundred_events_each` | green; 200 distinct event_ids, 2 distinct PIDs, monotonic seq |
| Migration idempotency | `test_memory_store.py::test_migration_is_idempotent` | green; 3rd open is a no-op |
| Round-trip export → import → byte-identical | `test_export_roundtrip.py::test_round_trip_byte_identical` | green; events list + snapshots + recommended_history all match |
| Full suite green | `pytest -q` | 1037 passed, 14 skipped, 0 failed |
| M0 Beauty fixture byte-identical | `test_slate_regression_beauty_brand.py` | 19/19 green |

## Out of scope (deliberately deferred)

- Engine writes `recommendation_emitted` / `recommendation_considered` events — **S-3** (bundles B-2 reason-code fan-out + typed `evidence_snapshot`). Schema-freeze milestone for the Swarm team is at end of S-3.
- Immutable snapshot discipline + `snapshot_sha256` field on event payload — S-4.
- Read-views (`v_lineage_timeline`, `v_calibration_state`, `v_open_recommendations`, `v_lineage_recent_emissions`) + `calibration_stub` rewire — S-5.
- Manual `tools/import_campaign_sent.py` import path + Swarm contract — S-6.
- `audience_definition` field actually appearing in `engine_run.json` — S-3 (the helper is ready; the engine doesn't pass anything to it yet).

## Risks observed during implementation (none unresolved)

- **Concurrent test runs in 0.1s.** Suspiciously fast. Verified by asserting the worker PIDs differ from the parent PID and from each other; the test would fail if the work happened in the parent or in a single child. SQLite + 100 events is genuinely just that fast.
- **Round-trip on snapshots.** Initial bundle only carried `snapshot_index` (filenames); re-export after import got an empty index. Promoted to a full `snapshots: {name: content}` map so the bundle is self-sufficient. Acceptance test pinned to catch any future regression.
- **`UPDATE ... RETURNING` syntax.** Requires SQLite 3.35; macOS Homebrew Python 3.14 ships 3.53. If a deployment targets a SQLite older than 3.35, this fails — out of scope but worth flagging in `docs/memory_substrate.md` when S-3 lands.

## Branch shape

Three commits on `post-6b-restructured-roadmap` (not pushed):

1. `82cefa4` — `S-2: SQLite memory.db substrate + lineage_id helper + inspect/export CLIs`
2. `26a391a` — `Document S-2 in repo memory.md`
3. (this file) — `S-2 summary`

Awaiting founder review + S-3 hand-off.
