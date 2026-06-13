# Implementation Plan — Campaign Slate

_Author: Implementation Manager_
_Date: 2026-05-04_
_Inputs: `agent_outputs/campaign-slate-contract-final.md`, `memory.md`, synthetic-fix summaries 1–11, current `src/` code._

This plan converts the accepted Campaign Slate contract into a phased, low-risk engineering sequence. Every ticket is PR-sized, TDD-first, and leaves the engine runnable. No causal priors. No production integrations. No `revenue_range.suppressed=false` on experiments. No restoration of forbidden tokens. All eleven synthetic-blocker fixes are preserved.

## Implementation Verdict

**Proceed.** The contract is implementable as a 12-ticket sequence behind a single new feature flag (`ENGINE_V2_SLATE`, default OFF) that flips on additively. The work is additive on top of M0–M9 + Phase 5.1 + synthetic Fixes 1–11 and does not require a schema-version bump, a renderer rewrite, or any deferred Phase 6 prerequisite (inventory loader fix, AnomalousWindow auto-registration, ct/lb parser). Risk to the legacy CSV → HTML workflow and to the V2 path with the flag off is mechanically zero, because every change is gated either at the renderer (new section), at the decide layer (new eligibility filter), or as additive metadata in `config/priors.yaml` and `engine_run.PlayCard`.

The decisive constraints driving the sequencing:

- The `would_be_measured_by` enum and the priors-metadata block are upstream blockers. They must land before any decide-layer eligibility filter, because the filter reads them.
- `Watching` cap reduction (7 → 4) is independent of slate work and can ship in any ticket; we sequence it first as a confidence-builder PR and a hedge on golden movement.
- The new role-uniqueness invariant must land **after** the experiment-eligibility filter so the assertion has something to assert against. Landing it first against the current code path would be a no-op.

## Phase Name

**Phase 6A — Campaign Slate.** Justification:

- M0–M9 + Phase 5 + Phase 5.1 are the canonical numbered phases in `memory.md`. Phase 6 is reserved by the `memory.md` Phase 5 close-out for the AnomalousWindow auto-register, the inventory loader fix, the `empty_bottle` ct/lb parser, and the calibration outcome-log read.
- The Campaign Slate is structurally distinct: it is a renderer + decide-layer surface change, not a Phase 6 architectural reorder.
- Calling it Phase 6A makes it parallel-trackable with the deferred Phase 6 chores (which we will refer to here as Phase 6B follow-ups) and keeps `memory.md` numbering coherent.
- We deliberately do NOT call this "Phase 5.7" because the Phase 5 series was scoped to one directional pathway + opportunity context. Adding a new role section is a meaningful UX change and warrants a phase boundary.

## Scope

In scope (this plan):

1. New role section: `Recommended Experiment` (cap 2, allowlist `discount_hygiene` + `bestseller_amplify`).
2. New PlayCard field: `would_be_measured_by` (enum-backed, additive).
3. Priors metadata: `audience_floor`, `mechanism`, `vertical_applicability`, `would_be_measured_by`, `audience_archetype` per play in `config/priors.yaml`.
4. New decide-layer eligibility filter for Recommended Experiment role.
5. Cannibalization gate vs Recommended Now (`<30%` audience overlap).
6. Slate diversity rule: no two Recommended Experiment cards with the same `audience_archetype` per run.
7. ABSTAIN_SOFT extension: zero Recommended Experiment cards (mirrors Fix 3).
8. Role-uniqueness invariant: no PlayCard appears in two role sections in the same run.
9. Watching cap reduction (7 → 4) and load-bearing-metric prioritization pin on `small_store_240d`.
10. Reuse Phase 5.1 opportunity-context block verbatim on Recommended Experiment cards.
11. Forbidden-token sweep extension on Recommended Experiment cards.
12. Beauty Brand pinned slate-regression fixture under `tests/fixtures/`.
13. Single feature flag `ENGINE_V2_SLATE` (default OFF) routing the new behavior.

Out of scope (explicit):

- Lifecycle Maintenance section.
- Recently-run-fatigue gate as anything other than a NO-OP.
- `recommended_history.json` reads (calibration_stub stays a stub).
- Any new Recommended Experiment plays beyond the two-play allowlist.
- AnomalousWindowCheck auto-registration.
- `src/load.py:626` pandas-compat fix.
- `empty_bottle` ct/lb/mg parser.
- M10 cleanup / V2 default flip.
- Causal priors. Calibrated lift. Promotion of any directional card to measured.
- Unsuppressing `revenue_range` on any card.
- Lowering materiality floors.
- Removing or weakening Fixes 1–11.
- Klaviyo / Shopify integration. `email_attributed_revenue_*` outcome metrics.

## Non-Goals

- Reducing the engine to a checklist or a rules engine.
- Promoting any expert prior to causal.
- Fabricating measurement on Recommended Experiment cards.
- Surfacing `would_be_measured_by` as free text. Always enum-backed or omitted.
- Renaming or restructuring `EngineRun` schema versions. (Additive field only.)
- Breaking M0 byte-identical legacy goldens.

## Open Decisions Resolved

Each maps to a "Question for Implementation Manager" in `agent_outputs/campaign-slate-contract-final.md`.

