# Code Refactor Engineer — Phase 6A Ticket B1 Summary

_Date: 2026-05-05_
_Branch: `engine-rework`_
_Baseline commit: `bfa8eff` (post-A4.5)_
_Scope: Phase 6A Ticket B1 ONLY from `agent_outputs/implementation-manager-campaign-slate-plan.md`._

## Approved Scope

Render the Recommended Experiment section in V2 `briefing.html`. The
data is already populated in `engine_run.recommended_experiments`
end-to-end (Ticket A4 added the field/selector; Ticket A4.5 plumbed
Phase 5/M3 candidates into `decide()`). Ticket B1 surfaces the list to
the merchant.

Render `engine_run.recommended_experiments` between Recommended Now
and Watching when `ENGINE_V2_SLATE` is on. The flag is implicitly
gated by data: A4 ensures the list is `[]` when `ENGINE_V2_SLATE=false`
and under both abstain branches, so "section absent when list is
empty" satisfies the contract without adding a second flag-read seam.

This is a renderer-only ticket. Decide layer, priors metadata,
PlayCard schema, materiality floors, ABSTAIN routing, and the legacy
renderer are explicitly out of scope.

## Patch Summary

1. **`src/storytelling_v2.py`** — additive only:
   - Imported `WouldBeMeasuredBy` from `src.engine_run`.
   - Added three module-level constants:
     `RECOMMENDED_EXPERIMENT_SECTION_CLASS = "recommended-experiment"`,
     `RECOMMENDED_EXPERIMENT_LEDE` (verbatim send-and-measure framing),
     `_WOULD_BE_MEASURED_BY_DISPLAY_COPY` (centralized 3-string
     enum-to-merchant-copy map).
   - Added `_would_be_measured_by_display(value)` — pure helper that
     maps an enum value to one of the three approved literal strings,
     or `""` for `None` / unknown.
   - Added `_render_recommended_experiment_card(card)` — renders one
     PlayCard inside an `article.play-card.play-card--experiment`
     wrapper. Reuses `_audience_summary_html` and
     `_render_opportunity_context_block` verbatim. No new template
     engine, no Jinja change.
   - Added `render_recommended_experiment_section(cards)` — public
     entry point. Returns `""` when the list is empty (no DOM node
     when no data); otherwise wraps the cards in
     `<section class="recommended-experiment" aria-label="Recommended
     Experiment">`.
   - Wired the new section into `render_engine_run` AFTER Recommended
     Now and BEFORE Watching. The exact slot order in the assembled
     body is now:
     state-of-store → recommended → recommended-experiment → considered
     → watching → dq-footer.
   - The ABSTAIN_HARD branch still returns the data-quality memo
     before reaching the Recommended Experiment slot, so the section
     never appears under ABSTAIN_HARD.

2. **`tests/test_render_recommended_experiment.py` (NEW)** — 20 tests
   pinning the B1 contract:
   - Section presence + count of cards (0, 1, 2 experiments).
   - DOM order: Recommended Now < Recommended Experiment < Watching.
   - Section title literal "Recommended Experiment".
   - Section lede contains "measure" (send-and-measure framing).
   - Three parametrized tests pin the exact merchant-readable display
     copy for each `WouldBeMeasuredBy` enum value.
   - Free-text rejection: raw enum values (e.g.
     `EMAIL_ATTRIBUTED_REVENUE_IN_7D`) MUST NOT appear anywhere in the
     rendered HTML.
   - Phase 5.1 opportunity-context block renders verbatim (probe by
     `OPPORTUNITY_CONTEXT_CLASS`).
   - "This is not projected lift" disclaimer renders.
   - Audience block reuses "N people" framing.
   - `revenue_range.suppressed=True` invariant: pinned on the
     EngineRun and on the rendered HTML (no `$X,XXX` outside the
     opportunity-context block).
   - ABSTAIN_SOFT path renders zero experiment cards.
   - ABSTAIN_HARD path does NOT render the experiment section (memo
     only).
   - Forbidden statistical strings absent from the section.
   - No "Aura" / "Beacon Score" tokens in the section.
   - Recommended Now still renders alongside Recommended Experiment.

