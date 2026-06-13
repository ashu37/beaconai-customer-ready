# Milestone 7 Summary — V2 Decision Selector

_Completed: 2026-05-03 (engine-rework branch)_

## Approved scope

Milestone 7 of `agent_outputs/implementation-manager-overhaul-plan-final.md`:
build the first V2 decision layer that composes the M1–M6 pieces into a
typed `EngineRun` via `decide(engine_run, *, cfg) -> EngineRun`.
Tickets T7.1, T7.2, T7.3, T7.4, T7.5, T7.6, T7.7, T7.8, T7.9.

- T7.1 — `decide()` skeleton; pure function on EngineRun in / EngineRun
  out. No mutation.
- T7.2 — Class-aware ranking (`measured > directional > targeting`,
  then by `revenue_range.p50` desc, then audience size, then play_id).
- T7.3 — Top-3 cap; excess demoted to `considered` with `CAP_EXCEEDED`.
- T7.4 — Materiality + class-aware-ranking interaction (DS Architect QA
  Change 2): zero measured/directional after gating ⇒ ABSTAIN_SOFT,
  never PUBLISH on a targeting-only briefing.
- T7.5 — RejectedPlay assembly: union of upstream guardrail rejections
  + cap-exceeded; deduplicated against recommendations; capped at 6.
- T7.6 — `would_fire_if` text builder: per-reason templates, no LLM,
  no storytelling layer.
- T7.7 — Abstain mode logic: ABSTAIN_HARD on any HARD data-quality
  flag (defensive; M5 also enforces); ABSTAIN_SOFT on no
  measured/directional; PUBLISH otherwise.
- T7.8 — `EngineRun` finalization: returns a new EngineRun via
  `dataclasses.replace`; preserves `state_of_store`, `scale`,
  `briefing_meta`, etc.
- T7.9 — Watching builder: deterministic, single-run, sourced from
  the M1 typed `state_of_store` observations. HELD-with-non-zero-
  change observations become `WatchedSignal` entries with
  template-driven `threshold_to_act` text.

**Out of scope (deferred per the M7 ticket):**

- M8 renderer flip / Play Thesis output / merchant-facing copy.
- M8's `tests/test_targeting_no_dollar_headline.py` invariant.
- M9 ML-readiness writers (`recommended_history.json`,
  `calibration_stub.load_realization_factors`).
- M10 cleanup / legacy code deletion.
- Klaviyo / Shopify production integrations.

## Files changed

### New files

- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` —
  the M7 V2 decision selector. Pure function `decide(engine_run, *,
  cfg) -> EngineRun`. Exports `MAX_RECOMMENDATIONS = 3`,
  `MAX_CONSIDERED_RENDERED = 6`, `MAX_WATCHING_SIGNALS = 4`.
  Sub-functions: `rank_recommendations`, `assemble_considered`,
  `build_watching`. Internal: `_decide_abstain_state`. Module-level
  constants: `_CLASS_PRIORITY` (measured=3, directional=2,
  targeting=1, weak=0), `_HARD_DQ_FLAGS` (mirrors
  `guardrails.HARD_DATA_QUALITY_FLAGS` defensively),
  `_WOULD_FIRE_IF_TEMPLATE` (per-reason-code text strings).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_decide.py`
  — 34 tests across 7 test classes: TestRanking (7), TestCap (3),
  TestAbstain (9), TestConsideredAssembly (4), TestWatching (7),
  TestPurity (1), TestEndToEnd (3).
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-milestone-7-summary.md` —
  this file.

### Edited files

- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`:
  - DEFAULTS: added `ENGINE_V2_DECIDE` (default false).
  - `_coerce` bool set: extended to include `ENGINE_V2_DECIDE`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`:
  - Added a V2-decide block immediately after the M6 sizing block and
    before the `engine_run.json` write. Behind `ENGINE_V2_DECIDE=true`
    only. Calls `src.decide.decide(engine_run, cfg=cfg)` to apply the
    M7 layer (ranking, cap, abstain, considered assembly, watching).
    Wrapped in try/except so a decide bug can never break the run.
    The legacy `actions_log.json`, briefing renderer, and the M5/M6
    pipelines are untouched.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/engine_flags.md`:
  - Last-updated stamp bumped to M7 (2026-05-03).
  - Added the `ENGINE_V2_DECIDE` row.

