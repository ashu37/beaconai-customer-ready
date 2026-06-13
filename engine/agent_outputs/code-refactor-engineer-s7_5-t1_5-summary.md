# S7.5-T1.5 — Priors YAML audit pass

**Owner:** code-refactor-engineer (Sprint 7.5, ticket S7.5-T1.5)
**Date:** 2026-05-17
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-s7_5-priors-validation-plan.md](./implementation-manager-s7_5-priors-validation-plan.md) §2, ticket S7.5-T1.5 (lines 113-152)
**Design rationale:** `ARCHITECTURE_PLAN.md` Part III-1 §III-1 Step 1
**Predecessor:** S7.5-T1 ([code-refactor-engineer-s7_5-t1-summary.md](./code-refactor-engineer-s7_5-t1-summary.md))
**Status:** Complete. YAML-only edits + 1 new test file + 1 T1-test rename. ZERO behavior change.

---

## 1. Approved scope

T1 introduced the closed-enum `PriorValidationStatus` field on
`PriorEntry` with a `HEURISTIC_UNVALIDATED` default. T1.5 walks
`config/priors.yaml` and authors the field explicitly on every entry
so the YAML is the source of truth (no implicit Python default in
production).

Founder pre-answers locked in by the orchestrator:

- **Q3** (csv_observation provenance): no internal CSV scripts known.
  Grep the repo; demote any entry without a reproducible artifact.
- **Q4** (pseudo_N values): accepted, scope of T3 not T1.5.

## 2. Audit findings

### Total entries

84 prior entries across 14 plays (the plan's "143 entries" projection
was an over-estimate; the live YAML has 84). Breakdown by play:

| Play | Priors |
|---|---|
| winback_21_45 | 7 |
| bestseller_amplify | 9 |
| discount_hygiene | 5 |
| subscription_nudge | 8 |
| routine_builder | 9 |
| empty_bottle | 2 |
| frequency_accelerator | 9 |
| aov_momentum | 8 |
| retention_mastery | 7 |
| journey_optimization | 9 |
| category_expansion | 8 |
| first_to_second_purchase | 3 |
| at_risk_repeat_buyer_rescue | 2 |
| onsite_funnel_watch | 0 (empty list — legal) |

### Distribution at T1.5 close

| validation_status | Count | Notes |
|---|---|---|
| `heuristic_unvalidated` | 82 | The honest baseline — every value is an engineer-typed constant without reproducible source artifact. |
| `placeholder` | 2 | `first_to_second_purchase.second_purchase_lift`; `at_risk_repeat_buyer_rescue.base_rate`. Both already carried "Placeholder" notes; T1.5 promotes the note to a structural field. |
| `validated_external` | 0 | T2 promotes the first batch. |
| `validated_internal` | 0 | No reproducible internal CSV artifact found (see §3). |
| `elicited_expert` | 0 | Reserved for SME-elicited priors with explicit citation. None today. |

### §3 — Repo grep for `internal_csv_observation_v1` provenance

The 8 entries tagged `source: internal_csv_observation_v1`:

1. `winback_21_45.base_rate` supplements = 0.12
2. `winback_21_45.base_rate` mixed = 0.06
3. `winback_21_45.orders_per_customer` `"*"` = 1.30
4. `discount_hygiene.margin_recovery_rate` supplements = 0.005
5. `discount_hygiene.margin_recovery_rate` mixed = 0.005
6. `empty_bottle.base_rate` `"*"` = 0.12
7. `frequency_accelerator.base_rate` supplements = 0.18
8. `frequency_accelerator.base_rate` mixed = 0.16

**Grep methodology:**

```
grep -ril "internal_csv_observation_v1\|csv_observation" \
  --include='*.py' --include='*.md' --include='*.ipynb' --include='*.sql' .
```

Hits: `ARCHITECTURE_PLAN.md`, `agent_outputs/code-refactor-engineer-s7_5-t1-summary.md`, `agent_outputs/implementation-manager-s7_5-priors-validation-plan.md`, `agent_outputs/code-refactor-engineer-g3-summary.md`, `tests/test_g3_supplements_priors.py`. All are documentation / plans / tests that **reference** the tag, none **derive** the values.

Secondary grep across analysis dirs:

```
grep -rEil "winback.*0\.12|0\.12.*winback|orders_per_customer.*1\.30|margin_recovery_rate.*0\.005|empty_bottle.*0\.12|frequency_accelerator.*0\.18" \
  --include='*.py' --include='*.md' --include='*.ipynb' --include='*.sql' \
  scripts/ tools/ analysis/ docs/ src/
```