No other source files were modified. No `src/storytelling.py`, no
`src/decide.py`, no `src/engine_run.py`, no `src/main.py`, no
`config/priors.yaml`, no `src/priors_loader.py`, no `src/utils.py`, no
goldens, no fixtures.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling_v2.py`
  - Added `WouldBeMeasuredBy` to the import block from `.engine_run`.
  - Added `RECOMMENDED_EXPERIMENT_SECTION_CLASS`,
    `RECOMMENDED_EXPERIMENT_LEDE`, and
    `_WOULD_BE_MEASURED_BY_DISPLAY_COPY` constants (after the
    OPPORTUNITY_CONTEXT_DISCLAIMER block).
  - Added `_would_be_measured_by_display(...)` helper.
  - Added `_render_recommended_experiment_card(...)` helper.
  - Added `render_recommended_experiment_section(...)` public entry
    point.
  - Modified `render_engine_run(...)` body assembly to insert
    `recommended_experiment_html` between `recommended_html` and
    `considered_html`.

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_render_recommended_experiment.py` (NEW)
  - 20 tests, including 3 parametrized cases for each enum value.

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-b1-summary.md` (NEW)
  - This summary.

## Renderer Selectors / Classes Added

- Section wrapper:
  `<section class="recommended-experiment" aria-label="Recommended Experiment">`
- Section title: `<h2 class="section__title">Recommended Experiment</h2>`
- Section lede:
  `<p class="section__lede">Plays we'd run as experiments. We will
  measure the result and learn whether they work for your store.</p>`
- Card wrapper: `<article class="play-card play-card--experiment"
  data-play-id="..." data-evidence-class="targeting">`
- Card title: `<h3 class="play-card__title">{Humanized Play Id}</h3>`
- "Run as experiment" framing badge:
  `<div class="play-card__class-badge play-card__class-badge--experiment">
  Run as experiment</div>`
- Recommendation text: `<p class="play-card__recommendation">...</p>`
- Audience block: reused `<div class="play-card-aud">...</div>` with
  the existing `<strong>N</strong> people` framing.
- `would_be_measured_by` line:
  `<p class="play-card__measured-by">{approved literal string}</p>`
- Phase 5.1 opportunity-context block: reused verbatim via
  `_render_opportunity_context_block(...)`. Renders with class
  `play-card-opportunity` and the negation disclaimer
  `play-card-opportunity__disclaimer`.

No CSS rule for `.play-card--experiment` was added; the existing
`.play-card` baseline rule applies. A future styling pass may add a
distinguishing border / background — out of scope for B1.

## `would_be_measured_by` Display Mapping

Centralized in `_WOULD_BE_MEASURED_BY_DISPLAY_COPY` in
`src/storytelling_v2.py`:

| Enum value                          | Display string                                         |
| ----------------------------------- | ------------------------------------------------------ |
| `INCREMENTAL_ORDERS_IN_14D`         | `We will measure incremental orders in 14 days.`       |
| `EMAIL_ATTRIBUTED_REVENUE_IN_7D`    | `We will measure email-attributed revenue in 7 days.`  |
| `REPEAT_PURCHASE_IN_30D`            | `We will measure repeat purchase in 30 days.`          |

Free-text rendering of the enum is forbidden; the helper returns
`""` for `None` or unknown values, in which case the
`play-card__measured-by` line is omitted entirely.

## Sample Rendered Behavior

A two-card experiment slate (discount_hygiene + bestseller_amplify)
renders as:

```html
<section class="recommended-experiment" aria-label="Recommended Experiment">
  <h2 class="section__title">Recommended Experiment</h2>
  <p class="section__lede">Plays we'd run as experiments. We will
    measure the result and learn whether they work for your store.</p>
  <div class="play-card-grid">
    <article class="play-card play-card--experiment"
      data-play-id="discount_hygiene"
      data-evidence-class="targeting">
      <h3 class="play-card__title">Discount Hygiene</h3>
      <div class="play-card__class-badge play-card__class-badge--experiment">
        Run as experiment</div>
      <p class="play-card__recommendation">Reduce blanket discounts on full-price audience.</p>
      <div class="play-card-aud">
        <span class="play-card-aud__size"><strong>2,251</strong> people</span>
        <span class="play-card-aud__def">discount-prone buyers</span>
      </div>
      <p class="play-card__measured-by">We will measure email-attributed
        revenue in 7 days.</p>
      <div class="play-card-opportunity"
        data-aov-source="store_observed" data-aov-window="L28">
        <p class="play-card-opportunity__line">Opportunity context:
          <strong>2,251</strong> eligible customers &times;
          <strong>$69</strong> recent AOV (L28) =
          <strong>about $155.3k</strong> addressable order value.</p>
        <p class="play-card-opportunity__disclaimer">This is not projected
          lift; it shows the size of the audience if the play converts.</p>
      </div>
    </article>
    <article class="play-card play-card--experiment"
      data-play-id="bestseller_amplify"
      data-evidence-class="targeting">
      <!-- ... -->
    </article>
  </div>
