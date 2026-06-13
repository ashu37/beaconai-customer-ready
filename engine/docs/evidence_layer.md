# The Evidence Layer — BeaconAI

**Status:** First-class spec. DS-defined 2026-06-02 (`ecommerce-ds-architect`), founder-ratified.
**Authority chain:** builds on the evidence-viz verdict (L-VIZ-1..6) and the handoff DS locks (`docs/handoff_architecture.md` §7). Consolidates both into the L-EV-1..12 locks below.
**Schema impact:** none — fully assemblable from frozen v2.0.0 (`src/engine_run.py`) via the manifest-pointer join. Convention-only.
**Why this doc exists:** "the evidence layer" was used informally (evidence chips, evidence tiers) but never defined as a planned artifact. This is that definition. Visualization is a *member* of the layer, not a bolt-on.

---

## 1. Definition

**The Evidence Layer is the typed, gated set of atoms on a PlayCard (plus the run-level diagnostic dicts) that justify the card's slate placement and let a merchant trust it — assembled, never authored, under one suppression discipline shared across number, prose, and visualization.**

It **is**: a consumer-side *view* over already-frozen v2.0.0 fields; gated identically to the card itself; the single rule-set under which a suppressed revenue number, a withheld retention curve, and an un-narratable segment claim all suppress for the same reason at the same seam.

It is **not**: a dashboard (PRODUCT.md §9 — it justifies decisions, not "metrics that moved"); fabricated (Pivot 2; §7 lock 8); the prose (narration authors *from* the layer); a new contract surface.

**Tier vs gate.** The evidence **tier** (`EvidenceSourceChip` A/B/C/D) is the **composition selector** — it decides which members are present and what each may claim. The four **gates** (audience-floor / cohort p-value / prior-validation / ML-fit) decide whether the card exists and in which lane. The Evidence Layer is what remains *visible* on a gate-surviving card, filtered by what its tier honestly supports. **Zero Tier-A plays exist today** (`src/engine_run.py:743`) — so no member may narrate a causal/lift claim in beta.

---

## 2. Membership — the 9 members (closed set)

Each member binds to a real typed field. `M*-VIZ` = the visualization member (renders an already-typed series; never a PNG, never a chart-spec).

| # | Member | Typed source field | Tiers | Gate / precondition | Merchant form | Viz | Dollar axis |
|---|---|---|---|---|---|---|---|
| **M1** | Evidence chip (tier) | `PlayCard.evidence_source` | all | `ENGINE_V2_TIER_CHIP` ON; **never `evidence_class`** | chip | — | — |
| **M2** | Measurement (observed effect) | `PlayCard.measurement` (`observed_effect`, `n`, windows; `p_internal`/`ci_internal` NEVER rendered) | B | `measurement is not None`; cohort-p gate passed | number + prose | **M2-VIZ** multi-window effect series | no |
| **M3** | Revenue posterior | `PlayCard.revenue_range` (`p10/p50/p90`, `source`, `suppressed`, `suppression_reason`) | B (+future A) | `suppressed==False` AND `source==BLEND` | range | **M3-VIZ** range bar | **yes** (only here + M8) |
| **M4** | Audience | `PlayCard.audience` (`size`, `definition`, `fraction_of_base`) | all | audience-floor gate passed | number + prose | **M4-VIZ** proportion-of-base | no |
| **M5** | Predicted segment | `PlayCard.predicted_segment` (`segment_name` + null-reason, `audience_modal_share`, `n_audience`) | C (often) | **D-S13-2 modal floor** (`n≥50` AND `share≥0.30`); use card field, NOT CSV column | chip | **M5-VIZ** modal-share composition | no |
| **M6** | Model-fit / provenance | `PlayCard.model_card_ref` (`fit_warnings`), `PlayCard.provenance` (blend inputs) | audit | ML ran / `source==BLEND` | **audit-only** | M6-VIZ blend split — **operator-only** | operator-only |
| **M7** | Cohort/retention context | `EngineRun.cohort_diagnostics["retention"]` (`cohorts[].period_retention/cumulative_retention/ci_*`, `fit_status`) | run-level | **fit_status ∈ {VALIDATED, PROVISIONAL}** | prose context | **M7-VIZ** retention curve + CI band | no |
| **M8** | Sensitivity | `PlayCard.sensitivity` (4 `Optional[RevenueRange]` scenarios) | B | `ENGINE_V2_SENSITIVITY` ON; `source==BLEND`; not suppressed | range deltas | **M8-VIZ** tornado/range overlay | yes (BLEND) |
| **M9** | Opportunity (addressable, non-lift) | `PlayCard.opportunity_context` (`NonLiftAtom`) | suppressed-range cards | `revenue_range.suppressed==True` AND defensible AOV | number ("addressable, not projected") | addressable-pool glyph (distinct from M3-VIZ) | no |

