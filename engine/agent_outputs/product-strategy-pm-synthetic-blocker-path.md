# Product PM Path — Synthetic Phase 5 Blocker Fixes

## Product Verdict

**Phase 5 V2 is not yet founder/manual-test-ready on the synthetic matrix, and the gap is fixable without redesign.** My prior end-to-end review flagged a soft-blocker state on real fixtures (M0–M9) and a hard-blocker state on the synthetic matrix. Nothing in the synthetic Phase 5 review changes the M0–M9 architecture verdict; what it exposes is a small set of *plumbing* defects between layers that already exist (legacy adapter → M5 guardrails → M3 detect → V2 considered → V2 renderer), plus one unresolved product-contract ambiguity that I now decide.

The product is honest by construction. It is not yet legible to a merchant on the matrix because:
- one scenario crashes upstream of V2 entirely (cold_start),
- one scenario silently violates the targeting/measurement invariant on internal receipts (promo_anomaly),
- one scenario surfaces the inverse of its purpose (low_inventory shows nothing inventory-related),
- the page footer regression hides the one piece of self-explaining copy a merchant gets,
- and the merchant-facing contract on ABSTAIN_SOFT + Targeting cards has been silently in two different states between PM intent and code.

I am calling the contract here. The remaining items are scoped to plumbing and copy, not redesign. Phase 5.1 opportunity context is already sufficient for this blocker pass; do not extend it.

## Product Blockers Before Founder Testing

These must ship before a founder is asked to inspect the matrix. Ordered by merchant-trust impact.

1. **Cold-start must produce a renderable briefing, not a Python traceback.** Any thin-history merchant hits the legacy `charts.py:273` crash. Founder testing of a "data scientist replacement" cannot survive a Python traceback as the failure mode for the most common low-data case. Whether the fix is defensive (filter `None` from `recent`/`prior` before `ax.bar`) or architectural (V2 ABSTAIN_HARD upstream of chart rendering) is for DS Architect; product contract requires a polite ABSTAIN_HARD memo on cold_start_45d.

2. **ABSTAIN_SOFT must render zero cards in the Recommended section.** This is the contract decision I am making here (see ABSTAIN_SOFT Product Contract section). promo_anomaly_240d today renders the ABSTAIN_SOFT callout with 2 Targeting cards immediately below it; the page contradicts itself. The implementation constant `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 2` in `src/storytelling_v2.py` must drop to 0, and `decide()` must clear `recommendations[]` when it sets `decision_state == abstain_soft`. The held targeting plays move into Considered.

3. **Inventory state must be visible somewhere on a low-inventory briefing.** The whole point of the low_inventory fixture is for a merchant to read the page and see that a hero SKU is held because of stock. Today the merchant briefing is byte-substitutable with the healthy beauty briefing. The minimum surface is a typed `inventory_blocked` reason on a Considered card for `bestseller_amplify`, with copy along the lines of "Hero SKU at low stock; held until restock." Without this, low_inventory is an actively misleading product surface.

4. **The targeting ⇒ measurement-null invariant must hold on every card the engine emits, not just on the rendered surface.** Saturated `p_internal` (1.6e-72, 0.0) on targeting cards in promo_anomaly receipts is an architectural violation that the renderer hides today but cannot be relied on to hide forever. Merchant trust depends on the invariant being structural, not cosmetic. This is the specific item where I previously deferred to DS Architect; their framing is correct and I am promoting it from "internal concern" to product blocker.

5. **The materiality footer line must render on every V2 briefing.** "We only recommend primary plays that could realistically add at least $X this month for a store your size." is the single piece of self-explaining copy that tells a merchant *why* the page is honest about not having a recommendation. Its absence on all six synthetic briefings (it is present in `agent_outputs/phase5_samples/beauty_brand_v2_briefing.html`) is a regression that turns ABSTAIN_SOFT into "engine is broken" from the merchant's point of view.

## Fixture / Reporter Issues

These do not block a founder from inspecting the engine; they prevent the matrix from validating Phase 5 acceptance. They must be fixed for the matrix to retest correctly, but they are not engine work.

