# Code Refactor Engineer — Synthetic Blocker Fix 4 Summary

_Date: 2026-05-04_
_Scope: Fix 4 ONLY from `agent_outputs/implementation-manager-synthetic-blocker-fix-plan.md`._

## Approved Scope

Inventory-block visibility in V2 Considered.

When a SKU-pushing play is held by inventory, V2 must surface that as
a Considered card with `reason_code = ReasonCode.INVENTORY_BLOCKED`
and merchant-readable copy. The wiring path (per the IM plan):

- M3 `detect_candidates` stamps the candidate with
  `preliminary_rejection_reason="inventory_blocked"` when its backing
  SKUs are below the cover-days threshold.
- `populate_considered_from_candidates` maps the stamp to
  `ReasonCode.INVENTORY_BLOCKED` via `_PRELIM_REASON_MAP`.
- The rendered Considered card shows merchant-readable text without
  exposing raw cover-days / units numbers.

Strict Non-Goals (not touched in this pass):

- Fix 5 (materiality footer).
- Materiality floors.
- Vertical-specific inventory thresholds.
- Multi-SKU aggregation logic.
- Numeric stock / cover-days on merchant cards.
- Legacy renderer.
- Re-baselining goldens.
- Lifecycle memory or M10 cleanup.
- Bestseller_amplify audience-builder rework.

## Patch Summary

The plumbing this fix lands:

1. **Reason map** (`src/decide.py`): added
   `"inventory_blocked": ReasonCode.INVENTORY_BLOCKED` to
   `_PRELIM_REASON_MAP`. Without this entry the M3 stamp would
   silently fall through to the `NO_MEASURED_SIGNAL` default and the
   inventory hold would be invisible on the Considered card.

2. **Merchant-readable reason text** (`src/decide.py`): updated
   `_CONSIDERED_REASON_TEXT[ReasonCode.INVENTORY_BLOCKED]` to PM's
   verbatim copy: `"Hero SKU at low stock; held until restock."`
   No raw inventory units / cover_days exposure on the merchant
   card; internal receipts retain numeric detail.

3. **Would-fire-if template** (`src/decide.py`): updated
   `_WOULD_FIRE_IF_TEMPLATE[ReasonCode.INVENTORY_BLOCKED]` to PM's
   verbatim copy: `"Would fire when stock on the hero SKU recovers
   above the cover-days threshold."`

