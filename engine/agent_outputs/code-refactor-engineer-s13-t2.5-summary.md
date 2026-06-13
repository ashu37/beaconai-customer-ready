# S13-T2.5 — ENGINE_V2_PLAY_PREDICTED_SEGMENT atomic default flip (OFF → ON)

**Status:** staged, awaiting orchestrator commit.

## Approved scope

S13-T2.5 atomic flag flip of `ENGINE_V2_PLAY_PREDICTED_SEGMENT` from
default `false` to default `true`. This is the **first ticket in S13
that intentionally changes `engine_run.json` shas on pinned fixtures**;
`briefing.html` byte-identity STILL HOLDS structurally because the
renderer at `src/briefing.py` does not consume `PlayCard.
predicted_segment` or `PlayCard.model_card_ref` (pinned at
`tests/test_s13_renderer_non_consumption.py`).

Per S7.6 / S8 / S10-T1.5 / S10-T2.5 / S11-T1.5 / S11-T2.5 / S12-T1.5 /
S12-T2.5 / S13-T1.5 cadence: SINGLE atomic flip + rollback contract
test (4 cases A/B/C/D) + REQUIRED renderer non-consumption grep pin +
per-fixture predicted_segment state report + new
`tests/fixtures/pinned_sha_ledger.json`.

## Files changed

| File | Range | Change |
|---|---|---|
| `src/utils.py` | L1039–1058 | Default flip `ENGINE_V2_PLAY_PREDICTED_SEGMENT` from `"false"` → `"true"`. Comment block rewritten to document S13-T2.5 atomic flip + ledger + grep-pin contract (Option-a comment-side rationale). |
| `tests/test_s13_t2_predicted_segment_population.py` | L44–61 | Inverted T2 flag-default test in place per S12-T2.5 / S13-T1.5 precedent (Option-a inline-invert, no KI-NEW-U growth). Renamed to `test_engine_v2_play_predicted_segment_default_on_after_t2_5`. Asserts `DEFAULTS["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] is True`; skips if env override present. |
| `tests/test_s10_t1_5_bgnbd_rollback.py` | L85–93 | Added `env["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] = "false"` env override + S13-T2.5 rationale comment, mirroring the existing S11-T2.5 / S12-T1.5 / S12-T2.5 cascade comments. |
| `tests/test_s10_t2_5_gamma_gamma_rollback.py` | L80–88 | Same env override + comment. |
| `tests/test_s11_t1_5_survival_rollback.py` | L77–85 | Same env override + comment. |
| `tests/test_s11_t2_5_cf_rollback.py` | L74–82 | Same env override + comment. |
| `tests/test_s12_t1_5_rfm_rollback.py` | L72–80 | Same env override + comment. |
| `tests/test_s12_t2_5_retention_rollback.py` | L70–78 | Same env override + comment. |
| `tests/test_s13_renderer_non_consumption.py` | NEW (~75 lines) | DS REQUIRED renderer non-consumption grep pin. Two tests: asserts `predicted_segment` and `model_card_ref` strings are absent from `src/briefing.py` source bytes. This is the STRUCTURAL guarantee behind the briefing.html byte-identity claim across the T2.5 flip. |
| `tests/test_s13_t2_5_predicted_segment_rollback.py` | NEW (~225 lines) | 4 rollback cases (A/B/C/D) per DS plan §D-T2.5. Case A: flag-OFF override, all other ML flags ON → PlayCard.predicted_segment + model_card_ref stay None. Case B: all flags ON → at least one PlayCard on Beauty carries populated model_card_ref. Case C: all S10-S13 ML flags OFF → no consumer-wiring state populates. Case D (INDEPENDENCE PIN): predicted_segment ON, BG/NBD OFF → chain walks past missing substrate, model_card_ref still populates, strategy_used != "BGNBD". |
| `tests/fixtures/pinned_sha_ledger.json` | NEW | DS Q-S13-2 Option α ledger. `pre_s13` (flag-OFF) vs `post_s13_t2_5` (flag-ON) shas per fixture per artifact across all 5 pinned fixtures. briefing.html `identity_holds=true` on all 5 (load-bearing). engine_run.json sha changes documented; ledger preamble explicitly notes the wall-clock `fit_timestamp` caveat so the ledger is documentation, not a re-runnable test gate (the gates are the renderer-grep + rollback test). |

## Flag flip confirmation

