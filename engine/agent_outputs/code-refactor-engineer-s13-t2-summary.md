# S13-T2 — PlayCard consumer wiring + ML-fit fit_warnings activation (FLAG-OFF) + engine_run.py:167-171 comment revision

**Status:** staged, awaiting orchestrator commit.

## Approved scope

T2 wires the PlayCard consumer side behind a new flag
`ENGINE_V2_PLAY_PREDICTED_SEGMENT` (default OFF; T2.5 owns the atomic
flip). Five sub-commits per the dispatch brief:

- **Commit A** — `src/engine_run.py:167-171` comment revision (Q-S13-4
  LOCK) + `PredictedSegment` / `ModelCardRef` dataclass extension.
- **Commit B** — consumer-wiring producer (`src/predictive/consumer_wiring.py`
  NEW module + post-injection callsite in `src/main.py`).
- **Commit C** — AST-aware dormancy test refactor; ranking_strategy.py
  allowlist REMOVED.
- **Commit D** — REQUIRED runtime invariant test
  `tests/test_s13_ml_fit_never_demotes.py`.
- **Commit E** — flag definition in `src/utils.py` +
  `tests/test_s13_t2_predicted_segment_population.py`.

Refactor-engineer chose to ship as ONE staged change (the orchestrator
may split at commit time if preferred per the dispatch brief's
"refactor-engineer may split sensibly").

## Files changed

| File | Range | Change |
|---|---|---|
| `src/engine_run.py` | L44 | Import `Tuple` from `typing`. |
| `src/engine_run.py` | L167–183 (was L167–171) | **LOAD-BEARING comment revision per Q-S13-4 LOCK.** Removed the speculative `RejectedPlay.reason_code` channel mention; replaced with the locked `model_card_ref.fit_warnings` channel + precedence-pin reaffirmation + structural-incoherence rationale + test-contract anchors. |
| `src/engine_run.py` | L789–863 | `PredictedSegment` extended additively with `segment_name`, `audience_modal_share`, `n_audience` (all `Optional`, default `None`). `ModelCardRef` extended additively with `strategy_used` (Optional str), `fit_status_chain: List[Tuple[str, str]]`, `fit_warnings: List[str]` (LOCKED `"{LEVEL}:{substrate}"` grammar). Both keep the legacy `notes: Optional[str]` slot for back-compat round-trip. |
| `src/engine_run.py` | `_from_dict_predicted_segment` / `_from_dict_model_card_ref` | Extended to round-trip the new fields with defensive coercions. `fit_status_chain` rehydrates list-of-lists → list-of-tuples. |
| `src/predictive/consumer_wiring.py` | NEW (~290 lines) | Public surface `populate_play_card_consumers(engine_run, *, audience_ids_resolver, rfm_parquet_path)`. Walks `engine_run.recommendations`, calls `rank_audience()` per card, populates `ModelCardRef`, computes RFM modal segment from per-store parquet under the DS-LOCKED stability floor (`n<50` OR `share<0.30` → `segment_name=None`; audit fields uncensored). Hardcoded `_INTENT_BY_PLAY_ID` map (replenishment_due→REPLENISHMENT_TIMING; all other Tier-B builders→GENERAL; unknown→GENERAL). Pure attribute mutation via `dataclasses.replace`; NO append to `recommendations` or `considered`. |
| `src/main.py` | new block after L1970 (post `apply_guardrails_to_injected`, before `_populate_considered`) | Imports + calls `populate_play_card_consumers` ONLY when `cfg["ENGINE_V2_PLAY_PREDICTED_SEGMENT"]` is True. Per-play `_resolve_audience_ids_for_play` resolver mirrors the cannibalization-overlap pattern at L1937-1954 (re-runs the audience builder via `_get_audience_builder`). RFM parquet path computed as `DATA_DIR / store_id / "predictive" / "rfm.parquet"`. Failures caught + warning-logged; do NOT abort the run. |
| `src/utils.py` | new flag block after `ENGINE_V2_RANKING_STRATEGY_CHAIN` | `ENGINE_V2_PLAY_PREDICTED_SEGMENT` default `false`. Added to `_coerce` bool set. |
| `tests/test_reason_code_precedence_invariant.py` | L33 (import), `test_model_fit_codes_not_emitted_in_s10_close` body | **AST-aware refactor.** Replaced raw line-based regex grep with `ast` module walk. New invariant: no AST `Assign` / `AnnAssign` / `Call(RejectedPlay, reason_code=...)` node carries `ReasonCode.MODEL_FIT_*`. **S13-T1 `ranking_strategy.py` allowlist REMOVED** — no longer needed (fit_warnings strings are not RejectedPlay.reason_code assignments). Docstring updated with Q-S13-4 LOCK rationale. |
| `tests/test_s13_ml_fit_never_demotes.py` | NEW (~165 lines) | DS §E.1 REQUIRED. Parametrized over 5 pinned fixtures; runs engine with `ENGINE_V2_PLAY_PREDICTED_SEGMENT=true`; walks `considered` + `watching` + `recommendations` in the produced `engine_run.json`; asserts no item's `reason_code` ∈ `{"model_fit_insufficient_data","model_fit_refused"}`. |
| `tests/test_s13_t2_predicted_segment_population.py` | NEW (~290 lines) | 9 unit tests on the consumer-wiring module: flag default OFF; chain-walk happy path; fit_warnings grammar pin (PROVISIONAL_SELECTED + MODEL_FIT_REFUSED + MODEL_FIT_INSUFFICIENT_DATA); modal segment populates when floor cleared; floor `n<50` → segment_name=None (audit fields uncensored); floor `share<0.30` → segment_name=None; missing RFM parquet → predicted_segment=None (model_card_ref still populates); replenishment_due routes to REPLENISHMENT_TIMING chain head (SURVIVAL); extended `PredictedSegment`+`ModelCardRef` round-trip through `_from_dict_*` helpers. |

