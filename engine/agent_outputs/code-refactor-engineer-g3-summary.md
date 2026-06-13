# G-3 Summary — Vertical priors expansion (supplements) + `mixed` semantics

**Date:** 2026-05-10
**Branch:** post-6b-restructured-roadmap
**Ticket:** Sprint 4 G-3 (post-6b-restructured implementation plan §4)
**Outcome:** Supplements priors carry `source` provenance on every
entry; `mixed` semantics formalised behind a deterministic
`resolve_mixed_prior` blender; per-vertical audience floors plumbed
into the priors loader; D-8 hard-lock surfaced via `ConfigError` on
non-supported vertical_mode top-level blocks (already present from
B-7; G-3 adds the positive-projection refusal test). Suite **1152
passed / 14 skipped / 0 failed** (was 1141/14/0 at G-1 closeout;
delta = +11 G-3 tests). M0 Beauty pinned fixture byte-identical;
G-1 supplements pinned fixture byte-identical (sha256
`feb03500c1...` unchanged).

## 1. Approved scope

Per the ticket brief (Sprint 4 G-3):

1. `config/priors.yaml`: at least one observational baseline conversion-rate
   band per play for supplements; every supplements entry carries a
   `source` field; no invented causal priors.
2. Formalise `mixed` semantics: explicit mixed block OR deterministic
   beauty+supplements blend. NEVER silently default to beauty alone.
3. Per-vertical audience floors moved out of beauty-only inheritance
   into `priors.yaml`; supplements floor strictly smaller than beauty
   (KI-25 resolution path).
4. `src/play_registry.py::_ALL_VERTICALS` stays frozen at
   `frozenset({"beauty","supplements","mixed"})`.
5. Priors loader rejects non-supported vertical top-level blocks
   (D-8 hard-lock).

## 2. Patch summary

- **`config/priors.yaml`**: added a G-3 documentation header pinning
  the `mixed` semantics + source-provenance contract; added `source`
  field to every prior entry whose `applies_to.vertical` is
  `supplements` / `mixed` / `"*"` (58 entries); promoted
  `routine_builder` from legacy list form to A3 dict form with
  `metadata.audience_floor_by_vertical: {beauty:60, supplements:30,
  mixed:45}`; `last_reviewed` bumped 2026-05-01 → 2026-05-10.
- **`src/priors_loader.py`**: extended `PlayMetadata` with optional
  `audience_floor_by_vertical: Dict[str,int]`; new public helpers
  `get_audience_floor(play_id, *, vertical) -> Optional[int]` and
  `resolve_mixed_prior(play_id, *, key) -> Optional[PriorEntry]`;
  `_coerce_metadata` validates per-vertical floor keys against
  `_SUPPORTED_VERTICALS_FOR_LOADER` (D-8 inside metadata).
  `resolve_mixed_prior` blends beauty + supplements 50/50
  deterministically (arithmetic mean of value / range_p10 / range_p90;
  conservative `source_class` ordering for the blend); refuses to
  fall back to one side alone.
- **`tests/test_g3_supplements_priors.py`**: new — 11 tests pinning
  all three G-3 acceptance contracts.
- **`tests/test_priors_metadata.py`**: minor update — removed
  `routine_builder` from the "no metadata" assertion list since it
  is now in dict form. Header note explains the shift.
- **`KNOWN_ISSUES.md`**: KI-19 flipped `tracked` → `resolved` with
  G-3 commit context; KI-25 flipped `open` → `tracked` with
  progress note explaining the floor mechanism is in place but
  the legacy-builder rewire is Sprint 5+ scope; KI-28 stays
  `tracked` with explicit note that the loader-level test path is
  the G-3 contract and an end-to-end `mixed` fixture is deferred.
  Open-count table updated.

No engine-side wire-up of `get_audience_floor` into
`src/audience_builders.py` (legacy floor for `routine_builder` still
comes from `MIN_N_SKU` config). That plumbing is deliberately
Sprint 5+ scope so this ticket stays priors-only per the brief.

## 3. Files changed

| Path | Change |
|---|---|
| `config/priors.yaml` | Source-provenance on 58 entries; routine_builder dict-form promotion; G-3 header comment; `last_reviewed` bump |
| `src/priors_loader.py` | `PlayMetadata.audience_floor_by_vertical`; `get_audience_floor`; `resolve_mixed_prior`; per-vertical floor validation |
| `tests/test_g3_supplements_priors.py` | NEW — 11 tests |
| `tests/test_priors_metadata.py` | Remove `routine_builder` from "no metadata" assertion list |
| `KNOWN_ISSUES.md` | KI-19 resolved; KI-25 tracked-with-progress; KI-28 progress note; open-count table |