`src/utils.py` L1058: `"ENGINE_V2_PLAY_PREDICTED_SEGMENT": os.getenv("ENGINE_V2_PLAY_PREDICTED_SEGMENT", "true").lower() == "true"`.

`DEFAULTS["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] is True` — verified via
`tests/test_s13_t2_predicted_segment_population.py::test_engine_v2_play_predicted_segment_default_on_after_t2_5`.

Already in `_coerce` bool set per T2 (no change required).

## Per-fixture predicted_segment state report (VERBATIM)

All 5 fixtures run with `ENGINE_V2_PLAY_PREDICTED_SEGMENT=true` and all
other ML flags at their default-ON state. Run date 2026-05-29. Honest
Pivot-5 framing — structural correctness pinned; predictive accuracy
NOT claimed.

### healthy_beauty_240d (n_recommendations = 3)

All 3 PlayCards (`discount_dependency_hygiene`, `cohort_journey_first_to_second`, `winback_dormant_cohort`) show identical chain-walk state:

- `predicted_segment`: **None** (RFM substrate REFUSED → no modal-segment computation)
- `model_card_ref.strategy_used`: **RECENCY** (terminal floor)
- `model_card_ref.fit_status_chain`: `[("bgnbd", "REFUSED"), ("cf", "INSUFFICIENT_DATA"), ("survival", "REFUSED"), ("rfm", "REFUSED")]`
- `model_card_ref.fit_warnings`: `["MODEL_FIT_REFUSED:bgnbd", "MODEL_FIT_INSUFFICIENT_DATA:cf", "MODEL_FIT_REFUSED:survival", "MODEL_FIT_REFUSED:rfm"]`
- Upstream `predictive_models`: bgnbd=REFUSED (n=3844), gamma_gamma=REFUSED (n=0), survival=REFUSED (n=3844), cf=INSUFFICIENT_DATA (n=9404), rfm=REFUSED (n=9404).

### healthy_supplements_240d (n_recommendations = 0)

decision_state=`abstain_soft`; no recommendations to walk. Consumer-wiring pass is a structural no-op on this fixture (no cards in `recommendations`). engine_run.json sha drift on this fixture is driven by upstream substrate `fit_timestamp` wall-clock changes only.

### small_store_240d (n_recommendations = 1)

1 PlayCard (`cohort_journey_first_to_second`):

- `predicted_segment`: **None**
- `model_card_ref.strategy_used`: **RECENCY**
- `model_card_ref.fit_status_chain`: `[("bgnbd", "REFUSED"), ("cf", "INSUFFICIENT_DATA"), ("survival", "REFUSED"), ("rfm", "REFUSED")]`
- `model_card_ref.fit_warnings`: `["MODEL_FIT_REFUSED:bgnbd", "MODEL_FIT_INSUFFICIENT_DATA:cf", "MODEL_FIT_REFUSED:survival", "MODEL_FIT_REFUSED:rfm"]`
- Upstream `predictive_models`: bgnbd=REFUSED (n=564), gamma_gamma=REFUSED (n=0), survival=REFUSED (n=564), cf=INSUFFICIENT_DATA (n=1087), rfm=REFUSED (n=1087).

### cold_start_45d (n_recommendations = 0)

45-day cold-start fixture. No recommendations. Consumer-wiring pass is a structural no-op. engine_run.json sha drift driven by upstream substrate `fit_timestamp` only.

### healthy_beauty_low_inventory_240d (n_recommendations = 3)

All 3 PlayCards (`discount_dependency_hygiene`, `cohort_journey_first_to_second`, `winback_dormant_cohort`) show identical chain-walk state — same shape as `healthy_beauty_240d` above:

- `predicted_segment`: **None**
- `model_card_ref.strategy_used`: **RECENCY**
- `model_card_ref.fit_status_chain`: `[("bgnbd", "REFUSED"), ("cf", "INSUFFICIENT_DATA"), ("survival", "REFUSED"), ("rfm", "REFUSED")]`
- `model_card_ref.fit_warnings`: `["MODEL_FIT_REFUSED:bgnbd", "MODEL_FIT_INSUFFICIENT_DATA:cf", "MODEL_FIT_REFUSED:survival", "MODEL_FIT_REFUSED:rfm"]`

## briefing.html sha byte-identity (load-bearing structural claim)

