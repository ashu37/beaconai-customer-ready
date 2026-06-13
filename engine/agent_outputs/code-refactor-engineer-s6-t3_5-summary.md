# S6-T3.5 PARTIAL CLOSEOUT — `replenishment_due` activation scaffolding landed; Commit C flag flip deferred (Path D)

**Date:** 2026-05-19
**Branch:** `post-6b-restructured-roadmap`
**Status:** PARTIAL CLOSEOUT (5 commits accepted; Commit C atomic flag flip deferred)
**Path:** D (DS-architect locked, 2026-05-19, agent `a3e8cc44e77dcf281`)
**Flag posture:** `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` remains default OFF

---

## 1. Approved scope

S6-T3.5 was originally scoped as a 3-commit closeout that would:

1. Prereq 1 — populate `RejectedPlay` surface fields at Considered-routing seams so the T3.z renderer reads real data when a held `replenishment_due` candidate routes to Considered.
2. Prereq 2 — author the `replenishment_due` audience-floor cell in `gate_calibration.yaml` + strict resolver + `D-FLOOR-replenishment_due` decision entry + envelope test.
3. Commit C — atomic flip of `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` ON + re-pin 4 slate fixtures.

The DS-architect audit (2026-05-19) reshaped this into a 5-commit **partial closeout** after diagnosing that the synthetic Beauty G-1 fixture's `cohort_n` collapses to 0 at the D-S6-4 per-SKU N≥30 gate — *binding upstream* of the D-FLOOR-replenishment_due floor of 150. The diagnosis is fixture-shape, not gate-logic.

## 2. Three-path founder deliberation + DS verdict

The founder weighed three paths before landing Path D:

- **Path A — Author a new Beauty fixture archetype with hero-SKU repeat concentration sufficient to clear D-S6-4.** REJECTED. Concentrates the engine's activation risk on a synthetic surface that the real beta cohort will obsolete within a sprint. Investment-to-shelf-life ratio unfavorable.
- **Path B — Tune D-S6-4 / D-S6-5 / D-FLOOR-replenishment_due now to surface the play on Beauty G-1.** REJECTED. DS-architect surfaced (now KI-NEW-H) that these three locked decisions are a coupled system whose joint recalibration belongs in Phase 9 against real beta outcome data, not against a single synthetic fixture's shape.
- **Path C — Ship Commits A+B and defer Commit C indefinitely without scaffolding-preservation discipline.** REJECTED. Risks future agent removing the scaffolding under M5.3 / M7 invariant pressure ("dead code, no consumer").
- **Path D — Partial closeout.** ACCEPTED. Ship A + B + a deferral scaffold (C-scaffold) that explicitly documents the deferred state, files the architectural KIs, and preserves the scaffolding for real-beta activation. DS-architect locked this path 2026-05-19.

## 3. Commit ledger

| # | Hash | Title |
|---|------|-------|
| A | `23fd73d` | Prereq 1: RejectedPlay surface field population at 3 Considered-routing seams + latent `CADENCE_DUE_REPEAT_BUYER` enum fix + 8 new tests + xfail-mark 4 slate pins |
| B | `e0b0eab` | Prereq 2: `replenishment_due` audience-floor cell + strict resolver + `D-FLOOR-replenishment_due` LOCKED + D-S6-3 envelope refresh + 42-cell envelope test + KI-NEW-B cross-link |
| C-scaffold | `4199e67` | Partial-closeout scaffolding: refresh xfail reason strings on the 4 slate-pin tests to cite D-S6-4 cohort_n=0 + KI-NEW-G resume trigger. NO flag flip. NO fixture re-pin. |
| D | `73bc16d` | File 3 new KIs (KI-NEW-G / KI-NEW-H / KI-NEW-I) documenting the deferred activation, the architectural coupling surfaced by DS, and the Watching-row operator-visibility gap. |
| E | (this commit) | memory.md S6-T3.5 entry + this summary file |

Pre-existing context: Commits A and B were authored by a prior agent attempt with the spec's intended *substance* but slightly different commit-boundary placement (xfails landed in A instead of being held to C-scaffold). The end-state is semantically identical to the spec; re-authoring was rejected to avoid churn.

## 4. Scaffolding preserved (DO NOT remove)

The following scaffolding is live, unit-tested, and consumer-aware. It will activate atomically when KI-NEW-G's trigger event fires. Removing any of it as "dead code" would silently regress the future activation:

