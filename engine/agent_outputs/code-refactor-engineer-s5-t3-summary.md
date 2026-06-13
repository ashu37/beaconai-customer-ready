# S5-T3 — KI-22 supplements repeat-rate metric incoherence typed flag

**Owner:** code-refactor-engineer (Sprint 5, ticket S5-T3)
**Date:** 2026-05-16
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §11, ticket S5-T3 (lines 602-608)
**Predecessor:** S5-T2 ([code-refactor-engineer-s5-t2-summary.md](./code-refactor-engineer-s5-t2-summary.md))
**Status:** Complete. Schema unchanged (`event_version=1` frozen; additive enum value on `data_quality_flags` is the Sprint 2 carve-out).

---

## 1. Approved scope

Resolves KI-22. Supplements engine runs log
`⚠️ Metric warnings: Repeat rate 0% suspiciously low for 972 orders`
to stdout via `src.validation.MetricConsistencyCheck`, but the
advisory never reached `engine_run.json::data_quality_flags`. The
within-window `repeat_rate_within_window` metric is structurally
incoherent on supplements because typical reorder cadences (28–45 days)
exceed the L28 primary window; the merchant sees a near-zero number on
a Watching row that does not reflect actual repeat behavior.

Per plan §11 lines 602-608:

- Add additive typed enum value `METRIC_INCOHERENT_FOR_CADENCE` on
  `data_quality_flags` (additive enum values are the explicit Sprint 2
  freeze carve-out).
- Propagate the existing stdout advisory into the typed flag list when
  supplement reorder cadence exceeds the active L28 window.
- Founder call inside the ticket: suppress OR relabel the misleading
  `repeat_rate_within_window` on the Watching row — either is
  contract-safe; pin whichever is chosen.
- Threshold heuristic: median customer-level reorder gap > 0.8 × active
  window length; pin in the test, not as a scattered magic constant.

**Founder choice exercised:** suppress (not relabel) the Watching row
when the flag fires. Both branches were contract-safe; suppression is
the strictly-honest choice on a metric that the engine has just
declared incoherent.

## 2. Patch summary

### `src/engine_run.py`

Added enum member `DataQualityFlag.METRIC_INCOHERENT_FOR_CADENCE =
"metric_incoherent_for_cadence"`. Additive within `event_version=1`;
the lowercase-string value convention matches every other
`DataQualityFlag` member. Docstring explicitly notes the flag is
ADVISORY and intentionally absent from `src/decide.py::_HARD_DQ_FLAGS`.

### `src/cadence_coherence.py` (NEW, isolated module)

Three pure helpers, no engine dependencies, no runtime deps beyond
pandas:

- `compute_median_customer_reorder_gap_days(orders_df) -> Optional[float]`
  — groups orders by `customer_id`, takes consecutive-order diffs in
  days, returns the median across customers. Returns `None` on empty /
  malformed / no-repeat-customers inputs.
- `cadence_exceeds_window(median_gap_days, window_days,
  threshold_ratio=DEFAULT_THRESHOLD_RATIO) -> bool` — strict-greater-than
  comparison; fail-closed on missing inputs.
- `evaluate(orders_df, window_days=28, threshold_ratio=...) ->
  (bool, Optional[float])` — convenience wrapper.

`DEFAULT_THRESHOLD_RATIO = 0.8` is the SINGLE source of truth for the
heuristic. Re-tunes must update it in one place; the test imports the
constant rather than re-deriving the magic number.

### `src/main.py`

New ~30-line block AFTER `_v2_decide(...)` and BEFORE the S-4 immutable
snapshot write. Gated to `vertical == "supplements"`. Order matters:

1. Compute `window_days` from `aligned_for_template["L28"]["window_days"]`
   (defaults to 28).
2. Call `cadence_coherence.evaluate(df, window_days)`.
3. If fires: append `DataQualityFlag.METRIC_INCOHERENT_FOR_CADENCE` to
   `engine_run.data_quality_flags` (idempotent — guarded by `not in`).
4. Filter `engine_run.watching` to drop the
   `repeat_rate_within_window` row.

The block lives AFTER `decide()` so it cannot trip the pre-decide
`_has_dq` gating at `main.py:1171` that would skip the directional
rebuild on a populated flag list. Because the flag is intentionally
absent from `decide._HARD_DQ_FLAGS`, post-decide insertion does NOT
change the decision_state (supplements stays `abstain_soft`).

Defensive `try`/`except` wraps the whole block; failure prints a
warning and engine continues with the pre-S5-T3 shape (same additive
contract as S5-T2).

### Fixture re-pin

`tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html`
sha256:

| | Pre-S5-T3 (S5-T2 close) | Post-S5-T3 |
|---|---|---|
| sha256 | `a7def447872b7780cb09ce54ad7c8a64f1891c71ee3ed3cf66447b76cb32415b` | `01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95` |

Behavioral delta on the briefing.html: (1) the supplements Watching
section no longer renders the `repeat_rate_within_window` row; (2) the
data-quality footer reflects the new typed flag presence.