1. **PlayCard schema migration (Q1).** Additive field on `PlayCard` in `src/engine_run.py`. No `schema_version` bump. Justification: the field is `Optional[<enum>]`, defaults to `None`, round-trips through `to_dict` / `from_dict` without breaking either consumer. Existing receipts emit `would_be_measured_by: null` for measured/directional/targeting cards that are not Recommended Experiment, which is forward-compatible with any future caller. Schema_version is reserved for breaking-change scenarios; this is not one.
2. **Priors metadata expansion (Q2).** Single milestone, two tickets: ticket A2 lands the YAML schema and the loader change; ticket A3 wires the loader output into the decide layer. The reason it splits cleanly is that A2 has zero behavioral impact (config-only) and can be reviewed/landed by itself; A3 is purely consumption.
3. **Audience archetype taxonomy (Q3).** DS authors the enum. Plan locks the initial set: `{first_time_buyer, lapsed_buyer, discount_buyer, hero_sku_buyer, replenishment_buyer, full_price_buyer, vip_loyalist, no_archetype}`. `no_archetype` is the conservative fallback so a play missing an archetype does not silently match every other play. Stored as `audience_archetype: <enum_string>` per play in `config/priors.yaml`. PM signs off before the renderer ticket lands.
4. **Renderer change scope (Q4).** Reuse the existing measured/targeting card partials in `src/storytelling_v2.py` with role-aware copy. A new `render_recommended_experiment_section` function lives alongside `render_recommended_section` and shares `render_play_card`. No new template engine, no Jinja change. Forbidden-token sweep is extended via `tests/test_phase5_no_aura_beacon.py` plus a new `tests/test_recommended_experiment_forbidden_tokens.py`.
5. **PM/DS Lifecycle disagreement (Q5).** Reconciled position holds: defer Lifecycle. Recorded explicitly in this plan. PM does not need to re-confirm; if PM reverses, that becomes Phase 6C scope.
6. **Recommended Experiment cap (Q6).** **2** (DS-tightened). Hard cap. Encoded as `MAX_RECOMMENDED_EXPERIMENT: int = 2` in `src/decide.py`.
7. **Test sequencing (Q7).** TDD red-first for: new PlayCard field round-trip, priors-metadata schema, decide-layer eligibility filter, ABSTAIN_SOFT zero-experiments contract, role-uniqueness assertion, forbidden-token extension, Watching cap reduction, load-bearing-metric prioritization, Beauty Brand pinned regression. Property-test additions for: cap and overlap invariants. Goldens refresh: single checkpoint after the renderer ticket lands and stabilizes (only V2-flag-on goldens, NOT the M0 legacy goldens).
8. **Goldens (Q8).** M0 legacy goldens remain byte-identical. The new section only renders when `ENGINE_V2_OUTPUT=true` AND `ENGINE_V2_SLATE=true`. The synthetic-sample directory under `agent_outputs/synthetic_fixes_8_11_samples/` will be regenerated as the visual diff target. A new pinned slate fixture lives under `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` (see Ticket B6).
9. **Beauty Brand pinned regression (Q9).** Yes, but as a new fixture under `tests/fixtures/synthetic_slate/`, not as a M0 golden. Avoids accidental coupling to the legacy golden contract. Covered in Ticket B6.
10. **Phase numbering (Q10).** Phase 6A. See "Phase Name" above.

## Ordered Tickets

Execution proceeds A1 → A4 → B1 → B2 → B3 → B4 → B5 → B6 → B7. Each ticket's "rollback notes" describe the smallest revert that restores the prior pass-rate.

### Ticket A1 — Watching cap reduction + load-bearing prioritization pin

**Goal.** Reduce Watching cap from 7 (Phase 5.3) to 4. Pin a load-bearing-metric prioritization test so `returning_customer_share`, `net_sales`, `repeat_rate_within_window`, and `aov` always surface ahead of small movers when computable.

**Likely files.**
- `src/storytelling_v2.py` — Watching renderer (already caps at `[:4]` on line ~773; verify and add a constant `MAX_WATCHING_RENDERED = 4`).
- `src/decide.py` — `MAX_WATCHING_SIGNALS: int = 4` already exists; verify no upstream code emits >4.
- `src/state_of_store.py` (or wherever `build_watching` lives, established Phase 5.3) — confirm and tighten cap if higher than 4 anywhere.
- `tests/test_render_v2.py` — extend Watching tests.
- New: `tests/test_watching_load_bearing_priority.py` — pin prioritization on `small_store_240d` synthetic fixture.

**Acceptance criteria.**
- The rendered Watching section never contains more than 4 `li.watching-row` rows.
- On `small_store_240d`, if any of the four named load-bearing metrics is computable, at least one appears in the rendered Watching section.
- Existing Phase 5.3 behavior preserved: flat load-bearing metrics surface as "stable, watching" instead of being filtered out.
- M0 legacy goldens still byte-identical.

**Tests.**
- Red-first: `test_watching_section_caps_at_four` — synthesize 7 WatchedSignals, render, count `li.watching-row` matches → 4.
- Red-first: `test_small_store_load_bearing_at_least_one` — run the harness on `small_store_240d`, assert at least one of the four metrics appears in DOM.
- `tests/test_phase5_3_watching.py` (existing, where present) regression sweep.

**Rollback notes.** Revert the constant change and the test files. Single-PR. No data migration.

### Ticket A2 — `would_be_measured_by` enum + additive PlayCard field

**Goal.** Introduce the enum-backed `would_be_measured_by` field on `PlayCard`. Confirm round-trip persistence and explicit absence on measured/directional/targeting cards.

**Likely files.**
- `src/engine_run.py` — add `class WouldBeMeasuredBy(str, Enum)` with the locked values: `INCREMENTAL_ORDERS_IN_14D`, `EMAIL_ATTRIBUTED_REVENUE_IN_7D`, `REPEAT_PURCHASE_IN_30D`. Add `would_be_measured_by: Optional[WouldBeMeasuredBy] = None` to `PlayCard`. Update `to_dict` and `from_dict` (the existing `_coerce_enum` handler covers most of this already).
- `tests/test_engine_run_schema.py` — extend round-trip + enum-completeness tests.
- New: `tests/test_would_be_measured_by_enum.py` — pin the enum surface and the field round-trip.

**Acceptance criteria.**
- `PlayCard.would_be_measured_by` round-trips through `EngineRun.to_dict()` → `EngineRun.from_dict()`.
- Free-text strings raise `ValueError` on `WouldBeMeasuredBy(<str>)` if not in the enum.
- Default value is `None` for every PlayCard built today; no existing test breaks.
- M0 legacy goldens still byte-identical (legacy adapter does not stamp this field; its absence persists as `would_be_measured_by: null` in V2 receipts only).

**Tests.**
- Red-first: round-trip preserves the field for every enum value.
- Red-first: free-text raises.
- Negative control: existing PlayCard-construction tests pass without explicit `would_be_measured_by`.

