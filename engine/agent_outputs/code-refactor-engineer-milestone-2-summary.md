# Milestone 2 — Code Refactor Engineer Summary

_Completed: 2026-05-01 (engine-rework branch)_

## Approved scope

Milestone 2 of `agent_outputs/implementation-manager-overhaul-plan-final.md`:
the Play Registry and per-vertical priors config. Tickets T2.1, T2.2,
T2.3, T2.4, T2.5, T2.6.

**Schema/config only.** M2 is NOT allowed to:
- add candidate detection (M3),
- change recommendations, scoring, gating, or briefing UX,
- touch evidence classification (M4a/M4b),
- remove fake stats (M4a),
- read `priors.yaml` at runtime (M6),
- rename merchant-facing plays (M8).

## Files changed

### New files

- `/Users/atul.jena/Projects/Personal/beaconai/src/play_registry.py` —
  typed `PlayDef` dataclass (frozen), `PLAYS: Dict[str, PlayDef]`
  populated for 14 plays (11 legacy + 3 new). Leaf-level: imports
  nothing from `src.action_engine` (verified by test). Provides
  `EVIDENCE_CLASSES` set, `get(play_id)`, `all_play_ids()` helpers.
  Construction-time validation rejects targeting plays that declare a
  `measurement_metric` (PM-Q2 hard rule).
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml` —
  schema-versioned per-play priors registry. Every entry carries
  `name`, `value`, `range_p10`, `range_p90`, `source_class` ∈
  `{observational, causal, expert}`, `last_updated`, and `applies_to`.
  Covers 11 legacy plays + 3 new T2.3 plays.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_play_registry.py` —
  18 tests: legacy-id coverage, T2.3 new-id coverage, schema validation,
  default-class invariants, per-play assertions, `PlayDef` validator
  unit tests, leaf-module guarantee, source-grep forcing function that
  re-greps `play_id="..."` literals in `action_engine.py` at test time.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_yaml.py` —
  8 tests: top-level schema, per-prior required keys, source_class
  whitelist, range ordering, value-inside-range invariant, applies_to
  shape, legacy-coverage, runtime-not-loaded invariant.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/play_registry.md` —
  contract reference: schema, per-play paragraphs (definition,
  audience, measurement metric, evidence class, inventory, priors,
  open issues), priors schema table, source_class semantics, M2-vs-M3
  -vs-M6-vs-M10 migration roadmap, deferred Phase-2 open question on
  `realization_factor` shape.

### Edited files

None. M2 is purely additive; no engine code paths were touched.

## Exact commands run (and outcomes)

| Command | Result |
|---|---|
| `python -m pytest tests/test_play_registry.py tests/test_priors_yaml.py -v` | **26 passed** |
| `python -m pytest tests/test_golden_diff.py -v` | **3 passed** (M0 still green) |
| `python -m pytest tests/ -v` | **60 passed** total (34 prior + 26 new) |
| `make golden-test` | **3 passed** |
| `python -m src.main --orders data/SM_orders.csv --brand m2_smoke --out /tmp/m2_smoke_run` | pass — briefing + 3 PRIMARY actions produced; legacy CSV → HTML workflow intact |

The 60-test count breakdown: 3 golden-diff + 7 engine_run schema + 16
anomaly + 8 observation + 18 play_registry + 8 priors_yaml = 60.

Sanity-grep confirms no `from src.play_registry` / `import play_registry`
anywhere in `src/` — runtime wiring is correctly deferred to M3+.

## Tests/checks run and their results

- 26 new tests across 2 files (`test_play_registry.py`,
  `test_priors_yaml.py`), all green.
- 3 M0 golden diff tests, all green (briefing.html + 6 receipts JSON
  byte-identical for all 3 fixtures: micro_coldstart, small_sm,
  mid_shopify).
- Full pytest pass: 60/60 green.
- End-to-end smoke run on `data/SM_orders.csv` produces a briefing and
  the same 3 PRIMARY recommendations the legacy engine has been
  producing.

### Anti-vacuity probes verified during dev

