# BeaconAI — Trust Engine Architecture Plan

**Status:** Draft for founder approval
**Date:** 2026-05-16
**Branch context:** `post-6b-restructured-roadmap` (S5-T3 closeout)
**Authors:** ecommerce-ds-architect (Part I — Design Spec) + implementation-manager (Part II — Phased Plan)
**Mandate:** Reshape the engine into a *trust engine* — a product the merchant returns to every month because every briefing produces plays they would actually execute. Timeline is open; architecture overhaul is allowed where it earns its keep.

> **LOAD-BEARING UPDATE — 2026-05-16:** Part III — Risk Mitigation Addendum (appended below) supersedes specific items in Parts I and II. Read Part III before executing any sprint, especially for: (1) priors validation reframe — `validation_status` field replaces `source_class` as the blend-eligibility driver; (2) V2 cleanup workstream — legacy/V2-era scaffolding flagged for removal alongside features; (3) **engine-only scope — there is no UI in v2; the deliverable is typed `engine_run.json`; all HTML renderer work is out of scope.**
>
> **LOAD-BEARING UPDATE — 2026-05-17:** Part IV — Store Profile Layer (appended below) introduces a new PROFILE step at the front of the pipeline (PROFILE → AUDIENCE → MEASUREMENT → SIZING → DECIDE). It supersedes hardcoded audience floors, materiality floors, primary measurement windows, and seasonality assumptions in Parts I and II. Read Part IV before executing any sprint after S6-T1.5, especially for: (1) per (vertical × sub-vertical × stage) gate calibration; (2) cadence-driven primary/agreement window selection (e.g., supplements/protein gets L60 primary with {L56, L90, L180} agreement, not L28); (3) vertical-specific seasonality calendar that annotates but does NOT multiply revenue ranges; (4) Sprint 6.5 inserts between S6-T1.5 (done) and S6-T2 (held).
>
> **LOAD-BEARING UPDATE — 2026-05-25 (Sprint 8 CLOSE — trust-surface contract live + Play Library wave 1 active):** Sprint 8 closed. All 4 IM-planned tickets + 2 surgical sub-tickets shipped across 12 commits (`77086fd` → `ce648fd`). All 3 S8 additive `PlayCard` fields LIVE in production (`evidence_source` + `sensitivity` + `provenance`); Play Library wave 1 directory structure LIVE with byte-identical contract enforced via spec.yaml ↔ legacy callable identity assertion at engine startup. Suite 1770 → 1882 (+112 tests across the sprint). All 5 pinned fixtures byte-identical from sprint-start to sprint-close (Beauty `f8676c9f…`, Supplements `13a91e6c…`, M0 3 fixtures unchanged). Sprint-close state:
>
> 1. **S8-T0 (`77086fd`):** KI-NEW-K Beauty Beta envelope re-fit — `discount_dependency_hygiene.base_rate.beauty` + `replenishment_due.base_rate.beauty` (founder-acked one-cell scope expansion per DS verdict §6 F1) re-fit from defective Beta(0.66, 29.34) to Beta(1.32, 58.68) at `effective_n=60` with SciPy-authoritative percentiles `(0.0037, 0.0169, 0.0471)`. KI-NEW-K closed.
>
> 2. **S8-T1 + T1.6 + T1.5 trio (`1372feb` + `7df2399` + `98dad72`):** `EvidenceSourceChip` enum (`STORE_MEASURED / STORE_OBSERVED / INDUSTRY_PRIOR / OBSERVATIONAL`) + `PlayCard.evidence_source` field + `ENGINE_V2_TIER_CHIP` flag. T1.6 was a surgical cfg-wiring fix discovered via T1.5 tripwire (DS-consulted, Option B sequencing); added 4 callsite `cfg=cfg` plumbing + structural callsite pin at `tests/test_v2_harness_cfg_gated_fields.py` + DS invariant 16 (harness-level coverage discipline). T1.5 flipped default ON; 3 Beauty Tier-B Recommended cards carry `evidence_source = STORE_OBSERVED`.
>
> 3. **S8-T2 + T2.5 (`fcc87af` + `47eebb2`):** `Sensitivity` typed dataclass (6-key block: 4 scenario revenue ranges + `pseudo_n_used` + `notes`) + `PlayCard.sensitivity` field + `ENGINE_V2_SENSITIVITY` separate flag (per DS Q7 verdict §4 — atomic per-ticket flip discipline, NOT bundled with TIER_CHIP). Helper reuses `bayesian_blend` — no parallel sizing math. T2 caught and fixed a latent bool-coerce bug at `src/utils.py:1041` (string `"false"` was leaking truthy in subprocess harness). T2.5 flipped default ON; sensitivity block live on 3 Beauty Tier-B Recommended cards.
>
> 4. **S8-T3 + T3.5 (`9817216` + `c3eb5e4`):** `Provenance` typed dataclass (validation_status + pseudo_n_used/cap + observed_n + weight_observed/prior + prior_source + notes) + `PlayCard.provenance` field + `ENGINE_V2_EB_BLEND` separate flag. **EB blend math UNCHANGED by S8-T3** — this was contract-formalization, not new math. Production `bayesian_blend` + `PSEUDO_N_BY_STATUS = {VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}` already shipped at S7.5-T3; T3 added the audit-surface payload only. Pinned-fixture byte-identity at flag OFF empirically verified blend math unchanged. T3.5 flipped default ON; provenance block live on 3 Beauty Tier-B Recommended cards with `pseudo_n_used=20, pseudo_n_cap=30` (per-stage profile lowering active per S7.5-T3 `min(status_cap, profile_default)` discipline). **DS invariant 12 cap reached: 3 of 3 S8 additive PlayCard fields landed; no 4th field permitted in S8.**
>
> 5. **S8-T4 + T4.5 (`a9e8bbf` + `ce648fd`):** Play Library wave 1 — `plays/` directory tree with `winback_dormant_cohort` + `replenishment_due` + `discount_dependency_hygiene` subdirectories (each carrying `spec.yaml` + `audience.py` re-export + `builder.py` re-export + `copy.md`). `consult_play_library_if_enabled` at `src/play_registry.py` performs pure identity-assertion (asserts spec.yaml-resolved callables ARE the legacy registry callables, not just equivalent) — guarantees byte-identity by construction. **`ENGINE_V2_PLAY_LIBRARY_WAVE1` default ON post-T4.5 now enforces this invariant on every engine startup** (refuses to start on drift). Wave-1 selection LOCKED per DS Q6 verdict — including dormant `replenishment_due` was load-bearing for stress-testing the dormant-path migration (KI-NEW-G honest-dormancy preserved at both flag states). 11 unmigrated plays stay in legacy locations; wave-2 post-S8.
>
> 6. **All 16 DS invariants preserved across all 12 commits.** Especially: invariant 1 (`PSEUDO_N_BY_STATUS` locked); invariant 2 (HEURISTIC_UNVALIDATED + PLACEHOLDER refusal); invariant 5 (no `Prior.pseudo_N` per-prior override — DS §6 F2 rejected the IM proposal); invariant 9 (reuse `blend` literal, no `blend_empirical_bayes` sibling — DS Q5 closed); invariant 11 (no injection-block touches at `src/main.py:1380-1597` — KI-NEW-L deferred to S13.5); invariant 12 (PlayCard additive surface capped at 3 fields — reached); invariant 13 (Play Library wave-1 acceptance + honest-dormancy); invariant 14 (independent flag matrix — chip × sensitivity × EB blend × Play Library all distinct); invariant 16 (harness-level coverage for every flag-gated producer field — pattern proven via T1.6 + T2 + T3 + T4).
>
> 7. **All three S7.6 architectural invariants preserved** + S7.6 CLI fix surfacing at `src/measurement_builder.py:2252-2270` reachable through all 6 commits. `Measurement.observed_effect/p_internal/n` continue to populate alongside all 3 new S8 fields on every Tier-B Recommended card.
>
> 8. **Engine state in production (end of S8):** every Tier-B Recommended card on Beauty ships with `Measurement.observed_effect / p_internal / n` (S7.6 CLI fix) + `evidence_source = "STORE_OBSERVED"` (S8-T1.5) + `sensitivity = {6-key dict}` (S8-T2.5) + `provenance = {audit object}` (S8-T3.5) + `revenue_range.source = "blend"` (S7.5/S7.6) + `drivers[].blend_provenance` (S7.6). The full trust-surface contract a merchant can audit from headline to feature.
>
> 9. **Out of scope (deferred per DS verdicts, not S8 regression):** KI-NEW-L (5 V2 injection blocks collapse) scheduled S13.5 between S13-T4 and S14-T1 — conditional invariant: "no new Tier-B builders through S13"; KI-NEW-M/N deferred to S14-T3 beta-merchant feedback; KI-NEW-J deferred to S14 with locked resume trigger; KI-NEW-O test-hygiene deferred to separate pass; KI-NEW-G (replenishment_due Commit C activation) remains as real-beta tracker (unaffected by S8). Sprint 9 store-profile-as-learned-artifact + Sprint 10-13 ML AUDIENCE layer (BG/NBD + Gamma-Gamma + survival + CF + RFM + retention curves + month-2 delta surface) are next on the roadmap per IM revised plan.
>
> 10. **Key learnings recorded:** (a) **Empirical-tripwire-over-prediction discipline pays off twice:** the T1.5 dispatch caught the cfg-wiring gap that producer-direct tests had missed, and the T2 harness work caught a latent bool-coerce bug that would have silently leaked at any flag-OFF state. (b) **DS-consult-on-agent-pause workflow validated end-to-end:** the cfg-wiring gap was resolved via DS verdict (`agent_outputs/ecommerce-ds-architect-s8-t1-cfg-wiring-gap-verdict-2026-05-24.md`) Option B path + new DS invariant 16, then refactor-engineer dispatched with DS-locked acceptance criteria. (c) **Atomic per-ticket flag-flip discipline (S7.6 lesson) holds through 4 separate flag flips:** T1.5, T2.5, T3.5, T4.5 each cleanly isolated blast radius. (d) **Identity-assertion design pattern for refactor-only commits:** T4's `consult_play_library_if_enabled` enforces byte-identity by construction (assert callables ARE identity-equal, not equivalent) — template for wave 2+ migrations.
>
> **Beta-readiness statement:** the engine now ships a complete, typed, auditable trust-surface contract on every Tier-B Recommended card. Real-merchant private-beta onboarding (S14) can begin once S10–S13 ML AUDIENCE layer lands. No further engine work required to make the S8 trust-surface contract beta-ready.
>
> **LOAD-BEARING UPDATE — 2026-05-24 (S8-T1 / T1.6 / T1.5 trio — EvidenceSourceChip live in production + cfg-wiring discipline + DS invariant 16):** Three commits land the first S8 trust-surface field end-to-end. Per IM S8 plan Part B S8-T1 + DS verdict 2026-05-24 (cfg-wiring gap, `agent_outputs/ecommerce-ds-architect-s8-t1-cfg-wiring-gap-verdict-2026-05-24.md`, Option B sequencing T1.6 → T1.5).
>
> 1. **`1372feb` (S8-T1, impl):** Typed `EvidenceSourceChip` enum at `src/engine_run.py:295-352` with 4 values (`STORE_MEASURED`, `STORE_OBSERVED`, `INDUSTRY_PRIOR`, `OBSERVATIONAL`); `PlayCard.evidence_source: Optional[EvidenceSourceChip] = None` additive field within `event_version=1`; `ENGINE_V2_TIER_CHIP` flag at `src/utils.py:702` default OFF; producer gate at `src/measurement_builder.py:2428-2430` populates `STORE_OBSERVED` on prior-anchored Tier-B cards when flag is ON. 25 new tests at `tests/test_s8_t1_evidence_source_chip.py`. M0 + Beauty + Supplements byte-identical at default OFF.
>
> 2. **Enum casing decision (founder-confirmed 2026-05-24):** keep `STORE_MEASURED / STORE_OBSERVED / INDUSTRY_PRIOR / OBSERVATIONAL` as shipped (match `ENGINE_OVERVIEW.md` §8 + `ARCHITECTURE_PLAN.md` Part I §A spec-doc identifiers verbatim). The earlier orchestrator brief proposed Tier-label-style `CAUSAL / DIRECTIONAL / PRIOR / OBSERVATIONAL`; refactor agent correctly shipped source-of-truth names per CLAUDE.md "Never assume" + read-the-spec-doc discipline. Founder ack: no rename.
>
> 3. **`7df2399` (S8-T1.6, cfg-wiring fix — surgical correctness):** S8-T1's flag was dead code in production because 4 of 5 callsites of `build_prior_anchored_recommendations` in `src/main.py` (~L1332, L1378, L1426, L1478) did not thread `cfg=cfg` — the producer gate at `src/measurement_builder.py:2428` couldn't reach the flag. The 5th callsite (AOV bundle at L1557) already had `cfg=cfg` from S7.6-T5 observed-effect work. Empirically discovered by T1.5 tripwire 2026-05-24. Per DS verdict §Q1 (Option B) + §Q2 (kwarg-adding is WITHIN invariant 11 exception when default-preserving + non-mutating; no deviation sign-off needed): T1.6 added `cfg=cfg` at the 4 missing callsites. Behavior unchanged at flag default OFF.
>
> 4. **DS invariant 16 (new, 2026-05-24, DS-locked):** Every flag-gated producer field (any `PlayCard` attribute whose population branches on `cfg.get("FLAG", ...)`) MUST be exercised by at least one harness-level test that calls `main.run_action_engine` end-to-end with the flag forced ON and asserts the field populates on at least one rendered card. Producer-direct tests that construct `cfg` manually and call the builder helper do NOT satisfy this invariant. Canonical test home: `tests/test_v2_harness_cfg_gated_fields.py` (created T1.6); T2/T3/S13 each append a parametrize row when they land. **Plus a structural callsite pin** in the same file that regex-walks `src/main.py` and asserts every call to `build_prior_anchored_recommendations` threads `cfg=cfg` — pattern-protects T2 (Sensitivity), T3 (provenance), S13 (ML AUDIENCE) from re-discovering the same bug class. Converts "remember to thread cfg" from tribal knowledge into a CI gate. Suite 1795 → 1798 (+3 tests).
>
> 5. **`98dad72` (S8-T1.5, atomic flag flip):** `ENGINE_V2_TIER_CHIP` default flipped `false` → `true` at `src/utils.py:702`. Env-override path preserved. Empirical tripwire post-flip (without env override): 3 Beauty Tier-B Recommended cards now carry `evidence_source = "STORE_OBSERVED"` in `engine_run.json` — `winback_dormant_cohort` (n=448), `discount_dependency_hygiene` (n=224K), `cohort_journey_first_to_second` (n=603). **All 5 pinned slate sha256 byte-identical across the flip** (Beauty `f8676c9f…`, Supplements `13a91e6c…`, M0 small_sm `40bf24ea…`, mid_shopify `380b2c5d…`, micro_coldstart `2191b251…`) — Beauty HTML pin is byte-identical because the renderer does not surface `evidence_source` (founder ack 2026-05-24: `briefing.html` is debug-only retiring; inspection via `engine_run.json` directly). Supplements + M0 unchanged because no Tier-B Recommended cards fire (supplements aov_bundle vertically excluded + replenishment_due dormant per KI-NEW-G; M0 fixtures too small for Tier-B activation). Suite 1798 → 1798 (no test count change; default flip only).
>
> 6. **Architectural invariants preserved across all three commits:** Single-demote-channel (S7.6 C2 `apply_guardrails_to_injected`); 3-channel `priority_prepend` (S7.6 T5.6); T6 eligibility gate + joint-p<0.10 amendment (S7.6 T6.5); S7.6 CLI fix surfacing at `src/measurement_builder.py:2252-2270` (Measurement.observed_effect/p_internal/n continue to populate alongside new evidence_source); DS invariants 1-15 from prior verdicts + new invariant 16. All `Deviation check: none`.
>
> 7. **S8 sprint progress:** T0 (KI-NEW-K re-fit) + T1 (chip impl) + T1.6 (cfg wiring) + T1.5 (atomic flip) all done. Suite 1770 → 1798. Pending: T2 (Sensitivity dataclass, separate `ENGINE_V2_SENSITIVITY` flag per DS Q7 verdict) + T2.5 atomic flip + T3 (EB blend + provenance) + T3.5 + T4 (Play Library wave 1) + T4.5. The cfg-wiring structural pin from T1.6 now protects T2/T3 from re-discovering the same bug. The DS-locked 30/15/10 pseudo_N table from S8-T0/Q4 verdict consumed by T3 unchanged.
>
> **LOAD-BEARING UPDATE — 2026-05-24 (S8 Q3/Q6/Q7 DS verdict — sprint shape locked + KI-NEW-L/M/N deferral calendar):** Per DS architect verdict 2026-05-24 (`agent_outputs/ecommerce-ds-architect-s8-q3-q6-q7-verdict-2026-05-24.md`, S14-readiness lens, founder-acked) — three locks closing the IM S8 plan's remaining open questions:
>
> 1. **Sprint shape locked at 4 tickets (T0 landed + T1 + T2 + T3 + T4).** KI-NEW-L / M / N all DEFER from S8. **KI-NEW-L (collapse 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597`) scheduled for S13.5** — a dedicated structural-cleanup ticket between S13-T4 atomic flip (which extends all 5 Tier-B audience builders with `ranking_strategy`, giving the eventual collapse a fresh per-builder safety net) and S14-T1 (first private-beta merchant onboarding). Doing the collapse pre-S13 would require two refactor passes; doing it post-S14 would risk re-pin churn against real-merchant baseline. Conditional invariant (DS verdict §5 invariant 15): **"no new Tier-B builders through S13"** — if that breaks, KI-NEW-L escalates and must land before the new builder. KI-NEW-M (`_dedupe_rejections` typed-code policy) + KI-NEW-N (experiment-promotion provenance-preserve) **deferred to S14-driven window**: resume trigger is S14-T3 beta-merchant feedback. Adding a 4th additive PlayCard field in S8 alongside `evidence_source` + `sensitivity` + `provenance` would stress R-S8.1 (additive-only contract). All three deferrals preserve the S14 sequence; no KI count change.
>
> 2. **Play Library wave 1 = `{winback_dormant_cohort, replenishment_due, discount_dependency_hygiene}`** (CONCUR with IM default). The honest-dormancy test is load-bearing: including `replenishment_due` (dormant on Beauty per KI-NEW-G RESOLVED-AS-DOCUMENTED 2026-05-23) is the only wave-1 test case that verifies the migration template handles dormant plays correctly. Substituting `cohort_journey_first_to_second` would leave dormant-path correctness unverified until wave 2 (post-S8) — a structural gap the founder cannot trust without real-beta data. T4.5 acceptance criterion (DS verdict §5 invariant 13): `replenishment_due` produces zero audience on Beauty pinned fixture post-migration (dormancy preserved); `tests/test_s8_t4_play_library_wave1_migration.py` asserts exactly these three `play_id`s have a `plays/<play_id>/spec.yaml` artifact post-T4.5.
>
> 3. **`ENGINE_V2_SENSITIVITY` is a SEPARATE flag** from `ENGINE_V2_TIER_CHIP` (OVERRIDE IM default which proposed bundling). Per DS verdict §4: the S7.6-T7.5 spiral happened because bundled flag flips hid which sub-change caused observed drift; atomic per-ticket flag-flip discipline is **load-bearing DS discipline**, not a stylistic choice. `EvidenceSourceChip` (deterministic enum table lookup) and `Sensitivity` (4-scenario numeric perturbation math) have different blast radii and must be independently observable. Cost of separate: ~1 hour extra refactor-engineer time for one additional re-pin commit (S7.6 ledger empirical). Benefit: blast-radius isolation on the typed surface beta merchants will pattern-match against. Atomic flip discipline: T1.5 flips `ENGINE_V2_TIER_CHIP` only; T2.5 flips `ENGINE_V2_SENSITIVITY` only; each with its own fixture re-pin commit. Test pin (DS verdict §5 invariant 14): env-override matrix at `tests/test_s8_flag_independence.py` asserts all 4 combinations `(chip ∈ {OFF, ON}) × (sensitivity ∈ {OFF, ON})` produce distinct, predictable `engine_run.json` shapes. **"Stop deferring things" misread by IM as "minimize commit count" — founder instruction targets deferred scope, not commits.**
>
> S8 ticket dispatch unblocked. Ready for S8-T1 refactor-engineer dispatch (EvidenceSourceChip enum + PlayCard field, behind `ENGINE_V2_TIER_CHIP` flag default OFF, atomic T1.5 flip + Beauty + Supplements re-pin).
>
> **LOAD-BEARING UPDATE — 2026-05-24 (S8-T0 KI-NEW-K Beauty Beta envelope re-fit + S8 `pseudo_N` lock):** Per DS architect verdict 2026-05-24 (`agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md`) + DS follow-up verdict (`agent_outputs/ecommerce-ds-architect-s8-t0-scipy-percentile-followup-2026-05-24.md`), both reviewed through the S14-readiness lens, commit `77086fd` (S8-T0) re-fit both Beauty `base_rate` entries (`discount_dependency_hygiene.base_rate.beauty` + `replenishment_due.base_rate.beauty`, founder-acked one-cell scope expansion per DS §6 F1) from defective Beta(0.66, 29.34) (J-shape, α<1) to Beta(1.32, 58.68) at `effective_n=60`. SciPy-authoritative percentiles `(p10, p50, p90) = (0.0037, 0.0169, 0.0471)` shipped per DS verdict's "SciPy values are authoritative" instruction; DS analytic ballpark `(0.0040, 0.0182, 0.0443)` superseded. DS follow-up verdict confirmed SciPy values mathematically correct (Beta(α=1.32) is strongly right-skewed, skewness=1.64; DS analytic ballpark under-modeled skew). NO ENGINE BEHAVIOR DEFECT — production dollar delta <0.1% at `observed_n=224K` (`w_obs=0.99987` for `discount_dependency_hygiene`). Beauty pinned slate sha256 `fcd2924b…` → `f8676c9f…` atomic with YAML edit. Supplements + M0 byte-identical. Suite 1770p preserved. All three S7.6 architectural invariants + S7.6 CLI fix surfacing preserved. **`pseudo_N` table LOCKED for S8 (and through S14):** `PSEUDO_N_BY_STATUS = {VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}` per S7.5-T3 production table. The Part I §C draft (`causal=200, observational=50, expert=20, internal_heuristic_unvalidated=5`, lines 325-334 below) is SUPERSEDED — DS verdict rejects it for failing the "small merchant evaluated honestly" criterion (at pseudo_N=200 with cohort n=448, posterior is ~70% prior; founder criterion fails). The phantom IM-plan citation (`expert=1, observational=5, causal=20`) also rejected — fails "survives single-month noise." The S7.5-T3 30/15/10 table is the only candidate that satisfies BOTH criteria + the "no laundering of unvalidated priors" criterion. **`HEURISTIC_UNVALIDATED` + `PLACEHOLDER` priors are refusal at sizing layer**, never blended with low weight — Gate 2 (validation_status, S7.5) is the laundering protection. **`Prior.pseudo_N: Optional[int]` per-prior override field REJECTED** per DS §6 F2 (founder-acked 2026-05-24): proposed in `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md` Part H S8-T3 row; validation_status is the single dial; per-prior numeric overrides re-introduce a backdoor that bypasses per-status cap discipline. If a future prior needs a different weight, that's a validation-status promotion/demotion (auditable in YAML), not a `pseudo_N` numeric field. **KI-NEW-K closed.** **KI-NEW-J defer to S14** with locked resume-trigger text. **KI-NEW-C** (Phase 9 per-stage `pseudo_n_default` recalibration) intentionally untouched; current `min(status_cap, profile_default)` discipline at `src/sizing.py:131-139` means stage-aware tightening drops in as a YAML edit post-beta, not a code change.
>
> **LOAD-BEARING UPDATE — 2026-05-24 (S7.6 CLI receipt-surface fix):** Per DS architect verdict 2026-05-23 (`agent_outputs/ecommerce-ds-architect-s7_6-cli-wiring-gap-verdict-2026-05-23.md`), `Measurement.observed_effect`, `Measurement.p_internal`, and `Measurement.n` on Tier-B prior-anchored Recommended cards landed in `engine_run.json` as `None` despite the observed-effect helpers running and the data being present in `card.drivers[*]` as a `blend_provenance` entry. Engine math was correct; only the canonical typed receipt slot was empty. Commit `d8ede8c` (S7.6-CLI-FIX) populates the three fields from the existing `blend_provenance` stash at `src/measurement_builder.py:2252-2270` (inside `build_prior_anchored_play_card`, guarded by `primary_obs_result is not None and int(primary_obs_result.n) > 0` so cold-start path stays byte-identical). Two-clause tripwire test at `tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_recommended_cards_surface_observed_effect_on_beauty` asserts BOTH (a) `card.drivers` contains a `blend_provenance` entry with `observed_n > 0` AND (b) `card.measurement.observed_effect is not None and card.measurement.n > 0` for the four wired Tier-B plays (`winback_dormant_cohort`, `discount_dependency_hygiene`, `cohort_journey_first_to_second`, `aov_lift_via_threshold_bundle`; `replenishment_due` omitted per DS Option iii 2026-05-23). **Three fields only** — `Measurement.consistency_across_windows` deferred (founder-confirmed 2026-05-24: not in scope, accepted-as-designed; if needed in future, requires its own DS verdict). **`drivers[]` remains the source of truth**; `_blend_provenance_for_card` at `src/decide.py:1524-1535` is byte-identical for the T6 copy ladder. **No top-level `blend_provenance` attribute added to `PlayCard`.** Single-demote-channel + 3-channel `priority_prepend` + T6 eligibility-gate invariants preserved. Beauty pinned slate sha256 `fcd2924b…` and Supplements `13a91e6c…` both unchanged (the pins are on `briefing.html`, which does not render `measurement.observed_effect`). M0 byte-identical. Suite 1769 → 1770 passed (+1 tripwire). Verified empirically on `data/healthy_beauty_240d/runs/d515aa26-…json`: `winback_dormant_cohort` observed_effect=0.057065/n=448/p=0.065477; `discount_dependency_hygiene` observed_effect=0.038045/n=224077/p=0.0; `cohort_journey_first_to_second` observed_effect=0.037297/n=603/p=0.042212; all three `revenue_range.source=blend`. **`briefing.html` does NOT render the new Measurement fields** — founder accepts (2026-05-24): `briefing.html` is debug-only wiring scheduled to be retired when the frontend app activates; `engine_run.json` is the canonical inspection surface for engine correctness during beta-prep. **Deferred to a separate test-hygiene pass:** KI-NEW-O xfail reasoning refresh (founder-confirmed 2026-05-24).
>
> **LOAD-BEARING UPDATE — 2026-05-23 (S7.6 continuation sprint-close):** Sprint 7.6 continuation closed. The 13-commit arc (commits `fc2de84` → `de01df4`) delivered the full observed-effect pipeline for 4 of 5 S6/S7-wired Tier-B plays; `replenishment_due` remains dormant on Beauty per honest-dormancy verdict (DS architect, Option iii, 2026-05-23). Sprint-close state:
>
> - **Activated end-to-end (observed-effect blend live):** `winback_dormant_cohort` (T1.5, Beauty `observed_n=334`, store-dominant), `discount_dependency_hygiene` (T3.5, Beauty `observed_n=148K`, store-dominant), `cohort_journey_first_to_second` (T4.5, Beauty `observed_n=392`, store-dominant, Berkson-protected early-half cohort).
> - **Honestly handled (no synthetic activation):** `replenishment_due` (T2.5 RESOLVED-AS-DOCUMENTED-EXPECTED-BEHAVIOR per DS Option iii, KI-NEW-G updated 2026-05-23); `aov_lift_via_threshold_bundle` (T5.5 flipped ON; joint-fail demotes to Considered with truthful `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` reason via the full T5 → T6 → T5.6 pipeline).
> - **Three architectural invariants now load-bearing in production:**
>   1. **Single-demote-channel** — `apply_guardrails_to_injected` helper at `src/guardrails.py` (commit `6d248fd`, S7.6 close 2026-05-22).
>   2. **`priority_prepend` coverage across all three demote channels** (`cap_exceeded` + `eligibility_rejects` + `prior_unvalidated_rejects` + `window_disagreement_rejects`) for Tier-B prior-anchored cards (commits `bb9fd32` + `8a2d726`, see the T5.6 LOAD-BEARING UPDATE block immediately below).
>   3. **T6 eligibility gate with joint-p<0.10 amendment** for builders that stash `*_band` per-window posteriors (commits `45033dd` + `6d312d3`, DS verdict `agent_outputs/ecommerce-ds-architect-t5_5-joint-gate-verdict-2026-05-23.md`).
> - **References:** 5 DS architect verdicts at `agent_outputs/ecommerce-ds-architect-t{2_5-floor-scope-card,2_5-escalation,t5_5-joint-gate,t6-priority-prepend-gap}-*.md` and 2 IM plans at `agent_outputs/implementation-manager-s7_6-{observed-effect-wiring,continuation}-plan.md`.
> - **Beta-readiness statement:** the engine now satisfies the founder honest-evaluation criterion ("I need all my plays evaluated honestly for each merchant") on Beauty + Supplements synthetic fixtures. Real-merchant validation on a small beta cohort is the natural next step; no further engine work is required to make that step productive.
> - **Out of scope (deferred to S8+):** KI-NEW-L (collapse 5 V2 prior-anchored injection blocks → 1 PRIOR_ANCHORED dispatch), KI-NEW-M (`_dedupe_rejections` typed-code policy), KI-NEW-N (experiment-promotion provenance-preserve), Sprint 9 store-profile-as-learned-artifact, Sprint 10-13 ML scoring layer (`ModelFitStatus` gate).
> - **Key learnings:** (a) **instrumentation-over-prediction** — the T5.5 fixture probe found the joint-gate gap via direct trace, not by code reading; three prior gate-location predictions in S7.6-T7.5 had each been wrong. (b) **DS-architect self-correcting verdicts** — the T5.6 priority_prepend gap was missed twice as a narrow `cap_exceeded` framing before the DS architect restated the wider invariant completely. (c) **CLAUDE.md Subagent Handoff Discipline** has empirically locked subagent behavior to read-first-never-assume.
>
> **LOAD-BEARING UPDATE — 2026-05-23 (S7.6-T5.6 priority_prepend three-channel fix):** Per DS architect verdict 2026-05-23 (`agent_outputs/ecommerce-ds-architect-t6-priority-prepend-gap-verdict-2026-05-23.md`), the 2026-05-22 single-demote-channel invariant was correct but underspecified — only `cap_exceeded` participated in `priority_prepend`. The three sibling reject streams (`eligibility_rejects`, `prior_unvalidated_rejects`, `window_disagreement_rejects`) all flowed into the `pre_existing` slot of `assemble_considered`, exposing Tier-B prior-anchored cards demoted via the T6 eligibility gate (and the analogous Sprint 7.5 / Sprint 6.5 routes) to silent truncation behind a flood of guardrail rejections. The complete restated invariant:
>
> > "Every drop produces a typed RejectedPlay through one demote channel, AND any demoted card whose original PlayCard carried `would_be_measured_by is not None` (Tier-B prior-anchored) MUST be emitted into Considered ahead of `pre_existing` so the `[:MAX_CONSIDERED_RENDERED]=6` truncation at `src/decide.py:assemble_considered` cannot silently drop it — regardless of which channel demoted it. Wired across eligibility_rejects + prior_unvalidated_rejects + window_disagreement_rejects in S7.6-T5.6."
>
> **Implementation shape (Option ii per DS Q4):** `RejectedPlay` gains an additive `would_be_measured_by: Optional[WouldBeMeasuredBy]` field at `src/engine_run.py`. The three routing helpers (`_route_observed_eligibility_holds`, `_route_prior_unvalidated_holds`, `_route_window_disagreement_holds` at `src/decide.py`) populate the field from the originating PlayCard. `assemble_considered` (`src/decide.py:343`) gains a `priority_prepend_rejects: Iterable[RejectedPlay] = ()` kwarg emitted ahead of `pre_existing`. All three assembly seams (PUBLISH `:2418`, ABSTAIN_SOFT `:2370`, ABSTAIN_HARD `:2254`) partition the three channels by `would_be_measured_by is not None` and route the Tier-B subset into the new slot. The original typed `reason_code` (SIGNAL_INCONSISTENT_ACROSS_WINDOWS / PRIOR_UNVALIDATED / WINDOW_DISAGREEMENT) is preserved — Tier-B cards land in Considered with the channel-of-origin reason intact, not a synthetic CAP_EXCEEDED. Parameterized invariant test at `tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_demoted_via_any_channel_survives_truncation` covers all three channels. Flag-OFF behavior preserved (M0 + Beauty + Supplements byte-identical). Unblocks T5.5 — `aov_lift_via_threshold_bundle` observed-effect activation can now land safely because joint-fail demotion preserves the diagnostic reason AND the Tier-B card remains visible in Considered.
>
> **LOAD-BEARING UPDATE — 2026-05-22 (S7.6 close):** Sprint 7.6 closed. Single-demote-channel invariant restored via three structural commits plus the C3 flag flip:
>
> 1. **`bb9fd32` (FIX):** `priority_prepend` in `populate_considered_from_candidates` at `src/decide.py:825-842` ensures S6/S7-wired Tier-B plays (`_PRIOR_ANCHORED` registry at `src/measurement_builder.py:717`) survive the `MAX_CONSIDERED_RENDERED=6` cap-trim. Legacy non-Tier-B plays may be silently truncated per founder decision (CLAUDE.md 2026-05-22).
> 2. **`6d248fd` (C2):** `apply_guardrails_to_injected` helper at `src/guardrails.py` runs full guardrails (inventory + materiality + cannibalization + portfolio-cap + recently-run-when-flag-ON) on cards injected by V2 prior-anchored builders at `src/main.py:1380-1597`. Replaces the T7-FIX materiality-only block. Helper is empirically inert on current synthetic fixtures but load-bearing forward insurance for real-merchant data (DS verdict `afb1fb2f81eebf88f`).
> 3. **C3 (this commit):** T7.5 flag flip — `ENGINE_V2_AOV_THRESHOLD_FROM_DATA` default OFF -> ON. AOV bundle threshold is now data-derived from L90 P60 on Beauty (computed `$71.88`). Supplements is gated via the explicit `vertical_excluded_per_b5_248` seam at `src/audience_builders.py:969-979` per plan §III B-5 lines 248 + 257(c).
>
> **Sprint discipline locked in CLAUDE.md (Subagent Handoff Discipline section, founder-authored 2026-05-22):** every refactor / DS / IM dispatch must read `ARCHITECTURE_PLAN.md`, `memory.md`, `memory_archive.md`, `KNOWN_ISSUES.md`, and the most recent `agent_outputs/*-summary.md` files before code changes. Never assume; instrument and verify when a prediction conflicts with observed behavior. Only follow the path that's decided.
>
> **Tier-B-presence invariant test** at `tests/test_s7_6_c1_priority_prepend_invariant.py` pins the founder criterion in CI: every play_id in `_PRIOR_ANCHORED` that produces an M3 candidate must appear in `engine_run.recommendations` OR `engine_run.considered` on Beauty + Supplements.
>
> **Deferred to S8:** KI-NEW-L (collapse 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` -> 1 PRIOR_ANCHORED dispatch); KI-NEW-M (`_dedupe_rejections` first-wins-vs-last-wins-typed-code policy at `src/decide.py`); KI-NEW-N (experiment-promotion provenance-preserve at `src/decide.py:2080-2087`). Structural cleanup, not provenance-blocking.
>
> **LOAD-BEARING UPDATE — 2026-05-22: Sprint 7.6 — Observed-Effect Wiring sprint + tripwire discipline.**
>
> 1. **S7.6 scope.** S7.6 is the deferred-second-half of S6-T1...S7-T3 builder specs — wires per-store observed-effect `(observed_k, observed_n)` into the EB blend at `src/sizing.py::bayesian_blend` so posteriors shift from prior toward store data as `n` grows. Cold-start (`n=0`) remains prior-dominant; with sufficient `n`, store-dominant. T0 helper + T1.5 winback (Beauty `observed_n=334`, posterior 0.08 → 0.16) prove the contract.
>
> 2. **Sprint discipline (DS-locked 2026-05-22).** Each T*N*.5 atomic flip requires an `observed_n >= 30` Beauty tripwire. If Beauty doesn't clear the builder's upstream gates (e.g., D-S6-4 floors), commit T*N* plumbing and DEFER T*N*.5 until Beauty clears via real beta data or upstream sprint reopen. Do NOT regenerate synthetic fixtures to flatter a specific T*N*.5 — fixtures are plausible-merchant-shape artifacts, not branch-coverage inputs. Branch coverage = isolated unit tests.
>
> 3. **T2.5 precedent (`b0c9980`).** B-2 `replenishment_due` wiring is correct and inert on Beauty under current fixtures (D-S6-4 N≥30 collapses `cohort_n` to 0). T2.5 deferred per DS Path (c); activation atomic when Beauty clears D-S6-4. Pattern applies prospectively to T3 / T4 / T5 if Beauty doesn't clear their respective floors. See `agent_outputs/code-refactor-engineer-s7_6-t2_5-deferred-summary.md` and `KNOWN_ISSUES.md::KI-NEW-G` (2026-05-22 update line).
>
> 4. **Sprint 9 plumbing-deferral clarification.** Sprint 9 = trust-math tooling (sensitivity strip, replay CLI, backtest CLI), NOT merchant-config plumbing for builder thresholds. Earlier builder docstrings referencing "Sprint 9 will plumb this from store profile" were sprint-number drift — store-profile plumbing was always tracked separately and remains tracked separately.
>
> 5. **B-5 supplements scope reaffirmed.** Plan B-5 lines 248 + 257(c) — supplements unconditionally excluded from `aov_lift_via_threshold_bundle` for first ship. S7-T3.5's supplements activation was scope deviation; S7.6-T7 reverts to plan via vertical gate behind `ENGINE_V2_AOV_THRESHOLD_FROM_DATA` flag.

---

## Executive Summary

### The Diagnosis

The engine is **operationally inert by structural design**, not by gate tightness.

- [src/measurement_builder.py:108](src/measurement_builder.py#L108) `_SUPPORTED` has **exactly one** directional builder (`first_to_second_purchase`), and it uses `returning_customer_share` — a *state statistic*, not an intervention-shaped signal. The rationale comment at lines 122–128 explicitly acknowledges this gap.
- Beauty pinned slate: 1 Recommended Now + up to 2 Tier-C Experiments. Supplements: **0 + 0**. Both land in ABSTAIN_SOFT on real fixtures.
- Every revenue-range whisker today renders `suppressed=True` per [src/sizing.py:274](src/sizing.py#L274) (the targeting + non-causal-prior contract).
- The current `EvidenceClass = {measured, directional, targeting, weak}` enum muddles two orthogonal axes (epistemic source vs. store-evidence strength).

The bottleneck is **plays without measurement designs**, not gates set too strict (per [project_engine_anemic_output.md](.claude/projects/-Users-atul-jena-Projects-Personal-beaconai/memory/project_engine_anemic_output.md)).

### The Plan in One Paragraph

Replace the muddled evidence semantics with **four explicit tiers** (A/B/C/D). Ship **five new Tier-B builders** grounded in real beauty/supplements DTC patterns (winback dormant cohort, predicted replenishment, discount-dependency hygiene, KM-survival first-to-second, AOV-lift threshold bundle). Add an **empirical-Bayes blend layer** in sizing so every revenue range becomes a defensible posterior. Ship **Phase 9-minimal** so month 2 produces *"Last month we recommended X. You sent it. Realized $Y. We now believe the lift is Z (was W)"* — the single sentence that turns a one-shot demo into a learning loop. Refactor the scattered play definition into a **Play Library** so the next 20 plays are cheap. Add **trust-math tooling** (sensitivity, replay, backtest) for the skeptical merchant DS. Replace binary ABSTAIN_SOFT with **4 actionable sub-states**. Six sprints, ~11 weeks of focused engineering, every commit ships a runnable engine.

### What This Plan Delivers

- **A typed `engine_run.json` per run** that produces Recommended Now cards when defensible Tier-A or Tier-B signal exists, and an honest sub-typed abstain otherwise. (Part III-3)
- **Defensible posterior revenue ranges** instead of suppressed whiskers — every numeric claim attached to (source, window, n, blend ratio), *only* when underlying priors carry `validation_status ∈ {validated_external, validated_internal, elicited_expert}`. (Part III-1)
- **Cross-month learning loop** — authorize → send → import outcome → calibration shifts → next month's run visibly remembers.
- **Drillable evidence** — every card collapses to audience definition → supporting signal → prior provenance → blend math (as JSON fields, not rendered slots).
- **15 plays in beauty + supplements inventory** grounded in patterns from Glossier, Native, ILIA, Ritual, Athletic Greens, Olipop, Crown Affair, Vuori.
- **Smarter abstain** — five sub-modes (4-state + `SOFT_PRIOR_UNVALIDATED`), each emitted as typed enum on `EngineRun`.
- **Backtest receipts** — run the engine on a brand's 12 months of history sliced as 12 monthly windows; emit CSV of what it would have called and what realized.
- **V2 cleanup workstream** — legacy and Phase-5/6A/6B scaffolding removed in lockstep with feature delivery, not preserved indefinitely. (Part III-2)

### What This Plan Does NOT Do

- **No ML / uplift modeling.** Banned per memory.md D-6 until calibrated outcome history accumulates.
- **No Loop B+ subsegment attribution (KI-29).** Year-2 enhancement. Loop B at the play level is the beachhead.
- **No quasi-experimental causal layer (DiD / RDD / synthetic control).** Premature without ~3 months of Phase 9 outcomes. Revisit post-PMF.
- **No knowledge graph of plays × evidence × verticals.** Premature at current play count.
- **No reversal of G-4** (hardcoded effect sizes stay removed) — contamination of Phase 9 calibration log is not acceptable.
- **No big-bang rewrites.** Every commit keeps the engine runnable end-to-end; `engine_run.json` content stays stable except at explicit, narrow re-pin points.
- **No HTML renderer work.** `briefing.html` is debug-only; the engine's v2 deliverable is `engine_run.json`. All "renderer surface," "chip rendering," "slot layout," "merchant copy template" work flagged in Parts I and II is out of scope. Future UI is a downstream consumer of the JSON contract, not part of v2. (Part III-3)
- **No fabricated priors dressed as math.** Where a prior is `heuristic_unvalidated`, the empirical-Bayes blend is refused and the revenue range is suppressed. The engine produces no dollar projection it cannot defend. (Part III-1)

### The Arc at a Glance

| Sprint | Anchor goal | Beta status |
|---|---|---|
| **S6** | Two Tier-B builders (`winback_dormant_cohort`, `replenishment_due`) + supplements parser (KI-18/KI-27) | Beta-enhancing |
| **S7** | Remaining three Tier-B builders + journey-proxy migration + 4-state abstain | **Beta-blocking** (operational-content baseline) |
| **S8** | Evidence Tier formalization + Empirical-Bayes blend + Play Library refactor wave 1 | **Beta-blocking** (locks trust-surface contract) |
| **S9** | Trust-math tooling (sensitivity, replay, backtest) + evidence-chip renderer surface | Beta-enhancing |
| **S10** | Phase 9-minimal outcome loop (importer + calibration writer + renderer surface) | **Beta-blocking** |
| **S11** | Buffer + private integration with 1–2 hand-picked brands before public beta | Pre-beta validation |

### The Three Beta-Blocking Sprints (in order)

1. **S7** delivers the operational content — without the remaining Tier-B builders, supplements still ships ABSTAIN-only.
2. **S8** locks the trust-surface contract — every PlayCard carries a typed `evidence_source` chip, sensitivity block, and provenance object.
3. **S10** delivers the month-2 learning loop — without it, the engine is a stateless dashboard forever.

S6, S9, S11 enhance but do not block.

### The Two Biggest Risks

1. **Priors validation is unscoped — and the empirical-Bayes blend launders fabricated anchors as rigorous math if not fixed first.** 51 of 143 priors entries carry `internal_heuristic_unvalidated`; 73 entries are labeled `source_class: expert` but were committed without elicitation protocol. Shipping the blend on these priors is worse than today's "we have no measured signal" — it produces calibrated-looking confidence on guesses. Mitigation: insert Sprint 7.5 priors-validation sprint; add `validation_status` field; refuse to blend on `heuristic_unvalidated`; source 1–3 external benchmarks. Full plan in Part III-1.
2. **V2 risks dragging legacy scaffolding it should retire.** Without an explicit cleanup workstream, the codebase ends up running Play Library + `_SUPPORTED` + `play_registry.PLAYS` + `RECOMMENDED_EXPERIMENT_ALLOWLIST` + Phase-5/6A/6B remnants simultaneously. The plan now includes a per-sprint cleanup track (S6-CL1 through S11-CL1, plus M10 bulk-delete). Full plan in Part III-2.

### How to Read This Document

- **Part I — Technical Design Specification** (sections A–I) is the engineering source-of-truth: tiers, builder designs, math, schemas, contracts. Read this when you're about to write code.
- **Part II — Phased Implementation Plan** (sections 1–9) is the executable sequence: per-sprint tickets, schema migrations, fixture re-pin schedule, KI roadmap, beta-launch checklist. Read this when you're about to plan a sprint.

The two parts are designed to be consistent — where Part I specifies *what*, Part II specifies *when*. Where they appear to disagree, Part II's sequencing wins on ordering and Part I's specifications win on contracts.

---


# Part I — Technical Design Specification


# BeaconAI Trust Engine — Technical Design Specification

**Author:** ecommerce-ds-architect
**Date:** 2026-05-16
**Status:** Draft for implementation-manager sequencing
**Branch context:** `post-6b-restructured-roadmap` (S5-T3 closeout)

This spec is the engineering source of truth for the Trust Engine overhaul. It is paired with implementation-manager's phased sequencing; together they form the founder's implementation plan. Where this document specifies math, schema, or invariants, those are the contract. Where it specifies ordering or naming, implementation-manager owns final sequencing — but the artifacts named here are what gets built.

---

## A. The Four Evidence Tiers (formal spec)

The current `EvidenceClass = {measured, directional, targeting, weak}` enum (`/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py`) muddles two orthogonal axes: (1) what is the *epistemic source* of the claim, and (2) how strong is the *store-specific* evidence. The result is that `directional` ends up overloaded — `first_to_second_purchase` ships as `directional` on a *state statistic* (returning_customer_share), while `aov_momentum` would also ship `directional` on an actual *trend signal*. They are not the same epistemic object.

The four tiers below collapse the two axes into one strictly ordered chain and surface the source as a separate typed chip.

### Tier A — Causal / Store-Measured

- **Definition.** Effect estimate is grounded in a within-store comparison that has a credible counterfactual. Either (a) a randomized holdout on a prior Beacon-emitted campaign with `outcome_observed` data through Phase 9, OR (b) a difference-in-differences / regression-discontinuity built on the store's own history with documented identifying assumptions.
- **Identifying claim.** "On this store, the lift attributable to this intervention is X within Y confidence."
- **Required inputs.** ≥1 `outcome_observed` event with non-null `realized_value` AND `treated_audience_size`, OR an explicit causal-design block on the play (`identifying_assumption`, `comparison_group_definition`, `pre_window`, `post_window`).
- **Statistical assumptions.** SUTVA on the audience; no contamination from concurrent Beacon plays on overlapping audiences (the role-uniqueness invariant at decide-layer enforces non-overlap of *recommendations*, but causal estimates must also check against `v_lineage_recent_emissions` for the trailing 28d).
- **Renderer chip.** `STORE_MEASURED` (chip color: green).
- **PlayCard mapping.** `evidence_class=measured`, `evidence_source=STORE_MEASURED`, `measurement.observed_effect != None`, `measurement.p_internal != None`, `measurement.consistency_across_windows >= 2`, `revenue_range.source=STORE_OBSERVED` and `suppressed=False`.
- **M-invariants preserved.** M4a (no fabricated stats), M4b (consistency_across_windows must be ≥2), M6 (sizing uses observed effect directly; no stacked multipliers).
- **Today's reality.** Zero Tier-A plays exist on any fixture. Phase 9 unlocks the first Tier-A cards.

### Tier B — Directional / Store-Observed

- **Definition.** A store-observed metric moved in a direction that justifies an intervention, but the metric is not itself the causal estimate of the intervention's lift. The claim is *correlation that motivates action*, not *measured lift*.
- **Identifying claim.** "On this store, [metric] moved by Δ on the primary window with sign-stable behavior across L56/L90. The intervention is motivated by this trend, but its actual lift is unknown until measured."
- **Required inputs.** Intervention-shaped supporting metric (not a state statistic — see §B for why `returning_customer_share` fails this test), L28 p-value < `PHASE5_DIRECTIONAL_P_MAX=0.05` from `src/measurement_builder.py:79`, sign-agreement count ≥2 across {L28, L56, L90} via `_sign_agreement_count` (`src/measurement_builder.py:228`).
- **Statistical assumptions.** Sign stability across windows is a *consistency* check, NOT a multi-window confidence claim — we do not combine p-values, do not produce a pooled CI, do not cherry-pick min-p.
- **Renderer chip.** `STORE_OBSERVED` (chip color: amber).
- **PlayCard mapping.** `evidence_class=directional`, `evidence_source=STORE_OBSERVED`, `measurement.observed_effect = primary_window_delta` (the *metric* delta, not a forecasted intervention lift), `measurement.p_internal` populated but never rendered, `measurement.consistency_across_windows >= 2`, `revenue_range.suppressed=True` by default UNLESS the play has a causal-class prior in `priors.yaml` (which none do today).
- **M-invariants preserved.** M3 (no fabricated p/q/CI in candidate detection), M6 (targeting-class sizing suppression cascades to directional-with-expert-prior), M9 (p_internal never reaches HTML).
- **Today's reality.** Only `first_to_second_purchase` ships as directional on Beauty, and it uses an invalid supporting signal (see §B-4 below). The 5 Tier-B builders below replace it.

### Tier C — Prior / Industry-Calibrated With Store Context

- **Definition.** The store does not yet have sufficient signal to justify the play on its own data, but the play is well-defined and the *audience definition* is store-specific. The expected behavior is calibrated by an industry-/expert-derived prior in `config/priors.yaml`. This is what today's `evidence_class=targeting` actually is.
- **Identifying claim.** "Stores in this vertical, with this audience archetype, typically convert this play at [prior.range_p10]–[prior.range_p90]. This store has [audience_size] customers in the audience. We have no store-specific evidence of lift yet."
- **Required inputs.** Audience built by a store-CSV-driven builder with audience_size > `audience_floor`. Prior entry in `priors.yaml` keyed by `(play_id, vertical)` exists. NO requirement for any supporting statistical test on the store's data.
- **Statistical assumptions.** Prior transportability — the assumption that industry/expert numbers apply to this store. This is *always weak* and must be surfaced as such.
- **Renderer chip.** `INDUSTRY_PRIOR` (chip color: blue).
- **PlayCard mapping.** `evidence_class=targeting`, `evidence_source=INDUSTRY_PRIOR`, `measurement = None` (load-bearing M4b invariant), `revenue_range.suppressed=True` unless `prior.source_class == "causal"` (no priors are today — sizing.py:277-289 enforces this).
- **M-invariants preserved.** M4b (`evidence_class == "targeting"` ⇒ `measurement is null`), M6 conservative-suppression policy on non-causal priors.
- **Mapping.** Most current `_PRELIM_REASON_MAP` reasons map to Tier-C holds; the experiment-eligible {discount_hygiene, bestseller_amplify} on the A4 allowlist are also Tier-C plays that surface to the Recommended Experiment slot rather than Considered.

### Tier D — Observational Only / No Action Yet

- **Definition.** Engine observed something noteworthy, but it does not yet motivate a specific play. This is the home of Watching, anomaly alerts, and "we saw X, monitoring." There is no executable recommendation; merchant action is undefined.
- **Identifying claim.** "We're tracking [metric / event] because [reason]. We will surface it as a play when [condition]."
- **Required inputs.** A `WatchedSignal` or an `Observation` with `classification != null` (already typed in `engine_run.py`).
- **Statistical assumptions.** None — this is an observation, not a claim.
- **Renderer chip.** `OBSERVATIONAL` (chip color: grey).
- **PlayCard mapping.** Not a PlayCard. Lives on `engine_run.watching` and `engine_run.state_of_store.observations`. Anomaly flags (POST_PROMO_WINDOW) also belong here epistemically, though they surface via `data_quality_flags`.
- **M-invariants preserved.** No effect/p/CI surfaces; no $ headline.

### Tier ordering rules (load-bearing)

- Strict ordering: **C > D > P > O**.
- A Tier-B card cannot outrank a Tier-A card on p50 (the `_CLASS_PRIORITY` map at `decide.py:128` already enforces this at class-priority weights {3,2,1,0}; we extend with A/B/C/D semantics on top, not as a replacement).
- The `EvidenceClass` enum stays as-is for the duration of the migration to avoid a re-pin cascade on all golden fixtures. The new chip lives in a separate typed field `PlayCard.evidence_source: EvidenceSourceChip` (additive within `event_version=1`).

---

## B. The Five Tier-B Builders (full design)

Tier-B is where the engine earns its monthly briefing identity. Today, exactly one Tier-B builder exists (`build_directional_play_card` in `src/measurement_builder.py`) and it has a fundamental shape problem: the supporting metric `returning_customer_share` is a *state statistic* (what fraction of the customer base has ordered before), not an *intervention-shaped* signal (a metric that would itself move under the proposed intervention's mechanism). A first-to-second-purchase nudge does not move "share of returning customers" — it moves "fraction of one-time buyers who place a second order within window N." Mixing the two means the trigger condition is structurally decoupled from the play's mechanism.

All five builders below carry the same shape contract:

```python
# pseudo-signature for every Tier-B builder
def build_<name>_card(
    candidate: Candidate,
    orders_df: pd.DataFrame,
    aligned: dict,
    priors: PriorsRegistry,
    *,
    primary_window: str = "L28",
    cfg: EngineConfig,
) -> Optional[PlayCard]:
    """Returns a PlayCard with evidence_class=DIRECTIONAL or None.

    Pre-conditions: candidate cleared M3 audience gate.
    Post-conditions: same as build_directional_play_card.
    """
```

Each is registered in a new module-level dict `_TIER_B_BUILDERS: Dict[play_id, builder]` replacing the single-entry `_SUPPORTED` dict at `src/measurement_builder.py:108`.

### B-1. `winback_dormant_cohort`

- **Brief.** Identify customers who bought once or more in the past, last ordered between 60–180 days ago, and re-engagement is justified by the store's *observed* lapse-recovery rate.
- **Vertical.** beauty, supplements, mixed.
- **Audience cohort.** From `orders_df`: customers whose `max(order_date) ∈ [now-180d, now-60d]` AND who have `total_orders >= 1` AND who are NOT in the audience of `first_to_second_purchase` (overlap exclusion). Definition version follows D-1: `audience_definition_version=1` on first ship.
- **Supporting metric.** `lapse_recovery_rate_l60` — the fraction of customers in the dormant cohort who placed an order in the most recent L28 window divided by the fraction in the prior L28 window. This IS intervention-shaped: the play sends a winback campaign, and "did dormant customers come back in the most recent window" is the metric the campaign moves.
- **Statistical method.** Two-proportion z-test on (recovery rate in L28 recent) vs (recovery rate in L28 prior, defined by anchoring 28 days earlier in the same dormant cohort). p < 0.05 threshold. Welch's t-test if cell counts are too small for normal approximation (n < 30 in either cell).
- **Multi-window consistency.** Re-compute the same proportion on L56 (recent vs L56 prior) and L90 (recent vs L90 prior). Sign-agreement ≥2 across {L28, L56, L90} required.
- **Prior dependencies.** `winback_21_45.base_rate`, `winback_21_45.incrementality`, `winback_21_45.orders_per_customer` (all already in `config/priors.yaml:86-140`).
- **Data assumptions.** min_n=200 customers in dormant cohort; min_history_days=120 to define a 60–180d lapse window meaningfully.
- **Honest claim.** "Dormant-cohort recovery rate moved up [X.X%] on L28 vs the prior 28-day window with consistent direction across L56/L90. A structured winback to this cohort is justified by the recovery trend." NO claim of campaign lift; revenue_range suppressed unless prior is causal.
- **Integration.** Add `"winback_dormant_cohort"` to `_TIER_B_BUILDERS`. The existing `winback_21_45` candidate from `audience_builders.py` is the audience source; rename emit to `winback_dormant_cohort` (per Play Library refactor §E) OR keep id stable and reroute the builder. Decide layer needs no change — class-priority ranking already handles directional cards.
- **Edge cases.** (a) Dormant cohort is empty → return None, route candidate to Considered with `AUDIENCE_TOO_SMALL`. (b) Recovery rate is mechanically zero in both recent and prior windows (store with no churn-recovery activity) → return None with `NO_MEASURED_SIGNAL`. (c) Recovery rate dropped (negative sign) → still emit the card with `direction="down"` in why_now — a *worsening* lapse-recovery rate is ALSO an intervention motivator. The renderer copy on negative deltas should be "deterioration is the reason to act," not "improvement justifies action."
- **Fixture strategy.** Synthetic healthy fixture: 1200 customers, 30% in 60–180d band, recovery rate 6.5% → 9.0% across L56→L28. Edge fixture: same audience but recovery rate flat at 7% across all windows → builder returns None, candidate flows to Considered.

### B-2. `replenishment_due`

- **Brief.** Customers who bought a replenishable SKU and are statistically due for a reorder based on the *store's own* observed median reorder interval for that SKU class.
- **Vertical.** beauty (all categories with parseable size), supplements (count/serving-based SKUs).
- **Audience cohort.** Customers whose last purchase of a replenishable SKU was within `[median_reorder_gap × 0.8, median_reorder_gap × 1.2]` days ago, where `median_reorder_gap` is computed per-SKU-class from the orders_df. Excludes anyone already in `winback_dormant_cohort` (overlap exclusion).
- **Supporting metric.** `due_cohort_reorder_rate_l28` — fraction of customers in the "due now" window who placed a same-class reorder in the L28 vs L28-prior. Intervention-shaped: a replenishment reminder moves this exact metric.
- **Statistical method.** Two-proportion z-test on (due-cohort reorder rate L28) vs (due-cohort reorder rate L28 prior). p < 0.05. Optional fallback: if the cohort is too thin per window, pool L56 with reduced effect threshold (no min-p cherry-pick — pre-declare which window is primary based on the SKU class's median gap).
- **Multi-window consistency.** Same proportion across L28/L56/L90. Sign-agreement ≥2.
- **Prior dependencies.** `empty_bottle.base_rate`, `empty_bottle.incrementality` (`priors.yaml:431-448`). Audience floor: `empty_bottle.metadata.audience_floor` (to be added; today empty_bottle uses list form).
- **Data assumptions.** Requires `replenishment_parser.py` to return non-null size/count for SKUs (G-2 supplements gap — KI-18/KI-27 — is the live blocker here; supplements need a `count|serving-per-container` parser before this builder works for supplements). min_n=100 customers in due cohort; min_history_days=180 (need to observe at least one full reorder cycle).
- **Honest claim.** "Customers due for a reorder are converting at [X.X%] in the most recent 28 days vs [Y.Y%] in the prior 28 days. A targeted replenishment reminder is justified by the elevated due-cohort conversion."
- **Integration.** Replaces today's `empty_bottle` legacy emitter on the Tier-B path. Legacy emitter stays in the engine but no longer surfaces as a Recommended Now card — it flows through to Considered with a "see replenishment_due card" cross-reference.
- **Edge cases.** (a) `replenishment_parser` returns null for vertical=supplements until G-3 parser ships → builder returns None on supplements, candidate routes to Considered with `DATA_QUALITY_FLAG: replenishment_parser_unavailable`. (b) median_reorder_gap is undefined (insufficient repeat history) → None, `COLD_START_INSUFFICIENT_DATA`. (c) due cohort overlaps with `winback_dormant_cohort` cohort >30% (Jaccard) → demote with `AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY`.
- **Fixture strategy.** Healthy beauty fixture exists today (Beauty pinned `dcb45cee...`). Healthy supplements fixture (G-1 `01f5feff84...`) needs the parser before it can exercise this builder. Edge fixture: store with one repeat buyer per SKU class → median_reorder_gap defined but cohort < 100 → None.

### B-3. `discount_dependency_hygiene`

- **Brief.** A meaningful slice of revenue is coming through orders with discounts above a vertical-tuned threshold. Suppressing discounts to a defined cohort for a defined window is an intervention motivated by *the store's own discount mix shift*, not a generic best-practice claim.
- **Vertical.** beauty, supplements, mixed.
- **Audience cohort.** Customers whose median order discount % over the last 90 days exceeds the vertical's `heavy_discount_threshold` (beauty=15%, supplements=10%, mixed=12%; to be added to `priors.yaml` under `discount_hygiene.metadata.heavy_discount_threshold_by_vertical`), AND who placed ≥2 orders.
- **Supporting metric.** `heavy_discount_share_of_revenue_l28` — fraction of L28 revenue from this cohort divided by total L28 revenue, compared to the L28-prior fraction. Intervention-shaped: a discount-suppression test moves this exact ratio.
- **Statistical method.** Two-proportion z-test on the revenue fractions. p < 0.05. The metric uses revenue-weighting (not order-counting) because the play's economic claim is margin, which scales with revenue.
- **Multi-window consistency.** Three-window check. Sign-agreement ≥2.
- **Prior dependencies.** `discount_hygiene.margin_recovery_rate` (`priors.yaml:250-272`). Note: this prior is currently `source_class: observational` but with `internal_csv_observation_v1` — it is one of the few priors that has any observational grounding.
- **Data assumptions.** min_n=150 in heavy-discount cohort; min_history_days=120; orders_df must carry `discount_amount` (Shopify CSV does — verified).
- **Honest claim.** "Heavy-discount share of revenue is [X%] of L28 revenue, [Δ pp] vs prior. A defined-window discount suppression on this cohort is justified by the elevated share. Margin recovery range based on observational priors."
- **Integration.** Add `"discount_hygiene"` to `_TIER_B_BUILDERS`. Today `discount_hygiene` is in the A4 Recommended Experiment allowlist (`decide.py:118`) — it gets PROMOTED from Experiment to Recommended Now when this builder fires. Allowlist behavior: if the Tier-B builder returns a card, that card outranks the Experiment slot; if it returns None, the play continues to flow through the experiment selector unchanged.
- **Edge cases.** (a) Store has no discounting whatsoever (discount_amount column all-zero) → None, route to Considered with `NO_MEASURED_SIGNAL`. (b) Cohort is the entire customer base (everyone discounts heavily) → cap audience at 40% of customer base via M5 audience-overlap guardrail. (c) `OPP_DISCOUNT_DEPENDENCE` is currently the directional pretty-name for this — preserve `data-play-id="discount_hygiene"` for log stability.
- **Fixture strategy.** Healthy fixture: 30% of revenue from heavy-discount cohort, trending up 4pp across L56→L28. Edge fixture: 10% of revenue, flat → None.

### B-4. `cohort_journey_first_to_second` (replaces `first_to_second_purchase` proxy)

- **Brief.** The intervention-shaped replacement for today's broken `first_to_second_purchase` directional. Audience is one-time buyers within an actionable recency band; supporting metric is the *observed* first-to-second conversion rate of comparable historical cohorts at this store, not a state statistic.
- **Vertical.** beauty, supplements, mixed.
- **Audience cohort.** Customers whose `total_orders == 1` AND `last_order_date ∈ [now-60d, now-7d]` (the 7d lower bound prevents sending to brand-new buyers who haven't had a chance to make a second purchase yet; the 60d upper bound matches the active first-to-second decision window). `audience_definition_version=2` (this is a redefinition of the existing v1 audience — D-1 mandates a version bump).
- **Supporting metric.** `cohort_first_to_second_rate` — defined on historical cohorts of one-time buyers who reached the same recency band: of those who were 7–60 days post-first-order in the L56 window, what fraction placed a second order within 30 days? Compare to the same calculation on the L56-prior window. This is intervention-shaped because the play (a first-to-second nudge) moves exactly this rate.
- **Statistical method.** Two-proportion z-test on cohort-defined rates. p < 0.05. Critical: cohort denominators are defined on EARLY-half-of-window first-purchase dates, never on late-half (the resolved journey_p_zero / Berkson confound — see `project_journey_p_zero.md` memory note; the B-5 invariant test in `tests/test_berkson_invariant.py` already pins this rule on `calculate_journey_stats_single_window`).
- **Multi-window consistency.** L28/L56/L90 sign agreement ≥2.
- **Prior dependencies.** `first_to_second_purchase.base_rate`, `first_to_second_purchase.second_purchase_lift` (`priors.yaml:803-836`).
- **Data assumptions.** min_n=150 one-time buyers in audience; min_history_days=120 (need at least one full cohort observation window).
- **Honest claim.** "First-to-second conversion in comparable cohorts moved from [Y%] to [X%] over the past 56 days. A structured first-to-second nudge is justified by the observed cohort lift."
- **Integration.** REPLACES the `first_to_second_purchase` entry in `_SUPPORTED`. The play_id stays stable (`first_to_second_purchase`) — only the builder logic changes. D-1 mandates `audience_definition_version` bumps to 2 on this swap; old lineages remain readable in substrate.
- **Edge cases.** (a) Supplements: typical reorder cadence is 28–45d, which straddles the 7–60d window — most supplements first-time buyers will still be inside the band but the L28 supporting metric will be noisy. The S5-T2 typed `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` reason code REMAINS — when this builder returns None on supplements due to thin cohort signal, route to Considered with that typed code (preserves the KI-20 contract). (b) Store with <30 days of first-purchase history → COLD_START, no card.
- **Fixture strategy.** Healthy beauty: 200 one-time buyers in band, cohort rate 18% → 22% across L56→L28, builder fires. Healthy supplements: cohort rate is flat at 8% (cadence-bound) → None, S5-T2 path fires the typed abstain. Edge: cohort rate dropped from 25%→18% → fires with `direction="down"`, "deterioration is the reason to act."

### B-5. `aov_lift_via_threshold_bundle`

- **Brief.** Customers' AOV distribution shows a bimodal shape with a meaningful right-tail mode above a vertical-tuned threshold. A bundle/threshold offer designed to nudge median customers above the threshold is justified by the *observed* AOV distribution shape, not a generic upsell heuristic.
- **Vertical.** beauty, mixed. (Supplements typically has narrower AOV distributions; the builder defers on supplements to avoid false-positive bundle plays.)
- **Audience cohort.** Customers whose median order value over the last 90 days is in `[bundle_threshold * 0.7, bundle_threshold * 0.95]`, i.e., they are *just below* the threshold and a small AOV nudge would clear them. `bundle_threshold` is a percentile-anchored value — the 60th percentile of L90 order AOV, computed on the store's own data, NOT a hardcoded number.
- **Supporting metric.** `near_threshold_aov_share_l28` — fraction of L28 orders falling in the `[0.7×T, 0.95×T]` band, compared to L28-prior. Intervention-shaped: a threshold-bundle nudge moves this fraction up (orders cross the threshold) AND moves median AOV in the audience up.
- **Statistical method.** Welch's t-test on audience-level AOV (L28 recent vs prior) AND a two-proportion z-test on the threshold-band share. BOTH must reach p<0.10 (looser bar on the joint test because we're requiring two signals to agree). Welch's because audience-level AOV is approximately normal under CLT for n>30.
- **Multi-window consistency.** L28/L56/L90 sign agreement ≥2 on AOV delta.
- **Prior dependencies.** `aov_momentum.base_rate`, `aov_momentum.growth_acceleration` (`priors.yaml:528-590`). Note: `aov_momentum` priors are pure expert — revenue_range suppression cascades.
- **Data assumptions.** min_n=200 customers in near-threshold band; min_history_days=120; AOV distribution must have a defined 60th percentile (i.e., audience size > some floor).
- **Honest claim.** "Median AOV in the just-below-threshold cohort moved from [$X] to [$Y] on L28, with the near-threshold band growing [Δ pp]. A threshold-bundle offer is justified by the observed distribution shift."
- **Integration.** New play_id `aov_lift_via_threshold_bundle`. The existing `aov_momentum` legacy play remains for backward compat but stops surfacing on Tier-B (it becomes a Tier-C fallback only). Register in `play_registry.py` per Play Library refactor §E.
- **Edge cases.** (a) Bundle threshold computation requires sufficient AOV variance — store with near-uniform order values returns None. (b) Joint test failure modes: if AOV moved but share didn't (or vice versa), demote to Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS`. (c) Supplements: builder returns None on `vertical == "supplements"` unconditionally for the first ship; revisit when subscription-AOV dynamics are better understood.
- **Fixture strategy.** Healthy beauty: 250 customers in band, AOV $58→$64, near-threshold share 22%→28%. Edge: AOV moved but threshold-share didn't → None with inconsistent-signal reason.

---

## C. Empirical-Bayes Blend Layer (full math spec)

### Why this exists

Today, `src/sizing.py:248-303` does one of two things: (a) use observed effect alone (collapses range to a point estimate), or (b) use prior range alone (ignores observed evidence entirely). Both are extreme. The correct operation is to *blend* the prior with the observed effect, weighted by `pseudo_N` from the prior source class.

The blend formula formalizes "trust the prior more when we have less store-specific data, trust the data more when we have more."

### Posterior mean formula

For a Beta-Bernoulli conversion-style prior with mean $\mu_0$ (the prior point estimate) and concentration parameter $\kappa_0 = $ `pseudo_N`, and observed data $(k, n)$ where $k$ is observed successes and $n$ is observed trials:

$$\mu_{\text{posterior}} = \frac{\kappa_0 \mu_0 + k}{\kappa_0 + n}$$

Equivalently, the blend weight on observed data is $w_{\text{obs}} = n / (n + \kappa_0)$, and the blend weight on prior is $w_{\text{prior}} = \kappa_0 / (n + \kappa_0)$. When $n \to \infty$, posterior → observed. When $n \to 0$, posterior → prior. The same form applies to continuous outcomes (Normal-Normal conjugate) with `pseudo_N` interpreted as equivalent sample size.

For the revenue range, the analogous blend on the p10/p50/p90 triple uses interval blending: the posterior interval shrinks toward the data interval at rate $w_{\text{obs}}$.

### `pseudo_N` policy by source_class

| source_class | pseudo_N | Rationale |
|---|---|---|
| `causal` | 200 | A causal estimate (RCT or strong quasi-experimental) is worth ~200 observational trials before the store's own data dominates. Today no priors are causal; this is forward-looking. |
| `observational` | 50 | Internal CSV-derived priors with no randomization. Worth ~50 trials. |
| `expert` | 20 | SME judgment / industry benchmark. Modest weight; the store's own evidence overtakes quickly. |
| `internal_heuristic_unvalidated` | 5 | Engineering intuition with no external citation (the source-tagged majority of supplements priors per G-3). Near-zero weight; effectively present only to prevent zero-data divide-by-zero. |

`pseudo_N` is a NEW field on `PriorEntry` (additive to `priors_loader.py::PriorEntry`). When `source` field on a prior names `internal_heuristic_unvalidated`, default to `pseudo_N=5` regardless of declared `source_class`.

### Helper signature

New module `src/empirical_bayes.py`:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class BlendResult:
    posterior_mean: float
    posterior_p10: float
    posterior_p90: float
    weight_observed: float    # n / (n + pseudo_N)
    weight_prior: float       # pseudo_N / (n + pseudo_N)
    observed_n: int
    pseudo_N: int

def bayesian_blend(
    prior_mean: float,
    prior_p10: float,
    prior_p90: float,
    observed_effect: Optional[float],
    observed_n: Optional[int],
    pseudo_N: int,
) -> BlendResult:
    """Empirical-Bayes blend of a numeric prior with optional observed data.

    Returns:
        BlendResult. When observed_effect is None or observed_n <= 0,
        returns the prior unchanged (weight_observed=0.0).
    Raises:
        Never. On any input pathology (negative N, NaN), falls back to
        prior unchanged and logs the fallback in the BlendResult.
    """
```

### Integration in sizing.py

Replace the current bifurcated logic at `src/sizing.py:248-303` with:

```python
# After determining (prior, observed_effect, observed_n):
blend = bayesian_blend(
    prior_mean=prior.value,
    prior_p10=prior.range_p10,
    prior_p90=prior.range_p90,
    observed_effect=inputs.observed_effect,
    observed_n=inputs.observed_n,
    pseudo_N=prior.pseudo_N,  # new field
)
p_action_p10, p_action_p50, p_action_p90 = blend.posterior_p10, blend.posterior_mean, blend.posterior_p90
```

The conservative-suppression policy (Tier-C with non-causal prior → suppressed) STAYS — empirical-Bayes does not unlock dollar projections on Tier-C plays. The blend only affects sizing on Tier-A and Tier-B cards where `observed_effect` is non-null.

### Blend ratio surfacing on PlayCard

New typed field on `Measurement`:

```python
@dataclass(frozen=True)
class BlendProvenance:
    weight_observed: float
    weight_prior: float
    observed_n: int
    pseudo_N: int
    prior_source_class: str
    prior_source: str  # e.g. "internal_csv_observation_v1"

# In Measurement:
blend_provenance: Optional[BlendProvenance] = None
```

This is additive within `event_version=1`. The Swarm renderer surfaces it as "Built on N store observations + industry prior (weight: 60/40 store)" on the EVIDENCE band of Recommended Now cards.

### Migration plan from today's priors

1. Add `pseudo_N: Optional[int] = None` to `PriorEntry` (defaulting from source_class when null).
2. Update `priors_loader.py` to apply defaults: causal→200, observational→50, expert→20, with `internal_heuristic_unvalidated` source override→5.
3. Add `pseudo_N` field to `config/priors.yaml` schema (optional; defaults via loader).
4. No re-pin of fixtures required — sizing on today's plays is dominated by `cold_start=True` or `targeting + non-causal` suppression, both of which preempt blending.

### Failure modes

- **Empty observed data.** `bayesian_blend` returns prior unchanged. No issue.
- **Weak prior (large p90/p10 spread).** Posterior inherits the wide range; honest reflection of uncertainty.
- **Single-store data.** `observed_n` is the n underlying the supporting metric; for a Tier-B card with 1200 audience members, `n=1200` quickly dominates `pseudo_N=20`. This is correct behavior.
- **Hostile observed value (e.g., observed_effect = 100% on a tiny n).** `pseudo_N=20` still anchors when n is small; blend gracefully degrades to prior.

---

## D. Phase 9-Minimal Outcome Loop (full spec)

### Goal

The single missing piece between "engine recommends" and "engine learns" is an outcome-importer + calibration-writer. Phase 9-minimal is ~500 LOC: importer CLI, schema, calibration module, renderer surface. NO subsegment attribution (that is Loop B+ per KI-29, deferred).

### `outcome_observed` event schema

Frozen contract at `event_version=1`. Documented in `docs/memory_substrate.md` per S-6:

```python
@dataclass(frozen=True)
class OutcomeObservedPayload:
    # Identity
    lineage_id: str
    campaign_id: str
    recommendation_event_id: str
    campaign_sent_event_id: str

    # Outcome
    outcome_status: str  # "OBSERVED" | "ZERO_OUTCOME" | "NO_DATA"
    realized_value: Optional[float]   # dollars, MUST be None if status != OBSERVED
    realized_orders: Optional[int]
    treated_audience_size: int
    converters: Optional[int]
    measurement_window_days: int      # typically 7, 14, or 30

    # Provenance
    outcome_window_start: str  # ISO-8601
    outcome_window_end: str    # ISO-8601
    attribution_method: str    # "klaviyo_attributed" | "shopify_first_touch" | "manual_ascription"
    notes: Optional[str]

    # Schema version
    event_version: int = 1
```

Refusal rules (enforced by importer):
- `outcome_status="OBSERVED"` with `realized_value is None` → REJECT.
- `outcome_status="ZERO_OUTCOME"` with non-None `realized_value` → REJECT.
- `lineage_id` not present in substrate → REJECT.
- `campaign_sent_event_id` not present OR not on the same lineage → REJECT.
- Duplicate `(lineage_id, campaign_id, outcome_window_end)` → REJECT.
- `measurement_window_days not in {7, 14, 30, 60}` → REJECT (closed enum for v1).

### `calibration_updated` event schema

Frozen contract at `event_version=1`. Already documented in S-5; this spec pins the v1 payload shape:

```python
@dataclass(frozen=True)
class CalibrationUpdatedPayload:
    # Identity
    lineage_id: Optional[str]   # null for store-wide calibrations
    triggering_event_ids: List[str]  # outcome_observed events that drove the update
    play_id: str
    audience_archetype: Optional[str]

    # Update payload (additive sections; absent sections preserved per KI-4)
    prior_overrides: Optional[Dict[str, Dict[str, float]]]  # {"base_rate": {"value": X, "p10": Y, "p90": Z}}
    evidence_thresholds: Optional[Dict[str, float]]         # {"p_max": 0.05, "min_consistency": 2}
    materiality_overrides: Optional[Dict[str, float]]       # {"floor_dollars": 1500}

    # Provenance
    update_method: str   # "running_mean" | "shrinkage_blend" | "manual"
    n_outcomes_used: int
    update_reason: str   # e.g. "K=3 outcomes observed; promote pseudo_N from expert to causal"

    event_version: int = 1
```

### `tools/import_outcome_observed.py` CLI design

```
python -m tools.import_outcome_observed \
    --store-id <store_id> \
    --inbox-dir data/<store_id>/inbox/outcomes/ \
    [--dry-run]
```

- **Single writer.** Per single-writer grep test, this CLI is the ONLY writer of `outcome_observed` events into substrate. `src/` files are FORBIDDEN from emitting this event type. The allowlist entry must be added to `tests/test_single_writer_per_event_type.py` in the same PR.
- **Validation.** Strict v1 — every refusal rule above is enforced. On any rejection, the file stays in inbox, importer prints the failing field and exits non-zero.
- **Calibration triggering.** After successful import, the CLI calls `src.calibration.outcome.maybe_emit_calibration_update(lineage_id)`. If the trigger fires (e.g., K=3 outcomes accumulated), a `calibration_updated` event is appended in the SAME transaction or in a follow-up transaction with referential integrity to the outcome events.
- **Idempotency.** Re-running over an inbox with already-imported files: refuses each as duplicate, exits zero (no-op).

### `src/calibration/outcome.py` module shape

```python
# src/calibration/outcome.py — NEW module

def maybe_emit_calibration_update(
    lineage_id: str,
    *,
    store_id: str,
    k_threshold: int = 3,
) -> Optional[CalibrationUpdatedPayload]:
    """When >= k_threshold outcome_observed events exist on the lineage,
    compute a shrinkage-blend update against the play's prior and emit
    a calibration_updated event.

    Returns the emitted payload, or None if K not yet reached / update
    not justified.
    """

def compute_running_calibration(
    outcomes: List[OutcomeObservedPayload],
    prior: PriorEntry,
) -> Dict[str, Any]:
    """Reduce N outcomes against a prior via Bayesian blend; return the
    payload sections for a calibration_updated event."""
```

This module is the SINGLE WRITER of `calibration_updated` events (grep allowlist).

### Single-writer claim

| Event type | Writer(s) | Readers |
|---|---|---|
| `recommendation_emitted` | `src/main.py::_emit_substrate_events` | `tools/import_campaign_sent.py`, `tools/import_outcome_observed.py`, `src/memory/views.py` |
| `recommendation_considered` | `src/main.py::_emit_substrate_events` | `src/memory/views.py` |
| `campaign_sent` | `tools/import_campaign_sent.py` | `src/memory/views.py`, `tools/import_outcome_observed.py` |
| `outcome_observed` | `tools/import_outcome_observed.py` (NEW) | `src/calibration/outcome.py`, `src/memory/views.py` |
| `calibration_updated` | `src/calibration/outcome.py` (NEW) | `src/calibration_stub.py`, `src/memory/views.py` |

### Renderer surface

The Swarm renderer reads a new typed `OutcomeRetrospective` block in `engine_run.json` (populated when the engine reads `v_calibration_state` for this store and finds prior calibration updates):

```python
@dataclass(frozen=True)
class OutcomeRetrospective:
    last_recommended_play_id: str
    last_recommended_date: str   # ISO
    was_sent: bool
    realized_value: Optional[float]
    predicted_p50: Optional[float]
    calibration_action: str   # "tightened_prior" | "widened_prior" | "no_change"
    delta_summary: str        # merchant-readable
```

Surface copy template: "Last month we recommended [play_name]. You sent it on [date]. Realized [$realized] vs predicted [p50]. We now believe [calibration_summary]." The Swarm owns formatting; engine emits typed fields.

### Schema-additive guarantee

All new fields above are additive within `event_version=1`. `OutcomeRetrospective` lives on `engine_run.json` and is `Optional` — older Swarm consumers ignore the field cleanly.

### Operator-discipline KIs this slice unblocks

- **KI-1** (positive-projection test for `outcome_observed` refusal rules) → Phase 9-minimal first PR includes the test.
- **KI-3** (`store_id` plumbing) → already resolved S5-T1; Phase 9-minimal exercises the substrate read path end-to-end with non-empty data for the first time.
- **KI-5** (`v_lineage_recent_emissions` wall-clock semantics) → Phase 9-minimal calibration trigger needs `gate_recently_run` semantics correct; this is the surface where the wall-clock vs deterministic anchor choice gets pinned.

---

## E. Play Library Refactor (full spec)

### Motivation

Today, a play's definition is scattered across:
- `src/play_registry.py` (PlayDef: audience_builder_ref, prior_keys)
- `src/audience_builders.py` (the builder callable)
- `config/priors.yaml` (priors + metadata block)
- `src/measurement_builder.py::_SUPPORTED` (Tier-B supporting metric for one play)
- `src/decide.py::RECOMMENDED_EXPERIMENT_ALLOWLIST` (eligibility)
- `src/action_engine.py::_TARGETING_RECLASSIFY` (structural targeting plays)

Adding a new play requires touching 5–7 files. The Play Library refactor collapses these into a single per-play directory.

### Target directory structure

```
plays/
  __init__.py              # exposes get_play_definition(play_id)
  _registry.py             # imports + registers every play directory
  winback_dormant_cohort/
    __init__.py
    audience.py            # build_audience(orders_df, cfg) -> AudienceCandidate
    measurement.py         # build_directional_card(...) (Tier-B builder)
    priors.yaml            # this play's priors (per-vertical)
    mechanism.py           # static copy strings
    eligibility.py         # is_experiment_eligible(), is_tier_b_eligible()
    post_launch.py         # how outcome_observed is computed for this play
  replenishment_due/
    ...
  ... (one dir per play)
```

### File template per play

Each play directory exports:

```python
# plays/<play_id>/__init__.py
from .audience import build_audience, AUDIENCE_DEFINITION_VERSION
from .measurement import build_directional_card
from .mechanism import MECHANISM_COPY, RECOMMENDATION_TEXT, WHY_NOW_TEMPLATE
from .eligibility import (
    is_tier_b_eligible,        # bool — does this play support Tier-B today?
    is_experiment_eligible,    # bool — A4 allowlist replacement
    is_targeting_structural,   # bool — _TARGETING_RECLASSIFY replacement
    audience_floor_by_vertical,
    vertical_applicability,
)
from .post_launch import compute_realized_outcome  # used by Phase 9 importer

PLAY_DEFINITION = PlayDefinition(...)  # the canonical object
```

The `priors.yaml` file in each play directory is a per-play subset of the global priors — at load time, a build step composes them into the global `config/priors.yaml` for backward compatibility, OR the loader is rewritten to scan `plays/*/priors.yaml`. Recommend the latter for cleaner ownership.

### Migration order

The migration is per-play. Order:

1. **`first_to_second_purchase`** (highest leverage — this play has the broken supporting signal AND is the only Tier-B today). Migration drops the old `_SUPPORTED` entry and brings up the new `cohort_journey_first_to_second` builder.
2. **`winback_21_45`** (rename to `winback_dormant_cohort` per Tier-B §B-1). Aliasing: keep `play_id="winback_21_45"` for lineage stability; just bump `audience_definition_version` to 2.
3. **`empty_bottle`** → `replenishment_due` (only after G-3 supplements parser unblocks).
4. **`discount_hygiene`** (becomes both Tier-B builder AND retains experiment eligibility as fallback).
5. **`aov_momentum`** → `aov_lift_via_threshold_bundle`.
6. Remaining Tier-C plays (`bestseller_amplify`, `subscription_nudge`, `routine_builder`, `category_expansion`, `journey_optimization`, `retention_mastery`, `frequency_accelerator`) migrate one-at-a-time with no behavior change.

### Collapse of existing structures

| Today's location | Plays Library destination |
|---|---|
| `src/play_registry.py::PlayDef` | `plays/<play_id>/__init__.py::PLAY_DEFINITION` |
| `src/audience_builders.py::<builder>` | `plays/<play_id>/audience.py::build_audience` |
| `config/priors.yaml::plays.<play_id>` | `plays/<play_id>/priors.yaml` |
| `src/measurement_builder.py::_SUPPORTED` | `plays/<play_id>/measurement.py::build_directional_card` |
| `src/decide.py::RECOMMENDED_EXPERIMENT_ALLOWLIST` | aggregated via `is_experiment_eligible()` at startup |
| `src/action_engine.py::_TARGETING_RECLASSIFY` | aggregated via `is_targeting_structural()` at startup |
| `src/decide.py::WouldBeMeasuredBy` enum value | `plays/<play_id>/post_launch.py::WOULD_BE_MEASURED_BY` |

### Backward compatibility during migration

- The legacy paths (priors.yaml, audience_builders.py, etc.) stay in place. The `_registry.py` collapses both legacy and new-style sources into a unified registry at startup. A play is "migrated" when it has a `plays/<play_id>/` directory; the legacy entries for that play are then ignored by the loader (with a single-source-of-truth assertion at startup).
- Beauty pinned fixture (`dcb45cee...`) and supplements pinned fixture (`01f5feff84...`) MUST stay byte-identical through migration. Any behavior-changing migration step requires a fixture re-pin in the same commit per the existing post-S3 discipline.
- Single-writer grep test (`tests/test_single_writer_per_event_type.py`) needs allowlist updates as event-emitting code moves; this is mechanical.

---

## F. Trust-Math Tooling (3 sub-tools)

These tools turn the engine from a black-box recommender into something a merchant (or a skeptical PM) can interrogate.

### F-1. Sensitivity Strip

**Goal.** Per Recommended Now / Recommended Experiment card, show how the headline number moves under five plausible perturbations.

**The 5 scalars.**

| Scalar | Computation | Reason |
|---|---|---|
| `aov_minus_15pct` | Re-run sizing with `aov` reduced by 15% | "What if AOV is overstated?" |
| `audience_minus_30pct` | Re-run sizing with `audience_size * 0.7` | "What if our audience definition is too generous?" |
| `prior_p10` | Re-run sizing with `prior.value = prior.range_p10` (low end of conversion prior) | "What if the prior is over-optimistic?" |
| `observed_effect_minus_50pct` | Re-run sizing with `observed_effect * 0.5` (Tier-B only) | "What if half of the observed signal is noise?" |
| `pseudo_N_doubled` | Re-run blend with `pseudo_N * 2` (Tier-B with blend only) | "What if we trust the prior more?" |

**Renderer surface.** New typed field on `PlayCard`:

```python
@dataclass(frozen=True)
class SensitivityStrip:
    base_p50: float
    aov_minus_15pct: float
    audience_minus_30pct: float
    prior_p10: Optional[float]
    observed_effect_minus_50pct: Optional[float]
    pseudo_N_doubled: Optional[float]
```

Swarm renders as five small bars next to the headline. The collapse of all five toward zero is a visual cue that the headline is fragile; the cluster staying near the headline is a cue it's robust.

### F-2. Replay CLI (`tools/replay_at_date.py`)

**Goal.** "If we'd run Beacon on store X on date D, what would we have recommended?" — for backtesting, demos, and rebuilding lineages after schema migrations.

**Inputs.**
- `--store-id <id>` (required)
- `--at-date <YYYY-MM-DD>` (required) — the effective "today" for the replay
- `--snapshot-source orders.csv | substrate` — where to read order history from

**Outputs.**
- `replays/<store_id>/<run_id>_<at_date>.json` — the full `engine_run.json` as it would have been produced
- A diff against any historical run on the same store, if one exists in substrate.

**Algorithm.**
1. Read orders CSV (or `v_lineage_timeline` for substrate replays).
2. Filter to orders with `Created at <= at_date`.
3. Run the engine entry point with the filtered data and a forced "today" override.
4. Write the resulting `engine_run.json` to `replays/`.
5. Compute snapshot sha256 and append to a `replay_log` event (NOT a substrate event — replays are NOT first-class events; they are tooling output).

**Determinism.** Replays use `seed_all(seed=0)` per G-7. Two replays of the same `(store_id, at_date)` must be byte-identical.

### F-3. Backtest CLI (`tools/backtest.py`)

**Goal.** Run the engine on a sliding window of historical dates and produce a calibration plot of (predicted p50) vs (realized value 28d later).

**Inputs.**
- `--store-id <id>`
- `--start-date <YYYY-MM-DD>`
- `--end-date <YYYY-MM-DD>`
- `--cadence weekly | monthly` (default: monthly)

**Outputs.**
- `backtests/<store_id>/<run_id>_<start>_<end>.csv` with columns: `replay_date, play_id, predicted_p10, predicted_p50, predicted_p90, realized_value_28d_actual, sent_or_simulated`.
- `backtests/<store_id>/<run_id>_<start>_<end>_calibration.html` — calibration scatter plot.

**Algorithm.**
1. For each replay_date in `[start, end]` stepping by cadence:
   a. Run `replay_at_date` for that date.
   b. Extract the Recommended Now / Recommended Experiment cards and their predicted p10/p50/p90.
   c. For each predicted card, look forward 28 days in the orders_df and compute the *realized* value of the metric the card claimed (e.g., for `cohort_journey_first_to_second`, count actual second-orders from the audience in the 28d window). This is *simulated realization* — it does NOT require an actual Klaviyo send; it just measures what would have happened on the customer base.
2. Aggregate predicted vs realized into a calibration record.

**Time-slicing constraint.** Replays must never look forward in time within the engine's own logic — only the backtest harness looks forward to compute realization. This is enforced by the `--at-date` cutoff inside replay.

---

## G. Smarter Abstain (state machine)

### Today

Three states: `PUBLISH`, `ABSTAIN_SOFT`, `ABSTAIN_HARD`. `ABSTAIN_SOFT` is a single bucket that conflates "we don't have measurement infrastructure yet" with "the audience doesn't clear materiality" with "we're inside an anomalous window."

### Four typed sub-modes

```python
class AbstainMode(str, Enum):
    HARD = "hard"
    SOFT_BELOW_FLOOR = "soft_below_floor"
    SOFT_AWAITING_MEASUREMENT = "soft_awaiting_measurement"
    SOFT_CADENCE_OUTSIDE_WINDOW = "soft_cadence_outside_window"
    SOFT_DATA_GAP = "soft_data_gap"
```

Additive within `event_version=1` on the `Abstain` typed object in `engine_run.py`.

| Mode | Trigger | Merchant copy template |
|---|---|---|
| `HARD` | Any HARD `data_quality_flags` (BFCM_OVERLAP, REFUND_STORM, TEST_ORDER_ANOMALY, INSUFFICIENT_CLEAN_HISTORY, VERTICAL_NOT_SUPPORTED) | "We're holding all recommendations this month because [flag]. Re-run next month or contact support." |
| `SOFT_BELOW_FLOOR` | All measured/directional candidates have `revenue_range.p50 < materiality_floor` | "Your top opportunities exist but their projected impact is below the floor we recommend for a store your size ([$floor]). Considered list shows what's close." |
| `SOFT_AWAITING_MEASUREMENT` | Zero measured/directional cards built; only Tier-C targeting candidates available | "We have promising audiences but no measured evidence on your store yet. Send any of the Considered plays and we'll learn from the outcome." |
| `SOFT_CADENCE_OUTSIDE_WINDOW` | `METRIC_INCOHERENT_FOR_CADENCE` flag is set (the supplements 28d-window-on-45d-cadence case) | "Your customers reorder on a cadence longer than our primary analysis window. Watching metrics may be unreliable; treat them as directional." |
| `SOFT_DATA_GAP` | Specific advisory flag set (e.g., parser unavailable for vertical) but not HARD | "We're missing a parser/data path for [specifics]. Standard plays still appear; specialty plays are deferred." |

### Reason-code fan-out extension

Extend `_S3_FANOUT_REASON_MAP` in `src/decide.py`:

```python
_S3_FANOUT_REASON_MAP_V2 = {
    **_S3_FANOUT_REASON_MAP,
    "below_floor": ReasonCode.MATERIALITY_BELOW_FLOOR,
    "awaiting_measurement": ReasonCode.NO_MEASURED_SIGNAL,
    "cadence_outside_window": ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW,
    "data_gap": ReasonCode.DATA_QUALITY_FLAG,
}
```

The S5-T2 `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` reason code remains the live example; the smarter-abstain layer generalizes the pattern.

### State transitions

The state machine is mostly write-once-per-run, but two transitions matter:

- **`SOFT_BELOW_FLOOR` → `PUBLISH`** when an empirical-Bayes blend (§C) crosses the materiality floor that the prior alone did not. This is the desired emergent behavior from Phase 9: as outcome data accumulates, blend posteriors shrink toward truth, and plays that were at the floor become decisively above/below.
- **`SOFT_AWAITING_MEASUREMENT` → `PUBLISH`** when a Tier-B builder fires for the first time (e.g., after enough first-purchase history accumulates for `cohort_journey_first_to_second`).

Transitions are NOT in-run; they happen across monthly runs. The engine logs them via the `calibration_updated` event.

---

## H. The Trust Surface — every typed field that needs to exist

### Schema additions (all additive within `event_version=1`)

**On `PlayCard`:**

```python
evidence_source: Optional[EvidenceSourceChip]  # STORE_MEASURED | STORE_OBSERVED | INDUSTRY_PRIOR | OBSERVATIONAL
signal_kind: Optional[str]                     # intervention_shaped | state_statistic | trend_observation
sensitivity_strip: Optional[SensitivityStrip]  # §F-1
provenance: Optional[ProvenanceBlock]          # see below
```

**On `Measurement`:**

```python
blend_provenance: Optional[BlendProvenance]    # §C
window_anchor_dates: Optional[Dict[str, str]]  # {"L28_recent_start": "...", "L28_recent_end": "..."}
```

**On `EngineRun`:**

```python
outcome_retrospective: Optional[OutcomeRetrospective]  # §D
abstain_mode: Optional[AbstainMode]                    # §G
```

**New `ProvenanceBlock`:**

```python
@dataclass(frozen=True)
class ProvenanceBlock:
    audience_definition_id: str
    audience_definition_version: int
    audience_builder_module: str        # e.g., "plays.cohort_journey_first_to_second.audience"
    supporting_metric_module: Optional[str]  # e.g., "plays.cohort_journey_first_to_second.measurement"
    priors_source_paths: List[str]      # e.g., ["plays/cohort_journey_first_to_second/priors.yaml"]
    engine_run_seed: int                # G-7 determinism seed
```

This block is the "show your work" surface — Swarm renders it as a small "Built by" disclosure under each card.

### Swarm consumer mapping

| Field | Swarm surface |
|---|---|
| `evidence_source` | Tier chip (color-coded) at top-right of card |
| `signal_kind` | Hover tooltip on the tier chip |
| `sensitivity_strip` | 5 small bars in the EVIDENCE band |
| `blend_provenance` | "Built on N store observations + industry prior" text |
| `provenance` | "Show your work" disclosure (collapsed by default) |
| `outcome_retrospective` | State-of-store ribbon top of briefing |
| `abstain_mode` | Replaces the dominant-gate-keyed ABSTAIN_SOFT copy |

### Stop-Coding Line discipline

Per the 6B Stop-Coding Line: engine emits typed fields, renderer renders them. Every new field above is a typed slot; no HTML/copy work in `src/`. The Swarm reads `engine_run.json` and owns formatting. The `briefing.html` engine path stays in place for the local CSV workflow but is treated as a fallback renderer, not the primary surface.

---

## I. Risk Register (engineering risks)

### R-1. Tier-B builder calibration: Type I (false fires) and Type II (false silence) errors

- **Risk.** Each new Tier-B builder applies a p<0.05 threshold on observed-data metrics. Across 5 builders × 4 windows = up to 20 statistical decisions per run. Without FDR correction or pre-registration, false-positive rate compounds.
- **Likelihood.** Medium-high. The current single-builder path is rarely-firing so this hasn't been a problem; with 5 builders it will become one.
- **Mitigation.** (a) Use a single primary-window decision per builder, not min-p across windows. (b) Require sign-agreement ≥2 (already in place — `PHASE5_DIRECTIONAL_MIN_CONSISTENCY=2`). (c) Tighten p<0.05 to p<0.02 for any builder that fires more than ~30% of monthly runs on the same store (operator discipline; tracked via substrate). (d) Backtest CLI (§F-3) becomes the calibration tool — if predicted-vs-realized scatter shows systematic bias on a builder, retune.
- **Observability hook.** Backtest CLI output. Substrate `v_lineage_recent_emissions` tracks per-builder fire rate.

### R-2. Priors validation gap (`internal_heuristic_unvalidated` dominates supplements)

- **Risk.** Per G-3, the majority of supplements priors are `source: internal_heuristic_unvalidated`. The new `pseudo_N=5` policy for these effectively means the prior contributes near-zero to blended posteriors — which is the right behavior, but it also means supplements stores will see ABSTAIN_SOFT until Tier-B builders mature.
- **Likelihood.** High — by design, this is the trade-off.
- **Mitigation.** (a) Supplements onboarding copy explicitly sets the expectation: "Your first month will be smaller until we observe outcomes." (b) Phase 9-minimal accelerates by turning observed outcomes into calibration events quickly (K=3 threshold is intentionally low for v1; raise to K=5 once we have evidence outcomes aren't noise-dominated). (c) Document `internal_heuristic_unvalidated` priors as the explicit research backlog — each one is a candidate for an internal CSV observational study.
- **Observability hook.** Per-store `abstain_mode` rate over time, surfaced in the calibration retrospective.

### R-3. Phase 9 operator-discipline dependence

- **Risk.** The entire calibration loop hinges on operators (or the founder) actually importing `campaign_sent` and `outcome_observed` events. There is no API; D-5 mandates manual import. A merchant who never imports outcomes never benefits from calibration.
- **Likelihood.** High in v1 — this is the core friction of the local CSV workflow.
- **Mitigation.** (a) Importer CLI is dead simple, one command per inbox. (b) `OutcomeRetrospective` surface gives merchants visible reward for importing outcomes ("we recalibrated based on your data"). (c) Long-term, AWS migration lands the Klaviyo pollers and outcome-importer becomes automated.
- **Observability hook.** Per-store count of `outcome_observed` events; merchants with zero outcomes after N months get a different briefing variant.

### R-4. Schema-additive discipline erosion

- **Risk.** Every spec section above adds typed fields. The discipline is "additive within `event_version=1`." Two failure modes: (a) someone changes a field type silently (re-typing requires `event_version=2`); (b) the Swarm starts depending on an `Optional` field being non-null, breaking when older runs lack it.
- **Likelihood.** Medium. The single-writer grep test catches new event types but not field-shape changes on existing typed payloads.
- **Mitigation.** (a) Add a typed-payload schema-shape test that pickles a v1 payload from a frozen fixture and unpickles it under the latest schema — any field re-typing fails. (b) The Swarm contract must document which fields are required vs optional; renderers must gracefully degrade on null Optionals. (c) Schema additions land in PRs that update `docs/memory_substrate.md` in the same commit (already established discipline per S-6).
- **Observability hook.** The pickle-shape regression test runs in CI.

### R-5. Fixture re-pinning cascade

- **Risk.** Each Tier-B builder migration, each priors expansion, each schema addition risks a Beauty / supplements / mid_shopify / small_sm / micro_coldstart fixture re-pin. Cascading re-pins make code review hard and accidentally normalize "fixtures keep changing."
- **Likelihood.** Medium. The discipline so far has been "intentional re-pin in the same commit as the behavior change, with sha256 documented." S-3, S5-T2, S5-T3 all followed this.
- **Mitigation.** (a) ALL Tier-B builder additions ship behind a feature flag (`ENGINE_TIER_B_<name>=false` default) until calibrated on synthetic fixtures. (b) M0 byte-identity is the load-bearing test; ANY M0 fixture change is a flag-flip decision, not a code-change side-effect. (c) When re-pinning, the commit message must enumerate the byte-diff (e.g., "one Considered card changes reason code" per S-3 closeout pattern).
- **Observability hook.** CI fails on M0 fixture sha256 drift unless the test file's pinned sha256 is updated in the same PR.

### R-6 (additional). The `signal_kind` enum surface — getting it wrong locks us in

- **Risk.** Calling `returning_customer_share` a `state_statistic` (correct, per my critique) means existing fixtures need that classification on the existing directional card. If we get the taxonomy wrong now, we're locked into an awkward enum at v1 schema freeze.
- **Likelihood.** Medium.
- **Mitigation.** Keep the enum tiny in v1: `{intervention_shaped, state_statistic, trend_observation}`. Audit each Tier-B builder against the enum before ship. Reject any builder whose supporting metric is `state_statistic` — that's the original sin we're fixing.
- **Observability hook.** A pre-commit test in the `plays/` directory: `assert PLAY_DEFINITION.supporting_signal.signal_kind in {INTERVENTION_SHAPED, TREND_OBSERVATION}` — `STATE_STATISTIC` is *forbidden* as a Tier-B builder's signal kind.

---

## Relevant file paths (all absolute)

- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py` — current Tier-B builder, line 108 `_SUPPORTED` is the single-builder dict to be replaced
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` — line 118 `RECOMMENDED_EXPERIMENT_ALLOWLIST`, line 128 `_CLASS_PRIORITY`, line 139 `_HARD_DQ_FLAGS`
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py` — line 248-303 is where the Bayesian blend integrates; line 277-289 is the targeting-non-causal suppression to preserve
- `/Users/atul.jena/Projects/Personal/beaconai/src/cadence_coherence.py` — S5-T3 pattern to extend for §G `SOFT_CADENCE_OUTSIDE_WINDOW`
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml` — receives `pseudo_N` field migration, plus per-vertical Tier-B builder priors
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — typed PlayCard/Measurement/EngineRun additions per §H
- `/Users/atul.jena/Projects/Personal/beaconai/src/memory/events.py` — `OutcomeObservedPayload`, `CalibrationUpdatedPayload` per §D
- `/Users/atul.jena/Projects/Personal/beaconai/src/memory/views.py` — read-views consumed by `OutcomeRetrospective`
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md` — KI-1, KI-2, KI-3, KI-4, KI-5 (Phase 9 entry conditions), KI-29 (subsegment Loop B+, NOT in this spec — deferred)
- `/Users/atul.jena/Projects/Personal/beaconai/memory.md` — Stop-Coding Line (post-6B), D-1 audience_definition_version policy, D-2 retention, D-5 manual import only, D-6 ML ban, D-8 vertical hard-lock


---

# Part II — Phased Implementation Plan


# BeaconAI Trust Engine — Phased Implementation Plan (Sprints 6–11)

**Author:** Implementation Manager
**Date:** 2026-05-16
**Branch context:** `post-6b-restructured-roadmap`; baseline 1190p / 14s / 1f (pre-existing wall-clock flake) at S5-T3 closeout.
**Companion docs:** `/Users/atul.jena/Projects/Personal/beaconai/memory.md`, `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md`, `/Users/atul.jena/Projects/Personal/beaconai/ENGINE.md`, `/Users/atul.jena/Projects/Personal/beaconai/CLAUDE.md`.

---

## 1. Executive sequencing summary

### Scope being sequenced

The DS architect spec is producing the full design surface for eight workstreams (4 tiers, 5 Tier-B builders, Empirical-Bayes blend, Phase 9-minimal outcome loop, Play Library refactor, trust-math tooling, 4-state abstain, PlayCard contract additions). This plan sequences them into six sprints. The DS architect handles *what* each one looks like internally; this plan handles *when* each lands and what invariant it must satisfy on the day it lands.

### Total scope and beta gating

| Sprint | Anchor goal | Duration | Beta status |
|---|---|---|---|
| **S6** | Two highest-leverage Tier-B builders + supplements parser unit-coherence (KI-18 / KI-27) | 2 wks | Beta-enhancing (not blocking) |
| **S7** | Remaining three Tier-B builders + journey-proxy migration + 4-state abstain | 2.5 wks | **Beta-blocking** (delivers the operational-content baseline) |
| **S8** | Evidence Tier formalization + Empirical-Bayes blend + Play Library refactor wave 1 | 2 wks | **Beta-blocking** (locks trust-surface contract) |
| **S9** | Trust-math tooling (sensitivity, replay, backtest CLIs) + evidence-chip renderer surface | 1.5 wks | Beta-enhancing |
| **S10** | Phase 9-minimal outcome loop (importer + calibration writer + "last month's outcome" surface) | 2 wks | **Beta-blocking** (turns "trust engine" framing into a closed loop) |
| **S11** | Private beta integration buffer with 1–2 founder-selected merchants | 1.5 wks | **Beta gate** |

**Total:** ~11.5 weeks of engineering wall-clock from today (2026-05-16) to public-beta-ready, plus the founder's discretion on launch timing post-S11.

### Minimum slice that earns "trust engine" framing

If the founder pushes for an earlier beta after S7 (against this plan's recommendation), the **minimum honest "trust engine" framing requires**:

1. **S6 + S7 in full** (5 Tier-B builders + 4-state abstain) — without these the engine remains structurally inert per the prior PM/DS finding.
2. **S8 evidence-tier formalization** *minus* Play Library refactor — the A/B/C/D chip and the typed `evidence_source` field on PlayCard must reach the briefing; the directory restructure can wait.
3. **S10 outcome loop in its read-only form** (importer + receipts surface, *no* calibration writer yet) — Beacon must be able to *show* last month's outcome on the briefing, even if the math doesn't yet shape future runs.

S9 trust-math tooling and the Empirical-Bayes blend layer are *founder-internal* during private beta — they don't need to be merchant-facing on Day 1. They become public-beta polish.

### Order rationale

1. **Builders first, then framing.** Tier-B builders (S6–S7) expand the set of plays the engine *can* recommend. Until that's done, every framing/tier/tooling change just dresses the same structurally-inert output. KI-21 (supplements zero experiments), KI-23 (drop-outs), KI-24 (subscription_nudge generic reason) all collapse to "we need more builders that emit Tier-B evidence."
2. **Smarter abstain follows builders.** The 4-state abstain machine (S7) only meaningfully differentiates outputs *after* there are more candidate plays to differentiate over. Today's binary HARD/SOFT abstain is the right primitive for the small-candidate-set engine; expanding to 4 states pre-S6 would be a renderer change without a payoff.
3. **Trust-surface contract before tooling.** The PlayCard contract additions (evidence_source chip, signal_kind, sensitivity, provenance — S8) are *what* the trust-math tooling (S9) measures. Pin the contract first, then build the tooling that exercises it. Reverse order = re-pin fixtures twice.
4. **Outcome loop last among engine-internal sprints.** Phase 9-minimal (S10) consumes the *output* of S6–S8. It depends on (a) Tier-B builders firing enough to have outcomes to observe, (b) evidence-tier formalization so the calibration writer knows which prior to overwrite, and (c) the EB blend layer so calibrated values have somewhere to land. Doing S10 before S8 produces a calibration consumer with no upstream contract.
5. **Beta integration buffer is non-negotiable.** S11 exists because every prior sprint shipped against synthetic fixtures. The first real merchant CSVs will surface KI-30-class UX issues, KI-7-class schema friction with Klaviyo provider strings, and KI-29-class subsegment-attribution conversations. Skipping S11 to ship public beta on the S10 close commit risks a launch-day rollback.

### What this plan does NOT do

- It does NOT propose a Phase 9 spec (DS architect owns it). It schedules a *Phase 9-minimal* outcome importer + calibration writer (KI-1 / KI-2 / KI-4 gates).
- It does NOT propose a subsegment-attribution implementation (KI-29 Loop B+). That decision is parked for the DS architect to surface; if endorsed, this plan inserts it as a Sprint 10.5 or splits the Phase 9-minimal in S10 into two commits.
- It does NOT delete legacy code paths. M10 cleanup stays deferred per the existing memory.md M10 note — per-vertical math knobs in legacy code must be re-homed in priors.yaml or successor config before M10 deletes their legacy home. Sprint sequencing has no removal sprints.
- It does NOT introduce production Shopify / Klaviyo / Segment integrations. D-5 holds. All outcome data still flows via manual JSON import (Sprint 2 S-6 contract).

---

## 2. Per-sprint plan

### Sprint 6 — First two Tier-B builders + supplements parser

**Anchor goal:** Add `winback_dormant_cohort` and `replenishment_due` as the first two Tier-B (directional / observed-effect) builders, closing KI-18/KI-27 in the process by giving supplements a unit-coherent replenishment parser.

**Estimated duration:** 2 weeks (Engineer A + Engineer B in parallel, mirroring Sprint 1 shape).

**Tickets:**

#### S6-T1 — `winback_dormant_cohort` Tier-B builder (Engineer A)

- **Scope:** New `src/builders/winback_dormant_cohort.py` (or extend `measurement_builder.py` if architect prefers a single module — surface this in the DS architect's directory call). Hooks into `src/main.py` Phase 5.6 directional-build site. New `_SUPPORTED` entry mirroring the existing `first_to_second_purchase` shape, but with the dormant-cohort metric (customers with no order in L56–L90).
- **Files touched:** `src/measurement_builder.py`, `src/main.py` (lazy-import the new builder alongside existing directional builder), `config/priors.yaml` (new `winback_dormant_cohort` block — already partially shipped under `winback_21_45`, this is the broader dormant-window variant).
- **Acceptance criteria:**
  - Builder emits `PlayCard(evidence_class=DIRECTIONAL)` on Beauty fixture when the dormant cohort has ≥ `min_audience` and the observed effect signal passes `PHASE5_DIRECTIONAL_P_MAX = 0.05`.
  - Builder cleanly returns `None` (engine falls through) on every supplements fixture where the cadence-coherence flag is set (KI-22 / S5-T3 already pins the flag).
  - Card respects targeting-no-dollar-headline invariant: directional card may show `revenue_range` if `suppressed=False`; today Phase 5.6 suppresses, S6 keeps that posture.
- **Test deliverables:**
  - Unit: `tests/test_s6_t1_winback_dormant_builder.py` — happy path on synthetic fixture, abstain on supplements via cadence-coherence flag, B-5 Berkson invariant check (no fabricated p-values).
  - Integration: Beauty fixture re-pin with new sha256 (likely; the Beauty Recommended Now slate gains one card OR shifts Considered membership). Supplements fixture should stay byte-identical because the supplements path returns `None`.
  - M0 golden behavior: byte-identical on `small_sm`, `mid_shopify`, `micro_coldstart` (the new builder is behind a flag).
- **Schema additions:** None. Re-uses existing `PlayCard` + `Measurement` + `EvidenceClass.DIRECTIONAL`.
- **Feature flags:** `ENGINE_V2_BUILDER_WINBACK_DORMANT` default OFF in all environments except the Beauty fixture; flipped ON at re-pin commit (same commit, plan §7 Risk #4 pattern).
- **Dependencies:** None — independent of S6-T2.

#### S6-T2 — `replenishment_due` Tier-B builder + supplements parser (Engineer B; bundles KI-18 + KI-27 + KI-25 cleanup)

- **Scope:** Two coupled changes in one commit because they must land together:
  1. New `src/builders/replenishment_due.py` Tier-B builder that uses customer-level reorder gap and product-replenishment-window data to flag customers who are X% past their expected reorder gap.
  2. Supplements regex / unit parser in `config/replenishment_sizes.yaml` (already exists for beauty per G-2 contract; this ticket adds a supplements block — `capsule_count`, `serving_per_container`, `mg_per_serving`). New parser dispatcher in `src/replenishment_parser.py`.
  3. Flip `empty_bottle.vertical_applicable` to include `supplements` (closes KI-18). Update `src/decide.py:614` filter accordingly.
- **Files touched:** new `src/builders/replenishment_due.py`, `src/replenishment_parser.py`, `config/replenishment_sizes.yaml`, `config/priors.yaml` (new `replenishment_due` priors per vertical), `src/play_registry.py` (register new play_id; check `display_name` uniqueness assertion still holds), `src/decide.py` (vertical_applicable filter update).
- **Acceptance criteria:**
  - On supplements G-1 fixture, `replenishment_due` ships AS a Recommended Now card (closing the operational-content gap from KI-20 with a *measured* path, not just the abstain card S5-T2 prepended).
  - `empty_bottle` re-enters Considered on supplements (per KI-27 expected re-pin event) OR Recommended if signal supports it.
  - Beauty fixture stays byte-identical *unless* `replenishment_due` outperforms an existing card; if it does, re-pin in same commit with explicit founder-visible justification in the summary file.
- **Test deliverables:**
  - Unit: `tests/test_s6_t2_replenishment_parser.py` — supplements regex coverage (60-count / 90-count / 30-serving), beauty regex unchanged.
  - Unit: `tests/test_s6_t2_replenishment_builder.py` — Tier-B emission shape, gap-calculation math.
  - Integration: Supplements G-1 fixture **re-pin** (this is the explicit re-pin commit). Beauty pin should hold; if it shifts, document why.
  - M0 byte-identical.
- **Schema additions:** None. Uses existing `Measurement.metric` slot with new metric name (`expected_reorder_gap_overrun`).
- **Feature flags:** `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` default OFF, flipped ON at re-pin commit.
- **Dependencies:** None upstream; downstream S7-T2 (`discount_dependency_hygiene`) reuses the parser dispatcher.

#### S6-T3 — Builder-registry harness + invariant scaffold

- **Scope:** Add a thin `src/builders/__init__.py` that exposes the typed `BUILDER_REGISTRY: Dict[play_id, BuilderFn]` so future Tier-B builders register declaratively instead of being hand-imported in `main.py`. This is the lightest-weight prep for S8's Play Library refactor — it lets S7's three remaining builders land without each one needing a `main.py` edit.
- **Files touched:** new `src/builders/__init__.py`, `src/main.py` (replace direct imports with registry lookup).
- **Acceptance criteria:** Existing `first_to_second_purchase` + S6-T1 + S6-T2 all flow through the registry; no behavior change; M0 byte-identical; Beauty pin unchanged.
- **Test deliverables:** `tests/test_s6_t3_builder_registry.py` — registry lookup is order-deterministic; missing-builder lookups return `None` (do not raise — engine must keep running per M9 contract).
- **Schema additions:** None.
- **Feature flags:** None — this is a refactor under existing behavior.
- **Dependencies:** S6-T1, S6-T2 (lands last in the sprint).

**Sprint exit criteria:**
- Suite count: ≥ 1210 passing (S5-T3 baseline 1190 + ~20 from three tickets).
- Beauty pinned slate sha256: documented (likely re-pinned by T1; the value gets recorded in the closeout).
- Supplements G-1 fixture: re-pinned by T2 with explicit sha256.
- KI-18, KI-25, KI-27 flipped resolved. KI-20 stays resolved (S5-T2 path b held). KI-23 partially closed via new Considered membership.

**Risk register:**
- **R-S6.1** — Re-pinning two fixtures in one sprint risks confusion if either ticket needs to revert. *Mitigation:* sequence T1 → T2 → T3 in strict chronological order, each as a separate commit with its own re-pin (plan §7 Risk #4 pattern from S-3).
- **R-S6.2** — `replenishment_due` may inadvertently shadow `subscription_nudge` on supplements (both target reorder-prone cohorts). *Mitigation:* B4 role-uniqueness invariant in `decide.py` already catches pairwise overlaps; add an explicit B5 cannibalization test for this pair.
- **R-S6.3** — New supplements parser may surface unit-coherence issues we haven't anticipated (e.g., variable-pack supplements like "30/60/90 day supply"). *Mitigation:* parser refuses ambiguous patterns and falls through to `vertical_applicable: false` for that SKU, never fabricates a number. Add a parser-refusal test.

**What stays unchanged:**
- M0 goldens (small_sm, mid_shopify, micro_coldstart) byte-identical.
- `event_version=1` schema frozen — no new fields on `engine_run.json`.
- `recommendation_emitted` / `recommendation_considered` payloads unchanged.
- Renderer (`src/storytelling_v2.py`) untouched.
- 4-state abstain not yet introduced; current HARD/SOFT contract still in force.

---

### Sprint 7 — Remaining three Tier-B builders + 4-state abstain + journey-proxy migration

**Anchor goal:** Complete the Tier-B builder set and replace the `returning_customer_share` proxy in `first_to_second_purchase` with a cleaner `cohort_journey_first_to_second` builder. Introduce 4-state abstain so the engine can express *why* it's abstaining beyond "no measured signal."

**Estimated duration:** 2.5 weeks (3 builders + abstain machine + migration is the heaviest sprint in this plan).

#### S7-T1 — `discount_dependency_hygiene` Tier-B builder

- **Scope:** New builder for the play that today exists as a *targeting* play (`discount_hygiene` in the priors and registry). This ticket promotes it to a Tier-B path when discount-share % over L56 has moved up materially against L90 baseline. Uses the existing two-proportion z-test infrastructure for the supporting metric (not the play outcome — see DS architect spec for the distinction).
- **Files touched:** new `src/builders/discount_dependency_hygiene.py`, `src/play_registry.py` (update `discount_hygiene` metadata; keep play_id stable — do NOT introduce a new play_id, this is a builder upgrade), `config/priors.yaml` (`discount_hygiene` keeps its suppression posture from Stop-Coding line fix but gains a directional emission path).
- **Acceptance criteria:**
  - On a synthetic fixture with discount-share % rising L56 vs L90, builder emits Recommended Now directional card.
  - On fixtures where discount-share is stable (Beauty), builder returns `None`; Beauty pin holds.
  - Play remains in `ENGINE_V2_SLATE` allowlist for Recommended Experiment seam (per A4 contract); the two paths don't conflict — builder fires *or* experiment seam fires, never both (role-uniqueness via B4).
- **Test deliverables:** Unit + integration + decide-layer role-uniqueness test.
- **Schema additions:** None.
- **Feature flags:** `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE` default OFF.
- **Dependencies:** S6-T3 (registry).

#### S7-T2 — `cohort_journey_first_to_second` builder + `returning_customer_share` migration

- **Scope:** This is the load-bearing migration. Today's `first_to_second_purchase` directional builder uses `returning_customer_share` as a *state-statistic proxy* (per the docstring in `src/measurement_builder.py:111`); the architect spec calls for replacing this with a real cohort-defined first-to-second metric. Critical: B-5 Berkson invariant pins that any cohort-definition change must respect the early-half-counts rule (per `project_journey_p_zero.md`).
- **Files touched:** `src/measurement_builder.py` (deprecate the `returning_customer_share`-based `_SUPPORTED` entry, route through new builder), new `src/builders/cohort_journey_first_to_second.py`, `src/stats.py` (extend `calculate_journey_stats_single_window` if cohort definition shifts — must keep B-5 invariant).
- **Acceptance criteria:**
  - Beauty fixture: the existing Recommended Now `first_to_second_purchase` card stays Recommended Now, but `measurement.metric` shifts from `returning_customer_share` to `first_to_second_conversion_28d` (or DS architect's chosen name). The numeric `observed_effect` value WILL change because the metric is different. **Beauty fixture re-pin required.**
  - B-5 Berkson invariant test still passes — no time-bias-by-construction reintroduced.
  - Supplements path: still abstains via S5-T2 `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` reason; that abstain card now references the new metric in its `held_reason_detail`.
- **Test deliverables:**
  - `tests/test_s7_t2_cohort_journey_metric.py` — cohort-definition math, B-5 invariant carry-over.
  - **Beauty fixture re-pin** with new sha256 documented.
  - Supplements G-1 fixture re-pin (held_reason_detail changes).
- **Schema additions:** None. Uses `Measurement.metric` with new string value.
- **Feature flags:** `ENGINE_V2_BUILDER_COHORT_JOURNEY` default OFF until re-pin commit.
- **Dependencies:** S6-T3.

#### S7-T3 — `aov_lift_via_threshold_bundle` Tier-B builder

- **Scope:** New builder for the bundle-threshold play (today exists as a targeting variant of `bestseller_amplify`). Detects when AOV has moved materially over L56 vs L90 *and* the customer distribution shows a fat tail near a natural bundle threshold (DS architect specifies the threshold-detection heuristic).
- **Files touched:** new `src/builders/aov_lift_via_threshold_bundle.py`, `src/play_registry.py` (new play_id `aov_lift_via_threshold_bundle` — check `display_name` uniqueness), `config/priors.yaml` (new priors block).
- **Acceptance criteria:**
  - Builder fires on a synthetic fixture with AOV rising and threshold-near distribution; emits Recommended Now directional.
  - Beauty and supplements: builder returns `None` unless the data supports it; fixtures hold unless explicit re-pin.
- **Test deliverables:** Unit + integration + role-uniqueness test (must not overlap with `bestseller_amplify`).
- **Schema additions:** None.
- **Feature flags:** `ENGINE_V2_BUILDER_AOV_BUNDLE_THRESHOLD` default OFF.
- **Dependencies:** S6-T3.

#### S7-T4 — 4-state smarter abstain machine

- **Scope:** Replace binary `ABSTAIN_HARD` / `ABSTAIN_SOFT` decision tag (in `src/engine_run.py::DecisionState`) with a 4-state additive enum:
  - `ABSTAIN_HARD` (existing — data quality flag set; recommendations=[])
  - `SOFT_BELOW_FLOOR` (no measured/directional cleared materiality, but candidates existed)
  - `SOFT_AWAITING_MEASUREMENT` (candidates exist; priors are observational/expert only; no calibration history yet)
  - `SOFT_CADENCE_OUTSIDE_WINDOW` (S5-T2 path generalized — supplements / replenishment cadence beyond primary window)
  - `SOFT_DATA_GAP` (missing data for materiality computation; lighter than HARD)
- **Files touched:** `src/engine_run.py` (extend `DecisionState`), `src/decide.py` (route logic), `src/storytelling_v2.py` (renderer mapping for each soft state to merchant-visible copy), `src/main.py` (S5-T2 supplements path updates to emit the new state).
- **Acceptance criteria:**
  - Existing fixtures get the *most specific* applicable state (Beauty likely `SOFT_BELOW_FLOOR` or PUBLISH; supplements `SOFT_CADENCE_OUTSIDE_WINDOW`).
  - **Beauty and supplements both re-pin in this commit** because the rendered abstain copy changes.
  - M0 byte-identical (the M0 fixtures hit `ABSTAIN_HARD` paths or PUBLISH; the new soft-state granularity should not perturb them — verify).
  - Backward-compat: `DecisionState.ABSTAIN_SOFT` retained as a deprecated alias mapping to `SOFT_BELOW_FLOOR` for one sprint; Swarm consumers update before S8. This is the *only* non-additive-feeling change in the plan; it's load-bearing for merchant-facing copy improvement.
- **Test deliverables:**
  - `tests/test_s7_t4_smarter_abstain.py` — each of the 4 states fires on its dedicated synthetic fixture.
  - Beauty + supplements fixture re-pin with sha256 documented.
  - Schema test: `engine_run.decision_state` accepts old + new strings during the deprecation window.
- **Schema additions:** ADDITIVE within `event_version=1` — three new enum values added to `DecisionState`. The legacy `ABSTAIN_SOFT` literal stays writeable through Sprint 8 then is removed in S9 cleanup (with founder sign-off). Per Sprint 2 schema-freeze contract, additive enum values within an existing field are permitted.
- **Feature flags:** `ENGINE_V2_ABSTAIN_4_STATE` default OFF until both fixtures re-pinned in the SAME commit (plan §7 Risk #4).
- **Dependencies:** S6-T1, S6-T2 (need more builders firing to make the 4 states observable on Beauty/supplements).

**Sprint exit criteria:**
- Suite count: ≥ 1250 passing.
- Beauty pin: re-pinned at S7-T2 (cohort migration) and again at S7-T4 (abstain copy) — two re-pin commits in this sprint, each with documented sha256.
- Supplements pin: re-pinned similarly at S7-T2 and S7-T4.
- KI-21 should now close — supplements gains Recommended Experiment candidates via S7-T1 / S7-T3.
- KI-23 should close — Considered list more comprehensively covers M3 shadow detections via the broader builder set.
- KI-24 stays open per its Phase 4.2 dependency.

**Risk register:**
- **R-S7.1** — Four fixture re-pins in one sprint = high churn. *Mitigation:* batch T2 and T4 re-pins so Beauty + supplements each re-pin twice with documented sha256 lineage in `KNOWN_ISSUES.md` (new KI entries for each re-pin event). Founder sign-off on each re-pin per Stop-Coding-Line discipline.
- **R-S7.2** — Replacing `returning_customer_share` proxy may surface that the original Beauty Recommended Now was emitting on a *less-defensible* metric than we knew. If the new cohort metric doesn't fire on the fixture, the Beauty Recommended Now slate goes to zero again. *Mitigation:* before S7-T2 commits, run the new builder on Beauty fixture in dry-run; if it doesn't fire, S7-T2 splits into two commits — first ship the new builder behind flag, then deprecate the proxy only after the new builder is validated on at least 2 fixtures.
- **R-S7.3** — 4-state abstain breaks Swarm consumer assumptions. *Mitigation:* deprecation alias (S7-T4 spec) + 1-sprint grace period + S-6 Swarm coordination memo updated in `docs/memory_substrate.md`.

**What stays unchanged:**
- M0 goldens byte-identical.
- `event_version=1` (new enum values are additive; no field reshape).
- `recommendation_emitted` / `recommendation_considered` payloads unchanged.
- B-5 Berkson invariant, B-4 role-uniqueness, M-invariants all hold.
- Renderer surface: only the abstain copy mapping changes; chart layout, card structure, mechanism line all unchanged.

---

### Sprint 8 — Evidence-tier formalization + Empirical-Bayes blend + Play Library refactor (wave 1)

**Anchor goal:** Lock the trust-surface PlayCard contract for beta and ship the EB blend layer so Tier-B builders' observed effects can be blended with priors via a defensible pseudo_N. Begin Play Library directory restructure with 3–4 plays as the migration template.

**Estimated duration:** 2 weeks.

#### S8-T1 — Evidence Tier (A/B/C/D) formalization + PlayCard contract additions

- **Scope:** Add typed `evidence_source` (Causal / Directional / Prior / Observational) and `signal_kind` (Observed / Predicted / Heuristic) fields to `PlayCard`. Today's `EvidenceClass` enum stays; the new fields are *additional* trust-surface dimensions per the DS architect spec.
- **Files touched:** `src/engine_run.py` (new typed enums + fields on `PlayCard`), `src/measurement_builder.py` + all S6/S7 builders (populate the new fields), `src/storytelling_v2.py` (render the chip in the EVIDENCE band per KI-30 slot spec).
- **Acceptance criteria:**
  - Every emitted PlayCard carries `evidence_source` and `signal_kind`.
  - HTML briefing renders a `data-evidence-source="C|D|P|O"` attribute on each Recommended Now / Recommended Experiment card.
  - Renderer respects the forbidden-token sweep (B2 contract) — no p-values, q-values, confidence percentages.
  - **Beauty and supplements re-pin** (renderer surface changes).
- **Test deliverables:**
  - `tests/test_s8_t1_evidence_tier_ahip.py` — every builder populates the field; chip renders per typed mapping.
  - Fixture re-pins.
  - Forbidden-token sweep extended to scope new chip text.
- **Schema additions:** ADDITIVE within `event_version=1` — `PlayCard.evidence_source: EvidenceSourceTier` and `PlayCard.signal_kind: SignalKind` as Optional fields. Default value `None` permitted during migration; populated by builders post-S8-T1. Single-writer ownership: builders are the only writers (decide.py and renderer are readers only). New `_ALLOWED_WRITERS` allowlist entry for these fields if grep test extends.
- **Feature flags:** `ENGINE_V2_EVIDENCE_TIER_AHIP` default OFF until fixture re-pin commit.
- **Dependencies:** None at code level; sequenced after S7 to avoid stacking re-pins.

#### S8-T2 — Sensitivity block + provenance object on PlayCard

- **Scope:** Add typed `sensitivity: Sensitivity` block (one-up-one-down scenario values for revenue_range — DS architect specifies the math) and `provenance: Provenance` object (data-source lineage for the supporting metric — which CSV, which window, which n).
- **Files touched:** `src/engine_run.py` (new typed dataclasses), all builders, `src/storytelling_v2.py` (renderer surface for the sensitivity strip per KI-30 slot 4/5).
- **Acceptance criteria:**
  - Every measured/directional PlayCard carries `sensitivity` and `provenance`.
  - Targeting cards: `sensitivity = None` (acceptable; targeting cards already lack measurement); `provenance` carries audience-builder lineage.
  - Renderer renders sensitivity strip when `revenue_range.suppressed = False`; when suppressed, sensitivity is hidden and the existing "audience × AOV" fallback shows.
- **Test deliverables:**
  - `tests/test_s8_t2_sensitivity_provenance.py` — math correctness, render output, suppressed-state behavior.
  - **Beauty fixture re-pin** (sensitivity strip is new visible surface).
- **Schema additions:** Additive within `event_version=1`. Both fields Optional. Builders are sole writers.
- **Feature flags:** `ENGINE_V2_SENSITIVITY_STRIP` default OFF until re-pin.
- **Dependencies:** S8-T1 (fixture already re-pinned; this is the second re-pin in S8).

#### S8-T3 — Empirical-Bayes blend layer in `sizing.py`

- **Scope:** New `src/sizing/eb_blend.py` (or extend `sizing.py`) that takes `(observed_effect, prior_p10/p50/p90, pseudo_N_for_source_class)` and returns a blended posterior. `pseudo_N` per `source_class`: `expert = 1`, `observational = 5`, `causal = 20` (DS architect locks the exact numbers). Observed n's effective weight = `n / (n + pseudo_N)`.
- **Files touched:** `src/sizing.py` (new `blend_with_prior` helper called from `size_play`), `src/priors_loader.py` (pseudo_N lookup helper).
- **Acceptance criteria:**
  - On a synthetic case where observed effect is dramatically larger than prior, blend pulls it back toward prior (defensibly conservative).
  - On a case where observed n is large (1000+ orders), blend lets observed dominate.
  - **No fixture re-pin** — this commit lands with the EB blend behind a flag that defaults to OFF; flag flip + re-pin is a separate commit in S8-T4.
- **Test deliverables:**
  - `tests/test_s8_t3_eb_blend.py` — math correctness, pseudo_N table, edge cases (zero observed n, missing prior).
- **Schema additions:** `RevenueRange.source` gains new literal `"blend_empirical_bayes"` (additive within existing `RevenueRangeSource` enum).
- **Feature flags:** `ENGINE_V2_EB_BLEND` default OFF.
- **Dependencies:** None — pure math, independent of S8-T1/T2.

#### S8-T4 — Flip EB blend ON + fixture re-pin

- **Scope:** Single commit that flips `ENGINE_V2_EB_BLEND` ON and re-pins Beauty + supplements. Separation from S8-T3 enforces the §7 Risk #4 discipline.
- **Files touched:** Test fixture sha256 constants only; one-line flag default flip in `src/utils.py`.
- **Acceptance criteria:** Re-pinned fixtures show `revenue_range.source = "blend_empirical_bayes"` and modestly narrower p10/p90 bands; merchant-facing copy unchanged.
- **Test deliverables:** Re-pin commit with documented sha256 lineage.
- **Schema additions:** None.
- **Feature flags:** Flag flipped ON; documented in flag inventory.
- **Dependencies:** S8-T3.

#### S8-T5 — Play Library refactor (wave 1: 3 plays)

- **Scope:** Begin the directory restructure to `plays/<play_id>/` first-class spec. **Wave 1: only 3 plays** — the three with the cleanest scope to migrate (DS architect recommendation; likely `winback_dormant_cohort`, `replenishment_due`, `discount_dependency_hygiene`). Each gets a `plays/<play_id>/{spec.yaml, audience.py, builder.py, copy.md}` directory; remaining 11 plays stay in legacy locations.
- **Files touched:** New `plays/` directory tree. `src/play_registry.py` extended to load from `plays/<play_id>/spec.yaml` when present; falls back to legacy hard-coded registry entries when absent.
- **Acceptance criteria:**
  - 3 migrated plays produce byte-identical output to their pre-migration state.
  - 11 unmigrated plays untouched.
  - M0 byte-identical (the migrated plays don't fire in M0 fixtures).
- **Test deliverables:**
  - `tests/test_s8_t5_play_library_migration.py` — registry loads both paths; behavior identical for migrated plays.
- **Schema additions:** None.
- **Feature flags:** None — this is a refactor with behavior preservation.
- **Dependencies:** S6-T3 (builder registry).

**Sprint exit criteria:**
- Suite count: ≥ 1290 passing.
- Beauty + supplements re-pinned: 2 times each in this sprint (S8-T1 chip, S8-T2 sensitivity; S8-T4 EB blend re-pin happens but rolls into the same fixture cycle).
- `engine_run.json` schema for `PlayCard`: 4 new optional fields (`evidence_source`, `signal_kind`, `sensitivity`, `provenance`) — all additive within `event_version=1`.
- 3 plays migrated to `plays/<play_id>/`; 11 remain in legacy form.

**Risk register:**
- **R-S8.1** — Three additive PlayCard fields landing in one sprint stress-tests the schema-freeze additive-only contract. *Mitigation:* DS architect spec must explicitly justify each field's additive shape; Swarm-team coordination memo updated in `docs/memory_substrate.md` per S-3 freeze discipline.
- **R-S8.2** — EB blend may narrow Beauty's revenue_range enough that the merchant-facing copy "could realistically add at least $X" footer threshold changes. *Mitigation:* materiality footer copy formula (Phase 5.4) reads from the *same* underlying numbers; if the band narrows, the footer threshold tracks. Pin the math relationship in test.
- **R-S8.3** — Play Library wave 1 migration may surface that some legacy plays have hidden dependencies on `action_engine.py` internals. *Mitigation:* DS architect spec selects the 3 cleanest candidates (likely the new S6/S7 builders themselves, which have no legacy entanglement).

**What stays unchanged:**
- M0 goldens byte-identical.
- `event_version=1` frozen (only additive field additions per established carve-out).
- 11 plays in legacy `src/audience_builders.py` / `src/action_engine.py` paths.
- B-4 role-uniqueness, B-5 Berkson, M-invariants.

---

### Sprint 9 — Trust-math tooling + renderer surface for evidence chip

**Anchor goal:** Ship the sensitivity strip, replay CLI, and backtest CLI as founder-internal trust-math tooling. These don't go merchant-facing for beta; they exist so the founder can audit recommendations and run synthetic backtests against historical CSVs.

**Estimated duration:** 1.5 weeks (lighter sprint; trust-math tooling is mostly CLI work).

#### S9-T1 — Sensitivity strip renderer + provenance chip

- **Scope:** Visible KI-30 slot 4/5 renderer for the sensitivity block S8-T2 landed. Renders three p10/p50/p90 markers on a horizontal bar with the provenance chip inline.
- **Files touched:** `src/storytelling_v2.py` (new HTML snippet), CSS templates if present.
- **Acceptance criteria:** Beauty re-pin (third in this trajectory; expected). Forbidden-token sweep passes. M0 unchanged.
- **Test deliverables:** Beauty re-pin commit with documented sha256.
- **Schema additions:** None (consumes S8-T2's typed fields).
- **Feature flags:** `ENGINE_V2_SENSITIVITY_RENDER` default OFF until re-pin.
- **Dependencies:** S8-T2.

#### S9-T2 — Replay CLI

- **Scope:** New `tools/replay_run.py` — loads an immutable `data/<store_id>/runs/<run_id>.json` snapshot and re-renders the briefing without re-running the engine. Useful for testing renderer changes against historical runs without CSV access.
- **Files touched:** New `tools/replay_run.py`. Reads `src/storytelling_v2.py` (does not modify engine).
- **Acceptance criteria:** Round-trip test: replay produces byte-identical briefing.html to the original run.
- **Test deliverables:** `tests/test_s9_t2_replay_cli.py`.
- **Schema additions:** None (reader only).
- **Feature flags:** None — CLI is opt-in by invocation.
- **Dependencies:** S-4 (immutable snapshot path).

#### S9-T3 — Backtest CLI

- **Scope:** New `tools/backtest_engine.py` — runs the engine against a historical CSV window with a fixed cut-off date, emits a synthetic `recommendation_emitted` payload, and (when paired with manually-curated outcome data) compares predicted vs realized for trust-math audit.
- **Files touched:** New `tools/backtest_engine.py`. Reads engine end-to-end; writes ONLY to a backtest namespace (`data/_backtest/<run_id>/`) — never touches a real store's substrate (D-3 enforcement).
- **Acceptance criteria:**
  - Backtest run produces an `engine_run.json` byte-identical to a normal run on the same CSV (modulo run_id).
  - Backtest writes are isolated to `data/_backtest/`; verify with grep test.
- **Test deliverables:** `tests/test_s9_t3_backtest_cli.py`.
- **Schema additions:** None.
- **Feature flags:** None.
- **Dependencies:** S-4, S-5.

#### S9-T4 — Sensitivity-strip math sanity audit tool

- **Scope:** `tools/audit_sensitivity.py` — for each play in `recommended_history.json`, prints the actual p10/p50/p90 vs the post-EB-blend prior. Helps the founder spot plays whose blend may have collapsed too aggressively (or not enough).
- **Files touched:** New tool only.
- **Acceptance criteria:** Output table is deterministic; documented in `docs/memory_substrate.md`.
- **Test deliverables:** `tests/test_s9_t4_sensitivity_audit.py`.
- **Schema additions:** None.
- **Feature flags:** None.
- **Dependencies:** S8-T3, S8-T4.

**Sprint exit criteria:**
- Suite count: ≥ 1310 passing.
- Beauty re-pinned once more (S9-T1).
- 3 new CLIs in `tools/`: `replay_run.py`, `backtest_engine.py`, `audit_sensitivity.py`.

**Risk register:**
- **R-S9.1** — Sensitivity strip render may be visually cluttered on cards already carrying mechanism + provenance + audience-size bar. *Mitigation:* DS architect spec validates the slot ordering against KI-30; founder accept-on-fixture before re-pin.
- **R-S9.2** — Backtest CLI accidentally writes to a real store's substrate. *Mitigation:* hard-coded namespace prefix + assertion in `tools/backtest_engine.py` + grep test that the writer path can never resolve outside `data/_backtest/`.

**What stays unchanged:**
- M0 goldens.
- `event_version=1`.
- 11 unmigrated plays still in legacy paths.

---

### Sprint 10 — Phase 9-minimal outcome loop

**Anchor goal:** Close the loop. Beacon can now ingest `outcome_observed` events for past `recommendation_emitted` events, write `calibration_updated` events that shift priors, and surface "last month's outcome" on the briefing.

**Estimated duration:** 2 weeks. **Beta-blocking.**

#### S10-T1 — `outcome_observed` importer (closes KI-1 / KI-2 / KI-9)

- **Scope:** New `tools/import_outcome_observed.py` — single-writer for `outcome_observed` events per S-6 contract. Strict v1 validation per documented refusal rules in `docs/memory_substrate.md`. Mirrors the `import_campaign_sent.py` shape.
- **Files touched:** New `tools/import_outcome_observed.py`. `src/memory/events.py` (typed `OutcomeObservedPayload` at `event_version=1`).
- **Acceptance criteria:**
  - Importer refuses every documented bad-shape case (positive-projection test per KI-1).
  - Lineage cross-check: each `outcome_observed` must reference a prior `recommendation_emitted` for the same `lineage_id`.
  - Re-running over same inbox file: idempotent refusal.
  - `outcome_status` enum strict.
- **Test deliverables:** `tests/test_s10_t1_outcome_observed_importer.py` (≥15 tests mirroring S-6's CampaignSent importer test count).
- **Schema additions:** `outcome_observed` payload at `event_version=1` — frozen post-S10-T1. Documented as the Phase 9 contract per S-6.
- **Feature flags:** None — CLI is opt-in.
- **Dependencies:** S-6 documented contract.

#### S10-T2 — Calibration writer (closes KI-4)

- **Scope:** New `src/calibration_writer.py` — reads `v_lineage_timeline` for completed `(recommendation_emitted, campaign_sent, outcome_observed)` triples, computes the realized-vs-predicted realization factor, writes `calibration_updated` events. Last-write-wins per (section, key) tuple is pinned per KI-4. K=3 minimum gate (founder decision).
- **Files touched:** New `src/calibration_writer.py`. New `tools/run_calibration.py` CLI to invoke the writer manually (engine does not auto-run calibration on every engine_run — founder discretion).
- **Acceptance criteria:**
  - Writer requires N≥3 outcomes per play before emitting `calibration_updated`.
  - `calibration_updated` payload shape matches S-5 `v_calibration_state` contract.
  - Single-writer grep test allowlist updated for `calibration_updated`.
- **Test deliverables:** `tests/test_s10_t2_calibration_writer.py`.
- **Schema additions:** `calibration_updated` payload formally pinned at `event_version=1` (previously documented but no writer existed). S-5 read view contract already in place.
- **Feature flags:** None — CLI is opt-in.
- **Dependencies:** S10-T1.

#### S10-T3 — Renderer surface for "last month's outcome"

- **Scope:** Briefing footer adds a "Last month's recommendations: outcome" section that reads from `v_open_recommendations` joined to `outcome_observed`. Renders one line per play with "Recommended → realized $X (N% of projected)". When `outcome_observed` is absent, renders "Outcome pending."
- **Files touched:** `src/storytelling_v2.py` (new section), `src/memory/views.py` (extend with a join view).
- **Acceptance criteria:**
  - Beauty fixture re-pin (new section added — but only if Beauty fixture has historical events; on a fresh fixture this section renders "No prior recommendations on file" and the briefing is still byte-stable).
  - M0 byte-identical.
- **Test deliverables:** `tests/test_s10_t3_last_month_outcome_render.py`. Beauty re-pin commit.
- **Schema additions:** New read view `v_last_month_outcomes` added per S-5 migration pattern; user_version bump 2 → 3.
- **Feature flags:** `ENGINE_V2_LAST_MONTH_OUTCOME` default OFF until re-pin.
- **Dependencies:** S10-T1, S10-T2.

**Sprint exit criteria:**
- Suite count: ≥ 1340 passing.
- KI-1, KI-2, KI-4, KI-9 all flipped resolved.
- `outcome_observed` and `calibration_updated` event_versions both pinned at v1.
- Beauty re-pinned with last-month-outcome section.

**Risk register:**
- **R-S10.1** — Calibration writer may emit `calibration_updated` events that shift priors in a way that breaks Beauty fixture stability. *Mitigation:* calibration runs ONLY on operator invocation (`tools/run_calibration.py`); not in the engine's main path. Beauty fixture never accumulates calibration events because no merchant outcomes exist for the synthetic data.
- **R-S10.2** — KI-29 Loop B+ subsegment-attribution decision still pending. *Mitigation:* DS architect surfaces the Loop B vs Loop B+ call before S10-T1 lands. If B+ endorsed, `outcome_observed` payload includes the Optional `realized_breakdown` field from day one (per KI-29 proposed shape) — *additive within v1, no re-version*. If B endorsed, that field is omitted; later upgrade to B+ is itself additive.
- **R-S10.3** — Importer's strict refusals may cause friction with Klaviyo Deploy Agent (Swarm team). *Mitigation:* S-6 already locked the contract; Swarm coordinated. If KI-7 provider-enum tightening is needed before beta, it bumps to `event_version=2` and pushes beta — escalation path documented.

**What stays unchanged:**
- M0 goldens.
- All M-invariants.
- Engine main path does NOT auto-calibrate — calibration is an operator-invoked tool.

---

### Sprint 11 — Private beta integration buffer

**Anchor goal:** Run the full stack end-to-end against 1–2 founder-selected merchant CSVs. Surface and fix integration issues before public beta.

**Estimated duration:** 1.5 weeks (timeboxed; founder can extend).

**Ticket structure:** Tickets in this sprint are *reactive* — they're filed in response to findings on real-merchant fixtures. Plan slot for:
- S11-T1: Pin the first private-beta merchant fixture (replicates G-1 / B-6 pattern).
- S11-T2: Pin the second private-beta merchant fixture.
- S11-T3: Buffer ticket for emergent KI-class findings (likely UX, copy, or edge-case parser).
- S11-T4: Beta-launch checklist sweep (see §9).

**Sprint exit criteria:**
- ≥2 real-merchant fixtures pinned with end-to-end PUBLISH-eligible runs (or documented honest-abstain reasons).
- All open KIs reviewed; any new findings filed.
- Beta-launch checklist (§9) checked end-to-end.

**Risk register:**
- **R-S11.1** — Real merchant data may exercise paths no synthetic fixture has touched (large customer pools, edge-case SKU patterns, multi-currency, etc.). *Mitigation:* this is exactly what S11 exists to surface; budget extends to S11-T5/T6 if needed.

---

## 3. Schema migrations summary

All schema changes additive within `event_version=1` unless explicitly noted. Single-writer ownership enforced via S-3 grep test.

| Sprint | Schema field | Type | Additive justification | Writer |
|---|---|---|---|---|
| S6 | `PlayCard.measurement.metric` new string values | `str` (enum-like) | New metric names within free-text slot | Builders |
| S7-T4 | `DecisionState` adds 3 enum values | Enum literal | Backward-compat alias for `ABSTAIN_SOFT` | `src/decide.py` |
| S8-T1 | `PlayCard.evidence_source` | `Optional[EvidenceSourceTier]` | Optional field; defaults `None` during migration | Builders |
| S8-T1 | `PlayCard.signal_kind` | `Optional[SignalKind]` | Optional field | Builders |
| S8-T2 | `PlayCard.sensitivity` | `Optional[Sensitivity]` | Optional typed sub-object | Builders |
| S8-T2 | `PlayCard.provenance` | `Optional[Provenance]` | Optional typed sub-object | Builders |
| S8-T3 | `RevenueRangeSource` adds `"blend_empirical_bayes"` | Enum literal | Additive enum value | `src/sizing.py` |
| S10-T1 | `OutcomeObservedPayload` v1 frozen | New event type | Already documented in S-6 contract | `tools/import_outcome_observed.py` |
| S10-T2 | `CalibrationUpdatedPayload` v1 frozen | New event type writer | Read view existed since S-5 | `src/calibration_writer.py` |
| S10-T3 | `v_last_month_outcomes` view + user_version 2→3 | New read view | Read-only addition; migration `IF NOT EXISTS` | `src/memory/views.sql` |

No field reshape. No type changes. No removal. The only borderline-non-additive change is the `DecisionState.ABSTAIN_SOFT` deprecation alias in S7-T4 — handled via 1-sprint grace period and explicit Swarm-team coordination.

---

## 4. Fixture re-pin schedule

Tracks every commit that re-pins a fixture sha256. Re-pin discipline: founder sign-off + same-commit re-pin per plan §7 Risk #4 (S-3 pattern).

| Sprint | Ticket | Fixture | Reason | Pattern |
|---|---|---|---|---|
| S6 | S6-T1 | Beauty | New `winback_dormant_cohort` Recommended Now card | Same-commit flag flip |
| S6 | S6-T2 | Supplements G-1 | New `replenishment_due` Recommended Now + `empty_bottle` re-entry | Same-commit flag flip |
| S7 | S7-T2 | Beauty + Supplements | `cohort_journey_first_to_second` migration; metric name + observed_effect shift | Same-commit flag flip |
| S7 | S7-T4 | Beauty + Supplements | 4-state abstain copy changes | Same-commit flag flip |
| S8 | S8-T1 | Beauty + Supplements | Evidence-tier chip render | Same-commit flag flip |
| S8 | S8-T2 | Beauty | Sensitivity strip render (supplements stays — strip suppressed when revenue_range suppressed) | Same-commit flag flip |
| S8 | S8-T4 | Beauty + Supplements | EB blend flag flip | Same-commit flag flip |
| S9 | S9-T1 | Beauty | Sensitivity strip + provenance chip CSS polish | Same-commit flag flip |
| S10 | S10-T3 | Beauty | "Last month's outcome" section | Same-commit flag flip |
| S11 | S11-T1/T2 | New real-merchant fixtures | First-time pinning | Replicates G-1 |

**M0 goldens** (`small_sm`, `mid_shopify`, `micro_coldstart`): byte-identical across the entire plan. If any M0 re-pin proves unavoidable, it gets escalated to founder before commit per Stop-Coding-Line discipline.

---

## 5. M-invariants preservation map

For each new component, the M-invariant test that pins its contract:

| New component | M-invariant | Enforcement |
|---|---|---|
| All 5 new Tier-B builders (S6/S7) | `evidence_class == "directional"` ⇒ `measurement.observed_effect` non-null | Unit test per builder: `test_builder_emits_directional_with_observed_effect` |
| All 5 new Tier-B builders | B-5 Berkson invariant — no time-bias-by-construction cohort | `tests/test_berkson_invariant.py` extended with each new builder |
| `cohort_journey_first_to_second` (S7-T2) | Cohort denominator on early-half counts only | Inherits B-5 test; explicit new assertion |
| 4-state abstain (S7-T4) | Targeting-only ⇒ never `PUBLISH` | M7 invariant carry-over: `tests/test_v2_decide.py::test_targeting_only_abstain_soft` |
| Evidence-tier chip (S8-T1) | No forbidden tokens in chip text | B2 forbidden-token sweep extended |
| Sensitivity block (S8-T2) | `revenue_range.suppressed=True` ⇒ sensitivity hidden in render | `tests/test_storytelling_v2.py` extended |
| EB blend (S8-T3) | Conservative — observed never exceeds prior p90 by more than pseudo_N ratio allows | `tests/test_s8_t3_eb_blend.py::test_blend_is_conservative` |
| Outcome importer (S10-T1) | Single-writer for `outcome_observed` | `tests/test_single_writer_per_event_type.py` allowlist |
| Calibration writer (S10-T2) | Single-writer for `calibration_updated` | Same allowlist; K=3 gate test |
| Last-month-outcome render (S10-T3) | No-forward-projection invariant (KI-30 universal rule) | Renderer test |

All existing invariants (B-1 anomaly routing, B-3 hardcoded-fallback sweep, B-4 role-uniqueness, B-5 Berkson, B-6 directional gap, G-2 parser unit-coherence, G-4 targeting-reclassify) **continue to hold across all sprints**.

---

## 6. Feature flag inventory

| Flag | Introduced | Default | Flip ON event | Cleanup |
|---|---|---|---|---|
| `ENGINE_V2_BUILDER_WINBACK_DORMANT` | S6-T1 | OFF | S6-T1 re-pin commit | After S11 |
| `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` | S6-T2 | OFF | S6-T2 re-pin commit | After S11 |
| `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE` | S7-T1 | OFF | S7-T1 same-commit | After S11 |
| `ENGINE_V2_BUILDER_COHORT_JOURNEY` | S7-T2 | OFF | S7-T2 same-commit | After S11 |
| `ENGINE_V2_BUILDER_AOV_BUNDLE_THRESHOLD` | S7-T3 | OFF | S7-T3 same-commit | After S11 |
| `ENGINE_V2_ABSTAIN_4_STATE` | S7-T4 | OFF | S7-T4 same-commit | After S11 |
| `ENGINE_V2_EVIDENCE_TIER_AHIP` | S8-T1 | OFF | S8-T1 re-pin | After S11 |
| `ENGINE_V2_SENSITIVITY_STRIP` | S8-T2 | OFF | S8-T2 re-pin | After S11 |
| `ENGINE_V2_EB_BLEND` | S8-T3 | OFF | S8-T4 re-pin | After S11 |
| `ENGINE_V2_SENSITIVITY_RENDER` | S9-T1 | OFF | S9-T1 re-pin | After S11 |
| `ENGINE_V2_LAST_MONTH_OUTCOME` | S10-T3 | OFF | S10-T3 re-pin | After S11 |

**Existing flags retained** (per memory.md): `ENGINE_V2_DECIDE`, `ENGINE_V2_OUTPUT`, `ENGINE_V2_SLATE`, `ANOMALY_GATE_ENABLED`, `RECENTLY_RUN_FATIGUE_ENABLED`, `OUTCOME_LOG_ENABLED`, `STATS_NAN_FOR_HARDCODED`, `EVIDENCE_CLASS_ENFORCED`.

**Ramp-up plan:** Every new builder flag flips ON in its own commit, paired with a fixture re-pin. No flag flips silently. Founder approves each flip via summary file review (Stop-Coding-Line discipline).

**Cleanup date:** All S6–S10 flags become defaults-ON across the entire codebase in S11-T4 (beta-launch checklist). The flags remain in the codebase as env-overridable switches (operator escape hatch) but no longer behind-flag in any sense; goldens reflect flag-ON state.

---

## 7. Rollback strategy

For each beta-blocking sprint, the rollback procedure:

| Sprint | Rollback granularity | Procedure |
|---|---|---|
| **S6** | Per-ticket | Each builder is behind its own flag; flip flag OFF and the engine reverts to pre-builder behavior. Fixture re-pin revert: cherry-pick the pre-pin commit's sha256 constants back. No data loss. |
| **S7** | Per-ticket | Same as S6. For 4-state abstain, the deprecation alias (`ABSTAIN_SOFT`) keeps Swarm consumers reading; flag OFF reverts engine emission. |
| **S8** | Per-feature | Schema additions are Optional; engines reading `engine_run.json` without the new fields still work. EB blend has its own flag. Play Library wave 1 plays fall back to legacy registry path if `plays/<play_id>/` directory is reverted. |
| **S10** | Per-tool | `outcome_observed` events in substrate are immutable per D-2. Reverting the importer doesn't remove already-imported events — the calibration writer simply doesn't run, and the briefing's "last month's outcome" section renders "No prior recommendations on file." Engine main path unchanged. |
| **S11** | Per-merchant | New real-merchant fixtures are isolated; rolling them back doesn't affect Beauty / Supplements G-1 baselines. |

**Cross-sprint rollback:** Because every sprint preserves M0 goldens byte-identical, a full rollback to S5-T3 baseline is always available via `git revert` on the post-S5 commits. The engine remains runnable at every commit.

**Schema rollback:** The only schema risk is S7-T4's `ABSTAIN_SOFT` deprecation. **Mitigation:** maintain the alias through S10. If a beta-launch issue requires reverting S7-T4, do so before S10-T3 (last-month-outcome section references decision_state).

---

## 8. KI roadmap mapped to sprints

| KI | Title | Status | Sprint | Rationale |
|---|---|---|---|---|
| KI-1 | `outcome_observed` no positive-projection test | **Closed S10-T1** | S10 | Importer's first test pins refusal rules end-to-end |
| KI-2 | `load_realization_factors` swallows malformed sections | **Closed S10-T2** | S10 | Calibration writer's positive-projection test forces loud failure |
| KI-3 | `store_id` kwarg not plumbed | Resolved S5-T1 | — | Already done |
| KI-4 | Calibration last-write-wins per (section, key) | **Closed S10-T2** | S10 | Writer's test pins the contract |
| KI-5 | `v_lineage_recent_emissions` anchor uses `MAX(created_at)` | **Closed S10-T2** | S10 | When calibration writer wires to fatigue gate, the anchor semantics get documented in test |
| KI-6 | `campaign_id` per-store, not global | Accepted | — | Won't fix; cross-store analytics Year 2+ |
| KI-7 | `provider` field free-text | Deferred | Post-beta | Closing requires `event_version=2`; Swarm coordination |
| KI-8 | Inbox files persist after import | Accepted | — | Operator discipline |
| KI-9 | `sent_at` shape-only validation | **Closed S10-T1** | S10 | Importer extends to ISO-8601 parse |
| KI-10 | Disk growth monotonic | Accepted | — | AWS migration |
| KI-11 | Snapshot mirror not atomic | Accepted | — | No live read-during-write consumer |
| KI-12 | Fallback `snapshot_sha256=None` | Accepted | — | Auditor contract |
| KI-13 | Substrate migration one-way | Accepted | — | D-2 |
| KI-14 | `UPDATE RETURNING` SQLite ≥ 3.35 | Accepted | — | Current runtime is 3.53 |
| KI-15 | Single-writer grep evades via rST | Accepted | — | Fragile but documented |
| KI-16 | Reader-allowlist grep hack | Deferred | Post-beta | Cosmetic refactor |
| KI-17 | Supplements V2 speculation | Resolved | — | G-1 |
| KI-18 | `empty_bottle.vertical_applicable` excludes supplements | **Closed S6-T2** | S6 | Supplements parser shipped with replenishment_due |
| KI-19 | `mixed` not formally tested | Resolved | — | G-3 |
| KI-20 | Supplements zero Recommended Now | Resolved | — | S5-T2 path (b) |
| KI-21 | Supplements zero Recommended Experiment | **Closed S7-T1 + S7-T3** | S7 | New Tier-B builders unblock |
| KI-22 | Repeat-rate 0% advisory | Resolved | — | S5-T3 |
| KI-23 | Supplements: M3 drop-outs | **Closed S7** | S7 | Broader Tier-B builders + 4-state abstain surface more candidates |
| KI-24 | Supplements `subscription_nudge` generic reason | Deferred | Post-PMF | Phase 4.2 redesign required; doc gap for now |
| KI-25 | Supplements `routine_builder` audience_too_small | **Closed S6-T2** | S6 | New replenishment parser + per-vertical floors wired |
| KI-26 | Supplements observations `prior: null` | Resolved | — | S5-T1 |
| KI-27 | `empty_bottle` clean-skipped on supplements | **Closed S6-T2** | S6 | Re-enters supplements via parser |
| KI-28 | `mixed` vertical not end-to-end fixture | **Closed S11** | S11 | Real-merchant fixture (if `mixed` merchant available) or new synthetic |
| KI-29 | Loop B vs Loop B+ subsegment attribution | **Decision S10** | S10 | DS architect call surfaces before S10-T1 |
| KI-30 | Per-play evidence visualization | **Closed S8 + S9** | S8/S9 | Slot spec lands as evidence_source chip + sensitivity strip + provenance chip |

**Won't-fix justifications (none outright won't-fix):** KI-6 and KI-7 are Swarm-coordination dependent; both could be revisited post-beta but neither blocks beta.

**Open post-S11:** KI-7 (provider enum tightening), KI-15/KI-16 (grep test cosmetics), KI-24 (Phase 4.2 subscription_nudge redesign).

---

## 9. Beta-launch checklist

Specific, checkable items that must be true on the day the first real brand opens their briefing.

- [ ] All M0 goldens (`small_sm`, `mid_shopify`, `micro_coldstart`) byte-identical to pre-S6 baseline.
- [ ] Beauty pinned slate at final S10-T3 sha256 documented in `KNOWN_ISSUES.md` lineage table.
- [ ] Supplements G-1 fixture at final S10-T3 sha256 documented.
- [ ] At least 2 real-merchant fixtures pinned in S11.
- [ ] All 5 new Tier-B builders firing on at least one fixture each.
- [ ] 4-state abstain machine: each of `ABSTAIN_HARD`, `SOFT_BELOW_FLOOR`, `SOFT_AWAITING_MEASUREMENT`, `SOFT_CADENCE_OUTSIDE_WINDOW`, `SOFT_DATA_GAP` covered by at least one test fixture.
- [ ] Every PlayCard in pinned fixtures carries: `evidence_class`, `evidence_source`, `signal_kind`, `provenance`. Measured/directional cards also carry `sensitivity`.
- [ ] EB blend layer enabled by default; `revenue_range.source == "blend_empirical_bayes"` visible on at least one card in a pinned fixture.
- [ ] `outcome_observed` importer tested end-to-end with a synthetic outcome JSON file.
- [ ] `calibration_writer` tested end-to-end on a synthetic 3-outcome history.
- [ ] Briefing "last month's outcome" section renders correctly on both empty-history (fresh install) and populated-history paths.
- [ ] All feature flags (`ENGINE_V2_BUILDER_*`, `ENGINE_V2_EVIDENCE_TIER_AHIP`, `ENGINE_V2_SENSITIVITY_*`, `ENGINE_V2_EB_BLEND`, `ENGINE_V2_ABSTAIN_4_STATE`, `ENGINE_V2_LAST_MONTH_OUTCOME`) default ON.
- [ ] No forbidden tokens in any pinned briefing.html (B-2 sweep extended for new sections).
- [ ] D-5 still enforced: no Klaviyo / Shopify production API calls in `src/` or `tools/`.
- [ ] D-6 still enforced: no ML model code (LinUCB, contextual bandits) anywhere.
- [ ] D-8 still enforced: `apparel`, `food`, `home`, `wellness` refused at engine entry.
- [ ] G-7 determinism CI passing: two-run byte-identity on `engine_run.json` post-`NORMALIZED_FIELDS`.
- [ ] S-3 substrate single-writer grep test passing.
- [ ] S-4 immutable snapshot path populated on every run.
- [ ] S-5 calibration view returning canonical empty-shape on fresh installs.
- [ ] S-6 campaign_sent importer tested.
- [ ] S10-T1 outcome_observed importer tested.
- [ ] `recommendation_emitted`, `recommendation_considered`, `campaign_sent`, `outcome_observed`, `calibration_updated` all at `event_version=1`.
- [ ] Suite count: ≥ 1340 passing, 14 skipped, 0 failed (modulo pre-existing wall-clock flake).
- [ ] `docs/memory_substrate.md` documents every event_type, payload shape, view, and migration version.
- [ ] `KNOWN_ISSUES.md` has zero `open` entries in categories 1 (Phase 9 entry conditions) and 5 (Supplements & vertical) other than the explicitly-deferred KI-24.
- [ ] Founder has personally reviewed at least one fresh-install run on a real merchant CSV and signed off on copy + slate.
- [ ] Beta merchants have been onboarded with manual-import documentation for `campaign_sent` and `outcome_observed` events (per D-5).
- [ ] `tools/export_store.py` round-trip test passes on the real-merchant fixtures (per D-4).

---

## 10. What not to touch yet

This plan deliberately defers the following:

- **M10 cleanup** (legacy renderer deletion, legacy `calculate_28d_revenue` deletion). Per-vertical math knobs still in legacy code paths. **Reason:** plays not yet migrated to `plays/<play_id>/` (S8-T5 ships only wave 1 of ~14 plays). Full migration is a Sprint 12+ task.
- **Klaviyo / Shopify production integrations.** D-5 holds permanently for v1.
- **ML model code.** D-6 holds permanently for the planning horizon.
- **Apparel / food / home / wellness vertical support.** D-8 holds permanently.
- **Subsegment attribution (KI-29 Loop B+).** Decision parked until DS architect surfaces it before S10. If endorsed, the `outcome_observed.realized_breakdown` Optional field lands additively in S10-T1; if rejected, no work needed.
- **Klaviyo provider enum tightening (KI-7).** Requires `event_version=2`; defer to post-beta.
- **Subscription_nudge multiplier-vs-baseline-rate redesign (KI-24 Phase 4.2).** Defer to post-beta; KI-24 surface is honest via G-4.
- **Cross-merchant priors pooling.** Per D-2/D-8 footnote, this is Year-2 work and within `{beauty, supplements}` only.
- **AWS hosting / S3 storage backend.** Local-disk substrate is the planning-horizon scaffolding per founder 2026-05-10 note. Storage swap is a separate workstream when AWS lands.
- **Daily/weekly time-series emission for sparklines (KI-30 slot 1/6 sparkline upgrade).** Phase 1 ships pip-strip and bar comparisons; sparklines wait for designer-validated need.

---

## Closing notes

**Relevant file paths:**
- `/Users/atul.jena/Projects/Personal/beaconai/memory.md`
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md`
- `/Users/atul.jena/Projects/Personal/beaconai/ENGINE.md`
- `/Users/atul.jena/Projects/Personal/beaconai/CLAUDE.md`
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py` (the `_SUPPORTED` choke point; expanded across S6/S7)
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` (M7 contract; extended for 4-state abstain in S7-T4)
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py` (EB blend lands here in S8-T3)
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` (PlayCard contract additions in S8)
- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling_v2.py` (renderer surface for chip/strip/last-month section)
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml` (per-play priors; extended each sprint)
- `/Users/atul.jena/Projects/Personal/beaconai/config/replenishment_sizes.yaml` (supplements parser added S6-T2)
- `/Users/atul.jena/Projects/Personal/beaconai/src/memory/events.py` (`OutcomeObservedPayload` added S10-T1)
- `/Users/atul.jena/Projects/Personal/beaconai/src/memory/views.py` (`v_last_month_outcomes` added S10-T3)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html`

The plan is opinionated about three sequencing calls that the founder may push back on: (1) putting builders before the 4-state abstain (could be reversed if the trust-surface framing is more urgent than operational content), (2) splitting S8 across two re-pin commits (could be condensed to one if Swarm-team coordination is willing to absorb a double-shift), and (3) gating beta on the Phase 9-minimal outcome loop in S10 (could be moved to Sprint 12 post-beta if the founder wants a faster ship at the cost of "trust engine" framing weight). Each of those is a defensible tradeoff and the DS architect's design spec may surface reasons to flip one of them.

---

# Part III — Risk Mitigation Addendum

**Status:** Authoritative override over Parts I and II where specified. Read this first if you intend to execute against the plan.
**Date:** 2026-05-16
**Author:** ecommerce-ds-architect

This addendum responds to three founder-flagged risks in the plan as originally written:

1. **Risk 1** — priors are weak; the empirical-Bayes blend would launder fabricated anchors as rigorous math.
2. **Risk 2** — V2 is dragging legacy V2-era scaffolding it shouldn't. Cleanup must be a first-class workstream.
3. **Risk 3** — There is no UI yet. `briefing.html` is debug-only. The v2 deliverable is `engine_run.json`. All renderer-shape work is out of scope.

Where Part III conflicts with Part I or Part II, Part III wins.

---

## III-1. Priors Validation Strategy (addresses Risk 1)

### Audit findings — `config/priors.yaml`

Hard counts:

- **143 total priors entries** with a `source_class` field (14 plays × ~10 priors each).
- **73 entries** are `source_class: expert` (~51% of all priors).
- **11 entries** are `source_class: observational`.
- **0 entries** are `source_class: causal`.
- **51 entries** carry `source: internal_heuristic_unvalidated` as a provenance string (about 36% of the file).
- **8 entries** carry `source: internal_csv_observation_v1` (the only halfway-defensible provenance string in the file).

Per-play prior quality, ranked from defensible to fabricated:

| Play | Quality | Notes |
|---|---|---|
| `discount_hygiene` (margin_recovery_rate) | Half-defensible | Beauty `observational/internal_csv_v1`; supplements + mixed mirror that; `base_rate=1.00` / `incrementality=1.00` block is `internal_heuristic_unvalidated` placeholder, not used in sizing |
| `winback_21_45` | Half-defensible | Beauty base_rate `observational`; supplements + mixed base_rate `internal_csv_observation_v1`; ALL incrementality priors are `expert/internal_heuristic_unvalidated` |
| `empty_bottle` | Half-defensible | `base_rate` is `observational/internal_csv_v1`; `incrementality` is `expert/internal_heuristic_unvalidated` |
| `frequency_accelerator` | Mixed | Base rates `observational`; incrementality + frequency_lift all `expert/internal_heuristic_unvalidated` |
| `first_to_second_purchase` | Weak | Every prior `expert/internal_heuristic_unvalidated`; `second_purchase_lift` docstring admits "placeholder" |
| `bestseller_amplify` | Weak | Beauty priors `expert` (no source); everything else `internal_heuristic_unvalidated` |
| `subscription_nudge` | Weak | All `expert`; supplements + mixed `internal_heuristic_unvalidated`; `subscription_multiplier` carries "Phase 4.2 conflation deferred" note |
| `routine_builder` | Weak | All `expert`; supplements + mixed `internal_heuristic_unvalidated` |
| `aov_momentum` | Weak | All `expert`; explicit note "do not forecast lift from observed AOV drift" |
| `retention_mastery` | Fabricated | All `expert`; explicit note "remove assumed churn reduction" |
| `journey_optimization` | Fabricated | All `expert`; explicit note "rename or demote until onsite funnel data exists" |
| `category_expansion` | Fabricated | All `expert`; explicit note "remove fabricated stats" |
| `at_risk_repeat_buyer_rescue` | Placeholder | Both priors `internal_heuristic_unvalidated`; intentionally has no churn_reduction prior |

**Verdict on the 14 plays:**

- **4 plays have at least one half-defensible CSV-observational prior** (`discount_hygiene`, `winback_21_45`, `empty_bottle`, `frequency_accelerator`).
- **8 plays are entirely expert/heuristic.**
- **2 plays are placeholders.**

For the supplements vertical specifically, **every single non-base-rate prior is `internal_heuristic_unvalidated`**. Supplements has zero defensible incrementality, zero defensible bundle_value, zero defensible second_purchase_lift, zero defensible expansion_rate.

### Diagnosis — why this makes the empirical-Bayes blend dangerous as currently designed

The Part I §C blend formula is `posterior = (κ₀ μ₀ + k) / (κ₀ + n)` with `pseudo_N` chosen by `source_class`. The plan's `pseudo_N` table assigns:

- `causal` → 200
- `observational` → 50
- `expert` → 20
- `internal_heuristic_unvalidated` override → 5

This looks principled. It is not. Three failures:

**Failure 1 — `pseudo_N=20` for `expert` is a fiction.** The plan justifies 20 as "SME judgment / industry benchmark; modest weight." But the `expert` priors in this file are not SME-elicited; they are *one engineer's intuition committed to YAML on 2026-05-01*. There is no panel, no calibration exercise, no documented elicitation protocol. The honest weight is much closer to `internal_heuristic_unvalidated`'s pseudo_N=5, but the file labels them `expert` because of the "when uncertain, use expert" rule at priors.yaml line 41.

**Failure 2 — `pseudo_N=50` for `observational` confuses the n.** The 8 entries labeled `internal_csv_observation_v1` were derived from "internal CSV-derived priors with no randomization" — but with how many stores? The provenance string does not record n. If `internal_csv_observation_v1` came from 3 stores' worth of CSVs, treating it as `pseudo_N=50` overstates by an order of magnitude. The `pseudo_N` for an observational prior should be **traceable to actual underlying sample size**, not a default constant.

**Failure 3 — the blend creates false rigor on inputs the engine should refuse to compute.** The blend produces a posterior_p10/p50/p90 with an exact-looking confidence weight ("60/40 store"). The downstream consumer renders this as "Built on N store observations + industry prior (weight: 60/40 store)." But if the prior is a guess, the 40% prior weight is a **guess-weighted-by-a-guess**. The merchant sees calibrated math; the actual reasoning is "engineer typed `0.18` once."

This is materially worse than today's "we have no measured signal" abstain. Today's engine refuses to project; tomorrow's engine would project from a fabricated prior with a real-looking confidence band.

### Remediation methodology

The fix is **not** a 6-month literature review. The fix is to **stop laundering the source-class enum into pseudo_N weight** and replace it with a per-prior **`validation_status`** field that drives blend eligibility.

**Five-step methodology:**

**Step 1 — Add a `validation_status` field to every PriorEntry.** Closed enum:

```yaml
validation_status:
  - validated_external      # external citation; n traceable; auditable
  - validated_internal      # internal CSV study; n recorded; reproducible script
  - elicited_expert         # documented panel/protocol; ≥3 SMEs
  - heuristic_unvalidated   # engineer intuition; no external grounding
  - placeholder             # admittedly not a prior; never used in sizing
```

This is orthogonal to `source_class`. A `source_class=causal` prior can be `heuristic_unvalidated` (someone wrote "this is causal" but didn't cite); a `source_class=expert` prior can be `validated_external` (sourced from a published meta-analysis).

**Step 2 — Reset every existing entry to `heuristic_unvalidated` by default.** The current entries are unaudited. Treat them all as unvalidated until proven otherwise.

**Step 3 — Promote the 8 `internal_csv_observation_v1` entries to `validated_internal` ONLY IF the analysis script can be reproduced.** If no script exists in the repo, demote to `heuristic_unvalidated`. Add a `source_artifact:` field pointing to the script path or research memo path.

**Step 4 — Acquire 1–3 external benchmark sources to seed `validated_external` entries.** Lightest-weight reasonable path:

- **Klaviyo Industry Benchmarks** (free, annual): email base rates, open rates, attributed-revenue rates by industry. Maps to `winback_21_45.base_rate`, `bestseller_amplify.base_rate`, `first_to_second_purchase.base_rate`. Observational, not causal; upper bound for "stores doing email at all."
- **Shopify Plus Benchmarks Report** (free): AOV ranges, repeat rate distributions by category. Maps to AOV-distribution priors for `aov_lift_via_threshold_bundle`.
- **DTC Power Index / Repeat Customer Insights / Lifetimely DTC benchmarks**: repeat-purchase curves for beauty and supplements. Maps to `winback_21_45.orders_per_customer`, `frequency_accelerator.frequency_lift`.

**Critical distinction:** These are observational benchmarks, **NOT causal lift**. A Klaviyo benchmark like "30-day winback emails see 8% reactivation in beauty" is a **base rate observed under treatment**, NOT incremental lift. It conflates would-have-returned-anyway with reactivated-by-email.

- Correct use: **as priors on observable rates** (base_rate priors), NOT on incrementality.
- For incrementality priors (the harder ones), there is no shortcut. The merchant's own outcomes through Phase 9 are the only path to non-heuristic incrementality estimates. Until then, incrementality priors stay `heuristic_unvalidated` with `pseudo_N` so low they don't contribute.

**Step 5 — Cold-start posture: refuse to blend on `heuristic_unvalidated` priors.** This is the key behavioral change. When prior is `heuristic_unvalidated`:

- Sizing **does not blend**. It uses the observed-only path (if Tier-B with observed effect) or **abstains from a revenue range entirely** (if Tier-C).
- The PlayCard renders without a posterior; `blend_provenance = None`.
- The card still surfaces — audience + AOV + mechanism + supporting metric — but no projected dollars.

This generalizes today's rule (`source_class != causal → suppressed`) into: `validation_status in {heuristic_unvalidated, placeholder} → suppress`.

### Concrete additions to the plan

**New sprint tickets (insert as S7.5, between S7 and S8):**

- **S7.5-T1 — Priors validation audit + `validation_status` field added to `PriorEntry`.** Walk every entry in `priors.yaml`, demote to `heuristic_unvalidated` unless an `source_artifact` exists. ~2 days.
- **S7.5-T2 — External-benchmark integration: Klaviyo + Shopify + DTC index.** Source 1 benchmark per play where one exists. Document each in `config/priors_sources/<play_id>.md` with publication, date, sample composition, verbatim numbers. Promote affected priors to `validated_external`. ~5 days.
- **S7.5-T3 — Cold-start blend refusal in `sizing.py`.** Extend the `source_class != causal` suppression to `validation_status in {heuristic_unvalidated, placeholder}`. Add the new abstain mode `SOFT_PRIOR_UNVALIDATED`. ~2 days.

**New `pseudo_N` policy:**

| validation_status | pseudo_N | Rationale |
|---|---|---|
| `validated_external` | 30 | Real external sample; moderate weight (n in benchmark itself is opaque) |
| `validated_internal` | 15 | Reproducible internal analysis on a small set of stores |
| `elicited_expert` | 10 | Documented panel; weak but documented |
| `heuristic_unvalidated` | — | **Blend refused; revenue_range suppressed** |
| `placeholder` | — | Never used in sizing |

These are lower than Part I §C's values. The plan as written assigns `pseudo_N=20` to entries that should be refused entirely; bringing the table down signals honest weight relative to a store's own data, which on a 1000-customer audience overwhelms any of these priors within two months.

**New `priors.yaml` schema fields per entry:**

```yaml
- name: base_rate
  value: 0.08
  range_p10: 0.04
  range_p90: 0.14
  source_class: observational           # KEEP (descriptive)
  validation_status: validated_internal  # NEW (load-bearing)
  source_artifact: "research/winback_base_rate_v1.md"  # NEW
  effective_n: 1200                      # NEW (the n underlying validated_* entries)
  applies_to: { vertical: beauty }
```

`effective_n` overrides `pseudo_N` when present. Closes Failure 2 above.

**Rule for refusing to render a Tier-C card on a low-quality prior:**

A Tier-C card with `validation_status in {heuristic_unvalidated, placeholder}` for its `base_rate` prior:
- Still emits in `considered[]` (audience identified; reason: `PRIOR_UNVALIDATED`).
- Does **not** emit in `recommendations[]` or `recommended_experiments[]`.
- This tightens the A4 Recommended Experiment allowlist mechanically: `discount_hygiene` survives (has `validated_internal` margin_recovery_rate); `bestseller_amplify` does NOT survive until its base_rate prior is validated.

### Honest abstain fallback

If, by S10 / beta gate, no external benchmark sourcing has happened and every supplements prior is still `heuristic_unvalidated`:

**Engine behavior on a supplements brand:**

- Tier-B builders may still fire (they use store-observed data, not priors). `replenishment_due` on supplements with adequate parser coverage CAN ship a Recommended Now card based on the store's own cohort metric.
- Tier-C plays uniformly fall through to Considered with reason `PRIOR_UNVALIDATED`.
- Revenue ranges on Tier-B cards are observed-only (no blend), with wide uncertainty bands derived from the supporting metric's own standard error.
- The `abstain_mode` for runs with zero firing Tier-B builders becomes a new sub-state: `SOFT_PRIOR_UNVALIDATED`. Distinct from `SOFT_AWAITING_MEASUREMENT` (which means "we have priors but no store-specific evidence yet").

Materially different from today's ABSTAIN in three ways:

1. **Today**: ABSTAIN_SOFT is a binary — engine has nothing to say.
2. **With Tier-B + this addendum**: the engine ships store-observed Recommended Now cards on Tier-B builders even with no validated priors. The merchant gets something to send.
3. **Today**: ABSTAIN copy is generic.
4. **With this addendum**: the typed `abstain_mode` names exactly which priors aren't validated; renderer (someday) tells the merchant their first Phase 9 outcome unlocks them.

The fallback is honest because **the engine produces no dollar projection it cannot defend**, while still producing audience-shaped recommendations a merchant can execute.

---

## III-2. V2 Cleanup Workstream (addresses Risk 2)

The current plan preserves a large amount of v1 / Phase 5 / Phase 6A / Phase 6B scaffolding "for migration." Most of it is upgrade-replaceable.

### Audit findings — typed list of v2 cruft

Format: file/symbol — current purpose — v2 status — recommended sprint boundary.

**`src/measurement_builder.py`**

- `_SUPPORTED` dict (line 108) — single-entry registry of Tier-B builders, the `first_to_second_purchase` proxy. **FOLD-INTO** Play Library `plays/<play_id>/measurement.py`. **Sprint:** S8-T5; delete the dict at S8 close.
- `_SupportingSignal` dataclass — local schema for the single supported play. **REMOVE** once each play's `measurement.py` owns its own builder signature. **Sprint:** S8-T5.
- The `returning_customer_share` `_SUPPORTED` entry itself — explicitly admitted as a state-statistic proxy (lines 122-128). **REMOVE** at S7-T2 when `cohort_journey_first_to_second` ships. Do not retain as fallback.

**`src/decide.py`**

- `RECOMMENDED_EXPERIMENT_ALLOWLIST = frozenset({"discount_hygiene", "bestseller_amplify"})` (line 118) — hard-coded list. **FOLD-INTO** per-play `eligibility.py::is_experiment_eligible()`. **Sprint:** S8-T5. The frozenset can stay as a build-time-computed aggregate; what gets removed is the hand-edited literal.
- `_S3_FANOUT_REASON_MAP` (line 436) — 5-key short-code-to-ReasonCode map. **KEEP** — this is the typed reason-code surface the substrate consumes; the smarter-abstain machine in §G extends it. Not cruft.
- `PHASE5_V2_SUPPRESS_PLAY_IDS` (line ~1665 export) — Phase 5 suppression list. **REMOVE** at S7 close when Play Library carries per-play `is_active_v2: bool`. **Sprint:** S8.
- `_PRELIM_REASON_MAP` — legacy mapping. **FOLD-INTO** the unified reason-code map. **Sprint:** S7-T4 (4-state abstain refactor absorbs this).

**`src/action_engine.py`**

- `_compute_candidates` (line 3056) — legacy candidate computation; lines 3084-3095 lazy-import `_TARGETING_RECLASSIFY` defensively. **DEFER-REMOVE**. M10 work; stays until per-vertical math knobs are re-homed.
- `_TARGETING_RECLASSIFY` frozenset import + fallback at line 3086 — defensive lazy import. **FOLD-INTO** Play Library `eligibility.py::is_targeting_structural()`. **Sprint:** S8-T5.
- The defensive `frozenset()` fallback when `evidence` import fails — pure scar tissue. **REMOVE** at S8-T5.

**`src/evidence.py`**

- `TARGETING_RECLASSIFY_PLAYS` frozenset — defensive list. **KEEP for now, FOLD-INTO** Play Library at S8-T5. Load-bearing safety net for B-5 Berkson invariant until then.
- Module-level `EVIDENCE_CLASSES` enum — **KEEP**. Schema; not cruft.

**`src/cadence_coherence.py`** (entire module)

S5-T3 advisory flag for supplements 28d window incoherence. **DEFER-REMOVE.** The module is small (118 lines), pure, and tested. Once `replenishment_due` ships (S6-T2), the supplements path produces Recommended Now cards based on actual reorder gap — and `repeat_rate_within_window` Watching row suppression becomes mechanically redundant. But:

- The cadence-coherence flag is also the signal for the new `SOFT_CADENCE_OUTSIDE_WINDOW` abstain sub-mode in §G.
- Keep the module; the *advisory* role gets absorbed into the abstain machine; the flag itself stays.

**Sprint:** Module stays through beta. Revisit at M10.

**`src/state_of_store.py`**

- Whole module — Observation builder. **KEEP.** The `prior:` slot now correctly populated post-S5-T1 (KI-26 fix at line 122) is the typed engine_run.json surface; load-bearing for OutcomeRetrospective in §D.
- HTML rendering pieces are NOT in this module. Good.

**`src/storytelling_v2.py`**

This is the load-bearing one for Risk 3.

- Entire module — V2 HTML renderer. **REMOVE FROM v2 SCOPE.** Per the founder reframe, `briefing.html` is debug-only; v2 deliverable is `engine_run.json`. The module stays in the codebase as a local-dev debug renderer, but **no new code lands in it** as part of S6–S11. Specifically:
  - S7-T4 spec calls for `storytelling_v2.py` updates to render new abstain copy → **delete from plan**. Engine emits typed `abstain_mode`; the local debug renderer can pick it up incidentally, but the spec should not direct work here.
  - S8-T1 spec calls for chip rendering in `storytelling_v2.py` → **delete from plan**. Typed `evidence_source` field on PlayCard is the contract.
  - S8-T2 spec calls for sensitivity strip render → **delete**. Typed `sensitivity` field is the contract.
  - S9-T1 — sensitivity strip + provenance chip CSS polish → **delete the entire ticket**.
  - S10-T3 — "last month's outcome" renderer section → **reduce** to "engine emits `OutcomeRetrospective` typed block on engine_run.json; renderer concern is out-of-scope for v2." The substrate read view and event-payload work survives; the HTML rendering does not.

**Sprint:** Module stays as debug-only artifact; do not refactor. Remove HTML renderer touches from all S6–S11 ticket scopes.

**`src/storytelling.py`** (legacy v1 renderer)

- ~24 functions building v1 briefing narrative. **REMOVE** at M10. Not v2-relevant.

**`src/briefing.py`**

- Thin orchestrator routing between legacy and `storytelling_v2.render_engine_run`. **REMOVE** at M10. The route check `use_v2=_use_v2_output` at `main.py:1573` becomes a no-op when both renderers are removed; main.py just writes `engine_run.json` and exits.

**`src/play_registry.py`**

- `PlayDef` dataclass (line 56) — v2-era typed schema for a play. **KEEP**. Survives the refactor as the Play Library's per-play file format.
- `PLAYS` dict + `get` / `all_play_ids` helpers — **FOLD-INTO** Play Library `_registry.py`. Aggregate dict is still exposed (now built from per-play imports), but the in-module hand-coded entries move to play directories. **Sprint:** S8-T5 wave 1; full collapse at M10.
- `_assert_display_name_uniqueness` (line 482) — **KEEP**. Load-time invariant.

**`src/priors_loader.py`**

- `PriorEntry` dataclass + loader — **KEEP** but extend per III-1 (add `validation_status`, `source_artifact`, `effective_n`).
- Dual YAML form (list and dict) for `_extract_play_block` — **KEEP** through S8-T5; after all plays migrate, loader scans `plays/*/priors.yaml` and dual form becomes single-form-per-file matter. **Defer collapse to S8 close or later.**
- `resolve_mixed_prior` (G-3) — **KEEP**. Load-bearing semantic for D-8.

**`src/audience_builders.py`**

- ~13 audience-builder functions. **FOLD-INTO** Play Library per-play `audience.py`. **Sprint:** S8-T5 wave 1 migrates 3 plays; post-beta migrates the rest. Legacy module stays until all plays migrated.

**`src/engine_run_adapter.py`**

- `build_engine_run_from_legacy` and `legacy_actions_from_engine_run` — bidirectional bridge between legacy `actions_bundle` and typed `EngineRun`. **DEFER-REMOVE** until legacy candidate computation in `action_engine.py::_compute_candidates` is itself removed. M10 work. Currently load-bearing for every V2 path.

**`src/memory/*`**

- All modules — Sprint 2 substrate. **KEEP** entirely. Schema frozen, well-tested, audit clean.

**`tools/*`**

- `inspect_memory.py`, `export_store.py`, `import_campaign_sent.py` — **KEEP**. Substrate operator tooling, single-writer-discipline correct.

### Cleanup tickets mapped to sprints

| Sprint | Cleanup ticket | Scope |
|---|---|---|
| **S6** | S6-CL1 | Remove `_SUPPORTED` `returning_customer_share` entry (or move to deprecation alias) as S7-T2 prep |
| **S7** | S7-CL1 | Bundle `_PRELIM_REASON_MAP` fold into unified reason-code map inside S7-T4 |
| **S7** | S7-CL2 | Remove `briefing.html` / renderer touches from all S7 ticket scopes (per III-3). Scope-removal from plan, not code |
| **S8** | S8-CL1 | Play Library wave 1 (3 plays). Folds `_SUPPORTED`, `RECOMMENDED_EXPERIMENT_ALLOWLIST`, `TARGETING_RECLASSIFY`, per-play priors.yaml block into per-play dirs. This is S8-T5 renamed |
| **S8** | S8-CL2 | Remove `PHASE5_V2_SUPPRESS_PLAY_IDS`; replace with `is_active_v2` field on PlayDef |
| **S8** | S8-CL3 | Delete `storytelling_v2.py` renderer touches from S8-T1 / S8-T2 ticket scopes (per III-3) |
| **S9** | S9-CL1 | Replace legacy `_compute_candidates` lazy-import-with-fallback (action_engine.py:3084-3095) with direct registry call once Play Library is source of truth |
| **S10** | S10-CL1 | Delete S10-T3 renderer surface from plan; reduce to typed `OutcomeRetrospective` emission only (per III-3) |
| **S11** | S11-CL1 | Beta-launch cleanup sweep: confirm no v1 module is required for the engine_run.json path. Catalog remaining M10 deletions |
| **M10 (post-S11)** | Bulk-delete | Remove `storytelling.py`, `briefing.py`, `_compute_candidates` post-Play-Library-full-migration, `engine_run_adapter.py` once no legacy path exists. **Not before per-vertical math knobs are re-homed in priors.yaml.** |

### Over-engineered backwards-compat to delete from Part II

1. **S7-T4 deprecation alias for `ABSTAIN_SOFT`.** Plan says "Backward-compat: `DecisionState.ABSTAIN_SOFT` retained as a deprecated alias mapping to `SOFT_BELOW_FLOOR` for one sprint." **Per Risk 3, there is no downstream renderer consumer that needs the alias.** **Remove the alias; do a clean enum migration.**

2. **S8-T5 backwards-compat clause** ("Beauty pinned fixture and supplements pinned fixture MUST stay byte-identical through migration"). **Per Risk 3, fixtures are testing artifacts, not Swarm contracts.** Byte-identity is a useful regression test, but it's not a Swarm-coordination concern. **Keep the fixture stability discipline as a CI-only check; stop framing as "Swarm coordination."**

3. **S8-T1 + S8-T2 fixture re-pins** (Beauty + supplements re-pinned for chip render, then again for sensitivity render). **Per Risk 3, no engine_run.json changes are required to render a chip.** **Remove the re-pin requirement.** Re-pins only happen when `engine_run.json` content actually changes.

4. **S9-T1 entire ticket** ("Sensitivity strip renderer + provenance chip"). **Per Risk 3, this is renderer work. Delete the ticket.** The sensitivity_strip typed field on PlayCard is the v2 deliverable.

5. **S10-T3 entire ticket as currently scoped** ("Renderer surface for 'last month's outcome'"). **Per Risk 3, reduce to: emit `OutcomeRetrospective` typed block on engine_run.json**. No `briefing.html` work, no Beauty re-pin tied to renderer change, no `_render_watching_section_for_run` extension.

6. **Phase 6B Stop-Coding Line framing throughout the plan.** **Per Risk 3, this framing is obsolete.** There is no Swarm team yet. The "discipline" of engine-emits-typed / renderer-renders is still correct, but the framing should be **"engine produces a typed JSON contract; renderer is a future workstream"** — not "Swarm rendering is the go-to-market risk."

### M-invariants protecting cleanup

1. **M-CL1 — Play Library single-source-of-truth assertion.** A play exists in *exactly one* registry. Load-time assertion.
2. **M-CL2 — `evidence_class == "targeting" ⇒ measurement is None`** (existing M4b invariant). Keep through cleanup.
3. **M-CL3 — No renderer call from `src/main.py::run` past `decide()` returns.** HTML render in main.py:1574 is the *last* thing after `engine_run.json` is written. Engine logic never depends on renderer behavior.
4. **M-CL4 — `engine_run.json` schema is the v2 contract.** Pickled v1 `engine_run.json` from M0 fixture must roundtrip through every successor schema version.
5. **M-CL5 — `briefing.html` byte-identity is NOT a load-bearing test.** `engine_run.json` sha256 is the contract; `briefing.html` sha256 becomes informational.

---

## III-3. Engine-Only Scope Restatement (addresses Risk 3)

### Restated v2 deliverable

The v2 engine produces a single typed artifact: **`data/<store_id>/runs/<run_id>.json`** (and its byte-identical mirror at `receipts/engine_run.json`). This JSON is the **v2 contract**. Anything that some future UI renders is downstream of this contract and is **not v2 scope**.

The JSON contains:

- `EngineRun.recommendations[]` — Recommended Now PlayCards.
- `EngineRun.recommended_experiments[]` — Tier-C experiment-eligible PlayCards.
- `EngineRun.considered[]` — RejectedPlays with typed `reason_code` and `held_reason_detail`.
- `EngineRun.watching[]` — WatchedSignals.
- `EngineRun.state_of_store.observations[]` — typed Observation records (`current`, `prior`, `delta_pct`, `classification`).
- `EngineRun.decision_state` — PUBLISH / ABSTAIN_HARD / `abstain_mode` (per §G 4-state, now 5 with `SOFT_PRIOR_UNVALIDATED`).
- `EngineRun.data_quality_flags[]` — typed DataQualityFlag enum.
- `EngineRun.opportunity_context` — typed audience/AOV/addressable_value block.
- `EngineRun.outcome_retrospective` (new, §D) — typed "what we said last month, what was realized."
- Per-PlayCard: `evidence_class`, `evidence_source` (chip), `signal_kind`, `audience`, `measurement` (when applicable), `revenue_range` (with `suppressed` flag and `drivers[]`), `sensitivity_strip`, `provenance`, `blend_provenance`, `would_be_measured_by`, `mechanism`.

That is the contract.

### What is NOT in the contract

- Rendered HTML strings.
- Color hex codes for chips.
- Slot-layout instructions for cards.
- Hover tooltip text.
- Merchant-facing copy templates beyond the typed `mechanism` and `recommendation_text` fields.
- CSS, JavaScript, or any rendering hint.
- Card ordering decisions made at render time (engine ranks; renderer respects).
- "What we'd send" prose composition (engine emits typed mechanism string; renderer composes sentence).

### JSON contract surface — what stays in v2

| Item | Category | v2 Status |
|---|---|---|
| `evidence_source` chip enum on PlayCard | engine-shape JSON field | KEEP |
| `signal_kind` enum on PlayCard | engine-shape JSON field | KEEP |
| `sensitivity_strip` typed sub-object | engine-shape JSON field | KEEP — engine emits the 5 scalars |
| `provenance` typed sub-object | engine-shape JSON field | KEEP |
| `blend_provenance` typed sub-object on Measurement | engine-shape JSON field | KEEP |
| `outcome_retrospective` typed block on EngineRun | engine-shape JSON field | KEEP |
| `abstain_mode` enum on EngineRun | engine-shape JSON field | KEEP |
| "Chip color: green/amber/blue/grey" | renderer-shape | REMOVE from v2 plan |
| "Hover tooltip on the tier chip" | renderer-shape | REMOVE |
| "5 small bars in the EVIDENCE band" | renderer-shape | REMOVE |
| "'Built on N store observations + industry prior' text" | in-between | KEEP typed fields; REMOVE the formatted string |
| "Show your work disclosure (collapsed by default)" | renderer-shape | REMOVE |
| "State-of-store ribbon top of briefing" | renderer-shape | REMOVE; engine emits OutcomeRetrospective block |
| "Replaces the dominant-gate-keyed ABSTAIN_SOFT copy" | renderer-shape | REMOVE; engine emits abstain_mode |
| "Surface copy template: 'Last month we recommended...'" | renderer-shape | REMOVE from v2; engine emits typed fields |
| "Renderer chip" sections (§A Tier A/D/P/O) | renderer-shape | REMOVE from v2 |

### Renderer-shape items to strip from the plan

**Part I:**

- §A Tier A/D/P/O "Renderer chip: (chip color: ...)" annotations → delete chip color.
- §C "Blend ratio surfacing on PlayCard" — keep typed `BlendProvenance` dataclass; delete the "Swarm renderer surfaces it as..." sentence.
- §D Renderer Surface — keep typed block; rewrite the sentence to "Engine emits typed `OutcomeRetrospective` block on `engine_run.json`; downstream renderers consume it."
- §F-1 Sensitivity Strip "Swarm renders as five small bars..." → delete; rendering concern only.
- §F-1 "The collapse of all five toward zero is a visual cue..." → delete; renderer concern.
- §H "Swarm consumer mapping" entire table — delete or move to `docs/future_renderer_contract.md` and mark "not v2 scope."
- §H "Stop-Coding Line discipline" — rewrite: "v2 engine emits typed JSON; renderer is a future workstream. `briefing.html` remains as a local-dev debug renderer, not a contract surface."
- §I R-2 last sentence ("If the renderer team is not staffed in parallel...") — delete. There is no renderer team.

**Part II:**

- Executive summary "Stop-Coding Line is real" risk — rewrite to remove "Swarm renderer" framing.
- §1 sprint table "Beta status" rationales referring to "trust-surface contract" — recharacterize as "JSON contract surface."
- §2 S7-T4 "renderer mapping for each soft state to merchant-visible copy" — strip.
- §2 S8-T1 "HTML briefing renders a `data-evidence-source` attribute on each card" — strip.
- §2 S8-T1 "render the chip in the EVIDENCE band per KI-30 slot spec" — strip.
- §2 S8-T2 "renderer surface for the sensitivity strip per KI-30 slot 4/5" — strip.
- §2 S9 — reduce to S9-T2 (Replay CLI), S9-T3 (Backtest CLI), S9-T4 (Sensitivity audit CLI). **Delete S9-T1 entirely.**
- §2 S10-T3 — reduce to "emit `OutcomeRetrospective` typed block on engine_run.json; v_last_month_outcomes read view added; no HTML rendering."
- §4 Fixture re-pin schedule — delete rows whose re-pin reason is "renderer surface change."
- §9 Beta-launch checklist:
  - "Every PlayCard in pinned fixtures carries: typed fields" — KEEP (JSON-shape assertion).
  - "No forbidden tokens in any pinned briefing.html" — KEEP as informational test only. Blocking criterion is `engine_run.json`.

### Reduced sprint scope where applicable

**S7-T4 (4-state abstain):** Engine emits `abstain_mode` typed enum. No `storytelling_v2.py` touch. No fixture re-pin unless `engine_run.json` actually changes.

**S8-T1 (Evidence Tier chip):** Add typed fields. Builders populate them. No HTML. Fixture re-pin only on `engine_run.json` content change.

**S8-T2 (Sensitivity + Provenance):** Add typed sub-objects. Compute 5 sensitivity scalars in `src/sizing.py`. No HTML. Fixture re-pin only on `engine_run.json` content change.

**S9 (Trust-math tooling):** 3 tickets — replay CLI, backtest CLI, sensitivity audit CLI (operator tools). **S9-T1 deleted. Duration drops from 1.5 weeks to ~1 week.**

**S10-T3 (Last-month-outcome):** Emit `outcome_retrospective: Optional[OutcomeRetrospective]` typed block on `EngineRun`, populated from `v_calibration_state` + `v_open_recommendations`. Add `v_last_month_outcomes` read view (engine-internal). No HTML.

**S11 (Private beta):** Founder reviews `engine_run.json` content for at least one real-merchant fixture. Copy + slate are not v2 deliverables.

### §F Trust-Math Tooling restated

**F-1 Sensitivity Strip** — **Engine output (JSON field).** Not a renderer surface. The 5 scalars are computed in `src/sizing.py` and serialized on `PlayCard.sensitivity_strip`. No renderer work in v2.

**F-2 Replay CLI** (`tools/replay_at_date.py`) — **Operator/founder tool.** Reads CSV, runs the engine end-to-end with `--at-date` cutoff, writes `replay_engine_run.json`. No HTML.

**F-3 Backtest CLI** (`tools/backtest.py`) — **Operator/founder tool.** Sliding-window replay + realized-vs-predicted calibration. **Remove the HTML calibration plot from v2 scope.** Emit CSV of records. Plotting is analysis-tooling outside v2.

In all three cases, the deliverable is a typed data artifact (JSON field, JSON file, CSV file). None are renderer concerns.

---

## III-4. Suggested Edits to Existing Plan Sections

Concrete edits to merge into `ARCHITECTURE_PLAN.md`:

**Executive Summary**

- "What This Plan Delivers" — drop "Recommended Now on every beta brand, every month." Replace with "A typed `engine_run.json` per run that produces Recommended Now cards when defensible Tier-A or Tier-B signal exists, and an honest sub-typed abstain otherwise."
- "What This Plan Does NOT Do" — add: "**No HTML renderer work.** `briefing.html` is debug-only; the engine's v2 deliverable is `engine_run.json`. Future renderer is out of scope."
- "The Two Biggest Risks" — replace "Stop-Coding Line is real / renderer team go-to-market risk" with "Priors validation is unscoped (Risk 1 mitigation in Part III)." The renderer/Swarm framing is obsolete.

**Part I §A (Four Evidence Tiers)** — Delete every "chip color: green/amber/blue/grey" annotation.

**Part I §C (Empirical-Bayes Blend)**

- Rewrite `pseudo_N` policy table per III-1: source weight from `validation_status`, not `source_class`. Lower weights.
- Add `validation_status` field to `PriorEntry` schema.
- Add cold-start refusal rule: `validation_status in {heuristic_unvalidated, placeholder} → blend refused, revenue_range suppressed`.
- Delete the "Swarm renderer surfaces it as..." sentence; keep typed `BlendProvenance` dataclass.

**Part I §D (Phase 9-Minimal)**

- Rewrite "Renderer surface" subsection: engine emits typed `OutcomeRetrospective` block; renderer out of scope for v2.
- Delete the "Surface copy template: 'Last month we recommended...'" sentence.

**Part I §F (Trust-Math Tooling)**

- Recategorize all three per III-3: F-1 is engine JSON output, F-2/F-3 are operator CLIs. Delete F-3's `calibration.html` plot output; emit CSV only.

**Part I §G (Smarter Abstain)**

- Add a fifth state: `SOFT_PRIOR_UNVALIDATED` (per III-1 honest-abstain fallback).
- Delete the "Merchant copy template" column in the state table.

**Part I §H (Trust Surface)**

- Delete "Swarm consumer mapping" table outright or move to `docs/future_renderer_contract.md` and mark "not v2 scope."
- Rewrite "Stop-Coding Line discipline" paragraph: "v2 engine emits typed JSON; renderer is a future workstream."

**Part I §I (Risk Register)**

- R-2 mitigation — replace with III-1 priors validation strategy. Delete R-2's "renderer team go-to-market risk" framing.

**Part II §1 (Executive sequencing summary)**

- Update sprint table "Beta status" rationales: "trust-surface contract" → "JSON contract surface."
- "Minimum slice that earns 'trust engine' framing" — remove "S10 outcome loop in its read-only form." Engine-only minimum is "S10-T1 outcome importer + S10-T2 calibration writer + the typed `OutcomeRetrospective` block."

**Part II §2 (Per-sprint plan)**

- **S6**: no changes.
- **S7**:
  - Delete the "Backward-compat: `DecisionState.ABSTAIN_SOFT` retained as a deprecated alias" clause from S7-T4.
  - Delete the "renderer mapping for each soft state to merchant-visible copy" clause.
  - Add S7-CL2 cleanup ticket.
- **S7.5 (NEW SPRINT, inserted)**: Priors validation. 3 tickets (audit, external-benchmark integration, blend-refusal in sizing). ~1.5 weeks.
- **S8**:
  - S8-T1: strip HTML rendering, keep typed field additions. Re-pin fixture only on `engine_run.json` change.
  - S8-T2: strip HTML rendering, keep typed field additions.
  - S8-T4 (EB blend flag flip): change blend trigger from `source_class != causal` to `validation_status in {validated_external, validated_internal, elicited_expert}`.
  - S8-T5: keep as-is (Play Library wave 1 is genuine engine refactor).
- **S9**: delete S9-T1 entirely. S9-T2/T3/T4 are operator CLIs. Drop S9-T3's HTML calibration plot, replace with CSV.
- **S10**:
  - S10-T3: reduce to "emit typed `OutcomeRetrospective` block + add `v_last_month_outcomes` view." Delete HTML rendering.
- **S11**: founder reviews `engine_run.json`, not briefing.html copy.

**Part II §3 (Schema migrations summary)**

- Add row: `PriorEntry.validation_status` (new field; closed enum) | Additive to YAML schema | `src/priors_loader.py`.
- Add row: `PriorEntry.source_artifact` (new field; Optional[str]) | Additive | `src/priors_loader.py`.
- Add row: `PriorEntry.effective_n` (new field; Optional[int]) | Additive | `src/priors_loader.py`.
- Add row: `AbstainMode.SOFT_PRIOR_UNVALIDATED` (new enum value) | Additive | `src/decide.py`.

**Part II §4 (Fixture re-pin schedule)**

- Delete every row whose re-pin reason is "renderer surface change." Keep rows whose re-pin reason is "engine_run.json content change."

**Part II §6 (Feature flag inventory)**

- Delete `ENGINE_V2_SENSITIVITY_RENDER` (renderer flag; not v2).
- Add `ENGINE_V2_PRIORS_VALIDATION` (flag-gated rollout of validation_status-driven blend refusal). Default OFF, flipped ON in S7.5.

**Part II §9 (Beta-launch checklist)**

- Demote all `briefing.html`-content items to informational.
- Promote all `engine_run.json`-content items to blocking.
- Add: "All priors in `config/priors.yaml` carry a `validation_status` field. No prior used in sizing has `validation_status == heuristic_unvalidated`."
- Add: "Founder has personally reviewed at least one real-merchant `engine_run.json` and signed off on the typed contract."


---

# Part IV — Store Profile Layer (Sprint 6.5)

**Status:** Founder-accepted 2026-05-17. Authoritative over Parts I and II where hardcoded floors / windows / seasonality assumptions exist.
**Date:** 2026-05-17
**Author:** ecommerce-ds-architect (full proposal: [agent_outputs/ds-architect-store-profile-layer-proposal.md](agent_outputs/ds-architect-store-profile-layer-proposal.md))
**IM ticket plan:** [agent_outputs/implementation-manager-s6_5-store-profile-layer-plan.md](agent_outputs/implementation-manager-s6_5-store-profile-layer-plan.md) (drafted in parallel with this section).

This part documents a foundational architectural change. The engine pipeline gains a new **PROFILE** step at the front that runs once per engine_run, produces a typed `StoreProfile` artifact, and parameterizes every downstream gate. It replaces hardcoded floors / windows / seasonality assumptions distributed across Parts I §B builders, Part II per-sprint specs, and Part III gates.

---

## IV-1. Why Part IV exists

S6-T1 + T1.5 shipped successfully, but the synthetic Beauty fixture failed the audience floor (356 customers < 500). This is not a synthetic-data artifact — it is the engine telling us it would abstain on real $1-3M brands. Two structural problems surfaced:

1. **The V2 engine dropped the legacy `BUSINESS_STAGE` knob.** Audience floor (500) and materiality floor ($4,500) are hardcoded "mature-store" defaults that filter out $1-3M brands wholesale.
2. **L28/L56 windows are fine for beauty/skincare and beauty/cosmetics (30-45d reorder cadence) but structurally too short for supplements (60-90d cadence).** Supplements/protein and supplements/multivitamin need L60 primary windows with {L56, L90, L180} agreement; nootropics need L90 primary. The engine does not currently know to vary window selection per sub-vertical.

Additionally, three latent issues compound these:

3. **Within-vertical heterogeneity is invisible.** Not all beauty stores reorder at the same cadence; skincare ≠ cosmetics ≠ haircare. Supplements has even more variance: protein powder vs multivitamin vs nootropics differ in cadence, AOV, and seasonality.
4. **Seasonality has no engine awareness.** January-resolution supplement spike, BFCM beauty tail, Mother's Day, back-to-school — invisible to L28/L56 metrics. Risk of either false-positive recommendations (BFCM signal misread as real trend) or false-negative ABSTAINs (January lull misread as retention problem).
5. **The legacy engine had this complexity** via `BUSINESS_STAGE`. V2 lost it in the refactor.

Band-aid fixes (per-play stage-aware floors, standalone seasonality calendar) would scatter these concerns across every Tier-B builder. A foundational fix consolidates them in a single typed artifact consumed by everything downstream.

## IV-2. The architectural shape

### New pipeline step

```
  PROFILE   →   AUDIENCE   →   MEASUREMENT   →   SIZING   →   DECIDE
  (NEW)         (existing)     (existing)        (existing)   (existing)
```

PROFILE runs once per `engine_run`, before any candidate detection. Its output is a typed `StoreProfile` dataclass persisted on `engine_run.json` under a top-level `store_profile` slot (additive within `event_version=1`).

### Schema (frozen at S6.5)

```python
@dataclass(frozen=True)
class StoreProfile:
    store_id: str
    profile_version: int
    profiled_at: datetime
    taxonomy: Taxonomy                   # vertical + subvertical + confidence
    business_stage: BusinessStage        # STARTUP|GROWTH|MATURE|ENTERPRISE
    business_model: BusinessModel        # ONE_TIME_LED|SUBSCRIPTION_LED|HYBRID
    cadence: CadenceBaseline             # per-SKU-class median reorder gap
    seasonality: SeasonalityContext      # active window + calendar entries
    data_depth: DataDepth                # history_days, n_customers, n_orders
    gate_calibration: GateCalibration    # all per-(vertical, subvertical, stage) floors
    measurement: MeasurementContext      # primary_window + agreement_windows
    provenance: ProfileProvenance        # which rules fired, with what inputs
```

The dataclass is **frozen + provenance-bearing**. Every recommendation downstream cites the profile fields it consumed in its `drivers[]` block — so when a merchant asks "why did you assume my floor is 300?", the answer is in the JSON.

### Downstream consumption

| Downstream consumer | Reads from profile |
|---|---|
| Audience floors | `profile.gate_calibration.audience_floor_by_play_id` |
| Materiality floors | `profile.gate_calibration.materiality_floor_usd` |
| Primary measurement window | `profile.measurement.primary_window` |
| Multi-window agreement set | `profile.measurement.agreement_windows` |
| Seasonality annotations | `profile.seasonality.active_context` |
| Prior selection (sub-vertical) | `profile.taxonomy.subvertical` |
| Bayesian blend `pseudo_n` defaults | `profile.calibration.pseudo_n_default` |
| ModelFitStatus thresholds (S10+) | `profile.data_depth.model_fit_thresholds` |

## IV-3. The eight profile dimensions

Each dimension is descriptive (classifies the store from CSV), not predictive. No ML, no forecasting. Pure heuristics + statistical summaries.

| Dimension | Source | Output | Confidence indicator |
|---|---|---|---|
| **Vertical** (existing, formalized) | Revenue-weighted product-title token classifier; `VERTICAL_MODE` env var override | `{beauty, supplements, mixed, other_refused}` | HIGH if >70% revenue-weighted match |
| **Sub-vertical** (NEW) | Token classifier per vertical (`config/subvertical_taxonomy.yaml`) | beauty: `{skincare, cosmetics, haircare, personal_care, mixed_beauty}`; supplements: `{protein, multivitamin, probiotics, nootropics, functional, mixed_supplements}` | HIGH if leader >3x runner-up; MEDIUM 2-3x; LOW or REFUSED → `mixed_<vertical>` |
| **Business stage** (auto-detect, replaces env var) | Annualized GMV from L90×4 (or L180×2, or trailing-12-month if ≥360 days history); `BUSINESS_STAGE` env var override | STARTUP <$500K, GROWTH $500K-$3M, MATURE $3M-$20M, ENTERPRISE >$20M | HIGH unless GMV within ±25% of band boundary |
| **Business model** (NEW) | Fraction of L180 orders from customers with ≥3 orders at near-constant inter-order gap (σ/μ < 0.3) | ONE_TIME_LED (<10%), SUBSCRIPTION_LED (>40%), HYBRID otherwise | HIGH if clearly bimodal; MVP: only `replenishment_due` priority change consumes this |
| **Cadence baseline** (NEW) | Right-censored empirical median per SKU class (≥30 customers with ≥2 purchases of class); K-M via `lifelines` lands in S11 | `median_reorder_days_by_sku_class`, `global_median_reorder_days` | Per SKU class; REFUSED if insufficient sample |
| **Seasonality exposure** (NEW) | Calendar lookup from `config/seasonality_calendars.yaml` against `run_date` | `SeasonalityContext(window_name, vertical_expected_lift_direction, vertical_expected_lift_magnitude_range, source_artifact)` | All cells `heuristic_unvalidated` until cited |
| **Data depth** (NEW, cheap) | Direct CSV counts | `history_days`, `n_customers`, `n_orders`, `n_repeat_customers`, `n_subscription_orders` | Used as input to other dimensions and to S10+ ModelFitStatus |
| **Gate calibration** (deterministic derivation) | Pure function of the seven dimensions above + `config/gate_calibration.yaml` | Per-play audience floors, materiality floor, primary window, agreement window set | All cells tagged `heuristic_unvalidated`; same discipline as priors.yaml |

## IV-4. The gate_calibration table (the load-bearing artifact)

`config/gate_calibration.yaml` is the central source of truth. It is the file the founder must review cell-by-cell before flag flip. Concrete sketch:

```yaml
audience_floors:
  winback_dormant_cohort:
    beauty:
      skincare:    { startup: 80,  growth: 200, mature: 500, enterprise: 1500 }
      cosmetics:   { startup: 100, growth: 250, mature: 600, enterprise: 1800 }
    supplements:
      protein:     { startup: 120, growth: 300, mature: 700, enterprise: 2000 }
      multivitamin:{ startup: 100, growth: 250, mature: 600, enterprise: 1800 }
materiality_floors_usd:
  startup: 800
  growth:  2000
  mature:  4500
  enterprise: 12000
primary_window:
  beauty:
    skincare:    L28
    cosmetics:   L28
    haircare:    L56
  supplements:
    protein:     L60
    multivitamin: L60
    nootropics:  L90
agreement_windows:
  beauty:
    skincare:    [L28, L56, L90]
  supplements:
    protein:     [L56, L90, L180]
    nootropics:  [L90, L180]
```

**Every cell is tagged `heuristic_unvalidated` at S6.5 ship.** They are starting heuristics, not validated numbers. Post-beta calibration loop will tune them with outcome data, same discipline as priors validation.

## IV-5. What changes vs. Parts I, II, III

**Part I §B (Tier-B builders):**
- Audience floors are no longer hardcoded in builder functions. Builders read `profile.gate_calibration.audience_floor_by_play_id[<play_id>]`.
- Primary measurement window is no longer a builder constant. Builders read `profile.measurement.primary_window`. Beauty/skincare stays L28; supplements/protein switches to L60.
- Multi-window agreement set varies per sub-vertical, not a global {L28, L56, L90}.

**Part I §C (Empirical-Bayes blend):**
- `pseudo_N` defaults can be sub-vertical-aware if the founder later decides to override (out of MVP scope; the hook exists).
- No other change to the blend mechanics.

**Part I §G (Smarter Abstain):**
- New abstain sub-mode possible: `SOFT_STORE_TOO_SMALL` when profile detects STARTUP with insufficient data depth for any play to clear floors. MVP: continue using existing `AUDIENCE_TOO_SMALL`; new sub-mode can be added post-beta.

**Part II §2 (Per-sprint plan):**
- Sprint 6.5 inserted between S6-T1.5 and S6-T2.
- S6-T2 (supplements parser) explicitly held until S6.5 lands.
- S6-T3, S7 builders consume profile values rather than re-litigating floors.
- S8 Play Library refactor folds profile dependencies into per-play folders.
- S10-S13 ML predictive layer reads `ModelFitStatus` thresholds from `profile.data_depth`.

**Part III-1 (Priors validation):**
- The `validation_status` discipline extends to `gate_calibration.yaml` cells: every floor / window value tagged `heuristic_unvalidated` until calibrated.
- Seasonality calendar magnitudes treated as **observational benchmarks, not causal lifts.** Never multiply revenue ranges.

**Part III-3 (Engine-only JSON scope):**
- Unchanged. Profile fields land on `engine_run.json` typed slots; no HTML renderer work.

## IV-6. Sprint slotting

| Sprint | Status | Profile interaction |
|---|---|---|
| S6-T1, T1.5 | ✅ Done | Pre-profile; floors hardcoded |
| **S6.5 (NEW)** | **In planning** | **Ships profile + gate_calibration.yaml + flag flip** |
| S6-T2 | Held | Resumes with `profile.taxonomy.subvertical`-aware SKU class parsing |
| S6-T3 (`replenishment_due`) | Held | Consumes `profile.measurement.primary_window` + `profile.cadence` |
| S7 | Held | Three builders each consume `profile.gate_calibration` |
| S7.5 | ✅ Done | Validation discipline extends to gate_calibration cells |
| S8 | Planned | Play Library refactor imports profile contracts into per-play folders |
| S10-S13 | Planned | ML predictive layer reads `profile.data_depth` for ModelFitStatus thresholds |

**Total sprint count update:** S6 through S14 was 9 sprints (~15 weeks); S6.5 insertion brings it to 10 sprints (~16 weeks). Net beta-launch impact: +0.5 to +1 sprint, possibly net-zero (downstream sprints get easier because builders consume profile values instead of re-litigating floors).

## IV-7. MVP scope vs. deferred (full vision)

**MVP at S6.5 (beta-blocking):**
- Token classifier for vertical + sub-vertical
- Annualized-GMV banding for business stage
- Heuristic for business model (subscription-led detection)
- Right-censored empirical median for cadence (K-M deferred to S11)
- Calendar lookup for seasonality (annotation only)
- Deterministic gate_calibration derivation
- Three new YAMLs authored as `heuristic_unvalidated` defaults

**Deferred to post-beta (full vision):**
- Embedding-based sub-vertical clustering
- STL seasonal decomposition / store-specific seasonality fits
- K-M with Cox PH covariates for cadence (lands organically in S11)
- ML-driven stage detection (LTV-aware, not just GMV-based)
- Profile calibration loop (outcome data → cell-by-cell floor recalibration, post Phase 9)
- Per-merchant seasonality calendars (learned from ≥2 years of history)

## IV-8. Risk register (S6.5)

1. **Sub-vertical mis-classification on cross-category stores.** Mitigation: LOW-confidence taxonomy routes to `mixed_<vertical>` with conservative-min priors (KI-19 discipline already exists).
2. **Cell sparsity in gate_calibration.yaml.** With 2 verticals × 4-6 sub-verticals × 4 stages × N plays = many cells with unstable starting values. Mitigation: all cells `heuristic_unvalidated`; founder review on the table before flag flip; calibration loop post-beta.
3. **Audit complexity.** Every recommendation now cites profile fields in `drivers[]`. JSON volume increases. Acceptable cost.
4. **Backward compat with env vars.** `BUSINESS_STAGE` and `VERTICAL_MODE` env vars stay as **operator overrides**; both detected and override values recorded in provenance.
5. **Single point of failure.** A bug in stage detection breaks every gate. Mitigation: pin profile derivation in tests; provenance makes it inspectable; operator override is the safety valve.
6. **The synthetic Beauty fixture activation moment.** If after S6.5 the Beauty fixture STILL doesn't surface the winback card (e.g., because revenue range is too small relative to materiality floor even at growth-stage settings), we need a different fix. Hard-stop discipline at S6.5-T5 catches this.
7. **Seasonality discipline drift.** Future engineers may be tempted to apply seasonality magnitudes as revenue multipliers. Strict invariant: seasonality is annotation only. Pin in tests.

## IV-9. Discipline insight (the seasonality / benchmark trap)

The seasonality magnitudes in `seasonality_calendars.yaml` and the Klaviyo / Shopify benchmarks already in `priors.yaml` are **observational averages from marketing-performance reporting**, not causal lift. The profile treats them the same way the priors validation discipline does:

- Use benchmarks as **priors for Bayesian blending** (already the discipline)
- Use them as **range constraints** for catching engine outputs that are wildly off (e.g., a winback revenue range that exceeds 5x the Klaviyo benchmark median is probably a bug)
- Do **NOT** use them as **causal lift multipliers** on revenue ranges
- Do **NOT** use seasonality magnitudes to bump cohort signals

The profile makes this discipline auditable because every benchmark-derived number cites its `source_artifact` and `validation_status` in JSON.