**Rollback notes.** Revert the `engine_run.py` field + enum and the test files. The adapter and decide layers do not yet read the field.

### Ticket A3 — Priors metadata: schema + loader

**Goal.** Add per-play metadata to `config/priors.yaml`: `audience_floor`, `mechanism`, `vertical_applicability`, `would_be_measured_by`, `audience_archetype`. Extend `src/priors_loader.py` to expose these. Stays config-only; no runtime consumer yet.

**Likely files.**
- `config/priors.yaml` — add a new `metadata:` block per play under each `plays.<play_id>` section. Use the locked `audience_archetype` enum from "Open Decisions Resolved" Q3. Set `vertical_applicability` to a list of `{beauty, supplements, mixed}`. `would_be_measured_by` matches the enum in Ticket A2. `audience_floor` is per-play (e.g. `bestseller_amplify: 500`, `discount_hygiene: 200`). `mechanism` is a short merchant-readable string (e.g. `"Email a 10% off code to discount-prone buyers; track redemption."`).
- `src/priors_loader.py` — add `get_play_metadata(play_id) -> PlayMetadata` returning a typed dataclass with the five fields plus `Optional`s. Reuse the existing lazy-load cache.
- New: `tests/test_priors_metadata.py` — schema validation, completeness for the two first-ship-eligible plays (`discount_hygiene`, `bestseller_amplify`), enum validation on `would_be_measured_by` and `audience_archetype`.

**Acceptance criteria.**
- `discount_hygiene` and `bestseller_amplify` both have all five metadata fields populated and pass schema validation.
- Other plays may have empty / partial metadata; missing metadata is treated as "no metadata" (no crash, returns `PlayMetadata` with `None`s).
- `would_be_measured_by` and `audience_archetype` only accept enum-valid strings; loader rejects free-text on these two fields.
- The loader is still lazy-loaded; no runtime behavior change in any other file.
- M0 legacy goldens still byte-identical.

**Tests.**
- Red-first: schema test `test_priors_metadata_first_ship_plays_complete` asserts all five fields populated for both allowlisted plays.
- Red-first: `test_priors_would_be_measured_by_must_be_enum` asserts loader rejects free-text.
- Negative control: plays without metadata return defaults without raising.

**Rollback notes.** Revert the YAML metadata block and the loader extension. No runtime consumer yet.

### Ticket A4 — Recommended Experiment role: decide-layer eligibility filter (skeleton, no rendering)

**Goal.** Stand up the experiment-eligibility filter behind `ENGINE_V2_SLATE` (default OFF). Compute the candidate set without rendering it. Eligibility rules from the contract:

- `evidence_class == "targeting"`.
- Audience size >= per-play `audience_floor`.
- `mechanism` non-empty in priors metadata.
- `vertical_applicable=true` for current `VERTICAL_MODE`.
- `would_be_measured_by` present and enum-valid.
- No inventory block (`preliminary_rejection_reason != "inventory_blocked"`).
- Audience overlap with any Recommended Now card `< 30%`. (Reuse existing M5 pairwise overlap helper.)
- Slate diversity: no two cards with the same `audience_archetype`.
- Hard cap = 2.
- Allowlist (first-ship): `{discount_hygiene, bestseller_amplify}`.
- Recently-run-fatigue: NO-OP today; structural placeholder calling the existing `calibration_stub` outcome-log reader, which always returns `{}`.

The filter writes the resulting list into a new `EngineRun.recommended_experiments: List[PlayCard]` (additive field, sibling to `recommendations`). When `ENGINE_V2_SLATE=false`, `recommended_experiments` is always `[]`.

**Likely files.**
- `src/engine_run.py` — add `recommended_experiments: List[PlayCard] = field(default_factory=list)` to `EngineRun`. Update `to_dict` / `from_dict`.
- `src/decide.py` — add `MAX_RECOMMENDED_EXPERIMENT: int = 2`, `RECOMMENDED_EXPERIMENT_ALLOWLIST: frozenset[str] = frozenset({"discount_hygiene", "bestseller_amplify"})`. New helper `_select_recommended_experiments(engine_run, *, cfg)` invoked from `decide()` after the existing rank/cap/abstain block.
- `src/utils.py` — register `ENGINE_V2_SLATE` flag, default `false`.
- `src/main.py` — pass through the flag to `decide()`.
- New: `tests/test_recommended_experiment_eligibility.py` — every eligibility rule, every negative case.

**Acceptance criteria.**
- Filter respects the allowlist; passes only `discount_hygiene` and `bestseller_amplify` even if other targeting plays carry full metadata.
- Filter respects per-play `audience_floor` (read from priors metadata, NOT a global env flag).
- Filter computes audience overlap pairwise vs each Recommended Now card; demotes violators with `ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY` into Considered.
- Filter enforces slate diversity; demotes the second card with the same archetype into Considered with `ReasonCode.CANNIBALIZATION_DEMOTED` (or a new typed code if PM prefers; default reuses the existing one).
- Hard cap 2.
- ABSTAIN_SOFT case (Recommended Now = []): filter returns []. Pre-conditions Ticket B3.
- ABSTAIN_HARD case: filter returns [].
- `recommended_experiments` round-trips through `to_dict` / `from_dict`.
- With flag OFF: filter is a no-op, `recommended_experiments` stays `[]`. Existing tests + V2 goldens pass.
- M0 legacy goldens still byte-identical.

**Tests.**
- Red-first: 12 eligibility unit tests (one per rule, plus the cap, plus the allowlist, plus ABSTAIN_SOFT, plus ABSTAIN_HARD).
- Red-first: round-trip `recommended_experiments` field on a synthesized EngineRun.
- Property test: invariant `len(out.recommended_experiments) <= 2` over a randomized set of inputs.
- Property test: invariant `len({c.would_be_measured_by for c in out.recommended_experiments}) == len(out.recommended_experiments)` (each card has a populated enum value).

**Rollback notes.** Revert the new schema field, the new constants, the helper, and the flag registration. The renderer has no awareness of the new field yet.

### Ticket B1 — Renderer: Recommended Experiment section

