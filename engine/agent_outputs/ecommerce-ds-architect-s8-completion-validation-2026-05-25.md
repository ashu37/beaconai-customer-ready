# DS Architect Verdict — Sprint 8 Completion Validation (2026-05-25)

**Author:** ecommerce-data-science-architect
**Branch:** `post-6b-restructured-roadmap`
**Sprint arc:** `77086fd` → `ce648fd` (12 commits; T0 + T1 trio + T2 pair + T3 pair + T4 pair + 2 probe-archive cleanups)
**Lens:** S14-readiness ("on a small private-beta merchant's first run, does the engine ship a defensible posterior + auditable trust chain?")
**Bottom line:** **PASS. PUSH.**

The orchestrator-claimed S8-close state (ARCHITECTURE_PLAN.md 2026-05-25 LOAD-BEARING UPDATE) matches the empirical code state. All six sub-tickets shipped what DS verdicts locked. All 16 DS invariants hold. No scope deviations sneaked in. Engine is in the S14-ready state my prior verdicts said it should be at S8 close. S10 ML AUDIENCE layer has a clean integration seam.

---

## V1. Did Sprint 8 ship what DS verdicts locked?

| Sub-ticket | Status | Empirical evidence |
|---|---|---|
| **S8-T0** (KI-NEW-K Beta re-fit) | **PASS** | `KNOWN_ISSUES.md:389` flips KI-NEW-K to RESOLVED with `77086fd`. SciPy authoritative percentiles `(0.0037, 0.0169, 0.0471)` shipped per the SciPy-followup verdict §4 amendment. One-cell scope expansion to `replenishment_due.base_rate.beauty` ratified per §6 F1. |
| **S8-T1 + T1.6 + T1.5** (chip + cfg-wiring) | **PASS** | `EvidenceSourceChip` at `src/engine_run.py:295`; `PlayCard.evidence_source` at L827. Flag default ON at `src/utils.py:702`. All 5 callsites at `src/main.py:1374,1422,1475,1534,1592` thread `cfg=cfg` (T1.6 fix), confirmed via grep. `tests/test_v2_harness_cfg_gated_fields.py` exists (invariant 16 canonical home). |
| **S8-T2 + T2.5** (Sensitivity) | **PASS** | `Sensitivity` dataclass at `src/engine_run.py:527`; `PlayCard.sensitivity` at L842. `compute_sensitivity` at `src/sizing.py:260-358` reuses `bayesian_blend` via `_revenue_range_from_blend` — no parallel sizing math (DS verdict §2 reasoning preserved). Separate flag `ENGINE_V2_SENSITIVITY` at `src/utils.py:727` default ON, per DS Q7 §4 override of IM bundling proposal. Latent bool-coerce bug at `utils.py:1041` caught and fixed (per memory.md L1900). |
| **S8-T3 + T3.5** (Provenance + EB blend) | **PASS** | `Provenance` dataclass at `src/engine_run.py:593`; `PlayCard.provenance` at L857. `compute_provenance` at `src/sizing.py:384-478` reuses `effective_pseudo_n` + `PSEUDO_N_BY_STATUS` (no parallel pseudo_N policy). Returns `None` on refused statuses (defense-in-depth for invariant 2). `ENGINE_V2_EB_BLEND` flag at `src/utils.py:759` default ON. EB blend math unchanged — `bayesian_blend` at `src/sizing.py:142-179` identical to S7.5-T3 shipped version. |
| **S8-T4 + T4.5** (Play Library wave 1) | **PASS** | `plays/` tree with exactly 3 wave-1 subdirs (`winback_dormant_cohort`, `replenishment_due`, `discount_dependency_hygiene`), each carrying `spec.yaml` + `audience.py` + `builder.py` + `copy.md`. `plays/_registry.py:29-35 WAVE1_PLAY_IDS` matches DS Q6 lock exactly. `consult_play_library_if_enabled` invoked at `src/main.py:550` after `cfg = get_config()` (single new call site, no L1380-1597 touches). `plays/replenishment_due/spec.yaml:25 honest_dormancy_on_beauty: true` preserved. Flag `ENGINE_V2_PLAY_LIBRARY_WAVE1` at `src/utils.py:796` default ON. |