**Absence is typed, never silent:** every conditionally-absent member encodes its absence via a RULE A null-reason or a `suppressed` flag — never by silent omission.

---

## 3. Per-tier composition

| Member | Tier A `STORE_MEASURED` | Tier B `STORE_OBSERVED` | Tier C `INDUSTRY_PRIOR` | Tier D `OBSERVATIONAL` | Refused / Abstain |
|---|---|---|---|---|---|
| M1 chip | A *(none today)* | B | C | D | n/a |
| M2 (+VIZ) | causal effect series | **observed effect series** | absent (`measurement=None`) | absent | absent |
| M3 (+VIZ) | measured lift range | **BLEND range bar** | suppressed → reason | suppressed → reason | absent |
| M4 (+VIZ) | present | present | present | **present (only evidence)** | present if any |
| M5 (+VIZ) | floor-gated | floor-gated | **floor-gated (audience fits)** | floor-gated | absent |
| M6 | audit | **audit (provenance)** | audit | audit | absent |
| M7 (+VIZ) | context | **context (fit-gated)** | context | context | suppressed → absence reason |
| M8 (+VIZ) | present | **present (BLEND only)** | absent | absent | absent |
| M9 | n/a | only if range suppressed | **present** | absent | absent |

- **Tier A** — empty in beta; slot wired, nothing renders until Phase 9 unlocks the first `STORE_MEASURED` card.
- **Tier B** — trust-dense ("month-1 wow"): M2 + M3 + M7 + M8 + provenance audit. Highest laundering risk: M2's effect series must **never** be narrated as the lift M3's range will deliver (§7 lock 2). That adjacency is the footgun the layer disciplines.
- **Tier C** — audience-fit, **no effect chart** (`measurement is None` → M2-VIZ structurally absent; rendering one is a REJECT-class breach). Story = M4 + M5 (floor-gated) + M7 context; M9 is the honest dollar-adjacent surface (addressable, explicitly non-lift).
- **Tier D** — audience only (M4).
- **Refused/abstain** — rendered typed reason, never an empty screen.

---

## 4. The unified honesty discipline (one rule across number / prose / viz)

Three states, applied identically to a member's number, its prose, and its visualization:

- **SHOWN** — field populated AND precondition met AND tier permits the claim.
- **SHOWN-WITH-CAVEAT** — populated but sub-VALIDATED: `RetentionCard.fit_status==PROVISIONAL` (M7 curve drawn, no absolute month-N retention quoted as fact); `window_corroboration==NEUTRAL` (M2 series PROVISIONAL-styled); upstream `ModelFitStatus==PROVISIONAL` (M5 ranking used, magnitudes not quoted). Caveat applies to viz styling and prose identically — they cannot disagree.
- **SUPPRESSED** — typed absence/suppression marker set → **render the typed reason, never blank**: M3 `suppression_reason` (1-of-9); M5 below floor → `segment_name=None` + null-reason, audit counters shown, no labelled chart; M7 `fit_status∈{INSUFFICIENT_DATA,REFUSED}` → no curve, render absence reason; per-scenario M8 suppression drops that scenario from the viz.