While iterating, the `test_play_registry_does_not_import_action_engine`
and `test_yaml_not_loaded_at_runtime` tests initially fired false
positives on substring matches of `action_engine` and `priors.yaml`
inside the registry's own docstring/comments. Both tests were tightened
to look for actual import statements / load patterns
(`open(...priors.yaml`, `safe_load(...priors.yaml`, etc.) rather than
arbitrary substrings. After tightening, both tests pass and remain
sensitive to a real wiring leak.

## Whether M0 golden diff still passes

**YES.** `pytest tests/test_golden_diff.py -v` returns 3 passed in
27.8s. M0 fixture briefing.html is byte-identical for all three
merchants (micro_coldstart, small_sm, mid_shopify); the 6-JSON-receipts
golden tree is byte-identical too. M2 added no engine-runtime imports,
so by construction M0 cannot drift.

## Artifacts created

```
src/play_registry.py
config/priors.yaml
tests/test_play_registry.py
tests/test_priors_yaml.py
docs/play_registry.md
agent_outputs/code-refactor-engineer-milestone-2-summary.md
```

## Inventory of legacy emitted play_ids (used to populate PLAYS)

Greppped from `src/action_engine.py` — ALL of these are now registered:

1. `winback_21_45` (line 2812 / 2827)
2. `bestseller_amplify` (line 2866 / 2882)
3. `discount_hygiene` (line 2932 / 2948)
4. `subscription_nudge` (line 3071)
5. `routine_builder` (line 3136 / 3168)
6. `empty_bottle` (line 3279) — registered as Replenishment Reminder
7. `frequency_accelerator` (line 3351 / 3364)
8. `aov_momentum` (line 3411 / 3424)
9. `retention_mastery` (line 3474 / 3487)
10. `journey_optimization` (line 3539 / 3552)
11. `category_expansion` (line 3603 / 3616)

Plus 3 new T2.3 entries:

12. `first_to_second_purchase` — measured (preferred replacement for
    journey_optimization per memory.md)
13. `at_risk_repeat_buyer_rescue` — targeting (rename of
    retention_mastery; assumed-churn-reduction removed per memory.md)
14. `onsite_funnel_watch` — targeting (demoted journey_optimization;
    waiting on onsite-funnel data)

The plan said "10 existing plays". The grep produced 11 distinct legacy
ids — `empty_bottle` is the eleventh (a replenishment-reminder
candidate generated alongside `subscription_nudge` in the legacy
emitter). Including it in PLAYS satisfies the M2 acceptance criterion
"every legacy emitted play_id is represented in `PLAYS`". Documented
explicitly here so the M3 author isn't surprised.

## Skipped items and why

- **No runtime wiring.** Per the M2 instructions, the registry is NOT
  wired into `_compute_candidates`, scoring, sizing, or rendering. M3
  will be the first milestone to read `PLAYS`; M4a/M4b will read
  `evidence_class_default`; M6 will read `prior_keys` and load
  `config/priors.yaml`. M2 only ships the schema/data.
- **No merchant-facing rename.** `retention_mastery` and
  `journey_optimization` remain in the briefing under their legacy
  display names. The new IDs (`at_risk_repeat_buyer_rescue`,
  `onsite_funnel_watch`) are reserved registry entries, not yet
  emitters.