- **`VERTICAL_MODE` not propagated per scenario** — test-harness defect. All six scenarios ran as beauty. Until fixed, the supplement scenario validates nothing about supplement-vertical behavior. This is the *only* item from the blocker list that lives in the harness rather than the engine, but it gates re-running the matrix correctly.
- **Reporter reads internal artifacts (`candidate_debug.json::pilot_actions`/`actions`) instead of `briefing.html`** and labels things "PRIMARY" / "pilot" that the merchant never sees. Five of six scenarios are misrepresented. This is reporter/test-tooling work, not engine work, but it must ship in the same pass because no founder should look at the matrix summary table while it claims the inverse of the merchant-visible state.
- **healthy_beauty_240d L28 returning_customer_share is -1.7%, not the upward signal the YAML claims.** The Phase 5.6 directional gate correctly does not fire; the fixture does not exercise the canonical pathway. Re-tune the generator so the Sep 18 anchor sits on a sign-stable upward L28 delta with consistency across L56/L90.
- **supplement_replenishment_240d has 100% returning customers and 0.8% within-window repeat rate** — internally inconsistent. Cap returning-customer share below 100%, fix the within-window repeat-rate definition, add an explicit loyal-SKU repeater cohort, and add size-token product metadata so `subscription_nudge` and `empty_bottle` actually have audiences.
- **promo_anomaly_240d May spike is outside the L28/L56 lookback from the Sep anchor.** Move the anchor to within ~56 days of the promo or move the spike. The anomaly gate cannot fire on a spike outside its window.
- **low_inventory CSV reads as "228 days stale"** — runner-clock artifact. Align the runner clock to the anchor date.
- **Synthetic generator is outcome-driven (YAML targets) rather than process-driven** — this is the structural reason three of six fixtures do not test what their YAML claims. Acknowledge as a Phase 6 generator-design item; do not block the blocker pass on it.

## Deferrable Issues

Defer everything below to Phase 6. None of these are needed to declare Phase 5 founder-testable.

- **Reason-code taxonomy expansion** beyond what the blocker pass needs (`vertical_not_applicable`, broader differentiation across the Considered list). The minimum the blocker pass adds is `inventory_blocked` rendered as a typed reason; the rest waits.
- **Per-card per-scenario Considered differentiation copy.** The structural improvement is real; the content shallowness is acceptable for founder testing.
- **Watching-section never-empty contract** for healthy stores when load-bearing metrics are present. The empty-state on small_store/promo_anomaly reads as broken, but it is not a trust violation, it is a polish gap.
- **Below-scale memo** for sub-floor stores like small_store_240d ($13k/month). The engine correctly abstains; the page does not say "your store is below recommendation scale today." Address in Phase 6.
- **`returning_customer_share` replacement as the supporting metric for `first_to_second_purchase`.** DS Architect flagged this as a measurement-design defect. Real concern; Phase 6 work; not part of unblocking founder testing.
- **Tiny-base ratio antipattern in state-of-store** (`repeat_rate 0.8% → +154.7% MoM`). Add a base-size guard in Phase 6.
- **Materiality floor not stamped on `engine_run.json::Scale.materiality_floor`.** Receipts-completeness defect; not merchant-visible.
- **State-of-store fact-count determinism** (3–5 facts across scenarios). Polish.
- **Watching-section copy rewording** ("Threshold to act: +/- 5% to fire an AOV play"). Engineering-flavored; M10 cosmetic.
- **Supplement-vertical directional pathway**, replenishment-cycle play, supplement causal prior. Phase 6 dependency.
- **Adding any new evidence tier or causal prior.** Hard out for this pass.

## ABSTAIN_SOFT Product Contract

Decision, binding for the blocker-fix pass:

**ABSTAIN_SOFT renders zero cards in the Recommended section. Held plays — including targeting plays surviving M5 guardrails — render in Considered, not Recommended.**

Rationale:
- The merchant must never read a page with a "No primary play this month" callout and a non-empty Recommended section directly underneath. That contradicts itself in a way no callout copy can patch.
- The PM contract from M0–M9 (`memory.md` Phase 1 Decision Core: "ABSTAIN_SOFT → standard layout + 'no measured' callout, 0–2 targeting cards (suppressed/labeled), no $ headlines") was originally permissive of up to 2 targeting cards. The synthetic matrix shows that this permissiveness produces a self-contradicting page. I am tightening the contract to zero. This supersedes the prior 0–2 phrasing for the blocker-fix pass forward.
- The implementation constants `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 2` (`src/storytelling_v2.py`) and the `decide.py` logic that allows up to 2 targeting cards under ABSTAIN_SOFT must both move to 0. The held targeting plays do not disappear; they appear in Considered with the appropriate reason code (`targeting_non_causal_prior` or equivalent).
- This change preserves the existing PUBLISH-with-targeting-cards behavior. Targeting cards still render in Recommended *when* `decision_state == publish`. They never render in Recommended when `decision_state == abstain_soft`.
- The ABSTAIN_SOFT callout copy itself is unchanged from Phase 5.1 (merchant-readable, gate-keyed). Only the cards-in-Recommended count drops.

