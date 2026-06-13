# BeaconAI Decision-Core Overhaul — Phased Implementation Plan

**Author:** Implementation Manager
**Date:** 2026-05-01
**Status:** Contract for code-refactor-engineer agent. Treats `memory.md` reconciled section as baseline, with PM doc and Skeptic critique layered in.

**DS Architect QA: RESOLVED (2026-05-01)**
**Engineering may begin with Milestone 0 / M0 only. No further milestone work should start until M0 lands and goldens are frozen.**
**No further architecture review is required unless implementation reveals a blocker.**

---

## 0. Implementation verdict

The PM doc and reviewer set are largely correct. The big risk is not the design — it is the migration. The current `select_actions` path is an entangled monolith that produces fields the HTML briefing reads by name. We must keep that path running on every commit while the new decision core is built behind a feature flag in a parallel module, then flip the renderer once shadow output matches. Three constraints dominate the sequencing:

1. **No big-bang.** Every milestone must ship and leave the existing CSV → HTML workflow runnable. The new path lives behind `ENGINE_V2=false` until Milestone 8.
2. **Schema before behavior.** The `EngineRun` contract (PM Q2) is the highest-leverage artifact. It is built in M1/M2 before we change any decision logic.
3. **Wow surface (rejection list, state-of-store, abstain) is product-load-bearing.** It is sequenced into M7/M8 and explicitly *not* deferred to a "polish" phase.

PM Phase 1A (the 10-day slice) maps to **Milestones 0, 4 (subset), and a thin slice of M7/M8**. The full Phase 1A goal — "no fake stats, evidence_class, reclassify targeting plays, three-section layout, rejected list, abstain modes, inventory gate" — does **not** require the full plan to ship. See "Phase 1A → Milestone mapping" below.

Where this plan disagrees with memory.md or the PM doc, I call it out inline ("Deviation").

---

## Phase 1A (PM doc) → Milestone mapping

PM Phase 1A is the 10-day slice. It is not a single milestone here. It is:

- **PM Day 1–2 (kill fabricated stats, add evidence_class field):** Milestone 4a tickets T4a.1, T4a.2, T4a.3.
- **PM Day 3–4 (reclassify targeting plays):** Milestone 4b tickets T4b.1, T4b.2.
- **PM Day 5 (collapse tier matrix in storytelling):** Milestone 8 ticket T8.1 (renderer-only, behind `ENGINE_V2_OUTPUT=false` initially; flipped on for the 1A slice).
- **PM Day 6–7 (rejected-play list, 5 reason codes):** Milestone 7 tickets T7.5, T7.6 (subset: only the 5 codes), Milestone 8 ticket T8.2.
- **PM Day 8 (inventory gate):** Milestone 5 ticket T5.1.
- **PM Day 9 (ABSTAIN_SOFT/HARD):** Milestone 7 ticket T7.7 + Milestone 8 ticket T8.3.
- **PM Day 10 (state-of-store + Watching):** Milestone 1 ticket T1.4 (state-of-store as typed Observations) + Milestone 8 ticket T8.4.

**Deviation from PM doc:** PM Phase 1A treats Milestones 4/5/7/8 fragments as one 10-day push. Operationally that is fine, but it requires Milestone 0 (golden fixtures), Milestone 1 (data contracts), and Milestone 2 (play registry stub) as prerequisites. The honest 10-day slice is closer to 14–18 working days when the prerequisites are counted. I keep the PM 1A scope but flag the prerequisite cost.

---

## Dependency graph between milestones

```
M0 (freeze) ──┬─► M1 (data contracts) ──┬─► M2 (play registry) ─► M3 (candidate detection)
              │                         │                                      │
              │                         └─► M4a (additive nan-ing) ─► M4b (combiner reroute) ◄──┘
              │                                                                │
              └─► M5 (guardrails) ◄────────────────────────────────────────────┤
                                                                               │
                                          M6 (economic sizing) ◄───────────────┤
                                                                               │
                                          M7 (decision selector) ◄─────────────┴─ depends on M3,M4b,M5,M6
                                                                               │
                                          M8 (Play Thesis output) ◄────────────┘
                                                                               │
                                          M9 (ML readiness) ◄─ runs in parallel with M5–M8
                                                                               │
                                          M10 (cleanup & deletion) ◄───── last; only after M8 default-on
```

**Can run in parallel:**
- M1 and M0 (M0 is mostly fixture capture; M1 is schema definition).
- M2 and M4a (registry is a config file; nan-ing fake stats is line-level patches).
- M5 and M6 (guardrails operate on candidates; sizing operates on candidates; both before M7).
- M9 and M5–M8 (logging is additive).

**Blockers:**
- M3 cannot start until M2 ships the registry shape.
- M4b cannot start until M4a has shipped and baked briefly (a few days) so the additive NaN-ing is shaken out before reclassification + combiner-reroute land.
- M7 cannot start until M3, M4b, M5, M6 are at least minimally available (even stubbed).
- M8 cannot ship default-on until M7 produces an `EngineRun` object the renderer can read.
- M10 cannot start until M8 has been default-on for one full release cycle.

---

## Feature-flag inventory

| Flag | Default | Added in | Flipped on by default in | Removed in |
|---|---|---|---|---|
| `ENGINE_V2` | `false` | M2 | M8 (after shadow parity) | M10 |
| `ENGINE_V2_OUTPUT` | `false` | M8 | M8 (paired with `ENGINE_V2`) | M10 |
| `ENGINE_V2_SHADOW` | `false` | M3 | M3 (on in CI/dev only) | M10 |
| `STATS_NAN_FOR_HARDCODED` | `false` | M4a | M4a | never (becomes default behavior; flag deleted in M10) |
| `EVIDENCE_CLASS_ENFORCED` | `false` | M4a | M4b | M10 |
| `INVENTORY_GATE_ENABLED` | `false` | M5 | M5 | never (becomes always-on; flag deleted in M10) |
| `ANOMALY_GATE_ENABLED` | `false` | M5 | M5 (after rule tuning in dev) | M10 |
| `CANNIBALIZATION_GATE_ENABLED` | `false` | M5 | M5 | M10 |
| `MATERIALITY_FLOOR_SCALE_AWARE` | `false` | M5 | M5 | never (becomes default; flag deleted in M10) |
| `REJECTED_PLAYS_RENDERED` | `false` | M8 | M8 | never (always-on; flag deleted in M10) |
| `ABSTAIN_MODE_ENABLED` | `false` | M7 | M7 | never (always-on; flag deleted in M10) |
| `OUTCOME_LOG_ENABLED` | `true` | M9 | M9 | never |

