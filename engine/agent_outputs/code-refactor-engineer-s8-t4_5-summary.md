# S8-T4.5 — flip ENGINE_V2_PLAY_LIBRARY_WAVE1 ON (wave-1 Play Library consult active by default, zero re-pin)

**Author:** code-refactor-engineer
**Date:** 2026-05-25
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `ce648fd`
**Approved ticket:** S8-T4.5 — Per IM S8 plan Part B S8-T4 atomic-flip half + DS verdict 2026-05-24 §3 Q6 + §5 invariant 13. **Final S8 atomic flip.** Zero re-pin target per IM Part I + DS verdict (identity-assertion design guarantees byte-identity by construction).

## 1. Approved scope

S8-T4.5: atomic flip of `ENGINE_V2_PLAY_LIBRARY_WAVE1` default false → true. Single-line default change. Zero re-pin target per DS verdict §5 invariant 13.

## 2. Patch summary

One-line default flip at `src/utils.py:796`: `"false"` → `"true"`. Env-override path preserved. No other code changes.

## 3. Files changed

- `src/utils.py` (line 796: default value string).

## 4. Tests/checks run

- Pre-flip baseline (T4 19 tests + harness gated tests): 28 passed.
- Post-flip tripwire (T4 + harness + pinned-fixture re-pins for Beauty/Supplements + S8-T1/T2/T3 trust-surface): 125 passed, 1 xpassed.
- Full suite post-flip: **1882 passed**, 14 skipped, 4 xfailed, 2 xpassed (matches pre-flip baseline exactly).

## 5. Behavior changes

- `ENGINE_V2_PLAY_LIBRARY_WAVE1` now defaults ON. `consult_play_library_if_enabled` runs at engine startup, asserting spec.yaml-resolved callables are identity-equal to legacy registry callables. Pure integrity check — no behavior diff vs flag-OFF.
- All 5 pinned fixtures byte-identical (Beauty `f8676c9f...`, Supplements `13a91e6c...`, 3 M0 fixtures) — confirmed via pin tests passing unchanged.
- KI-NEW-G honest-dormancy preserved (`replenishment_due` produces zero audience on Beauty at default-ON, asserted by `test_s8_t4_play_library_wave1_migration.py`).
- All 3 S8 trust-surface fields remain live (evidence_source / sensitivity / provenance).
- Harness parametrize row `test_play_library_wave1_byte_identical_recommendations` passes at both flag states via explicit env override (unaffected by default change).

## 6. Artifacts added

None.

- `agent_outputs/code-refactor-engineer-s8-t4_5-summary.md` (this file; backfilled 2026-05-25).

## 7. Remaining risks

- **None new.** The consult helper raises `RuntimeError` only if spec.yaml-resolved callables drift from legacy registry callables — flag-ON now enforces this invariant on every engine startup (intentional, refuses to start on drift).
- **Closes S8 implementation.** Sprint-close doc sweep (memory.md / ARCHITECTURE_PLAN.md / KNOWN_ISSUES.md update covering T2 + T2.5 + T3 + T3.5 + T4 + T4.5) is orchestrator's responsibility, not this ticket.

## 8. Follow-up work

- Orchestrator runs S8-close doc sweep across the six S8 tickets (handled at commit `c7e7963`).
- Future Play Library waves (wave 2+) — out of scope; new ticket required.

## 9. Verbatim founder ask answers

- **Exact line edited:** `src/utils.py:796` (`"false"` → `"true"`).
- **All 5 pinned slate sha256s post-flip:** Beauty `f8676c9f...`, Supplements `13a91e6c...`, M0 small_sm `40bf24ea...`, mid_shopify `380b2c5d...`, micro_coldstart `2191b251...` — all match pre-flip.
- **KI-NEW-G dormancy confirmation:** `replenishment_due` zero audience on Beauty post-flip confirmed.
- **T4 19 tests + harness row status:** all pass at default-ON.
- **S8-T1 + S8-T2 + S8-T3 + S7.6 invariant tests:** all pass unmodified.
- **Suite count:** 1882 → 1882 (no change).
- **Commit sha:** `ce648fd`.

## Backfill from memory.md (migration trim 2026-05-25)

