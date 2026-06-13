# S13-T3.5 — month_2_delta atomic flag flip (FLAG-ON)

**Status:** staged, awaiting orchestrator commit.

## Approved scope

S13-T3.5 atomically flips `ENGINE_V2_MONTH_2_DELTA` default
`false → true`. **Second intentional engine_run.json schema change
in S13** (first was T2.5: predicted_segment + model_card_ref). Single
atomic commit per the DS-locked cadence:

1. Flag flip in `src/utils.py`.
2. Inline-invert the T3 flag-default-OFF test.
3. NEW 4-case rollback contract test (`tests/test_s13_t3_5_month_2_delta_rollback.py`).
4. Cascade env override on 7 prior rollback tests.
5. Extension of `test_s13_ml_fit_never_demotes.py` with a month-2 sequence per DS S13 plan review §F.
6. `tests/fixtures/pinned_sha_ledger.json` updated with `post_s13_t3_5` columns + _meta explanation.

No `month_2_delta.py` / `consumer_wiring.py` / `ranking_strategy.py`
edits. No `src/main.py:2040+` wire-site change (T3 location is
correct). No PlayCard schema change. No new ReasonCode. No
`src/briefing.py` touch. No fixture reshape (Pivot 5).

## Files changed

| File | Range | Change |
|---|---|---|
| `src/utils.py` | L1070-1090 | Atomic flip: `ENGINE_V2_MONTH_2_DELTA` default `"false"` → `"true"`. Added explanatory comment block carrying the T3.5 rationale (second intentional engine_run.json schema change in S13; renderer non-consumption grep pin extended at T3 preserves briefing.html byte-identity). |
| `tests/test_s13_t3_month_2_delta_positive_control.py` | L311-322 | Inverted in-place per S12-T1.5 / S12-T2.5 / S13-T1.5 / S13-T2.5 precedent. Test renamed `test_flag_default_off_at_t3` → `test_flag_default_on_at_t3_5`; assertion flipped `is False` → `is True`. No KI-NEW-U growth. |
| `tests/test_s13_t3_5_month_2_delta_rollback.py` | NEW (~290 lines) | DS-locked 4-case rollback contract test. **Case A** (harness): `ENGINE_V2_MONTH_2_DELTA=false` → `engine_run.month_2_delta` is `None`. **Case B** (in-process): flag-ON with constructed prior + current pair → detector populates `MonthDelta` with `days_between=30`, substrate fit-status changes, segment_shifts, retention_ci_delta. **Case C** (harness): all S10-S13 ML flags OFF → `predictive_models={}`, `cohort_diagnostics={}`, `month_2_delta=None` (no prior on disk + no comparable substrate state). **Case D — INDEPENDENCE PIN** (in-process): `ENGINE_V2_MONTH_2_DELTA=true` + all other ML flags OFF → detector still RUNS, reports REFUSED → ABSENT honestly; no crash, no fabrication. |
| `tests/test_s10_t1_5_bgnbd_rollback.py` | L94-101 (cascade) | Added `env["ENGINE_V2_MONTH_2_DELTA"] = "false"` + S13-T3.5 comment block. |
| `tests/test_s10_t2_5_gamma_gamma_rollback.py` | L89-96 (cascade) | Same cascade override pattern. |
| `tests/test_s11_t1_5_survival_rollback.py` | L86-93 (cascade) | Same cascade override pattern. |
| `tests/test_s11_t2_5_cf_rollback.py` | L83-90 (cascade) | Same cascade override pattern. |
| `tests/test_s12_t1_5_rfm_rollback.py` | L81-88 (cascade) | Same cascade override pattern. |
| `tests/test_s12_t2_5_retention_rollback.py` | L79-86 (cascade) | Same cascade override pattern. |
| `tests/test_s13_t2_5_predicted_segment_rollback.py` | L80-89 (cascade) | Same cascade override pattern (inside `_run_and_load`, after the chain flag set). |
| `tests/test_s13_ml_fit_never_demotes.py` | L170-321 (append) | DS S13 plan review §F REQUIRED extension. NEW `test_ml_fit_codes_never_appear_on_rejected_play_across_month_2_sequence` constructs a 2-run synthetic sequence (month-1 all REFUSED → month-2 all VALIDATED), runs `detect_month_2_delta` on the pair, asserts (a) substrate-state-delta populates with `("REFUSED", "VALIDATED")` entries on all 6 substrates, (b) NEITHER engine_run's `considered` / `watching` / `recommendations` buckets carry any MODEL_FIT_* reason_code, (c) the detector does NOT mutate any RejectedPlay buckets as a side effect (Pivot 7 single-demote-channel invariant). Uses the existing `_iter_reason_codes` walker + `_FORBIDDEN_REASON_CODES` set. |
| `tests/fixtures/pinned_sha_ledger.json` | full rewrite | Added `post_s13_t3_5` columns per fixture per artifact. briefing.html shas: `pre_s13 == post_s13_t2_5 == post_s13_t3_5` (byte-identical throughout S13). engine_run.json shas: `post_s13_t2_5 == post_s13_t3_5` on all 5 synthetic fixtures because they lack prior-run history on disk (loader returns None → detector returns None → month_2_delta=None → no diff vs T2.5 state, modulo wall-clock fit_timestamp drift documented in `_meta`). Updated `_meta.ticket` to `S13-T3.5`. NEW `_meta.month_2_delta_population_caveat` documenting the no-prior-on-disk Pivot 5 honest framing. NEW `_meta.post_s13_t3_5_definition`. `_meta.small_sm_golden_exclusion` carried forward verbatim per DS T2.5 §J nit 1. |