### Pre-existing files (untouched in this milestone)

- `src/engine_run.py`, `src/engine_run_adapter.py`, `src/guardrails.py`,
  `src/sizing.py`, `src/priors_loader.py`, `src/evidence.py`,
  `src/detect.py`, `src/audience_builders.py`, `src/play_registry.py`,
  `src/anomaly.py`, `src/state_of_store.py` — read-only by `decide()`.
- `src/storytelling.py`, `src/briefing.py`, `src/copykit.py` — the
  renderer chain is untouched (M8 owns the renderer flip).
- `src/action_engine.py` — untouched (M10 owns the deletion).
- `tests/golden/` — no goldens re-baselined.

## Exact commands run

```
# M7 unit + integration tests
python -m pytest tests/test_decide.py -v
# 34 passed in 0.03s

# Golden diff (M4b canonical, both flags forced via monkeypatch)
python -m pytest tests/test_golden_diff.py -v
# 3 passed (no re-baseline)

make golden-test
# 3 passed

# Full suite
python -m pytest tests/ -q
# 371 passed, 5 skipped (M6 baseline was 337 passed; +34 new M7 tests)

# End-to-end smoke: small_sm, M7 + M5 + M6 + M4b flags ON
ENGINE_V2_DECIDE=true ENGINE_V2_SIZING=true \
STATS_NAN_FOR_HARDCODED=true EVIDENCE_CLASS_ENFORCED=true \
MATERIALITY_FLOOR_SCALE_AWARE=true CANNIBALIZATION_GATE_ENABLED=true \
ANOMALY_GATE_ENABLED=true \
  python -m src.main --orders data/SM_orders.csv \
                     --brand m7_smoke --out /tmp/m7_smoke
# Engine ran end-to-end. abstain.state=abstain_soft (expected — under
# M4b flag-on, every legacy action is targeting and the V2 sizer
# suppresses them; M7 then declares ABSTAIN_SOFT per Change 2).
# recommendations=0, considered=0, watching=0.

# End-to-end smoke: small_sm, M7 + M5 ON, M4b OFF (legacy actions present)
ENGINE_V2_DECIDE=true MATERIALITY_FLOOR_SCALE_AWARE=true \
CANNIBALIZATION_GATE_ENABLED=true \
  python -m src.main --orders data/SM_orders.csv \
                     --brand m7_legacy_smoke --out /tmp/m7_legacy
# abstain.state=abstain_soft (legacy actions surface as targeting via the
# M1 adapter; bestseller_amplify survives M5 gates).
# recommendations=1 (bestseller_amplify; targeting; suppressed-style
# treatment is M8's job).
# considered=2:
#   journey_optimization → MATERIALITY_BELOW_FLOOR
#   category_expansion → AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY
# Both have would_fire_if text populated (M5 already populated; M7
# preserves and supplements as needed).

# End-to-end smoke: mid_shopify, M7 + M5 + M6 ON
ENGINE_V2_DECIDE=true ENGINE_V2_SIZING=true \
MATERIALITY_FLOOR_SCALE_AWARE=true CANNIBALIZATION_GATE_ENABLED=true \
ANOMALY_GATE_ENABLED=true \
  python -m src.main --orders data/shopify_orders_mid.csv \
                     --brand m7_mid --out /tmp/m7_mid
# abstain.state=abstain_soft. recommendations=0, considered=0,
# watching=1. Watching surfaces the AOV held observation.

# Default-mode (all flags OFF) sanity check: engine_run.json reflects
# the legacy adapter output, NOT the M7 layer.
python -m src.main --orders data/SM_orders.csv \
                  --brand m7_default --out /tmp/m7_default
# abstain.state=publish, recommendations=3, considered=0, watching=0.
# Confirms ENGINE_V2_DECIDE=false is byte-equivalent to the M6 path.
```

