# S6-T3.x Summary — `replenishment_due` prior re-key + audit-response sprint

**Ticket:** S6-T3.x (per the 5-ticket audit-response sequence locked 2026-05-19 in `agent_outputs/code-refactor-engineer-s6-t3-summary.md` §7)
**Date:** 2026-05-19
**Branch:** post-6b-restructured-roadmap
**Status:** Impl complete. Flag `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` stays default OFF. All 5 pinned fixtures byte-identical under flag OFF. Suite green: 1422 passed.

---

## 1. Approved scope (6 items)

1. **YAML insert** — dedicated `replenishment_due.base_rate.beauty` validated_external block in `config/priors.yaml`.
2. **Dispatch update** — `_PRIOR_ANCHORED["replenishment_due"]` consumes `replenishment_due.base_rate` (not `bestseller_amplify.bundle_value`).
3. **N=30 G-1 probe** — verify supplements cadence floor on real fixture (NOT committed; one-time probe).
4. **DECISIONS.md** — supersede D-S6-2, author D-S6-2.1, demote framing on 5 entries (D-S6.5-12, -17, -18, -19, D-S7.5-3).
5. **KNOWN_ISSUES.md** — file 6 new architectural-limitations KIs (KI-NEW-A..F).
6. **Tests** — new `tests/test_s6_t3_x_prior_rekey.py` (6 tests); update tests that pinned the superseded D-S6-2 wiring.

---

## 2. Patch summary

### `config/priors.yaml`

New `replenishment_due:` block in dict form (metadata + priors), inserted after `onsite_funnel_watch`. Mirrors `first_to_second_purchase` structure verbatim:

- `metadata.audience_floor=500`, `mechanism="Send a cadence-timed replenishment reminder..."`, `vertical_applicability=[beauty, supplements, mixed]`, `would_be_measured_by=REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW`, `audience_archetype=cadence_due_repeat_buyer`.
- `priors[0]`: `name=base_rate`, `value=0.0220`, `range_p10=0.0120`, `range_p90=0.0430`, `source_class=observational`, `validation_status=validated_external`, `source_artifact=config/priors_sources/replenishment_due__base_rate__beauty.md`, `effective_n=30`, `applies_to={vertical: beauty}`, `source=klaviyo_h_and_b_2026_perl_cosmetics_case_study`.

NO supplements entry (asymmetric posture per DS architect verdict 2026-05-19).

### `src/measurement_builder.py`

`_PRIOR_ANCHORED["replenishment_due"]` entry: `prior_play_id="bestseller_amplify"` → `"replenishment_due"`; `prior_key="bundle_value"` → `"base_rate"`. Header docstring rewritten to cite D-S6-2.1, the validated_external memo, and the dollar-vs-rate resolution. Dispatch is the only routing surface that needed to change; the prior-anchored play-card construction logic in `build_prior_anchored_play_card` is fully data-driven (no hardcoded prior assumptions).

### `docs/DECISIONS.md`

**Supersede D-S6-2:** status `active` → `superseded`; added a `Superseded by:` line at the bottom citing D-S6-2.1, the category-error rationale (per-customer dollars vs probability rate; double-counting of AOV in `audience × posterior × aov`), and the Gemini Deep Research unlock. Entry body preserved.

**New D-S6-2.1 entry** authored as sibling immediately after D-S6-2: cites the dedicated `replenishment_due.base_rate.beauty` validated_external block, the source_artifact memo path, the dispatch routing in `_PRIOR_ANCHORED`, the dimensional-coherence resolution, the supplements asymmetry rationale, and the pinning tests.

**5 framing demotions** (each retains its values; only framing changed, with new `Why these specific numbers:` / `Revisit trigger:` lines):

