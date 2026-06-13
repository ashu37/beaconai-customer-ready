# Code Refactor Engineer — Phase 6B Ticket C1 Summary

_Date: 2026-05-05_
_Branch: `engine-rework`_
_Baseline commit: `585480e` (Phase 6A final review accepted)_
_Scope: Phase 6B Ticket C1 ONLY from `agent_outputs/implementation-manager-phase6b-founder-feedback-plan.md`._

## 1. Approved scope

Surface the already-loaded `mechanism` string from `config/priors.yaml`
as a "What we'd send:" line on Recommended Now (directional / measured)
and Recommended Experiment cards. Render-only change. No selector /
decide-layer / PlayCard schema change. No M0 golden change.

## 2. Files changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/priors_loader.py`
  — added `get_mechanism(play_id, *, vertical=None, subvertical=None,
  path=None) -> Optional[str]` typed accessor (~50 lines added,
  including docstring); updated `__all__` to export it. Wraps
  `get_play_metadata(play_id)` and returns
  `metadata.mechanism` when present, else `None`. Empty / whitespace-only
  mechanism strings also return `None` (silence-over-hallucination).
  `vertical`/`subvertical` kwargs accepted for forward compatibility but
  unused today (metadata block is per-play, not vertically scoped). No
  change to existing `get_prior` / `get_play_metadata` / cache semantics.

- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling_v2.py`
  — added module-level constants `WHAT_WE_SEND_CLASS = "play-card__what-we-send"`
  and `WHAT_WE_SEND_LABEL = "What we'd send:"`. Added private helpers
  `_render_what_we_send(mechanism: Optional[str]) -> str` and
  `_mechanism_for_play(play_id: Optional[str]) -> Optional[str]` (the
  latter does a lazy `from .priors_loader import get_mechanism` at call
  time and swallows transient lookup failures so a priors-loader glitch
  cannot poison the merchant briefing). Inserted the helper call in two
  card builders:
    - `_render_measured_card` (Recommended Now directional / measured):
      `what_we_send_html` is appended AFTER `audience_html` and BEFORE
      `metric_summary` in the `body_parts` list.
    - `_render_recommended_experiment_card` (Recommended Experiment):
      `what_we_send_html` is appended AFTER `audience_html` and BEFORE
      `measured_by_html` in the `body_parts` list.
  Added one CSS rule `.play-card__what-we-send { margin: 8px 0 8px 4px;
  font-size: 14px; color: #2d3748; line-height: 1.4; }` to the V2
  inline `_BRIEFING_CSS` block. NOT injected into M0 / legacy stylesheet.

- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`
  — re-pinned (byte-changing). Old: `len=12634`,
  `sha256=3ace01703ae16b9d31ea685eac0421c29cb8450794c2b5c2732fcaad60125e7a`.
  New: `len=13065`,
  `sha256=2985e8c01b218a7bb3620a4d31d6414c191494a01ad17ed01924d48f45662675`.
  Determinism verified: 3 fresh harness invocations under the same
  `_B6_ENV_OVERRIDES` produce identical sha256.

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_what_we_send_render.py`
  (NEW) — 4 tests pinning the C1 contract. Required-named tests all
  present:
    - `test_mechanism_renders_on_recommended_directional`
    - `test_mechanism_renders_on_recommended_experiment`
    - `test_mechanism_absent_on_considered_and_watching`
    - `test_mechanism_omits_when_string_missing`

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6b-ticket-c1-summary.md`
  (NEW) — this summary.

No changes to: `src/decide.py`, `src/main.py`, `src/storytelling.py`
(legacy), `src/play_registry.py`, `src/engine_run.py`, `src/briefing.py`,
`config/priors.yaml`, M0 goldens (`tests/golden/`),
`tests/test_slate_regression_beauty_brand.py` source (only its consumed
fixture is re-pinned), `tests/test_recommended_experiment_forbidden_tokens.py`,
`tests/test_targeting_no_dollar_headline.py`. The B6 test file pins the
fixture via `read_text` byte equality, not a hardcoded sha256 string —
so the test source did NOT need editing; only the on-disk fixture
content changed.

## 3. Exact commands run

```bash
# 1. Confirm baseline state (B6 tests green pre-C1).
python -m pytest tests/test_slate_regression_beauty_brand.py -q
# -> 19 passed in 34.90s

# 2. TDD red: write the new tests, confirm 2/4 fail before any src/ change.
python -m pytest tests/test_what_we_send_render.py -v
# -> FAILED test_mechanism_renders_on_recommended_directional (no WWS class)
# -> FAILED test_mechanism_renders_on_recommended_experiment (no WWS class)
# -> PASSED test_mechanism_absent_on_considered_and_watching (trivially passes)
# -> PASSED test_mechanism_omits_when_string_missing (trivially passes)

# 3. Implement: src/priors_loader.py + src/storytelling_v2.py.
python -m pytest tests/test_what_we_send_render.py -v
# -> 4 passed in 0.05s (TDD green).

# 4. Re-pin Beauty fixture using the harness env overrides pinned in
#    tests/test_slate_regression_beauty_brand.py::_B6_ENV_OVERRIDES.
python -c "...regenerate fixture..."
# -> len=13065 sha256=2985e8c01b218a7bb3620a4d31d6414c191494a01ad17ed01924d48f45662675

# 5. Determinism check: 3 fresh harness runs vs the pinned fixture.
python -c "...3-run sha256 check..."
# -> all 3 match fixture: True

# 6. Required test sequence (Ticket C1 acceptance).
python -m pytest tests/test_what_we_send_render.py -v
# -> 4 passed in 0.04s
python -m pytest tests/test_slate_regression_beauty_brand.py -v
# -> 19 passed in 35.49s
python -m pytest tests/test_recommended_experiment_forbidden_tokens.py -v
# -> 33 passed in 0.05s
python -m pytest tests/test_targeting_no_dollar_headline.py -v
# -> 6 passed in 0.01s
python -m pytest tests/test_golden_diff.py -v
# -> 3 passed (no re-baseline)
python -m pytest tests/ -q
# -> 904 passed, 14 skipped, 0 failed in 168.68s
```

## 4. Tests/checks run

| Check | Result | Notes |
|-------|--------|-------|
| `tests/test_what_we_send_render.py` (NEW) | **4 passed** | Failed pre-fix: 2/4 (positive-render tests). Negative-control tests trivially passed. |
| `tests/test_slate_regression_beauty_brand.py` | **19 passed** | One pre-fix failure on `test_briefing_matches_pinned_fixture_bytewise` (expected, fixture re-pin). |
| `tests/test_recommended_experiment_forbidden_tokens.py` | 33 passed | B2 sweep on `section.recommended-experiment` intact. |
| `tests/test_targeting_no_dollar_headline.py` | 6 passed | Targeting-card $ invariant intact. |
| `tests/test_golden_diff.py` | **3 passed (no re-baseline)** | M0 byte-identical. |
| `tests/test_render_recommended_experiment.py` | 20 passed | (verified inside full suite) B1 contract intact. |
| `tests/test_priors_metadata.py` | passed (inside full suite) | A3 metadata loader contract intact. |
| Full suite `python -m pytest tests/ -q` | **904 passed, 14 skipped, 0 failed** | Pre-C1 baseline 900 passed; +4 = exactly the new file. |

## 5. Did the new tests fail before the fix?

**Yes — TDD red confirmed.** Before applying the `src/priors_loader.py`
+ `src/storytelling_v2.py` patch, the new test file produced:

```
FAILED tests/test_what_we_send_render.py::test_mechanism_renders_on_recommended_directional
  AssertionError: Expected the 'play-card__what-we-send' class to appear inside section.recommended ...
FAILED tests/test_what_we_send_render.py::test_mechanism_renders_on_recommended_experiment
  AssertionError: Expected the 'play-card__what-we-send' class to appear inside section.recommended-experiment ...
PASSED test_mechanism_absent_on_considered_and_watching  (trivially — class never rendered yet)
PASSED test_mechanism_omits_when_string_missing  (trivially — class never rendered yet)

2 failed, 2 passed
```

After the patch landed: 4 passed in 0.05s.

## 6. Where mechanism is sourced from

`config/priors.yaml`. The per-play `metadata.mechanism` string field is
loaded by the existing Phase 6A Ticket A3 loader path:

```
config/priors.yaml
  -> src.priors_loader.load_priors() -> _extract_play_block(doc, play_id)
  -> _coerce_metadata(...) -> PlayMetadata(mechanism=str, ...)
  -> src.priors_loader.get_play_metadata(play_id) -> Optional[PlayMetadata]
  -> [NEW C1] src.priors_loader.get_mechanism(play_id) -> Optional[str]
  -> [NEW C1] src.storytelling_v2._mechanism_for_play(play_id) -> Optional[str]
  -> [NEW C1] src.storytelling_v2._render_what_we_send(mechanism) -> str (HTML)
```

Today only `bestseller_amplify` and `discount_hygiene` carry a
`metadata:` block in priors.yaml. All other plays use the legacy list
form, so `get_mechanism` returns `None` for them and the line is
omitted on their cards. Populating mechanism strings for additional
plays (e.g., `first_to_second_purchase`) is a content task in
priors.yaml; C1 ships only the surfacing path.

## 7. Was a new accessor added?

**Yes.** Signature:

```python
def get_mechanism(
    play_id: str,
    *,
    vertical: Optional[str] = None,
    subvertical: Optional[str] = None,
    path: Optional[Path] = None,
) -> Optional[str]
```

Added to `src/priors_loader.py` and exported via `__all__`. It is a
thin wrapper around `get_play_metadata(play_id, path=path)`:

- Returns `metadata.mechanism` when the play has a metadata block AND
  the mechanism is a non-empty string after `.strip()`.
- Returns `None` otherwise (no metadata block, missing mechanism,
  empty / whitespace-only mechanism, or non-string).
- `vertical`/`subvertical` kwargs are accepted for forward
  compatibility with `get_prior`'s scope-aware resolution; unused
  today because the metadata block is per-play, not vertically scoped.
  Routes through the existing `_extract_play_block` path; no new YAML
  loader, no cache change.

The renderer-side helper `_mechanism_for_play(play_id)` in
`storytelling_v2.py` is a defensive lazy-import wrapper that swallows
import-time / lookup-time failures so a transient priors-loader
exception cannot poison the merchant briefing.

## 8. Where the line renders (exact insertion seams in storytelling_v2.py)

**Recommended Now (directional / measured cards) — `_render_measured_card`:**

```python
# After audience_html, before metric_summary.
what_we_send_html = _render_what_we_send(_mechanism_for_play(card.play_id))

body_parts = [...]   # title + badge
if rec_text:                body_parts.append(...)   # recommendation
if why_now:                 body_parts.append(...)   # why-now
if audience_html:           body_parts.append(audience_html)
if what_we_send_html:       body_parts.append(what_we_send_html)   # <-- C1
if metric_summary:          body_parts.append(metric_summary)
if opportunity_context_html: body_parts.append(opportunity_context_html)
if range_chip_html:         body_parts.append(range_chip_html)
```

Final card order: title -> class badge -> recommendation -> why-now ->
audience -> **what we'd send** -> observed-metric -> opportunity-context
-> range-chip (if any). Matches the implementation plan §3.4.

**Recommended Experiment cards — `_render_recommended_experiment_card`:**

```python
# After audience_html, before measured_by_html.
what_we_send_html = _render_what_we_send(_mechanism_for_play(card.play_id))

body_parts = [...]   # title + "Run as experiment" badge
if rec_text:                body_parts.append(...)
if audience_html:           body_parts.append(audience_html)
if what_we_send_html:       body_parts.append(what_we_send_html)   # <-- C1
if measured_by_html:        body_parts.append(measured_by_html)
if opportunity_context_html: body_parts.append(opportunity_context_html)
```

Final card order: title -> "Run as experiment" badge -> (recommendation
if any) -> audience -> **what we'd send** -> measured-by -> opportunity-context.
Matches the implementation plan §3.4.

**Not called from:** `_render_targeting_card` (Considered uses the
rejected renderer, not the targeting renderer; there is no
mechanism-line call site there), `render_rejected_card` (Considered),
`render_watching_section` (Watching), `render_abstain_hard_memo`
(ABSTAIN_HARD).

## 9. Was any mechanism copy edited for forbidden-token compliance?

**No.** The two existing mechanism strings in `config/priors.yaml`
were inspected against the B2 universal-forbidden-token list:

- `bestseller_amplify.metadata.mechanism`: "Email a curated bundle of
  the hero SKU plus complementary products to recent buyers; track
  basket attach." — clean.
- `discount_hygiene.metadata.mechanism`: "Email a 10% off code to
  discount-prone buyers; track redemption rate." — clean.

Neither contains: `calibrated`, `uplift`, `ATE`, `ITT`, `treatment
effect`, `expected lift`, `forecast`, `predicted`, `p =`, `q =`,
`p-value`, `q-value`, `confidence_score`, `final_score`, `p_internal`,
`ci_internal`, `Aura`, `Beacon Score`, `beacon_score`, `projected
lift`, past-tense `measured`, `evidence`, or a `$XX,XXX` pattern.
Both pass the B2 sweep verbatim. `tests/test_recommended_experiment_forbidden_tokens.py`
runs against synthetic-card fixtures, not real priors.yaml content,
but the Beauty Brand pinned slate fixture's experiment section
contains the real strings rendered through the new line, and the
B6 forbidden-token sweeps (`test_no_forbidden_tokens_in_experiment_section`
and `test_projected_lift_only_inside_disclaimer`) both pass against
the new fixture.

`config/priors.yaml` was NOT modified in this ticket.

## 10. Updated Beauty fixture sha256 (old -> new)

| Attribute | Pre-C1 | Post-C1 |
|-----------|--------|---------|
| Path | `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | (same) |
| Length | 12,634 bytes | **13,065 bytes** |
| sha256 | `3ace01703ae16b9d31ea685eac0421c29cb8450794c2b5c2732fcaad60125e7a` | **`2985e8c01b218a7bb3620a4d31d6414c191494a01ad17ed01924d48f45662675`** |
| Net delta | — | +431 bytes (1 CSS rule + 2 rendered "What we'd send:" lines, one per experiment card) |

Re-pin verification: 3 fresh harness invocations under the
`_B6_ENV_OVERRIDES` env superset (`ENGINE_V2_OUTPUT=true,
ENGINE_V2_DECIDE=true, ENGINE_V2_SLATE=true, ENGINE_V2_SIZING=true,
VERTICAL_MODE=beauty, WINDOW_POLICY=auto`) all produce the same new
sha256. Byte-stable.

The Recommended Now card on the Beauty fixture (`first_to_second_purchase`)
does NOT show a "What we'd send:" line — that play has no metadata
block in priors.yaml today. The 2 Recommended Experiment cards
(`discount_hygiene`, `bestseller_amplify`) both show their
priors.yaml-authored mechanism strings verbatim. Counted occurrences
of `play-card__what-we-send` in the fixture: 3 (1 in CSS rule,
2 rendered lines).

## 11. Did M0 goldens pass byte-identical?

**Yes.** `pytest tests/test_golden_diff.py` -> 3 passed in 27.22s.
Sub-results:

```
tests/test_golden_diff.py::test_golden_matches[small_sm] PASSED
tests/test_golden_diff.py::test_golden_matches[mid_shopify] PASSED
tests/test_golden_diff.py::test_golden_matches[micro_coldstart] PASSED
```

C1's render-layer change lives entirely behind the V2 stack
(`ENGINE_V2_OUTPUT=true` flag-gated render call site in
`src/briefing.py`). M0 goldens use the legacy
`src/storytelling.py` renderer, which was not modified. The new
`get_mechanism` accessor in `src/priors_loader.py` is exported but
not called by the legacy path.

## 12. Behavior changes

**Default flags (`ENGINE_V2_OUTPUT=false`): no change.** Legacy
renderer unchanged; M0 goldens byte-identical.

**Full V2 stack (`ENGINE_V2_OUTPUT=true` + `ENGINE_V2_DECIDE=true` +
`ENGINE_V2_SLATE=true`):**

- Recommended Now (directional / measured) cards now render a "What
  we'd send:" line between audience and observed-metric IFF the
  card's `play_id` carries a `metadata.mechanism` string in priors.yaml.
  Today this fires for `bestseller_amplify` and `discount_hygiene`
  if either is ever stamped as the directional Recommended Now. For
  `first_to_second_purchase` (the current Beauty fixture's directional
  card) it stays silent because that play has no metadata block.
- Recommended Experiment cards now render a "What we'd send:" line
  between audience and measured-by. Both Beauty experiment cards
  (`bestseller_amplify`, `discount_hygiene`) gain the line.
- Considered cards, Watching rows, and the ABSTAIN_HARD memo path
  unchanged.

The new line is a single `<p class="play-card__what-we-send">` with a
strong-tagged "What we'd send:" label and the HTML-escaped mechanism
string. CSS rule `.play-card__what-we-send { margin: 8px 0 8px 4px;
font-size: 14px; color: #2d3748; line-height: 1.4; }` provides modest
indent and body-color text, visually subordinate to the recommendation
and superior to the disclaimer.

**No behavior change** to the selector seam, the role-uniqueness
invariant, the cannibalization gate, the diversity filter, the
`would_be_measured_by` line, the opportunity-context block math, the
"not projected lift" disclaimer, the dollar-headline invariant, or the
forbidden-token sweep.

## 13. Artifacts added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_what_we_send_render.py`
  (NEW) — 4 tests.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6b-ticket-c1-summary.md`
  (NEW) — this summary.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`
  (re-pinned in place; not a new file).

## 14. Confirmation Phase 6A behavior intact

- `src/decide.py` not modified — selector seam locked, B3 ABSTAIN_SOFT
  routing intact, B4 role-uniqueness intact, B6 PUBLISH-branch
  considered-filter intact.
- `src/guardrails.py` not modified — guardrails locked.
- `src/sizing.py` not modified — revenue-range suppression locked.
- `src/engine_run.py` not modified — PlayCard / Audience / Measurement
  / WouldBeMeasuredBy schema unchanged. C1 does NOT add a new
  PlayCard field.
- `src/main.py` not modified — A4.5 candidate plumbing intact.
- `src/storytelling.py` (legacy) not modified — legacy renderer
  intact, M0 goldens byte-identical.
- `config/priors.yaml` not modified — A3 metadata content unchanged.
- `src/priors_loader.py` extended additively only — `get_prior`,
  `get_play_metadata`, `load_priors`, `clear_cache`, `schema_version`,
  `_extract_play_block` semantics all unchanged. New `get_mechanism`
  is a wrapper around the existing accessor.

## 15. Remaining risks

1. **Mechanism content authoring discipline.** The B2 universal
   forbidden-token sweep is still scoped to synthetic test fixtures
   (per `tests/test_recommended_experiment_forbidden_tokens.py`),
   not to runtime-loaded priors.yaml content. The B6 fixture sweeps
   (`test_no_forbidden_tokens_in_experiment_section`,
   `test_projected_lift_only_inside_disclaimer`) DO run against the
   real rendered Beauty briefing and currently pass. A future
   priors-author who writes a banned token (e.g., "predicted 14% lift")
   into a mechanism string would be caught by the B6 fixture-pin
   tests on the next harness re-pin (because the rendered slate will
   now contain that token). Document this in the priors-authoring
   guide if/when one is created.

2. **Recommended Now card on the Beauty fixture has no mechanism
   line today.** `first_to_second_purchase` carries no metadata block
   in priors.yaml. Founder will see "What we'd send:" on the 2
   experiment cards but NOT on the directional card. This is
   correct per the silence-over-hallucination rule, but is a content
   gap to fill in priors.yaml in a future content-only ticket. C1's
   acceptance criterion is "shows when mechanism exists" — it shows
   wherever a mechanism is authored. Populating mechanism strings
   for additional plays is a separate content task.

3. **Lazy-import surface in `_mechanism_for_play`.** The renderer
   imports `priors_loader.get_mechanism` at call time and swallows
   any exception so a corrupted priors.yaml cannot crash the
   briefing. Cost: a corrupted mechanism string would silently
   omit the line rather than fail loudly. Mitigation: the priors
   metadata loader is strict (`PriorsMetadataError` on malformed
   blocks), and the fixture pin would surface any drift loudly.

4. **`vertical`/`subvertical` kwargs are forward-compatible no-ops
   today.** If a future YAML schema adds per-vertical mechanism
   overrides, the call site
   (`_mechanism_for_play(card.play_id)`) does not pass `vertical`
   / `subvertical` and will fall back to the play-level default.
   That's the correct deferral; a future ticket extending the
   schema would extend the call site too.

## 16. Readiness for C2

**Ready.** C1 is landed cleanly:

- All required tests in this ticket pass (4 new + 19 B6 + 33 B2 + 6
  dollar-headline + 3 M0 + the rest of the suite).
- M0 goldens are byte-identical (no re-baseline).
- The Beauty pinned slate fixture is re-pinned with a new sha256 and
  is byte-stable across 3 fresh harness runs.
- The B2 forbidden-token sweep on `section.recommended-experiment`
  still passes on both synthetic fixtures and the new pinned Beauty
  fixture.
- The dollar-headline invariant on targeting cards still passes (the
  new line never appears on TARGETING-class cards because the
  Considered path uses the rejected renderer).
- No selector / decide-layer / PlayCard schema change was made.
- Kill switch `ENGINE_V2_OUTPUT=false` still falls back to legacy
  renderer cleanly.

C2 (section reorder, Watching before Considered) is the next ticket.
It will require another Beauty fixture re-pin but does not depend on
C1 beyond co-location in `src/storytelling_v2.py`. C1 and C2 are
designed to be shipped serially; the implementation plan §2 sequence
is C1 -> C2 -> C3 -> C4. No C2 prerequisites were violated by the C1
patch.

## 17. Git status (uncommitted)

Per project convention, changes left unstaged on top of post-585480e:

- 1 modified `src/` file: `src/priors_loader.py` (`get_mechanism`
  added).
- 1 modified `src/` file: `src/storytelling_v2.py` (helper +
  insertion + CSS).
- 1 re-pinned fixture: `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`.
- 1 new test file: `tests/test_what_we_send_render.py`.
- 1 new doc: this summary.

No M0 golden modifications. No `config/priors.yaml` modifications.
No `src/decide.py` / `src/main.py` / `src/storytelling.py` /
`src/engine_run.py` / `src/guardrails.py` / `src/sizing.py` modifications.
