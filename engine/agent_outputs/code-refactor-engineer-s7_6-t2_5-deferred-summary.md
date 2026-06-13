# S7.6-T2.5 DEFERRED — `replenishment_due` observed-effect wiring inert on Beauty under current fixtures (Path c)

**Date:** 2026-05-22
**Branch:** `post-6b-restructured-roadmap`
**Status:** DEFERRED (T2 plumbing accepted at `b0c9980`; T2.5 atomic activation NOT executed in S7.6)
**Path:** (c) — DS-architect locked 2026-05-22
**Flag posture:** No flag flip in this ticket; wiring remains inert on Beauty until D-S6-4 clears via real beta data or upstream S6 reopen.

---

## 1. Approved scope

S7.6 wires per-store observed-effect `(observed_k, observed_n)` into the EB blend at `src/sizing.py::bayesian_blend`, so posteriors shift from prior toward store data as `n` grows. T0 helper + T1.5 winback (Beauty `observed_n=334`, posterior shifted 0.08 → 0.16) proved the contract. T2 extended the same plumbing to B-2 `replenishment_due`.

T2 (`b0c9980`) — measurement-builder + main.py wire-through that plumbs `observed_k` / `observed_n` for `replenishment_due` candidates through to `bayesian_blend`. Plumbing is structurally correct; suite green at **1678 passed / 14 skipped / 4 xfailed / 0 failed**.

T2.5 (the atomic activation half) was intended to confirm Beauty produces a card with non-null `observed_n` so the blend visibly shifts the posterior on the fixture. The tripwire run showed `replenishment_due` never reaches the card-build stage on Beauty G-1: `observed_n` / `observed_k` are undefined because the candidate is suppressed upstream at the D-S6-4 per-SKU N≥30 gate (cohort_n collapses to 0). No card → nothing to measure-shift → T2.5 has no surface to activate against.

## 2. DS-architect verdict — Path (c)

DS-architect (2026-05-22) ruled: ship T2 plumbing as-landed; do NOT execute T2.5; do NOT regenerate the Beauty fixture to manufacture a passing tripwire. The three paths considered:

- **Path (a) — Regenerate Beauty fixture with hero-SKU repeat concentration sufficient to clear D-S6-4.** REJECTED. Reshapes a pinned artifact that downstream agents read as ground truth ("this is what a merchant looks like") to flatter a single T-ticket. Worse failure mode than the deferral.
- **Path (b) — Recalibrate D-S6-4 now to surface the play.** REJECTED. KI-NEW-H already governs this as a coupled Phase 9 recalibration of D-S6-4 + D-S6-5 + D-FLOOR-replenishment_due. Tuning one in isolation is wrong-shaped.
- **Path (c) — Ship T2 plumbing, defer T2.5, encode tripwire discipline.** ACCEPTED. T2.5 reopens atomically when Beauty clears D-S6-4 (real beta data or future S6 reopen). All wiring is in place; activation requires no new code.

## 3. Trace correction

The gate is NOT "Path-D Supplements-only" (the initial read). It is **D-S6-4 per-SKU N≥30 floor collapses `cohort_n` to 0 on synthetic Beauty G-1**. Fixture-shape vs floor-coupling issue, not a vertical carve-out. Supplements has no `replenishment_due` floor cell at all (per `D-PRIORS-replenishment_due_supplements_deferred`), so the supplements posture is asymmetric-by-design and orthogonal to the Beauty trace.

## 4. New sprint discipline (DS-locked)

Before each T*N* observed-effect wiring ticket: predict whether `observed_n > 0` on the available Beauty fixture FIRST by reading builder + fixture. If predicted-zero, plan T*N*.5 as a Path-(c) deferral from the start, rather than discovering post-commit. Applies prospectively to S7.6-T3 / T4 / T5.

## 5. Synthetic-fixture philosophy (reaffirmed)

Synthetic Beauty / Supplements fixtures = plausible merchant shape, NOT branch coverage. Branch coverage belongs in isolated unit tests — which already exist for `replenishment_due` (the 42-cell floor resolver test + 8-cell surface-field test). End-to-end fixtures reflect what the engine actually decides on representative data; they are not test inputs to be reshaped to fire a specific builder.

## 6. Resume trigger

When Beauty clears D-S6-4 — via either real beta data carrying hero-SKU repeat concentration ≥30 per SKU AND cohort ≥150 in the ±½-cadence window, OR a Phase 9 KI-NEW-H joint recalibration that lowers the per-SKU gate — flip `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` ON, re-pin the slate fixtures against real-store byte-streams, and confirm `observed_n` populates non-null on the resulting card. No T2.5 work required in S7.6.

## 7. Files referenced (this ticket — documentation only)