| Entry | One-line demotion diff |
|---|---|
| D-S6.5-12 (stage bands) | Added `Why these specific numbers:` noting $500K/$3M/$20M are DTC industry-convention round numbers, not empirically derived; added `Revisit trigger: KI-NEW-E`. |
| D-S6.5-17 (Sephora + iHerb tokens) | "Source-of-truth" → "MVP token vocabulary from two industry-leader catalogs; not exhaustive"; added `Revisit trigger: KI-NEW-D`. |
| D-S6.5-18 (subvertical thresholds 3.0/2.0/1.3) | "DS architect §8.1" → "MVP threshold curve calibrated against synthetic fixtures; recalibrate against real beta confusion matrix"; added `Revisit trigger: KI-NEW-F`. |
| D-S6.5-19 (5 seasonality windows) | "Accept DS architect calendar verbatim" → "conjectural annotations — the DS architect's plausibility judgment, not empirical validation"; added `Revisit trigger: KI-NEW-A`. |
| D-S7.5-3 (pseudo_n cap 30/15/10) | "Founder Q4 locked" → "intentional prior weakness posture; values tunable; the ordering (external > internal > elicited) is the load-bearing claim, not the absolute magnitudes"; added `Revisit trigger: KI-NEW-C`. |

`Last updated:` footer bumped to 2026-05-19 with a one-line audit trail.

### `KNOWN_ISSUES.md`

6 new entries appended under "Architectural limitations parked for DS architect review" (mirror KI-31/KI-32 format; each carries Status `open`, Category line, What, Why it matters, Revisit trigger, Contract):

| KI | Topic | One-line summary |
|---|---|---|
| KI-NEW-A | Seasonality validation | Validate the 5 named seasonality windows against Phase 9 outcome data; remove unsupported windows, add empirically meaningful ones. |
| KI-NEW-B | Audience-floor recalibration | Per-(play × vertical × stage) audience floors are MVP-anchored; recalibrate from real beta outcome data at the lift-per-customer knee. |
| KI-NEW-C | pseudo_n recalibration | Per-stage `pseudo_n_default` magnitudes are tunable, ordering is load-bearing; recalibrate against real beta posterior-shift velocity. |
| KI-NEW-D | Token vocabulary audit | Sephora + iHerb token vocab is MVP; audit against real beta-merchant catalogs once available; add missing tokens, deprecate unused ones. |
| KI-NEW-E | Stage band continuous-uncertainty | Replace the discrete GMV bands + ±25% rule with a continuous uncertainty function once real beta GMV distributions are observed. |
| KI-NEW-F | Subvertical threshold recalibration | 3.0/2.0/1.3 leader-ratio thresholds are MVP-curve; recalibrate against the real beta-merchant confusion matrix. |

Open-count table: Architectural limitations 4 → 10; Total 13 → 19. Last-updated footer bumped to 2026-05-19 with audit-trail line.

### `tests/test_s6_t3_x_prior_rekey.py` (NEW)

6 tests:

1. `replenishment_due.base_rate.beauty` exists with `validation_status: validated_external`.
2. `source_artifact` points to an existing file under `config/priors_sources/`.
3. Exact value pin: `value=0.0220`, `range_p10=0.0120`, `range_p90=0.0430`, `effective_n=30`.
4. `replenishment_due.base_rate` has NO supplements entry (asserts the negative + asserts loader returns `None` for supplements lookup).
5. `_PRIOR_ANCHORED["replenishment_due"]` routes `prior_play_id="replenishment_due"`, `prior_key="base_rate"`.
6. Sanity: `bestseller_amplify.bundle_value.beauty` is preserved post re-key (validated_external retained) — guards against over-zealous cleanup invalidating the S7.5-T2 bsandco promotion.

### Tests updated in-place to track the re-key

`tests/test_s6_t3_replenishment_due_builder.py`:

- T6 (`test_t6_beauty_card_evidence_class_matches_prior_source_class`): `prior_source_class == "expert"` → `"observational"` (the Klaviyo memo derives from observational case-study + benchmark data, not expert elicitation).
- T9 (`test_t9_beauty_posterior_matches_bayesian_blend_cold_start`): `prior_value == 45.0` → `0.022`; `posterior_value == 45.0` → `0.022`. Cold-start posterior collapses to the new validated_external base rate.
- T11 (`test_t11_source_artifact_threaded_for_beauty_validated_external`): artifact path `bestseller_amplify__bundle_value__beauty.md` → `replenishment_due__base_rate__beauty.md`.

`tests/test_s7_5_t1_5_priors_audit.py`:

- Distribution pin: `validated_external == 3` → `== 4` (new replenishment_due.base_rate entry).
- Total-entries pin: `seen == 84` → `== 85`.

