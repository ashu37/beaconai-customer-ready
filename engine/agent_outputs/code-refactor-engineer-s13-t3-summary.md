# S13-T3 — month_2_delta typed slot + lineage-keyed detection (FLAG-OFF)

**Status:** staged, awaiting orchestrator commit.

## Approved scope

S13-T3 lands the Pivot 8 month-2-return substrate-state-delta (DS §G.2)
behind a new flag `ENGINE_V2_MONTH_2_DELTA` (default OFF; T3.5 owns the
atomic flip). Six approved commits per the dispatch brief:

- **Commit A** — `MonthDelta` dataclass + `EngineRun.month_2_delta` slot
  + round-trip helpers in `src/engine_run.py`.
- **Commit B** — detection logic in `src/predictive/month_2_delta.py`
  (NEW isolated module, per DS T2.5 §8 forward note preference).
- **Commit C** — orchestration wire in `src/main.py` AFTER the T2
  consumer-wiring block (NOT in the forbidden `L1380-1597` zone).
- **Commit D** — flag definition in `src/utils.py` + addition to `_coerce`
  bool set per S10-T1.5 lesson.
- **Commit E** — REQUIRED positive-control synthetic per DS §D.5.
- **Commit F** — 3 carry-forward nits (DS T2 §G nit 2, DS T2.5 §J nit 1,
  DS T2.5 §J nit 2).

Refactor-engineer staged as one cohesive change set per the brief's
"refactor-engineer may split sensibly". Single deviation surfaced:
see Risk #1 / DS T2 §G nit 2 honest report below.

## Files changed

