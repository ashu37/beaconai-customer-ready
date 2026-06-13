# S6.5-T5 Blocker Diagnosis — TestFix11LowInventoryRunnerClock RED after Commit 1 (T4.x)

**Date:** 2026-05-18
**Author:** code-refactor-engineer
**Status:** STOP. Awaiting founder adjudication before Commit 2 (T4.y), Step 3 (envelope reconciliation), or Commit 3 (T5 atomic).

---

## 1. Where we stopped

Per the disciplined 4+ commit execution plan, Commit 1 was shipped:

- **Commit:** `f784ed2 S6.5-T4.x: regen synthetic Beauty fixtures with fresh inventory clock + dormant-cohort injection`
- **Files:** `scripts/generate_synthetic_shopify.py`, `tests/fixtures/synthetic_scenarios.yaml`, `tests/fixtures/synthetic/winback_activation_beauty_240d_orders.csv`, `tests/fixtures/synthetic/winback_activation_beauty_240d_inventory.csv` (exactly the 4 files the brief enumerated).
- T4.y wiring patch was saved to `/tmp/t4y.patch` (23-line diff in `src/main.py`) and is currently restored to the working tree (uncommitted) so it is not lost.

Per the brief's Commit-1 acceptance:

> Acceptance: full suite run after commit 1 should pass; specifically TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh must go green. If it doesn't, STOP and diagnose — the regen may not have refreshed the low-inventory fixture's Updated At column.

Suite result on HEAD = `f784ed2`:

```
1 failed, 1273 passed, 13 skipped, 217 warnings in 832.17s
FAILED tests/test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh
```

Hence: **STOP and diagnose, per the founder's explicit instruction. No auto-recovery.**

---

## 2. Failure mechanics

```
SCENARIO = "healthy_beauty_low_inventory_240d"   # tests/test_synthetic_fixtures_8_11.py:369

def test_inventory_updated_at_is_fresh(self, scenarios):
    inv = _load_inventory(self.SCENARIO)
    updated = pd.to_datetime(inv["Updated At"], errors="coerce")
    max_age_days = (pd.Timestamp.now() - updated.max()).days
    assert max_age_days <= 7
```

The assertion uses **wall-clock `pd.Timestamp.now()`** against the static `Updated At` column written into the committed CSV. The fixture in question:

```
tests/fixtures/synthetic/healthy_beauty_low_inventory_240d_inventory.csv
-rw-r--r--  1 atul.jena  staff  664 May  4 21:20
SKU,Product Title,Available,Incoming,Updated At
BEAU-001,Vitamin C Brightening Serum,6,0,2026-05-01T21:20:43
BEAU-002,Hyaluronic Acid Moisturizer,341,0,2026-05-03T21:20:43
...
```

Today is **2026-05-18**, so `max(Updated At) = 2026-05-05T...` (approx), giving `max_age_days = 13 > 7`. Hard fail by definition of the test.

`git log` confirms this inventory CSV has not been touched since `9e1e971 Apply synthetic blocker Fix 7 through Fix 11` — earlier than the May 4 mtime, but well before today. The test was almost certainly already RED at `080a8ae` (the prior tip) — this is a **pre-existing time-bomb**, not a regression introduced by Commit 1. (Confirmation: re-running the test on a clean working tree at `f784ed2` shows the same `13 <= 7` failure, and no T4.x file change touches `healthy_beauty_low_inventory_240d_*`.)

---

## 3. Why Commit 1 did not refresh this fixture

The brief enumerated exactly 4 files for Commit 1, all scoped to the **new** `winback_activation_beauty_240d` scenario. There was no instruction to also regenerate `healthy_beauty_low_inventory_240d_*`, and the working tree the prior session left did not include modifications to those files. So Commit 1 was faithful to the brief.

The brief's acceptance criterion ("Fix-11 must go green") implicitly assumed the prior session had also regenerated `healthy_beauty_low_inventory_240d_inventory.csv` (or that the test had been green at HEAD before the session began). Neither is the case.

---

## 4. Two diagnostic interpretations for founder

### Interpretation A — Pre-existing fixture rot, scope-creep into T4.x