Hits:

- `analysis/conversion_rate_research_recommendations.md` — references DIFFERENT proposed values (e.g., winback_21_45 supplements **0.27**, not 0.12; frequency_accelerator supplements **0.26**, not 0.18). This is a research wishlist, not a derivation of the current YAML values.
- `src/action_engine.py` — the values appear inline as constants (lines 308, 317, 321-322), confirming the YAML mirrors `action_engine.py` rather than deriving from CSV analysis. No analysis script / notebook / SQL query producing these numbers is present in the repo.

No reproducible artifact exists. Per founder Q3 pre-answer, all 8 stay `heuristic_unvalidated`. The `source: internal_csv_observation_v1` YAML tag is left in place as a descriptive label (historical traceability) but is no longer a validation claim — the load-bearing field is `validation_status`.

## 4. Patch summary

### `config/priors.yaml`

- Header comment block added under `schema_version` documenting the T1.5 audit outcome (82 / 2 / 0 / 0 / 0 distribution; the 8 csv_observation entries' demotion rationale; T2's role).
- `last_reviewed: "2026-05-10"` → `"2026-05-17"`.
- 84 `validation_status: heuristic_unvalidated` lines inserted after every prior's `last_updated:` line (legacy-list and Phase 6A dict-form blocks alike).
- 2 entries flipped to `validation_status: placeholder`:
  - `first_to_second_purchase.priors[2] (second_purchase_lift)`
  - `at_risk_repeat_buyer_rescue[0] (base_rate)`

### `tests/test_s7_5_t1_5_priors_audit.py` (NEW)

3 tests:

1. `test_every_prior_entry_has_authored_validation_status` — walks the raw YAML (deliberately bypassing the loader so the T1 default cannot mask a missing field), asserts every dict entry has an explicit `validation_status` key whose value is in the closed-enum set.
2. `test_validation_status_distribution_pin` — pins the per-status counts (82 + 2 + 0 + 0 + 0) and the two specific (play_id, prior_name) tuples that are `placeholder` so a future YAML typo cannot silently swap a placeholder for a heuristic.
3. `test_loader_resolves_every_entry_with_an_enum_value` — sanity: the on-disk authored strings load through the closed-enum loader without raising; every resolved entry has a `PriorValidationStatus` instance.

### `tests/test_s7_5_t1_priors_validation_fields.py` (modified)

The T1-shipped test `test_real_priors_yaml_every_entry_defaults_to_heuristic_unvalidated` asserted that loading the live YAML produced `HEURISTIC_UNVALIDATED` on every entry. T1.5 introduces 2 `placeholder` entries, so this T1 test was renamed to `test_real_priors_yaml_every_entry_resolves_to_a_closed_enum_value` and reframed to assert the closed-enum invariant only. The per-status distribution check moved to the new T1.5 test (above). Both the new T1.5 test and the reframed T1 test pass on the audited YAML; both fail on missing-status or unknown-string drift.

### No changes to

- `src/priors_loader.py` (T1 owns the loader; T1.5 is YAML-only).
- `src/sizing.py`, `src/decide.py`, `src/engine_run.py` (T3 wires consumption behind a flag).
- Other YAML files / config artifacts.

### Fixture re-pin

**None.**

| Fixture | sha256 | Status |
|---|---|---|
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `45edaca58c47...` | **Unchanged** |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `01f5feff84...` | **Unchanged** |
| M0 goldens (small_sm / mid_shopify / micro_coldstart) | covered by `tests/test_golden_diff.py` | **Byte-identical** (test suite passes) |

## 5. Files changed

| File | Change |
|---|---|
| `config/priors.yaml` | Header audit comment + `last_reviewed` bump + 84 `validation_status:` insertions + 2 `placeholder` flips |
| `tests/test_s7_5_t1_5_priors_audit.py` | NEW — 3 tests covering authored-field presence + distribution pin + closed-enum loader resolution |
| `tests/test_s7_5_t1_priors_validation_fields.py` | Renamed and reframed `test_real_priors_yaml_every_entry_defaults_to_heuristic_unvalidated` → `..._resolves_to_a_closed_enum_value`; same scope, weaker assertion (closed-enum invariant only) |
| `memory.md` | New S7.5-T1.5 entry under existing Sprint 7.5 header |
| `agent_outputs/code-refactor-engineer-s7_5-t1_5-summary.md` | NEW — this file |

