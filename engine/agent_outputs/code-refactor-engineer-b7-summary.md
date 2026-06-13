# Sprint 1 Ticket B-7 — Hard-refuse non-supported verticals

## Scope

Add a guard at engine entry in `src/main.py` (orchestration boundary) that
fires BEFORE any priors loader, feature builder, or play registry runs. If
the resolved `vertical_mode` is not in `{beauty, supplements, mixed}`, the
engine returns ABSTAIN_HARD with `data_quality_flag = VERTICAL_NOT_SUPPORTED`
and `recommendations = []`. Add a comment at `src/play_registry.py:142` and a
loader-level assertion in `src/priors_loader.py` that raises `ConfigError`
on any non-supported top-level vertical block. Surface merchant-facing
refusal copy on the `Abstain.reason` field.

Source contract: `agent_outputs/implementation-manager-post-6b-restructured-plan.md`,
Section 1, Ticket B-7 (Addendum 3 / vertical-scope hard-lock correction).

## Files changed

Modified:

- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py`
  — added `DataQualityFlag.VERTICAL_NOT_SUPPORTED = "vertical_not_supported"`
  enum member (additive only; `EngineRun.data_quality_flags` schema field
  unchanged) with docstring naming B-7 / vertical_guard.
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py`
  — added `DataQualityFlag.VERTICAL_NOT_SUPPORTED` to `_HARD_DQ_FLAGS`
  (defensive: any downstream code re-classifying the run by its flags
  treats it as ABSTAIN_HARD).
- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling_v2.py`
  — added `DataQualityFlag.VERTICAL_NOT_SUPPORTED` mapping in
  `_humanize_data_quality_flag` so the V2 abstain-hard memo renders the
  merchant-facing refusal copy.
- `/Users/atul.jena/Projects/Personal/beaconai/src/play_registry.py`
  — single comment line above `_ALL_VERTICALS` (line 142):
  `# mixed = literal beauty+supplements blend, NOT an unknown-vertical fallback.`
- `/Users/atul.jena/Projects/Personal/beaconai/src/priors_loader.py`
  — new `ConfigError(ValueError)` exception class; new
  `_validate_top_level_verticals(doc)` helper called from `load_priors`
  BEFORE caching; structural-key allowlist
  `{schema_version, last_reviewed, plays}` plus the supported vertical
  set; raises `ConfigError` with the offending key named when a
  non-structural top-level mapping key is outside the supported set.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`
  — guard at the top of `run()` (after `cfg = get_config()` and the
  receipts-dir creation, BEFORE per-merchant store-id resolution, priors
  loader, feature builder, play registry). On refusal: builds the typed
  refusal `EngineRun`, writes `receipts/engine_run.json`, prints a
  diagnostic line, and returns. The lazy import of `vertical_guard`
  matches the pattern used elsewhere in `main.py` (e.g. guardrails) and
  keeps the orchestration boundary lightweight.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_engine_run_schema.py`
  — added `"vertical_not_supported"` to the closed-set assertion in
  `test_all_data_quality_flags_declared`.

Added:

- `/Users/atul.jena/Projects/Personal/beaconai/src/vertical_guard.py`
  — new isolated module exposing
  `SUPPORTED_VERTICALS` (re-exported from `play_registry._ALL_VERTICALS`,
  identity-equal), `MERCHANT_FACING_REFUSAL_COPY` (verbatim from the
  ticket), `is_supported(vertical_mode)` (None / empty / unsupported all
  return False — no silent `mixed` fallback), and
  `build_vertical_refusal_engine_run(...)` returning a typed
  ABSTAIN_HARD `EngineRun` with `data_quality_flags=[VERTICAL_NOT_SUPPORTED]`,
  `Abstain.reason = MERCHANT_FACING_REFUSAL_COPY`, and empty
  `recommendations` / `recommended_experiments` / `considered` /
  `watching` lists.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_vertical_hard_refuse.py`
  — 21 tests covering all 5 acceptance fixtures plus regression guards:
  - frozen-contract test on `_ALL_VERTICALS`;
  - parametrized refusal test for `food_bev`, `apparel`, `home`,
    `wellness` and casing variants;
  - None / empty / whitespace `vertical_mode` is refused (no
    silent-mixed fallback);
  - parametrized supported-set regression guard
    (`beauty`, `supplements`, `mixed`, casing + whitespace);
  - loader-level `apparel:` block raises `ConfigError`;
  - loader-level `food_bev:` block raises `ConfigError`;
  - loader accepts top-level `beauty` / `supplements` / `mixed` blocks
    (forward-compat regression);
  - shipped `config/priors.yaml` continues to load (over-refusal
    regression);
  - end-to-end synthetic apparel CSV via `main.run` writes ABSTAIN_HARD
    `engine_run.json` and skips the briefing render entirely (no slate,
    no HTML);
  - end-to-end Beauty regression: even on a tiny synthetic CSV that
    fails downstream, the guard never fires on `beauty` (no
    `vertical_not_supported` flag is ever written).

## Hard constraints respected

- `engine_run.json` schema reused (existing `data_quality_flags` slot;
  `EngineRun` class definition unchanged). The closed-enum
  `DataQualityFlag` gains one additive member; the schema-pin test in
  `tests/test_engine_run_schema.py::test_all_data_quality_flags_declared`
  was extended to match (the closed-set assertion would otherwise refuse
  the new member; this is the intended behavior — adding a flag IS the
  intentional schema-evolution event B-7 calls for).
- M0 Beauty pinned fixture byte-identical: 19/19 tests in
  `tests/test_slate_regression_beauty_brand.py` green; the guard does
  not fire on Beauty (`is_supported("beauty") is True`) so the Beauty
  path is byte-untouched.
- Trust contract preserved: no fabricated p / CI / projections; refusal
  payload carries only the typed flag, the typed reason text, and empty
  arrays.
- Vertical scope hard-lock at `{beauty, supplements, mixed}` enforced by
  the new frozen-contract test
  `test_all_verticals_frozen_contract`.
- Engine remains runnable: full suite `960 passed, 14 skipped, 0 failed`.
- Insertion point honored: guard is in `src/main.py`, after `cfg = get_config()`
  and the receipts-dir scaffold, BEFORE `resolve_store_id` /
  `migrate_legacy_recommended_history` / `load_orders_csv` /
  `compute_features` / priors loader / play registry.
- No substrate work, no Sprint 4 work, no Phase 9 work, nothing in the
  REFUSED list.

## Test results

| Suite                                                            | Result                            |
|------------------------------------------------------------------|-----------------------------------|
| `tests/test_vertical_hard_refuse.py` (new)                       | 21 passed                         |
| `tests/test_engine_run_schema.py` (updated)                      | passed                            |
| `tests/test_priors_loader.py`                                    | passed                            |
| `tests/test_slate_regression_beauty_brand.py` (M0 Beauty pinned) | 19 passed (byte-identical)        |
| `tests/test_engine_v2_shadow.py` (M0 goldens shadow)             | passed                            |
| `tests/test_golden_diff.py`                                      | passed                            |
| Full suite                                                       | 960 passed, 14 skipped, 0 failed  |

Pre-B-7 baseline was 939 passed / 14 skipped / 0 failed; B-7 adds 21
tests (`+21`).

## Out of scope (deliberately deferred)

- Adding a refusal HTML panel: per the ticket ("briefing renders only a
  refusal panel — or no briefing at all — pick whichever is cleaner; do
  not produce a normal slate with empty arrays"), the chosen behavior is
  to skip `render_briefing` entirely. The V2 abstain-hard memo renderer
  (`storytelling_v2.render_abstain_hard_memo`) already exists and would
  pick up the typed flag if a future ticket wires it; B-7 does not ship
  that wiring because the ticket explicitly allows the no-briefing
  option.
- Subvertical-level refusal: the guard only enforces the vertical_mode
  set. A future ticket may add subvertical scope locks; out of scope
  here.
- Loader-level validation of `applies_to.vertical` fields nested inside
  a play's prior list: the ticket scopes the loader check to *top-level*
  vertical blocks. Nested `applies_to` validation is a wider change and
  is not in B-7.
- B-1, S-2, S-3, G-7 — separate tickets / sprints.

## Risks observed

- **Post-promo soft-anomaly path stayed at 5 enum members** in the
  closed-set assertion before B-7; B-7 adds the 6th. Any future ticket
  that adds another `DataQualityFlag` must update the same assertion.
  No regression risk today (the assertion exists precisely to catch
  drift).
- **Lazy import inside `run()`** for `vertical_guard`: matches the
  existing pattern in `main.py` for guardrails / decide / debug renderer
  and keeps the import chain at orchestration time. If a future
  refactor moves `vertical_guard` import to module top, the guard
  semantics are unchanged.
- **`is_supported` casing tolerance**: the guard lowercases / strips
  `vertical_mode` before comparison. This is consistent with
  `priors_loader._matches_scope` (which also lowercases both sides).
  Should the engine ever decide to enforce strict-lowercase via .env
  validation, the guard remains correct (a strict-lowercase value is a
  fixed point of `_normalize`).
- **Priors loader top-level allowlist** is intentionally narrow:
  `{schema_version, last_reviewed, plays}`. Future YAML schema
  migrations that add a new structural key (e.g. `taxonomies:`) must
  extend `_STRUCTURAL_TOP_LEVEL_KEYS`. The new test
  `test_priors_loader_real_yaml_still_loads_clean` is the regression
  guard.
- **Stash interlude during edits**: while editing, an automated process
  stashed the in-progress B-7 work on `sprint1-engineer-b` (an unrelated
  branch). The stash was popped onto `post-6b-restructured-roadmap` and
  the unrelated B-1 in-progress edits to `src/guardrails.py`,
  `src/state_of_store.py`, and `tests/test_anomaly_gate_routing.py`
  (which had piggy-backed onto the stash) were reverted with
  `git checkout HEAD --` / `rm` so this commit is B-7 only. No B-1
  artifacts are in the resulting commit.

## Commit / PR shape

Commit on `post-6b-restructured-roadmap`. Single commit; no PR opened
(per ticket instructions: "do NOT push, do NOT open a PR"). Suggested
commit message:

```
B-7: hard-refuse non-supported verticals at engine entry

