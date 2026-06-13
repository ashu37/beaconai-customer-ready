# S8-T3 — Provenance typed dataclass + PlayCard.provenance field + EB blend contract formalization (flag OFF)

**Author:** code-refactor-engineer
**Date:** 2026-05-24
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `9817216`
**Approved ticket:** S8-T3 — Per IM S8 plan Part B S8-T3 + DS verdicts 2026-05-24 (pseudo_N §2 locked 30/15/10; §5 invariant 12 cap at 3 fields; §6 F2 rejected per-prior override; Q5 reuse `blend` literal; cfg-wiring §Q5 invariant 16 harness discipline). **Third + final S8 additive PlayCard field** (evidence_source at `98dad72`; sensitivity at `47eebb2`; provenance this commit). EB blend math is already shipped (S7.5-T3); this commit formalizes the audit-surface contract only.

## 1. Approved scope

- Add typed `Provenance` dataclass + `PlayCard.provenance` field (third and final S8 additive PlayCard field per DS invariant 12).
- Formalize the EB blend audit-surface contract.
- New `compute_provenance` helper reusing the locked `bayesian_blend` + `effective_pseudo_n` + `PSEUDO_N_BY_STATUS` (30/15/10) shipped at S7.5-T3.
- Behind `ENGINE_V2_EB_BLEND` flag default OFF; T3.5 atomic flip is a separate later dispatch.

## 2. Patch summary

Three additive shapes, one new flag, one new helper, audit-only refactor — **no blend math change**. `Provenance` dataclass refuses HEURISTIC_UNVALIDATED + PLACEHOLDER via `_BLEND_PERMITTED_STATUSES` (defense-in-depth for DS invariant 2); reuses `effective_pseudo_n` + `PSEUDO_N_BY_STATUS`; weights sum to 1.0; arithmetic-mean fallback at zero denominator.

REJECTED per DS verdicts: `Prior.pseudo_N` per-prior override field (§6 F2), new `blend_empirical_bayes` `RevenueRange.source` literal (Q5), new pseudo_N values (production 30/15/10 locked).

## 3. Files changed

- `src/engine_run.py` — `Provenance` dataclass at lines 592-689; `PlayCard.provenance: Optional[Provenance] = None` at lines 760-775; `_from_dict_provenance` helper at lines 1145-1186; round-trip wired in `_from_dict_play_card` at lines 1211-1215.
- `src/sizing.py` — `Provenance` import at line 64; `compute_provenance(...)` helper at lines 361-470 (refuses HEURISTIC_UNVALIDATED + PLACEHOLDER via `_BLEND_PERMITTED_STATUSES`; reuses `effective_pseudo_n` + `PSEUDO_N_BY_STATUS`; weights sum to 1.0; arithmetic-mean fallback at zero denominator); `__all__` extended.
- `src/measurement_builder.py` — `Provenance` import at line 73; populate site in `build_prior_anchored_play_card` at lines 2467-2496 (gate: cfg flag ON AND `revenue_range.source == BLEND` AND not suppressed); `PlayCard(..., provenance=provenance)` at line 2516.
- `src/utils.py` — `ENGINE_V2_EB_BLEND` flag default OFF at lines 729-758; bool-coerce set updated at line 1071.
- `tests/test_v2_harness_cfg_gated_fields.py` — new parametrize row `ENGINE_V2_EB_BLEND -> provenance` (harness end-to-end on Beauty 240d) per DS invariant 16.
- `tests/test_s8_t3_provenance.py` — new test file, 34 tests (round-trip, helper math, DS invariant 1/2/5 pins, weights-sum-to-1, cold-start, per-builder populates, flag-off omits, three-flag-independence, pinned-fixture byte-identity).

## 4. Tests/checks run

- `pytest tests/test_s8_t3_provenance.py`: 34/34 passed.
- `pytest tests/test_s8_t1_evidence_source_chip.py tests/test_s8_t2_sensitivity.py tests/test_v2_harness_cfg_gated_fields.py`: 57/57 passed (T1/T2 unchanged behavior; harness rows for chip + sensitivity + new provenance all pass).
- Full suite: **1825 → 1861 passed**, 14 skipped, 4 xfailed, 2 xpassed, 0 failed (+36).

## 5. Behavior changes

- At default (`ENGINE_V2_EB_BLEND=false`): zero behavior change. Every `PlayCard.provenance` is `None`; M0 + Beauty (`f8676c9f...`) + Supplements (`13a91e6c...`) HTML fixtures byte-identical (verified by pinned sha256 test).
- At flag ON (T3.5 later): the 4 wired Tier-B builders on the validated, non-suppressed BLEND path emit a typed `Provenance` audit object documenting which prior was consumed, validation_status, pseudo_n_used (≤ pseudo_n_cap), observed_n, and the resulting prior/observed weights.

## 6. Artifacts added

- `tests/test_s8_t3_provenance.py` (34 tests).
- `agent_outputs/code-refactor-engineer-s8-t3-summary.md` (this file; backfilled 2026-05-25).

## 7. Remaining risks

- **T3.5 atomic flag flip is the next dispatch.** When `ENGINE_V2_EB_BLEND` flips ON, Beauty + Supplements re-pin will be needed (provenance field appears on 3 Beauty Tier-B Recommended cards). Per the DS verdict the **blend math itself does not change** — so revenue_range.p10/p50/p90 must stay numerically identical; only the new `provenance` payload appears in `engine_run.json`.
- **DS invariant 12 cap reached:** no 4th additive PlayCard field permitted in S8. Any future Tier-B card slot belongs to S13 (`ranking_strategy` etc.) or a new event_version bump.

## 8. Follow-up work

- **S8-T3.5** (next dispatch): atomic default flip `ENGINE_V2_EB_BLEND=true` + Beauty + Supplements re-pin if shape diffs (expected: shape-only — new `provenance` key; numerics identical).
- **S8-T4**: Play Library wave 1 refactor (`plays/<play_id>/`), independent of T3.

## 9. Verbatim founder ask answers

- **Exact line numbers in `src/engine_run.py`:** Provenance dataclass at 592-689; PlayCard.provenance field at 760-775; `_from_dict_provenance` at 1145-1186; round-trip wired at 1211-1215.
- **Exact location in `src/sizing.py`:** `compute_provenance` at 361-470.
- **Exact line numbers in `src/measurement_builder.py`:** import L73; populate L2467-2496; PlayCard constructor L2516.
- **Flag location + default in `src/utils.py`:** L729-758 (default `"false"`); bool-coerce set at L1071.
- **New test file name + count:** `tests/test_s8_t3_provenance.py` (34 tests).
- **New parametrize row in `tests/test_v2_harness_cfg_gated_fields.py`:** `ENGINE_V2_EB_BLEND → provenance`.
- **Suite count:** 1825 → 1861 (+36).
- **M0 + Beauty + Supplements sha256 byte-identical:** confirmed (verifying blend math is unchanged).
- **S7.6 + S8-T1 + S8-T2 tests:** all pass unmodified.
- **Commit sha:** `9817216`.