## :167-171 comment revision — verbatim before/after

**Before (S10-T3, speculative):**

```python
# No emitter is wired at S10 close — schema-additive only. S13 wires
# ``src/decide.py`` to populate these on ``RejectedPlay.reason_code``
# for the inert ranking-fallback path; tests for the precedence
# contract live at ``tests/test_reason_code_precedence_invariant.py``.
```

**After (S13-T2, Q-S13-4 LOCK):**

```python
# Q-S13-4 LOCK (DS verdict 2026-05-28, S13 plan review §B): ML-fit
# ReasonCodes (MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED) emit
# ONLY on ``PlayCard.model_card_ref.fit_warnings`` per PlayCard.
# **NEVER on ``RejectedPlay.reason_code``** — ML-fit never demotes
# between slate roles; only gates (1)-(3) above route to Considered.
# The ``fit_warnings`` List[str] channel (grammar
# ``"{LEVEL}:{substrate}"``, LEVEL ∈ {PROVISIONAL_SELECTED,
# MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED}) is the single
# audit surface for ML-fit outcomes. If a card stays in
# Recommended/Experiment, there is no ``RejectedPlay`` to attach
# to — emission on ``RejectedPlay.reason_code`` is structurally
# incoherent and would conceptually re-open a fourth demote channel
# (threatening Pivot 7 single-demote-channel). Test contract pin:
# ``tests/test_s13_ml_fit_never_demotes.py`` (runtime) +
# ``tests/test_reason_code_precedence_invariant.py::test_model_fit_codes_not_emitted_in_s10_close``
# (AST). Producer at S13-T2 in the consumer-wiring pass
# (src/predictive/consumer_wiring.py).
```

## PredictedSegment + ModelCardRef extension shape

`PredictedSegment` (extended; all defaults `None`):

```python
@dataclass
class PredictedSegment:
    segment_name: Optional[str] = None       # suppressed under stability floor
    audience_modal_share: Optional[float] = None  # uncensored audit
    n_audience: Optional[int] = None              # uncensored audit
    notes: Optional[str] = None              # legacy S6 forward-scaffold slot
```

`ModelCardRef` (extended; all defaults empty/None):

```python
@dataclass
class ModelCardRef:
    strategy_used: Optional[str] = None             # "BGNBD"|"CF"|"SURVIVAL"|"RFM"|"RECENCY"
    fit_status_chain: List[Tuple[str, str]] = field(default_factory=list)
    fit_warnings: List[str] = field(default_factory=list)  # LOCKED grammar
    notes: Optional[str] = None                     # legacy
```

