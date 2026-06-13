# G-1 Summary — Pin synthetic supplements slate fixture

**Date:** 2026-05-10
**Branch:** post-6b-restructured-roadmap
**Ticket:** Sprint 4 G-1 (post-6b-restructured implementation plan §4)
**Outcome:** New pinned `healthy_supplements_240d_briefing.html` fixture +
12 new tests + 9 new `KI-` entries (KI-20 through KI-28). Engine runs
end-to-end on supplements without crash. M0 Beauty pinned fixture
byte-identical. Suite **1141 passed / 14 skipped / 0 failed** (was
1129/14/0 at S-6 closeout).

## 1. Approved scope

G-1: build a synthetic supplements merchant fixture mirroring the Beauty
pinned fixture shape, run the V2 engine end-to-end on it, capture every
breakage, pin the fixture sha256, and file every breakage as a
`KI-` entry under KNOWN_ISSUES.md category 5. Discovery ticket — the bug
list IS the deliverable, not a clean engine.

## 2. Patch summary

- New fixture data files cloned from the existing
  `supplement_replenishment_240d_*` CSVs to `healthy_supplements_240d_*`
  (byte-identical copy). The existing fixture already uses realistic
  supplement SKU names (Magnesium Glycinate 200mg 60ct, Vitamin D3 + K2
  Capsules 90ct, Probiotics 50 Billion CFU 30ct, Omega-3, Whey Protein
  Powder Vanilla 2lb, Creatine Monohydrate 500g, Zinc + Quercetin Immune
  Formula, etc.) and the existing scenario YAML declares reorder-interval
  cadences 28–45 days plausible for supplements. Rename pins it under
  the same naming convention as `healthy_beauty_240d`.
- New scenario entry `healthy_supplements_240d` in
  `tests/fixtures/synthetic_scenarios.yaml`.
- New pinned briefing.html at
  `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html`,
  sha256 `feb03500c1adc4a8a8a6762c6f0c98fd2a81ba2a9d3838d75ccca0ea221a0e0d`.
- New test file `tests/test_slate_regression_supplements_brand.py`
  mirroring `tests/test_slate_regression_beauty_brand.py` shape (module
  fixture, role-section assertions, byte-stable snapshot, sha256
  constant, M0-lane separation guard).
- New `KI-20`..`KI-28` entries in `KNOWN_ISSUES.md` category 5.

No `src/` changes. No schema changes. No engine-side fixes applied —
every supplements breakage was filed as a `KI-` entry per the discovery
contract; engine-side fixes are Sprint 5+ scope.

## 3. Files changed

- `tests/fixtures/synthetic_scenarios.yaml` (additive scenario entry)
- `tests/fixtures/synthetic/healthy_supplements_240d_orders.csv` (new,
  byte-identical clone of `supplement_replenishment_240d_orders.csv`)
- `tests/fixtures/synthetic/healthy_supplements_240d_inventory.csv` (new,
  byte-identical clone)
- `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html`
  (new pinned fixture)
- `tests/test_slate_regression_supplements_brand.py` (new — 12 tests)
- `KNOWN_ISSUES.md` (KI-20..KI-28 appended; open count table updated)

Untouched: any `src/`, `config/priors.yaml`, S-2/S-3/S-4/S-5/S-6
substrate surfaces, the Beauty pinned fixture, M0 goldens.

## 4. Tests/checks run

- New supplements regression test: **12/12 green** in 13.31s.
- Beauty pinned slate regression test (M0-equivalent contract):
  **19/19 green** — sha256 `5fa9f697...`/`dcb45cee...` lineage
  unchanged.
- Full suite: **1141 passed, 14 skipped, 0 failed** in 679s (was
  1129/14/0 at S-6 closeout; delta = +12 G-1 tests).
- Two-run determinism check: re-running the harness produces a
  briefing.html with the same sha256 (`feb03500c1...`) as the pinned
  fixture.

## 5. Behavior changes

None to production engine. The harness now exposes a new scenario
`healthy_supplements_240d` (additive). No `src/` code modified.

## 6. Artifacts added

| Path | Purpose |
|---|---|
| `tests/fixtures/synthetic/healthy_supplements_240d_orders.csv` | Supplements orders (clone) |
| `tests/fixtures/synthetic/healthy_supplements_240d_inventory.csv` | Supplements inventory (clone) |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | Pinned briefing (sha256 `feb03500c1...`) |
| `tests/test_slate_regression_supplements_brand.py` | 12 regression tests |
| `KNOWN_ISSUES.md` KI-20..KI-28 | Bug list per discovery contract |