Pre-T2.5 (flag-OFF env override) vs Post-T2.5 (flag-ON default) briefing.html sha256 across all 5 fixtures:

| Fixture | briefing.html sha (flag-OFF) | briefing.html sha (flag-ON) | identity_holds |
|---|---|---|---|
| healthy_beauty_240d | `f8676c9f…280e83a3` | `f8676c9f…280e83a3` | **TRUE** |
| healthy_supplements_240d | `13a91e6c…416d344` | `13a91e6c…416d344` | **TRUE** |
| small_store_240d | `4a92017a…89707e` | `4a92017a…89707e` | **TRUE** |
| cold_start_45d | `f8b924a5…779a7dc6` | `f8b924a5…779a7dc6` | **TRUE** |
| healthy_beauty_low_inventory_240d | `6f800ad0…01b203` | `6f800ad0…01b203` | **TRUE** |

**briefing.html byte-identity holds across all 5 fixtures at the T2.5 flip.** Pinned slate regression tests on Beauty + Supplements remain green (28 passed + 2 xpassed across the two test files post-flip).

## engine_run.json sha changes per fixture (intentional)

All 5 fixtures' engine_run.json shas change at the flip, as expected.
The diff is confined to `recommendations[*].predicted_segment` +
`recommendations[*].model_card_ref` keys (plus upstream substrate
`fit_timestamp` wall-clock drift, which is pre-existing and not
introduced by T2.5). Per-fixture pre/post shas captured in
`tests/fixtures/pinned_sha_ledger.json` with explicit wall-clock caveat
in the ledger `_meta` block.

## Renderer non-consumption grep result

```
$ grep -rn "predicted_segment\|model_card_ref" src/briefing.py
(empty)
$ echo $?
1
```

`src/briefing.py` does NOT reference either field name anywhere in its
source. The structural byte-identity guarantee for `briefing.html`
across the T2.5 flip is pinned at
`tests/test_s13_renderer_non_consumption.py` (two tests, one per field).

## Rollback contract test (4 cases)

`tests/test_s13_t2_5_predicted_segment_rollback.py`. Suite result: **4 passed** in 80s.

- **Case A** (`test_flag_off_rollback_predicted_segment_none`): flag OFF, others ON → every PlayCard on `.recommendations` + `.recommended_experiments` carries `predicted_segment=None` AND `model_card_ref=None`. Asserts Beauty produced > 0 cards (defensive non-vacuous gate).
- **Case B** (`test_flag_on_populates_model_card_ref_on_beauty`): all flags ON → at least one PlayCard on `.recommendations` carries populated `model_card_ref` with `strategy_used ∈ {BGNBD, CF, SURVIVAL, RFM, RECENCY, None}` and non-empty `fit_status_chain`. predicted_segment.segment_name population is NOT asserted (modal-segment stability floor is fixture-dependent).
- **Case C** (`test_all_ml_flags_off_no_consumer_wiring_state`): all S10-S13 ML flags OFF (including ranking-chain) → `predictive_models == {}`, `cohort_diagnostics == {}`, and `predicted_segment.segment_name is None` on every card.
- **Case D / INDEPENDENCE PIN** (`test_consumer_wiring_runs_independently_when_bgnbd_off`): predicted_segment ON, BG/NBD OFF → `"bgnbd" not in predictive_models`, at least one PlayCard's `model_card_ref` is populated via chain-walk past missing BG/NBD, and `strategy_used != "BGNBD"` on every populated card.

## pinned_sha_ledger.json shape

```json
{
  "_meta": {
    "ticket": "S13-T2.5",
    "captured_date": "2026-05-29",
    "engine_run_json_sha_caveat": "engine_run.json contains wall-clock fit_timestamp values… These shas are NOT byte-stable across re-runs at fixed code; they record the post_s13_t2_5 state at this commit moment only. The load-bearing T2.5 test gates are (1) tests/test_s13_renderer_non_consumption.py (structural briefing.html guarantee) and (2) tests/test_s13_t2_5_predicted_segment_rollback.py (PlayCard typed-slot population contract). This ledger is documentation, not a re-runnable test fixture.",
    "briefing_html_sha_pin": "briefing.html shas ARE byte-stable across re-runs (renderer is deterministic; no wall-clock leaks). identity_holds=true on all 5 fixtures is the load-bearing claim."
  },
  "healthy_beauty_240d": {
    "briefing_html": {"pre_s13": "f8676c9f…", "post_s13_t2_5": "f8676c9f…", "identity_holds": true},
    "engine_run_json": {"pre_s13": "…", "post_s13_t2_5": "…", "sha_changed_as_expected": true, "diff_confined_to": ["recommendations[*].predicted_segment", "recommendations[*].model_card_ref"]}
  },
  ...
}
```

