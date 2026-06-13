# S7.6 flips rollup — atomic observed-effect + eligibility-gate flag-flip closeouts

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commits covered:** `28e4859` (T1.5), `21bc273` (T3.5), `2f1c17c` (T4.5), `de01df4` (T5.5), `6d312d3` (T6.5)
**Note:** Rollup-style summary for five Sprint 2 Risk #4 atomic flag-flip commits in the S7.6 observed-effect wiring sprint. Each flip was probe-gated per CLAUDE.md 2026-05-22 discipline (predict observed_n before each T*.5 flip) and atomic with any required fixture re-pin.

---

## 1. Ticket scope

Five atomic flag flips that activate per-store observed-effect computation for the Tier-B prior-anchored plays (winback / discount_hygiene / journey / aov_bundle) and the eligibility gate that consumes the observed-effect data. Each flip was preceded by a tripwire probe (`scripts/s7_6_t*_5_probe.py`) verifying observed_n >= founder threshold (30) and sign_agreement_count >= 2 across {L28, L56, L90}.

- **T1.5 (28e4859)** — flip `ENGINE_V2_OBSERVED_EFFECT_WINBACK` ON. Beauty probe: observed_k=55, observed_n=334 (>>30), posterior_value=0.159887 (`store_dominant`), sign_agreement=3/3, dominant_sign=+1. Supplements winback prior is heuristic_unvalidated (suppressed via `prior_unvalidated`); winback card never reaches blend-permitted emit path on supplements.
- **T3.5 (21bc273)** — flip `ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE` ON. Beauty probe: observed_n=148,451 (very large), posterior shift 0.022 -> 0.116881 (`store_dominant`), sign_agreement=3/3 (all L28/L56/L90 p=0.0, sign=+1). Supplements helper short-circuits per Path-D Memo-4 REJECT (no `discount_dependency_hygiene` card on supplements at all).
- **T4.5 (2f1c17c)** — flip `ENGINE_V2_OBSERVED_EFFECT_JOURNEY` ON. Beauty probe: observed_n=392 (early-half-window cohort per Berkson invariant), observed_k=58, posterior shift 0.18 -> 0.149515 (`store_dominant`), sign_agreement=3/3. Berkson invariant test (`tests/test_berkson_invariant.py`) still passing. Supplements: card lands in Considered with no `blend_provenance` (thin first-to-second signal; KI-20 contract preserved).
- **T5.5 (de01df4)** — flip `ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE` ON. Beauty probe: Welch-t L28 p ~0.876, z-prop L28 p ~0.877, **joint-FAIL**. Gate correctly downgrades the card to Considered[0] with `signal_inconsistent_across_windows`, leading via `priority_prepend_rejects`; `would_be_measured_by` preserved. Re-sequenced from the original plan (was T5.5 -> T6) to T6 -> T6.5 -> T5.6 -> T5.5 per DS verdicts 2026-05-23; without T6/T6.5/T5.6 in place first, joint-fail on Beauty would have either surfaced aov_bundle in Recommended with a 20x noise-driven posterior shift OR vanished entirely — both violating the founder honest-placement criterion. **Last code commit of S7.6 continuation.**
- **T6.5 (6d312d3)** — flip `ENGINE_V2_OBSERVED_ELIGIBILITY_GATE` ON. Activates the T6 gate (joint-p<0.10 for builders stashing `*_band` windows; sign-agreement>=2 for all builders) AND the 3-state copy ladder (cold-start / accumulating / mature) per posterior_ratio. On Beauty: three active observed-effect cards (winback / discount_hygiene / journey) all hit `mature` (posterior_ratio>=0.6) and prepend "Cohort signal dominates - " to `why_now`. Unblocks T5.5.

## 2. Files changed (per commit)

- **T1.5 (28e4859, 3):** `src/utils.py`; `tests/test_s6_5_t5_atomic_repin.py`; `scripts/s7_6_t1_5_probe.py` (new probe script, kept in tree).
- **T3.5 (21bc273, 4):** `src/utils.py`; `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`; `tests/test_s6_t3_y_audience_floor_sensitivity.py`; `tests/test_s6_t3_z_considered_render.py`. Atomic re-pin script kept untracked.
- **T4.5 (2f1c17c, 1):** `src/utils.py` only (pinned fixtures byte-identical post-flip; HTML not sensitive to the posterior-precision shift on this card).
- **T5.5 (de01df4, 4):** `src/utils.py`; `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`; `tests/test_s6_t3_y_audience_floor_sensitivity.py`; `tests/test_s6_t3_z_considered_render.py`.
- **T6.5 (6d312d3, 4):** `src/utils.py`; `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`; `tests/test_s6_t3_y_audience_floor_sensitivity.py`; `tests/test_s6_t3_z_considered_render.py`.

