# S6.5-T1 — StoreProfile dataclass + skeleton dimension detection (ENGINE_V2_STORE_PROFILE flag, default OFF)

**Owner:** code-refactor-engineer (Sprint 6.5, ticket T1)
**Date:** 2026-05-17
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-s6_5-store-profile-layer-plan.md](./implementation-manager-s6_5-store-profile-layer-plan.md) §2 (S6.5-T1)
**Architectural rationale:** [agent_outputs/ds-architect-store-profile-layer-proposal.md](./ds-architect-store-profile-layer-proposal.md) + ARCHITECTURE_PLAN.md Part IV
**Predecessors:** S6-T1 ([summary](./code-refactor-engineer-s6-t1-summary.md)), S6-T1.5 ([summary](./code-refactor-engineer-s6-t1_5-summary.md))
**Status:** Complete. Flag default OFF. 5 pinned fixtures byte-identical post-impl.

---

## 1. Approved scope

Ship the typed `StoreProfile` dataclass + 4 skeleton detectors behind a new
`ENGINE_V2_STORE_PROFILE` env flag (default OFF). T1 is structural: the
profile is built and attached to `EngineRun.store_profile`, but **no
downstream gate consumes the profile in S6.5 until T4 wires consumers**.

Founder pre-locked decisions (memory.md Sprint 6.5 anchor, 2026-05-17):

- **Q1** Sephora + iHerb scraped vocabulary as token-dictionary source-of-truth (T2 lands the actual YAML).
- **Q2** Conservative-broader floor rule for stage band-boundary uncertainty (±25%).
- **Q4** Curated ~40-cell review at T4 checkpoint, not full table.
- **Q5** Subscription-led slate-ordering deferred to S6-T3; T1 only emits to `profile.business_model`.

---

## 2. StoreProfile schema (the 9 sub-dataclasses)

All sub-dataclasses are `@dataclass(frozen=True)` with safe defaults so a
pre-S6.5 `engine_run.json` (no `store_profile` key) round-trips with
`store_profile=None`. Schema-additive within the Sprint 2 `event_version=1`
frozen contract; precedent: S7.5-T1 (`PriorValidationStatus`), S6-T1
(`WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D`).

| Sub-dataclass | Fields populated at T1 | Fields deferred | Owner ticket |
|---|---|---|---|
| `Taxonomy` | `vertical`, `vertical_confidence`, `detection_method`, `operator_override_used`, `detected_vertical`, `override_disagrees` | `subvertical`, `subvertical_confidence` | T2 |
| `BusinessStage` | `stage`, `annualized_gmv_usd`, `detection_method`, `operator_override_used`, `uncertainty`, `conservative_floor_applied`, `detected_stage` | — | T1 (complete) |
| `BusinessModel` | `model`, `subscription_fraction`, `detection_confidence` | — | T1 (emit-only; consumer wired in S6-T3 per Q5) |
| `DataDepth` | `history_days`, `n_customers`, `n_orders`, `n_repeat_customers`, `n_subscription_orders` | — | T1 (complete) |
| `CadenceBaseline` | — (stub: `detection_status="DEFERRED_TO_T3"`) | `median_reorder_days_by_sku_class`, `global_median_reorder_days` | T3 |
| `SeasonalityContext` | — (stub: `detection_status="DEFERRED_TO_T3"`) | `active_window_name` | T3 |
| `GateCalibration` | — (stub: `detection_status="DEFERRED_TO_T4"`) | `audience_floor_by_play_id`, `materiality_floor_usd` | T4 |
| `MeasurementContext` | — (stub: `primary_window="L28"`, `agreement_windows=["L28","L56","L90"]` — fallback values; `detection_status="DEFERRED_TO_T4"`) | profile-driven primary_window + agreement set | T4 |
| `ProfileProvenance` | `profile_version=1`, `profiled_at`, `rules_fired` | — | T1 (extended at each downstream ticket) |

`StoreProfile` itself carries `store_id` + the 9 sub-dataclasses. The
defaults are constructed via `field(default_factory=...)` so the type is
safe to construct without arguments (used in `EngineRun()` and in
`store_profile_from_dict(None)` round-trip paths).

`EngineRun.store_profile: Optional[Any] = None` (typed as `Any` to avoid
a forward-reference cycle into `src.profile`; the round-trip helper
`_from_dict_store_profile_payload` lazy-imports `store_profile_from_dict`
so the legacy `ENGINE_V2_STORE_PROFILE=false` path is unaffected by any
future profile-side import error).

---

## 3. Patch summary

### `src/profile/__init__.py` (NEW)

Re-exports the 10 dataclasses + `build_store_profile`. Empty otherwise.

