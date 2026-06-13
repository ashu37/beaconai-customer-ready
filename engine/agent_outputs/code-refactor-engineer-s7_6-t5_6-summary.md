# S7.6-T5.6 — generalize priority_prepend to cover all three demote channels

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `8a2d726`

---

## 1. Ticket scope

Per DS architect verdict 2026-05-23 (`agent_outputs/ecommerce-ds-architect-t6-priority-prepend-gap-verdict-2026-05-23.md`): T5.5 probe found Tier-B cards demoted by the T6 eligibility gate vanish from Considered because `eligibility_rejects` channel lacks priority_prepend protection. DS-locked verdict expanded scope to THREE sibling channels with the same gap:

- `eligibility_rejects` (T6 gate)
- `prior_unvalidated_rejects` (S7.5 priors validation routing)
- `window_disagreement_rejects` (multi-window sign-agreement routing)

All three now partition by `would_be_measured_by is not None` (Tier-B discriminator) and route the Tier-B subset into the priority_prepend slot at the assembly seam (`src/decide.py::assemble_considered`), surviving the `[:MAX_CONSIDERED_RENDERED]=6` truncation.

Implementation (Option ii per DS Q4): `RejectedPlay` gains additive `would_be_measured_by: Optional[WouldBeMeasuredBy]` field at `src/engine_run.py`. Three routing helpers populate it from the originating PlayCard. `assemble_considered` gains a new `priority_prepend_rejects` kwarg emitted ahead of `pre_existing`. All three assembly seams (PUBLISH, ABSTAIN_SOFT, ABSTAIN_HARD) partition the three channels by the Tier-B discriminator. Original typed `reason_code` preserved — Tier-B cards land in Considered with channel-of-origin reason intact, not synthetic `CAP_EXCEEDED`.

Restates the single-demote-channel invariant (DS Q2): every drop produces a typed RejectedPlay through one demote channel, AND any demoted card whose original PlayCard carried `would_be_measured_by is not None` MUST be emitted into Considered ahead of `pre_existing`.

## 2. Files changed

- `ARCHITECTURE_PLAN.md` — 2026-05-23 LOAD-BEARING UPDATE with complete invariant statement (+6 lines).
- `src/decide.py` (+105 lines).
- `src/engine_run.py` — `RejectedPlay.would_be_measured_by` additive field.
- `tests/test_s7_6_c1_priority_prepend_invariant.py` — parameterized invariant test covers all three demote channels (per DS Q3).

## 3. Behavior change

Flag-OFF behavior preserved. Beauty + Supplements pinned fixtures still pass. Under flag-ON state (post-T6.5/T5.5), Tier-B cards demoted via any of the three channels survive the truncation cap and land in Considered with their channel-of-origin reason.

Unblocks T5.5 — aov_bundle observed-effect activation can land safely because joint-fail downgrade preserves `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` reason and Tier-B card remains visible.

## 4. Tests added / modified

Parameterized invariant test in `tests/test_s7_6_c1_priority_prepend_invariant.py` extended to cover three channels. Suite: 1769p (was 1766) / 14s / 4xf / 2xp / 0f. T6 gate tests + C1 cap_exceeded tests + Beauty/Supplements pinned-fixture tests still pass.

## 5. Risks + mitigations

- **Single-demote-channel invariant restated and DS-locked** — any future builder adding a sibling demote channel must follow the same partition-by-Tier-B-discriminator pattern.
- **Three channels, one helper shape** — keeps the surface narrow; channel-specific reason codes preserved (no synthetic flattening).

## 6. Follow-ups / known-issues opened

- T5.5 unblocked (landed at `de01df4`).

## 7. Commit ref

`8a2d726`
