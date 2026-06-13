# Code Refactor Engineer — Phase 6A Ticket B2 Summary

_Date: 2026-05-05_
_Branch: `engine-rework`_
_Baseline: post-B1.5 working tree (HEAD: `d48c9bc`)_
_Scope: Phase 6A Ticket B2 ONLY — forbidden-token sweep extension for the
Recommended Experiment section._

## Approved Scope

Add rigorous tests ensuring `section.recommended-experiment` never uses
forbidden causal/statistical/forecasting language, except the exact
allowed negation disclaimer phrase

    "This is not projected lift; it shows the size of the audience if
    the play converts."

This is a TEST-ONLY ticket. Zero changes to `src/`. The expectation, per
the implementation plan and B1 summary's explicit hand-off, is that B1's
existing renderer + B1.5's opportunity-context producer already emit
clean copy and the only deliverable is a scoped sweep that mechanizes
the contract.

## Patch Summary

1. **`tests/test_recommended_experiment_forbidden_tokens.py` (NEW)** — 33
   tests pinning the B2 contract:
   - 19 parametrized cases over `UNIVERSAL_FORBIDDEN_TOKENS_CASE_SENSITIVE`
     (one assertion per token).
   - `test_projected_lift_appears_only_inside_exact_disclaimer` — the
     allowlist-by-removal exact-string check.
   - `test_disclaimer_phrase_renders_verbatim` — count-of-2 occurrences
     pin (one per card).
   - `test_measured_past_tense_absent_from_experiment_section` — visible
     copy scan, "measured" forbidden.
   - `test_measure_future_tense_allowed_in_section_lede_and_cards` —
     positive control, "measure" + "We will measure" present.
   - `test_evidence_token_absent_from_experiment_section` — visible copy
     scan, "evidence" / "evidence-backed" forbidden.
   - 4 negative-control tests injecting forbidden copy via
     `recommendation_text` (calibrated/treatment effect, projected lift
     outside disclaimer, measured, evidence-backed) and confirming the
     sweep logic detects them.
   - `test_run_as_experiment_framing_remains_allowed` — positive
     control, contract-mandated badge copy preserved.
   - 2 parametrized positive-control tests for the per-card "We will
     measure ..." enum-derived lines.
   - `test_disclaimer_phrase_remains_allowed_at_exact_string` —
     defensive check that the disclaimer constant itself contains no
     universal-forbidden tokens (so the allowlist cannot mask a real
     leak).
   - `test_combined_universal_sweep_passes_on_canonical_slate` —
     single-fixture, single-pass production-shape assertion.

No `src/` files modified. No goldens, no fixtures, no priors metadata,
no PlayCard schema, no decide-layer changes, no renderer copy edits.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_recommended_experiment_forbidden_tokens.py` (NEW, 33 tests)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-b2-summary.md` (NEW, this summary)

## Scoped Section Extraction

The sweep targets ONLY `section.recommended-experiment`. The extraction
helper:

```python
_SECTION_RE = re.compile(
    rf'<section[^>]*class="[^"]*\b{re.escape(RECOMMENDED_EXPERIMENT_SECTION_CLASS)}\b[^"]*"[^>]*>(?P<body>.*?)</section>',
    re.DOTALL,
)


def _extract_experiment_section(html: str) -> str:
    match = _SECTION_RE.search(html)
    if not match:
        return ""
    return match.group(0)
```

The regex is anchored on the literal B1 module constant
`RECOMMENDED_EXPERIMENT_SECTION_CLASS = "recommended-experiment"`. A
future renderer rename would force this test to update in lockstep.
MOVED / WATCHING / Considered / State-of-Store / Recommended Now content
cannot leak in and trigger false positives because the regex stops at
the matching `</section>` tag and the V2 renderer does not nest sections.

## Visible-Text Scoping

Forbidden-token scans operate on visible text only — HTML tags
(including their attributes) are stripped before scanning. The contract
constrains merchant-facing language, not CSS class names or structured
data attributes used by scrapers.

