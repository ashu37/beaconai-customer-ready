# Sprint 7 Planning Refresh — post-S6 state, research-first

**Author:** implementation-manager
**Date:** 2026-05-19
**Branch baseline:** `post-6b-restructured-roadmap`, post-Sprint-6 (PARTIAL: T3.5 Path D, KI-NEW-G resume trigger). Suite 1497p / 14s / 4 xfail / 0f.
**Supersedes:** S7 ticket sketch in `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` §B-S7 (planned ~2 weeks ago; pre-S6 lessons not yet folded).
**Status:** Plan-only. No `src/` edits. Tickets sized for code-refactor-engineer. Identifies research blockers UPFRONT so Deep Research runs can launch in parallel.

---

## Section 0 — What changed since the original §B-S7 sketch

1. **S7.5 contract surface is live and battle-tested.** `bayesian_blend` + `PSEUDO_N_BY_STATUS` (`src/sizing.py`), `PriorValidationStatus`, `PriorEntry.{validation_status, source_artifact, effective_n}` (`src/priors_loader.py`), `AbstainMode.SOFT_PRIOR_UNVALIDATED` + `ReasonCode.PRIOR_UNVALIDATED` (`src/engine_run.py`), `_route_prior_unvalidated_holds` (`src/decide.py`). Sprint 6 exercised this end-to-end on Beauty winback. S7 builders ride this same contract — no new contract-installation risk.
2. **Prior-anchored measurement pathway exists.** `src/measurement_builder.py::build_prior_anchored_play_card` + `_PRIOR_ANCHORED` dispatch is the template for all 3 S7 builders. S6-T1 (winback) + S6-T3 (replenishment) populated 2 entries; S7 grows it to 5.
3. **D-FLOOR pattern is established.** `docs/DECISIONS.md::D-FLOOR-replenishment_due` (2026-05-19) is the template: per-stage cells with per-subvertical uniformity, `mixed_<vertical>` 1.5× multiplier, strict resolver with optional supplements-absent posture, locked via DS-architect audit.
4. **S6 lessons (load-bearing):**
   - **S6-T3 burned cycles on the D-S6-2 bundle_value-as-replenishment category error.** Mid-ticket prior gap forced T3.x re-key + Gemini Deep Research run + memo authoring sprint. **THIS IS THE TRAP S7 MUST AVOID.** Every S7 builder must declare its prior posture BEFORE Commit A — and the founder needs Gemini runs in flight in parallel.
   - **`cohort_n=0` at upstream gate can defeat a flag flip even after all scaffolding lands** (S6-T3.5 Commit C deferred → KI-NEW-G). Per-SKU N≥30 (D-S6-4) interacts with cohort floor (D-FLOOR-150). For S7, ANY builder whose audience depends on a sample-size threshold at the candidate seam needs an upstream-cohort probe BEFORE Commit C.
   - **Latent enum-missing bug bit at T3.5 Commit A** (`CADENCE_DUE_REPEAT_BUYER` was authored in YAML at T3.x but the enum wasn't extended; `storytelling_v2` + `decide.py` swallow `PriorsMetadataError` silently). Each new builder's `audience_archetype` value must be cross-pinned against `AudienceArchetype` enum at impl time.
   - **Fixture-shape mismatch on synthetic G-1.** Synthetic Beauty fixture is too small / too uniform to exercise some cohort thresholds. S7-T1 / T2 / T3 should each declare which fixture exercises the activation BEFORE Commit C; if neither Beauty G-1 nor supplements G-1 will activate the card, the flag flip goes Path D and waits for real-beta.
5. **3 of 4 S7 tickets need external priors.** Only `cohort_journey_first_to_second` can reuse an existing `validated_external` prior (S7.5-T2 `first_to_second_purchase.base_rate.all`). The other two (`discount_dependency_hygiene`, `aov_lift_via_threshold_bundle`) need fresh Gemini Deep Research memos OR Path-D dormant ships.
6. **4-state abstain migration (S7-T4)** is contract-evolution, not builder-shape. `AbstainMode` already carries `SOFT_AWAITING_MEASUREMENT` + `SOFT_PRIOR_UNVALIDATED` from S7.5-T3. T4 adds `SOFT_BELOW_FLOOR` + `SOFT_AUDIENCE_TOO_SMALL` and migrates the legacy `ABSTAIN_SOFT` enum's call sites.

---

## Section 1 — Sprint 7 ticket refresh (current best understanding)

### S7-T1 — `discount_dependency_hygiene` builder

- **Anchor goal:** Ship the Tier-B builder that targets customers whose purchase history is heavily discount-conditioned, and would benefit from a value-led full-price re-engagement (mechanism: 14-day discount suppression + full-price reminder + no urgency framing — see `discount_hygiene.metadata.mechanism` in priors.yaml).
- **Builder function name + module:** `discount_dependency_hygiene_candidates` in `src/audience_builders.py`. Pattern mirrors `winback_dormant_cohort_candidates` (vertical-aware cohort definition; ranking_strategy kwarg pre-reserved for S13 ML).
- **Measurement builder entry:** `_PRIOR_ANCHORED["discount_dependency_hygiene"]` in `src/measurement_builder.py`. Consumes `discount_hygiene.margin_recovery_rate.<vertical>` IF authored as `validated_external`, OR a NEW `discount_dependency_hygiene.base_rate.<vertical>` block per founder Q (Section 5). **Today: `discount_hygiene.margin_recovery_rate.*` are all `heuristic_unvalidated`** (priors.yaml L309-334) → Path-D dormant ship unless external research promotes.
- **Flag:** `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE`, default OFF at S7-T1 impl, flip ON atomically at S7-T1.5.
- **Schema additions:**
  - `_PRIOR_ANCHORED["discount_dependency_hygiene"]` (1 dispatch key)
  - `WouldBeMeasuredBy.DISCOUNT_ATTRIBUTED_MARGIN_IN_30D` (or similar; UPPER_SNAKE_CASE, additive)
  - `AudienceArchetype.DISCOUNT_BUYER` ALREADY EXISTS (priors_loader.py:183) — no enum addition needed.
  - Play registry entry: re-use `discount_hygiene` play_id OR new `discount_dependency_hygiene` play_id (Section 5 Q1 — founder decides). **Default proposed:** new `discount_dependency_hygiene` play_id; keep legacy `discount_hygiene` for the existing M2 measured-margin pathway.
- **Expected play_id:** `discount_dependency_hygiene` (NEW).
- **Dependencies:** S6 closed; S7.5 closed (uses `bayesian_blend`, `PSEUDO_N_BY_STATUS`, `PRIOR_UNVALIDATED` refusal). Independent of S7-T2 / T3 / T4.
- **Out of scope:** legacy `discount_hygiene` deletion; offer-depth optimization (D-6 ML-ban territory); margin-arithmetic in renderer (Stop-Coding Line).
- **Estimated commit count:** 3 commits at T1 (impl + memory + summary) + 3 at T1.5 (flip + memory + summary) = 6.

### S7-T2 — `cohort_journey_first_to_second` builder (retires Phase 5.6 `first_to_second_purchase` proxy)

- **Anchor goal:** Replace the L28-only Phase 5.6 directional builder (`measurement_builder.build_directional_play_card` for `first_to_second_purchase`) with a proper cohort-journey builder that ranks customers by predicted-second-purchase-window cadence; ride the validated_external `first_to_second_purchase.base_rate.all` prior (S7.5-T2 promotion, effective_n=156110) via the prior-anchored pathway.
- **Builder function name + module:** `cohort_journey_first_to_second_candidates` in `src/audience_builders.py`. Pattern: per-customer one-time-buyer cohort, age-since-first-purchase windowing per vertical (beauty 30-90d / supplements 21-60d; founder Q in Section 5).
- **Measurement builder entry:** `_PRIOR_ANCHORED["cohort_journey_first_to_second"]` in `src/measurement_builder.py`. Consumes `first_to_second_purchase.base_rate.*` (already `validated_external`, effective_n=156110, source_artifact `config/priors_sources/first_to_second_purchase__base_rate.md`).
- **Flag:** `ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND`, default OFF at T2 impl, flip ON atomically at T2.5. ON-flip ALSO retires the Phase 5.6 directional builder path for `first_to_second_purchase` (mechanical guard: `build_directional_play_card` skips when flag ON).
- **Schema additions:**
  - `_PRIOR_ANCHORED["cohort_journey_first_to_second"]` (1 dispatch key)
  - `WouldBeMeasuredBy.SECOND_PURCHASE_IN_30D` (NEW; UPPER_SNAKE_CASE) — distinct from existing `REPEAT_PURCHASE_IN_30D` because it's anchored to first-to-second specifically.
  - `AudienceArchetype.FIRST_TIME_BUYER` ALREADY EXISTS (priors_loader.py:181) — no enum addition.
  - Play registry entry: NEW `cohort_journey_first_to_second` (the existing `first_to_second_purchase` registry entry stays for the directional builder until T2.5 retires it).
- **Expected play_id:** `cohort_journey_first_to_second` (NEW). The legacy `first_to_second_purchase` play_id stays in the registry but with a `superseded_by` marker — do NOT delete (the S7.5-T2 memo + the S5-T2 supplements `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` plumbing reference it).
- **Dependencies:** S6 closed; S7.5-T2 prior must be in place (it is — `validated_external`).
- **Out of scope:** Berkson-class cohort-definition rework (preserve the early-half counts rule per B-5); legacy directional builder *deletion* (T2.5 retires the dispatch, keeps the function for one sprint of cushion); S5-T2 supplements typed-abstain plumbing changes.
- **Estimated commit count:** 3 + 3 = 6.

### S7-T3 — `aov_lift_via_threshold_bundle` builder

- **Anchor goal:** Tier-B builder that surfaces customers near AOV-threshold-bundle eligibility (e.g., $5-$15 below a "free shipping" or "spend $X get $Y" threshold), where a curated cross-sell to clear the threshold has defensible expected value. Mechanism: cadence-timed cross-sell email with threshold-completion bundle suggestion, no blanket discount.
- **Builder function name + module:** `aov_lift_via_threshold_bundle_candidates` in `src/audience_builders.py`. Pattern: per-customer near-threshold detection over a configurable look-back window; threshold inferred from merchant's shipping/promo config OR a `aov_lift_via_threshold_bundle.threshold` prior key (founder Q in Section 5).
- **Measurement builder entry:** `_PRIOR_ANCHORED["aov_lift_via_threshold_bundle"]` in `src/measurement_builder.py`. Consumes EITHER `bestseller_amplify.bundle_value.beauty` (validated_external, but **same D-S6-2 category-error risk that bit S6-T3** — bundle_value is per-customer DOLLARS, not a probability rate) OR a NEW `aov_lift_via_threshold_bundle.base_rate.<vertical>` block at validated_external (requires Deep Research).
- **Flag:** `ENGINE_V2_BUILDER_AOV_BUNDLE`, default OFF at T3 impl, flip ON atomically at T3.5.
- **Schema additions:**
  - `_PRIOR_ANCHORED["aov_lift_via_threshold_bundle"]` (1 dispatch key)
  - `WouldBeMeasuredBy.AOV_THRESHOLD_CONVERSION_IN_14D` (NEW)
  - `AudienceArchetype.THRESHOLD_NEAR_BUYER` (NEW) — closest existing is `HERO_SKU_BUYER` (not the same archetype). **Latent missing-enum risk** (parallel to `CADENCE_DUE_REPEAT_BUYER` in S6) — cross-pin enum addition at impl time.
  - Play registry entry: NEW `aov_lift_via_threshold_bundle`.
- **Expected play_id:** `aov_lift_via_threshold_bundle` (NEW).
- **Dependencies:** S6 closed; S7.5 closed. Independent of S7-T1 / T2. **Hardest of the 3 builders** because the prior + the threshold detection both need design choices.
- **Out of scope:** auto-tuning of the threshold offset (D-6 territory); free-shipping integration (D-5); reading Shopify shipping config (D-5).
- **Estimated commit count:** 3 + 3 = 6.

### S7-T4 — 4-state abstain migration

- **Anchor goal:** Migrate the 2-state `ABSTAIN_SOFT` enum to the typed 4-state `AbstainMode`:
  - `SOFT_AWAITING_MEASUREMENT` (default; "no measured / directional cards") — EXISTS from S7.5-T3
  - `SOFT_PRIOR_UNVALIDATED` — EXISTS from S7.5-T3
  - `SOFT_BELOW_FLOOR` — NEW (materiality floor failure dominates)
  - `SOFT_AUDIENCE_TOO_SMALL` — NEW (audience floor failure dominates across all candidates)
- **Builder function name + module:** Not a builder; this is a `decide.py` migration. Extend `_compute_abstain_mode` in `src/decide.py` (introduced at S7.5-T3) to inspect Considered cards' typed `reason_code` and route to the dominant-mode value. Drop legacy `ABSTAIN_SOFT` aliasing by S10 per IM plan; T4 introduces the 4-state but keeps `DecisionState.ABSTAIN_SOFT` as the parent (mode is the sub-typing).
- **Flag:** `ENGINE_V2_ABSTAIN_4STATE`, default OFF at T4 impl, flip ON atomically at T4.5.
- **Schema additions:**
  - `AbstainMode.SOFT_BELOW_FLOOR` (NEW enum value)
  - `AbstainMode.SOFT_AUDIENCE_TOO_SMALL` (NEW enum value)
  - No new `_SUPPORTED` / `_PRIOR_ANCHORED` entries.
  - No new `WouldBeMeasuredBy` / `AudienceArchetype` enums.
- **Expected play_id:** N/A (orthogonal to builders).
- **Dependencies:** None on S7-T1/T2/T3 (T4 can land FIRST in the sprint to de-risk later builders surfacing typed abstains). Could even ship BEFORE T1 (founder Q in Section 5).
- **Out of scope:** Renderer copy changes (Stop-Coding Line; merchant briefing reads `Abstain.mode` only via JSON consumers); `ABSTAIN_HARD` migration; legacy `ABSTAIN_SOFT` deletion (deferred to S10 per §B-S7).
- **Estimated commit count:** 3 + 3 = 6.

**Sprint total:** 24 commits across 4 tickets × 2 sub-tickets each (impl + flip). ~10 working days if research blockers don't gate.

---

## Section 2 — Per-ticket research needs (LOAD-BEARING)

### S7-T1 — `discount_dependency_hygiene`

**(a) What prior does it consume?**
A `base_rate` (probability that an audience member converts to a full-price repeat purchase during the 14-day discount-suppression window).

**(b) Existing prior block coverage?**
`discount_hygiene.margin_recovery_rate.{beauty, supplements, mixed}` exists (priors.yaml L309-334) but is **all `heuristic_unvalidated`** AND is the WRONG SHAPE (margin recovery rate, not full-price conversion probability). Same dimensional category as the D-S6-2 bundle_value error. **A new `discount_dependency_hygiene.base_rate.<vertical>` block is REQUIRED.**

**(c) Achievable `validation_status`?**
- `validated_external` — achievable IF Tier-1 source returns DTC beauty/supplements discount-suppression conversion benchmarks. Klaviyo / Shopify / Postscript / RechargePayments publish discount-flow benchmarks; isolation to "discount-suppression-recipient repeat rate" requires careful prompt scoping.
- `validated_internal` — not achievable (no outcome data).
- `elicited_expert` — fallback if Deep Research returns thin sources; founder-elicited 60-day envelope.
- `heuristic_unvalidated` — Path-D dormant ship (parallel to S6-T3.5 Commit C deferral).

**(d) Gemini Deep Research prompt — discount_dependency_hygiene (BEAUTY):**

```
You are a research analyst building external benchmark memos for a DTC
ecommerce decision engine. Author a benchmark memo for the prior
`discount_dependency_hygiene.base_rate` (vertical: BEAUTY) intended for
validated_external promotion.

The metric: probability that a customer who has been historically
discount-conditioned (>= 50% of their orders carried a discount code)
converts to ONE full-price repeat purchase within a 14-30 day window
after receiving a value-led, no-urgency, full-price email send, where
discount codes have been suppressed for the 14 days prior.

VERTICAL SCOPING: DTC beauty (skincare, cosmetics, haircare, personal
care). AOV $20-$120 range. Brands with at least one repeat-purchase
flow active. Email-attributed, 5-day last-touch attribution OK.

SOURCE-QUALITY BAR (Tier 1 only):
- Klaviyo: 2026 Omnichannel Benchmark Report, H&B vertical case studies
- Shopify Plus: DTC discount strategy reports (NOT blog speculation)
- Postscript / Attentive: SMS-discount-suppression benchmarks
- RechargePayments / Ordergroove: subscription cohort discount data
- Peer-reviewed marketing-science journals (J. Marketing Research,
  Marketing Science) on price-discount elasticity in CPG / DTC contexts.
Explicitly REJECT: agency blog posts without auditable sample sizes,
unverified case studies, SMS-conversion-rate sources without isolation
of discount-suppression cohorts.

REQUIRED OUTPUTS:
1. Point estimate (probability 0.0-1.0)
2. range_p10 and range_p90 (conservative bounds; not naive 1-sigma)
3. effective_n (sample-size weight for Bayesian blend; cap at 30 unless
   source discloses N >= 100,000)
4. Primary source list with URLs and access date
5. "What this measures" (1 paragraph)
6. "What this does NOT measure" (rejected confounds: cart abandonment,
   winback, replenishment, welcome flows, paid acquisition, etc.)
7. "Alternative sources considered + rejected" (with why)
8. Limitations of the benchmark (attribution model, channel-mix,
   discount-depth-dependence)
9. Beta(alpha, beta) shape parameters for the prior given the chosen N

Saving discipline: memo will be saved verbatim as
config/priors_sources/discount_dependency_hygiene__base_rate__beauty.md
BEFORE any wiring. Future engineering work cites this file, never
paraphrases.
```

**SUPPLEMENTS variant:** same prompt with VERTICAL SCOPING changed to "DTC supplements/wellness (protein, multivitamin, probiotic, functional, nootropic). AOV $25-$80. Brands subscription-led OR one-time-led; isolate one-time-led cohort because subscription-led discount-conditioning has different dynamics." Source-quality bar adds: iHerb / Ritual / Care/of subscription discount benchmarks.

**(e) Per-vertical applicability:**
Per D-S6-2.1 lesson (asymmetric posture for replenishment): **author Beauty and Supplements as SEPARATE memos**. If supplements Deep Research returns thin, ship Beauty-only validated_external + supplements `heuristic_unvalidated` (Path-D dormant on supplements). DS architect endorsed asymmetric posture explicitly for replenishment_due; same pattern here.

**Latent missing-enum risk:** none (DISCOUNT_BUYER exists).

---

### S7-T2 — `cohort_journey_first_to_second`

**(a) What prior does it consume?**
A `base_rate` (probability that a first-time buyer converts to a second purchase within the next 30 days).

**(b) Existing prior block coverage?**
**YES.** `first_to_second_purchase.base_rate` (vertical: `"*"`, validated_external, effective_n=156110, value=0.18, source_artifact `config/priors_sources/first_to_second_purchase__base_rate.md`) is live and consumed today by Phase 5.6 directional builder. S7-T2 re-routes its consumption from the directional path to the prior-anchored path.

**(c) Achievable `validation_status`?**
ALREADY `validated_external` (bsandco 2026 DTC RPR benchmarks, N=156,110). No new memo required.

**(d) Gemini Deep Research prompt:**
**NOT REQUIRED.** This is the one S7 builder that can ship WITHOUT external research.

**(e) Per-vertical applicability:**
Wildcard `applies_to: { vertical: "*" }` (bsandco source spans verticals). Works for beauty + supplements + mixed without per-vertical memos.

**Latent missing-enum risk:** SECOND_PURCHASE_IN_30D added to WouldBeMeasuredBy at impl time. FIRST_TIME_BUYER archetype exists.

**FLAGGED:** This builder can ship IMMEDIATELY at Commit A — no research blocker.

---

### S7-T3 — `aov_lift_via_threshold_bundle`

**(a) What prior does it consume?**
A `base_rate` (probability that an audience member exposed to a threshold-completion cross-sell email completes one threshold-crossing order in the next 14 days) — NOT the existing `bestseller_amplify.bundle_value` (which is per-customer dollars; D-S6-2 category error redux).

**(b) Existing prior block coverage?**
**NO.** `bestseller_amplify.bundle_value.beauty` is validated_external but it's a DOLLAR value, not a probability rate; consuming it would re-introduce the exact D-S6-2 error that DS architect rejected at S6-T3.x. **A new `aov_lift_via_threshold_bundle.base_rate.<vertical>` block is REQUIRED.**

**(c) Achievable `validation_status`?**
- `validated_external` — achievable IF Tier-1 source returns AOV-threshold-cross-sell conversion benchmarks. Klaviyo cross-sell flow benchmarks ≈ 1.90% (Balance Me case in the replenishment memo cites this for skincare-cross-sell). Shopify Plus reports AOV-tier benchmarks but typically don't isolate threshold-completion cohorts.
- `elicited_expert` — likely fallback; AOV-threshold cohorts are narrower than discount/winback/replenishment so Tier-1 sources may not isolate.
- `heuristic_unvalidated` — Path-D dormant ship.

**(d) Gemini Deep Research prompt — aov_lift_via_threshold_bundle (BEAUTY):**

```
Author a benchmark memo for the prior
`aov_lift_via_threshold_bundle.base_rate` (vertical: BEAUTY) intended
for validated_external promotion.

The metric: probability that a customer who is currently $5-$15 below a
merchant-defined AOV threshold (free shipping, "spend $X get $Y", or
bundle-tier threshold) converts to ONE threshold-crossing order within
14 days after receiving a curated cross-sell email suggesting a
specific SKU that would complete the threshold, with NO discount code
attached.

VERTICAL SCOPING: DTC beauty (skincare, cosmetics, haircare, personal
care). AOV thresholds typically $50, $75, $100. Brands with at least
one cross-sell flow active.

SOURCE-QUALITY BAR (Tier 1 only):
- Klaviyo: cross-sell flow benchmarks (Balance Me case study cites
  1.90% skincare cross-sell flow conversion; locate the broader
  Klaviyo cross-sell category benchmark)
- Shopify Plus: AOV-tier conversion reports
- ConvertCart / Yotpo: threshold-bundle case studies
- Peer-reviewed retail-marketing journals on basket-completion lift
Explicitly REJECT: generic "cross-sell increases AOV by 20%" claims
without isolation of threshold-completion cohorts, agency blog speculation.

REQUIRED OUTPUTS (same shape as discount_dependency_hygiene memo above):
1. Point estimate
2. range_p10, range_p90
3. effective_n
4. Primary sources + URLs
5. What this measures
6. What this does NOT measure (carefully distinguish from
   bestseller_amplify [which is a hero-SKU bundle, NOT a threshold
   completion], from welcome-flow cross-sell, from post-purchase
   thank-you cross-sell)
7. Alternative sources rejected
8. Limitations
9. Beta(alpha, beta) shape for chosen N

Saved verbatim at
config/priors_sources/aov_lift_via_threshold_bundle__base_rate__beauty.md
BEFORE wiring.
```

**SUPPLEMENTS variant:** scope to supplements vertical; thresholds typically $50, $75. The same asymmetric posture from replenishment_due likely applies — supplements may return thin; ship Beauty-only validated_external + supplements `heuristic_unvalidated` if so.

**(e) Per-vertical applicability:**
Two separate memos (per S6 D-S6-2.1 lesson). Asymmetric posture expected.

**Latent missing-enum risk:** **THRESHOLD_NEAR_BUYER archetype is NEW.** Cross-pin `AudienceArchetype` enum extension at impl time (parallel to `CADENCE_DUE_REPEAT_BUYER` fix at S6-T3.5 Commit A). Also new `AOV_THRESHOLD_CONVERSION_IN_14D` in WouldBeMeasuredBy.

---

### S7-T4 — 4-state abstain migration

**No external research needed.** Pure contract evolution within `event_version=1`. The 4-state mapping is design + DECISIONS-lock work (Section 3), not external benchmark work.

---

### Research-needs summary table

| Ticket | New external memo needed? | Beauty memo | Supplements memo | Fallback if research returns thin |
|---|---|---|---|---|
| S7-T1 discount_dependency_hygiene | YES | REQUIRED | REQUIRED (separate) | Path-D dormant ship |
| S7-T2 cohort_journey_first_to_second | NO | reuses S7.5-T2 | reuses S7.5-T2 (wildcard) | n/a — can ship immediately |
| S7-T3 aov_lift_via_threshold_bundle | YES | REQUIRED | REQUIRED (separate) | Path-D dormant ship |
| S7-T4 4-state abstain | NO | n/a | n/a | n/a |

**Total Gemini Deep Research runs to launch in parallel:** **4** (Beauty + Supplements × discount_hygiene + aov_threshold). All 4 should be triggered BEFORE any S7 code work begins.

---

## Section 3 — DECISIONS.md gaps to lock BEFORE Commit A

These need founder lock before agent dispatch on the corresponding ticket. DS-architect review recommended where flagged.

### Gap A — `D-FLOOR-discount_dependency_hygiene` per-stage audience floors (S7-T1)

**Status:** required before S7-T1 Commit A.
**Pattern:** parallel to `D-FLOOR-replenishment_due` (DECISIONS.md L76-95).
**Proposed default (DS-architect review):**

| stage | beauty subverticals | mixed_beauty (1.5×) | supplements subverticals | mixed_supplements (1.5×) |
|---|---|---|---|---|
| startup | 80 | 120 | 60 | 90 |
| growth | 200 | 300 | 150 | 225 |
| mature | 500 | 750 | 400 | 600 |
| enterprise | 1500 | 2250 | 1200 | 1800 |

**Reasoning:** Mirrors `D-S6.5-1/2` winback floors (winback and discount-dependency are both behavioral-history-based audiences; pool sizes should be comparable). Supplements asymmetric lower (per D-S6.5-2 reasoning: smaller dormant pools at any store size). Materiality floor `$2000` independently binds dollar-impact. **DS architect must validate** the symmetry with winback before lock.

### Gap B — `D-FLOOR-cohort_journey_first_to_second` per-stage audience floors (S7-T2)

**Status:** required before S7-T2 Commit A.
**Proposed default (clerical):**

| stage | beauty | mixed_beauty (1.5×) | supplements | mixed_supplements (1.5×) |
|---|---|---|---|---|
| startup | 40 | 60 | 40 | 60 |
| growth | 100 | 150 | 100 | 150 |
| mature | 300 | 450 | 300 | 450 |
| enterprise | 1000 | 1500 | 1000 | 1500 |

**Reasoning:** First-time buyers in a 30-90d age window are typically a LARGER addressable pool than dormant/replenishment cohorts at any store size — first-time buyers are a recurring stream. Lower floors than winback. Symmetric across verticals (S7.5-T2 prior is wildcard `*`; the prior itself doesn't argue asymmetry). **Clerical lock, DS-architect ratification optional.**

### Gap C — `D-FLOOR-aov_lift_via_threshold_bundle` per-stage audience floors (S7-T3)

**Status:** required before S7-T3 Commit A.
**Proposed default (DS-architect review):**

| stage | beauty | mixed_beauty (1.5×) | supplements | mixed_supplements (1.5×) |
|---|---|---|---|---|
| startup | 40 | 60 | 30 | 45 |
| growth | 100 | 150 | 80 | 120 |
| mature | 250 | 375 | 200 | 300 |
| enterprise | 750 | 1125 | 600 | 900 |

**Reasoning:** Near-threshold cohorts are NARROWER than first-to-second (a near-threshold customer is a snapshot constraint; a first-time buyer is a longer-window constraint). Floors slightly tighter than first-to-second. Supplements lower (parallel to replenishment_due no-cell-by-design? — Section 5 Q for founder: do we permit supplements at all, or carry the asymmetric-no-cell pattern again?). **DS architect must validate** the supplements posture.

### Gap D — `D-ENVELOPE-discount_dependency_hygiene` posterior envelope check (S7-T1.5)

**Status:** required before S7-T1.5 Commit C (flag flip).
**Pattern:** parallel to D-S6-3 (replenishment_due envelope).
**Proposed default (clerical, contingent on Deep Research return):**
Posterior p50 must land inside the prior's `[range_p10, range_p90]` envelope on the activation fixture. If Deep Research returns `[p10=X, p90=Y]`, the envelope is automatic; if research returns thin → Path D, no envelope check needed (card stays dormant).

### Gap E — `D-ENVELOPE-aov_lift_via_threshold_bundle` posterior envelope check (S7-T3.5)

**Status:** required before S7-T3.5 Commit C. Same pattern as Gap D.

### Gap F — `D-S7-T4-abstain-routing` precedence for 4-state migration

**Status:** required before S7-T4 Commit A.
**Pattern:** parallel to R5 in §B-S10 risk register (ReasonCode precedence on Considered cards) + existing `_HARD_DQ_FLAGS` precedence in `decide.py`.
**Proposed default (DS-architect review):**

When ABSTAIN_SOFT fires AND Considered cards exist, `_compute_abstain_mode` walks Considered in this precedence order:

1. ANY `PRIOR_UNVALIDATED` reason → `SOFT_PRIOR_UNVALIDATED` (existing S7.5-T3 behavior; PRESERVE)
2. ALL non-PRIOR_UNVALIDATED reasons are `MATERIALITY_BELOW_FLOOR` → `SOFT_BELOW_FLOOR` (NEW)
3. ALL non-PRIOR_UNVALIDATED reasons are `AUDIENCE_TOO_SMALL` → `SOFT_AUDIENCE_TOO_SMALL` (NEW)
4. ELSE → `SOFT_AWAITING_MEASUREMENT` (catch-all; existing default)

**Reasoning:** PRIOR_UNVALIDATED is the strongest typed claim (engine refuses to project) and takes precedence; below-floor and audience-too-small are both gate failures but reflect different operator interventions (raise marketing-spend ambition vs. wait for cohort to grow). Catch-all preserves backward-compat with pre-T4 ABSTAIN_SOFT semantics.

**Call sites needing explicit per-site routing decisions:**
- `src/decide.py::_compute_abstain_mode` — central seam.
- `src/main.py::_emit_substrate_events` — `recommendation_considered` payload's `reason_code` is unchanged (still per-card typed); only `Abstain.mode` reflects the new precedence.
- `src/storytelling_v2.py` — renderer reads `Abstain.state` not `Abstain.mode` today (Stop-Coding Line); no source/copy change.
- `src/engine_run_adapter.py::DecisionState.ABSTAIN_SOFT = PUBLISH if play_cards else ABSTAIN_SOFT` (L425) — unchanged at the legacy path.

**Legacy ABSTAIN_SOFT call sites needing audit:** grep shows 30+ refs; most are in storytelling/guardrails/anomaly and reference the *state*, not the *mode*. The migration is mode-additive, state-stable. Founder lock: confirm "no legacy call site needs migration; T4 only extends the typed mode slot."

### Gap G — Subvertical applicability for the 3 new builders

**Status:** required before each builder's Commit A.
**Pattern:** parallel to D-S6.5-22 (per-play audience floors authored only for active builders).
**Proposed default (clerical):**
Each new builder authors per-subvertical floor cells in `gate_calibration.yaml` for ALL 4 beauty subverticals + `mixed_beauty` (uniform per Gaps A-C grids). For supplements: `discount_dependency_hygiene` ships per-subvertical cells (symmetric posture if research returns); `aov_lift_via_threshold_bundle` may carry asymmetric-no-cell (founder decides per Section 5 Q3). `cohort_journey_first_to_second` ships all-subvertical cells (the prior is wildcard, the floor should be too).

---

## Section 4 — Sprint 7 critical-path + parallelization plan

### Work that can START IMMEDIATELY (no blockers)

- **S7-T2 (`cohort_journey_first_to_second`) impl** — reuses S7.5-T2 validated_external prior; no research blocker. Only needs Gap B floor lock (clerical, low-risk for DS-architect ratify-in-flight).
- **S7-T4 (4-state abstain) impl** — pure contract evolution. Needs Gap F lock (DS-architect review of precedence). Code work can proceed as soon as Gap F locks.
- **Gemini Deep Research runs** — 4 prompts to launch IMMEDIATELY (Beauty + Supplements × discount_hygiene + aov_threshold). Triggered in parallel with T2 impl.

### Work BLOCKED on Gemini Deep Research returns

- **S7-T1 (`discount_dependency_hygiene`) impl** — blocked until at least the Beauty memo returns (supplements can Path-D dormant if its memo is thin). Expected blocker duration: 24-72 hours per Deep Research run experience (S6-T3.x memo returned same-day; YMMV).
- **S7-T3 (`aov_lift_via_threshold_bundle`) impl** — same blocker as T1. The aov_threshold prompt is narrower than discount_hygiene; higher risk of thin return → Path-D dormant ship more likely.

### Work BLOCKED on DS architect review of DECISIONS gaps

- **S7-T1** — blocked on Gap A (DS-review) + Gap D (clerical, deferable).
- **S7-T3** — blocked on Gap C (DS-review) + Gap E (clerical, deferable) + Gap G supplements decision (founder Q3).
- **S7-T4** — blocked on Gap F (DS-review of precedence).
- **S7-T2** — blocked only on Gap B (clerical).

### Recommended commit order (optimizes parallel research + early activation)

1. **Day 0 (now):** Founder fires off 4 Gemini Deep Research prompts (Beauty + Supplements × discount_hygiene + aov_threshold). Founder issues founder Qs (Section 5) for Gap F + Gap G.
2. **Day 0-1:** DS architect reviews Gaps A, C, F (one bundled audit memo — same pattern as S6-T3.x's DS architect ratification).
3. **Day 1-2:** S7-T2 impl + S7-T2.5 flip. First Sprint 7 ticket closed. Suite passes; Beauty pinned slate gains the new `cohort_journey_first_to_second` card (likely replaces the directional `first_to_second_purchase` card from Phase 5.6); supplements stays Considered with PRIOR_UNVALIDATED (wildcard prior is `validated_external` so actually NO — supplements first-to-second prior is the same wildcard `*`, so supplements may ALSO activate; this is a hard-stop probe at T2.5).
4. **Day 2-3:** S7-T4 impl + S7-T4.5 flip. 4-state abstain migration. Suite passes; supplements `Abstain.mode` may flip from `SOFT_AWAITING_MEASUREMENT` to `SOFT_PRIOR_UNVALIDATED` (if it was carrying PRIOR_UNVALIDATED reason codes) — Beauty stays PUBLISH.
5. **Day 3-5:** Deep Research returns evaluated. Memos saved verbatim (per S6-T3.x discipline, BEFORE wiring). Memos that return thin → Path-D dormant decisions documented.
6. **Day 5-7:** S7-T1 impl + S7-T1.5 flip (discount_dependency_hygiene). Beauty + supplements activation depends on memo quality. If Path-D dormant: flag stays OFF, scaffolding lands, KI-NEW-J filed (parallel to KI-NEW-G).
7. **Day 7-10:** S7-T3 impl + S7-T3.5 flip (aov_lift_via_threshold_bundle). Same Path-D risk.

**Net:** if research returns clean memos, all 4 tickets close in ~10 days. If 2-of-2 high-risk memos go Path-D, sprint still closes T2 + T4 in 3 days; T1 + T3 ship dormant-scaffolded.

### Risk register: S6 failure modes that could repeat in S7

| Risk | Source S6 ticket | Mitigation in S7 |
|---|---|---|
| Mid-ticket prior gap discovered (D-S6-2 redux) | S6-T3 → T3.x re-key cycle | Research-FIRST discipline. All 4 memos in flight BEFORE Commit A on T1 / T3. |
| cohort_n=0 at upstream gate defeats activation (KI-NEW-G) | S6-T3.5 Commit C deferred | Upstream-cohort probe BEFORE each flip ticket's Commit C. For T1: probe `discount_buyer` cohort size on Beauty + supplements G-1. For T3: probe near-threshold cohort. For T2: probe first-time-buyer-in-window cohort. If any probe returns 0, Path-D the corresponding flip ticket. |
| Latent missing-enum bug (CADENCE_DUE_REPEAT_BUYER fix at T3.5 Commit A) | S6-T3.5 | Cross-pin enum addition at impl-ticket time. T3 specifically: THRESHOLD_NEAR_BUYER + AOV_THRESHOLD_CONVERSION_IN_14D both NEW. Test pins archetype + measured-by enum membership before flag flip. |
| Fixture-shape mismatch on synthetic G-1 | S6-T1.5 (winback cohort 356 < 500 floor on Beauty G-1) | Section 5 Q5: do we accept Path-D on any of T1/T3 ahead of time? Founder decision documented before impl. |
| Bundle_value-as-rate category error | D-S6-2 | T3-specific risk. The memo prompt EXPLICITLY scopes to "probability rate, not dollar amount" — and DS architect ratification of the new `aov_lift_via_threshold_bundle.base_rate` block prevents reuse of `bestseller_amplify.bundle_value` (the obvious wrong path). |
| Berkson-invariant regression | B-5 test guard | T2-specific risk (`cohort_journey_first_to_second` is the journey play). Preserve early-half-counts cohort definition; T2 must NOT re-introduce post-period cohort definition. B-5 invariant test already pins this. |

---

## Section 5 — Founder Q surface

Surface these BEFORE agent dispatch on the corresponding ticket. Each carries a proposed default that lets work proceed if founder is unavailable.

### Q1 — `discount_dependency_hygiene` play_id naming

**Question:** Ship as a NEW `discount_dependency_hygiene` play_id (parallel to legacy `discount_hygiene`)? Or refactor `discount_hygiene` in-place to consume the new prior + builder?

**Default (proposed):** NEW `discount_dependency_hygiene` play_id. Keep legacy `discount_hygiene` for the M2 measured-margin pathway (Recommended Experiment allowlist member; KI-21). The two are operationally distinct: legacy `discount_hygiene` measures margin recovery on already-discount-codes; the new `discount_dependency_hygiene` is a prior-anchored full-price-conversion play.

**Why founder must decide:** Naming locks the play registry. Once shipped, renames are migrations (priors.yaml, audience_builders.py, measurement_builder.py, decide.py allowlist, renderer copy, recommended_history.json keys per memory).

### Q2 — S7-T4 abstain migration ordering

**Question:** Ship S7-T4 (4-state abstain) BEFORE or AFTER the 3 new builders?

**Default (proposed):** BEFORE. Reasons: (a) T4 is independent of builders, (b) shipping T4 first means the new builders' typed abstains land in the new 4-state surface from day 1, (c) T4 is the lowest-risk of the 4 tickets (no research blocker, no fixture re-pin behavior change expected on current synthetics — Beauty stays PUBLISH, supplements stays in `SOFT_PRIOR_UNVALIDATED` or `SOFT_AWAITING_MEASUREMENT`).

**Counter-argument for AFTER:** Founder may prefer to see the new builders' Considered-card distributions before locking the typed-mode precedence (Gap F). Could lock Gap F provisionally on T4 then reconsider at the END of S7 if a builder surfaces a typed reason that needs different precedence.

### Q3 — `aov_lift_via_threshold_bundle` supplements posture

**Question:** Do we author a supplements `aov_lift_via_threshold_bundle.base_rate` block (symmetric posture, requires supplements Deep Research memo)? Or carry the asymmetric-no-cell pattern from D-PRIORS-replenishment_due_supplements_deferred (DS-architect-endorsed for replenishment)?

**Default (proposed):** Asymmetric-no-cell. AOV-threshold-bundle economics are weaker in supplements (subscription-led merchants don't have meaningful threshold-bundle dynamics; one-time-led supplements are a small subset). Supplements routes to PRIOR_UNVALIDATED Considered via S7.5-T3 refusal logic. Re-evaluate post-beta.

**Founder must decide:** the asymmetric pattern is becoming routine (replenishment_due is asymmetric; this would be the second). Worth confirming the pattern is intentional and won't compound into a beauty-only product.

### Q4 — Hard-stop calibration envelope for the activation tickets

**Question:** Same envelope rule as D-S6-3 (posterior p50 must land inside prior's `[range_p10, range_p90]`)? Or tighten/loosen per ticket?

**Default (proposed):** Same rule for all 3 activation tickets (T1.5, T2.5, T3.5). Out-of-envelope → STOP, ping orchestrator. Consistency with S6-T1.5 and S6-T3.5 hard-stop discipline.

### Q5 — Path-D acceptance ahead of impl (synthetic-fixture cohort sizing)

**Question:** Do we accept up-front that any of S7-T1 / S7-T3 may ship Path-D (dormant scaffolding) if either (a) Deep Research returns thin OR (b) the upstream-cohort probe on the activation fixture returns 0?

**Default (proposed):** YES, accept Path-D as a possible outcome on T1 / T3. This was the right call at S6-T3.5 Commit C; the same conditions may bite here. Founder pre-approval avoids a mid-sprint pause/audit (like S6-T3 → T3.x → T3.y → T3.z → T3.5 partial).

**This is the single highest-risk question.** A Path-D ship is honest engineering, but if the founder needs all 3 builders live for beta retention, S7 fails its anchor goal under Path-D ships. Founder direction on "beta success requires all 5 Tier-B builders activate on Beauty" vs "ship the scaffolding; activate when real-beta data arrives" is the load-bearing strategic call for S7.

---

## Section 6 — What S7 does NOT do (preserved out-of-scope discipline)

- No Play Library refactor (S8).
- No EB blend (S8).
- No ML predictive layer (S10-S13).
- No Phase 9 outcome importer (post-beta, S15+).
- No renderer / HTML work (Stop-Coding Line).
- No new vertical beyond `{beauty, supplements, mixed}` (D-8).
- No deletion of legacy `first_to_second_purchase` (one sprint of cushion past T2.5).
- No deletion of `ABSTAIN_SOFT` enum alias (S10 per IM plan).
- No new `validation_status` enum values (the 5-value closed set from S7.5-T1 is frozen).
- No causal/incrementality prior promotions (Part III-1 Step 4: base_rate / bundle_value only).
- No Shopify shipping-config integration (D-5) for T3 threshold detection.
- No Klaviyo / Postscript network calls (D-5).
- No event_version=2 bump.
- No `mixed` end-to-end fixture (KI-28 stays tracked).

---

## Cross-link index

- IM plan §B-S7 sketch: `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` L81-93
- S6 reference precedent: `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-s6-tier-b-builders-plan.md`
- S6 closeout memory: `/Users/atul.jena/Projects/Personal/beaconai/memory.md` L533-850 (full Sprint 6 block)
- DECISIONS registry: `/Users/atul.jena/Projects/Personal/beaconai/docs/DECISIONS.md`
- Replenishment_due memo template: `/Users/atul.jena/Projects/Personal/beaconai/config/priors_sources/replenishment_due__base_rate__beauty.md`
- Existing first_to_second_purchase memo (S7-T2 reuse): `/Users/atul.jena/Projects/Personal/beaconai/config/priors_sources/first_to_second_purchase__base_rate.md`
- S7.5 contract surface: `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py::PSEUDO_N_BY_STATUS`, `bayesian_blend`; `/Users/atul.jena/Projects/Personal/beaconai/src/priors_loader.py::PriorValidationStatus`
- S6 builder pattern: `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py::build_prior_anchored_play_card` + `_PRIOR_ANCHORED`
- Audience builder pattern: `/Users/atul.jena/Projects/Personal/beaconai/src/audience_builders.py::winback_dormant_cohort_candidates`
- Decide-seam abstain mode: `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py::_compute_abstain_mode`
- KIs S7 expected to close: KI-21 (supplements zero Recommended Experiment), KI-23 (supplements plays drop out)
- KIs S7 may file new: KI-NEW-J (parallel to KI-NEW-G if T1 Path-D); KI-NEW-K (if T3 Path-D)
