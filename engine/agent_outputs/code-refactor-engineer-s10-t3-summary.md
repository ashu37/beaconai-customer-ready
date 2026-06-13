# S10-T3 — ML-fit ReasonCode additions + precedence pin + docs + KI-NEW-P

**Date:** 2026-05-26
**Ticket:** S10-T3 — Two dormant `ReasonCode` enum values, precedence invariant test, `docs/engine_flags.md` update, KI-NEW-P filing
**Branch:** `post-6b-restructured-roadmap`
**Engineer:** code-refactor-engineer
**Status:** STAGED (orchestrator commits)
**Deviation check:** none.

---

## 1. Approved scope (restated)

S10-T3 closes Sprint 10 with four concrete pieces:
1. Add two dormant `ReasonCode` enum values to `src/engine_run.py`:
   `MODEL_FIT_INSUFFICIENT_DATA = "model_fit_insufficient_data"` and
   `MODEL_FIT_REFUSED = "model_fit_refused"`. Additive within
   `event_version=1`. No emitter wired (S13 consumes).
2. Create `tests/test_reason_code_precedence_invariant.py` pinning
   the DS-locked precedence
   `(1) audience-floor → (2) cohort p-value → (3) prior-validation →
   (4) ML-fit`.
3. Update `docs/engine_flags.md` with the three-orthogonal-gate (soon
   four) ML-fit row + ranking-strategy fallback chain
   `BG/NBD → CF → survival → RFM → recency`.
4. File **KI-NEW-P** (ModelFitStatus stage-grid threshold calibration
   suite). KI-NEW-Q and KI-NEW-R remain founder-deferred per IM plan
   §D-T3, NOT filed at T3.

No flag flips. No new flags. No `PlayCard` changes. No orchestration
changes. Pure schema-additive + test + documentation + KI.

---

## 2. Files changed

| Action | File | Line ranges | Notes |
|---|---|---|---|
| MODIFIED | `src/engine_run.py` | inserted after L150 (`WINDOW_DISAGREEMENT`), before the `AbstainMode` class header | Added a docstring block + `MODEL_FIT_INSUFFICIENT_DATA = "model_fit_insufficient_data"` + `MODEL_FIT_REFUSED = "model_fit_refused"`. Docstring explicitly documents dormancy at S10, S13 consumption, and the four-gate precedence (ML-fit is lowest, never demotes between slate roles). |
| MODIFIED | `docs/engine_flags.md` | new "S10 predictive layer — three-orthogonal-gate (soon four) ML-fit gate" section inserted directly before "Pre-V2 statistical flags (mostly deletion candidates)" | Documents the four-gate precedence, lists failure ReasonCodes per gate, documents ranking-strategy fallback chain `BG/NBD → CF → survival → RFM → recency`, and cross-links the precedence test. |
| MODIFIED | `KNOWN_ISSUES.md` | new `### KI-NEW-P` block inserted directly before the "Open count by category" `---` separator; count table architectural-limitations row 18 → 19, total 27 → 28; "Last updated" prepended with 2026-05-26 line | Files the calibration KI with two sub-bullets (`bgnbd_card=None` orchestration edge + Beauty BG/NBD failure-mode-across-path). |
| MODIFIED | `tests/test_engine_run_schema.py` | `test_all_reason_codes_declared` expected-set L204-234 | Added `"model_fit_insufficient_data"` and `"model_fit_refused"` to the expected set with a Sprint 10 Ticket T3 comment. Required to keep the existing enum-completeness contract green. |
| NEW | `tests/test_reason_code_precedence_invariant.py` | full file (~165 lines) | Four tests pinning the four-gate precedence + ML-fit dormancy contract. |
| NEW | `agent_outputs/code-refactor-engineer-s10-t3-summary.md` | this file | T3 receipt. |

No edits to `src/decide.py`, `src/sizing.py`, `src/main.py`,
`src/guardrails.py`, PlayCard schema, renderer, fixtures, or
`apply_guardrails*`. No flag flips.

---

## 3. ReasonCode enum additions (exact string values)

```python
MODEL_FIT_INSUFFICIENT_DATA = "model_fit_insufficient_data"
MODEL_FIT_REFUSED = "model_fit_refused"
```

Both members carry the `str` Enum shape inherited from `ReasonCode(str, Enum)`,
round-trip cleanly through `ReasonCode(code.value) is code`, and are
distinct from the run-level `COLD_START_INSUFFICIENT_DATA`. `event_version`
stays at 1 (additive enum values do not bump it; same Sprint 2 freeze
carve-out precedent as `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW`,
`PRIOR_UNVALIDATED`, `WINDOW_DISAGREEMENT`).

