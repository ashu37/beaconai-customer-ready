# S5-T1 — KI-26 supplements `prior` populated + KI-3 store_id wired

**Owner:** code-refactor-engineer (Sprint 5, ticket S5-T1)
**Date:** 2026-05-11
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §11, ticket S5-T1
**Predecessor:** G-4 ([code-refactor-engineer-g4-summary.md](./code-refactor-engineer-g4-summary.md))
**Status:** Complete. Schema unchanged (`event_version=1` frozen). Full suite green.

---

## 1. Approved scope

Bundled bugfix per implementation plan §11 (Sprint 5 first ticket).
Two one-line correctness wirings shipped in a single impl commit for
sprint hygiene; neither requires the other.

- **KI-26** — Supplements state-of-store Observations populated
  `current` and `delta_pct` but left `prior: null` for every metric
  (AOV, repeat rate, orders, returning-customer share, net sales).
  The typed Observation slot was reserved by 6B C2/C3 but the read
  path skipped the write.
- **KI-3** — S-5 added an optional `store_id` kwarg to
  `calibration_stub.load_realization_factors` but `src/main.py`
  didn't pass it; the `v_calibration_state` substrate read path was
  unreachable in production.

## 2. Patch summary

### KI-26 — `src/state_of_store.py::build_observations`

Root cause: every metric's prior leg was read from
`aligned["L28_prior"][<metric>]` — a top-level key that
`utils.kpi_snapshot_with_deltas` has never produced. The actual
structure produced by that function is nested:
`aligned["L28"]["prior"][<metric>]` (alongside the L28 window's
`delta` / `p` / `q` / `sig` blocks).

Reproduction (pre-fix) on the supplements G-1 fixture:

```
aov               | current=44.40   prior=None   delta=-1.68%
repeat_rate       | current=0.41%   prior=None   delta=-6.61%
orders            | current=972     prior=None   delta=+7.05%
returning_share   | current=96.28%  prior=None   delta=+1.09%
net_sales         | current=$43157  prior=None   delta=+5.25%
```

Reproduction (post-fix) on the same fixture:

```
aov               | current=44.40   prior=45.16   delta=-1.68%
repeat_rate       | current=0.41%   prior=0.44%   delta=-6.61%
orders            | current=972     prior=908     delta=+7.05%
returning_share   | current=96.28%  prior=95.24%  delta=+1.09%
net_sales         | current=$43157  prior=$41003  delta=+5.25%
```

Fix shape: five one-line read-path changes in `build_observations`,
each followed by a single explanatory comment on the first instance.

**Diagnostic note for future supplements regressions:** the bug was
NOT supplements-specific. It had been silent on BOTH Beauty and
supplements since M1 because (a) no test pinned the typed
`Observation.prior` slot and (b) the HTML renderer
(`src/storytelling_v2.py::render_state_of_store`) never read
`Observation.prior` directly — it composes the lead sentence from
`Observation.text`, which already carries the human-readable
"$X (Y% vs prior)" form. So the gap was invisible until G-1 surfaced
it on the supplements receipt JSON dump (no Recommended Now card
masked the observation block's missing prior leg). The fix populates
the reserved 6B C2/C3 typed slot for both verticals consistently —
zero HTML byte delta on either pinned briefing fixture.

### KI-3 — `src/main.py::run`

One-line wiring inserted immediately after `resolve_store_id` /
`ensure_store_dir` / `migrate_legacy_recommended_history` (the
B-4/S-1 surface that owns store_id resolution and the per-merchant
data directory):

```python
from .calibration_stub import load_realization_factors as _load_calib
_calibration_overrides = _load_calib(store_id=store_id)
```

Wrapped in a defensive `try/except` per the stub's "never raises"
contract. The same `store_id` value used by `_emit_substrate_events`
later in the function flows into the calibration loader, preserving
read/write symmetry once Phase 9 lights up the consumer.

With zero `calibration_updated` events present today (no live writer
ships before Phase 9), the projection is the canonical empty-shape
dict and engine behavior is byte-identical to today. This is
**dormant-but-correct wiring** per the ticket scope.

## 3. Files changed

| File | Change |
|---|---|
| `src/state_of_store.py` | 5 read-path edits + 1 explanatory comment block on first instance (KI-26 fix path) |
| `src/main.py` | New 13-line block after `migrate_legacy_recommended_history` calling `load_realization_factors(store_id=store_id)` (KI-3) |
| `tests/test_s5_t1_supplements_priors_populated.py` | NEW — 4 tests (3 supplements + 1 Beauty parity) |
| `tests/test_s5_t1_store_id_wired.py` | NEW — 4 tests (2 structural source-text + 2 behavioral empty-substrate parity) |
| `KNOWN_ISSUES.md` | KI-3 + KI-26 flipped `open` → `resolved`; open-count table updated (13 → 11) |
| `memory.md` | Sprint 3 section gains S5-T1 entry (template-shape, ≤15 lines) |
| `agent_outputs/code-refactor-engineer-s5-t1-summary.md` | NEW — this file |

## 4. Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s5_t1_supplements_priors_populated.py` | 4/4 green |
| `tests/test_s5_t1_store_id_wired.py` | 4/4 green |
| `tests/test_slate_regression_supplements_brand.py` | 12/12 green (sha256 `feb03500c1...` unchanged) |
| `tests/test_slate_regression_beauty_brand.py` | 19/19 green (Beauty pinned slate sha256 unchanged) |
| `tests/test_calibration_stub_shape.py` | 5/5 green (legacy contract preserved end-to-end) |
| `tests/test_s5_views.py` | 17/17 green (S-5 substrate views intact) |
| `tests/test_golden_diff.py` | 3/3 green (M0 Beauty / small_sm / mid_shopify / micro_coldstart byte-identical) |
| Full suite (`pytest -q`) | **1168 passed, 14 skipped, 0 failed** in 768s (was 1160/14/0 at G-4 closeout; delta = +8 S5-T1 tests) |

## 5. Behavior changes

- `engine_run.json::state_of_store[].prior` is now populated for every
  typed-current Observation on every fixture (Beauty, supplements,
  M0 lanes). Reserved 6B C2/C3 typed slot lit up.
- `src/main.py::run` now invokes `load_realization_factors` once per
  run, scoped to the resolved `store_id`. Today the call is a no-op
  (empty-shape projection); when Phase 9 lands the calibration
  writer, the same call site consumes the live projection without
  further plumbing.
- M0 goldens, Beauty pinned slate, supplements G-1 pinned slate: all
  byte-identical. HTML renderer does not consume `Observation.prior`.

## 6. Artifacts added

- `tests/test_s5_t1_supplements_priors_populated.py` (KI-26 acceptance)
- `tests/test_s5_t1_store_id_wired.py` (KI-3 acceptance)
- `agent_outputs/code-refactor-engineer-s5-t1-summary.md` (this file)

## 7. Remaining risks

1. **The supplements G-1 fixture sha256 stays unchanged** despite
   KI-26's resolution. This is correct (HTML renderer does not
   consume `Observation.prior`), but a future agent reading the
   ticket text might expect a re-pin. The KI-26 entry in
   `KNOWN_ISSUES.md` now documents the diagnostic path explicitly so
   the next regression of this class has a fast investigation route.
