# Sprint 6 — First Two Tier-B Builders + Supplements Parser

**Author:** implementation-manager
**Date:** 2026-05-17
**Branch baseline:** post-6b-restructured-roadmap, post-S7.5-T3.5 close
**Status:** Plan-only (no `src/` edits). Tickets sized for code-refactor-engineer.

---

## 1. Sprint 6 overview

### Anchor goal
Ship `winback_dormant_cohort` and `replenishment_due` as the first two Tier-B builders end-to-end, consuming validation-status-aware priors from Sprint 7.5; close at least KI-18 along the way via a supplements serving-count parser.

### Why this sprint follows S7.5 — the activation moment
Sprint 7.5 installed the priors-validation contract (closed-enum `validation_status`, `source_artifact`, `effective_n`, `PSEUDO_N_BY_STATUS`, `bayesian_blend`) and flipped `ENGINE_V2_PRIORS_VALIDATION` to default-ON. The contract is dormant on today's fixtures because no card on the V2 path consumes a base-rate / bundle-value prior of any validation status — the only directional pathway (`first_to_second_purchase`) uses the L28 returning-customer-share signal, not the prior. Sprint 6 is when the contract activates: the first `winback_dormant_cohort` card on Beauty will consume `winback_21_45.base_rate` (validated_external) via `bayesian_blend(pseudo_n=30, ...)` and emit a non-suppressed `revenue_range` with `source=blend` citing the Klaviyo H&B 2026 artifact. That single posterior is the load-bearing payoff of S7.5 plus S6 combined — and it is also why this sprint is structurally invasive (every fixture that gets a new card needs an atomic re-pin).

### Duration estimate
**~7 working days** across 5 tickets:
- S6-T1 (~2d) + S6-T1.5 (~0.5d) — first bundle
- S6-T2 (~2d) + S6-T3 (~2d) + S6-T3.5 (~0.5d) — second + third bundle

### Beta-blocking status
**Not beta-blocking.** Founder testing only per Phase 6A Final Review caveats; flags ship default OFF on impl tickets, default ON only after the atomic re-pin tickets land. External beta still blocked by the Phase 6A caveats 1–6 (separate gating).

### Schema additions table

| Field / enum addition | Surface | Where | Validation-status interaction |
|---|---|---|---|
| `WouldBeMeasuredBy.WINBACK_REACTIVATION_RATE` (or similar) | `WouldBeMeasuredBy` enum | `src/engine_run.py` or A2 enum module | New PlayCard `would_be_measured_by` value for `winback_dormant_cohort` |
| `WouldBeMeasuredBy.REPLENISHMENT_REPURCHASE_RATE` (or similar) | `WouldBeMeasuredBy` enum | same | New PlayCard `would_be_measured_by` value for `replenishment_due` |
| `_SUPPORTED["winback_dormant_cohort"]` | measurement_builder | `src/measurement_builder.py` ~L108 | Builder consumes `winback_21_45.base_rate` (Beauty validated_external) → `bayesian_blend`; supplements path resolves to heuristic_unvalidated → revenue_range suppressed under S7.5-T3.5 rule |
| `_SUPPORTED["replenishment_due"]` | measurement_builder | same | Builder consumes `bestseller_amplify.bundle_value` (Beauty validated_external) OR a play-specific prior if authored; supplements uses heuristic_unvalidated → suppressed |
| New audience-builder fns | `src/audience_builders.py` | `winback_dormant_cohort_candidates`, `replenishment_due_candidates` | None — audience layer is prior-agnostic |
| `RevenueRange.drivers[].source_artifact_ref` (optional, if not already present from S7.5-T2) | `RevenueRange.drivers` provenance | `src/engine_run.py` | Threads the `validated_external` source_artifact filename onto the driver entry for merchant-facing receipts |
| Supplements serving-count parser output fields | `config/replenishment_sizes.yaml` supplements block | New unit-coherent parser API in `src/replenishment_parser.py` | None — parser is below the priors layer |

**All additions are `Optional` with backward-compatible defaults. `event_version=1` frozen.**

### Feature flags introduced

| Flag | Default | Introduced in | Flipped ON in | Removed at |
|---|---|---|---|---|
| `ENGINE_V2_BUILDER_WINBACK_DORMANT` | OFF | S6-T1 | S6-T1.5 | S8 Play Library fold (no earlier) |
| `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` | OFF | S6-T3 | S6-T3.5 | S8 Play Library fold |
| (no new flag for the parser — S6-T2 is flagless if zero behavior change on Beauty; flag-gated only if existing supplements paths shift) |  |  |  |  |

