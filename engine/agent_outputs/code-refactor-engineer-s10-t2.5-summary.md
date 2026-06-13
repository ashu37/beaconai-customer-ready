# S10-T2.5 — Gamma-Gamma atomic flip + orchestration wire + rollback contract

**Date:** 2026-05-26
**Ticket:** S10-T2.5 — `ENGINE_V2_ML_GAMMA_GAMMA` atomic ON + `fit_gamma_gamma` wired into `src/main.py` + rollback contract test
**Branch:** `post-6b-restructured-roadmap`
**Engineer:** code-refactor-engineer
**Status:** STAGED (single atomic commit per S7.6 / S8 / T1.5 cadence — orchestrator commits)
**Deviation check:** none.

---

## 1. Approved scope (restated)

DS-locked Option γ (extended to G-G, 2026-05-26): atomically flip
`ENGINE_V2_ML_GAMMA_GAMMA` default ON, wire `fit_gamma_gamma` into
orchestration immediately after the BG/NBD block, accept honest 5/5
REFUSED-via-chained-refusal outcome on synthetic pinned fixtures (BG/NBD
already REFUSED or INSUFFICIENT_DATA on every one, so G-G short-circuits
per IM plan §C.2). Pivot 5 load-bearing — no fixture reshape, no new
VALIDATED-coverage fixture. Real VALIDATED evidence at S14 from real
merchant data.

Hard gates (all met):
1. `briefing.html` byte-identity across all 5 pinned fixtures.
2. No engine_run.json byte-pin contracts exist (verified at T1.5,
   re-confirmed) — additive `predictive_models["gamma_gamma"]` payload
   lands free.
3. Rollback contract: `ENGINE_V2_ML_GAMMA_GAMMA=false` reproduces the
   pre-T2.5 shape — `"gamma_gamma"` absent from `predictive_models`.
4. PlayCard.predicted_segment / model_card_ref stay `None` — S13 wires
   the populating producers, not T2.5.
5. Single-demote-channel invariant preserved — writes only to
   `engine_run.predictive_models["gamma_gamma"]`, never to
   `recommendations`.
6. NO G-G parquet artifacts written (all 5 chained-refused; parquet
   write branch gated on `{VALIDATED, PROVISIONAL}` per
   `src/predictive/gamma_gamma.py:722-730`).

---

## 2. Patch summary

| Action | File | Line ranges | Notes |
|---|---|---|---|
| MODIFIED | `src/utils.py` | L875-877 | `ENGINE_V2_ML_GAMMA_GAMMA` default flipped `"false"` → `"true"`. Already in `_coerce` bool set at L1156 (T2 pre-emptively added per T1.5 lesson) — no change there. |
| MODIFIED | `src/main.py` | L1003-1041 | New PREDICTIVE_FIT orchestration block, guarded by `cfg["ENGINE_V2_ML_GAMMA_GAMMA"]`. Placed IMMEDIATELY after the BG/NBD block (post-L1001), BEFORE guardrails. Builds the G-G orders frame from `g[["customer_id", "Created at", "net_sales"]]` (per-order monetary value), reads `engine_run.predictive_models.get("bgnbd")` as the chained-refusal input, calls `fit_gamma_gamma(orders, profile, bgnbd_card, store_id=..., data_dir=...)` → `ModelCard`. Writes via `dataclasses.replace`. Single try/except wrapper for safety (matches BG/NBD precedent immediately above). |
| MODIFIED | `tests/test_determinism_cross_run.py` | L99-118 | Added `"predictive_models.gamma_gamma.fit_timestamp"` to `_NESTED_NORMALIZED_PATHS` with rationale comment. Mirrors the T1.5 BG/NBD `fit_timestamp` normalization. fit_timestamp is the only run-varying field on the G-G ModelCard. |
| MODIFIED | `tests/test_s10_t1_5_bgnbd_rollback.py` | `_run_and_load` | Now explicitly sets `ENGINE_V2_ML_GAMMA_GAMMA=false`. Without this, the T1.5 rollback assertion `predictive_models == {}` would fail because T2.5's flip makes G-G default-ON. Necessary test contract update: T1.5 rollback test continues to pin BG/NBD-rollback specifically; T2.5's own rollback test pins G-G-rollback independently. |
| MODIFIED | `tests/test_s10_t2_gamma_gamma_fit.py` | L352-365 | Renamed `test_flag_default_off` → `test_flag_default_on_post_t2_5`. Assertion flipped from `is False` to `is True`. T2 was a substrate-only ship at flag-OFF; T2.5 is the atomic flip. |
| NEW | `tests/test_s10_t2_5_gamma_gamma_rollback.py` | full file | Four harness-level tests (see §6). |
| NEW | `agent_outputs/code-refactor-engineer-s10-t2.5-summary.md` | this file | T2.5 receipt. |

