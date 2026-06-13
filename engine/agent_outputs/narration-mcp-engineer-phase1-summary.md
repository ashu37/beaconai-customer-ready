# Narration MCP — Phase 1 summary

**Owner:** narration-mcp-engineer
**Phase:** 1 (handoff_architecture.md §5). Deps: Phase 0 (fixture DONE).
**Status:** built end-to-end, runs in MOCK mode with NO `ANTHROPIC_API_KEY` and NO SDKs installed. NOT committed (left unstaged for orchestrator + DS review).

## Contract sections coded against

- `docs/handoff_architecture.md` §2a (manifest-pointer resolution), §2b (narration consume/emit), §3 (stdio transport), §7 locks **1/2/3/6/7/8** (mine).
- `docs/mechanism_contract.md` — per-`MechanismType` entries + **RULE A** (None mechanism ⇒ no mechanism line) + Tier-B `{}` note + the 3 TODO(S14) None-param types (`THRESHOLD_BUNDLE_OFFER`, `DISCOUNT_DEPENDENCY_HYGIENE`, `REPLENISHMENT_REMINDER`).
- `src/engine_run.py` — schema authority; all types imported, none hand-rolled. Parsed via `EngineRun.from_dict`.
- `PRODUCT.md` §4 (Stop-Coding Line: engine emits typed, swarm narrates, swarm invents no numbers).

## What was built

A new package `src/mcp/narration/` (SDK-free at import; `anthropic` + `mcp` imported lazily):

| File | Role |
|---|---|
| `src/mcp/__init__.py` | MCP servers package marker |
| `src/mcp/narration/__init__.py` | package exports (all SDK-free) |
| `src/mcp/narration/config.py` | model/env config; no key required at import |
| `src/mcp/narration/run_locator.py` | manifest-pointer resolution + validate + parse (schema authority) |
| `src/mcp/narration/atoms.py` | lock-aware projection: input boundary half of the locks |
| `src/mcp/narration/llm_client.py` | injectable `LLMClient` protocol + `MockLLMClient` + `AnthropicLLMClient` (prompt caching) |
| `src/mcp/narration/guards.py` | output-validation guards: output half of the locks (incl. L8 dollar scrubber) + safe fallback |
| `src/mcp/narration/narrator.py` | orchestrates prompt -> LLM -> parse -> guards -> fail-closed |
| `src/mcp/narration/server.py` | MCP stdio server (`narrate_run`, `narrate_card` tools); pure `narrate_*_payload` functions are SDK-free + unit-testable |

Tests added:
- `tests/test_narration_mcp_locks.py` — 18 KI-FE-7 synthetic-fixture lock tests (mock LLM, no key).
- `tests/test_narration_mcp_smoke.py` — 6 smoke tests resolving `small_sm` via the manifest pointer and narrating through the mock.

`requirements.txt` — added `jsonschema` (was already used by the validator) + noted `anthropic` and `mcp` as OPTIONAL lazily-imported runtime deps.

## Lock -> guard mapping (two-layer enforcement)

Each lock is enforced at BOTH the input boundary (atoms projection: the LLM never sees the footgun) AND the output boundary (guards: verify what the LLM returned). Output guards FAIL CLOSED — on any violation the narrator drops the unverified output and emits a deterministic safe fallback line.

