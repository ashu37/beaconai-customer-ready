# S6-T3 Summary — `replenishment_due` audience builder

**Ticket:** Sprint 6 Ticket T3 (per `agent_outputs/implementation-manager-s6-tier-b-builders-plan.md` §S6-T3 lines 215–268)
**Date:** 2026-05-19
**Branch:** post-6b-restructured-roadmap
**Impl commit:** `c37007d`
**Memory commit:** (sibling to this summary)
**Status:** Impl shipped flag-OFF. Mid-sprint audit triggered 4-sub-ticket sequence before T3.5 (atomic flag flip + re-pin) can land. T3.x re-key supersedes the as-shipped prior wiring per DS architect + PM audit 2026-05-19.

---

## 1. Approved scope (as shipped)

- New audience builder `replenishment_due_candidates` in `src/audience_builders.py`. Per-customer × per-SKU cadence inference with founder-locked N=30 customers-with-≥2-repeat-purchases floor (D-S6-4). Right-censored empirical median per SKU class (mirrors S6.5-T3 `compute_cadence_baseline` discipline). Tolerance window = half cadence median (D-S6-5).
- Beauty path consumes existing G-2-era beauty regex via `get_size_regex("beauty")`. Supplements path consumes the S6-T2 parser via `parse_unit_coherent("supplements", lineitem_text)`. Mixed path blends 50/50 per G-3 contract. Un-parseable SKUs skip from cadence inference (graceful None handling; aligns with S6-T2's 5/10 supplements coverage).
- New `_SUPPORTED["replenishment_due"]` entry in `src/measurement_builder.py`. **AS-SHIPPED:** prior-anchored pathway consumes `bestseller_amplify.bundle_value.beauty` validated_external bsandco prior per the (now-superseded) founder Q3 / D-S6-2 decision. Dormant under flag OFF.
- New `WouldBeMeasuredBy.REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW` enum value (additive within `event_version=1`).
- New `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` flag (default OFF) in `src/utils.py` DEFAULTS + `_BOOL_FLAGS`.
- Play Registry entry `vertical_applicability=frozenset({"beauty", "supplements", "mixed"})`.
- Forward-scaffolding `ranking_strategy: Optional[str] = None` kwarg on the new audience builder for S13 ML integration.

## 2. Patch summary

### `src/audience_builders.py`
New `replenishment_due_candidates(g, aligned, cfg, *, ranking_strategy=None) -> List[CandidateBlock]`. ~260 lines. Reads `cfg["_store_profile"]` for profile-aware audience floor (consults `gate_calibration.audience_floor_by_play_id["replenishment_due"]`; falls back to `_default_by_stage` via the S6.5-T4 default-cell path with provenance fire `gate_calibration_default_floor_used`).

### `src/measurement_builder.py`
New `_SUPPORTED["replenishment_due"]` dispatch via prior-anchored pathway. **As-shipped routes to bundle_value Beauty; T3.x re-key updates this routing before T3.5.**

### `src/engine_run.py`
Single-line enum addition. Schema additive.

### `src/main.py`
Candidate detection plumbed via the established `_detect_candidates` pattern. Gate on `cfg.get("ENGINE_V2_BUILDER_REPLENISHMENT_DUE", False)`. Flag default OFF; flag-OFF path is byte-identical to S6-T2 close.

### `src/play_registry.py`
New entry mirrors `winback_dormant_cohort` shape.

### `src/utils.py`
New flag in DEFAULTS + `_BOOL_FLAGS` coercion set.

### `tests/test_s6_t3_replenishment_due_builder.py` (NEW)
19 tests covering the 14 IM-plan items + 5 belt-and-suspenders extras. Coverage: cadence inference determinism (G-7); positive-projection per Beauty SKU; Beauty fires with audience > 0; supplements via T2 parser fires on the 5/10 parseable SKUs that clear N=30; below-N=30 SKU contributes zero without crash; flag-OFF builder not invoked; flag-ON Beauty PlayCard `evidence_class` matches prior `source_class`; flag-ON supplements `revenue_range.suppressed=True` under as-shipped wiring; `vertical_mode=mixed` blends 50/50; bayesian_blend numerics verified at cold-start (Q5 envelope: posterior p50 ∈ [prior.range_p10, prior.range_p90]); `WouldBeMeasuredBy` enum serializes; `source_artifact` threaded; M3 candidate contract intact (no stats/revenue at audience layer); right-censored customers (no repeat purchases) excluded; tolerance window = ½ cadence median pinned on synthetic data.

## 3. Files changed

- `src/audience_builders.py`
- `src/engine_run.py`
- `src/main.py`
- `src/measurement_builder.py`
- `src/play_registry.py`
- `src/utils.py`
- `tests/test_s6_t3_replenishment_due_builder.py` (new, 19 tests)
- `tests/test_engine_run_schema.py` (additive enum coverage)
- `tests/test_would_be_measured_by_enum.py` (new enum value pin)

## 4. Tests / checks run

- New test file: 19 passed.
- `tests/test_slate_regression_beauty_brand.py` + `tests/test_slate_regression_supplements_brand.py`: byte-identical sha256 pins held under flag OFF.
- `tests/test_golden_diff.py`: M0 trio byte-identical.
- Full suite: 1394p/14s/0f → 1416p/14s/0f. +22 tests, +0 regressions.

## 5. Behavior changes (today, under flag OFF)

**ZERO merchant-facing behavior change.** The new builder is gated; flag-OFF leaves Beauty + supplements + M0 fixtures byte-identical. The wiring becomes runtime-active at T3.5 atomic flip.

## 6. Mid-sprint audit pause (2026-05-19)

Before T3.5 ramp-up, the sub-agent flagged 3 open risks. Founder paused the sprint to invoke DS architect + PM audit on the broader `docs/DECISIONS.md` registry health and the 3 specific risks.

### Risk 1 — Dollar-vs-rate semantic on bundle_value prior

`bestseller_amplify.bundle_value.beauty` is per-customer DOLLARS ($45 / range $25-$75) per the bsandco bundle-promotion memo. The prior-anchored pathway computes `revenue_range = audience × posterior × aov`, so plugging a dollar-prior into a rate slot would produce nonsense on T3.5 flag-ON (`500 × $45 × $59 ≈ $1.3M`). Compare to S6.5-T5 winback activation where `winback_21_45.base_rate = 0.08` was correctly a rate.

**DS architect verdict:** STOP. The bsandco memo is anchored to bundle-promotion economics, not replenishment-cadence conversion. Re-purposing it would invalidate the `validated_external` claim across all 3 priors that currently anchor the trust foundation. Options (b) suppress chip / (c) skip-AOV-multiplier-when-prior-key-is-bundle_value are both hacks — option (b) hides the bug, option (c) encodes "this prior key is special" as a code-path branch (fabricated rigor). Option (a) — re-key to a dedicated `replenishment_due.base_rate` block — is the only honest path.

### Risk 2 — Supplements path uses generic Considered, not typed PRIOR_UNVALIDATED

S6.5-T5 supplements winback shape was typed `PRIOR_UNVALIDATED` because both verticals had a `winback_21_45.base_rate` block (Beauty validated_external; supplements heuristic_unvalidated). For `replenishment_due` as-shipped, supplements has NO `bundle_value` block at all (T3 ticket forbade new YAML authoring), so supplements hits a different code branch and routes to generic Considered. "Supplements never in Recommended Now" invariant holds but reason code differs.

**DS architect verdict:** Accept the asymmetric reason codes. Dissolves under Risk 1 re-key — both verticals route symmetrically under the new `replenishment_due.base_rate` block. Do not author a supplements stub purely for code-symmetry — that would fabricate priors to satisfy code shape.

### Risk 3 — N=30 floor unverified on real G-1 supplements fixture

Sub-agent tested synthetic supplements data only. Unknown whether ANY supplements SKU clears N=30 on the actual G-1 cohort. If zero clear, T3.5 supplements card-count delta is zero.

**DS architect verdict:** N=30 is defensible heuristic (Wilks-style "stable empirical-median regime" threshold, but not specifically derived for this problem). Verify against G-1 in T3.x. If <3 SKUs clear, lower to N=15 with typed `LOW_CONFIDENCE_CADENCE` flag.

### Path A unlocked — 2026-05-19 Gemini Deep Research

Founder ran a Deep Research task targeting the dedicated `replenishment_due.base_rate.beauty` benchmark. Result returned **validated_external** at `value=0.0220 / range_p10=0.0120 / range_p90=0.0430 / effective_n=30`. Converging Tier-1 sources: Klaviyo PERL Cosmetics case study (replenishment-isolated 2.20%) + Klaviyo 2026 Omnichannel Benchmark Report H&B vertical (cross-flow average 1.96% across 183K+ brands). Tight mathematical alignment validates the 2.20% as a reliable starting point. Memo includes explicit §3 "what this does NOT measure" + §5 limitations (store-wide attribution inflation, flow aggregation bias, email vs SMS channel discrepancy, fixed-interval errors) + §6 (3 alternative sources rejected with rationale). Memo saved verbatim to `config/priors_sources/replenishment_due__base_rate__beauty.md` in commit `011c7cc` BEFORE any downstream wiring per process discipline.

**Consequence:** T3.5 now ships WITH Beauty activation. The audit-recommended path A (re-key + heuristic_unvalidated supplements) became path A (re-key + validated_external Beauty + heuristic_unvalidated supplements). Stronger outcome than DS architect's recommendation projected.

## 7. 5-ticket sequence locked (2026-05-19)

| # | Ticket | Scope | Status |
|---|---|---|---|
| 1 | S6-T3 closeout (this summary + memory.md) | Documentation of audit outcome | In flight |
| 2 | S6-T3.x re-key | priors.yaml: author `replenishment_due.base_rate.beauty` validated_external with source_artifact; supersede D-S6-2 in DECISIONS.md; verify N=30 G-1 probe (Risk 3); file 6 post-beta KIs (KI-NEW-A..F from PM verdict) | Pending |
| 3 | S6-T3.y | Audience-floor sensitivity driver on validated-path PlayCards (closes DS architect "firewall leak") | Pending |
| 4 | S6-T3.z | Considered surface render pass (closes PM beta-critical UX gap) | Pending |
| 5 | S6-T3.5 | Atomic flag flip + Beauty + supplements re-pin. Beauty `replenishment_due` lands in Recommended Now against new validated_external prior; supplements stays in Considered with PRIOR_UNVALIDATED. Second activation moment. | Pending |

## 8. Founder decisions consumed (per `docs/DECISIONS.md`)

- **D-S6-2** (founder Q3): `replenishment_due` consumes `bestseller_amplify.bundle_value.beauty`. **STATUS: SUPERSEDED by T3.x re-key (2026-05-19) per DS architect audit.** New decision: author dedicated `replenishment_due.base_rate.beauty` validated_external block backed by 2026-05-19 Gemini Deep Research memo.
- **D-S6-3** (founder Q5): T3.5 hard-stop = posterior p50 ∈ [prior.range_p10, prior.range_p90]. ACTIVE; unchanged.
- **D-S6-4** (founder Q2): N=30 customers-with-≥2-repeats per-SKU floor. ACTIVE; pending T3.x G-1 verification.
- **D-S6-5**: Tolerance window = ½ cadence median. ACTIVE.

## 9. Hard-stop status

| # | Hard-stop | Status |
|---|---|---|
| 1 | Beauty produces zero audience | NOT TRIPPED |
| 2 | Beauty posterior p50 outside [prior.p10, prior.p90] | PASS (cold-start; under as-shipped wiring, dormant) |
| 3 | Supplements lands in Recommended Now | NOT TRIPPED (gated by PRIOR_UNVALIDATED refusal logic) |
| 4 | Pinned fixture sha256 shifts under flag OFF | NOT TRIPPED (5 pinned fixtures byte-identical) |
| 5 | Cadence inference non-deterministic | NOT TRIPPED (G-7 contract intact, pinned by test) |
| 6 | Parser regression on supplements | NOT TRIPPED (S6-T2 5/10 coverage pinned by test) |

## 10. Invariants preserved

- D-5 / D-6 / D-8 intact (no Shopify/Klaviyo, no banned ML modules, vertical scope unchanged).
- B-4 role-uniqueness intact.
- B-5 Berkson invariant intact.
- S-2..S-6 substrate write paths untouched.
- Schema-additive only within `event_version=1` (new enum value only).
- S7.5-T3 validated-vs-heuristic refusal logic UNCHANGED.
- No new runtime deps.
- Forward-scaffolding for S13 ML integration preserved (`ranking_strategy=None` kwarg).

## 11. Commit list

1. `c37007d` — `S6-T3: replenishment_due audience builder + measurement_builder _SUPPORTED entry + WouldBeMeasuredBy enum + flag default OFF` (impl; landed 2026-05-18 with open-risk callout in commit message)
2. (sibling to this summary) — `Document S6-T3 in repo memory.md`
3. (this summary) — `S6-T3 summary + audit pause documentation`

## 12. Hand-off to T3.x

T3.x must:
1. Author `replenishment_due.base_rate.beauty` block in `config/priors.yaml` at `validated_external` with `source_artifact: config/priors_sources/replenishment_due__base_rate__beauty.md`, `value: 0.0220`, `range_p10: 0.0120`, `range_p90: 0.0430`, `effective_n: 30`.
2. Update `_SUPPORTED["replenishment_due"]` dispatch in `src/measurement_builder.py` to consume `replenishment_due.base_rate` (not `bestseller_amplify.bundle_value`).
3. Supersede D-S6-2 in `docs/DECISIONS.md` with explicit `Superseded by` line + new D-S6-2.1 entry citing the re-key.
4. Verify N=30 floor against G-1 supplements (Risk 3 probe). If <3 SKUs clear, lower to N=15 + typed flag.
5. File 6 post-beta KIs (KI-NEW-A through KI-NEW-F per PM verdict): seasonality validation, audience floor recalibration, pseudo_n recalibration, token vocabulary audit, stage band continuous-uncertainty, subvertical threshold recalibration.
6. Demote DECISIONS.md framing per DS architect Category C verdict (D-S6.5-12 stage bands, D-S6.5-17 token dictionary, D-S6.5-18 subvertical thresholds, D-S6.5-19 seasonality windows, D-S7.5-3 pseudo_n cap from "derived/validated" to "MVP posture / tunable").

After T3.x, T3.y ships audience-floor sensitivity driver (closes DS architect firewall leak), T3.z ships Considered surface render pass (closes PM beta-critical UX gap), T3.5 ships the atomic flag flip + Beauty + supplements re-pin with the second activation moment.

## Backfill from memory.md (migration trim 2026-05-25)

## S6-T3 closeout (2026-05-19)

Sprint 6 Ticket T3 — `replenishment_due` audience builder shipped, flag default OFF. Impl commit `c37007d`. **Open-risk callout in commit message escalated to DS architect + PM audit on 2026-05-19** (see "Mid-sprint audit pause" below).

**What shipped:**

- `src/audience_builders.py::replenishment_due_candidates` — per-customer × per-SKU cadence inference with N=30 floor (founder Q2, D-S6-4); right-censored empirical median; tolerance window = ½ cadence median (D-S6-5); ranking_strategy=None forward-scaffolding kwarg for S13 ML integration. Beauty path consumes G-2 era beauty regex; supplements path consumes S6-T2 `parse_unit_coherent`; mixed blends 50/50 per G-3.
- `src/measurement_builder.py::_SUPPORTED["replenishment_due"]` — prior-anchored pathway. **WIRING AS-SHIPPED routed to bestseller_amplify.bundle_value.beauty per founder Q3 / D-S6-2.** Superseded by T3.x re-key (see below); the as-shipped wiring is dormant under flag OFF.
- `src/engine_run.py` — new `WouldBeMeasuredBy.REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW` enum value (additive, `event_version=1` intact).
- `src/main.py` — candidate detection plumbed; gated on `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` (default OFF).
- `src/play_registry.py` — new entry `vertical_applicability={beauty, supplements, mixed}`.
- `src/utils.py` — new flag registered in DEFAULTS + `_BOOL_FLAGS`.

**Tests:** 19 new in `tests/test_s6_t3_replenishment_due_builder.py`. Cadence inference deterministic (G-7); audience builder fires on Beauty + supplements via T2 parser; below-N=30 SKU contributes zero without crash; flag-OFF invariant pinned; bayesian_blend numerics verified; Q5 envelope check (posterior p50 ∈ [prior.range_p10, prior.range_p90]) holds at cold-start. Suite: 1394p → 1416p / 14s / 0f.

**Pinned fixtures:** all 5 byte-identical under flag-OFF (Beauty + supplements G-1 + 3× M0). T3.5 owns atomic re-pin.

**Mid-sprint audit pause (2026-05-19):**

Sub-agent flagged 3 open risks before T3.5 ramp-up: (1) `bestseller_amplify.bundle_value.beauty` is per-customer dollars ($45), not a rate — multiplying by AOV double-counts on T3.5 flag-ON; (2) supplements lacks a `bundle_value` block so routes to generic Considered, not typed PRIOR_UNVALIDATED matching S6.5-T5 winback shape; (3) N=30 floor unverified on real G-1 supplements fixture. Founder paused Sprint 6 to invoke DS architect + PM audit on the broader DECISIONS.md registry health.

**DS architect verdict (memo returned 2026-05-19, full text in conversation transcript):** Registry structurally honest but epistemically shallow. Sprint 7.5's PRIOR_UNVALIDATED refusal logic is the firewall preventing heuristic stacks from reaching merchant-facing dollar projections. Of 22 decisions, ~3 defensible postures + ~5 reasonable MVP defaults + **1 category error** (D-S6-2 bundle_value-as-replenishment). Risk 1 verdict: STOP, re-key to `replenishment_due.base_rate` block; bundle_value memo is anchored to bundle-promotion economics, not replenishment-cadence conversion. Re-purposing it would invalidate the validated_external claim across all 3 priors. 11 heuristic layers from CSV → Recommended Now slot, mostly inside the firewall on validated paths; one named leak (audience-floor uncertainty silently inheriting into dollar projection).

**PM verdict (returned 2026-05-19):** Agrees with DS architect's verdict; diverges on timing — defer external memo authoring to S7/S8 rather than pause Sprint 6. Adds two PM-specific catches the DS audit missed: (1) Considered surface is now beta-critical UX (supplements stays ABSTAIN_SOFT with 6 Considered today; merchant who sees 0 Recommended Now won't return month-2 unless Considered communicates progress); (2) "month-2 return" engine isn't Phase 9, it's the ML predictive layer (S10-S13) — without Phase 9, `posterior = prior` at n_observed=0, cards barely move month-1 → month-2.