No other files changed. No edits to `src/decide.py`, `src/sizing.py`,
`src/engine_run.py` (ReasonCode), PlayCard, briefing.html / renderer,
guardrails, or `apply_guardrails*`.

---

## 3. Per-fixture G-G fit_status (5 fixtures, ENGINE_V2_ML_GAMMA_GAMMA=true, T2.5 default)

Per IM plan §C.2 (chained-refusal): when the same-run BG/NBD ModelCard
is REFUSED or INSUFFICIENT_DATA, Gamma-Gamma short-circuits to REFUSED
with `fit_warnings=["chained_bgnbd_refusal"]` (no fit attempted, no
parquet). The T1.5 receipt confirmed BG/NBD lands REFUSED or
INSUFFICIENT_DATA on all 5 pinned synthetic fixtures. Thus G-G inherits
chained-refusal on all 5.

| Fixture | BG/NBD fit_status (T1.5) | G-G fit_status | fit_warnings | parquet written |
|---|---|---|---|---|
| `healthy_beauty_240d` | REFUSED | **REFUSED** | `["chained_bgnbd_refusal"]` | NO |
| `healthy_supplements_240d` | REFUSED | **REFUSED** | `["chained_bgnbd_refusal"]` | NO |
| `small_sm` (golden) | REFUSED | **REFUSED** | `["chained_bgnbd_refusal"]` | NO |
| `mid_shopify` (golden) | INSUFFICIENT_DATA | **REFUSED** | `["chained_bgnbd_refusal"]` | NO |
| `micro_coldstart` (golden) | INSUFFICIENT_DATA | **REFUSED** | `["chained_bgnbd_refusal"]` | NO |

`healthy_beauty_240d` G-G result directly verified live via the new T2.5
rollback test
(`test_flag_on_populates_gamma_gamma_chained_refusal_on_beauty`):
`model_name=gamma_gamma`, `fit_status=REFUSED`,
`"chained_bgnbd_refusal" in fit_warnings`. The remaining 4 fixtures'
G-G postures inherit from the chained-refusal short-circuit (a pure
data-equality contract on `bgnbd_card.fit_status`); the full-suite
green pass exercises them through the slate-regression + golden-diff
trees.

### 3.1 Empirical curiosity (out-of-scope but informative)

When the operator runs `ENGINE_V2_ML_GAMMA_GAMMA=true` AND
`ENGINE_V2_ML_BGNBD=false` (BG/NBD card absent, no chained input),
G-G falls through to its own fit path on synthetic Beauty and lands
`fit_status=REFUSED, fit_warnings=["holdout_rank_spearman_below_floor"]`
(rank ≈ 0.0037, n_observed=3844, agg_ratio ≈ 1.05). This is the
real G-G fit refusing on its primary gate — NOT chained refusal.
Surfaced by `test_gamma_gamma_on_bgnbd_off_handles_missing_bgnbd_card`
in the new rollback test. Production path always runs BG/NBD ON +
G-G ON, so the chained-refusal path is canonical; this finding is
documented for completeness and as evidence the orchestration handles
`bgnbd_model_card=None` cleanly without crashing.