## S8-T2 + T2.5 + T3 + T3.5 + T4 + T4.5 — Sprint 8 CLOSE (2026-05-25)

**Shipped:** Six commits close Sprint 8 (`fcc87af` → `ce648fd`). All 3 S8 additive `PlayCard` trust-surface fields live in production + Play Library wave 1 directory structure with byte-identity enforcement.

- `fcc87af` (T2): `Sensitivity` typed dataclass (6 keys: 4 scenario revenue ranges + `pseudo_n_used` + `notes`) + `PlayCard.sensitivity` field + `ENGINE_V2_SENSITIVITY` separate flag default OFF + 25 new tests + harness parametrize row per DS invariant 16. `compute_sensitivity()` helper at `src/sizing.py` reuses `bayesian_blend` — no parallel sizing math. **Caught latent bool-coerce bug at `src/utils.py:1041`** (string `"false"` was leaking truthy in subprocess harness) — fixed in same commit.
- `47eebb2` (T2.5): `ENGINE_V2_SENSITIVITY` default `false` → `true`. Empirical tripwire: 3 Beauty Tier-B Recommended cards carry `sensitivity` block. Pinned slates byte-identical (renderer doesn't surface sensitivity per founder ack).
- `9817216` (T3): `Provenance` typed dataclass (validation_status + pseudo_n_used/cap + observed_n + weights + prior_source + notes) + `PlayCard.provenance` field + `ENGINE_V2_EB_BLEND` separate flag default OFF + `compute_provenance()` helper at `src/sizing.py:361-470` reusing `effective_pseudo_n` + 34 new tests + harness parametrize row. **EB blend math UNCHANGED** — contract formalization only; production `bayesian_blend` shipped at S7.5-T3. Pinned-fixture byte-identity at flag OFF verified math is unchanged.
- `c3eb5e4` (T3.5): `ENGINE_V2_EB_BLEND` default `false` → `true`. Empirical tripwire: 3 Beauty Tier-B Recommended cards carry `provenance` block with `validation_status=validated_external, pseudo_n_used=20, pseudo_n_cap=30` (per-stage profile lowering active per S7.5-T3 `min(status_cap, profile_default)` discipline). **`revenue_range.p10/p50/p90` bit-identical pre-vs-post flip** on all 3 cards (DS invariant: blend math unchanged).
- `a9e8bbf` (T4): Play Library wave 1 — `plays/` directory tree with 3 wave-1 play subdirs each carrying `spec.yaml` + `audience.py` (re-export) + `builder.py` (re-export) + `copy.md`. `consult_play_library_if_enabled` at `src/play_registry.py` performs pure identity assertion (asserts spec.yaml-resolved callables ARE the legacy registry callables, not just equivalent). `ENGINE_V2_PLAY_LIBRARY_WAVE1` flag default OFF + 19 new tests + harness parametrize row. Single new call site in `src/main.py::run` after `cfg = get_config()` — NO touches to injection blocks at L1380-1597 (KI-NEW-L deferred S13.5).
- `ce648fd` (T4.5): `ENGINE_V2_PLAY_LIBRARY_WAVE1` default `false` → `true`. **Zero re-pin** (identity-assertion design guarantees byte-identity). All 5 pinned fixtures byte-identical. KI-NEW-G honest-dormancy preserved on `replenishment_due` (zero audience on Beauty at default-ON).

**Load-bearing invariants (sprint-wide):**
- **All 16 DS invariants preserved** across all 6 commits. Especially: invariant 1 (`PSEUDO_N_BY_STATUS` locked 30/15/10); invariant 2 (HEURISTIC_UNVALIDATED + PLACEHOLDER refusal); invariant 5 (no `Prior.pseudo_N` per-prior override field — DS §6 F2 rejected the IM proposal); invariant 9 (reuse `blend` literal — DS Q5 closed); invariant 11 (no injection-block touches at `src/main.py:1380-1597`); invariant 12 (PlayCard additive surface capped at 3 fields, NOW REACHED — no 4th field permitted in S8); invariant 13 (Play Library wave-1 acceptance + honest-dormancy preserved); invariant 14 (independent flag matrix); invariant 16 (harness-level coverage for every flag-gated producer field — pattern proven via T1.6 + T2 + T3 + T4).
- **All three S7.6 architectural invariants preserved** + S7.6 CLI fix surfacing at `src/measurement_builder.py:2252-2270` reachable through all 6 commits.
- **Identity-assertion design pattern** at T4's `consult_play_library_if_enabled` — template for future wave-2+ migrations; engine refuses to start on spec.yaml ↔ legacy callable drift.
- **Engine state end of S8:** every Tier-B Recommended card on Beauty ships with `Measurement.observed_effect/p_internal/n` (S7.6) + `evidence_source = "STORE_OBSERVED"` (S8-T1.5) + `sensitivity = {6-key dict}` (S8-T2.5) + `provenance = {audit object}` (S8-T3.5) + `revenue_range.source = "blend"` (S7.5/S7.6) + `drivers[].blend_provenance` (S7.6). Full trust-surface contract auditable from headline to feature.

**Caveats / dormant behavior:** Supplements has no Tier-B Recommended cards firing (aov_bundle vertically excluded + replenishment_due dormant + winback/journey/discount_hygiene land in Considered on supplements). Supplements `engine_run.json` shows all 3 S8 trust-surface fields = None on every card; flag flips have no observable effect on supplements. M0 same story (cold-start). Honest behavior, not bugs.

**Caveats / IM-plan divergences (DS-locked):**
- IM `Prior.pseudo_N: Optional[int]` per-prior override field — REJECTED per DS verdict §6 F2.
- IM new `RevenueRange.source = "blend_empirical_bayes"` sibling literal — REJECTED per DS Q5 (reuse `blend`).
- IM proposed `pseudo_N` values `expert=1, observational=5, causal=20` — SUPERSEDED by S7.5-T3 production 30/15/10.
- IM proposed bundling `ENGINE_V2_SENSITIVITY` under `ENGINE_V2_TIER_CHIP` flag — OVERRIDDEN per DS Q7 §4 (separate-flag atomic per-ticket discipline).

**Out of scope (deferred per prior DS verdicts):** KI-NEW-L → S13.5 (between S13-T4 atomic flip and S14-T1 dispatch); KI-NEW-M/N → S14-T3 beta-merchant feedback resolution window; KI-NEW-J → S14 pre-private-beta calibration with locked resume trigger; KI-NEW-O → separate test-hygiene pass; Sprint 9 store-profile-as-learned-artifact + Sprint 10-13 ML AUDIENCE layer pending.

**Schema:** 3 additive `PlayCard` fields within `event_version=1` (`evidence_source: Optional[EvidenceSourceChip]`, `sensitivity: Optional[Sensitivity]`, `provenance: Optional[Provenance]`); DS invariant 12 cap REACHED — no 4th S8 field permitted.

**Suite:** 1798 → 1882 (+84 across T2/T2.5/T3/T3.5/T4/T4.5). Sprint-total: 1770 → 1882 (+112). All 5 pinned fixtures byte-identical from sprint-start (`9e2f357`) to sprint-close (`ce648fd`): Beauty `f8676c9f…`, Supplements `13a91e6c…`, M0 (3 fixtures). M0 byte-identical throughout.

**Beta-readiness statement:** the engine ships a complete, typed, auditable trust-surface contract on every Tier-B Recommended card. Real-merchant private-beta onboarding (S14) can begin once S10–S13 ML AUDIENCE layer lands. No further engine work required to make the S8 trust-surface contract beta-ready.

**Summary references:** IM S8 plan at `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md`; DS pseudo_N verdict `agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md`; DS Q3/Q6/Q7 verdict `agent_outputs/ecommerce-ds-architect-s8-q3-q6-q7-verdict-2026-05-24.md`; DS cfg-wiring verdict `agent_outputs/ecommerce-ds-architect-s8-t1-cfg-wiring-gap-verdict-2026-05-24.md`; DS SciPy-followup `agent_outputs/ecommerce-ds-architect-s8-t0-scipy-percentile-followup-2026-05-24.md`. Commits `77086fd` (T0) + `1372feb`/`7df2399`/`98dad72` (T1 trio) + `fcc87af`/`47eebb2` (T2) + `9817216`/`c3eb5e4` (T3) + `a9e8bbf`/`ce648fd` (T4).