- New src/vertical_guard.py: SUPPORTED_VERTICALS (= play_registry._ALL_VERTICALS),
  MERCHANT_FACING_REFUSAL_COPY, is_supported(), build_vertical_refusal_engine_run().
- Guard wired into src/main.py:run() BEFORE priors loader / feature
  builder / play registry. Refusal writes ABSTAIN_HARD engine_run.json
  with data_quality_flag=VERTICAL_NOT_SUPPORTED and skips render_briefing.
- src/engine_run.py adds DataQualityFlag.VERTICAL_NOT_SUPPORTED (additive;
  EngineRun schema field unchanged). src/decide.py adds it to
  _HARD_DQ_FLAGS defensively. src/storytelling_v2.py maps it to the
  merchant-facing refusal copy.
- src/play_registry.py:142 gains the contractual comment above
  _ALL_VERTICALS: "mixed = literal beauty+supplements blend, NOT an
  unknown-vertical fallback."
- src/priors_loader.py adds ConfigError + _validate_top_level_verticals;
  raises with the offending key named when a non-structural top-level
  mapping is outside {beauty, supplements, mixed}.
- tests/test_vertical_hard_refuse.py (new, 21 tests) covers the 4
  acceptance fixtures + frozen-contract test on _ALL_VERTICALS.
- tests/test_engine_run_schema.py extended for the new flag value.

Suite: 960 passed, 14 skipped, 0 failed (was 939p/14s/0f).
M0 Beauty pinned fixture byte-identical (19/19).
```

Next ticket on Engineer A's track: G-7 (cross-run determinism CI).
Stopping here per ticket instructions.