This is the single product-contract decision in the blocker pass. Everything else is plumbing.

## Scenario-Level Expected Merchant Experience

This is the acceptance matrix the implementation-manager and DS Architect should treat as the minimum founder-test bar. Each row is what the merchant must see on `briefing.html` after the blocker fixes ship.

**1. healthy_beauty_240d**
- Decision state: `publish` *if* the fixture is re-tuned to produce upward L28 returning_customer_share at the Sep 18 anchor with sign-stable consistency. Otherwise `abstain_soft` is acceptable but the briefing must be a useful ABSTAIN_SOFT, not a near-empty one.
- Recommended: 1 directional `first_to_second_purchase` card with audience size, observed metric line, opportunity context block (audience × AOV = "about $X.Xk addressable order value"), no dollar headline, no p/q/CI strings. Or 0 cards if the re-tuned fixture still does not produce the signal.
- Considered: 6 cards, each with a typed reason code. Reason codes should not all collapse to `no_measured_signal`; if they do, the considered list is honest but shallow (acceptable for founder test, not for production).
- Watching: at least 1 row.
- Materiality footer line present.
- No forbidden stats strings.

**2. healthy_beauty_low_inventory_240d**
- Decision state: `abstain_soft` (or `publish` if any non-blocked candidate clears the directional gate).
- Recommended: 0 cards.
- Considered: 6 cards. **`bestseller_amplify` must carry `reason_code = inventory_blocked` with copy explicitly referencing low stock on the hero SKU.** This is the load-bearing scenario test. If the merchant cannot see the inventory state on this page, the engine has failed its claim of operational awareness.
- Watching: same as healthy_beauty.
- Materiality footer line present.

**3. supplement_replenishment_240d**
- Decision state: `abstain_soft` is acceptable for the blocker pass. Supplement-vertical directional pathway is Phase 6 work.
- Recommended: 0 cards. The reporter previously falsely claimed "1 PRIMARY journey_optimization"; the merchant view is and should remain 0.
- Considered: 6 cards. Audience sizes must be non-degenerate once the fixture is re-tuned (loyal-SKU repeater cohort + size-token metadata). If `subscription_nudge` audience is still 12 because the fixture cannot model it, that is a fixture deferral, not an engine deferral.
- Watching: 1+ rows.
- Engine must run with `VERTICAL_MODE=supplements`. Today it runs as beauty. The blocker fix here is in the test harness, not in the engine: confirm `briefing_meta.vertical = supplements` in `engine_run.json`.
- Materiality footer line present.
- The merchant should not be misled into thinking supplement vertical has rich V2 support — but neither should the page actively misrender as a beauty store.

**4. small_store_240d**
- Decision state: `abstain_soft`. Correct epistemic outcome for a $13k/month store.
- Recommended: 0 cards.
- Considered: 6 cards. Acceptable if reason codes collapse to `audience_too_small` / `no_measured_signal`. A `materiality_floor_failed` reason code surfaced on at least one card would be better, but is Phase 6.
- Watching: empty is acceptable here for the blocker pass; "Watching never empty" is a deferred Phase 6 polish item.
- Materiality footer line present and unambiguous: the merchant of a $13k/month store reading "We only recommend primary plays that could realistically add at least $5k this month..." should walk away understanding why no plays are surfaced.
- No "below-scale memo" required for the blocker pass.

**5. cold_start_45d**
- Decision state: `abstain_hard` with `data_quality_flag = INSUFFICIENT_HISTORY` (or equivalent). Not a crash.
- briefing.html exists, renders, and contains the data-quality memo layout: explanation that 90+ days of history are needed, no fabricated recommendations, no chart errors.
- Recommended: 0 cards (forced empty by ABSTAIN_HARD).
- Considered: 0 cards (forced empty by ABSTAIN_HARD).
- Watching: 0 rows acceptable.
- The merchant uploads 45 days and gets a polite memo, not a Python traceback. This is the single scenario that is most non-negotiable.