- `config/priors_sources/replenishment_due__base_rate__beauty.md` — prior block, validated_external status, anchors D-S6-3 envelope citation.
- `config/gate_calibration.yaml::audience_floors.replenishment_due` — per-(subvertical, stage) floors: beauty {60/150/350/1000}, `mixed_beauty` 1.5× multiplier, no supplements cell (asymmetric per D-PRIORS-replenishment_due_supplements_deferred).
- `docs/DECISIONS.md::D-FLOOR-replenishment_due` — LOCKED 2026-05-19, full template with DS attribution.
- `src/profile/builder.py::_resolve_audience_floor_cell_strict` — strict variant of the audience-floor resolver that does NOT cascade to `_default_by_stage`; returns `(None, None)` for missing cells. Wired into `derive_gate_calibration`'s "Strict-cell plays" loop.
- `src/decide.py` (+89 lines) — surface-field population (`audience_size`, `audience_definition`, `mechanism`) on `RejectedPlay` at all three Considered-routing seams (`_route_window_disagreement_holds`, `_route_prior_unvalidated_holds`, `populate_considered_from_candidates`).
- `src/priors_loader.py` — `WouldBeMeasuredBy.CADENCE_DUE_REPEAT_BUYER` enum value (latent fix; symptom was silent mechanism-rendering failure when replenishment_due routes through the renderer).
- S6-T3.y audience-floor sensitivity driver — present on validated-path PlayCards, fires on Beauty winback today (robust → omits), will fire on Beauty replenishment_due when flag flips.
- S6-T3.z Considered render pass — reads the 3 surface fields above, conditional cohort row + mechanism line + PRIOR_UNVALIDATED honest-dollar copy + sensitivity render branches.
- `tests/test_s6_t3_5_considered_surface_population.py` — 8 tests pinning surface-field population at all 3 seams.
- `tests/test_s6_t3_5_replenishment_due_floor_resolver.py` — 42 tests pinning the full beauty × stage × subvertical floor grid + mixed_beauty multiplier + supplements-returns-None.

## 5. Three new KIs filed (Commit D)

- **KI-NEW-G** "`replenishment_due` Commit C activation pending real beta repeat-purchase-concentrated catalog" — names the trigger event (Phase 9 beta-onboarding store at GROWTH/skincare with hero-SKU repeat-buyer count ≥150 in ±½-cadence window). Activation happens against the real-store fixture, not a re-shaped synthetic Beauty G-1.
- **KI-NEW-H** "D-S6-4 + D-S6-5 + D-FLOOR-replenishment_due jointly recalibrate in Phase 9 as a coupled system" — DS-architect surfaced: per-SKU N≥30 gate is structurally hostile to small-merchant validation; the three locked decisions must recalibrate together in a single Phase 9 ticket. Candidate adjustments documented: drop per-SKU N to 15 with widened CI, OR aggregate across SKU class, OR route the suppressed case to Watching (per KI-NEW-I).
- **KI-NEW-I** "Watching-row routing for `replenishment_due` cohort_n=0 from D-S6-4" — today's `cohort_n=0`-from-D-S6-4 case produces no Considered card AND no Watching row (invisible suppression). Should route to Watching with operator-readable copy parallel to KI-22 / KI-23: "Replenishment-due audience not yet measurable — your top SKUs need 30+ repeat buyers each before cadence inference is reliable."

Cross-links wired between the three new KIs and to KI-NEW-B, KI-22, KI-23, D-FLOOR-replenishment_due, D-S6-4, D-S6-5.

## 6. Resume trigger (when does Commit C re-open?)

When KI-NEW-G's trigger fires — a Phase 9 beta-onboarding store with hero-SKU repeat-buyer count ≥30 per SKU AND cohort ≥150 in the ±½-cadence window — flip `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` ON, re-pin the 4 currently-xfailed slate-pin tests against the real-store byte-stream, lift the xfails. All scaffolding is in place; no new code required for activation.

If KI-NEW-H lands first (joint recalibration of D-S6-4 + D-S6-5 + D-FLOOR), the trigger may shift — the recalibration may lower per-SKU N to 15 and reduce the activation bar against real beta cohorts. The two KIs are coupled; whichever lands first informs the other.

## 7. Files changed (this closeout: Commit C-scaffold + D + E)

