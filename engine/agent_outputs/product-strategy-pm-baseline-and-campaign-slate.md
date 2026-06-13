# Product PM — Baseline Acceptance and Campaign Slate Contract

## Part 1 — Baseline Acceptance

### 1. Synthetic blocker fixes
Accept all 11 fixes as the current product baseline. Per `memory.md` and the per-fix summaries, Fix 1 (cold-start chart None-safety), Fix 2 (targeting-measurement structural invariant on receipts, not just renderer), Fix 3 (ABSTAIN_SOFT => recommendations=[] with `TARGETING_HELD_UNDER_ABSTAIN` routing), Fix 4 (M3 `inventory_blocked` stamping wired through `_PRELIM_REASON_MAP`/`_CONSIDERED_REASON_TEXT`/`_WOULD_FIRE_IF_TEMPLATE`), Fix 5 (materiality footer unconditionally stamped via `_scale_from_aligned`), Fix 6 (`VERTICAL_MODE` propagation), and Fix 7 (DOM-only reporter) all shipped with TDD where required, 687 passed/14 skipped, no goldens re-baselined. Each fix has a clean blast radius (`code-refactor-engineer-synthetic-fix-{1..7}-summary.md`) and respects every Non-Goal in `implementation-manager-synthetic-blocker-fix-plan.md`. Fixture retunes 8–11 are realism-only and pinned by `tests/test_synthetic_fixtures_8_11.py`.

### 2. Beauty Brand V2 utility
The latest healthy_beauty_240d V2 output (`agent_outputs/synthetic_fixes_8_11_samples/healthy_beauty_240d_briefing.html`) is useful enough as the next iteration baseline. It publishes 1 directional `first_to_second_purchase` (audience 5,560 × $59 AOV ≈ $329k addressable order value, suppressed revenue_range, sign-stable across L28/L56/L90), 6 Considered cards with typed reason codes and would_fire_if copy, 1 Watching row, materiality footer rendering, and zero forbidden statistical strings. The phase5_samples copy is structurally similar but the synthetic_fixes_8_11_samples render is canonical post-blocker-pass. Useful, not finished — the page is honest but commercially thin (one card; six "no measured signal" rejections look indistinguishable to a merchant).

### 3. ABSTAIN_SOFT contract
Yes, makes sense as currently shipped. Fix 3's contract — ABSTAIN_SOFT yields zero Recommended cards, head-routed targeting plays land in Considered with `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN`, `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 0` as second-line defense — eliminates the page-contradicts-itself defect on `promo_anomaly_240d` and is mechanically pinned by `tests/test_abstain_soft_no_recommendations.py`. Phase 5.1 merchant-readable callout copy preserved. Targeting plays are not lost; merchant still sees them with explicit "would fire when..." text.

### 4. Remaining non-inventory blockers
None for campaign-slate discussion. The `src/load.py:626` `groupby().apply().reset_index(name=...)` TypeError blocks low-inventory e2e validation of the `inventory_blocked` Considered card (per `code-refactor-engineer-synthetic-fixes-8-11-summary.md`), but the Fix 4 plumbing is structurally correct and unit-tested with synthetic `inventory_metrics`. Other open items (anomaly auto-registration, `empty_bottle` ct/lb parser, `returning_customer_share` as state-statistic-not-effect) are Phase 6, not slate-blocking.

### 5. Product caveats to carry forward
- `first_to_second_purchase` directional fires on three retuned beauty/promo fixtures because they share the same generator family producing strongly positive returning-share trends; do not over-generalize the "engine works on healthy stores" claim from this.
- `returning_customer_share` is a state statistic, not an intervention effect; the suppressed `revenue_range` and "not projected lift" disclaimer are forcing functions and must not be lifted without a calibrated causal prior.
- The Considered list is currently the strongest part of the briefing; six cards collapsing to "no_measured_signal" looks repetitive and undermines the differentiation between play types.
- Inventory loader bug at `src/load.py:626` blocks low-inventory e2e — flagged, not slate-blocking.
- AnomalousWindowCheck not auto-registered in V2; promo_anomaly publishes a directional card rather than ABSTAIN-ing on the spike.

