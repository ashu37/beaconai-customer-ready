# DS Architect Follow-Up Verdict — S8-T0 SciPy Percentile Sanity Check (2026-05-24)

**Date:** 2026-05-24 (same day as parent verdict, post-S8-T0 commit `77086fd`)
**Author:** ecommerce-data-science-architect
**Parent verdict:** `agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md`
**Decision scope:** Sanity-check the actual SciPy Beta-percentile values that landed in `config/priors.yaml` at commit `77086fd` vs the analytic ballpark in §3 of the parent verdict. Four narrow questions.
**Status:** All four questions decided. Engine behavior is correct as-shipped; one verdict-file addendum recommended (orchestrator applied separately).

---

## Context

Commit `77086fd` re-fit Beauty `discount_dependency_hygiene.base_rate.beauty` + `replenishment_due.base_rate.beauty` from defective Beta(0.66, 29.34) to Beta(1.32, 58.68) per parent verdict §3 + §6 F1.

The refactor agent computed exact percentiles via `scipy.stats.beta(1.32, 58.68).ppf([0.10, 0.50, 0.90])` → `[0.0036879681, 0.0169462728, 0.0470907418]`.

**Divergence from parent verdict §3 analytic ballpark:**
- p10: 0.0037 (ballpark 0.0040) — −7.5%
- p50: 0.0169 (ballpark 0.0182) — −7.1%
- p90: 0.0471 (ballpark 0.0443) — +6.3%

Two of three are outside the "~5% tolerance" cited in the parent verdict. This follow-up verifies that the SciPy values are mathematically correct, confirms engine behavior is correct as-shipped, and amends the parent verdict for future-reader transparency.

---

## Q1. Is the SciPy-vs-analytic divergence acceptable?

**ACCEPT-AS-SHIPPED.** The "~5% tolerance" phrasing in parent verdict §3 was casual, not load-bearing — the instruction to defer to SciPy as authoritative was the load-bearing part, and the refactor agent honored it.

The divergence does flag a methodological lesson worth recording: **for Beta(α, β) with α just barely above 1 (the J-shape transition region), the median-to-mean gap is larger than mild-skew intuition suggests**. Next time the DS architect gives an analytic ballpark for percentiles of a low-α Beta prior, skewness must be computed explicitly and median adjusted downward accordingly. No engine action required.

---

## Q2. Are the SciPy values mathematically correct for Beta(1.32, 58.68)?

**CONFIRMED.** Independent verification math below.

For Beta(α=1.32, β=58.68):

- **Mean** = α / (α + β) = 1.32 / 60 = **0.02200** ✓ (matches `value` in YAML).
- **Mode** = (α − 1) / (α + β − 2) = 0.32 / 58 = **0.00552**. Since α > 1, the distribution is unimodal (J-shape defect resolved, as memo claims). Mode (0.0055) ≪ mean (0.0220) means **strong right-skew**, not mild.
- **Variance** = αβ / [(α+β)² · (α+β+1)] = (1.32 · 58.68) / (3600 · 61) = 77.4576 / 219,600 = **0.0003527**. SD = **0.01878**.
- **Skewness** = 2(β − α)√(α + β + 1) / [(α + β + 2)√(αβ)] = 2(57.36)(7.81) / (62 · √77.46) = 895.9 / (62 · 8.801) = 895.9 / 545.7 = **1.642**.

A skewness of 1.64 is substantial right-skew. Median should sit well below the mean, not near it.

**Median check via the Beta-specific approximation** `(α − 1/3) / (α + β − 2/3)`:
- (1.32 − 0.333) / (60 − 0.667) = 0.9867 / 59.333 = **0.01663**
- SciPy reports 0.01695 — within 2% of the analytic approximation. ✓

**p90 tail check:** Gaussian-equivalent (mean + 1.28·SD) = 0.0220 + 0.0240 = 0.0460. Gaussian underestimates the upper tail of a right-skewed distribution, so true p90 should be modestly higher. SciPy's 0.0471 fits. ✓

**p10 tail check:** With strong right-skew and α just above 1, the density rises steeply from 0, peaks at mode (0.0055), then has a long right tail. Ten percent of mass should sit below a value somewhere between 0 and the mode. SciPy's 0.0037 (below the mode at 0.0055) is consistent with the near-J shape just past the unimodal threshold. ✓