2. **`_calibration_overrides` local in `main.py` is currently
   unconsumed.** It's bound for Phase 9's consumer; today it's a
   forward-looking placeholder. A future "delete unused variable"
   refactor must NOT remove the call — `tests/test_s5_t1_store_id_wired.py`
   pins the kwarg shape structurally, so a removal will fail loud.
3. **Calibration empty-shape projection is dormant.** Until Phase 9's
   live `calibration_updated` writer ships (per implementation plan
   §6 PR-1), `read_calibration_state` returns the empty-shape dict on
   every run. KI-2 / KI-4 / KI-5 remain open as Phase-9-entry
   conditions and are unaffected by this ticket.

## 8. Follow-up work / dependencies

- **Phase 9 calibration consumer** (plan §6 L-D #1) lands the live
  `calibration_updated` writer. At that point, `main.py`'s
  `_calibration_overrides` variable becomes load-bearing: Phase 9
  PR-1 must thread it into priors/thresholds/materiality consumers
  in the engine pipeline.
- **KI-22 / KI-23** remain `open` (supplements & vertical). Not in
  S5-T1 scope.

## 9. Branch shape

Three commits on `post-6b-restructured-roadmap` (not pushed),
following the per-commit ritual:

1. `406d1a3` — `S5-T1: KI-26 supplements prior populated + KI-3 store_id wired` (impl: engine fix + KI flips + 8 new tests)
2. `4e40be5` — `Document S5-T1 in repo memory.md` (memory entry, template-shape)
3. _this commit_ — `S5-T1 summary` (this file)

## 10. Hard constraints respected

- `engine_run.json` schema **unchanged** — `Observation.prior` was
  already a reserved typed slot from 6B C2/C3; populating it is
  additive within the frozen contract.
- `event_version=1` payloads **frozen** — no event payload field
  shape changes.
- D-6 enforced — no banned ML modules touched.
- D-8 enforced — vertical scope unchanged (`{beauty, supplements,
  mixed}`).
- M0 Beauty pinned fixture sha256 **unchanged**.
- Supplements G-1 fixture sha256 **unchanged** (HTML renderer does
  not consume `Observation.prior`; the ticket's anticipated re-pin
  was not required).
- Beauty pinned slate sha256 **unchanged**
  (`tests/test_slate_regression_beauty_brand.py` 19/19 green).
- S-2 / S-3 / S-4 / S-5 / S-6 substrate write paths **untouched**.
- `config/priors.yaml` (G-3 surface) **untouched**.
- `subscription_nudge` / `routine_builder` emit blocks (G-4 surface)
  **untouched**.
- No new runtime dependencies.
