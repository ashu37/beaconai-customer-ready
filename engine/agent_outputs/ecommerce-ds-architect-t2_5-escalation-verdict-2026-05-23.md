# T2.5 Escalation Verdict — DS Architect

**Date:** 2026-05-23
**Author:** ecommerce-ds-architect
**Scope:** Verdict-only. No code edits. Responds to atomic-flip probe empirical findings.

---

**Option (i) — Lower the growth-stage cell further (e.g., 12 → 5-8). REJECT.** The prior scope card (`agent_outputs/ecommerce-ds-architect-t2_5-floor-scope-card-2026-05-22.md` Q5) framed N≈10 as retaining "the spirit of a small handful of repeat-buyers to estimate a median that isn't a coin-flip." There is no clean statistical citation that puts the floor below this — the normal-approximation rule of thumb (N≥30) is the textbook source, and N=10 already departs from it on ICP-realism grounds. Below N≈8 the empirical median of inter-purchase gaps becomes a near-coin-flip on heavy-tailed reorder distributions (1-2 outlier customers can shift the median by >30%), and the cadence ±½-window at `src/audience_builders.py:550` would then admit/exclude customers based on noise. More importantly: the probe verified Beauty distribution sits below N=10 across all SKU buckets with `MIN_N_REPLENISHMENT_DUE_PER_SKU=10`. Lowering to N=5 is not statistically defensible AND is not empirically guaranteed to clear. The backstop ("what if N=5 still doesn't clear?") has no honest answer — chasing the floor down to the fixture is the floor accusing the floor.

**Option (ii) — Revisit `_beauty_key` regex. REJECT, prior Q4 verdict stands.** The probe did not produce evidence that "different size-token cadences" is empirically wrong — it produced evidence that the synthetic fixture is sparse at SKU-class granularity. Those are different findings. A 50ml-serum reorder cadence really does differ from a 30ml-retinol cadence (90d vs 45d is plausible); collapsing them to "any beauty SKU" would pool genuinely heterogeneous cadences and produce a median that fits no customer well. The downstream ±½-window gate (`src/audience_builders.py:550`) would then admit customers at the wrong reorder moment — which is worse than dormancy because it generates a confidently-wrong send list. The synthetic-fixture sparsity does not change the cadence-heterogeneity prior; it only tells us this specific 1,199-customer fixture under-populates per-bucket. The prior Q4 reasoning ("aggregation level is actually fine") was theoretically correct AND remains the right call under the new empirical data. The right tool for "sparsity at small ICP" is the audience-level floor at `src/audience_builders.py:559-573` deciding the cohort isn't actionable — not a regex that lies about cadence homogeneity.

**Option (iii) — Accept dormancy on Beauty until real beta data; document honestly. ACCEPT.** The empirical finding is unambiguous: at N=10 (already at the defensible floor of "small handful for median stability"), Beauty pinned fixture produces audience_size=0 because the per-SKU repeat-buyer distribution genuinely sits below that floor. The math is correct. Surfacing as `audience_too_small` in Considered is strictly worse merchant UX than dormancy because it presents the synthetic-fixture artifact as a merchant-actionable signal. On the "stop deferring" concern: this is NOT the same as prior Path (c) deferral. Prior deferral was "we haven't done the analysis, kicking it down the road." This is the analysis: floor is correct at N=10, fixture is correct at its observed shape, the conjunction produces zero. That is a finding, not a deferral. The reframe — "documented expected behavior on synthetic fixtures pending real-merchant validation" — is honest because the engine math is honest. The risk that real beta merchants also don't clear is real, but the response there is the same as here: the engine should refuse to surface a play when the per-merchant data doesn't support it. That refusal is the product.

**Option (iv) — N/A.** No further architectural proposal is needed. The three options exhaust the conceptual space (lower floor / coarser bucket / accept reality). Inventing a fourth would violate the no-new-architecture constraint and would not be statistically grounded.

**Meta-question — S7.6 floor adjustments vs architectural honesty.** The engine IS architecturally honest as long as (a) the floor logic is honest, and (b) silent-skip is replaced by an auditable "below-floor" trace. Condition (a) holds: N=10 with a per-stage profile cell is defensible. Condition (b) is the only real gap — the per-SKU skip at `src/audience_builders.py:537-539` is currently silent. Continuing to tune the floor downward to force activation on a synthetic fixture is exactly the wrong optimization; it would convert the engine from "honest math, dormant when data doesn't support" into "tuned-until-it-fires, defensibility lost." The founder's quoted concern — "evaluated honestly for each merchant" — is satisfied by honest dormancy, not by surfacing a noise card. The synthetic-fixture problem is genuinely a synthetic-fixture problem.

---

**Founder should pick option (iii); sprint scope adds 0 code commits + 1 doc commit (KI-NEW-G update at `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md` + a one-line entry in `memory.md` synthetic-fixture philosophy section); T2.5 status becomes RESOLVED-AS-DOCUMENTED-EXPECTED-BEHAVIOR (flag stays OFF on Beauty pinned fixture by design; supplements activation per S7-T2.5 atomic-flip proceeds independently since supplements already surfaces in Considered with `no_measured_signal`, which IS the honest signal-strength path).**

---

**Key file paths referenced:**
- `src/audience_builders.py` (lines 436-451, 537-539, 550, 559-573)
- `config/gate_calibration.yaml` (lines 419-423)
- `scripts/s7_6_t2_5_atomic_flip_probe.py` (verified empirical baseline)
- `agent_outputs/ecommerce-ds-architect-t2_5-floor-scope-card-2026-05-22.md` (prior verdict — Q4 holds)
- `KNOWN_ISSUES.md` (KI-NEW-G target for doc-only update)
