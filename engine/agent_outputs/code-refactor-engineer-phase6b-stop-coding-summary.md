# Phase 6B Stop-Coding-Line — Final Engine Freeze

**Status:** Applied. Full suite **922 passed / 14 skipped / 0 failed** (same count as post-C4). M0 goldens byte-identical. Beauty Brand pinned slate fixture intentionally re-pinned to absorb the `discount_hygiene` mechanism rewrite (Task 1) — the only authorized fixture refresh, executed once.

---

## 1. Approved Scope

Land the five Stop-Coding-Line items from `agent_outputs/phase6b-stop-coding-line-reconciled.md` as one bundled engine commit. Data-layer / schema fixes only. No renderer changes, no selector logic changes, no new causal priors, no new ML.

1. YAML content fixes — `discount_hygiene.mechanism`, `bestseller_amplify.mechanism`.
2. Display-name uniqueness — break the `retention_mastery` ↔ `at_risk_repeat_buyer_rescue` collision and assert uniqueness at registry-load time.
3. Raw typed numerics for opportunity-context and SoS deltas.
4. Considered reason-code enum equivalence + `held_reason_detail` struct.
5. Anomalous-window typed slot reservation (detector stubbed).

---

## 2. Task 0 — Field Verification

Verified before any code changes:

- `OpportunityContext` exists in `src/engine_run.py` with fields `audience_size: int`, `aov: float`, `addressable_value: float`, `aov_window: str`, `aov_source: str`. No pre-formatted dollar string fields anywhere in the dataclass; the renderer (`storytelling_v2._round_addressable_value`) is the only stringifier.
- `Observation` exists with `text: str`, `supporting_metric`, `change_magnitude`, `classification`. No `current` / `prior` / `delta_pct` fields existed before Task 2; the typed numerics were embedded in the freeform `text` string only (e.g. `"AOV (L28): $45 (6.6% vs prior)"`).
- `ReasonCode` enum exists with 13 values (the 11-code PM-Q3 set plus `CAP_EXCEEDED` and `TARGETING_HELD_UNDER_ABSTAIN`). Conceptual equivalents exist for every contract-final required code; no new codes invented.
- `RejectedPlay` did NOT have a `held_reason_detail` field before Task 3.
- No `anomaly_flags`, `n_days_observed`, `n_days_expected` fields existed on any schema before Task 4.
- `decide.py` already routes every reason assignment through `ReasonCode.X` (verified by full-file grep). No string-literal reason assignments remain to swap.

---

## 3. Patch Summary

### Task 1 — YAML mechanism rewrites + display_name uniqueness
- `config/priors.yaml::plays.discount_hygiene.metadata.mechanism`: rewrote to suppression posture — `"Suppress discount codes for 14 days; send a full-price, value-led reminder; no urgency framing."` (was a contradictory 10%-off-code instruction with a `"track redemption rate"` measurement-instruction tail).
- `config/priors.yaml::plays.bestseller_amplify.metadata.mechanism`: stripped trailing `"; track basket attach"` measurement-instruction clause.
- `src/play_registry.py::PLAYS["retention_mastery"].display_name`: renamed `"At-risk repeat-buyer rescue"` -> `"At-risk repeat-buyer rescue (legacy emitter)"` to break the collision with `at_risk_repeat_buyer_rescue` (which is the canonical post-rename ID per memory.md).
- `src/play_registry.py::_assert_display_name_uniqueness`: added module-import-time invariant. Lists colliding `play_id` values in the error message. Fires at registry load (not at render time).

### Task 2 — Raw typed components
- `src/engine_run.py::OpportunityContext`: added two optional float fields — `aov_used` and `monthly_revenue_estimate` — as the contract-final-named aliases of existing `aov` and `addressable_value`. Both populate via `from_dict` round-trip. No existing field removed (every test using positional/kwarg `OpportunityContext(audience_size=..., aov=..., addressable_value=...)` still works).
- `src/engine_run.py::Observation`: added optional `current`, `prior`, `delta_pct` (raw float ratios; `delta_pct` is `0.066`, never `"6.6%"`). Round-trip safe.
- `src/measurement_builder.py::_build_opportunity_context`: now also populates `aov_used` and `monthly_revenue_estimate` with the same numeric values — no recomputation, no formatting.
- `src/state_of_store.py::build_observations`: populates `current` / `prior` / `delta_pct` on the AOV, repeat-rate, orders, returning-customer-share, and net-sales observations from the existing `aligned[L28]` and `aligned[L28_prior]` snapshots. The freeform `text` field is unchanged (preserved for legacy renderer / test compatibility).