</section>
```

When `recommended_experiments` is empty, the renderer emits no
`<section class="recommended-experiment">` node at all. There is no
empty-state placeholder card, no jargon callout, no DOM artifact.

## Exact Commands Run

```bash
# Red-first capture (BEFORE the renderer change)
python -m pytest tests/test_render_recommended_experiment.py --tb=no -q
# -> 12 failed, 8 passed in 0.02s
# Failures (verbatim signatures captured below)

# Green (AFTER the renderer change)
python -m pytest tests/test_render_recommended_experiment.py -v
# -> 20 passed in 0.02s

# V2 renderer regression
python -m pytest tests/test_render_v2.py -v
# -> 25 passed in 0.39s

# A4 / A4.5 eligibility regression
python -m pytest tests/test_recommended_experiment_eligibility.py \
                 tests/test_recommended_experiment_main_wiring.py -v
# -> 27 passed in 0.05s

# Targeting no-dollar-headline invariant
python -m pytest tests/test_targeting_no_dollar_headline.py -v
# -> 6 passed in 0.10s

# Goldens (M0 byte-identical)
python -m pytest tests/test_golden_diff.py -v
# -> 3 passed in 27.39s, 0 re-baselined

# Full suite
python -m pytest tests/ -q
# -> 780 passed, 14 skipped, 0 failed in 117.71s
```

## Tests / Checks Run

| Check                                                              | Result                              | Notes                                           |
| ------------------------------------------------------------------ | ----------------------------------- | ----------------------------------------------- |
| `tests/test_render_recommended_experiment.py` (NEW)                | **20 passed**                       | Red-first failure captured before renderer landed |
| `tests/test_render_v2.py`                                          | 25 passed                           | M8 / A1 contract intact                         |
| `tests/test_recommended_experiment_eligibility.py`                 | 22 passed                           | A4 contract intact                              |
| `tests/test_recommended_experiment_main_wiring.py`                 | 5 passed                            | A4.5 contract intact                            |
| `tests/test_targeting_no_dollar_headline.py`                       | 6 passed                            | DS QA Change 4 / M8 invariant intact            |
| `tests/test_golden_diff.py`                                        | **3 passed (no re-baseline)**       | M0 byte-identical                                |
| Full suite `pytest tests/ -q`                                      | **780 passed, 14 skipped, 0 failed** | Pre-B1 baseline 760; +20 = exactly the new file |

## Did The New Tests FAIL Before The Fix?

**Yes — red-first evidence captured.** Before any change to
`src/storytelling_v2.py`,
`python -m pytest tests/test_render_recommended_experiment.py --tb=no -q`
produced **12 failed, 8 passed**. Verbatim failure signatures:

```
FAILED tests/test_render_recommended_experiment.py::test_section_renders_when_recommended_experiments_non_empty
  AssertionError: assert 'class="recommended-experiment"' in '<!DOCTYPE html>...'

FAILED tests/test_render_recommended_experiment.py::test_section_renders_one_card_per_experiment
  AssertionError: expected 2 cards under section.recommended-experiment, got 0
  assert 0 == 2

FAILED tests/test_render_recommended_experiment.py::test_section_appears_between_recommended_and_watching
  AssertionError: Recommended Experiment section missing
  assert -1 >= 0