Untouched: `src/play_registry.py` (B-7 already pinned `_ALL_VERTICALS`
contract; no change needed); all S-2/S-3/S-4/S-5/S-6 substrate code;
M0 Beauty pinned fixture; G-1 supplements pinned fixture; the
Beauty priors blocks (every `applies_to: { vertical: beauty }`
entry is byte-identical).

## 4. Tests / checks run

- `tests/test_g3_supplements_priors.py`: **11/11 green**.
- `tests/test_priors_loader.py` + `tests/test_priors_metadata.py` +
  `tests/test_priors_yaml.py`: **45/45 green**.
- `tests/test_slate_regression_beauty_brand.py` (M0-equivalent):
  **19/19 green** — Beauty fixture byte-identical (sha256
  unchanged).
- `tests/test_slate_regression_supplements_brand.py` (G-1 pinned):
  **12/12 green** — supplements fixture byte-identical (sha256
  `feb03500c1...` unchanged).
- Full suite: **1152 passed / 14 skipped / 0 failed** in 670.73s
  (was 1141/14/0 at G-1 closeout; delta = +11 G-3 tests).

## 5. Behavior changes

Engine runtime behavior is **unchanged** under all supported
verticals on existing fixtures.

- Beauty fixture: every Beauty-keyed prior unchanged; the loader's
  new helpers (`get_audience_floor`, `resolve_mixed_prior`) are not
  yet called from any production code path on the Beauty path. The
  routine_builder dict-form promotion adds a `metadata` block that
  only affects (a) the Recommended Experiment seam in `src/decide.py`
  (routine_builder is NOT in the A4 allowlist `{discount_hygiene,
  bestseller_amplify}`, so the seam never reads it), and (b) the
  renderer's `_mechanism_for_play` lookup which only renders for
  Recommended Now / Recommended Experiment cards (routine_builder
  is in Considered today, so the mechanism string never renders).
- Supplements fixture (G-1): unchanged. The rejection reason for
  `routine_builder` is structural (audience computes to 0 because
  the audience builder filters to `skincare single-product buyers`
  which yields the empty set on a supplements catalog with no
  `skincare` category column), not floor-related. Even the new
  supplements floor of 30 would still reject an audience of 0.
  Engine-side rewire of the legacy audience builder to consume the
  per-vertical floor is documented in the KI-25 progress note as
  Sprint 5+ scope.
- `mixed` semantics: the existing YAML carries explicit
  `vertical: mixed` entries for every supplements-bearing
  (play, key) pair already, so today's `mixed` lookups resolve
  through the explicit path. The new `resolve_mixed_prior` is
  the engine-facing contract that pins the no-silent-beauty-fallback
  guarantee; it activates automatically the first time the YAML
  gains a beauty + supplements pair without a mixed/wildcard
  authored entry. Until then it is dormant-but-pinned.

## 6. Artifacts added

| Path | Purpose |
|---|---|
| `tests/test_g3_supplements_priors.py` | 11 pinning tests for source-field coverage, mixed-blend semantics, D-8 hard-lock |
| `src/priors_loader.py::get_audience_floor` | Public per-vertical floor lookup |
| `src/priors_loader.py::resolve_mixed_prior` | Deterministic mixed-blend resolver |
| `src/priors_loader.py::PlayMetadata.audience_floor_by_vertical` | Optional per-vertical floor mapping on the typed metadata |

## 7. Assumptions documented

Per the prompt's "smallest safe implementation, document assumptions"
guidance:

1. **Supplements observational priors.** The ticket asks for "at
   least one observational baseline conversion-rate band per play
   for supplements." For plays where the engine already carries an
   `observational` source_class on supplements (winback_21_45,
   frequency_accelerator base_rate, discount_hygiene margin_recovery),
   the entry was tagged `source: internal_csv_observation_v1`. For
   plays with only `expert` supplements entries (subscription_nudge,
   routine_builder, bestseller_amplify, aov_momentum, retention_mastery,
   journey_optimization, category_expansion), the entry was tagged
   `source: internal_heuristic_unvalidated` — the honest reading of
   the ticket's "internal heuristic flagged as such" clause. I did
   NOT invent new `observational` priors with unverifiable industry
   citations to satisfy the "at least one observational baseline per
   play" target; the trust contract bar is loud-flag-honest-source
   over checkbox-honoring. Five of fourteen plays carry observational
   supplements priors today; the remainder carry `expert`-with-source.
   This is consistent with the prompt's escape clause: "If no
   defensible observational basis exists for a play on supplements,
   leave it absent (and document why in the G-3 summary)."

