# DS Architect — Engine Readiness for Frontend + MCP Agent Consumption

**Date:** 2026-05-30
**Branch:** post-6b-restructured-roadmap
**Post-sprint:** S13-T4-CLOSE shipped 2026-05-29
**Verdict:** **Engine is the strongest it has ever been for typed contract emission — but `engine_run.json` carries enough Pivot-2-violating prose fields + `Any`-typed slots that building MCP agents against today's contract will lock the violations in.**

---

## Headline recommendation

**Option D (Hybrid): S13.5 (KI-NEW-L collapse, already committed) + S13.6 (engine_run.json agent-contract cleanup) BEFORE S14 (real-merchant beta).**

Cost: ~1 sprint delay on S14. Risk reduction: avoids the cascading-rework event where agent prototypes built against today's JSON have to be rebuilt when prose / `Any` / dupes get cleaned up later.

---

## Part 1 — `engine_run.json` contract audit

DS walked all 1,285 lines of `src/engine_run.py`. The schema is **substantially production-ready as a typed contract** but carries debris from M0–S13 additive growth.

### Four classes of fluff the agents will trip on

1. **Engine-authored prose fields** (Pivot 2 violation): `PlayCard.recommendation_text`, `PlayCard.why_now`, `Observation.text`, `RejectedPlay.reason_text`, `RejectedPlay.evidence_snapshot`, `RejectedPlay.would_fire_if`, `Abstain.reason`.
2. **`Any`-typed slots** (assembly agent cannot validate): `store_profile: Optional[Any]`, `predictive_models: Dict[str, Any]`, `cohort_diagnostics: Dict[str, Any]`, `klaviyo_brief_inputs: Dict[str, Any]`.
3. **Debug-only counters surfacing in contract**: `considered_truncated_count`, all `notes: List[str]` fields in S6+ dataclasses.
4. **Duplicate fields on `OpportunityContext`**: `aov` vs `aov_used`, `addressable_value` vs `monthly_revenue_estimate`.

### Top-level `EngineRun` audit

| Field | Today | Recommendation |
|---|---|---|
| `run_id`, `store_id`, `anchor_date` | typed | KEEP |
| `schema_version: "1.0.0"` | lies about S8+S10-S13 additive growth | BUMP to 2.0.0; commit to additive-only `2.x.x` |
| `data_window`, `cold_start`, `data_quality_flags` | typed | KEEP |
| `abstain.reason` | free-text prose | STRIP from agent contract; `mode` enum is contract |
| `state_of_store[*].text` | engine-authored prose (Pivot 2 violation) | STRIP (numerics are contract) |
| `recommendations`, `recommended_experiments`, `considered`, `watching` | typed list slots | KEEP |
| `store_profile: Optional[Any]` | **UNTYPED** | RESHAPE: typed dataclass before agent build |
| `scale`, `briefing_meta` | typed | KEEP |
| `considered_truncated_count` | docstring says "NOT merchant copy — never rendered" | STRIP from agent surface; keep for CI pin |
| `predictive_models: Dict[str, Any]` | **UNTYPED values** | RESHAPE: `Dict[str, ModelCard]` with typed boundary |
| `cohort_diagnostics: Dict[str, Any]` | **UNTYPED values** | RESHAPE: typed at boundary |
| `month_2_delta: Optional[MonthDelta]` | typed at S13 | KEEP |

### PlayCard sub-field audit (the agent's main meal)

| Field | Today | Recommendation |
|---|---|---|
| `play_id`, `evidence_class`, `confidence_label` | typed | KEEP |
| `recommendation_text`, `why_now` | **engine-authored prose** | STRIP — narration agent generates |
| `audience` | typed | KEEP |
| `measurement.p_internal`, `measurement.ci_internal` | typed but "persisted but NEVER rendered" | KEEP but add explicit do-not-render flag |
| `revenue_range` | typed | KEEP |
| `opportunity_context` | typed but duplicative + carries "NOT projected lift" disclaimer in code comments only | DEDUP + add typed `_do_not_narrate_as_lift: bool` guardrail. **Highest single risk on list.** |
| `would_be_measured_by` | typed enum | KEEP |
| `klaviyo_brief_inputs: Dict[str, Any]` | **UNTYPED + dormant** | STRIP from v1 (re-add post-AWS-migration per D-5) |
| `predicted_segment` (S13) | typed | KEEP; `notes` STRIP/debug |
| `model_card_ref` (S13) | typed | KEEP; document `fit_warnings` grammar at contract boundary |
| `evidence_source` chip | typed enum | KEEP |
| `sensitivity` | typed | KEEP; `notes` STRIP/debug |
| `provenance` (EB audit object) | typed | KEEP; `notes` STRIP/debug; mark `audit_only=true` |

