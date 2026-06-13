# G-4 — Reclassify subscription_nudge + routine_builder permanently as targeting

**Owner:** code-refactor-engineer
**Date:** 2026-05-11
**Sprint:** Sprint 4 (Engineer B track)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §4, ticket G-4
**Memory:** [memory.md](../memory.md) G-4 entry
**Status:** Complete; full suite green; Beauty + supplements pinned fixtures byte-identical.

---

## Scope delivered

`_TARGETING_RECLASSIFY` for `subscription_nudge` and `routine_builder` is now the **structural** default in `src/action_engine.py::_compute_candidates`, not a flag-gated path. The historical inline placeholders (`effect_abs=0.05`, `effect_abs=0.08`, `effect_floor=0.05`, fabricated Welch-t and two-proportion-z p-values) are removed entirely.

Both plays now emit:
- `evidence_class="targeting"` stamped directly on the candidate dict at the `cands.append({...})` site — not via the `EVIDENCE_CLASS_ENFORCED` flag path.
- `effect_abs`, `p`, `effect_floor` as `float("nan")`.
- `baseline_rate` as `None`.
- No Phase-2 placeholder constants.

`engine_run_adapter._build_measurement_from_legacy` already short-circuits to `None` when `evidence_class == "targeting"`, so the rendered `engine_run.json` ships `measurement=None` on these plays structurally.

The `_TARGETING_RECLASSIFY` frozenset (`src/evidence.TARGETING_RECLASSIFY_PLAYS`) is intentionally **not** pruned. Both play_ids remain in the set as defensive coverage for the flag-on path (which is the M0-golden test harness and the slate test harness). G-4 closes the gap at the emit site so the contract holds with the flag OFF too.

## Files changed

| File | Change |
|---|---|
| [src/action_engine.py](../src/action_engine.py) | `_compute_candidates` blocks for `subscription_nudge` (lines ~3483) and `routine_builder` (lines ~3580): drop hardcoded constants, stamp `evidence_class="targeting"`, NaN-out fabricated stat fields. Drop the unused `rb_ids` setup line that fed the removed Welch-t path. Comments document the G-4 contract at both sites. |
| [tests/test_g4_targeting_reclassify.py](../tests/test_g4_targeting_reclassify.py) | NEW — 8 tests |
| [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) | KI-24 G-4 progress note added; "last updated" footer rolled forward |
| [memory.md](../memory.md) | G-4 entry appended (≤15 lines per template) |

## Tests added

| # | Test | Pins |
|---|---|---|
| 1–2 | `test_play_always_emits_evidence_class_targeting[subscription_nudge, routine_builder]` | (a)/(b): `evidence_class == "targeting"` on any PlayCard surface |
| 3–4 | `test_play_measurement_is_none_on_any_playcard[...]` | (c): `measurement is None` on any PlayCard surface |
| 5–6 | `test_no_phase2_effect_constants_in_emit_block[...]` | (d): no `"effect_abs": 0.05`, `"effect_abs": 0.08`, `"effect_floor": 0.05/0.08`, or `effect_rb = 0.08` literal remains in the per-play emit block of `src/action_engine.py` |
| 7–8 | `test_underlying_candidate_carries_no_forbidden_measured_fields[...]` | No `p_value`/`confidence_score`/`revenue_range`/`ci_internal`/`score`/`final_score` field declared on the candidate dict |

The source-text scanner (`_extract_play_emit_block`) deliberately scopes by the `"play_id": "<id>"` literal in the dict — file-wide grep would false-positive on the unrelated `aov_momentum` block which legitimately carries `effect_floor: 0.05` for its own scoring path.

## Fixture re-pin discipline

Per the ticket, the Beauty pinned fixture re-pin was prepared for the same commit if a shift occurred. **No shift occurred:**

