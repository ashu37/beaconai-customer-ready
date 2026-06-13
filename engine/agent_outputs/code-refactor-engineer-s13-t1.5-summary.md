# S13-T1.5 — ENGINE_V2_RANKING_STRATEGY_CHAIN atomic flag flip (default ON)

**Status:** staged, awaiting orchestrator commit.

## Approved scope

Single atomic commit: flip `ENGINE_V2_RANKING_STRATEGY_CHAIN` default
`false → true` in `src/utils.py`; handle the 3 T1 flag-default tests
in `tests/test_s13_t1_ranking_strategy_flag.py` via inline inversion
(Option a, mirroring S12-T2.5 precedent). No orchestration wire-up. No
consumer call-site change. No rollback contract test. No PlayCard
edits. No fixture touches.

## Files changed

| File | Range | Change |
|---|---|---|
| `src/utils.py` | L1036–1038 | `os.getenv("ENGINE_V2_RANKING_STRATEGY_CHAIN", "false")` → `"true"`. Flag was already in the `_coerce` bool set at L1317 per T1 — no change there. |
| `tests/test_s13_t1_ranking_strategy_flag.py` | L1–6, L15–25 | Module docstring updated to S13-T1.5 framing. Renamed `test_flag_default_off_at_t1` → `test_flag_default_on_after_t1_5`; inverted the assertion `is False` → `is True`. Updated the docstring to cite the S12-T2.5 Option-a precedent. |

The other two T1 tests (`test_flag_env_override_true`,
`test_flag_in_coerce_bool_set`) are default-independent and required
no change — they exercise the env-override + `_coerce` routing and
already encode the correct expected behavior.

## Flag-default test approach

**Option (a) — inline inversion.** Chosen for:
- Cleaner test stream (no growth of KI-NEW-U stale flag-default-off
  test list).
- Mirrors S12-T2.5 cadence.
- Per dispatch brief recommendation.

The pre-existing S12 stale tests (`test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1`,
`test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off`)
remain stale under KI-NEW-U — not chased per CLAUDE.md / dispatch
brief.

## Explicit confirmations

- **NO orchestration wire-up.** No edit to `src/decide.py`, `src/sizing.py`,
  `src/engine_run.py`, `src/main.py`, `src/audience_builders.py`, or
  `src/ranking_strategy.py`.
- **NO consumer call-site change.** `rank_audience()` is not invoked
  anywhere in the engine yet; that lands at T2+.
- **NO rollback contract test added.** There is no consumer side
  effect at T1.5 — flag-OFF and flag-ON produce identical
  `engine_run.json` and `briefing.html` by construction. A rollback
  contract is meaningful only once T2 wires a consumer.
- **NO PlayCard mutation.** Stubs stay `None`. No `ReasonCode`
  additions.
- **NO fixture touches** (Pivot 5).
- **NO merchant-facing copy.**
- **Single-demote-channel invariant preserved** — no new injection
  points into `engine_run.recommendations` were added.

## Byte-identity verification

`tests/test_slate_regression_beauty_brand.py` +
`tests/test_slate_regression_supplements_brand.py`:
**29 passed, 2 xpassed** — Beauty + Supplements briefing.html sha and
engine_run.json sha unchanged post flag-flip. The two pinned slate
regressions are the load-bearing byte-identity gates for the slate
output. Other fixtures (Micro Coldstart / Mid Shopify / Small SM) are
not separately sha-pinned in the active suite but are exercised via
the synthetic-fixtures families; byte-identity holds by construction
because no code path consumes `rank_audience()`.

## Suite status

Full suite (`python -m pytest -q`): **2078 passed, 3 failed, 14 skipped,
4 xfailed, 2 xpassed** in 1833s.

The 3 failures are all pre-existing and explicitly excluded from
chase-scope per the dispatch brief and CLAUDE.md:

1. `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` — KI-NEW-U
   stale S12-T1.5 flag-default-off test.
2. `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` —
   KI-NEW-U stale S12-T2.5 flag-default-off test.
3. `tests/test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` —
   wall-clock flake (pre-existing, documented).

None of these regressed at T1.5.

## Risk assessment

- **Byte-identity risk:** zero by construction. No code path reads
  `DEFAULTS["ENGINE_V2_RANKING_STRATEGY_CHAIN"]` yet.
- **Single-demote-channel:** unchanged — no new appends to
  `engine_run.recommendations`.
- **Test-stream noise:** flat. Option-a inversion keeps the KI-NEW-U
  stale-list at 2 entries (S12-T1 and S12-T2).
- **Forward exposure (T2):** when T2 wires `rank_audience()` into a
  consumer site, flag-ON becomes behaviorally meaningful and a
  rollback contract test (env-flip flag-OFF reverts to prior
  ordering) will be required there per S12-T2 / S11-T2 cadence.

## Deviation-check

Deviation check: none.

## Recommended commit message

```
S13-T1.5: ENGINE_V2_RANKING_STRATEGY_CHAIN atomic flip — default ON

Flips ENGINE_V2_RANKING_STRATEGY_CHAIN default false → true in
src/utils.py. Inline-inverts the T1 flag-default test
(test_flag_default_off_at_t1 → test_flag_default_on_after_t1_5;
assertion is False → is True) per S12-T2.5 Option-a precedent,
avoiding KI-NEW-U stale-test growth.

No consumer of rank_audience() exists yet — module remains
consumer-call-ready only (T2+). briefing.html sha + engine_run.json
sha byte-identical on Beauty + Supplements pins by construction.

No orchestration wire-up. No rollback contract test (no consumer
behavior to roll back at T1.5). PlayCard stubs unchanged. Pivot 5
respected — no fixture touches. Single-demote-channel invariant
preserved.

Suite: 2078 passed, 3 pre-existing failures (2 KI-NEW-U S12 stale
flag-default-off + wall-clock flake — not chased per CLAUDE.md).

Deviation check: none.
```

## Recommended T2 dispatch context

T2 is the consumer wiring + behavioral atomic flip. The dispatch
brief should cover:

1. **PlayCard wiring** — populate the `ranking_strategy` /
   `ml_fit_*` PlayCard fields from `rank_audience()` output (per
   T1 module + S13 consumer-wiring plan).
2. **ML-fit ReasonCode activation** — the suppressed ReasonCode set
   that T1 left dormant becomes emittable when the chain ranks an
   ML-fit candidate above the prior baseline.
3. **`src/engine_run.py:167-171` comment revision** — the inline
   comment ("ranking_strategy stays None until S13-T2") needs the
   T2 update; flag the line range explicitly.
4. **AST-aware dormancy test refactor** — DS T1 forward note flagged
   that the dormancy test for the suppressed ReasonCodes should
   migrate to AST-aware scanning before T2 lights them up, so the
   test transitions cleanly from "must not appear" to
   "must appear under flag-ON, must not appear under flag-OFF."
5. **Rollback contract test** — required at T2 atomic flip per
   S11-T2 / S12-T2 cadence (env-flip flag-OFF restores prior
   ordering + restores byte-identical briefing.html shas).
6. **Fixture re-pin** — once the chain actually changes selection,
   atomic flag-flip + fixture re-pin land together (per S5-T1 /
   S6-T1.5 / Sprint-2 closeout cadence).

## Artifacts

- This summary: `agent_outputs/code-refactor-engineer-s13-t1.5-summary.md`
- No other artifacts.