---

## 3. N=30 floor verification probe on G-1 supplements (Risk 3 from S6-T3 audit)

One-time probe (not committed; pure read using `parse_unit_coherent("supplements", text)` over `tests/fixtures/synthetic/healthy_supplements_240d_orders.csv`):

**Parser-layer outcome (10 unique SKU titles in fixture):**

- **5 SKU titles return `None` (skipped at parser layer, NOT at cadence layer):**
  - `Collagen Peptides Powder 1lb` (weight-only)
  - `Creatine Monohydrate 500g` (weight-only)
  - `Pre-Workout Energy Complex` (named blend; no container-volume signal)
  - `Whey Protein Powder Vanilla 2lb` (weight-only)
  - `Zinc + Quercetin Immune Formula` (named blend; no container-volume signal)
- This confirms the S6-T2 documented 5/10 supplements coverage flows through the builder honestly. Excluded at parser layer per the audience-builder docstring (`SKUs returning None are excluded entirely`).

**Coherence-key cadence eligibility table (N=30 floor):**

| Coherence key | SKU titles in key | Unique customers | Customers with ≥2 in-class repeats | Cadence median (days) | Clears N=30? |
|---|---|---|---|---|---|
| `count=30` | 1 (Magnesium Glycinate 200mg 60ct → bucketed by count=30) | 459 | 164 | 40.0 | YES |
| `count=60` | 2 (Vitamin D3 + Probiotic 60ct family) | 667 | 406 | 38.0 | YES |
| `count=90` | 1 (Multivitamin Complete 90ct) | 454 | 162 | 38.0 | YES |
| `count=120` | 1 (Omega-3 Fish Oil 120ct) | 455 | 156 | 38.0 | YES |

Note: actual SKU-to-coherence-key bucketing depends on the supplements regex in `parse_unit_coherent`; the per-customer counts above reflect the customer cohort that purchased ≥2 instances within the same coherence bucket, which is the founder Q2 (D-S6-4) gate population.

**Result:** 4/4 coherence-keys clear N=30 cleanly (lowest is 156 customers, ~5× the floor). **N=30 floor stays locked.** No KI-NEW-G filing needed. T3.5 supplements activation will be gated by S7.5-T3 PRIOR_UNVALIDATED refusal (asymmetric posture) — NOT by the per-SKU cadence floor.

---

## 4. Tests / checks run

- `tests/test_s6_t3_x_prior_rekey.py` — 6 passed (new file).
- `tests/test_s6_t3_replenishment_due_builder.py` — 19 passed (3 updated in place to track the re-key).
- `tests/test_s7_5_t1_5_priors_audit.py` — 3 passed (2 updated to bump counts).
- `tests/test_slate_regression_beauty_brand.py` — passed; PINNED_SHA256 byte-identical under flag OFF.
- `tests/test_slate_regression_supplements_brand.py` — passed; PINNED_SHA256 byte-identical under flag OFF.
- `tests/test_golden_diff.py` — passed; M0 trio (small_sm + mid_shopify + micro_coldstart) byte-identical.
- **Full suite: 1422 passed / 14 skipped / 0 failed** (was 1416 / 14 / 0). +6 from new test file; 5 in-place updates (no net change in count from those).

---

## 5. Behavior changes (today, under flag OFF)

**ZERO merchant-facing behavior change.** Flag `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` stays default OFF. The re-key affects only the wiring that becomes runtime-active at T3.5 atomic flip. All 5 pinned fixtures (Beauty + supplements G-1 + 3× M0) are byte-identical to the pre-T3.x state.

**What will change at T3.5 (next ticket-after-next):** Beauty `replenishment_due` lands in Recommended Now against the new validated_external prior; supplements stays in Considered with PRIOR_UNVALIDATED via the standard S7.5-T3 refusal path. The dollar-vs-rate category error from D-S6-2 is gone — `audience × posterior × aov` is now dimensionally coherent (posterior is a probability rate ∈ [0.012, 0.043]).

---

## 6. Artifacts added

- `tests/test_s6_t3_x_prior_rekey.py` — 6 new tests pinning the re-key contract.
- `agent_outputs/code-refactor-engineer-s6-t3_x-summary.md` — this document.