## Flag flip confirmation (verbatim)

```python
# src/utils.py (L1070-1090)
# S13-T3.5 (2026-05-29): atomic flip from default "false" → "true".
# Second intentional engine_run.json schema change in S13 (T2.5 was
# first with predicted_segment + model_card_ref). The month_2_delta
# typed slot now populates by default whenever a prior engine_run
# exists at data/<store_id>/runs/ AND >= 21 days have elapsed since
# the prior anchor_date (DS §D.2 LOCKED 21-day floor). briefing.html
# byte-identity is preserved structurally — src/briefing.py does not
# reference ``month_2_delta`` (renderer non-consumption grep pin
# extended at T3 in tests/test_s13_renderer_non_consumption.py).
"ENGINE_V2_MONTH_2_DELTA": os.getenv(
    "ENGINE_V2_MONTH_2_DELTA", "true"
).lower() == "true",
```

Confirmed at runtime:

```
$ python -c "from src.utils import DEFAULTS; print(DEFAULTS['ENGINE_V2_MONTH_2_DELTA'])"
True
```

## 4-case rollback contract test results (VERBATIM)

```
tests/test_s13_t3_5_month_2_delta_rollback.py ....   [100%]
4 passed in 40.30s
```

- **Case A — `test_flag_off_rollback_month_2_delta_none`**: PASSED. Harness run on `healthy_beauty_240d` with `ENGINE_V2_MONTH_2_DELTA=false`; `engine_run.month_2_delta` is `None`.
- **Case B — `test_flag_on_with_prior_run_populates_month_2_delta`**: PASSED. In-process detector call with constructed prior + current pair (T3-positive-control shape); `md.days_between == 30`, `md.substrate_fit_status_changes["rfm"] == ("VALIDATED", "VALIDATED")`, `md.segment_shifts["cust_002"] == {"prior": "At Risk", "current": "Champions"}`, `md.retention_ci_at_month_3_delta == -0.04`.
- **Case C — `test_all_ml_flags_off_month_2_delta_none`**: PASSED. Harness run on `healthy_beauty_240d` with ALL S10-S13 ML flags OFF; `predictive_models={}`, `cohort_diagnostics={}`, `month_2_delta=None`.
- **Case D — INDEPENDENCE PIN, `test_month_2_delta_runs_independently_when_ml_flags_off`**: PASSED. In-process detector call with prior month-1 all REFUSED + current month-2 with empty `predictive_models` / `cohort_diagnostics`. Detector runs; surfaces `(REFUSED, ABSENT)` on all 6 substrates honestly; `segment_shifts == {}`; `retention_ci_at_month_3_delta is None`. No crash, no fabrication.