### Fixture re-pin schedule

| Ticket | Fixture(s) re-pinned | Card-count delta | Notes |
|---|---|---|---|
| S6-T1 | none (flag default OFF) | n/a | Impl-only; tests build inputs in-memory |
| S6-T1.5 | Beauty pinned slate + supplements G-1 (both, atomically with flag flip) | Beauty: +1 Recommended Now (winback validated_external blend, non-suppressed $ range); supplements: +1 Considered card (heuristic_unvalidated → suppressed range; reason `no_measured_signal` or new typed code if added) | Beauty `5fa9f697...`/`dcb45cee...` → new sha; supplements `01f5feff84...` → new sha |
| S6-T2 | possibly supplements G-1 (only if parser changes existing supplements behavior — e.g., un-suppresses an `empty_bottle` clean-skip via KI-27) | parser coverage: capsule/serving SKU counts populate in receipts; no card changes unless KI-27 closes | If KI-27 stays open, supplements fixture stays byte-identical |
| S6-T3 | none (flag default OFF) | n/a | Impl-only |
| S6-T3.5 | Beauty pinned slate + supplements G-1 (both, atomically with flag flip) | Beauty: +1 card (either Recommended Now or Recommended Experiment depending on consistency_across_windows); supplements: +1 Considered or +1 Recommended Now if the new S6-T2 parser yields cadence-coherent audience and a directional signal exists | Both fixtures get a new sha; document per-fixture before/after card counts in summary |

### Behavior changes by ticket boundary

| Ticket | Behavior change on Beauty fixture | Behavior change on supplements fixture | M0 small_sm/mid_shopify/micro_coldstart |
|---|---|---|---|
| S6-T1 | NO (flag OFF) | NO (flag OFF) | byte-identical |
| S6-T1.5 | YES (+1 card) | YES (+1 card) | byte-identical (M0 fixtures do not exercise winback audience size) |
| S6-T2 | NO (parser is supplements-vertical-gated) | maybe (only if KI-27 closes) | byte-identical |
| S6-T3 | NO (flag OFF) | NO (flag OFF) | byte-identical |
| S6-T3.5 | YES (+1 card) | YES (+1 card) | byte-identical |

---

## 2. Per-ticket plan

### S6-T1 — `winback_dormant_cohort` builder (impl, flag default OFF)

**Scope:**
- New audience builder `winback_dormant_cohort_candidates` in `src/audience_builders.py` following the existing `AudienceResult` contract (Beauty: 21–45 day dormancy window per Part I §B-1; Supplements: 60–120 day window — vertical-gated inside the builder by reading `cfg["vertical_mode"]` or equivalent).
- New `_SUPPORTED["winback_dormant_cohort"]` entry in `src/measurement_builder.py` (~L108), wiring the audience to a `bayesian_blend`-aware measurement card. Reads `winback_21_45.base_rate` via `priors_loader.get_prior(..., vertical=...)`, computes posterior under `PSEUDO_N_BY_STATUS[validation_status]`.
- New `WouldBeMeasuredBy` enum value (UPPER_SNAKE_CASE per A2 invariant).
- Wire builder into `src/main.py::run` shadow detection / candidate emission, gated by `ENGINE_V2_BUILDER_WINBACK_DORMANT` env flag (default OFF). When OFF, engine path is byte-identical to S7.5-T3.5.
- New flag added to `src/utils.py::get_config` (or wherever flag-reading lives) with the existing precedence pattern.
- Play Registry entry for `winback_dormant_cohort` (if not already present from prior phases — verify; M2 registry had 14 plays).
- `vertical_applicability` set on the registry entry: `frozenset({"beauty", "supplements", "mixed"})`.