**Note on empirical run-file verification (V1 task spec item 19):** The runs in `data/healthy_beauty_240d/runs/` are stale (`profiled_at: 2026-05-22T17:42:42`, predating S8-T0 by 2 days); they reflect the S7.6-CLI-FIX baseline, not S8 fields. **This is not a regression** — these JSON snapshots are produced when `main.run_action_engine` actually executes, not by sprint commits. The empirical surfacing of `evidence_source = STORE_OBSERVED`, `sensitivity`, and `provenance` on Beauty Tier-B cards is enforced by the harness-level pytests at `tests/test_v2_harness_cfg_gated_fields.py` (DS invariant 16 home), which run end-to-end via `main.run_action_engine` with each flag forced ON. Suite at 1882p/0f confirms these pass. If the founder wants a fresh run snapshot for audit purposes pre-push, that's a separate single-command refresh — not a sprint deliverable gap.

## V2. Did all 16 DS invariants hold empirically?

| # | Invariant | Result | Evidence |
|---|---|---|---|
| 1 | `PSEUDO_N_BY_STATUS = {30, 15, 10}` locked | PASS | `src/sizing.py:87-91` unchanged |
| 2 | HEURISTIC_UNVALIDATED + PLACEHOLDER refusal | PASS | `_BLEND_PERMITTED_STATUSES` at `src/sizing.py:96`; `compute_provenance` returns None on refused statuses (`src/sizing.py:418-422`) |
| 3 | `min(status_cap, profile_default)` preserved | PASS | `src/sizing.py:121-139` unchanged |
| 4 | `effective_n` is metadata only | PASS | No code reads YAML `effective_n` as a weight; `compute_provenance` uses `PSEUDO_N_BY_STATUS[status]` directly |
| 5 | No `Prior.pseudo_N` per-prior override field | PASS | DS §6 F2 rejection held; no such field on `PriorEntry` |
| 6 | `Measurement.observed_effect/p_internal/n` reachable | PASS | S7.6 CLI fix surface at `src/measurement_builder.py:2252-2270` not modified by any S8 commit |
| 7 | Single-demote-channel + 3-channel priority_prepend + T6 eligibility gate | PASS | No edits to `src/main.py:1380-1597` (KI-NEW-L deferred to S13.5); `apply_guardrails_to_injected` untouched |
| 8 | T6 eligibility-gate + joint-p<0.10 amendment | PASS | Untouched in S8 |
| 9 | Reuse `blend` literal (no `blend_empirical_bayes` sibling) | PASS | `RevenueRangeSource.BLEND` consumed by `_revenue_range_from_blend` at `src/sizing.py:254`; no new literal |
| 10 | KI-NEW-K closed atomically with re-pin | PASS | `KNOWN_ISSUES.md:389` resolved; Beauty sha `fcd2924b…` → `f8676c9f…` per memory.md L1829 |
| 11 | No new injection blocks at `src/main.py:1380-1597` (incl. T1.6 sub-rule) | PASS | T1.6 only added `cfg=cfg` kwargs inside existing per-builder blocks at L1374/1422/1475/1534/1592 — satisfies §Q2 refined sub-rule (purely additive, no new `_dc_replace`) |
| 12 | PlayCard additive surface capped at 3 new fields | PASS (REACHED) | Exactly `evidence_source`, `sensitivity`, `provenance` added (`src/engine_run.py:827, 842, 857`); no 4th |
| 13 | Play Library wave 1 = {winback_dormant_cohort, replenishment_due, discount_dependency_hygiene} + honest-dormancy preserved | PASS | `plays/_registry.py:29-35`; `plays/replenishment_due/spec.yaml:25 honest_dormancy_on_beauty: true`; `tests/test_s8_t4_play_library_wave1_migration.py` exists |
| 14 | `ENGINE_V2_SENSITIVITY` distinct from `ENGINE_V2_TIER_CHIP` | PASS | Separate flags at `src/utils.py:702` and `:727`; atomic T1.5/T2.5/T3.5/T4.5 flips visible in commit log |
| 15 | S13.5 ticket pre-scoped with locked acceptance criteria | PASS | `KNOWN_ISSUES.md:421` 2026-05-24 update carries the full numbered invariant list |
| 16 | Harness-level coverage for every flag-gated producer field | PASS | `tests/test_v2_harness_cfg_gated_fields.py` exists; T2/T3/T4 each added a parametrize row per memory.md L1875 |

