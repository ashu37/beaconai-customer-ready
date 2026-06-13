# code-refactor-engineer — S13.6-T8 summary (sprint close)

**Ticket:** S13.6-T8 — sprint close (renderer rewire + documentation hardening)
**Date:** 2026-06-01
**Branch:** post-6b-restructured-roadmap
**Status:** COMPLETE

---

## Approved scope

Eight sub-tasks comprising the S13.6 sprint close:
1. `storytelling_v2.py` — retire YAML-lookup fallback; renderer reads `PlayCard.mechanism_intent` typed atom directly.
2. `PIVOTS.md` — Pivot 2 T6/T8 addendum.
3. `docs/engine_flags.md` — standalone `INCLUDE_DEBUG_FIELDS` section.
4. `docs/DECISIONS.md` — D-S13.6-1 through D-S13.6-5 locked.
5. `ROADMAP.md` — S13.6 SHIPPED 2026-06-01.
6. `STATE.md` — §10 output contract surface (v2.0.0 frozen).
7. `memory.md` — S13.6-T7.5 and S13.6-T8 sprint-close entries.
8. `KNOWN_ISSUES.md` — confirm KI-NEW-AA and KI-NEW-AB.

---

## Patch summary

### Sub-task 1: `src/storytelling_v2.py` rewire

**What changed:**
- Added `MechanismIntent` to the `from .engine_run import (...)` block.
- Deleted `_mechanism_for_play` function entirely (was 24 lines; lazy YAML lookup via `priors_loader.get_mechanism`). All 3 call sites eliminated first.
- Updated `_render_what_we_send` docstring to document that callers now pass `mechanism_intent.type.value` (enum string) or `None`.
- Rewired `_render_measured_card` call site (Recommended Now): replaced `_render_what_we_send(_mechanism_for_play(card.play_id))` with `_render_what_we_send(_mi.type.value if isinstance(_mi, MechanismIntent) else None)`.
- Rewired `_render_recommended_experiment_card` call site (Recommended Experiment): same pattern.
- Retired the T6 shim in `render_rejected_card`: the `elif isinstance(mechanism_raw, str): ... else: mechanism = _mechanism_for_play(...)` branch replaced with `if isinstance(mechanism_raw, MechanismIntent): mechanism = mechanism_raw.type.value else: mechanism = None`.
- Updated `_rej_has_t3z_fields` comment block to reference T8 (was T6 shim language).
- Updated `render_rejected_card` docstring to remove reference to YAML-lookup fallback.

**Finding:** The T6 summary (line 57) documented exactly the shim that T8 was expected to remove: "when the producer emitted a typed `MechanismIntent`, the renderer falls back to the `_mechanism_for_play(rej.play_id)` YAML lookup." The shim was present as described. The Recommended Now and Experiment call sites also still called `_mechanism_for_play(card.play_id)` rather than reading `card.mechanism_intent` — both were part of the rewire scope.

**Behavior change:** The `briefing.html` mechanism line for Recommended Now, Recommended Experiment, and Considered cards now shows the typed enum value string (e.g., `WINBACK_REACTIVATION_EMAIL`) when `mechanism_intent` is populated, and nothing when it is `None`. Previously, Recommended Now and Experiment cards always did a YAML lookup by `play_id` (which could surface a prose string from `priors.yaml`); Considered cards with a typed `MechanismIntent` also did a YAML lookup. Post-T8, all three card types read the typed contract atom directly.

### Sub-task 2: `PIVOTS.md`

Added S13.6-T6/T8 addendum after the S13.6-T1a addendum on Pivot 2. Text is verbatim from the ticket brief.

### Sub-task 3: `docs/engine_flags.md`

Added standalone `## INCLUDE_DEBUG_FIELDS` section with the 5-field format from the ticket brief. The flag was already catalogued in the V2 surface flags table (row added at S13.6-T1a); this section provides the expanded narrative entry that matches the other named-flag sections in the document.

### Sub-task 4: `docs/DECISIONS.md`

Added D-S13.6-1 through D-S13.6-5 immediately before D-S6-5 (after D-S13-5). Each entry follows the standard DECISIONS.md format with Status / Date locked / Decision / Why / Source-of-truth / Pinning tests / Safe to adjust / Cross-link fields.

Updated `Last updated` footer to prepend the T8 close note.

### Sub-task 5: `ROADMAP.md`

- Added `**S13.6 just closed (SHIPPED 2026-06-01).**` paragraph in the §1 Current sprint section.
- Added S13.6 row to the §2 beta-blocking sequence table.

**No other roadmap entries changed.**

### Sub-task 6: `STATE.md`

- Updated `Last refresh` date: `2026-05-29 → 2026-06-01`.
- Updated §8 Surface `engine_run.py` bullet to note v2.0.0 frozen at S13.6 and point to new §10.
- Added new **§10 Output contract surface (post-S13.6, v2.0.0 frozen)** section documenting: prose strip, `MechanismIntent`, RULE A null-reason pattern, `INCLUDE_DEBUG_FIELDS`, single-file authority, and the 3 pinning tests for S13.6 contract invariants.

### Sub-task 7: `memory.md`

Added two entries (template-compliant, ≤15 lines each):
- `S13.6-T7.5` — commit `015dd06` (null-reason enum registry).
- `S13.6-T8` — commit `<T8-SHA>` placeholder (this sprint close).

Both entries placed immediately before the existing `S13-CLOSE` entry.