The `strategy_used` field is annotated `Optional[str]` (NOT
`Literal[...]`) on the dataclass to avoid the asdict / round-trip
JSON-Literal interaction; the source-of-truth `Literal` is on
`RankingStrategyResult.strategy_used` (T1 module) and the
consumer-wiring module is the ONLY producer, so the typed-narrow
contract is preserved upstream.

## Consumer wire location — decision: Option II (post-injection mutation)

**Picked Option II** (post-injection PlayCard attribute mutation at
`src/main.py` after `apply_guardrails_to_injected`), NOT Option I
(factory threading in `build_prior_anchored_play_card`).

**Why Option II:** Option I requires threading the audience customer-ID
set through the factory, but the `Candidate` object passed into
`build_prior_anchored_play_card` does NOT carry `audience_ids` —
those live on `AudienceBuildResult` produced by the audience-builder
registry. Threading them through every Tier-B call-site (5 separate
build invocations at `src/main.py:1632-1898`) would either (a) pollute
the factory signature with kwargs unrelated to the prior-blend math
or (b) require synthesizing a sixth ID-resolution callable. Both add
factory-side complexity that doesn't serve the factory's purpose.

Option II is clean because:

1. **The Pivot 7 invariant is preserved structurally.** The
   consumer-wiring pass only mutates `pc.predicted_segment` and
   `pc.model_card_ref` (two `Optional[...]` typed slots that read
   `None` today). It does NOT append to `engine_run.recommendations`
   and does NOT append to `engine_run.considered`. Pivot 7 governs
   demote/inject channels; attribute-level mutation of an existing
   PlayCard's two unused typed slots is neither.
2. **Wire location is OUTSIDE the forbidden L1380-1597 zone.** Block
   sits after L1970 (after `apply_guardrails_to_injected`, before
   `_populate_considered`).
3. **Existing pattern reuse.** The per-play audience-IDs resolver
   re-runs the audience builder via `_get_audience_builder` exactly
   as the cannibalization-overlap recompute at L1937-1954 already
   does — no new orchestration concept introduced.
