# S7.6-FIX — priority_prepend in populate_considered_from_candidates for S6/S7 Tier-B plays

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `bb9fd32`

---

## 1. Ticket scope

Close the verified silent-drop at `decide.py:825-842` cap-trim. The three S6/S7-wired Tier-B plays were already being converted to typed RejectedPlay records inside `populate_considered_from_candidates` (`decide.py:807-820`) but sorted behind 6 legacy guardrail rejections and truncated off by `[:MAX_CONSIDERED_RENDERED=6]`. `considered_truncated_count=8` was correctly counting them; we misread what it counted until direct in-process probe (agent `aaa6428f60edf190c`, 2026-05-22).

Fix mirrors C1 `assemble_considered` priority_prepend precedent (`decide.py:343-409`) adapted for raw M3 candidates. Discriminator: `candidate.play_id in _PRIOR_ANCHORED` (the S6/S7-wired Tier-B set at `measurement_builder.py:717`). Tier-B candidates prepend before legacy rejections; cap-trim preferentially drops legacy plays per founder decision (CLAUDE.md 2026-05-22).

## 2. Files changed

- `src/decide.py` (+46 lines).
- `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` (re-pin).
- `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` (re-pin, +7 lines diff).
- 9 test files updated for sha re-pin + new Tier-B presence assertions:
  `tests/test_g2_empty_bottle_vertical_dispatch.py`,
  `tests/test_inventory_blocked_in_considered.py`,
  `tests/test_s5_t2_supplement_cadence_abstain.py`,
  `tests/test_s6_t1_5_winback_dormant_repin.py`,
  `tests/test_s6_t3_y_audience_floor_sensitivity.py`,
  `tests/test_s6_t3_z_considered_render.py`,
  `tests/test_s7_6_c1_priority_prepend_invariant.py`,
  `tests/test_slate_regression_beauty_brand.py`,
  `tests/test_slate_regression_supplements_brand.py`.

## 3. Behavior change

Verified on `healthy_supplements_240d`:
- `winback_dormant_cohort`: now in Considered with `AUDIENCE_TOO_SMALL`
- `cohort_journey_first_to_second`: now in Considered with `AUDIENCE_TOO_SMALL`
- `aov_lift_via_threshold_bundle`: now in Considered with `DATA_QUALITY_FLAG`

Beauty: `aov_lift_via_threshold_bundle` now in Considered with `DATA_QUALITY_FLAG` (was silent under T7.5-deferred flag state). `empty_bottle` is displaced by the Tier-B priority_prepend per the founder single-demote-channel invariant (legacy plays drop first).

Beauty briefing sha256: `158bf726f5...` -> `5afc4d62e9...`.
Supplements briefing sha256: `01f5feff84...` -> `0903071ee9...`.
M0 byte-identical confirmed.

## 4. Tests added / modified

Tier-B-presence invariant test (DS Q3 verdict 2026-05-22) pins the founder criterion in code on both Beauty and Supplements pinned fixtures. Sha re-pins across 9 test files.

## 5. Risks + mitigations

- **Identified via direct in-process probe** (agent `aaa6428f60edf190c`) after misreading `considered_truncated_count=8`. The CLAUDE.md "instrument-before-fix" rule directly traces to this discovery path.
- **Founder-locked legacy-plays-drop-first policy** (CLAUDE.md 2026-05-22): cap-trim preferentially drops legacy plays so Tier-B prior-anchored cards stay visible.

## 6. Follow-ups / known-issues opened

- C2 (`6d248fd`) follows to restore single-demote-channel invariant on the injection path.

## 7. Commit ref

`bb9fd32`
