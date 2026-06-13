# S11-T1.5 — Cox PH survival atomic flip + orchestration wire + rollback contract

**Date:** 2026-05-26
**Ticket:** S11-T1.5 — `ENGINE_V2_ML_SURVIVAL` atomic ON + `fit_survival` wired into `src/main.py` + rollback contract test
**Branch:** `post-6b-restructured-roadmap`
**Engineer:** code-refactor-engineer
**Status:** STAGED (single atomic commit per S7.6 / S8 / S10-T1.5 / S10-T2.5 cadence — orchestrator commits)
**Deviation check:** none.

---

## 1. Approved scope (restated)

DS-locked Option γ (extended to survival, 2026-05-26): atomically flip
`ENGINE_V2_ML_SURVIVAL` default ON, wire `fit_survival` into
orchestration immediately after the Gamma-Gamma block, accept honest
5/5 REFUSED-via-chained-refusal outcome on synthetic pinned fixtures
(BG/NBD already REFUSED or INSUFFICIENT_DATA on every one, so survival
short-circuits at Step 1 of `fit_survival`). Pivot 5 load-bearing — no
fixture reshape, no new VALIDATED-coverage fixture. Real VALIDATED
evidence at S14 from real merchant data.

Hard gates (all met):
1. `briefing.html` byte-identity across all 5 pinned fixtures.
2. No engine_run.json byte-pin contracts exist — additive
   `predictive_models["survival"]` payload lands free.
3. Rollback contract: `ENGINE_V2_ML_SURVIVAL=false` reproduces the
   pre-T1.5 shape — `"survival"` absent from `predictive_models`.
4. PlayCard.predicted_segment / model_card_ref stay `None` — S13 wires
   the populating producers.
5. Single-demote-channel invariant preserved — writes only to
   `engine_run.predictive_models["survival"]`, never to
   `recommendations`.
6. NO survival parquet artifacts written (all 5 chained-refused;
   parquet write branch gated on `{VALIDATED, PROVISIONAL}` per
   `src/predictive/survival.py:626-629`).

---

## 2. Patch summary

| Action | File | Line ranges | Notes |
|---|---|---|---|
| MODIFIED | `src/utils.py` | L908-910 | `ENGINE_V2_ML_SURVIVAL` default flipped `"false"` → `"true"`. Already in `_coerce` bool set per T1 — no change there. |
| MODIFIED | `src/main.py` | L1048-1086 | New PREDICTIVE_FIT orchestration block, guarded by `cfg["ENGINE_V2_ML_SURVIVAL"]`. Placed IMMEDIATELY after the G-G block (post-L1046), BEFORE guardrails. Builds the survival orders frame from `g[["customer_id", "Created at"]]` (per S11-T1 `fit_survival` signature: `customer_id`, `order_date`). Reads `engine_run.predictive_models.get("bgnbd")` as the chained-refusal input. Calls `fit_survival(orders, profile, bgnbd_card, store_id=..., data_dir=...)` → `ModelCard`. Writes via `dataclasses.replace`. Single try/except wrapper for safety (matches BG/NBD + G-G precedents immediately above). |
| MODIFIED | `tests/test_determinism_cross_run.py` | L107-125 | Added `"predictive_models.survival.fit_timestamp"` to `_NESTED_NORMALIZED_PATHS` with rationale comment. Mirrors the T1.5 BG/NBD + T2.5 G-G `fit_timestamp` normalizations. |
| MODIFIED | `tests/test_s10_t1_5_bgnbd_rollback.py` | `_run_and_load` | Now explicitly sets `ENGINE_V2_ML_SURVIVAL=false` (in addition to the existing `ENGINE_V2_ML_GAMMA_GAMMA=false`). Without this, the T1.5 rollback assertion `predictive_models == {}` would fail under T1.5's default-ON. Same composition pattern as T2.5 introduced. |
| MODIFIED | `tests/test_s10_t2_5_gamma_gamma_rollback.py` | `_run_and_load` | Now explicitly sets `ENGINE_V2_ML_SURVIVAL=false`. Same rationale as above — keeps the G-G-only rollback assertion semantic. |
| MODIFIED | `tests/test_s11_t1_survival_fit.py` | L323-340 | Renamed `test_flag_default_off` → `test_flag_default_on_post_t1_5`. Assertion flipped from `is False` to `is True`. T1 was a substrate-only ship at flag-OFF; T1.5 is the atomic flip. |
| NEW | `tests/test_s11_t1_5_survival_rollback.py` | full file (165 LoC) | Four harness-level tests (see §6). |
| NEW | `agent_outputs/code-refactor-engineer-s11-t1.5-summary.md` | this file | T1.5 receipt. |

