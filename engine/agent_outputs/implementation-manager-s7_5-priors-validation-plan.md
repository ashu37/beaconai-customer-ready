# Sprint S7.5 — Priors Validation: Implementation Manager Plan

**Owner:** implementation-manager
**Date:** 2026-05-17
**Branch target:** `post-6b-restructured-roadmap`
**Source contract:** `ARCHITECTURE_PLAN.md` Part III-1 (lines ~1585–1750)
**Predecessor sprint:** Sprint 5 (S5-T1/T2/T3 closeouts — 1190p/14s/1f baseline)
**Successor sprint:** Sprint 6 (Tier-B builders) — **gated on S7.5 close**

---

## 1. Sprint S7.5 Overview

### Anchor goal
Replace the unsafe `source_class → pseudo_N` blend weight with a per-prior `validation_status` field whose `heuristic_unvalidated` value causes sizing to refuse blending and the engine to emit a typed `SOFT_PRIOR_UNVALIDATED` abstain — without changing engine behavior until a single deliberate flag flip lands.

### Why S7.5 precedes S6 (Tier-B builders)

Sprint 6 builds Tier-B audience builders whose Recommended Now cards consume priors *through* `sizing.size_play` to produce blended `revenue_range` outputs. Shipping Tier-B before S7.5 would surface confident-looking dollar ranges built on engineer-typed YAML constants laundered through a "60/40 store + prior" weight — exactly the failure Part III-1 diagnoses. S7.5 lands the metadata + refusal contract first so Tier-B builders ship into a world where blend math is only permitted on validated anchors. Tier-B authors can then design each builder against a stable `validation_status` interface, knowing that `heuristic_unvalidated` priors will be refused without further plumbing.

### Total duration estimate
**11.5 working days** across 7 commit-shaped tickets (8 if T1.5 is split; see §2). Each ticket follows the team's three-commit ritual (impl + memory.md + summary doc), so the ticket count above counts logical tickets, not commits.

### Beta-blocking status
**Yes — S7.5 is beta-blocking.** Per Phase 6A Final Review (memory.md, 585480e), external beta requires founder sign-off on caveats 1–6. Caveat 4 (priors are unvalidated heuristics) is closed only by S7.5-T3.5's flag-on posture combined with S7.5-T2's external-benchmark memos. S6 (Tier-B) can begin after S7.5-T3 lands behind flag (no behavior change); S7.5-T3.5 is the actual gate.

### Schema fields added during the sprint

| Field | Type | Where | Default | Justification |
|---|---|---|---|---|
| `validation_status` | `Optional[ValidationStatus]` (closed enum) | `PriorEntry`, `priors.yaml` per-entry | `heuristic_unvalidated` when YAML omits the field | Closed enum named in Part III-1 §III-1 Step 1. Backwards-compatible default. |
| `source_artifact` | `Optional[str]` (relative path) | `PriorEntry`, `priors.yaml` per-entry | `None` | Points to `config/priors_sources/<file>.md`. Required to promote to `validated_external` / `validated_internal`. |
| `effective_n` | `Optional[int]` | `PriorEntry`, `priors.yaml` per-entry | `None` | Underlying n for validated entries. Overrides default `pseudo_N` per Part III-1 Failure 2. |
| `SOFT_PRIOR_UNVALIDATED` | enum value on `AbstainMode` (or equivalent typed abstain field) | `src/engine_run.py` | additive enum value | Sprint 2 freeze carve-out: additive enum values on typed fields are explicitly permitted (precedent: `METRIC_INCOHERENT_FOR_CADENCE`, `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW`). |
| `PRIOR_UNVALIDATED` | enum value on `ReasonCode` | `src/engine_run.py` | additive enum value | Tier-C cards held under unvalidated base_rate priors fall through to Considered with this typed reason. Same Sprint 2 carve-out. |

All schema additions are **additive within `event_version=1`**. Swarm consumers pattern-matching on existing enum values are unaffected.

### Feature flags introduced

| Flag | Default | Owned by ticket | Purpose | Removal milestone |
|---|---|---|---|---|
| `ENGINE_V2_PRIORS_VALIDATION` | `OFF` until S7.5-T3.5 | S7.5-T3 (add); S7.5-T3.5 (flip) | Gates the cold-start blend-refusal rule in `sizing.size_play`. When OFF, today's `source_class != causal → suppressed` rule continues unchanged. When ON, the refusal generalizes to `validation_status in {heuristic_unvalidated, placeholder} → suppressed`. | Sprint 9 cleanup (after one beta cycle with flag ON; gate becomes structural). |

No other flags are introduced. T1/T1.5/T2 ship pure metadata and require no gating.

### Behavior changes by ticket boundary

