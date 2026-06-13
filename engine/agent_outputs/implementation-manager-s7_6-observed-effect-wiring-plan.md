# Sprint 7.6 — Observed-Effect Wiring Implementation Plan

**Branch base:** `post-6b-restructured-roadmap` (current)
**Status convention:** S7.6-T{n} = code-behind-flag (default OFF); S7.6-T{n}.5 = flag flip + atomic fixture re-pin.
**Role discipline:** orchestrator dispatches one ticket per code-refactor-engineer turn; commits from staged only.

---

## 1. Sprint Goal

Finish the second half of every Tier-B builder spec by computing a per-store recent-vs-prior observed effect (z-test for proportions, Welch-t for AOV, multi-window sign agreement across {L28, L56, L90}) and threading `(observed_k, observed_n)` into the existing prior-anchored card seam. EB blend math (`src/sizing.py`) stays untouched; success is that posterior moves toward store data as `n` grows while cold-start (`n=0`) remains prior-only. Eligibility for emission gates on sign-agreement; copy templates rotate by 3-state posterior-ratio ladder (cold/accumulating/mature). Threshold-from-data (T3.5) lands independently as a hygiene fix.

---

## 2. Ticket Sequence & Dependency Graph

```
T0  shared helper  ──┬─► T1 winback (B-1)    ──► T1.5 flip
                     ├─► T2 replenish (B-2)  ──► T2.5 flip   [Beauty only]
                     ├─► T3 discount (B-3)   ──► T3.5 flip   [Beauty only]
                     ├─► T4 journey  (B-4)   ──► T4.5 flip   [Berkson-pinned]
                     └─► T5 aov_bundle (B-5) ──► T5.5 flip

T6  eligibility-gate + copy-ladder  (depends on >=2 builders wired; lands after T2.5)
T6.5  flip ENGINE_V2_OBSERVED_ELIGIBILITY_GATE

T7   threshold-from-data hygiene  (INDEPENDENT — can run in parallel with T0..T5)
T7.5 flip

T8   (optional) docs/KI sweep + S8-T1 readiness sign-off
```

**Critical path:** T0 -> T1 -> T1.5 (proves end-to-end wiring works on the simplest builder before fan-out).
**Parallelizable after T0:** T2/T3/T4/T5 implementations (separate files, independent fixtures); each `.5` flip is serialized to avoid fixture-pin races.
**T7 (threshold-from-data)** has no dependency on T0; can land any time.

---

## 3. Per-Ticket Specs

### T0 — Shared observed-effect helper
- **Scope:** new module `src/measurement_observed.py` exporting `compute_two_proportion_observed(recent_k, recent_n, prior_k, prior_n) -> dict{effect, n, p_value, sign}` and `compute_multi_window_sign_agreement(per_window: dict[str, result]) -> dict{sign_agreement_count, dominant_sign, windows}`. Welch-t variant `compute_welch_t_observed(recent_values, prior_values)` exported same shape.
- **Files:** new `src/measurement_observed.py`; no edits elsewhere.
- **Flags:** none (pure helper).
- **Acceptance:** unit tests cover (a) `n=0` short-circuits returning `effect=0, n=0`; (b) sign convention matches z-test (positive = recent>prior); (c) `p_value` matches scipy reference within 1e-6; (d) Welch handles unequal variances and `n<2` short-circuit.
- **Tests:** `tests/test_measurement_observed.py` (new) ~12 cases.
- **Schema:** none.
- **Fixture re-pin:** none (not wired in).
- **Dependencies:** none.