- `KNOWN_ISSUES.md` — KI-NEW-G appended with S7.6-T2 closeout note (no new KI; per DS, one resume trigger only).
- `memory.md` — S7.6-T1.5 acceptance entry, S7.6-T2 partial closeout entry, sprint-discipline rule entry, synthetic-fixture philosophy entry.
- `ARCHITECTURE_PLAN.md` — LOAD-BEARING UPDATE block for 2026-05-22 (S7.6 sprint summary + tripwire discipline + Sprint 9 plumbing-deferral clarification + B-5 supplements scope reaffirmed).
- `agent_outputs/code-refactor-engineer-s7_6-t2_5-deferred-summary.md` — this file.

T2 code surfaces (committed in `b0c9980`, NOT modified by this ticket):

- `src/measurement_builder.py` — observed-effect plumbing for replenishment_due candidates.
- `src/utils.py` — config + helper paths consumed by T2 wiring (NOTE: working tree carries Agent B's uncommitted T7 work in this file; do not touch).
- `src/main.py` — wire-through from candidate to `bayesian_blend`.
- `tests/test_s7_6_t2_replenishment_observed_effect.py` — already committed in `b0c9980`; pins the wiring contract.

## 8. Tests / checks

- Suite (post-T2): **1678 passed, 14 skipped, 4 xfailed, 0 failed** (the 4 xfailed are the long-standing S6-T3.5 slate-pin xfails citing D-S6-4 cohort_n=0; unchanged).
- M0 goldens: byte-identical (no flag flip, no fixture re-pin).
- Beauty + supplements pinned fixtures: sha256 unchanged.
- This deferral commit is documentation-only — no test run required.

## 9. Behavior changes

None. Engine output is byte-identical to pre-S7.6-T2 state on all pinned fixtures. T2 plumbing exists in code but is inert on Beauty fixtures because the upstream D-S6-4 gate suppresses the candidate before the observed-effect wiring is consulted.

## 10. Artifacts added

- `agent_outputs/code-refactor-engineer-s7_6-t2_5-deferred-summary.md` (this file)
- KI-NEW-G `2026-05-22 update` line item
- `memory.md` S7.6-T1.5 acceptance + S7.6-T2 partial-closeout + DS sprint-discipline + synthetic-fixture-philosophy entries
- `ARCHITECTURE_PLAN.md` LOAD-BEARING UPDATE 2026-05-22 block

## 11. Remaining risks

- **Tripwire-discipline drift:** the sprint discipline rule (predict `observed_n > 0` before each T*N* dispatch) is documented here and in `memory.md`, but enforcement depends on each future dispatch brief explicitly including the prediction step. Recommend the implementation-manager include "predict observed_n on Beauty fixture; if zero, plan deferral" as a literal checklist item in every remaining S7.6 T*N* dispatch.
- **Fixture-reshape pressure:** a future agent unfamiliar with the deferral context may propose regenerating the Beauty fixture to manufacture a non-zero `observed_n` for T3 / T4 / T5. Mitigated by the synthetic-fixture-philosophy memory.md entry + the ARCHITECTURE_PLAN amendment, both load-bearing.
- **KI-NEW-G / KI-NEW-H coupling:** activation still depends on real beta data or Phase 9 recalibration; nothing in S7.6 changes that timeline.

## 12. Follow-up work / next milestone dependencies

- Apply the predict-`observed_n`-first discipline to S7.6-T3 / T4 / T5 dispatch briefs.
- When Beauty clears D-S6-4 (real beta or Phase 9), execute the deferred T2.5 (single atomic flag flip + re-pin) — no new code required.
- Do not couple T2.5 to T3 / T4 / T5; they are independent observed-effect wirings on different builders.

---

**Attribution:** DS-architect lock by ecommerce-ds-architect 2026-05-22. Path (c) selected after rejecting Path (a) (fixture reshape) and Path (b) (premature D-S6-4 recalibration).

## Backfill from memory.md (migration trim 2026-05-25)

## S7.6-T2 — `replenishment_due` observed-effect wiring (partial, 2026-05-22)

**Shipped:**
- T2 plumbing landed at `b0c9980` — measurement_builder + main.py
  wire `(observed_k, observed_n)` through to `bayesian_blend` for
  `replenishment_due` candidates. Plumbing structurally correct;
  suite **1678 passed / 14 skipped / 4 xfailed / 0 failed**.

**Load-bearing invariants:**
- T2 plumbing is correct and inert on Beauty under current fixtures —
  D-S6-4 per-SKU N≥30 floor collapses `cohort_n` to 0 on synthetic
  Beauty G-1, suppressing the candidate upstream of the observed-
  effect seam. Wiring activates atomically when Beauty clears the
  floor.

**Caveats / dormant behavior:** T2.5 atomic flip DEFERRED per DS-
architect Path (c) verdict. Resume trigger = Beauty clears D-S6-4
(real beta data OR future S6 reopen / KI-NEW-H Phase 9 recalibration).
Do NOT regenerate the Beauty fixture to manufacture a passing tripwire.

**Schema:** unchanged.
**Suite:** 1678 passed / 14 skipped / 4 xfailed / 0 failed.
**Summary:** [agent_outputs/code-refactor-engineer-s7_6-t2_5-deferred-summary.md](agent_outputs/code-refactor-engineer-s7_6-t2_5-deferred-summary.md)