### Sub-task 8: `KNOWN_ISSUES.md`

KI-NEW-AA and KI-NEW-AB are correctly filed and accurate per T7a work. No corrections needed.
- KI-NEW-AA: `EngineRun.store_profile` paired-null-reason gap, deferred to S13.7-T7b. Status, description, proposed fix, closure trigger, and cross-links are all accurate.
- KI-NEW-AB: `targeting_non_causal_prior` legacy producer dead-code, deferred to S13.7 dead-code sweep. DS Q8 adjudication verbatim is present and accurate.

Updated `Last updated` footer to prepend the T8 confirmation note.

---

## Files changed

| File | Change |
|---|---|
| `src/storytelling_v2.py` | Add `MechanismIntent` import; delete `_mechanism_for_play`; rewire 2 Recommended card call sites + RejectedPlay shim; update docstrings/comments. |
| `PIVOTS.md` | Pivot 2: T6/T8 addendum appended. |
| `docs/engine_flags.md` | Standalone `## INCLUDE_DEBUG_FIELDS` section added. |
| `docs/DECISIONS.md` | D-S13.6-1 through D-S13.6-5 added; `Last updated` footer prepended. |
| `ROADMAP.md` | S13.6 SHIPPED paragraph + table row added. |
| `STATE.md` | `Last refresh` updated; §8 Surface bullet updated; §10 contract surface section added. |
| `memory.md` | S13.6-T7.5 and S13.6-T8 entries added. |
| `KNOWN_ISSUES.md` | `Last updated` footer prepended; KI-NEW-AA/AB confirmed correct (no text changes). |
| `agent_outputs/code-refactor-engineer-s13.6-t8-summary.md` | NEW (this file). |

---

## Tests / checks run

- `python -m pytest tests/test_s13_6_t6_mechanism_intent_atom.py tests/test_null_reason_registry.py tests/test_s7_6_c1_priority_prepend_invariant.py -x -q` — **37 passed, 2 xfailed** (31.76s).
- `python -m pytest tests/ -x -q` (full suite) — **596 passed, 1 failed (pre-existing), 7 skipped** (477.90s).

Pre-existing failure: `tests/test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section` — asserts `"Would fire" in html`; `would_fire_if` prose slot was stripped at S13.6-T1a (Pivot 2). Confirmed pre-existing via T7.5 summary. Not introduced by T8.

Pass count unchanged from T7.5 (596 passed). No regressions.

---

## Behavior changes

**Runtime (engine output):**
- `briefing.html` mechanism lines for Recommended Now / Experiment / Considered cards now show the typed `MechanismType` enum string (e.g., `WINBACK_REACTIVATION_EMAIL`) when `mechanism_intent` is populated, `None`/empty when absent.
- No change to `engine_run.json` (renderer-only change; no dataclass shape edits).
- No change to the 5 pinned fixture SHA ledger entries (SHA ledger pins `engine_run.json`, not `briefing.html`).

**Documentation:**
- PIVOTS.md, ROADMAP.md, STATE.md, DECISIONS.md, engine_flags.md, KNOWN_ISSUES.md, memory.md all updated to reflect S13.6 sprint close.

---

## Artifacts added

- `agent_outputs/code-refactor-engineer-s13.6-t8-summary.md` (this file)

---

## Remaining risks

1. **`briefing.html` mechanism line shows enum key string, not human-readable copy.** Post-T8, the rendered mechanism for a card is `WINBACK_REACTIVATION_EMAIL` (enum value), not "We'd send a reactivation email to dormant customers" (prose). This is correct per Pivot 2 and the Stop-Coding Line — the briefing.html is debug-only, and narration agents downstream will compose prose from the typed atom. No merchant-facing risk (briefing.html is not the product surface).
2. **`_surface_mechanism_for_play` in `decide.py` still exists** (retained at T6 per DS Q3c as a renderer-side debug-fallback until T8). Now that T8 has retired the renderer's use of it, `_surface_mechanism_for_play` in `decide.py` is no longer called by any live renderer code path. The function is not harmful (it's an internal helper), but it is now dead code. Cleanup deferred to S13.7 dead-code sweep alongside KI-NEW-AB.
3. **4 deferred null-reason pairs (StoreProfile / ModelCard / CohortDiagnostics / CustomerIds) remain open.** KI-NEW-AA (StoreProfile) is the highest-priority gap — `ENGINE_V2_STORE_PROFILE` is default-ON, meaning `store_profile=None` under default flags signals a builder failure without a typed reason. S13.7-T7b owns the closure.

---

## Follow-up work

- **S13.7-T7b:** `StoreProfileNullReason` paired enum + `EngineRun.store_profile_null_reason` field (KI-NEW-AA). Also covers ModelCard / CohortDiagnostics / CustomerIds null-reason gaps.
- **S13.7 dead-code sweep:** `decide.py::_surface_mechanism_for_play` removal (now renderer-unused); `sizing.py` `targeting_non_causal_prior` legacy producer path (KI-NEW-AB).
- **S13.7-T3:** `docs/mechanism_contract.md` — per-type `parameters` dict shape spec for narration agents.
- **S14+:** flesh out Tier-B `parameters` dicts (currently `None` with `TODO(S14)` markers for THRESHOLD_BUNDLE_OFFER / DISCOUNT_DEPENDENCY_HYGIENE / REPLENISHMENT_REMINDER).

---

## Deviation check

none