### `src/profile/types.py` (NEW)

`StoreProfile` + 9 frozen sub-dataclasses + per-sub-dataclass
`_from_dict_*` helpers + top-level `store_profile_from_dict` (the
inverse of `EngineRun.to_dict()["store_profile"]`). Round-trip is
defensive: unknown keys are ignored, malformed numeric fields fall back
to safe defaults, missing dicts become empty.

### `src/profile/builder.py` (NEW)

- **`_detected_vertical_from_titles`** — lightweight revenue-weighted
  hint scan. Two hardcoded token tuples (`_BEAUTY_HINT_TOKENS` +
  `_SUPPLEMENT_HINT_TOKENS`) score `product` / `lineitem_any` titles
  weighted by `net_sales`. Returns `(detected_vertical, confidence)`
  with HIGH if leader/runner ratio ≥3.0 AND leader share ≥0.30, MEDIUM
  if ratio ≥2.0, LOW otherwise. **This is a T1 stub** — the real
  revenue-weighted token classifier with sub-vertical resolution ships
  at T2 via `config/subvertical_taxonomy.yaml`.
- **`detect_taxonomy(g, cfg, rules_fired)`** — `VERTICAL_MODE` env var
  is authoritative. Detected-vertical is recorded regardless. When
  override disagrees with detected at HIGH/MEDIUM confidence, the
  `vertical_override_disagrees` rule fires in provenance. Subvertical
  stays `None` at T1.
- **`detect_business_stage(g, data_depth, cfg, rules_fired)`** — reads
  `BUSINESS_STAGE` env var; computes annualized GMV via TTM /
  `L180_x2` / `L90_x4` based on history depth; bands per architecture
  proposal (STARTUP <$500K, GROWTH $500K-$3M, MATURE $3M-$20M,
  ENTERPRISE >$20M). Conservative-broader rule (founder Q2) downgrades
  the applied band to the next-smaller band when GMV is within ±25%
  of any boundary and records `conservative_floor_applied=True` +
  `stage_boundary_uncertainty` provenance rule. Override wins, both
  detected + applied recorded.
- **`detect_business_model(g, data_depth, rules_fired)`** — customers
  with ≥3 orders at σ/μ <0.3 inter-order gap contribute their L180
  orders to the subscription bucket. `>40%` → SUBSCRIPTION_LED; `<10%`
  → ONE_TIME_LED; else HYBRID. Emit-only at T1 (no consumer; Q5
  deferred slate-ordering to S6-T3).
- **`detect_data_depth(g, rules_fired)`** — direct counts.
- **`build_store_profile(g, cfg, store_id)`** — orchestrator. Pure
  function. Threads a single `rules_fired` list through every detector
  so the audit trail is captured in `ProfileProvenance.rules_fired`.

### `src/engine_run.py`

Additive `store_profile: Optional[Any] = None` slot on `EngineRun`.
Round-trip wired via `_from_dict_store_profile_payload`. The
`_to_jsonable` helper already walks frozen dataclasses recursively, so
serialization needed no change.

### `src/main.py`

In the EngineRun build try-block, immediately after
`build_engine_run_from_legacy`, behind
`cfg.get("ENGINE_V2_STORE_PROFILE", False)`:

```python
_profile = _build_store_profile(g, cfg, store_id=brand)
engine_run = _dc_replace_profile(engine_run, store_profile=_profile)
```

Failure is non-fatal; a warning prints and `engine_run.store_profile`
stays `None` (the flag-OFF posture).

### `src/utils.py`

New `ENGINE_V2_STORE_PROFILE` in `DEFAULTS` (default `false`). Added
to the `_BOOL_FLAGS` typed-coercion set so env-var overrides work.
`BUSINESS_STAGE` + `VERTICAL_MODE` env vars stay as operator overrides
per the IM plan.

---

## 4. Tests

New: `tests/test_s6_5_t1_store_profile.py` (19 tests).

