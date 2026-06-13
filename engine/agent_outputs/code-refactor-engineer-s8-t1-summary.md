# S8-T1 — EvidenceSourceChip enum + PlayCard.evidence_source field (flag OFF)

**Author:** code-refactor-engineer
**Date:** 2026-05-24
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `1372feb`
**Approved ticket:** S8-T1 — Per IM S8 plan Part B S8-T1 + DS verdict 2026-05-24 §5 invariant 12 capping S8 additive surface at 3 PlayCard fields (first of 3). Typed `EvidenceSourceChip` enum + `PlayCard.evidence_source: Optional[EvidenceSourceChip] = None` additive field within `event_version=1`, behind `ENGINE_V2_TIER_CHIP` flag default OFF. T1.5 atomic flip is a separate later dispatch.

## 1. Approved scope

- New typed enum `EvidenceSourceChip` at `src/engine_run.py` with 4 values matching `ENGINE_OVERVIEW.md §8` evidence-tier table verbatim: `STORE_MEASURED`, `STORE_OBSERVED`, `INDUSTRY_PRIOR`, `OBSERVATIONAL`.
- New `PlayCard.evidence_source: Optional[EvidenceSourceChip] = None` field, additive within `event_version=1`.
- Producer-side population at the prior-anchored builder seam: `evidence_source = STORE_OBSERVED` when `ENGINE_V2_TIER_CHIP` is ON; `None` when OFF.
- New `ENGINE_V2_TIER_CHIP` flag at `src/utils.py` default OFF (T1.5 will flip atomically).
- 25 new tests in `tests/test_s8_t1_evidence_source_chip.py` covering enum exhaustiveness, round-trip, absent-key tolerance, invalid-string rejection, flag-ON population (parametrized across 4 wired Tier-B plays), flag-OFF omission (parametrized across 4 plays × 4 cfg shapes), and the 5 pinned HTML fixture byte-identity tripwire.

## 2. Patch summary

UPPER_SNAKE casing for both member name and string value (`STORE_MEASURED = "STORE_MEASURED"` etc.), matching the `WouldBeMeasuredBy` precedent for enums externally referenced in spec docs (`ENGINE_OVERVIEW.md §8` + `ARCHITECTURE_PLAN.md Part I §A` use these as quotable identifiers). The dispatch brief suggested Tier-label-style `CAUSAL/DIRECTIONAL/PRIOR/OBSERVATIONAL`; per CLAUDE.md "Never assume" + read-the-spec-doc discipline, refactor-engineer shipped source-of-truth names. Founder-confirmed 2026-05-24: no rename.

Producer seam unified at `build_prior_anchored_play_card` (single populate point), mirroring the S7.6 CLI fix surfacing pattern at `src/measurement_builder.py:2252-2270`. Producer-direct tests at `tests/test_s8_t1_evidence_source_chip.py:168` construct `cfg` manually and bypass main.py — this is the coverage gap that S8-T1.5 dispatch's tripwire discovered and S8-T1.6 closed.

## 3. Files changed

- `src/engine_run.py` — `EvidenceSourceChip` enum at lines 295-352; `PlayCard.evidence_source` field at lines 595-605; round-trip via `_from_dict_play_card` at lines 968-972.
- `src/utils.py` — `ENGINE_V2_TIER_CHIP` flag default `"false"` at lines 684-703; allowed-set extension at line 1015.
- `src/measurement_builder.py` — `EvidenceSourceChip` import at line 69; chip population logic at lines 2435-2447 (`if cfg is not None and cfg.get("ENGINE_V2_TIER_CHIP", False): evidence_source = EvidenceSourceChip.STORE_OBSERVED`); PlayCard return updated at line 2466 (`evidence_source=evidence_source`).
- `tests/test_s8_t1_evidence_source_chip.py` — new test file (25 tests).

## 4. Tests/checks run

- `pytest tests/test_s8_t1_evidence_source_chip.py` — 25 passed.
- `pytest tests/test_s7_6_c1_priority_prepend_invariant.py` — 8 passed, 2 xfailed (unmodified).
- `pytest -q` (full suite) — **1770 → 1795 passed**, 14 skipped, 4 xfailed, 2 xpassed, 0 failed (+25 = exactly the new tests).

## 5. Behavior changes

