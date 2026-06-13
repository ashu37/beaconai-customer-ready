# Phase 6B Ticket C3 — Customer-facing play-title relabel

**Status:** Applied. Suite green (914 passed / 14 skipped / 0 failed). M0 goldens byte-identical. Beauty Brand pinned slate fixture refreshed and re-pinned by byte-equality. Founder-testing-only gating unchanged.

---

## 1. Approved Scope

A render-layer copy pass that swaps `<h3>` text on V2 cards from the snake_case-derived `_humanize_play_id(play_id)` (e.g. "Winback 21 45", "Bestseller Amplify") to the merchant-readable `display_name` already declared in `src/play_registry.py`. Internal `play_id` strings, `data-play-id` HTML attributes, audience seams, priors metadata, decide-layer logic, and `recommended_history.json` keys are all unchanged. Per the Phase 6B IM plan §6 acceptance criteria, the three pinned exemplars use the exact strings from the plan:

- `winback_21_45` → "Lapsed-buyer reactivation (3–6 weeks since last order)"
- `bestseller_amplify` → "Top-product re-targeting"
- `empty_bottle` → "Replenishment timing"

Other plays (`discount_hygiene`, `subscription_nudge`, `routine_builder`, `frequency_accelerator`, `aov_momentum`, `retention_mastery`, `journey_optimization`, `category_expansion`, `first_to_second_purchase`, `at_risk_repeat_buyer_rescue`, `onsite_funnel_watch`) were authored in the same marketing-manager voice (concise, no jargon, no offer specifics, no causal claims, no dollar amounts, ≤ 60 chars).

No schema change — the existing `display_name` slot is reused. No selector / decide / guardrail / sizing changes. No legacy renderer changes. M0 goldens untouched.

---

## 2. Patch Summary

1. **`src/play_registry.py`** — Updated the `display_name` string on every legacy-emitted play (11 entries) plus the three T2.3 reserved entries (`first_to_second_purchase`, `at_risk_repeat_buyer_rescue`, `onsite_funnel_watch`). All other fields (`play_id`, `evidence_class_default`, `audience_builder_ref`, `measurement_metric`, `vertical_applicable`, `subvertical_applicable`, `prior_keys`, `targeting_disclaimer`, `notes`) are byte-unchanged.

