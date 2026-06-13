# S5-T2 — KI-20 supplements first_to_second_purchase typed honest abstain

**Owner:** code-refactor-engineer (Sprint 5, ticket S5-T2)
**Date:** 2026-05-13
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §11, ticket S5-T2 (lines 592-598)
**Predecessor:** S5-T1 ([code-refactor-engineer-s5-t1-summary.md](./code-refactor-engineer-s5-t1-summary.md))
**Status:** Complete. Schema unchanged (`event_version=1` frozen; additive enum value).

---

## 1. Approved scope

Resolves KI-20. The Phase 5.6 directional builder
(`measurement_builder.build_directional_play_card`) reads
`returning_customer_share` on the L28 primary window. Typical
supplement reorder cadences (28-45 days) straddle that boundary,
making the supporting state statistic structurally too stable on the
supplements vertical to clear `PHASE5_DIRECTIONAL_P_MAX`. Per the
plan, two viable paths:

- **Path (a)** — widen the directional builder's window for
  supplements (or vertical-dispatch the window choice).
- **Path (b)** — typed abstain `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW`
  surfaced in the Considered list.

Path (a) would have required a fresh cohort-definition design for the
wider window and risked re-introducing the Berkson-shaped confounding
that the B-5 invariant blocks. The plan explicitly flags this risk:
"If path (a) cohort design feels non-trivial, STOP and request
ecommerce-ds-architect review before coding." Path (b) is the
documented fallback when widening threatens cohort integrity.

This ticket ships **path (b)**. Path (a) is not foreclosed — a future
ticket with explicit DS-architect review can replace this typed
abstain with a widened cohort-coherent measurement design.

## 2. Patch summary

### `src/engine_run.py`

Added enum member `ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW =
"supplement_cadence_outside_window"`. Additive within
`event_version=1`; the lowercase-string value convention matches every
other `ReasonCode` member.

### `src/decide.py`

Added `_CONSIDERED_REASON_TEXT[SUPPLEMENT_CADENCE_OUTSIDE_WINDOW]`
(decide-layer hold copy) and
`_WOULD_FIRE_IF_TEMPLATE[SUPPLEMENT_CADENCE_OUTSIDE_WINDOW]` (the
forward-looking would-fire-if hint). Both reference the structural
mechanism (first-to-second nudge / L28 returning-customer-share
proxy) at the decide layer; merchant-jargon-free copy is the
renderer's job.

### `src/storytelling_v2.py`

Added merchant-readable phrasing to `_humanize_reason_code`. Copy
avoids "L28", "p-value", and "cadence" per M8 forbidden-token
discipline (Phase 5.4); pinned by
`test_renderer_humanizes_new_code_without_jargon`.

### `src/main.py`

After the Phase 5.6 directional builder attempt and BEFORE
`populate_considered_from_candidates`, on the supplements vertical
only:

1. Check whether `first_to_second_purchase` made it into
   `engine_run.recommendations` (Beauty's directional path does this;
   supplements does not).
2. If not, find the matching M3 candidate from `_phase5_cands` and
   PREPEND a typed `RejectedPlay` with
   `ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` to
   `engine_run.considered`.

Prepending matters: `populate_considered_from_candidates` ends with
`_dedupe_rejections(merged)[:MAX_CONSIDERED_RENDERED]`
(`MAX_CONSIDERED_RENDERED = 6`). The supplements run today has six
generic Considered cards already; without the prepend, the typed
abstain would be dropped at the cap-trim and KI-20 would silently
regress.

The directional builder itself
(`measurement_builder.build_directional_play_card`) is NOT modified.
B-5 Berkson invariant remains vacuously preserved on this surface
because no cohort-definition logic was touched. The
`tests/test_berkson_invariant.py` suite passes green.

### Fixture re-pin

`tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html`
sha256:

| | Pre-S5-T2 | Post-S5-T2 |
|---|---|---|
| sha256 | `feb03500c1adc4a8a8a6762c6f0c98fd2a81ba2a9d3838d75ccca0ea221a0e0d` | `a7def447872b7780cb09ce54ad7c8a64f1891c71ee3ed3cf66447b76cb32415b` |

Behavioral delta: one new Considered card
(`first_to_second_purchase` with
`reason_code=supplement_cadence_outside_window`) prepended;
`frequency_accelerator` displaced at the 6-card cap.

## 3. Files changed

| File | Change |
|---|---|
| `src/engine_run.py` | New `ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` enum member |
| `src/decide.py` | `_CONSIDERED_REASON_TEXT` + `_WOULD_FIRE_IF_TEMPLATE` entries |
| `src/storytelling_v2.py` | `_humanize_reason_code` merchant-readable copy |
| `src/main.py` | New ~40-line block after directional-builder attempt, gated to `vertical == supplements`, emitting the typed prepended Considered card |
| `tests/test_s5_t2_supplement_cadence_abstain.py` | NEW — 8 tests |
| `tests/test_engine_run_schema.py` | `test_all_reason_codes_declared` updated to 14-code expected set |
| `tests/test_slate_regression_supplements_brand.py` | `PINNED_SHA256` + `EXPECTED_CONSIDERED_PLAY_IDS` re-pinned (S5-T2) |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | Re-generated under post-S5-T2 engine |
| `KNOWN_ISSUES.md` | KI-20 `open` → `resolved`; KI-23 progress note + membership shift; open-count 13 → 12 |
| `memory.md` | Sprint 3 section gains S5-T2 entry (template-shape, ≤15 lines) |
| `agent_outputs/code-refactor-engineer-s5-t2-summary.md` | NEW — this file |

