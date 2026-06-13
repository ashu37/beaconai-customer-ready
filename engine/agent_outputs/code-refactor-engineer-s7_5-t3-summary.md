# S7.5-T3 — Cold-start blend refusal + SOFT_PRIOR_UNVALIDATED (default-OFF)

**Owner:** code-refactor-engineer (Sprint 7.5, ticket S7.5-T3)
**Date:** 2026-05-17
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-s7_5-priors-validation-plan.md](./implementation-manager-s7_5-priors-validation-plan.md) §2, ticket S7.5-T3
**Design rationale:** `ARCHITECTURE_PLAN.md` Part III-1 §III-1 Steps 1–5
**Predecessor:** S7.5-T2 ([code-refactor-engineer-s7_5-t2-summary.md](./code-refactor-engineer-s7_5-t2-summary.md))
**Status:** Complete. Flag `ENGINE_V2_PRIORS_VALIDATION` lands default-OFF. ZERO behavior change at default. The behavior flip is T3.5.

---

## 1. Approved scope

Per the orchestrator handoff prompt:

- Wire `validation_status` into sizing + decide consumption behind `ENGINE_V2_PRIORS_VALIDATION` (default OFF).
- Sizing refusal rule: priors in `{heuristic_unvalidated, placeholder}` -> revenue range suppressed with reason `prior_unvalidated`. `validated_external` / `validated_internal` / `elicited_expert` permit the blend with the per-status `pseudo_N` cap.
- `PSEUDO_N_BY_STATUS = {validated_external: 30, validated_internal: 15, elicited_expert: 10}` lands as a module constant + a `bayesian_blend` helper for Sprint 6 Tier-B builders to import.
- KI-19 conservative-min rule on `resolve_mixed_prior`: the blended PriorEntry carries the LESS validated of the two sides.
- New abstain mode `SOFT_PRIOR_UNVALIDATED` distinct from `SOFT_AWAITING_MEASUREMENT`.
- New reason code `PRIOR_UNVALIDATED` for considered-fan-out routing.
- Default OFF; flag flip is T3.5's atomic ticket.

Founder pre-locked:
- **Q1:** No new external sources beyond T2's three. T3.5 ships exactly the three validated_external entries that T2 promoted.
- **Q2:** Default OFF in T3; T3.5 flips ON separately.
- **Q4:** pseudo_N table = 30 / 15 / 10 (per validated_external / validated_internal / elicited_expert).

## 2. Patch summary

### `src/engine_run.py` (additive within `event_version=1`)

- Added `ReasonCode.PRIOR_UNVALIDATED` enum value (Sprint 2 carve-out: additive typed enum value precedent already set by `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` / `METRIC_INCOHERENT_FOR_CADENCE`).
- Added new `AbstainMode` enum with `SOFT_AWAITING_MEASUREMENT` + `SOFT_PRIOR_UNVALIDATED` values.
- Added `Abstain.mode: Optional[AbstainMode] = None` field. Default `None` -> serialization shape unchanged at flag-OFF.
- `_from_dict_abstain` round-trips the new field.

### `src/utils.py`

- Added `ENGINE_V2_PRIORS_VALIDATION` flag in `get_config()` defaulting to `false`. Read from env var `ENGINE_V2_PRIORS_VALIDATION`. Whitelisted in the `os_overrides` boolean coercion set.

### `src/sizing.py`

