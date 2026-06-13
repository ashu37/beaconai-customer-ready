# S6-T3.z Summary — merchant-facing Considered render pass + audience_floor_sensitivity render on validated-path Recommended Now cards

**Ticket:** S6-T3.z (follow-up to S6-T3.y commits `9d3615c..a437739`)
**Date:** 2026-05-19
**Branch:** post-6b-restructured-roadmap
**Status:** Impl complete. Render-layer only. Flag remains default OFF (T3.5 owns activation). All 5 pinned fixtures byte-identical under flag OFF. Suite 1433 → 1451 passed.

---

## 1. Approved scope (5 items, all delivered)

1. `render_rejected_card` upgraded with additive cohort row, "What we'd send" mechanism line, and PRIOR_UNVALIDATED honest-dollar copy. Each branch is field-presence-gated.
2. `audience_floor_sensitivity` driver surfaced on validated-path Recommended Now cards via 3 render branches (robust collapse / floor-fragile edge warning / typical band chip).
3. `render_considered_section` lede flips from legacy copy to the T3.z copy only when at least one Considered card carries a T3.z field.
4. CSS additions localized into `_BRIEFING_CSS_T3Z`, appended only when an `EngineRun` actually renders a T3.z DOM branch.
5. 18 new tests in `tests/test_s6_t3_z_considered_render.py`. Suite 1433 → 1451 passed / 14 skipped / 0 failed.

---

## 2. Patch summary

### `src/engine_run.py`

- `RejectedPlay` gains 3 Optional fields (`audience_size`, `audience_definition`, `mechanism`), defaulting to `None`. Schema-additive within `event_version=1`. No enum change.
- `_from_dict_rejected` coerces `audience_size` via `int(...)` with safe `None` fallback; passes `audience_definition` / `mechanism` through as-is.

### `src/storytelling_v2.py`

- New copy constants: `CONSIDERED_LEDE_LEGACY`, `CONSIDERED_LEDE_T3Z`, `PRIOR_UNVALIDATED_NO_PROJECTION_COPY`, `FLOOR_FRAGILE_SENSITIVITY_COPY`.
- New helpers: `_rej_has_t3z_fields`, `_render_considered_cohort_row`, `_render_considered_no_projection`, `_find_audience_floor_sensitivity_driver`, `_render_audience_floor_sensitivity`, `_engine_run_has_t3z_surfaces`.
- `render_rejected_card` upgraded — additive branches only; pre-T3.z payloads (all 3 new fields `None`) fall through to the legacy render shape.
- `_render_measured_card` appends the sensitivity render after the existing range chip when present.
- `render_considered_section` chooses lede based on `any(_rej_has_t3z_fields(r) for r in rendered_items)`.
- New `_BRIEFING_CSS_T3Z` constant (5 CSS rules). `render_engine_run` appends it to the inline `<style>` block only when `_engine_run_has_t3z_surfaces(engine_run)` is True.

### `tests/test_s6_t3_z_considered_render.py` (NEW)

18 tests covering cohort row gating (3 variants), mechanism line, PRIOR_UNVALIDATED branch (2 variants — present/absent), HTML escaping (mechanism, definition, lede via `_esc`), lede flip (2 variants), 3 sensitivity branches, pre-T3.z byte-identity on a card without the driver, and pinned-fixture sha256 byte-identity on all 5 pinned fixtures.

---

## 3. Considered card HTML diff (illustrative — supplements `replenishment_due` PRIOR_UNVALIDATED with audience > 0 + mechanism)

**Before (pre-T3.z):**

```html
<article class="play-card play-card--rejected" data-play-id="replenishment_due" data-reason-code="prior_unvalidated">
  <h3 class="play-card__title">Replenishment timing</h3>
  <p class="play-card__reason"><strong>Why held:</strong> Prior is unvalidated; no comparable measurement exists yet.</p>
  <p class="play-card__reason-detail">held</p>
</article>
```

**After (T3.z, with `audience_size=412`, `audience_definition="customers within +/-3d of next replenishment"`, `mechanism="Email a replenishment reminder 3 days before the predicted run-out."`):**