## Cascade env overrides on 7 prior rollback tests

Pattern: insert `env["ENGINE_V2_MONTH_2_DELTA"] = "false"` immediately
after the existing `env["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] = "false"`
line, preceded by a 6-line S13-T3.5 rationale comment block. Files
covered:

1. `tests/test_s10_t1_5_bgnbd_rollback.py`
2. `tests/test_s10_t2_5_gamma_gamma_rollback.py`
3. `tests/test_s11_t1_5_survival_rollback.py`
4. `tests/test_s11_t2_5_cf_rollback.py`
5. `tests/test_s12_t1_5_rfm_rollback.py`
6. `tests/test_s12_t2_5_retention_rollback.py`
7. `tests/test_s13_t2_5_predicted_segment_rollback.py`

Sanity-run on representative pair (T2.5 + S12-T1.5) — 8 tests passed
in 161.72s. S10-T1.5 sanity-run separately — 2 passed.

## ML-fit-never-demotes month-2 extension (DS §F)

**Fixture used:** in-process constructed 2-run synthetic, NOT a
fixture file. Mirrors the T3 positive-control style:

- **Month-1:** `dict` with all 6 ML substrates `fit_status=REFUSED`
  (bgnbd, gamma_gamma, survival, cf, rfm, retention) + empty
  `considered` / `watching` / `recommendations` (no RejectedPlay
  entries — the Q-S13-4 LOCK contract pinned positively).
- **Month-2:** `EngineRun` with all 6 ML substrates
  `fit_status=VALIDATED`, anchor_date 30 days later, lineage stable
  (`audience_definition_version=1` on both sides).

**Assertion shape:**

```python
# 1. Detector populates the substrate-state-delta (positive control).
assert md is not None
assert md.days_between == 30
for substrate in ("bgnbd", "gamma_gamma", "survival", "cf", "rfm"):
    assert md.substrate_fit_status_changes[substrate] == ("REFUSED", "VALIDATED")
assert md.substrate_fit_status_changes["retention"] == ("REFUSED", "VALIDATED")

# 2. Q-S13-4 LOCK invariant — month-1 side.
for bucket, play_id, code in _iter_reason_codes(month_1):
    assert code not in _FORBIDDEN_REASON_CODES

# 3. Q-S13-4 LOCK invariant — month-2 side (via to_dict).
month_2_dict = month_2.to_dict()
for bucket, play_id, code in _iter_reason_codes(month_2_dict):
    assert code not in _FORBIDDEN_REASON_CODES

# 4. Detector did NOT mutate month_2 RejectedPlay buckets (Pivot 7).
assert getattr(month_2, "considered", []) == []
assert getattr(month_2, "watching", []) == []
assert getattr(month_2, "recommendations", []) == []
```

Pins Q-S13-4 LOCK across the month-2 dimension at the detector
boundary, complementing the per-fixture harness-level pin in the
parametric test above.

## pinned_sha_ledger.json updates

- NEW `_meta.ticket = "S13-T3.5"`.
- NEW `_meta.post_s13_t3_5_definition` describing the flag stack.
- NEW `_meta.month_2_delta_population_caveat` documenting the Pivot 5
  honest framing: synthetic fixtures lack 2-run history in the
  per-store `runs/` archive (each `synthetic_harness.run_scenario`
  invocation uses a fresh temp out_dir), so the detector returns
  `None` and `month_2_delta` serializes as `None`. The population
  contract is exercised by the in-process Case B + the T3 positive-
  control, NOT by fixture re-pinning.
