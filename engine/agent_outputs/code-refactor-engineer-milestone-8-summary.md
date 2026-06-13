# Milestone 8 Summary — V2 Play Thesis Renderer

_Completed: 2026-05-03 (engine-rework branch)_

## Approved scope

Milestone 8 of `agent_outputs/implementation-manager-overhaul-plan-final.md`:
build a V2 renderer that consumes a fully-populated `EngineRun` and
produces the new merchant-facing Play Thesis briefing layout, behind
`ENGINE_V2_OUTPUT` (default OFF). Tickets T8.1, T8.2, T8.3, T8.4, T8.5,
T8.6, T8.7, T8.8.

- T8.1 — Three-section renderer (state-of-store + Recommended +
  Considered + Watching + DQ footer).
- T8.2 — Rejected-play card.
- T8.3 — ABSTAIN_HARD data-quality memo + ABSTAIN_SOFT layout with
  explicit "no measured opportunities cleared" callout.
- T8.4 — State-of-store paragraph from typed Observations.
- T8.5 — Targeting card visual treatment + fixed disclaimer + no
  standalone $ p50 headline.
- T8.6 — `briefing.py` router behind `ENGINE_V2_OUTPUT=true`.
- T8.7 — Legacy adapter `legacy_actions_from_engine_run()`.
- T8.8 — Side-by-side parity review artifacts.

**Out of scope (deferred per the M8 ticket):**

- M9 ML-readiness writers (`recommended_history.json`,
  `calibration_stub.load_realization_factors`).
- M10 cleanup / legacy code deletion.
- Klaviyo / Shopify production integrations.
- Outcome logging.
- Re-baselining of M0/M4b/M5/M6/M7 goldens (legacy path remains the
  default; flag OFF still byte-matches existing goldens).

## Files changed

### New files

- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling_v2.py` —
  the M8 V2 renderer. Pure function `render_engine_run(engine_run) ->
  str`. Public sub-renderers: `render_state_of_store`,
  `render_recommended_section`, `render_considered_section`,
  `render_rejected_card`, `render_watching_section`,
  `render_data_quality_footer`, `render_abstain_hard_memo`,
  `render_play_card`. Module-level constants:
  `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 2`, `TARGETING_CARD_DISCLAIMER`,
  `TARGETING_CARD_CLASS`, `MEASURED_CARD_CLASS`,
  `DIRECTIONAL_CARD_CLASS`, `REJECTED_CARD_CLASS`, `RANGE_CHIP_CLASS`.
  CSS is inlined in the module (kept self-contained; M10 may extract).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_render_v2.py`
  — 24 tests across PUBLISH, ABSTAIN_SOFT, ABSTAIN_HARD, state-of-store
  ordering, rejected-card content + cap, watching cap and empty-state,
  DQ footer, recommended section, badges, full-document smoke, and
  the legacy adapter `legacy_actions_from_engine_run` round-trip.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_targeting_no_dollar_headline.py`
  — 6 tests pinning the DS Architect QA Change 4 invariant. Targeting
  cards must not contain a standalone `$X,XXX` outside the range chip.
  Suppressed targeting card must contain zero dollar amounts. Page-wide
  forbidden-statistical-string sweep also lives here.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/m8_parity_review/README.md`
  — T8.8 parity review notes.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/m8_parity_review/small_sm_v2_briefing.html`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/m8_parity_review/small_sm_legacy_briefing.html`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/m8_parity_review/mid_shopify_v2_briefing.html`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/m8_parity_review/micro_coldstart_v2_briefing.html`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-milestone-8-summary.md`
  — this file.

### Edited files

- `/Users/atul.jena/Projects/Personal/beaconai/src/briefing.py`:
  - `render_briefing(...)` extended with two optional kwargs: `engine_run`
    (an EngineRun) and `use_v2` (bool). When both are supplied and
    `use_v2=True`, dispatches to `storytelling_v2.render_engine_run`
    and writes the V2 HTML. Otherwise falls back to the legacy Jinja
    renderer (existing behavior preserved byte-identically).
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run_adapter.py`:
  - Added `legacy_actions_from_engine_run(engine_run) -> Dict[str, Any]`
    (T8.7). Maps recommendations -> legacy `actions` shape and
    `considered` -> legacy `backlog` shape. Pure function; no I/O.
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`:
  - DEFAULTS: added `ENGINE_V2_OUTPUT` (default false).
  - `_coerce` bool set: extended to include `ENGINE_V2_OUTPUT`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`:
  - Hoisted `engine_run = None` out of the `try` block so the
    renderer router can read it after the M5/M6/M7 V2 chain runs.
  - Added a one-line route flag at the `render_briefing(...)` call:
    `_use_v2_output = bool(cfg.get("ENGINE_V2_OUTPUT", False)) and
    engine_run is not None`. The legacy CSV->HTML workflow is
    untouched when the flag is OFF.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/engine_flags.md`:
  - Last-updated stamp bumped to M8.
  - Added the `ENGINE_V2_OUTPUT` row to the future-flags table.

### Pre-existing files (untouched)

- `src/storytelling.py` — legacy renderer is preserved 1:1 as the
  flag-off default. No changes.
- `templates/briefing.html.j2` — legacy template untouched.
- `src/copykit.py`, `src/action_engine.py` — untouched (M10 owns the
  deletion).
- `src/decide.py`, `src/guardrails.py`, `src/sizing.py`,
  `src/priors_loader.py`, `src/evidence.py`, `src/engine_run.py`,
  `src/engine_run_adapter.py` — read-only by the renderer (only the
  adapter received an additive function).
- `tests/golden/` — no goldens re-baselined.

## Exact commands run

```
# M8 unit + integration tests
python -m pytest tests/test_render_v2.py tests/test_targeting_no_dollar_headline.py -v
# 30 passed in 0.42s

