# S7.6-T7 — B-5 threshold-from-data primary + supplements re-disable (flag OFF)

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `0831b03`

---

## 1. Ticket scope

Implement `ENGINE_V2_AOV_THRESHOLD_FROM_DATA` (default OFF) for `aov_lift_via_threshold_bundle_candidates` per `ARCHITECTURE_PLAN.md` B-5:248-257 (founder Path A, 2026-05-21):

- **Supplements unconditionally excluded** under flag-ON (reverts the S7-T3.5 supplements activation, which never fired on the synthetic fixture anyway). Reason: `vertical_excluded_per_b5_248`.
- **Threshold resolution order:** L90 P60 of net_sales (require L90 order count >= 200 for stable percentile per B-5:254), then `cfg["AOV_BUNDLE_THRESHOLD_USD"]` fallback, then `data_missing` refuse.
- New optional `AudienceResult.threshold_source` provenance field (`l90_p60_data_derived | cfg_merchant_declared | vertical_excluded | data_missing`). None by default; renderer-irrelevant.

Flag OFF preserves S7-T3.5 behavior verbatim. Default flips to ON in S7.6-T7.5 atomic with Beauty + Supplements fixture re-pin (landed at C3 / `d6053d0`).

## 2. Files changed

- `src/audience_builders.py` (+91 lines).
- `src/utils.py` (+21 lines).
- `tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py` (+142 lines, 7 new test cases).

## 3. Behavior change

None at flag-OFF default. M0 + Beauty + Supplements byte-identical.

Under flag-ON: Beauty AOV threshold becomes L90 P60 data-derived (~$71.88 on the synthetic Beauty fixture per C3 close-out); supplements card vanishes entirely with `vertical_excluded_per_b5_248`.

## 4. Tests added / modified

7 new test cases cover: default-OFF, OFF-cfg-only legacy preservation, ON-supplements-excluded, ON-Beauty-P60-derived, ON-P60-correctness, ON-n<200-fallback, ON-both-fail-refuse, AudienceResult field default.

Suite: 1686p / 14s / 4xf / 0f.

## 5. Risks + mitigations

- **Supplements activation reversal** — S7-T3.5 had shipped the supplements path Path-D dormant; T7 makes the exclusion explicit at the audience-builder seam via vertical gate. No supplements behavior regression because the synthetic fixture never produced the card under T3.5 anyway.
- **N>=200 stability threshold** — per B-5:254, prevents noisy P60 on small order histories.

## 6. Follow-ups / known-issues opened

- T7.5 atomic flip landed at C3 (`d6053d0`).
- T7-FIX (separate summary file) addresses the gate_materiality provenance gap surfaced by T7's surfacing path on real-merchant data.

## 7. Commit ref

`0831b03`