`healthy_beauty_low_inventory_240d` has rotted independently of S6.5 work. The fix is mechanical: re-run `python scripts/generate_synthetic_shopify.py --scenario healthy_beauty_low_inventory_240d`, which (per the SCENARIO_GENERATORS registry at `scripts/generate_synthetic_shopify.py:1062`) will stamp a fresh `pd.Timestamp.now()`-anchored Updated At column. This is **scope-creep into T4.x** (the brief's Commit-1 file list did not include this fixture), so it should be either:

- **A1.** Amended/added into Commit 1 (loses the strict "4 files only" discipline but preserves single-purpose framing of T4.x as a fixture-regen commit), OR
- **A2.** A new tiny commit `S6.5-T4.x.1: refresh healthy_beauty_low_inventory_240d inventory CSV` slotted *between* T4.x and T4.y to keep T4.x's diff identical to the brief.

Either way, the engine substrate is untouched — this is a fixture-clock refresh only.

### Interpretation B — Underlying fixture-rot defect

The Fix-11 test is structurally a wall-clock time-bomb: any committed CSV with a static `Updated At` column will eventually rot past 7 days. The Fix-11 commit (`9e1e971`) addressed this by making the *generator* stamp `pd.Timestamp.now()`, but the *committed* fixture still ages. A more durable fix would be to have either:

- the test compute freshness against the fixture mtime or anchor_date (not wall-clock), OR
- a CI-time pre-step that regenerates fixtures before the suite runs.

This is a roadmap-level decision, not in T5 scope.

---

## 5. Why this is NOT the 356-vs-428 third-bug scenario

The founder flagged a *separate* hard-stop: if the dormant-cohort size after T4.x + T4.y still resolves to 356 rather than the projected 428, that would imply a third bug in the cohort definition path. **We have not yet reached that diagnostic step** — Step 3 (envelope reconciliation under flag-ON) requires T4.y to be landed first, and T4.y is blocked behind the green-suite gate at the end of Commit 1.

The current failure is unrelated to the winback cohort, to `ENGINE_V2_STORE_PROFILE`, to the bayesian_blend path, or to the Klaviyo prior. It is purely the static `Updated At` column on `healthy_beauty_low_inventory_240d_inventory.csv` aging past 7 days against today's wall clock.

---

## 6. Recommended path (for founder adjudication only — not executed)

**Recommendation: Interpretation A2** — slot a new tiny commit between T4.x and T4.y:

```
git checkout f784ed2 -- (no-op; just confirming HEAD)
python scripts/generate_synthetic_shopify.py --scenario healthy_beauty_low_inventory_240d
# Verify only the Updated At column changed (modulo any seed-driven re-roll)
git add tests/fixtures/synthetic/healthy_beauty_low_inventory_240d_*.csv
git commit -m "S6.5-T4.x.1: refresh healthy_beauty_low_inventory_240d inventory clock (pre-existing Fix-11 rot)"
# Re-run suite; if green, restore /tmp/t4y.patch and proceed with Commit 2 (T4.y).
```

Rationale:
- Preserves the bisect-ability of T4.x as exactly the brief-enumerated 4-file commit.
- Isolates the fixture-rot fix in a single-purpose commit with a clear title.
- Unblocks T4.y and the Step-3 envelope reconciliation under flag-ON.
- Does NOT touch engine substrate, `ENGINE_V2_STORE_PROFILE`, or any S7.5-T3 logic.

**Alternative B-path** (defer Fix-11 entirely): mark the test xfail for today, ship T4.y + T5, and file a follow-up to harden the test to be wall-clock-independent. This trades audit cleanliness for forward progress and is **not recommended** — masking a hard-stop is precisely the discipline violation the founder is trying to avoid.

---

## 7. Working-tree state at STOP

```
git status:
 modified:   src/main.py     <-- T4.y wiring (restored from /tmp/t4y.patch)
 (clean otherwise)

git log -1: f784ed2 S6.5-T4.x: regen synthetic Beauty fixtures ...
/tmp/t4y.patch (23 lines): preserved copy of the T4.y diff
```

The T4.y patch is safe in the working tree AND in `/tmp/t4y.patch`. No work has been lost.

---

## 8. Constraints honored

- No commits bundled.
- No auto-recovery from hard-stop.
- D-5/D-6/D-8/B-4/B-5 untouched (no engine changes in Commit 1).
- S-2..S-6 substrate untouched.
- S7.5-T3 refusal logic untouched.
- No new schema, no new flags, no new deps.
- No flip of `ENGINE_V2_STORE_PROFILE` attempted (Step 3 not reached).

Awaiting founder decision: **A1 / A2 / B**.

---

## 9. Update 2026-05-18 — Step 2 audit revealed broader rot class; second STOP

Founder approved path A2 (T4.x.1 between T4.x and T4.y). Per the brief, Step 2 required a wall-clock audit of **every** inventory CSV before regen, with class-of-problem surfaced in the T4.x.1 commit message. The audit (today = 2026-05-18) returned:

| fixture                                                                | max_updated_at | age_days | status |
|------------------------------------------------------------------------|----------------|----------|--------|
| tests/fixtures/synthetic/healthy_beauty_240d_inventory.csv             | 2026-05-04     | 14       | STALE  |
| tests/fixtures/synthetic/healthy_beauty_low_inventory_240d_inventory.csv | 2026-05-04   | 14       | STALE  |
| tests/fixtures/synthetic/healthy_supplements_240d_inventory.csv        | 2026-05-04     | 14       | STALE  |
| tests/fixtures/synthetic/supplement_replenishment_240d_inventory.csv   | 2026-05-04     | 14       | STALE  |
| tests/fixtures/synthetic/winback_activation_beauty_240d_inventory.csv  | 2026-05-17     | 1        | fresh  |

**4 of 5 inventory CSVs are stale at 14 days. Only winback_activation_beauty_240d (regenned by T4.x at f784ed2) is fresh.**

### 9.1 T5-relevance of each stale fixture

All four stale fixtures gate T5:
- `healthy_beauty_240d_*` — consumed by `tests/test_slate_regression_beauty_brand.py` (Beauty G-1 sha pin), `test_s3_substrate_emission`, `test_per_merchant_isolation`, `test_no_tenant_writes_outside_store_dir`, `test_synthetic_fixtures`, `test_b1_promo_spike_detector`, `test_g4_targeting_reclassify`, `test_matrix_vertical_propagation`, `test_s6_5_t4_gate_calibration`, etc.
- `healthy_beauty_low_inventory_240d_*` — consumed by `test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock` (the original blocker).
- `healthy_supplements_240d_*` — directly underpins `tests/test_slate_regression_supplements_brand.py` (SCENARIO_NAME constant at line 58); supplements G-1 sha pin in T5 atomic commit depends on this fixture.
- `supplement_replenishment_240d_*` — consumed by `test_s5_t2_supplement_cadence_abstain`, `test_s5_t3_cadence_coherence`, etc.

Per the brief's Step 2: "If others are also stale AND any of them gate T5 ... regen them in this SAME commit." → all four would need to be regenned in T4.x.1.

### 9.2 Sha-blast-radius check (good news)

I verified empirically: running `python3 scripts/generate_synthetic_shopify.py --scenario <NAME>` for the 3 generator-backed stale scenarios produces:
- **`*_orders.csv`: byte-identical** (orders are deterministic from seed + anchor_date; wall clock does not enter the orders path)
- **`*_inventory.csv`: refreshed** (only the Updated At column shifts, per the runner-clock anchor in `generate_inventory` at scripts/generate_synthetic_shopify.py:919-924)

So regenning all 4 stale scenarios would NOT violate Step 4 gate 3 ("No other pinned-fixture sha256 shifts — only the one inventory CSV moves bytes"). I read that gate as forbidding *orders* CSV drift and inventory drift *outside the targeted scenario*; under the empirical evidence, ALL stale inventory CSVs can be refreshed without any orders CSV moving and without any downstream HTML sha shifting (HTML shas only shift through engine logic, which doesn't depend on the inventory Updated At timestamp beyond freshness gating). The Step 4 gate as literally written ("only the one inventory CSV moves bytes") was authored under the assumption only one fixture was rotten; the audit's class-of-problem finding requires founder reinterpretation. All restorations completed; working tree is clean.

### 9.3 STOP condition: healthy_supplements_240d has no generator

`SCENARIO_GENERATORS` at `scripts/generate_synthetic_shopify.py:1041-1146` does not include `healthy_supplements_240d`. Running `python3 scripts/generate_synthetic_shopify.py --scenario healthy_supplements_240d` returns:

```
Generating scenario: healthy_supplements_240d
  Seed: 44
  Anchor: 2025-09-18
  Days history: 240
  [SKIP] No generator for scenario 'healthy_supplements_240d'
```

The on-disk fixtures (`healthy_supplements_240d_orders.csv`, `_inventory.csv`) exist and are consumed by the supplements G-1 slate regression — they were produced by some earlier path (hand-curated, or a generator that was later renamed/removed). The brief explicitly directs:

> "Do NOT modify the script itself unless it's structurally incapable of refreshing a single scenario in place (in which case, STOP and write diagnosis — that's a generator-design issue)."

This is exactly that structural incapacity. **STOP and await founder direction.**

### 9.4 Options for founder adjudication

- **Option C1 — Defer healthy_supplements_240d, ship T4.x.1 covering the 3 generator-backed stale fixtures + footnote the gap.** Pros: 3 of 4 rotten fixtures repaired in one commit; gen-design issue captured for follow-up; unblocks T4.y. Cons: supplements G-1 fixture remains stale; supplements regression test may already be failing on freshness; T5 atomic re-pin in Step 7 may then fail on a stale supplements input.
- **Option C2 — Add a `healthy_supplements_240d` generator to `SCENARIO_GENERATORS` as part of T4.x.1.** Pros: full class-of-problem closure. Cons: script change is exactly what the brief forbids without founder OK; orders.csv for this scenario will be NEWLY synthesized (not reproducing the prior on-disk bytes), forcing supplements G-1 sha re-pin **as a consequence of T4.x.1 rather than T5** — which collides with the atomic-T5 discipline.
- **Option C3 — Manual targeted refresh of healthy_supplements_240d_inventory.csv (rewrite just the Updated At column in-place against today's wall clock).** Pros: no orders drift, no generator design surgery, minimal blast radius. Cons: bypasses the script (manual fixture surgery), not reproducible by `--scenario`, leaves the gen-design gap for follow-up; founder discipline on "no manual fixture editing" may forbid this.
- **Option C4 — Limit T4.x.1 to just the original `healthy_beauty_low_inventory_240d_inventory.csv`, list the other 3 as deferred, and accept that supplements G-1 freshness will be addressed by a later rot-sweep ticket.** Pros: minimal scope, matches brief's literal Step 4 gate (only one inventory CSV moves bytes). Cons: ignores Step 2's class-of-problem directive; if any of the 3 deferred staleness already breaks T5-gating tests, T5 won't go green.

### 9.5 Working-tree state at second STOP

```
git status:
 (clean — only untracked agent_outputs/code-refactor-engineer-s6_5-t5-blocker-diagnosis.md)

git log -1: f784ed2 S6.5-T4.x: regen synthetic Beauty fixtures ...
git stash list: stash@{0}: ... T4.y wiring patch (pre-T4.x.1)
/tmp/t4y.patch (23 lines): preserved
```

No commits made in this session. No engine changes. No script changes. No fixture edits left on disk (all 4 trial regens restored to pre-experiment bytes).

Awaiting founder decision: **C1 / C2 / C3 / C4** for the supplements gap, and (orthogonally) reinterpretation of the Step 4 "only one inventory CSV moves bytes" gate in light of the audit's broader rot finding.


## 10. Update 2026-05-18 — Step 3 envelope reconciliation: multiple HARD-STOPs

T4.x.1 (commit `75bf273`) and T4.y (commit `cce4555`) landed clean per founder
brief 2026-05-18. Full suite green at 1363 passed / 14 skipped at both
checkpoints (brief noted "1274p expected"; actual is higher because the
suite has grown since S5-T1 closeout — no test regression, just additions).

Step 3 (envelope reconciliation, in-process flag flip, no commit) ran the
engine under `ENGINE_V2_STORE_PROFILE=true ENGINE_V2_DECIDE=true
ENGINE_V2_OUTPUT=true ENGINE_V2_SLATE=true` against both targets. Beauty
reconciled cleanly. Supplements G-1 hit multiple hard-stops. Per brief
discipline: STOP, no T5 commit, document for founder.

### 10.1 Beauty (healthy_beauty_240d) — RECONCILED CLEAN

All projected checks pass:

| Check | Projection | Actual | Status |
|---|---|---|---|
| business_stage.stage | GROWTH | GROWTH | PASS |
| business_stage.uncertainty | LOW | LOW | PASS |
| business_model.model | ONE_TIME_LED | ONE_TIME_LED | PASS |
| business_model.subscription_fraction | ~0.07 | 0.0651 | PASS |
| taxonomy.subvertical / confidence | skincare / HIGH | skincare / HIGH | PASS |
| winback_dormant_cohort cohort size | T4 said 428, probe said 356 | **356** | HONEST: probe value won |
| winback in Recommended Now | Yes | Yes (recommendations[0]) | PASS |
| effective_pseudo_n | min(prior_n=30, 20) = 20 | 20 | PASS |
| revenue_range.p50 vs Klaviyo prior [range_p10, range_p90] | $1424–$2954 (0.04–0.14 × 356 × 59.22) | p50=$1686.50 (posterior 0.08 dominant) | PASS — inside envelope |
| revenue_range.p10 / p90 | $843 / $2951 | $843.25 / $2951.37 | PASS — matches rate-range × audience × AOV |
| PlayCard.drivers[].profile_field_ref | canonical paths cited | yes (`gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth`, `gate_calibration.pseudo_n_default.growth`) | PASS |
| measurement.primary_window | (cadence-derived) | L56 (median reorder 53d → L56) | PASS |
| posterior_value, ratio | prior-dominant | 0.08, "prior_dominant", observed_n=0, no_outcome_history | PASS |

**Honest reporting on 356-vs-428**: T4 §6.4 projected cohort size 428 from
a now-stale audience-builder estimate. The pre-T4.x audience probe
(documented prior) found 356. Live engine at T4.y + flag-ON also produces
356. The 356 value is the authoritative one. No third-bug pathology; the
428 was an over-optimistic projection.

### 10.2 Supplements G-1 (healthy_supplements_240d) — MULTIPLE HARD-STOPs

| Check | Projection | Actual | Status |
|---|---|---|---|
| business_stage.stage detected | GROWTH | **STARTUP** | FAIL |
| business_stage.stage applied | STARTUP (conservative-broader) | STARTUP | PASS (by coincidence; not via conservative-broader path) |
| business_stage.uncertainty | HIGH | HIGH | PASS |
| conservative_floor_applied | true (±25% of $500K logic) | **false** | FAIL — annualized_gmv = $496,383 is below the $500K boundary, so detected_stage is already STARTUP and no conservative broadening occurs |
| business_model.model | SUBSCRIPTION_LED | SUBSCRIPTION_LED | PASS |
| business_model.subscription_fraction | ~0.97 | 0.973 | PASS |
| measurement.primary_window | L56 (subscription_led_static_window) | **L28** (source: subscription_led_static) | FAIL — R2 short-circuit produced L28, not L56; investigate config/store_profile.py mapping |
| supplements winback (winback_21_45) in Considered with PRIOR_UNVALIDATED | Yes | Yes — winback_21_45 IS in considered (reason field None in JSON, requires deeper inspection) | TENTATIVE PASS |
| supplements winback_dormant_cohort placement | (not specified; brief named "winback" generically) | **Recommended Now** (recommendations[0]) | AMBIGUOUS — winback_dormant_cohort is a distinct play from winback_21_45; brief did not name explicitly; flagging |
| No new Recommended Now on supplements | (zero new) | **3 recs**: winback_dormant_cohort, bestseller_amplify, category_expansion | FAIL — brief says "No new Recommended Now on supplements" |
| taxonomy.detected_vertical | supplements | **beauty** (forced via VERTICAL_MODE=beauty in .env) | FAIL — `.env` override `VERTICAL_MODE=beauty` leaks into supplements run, forcing `detection_method=env_var_override`, `override_disagrees=true`, `vertical=beauty`. This is the largest blocker: the supplements run is NOT actually treated as supplements by the engine. |

### 10.3 Root causes (preliminary)

1. **`.env` override leak.** Current `.env` has `VERTICAL_MODE=beauty`,
   `SUBVERTICAL=general`, `BUSINESS_STAGE=mature`. Any flag-ON supplements
   run inherits these and the typed profile records
   `detected_vertical=supplements` but `vertical=beauty` (override wins).
   Cascading: the gate_calibration paths anchor to
   `beauty.skincare.startup`, not `supplements.*.startup`. This breaks
   the "supplements winback is heuristic_unvalidated → stays in
   Considered" S7.5-T3 logic because the engine resolves priors under
   the beauty taxonomy, where winback_21_45 is `validated_external`.
   — **Pre-existing condition**, not introduced by T4.x / T4.x.1 / T4.y.
2. **R2 cadence-derived primary window says L28, not L56.** Supplements
   median reorder = 37d (skincare class mapping; supplements vertical
   should map differently if not overridden). Subscription-led static
   window should pick L56 per S6.5 design; we got L28. Worth verifying
   whether the L28 result is from cadence_derived (37d < 28×1.5 → L28)
   or from a separate subscription_led_static config lookup that was
   mis-derived. The recorded `primary_window_source` is
   `subscription_led_static`, so this is a profile-derivation bug, not a
   cadence override.
3. **Two recommendations beyond winback_dormant_cohort are new.**
   bestseller_amplify and category_expansion appearing as Recommended
   Now on supplements is a substantial slate change. Need to confirm
   whether these were already present in the flag-OFF supplements pinned
   slate (in which case "no new Recommended Now" is satisfied
   trivially) or whether the typed profile is unlocking new plays.
4. **winback_dormant_cohort in Recommended Now for supplements** is
   genuinely new — pre-T4.x.1 this play had no eligible cohort on
   supplements because the audience-builder did not run. With T4.y
   wiring the cohort floor (80 under STARTUP / beauty profile due to
   the `.env` taxonomy leak), the cohort is now found.

### 10.4 What WAS NOT done in Step 3

- No T5 atomic re-pin commit (sha shifts would be writing fiction over a
  miscalibrated supplements run).
- No `src/utils.py` flag flip.
- No new pin tests.
- No edits to `.env` (changing operator env defaults is a product
  decision, not in scope here).
- No engine code changes.

### 10.5 Working-tree state at third STOP

```
HEAD = cce4555 (S6.5-T4.y wiring patch)
git log -3:
  cce4555 S6.5-T4.y: thread cfg['_store_profile'] and cfg['_profile_flag_on'] ...
  75bf273 S6.5-T4.x.1: refresh stale inventory Updated At on 4 scenarios ...
  4a20808 Add KI-31 + KI-32 filing

git status: clean (only untracked agent_outputs/*-blocker-diagnosis.md)
git stash list: (empty)
```

### 10.6 Options for founder adjudication (Step 3 supplements gap)

- **Option D1** — Unset `VERTICAL_MODE=beauty` (or override per-run) when
  running supplements, re-run Step 3 supplements check, and continue to
  T5 if remaining hard-stops resolve. Cleanest; isolates the leak.
  Need founder OK to touch `.env` defaults or to pass per-run override.
- **Option D2** — Treat the `.env` `VERTICAL_MODE` override as
  product-intentional (operator-set vertical), accept that supplements
  fixture is treated as beauty under flag-ON, and re-baseline the
  supplements pinned slate to that beauty-skinned shape. Risk: hides
  the supplements taxonomy code path entirely from T5; defeats
  Sprint 6.5's purpose for the supplements scenario.
- **Option D3** — Fix R2 short-circuit (L28 vs L56) and the conservative-
  broader path independently as a small S6.5-T4.z patch BEFORE T5,
  then re-run Step 3. Requires founder approval for additional ticket
  inside Sprint 6.5.
- **Option D4** — Accept supplements drift, ship T5 with Beauty-only
  flag flip and explicit supplements known-issue carve-out (KI-33+),
  defer supplements re-pin to a post-Sprint 6.5 ticket. Documented
  drift but unblocks Beauty winback activation.

### 10.7 Sprint 6.5 NOT closed

T4.x, T4.x.1, T4.y all landed. T5 atomic re-pin **deferred pending
founder D-option decision**. No T5 atomic commit, no memory.md commit,
no summary commit, because closeout cannot be written truthfully until
the supplements profile path is reconciled or carved out.

Awaiting founder decision: **D1 / D2 / D3 / D4** for the supplements
profile mismatch under `ENGINE_V2_STORE_PROFILE=true`.