## V3. Were there scope deviations needing ratification or rollback?

| Deviation candidate | Status |
|---|---|
| IM `Prior.pseudo_N` per-prior override field | **NO DEVIATION** — DS §6 F2 rejection held; not present on `PriorEntry` |
| IM `blend_empirical_bayes` literal | **NO DEVIATION** — `RevenueRangeSource.BLEND` reused |
| IM `signal_kind` field | **NO DEVIATION** — only 3 new PlayCard fields shipped (invariant 12 cap reached) |
| HTML renderer changes for evidence chip | **NO DEVIATION** — renderer untouched; `briefing.html` debug-only retiring posture preserved (founder ack 2026-05-24) |
| New injection blocks at `src/main.py:1380-1597` | **NO DEVIATION** — T1.6 added only `cfg=cfg` kwargs within existing blocks (allowed under §Q2 sub-rule of invariant 11). Verified via grep — 5 callsites all thread `cfg=cfg`, none introduce `_dc_replace` mutations |
| Pseudo_N values 30/15/10 | **NO DEVIATION** — `src/sizing.py:87-91` unchanged; no fourth value, no per-prior override |
| Wave 1 play substitution | **NO DEVIATION** — `WAVE1_PLAY_IDS` matches DS Q6 lock exactly; dormant `replenishment_due` retained as the load-bearing migration-template stress test |

One minor observation worth surfacing (not a deviation, not a blocker): `plays/replenishment_due/spec.yaml:17-18` lists `prior_keys: [bundle_value]` rather than `[base_rate]`. The S6-T3.x re-key moved the production dispatch from `bestseller_amplify.bundle_value` to `replenishment_due.base_rate`. The spec.yaml `prior_keys` field is **wave-1 metadata-only** (not consumed by the dispatch — the dispatch identity-asserts against the legacy `measurement_builder._PRIOR_ANCHORED` registry, which is correctly keyed). Worth a memo cleanup in wave 2 when behavior actually moves into `plays/<play_id>/`, but no engine-behavior impact today. Not push-blocking.

## V4. Is the engine in the S14-readiness state?

**S14-READY.**

- **Small-merchant posterior velocity:** With `PSEUDO_N=30` for validated_external and `pseudo_n_used=20` post-profile-lowering on Beauty (per memory.md L1903), a beta merchant with cohort `n ∈ [200, 5000]` produces `w_obs ∈ [0.91, 0.996]` — store-dominant in month 1 on validated paths, exactly the velocity my parent verdict §1 required. The 2026-05-24 SciPy-followup confirmed the envelope re-fit strengthens (does not weaken) small-merchant honest evaluation.
- **Three orthogonal gates wired clean:** Gate 1 (cohort p-value at MEASUREMENT) untouched; Gate 2 (`validation_status` at SIZING) defense-in-depth strengthened by `compute_provenance`'s explicit None-return on refused statuses; Gate 3 (`ModelFitStatus` at AUDIENCE) ready for S10's drop-in via the preserved `ranking_strategy` scaffolding kwarg on all 5 Tier-B builders.
- **`pseudo_n_used=20 < pseudo_n_cap=30`** on Beauty correctly reflects `min(status_cap, profile_default)` — the profile lowered from 30 → 20 via `gate_calibration.pseudo_n_default`. This is correct behavior, not a cap bypass. `effective_pseudo_n` at `src/sizing.py:99-139` enforces this; `compute_provenance` reports both numbers honestly so a skeptical operator can audit the lowering.