No other files changed. No edits to `src/decide.py`, `src/sizing.py`,
`src/engine_run.py` (ReasonCode), PlayCard, briefing.html / renderer,
guardrails, `apply_guardrails*`, or `src/predictive/survival.py` (T1
logic preserved unchanged).

---

## 3. Per-fixture survival fit_status (5 fixtures, ENGINE_V2_ML_SURVIVAL=true, T1.5 default)

Per `src/predictive/survival.py` Step 1 (chained-refusal): when the
same-run BG/NBD ModelCard is missing OR its fit_status ∈ {REFUSED,
INSUFFICIENT_DATA}, survival short-circuits to REFUSED with
`fit_warnings=["chained_bgnbd_refusal"]` (no fit attempted, no
parquet). The S10-T1.5 receipt confirmed BG/NBD lands REFUSED or
INSUFFICIENT_DATA on all 5 pinned synthetic fixtures. Thus survival
inherits chained-refusal on all 5.

| Fixture | BG/NBD fit_status | Survival fit_status | fit_warnings | parquet written |
|---|---|---|---|---|
| `healthy_beauty_240d` | REFUSED | **REFUSED** | `["chained_bgnbd_refusal"]` | NO |
| `healthy_supplements_240d` | REFUSED | **REFUSED** | `["chained_bgnbd_refusal"]` | NO |
| `small_sm` (golden) | REFUSED | **REFUSED** | `["chained_bgnbd_refusal"]` | NO |
| `mid_shopify` (golden) | INSUFFICIENT_DATA | **REFUSED** | `["chained_bgnbd_refusal"]` | NO |
| `micro_coldstart` (golden) | INSUFFICIENT_DATA | **REFUSED** | `["chained_bgnbd_refusal"]` | NO |

`healthy_beauty_240d` survival result directly verified live via the
new T1.5 rollback test
(`test_flag_on_populates_survival_chained_refusal_on_beauty`):
`model_name=survival`, `fit_status=REFUSED`, `"chained_bgnbd_refusal" in
fit_warnings`. The remaining 4 fixtures' survival postures inherit from
the chained-refusal short-circuit (a pure data-equality contract on
`bgnbd_card.fit_status`); the full-suite green pass exercises them
through the slate-regression + golden-diff trees.

**No survival parquet artifacts written on any of the 5 pinned
fixtures.** Verified by construction:
`src/predictive/survival.py::fit_survival` returns the chained-refusal
ModelCard at Step 1 (L311-326) BEFORE Step 8's parquet-write guard.
Path `data/<store_id>/predictive/survival.parquet` is never touched.

### 3.1 Empirical curiosity (out-of-scope but informative)

When the operator runs `ENGINE_V2_ML_SURVIVAL=true` AND
`ENGINE_V2_ML_BGNBD=false` (BG/NBD card absent, no chained input),
survival's Step 1 treats `bgnbd_model_card is None` as REFUSED (per
`fit_survival` Step 1 spec L311-314) and short-circuits to REFUSED
with `chained_bgnbd_refusal`. Surfaced by
`test_survival_on_bgnbd_off_handles_missing_bgnbd_card` in the new
rollback test. Production path always runs BG/NBD ON + G-G ON +
survival ON, so the chained-refusal-via-BG/NBD-status path is canonical;
this finding documents that the orchestration handles
`bgnbd_model_card=None` cleanly without crashing.