```python
_TAG_RE = re.compile(r"<[^>]+>")


def _visible_text(section_html: str) -> str:
    return _TAG_RE.sub("", section_html)
```

Why this matters: the B1 renderer emits
`data-evidence-class="targeting"` (used by tests like
`tests/test_render_recommended_experiment.py` to scope card selectors)
and `class="play-card__measured-by"` (the CSS class for the future-tense
"We will measure ..." line). Both contain forbidden lemmas as
substrings (`evidence`, `measured`) but neither is merchant-readable
copy. Scoping the scan to visible text is the correct contract layer:

- `data-evidence-class="targeting"` — scraper selector, not visible.
- `class="play-card__measured-by"` — CSS class, not visible.
- "We will measure ..." — visible copy, allowed (future tense).
- "We measured ..." (hypothetical merchant-facing leak) — visible copy,
  forbidden (past tense, evidence claim).

The negative-control tests confirm the scan logic detects forbidden
text injected via `recommendation_text` (which renders into visible
copy via `<p class="play-card__recommendation">{rec_text}</p>`).

## "projected lift" Disclaimer Allowlist (Exact-String Match)

The allowlist is implemented as an exact-string-removal pass over the
visible text of the section, using the module constant
`OPPORTUNITY_CONTEXT_DISCLAIMER` from `src.storytelling_v2`:

```python
visible = _visible_text(section)
residual = visible.replace(OPPORTUNITY_CONTEXT_DISCLAIMER, "")
assert "projected lift" not in residual
```

The constant is the verbatim source of truth:

```
"This is not projected lift; it shows the size of the audience if the
 play converts."
```

`str.replace(...)` removes EVERY exact occurrence of the constant
(idempotent on its own output). Any "projected lift" substring that
survives the removal step is, by definition, NOT inside the disclaimer
phrase and trips the assertion. This is the surrounding-context-by-
removal approach: the allowlist is not a regex window, it is the
literal disclaimer text as a Python string.

The allowlist is also defended by
`test_disclaimer_phrase_remains_allowed_at_exact_string`, which asserts
that `OPPORTUNITY_CONTEXT_DISCLAIMER` itself contains no
universal-forbidden tokens. If a future contract update changes the
disclaimer to e.g. include "uplift", the allowlist would silently mask
a real leak; that test forces the issue at the constant.

## Forbidden Tokens Covered

### Universal forbidden (case-sensitive scan over visible text)

| Token              | Coverage                                            |
| ------------------ | --------------------------------------------------- |
| `calibrated`       | parametrized + combined sweep + negative control    |
| `uplift`           | parametrized + combined sweep                       |
| `ATE`              | parametrized + combined sweep                       |
| `ITT`              | parametrized + combined sweep                       |
| `treatment effect` | parametrized + combined sweep + negative control    |
| `expected lift`    | parametrized + combined sweep                       |
| `forecast`         | parametrized + combined sweep                       |
| `predicted`        | parametrized + combined sweep                       |
| `p =`              | parametrized + combined sweep                       |
| `q =`              | parametrized + combined sweep                       |
| `p-value`          | parametrized + combined sweep                       |
| `q-value`          | parametrized + combined sweep                       |
| `confidence_score` | parametrized + combined sweep                       |
| `final_score`      | parametrized + combined sweep                       |
| `p_internal`       | parametrized + combined sweep                       |
| `ci_internal`      | parametrized + combined sweep                       |
| `Aura`             | parametrized + combined sweep                       |
| `Beacon Score`     | parametrized + combined sweep                       |
| `beacon_score`     | parametrized + combined sweep                       |

### Special-case (allowlist by exact disclaimer phrase)

| Phrase           | Treatment                                                       |
| ---------------- | --------------------------------------------------------------- |
| `projected lift` | Allowed only inside `OPPORTUNITY_CONTEXT_DISCLAIMER`; rejected anywhere else. |

