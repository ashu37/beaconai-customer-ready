# BeaconAI Post-6B Restructured Implementation Plan

**Owner:** Implementation Manager
**Date:** 2026-05-09
**Horizon:** Sprints 1–4 (8 weeks) ticket-level + Phase 9 (months 3–6) outline
**Source roadmap:** [agent_outputs/beacon-ml-roadmap-reconciled-review.md](./beacon-ml-roadmap-reconciled-review.md) (Addendum 2 supersedes linear)
**Audit source:** [agent_outputs/post-6b-stop-coding-audit.md](./post-6b-stop-coding-audit.md)
**Stop-Coding-Line guarantee:** `engine_run.json` schema is frozen. No tickets below modify it. The substrate is additive (new `data/<store_id>/memory.db`, new event payloads, internal-only). Trust contract preserved end-to-end.

---

## 1. Sprint 1 (Week 1–2) — Engine Track, No Swarm Dependency

Two engineers (A, B) per Addendum 2's suggested split. Scope ruthlessly cut so the sprint actually closes.

### Sprint 1 Tickets (in order they may be picked up)

---

**Ticket B-4 / S-1 — Per-merchant directory + `store_id` resolution**
- **ID:** B-4/S-1 (bundled — same code paths)
- **Owner:** Engineer A
- **Scope:** Resolve `store_id` from basename of orders-CSV parent dir, with `STORE_ID` env override. Re-route all `data/...` reads/writes that hold tenant data to `data/<store_id>/...`. Re-key `gate_recently_run` to `(play_id, audience_definition_id, store_id)` lineage tuple; flag stays OFF, behavior unchanged. Idempotent copy-with-attribution migration of existing `data/recommended_history.json` into per-store path. Files: [src/outcome_log.py](../src/outcome_log.py) (line ~285 writer), [src/main.py](../src/main.py) (line ~860 call site), [src/guardrails.py](../src/guardrails.py) (line ~604 fatigue key), new `src/store_id.py` resolver.
- **Inputs:** Current shared `data/recommended_history.json`; current `RECENTLY_RUN_FATIGUE_ENABLED=false` default.
- **Outputs:** `data/<store_id>/recommended_history.json` per merchant; lineage-tuple keyed fatigue gate ready (still off); migration helper.
- **Acceptance test:** Two-merchant smoke (run Beauty fixture once with `STORE_ID=beauty_alpha`, once with `STORE_ID=beauty_beta`, in same checkout). Assert: zero file overlap, zero leakage across `data/<store_id>/`. M0 Beauty goldens byte-identical (fixture uses pinned `STORE_ID`). New unit test: lineage-tuple gate key contains all three components.
- **Risk:** Path resolution leaks via a missed call site. Mitigation: grep for `data/recommended_history` and `data/actions_log` and audit each. Mitigation 2: CI guard test asserts no writes outside `data/<store_id>/` for any tenant artifact.
- **Dependencies:** None. Critical path for S-2 onward.

---

**Ticket G-7 — Cross-run byte-identical determinism CI**
- **ID:** G-7
- **Owner:** Engineer A (week 1, after B-4/S-1 lands)
- **Scope:** New CI test that runs Beauty pinned fixture twice and asserts `engine_run.json` byte-identical (with timestamp/run_id fields explicitly normalized in the comparator, not the artifact). Add deterministic seeding helper `src/_determinism.py` that seeds `random` and `numpy.random` if either is imported anywhere in `src/`.
- **Inputs:** Pinned Beauty fixture (sha256 `48d61b89...` per memory).
- **Outputs:** New test `tests/test_determinism_cross_run.py`. CI green on two-run identity.
- **Acceptance test:** Test runs Beauty fixture twice in fresh tempdirs; diff of `engine_run.json` (after normalizing `run_id`, `generated_at`) is empty. Mutation test: introduce a `random.random()` call in `src/decide.py`, assert test fails.
- **Risk:** Hidden non-determinism in dict iteration / set ordering surfaces. Mitigation: this is the point — surface it now, not at S-3 acceptance.
- **Dependencies:** B-4/S-1 (path resolution must be deterministic per store first). **Strict ordering: G-7 must land before S-3 attempts its lineage-id-stability acceptance test.**

---

**Ticket B-1 — AnomalousWindow auto-registration → ABSTAIN routing**
- **ID:** B-1
- **Owner:** Engineer B
- **Scope:** Wire `AnomalousWindowCheck` into `apply_guardrails`. Populate the reserved `anomaly_flags` slot in `engine_run.json` (slot exists; payload was empty). On a load-bearing window, demote per-play to ABSTAIN_SOFT; on whole-run anomaly, ABSTAIN_HARD with `data_quality_flag = ANOMALOUS_WINDOW_DETECTED`. Files: [src/guardrails.py](../src/guardrails.py), [src/validation.py](../src/validation.py), [src/decide.py](../src/decide.py) (abstain routing seam only).
- **Inputs:** Existing reserved schema slot for `anomaly_flags`; existing `promo_anomaly_240d` synthetic fixture.
- **Outputs:** `anomaly_flags`, `n_days_observed`, `n_days_expected` populated when triggered. New ABSTAIN routing on detection.
- **Acceptance test:** Pin `promo_anomaly_240d` to slate test lane; assert today's "1 directional + 2 experiments" output flips to ABSTAIN_SOFT or ABSTAIN_HARD with populated `anomaly_flags`. Beauty pinned fixture stays byte-identical (no anomaly in healthy fixture).
- **Risk:** Over-aggressive demotion on healthy data. Mitigation: detector thresholds calibrated against Beauty healthy + Beauty edge fixtures before merge.
- **Dependencies:** None.

---

**Ticket B-3 — Hardcoded-fallback regression test**
- **ID:** B-3
- **Owner:** Engineer B
- **Scope:** Pure test, no behavior change. Grep-assert constants `{0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40}` never appear as `measurement.effect_abs` or `measurement.p_internal` on Beauty pinned slate. Apply same assertion to a synthetic supplements run (ad-hoc — full G-1 fixture not yet pinned).
- **Inputs:** Beauty pinned fixture; existing synthetic supplements CSV from `tests/fixtures/synthetic/supplement_replenishment_*`.
- **Outputs:** New test `tests/test_no_hardcoded_fallbacks_in_payload.py`.
- **Acceptance test:** Test green on current Beauty fixture; test fails if `category_expansion`/`empty_bottle`/`subscription_nudge` Phase 2 constants leak into a `measurement` block.
- **Risk:** False positives on legitimately-computed values that happen to equal `0.05`. Mitigation: scope assertion to plays in M4b's `_TARGETING_RECLASSIFY` set + `empty_bottle` only.
- **Dependencies:** None.

---

**Ticket B-5 — Berkson-class invariant test**
- **ID:** B-5
- **Owner:** Engineer B (week 2)
- **Scope:** Property test: for any candidate where audience is a behavioral subset of one window and outcome is observed in a later overlapping window, cohort must be defined on early-half counts only. Explicitly assert `subscription_nudge` and `routine_builder` ship `evidence_class=targeting` with `measurement=None`. Files: new `tests/test_berkson_invariant.py`.
- **Inputs:** Beauty pinned fixture + a Berkson-violating synthetic constructed in the test.
- **Outputs:** Regression test pinning the 554960d resolution; pin for M4b targeting reclassification.
- **Acceptance test:** Test green; injecting a measurement-emitting `subscription_nudge` candidate causes failure.
- **Risk:** Low. Mitigation: review against `project_journey_p_zero.md` resolution.
- **Dependencies:** None.

---