Note this differs from G-G's None-input behavior (G-G falls through to
its own fit path when bgnbd_card is None — see S10-T2.5 §3.1). The
divergence is by design at the module level (T1 module decision): Cox
PH chained refusal is stricter because the rationale is "no upstream
aliveness signal at all means hazard-on-the-same-gap-time signal is
also uninformative."

---

## 4. briefing.html byte-identity (5 fixtures, hard gate)

All five pinned briefing.html files are **byte-identical** post-flip,
verified by full-suite green pass:

| Fixture | Pinned sha (S8-T3) | Source | Status |
|---|---|---|---|
| `healthy_beauty_240d` | `f8676c9f...` | `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | PASS |
| `healthy_supplements_240d` | `13a91e6c...` | `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | PASS |
| `small_sm` | `40bf24ea...` | `tests/golden/small_sm/briefing.html` | PASS |
| `mid_shopify` | `380b2c5d...` | `tests/golden/mid_shopify/briefing.html` | PASS |
| `micro_coldstart` | `2191b251...` | `tests/golden/micro_coldstart/briefing.html` | PASS |

Tests confirming: `test_slate_regression_beauty_brand`,
`test_slate_regression_supplements_brand`, `test_golden_diff[*]`,
`test_s8_t3_provenance` — all PASS (72 passed, 2 xpassed in 168.89s).

Structural guarantee: `grep -rn "predictive_models" src/` confirms the
renderer does NOT read the field. The new survival ModelCard payload is
purely operator-visible on `engine_run.json`.

---

## 5. engine_run.json byte-pin status

`grep -rln "engine_run.json" tests/` does NOT surface any sha-pinned
contract (re-confirmed from T1.5 / T2.5). The only byte-comparison on
engine_run.json is the cross-run determinism test
(`tests/test_determinism_cross_run.py`) which normalizes `run_id` +
nested timestamp paths. T1.5 added
`predictive_models.survival.fit_timestamp` to that normalization list
(precedents: `predictive_models.bgnbd.fit_timestamp` at S10-T1.5;
`predictive_models.gamma_gamma.fit_timestamp` at S10-T2.5;
`store_profile.provenance.profiled_at` at S6.5-T5).

**No pinned-sha fixture files required updates.**

---

## 6. Rollback contract test

`tests/test_s11_t1_5_survival_rollback.py` (NEW). Four tests:

1. `test_flag_off_rollback_survival_absent` — with
   `ENGINE_V2_ML_SURVIVAL=false` (BG/NBD ON, G-G ON), the Beauty
   harness produces `predictive_models` that does NOT contain
   `"survival"`. BG/NBD + G-G cards may still be present. Pins the
   rollback contract (orchestration block is a pure no-op at survival
   flag OFF).

2. `test_flag_on_populates_survival_chained_refusal_on_beauty` — with
   all three flags ON (T1.5 default), Beauty's
   `predictive_models["survival"]` is populated with
   `model_name="survival"`, `fit_status="REFUSED"`, and
   `"chained_bgnbd_refusal" in fit_warnings`. Pins the chained-refusal
   expected outcome (Option γ extends).

3. `test_all_flags_off_predictive_models_empty` — all three flags OFF
   reproduces the pre-S10 shape: `predictive_models == {}`.

4. `test_survival_on_bgnbd_off_handles_missing_bgnbd_card` — edge case
   (BG/NBD OFF + G-G OFF, survival ON). The survival orchestration must
   handle `bgnbd_model_card=None` cleanly. ModelCard populated with
   `fit_status` ∈ four-state vocabulary; no crash. Survival's Step 1
   contract treats None as REFUSED (chained_bgnbd_refusal).

All 4 pass (run against the bundled `pytest` invocation across the
four rollback tests and the related survival-fit + bgnbd-rollback +
gg-rollback tests: **24 passed in 306.68s**).

---

## 7. Suite status