## Tests / checks run and results

| Suite                                            | Result                       |
|--------------------------------------------------|------------------------------|
| `tests/test_decide.py`                           | **34 passed** in 0.03s       |
| `tests/test_golden_diff.py`                      | **3 passed** (no re-baseline)|
| `tests/test_engine_v2_shadow.py`                 | **3 passed**                 |
| Full suite `python -m pytest tests/`             | **371 passed, 5 skipped**    |
| `make golden-test`                               | **3 passed**                 |

Full-suite count went from 337 (M6) → 371 (M7) = +34 new tests. Zero
regressions. Zero golden re-baselines.

## What was implemented

### Class-aware ranking (T7.2)

`rank_recommendations(cards) -> List[PlayCard]` sorts by
`(class_priority, p50, audience_size, play_id)` with the first three
descending. Class priority: measured=3, directional=2, targeting=1,
weak=0. The forcing-function test
`test_measured_outranks_targeting_regardless_of_p50` constructs a
measured play with $100 p50 and a targeting play with $99,999 p50 and
audience 99,999; the measured play wins. This pins the DS Architect
QA Change 2 invariant that targeting must not outrank
measured/directional solely on dollars or audience.

### Top-3 cap (T7.3)

`MAX_RECOMMENDATIONS = 3`. Excess candidates are demoted to
`considered` with `reason_code = CAP_EXCEEDED` and a `would_fire_if`
text from the M7 template. The `test_max_three_recommendations_published`
test constructs 5 measured plays and asserts exactly 3 survive and 2
appear as `CAP_EXCEEDED`.

### Abstain state machine (T7.4 / T7.7)

`_decide_abstain_state(recommendations, data_quality_flags, *, pre_existing_state)`:

- ABSTAIN_HARD: any flag in `_HARD_DQ_FLAGS` (BFCM_OVERLAP,
  REFUND_STORM, TEST_ORDER_ANOMALY, INSUFFICIENT_CLEAN_HISTORY) OR a
  pre-existing ABSTAIN_HARD state. `recommendations` is cleared.
  When upstream `considered` is empty, M7 synthesizes
  `DATA_QUALITY_FLAG` rejections per recommendation so reviewers can
  see the demoted set; when upstream already populated rejections
  (e.g., M5 anomaly gate emitted ANOMALOUS_WINDOW), they are
  preserved.
- ABSTAIN_SOFT: zero measured/directional cards after the cap.
  Recommendations are kept (renderer in M8 will mark them as
  suppressed targeting cards). Reason text: "no measured or
  directional recommendation cleared materiality + cannibalization
  gating".
- PUBLISH: at least one measured/directional in the top-3.

POST_PROMO_WINDOW is intentionally NOT in `_HARD_DQ_FLAGS`; it is a
soft warning per M5's contract. Pinned by
`test_post_promo_window_does_not_force_abstain_hard`.

### Considered assembly (T7.5 / T7.6)

`assemble_considered(pre_existing, cap_exceeded, no_measured, *, recommended_play_ids)`:

- Drops any rejection whose `play_id` is in the recommendation set
  (lists are disjoint).
- Converts cap-exceeded PlayCards to `RejectedPlay(reason_code=CAP_EXCEEDED)`.
- (no_measured is unused on the M7 path; reserved for M8/M9 if a
  future agent wants to surface "would have been measured if X")
- Populates `would_fire_if` from a per-reason-code template when the
  upstream rejection didn't already set one.