**6. promo_anomaly_240d**
- Decision state: `abstain_soft` is the current reality given the fixture (spike outside L56). After the fixture is re-anchored, `abstain_hard` with an anomaly DQ flag is the correct outcome. For the blocker pass, either is acceptable as long as the contract holds.
- Recommended: 0 cards. **This is the hard blocker fix.** Today the page renders the ABSTAIN_SOFT callout with 2 Targeting cards; after the fix, the callout stands alone and the targeting plays appear in Considered.
- Considered: 6 cards including the formerly-Recommended targeting plays (winback_21_45, bestseller_amplify) with reason codes indicating they were held because of the abstain state.
- Watching: empty is acceptable (Phase 6 polish).
- Materiality footer line present.
- Internal `p_internal` saturation (1.6e-72, 0.0) on targeting cards must not exist in `receipts/engine_run.json` regardless of whether it is rendered. The targeting ⇒ measurement-null invariant must hold structurally.

## Minimum Founder-Test Standard

A founder can be invited to inspect the matrix when **all** of the following hold:

1. Every scenario produces a renderable `briefing.html` with no exceptions, including cold_start_45d.
2. cold_start_45d renders ABSTAIN_HARD with a data-quality memo, not a crash and not a near-empty page.
3. No `briefing.html` shows ABSTAIN_SOFT callout AND a non-empty Recommended section. Zero exceptions across the matrix.
4. healthy_beauty_low_inventory_240d surfaces an inventory-related reason on at least one Considered card, with copy a merchant can parse.
5. The materiality footer line ("We only recommend primary plays that could realistically add at least $X...") renders on every non-ABSTAIN_HARD briefing.
6. All six scenarios run with their declared `VERTICAL_MODE` (visible in `engine_run.json::briefing_meta::vertical`).
7. No `briefing.html` contains forbidden statistical strings (`p =`, `q =`, `CI`, `confidence_score`, `final_score`, `Aura`, `Beacon Score`, numeric confidence percentage).
8. No `engine_run.json::recommendations[]` carries `evidence_class = targeting` AND a non-null `measurement` object. Invariant must hold structurally on receipts, not just on the rendered surface.
9. The matrix-runner reporter accurately describes what `briefing.html` shows (Recommended/Considered/Watching counts), not what `candidate_debug.json` shows.

Today's pass count from the synthetic e2e review: 1 of 9. The blocker pass closes 8 of 9; item 4 depends partly on the low_inventory fixture being re-runnable, which depends on the runner-clock artifact also being fixed.

## In-Scope For Blocker-Fix Plan

Implementation-manager treats these as the work envelope. Each is bounded.

**Engine / V2 plumbing (small surface):**
- Cold-start: defensive fix to `charts.py:273-274` filtering `None` from `recent`/`prior` before `ax.bar`. Or the architectural reorder (V2 ABSTAIN_HARD upstream of chart rendering). DS Architect picks; the cheaper fix is acceptable.
- ABSTAIN_SOFT contract enforcement: drop `MAX_ABSTAIN_SOFT_TARGETING_CARDS` from 2 to 0 in `src/storytelling_v2.py`; clear `recommendations[]` in `decide.py` when `decision_state == abstain_soft`; route the formerly-rendered targeting plays into Considered with an appropriate reason code.
- Targeting ⇒ measurement-null invariant hardening: ensure that any path producing an `evidence_class = targeting` PlayCard cannot also carry a populated `Measurement`. Either reclassify before measurement is built or null measurement after reclassification. DS Architect's call on which.
- Inventory M5 → V2 considered wiring: surface `inventory_blocked` as a typed reason code on the `bestseller_amplify` Considered card on the low-inventory fixture. DS Architect's preferred path is `preliminary_rejection_reason="inventory_blocked"` in M3 `detect_candidates`. Also confirm `bestseller_amplify` is produced as a base candidate at all on the low-inventory fixture.
- Materiality footer line restoration on V2 briefings (regression vs. `agent_outputs/phase5_samples/beauty_brand_v2_briefing.html`).

**Test harness (small surface):**
- Per-scenario `VERTICAL_MODE` propagation in the matrix runner.
- Reporter rewrite to read `briefing.html` (DOM/bs4 parse) and count rendered cards. Treat as test-tooling, not engine work.

**Fixture re-tuning (matrix-validity):**
- healthy_beauty_240d L28 returning_customer_share sign at the anchor.
- supplement_replenishment_240d returning-share cap, repeat-rate definition, loyal-SKU cohort, size-token metadata.
- promo_anomaly_240d anchor or spike placement.
- low_inventory CSV runner-clock artifact.

## Out-Of-Scope For Blocker-Fix Plan

Implementation-manager rejects any task in this list as out-of-scope for the blocker pass.