### Task 3 — Considered reason-codes
- `src/engine_run.py::ReasonCode` docstring: documented the equivalence mapping from contract-final canonical codes (`AUDIENCE_BELOW_FLOOR`, `EVIDENCE_BELOW_THRESHOLD`, `ROLE_CONFLICT`, `DUPLICATE_AUDIENCE`) to the existing enum members (`AUDIENCE_TOO_SMALL`, `NO_MEASURED_SIGNAL` / `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` / `MATERIALITY_BELOW_FLOOR`, `AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY` / `CANNIBALIZATION_DEMOTED`). No new enum values invented per the constraint.
- `src/engine_run.py::RejectedPlay`: added optional `held_reason_detail: Optional[Dict[str, Any]]` for structured numeric context (e.g. `{"observed": 312, "floor": 500}`). Round-trip safe.
- `src/decide.py`: no changes required. Audited end-to-end; every `RejectedPlay` instantiation already uses a typed `ReasonCode.X` value (no string literals remain). The `_PRELIM_REASON_MAP` short-code -> `ReasonCode` table is the single conversion seam.

### Task 4 — Anomalous-window typed slot
- `src/engine_run.py::Observation`: added `anomaly_flags: List[str]` (default `[]`), `n_days_observed: int` (default `0`), `n_days_expected: int` (default `0`). Detector is a stub (no producer populates non-default values today); the typed slot is reserved so the JSON contract is stable for downstream agents and Phase 6C can wire a detector without a schema change.

### Task 5 — Cross-task consistency
- Verified no pre-formatted dollar string is the only representation in any dataclass: `OpportunityContext` was already raw-typed; `Observation.text` is freeform but no longer the only representation now that `current`/`prior`/`delta_pct` are populated.
- Verified the uniqueness assertion fires correctly on a duplicate display_name (smoke-tested by constructing two PlayDefs with the same display_name; `ValueError` raised as expected).
- Verified `decide.py` imports `ReasonCode` and uses it everywhere; no string-literal reason assignments exist.
- Verified `anomaly_flags` defaults to `[]` and round-trips cleanly through `to_dict` / `from_dict`. Existing serialization paths unaffected.

---

## 4. Files Changed

| Path | Change |
|---|---|
| `config/priors.yaml` | `discount_hygiene.mechanism` rewritten; `bestseller_amplify.mechanism` measurement-tail stripped. |
| `src/play_registry.py` | `retention_mastery.display_name` disambiguated; `_assert_display_name_uniqueness` added and fires at module import. |
| `src/engine_run.py` | `OpportunityContext` += `aov_used`, `monthly_revenue_estimate`. `Observation` += `current`, `prior`, `delta_pct`, `anomaly_flags`, `n_days_observed`, `n_days_expected`. `RejectedPlay` += `held_reason_detail`. `ReasonCode` docstring documents equivalence mapping. `_from_dict_observation` / `_from_dict_rejected` / `_from_dict_opportunity_context` round-trip every new field. |
| `src/measurement_builder.py` | `_build_opportunity_context` now also populates `aov_used` and `monthly_revenue_estimate`. |
| `src/state_of_store.py` | `build_observations` now populates `current` / `prior` / `delta_pct` on all 5 metric observations from the `aligned[L28]` and `aligned[L28_prior]` snapshots. |
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | Re-pinned (intentional, single-task fixture refresh) to absorb the `discount_hygiene.mechanism` rewrite. New sha256 below. M0 goldens NOT touched. |

No changes to: `src/storytelling.py` (legacy), `src/storytelling_v2.py` (renderer), `src/decide.py` (already enum-typed), `src/sizing.py`, `src/anomaly.py`, `tests/golden/`, any selector logic.

---

## 5. Tests / Checks Run

| Lane | Result |
|---|---|
| `tests/test_slate_regression_beauty_brand.py` | 19 passed (after fixture refresh) |
| `tests/test_golden_diff.py` (M0) | 3 passed, byte-identical |
| `tests/` (full suite) | **922 passed / 14 skipped / 0 failed** (170s) |

Suite count delta: post-C4 = 922p/14s/0f -> Stop-Coding-Line = 922p/14s/0f (no test count change). No new tests added (per the Stop-Coding scope: schema-only typed-contract additions, not new logic).

### Beauty Brand pinned fixture sha256

```
prior:    dcb45ceefe5f4dd44cc05e4e539df75402cf7fe80abf4a4757ce69b8f2e0f3bb (post-C4)
new:      ed02ddc2bc33564e2b1647dc725d69bc70e69cde4dd878e3358fad87d97e7914 (post-Stop-Coding)
```

The fixture drift is exclusively the `What we'd send` mechanism line for `discount_hygiene` — the rewrite from "Email a 10% off code to discount-prone buyers; track redemption rate." to "Suppress discount codes for 14 days; send a full-price, value-led reminder; no urgency framing." This is the explicit goal of Task 1 founder-issue #1. Re-pinning is the documented refresh path; the test's own assertion message points at it.

### M0 goldens