| Lock | Input boundary (`atoms.py`) | Output guard (`guards.py`) |
|---|---|---|
| **L1** evidence_source only, never evidence_class | `evidence_class` is never copied into `CardAtoms`; only the `evidence_source` chip is projected | `check_no_evidence_class_leak` rejects overclaim phrasings ("we measured this on your store", "evidence class") |
| **L2** STORE_OBSERVED revenue is NOT lift | non-STORE_MEASURED + allowed dollars ⇒ `revenue_note` carries explicit "NOT lift / NOT incremental" framing | `check_no_lift_framing` rejects lift/incremental/expected-from-sending terms on non-STORE_MEASURED cards |
| **L3** fit_warnings audit-only | `model_card_ref.fit_warnings` is never copied into the projection | `check_no_fit_warning_leak` rejects MODEL_FIT_REFUSED / BG-NBD / model-fallback vocabulary |
| **L6** no AOV; segment only from PlayCard | segment read only from `PlayCard.predicted_segment.segment_name` (floor-honoring); no CSV `aov_individual`/`predicted_segment` (not on EngineRun anyway) | `check_no_aov_or_csv_segment` rejects AOV vocabulary |
| **L7 / RULE A** None mechanism / None-param / Tier-B {} | `mechanism_intent is None` ⇒ `mechanism=None` (no line); None-valued params are dropped at projection; `{}`-param Tier-B types ⇒ type named, `parameters={}` | `check_no_fabricated_mechanism` rejects any mechanism line when `mechanism is None` |
| **L8** dollar gate (master) | `allowed_dollar_figures` populated ONLY from a non-suppressed, `source=BLEND`, p10/p50/p90-present `revenue_range`; suppressed/non-BLEND/None ⇒ empty + explanatory `revenue_note` | `scrub_dollar_figures` rejects ANY `$` figure not traceable (with rounding tolerance) to `allowed_dollar_figures`; fails closed to a no-dollar fallback |

Note on the canonical fixture: `small_sm`'s one card (`bestseller_amplify`) has `revenue_range.source = None` (NOT `BLEND`) and `evidence_source = None`. Per L8 this means **no dollar figure is emittable for it** — the smoke test pins exactly that (`"$" not in` the prose). This is the correct, conservative behavior.

## How mock mode works

- `Narrator` takes an injected `LLMClient`; default is `MockLLMClient` (deterministic, no network).
- `MockLLMClient` reads the `<atoms>...</atoms>` JSON the narrator embeds in the user message and emits a safe 3-key JSON narration that, by construction, states a dollar figure only if `allowed_dollar_figures` is non-empty and writes no mechanism line when `mechanism is None`. So happy-path tests assert real lock conformance, not a fixed string.
- A `responder` callable can be injected into `MockLLMClient` to simulate a MISBEHAVING LLM (fabricated dollar, invented mechanism, lift framing, fit-warning leak). Those tests prove the guards trip and the narrator falls back — this is what makes the locks structural, not prompt-dependent.
- `server._default_llm` returns `AnthropicLLMClient` only when `ANTHROPIC_API_KEY` is present; otherwise `MockLLMClient`. `AnthropicLLMClient` constructs without a key and raises only if `complete()` is called keyless (fail closed). `build_server` lazily imports the `mcp` SDK and raises a clean install message if absent.

## Tests / checks run

- `python tools/validate_engine_run.py data/small_sm/runs/f119c98b-1108-4dd6-bd6f-d12f6e133899.json` → **PASS**.
- `pytest tests/test_narration_mcp_locks.py tests/test_narration_mcp_smoke.py` → **24 passed**.
- `pytest tests/test_engine_run_schema.py` + the two new files → **41 passed** (no schema regression).
- Verified SDK-free import + fail-closed behaviors (no `anthropic`, no `mcp`, no key).

## RULE A / Stop-Coding-Line conformance

- RULE A pinned by `test_rule_a_null_mechanism_no_mechanism_line` (no line on None) + `test_rule_a_guard_rejects_injected_mechanism_line` (guard trips on an injected line).
- Stop-Coding Line pinned by the L8 scrubber tests: a misbehaving LLM that invents `$12,000` fails closed; the fixture (non-BLEND source) emits no dollar at all; only a non-suppressed `source=BLEND` p10/p50/p90 produces an allowed figure.

## What I need from the founder to go live (real-key end-to-end)

1. **Env var:** `ANTHROPIC_API_KEY` set in the engine-host environment where the narration MCP process runs.
2. **Model id:** default is `claude-sonnet-4-6` (cost). Override via `NARRATION_MODEL` (e.g. `claude-opus-4-8`) if a card's reasoning demands it. Optional `NARRATION_MAX_TOKENS` (default 700).
3. **SDKs:** `pip install anthropic mcp` on the engine host (both noted in `requirements.txt`, both lazy — not needed for tests).
   Nothing else changes: `server._default_llm` auto-selects `AnthropicLLMClient` the moment the key is present; the guards remain the safety net regardless of LLM.

