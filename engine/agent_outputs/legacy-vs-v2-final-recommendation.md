# Legacy vs V2 Final Recommendation

## Executive Verdict

**Both reviews independently converged on: ship neither artifact as-is, but the fix is upstream of the renderer.** The legacy briefing is scientifically indefensible (template-fabricated CIs surfaced as measured signals). The V2 briefing is scientifically honest but operationally inert — and it is empty for an architectural reason, not because the data is silent. The Beauty Brand dataset has real, defensible signal (`returning_customer_share` L28 `p=9.5e-05` with +6.6% delta, persistent and growing across L56/L90), and the V2 spine is structurally unable to surface it because the M3 detect path does not feed `decide()` and the legacy adapter coerces every unmapped play to `targeting`.

The recommendation is a small, scoped set of changes that combine V2's epistemic posture with a populated rejection list, an extended Watching schema, and a single causal-priored measured pathway — *not* a port of legacy's execution-plan chrome and *not* a reopening of the architecture loop.

**Final go/no-go:** GO on a tightly-scoped Phase 5 (4 small changes, no architecture redesign). NO-GO on shipping either current artifact as the merchant default until at least the rejection-list-always change and the abstain-soft copy rewrite ship.

## What The Outputs Show

**Legacy `out/legacy_beauty_brand/`** — 1707-line themed briefing rendering an "Aura Score 77 / Healthy" header, $14,463 monthly opportunity hero, and three play cards (`journey_optimization` PRIMARY, `frequency_accelerator` and `retention_mastery` QUICK_WINS) each with audience CSV, channel/sequence/offer/holdout, success metric, and 7-step execution list. The merchant can publish from this page. The trust problem is the receipts: `journey_optimization` carries `effect_abs=0.9165, ci=[0.894, 0.939], p=1e-10, confidence_score=1.0` — these are template-fabricated stats, not measured uplift. `frequency_accelerator` shows L28/L56/L90 effects of +0.011/-0.071/-0.194 (sign-flipping across windows) but is presented as a single saturated `p=1e-10` measured signal. `retention_mastery`'s CI literally crosses zero (`[-0.030, +0.049]`) but renders with a "Strong signal" badge.

**V2 `out/manual_test_beauty_brand/`** — 50-line briefing: subtitle, one state-of-store paragraph (3 typed Observations with deltas), an ABSTAIN_SOFT callout reading "no measured or directional recommendation cleared materiality + cannibalization gating," three empty-state placeholders ("No targeting plays met audience-floor and overlap rules this run.", "No plays were considered and held this run.", "No deterministic signals to watch this run."), and a 4-row data-quality footer including `materiality_floor: $10,000`. Receipts are empty and internally consistent: `recommendations=[]`, `actions_log=[]`, `v2_sizing_shadow.records=[]`, `considered=[]`, `watching=[]`. The forbidden-string contract holds (no `p`, `q`, `CI`, `confidence_score`, `final_score` in the merchant view).

The same dataset (9,620 orders, A-grade data quality, $1.13M ARR, healthy on all KPIs) produces a glossy 3-play sprint plan in legacy and a near-empty memo in V2.

## Product Findings

PM verdict (file: `agent_outputs/product-strategy-pm-legacy-vs-v2-review.md`):

- **Legacy: 9/10 actionable, 3/10 trustworthy.** Publish-ready form, but the trust collapse is binary on inspection — any merchant who clicks through to `candidate_debug.json` finds the saturated CIs and disbelieves the entire page.
- **V2: 0/10 actionable, 7/10 trustworthy.** Honest by construction, but a healthy $1.1M-ARR brand with A-grade data getting a 50-line page with three empty placeholders reads as broken to a non-technical operator.
- **The product question is not "which is right" but "which is closer to the eventual merchant experience."** Legacy is closer to the *form*; V2 is closer to the *epistemic posture*. The product is the merge.
- **Smallest-change list (PM, priority order):** rewrite the abstain-soft callout text; surface the considered list always; flip default renderer to V2 only after #1–2; author a beauty causal prior; port legacy's execution-plan structure into V2 cards; extend the Watching schema; kill the Aura Score in V2; explain or hide the `materiality_floor` footer.
- **Eight specific questions deferred to DS Architect** — including why `returning_customer_share` (real, p=1e-4) doesn't surface, why `frequency_accelerator` (not in TARGETING_RECLASSIFY_PLAYS) doesn't surface under V2, why repeat_rate differs between legacy (0.3229) and V2 (0.3399), and whether the suppressed legacy candidates should appear in `v2_sizing_shadow.json` for diagnostic value.