- Beauty pinned fixture sha256: `45edaca58c47797addf556b91460b81782dba6653d5d1ec82043bd40a051ea78` — unchanged from S-3 closeout. The fixture is generated under the M4b flag-on stack (`STATS_NAN_FOR_HARDCODED=true`, `EVIDENCE_CLASS_ENFORCED=true` via the synthetic harness's `extra_v2_flags=True` default), and the post-G-4 emit-site shape is byte-equivalent to what the M4b flag-on path was already producing for these two plays. Promoting from flag-gated to structural produces zero rendered-output delta on this fixture.
- Supplements G-1 fixture sha256: `feb03500c1adc4a8a8a6762c6f0c98fd2a81ba2a9d3838d75ccca0ea221a0e0d` — unchanged. Same reason; the supplements run also uses the M4b flag-on harness.
- Considered membership unchanged on both fixtures: Beauty `{winback_21_45, routine_builder, subscription_nudge, empty_bottle}`; supplements `{winback_21_45, bestseller_amplify, discount_hygiene, subscription_nudge, routine_builder, frequency_accelerator}`.
- M0 legacy goldens (small_sm, mid_shopify, micro_coldstart): byte-identical. `tests/test_golden_diff.py` runs them under the M4b flag-on stack as well.

The re-pin lane stays live for any *future* refactor that does shift these plays at the emit site (e.g., when Phase 4.2's `subscription_nudge` redesign lands and the play graduates to a real `directional` measurement).

## KI-24 update

KI-24 stays `open` (Phase 4.2 redesign work pending). G-4 progress note added inline:

> the *surface* is now correctly honest. `subscription_nudge` and `routine_builder` ship `evidence_class=targeting` with `measurement=None` STRUCTURALLY in `src/action_engine.py` (not flag-gated), and the hardcoded `effect_abs=0.05` / `effect_abs=0.08` placeholders are removed. So the merchant no longer sees a fabricated effect masquerading as measured for these plays. The underlying issue — multiplier-vs-baseline-rate conflation on the supplements `subscription_nudge` audience definition — is unchanged and remains Phase 4.2 redesign work, NOT a G-4 deliverable.

No supplements G-1 considered-membership shift, so the G-1 regression-pin note in `memory.md` doesn't need an additive update.

## Hard constraints respected

- `engine_run.json` schema unchanged (the `measurement` field going from "object present" to "null" was already supported under the M4b flag-on path; G-4 merely makes that the default).
- `event_version=1` payloads frozen (Sprint 2 schema-freeze — untouched).
- D-6 enforced: no ML scaffolding. The hardcoded effects are *removed*, not replaced with another invented number.
- D-8 enforced: vertical scope untouched.
- M0 Beauty + supplements pinned fixtures byte-identical — no re-pin needed despite the discipline being prepared.
- No S-2/S-3/S-4/S-5/S-6 substrate surfaces touched.
- No priors.yaml changes (G-3 surface, frozen).
- No new runtime dependencies.

## Test results

| Suite | Result |
|---|---|
| `tests/test_g4_targeting_reclassify.py` | 8/8 |
| `tests/test_no_hardcoded_fallbacks_in_payload.py` (B-3) | 6/6 |
| `tests/test_berkson_invariant.py` (B-5) | 5/5 |
| `tests/test_slate_regression_beauty_brand.py` | 19/19 |
| `tests/test_slate_regression_supplements_brand.py` (G-1) | 12/12 |
| **Full suite** | **1160 passed, 14 skipped, 0 failed** (~11 min 14 s) |

Was 1152p/14s/0f at G-3 closeout; +8 G-4 tests.

## Behavior changes

- With both M4b flags OFF (legacy default): `subscription_nudge` / `routine_builder` candidates now carry `evidence_class="targeting"` and NaN stat fields at the emit site, instead of `effect_abs=0.05`/`0.08` with a computed-or-fabricated `p`. The legacy decision lanes that read these candidate fields handle NaN safely (the M4b flag-on path has been exercising this shape since M4b shipped). No M0 golden shift observed.
- With both M4b flags ON (slate / fixture harnesses): no observable change — the M4b flag-on transforms (`_maybe_nan_fabricated_stats` + `_maybe_attach_evidence_class`) are now redundant for these two specific plays but harmless (NaN→NaN, "targeting"→"targeting"). The frozenset entry is retained so the flag path still covers `empty_bottle` / `category_expansion` / `bestseller_amplify` / `vip_no_discount_nurture` / `replenishment_reminder`.

## Out of scope (deliberately not touched)

- Phase 4.2 `subscription_nudge` redesign (multiplier-vs-baseline-rate conflation; survivorship bias on the ≥3-SKU audience). KI-24 stays open; this is the real Sprint 5+ work.
- Phase 4.2 `routine_builder` redesign (unit-coherent measurement design that produces a defensible directional effect, not just a p-value). `project_phase4_routine_builder_open.md` stays open.
- Pruning the `TARGETING_RECLASSIFY_PLAYS` frozenset. Deliberately retained for defensive coverage; B-5's membership-pin test forces founder-level review if either play is ever removed.
- Re-pinning Beauty / supplements fixtures (no shift occurred; the re-pin discipline lane stays live for the next refactor that does shift them).

## Remaining risks

- A future refactor that re-enables the Welch-t / two-proportion-z paths on these two plays without re-stamping `evidence_class="targeting"` would silently re-introduce the Berkson-class measurement object. The G-4 source-text test (tests 5–6) catches the *literal-constant* form of the regression; B-5 catches the *evidence-class* form on Beauty fixture. Together they pin the contract from both sides.
- The `_TARGETING_RECLASSIFY` flag path remains a no-op safety net for these two plays. If a future maintainer "cleans up" what they see as dead code in `_maybe_attach_evidence_class`, the flag-off behavior would still be safe (G-4 stamps at the emit site), but the flag-on harnesses (M0 goldens, slate fixtures) would also need to keep passing. The structural-default contract is the load-bearing one.

## Branch shape

| Commit | Subject |
|---|---|
| `0e86e44` | G-4: subscription_nudge + routine_builder permanently targeting |
| `f0c3602` | Document G-4 in repo memory.md |
| (this commit) | Add G-4 summary file |

Branch: `post-6b-restructured-roadmap` (not pushed).

## Next ticket

I-1 — affinity emitter ships at `targeting` class (Engineer B, after G-4). G-4 was an I-1 dependency; with `subscription_nudge`/`routine_builder` out of the fabricated-measurement way, I-1's `bestseller_amplify` slot is the clean lane to land a model-derived candidate at `evidence_class=targeting`.
