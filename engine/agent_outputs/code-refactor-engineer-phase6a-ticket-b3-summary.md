# Code Refactor Engineer — Phase 6A Ticket B3 Summary

_Date: 2026-05-05_
_Branch: `engine-rework`_
_Baseline commit: `d48c9bc` (post-B1 + B1.5; B2 was test-only)_
_Scope: Phase 6A Ticket B3 ONLY from `agent_outputs/implementation-manager-campaign-slate-plan.md`._

## Approved Scope

Extend the ABSTAIN_SOFT contract so that, in addition to forcing
`engine_run.recommended_experiments=[]` (Ticket A4), any
experiment-eligible candidates that would have qualified under PUBLISH
are routed to `engine_run.considered` with
`ReasonCode.TARGETING_HELD_UNDER_ABSTAIN`. Reuse the existing Fix 3
templates for `reason_text` and `would_fire_if`. De-duplicate against
both the regular Fix 3 head-routing path and any pre-existing
considered entries.

Out of scope: PUBLISH behavior, eligibility rules, renderer copy,
priors metadata, materiality floors, `revenue_range` suppression,
legacy renderer, ABSTAIN_HARD memo path, goldens.

## Patch Summary

1. **`src/decide.py`** — two surgical edits, both additive:
   - Added `publish_shadow: bool = False` parameter to
     `_select_recommended_experiments(...)`. When `True`, bypasses the
     ABSTAIN short-circuit (rule 2) so the helper returns the
     would-have-qualified candidates under PUBLISH semantics. The
     `flag_on` short-circuit (rule 1) is preserved, so the new B3
     routing remains a no-op under `ENGINE_V2_SLATE=false`.
   - Inside the ABSTAIN_SOFT branch of `decide()`, after the existing
     Fix 3 head-routing loop, added a B3 block that:
     a. Runs the selector with `publish_shadow=True` to get the
        experiment-eligible candidate set.
     b. Builds an `already_routed` set from
        `engine_run.considered` (pre-existing) plus the regular Fix 3
        `held_rejections` (head-routed).
     c. Iterates the shadow output and appends a new
        `RejectedPlay(play_id=..., reason_code=TARGETING_HELD_UNDER_ABSTAIN, ...)`
        for any play_id not already in `already_routed`. Reuses
        `_CONSIDERED_REASON_TEXT[TARGETING_HELD_UNDER_ABSTAIN]` and
        `_WOULD_FIRE_IF_TEMPLATE[TARGETING_HELD_UNDER_ABSTAIN]`
        verbatim.
     d. The newly-appended entries flow through the existing
        `assemble_considered(...)` pipeline alongside the regular Fix 3
        rejections, preserving the existing dedupe-on-play_id behavior
        and the `MAX_CONSIDERED_RENDERED` cap.
   - The returned EngineRun under ABSTAIN_SOFT continues to set
     `recommended_experiments=[]`. The list semantics are unchanged;
     only `considered` gains the new typed entries.

2. **`tests/test_abstain_soft_no_experiments.py` (NEW)** — 14 tests
   pinning the B3 contract:
   - 2 acceptance tests on the existing `recommended_experiments=[]`
     and "no rendered section" invariants under ABSTAIN_SOFT.
   - 5 new red-first tests on the held-card routing, the typed reason
     code, populated `reason_text`, populated `would_fire_if`, and
     literal equality with the Fix 3 templates.
   - 2 dedupe tests covering pre-existing-considered overlap and
     regular-Fix-3-head overlap.
   - 2 PUBLISH negative controls (regression).
   - 1 ABSTAIN_HARD negative control (no contamination of the memo
     path).
   - 1 flag-off invariant (`ENGINE_V2_SLATE=false` keeps the routing a
     no-op).
   - 1 end-to-end render smoke test confirming the held experiment
     plays surface in the rendered Considered section under
     ABSTAIN_SOFT with `data-reason-code="targeting_held_under_abstain"`.