## DS / Scientific Findings

DS Architect verdict (file: `agent_outputs/ecommerce-ds-architect-legacy-vs-v2-response.md`):

- **Legacy is scientifically indefensible.** Two of three PRIMARY/QUICK_WINS plays carry template-fabricated stats: `journey_optimization` (Wald CI on a proportion presented as a measured-uplift CI) and `frequency_accelerator` (min-p cherry-pick across sign-flipping windows). The third (`retention_mastery`) has a real p but its CI crosses zero and the engine itself fails it on `effect_floor` — yet the renderer surfaces it with "Strong signal" anyway.
- **V2 is scientifically defensible but operationally inert because of a wiring defect, not because of conservative gates.** The data has real signal; the V2 spine doesn't carry it. M3 detect path exists but doesn't feed `decide()`. The legacy adapter's `_coerce_evidence` defaults all unmapped plays to TARGETING. M5/M6/M7 then *correctly* suppress targeting plays without causal priors. The empty page is a structural artifact, not an evidence verdict.
- **The PM's "port legacy's execution plan into V2" prescription is risky** because most of legacy's execution plan content is also template-generated. The minimal correct change is narrower.
- **Materiality at $10k is correctly the binding floor** for a $1.13M-ARR brand under the contract's `max($10k, 3%)` rule for the $1–5M tier. Lowering it pre-empirically is itself a fabrication; the calibration stub (M9 `materiality_overrides`) is the place where a beauty-specific floor would eventually live, but only after realization data exists.
- **Three scientifically valid recommendation types** can exist without measured-lift claims: measured (with observed effect), directional (sign-stable across windows but below effect_floor), targeting (audience-only with mandatory disclaimer) — plus a fourth structural "do-nothing" type for genuinely thin evidence.
- **Forbidden** in any V2 surface: heuristic-as-measured plays, benchmark-derived dollar projections on targeting cards, "Strong signal" badges without calibrated probability, sum-of-impact heroes uncorrected for audience overlap, saturated `confidence_score: 1.0` displayed as confidence, composite "health scores" (Aura/Beacon) as a product claim.
- **DS practical priority:** (1) surface rejection list always with deterministic reason codes; (2) add `returning_customer_share` to the Watching threshold table; (3) rewrite the abstain-soft text; (4) author one causal prior for one beauty play; (5) wire one M3 audience builder through to a measured PlayCard.

## Points Of Agreement

1. **Neither output is shippable as the merchant artifact.** Legacy is unrecoverable on inspection; V2 is unusable on first read.
2. **The smallest correct change is narrow, not a redesign.** Both reviews explicitly reject "restart the architecture loop."
3. **The abstain-soft callout text is the most jargon-leaky string in the merchant view** and must be rewritten as the first PR.
4. **The considered/rejection list must be populated even when the decision state is abstain.** This is the contract's wow surface and it's empty on a brand where the engine objectively *did* consider plays.
5. **The M7 Watching builder is too strict for this dataset.** A flat `Orders` HELD observation produces no watching entry; the `returning_customer_share` signal (the most informative metric on this brand) has no slot in the watching schema.
6. **A causal prior for at least one beauty play is required** before V2 can produce a non-empty Recommended section on this dataset. Without it, the engine is structurally locked into ABSTAIN_SOFT for beauty merchants.
7. **The Aura/Beacon composite score does not belong in V2.** PM agrees ("Hide the legacy Beacon Score from V2"); DS agrees ("This should not survive into V2 in any form").
8. **The legacy `journey_optimization`, `frequency_accelerator`, and the badging on `retention_mastery` are not defensible.** Both reviews independently identify these as the three highest-trust-cost defects.
9. **The fundamental fix is upstream of the renderer.** PM frames it as "wire the Klaviyo-publishing form to honest evidence"; DS frames it as "wire M3 detect into `decide()` for one measured pathway." Same change, different vocabulary.

## Points Of Disagreement

1. **Scope of "porting legacy's execution plan into V2."**
   - PM #5: "Port legacy's execution plan into V2 measured/directional cards. When V2 *does* produce a recommendation, the card today shows audience size + AOV + a 1-line disclaimer. That is not enough to publish from. Bring across legacy's channel/sequence/offer/holdout/success-metric structure."
   - DS pushback: "Most of legacy's 'execution plan' content is *also* template-generated text not tied to any measured signal at this store. Bringing the form across without bringing the priors and the detection wiring along would just relocate the trust collapse from 'fabricated CI on a card' to 'fabricated execution plan on a card.'"
   - **Tension:** the PM treats execution-plan content as merchant-value-add; the DS treats it as a fabrication risk if it's not bound to evidence.