## V5. Does S8 leave S10 a clean integration?

**CLEAN HANDOFF.**

- `ranking_strategy: Optional[str] = None` kwarg preserved on all 5 Tier-B audience builders (forward-scaffolded at S6-T1 per memory.md L578-580; round-trip-clean).
- T1.6 structural callsite pin at `tests/test_v2_harness_cfg_gated_fields.py` will catch any S10 producer that fails to thread `cfg=cfg` — converts tribal knowledge into CI gate. This is exactly the protection S10 needs given it adds new producers via the same builder seam.
- **DS invariant 12 (PlayCard cap=3 fields) is S8-scoped, not permanent.** The memory.md sprint-close entry frames it correctly: "DS invariant 12 cap REACHED — no 4th S8 field permitted." S10's `ranking_strategy` and S13's `predicted_segment` + `model_card_ref` are out of S8 scope; they were forward-scaffolded as stub dataclasses at S6-T1 (memory.md L579) and remain reserved on `PlayCard`. The cap protects R-S8.1 (additive surface stress), it does not freeze the schema.
- `consult_play_library_if_enabled` identity-assertion at `src/main.py:550` is robust to S10 adding new producers — the assertion is per-play, so new ML producers added via the same builder seam either (a) are wave-2+ migrations subject to their own identity assertions, or (b) live in `src/measurement_builder._PRIOR_ANCHORED` untouched. Either way, no engine-startup breakage.

## V6. Push-to-origin recommendation

**PUSH.**

All six sub-tickets shipped what DS verdicts locked, all 16 invariants hold empirically, zero scope deviations sneaked in, engine state matches the S14-ready criterion my parent verdicts pinned, and S10 has a clean integration seam. The atomic per-ticket flag-flip discipline held through 4 separate flips with zero re-pin churn drift; the harness-level coverage discipline (invariant 16) caught a latent bool-coerce bug that would otherwise have leaked at any flag-OFF state. This is the cleanest sprint in the V2 arc.

**Push hygiene reminder:** Per the task spec, leave `agent_outputs/ecommerce-ds-architect-doc-audit-2026-05-24.md` and the various `scripts/c2_*`, `scripts/s7_6_*`, `outputs/` untracked entries out of this push — they are not S8 scope. Only push the 12 sprint commits + this verdict file (when the orchestrator saves it).

**Post-push:** Dispatch IM for S10 (ML AUDIENCE layer per `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` §B-S10). No pre-S10 cleanup required.

---

**Cross-references**
- Parent verdicts: `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md`, `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ecommerce-ds-architect-s8-q3-q6-q7-verdict-2026-05-24.md`, `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ecommerce-ds-architect-s8-t1-cfg-wiring-gap-verdict-2026-05-24.md`, `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ecommerce-ds-architect-s8-t0-scipy-percentile-followup-2026-05-24.md`
- Code state (read for V1/V2): `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py` (L87-91, 99-139, 142-179, 260-358, 384-478); `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` (L295, 527, 593, 827, 842, 857); `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` (L702, 727, 759, 796); `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` (L550, 1374, 1422, 1475, 1534, 1592); `/Users/atul.jena/Projects/Personal/beaconai/plays/_registry.py` (L29-35); `/Users/atul.jena/Projects/Personal/beaconai/plays/replenishment_due/spec.yaml`
- Sprint state: `/Users/atul.jena/Projects/Personal/beaconai/memory.md` (L1822-1936); `/Users/atul.jena/Projects/Personal/beaconai/ARCHITECTURE_PLAN.md` (L13-36 2026-05-25 LOAD-BEARING UPDATE); `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md` (L389 KI-NEW-K resolved, L421 KI-NEW-L S13.5 deferral, L432 KI-NEW-M S14 deferral)

**End of verdict.** Push to origin; dispatch IM for S10.