No new modules, no new runtime deps, no new flags, no schema changes (event_version=1 intact; no enum additions; no field reshape).

---

## 7. Remaining risks

- **T3.5 envelope hard-stop pending:** D-S6-3 envelope check (`posterior p50 ∈ [prior.range_p10, prior.range_p90]`) is enforced at T3.5 against `bayesian_blend` numerics on the Beauty fixture. With the new prior at `value=0.022` / `[range_p10=0.012, range_p90=0.043]` and cold-start `observed_n=0`, the posterior collapses to 0.022 — trivially inside the envelope. T3.5 will pin this in `tests/test_s6_t3_5_replenishment_due_repin.py`.
- **Supplements asymmetric reason code remains:** Per DS architect verdict, no supplements stub. Supplements continues to route to Considered with PRIOR_UNVALIDATED. This is the intentional posture; merchant-facing impact lands as part of T3.z (Considered render pass) which closes the PM beta-critical UX gap.
- **5 demoted framings now have explicit revisit triggers:** Each tied to a Phase 9 / post-beta KI. Future agents adjusting any of D-S6.5-12 / -17 / -18 / -19 / D-S7.5-3 must check the corresponding KI-NEW entry first.

---

## 8. Hand-off to T3.y

T3.x establishes the new validated_external prior wiring on a dedicated `replenishment_due.base_rate.beauty` block with dimensionally-coherent rate semantics. This unlocks T3.y's audience-floor sensitivity driver:

- T3.y wires a per-PlayCard sensitivity field showing how the dollar projection moves as the audience floor varies (e.g., what happens at floor=300 vs floor=500 vs floor=750 on the same cohort). The driver requires a prior-anchored card structure where the posterior is a probability rate (not a dollar amount), so the audience × posterior × aov decomposition is interpretable in the chart.
- Under D-S6-2's bundle_value-as-replenishment wiring, the dollar-typed posterior made the sensitivity driver semantically broken; T3.x's re-key makes it actionable. T3.y can now ship without re-tangling the dimensional-coherence question.
- T3.z (Considered render pass) and T3.5 (atomic flip + re-pin) follow per the locked 5-ticket sequence.

---

## 9. Invariants preserved

- D-5 / D-6 / D-8 intact (no Shopify/Klaviyo production integration; no banned ML modules; vertical scope unchanged at `{beauty, supplements, mixed}`).
- B-4 role-uniqueness intact.
- B-5 Berkson invariant intact (re-key does not touch cohort-definition logic).
- S-2..S-6 substrate write paths untouched.
- Schema-additive only within `event_version=1` (no new enum values added in this ticket; T3 already added `REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW`).
- S7.5-T3 validated-vs-heuristic refusal logic UNCHANGED. Supplements asymmetric routing is the SAME mechanism that S6.5-T5 supplements winback uses — no new code path introduced.
- No new runtime deps. No new feature flags. `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` stays default OFF.
- The `bestseller_amplify.bundle_value.beauty` validated_external prior (S7.5-T2 bsandco promotion) is intact and unmoved; only its (mis-)use as a replenishment_due prior was invalidated. The bestseller_amplify play continues to consume it correctly.

---

## 10. Commit list (per 3-commit boundary)

1. **Impl** — `S6-T3.x: re-key replenishment_due prior to dedicated base_rate block (validated_external) + supersede D-S6-2 + 6 post-beta KIs + DECISIONS.md framing demotions` — `config/priors.yaml`, `src/measurement_builder.py`, `docs/DECISIONS.md`, `KNOWN_ISSUES.md`, `tests/test_s6_t3_x_prior_rekey.py`, `tests/test_s6_t3_replenishment_due_builder.py`, `tests/test_s7_5_t1_5_priors_audit.py`.
2. **Memory** — `Document S6-T3.x in repo memory.md`.
3. **Summary** — `agent_outputs/code-refactor-engineer-s6-t3_x-summary.md` (this file).

## Backfill from memory.md (migration trim 2026-05-25)

## S6-T3.x closeout — `replenishment_due` prior re-key + audit-response sprint (2026-05-19)

**Shipped:**