## 3. Files changed

| File | Change |
|---|---|
| `src/engine_run.py` | New `DataQualityFlag.METRIC_INCOHERENT_FOR_CADENCE` enum member + advisory-not-hard docstring |
| `src/cadence_coherence.py` | NEW — pure helper module (median customer reorder gap + threshold check) |
| `src/main.py` | New ~30-line post-decide supplements-gated block (flag append + Watching row suppression) |
| `tests/test_s5_t3_cadence_coherence.py` | NEW — 16 tests (threshold pin + helper semantics + enum advisory contract + end-to-end supplements/Beauty assertions) |
| `tests/test_engine_run_schema.py` | `test_all_data_quality_flags_declared` expected set gains the new value |
| `tests/test_slate_regression_supplements_brand.py` | `PINNED_SHA256` re-pin; `EXPECTED_WATCHING_METRICS` drops `repeat_rate_within_window`; renamed `test_no_data_quality_flags_today` → `test_data_quality_flags_carry_cadence_advisory` |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | Re-generated under post-S5-T3 engine |
| `KNOWN_ISSUES.md` | KI-22 `open` → `resolved`; open-count 12 → 11 |
| `memory.md` | Sprint 5 section gains S5-T3 entry (template-shape, ≤15 lines) |
| `agent_outputs/code-refactor-engineer-s5-t3-summary.md` | NEW — this file |

## 4. Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s5_t3_cadence_coherence.py` | 16/16 green |
| `tests/test_engine_run_schema.py` | green |
| `tests/test_slate_regression_supplements_brand.py` | 12/12 green (sha256 `01f5feff84...` matches re-pinned fixture) |
| `tests/test_slate_regression_beauty_brand.py` | 19/19 green (Beauty pinned slate sha256 unchanged) |
| `tests/test_golden_diff.py` | 3/3 green (M0 Beauty / small_sm / mid_shopify / micro_coldstart byte-identical) |
| `tests/test_s5_t2_supplement_cadence_abstain.py` | green (S5-T2 contract intact) |
| `tests/test_s5_t1_*.py` | green (S5-T1 contract intact) |
| Full suite (`pytest -q`) | **1190 passed, 14 skipped, 1 failed** in 828s (was 1175/14/1 at S5-T2). The 1 failure (`test_inventory_updated_at_is_fresh`) is the pre-existing wall-clock drift in the inventory CSV fixture, unrelated to this ticket. Delta = +15 net new tests (16 new in `test_s5_t3_cadence_coherence.py`; net +15 after the one supplements regression assertion was renamed-and-rescoped rather than added). |

## 5. Behavior changes

- Supplements run's `engine_run.data_quality_flags` now carries
  `metric_incoherent_for_cadence` as an advisory typed flag. Previously
  the advisory only appeared as stdout text from the validation layer.
- Supplements Watching section no longer renders the
  `repeat_rate_within_window` row when the flag fires (founder choice:
  suppress over relabel).
- Supplements decision_state stays `abstain_soft` — the new flag is
  intentionally absent from `decide._HARD_DQ_FLAGS`, so it does NOT
  push the run to `abstain_hard`.
- Beauty / `mixed` paths: zero change. Beauty pinned slate sha256
  unchanged; M0 goldens byte-identical.
- `event_version=1` payloads: additive only (new enum value); Swarm
  consumers that pattern-match on the existing 6 flag values are
  unaffected.

## 6. Artifacts added

- `src/cadence_coherence.py` (pure helper module)
- `tests/test_s5_t3_cadence_coherence.py` (KI-22 acceptance)
- `agent_outputs/code-refactor-engineer-s5-t3-summary.md` (this file)

## 7. Remaining risks

1. **Threshold heuristic is a single magic number (0.8).** Pinned in
   one place (`cadence_coherence.DEFAULT_THRESHOLD_RATIO`) and in one
   test (`test_default_threshold_ratio_pinned`), so re-tunes are
   explicit. If a future supplements fixture lands with cadence right
   at the boundary, the test will surface that the heuristic needs
   re-tuning.
2. **The helper consumes the raw `df` (post-`preprocess`) at
   `src/main.py`.** Column-name drift in the orders CSV pipeline (e.g.
   `Created at` → `created_at`) would make the helper return `None` and
   silently fail to flag. The helper fails-closed (returns
   `None`/`False`), which preserves the additive contract but would
   leave KI-22 silently re-opened.
3. **Watching row suppression is decided at engine emit, not renderer.**
   A future v2 of the briefing pipeline that re-derives Watching from
   `state_of_store` independently of `engine_run.watching` would
   re-introduce the misleading row. The pinned fixture sha256 is the
   regression test.
4. **Pre-existing inventory-freshness test** (`test_inventory_updated_at_is_fresh`)
   still fails on the runner clock. Not in S5-T3 scope; tracked
   separately.

## 8. Follow-up work / dependencies

