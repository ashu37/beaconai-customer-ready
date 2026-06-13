# S8-T0 — KI-NEW-K Beauty Beta envelope re-fit (discount_dependency_hygiene + replenishment_due)

**Author:** code-refactor-engineer
**Date:** 2026-05-24
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `77086fd`
**Approved ticket:** S8-T0 — Per DS architect verdict 2026-05-24 (`agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md` §3) + founder-acked one-cell scope expansion per §6 F1 (2026-05-24). YAML-only data fix; engine code untouched. Re-fit both Beauty `base_rate` entries from defective Beta(0.66, 29.34) (J-shape, α<1, text-derived envelope) to Beta(1.32, 58.68) (unimodal, analytic envelope) at `effective_n=60`. Point estimate `value=0.0220` preserved.

## 1. Approved scope

- Re-fit `discount_dependency_hygiene.base_rate.beauty` per KI-NEW-K text scope.
- Re-fit `replenishment_due.base_rate.beauty` per founder-acked one-cell scope expansion (identical defect from same Klaviyo H&B 2026 source).
- SciPy-authoritative percentiles per DS verdict's "SciPy values are authoritative" instruction.
- Atomic Beauty pinned slate re-pin per S7.5-T3 / S7.6 atomic-flip pattern.

## 2. Patch summary

YAML-only data fix. Re-fit at `effective_n=60` preserving `value=0.0220 = α/(α+β)`. α = 0.0220 × 60 = 1.32; β = 60 − 1.32 = 58.68. Beta(1.32, 58.68) is unimodal because α>1. Analytic CDF percentiles computed via `scipy.stats.beta(1.32, 58.68).ppf([0.10, 0.50, 0.90])` → `[0.0036879681, 0.0169462728, 0.0470907418]`. Rounded to 4 decimals: p10=0.0037, p50=0.0169, p90=0.0471.

DS verdict's analytic ballpark was (0.0040, 0.0182, 0.0443) — SciPy authoritative per spec; analytic ballpark superseded. DS follow-up verdict 2026-05-24 (`agent_outputs/ecommerce-ds-architect-s8-t0-scipy-percentile-followup-2026-05-24.md`) confirmed SciPy values mathematically correct (Beta(α=1.32) is strongly right-skewed, skewness=1.64; DS analytic under-modeled skew). ACCEPT-AS-SHIPPED.

## 3. Files changed

- `config/priors.yaml` lines 363-375 (`discount_dependency_hygiene.base_rate.beauty`) + lines 1110-1122 (`replenishment_due.base_rate.beauty`). Five fields per entry: `value=0.0220` (unchanged), `range_p10=0.0037` (was 0.0120), `range_p90=0.0471` (was 0.0430), `effective_n=60` (was 30), `notes` (updated to remove KI-NEW-K caveat and cite SciPy provenance).
- `config/priors_sources/discount_dependency_hygiene__base_rate__beauty.md` — existed; updated (front-matter numerics block + provenance note).
- `config/priors_sources/replenishment_due__base_rate__beauty.md` — existed; updated (Section 1 numerics + new S8-T0 re-fit subsection).
- `tests/test_s6_t3_x_prior_rekey.py` — numeric pins updated (only test with hard pins on the affected values).
- `tests/test_s6_t3_y_audience_floor_sensitivity.py` — sha256 pin updated.
- `tests/test_s6_t3_z_considered_render.py` — sha256 pin updated.
- `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` — regenerated (re-pin).
- `scripts/s8_t0_repin.py` — new helper (audit-trail re-pin script; mirrors S7.6 archive pattern). Subsequently moved to `scripts/archive/s8_probes/` in doc-sweep commit `ca794bd`.

## 4. Tests/checks run

