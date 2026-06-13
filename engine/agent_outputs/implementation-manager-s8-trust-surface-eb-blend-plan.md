# BeaconAI Sprint 8 — Trust-Surface PlayCard Contract + EB Blend + Play Library Wave 1

**Author:** implementation-manager
**Date:** 2026-05-24
**Branch baseline:** `post-6b-restructured-roadmap` (HEAD `9e2f357`, post-S7.6 CLI-fix `d8ede8c`)
**Supersedes:** ARCHITECTURE_PLAN.md Part II §2 Sprint 8 specification where it conflicts with this document.
**Authoritative parent:** `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` §B-S8.
**Status:** Draft for founder approval before first S8 refactor dispatch.

---

## Part A — Executive Summary

### Sprint anchor

Sprint 8 locks the trust-surface PlayCard contract for beta: typed `evidence_source` chip, typed `sensitivity` block, typed `provenance` object — all additive within `event_version=1`. It ships the **empirical-Bayes blend layer** in `sizing.py` as a defensible posterior-blending primitive consumed by the four S6/S7-wired Tier-B builders. It migrates the first three plays (`winback_dormant_cohort`, `replenishment_due`, `discount_dependency_hygiene`) into the `plays/<play_id>/` directory layout as a refactor-by-template that does not change behavior. Founder-facing inspection surface is `engine_run.json` only — `briefing.html` is debug-only and scheduled to retire when the frontend app activates (founder-confirmed 2026-05-24).

### Beta-criticality posture

Per IM revised plan line 109: **partial.** Tier formalization (S8-T1, S8-T2) is beta-blocking — the trust-surface contract is what the merchant-facing JSON consumer (eventual frontend, and any private-beta operator inspection) will pattern-match against. The EB blend (S8-T3) ships **for contract-stability** but its *epistemic payoff* is dormant until Phase 9 outcome ingestion (post-beta S15+). Play Library wave 1 (S8-T4) is a refactor with byte-identical behavior; beta-enhancing rather than blocking.

The honest read: S8 buys us a stable typed surface that S10–S13 (ML predictive layer) can extend additively. The EB blend layer is real working math, but until Phase 9 returns outcome data into `(observed_k, observed_n)` over multiple months, the blend's contribution above today's already-live S7.6 observed-effect surfacing (`Measurement.observed_effect/p_internal/n`) is incremental, not transformative.

### Dependencies on landed S7 / S7.5 / S7.6 work

- **S7.5 `validation_status` field (DONE 2026-05-17).** Three-state gate (`validated_external` / `validated_internal` / `elicited_expert` / `heuristic_unvalidated`) already drives blend-eligibility. S8-T3's EB blend MUST refuse to blend on `heuristic_unvalidated` priors — the existing `bayesian_blend` helper at `src/sizing.py` is the contract entrypoint S8-T3 extends, not replaces.
- **S7.6 observed-effect pipeline (CLOSED 2026-05-23).** Four of five S6/S7-wired Tier-B builders carry `revenue_range.source=blend` live with real per-store `(observed_k, observed_n)`. The S7.6 CLI fix (`d8ede8c`, 2026-05-24) populates canonical `Measurement.observed_effect/p_internal/n` from the `drivers[*].blend_provenance` stash at `src/measurement_builder.py:2252-2270`. **S8-T3's EB blend must preserve this surfacing logic** — any refactor that moves `build_prior_anchored_play_card` must keep the three-field population reachable.
- **S7.6 forward-scaffolding for S13.** `PlayCard.predicted_segment` and `PlayCard.model_card_ref` Optional stubs are in production (memory.md:578-580). S8 schema additions (`evidence_source`, `sensitivity`, `provenance`) must coexist cleanly with these and respect the same Optional-with-default-None additive shape.
- **S7.6 architectural invariants (load-bearing).** Single-demote-channel via `apply_guardrails_to_injected`; 3-channel `priority_prepend` via `8a2d726` T5.6; T6 eligibility gate with joint-p<0.10 amendment. **Every S8 ticket that touches `src/main.py:1380-1597`, `src/decide.py:assemble_considered`, or guardrail seams must explicitly preserve all three invariants.**

### What S8 delivers vs what is dormant

