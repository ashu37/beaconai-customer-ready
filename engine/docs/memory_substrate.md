# Memory Substrate — Read-Views Contract

**Status:** Sprint 3, ticket S-5. `event_version=1` schema-freeze contract for the Swarm team established at end of S-3 (Sprint 2). Read-views below are additive over that frozen schema.

**Storage backend note (founder, 2026-05-10):** `data/<store_id>/` (SQLite `memory.db` + immutable run snapshots) is local-disk scaffolding for the planning horizon. When AWS hosting lands, the storage backend swaps. The substrate API (`open_memory`, `append_event`, `write_immutable_snapshot`, the read-views below) is abstracted enough that storage swaps without engine changes. Do NOT add TTLs, archival tiers, or local-disk cleanup logic — D-2 (retention forever) holds today.

---

## Per-store layout

```
data/<store_id>/
├── memory.db                  # SQLite (WAL); append-only events table; user_version=2
├── runs/
│   └── <run_id>.json          # immutable engine_run.json snapshot (S-4)
├── recommended_history.json   # legacy outcome log (B-4/S-1, kept in parallel)
└── inbox/
    └── campaigns/             # S-6: drop campaign_sent JSON here for manual import
```

Per founder decision **D-3**, the per-store directory is the deletion unit (`rm -rf data/<store_id>/`). Per **D-2**, there are no TTLs.

---

## Schema versions

| `PRAGMA user_version` | Introduced | Description |
|---|---|---|
| 1 | S-2 | `events` append-only table + `event_seq` counter + 3 indexes |
| 2 | S-5 | Adds four read-views (DDL in [`src/memory/views.sql`](../src/memory/views.sql)) |