- Added `PSEUDO_N_BY_STATUS` module-level constant: `{VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}`. Closed table; `heuristic_unvalidated` / `placeholder` are deliberately absent (they trigger refusal, not weight).
- Added `_BLEND_PERMITTED_STATUSES = frozenset(PSEUDO_N_BY_STATUS.keys())` for the refusal predicate.
- Added `bayesian_blend(prior_value, pseudo_n, store_value, n_observed) -> float` pure helper. Formula `(pseudo_n * prior_value + n_observed * store_value) / (pseudo_n + n_observed)`. Falls back to arithmetic mean on degenerate-zero denom rather than raising. Numerically pinned by tests.
- Extended `SizingInputs` with `priors_validation_enabled: bool = False`. Default False preserves M0 + Beauty + supplements byte-identity.
- Extended `size_play` targeting branch: when `priors_validation_enabled=True` and the resolved prior's `validation_status` is not in `_BLEND_PERMITTED_STATUSES`, return a suppressed `RevenueRange` with `suppression_reason="prior_unvalidated"`. The base_rate driver records the `validation_status` for audit. The legacy `source_class != causal` rule continues to fire when the flag is OFF (and acts as an orthogonal second gate when the flag is ON — both must pass for a range to surface).
- `__all__` extended with `bayesian_blend` and `PSEUDO_N_BY_STATUS`.

### `src/main.py`

- The V2-sizing call site at the M6 adapter plumbs `priors_validation_enabled=bool(cfg["ENGINE_V2_PRIORS_VALIDATION"])` into every `SizingInputs(...)`. No other code at the call site changes.

### `src/priors_loader.py::resolve_mixed_prior` (KI-19 conservative-min)

- The blended mixed PriorEntry now carries the LESS validated of the two per-vertical sides' `validation_status`. Rank table:
  ```
  PLACEHOLDER             = 0
  HEURISTIC_UNVALIDATED   = 1
  ELICITED_EXPERT         = 2
  VALIDATED_INTERNAL      = 3
  VALIDATED_EXTERNAL      = 4
  ```
  The lower-rank side wins. Examples:
  - validated_external (beauty) + heuristic_unvalidated (supplements) -> blended status = heuristic_unvalidated. The blended prior is refused at the sizing seam under the flag.
  - validated_external + validated_internal -> blended status = validated_internal.
  - validated_external + validated_external -> blended status = validated_external.
- The blended entry also explicitly sets `source_artifact=None` and `effective_n=None` because the blend is loader-derived, not author-attested.

### `src/decide.py`

- Imported `AbstainMode` from engine_run.
- Added `_route_prior_unvalidated_holds(recommendations, *, flag_on)` helper: splits incoming recs into (kept, refused) by inspecting `revenue_range.drivers` for a `prior_unvalidated` reason. Flag-off path: identity (no rerouting), preserving M0 byte-identity.
- Added `_compute_abstain_mode(state, considered, *, flag_on)` helper. Returns:
  - `None` if flag_on=False (M0 byte-identity).
  - `None` if state != ABSTAIN_SOFT.
  - `SOFT_PRIOR_UNVALIDATED` if any considered entry has `reason_code=PRIOR_UNVALIDATED`.
  - `SOFT_AWAITING_MEASUREMENT` otherwise (validated priors exist; just no store-specific evidence).
- `decide()` reads `cfg["ENGINE_V2_PRIORS_VALIDATION"]` and threads `flag_on` into the helper. The refused rejections are merged into `considered_in` before `assemble_considered(...)` in all three branches (ABSTAIN_HARD / ABSTAIN_SOFT / PUBLISH).
- All three `Abstain(...)` constructions now pass `mode=_compute_abstain_mode(...)`. Flag-off branches still emit `mode=None`, so M0 / Beauty pinned slate / supplements G-1 fixture remain byte-identical.

### `tests/test_s7_5_t3_blend_refusal.py` (NEW)

24 hermetic tests covering:

- `PSEUDO_N_BY_STATUS` table values (founder Q4 30/15/10 pin) + closed-table invariant (heuristic / placeholder absent).
- `bayesian_blend` numerics: prior-dominated (n_observed=0), store-dominated (large n_observed), equal-weight pinpoint (30+30 → 0.14 on 0.08/0.20 inputs), degenerate-zero fallback.
- `size_play` flag-OFF: heuristic_unvalidated prior + non-causal source_class still suppresses via the legacy `targeting_non_causal_prior` reason (T2-close behavior preserved).
- `size_play` flag-ON: heuristic_unvalidated -> `prior_unvalidated` suppression.
- `size_play` flag-ON: placeholder -> `prior_unvalidated` suppression.
- `size_play` flag-ON: validated_external prior + `allow_targeting_unsuppressed=True` -> NOT suppressed under the T3 rule.
- `resolve_mixed_prior` KI-19: validated_external + heuristic_unvalidated -> blended carries heuristic_unvalidated.
- `resolve_mixed_prior` KI-19: validated_external + validated_internal -> blended carries validated_internal.
- `resolve_mixed_prior` KI-19 + sizing handoff: blended heuristic prior is NOT in `PSEUDO_N_BY_STATUS` (refused at sizing seam).
- `_route_prior_unvalidated_holds` flag-OFF: identity (no rerouting).
- `_route_prior_unvalidated_holds` flag-ON: refused cards split to RejectedPlay with PRIOR_UNVALIDATED.
- `_route_prior_unvalidated_holds` flag-ON: validated cards pass through.
- `_compute_abstain_mode` flag-OFF: always None.
- `_compute_abstain_mode` flag-ON + PUBLISH: None.
- `_compute_abstain_mode` flag-ON + ABSTAIN_SOFT + no PRIOR_UNVALIDATED considered -> SOFT_AWAITING_MEASUREMENT.
- `_compute_abstain_mode` flag-ON + ABSTAIN_SOFT + PRIOR_UNVALIDATED in considered -> SOFT_PRIOR_UNVALIDATED.
- `decide()` end-to-end flag-ON: refused card routed to considered with PRIOR_UNVALIDATED, absent from recommendations.
- `decide()` end-to-end flag-ON: SOFT_PRIOR_UNVALIDATED abstain mode emitted when the only candidate was refused.
- `decide()` end-to-end flag-OFF: `Abstain.mode is None` (M0 byte-identity contract).
- `SizingInputs.priors_validation_enabled` defaults False (defensive byte-identity contract).

## 3. Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s7_5_t3_blend_refusal.py` (NEW) | 24/24 green |
| `tests/test_slate_regression_beauty_brand.py` | green (Beauty pinned slate byte-identical) |
| `tests/test_slate_regression_supplements_brand.py` | green (supplements G-1 sha256 unchanged) |
| `tests/test_golden_diff.py` | green (M0 byte-identical across small_sm / mid_shopify / micro_coldstart) |
| `tests/test_sizing.py` | green |
| `tests/test_priors_loader.py` | green |
| `tests/test_decide.py` | green |
| `tests/test_priors_yaml.py` | green |
| `tests/test_s7_5_t1_priors_validation_fields.py` | green |
| `tests/test_s7_5_t1_5_priors_audit.py` | green |
| `tests/test_s7_5_t2_external_priors.py` | green |
| `tests/test_g3_supplements_priors.py` | green |
| Full suite | 1237 passed, 14 skipped, 1 failed in ~ 800 s (was 1213/14/1 at T2 close; delta = +24 new T3 tests). The 1 failure is the same pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift, unrelated. |

## 4. Behavior changes

**NONE at default flag.** The new behavior is gated behind `ENGINE_V2_PRIORS_VALIDATION` and the default in `src/utils.py::get_config()` is `false`.

- M0 goldens byte-identical (3/3 fixtures unchanged).
- Beauty pinned slate byte-identical.
- Supplements G-1 pinned sha256 unchanged.
- `engine_run.json` shape unchanged at flag-OFF (`Abstain.mode` defaults to `None`; asdict serializes `"mode": null` but engine_run.json is only written under the V2 flag stack, which is itself not part of the M0 golden tree — the V2-rendered Beauty / supplements pinned fixtures compare HTML bytes, not JSON, and the renderer never reads `Abstain.mode`).