**Goal.** Render the `Recommended Experiment` section between Recommended Now and Watching, behind `ENGINE_V2_SLATE`.

**Likely files.**
- `src/storytelling_v2.py` — new `render_recommended_experiment_section(cards, *, scale, abstain)`. Reuses `render_play_card` but wraps in `<section class="recommended-experiment" aria-label="Recommended Experiment">`. Each card carries:
  - Heading framing: "Run as experiment" (literal).
  - "Send to N people" copy via the existing audience block.
  - The `would_be_measured_by` value rendered as a short merchant-readable string keyed by enum (e.g., `INCREMENTAL_ORDERS_IN_14D` → "We will measure incremental orders in 14 days.").
  - Phase 5.1 opportunity-context block via `_render_opportunity_context_block` — verbatim reuse, no copy edits, no math change.
  - `revenue_range.suppressed=true` on every card; the renderer must hide $ values.
- `src/storytelling_v2.py::render_engine_run` — call the new section with `engine_run.recommended_experiments` in the right position.
- New: `tests/test_render_recommended_experiment.py`.

**Acceptance criteria.**
- Rendered HTML contains exactly the count of `recommended_experiments` cards under `section.recommended-experiment article.play-card`.
- Each card displays `would_be_measured_by` as enum-mapped text. No free-text.
- Each card displays the Phase 5.1 opportunity-context block including the disclaimer "This is not projected lift; it shows the size of the audience if the play converts."
- No card displays a $ headline larger than the range chip text (M8 invariant extended to this section).
- `revenue_range` is always suppressed in receipts for cards in this list (write-time invariant in Ticket A4 reaffirmed here).
- ABSTAIN_SOFT renders zero cards (Ticket B3 enforces).
- M0 legacy goldens still byte-identical.

**Tests.**
- Red-first: section presence + card count.
- Red-first: `would_be_measured_by` enum-mapped text presence.
- Red-first: opportunity-context block rendered verbatim.
- Red-first: `tests/test_targeting_no_dollar_headline.py`-style invariant for this section.

**Rollback notes.** Revert the new render function and the call from `render_engine_run`. The decide layer still computes the list; it just stops surfacing.

### Ticket B2 — Forbidden-token sweep extension on Recommended Experiment

**Goal.** Extend Phase 5.5 forbidden-token sweep to cover the new section. Add the seven new forbidden phrases from the contract: `calibrated`, `uplift`, `ATE`, `ITT`, `treatment effect`, `expected lift`, `projected lift` — plus reaffirm `forecast`, `predicted`, `evidence`, `measured` for this section only.

**Likely files.**
- `tests/test_phase5_no_aura_beacon.py` — extend to include the new section.
- New: `tests/test_recommended_experiment_forbidden_tokens.py` — explicit, scoped sweep on `section.recommended-experiment` HTML, plus a whole-document sweep for the seven new universal-forbidden tokens.

**Acceptance criteria.**
- Synthesizing a `recommended_experiments` list with both allowlisted plays and rendering produces zero forbidden tokens in `section.recommended-experiment`.
- The phrase "projected lift" still appears once per card body (inside the negation disclaimer "This is not projected lift; ..."). The sweep allowlists that single phrase verbatim and rejects every other occurrence.
- The seven new forbidden tokens are rejected anywhere in the document outside the disclaimer.
- M0 legacy goldens still byte-identical.

**Tests.**
- Red-first: every forbidden token tested individually with a card that contains it; assertion fails until renderer scrubs / never emits.
- Negative control: the disclaimer's "not projected lift" phrase is allowed.

**Rollback notes.** Test-file revert. No source change.

### Ticket B3 — ABSTAIN_SOFT contract extension to Recommended Experiment

**Goal.** Extend Fix 3's ABSTAIN_SOFT contract so `recommended_experiments` is also `[]` under ABSTAIN_SOFT. Held cards route to Considered with `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN` exactly as Fix 3 routes Recommended Now cards.

**Likely files.**
- `src/decide.py` — extend the existing ABSTAIN_SOFT branch so `recommended_experiments = []` and any cards the experiment-eligibility filter emitted are routed into `considered` with the typed reason code.
- `src/storytelling_v2.py` — new `render_recommended_experiment_section` already returns an empty section under ABSTAIN_SOFT; add the same "No experiment plays met audience-floor and overlap rules this run." empty-state copy and a callout reuse.
- New: `tests/test_abstain_soft_no_experiments.py`.

**Acceptance criteria.**
- Under ABSTAIN_SOFT, `engine_run.recommended_experiments == []`.
- Held experiment cards appear in `engine_run.considered` with `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN`, populated `reason_text`, populated `would_fire_if`.
- Under ABSTAIN_SOFT, the rendered `section.recommended-experiment` contains zero `article.play-card` elements.
- Under PUBLISH, behavior is unchanged from Ticket B1.
- Under ABSTAIN_HARD, the entire briefing is the data-quality memo (unchanged).
- M0 legacy goldens still byte-identical.
- Fix 3 contract tests still pass.

**Tests.**
- Red-first: `test_abstain_soft_routes_experiments_to_considered`.
- Red-first: `test_abstain_soft_renders_zero_experiment_cards`.
- Negative control: PUBLISH path renders the configured count.

**Rollback notes.** Revert the abstain branch extension and the renderer empty-state. The eligibility filter still computes; the routing reverts to Fix-3-only behavior.

### Ticket B4 — Role-uniqueness invariant: no PlayCard appears in two role sections

**Goal.** Add a structural assertion in `decide.py` that no `play_id` appears in both `engine_run.recommendations` and `engine_run.recommended_experiments` in a single run. This is a load-bearing trust constraint per the accepted contract.

**Likely files.**
- `src/decide.py` — final-pass assertion at the end of `decide()`. Raise `AssertionError` with the duplicate `play_id` in the message. The eligibility filter is the single seam through which an experiment card can reach `recommended_experiments`; this assertion is a defensive net.
- New: `tests/test_role_uniqueness_invariant.py`.

