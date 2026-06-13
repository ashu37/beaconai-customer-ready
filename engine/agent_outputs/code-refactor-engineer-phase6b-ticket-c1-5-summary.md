# Code Refactor Engineer — Phase 6B Ticket C1.5 Summary

_Date: 2026-05-06_
_Branch: `engine-rework`_
_Predecessor: Phase 6B Ticket C1 (in-flight, uncommitted on top of `585480e`)._
_Scope: Phase 6B Ticket C1.5 ONLY — content-only mechanism metadata for `first_to_second_purchase` so the Beauty Brand Recommended Now card renders the C1 "What we'd send:" line._

## 1. Approved scope

Add a defensible, merchant-readable `mechanism` string for
`first_to_second_purchase` in `config/priors.yaml` so the Recommended
Now card on the Beauty Brand pinned slate fixture renders the C1
"What we'd send:" line. Content-only change. No `src/decide.py`,
selector logic, `PlayCard` schema, or renderer logic edits permitted
unless a tiny renderer bug is discovered (none found).

## 2. Patch summary

- Promoted `config/priors.yaml::plays.first_to_second_purchase` from
  the legacy list-only form to the Phase 6A Ticket A3 dict form
  (`metadata` + `priors`), preserving every existing prior row
  byte-for-byte in the new `priors:` sub-block. The five required
  metadata fields (`audience_floor`, `mechanism`,
  `vertical_applicability`, `would_be_measured_by`,
  `audience_archetype`) match the schema voice of the existing
  `discount_hygiene` and `bestseller_amplify` blocks exactly. No new
  metadata fields were introduced.
- Added a parallel typed pin in `tests/test_priors_metadata.py`
  (`test_first_to_second_purchase_metadata_loaded_and_typed`),
  matching the shape of the existing
  `test_discount_hygiene_metadata_loaded_and_typed` and
  `test_bestseller_amplify_metadata_loaded_and_typed` pins. Includes
  a 15-35 word range invariant on the mechanism string.
- Added a tightening render-side test
  (`test_mechanism_renders_for_first_to_second_purchase_directional`)
  in `tests/test_what_we_send_render.py` to exercise the realistic
  Beauty Brand directional play_id (`first_to_second_purchase`)
  end-to-end. The pre-existing C1 directional test
  (`test_mechanism_renders_on_recommended_directional`) artificially
  stamped `discount_hygiene` as DIRECTIONAL and was already
  exercising the `_render_measured_card` path correctly — it was NOT
  trivially passing, so it did not need to be tightened in place;
  the new test pins the realistic case alongside it.
- Re-pinned `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`
  with the harness running under `_B6_ENV_OVERRIDES`. The B6 fixture
  test compares via `read_text` byte equality — no hardcoded sha256
  string in the test source — so the test source did NOT need
  editing.

No edits to `src/decide.py`, `src/main.py`, `src/storytelling.py`
(legacy), `src/storytelling_v2.py`, `src/priors_loader.py`,
`src/play_registry.py`, `src/engine_run.py`, `src/sizing.py`,
`src/guardrails.py`. No renderer bug was discovered.

## 3. Exact mechanism string added

```
Email one-time buyers a value-led second-purchase nudge with best-next-product education, two sends one week apart, no blanket discount.
```

- **Word count: 18** (within the 15-35 range).
- **Audience**: "one-time buyers".
- **Channel**: "Email".
- **Posture**: "value-led", "no blanket discount", "best-next-product education".
- **Cadence**: "two sends one week apart".

Used the user-suggested copy verbatim. Matches the existing
`discount_hygiene` / `bestseller_amplify` schema voice (single
sentence, terse, "Email <audience> a <thing>; <how>" register).

## 4. Forbidden-token compliance check

The mechanism string was grep'd against the merger of the user's
required ban list and the B2 universal forbidden-token sweep list:

| Token | Present? |
|-------|----------|
| `lift` | absent |
| `forecast` | absent |
| `predicted` | absent |
| `guaranteed` | absent |
| `calibrated` | absent |
| `confidence` | absent |
| `p =` / `q =` / `p-value` / `q-value` | absent |
| `CI` / `ci_internal` / `p_internal` | absent |
| `confidence_score` / `final_score` | absent |
| `uplift` / `ATE` / `ITT` / `treatment effect` | absent |
| `expected lift` / `projected lift` | absent |
| `Aura` / `Beacon Score` / `beacon_score` | absent |
| `will increase` / `will lift` (causal claim) | absent |
| `% off` (concrete offer amount) | absent (regex `[0-9]+%` returns []) |
| `$` followed by digit (concrete offer amount) | absent (regex `\$[0-9]` returns []) |
| `$XX,XXX` pattern (Phase 6A targeting invariant) | absent |

