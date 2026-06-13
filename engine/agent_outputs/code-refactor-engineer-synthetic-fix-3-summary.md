# Code Refactor Engineer — Synthetic Blocker Fix 3 Summary

_Date: 2026-05-04_
_Scope: Fix 3 ONLY from `agent_outputs/implementation-manager-synthetic-blocker-fix-plan.md`._

## Approved Scope

ABSTAIN_SOFT contract enforcement. PM-resolved product contract:

> When `decision_state == abstain_soft`, V2 must render zero cards in
> the Recommended section. Held targeting cards must move to
> Considered with an explicit reason.

Land tests first (TDD), watch them fail on the pre-Fix-3 code path,
then ship the smallest safe fix that:

1. Tightens `MAX_ABSTAIN_SOFT_TARGETING_CARDS` from 2 to 0 in
   `src/storytelling_v2.py`.
2. Routes held targeting cards from `decide()`'s ranked head into
   `engine_run.considered` with a typed
   `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN`, populated `reason_text`,
   and populated `would_fire_if`.
3. Sets `engine_run.recommendations = []` under ABSTAIN_SOFT.

Strict Non-Goals (not touched in this pass):

- Fix 4 / Fix 5 / Fix 6 / Fix 7.
- Inventory logic.
- Materiality floors.
- New recommendation tiers.
- Opportunity-context changes.
- Lifecycle memory.
- Fake stats.
- Re-baselining goldens.

## Patch Summary

The pre-Fix-3 `decide()` ABSTAIN_SOFT branch deliberately kept up to
3 targeting cards in `engine_run.recommendations[]` so the renderer
in M8 could mark them as suppressed targeting cards. The renderer
then capped at 2 via `MAX_ABSTAIN_SOFT_TARGETING_CARDS`. PM resolved
the contract: zero cards in Recommended under ABSTAIN_SOFT.

The fix is two-sided:

- **Engine side** (`src/decide.py`): Under ABSTAIN_SOFT, build
  `RejectedPlay` records for every PlayCard in the ranked head,
  carrying the new typed reason code, merchant-readable reason
  text, and a would_fire_if template. Append them to
  `engine_run.considered` (the existing `assemble_considered`
  pipeline dedupes against earlier entries so an upstream M3
  rejection for the same play_id wins). Set
  `engine_run.recommendations = []`.
- **Renderer side** (`src/storytelling_v2.py`): Tighten
  `MAX_ABSTAIN_SOFT_TARGETING_CARDS` from 2 to 0 as a second line
  of defense — even if a future code path wires the renderer with
  cards still in `recommendations[]` under ABSTAIN_SOFT, the
  renderer drops every targeting card.
- **Schema side** (`src/engine_run.py`): Add
  `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN = "targeting_held_under_abstain"`.
  Choosing a new reason code (instead of reusing `NO_MEASURED_SIGNAL`)
  keeps semantics clean: `NO_MEASURED_SIGNAL` is the upstream M3
  candidate condition, `TARGETING_HELD_UNDER_ABSTAIN` is the
  decide-state transition. Both PM and DS accepted either; the
  separate code lets the considered list distinguish "we never had
  enough signal" from "the engine ranked this into the head but
  ABSTAIN_SOFT held it".