### T1 — B-1 winback_dormant_cohort observed effect
- **Scope:** in `src/measurement_builder.py` winback path, compute `lapse_recovery_rate_l28` (recent 28d returners from dormant cohort) vs prior-28d anchored 28d earlier on the **same dormant cohort definition**. Call helper across {L28, L56, L90}. Thread `observed_k=recent_k, observed_n=recent_n` into `build_prior_anchored_play_card(...)`. Stash sign-agreement in card's measurement payload only (no copy change yet).
- **Files:** `src/measurement_builder.py` (winback builder only).
- **Flag:** new `ENGINE_V2_OBSERVED_WINBACK` default OFF in `src/utils.py` DEFAULTS.
- **Acceptance:** when flag OFF, card sha256 byte-identical to current Beauty/supplements; when flag ON in unit test, `observed_n > 0` on Beauty fixture and `posterior != prior` when `n >= 30`.
- **Tests:** extend `tests/test_s6_t1_winback_dormant_cohort.py` with flag-on/off parity + observed-effect cases; cohort definition identity test (same dormant_at boundary recent vs prior).
- **Fixture re-pin (T1.5):** Beauty + supplements re-pin; sha256 documented in commit.
- **Deps:** T0.

### T1.5 — flag flip
- Flip `ENGINE_V2_OBSERVED_WINBACK=ON`. Re-pin Beauty + supplements fixtures atomically. M0 goldens must stay byte-identical (winback not emitted in M0 small_sm/mid_shopify/micro_coldstart — verify in PR description).

### T2 — B-2 replenishment_due observed effect (Beauty only)
- **Scope:** compute `due_cohort_reorder_rate_l28` recent-vs-prior on the L90 due-cohort denominator. Supplements path remains feature-gated behind existing KI-27 parser block.
- **Files:** `src/measurement_builder.py` replenishment path.
- **Flag:** `ENGINE_V2_OBSERVED_REPLENISH` default OFF.
- **Acceptance:** Beauty fixture emits `observed_n > 0`; supplements still emits with `observed_n = 0` (KI-27 deferred); flag-off byte-identical.
- **Tests:** extend `tests/test_s6_t3_replenishment_due_builder.py`; explicit supplements-skip assertion citing KI-27.
- **T2.5:** flip + Beauty re-pin (supplements unchanged, document why).
- **Deps:** T0.

### T3 — B-3 discount_dependency_hygiene observed effect (Beauty only)
- **Scope:** revenue-weighted two-proportion z-test on `heavy_discount_share_of_revenue_l28` recent-vs-prior. Supplements Path-D dormant per DS Memo-4.
- **Files:** `src/measurement_builder.py` discount path.
- **Flag:** `ENGINE_V2_OBSERVED_DISCOUNT_HYGIENE` default OFF.
- **Acceptance:** revenue-weighting unit test (heavy orders contribute by `gross_revenue`, not order-count); Beauty emits `observed_n > 0`; supplements untouched.
- **Tests:** extend `tests/test_s7_t1_discount_dependency_hygiene_builder.py`.
- **T3.5:** flip + Beauty re-pin.
- **Deps:** T0.

### T4 — B-4 cohort_journey_first_to_second observed effect (Berkson-protected)
- **Scope:** cohort first-to-second rate on **early-half-window denominators** (per `project_journey_p_zero.md` and existing `tests/test_berkson_invariant.py`). MUST route through existing `calculate_journey_stats_single_window` — do not bypass.
- **Files:** `src/measurement_builder.py` journey path.
- **Flag:** `ENGINE_V2_OBSERVED_JOURNEY` default OFF.
- **Acceptance:** `tests/test_berkson_invariant.py` still passes; new test asserts denominator = early-half cohort count, not full-window count.
- **Tests:** extend `tests/test_s7_t2_cohort_journey_first_to_second_builder.py`; explicit Berkson regression test re-run.
- **T4.5:** flip + Beauty re-pin.
- **Deps:** T0.

