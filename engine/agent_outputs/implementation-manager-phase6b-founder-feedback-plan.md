# Phase 6B Implementation Plan — Founder-Feedback-Driven, Low-Risk

_Author: implementation-manager_
_Date: 2026-05-05_
_Inputs: agent_outputs/product-strategy-pm-founder-style-phase6a-review.md; agent_outputs/phase6a-final-review.md; memory.md_
_Status: PLAN ONLY — no code edits in this pass_
_Predecessor: Phase 6A commit 585480e, founder-testing-only, gated by ENGINE_V2_DECIDE + ENGINE_V2_OUTPUT + ENGINE_V2_SLATE_

---

## 1. Phase 6B verdict

Phase 6B is a **render-layer copy and ordering pass**, not a new engine intelligence layer. The single largest founder ARPU lever is surfacing the already-loaded `mechanism` string ("what we'd send") on Recommended Now and Recommended Experiment cards — that one ticket is what moves perceived value from $300 to ~$600. After that, two cheap wins (section reorder; customer-facing play-name relabel) plus one defensive copy fallback (never-empty Watching when the store has 240+ days of clean history) should land founder-tier value at the $500–$1,000 band without touching the decision core, the selector seam, the trust contract, or M0 goldens. Considered-list quality refresh and AnomalousWindow auto-registration are explicitly NOT in Phase 6B; they are scoped to Phase 6C. This is four tickets, all behind the existing `ENGINE_V2_OUTPUT` flag, each shippable independently, each leaving the engine runnable.

In scope: render-time copy surfacing, DOM section ordering, customer-facing display name, single-line empty-Watching copy fallback.

Out of scope: any selector/decide-layer change, any new measurement wiring, any new play type, any `revenue_range` unsuppression, any A/B-split UI, any per-card numeric confidence, any Klaviyo/Shopify integration, any Considered-list reason-bucket overhaul (deferred), any AnomalousWindow auto-registration (deferred to Phase 6C — DS-owned, not founder-perceived gap).

Smallest sequencing for founder-beta: C1 (mechanism surface) → C2 (section reorder) → C3 (display-name relabel) → C4 (never-empty Watching copy fallback). Ship them in this order; each ticket is independently revertible by toggling `ENGINE_V2_OUTPUT=false`.

---

## 2. Proposed tickets

| # | Title | Scope (one line) | Depends on | Complexity | Flag |
|---|---|---|---|---|---|
| **C1** | Surface "What we'd send" / mechanism copy on Recommended Now and Recommended Experiment cards | Render the already-loaded `mechanism` string as a new bordered line on Recommended-class cards (directional + experiment); copy guidelines limit it to audience-action-posture, no offer specifics that aren't grounded in evidence | none | M | existing `ENGINE_V2_OUTPUT` |
| **C2** | Reorder briefing sections: Recommended → Recommended Experiment → Watching → Considered | Move the Watching block above Considered in the V2 renderer; no model/selector change; `data-section` ordinals stay 1-indexed | C1 (only because both touch storytelling_v2) | S | existing `ENGINE_V2_OUTPUT` |
| **C3** | Customer-facing play-title relabel (display_name pass) | Replace `<h3>` text with merchant-friendly labels (e.g., "Winback 21 45" → "Lapsed-buyer reactivation (3–6 weeks since last order)"); internal `play_id` persists in `data-play-id`; `display_name` field already exists in `play_registry.py` and is the only string the renderer reads | none (parallel to C1/C2) | S | existing `ENGINE_V2_OUTPUT` |
| **C4** | Never-empty Watching copy fallback for stores with sufficient history | When the V2 Watching list would render empty AND the store has >=180 days of clean history AND State of Store has at least one `Observation` with a directional delta, render a single one-line fallback row pointing at the most-anomalous State-of-Store metric; do NOT plumb new trend stats; do NOT change how Watching is computed for stores that already have rows; on cold-start or hard-abstain, render the existing `<p class="section__empty">` text unchanged | C2 (Watching now sits before Considered, fallback is more visible) | S | existing `ENGINE_V2_OUTPUT` |