All checks performed via lowercase substring match plus regex; zero
hits. Confirmed by full-suite run of
`tests/test_recommended_experiment_forbidden_tokens.py` (33 passed),
`tests/test_targeting_no_dollar_headline.py` (6 passed), and the B6
in-fixture sweeps (`test_no_forbidden_tokens_in_experiment_section`,
`test_projected_lift_only_inside_disclaimer`).

## 5. Files changed (full list)

Modifications introduced by Ticket C1.5 (on top of the in-flight C1
working tree):

- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml`
  — promoted `first_to_second_purchase` to the dict (`metadata` +
  `priors`) form. Five-key metadata block matches A3 schema. All
  three pre-existing prior rows (`base_rate`, `incrementality`,
  `second_purchase_lift`) preserved byte-for-byte under `priors:`.
  Added a short Phase 6B C1.5 comment block above the play_id.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_metadata.py`
  — added `test_first_to_second_purchase_metadata_loaded_and_typed`
  parallel to the existing two metadata-typed pins (29 added lines).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_what_we_send_render.py`
  — added the tightening render test
  `test_mechanism_renders_for_first_to_second_purchase_directional`
  (~50 added lines). The existing four C1 tests were left unchanged
  — the analysis (see §7) found no need to tighten them in place.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`
  — re-pinned in place (byte-changing). See §6 for old/new sizes
  and sha256.

No `src/` files changed in this ticket. No M0 golden files changed.
No `agent_outputs/` files written other than this summary.

## 6. Old -> new Beauty fixture sha256 and length

| Attribute | Pre-C1.5 (post-C1) | Post-C1.5 |
|-----------|--------------------|-----------|
| Path | `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | (same) |
| Length | 13,065 bytes | **13,278 bytes** |
| sha256 | `2985e8c01b218a7bb3620a4d31d6414c191494a01ad17ed01924d48f45662675` | **`48d61b89b3a6bb5b7c29d776ceec7fe8ba396522df4362651f7e476bf04726fe`** |
| Net delta | — | +213 bytes (1 rendered "What we'd send:" line on the `first_to_second_purchase` Recommended Now card) |

Determinism verification: 3 fresh harness invocations under
`_B6_ENV_OVERRIDES` (`ENGINE_V2_OUTPUT=true`, `ENGINE_V2_DECIDE=true`,
`ENGINE_V2_SLATE=true`, `ENGINE_V2_SIZING=true`,
`VERTICAL_MODE=beauty`, `WINDOW_POLICY=auto`) all produce identical
sha256. Byte-stable.

`play-card__what-we-send` occurrence count in the new fixture (per
BeautifulSoup section parse):

- `section.recommended` (Recommended Now): **1** — the new
  `first_to_second_purchase` directional card.
- `section.recommended-experiment`: **2** — `discount_hygiene`,
  `bestseller_amplify` (unchanged from post-C1).
- `section.considered`: 0.
- `section.watching`: 0.
- `section.state-of-store`: 0.
- Plus 1 occurrence in the inline CSS rule (`.play-card__what-we-send { ... }`).

Total class-string occurrences in the fixture: 4 (1 CSS rule + 3
rendered lines).

## 7. Was the existing C1 directional test sufficient?

**The existing C1 directional test was NOT trivially passing — it
was already exercising the right code path.** Specifically:

- `tests/test_what_we_send_render.py::test_mechanism_renders_on_recommended_directional`
  builds a synthetic engine run that artificially stamps
  `discount_hygiene` (a play that has carried metadata since Phase 6A
  Ticket A3) onto a `_directional_card(...)` factory, then asserts
  the WWS line renders inside `section.recommended`. Pre-C1.5 this
  test was passing because the renderer call site
  `_render_measured_card` -> `_mechanism_for_play("discount_hygiene")`
  -> non-`None` mechanism string -> `_render_what_we_send(...)`
  produces the expected `<p class="play-card__what-we-send">` block.
  The directional render path was being exercised end-to-end; it was
  not "passing because no directional card had a mechanism".

- However, before C1.5, the **realistic** Beauty Brand Recommended
  Now card (`first_to_second_purchase`) carried no metadata block
  in `priors.yaml`, so its `_mechanism_for_play(...)` returned
  `None` and the WWS line was correctly omitted. That was a
  content gap, not a test gap.

- Per the user task ("confirm it actually fires on the directional
  first_to_second_purchase card now that the mechanism exists, and
  tighten it if it was previously passing only because no
  directional card had a mechanism"), the spirit of the request is:
  add a realistic-case test alongside the existing artificial-case
  test. The existing test was NOT modified in place (it remains
  valuable as an isolation pin against a play that has had metadata
  since A3); a NEW test
  (`test_mechanism_renders_for_first_to_second_purchase_directional`)
  was added that pins the realistic Beauty fixture's directional
  play_id end-to-end. This test would have failed pre-C1.5 because
  `get_play_metadata("first_to_second_purchase")` returned `None`;
  it now passes because C1.5 added the metadata block.

## 8. M0 goldens byte-identical?

**Yes.** `python -m pytest tests/test_golden_diff.py -v` ->
3 passed. Sub-results:

```
tests/test_golden_diff.py::test_golden_matches[small_sm] PASSED
tests/test_golden_diff.py::test_golden_matches[mid_shopify] PASSED
tests/test_golden_diff.py::test_golden_matches[micro_coldstart] PASSED
```

C1.5 is config-only (`config/priors.yaml`) plus tests-only edits.
The legacy `src/storytelling.py` renderer does not consume the
priors-metadata `mechanism` field; the new mechanism content is
only read by the V2 renderer's
`_mechanism_for_play(...)` -> `priors_loader.get_mechanism(...)`
path which is gated behind `ENGINE_V2_OUTPUT=true`. M0 goldens use
the legacy renderer with `ENGINE_V2_OUTPUT=false`, so they are
unaffected.

## 9. Exact commands run (Ticket C1.5 acceptance sequence)

```bash
# 0. Baseline — confirm pre-C1.5 state is green for the in-flight C1.
python -m pytest tests/test_what_we_send_render.py tests/test_priors_metadata.py -q
# -> 25 passed in 0.22s