**Acceptance criteria.**
- `decide()` raises `AssertionError` if a `play_id` appears in both lists.
- The eligibility filter's natural behavior never produces this case (because cards in `recommendations` are measured/directional, and the experiment allowlist is targeting-only).
- The assertion is the forcing function for any future code path that mis-stamps an experiment card as measured.
- M0 legacy goldens still byte-identical.

**Tests.**
- Red-first: synthesize an EngineRun with the same `play_id` in both lists, call `decide()` → assertion raised.
- Negative control: synthesize a clean EngineRun (different `play_id`s) → no assertion.

**Rollback notes.** Revert the assertion and the test file. Single-line revert.

### Ticket B5 — Cannibalization gate hardening + slate diversity assertion

**Goal.** Pin the `<30%` overlap cannibalization gate vs Recommended Now and the slate-diversity rule (no two experiments with the same `audience_archetype`) as two pinned tests. Audit Ticket A4's filter against them. If the filter passes both red-first tests on day-1, this ticket is purely test-additions (and that's a green signal).

**Likely files.**
- `src/decide.py` — verify `_select_recommended_experiments` calls into `src.guardrails`'s pairwise-overlap helper, NOT a custom one. Verify diversity check uses the locked archetype enum.
- New: `tests/test_recommended_experiment_cannibalization.py`.
- New: `tests/test_recommended_experiment_diversity.py`.

**Acceptance criteria.**
- Cannibalization: synthesize a Recommended Now card with audience overlap 31% and 29% to two experiment candidates → only the 29% candidate survives.
- Diversity: synthesize two experiment candidates both stamped `audience_archetype=discount_buyer` → only the higher-ranked one survives.
- Demoted cards land in Considered with the correct reason code.
- M0 legacy goldens still byte-identical.

**Tests.**
- Red-first: both above scenarios.
- Property test: for any randomly synthesized set of N candidates, output `<= 2` AND every output has a unique `audience_archetype` AND no output overlaps any Recommended Now by `>= 30%`.

**Rollback notes.** Test-only revert. The gate logic is owned by Ticket A4.

### Ticket B6 — Beauty Brand pinned slate-regression fixture

**Goal.** Pin `agent_outputs/synthetic_fixes_8_11_samples/healthy_beauty_240d_briefing.html` (or a fresh post-Ticket-B1 render) under `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` as a slate-regression fixture. This is NOT an M0 golden; it lives in a separate test lane to avoid coupling.

**Likely files.**
- New directory: `tests/fixtures/synthetic_slate/`.
- New: `tests/test_slate_regression_beauty_brand.py` — exercise the synthetic harness on `healthy_beauty_240d` with the full V2+slate flag stack on, parse the resulting briefing.html via `tests/synthetic_reporter.py` (Fix 7), and pin the expected slate row:
  - 1 Recommended Now (`first_to_second_purchase`, directional, addressable value about $329k).
  - 2 Recommended Experiment (`discount_hygiene` + `bestseller_amplify`).
  - 1 Watching (`aov` trend).
  - 4 Considered (`winback_21_45`, `routine_builder`, `subscription_nudge`, `empty_bottle`).
  - decision_state = `publish`.

**Acceptance criteria.**
- Test passes deterministically on the post-Fixes-1–11 fixture.
- Test fails loudly if any slate-side regression moves the row.
- M0 legacy goldens still byte-identical.

**Tests.**
- Red-first: assert each of the four counts on the rendered DOM via the Fix 7 reporter.
- Snapshot: byte-equality of the pinned briefing.html (allowing a manual refresh ticket if a future renderer change is intentional).

**Rollback notes.** Test-only revert. The fixture stays around for Phase 6B.

### Ticket B7 — Optional inventory loader prerequisite ticket (gated, separate)

**Goal.** OPTIONAL prerequisite. Only pursue if low_inventory e2e validation of the inventory_blocked Considered card becomes blocking for Beauty Brand pinned regression in Ticket B6. The fix is the one-line `src/load.py:626` `groupby().apply().reset_index(name=...)` → `to_frame(name=...).reset_index()` change documented in Fixes 8–11.

**Likely files.**
- `src/load.py` — line 626 only.
- `tests/test_inventory_loader_pandas_compat.py` (new) — pin the load behavior on a synthetic CSV.

**Acceptance criteria.**
- `compute_inventory_metrics` no longer raises `TypeError` on the standard pandas version in the project venv.
- `data/SM_orders.csv + data/SM_inventory.csv` reads cleanly.
- Fix 4 e2e: `inventory_blocked` Considered card surfaces on `healthy_beauty_low_inventory_240d`.
- M0 legacy goldens still byte-identical.

**Tests.**
- Red-first: minimal repro test on a 2-row inventory CSV.
- Existing `tests/test_inventory_blocked_in_considered.py` matrix-wide test should now exercise the e2e path without skipping.

**Rollback notes.** Single-line revert.

**Status:** OPTIONAL. Not on the critical path. Land only if Beauty Brand pinned regression cannot be made deterministic without it.

## Schema / Contract Changes

Additive-only. No `schema_version` bump.

| Surface | Change | File |
|---|---|---|
| `EngineRun.recommended_experiments` | New `List[PlayCard]`, default `[]`, round-trips. | `src/engine_run.py` |
| `PlayCard.would_be_measured_by` | New `Optional[WouldBeMeasuredBy]`, default `None`. | `src/engine_run.py` |
| `WouldBeMeasuredBy` enum | New: `{INCREMENTAL_ORDERS_IN_14D, EMAIL_ATTRIBUTED_REVENUE_IN_7D, REPEAT_PURCHASE_IN_30D}`. | `src/engine_run.py` |
| `config/priors.yaml` per-play `metadata:` block | New: `audience_floor, mechanism, vertical_applicability, would_be_measured_by, audience_archetype`. | `config/priors.yaml` |
| `audience_archetype` enum | New (loader-side): `{first_time_buyer, lapsed_buyer, discount_buyer, hero_sku_buyer, replenishment_buyer, full_price_buyer, vip_loyalist, no_archetype}`. | `src/priors_loader.py` |
| `MAX_RECOMMENDED_EXPERIMENT = 2` | New constant. | `src/decide.py` |
| `RECOMMENDED_EXPERIMENT_ALLOWLIST = {discount_hygiene, bestseller_amplify}` | New constant. | `src/decide.py` |
| `ENGINE_V2_SLATE` flag, default OFF | New. | `src/utils.py` |