# Golden diff (M4b canonical, both flags forced via monkeypatch)
python -m pytest tests/test_golden_diff.py -v
# 3 passed (no re-baseline)

# Full suite
python -m pytest tests/ -q
# 401 passed, 5 skipped (M7 baseline 371 -> M8 401 = +30 new tests)

# End-to-end smoke: small_sm, full V2 stack
ENGINE_V2_OUTPUT=true ENGINE_V2_DECIDE=true ENGINE_V2_SIZING=true \
STATS_NAN_FOR_HARDCODED=true EVIDENCE_CLASS_ENFORCED=true \
MATERIALITY_FLOOR_SCALE_AWARE=true CANNIBALIZATION_GATE_ENABLED=true \
ANOMALY_GATE_ENABLED=true \
  python -m src.main --orders data/SM_orders.csv \
                     --brand m8_smoke_v2 --out /tmp/m8_smoke_v2
# Briefing renders V2 layout. abstain.state = abstain_soft. Targeting
# card surfaced; no $ headline; range chip hidden because prior is
# non-causal under M6 sizing.

# End-to-end smoke: mid_shopify and micro_coldstart, full V2 stack
ENGINE_V2_OUTPUT=true ... python -m src.main --orders data/shopify_orders_mid.csv ...
ENGINE_V2_OUTPUT=true ... python -m src.main --orders data/shopify_orders_micro_*.csv ...
# Both render V2; abstain_soft on both. Watching/considered render where
# upstream populated them.

# Default (flag-off) sanity check
python -m src.main --orders data/SM_orders.csv --brand m8_legacy_smoke --out /tmp/m8_legacy_smoke
# Briefing renders the legacy template (no `briefing-v2` markers).

