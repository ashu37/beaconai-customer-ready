# S8-T2.5 — flip ENGINE_V2_SENSITIVITY ON (Sensitivity block activates on 3 Beauty Tier-B Recommended cards)

**Author:** code-refactor-engineer
**Date:** 2026-05-24
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `47eebb2`
**Approved ticket:** S8-T2.5 — Per IM S8 plan Part B S8-T2 atomic-flip half + DS verdict 2026-05-24 §4 (separate per-ticket atomic flip discipline; cf. S8-T1.5 precedent at `98dad72`).

## 1. Approved scope

- Flip `ENGINE_V2_SENSITIVITY` default from `false` to `true` at `src/utils.py:727`.
- Re-pin any pinned fixture whose `engine_run.json` (or `briefing.html`) shape changes.
- Empirical tripwire: 3 Beauty Tier-B Recommended cards each carry a `sensitivity` block (NOT None) post-flip without env override.

## 2. Patch summary

One-line default change at `src/utils.py:727` (`"false"` → `"true"`). Env-override path preserved. No re-pin needed: empirically verified that `briefing.html` sha256 is byte-identical at both flag states (renderer does not surface sensitivity; founder ack 2026-05-24).

## 3. Files changed

- `src/utils.py` (L727, one-line default flip).

## 4. Tests/checks run

- Pre-flip baseline: 5 focused tests pass; harness `ENGINE_V2_SENSITIVITY → sensitivity` row passes at both env-on and env-off.
- Pre-flip empirical HTML byte-check: Beauty sha `f8676c9f...` and Supplements sha `13a91e6c...` identical at both env-on and env-off.
- Pre-flip tripwire (env-on): all 3 Beauty Tier-B Recommended cards carry `sensitivity` dict with 6 keys; all 3 carry `evidence_source = STORE_OBSERVED`; at env-off all 3 carry `sensitivity = None`.
- Post-flip focused suite (5 files: T2 sensitivity, T1 chip, harness, Beauty regression, Supplements regression): 84 passed + 2 xpassed.
- Post-flip full suite: **1825 passed**, 14 skipped, 4 xfailed, 2 xpassed, 0 failed (identical to pre-flip baseline).

## 5. Behavior changes

- `engine_run.json` now carries `sensitivity = {scenario_observed_n_halved, scenario_observed_n_doubled, scenario_prior_shifted_down, scenario_prior_shifted_up, pseudo_n_used, notes}` on the 4 wired Tier-B prior-anchored builders' validated non-suppressed BLEND cards by default (no env override required).
- `briefing.html` output: byte-identical (renderer does not surface the field).
- All other engine outputs: byte-identical.

## 6. Artifacts added

None. Tripwire scripts are throwaway `/tmp/` only.

- `agent_outputs/code-refactor-engineer-s8-t2_5-summary.md` (this file; backfilled 2026-05-25).

## 7. Remaining risks

- **HTML surface for sensitivity is intentionally absent** in the legacy renderer; consumption surface lives in the future front-end app (founder-locked).
- **KI-NEW-G (replenishment_due honest-dormancy) unaffected:** no Tier-B card emitted → no sensitivity block, consistent with the validated/non-suppressed gate.
- **Pinned-fixture shas (5/5) remain valid;** no co-changes needed in `tests/test_s8_t2_sensitivity.py::_S8_T2_PINNED_FIXTURES_AT_FLAG_OFF` (the constant's "flag OFF" naming is now slightly stale post-flip but the shas are still authoritative for HTML output; orchestrator/doc-sweep can rename if desired).

## 8. Follow-up work

- **S8-T3:** `ENGINE_V2_PROVENANCE` field + EB blend contract formalization (third additive PlayCard field per DS §5 invariant 12 cap).
- Doc sweep (orchestrator handles separately, likely T1-trio precedent style: bundle T2.5 + T3 + T3.5 LOAD-BEARING UPDATE).
- Consider renaming the `_S8_T2_PINNED_FIXTURES_AT_FLAG_OFF` constant to drop the "flag OFF" suffix now that default is ON (cosmetic; no behavior risk).

## 9. Verbatim founder ask answers

- **Line edited:** `src/utils.py:727` (`"false"` → `"true"`).
- **Pin-test files updated:** none — HTML byte-identical at both flag states.
- **Beauty sha256:** unchanged `f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3`.
- **Supplements sha256:** unchanged `13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344`.
- **M0:** byte-identical (3 fixtures verified via full suite).
- **Empirical tripwire:** 3/3 Beauty Tier-B Recommended cards carry `sensitivity` dict (6 keys; `pseudo_n_used=20`; all 4 scenario fields `source=blend, suppressed=false`) at default-ON without env override; flag-OFF returns to `None` on all 3.
- **T2 harness test:** `tests/test_v2_harness_cfg_gated_fields.py` SENSITIVITY row passes at default-ON.
- **S8-T1 + T1.6 harness + S7.6 invariants:** all pass unmodified (full suite green).
- **Suite count:** 1825 → 1825 (no change).
- **Commit sha:** `47eebb2`.