Hard rules pinned as tests:

- Cards in `recommended_experiments` MUST have `evidence_class == TARGETING`, `revenue_range.suppressed == True`, and a populated `would_be_measured_by`.
- No `play_id` may appear in both `recommendations` and `recommended_experiments` in the same `EngineRun`.
- Under ABSTAIN_SOFT, both lists are `[]`.
- Under ABSTAIN_HARD, both lists are `[]`.
- `would_be_measured_by` MUST be enum-valid; free-text rejected at load.
- Watching cap: `<= 4`.

## Priors Metadata Plan

Loaded via `src.priors_loader.get_play_metadata(play_id) -> PlayMetadata`. The loader is the single source of truth.

Schema per play under `config/priors.yaml`:

```yaml
plays:
  bestseller_amplify:
    metadata:
      audience_floor: 500
      mechanism: "Email a curated bundle of the hero SKU plus complementary products to recent buyers; track basket attach."
      vertical_applicability: [beauty, mixed]
      would_be_measured_by: REPEAT_PURCHASE_IN_30D
      audience_archetype: hero_sku_buyer
    - name: base_rate
      ...
  discount_hygiene:
    metadata:
      audience_floor: 200
      mechanism: "Email a 10% off code to discount-prone buyers; track redemption rate."
      vertical_applicability: [beauty, supplements, mixed]
      would_be_measured_by: EMAIL_ATTRIBUTED_REVENUE_IN_7D
      audience_archetype: discount_buyer
    - name: base_rate
      ...
```

Validation rules:

- `audience_floor` is a positive int.
- `mechanism` is a non-empty string, max ~200 chars (advisory; tests assert non-empty only).
- `vertical_applicability` is a list of `{beauty, supplements, mixed}` strings.
- `would_be_measured_by` matches the `WouldBeMeasuredBy` enum.
- `audience_archetype` matches the loader-side `AudienceArchetype` enum.
- A play MAY omit the `metadata:` block; the loader returns a `PlayMetadata` with `None`s and the experiment-eligibility filter rejects the play. This is the conservative default and the reason no other plays slip into Recommended Experiment until explicitly enabled.

## Renderer Plan

The renderer changes are entirely additive on top of `src/storytelling_v2.py`. No template engine swap. No copy regeneration on existing sections.

`render_engine_run` ordering:

1. State of Store (existing).
2. Recommended Now (existing `render_recommended_section`).
3. **Recommended Experiment (new `render_recommended_experiment_section`).**
4. Watching (existing `render_watching_section`, cap reduced to 4).
5. Held / Considered (existing `render_considered_section`).
6. Data-quality footer (existing `render_data_quality_footer`).

`render_recommended_experiment_section` reuses `render_play_card` to keep targeting visual treatment consistent. Section-level wrapper:

```html
<section class="recommended-experiment" aria-label="Recommended Experiment">
  <h2 class="section__title">Recommended Experiment</h2>
  <p class="section__lede">Plays we'd run as experiments. We will measure the result and learn whether they work for your store.</p>
  <div class="play-card-grid">{cards}</div>
</section>
```

Each card inside reuses `render_play_card` with one additional pre-card block:

- "Send to N people" framing: the existing audience block already renders this; no copy change.
- `would_be_measured_by` rendered as a small chip under the targeting disclaimer:
  - `INCREMENTAL_ORDERS_IN_14D` → "We will measure incremental orders in 14 days."
  - `EMAIL_ATTRIBUTED_REVENUE_IN_7D` → "We will measure email-attributed revenue in 7 days."
  - `REPEAT_PURCHASE_IN_30D` → "We will measure repeat purchase in 30 days."

Phase 5.1 `_render_opportunity_context_block` is invoked verbatim. The block already self-hides when `revenue_range` is unsuppressed; here it always renders because `revenue_range.suppressed=True` is structurally guaranteed by Ticket A4.

ABSTAIN_SOFT: section renders the empty-state and the held-cards routing into Considered (Ticket B3).

ABSTAIN_HARD: section is not rendered at all (the entire briefing is the data-quality memo).

## Decision Selector Plan

`decide()` gains one new helper invoked after the existing rank/cap/abstain block:

```
decide(engine_run, *, cfg)
  recommendations, cap_exceeded = rank_and_cap(...)
  abstain_state = decide_abstain(...)
  if abstain_state == PUBLISH:
      recommended_experiments = _select_recommended_experiments(
          engine_run, recommendations, *, cfg
      )
  else:
      recommended_experiments = []
      held_experiments_to_considered = ...   # Ticket B3
  considered = assemble_considered(...)
  watching = build_watching(...)
  return EngineRun(... recommendations, recommended_experiments, considered, watching ...)
```

`_select_recommended_experiments` reads:

- `engine_run.recommendations` (for cannibalization overlap).
- M3 candidate list (already on `engine_run` via Phase 5 wiring) for the universe of targeting candidates.
- `priors_loader.get_play_metadata(play_id)` per candidate.
- `cfg["VERTICAL_MODE"]`.

It returns at most 2 PlayCards. Each card has:

- `evidence_class = TARGETING`.
- `revenue_range = RevenueRange(suppressed=True)` with a `drivers=[{"reason": "experiment_no_calibrated_lift"}]`.
- `would_be_measured_by = <enum from priors metadata>`.
- `opportunity_context` populated via the existing Phase 5.1 builder.
- `audience` populated from M3.

Recently-run-fatigue is a structural placeholder: the helper calls `calibration_stub.was_run_recently(play_id)` which always returns `False` today. When the outcome log is non-stub (Phase 6B+), this flips on without a code change here.

## Test Strategy

TDD red-first sequence (in landing order):