When an operator sets `ENGINE_V2_PRIORS_VALIDATION=true` for ad-hoc testing:
- Tier-C plays whose base_rate prior is heuristic_unvalidated / placeholder get their revenue_range suppressed with `prior_unvalidated`.
- `decide()` routes them to `considered` with `reason_code=PRIOR_UNVALIDATED`.
- When the run goes ABSTAIN_SOFT under the rule, `Abstain.mode=SOFT_PRIOR_UNVALIDATED`.

## 5. Numerical sanity-check (pseudo_N = 30)

Pinned by the T3 test suite:

```
bayesian_blend(prior_value=0.08, pseudo_n=30, store_value=0.20, n_observed=0)    = 0.08   (prior-dominated)
bayesian_blend(prior_value=0.08, pseudo_n=30, store_value=0.20, n_observed=30)   = 0.14   (equal weight)
bayesian_blend(prior_value=0.08, pseudo_n=30, store_value=0.20, n_observed=10000) ≈ 0.20  (store-dominated)
```

The 0.14 mid-point is inside the [0.04, 0.15] p10/p90 of the winback Klaviyo validated_external prior — no posterior-outside-prior-range pathology.

The bsandco entry carries `effective_n=156110` in YAML; per Part III-1 the pseudo_N stays at the 30 default for `validated_external` regardless of disclosed N. effective_n is metadata for traceability only (no sizing.py call site reads it today — the Bayesian blend math is consumed by Sprint 6 Tier-B builders).

## 6. KI-19 conservative-min test sanity-check

The test fixture pins three configurations and the rank table:

| Beauty side | Supplements side | Blended status |
|---|---|---|
| validated_external | heuristic_unvalidated | heuristic_unvalidated |
| validated_external | validated_internal | validated_internal |
| validated_external | validated_external | validated_external (rank tie -> beauty side; either is fine) |

Silent-upgrade defense: a validated_external beauty side can NEVER promote a heuristic supplements side. The blended mixed prior fails the refusal predicate at the sizing seam, just like the heuristic supplements per-vertical entry would.

## 7. Schema status

`event_version=1` frozen contract intact. Additions:

- `ReasonCode.PRIOR_UNVALIDATED` (additive enum value; Sprint 2 carve-out).
- `AbstainMode` enum (NEW; values `SOFT_AWAITING_MEASUREMENT`, `SOFT_PRIOR_UNVALIDATED`).
- `Abstain.mode: Optional[AbstainMode] = None` (additive dataclass field; default `None`; round-trips via `_from_dict_abstain`).

All three additions are within the Sprint 2 freeze's "additive typed enum / typed slot" carve-out.

## 8. Artifacts added

- `tests/test_s7_5_t3_blend_refusal.py` (24 tests, NEW)
- `agent_outputs/code-refactor-engineer-s7_5-t3-summary.md` (this file)

No new YAML / config / fixture files. The 3 T2-promoted `config/priors_sources/` memos continue to back the 3 validated_external entries that T3.5 will let through.

## 9. Remaining risks / follow-ups

1. **`Abstain.mode` field present in serialized engine_run.json at flag-OFF.** asdict writes `"mode": null` into the dataclass dict. Today no test compares engine_run.json byte-identically (M0 goldens are HTML + receipts; Beauty/supplements pinned fixtures are HTML), so this is invisible. If a future test pins engine_run.json bytes at flag-OFF, the new key would surface as a diff. Mitigation deferred — additive `null` keys are within the additive-enum-value carve-out and downstream Swarm consumers tolerant.
2. **`bayesian_blend` is currently unused at runtime.** Lands as the contract surface for Sprint 6 Tier-B builders. Tests pin the numerics + table values so it does NOT drift before consumers arrive. Listed under Risk R3 in the IM plan (intentional forward scaffolding; documented in `__all__`).
3. **The legacy `source_class != causal` rule is preserved as a second gate when the flag is ON.** A validated_external prior with non-causal source_class (e.g., the T2 winback / bestseller / first_to_second promotions) still gets suppressed by the legacy rule unless the call site sets `allow_targeting_unsuppressed=True`. This is intentional for T3 (T3 is the refusal contract; T3.5 may need to revisit whether the legacy rule applies after the flag is ON — current T2 priors are observational, NOT causal, so they would remain suppressed merchant-facing). Founder review of the T3.5 diff will surface whether the legacy rule should be relaxed under flag-on; if so, that is a T3.5 follow-up edit, not a T3 edit.
4. **`Abstain.mode` is not yet rendered.** The merchant briefing does not surface the typed mode; it remains a structured slot for downstream agents (calibration, Klaviyo, future renderers).