- **No `realization_factor` shape decision.** Per the QA "nice-to-have"
  in memory.md (`docs/play_registry.md`: "what `realization_factor` is
  — ratio? regression? ITT?"), I documented this as a deferred Phase-2
  question instead of locking down a definition that PM hasn't yet
  arbitrated. M9 author should re-open with PM.
- **No cross-validation of `prior_keys` against `priors.yaml`.** M2
  intentionally does not enforce that every key in `PlayDef.prior_keys`
  has a matching block in `priors.yaml`. M6 (which introduces
  `priors_loader.py`) is the right place to add that consistency check.

## Assumptions and ambiguity calls

- **Source class assignment.** Most priors are labeled `expert` because
  they are hand-tuned constants. Only base rates and a few effects
  with at least some CSV-derived support are labeled `observational`.
  No prior is `causal` (no randomized study exists). This follows the
  conservative ordering ruleset in the M2 instructions: "When in doubt,
  prefer the more conservative class (expert > observational > causal)".
- **`empty_bottle` evidence class.** Set to `directional` because the
  legacy emitter already runs a two-proportion z-test between depleted
  and non-depleted cohorts, but `n` is often small enough that M4a/M4b
  may demote to `targeting`. Documented in the PlayDef notes and the
  registry doc.
- **`first_to_second_purchase` evidence class.** Set to `measured`
  because the metric is a binary first→second conversion rate
  computable from CSV history alone. Memory.md explicitly calls this
  play "MVP-safe and preferred replacement for Journey Optimization."
- **`at_risk_repeat_buyer_rescue` priors.** Intentionally NO
  `churn_reduction` prior in `priors.yaml` for this new play (memory.md
  guidance: "remove assumed churn reduction"). The legacy
  `retention_mastery` block keeps the historical churn_reduction values
  for traceability; M4a will NaN the merchant-facing exposure.

## Readiness for Milestone 3

Green to start M3. The registry shape is stable, leaf-level, and tested.
Open items the M3 author should be aware of:

1. **`audience_builder_ref` is a free-text reference, not a callable.**
   M3 must define the audience-builder API surface and add a
   resolution layer (e.g., a dict keyed by the ref string) before
   wiring detection. No M2 code stands in the way.

2. **The legacy `_compute_candidates` still emits its own dicts.** M3
   should run the new `detect_candidates` in shadow mode alongside the
   legacy path and only flip the renderer when M8 lands. The existing
   `engine_run_adapter.py` already accepts arbitrary `play_id`s; if M3
   emits a candidate not in `PLAYS`, the adapter currently maps it to
   `EvidenceClass.TARGETING` — the M2 registry-sanity test will be the
   forcing function to keep that mapping honest.

3. **`empty_bottle` is the 11th legacy play.** The M3 detector should
   produce a candidate for it; the registry expects `directional` as
   the default class.

4. **`first_to_second_purchase` is the M3 MVP add.** Memory.md flags
   this as the preferred replacement for `journey_optimization`. M3
   should prioritize wiring its detector first.

5. **Priors are not loaded yet.** The legacy sizing constants in
   `action_engine.py` (`get_conversion_rates`,
   `get_incrementality_factors`, `get_effect_params`,
   `calculate_28d_revenue` per-play branches) continue to drive
   merchant output. M6 is the migration point. Until then the
   `priors.yaml` values are effectively documentation.

6. **Targeting plays must NOT expose `measurement` in `EngineRun`.**
   This is a PM-Q2 hard rule. The registry enforces the no-metric
   constraint at construction (a default-targeting play cannot declare
   a `measurement_metric`); M4a is the milestone where the runtime
   contract is enforced (NaN out p/q/CI/measured-effect for any
   candidate whose evidence class collapsed to targeting).

## Risks (and how M2 mitigates them)

- **Registry desync from legacy emitters.** Mitigated:
  `test_grep_action_engine_emitted_ids_match_registry` re-greps the
  source on every test run. Adding a new `play_id="..."` literal in
  `action_engine.py` without registering it will fail the test.
- **Targeting plays sneaking in a measurement metric.** Mitigated:
  `PlayDef.__post_init__` raises `ValueError` at construction time. A
  reviewer who tries to back-door a `measurement_metric` onto a
  default-targeting play will fail import on the first test run.
- **Priors drift between schema versions.** Mitigated: `priors.yaml`
  carries `schema_version: "1.0.0"`. Bump on incompatible changes.
- **Registry is read at runtime accidentally.** Mitigated:
  `test_yaml_not_loaded_at_runtime` will fail if any module in `src/`
  (other than the future `priors_loader.py`) opens or loads
  `config/priors.yaml`. M2 contract preserved.

## Validation summary

- 60 tests pass (3 M0 golden + 7 schema + 16 anomaly + 8 observation +
  18 play_registry + 8 priors_yaml).
- 0 changes to merchant-facing output.
- 0 changes to legacy `actions_bundle` shape.
- 0 new env flags.
- 0 edits to `action_engine.py`, `main.py`, `validation.py`,
  `utils.py`, `engine_run.py`, or any other prior module.
- 5 new files: 1 source module, 1 config artifact, 2 test files, 1 doc.
- Registry covers 11 legacy + 3 new = 14 plays.
- Priors cover the same 11 legacy + 3 new plays (with `onsite_funnel_watch`
  intentionally listed as `[]` since it has no priors yet).