```
tests/test_golden_diff.py::test_golden_matches[small_sm]        PASSED
tests/test_golden_diff.py::test_golden_matches[mid_shopify]     PASSED
tests/test_golden_diff.py::test_golden_matches[micro_coldstart] PASSED
```

Byte-identical. The Stop-Coding-Line changes are gated behind the V2 stack (`ENGINE_V2_DECIDE` + `ENGINE_V2_OUTPUT` + `ENGINE_V2_SLATE`); the legacy CSV -> HTML pipeline is unchanged.

---

## 6. Behavior Changes

**Default-flag path (M0 / `ENGINE_V2_OUTPUT=false`):** No change. Legacy renderer untouched. M0 goldens byte-identical.

**Full V2 stack:**
- `engine_run.json` now emits **two new opportunity-context fields**: `aov_used` (= `aov`) and `monthly_revenue_estimate` (= `addressable_value`). Both numeric. Existing fields unchanged.
- `engine_run.json` `state_of_store[]` Observations now carry **`current`**, **`prior`**, **`delta_pct`** as raw floats alongside the freeform `text` string. Renderers / agents may read either; `delta_pct` is a ratio (0.066), never a percent string.
- `engine_run.json` `state_of_store[]` Observations now carry **`anomaly_flags: []`**, **`n_days_observed: 0`**, **`n_days_expected: 0`** as reserved typed slots. Detector is stubbed; defaults are safe.
- `engine_run.json` `considered[]` RejectedPlays now carry an optional **`held_reason_detail`** dict (default `null`). No producer populates it today; the typed slot is reserved for downstream agents to read alongside the existing `reason_code` enum.
- The `discount_hygiene` "What we'd send" mechanism line on rendered Recommended Now / Recommended Experiment cards now reads as a suppression posture, matching the play title. The `bestseller_amplify` mechanism no longer trails into a measurement instruction.
- `retention_mastery` is now disambiguated from `at_risk_repeat_buyer_rescue` in any merchant-facing surface that reads `display_name`.

The selector logic, gates, sizing math, and HTML structure are unchanged.

---

## 7. Artifacts Added

- `agent_outputs/code-refactor-engineer-phase6b-stop-coding-summary.md` (this file).

No new modules, no new tests, no new YAML keys, no new dataclasses.

---

## 8. Remaining Risks

- **Equivalence mapping is a docstring, not an alias.** The contract-final canonical names (`AUDIENCE_BELOW_FLOOR`, `EVIDENCE_BELOW_THRESHOLD`, `ROLE_CONFLICT`, `DUPLICATE_AUDIENCE`) are NOT enum members — they are documented equivalences. Downstream agents that hard-code the canonical names will need a thin translation layer (or the docstring becomes the authoritative mapping). The constraint forbade inventing new codes; this is the conservative trade-off.
- **`held_reason_detail` is reserved but unpopulated.** No `RejectedPlay` producer in `decide.py` populates the field today. Agents can rely on the typed slot existing in `engine_run.json` (it serializes as `null`); a follow-up ticket should wire the existing M5 / abstain-rerouting code paths to populate `{"observed": N, "floor": F}` style payloads.
- **`anomaly_flags` defaults are static.** The detector is a Phase 6C concern. Until then, every Observation reports `anomaly_flags=[]`, `n_days_observed=0`, `n_days_expected=0`. Agents must read these as "unknown / not detected", not "verified clean window".
- **`current`/`prior` derive from `aligned[L28_prior]`.** When the upstream KPI snapshot does not surface a prior block (older fixtures, certain cold-start paths), these fields fall through to `None` while `delta_pct` may still be populated from `aligned[L28].delta`. This is consistent with the prior-omission policy elsewhere in the codebase but is a soft inconsistency to track.
- **The Beauty Brand fixture refresh consumed the only authorized re-pin in this commit.** Future YAML-content changes that bleed into the rendered slate will trigger a new drift; PMs should treat the mechanism strings as part of the merchant-facing contract.

---

## 9. Follow-up Work

- **Phase 6C:** wire the anomaly detector to populate `Observation.anomaly_flags` from real window-gap / spike heuristics; backfill `n_days_observed` / `n_days_expected` from the KPI snapshot.
- **Phase 6C:** wire `RejectedPlay.held_reason_detail` payloads at every M5 guardrail and the M7 abstain-rerouting seam in `decide.py`. The struct is reserved; producers are not.
- **Agent-swarm milestone:** consume `OpportunityContext.monthly_revenue_estimate` and `Observation.delta_pct` directly. Stop reading `addressable_value` and the `text` freeform string.
- **Optional cleanup:** once all downstream consumers migrate to `aov_used` / `monthly_revenue_estimate`, deprecate the duplicate `aov` / `addressable_value` fields. Out of scope for this commit (would break existing tests).