# Forbidden-string sweep on V2 output
grep -cE 'p =|q =|p-value|q-value|confidence_score|final_score|p_internal|ci_internal' \
  agent_outputs/m8_parity_review/*v2*.html
# all results: 0
```

## Tests / checks run and results

| Suite                                            | Result                       |
|--------------------------------------------------|------------------------------|
| `tests/test_render_v2.py`                        | **24 passed**                |
| `tests/test_targeting_no_dollar_headline.py`     | **6 passed**                 |
| `tests/test_golden_diff.py`                      | **3 passed** (no re-baseline)|
| Full suite `python -m pytest tests/`             | **401 passed, 5 skipped**    |

Full-suite count went from 371 (M7) -> 401 (M8) = +30 new tests. Zero
regressions. Zero golden re-baselines.

## Renderer architecture

The V2 renderer is a single self-contained module
(`src/storytelling_v2.py`) with the following layering:

1. **Formatting helpers** (`_esc`, `_fmt_money`, `_fmt_int`,
   `_humanize_play_id`, `_humanize_metric`, `_humanize_reason_code`,
   `_humanize_data_quality_flag`) — internal to the module. All
   user-facing strings escape via `_esc` to prevent XSS on
   merchant-supplied audience definitions.
2. **Card renderers** (`_render_targeting_card`,
   `_render_measured_card`) — produce one `<article>` per PlayCard.
   `render_play_card(card, scale=...)` dispatches by evidence class.
3. **Section renderers** (`render_state_of_store`,
   `render_recommended_section`, `render_considered_section`,
   `render_rejected_card`, `render_watching_section`,
   `render_data_quality_footer`) — accept the relevant slice of the
   EngineRun and return an HTML string for the section.
4. **Abstain renderer** (`render_abstain_hard_memo`) — owns the
   ABSTAIN_HARD layout end-to-end (header + state-of-store + memo +
   DQ footer; no plays).
5. **Top-level** (`render_engine_run(engine_run) -> str`) — chooses
   between the abstain-hard layout and the standard 3-section layout
   based on `engine_run.abstain.state`. Returns a complete HTML
   document including doctype, head, inline CSS, and body.

The `briefing.render_briefing` router is the only consumer; it passes
`engine_run` and `use_v2=True` when `ENGINE_V2_OUTPUT=true` AND a
populated EngineRun is available. Otherwise it falls back to the
legacy Jinja template path.

## V2 sections implemented

### State-of-store paragraph (T8.4)

- Reads `engine_run.state_of_store: List[Observation]`.
- Orders observations: MOVED first (top 3), then HELD (filling to 5),
  then ANOMALOUS (filling to 5).
- Each observation contributes one sentence (already a complete
  sentence in the typed `Observation.text`); fallback sentence emitted
  when the list is empty.
- Output: `<section class="state-of-store">` with a `<p>` lead.
- Numeric confidence percentages and statistical jargon are
  structurally absent (the `Observation` schema does not carry them).

### Recommended section (T8.1)

- Reads `engine_run.recommendations: List[PlayCard]`.
- Renders 0-3 cards (M7 already caps at 3).
- Under ABSTAIN_SOFT, additionally caps the visible cards at
  `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 2` and renders the
  "no measured opportunities cleared" callout above the grid.
- Empty-state placeholder text emitted when no cards remain.
- Each card carries an evidence-class wrapper: `play-card--measured`,
  `play-card--directional`, or `play-card--targeting`.

### Considered, not recommended section (T8.2)

- Reads `engine_run.considered: List[RejectedPlay]`.
- Caps at 6 visible cards (M7 already caps the upstream list).
- Each card renders:
  - Title (humanized `play_id`).
  - Plain-English reason summary derived from `reason_code` (e.g.
    "Expected impact is below the materiality floor for this store.").
  - Optional `reason_text` detail (when not redundant with the summary).
  - Optional `evidence_snapshot` (italicized).
  - Optional `would_fire_if` (preceded by **Would fire if:**).
  - `data-reason-code="..."` attribute for downstream tooling.

### Watching section (T8.1)

- Reads `engine_run.watching: List[WatchedSignal]`.
- Renders up to 4 rows in a `<ul>`.
- Each row shows metric name, trend arrow (`up=&uarr;`, `down=&darr;`,
  `flat=&rarr;`), and `threshold_to_act` text when present.
- Empty-state placeholder when no signals.

### Data-quality footer (T8.1)

- Reads `engine_run.data_quality_flags`, `engine_run.data_window`,
  and `engine_run.scale`.
- Renders flag explanations from the per-flag plain-English mapping.
- Renders primary window, available windows, anchor quality.
- Renders monthly revenue estimate and materiality floor (when set).
- Falls back to "No data-quality flags on this run." when empty.

## Abstain rendering behavior

### ABSTAIN_HARD

- `render_abstain_hard_memo(engine_run)` renders a focused data-quality
  memo. **No recommendations are rendered**, even if the EngineRun's
  `recommendations` list is non-empty.
- Page wrapper: `<main class="briefing-v2 briefing-v2--abstain-hard">`.
- Sections: header, state-of-store paragraph, "Why no plays this run"
  memo with flag explanations and merchant guidance, DQ footer.
- Considered list is also suppressed (the page is intentionally a
  memo, not a partial briefing).
- Test: `test_abstain_hard_renders_data_quality_memo_and_no_recommendations`.

### ABSTAIN_SOFT

- Standard 3-section layout (state-of-store + Recommended + Considered
  + Watching + DQ footer) is preserved; the page must NOT look like an
  error page.
- An explicit `<div class="abstain-callout abstain-callout--soft">` is
  rendered at the top of the Recommended section with the load-bearing
  text "No measured opportunities cleared." plus the `Abstain.reason`.
- Recommendations are capped at 2 targeting cards (PM Q4 contract).
- Watching and Considered render where data is available.
- Test: `test_abstain_soft_renders_callout_and_layout_not_error_page`,
  `test_abstain_soft_caps_targeting_cards_at_two`,
  `test_abstain_soft_with_no_targeting_cards_still_renders_useful_sections`.

## Targeting-card rendering behavior (T8.5 / DS Architect QA Change 4)

- Wrapper class: `play-card play-card--targeting` (dashed border in CSS).
- Class badge: `Targeting`.
- Recommendation text + why-now line.
- Audience block: `**N** people` + definition + overlap callout.
- Optional source-labeled range chip (`<span class="play-card-range-chip">`)
  ONLY when `revenue_range.suppressed=False` AND a numeric span is
  available. The chip text reads `Estimated range (source label):
  $low - $high`. The chip is the **only** allowed dollar mention on a
  targeting card.
- When `revenue_range.suppressed=True` (cold-start, non-causal prior,
  default for current targeting plays) the renderer emits a
  "Why no $ projection" context block instead of any dollar amount.
- Fixed disclaimer footer: "This is a who-to-send-to recommendation,
  not a measured-lift forecast." Always present, on every targeting
  card.
- Mechanically pinned by `tests/test_targeting_no_dollar_headline.py`:
  - `test_suppressed_targeting_card_has_no_dollar_amount_at_all`.
  - `test_unsuppressed_targeting_card_renders_chip_but_no_headline`.
  - `test_targeting_card_disclaimer_is_fixed_text`.
  - `test_full_engine_run_targeting_cards_pass_invariant`.
  - `test_briefing_html_has_no_pvalue_qvalue_ci_confidence_score_or_finalscore`.
  - `test_no_numeric_confidence_percentage_string`.

## Rejected/considered rendering behavior

See "Considered, not recommended section" above. Key points:

- Up to 6 cards rendered.
- Plain-English reason summary derived from each `ReasonCode` so the
  merchant does not see a code string.
- `would_fire_if` text rendered with the `Would fire if:` prefix.
- `evidence_snapshot` rendered italicized below the reason.
- `data-reason-code` HTML attribute carries the machine code for any
  downstream tooling (intentionally hidden from rendered text).

## Watching rendering behavior

- Up to 4 deterministic signals rendered as a `<ul>` of
  `<li class="watching-row">` entries.
- Each row: metric name (humanized) + trend arrow + optional
  threshold-to-act sentence.
- Trend arrows: `up=&uarr;`, `down=&darr;`, `flat=&rarr;` (HTML entities
  so the page renders cleanly without external font assets).
- Empty-state line emitted when no signals.

## Data-quality footer behavior

- Always rendered on PUBLISH and ABSTAIN_SOFT (and inside the
  ABSTAIN_HARD memo).
- Lists data-quality flags with plain-English explanations.
- Lists primary window + available windows + anchor quality.
- Lists monthly revenue estimate + materiality floor when scale is
  populated.

## Legacy renderer status

- The legacy renderer (`src/storytelling.py` +
  `templates/briefing.html.j2`) is **preserved 1:1**. No source line
  was modified.
- With `ENGINE_V2_OUTPUT=false` (default), `briefing.render_briefing`
  follows the same code path it followed in M0-M7. The flag is the only
  branch.
- The legacy `actions_log.json` writer, `copykit.render_copy_for_actions`,
  and console summary path are untouched. T8.7's
  `legacy_actions_from_engine_run` is available for callers that want
  to drive the legacy consumers from the V2 EngineRun, but is not yet
  wired in `main.py` (the M8 ticket only requires the function to
  exist; M10 owns the rewiring).

## Fixture impact

- M0/M4b/M5/M6/M7 goldens: byte-identical with `ENGINE_V2_OUTPUT=false`.
  `tests/test_golden_diff.py` passes with 3/3 fixtures (no re-baseline).
- V2 parity samples: saved under `agent_outputs/m8_parity_review/`.
  - `small_sm_v2_briefing.html`: ABSTAIN_SOFT.
  - `mid_shopify_v2_briefing.html`: ABSTAIN_SOFT.
  - `micro_coldstart_v2_briefing.html`: ABSTAIN_SOFT.
  - `small_sm_legacy_briefing.html`: legacy baseline for visual diff.
- V2 goldens are intentionally NOT committed under `tests/golden/`
  yet. The plan explicitly says V2 goldens may be re-baselined after
  parity review sign-off. Per the M7 caveat ("With M4b flags off, the
  legacy adapter can label legacy actions as targeting"), the M8 V2
  state today is dominated by ABSTAIN_SOFT, which is a transition
  artifact, not a final shape. M9/M10 may revisit when measured cards
  start surfacing in real-fixture runs.

## Whether goldens still pass

**Yes. Zero goldens re-baselined.**

- `tests/test_golden_diff.py` runs unmodified. It does NOT set
  `ENGINE_V2_OUTPUT`, so the V2 renderer is not invoked. M4b canonical
  goldens remain byte-identical.
- `make golden-test` (equivalent to the diff test) passes.
- The merchant-facing `briefing.html` is unchanged on every fixture
  in flag-off mode because the legacy renderer is unchanged.
- The flag-on V2 path is fully exercised by `tests/test_render_v2.py`
  and `tests/test_targeting_no_dollar_headline.py` (synthetic fixtures
  cover PUBLISH, ABSTAIN_SOFT, ABSTAIN_HARD).

## Skipped items / accepted notes

None of the M8 tickets are skipped.

Accepted notes:

- **V2 goldens are not committed.** Per the plan ("ship
  `ENGINE_V2_OUTPUT=true` only after sign-off"), the M8 ticket only
  requires V2 to be runnable behind the flag and to pass synthetic
  golden tests. The flag-off legacy goldens remain canonical until a
  follow-up commit re-baselines on the V2 path.
- **`legacy_actions_from_engine_run` is not yet wired into `main.py`.**
  T8.7's contract is satisfied (the function exists, is exported, is
  unit-tested). The plan says "Lets us flip the renderer without
  touching action consumers" — i.e., the function is available for use,
  not mandated to replace the legacy bundle today. M10 owns the actual
  rewiring of `actions_log.json` / `copykit` to consume V2 EngineRun.
- **Inline CSS in `storytelling_v2.py`.** Kept inline so the renderer
  is fully self-contained for review; M10 may extract to an
  `assets/briefing_v2.css` file when the legacy template is deleted.
- **No PUBLISH-state V2 sample on a real fixture.** Today no fixture
  produces a measured/directional play under the V2 stack (because
  M4b reclassification + M6 conservative sizing demote all current
  legacy plays to TARGETING with suppressed ranges). Synthetic PUBLISH
  cases are exercised by `tests/test_render_v2.py`. Real-fixture
  PUBLISH state will return when M5/M6 measured plays start surfacing
  in M9 and beyond.
- **No ABSTAIN_HARD V2 sample on a real fixture.** No current fixture
  triggers a HARD data-quality flag. Synthetic ABSTAIN_HARD cases are
  exercised in `tests/test_render_v2.py`.

## Remaining risks

1. **V2 page is "ABSTAIN_SOFT-only" on every real fixture today.** This
   is the expected M4b/M5/M6 transition state, not a renderer bug. The
   renderer correctly displays the callout and the targeting cards.
   Reviewers should not interpret the absence of a measured/directional
   real-fixture sample as a rendering failure — the synthetic tests
   pin every layout variant.
2. **Legacy adapter for downstream consumers (T8.7) exists but is not
   wired in.** If a future agent flips `ENGINE_V2_OUTPUT=true` as the
   default before M10 rewires the legacy consumers, the
   `actions_log.json` writer and `copykit` will still consume the
   legacy `actions_bundle` produced by `select_actions`, not the V2
   EngineRun. This is acceptable today (both shapes are produced
   independently by the engine), but the wiring should be revisited
   before flipping the default.
3. **CSS is inline.** The page is self-contained but the rendered
   HTML is ~10kB heavier than the legacy template. M10 may extract.
4. **No JS interactivity.** The V2 page is intentionally static HTML.
   If product wants a live filter / sort widget on the considered
   list, that is a future enhancement.
5. **Targeting card $ check is structural, not literal.** The
   `tests/test_targeting_no_dollar_headline.py` invariant scopes its
   regex sweep to the targeting-card wrapper class. If a future edit
   changes the wrapper class without updating the test, the invariant
   could silently weaken. The test asserts the wrapper class string
   matches `TARGETING_CARD_CLASS` so a name change must be
   accompanied by the test seeing the new class.
6. **Charts/segments are not yet wired into V2.** The V2 page does
   not embed the chart images that the legacy template includes. The
   plan does not require them in M8 (the page is the Play Thesis
   layout, not a dashboard). If parity review wants the charts, M9/M10
   can pass `outputs["charts_map"]` through the V2 renderer.

## Readiness for Milestone 9

**Green to start M9.** M8 acceptance criteria are met:

- V2 renderer produces a complete HTML document for PUBLISH,
  ABSTAIN_SOFT, and ABSTAIN_HARD. Verified by 24 V2 renderer tests + 6
  targeting-invariant tests + 3 end-to-end smoke runs on the pinned
  fixtures.
- Legacy renderer remains the default and untouched. Verified by 3
  golden-diff tests passing with no re-baseline.
- No `p`/`q`/`CI`/`confidence_score`/`final_score` appears in the V2
  briefing HTML. Verified by both the synthetic test sweep and a
  `grep -cE` sweep on the saved real-fixture V2 outputs.
- Targeting no-dollar-headline test passes (6/6).
- ABSTAIN_HARD renders no recommendations (verified by both the
  test and the renderer's structural separation of layouts).
- ABSTAIN_SOFT renders the explicit callout and does not look like
  an error page (verified by tests).
- Rejected/considered section renders up to 6 plays (verified).
- Watching section renders deterministic signals up to 4 (verified).
- Data-quality footer renders flags + window metadata + scale info.
- M7/M6/M5/M4b goldens still pass for the legacy flag-off path
  (verified by `tests/test_golden_diff.py`).

**M9 prerequisites that M8 satisfies:**

- The V2 EngineRun is fully renderable end-to-end. M9's outcome
  logger can read the same `engine_run.json` receipts file and append
  history entries without touching the renderer.
- The legacy adapter `legacy_actions_from_engine_run` exists for
  any future consumer that wants to keep the legacy bundle shape
  while reading V2-decided plays.
- The renderer is pure (no I/O, no globals); M9's debug.html can
  reuse the helper functions to surface internal stats in a
  merchant-invisible debug page.
- The flag stack is well-documented (`docs/engine_flags.md`); M9
  can add `OUTCOME_LOG_ENABLED` cleanly alongside.

The M8 contract — `render_engine_run(EngineRun) -> str` — is a clean
seam for M9's debug renderer to plug into and for M10's eventual
default flip to consume.

## Validation summary

- **30 new tests** across 2 new test files. Zero existing tests modified.
- **0 regressions** in the 371-test M7 baseline (now 401 with M8
  additions).
- **0 goldens re-baselined.** All 3 M0/M4b/M5/M6/M7 fixtures still
  pass byte-identical with the V2 output flag off.
- **1 new env flag** added (`ENGINE_V2_OUTPUT`); default off.
- **1 new module** added: `src/storytelling_v2.py` (leaf-level; imports
  only `engine_run` + stdlib `html`).
- **1 new function** added to `src/engine_run_adapter.py`:
  `legacy_actions_from_engine_run`.
- **3 end-to-end smoke runs** on the three pinned fixtures
  (small_sm, mid_shopify, micro_coldstart) confirm the V2 renderer
  produces a complete HTML document with the right section markers
  and zero forbidden statistical strings.
- **Legacy renderer untouched. Briefing template untouched. Legacy
  `actions_log.json` untouched.** Per the M8 hard NOT-IN-SCOPE rule.
- **No `p` / `q` / `CI` / `confidence_score` / `final_score`** in any
  V2 briefing output (verified mechanically and by grep sweep on
  saved samples).
