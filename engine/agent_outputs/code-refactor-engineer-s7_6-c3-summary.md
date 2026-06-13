# S7.6-C3 — T7.5 flag flip + KIs + memory + ARCHITECTURE_PLAN + CLAUDE.md — sprint closes

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `d6053d0`

---

## 1. Ticket scope

Flip `ENGINE_V2_AOV_THRESHOLD_FROM_DATA` ON. AOV bundle threshold now data-derived from L90 P60 on Beauty (computed $71.88). Supplements gated via explicit `vertical_excluded_per_b5_248` per `ARCHITECTURE_PLAN.md` III B-5 lines 248 + 257(c).

Closes Sprint 7.6 (Observed-Effect Wiring sprint). Four commits total comprised the C-series + sprint close:
- `18e33b1` C1: priority_prepend scaffolding on `assemble_considered`
- `bb9fd32` FIX: priority_prepend mirrored to `populate_considered_from_candidates`
- `6d248fd` C2: `apply_guardrails_to_injected` helper (single-demote-channel)
- `d6053d0` C3 (this): T7.5 flip + close-out docs + dependent sha re-pins

Single-demote-channel invariant restored. Tier-B-presence invariant test pins founder criterion in CI: every `_PRIOR_ANCHORED` play with an M3 candidate must appear in `engine_run.recommendations` OR `engine_run.considered`.

## 2. Files changed

- `ARCHITECTURE_PLAN.md` (+12 lines, 2026-05-22 S7.6 close LOAD-BEARING UPDATE).
- `CLAUDE.md` (+17 lines, handoff discipline section locked).
- `KNOWN_ISSUES.md` (+37 lines).
- `memory.md` (+65 lines).
- `src/utils.py` (+1/-1 line, default flag flip).
- `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` (re-pin).
- `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` (re-pin).
- 5 dependent test files updated atomically:
  `tests/test_s6_t1_5_winback_dormant_repin.py`,
  `tests/test_s6_t3_y_audience_floor_sensitivity.py`,
  `tests/test_s6_t3_z_considered_render.py`,
  `tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py`,
  `tests/test_slate_regression_supplements_brand.py`.

## 3. Behavior change