**No G-G parquet artifacts written on any of the 5 pinned fixtures.**
Verified by construction: `src/predictive/gamma_gamma.py::fit_gamma_gamma`
returns the chained-refusal ModelCard at Step 1 (L460-477) BEFORE Step
8's parquet-write guard. Path `data/<store_id>/predictive/gamma_gamma.parquet`
is never touched.

---

## 4. briefing.html byte-identity (5 fixtures, hard gate)

All five pinned briefing.html files are **byte-identical** post-flip,
verified by full-suite green pass (`test_slate_regression_beauty_brand`,
`test_slate_regression_supplements_brand`, `test_golden_diff[*]`,
`test_s8_t3_provenance`).

| Fixture | Pinned sha (S8-T3) | Source | Status |
|---|---|---|---|
| `healthy_beauty_240d` | `f8676c9f...` | `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | PASS (xpass under flag-ON default) |
| `healthy_supplements_240d` | `13a91e6c...` | `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | PASS (xpass) |
| `small_sm` | `40bf24ea...` | `tests/golden/small_sm/briefing.html` | PASS (golden_diff) |
| `mid_shopify` | `380b2c5d...` | `tests/golden/mid_shopify/briefing.html` | PASS (golden_diff) |
| `micro_coldstart` | `2191b251...` | `tests/golden/micro_coldstart/briefing.html` | PASS (golden_diff) |

Structural guarantee: `grep -rn "predictive_models" src/` confirms the
renderer does NOT read the field (matches the T1.5 finding). The new
G-G ModelCard payload is purely operator-visible on `engine_run.json`.

---

## 5. engine_run.json byte-pin status

`grep -rln "engine_run.json" tests/` does NOT surface any sha-pinned
contract (re-confirmed from T1.5). The only byte-comparison on
engine_run.json is the cross-run determinism test
(`tests/test_determinism_cross_run.py`) which normalizes `run_id` +
nested timestamp paths. T2.5 added
`predictive_models.gamma_gamma.fit_timestamp` to that normalization
list (precedent: `predictive_models.bgnbd.fit_timestamp` at T1.5;
`store_profile.provenance.profiled_at` at S6.5-T5).

**No pinned-sha fixture files required updates.** No engine_run.json sha
is byte-stable by design.

---

## 6. Rollback contract test

`tests/test_s10_t2_5_gamma_gamma_rollback.py` (NEW). Four tests:

1. `test_flag_off_rollback_gamma_gamma_absent` — with
   `ENGINE_V2_ML_GAMMA_GAMMA=false` (BG/NBD ON), the Beauty harness
   produces `predictive_models` that does NOT contain `"gamma_gamma"`.
   BG/NBD card may still be present. Pins the rollback contract
   (orchestration block is a pure no-op at G-G flag OFF).

2. `test_flag_on_populates_gamma_gamma_chained_refusal_on_beauty` — with
   both flags ON (T2.5 default), Beauty's `predictive_models["gamma_gamma"]`
   is populated with `model_name="gamma_gamma"`, `fit_status="REFUSED"`,
   and `"chained_bgnbd_refusal" in fit_warnings`. Pins the
   chained-refusal expected outcome (Option γ extends).

3. `test_both_flags_off_predictive_models_empty` — both flags OFF
   reproduces the pre-S10 shape: `predictive_models == {}`.

4. `test_gamma_gamma_on_bgnbd_off_handles_missing_bgnbd_card` — edge
   case (BG/NBD OFF, G-G ON). The G-G orchestration must handle
   `bgnbd_model_card=None` cleanly. ModelCard populated with
   `fit_status` ∈ four-state vocabulary; no crash; no chained-refusal
   warning (because input is None, not REFUSED).

