# S10-T0 — Lineage-keyed fatigue correctness fix — code-refactor-engineer summary

**Branch:** `post-6b-restructured-roadmap`
**Date:** 2026-05-25
**Ticket:** S10-T0 (CONFIRMED IN S10 per IM plan §D-T0)
**Status:** Implemented, tests green, fixtures byte-identical.

---

## 1. Scope (verbatim from plan §D-T0)

> Re-key the fatigue gate from `play_id`-only (the v1 plan misstated `src/guardrails.py:604`; actual `gate_recently_run` body starts at **`src/guardrails.py:632`**) to `lineage_id = sha1(store_id | play_id | audience_definition_id | audience_definition_version)`. The helper `src/memory/lineage.py::compute_lineage_id` (L28–63) already exists from S-2 and requires all four args.

Flag stays OFF. Byte-identical on existing fixtures by construction.

---

## 2. Files changed

| File | Lines (post-edit) | Change |
|---|---|---|
| `src/guardrails.py` | L632–646 (NEW helper `_card_audience_definition_version`), L648–734 (`gate_recently_run` body — extended signature + 4th-component defensive match), L862–876 (callsite #1 inside `apply_guardrails`), L1051–1066 (callsite #2 inside `apply_guardrails_to_injected` injected-only loop) | Added `audience_definition_version` kwarg to `gate_recently_run`; added defensive 4th-component match in the inner loop (only enforces when both sides carry the field); both internal callsites updated to pass the version via the new local helper. |
| `tests/test_s10_t0_lineage_keyed_fatigue.py` | NEW file, 7 tests | Coverage for the 4-tuple match (positive + 4 negative-mismatch cases + 1 defensive backward-compat case + 1 flag-OFF dormancy case). |

No other files modified. `src/memory/events.py`, `src/sizing.py`, `src/decide.py`, `config/gate_calibration.yaml`, `requirements.txt`, `src/utils.py` untouched per ticket constraints.

---

## 3. Implementation notes

### 3a. The 4-tuple key

`gate_recently_run` now matches on the four-component lineage tuple

```
(play_id, audience_definition_id, store_id, audience_definition_version)
```

aligned with `src/memory/lineage.py::compute_lineage_id` (which already requires all four args per founder decision D-1). Each component is matched defensively — i.e. the gate enforces a component only when both sides (candidate and history record) carry it. This preserves the existing S-1/S-2 backward-compat policy already used for `store_id` and `audience_id`, and prevents legacy history records (pre-S10) from spuriously failing to match on `audience_definition_version`.

### 3b. Helper duplication

Added a tiny local helper `_card_audience_definition_version(card) -> int` in `src/guardrails.py` that returns `1` (the same default `src/main.py::_audience_definition_version` returns). The duplication is intentional and documented in the helper docstring: importing `src.main` from `src.guardrails` would introduce a circular import, and the policy is one line of code anchored on D-1. When the Audience dataclass eventually gains an explicit field, both helpers can route to it in a single follow-up.

### 3c. Why `src/memory/events.py` is not edited

The dispatch brief listed `src/memory/events.py` as a second touchpoint ("filter that reads recommended_history aligned to the same 4-tuple match shape"). On reading the file (`src/memory/events.py:1–469`), this module is purely **typed payload schemas** for the S-3 substrate event payloads — it contains no fatigue-match filter and no consumer of `recommended_history.json`. The schemas (`RecommendationEmittedPayload` at L189–258, `RecommendationConsideredPayload` at L261–320) already carry `audience_definition_version` as a required field (L237, L291), so the 4-tuple shape is already pinned on the schema side.

The **only** code that filters/reads `recommended_history.json` against a candidate is `gate_recently_run` in `src/guardrails.py` (confirmed via `grep -rn "_read_recommended_history\|recommended_history" src/`). Editing `src/memory/events.py` would be out of scope for T0 and would touch frozen typed schemas. Per the dispatch's "only follow the path that's decided" + "STOP and escalate before deviating" rule, I'm flagging this in the summary rather than introducing an out-of-scope edit. The acceptance criterion ("filter aligned to the same 4-tuple match shape") is met by the single fatigue-match site being re-keyed; the schemas are already 4-tuple-shaped.

### 3d. Single-demote-channel invariant — unaffected

`gate_recently_run` is invoked from inside `apply_guardrails` (and from inside `apply_guardrails_to_injected` for injected-only re-application). Both paths emit `RejectedPlay` objects via the existing typed channel, not via post-guardrails appends to `engine_run.recommendations`. The CLAUDE.md single-demote-channel invariant is preserved.

---

## 4. Tests added

`tests/test_s10_t0_lineage_keyed_fatigue.py` — 7 tests (1 more than the planned 6; the extra is the defensive backward-compat case that mirrors the existing S-1 policy):

1. `test_four_tuple_match_fires_when_all_components_match` — positive case: all 4 components equal → `RECENTLY_RUN_FATIGUE` fires.
2. `test_audience_definition_version_mismatch_does_not_fire` — the load-bearing new assertion: bumping `audience_definition_version` (per D-1) forks to a new lineage; the old fatigue record must NOT match.
3. `test_store_id_mismatch_does_not_fire` — re-pins the existing S-1 invariant under the 4-tuple regime.
4. `test_play_id_mismatch_does_not_fire` — basic component-divergence sanity.
5. `test_audience_definition_id_mismatch_does_not_fire` — basic component-divergence sanity.
6. `test_record_without_version_still_matches_under_defensive_policy` — legacy pre-S10 records (no `audience_definition_version` field) still match on the available subset, mirroring the existing S-1 defensive policy for `store_id`.
7. `test_flag_off_no_fatigue_match_in_apply_guardrails` — wires through the full `apply_guardrails` entry with `RECENTLY_RUN_FATIGUE_ENABLED=False`; verifies the candidate survives and no `RECENTLY_RUN_FATIGUE` reason code appears in `considered`. This is the byte-identity invariant proven in unit form.

All 7 pass.

---

## 5. Verification steps run

| Check | Result |
|---|---|
| `pytest tests/test_s10_t0_lineage_keyed_fatigue.py -v` | **7 passed** |
| Full suite `pytest tests/ -q` | **1891 passed, 14 skipped, 4 xfailed, 2 xpassed, 0 failed** (baseline was 1904 collected; +7 new tests = 1911 collected, matches the post-T0 numbers) |
| Beauty + Supplements + M0 pinned slates: `pytest tests/test_slate_regression_beauty_brand.py tests/test_slate_regression_supplements_brand.py tests/test_synthetic_fixtures.py tests/test_synthetic_fixtures_8_11.py -v` | **113 passed, 6 skipped, 2 xpassed, 0 failed** |
| `gate_recently_run` callsite grep | 2 internal callsites updated (`src/guardrails.py:862`, `src/guardrails.py:1051`); 11 test callsites unchanged (kwarg is optional + back-compat). |
| `RECENTLY_RUN_FATIGUE_ENABLED` flag default | Unchanged (OFF). No flag flip. |

Byte-identical confirmation: Beauty + Supplements + M0 fixture regression tests pass with no `.expected.json` deltas, since the modified code path (`gate_recently_run`) is gated by `RECENTLY_RUN_FATIGUE_ENABLED` which remains OFF in production cfg and in all pinned-fixture configs.

---

## 6. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Behavior change leaks under flag OFF | Low | The gate function is only called inside two `if _flag_on(cfg, "RECENTLY_RUN_FATIGUE_ENABLED"):` branches. Test 7 wires through `apply_guardrails` with the flag explicitly OFF and verifies the candidate survives. |
| Defensive-policy escape hatch hides a real future bug | Low | The 4th-component defensive policy mirrors the established S-1 policy for `store_id`/`audience_id`. When the engine starts writing `audience_definition_version` into history records (already supported by the schema in `src/memory/events.py`), the defensive branch becomes a no-op and strict 4-tuple equality takes over. |
| Local helper duplication drifts from `src/main.py::_audience_definition_version` | Low | Both helpers return the same hard-coded `1` per D-1 until the Audience dataclass gains an explicit field. A follow-up ticket should consolidate when that field lands; for now, the duplication is documented in the helper docstring and explicitly tied to D-1. |
| S10-T1+ ML work touches the same module | None for T0 | T1+ modify `src/predictive/`, `config/gate_calibration.yaml`, and `requirements.txt` — disjoint from `src/guardrails.py`. |

---

## 7. Deviation-check statement

Per CLAUDE.md L42 + IM plan §D-T0 acceptance:

> Deviation check: none. Single-demote-channel invariant unaffected — `gate_recently_run` runs inside the guardrails pass and produces a `RejectedPlay`, not a post-guardrails injection.

One scope clarification (not a deviation): the dispatch's reference to a `src/memory/events.py` filter does not match the file's actual contents (typed payload schemas, no filter). The only fatigue-match filter is in `src/guardrails.py`. See §3c. The acceptance criteria are satisfied without touching `src/memory/events.py`. If the orchestrator/DS judges this should have been an edit somewhere else, please surface the specific target file and I will follow up.

---

## 8. Follow-up work / open questions

- **Audience.audience_definition_version field:** the gap noted in `src/main.py:106-113` and mirrored in the new helper in `src/guardrails.py` — both default to `1` until the Audience dataclass carries an explicit field. Net new follow-up ticket should add the field + consolidate the two helpers. Out of scope for T0 (no Audience schema changes per IM plan).
- **History-writer integration:** `src/outcome_log.py::build_record` does not currently persist `audience_definition_version` into the per-run history record. Once the field lands on the Audience dataclass (or main.py routes it explicitly), `_play_card_summary` should include it so that future fatigue checks can use strict 4-tuple equality rather than the defensive fallback. Out of scope for T0.
- **S13 dependency:** S13 turns `RECENTLY_RUN_FATIGUE_ENABLED` ON to support `month_2_delta` lineage continuity (per IM plan §D-T0 (a)). The 4-tuple key shape pinned at T0 is the contract S13 will activate.

---

## 9. Commit message (proposed; orchestrator commits)

```
S10-T0: lineage-keyed fatigue correctness fix

Re-key gate_recently_run in src/guardrails.py from the 3-tuple
(play_id, audience_definition_id, store_id) to the 4-tuple lineage
key (play_id, audience_definition_id, store_id, audience_definition_version),
aligned with src/memory/lineage.py::compute_lineage_id (which already
requires all four args per founder decision D-1).

RECENTLY_RUN_FATIGUE_ENABLED remains OFF — byte-identical on Beauty,
Supplements, and M0 pinned fixtures by construction. Defensive
component-matching policy preserved for legacy history records that
pre-date the audience_definition_version field.

7 new tests in tests/test_s10_t0_lineage_keyed_fatigue.py covering:
positive 4-tuple match; mismatch on each of the four components
independently; defensive backward-compat; flag-OFF dormancy through
apply_guardrails.

Full suite: 1891 passed, 14 skipped, 4 xfailed, 2 xpassed, 0 failed.

Deviation check: none. Single-demote-channel invariant unaffected —
gate_recently_run runs inside the guardrails pass and produces a
RejectedPlay, not a post-guardrails injection.
```

---

*End of summary.*