### RejectedPlay sub-field audit

| Field | Today | Recommendation |
|---|---|---|
| `play_id`, `reason_code` | typed enum | KEEP |
| `reason_text`, `evidence_snapshot`, `would_fire_if` | free-text prose | STRIP for agent consumption |
| `held_reason_detail: Dict[str, Any]` | structured numeric context | KEEP — narration agent reads this instead of `reason_text` |
| `audience_size`, `audience_definition`, `mechanism` | typed | KEEP |
| `would_be_measured_by` | typed enum | KEEP |

---

## Part 2 — Engine current state (one paragraph)

Post-S13-T4-CLOSE the engine is in the **strongest position it has ever been in for typed contract emission**: all 6 ML substrates land typed payloads (BG/NBD + G-G + survival + CF + RFM + retention), the four orthogonal gates are LIVE with locked precedence (Q-S13-4 LOCK prevents ML-fit from demoting), `predicted_segment` and `model_card_ref` populate PlayCards from the consumer-wiring module, and `month_2_delta` ships as a substrate-state-delta per Pivot 8. **What is production-ready for agents:** the four-lane slate structure, the evidence-tier chips, the typed reason-code enum, the four-state ML-fit status, the EB blend provenance audit object, and the Sensitivity scenario block — typed, locked, and stable. **What is fluff-laden / shaped wrong for agent consumption:** the engine-authored prose fields, the four `Any`-typed slots, the duplicate fields on `OpportunityContext`, the schema_version that lies about additive growth, and the debug-only counters/`notes` surfacing on the same JSON object as the agent contract. **What is missing for agent consumption:** (a) a typed `store_profile` dataclass (currently `Any`), (b) typed `ModelCard` and `RetentionCard` exposure at the EngineRun boundary (currently `Any` values), (c) a contract-level distinction between "fields the narration agent reads" and "fields that are operator-only audit," (d) a documented grammar contract for `model_card_ref.fit_warnings: List[str]` `"{LEVEL}:{substrate}"` format, and (e) explicit do-not-narrate flags on `p_internal`, `ci_internal`, `considered_truncated_count`, and every `notes` field.

---

## Part 3 — KI prioritization for frontend/agent unblock

DS read all 37 open KIs. Ranked by impact on "engine_run.json is ready for narration + assembly agents":

### P0 — MUST-FIX before agents can consume

1. **NEW-KI-AGENT-1 (not yet filed): `store_profile: Optional[Any]` → typed dataclass.** Assembly agent cannot validate a sub-object whose schema is `Any`. ~1 day.
2. **NEW-KI-AGENT-2 (not yet filed): `predictive_models: Dict[str, Any]` + `cohort_diagnostics: Dict[str, Any]` → typed at EngineRun boundary.** Re-export `ModelCard` and `RetentionCard` from `src/engine_run.py`. ~1 day.
3. **NEW-KI-AGENT-3 (not yet filed): Prose-field policy.** Decide per-field strip/rename/keep for `Observation.text`, `PlayCard.recommendation_text`, `PlayCard.why_now`, `RejectedPlay.reason_text`/`evidence_snapshot`/`would_fire_if`, `Abstain.reason`. **Founder call needed.** Pivot 2 says strip; back-compat says rename-as-legacy. ~1 day implementation once decided.
4. **KI-NEW-L (S13.5 collapse — already committed).** Does not directly affect contract shape but threatens single-demote-channel invariant whenever next Tier-B builder lands. Agent contract stability depends on this invariant holding. Ship before agent build. ~1 ticket.

### P1 — SHOULD-FIX for agent ergonomics

- **NEW-KI-AGENT-4: `notes: List[str]` debris.** Every S6+ dataclass carries back-compat `notes`. Mark debug-only or strip unless `INCLUDE_DEBUG_FIELDS=true`. ~0.5 day.
- **NEW-KI-AGENT-5: `OpportunityContext` field dedup.** Pick one pair. ~0.25 day.
- **NEW-KI-AGENT-6: Document `fit_warnings` grammar in `ModelCardRef` docstring at contract boundary.** ~0.1 day.
- **NEW-KI-AGENT-7: Schema_version bump (1.0.0 → 2.0.0) + CHANGELOG block at top of engine_run.py.** ~0.25 day.
- **KI-NEW-M / KI-NEW-N** (decide-layer provenance hygiene). Bundle if narration prototyping surfaces friction.
- **KI-30** (per-play evidence visualization spec). Documented UX gap; assembly agent IS the renderer.

### P2 — CAN-DEFER until S14 / post-beta