| Check | Result |
|---|---|
| `pytest tests/test_s11_t1_5_survival_rollback.py tests/test_s10_t1_5_bgnbd_rollback.py tests/test_s10_t2_5_gamma_gamma_rollback.py tests/test_s11_t1_survival_fit.py` | **24 passed (306.68s)** |
| `pytest tests/test_slate_regression_beauty_brand.py tests/test_slate_regression_supplements_brand.py tests/test_golden_diff.py tests/test_s8_t3_provenance.py tests/test_determinism_cross_run.py` | **72 passed, 2 xpassed (168.89s)** — briefing.html byte-identity preserved |
| `pytest` (full suite, post-T1.5) | **1973 passed, 14 skipped, 4 xfailed, 2 xpassed, 1 failed** in 1568.11s (≈26 min) |

The 1 failure is
`test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh`
— the pre-existing wall-clock flake explicitly called out in the
dispatch ("DO NOT chase"). No regressions introduced by T1.5.

Net delta vs S11-T1 baseline (1969 passed): **+4 passed** (4 new T1.5
rollback tests). No new failures, no new skips, no new xfails.

---

## 8. Behavior changes

1. **Flag-ON default (operator-visible).** When `ENGINE_V2_ML_SURVIVAL`
   is not explicitly set in env, the engine now invokes `fit_survival`
   per merchant immediately after Gamma-Gamma and surfaces the
   ModelCard on `engine_run.predictive_models["survival"]`. On synthetic
   pinned fixtures every result is REFUSED via chained-refusal (BG/NBD
   short-circuited every one); audit-log fit_warnings carry
   `chained_bgnbd_refusal`.

2. **Renderer unchanged.** briefing.html bytes preserved across all 5
   pinned fixtures (renderer does not consume `predictive_models`).

3. **PlayCard unchanged.** `predicted_segment` / `model_card_ref` stay
   `None`. S13 wires the populating producers.

4. **Recommendations unchanged.** The new orchestration block writes
   only to `engine_run.predictive_models["survival"]`, never to
   `engine_run.recommendations` — single-demote-channel invariant
   preserved.

5. **No new dependency.** `scikit-survival>=0.22,<0.24` already pinned
   at S11-T1; `scipy<1.13` pin retained (not relaxed at T1.5).

6. **`fit_survival` semantics unchanged.** T1.5 wires the existing T1
   module into orchestration; no edits to `src/predictive/survival.py`.

---

## 9. Files changed

- `src/utils.py` (modified — flag default flip L908-910)
- `src/main.py` (modified — survival PREDICTIVE_FIT orchestration block at L1048-1086)
- `tests/test_determinism_cross_run.py` (modified — added survival.fit_timestamp to nested normalization)
- `tests/test_s10_t1_5_bgnbd_rollback.py` (modified — env override now disables survival flag for BG/NBD-only rollback semantic)
- `tests/test_s10_t2_5_gamma_gamma_rollback.py` (modified — env override now disables survival flag for G-G-only rollback semantic)
- `tests/test_s11_t1_survival_fit.py` (modified — flag default test renamed + assertion flipped)
- `tests/test_s11_t1_5_survival_rollback.py` (NEW)
- `agent_outputs/code-refactor-engineer-s11-t1.5-summary.md` (NEW)

---

## 10. Risk assessment

1. **5/5 fixtures REFUSED-via-chained-refusal at S11-T1.5 close.** Same
   Option γ posture as S10-T1.5 / S10-T2.5. Real VALIDATED evidence
   will come from S14 real-merchant data. No new failure surface
   introduced.

2. **Survival orchestration block reads only `customer_id` and
   `Created at`.** Per the T1 `fit_survival` signature, monetary value
   is NOT a covariate (covariates are RFM-derived `log_frequency` +
   `log_recency_over_T`). The orders frame construction is intentionally
   the minimal projection from `g`. Net_sales is not threaded through.

3. **Two prior rollback tests required env-override updates** as
   load-bearing companions to the flag flip (not new scope):
   - `test_s10_t1_5_bgnbd_rollback.py::_run_and_load` set
     `ENGINE_V2_ML_SURVIVAL=false` explicitly so the BG/NBD-only
     rollback assertion (`predictive_models == {}`) keeps its semantic
     under the new survival default-ON envelope.
   - `test_s10_t2_5_gamma_gamma_rollback.py::_run_and_load` same
     pattern.
   Both are mechanical follow-ons (same precedent as S10-T2.5
   introduced for the S10-T1.5 test). Each rollback test pins its own
   flag's contract independently.