| After ticket | Behavior change? | What changed |
|---|---|---|
| S7.5-T1 | **No** | Pure schema/loader additions. New fields parse with default `heuristic_unvalidated`. `PriorEntry` constructions in tests get an additional optional field. `engine_run.json` unchanged. |
| S7.5-T1.5 | **No** | YAML-only edits: every entry's `validation_status` is set explicitly. The 8 `internal_csv_observation_v1` entries are evaluated: those WITHOUT a reproducible source_artifact in the repo stay at `heuristic_unvalidated` (founder Q3 below). `engine_run.json` unchanged because nothing consumes the field yet. |
| S7.5-T2 | **No** | New `config/priors_sources/<file>.md` memos land. Affected YAML entries gain `source_artifact:` paths and (where defensible) promote to `validated_external` / `validated_internal`. Loader parses the new pointers. **Nothing in sizing or decide reads the field yet** (T3 wires consumption). `engine_run.json` unchanged. |
| S7.5-T3 (flag OFF) | **No** | New refusal helper + `SOFT_PRIOR_UNVALIDATED` abstain mode are implemented behind `ENGINE_V2_PRIORS_VALIDATION`. With flag OFF, `sizing.size_play` continues to take the `source_class != causal → suppressed` branch and never consults `validation_status`. M0 goldens and pinned slate fixtures byte-identical. |
| S7.5-T3 (flag ON, manual test only) | **Yes (test-only)** | When operator sets `ENGINE_V2_PRIORS_VALIDATION=true` for ad-hoc testing: sizing refuses to blend on `heuristic_unvalidated`/`placeholder` priors; affected Tier-C cards drop to Considered with `ReasonCode.PRIOR_UNVALIDATED`; runs with zero firing Tier-B builders emit `abstain_mode=SOFT_PRIOR_UNVALIDATED`. Beauty pinned slate would change → DO NOT run flag-on in CI yet. |
| S7.5-T3.5 | **Yes (intentional re-pin)** | Flag default flips ON. Beauty pinned slate, supplements G-1 fixture, M0 goldens re-pinned in the SAME commit (Sprint 2 Risk #4 discipline). This is the ONLY ticket in S7.5 that changes engine output by design. |

---

## 2. Per-ticket plan

The team's existing ticket pattern is one **logical ticket = three commits**: impl + tests + KI/fixtures, then `Document <ticket> in repo memory.md`, then the summary doc. Each ticket's "Commit boundary" section makes this explicit. The summary doc filename pattern follows S5-T3.

---

### S7.5-T1 — `validation_status` / `source_artifact` / `effective_n` fields on `PriorEntry`

**Title:** Additive `PriorEntry` schema + loader fields for validation provenance; no behavior change.

**Scope (files touched):**
- `src/priors_loader.py` — extend `PriorEntry` dataclass with three new `Optional` fields; extend `_coerce_entry` to read them from YAML; add closed `ValidationStatus` enum (importable from `priors_loader`); validate enum string on parse, falling back to `heuristic_unvalidated` on missing or unknown value (with a debug log line, no raise — consistent with existing tolerant-loader policy).
- `tests/test_priors_loader_validation_fields.py` — **new**. ~10 tests: enum membership pinned; default-when-absent; explicit enum value parsed; unknown string falls back; `effective_n` non-int → `None`; `source_artifact` whitespace-only → `None`; existing fixture priors (Beauty/supplements/mixed) parse without error.
- `tests/test_priors_yaml.py` — extend YAML schema test to allow the new optional keys.

**No changes to:** `config/priors.yaml` (T1 is loader-only; T1.5 walks the YAML). `src/sizing.py`. `src/decide.py`. `src/engine_run.py`.

**Acceptance criteria:**
- `PriorEntry.validation_status` returns `ValidationStatus.HEURISTIC_UNVALIDATED` for every existing prior loaded from today's YAML (verified across all 14 plays in a parametrized test).
- `PriorEntry.source_artifact` returns `None` for every existing entry.
- `PriorEntry.effective_n` returns `None` for every existing entry.
- `ValidationStatus` is a closed enum exposing exactly: `validated_external`, `validated_internal`, `elicited_expert`, `heuristic_unvalidated`, `placeholder`. Unknown values are NOT silently accepted.
- `tests/test_priors_yaml.py::test_yaml_not_loaded_at_runtime` still passes (loader gating not changed).
- Beauty pinned slate sha256 **unchanged** at `dcb45cee...` (C3 baseline). Supplements G-1 fixture sha256 **unchanged** at `01f5feff84...` (S5-T3 baseline). M0 goldens byte-identical.

**Test deliverables:**
- New: `tests/test_priors_loader_validation_fields.py` (~10 tests).
- Extended: `tests/test_priors_yaml.py` (allow new optional fields).
- Must stay green: full suite at 1190p baseline.

**Schema additions:**
- `PriorEntry.validation_status: Optional[ValidationStatus] = None` (loader coerces None → `HEURISTIC_UNVALIDATED` at read time). Additive because every existing constructor of `PriorEntry` (including `resolve_mixed_prior` which builds the synthetic blended entry) continues to work; the field has a safe default.
- `PriorEntry.source_artifact: Optional[str] = None`. Additive.
- `PriorEntry.effective_n: Optional[int] = None`. Additive.
- `ValidationStatus` enum is new and exported from `priors_loader.__all__`.

**Fixture re-pin:** **No.**

**Behavior change:** **No.**

**Dependencies:** None. T1 is the entry point.

**Estimated duration:** 1 day.

**Commit boundary (3 commits):**
1. `S7.5-T1: validation_status / source_artifact / effective_n fields on PriorEntry`
2. `Document S7.5-T1 in repo memory.md`
3. `S7.5-T1 summary`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s7_5-t1-summary.md`

---

### S7.5-T1.5 — Priors YAML audit pass (walk every entry; set `validation_status` explicitly)

**Title:** YAML-only audit; promote `internal_csv_observation_v1` to `validated_internal` ONLY where a source artifact exists.

**Scope (files touched):**
- `config/priors.yaml` — walk every entry (143 entries per Part III-1 audit). For each:
  - Default: explicit `validation_status: heuristic_unvalidated`.
  - The 8 `internal_csv_observation_v1` entries: founder Q3 below determines promotion. If a script/research memo exists in the repo, promote to `validated_internal` and set `source_artifact:` to the path. If not, stay at `heuristic_unvalidated` with a YAML comment noting "no reproducible artifact found in repo as of 2026-05-17; T2 may upgrade".
  - The 4 `discount_hygiene` margin_recovery_rate entries (currently `observational`, half-defensible per Part III-1): same audit. Either promote with source artifact or stay heuristic.
  - The 2 placeholder docstring entries (`first_to_second_purchase.second_purchase_lift`, `at_risk_repeat_buyer_rescue`): mark `validation_status: placeholder` explicitly.
- `tests/test_priors_yaml_validation_status_authored.py` — **new**. Parametrized test asserting every (play_id, prior_name, applies_to) tuple has an authored `validation_status` (no implicit default after T1.5).

**No code changes.** This is a content-editor ticket on YAML + a structural pin test.

**Acceptance criteria:**
- Every prior entry in `config/priors.yaml` carries an authored `validation_status` field. The parametrized test fails on any missing entry.
- Per-status counts at T1.5 close are recorded in the summary doc (e.g., "139 entries `heuristic_unvalidated`, 2 entries `placeholder`, 0 entries `validated_*`" — actual numbers depend on founder Q3 resolution).
- Loader continues to parse the file without raising.
- Beauty pinned slate sha256 **unchanged**. M0 goldens byte-identical.

**Test deliverables:**
- New: `tests/test_priors_yaml_validation_status_authored.py` (1 parametrized test across all entries).
- Must stay green: T1's `tests/test_priors_loader_validation_fields.py`, full suite.

**Schema additions:** None (T1 added the fields; T1.5 populates them).

**Fixture re-pin:** **No.**

**Behavior change:** **No.** Nothing reads `validation_status` yet.

**Dependencies:** S7.5-T1.

**Estimated duration:** 0.5 day (mostly YAML editing + per-entry status decisions; the founder's answer to Q3 below is the main input).

**Commit boundary (3 commits):**
1. `S7.5-T1.5: audit priors.yaml; set validation_status on every entry`
2. `Document S7.5-T1.5 in repo memory.md`
3. `S7.5-T1.5 summary`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s7_5-t1_5-summary.md`

---

### S7.5-T2 — External-benchmark research memos + `source_artifact` wiring

**Title:** Add `config/priors_sources/` memos for each external benchmark; promote affected YAML entries to `validated_external` / `validated_internal`.

**Scope (files touched):**
- `config/priors_sources/` — **new directory**. One memo per validated_external prior, filename pattern `<play_id>__<prior_name>.md` (e.g., `winback_21_45__base_rate__beauty.md`). Each memo carries: publication title; date; sample composition (vertical / size / methodology); verbatim numbers extracted; how the YAML value was derived from the verbatim number; observational-vs-causal distinction; effective_n if attributable.
- `config/priors_sources/README.md` — explains the memo template and the validated_external promotion criteria.
- `config/priors.yaml` — update affected entries: add `source_artifact:` pointer + promote `validation_status` accordingly. The architecture plan §III-1 Step 4 names the candidate sources (Klaviyo Industry Benchmarks → email base rates; Shopify Plus Benchmarks → AOV; DTC Power Index / Repeat Customer Insights → repeat-purchase curves). **Critical constraint repeated:** these are observational benchmarks, NOT causal lift; promote only `base_rate`-style priors, NEVER `incrementality` / `*_lift` priors.
- `tests/test_priors_sources_artifacts_exist.py` — **new**. For every YAML entry with `source_artifact:` set, assert the file exists relative to repo root. Parametrized over all entries with a non-null pointer.
- `tests/test_priors_validation_status_invariants.py` — **new**. Invariant tests:
  - Any entry promoted to `validated_external` / `validated_internal` MUST have a non-null `source_artifact`.
  - Any entry with `validation_status in {validated_*}` and `name in {"incrementality", "frequency_lift", "second_purchase_lift", "subscription_multiplier", "churn_reduction", "conversion_improvement", "expansion_rate", "growth_acceleration", "bundle_value"}` raises in the test — incrementality / lift priors CANNOT be `validated_external` until a causal study is cited (Part III-1 Step 4 critical distinction).

**No code changes** beyond the loader already doing tolerant parsing. This is primarily content-author work (3–4 days of memo research) + ~1 day YAML+test scaffolding.

**Acceptance criteria:**
- Each `validated_external` / `validated_internal` entry's `source_artifact:` resolves to an existing file under `config/priors_sources/`.
- The invariant test pins the "no validated_* on incrementality / lift" rule.
- The memo per `priors_sources/` file follows the README template (the test should be content-aware enough to assert the memo has non-empty publication / date / sample / verbatim sections — a markdown-header presence check is sufficient).
- Per-status counts at T2 close are recorded in summary (expectation: a handful of `validated_external` base_rate entries; a handful of `validated_internal` margin_recovery_rate entries IF founder Q3 produces the artifacts).
- Beauty pinned slate sha256 **unchanged**. M0 goldens byte-identical.

**Test deliverables:**
- New: `tests/test_priors_sources_artifacts_exist.py`.
- New: `tests/test_priors_validation_status_invariants.py`.
- Must stay green: T1.5's parametrized authored-status test (now stricter — promotions count as authored); full suite.

**Schema additions:** None (T1 added the fields; T2 populates `source_artifact` and lifts `validation_status` values).

**Fixture re-pin:** **No.**

**Behavior change:** **No.** Still nothing reads `validation_status` at decide/sizing seam.

**Dependencies:** S7.5-T1, S7.5-T1.5. Founder Q1 must be resolved before content work begins.

**Estimated duration:** 5 days. Memo research is the dominant cost: 1 day per benchmark source × 3 named sources + 1 day of YAML wiring/tests. Could compress to 3 days if founder pre-supplies extracted numbers from existing reports.

**Commit boundary (3 commits, plus optional sub-commits per memo for traceability):**
1. `S7.5-T2: external-benchmark memos + source_artifact wiring + validation_status invariants` (this commit may be split into N memo-add sub-commits for review ergonomics; final logical ticket-close commit consolidates the test additions)
2. `Document S7.5-T2 in repo memory.md`
3. `S7.5-T2 summary`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s7_5-t2-summary.md`

---

### S7.5-T3 — Cold-start blend refusal + `SOFT_PRIOR_UNVALIDATED` abstain mode (behind flag, default OFF)

**Title:** Implement the behavioral change behind `ENGINE_V2_PRIORS_VALIDATION`; flag defaults OFF; engine output byte-identical until flip.

**Scope (files touched):**
- `src/engine_run.py` — additive enum values: `AbstainMode.SOFT_PRIOR_UNVALIDATED` (or equivalent typed slot — check whether abstain modes are already typed; if today they're strings on `Abstain.reason`, the additive precedent from S5-T2's `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` applies: add a typed enum value rather than a free string). Additive `ReasonCode.PRIOR_UNVALIDATED` for the Considered-fan-out reason.
- `src/sizing.py` — extend the suppression branch around lines 270-289. Behind `ENGINE_V2_PRIORS_VALIDATION`, the rule generalizes from `source_class != causal → suppressed` to:
  ```
  if validation_status in {HEURISTIC_UNVALIDATED, PLACEHOLDER}:
      return _suppressed_range("prior_unvalidated", drivers)
  if validation_status in {VALIDATED_EXTERNAL, VALIDATED_INTERNAL, ELICITED_EXPERT}:
      # blend permitted; pseudo_N derived from effective_n if present, else per-status default
      ...
  ```
  When `ENGINE_V2_PRIORS_VALIDATION` is OFF, the original `source_class != "causal"` branch is preserved unchanged.
- `src/decide.py` — extend the post-decide considered-fan-out so that any Tier-C card whose base_rate prior was suppressed under the new rule gets routed to Considered with `ReasonCode.PRIOR_UNVALIDATED` and dropped from `recommendations[]` / `recommended_experiments[]`. New abstain branch: when `ENGINE_V2_PRIORS_VALIDATION` is ON AND there are zero firing Tier-B builders AND every Tier-C play is suppressed under the new rule, emit `abstain_mode=SOFT_PRIOR_UNVALIDATED` distinct from `SOFT_AWAITING_MEASUREMENT`.
- `src/sizing.py` — also introduce the `pseudo_N` policy table per Part III-1: `{validated_external: 30, validated_internal: 15, elicited_expert: 10}`; `effective_n` overrides the default when present. (Note: the actual blend math that consumes `pseudo_N` is Tier-B territory; today's sizing only reads base_rate ranges, not a Bayesian posterior. T3 lands the table as a constant + helper for Tier-B builders to import in S6, but does not yet wire the blend posterior path into the existing sizing function. This is intentional — T3 is the refusal contract; S6 owns the actual blend math when it builds Tier-B.)
- `tests/test_s7_5_t3_priors_validation_refusal.py` — **new**. ~15 tests:
  - Flag OFF: pre-T3 behavior preserved (no new suppression reasons appear; M0 goldens byte-identical).
  - Flag ON: `heuristic_unvalidated` base_rate prior → suppressed with `reason="prior_unvalidated"`.
  - Flag ON: `placeholder` base_rate prior → suppressed.
  - Flag ON: `validated_external` base_rate prior with `effective_n=1200` → NOT suppressed under this rule (still subject to existing source_class causal rule which is unchanged).
  - Flag ON: zero-Tier-B + all-Tier-C-suppressed run produces `abstain_mode=SOFT_PRIOR_UNVALIDATED`.
  - Flag ON: zero-Tier-B + one validated Tier-C produces existing abstain modes, NOT SOFT_PRIOR_UNVALIDATED (the new mode requires the "every prior unvalidated" condition).
  - Considered-fan-out: a Tier-C card suppressed under the rule appears in `considered[]` with `reason_code=PRIOR_UNVALIDATED` and is absent from `recommendations[]` / `recommended_experiments[]` (B4 role-uniqueness contract preserved).
  - `pseudo_N` table: each enum value maps to the documented constant; `effective_n` override.
  - Flag-OFF / flag-ON parity test: same fixture run twice (once each), capture the two engine_run.json files, assert flag-OFF version equals current pinned fixture sha256.

**No changes to:** `config/priors.yaml` (T1.5/T2 already populated it). `tests/fixtures/synthetic_slate/` (no re-pin in T3 — that's T3.5's job).

**Acceptance criteria:**
- With `ENGINE_V2_PRIORS_VALIDATION=false` (default): Beauty pinned slate sha256 **unchanged**, supplements G-1 fixture sha256 **unchanged**, M0 goldens byte-identical.
- With `ENGINE_V2_PRIORS_VALIDATION=true`: Tier-C plays with `heuristic_unvalidated` base_rate priors fall through to Considered with `PRIOR_UNVALIDATED`; revenue ranges suppressed; B4 role-uniqueness intact.
- New abstain mode `SOFT_PRIOR_UNVALIDATED` emits ONLY when zero firing Tier-B builders AND every Tier-C suppressed under the new rule.
- `pseudo_N` policy table is a module-level constant in `src/sizing.py` (or `src/priors_loader.py` — implementation choice) so Tier-B authors in S6 have a single import target.
- The flag's name `ENGINE_V2_PRIORS_VALIDATION` is structurally pinned by a test (same shape as `ENGINE_S3_REASON_FANOUT` test).

**Test deliverables:**
- New: `tests/test_s7_5_t3_priors_validation_refusal.py`.
- Must stay green: every B-series invariant test (B1/B2/B3/B4/B5/B6), every M0 fixture test, every G-series fixture test, full suite at 1190p baseline + 14 new tests ≈ 1205p target.

**Schema additions:**
- `AbstainMode.SOFT_PRIOR_UNVALIDATED` — additive enum value within `event_version=1` (Sprint 2 carve-out).
- `ReasonCode.PRIOR_UNVALIDATED` — additive enum value within `event_version=1`.

**Fixture re-pin:** **No** (the flag defaults OFF; the flip+re-pin is T3.5).

**Behavior change:** **No when flag OFF** (the default). Behavior change only manifests under explicit operator flag-on, which is a test/founder-eval posture.

**Dependencies:** S7.5-T1 (loader fields). S7.5-T1.5 strongly recommended (so the flag-on test is meaningful on real fixtures, not synthetic ones). S7.5-T2 NOT a hard dependency (T3 can ship with zero validated_* entries; flag-on would simply suppress every Tier-C prior, which is the honest posture per Part III-1 Step 5).

**Estimated duration:** 2 days.

**Commit boundary (3 commits):**
1. `S7.5-T3: cold-start blend refusal + SOFT_PRIOR_UNVALIDATED abstain mode behind ENGINE_V2_PRIORS_VALIDATION`
2. `Document S7.5-T3 in repo memory.md`
3. `S7.5-T3 summary`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s7_5-t3-summary.md`

---

### S7.5-T3.5 — Flag flip ON + fixture re-pin (the only behavior-changing ticket in S7.5)

**Title:** Flip `ENGINE_V2_PRIORS_VALIDATION` default ON; re-pin Beauty + supplements fixtures atomically.

**Scope (files touched):**
- `src/utils.py` (or wherever `get_config()` resolves the flag) — flip the default. Operator override via env var still works.
- `tests/fixtures/synthetic_slate/healthy_beauty_*.html` — re-pin sha256. New baseline.
- `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` — re-pin sha256. New baseline.
- `tests/test_golden_diff.py` M0 fixtures (small_sm, mid_shopify, micro_coldstart) — re-pin per the same atomic commit (Sprint 2 Risk #4 discipline: flag flip + golden re-pin land in ONE commit).
- `tests/test_slate_regression_beauty_brand.py` — `PINNED_SHA256` update; expected Considered membership update (will likely gain ≥1 new `PRIOR_UNVALIDATED` entry); expected Recommended Experiment slate may shrink (allowlist mechanically tightens per Part III-1 §III-1: `bestseller_amplify` does NOT survive until its base_rate prior is validated; `discount_hygiene` survives ONLY IF T2 promoted its `margin_recovery_rate` to `validated_internal`).
- `tests/test_slate_regression_supplements_brand.py` — same shape.
- `KNOWN_ISSUES.md` — flip relevant KIs to `resolved` (see §4 below). Add any new caveats surfaced by the flag-on posture.

**Acceptance criteria:**
- Default-config run reproduces the new pinned sha256 byte-identically.
- The diff between old and new pinned slate is explainable in the summary doc: list each Considered card that moved, each Recommended/Experiment slot that emptied or filled.
- Operator override `ENGINE_V2_PRIORS_VALIDATION=false` still produces the OLD pinned fixture (regression test pins this — the flag can be flipped back via env if a beta merchant trips on it).
- B4 role-uniqueness invariant intact post-flip.
- Sprint 2 schema freeze intact: `event_version=1`, no field shape changes (the new enum values were added in T3 additively).
- Suite count post-T3.5 documented in summary.

**Test deliverables:**
- Re-pin SHAs in 3 fixture test files.
- New: 1 regression test pinning that `ENGINE_V2_PRIORS_VALIDATION=false` reproduces the pre-T3.5 sha256 (rollback safety).
- Must stay green: full suite.

**Schema additions:** None.

**Fixture re-pin:** **Yes — atomic with flag flip.** Beauty, supplements G-1, M0 (small_sm + mid_shopify + micro_coldstart) all in one commit.

**Behavior change:** **Yes — intentional.** This is the load-bearing posture change for beta.

**Dependencies:** S7.5-T3 (the flag must exist before it can be flipped). Founder Q2 must be resolved.

**Estimated duration:** 1 day. Mostly fixture regeneration + diff explanation.

**Commit boundary (3 commits):**
1. `S7.5-T3.5: flip ENGINE_V2_PRIORS_VALIDATION default ON; re-pin Beauty + supplements + M0 fixtures`
2. `Document S7.5-T3.5 in repo memory.md`
3. `S7.5-T3.5 summary`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s7_5-t3_5-summary.md`

---

### Sprint summary commit

A 7th logical ticket — `S7.5-CLOSE` — is not strictly necessary (the T3.5 summary doc and the memory.md updates close the sprint). Recommend skipping a dedicated sprint-close commit unless founder wants a single tagged commit to anchor the beta cut.

---

## 3. Risk register for this sprint

### R1 — T2 memo research stalls; sprint loses 3+ days

- **What could go wrong:** Klaviyo / Shopify / DTC Power Index reports change URL, get paywalled, or carry sample-composition that does not map cleanly onto BeaconAI's plays.
- **Mitigation:** T2 is non-blocking for T3. T3 ships flag-OFF with zero validated_* entries; T3.5 can flip with everything `heuristic_unvalidated` and produce the honest "every Tier-C suppressed; SOFT_PRIOR_UNVALIDATED" posture per Part III-1's "Honest abstain fallback" section. Memo backfill is allowed as a follow-on within S7.5 or as an S8 sub-ticket. **Founder Q1 below pins which sources to pursue.**
- **Observability hook:** T2's `tests/test_priors_validation_status_invariants.py` reports per-status counts in test stdout; the T2 summary doc records these.

### R2 — Flag-on posture renders the Beauty fixture too sparse (no Recommended / no Experiments)

- **What could go wrong:** With every base_rate prior at `heuristic_unvalidated`, the Recommended Experiment allowlist collapses (Part III-1 §III-1 explicitly notes `bestseller_amplify` falls out unless its base_rate is validated). Beauty fixture may render an empty slate, which founder may reject as "too aggressive a tightening for first beta."
- **Mitigation:** T3.5 is gated on founder review (Q2). If founder rejects, T3 stays in tree behind flag OFF (no behavior change), T3.5 is parked until after T2 produces ≥1 validated_external entry for `bestseller_amplify`. T3 is the contract; T3.5 is the activation, and the two are intentionally separable.
- **Observability hook:** T3.5 summary doc must include before/after side-by-side of the Beauty fixture's slate shape (Recommended count, Experiment count, Considered count by reason_code).

### R3 — `pseudo_N` policy table is added but no caller consumes it; dead code drifts

- **What could go wrong:** T3 lands `PSEUDO_N_BY_STATUS = {validated_external: 30, ...}` in `src/sizing.py` as a module constant for S6 Tier-B builders to import. If S6 slips, the constant sits unused.
- **Mitigation:** Pin the constant's existence and exact values in `tests/test_s7_5_t3_priors_validation_refusal.py`. Mark in code comment that the consumer is S6 Tier-B builders. Accept that this is forward-looking scaffolding — it's not "fake ML"; it's the refusal contract's reverse side.
- **Observability hook:** A simple grep test ensures the constant is exported in `priors_loader.__all__` (or `sizing.__all__`), making the contract visible to S6 authors.

### R4 — KI register drifts: open KIs not flipped on T3.5 close

- **What could go wrong:** S7.5 touches multiple priors-related KIs (see §4). If the T3.5 commit doesn't flip them atomically, KNOWN_ISSUES.md and engine behavior diverge.
- **Mitigation:** T3.5 commit must include KI flips in the same commit (precedent: S5-T3 flipped KI-22 atomically). The KI updates are listed in §4 below; the T3.5 summary doc must enumerate which flipped to `resolved` and which got a progress note.
- **Observability hook:** A simple grep test `tests/test_priors_kis_resolved_post_t3_5.py` (optional, lightweight) can pin the resolution state for the named KIs.

### R5 — Re-pin diff hides an unintended regression

- **What could go wrong:** Re-pinning Beauty fixture in T3.5 produces a sha256 change of legitimate origin (the new flag), but the same commit contains an accidental side-effect (e.g., an enum string-cast change that affected Considered ordering).
- **Mitigation:** T3.5's summary doc must walk the diff card-by-card. Pre-T3.5, run `python -m src.main` with `ENGINE_V2_PRIORS_VALIDATION=false` and capture the slate JSON; compare byte-for-byte against the pre-T3 baseline. Then with `ENGINE_V2_PRIORS_VALIDATION=true`, compare the diff against the previous flag-on test capture from T3. Any unexplained byte difference between these two checkpoints is the regression.
- **Observability hook:** The flag-off-still-reproduces-baseline regression test in T3.5 is the production net.

---

## 4. KIs touched / closed

Walking `KNOWN_ISSUES.md` for priors-related entries (grep on "prior", "validation", "csv_observation", "heuristic"):

| KI | Title | Current status | S7.5 impact |
|---|---|---|---|
| KI-13 | (Need to read full register; first 100 lines only shown) — likely tracks the priors-validation gap if logged | TBD | T3.5 may flip to `resolved` if entry exists; otherwise a new KI should land at T1 close documenting the new contract surface. |
| KI-19 | `mixed` semantics — silent beauty fallback risk | `resolved` (G-3) | No change. `resolve_mixed_prior` is orthogonal to validation_status. T3 must verify that the blended PriorEntry returned by `resolve_mixed_prior` carries the conservative-min `validation_status` of its two inputs (i.e., if beauty is `validated_external` and supplements is `heuristic_unvalidated`, blended is `heuristic_unvalidated`). T3 adds a test pinning this. |
| KI-25 | Supplements `routine_builder` audience floor (per-vertical floor wired at priors layer; legacy builder still applies its own floor) | `tracked` | No direct S7.5 impact. Stays `tracked`. |
| KI-26 | Observations carried `prior: null` (S5-T1 resolved) | `resolved` | No change. |
| KI-28 | End-to-end `mixed` fixture deferred | `tracked` | No direct S7.5 impact. After T3.5, a hypothetical mixed fixture would inherit the same flag-on behavior; if/when KI-28 closes, the mixed fixture would also need to be pinned at the flag-on baseline. |

**New KI to file at S7.5-T1 close:** A new KI (e.g., KI-29) documenting that the `pseudo_N_BY_STATUS` table in `sizing.py` is forward-looking scaffolding for S6 Tier-B; not consumed by any caller pre-S6. Status: `accepted` (intentional). This is the "fake-ML guard" entry so a future review doesn't flag it as dead code.

**Action for the implementing agent on T1:** Read the FULL `KNOWN_ISSUES.md` (file was only partially read in this plan's research pass). Enumerate every entry with "prior" / "validation" / "blend" / "pseudo_N" / "heuristic" in title or body, and produce the per-KI status flip plan as part of the T1 summary doc.

---

## 5. What S7.5 does NOT do

Explicit non-goals (so no scope creep):

1. **S7.5 does NOT build any Tier-B builders.** Tier-B is S6. S7.5 lands only the contract that Tier-B consumes.
2. **S7.5 does NOT refactor `config/priors.yaml` into per-play files.** That's S8 Play Library work (per ARCHITECTURE_PLAN.md cleanup workstream III-2). The YAML stays monolithic through S7.5.
3. **S7.5 does NOT introduce a Bayesian posterior / blend math in `sizing.py`.** The `pseudo_N` table lands as a constant for S6 to import; no blend math is computed in S7.5. Suppression-on-unvalidated is the only behavioral change.
4. **S7.5 does NOT introduce ML model code.** D-6 enforced. No placeholder bandit/Thompson/LinUCB modules.
5. **S7.5 does NOT introduce Shopify/Klaviyo network calls.** D-5 enforced. T2 memos are read-only research artifacts; they describe public benchmark numbers, they do not call APIs.
6. **S7.5 does NOT touch the Phase 9 outcome importer / calibration consumer.** KI-1 / KI-2 / KI-4 remain Phase 9's scope. S7.5 is the priors *intake* validation; outcome calibration is downstream.
7. **S7.5 does NOT change `event_version` from 1 to 2.** Every schema addition is additive (new optional fields + new enum values). The Sprint 2 schema freeze contract holds.
8. **S7.5 does NOT renegotiate D-8.** Vertical scope stays `{beauty, supplements, mixed}`. No "wellness" / "apparel" priors introduced via memo-backfill back-doors.
9. **S7.5 does NOT introduce per-vertical audience floors.** That's G-3 / KI-25 territory. The per-vertical floor mechanism is orthogonal to validation_status.
10. **S7.5 does NOT delete legacy `source_class` field.** `source_class` is descriptive; `validation_status` is load-bearing. They coexist. A future M10-style cleanup may retire `source_class`; not S7.5.

---

## 6. Open questions for the founder

These need human judgment before tickets can ship. Tickets are sequenced so T1 + T3 can begin in parallel without these answers; T1.5 + T2 + T3.5 block on the answers below.

### Q1 — External benchmark sourcing

**Question:** Which external benchmarks will the founder source for T2 memos?

Part III-1 §III-1 Step 4 names three candidates:
- **Klaviyo Industry Benchmarks** (free, annual). Maps to base rates on email-driven plays.
- **Shopify Plus Benchmarks Report** (free). Maps to AOV-distribution priors.
- **DTC Power Index / Repeat Customer Insights / Lifetimely DTC benchmarks** (some free, some paywalled). Maps to repeat-purchase curves.

**Decision needed:**
- Should T2 commit to all three sources, or scope down to Klaviyo only on first ship?
- For DTC Power Index specifically: does the founder have access? If not, fall back to Repeat Customer Insights (lighter-weight, public-blog-post sourcing).
- For supplements specifically: are there beauty-shaped benchmarks the founder is comfortable cross-applying as conservative priors, or must supplements stay `heuristic_unvalidated` until S6+ generates internal data?

**Default if founder doesn't respond:** Scope T2 to Klaviyo + Shopify benchmarks only (both free, both public). DTC Power Index deferred. Memos for `winback_21_45.base_rate`, `first_to_second_purchase.base_rate`, `bestseller_amplify.base_rate` (beauty), `aov_momentum.base_rate` (beauty).

### Q2 — `ENGINE_V2_PRIORS_VALIDATION` default-OFF on first ship?

**Question:** Is the founder OK with `ENGINE_V2_PRIORS_VALIDATION` default-OFF on first ship, with T3.5 (the flag flip) as a separate ticket?

**Default if founder says yes:** Ship T3 alone. T3.5 lands after founder reviews the diff (which T3.5's summary doc must include before/after slate counts). This preserves the rollback option: if a beta merchant trips, operator sets the env var back to `false`.

**Default if founder says no (i.e., land T3 and T3.5 in one go):** Skip T3.5 as a separate ticket; merge the flag flip into T3 itself. This is contract-safe (the rollback env var still works), but it removes the "Sprint 2 Risk #4 atomic re-pin" discipline as a separate review surface. Acceptable but less reviewable.

### Q3 — Reproducible `internal_csv_observation_v1` source artifacts in the repo

**Question:** For the 4 plays with half-defensible CSV observational priors (`discount_hygiene`, `winback_21_45`, `empty_bottle`, `frequency_accelerator`), do the source CSV/scripts that produced the values exist in the repo? If yes, where?

The 8 entries currently tagged `internal_csv_observation_v1` produced values like:
- `winback_21_45.base_rate` supplements = 0.12
- `winback_21_45.base_rate` mixed = 0.06
- `winback_21_45.orders_per_customer` `"*"` = 1.30
- `discount_hygiene.margin_recovery_rate` supplements = 0.005
- `discount_hygiene.margin_recovery_rate` mixed = 0.005
- `empty_bottle.base_rate` `"*"` = 0.12
- `frequency_accelerator.base_rate` supplements = 0.18
- `frequency_accelerator.base_rate` mixed = 0.16

**Decision needed:**
- Is there a `scripts/` or `notebooks/` artifact in the repo (or in `agent_outputs/`) where these numbers were computed? If yes, point T1.5 at the path; promote those 8 entries to `validated_internal` with `source_artifact:` pointers.
- If the numbers were derived informally and no reproducible script exists, the entries stay `heuristic_unvalidated`. This is the honest answer per Part III-1 §III-1 Step 3.

**Default if founder doesn't respond:** Stay `heuristic_unvalidated`. Open a follow-up KI ("the 8 csv_observation_v1 entries lack reproducible source artifacts; promote on demand") and move on. The T2 memo work can backfill these later if founder produces the scripts/CSVs.

### Q4 (bonus, not blocking) — Pseudo-N table values

Part III-1 §III-1 publishes the table:
- `validated_external` → 30
- `validated_internal` → 15
- `elicited_expert` → 10

These are lower than Part I §C's original values (50/20). Founder accepted the lower values per the architecture plan, but T3 lands them as a module constant — confirm the values are still right at T3 implementation time. If founder revises, T3 updates the constant in one place.

---

## Ticket count + duration roll-up

| Ticket | Days | Behavior change | Fixture re-pin |
|---|---|---|---|
| S7.5-T1 | 1.0 | No | No |
| S7.5-T1.5 | 0.5 | No | No |
| S7.5-T2 | 5.0 | No | No |
| S7.5-T3 | 2.0 | No (flag OFF) | No |
| S7.5-T3.5 | 1.0 | Yes (flag flip) | Yes (atomic) |
| **Total** | **9.5 working days** | — | — |

Adding 2 days of slack for review/founder Q&A → **11.5 working days** as quoted in §1.

5 tickets total (T1, T1.5, T2, T3, T3.5). Each ticket = 3 commits in the team's pattern → **15 commits** across the sprint.

---

## Appendix A — File path index (absolute)

Files this plan expects to touch or create:

- `/Users/atul.jena/Projects/Personal/beaconai/src/priors_loader.py` — T1
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py` — T3
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` — T3
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — T3 (new enum values)
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` — T3.5 (flag default flip)
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml` — T1.5, T2
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors_sources/` — T2 (new directory)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_loader_validation_fields.py` — T1 (new)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_yaml_validation_status_authored.py` — T1.5 (new)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_sources_artifacts_exist.py` — T2 (new)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_validation_status_invariants.py` — T2 (new)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s7_5_t3_priors_validation_refusal.py` — T3 (new)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_yaml.py` — T1 (extend)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_slate_regression_beauty_brand.py` — T3.5 (re-pin)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_slate_regression_supplements_brand.py` — T3.5 (re-pin)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_golden_diff.py` — T3.5 (re-pin M0)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic_slate/healthy_beauty_*.html` — T3.5 (regenerate)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` — T3.5 (regenerate)
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md` — T3.5 (KI flips)
- `/Users/atul.jena/Projects/Personal/beaconai/memory.md` — each ticket
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s7_5-t1-summary.md` — T1 (new)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s7_5-t1_5-summary.md` — T1.5 (new)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s7_5-t2-summary.md` — T2 (new)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s7_5-t3-summary.md` — T3 (new)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s7_5-t3_5-summary.md` — T3.5 (new)
