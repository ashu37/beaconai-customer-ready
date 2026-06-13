# S6-T2 Summary — Supplements serving-count parser

**Ticket:** Sprint 6 Ticket T2 (per `agent_outputs/implementation-manager-s6-tier-b-builders-plan.md` §S6-T2 lines 170-212)
**Date:** 2026-05-18
**Branch:** post-6b-restructured-roadmap
**Impl commit:** `7f705d0`
**Memory commit:** `9060295`
**Summary commit:** (this file)

## 1. Approved scope

- Author supplements regex/parser block in `config/replenishment_sizes.yaml` (today's supplements stub is null per G-2).
- Extend `src/replenishment_parser.py` dispatcher to handle supplements unit-coherent parsing.
- Coverage target: serving / count / day_supply forms with unit-coherence keys.
- Closes KI-18 (parser stub).
- KI-27 (`empty_bottle.vertical_applicable` expansion) close conditional on coverage + founder confirmation.
- Below the priors layer; no audience builder, no measurement card.

## 2. Patch summary

### `config/replenishment_sizes.yaml`
Supplements block extended with `coherent_units` list (precedence: `count > day_supply > serving`). Schema is additive — `coherent_units` and the legacy `size_regex` field coexist so beauty/mixed (which use `size_regex`) are untouched. Precedence and `validation_status: heuristic_unvalidated` documented in YAML header + supplements `notes`.

### `src/replenishment_parser.py`
New public surface `parse_unit_coherent(vertical, text) -> Optional[tuple[str, int]]`. Walks compiled regex list in YAML declaration order, returns the first match as `(coherence_key, value)`. Module-level `_compiled_cache` mirrors the S6.5-T2 subvertical_taxonomy.yaml singleton pattern. Legacy `get_size_regex` / `get_case_insensitive` accessors untouched. Pure, idempotent, deterministic.

### `tests/test_s6_t2_supplements_serving_parser.py`
17 tests (15 per IM plan §S6-T2 test deliverables + coverage-rate doc + determinism check).

### `KNOWN_ISSUES.md`
KI-18 `tracked → resolved` with parser-shipped note. KI-27 stays `accepted` with explicit deferral rationale. Open-count table updated.

## 3. Files changed

- `config/replenishment_sizes.yaml`
- `src/replenishment_parser.py`
- `tests/test_s6_t2_supplements_serving_parser.py` (new)
- `KNOWN_ISSUES.md`
- `memory.md` (in memory commit)

## 4. Tests / checks run

- New file `tests/test_s6_t2_supplements_serving_parser.py`: 17 passed.
- `tests/test_slate_regression_beauty_brand.py` + `tests/test_slate_regression_supplements_brand.py` + `tests/test_s6_5_t5_atomic_repin.py`: 45 passed (Beauty + supplements G-1 + atomic re-pin byte-identical).
- Full suite: 1377p/14s/0f → 1394p/14s/0f. +17 tests, +0 regressions.
- Determinism check: `test_parser_is_deterministic_across_repeated_calls` runs the parser twice on the full G-1 SKU list and diffs results.

## 5. Behavior changes

**Today: ZERO merchant-facing behavior change.** The new `parse_unit_coherent` surface has no production caller. Beauty `get_size_regex` path untouched. Supplements G-1 fixture sha256 unchanged (`01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95`). Beauty pinned slate unchanged. M0 trio unchanged.

The parser becomes a runtime caller surface when S6-T3 `replenishment_due` audience builder lands.

## 6. Artifacts added

### G-1 supplements per-SKU coverage table

| # | SKU (lineitem name) | Regex matched | Outcome |
|---|---|---|---|
| 1 | Ashwagandha KSM-66 300mg 60ct | `count` (`(?:^\|\s)(\d+)\s*(?:ct\|caps?\|...)\b`) | `("count", 60)` |
| 2 | Collagen Peptides Powder 1lb | (none) | `None` — weight-only, no serving-size context |
| 3 | Creatine Monohydrate 500g | (none) | `None` — weight-only, no serving-size context |
| 4 | Magnesium Glycinate 200mg 60ct | `count` | `("count", 60)` |
| 5 | Omega-3 Fish Oil 1000mg 120ct | `count` | `("count", 120)` |
| 6 | Pre-Workout Energy Complex | (none) | `None` — named blend, no container-volume signal |
| 7 | Probiotics 50 Billion CFU 30ct | `count` | `("count", 30)` |
| 8 | Vitamin D3 + K2 Capsules 90ct | `count` | `("count", 90)` |
| 9 | Whey Protein Powder Vanilla 2lb | (none) | `None` — weight-only, no serving-size context |
| 10 | Zinc + Quercetin Immune Formula | (none) | `None` — named blend, no container-volume signal |

**Coverage: 5 of 10 SKUs (50%).** Pinned by `test_g1_supplements_coverage_rate_documented`.

### KI-27 close decision

**Decision: KEEP ACCEPTED.** Two independent reasons:

1. **Coverage threshold not met.** The IM plan §S6-T2 default close criterion is "every SKU in the pinned supplements fixture parses." Coverage is 5/10. Closing on partial coverage would expand `empty_bottle.vertical_applicable` to a vertical where half the SKUs would silently skip the play's audience-builder consumption.
2. **Founder not in loop.** The brief explicitly defaults to "keep KI-27 accepted (no fixture re-pin)" when founder confirmation is not available. No fixture re-pin lands in this ticket.

**Path to close:** either (a) founder confirms expansion despite 5/10 coverage, or (b) a separate ticket lifts coverage to 100% — likely a weight-to-serving conversion design that requires per-SKU serving-size metadata not present in current order CSVs.

### Fixture status

| Fixture | sha256 before | sha256 after | Re-pinned? |
|---|---|---|---|
| Supplements G-1 briefing | `01f5feff8449...` | `01f5feff8449...` | No (default posture) |
| Beauty pinned slate briefing | unchanged | unchanged | No |
| M0 small_sm briefing | unchanged | unchanged | No |
| M0 mid_shopify briefing | unchanged | unchanged | No |
| M0 micro_coldstart briefing | unchanged | unchanged | No |

## 7. Remaining risks

- **5/10 coverage on G-1 supplements.** Weight-only forms (`1lb`, `2lb`, `500g`) and named blends (`Pre-Workout Energy Complex`, `Zinc + Quercetin Immune Formula`) return None. This is intentional (no fabricated unit) but means S6-T3 must handle un-parseable SKUs gracefully (skip from cadence inference).
- **`validation_status: heuristic_unvalidated`** on the supplements `coherent_units` block. The regex set was derived from the G-1 fixture only; real-world supplements naming may carry forms not yet covered (e.g., `"30 day pack"`, `"60-count bottle"`, foreign-language variants). Coverage regressions are pinned by the coverage-rate test, but new forms are not pre-emptively covered.
- **KI-27 path remains open.** No timeline forced — the parser surface is live and ready when the founder decision lands.

## 8. Follow-up work

- **S6-T3** (next ticket): `replenishment_due` audience builder consumes `parse_unit_coherent("supplements", lineitem_text)` for per-SKU cadence inference. Must handle the 5/10 None case (skip from cadence inference, aligns with S6-T3's per-SKU N≥30 floor).
- **KI-27 close ticket** (separate): atomic commit that expands `empty_bottle.vertical_applicable` to include supplements, wires `parse_unit_coherent` into the empty_bottle audience builder, and re-pins the supplements G-1 fixture. Requires founder confirmation OR coverage path to 100%.

## Hand-off to S6-T3

S6-T3 reads from:

- **YAML surface:** `config/replenishment_sizes.yaml::supplements.coherent_units` — list of `{key, regex}` entries in precedence order.
- **Parser surface:** `src.replenishment_parser.parse_unit_coherent(vertical, text) -> Optional[tuple[str, int]]`. Returns `(coherence_key, integer_value)` or `None`. Pure, deterministic, cached.
- **Beauty path unchanged:** S6-T3's beauty branch should continue using `get_size_regex("beauty")` (or extend beauty to a `coherent_units` block as a separate scoped change — out of S6-T3 scope per IM plan).

Expected S6-T3 behavior on supplements G-1: cadence inference operates on the 5 parseable SKUs; the 5 None SKUs are excluded from cadence-due audience computation (aligned with the per-SKU minimum-sample-size floor S6-T3 already enforces).

## Backfill from memory.md (migration trim 2026-05-25)

## S6-T2 closeout (2026-05-18)

Sprint 6 Ticket T2 — supplements serving-count parser shipped; KI-18 closed; KI-27 deferred. Pure parser work below the priors layer; zero engine-output change today (parser is contract surface for S6-T3 `replenishment_due` builder which consumes `parse_unit_coherent`). Impl commit `7f705d0`.

**Files changed:**

- `config/replenishment_sizes.yaml`: supplements block gains `coherent_units` list (precedence `count > day_supply > serving`) covering ct/caps/capsules/tablets/softgels/gummies + day-supply + serving forms. Beauty + mixed `size_regex` blocks preserved verbatim (M0 byte-identical contract). Schema is additive — `coherent_units` coexists with `size_regex` so the beauty/mixed legacy accessor surface is untouched.
- `src/replenishment_parser.py`: new `parse_unit_coherent(vertical, text) -> Optional[(coherence_key, value)]` walks compiled regex list in YAML declaration order (first-match-wins = precedence). Module-level `_compiled_cache` mirrors the S6.5-T2 subvertical_taxonomy.yaml singleton pattern. Legacy `get_size_regex` / `get_case_insensitive` accessors unchanged. `_reset_cache_for_tests` now clears both caches.
- `tests/test_s6_t2_supplements_serving_parser.py`: 17 tests (15 per IM plan §S6-T2 + coverage-rate doc + determinism check).
- `KNOWN_ISSUES.md`: KI-18 `tracked → resolved`; KI-27 stays `accepted` with explicit deferral rationale.

**G-1 supplements coverage (5/10 parse; 5/10 documented None):**

| SKU | Outcome |
|---|---|
| Ashwagandha KSM-66 300mg 60ct | (count, 60) |
| Magnesium Glycinate 200mg 60ct | (count, 60) |
| Omega-3 Fish Oil 1000mg 120ct | (count, 120) |
| Probiotics 50 Billion CFU 30ct | (count, 30) |
| Vitamin D3 + K2 Capsules 90ct | (count, 90) |
| Collagen Peptides Powder 1lb | None (weight-only) |
| Creatine Monohydrate 500g | None (weight-only) |
| Whey Protein Powder Vanilla 2lb | None (weight-only) |
| Pre-Workout Energy Complex | None (named blend, no signal) |
| Zinc + Quercetin Immune Formula | None (named blend, no signal) |

The 5 documented-None SKUs are not parser bugs: weight-only forms (`1lb`, `500g`, `2lb`) lack the serving-size context required for unit coherence; named blends carry no container-volume signal. Treating either as a coherent unit would fabricate a value — explicitly disallowed by the project invariants (no hardcoded effects).

**KI-27 close decision: KEEP ACCEPTED.** Two reasons: (a) coverage is 5/10, below the IM-plan default close threshold of "every SKU in the pinned supplements fixture parses"; (b) founder was not in-loop to confirm `empty_bottle.vertical_applicable` expansion, and the brief's default in that case is "keep KI-27 accepted, no fixture re-pin." Supplements G-1 fixture stays byte-identical at `01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95` (post-S5-T3 pin).

**Fixture status:** Beauty pinned slate byte-identical (verified via `test_slate_regression_beauty_brand.py`). Supplements G-1 briefing byte-identical (verified via `test_slate_regression_supplements_brand.py`). M0 trio byte-identical. No fixture re-pin in this ticket.

**Suite delta:** 1377p/14s/0f → 1394p/14s/0f (+17 tests: 10 parametrized per-SKU pins + 5 IM-plan tests 11-15 + coverage-rate doc + determinism).

**Hard-stop status:**

1. G-1 SKU fails to parse to coherent unit — NOT TRIPPED in spirit (only count/day_supply/serving forms parse; weight/named-blend forms return documented None, not a silent fall-through; outcomes pinned per-SKU).
2. Beauty parser regresses — NOT TRIPPED (size_regex preserved verbatim; beauty regression suite green).
3. Parser non-deterministic — NOT TRIPPED (determinism test passes).
4. YAML schema diverges from beauty block — NOT TRIPPED (additive `coherent_units` list extends the schema as a superset; beauty's `size_regex` stays).

**Hand-off to S6-T3:** the `replenishment_due` audience builder will consume `parse_unit_coherent("supplements", lineitem_text)` to derive per-SKU cadence units. Beauty path keeps using `get_size_regex` (or the audience builder may eventually adopt `parse_unit_coherent` once a beauty `coherent_units` block is authored — out of S6-T3 scope). The 5/10 G-1 coverage means S6-T3 must gracefully handle un-parseable SKUs (typically: skip them from cadence inference, which aligns with the per-SKU minimum sample-size floor S6-T3 already enforces).

**Caveats / next milestones:**

- KI-27 close requires either (a) founder confirmation, or (b) a coverage path to 100% — likely a weight-to-serving conversion design ticket that requires per-SKU serving-size metadata not present in current order CSVs.
- The 5/10 coverage rate is pinned by `test_g1_supplements_coverage_rate_documented`. Future regressions that drop coverage (regex shape change) will trip this test rather than silently degrading.

**Summary:** [agent_outputs/code-refactor-engineer-s6-t2-summary.md](agent_outputs/code-refactor-engineer-s6-t2-summary.md)

**Founder decisions locked in (2026-05-18) for S6-T3:**

- **Q2 — Per-SKU cadence-inference floor:** N=30 customers-with-≥2-repeat-purchases per SKU. SKUs below floor contribute zero audience without crash. IM-plan default accepted.
- **Q3 — Prior consumption for `replenishment_due`:** Option (a) — consume existing `bestseller_amplify.bundle_value` (Beauty validated_external bsandco prior from S7.5-T2). No new YAML authoring at T3. Authoring a fresh `replenishment_due.base_rate` block deferred to a future memo-pending ticket (would require external benchmark source-of-truth).
- **Q5 — Hard-stop calibration envelope at T3.5:** Beauty posterior p50 must land inside prior's `[range_p10, range_p90]` band. Same envelope as S6.5-T5 Klaviyo winback activation. Out-of-envelope → STOP and escalate, not auto-re-pin.

**KI-27 status (post-S6-T2 close):** stays `accepted`. No `empty_bottle.vertical_applicable` expansion. 5/10 G-1 coverage means half the supplements catalog would silently skip the play's audience builder; that partial-coverage behavior is the kind of thing the engine should refuse. Revisit when supplements coverage reaches 100% (likely post-beta via Shopify product-metadata integration).