**Acceptance criteria:**
- [ ] Builder runs end-to-end on Beauty + supplements fixtures under `ENGINE_V2_BUILDER_WINBACK_DORMANT=true`; produces a `PlayCard` with `evidence_class` consistent with the prior's `source_class` (today both promoted priors are `observational` → `directional`, NOT `measured`; under S7.5-T3.5 rule-replacement the validated_external status permits a non-suppressed blend).
- [ ] When flag OFF, every existing fixture sha256 is byte-identical to S7.5-T3.5 close.
- [ ] Audience floors per-vertical: Beauty default falls back to `_safe_int_cfg`-driven floor; supplements uses `get_audience_floor("winback_dormant_cohort", "supplements")` if metadata authored, else the registry default.
- [ ] Builder respects M3 "no stats, no revenue" contract on the candidate object itself — sizing happens in `_SUPPORTED` path.
- [ ] Beauty audience size is >= floor on the pinned fixture (founder-confirmed envelope; hard-stop if <30 customers).
- [ ] Posterior p50 lands inside the `winback_21_45.base_rate` prior's `[range_p10, range_p90]` envelope on Beauty (sanity calibration — see hard-stop §3).
- [ ] No M-invariant regression: B-5 Berkson invariant test passes; M0 goldens byte-identical.

**Test deliverables:**
- `tests/test_s6_t1_winback_dormant_cohort_builder.py` — 12 tests:
  1. Builder fires on Beauty fixture with audience >= floor
  2. Builder fires on supplements fixture with audience >= supplements floor
  3. Beauty vertical window is 21–45d (boundary test on synthetic data)
  4. Supplements vertical window is 60–120d
  5. Flag OFF ⇒ builder not invoked (zero new candidates in shadow)
  6. Flag ON Beauty: PlayCard has `evidence_class=DIRECTIONAL`, `revenue_range.source="blend"`, `revenue_range.suppressed=False`
  7. Flag ON supplements: PlayCard has `revenue_range.suppressed=True` (heuristic_unvalidated refusal under T3.5 rule-replacement)
  8. Posterior p50 inside prior's [p10, p90] envelope on Beauty
  9. `WouldBeMeasuredBy` enum value present + UPPER_SNAKE_CASE
  10. `source_artifact` threaded onto `revenue_range.drivers[0]` for validated_external Beauty path
  11. Candidate object carries no p/q/revenue/effect fields (M3 contract)
  12. `vertical_mode=mixed` blends beauty+supplements priors per G-3 `resolve_mixed_prior`
- Aim for 1213 → 1225p suite count.

**Schema additions:** `WouldBeMeasuredBy.<NEW_VALUE>` (1 enum addition); `_SUPPORTED` entry (1 dict key); registry entry edits.

**Fixture re-pin:** NONE (flag OFF).

**Behavior change:** NO.

**Dependencies:** S7.5-T3.5 closed; G-3 `resolve_mixed_prior`.

**Estimated duration:** ~2 days.

**Commit boundary (3 commits per S5/S7.5 pattern):**
1. Impl commit: `src/audience_builders.py`, `src/measurement_builder.py`, `src/engine_run.py` (enum), `src/main.py` (flag wiring), `src/play_registry.py` (if needed), `tests/test_s6_t1_winback_dormant_cohort_builder.py`, `config/priors.yaml` (if new `winback_dormant_cohort.*` metadata authored).
2. `Document S6-T1 in repo memory.md`
3. `S6-T1 summary` → `agent_outputs/code-refactor-engineer-s6-t1-summary.md`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s6-t1-summary.md`

---

### S6-T1.5 — Flip `ENGINE_V2_BUILDER_WINBACK_DORMANT` ON + atomic fixture re-pin

**Scope:**
- Single atomic commit: flag default flip OFF → ON in `src/utils.py` AND both pinned fixtures (Beauty + supplements G-1) re-pinned with new sha256 constants.
- Per S3 / S5-T2 / S7.5-T3.5 pattern: re-pin discipline same as flag-flip-and-fixture-shift bundle.
- New regression tests for the activation moment.

**Acceptance criteria:**
- [ ] Beauty pinned slate sha256 updates from `dcb45cee...` (or current value, whatever sticks at S7.5-T3.5 close) to a new pinned constant; diff scope = 1 added Recommended Now card for `winback_dormant_cohort` with non-suppressed $ range and Klaviyo source_artifact chip in drivers.
- [ ] Supplements G-1 fixture sha256 updates from `01f5feff84...` to new constant; diff scope = 1 added Considered card with `reason_code` reflecting heuristic_unvalidated suppression.
- [ ] M0 goldens byte-identical (audience-size floor blocks the builder on M0 fixtures' small / cold-start cohorts).
- [ ] Beauty card's `revenue_range.p50` matches `bayesian_blend(prior_value=0.14, pseudo_n=30, store_value=<observed>, n_observed=<audience>)` to 4 decimal places.
- [ ] Beauty card's `revenue_range.drivers` includes a driver with `source="vertical_prior"` referencing the Klaviyo `source_artifact`.

**Test deliverables:**
- `tests/test_s6_t1_5_winback_dormant_repin.py` — 6 tests:
  1. Beauty new sha256 pin
  2. Supplements G-1 new sha256 pin
  3. M0 goldens byte-identical
  4. Beauty winback card's posterior numerics match `bayesian_blend`
  5. Beauty winback card's `source_artifact` matches the YAML's pointer
  6. Supplements winback card's `revenue_range.suppressed=True`
- Aim for 1225 → 1231p.

**Schema additions:** none (T1 already shipped them).

**Fixture re-pin:** YES — Beauty + supplements G-1 atomically with flag flip in the SAME commit (S3 Risk #4 discipline).

**Behavior change:** YES.

**Dependencies:** S6-T1.

**Estimated duration:** ~0.5 days.

**Commit boundary:**
1. Atomic commit: `src/utils.py` flag flip + `tests/test_slate_regression_*.py` sha pins + `tests/test_s6_t1_5_winback_dormant_repin.py`.
2. `Document S6-T1.5 in repo memory.md`
3. `S6-T1.5 summary`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s6-t1_5-summary.md`