No other files were modified. No `src/storytelling.py`, no
`src/storytelling_v2.py`, no `src/main.py`, no `src/engine_run.py`, no
`src/utils.py`, no `config/priors.yaml`, no `src/priors_loader.py`, no
goldens, no fixtures.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py`
  - Added `publish_shadow: bool = False` parameter to
    `_select_recommended_experiments(...)` (line ~985).
  - Updated docstring with the publish_shadow contract (Phase 6A
    Ticket B3).
  - Refactored the abstain short-circuit to honor publish_shadow
    (rule 2 only; rule 1 / `flag_on` preserved).
  - Inside `decide()` ABSTAIN_SOFT branch (line ~1318), added the
    experiment-side held-card routing block after the regular Fix 3
    head loop, reusing `_CONSIDERED_REASON_TEXT` and
    `_WOULD_FIRE_IF_TEMPLATE` for `TARGETING_HELD_UNDER_ABSTAIN`.

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_abstain_soft_no_experiments.py` (NEW)
  - 14 tests across acceptance, routing, dedupe, regression, and
    flag-off invariants. Includes a literal-string assertion against
    the Fix 3 templates so a drift in either side breaks loudly.

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-b3-summary.md` (NEW)
  - This summary.

## How Held Experiment Cards Are Routed To Considered

Function: `decide()` in `src/decide.py`.

Code path (under `state == DecisionState.ABSTAIN_SOFT`):

```python
# 1. Existing Fix 3 head-routing loop builds held_rejections from `head`.
held_rejections = [...]

# 2. NEW (Ticket B3): publish-shadow call to get experiment-eligible set.
already_routed = (
    {str(r.play_id) for r in (engine_run.considered or [])}
    | {str(r.play_id) for r in held_rejections}
)
experiment_shadow = _select_recommended_experiments(
    candidates,
    recommendations=head,
    flag_on=flag_on,
    decision_state=state,
    vertical=str(vertical) if vertical else None,
    aligned=aligned,
    publish_shadow=True,  # bypass rule-2 abstain short-circuit
)

# 3. Append a RejectedPlay for each non-duplicate shadow card.
for shadow_card in experiment_shadow:
    pid = str(shadow_card.play_id)
    if pid in already_routed:
        continue
    already_routed.add(pid)
    held_rejections.append(
        RejectedPlay(
            play_id=pid,
            reason_code=ReasonCode.TARGETING_HELD_UNDER_ABSTAIN,
            reason_text=_CONSIDERED_REASON_TEXT[ReasonCode.TARGETING_HELD_UNDER_ABSTAIN],
            evidence_snapshot=None,
            would_fire_if=_WOULD_FIRE_IF_TEMPLATE[ReasonCode.TARGETING_HELD_UNDER_ABSTAIN],
        )
    )