- None at flag-OFF default. `PlayCard.evidence_source` is always `None`. All five pinned HTML fixtures byte-identical (Beauty `f8676c9f...`, Supplements `13a91e6c...`, three M0 goldens unchanged).
- Under flag-ON (not flipped in this commit), every prior-anchored Tier-B card SHOULD emit `evidence_source = EvidenceSourceChip.STORE_OBSERVED` — **but the S8-T1.5 tripwire discovered this is dead code due to a cfg-wiring gap (4 of 5 callsites in src/main.py don't thread cfg=cfg). Bug fixed at S8-T1.6 (commit `7df2399`).**

## 6. Artifacts added

- `tests/test_s8_t1_evidence_source_chip.py` (new, 25 tests).
- `agent_outputs/code-refactor-engineer-s8-t1-summary.md` (this file; backfilled 2026-05-25).

## 7. Remaining risks

- **Enum naming deviation from brief.** The brief listed `CAUSAL/DIRECTIONAL/PRIOR/OBSERVATIONAL` but the source-of-truth docs (ENGINE_OVERVIEW.md §8, ARCHITECTURE_PLAN.md Part I §A) specify `STORE_MEASURED/STORE_OBSERVED/INDUSTRY_PRIOR/OBSERVATIONAL`. Refactor shipped source-of-truth names; founder-confirmed 2026-05-24 to keep as shipped (no rename).
- **Coverage gap on the main.py orchestration seam.** S8-T1 acceptance test bypasses main.run_action_engine; the flag-ON tests construct cfg manually. This gap allowed the cfg-wiring bug to ship undetected. Closed by S8-T1.6 (harness-level test + structural callsite pin).
- **NO `signal_kind` field shipped** despite IM plan Part H mentioning it; DS verdict §5 invariant 12 caps S8 at 3 fields (this commit lands one). If `signal_kind` is later judged necessary, that becomes a separate ticket with its own additive-surface justification.

## 8. Follow-up work

- **S8-T1.6:** cfg-wiring fix (add `cfg=cfg` to 4 callsites in src/main.py) + harness coverage test + structural callsite pin per DS verdict 2026-05-24 (cfg-wiring-gap) Option B sequencing. **Surfaced by S8-T1.5 tripwire.**
- **S8-T1.5 (after T1.6):** flip `ENGINE_V2_TIER_CHIP` default to `true` per S7.6 atomic-flip discipline.

## 9. Verbatim founder ask answers

- **Insertion-point line numbers in `src/engine_run.py`:** enum at 295-352; PlayCard.evidence_source field at 595-605; round-trip at 968-972.
- **Insertion-point line numbers in `src/measurement_builder.py`:** 2418 (block start), 2425 (comment), 2428 (default `evidence_source = None`), 2430 (populate when cfg flag ON).
- **Flag location:** `src/utils.py:684-703` (default `"false"`); bool-coerce set updated at line 1015.
- **Enum casing decision:** UPPER_SNAKE matching spec-doc identifiers verbatim (founder-confirmed no rename 2026-05-24).
- **New test file name + count:** `tests/test_s8_t1_evidence_source_chip.py` — 25 tests.
- **Suite count:** 1770 → 1795 passed (+25 new tests).
- **M0 byte-identical:** confirmed (small_sm, mid_shopify, micro_coldstart unchanged).
- **Beauty + Supplements pinned slate sha256:** `f8676c9f...` + `13a91e6c...` unchanged.
- **S7.6 tripwire test status:** both `test_tier_b_recommended_cards_surface_observed_effect_on_beauty` + `test_tier_b_demoted_via_any_channel_survives_truncation` pass unmodified.
- **Commit sha:** `1372feb`.

## Backfill from memory.md (migration trim 2026-05-25)

## S8-T1 + T1.6 + T1.5 trio — EvidenceSourceChip live in production (2026-05-24)

**Shipped:** Three atomic commits land the first S8 trust-surface field end-to-end:

- `1372feb` (T1, impl): typed `EvidenceSourceChip` enum (4 values: `STORE_MEASURED`, `STORE_OBSERVED`, `INDUSTRY_PRIOR`, `OBSERVATIONAL`) at `src/engine_run.py:295-352`; `PlayCard.evidence_source: Optional[EvidenceSourceChip] = None` additive within `event_version=1`; `ENGINE_V2_TIER_CHIP` flag at `src/utils.py:702`; producer gate at `src/measurement_builder.py:2428-2430` populates `STORE_OBSERVED` on prior-anchored Tier-B cards when flag is ON; 25 new tests at `tests/test_s8_t1_evidence_source_chip.py`. Enum casing keeps source-of-truth names from `ENGINE_OVERVIEW.md §8` + `ARCHITECTURE_PLAN.md Part I §A` (founder-confirmed 2026-05-24 — no rename to Tier-label form).
- `7df2399` (T1.6, cfg-wiring fix): added `cfg=cfg` at 4 callsites of `build_prior_anchored_recommendations` in `src/main.py` (~L1332, L1378, L1426, L1478); the 5th (AOV bundle L1557) already had it from S7.6-T5. T1's flag was dead code in production until this commit. Empirically discovered via T1.5 tripwire; DS-consulted (`agent_outputs/ecommerce-ds-architect-s8-t1-cfg-wiring-gap-verdict-2026-05-24.md`); Option B sequencing (T1.6 → T1.5). +3 tests at `tests/test_v2_harness_cfg_gated_fields.py` (harness end-to-end + structural callsite pin).
- `98dad72` (T1.5, atomic flag flip): `ENGINE_V2_TIER_CHIP` default `false` → `true` at `src/utils.py:702`. Empirical tripwire post-flip (no env override): 3 Beauty Tier-B Recommended cards carry `STORE_OBSERVED` in `engine_run.json` — winback n=448, discount_hygiene n=224K, journey n=603.

**Load-bearing invariants:**
- **DS invariant 16 (new, 2026-05-24, DS-locked):** every flag-gated producer field MUST be exercised by a harness-level test calling `main.run_action_engine` end-to-end with the flag forced ON. Canonical test home: `tests/test_v2_harness_cfg_gated_fields.py`. T2/T3/S13 each append a parametrize row when they land.
- **Structural callsite pin** at `tests/test_v2_harness_cfg_gated_fields.py`: regex-walks `src/main.py` and asserts every call to `build_prior_anchored_recommendations` threads `cfg=cfg`. Pattern-protects T2 (Sensitivity), T3 (provenance), S13 (ML AUDIENCE) from re-discovering the cfg-wiring bug class. Converts "remember to thread cfg" from tribal knowledge into a CI gate.
- **DS invariant 11 refined sub-rule (per cfg-wiring verdict §Q2):** kwarg-adding on existing callsites of pre-existing builder seams is permitted without deviation sign-off provided (a) the kwarg is purely additive at the producer side (default `None`/`False` preserves prior behavior) AND (b) the change does not introduce a new `engine_run = _dc_replace(engine_run, recommendations=...)` mutation.
- **Enum casing locked:** `STORE_MEASURED / STORE_OBSERVED / INDUSTRY_PRIOR / OBSERVATIONAL`. Do NOT rename to Tier-label form (`CAUSAL / DIRECTIONAL / PRIOR / OBSERVATIONAL`); these are spec-doc identifiers from `ENGINE_OVERVIEW.md §8` and `ARCHITECTURE_PLAN.md Part I §A` cited verbatim.
- **All three S7.6 architectural invariants preserved** (single-demote-channel + 3-channel priority_prepend + T6 eligibility gate); S7.6 CLI fix surfacing at `src/measurement_builder.py:2252-2270` preserved; all 15 prior DS invariants preserved.
- **M0 + Beauty + Supplements pinned slate sha256 byte-identical across all 3 commits** — Beauty `f8676c9f…`, Supplements `13a91e6c…`, M0 (3 fixtures). HTML pin is byte-identical because the renderer doesn't surface `evidence_source` (founder ack 2026-05-24: `briefing.html` debug-only retiring; inspection via `engine_run.json` directly).

**Caveats / dormant behavior:** Supplements has no Tier-B Recommended cards firing today (aov_bundle vertically excluded per S7.6 close + replenishment_due dormant per KI-NEW-G honest-dormancy 2026-05-23 + winback/journey/discount_hygiene all land in Considered on supplements per S7.6). So supplements `engine_run.json` shows `evidence_source=None` on every card; flag flip has no observable effect on supplements. M0 same story (cold-start). This is honest behavior, not a bug.

**Founder-discipline memory saved 2026-05-24:** "future questions where agent pauses → invoke DS architect with full engine context + S14 end-goal lens → pass verdict back to paused agent" (`feedback_ds_consult_on_agent_pause.md` in user memory). DS-consulted on the cfg-wiring gap rather than re-prompting founder; refactor agent dispatched with DS-locked acceptance criteria.

**Schema:** additive — `PlayCard.evidence_source: Optional[EvidenceSourceChip] = None` within `event_version=1`. Round-trip clean. **Suite:** 1770 → 1798 (+28 across T1+T1.6; T1.5 no change). **Pinned slates:** all 5 byte-identical across the 3 commits.

**Summary references:** IM S8 plan at `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md` Part B S8-T1; DS cfg-wiring verdict at `agent_outputs/ecommerce-ds-architect-s8-t1-cfg-wiring-gap-verdict-2026-05-24.md` (Option B + invariant 16 + sprint-table Option (a) tracking shape); commits `1372feb` + `7df2399` + `98dad72`.

## S8 Q3/Q6/Q7 — DS verdict + founder ack: sprint shape locked (2026-05-24)

**Shipped:** DS architect verdict at `agent_outputs/ecommerce-ds-architect-s8-q3-q6-q7-verdict-2026-05-24.md` closes the three remaining S8 open questions from the IM plan Part E (Q4/Q5 + Q1/Q2 already closed by the prior pseudo_N verdict). All locks made through the S14-readiness lens.

- **Q3 (KI-NEW-L/M/N bundling): ALL THREE DEFER from S8.** Sprint stays at 4 tickets (T0 landed + T1 + T2 + T3 + T4). KI-NEW-L → **S13.5** (between S13-T4 atomic flip and S14-T1 dispatch); reasoning: S13 extends all 5 Tier-B builders with `ranking_strategy`, giving the eventual 5-block collapse a fresh per-builder safety net (avoids two refactor passes). KI-NEW-M + KI-NEW-N → **S14-driven**: resume trigger is S14-T3 beta-merchant feedback; adding a 4th additive PlayCard field in S8 would stress R-S8.1.
- **Q6 (Play Library wave 1): CONCUR with IM default.** `{winback_dormant_cohort, replenishment_due, discount_dependency_hygiene}`. Including dormant `replenishment_due` (per KI-NEW-G honest-dormancy 2026-05-23) is the only wave-1 test case that verifies the migration template handles dormant plays correctly — load-bearing structural-correctness test.
- **Q7 (Sensitivity flag bundling): OVERRIDE IM default. SEPARATE flag `ENGINE_V2_SENSITIVITY`** with independent T2.5 atomic flip. DS-load-bearing reasoning: the S7.6-T7.5 spiral happened because bundled flag flips hid blast-radius; atomic per-ticket discipline is non-negotiable, not stylistic. IM "fewer commits" framing misreads founder's "stop deferring things" — that targets deferred scope, not commit count.

**Load-bearing invariants:**
- **S8 ticket scope LOCKED at 4** (T0 landed + T1 + T2 + T3 + T4). No T5/T6/T7. Schema-additive surface capped at exactly 3 new `PlayCard` fields (`evidence_source` + `sensitivity` + `provenance`); no 4th field.
- **KI-NEW-L deferral conditional invariant** (DS verdict §5 invariant 15): **"no new Tier-B builders through S13"** — if that breaks, KI-NEW-L escalates and must land before the new builder. Today: 5 wired Tier-B builders, no S8–S13 additions planned per IM revised plan.
- **S13.5 ticket pre-pinned** with invariant-preservation acceptance criteria (DS verdict §2 KI-NEW-L numbered list): (1) single-demote-channel via `apply_guardrails_to_injected`; (2) 3-channel `priority_prepend`; (3) `Measurement.observed_effect/p_internal/n` surfacing at `src/measurement_builder.py:2252-2270`; (4) per-builder behavior byte-identical pre/post-collapse on Beauty + Supplements pinned slates.
- **Play Library wave 1 acceptance** (DS verdict §5 invariant 13): `tests/test_s8_t4_play_library_wave1_migration.py` asserts exactly the three named `play_id`s have a `plays/<play_id>/spec.yaml` artifact post-T4.5; `replenishment_due` produces zero audience on Beauty pinned fixture post-migration (honest-dormancy preserved).
- **`ENGINE_V2_SENSITIVITY` distinct from `ENGINE_V2_TIER_CHIP`** (DS verdict §5 invariant 14): test pin at `tests/test_s8_flag_independence.py` asserts all 4 `(chip, sensitivity) ∈ {OFF, ON}²` combinations produce distinct, predictable `engine_run.json` shapes; T1.5 flips chip only, T2.5 flips sensitivity only.

**Caveats / dormant behavior:** Founder ack F1 received 2026-05-24: KI-NEW-L resume trigger is S13.5 (between S13-T4 atomic flip and S14-T1 dispatch). If post-S13/pre-S14 window is later reserved for something else (e.g., S14 dry-run on synthetic before real-merchant onboarding), KI-NEW-L re-defers to post-beta and the "no new Tier-B builders post-S13" rule hardens from mitigation to hard rule.

**Schema:** unchanged (verdict-only commit). **Suite:** unchanged. **M0:** byte-identical.

**Summary:** DS verdict `agent_outputs/ecommerce-ds-architect-s8-q3-q6-q7-verdict-2026-05-24.md` (full S14-readiness reasoning, 15 load-bearing test pins). S8-T1 dispatch unblocked.
