# code-refactor-engineer — S-FE-descriptive-distribution summary

**Ticket:** FOUNDER-AUTHORIZED additive engine change — `Audience.descriptive_distribution` (schema 2.0.0 → 2.1.0).
**Authority:** `docs/evidence_layer.md` §7 L-EV-18/19/20 + §8 (descriptive/inferential frame). Founder-authorized 2026-06-02.
**Deviation check:** none.

## The atom shape

`DescriptiveDistribution` (new dataclass, `src/engine_run.py`):

- `kind: DistributionKind` — closed 4-member str-Enum, no generic fallback (L-EV-19 lock): `DORMANCY_DAYS`, `AOV_GAP`, `REORDER_GAP_DAYS`, `DISCOUNT_FRACTION`.
- `bins: List[float]` — ascending bin edges; `len(bins) == len(counts) + 1`.
- `counts: List[int]` — observed count per bin; `counts[i]` counts `[bins[i], bins[i+1])`, final bin closed on the right.
- `marker: Optional[float]` — real window/threshold annotation when one exists; `None` when the underlying scalar parameter is None/TODO(S14). A `None` marker is the typed-absence of the annotation line, NOT a series suppression (L-EV-20).
- `suppressed: bool` + `suppression_reason: Optional[DescriptiveDistributionSuppressionReason]` — RULE-A paired typed absence (RevenueRange precedent). Invariant: `suppressed=True` ⇔ `suppression_reason is set`.

`DescriptiveDistributionSuppressionReason` (new closed 3-member str-Enum): `SOURCE_SERIES_EMPTY`, `SOURCE_SERIES_ABSENT`, `INTEGRITY_FAILED`.

`Audience.descriptive_distribution: Optional[DescriptiveDistribution] = None` — additive field. Outer Optional is `null_reason_exempt` because absence-typing lives INSIDE the atom (mirrors the `PlayCard.revenue_range` exemption). All four symbols + the `build_descriptive_distribution` helper exported via `__all__`.

## The 4 kinds + their builder source lines (`src/audience_builders.py`)

Builders stay pure (no `engine_run` import): each stashes raw `descriptive_kind` (string value), `descriptive_series: List[float]`, `descriptive_marker` on `AudienceResult`. The producer bins + types them.