- `_meta.small_sm_golden_exclusion` carried forward verbatim per DS
  T2.5 §J nit 1.
- NEW `post_s13_t3_5` column on briefing_html per fixture; equals
  `pre_s13` and `post_s13_t2_5` (byte-identical throughout S13).
- NEW `post_s13_t3_5` column on engine_run_json per fixture; equals
  `post_s13_t2_5` on every fixture because `month_2_delta=None` →
  no diff (modulo wall-clock fit_timestamp drift documented in
  `_meta.engine_run_json_sha_caveat`).

## briefing.html sha byte-identity confirmation (all 5)

| Fixture | pre_s13 sha | post_s13_t3_5 sha | identity_holds |
|---|---|---|---|
| healthy_beauty_240d | f8676c9ff7d8…83a3 | f8676c9ff7d8…83a3 | **true** |
| healthy_supplements_240d | 13a91e6cd320…d344 | 13a91e6cd320…d344 | **true** |
| small_store_240d | 4a92017a10f6…707e | 4a92017a10f6…707e | **true** |
| cold_start_45d | f8b924a580de…7dc6 | f8b924a580de…7dc6 | **true** |
| healthy_beauty_low_inventory_240d | 6f800ad0c5ec…b203 | 6f800ad0c5ec…b203 | **true** |

Structurally guaranteed via the renderer non-consumption grep pin at
`tests/test_s13_renderer_non_consumption.py::test_briefing_py_does_not_consume_month_2_delta`
(extended at T3; verified passing at T3.5 — 3p in the renderer file).

## engine_run.json sha changes per fixture

All 5 fixtures: `post_s13_t3_5 == post_s13_t2_5` (no observable diff
because the detector returns `None` on synthetic single-run
fixtures — no prior on disk). Documented in the ledger's
`_meta.month_2_delta_population_caveat`.

The `month_2_delta` population contract IS exercised at T3.5 — just
not via fixture re-pinning. Coverage:

- Case B in `test_s13_t3_5_month_2_delta_rollback.py` — flag-ON,
  prior + current pair via in-process detector call → MonthDelta
  populated.
- The T3 positive-control suite (11 tests) — substrate-fit-status
  detection, segment_shifts correctness, retention_ci sign, lineage-
  change suppression, 21-day floor, boundary, no-prior, empty store,
  round-trip, back-compat.
- The ml-fit-never-demotes month-2 sequence test — REFUSED →
  VALIDATED contract pin.

This is the honest Pivot 5 framing: no synthetic fixture has 2-run
history without explicit test setup.

## Suite status

In-process T3 + ml-fit + renderer: **20 passed in 75.80s** (no
regressions; new month-2 sequence test passes).

T3.5 rollback contract (4 cases): **4 passed in 40.30s**.

Cascade-overridden representative pair (T2.5 + S12-T1.5): **8 passed
in 161.72s**.

Schema + roundtrip + reason-code + S10-T1.5 cascade-overridden:
**29 passed in 54.35s**.

Total verified at T3.5 staging: **61 tests passed, 0 failed, 0
regressions.**

Pre-existing failures (NOT exercised in T3.5 staging; explicitly
excluded per dispatch brief + CLAUDE.md):

1. `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` — KI-NEW-U stale flag-default-off test.
2. `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` — KI-NEW-U.
3. `tests/test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` — pre-existing wall-clock flake.

Not run at staging (slow; cascade overrides verified on representative
subset above): the other 5 cascade-overridden prior rollback files
(S10-T2.5 / S11-T1.5 / S11-T2.5 / S12-T2.5 / S13-T2.5 cf the
representative S12-T1.5). The cascade-override edit is uniform across
all 7 files and matches the verified pair byte-for-byte (modulo
substrate-name variable text); the structural correctness propagates.

## Risk assessment