## 10. Follow-up work / dependencies

- **S7.5-T3.5** (flag flip ON + atomic fixture re-pin) is next. With T3.5 the default flips to ON, the 3 T2-promoted validated_external priors survive the rule, and the 5 fixtures (Beauty + supplements + 3 M0 goldens) get re-pinned in ONE atomic commit per Sprint 2 Risk #4 discipline. The summary doc for T3.5 will include the per-fixture card-count delta + a verbatim engine_run.json diff for at least one suppressed PlayCard.
- **Sprint 6** (Tier-B builders) will consume `PSEUDO_N_BY_STATUS` + `bayesian_blend` as imports from `src.sizing`. T3's contract surface is stable.

## 11. Hard constraints respected

- `engine_run.json` schema additive only (`event_version=1` intact).
- D-5: no Shopify / Klaviyo network calls.
- D-6: no banned ML modules. The `bayesian_blend` helper is an arithmetic posterior, not an ML model.
- D-8: vertical scope unchanged (`{beauty, supplements, mixed}`).
- M0 Beauty / supplements / 3 M0 goldens byte-identical at flag-OFF.
- B-5 Berkson invariant intact.
- S-2 / S-3 / S-4 / S-5 / S-6 substrate write paths untouched.
- B4 role-uniqueness invariant intact (`_assert_role_uniqueness` still runs on every decide() branch).
- Sprint 2 schema freeze intact (additive enum + optional dataclass field).
- No new runtime dependencies.

## Backfill from memory.md (migration trim 2026-05-25)

## S7.5-T3 — Cold-start blend refusal + SOFT_PRIOR_UNVALIDATED abstain (default-OFF flag) (2026-05-17)

**Shipped:**
- New cfg flag `ENGINE_V2_PRIORS_VALIDATION` in `src/utils.py::get_config()` defaulting to `false`. Env-override via `ENGINE_V2_PRIORS_VALIDATION=true`. Flag flip to default-ON is T3.5's atomic re-pin ticket.
- `src/sizing.py`: added `PSEUDO_N_BY_STATUS = {VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}` module constant (founder Q4 locked). Heuristic / placeholder deliberately absent — they trigger refusal, not weight. Added pure `bayesian_blend(prior_value, pseudo_n, store_value, n_observed)` helper. Extended `SizingInputs` with `priors_validation_enabled: bool = False`. Extended `size_play` targeting branch: when flag-on and prior's `validation_status` not in the blend-permitted set, suppress with reason `prior_unvalidated`. The legacy `source_class != causal` rule continues to fire as an orthogonal second gate when the flag is ON (both must pass). `bayesian_blend` is contract surface for Sprint 6 Tier-B builders — no runtime caller in T3.
- `src/main.py`: V2 sizing adapter threads `priors_validation_enabled=bool(cfg["ENGINE_V2_PRIORS_VALIDATION"])` into `SizingInputs(...)`. No other M6 adapter change.
- `src/priors_loader.py::resolve_mixed_prior`: KI-19 conservative-min rule. Blended mixed PriorEntry inherits the LESS validated of the two per-vertical sides (rank table: PLACEHOLDER=0 < HEURISTIC_UNVALIDATED=1 < ELICITED_EXPERT=2 < VALIDATED_INTERNAL=3 < VALIDATED_EXTERNAL=4). Silent-upgrade through mixing is structurally impossible; the blended prior fails the sizing-seam refusal predicate.
- `src/engine_run.py`: additive `ReasonCode.PRIOR_UNVALIDATED` enum value (Sprint 2 carve-out, same precedent as `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW`). NEW `AbstainMode` enum with `SOFT_AWAITING_MEASUREMENT` + `SOFT_PRIOR_UNVALIDATED` values. NEW optional `Abstain.mode: Optional[AbstainMode] = None` field. `_from_dict_abstain` round-trips the new field.
- `src/decide.py`: added `_route_prior_unvalidated_holds(recs, *, flag_on)` helper that splits incoming recs by inspecting `revenue_range.drivers` for a `prior_unvalidated` reason; flag-off path is identity (no rerouting; preserves M0 byte-identity). Added `_compute_abstain_mode(state, considered, *, flag_on)` helper: flag-off -> None; PUBLISH -> None; ABSTAIN_SOFT + PRIOR_UNVALIDATED considered -> SOFT_PRIOR_UNVALIDATED; ABSTAIN_SOFT otherwise -> SOFT_AWAITING_MEASUREMENT. `decide()` reads `cfg["ENGINE_V2_PRIORS_VALIDATION"]`, splits incoming recs through the helper before ranking, and threads the typed mode into every `Abstain(...)` construction across all three branches.