# 4. Existing Fix 3 assemble_considered() flow continues unchanged.
considered_in = list(engine_run.considered or []) + held_rejections
considered = assemble_considered(considered_in, cap_exceeded=tail, ...)
```

Dedupe key: `str(play_id)`. Scope: a single `decide()` call. The
`already_routed` set covers pre-existing considered entries AND the
regular Fix 3 head-routing list. The downstream
`assemble_considered(...)` already calls `_dedupe_rejections(...)` which
keeps the first entry per play_id; the explicit dedupe in B3 is a
forcing function so no duplicate entries are even constructed in
memory.

Reason code (exact `ReasonCode` enum value):
`ReasonCode.TARGETING_HELD_UNDER_ABSTAIN` — same as the regular Fix 3
path. Serialized form is `"targeting_held_under_abstain"`.

`reason_text` template (verbatim from Fix 3):
`_CONSIDERED_REASON_TEXT[TARGETING_HELD_UNDER_ABSTAIN]` =
`"Held this month because no measured or directional play cleared evidence requirements; targeting plays do not publish on their own."`

`would_fire_if` template (verbatim from Fix 3):
`_WOULD_FIRE_IF_TEMPLATE[TARGETING_HELD_UNDER_ABSTAIN]` =
`"Would fire when at least one measured or directional play clears evidence and materiality this run."`

Pinned with literal equality in
`tests/test_abstain_soft_no_experiments.py::test_abstain_soft_experiment_held_reuses_fix3_template_strings`.

## Selector Refactor

Selector signature post-B3:

```python
def _select_recommended_experiments(
    candidates: Iterable[Any],
    *,
    recommendations: Iterable[PlayCard],
    flag_on: bool,
    decision_state: DecisionState,
    vertical: Optional[str],
    metadata_lookup=None,
    aligned: Optional[Mapping[str, Any]] = None,
    publish_shadow: bool = False,    # NEW
) -> List[PlayCard]
```

Behavior:
- `publish_shadow=False` (default): identical to the post-A4/B1.5
  contract. ABSTAIN_SOFT/HARD short-circuit to `[]`. Used by the
  PUBLISH branch of `decide()`.
- `publish_shadow=True`: the abstain short-circuit (rule 2) is
  bypassed. The `flag_on` short-circuit (rule 1) is preserved, so the
  function still returns `[]` when `ENGINE_V2_SLATE=false`. All other
  eligibility rules (allowlist, metadata, audience floor, vertical,
  inventory, overlap, archetype diversity, hard cap) are unchanged.
  Used by the ABSTAIN_SOFT branch of `decide()` to compute the
  would-have-qualified candidate set.

Eligibility rules are NOT relaxed under publish_shadow. The
candidate-shape contract is unchanged: each shadow card carries the
same `evidence_class=TARGETING`, `revenue_range.suppressed=True`,
`would_be_measured_by`, audience, and (when available)
`opportunity_context` as a real published experiment card. Only the
abstain gate is bypassed.

The shadow `PlayCard` instances themselves are NOT used as PlayCards
on the EngineRun output — only their `play_id` is read to build the
`RejectedPlay` entries. This keeps the role-uniqueness invariant
intact: an experiment play_id can appear as either a Recommended
Experiment card OR a Considered entry, never both, in any single run.

## Duplicate-Prevention Behavior

Three layers of dedupe protection:

1. **In-block dedupe (B3-introduced):** `already_routed` set inside
   `decide()` ABSTAIN_SOFT branch, seeded with both
   `engine_run.considered` play_ids and the regular Fix 3
   `held_rejections` play_ids, blocks duplicate construction.
2. **Existing assemble_considered dedupe (Fix 3-era):**
   `assemble_considered(...)` calls `_dedupe_rejections(...)` which
   keeps the first `RejectedPlay` per play_id even if two enter the
   pipeline.
3. **Renderer dedupe (storytelling_v2):** the renderer's Considered
   section iterates the deduplicated list emitted by
   `assemble_considered`, so the rendered DOM cannot show the same
   play_id twice.

Scope: one `decide()` call (one EngineRun). Cross-run dedupe is not in
scope (recently-run-fatigue is a separate Phase 6B+ concern).

Dedupe key: `str(play_id)`. Tested in
`test_abstain_soft_no_duplicate_considered_entries` (pre-existing
considered overlap) and
`test_abstain_soft_dedupes_with_regular_fix3_held_card` (regular Fix 3
head overlap).

## PUBLISH Before/After (Regression Confirmation)

Before B3:
- `recommended_experiments` populated by selector with default args
  (publish_shadow=False, decision_state=PUBLISH).
- `considered` does NOT carry experiment-side
  `TARGETING_HELD_UNDER_ABSTAIN` entries.

After B3:
- Selector call from PUBLISH branch is unchanged (no `publish_shadow`
  kwarg passed, so it defaults to `False`). Behavior is byte-identical.
- `considered` does NOT carry experiment-side
  `TARGETING_HELD_UNDER_ABSTAIN` entries (the new B3 block lives
  inside the ABSTAIN_SOFT branch and never executes under PUBLISH).

Pinned with two regression tests:
- `test_publish_path_still_renders_recommended_experiment_cards`:
  asserts both allowlisted plays still surface in
  `recommended_experiments` under PUBLISH.
- `test_publish_path_does_not_route_experiments_to_considered`:
  asserts no allowlisted play_id appears in `considered` with
  `TARGETING_HELD_UNDER_ABSTAIN` under PUBLISH.

The existing eligibility test
`tests/test_recommended_experiment_eligibility.py::test_selects_allowlisted_targeting_candidates_when_flag_on`
also passes unchanged, confirming the selector's PUBLISH path is
intact at the unit level.

## ABSTAIN_HARD Behavior (Unchanged)

The ABSTAIN_HARD branch in `decide()` is untouched. It continues to:
- set `recommendations=[]`,
- set `recommended_experiments=[]`,
- route the head into `considered` with `DATA_QUALITY_FLAG`
  (synthesized) or pre-existing reason codes,
- never emit `TARGETING_HELD_UNDER_ABSTAIN` (that code is
  ABSTAIN_SOFT-specific by design).

Pinned with
`test_abstain_hard_recommended_experiments_remains_empty_no_routing`.

## Flag-Off Behavior (Kill Switch)

When `ENGINE_V2_SLATE=false` (default), the publish-shadow call inside
the ABSTAIN_SOFT branch returns `[]` because rule 1 (`flag_on`) is
preserved through publish_shadow. No experiment-side routing occurs.

This means:
- A merchant on the default flag set sees byte-identical ABSTAIN_SOFT
  Considered behavior to the post-Fix-3 baseline.
- Goldens are unaffected.
- The kill switch fully reverts the new routing.

Pinned with
`test_flag_off_does_not_route_experiments_to_considered_under_abstain_soft`.

## Exact Commands Run

```bash
# Red-first capture (BEFORE the routing change)
python -m pytest tests/test_abstain_soft_no_experiments.py -v
# -> 8 passed, 6 failed
#    Failures: routing-to-considered, typed reason code, reason_text,
#    would_fire_if, literal Fix 3 template equality, render-side smoke.

