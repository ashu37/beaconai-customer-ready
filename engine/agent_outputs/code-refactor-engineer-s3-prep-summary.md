# S-3 Prep — Reason-code Fan-out + Typed Event Schemas (NON-merging)

**Owner:** code-refactor-engineer (Engineer B)
**Date:** 2026-05-09
**Sprint:** Sprint 2 (Engineer B track, S-3 prep — substrate-independent)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §2, ticket S-3 (bundles B-2)
**Audit reference:** [agent_outputs/post-6b-stop-coding-audit.md](./post-6b-stop-coding-audit.md) §B-2 surfaces a/b, §L-E pre-registration
**Status:** Complete. Awaits Engineer A's S-2 substrate before final wiring can land.

---

## Why this is a separate "prep" commit

S-3 is the engine-writes-events ticket bundled with B-2 (per implementation plan §2 Ordering 2). The substrate writer (`src/memory/store.py::append_event`) and lineage helper (`src/memory/lineage.py::compute_lineage_id`) live behind ticket S-2, owned by Engineer A in parallel. S-2 is not yet merged to `post-6b-restructured-roadmap`. **This commit lands all NON-substrate S-3 work** so the final wire-up post-S-2 is a mechanical change (~5 import lines + 2 loops + 1 file move + 1 flag flip + 1 goldens re-pin), not a from-scratch implementation.

The four surfaces shipped here are the parts of S-3 that are independent of the substrate writer:

1. **Reason-code fan-out** (B-2 surface a) — pure typed-enum mapping in `src/decide.py`.
2. **Typed `EvidenceSnapshot`** (B-2 surface b) — pure dataclass with no I/O.
3. **Pre-registered `ExpectedOutcome`** (audit L-E) — pure dataclass with no I/O.
4. **Single-writer grep test stub** — pure source-text scanner; no runtime hook.

## Files changed

| File | Change |
|---|---|
| [src/decide.py](../src/decide.py) | NEW `_S3_FANOUT_REASON_MAP` (6 entries) + `_s3_fanout_enabled()` helper reading `ENGINE_S3_REASON_FANOUT` env var. `_candidate_reason_code` extended to consult the fan-out map only when flag is set. Legacy `_PRELIM_REASON_MAP` untouched. |
| [src/memory_events.py](../src/memory_events.py) | NEW — typed `EvidenceSnapshot`, `ExpectedOutcome`, `RecommendationEmittedPayload`, `RecommendationConsideredPayload` dataclasses + `RECOMMENDATION_EVENT_VERSION = 1` constant. Pure schema module, no runtime callers. |
| [src/main.py](../src/main.py) | NEW multi-line TODO block right after `engine_run.json` write (line 925) carrying the exact import + call shape that S-3 will replace once S-2 lands. Pure comment, no runtime change. |
| [tests/test_s3_reason_code_fanout.py](../tests/test_s3_reason_code_fanout.py) | NEW — 18 tests pinning legacy mappings, fan-out-flag-ON behavior, fan-out-flag-OFF inert behavior, default fallback, and reachability of the 5 plan-required ReasonCodes across the union of both maps. |
| [tests/test_s3_memory_event_schemas.py](../tests/test_s3_memory_event_schemas.py) | NEW — 6 tests pinning `RECOMMENDATION_EVENT_VERSION=1`, `to_dict` shape for all 4 dataclasses, `targeting`-class None acceptance, optional fields on Considered. |
| [tests/test_single_writer_per_event_type.py](../tests/test_single_writer_per_event_type.py) | NEW — 6 tests (5 parametrized event types + allowlist coverage). Grep-based; fails CI if any file outside the per-event-type allowlist contains the literal event-type string. |

## Surfaces delivered

### Surface 1 — Reason-code fan-out (B-2 surface a)

The plan calls for `_candidate_reason_code` to emit `AUDIENCE_TOO_SMALL`, `COLD_START`, `INVENTORY_BLOCKED`, `MATERIALITY_BELOW_FLOOR`, `DATA_QUALITY` instead of collapsing all to `NO_MEASURED_SIGNAL`. Two of the five (`AUDIENCE_TOO_SMALL`, `INVENTORY_BLOCKED`) were already in `_PRELIM_REASON_MAP`. The other three needed mappings:

```python
_S3_FANOUT_REASON_MAP: dict[str, ReasonCode] = {
    "data_missing": ReasonCode.DATA_QUALITY_FLAG,
    "data_quality": ReasonCode.DATA_QUALITY_FLAG,
    "cold_start": ReasonCode.COLD_START_INSUFFICIENT_DATA,
    "insufficient_history": ReasonCode.COLD_START_INSUFFICIENT_DATA,
    "materiality_below_floor": ReasonCode.MATERIALITY_BELOW_FLOOR,
    "below_materiality_floor": ReasonCode.MATERIALITY_BELOW_FLOOR,
}
```

`_candidate_reason_code` consults the fan-out map only when `ENGINE_S3_REASON_FANOUT` is truthy in the env. The default-OFF posture is the load-bearing design decision — see "Design decisions" below.

### Surface 2 — Typed `EvidenceSnapshot` (B-2 surface b)

Frozen dataclass in `src/memory_events.py`:

```python
@dataclass(frozen=True)
class EvidenceSnapshot:
    evidence_class: Literal["measured", "directional", "targeting"]
    window_label: str
    effect_abs: Optional[float]
    p_internal: Optional[float]
    sample_size: Optional[int]
    multiwindow_agreement: Optional[float] = None
    data_quality_flags: List[str] = field(default_factory=list)
    measurement_design_version: int = 1
```

`targeting` plays explicitly accept `None` for `effect_abs` / `p_internal` per the Phase 6A discipline that `targeting` candidates ship `measurement=None` (subscription_nudge / routine_builder per memory.md). The `data_quality_flags` list snapshots `EngineRun.data_quality_flags` at emission time so calibration can skip outcomes from anomalous-window runs.

### Surface 3 — Pre-registered `ExpectedOutcome` (audit L-E)

Frozen dataclass in `src/memory_events.py`:

```python
@dataclass(frozen=True)
class ExpectedOutcome:
    expected_direction: Literal["increase", "decrease", "either"]
    min_interesting_effect_size: float
    expected_observation_window_days: int
```