**Load-bearing invariants:**
- `tests/test_s7_5_t3_blend_refusal.py` pins (a) pseudo_N table values (30/15/10) + closed-table invariant, (b) `bayesian_blend` numerics (prior-dominated, store-dominated, equal-weight 0.14, degenerate-zero fallback), (c) `size_play` flag-OFF preserves T2-close behavior (legacy `targeting_non_causal_prior` reason wins), (d) `size_play` flag-ON refuses heuristic_unvalidated + placeholder with `prior_unvalidated`, (e) `size_play` flag-ON permits validated_external, (f) KI-19 conservative-min on `resolve_mixed_prior` (3 configurations), (g) `_route_prior_unvalidated_holds` + `_compute_abstain_mode` unit behavior, (h) `decide()` end-to-end routing of PRIOR_UNVALIDATED + emission of SOFT_PRIOR_UNVALIDATED, (i) `SizingInputs.priors_validation_enabled` defaults False.
- 24 new tests; ZERO test removed.

**Caveats / dormant behavior:**
- Default OFF in T3 (`ENGINE_V2_PRIORS_VALIDATION=false`). M0 / Beauty pinned slate / supplements G-1 all byte-identical at default flag.
- `bayesian_blend` is forward-looking scaffolding for Sprint 6 Tier-B builders; no runtime caller in T3. Tests pin numerics so it can't drift before consumers arrive.
- `Abstain.mode` is a typed slot for downstream agents (Klaviyo / calibration). The merchant briefing renderer does NOT surface the typed mode; HTML byte-identity preserved.
- When flag is ON, the legacy `source_class != causal` rule still applies as an orthogonal second gate. The 3 T2-promoted validated_external priors are observational (NOT causal), so they would remain suppressed merchant-facing under the legacy rule — T3.5 founder review may decide whether to relax the legacy rule under flag-on.

**Schema:** additive within `event_version=1` freeze. `ReasonCode.PRIOR_UNVALIDATED` (additive enum value); `AbstainMode` enum (new); `Abstain.mode: Optional[AbstainMode] = None` (additive optional dataclass field).

**Suite:** 1237 passed, 14 skipped, 1 failed (was 1213/14/1 at T2 close; +24 new T3 tests; the 1 fail is the same pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift, unrelated).
**Fixtures:** Beauty pinned slate sha256 unchanged at `45edaca58c47...`; supplements G-1 sha256 unchanged at `01f5feff84...`; M0 goldens byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s7_5-t3-summary.md](agent_outputs/code-refactor-engineer-s7_5-t3-summary.md)

---