4. **`bgnbd_model_card=None` edge case** (BG/NBD OFF, survival ON) is
   now operator-visible and tested. Survival's Step 1 contract treats
   None as REFUSED and emits `chained_bgnbd_refusal` — divergent from
   G-G's None-input behavior (which falls through to its own fit
   path). The divergence is by design at the T1 module level (Cox PH
   chained refusal is stricter; rationale documented in
   `src/predictive/survival.py` L46-54).

5. **`fit_timestamp` is run-varying.** Now normalized in the cross-run
   determinism comparator for BG/NBD, G-G, and survival. If a future
   ticket adds another wall-clock field to the ModelCard, the
   comparator must learn it too (same standing risk noted at S10-T1.5
   §10.3 / S10-T2.5 §10.5).

6. **scipy<1.13 pin advisory** carried forward from S11-T1 §8.1 (pin
   silently bypassed on Python 3.14 dev envs). No T1.5 change. Real
   environments at S14 should validate.

---

## 11. Deviation-check statement

**Deviation check: none.**

The T1.5 patch follows the IM plan §D-T1.5 and the DS-pre-approved
Option γ extension shape (parallel to S10-T1.5 and S10-T2.5):
- Flag flip + orchestration wire + rollback test + determinism update
  in one atomic commit.
- No fixture reshape (Pivot 5 honored).
- No new VALIDATED-coverage fixture (Pivot 5 honored).
- No `src/decide.py` / `src/sizing.py` / ReasonCode / PlayCard /
  briefing.html / renderer / guardrails changes (S13 scoped).
- No survival semantics change (T1 logic preserved unchanged). The
  orchestration passes the chained-refusal input through unchanged.
- No scipy pin relaxation.
- No self-commit (orchestrator commits per founder protocol).

Two test contract updates surfaced as load-bearing companions to the
flag flip (mechanical, not new scope) — same pattern as S10-T2.5.

---

## 12. Recommended T2 (CF) dispatch context

T2 ships the collaborative-filtering predictive substrate (the third
and final S11 predictive layer; per IM plan §B/§D-T2).

1. **Pattern is locked.** S11-T1 (substrate flag-OFF land) + S11-T1.5
   (atomic flip + wire + rollback) is now the third successful
   instance of this cadence (after S10-T1+T1.5 BG/NBD and
   S10-T2+T2.5 G-G). T2 should mirror it exactly: ship substrate +
   tests at flag-OFF first, then T2.5 atomic flip.

2. **Chained-refusal posture remains DS-pre-approved.** CF's chained
   inputs (TBD by T2 IM dispatch — likely BG/NBD repeat-propensity
   ranking and/or survival expected-days) need definition. On
   synthetic pinned fixtures CF will land REFUSED via chained refusal,
   same as BG/NBD / G-G / survival.

3. **ModelFitStatus four-state vocabulary is locked.** `VALIDATED`,
   `PROVISIONAL`, `REFUSED`, `INSUFFICIENT_DATA` per
   `src/predictive/model_card.py`. CF should NOT add new states; if
   one seems needed, pause and surface to DS.

4. **Single-demote-channel invariant remains load-bearing.** CF
   ModelCard writes only to `engine_run.predictive_models["cf"]` (or
   similar key); never to `engine_run.recommendations`.

5. **briefing.html byte-identity is the hard gate** — renderer must
   not read `predictive_models["cf"]`. Verify via grep at T2 close.

6. **engine_run.json has no byte-pin contracts** — additive payloads
   land free. Re-confirm at T2.

7. **Determinism test:** if CF ModelCard adds a wall-clock field, add
   `predictive_models.cf.<field>` to `_NESTED_NORMALIZED_PATHS` in
   `tests/test_determinism_cross_run.py`.