---

## 5. Contract sufficiency + assembly seam

**Assemblable from v2.0.0 today — no schema change.** Every member binds to an existing field; M7's retention series is already JSON-shaped in `cohort_diagnostics` (no parquet). Defining the layer is a documentation + assembler-convention act; the freeze holds.

**Deferred net-new field:** `PlayCard.evidence_layer_ref: Optional[str]` (a per-card presence manifest) is **NOT added** — the 9 typed preconditions already encode presence deterministically. If ever needed, it is additive `2.0.0 → 2.1.0` with paired RULE A handling, on DS re-review.

**Assembly seam:**
- **Engine** — emits typed atoms only (immutable, no prose, no chart). Assembles nothing.
- **Narration MCP** — assembles the *claim/prose projection*: reads the run via manifest pointer, applies §4 discipline, emits per-`(run_id, play_id)` narration. Authors language for M1–M5/M7/M9; treats M6 as audit-only; invents no numbers.
- **Frontend** — assembles the *visual projection*: renders pixels from the typed series (M2/M3/M4/M5/M7/M8), honoring §4. The Stop-Coding Line applied to charts: typed series = engine; pixels = UI.
- Neither MCP nor UI writes back to the engine snapshot (PRODUCT.md §8).

---

## 6. Roadmap placement

Evidence Layer is a **named joint Narration-MCP + Frontend workstream**, threaded through the handoff phases (not a new phase):

- **Discipline (§4 + L-EV-4..7) → Phase 1 narration brief** (alongside §7 locks 1/2/3/6/7/8). Claim-suppression rules are identical whether the suppressed thing is a sentence or a chart; prose templates shipped without them encode the laundering paths.
- **Visual projection → Phase 3 (frontend slate)**. Depends on Phase 2 (integration) + Phase 1 (narration).
- **Minimum-honest beta set: {M1, M3, M4, M5, M7}** (chip, revenue bar, audience proportion, segment composition, retention curve) — carries month-1-wow + month-2-return.
- **Deferrable to Phase 3.x:** M2-VIZ (effect series) + M8-VIZ (sensitivity) — caveat-heavy, high laundering risk; ship once §4 is enforced in templates.
- **Operator-only, never beta merchant surface:** M6-VIZ.
- **Tier-A composition** activates only when Phase 9 outcome history produces the first `STORE_MEASURED` card — not before.

---

## 7. Locks established (L-EV-1..12)

| Lock | Substance |
|---|---|
| **L-EV-1** | Evidence Layer = consumer-side assembled view over frozen v2.0.0 atoms; tier selects membership, gates select existence/lane, unified suppression. No engine behavior change. |
| **L-EV-2** | Closed 9-member set (M1–M9), each bound to named typed field(s); absence encoded by RULE A null-reason / suppression flag, never silent. |
| **L-EV-3** | Viz is a first-class member rendering an already-typed series/scalar set; no `chart_spec`, no PNG, no invented series (carries L-VIZ-1/4). |
| **L-EV-4** | Tier gates membership; a member absent-per-tier must not be assembled/rendered (Tier-C effect chart = REJECT-class). |
| **L-EV-5** | One SHOWN / SHOWN-WITH-CAVEAT / SUPPRESSED state per member across number+prose+viz; they cannot diverge; suppression renders the typed reason. |
| **L-EV-6** | Dollar axis only in M3-VIZ and M8-VIZ, only on non-suppressed `source==BLEND` RevenueRange (carries L-VIZ-5 + §7 lock 8). |
| **L-EV-7** | Each viz inherits its gate from its parent member's typed status (fit_status / modal floor / window_corroboration); M6-VIZ never reaches the merchant surface (carries L-VIZ-2/3/6, §7 lock 3). |
| **L-EV-8** | Assembly seam: Narration MCP = claim projection, Frontend = visual projection, engine emits atoms only; no engine-side chart or layer manifest. |
| **L-EV-9** | Fully assemblable from v2.0.0 (convention-only, no bump); sole net-new candidate `PlayCard.evidence_layer_ref` DEFERRED (additive 2.1.0 if ever needed, on DS re-review). |
| **L-EV-10** | Roadmap: joint Narration+Frontend workstream; discipline → Phase 1 brief; visuals → Phase 3 (min-honest {M1,M3,M4,M5,M7}); M2/M8-VIZ deferrable to Phase 3.x; Tier-A gated on Phase 9. |
| **L-EV-11** | Narration consumes `evidence_source` (chip), NEVER `evidence_class`; zero Tier-A plays today, so no member may narrate a causal/lift claim (carries §7 lock 1). |
| **L-EV-12** | The abstain/refused state is a rendered member-state (typed reason), never an empty screen; honest "not yet" is part of the layer. |