### Verdict
**Accepted with caveats.**

---

## Part 2 — Campaign Slate Contract

### Slate vs single-list
**Yes, evolve to a campaign slate.** Reasoning: the current Beauty Brand V2 page surfaces 1 directional Recommended card and 6 indistinguishable "no measured signal" Considered cards with non-trivial audiences (winback_21_45 = 686, bestseller_amplify = 1,475, discount_hygiene = 2,251, routine_builder = 1,926). A merchant looking at this page sees one play to run and a wall of held cards; the page does not differentiate between "we have measured signal," "we have a sensible targeting list to send to anyway," and "we are watching this for next month." The slate model fixes that without restoring fake stats: it lets directional plays drive Recommended Now while honest targeting plays (winback, discount_hygiene, bestseller_amplify) become Recommended Experiments — explicitly framed as send-and-measure, not as evidence-backed forecasts. This is the structural change that takes the engine from "scientifically honest, operationally thin" to "commercially valuable, scientifically honest." The Phase 5.6 directional pathway, ABSTAIN_SOFT contract, materiality floor, and targeting-measurement invariant all carry forward unchanged.

### Merchant-facing sections
Five sections, in this order on `briefing.html`:
1. **State of Store** (existing)
2. **Recommended Now** — measured/directional only (replaces current Recommended)
3. **Recommended Experiment** — high-quality targeting plays explicitly framed as send-and-measure
4. **Lifecycle Maintenance** — always-on, low-effort plays with clear cadence (winback, replenishment-style)
5. **Watching** (existing, unchanged)
6. **Held / Considered** (existing, unchanged — renamed clearly to disambiguate from Lifecycle)
Plus existing data-quality footer.

### Counts per section
- Recommended Now: **0–2** (cap stays tight; never more than 2 measured/directional)
- Recommended Experiment: **0–3** (hard cap 3)
- Lifecycle Maintenance: **0–2** (cadence-driven; missing if no eligible play)
- Watching: **0–4** (current cap 7 is too generous; reduce to keep page scannable)
- Held / Considered: **3–6** (current 6-cap stays; surfaces what was filtered)

Total visible play cards: 0–7 (vs current 1–9). Reasoning: PM Phase 1 reconciled memory says "0–3 high-value Play Theses." Slate adds two more roles but they each have tight caps and stricter eligibility, so the merchant-facing total stays bounded. ABSTAIN_SOFT collapses Recommended Now AND Recommended Experiment to 0; only Lifecycle and Considered survive, preserving Fix 3.

### Role definitions

**1. Recommended Now**
- Definition: Plays with measured or directional evidence that cleared materiality, cannibalization, and inventory gates this run.
- Merchant promise: "Run this campaign this month; we have signal in your data that supports it."
- Evidence bar: `evidence_class ∈ {measured, directional}`, `consistency_across_windows >= 2`, `p_internal < 0.05` (internal, never rendered), audience cleared materiality, no inventory block.
- Expected count: 0–2. Healthy stores typically 1; abstain stores 0.

**2. Recommended Experiment**
- Definition: Targeting plays with non-trivial audience and clear merchant-readable mechanism, framed as send-and-measure pilots, not as forecasted lift.
- Merchant promise: "Run this as an experiment; we will measure the result and learn whether it works for your store."
- Evidence bar: `evidence_class == targeting`, audience >= materiality threshold for the play type, no inventory block, no cannibalization conflict with Recommended Now, `revenue_range.suppressed = true` always.
- Expected count: 0–3. Always 0 under ABSTAIN_SOFT (Fix 3 contract).
- Forbidden: $ p50 headline, p-value, CI, "expected lift," "measured."