(Full per-fixture content at `tests/fixtures/pinned_sha_ledger.json`.)

## small_store_240d honest framing (Pivot 5 — structural correctness, NOT predictive accuracy)

The dispatch brief noted DS surfaced `small_sm` (== `small_store_240d`)
as **the only fixture where RFM VALIDATED at S12-T1.5 (Spearman=0.93,
coverage=0.106)**, and expected T2.5 to show its
`predicted_segment.segment_name` populated as the first synthetic with
a non-None segment_name.

**Actual T2.5 state on small_store_240d:**
`predicted_segment.segment_name = None`. RFM substrate fit
`fit_status = REFUSED` (n=1087). Chain walked all the way down to
RECENCY terminal. No modal-segment population possible because the RFM
parquet wasn't produced at REFUSED status (the consumer-wiring module
falls back to `predicted_segment=None` when the RFM substrate is
absent/refused).

**Honest framing (DS S13 plan review §G.3, Pivot 5):**
1. **Structural correctness is verified.** The consumer-wiring pass runs, the chain walker emits well-typed `fit_status_chain` + `fit_warnings` with the LOCKED `{LEVEL}:{substrate}` grammar, the modal-segment stability floor is respected (segment_name=None when the upstream substrate is unavailable), and the `RECENCY` terminal is correctly selected as the last-resort fallback.
2. **Predictive accuracy is NOT claimed.** The S12-T1.5 RFM VALIDATED finding on small_sm was a specific historical state; today's small_store_240d run shows RFM=REFUSED. This is NOT a regression introduced by T2.5 (T2.5 only flipped the consumer-wiring flag; T2.5 does not touch RFM fit logic). The substrate-fit shift may be due to (a) ML flag defaults having drifted upward in cascade across S10-S12 atomic flips changing the surrounding pipeline state, (b) the fixture's customer/orders data shape genuinely producing REFUSED at the current RFM Spearman/coverage gates, or (c) a state interaction not previously surfaced. Per Pivot 5, the synthetic-fixture state is NOT a predictive-accuracy claim about real merchants — it is a structural exerciser.
3. **No fix-on-a-guess.** The brief told us to "document why" if the floor or upstream substrate suppresses segment_name. The reason is upstream RFM REFUSED, NOT the modal-segment floor (`n>=50, share>=0.30`). If the founder/DS wants the first synthetic-populated segment_name, that is an upstream substrate-fit calibration question, not a consumer-wiring question, and is out of T2.5 scope.

## Suite status

- `tests/test_s13_t2_5_predicted_segment_rollback.py`: **4 passed** (80s).
- `tests/test_s13_renderer_non_consumption.py`: **2 passed**.
- `tests/test_s13_t2_predicted_segment_population.py`: **10 passed**.
- `tests/test_s13_ml_fit_never_demotes.py`: **5 passed**.
- `tests/test_s13_t1_ranking_strategy_flag.py`: **4 passed**.
- `tests/test_reason_code_precedence_invariant.py`: **4 passed** (no new findings post-flip).
- Combined S13 sweep above: **28 passed in 187s** + **1 separate run of 4 passed in 80s** = **32 passed**.
- Pinned slate regressions (Beauty + Supplements): **29 passed, 2 xpassed**.
- Prior 6 rollback tests with new env override: **22 passed in 447s**.

**Pre-existing failures (NOT introduced by T2.5; explicitly excluded per dispatch brief + CLAUDE.md):**
1. `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` — KI-NEW-U stale S12-T1.5 flag-default-off test.
2. `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` — KI-NEW-U stale S12-T2.5 flag-default-off test.
3. `tests/test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` — pre-existing wall-clock flake.

**No new regressions introduced at T2.5.** The full-suite delta vs T2-close baseline: +1 new test file (renderer non-consumption: 2 tests), +1 new test file (rollback contract: 4 tests), +0 net delta on prior test counts (the 1 flipped test at test_s13_t2_predicted_segment_population.py replaces the inverted assertion in place, not adds a new one).

## Risk assessment