## 3. Behavior change

Beauty briefing sha256 chain across the sprint:
- pre-S7.6 (post-S7-T3.5 + T7.5 deferral close): `1a5a35eb67898e6...`
- T3.5 re-pin: -> `f66894a2d8f4e2...`
- T4.5: unchanged (`f66894a2...`)
- T6.5 re-pin: -> `87226ba707cfbe...`
- T5.5 re-pin: -> `fcd2924bc18d72...`

Supplements byte-identical throughout (sha256 `13a91e6cd320...`). M0 goldens byte-identical throughout.

Observable merchant-facing changes on Beauty:
- Three Recommended Now cards (winback, discount_hygiene, journey) carry mature-stage `why_now` copy ("Cohort signal dominates - ...").
- AOV bundle card lands at Considered[0] with `signal_inconsistent_across_windows`, leading the rest of Considered via priority_prepend; `would_be_measured_by` preserved.

## 4. Tests added / modified

- **T1.5:** updated `test_s6_5_t5_atomic_repin.py::test_04_beauty_winback_posterior_numerics` to pin new contract (k=55, n=334, posterior=0.159887, store_dominant, sign_agreement=3, dominant_sign=+1). Suite 1668p/14s/4xf/0f.
- **T3.5:** sha cite + S7.6-T3.5 attribution comment in 2 pin-test files. Suite 1742p (baseline preserved).
- **T4.5:** Berkson invariant test still passing; no test edits. Suite 1742p.
- **T5.5:** pin-test sha re-cites. Suite 1769p/14s/4xf/2xp/0f.
- **T6.5:** pin-test sha re-cites. Suite 1766p/14s/4xf/2xp (+24 new T6 tests from prior commit, zero regressions).

Tier-B-presence invariant test (`tests/test_s7_6_c1_priority_prepend_invariant.py`) passing on every flip.

## 5. Risks + mitigations

- **Re-sequencing dependency (T5.5 after T6/T6.5/T5.6).** Originally planned T5.5 -> T6. DS verdict 2026-05-23 re-sequenced to land the gate + priority_prepend generalization first; otherwise Beauty's joint-fail AOV-bundle case would have either surfaced with a 20x noise posterior or silently vanished. The C2 helper (apply_guardrails_to_injected, commit `6d248fd`) + T5.6 priority_prepend generalization (commit `8a2d726`) together restore the single-demote-channel invariant.
- **Pure-contract flips (T1.5, T4.5 for fixtures).** Renderer is not yet wired to surface observed_k / observed_n / posterior numerics on winback card -> Beauty briefing byte-identical at T1.5. Downstream contract consumers (memory.db reason fan-out, blend_provenance stash) do see the new values. CLI receipt-surface fix is deferred to S7.6-CLI-FIX (commit `d8ede8c`, has its own summary file).
- **Supplements deliberately under-exercised.** Multiple flips short-circuit on supplements per Path-D / vertical exclusion / heuristic_unvalidated paths. This is by design (founder direction to keep supplements honest under thin signal), not a coverage gap.

## 6. Follow-ups / known-issues opened

- **S7.6-CLI-FIX (d8ede8c)** — populate `Measurement.observed_effect / p_internal / n` on Tier-B prior-anchored cards from the `blend_provenance` stash for CLI receipts. Separate summary file exists.
- **S8 sprint** — Provenance + Sensitivity + EvidenceSourceChip work consume the observed-effect contract surface this sprint formalized.
- **KI-NEW-L / -M / -N** — opened at S7.6-C3 (commit `d6053d0`): consolidate the 5 V2 prior-anchored injection blocks; resolve `_dedupe_rejections` first-wins vs last-wins-typed-code policy; experiment-promotion provenance preservation at decide.py:2080-2087.

## 7. Commit refs

- T1.5 — `28e4859`
- T3.5 — `21bc273`
- T4.5 — `2f1c17c`
- T5.5 — `de01df4` (last code commit of S7.6 continuation pre-CLI-FIX)
- T6.5 — `6d312d3`