| Kind | Play / builder | Source series | Marker |
|---|---|---|---|
| `DORMANCY_DAYS` | `winback_dormant_cohort_candidates` | `days_since` (built ~L267) subset to resolved cohort `ids` | `wb_hi` = dormancy-window upper bound (45 beauty/mixed, 120 supplements) — **real, builder-derived** |
| `REORDER_GAP_DAYS` | `replenishment_due_candidates` | per-customer `days_since` accumulated in the `_audience_for_keyer` closure (~L599) into `reorder_gap_by_cust` | `None` (replenishment_window_days is None/TODO(S14)) |
| `DISCOUNT_FRACTION` | `discount_dependency_hygiene_candidates` | `eligible["frac"]` (per-customer discount fraction; ≥0.5 cohort, ~L862) | `None` (target_discount_share is None/TODO(S14)) |
| `AOV_GAP` | `aov_lift_via_threshold_bundle_candidates` | per-customer `in_band` AOV (`cart_by_cust` / `avg_by_cust`, ~L1093/1143) into `aov_by_cust_band` | `None` (threshold_aov annotation parameter is None/TODO(S14); the builder's internal `threshold` is a band-derivation input, not the L-EV-20 marker) |

Producer seam: `src/measurement_builder.py` — `_maybe_build_descriptive_distribution(candidate)` coerces the stashed kind to `DistributionKind`, looks up fixed bin edges, calls `build_descriptive_distribution`, and attaches the atom at the prior-anchored `Audience(...)` site (the single construction site that serves all 4 distributional plays via `_PRIOR_ANCHORED`). Returns `None` for any candidate with no stashed kind (every non-distributional play) so `Audience.descriptive_distribution` stays `None`.

## Binning convention (chosen, fixed)

Fixed per-kind bin edges live in `measurement_builder._DESCRIPTIVE_BIN_EDGES` so charts are comparable across runs/stores:

- `DORMANCY_DAYS`: `[0,21,30,45,60,90,120,180]`
- `REORDER_GAP_DAYS`: `[0,15,30,45,60,90,120,180]`
- `AOV_GAP`: `[0,25,50,75,100,150,200,300,500]`
- `DISCOUNT_FRACTION`: `[0,0.25,0.5,0.6,0.7,0.8,0.9,1.0]`

`build_descriptive_distribution` (pure helper in `engine_run.py`) counts `[edges[i], edges[i+1])`, final bin closed on the right, and **clamps** out-of-range observations into the edge bins so no observed value is dropped (descriptive integrity). `len(counts) == len(bins) - 1`. A `None`/empty/non-finite-only series yields a typed `suppressed=True` atom (`SOURCE_SERIES_ABSENT` / `SOURCE_SERIES_EMPTY` / `INTEGRITY_FAILED`) with empty `bins`/`counts` — never a fabricated distribution.

## Descriptive-only conformance (L-EV-20)

- The atom's field set is exactly `{kind, bins, counts, marker, suppressed, suppression_reason}` — pinned by `test_descriptive_only_no_dollar_or_lift_field_on_atom`, which also asserts no field name contains dollar/revenue/value/lift/rate/projected/forecast/p10/p50/p90/aov substrings.
- No projected rate, no dollar figure, no lift on the atom. The only dollar-adjacent surfaces remain M3/M8 (RevenueRange) + M9 (NonLiftAtom).
- Engine emits the binned series only — no chart-spec (no axis/color/type), per L-EV-3 Stop-Coding Line.

## Version bump + schema mirror

- `EngineRun.schema_version` literal `"2.0.0"` → `"2.1.0"` (additive within the founder lock-in #3 2.x.x freeze).
- New `v2.1.0` CHANGELOG block prepended in `src/engine_run.py`; NULL-REASON ENUM REGISTRY comment block updated (new paired reason documented).
- `tools/generate_schema.py` title `"EngineRun v2.0.0"` → `"v2.1.0"`; `schemas/engine_run.v2.json` regenerated (the generator auto-discovers the new dataclass + enums by module membership — `DescriptiveDistribution`, `DistributionKind`, `DescriptiveDistributionSuppressionReason` all present in `$defs`; `Audience.properties` gains `descriptive_distribution`).
- `tools/validate_engine_run.py` PASSES against a fresh e2e run (`schema_version: 2.1.0`), and against synthetically-populated + suppressed + empty EngineRuns.

## Fixture re-pins (which move + why)

- **No SHA re-pins.** Per `tests/fixtures/pinned_sha_ledger.json::_meta.engine_run_json_sha_caveat`, the engine_run.json SHAs carry wall-clock `fit_timestamp` and are explicitly "documentation, not a re-runnable test fixture." The load-bearing gates are structural/AST/round-trip tests. A documentation-only `post_s_fe_descriptive_distribution_definition` meta note was added describing the additive shape change.
- **briefing.html unchanged** — the renderer does not consume the new field (no merchant-facing change this ticket).
- The two version literals in `tests/test_s13_6_t5_schema_version_2_0_0.py` were updated `2.0.0 → 2.1.0` (the explicit version-bump deliverable); the S13.6-T5 CHANGELOG anchor-phrase checks still pass (that block is preserved).

## Files changed

- `src/engine_run.py` — `DistributionKind`, `DescriptiveDistributionSuppressionReason`, `DescriptiveDistribution`, `build_descriptive_distribution` + `_is_finite`; `Audience.descriptive_distribution` field; `_from_dict_descriptive_distribution` + `_from_dict_audience` wiring; `__all__` + CHANGELOG + registry comment + `schema_version` bump.
- `src/audience_builders.py` — 3 stash fields on `AudienceResult`; series capture in the 4 distributional builders.
- `src/measurement_builder.py` — imports; `_DESCRIPTIVE_BIN_EDGES` + `_maybe_build_descriptive_distribution`; attach at the prior-anchored `Audience(...)` site.
- `tools/generate_schema.py` — title → v2.1.0.
- `schemas/engine_run.v2.json` — regenerated.
- `tests/test_s_fe_descriptive_distribution.py` — NEW (22 tests).
- `tests/test_s13_6_t5_schema_version_2_0_0.py` — version literals 2.0.0 → 2.1.0.
- `tests/fixtures/pinned_sha_ledger.json` — documentation-only meta note.

## Tests / checks run

- `tests/test_s_fe_descriptive_distribution.py`: **22 passed** (atom round-trip; descriptive-only guard; closed-set enums; binning convention + clamping per kind; empty/absent/integrity-failed → suppressed+typed reason; marker-None pass-through; builders stash kind+series; producer binds typed atom; full `build_prior_anchored_play_card` integration; from_dict 2.0.0 back-compat).
- Consolidated affected suites (engine_run / schema / no-silent-nulls AST / null-reason registry / schema-version / schema-generator / audience builders / winback_dormant / discount / aov bundle): **209 passed**.
- Full `tests/` regression filtered to affected surfaces: **822 passed, 3 skipped, 2 xfailed**. The only 3 failures (`test_s3_memory_event_schemas.py` x2, `test_s6_t3_z_considered_render.py` x1) are **pre-existing on the stashed baseline** — confirmed unrelated to this ticket.
- e2e: ran the engine on the winback/healthy beauty synthetic fixtures; emitted `engine_run.json` validates PASS against the regenerated schema with `schema_version: 2.1.0`.

## Behavior changes

- Additive only. Every existing field unchanged; `from_dict` tolerates absence of the new field (older runs → `None`).
- The 4 distributional plays, when they surface through the prior-anchored pathway, now carry a typed `Audience.descriptive_distribution`. Every other play has it `None`.
- No merchant-facing / renderer change; no narration/frontend change; no chart-spec.
- Single-demote-channel invariant + pure-builder discipline preserved (builders do not import `engine_run`; no new post-guardrails append path).

## Remaining risks / next-milestone dependencies

- **Markers None for 3 of 4 kinds** by design (threshold_aov / replenishment_window_days / target_discount_share are None/TODO(S14)). When S14 supplies those scalar parameters, the existing `descriptive_marker` stash carries them through with no schema change.
- **Replenishment series shape:** one observed reorder-gap per customer (smallest gap when a customer qualifies via multiple SKU buckets) — a deterministic descriptive choice; revisit if S14 wants per-(customer,SKU) granularity.
- Frontend per-mechanism selection map (L-EV-17) + narration consumption are downstream and untouched here (out of scope).
- Left unstaged for orchestrator + DS review per the brief.