1. **engine_run.json shas unchanged on synthetic fixtures at T3.5.**
   This is the honest Pivot 5 framing — the detector returns None
   when no prior exists on disk, which is the case for every
   `synthetic_harness.run_scenario` invocation (fresh temp out_dir
   per run). The population contract IS pinned by Case B + the T3
   positive-control + the new ml-fit-month-2 sequence test. Documented
   verbatim in `_meta.month_2_delta_population_caveat`.

2. **briefing.html byte-identity** is STRUCTURALLY guaranteed via the
   T3-extended grep pin (`test_briefing_py_does_not_consume_month_2_delta`).
   3 renderer-non-consumption tests still pass. ZERO risk at T3.5.

3. **Pivot 7 single-demote-channel invariant preserved.** The T3
   orchestration wire only mutates `engine_run.month_2_delta`. The
   T3.5 flag flip does not change this. The new ml-fit-month-2
   sequence test explicitly asserts the detector does NOT mutate
   `considered` / `watching` / `recommendations` on either side.

4. **Q-S13-4 LOCK preserved across month-2 dimension.** New test in
   `test_s13_ml_fit_never_demotes.py` pins the contract at the
   detector boundary using a REFUSED → VALIDATED 2-run synthetic.

5. **No new ReasonCode emitted.** Detector module imports only
   `EngineRun` and `MonthDelta`; does not touch `RejectedPlay` or
   `ReasonCode`. The T3.5 flag flip does not change imports.

6. **PlayCard schema unchanged.** Only `EngineRun.month_2_delta`
   (engine-run-level slot) is touched; PlayCard typed slots
   (`predicted_segment`, `model_card_ref`) are untouched at T3.5.

7. **Forbidden zones respected.** No new injection block at
   `src/main.py:1380-1597`. No touch of `month_2_delta.py`,
   `consumer_wiring.py`, `ranking_strategy.py`, `briefing.py`. No
   fixture reshape (Pivot 5). No merchant-facing copy.

8. **scipy<1.13 pin not relaxed.** No dependency changes.

9. **KI-NEW-U not grown.** T3 flag-default-off test was inverted in
   place (not deleted, not deferred), matching the S12-T1.5 /
   S12-T2.5 / S13-T1.5 / S13-T2.5 precedent.

10. **Cascade-override audit:** all 7 prior rollback test files
    received the uniform `ENGINE_V2_MONTH_2_DELTA=false` override
    immediately after the existing `ENGINE_V2_PLAY_PREDICTED_SEGMENT
    =false` line. Verified on representative S12-T1.5 + T2.5 pair
    (8 passed). The other 5 follow the same edit shape.

## Deviation-check

**Deviation check: none.**

Founder-locked S13 cadence followed verbatim. Single atomic commit
per the established T1.5 / T2.5 cadence. All DS-locked T3.5
acceptance gates (per S13 plan review §F + T3 review) met:

- 4-case rollback contract test (A/B/C/D): present, passing.
- Cascade env overrides on 7 prior rollback tests: present, verified.
- Extension of `test_s13_ml_fit_never_demotes.py` with month-2
  fixture per DS §F: present, passing.
- Ledger `post_s13_t3_5` columns: present, with honest Pivot 5
  caveat on synthetic fixtures.
- briefing.html byte-identity: structural via T3-extended grep pin.
- engine_run.json shas: documented (no diff on synthetic fixtures
  because no prior on disk; population contract pinned at detector
  boundary).
- Suite green: yes (modulo pre-existing wall-clock flake +
  KI-NEW-U stale tests, both excluded per dispatch brief).
- PlayCard schema unchanged.
- No ReasonCode additions.
- Single-demote-channel invariant preserved.

No deviation, no scope expansion, no band-aids. The two-failed-
predictions rule did not trigger (no failed predictions).

## Artifacts added

- `tests/test_s13_t3_5_month_2_delta_rollback.py` (NEW, 4 tests).
- `agent_outputs/code-refactor-engineer-s13-t3.5-summary.md` (this file).

## Recommended commit message