### L-EV-13..20 — added 2026-06-02 (founder "viz is the value" + "do the visuals flex per play" re-engagements)

> These extend the set after two DS re-engagements. L-EV-13..16 establish the descriptive/inferential frame, the refused-data posture, and the dashboard boundary (the founder's "what decision does this pixel justify?" line). L-EV-17..20 establish per-play visual flexibility. Founder authorized the `Audience.descriptive_distribution` 2.1.0 bump (L-EV-19) on 2026-06-02.

| Lock | Substance |
|---|---|
| **L-EV-13** | **Descriptive/inferential split governs viz gating.** DESCRIPTIVE viz renders observed past behavior (counts, rates, realized cohort/segment behavior); INFERENTIAL viz renders a forward claim (prediction, posterior, projected lift). The four gates discipline inferential viz; descriptive viz is gated only by a **data-integrity** check, NOT a forward-precision check. |
| **L-EV-14** | **REFUSED has two meanings; only one taints the descriptive series.** REFUSED-for-data-integrity (retention `cumulative_retention_monotonicity_violation==true`; degenerate RFM) → SUPPRESS the descriptive series (data is corrupt). REFUSED/INSUFFICIENT-for-horizon-or-precision (`retention_below_provisional_thresholds`, CI-width, cohort_count) → SHOW the observed series over its observed window, SUPPRESS only the inferential overlay. Consumers branch on `fit_warnings` / the monotonicity flag, not `fit_status` alone. |
| **L-EV-15** | **Refused-data posture (pinned).** A descriptive viz renders iff its observed series passes the data-integrity check (not the forward-precision check); forward-precision shortfalls gate the inferential overlay only. RFM has no descriptive twin (the segmentation IS the inferential product) → suppresses as a unit on REFUSED. Observed-retention on a too-few-cohorts REFUSED run renders over the observed periods only, NOT extrapolated to `months_horizon`. |
| **L-EV-16** | **Dashboard boundary = decision-anchoring.** For every chart: "what decision does this pixel justify?" If it justifies a card / slate / hold → evidence visualization (ship). If it just shows a number for its own sake → dashboard tile (refuse, PRODUCT.md §9). `state_of_store` atoms render as card-anchored evidence-for-classification, never a free-floating metrics grid. The Intelligence page is a legitimate run-level evidence surface; it must be wired to the contract (RFM ← `predictive_models.rfm` fit-gated; retention ← `cohort_diagnostics`, the same source as RetentionContext, resolving the double-retention redundancy) — fabricated mock charts (`mockRfmSegments`/`mockCohortRetention`) are a fabrication surface and are deleted. |
| **L-EV-17** | **Play-specific viz = frontend per-mechanism selection map.** Delivered by a frontend static map `{MechanismType → preferred descriptive viz}` keyed on `mechanism_intent.type`, choosing among existing typed members/series. Convention-only — no engine field, no schema bump for the *selection* logic (the chart-selection analogue of the L-EV-8 card→series join). The engine never emits a per-play chart selection. |
| **L-EV-18** | **Generic M1-M9 suffices for beta; the bespoke-chart blocker is a discarded-series problem.** The four distributional plays (WINBACK / THRESHOLD_BUNDLE / REPLENISHMENT / DISCOUNT_HYGIENE) are under-served by generic-only because their story is a *distribution*, not a scalar. They are blocked NOT on Tier-B `{}` parameters but because the audience builders compute the distribution (dormancy `days_since`, AOV-gap, reorder cadence, discount-frac) and `Audience` carries only the scalar count. A play earns a bespoke chart iff (i) its story is distributional not scalar, (ii) the series is already builder-computed, (iii) it passes the descriptive gate. |
| **L-EV-19** | **`Audience.descriptive_distribution` — one generic additive primitive (FOUNDER-AUTHORIZED 2026-06-02; 2.0.0 → 2.1.0).** A single `Optional[DescriptiveDistribution]` atom (`kind` enum, `bins`, `counts`, optional `marker`, paired RULE-A `suppressed`/null-reason) reused across the 4 distributional plays. It is a richer rendering of **M4** (audience), NOT a 10th member — the closed 9-member set (L-EV-2) is preserved. Engine emits the binned series, NEVER a chart-spec (carries L-EV-3 Stop-Coding Line). Requires paired null-reason per RULE A / schema-freeze policy. |
| **L-EV-20** | **Bespoke distribution charts are descriptive-only and Tier-A-empty-safe.** Count axis, NO dollar axis (L-EV-6), NO projected-rate/lift overlay — an inferential overlay on a descriptive distribution is a REJECT-class breach (carries L-EV-5 + the §3 Tier-B laundering note). Suppression binds the marker too: when a scalar parameter is `None`/`TODO(S14)` (`threshold_aov`, `current_discount_share`, `replenishment_window_days`, `sku_class`), the chart renders the typed absence, never a guessed line. No gate may be relaxed to surface a distribution early. |

**DS-domain (settled here):** membership + field bindings; viz-as-member typing; per-tier table; unified suppression; assembly seam; the descriptive/inferential frame + refused-data posture (L-EV-13..15); the dashboard boundary (L-EV-16); the per-mechanism selection-map architecture + discarded-series diagnosis (L-EV-17/18); the `DescriptiveDistribution` primitive shape + descriptive-only gating (L-EV-19/20 spec).

**Founder-domain (decided 2026-06-02):** M2-VIZ/M8-VIZ shipped (in); Intelligence page wired-to-contract (in); `Audience.descriptive_distribution` 2.1.0 bump **AUTHORIZED**. **Open:** D-letter assignment at sprint close (recommended anchor: a D-S14-class entry recording L-EV-1..20 + the L-VIZ→L-EV consolidation).

---

## 8. The descriptive/inferential frame (governing rule for viz honesty)

The load-bearing distinction behind L-EV-13..15, stated once for reference:

- **DESCRIPTIVE** = *what the merchant's customers actually did* — observed counts, rates, realized cohort/segment behavior, metric movement. A statement about the past. Integrity requirements: (a) underlying data not corrupt, (b) not extrapolated beyond the observation window. Light gate.
- **INFERENTIAL** = *a forward claim* — a validated retention prediction, a revenue posterior, a projected lift, a causal magnitude. The four gates (audience-floor / cohort-p / prior-validation / ML-fit) exist to discipline these.

The frame resolves the "is `beauty_brand` visually thin?" question: it is NOT thin — the prior min-honest set leaked the *inferential* gate onto *descriptive* series. A REFUSED-for-too-few-cohorts retention model still has clean observed cohort curves worth charting; only the 12-month forward prediction is withheld. Charting the observed (over its window) while suppressing the projection is honest and rich. The dashboard boundary (L-EV-16) is the orthogonal guard: descriptive ≠ permission to show a number for its own sake — it must still anchor a decision.