- `tests/test_s6_5_t5_atomic_repin.py` — xfail reason strings refreshed on 2 tests
- `tests/test_slate_regression_beauty_brand.py` — xfail reason string refreshed
- `tests/test_slate_regression_supplements_brand.py` — xfail reason string refreshed
- `KNOWN_ISSUES.md` — KI-NEW-G + KI-NEW-H + KI-NEW-I appended; open-count table updated (Architectural-limitations 10 → 13; Total 19 → 22)
- `memory.md` — S6-T3.5 partial-closeout entry appended
- `agent_outputs/code-refactor-engineer-s6-t3_5-summary.md` — this file

(Commits A and B already landed; their files are listed in their respective commits.)

## 8. Tests / checks

- Suite baseline (post-Commit-B, unchanged by C-scaffold + D + E): **1497 passed, 14 skipped, 4 xfailed, 0 failed.**
- 4 xfailed (strict=False): the Beauty + supplements slate-pin tests, with refreshed reason strings citing the D-S6-4 root cause and KI-NEW-G resume trigger.
- M0 goldens: byte-identical.
- Beauty + supplements pinned fixtures: sha256 unchanged (no flag flip).
- briefing.html forbidden-token sweep: clean (no `p =`, `q =`, `CI`, `confidence_score`, `final_score`, numeric confidence %).

## 9. Behavior changes

None. Engine output is byte-identical to pre-S6-T3.5 state on all 5 pinned fixtures.

The only consumer-visible change at flag-flip time (deferred) will be that `replenishment_due` candidates begin surfacing on Beauty merchants whose cohort clears the D-FLOOR floor AND whose SKUs clear the D-S6-4 per-SKU N≥30 gate.

## 10. Artifacts added

- `agent_outputs/code-refactor-engineer-s6-t3_5-summary.md` (this file)
- `memory.md` S6-T3.5 PARTIAL CLOSEOUT entry

## 11. Remaining risks

- **Scaffolding-removal risk:** a future agent unfamiliar with the deferral context could remove the strict floor resolver, T3.y driver, T3.z renderer, or surface-field population as "dead code, no consumer." Mitigated by: (a) this summary file, (b) memory.md entry, (c) KI-NEW-G cross-link from `D-FLOOR-replenishment_due`, (d) load-bearing pin tests that fail loudly if scaffolding is removed.
- **D-S6-4 small-merchant hostility (KI-NEW-H):** real beta data may confirm that the per-SKU N≥30 gate suppresses `replenishment_due` on ≥60% of small consumable-repeat-dominated merchants. Joint Phase 9 recalibration with D-S6-5 and D-FLOOR-replenishment_due is required; tuning any one in isolation will yield a wrong answer.
- **Invisible-suppression UX (KI-NEW-I):** today's `cohort_n=0` failure mode is operator-hostile; merchants whose hero SKUs miss the per-SKU gate get no signal at all. Should be closed alongside Commit C activation (Watching-row routing).
- **xfail strict=False discipline:** a real-fixture re-pin that *happens* to produce a sha256 matching the current `BEAUTY_NEW_SHA256` constant would xpass; strict=False ensures this does not blow up the suite. Activation-time discipline: refresh both the constant AND the xfail removal in the same commit.

## 12. Follow-up work / next milestone dependencies

- **Phase 9 entry condition:** KI-NEW-G's trigger event must be detected on beta onboarding. Recommend a brief checklist item on the beta-onboarding workflow that flags consumable-repeat-concentrated catalogs for Commit C re-open.
- **Phase 9 ticket:** KI-NEW-H joint recalibration of D-S6-4 + D-S6-5 + D-FLOOR-replenishment_due. Single coupled ticket, not three independent ones.
- **Coupled-or-subsumed work:** KI-NEW-I Watching-row routing for `cohort_n=0`. Land alongside Commit C activation OR within KI-NEW-H's candidate adjustment (c).
- **No immediate next milestone in S6.** Sprint can advance to the next non-replenishment_due ticket; the deferred Commit C does not block any other play's activation path.

---

**Attribution:** DS-architect lock by ecommerce-ds-architect (agent `a3e8cc44e77dcf281`) 2026-05-19. Path D selected after rejecting Paths A (synthetic-fixture authoring), B (premature decision recalibration), and C (deferral without scaffolding-preservation discipline).