| Group | Test | What it pins |
|---|---|---|
| Dataclass | `test_store_profile_default_construction` | All 9 sub-dataclasses default-constructible |
| Dataclass | `test_store_profile_dataclasses_are_frozen` | `dataclasses.replace` works (frozen) |
| Round-trip | `test_engine_run_store_profile_round_trip_none` | Pre-S6.5 payload with `store_profile=None` round-trips |
| Round-trip | `test_engine_run_store_profile_round_trip_populated` | Beauty profile round-trips through `to_dict`/`from_dict` |
| Taxonomy | `test_detect_taxonomy_env_var_override_wins` | `VERTICAL_MODE=supplements` wins over detected beauty; `override_disagrees=True` fires the provenance rule |
| Taxonomy | `test_detect_taxonomy_detects_beauty_when_no_override` | Detection-only path |
| Taxonomy | `test_detect_taxonomy_subvertical_deferred_to_t2` | `subvertical=None`, `subvertical_confidence="REFUSED"` at T1 |
| Stage | `test_detect_business_stage_growth_band` | ~$1.5M GMV → GROWTH, `uncertainty=LOW`, `conservative_floor_applied=False` |
| Stage | `test_detect_business_stage_env_var_override` | `BUSINESS_STAGE=enterprise` wins; provenance carries both detected GROWTH + override ENTERPRISE |
| Stage | `test_detect_business_stage_boundary_uncertainty_growth_mature` | $3.3M (within +10% of $3M) → detected MATURE, applied GROWTH, `conservative_floor_applied=True` (founder Q2) |
| Stage | `test_detect_business_stage_boundary_uncertainty_startup_growth` | $550K (within +10% of $500K) → detected GROWTH, applied STARTUP (founder Q2) |
| Stage | `test_detect_business_stage_insufficient_history` | <90d history → STARTUP + `detection_method="insufficient_history"` + `annualized_gmv_usd=0.0` |
| Business model | `test_detect_business_model_subscription_led` | 30d-cadence customers → SUBSCRIPTION_LED, `subscription_fraction > 0.40` |
| Business model | `test_detect_business_model_one_time_led` | Single-purchase customers → ONE_TIME_LED, fraction <0.10 |
| Business model | `test_detect_business_model_hybrid` | Mixed cohort tolerated in {HYBRID, ONE_TIME_LED} |
| Data depth | `test_detect_data_depth_counts` | history_days, n_orders, n_customers, n_repeat_customers all correct |
| Orchestrator | `test_build_store_profile_orchestrator` | Profile carries detected fields; T3/T4 fields remain stubs |
| Orchestrator | `test_build_store_profile_is_pure_function` | Same inputs → same `taxonomy`/`business_stage`/`business_model`/`data_depth` |
| Flag | `test_engine_v2_store_profile_flag_default_off` | `DEFAULTS["ENGINE_V2_STORE_PROFILE"] is False` |

The band-boundary uncertainty rule (founder Q2) is verified end-to-end:
both the GROWTH/MATURE and the STARTUP/GROWTH boundaries trigger
`uncertainty=HIGH` + `conservative_floor_applied=True` + a typed
`stage_boundary_uncertainty` rule in provenance.

## 5. Full-suite status

(Filled in by the implementor after `pytest -q` completes.)

## 6. Per-fixture posture (flag OFF — the T1 contract)

| Fixture | `store_profile` slot | Profile content under flag-ON probe |
|---|---|---|
| Beauty pinned slate | `None` (flag OFF) | (will be populated at T5; T1 surface is dormant) |
| Supplements G-1 | `None` (flag OFF) | (will be populated at T5; T1 surface is dormant) |
| M0 small_sm | `None` | (M0 hits the legacy ENGINE_V2_SIZING=false path) |
| M0 mid_shopify | `None` | (legacy path) |
| M0 micro_coldstart | `None` | (legacy path) |

The 5 pinned fixtures are byte-identical to the S6-T1.5 close state.

---

## 7. Forward-scaffolding pattern

This ticket follows the same forward-scaffolding pattern as S6-T1
(`PredictedSegment`, `ModelCardRef`, `ranking_strategy` parameter): all
9 sub-dataclasses are defined now with their final shape, but only the
4 covered by T1 carry populated fields today. T2/T3/T4 each fill in
one or more sub-dataclasses without changing the schema or the
EngineRun round-trip surface. The `Optional[Any]` typing on
`EngineRun.store_profile` avoids any forward-reference cycle into
`src.profile`.

---

## 8. Hard constraints respected