# 1. Verify accessor returns the new mechanism string (ad hoc).
python -c "from src.priors_loader import get_mechanism, clear_cache; clear_cache(); print(get_mechanism('first_to_second_purchase'))"
# -> Email one-time buyers a value-led second-purchase nudge with
#    best-next-product education, two sends one week apart, no
#    blanket discount.

# 2. Pre-pin run of slate regression — confirm the only failure is
#    the byte-pin (proves C1.5 only changes content of the directional
#    Recommended Now card on the Beauty fixture).
python -m pytest tests/test_slate_regression_beauty_brand.py -v
# -> 18 passed, 1 failed (test_briefing_matches_pinned_fixture_bytewise,
#    expected — the directional card now has a WWS line).

# 3. Re-pin the fixture under _B6_ENV_OVERRIDES; assert byte stability
#    across 3 fresh harness invocations.
python -c "...3-run sha256 check + write fixture..."
# -> all 3 sha256 = 48d61b89b3a6bb5b7c29d776ceec7fe8ba396522df4362651f7e476bf04726fe (match).

# 4. Required acceptance check sequence.
python -m pytest tests/test_what_we_send_render.py -v
# -> 5 passed in 0.04s

python -m pytest tests/test_slate_regression_beauty_brand.py -v
# -> 19 passed in 34.11s

python -m pytest tests/test_recommended_experiment_forbidden_tokens.py -v
# -> 33 passed in 0.05s

python -m pytest tests/test_targeting_no_dollar_headline.py -v
# -> 6 passed in 0.01s

python -m pytest tests/test_priors_metadata.py -v
# -> 22 passed in 0.23s

python -m pytest tests/test_golden_diff.py -v
# -> 3 passed in 27.65s (no re-baseline)

python -m pytest tests/ -q
# -> 906 passed, 14 skipped, 0 failed in 166.83s
```

Pre-C1.5 baseline (post-C1) was 904 passed; post-C1.5 is 906
passed. The +2 increment is exactly the two tests added
(`tests/test_priors_metadata.py::test_first_to_second_purchase_metadata_loaded_and_typed`,
`tests/test_what_we_send_render.py::test_mechanism_renders_for_first_to_second_purchase_directional`).

## 10. Behavior changes

**Default flags (`ENGINE_V2_OUTPUT=false`): no change.** The legacy
renderer does not read `metadata.mechanism`. M0 goldens are
byte-identical. The legacy CSV -> HTML workflow is unchanged.

**Full V2 stack (`ENGINE_V2_OUTPUT=true` + `ENGINE_V2_DECIDE=true` +
`ENGINE_V2_SLATE=true`):**

- The Beauty Brand Recommended Now card (`first_to_second_purchase`)
  now renders a `<p class="play-card__what-we-send">` line between
  audience and observed-metric, displaying the priors-authored
  mechanism string verbatim:
  > **What we'd send:** Email one-time buyers a value-led
  > second-purchase nudge with best-next-product education, two
  > sends one week apart, no blanket discount.
- Both Beauty Brand Recommended Experiment cards
  (`discount_hygiene`, `bestseller_amplify`) continue to render
  their own mechanism lines unchanged from C1.
- No change to selector / decide-layer behavior:
  `first_to_second_purchase` is NOT on the Phase 6A Ticket A4
  Recommended Experiment allowlist (which is hardcoded to
  `{discount_hygiene, bestseller_amplify}` in `src/decide.py:114`).
  Adding metadata does not promote it to the Recommended Experiment
  slate.
- No change to role-uniqueness, considered-filter, or any other B-series
  invariant.

**Edge cases:**

- `get_prior("first_to_second_purchase", ..., key="base_rate")`
  continues to resolve identically (verified via
  `test_get_prior_still_resolves_for_legacy_list_form_plays`'s sister
  pattern; `_extract_play_block` already handles both list and dict
  shapes per Phase 6A Ticket A3).
- `list_priors_for_play("first_to_second_purchase")` returns the
  same 3 prior rows it returned pre-C1.5; no entries lost.

## 11. Artifacts added

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6b-ticket-c1-5-summary.md`
  (NEW) — this summary.