### Section-only forbidden (case-insensitive scan over visible text)

| Token             | Treatment                                                      |
| ----------------- | -------------------------------------------------------------- |
| `measured`        | Forbidden in visible copy (past tense / evidence claim).       |
| `evidence`        | Forbidden in visible copy.                                     |
| `evidence-backed` | Forbidden in visible copy.                                     |

### Allowed (positive controls)

| Phrase                                     | Treatment              |
| ------------------------------------------ | ---------------------- |
| `Run as experiment`                        | Required (badge copy). |
| `We will measure`                          | Required.              |
| `We will measure email-attributed revenue in 7 days.` | Required (enum copy). |
| `We will measure incremental orders in 14 days.`      | Required (enum copy). |
| `measure` (lemma, future tense)            | Allowed.               |
| `OPPORTUNITY_CONTEXT_DISCLAIMER` verbatim  | Required (twice; one per card). |

## Source Copy Changes

**No source copy was changed.** The B1 renderer + B1.5 producer already
emit clean visible copy. The sweep passed on the existing renderer
output the moment the test scope was correctly aligned to visible text
(rather than raw HTML, which would have falsely flagged
`data-evidence-class="targeting"` and `class="play-card__measured-by"`).

The visible-text scope is consistent with the contract's wording:

> No "calibrated," "uplift," "ATE," "ITT," "treatment effect" anywhere
> merchant-facing.
> No "expected lift," "projected lift," "forecast," "predicted" on any
> role.
> No "measured" or "evidence" claim on a directional or experiment card.

CSS class names and data attributes are not "merchant-facing" nor
"claims"; they are scraper selectors. The negative-control tests
confirm the sweep DOES detect forbidden text the moment it leaks into
visible copy via `recommendation_text` or any other body-copy field.

## Confirmation No Forbidden Language Appears In Recommended Experiment Section

`test_combined_universal_sweep_passes_on_canonical_slate` is the
single-pass, production-shape assertion. On the canonical Beauty-Brand-
shaped fixture (`discount_hygiene` + `bestseller_amplify`, both with
populated Phase 5.1 opportunity-context blocks):

- 19 universal-forbidden tokens — 0 occurrences each in visible copy.
- `projected lift` — 2 occurrences in visible copy, BOTH inside the
  exact `OPPORTUNITY_CONTEXT_DISCLAIMER` phrase (one per card). 0
  occurrences in the disclaimer-stripped residual.
- `measured` — 0 occurrences in visible copy.
- `evidence` / `evidence-backed` — 0 occurrences in visible copy.
- Contract-mandated copy: `Recommended Experiment`, `Run as experiment`,
  `We will measure` all present.

## Exact Commands Run

```bash
# B2 file (in order)
python -m pytest tests/test_recommended_experiment_forbidden_tokens.py -v
# -> 33 passed in 0.03s

# B1 / B1.5 / Phase 5 invariants (in order, per ticket spec)
python -m pytest tests/test_render_recommended_experiment.py -v
# -> 20 passed in 0.02s

python -m pytest tests/test_recommended_experiment_opportunity_context.py -v
# -> 15 passed in 0.26s

python -m pytest tests/test_phase5_no_aura_beacon.py -v
# -> 4 passed in 0.01s

python -m pytest tests/test_phase5_1_opportunity_context.py -v
# -> 20 passed in 0.38s

python -m pytest tests/test_targeting_no_dollar_headline.py -v
# -> 6 passed in 0.01s

# Goldens
python -m pytest tests/test_golden_diff.py -v
# -> 3 passed in 28.20s, 0 re-baselined

# Full suite
python -m pytest tests/ -q
# -> 828 passed, 14 skipped, 0 failed in 121.53s
```

## Tests / Checks Run