4. **Module isolation.** New code lives in
   `src/predictive/consumer_wiring.py`, NOT in the large legacy
   `src/main.py` or `src/measurement_builder.py` files (CLAUDE.md
   "Prefer adding new isolated modules over editing large legacy
   files when possible").

The dispatch brief's "Recommendation: Option I" was based on
assumption — reading the actual factory signature surfaced the
audience-IDs-not-on-Candidate constraint. Documented here per
CLAUDE.md "instrument and verify".

## AudienceIntent mapping per play_id

Hardcoded in `_INTENT_BY_PLAY_ID` at `src/predictive/consumer_wiring.py`:

| play_id | AudienceIntent | Rationale |
|---|---|---|
| `replenishment_due` | `REPLENISHMENT_TIMING` | survival → BG/NBD → CF → RFM → recency (Cox PH hazard is the right top-of-chain for next-reorder prediction). |
| `winback_dormant_cohort` | `GENERAL` | BG/NBD-first chain — expected-purchase-count over forecast horizon. |
| `discount_dependency_hygiene` | `GENERAL` | Same. |
| `cohort_journey_first_to_second` | `GENERAL` | Same. |
| `aov_lift_via_threshold_bundle` | `GENERAL` | Same. |
| (unknown play_id) | `GENERAL` (safe default) | Chain walker still produces typed result; any fall-through surfaces on fit_warnings. |

No `LOOKALIKE_EXPANSION` play is currently wired (S13 plan §B.4); the
intent is forward-compat for future ALS-driven look-alike builders.
Adding a new intent value to a play requires updating this dict only.

## Modal-segment floor implementation

Computed in `_compute_modal_segment(audience_ids, rfm_parquet_path)`:

1. Empty audience or missing parquet → `(None, None, None)`.
2. Read parquet; require `customer_id` + `segment_name` columns.
3. `audience_str = {str(x) for x in audience_ids}`; intersect with RFM
   `customer_id` (string-cast). `n_audience = scored["customer_id"].nunique()`.
4. `value_counts()` on `segment_name`; modal_name + modal_count.
5. `audience_modal_share = modal_count / n_audience`.
6. **Stability floor (DS §D.4):** `if n_audience < 50 OR
   audience_modal_share < 0.30 → return (None, audience_modal_share,
   n_audience)`. Audit fields uncensored; `segment_name` suppressed
   only.
7. Otherwise return `(modal_name, audience_modal_share, n_audience)`.

Constants `_MODAL_SEGMENT_MIN_N = 50` and
`_MODAL_SEGMENT_MIN_SHARE = 0.30` are module-level for ease of
future DS calibration. Unit tests pin all three branches:
floor-cleared, n<50, share<0.30.

## AST-aware dormancy test refactor (before/after)

**Before (S10-T3, raw regex grep):** scanned every `src/` `.py` for
the four string patterns (uppercase + lowercase variants of both
codes); allowlisted `src/engine_run.py` (definition site) and
`src/predictive/ranking_strategy.py` (T1 carve-out).

**After (S13-T2, AST walk):** parses each `src/` `.py` with the
`ast` module; walks the tree looking for two structural patterns:

1. **`Assign` / `AnnAssign`** whose target is an
   `Attribute(attr="reason_code")` AND whose value is an
   `Attribute(value=Name("ReasonCode"), attr in {"MODEL_FIT_INSUFFICIENT_DATA","MODEL_FIT_REFUSED"})`.
2. **`Call(Name("RejectedPlay"), keywords=[keyword(arg="reason_code", value=Attribute(...))])`**
   constructor invocations where the keyword value is
   `ReasonCode.MODEL_FIT_*`.

**The `ranking_strategy.py` allowlist is REMOVED** — T1's fit_warnings
emission is `result.fit_warnings.append(f"MODEL_FIT_REFUSED:{...}")`
into a `List[str]`, which is structurally NOT a
`RejectedPlay.reason_code` assignment, so the AST walk naturally
ignores it. T2's consumer-wiring module follows the same pattern.
This is the correct end state for Q-S13-4 LOCK enforcement.

The test's failure message now cites the Q-S13-4 LOCK directly and
points operators at the correct audit surface
(`PlayCard.model_card_ref.fit_warnings`).

## test_s13_ml_fit_never_demotes.py shape

Parametrized over 5 pinned fixture names:

```python
_PINNED_FIXTURES = (
    "healthy_beauty_240d",
    "healthy_supplements_240d",
    "small_store_240d",
    "cold_start_45d",
    "healthy_beauty_low_inventory_240d",
)
```

Per fixture: sets `VERTICAL_MODE` (beauty/supplements; rest from
scenario YAML) + the V2 flag stack + the new
`ENGINE_V2_PLAY_PREDICTED_SEGMENT=true`. Runs `run_scenario`;
asserts return code 0; loads `engine_run.json`; iterates
`considered` + `watching` + `recommendations` and yields
`(bucket, play_id, reason_code)` per item with a non-empty
`reason_code`. Asserts no `reason_code` value ∈
`{"model_fit_insufficient_data", "model_fit_refused"}`.

The synthetic month-2 fixture is NOT in scope at T2 — T3 introduces
it. Per DS §E.1 verbatim, T2 covers "the 5 pinned fixtures + the new
synthetic month-2 fixture"; T3 extends the parametrize list.

## briefing.html sha byte-identity (Beauty + Supplements pinned slate)

- `tests/test_slate_regression_beauty_brand.py`: **18 passed**
  (29 passed across the two slate-regression files; 2 xpassed
  pre-existing).
- `tests/test_slate_regression_supplements_brand.py`: **11 passed**.

Both pinned briefing.html shas unchanged. Renderer non-consumption
holds at flag-OFF (default) by construction (no consumer-wiring pass
runs); the renderer-non-consumption grep that pins flag-ON
non-effect on briefing.html is a T2.5 acceptance per the IM plan
§D-T2.5 — out of T2 scope.

The other 3 pinned fixtures (Micro / Mid Shopify / Small SM) are
exercised via the synthetic-fixtures families; byte-identity holds
by construction at flag-OFF because no code path is touched.

## Suite status

Targeted sweep (`engine_run or play_card or predicted_segment or
ranking_strategy or ml_fit or precedence or round_trip`):
**130 passed** in 210s. No regressions.

`tests/test_s13_ml_fit_never_demotes.py`: **5 passed** (all 5
pinned fixtures) in 59s.

`tests/test_s13_t2_predicted_segment_population.py`: **9 passed**.

`tests/test_reason_code_precedence_invariant.py`: **4 passed** (post
AST refactor).

`tests/test_s13_t1_ranking_strategy_flag.py`: **4 passed**.

Pinned slate regressions: **29 passed, 2 xpassed**.

**Full suite (`python -m pytest tests/ -q`): 2093 passed, 3 failed,
14 skipped, 4 xfailed, 2 xpassed in 1908.56s (0:31:48).**

The 3 failures are pre-existing and explicitly excluded from chase
scope per the dispatch brief and CLAUDE.md:

1. `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` —
   KI-NEW-U stale S12-T1.5 flag-default-off test.
2. `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off`
   — KI-NEW-U stale S12-T2.5 flag-default-off test.
3. `tests/test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh`
   — wall-clock flake (pre-existing, documented).

None of these regressed at T2. T1.5 baseline was 2078 passed;
T2 ships 2093 passed (+15 = 9 new unit tests + 5 ML-fit-never-demotes
runtime invariant tests + 1 net delta from adjacent stream).

## Risk assessment

- **Byte-identity at flag-OFF:** zero risk by construction —
  `populate_play_card_consumers` is NOT called when the flag is
  False. Pinned slate regressions confirm.
- **Single-demote-channel invariant (Pivot 7):** preserved. The
  consumer-wiring pass does NOT append to `recommendations` or
  `considered`. The one `apply_guardrails_to_injected` call above
  remains the only post-injection guardrails surface. AST contract
  pin enforces no `RejectedPlay.reason_code = MODEL_FIT_*` assignment.
- **Q-S13-4 LOCK enforcement:** dual-pinned. AST contract +
  5-fixture runtime contract. The runtime test is FLAG-ON, so any
  future regression that wires the codes to `RejectedPlay` will
  fire BOTH tests.
- **Modal-segment floor:** dual-cited (n<50 OR share<0.30); audit
  fields uncensored as locked.
- **Wire-location risk (Option II vs Option I):** documented +
  defended above. The choice is reversible — Option I migration in
  a future sprint would consolidate into the factory if/when the
  factory signature gains the audience-IDs threading.
- **RFM parquet path missing on pinned fixtures:** graceful
  degradation — `predicted_segment` stays `None`, `model_card_ref`
  still populates. Unit test pins this branch.
- **Forward exposure (T2.5):** atomic flag flip → first intentional
  `engine_run.json` re-pin per IM plan §D-T2.5. T2.5 brief MUST
  include: (a) atomic default flip in `src/utils.py`, (b) renderer
  non-consumption grep pin (DS §D.6 — REQUIRED, promoted from §L),
  (c) `pinned_sha_ledger.json` re-pin for `engine_run.json` (diff
  confined to predicted_segment + model_card_ref keys), (d)
  rollback contract test (flag-OFF override produces T1.5-close
  byte-identical engine_run.json), (e) positive per-fixture test
  (small_sm modal segment populates with stability-floor honesty).

## Deviation-check

**Deviation check: comment-revision-per-DS-lock-Q-S13-4**

(Per DS S13 plan review §G.5 — explicit deliberate one-line for the
`:167-171` comment revision per Q-S13-4 LOCK. This is the ONLY
non-"none" deviation-check expected in S13 per the IM plan §D-T2.)

## Recommended commit message

```
S13-T2: PlayCard consumer wiring (predicted_segment + model_card_ref) FLAG-OFF + engine_run.py:167-171 comment revision

Wires the PlayCard consumer side behind ENGINE_V2_PLAY_PREDICTED_SEGMENT
(default OFF; T2.5 owns atomic flip). Five sub-changes:

1. src/engine_run.py:167-171 comment block revised per Q-S13-4 LOCK
   (DS verdict 2026-05-28). Removed speculative RejectedPlay.reason_code
   channel; replaced with the locked model_card_ref.fit_warnings
   channel + precedence-pin reaffirmation + structural-incoherence
   rationale. ML-fit ReasonCodes NEVER on RejectedPlay.reason_code.

2. PredictedSegment + ModelCardRef dataclasses extended additively
   (4 new fields total; all Optional/default-empty). Round-trip
   helpers updated. Schema-additive within event_version=1.

3. NEW src/predictive/consumer_wiring.py: populate_play_card_consumers
   walks engine_run.recommendations, populates ModelCardRef from
   rank_audience() chain walk, computes RFM modal segment under
   DS-LOCKED stability floor (n<50 OR share<0.30 → segment_name=None).
   Pure attribute mutation; no append to recommendations/considered.

4. src/main.py post-injection callsite at L1970+ (after
   apply_guardrails_to_injected, outside the L1380-1597 forbidden
   zone). Flag-gated; per-play audience-IDs resolver mirrors the
   cannibalization-overlap pattern.

5. tests/test_reason_code_precedence_invariant.py refactored from
   raw grep to AST-aware walk; ranking_strategy.py T1 allowlist
   REMOVED. tests/test_s13_ml_fit_never_demotes.py NEW — runtime
   invariant pin across 5 pinned fixtures. tests/test_s13_t2_
   predicted_segment_population.py NEW — 9 unit tests on the
   wiring module (flag default, chain walk, fit_warnings grammar,
   modal segment populates, n<50 floor, share<0.30 floor, missing
   parquet, replenishment_due→REPLENISHMENT_TIMING, round-trip).

src/utils.py: ENGINE_V2_PLAY_PREDICTED_SEGMENT default false; added
to _coerce bool set.

Byte-identity gates: Beauty + Supplements pinned slate regressions
green (29p/2xp). Targeted sweep 130p. ML-fit-never-demotes 5p across
all pinned fixtures.

Wire location: Option II (post-injection mutation) chosen over Option I
(factory threading) because Candidate does not carry audience_ids —
threading would pollute build_prior_anchored_play_card across 5 call-
sites. Option II preserves Pivot 7 single-demote-channel structurally
(no append; attribute mutation only).

Deviation check: comment-revision-per-DS-lock-Q-S13-4
```

## Recommended T2.5 dispatch context

T2.5 is the atomic flip + first intentional engine_run.json re-pin.
The dispatch brief should cover:

1. **Flag flip** — `src/utils.py` `ENGINE_V2_PLAY_PREDICTED_SEGMENT`
   default `false → true`. Mirror S12-T2.5 / S13-T1.5 Option-a
   inline test inversion (or accept stale-test growth per
   founder preference; current Option-a precedent recommends
   inversion to avoid KI-NEW-U growth).
2. **Rollback contract test** — REQUIRED:
   `tests/test_s13_t2_5_predicted_segment_rollback.py` asserts that
   with `ENGINE_V2_PLAY_PREDICTED_SEGMENT=false` env-override, the
   engine produces byte-identical `engine_run.json` and
   `briefing.html` shas to T1.5-close per S12-T2.5 / S11-T2 cadence.
3. **Renderer non-consumption grep pin** — REQUIRED per DS §D.6
   (promoted from §L mention to T2.5 acceptance):
   `grep -rn "predicted_segment\|model_card_ref" src/briefing.py`
   returns empty. Guarantees `briefing.html` sha-unchanged claim is
   structural, not coincidental.
4. **engine_run.json re-pin** — first intentional sha change.
   `tests/fixtures/pinned_sha_ledger.json` (NEW per S13 plan §D-T2.5)
   tracks `pre_s13_t2_5` and `post_s13_t2_5` shas per fixture per
   artifact. Diff confined to PlayCard `predicted_segment` /
   `model_card_ref` keys; all other keys byte-identical (positive
   test asserts this).
5. **Positive per-fixture test** — assert `small_sm` (the only
   synthetic that VALIDATES RFM per S12-T1.5) carries a non-None
   `predicted_segment` on its PlayCards (subject to stability
   floor — operator may need to set a smaller audience or accept
   None depending on fixture size). Pivot-5-honest framing: structural
   correctness, not predictive accuracy. Per DS §G.3 the T4-CLOSE
   PIVOTS.md clarifier carries the verbatim "synthetic VALIDATED ≠
   merchant value" wording.
6. **briefing.html byte-identity assertion** at flag-ON across all
   5 pinned fixtures.

## Artifacts

- This summary: `agent_outputs/code-refactor-engineer-s13-t2-summary.md`
- New module: `src/predictive/consumer_wiring.py`
- New tests: `tests/test_s13_ml_fit_never_demotes.py`,
  `tests/test_s13_t2_predicted_segment_population.py`
- AST-refactored test: `tests/test_reason_code_precedence_invariant.py`
- No fixture / golden touches (Pivot 5 respected).
- No merchant-facing copy (Pivot 2 / Stop-Coding Line respected).