All 4 pass in 83.75s. Plus the T1.5 rollback test
(`test_s10_t1_5_bgnbd_rollback.py`) updated to keep its BG/NBD-rollback
assertion clean under the new G-G-default-ON envelope — both T1.5 tests
still pass.

---

## 7. Suite status

| Check | Result |
|---|---|
| `pytest` (full suite, post-T2.5) | **1944 passed, 14 skipped, 4 xfailed, 2 xpassed** in 1446.80s |
| `pytest tests/test_s10_t2_5_gamma_gamma_rollback.py` | 4 passed (83.75s) |
| `pytest tests/test_s10_t1_5_bgnbd_rollback.py` | 2 passed (under updated env contract) |
| `pytest tests/test_s10_t2_gamma_gamma_fit.py` | 12 passed (including renamed `test_flag_default_on_post_t2_5`) |
| `pytest tests/test_slate_regression_beauty_brand.py tests/test_slate_regression_supplements_brand.py tests/test_determinism_cross_run.py tests/test_golden_diff.py tests/test_s8_t3_provenance.py` | 72 passed, 2 xpassed — briefing.html byte-identity preserved |

Baseline (post-T1.5): 1940 passed, 14 skipped, 4 xfailed, 2 xpassed.
Net delta: **+4 passed** (4 new T2.5 rollback tests). No regressions,
no new skips, no new xfails.

---

## 8. Behavior changes

1. **Flag-ON default (operator-visible).** When
   `ENGINE_V2_ML_GAMMA_GAMMA` is not explicitly set in env, the engine
   now invokes `fit_gamma_gamma` per merchant immediately after BG/NBD
   and surfaces the ModelCard on
   `engine_run.predictive_models["gamma_gamma"]`. On synthetic pinned
   fixtures every result is REFUSED via chained-refusal (BG/NBD
   short-circuited every one); audit-log fit_warnings carry
   `chained_bgnbd_refusal`.

2. **Renderer unchanged.** briefing.html bytes preserved across all 5
   pinned fixtures (renderer does not consume `predictive_models`).

3. **PlayCard unchanged.** `predicted_segment` / `model_card_ref` stay
   `None`. S13 wires the populating producers.

4. **Recommendations unchanged.** The new orchestration block writes
   only to `engine_run.predictive_models["gamma_gamma"]`, never to
   `engine_run.recommendations` — single-demote-channel invariant
   preserved.

5. **No new dependency.** `lifetimes==0.11.3` already pinned at T1.5;
   `scipy<1.13` pin retained per DS direction (not relaxed at T2.5).

---

## 9. Files changed

- `src/utils.py` (modified — flag default flip)
- `src/main.py` (modified — G-G PREDICTIVE_FIT orchestration block at L1003-1041)
- `tests/test_determinism_cross_run.py` (modified — added gamma_gamma.fit_timestamp to nested normalization)
- `tests/test_s10_t1_5_bgnbd_rollback.py` (modified — env override updated to keep BG/NBD-rollback assertion clean under new G-G default-ON envelope)
- `tests/test_s10_t2_gamma_gamma_fit.py` (modified — flag default test renamed + assertion flipped)
- `tests/test_s10_t2_5_gamma_gamma_rollback.py` (NEW)
- `agent_outputs/code-refactor-engineer-s10-t2.5-summary.md` (NEW)

---

## 10. Risk assessment

1. **5/5 fixtures REFUSED-via-chained-refusal at S10 close.** Same
   Option γ posture as T1.5. Real VALIDATED evidence will come from
   S14 real-merchant data. No new failure surface introduced.