- KI-NEW-P (calibration — closure needs real merchants).
- KI-NEW-T (retention CI=0.0).
- KI-NEW-X (§G.3 three-precondition framing).
- KI-NEW-W (stale-parquet across REFUSED runs).
- KI-NEW-Y (intent-mapping YAML promotion).
- KI-NEW-G/H/I (replenishment_due activation cluster).
- KI-NEW-A through F (priors/floors/vocab/band recalibration).
- KI-1 through KI-5 (Phase 9 entry conditions).
- KI-NEW-Q (operator parquet query CLI — operator-only).
- KI-NEW-R (vendor-fork escape hatches — maintenance posture).

### P3 — ORTHOGONAL / NEVER-BLOCKS-AGENTS

- KI-NEW-S (wall-clock flake — test-only).
- KI-NEW-U (stale flag-default-off tests — test hygiene).
- KI-NEW-V (DS T1.5/T2.5 nits — internal DS process).
- KI-NEW-O (xfail reasoning stale).
- KI-NEW-Z (Option II wire-site process discipline).
- KI-6 through KI-28 (legacy substrate / supplements / vertical KIs).
- KI-29 (Loop B+ subsegment attribution — post-Phase-9).
- KI-31, KI-32 (synthetic fixture maintenance).

---

## Part 4 — Suggested next-sprint shape

**Recommendation: Option D — Hybrid sprint "S13.5 (KI-NEW-L collapse) + S13.6 (engine_run.json agent-contract cleanup)".**

### Justification

1. **Pivot 2 (Stop-Coding Line):** Pivot 2 says `engine_run.json` IS the product contract. Pivot 2 is violated *today* by `recommendation_text`, `why_now`, `Observation.text`, `RejectedPlay.reason_text`, `evidence_snapshot`, `would_fire_if`, `Abstain.reason` — engine-authored prose fields the schema docstring acknowledges as legacy. Building MCP agents against a contract that violates its own foundational pivot will **lock the violation into the agent surface**.

2. **D-S13-1 through D-S13-4 just landed.** These describe contract behavior. The contract-level typing and documentation of these decisions is incomplete at the EngineRun boundary. S13.6 finishes the typing work S13 started.

3. **KI dependency graph.** KI-NEW-L is invariant-preserving with no contract shape change. S13.6 (agent-contract cleanup) is the natural co-traveler — same contract surface, same single-sprint scale, shipping both before S14 means the first real merchant sees a stable contract.

4. **Founder priority.** Founder said "engine_run.json is the contract surface." S14 requires the contract to be stable. S13.6 is the minimum work to call the contract production-ready.

### Why NOT each alternative

- **Option C (skip to S14):** Onboarding against unstable contract creates cascading-rework risk. Cost of agent rebuild >> cost of cleanup now.
- **Option A (S13.5 alone):** KI-NEW-L is invariant-preservation only; doesn't make contract agent-ready.
- **Option B (cleanup alone, skip KI-NEW-L):** KI-NEW-L is founder-committed and DS-locked. Deferring widens 5-injection-block surface area.

### Proposed S13.5 / S13.6 split

- **S13.5 (committed):** KI-NEW-L collapse. ~1 refactor ticket. DS-locked invariant preservation. Engine behavior byte-identical.
- **S13.6 (proposed):** Agent-contract cleanup — 7 P0 items (NEW-KI-AGENT-1/2/3 + KI-NEW-L invariant carry-forward) + 4 cheapest P1 items (NEW-KI-AGENT-4/5/6/7). ~3-4 refactor tickets. PlayCard population byte-identical; serialization shape changes (re-pin pinned fixtures).
- **Then S14:** real-merchant beta onboarding against a stable contract.

Total delay vs Option C: ~1 sprint. Risk reduction: substantial.

---

## Part 5 — Open questions for founder

1. **Prose-field policy (P0 blocker).** For each of `Observation.text`, `PlayCard.recommendation_text`, `PlayCard.why_now`, `RejectedPlay.reason_text`/`evidence_snapshot`/`would_fire_if`, `Abstain.reason`: (a) strip, (b) rename `_legacy_*` + mark ignored-by-agents, or (c) keep as engine-authored. **DS recommends (a) for new fields, (b) for fields with existing fixture history.**

2. **Should `considered` be merged into `recommendations` with a `lane: enum` discriminator?** Today the four lanes are four list slots. Alternative: `slate: List[PlayCard]` where each card carries `lane: Literal[...]`. Merged shape is more ergonomic for agents (one iteration) but breaks role-uniqueness invariant pin. **DS recommends keep 4 lists** — structural separation IS the invariant.

3. **Strict v1 contract freeze vs additive evolution.** Once agents ship, schema bumps require coordinated agent updates. Hard schema freeze at S13.6 end (next additions via major-version bump) vs S8-style additive growth. **DS recommends hard freeze for v1 after S13.6.**