# Green (AFTER the routing change)
python -m pytest tests/test_abstain_soft_no_experiments.py -v
# -> 14 passed in 0.22s

# Fix 3 regression
python -m pytest tests/test_abstain_soft_no_recommendations.py -v
# -> 11 passed in 0.02s

# B-series regressions (eligibility + renderer + forbidden tokens + goldens)
python -m pytest tests/test_recommended_experiment_eligibility.py \
                 tests/test_render_recommended_experiment.py \
                 tests/test_recommended_experiment_forbidden_tokens.py \
                 tests/test_golden_diff.py -v
# -> 78 passed (22 + 20 + 33 + 3) in 28.19s, 0 re-baselined

# Full suite
python -m pytest tests/ -q
# -> 842 passed, 14 skipped, 0 failed in 118.00s
```

## Tests / Checks Run

| Check | Result | Notes |
|---|---|---|
| `tests/test_abstain_soft_no_experiments.py` (NEW) | **14 passed** | 6 red-first failures captured before the fix |
| `tests/test_abstain_soft_no_recommendations.py` | 11 passed | Fix 3 contract intact |
| `tests/test_recommended_experiment_eligibility.py` | 22 passed | A4 contract intact |
| `tests/test_render_recommended_experiment.py` | 20 passed | B1 renderer contract intact |
| `tests/test_recommended_experiment_forbidden_tokens.py` | 33 passed | B2 forbidden-token sweep intact |
| `tests/test_golden_diff.py` | **3 passed (no re-baseline)** | M0 byte-identical |
| Full suite `pytest tests/ -q` | **842 passed, 14 skipped, 0 failed** | Pre-B3 baseline 828 passed; +14 = exactly the new test file |

## Did The New Tests FAIL Before The Fix?

**Yes — red-first evidence captured.** Before any change to
`src/decide.py`, running
`python -m pytest tests/test_abstain_soft_no_experiments.py -v`
produced this output:

```
tests/test_abstain_soft_no_experiments.py::test_abstain_soft_recommended_experiments_is_empty PASSED
tests/test_abstain_soft_no_experiments.py::test_abstain_soft_renders_zero_recommended_experiment_cards PASSED
tests/test_abstain_soft_no_experiments.py::test_abstain_soft_routes_experiment_eligible_candidates_to_considered FAILED
tests/test_abstain_soft_no_experiments.py::test_abstain_soft_experiment_held_uses_targeting_held_under_abstain_reason FAILED
tests/test_abstain_soft_no_experiments.py::test_abstain_soft_experiment_held_has_populated_reason_text FAILED
tests/test_abstain_soft_no_experiments.py::test_abstain_soft_experiment_held_has_populated_would_fire_if FAILED
tests/test_abstain_soft_no_experiments.py::test_abstain_soft_experiment_held_reuses_fix3_template_strings FAILED
tests/test_abstain_soft_no_experiments.py::test_abstain_soft_no_duplicate_considered_entries PASSED
tests/test_abstain_soft_no_experiments.py::test_abstain_soft_dedupes_with_regular_fix3_held_card PASSED
tests/test_abstain_soft_no_experiments.py::test_publish_path_still_renders_recommended_experiment_cards PASSED
tests/test_abstain_soft_no_experiments.py::test_publish_path_does_not_route_experiments_to_considered PASSED
tests/test_abstain_soft_no_experiments.py::test_abstain_hard_recommended_experiments_remains_empty_no_routing PASSED
tests/test_abstain_soft_no_experiments.py::test_flag_off_does_not_route_experiments_to_considered_under_abstain_soft PASSED
tests/test_abstain_soft_no_experiments.py::test_abstain_soft_rendered_considered_section_includes_held_experiments FAILED
6 failed, 8 passed in 0.10s
```

The 8 passing tests cover invariants already pinned by Tickets A4 and
B1 (recommended_experiments=[] under abstain, renderer omits empty
sections, PUBLISH/HARD/flag-off paths). The 6 failing tests are the
B3-specific routing assertions: held-card routing to Considered, the
typed reason code, populated `reason_text` and `would_fire_if`,
literal equality with the Fix 3 templates, and the end-to-end render
smoke. After the `publish_shadow` parameter and the routing block
landed, all 14 tests passed on first run.

## Goldens

- `tests/test_golden_diff.py` → **3 passed, 0 re-baselined**.
- M0 legacy goldens (`tests/golden/{small_sm, mid_shopify,
  micro_coldstart}/*`): byte-identical.
- The default flag set is `ENGINE_V2_SLATE=false`. The new B3 routing
  is gated on `flag_on=True` through `publish_shadow`, so under default
  flags the routing never activates and observable behavior is
  unchanged.
- V2 receipts (where `recommended_experiments` is serialized) continue
  to carry `recommended_experiments: []` under ABSTAIN_SOFT. The
  Considered list under ABSTAIN_SOFT continues to carry only the
  regular Fix 3 head-routing entries when the flag is off.

## Behavior Changes

Under default flags (`ENGINE_V2_SLATE=false`): no observable change at
any layer. ABSTAIN_SOFT briefings render identical Considered lists
to the post-B2 baseline.

Under `ENGINE_V2_SLATE=true` AND `ENGINE_V2_DECIDE=true`:
- ABSTAIN_SOFT runs that have allowlisted experiment-eligible
  candidates (typically `discount_hygiene` and/or `bestseller_amplify`
  with sufficient audience and the right vertical) now show those
  plays in the Considered section with
  `data-reason-code="targeting_held_under_abstain"`.
- `engine_run.recommended_experiments` remains `[]` under
  ABSTAIN_SOFT (unchanged from A4).
- The rendered briefing.html still omits `section.recommended-experiment`
  under ABSTAIN_SOFT (unchanged from B1).
- The PUBLISH path is byte-identical to the post-B1.5 baseline.
- The ABSTAIN_HARD memo path is byte-identical.

This means: when a merchant has the slate stack enabled but the run
is ABSTAIN_SOFT (e.g., no measured/directional candidate cleared the
bar), they now see the experiment plays explained in Considered with
a typed reason and "would fire if" template, rather than vanishing.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_abstain_soft_no_experiments.py`
  — 14 tests pinning the B3 contract.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-b3-summary.md`
  — this summary.

No new sample HTML / receipts / docs / fixtures. No goldens modified.

## Confirmation A1 + A2 + A3 + A4 + A4.5 + B1 + B1.5 + B2 Behavior Is Intact

- `src/storytelling_v2.py` not modified — B1/B1.5/B2 contracts intact.
- `src/engine_run.py` not modified — A2/A4 schema contracts intact.
- `src/main.py` not modified — A4.5 wiring intact.
- `src/utils.py` not modified — `ENGINE_V2_SLATE` flag default false
  unchanged.
- `config/priors.yaml` not modified — A3 metadata intact.
- `src/priors_loader.py` not modified — A3 loader intact.
- B2 forbidden-token sweep (33 tests) passes unchanged: the new B3
  routing only injects `RejectedPlay` entries with the existing Fix 3
  template strings, which the B2 sweep already allows in the Considered
  section.

## Remaining Risks

1. **publish_shadow leak risk.** A future caller that wires
   `publish_shadow=True` into the PUBLISH branch (or omits
   `decision_state` filtering) could accidentally publish experiment
   cards from an abstain run. Mitigation: the abstain-zero contract on
   the returned EngineRun is enforced inside `decide()` itself
   (`recommended_experiments=[]` is set explicitly on both abstain
   `replace()` calls), not by the selector. The selector remains pure;
   the EngineRun construction is the gating seam.
2. **Selector still pure-ish.** The lazy import of
   `_build_opportunity_context` inside the selector now executes
   under `publish_shadow=True` for ABSTAIN_SOFT runs even though the
   shadow output is discarded after `play_id` extraction. This is a
   negligible perf cost and is structurally consistent with the B1.5
   contract; the alternative (skipping `_build_opportunity_context`
   under publish_shadow) would create a divergent code path that is
   harder to test.
3. **Multiple shadow calls.** A future refactor that calls
   `_select_recommended_experiments(publish_shadow=True)` from
   multiple sites in `decide()` could double-route the same play_id.
   Mitigation: the `already_routed` set is a forcing function inside
   the ABSTAIN_SOFT branch; if a future site is added, it must extend
   the set.
4. **Render-side dedupe delegation.** The new B3 routing relies on
   `assemble_considered(...)` to apply
   `MAX_CONSIDERED_RENDERED=6` and `_dedupe_rejections(...)` after
   appending. A future change to `assemble_considered` that loosens
   either invariant would also affect B3. Test coverage on
   considered cap and dedupe is provided by existing
   `tests/test_decide.py` and the new B3 dedupe tests.
5. **No e2e fixture run.** B3 is unit-level. The Beauty Brand pinned
   slate-regression fixture (Ticket B6) is the planned e2e forcing
   function; it will exercise this routing on real CSV data.
6. **Recently-run-fatigue still a NO-OP.** The selector's
   recently-run-fatigue placeholder still always returns False. When
   `recommended_history.json` becomes non-stub (Phase 6B+), the
   publish-shadow call path will need to honor it identically to the
   PUBLISH path, so the considered-routing list reflects the same
   filter the published list would have.

## Readiness for Phase 6A Ticket B4

**Ready for Ticket B4 (role-uniqueness invariant assertion in `decide`).**

B3 reinforces the role-uniqueness contract by ensuring that under
ABSTAIN_SOFT a held experiment play_id appears in `considered` only,
never in `recommended_experiments` (which is forced to `[]`). Under
PUBLISH the same allowlisted play_id can only appear in
`recommended_experiments`, never in `recommendations` (the selector's
rule 4 already filters this). B4 should add the defensive assertion
at the end of `decide()` covering all three branches (PUBLISH,
ABSTAIN_SOFT, ABSTAIN_HARD).

Clean baseline for B4:
- `recommended_experiments=[]` invariant pinned under both abstain
  branches.
- New B3 routing has its own dedupe layer plus the existing
  `assemble_considered` dedupe.
- Full suite at 842 passed, 14 skipped.
- Goldens byte-identical, no re-baseline.

## Git Status

Per convention, changes are NOT committed. Files left unstaged on top
of the post-d48c9bc working tree:

- 1 modified `src/` file: `decide.py` (publish_shadow parameter +
  ABSTAIN_SOFT branch routing block).
- 1 new test file: `test_abstain_soft_no_experiments.py`.
- 1 new doc file: this summary.

No goldens modified. No `src/storytelling.py` modified. No
`src/storytelling_v2.py` modified. No `src/main.py` modified. No
`src/engine_run.py` modified. No `src/utils.py` modified. No
`config/priors.yaml` modified. No `src/priors_loader.py` modified.