Migrations are idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE VIEW IF NOT EXISTS`). Opening an already-migrated db is a no-op. **Downgrade is refused:** opening a db with `user_version > CURRENT_USER_VERSION` raises `RuntimeError` — operators must run a newer Beacon build, never an older one.

---

## Event types (Sprint 2/3 freeze)

| event_type | Writer | event_version | Notes |
|---|---|---|---|
| `recommendation_emitted` | `src/decide.py` (via `src/main.py::_emit_substrate_events`) | 1 | One per `PlayCard` in `recommendations` + `recommended_experiments`. Carries typed `evidence_snapshot`, `expected_outcome`, `snapshot_path`, `snapshot_sha256`. |
| `recommendation_considered` | same | 1 | One per `RejectedPlay`. Carries `reason_code` from S-3 fan-out. |
| `campaign_sent` | `tools/import_campaign_sent.py` (S-6) | 1 | Manual JSON import, never engine-written. |
| `outcome_observed` | `tools/import_outcome_observed.py` (Phase 9) | 1 | Manual JSON import or Swarm Monitor Agent. |
| `calibration_updated` | calibration consumer (Phase 9, L-D #1) | 1 | Reader today: `src/calibration_stub.py::load_realization_factors`. |

Single-writer-per-event-type discipline is enforced by [`tests/test_single_writer_per_event_type.py`](../tests/test_single_writer_per_event_type.py) (grep guard).

---

## Read-views (S-5)

All four views are defined in [`src/memory/views.sql`](../src/memory/views.sql) and exposed via typed Python helpers in [`src/memory/views.py`](../src/memory/views.py). Helpers are reachable from the package re-exports:

```python
from src.memory import (
    open_memory,
    read_lineage_timeline,
    read_calibration_state,
    read_open_recommendations,
    read_lineage_recent_emissions,
)
```

### View read-only contract

Views are **read-only by SQLite construction**. No `INSTEAD OF` triggers are defined. A direct `INSERT`, `UPDATE`, or `DELETE` against any view raises `sqlite3.OperationalError`. The acceptance test `tests/test_s5_views.py::test_views_reject_writes` pins this for all four views.

### View ordering guarantee

`created_seq` (the monotonic insertion-order counter from S-2) is the **canonical ordering field** for substrate consumers. Wall-clock `created_at` is informational only and may collide on fast systems. Every multi-row view orders by `created_seq` (or a derived equivalent like `emitted_seq`).

### `v_lineage_timeline`

Ordered event history per lineage_id. Rows whose `lineage_id` is NULL are excluded — the timeline is per-lineage by construction.

| Column | Type | Notes |
|---|---|---|
| `lineage_id` | TEXT | not null |
| `created_seq` | INTEGER | monotonic insertion order |
| `event_type` | TEXT | e.g. `recommendation_emitted`, `outcome_observed` |
| `payload_json` | TEXT | canonical JSON payload |

Ordering: `lineage_id ASC, created_seq ASC`.

### `v_calibration_state`

Projects `calibration_updated` events. Returns one row per event in `created_seq` ascending order. The Python helper `read_calibration_state(store)` walks rows last-write-wins per `(section, key)` pair and returns the contract dict:

```python
{
  "prior_overrides":       {prior_key: override_value},
  "evidence_thresholds":   {play_id: {threshold_name: value}},
  "materiality_overrides": {scale_band: {floor_param: value}},
}
```

| Column | Type | Notes |
|---|---|---|
| `created_seq` | INTEGER | last-write-wins requires this ordering |
| `play_id` | TEXT | scope (nullable for global overrides) |
| `payload_json` | TEXT | full event payload |

Ordering: `created_seq ASC`.

**Empty-state contract:** with zero `calibration_updated` events present (today's state — no writer ships before Phase 9), the view returns zero rows and the helper returns the same three-key empty-shape dict the calibration stub returned pre-S-5. M0 Beauty pinned fixture is byte-identical.

### `v_open_recommendations`

Most recent `recommendation_emitted` per lineage_id with no later `outcome_observed` row for the same lineage_id.

| Column | Type | Notes |
|---|---|---|
| `lineage_id` | TEXT | not null |
| `run_id` | TEXT | run that emitted |
| `play_id` | TEXT | |
| `emitted_seq` | INTEGER | `created_seq` of the emission row |
| `emitted_at` | TEXT | wall-clock; informational |
| `payload_json` | TEXT | emission payload |

Ordering: `emitted_seq ASC`.

"Most recent" is defined by `created_seq`. "No matching outcome yet" is defined as no `outcome_observed` row exists for this lineage_id with `created_seq` strictly greater than the emission's `created_seq`.

### `v_lineage_recent_emissions`

Per-lineage emission count within the trailing 28-day window. The "now" anchor is derived from `MAX(created_at)` in the events table — deterministic at test time and reproducible across runs.

| Column | Type | Notes |
|---|---|---|
| `lineage_id` | TEXT | not null |
| `count_in_last_28d` | INTEGER | `>= 1` (lineages with zero emissions in the window are excluded) |

Ordering: `lineage_id ASC`.

This view supports the `gate_recently_run` fatigue check (still flag-gated OFF via `RECENTLY_RUN_FATIGUE_ENABLED`). Production callers wanting a true wall-clock window should add their own filter; the view is meant for the existing within-store recency shape.

---

## Calibration stub rewire (S-5)

[`src/calibration_stub.py::load_realization_factors`](../src/calibration_stub.py) now optionally accepts a `store_id` keyword. When provided, it opens the per-store substrate and projects `v_calibration_state` into the contract dict. When omitted (or when the substrate is absent), it returns the empty-shape dict — preserving the pre-S-5 behaviour for legacy call sites.

The function never raises:
- arbitrary `history_path` arguments are accepted and ignored (legacy M9 contract);
- a missing `data/<store_id>/memory.db` short-circuits to the empty dict;
- a corrupt or stale db short-circuits to the empty dict.

The engine MUST keep running when the substrate is absent or empty.

---

## Manual `campaign_sent` import path (S-6)

S-6 ships the Swarm-integration boundary on the engine side. The
**engine never writes `campaign_sent` events.** All sends (whether
operator-driven manual imports today or Swarm-Deploy-Agent-driven
automated ingestion later) flow through one CLI:

```
python -m tools.import_campaign_sent <store_id> [--inbox PATH]
                                                [--base data]
                                                [--dry-run]
                                                [--no-strict]