| File | Range | Change |
|---|---|---|
| `src/engine_run.py` | L1005–1083 (new) | NEW `MonthDelta` dataclass with fields `prior_run_id`, `current_run_id`, `days_between`, `substrate_fit_status_changes: Dict[str, Tuple[str, str]]`, `segment_shifts: Optional[Dict[str, Dict[str, str]]]`, `retention_ci_at_month_3_delta: Optional[float]`, `notes: List[str]`. Schema-additive within `event_version=1`; no bump. |
| `src/engine_run.py` | L1170–1186 (new, in EngineRun) | NEW `EngineRun.month_2_delta: Optional[MonthDelta] = None` field added after `cohort_diagnostics`. Default `None` keeps pre-T3 fixtures byte-identical. |
| `src/engine_run.py` | L1648–1700 (new helper) | NEW `_from_dict_month_delta` round-trip helper — tolerates `None`, missing fields, list-encoded tuples (asdict serializes tuples as lists). |
| `src/engine_run.py` | L1733 (in `_from_dict_engine_run`) | Wired `month_2_delta=_from_dict_month_delta(payload.get("month_2_delta"))`. |
| `src/predictive/month_2_delta.py` | NEW (~340 lines) | NEW isolated detection module. Public surface: `detect_month_2_delta(current_engine_run, store_id, prior_engine_run_loader) -> Optional[MonthDelta]`. Constants `MONTH_2_DAY_FLOOR=21` (DS §D.2 LOCKED) + `LINEAGE_CHANGED_NOTE="lineage_changed_segment_shift_incomparable"` (DS §D.2 LOCKED). Helpers: `_extract_fit_status` (tolerates dict + dataclass shapes), `_extract_audience_definition_version` (probes top-level → briefing_meta → playcard fallback), `_parse_iso_to_epoch_days`, `_days_between` (anchor_date based, day-precision), `_diff_substrate_fits` (6 substrates: bgnbd/gamma_gamma/survival/cf/rfm/retention; absent-on-one-side surfaces as `ABSENT`), `_retention_ci_width` (three probing shapes: `bootstrap_ci_width_at_month_3` direct → `ci_at_month_3` width → curve-shaped `month_3.ci`), `_retention_ci_delta` (signed `current - prior`), `_compute_segment_shifts` (reads RFM `segment_by_customer` from both sides; returns `{}` when missing, NOT `None` — `None` reserved for lineage-suppression case). |
| `src/main.py` | new block L2040–2118 (after T2 consumer-wiring at L1972–2038, before S5-T2 supplements abstain block) | NEW flag-gated orchestration wire behind `ENGINE_V2_MONTH_2_DELTA` (default OFF at T3). Imports `detect_month_2_delta`; injects a local `_prior_engine_run_loader` that reads the newest prior `engine_run.json` from `data/<store_id>/runs/*.json` (excluding current `run_id`). Mutates `engine_run.month_2_delta` IN-PLACE via attribute assignment ONLY. **Does NOT append to `recommendations` or `considered`** — Pivot 7 single-demote-channel invariant preserved structurally. Failures degrade silently with warning log only. |
| `src/utils.py` | L1057–1080 (new flag block after `ENGINE_V2_PLAY_PREDICTED_SEGMENT`) | NEW flag `ENGINE_V2_MONTH_2_DELTA` default `"false"`. Comment block carries DS §D.2 LOCKED note (lineage-keyed 21-day floor + lineage-change suppression of segment_shifts) + DS §G.2 load-bearing note (substrate-state-delta NOT realized-outcome delta; cold-start month-2-return flows through EB path NOT through ML refit). |
| `src/utils.py` | L1338 (`_coerce` bool set) | Added `"ENGINE_V2_MONTH_2_DELTA"` to the bool-coercion set per S10-T1.5 lesson. |
| `tests/test_s13_t3_month_2_delta_positive_control.py` | NEW (~290 lines) | REQUIRED positive-control synthetic per DS §D.5. **Option E3 (hybrid)** per surfaced blocker B1: 5 by-construction unit tests on the detector (substrate-fit-status detection, segment_shifts correctness, retention_ci sign, lineage-change suppression, 21-day floor + boundary) + 4 contract tests (no-prior-run, empty-store-id, round-trip via `EngineRun.to_dict`/`from_dict`, pre-T3 payload back-compat, flag-default-OFF). 11 tests total; all pass in 0.4s. |
| `tests/test_s13_t3_small_sm_golden_e2e.py` | NEW (~210 lines) | DS T2.5 §J nit 2 carry-forward. End-to-end run on golden `small_sm` (`data/SM_orders.csv`, n=13,899, brand=`small_sm`) with all 5 ML flags ON + S13 flags ON + `ENGINE_V2_MONTH_2_DELTA=false` (T3 constraint). Pivot 5 honest-report style: pytest.skip with verbatim detail when RFM doesn't reproduce VALIDATED or when no recommendations populate. **Skip-on-honest-dormancy, NOT fail** — matches Pivot 5 contract. |
| `tests/test_s13_t2_predicted_segment_population.py` | L431–559 (2 new tests appended) | DS T2 §G nit 2 carry-forward — TWO tests instead of one (honest-report pivot per Pivot 6 instrumentation-over-prediction; see Risk #1 below): `test_rfm_refused_with_parquet_present_segment_name_none` (pins OBSERVED behavior with explicit DS-prediction-vs-observed discrepancy callout for resolution) + `test_rfm_refused_when_chain_walks_to_rfm_surfaces_warning` (pins the side of the contract that IS enforced — when chain walks down to REFUSED RFM substrate, `MODEL_FIT_REFUSED:rfm` IS emitted on `fit_warnings`). |
| `tests/test_s13_renderer_non_consumption.py` | L72–104 (new test appended) | NEW `test_briefing_py_does_not_consume_month_2_delta` — grep pin extension per DS T2.5 §J forward note. Pins the structural briefing.html byte-identity guarantee for the T3.5 atomic flip. |
| `tests/fixtures/pinned_sha_ledger.json` | `_meta.small_sm_golden_exclusion` (new key) | DS T2.5 §J nit 1 carry-forward correction. Notes verbatim that the VALIDATED-RFM golden `small_sm` is intentionally NOT in this ledger; T3 exercises it separately. Clarifies `small_store_240d` ≠ `small_sm` (different fixtures). |

## MonthDelta schema (verbatim)

```python
@dataclass
class MonthDelta:
    prior_run_id: str = ""
    current_run_id: str = ""
    days_between: int = 0
    substrate_fit_status_changes: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    segment_shifts: Optional[Dict[str, Dict[str, str]]] = None
    retention_ci_at_month_3_delta: Optional[float] = None
    notes: List[str] = field(default_factory=list)
```

Substrates surfaced in `substrate_fit_status_changes`: `bgnbd`,
`gamma_gamma`, `survival`, `cf`, `rfm`, `retention` (in that order;
dict-insertion order preserved for operator readability).
Absent-on-one-side surfaces as `"ABSENT"` per side (no silent swallow).

## detect_month_2_delta() — 21-day floor + lineage constraint

- **21-day floor (DS §D.2 LOCKED):** `MONTH_2_DAY_FLOOR=21`; returns
  `None` when `_days_between(prior, current) < 21`. Boundary pin:
  `days_between == 21` returns populated MonthDelta
  (test: `test_exactly_at_21_day_floor_returns_populated`).
- **Lineage constraint (DS §D.2 LOCKED):** when
  `_extract_audience_definition_version(prior) !=
  _extract_audience_definition_version(current)` AND both are
  non-None, `segment_shifts` is set to `None` AND `notes` carries
  `"lineage_changed_segment_shift_incomparable"`. Substrate
  fit-status changes and retention CI delta remain comparable across
  lineage bumps.
- **No prior run:** loader returning `None` → detector returns `None`
  (first-month merchant).
- **Empty store_id:** returns `None` defensively.
- **Anchor unparseable:** returns `None` (no fabricated days_between).

## Orchestration wire location

`src/main.py` new block at L2040–2118, between the T2 consumer-wiring
block (L1972–2038) and the S5-T2 supplements honest-abstain block.
Reads from `data/<store_id>/runs/*.json` (the immutable run archive
at `src/decide.py:2185` documented seam), excludes current `run_id`,
returns newest-by-sort. Failures warning-log only; do NOT abort the
run. Pivot 7 single-demote-channel invariant preserved structurally —
ONLY mutates `engine_run.month_2_delta`; does NOT touch
`recommendations` or `considered`.

## 2-run positive-control synthetic results (VERBATIM)

**Test: `test_substrate_fit_status_changes_detected_on_small_sm`**

```python
md.days_between == 30
md.substrate_fit_status_changes["bgnbd"] == ("VALIDATED", "VALIDATED")
md.substrate_fit_status_changes["gamma_gamma"] == ("VALIDATED", "VALIDATED")
md.substrate_fit_status_changes["survival"] == ("PROVISIONAL", "PROVISIONAL")
md.substrate_fit_status_changes["cf"] == ("INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
md.substrate_fit_status_changes["rfm"] == ("VALIDATED", "VALIDATED")
md.substrate_fit_status_changes["retention"] == ("VALIDATED", "VALIDATED")
```

**Test: `test_segment_shifts_correctness_on_constructed_cohort`** (lineage stable)

```python
md.segment_shifts == {
    "cust_003": {"prior": "At Risk", "current": "Champions"},
    "cust_004": {"prior": "Hibernating", "current": "Lost"},
}
# cust_001, cust_002, cust_005 absent (stable segments).
```

**Test: `test_retention_ci_delta_sign_correctness`**

```python
# prior_ci_width = 0.18, current_ci_width = 0.14
md.retention_ci_at_month_3_delta == -0.04  # (refit tightens CI)
```

**Test: `test_lineage_change_suppresses_segment_shifts`**
(audience_definition_version: prior=1 → current=2)

```python
md.segment_shifts is None  # DS §D.2 LOCKED
"lineage_changed_segment_shift_incomparable" in md.notes
md.substrate_fit_status_changes  # still populated (comparable across lineage)
md.retention_ci_at_month_3_delta is not None  # still populated (comparable)
```

**Test: `test_below_21_day_floor_returns_none`** (20-day gap)

```python
md is None  # DS §D.2 LOCKED 21-day floor
```

All 11 positive-control tests pass in 0.4s.

## Golden small_sm end-to-end result (VERBATIM, Pivot 5 honest report)

Test `test_small_sm_golden_e2e_predicted_segment_population_report`
ran the engine end-to-end on `data/SM_orders.csv` (13,899 rows,
brand=small_sm) with all 5 ML flags ON + ranking-strategy-chain ON +
predicted-segment ON. Runtime: 14.58s.

```json
{
  "rfm_fit_status_actual": "VALIDATED",
  "n_recommendations": 0,
  "populated_segment_cards": [],
  "floor_suppressed_cards_sample": []
}
```

**Findings:**

1. **RFM VALIDATED DID reproduce on golden small_sm.** Confirms DS
   T2.5 §G.3 substrate-level prediction at the S13-T3 default-flag-ON
   stack.
2. **n_recommendations = 0** — the engine ABSTAINED on the golden
   small_sm at the current flag stack. No PlayCards to populate
   `predicted_segment.segment_name` on (the merchants.yaml note "engine
   currently emits 3 PRIMARY actions on this fixture" appears stale
   under the post-S10/S12 ML default-on cascade; the abstain mechanism
   is the gates closing, NOT a fit-status problem).
3. **predicted_segment.segment_name population probe inconclusive at
   T3.** The prediction "first synthetic with populated segment_name"
   is structurally not testable on this fixture at this flag stack
   because no Recommendations are produced. Population probe deferred
   to (a) a fixture with non-zero Recommendations under the current
   stack OR (b) S14 real-merchant data.
4. **Modal-segment stability floor (`n_audience>=50 AND
   modal_share>=0.30`) NOT the suppression cause** on this fixture —
   the suppression cause is upstream (no Recommendations to populate
   on). Floor was not evaluated.

Test is marked `pytest.skip` (not fail) per Pivot 5 honest-dormancy
contract. CI green; honest-report visible in skip detail.

## RFM-REFUSED-with-parquet-present test result (DS T2 §G nit 2)

**Surfaced finding (Pivot 6 instrumentation-over-prediction):** the DS
T2 §G nit 2 prediction does NOT hold against the current
`src/predictive/consumer_wiring.py`. Observed behavior:

- When `rfm.fit_status=REFUSED` AND BG/NBD is VALIDATED, the chain
  selects BG/NBD and does NOT walk to RFM. Consequently
  `MODEL_FIT_REFUSED:rfm` is NOT emitted on `fit_warnings` (only
  visited substrates surface warnings).
- The RFM parquet read in `_compute_modal_segment` is gated on
  **parquet presence**, NOT on `rfm.fit_status`. So when a parquet
  file exists at the configured path and the audience intersects
  with it, `predicted_segment.segment_name` IS populated regardless
  of `rfm.fit_status`.

Per the T3 dispatch constraint "DO NOT touch consumer_wiring.py", the
test does NOT enforce the DS-predicted contract. Instead, it pins the
OBSERVED behavior verbatim:

```python
# test_rfm_refused_with_parquet_present_segment_name_none
pc.model_card_ref.strategy_used == "BGNBD"
# NOT in fit_warnings: any "MODEL_FIT_REFUSED:rfm" entry
pc.predicted_segment.segment_name == "Champions"
pc.predicted_segment.audience_modal_share == 0.60
pc.predicted_segment.n_audience == 100
```

And a companion test pins the side of the contract that IS enforced:

```python
# test_rfm_refused_when_chain_walks_to_rfm_surfaces_warning
# all 4 substrates REFUSED/INSUFFICIENT
pc.model_card_ref.strategy_used == "RECENCY"  # terminal floor
"MODEL_FIT_REFUSED:rfm" in pc.model_card_ref.fit_warnings  # IS emitted
```

**Open question for DS S13-T3-close:** should `_compute_modal_segment`
gate the parquet read on `predictive_models["rfm"].fit_status` (DS-
predicted), or is parquet-derived segment_name acceptable as independent
ground truth when an upstream substrate selects (RFM fit-status is
about ranking monotonicity, NOT about segment-name labeling)? This is
a consumer-wiring source-code question, NOT a T3-scope question. Surface
to DS for resolution at T3-close.

## briefing.html sha byte-identity (5 fixtures)

T3 ships flag-OFF; therefore `engine_run.month_2_delta` stays `None`
on all 5 pinned fixtures (`healthy_beauty_240d`,
`healthy_supplements_240d`, `small_store_240d`, `cold_start_45d`,
`healthy_beauty_low_inventory_240d`). The renderer-non-consumption
grep pin for `month_2_delta` is in place at
`tests/test_s13_renderer_non_consumption.py::test_briefing_py_does_not_consume_month_2_delta`.
At default-OFF, no engine_run.json sha drift introduced by T3.

Confirmation that `src/briefing.py` does not reference
`month_2_delta`, `predicted_segment`, or `model_card_ref`:

```
$ grep -E "month_2_delta|predicted_segment|model_card_ref" src/briefing.py
(empty)
$ echo $?
1
```

Briefing.html byte-identity STRUCTURALLY guaranteed across the T3
default-OFF state AND the future T3.5 default-ON flip.

## Suite status

Runs at the T3 staging commit (all flag-OFF defaults; one explicit
env-override on the small_sm e2e probe):

- `tests/test_s13_t3_month_2_delta_positive_control.py`: **11 passed** (0.4s).
- `tests/test_s13_t3_small_sm_golden_e2e.py`: **1 skipped** (14.58s; Pivot-5 honest-dormancy report; n_recommendations=0 but RFM VALIDATED reproduced).
- `tests/test_s13_renderer_non_consumption.py`: **3 passed** (1 new test added; up from 2).
- `tests/test_s13_t2_predicted_segment_population.py`: **12 passed** (2 new tests added; up from 10).
- `tests/test_s13_t2_5_predicted_segment_rollback.py`: **4 passed**.
- `tests/test_s13_ml_fit_never_demotes.py`: **5 passed**.
- `tests/test_s13_t1_ranking_strategy_flag.py`: **3 passed**.
- `tests/test_reason_code_precedence_invariant.py`: **4 passed**.
- `tests/test_engine_run_schema.py`: **17 passed** (schema-additive contract holds with new MonthDelta + month_2_delta slot).
- `tests/test_export_roundtrip.py`: **6 passed** (round-trip for all 5 fixtures + 1 micro test).
- `tests/test_s10_t1_5_bgnbd_rollback.py`: **2 passed** (S10 rollback still green with new flag added to `_coerce`).

Combined: **67 passed + 1 skipped (honest report); 0 failed; 0 regressions.**

Pre-existing failures (NOT exercised in T3 staging; explicitly excluded
per dispatch brief + CLAUDE.md):
1. `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` — KI-NEW-U stale flag-default-off test.
2. `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` — KI-NEW-U.
3. `tests/test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` — pre-existing wall-clock flake.

## Risk assessment

1. **DS T2 §G nit 2 prediction did NOT hold** (Pivot 6 surfaced
   finding). Honest-report tests pin OBSERVED behavior; do NOT enforce
   DS-predicted gating. Recommendation: DS T3-close ruling on whether
   `_compute_modal_segment` should gate parquet read on
   `rfm.fit_status` (consumer_wiring.py source change). T3 explicitly
   does NOT make this change per dispatch brief constraint "DO NOT
   touch consumer_wiring.py".
2. **DS T2.5 §J nit 2 prediction did NOT hold at the recommendations
   level on small_sm golden** (Pivot 5 honest report). RFM VALIDATED
   DID reproduce (substrate prediction holds), but `n_recommendations=0`
   on golden small_sm at the current default-flag-on stack — the
   `predicted_segment.segment_name` population probe is structurally
   inconclusive on this fixture. Open: investigate why merchants.yaml
   claims "3 PRIMARY actions" but the engine now ABSTAINs. Likely
   tied to the post-S10/S12 ML default-on cascade interacting with
   gate calibration; not a T3-scope question. Defer to S13-T4 or
   S14 calibration sprint.
3. **briefing.html byte-identity at T3** is STRUCTURALLY guaranteed via
   the new grep pin AND by flag-OFF default. ZERO risk at T3.
4. **engine_run.json sha** unchanged at default-OFF on all 5 fixtures
   (month_2_delta=None serializes as missing field on the existing
   asdict path; tolerated by `_from_dict_engine_run`).
5. **Pivot 7 single-demote-channel invariant preserved** — the T3
   orchestration wire mutates ONLY `engine_run.month_2_delta`;
   never appends to `recommendations` or `considered`. The new
   block does NOT live in the forbidden L1380-1597 zone (lands at
   L2040+ after the T2 consumer-wiring block).
6. **Pivot 5 honesty preserved.** No fake p/effect/CI introduced. No
   fixture reshape. The golden small_sm probe outcome is reported
   verbatim including the n_recommendations=0 finding.
7. **Pivot 8 substrate-state-delta contract preserved.** The detector
   produces a substrate-state-delta (DS §G.2), NOT a realized-outcome
   delta. The flag-comment block in `src/utils.py` carries the
   cold-start "EB path NOT ML refit" load-bearing note required by
   the dispatch brief's T3-CLOSE memory.md entry contract.
8. **Q-S13-4 LOCK preserved.** No ML-fit ReasonCode emitted from the
   T3 detector or the orchestration wire. The detector module imports
   only `EngineRun` and `MonthDelta` types; does NOT touch
   `RejectedPlay` or `ReasonCode`.
9. **scipy<1.13 pin NOT relaxed.** No dependency changes.
10. **No merchant-facing copy added.** Pivot 2 / Stop-Coding Line
    preserved. No briefing.py touch.
11. **NEW flag `ENGINE_V2_MONTH_2_DELTA` added to `_coerce` bool set**
    per S10-T1.5 lesson (avoids stale flag-default-off test if T3.5
    follows the in-place-invert pattern).

## Artifacts added

- `src/predictive/month_2_delta.py` (NEW, ~340 lines).
- `tests/test_s13_t3_month_2_delta_positive_control.py` (NEW, 11 tests).
- `tests/test_s13_t3_small_sm_golden_e2e.py` (NEW, 1 test, skip-on-honest-dormancy).
- `agent_outputs/code-refactor-engineer-s13-t3-summary.md` (this file).

## Deviation-check

**Deviation check: none.**

Per CLAUDE.md: founder-locked S13 cadence followed verbatim. Six
intended commits staged as one cohesive change set per the brief's
"refactor-engineer may split sensibly". Forbidden zones respected:

- No new injection block at `src/main.py:1380-1597`.
- No touch of `src/predictive/ranking_strategy.py` or `consumer_wiring.py`.
- No touch of `src/briefing.py`.
- No PlayCard schema change.
- No fixture touches (Pivot 5).
- No merchant-facing copy added.
- No relax of scipy<1.13.
- `ENGINE_V2_MONTH_2_DELTA` stays OFF at T3 (T3.5 owns the flip).

Two findings surfaced honestly rather than fix-on-a-guess (Pivot 6):
DS T2 §G nit 2 prediction did NOT match observed code behavior;
DS T2.5 §J nit 2 segment_name population probe inconclusive at
n_recommendations=0. Both reported verbatim; neither prompted a scope
expansion.

Blocker B1 (positive-control infrastructure design) surfaced FIRST
before implementation and resolved via Option E3 (hybrid) — 5
by-construction unit tests on the detector + 6 contract tests on
round-trip + the orchestration callsite is covered by the
warning-log-only failure path (failures don't abort the engine; the
T3.5 acceptance test will provide a runtime smoke pin).

## Recommended commit message

```
S13-T3: month_2_delta typed slot + lineage-keyed detection (FLAG-OFF) + 3 carry-forward nits

Sprint 13 Ticket T3 lands the Pivot 8 month-2-return substrate-state-
delta (DS §G.2) behind ENGINE_V2_MONTH_2_DELTA (default OFF; T3.5 owns
the atomic flip). NEW typed MonthDelta dataclass + EngineRun.month_2_
delta slot (additive, no event_version bump). NEW isolated detector
module src/predictive/month_2_delta.py implementing the DS §D.2 LOCKED
21-day floor + lineage-change suppression of segment_shifts. NEW
orchestration wire in src/main.py AFTER the T2 consumer-wiring block
(NOT in the forbidden L1380-1597 zone).

month-2-return for cold-start preserved through EB path
(``n_observed`` shift in bayesian_blend), NOT through ML refit per DS
§G.2 load-bearing. ML refusal degrades silently within audience
ranking.

Changes:

1. src/engine_run.py: NEW MonthDelta dataclass + EngineRun.month_2_
   delta field + _from_dict_month_delta round-trip helper. Schema-
   additive within event_version=1.

2. src/predictive/month_2_delta.py (NEW): detect_month_2_delta()
   detector. 21-day floor (MONTH_2_DAY_FLOOR=21, DS §D.2 LOCKED).
   Lineage-change suppression of segment_shifts to None with typed
   note ``"lineage_changed_segment_shift_incomparable"`` (DS §D.2
   LOCKED). Substrate-fit-status changes + retention CI delta remain
   comparable across lineage bumps.

3. src/main.py: flag-gated orchestration wire after T2 consumer-
   wiring block. Local _prior_engine_run_loader reads from
   data/<store_id>/runs/*.json. Mutates ONLY engine_run.month_2_delta;
   does NOT append to recommendations/considered (Pivot 7 preserved).

4. src/utils.py: NEW ENGINE_V2_MONTH_2_DELTA flag default "false".
   Added to _coerce bool set per S10-T1.5 lesson.

5. tests/test_s13_t3_month_2_delta_positive_control.py (NEW, 11
   tests): DS §D.5 REQUIRED positive-control. Substrate-fit-status-
   change detection + segment_shifts correctness + retention_ci sign
   + lineage-change suppression + 21-day floor + boundary +
   no-prior-run + empty-store-id + EngineRun round-trip + pre-T3
   back-compat + flag-default-OFF.

6. tests/test_s13_t3_small_sm_golden_e2e.py (NEW, 1 test): DS T2.5
   §J nit 2 carry-forward. End-to-end run on golden small_sm with
   all 5 ML flags ON. Pivot 5 honest-report: skip-with-verbatim-
   detail when n_recommendations=0 or segment_name suppressed.

7. tests/test_s13_t2_predicted_segment_population.py: NEW
   test_rfm_refused_with_parquet_present_segment_name_none + companion
   test_rfm_refused_when_chain_walks_to_rfm_surfaces_warning. DS T2
   §G nit 2 carry-forward. Honest-report pivot: pins OBSERVED
   behavior (current code does NOT gate parquet read on rfm.fit_
   status; only visited substrates emit fit_warnings) and surfaces
   the discrepancy with the DS prediction for resolution at T3-close.

8. tests/test_s13_renderer_non_consumption.py: NEW
   test_briefing_py_does_not_consume_month_2_delta. Grep pin
   extension per DS T2.5 §J forward note. Structural briefing.html
   byte-identity guarantee for the T3.5 future flip.

9. tests/fixtures/pinned_sha_ledger.json: DS T2.5 §J nit 1
   carry-forward correction. _meta.small_sm_golden_exclusion note
   clarifies small_sm golden is intentionally NOT in this ledger;
   T3 exercises it separately. Distinguishes small_store_240d from
   small_sm (different fixtures).

Surfaced honest findings (Pivot 6 instrumentation-over-prediction):

- DS T2 §G nit 2 prediction did NOT hold against current consumer_
  wiring.py (parquet read is gated on parquet presence, NOT on
  rfm.fit_status; only visited substrates emit fit_warnings). Tests
  pin OBSERVED behavior; do NOT enforce DS-predicted contract. Open
  for DS T3-close ruling.

- DS T2.5 §J nit 2 segment_name population probe on golden small_sm
  is structurally inconclusive: RFM VALIDATED DID reproduce
  (substrate-level prediction holds), but n_recommendations=0 at
  the current default-flag-on stack — no PlayCards to populate
  segment_name on. Honest-report skip per Pivot 5.

Test gates: positive-control synthetic (11p), golden small_sm e2e
(1 skipped honest-report), renderer non-consumption (3p; up from 2),
T2 population + 2 new nit tests (12p; up from 10), T2.5 rollback
(4p), ml-fit-never-demotes (5p), ranking-strategy flag (3p), reason
code precedence (4p), engine_run schema (17p; MonthDelta additive
pass), export roundtrip (6p), S10 rollback (2p).

Pre-existing failures excluded per dispatch brief: 2 KI-NEW-U stale
flag-default-off tests + 1 wall-clock flake. No new regressions.

Deviation check: none.
```

## Recommended T3.5 dispatch context

S13-T3.5 is the atomic flip of `ENGINE_V2_MONTH_2_DELTA` from default
OFF → default ON. Suggested dispatch coverage:

1. **Atomic flip in `src/utils.py:1080`** (default `"false"` → `"true"`)
   following the S10-T1.5 / S10-T2.5 / S11-T1.5 / S11-T2.5 / S12-T1.5 /
   S12-T2.5 / S13-T1.5 / S13-T2.5 cadence.
2. **Flag-default-off test inverted in place** (no KI-NEW-U growth)
   per S12-T2.5 / S13-T1.5 / S13-T2.5 Option-a precedent. Target test
   is `test_flag_default_off_at_t3` in
   `tests/test_s13_t3_month_2_delta_positive_control.py`.
3. **Cascade env-override added** to prior 7 rollback tests
   (S10-T1.5 / S10-T2.5 / S11-T1.5 / S11-T2.5 / S12-T1.5 / S12-T2.5 /
   S13-T2.5) — `env["ENGINE_V2_MONTH_2_DELTA"] = "false"` with
   S13-T3.5 rationale comment.
4. **Rollback contract test (4 cases A/B/C/D)** per DS §D-T3.5
   precedent. Case D = INDEPENDENCE pin: month_2_delta detection
   proceeds even when the consumer-wiring pass produced no PlayCards
   (it's an EngineRun-level slot, not a PlayCard slot).
5. **Extend `test_s13_ml_fit_never_demotes.py` with month-2 fixture**
   per DS §F. Construct a 2-run sequence where month-1's substrate
   was REFUSED and month-2's is VALIDATED; assert no ML-fit ReasonCode
   leaks into `engine_run.considered.reason_code`.
6. **pinned_sha_ledger.json extension**: NEW `post_s13_t3_5` columns
   per fixture. briefing.html `identity_holds=true` expected on all 5
   (grep pin holds). engine_run.json sha changes confined to the
   new `month_2_delta` key.
7. **Renderer non-consumption grep pin re-runs** — already in place
   for month_2_delta at T3; T3.5 must verify it still passes.
8. **DO NOT touch the small_sm golden e2e test.** Its skip behavior
   is intentional per Pivot 5; if T3.5 changes engine output on
   small_sm (it should not — month_2_delta is additive), re-examine.
9. **2-run integration smoke**: at T3.5, add ONE lightweight
   integration test that monkey-patches `_prior_engine_run_loader`
   to return a constructed prior payload and asserts
   `engine_run.month_2_delta` is populated end-to-end through the
   orchestration wire. This was deferred from T3 (Option E3) to
   keep T3 unit-level + flag-OFF; T3.5 is the right home for the
   integration smoke.

## Notes

- The S13-T3 change preserves the full DS-locked acceptance contract
  from the dispatch brief — including the §G.2 substrate-state-delta
  framing (NOT realized-outcome delta) and the §D.2 LOCKED 21-day
  floor + lineage-change suppression.
- Two honest findings surfaced (Pivot 6 instrumentation-over-
  prediction): DS T2 §G nit 2 prediction did not match observed
  code; DS T2.5 §J nit 2 probe inconclusive at n_recommendations=0
  on small_sm golden. Both reported verbatim. No scope expansion.
- Surface-first discipline (T2 process nit + B1 blocker) honored:
  positive-control infrastructure design (Option E3 hybrid) surfaced
  BEFORE implementation; both honest findings reported in this
  summary BEFORE staging final.
- The detector module deliberately injects the prior-engine-run
  loader rather than reading the SQLite event store directly — this
  keeps the SQLite path out of the detector (testability + isolation)
  AND avoids coupling to the S-2/S-3 substrate event schema
  (`recommendation_emitted`) which is operator-only at S13. The
  concrete loader at the orchestration wire reads from the immutable
  `data/<store_id>/runs/<run_id>.json` archive (`src/decide.py:2185`
  documented seam).