## 7. Full breakage list with reproduction steps

Reproduction for every entry below: run the V2 + slate flag stack on the
new fixture, e.g.

```python
from tests.synthetic_harness import run_scenario
env = {"ENGINE_V2_OUTPUT":"true", "ENGINE_V2_DECIDE":"true",
       "ENGINE_V2_SLATE":"true", "ENGINE_V2_SIZING":"true",
       "VERTICAL_MODE":"supplements", "WINDOW_POLICY":"auto"}
result = run_scenario("healthy_supplements_240d", out_dir, env_overrides=env)
```

### Breakage 1 (KI-20) — Zero Recommended Now cards; `first_to_second_purchase` doesn't surface
- Beauty: 1 Recommended Now card (`first_to_second_purchase`,
  directional via Phase 5.6 builder).
- Supplements: 0 Recommended Now cards; `first_to_second_purchase` is
  absent from every section (not even in Considered).
- Hypothesis: Phase 5.6 directional builder's L28 cohort definition
  produces no qualifying observations because supplement reorder
  cadences (28–45 days) straddle the L28 window edge.
- **Sprint 5+ scope:** Instrument the directional builder; either widen
  the window for supplements or document an explicit no-signal abstain.
- **Contract:** CONTRACT-SAFE (engine-side; no schema change).

### Breakage 2 (KI-21) — Zero Recommended Experiment cards; allowlist plays both fail gating with generic reason
- A4 allowlist `{discount_hygiene, bestseller_amplify}` both detected
  by M3 shadow on supplements, both routed to Considered with
  `no_measured_signal`. Generic reason_text — same string as every
  other targeting-held play.
- **Sprint 5+ scope:** Extend `_candidate_reason_code` fan-out on the
  experiment-held path; populate `held_reason_detail` struct (already
  reserved in 6B). Add typed `EXPERIMENT_HELD_PRIOR_SUPPRESSED` enum.
- **Contract:** CONTRACT-SAFE (additive enum value).

### Breakage 3 (KI-22) — "Repeat rate 0% suspiciously low" advisory doesn't propagate to `data_quality_flags`
- Engine stdout: `⚠️ Metric warnings: Repeat rate 0% suspiciously low
  for 972 orders`. `engine_run.json::data_quality_flags = []`.
- Repeat rate L28 = 0.4% on a store with 96.3% returning-customer share
  — structurally incoherent for supplement cadences (28–45d > 28d
  window).
- **Sprint 5+ scope:** Suppress or relabel `repeat_rate_within_window`
  Watching row when cadence > window; emit typed
  `METRIC_INCOHERENT_FOR_CADENCE` flag.
- **Contract:** CONTRACT-SAFE (additive flag enum + Watching
  suppression).

### Breakage 4 (KI-23) — Silent drop-out: 5 plays detected by M3 but never appear in Considered
- Shadow detection: 8 V2-only candidates
  (`aov_momentum, bestseller_amplify, category_expansion,
  discount_hygiene, frequency_accelerator, journey_optimization,
  subscription_nudge, winback_21_45`).
- Considered: 6 cards; `aov_momentum`, `category_expansion`,
  `journey_optimization` silently dropped. `first_to_second_purchase`
  and `empty_bottle` also absent.
- **Sprint 5+ scope:** Surface "detected but not surfaced" trace in
  Considered, OR pin a documented filter so the drop is explicit.
- **Contract:** CONTRACT-SAFE (additive).

### Breakage 5 (KI-24) — `subscription_nudge` lands at generic `no_measured_signal` on its strongest fixture
- For supplements with subscription cadence, `subscription_nudge` is
  THE core thesis. Today: generic reason. The structural issue is the
  Phase 4.2 deferral (multiplier-vs-baseline conflation,
  `project_phase4_subnudge_open.md`).
- **Sprint 5+ scope:** Phase 4.2 redesign; supplements fixture becomes
  the acceptance test.
- **Contract:** CONTRACT-SAFE.

### Breakage 6 (KI-25) — `routine_builder` rejected `audience_too_small` on a 1,200-customer supplements store
- Audience floor inherited from beauty over-rejects on supplements
  (smaller customer bases by model).
- **Sprint 5+ scope:** Per-vertical audience floors in priors.yaml
  (overlaps G-3 scope).
- **Contract:** CONTRACT-SAFE (priors edits).

### Breakage 7 (KI-26) — State-of-store observations populate `current`/`delta_pct` but leave `prior: null`
- Every observation (AOV, repeat rate, orders, returning-customer
  share, net sales) shows `"prior": null` despite a computed
  `delta_pct`. Beauty populates `prior`. Breaks the 6B typed-slot
  contract on the supplements path.