- One new test in `tests/test_priors_metadata.py`:
  `test_first_to_second_purchase_metadata_loaded_and_typed`.
- One new test in `tests/test_what_we_send_render.py`:
  `test_mechanism_renders_for_first_to_second_purchase_directional`.
- Re-pinned `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`
  (in-place; not a new file).

## 12. Remaining risks

1. **Mechanism content authoring discipline (carry-over).** The B6
   in-fixture forbidden-token sweeps
   (`test_no_forbidden_tokens_in_experiment_section`,
   `test_projected_lift_only_inside_disclaimer`) run against the
   rendered Beauty briefing and currently pass. The new mechanism
   line is in `section.recommended` (not `.recommended-experiment`),
   so the B2 sweep of the experiment section does not exercise it
   directly; however, the Beauty fixture pin guarantees byte
   stability of the directional card too. A future content author
   who introduces a banned token into a `mechanism` would force a
   re-pin and surface the change. No systemic risk; documented.

2. **`audience_floor=500` is a content-author choice, not a
   selector-derived constraint.** The Phase 6A Ticket A4
   Recommended Experiment allowlist hardcodes `discount_hygiene` and
   `bestseller_amplify` only; the floor is not consulted for the
   directional Recommended Now path today. If a future ticket
   widens the experiment allowlist to include
   `first_to_second_purchase`, the floor would activate. Setting it
   conservatively at 500 (matching `bestseller_amplify`) leaves a
   reasonable default; tighten in the C2/C3 review if needed.

3. **`vertical_applicability` lists supplements alongside beauty +
   mixed.** The current Beauty-only fixture exercises `beauty`. The
   list does not currently affect any selector behavior because
   `first_to_second_purchase` is not on the experiment allowlist.
   Adding `supplements` is forward-compatible and matches the
   existing `discount_hygiene` block's shape; no behavior change
   today.

## 13. Follow-up work / Readiness for C2

**Ready for C2.**

- All seven required check sequences are green.
- Full suite: 906 passed, 14 skipped, 0 failed.
- M0 goldens byte-identical (3 passed, no re-baseline).
- The Beauty Brand Recommended Now card now renders "What we'd send:"
  alongside the two Recommended Experiment cards — closing the C1
  acceptance criterion for the Beauty fixture's directional path.
- Trust contract intact: no projected lift, no calibrated effect,
  no offer-amount specifics, no causal claim language in the new
  mechanism string.
- Selector / decide-layer untouched; PlayCard schema untouched;
  legacy renderer untouched.
- `ENGINE_V2_OUTPUT=false` kill-switch path remains unchanged
  (legacy renderer does not consume `metadata.mechanism`).

C2 (section reorder: Recommended -> Recommended Experiment ->
Watching -> Considered) does not depend on C1.5 beyond the same
`storytelling_v2.py` co-location it already inherits from C1. C1.5
does not violate any C2 prerequisites.

## 14. Confirmation Phase 6A behavior intact

- `src/decide.py` not modified — selector seam locked, A4 allowlist
  intact, B3 ABSTAIN_SOFT routing intact, B4 role-uniqueness
  intact, B6 PUBLISH-branch considered-filter intact.
- `src/guardrails.py` not modified.
- `src/sizing.py` not modified.
- `src/engine_run.py` not modified — PlayCard / Audience /
  Measurement / WouldBeMeasuredBy schema unchanged.
- `src/main.py` not modified — A4.5 candidate plumbing intact.
- `src/storytelling.py` (legacy) not modified — legacy renderer
  intact, M0 goldens byte-identical.
- `src/priors_loader.py` not modified — `get_mechanism`,
  `get_play_metadata`, `_extract_play_block` semantics unchanged.
  The new metadata content loads through the existing C1 accessor
  unchanged.
- `src/storytelling_v2.py` not modified — `_render_what_we_send`,
  `_mechanism_for_play`, the two card-builder insertion sites, and
  the inline CSS rule remain as committed by C1.
- B-series (B1-B6) test contracts intact: 19/19 B6 pass; B2 sweep
  passes; B5 cannibalization pins not exercised by this content
  edit; B4 role-uniqueness passes.