- New `replenishment_due.base_rate.beauty` validated_external block in `config/priors.yaml` (value=0.0220, range=[0.0120, 0.0430], effective_n=30; backed by `config/priors_sources/replenishment_due__base_rate__beauty.md` from commit `011c7cc`). Supplements asymmetric posture intentional (no supplements block; routes to PRIOR_UNVALIDATED Considered via S7.5-T3 refusal).
- `_PRIOR_ANCHORED["replenishment_due"]` dispatch in `src/measurement_builder.py` re-keyed from `bestseller_amplify.bundle_value` → `replenishment_due.base_rate` (resolves the D-S6-2 dollar-vs-rate category error).
- `docs/DECISIONS.md`: D-S6-2 marked superseded; new D-S6-2.1 sibling entry authored. Framing demoted on 5 entries with `Revisit trigger:` lines pointing to KI-NEW-A..F: D-S6.5-12 (stage bands → DTC-convention round numbers), D-S6.5-17 (token vocabulary → MVP, not source-of-truth), D-S6.5-18 (subvertical thresholds → MVP curve, not §8.1-derived), D-S6.5-19 (seasonality windows → conjectural annotations), D-S7.5-3 (pseudo_n cap → tunable magnitudes; ordering is load-bearing).
- `KNOWN_ISSUES.md`: 6 new architectural-limitations KIs filed (KI-NEW-A seasonality validation, KI-NEW-B audience-floor recalibration, KI-NEW-C pseudo_n recalibration, KI-NEW-D token vocabulary audit, KI-NEW-E stage band continuous-uncertainty, KI-NEW-F subvertical threshold recalibration). Architectural-limitations open count 4 → 10; total 13 → 19.
- New `tests/test_s6_t3_x_prior_rekey.py` (6 tests). Updated 3 tests in `tests/test_s6_t3_replenishment_due_builder.py` (T6 source_class expert → observational, T9 prior_value 45.0 → 0.022, T11 source_artifact path) + 2 counts in `tests/test_s7_5_t1_5_priors_audit.py` (validated_external 3 → 4; total entries 84 → 85).

**N=30 G-1 supplements probe (Risk 3 verification):** 4 coherence-keys all clear N=30 cleanly. count=30 (Magnesium 200mg): 164 custs; count=60 (2 SKUs blended: Vitamin D3 + Probiotic): 406 custs; count=90 (Multivitamin Complete): 162 custs; count=120 (Omega-3 Fish Oil): 156 custs. 5/10 SKU titles excluded at parser layer (weight-only `1lb`/`500g`/`2lb`, named blends `Pre-Workout Energy Complex` + `Zinc + Quercetin Immune Formula`) — these never reach the cadence layer, confirming S6-T2 5/10 coverage flows through the builder honestly. No floor lowering needed; N=30 stays locked.

**Load-bearing invariants:**

- D-S6-2 superseded by D-S6-2.1; the `bestseller_amplify.bundle_value.beauty` prior remains intact (only its USE as a replenishment_due prior was invalidated). Future agent MUST NOT delete the bundle_value prior or its memo.
- Supplements `replenishment_due.base_rate` is INTENTIONALLY absent — do not author a stub for code-symmetry (DS architect verdict 2026-05-19); the asymmetric reason code (Beauty validated_external activation vs supplements PRIOR_UNVALIDATED refusal) is informative.
- N=30 floor for per-SKU cadence inference stays locked (D-S6-4); 4/4 G-1 supplements coherence-keys clear it.
- The 5 demoted DECISIONS.md entries retained their values; only the framing changed. New `Revisit trigger:` lines tie each to a specific post-beta KI.

**Caveats / dormant behavior:** All 5 pinned fixtures byte-identical under flag-OFF (Beauty + supplements G-1 + 3× M0). T3.5 owns the atomic flip + re-pin (Beauty replenishment_due lands in Recommended Now against the new validated_external prior; supplements stays in Considered with PRIOR_UNVALIDATED).

**Schema:** unchanged (no enum additions; only YAML + dispatch routing + docs).
**Suite:** 1422 passed (was 1416; +6 from new test file, with 3 existing tests updated in-place to track the re-key).
**Summary:** [agent_outputs/code-refactor-engineer-s6-t3_x-summary.md](agent_outputs/code-refactor-engineer-s6-t3_x-summary.md)