**3. Lifecycle Maintenance**
- Definition: Always-on, cadence-driven plays the merchant should be running continuously regardless of monthly variance — winback, replenishment, lapsed-buyer rescue.
- Merchant promise: "Keep this running every month; this is table stakes for retention, not a monthly experiment."
- Evidence bar: targeting evidence, audience non-trivial, vertical-applicable. No measurement claims.
- Expected count: 0–2. Often 1 (a winback). Missing on cold-start.

**4. Watching**
- Definition: Metrics trending but not yet at threshold to recommend; or load-bearing metrics flat.
- Merchant promise: "Nothing to do; we're watching these and will surface a play if they cross threshold."
- Evidence bar: trending metric with named threshold and named would-fire play.
- Expected count: 0–4 (cap reduced from 7).

**5. Held / Considered**
- Definition: Plays that ran through the candidate pipeline and were rejected with a typed reason code.
- Merchant promise: "Here's what we considered and why we didn't surface it. Each one has a 'would fire if...' so you know what would unlock it."
- Evidence bar: typed `ReasonCode`, populated `reason_text`, populated `would_fire_if`.
- Expected count: 3–6.

### Eligibility by play_type

- **Recommended Now**: `first_to_second_purchase` (Phase 5.6 directional pathway, current canonical entry); future measured/directional plays as they land. NOT: any current targeting-class play.
- **Recommended Experiment**: `discount_hygiene`, `bestseller_amplify`, `winback_21_45` (when aged), `routine_builder`, `subscription_nudge` (when audience clears the floor).
- **Lifecycle Maintenance**: `winback_21_45` (the canonical lifecycle), `empty_bottle` once ct/lb parser ships, `subscription_nudge` for supplement vertical once a stable cohort exists.
- **Watching**: AOV, repeat_rate_within_window, returning_customer_share, net_sales (current observation set), capped at 4 most-load-bearing.
- **Held / Considered**: any play with `inventory_blocked`, `audience_too_small`, `no_measured_signal`, `targeting_held_under_abstain`, `cap_exceeded`, `data_missing`, `vertical_not_applicable`, `cannibalization`, `recently_run_fatigue`, `materiality_floor_failed`, `data_quality_flag`.

A single play CAN be eligible for multiple roles across runs but appears in only one role per run. Priority: Recommended Now > Recommended Experiment > Lifecycle > Considered. Watching is a separate metric track.

### Beauty Brand expected output under new contract

Using `agent_outputs/synthetic_fixes_8_11_samples/healthy_beauty_240d_briefing.html` audiences:
- **Recommended Now (1)**: `first_to_second_purchase` — 5,560 audience, $329k addressable, directional, suppressed revenue. Unchanged from current.
- **Recommended Experiment (3)**: `discount_hygiene` (audience 2,251), `bestseller_amplify` (audience 1,475), `routine_builder` (audience 1,926). All targeting; no $ headline; explicit experiment framing.
- **Lifecycle Maintenance (1)**: `winback_21_45` (audience 686). Currently in Considered as `no_measured_signal`; promote to Lifecycle because winback at 21–45 days lapsed is the canonical always-on play.
- **Watching (1)**: `aov` trend (already there).
- **Held / Considered (2)**: `subscription_nudge` (audience 2 — `audience_too_small` is the real reason, keep), `empty_bottle` (audience 0 — `audience_too_small`, keep). The four plays now in Recommended Experiment / Lifecycle exit Considered.

Total visible plays: 7 (1 + 3 + 1 + 1 + 2). Page becomes scannable, differentiated, and commercially actionable. ABSTAIN_SOFT stores collapse to 0 Recommended Now + 0 Recommended Experiment + ≤1 Lifecycle + Watching + Considered.

### Economic context rules per role

- **Recommended Now**:
  - Allowed: audience size, recent AOV, addressable order value (Phase 5.1 opportunity-context block: "audience × AOV = about $X"), "not projected lift" disclaimer, suppressed `revenue_range`.
  - Forbidden: any p/q/CI, `revenue_range.p50` headline, "expected lift," "forecast," numeric confidence percentage.