- **briefing.html byte-identity at T2.5 flip:** STRUCTURALLY GUARANTEED via grep pin. If a future commit reads `predicted_segment` or `model_card_ref` from `src/briefing.py`, the renderer non-consumption test fails AND that commit must re-pin briefing.html shas atomically. ZERO risk at T2.5.
- **engine_run.json sha changes:** intentional and confined to `recommendations[*].predicted_segment` + `recommendations[*].model_card_ref` keys. The pinned_sha_ledger.json records the moment-in-time shas with explicit wall-clock caveat — future commits do not need to maintain byte-stability against this ledger (the substrate `fit_timestamp` already breaks byte-stability across re-runs at fixed code).
- **Single-demote-channel invariant (Pivot 7) preserved.** No new code path appends to `engine_run.recommendations` or `engine_run.considered`. The T2.5 flip activates a typed-slot mutation pass that was already structurally compliant at T2.
- **Pivot 5 honesty preserved.** No fake p/effect/CI introduced. The synthetic `predicted_segment.segment_name` outcomes are reported verbatim, including the small_store_240d divergence from the brief's expectation.
- **Q-S13-4 LOCK enforcement still holds.** ML-fit ReasonCodes emit ONLY on `model_card_ref.fit_warnings`. The AST contract test + 5-fixture runtime contract test still pass post-flip.
- **Rollback contract:** REQUIRED test (4 cases A/B/C/D) all green. Operators can switch back to pre-T2.5 behavior via `ENGINE_V2_PLAY_PREDICTED_SEGMENT=false` env override; PlayCard typed slots stay None.
- **scipy<1.13 pin NOT relaxed.** No dependency changes.
- **No fixture / golden touches.** Pivot 5 respected — synthetic CSVs untouched.
- **No merchant-facing copy added.** Pivot 2 / Stop-Coding Line respected.

## Artifacts added

- `tests/test_s13_renderer_non_consumption.py` (NEW) — 2 tests, structural grep pin.
- `tests/test_s13_t2_5_predicted_segment_rollback.py` (NEW) — 4 tests (Cases A/B/C/D).
- `tests/fixtures/pinned_sha_ledger.json` (NEW) — DS Q-S13-2 Option α ledger across 5 fixtures × 2 artifacts.
- `agent_outputs/code-refactor-engineer-s13-t2.5-summary.md` (this file).

## Deviation-check

**Deviation check: none.**

Per CLAUDE.md: founder-locked S13 cadence followed verbatim. Single
atomic commit. No scope expansion (consumer_wiring.py / ranking_strategy.py /
the L1972-2038 wire site UNCHANGED). No band-aids added. No factory
threading or other Option-I migration attempted. No fixture touches.
The renderer non-consumption grep pin is a new file but DS-REQUIRED
per S13 plan review §E.8 (promoted from §L mention to T2.5 acceptance
in the dispatch brief). The pinned_sha_ledger.json is DS-REQUIRED per
Q-S13-2 Option α.

## Recommended commit message