**Ticket B-6 — Multi-window combiner universality test**
- **ID:** B-6
- **Owner:** Engineer B (week 2)
- **Scope:** One-time test: every `measurement` block where `evidence_class=measured` on Beauty fixture must have been produced via `combine_multiwindow_statistics`, not min-p merge. Instrument [src/stats.py:334](../src/stats.py#L334) with a thread-local trace flag readable by the test. No production behavior change.
- **Inputs:** Beauty pinned fixture.
- **Outputs:** Test + thread-local trace facility.
- **Acceptance test:** Test green; if `discount_hygiene` or `bestseller_amplify` Beauty `measured` card was produced via min-p, test fails.
- **Risk:** If test fails on day 1, becomes a real B-6 fix, not a test-only ticket — re-scope with founder before merging the fix.
- **Dependencies:** None.

---

**Ticket G-2 — `empty_bottle` parser unit-coherence**
- **ID:** G-2
- **Owner:** Engineer B (week 2)
- **Scope:** Vertical-dispatched parser at [src/action_engine.py:1687](../src/action_engine.py#L1687). New `config/replenishment_sizes.yaml` with Beauty (current regex preserved) and a stub for supplements. Plus `vertical_applicable` filter at [src/decide.py:614](../src/decide.py#L614) that gates `empty_bottle` to verticals with parser coverage. Pick whichever path is smaller; recommend filter + Beauty-only parser, defer supplements parser to Sprint 4 G-3 work.
- **Inputs:** Current Beauty regex.
- **Outputs:** Parser dispatch table + filter; Beauty behavior unchanged; supplements cleanly holds via `vertical_applicable=false`. Apparel/food/home/wellness HARD REFUSE upstream at vertical resolution (B-7); they never reach play selection.
- **Acceptance test:** Beauty pinned fixture byte-identical. Synthetic supplements CSV shows `empty_bottle` held with `vertical_applicable=false`. Synthetic apparel CSV is covered by B-7 acceptance test (HARD REFUSE at engine entry, never reaches selector).
- **Risk:** Renaming Beauty parser surface breaks an internal caller. Mitigation: keep current function as Beauty-vertical implementation; only add dispatcher.
- **Dependencies:** None.

---

---

**Ticket B-7 — Hard-refuse non-supported verticals**
- **ID:** B-7 (added per Addendum 3 / vertical-scope hard-lock correction)
- **Owner:** Engineer A (week 1, after B-4/S-1 lands; ~1 day)
- **Scope:** Add a guard at engine entry in [src/main.py](../src/main.py) (orchestration boundary, BEFORE `decide()` runs). Two-line refusal:
  ```python
  if vertical_mode not in {"beauty", "supplements", "mixed"}:
      return abstain_hard(reason="VERTICAL_NOT_SUPPORTED", vertical=vertical_mode)
  ```
  Must short-circuit BEFORE priors loader, feature builder, or play registry runs (otherwise silent `mixed` fallback masks the refusal). Add comment at [src/play_registry.py:142](../src/play_registry.py#L142): "mixed = literal beauty+supplements blend, NOT an unknown-vertical fallback." Add loader-level assertion in priors loader: any `priors.yaml` block keyed on a non-supported vertical raises `ConfigError`. Merchant-facing copy in the ABSTAIN_HARD payload: "Beacon currently supports Beauty and Supplements brands. Your store profile is outside our supported scope and we won't generate recommendations rather than guess."
- **Inputs:** Existing `vertical_mode` resolution via `VERTICAL_MODE` env / config.
- **Outputs:** ABSTAIN_HARD with `data_quality_flag = VERTICAL_NOT_SUPPORTED` for any vertical outside `{beauty, supplements, mixed}`. New frozen-contract test pinning `_ALL_VERTICALS`.
- **Acceptance test:** Four fixtures:
  1. Synthetic apparel CSV → ABSTAIN_HARD, no slate, no HTML briefing rendered (or briefing renders only the refusal panel)
  2. Unit test: `vertical_mode="food_bev"` → ABSTAIN_HARD with typed flag
  3. Unit test: `vertical_mode in {"beauty", "supplements", "mixed"}` → no refusal (regression guard)
  4. Loader-level test: `priors.yaml` containing an `apparel:` block → loader raises `ConfigError`
  Plus frozen-contract test: `assert _ALL_VERTICALS == frozenset({"beauty", "supplements", "mixed"})`. Any future PR that adds a vertical breaks this test, forcing founder-level scope decision.
- **Risk:** Insertion point too deep — if guard lands inside `decide.py`, the priors loader has already silently mixed-fallback'd. Mitigation: insertion at `src/main.py` orchestration boundary is non-negotiable; PR review enforces.
- **Dependencies:** None (parallel to B-1, B-3, etc.). Beta-blocker — must land before any pilot demo touches non-Beauty merchant data.

---

### Sprint 1 deliberate slips (not in 2-week window)

- **B-2** — bundled with S-3 in Sprint 2 per Addendum 2 (avoid double contract migration).
- **S-2** — starts week 2 only if A finishes G-7 early; otherwise slips to start of Sprint 2 (no harm; substrate is in isolation).
- Anything Bucket B beyond S-1.

---

## 2. Sprint 2 (Week 3–4) — Substrate writing path

End of S-3 = **substrate schema freeze milestone for Swarm team**. Flag this explicitly in commit message and Slack-equivalent. Swarm team begins their build against frozen schemas at this point.

### Sprint 2 Tickets

**Ticket S-1.7 — Vertical resolution hardening (Sprint 2 prelude, single commit)**
- **Owner:** Engineer A or B (whoever picks up first; ~30–60 min)
- **Why this ticket exists:** Surfaced during Sprint 1 merge manual-validation (founder, 2026-05-09). Two bugs in vertical resolution were silently undermining B-7's hard-refuse contract. The ecommerce-ds-architect review confirmed they are correctness issues, not hygiene. Fixing them before S-2 means S-2 / S-3 lineage_id partitioning never has to deal with a vertical that was laundered into `mixed`.
  - Bug 1: [src/utils.py:382-386](../src/utils.py#L382-L386) `get_vertical_mode()` silently maps any unknown vertical (e.g., `apparel`, `food`, `home`) to `'mixed'`. Because `'mixed'` is in `SUPPORTED_VERTICALS`, B-7's vertical_guard never fires for these inputs — the engine runs on mixed priors instead of refusing. Defeats the B-7 hard-refuse contract.
  - Bug 2: [src/utils.py:14-27](../src/utils.py#L14-L27) manual `.env` fallback (used when `python-dotenv` is missing) does `os.environ[k] = v` unconditionally, overriding exported env vars. Already documented as a known caveat in repo `memory.md:912`. Affects local-dev-only but compounds Bug 1 by making the laundering hard to detect during testing.
- **Scope:**
  - `get_vertical_mode()`: pass through unknown verticals as-is (or raise `ConfigError`) instead of mapping to `'mixed'`. Let B-7's vertical_guard be the single point of refusal.
  - Manual `.env` fallback: change assignment to `setdefault` semantics so exported env vars win.
  - Add a regression test asserting `get_vertical_mode()` does NOT return `'mixed'` for inputs outside `{beauty, supplements, mixed}`.
  - Add a regression test asserting `VERTICAL_MODE=apparel python -m src.main ...` triggers B-7 ABSTAIN_HARD path (end-to-end, not just guard unit test).
- **Inputs:** None.
- **Outputs:** B-7's hard-refuse contract is actually enforced for unsupported verticals. Local-dev env-var overrides work as documented.
- **Acceptance test:** Two new tests green; full suite green; M0 Beauty pinned fixture byte-identical (Beauty is in supported set so behavior unchanged).
- **Risk:** Any code path that *relied* on the `'mixed'` laundering (e.g., a test that sets `VERTICAL_MODE=apparel` expecting the engine to silently run on mixed priors) breaks. Mitigation: grep for `VERTICAL_MODE=apparel|food|home` in tests/; expected count is zero.
- **Dependencies:** None. Independent of S-2.
- **Out of scope (deferred):** Per-merchant `store_profile.vertical` resolver (architectural recommendation; folds into S-2's per-merchant substrate work, NOT this ticket). M10 collapse of legacy `VERTICAL_MODE` env paths (Phase 9).

---

**Ticket S-2 — SQLite memory.db + events table + lineage_id helper**
- **Owner:** Engineer A
- **Scope:** New module `src/memory/store.py` exposing `open_memory(store_id) -> MemoryStore` with `append_event(...)`. WAL-mode SQLite, `PRAGMA user_version` migrations. New `src/memory/lineage.py` with `compute_lineage_id(store_id, play_id, audience_definition_id, audience_definition_version) -> sha1 hex`. New `tools/inspect_memory.py` CLI. **No engine code changes** — substrate stands alone.
- **Inputs:** Per-store dirs from S-1.
- **Outputs:** `data/<store_id>/memory.db` created on first call; CLI for hand-inspection.
- **Acceptance test:** Append 1000 events, query by lineage_id, assert insertion order. Concurrent-write test (2 processes × 100 events) → 200 distinct event_ids, zero corruption. Migration test idempotent re-run.
- **Risk:** SQLite locking on concurrent writes. Mitigation: WAL mode + `busy_timeout=5000`.
- **Dependencies:** B-4/S-1.

---

**Ticket S-3 — Engine writes `recommendation_emitted` + `recommendation_considered` (BUNDLES B-2)**
- **Owner:** Engineer A (lead) + Engineer B (B-2 payload work)
- **Scope:** At end of `decide()`, after `engine_run.json` is written, append one `recommendation_emitted` event per `PlayCard` in `recommendations` and `recommended_experiments`, one `recommendation_considered` event per `RejectedPlay`. Payload includes internal Measurement diagnostics, **typed `evidence_snapshot` (B-2 surface b)**, pre-registered expectation block (`expected_direction`, `min_interesting_effect_size`, `expected_observation_window_days` — audit L-E), snapshot path. Reason-code fan-out (B-2 surface a): extend `_candidate_reason_code` to emit `AUDIENCE_TOO_SMALL`, `COLD_START`, `INVENTORY_BLOCKED`, `MATERIALITY_BELOW_FLOOR`, `DATA_QUALITY` instead of collapsing to `NO_MEASURED_SIGNAL`. Engine still writes legacy `recommended_history.json` in parallel for one phase. Files: [src/decide.py](../src/decide.py) (lines ~515, ~622), [src/main.py](../src/main.py) (call site ~860), [src/outcome_log.py](../src/outcome_log.py). **Single-writer guard:** grep test asserting only this module writes `recommendation_emitted` / `recommendation_considered` event types.
- **Inputs:** S-2 substrate live; G-7 determinism CI green; B-4/S-1 lineage tuple available.
- **Outputs:** Events flowing into `data/<store_id>/memory.db`. Frozen contract for `recommendation_*` events ready for Swarm team consumption.
- **Acceptance test:** Run Beauty fixture twice with 30 days of synthetic delta. Assert: (a) `lineage_id` for `first_to_second_purchase` byte-identical across runs (this satisfies audit L-B as a regression test), (b) two `recommendation_emitted` rows with same lineage_id and different run_id, (c) snapshot files referenced by event payload exist on disk, (d) all 5 reason codes emitted in at least one fixture, (e) `engine_run.json` byte-identical to pre-S-3 (substrate is purely additive). Single-writer grep test green.
- **Risk:** B-2 reason-code fan-out changes which RejectedPlays appear in Considered. Mitigation: add the 5 codes additively; only emit a non-`NO_MEASURED_SIGNAL` code when the candidate produced one of the 4 specific signals; default unchanged.
- **Dependencies:** S-2, G-7, B-4/S-1.
- **Schema-freeze milestone:** end of S-3, `recommendation_emitted` and `recommendation_considered` payload schemas pinned at `event_version=1`. Hand to Swarm team.

---

**Sprint 1 carryover candidates:** B-5, B-6, G-2 if any slipped from week 2.

---

## 3. Sprint 3 (Week 5–6) — Substrate read-views + Swarm contract hand-off

**Hand-off milestone:** end of S-6 = full substrate API frozen. Swarm team has manual import path to test against. Approval queue work begins on Swarm side.

### Sprint 3 Tickets

**Ticket S-4 — Immutable snapshot discipline + run_id contract**
- **Owner:** Engineer A
- **Scope:** Move `engine_run.json` write target from mutable `receipts/engine_run.json` to immutable `data/<store_id>/runs/<run_id>.json`. Keep mutable `receipts/engine_run.json` as a copy of latest (backward compat for current Agent Swarm consumers — frozen contract). Add `snapshot_sha256` field to `recommendation_emitted` payload at write time. Files: [src/main.py](../src/main.py), snapshot writer module.
- **Acceptance test:** Run engine 5 times → 5 distinct snapshot files; each file's sha256 matches event log value. Mutation test: hand-edit a snapshot, rerun verification, assert mismatch detected. `receipts/engine_run.json` matches latest run byte-for-byte.
- **Risk:** Swarm consumers reading `receipts/engine_run.json` see no change. Mitigation: backward-compat copy. Document in `docs/memory_substrate.md`.
- **Dependencies:** S-3.

---

**Ticket S-5 — Read-views + calibration_stub rewire**
- **Owner:** Engineer A
- **Scope:** New `src/memory/views.sql` with `v_lineage_timeline`, `v_calibration_state`, `v_open_recommendations` plus a fatigue-supporting `v_lineage_recent_emissions(lineage_id, count_in_last_28d)`. Python helpers in `src/memory/views.py`. Rewire [src/calibration_stub.py:37](../src/calibration_stub.py#L37) `load_realization_factors` to call `v_calibration_state` and project into existing `{prior_overrides, evidence_thresholds, materiality_overrides}` dict. With zero `calibration_updated` events present, view returns empty → stub returns identical empty-shape dict to today. Document contract in `docs/memory_substrate.md`.
- **Acceptance test:** Seed fixture (10 lineages, 30 events); each view returns expected shape. Forbidden-write test: attempt `INSERT` into a view, assert SQLite rejects. M0 Beauty goldens byte-identical (calibration stub returns same empty dict).
- **Risk:** Calibration stub callers depend on unspecified key ordering. Mitigation: stub still returns same dict shape with zero entries until `calibration_updated` events arrive.
- **Dependencies:** S-3.

---

**Ticket S-6 — Manual `campaign_sent` import path + Swarm contract**
- **Owner:** Engineer A
- **Scope:** New `tools/import_campaign_sent.py` CLI. Reads `data/<store_id>/inbox/campaigns/*.json`, validates against documented schema, appends `campaign_sent` events. Define `outcome_observed` JSON schema in `docs/memory_substrate.md` but do NOT implement importer (deferred to Phase 9 with `compute_realized_outcome`). Engine never calls this tool — file boundary is the discipline. **This is the Swarm integration contract** — high schema review bar.
- **Acceptance test:** Two-run integration test: T0 produces 3 `recommendation_emitted` events; manual import drops `campaign_sent` JSON for one of them; T1's `v_lineage_timeline` for that lineage_id returns `[recommendation_emitted, campaign_sent]` in order; T1 engine still runs identically (does NOT read `campaign_sent` events). Single-writer grep: only `tools/import_campaign_sent.py` writes `campaign_sent` event_type.
- **Risk:** Schema lock-in. Mitigation: `event_version=1`, additive-only future evolution rule documented and CI-enforced (forbid field removal).
- **Dependencies:** S-3, S-5.

---

**Spike (not a full ticket): I-1 affinity emitter prototype**
- **Owner:** Engineer B (week 5–6, parallel to A's S-4/S-5/S-6)
- **Scope:** Feature branch only. FP-growth + ALS over Beauty fixture line items. Goal is to prove the candidate-registry seam admits a model-derived candidate at `evidence_class=targeting` with no contract change. NOT to ship to merchants. Output: a memo at `agent_outputs/i1-spike-findings.md` describing seam fit, perf, data sufficiency observed on Beauty fixture.
- **Acceptance:** Memo + working prototype branch. No merge to main in Sprint 3.
- **Risk:** Spike scope expands. Mitigation: time-box at 4 days; if seam doesn't fit cleanly, halt and report.

---

## 4. Sprint 4 (Week 7–8) — Substrate stabilization + supplements hardening + mixed semantic formalization

### Sprint 4 Tickets

**Ticket G-1 — Pin synthetic supplements slate fixture**
- **Owner:** Engineer A
- **Scope:** Replicate `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` process for `healthy_supplements_240d`. Pin sha256. Capture every breakage (parser, priors, anomaly false positive, abstain spurious, "mixed" fallback). Each finding becomes a Sprint 5+ ticket. **This converts the supplements support story from speculation into a concrete bug list.**
- **Acceptance test:** New pinned fixture in `tests/fixtures/synthetic_slate/healthy_supplements_240d_*`. Slate runs end-to-end without crash. Bug list filed as separate tickets — that IS the deliverable.
- **Risk:** Supplements run reveals a deep contract problem requiring frozen-schema work. Mitigation: such findings escalate to founder before scoping; do not patch under the freeze.
- **Dependencies:** G-2 (vertical_applicable filter must be live so supplements doesn't crash on `empty_bottle`).

---

**Ticket G-3 — Vertical priors expansion (start)**
- **Owner:** Engineer B
- **Scope:** Begin in [config/priors.yaml](../config/priors.yaml). Add at least one `observational` baseline conversion-rate band per play for supplements (no invented causal priors). Formalize `mixed` semantics: when `vertical_mode=="mixed"`, the loaded prior block must derive from the beauty + supplements blocks (or be explicitly authored as a mixed block — never silently default). [src/play_registry.py:142](../src/play_registry.py#L142) `_ALL_VERTICALS` stays at `frozenset({"beauty", "supplements", "mixed"})` — frozen-contract test in B-7 enforces this. **Apparel, food/bev, home, wellness are out of scope permanently — refused by B-7, NOT deferred.**
- **Acceptance test:** G-1 supplements fixture's slate now uses supplement-keyed priors instead of `mixed` fallback; `evidence_class=measured` may now graduate where appropriate.
- **Risk:** Priors authoring without citation drifts to invented numbers. Mitigation: each prior carries `source` field; PR review enforces citation presence.
- **Dependencies:** G-1.

---

**Ticket G-4 — Reclassify `subscription_nudge` + `routine_builder` permanently as targeting**
- **Owner:** Engineer B
- **Scope:** Drop `measurement` emission for both plays in [src/action_engine.py:2966-3186](../src/action_engine.py#L2966). Remove the hardcoded `effect_abs=0.05` / `effect_abs=0.08` constants. M4b's flag-gated `_TARGETING_RECLASSIFY` becomes the structural default for these two. Per DS recommendation (option a) over redesign.
- **Acceptance test:** Beauty fixture: both plays now ship `evidence_class=targeting`, `measurement=None`. B-3 hardcoded-fallback test still green. B-5 Berkson invariant test still green.
- **Risk:** Goldens shift. Mitigation: this IS the intended behavior change — re-pin Beauty fixture in same commit; all three flag defaults stay OFF so legacy path unchanged.
- **Dependencies:** B-3, B-5 (both must be passing first to detect any regression).

---

**Ticket I-1 — Affinity emitter ships at `targeting` class**
- **Owner:** Engineer B (after G-4)
- **Scope:** Promote Sprint 3 spike branch to a real candidate emitter behind the `bestseller_amplify` Recommended Experiment slot. `evidence_class=targeting`, `would_be_measured_by=REPEAT_PURCHASE_IN_30D`. No projections. The audience itself ("1,247 customers who bought SKU-A but not SKU-B; lift ratio 3.2x base co-occurrence") IS the artifact. No model name surfaces in slate.
- **Acceptance test:** Beauty fixture: `bestseller_amplify` Recommended Experiment now contains affinity-derived audience. Forbidden-token sweep still green. Role-uniqueness invariant still green. Substrate event `recommendation_emitted` carries `source=affinity_v1` in internal `evidence_snapshot` only.
- **Risk:** The "data-backed audience" framing leaks model claims into copy. Mitigation: scoped forbidden-token sweep on the experiment card; copy stays under Swarm control.
- **Dependencies:** S-3 (substrate must be live so calibration accumulates), G-4 (subscription_nudge/routine_builder out of the way), I-1 spike memo.

---

## 5. Phase 9 readiness checkpoint (end of Sprint 4)

Phase 9 = `compute_realized_outcome` (L-C) + calibration consumer (L-D #1). Cannot start until **outcome events exist** in the substrate.

### Go/no-go gate (all must be true)

1. **S-3 through S-6 landed and stable for ≥2 weeks.** Substrate writing path proven on Beauty pinned fixture in CI on every commit.
2. **At least one of the following is true:**
   - **(a)** Swarm Monitor Agent is writing `outcome_observed` events into `data/<store_id>/memory.db` for at least one pilot merchant for ≥30 days, OR
   - **(b)** Manual import path (`tools/import_outcome_observed.py`, sister to `import_campaign_sent.py`) is exercised in a two-run integration test that simulates `outcome_observed` arrival.
3. **Beta blockers B-1, B-3, B-5, B-6 green in CI.** No outstanding Phase 6B Beta blockers.
4. **G-1 supplements fixture pinned + bug list triaged.** At least one pilot merchant on supplements is plausible.
5. **G-7 determinism CI green for ≥30 days** with no flaky failures. Calibration loop is unmeasurable on a non-deterministic engine.
6. **`audience_definition_version` policy decided** by founder (audit open question). L-F schema cannot ship without this.
7. **`would_be_measured_by` enum cap acknowledged.** Explicit decision: only `REPEAT_PURCHASE_IN_30D` is locally honest; calibration ladder caps at this enum until external integrations land.

**Go/no-go owner:** Implementation Manager + founder review at end of Sprint 4. If gate (2) fails on both branches — Swarm slip + manual path not exercised — Phase 9 slips by one sprint and Beacon team backfills the manual `outcome_observed` import path so the calibration consumer has something to consume.

---

## 6. Phase 9 plan (Months 3–6) — outline only

Sequence + acceptance bars only. Ticket-level plan generated at start of Phase 9 once Sprint 4 actuals are in.

**Phase 9 sequence:**

1. **L-C `compute_realized_outcome(card, next_run_csv)` for `REPEAT_PURCHASE_IN_30D`.** Pure function. From a `recommendation_emitted` event (with audience pinned at recommendation time) and a next-run CSV, count second-purchase events within 30 days. Other enums (`EMAIL_ATTRIBUTED_REVENUE_IN_7D`, `INCREMENTAL_ORDERS_IN_14D`) document `outcome_status = REQUIRES_INTEGRATION` / `REQUIRES_HOLDOUT`. **Acceptance:** two-run integration test (audit L-G) — T0 emits, T1 reads T0's recommendation_emitted, computes the realized rate, calls outcome_observed-import path, view returns row.
2. **L-D #1 calibration consumer (trailing-window mean per `(play_id, vertical, store_id)`).** Reads `outcome_observed`, emits `calibration_updated`. Once K=3 outcomes accumulate per partition, override prior baseline with observed mean. **Acceptance:** synthetic test seeds 3 outcomes, asserts `v_calibration_state` returns updated baseline; engine reads it via S-5 rewired `calibration_stub`; subsequent slate uses updated baseline.
3. **I-2 replenishment-timing emitter.** Discrete-time survival on per-customer hazard. Publishes `directional` with `would_be_measured_by=REPEAT_PURCHASE_IN_30D`. Scoped narrowly: "profile property the merchant uses." **Acceptance:** Beauty fixture surfaces a per-audience expected-reorder-date with internal-only CI; forbidden-token sweep green; role-uniqueness invariant green.
4. **(Optional, founder call) L-H Klaviyo/Shopify outcome ingestion seam contract.** Engine reads `data/<store_id>/campaign_outcomes.json` if present; never writes. Documented contract; no integration code in engine.

**Phase 9 hard bar:** no model in this phase is allowed to surface a merchant-facing prediction. Affinity audience (I-1, already shipped) and replenishment date (I-2) are the visible artifacts. Calibration drift is the receipts surface.

**What does NOT ship in Phase 9:** uplift (I-4), churn (I-3), discount elasticity (I-5), LTV (I-6), bundle combinatorial optimization. All deferred to Year 2.

---

## 7. Risk register

Top 5 ranked impact × likelihood.

| # | Risk | Impact | Likelihood | Mitigation | Owner |
|---|---|---|---|---|---|
| 1 | **Schema-freeze risk on `recommendation_emitted` / `recommendation_considered`** — Swarm team builds against pinned schema; a Beacon-side mid-sprint payload addition that turns out to be field-removal-shaped breaks Swarm | High | Medium | Additive-only versioning enforced via CI grep test on `src/memory/events.py` event payload schemas; PR template checklist forces `event_version++` reasoning; schemas pinned in `docs/memory_substrate.md` with diff review | Engineer A + Implementation Manager |
| 2 | **Lineage-id stability risk** — if `audience.id` for `first_to_second_purchase` churns between identical runs, every memory claim is wrong; entire Phase 9 calibration sits on sand | Critical | Medium | S-3 acceptance test (a) IS this regression test, and is gated by G-7 determinism CI; if test fails on day 1, halt S-4 and treat L-B as a separate spike before continuing | Engineer A |
| 3 | **Swarm-slip risk** — Swarm team is 2–3 weeks behind; if they slip 6+ weeks, Phase 9 calibration consumer has no `outcome_observed` events to consume | High | Medium | Manual import path (S-6 + a sibling `import_outcome_observed.py` in Phase 9) is the **permanent backstop**; substrate definition-of-done is "manual import passes," NOT "Swarm in production"; Phase 9 readiness gate explicitly accepts manual-path branch (b) | Implementation Manager |
| 4 | **B-2 reason-code fan-out shifts Considered membership unintentionally** — changes which cards appear in Considered on Beauty fixture, breaking goldens or pilot expectations | Medium | High | Reason codes added additively; the 5 new codes only fire when their specific signal is present; default `NO_MEASURED_SIGNAL` retained; re-pin goldens in S-3 commit and document the diff | Engineer B |
| 5 | **G-1 supplements fixture surfaces a frozen-contract problem** — non-Beauty run reveals the contract has a Beauty-shaped assumption baked in | High | Low | If found, escalate to founder before patching; do NOT amend frozen schema without explicit founder + DS sign-off; alternate path is `vertical_applicable` gating to keep Beauty contract pure | Engineer A + founder |

**Honorable mention (not top 5 but tracked):** SQLite concurrent-write corruption under multi-process load, `store_id` resolution ambiguity when running locally without `STORE_ID` env, hidden non-determinism surfacing late in S-3 acceptance.

---

## 8. Cross-track coupling enforcement

Three strict orderings from Addendum 2. Concrete enforcement, not aspirational.

**Ordering 1: G-7 must land before S-3 attempts lineage-id stability acceptance.**
- *Enforcement:* CI test `tests/test_determinism_cross_run.py` (created in G-7) is a required check on the `s-3` PR. PR template for S-3 includes a "G-7 CI green for last 5 commits on main" checkbox. CODEOWNERS routes any change touching `src/decide.py` outputs through Implementation Manager review until S-3 lands.

**Ordering 2: B-2 bundled with S-3, NOT shipped standalone.**
- *Enforcement:* B-2 has no separate ticket in the tracker; it lives only as scope inside S-3's description. If an engineer attempts to open a B-2-only PR, the labeled ticket reference forces redirect. Code-review checklist for S-3 explicitly lists "B-2 reason-code fan-out + typed evidence_snapshot included."

**Ordering 3: B-4 = S-1 (one ticket, two blocker IDs).**
- *Enforcement:* Single PR, single commit message references both IDs. The ticket title literally reads `B-4/S-1`. Any future doc/audit referring to B-4 or S-1 separately is a bug — flag and reconcile to the bundled form.

**Additionally:**
- **No event-type writer added outside its single owner** — CI grep test in `tests/test_single_writer_per_event_type.py` (lands with S-3) asserts:
  - `recommendation_emitted` written only from `src/decide.py` (or its event-emit helper)
  - `recommendation_considered` written only from `src/decide.py`
  - `campaign_sent` written only from `tools/import_campaign_sent.py` (and Swarm Deploy Agent path when integrated)
  - `outcome_observed` written only from monitor / manual import path
  - `calibration_updated` written only from calibration consumer (Phase 9)
- **`engine_run.json` schema freeze enforcement:** existing M0 byte-identical golden test on Beauty pinned fixture is the freeze enforcement. Any S-3/S-4 change that perturbs the JSON fails CI, no exceptions.

---

## 9. Definition of Done per phase

**Phase 7 — Lineage Memory Substrate complete when ALL of:**
- [ ] B-4/S-1 merged; per-merchant directory live; lineage-tuple fatigue key in place (flag still off)
- [ ] G-7 determinism CI green on main for ≥30 days
- [ ] B-1, B-3, B-5, B-6 merged; CI green
- [ ] G-2 vertical_applicable filter live
- [ ] S-2 SQLite substrate live; `data/<store_id>/memory.db` created on engine run
- [ ] S-3 engine writes `recommendation_emitted` + `recommendation_considered` events; B-2 reason-code fan-out + typed evidence_snapshot bundled; `event_version=1` schema pinned in `docs/memory_substrate.md`
- [ ] S-4 immutable snapshots + `snapshot_sha256` in event payload
- [ ] S-5 read views + `calibration_stub` rewired (zero behavior change with empty `calibration_updated`)
- [ ] S-6 manual `campaign_sent` import path + two-run integration test green
- [ ] Single-writer-per-event-type CI test green
- [ ] G-1 supplements fixture pinned (even if bug list opens new tickets)
- [ ] G-4 subscription_nudge + routine_builder permanently classified as targeting
- [ ] I-1 affinity emitter live at `evidence_class=targeting` behind `bestseller_amplify`
- [ ] M0 Beauty pinned fixture byte-identical (substrate is purely additive)

**Phase 8 — Swarm-integrated complete when ALL of:**
- [ ] Swarm Deploy Agent writes `campaign_sent` events into substrate for ≥1 pilot merchant for ≥30 days
- [ ] Approval queue UI live (Swarm-track responsibility, not engine team)
- [ ] Beacon engine has consumed zero new responsibilities — engine still writes only `recommendation_*` event types
- [ ] At least 1 paying Beauty merchant on full Brief+Swarm bundle
- [ ] `v_lineage_timeline` queries return non-empty `[recommendation_emitted, campaign_sent, ...]` chains for real merchant data
- [ ] No frozen-contract violations from Swarm consumption

**Phase 9 — Calibration loop closed when ALL of:**
- [ ] L-C `compute_realized_outcome(REPEAT_PURCHASE_IN_30D)` shipped; pure function with `computed_by_function_version` field in `outcome_observed` payload
- [ ] L-D #1 calibration consumer shipped; `calibration_updated` events written when K=3 outcomes accumulate per `(play_id, vertical, store_id)`
- [ ] Engine consumes `v_calibration_state` and overrides priors when present
- [ ] Two-run integration test (audit L-G) green: T0 → T1 with synthetic 30-day delta produces realized outcome row + calibration update
- [ ] At least 1 `(play_id, vertical, store_id)` partition has K≥3 real outcome rows on real merchant data
- [ ] Receipts surface ("we said X in March, observed Y in April") rendered by Swarm from `v_lineage_timeline` join with `outcome_observed`
- [ ] I-2 replenishment timing emitter live at `evidence_class=directional`
- [ ] Forbidden-token sweep still green; no "predicted lift" / model names leaked to slate

---

## 10. What I explicitly REFUSE to plan

These items appear in roadmap discussion but are NOT going on the next-6-months implementation track. Listed with reason so the founder knows what is deliberately deferred.

- **I-3 subscription churn (Cox PH / DeepSurv).** Deferred. Gated on Recharge/Bold/Skio integration; until that lands, the model is `REQUIRES_INTEGRATION` and shipping it would violate the trust contract.
- **I-4 uplift / T-learner.** Deferred to Year 2. Premature until K outcome rows accumulate across multiple `(play_id, vertical, store_id)` partitions; shipping with wide CIs forces hiding them, which violates trust contract.
- **I-5 discount elasticity (double-ML).** Deferred. Defensible eventually but requires uplift framework (I-4) and L-D #2 Bayesian calibration first.
- **I-6 BG/NBD + Gamma-Gamma LTV.** Refused for Year 1. Model-data mismatch on subscription brands; $1–2M brands won't clear the 1,000-active-customer N threshold; cross-merchant pooling has antitrust/privacy implications not yet scoped.
- **I-9 hierarchical / cross-merchant pooling.** Refused without legal + privacy review. Single-merchant only in Year 1, per Addendum 2 founder default #15.
- **Klaviyo publish automation from engine side.** Refused. This is Swarm-track scope; engine emits typed payload only. Engine team does not touch Klaviyo APIs.
- **Auto-pilot graduation.** Refused for Year 1. Year 2 work, per play type, gated on N≥20 substrate observations + CI-bounded outcomes.
- **M10 V1 deletion.** Refused for the next 4 sprints. Explicitly gated by audit §4's 11-prerequisite checklist; at minimum needs G-7, B-3, 30-day Beauty stability, supplements pinned fixture, three V2 flags defaulted ON, AND Agent Swarm shipping a production cycle. None of these is true at end of Sprint 4. Revisit after Phase 9.
- **G-5 FDR family scope documentation + G-6 overlap-window leakage fix.** Deferred past Sprint 4. Real defensibility holes (G-6 is "first thing an external statistical reviewer catches"), but neither blocks Beta or Phase 9 substrate. Slot in Phase 10 alongside vertical expansion #2.
- **G-8 cannibalization-overlap key existence test.** Deferred to Phase 8 alongside Swarm-integrated work; harmless until candidate count grows.
- **L-D options #2 (Bayesian) and #3 (hierarchical) calibration.** Refused for Phase 9. L-D #1 trailing-window mean is the honest first version; promote only when row count justifies complexity.
- **`empty_bottle` supplements parser** (full G-2 fix, not the gating filter). Deferred to Sprint 5+ following G-1 bug-list triage.
- **Apparel / food / wellness / home priors and fixtures.** **REFUSED PERMANENTLY** (not deferred). Engine scope hard-locked at `{beauty, supplements, mixed}` per [src/play_registry.py:142](../src/play_registry.py#L142). Non-supported merchants are refused at engine entry via B-7, not absorbed via `mixed` fallback. No commercial-demand path reopens this — a merchant on a non-supported vertical is a "wrong product, not wrong sprint" refusal.
- **Auto-detection of vertical from product catalog as a way to onboard non-supported merchants.** Refused. Vertical is a gate, not an inference target.
- **Pricing tier raise to $1.5K/$3K/$8K.** Refused for engine-team scope. PM/founder call, not implementation. Substrate enables it; doesn't trigger it.

---

**Bottom line for the founder:** Monday morning, Engineer A starts B-4/S-1 (per-merchant scoping) → B-7 (vertical hard-refuse) → G-7 (determinism CI); Engineer B starts B-1 (anomaly auto-register). End of Sprint 1 (week 2), all 6 Bucket A Beta blockers are landed (B-1, B-3, B-5, B-6, B-7) plus per-merchant scoping plus determinism CI plus `empty_bottle` parser dispatch. End of Sprint 2 (week 4), substrate writes events and `recommendation_*` schemas freeze for the Swarm team. End of Sprint 4 (week 8), supplements is pinned, `mixed` semantics formalized, affinity ships at `targeting`, and Phase 9 readiness gate is evaluated. Trust contract preserved. `engine_run.json` byte-identical on Beauty throughout. Manual import path is the permanent backstop against any Swarm-team slip. Vertical scope hard-locked at {beauty, supplements, mixed} via B-7; non-supported merchants refused at engine entry, never absorbed.

---

## File References

- [agent_outputs/beacon-ml-roadmap-reconciled-review.md](./beacon-ml-roadmap-reconciled-review.md)
- [agent_outputs/post-6b-stop-coding-audit.md](./post-6b-stop-coding-audit.md)
- [CLAUDE.md](../CLAUDE.md)
- [src/decide.py](../src/decide.py)
- [src/main.py](../src/main.py)
- [src/outcome_log.py](../src/outcome_log.py)
- [src/guardrails.py](../src/guardrails.py)
- [src/calibration_stub.py](../src/calibration_stub.py)
- [src/action_engine.py](../src/action_engine.py)
- [src/stats.py](../src/stats.py)
- [src/play_registry.py](../src/play_registry.py)
- [src/utils.py](../src/utils.py)
- [src/features.py](../src/features.py)
- [src/engine_run_adapter.py](../src/engine_run_adapter.py)
- [src/validation.py](../src/validation.py)
- [config/priors.yaml](../config/priors.yaml)
- [tests/fixtures/synthetic_slate/](../tests/fixtures/synthetic_slate/) (Beauty pinned, supplements forthcoming via G-1)

**New files created across the plan:**
- `src/memory/store.py`, `src/memory/lineage.py`, `src/memory/views.sql`, `src/memory/views.py`
- `src/store_id.py`, `src/_determinism.py`
- `tools/inspect_memory.py`, `tools/import_campaign_sent.py`
- `docs/memory_substrate.md`
- `config/replenishment_sizes.yaml`

---

# ADDENDUM: Founder Decisions Recorded (2026-05-09)

The following decisions resolve open items from the substrate addendum (`beacon-ml-roadmap-reconciled-review.md` Addendum 1) and gaps surfaced during plan review. These are NOT subject to renegotiation by implementing agents — they are constraints for the Sprint 1–4 build.

## D-1. `audience_definition_version` policy (BLOCKING for S-3)

**Decision:** Accepted default. Any change to the SQL/Python logic that produces an audience definition MUST increment `audience_definition_version` by 1. Old lineages remain readable but fork to a new `lineage_id` by construction.

**Engineering implications:**
- The integer `audience_definition_version` MUST exist as a field in the `engine_run.json` audience block
- The integer MUST be passed into `compute_lineage_id(store_id, play_id, audience_definition_id, audience_definition_version)` in S-2
- Refactor agents touching audience builders MUST bump the version in the same commit; PR template checklist includes this item
- No "cosmetic change" carve-out — any logic-level change increments the version

**Resolves:** Phase 9 readiness gate item #6 (now closed at Sprint 1 start, not deferred).

## D-2. Retention policy

**Decision:** Keep everything forever. Do NOT build TTLs, auto-deletion crons, or archival tiers.

**Engineering implications:**
- No `expires_at` or `archived_at` fields on event rows
- No background cleanup jobs
- SQLite `memory.db` grows monotonically; revisit if/when disk becomes a real constraint (years out)

## D-3. Merchant deletion semantics

**Decision:** Full wipe only. No partial-delete logic. SQLite architecture must support a drop/delete-database equivalent (single rm/delete operation per store).

**Engineering implications:**
- Per-store SQLite file at `data/<store_id>/memory.db` is the deletion unit
- Per-store directory `data/<store_id>/` is the export/wipe unit
- Do NOT implement row-level deletion APIs, soft-delete flags, or partial-history redaction
- A future "wipe my data" CLI is `rm -rf data/<store_id>/`; document this in `docs/memory_substrate.md`

## D-4. Export

**Decision:** Full per-store JSON export from Day 1.

**Engineering implications:**
- Bundle a `tools/export_store.py` CLI alongside `tools/inspect_memory.py` in S-2 or S-3
- Output: single JSON file per store containing all events + snapshot index + recommended_history mirror
- No selective field filtering, no PII redaction toggle (everything-or-nothing)
- Acceptance: round-trip test (export → fresh import script → byte-identical event log)

## D-5. Ingestion

**Decision:** Manual JSON import ONLY for v1. Do NOT build Klaviyo API pollers, OAuth flows, or webhook receivers in Beacon-track scope.

**Engineering implications:**
- S-6 ships exactly as specified: `tools/import_campaign_sent.py` reads from `data/<store_id>/inbox/campaigns/*.json`
- The sister `tools/import_outcome_observed.py` (Phase 9) follows the same shape
- Klaviyo integration is Swarm-track scope, not Beacon-track scope
- Do NOT scaffold a Klaviyo SDK dependency in `requirements.txt`

## D-6. ML models EXPLICITLY BANNED for the planning horizon

The following models must NOT be scaffolded, stubbed, or have priors written for them in any Sprint 1–4 work:

- Quiz contextual bandits (LinUCB / Thompson Sampling)
- VIP / loyalty tier optimization
- New product launch targeting
- Bundle combinatorial optimization
- Stockout prediction / inventory-driven marketing
- Cause / limited-edition → core conversion

**Engineering implications:**
- No empty modules, placeholder classes, or `TODO: ML model here` comments for these
- No prior entries in `config/priors.yaml` for these play types
- No `play_id` registrations in `play_registry.py` for these
- If a candidate emitter for one of these accidentally appears, fail CI

**Re-additions:** any of the above can only re-enter the roadmap via explicit founder approval + a new addendum to this plan.

## D-7. I-1 affinity audience-builder spec

**Decision:** Leave deferred to the Sprint 3 spike memo (`agent_outputs/i1-spike-findings.md`). Engineer B owns the spec; ships with the spike output for review before Sprint 4 promotion.

---

## D-8. Vertical scope hard-lock (BLOCKING for B-7, S-2, S-3)

**Decision:** Beacon's vertical scope is permanently locked to `{beauty, supplements, mixed}` where `mixed` = the literal beauty+supplements blend (NOT a fallback for unknown verticals). Apparel, food/bev, home goods, and wellness are **out of scope permanently** — refused at engine entry, never absorbed by `mixed`.

**Engineering implications:**
- B-7 ticket (added to Sprint 1 above) implements the hard refuse at engine entry
- [src/play_registry.py:142](../src/play_registry.py#L142) `_ALL_VERTICALS = frozenset({"beauty", "supplements", "mixed"})` is the canonical scope; frozen-contract test pins it
- `lineage_id` partition cardinality is now bounded at 3 — calibration partition state space is small by design
- Cross-merchant pooling (when/if it lands in Year 2) is within {beauty, supplements} only — narrower scope makes hierarchical pooling more defensible, not less
- Priors loader rejects any `priors.yaml` block keyed on a non-supported vertical (`ConfigError`)
- Sprint 4 G-3 work is **supplements-only hardening + mixed semantic formalization**, NOT expansion to other verticals

**Commercial implications:**
- TAM: ~15k–25k US/EU addressable Beauty+Supplements merchants; realistic ARR ceiling **$10M–$40M** with full Brief+Swarm bundle expansion. Bootstrap/Series-A friendly outcome, NOT venture-decacorn.
- Pricing: shift UP to **$1.5K → $3K → $5K → $12K** (kill the $800 tier; narrower TAM justifies higher prices).
- Persona: **"The AI growth team for consumables DTC."** Strength through specificity.
- Sales gate-1: *"Is your store primarily Beauty, Supplements, or both?"* If no → instant disqualify.
- "Vertical expansion" is **NOT a future revenue lever** — it's been removed from the roadmap. Any investor narrative implying horizontal applicability is rejected.

**Resolves:** the framing error in the prior reconciled review and implementation plan that treated `mixed` as a fallback and apparel/food/home/wellness as deferred-but-eventual. See Addendum 3 in `beacon-ml-roadmap-reconciled-review.md` for full context.

---

## Gap-closure summary

| Gap surfaced in plan review | Decision | Resolution |
|---|---|---|
| `audience_definition_version` policy undecided | D-1 above | Closed; constraint baked into S-2/S-3 |
| 17 founder defaults silently accepted | D-2/D-3/D-4/D-5 above | 4 most engineering-load-bearing now explicit |
| 6 deferred research-doc plays not in REFUSED list | D-6 above | All 6 explicitly banned with CI enforcement |
| I-1 audience-builder unspec'd | D-7 above | Correctly deferred to spike memo |
| Vertical scope ambiguity (treated apparel/food/home/wellness as deferred-but-eventual; treated `mixed` as fallback) | D-8 above + B-7 ticket added to Sprint 1 | Hard-locked at {beauty, supplements, mixed}; B-7 enforces refusal; pricing shifted up |

**No gaps remain. Sprint 1 is unblocked.**

---

## 11. Sprint 5 (addendum) — Supplements demo-readiness + calibration wiring (Week 9–10)

**Date appended:** 2026-05-11
**Framing (read once, applies to entire section):** These are bugs and known issues we found during the execution of Sprints 1–4, AND things we were aware of going into the plan (i.e., the K=3 calibration math being stress-untested, the dormant `store_id` plumbing, the supplements scope completion gap). **This is not new product scope — it is technical-debt closure and consumer-wiring of mechanisms already shipped.** The substrate is in place; the writers are in place; what remains is honest end-to-end behavior on the supplements vertical and the dormant calibration read-path getting plugged in at its production call site.

**Operational context:**
- Agent Swarm work is paused for ~2 weeks. No live `campaign_sent` / `outcome_observed` writers will land before then.
- Zero merchant data. Synthetic fixtures only (Beauty + supplements pinned).
- Feedback / lifecycle loop testable only synthetically. No real outcomes flowing.
- SQLite substrate is scaffolding for the planning horizon; AWS migration is the real deployment story. Storage backend will swap behind the existing API.
- Sprint 4 closed; branch pushed to origin (36 commits at push time).

### Sprint 5 hard constraints

- `engine_run.json` schema remains **FROZEN**. All ticket changes use existing field shapes.
- `event_version=1` for `recommendation_emitted` / `recommendation_considered` / `campaign_sent` remains **FROZEN**. P-1 (§12) is additive within `event_version=1` (all new fields Optional).
- **D-6 enforced:** no ML scaffolding added.
- **D-8 enforced:** vertical scope stays `{beauty, supplements, mixed}`. No apparel/food/home/wellness.
- **M0 Beauty pinned fixture sha256 must stay byte-identical** except in tickets where re-pin is explicitly listed in acceptance (Beauty re-pin in S5-T1 is the only Beauty change in this sprint).
- **Supplements G-1 fixture WILL re-pin multiple times in this sprint** — intentional, not a regression. Each re-pin commit documents old→new sha256.
- **Per-commit ritual:** impl commit + memory.md doc commit (≤15 lines, use template) + summary file in `agent_outputs/`.

### Sprint 5 Tickets (in founder-confirmed priority order)

---

**Ticket S5-T1 — KI-26 + KI-3 (bundled) — Supplements `prior` plumbing + `store_id` wiring**
- **ID:** S5-T1 (bundles KI-26 + KI-3)
- **Owner:** code-refactor-engineer
- **Scope:** Two one-line wirings, one commit, both real correctness bugs (not deferrals). **KI-26:** supplements state-of-store Observations populate `current` and `delta_pct` but leave `prior: null` — Beauty populates `prior` correctly. Engine-side fix: the Observation typed slot is already reserved (6B contract); investigate which observation builder on the supplements path skips the `prior` write and plumb it. **KI-3:** S-5 added an optional `store_id` kwarg to `calibration_stub.load_realization_factors` but `src/main.py` doesn't pass it; the substrate read path is unreachable in production. One-line wiring at the main.py call site. Bundled because both are one-line wirings that share an "activation" theme; neither requires the other but both ship together for sprint hygiene.
- **Acceptance test:** (a) supplements G-1 fixture re-pinned in same commit; document old `feb03500c1...` → new sha256; assertion that supplements observations now carry non-null `prior` for AOV, repeat rate, orders, returning-customer share, net sales; (b) `tests/test_calibration_stub_shape.py` updated to assert the store_id-aware code path returns identical empty-shape dict when no `calibration_updated` events present (so behavior is unchanged on Beauty); (c) M0 Beauty pinned fixture byte-identical (no Beauty observation builder touched; KI-26 fix is scoped to the supplements code path).
- **Risk:** If the supplements observation builder shares code with Beauty and the `prior` plumbing accidentally changes Beauty's `prior` semantics, M0 breaks. Mitigation: golden diff on Beauty MUST be empty before merge; if Beauty shifts, the scope was wider than expected and the ticket re-scopes.
- **Dependencies:** None. First ticket of the sprint.

---

**Ticket S5-T2 — KI-20 — Supplements directional Recommended Now path**
- **ID:** S5-T2 (resolves KI-20)
- **Owner:** code-refactor-engineer (with consultation from ecommerce-ds-architect if window/cohort design needs review)
- **Scope:** `first_to_second_purchase` ships as a directional Recommended Now card on Beauty via the Phase 5.6 directional builder (L28 primary-window signal), but is invisible on supplements because the L28 window edge falls inside the typical 28–45 day supplement reorder cadence. Two viable resolution paths: (a) widen the directional builder's window for supplements (or vertical-dispatch the window choice), OR (b) document an explicit no-signal abstain with typed reason. Path (a) is preferred if cohort design is clean; path (b) is the fallback if widening the window threatens cohort integrity.
- **Acceptance test:** Supplements G-1 fixture re-pinned; document old → new sha256. Either (i) Recommended Now on supplements contains at least `first_to_second_purchase` with `evidence_class=directional`, OR (ii) Considered contains `first_to_second_purchase` with a new typed reason code (e.g., `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW`) and a memory.md note explains why the supplements directional path is honestly empty. New test pins whichever behavior was chosen. M0 Beauty byte-identical.
- **Risk:** If the fix is "widen the window for supplements," the cohort definition MUST NOT introduce Berkson confounding (B-5 invariant must stay green). The directional builder's cohort is defined on early-half counts (per 554960d / `project_journey_p_zero.md`) — preserving that property across window widening is non-trivial.
- **Dependencies:** S5-T1 (supplements fixture re-pin lands first to avoid double re-pin overhead).

---

**Ticket S5-T3 — KI-22 — Repeat-rate incoherence flag for cadence > window**
- **ID:** S5-T3 (resolves KI-22)
- **Owner:** code-refactor-engineer
- **Scope:** Supplements run logs `⚠️ Metric warnings: Repeat rate 0% suspiciously low for 972 orders` to stdout but the advisory never reaches `engine_run.json::data_quality_flags`. Add typed enum value `METRIC_INCOHERENT_FOR_CADENCE` (additive — Sprint 2 schema-freeze explicitly allows additive enum values on `data_quality_flags`). When supplement reorder cadence exceeds the active L28 window, propagate the existing advisory into the typed flag list. Optionally suppress or relabel the misleading `repeat_rate_within_window` value on the Watching row (founder call inside the ticket — either is contract-safe).
- **Acceptance test:** Supplements G-1 fixture re-pinned; document old → new sha256. Assertion that `engine_run.json::data_quality_flags` contains `METRIC_INCOHERENT_FOR_CADENCE` on the supplements pinned run; Watching row either suppresses or relabels the incoherent metric (documented in the test); M0 Beauty byte-identical (Beauty cadence < window so flag does not fire).
- **Risk:** Threshold definition for "cadence exceeds window" — pick a defensible heuristic (e.g., median customer-level reorder gap > 0.8 × active window length) and pin it in the test, not in a magic constant scattered across modules.
- **Dependencies:** S5-T2 (re-pin order; both touch the supplements golden).

---

**Ticket S5-T4 — KI-25 engine-side wire-up — Per-vertical audience floor in legacy builder**
- **ID:** S5-T4 (partially resolves KI-25; structural audience redefinition deferred to Sprint 6)
- **Owner:** code-refactor-engineer
- **Scope:** G-3 (Sprint 4) shipped `src/priors_loader.py::get_audience_floor(play_id, vertical)` and per-vertical floors in `config/priors.yaml` (`routine_builder` metadata: `{beauty: 60, supplements: 30, mixed: 45}`). The legacy `src/audience_builders.py::routine_completion_candidates` still uses `MIN_N_SKU` config-driven floor unconditionally. Plumb `get_audience_floor(..., vertical=...)` into the legacy builder so the per-vertical floor takes effect.
- **Acceptance test:** Supplements `routine_builder` no longer rejects with `audience_too_small` IF the audience under the per-vertical floor is non-empty. Supplements G-1 fixture may re-pin if behavior shifts; document old → new sha256. New unit test asserts the legacy builder reads `get_audience_floor(play_id="routine_builder", vertical="supplements") == 30`. M0 Beauty byte-identical (Beauty floor is 60, matches current `MIN_N_SKU`).
- **Risk:** This **only fully resolves KI-25 if the supplements audience-builder definition itself produces a non-empty audience.** The structural audience=0 problem (G-1 finding: skincare-single-product cohort doesn't exist on supplements) is a **separate Sprint 6 ticket** — re-think the `routine_builder` audience definition for supplements (replenishment-cadence buyers, not skincare-single-product). S5-T4 lands the mechanism wiring; Sprint 6 lands the definition redesign.
- **Dependencies:** S5-T3 (re-pin order).

---

### Deferred to Sprint 6 (explicitly NOT in Sprint 5)

The following surfaced during Sprint 4 G-1 triage. Stated here so the deferral is explicit, not silent.

- **KI-21** — typed reason fan-out on the experiment-held path (`EXPERIMENT_HELD_PRIOR_SUPPRESSED` etc.). Polish, not blocking. Generic `no_measured_signal` is correct-but-unhelpful; expanding the typed reason is Sprint 6.
- **KI-23** — detected-but-not-surfaced trace. Polish. Five M3-detected plays silently drop on supplements between shadow detection and Considered render. Surface a trace or pin the documented filter as a Sprint 6 ticket.
- **KI-24** — Phase 4.2 `subscription_nudge` redesign. **Real redesign work, not a one-ticket fix.** Multiplier-vs-baseline-rate conflation; survivorship bias on ≥3-SKU audience. Needs a DS architecture pass (ecommerce-ds-architect) before scoping. G-4 already tightened the surface honestly (`evidence_class=targeting`, `measurement=None`); the underlying audience-definition redesign is the open work.
- **I-1 ship** (affinity emitter behind `bestseller_amplify`) — spike memo exists at `agent_outputs/i1-spike-findings.md`; ship deferred indefinitely per founder direction.

---

## 12. Phase 9 prep (parallel to Sprint 5)

**Frame:** warm-up while Sprint 5 runs; not blocking, but lands before Swarm comes back from the ~2-week pause.

**Ticket P-1 — Extend `calibration_updated` payload schema (additive, no version bump)**
- **ID:** P-1
- **Owner:** code-refactor-engineer
- **Scope:** Per the recent DS architecture memo on the feedback loop, the current `calibration_updated` payload shape `{prior_overrides, evidence_thresholds, materiality_overrides}` is too thin for Phase 9's actual consumer needs. Add the following fields (**all Optional, all additive at `event_version=1`** — no schema bump because the substrate's additive-only rule covers this):
  - `n_observations: Optional[int]` — the K count contributing to the override (lets Phase 9's calibration consumer enforce K=3 minimum at read time)
  - `source_class: Optional[str]` — one of `"expert" | "observational" | "causal"` — tracks promotion from G-3's expert defaults to observational means to (eventually) causal estimates
  - `contributing_lineage_ids: Optional[List[str]]` — audit trail enabling the merchant-facing "Proven on your store" badge (Swarm-rendered, not engine-rendered)
  - `computed_by_function_version: Optional[int]` — mirrors the `outcome_observed` schema; lets future `compute_realized_outcome` versions invalidate stale overrides instead of silently mixing function-version cohorts
  - `partition: Optional[Dict]` — `{play_id, store_id, audience_definition_version}` for partition explicitness (today implicit in the section/key structure; making it explicit lets future consumers cross-check)
- Update `docs/memory_substrate.md` with the extended schema and an example payload. Update `src/memory/events.py` type definitions if applicable. **NO consumer changes** — `calibration_stub.read_calibration_state` continues to project into the existing `{prior_overrides, evidence_thresholds, materiality_overrides}` dict shape. The new fields are written but not yet read; Phase 9's actual consumer is the future work that consumes them.
- **Acceptance test:** Schema documented in `docs/memory_substrate.md`; type additions in `src/memory/events.py` (if events.py uses typed payload structs); substrate write/read tests still green; M0 Beauty pinned fixture byte-identical (additive Optional fields with no writer present in Sprint 5).
- **Risk:** Adding a field that Phase 9 then wants to type more strictly forces a real `event_version=2` bump. Mitigation: all five additions are typed as Optional at the start; Phase 9 tightens the types under its own version-bump discipline if needed.
- **Dependencies:** None. Parallel-track to S5-T1 through S5-T4.

---

### Sprint 5 Definition of Done

**Sprint 5 complete when ALL of:**
- [ ] S5-T1 merged; supplements observations carry non-null `prior` for state-of-store metrics; `store_id` plumbed into `load_realization_factors` from `src/main.py`; supplements G-1 fixture re-pinned (sha256 documented); M0 Beauty byte-identical
- [ ] S5-T2 merged; supplements directional Recommended Now path resolved (either surfaces `first_to_second_purchase` or honestly abstains with typed reason); supplements G-1 fixture re-pinned (sha256 documented); B-5 Berkson invariant test still green; M0 Beauty byte-identical
- [ ] S5-T3 merged; `METRIC_INCOHERENT_FOR_CADENCE` enum value live; supplements run propagates the advisory into `data_quality_flags`; supplements G-1 fixture re-pinned (sha256 documented); M0 Beauty byte-identical
- [ ] S5-T4 merged; `routine_builder` legacy builder reads `get_audience_floor(..., vertical=...)`; supplements behavior shift documented (re-pin if applicable); M0 Beauty byte-identical
- [ ] P-1 merged (parallel); `calibration_updated` payload schema extended with 5 Optional fields; `docs/memory_substrate.md` reflects new shape; no consumer changes; M0 Beauty byte-identical
- [ ] All Sprint 1–4 invariants still green: G-7 determinism CI, B-3 hardcoded-fallback regression, B-5 Berkson invariant, B-6 multi-window combiner universality, single-writer-per-event-type CI, role-uniqueness invariant, forbidden-token sweep
- [ ] Per-commit ritual followed for all 5 tickets (impl commit + memory.md note + summary file in `agent_outputs/`)
- [ ] KNOWN_ISSUES.md updated: KI-3, KI-20, KI-22, KI-26 flipped to `resolved` with commit hashes; KI-25 status updated to reflect partial resolution + Sprint 6 follow-up

### What Sprint 5 does NOT do

Explicit non-goals — stated so scope creep has nowhere to hide:
- **NOT introducing new product scope.** Every ticket consumer-wires or fixes a mechanism already shipped in Sprints 1–4.
- **NOT touching the schema freeze.** `engine_run.json` remains byte-identical on Beauty. `event_version=1` for all five typed event payloads remains in force. P-1 is additive Optional fields within `event_version=1` (substrate's additive-only rule explicitly permits this).
- **NOT shipping I-1.** The affinity emitter spike memo stays at `agent_outputs/i1-spike-findings.md`; ship deferred indefinitely per founder direction.
- **NOT addressing Phase 4.2 redesigns.** KI-24 (`subscription_nudge` multiplier-vs-baseline-rate conflation) needs an ecommerce-ds-architect pass before scoping; Sprint 5 only inherits G-4's surface honesty.
- **NOT expanding vertical scope.** D-8 hard-lock `{beauty, supplements, mixed}` enforced; no apparel/food/home/wellness.
- **NOT scaffolding ML modules.** D-6 ban enforced — no quiz bandits, LTV, uplift, churn, elasticity, bundle optimization placeholders.
- **NOT building Klaviyo/Shopify production integrations.** D-5 manual-import-only contract holds.

### Sprint 6 candidates surfaced by Sprint 5

Listed without committing to a Sprint 6 plan yet. Each gets ticket-level scoping at Sprint 5 closeout.

- **KI-21 typed reason fan-out on experiment-held path** — additive enum growth on `ReasonCode`; populate `held_reason_detail` struct that was reserved in 6B.
- **KI-23 detected-but-not-surfaced trace** — extend `populate_considered_from_candidates` to surface a "Detected but did not reach Considered" trace OR document the filter and pin it in test.
- **KI-24 Phase 4.2 `subscription_nudge` redesign** — multi-week DS architecture work; needs ecommerce-ds-architect engagement first. Gating dependency for honest supplements `subscription_nudge` claims.
- **KI-25 structural audience redefinition for `routine_builder` on supplements** — separate from S5-T4's mechanism wiring. Replenishment-cadence buyers, not skincare-single-product cohort. Audience builder rewrite, not config change.
- **KI-28 end-to-end `mixed` fixture pin** — once at least one of KI-20 / KI-24 lands so the mixed run produces a non-trivial slate, pin `healthy_mixed_240d_*` end-to-end. Until then, the loader-level test path (G-3) remains the contract.
- **Phase 9 P-2 candidate (parallel-track):** once Swarm returns from the pause, scope L-C `compute_realized_outcome(REPEAT_PURCHASE_IN_30D)` as the next Phase 9 prep ticket. Not committed to Sprint 6 yet — depends on Swarm readiness.