Audit reference L-E: every `recommendation_emitted` event MUST carry these three fields. Pre-registration prevents post-hoc rationalization at calibration time. The Phase 9 calibration consumer (L-D #1 trailing-window mean) compares the realized outcome against `expected_direction` and `min_interesting_effect_size` to decide "as predicted" vs "below threshold" vs "wrong direction." `expected_observation_window_days` must match the play's `would_be_measured_by` enum natural window (e.g. 30 for `REPEAT_PURCHASE_IN_30D`).

### Surface 4 — Single-writer grep test stub

`tests/test_single_writer_per_event_type.py` enforces plan §8 cross-track coupling: each event type has exactly one allowed writer module. The allowlist:

| Event type | Allowed writer(s) |
|---|---|
| `recommendation_emitted` | `src/decide.py`, `src/main.py`, `src/memory_events.py` (schema mention) |
| `recommendation_considered` | same as above |
| `campaign_sent` | `tools/import_campaign_sent.py` (post-S-6) |
| `outcome_observed` | `tools/import_outcome_observed.py` (post-Phase 9) |
| `calibration_updated` | `src/calibration_stub.py` (consumer view, NOT a writer yet) |

The test today is vacuous-passing for emit/considered (substrate not yet wired). It graduates to a strict guard the moment S-3 wires `append_event` — any unauthorized second writer will fail CI on the next commit.

## Design decisions

### Decision 1 — `ENGINE_S3_REASON_FANOUT` default OFF

**Why:** with the fan-out enabled by default, Beauty's `empty_bottle` Considered card flips reason code from `no_measured_signal` (current default fallback) to `data_quality_flag` (the typed S-3 code). This perturbs the briefing HTML at byte 12277 and breaks the M0 Beauty pinned fixture (`actual[..first_diff..]='lay-id="empty_bottle" data-reason-code="data_quality_flag">…'` vs expected `'…data-reason-code="no_measured_signal">…'`).

The plan §7 Risk #4 anticipates this exactly: *"reason codes added additively; the 5 new codes only fire when their specific signal is present; default `NO_MEASURED_SIGNAL` retained; **re-pin goldens in S-3 commit and document the diff**."* The flag-OFF default lets this prep commit ship without a goldens re-pin (which is itself a non-trivial founder-review event); the flag flips ON in the S-3 final commit alongside the documented re-pin. **The default-OFF posture is load-bearing for M0 byte-identity on this branch.**

### Decision 2 — Additive only, no re-targeting of legacy short codes

`_S3_FANOUT_REASON_MAP` is consulted ONLY for short codes NOT already in `_PRELIM_REASON_MAP`. Legacy mappings (`audience_zero`, `no_builder`, `inventory_blocked`, etc.) are untouched. This satisfies plan §7 Risk #4's "additive only" mitigation and means a future engineer reading `_PRELIM_REASON_MAP` doesn't have to mentally diff against a separate fan-out table — the fan-out is strictly extension.

### Decision 3 — `src/memory_events.py` flat-file location

S-2 introduces the `src/memory/` package. Until that package exists, this commit puts the typed schemas in a flat file at `src/memory_events.py`. The TODO block in `src/main.py:927` calls out the eventual move to `src/memory/events.py`. The `_ALLOWED_WRITERS` dict in the single-writer test allowlists `src/memory_events.py` for now; the S-3 final commit updates the allowlist to `src/memory/events.py` in the same file move.

Rationale: creating an empty `src/memory/__init__.py` on this branch would conflict with S-2's own package init and force a merge fix-up. A flat file with a documented eventual-move marker is cleaner.

### Decision 4 — TODO block, not a stub function

The S-3 wire-up site in `src/main.py:927` is a multi-line comment block listing the exact imports and call shape the final commit will use. Alternatives considered:

- **Stub function `_emit_recommendation_events()` that no-ops.** Rejected: an empty function is harder to spot during S-3 final wiring (you have to remember it exists) than a TODO block grep'd by the rebaser.
- **Feature flag wrapping a no-op.** Rejected: same problem plus it would require shipping the `_s3_fanout_enabled()` pattern twice.
- **Empty try/except around `from .memory.store import append_event`.** Rejected: silently masks the S-2 dependency at runtime, which is the opposite of what we want.

A grep'able TODO block is the smallest possible surface that makes the rebase mechanical.

## Tests

36 new tests across 3 files:

### `tests/test_s3_reason_code_fanout.py` (18)

- 9 parametrized regression tests — every entry in `_PRELIM_REASON_MAP` continues to map to its current ReasonCode (additive contract).
- 6 parametrized fan-out-flag-ON tests — each new short code in `_S3_FANOUT_REASON_MAP` produces the expected typed code when `ENGINE_S3_REASON_FANOUT=1`.
- 3 parametrized fan-out-flag-OFF inert tests — same short codes fall through to `NO_MEASURED_SIGNAL` when the flag is unset (the default-OFF contract).
- 1 default-fallback test — candidate with no `preliminary_rejection_reason` still defaults to `NO_MEASURED_SIGNAL`.
- 1 unknown-short-code test — a future short code not in either map falls through to `NO_MEASURED_SIGNAL`, NOT to a typed code.
- 1 reachability test — the 5 plan-required ReasonCodes are reachable from the union of `_PRELIM_REASON_MAP ∪ _S3_FANOUT_REASON_MAP`.

### `tests/test_s3_memory_event_schemas.py` (6)

- `RECOMMENDATION_EVENT_VERSION` pinned at 1 (any bump is a Swarm-team coordination event).
- `ExpectedOutcome.to_dict` produces the documented JSON shape.
- `EvidenceSnapshot` required + default fields.
- `EvidenceSnapshot` accepts None for `targeting`-class plays.
- `RecommendationEmittedPayload.to_dict` round-trip.
- `RecommendationConsideredPayload` accepts None for `evidence_snapshot` / `expected_outcome`.

### `tests/test_single_writer_per_event_type.py` (6)

- 5 parametrized: for each event type, every file mentioning the literal must be on the allowlist.
- 1 sanity: the allowlist covers all 5 event types the plan freezes for Sprint 2 / 3 / Phase 9.

## Hard constraints respected

- `engine_run.json` schema **unchanged** — no event payload writes happen on this branch yet.
- M0 Beauty pinned fixture **byte-identical** — verified via `tests/test_slate_regression_beauty_brand.py::test_briefing_matches_pinned_fixture_bytewise`.
- `RECENTLY_RUN_FATIGUE_ENABLED` and other guardrail flags untouched.
- Vertical scope hard-lock (B-7) untouched.
- No substrate work — `src/memory/` package not created; no `append_event` or `compute_lineage_id` calls.
- No banned ML scaffolding (D-6).
- Engine remains runnable after the patch.
- Single-writer-per-event-type discipline preserved; grep test pins it for the future.
- `event_version=1` pinned; any future bump must update the schema doc and coordinate with Swarm.

## Acceptance results

| Suite | Result |
|---|---|
| `tests/test_s3_reason_code_fanout.py` | 18/18 |
| `tests/test_s3_memory_event_schemas.py` | 6/6 |
| `tests/test_single_writer_per_event_type.py` | 6/6 |
| `tests/test_s1_7_vertical_resolution.py` (companion) | 12/12 |
| `tests/test_slate_regression_beauty_brand.py` (M0) | 19/19 (byte-identical) |
| `tests/test_vertical_hard_refuse.py` (B-7) | 21/21 |
| **Full suite** | **1047 passed, 14 skipped, 0 failed** (~5 min) |

## What S-3 final wiring needs (post-S-2 rebase)

This is the punch list the rebaser executes when S-2 lands on `post-6b-restructured-roadmap`:

1. **Rebase** `sprint2-engineer-b` onto `post-6b-restructured-roadmap` (post-S-2).
2. **Replace TODO block** in `src/main.py:927` with:
   ```python
   from .memory.store import open_memory, append_event
   from .memory.lineage import compute_lineage_id
   from .memory.events import (
       RecommendationEmittedPayload,
       RecommendationConsideredPayload,
       EvidenceSnapshot,
       ExpectedOutcome,
       RECOMMENDATION_EVENT_VERSION,
   )
   ```
3. **Wire emission loops:** for each `PlayCard` in `recommendations` and `recommended_experiments`, build `RecommendationEmittedPayload` and call `append_event(memory, "recommendation_emitted", payload.to_dict())`. For each `RejectedPlay` in `considered`, call `append_event(... "recommendation_considered" ...)`.
4. **Lineage tuple** is `(store_id, play_id, audience_definition_id, audience_definition_version)` per founder decision D-1. Computed via `compute_lineage_id(...)` from S-2.
5. **Move** `src/memory_events.py` → `src/memory/events.py`. Update the `_ALLOWED_WRITERS` allowlist in `tests/test_single_writer_per_event_type.py` accordingly.
6. **Flip the flag default:** set `ENGINE_S3_REASON_FANOUT=1` in engine defaults (or remove the gating helper and inline the union of both maps). Re-pin the Beauty pinned fixture (`tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`) in the same commit per plan §7 Risk #4.
7. **Add the determinism CI test** (G-7 acceptance overlap): two-run `lineage_id` byte-identity for `first_to_second_purchase` is the S-3 acceptance test (a) and lands here.
8. **Single-writer grep test** transitions from vacuous-passing to strict — any unauthorized second writer fails CI immediately.

## Out of scope (deliberately not touched)

- Calling `append_event` or `compute_lineage_id` — those modules are S-2 and don't exist yet.
- Engine-side substrate I/O wiring — final S-3 work, post-S-2 rebase.
- Re-pinning Beauty goldens with the typed reason codes — final S-3 work, paired with `ENGINE_S3_REASON_FANOUT=1`.
- Migrating to `src/memory/events.py` — final S-3 work, after `src/memory/` package exists.
- `audience_definition_id` / `audience_definition_version` propagation through the audience builder pipeline — D-1 is decided; the plumbing lands in S-3 final wiring (the schemas already accept the fields).
- Snapshot SHA256 computation — S-4 work, lands after S-3.
- Immutable snapshot path resolution — S-4 work.
- Calibration consumer — Phase 9.

## Commit shape

Single impl commit on `sprint2-engineer-b`:

```
0ab7be9 S-3 prep (NON-merging): reason-code fan-out + typed event schemas
```

Per-ticket-ritual companion commits (memory.md update + this summary file) follow as separate documentation-only commits per the established repo pattern (B-1, B-3, B-5, B-6, G-2, S-1.7).

## Next ticket

Engineer A's S-2 (substrate writer + lineage helper) is the gating dependency. Once S-2 merges to `post-6b-restructured-roadmap`, this branch rebases and S-3 final wiring lands in a single commit per the punch list above.