## Open clarities (for frontend KNOWN_ISSUES.md)

- **KI-FE-7 (suppression-branch coverage):** DISCHARGED for narration via `tests/test_narration_mcp_locks.py` synthetic fixtures (suppressed range, RULE A, None-param, Tier-B {}, STORE_OBSERVED-not-lift, BLEND-allowed). Recommend marking the Phase-1 narration obligation of KI-FE-7 satisfied; the broader "regenerate a runtime fixture that exercises suppression" remains a separate (lower-priority) item if the integration layer wants a live suppressed card.
- **Narration artifact persistence:** the narrator returns the artifact dict keyed `(run_id, play_id)`; it does NOT write it to disk. Where/whether to persist (sibling `narration/<run_id>.json` vs. broker-cached) is a Phase-2 integration decision (mcp-integration-engineer). Flag for KI.

## Remaining risks / follow-ups

- The guard term lists (lift/fit-warning/AOV vocab) are heuristic string matches. They are conservative (fail closed) but a determined LLM could phrase an overclaim outside the list. Mitigation: the L8 dollar scrubber (the highest-value laundering vector) is value-traceable, not vocabulary-based, so the number itself cannot be invented. Recommend a real-key adversarial pass once the key lands to widen the L2/L3 term lists if needed.
- L2 currently only fires on the prose; it does not yet bump confidence labels — out of scope (engine owns confidence_label). No action.
- Prompt-caching `cache_control` blocks are set on the system preamble + mechanism contract; effectiveness is unverifiable until a real key run. The mock path ignores them. Verify cache hit-rate when live.
- `Deviation check: none` — built exactly the Phase-1 slice; no scope expansion, no engine mutation, no commit.

---

## DS review (2026-06-02) — APPROVE WITH CHANGES

Verdict: **safe to commit the mock-mode milestone now; the changes below GATE the real-key cutover, not the commit.** DS confirmed the highest-stakes property holds — inventing a number from nothing is structurally impossible (input projection withholds raw figures + fail-closed on every path) — and praised the fail-closed design as the model for the assembly MCP. L1/L3/L6/RULE-A(type)/immutability/KI-FE-7 all sound.

### 🔑 REAL-KEY-GATED CHECKLIST — do ALL before pointing a live ANTHROPIC_API_KEY at any BLEND-range card

1. **[ ] Tighten `_figures_match` (guards.py:107-122) — MUST-FIX.** The cross-magnitude `(10,100,1000)` rounding grid accepts a fabricated `$2,000` as a "rounding" of a real `$2,500` p50 — a precise-looking invented number. Remove the grid; accept only exact / whole-dollar / same-magnitude significant-figure rounding (computed from each allowed value's own magnitude, never a fixed 1000 grid).
2. **[ ] Add a percentage scrubber.** L8 covers `$` but NOT `%`. A fabricated discount-share / lift-% (e.g. "shift 15% of customers") passes every guard today. Add `scrub_percentages` mirroring L8: no `%` figure unless traceable to a projected numeric param. Closes the RULE-A-param + DISCOUNT/THRESHOLD-type gap.
3. **[ ] Harden L2 structurally (not a longer denylist).** "STORE_OBSERVED revenue not narrated as lift" is the one lock with NO input backstop (the number is intentionally surfaced) and the output denylist is paraphrase-evadable. Mitigate structurally: positive-template the dollar-bearing field, OR a one-shot "is this a causal/lift claim?" classifier pass before going live. Applies to EVERY card today (zero Tier-A plays).

### Logged as KIs (defer, not key-gating)
- L8 `_DOLLAR_RE` catches only `$`-prefixed numerals; spelled-out / `k`-suffixed numbers rely on the input projection withholding source figures. Acceptable while projection holds.
- `validate_snapshot` FAIL is non-fatal (narrates anyway with a `validation_warning`). Integration layer (Phase 2) decides whether `/api/narrate` hard-fails on a schema-validation FAIL.

### Cutover dependency
None of the above blocks Phase 2 (integration spine) wiring against MOCK mode. They block ONLY the moment a real key authors prose on a card carrying a non-suppressed `source=BLEND` revenue_range.