KIs updated / opened:
- **KI-NEW-G:** 2026-05-22 close-out note — T2.5 architectural gap addressed by `bb9fd32` + `6d248fd`; atomic flip itself remains Path (c) deferred.
- **KI-NEW-L:** collapse 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` into a single `_PRIOR_ANCHORED` dispatch.
- **KI-NEW-M:** resolve `_dedupe_rejections` first-wins vs last-wins-typed-code policy at `src/decide.py`.
- **KI-NEW-N:** experiment-promotion provenance-preserve at `src/decide.py:2080-2087`.

Fixture re-pins (5 dependent test files updated atomically):
- Beauty briefing.html sha256: `5afc4d62e9...` -> `1a5a35eb67898e6...`.
- Supplements briefing.html sha256: `0903071ee9...` -> `13a91e6cd3200831...`.
- M0 byte-identical confirmed.

CLAUDE.md handoff discipline section locked in 2026-05-22 (founder-authored): every subagent dispatch reads `ARCHITECTURE_PLAN.md` + `memory.md` + `KNOWN_ISSUES.md` + recent `agent_outputs` before code changes. Never assume. Only follow the path that's decided.

## 4. Tests added / modified

5 dependent test files updated atomically (sha re-pins). Suite: 1690 passed / 14 skipped / 4 xfailed / 2 xpassed (baseline preserved post-flag-flip).

## 5. Risks + mitigations

- **Atomic sprint close.** Flag flip + KIs + memory + ARCHITECTURE_PLAN + CLAUDE.md + fixture re-pins all in one commit per Sprint 2 Risk #4 discipline. Operator override `ENGINE_V2_AOV_THRESHOLD_FROM_DATA=false` rolls back.
- **Founder criterion satisfied:** every S6/S7-wired Tier-B play evaluated honestly on Beauty + Supplements pinned fixtures.

## 6. Follow-ups / known-issues opened

- KI-NEW-G / -L / -M / -N (see above).
- T2.5 atomic flip remains Path (c) deferred.
- **CLI receipt-surface gap** subsequently closed at `d8ede8c` (S7.6-CLI-FIX, separate summary file).

## 7. Commit ref

`d6053d0` — final code commit of S7.6 closeout cluster.

## Backfill from memory.md (migration trim 2026-05-25)

## S7.6-continuation — sprint close (2026-05-23)

**Sprint outcome:** S7.6 continuation closed with all 5 S6/S7-wired Tier-B
plays evaluated honestly on Beauty + Supplements pinned fixtures per the
founder criterion ("I need all my plays evaluated honestly for each
merchant"). 13-commit arc landed: T3/T3.5 (discount_hygiene), T2.5-fix +
T2.5-close (D-S6-4 floor lowered 30 → 10 with per-stage cells, then
RESOLVED-AS-DOCUMENTED-EXPECTED-BEHAVIOR per DS Option iii),
T4/T4.5 (cohort_journey), T5 (aov_bundle wiring), T6/T6.5 (eligibility
gate + 3-state copy ladder + joint-p<0.10 amendment), T5.6 (priority_prepend
generalized across 3 demote channels), T5.5 (aov_bundle flip — joint-fail
demotes honestly via full T5 → T6 → T5.6 pipeline).

**Activated end-to-end (observed-effect blend live):**
- `winback_dormant_cohort` (T1.5, pre-existing — Beauty `observed_n=334`,
  posterior 0.08 → 0.16, store-dominant).
- `discount_dependency_hygiene` (T3.5, commit `21bc273` — Beauty
  `observed_n=148K`, store-dominant, 3/3 window sign-agreement).
- `cohort_journey_first_to_second` (T4.5, commit `2f1c17c` — Beauty
  `observed_n=392`, store-dominant, Berkson-protected via early-half cohort
  window per Phase 4.1 resolution).

**Honestly handled (no synthetic activation):**
- `replenishment_due` (T2.5, RESOLVED-AS-DOCUMENTED-EXPECTED-BEHAVIOR per
  DS escalation verdict 2026-05-23 — Beauty synthetic per-SKU repeat-buyer
  distribution genuinely sits below the defensible N=10 floor; honest
  dormancy IS the product, not a deferral. KI-NEW-G updated.
- `aov_lift_via_threshold_bundle` (T5.5, commit `de01df4` — joint-p
  Welch≈0.876 + z-prop≈0.877 fails the <0.10 amended gate; demotes to
  Considered with truthful `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` reason via
  the full T5 → T6 → T5.6 pipeline; Tier-B-presence invariant holds).

**Architectural invariants restored / extended (load-bearing):**
1. Single-demote-channel (`apply_guardrails_to_injected` helper, commit
   `6d248fd`, S7.6 close 2026-05-22).
2. `priority_prepend` coverage across all 3 demote channels —
   `eligibility_rejects` + `prior_unvalidated_rejects` +
   `window_disagreement_rejects` (commits `bb9fd32` + `8a2d726`, T5.6) —
   restated DS-architect invariant per verdict
   `agent_outputs/ecommerce-ds-architect-t6-priority-prepend-gap-verdict-2026-05-23.md`.
3. T6 eligibility gate with joint-p<0.10 amendment for builders that stash
   `*_band` per-window posteriors (commits `45033dd` + `6d312d3`).
4. Tier-B-presence invariant in CI at
   `tests/test_s7_6_c1_priority_prepend_invariant.py` extended structurally
   by the three-channel coverage.

**Deferred to S8+:** KI-NEW-L (collapse 5 V2 prior-anchored injection
blocks → 1 PRIOR_ANCHORED dispatch), KI-NEW-M (`_dedupe_rejections`
typed-code policy), KI-NEW-N (experiment-promotion provenance-preserve),
KI-NEW-O (truncation-count xfail reasoning stale post-T5.6); Sprint 9
store-profile-as-learned-artifact; Sprint 10-13 ML scoring layer
(`ModelFitStatus` gate). Structural cleanup, not provenance-blocking for
today's slate.

**Key learnings:**
- **Instrumentation-over-prediction.** The T5.5 fixture probe found the
  joint-gate gap via direct trace, not by code reading; three prior
  gate-location predictions in S7.6-T7.5 had each been wrong. CLAUDE.md
  Subagent Handoff Discipline now codifies this.
- **DS-architect self-correcting verdicts.** The T5.6 priority_prepend gap
  was missed twice as a narrow `cap_exceeded` framing before the DS
  architect restated the wider three-channel invariant completely.
- **Synthetic-fixture honesty.** T2.5 RESOLVED-AS-DOCUMENTED-EXPECTED-
  BEHAVIOR is the precedent: don't reshape a fixture to flatter a
  builder; if the fixture honestly lacks the cohort, honest dormancy
  is the product.

**Beta-readiness statement:** the engine satisfies the founder honest-
evaluation criterion empirically on Beauty + Supplements synthetic
fixtures. Real-merchant validation on a small beta cohort is the natural
next step; no further engine work is required to make that step
productive.

**Schema:** unchanged.
**Suite:** 1769 passed baseline preserved across the 13-commit arc; this
sprint-close commit is doc-only (zero code change, M0 + Beauty +
Supplements byte-identical).
**Summary:** in-thread; KNOWN_ISSUES.md KI-NEW-G/L/O updated;
ARCHITECTURE_PLAN.md 2026-05-23 (S7.6 continuation sprint-close)
LOAD-BEARING UPDATE added.

## S7.6-C3 — Sprint 7.6 closed (2026-05-22)

**Shipped:**
- T7.5 flag flip: ``ENGINE_V2_AOV_THRESHOLD_FROM_DATA`` default OFF -> ON
  in ``src/utils.py``. Activates L90 P60 data-derived threshold path
  in ``aov_lift_via_threshold_bundle_candidates`` and the supplements
  explicit ``vertical_excluded_per_b5_248`` gate (ARCHITECTURE_PLAN.md
  §III B-5 lines 248 + 257(c)).
- Beauty fixture re-pin (sha256 ``5afc4d62...`` -> ``1a5a35eb67898e6e
  eda8196bc588bc8e7c5c4e2198bb4d721bf6b5da76c17f44``). Supplements
  fixture re-pin (sha256 ``0903071e...`` -> ``13a91e6cd3200831fb9c
  17373ad316d961a80c05d75b5e6d749e6b314416d344``). Membership unchanged
  on both; only AOV bundle reason/threshold_source provenance shifts.
- Sprint 7.6 closes with four atomic commits: ``18e33b1`` (C1
  priority_prepend scaffolding), ``bb9fd32`` (FIX: mirror to
  populate_considered_from_candidates), ``6d248fd`` (C2:
  apply_guardrails_to_injected helper), and this C3 commit.

**Load-bearing invariants:**
- Single-demote-channel invariant restored. Every S6/S7-wired Tier-B
  play (``_PRIOR_ANCHORED`` registry at
  ``src/measurement_builder.py:717``) now surfaces honestly in
  ``engine_run.recommendations`` OR ``engine_run.considered`` on
  Beauty + Supplements per the founder criterion locked in CLAUDE.md
  2026-05-22. Tier-B-presence invariant test at
  ``tests/test_s7_6_c1_priority_prepend_invariant.py`` pins this
  contract in CI.
- CLAUDE.md Subagent Handoff Discipline section (founder-authored,
  2026-05-22) is now committed. Every subagent dispatch must read
  ARCHITECTURE_PLAN + memory.md + KNOWN_ISSUES + recent agent_outputs
  before code changes. Never assume. Only follow the path that\047s
  decided.

**Key learnings:**
- Three diagnostic cycles predicted wrong gates for T7.5 (materiality
  bypass, prior-anchored early-return, injection storm). A direct
  in-process probe (agent ``aaa6428f60edf190c``) found the actual
  gate at ``populate_considered_from_candidates`` cap-trim. Discipline
  locked in CLAUDE.md: instrument before fixing.
- DS architect verdicts were correct on mechanism but wrong on gate
  location twice; direct probes superseded predictions.

**Caveats / dormant behavior:** AOV bundle disposition on Beauty under
flag-ON surfaces in Considered with ``cap_exceeded`` (rank 6, kept via
C1 priority_prepend). Threshold-from-data computation succeeded (L90
P60 = $71.88 computed on the synthetic Beauty fixture). Supplements
AOV bundle routes through the explicit ``vertical_excluded_per_b5_248``
seam at ``audience_builders.py:969-979``.

**Deferred to S8:** KI-NEW-L (collapse 5 V2 prior-anchored injection
blocks at ``src/main.py:1380-1597`` -> 1 PRIOR_ANCHORED dispatch);
KI-NEW-M (``_dedupe_rejections`` first-wins-vs-last-wins-typed-code
policy); KI-NEW-N (experiment-promotion provenance-preserve at
``src/decide.py:2080-2087``). Structural cleanup, not provenance-blocking.

**Founder criterion (verbatim):** "I need all my plays evaluated
honestly for each merchant." Satisfied empirically on Beauty +
Supplements pinned fixtures.

**Schema:** unchanged.
**Suite:** 1690 passed / 14 skipped / 4 xfailed / 2 xpassed (baseline
preserved post-flag-flip after sha + flag-default test updates).
**Summary:** in-thread; KNOWN_ISSUES.md KI-NEW-G/L/M/N updated;
ARCHITECTURE_PLAN.md 2026-05-22 (S7.6 close) LOAD-BEARING UPDATE added.

## S7.6 — Synthetic-fixture philosophy (load-bearing, 2026-05-22)

**Rule:** synthetic Beauty / Supplements fixtures = plausible
merchant shape, NOT branch coverage. Branch coverage belongs in
isolated unit tests.

**Why this is load-bearing:** pinned fixtures are read by downstream
agents as economic ground truth — "this is what a merchant looks
like." Reshaping a fixture to fire a specific builder injects a
false claim into the artifact every other agent reads. The 42-cell
floor-resolver test and 8-cell surface-field test are the right
home for `replenishment_due` branch coverage; the Beauty G-1 fixture
is the wrong home.

**How to apply:** when an agent proposes "regenerate fixture to fire
builder X," push back unless the regeneration reflects a real
merchant shape we expect in beta. T2.5 (b0c9980) is the precedent:
DS-architect rejected the fixture-reshape path explicitly.

- 2026-05-23: T2.5 RESOLVED-AS-DOCUMENTED-EXPECTED-BEHAVIOR per DS
  escalation verdict (`agent_outputs/ecommerce-ds-architect-t2_5-
  escalation-verdict-2026-05-23.md`, Option iii accepted). At
  defensible floor N=10 (post-T2.5-fix, commit `506c703`), Beauty
  synthetic fixture's per-SKU repeat-buyer distribution genuinely
  sits below floor (audience_size=0). Honest dormancy is the product,
  not a deferral. Chasing the floor down to the fixture = floor
  accusing the floor. Supplements path independent (audience=235,
  `no_measured_signal` — signal-strength working as intended).