1. A1 — Watching cap, load-bearing prioritization (2 new tests).
2. A2 — `would_be_measured_by` enum + round-trip (3 new tests).
3. A3 — Priors metadata schema + loader (4 new tests).
4. A4 — Eligibility filter (12 new unit tests + 2 property tests).
5. B1 — Renderer presence + opportunity-context block on experiments (5 new tests).
6. B2 — Forbidden-token sweep extension (11 forbidden tokens, 1 negative control = 12 new tests).
7. B3 — ABSTAIN_SOFT zero experiments + Considered routing (4 new tests).
8. B4 — Role-uniqueness assertion (2 new tests).
9. B5 — Cannibalization + diversity (2 deterministic tests + 1 property test).
10. B6 — Beauty Brand pinned slate regression (1 deterministic harness-driven test + 1 byte-equality snapshot).
11. B7 (optional) — Inventory loader pandas-compat (1 minimal repro test).

Cumulative new tests: ~51. Estimate matches the cadence of Fixes 2–5 (each landed 6–12 new tests).

Cross-cutting regression checks (run on every ticket):

- `tests/test_golden_diff.py` — must remain 3 passed, no re-baseline.
- `tests/test_targeting_no_dollar_headline.py` — must remain green.
- `tests/test_phase5_no_aura_beacon.py` — must remain green.
- `tests/test_targeting_measurement_invariant.py` — Fix 2 invariant.
- `tests/test_abstain_soft_no_recommendations.py` — Fix 3 invariant.
- `tests/test_inventory_blocked_in_considered.py` — Fix 4 invariant.
- `tests/test_materiality_footer_present.py` — Fix 5 invariant.
- `tests/test_matrix_vertical_propagation.py` — Fix 6 invariant.
- `tests/test_reporter_dom_only.py` — Fix 7 invariant.
- `tests/test_synthetic_fixtures_8_11.py` — Fixes 8–11 invariant.

Property tests (ticket B5):

- For 100 randomly synthesized candidate sets: `len(experiments) <= 2`, all unique archetypes, no >=30% overlap with Recommended Now, no Considered duplicates.

## Golden / Fixture Strategy

- M0 legacy goldens (`tests/golden/{small_sm, mid_shopify, micro_coldstart}/*`): byte-identical. Never re-baselined in any Phase 6A ticket.
- V2 fixtures: no current pinned V2 goldens exist; nothing to refresh.
- New pinned slate fixture: `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` (Ticket B6). Lives in a separate lane.
- Synthetic samples in `agent_outputs/synthetic_fixes_8_11_samples/`: regenerate post-B6 as a visual diff target. These are reference artifacts, not test fixtures.

Refresh checkpoints:

- After Ticket B1 lands: regenerate the synthetic samples directory and visually inspect on `healthy_beauty_240d`.
- After Ticket B6 lands: pin the regression briefing; tag the commit.

## Risks

1. **Audience archetype taxonomy drift.** If a future PM wants new archetypes (e.g., `subscription_buyer`), the loader enum must extend. Mitigation: enum extension is single-line; tests force a load-time check on every play that has `audience_archetype` set.
2. **`mechanism` copy quality.** The first-ship two plays' mechanism strings will be customer-facing. Mitigation: Ticket A3 acceptance includes PM sign-off on the literal copy before the YAML lands. Strings live in `config/priors.yaml` and can be edited without code changes.
3. **Filter flakiness on cannibalization edge cases.** The pairwise-overlap helper depends on M3 audience size estimates which are deterministic but version-sensitive. Mitigation: pin a ULP-tolerant equality check on the 30% threshold, just as Phase 5 had to do for stat thresholds.
4. **Beauty Brand fixture brittleness.** A future change to `_resolve_aov_for_context` (Phase 5.1 contract risk noted in `memory.md`) could shift the addressable value on the pinned briefing. Mitigation: Ticket B6 reads `kpi_snapshot_with_deltas[window]["aov"]` directly via the existing builder; any AOV definition change must update the fixture in lockstep, with explicit review.
5. **Default flag interaction.** `ENGINE_V2_SLATE=true` only takes effect when `ENGINE_V2_OUTPUT=true` AND `ENGINE_V2_DECIDE=true`. Mitigation: tests pin the matrix; `src/main.py` raises a clear error if `ENGINE_V2_SLATE=true` but the V2 stack is not on, rather than silently no-oping.
6. **`recommended_experiments` field-not-supported on legacy adapter.** The legacy adapter is a no-op for this field (always `[]`), so a downstream consumer that reads `recommended_experiments` from a legacy-adapter-built EngineRun will see an empty list. Documented; no action required.
7. **AnomalousWindow auto-registration deferred.** `promo_anomaly_240d` will publish 1 Recommended Now + 2 Recommended Experiment cards under Phase 6A. This is not a regression — the contract explicitly accepts this until Phase 6B. Mitigation: documented in this plan and in the synthetic-fix-10 summary.

Rollback strategy:

- Each ticket is a single PR with a single revert path.
- The flag `ENGINE_V2_SLATE=false` (default) is the immediate kill-switch for everything in this plan.
- Tests are additive — reverting a ticket reverts its tests.
- M0 legacy goldens are the bottom-line forcing function: any ticket that moves them is rejected at code review.

## Definition Of Done

Phase 6A is shippable when all of the following hold:

1. Tickets A1, A2, A3, A4, B1, B2, B3, B4, B5, B6 are merged.
2. `ENGINE_V2_SLATE=true` end-to-end on `healthy_beauty_240d` produces:
   - 1 Recommended Now (directional `first_to_second_purchase`).
   - 2 Recommended Experiment (`discount_hygiene`, `bestseller_amplify`), both with `would_be_measured_by` enum-mapped text and the Phase 5.1 opportunity-context block.
   - 1 Watching.
   - 4 Considered.
   - decision_state = `publish`.
3. `ENGINE_V2_SLATE=true` on `small_store_240d` produces:
   - 0 Recommended Now, 0 Recommended Experiment, decision_state = `abstain_soft`.
   - Watching contains at least one of `returning_customer_share`, `net_sales`, `repeat_rate_within_window`, `aov` (when computable).
   - Held experiment cards routed to Considered with `TARGETING_HELD_UNDER_ABSTAIN`.