---

### S6-T2 — Supplements serving-count parser (closes KI-18; KI-27 close-if-coverage)

**Scope:**
- Author supplements regex/parser block in `config/replenishment_sizes.yaml` (today's supplements stub is null per G-2). Coverage target: serving-per-container (e.g., `30 servings`, `60 ct`, `120 capsules`, `90 caps`, `30 ct`, `30-day supply`, `60-day supply`), with unit-coherence keys `serving` / `count` / `day_supply`.
- Extend `src/replenishment_parser.py` dispatcher to handle the supplements block.
- New parser-coverage assertions on the G-1 supplements fixture SKUs (positive-projection test pinning extraction per SKU).
- Flip `empty_bottle.vertical_applicable` to include `supplements` ONLY if coverage is sufficient AND founder confirms; otherwise leave G-2 contract intact and document KI-27 close criteria deferred.
- Pure parser work — no audience builder, no measurement card. Below the priors layer.

**Acceptance criteria:**
- [ ] All SKUs in the G-1 supplements fixture extract a coherent serving/count/day_supply; assertion is positive-projection (failure = test failure, not silent fall-through to None).
- [ ] Parser is pure (no I/O beyond YAML load, idempotent, deterministic).
- [ ] KI-18 flipped `tracked` → `resolved` in `KNOWN_ISSUES.md`.
- [ ] KI-27 close decision documented: if parser coverage ≥ founder threshold (default: every SKU in the pinned supplements fixture parses) AND founder confirms, KI-27 flipped `accepted` → `resolved`; else KI-27 stays `accepted` with a note that S6-T2 closed the parser but not the `empty_bottle.vertical_applicable` expansion.
- [ ] Supplements G-1 fixture stays byte-identical (parser produces data that isn't yet consumed end-to-end until S6-T3 wires it).

**Test deliverables:**
- `tests/test_s6_t2_supplements_serving_parser.py` — 15 tests:
  1–10. Per-SKU positive-projection extraction (10 SKUs in supplements fixture)
  11. Day-supply variant parses
  12. Serving-count variant parses
  13. Capsule-count variant parses
  14. Unknown / un-parseable supplement SKU returns None (not crash)
  15. Beauty SKUs still parse via the existing beauty regex block (no cross-contamination)
- Aim for 1231 → 1246p.

**Schema additions:** none in `engine_run.json`; YAML-only extension to `config/replenishment_sizes.yaml`.

**Fixture re-pin:** conditional. Default: NO. If KI-27 closes and `empty_bottle.vertical_applicable` is expanded to include supplements, supplements G-1 may gain a Considered/Recommended card for `empty_bottle` — that re-pin lands inside this ticket atomically.

**Behavior change:** default NO; conditional YES if KI-27 closes.

**Dependencies:** S6-T1.5 closed (clean baseline); G-2 parser dispatcher already in place.

**Estimated duration:** ~2 days.

**Commit boundary:**
1. Impl commit: `config/replenishment_sizes.yaml`, `src/replenishment_parser.py`, `tests/test_s6_t2_supplements_serving_parser.py`, optional fixture re-pin + `KNOWN_ISSUES.md` flips.
2. `Document S6-T2 in repo memory.md`
3. `S6-T2 summary`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s6-t2-summary.md`

---

### S6-T3 — `replenishment_due` builder (impl, flag default OFF)

**Scope:**
- New audience builder `replenishment_due_candidates` in `src/audience_builders.py`. Logic: per-customer SKU repurchase cadence inference. Required minimum: ≥2 repeat purchases per customer for ≥30 customers per SKU (founder-confirm — see §6 Q2). Audience = customers whose most-recent purchase of an SKU has reached the inferred cadence ± tolerance window.
- Beauty path: consume existing replenishment parser (G-2 era beauty regex).
- Supplements path: consume the S6-T2 parser (serving/count/day_supply).
- New `_SUPPORTED["replenishment_due"]` entry in `src/measurement_builder.py`. Prior consumption depends on which prior is most defensible — start with `bestseller_amplify.bundle_value` (validated_external for Beauty) OR a new prior key authored under `replenishment_due.base_rate`. Founder to confirm prior selection (§6 Q3).
- New `WouldBeMeasuredBy` enum value.
- Wire under `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` flag (default OFF).
- Play Registry entry; `vertical_applicability=frozenset({"beauty","supplements","mixed"})`.

**Acceptance criteria:**
- [ ] Builder produces non-empty audience on both Beauty and supplements fixtures when `ENGINE_V2_BUILDER_REPLENISHMENT_DUE=true`.
- [ ] Cadence inference is deterministic (G-7 seed-all contract preserved).
- [ ] Per-SKU minimum sample size (N=30 customers with ≥2 repeats) enforced; SKUs below threshold contribute zero audience without crash.
- [ ] When flag OFF, every fixture sha256 byte-identical to S6-T2 close.
- [ ] Supplements path uses S6-T2 parser output; Beauty path uses pre-existing beauty regex.
- [ ] Posterior p50 inside prior's [p10, p90] envelope on Beauty.
- [ ] Builder respects M3 candidate contract (no stats/revenue at audience layer).

**Test deliverables:**
- `tests/test_s6_t3_replenishment_due_builder.py` — 14 tests:
  1. Builder fires on Beauty with N≥30 SKUs
  2. Builder fires on supplements with N≥30 SKUs via T2 parser
  3. SKU below N=30 threshold contributes zero audience (no crash)
  4. Cadence inference deterministic across 2 runs (G-7)
  5. Flag OFF ⇒ builder not invoked
  6. Flag ON Beauty: PlayCard `evidence_class` matches prior `source_class`
  7. Flag ON supplements: revenue_range.suppressed=True (heuristic_unvalidated)
  8. `vertical_mode=mixed` blends 50/50 per G-3
  9. Posterior numerics match `bayesian_blend` formula
  10. `WouldBeMeasuredBy` enum value present
  11. `source_artifact` threaded for validated_external paths
  12. Candidate object carries no forbidden fields
  13. Audience excludes customers with no repeat purchases
  14. Tolerance window (cadence ± founder-confirmed days) respected on synthetic data
- Aim for 1246 → 1260p.

**Schema additions:** `WouldBeMeasuredBy.<NEW_VALUE>` (1 enum); `_SUPPORTED` entry; potentially new `replenishment_due.*` block in `config/priors.yaml` if prior is authored fresh (founder Q3).

**Fixture re-pin:** NONE (flag OFF).

**Behavior change:** NO.

**Dependencies:** S6-T1.5, S6-T2.

**Estimated duration:** ~2 days.

**Commit boundary:**
1. Impl commit: `src/audience_builders.py`, `src/measurement_builder.py`, `src/engine_run.py`, `src/main.py`, `src/play_registry.py`, `config/priors.yaml` (if new prior), tests.
2. `Document S6-T3 in repo memory.md`
3. `S6-T3 summary`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s6-t3-summary.md`

---

### S6-T3.5 — Flip `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` ON + atomic fixture re-pin (closes Sprint 6)

**Scope:** mirror of S6-T1.5 for replenishment_due.

**Acceptance criteria:**
- [ ] Beauty + supplements G-1 sha256 re-pinned in same commit as flag flip.
- [ ] Per-fixture before/after card counts documented in summary doc.
- [ ] M0 goldens byte-identical.
- [ ] Beauty card posterior numerics match `bayesian_blend`.
- [ ] If supplements posterior is suppressed under heuristic_unvalidated rule, card lands in Considered with typed reason code; if a new `SUPPLEMENT_PRIOR_UNVALIDATED` reason is needed, add it additively per S5-T2 pattern.

**Test deliverables:**
- `tests/test_s6_t3_5_replenishment_due_repin.py` — 7 tests:
  1. Beauty sha256 new pin
  2. Supplements sha256 new pin
  3. M0 byte-identical
  4. Beauty posterior matches `bayesian_blend`
  5. Beauty source_artifact present
  6. Supplements suppression contract pinned
  7. Card-count delta per fixture pinned
- Aim for 1260 → 1267p.

**Schema additions:** none (T3 shipped them); optional new `ReasonCode` enum value if supplements path needs typed reason.

**Fixture re-pin:** YES.

**Behavior change:** YES.

**Dependencies:** S6-T3.

**Estimated duration:** ~0.5 days.

**Commit boundary:**
1. Atomic commit: flag flip + fixture pins + tests + optional ReasonCode enum addition.
2. `Document S6-T3.5 in repo memory.md`
3. `S6-T3.5 summary` (Sprint 6 closeout doc)

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s6-t3_5-summary.md`

---

## 3. Risk register for Sprint 6

| # | Risk | Mitigation | Observability hook |
|---|---|---|---|
| R1 | **Builder Type I (false fires on noisy small cohorts).** Beauty fixture has small per-SKU repeat-buyer counts; cadence inference could fire on coincidental clusters. | Hard floor: N=30 customers with ≥2 repeats per SKU before that SKU contributes. Audience floor at play level via `get_audience_floor`. Founder-confirmed envelope check in S6-T1 / T3 acceptance. | New test asserts audience > floor; positive-projection on Beauty fixture pinned audience size. |
| R2 | **Builder Type II (silent on real signal).** Supplements cadences (28–45d) plus the 60–120d winback window could leave a window gap that misses real dormant customers. | Vertical-specific windows authored in builder (Beauty 21–45 / Supplements 60–120 per Part I §B-1). Founder-confirm windows in §6 Q1. | Per-fixture audience-size pin (S6-T1.5 / T3.5) makes silent regression detectable on re-pin. |
| R3 | **KI-19 conservative-min on `mixed` blends.** Beauty winback validated_external + supplements winback heuristic_unvalidated → under T3.5 rule-replacement, the blended prior's validation_status defaults to the most-conservative side (heuristic_unvalidated), suppressing revenue_range under `vertical_mode=mixed`. | This is the correct conservative posture per S7.5-T1 caveat (blended entries default to HEURISTIC_UNVALIDATED). Document explicitly in S6-T1 summary so a future "fix" doesn't soften the rule. Add explicit test in S6-T1 case 12. | Test `test_mixed_vertical_winback_card_revenue_suppressed`. |
| R4 | **Fixture re-pin cascade.** Each flip ticket re-pins Beauty + supplements + potentially M0; if pins drift unintentionally, downstream Swarm contract risks. | Atomic re-pin discipline per S3 Risk #4 / S5-T2 pattern: flag flip + fixture pins + tests in ONE commit. New test asserts M0 byte-identity inside the same commit. | sha256 pin constants in test files; CI fails the moment any goes stale. |
| R5 | **Hard-stop on calibration envelope.** If Beauty winback posterior p50 lands outside the prior's [p10, p90] range, the prior is mis-calibrated OR the audience size dwarfs `pseudo_n=30` and pulls the posterior toward an unvetted store value. | STOP rather than re-pin. Document the divergence, ping orchestrator. Likely path forward: re-audit the Klaviyo memo OR raise `pseudo_n` for that prior (founder + DS architect call). | Acceptance criterion in S6-T1 / T3; test fails loudly. |
| R6 | **Hard-stop on vertical_applicability misfire.** If `replenishment_due` builder fires on a vertical its `vertical_applicability` excludes (e.g., a future apparel — refused at engine entry by B-7, but the unit-test path could mis-mock). | `decide.py:614` clean-skip filter; new test asserts builder is invoked ONLY for in-scope verticals. | Test `test_replenishment_due_skipped_on_excluded_vertical`. |
| R7 | **Hard-stop on audience floor.** If audience < floor on the pinned fixture, STOP and document — do NOT lower the floor to make the card appear. The floor is the load-bearing protection against Type I. | Acceptance criterion explicit; floor lives in priors metadata via G-3 `audience_floor_by_vertical`. | Per-fixture audience-size pin in S6-T1.5 / T3.5. |
| R8 | **KI-27 close-criteria ambiguity.** S6-T2 may parse all current supplement SKUs but new SKUs are forever-future. KI-27 "resolved" risks future regressions. | Default: keep KI-27 `accepted` post-S6-T2, flip to `resolved` ONLY if founder confirms "every SKU in the pinned supplements fixture parses" is sufficient. Document fallback behavior (parser returns None on unmatched SKU, no crash) explicitly. | Test `test_unknown_supplement_sku_returns_none_no_crash`. |

---

## 4. KIs touched / closed

| KI | Title | Status pre-S6 | Status post-S6 | Resolving ticket |
|---|---|---|---|---|
| KI-18 | `empty_bottle.vertical_applicable` excludes supplements (no unit-coherent parser) | tracked | ✅ Closed | S6-T2 |
| KI-27 | `empty_bottle` clean-skipped on supplements (G-2 contract) | accepted | ⏸ Conditional close (founder Q4) | S6-T2 if KI-27 close criteria met; else stays `accepted` |
| KI-21 | Supplements run emits zero Recommended Experiment cards (allowlist {discount_hygiene, bestseller_amplify} both fail gating) | open | ⏸ Still deferred (not Tier-B builder scope; allowlist redesign is S7) | none |
| KI-23 | Supplements: plays drop out between M3 shadow detection and Considered render | open | ⏸ Still deferred (partial: winback / replenishment audience surfaces grow, but the drop-out filter design is S7+) | none |
| KI-24 | Supplements `subscription_nudge` lands at `no_measured_signal` | open | ⏸ Still deferred (Phase 4.2 redesign, not S6) | none |
| KI-25 | Supplements `routine_builder` reason `audience_too_small` structurally wrong | tracked | ⏸ Still deferred | none |
| KI-28 | `mixed` vertical never exercised end-to-end | tracked | ⏸ Still deferred (S6 exercises `mixed` only via loader unit tests; no `mixed` end-to-end fixture) | none |
| (no existing KI tracks `_SUPPORTED` single-entry — it's documented in M2/Phase 5.6 architecture, not as a bug; S6 grows it from 1 → 3 entries organically) |

**Net KI delta:** KI-18 resolved; KI-27 conditionally resolved; 5 KIs remain deferred to S7+.

---

## 5. What Sprint 6 does NOT do

- ✗ **No Play Library refactor (S8).** `_SUPPORTED` stays as a dict in `measurement_builder.py`. The 2 new entries are interim; S8 folds all 3 into `plays/<play_id>/measurement.py`.
- ✗ **No additional Tier-B builders beyond the 2 specified.** `discount_dependency_hygiene`, `cohort_journey_first_to_second`, `aov_lift_via_threshold_bundle` are S7.
- ✗ **No additional `validated_external` promotions beyond the 3 from S7.5-T2.** No new memos under `config/priors_sources/`.
- ✗ **No renderer / HTML work.** Per Part III-3, JSON-only scope. The mechanism slot is the only typed copy-string change permitted, and only if the new plays need one — if so, follow the C1/C1.5 mechanism-line pattern, no other copy changes.
- ✗ **No Phase 9 outcome importer (S10).** `tools/import_outcome_observed.py` stays reserved.
- ✗ **No new `validation_status` enum values.** The 5-value closed set from S7.5-T1 is frozen.
- ✗ **No `event_version` bump.** All additions are `Optional` with backward-compat defaults.
- ✗ **No Klaviyo / Shopify network calls (D-5).**
- ✗ **No ML models (D-6).**
- ✗ **No new vertical** beyond {beauty, supplements, mixed} (D-8).
- ✗ **No `mixed` end-to-end fixture.** KI-28 stays tracked; mixed coverage continues to be loader-unit-test only.
- ✗ **No subsegment attribution (Loop B+, KI-29).** Stays parked for DS architect review.
- ✗ **No per-play chart spec (KI-30).** UX/design layer, not engine scope.
- ✗ **No legacy `calculate_28d_revenue` deletion (M10).** Out of scope.
- ✗ **No retroactive cleanup of S5-T2 `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` plumbing.** That reason stays as-is for `first_to_second_purchase`.

---

## 6. Open questions for the founder (with sensible defaults)

### Q1 — Vertical-specific dormancy windows for `winback_dormant_cohort`
Part I §B-1 specifies 21–45d for Beauty and 60–120d for Supplements. Confirm or override?
**Default:** ship as specified (21–45 / 60–120). Founder confirm before S6-T1 lands.

### Q2 — Minimum SKU sample size for `replenishment_due` cadence inference
Plan suggests N=30 customers with ≥2 repeat purchases per SKU as the per-SKU floor. Confirm or override?
**Default:** N=30. If founder prefers higher (N=50) the Beauty fixture's per-SKU cohort may not clear threshold for any SKU and the builder would silently no-op — re-pin would show zero card delta. If lower (N=15), Type I risk rises.

### Q3 — Prior consumption for `replenishment_due`
Two options: (a) consume existing `bestseller_amplify.bundle_value` (validated_external Beauty) — cleanest, no new YAML authoring; or (b) author a fresh `replenishment_due.base_rate` block in `config/priors.yaml` — more semantically correct but starts as `heuristic_unvalidated` (no external memo). Confirm which?
**Default:** (a) for S6-T3; (b) authored as a memo-pending future ticket. Founder confirm before S6-T3 lands.

### Q4 — KI-27 close criteria
Plan suggests: KI-27 flips to `resolved` if S6-T2 parser handles every SKU in the pinned supplements fixture. Confirm or set a stricter bar (e.g., parser handles ≥95% of SKUs across a future representative supplements catalog)?
**Default:** flip to `resolved` if every SKU in the pinned supplements fixture parses; document the fallback (None on unmatched SKU, no crash) explicitly. Future SKUs that fail to parse become a fresh KI.

### Q5 — Hard-stop calibration envelope
For Beauty winback posterior p50, what's the "looks reasonable" envelope? Plan suggests: posterior p50 must land inside the prior's `[range_p10, range_p90]` band on the pinned Beauty fixture. Confirm or replace with a different sanity criterion (e.g., posterior p50 within ±30% of prior p50)?
**Default:** posterior p50 ∈ [prior.range_p10, prior.range_p90]. Out-of-envelope triggers STOP, not re-pin.

---

## Final summary (~250 words for parent orchestrator)

**Ticket count:** 5 tickets (S6-T1, S6-T1.5, S6-T2, S6-T3, S6-T3.5), each with the standard 3-commit shape (impl + memory.md + summary doc) per the S5 / S7.5 template. Total ~15 commits — same volume as Sprint 7.5.

**Total estimated duration:** ~7 working days.

**First handoff bundle:** S6-T1 + S6-T1.5. Reasons: (a) S6-T1 is the larger of the two activation builders and the one that lights up the S7.5 validated_external Klaviyo prior — highest signal-per-day; (b) the bundle is self-contained (no parser dependency); (c) bundling the impl-then-flip cycle keeps the orchestrator review boundary clean, mirroring the S7.5-T3 / T3.5 cadence; (d) success here de-risks the same shape for S6-T3 / T3.5.

**Most important open questions for founder:** Q1 (vertical-specific dormancy windows — load-bearing for audience semantics), Q2 (replenishment cadence N=30 — load-bearing for Type I protection), Q3 (which prior `replenishment_due` consumes — controls whether S6-T3 reuses an S7.5-T2 promotion or authors a fresh heuristic_unvalidated entry), Q5 (calibration envelope hard-stop — defines the line between "re-pin" and "STOP and escalate").

**What makes S6 different from S7.5 from an implementation-risk standpoint:** S7.5 was contract-installation with zero behavior change on every fixture — every test asserted byte-identity. S6 is the *opposite*: every flip ticket intentionally changes Beauty + supplements fixture content. The atomic re-pin discipline (flag flip + sha256 pins + tests in one commit, per S3 Risk #4) is the only thing keeping CI honest. Founder should know up front that two pinned fixtures will move twice this sprint — and that the load-bearing "did this look right?" check (Q5 calibration envelope) happens *during* implementation, not after. If a posterior lands outside the prior's [p10, p90] band, the engineer STOPS rather than re-pinning, and the orchestrator gets a ping. That is the single most important hand-off rule for this sprint.