```html
<article class="play-card play-card--rejected" data-play-id="replenishment_due" data-reason-code="prior_unvalidated">
  <h3 class="play-card__title">Replenishment timing</h3>
  <p class="play-card__reason"><strong>Why held:</strong> Prior is unvalidated; no comparable measurement exists yet.</p>
  <p class="play-card__reason-detail">held</p>
  <div class="play-card-aud play-card-aud--considered">
    <span class="play-card-aud__size"><strong>412</strong> people</span>
    <span class="play-card-aud__def">customers within +/-3d of next replenishment</span>
  </div>
  <p class="play-card__what-we-send">
    <strong>What we&#x27;d send:</strong> Email a replenishment reminder 3 days before the predicted run-out.
  </p>
  <p class="play-card__no-projection">
    We&#x27;re not projecting dollars on this play until we measure outcomes from a campaign on your store.
  </p>
</article>
```

The pre-T3.z shape is preserved exactly when `audience_size` is `None` / 0, `mechanism` is `None` / empty, and `reason_code != PRIOR_UNVALIDATED`. This is the path the 5 pinned fixtures take under flag OFF.

---

## 4. Recommended Now sensitivity-band HTML (3 illustrative cases)

Driver value shape (from T3.y):

```json
{ "name": "audience_floor_sensitivity", "value": { "p50_low": <float>, "p50_high": <float>, ... } }
```

### 4a. Robust collapse (Beauty winback, S6.5-T5 numbers — `p50_low == p50_high == 1686.59`)

Renderer returns the empty string. The card renders identically to the pre-T3.z shape — the existing revenue range chip is the only sensitivity surface. No "robust to ±25%" microcopy. This is the path the live Beauty winback card takes today; the pinned `healthy_beauty_240d_briefing.html` is byte-identical.

### 4b. Floor-fragile (`p50_low == 0.0`, `p50_high == 1050.0`)

```html
...
<span class="play-card-range-chip" data-source="blend"> ... </span>
<p class="play-card__sensitivity-edge">
  Today&#x27;s dollar estimate sits at a heuristic edge — under a 25%-higher audience floor, this cohort would not have surfaced.
</p>
...
```

### 4c. Typical band (`p50_low == 1200.0`, `p50_high == 1900.0`)

```html
...
<span class="play-card-range-chip" data-source="blend"> ... </span>
<span class="play-card-range-chip__sensitivity">Floor sensitivity: $1,200-$1,900</span>
...
```

---

## 5. CSS additions

Localized into a separate `_BRIEFING_CSS_T3Z` constant so the legacy `_BRIEFING_CSS` is byte-identical when no T3.z surface renders. Appended at the top-level `render_engine_run` seam only when `_engine_run_has_t3z_surfaces(engine_run)` returns True.

| Class | Rule | Rationale |
|---|---|---|
| `.play-card-aud--considered` | `color: #4a5568; font-size: 13px;` | Mute the existing `.play-card-aud` styling so it reads as cohort-that-exists-but-not-being-acted-on rather than cohort-we-are-recommending-against. |
| `.play-card-aud--considered > span` | `color: #4a5568;` | Ensure the inner size/definition spans inherit the muted color when nested under `play-card-aud > span` (which sets margin only). |
| `.play-card__no-projection` | `font-size: 13px; color: #4a5568; font-style: italic;` | Subtle italic. The honest-dollar copy is reassurance, not a headline. |
| `.play-card__sensitivity-edge` | `font-size: 13px; color: #744210; font-style: italic;` | Subtle warning tone (muted amber, matches the existing `.play-card__class-badge--directional` palette). |
| `.play-card-range-chip__sensitivity` | `display: inline-block; background: #fef5e7; color: #744210; padding: 3px 8px; border-radius: 6px; font-size: 12px; margin-left: 8px;` | Chip styling alongside the revenue chip; visually echoes `.play-card-range-chip` with a muted amber palette so it reads as "additional context on the same dollar number". |

The `_engine_run_has_t3z_surfaces` detector is RENDER-aware (not just driver-presence-aware): it returns False when the Beauty `audience_floor_sensitivity` driver is present but collapses to robust (`p50_low == p50_high`). This is what keeps the 5 pinned fixtures byte-identical under flag OFF.

---

## 6. Field population path

Three Optional fields added to `RejectedPlay` (schema-additive within `event_version=1`):

- `audience_size: Optional[int] = None`
- `audience_definition: Optional[str] = None`
- `mechanism: Optional[str] = None`

**No `decide.py` routing function was modified.** The hand-off below describes the wiring T3.5 is expected to add. T3.z deliberately leaves the seam open so today's producers (which call `RejectedPlay(...)` without the new kwargs) round-trip with the new fields defaulting to `None`. Round-trip discipline: `_from_dict_rejected` coerces `audience_size` to `int` with a `None` fallback on bad inputs; `audience_definition` and `mechanism` pass through as-is.

---

## 7. Flag-OFF byte-identity confirmation (all 5 pinned fixtures)