- `tests/test_s6_t3_x_prior_rekey.py`: 6 passed (numeric pins re-validate).
- `tests/test_s7_6_c1_priority_prepend_invariant.py`: 8 passed, 2 xfailed (S7.6 tripwire intact).
- Full suite: **1770 passed**, 14 skipped, 4 xfailed, 2 xpassed (identical to pre-edit baseline).

## 5. Behavior changes

- Beauty pinned slate sha256: `fcd2924b...` → **`f8676c9f...`** (one card's prior-trace metadata updated; revenue_range bounds shift is bps-scale because store dominates posterior at `observed_n=224K`, `w_obs > 0.9998`).
- Supplements pinned slate sha256: `13a91e6c...` (UNCHANGED — no supplements entry exists for either play and `replenishment_due` is dormant per KI-NEW-G).
- M0 goldens (small_sm, mid_shopify, micro_coldstart): byte-identical (no Tier-B consumer for these priors).
- All three S7.6 architectural invariants preserved (single-demote-channel, 3-channel priority_prepend, T6 eligibility gate).
- S7.6 CLI fix Measurement.observed_effect/p_internal/n surfacing preserved (tripwire test pinned-pass).

## 6. Artifacts added

- `scripts/s8_t0_repin.py` (later archived to `scripts/archive/s8_probes/`).
- `agent_outputs/code-refactor-engineer-s8-t0-summary.md` (this file; backfilled 2026-05-25).

## 7. Remaining risks

- **SciPy values diverged from DS analytic ballpark (6-8% on p50/p90).** Verified ACCEPT-AS-SHIPPED by DS follow-up verdict 2026-05-24 — DS analytic under-modeled right-skew at α≈1.32. No engine-behavior risk; methodological lesson recorded for future DS-architect ballparks at low-α Beta priors.
- **Klaviyo PDF provenance verification (KI-NEW-K secondary issue)** — base64-image-transcribed source numerics still unverified against original Klaviyo PDFs. Out of S8-T0 scope; called out in updated memos.
- **`replenishment_due.base_rate.beauty` was a founder-acked scope expansion** beyond the KI text — atomic fix applied because same defect from same source; if KI text bounds matter strictly, this is a deviation logged with founder ratification 2026-05-24.

## 8. Follow-up work

- Orchestrator doc-sweep (closed KI-NEW-K in KNOWN_ISSUES.md; pseudo_N lock documented in ARCHITECTURE_PLAN.md + memory.md; DS verdicts tracked in agent_outputs; probe script archived).
- S8-T1 dispatch unblocked (EvidenceSourceChip enum + PlayCard.evidence_source field).

## 9. Verbatim founder ask answers

- **SciPy command + output:** `scipy.stats.beta(1.32, 58.68).ppf([0.10, 0.50, 0.90])` → `[0.0036879681, 0.0169462728, 0.0470907418]`.
- **Exact line numbers:** `config/priors.yaml:363-375` (discount_dependency_hygiene) + `:1110-1122` (replenishment_due).
- **Beauty pinned slate sha256:** `fcd2924b...` → `f8676c9f...`.
- **Predicted vs actual shift:** Beauty `discount_dependency_hygiene.revenue_range` bounds shift ≤0.1% on dollars (store-dominant blend at w_obs > 0.9998); JSON sha changes due to prior-trace metadata bytes (effective_n + range_p10/p90). Actual: sha changed as predicted; suite-level invariants on the active card all hold.
- **Supplements pinned slate sha256:** `13a91e6c...` (unchanged, matches prediction).
- **M0 byte-identical:** confirmed (small_sm, mid_shopify, micro_coldstart).
- **Suite count:** 1770 passed (unchanged from pre-edit baseline).
- **S7.6 CLI fix tripwire test:** PASS unmodified.
- **Commit sha:** `77086fd`.
- **Memos updated:** both existed and were updated (`discount_dependency_hygiene__base_rate__beauty.md` + `replenishment_due__base_rate__beauty.md`).

## Backfill from memory.md (migration trim 2026-05-25)

## S8-T0 — KI-NEW-K Beauty Beta envelope re-fit (2026-05-24)

**Shipped:**
- `config/priors.yaml` lines 363-375 (`discount_dependency_hygiene.base_rate.beauty`) + lines 1110-1122 (`replenishment_due.base_rate.beauty`, founder-acked one-cell scope expansion per DS verdict §6 F1) re-fit from defective Beta(0.66, 29.34) (J-shape, α<1, text-derived envelope) to Beta(1.32, 58.68) at `effective_n=60`.
- SciPy-authoritative percentiles `(p10, p50, p90) = (0.0037, 0.0169, 0.0471)` computed via `scipy.stats.beta(1.32, 58.68).ppf(...)`; DS analytic ballpark `(0.0040, 0.0182, 0.0443)` superseded per DS verdict's "SciPy values are authoritative" instruction. DS follow-up verdict 2026-05-24 confirmed SciPy values mathematically correct (Beta(α≈1.32) is strongly right-skewed, skewness=1.64; DS analytic ballpark under-modeled skew). NO ENGINE BEHAVIOR DEFECT — production dollar delta <0.1% at `observed_n=224K` (`w_obs=0.99987`).
- Memos at `config/priors_sources/discount_dependency_hygiene__base_rate__beauty.md` + sibling `replenishment_due__base_rate__beauty.md` updated to document SciPy-authoritative posture.
- `tests/test_s6_t3_x_prior_rekey.py` numeric pins updated.
- Beauty pinned slate sha256 `fcd2924b…` → `f8676c9f…` atomically with YAML edit (S7.5-T3 / S7.6 atomic-flip pattern).

**Load-bearing invariants:**
- **`PSEUDO_N_BY_STATUS = {VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}`** is the locked S7.5-T3 production table per DS verdict §2. No new statuses, no new numbers in S8. The `Prior.pseudo_N: Optional[int]` per-prior override field proposed in `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md` Part H is REJECTED per DS verdict §6 F2 (founder-acked 2026-05-24) — validation_status is the single dial; per-prior numeric overrides are a backdoor that bypasses per-status cap discipline.
- `HEURISTIC_UNVALIDATED` + `PLACEHOLDER` priors are refusal at sizing layer, never blended with low weight. Gate 2 (validation_status, S7.5) is the laundering protection — `pseudo_N` only governs validated priors.
- `effective_n` is metadata only; never overrides per-status cap.
- `gate_calibration.pseudo_n_default` can only LOWER the cap (`min(status_cap, profile_default)`), never raise.
- All three S7.6 architectural invariants preserved (single-demote-channel + 3-channel priority_prepend + T6 eligibility gate); S7.6 CLI fix surfacing preserved (tripwire test passes unchanged).
- M0 byte-identical (small_sm, mid_shopify, micro_coldstart); Supplements byte-identical.

**Caveats / dormant behavior:** Klaviyo PDF provenance verification (KI-NEW-K secondary issue: base64-image transcribed source numerics) noted in memos as out-of-S8-T0-scope follow-up. KI-NEW-J supplements `aov_lift_via_threshold_bundle` magnitude defers to S14 pre-private-beta calibration window with locked resume-trigger text per DS verdict §4.

**Schema:** unchanged (YAML-only data fix, no code change). **Suite:** 1770 passed, 14 skipped, 4 xfailed, 2 xpassed, 0 failed (unchanged from S7.6 CLI fix baseline). **M0:** byte-identical.

**Summary:** DS verdict `agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md` (full S8 pseudo_N + KI-NEW-K lock through the S14-readiness lens); DS follow-up verdict `agent_outputs/ecommerce-ds-architect-s8-t0-scipy-percentile-followup-2026-05-24.md` (SciPy values verification + ACCEPT-AS-SHIPPED ruling); commit `77086fd` (S8-T0); commit `<doc-sweep>` (this doc sweep).