**Founder direction (2026-05-19):** Go with DS architect path. 5-ticket sequence locked: T3 closeout (this) → T3.x re-key → T3.y audience-floor sensitivity driver → T3.z Considered render pass → T3.5 atomic flag flip + re-pin. Both PM catches fold into S6 scope per founder Q (T3.y + T3.z stay in sprint, ~+2 days).

**Path A unlocked by 2026-05-19 Gemini Deep Research:** External research returned `replenishment_due.base_rate.beauty = 0.0220` at validated_external status with converging Tier-1 sources (Klaviyo PERL Cosmetics case study 2.20% + Klaviyo H&B 2026 cross-flow average 1.96% across 183K+ brands). Memo saved verbatim to `config/priors_sources/replenishment_due__base_rate__beauty.md` in commit `011c7cc` BEFORE any wiring. T3.5 will ship WITH Beauty activation against the new validated_external prior (DS architect's option A path with stronger outcome than expected).

**Caveats / what T3 does NOT do:**

- The as-shipped `_SUPPORTED["replenishment_due"]` wiring routes to bundle_value per the (now-superseded) D-S6-2 decision. T3.x re-key supersedes this in priors.yaml + measurement_builder dispatch BEFORE T3.5 flag flip. The as-shipped wiring is dormant under flag OFF, so no incorrect behavior is reachable.
- Risk 2 (supplements lacks bundle_value block) dissolves under T3.x re-key — both verticals route symmetrically under the new `replenishment_due.base_rate` block (Beauty validated_external; supplements heuristic_unvalidated). DS architect explicitly advised against authoring a supplements stub for code-symmetry — the asymmetric reason code is informative.
- Risk 3 (N=30 on G-1 supplements) verified in T3.x probe.

**Summary:** [agent_outputs/code-refactor-engineer-s6-t3-summary.md](agent_outputs/code-refactor-engineer-s6-t3-summary.md)