**Flags being removed (existing flags in code today):**
- `ENABLE_COHORT_POOLING` — set to `false` in M0; deleted with the dead path in M10. (Default flip lives in M4a ticket T4a.6.)
- `ENABLE_REPEAT_RATE_BIAS_CORRECTION` — kept on default in M0–M5, flipped off in M5 (audit reviewer #6), deleted in M10. (Default flip also referenced in M4a ticket T4a.6 to keep the additive-nan milestone self-contained.)
- `ENABLE_ENHANCED_STATISTICS` — kept on; superseded by `combine_multiwindow_statistics` everywhere in M4b. Flag deleted in M10.
- `_FORCE_SINGLE_WINDOW` (set in `select_actions` line 3785) — removed in M0 as a code-cleanup ticket; replaced with explicit cfg.

---

## Risk register (ranked)

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Setting fake stats to NaN cascades through `benjamini_hochberg`, `confidence_from_ci`, `compute_score` and breaks every test fixture and every PRIMARY-tier assignment | High | High | M0 captures a golden HTML/JSON snapshot for at least 3 merchant CSVs **before** M4a runs. M4a lands behind `STATS_NAN_FOR_HARDCODED=false` and ships flag-on after fixture diffs are reviewed. Acceptance criterion: existing engine still runs with flag off and produces byte-identical receipts. The M4a/M4b split (see Change 6) further reduces single-PR review burden by separating additive NaN-ing from reclassification + combiner reroute. |
| 2 | Renderer collapse (4-tier matrix → three sections) silently changes downstream consumers (action log, `actions_log.json`, copy templates in `copykit.py`) | High | High | M8 builds the new renderer next to the old one and wires `ENGINE_V2_OUTPUT` to choose. Old briefing path is NOT modified. M10 deletes only after one stable release cycle on V2. |
| 3 | `combine_multiwindow_statistics` rerouting changes which plays clear gates in single-window mode for stores with thin data, surfacing more abstains than expected and triggering merchant churn fear | Medium | High | M4b ships combiner rerouting in shadow first (`ENGINE_V2_SHADOW=true`) and logs differences across the three test merchants. Sign off on per-merchant delta before flipping default. |
| 4 | New `EngineRun` schema diverges from what `briefing.py`, `storytelling.py`, `copykit.py` currently consume by field name, causing renderer crashes | Medium | High | M1 introduces the schema as additive — the new fields exist alongside legacy fields. M8 ships an adapter `legacy_actions_from_engine_run()` that reproduces the old per-action dict so existing renderer keeps working until M10. |
| 5 | Anomalous-window detection (BFCM, refund storm, test-order) produces false positives on the test fixtures and abstains everywhere | Medium | Medium | M5 ships rules behind `ANOMALY_GATE_ENABLED=false` in production-equivalent mode; tune thresholds against captured M0 fixtures + 1 BFCM-window fixture (synthesized from existing data). Flip on only when no false-positive abstain on the 3 baseline merchants. |
| 6 | Inventory gate breaks merchants who lack inventory CSV (current `compute_inventory_metrics` returns empty) | Medium | Medium | M5 ticket T5.1 explicitly defines "no inventory data → gate is no-op, log warning, do not block plays." Add a unit test for that branch. |
| 7 | Cannibalization demotion cap (sum of p50 ≤ 25% of monthly revenue) reduces the recommendation set on high-volume stores below 1, indirectly forcing ABSTAIN_SOFT | Low | Medium | M5 ticket T5.4 includes a backoff: if cap demotes everything, surface the highest-confidence single play with a "constrained by portfolio cap" note instead of going to ABSTAIN_SOFT. |

---

## Deletion list (sequenced)

Never delete a path until its replacement is on by default.

| Code/path | Deleted in | Replaced by | Notes |
|---|---|---|---|
| Hardcoded `p`/`effect_abs`/`ci_low`/`ci_high` constants in `_compute_candidates` (frequency_accelerator, aov_momentum, retention_mastery, journey_optimization, category_expansion, subscription_nudge, routine_builder, empty_bottle) | M4a (NaN'd) → M10 (branch deleted) | NaN + evidence_class | Audit C-1, C-3 |
| `_merge_multiwindow_candidates` min-p selection | M4b | `combine_multiwindow_statistics` re-routed for all evidence-class plays | Audit C-2 |
| `_calculate_calibrated_confidence` (dead code, `action_engine.py:2151`) | M10 | nothing | Audit L-1 |
| `_run_cohort_statistical_test` placeholder + `_enhance_candidates_with_cohorts` | M10 | nothing (re-introduce in Phase 3+ if real cohort design exists) | Audit M-1 |
| `bias_corrections = {7:1.0, 28:0.95, 56:0.90, 90:0.85}` | M5 (turned off), M10 (deleted) | none; if a correction returns it derives from data | Audit M-2 |
| `_calculate_business_confidence` 7-factor formula | M10 (after M4b/M7 collapse) | single deterministic 3-bucket label from `evidence_class` + consistency + audience | Audit C-4, PM Q3 |
| `confidence_score`, `final_score` as merchant-rendered fields | M10 | `confidence_label` + `merit_p50` (internal) | PM Q3 |
| 4-tier matrix (`PRIMARY/QUICK_WINS/WATCHLIST/EXPERIMENTS`) in storytelling | M10 | three sections (Recommended / Considered / Watching) | PM Q3 |
| `_FORCE_SINGLE_WINDOW = False` line in `select_actions` | M0 | explicit cfg key, defaulted in `utils.get_config` | Cleanup |
| Inline per-vertical priors scattered in `action_engine.py` (e.g., bestseller `base_rate=0.18`) | M2 (extracted), M10 (deleted from action_engine.py) | `config/priors.yaml` registry | DS architect |
| `ENABLE_COHORT_POOLING` flag and downstream branches | M10 | none | Audit M-1 |
| Seasonality input into `confidence_score` | M5 (decoupled), M10 (old branch deleted) | `launch_window.recommended` + separate `revenue_range.seasonality_factor` | DS architect |

---

## What-not-to-do list (anti-scope)

The implementer will be tempted to do these. Don't.

1. **Don't redesign `_compute_candidates` as one PR.** It is ~1000 lines covering 10 plays. Touch only what each ticket calls out.
2. **Don't introduce Bayesian credible intervals, hierarchical priors, or uplift terminology in Phase 1.** PM doc Q8 is explicit.
3. **Don't start integrating Klaviyo or Shopify APIs.** Project context is local CSV → HTML; the schema must be Klaviyo-ready (M9), but no real network calls.
4. **Don't generalize the play registry into a "rules engine."** Skeptic critique and PM doc Q9 both flag that the rejection list / state-of-store / honest abstain are the wow surface, not configurability. The registry is a typed Python dict over the existing 10 plays — period.
5. **Don't replace `combine_multiwindow_statistics` with a new combiner.** It exists, it's correct (audit cleared it). Just route to it.
6. **Don't write LLM-generated state-of-store prose in M1.** Observations are typed; prose assembly is template-only in Phase 1. (PM Q8: don't templatize prose first and try to ML-ify later — but template *assembly* of typed Observations is fine; LLM-narration is Phase 3+.)
7. **Don't fold `evidence_class` into `confidence_label` directly.** They are two fields. `evidence_class` is internal/typed; `confidence_label` is merchant-facing/qualitative. PM Q5 is explicit.
8. **Don't cap `recommendations` at 1 on the first month of testing.** ABSTAIN_SOFT exists for that. Don't bypass the state machine to "always show something."
9. **Don't compute audience overlap by re-running segment builders.** Use the customer-id sets already produced by `build_segments`.
10. **Don't refactor `utils.py` in flight.** `utils.py` is the most fragile shared module. Touch only the specific functions each ticket calls out. Anything that needs broader cleanup goes in M10.
11. **Don't add new CONFIDENCE_MODE values.** PM Q8: do not introduce a "learning" mode that secretly relaxes thresholds.
12. **Don't suppress fields in the EngineRun JSON that the renderer doesn't render.** `p_internal`/`ci_internal` must persist (PM Q8 ML hook).

---

# Milestones

## Milestone 0 — Freeze current behavior and golden outputs

**Goal**
Capture the exact byte-level output of the current engine on a fixed set of merchant CSVs, so every subsequent milestone can prove "no regression with flag off."

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/tests/` (new directory)
- `/Users/atul.jena/Projects/Personal/beaconai/scripts/freeze_golden.py` (new)
- `/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py` (one-line cleanup of `_FORCE_SINGLE_WINDOW`)
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` (no behavioral changes; only config defaulting cleanup)

**New artifacts**
- `tests/golden/` directory with subdirs `tests/golden/{merchant_id}/` containing: `actions.json`, `briefing.html`, `receipts/*.json`, `actions_log.json`, `engine_run.json` (current-shape).
- `scripts/freeze_golden.py` that runs the engine on each merchant CSV and writes goldens.
- `tests/test_golden_diff.py` that re-runs and diffs against golden, ignoring timestamp fields.
- `tests/fixtures/merchants.yaml` listing 3 baseline merchants (one cold-start ~60d, one mid ~$500K-ARR, one mid ~$2M-ARR) referencing CSVs already in `data/`.

**Tickets**
- **T0.1 — Pin merchant test fixtures.** Choose 3 merchants from `data/`: one micro/cold-start (e.g., `shopify_orders_micro_*`), one small (`SM_*`), one mid (`shopify_orders_mid.csv` or `BM_*`). Document the choice in `tests/fixtures/merchants.yaml` with anchor dates so each run is deterministic.
- **T0.2 — Add `scripts/freeze_golden.py`.** Run `main.py` against each fixture with a fixed anchor date and write outputs into `tests/golden/{merchant_id}/`. Strip non-deterministic fields (timestamps in `actions_log.json`, `run_id`).
- **T0.3 — Add `tests/test_golden_diff.py`.** Pytest that re-runs each merchant, normalizes outputs, and diffs against frozen golden. Failure prints unified diff.
- **T0.4 — Remove `_FORCE_SINGLE_WINDOW = False` line in `select_actions`.** Replace with explicit cfg key; default to current behavior. No behavior change. (Cleanup so M4a has a clean cfg surface.)
- **T0.5 — Document existing flag inventory.** Add `docs/engine_flags.md` listing every `os.getenv` and cfg key the engine reads today, with current default and "to be removed in M10" annotations.
- **T0.6 — Add a CI shadow-run target.** Make `pytest tests/test_golden_diff.py` part of the default test run. Any PR that changes goldens has to commit the regenerated goldens + a justification line.

**Acceptance criteria**
- Re-running `main.py` for any of the 3 merchants produces output byte-identical to `tests/golden/{merchant_id}/`, modulo timestamp normalization.
- `tests/test_golden_diff.py` passes on `engine-rework` HEAD before any other milestone starts.
- `docs/engine_flags.md` exists and lists every flag.

**Test cases**
- Run `python scripts/freeze_golden.py --regenerate` and confirm clean state.
- Run `pytest tests/test_golden_diff.py` — pass.
- Modify a constant in `_compute_candidates`; rerun pytest — fail with diff (proves the test is not vacuous).

**Rollback plan**
- M0 only adds tests + scripts and removes one debug line. Rollback = `git revert` the commit; engine output is unaffected since no production code path changes.

**What must not change yet**
- Any decision logic.
- Any flag defaults.
- The 4-tier matrix.
- The `_compute_candidates` function body.
- Any output schema.

---

## Milestone 1 — Data contracts and anomaly detection

**Goal**
Define the `EngineRun` JSON schema, the typed `Observation` model for state-of-store, and a stub anomaly detector — all *additive* (the new fields exist alongside today's output and are not yet rendered).

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/contracts.py` (extend; do not break)
- `/Users/atul.jena/Projects/Personal/beaconai/src/load.py` (anomaly detection hooks, ~10 lines)
- `/Users/atul.jena/Projects/Personal/beaconai/src/validation.py` (extend `DataValidationEngine` with anomalous-window check)
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` (call new contract + serialize EngineRun stub)

**New artifacts**
- `src/engine_run.py` — dataclass for `EngineRun`, `PlayCard`, `RejectedPlay`, `WatchedSignal`, `Observation`. Mirrors PM doc Q2 schema. Pydantic or `@dataclass`; no validation logic yet.
- `src/anomaly.py` — `detect_anomalous_windows(df, anchor_date) -> list[DataQualityFlag]` returning enum-coded flags: `bfcm_overlap`, `post_promo_window`, `refund_storm`, `test_order_anomaly`, `insufficient_clean_history`. Pure function, no state.
- `tests/test_engine_run_schema.py` — instantiate `EngineRun` with empty plays, assert serializability.
- `tests/test_anomaly.py` — fixtures with synthetic BFCM-window CSV and refund-storm CSV; assert flags are detected.

**Tickets**
- **T1.1 — Add `src/engine_run.py` with the full PM-Q2 schema as `@dataclass`es.** Include every field, including `measurement.p_internal` and `ci_internal`. No methods yet beyond `to_dict()`.
- **T1.2 — Add `src/anomaly.py`.** Implement 5 detectors as pure functions; combine into `detect_anomalous_windows`. Detector thresholds live in `config/anomaly_thresholds.yaml` (PM Q6 #3). Default thresholds match PM doc.
- **T1.3 — Wire `EngineRun` skeleton into `main.py`.** After `select_actions` returns, build an `EngineRun` populated from existing actions dict (legacy adapter pattern). Serialize to `receipts/engine_run.json`. Don't change anything else.
- **T1.4 — Add `Observation` builder for state-of-store.** New module `src/state_of_store.py`. Function `build_observations(aligned, scale) -> list[Observation]` produces 3–5 typed facts (AOV delta, repeat-rate delta, top-product velocity, anomaly notes). No prose templating yet — just typed data.
- **T1.5 — Extend `DataValidationEngine`.** Add an `AnomalousWindowCheck` that wraps `detect_anomalous_windows` and surfaces in the validation report. Output goes to receipts only; no gating yet.
- **T1.6 — Add `data_quality_flags[]` field to receipts.** Already in `EngineRun`; ensure it serializes even when empty.

**Acceptance criteria**
- `receipts/engine_run.json` is produced on every run for the 3 baseline merchants.
- `receipts/engine_run.json` schema validates against `src/engine_run.py` dataclasses.
- M0 golden tests still pass (legacy outputs unchanged).
- Synthetic BFCM-window fixture produces `data_quality_flags = ["bfcm_overlap"]`.
- No anomaly flag changes any merchant-facing output yet.

**Test cases**
- `tests/test_engine_run_schema.py` — instantiate, serialize, deserialize.
- `tests/test_anomaly.py` — 5 detector-specific fixtures; each detector fires correctly and others don't.
- `tests/test_observations.py` — feed canned `aligned` dict; assert 3 observations produced.
- `tests/test_golden_diff.py` from M0 — must still pass.

**Rollback plan**
- All new code is additive. Revert M1 commits; no merchant-visible output changes since flags default off and `engine_run.json` is a receipts-only artifact.

**What must not change yet**
- Any decision logic.
- The legacy `actions_bundle` shape.
- The `briefing.html` content.
- `_compute_candidates` body.

---

## Milestone 2 — Play registry

**Goal**
Extract the implicit play definitions scattered through `_compute_candidates` and the storytelling/copykit modules into a single typed registry. This is the foundation for M3 (candidate detection) and M4a/M4b (evidence class enforcement).

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py` (read-only; we extract metadata, don't change behavior)
- `/Users/atul.jena/Projects/Personal/beaconai/src/copykit.py` (read; copy templates referenced)
- `/Users/atul.jena/Projects/Personal/beaconai/src/execution_templates.py` (read)

**New artifacts**
- `src/play_registry.py` containing:
  - `class PlayDef` dataclass with fields: `play_id`, `display_name`, `evidence_class_default` (`"measured" | "directional" | "targeting"`), `requires_inventory` (bool), `audience_builder_ref` (str), `measurement_metric` (str | None), `vertical_applicable` (set[str]), `subvertical_applicable` (set[str] | None), `prior_keys` (list[str]), `targeting_disclaimer` (str | None).
  - `PLAYS: dict[str, PlayDef]` populated for the 10 existing plays plus `first_to_second_purchase`, `at_risk_repeat_buyer_rescue` (rename of retention_mastery), and `onsite_funnel_watch` (demoted journey_optimization).
- `config/priors.yaml` — extracted per-vertical/per-stage constants currently inline in `action_engine.py` (e.g., `bestseller_amplify.beauty.base_rate = 0.18`). Each prior carries `name`, `value`, `range_p10`, `range_p90`, `source_class`, `last_updated`, `applies_to`.
- `tests/test_play_registry.py` — assert every play_id used in the engine is in `PLAYS`.
- `tests/test_priors_yaml.py` — schema-validate `config/priors.yaml`.

**Tickets**
- **T2.1 — Add `src/play_registry.py` with `PlayDef` dataclass.** Define schema only; no plays yet.
- **T2.2 — Populate `PLAYS` for the 10 existing plays.** Use the play classification table in PM doc Q3 + memory.md "Play classification" as source of truth. `evidence_class_default` per the table.
- **T2.3 — Add three new entries: `first_to_second_purchase`, `at_risk_repeat_buyer_rescue`, `onsite_funnel_watch`.** Mark the latter as `evidence_class_default="targeting"` until onsite data exists. No engine logic for them yet — registry only.
- **T2.4 — Extract per-vertical priors into `config/priors.yaml`.** Inventory of inline constants comes from the audit (bestseller_amplify base rates, retention_mastery churn_reduction, etc.). Each entry is dated and source-classed (`observational`, `causal`, `expert`).
- **T2.5 — Add a "registry sanity" test.** Walk every place `_compute_candidates` emits a candidate and assert each `play_id` exists in `PLAYS`.
- **T2.6 — Document the registry contract.** `docs/play_registry.md` — one paragraph per play: definition, audience, measurement metric (if any), evidence class.

**Acceptance criteria**
- `src/play_registry.py` exists with `PLAYS` populated.
- `config/priors.yaml` exists, schema-valid.
- Test asserts every emitted candidate's `play_id` is registered.
- M0 golden tests still pass (no engine behavior change).

**Test cases**
- `tests/test_play_registry.py` — asserts 10+ plays present, all required fields populated.
- `tests/test_priors_yaml.py` — every prior has `source_class` ∈ {observational, causal, expert}.
- `tests/test_golden_diff.py` — passes.

**Rollback plan**
- Registry is config-only and unread by the engine until M3. Revert = delete files; engine continues unchanged.

**What must not change yet**
- `_compute_candidates` still emits its own candidate dicts using inline constants.
- No play is renamed in merchant-facing output yet.
- No prior is read from yaml at runtime yet (just tested for schema).

---

## Milestone 3 — Candidate detection without scoring

**Goal**
Build a parallel `detect_candidates(g, aligned, cfg, registry) -> list[Candidate]` that uses the registry to surface candidates from data-presence predicates only — no p-values, no effects, no CIs at this stage. Run it in shadow mode alongside the legacy path.

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/detect.py` (new)
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` (shadow invocation)
- `/Users/atul.jena/Projects/Personal/beaconai/src/segments.py` (reuse audience builders)

**New artifacts**
- `src/detect.py` with `detect_candidates(g, aligned, cfg, registry) -> list[Candidate]`. `Candidate` is a slim dataclass: `play_id, audience_ids, segment_definition, audience_size, fraction_of_base, primary_window`. No statistics.
- `src/audience_builders.py` — per-play audience builders extracted from `_compute_candidates` and `build_segments`. Pure functions: `(g, aligned) -> set[customer_id]`. Memoize within a run.
- `tests/test_detect.py` — for each merchant fixture, assert `detect_candidates` returns the expected play_ids.
- `tests/test_audience_builders.py` — unit-test each audience builder.

**Tickets**
- **T3.1 — Add `src/audience_builders.py`.** Move audience-construction logic for: winback_21_45, dormant_60_120, bestseller_buyers, ≥3-product cohort, single-product-skincare cohort, depletion-window cohort, full-price-buyers. Each is a function returning customer-ids, no statistics.
- **T3.2 — Add `src/detect.py:detect_candidates`.** For each `PlayDef` in `PLAYS`, call the registered audience builder; if `len(audience) >= min_n` (from registry/cfg), emit a `Candidate`. Otherwise, emit a `RejectedPlay` with `reason_code="audience_too_small"`.
- **T3.3 — Add shadow invocation in `main.py`.** Behind `ENGINE_V2_SHADOW=true` (on in dev/CI, off in prod), call `detect_candidates` after `select_actions`, write `receipts/v2_candidates.json`, log a summary diff (which plays both paths emitted, which only legacy, which only V2). Don't act on the diff; just log.
- **T3.4 — Wire the cold-start detector.** `cold_start = days_of_clean_data < 90` becomes a flag on `EngineRun`; in M3 it's just logged, not gating.
- **T3.5 — Add audience overlap computation.** `compute_overlaps(candidates) -> dict[(play_id_a, play_id_b), float]`. Pure function on customer-id sets. Used by M5 cannibalization gate.

**Acceptance criteria**
- `receipts/v2_candidates.json` exists for every run with `ENGINE_V2_SHADOW=true`.
- For each merchant fixture, the V2 candidate list is at least as long as the legacy candidate list (no plays disappeared).
- `tests/test_detect.py` passes — V2 detection produces expected play_ids on each fixture.
- M0 golden tests still pass.

**Test cases**
- `tests/test_audience_builders.py` — for synthetic g with known customers, each builder returns the expected set.
- `tests/test_detect.py` — winback play emitted for fixture with 50+ winback-window customers; not emitted otherwise.
- `tests/test_overlaps.py` — pairwise overlap between bestseller and frequency_accelerator computed correctly.
- `tests/test_golden_diff.py` — passes.

**Rollback plan**
- `ENGINE_V2_SHADOW=false` makes M3 a no-op. Revert = flag off; no merchant output change.

**What must not change yet**
- The legacy `_compute_candidates` is still authoritative for what merchants see.
- No statistical work in the new path.
- No reclassification of plays to `targeting`.

---

## Milestone 4a — Additive NaN-ing of fabricated stats + evidence_class field

**Goal**
Eliminate fabricated p-values, q-values, CIs, and effect sizes by NaN-ing them (additive — no semantic reclassification yet). Introduce `evidence_class` as a first-class candidate attribute. Drop redundant BH entries. Disable cohort-pooling and bias-correction defaults. This milestone is **additive and flag-gated**; it lands and bakes for a few days before M4b applies semantic changes (combiner reroute, reclassification, confidence collapse).

**This split is the result of DS Architect QA Change 6: M4 was the largest milestone in the original plan and the highest-stakes change. M4a reduces single-PR review burden by separating mechanical NaN-ing from semantic reclassification.**

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py` (targeted patches)
- `/Users/atul.jena/Projects/Personal/beaconai/src/scoring.py` (gate on NaN cleanly)
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` (drop `new_customer_rate` from BH list — one line; flip `ENABLE_COHORT_POOLING` and `ENABLE_REPEAT_RATE_BIAS_CORRECTION` defaults)

**New artifacts**
- `src/evidence.py` — `classify_evidence(candidate, registry) -> EvidenceClass` deterministic mapping per PM Q5 mapping rules.
- `tests/test_evidence_classification.py`.
- `tests/test_no_fabricated_stats.py` — asserts no candidate has hardcoded p/effect/CI.
- `tests/test_targeting_nan_safety.py` — asserts the NaN-handling invariant in `evidence.classify_evidence` (Change 3).

**Tickets**
- **T4a.1 — Set fabricated stats to NaN, behind `STATS_NAN_FOR_HARDCODED=true`.** In `_compute_candidates`, replace the constants for `frequency_accelerator` (~3362), `aov_momentum` (~3422), `retention_mastery` (~3485), `journey_optimization` (~3550), `category_expansion` (~3614), `subscription_nudge` (~3074), `routine_builder` (~3148), `empty_bottle` (~3219) with `np.nan` when the flag is on. Discount_hygiene fallback constants in `get_effect_params` (~542) get the same treatment.
- **T4a.2 — Make scoring NaN-safe.** `compute_score` and `confidence_from_ci` already handle NaN partially; audit and patch any branch that falls through to a non-zero contribution from NaN.
- **T4a.3 — Add `evidence_class` to candidate dicts.** In `_compute_candidates`, after each candidate is built, call `classify_evidence` (M4a new module) using the registry. Store on the candidate dict as `candidate["evidence_class"]`. Behind `EVIDENCE_CLASS_ENFORCED` (added but kept off-by-default in M4a; flipped on in M4b).
- **T4a.4 — NaN-handling invariant in `evidence.classify_evidence` (DS Architect QA Change 3).** This is the boundary where `evidence_class` is assigned. The invariant MUST be enforced here:
  - A row with NaN p-value AND `evidence_class == "targeting"` → maps deterministically to Targeting (this is expected and safe).
  - A row with NaN p-value AND `evidence_class == "measured"` → this is an engine bug; the code MUST raise an exception or fail validation rather than silently downgrade.
  - This invariant must be enforced at the boundary where `evidence_class` is assigned in `evidence.classify_evidence`.
  - Add `tests/test_targeting_nan_safety.py` asserting both branches: a NaN-p targeting candidate is accepted (deterministic Targeting); a NaN-p measured candidate raises.
- **T4a.6 — Drop `new_customer_rate` from BH list.** One-line fix in `kpi_snapshot_with_deltas` (`utils.py:1741`). Delete the duplicated p-value addition.
- **T4a.8 — Disable `ENABLE_COHORT_POOLING` and `ENABLE_REPEAT_RATE_BIAS_CORRECTION` defaults.** Set defaults to `false` in `utils.py`. (Code paths are not deleted yet — that's M10.) Note: T5.6 in M5 also references the bias-correction default; M4a sets it as part of the additive cleanup so M4b/M5 inherit a clean default.

**Acceptance criteria**
- `tests/test_no_fabricated_stats.py` passes: walk every candidate emitted on every merchant fixture; assert no `p`/`effect_abs`/`ci_low`/`ci_high` is one of the known constants from the audit.
- `tests/test_evidence_classification.py` passes (basic classification, semantic reclassification deferred to M4b).
- `tests/test_targeting_nan_safety.py` passes: NaN-p targeting accepted; NaN-p measured raises.
- For each merchant fixture, V2-shadow vs legacy diff (on `ENGINE_V2_SHADOW`) shows: targeting plays no longer carry numeric p/q/CI.
- M0 golden tests are regenerated for the M4a flag combo; new goldens are committed; PR reviewer signs off on the diff for each merchant.
- BH `new_customer_rate` duplication removed.

**Test cases**
- `tests/test_no_fabricated_stats.py` — fail if any candidate's p ∈ {0.02, 0.03, 0.04, 0.05} from a hardcoded source.
- `tests/test_evidence_classification.py` — basic typing assertions.
- `tests/test_targeting_nan_safety.py` — invariant from Change 3.
- `tests/test_golden_diff.py` — re-baselined against new M4a goldens.

**Rollback plan**
- Both flags default `false` until the milestone ships. Rollback = flip flags off, revert goldens. Engine returns to legacy behavior.
- M4a is the additive subset of the original M4 — high-risk but lower-risk than the combined milestone.

**What must not change yet**
- HTML briefing layout (still 4-tier).
- Renderer (still reads `confidence_score`/`final_score`).
- `EngineRun` is still receipts-only.
- Multi-window combiner reroute (M4b).
- Targeting reclassification (M4b).
- Confidence collapse (M4b).
- Cannibalization, materiality, inventory gates (M5).

---

## Milestone 4b — Targeting reclassification + combiner reroute + confidence collapse

**Goal**
Apply the semantic changes that M4a deferred: reclassify targeting plays, reroute multi-window combination through `combine_multiwindow_statistics`, collapse `_calculate_business_confidence` to the single-source `_calculate_statistical_confidence(p)`, normalize `evidence_for_action` labels, and re-baseline fixtures. This is the "decision-logic surgery" half of the original M4.

**M4b blocks M5 and M7 the same way the original M4 did. M4a must ship and bake briefly before M4b lands.**

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py` (extensive; targeted patches)
- `/Users/atul.jena/Projects/Personal/beaconai/src/scoring.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/stats.py` (read-only; combiner is correct)
- `/Users/atul.jena/Projects/Personal/beaconai/src/evidence.py` (consistency_across_windows semantics)

**New artifacts**
- `tests/test_multiwindow_combiner.py` — for measured plays, assert the combiner is called and min-p selection is not.
- `tests/test_consistency_across_windows.py` — asserts the pre-combination sign-agreement count semantics (Change 1).

**Tickets**
- **T4b.1 — Reclassify targeting plays.** For `subscription_nudge`, `routine_builder`, `empty_bottle`, `category_expansion`, `bestseller_amplify`, `vip_no_discount_nurture`, `replenishment_reminder`: set `evidence_class="targeting"` regardless of any computed p/effect. Their `measurement.*` block becomes None in the EngineRun mapper.
- **T4b.2 — Reroute multi-window combination.** Replace `_merge_multiwindow_candidates` invocation in `_compute_multiwindow_candidates` with `combine_multiwindow_statistics` for any candidate where `evidence_class in {"measured", "directional"}`. Targeting candidates skip combination entirely. Behind `STATS_NAN_FOR_HARDCODED` (paired flag).

  **`consistency_across_windows` semantics specification (DS Architect QA Change 1).** This is a load-bearing clarification. The combiner produces *one* p, *one* effect, *one* CI. `consistency_across_windows` is the robustness signal that sits alongside the combined estimate:
  - `consistency_across_windows` is a **pre-combination sign-agreement count** (count of windows whose effect points the same direction as the combined estimate).
  - It is NOT a post-combination p-value vote.
  - It is used as a **robustness signal**, not as independent evidence.
  - It must NOT be used to upgrade a play's evidence class.
  - **Default formula:** `consistency_across_windows = count of windows where sign(observed_effect) == sign(combiner.effect) AND |t-stat| > 1` — pre-combination, sign-only, not a p-vote.

  Add `tests/test_consistency_across_windows.py` asserting the formula on synthetic per-window stats: 4 windows with mixed signs and t-stats verify the count is sign-agreement-only and that windows below `|t|=1` are excluded.

- **T4b.3 — Decouple confidence from p multi-counting.** Patch `_calculate_business_confidence` to use only `_calculate_statistical_confidence(p)`; remove `gate_score` p-term, `signal_bonus`, `safety_multiplier` p-recoding. Behind `EVIDENCE_CLASS_ENFORCED=true` (flipped to `true` here in M4b).
- **T4b.4 — `evidence_for_action` consistency.** Label every targeting play's bullets with `(targeting recommendation)`, matching the existing `(heuristic)` label on subscription. Currently inconsistent (audit M-5).
- **T4b.5 — Update fixtures.** This is the part that breaks tests. Regenerate goldens with `STATS_NAN_FOR_HARDCODED=true` + `EVIDENCE_CLASS_ENFORCED=true` + combiner reroute on. Commit goldens with a labeled migration commit. Diff every change line-by-line in PR review.

**Acceptance criteria**
- For each merchant fixture, V2-shadow vs legacy diff (on `ENGINE_V2_SHADOW`) shows: measured plays now use `combine_multiwindow_statistics` output; targeting plays carry `evidence_class="targeting"` deterministically.
- `tests/test_consistency_across_windows.py` passes: pre-combination sign-agreement count formula enforced.
- `tests/test_multiwindow_combiner.py` passes.
- `confidence_score` for any single candidate moves only by the `_calculate_statistical_confidence` term — no p multi-counting.
- M0 golden tests are regenerated; new goldens are committed; PR reviewer signs off on the diff for each merchant.
- `evidence_for_action` bullets consistently labeled across all targeting plays.

**Test cases**
- `tests/test_evidence_classification.py` — winback with 200-customer audience and significant repeat-rate delta → `measured`; subscription_nudge → `targeting`; cold-start fixture's frequency_accelerator → `directional` or `weak`.
- `tests/test_multiwindow_combiner.py` — combiner called for measured plays; min-p selection not called.
- `tests/test_consistency_across_windows.py` — sign-agreement count, not p-vote.
- `tests/test_golden_diff.py` — re-baselined against new M4b goldens.

**Rollback plan**
- All M4b flags default `false` if reverted. Rollback = flip flags off, revert goldens to M4a baseline. Engine returns to M4a behavior (additive NaN-ing only).
- High-risk milestone — keep two CI lanes: one with flags on, one with flags off, until M5.

**What must not change yet**
- HTML briefing layout (still 4-tier).
- Renderer (still reads `confidence_score`/`final_score`).
- `EngineRun` is still receipts-only.
- Cannibalization, materiality, inventory gates (M5).

---

## Milestone 5 — Guardrail engine

**Goal**
Add the inventory gate, anomalous-window gate, audience-overlap/cannibalization gate, scale-aware materiality floor, and recently-run-fatigue stub. Each guardrail produces a `RejectedPlay` with a reason code rather than silently filtering.

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/guardrails.py` (new)
- `/Users/atul.jena/Projects/Personal/beaconai/src/load.py` (read inventory; no behavior change)
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` (wire guardrails into the V2 path)
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` (scale-aware floor function)

**New artifacts**
- `src/guardrails.py` exporting:
  - `gate_inventory(candidate, inventory_metrics) -> RejectedPlay | None`
  - `gate_anomaly(candidates, data_quality_flags) -> EngineRun.abstain | None`
  - `gate_cannibalization(candidates) -> tuple[list[Candidate], list[RejectedPlay]]`
  - `gate_materiality(candidate, scale) -> RejectedPlay | None`
  - `gate_recently_run(candidate, history_path) -> RejectedPlay | None`
- `data/recommended_history.json` (per-store; written by M9 but read here as a stub).
- `config/anomaly_thresholds.yaml` (already added in M1; thresholds tuned here).
- `tests/test_guardrails.py`.

**Tickets**
- **T5.1 — Inventory gate.** For SKU-pushing plays (`bestseller_amplify`, `routine_builder`, `category_expansion`, `overstock_demand_push`), require `days_of_cover >= 21`. Below → RejectedPlay with `inventory_blocked`. No-inventory-data → no-op + warning. Behind `INVENTORY_GATE_ENABLED=true`.
- **T5.2 — Anomalous-window gate.** Read `data_quality_flags` from M1. If any of {`bfcm_overlap`, `refund_storm`, `test_order_anomaly`, `insufficient_clean_history`} is set, signal `EngineRun.abstain.state = "abstain_hard"`. Behind `ANOMALY_GATE_ENABLED=true`.
- **T5.3 — Materiality gate (scale-aware).** Compute `materiality_floor` = max($5k, 2% × monthly_revenue) for ARR < $1M; max($10k, 3%) for $1M–$5M; max($25k, 5%) over $5M. Per-play `revenue_range.p50 < floor` → RejectedPlay with `materiality_below_floor`. Behind `MATERIALITY_FLOOR_SCALE_AWARE=true`.
- **T5.4 — Cannibalization gate.** Use `compute_overlaps` from M3. For overlap > 50%, demote lower-confidence play to RejectedPlay with `audience_overlap_with_higher_priority`. Then enforce sum of remaining `revenue_range.p50` ≤ 25% of monthly_revenue; demote lowest-priority until cap holds. **Backoff:** if cap demotes everything, retain top-1 with a "constrained_by_portfolio_cap" annotation (do not go to ABSTAIN_SOFT for this reason alone). Behind `CANNIBALIZATION_GATE_ENABLED=true`.
- **T5.5 — Recently-run-fatigue stub.** Read `data/recommended_history.json` if present; for any `(audience_id, play_id)` recommended in the last 28 days, demote to RejectedPlay with `recently_run_fatigue`. If file absent, no-op. (Writing of this file is M9.)
- **T5.6 — Disable bias correction.** Already defaulted off in M4a/T4a.8; this ticket confirms the default and removes any remaining call sites that bypass it. Path remains for M10 deletion.
- **T5.7 — Decouple seasonality from confidence.** Move `get_seasonal_multiplier` invocation out of `_calculate_business_confidence` and into `revenue_range.seasonality_factor` (sizing) + `launch_window.recommended` (advisory copy). Behind paired flags.

**Acceptance criteria**
- For a BFCM-window fixture, `EngineRun.abstain.state == "abstain_hard"`.
- For a fixture with bestseller play and `days_of_cover = 9`, the play appears in `RejectedPlay` with `inventory_blocked`, not in recommendations.
- For a synthetic fixture with 3 overlapping plays (>50% overlap pairwise), exactly the highest-confidence play is recommended; the other two are rejected with `audience_overlap_with_higher_priority`.
- Sum of `recommendations[].revenue_range.p50` ≤ 25% of monthly revenue on every test fixture.
- M0 goldens still pass with all M5 flags off.

**Test cases**
- `tests/test_guardrails.py` — one test per gate, plus a portfolio-level test combining all gates.
- `tests/test_anomaly_abstain.py` — synthetic refund-storm fixture → `abstain_hard`.
- `tests/test_inventory_gate.py` — fixture with no inventory file → gate is no-op.
- `tests/test_materiality_floor.py` — three ARR tiers tested.

**Rollback plan**
- Flags default off until each gate is signed off on the 3 fixtures. Rollback = flip flags off.

**What must not change yet**
- The HTML briefing renderer.
- Decision selector (M7).
- ABSTAIN_SOFT logic (M7).

---

## Milestone 6 — Economic sizing

**Goal**
Replace stacked-multiplier `expected_$` with audience-economics `revenue_range = (p10, p50, p90)` per PM Q3 + DS architect Stage 4. Surface assumption sources. Suppress dollar projections for cold-start.

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py` (new)
- `/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py` (`calculate_28d_revenue` deprecated path)
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` (read priors.yaml)

**New artifacts**
- `src/sizing.py` exporting:
  - `size_play(candidate, registry, priors, scale, cold_start) -> RevenueRange` returning `{p10, p50, p90, source, drivers, suppressed}`.
- `src/priors_loader.py` — caches `config/priors.yaml`.
- `tests/test_sizing.py`.

**Tickets**
- **T6.1 — Add `src/priors_loader.py`.** Lazy-load `config/priors.yaml` once per run; expose `get_prior(play_id, vertical, subvertical, key)`.
- **T6.2 — Add `src/sizing.py:size_play`.** Implement `audience × p_action × incremental_orders × AOV` per DS architect Stage 4. For evidence-based plays: `p_action` from store-observed effect (e.g., observed repeat-rate delta). For targeting plays: `p_action` = prior range; range derived by varying `p_action` over its p10/p90.
- **T6.3 — Suppress for cold-start.** If `cold_start=true` OR play is targeting AND `vertical_prior.source_class != causal`, set `revenue_range.suppressed = true`. Renderer in M8 hides the dollar number.
- **T6.4 — Add `drivers[]` provenance.** Each `revenue_range` carries the list of named inputs that produced it (PM Q8 ML hook).
- **T6.5 — Deprecate `calculate_28d_revenue` in V2 path.** Legacy path keeps using it; V2 path uses `size_play`. Don't delete `calculate_28d_revenue` yet — that's M10.
- **T6.6 — Shadow-compare V2 sizing vs legacy.** For each merchant fixture, log `legacy_expected_$` vs `v2_p50` and the ratio. Acceptance: V2 p50 should be smaller than legacy on heuristic plays (because legacy multiplied by Klaviyo benchmarks); approximately equal on measured plays (winback, discount_hygiene).

**Acceptance criteria**
- For every recommended play in V2, `revenue_range.p10 < revenue_range.p50 < revenue_range.p90` and `revenue_range.source ∈ {"store_observed", "vertical_prior", "blend"}`.
- Cold-start fixture: every play has `revenue_range.suppressed = true`.
- Measured plays (winback, discount_hygiene) have `source = "store_observed"` and a single-driver `drivers[]` (the observed metric).
- M0 goldens still pass; legacy `calculate_28d_revenue` unchanged.

**Test cases**
- `tests/test_sizing.py` — winback with 200 customers, AOV $80, observed repeat-rate uplift 4pp → p10/p50/p90 match expected formula.
- `tests/test_sizing.py::test_cold_start_suppression` — all plays suppressed.
- `tests/test_priors_loader.py` — yaml load + cached access.
- `tests/test_golden_diff.py` — legacy goldens pass.

**Rollback plan**
- V2 path is still gated by `ENGINE_V2=false`. Revert = flag off.

**What must not change yet**
- HTML briefing (still reads legacy `expected_$`).
- Decision selector (M7).

---

## Milestone 7 — Decision selector

**Goal**
Compose detection + classification + guardrails + sizing into a single `decide(g, aligned, cfg) -> EngineRun`. Implement the state machine: PUBLISH / ABSTAIN_SOFT / ABSTAIN_HARD. Implement class-aware ranking. Cap recommendations at 3.

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` (new — the V2 entry point)
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` (wire V2 path behind `ENGINE_V2`)

**New artifacts**
- `src/decide.py:decide(g, aligned, cfg) -> EngineRun`.
- `tests/test_decide.py`.
- `tests/fixtures/abstain_hard_*.json`, `abstain_soft_*.json`, `publish_*.json` — expected EngineRun outputs.

**Tickets**
- **T7.1 — `decide()` skeleton.** Wire detect → evidence_classify → size → apply guardrails → select. Inputs/outputs typed.
- **T7.2 — Class-aware ranking.** Within recommendations, sort by `evidence_class` priority (`measured > directional > targeting`), then by `revenue_range.p50` within class (PM Q10 #7 — class-first chosen).
- **T7.3 — Recommendation cap.** Max 3 PlayCards. Drop excess to `considered` with reason `cap_exceeded` (new reason code; add to enum).
- **T7.4 — Require ≥1 measured/directional + materiality interaction rule (DS Architect QA Change 2).** If 0 of either, demote to ABSTAIN_SOFT (PM Q4).

  **Materiality + class-aware-ranking interaction rule.** This is a load-bearing addition that closes the failure mode where a TARGETING-only briefing publishes as PUBLISH:
  - If, after materiality and cannibalization gating, there are zero measured-or-directional recommendations remaining, the engine MUST set `decision_state = ABSTAIN_SOFT` regardless of how many TARGETING plays remain.
  - A targeting-only briefing must NOT be published as a normal PUBLISH state.
  - Targeting plays alone are insufficient evidence to justify a "we have a plan this month" briefing.

  Add a test: synthetic fixture where materiality + cannibalization gates remove all measured/directional candidates but leave 2 TARGETING candidates → assert `decision_state == "ABSTAIN_SOFT"`.

- **T7.5 — RejectedPlay assembly.** From the union of guardrail rejections, audience-too-small, no-measured-signal, cap-exceeded. Cap at 6 rendered (PM Q10 #6); the closest-to-firing 6.
- **T7.6 — `would_fire_if` text builder.** For each RejectedPlay, generate plain-English copy ("would fire if audience size reaches 80; currently 38"). Template-only; no LLM.
- **T7.7 — Abstain mode logic.** ABSTAIN_HARD: any data_quality_flag triggers; PlayCards = []. ABSTAIN_SOFT: 0 measured/directional clear + ≥0 targeting; PlayCards = top-2 targeting (clearly labeled). PUBLISH: at least one measured/directional + others. Behind `ABSTAIN_MODE_ENABLED=true`.
- **T7.8 — `EngineRun` finalization.** Populate `state_of_store` (from M1), `watching` (from new sub-step T7.9), `recommendations`, `considered`, `data_quality_flags`, `abstain`.
- **T7.9 — Watching section builder.** `src/watching.py` — produce 1–4 typed `WatchedSignal` entries: metrics being tracked but not actionable yet (e.g., AOV down 2% — would need 5% drop to fire AOV play).

**Acceptance criteria**
- For each merchant fixture, `decide()` produces a fully-populated `EngineRun` matching expected fixtures.
- ABSTAIN_HARD on BFCM-window fixture; PlayCards = [].
- ABSTAIN_SOFT on cold-start fixture; PlayCards has 0–2 targeting items, all suppressed.
- ABSTAIN_SOFT on the materiality-strips-all-measured fixture (Change 2 rule); targeting plays NOT published as PUBLISH.
- PUBLISH on the standard-merchant fixture; PlayCards in priority order.
- M0 goldens still pass (legacy path).

**Test cases**
- `tests/test_decide.py` — 3 fixtures × 3 abstain states.
- `tests/test_ranking.py` — measured > targeting regardless of p50 ordering.
- `tests/test_cap.py` — 5 valid candidates → 3 recommended + 2 in considered with `cap_exceeded`.
- `tests/test_targeting_only_no_publish.py` — Change 2 rule: 0 measured/directional after gating + N targeting → ABSTAIN_SOFT.

**Rollback plan**
- `ENGINE_V2=false` keeps everything legacy. V2 path runs only in shadow.

**What must not change yet**
- HTML briefing renders legacy output.
- M8 builds the new renderer.

---

## Milestone 8 — Play Thesis merchant output

**Goal**
Replace the 4-tier matrix briefing with the three-section layout (Recommended / Considered / Watching) plus state-of-store paragraph and data-quality footer. Render targeting cards distinctly. Render abstain modes distinctly. Default-flip `ENGINE_V2_OUTPUT=true` after parity review.

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling.py` (extensive; net change = new render path, old kept until M10)
- `/Users/atul.jena/Projects/Personal/beaconai/src/briefing.py` (route between legacy and V2)
- `/Users/atul.jena/Projects/Personal/beaconai/src/copykit.py` (new copy templates for rejection reasons + abstain memo)

**New artifacts**
- `src/storytelling_v2.py` — new render path consuming `EngineRun`.
- Templates for: PUBLISH briefing, ABSTAIN_SOFT briefing, ABSTAIN_HARD "Data quality memo", per-play card (measured/directional/targeting variants), rejected card, watching card.
- `tests/test_render_v2.py` — golden HTML for each layout.
- `tests/test_targeting_no_dollar_headline.py` — grep-asserts no `$X,XXX` pattern outside the range chip element on rendered targeting cards (DS Architect QA Change 4).

**Tickets**
- **T8.1 — Three-section renderer.** `render_engine_run(engine_run) -> str` produces the new HTML. Sections: state-of-store (lead), Recommended (0–3 cards), Considered (3–6 cards), Watching (1–4 cards), Data quality footer.
- **T8.2 — Rejected-play card.** Per-play: title, one-line reason text from `reason_code`, `evidence_snapshot`, `would_fire_if`. Visual treatment muted vs Recommended.
- **T8.3 — Abstain renderers.** ABSTAIN_HARD = "Data quality memo" template (no plays, prominent flag explanation, what merchant should check). ABSTAIN_SOFT = standard layout with prominent "no measured opportunities cleared" callout + 1–2 targeting cards if present.
- **T8.4 — State-of-store paragraph.** Template-assembled from typed `Observation` list.
- **T8.5 — Targeting card visual treatment.** Different border, fixed disclaimer sentence ("This is a who-to-send-to recommendation…"), no `revenue_range.p50` headline (only the range). Per PM Q5 + Q9.

  **Acceptance criterion (DS Architect QA Change 4) — no standalone p50 dollar headline on targeting cards:**
  - Targeting cards MUST NOT display a standalone p50 dollar headline.
  - The rendered HTML must not show a single-number dollar headline for targeting plays — only the range chip.
  - This must be a tested invariant. The corresponding test is `tests/test_targeting_no_dollar_headline.py` that grep-asserts the rendered targeting card HTML for the absence of any `$X,XXX` pattern outside the range chip element.

- **T8.6 — `briefing.py` router.** Behind `ENGINE_V2_OUTPUT=true`, call `storytelling_v2.render_engine_run`. Otherwise legacy.
- **T8.7 — Legacy adapter for downstream.** `legacy_actions_from_engine_run(engine_run) -> dict` produces the old `actions_bundle` shape so `actions_log.json`, `copykit.render_copy_for_actions`, etc. keep working without modification. Lets us flip the renderer without touching action consumers.
- **T8.8 — Parity review.** For each merchant, render both legacy and V2 briefings; review side-by-side; adjust copy where V2 loses a useful detail. Ship `ENGINE_V2_OUTPUT=true` only after sign-off.

**Acceptance criteria**
- All 12 PM Phase 1A acceptance criteria (Appendix B of PM doc) pass on the 3 merchant fixtures.
- `briefing.html` for each merchant renders with three sections, no p-values/q-values/CIs, no `confidence_score`/`final_score` in the merchant view.
- ABSTAIN_HARD fixture renders the data-quality memo with no plays.
- ABSTAIN_SOFT fixture renders with the explicit "no measured opportunities" callout.
- Targeting plays in cold-start fixture do not display dollar numbers.
- **Targeting cards on every fixture pass `tests/test_targeting_no_dollar_headline.py`: no standalone `$X,XXX` pattern outside the range chip element (Change 4).**
- After flag flip, M0 goldens are re-baselined for V2 output (with a labeled migration commit; legacy goldens kept in `tests/golden_legacy/` for reference until M10).

**Test cases**
- `tests/test_render_v2.py` — for each fixture, render HTML and compare to expected.
- `tests/test_render_v2_targeting.py` — targeting card has disclaimer; no p50 headline.
- `tests/test_render_abstain.py` — both abstain modes render correctly.
- `tests/test_targeting_no_dollar_headline.py` — grep-assert no `$X,XXX` pattern outside the range chip element on every rendered targeting card across all fixtures.

**Rollback plan**
- `ENGINE_V2_OUTPUT=false` returns to legacy briefing. The engine still computes V2 in shadow; only the renderer reverts.
- High-stress milestone — keep legacy renderer in repo until M10.

**What must not change yet**
- Anything in `actions_log.json` (legacy adapter handles this).
- Any downstream copykit logic for actual action copy.

---

## Milestone 9 — ML readiness / outcome logging

**Goal**
Persist enough structured data per run that a future calibration / uplift / hierarchical-prior layer can plug in without re-architecture. Add the data, do not claim ML lift.

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/outcome_log.py` (new)
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` (wire outcome write)

**New artifacts**
- `src/outcome_log.py` — `write_recommended_history(engine_run, history_path)` appends to `data/recommended_history.json` per store.
- `data/recommended_history.json` (gitignored; created at runtime).
- `tests/test_outcome_log.py`.

**Tickets**
- **T9.1 — `recommended_history.json` writer.** Append `{store_id, run_id, anchor_date, plays_recommended, plays_rejected}` after every run. Uses `EngineRun` directly. Behind `OUTCOME_LOG_ENABLED=true` (default on).
- **T9.2 — `measurement.p_internal` and `ci_internal` persistence.** Already in `EngineRun` from M1. Verify they survive serialization end-to-end. Confirm they are NOT in any rendered HTML.
- **T9.3 — Drivers provenance in `revenue_range`.** Already added in M6; here we lock down the schema (`drivers` is required to be non-empty for any non-suppressed range).
- **T9.4 — Stub realized-vs-predicted reader (DS Architect QA Change 5).** `src/calibration_stub.py` — function `load_realization_factors(history_path) -> dict`. Establishes the interface a future ML layer plugs into; the engine doesn't read it yet.

  **Return shape (Change 5).** Rather than returning `{}`, the stub MUST return three declared fields so future calibration work doesn't require API changes:
  - `prior_overrides`
  - `evidence_thresholds`
  - `materiality_overrides`

  Each field is an empty dict by default. The stub itself remains a stub — no logic populates these fields in Phase 1 — but the shape is the contract:

  ```python
  def load_realization_factors(history_path) -> dict:
      return {
          "prior_overrides": {},        # {prior_key: override_value}
          "evidence_thresholds": {},    # {play_id: {threshold_name: value}}
          "materiality_overrides": {},  # {scale_band: {floor_param: value}}
      }
  ```

  Add a test asserting the return dict has exactly these three keys, each mapping to an empty dict.

- **T9.5 — Receipts page surfaces internal stats.** A merchant-invisible debug HTML reads `engine_run.json` and shows p_internal/ci_internal/drivers for each play. Lives at `receipts/debug.html`.

**Acceptance criteria**
- After 3 consecutive runs on the same merchant, `data/recommended_history.json` has 3 entries.
- Every PlayCard with `evidence_class in {measured, directional}` has non-null `measurement.p_internal`.
- `tests/test_outcome_log.py` passes.
- `load_realization_factors()` returns a dict with keys `{prior_overrides, evidence_thresholds, materiality_overrides}` (Change 5).
- Internal stats appear in `receipts/debug.html` but NOT in `briefing.html`.

**Test cases**
- `tests/test_outcome_log.py` — append, then re-read.
- `tests/test_calibration_stub_shape.py` — Change 5 return-shape assertion.
- `tests/test_internal_stats_not_rendered.py` — search rendered briefing HTML; assert no "p_internal", "ci_internal", "p =", "q =" string appears.

**Rollback plan**
- `OUTCOME_LOG_ENABLED=false` disables logging only. No effect on briefing.

**What must not change yet**
- The engine doesn't *read* the history file for calibration. (Only the recently-run-fatigue gate from M5 reads it.)
- No "calibrated" claim in any merchant copy.

---

## Milestone 10 — Cleanup and migration

**Goal**
Remove deprecated paths, deleted code, and now-redundant flags. Only run after M8 has been default-on for one full release cycle (i.e., on the latest merchant fixtures, V2 output is the only output anyone sees and there are no open bug reports tracing to V2).

**Files likely touched**
- `/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py` (large deletions)
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` (flag removal)
- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling.py` (legacy renderer deleted)
- `/Users/atul.jena/Projects/Personal/beaconai/src/scoring.py` (most functions deprecated)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/golden_legacy/` (deleted)

**New artifacts**
- None — this milestone is deletion.

**Tickets**
- **T10.1 — Delete fabricated-stats branches.** Hardcoded constants in `_compute_candidates` for the 8 plays (already NaN'd in M4a); now remove the branch entirely. Replace with `evidence_class = "targeting"` short-circuit emit.
- **T10.2 — Delete `_merge_multiwindow_candidates`.** Replaced by `combine_multiwindow_statistics` in M4b.
- **T10.3 — Delete `_calculate_calibrated_confidence`.** Dead.
- **T10.4 — Delete `_calculate_business_confidence` and the gate_score/signal_bonus/safety_multiplier helpers.** Replaced by `evidence_class`-driven label in M4b.
- **T10.5 — Delete `_run_cohort_statistical_test` and `_enhance_candidates_with_cohorts`.** Half-implemented; placeholder p=1.0.
- **T10.6 — Delete `bias_corrections` dict and the wrapping logic in `kpi_snapshot_with_deltas`.**
- **T10.7 — Delete `calculate_28d_revenue`.** V2 sizing replaces.
- **T10.8 — Delete legacy 4-tier renderer in `storytelling.py`.** Keep `storytelling_v2.py` as canonical.
- **T10.9 — Delete `tests/golden_legacy/`.**
- **T10.10 — Remove deprecated flags.** From `utils.py` defaults: `ENABLE_COHORT_POOLING`, `ENABLE_REPEAT_RATE_BIAS_CORRECTION`, `ENABLE_ENHANCED_STATISTICS`, `ENGINE_V2`, `ENGINE_V2_OUTPUT`, `ENGINE_V2_SHADOW`, `STATS_NAN_FOR_HARDCODED`, `EVIDENCE_CLASS_ENFORCED`, `INVENTORY_GATE_ENABLED`, `MATERIALITY_FLOOR_SCALE_AWARE`, `REJECTED_PLAYS_RENDERED`, `ABSTAIN_MODE_ENABLED`. Update `docs/engine_flags.md`.
- **T10.11 — Move `briefing.py` router to V2-only.** No more legacy fork.
- **T10.12 — Inline-prior cleanup.** Verify no remaining inline per-vertical constants in `action_engine.py`; everything reads from `config/priors.yaml`.

**Acceptance criteria**
- `git grep -i "force_single_window\|_calculate_calibrated_confidence\|_calculate_business_confidence\|bias_corrections\|_merge_multiwindow_candidates\|calculate_28d_revenue\|ENABLE_COHORT_POOLING"` returns no hits.
- M8 acceptance criteria still pass on V2 goldens.
- `docs/engine_flags.md` is dramatically shorter.
- Engine runs end-to-end on all 3 fixtures with no flags set (defaults are V2 behavior).

**Test cases**
- `tests/test_no_legacy_paths.py` — grep-style assertions for absence of deleted symbols.
- `tests/test_render_v2.py` — passes.
- `tests/test_decide.py` — passes.
- All M0 V2 goldens — pass.

**Rollback plan**
- M10 is pure deletion. Rollback = `git revert` the deletion commits. Each ticket is one commit so individual deletions are revertable.
- Critical: do NOT do M10 in a single commit. Each T10.x is its own PR.

**What must not change yet**
- Nothing — this is the final milestone in scope. New product features (Klaviyo integration, calibration loop, hierarchical priors) are Phase 2+.

---

## Critical path

M0 → M1 → M2 → M4a → M4b → M7 → M8 → M10. M3 is required for M5/M7 but can ship on the same week as M2. M5 and M6 are independent and can run in parallel by different sub-engineers; both block M7. M4a must ship and bake briefly before M4b lands.

If a single engineer has 6 weeks, the realistic sequence is:
- Week 1: M0 + M1.
- Week 2: M2 + M3.
- Week 3: M4a (additive nan-ing — additive/flag-gated; lower review burden).
- Week 4: M4b (combiner reroute + reclassification + confidence collapse — the heavy week; fixture migration is the long pole).
- Week 5: M5 + M6 in parallel.
- Week 6: M7 + M8 (PM Phase 1A complete).
- Defer M9 + M10 to a follow-up cycle.

---

## Top breakage risk

**Risk #1 above (NaN-cascade through scoring) is the dominant breakage risk.** Setting hardcoded p/effect/CI to NaN in M4a and rerouting through the combiner in M4b will cascade through `benjamini_hochberg`, `confidence_from_ci`, `compute_score`, `_calculate_business_confidence`, and the tier-matrix assignment. Every test fixture changes; PRIMARY tier counts shift; the merchant-facing briefing changes character even before the renderer is updated in M8. The mitigation is M0 + the M4a/M4b split + the `STATS_NAN_FOR_HARDCODED` flag — but the flag is only a partial defense, because once we flip it on (which we must, to unblock M5/M6/M7), we cannot ship M8 fast enough to keep pace. The honest engineering posture: budget 2 extra days in M4b for fixture migration and PR review, and treat the M4b PR as the most critical merge of the entire phase. M4a's job is to soak up the mechanical risk first so M4b is "just" the semantic surgery.

---

## Most important deviation from memory.md / PM doc

**Memory.md treats Phase 1 as a 12-item must-have list.** PM doc adds product-shape requirements but accepts the 12 items. **My deviation: those 12 items are not equally costly, and 4 of them (the renderer collapse, the abstain modes, the rejection-list rendering, and the multi-window combiner reroute) carry 80% of the breakage risk.** This plan separates "schema and registry" (M1, M2 — additive, low-risk) from "decision-logic surgery" (M4a additive nan-ing → M4b reclassification + combiner reroute — high-risk, now split into two PRs) from "renderer surgery" (M8 — high-risk), and forbids combining them into one PR.

**Second deviation: PM doc's Phase 1A maps to "10 working days" but actually requires M0–M3 prerequisites that PM doc treats as implicit.** I have made them explicit. The honest 1A-equivalent work is 14–18 working days when prerequisites are counted, not 10. The 10-day frame is achievable only if M0 fixtures and M2 registry are pre-baked.

**Third deviation: against the DS architect's "drop saturation guard"** (skeptic F-4 also flags this). Saturation guard / `audience_coverage_cap` is *retained and renamed* in M5 ticket T5.4's portfolio cap. The architect's design implicitly removed it; I keep it because without it, the new sizing formula projects worse on small stores.
