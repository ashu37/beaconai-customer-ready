# S-3 — Engine writes `recommendation_*` events to substrate (closes Sprint 2)

**Owner:** code-refactor-engineer (Engineer A, S-3 final wiring)
**Date:** 2026-05-10
**Sprint:** Sprint 2 closeout
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §2, ticket S-3 (bundles B-2)
**Substrate dependency:** S-2 ([code-refactor-engineer-s2-summary.md](./code-refactor-engineer-s2-summary.md))
**Schema dependency:** S-3 prep ([code-refactor-engineer-s3-prep-summary.md](./code-refactor-engineer-s3-prep-summary.md))
**Founder decisions consulted:** D-1 (audience_definition_version policy), D-3 (full wipe only), D-6 (banned ML scaffolding), D-8 (vertical hard-lock).
**Status:** Complete. Schema freeze for Swarm team in effect. Full suite green. Beauty pinned fixture re-pinned in same commit per plan §7 Risk #4.

---

## Why this is the schema-freeze milestone

End of S-3 marks the point where the Swarm team begins building against pinned `recommendation_emitted` / `recommendation_considered` payloads. From this commit forward, the payload schemas at `event_version = 1` are a **frozen contract**. Any field-shape change requires founder sign-off, an `event_version++`, and Swarm-team coordination. Additive-only fields with safe defaults are still permitted under that discipline.

This is the third and final mechanical step for Sprint 2's substrate-writing path:

1. **S-2** built the SQLite substrate + lineage helper + CLIs (Engineer A, isolated).
2. **S-3 prep** pinned the typed payload dataclasses + reason-code fan-out behind a default-OFF flag (Engineer B, parallel).
3. **S-3 final** (this ticket) wires `decide()`'s output into `append_event()`, flips the fan-out flag on, re-pins the Beauty fixture, and removes the gating helper. Mechanical, no architectural decisions.

## Scope delivered