- **S5-T4** (KI-25 legacy audience-builder per-vertical floor wire-up)
  takes the next fixture-re-pin slot per plan §11. Coordinate with the
  current sha256 (`01f5feff84...`).
- **Path (a) directional-builder window-widening** for supplements
  (Sprint 6+ with ecommerce-ds-architect review) — not impacted by
  this ticket; the typed abstain from S5-T2 plus the cadence-coherence
  flag from S5-T3 together describe the honest supplements posture
  while the architecture decision is pending.
- **Inventory CSV fixture refresh** remains a separate ticket.

## 9. Branch shape

Three commits on `post-6b-restructured-roadmap` (not pushed),
following the per-commit ritual:

1. `269f03e` — `S5-T3: KI-22 supplements repeat-rate metric incoherence typed flag` (impl + new helper + 16 new tests + supplements re-pin + KI-22 flip)
2. `c6e3d31` — `Document S5-T3 in repo memory.md`
3. _this commit_ — `S5-T3 summary` (this file)

## 10. Hard constraints respected

- `engine_run.json` schema **unchanged** in shape — new
  `DataQualityFlag.METRIC_INCOHERENT_FOR_CADENCE` is additive within
  the Sprint 2 `event_version=1` freeze (additive enum values on
  `data_quality_flags` are the documented carve-out per plan §11).
- `event_version=1` payloads **frozen** — no payload field shape
  changes.
- D-6 enforced — no banned ML modules touched.
- D-8 enforced — vertical scope unchanged (`{beauty, supplements,
  mixed}`); the new emit is `supplements`-gated, not a backdoor for
  unsupported verticals.
- M0 Beauty pinned fixture sha256 **unchanged**.
- Beauty pinned slate sha256 **unchanged** at `45edaca5...`.
- Supplements G-1 fixture re-pinned `a7def44787...` → `01f5feff84...`
  (deliberate; documented in commit + KNOWN_ISSUES + this summary).
- B-5 Berkson invariant intact — directional builder cohort logic
  untouched (this ticket is post-decide only).
- The new advisory flag is intentionally absent from
  `decide._HARD_DQ_FLAGS` — supplements stays `abstain_soft`.
- S-2 / S-3 / S-4 / S-5 / S-6 substrate write paths **untouched**.
- `config/priors.yaml` (G-3 surface) **untouched**.
- No new runtime dependencies.

## Backfill from memory.md (migration trim 2026-05-25)

## S5-T3 — KI-22 supplements repeat-rate metric incoherence typed flag (2026-05-16)

**Shipped:**
- New additive typed `DataQualityFlag.METRIC_INCOHERENT_FOR_CADENCE` (Sprint 2 freeze carve-out for additive enum values on `data_quality_flags`).
- New pure helper `src/cadence_coherence.py` (median customer reorder gap > `DEFAULT_THRESHOLD_RATIO=0.8` × window_days); `src/main.py` post-decide block on supplements vertical only propagates the existing stdout advisory into `data_quality_flags` AND suppresses the misleading `repeat_rate_within_window` Watching row.

**Load-bearing invariants:**
- `METRIC_INCOHERENT_FOR_CADENCE` is ADVISORY — intentionally absent from `src/decide.py::_HARD_DQ_FLAGS`. Adding it to that frozenset would silently push the supplements run to ABSTAIN_HARD; `test_new_flag_is_advisory_not_hard` pins this.
- Heuristic threshold lives in `cadence_coherence.DEFAULT_THRESHOLD_RATIO = 0.8` as the single source of truth — pinned by `test_default_threshold_ratio_pinned`. Future re-tunes must update the constant in one place.
- Emit gated on `vertical == "supplements"`. Beauty / `mixed` paths untouched; Beauty pinned slate sha256 unchanged and M0 goldens byte-identical (`test_beauty_engine_run_does_not_emit_cadence_flag`).

**Caveats / dormant behavior:** Founder call inside the ticket — suppress (not relabel) the Watching row. If a future ticket prefers relabel, both are contract-safe; the test asserts the suppress branch.

**Schema:** unchanged (additive enum value within `event_version=1` frozen contract).
**Suite:** 1190 passed, 14 skipped, 1 failed (the 1 fail is the pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift; unrelated to S5-T3).
**Summary:** [agent_outputs/code-refactor-engineer-s5-t3-summary.md](agent_outputs/code-refactor-engineer-s5-t3-summary.md)

# Sprint 7.5 — Priors Validation (2026-05-17 onward)

Anchor goal per [implementation-manager-s7_5-priors-validation-plan.md](agent_outputs/implementation-manager-s7_5-priors-validation-plan.md): replace the unsafe `source_class → pseudo_N` blend weight with a per-prior `validation_status` field so `heuristic_unvalidated` causes sizing to refuse blending and the engine to emit a typed `SOFT_PRIOR_UNVALIDATED` abstain. S7.5 is beta-blocking (Phase 6A Final Review caveat 4) and gates Sprint 6 (Tier-B builders). 5 logical tickets (T1, T1.5, T2, T3, T3.5); only T3.5 changes engine output.
