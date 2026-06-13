# DS Architect Verdict — S7.6 CLI Wiring Gap (2026-05-23)

**Author:** ecommerce-ds-architect
**Scope:** Verdict-only. No code edits. Responds to founder finding that S7.6 observed-effect data is missing from CLI-mode `engine_run.json` despite all flags ON and tests passing.

---

## 1. Diagnosis

**Hypothesis A is FALSE on the CLI path.** All five injection blocks at `src/main.py:1321-1563` correctly pass `orders_df=g` and the per-play observed flag (`observed_effect_enabled`, `observed_replenishment_enabled`, `observed_discount_hygiene_enabled`, `observed_journey_enabled`, `observed_aov_bundle_enabled`). The plural `build_prior_anchored_recommendations` at `src/measurement_builder.py:2461-2476` threads each kwarg through to `build_prior_anchored_play_card`, which gates the helper invocations correctly at `src/measurement_builder.py:1988-2106`. The helpers run and emit a `blend_provenance` dict at `src/measurement_builder.py:2199-2240`. The mature copy ladder prefix observed in the receipts **is proof the helpers ran**: `_apply_copy_ladder` at `src/decide.py:1629-1654` returns the card unchanged when `obs_n <= 0` (line 1616), so a "Cohort signal dominates" prefix CANNOT exist unless `observed_n > 0` was actually computed. The pipeline worked.

**Hypothesis B is FALSE.** The flag resolution path through `cfg.get(...)` inside each block at `src/main.py:1352, 1396, 1444, 1497, 1554` reads at injection time, not at init — no leak.

**Hypothesis C is FALSE as a code bug, but TRUE as a schema-reading defect.** `blend_provenance` is **NOT a PlayCard attribute.** It is one named entry inside `card.drivers: List[Dict[str, Any]]` (declared at `src/engine_run.py:453`, emitted at `src/measurement_builder.py:2293, 2321, 2345`, read back at `src/decide.py:1524-1535` via `d.get("name") == "blend_provenance"`). The receipt schema in `/tmp/s76_explicit/receipts/engine_run.json` shows `blend_provenance: None` and `measurement.observed_effect: None` because whatever code path is exposing those keys in that JSON is doing `getattr(card, "blend_provenance", None)` against a PlayCard that has no such field, and similarly `measurement.observed_effect` is a separate Measurement field (`src/engine_run.py:426`) that the prior-anchored builders **do not populate** — only the `drivers[]` entry carries the observed signal. **The data IS in the run; the receipt schema does not surface it.** The system is computing the math. The audit trail is reading the wrong slot.

## 2. Fix prescription

Single, mirror-pattern change. In the prior-anchored builder at `src/measurement_builder.py` (the block that constructs the PlayCard after assembling `blend_provenance` near line 2199-2293), thread the relevant observed-effect numerics into the typed `Measurement` so they surface in the canonical receipt slot: set `Measurement.observed_effect` from the primary-window observed rate, `Measurement.n` from `observed_n`, and `Measurement.p_internal` from the L28 helper p-value carried in the `observed_windows` stash (`src/measurement_builder.py:2238`). Do NOT add a top-level `blend_provenance` attribute to PlayCard — `drivers[]` remains the source of truth and `_blend_provenance_for_card` keeps working byte-identically for decide.py consumers. This mirrors the existing pattern at `src/engine_run.py:426, 839` where `Measurement.observed_effect` is already the documented receipt-surface field (per `src/engine_run.py:27` docstring).

## 3. Missing tripwire test

In `tests/test_s7_6_c1_priority_prepend_invariant.py` (or new `tests/test_s7_6_cli_observed_surface_invariant.py`), add a test that runs the full `main.run_action_engine` (or its CLI entrypoint) on `tests/fixtures/synthetic/healthy_beauty_240d_orders.csv` with all `ENGINE_V2_OBSERVED_EFFECT_*` + `ENGINE_V2_BUILDER_*` flags ON, reads back `receipts/engine_run.json`, and asserts: for every Tier-B Recommended card whose `play_id` matches the four wired builders, **(a)** `card.drivers` contains an entry with `name == "blend_provenance"` AND `observed_n > 0`, AND **(b)** `card.measurement.observed_effect is not None` AND `card.measurement.n > 0`. Both assertions are required — (a) catches helper-invocation regressions, (b) catches the receipt-surfacing regression that the current implementation exhibits and that no existing test pins.

---

**Refactor agent should populate `Measurement.observed_effect`, `Measurement.n`, and `Measurement.p_internal` from the existing `blend_provenance` stash inside `build_prior_anchored_play_card` at `src/measurement_builder.py:2199-2293`, and add the two-clause CLI-mode tripwire test described above — no other deviation.**

---

**Key file paths referenced:**
- `src/main.py:1321-1563` (5 injection blocks — wiring confirmed correct)
- `src/measurement_builder.py:1988-2106, 2199-2293, 2461-2476` (helper invocation + blend_provenance assembly)
- `src/decide.py:1524-1535, 1616, 1629-1654` (blend_provenance read + copy ladder mature-state gate)
- `src/engine_run.py:426, 453, 839` (Measurement.observed_effect, PlayCard.drivers schema)
- `/tmp/s76_explicit/receipts/engine_run.json` (verified failing output)
- `tests/test_s7_6_c1_priority_prepend_invariant.py` (target for new tripwire test)