2. **Whether to flip default renderer to V2.**
   - PM #3: "Flip the renderer default to V2 and accept the empty pages as the conservative outcome — *but only after fix #1 and #2 above*."
   - DS: "Do not flip `ENGINE_V2_OUTPUT=true` as the default until the considered-list-always change ships and the abstain-soft text is rewritten. Today's V2 page is too austere to be the merchant-facing default."
   - **Tension:** PM allows the flip after two specific fixes; DS allows it after the same fixes, but emphasizes that the V2 page must produce real content (populated considered list, populated watching) before it can be the default.

3. **Whether to lower the materiality floor.**
   - PM Q5 (open question): "If the floor were $5K (5%), would `discount_hygiene` (which has measured effect at L56 and L90 with `p ≈ 0.002`) clear it?"
   - DS answer: "Lowering the floor without empirical realization data is itself a fabrication. The calibration stub is the place where we'll know once we have realization data."
   - **Resolution:** DS is correct. The floor stays.

4. **Whether to remove `journey_optimization` from the legacy emitter or just reclassify it.**
   - PM Q3: "Should we remove the candidate from the legacy emitter outright rather than carrying it through M4b reclassification?"
   - DS answer: "The cleaner fix is to *remove the candidate entirely* from the legacy emitter — it is a template that has no measurement design at this store and no causal prior anywhere."
   - **Resolution:** Both agree on deletion as the cleaner fix; the question is whether to do it now or after the measured pathway exists.