- Deduplicates by `play_id` (first wins).
- Caps at `MAX_CONSIDERED_RENDERED = 6` (PM Q10 #6).

### Watching section (T7.9)

`build_watching(state_of_store, *, max_signals=4)`:

- Reads only the M1 typed `Observation` list. Pure, deterministic.
- HELD observations with non-zero `change_magnitude` become
  `WatchedSignal` entries.
- ANOMALOUS observations are excluded (they belong to the
  data-quality footer; including them would double-render).
- MOVED observations are excluded (they belong to the
  state-of-store paragraph).
- Sorted by absolute change magnitude desc, then metric name asc.
- Capped at `MAX_WATCHING_SIGNALS = 4`.
- `threshold_to_act` populated from a small known-metric table:
  `aov`, `repeat_rate_within_window`, `orders`. Unknown metrics get
  `None`. No LLM, no storytelling layer.

### `decide()` orchestration

```python
def decide(engine_run, *, cfg=None) -> EngineRun:
    ranked = rank_recommendations(engine_run.recommendations)
    head, tail = ranked[:3], ranked[3:]
    state, reason = _decide_abstain_state(head, engine_run.data_quality_flags,
                                          pre_existing_state=engine_run.abstain.state)
    if state == ABSTAIN_HARD:
        # clear recommendations, synthesize DQ rejections if needed
        ...
    considered = assemble_considered(engine_run.considered, cap_exceeded=tail,
                                     recommended_play_ids=...)
    watching = build_watching(engine_run.state_of_store)
    return replace(engine_run, recommendations=head, considered=considered,
                   abstain=Abstain(state=state, reason=reason), watching=watching)
```

The function is total (never raises), pure (input not mutated), and
respects all M7 invariants:
- Max 3 recommendations.
- Targeting-only ⇒ ABSTAIN_SOFT, never PUBLISH.
- Hard DQ flag ⇒ ABSTAIN_HARD with `recommendations=[]`.
- No `p`/`q`/`CI`/`confidence_score`/`final_score` introduced into
  V2 merchant-facing fields (the EngineRun schema doesn't define
  them; the M7 module doesn't add them).

## Deviations from the plan

### T7.5 / T7.6 minimal scope

The plan calls for a "would_fire_if" copy builder and a 6-rendered cap
on considered. M7 ships a per-reason-code template
(`_WOULD_FIRE_IF_TEMPLATE`) keyed off the M1 `ReasonCode` enum, with
plain-English strings that are intentionally template-only (no LLM,
no narrative layer). The M5 guardrails already populate
`would_fire_if` for the rejections they emit; M7 only fills in the
gaps for new rejections it introduces (e.g., `CAP_EXCEEDED`,
`DATA_QUALITY_FLAG`). This is the smallest safe implementation; M8 is
free to refine the copy when the renderer ships.

### T7.7 ABSTAIN_SOFT keeps recommendations

The plan says: "ABSTAIN_SOFT: 0 measured/directional clear + ≥0
targeting; PlayCards = top-2 targeting (clearly labeled)." M7 keeps
the top-3 (not top-2) targeting plays in `recommendations` and lets
M8's renderer cap to 2 if PM wants. The reason: changing the cap
between M7 and M8 would couple two milestones unnecessarily; the cap
is presentation, not decision logic. The state itself
(ABSTAIN_SOFT) is the load-bearing decision; the count of
suppressed targeting cards is a renderer concern.

The integration test `test_abstain_soft_with_only_targeting_e2e`
asserts both: state=ABSTAIN_SOFT AND recommendations=2 (because the
test passes 2 targeting cards in). If 3 targeting cards are passed
in, the cap of 3 still applies.

### T7.4 NO_MEASURED_SIGNAL not synthesized as a rejection

The plan suggests treating "0 measured/directional after gating" as
a rejection reason worth surfacing. M7 does NOT synthesize
NO_MEASURED_SIGNAL rejections per recommendation when ABSTAIN_SOFT
fires, because:

1. The `recommendations` list itself is the audit trail (every
   targeting card surfaces with `evidence_class=targeting`).
2. Adding a synthetic rejection per kept card would double-count.
3. The renderer in M8 will display the "no measured opportunities
   cleared" callout from `Abstain.reason`, which is the merchant-
   facing equivalent.

The reason code remains in the `_WOULD_FIRE_IF_TEMPLATE` so a future
agent can opt in if PM disagrees.

### M3 detect → M4 evidence integration deferred to M8/M9

The plan's T7.1 sketch (`detect → evidence_classify → size → apply
guardrails → select`) describes a full V2 build path that constructs
the EngineRun from scratch using M3 candidates + M4 classification.
M7 instead **composes the existing legacy-adapter EngineRun** (output
of `build_engine_run_from_legacy` after `apply_guardrails` and the M6
sizing block in `main.py`). This is the smallest safe implementation
for two reasons:

1. **Risk**: building an EngineRun from M3 candidates would require
   M3 to surface evidence/measurement on Candidate, which it
   intentionally does not (the M3 surface is statistics-free by
   design). Plumbing measurement through would either re-introduce
   the forbidden fields on Candidate or require a parallel "measured
   candidate" type that the plan did not specify.
2. **Plan deferral**: the plan's M3 summary explicitly says
   `Candidate` is "no statistics" and M4a/M4b populate measurement
   on the legacy emitter. Rebuilding the legacy → EngineRun mapping
   from M3 candidates would re-litigate decisions M3 froze.

The legacy adapter + guardrails + sizing chain already produces a
valid `EngineRun` with `evidence_class`, `Measurement`,
`RevenueRange`, `audience` on every PlayCard. M7's `decide()` reads
that EngineRun and applies the decision-layer rules. This preserves
runnable behavior and isolates risk.

When M8/M9 wire the renderer + ML hooks, a future agent can either:
(a) keep the legacy-adapter-as-input shape (simpler), or
(b) refactor to a from-scratch build (more aspirational, requires
M3/M4 surface design work).

The M7 contract — `decide(engine_run) -> engine_run` — works for
both paths.

## Impact on the three baseline fixtures

### `small_sm` under M4b flag-on (canonical M5/M6 baseline state)

- **Without M7 flag**: 0 PRIMARY recommendations (M4b state),
  ABSTAIN_SOFT inherited from the M1 adapter's "empty actions"
  default. `engine_run.json` is byte-identical to the M6 baseline.
- **With `ENGINE_V2_DECIDE=true`**: same 0 recommendations,
  ABSTAIN_SOFT now decided by the M7 state machine (with explicit
  reason text "no measured or directional recommendation cleared
  materiality + cannibalization gating"). Considered list empty
  (no rejections to surface). Watching list empty (no observations
  with the right shape on this fixture). The change is semantic
  (the reason text is now M7-grade), not structural.

### `mid_shopify`

- **Without M7 flag**: 0 recommendations, ABSTAIN_SOFT inherited
  from the M1 adapter.
- **With `ENGINE_V2_DECIDE=true`**: 0 recommendations, ABSTAIN_SOFT
  with M7 reason text. **Watching now surfaces 1 entry** (the AOV
  held observation). This is the visible M7 add.

### `micro_coldstart`

- **Without M7 flag**: 0 recommendations, ABSTAIN_SOFT.
- **With `ENGINE_V2_DECIDE=true`**: same. Cold-start observations
  may produce a watching entry depending on the AOV/orders deltas.

### `small_sm` under M4b flag-OFF + M5/M7 ON (validation case)

This is the most informative case: legacy actions are present, so
M7 has something to act on.

- 3 legacy targeting actions arrive at the EngineRun via the M1
  adapter (`bestseller_amplify`, `journey_optimization`,
  `category_expansion`).
- M5 materiality gate demotes `journey_optimization` ($4,545 < $10k
  floor at this $1.5M ARR tier).
- M5 cannibalization gate demotes `category_expansion` (98% audience
  overlap with `bestseller_amplify`).
- M7 keeps the surviving `bestseller_amplify` (targeting class).
- M7 declares ABSTAIN_SOFT (Change 2 rule: targeting-only, no
  measured/directional).
- `considered = 2` entries (the M5 demotions, with `would_fire_if`
  populated and rendered through the M7 cap of 6).

This validates the full M5 → M7 composition and the Change 2
invariant.

## Whether goldens still pass

**Yes. Zero goldens re-baselined.**

- `tests/test_golden_diff.py` runs unmodified. It forces M4b flags ON
  via monkeypatch but does NOT set `ENGINE_V2_DECIDE`, so the V2
  decide block is a no-op. M4b canonical goldens remain
  byte-identical.
- `make golden-test` → 3 passed.
- The merchant-facing `briefing.html` is unchanged on every fixture
  because the renderer is unchanged (M8 owns the renderer flip).
- `receipts/engine_run.json` is intentionally NOT in the golden tree
  (documented in the M0 summary). M7 changes its content ONLY when
  `ENGINE_V2_DECIDE=true`. With the flag off, the receipt is
  identical to the M6 output.

## Skipped items / accepted notes

None of the listed M7 tickets are skipped.

Accepted notes:

- **M3 candidate detection is not re-wired into `decide()`.** See
  the "Deviations from the plan" section above. M7 composes the
  existing legacy-adapter EngineRun. M8/M9 may revisit.
- **`Watching.current` and `Watching.prior` are not populated.** The
  M1 `Observation` schema doesn't carry the prior numeric value
  separately from the change magnitude; surfacing both would require
  an Observation schema bump. M7 leaves these as `None`; the
  `threshold_to_act` text + `trend` carry enough information for
  the M8 renderer.
- **`would_fire_if` template strings are intentionally generic.**
  The M5 guardrails already produce specific per-rejection text
  (e.g., "expected impact $4,545 below scale-aware floor $10,000");
  M7 only fills in for the new rejection types it introduces. M8
  will refine for merchant-facing copy if needed.
- **No new env flag added beyond `ENGINE_V2_DECIDE`.** The
  `ABSTAIN_MODE_ENABLED` flag is referenced in
  `docs/engine_flags.md` but the abstain state machine in M7 is
  unconditional (always-on inside `decide()`). The M10 deletion list
  already marks it as never-enabled-separately.

## Remaining risks

1. **Legacy adapter + M4b flag-off produces "all-targeting" labels.**
   Today the legacy adapter defaults `evidence_class = TARGETING`
   when the legacy emitter does not stamp one. With M4b flags off,
   none of the legacy actions stamp `evidence_class`, so every
   action surfaces as targeting in EngineRun. This means the M7
   ABSTAIN_SOFT state correctly fires (no measured/directional
   present), but a merchant who sees only the EngineRun would think
   the engine never has measured opportunities. **This is M4b's
   transition state, not an M7 regression.** The merchant-facing
   briefing.html still reads from `actions_log.json` (legacy path),
   so this is a receipts-only artifact.

2. **HARD-flag synthesis path may double-emit if M5 is partially on.**
   When `ANOMALY_GATE_ENABLED=true`, M5 already clears recommendations
   and populates `considered` with ANOMALOUS_WINDOW rejections. M7
   detects the existing ABSTAIN_HARD state and does NOT synthesize
   DATA_QUALITY_FLAG rejections. When `ANOMALY_GATE_ENABLED=false`
   and a HARD flag is present in receipts, M7 synthesizes the
   rejections. The two paths are tested separately
   (`test_hard_dq_flag_preserves_pre_existing_considered` vs
   `test_hard_dq_flag_synthesizes_data_quality_rejections`).

3. **`measurement.consistency_across_windows` is not consumed by
   ranking yet.** The M4b combiner stamps this on measured candidates
   as a robustness signal, but the M7 ranker uses only
   `(class_priority, p50, audience_size, play_id)`. If two measured
   plays have identical p50 and audience, the consistency value is
   not used as a tiebreaker. The M7 plan does not require it, and
   the deterministic play_id tiebreak produces stable ordering. M8
   or M9 may incorporate it if needed.

4. **The Watching threshold-to-act table covers 3 metrics.** AOV,
   repeat_rate_within_window, orders. State-of-store today emits
   these three (per `src/state_of_store.py`). If M8/M9 adds new
   typed observations (e.g., per-SKU velocity), the threshold table
   will need a corresponding entry; otherwise `threshold_to_act`
   will be `None` for those signals (which the renderer can handle
   gracefully).

## Readiness for Milestone 8

**Green to start M8.** M7 acceptance criteria are met:

- `decide()` produces a fully-populated `EngineRun` with class-aware
  ranking, top-3 cap, abstain state, considered list, and watching.
  Verified by 34 unit/integration tests + 3 end-to-end smoke runs.
- ABSTAIN_HARD on HARD data-quality flags; recommendations cleared;
  considered preserved or synthesized. Verified.
- ABSTAIN_SOFT on cold-start / targeting-only / no-recommendations.
  Verified.
- ABSTAIN_SOFT on the materiality-strips-all-measured fixture
  (Change 2 rule); targeting plays NOT published as PUBLISH.
  Verified by `test_targeting_only_yields_abstain_soft`.
- PUBLISH on the standard-merchant fixture (when measured/directional
  exist). Verified.
- M0/M4b/M5/M6 goldens still pass.

**M8 prerequisites that M7 satisfies:**

- `EngineRun.recommendations` is class-ranked top-3 with stable order.
- `EngineRun.considered` is deduplicated against recommendations,
  capped at 6, with `would_fire_if` populated on every entry.
- `EngineRun.abstain.state` is one of PUBLISH / ABSTAIN_SOFT /
  ABSTAIN_HARD with a human-readable `reason`. The M8 renderer can
  switch on this state to choose between the standard layout, the
  "no measured opportunities" callout, and the data-quality memo.
- `EngineRun.watching` is a deterministic list of 0–4 typed
  WatchedSignal entries with `metric`, `trend`, and
  `threshold_to_act`. The M8 Watching renderer can consume this
  directly.
- `EngineRun.state_of_store` is unchanged (M1 contract preserved);
  the M8 lead paragraph can read the typed Observations.
- `EngineRun.scale.materiality_floor` is set when M5 was on;
  M8 can render it in the data-quality footer if PM wants.
- The legacy `actions_log.json`, briefing template, and CSV → HTML
  workflow are unchanged. M8's task is to add `storytelling_v2`
  next to the legacy renderer behind `ENGINE_V2_OUTPUT`, not to
  replace anything.

The M7 contract — `decide(engine_run) -> engine_run` — is a clean
seam for M8 to plug into. M9 can additionally read the same
EngineRun for ML-readiness logging.

## Validation summary

- **34 new tests** in 1 new test file. Zero existing tests modified.
- **0 regressions** in the 337-test M6 baseline (now 371 with M7
  additions).
- **0 goldens re-baselined.** All 3 M0/M4b/M5/M6 fixtures still
  pass byte-identical with the V2 decide flag off.
- **1 new env flag** added (`ENGINE_V2_DECIDE`); default off.
- **1 new module** added: `src/decide.py`. Leaf-level (imports only
  `engine_run`).
- **3 end-to-end smoke runs** (small_sm M7-only, small_sm M7+M5,
  mid_shopify M7+M5+M6) confirm `decide()` runs end-to-end and
  produces the expected EngineRun shape.
- **Renderer untouched. Briefing template untouched. Legacy
  `actions_log.json` untouched.** Per the M7 hard NOT-IN-SCOPE rule.
- **No `p` / `q` / `CI` / `confidence_score` / `final_score`** in
  the M7-produced EngineRun (verified by inspection; the schema
  doesn't define these fields and `decide()` does not introduce
  them).