FAILED tests/test_render_recommended_experiment.py::test_section_title_is_recommended_experiment
  AssertionError: assert 'Recommended Experiment' in ''

FAILED tests/test_render_recommended_experiment.py::test_section_lede_frames_send_and_measure_not_proven_lift
  (same root cause: empty section extraction)

FAILED tests/test_render_recommended_experiment.py::test_would_be_measured_by_enum_renders_approved_display_copy[INCREMENTAL_ORDERS_IN_14D-We will measure incremental orders in 14 days.]
FAILED tests/test_render_recommended_experiment.py::test_would_be_measured_by_enum_renders_approved_display_copy[EMAIL_ATTRIBUTED_REVENUE_IN_7D-We will measure email-attributed revenue in 7 days.]
FAILED tests/test_render_recommended_experiment.py::test_would_be_measured_by_enum_renders_approved_display_copy[REPEAT_PURCHASE_IN_30D-We will measure repeat purchase in 30 days.]
  (same root cause: section did not render)

FAILED tests/test_render_recommended_experiment.py::test_opportunity_context_block_renders_on_experiment_card
  AssertionError: Phase 5.1 opportunity-context block is missing on Recommended Experiment cards.

FAILED tests/test_render_recommended_experiment.py::test_opportunity_context_disclaimer_renders_on_experiment_card
  AssertionError: Disclaimer 'not projected lift' must render on experiment cards.

FAILED tests/test_render_recommended_experiment.py::test_audience_size_renders_with_people_framing
  (same root cause: section did not render)

FAILED tests/test_render_recommended_experiment.py::test_recommended_now_section_still_renders_with_experiment_section
  AssertionError: assert 'class="recommended-experiment"' in '<!DOCTYPE html>...'

