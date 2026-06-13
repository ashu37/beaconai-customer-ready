# S-6 — Manual `campaign_sent` import path + Swarm contract

**Owner:** code-refactor-engineer (Engineer A, Sprint 3)
**Date:** 2026-05-10
**Sprint:** Sprint 3, ticket S-6 (closes Sprint 3)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §3, ticket S-6 + D-5
**Predecessor:** S-5 ([code-refactor-engineer-s5-summary.md](./code-refactor-engineer-s5-summary.md))
**Status:** Complete. Schema-freeze (`event_version=1`) preserved. Full suite green.

---

## Approved scope

1. New `tools/import_campaign_sent.py` CLI. Reads `data/<store_id>/inbox/campaigns/*.json`, validates against documented schema, appends `campaign_sent` events to per-store substrate. Strict v1: refuses malformed JSON, missing required fields, unknown fields, bad enum values, orphan lineage_id, unknown recommendation_event_id, lineage/event_id mismatch, duplicate campaign_id.
2. Define `campaign_sent` JSON payload schema in `src/memory/events.py` — typed `CampaignSentPayload` at `event_version=1`. Required fields: `lineage_id`, `recommendation_event_id`, `campaign_id`, `sent_at`, `audience_size`, `channel`. Optional fields: `campaign_name`, `provider`, `provider_message_id`, `notes`. Channel enum `{email, sms, push, other}`.
3. Define `outcome_observed` JSON schema in `docs/memory_substrate.md` ONLY — Phase 9 contract, NOT implemented.
4. Engine NEVER calls `tools/import_campaign_sent.py`. Single-writer grep allowlist for `campaign_sent` exactly `{tools/import_campaign_sent.py}`.
5. Extend `docs/memory_substrate.md` with: `campaign_sent` schema + import path + validation rules + additive-only evolution rule; `outcome_observed` Phase 9 contract; Swarm integration boundary (who writes what, when).

## Patch summary

- **`src/memory/events.py`** — Added `CampaignSentPayload` dataclass + `CAMPAIGN_SENT_EVENT_VERSION` + `CAMPAIGN_SENT_ALLOWED_CHANNELS` + `CAMPAIGN_SENT_REQUIRED_FIELDS` + `CAMPAIGN_SENT_OPTIONAL_FIELDS` constants. Mirrors the documented schema 1:1; `to_dict()` omits absent optional fields so a minimal payload serializes minimally.
- **`src/memory/__init__.py`** — Re-exports the new dataclass + constants.
- **`tools/import_campaign_sent.py` (new)** — CLI + library surface. `_validate_payload_shape` is the pure shape-check (no I/O); `_validate_against_substrate` runs the three substrate cross-checks (lineage_id existence, recommendation_event_id pairing, campaign_id uniqueness); `import_one` orchestrates one file; `import_inbox` walks the inbox in lex order. CLI exits 1 on any refusal under default `--strict`; `--no-strict` exits 0 regardless.
- **`docs/memory_substrate.md`** — Added three new sections: "Manual `campaign_sent` import path (S-6)" with schema table + refusal rules + additive-only evolution rule; "`outcome_observed` payload schema (Phase 9 contract — NOT IMPLEMENTED)" with full Phase-9-target schema + refusal rules; "Swarm integration boundary contract" pinning who writes what, when.
- **`tests/test_single_writer_per_event_type.py`** — Added `tools/import_campaign_sent.py` to the `recommendation_emitted` allowlist as a READER (substrate cross-check queries the literal). The `campaign_sent` allowlist remains exactly `{tools/import_campaign_sent.py}` and now graduates from forward-looking-vacuous-pass to strict (the file mentions the literal as the writer call site).
- **`tests/test_s6_campaign_sent_import.py` (new)** — 28 tests covering the acceptance bar.

## Files changed

| File | Change |
|---|---|
| `src/memory/events.py` | NEW types: `CampaignSentPayload` + 4 constants |
| `src/memory/__init__.py` | Re-export new symbols |
| `tools/import_campaign_sent.py` | NEW — CLI + library; single writer for `campaign_sent` |
| `docs/memory_substrate.md` | NEW sections — `campaign_sent` schema, `outcome_observed` Phase 9 contract, Swarm boundary |
| `tests/test_single_writer_per_event_type.py` | Allowlist update — reader entry on `recommendation_emitted` |
| `tests/test_s6_campaign_sent_import.py` | NEW — 28 acceptance tests |
| `memory.md` | S-6 entry in Sprint 3 section |

## Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s6_campaign_sent_import.py` | 28/28 green |
| `tests/test_single_writer_per_event_type.py` | 6/6 green (allowlist updated, grep clean) |
| `tests/test_golden_diff.py` | 3/3 green (M0 byte-identical) |
| `tests/test_slate_regression_beauty_brand.py` | 19/19 green (Beauty pinned slate sha256 unchanged) |
| `tests/test_s5_views.py` | 17/17 green (S-5 surface untouched) |
| `tests/test_s4_snapshot_immutability.py` | 6/6 green (S-4 surface untouched) |
| `tests/test_memory_store.py` | 7/7 green (S-2 substrate intact) |
| `tests/test_calibration_stub_shape.py` | 5/5 green (legacy contract preserved) |
| `tests/test_export_roundtrip.py` | green |
| Full suite (`pytest -q`) | **1129 passed, 14 skipped, 0 failed** (was 1107/14/0 at S-5 closeout) |