---

## 4. Precedence test file structure

`tests/test_reason_code_precedence_invariant.py` — 4 tests:

1. `test_model_fit_codes_exist_in_enum` — confirms both members exist
   with exact string values; confirms identity-distinct from
   `COLD_START_INSUFFICIENT_DATA`.
2. `test_model_fit_codes_not_emitted_in_s10_close` — load-bearing
   dormancy assertion. Greps every `.py` file under `src/` EXCEPT
   `src/engine_run.py` (the definition site) for `MODEL_FIT_*` or
   `model_fit_*` references; asserts zero matches. This is the
   contract that ML-fit cannot demote a card at S10 close — there
   is literally no production emitter.
3. `test_precedence_ranking_order_documented` — encodes the
   DS-locked four-gate precedence as a `PRECEDENCE_ORDER` tuple
   constant and asserts the ordering (`audience_floor`,
   `cohort_p_value`, `prior_validation`, `ml_fit`). Asserts ML-fit
   is last (lowest precedence) and audience-floor is first.
4. `test_ml_fit_codes_are_string_enum_members` — defensive shape
   check (str-Enum semantics; round-trip via `.value`).

All 4 pass standalone (`pytest tests/test_reason_code_precedence_invariant.py
-v` → 4 passed in 0.07s).

---

## 5. `docs/engine_flags.md` updates

New section "S10 predictive layer — three-orthogonal-gate (soon four)
ML-fit gate" inserted before "Pre-V2 statistical flags". Contents:

1. Narrative paragraph: ML-fit is gate 4 of 4, lowest precedence,
   never demotes between slate roles.
2. DS-locked precedence statement (2026-05-26):
   `(1) audience-floor → (2) cohort p-value → (3) prior-validation →
   (4) ML-fit`.
3. Table — Gate × Position × Failure ReasonCodes × Effect when failing
   × Active at. Rows for audience-floor, cohort p-value,
   prior-validation, ModelFitStatus.
4. Ranking-strategy fallback chain:
   `BG/NBD → CF → survival → RFM → recency`. RFM = floor; recency =
   last-resort.
5. Cross-link to `tests/test_reason_code_precedence_invariant.py` for
   the dormancy contract pin.

---

## 6. KI-NEW-P filing (KI letter used = P)

KI-NEW-P (open, 2026-05-26, Architectural-limitations category) — file
covers BOTH BG/NBD (Spearman ≥ 0.20 / 0.10 floor) AND Gamma-Gamma
(Spearman ≥ 0.20 AND agg_ratio ∈ [0.5, 1.5] / band [0.4, 1.6]) per
business stage. Dimensions = ~20 numbers organized as 4 stage rows ×
4 metrics + 2 vertical month overrides + G-G band thresholds. Closure
criterion is ≥3 real beta merchants per stage cell with realized-vs-
predicted ranking + calibration data; founder reviews false-VALIDATED
rate (>20% triggers retune).

Two sub-bullets (NOT separate KIs):
- `bgnbd_card=None` orchestration edge case at `src/main.py:1003-1041`
  (BG/NBD OFF + G-G ON → non-chained REFUSED on synthetic Beauty,
  `holdout_rank_spearman_below_floor`, rank ≈ 0.0037).
- Beauty fixture BG/NBD failure-mode change across path: T1.4
  direct-CSV → `ConvergenceError`; T1.5 orchestration-load →
  `holdout_rank_spearman_below_floor`. Same fixture, different
  failure mode, both valid REFUSED.

Revisit trigger pinned to S14-T3 (real beta merchants × ≥30 days CSVs
× ModelFitStatus emitted across both BG/NBD and G-G; founder
false-VALIDATED rate review).

KI-NEW-Q and KI-NEW-R were intentionally NOT filed at T3 per IM plan
§D-T3 L415 founder-deferral. No KI letter variants invented
(no KI-NEW-Q-v2, no KI-NEW-R variants).

Count table updated: Architectural limitations 18 → 19; Total 27 → 28.

---

## 7. briefing.html byte-identity confirmation (all 5 fixtures)

Targeted subset run (`pytest tests/test_slate_regression_beauty_brand.py
tests/test_slate_regression_supplements_brand.py tests/test_golden_diff.py
tests/test_s8_t3_provenance.py`): **66 passed + 2 xpassed** in 95.61s.
All five pinned briefing.html shas held byte-identical:

| Fixture | Source path |
|---|---|
| `healthy_beauty_240d` | `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` |
| `healthy_supplements_240d` | `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` |
| `small_sm` | `tests/golden/small_sm/briefing.html` |
| `mid_shopify` | `tests/golden/mid_shopify/briefing.html` |
| `micro_coldstart` | `tests/golden/micro_coldstart/briefing.html` |

Structural guarantee: zero edits to `src/decide.py`, `src/main.py`,
renderer, or any other code path that produces briefing.html bytes.
T3 is purely schema-additive (enum values + test file + docs + KI
prose); the engine never touches the new codes at runtime in S10.

---

## 8. Suite status

| Check | Result |
|---|---|
| `pytest tests/test_reason_code_precedence_invariant.py` | 4 passed (0.07s) |
| `pytest tests/test_engine_run_schema.py tests/test_reason_code_precedence_invariant.py` (post enum-completeness expected-set update) | 21 passed (0.07s) |
| Briefing-byte-identity targeted suite | 66 passed, 2 xpassed (95.61s) |
| Full suite (initial — before expected-set update) | 1947 passed, 14 skipped, 4 xfailed, 2 xpassed, **1 failed** in 1485s — `test_engine_run_schema.py::test_all_reason_codes_declared` (enum-completeness contract) caught the additive change as expected |
| Full suite (post expected-set update) — NOT re-run end-to-end; targeted slice green; full re-run recommended at sprint-close gate | targeted slice green; the failure was a clean one-line expected-set sync, no other tests touch the new codes |

Baseline (post-T2.5): 1944 passed. Net delta after the expected-set
sync: +4 passed (the four new precedence-invariant tests) for a
projected 1948 passed if the full suite is re-run end-to-end. The
single fixture sync to `test_all_reason_codes_declared` is mechanical
and was validated standalone after the patch.

Recommended sprint-close gate: rerun the full suite once before
commit-and-push to capture the final post-update count.

---

## 9. Behavior changes

1. **Schema-additive only.** `ReasonCode` enum gains two new members.
   Production code paths do not reference them at S10 close (verified
   by the dormancy grep test in the new precedence file).
2. **`event_version` unchanged (still 1).** Same additive carve-out
   precedent as `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW`, `PRIOR_UNVALIDATED`,
   `WINDOW_DISAGREEMENT`.
3. **PlayCard untouched.** `predicted_segment` and `model_card_ref`
   stay None.
4. **Briefing.html bytes preserved.** All 5 pinned fixtures unchanged.
5. **Renderer untouched.** No new merchant-facing surface.
6. **Single-demote-channel invariant preserved.** No new write site to
   `engine_run.recommendations`; no new injection block.

---

## 10. Risk assessment

1. **Dormancy contract is grep-based.** The precedence test enforces
   "no src/ emitter outside `src/engine_run.py`" via regex over
   source text. False positives would require literal occurrence of
   `MODEL_FIT_*` or `model_fit_*` in an unrelated context (e.g.,
   variable name in an experimental script). Mitigation: when S13
   wires the real emitter, this test updates concurrently with the
   emitter landing — the regex pattern is intentionally narrow.
2. **`test_all_reason_codes_declared` is an enum-completeness contract
   pin.** Future additive ReasonCodes will require updating that
   expected set. Standard pattern.
3. **KI-NEW-P is calibration evidence pending — not a code defect.**
   The KI documents a knowledge gap (per-stage threshold validity
   against real merchant data), not a bug. S14 onboarding is the
   resolution window. No production behavior change required at S10
   close.
4. **Founder-deferred KI-NEW-Q / KI-NEW-R remain unfiled.** Per IM
   plan §D-T3 L415. If the founder later decides to file them, they
   will use letters Q and R respectively (next two unused letters
   after P).
5. **No fixtures touched.** No risk of fixture drift.

---

## 11. Deviation-check statement

**Deviation check: none.**

T3 ships exactly the four pieces specified by the dispatch brief +
IM plan §D-T3:
- Two dormant ReasonCode enum values with exact spec string values.
- New precedence invariant test file with ≥3 tests (shipped 4).
- `docs/engine_flags.md` augmentation with the three-orthogonal-gate
  ML-fit row + ranking-strategy fallback chain.
- KI-NEW-P filed (letter P, next available after KI-NEW-O); two
  sub-bullets included per spec; KI-NEW-Q / KI-NEW-R NOT filed.