1. Engine emits one `recommendation_emitted` event per `PlayCard` in `recommendations` and `recommended_experiments`, one `recommendation_considered` event per `RejectedPlay` in `considered`. Single writer per event type (grep-test enforced).
2. Lineage tuple per founder decision D-1: `(store_id, play_id, audience_definition_id, audience_definition_version)`. All four args required at every `compute_lineage_id(...)` call.
3. Substrate writes are PURELY ADDITIVE — the engine continues to produce `engine_run.json` and the briefing if `open_memory(store_id)` raises. Caller's try/except in `src/main.py::run` is the load-bearing layer.
4. Reason-code fan-out activated unconditionally; `ENGINE_S3_REASON_FANOUT` flag and `_s3_fanout_enabled()` helper REMOVED.
5. Beauty pinned slate fixture re-pinned in the same commit (plan §7 Risk #4 atomicity).
6. `src/memory_events.py` → `src/memory/events.py` (typed payloads now part of the `src/memory/` package).

## Files changed

| File | Change |
|---|---|
| [src/memory/events.py](../src/memory/events.py) | RENAMED from `src/memory_events.py`. Typed `EvidenceSnapshot`, `ExpectedOutcome`, `RecommendationEmittedPayload`, `RecommendationConsideredPayload`, `RECOMMENDATION_EVENT_VERSION` move into the `src/memory/` package. |
| [src/memory/__init__.py](../src/memory/__init__.py) | Re-exports the typed payload schemas alongside `open_memory`, `MemoryStore`, `compute_lineage_id`. |
| [src/main.py](../src/main.py) | New module-level `_emit_substrate_events(...)` (plus `_emit_one_play_card`, `_emit_one_rejected_play`, `_evidence_snapshot_for`, `_expected_outcome_for`, `_audience_definition_id`, `_audience_definition_version` helpers). Replaced the 38-line S-3 TODO comment block with a single try/except call. |
| [src/decide.py](../src/decide.py) | REMOVED `_s3_fanout_enabled()` helper. `_candidate_reason_code` now consults `_S3_FANOUT_REASON_MAP` unconditionally for short codes not already in `_PRELIM_REASON_MAP`. |
| [tests/test_s3_substrate_emission.py](../tests/test_s3_substrate_emission.py) | NEW. 5 tests: events emitted; `lineage_id` byte-stable across two runs of Beauty fixture; `run_id` distinct per run; engine survives substrate-init failure (subprocess-level); helper propagates `open_memory` errors (in-process). |
| [tests/test_s3_memory_event_schemas.py](../tests/test_s3_memory_event_schemas.py) | Import path updated `src.memory_events` → `src.memory.events`. |
| [tests/test_s3_reason_code_fanout.py](../tests/test_s3_reason_code_fanout.py) | Replaced flag-ON / flag-OFF parametrized tests with a single unconditional-mapping test (the gating flag no longer exists). |
| [tests/test_single_writer_per_event_type.py](../tests/test_single_writer_per_event_type.py) | `_ALLOWED_WRITERS` allowlist updated for `src/memory/events.py`. |
| [tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html](../tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html) | RE-PINNED (plan §7 Risk #4: flag flip + goldens re-pin must be atomic). |

## Beauty fixture re-pin (atomic with flag flip)

Per plan §7 Risk #4, the typed-reason fan-out flag flip and the Beauty pinned-fixture re-pin MUST be in the same commit:

| | sha256 |
|---|---|
| **Before** | `ed02ddc2bc33564e2b1647dc725d69bc70e69cde4dd878e3358fad87d97e7914` |
| **After**  | `45edaca58c47797addf556b91460b81782dba6653d5d1ec82043bd40a051ea78` |

**Diff scope (single change):** the `empty_bottle` Considered card flips `data-reason-code="no_measured_signal"` → `data-reason-code="data_quality_flag"`. The previous code was the legacy NO_MEASURED_SIGNAL fallback; the new code is the typed `DATA_QUALITY_FLAG` from `_S3_FANOUT_REASON_MAP` mapping the candidate's `preliminary_rejection_reason="data_missing"` short code. This is exactly the behavior change the plan calls for and the only byte change in `engine_run.json` shape.

**M0 goldens (small_sm, mid_shopify, micro_coldstart) remain byte-identical.** Those three legacy fixtures do not exercise the S-3 fan-out short codes (their Considered cards continue to map through `_PRELIM_REASON_MAP` to legacy reason codes), so the re-pin is scoped to the synthetic slate fixture only.

## Hard constraints respected

- `engine_run.json` schema **unchanged in shape** (dataclass fields untouched); only Considered `reason_code` *values* fan out (additive).
- M0 goldens (`tests/test_golden_diff.py`) **byte-identical** — all 3 merchant fixtures green.
- Substrate writes are PURELY ADDITIVE — the engine still produces `engine_run.json` and briefing.html if `memory.db` cannot open. Caller's try/except in `src/main.py::run` catches and prints a `[Substrate] Warning: ...` line; the rest of the run proceeds.
- D-1 lineage-tuple discipline: all 4 args required at every `compute_lineage_id(...)` call. The version field defaults to `1` until the audience-builder pipeline carries an explicit integer; the founder closes that gap separately. The lineage_id is still **deterministic and stable across runs of the same fixture** (the acceptance test pins this).
- D-3 deletion semantics: per-store `data/<store_id>/memory.db` remains the deletion unit; no row-level delete APIs introduced.
- D-6 ML scaffolding: untouched.
- D-8 vertical hard-lock: untouched.
- Single-writer per event type: `recommendation_emitted` / `recommendation_considered` written ONLY from `src/decide.py`, `src/main.py`, `src/memory/events.py` (last is the schema dataclass file, allowlisted for the literal in docstring/dataclass annotations). Grep test enforced.

## Acceptance test results

| Acceptance criterion | Test | Result |
|---|---|---|
| Beauty fixture re-pinned with new sha; no other golden changes | `test_slate_regression_beauty_brand.py` (19 tests) + `test_golden_diff.py` (3 fixtures) | green; sha256 `45edaca5...` |
| `engine_run.json` bytes change ONLY due to typed reason codes flowing into Considered cards | Manual diff inspection (one byte-shift at offset 12277 in Beauty fixture; `data_quality_flag` replaces `no_measured_signal` for `empty_bottle` Considered card) | confirmed |
| Substrate emits `recommendation_emitted` + `recommendation_considered` events | `test_s3_substrate_emission.py::test_substrate_emits_recommendation_events` | green |
| `tools/inspect_memory.py` shows them after a Beauty run | Manual harness run; `python -m tools.inspect_memory <store_id> --base <data_dir> --json --limit 2` | confirmed (sample row in branch report) |
| Lineage_id stable across two runs of the same Beauty fixture (audit L-B regression test) | `test_s3_substrate_emission.py::test_lineage_id_stable_across_runs` | green |
| Single-writer grep test | `test_single_writer_per_event_type.py` (6 tests) | green |
| Full suite green | `pytest -q` | **1084 passed, 14 skipped, 0 failed** (was 1047/14/0 baseline pre-S-3) |
| M0 + Beauty re-pin together (NOT separately) | Single impl commit | confirmed |

## Sample event row (`tools/inspect_memory.py --json`)

The first `recommendation_emitted` event from a real Beauty harness run, lightly reformatted for readability (the actual NDJSON is one line per row):

```json
{
  "event_id": "244186283d2d44bfa5e0ce566f8a371d",
  "event_type": "recommendation_emitted",
  "lineage_id": "3b356d8176a16f5819a566b8d87ded93ebc3315e",
  "run_id": "1aaf8be5-77ed-4593-adb8-2f4c22d2c5ac",
  "store_id": "healthy_beauty_240d",
  "play_id": "first_to_second_purchase",
  "audience_definition_id": "phase5_first_to_second_purchase",
  "audience_definition_version": 1,
  "event_version": 1,
  "created_at": "2026-05-10T07:56:12.566731Z",
  "created_seq": 1,
  "payload": {
    "event_version": 1,
    "run_id": "1aaf8be5-77ed-4593-adb8-2f4c22d2c5ac",
    "lineage_id": "3b356d8176a16f5819a566b8d87ded93ebc3315e",
    "store_id": "healthy_beauty_240d",
    "play_id": "first_to_second_purchase",
    "audience_definition_id": "phase5_first_to_second_purchase",
    "audience_definition_version": 1,
    "role": "recommendation",
    "evidence_snapshot": {
      "evidence_class": "directional",
      "window_label": "L28",
      "effect_abs": 0.1148588627281809,
      "p_internal": 0.0010164023064044771,
      "sample_size": 2288,
      "multiwindow_agreement": 3.0,
      "data_quality_flags": [],
      "measurement_design_version": 1
    },
    "expected_outcome": {
      "expected_direction": "increase",
      "min_interesting_effect_size": 0.02,
      "expected_observation_window_days": 30
    },
    "snapshot_path": null,
    "snapshot_sha256": null
  }
}
```

The second emitted event in the same run is a `discount_hygiene` `recommended_experiment` card with `evidence_class="targeting"`, `expected_observation_window_days=7` (driven by `WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D`), and all stat fields at `null` per the Phase 6A discipline that targeting plays ship `measurement=None`.

## Key design decisions (judgment calls)

1. **`_emit_substrate_events` opens `MemoryStore` once per run, not once per card.** The S-2 `MemoryStore` carries an in-process `threading.Lock` and a single SQLite connection. Per-card `open_memory(...)` calls would multiply the SQLite open/migrate/close cost by ~10× on a typical Beauty run for no concurrency benefit (the calls are sequential within one engine run). The single connection is closed in `finally:` so a partial-failure leaves no lingering FD.

2. **Helper *propagates* `open_memory` failures; the *caller* swallows them.** The unit test `test_emit_substrate_events_swallows_open_failure` deliberately pins this split. If the helper itself swallowed errors, ops would see no signal — the substrate would silently stop accumulating events. The caller's `[Substrate] Warning: ...` line is the operational surface; it points to the underlying `RuntimeError` so the cause is investigatable.

3. **`audience_definition_id` falls back to `play_id` when `audience.id` is empty.** D-1 requires a non-empty string for the lineage tuple. Some `RejectedPlay` rows are held BEFORE an audience builder runs (e.g. `inventory_blocked` candidates can be rejected with no audience attached). Falling back to `play_id` keeps the lineage tuple shaped — and stable across runs — without inventing a synthetic ID. The lineage_id collision risk is bounded: two plays with the same `play_id` would already conflict by definition.

4. **`audience_definition_version = 1` default is a transition, not a permanent shortcut.** Once the audience-builder pipeline carries an explicit version (founder gap), the helper switches to reading it directly. The default-1 behavior today does NOT excuse a future engineer from bumping the version when audience logic changes — D-1 still bites. The lineage_id stability test pins the contract: same fixture two runs → byte-identical lineage_id.

5. **`_S3_FANOUT_REASON_MAP` kept separate from `_PRELIM_REASON_MAP`.** With the gating flag removed, merging the two maps would simplify the lookup. We kept them separate because the additive provenance is auditable at a glance — legacy mappings on top, S-3 fan-out below — and so the single-writer grep test on the typed `DATA_QUALITY_FLAG` / `MATERIALITY_BELOW_FLOOR` codes can locate them quickly.

6. **`ExpectedOutcome.expected_direction = "increase"` default.** Every shipped play in the registry today predicts an increase in its outcome metric; explicit two-sided plays (e.g. discount-hygiene margin movement) need to override at recommendation-build time. Hardcoding `"increase"` is the conservative default — the calibration consumer (Phase 9) treats "wrong direction" as a distinct bucket from "below threshold," so a misclassified two-sided play surfaces as a calibration gap rather than silently passing.

7. **`expected_observation_window_days` driven by `WouldBeMeasuredBy` enum, NOT a hardcoded 30.** The enum already encodes the natural window (`REPEAT_PURCHASE_IN_30D`, `EMAIL_ATTRIBUTED_REVENUE_IN_7D`, `INCREMENTAL_ORDERS_IN_14D`). Reading from the enum keeps the contract self-consistent and makes the inevitable Phase 9 ladder of new outcome metrics a one-line addition.

8. **Subprocess test `test_substrate_failure_does_not_crash_engine` deliberately uses the harness, not in-process monkey-patching.** The synthetic harness runs the engine in a child process; the in-process `monkeypatch.setattr(_main, "open_memory", _boom)` does NOT propagate to the child. The test still exercises the additive contract end-to-end (the engine returns rc=0, `engine_run.json` is produced) — which is the operationally important guarantee — and the in-process unit test (`test_emit_substrate_events_swallows_open_failure`) covers the helper-level error propagation directly.

## Out of scope (deliberately deferred)

- Immutable snapshot path resolution + `snapshot_sha256` population — **S-4**. The payload schema already accepts these fields (`Optional[str]`); S-4 wires the producer.
- Read-views (`v_lineage_timeline`, `v_calibration_state`, `v_open_recommendations`, `v_lineage_recent_emissions`) + `calibration_stub` rewire — **S-5**.
- Manual `tools/import_campaign_sent.py` import path — **S-6** (Swarm contract).
- Explicit `audience_definition_id` / `audience_definition_version` fields on the `Audience` dataclass — founder gap, separate from S-3.
- Pre-registered per-play `expected_direction` / `min_interesting_effect_size` from `priors.yaml` — Phase 9 work, lands when the calibration consumer needs richer signal than the conservative default.
- Calibration consumer — Phase 9 L-D #1.

## Risks observed during implementation (none unresolved)

1. **Beauty fixture drift was exactly as predicted.** The S-3 prep summary called the byte offset (12277) and the substring (`empty_bottle` Considered card flip). Reality matched. No silent secondary drift was surfaced by the fan-out activation, indicating the prep gating discipline held.

2. **`tests/test_s3_reason_code_fanout.py` had a flag-OFF inert test that became wrong post-flip.** Updated the test to a single unconditional-mapping parametrized test. The test name `test_s3_fanout_mappings_fire_unconditionally` documents the post-flip contract.

3. **Single-writer grep allowlist needed updating in two places** — the literal path strings in `_ALLOWED_WRITERS` plus the docstring reference. Caught by the failing test on first run; updated and re-ran green.

4. **`_emit_substrate_events` initial draft used `getattr(memory, "append_event")` as a free function call.** S-2's `MemoryStore.append_event` is a bound method, not a free import. The S-3 prep punch list said `append_event(memory, "recommendation_emitted", payload.to_dict())` (free-function shape). Resolved by calling `memory.append_event(event_type=..., payload=...)` directly — the public API is the bound method. The TODO block in the prep commit reflected the prep-author's expectation; S-2's actual API is what we wired against.

## Branch shape

Two commits on `post-6b-restructured-roadmap` (not pushed):

1. `d7dc96f` — `S-3: engine writes recommendation_* events to substrate (closes Sprint 2)`
2. `41a8573` — `Document S-3 in repo memory.md`
3. (this file) — `S-3 summary`

## Schema-freeze milestone for the Swarm team

End of S-3. The `recommendation_emitted` and `recommendation_considered` payloads at `event_version = 1` are the **frozen contract** the Swarm team builds against. Schema additions after this point are additive-only with founder sign-off. The single-writer grep test enforces that no second producer of these event types slips in without a same-PR allowlist update.

Sprint 2 closeout complete.