```
S13-T2.5: atomic flip ENGINE_V2_PLAY_PREDICTED_SEGMENT (false -> true) + rollback contract + renderer non-consumption grep pin + pinned_sha_ledger

First intentional engine_run.json schema change in S13. briefing.html
stays byte-identical across all 5 pinned fixtures (structural guarantee
via renderer non-consumption grep pin); only engine_run.json shas
change, confined to recommendations[*].predicted_segment +
recommendations[*].model_card_ref keys.

Changes:

1. src/utils.py L1058: ENGINE_V2_PLAY_PREDICTED_SEGMENT default flipped
   from "false" to "true". Comment block updated with T2.5 atomic-flip
   + ledger + grep-pin rationale.

2. tests/test_s13_renderer_non_consumption.py (NEW) — DS REQUIRED grep
   pin. Asserts neither "predicted_segment" nor "model_card_ref"
   appears in src/briefing.py source bytes. This is the STRUCTURAL
   guarantee behind the briefing.html byte-identity claim.

3. tests/test_s13_t2_5_predicted_segment_rollback.py (NEW) — 4
   rollback cases per DS plan §D-T2.5. Case A (flag-OFF rollback),
   Case B (flag-ON populates model_card_ref on Beauty), Case C (all
   ML flags OFF → no consumer-wiring state), Case D (INDEPENDENCE PIN
   — chain walks past missing BG/NBD without crashing).

4. tests/fixtures/pinned_sha_ledger.json (NEW) — DS Q-S13-2 Option α
   ledger. pre_s13 (flag-OFF) vs post_s13_t2_5 (flag-ON) shas across
   5 fixtures × 2 artifacts. briefing.html identity_holds=true on all
   5; engine_run.json sha changes documented. _meta preamble carries
   explicit wall-clock fit_timestamp caveat.

5. tests/test_s13_t2_predicted_segment_population.py L44-61: T2
   flag-default test inverted in place per S12-T2.5 / S13-T1.5
   Option-a precedent (no KI-NEW-U growth). Renamed to
   test_engine_v2_play_predicted_segment_default_on_after_t2_5.

6. Prior 6 rollback tests (S10-T1.5 / S10-T2.5 / S11-T1.5 / S11-T2.5 /
   S12-T1.5 / S12-T2.5) extended with
   ENGINE_V2_PLAY_PREDICTED_SEGMENT=false env override + S13-T2.5
   rationale comment, mirroring the existing cascade pattern.

Test gates: renderer non-consumption (2p), rollback contract (4p),
T2 unit (10p, flag-default test inverted), ml-fit-never-demotes (5p),
ranking strategy flag (4p), reason code precedence (4p), pinned slate
regressions Beauty + Supplements (29p/2xp), 6 prior rollback tests
with new env override (22p).

Per-fixture predicted_segment state captured verbatim in
agent_outputs/code-refactor-engineer-s13-t2.5-summary.md. All 5
fixtures' upstream substrates currently REFUSED / INSUFFICIENT_DATA
on the synthetic CSVs, so every populated model_card_ref shows
strategy_used=RECENCY (terminal floor) and predicted_segment=None.
small_store_240d outcome divergence from brief's S12-T1.5 expectation
documented honestly per Pivot 5 (structural correctness pinned;
predictive accuracy NOT claimed).

Pre-existing failures excluded per dispatch brief: 2 KI-NEW-U stale
flag-default-off tests + 1 wall-clock flake. No new regressions.

Deviation check: none.
```

## Recommended T3 dispatch context

S13-T3 is the month_2_delta typed slot + lineage-keyed detection per
the S13 plan §E. Suggested dispatch coverage:

1. **Re-read DS T2 review §G nit forwarding.** The dispatch brief
   highlighted this. Surface any T2 process nits the orchestrator
   should pass through to T3 dispatch (e.g., Option II vs Option I
   reversibility note in T2 summary).
2. **Synthetic month-2 fixture introduction** — T2's
   `_PINNED_FIXTURES` list at `tests/test_s13_ml_fit_never_demotes.py`
   was scoped to 5 pinned fixtures per DS §E.1; T3 extends that list
   with the synthetic month-2 fixture.
3. **Lineage-keyed detection** — define the lineage key (per
   audience_definition_id × play_id × store_id or whatever IM/DS
   approves) and store the month_n→month_n+1 delta in a typed slot
   on PlayCard or EngineRun. The Sprint 9 deferred store-profile-as-
   learned-artifact stream stays out of scope (per
   project_beta_no_learning_loop memory).
4. **Avoid changing T2.5 wire site.** The consumer-wiring callsite at
   src/main.py:1972-2038 should remain stable; T3 should add the
   month_2_delta pass either alongside (preferred — new isolated
   module) or in a separate callsite after the consumer-wiring pass.
5. **DO NOT touch the renderer.** briefing.html byte-identity remains
   load-bearing through T3+. The grep pin at
   tests/test_s13_renderer_non_consumption.py would need extension
   if month_2_delta introduces another forbidden field.
6. **Honesty contract:** T3 must NOT introduce hardcoded baselines
   for month_2_delta. If month-1 RFM was REFUSED, month_2_delta
   should be a structural delta (or absent), not a fabricated value.

## Notes

- The S13-T2.5 atomic flip preserves the full DS-locked acceptance contract from the dispatch brief.
- The brief's expectation that small_sm would carry a populated `predicted_segment.segment_name` at T2.5 did NOT hold; documented honestly with upstream cause analysis. This is a structural-correctness finding, not a regression — T2.5 did not change RFM fit logic.
- Surface-first discipline (T2 process nit): no wire-site changes were considered, so no surface needed. The flag flip + ledger + grep pin + rollback test composition followed the dispatch brief verbatim.