8. **Rollback contract test:** mirror this T1.5 test file's shape —
   4 cases (flag OFF, flag ON chained-refusal, all flags OFF, edge
   case where upstream inputs are None).

9. **Prior rollback tests** (`test_s10_t1_5`, `test_s10_t2_5`,
   `test_s11_t1_5`) will need their `_run_and_load` env overrides
   updated to disable the new CF flag — same composition pattern.

10. **No briefing.html / renderer / PlayCard changes at T2 / T2.5**
    (same as T1.5 / T2.5 / S10). S13 wires the consumers.

---

## 13. Recommended commit message (orchestrator uses)

```
S11-T1.5: Cox PH survival atomic flip — orchestration wire + rollback test

Atomic single-commit per S7.6/S8/S10-T1.5/S10-T2.5 cadence. Flips
ENGINE_V2_ML_SURVIVAL default ON, wires fit_survival into
src/main.py orchestration immediately after the Gamma-Gamma block,
adds rollback contract test, normalizes survival.fit_timestamp in
cross-run determinism.

Per S11-T1 module contract / DS Option γ extends (2026-05-26): all 5
pinned synthetic fixtures have BG/NBD REFUSED or INSUFFICIENT_DATA
(S10-T1.5 receipt), so survival short-circuits to REFUSED via
chained refusal with fit_warnings=["chained_bgnbd_refusal"] on every
one. No fit attempted, no parquet artifact written. Real VALIDATED
evidence at S14 from real merchant data.

- src/utils.py: ENGINE_V2_ML_SURVIVAL default true (already in
  _coerce bool set at T1; no change needed there).
- src/main.py L1048-1086: survival PREDICTIVE_FIT block, guarded by
  cfg["ENGINE_V2_ML_SURVIVAL"], placed immediately after the G-G
  block (post-L1046), before guardrails. Reads
  predictive_models["bgnbd"] as the chained-refusal input. Builds
  the survival orders frame from g[customer_id, Created at]
  (matching T1 fit_survival signature: RFM covariates derived
  internally; no monetary covariate). Writes ModelCard to
  engine_run.predictive_models["survival"]; never to recommendations
  (single-demote-channel invariant).
- tests/test_s11_t1_5_survival_rollback.py: NEW. Four cases:
  survival flag OFF (survival absent), survival flag ON
  (chained-refusal on Beauty), all flags OFF (predictive_models
  == {}), and BG/NBD-OFF + survival-ON edge case (survival handles
  None bgnbd_card cleanly via Step 1 None-as-REFUSED).
- tests/test_s10_t1_5_bgnbd_rollback.py + tests/test_s10_t2_5_gamma_gamma_rollback.py:
  env overrides now set ENGINE_V2_ML_SURVIVAL=false explicitly so
  the BG/NBD-only / G-G-only rollback assertions keep their
  semantics under the T1.5 default-ON envelope.
- tests/test_s11_t1_survival_fit.py: test_flag_default_off renamed
  to test_flag_default_on_post_t1_5; assertion flipped.
- tests/test_determinism_cross_run.py: added
  predictive_models.survival.fit_timestamp to the nested-path
  normalization list (precedent: bgnbd.fit_timestamp at S10-T1.5,
  gamma_gamma.fit_timestamp at S10-T2.5).

Briefing.html byte-identical for all 5 pinned fixtures (renderer
does not consume predictive_models; verified by full
test_slate_regression + test_golden_diff suites). No engine_run.json
byte-pin contracts existed; additive predictive_models.survival
payload lands free.

PlayCard.predicted_segment / model_card_ref stay None — S13 wires
the populating producers. No src/decide.py / src/sizing.py /
ReasonCode / PlayCard / briefing.html / renderer / guardrails
changes. No src/predictive/survival.py edits (T1 module logic
preserved unchanged).

Suite: 1973 passed, 14 skipped, 4 xfailed, 2 xpassed, 1 failed
(pre-existing test_inventory_updated_at_is_fresh wall-clock flake;
not chased per dispatch). +4 vs S11-T1 baseline — all 4 new T1.5
rollback tests.

Deviation check: none.
```

---

**Deviation check: none.**