12 failed, 8 passed in 0.02s
```

Tests that passed before the fix (the 8 passing tests):
- `test_section_absent_when_recommended_experiments_empty` — passes
  trivially because the section did not exist yet (the test pins
  absence under empty-list, which is also true when the renderer is
  unchanged).
- `test_section_renders_zero_cards_when_list_empty_via_publish` —
  same trivial-absence reason.
- `test_revenue_range_suppressed_remains_true_on_experiment_cards` —
  EngineRun-level invariant; no rendered output exercised.
- `test_abstain_soft_renders_zero_experiment_cards` — list is `[]`
  under ABSTAIN_SOFT (A4 contract); section absent regardless.
- `test_abstain_hard_does_not_render_experiment_section` —
  ABSTAIN_HARD memo path returns early; section absent regardless.
- `test_no_forbidden_statistical_strings_in_experiment_section` —
  empty section trivially has no forbidden tokens.
- `test_no_aura_or_beacon_score_in_experiment_section` — same.
- `test_no_free_text_would_be_measured_by_rendering` — no enum string
  in HTML when nothing renders.

After the renderer landed, all 20 tests passed. One iteration was
required: an early version emitted a
`data-would-be-measured-by="EMAIL_ATTRIBUTED_REVENUE_IN_7D"` HTML
data attribute, which leaked the raw enum string into the rendered
HTML and tripped `test_no_free_text_would_be_measured_by_rendering`.
The data attribute was removed; the contract enforces enum-to-display
mapping in body copy only. Final state: **20 passed**.

## Confirmation `revenue_range` Remains Suppressed

`test_revenue_range_suppressed_remains_true_on_experiment_cards`
pins this. The test:
1. Constructs experiment cards with `RevenueRange(suppressed=True,
   drivers=[{"reason": "experiment_no_calibrated_lift"}])`.
2. Asserts `card.revenue_range.suppressed is True` directly on the
   `EngineRun.recommended_experiments` list (structural pin).
3. Renders the EngineRun, extracts the `recommended-experiment`
   section, strips the `play-card-opportunity` blocks, and asserts
   no `$X,XXX` pattern remains. The opportunity-context block uses
   "about $X" framing which is allowed body copy; no standalone $
   headline appears outside the block.

The renderer never calls `_render_revenue_range_chip` for experiment
cards, so even if a future regression accidentally sets
`suppressed=False` on the EngineRun, the rendered HTML would still
omit the chip. The combination is "suspenders + belt": the
upstream A4 selector enforces `suppressed=True` at write time, and
the renderer never emits a chip on experiment cards regardless.

## Confirmation No Forbidden Terms Were Added

Pinned by:

- `test_no_forbidden_statistical_strings_in_experiment_section` —
  scans the experiment section for `p =`, `q =`, `p-value`,
  `q-value`, `confidence_score`, `final_score`, `CI [`, `p_internal`,
  `ci_internal`. None appear.
- `test_no_aura_or_beacon_score_in_experiment_section` — scans for
  `Aura`, `aura`, `Beacon Score`, `beacon_score`. None appear.
- `test_no_free_text_would_be_measured_by_rendering` — pins that the
  raw enum strings (`EMAIL_ATTRIBUTED_REVENUE_IN_7D`,
  `INCREMENTAL_ORDERS_IN_14D`, `REPEAT_PURCHASE_IN_30D`) do not
  appear anywhere in the rendered HTML.
- `tests/test_targeting_no_dollar_headline.py` — 6 passed (M8
  invariant) — the experiment cards use the existing
  `_render_opportunity_context_block` which already carries the
  "not projected lift" negation disclaimer; the test sweep over the
  full briefing remains green.
- The forbidden-token sweep extension (Ticket B2) lands the explicit
  scoped sweep on `section.recommended-experiment` for the seven new
  forbidden tokens. B1 keeps a light pin in place; B2 owns the
  rigorous sweep.

The renderer never calls `print` / `_fmt_money(card.revenue_range.p50)`
/ raw-enum string interpolation. The only $ amounts that can render
on an experiment card are inside the Phase 5.1 opportunity-context
block, which uses `_round_addressable_value` ("about $X" framing)
and carries the negation disclaimer verbatim.

## Goldens

- `tests/test_golden_diff.py` → **3 passed, 0 re-baselined**.
- M0 legacy goldens
  (`tests/golden/{small_sm, mid_shopify, micro_coldstart}/*`):
  byte-identical.
- This is the expected outcome because (a) the legacy renderer
  (`src.storytelling`) is unchanged, (b) goldens are produced under
  default flags (`ENGINE_V2_OUTPUT=false` and
  `ENGINE_V2_SLATE=false`), so the legacy path runs, (c) even on the
  V2 path, `recommended_experiments` is `[]` when the slate flag is
  off, so the new section emits no DOM node and no character drift.

## Behavior Changes

Under default flags (`ENGINE_V2_SLATE=false`) — **no merchant-facing
change**. Legacy briefing is unchanged. V2 receipts already carried
`recommended_experiments: []` since A4; A4.5 plumbed candidates;
neither exposed the section to the merchant. B1 leaves both behaviors
intact.

Under `ENGINE_V2_OUTPUT=true` AND `ENGINE_V2_DECIDE=true` AND
`ENGINE_V2_SLATE=true` (full V2 + slate stack):

- A new `<section class="recommended-experiment">` renders between
  Recommended Now and Considered/Watching when
  `engine_run.recommended_experiments` is non-empty.
- Each card carries: title, "Run as experiment" badge, recommendation
  text, audience block ("N people"), `would_be_measured_by` line
  with one of three approved strings, Phase 5.1 opportunity-context
  block with "about $X" framing and the "not projected lift"
  disclaimer.
- No $ headline, no chip, no statistical string, no enum free-text.

Under `ENGINE_V2_OUTPUT=true` + ABSTAIN_SOFT — section absent (list is
`[]` per A4 contract).

Under `ENGINE_V2_OUTPUT=true` + ABSTAIN_HARD — entire briefing is
the data-quality memo; the experiment section is structurally
unreachable in this branch.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_render_recommended_experiment.py`
  — 20 tests pinning section presence, DOM order, title, lede, enum
  display mapping, free-text rejection, opportunity-context block
  reuse, disclaimer presence, audience framing, suppressed
  revenue_range invariant, ABSTAIN_SOFT zero-card behavior,
  ABSTAIN_HARD section-absent behavior, forbidden-token absence,
  Aura/Beacon-Score absence, sibling-section coexistence.

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-b1-summary.md`
  — this summary.

No new sample HTML, fixtures, or goldens. No CSS rule additions.

## Confirmation A1 + A2 + A3 + A4 + A4.5 Behavior Is Intact

**A1 (Watching cap=4 + load-bearing pin):**
- `MAX_WATCHING_RENDERED = 4` unchanged.
- `_LOAD_BEARING_WATCH_METRICS` unchanged.
- `tests/test_render_v2.py` 25/25 passed (includes Watching cap
  tests, load-bearing tests, MOVED-load-bearing fallback test).
- `tests/test_watching_load_bearing_priority.py` — passed in full
  suite run.

**A2 (`would_be_measured_by` enum + PlayCard field):**
- `WouldBeMeasuredBy` enum unchanged.
- `PlayCard.would_be_measured_by` field unchanged.
- B1 imports the enum from `engine_run` and reads it via
  `_would_be_measured_by_display`; no schema-side change.
- `tests/test_would_be_measured_by_enum.py` — passed in full suite
  run.
- `tests/test_engine_run_schema.py` — passed in full suite run.

**A3 (priors metadata schema + loader):**
- `config/priors.yaml` unchanged.
- `src/priors_loader.py` unchanged.
- `AudienceArchetype`, `PlayMetadata`, `PriorsMetadataError`,
  `get_play_metadata` unchanged.
- `tests/test_priors_metadata.py` — passed in full suite run.

**A4 (Recommended Experiment eligibility filter):**
- `src/decide.py` not modified.
- `_select_recommended_experiments(...)` unchanged.
- `MAX_RECOMMENDED_EXPERIMENT`,
  `RECOMMENDED_EXPERIMENT_ALLOWLIST`,
  `RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD` unchanged.
- `decide()` signature and behavior unchanged.
- `EngineRun.recommended_experiments` field unchanged.
- `tests/test_recommended_experiment_eligibility.py` — 22/22 passed.
- ABSTAIN_HARD / ABSTAIN_SOFT / PUBLISH branches in `decide()` still
  stamp `recommended_experiments=[]` / `recommended_experiments=[]`
  / selector output respectively.

**A4.5 (candidate plumbing into decide):**
- `src/main.py` not modified.
- `_phase5_cands_for_decide` hoist + bind + kwarg pin unchanged.
- `tests/test_recommended_experiment_main_wiring.py` — 5/5 passed.
- The structural source-text test that pins
  `_v2_decide(engine_run, cfg=cfg, candidates=...)` in `src/main.py`
  remains green.

## Remaining Risks

1. **CSS for `.play-card--experiment` is unstyled.** The new card
   wrapper inherits the baseline `.play-card` rules, so it renders
   readably but does not visually distinguish itself from a measured
   or directional card beyond the "Run as experiment" badge text.
   B-series styling polish is out of scope. A future cosmetic ticket
   can add a dashed border / different accent color without changing
   the contract.

2. **Empty-state copy is intentionally absent.** Per the contract
   ("the cleanest path: do not render the section at all when the
   list is empty"), a non-firing experiment slate produces no DOM
   node. This is consistent with the contract's "No experiment plays
   met audience-floor and overlap rules this run." optional copy
   becoming a Ticket B3 concern (ABSTAIN_SOFT empty-state). B1 takes
   the cleaner contract path.

3. **No B2 forbidden-token sweep yet.** The contract's seven
   universal-forbidden phrases (`calibrated`, `uplift`, `ATE`,
   `ITT`, `treatment effect`, `expected lift`, `projected lift`)
   are not yet pinned by an explicit scoped sweep. B1 adds a light
   pin (the existing `test_no_forbidden_statistical_strings_in_experiment_section`)
   covering the older M8 list. Ticket B2 owns the rigorous sweep
   extension. Today: I verified manually that the rendered output
   on the smoke fixture contains "projected lift" only once, inside
   the negation disclaimer, and contains none of the seven new
   forbidden phrases. B2 will mechanize that check.

4. **Section uses `<h2>` matching siblings.** This is consistent
   with the existing `recommended` / `considered` / `watching`
   headings, but a future accessibility audit might prefer a
   distinct heading hierarchy. Out of scope for B1.

5. **Opportunity-context block depends on `OpportunityContext`
   being populated on the card.** The Ticket A4 selector currently
   stamps `revenue_range` and `would_be_measured_by` but does NOT
   populate `opportunity_context`. The renderer therefore omits the
   Phase 5.1 block on real fixtures today — the cards render with
   audience + measured-by line, but no addressable-value sentence.
   This is consistent with the A4 selector contract; a future
   ticket can extend `_select_recommended_experiments` to call
   `_build_opportunity_context` (or the equivalent measurement_builder
   helper) and stamp the field. The renderer is already wired to
   surface it the moment the selector populates it. A future test
   can land alongside that selector change. For B1: the test file
   constructs cards with `opportunity_context` populated to verify
   the renderer wiring works; the producer wiring is a downstream
   concern.

6. **`render_engine_run` body order changed.** Previously:
   `state-of-store → recommended → considered → watching → dq-footer`.
   Now: `state-of-store → recommended → recommended-experiment →
   considered → watching → dq-footer`. Considered and Watching
   sibling order is preserved. A test in
   `tests/test_render_v2.py::test_publish_renders_all_three_sections_plus_state_of_store_and_dq_footer`
   asserted only presence (not order) of all four sections; that
   test remains green. No existing test pinned the literal
   considered-vs-watching DOM order.

## Readiness for Ticket B2

**Ready.** B2 (forbidden-token sweep extension on Recommended
Experiment) can build on B1 with confidence:

- Section CSS class `recommended-experiment` is the load-bearing
  selector for B2's `extract_section_html(html, "recommended-experiment")`
  helper.
- `OPPORTUNITY_CONTEXT_DISCLAIMER` is a stable module-level constant
  B2 can import to allowlist the single permitted "projected lift"
  occurrence inside the negation disclaimer.
- The `_WOULD_BE_MEASURED_BY_DISPLAY_COPY` mapping is the single
  source of truth for the three approved enum-derived strings; B2
  can pin that no other variants render.
- 20 B1 tests are green and pin the section's structural contract;
  B2's red-first test additions can rely on stable selectors.

B2's scope per the implementation plan:
- Add scoped forbidden-token sweep on `section.recommended-experiment`
  for the seven new tokens (`calibrated`, `uplift`, `ATE`, `ITT`,
  `treatment effect`, `expected lift`, `projected lift`) plus
  reaffirmed `forecast`, `predicted`, `evidence`, `measured`.
- Allowlist the single occurrence of "projected lift" inside the
  negation disclaimer.
- Reject every other occurrence anywhere in the section.
- Test-only file additions; no source change expected.

## Git Status

Per project convention, changes are NOT committed. Files left
unstaged for review:

- 1 modified `src/` file: `src/storytelling_v2.py`
  (additive: imports, constants, helpers, render function, body
  assembly slot).
- 1 new test file:
  `tests/test_render_recommended_experiment.py` (20 tests).
- 1 new doc file: this summary.

Pre-existing post-A4.5 unstaged files (from prior tickets) remain
unchanged in this commit window:
- `memory.md` (post-A4.5 notes)
- `src/decide.py` (A4 selector)
- `src/engine_run.py` (A4 field, A2 enum)
- `src/utils.py` (`ENGINE_V2_SLATE` flag default)
- `src/main.py` (A4.5 candidate plumb)
- `tests/test_recommended_experiment_eligibility.py` (A4)
- `tests/test_recommended_experiment_main_wiring.py` (A4.5)
- `agent_outputs/code-refactor-engineer-phase6a-ticket-a4-summary.md`
- `agent_outputs/code-refactor-engineer-phase6a-ticket-a4-5-summary.md`
- A1/A2/A3 territory files (from prior commits in the engine-rework
  branch).

No goldens modified. No `src/storytelling.py` (legacy renderer)
modified. No `config/priors.yaml` modified. No
`src/priors_loader.py` modified. No `src/decide.py`,
`src/engine_run.py`, `src/main.py`, or `src/utils.py` modified in B1.