| Check                                                                  | Result                              | Notes                                                         |
| ---------------------------------------------------------------------- | ----------------------------------- | ------------------------------------------------------------- |
| `tests/test_recommended_experiment_forbidden_tokens.py` (NEW)          | **33 passed**                       | 19 parametrized universal + 14 disclaimer / past-tense / evidence / negative-control / positive-control tests |
| `tests/test_render_recommended_experiment.py`                          | 20 passed                           | B1 contract intact                                            |
| `tests/test_recommended_experiment_opportunity_context.py`             | 15 passed                           | B1.5 contract intact                                          |
| `tests/test_phase5_no_aura_beacon.py`                                  | 4 passed                            | Phase 5.5 forbidden-token sweep intact                        |
| `tests/test_phase5_1_opportunity_context.py`                           | 20 passed                           | Phase 5.1 helper invariants intact (incl. forbidden-affirmative scan) |
| `tests/test_targeting_no_dollar_headline.py`                           | 6 passed                            | DS QA Change 4 / M8 invariant intact                          |
| `tests/test_golden_diff.py`                                            | **3 passed (no re-baseline)**       | M0 byte-identical                                             |
| Full suite `pytest tests/ -q`                                          | **828 passed, 14 skipped, 0 failed** | Pre-B2 baseline 795 passed; +33 = exactly the new test file   |

## Goldens

- `tests/test_golden_diff.py` → **3 passed, 0 re-baselined**.
- M0 legacy goldens
  (`tests/golden/{small_sm, mid_shopify, micro_coldstart}/*`):
  byte-identical.
- Expected outcome because B2 is test-only: zero `src/` modifications,
  zero renderer copy changes, zero behavior changes. The legacy
  briefing path is untouched and the V2 path is unchanged.

## Behavior Changes

**None.** B2 is a test-only ticket. Under default flags
(`ENGINE_V2_SLATE=false`) — no merchant-facing change. Under the full
V2 + slate stack (`ENGINE_V2_OUTPUT=true` AND `ENGINE_V2_DECIDE=true`
AND `ENGINE_V2_SLATE=true`) — no merchant-facing change. The new tests
mechanize what the existing renderer already emits.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_recommended_experiment_forbidden_tokens.py`
  — 33 tests pinning the B2 forbidden-token contract on
  `section.recommended-experiment`.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-b2-summary.md`
  — this summary.

No new sample HTML, fixtures, goldens, CSS, or source modules.

## Confirmation A1 + A2 + A3 + A4 + A4.5 + B1 + B1.5 Behavior Is Intact

All prior-ticket invariants pass in the full-suite run (828 passed, 14
skipped). Specific spot checks:

- **A1 (Watching cap=4 + load-bearing pin):**
  `tests/test_render_v2.py` and
  `tests/test_watching_load_bearing_priority.py` green in full suite.
- **A2 (`would_be_measured_by` enum + PlayCard field):**
  `tests/test_would_be_measured_by_enum.py` and
  `tests/test_engine_run_schema.py` green.
- **A3 (priors metadata schema + loader):**
  `tests/test_priors_metadata.py` green.
- **A4 (Recommended Experiment eligibility filter):**
  `tests/test_recommended_experiment_eligibility.py` green.
- **A4.5 (candidate plumbing into decide):**
  `tests/test_recommended_experiment_main_wiring.py` green.
- **B1 (Recommended Experiment renderer):**
  `tests/test_render_recommended_experiment.py` 20/20 passed.
- **B1.5 (opportunity_context populated by selector):**
  `tests/test_recommended_experiment_opportunity_context.py` 15/15
  passed.

## Allowlist Pin Specifics

The "projected lift" disclaimer is allowlisted by the following
mechanism (visible everywhere in the file):

1. The B1 module constant `OPPORTUNITY_CONTEXT_DISCLAIMER` from
   `src.storytelling_v2` is imported at the test file's top.
2. The full visible-text section is captured.
3. `visible.replace(OPPORTUNITY_CONTEXT_DISCLAIMER, "")` removes EVERY
   exact occurrence of the disclaimer.