The Phase 5.1 merchant-readable callout copy ("No primary play this
month." + the dominant-gate reason text) is preserved verbatim.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` —
  added `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN` enum value with
  documenting comment.
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` —
  added entries in `_WOULD_FIRE_IF_TEMPLATE` and
  `_CONSIDERED_REASON_TEXT` for the new code; split the PUBLISH /
  ABSTAIN_SOFT branch in `decide()`; under ABSTAIN_SOFT, route the
  ranked head into `considered` with the new reason code and clear
  `recommendations = []`. Updated module-level and `decide()`
  docstrings.
- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling_v2.py`
  — tightened `MAX_ABSTAIN_SOFT_TARGETING_CARDS` from 2 to 0 with a
  Fix-3-anchored docstring; updated module-level docstring to
  document the new contract.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_abstain_soft_no_recommendations.py`
  — NEW. 11 tests landed BEFORE the fix per TDD. 5 fail pre-fix
  (require the new code path to exist), 6 pass pre-fix (negative
  controls / unchanged paths).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_decide.py`
  — updated 2 tests whose intent is now contradicted by the
  tightened contract:
  - `test_targeting_only_yields_abstain_soft` now asserts
    `recommendations == []` and verifies the held targeting cards
    appear in `considered` with the new reason code.
  - `test_abstain_soft_with_only_targeting_e2e` updated identically.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_render_v2.py`
  — renamed `test_abstain_soft_caps_targeting_cards_at_two` to
  `test_abstain_soft_renders_zero_targeting_cards`; the assertion
  is now `target_count == 0` instead of `<= 2`. Phase 5.1 callout
  presence assertion added.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_engine_run_schema.py`
  — `test_all_reason_codes_declared` now expects 13 codes (was 12)
  including the new `targeting_held_under_abstain`.

No other files touched. Specifically NOT modified: `engine_run_adapter.py`,
`measurement_builder.py`, `evidence.py`, `guardrails.py`, `sizing.py`,
`storytelling.py` (legacy renderer), `briefing.py`, `main.py`,
`charts.py`, the M3 Candidate contract, the M5 / M6 V2 blocks, the
materiality floors, or the M0 goldens.

## Exact Commands Run

```
# Pre-fix baseline
python -m pytest tests/ -q                                                    # 589 passed, 12 skipped
# Land new test file BEFORE fix (TDD)
python -m pytest tests/test_abstain_soft_no_recommendations.py -v             # 5 failed, 6 passed (expected)
# Apply fix to engine_run.py / decide.py / storytelling_v2.py
python -m pytest tests/test_abstain_soft_no_recommendations.py -v             # 11 passed
# Update tests whose old contract assertion is now contradicted
python -m pytest tests/test_render_v2.py tests/test_decide.py \
  tests/test_phase5_measured_pathway.py tests/test_phase5_abstain_copy.py \
  tests/test_phase5_no_aura_beacon.py tests/test_phase5_considered_always.py \
  tests/test_phase5_materiality_copy.py tests/test_targeting_no_dollar_headline.py \
  tests/test_abstain_soft_no_recommendations.py \
  tests/test_targeting_measurement_invariant.py                               # 121 passed, 1 skipped
# Repair test_engine_run_schema enum-completeness assertion (13 codes now)
python -m pytest tests/test_engine_run_schema.py                              # all green
# Golden diff
python -m pytest tests/test_golden_diff.py -v                                 # 3 passed
# Forbidden-string suite
python -m pytest tests/test_targeting_no_dollar_headline.py \
  tests/test_internal_stats_not_rendered.py tests/test_phase5_no_aura_beacon.py # 20 passed total
# Full suite
python -m pytest tests/ -q                                                    # 600 passed, 12 skipped
# E2E smoke runs
mkdir -p /tmp/fix3_promo_anomaly /tmp/fix3_small_sm
ENGINE_V2_DECIDE=true ENGINE_V2_OUTPUT=true ENGINE_V2_SHADOW=true ENGINE_V2_SIZING=true \
  STATS_NAN_FOR_HARDCODED=true EVIDENCE_CLASS_ENFORCED=true ANOMALY_GATE_ENABLED=true \
  GUARDRAIL_INVENTORY_ENABLED=true GUARDRAIL_OVERLAP_ENABLED=true \
  GUARDRAIL_MATERIALITY_ENABLED=true python -m src.main \
  --orders tests/fixtures/synthetic/promo_anomaly_240d_orders.csv \
  --brand promo_anomaly --out /tmp/fix3_promo_anomaly
ENGINE_V2_DECIDE=true ENGINE_V2_OUTPUT=true STATS_NAN_FOR_HARDCODED=true \
  EVIDENCE_CLASS_ENFORCED=true python -m src.main \
  --orders data/SM_orders.csv --brand small_sm --out /tmp/fix3_small_sm
```

## Tests / Checks Run

| Check | Result |
|---|---|
| `tests/test_abstain_soft_no_recommendations.py` (NEW) — pre-fix | 5 FAILED (as designed), 6 passed |
| `tests/test_abstain_soft_no_recommendations.py` (NEW) — post-fix | 11 passed |
| `tests/test_decide.py` (updated) | All passing |
| `tests/test_render_v2.py` (updated) | All passing |
| `tests/test_engine_run_schema.py` (updated for enum count) | All passing |
| `tests/test_targeting_no_dollar_headline.py` | 6 passed |
| `tests/test_internal_stats_not_rendered.py` | passed |
| `tests/test_phase5_no_aura_beacon.py` | 4 passed (PUBLISH / ABSTAIN_SOFT / ABSTAIN_HARD forbidden-token sweep) |
| `tests/test_phase5_abstain_copy.py` | 8 passed (Phase 5.1 callout copy preserved) |
| `tests/test_phase5_considered_always.py` | 10 passed |
| `tests/test_targeting_measurement_invariant.py` (Fix 2) | 6 passed, 1 skipped |
| `tests/test_golden_diff.py` | 3 passed (no re-baseline) |
| Full suite `pytest tests/` | **600 passed, 12 skipped, 0 failed** |
| E2E V2-stack smoke run on `promo_anomaly_240d` | Briefing produced; 0 Recommended cards; 6 Considered cards; ABSTAIN_SOFT callout intact |
| E2E V2-stack smoke run on `data/SM_orders.csv` | Briefing produced; 0 Recommended cards; 6 Considered cards; ABSTAIN_SOFT callout intact |

Pre-fix baseline was 589 passed + 12 skipped (post-Fix-2). Post-fix
is 600 passed + 12 skipped — exactly the 11 new tests this PR
added, with no previously-passing test moving and no skip count
delta.

## Did The New Test FAIL Before The Fix?

Yes. Captured pre-fix failure summary from
`tests/test_abstain_soft_no_recommendations.py`:

```
FAILED tests/test_abstain_soft_no_recommendations.py::test_targeting_held_under_abstain_reason_code_exists
FAILED tests/test_abstain_soft_no_recommendations.py::test_targeting_only_decide_clears_recommendations
FAILED tests/test_abstain_soft_no_recommendations.py::test_held_targeting_cards_routed_to_considered_with_typed_reason
FAILED tests/test_abstain_soft_no_recommendations.py::test_render_abstain_soft_after_decide_has_zero_recommended_cards
FAILED tests/test_abstain_soft_no_recommendations.py::test_render_abstain_soft_with_existing_considered_does_not_drop_them
========================= 5 failed, 6 passed in 0.05s ==========================
```

Specific load-bearing pre-fix failures and what they would have
caught:

1. `test_targeting_held_under_abstain_reason_code_exists` —
   `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN` did not exist on the
   enum. Pins the schema contract programmatically so the typed
   reason code cannot regress to a magic string.
2. `test_targeting_only_decide_clears_recommendations` —
   `decide()` left the targeting cards in `recommendations[]`. The
   assertion `out.recommendations == []` failed with the actual
   list of 2 PlayCards. This is the canonical PM contract
   violation.
3. `test_held_targeting_cards_routed_to_considered_with_typed_reason` —
   the held cards were not in `considered`, the new reason code
   did not exist, and `would_fire_if` / `reason_text` were not
   populated for the held set. All three failed.
4. `test_render_abstain_soft_after_decide_has_zero_recommended_cards` —
   the rendered HTML still contained `<article
   class="play-card play-card--targeting"
   data-play-id="t1"...>` under the Recommended section, which is
   the page-contradicts-itself defect PM described on
   `promo_anomaly_240d`.
5. `test_render_abstain_soft_with_existing_considered_does_not_drop_them` —
   without the routing change, the targeting cards were still in
   `recommendations` (assertion `out.recommendations == []`
   failed); the test also pins that pre-existing `considered`
   entries are not evicted by Fix 3 routing.

The 6 passing tests pre-fix were the negative controls
(PUBLISH path unchanged, ABSTAIN_HARD path unchanged, Phase 5.1
copy preserved when no targeting cards are present). They confirm
Fix 3 does not over-fire onto unrelated paths.

## How Held Targeting Cards Move To Considered (Data Flow)

End-to-end flow for the unit-test case (legacy adapter pushes
targeting cards into `recommendations[]`, decide() then fires
ABSTAIN_SOFT):

```
EngineRun input
  recommendations = [tc1: TARGETING, tc2: TARGETING]   # from legacy adapter
  considered      = [...M3 rejections, M5 rejections...]
  abstain         = Abstain(state=PUBLISH)             # default

  ↓  decide(engine_run)

# Step 1: rank_recommendations() — class-aware sort
# Step 2: head = ranked[:3]; tail = ranked[3:]
# Step 3: _decide_abstain_state(head, ...)
#   no measured/directional in head ⇒ ABSTAIN_SOFT

# Step 4 (NEW Fix 3 branch in decide()):
held_rejections = [
    RejectedPlay(
        play_id              = card.play_id,
        reason_code          = ReasonCode.TARGETING_HELD_UNDER_ABSTAIN,
        reason_text          = _CONSIDERED_REASON_TEXT[…]
                               = "Held this month because no measured or
                                  directional play cleared evidence
                                  requirements; targeting plays do not
                                  publish on their own.",
        evidence_snapshot    = None,
        would_fire_if        = _WOULD_FIRE_IF_TEMPLATE[…]
                               = "Would fire when at least one measured
                                  or directional play clears evidence
                                  and materiality this run.",
    )
    for card in head
]

# Step 5: assemble_considered(
#   pre_existing = engine_run.considered + held_rejections,
#   cap_exceeded = tail,
#   ...
# )
#   _dedupe_rejections() keeps the FIRST entry per play_id, so an
#   upstream M3 / M5 rejection for the same play_id wins over the
#   newly-added Fix 3 entry. (Considered list is then capped at 6.)

# Step 6: return replace(engine_run, recommendations=[],
#                                    considered=…,
#                                    abstain=Abstain(SOFT, reason),
#                                    watching=…)

EngineRun output
  recommendations = []                                 # PM contract
  considered      = [...pre-existing..., tc1, tc2]    # held cards routed here
  abstain         = Abstain(SOFT, "<merchant-readable Phase 5.1 reason>")
```

The renderer (`src/storytelling_v2.py`) is the second line of
defense. Even if a future caller wires the renderer with cards
still in `recommendations[]` under ABSTAIN_SOFT,
`MAX_ABSTAIN_SOFT_TARGETING_CARDS = 0` slices the list to zero
inside `render_recommended_section()` before rendering. The
"No targeting plays met audience-floor and overlap rules this
run." empty-state copy then renders below the Phase 5.1 callout.

Fields populated on every routed `RejectedPlay`:

- `play_id` — copied from the held PlayCard.
- `reason_code` — `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN`.
- `reason_text` — typed, merchant-readable, Phase 5.2 style copy.
- `evidence_snapshot` — `None`. The card's audience snapshot is
  an upstream concern (M3 candidate path / opportunity context);
  we deliberately do not synthesize one here to avoid duplicating
  evidence already on the EngineRun.
- `would_fire_if` — template-only, no LLM, no storytelling layer.

## Reason Code Used (Existing Or Newly Added; Justification)

**Newly added: `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN = "targeting_held_under_abstain"`.**

PM doc (line 67) and the IM plan (line 145) both accept either
"a new code such as `targeting_held_under_abstain`" or "reusing
`NO_MEASURED_SIGNAL`". I picked the explicit new code because:

1. **Different semantics.** `NO_MEASURED_SIGNAL` is already used
   by `populate_considered_from_candidates` (Phase 5.2) for M3
   candidates that exist but have no calibrated lift to size
   with. `TARGETING_HELD_UNDER_ABSTAIN` is a decide-state
   transition: the engine *did* rank the candidate into the head,
   but ABSTAIN_SOFT held the publish. Conflating the two would
   make the considered list less explainable.
2. **Programmatic test surface.** Tests assert
   `hasattr(ReasonCode, 'TARGETING_HELD_UNDER_ABSTAIN')` so the
   contract is enforced at the schema level, not via magic
   strings.
3. **Plumbing parity with the rest of the pipeline.** The
   `_WOULD_FIRE_IF_TEMPLATE` and `_CONSIDERED_REASON_TEXT` maps
   are keyed by `ReasonCode`. Adding the entry once means every
   downstream renderer (HTML, debug, future Klaviyo agent) can
   look up the string without a special case.
4. **Test count delta is minimal.** Adding the enum cost one
   one-line update in `test_engine_run_schema.py` (the
   completeness test). No other test needed updating to be aware
   of the new code.

The new value is keyed lowercase `"targeting_held_under_abstain"`
matching PM doc verbatim. `data-reason-code="targeting_held_under_abstain"`
appears on rendered considered cards via the existing
`render_rejected_card` path (no renderer changes were needed for
the data-attribute).

## promo_anomaly Before / After Behavior

The synthetic Phase 5 e2e review reported:

> `promo_anomaly_240d` renders ABSTAIN_SOFT alongside 2 Targeting
> cards in Recommended.

V2-stack end-to-end run on `tests/fixtures/synthetic/promo_anomaly_240d_orders.csv`
after Fix 3:

```
decision_state: abstain_soft
recommendations count: 0
considered count: 6
considered reason_codes:
  winback_21_45        → no_measured_signal
  bestseller_amplify   → no_measured_signal
  discount_hygiene     → no_measured_signal
  subscription_nudge   → audience_too_small
  routine_builder      → no_measured_signal
  empty_bottle         → no_measured_signal
```

Rendered briefing.html on `promo_anomaly_240d`:

- `<article class="play-card play-card--targeting"` count: **0**.
- `<article class="play-card play-card--rejected"` count: 6.
- "No primary play this month." callout: present.
- ABSTAIN_SOFT-style empty-state ("No targeting plays met audience-floor
  and overlap rules this run."): present.

This run did not exercise the new decide() head-routing path
because the V2 candidate pipeline (M3 Phase 5.2) populated
considered upstream — the head was empty by the time decide()
ran. That is the modern V2 path. The Fix 3 routing is a safety
net for the legacy adapter case where targeting cards reach
`recommendations[]`, which is captured by the unit tests (the
TDD failures pre-fix showed the routing path was missing).

`small_sm` ran identically: 0 Recommended cards, 6 Considered
cards, ABSTAIN_SOFT callout intact, no targeting card articles
rendered.

## Goldens

`tests/test_golden_diff.py`: 3 fixtures (`small_sm`,
`mid_shopify`, `micro_coldstart`) all pass byte-for-byte against
the pinned golden tree. No file under `tests/golden/` was
modified. No `--baseline` / `--regenerate` invocation was used.

The legacy renderer is the canonical path for the goldens, and
none of the changed files (`engine_run.py` enum addition,
`decide.py` ABSTAIN_SOFT routing, `storytelling_v2.py`
`MAX_ABSTAIN_SOFT_TARGETING_CARDS`) affect the legacy
`actions_log` / `briefing.html` path. The legacy renderer
(`src/storytelling.py`) is untouched.

## Behavior Changes

- Under ABSTAIN_SOFT, `EngineRun.recommendations[]` is empty on
  every `decide()` call. Held targeting cards are re-routed into
  `EngineRun.considered` with
  `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN`, populated
  `reason_text`, and populated `would_fire_if`.
- Under ABSTAIN_SOFT, the V2 renderer renders zero PlayCard
  articles in the Recommended section; only the Phase 5.1 callout
  + the empty-state copy renders under the Recommended heading.
- Under ABSTAIN_HARD: behavior unchanged. Recommendations remain
  empty; the head is moved into considered with
  `DATA_QUALITY_FLAG` (or pre-existing M5 anomaly reasons),
  exactly as before.
- Under PUBLISH: behavior unchanged. Targeting cards continue to
  render in Recommended alongside measured / directional cards.
- Phase 5.1 ABSTAIN_SOFT callout copy: unchanged. The
  `abstain.reason` text is still selected from
  `ABSTAIN_SOFT_REASONS` based on the dominant gate, falling back
  to `ABSTAIN_SOFT_DEFAULT_REASON`. The label "No primary play
  this month." continues to render.
- Default-flags-off path on the M0 goldens: byte-identical.
- Materiality floor, sizing, evidence classes, NaN gate, M3
  Candidate contract, M5 / M6 V2 blocks, and outcome log: all
  unchanged.
- `ReasonCode` enum: 12 values → 13 values
  (`TARGETING_HELD_UNDER_ABSTAIN` added).

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_abstain_soft_no_recommendations.py`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-synthetic-fix-3-summary.md`
  (this file)

## Remaining Risks

- **Fix 4 not yet shipped.** The plan calls for an
  `inventory_blocked` reason code wiring on the
  `bestseller_amplify` candidate for the low-inventory fixture.
  Fix 3 does not affect that path. The
  `_PRELIM_REASON_MAP` / `_CONSIDERED_REASON_TEXT` /
  `_WOULD_FIRE_IF_TEMPLATE` already have entries for
  `INVENTORY_BLOCKED`; Fix 4 is the M3 stamping.
- **Test runs that exercise V2 stack on real fixtures don't
  always show the Fix 3 routing.** That is by design: when the
  M3 candidate pipeline populates considered upstream, the head
  is empty and Fix 3's routing is a no-op. The unit tests cover
  the legacy-adapter case where head is non-empty under
  ABSTAIN_SOFT.
- **`MAX_ABSTAIN_SOFT_TARGETING_CARDS = 0` is the second line of
  defense, not the canonical contract.** A future contributor
  who reads the renderer code in isolation might think the cap
  is the contract. The docstring explicitly references Fix 3
  and points to `decide()` as the canonical path.
- **The new `TARGETING_HELD_UNDER_ABSTAIN` reason code is not
  yet plumbed through `data_quality_flag` or anomaly receipts.**
  It is purely a decide-state transition reason. If a future
  Klaviyo / outcome-log agent surfaces this code, the existing
  `_CONSIDERED_REASON_TEXT` lookup is the single source of truth
  for the merchant-readable copy.
- **Pre-existing considered entries with the same play_id win
  over the new typed entry.** This is the existing dedupe rule
  in `_dedupe_rejections` (first entry wins). If both M3 emits
  `NO_MEASURED_SIGNAL` for `bestseller_amplify` AND decide()
  ranks `bestseller_amplify` into the head under SOFT, the M3
  reason code surfaces. This was an explicit choice to avoid
  doubling cards. PM and DS both accepted; if the desired UX is
  the inverse (Fix 3 wins), the dedupe rule is the single seam
  to flip.

## Readiness Assessment For Fix 4

Ready. Specifically:

- Full suite (600 passed, 12 skipped) is clean, so Fix 4's
  `tests/test_inventory_blocked_in_considered.py` can land
  against a known-green baseline.
- The `_PRELIM_REASON_MAP`, `_CONSIDERED_REASON_TEXT`, and
  `_WOULD_FIRE_IF_TEMPLATE` already have entries for
  `INVENTORY_BLOCKED`. Fix 4 only needs to stamp
  `preliminary_rejection_reason="inventory_blocked"` in M3
  `detect_candidates` and (optionally) verify `bestseller_amplify`
  surfaces as a base candidate on the low-inventory fixture.
- `decide.py` ABSTAIN_SOFT routing is now in place; if the
  inventory-blocked candidate also reaches the ranked head, the
  dedupe rule keeps the M3 `INVENTORY_BLOCKED` reason ahead of
  the new `TARGETING_HELD_UNDER_ABSTAIN` reason. Fix 4 does not
  need to interact with Fix 3.
- No goldens were re-baselined.
- The `ReasonCode` enum is now 13 values; Fix 4 does not need
  to add another (`INVENTORY_BLOCKED` already exists from M5).

No code-level discovery from Fix 3 changes the planned shape of
Fix 4.

## Git Status

Per the brief, changes are NOT committed. Files left unstaged so
the user can review the diff before committing. Current state:

- 1 new test file: `tests/test_abstain_soft_no_recommendations.py`.
- 1 new doc file: this summary.
- 4 source files modified: `src/engine_run.py`, `src/decide.py`,
  `src/storytelling_v2.py` (and 3 test files updated for the
  contract change).