Load-bearing companion: `tests/test_engine_run_schema.py`'s
`test_all_reason_codes_declared` expected-set updated to recognize the
two new members — mechanical follow-on to the enum addition (same
pattern as every prior additive ReasonCode landing per the existing
enum-completeness contract). Surfaced here for transparency.

No self-commit per founder protocol — orchestrator commits.

---

## 12. S10 sprint-close recommendation

T3 closes Sprint 10. The sprint-close commit should bundle:

1. **`memory.md` template-shape entry for S10-T3** (≤15 lines per
   `memory.md` L20-36 template). Fields:
   - Ticket: S10-T3
   - Date: 2026-05-26
   - Author: code-refactor-engineer + orchestrator
   - Status: SHIPPED
   - Files touched: 6 (3 modified src/test/docs + 2 modified KI/test
     + 1 new precedence test + 1 new summary)
   - Behavior change: schema-additive only; ML-fit dormancy pinned
   - Cross-link: this summary file
2. **`memory.md` Sprint 10 close entry** (≤15 lines): bundles T0,
   T1, T1.4, T1.5, T2, T2.5, T3 close. Cross-link to each ticket
   summary in `agent_outputs/`.
3. **`agent_outputs/INDEX.md` update** — add the S10-T3 summary file
   under the active sprint section, mark S10 as closed.
4. **`ROADMAP.md` update** — close S10 item; advance to S11 / S13
   per the active roadmap shape.
5. **`STATE.md` §4 update** — narrative tweak to reflect that the
   three orthogonal gates are now documented as "three (with a
   fourth dormant)" per the four-gate precedence locked at T3. No
   code-behavior change; documentation-only.
6. **`PIVOTS.md`** — no entry required (no direction change at T3;
   pure schema-additive + docs + KI). Skip unless founder asks
   otherwise.
7. **`ARCHITECTURE_PLAN.md`** — optional one-line append documenting
   the four-gate precedence lock. Founder/DS may prefer this lands
   in `docs/engine_flags.md` only (already done). Recommend SKIP at
   sprint-close unless DS specifically requests.

S10 sprint-close commit message recommendation:

```
S10-T3 + S10 sprint-close: ML-fit ReasonCode additions + four-gate precedence pin + KI-NEW-P

Adds two dormant ReasonCode enum values (MODEL_FIT_INSUFFICIENT_DATA,
MODEL_FIT_REFUSED) at src/engine_run.py — schema-additive within
event_version=1, no emitter wired at S10 close (S13 consumes). Pins
the DS-locked four-gate precedence
(audience-floor > cohort p-value > prior-validation > ML-fit) at
tests/test_reason_code_precedence_invariant.py. Documents the
three-orthogonal-gate (soon four) ML-fit row + ranking-strategy
fallback chain BG/NBD -> CF -> survival -> RFM -> recency at
docs/engine_flags.md. Files KI-NEW-P (ModelFitStatus stage-grid
threshold calibration suite) with two sub-bullets covering the
bgnbd_card=None orchestration edge case and the Beauty BG/NBD
failure-mode change across direct-CSV vs orchestration-load paths.

KI-NEW-Q and KI-NEW-R remain founder-deferred per IM plan §D-T3,
NOT filed at T3.

- src/engine_run.py: two new ReasonCode members + docstring documenting
  dormancy, S13 consumption, and the four-gate precedence.
- tests/test_reason_code_precedence_invariant.py: NEW. Four tests —
  enum existence, dormancy grep over src/, precedence ordering pin,
  str-Enum shape round-trip.
- tests/test_engine_run_schema.py: test_all_reason_codes_declared
  expected-set extended with the two new codes (mechanical follow-on
  to the enum addition, same pattern as every prior additive code).
- docs/engine_flags.md: new "S10 predictive layer — three-orthogonal-
  gate (soon four) ML-fit gate" section with precedence table +
  ranking-strategy fallback chain.
- KNOWN_ISSUES.md: KI-NEW-P filed; count table 18 -> 19 / 27 -> 28;
  last-updated line refreshed.
- agent_outputs/code-refactor-engineer-s10-t3-summary.md: NEW. T3
  receipt.

Briefing.html bytes preserved on all 5 pinned fixtures (renderer
does not touch the new codes; verified by targeted slate-regression
+ golden-diff suite — 66 passed + 2 xpassed). event_version stays
at 1. PlayCard untouched. No flag flips. No orchestration changes.
Single-demote-channel invariant preserved.

Deviation check: none.
```

---

**Deviation check: none.**