4. The residual is asserted to NOT contain the substring
   `projected lift`.

This is an exact-string-match allowlist (Python `str.replace`), not a
regex. It is brittle by design — any deviation from the verbatim
disclaimer phrase (paraphrase, capitalization change, word reorder)
would survive the removal step and trip the assertion. A defensive
companion test (`test_disclaimer_phrase_remains_allowed_at_exact_string`)
asserts that the disclaimer constant itself contains no
universal-forbidden tokens, so a future copy change cannot silently
expand the allowlist.

## Remaining Risks

1. **HTML-attribute-free assumption.** The `_visible_text` helper
   strips `<...>` tags wholesale. If a future renderer change
   introduced merchant-readable text inside an attribute (e.g. an
   `aria-label` with merchant-facing copy), the sweep would miss it.
   Today, every `aria-label` in the renderer is structural ("Recommended
   Experiment", "Recommended Now", etc.), so this is a low-risk gap.
   Future tickets that add merchant-readable attribute values should
   extend the helper.

2. **Section regex assumes single-section, no nesting.** The V2
   renderer does not nest sections, and the regex is non-greedy, so
   the first `</section>` after the open tag is the matching close.
   A future change that wraps the experiment section in a parent
   `<section>` would force this test to update.

3. **Disclaimer brittleness.** Changing the disclaimer copy
   anywhere (e.g. updating "size of the audience" to "audience size")
   without updating `OPPORTUNITY_CONTEXT_DISCLAIMER` in lockstep would
   trip the allowlist. This is intentional — the constant is the
   single source of truth. It is also pinned by
   `test_disclaimer_phrase_renders_verbatim` (count == 2 occurrences).

4. **Token list completeness.** B2 mechanizes the contract's documented
   forbidden tokens. Future contract updates that add new forbidden
   tokens require extending `UNIVERSAL_FORBIDDEN_TOKENS_CASE_SENSITIVE`
   in this file. The list is module-level for visibility.

5. **`evidence` lemma overlap with content.** "evidence" and
   "evidence-backed" are scanned case-insensitively over visible text.
   Today the only place the lemma could leak is via
   `recommendation_text` (negative control proves detection). If a
   future renderer adds a lede or footer that legitimately uses
   "evidence" (e.g. discussing why no card surfaced), the test would
   reject it. The contract is explicit that experiment cards must not
   carry that claim, so this is the correct floor.

## Readiness for Ticket B3

**Ready.** B3 (ABSTAIN_SOFT contract extension to Recommended
Experiment) builds on:

- `engine_run.recommended_experiments == []` under ABSTAIN_SOFT
  (already enforced by Ticket A4; B3 adds the held-cards-routing-into-
  Considered behavior + empty-state copy).
- The B2 sweep transitively confirms ABSTAIN_SOFT renders no section
  at all (via `tests/test_render_recommended_experiment.py::
  test_abstain_soft_renders_zero_experiment_cards`); B3 may extend
  this to add an empty-state callout copy block, in which case B2's
  sweep will mechanically apply to that new copy as well (no test
  changes needed unless the empty-state copy itself is forbidden).
- 33 B2 tests are green and pin the section's forbidden-token contract;
  B3's red-first additions can rely on a stable forbidden-language
  baseline.

B2 is also a clean prerequisite for B4 (role-uniqueness invariant), B5
(cannibalization + diversity), and B6 (Beauty Brand pinned slate
regression). B6 in particular benefits because the rendered section
copy is now mechanically pinned against forbidden language.

## Git Status

Per project convention, changes are NOT committed. Files left unstaged
for review on top of the post-B1.5 working tree:

B2-specific:
- `tests/test_recommended_experiment_forbidden_tokens.py` (new): 33 tests.
- `agent_outputs/code-refactor-engineer-phase6a-ticket-b2-summary.md`
  (new): this summary.

No other source, fixture, golden, or config files modified by B2.