2. **KI-25 resolution status.** The ticket asked for KI-25 to flip
   to `resolved`. The G-3 floor-mechanism IS in place (priors.yaml
   per-vertical, loader exposes it). But the G-1 supplements fixture's
   `routine_builder` rejection cause is structural — audience=0 from
   an audience-builder definition that is beauty-shaped, not
   floor-shaped. Even floor=1 would still reject audience=0. I flipped
   KI-25 to `tracked` (was `open`) with a verbose progress note
   instead of `resolved`. The honest call: floor mechanism is done;
   legacy-audience-builder plumbing is a separate Sprint 5+ ticket.
   This matches the prompt's "smallest safe implementation, document
   assumptions" instruction; over-claiming resolution would dilute
   the registry's signal.

3. **`mixed` semantics: deterministic 50/50 arithmetic mean.** No
   weighting authored today (50/50 is the trivially-defensible
   choice). A weighted blend (e.g. by merchant-count or revenue
   share within the mixed segment) is forward-compatible — the
   resolver's `applies_to.derived_from` field would name the inputs
   and a future field would name the weights. Conservative
   source_class ordering is `expert > observational > causal`
   (matches the M2 docstring).

4. **`routine_builder` `audience_archetype: no_archetype`.** The
   campaign-slate contract enum locks `no_archetype` as a valid
   value; routine_builder doesn't fit any of the more specific
   archetypes (`first_time_buyer`, `lapsed_buyer`, `discount_buyer`,
   `hero_sku_buyer`, `replenishment_buyer`, `full_price_buyer`,
   `vip_loyalist`). Future Sprint 5+ rewire may introduce a
   `single_product_buyer` archetype — additive.

## 8. Remaining risks

1. **Legacy audience-builder still uses `MIN_N_SKU` for routine_builder.**
   The per-vertical floor is in priors.yaml but not yet read by
   `src/audience_builders.py::routine_completion_candidates`.
   Filed as Sprint 5+ scope under KI-25. Engine behavior unchanged.

2. **No e2e `mixed` fixture.** The mixed-resolver is fixture-tested
   only via the priors-loader unit-test path; no `healthy_mixed_240d_*`
   end-to-end fixture is pinned. KI-28 documents the gap and the
   deferral rationale (would re-render the same supplements-shaped
   abstain pattern until KI-20 lands).

3. **`expert`-with-source dominates supplements.** Five of fourteen
   plays carry an `observational` supplements baseline; the rest
   are `expert` flagged `internal_heuristic_unvalidated`. The
   inventory of `expert` priors is the same as before G-3 — what
   changed is the loud `source` flag. A future calibration sprint
   would graduate observed plays from `expert` → `observational`
   once K=3 outcomes accumulate (Phase 9 work).

## 9. Follow-up work

| Priority | Ticket | KI | Scope |
|---|---|---|---|
| 1 | Plumb `get_audience_floor` into `audience_builders.py` | KI-25 | Engine-side wire-up; trivial after this ticket lands |
| 2 | Re-think `routine_builder` audience definition for supplements | KI-25 | Audience builder is currently `skincare single-product buyers` — replace with cadence-aware buyers for supplements |
| 3 | E2E `mixed` pinned fixture | KI-28 | Add once KI-20 closes so the mixed slate is non-trivial |
| 4 | Graduate supplements `expert` priors to `observational` | (new) | Phase 9 calibration loop — runs once K=3 outcomes accumulate per (play, supplements, store) |

---

**Bottom line:** G-3 ships the priors-level contracts the brief asked
for. `mixed` is now semantically deterministic and pinned with three
tests against silent beauty-fallback. Every supplements entry carries
provenance. Per-vertical floors live in priors.yaml with a typed
loader helper. The D-8 hard-lock is positively tested with synthetic
non-supported-vertical YAML fragments. KI-19 closed; KI-25 progress
flagged; KI-28 progress flagged. Beauty + supplements pinned fixtures
byte-identical. 1152/14/0.
