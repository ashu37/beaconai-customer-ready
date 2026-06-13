# B-4/S-1 — Per-merchant directory + `store_id` resolution

**Owner:** code-refactor-engineer
**Date:** 2026-05-09
**Sprint:** Sprint 1 (Engineer A track, critical path)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §1, ticket B-4/S-1
**Status:** Complete; full suite green; M0 Beauty pinned fixture byte-identical.

---

## Scope delivered

1. Resolve a single canonical `store_id` per engine run.
2. Re-route all tenant-data writes/reads under `data/<store_id>/`.
3. Re-key `gate_recently_run` to the lineage tuple `(play_id, audience_definition_id, store_id)` — flag stays default-OFF, behavior unchanged.
4. Idempotent copy-with-attribution migration of any pre-existing shared `data/recommended_history.json` into per-store path.
5. Acceptance tests + CI guard against missed call sites.

## Resolution precedence (final)

`STORE_ID` env > `--brand` CLI arg > basename of orders-CSV parent dir > literal `"unknown"`. Result is sanitized to `[a-z0-9_-]+` (lowercase) so a hostile or unexpected basename can never escape the per-store directory.

## Files changed

| File | Change |
|---|---|
| [src/store_id.py](../src/store_id.py) | NEW — `resolve_store_id`, `store_data_dir`, `ensure_store_dir`, `migrate_legacy_recommended_history` |
| [src/main.py](../src/main.py) | Resolve `store_id` once at top of `run()`; both hardcoded `data/recommended_history.json` paths replaced; migration call wired (best-effort, non-fatal) |
| [src/guardrails.py](../src/guardrails.py) | `gate_recently_run` and `apply_guardrails` accept `store_id`; lineage-tuple matching with defensive policy (only enforce a component when both sides carry it) |
| [tests/test_store_id.py](../tests/test_store_id.py) | NEW — 12 unit tests (resolver precedence, sanitization, dir helpers, migration idempotency) |
| [tests/test_per_merchant_isolation.py](../tests/test_per_merchant_isolation.py) | NEW — 4 tests: two-merchant smoke (zero file overlap) + 3 lineage-tuple gate tests |
| [tests/test_no_tenant_writes_outside_store_dir.py](../tests/test_no_tenant_writes_outside_store_dir.py) | NEW — CI guard: no `recommended_history.json` written outside `data/<store_id>/`; no tenant artifacts at `data/` root |

## Hard constraints respected

- `engine_run.json` schema **unchanged** (no fields added, removed, or renamed).
- M0 Beauty pinned fixture **byte-identical** (`tests/test_slate_regression_beauty_brand.py::test_briefing_matches_pinned_fixture_bytewise` green).
- `RECENTLY_RUN_FATIGUE_ENABLED` flag stays default-OFF → fatigue behavior unchanged on Beauty fixture.
- Vertical scope hard-lock untouched (B-7 territory).
- No substrate work (S-2+ scope).
- No banned ML scaffolding (D-6).
- Engine remains runnable after every patch.

## Lineage-tuple matching policy (Patch 4)

`gate_recently_run` accepts a new `store_id` kwarg. Match key is the lineage tuple `(play_id, audience_definition_id, store_id)` where `audience_definition_id` falls back to `audience.id` until S-2/S-3 introduces an explicit field. Each component uses the same defensive policy already in place for `audience_id`: enforced only when **both** the candidate and the history record carry that component. This keeps existing history records (which may pre-date the per-store layout) matching on the historic 2-tuple — no migration needed for in-the-wild data.

## Migration semantics (Patch 3)

`migrate_legacy_recommended_history(store_id)`:

- If `data/recommended_history.json` exists AND `data/<store_id>/recommended_history.json` does NOT → copy with `.migration.json` sidecar (`source_path`, `copied_at`, `source_sha256`, `store_id`).
- If destination exists → no-op (`status="dest_exists"`).
- If legacy missing → no-op (`status="no_legacy"`).
- **Never deletes the legacy file** — D-3 is "full wipe only," and stranding the legacy file is safe.
- All errors reported via status dict; nothing raises.

## Test results

| Suite | Result |
|---|---|
| `tests/test_store_id.py` | 12/12 |
| `tests/test_per_merchant_isolation.py` | 4/4 |
| `tests/test_no_tenant_writes_outside_store_dir.py` | 1/1 |
| `tests/test_guardrails.py` (existing) | 51/51 |
| M0 Beauty pinned fixture | byte-identical |
| **Full suite** | **939 passed, 14 skipped, 0 failed** (~4 min) |

## Out of scope (deliberately not touched)

- `audience_definition_version` (D-1) — S-2/S-3 work; this ticket only prepares the fatigue-gate tuple shape.
- `compute_lineage_id` helper — S-2 scope.
- Fatigue flag flip — stays OFF.
- `actions_log.json` location — already written into per-run `receipts_dir` (per-run-isolated, not under `data/`); no relocation needed. CI guard test asserts it never appears at the `data/` root.
- Substrate (`memory.db`) — S-2 onwards.
- B-7 vertical hard-refuse — separate Sprint 1 ticket on the same engineer track.

## Risks observed during implementation (none unresolved)

- **Synthetic harness `cwd=tmpdir`:** the test harness already runs the engine outside the repo root, so `data/` resolves under tmpdir. The path-layout change had zero impact on goldens, which compare `briefing.html` bytes only. Confirmed by running the M0 byte-identical check before merge.
- **Resolver-vs-`brand`-arg drift:** addressed by making `--brand` the second resolution layer (after env override) so the canonical `store_id` agrees with the value already passed into `build_engine_run_from_legacy(store_id=brand)`.
- **Hidden call site:** mitigated by Patch 6 CI guard test which scans the post-run `data/` tree.

## Commit/PR shape

Ready for a single PR / single commit:

```
B-4/S-1: per-merchant directory + store_id resolution
```

When approved, the next ticket on Engineer A's track is **B-7 (vertical hard-refuse)**.
