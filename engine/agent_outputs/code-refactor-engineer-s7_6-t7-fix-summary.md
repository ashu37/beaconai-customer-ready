# S7.6-T7-FIX — re-invoke gate_materiality on V2 prior-anchored cards

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `6f8b891`

---

## 1. Ticket scope

Close provenance gap: V2-injected cards previously laundered as `CAP_EXCEEDED` now route through `MATERIALITY_BELOW_FLOOR` with truthful p50-vs-floor reason. Addresses memory.md "engine output is structurally anemic" note (2026-04-30).

DS-diagnosed root cause: `apply_guardrails` ran before V2 injection (`main.py:994` before `:1480`), so V2 cards never faced the materiality gate. Smallest scoped fix per DS recommendation; no gates/floors/priors tuned.

Implementation: snapshot recommendation play_ids BEFORE any prior-anchored V2 builder injects, then re-invoke `gate_materiality` on the newly-injected V2 cards only (cards in the pre-snapshot are deliberately skipped — they already went through `apply_guardrails`). Mirrors the `MATERIALITY_FLOOR_SCALE_AWARE` gate inside `apply_guardrails()` at `guardrails.py:822-846`: same flag, same profile-floor resolution (`ENGINE_V2_STORE_PROFILE` + `store_profile.gate_calibration.materiality_floor_usd`), same `gate_materiality()` function.

Always-on (no new flag) — there is no scenario where sub-floor cards should be laundered as `CAP_EXCEEDED`.

**Subsequently superseded by S7.6-C2 (`6d248fd`)** which generalized the helper to `apply_guardrails_to_injected` covering inventory + materiality + cannibalization + portfolio-cap + recently-run. T7-FIX is the materiality-only precedent that motivated the broader C2 helper.

## 2. Files changed

- `src/main.py` (+92 lines): pre-snapshot + materiality re-invocation block at `~L1525`.

## 3. Behavior change

V2 prior-anchored cards with `p50` below the scale-aware materiality floor now route to Considered with `MATERIALITY_BELOW_FLOOR` reason instead of being silently truncated as `CAP_EXCEEDED`. Provenance is now truthful end-to-end.

Pinned-fixture impact: not recorded in this commit message (subsequently C2 + C3 cascade re-pins captured the full sha256 chain).

## 4. Tests added / modified

Not recorded in commit message. (Suite delta and any new test files not captured by the commit body.)

## 5. Risks + mitigations

- **Helper hand-rolled** in main.py; later refactored at C2 into a single helper exported from `src/guardrails.py`. Single-call-site code duplication was the trade-off accepted for the smallest scoped fix.

## 6. Follow-ups / known-issues opened

- **S7.6-C2 (`6d248fd`)** generalized to `apply_guardrails_to_injected` (inventory + materiality + cannibalization + portfolio-cap + recently-run). T7-FIX was the narrow precedent.

## Process lesson

This ticket is the origin of the CLAUDE.md "instrument-before-fix" rule (locked 2026-05-22 in the Subagent Handoff Discipline section). The T7.5 dispatch went through a three-strike spiral: three consecutive predictions about where the AOV-bundle Tier-B card died were each wrong (first: "materiality bypass" — partial truth, the fix here; second: "silent early-return" — wrong location; third: "injection storm" — wrong mechanism). Only after the founder authored an in-process probe (`scripts/s7_6_t7_5_inproc_probe.py`) did the actual gate surface: it was the `populate_considered_from_candidates` cap-trim at `decide.py:825-842` that silently dropped the card behind 6 legacy guardrail rejections (closed at S7.6-FIX `bb9fd32`). The CLAUDE.md rule "Two failed predictions = stop guessing" exists because of this spiral.

## 7. Commit ref

`6f8b891`