2. **`net_sales` is the per-order monetary column carried into G-G.**
   The orchestration reads `g["net_sales"]` (per `src/features.py`
   convention: `n_orders` × `net_sales=first`-per-order, so each row's
   `net_sales` is the order's monetary value). On synthetic fixtures
   the chained-refusal short-circuit fires before G-G inspects the
   column, so any DGP issue with synthetic monetary values cannot
   reach the fit path on the 5 pinned fixtures.

3. **T1.5 rollback test contract update is load-bearing.** The
   `_run_and_load` helper in `test_s10_t1_5_bgnbd_rollback.py` now
   sets `ENGINE_V2_ML_GAMMA_GAMMA=false` explicitly to keep the
   BG/NBD-rollback assertion `predictive_models == {}` semantic.
   Failure to apply this update would have caused the T1.5 test to
   fail on the T2.5 atomic flip — caught immediately by the
   single-test run before suite-wide validation. This is a clean
   composition: each rollback test pins its own flag's contract.

4. **The `bgnbd_model_card=None` edge case** (BG/NBD OFF, G-G ON) is
   now operator-visible and tested. G-G falls through to its own fit
   path and on Beauty lands REFUSED via `holdout_rank_spearman_below_floor`
   (rank ≈ 0.0037). This is the real G-G metric refusing — an honest
   outcome, not a crash. Documented in §3.1 and pinned in test 4 of
   the new rollback test.

5. **`fit_timestamp` is run-varying.** Now normalized in the cross-run
   determinism comparator for both BG/NBD and G-G. If a future ticket
   adds another wall-clock field to the ModelCard, the comparator must
   learn it too (same standing risk noted at T1.5 §10.3).

---

## 11. Deviation-check statement

**Deviation check: none.**

The T2.5 patch follows the IM plan §D-T2.5 and the DS-pre-approved
Option γ extension shape:
- Flag flip + orchestration wire + rollback test + determinism update
  in one atomic commit.
- No fixture reshape (Pivot 5 honored).
- No new VALIDATED-coverage fixture (Pivot 5 honored).
- No `src/decide.py` / `src/sizing.py` / ReasonCode / PlayCard /
  briefing.html / renderer / guardrails changes (T3 + S13 scoped).
- No G-G semantics change (T2 logic preserved). The orchestration
  passes the chained-refusal input through unchanged.
- No scipy pin relaxation.
- No self-commit (orchestrator commits per founder protocol).

Two test contract updates surfaced as load-bearing companions to the
flag flip (not new scope):
- `test_s10_t1_5_bgnbd_rollback.py::_run_and_load` set
  `ENGINE_V2_ML_GAMMA_GAMMA=false` explicitly so the BG/NBD-only
  rollback assertion keeps its semantics under the new G-G default.
- `test_s10_t2_gamma_gamma_fit.py::test_flag_default_off` renamed and
  re-asserted to reflect the new default. Same pattern as T1.5's
  `test_flag_default_on_post_t1_5` (if it exists in that suite under a
  similar name).

Both are mechanical follow-ons to the atomic flag flip — surfaced in
the receipt for transparency.

---

## 12. Recommended T3 dispatch context

T3 ships ReasonCode precedence pin + KI filings for the predictive
layer. Dispatch context for T3:

1. **ReasonCode enum is locked at T2.5.** No new ReasonCodes have been
   added at T1.5 or T2.5. T3's job is the precedence ORDER pin (not
   new codes) — `src/engine_run.py::ReasonCode` enum is unchanged
   since pre-S10. T3 will likely codify the precedence in a typed
   sequence or sorted tuple and add a test pinning it.

2. **ModelFitStatus four-state vocabulary is locked.** `VALIDATED`,
   `PROVISIONAL`, `REFUSED`, `INSUFFICIENT_DATA` per
   `src/predictive/model_card.py`. T3 should NOT add new states; if
   a new state seems needed, pause and surface to DS.

3. **Single-demote-channel invariant remains load-bearing.** T3 must
   not append to `engine_run.recommendations` outside of
   `apply_guardrails*`. Predictive_models writes are an isolated
   surface — never cross the boundary.