### T5 — B-5 aov_lift_via_threshold_bundle observed effect (dual test)
- **Scope:** Welch-t on audience-level L28 AOV (recent vs prior) **AND** two-proportion z-test on threshold-band share. **Both** must reach p<0.10 to set `eligible_observed=True`. Emit both p-values into card measurement payload.
- **Files:** `src/measurement_builder.py` aov_bundle path.
- **Flag:** `ENGINE_V2_OBSERVED_AOV_BUNDLE` default OFF.
- **Acceptance:** dual-test combiner unit test (only-one-passes => `eligible_observed=False`); Beauty fixture emits both p-values.
- **Tests:** extend `tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py`.
- **T5.5:** flip + Beauty re-pin.
- **Deps:** T0, T7 (uses data-driven threshold once available; if T7 not yet merged, falls back to `cfg` threshold — wire is independent but threshold quality matters).

### T6 — Eligibility gate + copy ladder
- **Scope:** at prior-anchored card seam, when `observed_n > min_eligibility_n` (default 30, plumbed via `cfg["OBSERVED_MIN_ELIGIBILITY_N"]` already present or new) **and** `sign_agreement_count < 2`, downgrade card to Considered with reason `OBSERVED_SIGN_DISAGREEMENT`. Rotate why-now copy by 3-state ladder driven by `posterior_ratio = observed_n / (observed_n + prior_effective_n)`: cold (<0.2) / accumulating (0.2-0.6) / mature (>0.6). No new rendering surface — reuse existing why-now slot.
- **Files:** `src/measurement_builder.py` card-build seam (or thin wrapper); copy strings centralized in `src/measurement_builder.py` constants.
- **Flag:** `ENGINE_V2_OBSERVED_ELIGIBILITY_GATE` default OFF.
- **Acceptance:** sign-disagreement test (synthetic builder output with opposing-sign windows at n=200 -> Considered, reason set); cold-start parity (n=0 -> prior copy, identical to today).
- **Tests:** new `tests/test_observed_eligibility_gate.py`; new `tests/test_observed_copy_ladder.py` (3 states + boundary tests).
- **T6.5:** flip + Beauty + supplements re-pin.
- **Deps:** at least T1.5 + T2.5 landed (need >=2 wired builders to validate gate behavior in fixtures).

### T7 — Threshold-from-data (independent hygiene fix)
- **Scope:** `src/audience_builders.py:955-966`: `threshold = np.percentile(L90 net_sales, 60)` primary; fall back to `cfg["AOV_BUNDLE_THRESHOLD_USD"]` only when L90 order count < 200; emit `data_missing` only when both fail.
- **Files:** `src/audience_builders.py` (single block).
- **Flag:** `ENGINE_V2_AOV_THRESHOLD_FROM_DATA` default OFF.
- **Acceptance:** unit test with `len(L90)=50` -> uses cfg fallback; `len(L90)=500` -> uses percentile; empty L90 + missing cfg -> `data_missing`.
- **Tests:** extend `tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py`.
- **T7.5:** flip + Beauty re-pin (audience size may shift -> downstream cards may shift -> document sha256).
- **Deps:** none (parallel-safe with T0..T5).

### T8 — S8-T1 readiness sign-off (no code)
- KNOWN_ISSUES.md sweep, memory.md update, S8-T1 entry criteria checklist, founder fixture-density review trigger.

---

## 4. Risk Register

**(a) Sign-disagreement at non-trivial n.** Card does **not** vanish; it downgrades to Considered with `OBSERVED_SIGN_DISAGREEMENT` reason. This preserves explainability (founder sees engine saw conflicting evidence) and avoids the "engine went silent" failure mode. Hard-vanish only if `eligibility_gate` flag is later tightened — out of S7.6 scope.

**(b) Fixture re-pin cascade.** Each `T*.5` flip re-pins Beauty (and supplements where applicable) atomically with the flip commit, per S7 convention (`45edaca5` model). M0 goldens (small_sm, mid_shopify, micro_coldstart) must remain byte-identical because Tier-B builders are not in the M0 small-fixture surface; CI must assert this. Mitigation: PR template line "M0 sha256 unchanged: yes/no — if no, escalate."

