# S8-T3.5 — flip ENGINE_V2_EB_BLEND ON (Provenance block activates on 3 Beauty Tier-B Recommended cards, blend math unchanged)

**Author:** code-refactor-engineer
**Date:** 2026-05-24
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `c3eb5e4`
**Approved ticket:** S8-T3.5 — Per IM S8 plan Part B S8-T3 atomic-flip half + DS verdict 2026-05-24 §4 (separate per-ticket atomic flip discipline; cf. S8-T1.5 precedent at `98dad72` and S8-T2.5 at `47eebb2`).

## 1. Approved scope

S8-T3.5: atomic flip of `ENGINE_V2_EB_BLEND` default false → true; activates typed `provenance` payload on the 3 Beauty Tier-B Recommended cards. T3 contract-only ticket; **blend math unchanged per DS verdict**. Zero re-pin if blend numerics are bit-identical pre-vs-post flip (load-bearing invariant verification).

## 2. Patch summary

One-line default flip in `src/utils.py`. No test edits. No re-pin required (renderer doesn't surface provenance; founder-acked).

## 3. Files changed

- `src/utils.py` L759: `"false"` → `"true"`.

Untracked helper (later archived to `scripts/archive/s8_probes/` in S8-CLOSE doc sweep commit `c7e7963`):
- `scripts/s8_t3_5_probe.py` (tripwire probe).

## 4. Tests/checks run

- Full suite: **1861 passed**, 14 skipped, 4 xfailed, 2 xpassed in 1211.67s (identical to pre-flip baseline).
- Empirical tripwire (Beauty 240d, both flag states): passed all invariants.

## 5. Behavior changes

- `engine_run.json` now carries `provenance = Provenance(...)` on 3 Tier-B Recommended cards by default.
- `briefing.html` byte-identical (renderer-invisible).
- `revenue_range.p10/p50/p90` bit-identical to pre-flip on all 3 cards (DS invariant preserved — blend math unchanged).

## 6. Artifacts added

- Probe script (later archived) at `scripts/s8_t3_5_probe.py`.
- `agent_outputs/code-refactor-engineer-s8-t3_5-summary.md` (this file; backfilled 2026-05-25).

## 7. Empirical tripwire results

| Play | pre (p10,p50,p90) | post (p10,p50,p90) | provenance flips |
|---|---|---|---|
| winback_dormant_cohort | (843.25, 3370.61, 3370.61) | (843.25, 3370.61, 3370.61) | None → populated |
| discount_dependency_hygiene | (420.02, 13268.19, 13268.19) | (420.02, 13268.19, 13268.19) | None → populated |
| cohort_journey_first_to_second | (5746.41, 10739.64, 22985.62) | (5746.41, 10739.64, 22985.62) | None → populated |

All 3 cards: `validation_status=validated_external`, `pseudo_n_used=20`, `pseudo_n_cap=30`. Beauty/Supplements/M0 fixture shas all unchanged.

## 8. Remaining risks / follow-up

- **KI-NEW-G (replenishment_due dormant — no card → no provenance)** unchanged; not in T3.5 scope.
- **Untracked probe scripts in `/scripts/`** pending orchestrator's S7.6-pattern archive sweep (handled at S8-CLOSE doc sweep commit `c7e7963`).
- **Next milestone:** per IM S8 plan, downstream tickets layering on provenance audit surface (front-end app consumer, KI-NEW-G replenishment_due reactivation).

## 9. Verbatim founder ask answers

- **Exact line number in `src/utils.py` edited:** L759 (`"false"` → `"true"`).
- **Pin-test file path(s) updated:** none — Beauty HTML pin byte-identical (renderer doesn't surface provenance).
- **Beauty pinned slate sha256:** unchanged.
- **Supplements pinned slate sha256:** unchanged.
- **M0 byte-identical:** confirmed.
- **Empirical tripwire:** 3 Beauty Tier-B Recommended cards' `provenance` blocks populated; `revenue_range.p10/p50/p90` numerics IDENTICAL pre-vs-post (DS-required, blend math unchanged).
- **T3 harness test:** EB_BLEND row passes at default-ON.
- **S8-T1 + T1.6 + S8-T2 + S7.6 + priority_prepend invariant tests:** all pass unmodified.
- **Suite count:** 1861 → 1861 (no change).
- **Commit sha:** `c3eb5e4`.