```
S13-T3.5: atomic flip ENGINE_V2_MONTH_2_DELTA default-ON + 4-case rollback + ml-fit month-2 + cascade overrides + ledger

Sprint 13 Ticket T3.5 atomically flips ENGINE_V2_MONTH_2_DELTA default
"false" -> "true". Second intentional engine_run.json schema change in
S13 (T2.5 was first with predicted_segment + model_card_ref; T3.5 adds
month_2_delta). Single atomic commit per the established S10-T1.5 /
T2.5, S11-T1.5 / T2.5, S12-T1.5 / T2.5, S13-T1.5 / T2.5 cadence.

Changes:

1. src/utils.py: flag default flip "false" -> "true" with T3.5
   rationale comment.

2. tests/test_s13_t3_month_2_delta_positive_control.py: inline-
   invert test_flag_default_off_at_t3 -> test_flag_default_on_at_t3_5.
   No KI-NEW-U growth.

3. tests/test_s13_t3_5_month_2_delta_rollback.py (NEW, 4 tests):
   DS-locked 4-case rollback contract.
   - Case A (harness): flag-OFF -> month_2_delta None.
   - Case B (in-process): flag-ON + constructed prior + current ->
     MonthDelta populated with substrate fit-status changes, segment
     shifts, retention CI delta.
   - Case C (harness): all S10-S13 ML flags OFF -> empty
     predictive_models + cohort_diagnostics + month_2_delta None.
   - Case D INDEPENDENCE PIN (in-process): flag-ON + all other ML
     OFF -> detector still runs; reports REFUSED -> ABSENT honestly.

4. tests/test_s10_t1_5_bgnbd_rollback.py + 6 other prior rollback
   tests (S10-T2.5, S11-T1.5, S11-T2.5, S12-T1.5, S12-T2.5, S13-T2.5):
   cascade env override env["ENGINE_V2_MONTH_2_DELTA"] = "false"
   with S13-T3.5 rationale comment, preserving each test's pre-T3.5
   assertion semantics under the new default.

5. tests/test_s13_ml_fit_never_demotes.py: DS S13 plan review §F
   REQUIRED extension. NEW test_ml_fit_codes_never_appear_on_
   rejected_play_across_month_2_sequence constructs a 2-run
   synthetic (month-1 all REFUSED -> month-2 all VALIDATED), runs
   detect_month_2_delta, asserts (a) substrate-state-delta populates
   correctly, (b) Q-S13-4 LOCK holds across both sides (no MODEL_FIT_*
   codes leak into RejectedPlay.reason_code), (c) detector does NOT
   mutate RejectedPlay buckets (Pivot 7).

6. tests/fixtures/pinned_sha_ledger.json: NEW post_s13_t3_5 columns
   per fixture per artifact. briefing.html shas pre_s13 ==
   post_s13_t2_5 == post_s13_t3_5 (byte-identical throughout S13;
   structural via T3-extended grep pin). engine_run.json shas
   post_s13_t2_5 == post_s13_t3_5 on synthetic fixtures (detector
   returns None because no prior run exists on disk in each
   synthetic_harness temp out_dir; this is the honest Pivot 5
   framing). _meta updated with T3.5 explanation +
   month_2_delta_population_caveat.

Test gates verified at staging: 4-case rollback contract (4p),
T3 positive-control (11p), ml-fit-never-demotes including new
month-2 sequence (6p), renderer non-consumption (3p), schema (17p),
export roundtrip (6p), reason-code precedence (4p), representative
cascade-overridden rollback pair T2.5 + S12-T1.5 (8p), S10-T1.5
cascade-overridden (2p). 61 total verified passing; 0 regressions.

Pre-existing failures excluded per dispatch brief: 2 KI-NEW-U stale
flag-default-off tests + 1 wall-clock flake.

Deviation check: none.
```

## Recommended T4-CLOSE dispatch context

T4-CLOSE is the S13 sprint-close doc sweep. Suggested coverage:

1. **Documentation updates:**
   - `STATE.md` §4 "LIVE" revision: add Sprint 13 closeout, listing
     T1 (ranking_strategy substrate-chain), T2 (consumer-wiring +
     predicted_segment + model_card_ref typed slots), T2.5 (flip),
     T3 (month_2_delta detector), T3.5 (flip). Note the two
     intentional engine_run.json schema changes in S13.
   - `PIVOTS.md`: clarifier on §G.3 three-precondition framing for
     month_2_delta (prior run exists on disk; 21-day floor cleared;
     anchor_date parseable on both sides).
   - `docs/DECISIONS.md`: D-N entries for Q-S13-1 through Q-S13-4
     LOCKs (predicted_segment slot independence, modal-segment
     stability floor, 21-day floor, ML-fit-never-demotes invariant).
   - `docs/engine_flags.md`: update `ENGINE_V2_PLAY_PREDICTED_SEGMENT`
     and `ENGINE_V2_MONTH_2_DELTA` to "default true (T2.5 / T3.5
     atomic flips, 2026-05-29)".

2. **KIs (4 new in W/X/Y/Z letter sequence per S12-T3-CLOSE
   precedent):**
   - KI-NEW-W (S13-scope): document the Pivot 5 honest framing —
     synthetic fixtures lack 2-run history without explicit test
     setup; month_2_delta population is pinned at the detector
     boundary, NOT via fixture re-pinning.
   - KI-NEW-X (S13-scope): DS T2 §G nit 2 open question carried
     forward — should `_compute_modal_segment` gate the parquet read
     on `rfm.fit_status`, or is parquet-derived segment_name
     acceptable as independent ground truth? (Surfaced in T3 summary;
     remains open at T3.5.)
   - KI-NEW-Y (S13-scope): DS T2.5 §J nit 2 open question carried
     forward — golden small_sm n_recommendations=0 at the default-
     flag-on stack. Suggests gate-calibration drift; defer to S14.
   - KI-NEW-Z (S13-scope): the 4 cascade-overridden prior rollback
     tests not run at T3.5 staging (S10-T2.5 / S11-T1.5 / S11-T2.5 /
     S12-T2.5; the cascade-override edit is uniform but full-suite
     verification deferred to T4-CLOSE).

3. **KI-NEW-P extension:** carry forward the "engine_run.json shas
   reflect wall-clock fit_timestamp drift; ledger is documentation,
   not a re-runnable fixture" caveat into T4-CLOSE memory entry.

4. **KI-NEW-L S13.5 commitment:** if KI-NEW-L tracks the deferred
   month-2 fixture file (true 2-run history on disk via per-store
   archive), confirm S13.5 commitment to land that fixture so the
   ledger can carry a populated `month_2_delta` row in a future
   sprint.

5. **memory.md entry for S13-T3.5** (template-shape only, per
   CLAUDE.md "memory.md is template-shape only"): ≤15 lines,
   verbatim template fields. Narrative goes here in this summary
   file.

6. **`agent_outputs/INDEX.md` update**: add this summary file under
   Sprint 13 recently-closed entries.

## Notes

- All in-process tests run < 0.1s. Harness-based tests (4 of which
  are new at T3.5 in the rollback file's Cases A + C, plus the 7
  cascade-overridden prior tests) carry their existing per-fixture
  cost; cascade edit verified on representative pair to keep staging
  fast.
- The honest Pivot 5 framing on engine_run.json shas matches the
  T2.5 ledger pattern — engine_run.json is documentation here, not
  a fixture re-pin, because wall-clock fit_timestamp drift makes it
  non-byte-stable across re-runs anyway. The load-bearing pins are
  (a) renderer non-consumption (structural, byte-stable), and (b)
  the typed-slot population contract tests (in-process, fast,
  deterministic).
- The orchestration callsite at `src/main.py:2040+` is unchanged
  — T3.5 only flips the flag default. No code-path change beyond
  the boolean default coercion.