**Conclusion: SciPy values (0.0037, 0.0169, 0.0471) are mathematically correct.** The parent verdict's analytic ballpark p50 (0.0182) was wrong by ~7% because it implicitly treated the distribution as closer-to-symmetric than it actually is at α≈1.32. The true median sits ~23% below the mean, not ~17% as the ballpark estimated.

---

## Q3. Does the new envelope shape change any S14-readiness invariant?

**NO INVARIANT CHANGE.** All 10 S14-readiness invariants from parent verdict §5 hold unchanged.

The p90/p10 ratio widening from 11.1 to 12.7 is a relative-spread artifact of the right-skew, not a substantive change in prior informativeness. Specifically:

- The small-merchant-evaluated-honestly math (parent verdict §1 third bullet) depends on `effective_n=60` and the blend formula `w_obs = n_obs / (n_obs + 60)`. Neither the pseudo-count nor the blend math is affected by the percentile-shape correction.
- Crossover thresholds are unchanged: `n_obs` where `w_obs = 0.5` → `n_obs = 60`; where `w_obs = 0.9` → `n_obs = 540`.
- The observed-effect dominance at `n_obs = 224,077` (`w_obs = 0.99987`) makes the prior envelope shape essentially irrelevant in production for `discount_dependency_hygiene` today.
- The wider envelope **only matters for plays with small `observed_n`**, where it makes the prior slightly more diffuse. **This is directionally safer** (less prior bias, wider honest uncertainty), not less safe. The founder's "evaluated honestly for each merchant" criterion is preserved or strengthened, not weakened.

---

## Q4. Should the original verdict file be amended?

**AMEND VERDICT FILE.** Future readers comparing the parent verdict to the YAML would otherwise wonder why numbers don't match. The amendment is a one-block addendum at the end of §3 of the parent verdict.

**Exact addendum text** (orchestrator applied to parent verdict file separately):

```
---
ADDENDUM (2026-05-24, post-S8-T0 commit 77086fd):
SciPy-authoritative percentiles computed by the refactor agent are
(p10, p50, p90) = (0.0037, 0.0169, 0.0471), shipped to config/priors.yaml
lines 366-367 and 1113-1114. These supersede the analytic ballpark
(0.0040, 0.0182, 0.0443) per the "SciPy values are authoritative" instruction
in this verdict. Divergence (6-8%) traced to under-modeling right-skew at
alpha=1.32 (mode 0.0055, skewness 1.64); SciPy values verified independently
via Beta median approximation (alpha-1/3)/(alpha+beta-2/3) = 0.01663.
No S14-readiness invariant impact; production dollar delta < 0.1% at
observed_n=224,077 (w_obs = 0.99987). See follow-up DS verdict
agent_outputs/ecommerce-ds-architect-s8-t0-scipy-percentile-followup-2026-05-24.md.
---
```

---

## Cross-references

- `agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md` §3 (parent verdict, analytic ballpark) + §3 ADDENDUM (this follow-up's amendment).
- `config/priors.yaml` lines 366-367 (`discount_dependency_hygiene.base_rate.beauty` SciPy values) and lines 1113-1114 (`replenishment_due.base_rate.beauty` SciPy values).
- `config/priors_sources/discount_dependency_hygiene__base_rate__beauty.md` + sibling `replenishment_due__base_rate__beauty.md` (memos document SciPy-authoritative posture).
- Commit `77086fd` (S8-T0; KI-NEW-K resolved).
- `src/sizing.py:87-91` (`PSEUDO_N_BY_STATUS` locked table; unaffected by this follow-up).
- `src/sizing.py:131-139` (`effective_pseudo_n`'s `min(cap, profile_default)` discipline; unaffected).

---

## Methodological lesson recorded for future DS-architect work

For Beta(α, β) priors with α in the [1.0, 2.0] range (the J-shape transition region), median-to-mean gap is larger than mild-skew intuition predicts. When giving analytic percentile ballparks:
- Compute skewness explicitly: `skew = 2(β-α)√(α+β+1) / [(α+β+2)√(αβ)]`.
- Adjust median estimate downward proportionally to skewness.
- Better: use the Beta-specific median approximation `(α-1/3)/(α+β-2/3)` which is accurate to within ~2% for `α > 1`.
- Or simply defer to SciPy from the start, which is what the parent verdict ultimately did via the "SciPy values are authoritative" instruction.

**End of follow-up verdict.** Engine behavior at commit `77086fd` is correct as-shipped. KI-NEW-K stays closed. S8-T1 dispatch remains unblocked.