## 6. Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s7_5_t1_5_priors_audit.py` | 3/3 green |
| `tests/test_s7_5_t1_priors_validation_fields.py` | 15/15 green (post-rename) |
| `tests/test_priors_loader.py` | green |
| `tests/test_priors_yaml.py` | green |
| `tests/test_priors_metadata.py` | green |
| `tests/test_g3_supplements_priors.py` | green |
| `tests/test_slate_regression_beauty_brand.py` | green (Beauty pinned slate sha256 `45edaca58c47...` unchanged) |
| `tests/test_slate_regression_supplements_brand.py` | green (supplements G-1 sha256 `01f5feff84...` unchanged) |
| `tests/test_golden_diff.py` | green (M0 fixtures byte-identical) |
| Full suite (`pytest -q`) | **1208 passed, 14 skipped, 1 failed** in 795s (was 1205/14/1 at S7.5-T1 close). Delta = +3 new T1.5 tests. The 1 failure is the pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift unrelated to this ticket. |

## 7. Behavior changes

**NONE.** YAML-only edits + test file additions. No engine output change.

- `engine_run.json` shape and value unchanged.
- `event_version=1` frozen contract intact.
- Nothing reads `validation_status` until T3.

## 8. Artifacts added

- `tests/test_s7_5_t1_5_priors_audit.py` (3 tests)
- `agent_outputs/code-refactor-engineer-s7_5-t1_5-summary.md` (this file)

## 9. Remaining risks / follow-ups

1. **`internal_csv_observation_v1` YAML tag is now descriptive-only.** The tag survives in 8 entries because deleting it would balloon the T1.5 diff and lose historical traceability. T2 should consider whether to retire the tag entirely once those entries are either promoted (to `validated_external` with a real memo) or stay `heuristic_unvalidated` with no further provenance work planned. Tracked here, not opening a new KI.
2. **`internal_heuristic_unvalidated` source tag is redundant with `validation_status: heuristic_unvalidated`.** Many entries carry both. Retention is intentional: the `source:` tag predates T1 and is referenced by other tests (e.g., G-3 supplements tests). Removing it is a cleanup workstream, not T1.5 scope.
3. **The "8 csv_observation entries" wishlist memo (`analysis/conversion_rate_research_recommendations.md`)** proposes different values than current YAML (e.g., winback supplements 0.27 vs 0.12). T2 should NOT use the wishlist values without sourcing them from a free public benchmark — the memo is a research-direction artifact, not a benchmark citation.

## 10. Follow-up work / dependencies

- **S7.5-T2** (external-benchmark memos) is next. Founder Q1 pre-answer: free public sources only (Klaviyo + Shopify Plus). DTC Power Index skipped.
- **S7.5-T3** (cold-start blend refusal + abstain mode behind `ENGINE_V2_PRIORS_VALIDATION`) wires consumption.
- **S7.5-T3.5** (flag flip ON + atomic fixture re-pin) is the only behavior-changing ticket.

## 11. Branch shape

Three commits on `post-6b-restructured-roadmap` (not pushed), plus the upstream housekeeping commit:

1. `d060b00` — `S7.5 housekeeping: commit IM plan; gitignore .claude/*.lock`
2. `ae5e5ea` — `S7.5-T1.5: explicit validation_status on every priors.yaml entry`
3. `4f1d22d` — `Document S7.5-T1.5 in repo memory.md`
4. _this commit_ — `S7.5-T1.5 summary`

## 12. Hard constraints respected

- `engine_run.json` schema **unchanged** in shape and value.
- `event_version=1` payloads **frozen** — no payload changes; T1.5 is YAML + tests only.
- D-6 enforced — no banned ML modules touched.
- D-8 enforced — vertical scope unchanged (`{beauty, supplements, mixed}`); no new verticals.
- M0 Beauty pinned fixture sha256 **unchanged**.
- Beauty pinned slate sha256 **unchanged** at `45edaca58c47...`.
- Supplements G-1 fixture sha256 **unchanged** at `01f5feff84...`.
- B-5 Berkson invariant intact — directional builder cohort logic untouched.
- S-2 / S-3 / S-4 / S-5 / S-6 substrate write paths **untouched**.
- `src/` **untouched** (T1.5 is YAML + tests only).
- `KNOWN_ISSUES.md` **untouched** at T1.5 close.
- No new runtime dependencies.