2. **`src/storytelling_v2.py`** — Added a private `_card_title_for(play_id)` helper that lazily imports `play_registry.PLAYS` (mirroring the lazy `priors_loader` pattern from C1's `_mechanism_for_play`), returns `PLAYS[play_id].display_name` when registered with a non-empty string, and falls back to `_humanize_play_id` for unknown / future / empty inputs. Switched the four `<h3>` call sites — `_render_targeting_card`, `_render_measured_card`, `_render_recommended_experiment_card`, `render_rejected_card` — from `_humanize_play_id(...)` to `_card_title_for(...)`. The `_humanize_play_id` function itself is unchanged and still used as the fallback path. The `data-play-id` attribute and all other markup are unchanged.

3. **`tests/test_display_name_render.py`** — New test file (4 named tests; one is parametrized over 3 pinned plays for 6 cases total). Pins the registry-display-name path, the unknown-play-id fallback path, the `data-play-id` snake_case invariant across all three card sections, and the IM-plan exemplar copy verbatim.

4. **`tests/test_phase5_considered_always.py`** + **`tests/test_phase5_measured_pathway.py`** — Two pre-C3 tests asserted the old `_humanize_play_id`-derived V2 titles ("First To Second Purchase", "Bestseller Amplify", "Subscription Nudge"). Updated to assert the new merchant-readable display_names. Tests still cover the same render-path contracts; only the literal title strings changed.

5. **`tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`** — Re-pinned via the synthetic harness with the same `_B6_ENV_OVERRIDES` superset used by the B6 regression test (`ENGINE_V2_OUTPUT=true`, `ENGINE_V2_DECIDE=true`, `ENGINE_V2_SLATE=true`, `ENGINE_V2_SIZING=true`, `VERTICAL_MODE=beauty`, `WINDOW_POLICY=auto`). New `<h3>` titles surface on all 7 cards (1 Recommended Now, 2 Experiments, 4 Considered). Byte-stability verified by 3 fresh harness invocations.

---

## 3. Files Changed

```
 M src/play_registry.py
 M src/storytelling_v2.py
 M tests/test_phase5_considered_always.py
 M tests/test_phase5_measured_pathway.py
 M tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html
?? tests/test_display_name_render.py
```

| Path | Description |
|---|---|
| `src/play_registry.py` | Updated `display_name` on 14 PlayDef entries. Schema, `play_id`s, all other fields unchanged. |
| `src/storytelling_v2.py` | Added `_card_title_for(play_id)` helper (lazy import of `play_registry.PLAYS`; falls back to `_humanize_play_id`). Switched 4 `<h3>` call sites. |
| `tests/test_display_name_render.py` (NEW) | 4 named tests (6 cases) pinning the registry-title contract, the fallback contract, the `data-play-id` invariant, and the IM-plan exemplar copy. |
| `tests/test_phase5_considered_always.py` | Updated 3 literal title assertions to the new merchant-readable copy. Render-path contract unchanged. |
| `tests/test_phase5_measured_pathway.py` | Updated 1 literal title assertion to the new merchant-readable copy. Render-path contract unchanged. |
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | Refreshed via harness. sha256 `5fa9f697...` → `dcb45cee...`; byte length 13,278 → 13,408 (delta = +130 bytes from the new merchant-readable titles, including one 3-byte UTF-8 en-dash in `winback_21_45`). |

---

## 4. Exact display_name mapping table (old → new)

| play_id | OLD display_name | NEW display_name | Length |
|---|---|---|---|
| `winback_21_45` | `Winback 21-45` | `Lapsed-buyer reactivation (3–6 weeks since last order)` | 54 |
| `bestseller_amplify` | `Bestseller Amplify` | `Top-product re-targeting` | 24 |
| `discount_hygiene` | `Discount Hygiene` | `Discount-dependence cleanup` | 27 |
| `subscription_nudge` | `Subscription Nudge` | `Subscribe-and-save invitation for repeat buyers` | 47 |
| `routine_builder` | `Routine Builder` | `Complete-the-routine bundle` | 27 |
| `empty_bottle` | `Replenishment Reminder` | `Replenishment timing` | 20 |
| `frequency_accelerator` | `Frequency Accelerator` | `Repeat-purchase cadence nudge` | 29 |
| `aov_momentum` | `AOV Momentum` | `Basket-size momentum watch` | 26 |
| `retention_mastery` | `Retention Mastery` | `At-risk repeat-buyer rescue` | 27 |
| `journey_optimization` | `Journey Optimization` | `Post-first-purchase journey nudge` | 33 |
| `category_expansion` | `Category Expansion` | `Cross-category discovery for single-category buyers` | 51 |
| `first_to_second_purchase` | `First-to-Second Purchase` | `Second-purchase nudge for one-and-done buyers` | 45 |
| `at_risk_repeat_buyer_rescue` | `At-Risk Repeat Buyer Rescue` | `At-risk repeat-buyer rescue` | 27 |
| `onsite_funnel_watch` | `Onsite Funnel Watch` | `Onsite funnel watch` | 19 |

All strings are within the 60-character hard cap and ≤ 8 words where practical (the longest is `winback_21_45` at 7 words; the parenthetical "(3–6 weeks since last order)" is intentional per the IM plan and is the only entry that uses parenthetical scoping). No entry contains offer specifics, causal claims ("will lift"), dollar amounts, or projected-lift language. None of the legacy "Title Case the snake" titles survive — every title now reads like a marketing manager wrote it.

---

## 5. Forbidden-token compliance check on the new display_name strings

Programmatic sweep of every new `display_name` against the union of B2 / B6 universal-forbidden tokens plus the C2 expanded list (`calibrated`, `uplift`, `ATE`, `ITT`, `treatment effect`, `expected lift`, `forecast`, `predicted`, `p =`, `q =`, `p-value`, `q-value`, `confidence_score`, `final_score`, `p_internal`, `ci_internal`, `Aura`, `Beacon Score`, `beacon_score`, `projected lift`, `$`, `20% off`, `will lift`):

```
CLEAN: no forbidden tokens in any new display_name
```

The B6 in-fixture forbidden-token sweeps (`test_no_forbidden_tokens_in_experiment_section` and `test_projected_lift_only_inside_disclaimer`) both pass against the refreshed Beauty fixture, confirming the new titles do not leak any banned tokens into `section.recommended-experiment`.

---

## 6. Old → New Beauty fixture sha256, length, byte-stability

| Field | Pre-C3 | Post-C3 |
|---|---|---|
| sha256 | `5fa9f697967566eab1a3d66a2d7edd6776b68cc166ca9677262f9e5f84e80b53` | `dcb45ceefe5f4dd44cc05e4e539df75402cf7fe80abf4a4757ce69b8f2e0f3bb` |
| Byte length | 13,278 | 13,408 |
| Character length | 13,278 | 13,406 |

Note: The 2-byte gap between byte-length (13,408) and character-length (13,406) is the single 3-byte UTF-8 en-dash `–` in the `winback_21_45` display_name "Lapsed-buyer reactivation (3–6 weeks since last order)". All other characters in the fixture are ASCII. Both numbers are deterministic and reproducible.

### Byte-stability (3 fresh harness invocations, mirroring C1.5 / C2 protocol)

```
Run 1 (in-place write):  13,408 bytes  sha256 dcb45ceefe5f4dd44cc05e4e539df75402cf7fe80abf4a4757ce69b8f2e0f3bb  CANONICAL
Run 2 (tempdir):         13,408 bytes  sha256 dcb45ceefe5f4dd44cc05e4e539df75402cf7fe80abf4a4757ce69b8f2e0f3bb  MATCH
Run 3 (tempdir):         13,408 bytes  sha256 dcb45ceefe5f4dd44cc05e4e539df75402cf7fe80abf4a4757ce69b8f2e0f3bb  MATCH
```

All 3 invocations produced byte-identical output. The fixture is deterministic.

---

## 7. Exact Commands Run

```bash
# 1. Verified pre-C3 fixture state
shasum -a 256 tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html
# → 5fa9f697... 13278 bytes

# 2. Edited src/play_registry.py to update 14 display_name entries

# 3. Edited src/storytelling_v2.py:
#    - added _card_title_for() helper after _humanize_play_id()
#    - switched 4 <h3> call sites to _card_title_for()

# 4. Created tests/test_display_name_render.py
python -m pytest tests/test_display_name_render.py -v
# → 6 passed in 0.05s

# 5. Confirmed M0 goldens byte-identical
python -m pytest tests/test_golden_diff.py -v
# → 3 passed in 27.35s

# 6. Refreshed the Beauty Brand fixture via the harness (same env superset
#    as the B6 regression test)
python /tmp/refresh_b6_fixture.py
# → Wrote tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html
# → sha256: dcb45ceefe5f4dd44cc05e4e539df75402cf7fe80abf4a4757ce69b8f2e0f3bb

# 7. Byte-stability check (runs 2 + 3, with run 1 = the write above)
python /tmp/c3_byte_stability.py
# → All 3 invocations produced byte-identical output.

# 8. Re-ran B6 in full
python -m pytest tests/test_slate_regression_beauty_brand.py -v
# → 19 passed in 34.47s

# 9. First full-suite run revealed 2 pre-C3 tests pinning the literal old V2
#    titles ("First To Second Purchase", "Bestseller Amplify",
#    "Subscription Nudge"). Both updated to the new merchant-readable
#    display_names; render-path contracts unchanged.
python -m pytest tests/test_phase5_considered_always.py tests/test_phase5_measured_pathway.py -v
# → 24 passed in 0.23s

# 10. Final full-suite run
python -m pytest tests/ -q
# → 914 passed, 14 skipped, 200 warnings in 168.03s

# 11. Re-confirmed M0 + B6 forbidden-token sweeps after the rerun
python -m pytest tests/test_golden_diff.py \
    tests/test_slate_regression_beauty_brand.py::test_no_forbidden_tokens_in_experiment_section \
    tests/test_slate_regression_beauty_brand.py::test_projected_lift_only_inside_disclaimer -v
# → 5 passed in 52.63s

# 12. Visual sanity on the refreshed fixture
python3 -c "
import re
html = open('tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html', encoding='utf-8').read()
articles = re.findall(r'<article[^>]*data-play-id=\"([^\"]+)\"[^>]*>.*?<h3 class=\"play-card__title\">([^<]+)</h3>', html, re.DOTALL)
for pid, title in articles: print(f'{pid:32s} -> {title!r}')
"
# → All 7 cards: snake_case data-play-id intact + merchant-readable display_name in <h3>
```

---

## 8. Test Results

| Lane | Result |
|---|---|
| `tests/test_display_name_render.py` (NEW) | 6 passed |
| `tests/test_slate_regression_beauty_brand.py` (B6) | 19 passed |
| `tests/test_golden_diff.py` (M0) | 3 passed |
| `tests/test_phase5_considered_always.py` | 9 passed |
| `tests/test_phase5_measured_pathway.py` | 15 passed |
| `tests/test_what_we_send_render.py` (C1 / C1.5) | 5 passed |
| `tests/test_storytelling_v2_layout.py` (C2) | 2 passed |
| **Full `pytest -q`** | **914 passed / 14 skipped / 0 failed** |

**Suite count delta: 908 → 914** (+6 new tests in `test_display_name_render.py`; the 4 named tests + 1 parametrized over 3 pinned plays = 4 + 2 = 6 collected cases, since `test_renderer_uses_play_registry_display_name`, `test_renderer_falls_back_to_humanize_for_unknown_play_id`, and `test_data_play_id_attribute_is_internal_snake_case` are 1-each and `test_display_name_is_merchant_readable_for_pinned_plays` is 3 cases, total 6).

---

## 9. Behavior Changes

**Default-flag path (M0 / `ENGINE_V2_OUTPUT=false`):** No change. The legacy `src/storytelling.py` renderer is untouched. M0 goldens (`small_sm`, `mid_shopify`, `micro_coldstart`) remain byte-identical.

**Full V2 stack (`ENGINE_V2_DECIDE=true` + `ENGINE_V2_OUTPUT=true` + `ENGINE_V2_SLATE=true`):** Card `<h3>` text now reads as merchant-readable copy authored in marketing-manager voice (e.g. "Lapsed-buyer reactivation (3–6 weeks since last order)" instead of "Winback 21 45"). The `data-play-id` attribute on every `<article>` continues to carry the original snake_case `play_id` byte-for-byte, so log analysis, history files (`recommended_history.json`), and engineering tooling all continue to read the stable internal identifier. No copy elsewhere on the card has changed. Section ordering, badges, mechanism lines (C1), opportunity context blocks, would-be-measured-by lines, and disclaimers are all byte-unchanged.

**Engine-visible:** None. `decide()`, `_select_recommended_experiments`, the role-uniqueness invariant, the abstain branches, the priors loader, and the typed `EngineRun` schema are all untouched.

---

## 10. M0 byte-identity confirmation

```
$ python -m pytest tests/test_golden_diff.py -v
PASSED tests/test_golden_diff.py::test_golden_matches[small_sm]
PASSED tests/test_golden_diff.py::test_golden_matches[mid_shopify]
PASSED tests/test_golden_diff.py::test_golden_matches[micro_coldstart]
3 passed in 27.35s
```

M0 fixtures (`small_sm`, `mid_shopify`, `micro_coldstart`) are byte-identical pre- and post-C3. The legacy renderer in `src/storytelling.py` does not read `play_registry.display_name`; it reads `src/copykit.py`-managed strings, neither of which were touched.

---

## 11. Phase 6A / 6B C1 / C1.5 / C2 contracts intact

- **Phase 6A Ticket A1** (Watching cap=4 + load-bearing pin) — Untouched. C3 is render-string-only.
- **Phase 6A Ticket A2** (`WouldBeMeasuredBy` enum + `PlayCard` field; UPPER_SNAKE_CASE values) — Untouched. The renderer's `_would_be_measured_by_display` lookup is unchanged.
- **Phase 6A Ticket A3** (priors metadata loader; dual list/dict YAML) — Untouched. C3 does not consult `priors.yaml`.
- **Phase 6A Ticket A4** (Recommended Experiment selector behind `ENGINE_V2_SLATE`; allowlist + cap 2 + abstain⇒[]) — Untouched. C3 does not change selector logic.
- **Phase 6A Ticket A4.5** (`main.py` plumbs Phase 5 candidates into `decide()`) — Untouched.
- **Phase 6A Tickets B1 + B1.5** (Recommended Experiment renderer + `opportunity_context`) — Untouched. C3 does not change the opportunity context block, the AOV-source plumbing, or the lazy `_build_opportunity_context` import.
- **Phase 6A Ticket B2** (scoped forbidden-token sweep on `section.recommended-experiment`; "projected lift" allowlisted only inside the verbatim `OPPORTUNITY_CONTEXT_DISCLAIMER` constant) — Verified clean against the refreshed fixture; the new merchant-readable display_names contain none of the universal-forbidden tokens.
- **Phase 6A Ticket B3** (`ABSTAIN_SOFT` routes experiment-eligible held plays to Considered with `TARGETING_HELD_UNDER_ABSTAIN`; `publish_shadow` kwarg; abstain-zero contract enforced at `decide()` seam) — Untouched.
- **Phase 6A Ticket B4** (role-uniqueness invariant in `decide.py`; Watching exempt by design) — Untouched.
- **Phase 6A Ticket B6** (Beauty pinned slate fixture + decide-layer post-experiment Considered filter; 19 tests) — All 19 tests pass against the refreshed fixture (`5fa9f697... → dcb45cee...`).
- **Phase 6A Final Review caveats 1–6** — No regressions. Founder-testing-only gating unchanged.
- **Phase 6B Ticket C1** ("What we'd send" mechanism line on Recommended Now + Experiment cards; `_mechanism_for_play` lazy import; `WHAT_WE_SEND_CLASS`) — Untouched. The `<h3>` title and the mechanism line are independent render seams and now coexist on every Recommended card with a merchant-readable title above the mechanism.
- **Phase 6B Ticket C1.5** (`first_to_second_purchase` promoted to A3 dict form with mechanism) — Untouched. The C1.5 mechanism string still surfaces on the directional card, now under the merchant-readable display_name "Second-purchase nudge for one-and-done buyers".
- **Phase 6B Ticket C2** (section reorder: Recommended Now → Recommended Experiment → Watching → Considered → DQ-footer) — Untouched. All four sections render in the C2 order in the refreshed Beauty fixture.

---

## 12. Readiness for Ticket C4

The patch is complete for Ticket C3. Stopping per the orchestrator hand-back contract.

Pre-conditions for Ticket C4 (never-empty Watching copy fallback for stores with sufficient history) are unchanged:

- The V2 renderer remains a pure function over `EngineRun`. C4 will branch inside `_render_watching_section` on `engine_run.watching` emptiness + history-window >=180d + State-of-Store directional Observation availability.
- The card title plumbing established by C3 is fully isolated from the Watching section (Watching renders metric rows, not cards). C4 can safely add a `watching-row--fallback` row variant without touching `_card_title_for`.
- The Beauty fixture (post-C3 sha256 `dcb45cee...`) has a non-empty Watching list (1 row: AOV directional). C4 should NOT change the Beauty fixture bytes because Beauty's Watching is already populated; the fallback branch will never fire there. C4 will need separate fixture coverage for the empty-Watching + 240d-history case (e.g. via a small_store_240d-shaped scenario), per the IM plan §4 fixture-touched table.
- M0 goldens, the legacy `storytelling.py` renderer, `decide.py`, `guardrails.py`, `sizing.py`, `copykit.py`, and `priors.yaml` schema all remain locked for the rest of Phase 6B per the C1–C4 charter.

Do not proceed to Ticket C4. Hand back to the orchestrator.