```

Default inbox is `data/<store_id>/inbox/campaigns/*.json`. The
importer:

1. Reads each `*.json` file in lexicographic name order.
2. Validates against the `CampaignSentPayload` v1 schema (strict
   mode — see refusal rules below).
3. Cross-checks the payload against the live substrate.
4. On success, appends one `campaign_sent` event to
   `data/<store_id>/memory.db` via `MemoryStore.append_event`.

Files are NEVER moved or deleted by the importer; operator owns inbox
hygiene. Re-running the importer over the same file refuses it on the
duplicate-`campaign_id` check, so re-runs are safe.

### `campaign_sent` payload schema (event_version=1)

Pinned by [`src/memory/events.py::CampaignSentPayload`](../src/memory/events.py).
Frozen contract for the Swarm team; **additive-only future evolution**.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event_version` | int | yes | Always `1` for v1. |
| `lineage_id` | string (sha1 hex) | yes | Must match a `recommendation_emitted` event's `lineage_id` in this store. Orphan campaigns are refused. |
| `recommendation_event_id` | string (uuid hex) | yes | `event_id` of the originating `recommendation_emitted` event. Importer verifies the referenced event exists, has `event_type=recommendation_emitted`, and has the same `lineage_id`. |
| `campaign_id` | string | yes | Operator-chosen identifier. Unique within a store — duplicate refused. |
| `sent_at` | string (ISO-8601 UTC) | yes | Stored as-is; consumers parse on read. |
| `audience_size` | int >= 0 | yes | Audience N at send time. |
| `channel` | string enum | yes | One of `{"email", "sms", "push", "other"}` (`CAMPAIGN_SENT_ALLOWED_CHANNELS`). |
| `campaign_name` | string | no | Operator-supplied label. |
| `provider` | string | no | Upstream provider name (e.g. `"klaviyo"`, `"postscript"`). Free-text in v1. |
| `provider_message_id` | string | no | Provider's message id for cross-reference. |
| `notes` | string | no | Free-form operator notes. |

### Validation refusal rules (v1 strict mode)

The importer refuses a file (no event appended) for ANY of:

- malformed JSON (parse error)
- top-level JSON value is not an object
- any required field missing
- any unknown top-level key (strict v1; new keys land via additive
  schema evolution only)
- `audience_size` not a non-negative int (booleans rejected)
- `channel` outside the allowed enum
- `lineage_id` does not match any `recommendation_emitted` event in
  this store
- `recommendation_event_id` does not exist in this store
- `recommendation_event_id` exists but its `event_type` is not
  `recommendation_emitted`
- `recommendation_event_id` exists but its `lineage_id` differs from
  the payload's `lineage_id`
- `campaign_id` already used by a prior `campaign_sent` event in the
  store

Each refusal prints a one-line reason on stdout. CLI exits non-zero if
any file was refused (override with `--no-strict`).

### Additive-only evolution rule

A new field in the v1 payload may be added if and only if:

1. The field is `Optional` (default `None`).
2. The importer treats absent values as the default.
3. No existing field is removed, renamed, or re-typed.
4. The change is reflected in `CampaignSentPayload`,
   `CAMPAIGN_SENT_OPTIONAL_FIELDS`, and this table simultaneously.

Removing a field, renaming a field, or changing a field's type bumps
`CAMPAIGN_SENT_EVENT_VERSION` to `2` and is a frozen-contract change
requiring Swarm-team coordination per the plan §1 Stop-Coding-Line
guarantee.

---

## `outcome_observed` payload schema (Phase 9 contract — NOT IMPLEMENTED)

The schema below is the **frozen contract** the Phase 9 implementer
will build against. No importer ships in S-6; `tools/import_outcome_observed.py`
is reserved as the sister CLI to `tools/import_campaign_sent.py`. The
schema is documented here under the same review bar as
`campaign_sent` so Phase 9 can implement against a settled contract.

`outcome_observed` events close out an open recommendation by recording
the realized outcome of a sent campaign. Written by either:

- `tools/import_outcome_observed.py` (manual JSON import, sister to
  `import_campaign_sent.py`), OR
- the Swarm Monitor Agent (when it ships)

### Payload schema (event_version=1, target)

| Field | Type | Required | Notes |
|---|---|---|---|
| `event_version` | int | yes | Always `1` for v1. |
| `lineage_id` | string (sha1 hex) | yes | Must match a `recommendation_emitted` event in the same store. |
| `recommendation_event_id` | string (uuid hex) | yes | `event_id` of the originating `recommendation_emitted`. |
| `campaign_sent_event_id` | string (uuid hex) | yes | `event_id` of the `campaign_sent` row that produced this outcome. Importer verifies it exists and shares the lineage_id. |
| `observed_at` | string (ISO-8601 UTC) | yes | Timestamp at which the outcome was finalized. |
| `observation_window_days` | int >= 1 | yes | Window over which the outcome was measured. Must equal the originating recommendation's `expected_outcome.expected_observation_window_days` (calibration consumer needs commensurability). |
| `outcome_kind` | string enum | yes | One of `{"REPEAT_PURCHASE_IN_30D", "EMAIL_ATTRIBUTED_REVENUE_IN_7D", "INCREMENTAL_ORDERS_IN_14D"}`. Must equal the originating recommendation's `would_be_measured_by` enum value. |
| `outcome_status` | string enum | yes | One of `{"OBSERVED", "REQUIRES_INTEGRATION", "REQUIRES_HOLDOUT", "INSUFFICIENT_DATA"}`. Only `"OBSERVED"` rows feed the calibration consumer. |
| `realized_value` | float \| null | conditional | Required when `outcome_status == "OBSERVED"`; null otherwise. Unit matches `outcome_kind` (proportion delta for `REPEAT_PURCHASE_IN_30D`, dollars for revenue enums, integer count for orders). |
| `sample_size` | int >= 0 \| null | conditional | Required when `outcome_status == "OBSERVED"`. |
| `computed_by_function_version` | int >= 1 | yes | Version of the `compute_realized_outcome` function that produced this row. Bumped whenever the outcome-computation logic changes (analogous to `audience_definition_version` per D-1). |
| `notes` | string | no | Free-form notes. |

### Validation refusal rules (Phase 9 implementer must enforce)

- All `campaign_sent` validation rules apply by analogy
  (malformed JSON / missing fields / unknown fields / strict v1).
- `lineage_id` must match a `recommendation_emitted` event in the
  store.
- `campaign_sent_event_id` must exist as a `campaign_sent` event and
  share the `lineage_id`.
- `outcome_kind` must equal the originating recommendation's
  `would_be_measured_by` enum value.
- `observation_window_days` must equal the originating
  recommendation's `expected_outcome.expected_observation_window_days`.
- When `outcome_status == "OBSERVED"`: `realized_value` and
  `sample_size` must be present and the right type.
- Duplicate `campaign_sent_event_id` in a prior `outcome_observed`
  event is refused — outcomes are one-per-campaign by construction.

### Additive-only evolution rule

Same rule as `campaign_sent`: only `Optional` fields may be added
without bumping `event_version`; removal / rename / re-type is a
frozen-contract change requiring founder + Swarm-team sign-off.

---

## Swarm integration boundary contract

The substrate is the **only** integration surface between the Beacon
engine and the AI Agent Swarm. Per the Stop-Coding Line (Phase 6B,
2026-05-05) the engine does not own narration, dollar formatting,
percent framing, or any visual polish — those are downstream of the
substrate read-views.

### Who writes what, when

| Event type | Writer (today) | Writer (when Swarm ships) | Trigger |
|---|---|---|---|
| `recommendation_emitted` | `src/decide.py` via `src/main.py::_emit_substrate_events` | unchanged | Engine run, one per emitted PlayCard. |
| `recommendation_considered` | same | unchanged | Engine run, one per RejectedPlay. |
| `campaign_sent` | `tools/import_campaign_sent.py` (manual JSON drop) | additionally Swarm Deploy Agent (still through `append_event`; allowlist updated in same PR) | After a campaign is dispatched in the operator's send tool (Klaviyo / Postscript / Shopify Email). |
| `outcome_observed` | (none today; `tools/import_outcome_observed.py` reserved for Phase 9) | additionally Swarm Monitor Agent | After the `expected_observation_window_days` window closes for a `campaign_sent` event. |
| `calibration_updated` | (none today; calibration consumer reserved for Phase 9) | unchanged | After K=3 outcomes accumulate per `(play_id, vertical, store_id)` partition. |

### Engine never reads `campaign_sent` / `outcome_observed`

By construction, the engine's run loop reads only `calibration_updated`
events (via the rewired `calibration_stub` in S-5 and the Phase 9
calibration consumer). `engine_run.json` is byte-identical whether or
not `campaign_sent` / `outcome_observed` rows exist in the store; the
S-6 acceptance test pins this with a two-run integration check.

This is load-bearing: it means the engine's recommendation logic
cannot be biased by past send/outcome history except through the
explicit `calibration_updated` channel. Receipts ("we said X, observed
Y") are rendered downstream by the Swarm against `v_lineage_timeline`
join with `outcome_observed`, not by the engine.

### Single-writer-per-event-type discipline

[`tests/test_single_writer_per_event_type.py`](../tests/test_single_writer_per_event_type.py)
greps every `*.py` file under `src/` and `tools/` for quoted event-type
literals. Each event type has an allowlist of files permitted to
contain the literal. A new writer for an existing event type requires
updating the allowlist in the same PR — forces explicit cross-track
coordination before silent second-writer regressions land.

The S-6 grep allowlist for `campaign_sent` is exactly
`{tools/import_campaign_sent.py}`. The Phase 9 implementer adds
`tools/import_outcome_observed.py` to the `outcome_observed` allowlist
(currently a forward-looking entry pinned by the test's known-event-types
sanity check).