| Deliverable | Live value at S8 close | Dormant until |
|---|---|---|
| Typed `EvidenceSourceChip` on every PlayCard | Yes (inspection / future frontend) | — |
| Typed `Sensitivity` block on measured/directional cards | Yes (inspection) | Renderer surface deferred |
| Typed `Provenance` object | Yes (audit trail in `engine_run.json`) | — |
| EB blend layer in `sizing.py` | Yes (call-site replaces today's `bayesian_blend` wrapper) | Phase 9 outcome ingestion (S15+) for full payoff |
| `plays/<play_id>/` directory for 3 plays | Refactor-only, byte-identical | S8+ template usage for new plays |

---

## Part B — Ticket-by-ticket plan

### S8-T1 — Typed `EvidenceSourceChip` enum + PlayCard field

**Anchor goal:** Add the typed `evidence_source: Optional[EvidenceSourceChip]` field on `PlayCard`. The chip surfaces the epistemic provenance of the card as a single typed enum that downstream consumers (eventual frontend, operator inspection of `engine_run.json`) can pattern-match without reading drivers[] or measurement internals.

**Enum shape (additive within `event_version=1`):**
```
EvidenceSourceChip = STORE_MEASURED | STORE_OBSERVED | INDUSTRY_PRIOR | OBSERVATIONAL
```
Maps onto the Tier A/B/C/D spec from ARCHITECTURE_PLAN.md Part I §A. Does NOT replace the existing `EvidenceClass` enum — it is an additional typed dimension.

**Files predicted touched (verify via Read at impl time):**
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — new `EvidenceSourceChip` enum + Optional field on `PlayCard`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py` — `build_prior_anchored_play_card` populates the chip from existing `revenue_range.source` and `evidence_class`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` — pass-through; no decision logic depends on the chip.
- 5 S6/S7 Tier-B builder seams (winback, replenishment_due, discount_hygiene, journey_first_to_second, aov_bundle) — each populates the chip.

**Schema additions:** `PlayCard.evidence_source: Optional[EvidenceSourceChip] = None`. Additive within `event_version=1`. Default `None` permitted during migration; populated by builders post-T1.

**Feature flag:** `ENGINE_V2_TIER_CHIP` default **OFF** at T1 commit; flipped **ON** in T1.5 atomic re-pin commit.

**Acceptance criteria:**
1. Every emitted PlayCard on Beauty + Supplements carries `evidence_source != None` when flag is ON.
2. Mapping is deterministic per `(evidence_class, revenue_range.source)` pair (table pinned in test).
3. Flag OFF reproduces pre-T1 fixture sha256 byte-identical.
4. Suite ≥1770 passing (no regression).

**Test deliverables:**
- `tests/test_s8_t1_evidence_source_chip.py` — per-builder population, mapping-table determinism, flag-OFF byte-identical contract, every PlayCard on Beauty + Supplements pinned fixtures carries the chip with the expected value.

**Re-pin posture:** `engine_run.json` shape changes (new field). `briefing.html` byte-identical because renderer doesn't surface the chip (founder-confirmed: HTML is debug-only and retiring). **The re-pin trigger is JSON shape, not HTML.**

**Dependencies:** S7.5 `validation_status` field (DONE), S7.6 observed-effect pipeline (CLOSED).

**Estimated commits:** 3 (T1 impl + memory + summary, plus T1.5 atomic flip + re-pin = 1 more commit = 4 total for T1 cluster).

---

### S8-T2 — `Sensitivity` typed dataclass + per-PlayCard population

**Anchor goal:** Add typed `sensitivity: Optional[Sensitivity]` block carrying one-up-one-down scenario values for the revenue range (e.g., what if observed_n were 50% smaller / 50% larger, what if prior anchor shifted by ±1 σ). Surface in `engine_run.json` as a typed slot that future trust-math tooling (S9, deferred) and the eventual frontend can consume.

**Dataclass shape:**
```
@dataclass
class Sensitivity:
    scenario_observed_n_halved: Optional[RevenueRange]
    scenario_observed_n_doubled: Optional[RevenueRange]
    scenario_prior_shifted_down: Optional[RevenueRange]
    scenario_prior_shifted_up: Optional[RevenueRange]
    pseudo_N_used: int
    notes: List[str]
```

**Population rules:**
- Tier-B prior-anchored cards (cards with `revenue_range.source=blend`): full Sensitivity block populated.
- Targeting / Tier-C cards (`measurement is None`): `sensitivity = None` (acceptable — no point estimate to perturb).
- Cards with `revenue_range.suppressed=True`: `sensitivity = None`.

**Files predicted touched:**
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — new `Sensitivity` dataclass + Optional PlayCard field.
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py` — new `compute_sensitivity(observed_effect, observed_n, prior, pseudo_N)` helper.
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py` — `build_prior_anchored_play_card` populates sensitivity from `drivers[*].blend_provenance` (same source as the S7.6 CLI fix's three-field population).

**Schema additions:** `PlayCard.sensitivity: Optional[Sensitivity] = None`. Additive within `event_version=1`.

**Feature flag:** `ENGINE_V2_TIER_CHIP` (reused — sensitivity ships in same atomic flip as the chip, per founder's "stop deferring things" guidance). Alternative: `ENGINE_V2_SENSITIVITY` separate flag if founder prefers staged rollout. **Open question, Part E.**

**Acceptance criteria:**
1. Every Tier-B `revenue_range.source=blend` card carries a populated `sensitivity` block when flag is ON.
2. Targeting cards carry `sensitivity = None`.
3. The four sensitivity scenarios are reproducible (deterministic given input).
4. Flag OFF byte-identical to pre-T2.

**Test deliverables:**
- `tests/test_s8_t2_sensitivity_block.py` — per-tier population matrix, scenario math correctness, suppressed-state behavior, byte-identical flag-OFF contract.

**Re-pin posture:** `engine_run.json` shape only. HTML byte-identical.

**Dependencies:** S8-T1 (sequenced after — atomic flag flip bundled with T1.5 OR separate T2.5 flip; see Part E open question).

**Estimated commits:** 3 (impl + memory + summary), plus shared atomic flip with T1.5 if bundled.

---

### S8-T3 — EB blend layer in `sizing.py` consumed by S6/S7 Tier-B builders

**Anchor goal:** Promote the existing S7.5 `bayesian_blend` helper into the formal EB blend layer with the `pseudo_N` policy table per `source_class`, refusal-on-`heuristic_unvalidated` discipline, and a new `RevenueRangeSource` enum value (`blend_empirical_bayes` OR retain current `blend` literal — **see Part E open question on the discrepancy**). Tier-B builders (already calling `bayesian_blend` post-S7.5) gain the `pseudo_N` lookup path; behavior is unchanged for `validated_*` priors and identical-to-suppress for `heuristic_unvalidated`.

**Math contract (from ARCHITECTURE_PLAN.md Part I §C, line 317–321):**
```
posterior_mean = (κ₀ · μ₀ + k) / (κ₀ + n)
weight_observed = n / (n + pseudo_N)
weight_prior = pseudo_N / (n + pseudo_N)
```
Refusal on `heuristic_unvalidated`: blend returns `None`, caller suppresses the revenue range with `ReasonCode.PRIOR_UNVALIDATED` (existing seam).

**Files predicted touched:**
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py` — formalize `bayesian_blend` into `blend_with_prior(observed_effect, observed_n, prior, pseudo_N) -> Optional[BlendedPosterior]`. Preserve the existing observed-effect plumbing that the S7.6 CLI fix relies on.
- `/Users/atul.jena/Projects/Personal/beaconai/src/priors_loader.py` — `pseudo_N` lookup helper keyed on `source_class` and overridden per-prior when explicitly set in YAML.
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml` — optional per-prior `pseudo_N` field (defaults from `source_class` table when absent).
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py` — `build_prior_anchored_play_card` calls the new helper; **MUST preserve the `Measurement.observed_effect/p_internal/n` population at lines 2252-2270 (S7.6 CLI fix)**.

**Schema additions:** `RevenueRange.source` enum may gain literal `blend_empirical_bayes` if founder confirms split from current `blend` literal (Part E). Otherwise the existing `blend` literal carries the new semantics. `Prior.pseudo_N: Optional[int] = None` added to the YAML loader contract.

**Feature flag:** `ENGINE_V2_EB_BLEND` default **OFF** at T3 commit; flipped **ON** in T3.5 atomic re-pin commit.

**Acceptance criteria:**
1. On synthetic test where `observed_effect >> prior_mean` and `n=10`, blend pulls posterior toward prior (defensibly conservative).
2. On synthetic test where `n >> pseudo_N`, blend lets observed dominate (posterior within 5% of observed).
3. On `heuristic_unvalidated` prior, blend returns None and caller suppresses revenue range.
4. `Measurement.observed_effect/p_internal/n` remains populated on all four wired Tier-B cards on Beauty (S7.6 tripwire test at `tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_recommended_cards_surface_observed_effect_on_beauty` still passes).
5. Flag OFF byte-identical.

**Test deliverables:**
- `tests/test_s8_t3_eb_blend.py` — math correctness across 6 canonical scenarios (low-n, high-n, hostile-observed, missing-prior, unvalidated-prior, edge case `n=0`).
- `tests/test_s8_t3_pseudo_n_table.py` — `source_class` → `pseudo_N` mapping is deterministic and respects per-prior overrides.
- Existing S7.6 tripwire test must continue to pass unmodified.

**Re-pin posture:** When `ENGINE_V2_EB_BLEND` flips ON in T3.5, Beauty + Supplements `engine_run.json` may show modest changes in revenue_range p10/p50/p90 on the four wired Tier-B cards (blend math is functionally equivalent to today's `bayesian_blend` for validated priors, so changes should be small or zero). M0 byte-identical (M0 fixtures have no Tier-B activation). HTML byte-identical.

**Dependencies:** S7.5 (`bayesian_blend` contract surface, DONE), S7.6 (observed-effect pipeline, CLOSED). Independent of S8-T1 / S8-T2 at code level — can land in parallel.

**Estimated commits:** 3 (impl + memory + summary), plus T3.5 atomic flip (1 commit) = 4 total.

---

### S8-T4 — Play Library wave 1: fold 3 plays into `plays/<play_id>/`

**Anchor goal:** Begin the directory restructure to `plays/<play_id>/{spec.yaml, audience.py, builder.py, copy.md}` as the canonical Play Library shape. **Wave 1: 3 plays.** Refactor-only — byte-identical behavior. The wave 1 selection is the founder's call (Part E): default proposal per IM revised plan = `winback_dormant_cohort`, `replenishment_due`, `discount_dependency_hygiene`.

**Files predicted touched:**
- New directory tree under `/Users/atul.jena/Projects/Personal/beaconai/plays/<play_id>/`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/play_registry.py` — extended to load from `plays/<play_id>/spec.yaml` when present; falls back to legacy registry entries when absent.
- 3 play-specific source files refactored under `plays/<play_id>/` (audience builder, measurement builder hookup, copy template).
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py` — registry references updated; `_PRIOR_ANCHORED` at line 717 may need a thin shim or be auto-populated from spec.yaml entries.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` — **must NOT add new injection blocks at lines 1380–1597** (single-demote-channel invariant). Wave 1 refactor inherits the existing injection block per play; KI-NEW-L collapse is a separate ticket (Part D).

**Schema additions:** None.

**Feature flag:** `ENGINE_V2_PLAY_LIBRARY_WAVE1` default **OFF** at T4 commit; flipped **ON** in T4.5 atomic re-pin commit. Flag-OFF reproduces legacy load path byte-identical.

**Acceptance criteria:**
1. The 3 migrated plays produce byte-identical PlayCards (sha256 over the relevant `engine_run.json` substructures) under flag ON vs flag OFF.
2. The 11 unmigrated plays untouched.
3. M0 + Beauty + Supplements pinned fixtures byte-identical.
4. S7.6 invariant tests all pass unchanged (single-demote-channel, 3-channel priority_prepend, T6 eligibility gate, observed-effect tripwire).

**Test deliverables:**
- `tests/test_s8_t4_play_library_wave1_migration.py` — flag-ON vs flag-OFF byte-identical contract per migrated play; registry loads both paths; behavior identical.

**Re-pin posture:** Goal is **zero re-pin**. If a re-pin is forced by a subtle difference, that is a regression and the ticket should halt + escalate.

**Dependencies:** S6, S7 closed; S8-T1, S8-T2, S8-T3 do NOT block T4 at code level (can land in parallel), but sequencing T4 last in the sprint avoids stacking risk.

**Estimated commits:** 3 (impl + memory + summary), plus T4.5 flag flip = 4 total.

---

### S8 ticket-cluster totals

| Ticket | Commits | Re-pin? | Beta-blocking? |
|---|---|---|---|
| S8-T1 (chip) + T1.5 | 4 | engine_run.json only | yes (tier formalization) |
| S8-T2 (sensitivity) | 3 (shared T1.5 flip or separate T2.5) | engine_run.json only | yes (tier formalization) |
| S8-T3 (EB blend) + T3.5 | 4 | engine_run.json (minor numeric) | partial (contract yes, payoff post-beta) |
| S8-T4 (Play Lib wave 1) + T4.5 | 4 | none target | no (refactor) |
| **S8 total** | **~15 commits** | 3 re-pin events | partial |

Estimated duration: ~2 weeks per IM revised plan §B-S8 line 108.

---

## Part C — S8 prerequisites (hard blockers landing inside or before S8)

### KI-NEW-K — `discount_dependency_hygiene.base_rate.beauty` Beta envelope re-fit at effective_n=60

**KI text (KNOWN_ISSUES.md:386):** Beta(alpha=0.66, beta=29.34) is J-shaped because alpha<1; published `range_p10=0.0120` and `range_p90=0.0430` are text-derived, not re-derived from the Beta CDF. KI explicitly says **"before Sprint 8 calibration."**

**Recommendation:** **Land as S8-T0, before any S8 ticket dispatch.** Rationale:
1. KI text is explicit about pre-S8 timing.
2. The play is currently consumer-dormant per S7.6, but S8-T3's EB blend math against a J-shaped prior will produce mis-calibrated posteriors the moment a real-beta cohort activates the play (and Beauty already has `observed_n=148K` on `discount_dependency_hygiene` post-S7.6 T3.5).
3. The work is non-code (`priors.yaml` numeric edit + DS architect re-validation), so it does not consume refactor-engineer cycles.
4. Sequencing it as S8-T0 cleanly separates "priors-shape work" from "code-shape work" in the sprint diary.

**Dispatch shape:** DS architect ticket — re-fit Beta envelope at `effective_n=60` (alpha=1.32, beta=58.68), re-derive p10 / p90 analytically, verify base64-image numerics against original Klaviyo PDF source. No engine code change. Pin priors.yaml sha256 in test.

### KI-NEW-J — Supplements `aov_lift_via_threshold_bundle` magnitude re-research

**KI text (KNOWN_ISSUES.md:374):** Supplements entry was DOWNGRADED at S7 from `validated_external` to `elicited_expert` with `pseudo_n=10` because primary anchor evidence is beauty-vertical case studies transferred to supplements. Magnitude (0.95% vs 1.20% beauty) is NOT independently sourced from supplements-vertical CVR data.

**Recommendation:** **Defer to post-S8 / pre-private-beta (S14) calibration window.** Rationale:
1. The downgrade is *already correct behavior* — supplements is gated via `vertical_excluded_per_b5_248` per S7.6 close, so the play does not activate on supplements regardless of magnitude resolution.
2. S8's EB blend math does NOT consume this prior on supplements (gate prevents activation).
3. Re-research requires a dedicated Gemini Deep Research re-run pass against supplements-vertical sources (Ritual, Athletic Greens, Care/of, iHerb, Thorne) — not a blocker for S8 deliverables.
4. S14 private-beta will surface whether real-supplements merchants have shape that justifies promoting the entry; that is the natural resolution moment.

**Tradeoff called out:** If S8 ships the EB blend layer without resolving KI-NEW-J and a supplements merchant manually overrides the vertical-exclusion gate (via env-flag escape hatch), the blend will run against the elicited_expert prior with pseudo_N=10, anchoring toward beauty-rooted magnitude. Mitigation: document the gate-override contract explicitly in the S8-T3 summary; flag-default behavior is correct.

---

## Part D — Structural cleanup KIs the founder may want bundled into S8

### KI-NEW-L — Collapse 5 V2 prior-anchored injection blocks → 1 PRIOR_ANCHORED dispatch

**Founder consideration:** This is a structural refactor at `src/main.py:1380-1597` that **must preserve three S7.6 invariants simultaneously**: (a) single-demote-channel via `apply_guardrails_to_injected`, (b) 3-channel `priority_prepend` coverage for Tier-B cards across `cap_exceeded` + `eligibility_rejects` + `prior_unvalidated_rejects` + `window_disagreement_rejects`, (c) the `Measurement.observed_effect/p_internal/n` population at `src/measurement_builder.py:2252-2270` (S7.6 CLI fix).

**Recommendation:** **Defer to S9** (or a dedicated structural-cleanup sprint between S8 and S10). Rationale:
1. The collapse is high-risk because it touches every Tier-B builder activation seam simultaneously. A single missed invariant equals silent regression in beta-prep validation.
2. The benefit is structural (single dispatch instead of 5 blocks); behavior is unchanged.
3. S8's deliverables (chip, sensitivity, EB blend, Play Library wave 1) are independently valuable and do not require the collapse. The Play Library wave 1 refactor explicitly inherits the existing injection blocks per play.
4. The collapse becomes natural as Play Library waves 2+ migrate the remaining plays; at that point the `_PRIOR_ANCHORED` registry can drive a single dispatch as the legacy injection blocks empty out organically.

**Tradeoff called out:** Deferring KI-NEW-L means S8 ships with 5 injection blocks intact, and any future Tier-B builder (none planned for S8, but possible post-S10) continues to add another block. The structural-drift surface grows by 1 per builder. The founder may reasonably prefer to land the collapse in S8 to stop the drift before S10–S13 land — at the cost of an extra ~1 week of sprint scope and the cross-invariant verification burden. **Founder call.**

### KI-NEW-M — `_dedupe_rejections` first-wins-vs-last-wins-typed-code policy

**Founder consideration:** Today, when the same `play_id` appears in multiple rejection sources, the first reason wins and downstream (more specific) reasons are silently dropped. Cosmetic-but-load-bearing for merchant surface clarity.

**Recommendation:** **Defer to S9 or post-beta.** Rationale:
1. Engine behavior is honest today; the reasons displayed are correct, just sometimes less specific than they could be.
2. The fix requires a typed-reason priority map, which is a small but careful piece of policy work — the kind that benefits from a dedicated sprint slot rather than a sprint-tail bundle.
3. Beta merchants are likely to surface concrete examples of "this reason is confusing" that should inform the priority map design.

**Tradeoff called out:** Bundling it into S8 (as S8-T6) would close a known papercut before beta, at the cost of ~3 days of sprint scope. Acceptable scope creep if founder prioritizes "no known papercuts at beta entry."

### KI-NEW-N — Experiment-promotion provenance-preserve at `src/decide.py:2080-2087`

**Founder consideration:** When a Considered play_id is promoted to Recommended Experiment, the original upstream rejection reason is silently dropped. Merchant sees the experiment card but not why the play was originally Considered.

**Recommendation:** **Defer to post-S8** (likely S9 alongside KI-NEW-M, as both are decide-layer provenance hygiene). Rationale:
1. Experiment promotion fires rarely on current fixtures; the provenance loss is a low-frequency surface today.
2. The fix is a small additive field (`promoted_from_considered_reason`) — beta-low-risk, but also beta-low-value relative to the chip/sensitivity work S8 delivers.
3. S8 already adds three PlayCard fields; adding a fourth additive field in the same sprint stress-tests the schema-freeze additive-only contract beyond comfortable bounds (cf. R-S8.1).

**Tradeoff called out:** Same as KI-NEW-M — bundling adds ~2 days, closes a papercut before beta.

### Summary verdict on Part D bundling

Default recommendation: **all three (L, M, N) defer to S9.** S8 stays focused on its locked 4-ticket scope. Founder may override to bundle L (high-value, high-risk) and/or M+N (low-value, low-risk papercuts) — **Part E open question Q3.**

---

## Part E — Open questions for the founder

### Q1 — KI-NEW-K timing: pre-S8 or S8-T0?

**Decision needed:** Does the `discount_dependency_hygiene.base_rate.beauty` Beta envelope re-fit land as a pre-S8 commit (before S8 sprint kickoff) or as the first ticket inside S8 (S8-T0)?

**Default recommendation:** S8-T0 inside the sprint, dispatched to DS architect (not refactor-engineer). Rationale: keeps the priors-shape work auditable in the S8 sprint diary; does not delay sprint kickoff.

### Q2 — KI-NEW-J in scope or defer?

**Decision needed:** Does S8 require resolution of the supplements `aov_lift_via_threshold_bundle` magnitude re-research, or defer to S14 pre-private-beta?

**Default recommendation:** Defer to S14. Supplements is gated via `vertical_excluded_per_b5_248` per S7.6 close; S8's EB blend does not consume this prior on supplements under default behavior.

### Q3 — Bundle KI-NEW-L / M / N into S8 or defer?

**Decision needed:** Land any/all of the three structural-cleanup KIs as S8-T5 / T6 / T7, or defer all to S9 / post-beta?

**Default recommendation:** Defer all three to S9. S8 stays focused. Founder may override to bundle individual items per Part D tradeoff text.

### Q4 — `pseudo_N` table — LOCKED VALUES DISCREPANCY (DS architect must resolve)

**The discrepancy:**

- **IM revised plan line 1190** (`agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md`): "pseudo_N per source_class: `expert = 1`, `observational = 5`, `causal = 20`."
- **ARCHITECTURE_PLAN.md Part I §C line 327** (table preserved from 2026-05-16 design): different shape — `causal = 200`, `observational = 50`, `expert = 20`, `internal_heuristic_unvalidated = 5`.
- **Current S7.5 production code** uses a `bayesian_blend` helper with its own implicit pseudo_N defaults that should be the third datapoint.

**Decision needed:** Which shape is locked for S8-T3?

**Default recommendation:** **STOP and dispatch DS architect to lock the values before S8-T3 implementation.** Do NOT pick silently. The two documents disagree by an order of magnitude on `causal` (200 vs 20) and on `observational` (50 vs 5). Whichever set is locked has direct numeric impact on every Tier-B revenue range from S8 forward. This is exactly the "only follow the path that's decided" trigger from CLAUDE.md.

**Escalation shape:** DS architect verdict ticket at `agent_outputs/ecommerce-ds-architect-s8-pseudo-n-lock-verdict-2026-05-2X.md`. Must reconcile: (a) which document's values are correct, (b) what does the current production `bayesian_blend` actually use, (c) what is the locked S8 table.

### Q5 — `RevenueRange.source` enum: new literal or reuse existing?

**Decision needed:** S8-T3's EB blend layer — does `RevenueRange.source` gain a new literal `blend_empirical_bayes` (per ARCHITECTURE_PLAN.md Part II §S8-T3 line 1198) or reuse the existing `blend` literal that S7.6 already populates?

**Default recommendation:** Reuse `blend`. The S7.6 pipeline already populates `blend` semantics; introducing `blend_empirical_bayes` as a sibling literal would force a re-pin on the four currently-wired Tier-B cards for no consumer-visible change. The "empirical Bayes" framing is engineering-internal; the contract surface is the same posterior math.

### Q6 — Play Library wave 1 selection: include `replenishment_due` or substitute?

**Decision needed:** Per S7.6 honest-dormancy verdict, `replenishment_due` is consumer-dormant on Beauty (D-S6-4 N≥30 collapses cohort_n to 0). Does it still land in wave 1 (folder-only refactor, no behavior change, dormancy preserved) or substitute another play (e.g., `cohort_journey_first_to_second` which is active on Beauty)?

**Default recommendation:** Include `replenishment_due` in wave 1 as planned. The folder-only refactor does not alter dormancy; the migration template benefits from including one dormant + two active plays (it surfaces any refactor assumption that silently depends on activation).

### Q7 — S8-T2 atomic flip: bundled with T1.5 or separate T2.5?

**Decision needed:** Does the `Sensitivity` block ship under the same `ENGINE_V2_TIER_CHIP` flag (atomic flip with T1.5) or a separate `ENGINE_V2_SENSITIVITY` flag (independent T2.5 flip)?

**Default recommendation:** Bundle under `ENGINE_V2_TIER_CHIP` per founder's "stop deferring things" guidance. Two flip events instead of three reduces re-pin churn.

---

## Part F — Risk register

### R-S8.1 — Three additive PlayCard fields landing in one sprint stress-tests schema-freeze contract

**What could go wrong:** `evidence_source` + `sensitivity` + `provenance` all additive within `event_version=1`. Plus the existing S7.6-era stubs (`predicted_segment`, `model_card_ref`). PlayCard's optional-field surface area expands materially in one sprint. A subtle additive-vs-non-additive policy violation could force a `event_version=2` bump, pushing beta.

**Mitigation:** Per-ticket DS architect spec-check before landing each schema addition. Each field default-`None` and Optional. Single-writer ownership documented per field in the summary file. `_ALLOWED_WRITERS` grep test extended to the new fields if applicable.

### R-S8.2 — EB blend numeric drift narrows revenue ranges → triggers re-pin cascade

**What could go wrong:** S8-T3.5 atomic flip switches the four wired Tier-B cards from the current S7.5 `bayesian_blend` to the formalized `blend_with_prior`. Even if functionally equivalent on validated priors, floating-point drift could change p10/p50/p90 by cents. The materiality-floor footer copy reads from the same underlying numbers — drift may cross a copy threshold and force unexpected wording changes.

**Mitigation:** S8-T3 test pins the math relationship; T3.5 re-pin commit documents the numeric diff explicitly in the summary. If the diff exceeds 5% on any single card's p50, STOP and escalate to DS architect — this would signal a math discrepancy between today's `bayesian_blend` and the new helper, not floating-point drift.

### R-S8.3 — Play Library wave 1 surfaces hidden coupling between migrated plays and `src/action_engine.py` internals

**What could go wrong:** The 3 selected plays may have unobvious dependencies on legacy `action_engine.py` paths that don't surface until the spec.yaml-driven loader runs. M0 byte-identical contract breaks.

**Mitigation:** Per IM revised plan, the 3 selected plays are the *cleanest* candidates (S6/S7 Tier-B builders themselves, which have no legacy entanglement — `discount_dependency_hygiene` and `winback_dormant_cohort` are post-S6/S7 builds; `replenishment_due` is dormant). T4 acceptance criterion #1 (byte-identical under flag ON vs OFF per migrated play) catches the regression before T4.5 atomic flip.

### R-S8.4 — KI-NEW-L deferral lets injection-block drift continue

**What could go wrong:** S8 ships with 5 injection blocks at `src/main.py:1380-1597` intact. Any future Tier-B builder (post-S10) adds a 6th. The single-demote-channel invariant becomes harder to verify per-block.

**Mitigation:** No new Tier-B builders are planned through S13 (ML predictive layer doesn't add builders, only ranking strategies). KI-NEW-L collapse is naturally bundled with Play Library wave 2+ as registry-driven dispatch becomes the load-bearing path.

### R-S8.5 — `pseudo_N` value discrepancy (Q4) goes silently unresolved

**What could go wrong:** S8-T3 implementation picks one of the two documented `pseudo_N` tables without DS architect verdict, locking the wrong values for the next 6+ months.

**Mitigation:** Part E Q4 is the explicit STOP-and-escalate gate. No T3 implementation dispatch without locked DS verdict.

### R-S8.6 — S7.6 CLI-fix `Measurement.observed_effect/p_internal/n` surfacing breaks under T3 or T4 refactor

**What could go wrong:** S8-T3 refactors `build_prior_anchored_play_card`; S8-T4 migrates `discount_dependency_hygiene` and `winback_dormant_cohort` into `plays/<play_id>/`. Both touch the code path containing the S7.6 CLI fix at `src/measurement_builder.py:2252-2270`. A subtle move could leave the three fields unpopulated on production.

**Mitigation:** The S7.6 tripwire test (`tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_recommended_cards_surface_observed_effect_on_beauty`) is the canary. Both T3 and T4 acceptance criteria pin "S7.6 tripwire passes unmodified." Re-run the test after every commit in the T3 / T4 cluster.

### R-S8.7 — S13 forward-compatibility regression on `PlayCard.predicted_segment` / `model_card_ref` stubs

**What could go wrong:** S8's three new fields (`evidence_source`, `sensitivity`, `provenance`) live on `PlayCard` alongside the S7.6-era `predicted_segment` and `model_card_ref` stubs. A serialization or ordering quirk could break the S13 integration assumption that all five fields coexist cleanly.

**Mitigation:** Per-ticket test asserts all 5 Optional fields coexist with default-None semantics. Schema migration table (Part H) documents the additive-only contract per field.

---

## Part G — KI roadmap update (S8 closes / opens / updates)

| KI | Title (short) | S8 disposition | Notes |
|---|---|---|---|
| KI-NEW-K | discount_dependency_hygiene Beta envelope re-fit | **CLOSED at S8-T0** | DS architect ticket pre-T1 |
| KI-NEW-J | supplements aov_lift_via_threshold_bundle re-research | **Updated** (defer to S14 pre-private-beta confirmed) | No engine code change in S8 |
| KI-NEW-L | Collapse 5 V2 prior-anchored injection blocks | **Updated** (deferred to S9 per Part D recommendation) | Founder may override to bundle |
| KI-NEW-M | `_dedupe_rejections` typed-code policy | **Updated** (deferred to S9) | Founder may override |
| KI-NEW-N | Experiment-promotion provenance-preserve | **Updated** (deferred to S9) | Founder may override |
| KI-NEW-O | xfail reasoning stale post-T5.6 | **Unchanged** (founder-confirmed 2026-05-24: separate test-hygiene pass, NOT in S8) | — |
| KI-30 | Per-play evidence visualization spec | **Updated** (chip + sensitivity blocks make this typed-JSON-renderable; UI layer remains out of scope) | engine-only deliverable |

**Newly opened by S8 (anticipated):**
- **KI-NEW-P (proposed):** `pseudo_N` per-prior override convention — once S8-T3 ships, individual priors.yaml entries may want per-prior pseudo_N overrides separate from the source_class default. Convention to be documented post-T3.
- **KI-NEW-Q (proposed):** Sensitivity scenario count — S8-T2 ships 4 scenarios; if beta merchants want more (e.g., observed_n quartiled), that becomes a post-beta extension. Track here so the field isn't extended ad-hoc.

---

## Part H — Schema migrations summary (S8-specific)

| Ticket | Field added | Type | Default | event_version | Single-writer |
|---|---|---|---|---|---|
| S8-T1 | `PlayCard.evidence_source` | `Optional[EvidenceSourceChip]` | `None` | 1 (additive) | `measurement_builder.py::build_prior_anchored_play_card` + per-builder seams |
| S8-T2 | `PlayCard.sensitivity` | `Optional[Sensitivity]` | `None` | 1 (additive) | `measurement_builder.py` (same seam) |
| S8-T2 | `Sensitivity` dataclass | new typed slot | — | 1 (additive) | `sizing.py::compute_sensitivity` |
| S8-T3 | `Prior.pseudo_N` | `Optional[int]` | `None` (defaults from source_class table) | 1 (additive) | `priors_loader.py` |
| S8-T3 | `RevenueRange.source` literal | (per Q5: reuse `blend` OR add `blend_empirical_bayes`) | — | 1 (additive enum extension) | `sizing.py::blend_with_prior` |
| S8-T4 | `plays/<play_id>/spec.yaml` schema | new file format | — | n/a (new artifact) | spec.yaml is single-writer per play directory |

All additions are strictly additive within `event_version=1` per Phase 6B Stop-Coding Line. **If any addition turns out to require a non-additive change, STOP and escalate to founder before commit.**

---

## Part I — Fixture re-pin schedule (S8-specific)

**Founder-confirmed posture (2026-05-24):** `engine_run.json` shape changes drive re-pins; `briefing.html` is debug-only and retiring; HTML re-pins are advisory, not blocking.

| Commit | Fixtures re-pinned | Trigger | HTML byte-identical? |
|---|---|---|---|
| S8-T0 (priors.yaml re-fit) | priors.yaml sha256 pin in test | KI-NEW-K Beta envelope re-fit | n/a (config file) |
| S8-T1.5 (chip flag ON) | Beauty + Supplements `engine_run.json` | new `evidence_source` field populated | yes (renderer doesn't surface chip) |
| S8-T2 (sensitivity, bundled with T1.5 per Q7 default) | bundled in T1.5 re-pin | new `sensitivity` block populated | yes |
| S8-T3.5 (EB blend flag ON) | Beauty + Supplements `engine_run.json` if numeric drift on Tier-B revenue_range | math-equivalent in expected case | yes |
| S8-T4.5 (Play Library wave 1 flag ON) | **target: ZERO re-pin** | refactor-only, byte-identical | yes |
| M0 fixtures | byte-identical across all S8 tickets | M0 has no Tier-B activation | yes |

**Beauty pinned slate sha256 baseline (pre-S8):** `fcd2924bc18d726fa18bf407c77ba433ba89a4563d3ad413a466b063c8eeb056` (current HEAD `9e2f357`).
**Supplements pinned slate sha256 baseline (pre-S8):** `13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344`.

These are the pre-S8 baselines. Post-S8 baselines will be documented in each `T*.5` summary file per the precedent set by S6 and S7.6.

---

## Appendix — Sprint-discipline reminders (CLAUDE.md, founder-locked 2026-05-22)

Every S8 refactor-engineer / DS-architect / IM dispatch MUST begin with the Subagent Handoff Discipline reading list:

1. `/Users/atul.jena/Projects/Personal/beaconai/ARCHITECTURE_PLAN.md` — all LOAD-BEARING UPDATE blocks chronologically, especially the 2026-05-24 S7.6 CLI-fix block.
2. `/Users/atul.jena/Projects/Personal/beaconai/memory.md` and `memory_archive.md`.
3. `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md` — all KI-NEW-* entries.
4. `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` — authoritative S6–S14 roadmap.
5. `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-s7_6-continuation-plan.md` and `implementation-manager-s7_6-observed-effect-wiring-plan.md` — S7.6 precedent for atomic flag-flip discipline.
6. This document — `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md`.

**Founder discipline locks:**
- "Never assume" — instrument and verify when a prediction conflicts with observed behavior.
- "Only follow the path that's decided" — no silent scope expansion. Part E Q4 (`pseudo_N` table) is the explicit STOP-and-escalate gate.
- "Single-demote-channel invariant" — no new injection blocks at `src/main.py:1380-1597` without explicit founder + DS sign-off.
- "Stop deferring things" — S8 ships its four tickets in ~2 weeks, no scope creep.

---

**End of plan. Founder review requested on Part E (7 open questions) before S8-T0 dispatch.**