4. **M3 stamping** (`src/detect.py`): added optional
   `inventory_metrics` keyword argument to `detect_candidates`. When
   provided AND the minimum `cover_days` across SKUs is below the
   threshold (default 21, overridable via
   `cfg["INVENTORY_MIN_COVER_DAYS"]["default"]`), SKU-pushing plays
   with non-zero audience are stamped with
   `preliminary_rejection_reason="inventory_blocked"`. The stamping
   is conservative:
   - Only fires when inventory data is present (None is a no-op,
     mirroring `gate_inventory`'s "no inventory data => no-op" rule).
   - Only fires for plays in the SKU-pushing set
     (`bestseller_amplify`, `routine_builder`, `category_expansion`,
     `overstock_demand_push`).
   - Only fires when the candidate has a non-zero audience (so the
     audience-zero / data-missing reason still wins when applicable).
   - Never overwrites an upstream rejection reason (preserves
     `audience_too_small`, `data_missing`, `audience_zero`).
   - Cover-days threshold and SKU-push set are mirrored as small
     local helpers (`_min_cover_days_from_metrics`,
     `_resolve_inventory_threshold`, `_SKU_PUSH_PLAYS`) rather than
     imported from `src.guardrails`. This keeps M3 import-light per
     the M3 contract (M3 is shadow-only and must not pull in M5 at
     import time). Threshold and SKU set are kept consistent with
     `src.guardrails.DEFAULT_MIN_COVER_DAYS` and
     `src.guardrails.SKU_PUSH_PLAYS`.

5. **Main.py wiring** (`src/main.py`): passed `inventory_metrics`
   into `detect_candidates` at both call sites — the V2 decide path
   (line ~731) and the shadow receipts path (line ~850). Without
   this the optional kwarg is unused at runtime.

`ReasonCode.INVENTORY_BLOCKED` already existed in
`src/engine_run.py`. No enum changes were required (verified per the
brief).

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` — added
  `inventory_blocked` to `_PRELIM_REASON_MAP`; updated
  `_CONSIDERED_REASON_TEXT[INVENTORY_BLOCKED]` to PM's verbatim copy;
  updated `_WOULD_FIRE_IF_TEMPLATE[INVENTORY_BLOCKED]` to PM's
  verbatim copy.
- `/Users/atul.jena/Projects/Personal/beaconai/src/detect.py` — added
  optional `inventory_metrics` kwarg to `detect_candidates`; added
  three small private helpers (`_min_cover_days_from_metrics`,
  `_resolve_inventory_threshold`, `_SKU_PUSH_PLAYS`).
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` —
  threaded `inventory_metrics` through both `detect_candidates` call
  sites.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_inventory_blocked_in_considered.py`
  — NEW. 12 tests landed BEFORE the fix per TDD. 10 fail pre-fix,
  2 pass pre-fix (negative controls / pre-existing schema).

No other files touched. Specifically NOT modified:
`engine_run_adapter.py`, `measurement_builder.py`, `evidence.py`,
`guardrails.py`, `storytelling_v2.py` (V2 renderer), `storytelling.py`
(legacy renderer), the M3 Candidate schema, the bestseller_amplify
audience builder, or the M0 goldens.

## Exact Commands Run

```
# TDD: land tests first, watch them fail.
python -m pytest tests/test_inventory_blocked_in_considered.py -v
# pre-fix: 10 failed, 2 passed

# Apply patches to src/decide.py and src/detect.py.

python -m pytest tests/test_inventory_blocked_in_considered.py -v
# post-fix: 12 passed

# Wire src/main.py call sites.
# Re-run targeted suites to verify no regression in M5 or related
# considered-list tests.
python -m pytest \
  tests/test_inventory_gate.py \
  tests/test_detect_candidates.py \
  tests/test_phase5_considered_always.py \
  tests/test_engine_v2_shadow.py \
  tests/test_guardrails.py \
  tests/test_decide.py \
  tests/test_engine_run_schema.py -v
# 127 passed

# Golden diff + forbidden-string suite.
python -m pytest \
  tests/test_golden_diff.py \
  tests/test_targeting_no_dollar_headline.py \
  tests/test_internal_stats_not_rendered.py \
  tests/test_phase5_no_aura_beacon.py -v
# 20 passed

# Full suite.
python -m pytest tests/ -q
# 612 passed, 12 skipped

# E2E smoke runs.
mkdir -p /tmp/fix4_low_inv_smoke /tmp/fix4_healthy_smoke

ENGINE_V2_DECIDE=true ENGINE_V2_OUTPUT=true ENGINE_V2_SHADOW=true \
  ENGINE_V2_SIZING=true STATS_NAN_FOR_HARDCODED=true \
  EVIDENCE_CLASS_ENFORCED=true ANOMALY_GATE_ENABLED=true \
  GUARDRAIL_INVENTORY_ENABLED=true GUARDRAIL_OVERLAP_ENABLED=true \
  GUARDRAIL_MATERIALITY_ENABLED=true VERTICAL_MODE=beauty \
  INVENTORY_GATE_ENABLED=true python -m src.main \
  --orders tests/fixtures/synthetic/healthy_beauty_low_inventory_240d_orders.csv \
  --inventory tests/fixtures/synthetic/healthy_beauty_low_inventory_240d_inventory.csv \
  --brand low_inv --out /tmp/fix4_low_inv_smoke

ENGINE_V2_DECIDE=true ENGINE_V2_OUTPUT=true ENGINE_V2_SHADOW=true \
  python -m src.main --orders data/SM_orders.csv \
  --brand healthy_smoke --out /tmp/fix4_healthy_smoke
```

## Tests / Checks Run

| Check | Result |
|---|---|
| `tests/test_inventory_blocked_in_considered.py` (new) — pre-fix | **10 FAILED** (as designed), 2 passed |
| `tests/test_inventory_blocked_in_considered.py` (new) — post-fix | **12 passed** |
| `tests/test_inventory_gate.py` (M5 inventory gate, existing) | 11 passed |
| `tests/test_detect_candidates.py` (M3 detect contract) | passed |
| `tests/test_phase5_considered_always.py` | 10 passed |
| `tests/test_engine_v2_shadow.py` | passed |
| `tests/test_guardrails.py` | 61 passed |
| `tests/test_decide.py` | passed |
| `tests/test_engine_run_schema.py` | passed |
| `tests/test_golden_diff.py` | 3 passed (no goldens re-baselined) |
| `tests/test_targeting_no_dollar_headline.py` | 6 passed |
| `tests/test_internal_stats_not_rendered.py` | passed (debug.html still surfaces `inventory_blocked` reason code) |
| `tests/test_phase5_no_aura_beacon.py` | 4 passed (forbidden-token sweep clean) |
| Full suite `pytest tests/ -q` | **612 passed, 12 skipped, 0 failed** |
| E2E smoke run on `data/SM_orders.csv` (no inventory CSV) | 0 false-positive `inventory_blocked` stamps in `v2_candidates.json` |
| E2E smoke run on `healthy_beauty_low_inventory_240d` fixture | Briefing produced; bestseller_amplify is a base candidate (audience_size=1357) but inventory_metrics is None at engine time due to the Fix 11 runner-clock issue (228d stale). Fix 4 plumbing is correct; e2e validation on this fixture awaits Fix 11. |

Pre-Fix-4 baseline was 600 passed + 12 skipped (post-Fix-3). Post-fix
is **612 passed + 12 skipped** — exactly the +12 new tests this PR
added, with no previously-passing test moving and no skip count delta.

## Did The New Tests FAIL Before The Fix?

Yes. Pre-fix run summary on the new test file:

```
FAILED tests/test_inventory_blocked_in_considered.py::test_prelim_reason_map_contains_inventory_blocked
FAILED tests/test_inventory_blocked_in_considered.py::test_considered_reason_text_for_inventory_blocked_is_merchant_readable
FAILED tests/test_inventory_blocked_in_considered.py::test_would_fire_if_for_inventory_blocked_is_populated
FAILED tests/test_inventory_blocked_in_considered.py::test_inventory_blocked_candidate_lands_in_considered_with_typed_reason
FAILED tests/test_inventory_blocked_in_considered.py::test_inventory_blocked_considered_card_has_merchant_readable_reason_text
FAILED tests/test_inventory_blocked_in_considered.py::test_detect_candidates_stamps_inventory_blocked_when_cover_below_threshold
FAILED tests/test_inventory_blocked_in_considered.py::test_detect_candidates_does_not_stamp_inventory_blocked_when_cover_healthy
FAILED tests/test_inventory_blocked_in_considered.py::test_detect_candidates_does_not_stamp_inventory_blocked_on_non_sku_push_plays
FAILED tests/test_inventory_blocked_in_considered.py::test_detect_candidates_no_inventory_metrics_is_no_op_for_inventory_stamping
FAILED tests/test_inventory_blocked_in_considered.py::test_e2e_detect_then_populate_surfaces_inventory_blocked_in_considered
================ 10 failed, 2 passed in 0.43s ================
```

Specific load-bearing pre-fix failures and what they would have
caught:

1. `test_prelim_reason_map_contains_inventory_blocked` — pinned
   that the `_PRELIM_REASON_MAP` learns the new short code. Without
   this, M3 stamps would silently map to `NO_MEASURED_SIGNAL`.
2. `test_considered_reason_text_for_inventory_blocked_is_merchant_readable` —
   pinned PM's verbatim copy and the no-raw-numbers contract on the
   merchant card.
3. `test_would_fire_if_for_inventory_blocked_is_populated` — pinned
   that the would-fire-if template references restock / stock /
   recovery in plain English with no raw numbers. (The pre-fix copy
   used the phrase "days-of-cover" which the assertion accepted as
   merchant-readable; the pre-fix copy did NOT pass the no-digits
   assertion because the new copy explicitly omits cover-day numbers.
   The negative-digit assertion caught the regression.)
4. `test_inventory_blocked_candidate_lands_in_considered_with_typed_reason`
   — pinned that a candidate stamped `"inventory_blocked"` lands in
   considered with `ReasonCode.INVENTORY_BLOCKED` rather than the
   default `NO_MEASURED_SIGNAL`.
5. `test_detect_candidates_stamps_inventory_blocked_when_cover_below_threshold`
   — pinned that `detect_candidates` accepts the optional
   `inventory_metrics` kwarg and stamps SKU-pushing plays with
   non-zero audience when cover_days < threshold. Pre-fix this
   raised `TypeError: detect_candidates() got an unexpected keyword
   argument 'inventory_metrics'`.
6. `test_detect_candidates_does_not_stamp_inventory_blocked_when_cover_healthy`,
   `test_detect_candidates_does_not_stamp_inventory_blocked_on_non_sku_push_plays`,
   `test_detect_candidates_no_inventory_metrics_is_no_op_for_inventory_stamping`
   — negative controls; all three failed pre-fix on the same
   TypeError because the kwarg did not exist.
7. `test_e2e_detect_then_populate_surfaces_inventory_blocked_in_considered`
   — end-to-end M3 → populate → Considered with merchant-readable
   reason text. Failed pre-fix on the same TypeError.

The 2 tests that passed pre-fix were:
- `test_reason_code_inventory_blocked_exists` —
  `ReasonCode.INVENTORY_BLOCKED` already existed (M5 / Fix 3).
- `test_inventory_blocked_considered_card_has_would_fire_if_populated`
  — vacuously passed because the candidate fell through to
  `NO_MEASURED_SIGNAL`'s would-fire-if template, which still starts
  with "Would fire". This is the safety net the structural
  `test_inventory_blocked_candidate_lands_in_considered_with_typed_reason`
  test catches: pre-fix, the candidate would surface, but with the
  wrong reason code.

## How `inventory_blocked` Is Stamped (Call Site) And Mapped (Function)

**Stamping call site:** `src/detect.py::detect_candidates`. The
function builds each candidate from the audience builder result, then
applies the inventory check:

```python
prelim_reason = res.preliminary_rejection_reason

if (
    inventory_blocked
    and prelim_reason is None
    and play_id in _SKU_PUSH_PLAYS
    and int(res.audience_size or 0) > 0
):
    prelim_reason = "inventory_blocked"
```

`inventory_blocked` is pre-computed once per call from the
`inventory_metrics` DataFrame's minimum `cover_days` value, compared
against the threshold (default 21) resolved from `cfg`. The check
is bypassed when `inventory_metrics is None`, when the play is not
in `_SKU_PUSH_PLAYS`, when the audience builder already produced a
more specific rejection reason, or when audience size is 0.

**Mapping function:** `src/decide.py::_candidate_reason_code`, which
reads `candidate.preliminary_rejection_reason` and looks it up in
`_PRELIM_REASON_MAP`. With the new entry
`"inventory_blocked": ReasonCode.INVENTORY_BLOCKED`, the candidate
lands in `populate_considered_from_candidates`'s output as a
`RejectedPlay` with:
- `reason_code = ReasonCode.INVENTORY_BLOCKED`
- `reason_text = "Hero SKU at low stock; held until restock."`
- `would_fire_if = "Would fire when stock on the hero SKU recovers
  above the cover-days threshold."`
- `evidence_snapshot = "Audience: <N> people | <segment definition>"`

**Wiring through main.py:** The V2 decide path
(`if cfg.get("ENGINE_V2_DECIDE")` block, ~line 720) and the shadow
receipts path (`if ENGINE_V2_SHADOW` block, ~line 840) both pass
`inventory_metrics=inventory_metrics` into `detect_candidates`.
`inventory_metrics` is computed once at line 345 from the inventory
CSV (when provided) and is `None` otherwise — a clean no-op.

## bestseller_amplify Surface — Surfaced, Not Deferred

The IM plan flagged a possible rathole: bestseller_amplify might
not surface as a base candidate on the low-inventory fixture and
might require audience-builder rework. The smoke run on
`healthy_beauty_low_inventory_240d` shows:

```
v2_candidates.json:
  bestseller_amplify => preliminary_rejection_reason=None,
                         audience_size=1357
```

bestseller_amplify IS produced as a base candidate with a
non-trivial audience. No audience-builder rework was required.
The Fix 4 plumbing alone is sufficient for the M3 stamp to fire
once inventory_metrics actually reaches the engine (gated by
Fix 11).

## E2E Low-Inventory Validation — Awaits Fix 11

The brief explicitly says:

> If e2e validation depends on Fix 11 runner-clock alignment, do
> not force it in Fix 4; document that full fixture validation
> awaits Fix 11.

E2E validation on `healthy_beauty_low_inventory_240d` was attempted.
The result:

- bestseller_amplify is a base candidate with audience_size=1357.
- `inventory_metrics` returns `None` at engine time because
  `compute_inventory_metrics` raises `TypeError: Cannot subtract
  tz-naive and tz-aware datetime-like objects` on this fixture's
  CSV — a side effect of the 228-day staleness gap between the
  inventory CSV (dated 2025-09-15..09-18) and the runner clock.
- With `inventory_metrics=None`, the M3 stamp is correctly a no-op.
- Therefore `briefing.html` does not yet show an
  `inventory_blocked` Considered card on this fixture.
- The unit + integration tests in
  `tests/test_inventory_blocked_in_considered.py` exercise the
  stamping wire end-to-end with synthetic `pd.DataFrame`
  inventory_metrics and confirm the Considered card surfaces with
  the correct reason code, reason text, and would_fire_if. The
  V2 plumbing is structurally correct.

Fix 11 (runner-clock alignment) will resolve the upstream pandas
error and give Fix 4 a runnable e2e fixture. No engine-side change
is needed in this PR.

## Goldens Passed

`tests/test_golden_diff.py`: 3 fixtures (`small_sm`, `mid_shopify`,
`micro_coldstart`) all pass byte-for-byte against the pinned golden
tree. No file under `tests/golden/` was modified. No `--baseline` /
`--regenerate` invocation was used.

The legacy renderer is the canonical path for the goldens and none
of the changed files (`src/decide.py` reason-text + map entries,
`src/detect.py` optional kwarg + helpers, `src/main.py` kwarg
plumbing) affect the legacy `actions_log` / `briefing.html` path.
The legacy renderer (`src/storytelling.py`) is untouched.

## Behavior Changes

- `detect_candidates(g, aligned, cfg, registry, *, inventory_metrics=...)`
  now accepts an optional `inventory_metrics` keyword argument.
  When omitted (default), behavior is identical to pre-Fix-4.
- When `inventory_metrics` is provided AND the minimum cover_days
  across SKUs is below the threshold AND a SKU-pushing play has a
  non-zero audience AND no upstream rejection reason: the candidate
  is stamped with `preliminary_rejection_reason="inventory_blocked"`.
- `populate_considered_from_candidates` now translates that stamp
  into a `RejectedPlay` with `reason_code = ReasonCode.INVENTORY_BLOCKED`,
  `reason_text = "Hero SKU at low stock; held until restock."`, and
  `would_fire_if = "Would fire when stock on the hero SKU recovers
  above the cover-days threshold."`.
- The rendered V2 briefing's Considered section will now include
  the inventory-blocked card on fixtures where inventory data is
  available and any backing SKU is below cover-days. Merchant card
  text references stock / restock in plain English; raw cover-day
  numbers are NOT surfaced on the merchant card.
- `engine_run.json::considered[]` carries the typed
  `INVENTORY_BLOCKED` reason code.
- M5 `gate_inventory` behavior: unchanged. The pre-existing
  PlayCard-side gate continues to fire on PlayCards in
  `engine_run.recommendations[]` (for the legacy adapter path).
  The two paths are complementary, not redundant: M3 stamps M3
  candidates (V2 considered list source), M5 gates M5 PlayCards
  (V2 recommendations gate).
- Default flags-off path on the M0 goldens: byte-identical.
- Materiality floor, sizing, evidence classes, NaN gate, M3
  Candidate schema, M5/M6 V2 blocks, ABSTAIN_SOFT contract (Fix 3),
  targeting-measurement invariant (Fix 2), legacy renderer: all
  unchanged.
- ReasonCode enum: unchanged (INVENTORY_BLOCKED already existed).

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_inventory_blocked_in_considered.py`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-synthetic-fix-4-summary.md`
  (this file)

## Remaining Risks

- **E2E validation gated on Fix 11.** The
  `healthy_beauty_low_inventory_240d` fixture's CSV cannot be read
  cleanly today (228d stale, tz-aware/naive datetime mix). The
  unit and integration tests exercise the M3 → Considered wire
  with synthetic inventory_metrics and pin the contract. Once
  Fix 11 lands, no engine-side change is needed; the e2e
  briefing.html will show the inventory_blocked card automatically.
- **Threshold and SKU-push set duplicated as M3 helpers.** The
  helpers `_min_cover_days_from_metrics`, `_resolve_inventory_threshold`,
  and `_SKU_PUSH_PLAYS` in `src/detect.py` mirror the M5 source
  of truth in `src/guardrails.py`. They are intentionally duplicated
  to keep the M3 module import-light per the M3 contract (M3 must
  not pull in M5 at import time). If M5's threshold or SKU set
  changes, M3's mirror needs to be updated. The duplication is
  a small, well-defined surface; a future refactor could move
  the constants to a shared `src/contracts.py`-like module without
  affecting Fix 4 semantics.
- **Stamp ordering rule.** M3 will not overwrite an upstream
  rejection reason. If the bestseller_amplify audience builder
  ever produces an `audience_too_small` reason on a low-inventory
  fixture, the M3 stamp does not fire and the Considered card
  surfaces as `AUDIENCE_TOO_SMALL`. This is the intended ordering
  (audience presence before inventory check). It mirrors the M5
  gate's "no inventory data => no-op" logic and the audience
  builder's "data_missing" / "audience_too_small" semantics.
- **No multi-SKU aggregation.** The stamp fires when ANY backing
  SKU is below the threshold (the min cover_days across all SKUs
  is the trigger). This matches `gate_inventory`'s behavior on
  the M5 side. A merchant with one low-cover SKU and 9 healthy
  SKUs will still see bestseller_amplify held — correctly,
  because the play pushes to that one SKU's buyers. Multi-SKU
  aggregation logic is explicitly out of scope per the brief.
- **Merchant card does not name the SKU.** PM's verbatim copy
  reads "Hero SKU at low stock" generically, not "Vitamin C
  Brightening Serum at low stock". Naming the SKU is a Phase 6
  copy-improvement chore; this fix is wire-only.

## Readiness Assessment For Fix 5

Ready. Specifically:

- Full suite (612 passed, 12 skipped) is clean, so Fix 5's
  `tests/test_materiality_footer_present.py` can land against a
  known-green baseline.
- No goldens were re-baselined.
- The reason-code taxonomy is now wired end-to-end for
  inventory_blocked. Fix 5 is a separate concern (materiality
  footer regression, suspected to be a stamping or renderer
  conditional issue).
- No code-level discovery from Fix 4 changes the planned shape of
  Fix 5.

## Git Status

Per the brief, changes are NOT committed. Files left unstaged so
the user can review the diff before committing. Current state at
the close of Fix 4:

- 1 new test file from Fix 4: `tests/test_inventory_blocked_in_considered.py`.
- 1 new doc file from Fix 4: this summary.
- 3 source files modified by Fix 4: `src/decide.py` (additive map +
  text + would-fire-if entries), `src/detect.py` (optional kwarg +
  small helpers), `src/main.py` (kwarg plumbing at two call sites).

`memory.md`, `tests/test_decide.py`, `tests/test_engine_run_schema.py`,
`tests/test_render_v2.py`, `tests/test_abstain_soft_no_recommendations.py`,
`agent_outputs/code-refactor-engineer-synthetic-fix-3-summary.md`,
`src/engine_run.py`, and `src/storytelling_v2.py` are still
unstaged from Fix 3 (per Fix 3's brief, those were also left
unstaged). Fix 4 does not touch any of those files.