## Behavior changes

- New CLI surface `python -m tools.import_campaign_sent <store_id>`; writes `campaign_sent` events to `data/<store_id>/memory.db` after strict validation. No existing engine path touched.
- `data/<store_id>/inbox/campaigns/` directory is auto-created on first import call (idempotent `mkdir(parents=True, exist_ok=True)`).
- `engine_run.json` byte-identical whether or not the inbox has been imported. Two-run integration test in `tests/test_s6_campaign_sent_import.py::TestTwoRunIntegration::test_timeline_returns_emitted_then_sent` pins this end-to-end via `read_lineage_timeline`.
- `tests/test_s6_campaign_sent_import.py::TestTwoRunIntegration::test_engine_does_not_read_campaign_sent_event_type` is a structural read-isolation pin: no `*.py` file under `src/` references the literal `'campaign_sent'` or `"campaign_sent"`. Complements the single-writer grep on the read side.

## Artifacts added

- `tools/import_campaign_sent.py` (new tool, ~280 lines)
- `tests/test_s6_campaign_sent_import.py` (new test, 28 tests)
- New sections in `docs/memory_substrate.md` (~190 lines added)
- `agent_outputs/code-refactor-engineer-s6-summary.md` (this file)

## Remaining risks

1. **No live `outcome_observed` writer exists yet.** The schema is documented to the same review bar as `campaign_sent`, but Phase 9 is the implementer. If Phase 9 deviates from the documented refusal rules (e.g. accepts `outcome_status="OBSERVED"` with null `realized_value`), calibration consumers downstream silently ingest junk. Phase 9's first PR must include a positive-projection acceptance test against the documented schema.
2. **`campaign_id` uniqueness is per-store, not global.** Two stores may share a `campaign_id` value without collision. This is intentional (the Swarm tracks campaigns per merchant) but worth pinning if/when cross-store analytics ship.
3. **`provider` is free-text in v1.** When the Swarm Deploy Agent ships, it will likely want a closed enum. Adding the enum is `event_version=2` (re-typing a field), so the founder + Swarm team must coordinate before that change. Documented in the additive-only evolution rule.
4. **The reader-allowlist entry on `recommendation_emitted` is a grep-time hack.** A future agent renaming `import_campaign_sent.py` or adding a second cross-checking importer must update both allowlists by hand. Preferable long-term: a `# allowlist: reads recommendation_emitted` decorator that the grep test ignores. Not in scope here.
5. **Inbox files persist after successful import.** Operator must clean up. Re-running the importer over a non-empty inbox refuses every file with the duplicate-`campaign_id` reason — safe but noisy. A future `--archive` flag is plausible; out of scope.
6. **Sent-time validation is shape-only.** `sent_at` is stored as a string and never parsed for ISO-8601 conformance. Phase 9's `compute_realized_outcome` will need a real parse; if the operator drops a malformed timestamp here, Phase 9 sees the issue, not S-6.

## Next milestone dependencies

- **Phase 8 (Swarm-integrated)** — Swarm Deploy Agent writes `campaign_sent` events; allowlist update ships in same PR. View `v_lineage_timeline` returns multi-event chains for real merchant data; B-1 surface (currently dormant) reads them via the read-views.
- **Phase 9 L-C `compute_realized_outcome`** — Implements `tools/import_outcome_observed.py` against the documented schema in `docs/memory_substrate.md`. Adds writer to `outcome_observed` allowlist in `tests/test_single_writer_per_event_type.py`. Two-run integration test pattern in this S-6 acceptance test is the template.
- **Phase 9 L-D #1 calibration consumer** — Reads `outcome_observed` via `v_open_recommendations` join. The documented `outcome_status="OBSERVED"` rule is the gate.

## Branch shape

Per the per-commit ritual on `post-6b-restructured-roadmap` (not pushed):

1. `091114e` — `S-6: manual campaign_sent import path + Swarm contract (closes Sprint 3)` (impl)
2. `fc4d996` — `Document S-6 in repo memory.md` (memory)
3. `S-6 summary` (this file)

## Hard constraints respected

- `engine_run.json` schema **unchanged** — no payload writes from S-6 to the engine; importer writes only into the substrate.
- `event_version` for `recommendation_*` stays `1` — no changes to those payload schemas. New `campaign_sent` payload also at `v1` per ticket.
- M0 Beauty pinned fixture sha256 **unchanged** (`test_golden_diff` 3/3 green, `test_slate_regression_beauty_brand` 19/19 green).
- `recommendation_emitted` / `recommendation_considered` payloads frozen (Sprint 2 schema-freeze) — no changes to `EvidenceSnapshot` / `ExpectedOutcome` / `RecommendationEmittedPayload` / `RecommendationConsideredPayload`.
- D-5 respected: manual JSON import only. No Klaviyo SDK, no OAuth, no webhook receivers.
- D-6 respected: no ML scaffolding. `campaign_sent` is operational data.
- No new runtime dependencies (`argparse` + `json` from stdlib only).
- `src/main.py` snapshot writer (S-4) **untouched**.
- `src/memory/views.*` (S-5) **untouched**.
- Single-writer-per-event-type allowlist updated for both `campaign_sent` (writer entry, graduates from vacuous to strict) and `recommendation_emitted` (reader entry, with comment pinning the rationale).