| Fixture | sha256 (pre-T3.z = post-T3.z) |
|---|---|
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `cacb6691b387b1770502a841f9c224d1fe76e5bc3be58802eafc8c5d0fa95269` |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95` |
| `tests/golden/small_sm/briefing.html` | `40bf24ea3c3632fa717293c82f66ac074d5e765ed29009b3297d2088952278e6` |
| `tests/golden/mid_shopify/briefing.html` | `380b2c5d0aa6806d81a38666c63603781e904f4e10a9fdfff72430551152d81a` |
| `tests/golden/micro_coldstart/briefing.html` | `2191b251edffbb7814e28a872e66b69e3d9289e680f077daa6ccea6a2694b2fc` |

Confirmed via `tests/test_s6_t3_z_considered_render.py::test_pinned_fixture_byte_identical_under_flag_off[*]` and via the existing pinned-fixture suites (`test_slate_regression_beauty_brand.py`, `test_slate_regression_supplements_brand.py`, `test_golden_diff.py`).

The Beauty `audience_floor_sensitivity` driver IS present on the live `winback_dormant_cohort` card (T3.y wired it under `ENGINE_V2_STORE_PROFILE`-on harness). It collapses to robust on the Beauty cohort (356 ≥ 250 = floor + 25%), so the renderer correctly returns the empty string for that card's sensitivity branch and `_engine_run_has_t3z_surfaces` returns False — the new CSS is suppressed and the bytes match.

---

## 8. Tests / checks run

- `tests/test_s6_t3_z_considered_render.py` — 18 passed (new file).
- `tests/test_slate_regression_beauty_brand.py`, `tests/test_slate_regression_supplements_brand.py`, `tests/test_golden_diff.py` — 34 passed; all 5 pinned sha256s held.
- **Full suite: 1451 passed / 14 skipped / 0 failed** (was 1433; +18 from new test file).

---

## 9. Behavior changes (today, under flag OFF)

**ZERO merchant-facing behavior change.** All new render branches are field-presence-gated and the new CSS block is render-presence-gated. Today's producers do not populate the new `RejectedPlay` fields, and the live Beauty `audience_floor_sensitivity` driver collapses to robust. The 5 pinned fixtures are byte-identical to the pre-T3.z state.

---

## 10. Hand-off to T3.5

To activate the T3.z surfaces on Beauty + supplements, T3.5 needs to:

1. **Populate `RejectedPlay.audience_size` / `audience_definition` / `mechanism` from candidate at Considered-routing time.** Two seams:
   - `_route_window_disagreement_holds` and `_route_prior_unvalidated_holds` in `src/decide.py` (these route by PlayCard; the PlayCard already carries `audience.size` / `audience.definition`; mechanism is via `src.priors_loader.get_mechanism(play_id)`).
   - `populate_considered_from_candidates` in `src/decide.py` (routes from raw `Candidate` objects; pull `audience_size`, `audience_definition`, and mechanism the same way the existing `evidence_snapshot` does).
   - Guard the population behind a flag (likely `ENGINE_V2_STORE_PROFILE` since T3.z is the merchant render counterpart of T3.y, which is gated there).
2. **Author `gate_calibration.yaml.audience_floors.replenishment_due.{vertical}.{subvertical}.{stage}`** so the `audience_floor_sensitivity` driver can fire on validated-path `replenishment_due` PlayCards. The profile builder must populate `audience_floor_by_play_id["replenishment_due"]` and `profile_field_refs["audience_floor.replenishment_due"]` as siblings of the existing `winback_dormant_cohort` cells.
3. **Atomic re-pin of all 5 fixtures** under the flag flip. The byte-shift is intentional and expected (new lede on the Considered section, new cohort/mechanism/no-projection lines on each Considered card, sensitivity surface on any non-robust Recommended Now card).
4. **Verify** that the supplements G-1 ABSTAIN_SOFT case renders the 6 Considered cards with the new merchant surface, and that Beauty `winback_dormant_cohort` continues to render robust (no sensitivity render) while `replenishment_due` either renders a floor-fragile warning or a typical band depending on the cohort size vs the new floor cell.

---

## 11. Invariants preserved

- D-5 / D-6 / D-8 intact (no Shopify/Klaviyo production integration; no banned ML modules; vertical scope unchanged).
- B-4 role-uniqueness intact (no slate/role changes).
- B-5 Berkson invariant intact (no cohort-definition logic touched).
- S-2..S-6 substrate write paths untouched.
- S7.5-T3 refusal logic UNCHANGED — `_route_prior_unvalidated_holds` semantics intact; T3.z only reads the existing `ReasonCode.PRIOR_UNVALIDATED` to decide whether to render the no-projection line.
- Schema-additive only within `event_version=1`. 3 Optional fields on `RejectedPlay`; pre-T3.z payloads round-trip with `None`.
- T3.y's `audience_floor_sensitivity` driver shape is UNCHANGED. T3.z is a pure reader.
- No new flags. No new runtime deps. No CSS rewrites — additions only.

---

## 12. Commit list (per 3-commit boundary)

1. **Impl** — `S6-T3.z: Considered surface render pass + audience_floor_sensitivity render on validated-path Recommended Now cards` — `src/engine_run.py`, `src/storytelling_v2.py`, `tests/test_s6_t3_z_considered_render.py`.
2. **Memory** — `Document S6-T3.z in repo memory.md`.
3. **Summary** — `agent_outputs/code-refactor-engineer-s6-t3_z-summary.md` (this file).

## Backfill from memory.md (migration trim 2026-05-25)

## S6-T3.z closeout — Considered render pass + audience_floor_sensitivity render on validated-path Recommended Now cards (2026-05-19)

**Shipped:**

- `RejectedPlay` gains 3 Optional schema-additive fields (`audience_size`, `audience_definition`, `mechanism`) within `event_version=1`. Pre-T3.z payloads round-trip unchanged.
- `render_rejected_card` upgraded with conditional cohort row (`play-card-aud--considered`), "What we'd send" mechanism line, and PRIOR_UNVALIDATED honest-dollar copy ("We're not projecting dollars on this play until we measure outcomes from a campaign on your store.") — each gated on field presence.
- `_render_audience_floor_sensitivity` surfaces T3.y's driver as 3 render branches: robust collapse (`p50_low == p50_high` → omit, no "robust to ±25%" microcopy), floor-fragile (`p50_low == 0.0` → `<p class="play-card__sensitivity-edge">` edge warning), typical band (`<span class="play-card-range-chip__sensitivity">Floor sensitivity: $X-$Y</span>`). Pure reader, never recomputes the band.
- `render_considered_section` lede flips from legacy to T3.z copy only when at least one card carries a T3.z field; legacy lede otherwise.
- New `_BRIEFING_CSS_T3Z` constant appended to `<style>` ONLY when an `EngineRun` actually renders T3.z DOM (`_engine_run_has_t3z_surfaces` is RENDER-aware — the mere presence of the `audience_floor_sensitivity` driver is NOT enough; the robust branch renders nothing and must not trip the CSS).
- 18 new tests in `tests/test_s6_t3_z_considered_render.py`.

**Load-bearing invariants:**

- Renderer NEVER recomputes the sensitivity band. T3.y's driver is the single source of truth.
- T3.z is render-layer only — `_route_window_disagreement_holds` / `_route_prior_unvalidated_holds` semantics UNCHANGED. T3.5 owns the candidate→`RejectedPlay` population path for the new fields and the activation of `audience_floor.replenishment_due` on Beauty.
- No "robust to ±25%" microcopy. Robust = omit the band entirely.
- New render branches are ALL field-presence-gated; new CSS is RENDER-presence-gated. The 5 pinned fixtures stay byte-identical under flag OFF (Beauty winback `audience_floor_sensitivity` driver is present but robust → renders nothing → CSS suppressed → bytes match).
- Directional-pathway Recommended Now cards untouched by the sensitivity render (driver is absent on directional by T3.y design).

**Caveats / dormant behavior:** All 5 pinned fixtures byte-identical under flag OFF (Beauty + supplements G-1 + 3× M0). T3.5 still owns the visible flip: it must populate `audience_size` / `audience_definition` / `mechanism` from candidate at Considered-routing time, AND author `gate_calibration.yaml.audience_floors.replenishment_due.{vertical}.{subvertical}.{stage}` + `profile.gate_calibration.audience_floor_by_play_id["replenishment_due"]` for the sensitivity driver to fire on Beauty replenishment_due.

**Schema:** `RejectedPlay` schema-additive within `event_version=1` (3 Optional fields default `None`; `_from_dict_rejected` coerces `audience_size` via `int(...)` with `None` fallback). No enum changes.
**Suite:** 1451 passed / 14 skipped / 0 failed (was 1433; +18 from new test file).
**Summary:** [agent_outputs/code-refactor-engineer-s6-t3_z-summary.md](agent_outputs/code-refactor-engineer-s6-t3_z-summary.md)