- **Recommended Experiment**:
  - Allowed: audience size, recent AOV, addressable order value (same opportunity-context format), explicit "Send to N people; we'll measure the result" framing, `would_be_measured_by` field naming the metric.
  - Forbidden: $ headline, any statistical claim, "evidence," "measured" (these are experiments precisely because they are not yet measured).
- **Lifecycle Maintenance**:
  - Allowed: audience size, cadence ("monthly," "weekly"), prior-run reference if outcome log exists.
  - Forbidden: $ headline, statistical claim, "lift," "uplift."
- **Watching**:
  - Allowed: trend direction, threshold-to-act copy, named would-fire play.
  - Forbidden: dollar context, predictive claim.
- **Held / Considered**:
  - Allowed: typed reason text, would_fire_if, evidence_snapshot (audience + segment definition).
  - Forbidden: dollar context, $ value, statistical claim.

### $500–$1,000/month value argument

A merchant pays this when the engine reliably (a) surfaces 1 high-confidence directional play per month with audience and AOV math the merchant can act on (current Beauty Brand: $329k addressable on first_to_second_purchase = 33–66x ROI even at 1% conversion to a $20 incremental order), (b) gives 2–3 send-and-measure experiments with audience math so the merchant doesn't have to come up with campaign ideas, (c) maintains a winback/lifecycle play continuously without merchant nagging, (d) shows what was filtered and why with would_fire_if so the merchant trusts the engine wasn't lazy. A $500–$1,000/month spend is recovered if the merchant runs 1–2 of these per month and gets +1% retention or +2% AOV. The current single-recommendation-plus-considered structure does not justify $500/month; the slate does because it converts the engine from "one suggestion per month" to "a campaign program."

### Forbidden claims (carry-forward)

- No fake p, q, CI, `confidence_score`, `final_score`, numeric confidence percentages.
- No Aura, Beacon Score.
- No targeting card with non-null Measurement (Fix 2 invariant).
- No targeting card with $ p50 headline or standalone dollar number larger than the range chip (M8 invariant).
- No "calibrated," "uplift," "ATE," "ITT," "treatment effect" anywhere merchant-facing.
- No expected lift / projected lift / forecast / predicted on Recommended Experiment, Lifecycle, or Watching.
- No "measured" claim on a directional card; the current Phase 5.6 forcing function (suppressed revenue_range + addressable-value disclaimer) carries forward verbatim.
- No restoration of `journey_optimization` to V2 path.
- ABSTAIN_SOFT never publishes Recommended Now or Recommended Experiment cards (extends Fix 3 contract from Recommended to all measured/directional/experiment surfaces).
- Lifecycle Maintenance under ABSTAIN_SOFT: PM-decided. Defaulting to suppress (consistency with Fix 3) unless DS argues lifecycle is exempt because it's cadence-driven, not insight-driven.

---

## Open questions for DS Architect

- Is `winback_21_45` defensibly Lifecycle Maintenance (always-on cadence) vs Recommended Experiment (send-and-measure) given current evidence_class is targeting and no causal prior exists?
- Should Lifecycle Maintenance render under ABSTAIN_SOFT, or does Fix 3's "no Recommended under ABSTAIN_SOFT" extend to Lifecycle?
- Watching cap reduction 7 → 4 — does this break any Phase 5.3 "load-bearing flat metrics surface" guarantee?
- Should Recommended Experiment require a `would_be_measured_by` metric name as a contract field on the PlayCard (not just descriptive copy), to keep the engine ML-ready for outcome-log calibration?
- Does `bestseller_amplify` surfacing as Recommended Experiment require a new measurement-design milestone, or is "send-and-measure with audience × AOV" defensible with the current opportunity-context block?
- For Lifecycle Maintenance, should the engine read `recommended_history.json` (Phase 5.9 outcome log) to suppress a lifecycle play if it ran in the prior 14 days, to avoid fatigue?
- Does the current `empty_bottle` ml/oz parser limitation block supplement Lifecycle Maintenance entirely, or can `subscription_nudge` substitute for the supplement vertical until ct/lb parsing lands?