**(c) Synthetic fixture signal density.** Real risk: Beauty/supplements fixtures may not have enough recent-vs-prior delta to push `observed_n` past `min_eligibility_n=30` or generate sign-agreement on >=2 windows. **Detection:** T1.5 PR description must report Beauty `observed_n` and sign-agreement count for the wired builder. If <30 or `sign_agreement<2` on the fixture, flag for founder synthetic-data regeneration (new ticket S7.6-T-FX) **before** proceeding to T2/T3/T4/T5 flips. Do not paper over with smaller `min_eligibility_n` defaults.

**(d) Berkson regression on T4.** Existing `tests/test_berkson_invariant.py` is the tripwire; T4 PR fails to merge if that test breaks. No flag-flip-time waiver.

**(e) T5 dual-test combiner brittleness.** Welch-t and z-test on small Beauty audiences may both fail p<0.10 -> card stays prior-only. Acceptable; document expected behavior in T5 acceptance.

---

## 5. Sprint Exit Criteria

- Test suite: current 1168p/14s/0f -> target ~1220p+/14s/0f (T0:12, T1:4, T2:4, T3:4, T4:4, T5:6, T6:10, T7:4, plus parity tests).
- All 5 Tier-B builders thread non-zero `observed_n` on Beauty fixture (supplements: B-1 only; B-2/B-3 dormant per KI-27 / Memo-4).
- Beauty fixture re-pinned 5x (one per `T*.5`); supplements re-pinned 1x (T1.5).
- M0 goldens unchanged across the sprint.
- Eligibility gate live with sign-disagreement downgrade path covered.
- KNOWN_ISSUES.md count: open KI 11 -> 9 (close threshold-from-data + observed-wiring KIs).
- **S8-T1 ready** = every Recommended/Experiment card on a Beauty run shows either (1) cold-start prior copy with `posterior_ratio<0.2`, or (2) blended copy with documented `observed_n > 0` and 3-state ladder string.

---

## 6. What Stays Unchanged (auditable no-touch surface)

- `src/sizing.py` — EB blend math.
- Priors YAML files + DS Memos 1-4.
- Decide layer: `src/decide.py`, role-uniqueness invariant, slate selector (Phase 6A/6B).
- Renderer slate logic: Recommended Experiment, opportunity_context, considered filter (B-series).
- `src/utils.py` DEFAULTS block other than additive flags listed above.
- M0 goldens (small_sm, mid_shopify, micro_coldstart).
- `recently_run` fatigue gate (still OFF per Sprint 1 B-4).
- `src/memory/events.py` schema (frozen for Swarm per Sprint 2 S-3).
- Recommended-history JSON format.
- `state_of_store.py` supplements nested-key fix (S5-T1).
- `tests/test_berkson_invariant.py` — tripwire only, not edited.

---

## 7. Deferred (post-S7.6)

- **Supplements B-2 observed-effect** — blocked on KI-27 supplements replenishment parser. Resurface after KI-27 ticket lands.
- **Supplements B-3 observed-effect** — blocked on DS Memo-4 Path-D activation work; explicit non-goal here.
- **subscription_nudge observed-effect** — Phase 4.2 deferred per `project_phase4_subnudge_open.md` (multiplier vs baseline-rate conflation + survivorship bias unresolved); out of scope.
- **routine_builder observed-effect** — Phase 4.2 deferred per `project_phase4_routine_builder_open.md` (Welch-t produces p-value only, no effect-unit coherence); out of scope.
- **Hard-vanish on sign-disagreement** — S7.6 downgrades to Considered; hardening to suppression is an S8 product call.
- **4th ladder state (mature+contradiction)** — DS proposed 3-state; expanding to 4-state requires founder copy review, deferred.
- **Recently-run fatigue flag flip** — independent of observed-effect, stays OFF.
- **Outcome-log feedback loop wiring** — separate Swarm-era epic.