4. `ENGINE_V2_SLATE=true` on `cold_start_45d` produces ABSTAIN_HARD with recommendations and recommended_experiments both `[]`.
5. With `ENGINE_V2_SLATE=false`: byte-identical V2 output to current Phase 5.1 + Fixes 1–11 baseline. M0 legacy goldens byte-identical.
6. Full test suite green: target `~720+ passed, 14 skipped`.
7. No forbidden token in any rendered briefing on any of the six synthetic scenarios.
8. No `play_id` appears in two role sections in any of the six runs.
9. `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` pinned; regression test green.

Phase 6A is NOT done if:

- M0 goldens moved.
- Any forbidden token shipped.
- Any Recommended Experiment card has `revenue_range.suppressed=false`.
- Any Recommended Experiment card lacks an enum-valid `would_be_measured_by`.
- ABSTAIN_SOFT publishes any non-zero card count.
- Any synthetic-fix invariant test breaks.

## What Not To Touch Yet

Explicit non-touch list:

- `src/load.py:626` (unless Ticket B7 is taken).
- `AnomalousWindowCheck` registration in `DataValidationEngine` — Phase 6B.
- `src/audience_builders.py:439` `empty_bottle` parser — Phase 6B.
- `config/priors.yaml` `source_class` values — no promotion of expert→causal.
- `src/sizing.py` — no unsuppressing of `revenue_range`.
- `src/storytelling.py` (legacy renderer) — untouched.
- `actions_log.json` writer — untouched.
- `src/measurement_builder.py::_SUPPORTED` — no new directional plays.
- `recommended_history.json` outcome-log read path — Phase 6B.
- M10 cleanup or V2 default flip — Phase 7.
- Any Lifecycle Maintenance section — Phase 6B+.
- Renderer copy on Recommended Now, Watching, Considered, or Data-quality footer — preserved verbatim from Phase 5.1 + Fix 5.

## Handoff Prompt For Code Refactor Engineer

The following is a self-contained prompt for the FIRST ticket only (Ticket A1 — Watching cap reduction + load-bearing prioritization pin). Paste verbatim to the code-refactor-engineer agent.

---

You are the code-refactor-engineer agent. This is Phase 6A, Ticket A1 ONLY, from `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-campaign-slate-plan.md`. Read that file in full before touching code, then read `agent_outputs/campaign-slate-contract-final.md` for the broader contract, then proceed.

**Approved scope.** Reduce the Watching section cap from 7 (Phase 5.3) to 4. Pin a load-bearing-metric prioritization test on `small_store_240d` synthetic fixture: when any of `returning_customer_share`, `net_sales`, `repeat_rate_within_window`, or `aov` is computable, at least one MUST surface in the rendered Watching section.

**Strict non-goals.**
- No PlayCard schema changes.
- No `would_be_measured_by`.
- No new Recommended Experiment section.
- No priors metadata.
- No decide-layer eligibility filter.
- No legacy renderer change.
- No materiality floor change.
- No goldens re-baselined.
- No fix to `src/load.py:626`.
- No AnomalousWindowCheck registration.
- No `empty_bottle` ct/lb parser.

**Files in scope.**
- `src/storytelling_v2.py` — confirm and tighten the Watching cap (currently `[:4]` on line ~773; add `MAX_WATCHING_RENDERED: int = 4` constant).
- `src/decide.py` — `MAX_WATCHING_SIGNALS: int = 4` exists (line ~106); verify no upstream code emits more than 4 to `engine_run.watching`.
- Any builder that historically emitted 7 (Phase 5.3 raised the cap from 5 to 7) — locate via grep on `7` near "watching"; confirm and reduce.
- `tests/test_render_v2.py` — extend Watching tests.
- New: `tests/test_watching_load_bearing_priority.py` — pin prioritization on `small_store_240d`.

**Approach.**
1. Read `src/storytelling_v2.py::render_watching_section`. Confirm the current cap.
2. Locate Phase 5.3's `build_watching` function (likely `src/state_of_store.py`). Confirm any `[:7]` slice. Reduce to `[:4]`. Document the source-of-truth in a single constant.
3. Land the new test file `tests/test_watching_load_bearing_priority.py` red-first:
   - Use the synthetic harness `tests/synthetic_harness.py` to run `small_store_240d`.
   - Use the synthetic reporter `tests/synthetic_reporter.py` (Fix 7) to parse the briefing DOM.
   - Assert: `count_watching_rows >= 1` AND at least one row's `metric` text contains one of the four named load-bearing metrics (humanized form).
4. Add a renderer-level test in `tests/test_render_v2.py`:
   - Synthesize 7 WatchedSignals, render, count `li.watching-row` matches → 4.
5. Run the targeted suites and the full suite. Confirm no regression.

**Acceptance criteria.**
- Rendered Watching section never contains more than 4 rows.
- On `small_store_240d`, at least one load-bearing metric surfaces.
- M0 legacy goldens byte-identical.
- Full pytest suite green; expected pass count ~689+ (was 687 post-Fixes-8–11; +2 new tests).
- No goldens re-baselined.
- All Fix 1–11 invariants still pass.

**Tests to run.**
```bash
python -m pytest tests/test_watching_load_bearing_priority.py -v
python -m pytest tests/test_render_v2.py -v
python -m pytest tests/test_phase5_3_watching.py -v   # if it exists
python -m pytest tests/test_golden_diff.py -v
python -m pytest tests/ -q
```

**TDD discipline.** Land the new test file BEFORE the cap change; watch it fail; then ship the cap change; then watch it pass.

**Rollback notes.** If the cap reduction breaks a Phase 5.3 test you cannot reconcile, revert the cap change and the new test file. Single-PR.

**Output expected.** A summary at `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-a1-summary.md` following the same structure as `agent_outputs/code-refactor-engineer-synthetic-fix-5-summary.md` (Approved Scope, Patch Summary, Files Changed, Exact Commands Run, Tests / Checks Run, Did The New Test FAIL Before The Fix, Behavior Changes, Goldens, Remaining Risks, Readiness Assessment for Ticket A2).

When done, do NOT proceed to Ticket A2. Hand back to the orchestrator with the summary path.