Total: 4 tickets. No new sub-flags. All four together are a single PR-each on `engine-rework`, with C1 sequenced first because it is the largest single ARPU lever and unblocks the founder's "I'd pay $500" threshold.

---

## 3. Ticket 1 scope (detailed) — Surface "What we'd send" / mechanism copy

### 3.1 Where the mechanism string lives today

Per Phase 6A Ticket A3 (commit `d8b7859`) the priors YAML loader (`src/priors_loader.py`) reads `config/priors.yaml`, where each play block carries a merchant-readable `mechanism` string alongside priors. Phase 6A Ticket A2 (commit `e11f7c5`) added a `WouldBeMeasuredBy` enum and a corresponding `PlayCard` field that is rendered as the future-tense "We will measure ___ in N days" line. The `mechanism` string is loaded into the priors metadata structure (Phase 6A Ticket A3 acceptance memo confirms this) but the V2 renderer does NOT currently surface it on any card. Phase 6A final review caveat #2 explicitly calls this out: "Priors metadata (Ticket A3) carries a merchant-readable mechanism, but the rendered card does not show it."

**Source path of truth (read-only, do not modify the loader semantics):**

- `config/priors.yaml` — per-play mechanism strings.
- `src/priors_loader.py::_extract_play_block` — dual list/dict YAML form already accommodated; route through this exclusively.
- `src/play_registry.py::PlayDef.notes` (or a new `mechanism` accessor on the priors metadata path) — verify with the engineer at C1 implementation time which seam the renderer should read from. Per Phase 6A A3 memo, the priors metadata path is the canonical seam; do NOT reach into the registry directly for `mechanism`.

C1 is therefore a render-only surfacing decision: read the already-loaded mechanism via the existing priors metadata accessor, escape it, and render a new line on the card.

### 3.2 What the rendered line should look like

A single bordered/dashed-border line, sibling to `play-card__why-now` / `play-card__measured-by`, styled lighter than the recommendation but darker than the disclaimer. New CSS class: `play-card__what-we-send`. New strong-tagged label: **"What we'd send:"** followed by the mechanism string, escaped.

Render conditions:

- Render on `evidence_class in {measured, directional}` cards (Recommended Now).
- Render on Recommended Experiment cards (which are `evidence_class=targeting` with `Run as experiment` framing per Phase 6A Ticket A4).
- Do NOT render on Considered cards. The Considered section is not the place for action copy.
- Do NOT render on Watching rows. Watching is metric-only.
- Do NOT render under ABSTAIN_HARD (no Recommended cards exist).
- Under ABSTAIN_SOFT, Recommended sections collapse to zero per Phase 6A Ticket B3, so this line never renders; no special-case logic needed.
- If the mechanism string is missing/empty for a given play in priors metadata, omit the line entirely (do NOT render an empty box, do NOT render placeholder copy). Phase 6A trust register: silence is preferable to hallucination.

### 3.3 Copy guidelines (mandatory; encode as test pins)

The mechanism string MUST be:

- **15–35 words** for clarity. Longer lines drift into briefs; shorter lines say nothing.
- **Audience + channel + posture + cadence**, in that order. Example: "Email these single-purchase customers a value-led second-purchase nudge, two sends one week apart, no discount."
- **No offer specifics** the engine cannot ground in evidence. Ban terms in copy: "20% off", "$X off", "free shipping" with concrete amounts, "predicted lift", "expected revenue", "guaranteed", "XX%". The render layer does not need to enforce all these as a sweep (the founder review's anti-priorities forbid us from inventing copy at render time anyway), but the priors authoring guideline document must call them out.
- **No causal language**: "will increase", "will lift", "drives X% more". Use "encourages", "tests", "checks", "surfaces".
- **No first-person engine voice** ("we recommend you...") — the engine recommends *what to send*, not what to do. Use imperative ("send", "test", "suppress") or noun-headed phrasing.

These are guidelines for the priors-YAML author, NOT runtime sweeps. The C1 ticket itself does NOT add a forbidden-token sweep on mechanism strings — that would be a prior-content audit, separately tracked. C1 only adds a structural sweep: `play-card__what-we-send` exists on directional + experiment cards in a publish-state slate fixture, and is absent on rejected/Considered cards.

### 3.4 Example before/after pseudo-HTML

**Before (Recommended Experiment card today):**

```html
<article class="play-card play-card--experiment" data-play-id="discount_hygiene" data-evidence-class="targeting">
  <h3 class="play-card__title">Discount Hygiene</h3>
  <div class="play-card__class-badge play-card__class-badge--experiment">Run as experiment</div>
  <div class="play-card-aud">
    <span class="play-card-aud__size"><strong>2,251</strong> people</span>
    <span class="play-card-aud__def">customers with discounted orders in last 28 days</span>
  </div>
  <p class="play-card__measured-by">We will measure email-attributed revenue in 7 days.</p>
  <!-- opportunity context block -->
</article>
```

**After (C1, mechanism surfaced):**

```html
<article class="play-card play-card--experiment" data-play-id="discount_hygiene" data-evidence-class="targeting">
  <h3 class="play-card__title">Discount Hygiene</h3>
  <div class="play-card__class-badge play-card__class-badge--experiment">Run as experiment</div>
  <div class="play-card-aud">
    <span class="play-card-aud__size"><strong>2,251</strong> people</span>
    <span class="play-card-aud__def">customers with discounted orders in last 28 days</span>
  </div>
  <p class="play-card__what-we-send"><strong>What we'd send:</strong> Suppress all discount codes from this segment for 14 days; send one full-price reminder of the last item they viewed, value-led copy, no urgency framing.</p>
  <p class="play-card__measured-by">We will measure email-attributed revenue in 7 days.</p>
  <!-- opportunity context block unchanged -->
</article>
```

The new line sits between audience block and measured-by line. Visual order on the card: title → class badge → audience → **what we'd send** → measured-by → opportunity context → (disclaimer if directional). On Recommended Now cards, the order is title → class badge → recommendation → why-now → audience → **what we'd send** → observed-metric → opportunity context.

### 3.5 Negative space (what C1 does NOT do)

- Does NOT add a new field to `PlayCard` schema. Mechanism is read at render time from priors metadata via the existing accessor.
- Does NOT add forbidden-token sweeps over mechanism string content. C1 is structural; content-quality sweeps belong to a separate content-audit task.
- Does NOT change selector/decide logic. No change to `src/decide.py`, `src/recommended_experiment.py`, or `src/guardrails.py` (or wherever the experiment selector module currently lives — verify path at implementation time).
- Does NOT touch M0 goldens. M0 fixtures are legacy-renderer; C1 only fires under `ENGINE_V2_OUTPUT=true`.
- Does NOT add CSS that would contaminate the M0 stylesheet block (V2 has its own inline style block in storytelling_v2.py).
- Does NOT auto-generate mechanism strings. If priors.yaml is missing a mechanism for a play, C1 omits the line; populating the YAML is a separate content task.

---

## 4. Files likely affected

### C1 — Surface mechanism

**Edited:**
- `src/storytelling_v2.py` — add `_render_what_we_send(play_card, mechanism)` helper; call it inside the directional and experiment card builders; add `.play-card__what-we-send` rule to the inline CSS block.
- `src/priors_loader.py` — add a typed accessor `get_mechanism(play_id, *, vertical, subvertical) -> Optional[str]` if one does not already exist; if it does (worth confirming under the Phase 6A A3 path), no edit required.

**New:**
- None.

**Likely also touches if the priors-metadata accessor seam is not what we expect:** `src/play_registry.py` (only to expose a `mechanism` accessor; not to add a new schema field — the value lives in priors.yaml, not the registry).

**Test fixtures touched:**
- `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` — pinned regression fixture **WILL** change byte-content. Re-pin under the existing fixtures lane (separate from M0). Re-compute sha256 in the B6 fixture pin.
- `agent_outputs/synthetic_fixes_8_11_samples/small_store_240d_briefing.html` and `cold_start_45d_briefing.html` — these are sample artifacts, not pinned fixtures; will rewrite on next harness run, no test impact.

### C2 — Section reorder (Watching before Considered)

**Edited:**
- `src/storytelling_v2.py` — change the order of `_render_considered_section(...)` and `_render_watching_section(...)` calls in the top-level `render_engine_run()` function. Likely a 2-line swap.

**New:** None.

**Test fixtures touched:**
- `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` — re-pin (byte change).
- Any structural-source-text test that asserts `section.considered` appears before `section.watching` in the HTML — invert the assertion. Likely lives in `tests/test_storytelling_v2_layout.py` or a B-series test; verify at implementation time.

### C3 — Display-name relabel

**Edited:**
- `src/play_registry.py` — update `display_name` on the legacy-emitted plays to merchant-readable strings. `play_id` and all other fields unchanged.
- `src/storytelling_v2.py` — confirm the renderer reads `display_name` (not `play_id.title()`) for the `<h3>` text. If it currently uses `play_id.replace("_", " ").title()`, switch to `PLAYS[play_id].display_name`. Verify at implementation time which branch is live.

**New:** None.

**Likely also touches if display_name is read elsewhere for merchant-facing strings:** `src/copykit.py` (legacy copy module — should NOT be edited; legacy renderer must remain byte-identical). If the V2 renderer accidentally pulls from copykit, a small render-only override is needed.

**Test fixtures touched:**
- `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` — re-pin.
- M0 goldens (`small_sm`, `mid_shopify`, `micro_coldstart`) — **MUST stay byte-identical**. The legacy renderer reads display strings from `copykit`/`storytelling`, not from `play_registry.display_name`. Confirm this before merging C3; if any M0 golden changes, abort C3 and re-scope to a V2-renderer-only string override.

### C4 — Never-empty Watching copy fallback

**Edited:**
- `src/storytelling_v2.py` — in `_render_watching_section`, when `engine_run.watching` is empty, branch on `engine_run.decision_state == DecisionState.PUBLISH or DecisionState.ABSTAIN_SOFT`, AND the engine-run scale window indicates >=180 days of history (use the existing `engine_run.scale.window` or `engine_run.data_window` field — verify at implementation time), AND there is at least one State-of-Store `Observation` with a non-zero directional delta. If all three hold, render a single `<li class="watching-row watching-row--fallback">` with a static one-line message: "Trend signals are firming up; we'll surface specific watch items here as your run-over-run history accumulates." (Exact copy TBD with PM at implementation.) Otherwise render the current `<p class="section__empty">` text unchanged.

**New:** None.

**Likely also touches if the State-of-Store check needs a helper:** add `_has_directional_observation(engine_run)` private helper inside `storytelling_v2.py`. Do not export.

**Test fixtures touched:**
- `agent_outputs/synthetic_fixes_8_11_samples/small_store_240d_briefing.html` — sample, not pinned, no test impact.
- `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` — re-pin only if Watching changes (it has 1 row today, so no fallback fires; should remain byte-identical post-C2 swap, byte-changing post-C1 due to mechanism, but C4 specifically should NOT change healthy_beauty fixture).

---

## 5. Tests required

### C1 — Mechanism surfacing

- **Structural source-text pin (new):** `tests/test_what_we_send_render.py::test_mechanism_renders_on_recommended_directional` — assert `play-card__what-we-send` class appears inside `section.recommended` when at least one directional card is present.
- **Structural source-text pin (new):** `tests/test_what_we_send_render.py::test_mechanism_renders_on_recommended_experiment` — assert `play-card__what-we-send` appears inside `section.recommended-experiment` for the pinned Beauty fixture.
- **Negative pin (new):** `tests/test_what_we_send_render.py::test_mechanism_absent_on_considered_and_watching` — assert NO `play-card__what-we-send` inside `section.considered` or `section.watching`.
- **Negative pin (new):** `tests/test_what_we_send_render.py::test_mechanism_omits_when_string_missing` — fixture with a play that has no `mechanism` in priors.yaml; assert the line is absent (not rendered as empty `<p>`).
- **Forbidden-token pin (additive to existing B2 sweep):** the existing B2 sweep on `section.recommended-experiment` MUST continue to pass. The new mechanism line introduces merchant-facing copy inside the experiment section; verify B2 does not flag any `mechanism` strings authored in priors.yaml. Add a one-time audit to the priors.yaml mechanism strings; future-tightening (sweep over priors.yaml content at load time) is OUT of C1 scope.
- **Beauty fixture re-pin:** `healthy_beauty_240d_briefing.html` byte-content + sha256 update in the B6 fixture-pin test. Documented as expected change.

**At-risk existing tests (must stay green):**
- M0 goldens — should be unaffected (V2 flag is off in M0 path). Verify with `pytest tests/test_golden_diff.py`.
- B2 forbidden-token sweep — verify mechanism strings introduce no banned tokens.
- B6 slate-shape pins — verify card counts, role-uniqueness, abstain-zero contract still hold.
- The Phase 6A `test_targeting_no_dollar_headline.py` — verify the new mechanism line does not contain a `$XX,XXX` pattern; if a priors author writes a dollar amount into a mechanism, this test will fail and force a copy revision (this is a feature, not a bug).

### C2 — Section reorder

- **Structural source-text pin (modify existing):** flip the assertion in whichever B-series or layout test asserts the current `Considered → Watching` order to assert `Watching → Considered`. Add an explicit `test_section_order_recommended_experiment_watching_considered` that pins all four sections in the expected order.
- **Beauty fixture re-pin.**

**At-risk:** any existing test that hardcodes the substring sequence "Considered, not recommended … Watching" — invert.

### C3 — Display-name relabel

- **Structural pin (new):** `tests/test_display_name_render.py::test_renderer_uses_play_registry_display_name` — assert that for a fixture, the `<h3>` text equals `PLAYS[play_id].display_name`, not a `play_id.title()` derivation.
- **M0 byte-identity guard (must continue to pass):** `pytest tests/test_golden_diff.py` — if this fails after C3, abort and re-scope.
- **Beauty fixture re-pin.**

**At-risk:** any test that pins the literal string "Winback 21 45" in the V2 renderer output. Update to the new display name. None on M0 (legacy renderer is unchanged).

### C4 — Never-empty Watching fallback

- **Structural pin (new):** `tests/test_watching_fallback.py::test_fallback_fires_on_240d_with_empty_watching` — synthetic fixture: 240-day store, empty `engine_run.watching`, at least one directional `Observation`. Assert one `watching-row--fallback` appears.
- **Negative pin (new):** `tests/test_watching_fallback.py::test_fallback_does_not_fire_on_cold_start` — 45-day store, empty watching → assert `<p class="section__empty">` renders (current behavior).
- **Negative pin (new):** `tests/test_watching_fallback.py::test_fallback_does_not_fire_when_watching_has_rows` — non-empty watching → no fallback row. Healthy Beauty fixture (which has 1 AOV row) covers this.
- **Beauty fixture: should remain byte-identical to its post-C1+C2+C3 state** because Beauty has a non-empty Watching row.

**At-risk:** none. C4 is additive copy in a previously-empty branch.

---

## 6. Acceptance criteria (founder-readable)

### C1 — Surface mechanism

- A founder reading the Beauty briefing can answer the question "what's the actual email?" for every Recommended Now and every Recommended Experiment card without leaving the page.
- The line appears as a labeled "What we'd send:" sentence on every directional and experiment card.
- The line never appears on Considered cards or Watching rows (avoid implying Considered plays come with action copy).
- If a play has no authored mechanism string, the card renders without the line — never with placeholder text or an empty box.
- The trust register is unbroken: no projected lift, no predicted revenue, no concrete offer specifics in the rendered string.

Maps to: founder review section 4 ("No 'what to actually send'") and Top-5 priority #1; Phase 6A final review caveat #2.

### C2 — Section reorder

- Sections render in the order: Recommended Now → Recommended Experiment → Watching → Considered → Data Quality footer.
- A founder reading top-to-bottom encounters forward-looking Watching before back-of-the-magazine Considered.
- ABSTAIN_HARD memo path is unchanged (no Recommended sections exist in that path; the order is moot).

Maps to: founder review Top-5 priority #3; Phase 6A final review caveat #1.

### C3 — Display-name relabel

- Card titles read like a marketing manager wrote them: "Lapsed-buyer reactivation (3–6 weeks since last order)" instead of "Winback 21 45"; "Top-product re-targeting" instead of "Bestseller Amplify"; "Replenishment timing" instead of "Empty Bottle"; etc.
- Internal `data-play-id="winback_21_45"` continues to appear on the article tag (engineering-readable, log-stable).
- M0 legacy goldens are byte-identical (legacy renderer path is untouched).

Maps to: founder review Top-5 priority #5.

### C4 — Never-empty Watching fallback

- For a store with 240 days of clean history and at least one directional State-of-Store observation, the Watching section is never rendered as "No deterministic signals to watch this run."
- The fallback row is one line, written in honest language, and never claims a measured signal.
- Cold-start (insufficient history) and ABSTAIN_HARD continue to render the existing empty-section copy unchanged.

Maps to: founder review Top-5 priority #4 (the small-and-safe portion only; the deeper "populate Watching with State of Store metrics" portion is deferred).

---

## 7. What to defer (and why)

| Founder-review item | Why deferred |
|---|---|
| **Considered-list reason-bucket overhaul (4+ differentiated buckets)** | The founder review explicitly flags this as the next priority after #1, but executing it well requires either (a) typed reason-code work in the selector layer (touches `src/decide.py`, the role-uniqueness invariant, and the B6 considered-filter, all of which are currently load-bearing per memory.md), or (b) authoring per-store-context rejection copy that risks faking specificity. Phase 6C territory. The cheap win — the `empty_bottle` reason-code mismatch (`audience=0` but `reason_code=no_measured_signal`) — should be folded into the Phase 6C ticket alongside the bucket work, not split out. |
| **AnomalousWindow auto-registration (Phase 6A caveat #3)** | The DS architect listed this as a Phase 6B priority for trust-during-promo, and the founder review acknowledges it: "as a founder reviewing the three non-promo scenarios I'm seeing, it's not the founder-perceived gap — it's an integrity-of-engine gap." Sequencing it parallel to or after C1–C4 is fine for engine integrity, but it does NOT move ARPU and is therefore out of the Phase 6B founder-feedback plan. Track as Phase 6C-DS, scope it independently, and flag `promo_anomaly_240d` as not-for-external-beta until done. The founder review explicitly endorses this deferral. |
| **Outcome-log / `would_be_measured_by` real attribution wiring** | Caveat #12. Depends on segment AOV, control-group definition, Klaviyo attribution. Hard guardrail in this plan: "Do NOT add outcome-log measurement wiring." Until the recommendation surface is sharp enough to be worth measuring, building the measurement plumbing is premature. Phase 7+. |
| **Per-segment AOV in opportunity context** | Caveat #4. Store-wide L28 with disclaimer is good enough at the founder-testing tier. Disclaimer carries the trust load. |
| **Calibrated lift / projected revenue on experiment cards** | Hard guardrail. Would destroy the trust win. Forever-deferred unless the engine ships measurement first. |
| **A/B test scaffolding inside the briefing** | Hard guardrail. Theatre without measurement. |
| **Numeric confidence score per card** | Hard guardrail. The `Emerging` / `Run as experiment` / `Measured` badges are doing the right job. |
| **More play archetypes** | Hard guardrail. Library is the right size; expanding it before render-quality lands multiplies grey-card volume. |
| **Klaviyo / Shopify direct-publish** | Hard guardrail. Out of charter. |
| **Watching section populated from State-of-Store trend stats (deeper version of C4)** | The founder review's full version of priority #4 is "populate Watching with the descriptive trends already computed in State of Store." That requires plumbing: a typed accessor from `Observation` records to `WatchedSignal`, deduping against existing watching rows, ordering by anomaly magnitude, capping at 4. C4 ships only the cheap copy fallback for empty Watching; the full plumbing is Phase 6C. |
| **Cold-start "first 90 days plan" template** | Founder review section 2c smallest-improvement #8 — convert ABSTAIN_HARD from refund event to onboarding event. Genuinely good idea, but it requires writing static onboarding-play templates, deciding on copy register, and routing a new section type. Out of Phase 6B scope; revisit after C1–C4 land and we have founder feedback on whether ABSTAIN_HARD continues to feel like a refund event. |
| **Recommended-Now cap raise from 1 to 2 for healthy mid-market** | Founder hesitation 7a. Touches `src/decide.py` cap of 3 / inner ranking and the role-uniqueness invariant. Genuinely a selector-layer change; not a render-layer change. Out of Phase 6B charter. Phase 6C+. |

---

## 8. Handoff prompt for code-refactor-engineer (Ticket C1 only)

```
You are the code-refactor-engineer for BeaconAI Action Engine. You are
implementing exactly ONE Phase 6B ticket: C1 — Surface "What we'd send"
mechanism copy on Recommended Now and Recommended Experiment cards.

CONTEXT (do not re-derive)

- Phase 6A shipped at commit 585480e behind ENGINE_V2_DECIDE +
  ENGINE_V2_OUTPUT + ENGINE_V2_SLATE. Founder testing only. Not external beta.
- Phase 6A Ticket A3 (commit d8b7859) added priors metadata loading via
  src/priors_loader.py and the dual list/dict YAML form is intentionally
  accommodated; route through _extract_play_block. The priors YAML at
  config/priors.yaml carries a per-play `mechanism` string that is loaded
  but NOT currently surfaced on the rendered card. This ticket surfaces it.
- Phase 6A Ticket A2 (commit e11f7c5) added the WouldBeMeasuredBy enum
  and PlayCard field that drives the "We will measure ___ in N days" line.
  Mechanism is a SEPARATE concept: it describes what to send, not what
  to measure. Do not conflate them and do not collapse them into one line.

WHAT TO BUILD

1. Add a typed accessor (or extend the existing one) in
   src/priors_loader.py to return Optional[str] for the
   merchant-readable `mechanism` string, scoped by (play_id, vertical,
   subvertical). Reuse _extract_play_block. Do not create a new YAML
   loader. Do not modify the cache semantics.

2. In src/storytelling_v2.py:
   a. Add a private helper `_render_what_we_send(mechanism: Optional[str]) -> str`
      that returns either an empty string (when mechanism is None or empty)
      or `<p class="play-card__what-we-send"><strong>What we'd send:</strong> {escaped}</p>`.
   b. Call the helper inside the directional and experiment card render paths.
      Place the line BETWEEN the audience block and the measured-by line on
      experiment cards, and BETWEEN the audience block and the observed-metric
      line on directional cards. Do NOT call it from the Considered or Watching
      render paths. Do NOT call it from the ABSTAIN_HARD memo path.
   c. Add a `.play-card__what-we-send { ... }` rule to the inline CSS block
      at the top of the rendered HTML. Style: regular weight body, slight
      indent, no border. Visually subordinate to recommendation/why-now,
      visually superior to disclaimer.

3. Re-pin tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html
   AND its sha256 fixture-pin in the B6 test that asserts byte-stability.
   Document the byte-change in the commit message.

4. Add tests/test_what_we_send_render.py with at minimum:
   - test_mechanism_renders_on_recommended_directional
   - test_mechanism_renders_on_recommended_experiment
   - test_mechanism_absent_on_considered_and_watching
   - test_mechanism_omits_when_string_missing

CONSTRAINTS — these are non-negotiable

- DO NOT add a new field to PlayCard. The mechanism is a render-time
  lookup from priors.yaml, not a typed engine-output field.
- DO NOT change src/decide.py or any selector-seam code. C1 is render-only.
- DO NOT add Shopify or Klaviyo integrations.
- DO NOT add outcome-log measurement wiring.
- DO NOT add A/B split scaffolding.
- DO NOT add revenue projections / calibrated lift / "predicted lift"
  anywhere, including via the mechanism string content.
- DO NOT unsuppress revenue_range.
- DO NOT add a numeric confidence score per card.
- DO NOT add new play types or expand the play library.
- DO NOT modify M0 goldens (small_sm, mid_shopify, micro_coldstart) —
  they MUST remain byte-identical. C1 only fires under ENGINE_V2_OUTPUT=true.
- DO NOT change the legacy storytelling.py renderer.
- DO NOT change the Phase 6A B2 forbidden-token sweep on
  section.recommended-experiment. The new mechanism line MUST pass that
  sweep. If any priors-authored mechanism contains a banned token
  (projected/predicted/calibrated/lift/forecast/p =/etc.), the priors
  YAML MUST be edited, not the sweep.
- DO NOT auto-generate or LLM-generate mechanism content. If priors.yaml
  is missing a mechanism for a play, omit the line. Populating the YAML
  is a separate content task, not part of C1.
- DO NOT change the Phase 6A test_targeting_no_dollar_headline.py invariant.
  The mechanism line MUST NOT contain a `$XX,XXX` pattern.
- DO NOT weaken the trust contract. The mechanism is "what we'd send" —
  audience + channel + posture + cadence — never "what lift to expect".

ACCEPTANCE

- pytest -q is green: 900+ passed, the same skip count, 0 failed,
  plus your new tests in test_what_we_send_render.py.
- M0 golden diff (pytest tests/test_golden_diff.py) is green.
- B2 forbidden-token sweep on section.recommended-experiment is green.
- B6 fixture pin is updated to the new sha256 and is green.
- ENGINE_V2_OUTPUT=false reverts to byte-identical pre-C1 V2 output (no, it
  reverts to the legacy renderer entirely, which is the kill switch — the
  V2 renderer with the flag on is the only place the new line appears).
- A founder reading the pinned Beauty briefing can answer "what's the
  actual email?" for every Recommended Now and every Recommended
  Experiment card without leaving the page.

Run pytest. Open one PR. Do not bundle C2/C3/C4. Do not refactor anything
unrelated. Done.
```

---

## 9. Risks and rollback

- **Re-pinning the Beauty fixture is the only structural risk.** Each ticket re-pins it. Sequence: ship C1, re-pin, then ship C2, re-pin, then ship C3, re-pin. Do NOT bundle. If a re-pin reveals an unexpected diff (e.g., M0 golden contamination), revert that single ticket.
- **Kill switch:** `ENGINE_V2_OUTPUT=false` reverts to the legacy renderer for all four tickets simultaneously. Founder can fall back at any time.
- **Selector-layer untouched:** none of C1–C4 modify `src/decide.py`, the experiment selector, or guardrails. Phase 6A trust contract holds.

## 10. What not to touch yet

- `src/decide.py` — selector-layer is locked for Phase 6B.
- `src/guardrails.py` — guardrail thresholds are locked.
- `src/sizing.py` — revenue-range suppression rules are locked.
- M0 fixtures (`small_sm`, `mid_shopify`, `micro_coldstart`) and `tests/test_golden_diff.py`.
- Phase 6A B2 forbidden-token sweep, B3 ABSTAIN_SOFT routing, B4 role-uniqueness invariant, B6 considered-filter.
- The legacy `src/storytelling.py` renderer.
- `src/copykit.py` (legacy copy module).
- `config/priors.yaml` schema (content edits to authored `mechanism` strings are OK; schema additions are OUT of Phase 6B scope).
- AnomalousWindow auto-registration — Phase 6C-DS owns this.
- Outcome-log wiring — Phase 7+.

---

_End of plan. Saved to `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-phase6b-founder-feedback-plan.md`._