4. **Mechanism string ownership.** S6 C1 wired mechanism lines `"What we'd send"` on Recommended Now + Experiment cards. Engine-authored copy. Narration agent will want to own. Strip mechanism from engine emission, OR keep as typed `mechanism: str` and let narration agent override?

5. **Beta-launch timing.** If S13.5 + S13.6 take 2 sprints, S14 shifts ~2 weeks right. OK with delay, or push S14 against today's contract and absorb agent-rebuild cost later? **DS strongly recommends the delay.**

6. **`klaviyo_brief_inputs: Dict[str, Any]` — keep dormant or strip from v1?** Today empty; will only populate post-AWS-migration (D-5 forbids API calls). Type now (premature) or strip from v1 (re-add post-AWS).

---

## Part 6 — Risk surface

What can go wrong if founder builds agents against today's contract:

1. **Pivot-2 violation locked into agent surface.** Narration agent reads `recommendation_text` as authoritative → narrates engine prose → engine prose drifts → agent narrates stale text. Mitigation: strip/rename before agent build.

2. **`Any`-typed slots cause schema-drift bugs.** Assembly agent uses runtime introspection on `predictive_models["bgnbd"]` because schema doesn't declare shape. ModelCard refactor (already happened at S13-T0) is the kind of change that silently breaks runtime-introspecting consumers. Mitigation: type at contract boundary.

3. **Duplicate fields on `OpportunityContext`.** Narration agent picks `aov`; assembly agent picks `aov_used`. Same number today, diverges on future ticket update. Mitigation: dedup.

4. **Debug-only fields surfacing as contract.** `considered_truncated_count` carries founder-internal-only semantics but emitted in `to_dict()`. Mitigation: `to_dict(include_debug=False)` mode.

5. **`fit_warnings` grammar documented in code comments, not contract.** Narration agent parses `"PROVISIONAL_SELECTED:cf"` to know substrate. If grammar changes (S14 adds fourth LEVEL), agents break silently. Mitigation: typed dataclass `FitWarning(level: Enum, substrate: str)` instead of `List[str]`.

6. **`schema_version="1.0.0"` lies about additive growth.** Agents may version-pin on `1.0.0` thinking stable; every sprint since S8 added fields under same version. Mitigation: bump to `2.0.0` with S13.6 cleanup; commit to additive-only `2.x.x`.

7. **`opportunity_context` carries `OPPORTUNITY_CONTEXT_DISCLAIMER` semantic constraint** (NOT projected lift, NOT p50, NOT forecast) — constraint lives in code comments at `src/engine_run.py:759-768`, NOT in contract surface. Narration agent will violate this on first run unless given typed `_do_not_narrate_as_lift: bool` flag. **HIGHEST SINGLE RISK ON LIST.** Exactly the failure mode Pivot 2 was locked to prevent.

8. **Empty/None placeholder fields confuse agents.** Pre-S13 fixtures have `predicted_segment=None`. Post-S13 modal-segment stability floor means `predicted_segment.segment_name=None` is ALSO valid (per D-S13-2). Two semantically different `None` shapes. Mitigation: document explicitly; `populated: bool` flag or discriminated union.

---

## TL;DR

- **Engine is the richest typed contract it has ever shipped — but agents will trip on Pivot-2-violating prose fields, `Any`-typed slots, dupes, and debug debris.**
- **Top 3 P0 fixes:** prose-field policy + type the `Any` slots + ship KI-NEW-L collapse.
- **Recommend Option D:** S13.5 (KI-NEW-L collapse) + S13.6 (agent-contract cleanup) before S14.
- **6 founder decisions needed** (mostly schema-shape calls; DS has recommendations on all).
- **Highest single risk:** `opportunity_context` "NOT projected lift" disclaimer lives in code comments, not contract — narration agent will violate this on first run unless typed guardrail added.
- **Bottom line:** 1-sprint delay on S14 to ship agent-ready contract. Cost: 2 weeks. Risk reduction: avoid cascading agent rebuild.

---

**Relevant file paths (all absolute):**
- `/Users/atul.jena/Projects/Personal/beaconai/PRODUCT.md`
- `/Users/atul.jena/Projects/Personal/beaconai/STATE.md`
- `/Users/atul.jena/Projects/Personal/beaconai/PIVOTS.md` (especially Pivot 2 Stop-Coding Line, L24-30)
- `/Users/atul.jena/Projects/Personal/beaconai/ROADMAP.md`
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md`
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` (contract surface — full 1285 lines audited)
- `/Users/atul.jena/Projects/Personal/beaconai/docs/DECISIONS.md` (D-S13-1 through D-S13-4 locked)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/phase6b-stop-coding-line-reconciled.md` (Pivot 2 origin)