## 4. Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s5_t2_supplement_cadence_abstain.py` | 8/8 green |
| `tests/test_engine_run_schema.py` | green |
| `tests/test_slate_regression_supplements_brand.py` | 12/12 green (sha256 `a7def44787...` matches re-pinned fixture) |
| `tests/test_slate_regression_beauty_brand.py` | 19/19 green (Beauty pinned slate sha256 unchanged) |
| `tests/test_berkson_invariant.py` | green (B-5 invariant intact) |
| `tests/test_golden_diff.py` | 3/3 green (M0 Beauty / small_sm / mid_shopify / micro_coldstart byte-identical) |
| Full suite (`pytest -q`) | **1175 passed, 14 skipped, 1 failed** in 772s (was 1168/14/0 at S5-T1). The 1 failure (`test_inventory_updated_at_is_fresh`) is a pre-existing wall-clock drift in the inventory CSV fixture; confirmed at baseline HEAD before S5-T2 and unrelated to this ticket. Delta = +7 S5-T2 acceptance tests. |

## 5. Behavior changes

- Supplements run now surfaces `first_to_second_purchase` in
  Considered with `reason_code=supplement_cadence_outside_window`.
  Previously it dropped silently between M3 detection and the
  Considered render (KI-20 / KI-23).
- Supplements Considered cap-trim drops `frequency_accelerator`
  (previously 6th) to make room.
- Beauty / `mixed` paths: zero change. Beauty pinned slate sha256
  unchanged; Beauty `first_to_second_purchase` still ships as the
  directional Recommended Now card it did pre-S5-T2.
- `event_version=1` payloads: additive only (new enum value); Swarm
  consumers that pattern-match on the existing 13 codes are
  unaffected.

## 6. Artifacts added

- `tests/test_s5_t2_supplement_cadence_abstain.py` (KI-20 acceptance)
- `agent_outputs/code-refactor-engineer-s5-t2-summary.md` (this file)

## 7. Remaining risks

1. **Path (b) is honest but does not unlock Recommended Now on
   supplements.** A future ticket (with ecommerce-ds-architect review)
   can replace this typed abstain with a widened
   cohort-coherent measurement design (path (a)); the typed enum value
   stays a useful fallback while that design is in flight.
2. **The supplements `frequency_accelerator` card no longer renders
   in Considered.** Cap displacement is documented in the
   `EXPECTED_CONSIDERED_PLAY_IDS` test docstring and KI-23 progress
   note. If a future ticket raises `MAX_CONSIDERED_RENDERED`, the
   supplements fixture re-pins.
3. **Pre-existing inventory-freshness test (`test_inventory_updated_at_is_fresh`)
   is failing on the runner clock today (9 days vs 7-day max).** Not
   in S5-T2 scope; resolved by regenerating the synthetic inventory
   CSV fixture against today's wall clock in a separate ticket. The
   baseline confirmation (HEAD before S5-T2 also fails on this test)
   is in the impl commit message.

## 8. Follow-up work / dependencies

- **S5-T3** (KI-22 repeat-rate-cadence flag) takes the next
  fixture-re-pin slot on supplements per plan §11. Coordinate with the
  current sha256 (`a7def44787...`).
- **Path (a) directional-builder window-widening** (separate Sprint 6+
  ticket scope, requires ecommerce-ds-architect review per the plan's
  STOP-AND-REVIEW clause). This S5-T2 path (b) is a stable fallback
  until that design ships.
- **Inventory CSV fixture refresh** is a separate ticket (pre-existing
  failure, not in S5-T2 scope).

## 9. Branch shape

Three commits on `post-6b-restructured-roadmap` (not pushed),
following the per-commit ritual:

1. `dae9e9c` — `S5-T2: KI-20 supplements first_to_second_purchase typed honest abstain` (impl + 8 new tests + supplements re-pin + KI-20/KI-23 flips)
2. `a39504c` — `Document S5-T2 in repo memory.md`
3. _this commit_ — `S5-T2 summary` (this file)

## 10. Hard constraints respected

- `engine_run.json` schema **unchanged** in shape — new
  `ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` is additive within
  the Sprint 2 `event_version=1` freeze. No field reshape; no
  breaking change to Swarm consumers.
- `event_version=1` payloads **frozen** — no payload field shape
  changes.
- D-6 enforced — no banned ML modules touched.
- D-8 enforced — vertical scope unchanged (`{beauty, supplements,
  mixed}`); the new emit is `supplements`-gated, not a backdoor for
  unsupported verticals.
- M0 Beauty pinned fixture sha256 **unchanged**.
- Beauty pinned slate sha256 **unchanged** at `45edaca5...`
  (`tests/test_slate_regression_beauty_brand.py` 19/19 green).
- Supplements G-1 fixture re-pinned `feb03500c1...` → `a7def44787...`
  (deliberate; documented in commit + KNOWN_ISSUES).
- B-5 Berkson invariant intact — directional builder cohort logic
  untouched.
- S-2 / S-3 / S-4 / S-5 / S-6 substrate write paths **untouched**.
- `config/priors.yaml` (G-3 surface) **untouched**.
- No new runtime dependencies.
