# DS Architect — S11 Plan Review + `lifelines` Library Posture

**Date:** 2026-05-26
**Reviewer:** ecommerce-ds-architect
**Plan under review:** `agent_outputs/implementation-manager-s11-ml-part2-plan.md`
**Verdict:** **APPROVE WITH CHANGES**

---

## (a) S11 plan verdict — APPROVE WITH CHANGES

Cadence, scope decomposition, chained-refusal architecture, four-state mapping, parquet schemas, KI-NEW-P extension posture, single-demote-channel discipline, atomic-flip pattern, and Pivot 5 honest-synthetic posture all mirror S10 correctly. The plan is dispatchable after the changes below.

### Required changes before T1 dispatch

1. **Library posture (load-bearing — see §(b)).** The plan, ROADMAP.md, and `docs/DECISIONS.md` all use `lifelines` as the S11 library name. **The codebase ships `lifetimes` (BG/NBD library), not `lifelines` (survival library)** — two distinct PyPI packages from the same maintainer (Cam Davidson-Pilon). `requirements.txt` L4: `lifetimes==0.11.3`. `lifelines` is **not yet a dependency**. S11 is the first sprint that **actually adds `lifelines`**. The IM plan is correct to add it; my recommendation in §(b) revises the library choice for survival.

2. **C-index threshold floors (Q4).** The 0.65 VALIDATED / 0.55 PROVISIONAL floors are defensible against Steyerberg's "weak/fair/good" bands, but on per-customer DTC replenishment with only RFM covariates, a realistic VALIDATED C-index on a healthy merchant lands in the **0.62–0.68 band**, not 0.70+. Beauty especially won't clear 0.65 without a `sub_vertical` factor or coupon-recency covariate. **Recommendation:** lower the VALIDATED floor to **0.62 for startup/growth, 0.63 for mature/enterprise**, keep PROVISIONAL at 0.55, keep REFUSED at <0.55. Keep `min_events_absolute_floor: 30` theory-locked. DS-locked.

3. **C-index needs a calibration companion.** Per the G-G `holdout_agg_ratio` precedent (gating Spearman + operator-visible agg_ratio), add a **calibration check** that gates alongside C-index: **time-dependent Brier score at 90d ≤ 0.25** as a *secondary gate* (not operator-only). Pure rank discrimination (C-index) without calibration can ship a model that orders correctly but predicts wildly miscalibrated absolute times — and S13's `replenishment_due` consumer reads `expected_days_to_next_purchase` (a magnitude), not just rank. Without a calibration gate, PROVISIONAL/VALIDATED magnitudes are unsafe. DS-locked.

4. **CF recall@10 floors (Q4).** Top-K recall@10 is the right primary metric. The 0.08–0.15 stage-dependent VALIDATED floors are **too aggressive**. On a real ALS implicit-feedback matrix with K=10 neighbors and typical Beauty/Supplements catalog density (catalog size 200–2000 items, 5–15 avg orders per repeat customer), realistic recall@10 lands in the **0.04–0.10** band even on healthy data. **Recommendation:** lower VALIDATED floors to **{startup 0.05, growth 0.06, mature 0.08, enterprise 0.10}**; lower PROVISIONAL floor to 0.03. Keep `coverage_at_10` floors as proposed. DS-locked, with KI-NEW-P closure-criterion-evidence S14.