- Any change to evidence classes, evidence taxonomy, or recommendation tiers. The three classes (measured/directional/targeting) and three buckets (Strong/Emerging/Targeting) stay as-is.
- Any change to materiality floors. Stays at the M5 contract values.
- Any V2 default flip. Stays behind flags.
- Any M10 cleanup. Including legacy emitter deletion, journey_optimization removal from legacy, deprecation of any legacy code path.
- Any reopening of M0–M9 decisions or the Phase 5 / Phase 5.1 work.
- Any addition of a causal prior. The Phase 5.6 directional pathway stays at `revenue_range.suppressed = true`.
- Any opportunity-context extension. Phase 5.1 already added the addressable-value block on suppressed-revenue cards. It is sufficient as-is. Do not extend it to targeting cards (M8 invariant) and do not extend it to the Considered cards (calibration-data risk; both PM and DS in the synthetic review explicitly deferred this).
- Restoration of any forbidden artifact: fake p-values, fake CIs, `confidence_score`, `final_score`, legacy dollar projections on targeting cards, Aura, Beacon Score.
- Reason-code taxonomy expansion beyond what the inventory blocker requires (no new `vertical_not_applicable`, no `materiality_floor_failed` rendering, no broader Considered differentiation in this pass).
- Watching-section never-empty contract, below-scale memo, state-of-store fact-count determinism, Watching copy rewording. All Phase 6.
- Replacement of `returning_customer_share` as the supporting metric. Phase 6.
- Supplement-vertical directional pathway, supplement causal prior, replenishment-cycle play. Phase 6.
- Tiny-base ratio guard in state-of-store. Phase 6.
- Materiality floor stamping on `engine_run.json::Scale.materiality_floor`. Phase 6 receipts-completeness work.
- Generator process-driven redesign. Phase 6 generator overhaul.
- Lifecycle memory, recommendation carryover semantics across runs, fatigue logic. Out by hard constraint.

## Notes For DS Architect

You read this file next. Three things to land before implementation-manager scopes the plan.

1. **Pick the targeting ⇒ measurement-null enforcement strategy.** Two options on the table from the e2e review: (a) post-hoc clear measurement to `None` after evidence reclassification, with an assertion; (b) reclassify before measurement is built (architectural reorder). The synthetic review recommended (a) as cheaper and sufficient. Confirm or override. Whichever you pick, please pin it with a test that constructs an EngineRun with `evidence_class = targeting` AND non-null `Measurement` and asserts the engine raises or coerces — the synthetic review explicitly called this out as a structural defect that the renderer hides today, and I am treating that hiding as a future-regression risk, not as protection.

2. **Pick the inventory M5 → V2 considered wiring path.** Synthetic review recommended `preliminary_rejection_reason="inventory_blocked"` in M3 `detect_candidates` as the cleaner path because it keeps M3 as the canonical V2 source of truth. Confirm or override. Also confirm whether `bestseller_amplify` is currently produced as a base candidate on the low-inventory fixture; if not, that is a separate fix (audience builder) that needs to land in the same pass.

3. **Pick the cold-start fix path.** Defensive one-liner in `charts.py:273-274` vs. architectural reorder (V2 ABSTAIN_HARD upstream of chart rendering). Synthetic review recommended the defensive one-liner now and the architectural reorder as Phase 6. The architectural reorder is the right long-term fix; the defensive one-liner is acceptable for the blocker pass if you confirm it doesn't mask other latent issues with `None` in chart inputs.

Two things I am specifically *not* asking you to revisit:

- The ABSTAIN_SOFT + Targeting cards contract. I have decided: zero cards in Recommended under ABSTAIN_SOFT. The PM contract (`memory.md`) phrasing of "0–2 targeting cards" is hereby tightened to 0 for the blocker-fix pass forward. This is a product call. Code follows.
- Whether the matrix is the right place to validate Phase 5. It is. Re-run after the blockers ship and the fixtures are re-tuned. If the re-run still produces near-uniform ABSTAIN_SOFT pages on healthy fixtures, that is a separate conversation (Phase 6 measurement-design work on `returning_customer_share`), not a blocker-pass conversation.

One thing I want you to be willing to push back on:

- If `inventory_blocked` as a typed reason code on the considered list opens a measurement-design rathole (e.g., "what counts as low stock," vertical-specific thresholds, multi-SKU aggregation), say so. I would rather ship a less-polished `inventory_blocked` reason in this pass than ship a measurement-design redesign as part of a blocker pass. The minimum acceptable surface is "this play is held because of inventory state on the hero SKU," text the merchant can parse. Sophistication waits.