5. **`frequency_accelerator` reclassification.**
   - PM Q7 (open question): "Under V2 reclassification, is `frequency_accelerator` measured/directional or targeting? It is not in the TARGETING_RECLASSIFY_PLAYS list."
   - DS answer: "Let the consistency check do its job rather than hardcoding the reclassification — sign-flipping windows give consistency=0 which would correctly prevent it from reaching PUBLISH."
   - **Resolution:** DS is correct. No reclassification needed; the existing M4b `consistency_across_windows` mechanism is the right gate. But this depends on M3 detect → decide wiring (#5 below) actually running, which is *not* yet shipped.

## Resolution

The reconciled position is the **DS Architect's narrower scope** with two PM-derived additions:

1. **Adopt DS's five-step priority list.** It is the smallest set of changes that produces a credible product surface on this dataset: rejection list always, Watching schema extension, abstain-soft copy, one causal beauty prior, one M3 measured pathway. Each is small. None reopens the architecture loop.

2. **Add the PM's "merchant-readable materiality footer" change.** The current "Materiality floor: $10,000" string in the V2 footer is jargon to a non-technical operator. Either explain it ("We only recommend plays that could realistically add at least $10K this month for a store your size") or hide it. This is a one-string change.

3. **Defer the PM's "port legacy's execution plan" prescription.** The DS pushback is correct: the form is template-generated, not evidence-bound. Once the M3 measured pathway is wired (DS step 5), the *one* play that goes through it can carry a real channel/sequence/offer/holdout/success-metric block — but that block must be bound to the play's audience and the play's measurement, not generated from a template. Build this for one play first, prove it doesn't fabricate, then generalize. This is *not* in the Phase 5 minimum scope.

4. **Materiality floor stays at $10k.** No empirical reason to lower it; the calibration stub is the right home for vertical-specific overrides once realization data exists.

5. **`journey_optimization` candidate gets deleted from the legacy emitter, not just reclassified.** This is a defensive cleanup that prevents a future regression where the M4b reclassification is bypassed and the saturated stats leak through. Both reviews agree on the cleaner fix; do it as part of Phase 5.

6. **Aura/Beacon Score gets killed in V2-default mode** (or gated behind an explicit `legacy_compat` flag). Both reviews agree.

## Recommended Path

**Phase 5 (next milestone after M9): "Honest Considered List + One Measured Pathway."**

Six small, scoped changes. Each is independently shippable. No code architecture redesign. The engine remains runnable after every change.

The order is deliberate: copy + rejection list ship *first* so V2 stops looking broken on healthy brands; the measured pathway ships *last* because it is the largest change and benefits from the others landing first.

## Proposed Decision Contract, If Any

The existing decision contract from the M0–M9 plan (PM contract + 12 must-haves + 6 required QA changes per memory.md) is **not modified**. The Phase 5 work operates *within* that contract.

The one contract clarification is on **what populates the considered list**:

- A play appears in `considered[]` if it was either (a) emitted by the legacy adapter, (b) detected by M3 `detect_candidates()`, or (c) explicitly registered as a vertical-applicable play for this brand's vertical.
- Each entry has a `reason_code` from a fixed enum (`measurement_design_missing`, `targeting_non_causal_prior`, `effect_floor_failed`, `cannibalization_overlap`, `materiality_floor_failed`, `audience_floor_failed`, `vertical_not_applicable`, `evidence_class_targeting_no_render_path`, etc.).
- Each entry carries a merchant-readable `held_because` string generated *from* the reason code, not free-form authored.
- The considered list is populated even when `decision_state == abstain_soft` — that is the wow surface and it must be present.

## Minimum Next Implementation Scope

Six items, sized for a single phase. Each shippable independently.

**5.1 — Rewrite the abstain-soft callout text.** (Smallest. Two strings.)
- Replace `engine_run.json::abstain.reason` and the briefing.html callout from "no measured or directional recommendation cleared materiality + cannibalization gating" to a deterministic merchant-readable string parameterized by the actual gate that fired. Default: "Your store is healthy this month. We didn't find a play with strong enough evidence to recommend. Here's what we're watching."
- Files: `src/decide.py` (abstain reason builder), `src/render_v2.py` (callout copy).
- Test: snapshot test on the briefing.html for ABSTAIN_SOFT scenarios.

**5.2 — Surface the rejection list always.**
- `decide()` must populate `considered[]` whenever any candidate was detected, considered, or registered for the brand's vertical, even on abstain_soft.
- Define the reason-code enum (above) and the `held_because` template per code.
- Files: `src/decide.py`, `src/contracts.py` (extend `ConsideredItem`), `src/render_v2.py` (render considered always).
- Test: a fixture where ABSTAIN_SOFT fires and `considered[]` has ≥3 entries with distinct reason codes.

**5.3 — Extend the Watching schema.**
- Add `returning_customer_share` to the M7 watching threshold table.
- Soften the M7 builder: HELD observations with `change_magnitude == 0` on a *load-bearing* metric (orders, net_sales) should produce a "stable but watching" entry, not be filtered out.
- Files: `src/decide.py::build_watching` (threshold table; HELD logic).
- Test: a fixture where `returning_customer_share` produces a Watching entry; a fixture where flat orders produce a "stable" Watching entry.

**5.4 — Make the materiality footer merchant-readable.**
- Replace "Materiality floor: $10,000" with "We only recommend plays that could realistically add at least $10,000 this month for a store your size."
- Or hide it from the merchant view and keep it in `debug.html`.
- Files: `src/render_v2.py` (footer renderer).
- Test: snapshot test on briefing.html footer.

**5.5 — Kill the Aura/Beacon score in V2-default rendering.**
- Computation can stay in `run_summary.json` for legacy-compat consumers, but the V2 spine must not read it and the V2 renderer must not render it.
- Files: `src/render_v2.py`, `src/decide.py` (no read path).
- Test: assert no occurrence of "Aura", "Beacon", "tier", "health_score" in the V2 briefing.html.

**5.6 — Author one causal prior + wire one M3 measured pathway.**
- Author `priors.yaml` entry for `first_to_second_purchase` (or `at_risk_repeat_buyer_rescue`) with `source_class: causal`, `applies_to: {vertical: beauty}`, `source` field naming the evidence (initial value: "expert prior pending realization data; will be re-calibrated after N≥10 published runs").
- Wire M3 `detect_candidates()` to produce a Candidate for that play with the `returning_customer_share` Measurement attached, and have `decide()` consume that Candidate as `evidence_class=measured` (or `directional`, depending on what the L28 sign-stability check yields).
- Have the M6 sizer produce a non-suppressed range using the causal prior.
- Result: this dataset should produce **one PUBLISH or one DIRECTIONAL** card, not abstain_soft.
- Files: `config/priors.yaml`, `src/detect.py`, `src/decide.py`, `src/sizing.py`.
- Test: a beauty-vertical fixture where the first-to-second / at-risk play surfaces with `evidence_class != "targeting"`, a non-null `Measurement`, and a non-null sized range.

**5.7 (optional, defensive) — Delete `journey_optimization` from the legacy emitter.**
- Remove the candidate-builder for `journey_optimization` from the legacy code path. Replace with `first_to_second_purchase` keyed off `returning_customer_share`.
- Files: legacy emitter (need to grep `src/action_engine.py` or similar).
- Test: a fixture where the legacy emitter does *not* emit a `journey_optimization` candidate; the new play emits one.

**Out of scope for Phase 5 (explicit deferrals):**
- Porting the full execution-plan structure (channel/sequence/offer/holdout/success-metric) into V2 cards beyond the one play used in 5.6.
- Lowering the materiality floor.
- Cosmetic theming of the V2 briefing (M10 work).
- Reclassifying `frequency_accelerator` (let the consistency check do its job once 5.6 ships).
- The `repeat_rate_within_window` legacy/V2 drift (0.3229 vs 0.3399). Document as a known methodology change in the briefing footer; don't relitigate the bias-correction default.

## What To Test After The Change

After Phase 5 lands, re-run the engine on `data/beauty_brand_orders.csv` and confirm:

1. **Briefing.html length is no longer 50 lines.** It should have at least one populated section between `state-of-store` and the data-quality footer.
2. **Considered list has ≥3 entries with distinct reason codes.** At minimum: one entry for `journey_optimization` (or its successor) with a "measurement design missing" reason code; one for `bestseller_amplify` with "targeting non-causal prior"; one for `subscription_nudge` with "targeting non-causal prior."
3. **Watching list has ≥1 entry.** `returning_customer_share` should appear with a "stable / increasing" framing and an "act if drops below X%" template.
4. **Recommended section has 1 entry** (the M3-wired measured/directional play). Card carries: audience size, evidence class chip ("Measured" or "Directional"), no `p`/`q`/`CI`, no saturated confidence score. Sized using the causal prior.
5. **Abstain-soft does not fire** on this dataset — but if it did fire on a thinner dataset, the callout reads as merchant English not as engineering jargon.
6. **`v2_sizing_shadow.records`** has at least one entry (the new play's sized range), suppressed or not.
7. **Forbidden-string contract holds:** no `p =`, `q =`, `CI`, `confidence_score`, `final_score`, `Aura`, `Beacon` in briefing.html.
8. **`recommended_history.json`** logs at least one recommended play, restoring the calibration loop's bootstrap data.

A regression test suite covering the above fixtures should land alongside Phase 5 and run on every milestone PR thereafter.

## What Not To Reopen

Both reviews independently flagged the following as already-correct or out-of-scope. **Do not reopen any of these in Phase 5.**

1. **The forbidden-string contract** in V2 (no `p`/`q`/`CI`/`confidence_score`/`final_score`/etc. in merchant HTML). It's correct and tested. Do not loosen.
2. **The materiality tiering formula** (`<$1M → max($5k, 2%)`, `$1–5M → max($10k, 3%)`, `>$5M → max($25k, 5%)`). It's defensible and contract-mandated. Do not lower or rescale.
3. **The targeting-no-dollar-headline invariant** (M8 pinned by `tests/test_targeting_no_dollar_headline.py`). Do not allow targeting cards to carry standalone $ projections.
4. **The M4b combiner reroute** (`combine_multiwindow_statistics` Fisher + inverse-variance, not min-p selection). It's correct and pinned.
5. **The M4b consistency-across-windows check** (sign-agreement count, not p-vote). It's correct and pinned by `test_not_a_p_value_vote`.
6. **The `new_customer_rate` BH dedup** (M4a T4a.6). Correct fix; legacy receipts that show `new_customer_rate.p=9.5e-05` are pre-dedup artifacts; V2 receipts are canonical.
7. **The Aura/Beacon Score's absence from V2 briefings.** Do not "bring it back to make V2 look more like legacy." Both reviews explicitly reject this.
8. **The decision-state machine** (`act` / `directional_act` / `targeting_only` / `abstain_soft` / `data_quality_block`). The state machine is correct; the bug is in the upstream wiring that produces abstain_soft for the wrong reason.
9. **The contract that Candidate has no statistics attached.** Phase 5.6 must add an *optional Measurement* block, not leak per-stat fields onto Candidate.
10. **The PM contract / 12 must-haves / 6 required QA changes** from the M0–M9 reconciled review. Phase 5 operates within them, not on them.

## Final Go / No-Go Recommendation

**GO** on Phase 5 as scoped above (6 changes, no architecture redesign, engine runnable after every change). This is small enough to hand to code-refactor-engineer as a single phased plan.

**NO-GO** on:
- Shipping either current artifact as the merchant-facing default until at least 5.1 (abstain copy) and 5.2 (rejection list always) ship.
- Restoring legacy as the renderer.
- Restarting the architecture loop.
- Any "broad redesign" beyond the 6-item Phase 5 scope.
- Authoring multiple causal priors at once. Author one (5.6), watch what happens on the realization side, then expand.

The Beauty Brand fixture should become the canonical Phase 5 acceptance test: a healthy $1.1M-ARR brand with A-grade data must produce a populated, defensible, useful briefing — not legacy's overconfident sprint plan, and not V2's empty page.