- **Sprint 5+ scope:** Trace which observation builder branch on the
  supplements path skips the `prior` write.
- **Contract:** CONTRACT-SAFE (populating an already-reserved typed
  slot).

### Breakage 8 (KI-27, accepted) — `empty_bottle` clean-skipped (G-2 working as intended)
- Supplements run does NOT crash on `empty_bottle`. The
  `vertical_applicable=frozenset({"beauty","mixed"})` filter at
  `src/decide.py:614` clean-skips. Confirmed positively by the G-1
  fixture's pinned membership (empty_bottle absent from Recommended +
  Considered).
- **Status:** accepted; G-3 supplements-coherent parser is the future
  re-pin event, not a regression.

### Breakage 9 (KI-28, tracked) — `mixed` vertical not exercised by G-1
- G-1 pinned supplements only. The KI-19 question ("does `mixed`
  silently fall back to beauty priors") remains open under G-3 scope.
- **Status:** tracked under G-3; document the gap so readers don't
  assume `mixed` is now end-to-end tested.

## 8. Founder escalation required (CONTRACT-RISK)

**None.** Every breakage discovered during G-1 is fixable inside the
frozen `engine_run.json` schema and the frozen `event_version=1`
payloads. Specifically:

- KI-20 / KI-21 / KI-22 / KI-23 / KI-26: engine-side fixes only
  (selectors, builders, observation population) — no payload field
  shape change.
- KI-21's typed reason_code growth and KI-22's `data_quality_flag`
  growth are both additive enum values on existing string fields —
  Sprint 2 schema-freeze explicitly allows additive enum values without
  bumping `event_version`.
- KI-24 / KI-25 are priors/redesign work; `config/priors.yaml` is
  outside the frozen contract.
- KI-27 is the intended G-2 behavior (no fix needed).
- KI-28 is already tracked under G-3 (no new escalation).

No founder escalation triggered. The G-1 CONTRACT-RISK rule did not
fire on any discovered breakage.

## 9. Remaining risks

1. **Engine-emitted `confidence_mode: "learning"`** in
   `briefing_meta`. memory.md Phase 1 says "No 'Learning' CONFIDENCE_MODE
   that relaxes thresholds." Beauty fixture also emits this value, so
   it's not supplements-specific and is documented as legacy
   (`engine_run_adapter` writes it from `CONFIDENCE_MODE` env). NOT a
   G-1 finding; flagged here so future readers don't mis-attribute it
   to KI-20/KI-21.
2. **Supplements run never reaches PUBLISH state** under current V2
   gates. The G-1 pinned fixture locks this as the regression contract
   — any deliberate improvement (e.g. KI-20 close, KI-24 close) will
   require an explicit re-pin of `PINNED_SHA256` and the considered
   membership set.
3. **The fixture data is identical to the existing
   `supplement_replenishment_240d_*` CSVs.** Future merges that touch
   the old fixture must remember to keep the new one in sync, or accept
   that the two diverge intentionally. No automatic linkage today.

## 10. Follow-up work (Sprint 5+ ticket recommendations)

Each `KI-` maps to one Sprint 5+ ticket (priority ordering reflects
merchant-facing impact):

| Priority | Ticket | KI | Engine surface |
|---|---|---|---|
| 1 | Supplements directional Recommended Now path | KI-20 | Phase 5.6 directional builder window/cohort fix |
| 2 | Supplements Watching metric coherence | KI-22 + KI-26 | Observation builder + Watching suppression |
| 3 | Per-vertical audience floors | KI-25 | `config/priors.yaml` (overlaps G-3) |
| 4 | Experiment-held typed reason fan-out | KI-21 | `_candidate_reason_code` + `held_reason_detail` |
| 5 | Detected-but-not-surfaced trace | KI-23 | `populate_considered_from_candidates` |
| 6 | Phase 4.2 subscription_nudge redesign | KI-24 | (already deferred; supplements fixture is acceptance test) |

None of these block Phase 9 readiness (no calibration loop dependency).
KI-19 + KI-28 (`mixed` semantic) remain G-3 scope, not Sprint 5+.

---

**Bottom line:** G-1 delivered exactly what the discovery contract
asked for. Engine runs end-to-end on supplements. Nine concrete
breakages filed as `KI-` entries. Pinned fixture is byte-stable
across runs. Beauty M0 byte-identical. No contract-risk escalation
required.