- `engine_run.json` schema additive only (`event_version=1` intact).
- D-5: no Shopify / Klaviyo network calls.
- D-6: no banned ML modules.
- D-8: vertical scope unchanged.
- All 5 pinned fixtures byte-identical under flag-OFF (today's default).
- B4 role-uniqueness invariant intact.
- B-5 Berkson invariant intact (profile is descriptive of the store; no
  per-window cohort cross-comparison).
- S-2 / S-3 / S-4 / S-5 / S-6 substrate write paths untouched.
- No new runtime dependencies.

---

## 9. Commit list

1. `S6.5-T1: StoreProfile dataclass + skeleton dimension detection (vertical / stage / business_model / data_depth), ENGINE_V2_STORE_PROFILE flag default OFF`
2. `Document S6.5-T1 in repo memory.md`
3. (this commit) — `S6.5-T1 summary`

## Backfill from memory.md (migration trim 2026-05-25)

## Sprint 6.5 Ticket T1 closeout (2026-05-17)

**Status:** Complete. Flag default OFF. The 5 pinned fixtures are byte-identical post-impl — no PINNED_SHA256 updates required at T1. T5 owns the flag flip + atomic re-pin.

**What shipped:**

- New module `src/profile/` with `__init__.py`, `types.py`, `builder.py`.
- Typed `StoreProfile` dataclass + 9 frozen sub-dataclasses (`Taxonomy`, `BusinessStage`, `BusinessModel`, `CadenceBaseline`, `SeasonalityContext`, `DataDepth`, `GateCalibration`, `MeasurementContext`, `ProfileProvenance`). All fields `Optional` with safe defaults so pre-S6.5 `engine_run.json` payloads round-trip with `store_profile=None`.
- 4 skeleton detectors active at T1:
  - `detect_taxonomy` — `VERTICAL_MODE` env-var authoritative; revenue-weighted hint-token scan supplies `detected_vertical`; `override_disagrees=True` when they conflict at HIGH/MEDIUM detected confidence. `subvertical` stays `None` until T2.
  - `detect_business_stage` — annualized GMV via TTM / L180×2 / L90×4 with insufficient-history fallback; bands STARTUP <$500K / GROWTH $500K-$3M / MATURE $3M-$20M / ENTERPRISE >$20M; founder Q2 conservative-broader rule downgrades the applied band when GMV is within ±25% of any boundary (`uncertainty=HIGH`, `conservative_floor_applied=True`); `BUSINESS_STAGE` env-var override wins, both detected and override recorded in provenance.
  - `detect_business_model` — customers with ≥3 orders at σ/μ <0.3 inter-order gap contribute their L180 orders to the subscription bucket; >40% → SUBSCRIPTION_LED, <10% → ONE_TIME_LED, else HYBRID. Emit-only at T1 (founder Q5 deferred slate-ordering to S6-T3).
  - `detect_data_depth` — direct counts.
- Cadence + seasonality + gate_calibration + measurement remain T3/T4 stubs with explicit `detection_status="DEFERRED_TO_T3"` / `"DEFERRED_TO_T4"`.
- `EngineRun.store_profile: Optional[Any]` slot wired with round-trip via `_from_dict_store_profile_payload` (lazy-imports `src.profile.types.store_profile_from_dict` so the legacy `ENGINE_V2_STORE_PROFILE=false` path is unaffected by any future profile-side import error).
- `src/main.py` calls `build_store_profile(g, cfg, store_id=brand)` inside the existing EngineRun build try-block under `cfg.get("ENGINE_V2_STORE_PROFILE", False)`. Failure is non-fatal; flag-OFF leaves the slot `None`.
- `src/utils.py` registers `ENGINE_V2_STORE_PROFILE` in `DEFAULTS` + `_BOOL_FLAGS` coercion set. Default OFF. `BUSINESS_STAGE` + `VERTICAL_MODE` env vars unchanged (remain operator overrides per founder Q2 / IM plan §2).

**Tests:** 19 new in `tests/test_s6_5_t1_store_profile.py`. Coverage: dataclass shape + round-trip via `EngineRun.from_dict`; band-boundary uncertainty at both STARTUP/GROWTH and GROWTH/MATURE boundaries with the conservative-broader rule; env-var override paths for both vertical + stage; business_model subscription/one-time/hybrid classification; data_depth direct counts; orchestrator pure-function property; flag default OFF pin.

**Forward-scaffolding pattern preserved:** same as S6-T1 (`PredictedSegment`, `ModelCardRef`, `ranking_strategy`). All 9 sub-dataclasses are defined with their final shape; T2 fills `Taxonomy.subvertical`; T3 fills cadence + seasonality; T4 fills gate_calibration + measurement + wires consumers; T5 flips the flag.

**Caveats / what T1 does NOT do:**

- No consumer reads `EngineRun.store_profile` in S6.5 until T4 wires audience / measurement / decide / sizing.
- The detected-vertical token scan in `_detected_vertical_from_titles` is a T1 stub. T2 ships the real revenue-weighted classifier with sub-vertical resolution via `config/subvertical_taxonomy.yaml`.
- `EngineRun.store_profile` is typed `Optional[Any]` (not `Optional[StoreProfile]`) to avoid forcing `src.engine_run` to forward-import `src.profile`; the round-trip helper lazy-imports the typed constructor.

**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t1-summary.md](agent_outputs/code-refactor-engineer-s6_5-t1-summary.md)