5. **Survival CHAINS on BG/NBD — adjudicated CORRECT, with a caveat.** The math is right: Cox PH hazard transforms the same gap-time signal BG/NBD evaluates, so a BG/NBD REFUSED on rank-skill noise means the gap distribution itself is uninformative. **BUT** there is one audit case worth preserving: **"BG/NBD VALIDATED + survival REFUSED"** is meaningful (BG/NBD ranks repeat propensity well, but Cox PH covariates don't add discriminative power → REFUSED on c_index<0.55). That story should be explicit in the T3 audit copy as a *valid orthogonal-failure case*, not a contradiction. The reverse — BG/NBD REFUSED → survival VALIDATED — should be impossible by chained-refusal construction, and that's the correct invariant. **No code change; T3 audit copy addition.**

6. **CF independent of BG/NBD — adjudicated CORRECT.** ALS interaction-matrix math is orthogonal to P(alive). Keep as planned.

7. **Per-customer survival unit (Q2) — adjudicated CORRECT.** Per-SKU survival is a different unwired play (`replenishment_due_per_sku`), forbidden by DS invariant 15 (no new Tier-B builders through S13). Pivot 5 forbids fabricating product-shaped audiences just because the math could. Lock per-customer.

8. **Look-alikes-only CF (Q1) — adjudicated CORRECT.** Item-affinity is reusable from the same factor matrices later; S11 ships customer-side only, matches S13's wired consumer (audience expansion). Lock.

9. **No S11-T0 (Q3) — adjudicated CORRECT.** I re-read `src/predictive/`, `src/main.py:971-1046`, `src/decide.py`, `src/guardrails.py`. No latent correctness debt analog to S10-T0's lineage-keyed fatigue bug. Greenfield substrate; no carry-over.

10. **`_coerce` bool set at T1/T2 not T1.5/T2.5 — adjudicated CORRECT.** S10-T1.5 lesson is binding. Plan §E.4 carries it forward correctly. Verify both flags in T1 / T2 dispatch briefs.

11. **Determinism comparator gets 2 new fit_timestamp paths — flagged correctly (§E.3).** No change needed.

12. **No new ReasonCode at S11 — adjudicated CORRECT.** S10-T3 codes (`MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`) cover survival + CF.

13. **Pivot 5 / Option γ extends — confirmed.** Honest synthetic posture predicts 5/5 REFUSED or INSUFFICIENT_DATA across both substrates. The plan correctly anticipates and does not reshape fixtures. Real VALIDATED evidence comes from S14.

14. **Three-channel single-demote-channel invariant preserved — confirmed.** New blocks write only to `engine_run.predictive_models`. No edits to `src/main.py:1380-1597` (KI-NEW-L S13.5).

15. **Beauty-replenishment_due dormancy audit story (§B.8) — adjudicated CORRECT but tighten copy.** T3 audit copy for `docs/engine_flags.md` should read: "INSUFFICIENT_DATA on Beauty's first 90 days is EXPECTED — repeat-purchase events haven't accumulated; this is product correctness, not a calibration failure." Plan §B.8 has this; lock the copy verbatim before T3 dispatch.

---

## (b) `lifelines` library — current usage, maintenance state, S11 recommendation

### 2.1 Current usage in the codebase

**Verified by grep of `src/`:**

| File | Import | Purpose |
|---|---|---|
| `src/predictive/bgnbd.py:339` | `from lifetimes import BetaGeoFitter` | BG/NBD fit (S10) |
| `src/predictive/gamma_gamma.py:336` | `from lifetimes import BetaGeoFitter` | BG/NBD param re-fit inside G-G holdout (S10-T2) |
| `src/predictive/gamma_gamma.py:536` | `from lifetimes import GammaGammaFitter` | Gamma-Gamma fit (S10) |

**`lifelines` is NOT imported anywhere in `src/` today.** It is referenced in *docs* (`docs/DECISIONS.md`, ROADMAP.md, engine_flags.md, the IM plan), but the only `lifelines`-test reference is a **banned-modules contract** at `tests/test_s6_5_t3_cadence_seasonality.py:166` that bans `lifelines` from `src/profile/cadence.py`. **`requirements.txt` pins `lifetimes==0.11.3`; no `lifelines` pin.**

This is critical: the founder is asking about a library that the engine **does not yet depend on**. S11 is the first sprint that would add it.

### 2.2 Current support / maintenance state

Both `lifetimes` and `lifelines` are maintained (or were) by Cam Davidson-Pilon. As of training data (Jan 2026 cutoff):

- **`lifelines`** (survival): historically active; ~2,300 stars; releases through 2023; the maintainer explicitly stated reduced personal maintenance around 2022–2023, asking for community help. The library is **mature and stable** — Cox PH math hasn't moved in 50 years — but the **release cadence has slowed significantly**. New scipy / numpy compatibility breakages have historically taken months to patch. The `scipy<1.13` pin we already carry from S10 is itself evidence that this maintenance lag is real.
- **`lifetimes`** (BG/NBD): same maintainer, same posture; pinned to `==0.11.3` precisely because newer scipy breaks the optimizer paths. Long-tail maintenance.

**KI-NEW-R rationale (re-stated):** vendor-fork escape hatch for `lifelines`. The math is from 1972 (Cox) and is fully derivable from `scipy.optimize` in ~200 lines. If `lifelines` becomes unmaintained or incompatible with a forced scipy upgrade, vendor-forking the 2–3 fitters we need is a 1–2 day operation, not a beta-blocker. Same argument applies to `lifetimes`.

### 2.3 Fallback options

**For BG/NBD + Gamma-Gamma (already shipped, S10):**
- **`pymc-marketing`** (PyMC Bayesian framework) — actively maintained by PyMC Labs. Pros: clean API, full posteriors. Cons: PyMC is a heavyweight dependency (theano/pytensor compile-graph), slower fits, install complexity (especially on mac ARM with BLAS). Not a 1:1 drop-in.
- **Vendor-fork `lifetimes`** — 2–3 fitter classes, ~500 lines total. Math is from Fader/Hardie 2005, stable. Cost: ~2 days. Recommended fallback.
- **Roll our own via `scipy.optimize`** — feasible but redundant with the vendor-fork option above.
- **`btyd`** / **`PyBTYD`** — community forks of `lifetimes` exist; quality varies; not stable enough to rely on.

**For Cox PH (S11 new surface):**
- **`scikit-survival`** — actively maintained, sklearn-API, integrates with sklearn cross-validation, ships `CoxPHSurvivalAnalysis` + `concordance_index_censored`. **This is the modern alternative.** Maintained by Sebastian Pölsterl. Releases through cutoff. Pin to recent version; `scipy<1.13` compatibility should be verified at install time.
- **`pysurvival`** — exists; significantly less active than `scikit-survival`; not recommended.
- **`pycox`** — deep-learning survival; overkill, violates D-6 (peer-reviewed-classical only).
- **`statsmodels.duration`** — already in requirements; has a Cox PH implementation (`PHReg`). **Underrated option** — already a dependency, no new install, no maintenance risk.
- **Raw `scipy.optimize` Cox partial likelihood** — feasible (~150 lines including C-index), but unneeded with the above options.

### 2.4 Recommendation — Option (b): use `scikit-survival` for Cox PH; keep `lifetimes` for BG/NBD + G-G; document the dual surface

**Justifications:**

1. **Beta-blocking risk.** Option (c) (refactor S10's BG/NBD + G-G off `lifetimes`) re-opens an atomic flip that already shipped successfully. Touching `src/predictive/bgnbd.py` + `gamma_gamma.py` mid-beta-blocking-sequence with merchant onboarding 4 sprints away is unjustified risk for zero S11 benefit. **Defer S10 library refactor to post-beta (S15+).**

2. **DS-architecture correctness.** `lifelines` and `lifetimes` are different libraries with different math heritage. There is no "consistency" argument from using `lifelines` for Cox PH just because we use `lifetimes` for BG/NBD — they share a maintainer but they are independent packages with independent maintenance risk. The "same parent ecosystem" framing in the IM plan §B.2 and Q6 is misleading.

3. **Maintenance debt.** `scikit-survival` is more actively maintained than `lifelines` and has a stronger institutional backer (the sklearn ecosystem); adopting it for the new survival surface reduces future maintenance debt. It also gives the engine an exit strategy from `lifetimes` later (S15+) onto sklearn-ecosystem ML if we ever consolidate.

4. **Cost of carry-forward.** Adding `scikit-survival` instead of `lifelines` is a same-day decision at S11-T1 — no code exists yet for survival. The cost is zero. Carrying forward `lifelines` would add a *second* package with the same long-tail-maintenance risk as `lifetimes`.

5. **`scipy<1.13` compatibility — verify at T1 commit-1.** `scikit-survival` recent versions are compatible with scipy 1.10–1.12 (within our pin window). The dispatch brief should require this as a commit-1 smoke test, mirroring the S10-T1 lesson.

6. **API simplicity for our use case.** Cox PH + C-index + per-customer hazard predictions: `scikit-survival`'s `CoxPHSurvivalAnalysis` + `predict_survival_function` + `concordance_index_censored` is a 30-line fit-and-evaluate flow. Same complexity as `lifelines.CoxPHFitter`.

**Migration plan for S11 (changes to IM plan):**

- Replace `lifelines==<pin>` with **`scikit-survival>=0.22,<0.24`** (or current stable) in §H modified files.
- Replace `lifelines.CoxPHFitter` references in §B.2 with `sksurv.linear_model.CoxPHSurvivalAnalysis`.
- C-index source: `sksurv.metrics.concordance_index_censored` (returns C-index + counts of concordant/discordant pairs; richer than `lifelines.utils.concordance_index`).
- Time-dependent Brier source (per change-3 above): `sksurv.metrics.integrated_brier_score`.
- KI-NEW-Q extension at S11-T3: scope becomes `{lifetimes, scikit-survival, implicit}` maintenance posture. Vendor-fork escape hatches: `lifetimes` (BG/NBD math vendor-forkable in ~2 days); `scikit-survival` (Cox PH math vendor-forkable in ~1 day via `scipy.optimize`); `implicit` (ALS vendor-forkable in ~3 days, but BLAS-bound — accept dependency risk).
- ROADMAP.md §1 L13 and §2 L42 to be updated at S11-T3 close from "`lifelines`" to "`scikit-survival`". `docs/DECISIONS.md` D-FLOOR-replenishment_due footnote to record the substitution rationale.

**Fallback if `scikit-survival` install fails on mac ARM (unlikely but possible):** use **`statsmodels.duration.PHReg`** (already a dependency — zero new install). Statsmodels is well-maintained and Cox PH is in scope. API is older-style but works. This is the "no new dependency at all" fallback the founder may prefer.

### 2.5 Founder-actionable summary (3 sentences)

`lifelines` is **not used anywhere in the engine today** — `requirements.txt` ships `lifetimes==0.11.3` (BG/NBD, by the same maintainer), which is in long-tail maintenance and pinned defensively against scipy 1.13. Both `lifetimes` and `lifelines` are mature-but-slow-moving libraries from one maintainer; the vendor-fork escape hatch (KI-NEW-R) remains the correct posture for `lifetimes`, and I am **recommending S11 adopt `scikit-survival` instead of `lifelines`** for the new Cox PH surface — better-maintained, sklearn-ecosystem-backed, and zero refactor cost since no survival code exists yet. Do **not** refactor S10's BG/NBD + G-G off `lifetimes` now (beta-blocking risk for zero S11 benefit); revisit consolidation post-beta at S15+ when AWS migration revisits the dependency surface.

---

## (c) Product-level escalations for the founder

1. **Library substitution `lifelines` → `scikit-survival`.** Per §(b) above. Requires founder ack to update ROADMAP §1 L13 + §2 L42 verbatim text and `docs/DECISIONS.md` D-FLOOR-replenishment_due footnote at S11-T3 close. Low-risk substitution; DS recommending under DS authority and surfacing for founder sign-off because the doc text is founder-quoted.

2. **C-index VALIDATED floor at 0.62–0.63 (not 0.65).** DS-locked per §(a) change 2. Surface to founder because the IM plan documented 0.65 as the default and DS is revising it.

3. **Add Brier-score@90d ≤ 0.25 as a secondary survival gate.** DS-locked per §(a) change 3. New gate field on ModelCard alongside C-index. Surface to founder because this is an additive gating contract beyond what the plan proposed.

4. **CF recall@10 VALIDATED floors lowered to {0.05, 0.06, 0.08, 0.10} per stage.** DS-locked per §(a) change 4. Surface to founder.

5. **No S11-T0.** Confirmed.

6. **Item-affinity (cross-sell) at S11 — declined.** Look-alikes only, consistent with IM Q1. Item-side artifact can be added in a later sprint without re-fitting ALS.

---

## (d) Adjudication of the 6 IM open questions

| # | IM recommendation | DS verdict |
|---|---|---|
| Q1 — CF scope (look-alikes only vs also product-affinity) | Look-alikes only at S11 | **CONFIRM look-alikes only.** Reasons in §(a) change 8. |
| Q2 — Survival granularity (per-customer vs per-customer-per-SKU) | Per-customer only | **CONFIRM per-customer only.** Per-SKU would require a new Tier-B builder, violating DS invariant 15. |
| Q3 — S11-T0 analog | No analog | **CONFIRM no S11-T0.** Audited `src/predictive/`, `src/main.py:971-1046`, `src/decide.py`, `src/guardrails.py`; no correctness debt parallel to S10-T0. |
| Q4 — DS sign-off on c_index and recall@10 floors | Confirm in-loop at T1/T2 DS reviews | **REVISE FLOORS NOW (do not defer):** c_index VALIDATED 0.62/0.63 (not 0.65); PROVISIONAL 0.55; recall@10 VALIDATED {0.05, 0.06, 0.08, 0.10} per stage; PROVISIONAL 0.03. Add Brier@90d ≤ 0.25 as secondary survival gate. T1 dispatch brief carries these revised numbers verbatim. |
| Q5 — ModelCard field-growth posture | Acceptable additive; revisit refactor at S12 | **CONFIRM additive at S11.** At S12 if RFM + retention adds 3+ more optional fields, refactor to `Dict[str, float] metrics` shape. Plan ahead, do not act at S11. |
| Q6 — `lifelines` vs `scikit-survival` | Stay with `lifelines` for ROADMAP consistency | **OVERRIDE: use `scikit-survival`.** Full reasoning in §(b). The "ROADMAP consistency" / "maintainer-lineage continuity" arguments do not hold up — `lifelines` and `lifetimes` are separate packages with independent maintenance risk. `scikit-survival` is the modern, better-maintained Cox PH library. Zero refactor cost (no survival code exists yet). Update ROADMAP / DECISIONS.md text at S11-T3 close. |