4. **KI filings:**
   - KI-NEW-Q-v2 (G-G Spearman threshold speculative-until-S14):
     mirror KI-NEW-P-v2 (BG/NBD Spearman) shape, same vintage.
   - KI-NEW-R (G-G `holdout_empty` short-circuit behavior on
     low-span fixtures): pinned by T2's `holdout_empty` warning;
     T3 should file the KI for explicit operator visibility.
   - KI for the `bgnbd_card=None` orchestration edge case (per §3.1
     above): when BG/NBD is OFF but G-G is ON, G-G runs its own fit
     and may surface non-chained REFUSED postures. Inform operators.

5. **Per-fixture summary table** (in this receipt, §3) should be
   carried into the T3 KI body for KI-NEW-Q-v2 evidence.

6. **No briefing.html / renderer / PlayCard changes at T3** (same as
   T1.5 + T2.5). S13 wires the consumers.

---

## 13. Recommended commit message (orchestrator uses)

```
S10-T2.5: Gamma-Gamma atomic flip — orchestration wire + rollback test

Atomic single-commit per S7.6/S8/T1.5 cadence. Flips
ENGINE_V2_ML_GAMMA_GAMMA default ON, wires fit_gamma_gamma into
src/main.py orchestration immediately after the BG/NBD block, adds
rollback contract test, normalizes gamma_gamma.fit_timestamp in
cross-run determinism.

Per IM plan §C.2 / DS Option γ extends (2026-05-26): all 5 pinned
synthetic fixtures have BG/NBD REFUSED or INSUFFICIENT_DATA (T1.5
receipt), so Gamma-Gamma short-circuits to REFUSED via chained
refusal with fit_warnings=["chained_bgnbd_refusal"] on every one.
No fit attempted, no parquet artifact written. Real VALIDATED
evidence at S14 from real merchant data.

- src/utils.py: ENGINE_V2_ML_GAMMA_GAMMA default true (in _coerce
  bool set at T2; no change needed there).
- src/main.py L1003-1041: G-G PREDICTIVE_FIT block, guarded by
  cfg["ENGINE_V2_ML_GAMMA_GAMMA"], placed immediately after the
  BG/NBD block (post-L1001), before guardrails. Reads
  predictive_models["bgnbd"] as the chained-refusal input. Builds
  the G-G orders frame from g[customer_id, Created at, net_sales].
  Writes ModelCard to engine_run.predictive_models["gamma_gamma"];
  never to recommendations (single-demote-channel invariant).
- tests/test_s10_t2_5_gamma_gamma_rollback.py: NEW. Four cases:
  G-G flag OFF (gamma_gamma absent), G-G flag ON (chained-refusal
  on Beauty), both flags OFF (predictive_models == {}), and the
  BG/NBD-OFF / G-G-ON edge case (G-G handles None bgnbd_card
  cleanly).
- tests/test_s10_t1_5_bgnbd_rollback.py: env override now sets
  ENGINE_V2_ML_GAMMA_GAMMA=false explicitly so the BG/NBD-rollback
  assertion (predictive_models == {}) keeps its semantic under the
  T2.5 default-ON envelope.
- tests/test_s10_t2_gamma_gamma_fit.py: test_flag_default_off
  renamed to test_flag_default_on_post_t2_5; assertion flipped.
- tests/test_determinism_cross_run.py: added
  predictive_models.gamma_gamma.fit_timestamp to the nested-path
  normalization list (precedent: bgnbd.fit_timestamp at T1.5).

Briefing.html byte-identical for all 5 pinned fixtures (renderer
does not consume predictive_models; verified by full
test_slate_regression + test_golden_diff suites). No engine_run.json
byte-pin contracts existed; additive predictive_models.gamma_gamma
payload lands free.

PlayCard.predicted_segment / model_card_ref stay None — S13 wires
the populating producers. No src/decide.py / src/sizing.py /
ReasonCode / PlayCard / briefing.html / renderer / guardrails
changes.

Suite: 1944 passed, 14 skipped, 4 xfailed, 2 xpassed (+4 vs T1.5
baseline — all 4 new T2.5 rollback tests).

Deviation check: none.
```

---

**Deviation check: none.**
