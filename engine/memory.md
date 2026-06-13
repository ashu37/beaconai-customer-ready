# BeaconAI Working Memory

## How to use this file

This is the canonical chronological record of the V2 implementation. New agents should read this top-to-bottom to understand:

- What V2 is (Decision Core overhaul direction)
- What shipped, in order, with load-bearing invariants and founder-visible caveats
- What is permanently out of scope

**What is NOT in this file:** verbose ticket details (file change tables, full test counts, line-by-line implementation notes). For those, see:
- Per-ticket summary files: `agent_outputs/code-refactor-engineer-<ticket>-summary.md`
- **Open bugs / edge cases / engine behavior issues: [KNOWN_ISSUES.md](KNOWN_ISSUES.md)** — the canonical registry. Every ticket's non-obvious caveat lands there; check before assuming a behavior is broken vs documented.
- **Locked decisions / per-play floors / per-vertical defaults / hard-stop envelopes: [docs/DECISIONS.md](docs/DECISIONS.md)** — the canonical registry for founder-locked heuristic values. Each entry includes WHAT, WHY, source-of-truth code path, override mechanism, and pinning tests. Read BEFORE adjusting any heuristic value. New founder Q decisions land here on sprint close.
- Full historical entries: `memory_archive.md` (frozen snapshot of pre-trim memory)
- Git history: `git log --oneline` and `git show <commit>:memory.md`

**Adding new entries:** Each completed ticket gets a per-commit ritual (impl commit + `Document <ticket> in repo memory.md` commit + summary file). When appending here, keep it tight: scope shipped, load-bearing invariants, founder-visible caveats, suite count, schema impact. Expand into the summary file if more detail is needed.

**Entry length cap: ≤15 lines per ticket.** Use this template:

```
## <Ticket-ID> — <one-line scope> (YYYY-MM-DD)

**Shipped:** <2-3 bullets, what's now true that wasn't before>

**Load-bearing invariants:**
- <invariant 1 — what future agents must NOT break>
- <invariant 2>

**Caveats / dormant behavior:** <one sentence — e.g., "store_id kwarg added but not plumbed; Phase 9 activates">

**Schema:** unchanged | event_version=1 additive | user_version bump 1→2
**Suite:** N passed (was M)
**Summary:** [agent_outputs/code-refactor-engineer-<ticket>-summary.md](...)
```

What goes OUT of memory.md (lives in summary file only): file change tables, per-test-suite pass counts, implementation notes, risk paragraphs, branch shape, commit hashes (git log has these).

---

# Decision Core Phase 1 — Reconciled Direction (2026-05-01)

## Accepted diagnosis
- Engine was a hypothesis/targeting recommender presenting itself as forecasting/significance.
- Core product = ecommerce decision engine recommending 0–3 high-value Play Theses, not a dashboard.
- No-recommendation is a valid outcome. Engine must explain rejected plays.

## Architecture
- Detect → Size → Recommend.
- Evidence classes: `measured`, `directional`, `targeting`, `weak`, `blocked`.
- Targeting plays do NOT expose p-values, q-values, CIs, or measured effects merchant-facing.
- No multi-window min-p cherry-picking.
- Abstain modes: `ABSTAIN_HARD` (data quality memo, recommendations=[]) and `ABSTAIN_SOFT` (standard layout + "no measured" callout, 0–2 targeting cards).
- Rejection list ("Considered, not recommended") is a first-class output with typed `reason_code` enum.
- Scale-aware materiality floors by ARR tier: `<$1M → max($5k, 2%)`, `$1–5M → max($10k, 3%)`, `>$5M → max($25k, 5%)` of monthly revenue.

## Load-bearing invariants (must hold across V2)
- `evidence_class == "targeting"` ⇒ `measurement is null`
- `evidence_class == "measured"` ⇒ `measurement.observed_effect` non-null AND `consistency_across_windows >= 2` AND `p_internal` non-null
- `revenue_range.suppressed == true` ⇒ renderer hides $; shows audience + AOV
- `sum(recommendations[].revenue_range.p50) <= 0.25 * monthly_revenue`
- 0 measured/directional in recommendations ⇒ `ABSTAIN_SOFT`, never `PUBLISH`
- Any `data_quality_flag` ⇒ `ABSTAIN_HARD`, recommendations=[]
- `briefing.html` contains no `"p ="`, `"q ="`, `"CI"`, `"confidence_score"`, `"final_score"`, or numeric confidence percentage
- Vertical hard-locked at `{beauty, supplements, mixed}` (D-8); `mixed` = literal beauty+supplements blend, NOT unknown-vertical fallback

## Permanently out of scope (Phase 1)
- Bayesian credible intervals; hierarchical priors over fleet of stores
- LLM-narrated state-of-store
- Klaviyo / Shopify network calls (manual JSON import only per D-5)
- "Calibrated" claim or uplift terminology in merchant-facing copy
- "Learning" CONFIDENCE_MODE that relaxes thresholds

---

# Milestones M0–M9 (Phase 1 build, 2026-05-01 → 2026-05-03)

Each milestone shipped behind ENGINE_V2 flag stack, M0 goldens preserved unless explicitly re-pinned.

**M0 — Golden Freeze.** 3 merchant fixtures pinned. 21 golden files (3 × briefing.html + 6 receipts JSON each). Charts/segment ZIPs excluded (nondeterministic).

**M1 — Additive EngineRun + Anomaly Foundation.** Typed EngineRun schema + anomaly detection module + state-of-store Observation + legacy adapter. Receipts/engine_run.json on every run. Merchant output unchanged. *Caveat: AnomalousWindowCheck defined but not auto-registered (M5 flips). Resolved later in B-1.*

**M2 — Play Registry + Priors Config.** Typed Play Registry + `config/priors.yaml` (versioned, `source_class ∈ {observational, causal, expert}`). Registry covers 11 legacy + 3 planned plays. *Note: empty_bottle is its own play, registry has 14 plays, not 10.*

**M3 — Shadow Candidate Detection.** Pure audience builders + shadow `detect_candidates()` + Candidate schema with forbidden-fields enforcement. Pairwise audience overlap. cold_start flag (logged-only). v2_candidates.json behind `ENGINE_V2_SHADOW`. *Invariant: Candidate objects contain no p/q/confidence/revenue/CI/effect/score/rank/recommended fields.*

**M4a — Fabricated-Stats NaN Gate + Evidence Class Field.** `src/evidence.py`. NaN-handling invariant: targeting+NaN p ⇒ Targeting; measured/directional+NaN p ⇒ engine bug raises. STATS_NAN_FOR_HARDCODED + EVIDENCE_CLASS_ENFORCED flags. Dropped duplicated new_customer_rate BH entry. *Behavior change: small_sm golden regenerated due to ENABLE_REPEAT_RATE_BIAS_CORRECTION default flip.*

**M4b — Targeting Reclassification + Combiner Reroute.** Targeting plays drop `measurement` in EngineRun. Multi-window measured/directional candidates use `combine_multiwindow_statistics`. Legacy min-p merge bypassed on V2 path. `consistency_across_windows` = pre-combination sign-agreement count, NOT p-vote. *Transition state: small_sm produces 0 PRIMARY actions under V2 — expected; M5–M8 bring guardrails/sizing/abstain/renderer.*

**M5 — Guardrail Engine.** `src/guardrails.py`: inventory gate, anomalous-window hard abstain, scale-aware materiality, audience-overlap/cannibalization, portfolio cap, recently-run fatigue stub. *Caveat: POST_PROMO_WINDOW soft warning, not ABSTAIN_HARD until B-1.*

**M6 — Conservative Economic Sizing.** `src/priors_loader.py` + `src/sizing.py`. Formula: `audience × p_action × incremental_orders × AOV`. Cold-start suppression. Targeting suppression for non-causal priors. `revenue_range.drivers[]` provenance. *Behavior: all current targeting plays suppressed under V2 sizing because priors are expert/observational, not causal — intentional and conservative.*

**M7 — V2 Decision Selector.** `src/decide.py::decide(engine_run, cfg)`. Class-aware ranking (measured > directional > targeting), max-3 cap, ABSTAIN_HARD/ABSTAIN_SOFT/PUBLISH state logic. Targeting-only ⇒ ABSTAIN_SOFT (never PUBLISH). Watching builder. *Implementation choice: M7 composes existing EngineRun from legacy adapter + M5/M6 layers, does NOT rebuild from M3 candidates — preserves M3's no-stat contract.*

**M8 — V2 Play Thesis Renderer.** `src/storytelling_v2.py`. State-of-store lead, Recommended/Considered/Watching/data-quality footer sections. ABSTAIN_SOFT layout + ABSTAIN_HARD memo. Targeting no-dollar-headline invariant. `ENGINE_V2_OUTPUT` flag. *Caveat: Real pinned fixtures all render ABSTAIN_SOFT under full V2 stack — expected from M4b/M6 transition.*

**M9 — ML Readiness / Outcome Logging.** `src/outcome_log.py` + `src/calibration_stub.py` + `src/debug_renderer.py`. `recommended_history.json` writer. Calibration stub shape: `{prior_overrides, evidence_thresholds, materiality_overrides}` (returns empty until live consumer). Internal `receipts/debug.html` (carries internal stats; not linked from briefing). Privacy: no raw customer IDs/emails, local file only, gitignored. *OUTCOME_LOG_ENABLED defaults TRUE (safe, local, deterministic).*

**M10 — Cleanup (deferred).** Legacy renderer + legacy `calculate_28d_revenue` deletion territory. Per-vertical math knobs (window weights, winback/dormant windows, material thresholds, subscription thresholds) currently live only in legacy code — must be re-homed into priors.yaml or successor config before M10 deletes their legacy home.

---

# Phase 5 — Honest Considered List + One Measured Pathway (2026-05-03)

**Motivation:** After M0–M9, V2 was scientifically honest but operationally inert. Beauty Brand rendered ABSTAIN_SOFT with empty Recommended/Considered/Watching despite real signal.

**Phase 5.1–5.7 shipped:**
- 5.1 Rewrote ABSTAIN_SOFT copy: merchant-readable, keyed by dominant gate (no-evidence / materiality / overlap).
- 5.2 `populate_considered_from_candidates()`: maps M3 candidates to RejectedPlay with reason_code, reason_text, evidence_snapshot, would_fire_if. Considered now renders during ABSTAIN_SOFT.
- 5.3 Extended Watching: returning_customer_share + net_sales observations. Softened to surface flat load-bearing metrics as "stable, watching" instead of filtering out. Suppressed/labeled `repeat_rate_within_window` when no identified customers exist (was rendering 0.0%). Observation cap raised 5→7.
- 5.4 Materiality footer rewritten: "We only recommend primary plays that could realistically add at least $X this month for a store your size." Exact numeric floor stays in debug.html.
- 5.5 Aura/Beacon Score absence verified in V2.
- 5.6 Phase 5.6 directional builder: `measurement_builder.build_directional_play_card` constructs `first_to_second_purchase` Measurement from L28 primary-window signal directly, NOT via the combiner. Documented gap pinned in B-6.
- 5.7 (Phase 5.1.1) Addressable Opportunity Context produced; renders alongside Recommended cards.

**Synthetic blocker fixes 1–11 (2026-05-03):** fixture retuning, cold-start chart crash fix, targeting measurement invariant, ABSTAIN_SOFT contract pinning, inventory block visibility, materiality footer restoration, per-scenario vertical propagation (closed Bug 2 caveat — see S-1.7 below for the full close), DOM-only synthetic reporter, fixture rebalancing.

---

# Phase 6A — Recommended Experiment Lane (2026-05-04 to 2026-05-05)

Adds a second slate role between Recommended Now and Considered: experiment-eligible plays that cleared a high bar but aren't a clean Recommended Now.

**Tickets A1–A4.5, B1–B6 shipped.** Key load-bearing pieces:

- **A1 — Watching cap=4 + load-bearing pin.** Empty-HELD MOVED-load-bearing fallback is INTENTIONAL, not an M7/M5.3 violation.
- **A2 — `WouldBeMeasuredBy` enum + PlayCard field.** UPPER_SNAKE_CASE values intentional (match priors YAML / `recommended_history.json`); do not normalize.
- **A3 — Priors metadata loader.** Dual YAML form (list+dict) coexists intentionally — always route through `_extract_play_block`. `AudienceArchetype` is lowercase by design. **Downgrade note (S7 priors-wiring, 2026-05-20):** the "lowercase by design" pin is now scoped to Contract-Q3 archetypes only. Casing follows authoring-source provenance under the new invariant: "Contract-Q3 archetypes lowercase; founder-spec S7 archetypes UPPER_SNAKE; future additions cite source and follow its casing." Do NOT migrate existing values; mixed regime is intentional.
- **A4 — Recommended Experiment selector** behind `ENGINE_V2_SLATE`. Allowlist `{discount_hygiene, bestseller_amplify}`, hard cap 2, abstain ⇒ [].
- **A4.5 — main.py plumbs Phase 5 candidates into `decide()`.** Structural source-text test pins the `candidates=` kwarg; do not rename `_v2_decide` without updating it.
- **B1 + B1.5 — Recommended Experiment renderer + opportunity_context producer wiring** bundled in one commit. Lazy import of `_build_opportunity_context` is intentional; AOV source aligned `[L28]` with `L56/L90` fallback.
- **B2 — Forbidden-token sweep on `section.recommended-experiment`.** "Projected lift" allowlisted ONLY inside exact `OPPORTUNITY_CONTEXT_DISCLAIMER` constant. Test-only, no src/copy changes.
- **B3 — ABSTAIN_SOFT routes experiment-eligible held plays to Considered with `TARGETING_HELD_UNDER_ABSTAIN`.** Selector gained `publish_shadow` kwarg; abstain-zero contract enforced at `decide()` seam, NOT selector.
- **B4 — Role-uniqueness invariant in decide.py.** All 3 pairwise overlaps checked (recs × experiments × considered); Watching exempt by design; single-run scope only.
- **B5 — Cannibalization + diversity tests on experiments.**
- **B6 — Beauty pinned slate fixture** (sha256 `48d61b89...`) + decide-layer post-experiment considered filter. 19/19 byte-identical contract.

**Phase 6A Final Review (2026-05-05, 585480e):** founder testing ONLY, NOT external beta. Rendering the slate requires ALL THREE flags `ENGINE_V2_DECIDE + ENGINE_V2_OUTPUT + ENGINE_V2_SLATE`.

---

# Phase 6B — Founder Feedback + Stop-Coding Line (2026-05-05)

**Tickets C1–C4 shipped:**
- **C1 + C1.5** — Mechanism copy ("What we'd send") on Recommended cards. `first_to_second_purchase` promoted to A3 dict form with mechanism. Beauty fixture sha256 `48d61b89...` (unchanged).
- **C2** — Section reorder: Recommended Now → Recommended Experiment → Watching → Considered → DQ-footer. Beauty fixture re-pinned `5fa9f697...`.
- **C3** — Customer-facing play-title relabel. `display_name` updated on all 14 plays. V2 renderer uses `_card_title_for(play_id)` for `<h3>` tags. Internal `data-play-id` HTML attributes preserved for log/tooling stability. Beauty fixture re-pinned `dcb45cee...`.
- **C4** — Never-empty Watching copy fallback for mature stores when `engine_run.watching` is empty. Maturity proxied by `cold_start == False` and absence of `INSUFFICIENT_CLEAN_HISTORY`.

## STOP-CODING LINE (load-bearing for all future work)

**The `engine_run.json` schema is FROZEN.** All narration, dollar formatting, percent framing, and visual polish is delegated to a downstream AI Agent Swarm reading `engine_run.json`. **Do not write further UI/HTML code in the engine.**

Stop-Coding Line fixes (one commit, 2026-05-05):
- `config/priors.yaml`: rewrote `discount_hygiene` to suppression posture; stripped trailing measurement instructions.
- `play_registry.py`: broke `display_name` collisions, added load-time uniqueness assertions.
- Added raw typed floats/ints to `OpportunityContext` (`aov_used`, `monthly_revenue_estimate`) and State-of-Store `Observation` (`current`, `prior`, `delta_pct`).
- Mapped freeform Considered reasons to strict Enums; reserved `held_reason_detail` struct.
- Reserved typed slots `anomaly_flags`, `n_days_observed`, `n_days_expected` (B-1 later populates them).

**Schema additions after this point are additive-only with founder sign-off.**

---

# Founder Decisions (2026-05-09)

These are constraints, NOT subject to renegotiation by implementing agents.

- **D-1** — `audience_definition_version` policy. Any change to SQL/Python audience-definition logic MUST increment `audience_definition_version` by 1. Old lineages remain readable but fork to a new `lineage_id`. Required arg in `compute_lineage_id`.
- **D-2** — Retention forever. No TTLs, auto-deletion, archival tiers. SQLite grows monotonically.
- **D-3** — Merchant deletion = full wipe only. Per-store `data/<store_id>/memory.db` is the deletion unit. No row-level deletion APIs, soft-delete flags, or partial redaction.
- **D-4** — Full per-store JSON export from Day 1 (`tools/export_store.py`). Round-trip test required.
- **D-5** — Manual JSON import ONLY for v1. NO Klaviyo API pollers, OAuth flows, or webhook receivers in Beacon-track scope.
- **D-6** — ML models EXPLICITLY BANNED for the planning horizon: quiz contextual bandits (LinUCB/Thompson), VIP/loyalty tier optimization, new product launch targeting, bundle combinatorial optimization, stockout prediction, cause/limited-edition→core conversion. NO empty modules, placeholder classes, prior entries, or `play_id` registrations for these. Re-additions require explicit founder approval + new addendum.
- **D-7** — I-1 affinity audience-builder spec deferred to Sprint 3 spike memo.
- **D-8** — Vertical scope hard-locked at `{beauty, supplements, mixed}`. `mixed` = literal beauty+supplements blend, NOT a fallback for unknown verticals. Apparel, food/bev, home goods, wellness are out of scope PERMANENTLY — refused at engine entry, never absorbed by `mixed`. Cross-merchant pooling (if/when it lands Year 2) within {beauty, supplements} only.

**Storage backend note (founder, 2026-05-10):** `data/<store_id>/` (SQLite memory.db + immutable run snapshots) is LOCAL-DISK SCAFFOLDING for the planning horizon. When AWS hosting lands, the storage backend swaps — likely S3 for immutable snapshots (object versioning + lifecycle policies handle retention) and managed Postgres/Aurora for the event log. The substrate API (`open_memory`, `append_event`, `write_immutable_snapshot`) is already abstracted enough that storage swaps without engine changes. **Do NOT "optimize" disk growth, add TTLs, archive tiers, or local-disk cleanup logic — D-2 still holds today; AWS migration is the right time to revisit, not now.**

---

# Sprint 1 — Engine Hardening (2026-05-09)

Two parallel tracks merged into `post-6b-restructured-roadmap`.

## Engineer A track

**B-4/S-1 — Per-merchant directory + `store_id` resolution.** New `src/store_id.py`: `resolve_store_id` (precedence: `STORE_ID` env > `--brand` > orders-CSV parent basename > `"unknown"`), sanitized to `[a-z0-9_-]+`. Both hardcoded `data/recommended_history.json` paths replaced with `store_dir / "recommended_history.json"`. `gate_recently_run` re-keyed to lineage tuple `(play_id, audience_definition_id, store_id)`; `audience_definition_id` falls back to `audience.id` until S-2/S-3. Idempotent copy-with-attribution migration of legacy file (D-3: never deleted). `RECENTLY_RUN_FATIGUE_ENABLED` stays default-OFF. Critical-path prerequisite for substrate.

**B-7 — Hard-refuse non-supported verticals.** `src/vertical_guard.py` short-circuits engine when `vertical_mode` outside `{beauty, supplements, mixed}` → ABSTAIN_HARD with `data_quality_flag=VERTICAL_NOT_SUPPORTED` and typed merchant-facing refusal copy on `Abstain.reason`. Wired top of `src/main.py::run()` BEFORE priors/feature/play registry. `_ALL_VERTICALS = frozenset({"beauty", "supplements", "mixed"})` is canonical scope. Priors loader rejects non-supported top-level keys (`ConfigError`). *Caveat closed by S-1.7: B-7 was being silently undermined by `get_vertical_mode()` laundering unknown verticals to `'mixed'` — fixed.*

**G-7 — Cross-run byte-identical determinism CI.** New `src/_determinism.py::seed_all(seed=DEFAULT_SEED=0)` seeds stdlib `random` + (best-effort) `numpy.random`. Idempotent. Called at engine entry in `src/main.py::run()` AFTER `cfg = get_config()`, BEFORE B-7 vertical guard / B-4 store-id / feature build / decide. Two-run identity contract: `engine_run.json` byte-identical after stripping `NORMALIZED_FIELDS=("run_id",)` IN COMPARATOR, NOT artifact. *Invariants: seed call MUST stay at engine entry — moving past `decide()` makes S-3's lineage-id stability test unverifiable. `NORMALIZED_FIELDS` is intentionally narrow.*

## Engineer B track

**B-1 — AnomalousWindow auto-registration + ABSTAIN routing.** New `detect_promo_spike` in `src/anomaly.py`: fires `POST_PROMO_WINDOW` when L56 revenue ≥ 2.0x prior-L56 with credible baseline (`min_prior_orders=50`, `min_prior_days_covered=28`). Threshold in `config/anomaly_thresholds.yaml::promo_spike`. `ANOMALY_GATE_ENABLED` default flipped TRUE; healthy fixtures produce zero flags so M0 stays byte-identical. `gate_anomaly` routes `POST_PROMO_WINDOW` alone → `ABSTAIN_SOFT` (recommendations cleared, demoted to Considered with `ReasonCode.ANOMALOUS_WINDOW`). Reserved typed `Observation` slots `anomaly_flags`/`n_days_observed`/`n_days_expected` now populated. Phase 5.6 directional rebuild in `main.py` skips when ABSTAIN_HARD OR (ABSTAIN_SOFT AND populated `data_quality_flags`). *Calibration: Beauty L56=1.17 silent; promo_anomaly L56=2.28 fires.*

**B-3 — Hardcoded-fallback regression test.** `tests/test_no_hardcoded_fallbacks_in_payload.py`. Scans rendered `engine_run.json` for forbidden Phase 2 constants `{0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40}` on at-risk plays (`TARGETING_RECLASSIFY_PLAYS` + defensive empty_bottle guard). Trust-contract test: violation means re-pin BEFORE shipping the fix, not the other way around.

**B-5 — Berkson-class invariant test.** Pins TWO invariants: (A) structural cohort-definition rule (cohort denominator on early-half counts only — 554960d fix) via `calculate_journey_stats_single_window`; (B) M4b reclassification contract — `subscription_nudge` and `routine_builder` must ship `evidence_class=targeting` with `measurement=null`. Defensive membership pin: both play_ids must remain in `TARGETING_RECLASSIFY_PLAYS`.

**B-6 — Multi-window combiner universality test.** Thread-local trace facility in `src/stats.py` (`multiwindow_combiner_trace()` + `record_combine_multiwindow_call`). Production overhead: zero outside test context. *Caveat: assertion is VACUOUSLY satisfied today because Beauty has zero `evidence_class=measured` cards (only `first_to_second_purchase` ships at `directional`). Documented-gap test pins the Phase 5.6 directional builder's L28-only path. Contract locks in moment a measured-class card emerges.*

**G-2 — `empty_bottle` parser unit-coherence (vertical_applicable filter).** New `config/replenishment_sizes.yaml` (per-vertical regex; supplements stub null). New `src/replenishment_parser.py` thin loader. `_targeted_skus_for_play` for `empty_bottle` refactored to use dispatcher. `empty_bottle.vertical_applicable` restricted from `_ALL_VERTICALS` to `frozenset({"beauty", "mixed"})`. `decide.py:614` filter clean-skips on supplements. Beauty regex `30ml|1 oz|1oz|50ml|1.7 oz|1.7oz|100ml|3.4 oz|3.4oz` preserved verbatim.

---

# Sprint 2 — Substrate Writing Path (2026-05-09 to 2026-05-10)

End of S-3 = **substrate schema freeze for Swarm team**.

## Engineer A track

**S-2 — SQLite memory.db substrate + lineage_id helper + inspect/export CLIs.** Substrate stands alone — zero engine code changes.
- `src/memory/store.py`: `MemoryStore` + `open_memory(store_id)`. Per-store SQLite at `data/<store_id>/memory.db`. WAL + `busy_timeout=5000` + `synchronous=NORMAL`. `PRAGMA user_version` migrations (current=1). Schema: `events(event_id PK, event_type, lineage_id, run_id, store_id, play_id, audience_definition_id, audience_definition_version, event_version, created_at, created_seq, payload_json)` + 3 indexes + one-row `event_seq` counter.
- `src/memory/lineage.py`: `compute_lineage_id(store_id, play_id, audience_definition_id, audience_definition_version) -> sha1 hex`. ALL 4 args required (D-1). Length-prefixed components joined by `\x1f`. sha1 (not sha256) — partition key, not security primitive.
- `tools/inspect_memory.py` + `tools/export_store.py` (D-4 full per-store JSON export with round-trip test). `import_store` refuses to overwrite populated store (operator does `rm -rf` upstream).

*Invariants for future readers:*
- `created_seq` is the canonical ordering field, NOT `created_at`. Counter incremented inside the same transaction as INSERT via `UPDATE ... RETURNING` (SQLite ≥ 3.35; we have 3.53). Moving the increment outside the transaction re-introduces the race the table was added to fix.
- `compute_lineage_id` length-prefixes each string component. Removing prefixing re-opens the `("ab","c")` vs `("a","bc")` collision the unit test pins.
- `MemoryStore` is NOT thread-safe across instances on the same db file from a single process. Open one per thread, or serialise. Across processes, WAL handles it.
- Export `_format_version=1`. Bumping requires writeback migration story.
- CLIs run as `python -m tools.<name>` from repo root.

## Engineer B track

**S-1.7 — Vertical resolution hardening.** Fixed two bugs in `src/utils.py` undermining B-7:
1. `get_vertical_mode()` no longer launders unknown verticals (`apparel`, `food`, `home`, `wellness`) into `'mixed'`. Pass through as-is (lowercased+stripped). Default when no env set remains `'mixed'` (the literal blend, NOT a fallback). B-7 vertical_guard stays the single point of refusal.
2. Manual `.env` fallback (when python-dotenv missing) changed from unconditional assignment to `os.environ.setdefault(...)` — exported env vars now win.

End-to-end test: `VERTICAL_MODE=apparel python -m src.main ...` triggers B-7 ABSTAIN_HARD with `data_quality_flags=["vertical_not_supported"]`, no slate, no briefing.

**S-3 prep (NON-merging, gated OFF).** Reason-code fan-out + typed event schemas. Substrate writer (S-2) lives in parallel; final wire-up is mechanical post-S-2 merge.
- Reason-code fan-out (B-2 surface a) in `src/decide.py`: new `_S3_FANOUT_REASON_MAP` maps short codes to typed `ReasonCode` (`DATA_QUALITY_FLAG`, `COLD_START_INSUFFICIENT_DATA`, `MATERIALITY_BELOW_FLOOR`; plus `AUDIENCE_TOO_SMALL`/`INVENTORY_BLOCKED` from legacy `_PRELIM_REASON_MAP`). **Gated behind `ENGINE_S3_REASON_FANOUT` env flag (default OFF)** to preserve M0 byte-identity until S-3 final commit re-pins goldens (per plan §7 Risk #4). Additive only.
- Typed `EvidenceSnapshot` + `ExpectedOutcome` (audit L-E) + `RecommendationEmittedPayload`/`RecommendationConsideredPayload` in new `src/memory_events.py` (will move to `src/memory/events.py` post-S-2 merge). `RECOMMENDATION_EVENT_VERSION = 1`.
- TODO block in `src/main.py:925` carries exact import + call shape for S-3 wire-up.
- Single-writer grep test stub (`tests/test_single_writer_per_event_type.py`): allowlist of writer files per event type.

**S-3 — Engine writes `recommendation_*` events to substrate (closes Sprint 2, schema-freeze milestone for Swarm team).** Final wire-up of the substrate writing path. End of S-3 freezes the `recommendation_emitted` / `recommendation_considered` payloads at `event_version=1`; future field-shape changes are frozen-contract events requiring Swarm-team coordination.
- `src/memory_events.py` → `src/memory/events.py` (typed payloads now part of the `src/memory/` package alongside the S-2 substrate). Re-exported through `src/memory/__init__.py`.
- `src/main.py` TODO block replaced with `_emit_substrate_events(...)` — opens per-store `memory.db` via `open_memory(store_id)`, walks `recommendations` / `recommended_experiments` / `considered`, appends typed payloads. Wrapped in try/except: substrate failures log a warning and DO NOT crash the engine (purely additive).
- Lineage tuple per D-1: `(store_id, play_id, audience_definition_id, audience_definition_version)`. Until the audience-builder pipeline carries explicit fields, `audience_definition_id` falls back to `audience.id` (or `play_id` when empty) and `audience_definition_version` defaults to 1; founder closes that gap separately.
- Reason-code fan-out activated unconditionally — `_s3_fanout_enabled()` gating helper and `ENGINE_S3_REASON_FANOUT` env flag REMOVED. `_S3_FANOUT_REASON_MAP` consulted on every `_candidate_reason_code` call. `DATA_QUALITY_FLAG`, `COLD_START_INSUFFICIENT_DATA`, `MATERIALITY_BELOW_FLOOR` now flow into Considered cards alongside legacy `AUDIENCE_TOO_SMALL` / `INVENTORY_BLOCKED`.
- Beauty pinned slate re-pinned in the SAME commit (plan §7 Risk #4):
  - before sha256 `ed02ddc2bc33564e2b1647dc725d69bc70e69cde4dd878e3358fad87d97e7914`
  - after sha256 `45edaca58c47797addf556b91460b81782dba6653d5d1ec82043bd40a051ea78`
  - diff scope: ONE Considered card (`empty_bottle`) flips `data-reason-code="no_measured_signal"` → `data-reason-code="data_quality_flag"`. Only byte change in `engine_run.json` shape.
- M0 goldens (small_sm, mid_shopify, micro_coldstart) stay byte-identical; those fixtures do not exercise S-3 fan-out short codes.
- Acceptance test `tests/test_s3_substrate_emission.py` (5 tests): events emitted; `lineage_id` byte-identical across two runs of Beauty fixture (audit L-B regression test riding on G-7 determinism); `run_id` distinct per run; `_emit_substrate_events` propagates the underlying exception to the caller (caller's try/except in `src/main.py::run` is what guarantees the additive contract).
- Single-writer grep test (`tests/test_single_writer_per_event_type.py`) graduates from vacuous-passing to strict; allowlist for `recommendation_emitted` / `recommendation_considered` updated to `{src/decide.py, src/main.py, src/memory/events.py}`.
- `inspect_memory.py` confirmed end-to-end on a Beauty harness run: emits `recommendation_emitted` rows with full typed `evidence_snapshot` + `expected_outcome` payloads.

*Invariants for future readers (S-3 closeout):*
- `recommendation_emitted` / `recommendation_considered` `event_version = 1` is the SCHEMA-FREEZE milestone for the Swarm team. Additions are additive-only with founder sign-off.
- `_emit_substrate_events` must remain the ONLY producer of these event types in `src/`; the grep test enforces this. Adding a new writer (e.g. a future re-emission helper) requires updating `_ALLOWED_WRITERS` in the same PR.
- Substrate writes are PURELY ADDITIVE to runtime — engine still works if `memory.db` cannot open. Caller's try/except is the load-bearing layer; helper itself does not swallow `open_memory` failures so ops can see the underlying cause.
- `audience_definition_id` falling back to `audience.id` / `play_id` is a documented transition; the lineage tuple stays deterministic and stable across runs of the same fixture (`tests/test_s3_substrate_emission.py::test_lineage_id_stable_across_runs` pins this).
- D-1 still bites: any future change to audience-builder logic MUST bump `audience_definition_version`. The default-1 behaviour today is a transitional convenience, NOT a license to skip the bump when an explicit field exists.
- Suite count: 1084p / 14s / 0f (was 1047p / 14s / 0f at S-3 prep).

---

# Sprint 3 — Substrate Read-Views + Swarm Hand-Off (2026-05-10 onward)

## Engineer A track

**S-4 — Immutable snapshot discipline + `snapshot_sha256`.** Engine now writes the slate JSON to an immutable per-run path `data/<store_id>/runs/<run_id>.json` (never overwritten), and mirrors it byte-identically into `receipts/engine_run.json` for backward-compat with existing Swarm consumers. The sha256 of the on-disk immutable snapshot is computed at write time and threaded onto every `recommendation_emitted` / `recommendation_considered` event payload. New `src/memory/snapshot.py` (`write_immutable_snapshot`, `verify_snapshot`, stdlib `hashlib.sha256` only). `src/main.py` replaces the `write_json(receipts/engine_run.json, ...)` call with a snapshot write + mirror; on immutable-write failure, falls back to legacy `write_json` so the engine still produces output (substrate snapshot fields then stay None for that run). `_emit_substrate_events` gained `snapshot_path` / `snapshot_sha256` kwargs threaded into both emit helpers. `event_version` stays `1` (additive field — `snapshot_path` / `snapshot_sha256` already lived on the typed payloads as `Optional[str]` from S-3 prep). Acceptance: `tests/test_s4_snapshot_immutability.py` (6 tests) — 5 distinct immutable files across 5 runs, every event's `snapshot_sha256` matches on-disk re-hash, `verify_snapshot` detects a hand-edited byte mutation, receipts mirror byte-identical to immutable snapshot, helper refuses overwrite on `run_id` collision, empty `run_id` raises `ValueError`. M0 Beauty pinned fixture byte-identical (the slate JSON content is unchanged; only its location and a per-payload sha256 are new). 1090p / 14s / 0f (was 1084p / 14s / 0f at S-3 closeout).

*Invariants for future readers (S-4):*
- The immutable snapshot path stored on event payloads is **absolute** (`Path.resolve()`), so a downstream auditor running from any cwd can re-hash the file directly.
- `write_immutable_snapshot` raises `FileExistsError` on `run_id` collision rather than overwriting. Per-run uuid4 makes collisions effectively impossible; an actual collision points to a caller bug we want to surface.
- `receipts/engine_run.json` is produced by `shutil.copyfile` from the immutable snapshot, NOT by re-serialising the dict — byte-identity with the immutable file is load-bearing for the existing Swarm contract.
- Schema-freeze at `event_version=1` preserved: S-3 already declared `snapshot_path` / `snapshot_sha256` as `Optional[str]`; S-4 only populates them.
- `src/memory/snapshot.py` is NOT a new event-type writer; the single-writer grep test allowlist remains unchanged (no new event types introduced).
- Fallback path on immutable-write failure preserves the additive contract: engine_run.json still appears, substrate emission still runs (with `snapshot_path=None` / `snapshot_sha256=None` for that run), the operator sees a `[Snapshot] Warning:` line.

**S-5 — Substrate read-views + `calibration_stub` rewire.** Four read-only views projected over the `events` table from S-2: `v_lineage_timeline` (per-lineage event history ordered by `created_seq`), `v_calibration_state` (`calibration_updated` rows in `created_seq` order, walked last-write-wins), `v_open_recommendations` (most recent `recommendation_emitted` per `lineage_id` with no later `outcome_observed`), `v_lineage_recent_emissions` (per-lineage emission count in trailing 28-day window anchored on `MAX(created_at)`). DDL in new `src/memory/views.sql`; typed Python helpers in new `src/memory/views.py`. `PRAGMA user_version` bumped 1→2 with idempotent `CREATE VIEW IF NOT EXISTS` migration; downgrade refusal still in force (`user_version > CURRENT_USER_VERSION` raises). `src/calibration_stub.py::load_realization_factors` gained an optional `store_id` kwarg — when provided, opens the per-store substrate and projects `v_calibration_state` into the existing `{prior_overrides, evidence_thresholds, materiality_overrides}` dict. With no `store_id` / missing `memory.db` / zero `calibration_updated` events, returns the same three-key empty-shape dict the pre-S-5 stub returned (legacy contract preserved end-to-end). New `docs/memory_substrate.md` documents per-store layout, schema versions, event-type freeze, and view contracts (columns, types, ordering guarantees, read-only invariant). Acceptance: `tests/test_s5_views.py` (17 tests) — seed-fixture row counts on all four views, parametrized forbidden-write rejection, empty-substrate parity with the pre-S-5 stub, `calibration_updated` last-write-wins projection, forward-compat ignore of unknown payload sections, migration idempotency through v2, downgrade refusal. M0 Beauty pinned fixture byte-identical. 1107p / 14s / 0f (was 1090p / 14s / 0f at S-4 closeout).

*Invariants for future readers (S-5):*
- Views are read-only by SQLite construction (no `INSTEAD OF` triggers); the parametrized forbidden-write test pins the `OperationalError` on every view. Adding an `INSTEAD OF` trigger would silently break the contract — don't.
- `created_seq` is the ordering source of truth for all views. Wall-clock `created_at` is only used as a window anchor inside `v_lineage_recent_emissions`, and even there the anchor is `MAX(created_at)` from the events table itself (deterministic at test time, reproducible across runs) — NOT the OS wall clock.
- `v_calibration_state` returns one row per `calibration_updated` event in `created_seq` ASC order. The `read_calibration_state` helper walks them last-write-wins per `(section, key)` tuple. Reordering this to "most-recent-only" would break legitimate Phase 9 patterns where one event updates `prior_overrides` and a later event updates only `evidence_thresholds`.
- `read_calibration_state` ignores any payload section outside the canonical three (`prior_overrides`, `evidence_thresholds`, `materiality_overrides`). This is the forward-compat shim — Phase 9 / 10 may grow new sections; older readers must keep returning the empty-shape dict for absent sections without crashing on unknown ones.
- The calibration_stub's `try/except` around `open_memory` and `read_calibration_state` is load-bearing: the engine must keep running when `data/<store_id>/memory.db` is absent (fresh install) or stale (mid-migration). NEVER replace the empty-shape fallback with a raise.
- The `CURRENT_USER_VERSION = 2` bump is the FIRST migration past the S-2 baseline. Future migrations follow the same pattern: append a SQL block to `_MIGRATIONS[N]`, bump `CURRENT_USER_VERSION` by 1, ensure every statement is `IF NOT EXISTS`-shaped.
- `src/memory/views.py` is a READER, not a writer — it must NEVER appear in the single-writer grep test allowlist for any event type. Event-type literals in `views.py` use rST backticks in docstrings (` ``calibration_updated`` `), NOT quoted strings, so the grep pattern `['"]<literal>['"]` does not match. Keep it that way; SQL filter literals live in `views.sql` (which is `.py`-extension-filtered out of the grep scan).

## S-6 — Manual `campaign_sent` import path + Swarm contract (2026-05-10)

**Shipped:** New `tools/import_campaign_sent.py` CLI (single writer for `campaign_sent`); typed `CampaignSentPayload` in `src/memory/events.py` at `event_version=1`; `outcome_observed` schema documented in `docs/memory_substrate.md` as the Phase 9 frozen contract (NOT implemented); Swarm integration boundary section added.

**Load-bearing invariants:**
- Engine NEVER writes/reads `campaign_sent` — file boundary is the discipline (D-5). Single-writer grep allowlist for `campaign_sent` is exactly `{tools/import_campaign_sent.py}`.
- `tools/import_campaign_sent.py` IS allowlisted for `recommendation_emitted` as a READER (substrate cross-check queries that event_type literal). The grep can't distinguish read from write; comment in test pins the rationale.
- Importer refuses (strict v1): malformed JSON, missing required field, unknown field, bad channel enum, negative/non-int audience_size, orphan lineage_id, unknown recommendation_event_id, lineage/event_id mismatch, duplicate campaign_id within store.
- `CampaignSentPayload` schema is frozen at `event_version=1`. Additive-only: new `Optional` fields only; removal/rename/re-type bumps version.
- Two-run integration test pins `v_lineage_timeline` returning `[recommendation_emitted, campaign_sent]` in `created_seq` order for the imported lineage; engine `engine_run.json` unaffected by presence/absence of `campaign_sent` events.
- `outcome_observed` schema in `docs/memory_substrate.md` is the Phase 9 contract; `tools/import_outcome_observed.py` is reserved but NOT implemented in S-6.

**Caveats / dormant behavior:** `outcome_observed` allowlist entry stays forward-looking (`tools/import_outcome_observed.py`); Phase 9 implementer adds the writer in the same PR. CLI does not move/delete inbox files on success — operator owns inbox hygiene; re-running over the same file refuses on duplicate-campaign_id.

**Schema:** `event_version=1` additive — `CampaignSentPayload` pinned. `recommendation_*` payloads still frozen at v1 (Sprint 2 freeze).
**Suite:** 1129 passed, 14 skipped, 0 failed (was 1107/14/0 at S-5 closeout).
**Summary:** [agent_outputs/code-refactor-engineer-s6-summary.md](agent_outputs/code-refactor-engineer-s6-summary.md)

## G-1 — Pin synthetic supplements slate fixture (2026-05-10)

**Shipped:** Pinned `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` (sha256 `feb03500c1adc4a8a8a6762c6f0c98fd2a81ba2a9d3838d75ccca0ea221a0e0d`); new `tests/test_slate_regression_supplements_brand.py` (12 tests); 9 new `KI-` entries (KI-20..KI-28) in `KNOWN_ISSUES.md` category 5. Engine runs end-to-end on supplements without crash (ABSTAIN_SOFT, 0 Recommended, 0 Experiments, 6 Considered, 4 Watching). No `src/` changes — discovery ticket; every breakage filed as a `KI-`, none required contract escalation.

**Load-bearing invariants:**
- Fixture sha256 pinned as a constant in the test file; on-disk drift fails `test_pinned_fixture_sha256_matches` AND the byte-wise snapshot test — both must be updated together on intentional refresh.
- Considered membership pinned as `{winback_21_45, bestseller_amplify, discount_hygiene, subscription_nudge, routine_builder, frequency_accelerator}`. The 5-play drop-out from M3 shadow (KI-23) is part of the regression contract — any membership change must update KI-23 in the same commit.
- `healthy_supplements_240d_*.csv` are byte-identical clones of `supplement_replenishment_240d_*.csv`; the two will not auto-sync if either is edited.

**Caveats / dormant behavior:** Supplements never reaches PUBLISH under current V2 gates (KI-20 directional builder gap). `confidence_mode: "learning"` leaks via legacy adapter on both Beauty + supplements — out of G-1 scope. `mixed` vertical still not exercised end-to-end (KI-28 / KI-19; G-3 owns).

**Schema:** unchanged (no `engine_run.json` or `event_version` changes; KI entries' future fixes are all additive).
**Suite:** 1141 passed, 14 skipped, 0 failed (was 1129/14/0 at S-6 closeout; +12 G-1 tests).
**Summary:** [agent_outputs/code-refactor-engineer-g1-summary.md](agent_outputs/code-refactor-engineer-g1-summary.md)

## G-3 — Supplements priors expansion + `mixed` semantics formalised (2026-05-10)

**Shipped:** every supplements/mixed/wildcard prior in `config/priors.yaml` carries a `source` provenance field (58 entries); `mixed` semantics pinned by new `src/priors_loader.py::resolve_mixed_prior` (explicit-mixed → wildcard → deterministic 50/50 beauty+supplements blend; never silent beauty-only fallback); per-vertical audience floors live in priors metadata via `PlayMetadata.audience_floor_by_vertical` + helper `get_audience_floor`; `routine_builder` promoted to A3 dict form with supplements floor 30 < beauty 60; D-8 hard-lock positively tested (synthetic `apparel:` YAML fragment raises `ConfigError`).

**Load-bearing invariants:**
- `resolve_mixed_prior` MUST return `None` when either beauty or supplements input is missing — never silently absorb the present side (D-8). Three tests pin this; do not "soften" to fall-through.
- Beauty priors block UNTOUCHED — every `applies_to: { vertical: beauty }` entry is byte-identical. Beauty fixture sha256 unchanged. Supplements G-1 fixture sha256 unchanged.
- `routine_builder` is now dict-form; its `metadata.mechanism` is set but `routine_builder` does NOT render in Recommended Now / Experiment today, so the "What we'd send" line stays absent (renderer only calls `_mechanism_for_play` for those two card classes).
- Per-vertical floor mechanism shipped at priors layer ONLY; the legacy `audience_builders.py::routine_completion_candidates` still applies `MIN_N_SKU` config-driven floor unconditionally. Plumbing into the legacy builder is Sprint 5+ scope (KI-25 progress note).

**Caveats / dormant behavior:** KI-25 flipped `open` → `tracked` (not `resolved`): floor mechanism is in place but the G-1 supplements rejection cause is structural (audience=0 from beauty-shaped audience builder), so the supplements fixture stayed byte-identical. KI-19 flipped to `resolved`. KI-28 stays `tracked` — `mixed` is loader-unit-test pinned only; end-to-end `mixed` fixture deferred.

**Schema:** unchanged.
**Suite:** 1152 passed, 14 skipped, 0 failed (was 1141/14/0 at G-1 closeout; +11 G-3 tests).
**Summary:** [agent_outputs/code-refactor-engineer-g3-summary.md](agent_outputs/code-refactor-engineer-g3-summary.md)

## G-4 — subscription_nudge + routine_builder permanently targeting (2026-05-11)

**Shipped:** `_TARGETING_RECLASSIFY` for these two plays is now the *structural* default in `src/action_engine.py::_compute_candidates`, not a flag-gated path. Hardcoded `effect_abs=0.05` / `effect_abs=0.08` / `effect_floor=0.05` placeholders and the Welch-t / z-test fabricated p-values are removed. Candidates emit `evidence_class="targeting"` directly + NaN stat fields; `engine_run_adapter` drops the measurement block. KI-24 updated with G-4 progress note (surface tightened; Phase 4.2 multiplier-vs-baseline-rate redesign still open).

**Load-bearing invariants:**
- `subscription_nudge` and `routine_builder` ship `evidence_class=targeting` with `measurement=None` STRUCTURALLY, no env flag. Re-introducing a fabricated measurement object on either play is a Berkson-class regression — `tests/test_g4_targeting_reclassify.py` and the existing `tests/test_berkson_invariant.py` both pin this.
- Both play_ids stay in `TARGETING_RECLASSIFY_PLAYS` (defensive coverage); G-4 makes the reclassification structural at the emit site, it does NOT prune the frozenset.
- Beauty pinned fixture sha256 unchanged at `45edaca58c47797addf556b91460b81782dba6653d5d1ec82043bd40a051ea78`. Supplements G-1 fixture sha256 unchanged at `feb03500c1adc4a8a8a6762c6f0c98fd2a81ba2a9d3838d75ccca0ea221a0e0d`. The fixtures were already generated under the M4b flag-on stack, so promoting to structural produces zero on-disk delta — re-pin discipline was prepared for a shift; none occurred.

**Caveats / dormant behavior:** KI-24 stays `open` — surface is now honest but the underlying multiplier-vs-baseline-rate conflation on supplements `subscription_nudge` audience is Phase 4.2 redesign scope, not G-4.

**Schema:** unchanged (no engine_run.json or event_version impact).
**Suite:** 1160 passed, 14 skipped, 0 failed (was 1152/14/0 at G-3 closeout; +8 G-4 tests).
**Summary:** [agent_outputs/code-refactor-engineer-g4-summary.md](agent_outputs/code-refactor-engineer-g4-summary.md)

## S5-T1 — KI-26 supplements `prior` populated + KI-3 store_id wired (2026-05-11)

**Shipped:** `src/state_of_store.py::build_observations` now reads prior values from the correct nested path `aligned["L28"]["prior"][<metric>]` (was a non-existent top-level `aligned["L28_prior"][<metric>]`, silent since M1). `src/main.py::run` calls `load_realization_factors(store_id=store_id)` after `resolve_store_id`, making the `v_calibration_state` substrate read path reachable end-to-end (dormant-but-correct wiring; empty-shape projection until Phase 9 lights up the writer). KI-3 + KI-26 both flipped `open` → `resolved`.

**Load-bearing invariants:**
- HTML renderer must NOT consume `Observation.prior` directly — `prior` is `engine_run.json`-only surface. Both pinned briefing fixtures (Beauty `dcb45cee...` sha256 unchanged from C3; supplements G-1 `feb03500c1...` unchanged) confirm this; if a future renderer change reads `Observation.prior` and emits it into HTML, the fixture sha256s must be re-pinned in the same commit.
- `load_realization_factors(store_id=...)` call site stays at the `main.py` `run()` entry, immediately after `resolve_store_id` and before feature build / decide. Moving it past `decide()` would defer the projection past the consumer; the kwarg name `store_id=store_id` is pinned by `tests/test_s5_t1_store_id_wired.py`.

**Caveats / dormant behavior:** Calibration projection is empty-shape until Phase 9 lands the live `calibration_updated` writer. Engine behavior is byte-identical to pre-S5-T1 today; the wiring is reachable in production but the projection is the canonical three-key empty dict.

**Schema:** unchanged (Observation `prior` slot was reserved by 6B C2/C3; populating it is additive within `event_version=1`).
**Suite:** 1168 passed, 14 skipped, 0 failed (was 1160/14/0 at G-4 closeout; +8 S5-T1 tests).
**Summary:** [agent_outputs/code-refactor-engineer-s5-t1-summary.md](agent_outputs/code-refactor-engineer-s5-t1-summary.md)

## S5-T2 — KI-20 supplements first_to_second_purchase typed honest abstain (2026-05-13)

**Shipped:** New `ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` (additive within `event_version=1`) + `src/main.py` emit-on-supplements path that prepends a typed `RejectedPlay` for `first_to_second_purchase` into Considered when the Phase 5.6 directional builder did not produce a Recommended card. Path (b) per plan §11 lines 592-598; path (a) window-widening rejected to preserve B-5 Berkson invariant. Supplements G-1 fixture re-pinned `feb03500c1...` → `a7def44787...`.

**Load-bearing invariants:**
- Emit gated on `vertical == "supplements"`; Beauty / `mixed` paths untouched. `tests/test_s5_t2_supplement_cadence_abstain.py::test_beauty_does_not_emit_supplement_cadence_code` pins isolation.
- Card is PREPENDED so the 6-card cap inside `populate_considered_from_candidates` cannot displace it; reordering this to append would silently regress KI-20.
- Directional builder (`measurement_builder.build_directional_play_card`) is NOT modified by this ticket; B-5 Berkson invariant stays vacuously preserved on this surface.

**Caveats / dormant behavior:** KI-23 supplements drop-out gap remains open for `aov_momentum` / `category_expansion` / `journey_optimization` / `empty_bottle`; `frequency_accelerator` is now the displaced 6th card.

**Schema:** unchanged (additive enum value within `event_version=1` frozen contract).
**Suite:** 1175 passed, 14 skipped, 1 failed (the 1 fail is pre-existing wall-clock drift in `test_inventory_updated_at_is_fresh`, unrelated to S5-T2; confirmed at baseline HEAD).
**Summary:** [agent_outputs/code-refactor-engineer-s5-t2-summary.md](agent_outputs/code-refactor-engineer-s5-t2-summary.md)

## S5-T3 — KI-22 supplements repeat-rate metric incoherence typed flag (2026-05-16)

**Shipped:**
- New additive typed `DataQualityFlag.METRIC_INCOHERENT_FOR_CADENCE` (Sprint 2 freeze carve-out for additive enum values on `data_quality_flags`).
- New pure helper `src/cadence_coherence.py` (median customer reorder gap > `DEFAULT_THRESHOLD_RATIO=0.8` × window_days); `src/main.py` post-decide block on supplements vertical only propagates the existing stdout advisory into `data_qua...

**Load-bearing invariants:**
- `METRIC_INCOHERENT_FOR_CADENCE` is ADVISORY — intentionally absent from `src/decide.py::_HARD_DQ_FLAGS`. Adding it to that frozenset would silently push the supplements run to ABSTAIN_HARD; `test_new_flag_is_advisory_not_hard` pins this.
- Heuristic threshold lives in `cadence_coherence.DEFAULT_THRESHOLD_RATIO = 0.8` as the single source of truth — pinned by `test_default_threshold_ratio_pinned`. Future re-tunes must update the constant in one place.

**Caveats / dormant behavior:** Founder call inside the ticket — suppress (not relabel) the Watching row. If a future ticket prefers relabel, both are contract-safe; the test asserts the suppress branch.

**Schema:** unchanged (additive enum value within `event_version=1` frozen contract).
**Suite:** 1190 passed, 14 skipped, 1 failed (the 1 fail is the pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift; unrelated to S5-T3).
**Summary:** [agent_outputs/code-refactor-engineer-s5-t3-summary.md](agent_outputs/code-refactor-engineer-s5-t3-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7.5-T1 — PriorEntry validation_status + source_artifact + effective_n fields (2026-05-17)

**Shipped:**
- New closed `PriorValidationStatus` enum in `src/priors_loader.py` with exactly 5 values: `validated_external`, `validated_internal`, `elicited_expert`, `heuristic_unvalidated`, `placeholder`. Exported in `__all__` alongside new `PriorsValidationError` (ValueError subclass).
- `PriorEntry` dataclass gains three additive optional fields: `validation_status` (defaults to `HEURISTIC_UNVALIDATED`), `source_artifact` (Optional[str]), `effective_n` (Optional[int]). `_coerce_entry` parses them; closed-enum violations raise `PriorsValidationError` naming the play/prior/value triple plus the full legal set.

**Load-bearing invariants:**
- Closed-enum strictness on `validation_status` is the whole point of T1 — silent coercion to the default would defeat the T3 refusal contract. `tests/test_s7_5_t1_priors_validation_fields.py::test_loader_rejects_unknown_validation_status_string` pins this.
- Missing field → `HEURISTIC_UNVALIDATED` default. Every pre-T1 entry in `config/priors.yaml` (zero authored `validation_status`) parses unchanged; `test_real_priors_yaml_every_entry_defaults_to_heuristic_unvalidated` pins it.
- `effective_n` and `source_artifact` use tolerant coercion (non-positive int / non-string / whitespace-only → `None`); only `validation_status` is closed-enum strict.

**Caveats / dormant behavior:** ZERO behavior change in this ticket — sizing/decide do not yet read `validation_status` (T3 wires consumption behind `ENGINE_V2_PRIORS_VALIDATION`, default OFF; T3.5 is the activation). `resolve_mixed_prior` blended entries default to `HEURISTIC_UNVALIDATED` (the most-conservative value), which is the right answer pre-T3; the explicit conservative-min rule on blend lands in T3 alongside the KI-19 verification test.

**Schema:** unchanged (additive dataclass fields with safe defaults; `event_version=1` frozen contract intact).
**Suite:** 1205 passed, 14 skipped, 1 failed (was 1190p at S5-T3 close; +15 new T1 tests; the 1 fail is the pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift unrelated to S7.5-T1).
**Summary:** [agent_outputs/code-refactor-engineer-s7_5-t1-summary.md](agent_outputs/code-refactor-engineer-s7_5-t1-summary.md)

## S7.5-T1.5 — Priors YAML audit pass (2026-05-17)

**Shipped:**
- Every prior entry in `config/priors.yaml` (84 total across 14 plays) now carries an authored `validation_status` field. No implicit defaults remain in production YAML; the loader's T1-introduced default still exists for backwards-compat but is unreached by the shipped file.
- Distribution at T1.5 close: **82 entries** `heuristic_unvalidated`, **2 entries** `placeholder` (`first_to_second_purchase.second_purchase_lift`; `at_risk_repeat_buyer_rescue.base_rate` — both already carried "Placeholder" notes). **0** entries promoted to `validated_internal` or `validated_external` (T2 owns that next).
- Repo grep for the 8 `internal_csv_observation_v1` entries: searched `scripts/`, `tools/`, `analysis/`, `docs/`, `notebooks/`, `agent_outputs/` for analysis artifacts producing the exact values (`winback_21_45.base_rate` supplements=0.12 / mixed=0.06; `orders_per_customer`=1.30; `discount_hygiene.margin_recovery_rate` supplements=0.005 / mixed=0.005; `empty_bottle.base_rate`=0.12; `frequency_accelerator.base_rate` supplements=0.18 / mixed=0.16). The values appear hard-coded in `src/action_engine.py` but no reproducible derivation (script / notebook / CSV / memo) was found. Per founder Q3, all 8 stay `heuristic_unvalidated`; the `source: internal_csv_observation_v1` YAML tag remains as a descriptive label but is no longer a validation claim — the load-bearing field is `validation_status`.

**Load-bearing invariants:**
- `tests/test_s7_5_t1_5_priors_audit.py::test_every_prior_entry_has_authored_validation_status` walks the raw YAML (not the loader, so the T1 default cannot mask a missing field) and asserts every entry has an explicit `validation_status` string in the closed set.
- `test_validation_status_distribution_pin` pins the per-status counts and the two specific (play_id, prior_name) tuples that are `placeholder` so a typo cannot silently swap a placeholder for a heuristic.
- T1's `test_real_priors_yaml_every_entry_defaults_to_heuristic_unvalidated` was reframed to `test_real_priors_yaml_every_entry_resolves_to_a_closed_enum_value` (closed-enum invariant only; the distribution check moved to T1.5).

**Caveats / dormant behavior:** ZERO behavior change — nothing reads `validation_status` until T3. The `internal_csv_observation_v1` source tag stays in the YAML for historical traceability but is descriptive, not load-bearing.

**Schema:** unchanged (`event_version=1` frozen; YAML-only edits).
**Suite:** 1208 passed, 14 skipped, 1 failed (was 1205p at S7.5-T1 close; +3 new T1.5 tests; the 1 fail is the same pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift).
**Fixtures:** Beauty pinned slate sha256 unchanged at `45edaca58c47...`; supplements G-1 sha256 unchanged at `01f5feff84...`; M0 goldens byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s7_5-t1_5-summary.md](agent_outputs/code-refactor-engineer-s7_5-t1_5-summary.md)

## S7.5-T2 — External benchmark memos + validated_external promotions (2026-05-17)

**Shipped:**
- New `config/priors_sources/` directory with a README documenting the memo shape + promotion contract (per Part III-1 Step 4: ONLY base_rate / bundle_value priors may be validated by observational benchmarks; incrementality / *_lift / c...
- **3 priors promoted to `validated_external`** with `source_artifact` pointers and `effective_n` where the source discloses sample size:

**Load-bearing invariants:**
- `tests/test_s7_5_t2_external_priors.py` pins (a) ≥3 validated_external entries, (b) every validated_* entry has a non-null `source_artifact` whose file exists AND cites at least one URL, (c) no `incrementality` / `*_lift` / `churn_redu...
- Memos document what the source DOES prove and what it does NOT prove. Klaviyo's "flow placed order rate" is per-email-send, not per-recipient-in-window — the YAML value mapping is structurally compatible but the point estimate is engin...

**Caveats / dormant behavior:** ZERO behavior change — nothing reads `validation_status` / `source_artifact` / `effective_n` until T3. The promotions create a `validated_external` set for T3's blend-refusal rule to recognize (heuristic_unvalidated → suppress; validated_externa...

**Schema:** unchanged (`event_version=1` frozen; YAML + new memo files + new test file only).
**Suite:** 1213 passed, 14 skipped, 1 failed (was 1208p at S7.5-T1.5 close; +5 new T2 tests; the 1 fail is the same pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift).
**Summary:** [agent_outputs/code-refactor-engineer-s7_5-t2-summary.md](agent_outputs/code-refactor-engineer-s7_5-t2-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7.5-T3 — Cold-start blend refusal + SOFT_PRIOR_UNVALIDATED abstain (default-OFF flag) (2026-05-17)

**Shipped:**
- New cfg flag `ENGINE_V2_PRIORS_VALIDATION` in `src/utils.py::get_config()` defaulting to `false`. Env-override via `ENGINE_V2_PRIORS_VALIDATION=true`. Flag flip to default-ON is T3.5's atomic re-pin ticket.
- `src/sizing.py`: added `PSEUDO_N_BY_STATUS = {VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}` module constant (founder Q4 locked). Heuristic / placeholder deliberately absent — they trigger refusal, not weight. Ad...

**Load-bearing invariants:**
- `tests/test_s7_5_t3_blend_refusal.py` pins (a) pseudo_N table values (30/15/10) + closed-table invariant, (b) `bayesian_blend` numerics (prior-dominated, store-dominated, equal-weight 0.14, degenerate-zero fallback), (c) `size_play` fl...
- 24 new tests; ZERO test removed.

**Caveats / dormant behavior:** - Default OFF in T3 (`ENGINE_V2_PRIORS_VALIDATION=false`). M0 / Beauty pinned slate / supplements G-1 all byte-identical at default flag. - `bayesian_blend` is forward-looking scaffolding for Sprint 6 Tier-B builders; no runtime caller in T3. Te...

**Schema:** additive within `event_version=1` freeze. `ReasonCode.PRIOR_UNVALIDATED` (additive enum value); `AbstainMode` enum (new); `Abstain.mode: Optional[AbstainMode] = None` (additive optional dataclass field).
**Suite:** 1237 passed, 14 skipped, 1 failed (was 1213/14/1 at T2 close; +24 new T3 tests; the 1 fail is the same pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift, unrelated).
**Summary:** [agent_outputs/code-refactor-engineer-s7_5-t3-summary.md](agent_outputs/code-refactor-engineer-s7_5-t3-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7.5-T3.5 — Flip ENGINE_V2_PRIORS_VALIDATION default ON + atomic re-pin (closes Sprint 7.5) (2026-05-17)

**Shipped:**
- `src/utils.py::get_config()`: env-var default for `ENGINE_V2_PRIORS_VALIDATION` flipped from `"false"` to `"true"`. The cold-start blend-refusal rule is now the engine's default posture (beta cut). Operator override `ENGINE_V2_PRIORS_V...
- `src/sizing.py`: tightened the T3 rule semantics — under flag-on the validation-status rule REPLACES (rather than supplements) the legacy `source_class != causal` rule. The 3 T2-promoted validated_external priors are `observational`; u...

**Load-bearing invariants:**
- All 5 pinned fixtures render byte-identically post-flip. The behavior change lives entirely in typed slots (`Abstain.mode`, considered-fan-out routing) that the merchant briefing renderer does NOT surface today.
- M0 goldens (`small_sm`, `mid_shopify`, `micro_coldstart`): legacy `ENGINE_V2_SIZING=false` path; the new rule is structurally unreachable.

**Caveats / next milestones:** - The behavior change of the rule will only manifest on real Tier-C targeting plays once Sprint 6 Tier-B builders surface them with heuristic-unvalidated priors. - The merchant briefing renderer does NOT yet distinguish `soft_awaiting_measurement...

**Schema:** unchanged (no new fields). T3.5 ONLY flips the flag default + tightens the elif branch in `size_play`. T3's schema additions (`ReasonCode.PRIOR_UNVALIDATED`, `AbstainMode`, `Abstain.mode`) are additive within `event_version=1`.
**Suite:** 1237 passed, 14 skipped, 1 failed (was 1237/14/1 at T3 close; same pre-existing wall-clock drift in `test_inventory_updated_at_is_fresh`, unrelated).
**Summary:** [agent_outputs/code-refactor-engineer-s7_5-t3_5-summary.md](agent_outputs/code-refactor-engineer-s7_5-t3_5-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S6-T1 closeout (2026-05-17)

**Caveats / next milestones:** - T1.5 may discover that the synthetic Beauty fixture's winback cohort is < 500 (the audience floor). Per orchestrator decision (2026-05-17): if cohort < 500, the new card routes to Considered with `AUDIENCE_TOO_SMALL` — that is correct behavior,...

**Summary:** [agent_outputs/code-refactor-engineer-s6-t1-summary.md](agent_outputs/code-refactor-engineer-s6-t1-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S6-T1.5 closeout (2026-05-17)

**Caveats / next milestones:** - The contract is "live but dormant" on today's synthetic fixtures. A real beta brand will be the first runtime caller of `build_prior_anchored_play_card`'s validated path. - The cap-trim in `populate_considered_from_candidates` deserves a future...

**Schema:** unchanged at T1.5 (T1 shipped the `WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D` enum + `PredictedSegment` / `ModelCardRef` ML scaffolding; T1.5 is a flag-default flip only).
**Summary:** [agent_outputs/code-refactor-engineer-s6-t1_5-summary.md](agent_outputs/code-refactor-engineer-s6-t1_5-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S6-T2 closeout (2026-05-18)

**Caveats / next milestones:** - KI-27 close requires either (a) founder confirmation, or (b) a coverage path to 100% — likely a weight-to-serving conversion design ticket that requires per-SKU serving-size metadata not present in current order CSVs. - The 5/10 coverage rate i...

**Summary:** [agent_outputs/code-refactor-engineer-s6-t2-summary.md](agent_outputs/code-refactor-engineer-s6-t2-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S6-T3 closeout (2026-05-19)

**Summary:** [agent_outputs/code-refactor-engineer-s6-t3-summary.md](agent_outputs/code-refactor-engineer-s6-t3-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S6-T3.x closeout — `replenishment_due` prior re-key + audit-response sprint (2026-05-19)

**Shipped:**
- New `replenishment_due.base_rate.beauty` validated_external block in `config/priors.yaml` (value=0.0220, range=[0.0120, 0.0430], effective_n=30; backed by `config/priors_sources/replenishment_due__base_rate__beauty.md` from commit `011...
- `_PRIOR_ANCHORED["replenishment_due"]` dispatch in `src/measurement_builder.py` re-keyed from `bestseller_amplify.bundle_value` → `replenishment_due.base_rate` (resolves the D-S6-2 dollar-vs-rate category error).

**Load-bearing invariants:**
- D-S6-2 superseded by D-S6-2.1; the `bestseller_amplify.bundle_value.beauty` prior remains intact (only its USE as a replenishment_due prior was invalidated). Future agent MUST NOT delete the bundle_value prior or its memo.
- Supplements `replenishment_due.base_rate` is INTENTIONALLY absent — do not author a stub for code-symmetry (DS architect verdict 2026-05-19); the asymmetric reason code (Beauty validated_external activation vs supplements PRIOR_UNVALID...

**Caveats / dormant behavior:** All 5 pinned fixtures byte-identical under flag-OFF (Beauty + supplements G-1 + 3× M0). T3.5 owns the atomic flip + re-pin (Beauty replenishment_due lands in Recommended Now against the new validated_external prior; supplements stays in Consider...

**Schema:** unchanged (no enum additions; only YAML + dispatch routing + docs).
**Suite:** 1422 passed (was 1416; +6 from new test file, with 3 existing tests updated in-place to track the re-key).
**Summary:** [agent_outputs/code-refactor-engineer-s6-t3_x-summary.md](agent_outputs/code-refactor-engineer-s6-t3_x-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S6-T3.y closeout — audience-floor sensitivity driver on validated-path PlayCards (2026-05-19)

**Shipped:**
- New `_audience_floor_sensitivity_driver()` helper in `src/measurement_builder.py` (pure function; 9-key typed dict with 8-key inner `value`). Driver appended to `RevenueRange.drivers` on validated-path prior-anchored PlayCards when pri...
- Closes the DS architect 2026-05-19 firewall leak: surfaces `if audience floor were +/-25%, revenue_p50 would shift to $p50_low–$p50_high`. Sensitivity is on the FLOOR (heuristic choice in `gate_calibration.yaml`), not the audience. Coh...

**Load-bearing invariants:**
- Driver is additive on `RevenueRange.drivers` ONLY; never wired into directional pathway, never wired on `heuristic_unvalidated` / `placeholder` paths, never modifies any existing driver's shape.
- Sensitivity is on the FLOOR variant `[floor*0.75, floor, floor*1.25]`, NOT on the audience. Computing against the audience is a category error (audience is observed data; floor is the heuristic).

**Caveats / dormant behavior:** All 5 pinned fixtures byte-identical under flag OFF (Beauty + supplements G-1 + 3× M0). T3.z reads the new driver value to optionally surface a "robustness band" or "sensitivity envelope" on Recommended Now cards.

**Schema:** unchanged (driver value is polymorphic `Optional[Any]` per existing pattern; no enum / dataclass change; `event_version=1` intact).
**Suite:** 1433 passed (was 1422; +11 from new test file).
**Summary:** [agent_outputs/code-refactor-engineer-s6-t3_y-summary.md](agent_outputs/code-refactor-engineer-s6-t3_y-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S6-T3.z closeout — Considered render pass + audience_floor_sensitivity render on validated-path Recommended Now cards (2026-05-19)

**Shipped:**
- `RejectedPlay` gains 3 Optional schema-additive fields (`audience_size`, `audience_definition`, `mechanism`) within `event_version=1`. Pre-T3.z payloads round-trip unchanged.
- `render_rejected_card` upgraded with conditional cohort row (`play-card-aud--considered`), "What we'd send" mechanism line, and PRIOR_UNVALIDATED honest-dollar copy ("We're not projecting dollars on this play until we measure outcomes...

**Load-bearing invariants:**
- Renderer NEVER recomputes the sensitivity band. T3.y's driver is the single source of truth.
- T3.z is render-layer only — `_route_window_disagreement_holds` / `_route_prior_unvalidated_holds` semantics UNCHANGED. T3.5 owns the candidate→`RejectedPlay` population path for the new fields and the activation of `audience_floor.repl...

**Caveats / dormant behavior:** All 5 pinned fixtures byte-identical under flag OFF (Beauty + supplements G-1 + 3× M0). T3.5 still owns the visible flip: it must populate `audience_size` / `audience_definition` / `mechanism` from candidate at Considered-routing time, AND autho...

**Schema:** `RejectedPlay` schema-additive within `event_version=1` (3 Optional fields default `None`; `_from_dict_rejected` coerces `audience_size` via `int(...)` with `None` fallback). No enum changes.
**Suite:** 1451 passed / 14 skipped / 0 failed (was 1433; +18 from new test file).
**Summary:** [agent_outputs/code-refactor-engineer-s6-t3_z-summary.md](agent_outputs/code-refactor-engineer-s6-t3_z-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S6-T3.5 PARTIAL CLOSEOUT — `replenishment_due` activation scaffolding landed; Commit C flag flip deferred (2026-05-19, Path D, DS-architect-locked)

**Status:** PARTIAL CLOSEOUT. Commits A (23fd73d) + B (e0b0eab) + C-scaffold (4199e67) + D (73bc16d) + E accepted. Commit C atomic flag flip DEFERRED — `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` stays default OFF.

**Path D locked by:** ecommerce-ds-architect 2026-05-19 (agent a3e8cc44e77dcf281). Diagnosis: Beauty G-1 `cohort_n` collapses to 0 at D-S6-4 per-SKU N≥30 gate — binding upstream of D-FLOOR-replenishment_due=150. Fixture-shape, not gate-logic. Synthetic activation rejected; real beta drives Commit C.

**Shipped (scaffolding, all live + unit-tested):** prior block (`config/priors_sources/replenishment_due__base_rate__beauty.md`), audience-floor cell (`config/gate_calibration.yaml::audience_floors.replenishment_due` + `docs/DECISIONS.md::D-FLOOR-replenishment_due` LOCKED, beauty {60/150/350/1000} + `mixed_beauty` 1.5×, no supplements cell), strict floor resolver (`src/profile/builder.py::_resolve_audience_floor_cell_strict`), envelope test (42-cell `tests/test_s6_t3_5_replenishment_due_floor_resolver.py`), RejectedPlay surface-field population at all 3 Considered-routing seams (`src/decide.py`, +89 lines), `CADENCE_DUE_REPEAT_BUYER` enum (`src/priors_loader.py`, latent fix), 8 new tests (`tests/test_s6_t3_5_considered_surface_population.py`). D-S6-3 envelope citation refreshed to `replenishment_due.base_rate.beauty [p10=0.0120, p90=0.0430]`.

**Deferred:** Commit C atomic flag flip + 4 slate-pin re-pins. xfail-marked (strict=False) with new reason citing D-S6-4 cohort_n=0 root cause + KI-NEW-G resume trigger.

**Resume trigger (KI-NEW-G):** Phase 9 beta-onboarding store enters at GROWTH/skincare with hero-SKU repeat-buyer count ≥150 in ±½-cadence window. Activation against real-store fixture, not re-shaped Beauty G-1.

**3 new KIs filed (Commit D):** KI-NEW-G (Commit C activation pending), KI-NEW-H (D-S6-4 + D-S6-5 + D-FLOOR joint Phase 9 recalibration, DS-surfaced), KI-NEW-I (Watching-row routing for cohort_n=0).

**Load-bearing invariants:** ENGINE_V2_BUILDER_REPLENISHMENT_DUE OFF. Scaffolding preserved — DO NOT remove priors block, floor resolver, envelope test, T3.y driver, or T3.z renderer. M0 goldens byte-identical. Beauty + supplements pinned fixtures byte-identical (sha256 unchanged; 4 slate-pin tests xfailed strict=False).

**Suite:** 1497 passed, 14 skipped, 4 xfailed, 0 failed (post-B; C-scaffold + D add no test counts). Briefing.html forbidden-token sweep clean.

**Summary:** [agent_outputs/code-refactor-engineer-s6-t3_5-summary.md](agent_outputs/code-refactor-engineer-s6-t3_5-summary.md)

## Sprint 6 — CLOSED (PARTIAL: T3.5 Path D) — 2026-05-19

Anchor goal: First two Tier-B builders (`winback_dormant_cohort`, `replenishment_due`) + supplements serving-count parser.

**Status:** CLOSED. T3.5 is PARTIAL CLOSEOUT per DS-architect-locked Path D — Commit A (Considered surface fields) + Commit B (`gate_calibration` floor + DECISIONS) accepted; Commit C (atomic flag flip + 5-fixture re-pin) deferred behind KI-NEW-G real-beta trigger.

**Shipped:**
- **T1 / T1.5:** `winback_dormant_cohort` end-to-end. **FIRST ACTIVATION** of S7.5 `validated_external` Klaviyo prior on a real fixture. `ENGINE_V2_BUILDER_WINBACK_DORMANT` default ON.
- **T2:** supplements serving-count parser. KI-18 closed. KI-27 deferred.
- **T3 + T3.x + T3.y + T3.z:** `replenishment_due` builder + Klaviyo PERL + 2026 H&B cross-flow `validated_external` prior + `audience_floor_sensitivity` driver + Considered surface population. Flag `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` default OFF.
- **T3.5 partial:** RejectedPlay surface fields populated at all 3 Considered-routing seams; `D-FLOOR-replenishment_due` LOCKED (60/150/350/1000 across Beauty subverticals, `mixed_beauty` 1.5×); D-S6-3 envelope citation refreshed.

**Deferred (Commit C):** Atomic flag flip + 5-fixture re-pin. Beauty G-1 fixture `cohort_n=0` at D-S6-4 per-SKU N≥30 gate (binding upstream of D-FLOOR). Resume trigger per KI-NEW-G: real beta-onboarding store at GROWTH/skincare with hero-SKU repeat-buyer count ≥150 in ±½-cadence window.

**Load-bearing invariants:**
- `ENGINE_V2_BUILDER_WINBACK_DORMANT` default ON (operator rollback via env var).
- `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` default OFF until KI-NEW-G trigger fires.
- All scaffolding live: priors block, floor resolver, T3.y sensitivity driver, T3.z renderer, T3.5 surface population, `CADENCE_DUE_REPEAT_BUYER` enum.
- 4 fixture-pin tests carry `strict=False` xfail markers with explicit KI-NEW-G reason strings; they lift in the same commit as Commit C activation.

**Caveats / dormant behavior:**
- `replenishment_due` is dormant on every pinned fixture today (cohort_n=0 at D-S6-4); production activation pending real beta.
- 3 new architectural-limitations KIs filed for Phase 9 coupled recalibration: **KI-NEW-G** (resume trigger), **KI-NEW-H** (D-S6-4 + D-S6-5 + D-FLOOR jointly), **KI-NEW-I** (Watching-row routing for cohort_n=0).
- Schema: `event_version=1` additive (RejectedPlay gains 3 Optional surface fields at T3.z; `AudienceArchetype` gains `CADENCE_DUE_REPEAT_BUYER` at T3.5 Commit A).
- Suite: 1497 passed / 14 skipped / 4 xfailed / 0 failed.

**Summary:** [agent_outputs/code-refactor-engineer-s6-t3_5-summary.md](agent_outputs/code-refactor-engineer-s6-t3_5-summary.md)

**Sprint 7 unblocked:** all S7 dependencies (S6 closed, S7.5 closed) satisfied. Next anchor: `discount_dependency_hygiene` + `cohort_journey_first_to_second` + `aov_lift_via_threshold_bundle` + 4-state abstain migration.

# Sprint 6.5 — Store Profile Layer MVP (2026-05-17 onward)

Anchor goal per [implementation-manager-s6_5-store-profile-layer-plan.md](agent_outputs/implementation-manager-s6_5-store-profile-layer-plan.md) and [Part IV of ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md): insert a new PROFILE step at the front of the engine pipeline (PROFILE → AUDIENCE → MEASUREMENT → SIZING → DECIDE). Produces a typed `StoreProfile` artifact consumed by every downstream gate. Triggered by S6-T1.5's surfacing the failure mode: synthetic Beauty fixture's 356-customer winback cohort failed the hardcoded 500-customer floor because V2 dropped the legacy `BUSINESS_STAGE` knob. 5 logical tickets (T1-T5), ~7 working days, beta-blocking. T5 is the only behavior-changing ticket; T4 holds a founder-review checkpoint on `gate_calibration.yaml` cell values before T5 starts.

**Founder decisions locked in (2026-05-17):**

- **Q1 — Token-dictionary authority:** ACCEPT Sephora + iHerb scraped vocabulary as the source-of-truth for `subvertical_taxonomy.yaml`. Source URLs documented inline in the YAML; tokens tagged `heuristic_unvalidated` with the same discipline as priors.
- **Q2 — Band-boundary uncertainty:** ACCEPT the conservative-broader floor rule. Stores within ±25% of a stage band boundary (e.g., ARR $2.6M, on the GROWTH/MATURE boundary at $3M) get the BROADER (more conservative, smaller-store) floor + an `uncertainty=HIGH` flag in profile.provenance.
- **Q4 — Gate calibration cell review:** CURATED ~20 high-leverage cells. The full ~616-cell table is too much for human review. T4 summary doc will present: Beauty/skincare × {startup, growth, mature, enterprise} (~12 cells), Supplements/protein × {startup, growth, mature, enterprise} (~12 cells), `mixed_beauty` + `mixed_supplements` rows (~6 cells), window assignments per sub-vertical (~10 cells). Total ~40 cells. The remaining ~576 cells default to the heuristic table without per-cell review.
- **Q5 — Subscription-led prioritization:** DEFER the `replenishment_due > winback_dormant_cohort` ordering change to S6-T3. S6.5 keeps its behavior surface to ONE flip (T5). Subscription detection still emits to profile.business_model in MVP; consumers wired in S6-T3.

**Multi-window evidence decisions locked in (2026-05-18, post-T3):**

Triggered by T3 founder envelope check revealing Beauty/skincare cadence is 53d while the IM plan sketch set primary_window=L28. Founder asked: are we losing the legacy multi-window weighted-vote signal? DS architect memo (returned 2026-05-18; full text in 2026-05-18 conversation transcript) recommended R1 + R2; founder approved both for T4, deferred L42.

- **R1 — `window_corroboration` as confidence modifier (FOLD INTO T4):** Primary window decides point estimate + p-value (unchanged). The two non-primary windows in `agreement_windows` produce a typed `PlayCard.measurement.window_corroboration` field with values `CORROBORATED | NEUTRAL | CONTRADICTED`. Trust engine reads it: CORROBORATED → confidence_label bumps one notch within its tier ceiling (Emerging → Trustworthy where trust-tier permits; NEVER crosses tier boundaries); CONTRADICTED → demote to Considered with new `WINDOW_DISAGREEMENT` ReasonCode; NEUTRAL → no change. Sign-only check (magnitude-ratio band deferred). Excludes primary from its own agreement check. Closes the asymmetry where today's directional pathway uses `_sign_agreement_count` but the prior-anchored pathway does not.
- **R2 — Cadence-derived primary window per cohort (FOLD INTO T4):** Replace the static `(vertical, subvertical) → primary_window` lookup with `round_to_nearest({L28, L56, L90}, cadence.median_reorder_days_by_sku_class[class])`. Fallback to static sketch table when cadence is INSUFFICIENT_DATA. **Gate OFF for SUBSCRIPTION_LED stores** — subscription cadence is contractual not behavioral; sub-led keeps static table read. Beauty/skincare 53d → L56 (was L28 sketch). Provenance records `cadence_derived_primary_window` or `subscription_led_static_window` rule fire.
- **L42 4th window — DEFERRED (2026-05-18):** Ship T4 with `{L28, L56, L90}` only. Document 35–48d cadence as a known quantization gap. Synthetic supplements fixture 38–40d cluster acknowledged as known calibration target, not blocking. Revisit after one real beta store. Test pins window set as `{L28, L56, L90}` (deferred-L42 decision is auditable).
- **NOT bringing back legacy weighted vote (0.30/0.60/0.10 weights):** sign-agreement is interpretable; weighted magnitudes are not. DS architect §1.

**T4 scope expansion:** ~2 days → ~3 days. Test count ~20 → ~28. Additional schema additions within `event_version=1`: `PlayCard.measurement.window_corroboration`, `ReasonCode.WINDOW_DISAGREEMENT`.

**Behavior-change posture by ticket:**

- T1, T2, T3, T4 — NO behavior change (impl behind default-OFF `ENGINE_V2_STORE_PROFILE` flag).
- T5 — ONLY behavior-changing ticket: flag flip + atomic Beauty + supplements G-1 fixture re-pin. The Klaviyo Beauty winback `validated_external` prior is expected to activate for the first time on a real fixture (the 356-customer cohort meets the new growth-stage skincare floor of ~200).

**Schema additions (additive within `event_version=1` frozen contract):**

- Typed `StoreProfile` dataclass on `EngineRun` with 9 sub-dataclasses (`Taxonomy`, `BusinessStage`, `BusinessModel`, `CadenceBaseline`, `SeasonalityContext`, `DataDepth`, `GateCalibration`, `MeasurementContext`, `ProfileProvenance`). All fields `Optional` with safe defaults so pre-S6.5 `engine_run.json` files continue to parse.
- One new feature flag: `ENGINE_V2_STORE_PROFILE` (default OFF at impl tickets; flip ON at T5).
- Three new YAMLs: `config/subvertical_taxonomy.yaml`, `config/seasonality_calendars.yaml`, `config/gate_calibration.yaml`. All cells tagged `heuristic_unvalidated`; same validation_status discipline as `priors.yaml`.

**Why this matters (the activation moment):**

S7.5 installed the priors validation contract (3 priors at `validated_external`) but the contract has been dormant on synthetic fixtures because Beauty's winback cohort (356 customers) fell below the hardcoded 500-customer floor. S6.5 introduces stage-aware floors that resize for $1-3M growth-stage beauty stores. At T5 flag flip, the Klaviyo `validated_external` Beauty winback prior is expected to anchor a posterior on a real fixture for the FIRST TIME. This is the activation moment for everything S7.5 built.

**Sprint 6.5 vs Sprint 7.5 risk shape:**

S7.5 was contract-installation with zero behavior change. S6.5 is similar (impl tickets T1-T4 are flag-OFF; T5 is the single flip). The difference: T5 expects a REAL behavior change on Beauty (the activation moment), not zero behavior change. Hard-stop discipline at T5 catches the case where the activation doesn't happen as expected (cohort STILL below new floor, or materiality below new floor, or numerics look wrong).

## Sprint 6.5 Ticket T1 closeout (2026-05-17)

**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t1-summary.md](agent_outputs/code-refactor-engineer-s6_5-t1-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## Sprint 6.5 Ticket T2 closeout (2026-05-17)

**Caveats:** - `taxonomy.subvertical` is dormant in the engine until T4 wires consumers (audience floors keyed on subvertical + measurement primary_window per subvertical). - The classifier's 1.3x LOW threshold may need tightening once T4's gate-calibration cells reveal which...

**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t2-summary.md](agent_outputs/code-refactor-engineer-s6_5-t2-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## Sprint 6.5 Ticket T3 closeout (2026-05-17)

**Schema:** `event_version=1` additive (4 new optional fields on existing T1 sub-dataclasses; all defaults preserve pre-T3 round-trip).
**Suite:** 1322 passed / 14 skipped (1 pre-existing wall-clock fail unrelated to T3).
**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t3-summary.md](agent_outputs/code-refactor-engineer-s6_5-t3-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## Sprint 6.5 Ticket T4 closeout (2026-05-18)

**Schema:** `event_version=1` additive (3 schema additions; all defaults preserve pre-T4 round-trip).
**Suite:** 100 S6.5 tests pass (T1+T2+T3+T4 combined). Pinned fixture sha256 byte-identical under flag OFF (18 regression tests pass).
**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t4-summary.md](agent_outputs/code-refactor-engineer-s6_5-t4-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## Sprint 6.5 Ticket T4.x closeout (2026-05-18)

**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t4-summary.md](agent_outputs/code-refactor-engineer-s6_5-t4-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## Sprint 6.5 Ticket T4.x.1 closeout (2026-05-18)

**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t4-summary.md](agent_outputs/code-refactor-engineer-s6_5-t4-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## Sprint 6.5 Ticket T4.y closeout (2026-05-18)

**Status:** Complete. main.py engine-pipeline wiring patch to ensure
the Store Profile builder runs at the documented seam before
guardrails consume `EngineRun.store_profile`. Behavior change is
flag-gated (still default OFF at T4.y close).

**Commit:** `cce4555 S6.5-T4.y: wire build_store_profile into
src/main.py pipeline pre-guardrails`

**File:** `src/main.py` (23-line wiring patch).

**Behavior:** Under `ENGINE_V2_STORE_PROFILE=true`, `engine_run.
store_profile` populated end-to-end. Default OFF; flag-OFF runs are
byte-identical with the legacy pipeline.

## Sprint 6.5 Ticket T4.y.1 closeout (2026-05-18)

**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t4-summary.md](agent_outputs/code-refactor-engineer-s6_5-t4-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## Sprint 6.5 Ticket T5 closeout (2026-05-18)

**Suite:** 1377 passed / 14 skipped / 0 failed (exceeds IM plan target of ~1346). **8 hard-stops all PASS:** (1) Beauty detected as beauty, supplements as supplements; (2) Beauty gate calibration non-empty; (3) Beauty GROWTH; (4) Beauty skincare HIGH; (5) supplements winback N...
**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t5-summary.md](agent_outputs/code-refactor-engineer-s6_5-t5-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7 priors-wiring — Memos 1/2/3/4 -> priors.yaml + enum surface (2026-05-20)

**Shipped:**
- 4 Gemini Deep Research memos + DS-architect verdict matrix saved verbatim
- 2 NEW play_id blocks in `config/priors.yaml::plays` authored in DICT FORM

**Load-bearing invariants:**
- The cross-pin test scoped to dict-form blocks pins YAML metadata <->
- The S7 AudienceArchetype additions use UPPER_SNAKE_CASE per founder-spec

**Caveats / dormant behavior:** - All enum additions are CONSUMER-DORMANT until S7-T1 / S7-T3 ship the builders + measurement_builder dispatch. Renderer-side display copy (`storytelling_v2::_WOULD_BE_MEASURED_BY_DISPLAY_COPY`) is NOT extended in this ticket — same posture as t...

**Schema:** event_version=1 additive (4 enum members + Optional audience_floor)
**Suite:** 1500 passed / 14 skipped / 4 xfailed / 0 failed (last full run 2026-05-20; +5 net tests via cross-pin file relative to pre-S7 baseline of ~1497).
**Summary:** [agent_outputs/code-refactor-engineer-s7-priors-wiring-summary.md](agent_outputs/code-refactor-engineer-s7-priors-wiring-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7-T2 closeout — `cohort_journey_first_to_second` builder (2026-05-20)

**Schema:** event_version=1 additive (1 enum member + ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND flag + 1 _PRIOR_ANCHORED dispatch key + 1 PLAYS entry + 1 BUILDERS entry + 1 audience_floors YAML block + 1 D-FLOOR DECISIONS entry).
**Suite:** test count expected +15 tests via the new file; full pytest run pending in this environment (Bash pytest blocked by sandbox; founder to run `python -m pytest -q tests/test_s7_t2_cohort_journey_first_to_second_builder.py` locally to confirm green before proceeding to...
**Summary:** [agent_outputs/code-refactor-engineer-s7-t2-summary.md](agent_outputs/code-refactor-engineer-s7-t2-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7-T4 closeout — 4-state abstain mode migration (2026-05-20)

**Shipped:**
- AbstainMode enum gains SOFT_BELOW_FLOOR + SOFT_AUDIENCE_TOO_SMALL
- `_compute_abstain_mode` refactored to majority-with-tiebreak rule per

**Load-bearing invariants:**
- Flag OFF: 2-state legacy semantics preserved byte-for-byte. Any
- Flag ON: TARGETING_HELD_UNDER_ABSTAIN MUST be excluded from the

**Caveats / dormant behavior:** mode slot is dormant on every pinned fixture today (renderer reads state). Surface activation lands at later sprint when renderer migrates to mode-aware copy.

**Schema:** event_version=1 additive (2 new AbstainMode enum values).
**Suite:** 1565+ passed (was 1497 before S7-priors-wiring + S7-T2; T4 adds 20+ tests).
**Summary:** [agent_outputs/code-refactor-engineer-s7-t4-summary.md](agent_outputs/code-refactor-engineer-s7-t4-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7-T1 — `discount_dependency_hygiene` builder (2026-05-20)

**Shipped:**
- New `discount_dependency_hygiene_candidates` audience builder + new
- New `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE` flag default OFF; main.py

**Load-bearing invariants:**
- Legacy `discount_hygiene` play_id PRESERVED untouched (founder Q1
- Supplements gets ZERO behavior change: no priors block, no

**Caveats / dormant behavior:** - Heavy-promo conditional bump (40%>discount_fraction → 80/200/500/1500 per D-FLOOR rule) is INTENTIONALLY DORMANT because `StoreProfile.commerce_posture.discount_fraction` does NOT exist today. Pinned by T18. **Founder Q surfaced:** ship the `c...

**Schema:** event_version=1 additive (1 PLAYS entry + 1 BUILDERS entry + 1 _PRIOR_ANCHORED entry + 1 ENGINE_V2_BUILDER_DISCOUNT_HYGIENE flag + 1 audience_floors YAML block; D-FLOOR DECISIONS entry pre-existed).
**Suite:** test count expected +19 new tests via the new file; full pytest run pending (sandbox-blocked); founder to run `python -m pytest -q tests/test_s7_t1_discount_dependency_hygiene_builder.py` then the full suite before S7-T1.5.
**Summary:** [agent_outputs/code-refactor-engineer-s7-t1-summary.md](agent_outputs/code-refactor-engineer-s7-t1-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7-T3 — `aov_lift_via_threshold_bundle` builder (2026-05-20)

**Shipped:**
- New `aov_lift_via_threshold_bundle_candidates` audience builder
- New `ENGINE_V2_BUILDER_AOV_BUNDLE` flag default OFF; main.py

**Load-bearing invariants:**
- Legacy `bestseller_amplify` play PRESERVED untouched (M2 Recommended
- Both verticals activate as Recommended Now (both blend-permitted

**Caveats / dormant behavior:** - Today's standard CSV does NOT carry `cart_state_total` / `current_cart_total` columns; the avg-AOV fallback (last-90d `net_sales` mean per customer) is the active path. Cart-state path pinned by T5 against a synthetic dataframe carrying the co...

**Schema:** event_version=1 additive (1 PLAYS entry + 1 BUILDERS entry + 1 `_PRIOR_ANCHORED` entry + 1 `ENGINE_V2_BUILDER_AOV_BUNDLE` flag + 1 audience_floors YAML block + 1 strict-resolver list entry; D-FLOOR DECISIONS entry pre-existed at LOCKED 2026-05-20).
**Suite:** test count expected +20 new tests via the new file (T17 ×8 parametrize cases + T17b ×4 + T18 ×6 + 14 non-parametrize); full pytest run pending (sandbox-blocked); founder to run `python -m pytest -q tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py` then the...
**Summary:** [agent_outputs/code-refactor-engineer-s7-t3-summary.md](agent_outputs/code-refactor-engineer-s7-t3-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7.6-T1.5 — Winback observed-effect activation (2026-05-21)

**Shipped:**
- T0 helper `src/measurement_observed.py` extracts per-store
- Tripwire result: Beauty `observed_n=334`; posterior shifted from

**Load-bearing invariants:**
- Cold-start (`observed_n=0`) remains prior-dominant by construction
- `src/measurement_observed.py` is the single seam for observed-effect

**Caveats / dormant behavior:** none for winback. Commit refs `713493b` (T0), `e8864d8` (T1), `28e4859` (T1.5).

**Schema:** unchanged.
**Suite:** Beauty + Supplements + M0 byte-identical; suite green.
**Summary:** [agent_outputs/code-refactor-engineer-s7_6-t1-summary.md](agent_outputs/code-refactor-engineer-s7_6-t1-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7.6-T2 — `replenishment_due` observed-effect wiring (partial, 2026-05-22)

**Shipped:**
- T2 plumbing landed at `b0c9980` — measurement_builder + main.py

**Load-bearing invariants:**
- T2 plumbing is correct and inert on Beauty under current fixtures —

**Caveats / dormant behavior:** T2.5 atomic flip DEFERRED per DS- architect Path (c) verdict. Resume trigger = Beauty clears D-S6-4 (real beta data OR future S6 reopen / KI-NEW-H Phase 9 recalibration). Do NOT regenerate the Beauty fixture to manufacture a passing tripwire.

**Schema:** unchanged.
**Suite:** 1678 passed / 14 skipped / 4 xfailed / 0 failed.
**Summary:** [agent_outputs/code-refactor-engineer-s7_6-t2_5-deferred-summary.md](agent_outputs/code-refactor-engineer-s7_6-t2_5-deferred-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7.6 sprint discipline — predict-`observed_n`-first rule (2026-05-22)

**DS-locked rule (load-bearing for all remaining S7.6 T*N* dispatches):**
Before each T*N* observed-effect wiring ticket, predict whether
`observed_n > 0` on the available Beauty fixture FIRST by reading
the builder + fixture together. If predicted-zero, plan T*N*.5 as
a Path-(c) deferral from the start — do NOT discover post-commit.

**Why this is load-bearing:** S7.6-T2.5 discovered the D-S6-4 gate
post-commit on `replenishment_due`. The same shape (Beauty fixture
suppressed upstream of the observed-effect seam) can recur on T3 /
T4 / T5. Predicting up-front avoids burning a T*N*.5 dispatch on a
no-card outcome.

**How to apply:** every remaining S7.6 T*N* dispatch brief must
include an explicit step: "predict `observed_n` on Beauty fixture
by tracing builder + fixture; if zero, plan deferral, not activation."

## S7.6 — Synthetic-fixture philosophy (load-bearing, 2026-05-22)

**Summary:** [agent_outputs/code-refactor-engineer-s7_6-c3-summary.md](agent_outputs/code-refactor-engineer-s7_6-c3-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7.6-C3 — Sprint 7.6 closed (2026-05-22)

**Shipped:**
- T7.5 flag flip: ``ENGINE_V2_AOV_THRESHOLD_FROM_DATA`` default OFF -> ON
- Beauty fixture re-pin (sha256 ``5afc4d62...`` -> ``1a5a35eb67898e6e

**Load-bearing invariants:**
- Single-demote-channel invariant restored. Every S6/S7-wired Tier-B
- CLAUDE.md Subagent Handoff Discipline section (founder-authored,

**Caveats / dormant behavior:** AOV bundle disposition on Beauty under flag-ON surfaces in Considered with ``cap_exceeded`` (rank 6, kept via C1 priority_prepend). Threshold-from-data computation succeeded (L90 P60 = $71.88 computed on the synthetic Beauty fixture). Supplement...

**Schema:** unchanged.
**Suite:** 1690 passed / 14 skipped / 4 xfailed / 2 xpassed (baseline preserved post-flag-flip after sha + flag-default test updates).
**Summary:** [agent_outputs/code-refactor-engineer-s7_6-c3-summary.md](agent_outputs/code-refactor-engineer-s7_6-c3-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7.6-continuation — sprint close (2026-05-23)

**Schema:** unchanged.
**Suite:** 1769 passed baseline preserved across the 13-commit arc; this sprint-close commit is doc-only (zero code change, M0 + Beauty + Supplements byte-identical).
**Summary:** [agent_outputs/code-refactor-engineer-s7_6-c3-summary.md](agent_outputs/code-refactor-engineer-s7_6-c3-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S7.6-CLI-FIX — Measurement observed-effect surfacing on Tier-B Recommended cards (2026-05-24)

**Shipped:**
- `src/measurement_builder.py:2252-2270` populates `Measurement.observed_effect`, `Measurement.p_internal`, `Measurement.n` from the existing `blend_provenance` stash (guarded by `primary_obs_result is not None and int(primary_obs_result.n) > 0`). No change to `Measurement` dataclass; no new PlayCard attribute.
- Tripwire test at `tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_recommended_cards_surface_observed_effect_on_beauty` — two-clause invariant on the four wired Tier-B plays (`winback`, `discount_dependency_hygiene`, `cohort_journey_first_to_second`, `aov_lift_via_threshold_bundle`; `replenishment_due` omitted per DS Option iii).
- Empirical verification on `data/healthy_beauty_240d/runs/d515aa26-…json`: all 3 Tier-B Recommended cards now carry observed-effect + n + p_internal on the canonical Measurement slot with `revenue_range.source=blend`.

**Load-bearing invariants:**
- **Three fields only.** `Measurement.consistency_across_windows` deferred (founder-confirmed 2026-05-24, accepted-as-designed per DS verdict §2/§3); requires its own DS verdict before any future agent adds the 4th field.
- **`drivers[]` remains the source of truth.** `_blend_provenance_for_card` at `src/decide.py:1524-1535` byte-identical; T6 copy ladder ("Cohort signal dominates" prefix) reads from drivers, not Measurement.
- **No top-level `blend_provenance` PlayCard attribute.** Per DS verdict §2 — the canonical surface is `Measurement.*` + `drivers[]`, not a parallel attribute.
- Single-demote-channel + 3-channel `priority_prepend` + T6 eligibility-gate invariants untouched (fix is purely inside `build_prior_anchored_play_card`; no dispatch surface change).
- M0 byte-identical; Beauty + Supplements pinned slate sha256 unchanged (`briefing.html` does not render the new Measurement fields).

**Caveats / dormant behavior:** `briefing.html` does NOT surface the new Measurement fields. Founder-accepted (2026-05-24): `briefing.html` is debug-only wiring scheduled to retire when the frontend app activates; inspection during beta-prep uses `engine_run.json` directly (canonical contract per Phase 6B Stop-Coding Line). KI-NEW-O xfail-reasoning refresh deferred to a separate test-hygiene pass.

**Schema:** unchanged (`Measurement` dataclass and `PlayCard` dataclass both untouched; only field population logic changed).
**Suite:** 1770 passed (was 1769) / 14 skipped / 4 xfailed / 2 xpassed / 0 failed.
**Summary:** DS verdict at `agent_outputs/ecommerce-ds-architect-s7_6-cli-wiring-gap-verdict-2026-05-23.md`; commit `d8ede8c`.

## S7.6-cleanup — probe-script archive + outputs/ removal (2026-05-24)

**Shipped:**
- 21 S7.6 spiral debug-probe scripts moved from `scripts/` to `scripts/archive/s7_6_probes/` (c2_helper_inert_probe, c2_supplements_trace_probe, s7_6_cli_wiring_trace, s7_6_t{2_5,3_5,4_5,5_5,6_5,7_5}_*probe/repin/inspect/trace files).
- `outputs/` directory removed (was a probe artifact, not engine output).
- `scripts/s7_6_t1_5_probe.py` left in place — already git-tracked from an earlier commit.

**Load-bearing invariants:** none (cleanup-only). Archived probes preserved for historical reference; if a similar spiral surfaces in S8+, the probes are available as a reproduction template.

**Schema:** unchanged. **Suite:** unchanged. **M0:** byte-identical.

## S8-T0 — KI-NEW-K Beauty Beta envelope re-fit (2026-05-24)

**Shipped:**
- `config/priors.yaml` lines 363-375 (`discount_dependency_hygiene.base_rate.beauty`) + lines 1110-1122 (`replenishment_due.base_rate.beauty`, founder-acked one-cell scope expansion per DS verdict §6 F1) re-fit from defective Beta(0.66,...
- SciPy-authoritative percentiles `(p10, p50, p90) = (0.0037, 0.0169, 0.0471)` computed via `scipy.stats.beta(1.32, 58.68).ppf(...)`; DS analytic ballpark `(0.0040, 0.0182, 0.0443)` superseded per DS verdict's "SciPy values are authorita...

**Load-bearing invariants:**
- **`PSEUDO_N_BY_STATUS = {VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}`** is the locked S7.5-T3 production table per DS verdict §2. No new statuses, no new numbers in S8. The `Prior.pseudo_N: Optional[int]` per-p...
- `HEURISTIC_UNVALIDATED` + `PLACEHOLDER` priors are refusal at sizing layer, never blended with low weight. Gate 2 (validation_status, S7.5) is the laundering protection — `pseudo_N` only governs validated priors.

**Caveats / dormant behavior:** Klaviyo PDF provenance verification (KI-NEW-K secondary issue: base64-image transcribed source numerics) noted in memos as out-of-S8-T0-scope follow-up. KI-NEW-J supplements `aov_lift_via_threshold_bundle` magnitude defers to S14 pre-private-bet...

**Schema:** unchanged (YAML-only data fix, no code change). **Suite:** 1770 passed, 14 skipped, 4 xfailed, 2 xpassed, 0 failed (unchanged from S7.6 CLI fix baseline). **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s8-t0-summary.md](agent_outputs/code-refactor-engineer-s8-t0-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S8 Q3/Q6/Q7 — DS verdict + founder ack: sprint shape locked (2026-05-24)

**Shipped:** DS architect verdict at `agent_outputs/ecommerce-ds-architect-s8-q3-q6-q7-verdict-2026-05-24.md` closes the three remaining S8 open questions from the IM plan Part E (Q4/Q5 + Q1/Q2 already closed by the prior pseudo_N verdict). All locks made through the S14-readiness lens.
- **Q3 (KI-NEW-L/M/N bundling): ALL THREE DEFER from S8.** Sprint stays at 4 tickets (T0 landed + T1 + T2 + T3 + T4). KI-NEW-L → **S13.5** (between S13-T4 atomic flip and S14-T1 dispatch); reasoning: S13 extends all 5 Tier-B builders wit...
- **Q6 (Play Library wave 1): CONCUR with IM default.** `{winback_dormant_cohort, replenishment_due, discount_dependency_hygiene}`. Including dormant `replenishment_due` (per KI-NEW-G honest-dormancy 2026-05-23) is the only wave-1 test c...

**Load-bearing invariants:**
- **S8 ticket scope LOCKED at 4** (T0 landed + T1 + T2 + T3 + T4). No T5/T6/T7. Schema-additive surface capped at exactly 3 new `PlayCard` fields (`evidence_source` + `sensitivity` + `provenance`); no 4th field.
- **KI-NEW-L deferral conditional invariant** (DS verdict §5 invariant 15): **"no new Tier-B builders through S13"** — if that breaks, KI-NEW-L escalates and must land before the new builder. Today: 5 wired Tier-B builders, no S8–S13 add...

**Caveats / dormant behavior:** Founder ack F1 received 2026-05-24: KI-NEW-L resume trigger is S13.5 (between S13-T4 atomic flip and S14-T1 dispatch). If post-S13/pre-S14 window is later reserved for something else (e.g., S14 dry-run on synthetic before real-merchant onboardin...

**Schema:** unchanged (verdict-only commit). **Suite:** unchanged. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s8-t1-summary.md](agent_outputs/code-refactor-engineer-s8-t1-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S8-T1 + T1.6 + T1.5 trio — EvidenceSourceChip live in production (2026-05-24)

**Shipped:** Three atomic commits land the first S8 trust-surface field end-to-end:
- `1372feb` (T1, impl): typed `EvidenceSourceChip` enum (4 values: `STORE_MEASURED`, `STORE_OBSERVED`, `INDUSTRY_PRIOR`, `OBSERVATIONAL`) at `src/engine_run.py:295-352`; `PlayCard.evidence_source: Optional[EvidenceSourceChip] = None` add...
- `7df2399` (T1.6, cfg-wiring fix): added `cfg=cfg` at 4 callsites of `build_prior_anchored_recommendations` in `src/main.py` (~L1332, L1378, L1426, L1478); the 5th (AOV bundle L1557) already had it from S7.6-T5. T1's flag was dead code...

**Load-bearing invariants:**
- **DS invariant 16 (new, 2026-05-24, DS-locked):** every flag-gated producer field MUST be exercised by a harness-level test calling `main.run_action_engine` end-to-end with the flag forced ON. Canonical test home: `tests/test_v2_harnes...
- **Structural callsite pin** at `tests/test_v2_harness_cfg_gated_fields.py`: regex-walks `src/main.py` and asserts every call to `build_prior_anchored_recommendations` threads `cfg=cfg`. Pattern-protects T2 (Sensitivity), T3 (provenance...

**Caveats / dormant behavior:** Supplements has no Tier-B Recommended cards firing today (aov_bundle vertically excluded per S7.6 close + replenishment_due dormant per KI-NEW-G honest-dormancy 2026-05-23 + winback/journey/discount_hygiene all land in Considered on supplements...

**Schema:** additive — `PlayCard.evidence_source: Optional[EvidenceSourceChip] = None` within `event_version=1`. Round-trip clean. **Suite:** 1770 → 1798 (+28 across T1+T1.6; T1.5 no change). **Pinned slates:** all 5 byte-identical across the 3 commits.
**Summary:** [agent_outputs/code-refactor-engineer-s8-t1-summary.md](agent_outputs/code-refactor-engineer-s8-t1-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S8 cleanup — probe script archive (2026-05-24)

**Shipped:** `scripts/s8_t1_5_probe.py` moved to `scripts/archive/s8_probes/` (mirrors S7.6 + S8-T0 probe-archive pattern). Single `git mv`; no other change.

**Load-bearing invariants:** none (cleanup-only). **Schema:** unchanged. **Suite:** unchanged. **M0:** byte-identical.

## S8-T2 + T2.5 + T3 + T3.5 + T4 + T4.5 — Sprint 8 CLOSE (2026-05-25)

**Shipped:** Six commits close Sprint 8 (`fcc87af` → `ce648fd`). All 3 S8 additive `PlayCard` trust-surface fields live in production + Play Library wave 1 directory structure with byte-identity enforcement.
- `fcc87af` (T2): `Sensitivity` typed dataclass (6 keys: 4 scenario revenue ranges + `pseudo_n_used` + `notes`) + `PlayCard.sensitivity` field + `ENGINE_V2_SENSITIVITY` separate flag default OFF + 25 new tests + harness parametrize row p...
- `47eebb2` (T2.5): `ENGINE_V2_SENSITIVITY` default `false` → `true`. Empirical tripwire: 3 Beauty Tier-B Recommended cards carry `sensitivity` block. Pinned slates byte-identical (renderer doesn't surface sensitivity per founder ack).

**Caveats / dormant behavior:** Supplements has no Tier-B Recommended cards firing (aov_bundle vertically excluded + replenishment_due dormant + winback/journey/discount_hygiene land in Considered on supplements). Supplements `engine_run.json` shows all 3 S8 trust-surface fiel...

**Schema:** 3 additive `PlayCard` fields within `event_version=1` (`evidence_source: Optional[EvidenceSourceChip]`, `sensitivity: Optional[Sensitivity]`, `provenance: Optional[Provenance]`); DS invariant 12 cap REACHED — no 4th S8 field permitted.
**Suite:** 1798 → 1882 (+84 across T2/T2.5/T3/T3.5/T4/T4.5). Sprint-total: 1770 → 1882 (+112). All 5 pinned fixtures byte-identical from sprint-start (`9e2f357`) to sprint-close (`ce648fd`): Beauty `f8676c9f…`, Supplements `13a91e6c…`, M0 (3 fixtures). M0 byte-identical throug...
**Summary:** [agent_outputs/code-refactor-engineer-s8-t4_5-summary.md](agent_outputs/code-refactor-engineer-s8-t4_5-summary.md) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`.

## S8-close cleanup — probe archive (2026-05-25)

**Shipped:** `scripts/s8_t3_5_probe.py` moved to `scripts/archive/s8_probes/` (mirrors S7.6 + S8-T0 + S8-T1.5 probe-archive pattern). Single `git mv`; no other change.

**Load-bearing invariants:** none (cleanup-only). **Schema:** unchanged. **Suite:** unchanged. **M0:** byte-identical.

## S10-T0 — lineage-keyed fatigue correctness fix (2026-05-25)

**Shipped:** `gate_recently_run` in `src/guardrails.py` re-keyed from `play_id`-only to the 4-tuple `lineage_id = sha1(store_id | play_id | audience_definition_id | audience_definition_version)`. Defensive inner-loop 4th-component match (enforced only when both sides carry the field). Both internal callsites updated. 7 new tests in `tests/test_s10_t0_lineage_keyed_fatigue.py`.

**Load-bearing invariants:**
- Fatigue key is the 4-tuple `lineage_id`; never reverts to `play_id`-only.
- `RECENTLY_RUN_FATIGUE_ENABLED` stays OFF (Sprint 1 closeout posture preserved).

**Caveats / dormant behavior:** flag OFF; behavior dormant until founder flips. Byte-identical on existing fixtures by construction.

**Schema:** unchanged. **Suite:** +7 new tests, all green. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s10-t0-summary.md](agent_outputs/code-refactor-engineer-s10-t0-summary.md) — commit `b1ed79f`.

## S10-T1 — BG/NBD substrate + ModelCard + four-state ModelFitStatus (2026-05-26)

**Shipped:** New `src/predictive/` package: `model_card.py` (typed four-state `ModelFitStatus` enum {VALIDATED, PROVISIONAL, INSUFFICIENT_DATA, REFUSED} + `ModelCard` dataclass + threshold loader) and `bgnbd.py` (fit + classifier + parquet writer). `config/gate_calibration.yaml::model_fit_thresholds` block (business-stage-keyed + vertical override on months + relaxation factors). `scipy<1.13` hard pin. Additive `EngineRun.predictive_models: Dict[str, Any] = {}` slot.

**Load-bearing invariants:**
- Four-state `ModelFitStatus` enum is the single authority on ML-fit outcomes; no fifth state.
- `predictive_models` is additive within `event_version=1`; default `{}` round-trips byte-identical on pre-S10 fixtures.

**Caveats / dormant behavior:** `ENGINE_V2_ML_BGNBD` default OFF at T1; no orchestration wiring until T1.5.

**Schema:** additive — `EngineRun.predictive_models`. **Suite:** new tests green. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s10-t1-summary.md](agent_outputs/code-refactor-engineer-s10-t1-summary.md) — commit `b1093e1`.

## S10-T1.4 — BG/NBD metric correction (Spearman + time-based holdout) (2026-05-26)

**Shipped:** DS-mandated correction to T1: replaced per-customer-frequency MAPE (denominator clamp to 1.0 made the metric meaningless on DTC populations) with rank-Spearman against a **time-based holdout** (`t_split = t_end - window_days`). VALIDATED/PROVISIONAL/INSUFFICIENT_DATA/REFUSED routing now uses Spearman + holdout-window agg_ratio.

**Load-bearing invariants:**
- BG/NBD gating metric is rank Spearman on a time-based holdout, not per-customer MAPE. Customer-hash holdout retired.
- Operational goal is within-audience ranking for Klaviyo dispatch — rank correlation is the right family.

**Caveats / dormant behavior:** flag still OFF at T1.4; the corrected metric is substrate-only until T1.5 atomic flip.

**Schema:** unchanged. **Suite:** updated tests green. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s10-t1.4-summary.md](agent_outputs/code-refactor-engineer-s10-t1.4-summary.md) — commit `3470f40`.

## S10-T1.5 — BG/NBD atomic flip + orchestration wire + rollback contract (2026-05-26)

**Shipped:** Atomic flip of `ENGINE_V2_ML_BGNBD` default ON; `fit_bgnbd` wired into `src/main.py` orchestration; `lifetimes==0.11.3` pinned; rollback contract test landed. 5/5 pinned synthetic fixtures land at REFUSED / INSUFFICIENT_DATA under DS-locked **Option γ** (honest Pivot 5 outcome — no fixture reshape, no synthetic VALIDATED coverage manufactured).

**Load-bearing invariants:**
- Pivot 5 honest synthetic outcome: pinned fixtures may land REFUSED; never reshape fixtures to manufacture VALIDATED coverage.
- Atomic flip = single commit (flag flip + orchestration wire + rollback test) per S7.6/S8 cadence.

**Caveats / dormant behavior:** VALIDATED path verified by in-code synthetic sanity (not via pinned fixtures). Real VALIDATED evidence deferred to S14 real-merchant data.

**Schema:** unchanged (additive payload uses T1 slot). **Suite:** +rollback test green. **M0:** briefing.html byte-identical across all 5 pinned fixtures.
**Summary:** [agent_outputs/code-refactor-engineer-s10-t1.5-summary.md](agent_outputs/code-refactor-engineer-s10-t1.5-summary.md) — commit `729d588`.

## S10-T2 — Gamma-Gamma substrate + chained refusal + window-aligned agg_ratio (2026-05-26)

**Shipped:** `src/predictive/gamma_gamma.py` (fit + classifier + parquet writer) behind `ENGINE_V2_ML_GAMMA_GAMMA` (default OFF at T2). DS-mandated fix on the window-alignment bug: holdout `pred_total` now uses holdout-window-aligned frequency, not train-window frequency (the original `pred * train_summary["frequency"]` shipped a `~7-8x` window mismatch — the 6.02 agg_ratio at seed=7 was the bug, not the DGP). **Chained refusal** contract: when BG/NBD is REFUSED/INSUFFICIENT_DATA, G-G short-circuits with `chained_bgnbd_refusal`.

**Load-bearing invariants:**
- G-G holdout agg_ratio is window-aligned (holdout-window frequency, not train-window).
- G-G is chained on BG/NBD acceptance; never reports VALIDATED in isolation from BG/NBD.

**Caveats / dormant behavior:** flag OFF at T2; orchestration wiring lands at T2.5.

**Schema:** additive (uses T1 `predictive_models` slot). **Suite:** new tests green. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s10-t2-summary.md](agent_outputs/code-refactor-engineer-s10-t2-summary.md) — commit `8c89f32`.

## S10-T2.5 — G-G atomic flip + orchestration wire + rollback contract (2026-05-26)

**Shipped:** Atomic flip of `ENGINE_V2_ML_GAMMA_GAMMA` default ON; `fit_gamma_gamma` wired into `src/main.py` immediately after the BG/NBD block; rollback contract test landed. 5/5 pinned synthetic fixtures land at `chained_bgnbd_refusal` (BG/NBD already REFUSED/INSUFFICIENT_DATA on every one, so G-G short-circuits per IM plan §C.2). Option γ posture preserved.

**Load-bearing invariants:**
- G-G orchestration runs strictly after BG/NBD and respects the chained-refusal short-circuit.
- Pivot 5 honest synthetic outcome preserved — no fixture reshape for VALIDATED G-G coverage.

**Caveats / dormant behavior:** VALIDATED G-G path verified by in-code synthetic sanity. Real VALIDATED evidence deferred to S14.

**Schema:** unchanged. **Suite:** +rollback test green. **M0:** briefing.html byte-identical across all 5 pinned fixtures.
**Summary:** [agent_outputs/code-refactor-engineer-s10-t2.5-summary.md](agent_outputs/code-refactor-engineer-s10-t2.5-summary.md) — commit `9950a87`.

## S10-T3 — dormant ML-fit ReasonCodes + precedence pin + docs + KI-NEW-P (2026-05-26)

**Shipped:** Two new dormant `ReasonCode` enum values on `src/engine_run.py`: `MODEL_FIT_INSUFFICIENT_DATA = "model_fit_insufficient_data"` and `MODEL_FIT_REFUSED = "model_fit_refused"` (additive within `event_version=1`; no emitter wired — S13 consumes). New `tests/test_reason_code_precedence_invariant.py` pinning the DS-locked four-gate precedence. `docs/engine_flags.md` updated with the ML-fit gate row + ranking-strategy fallback chain. KI-NEW-P filed (stage-grid threshold calibration suite; closure deferred to S14 real-merchant data).

**Load-bearing invariants:**
- ReasonCode precedence (DS-locked): **(1) audience-floor → (2) cohort p-value → (3) prior-validation → (4) ML-fit**. ML-fit is lowest precedence; never demotes between slate roles; only triggers silent fallback within audience ranking (`BG/NBD → CF → survival → RFM → recency`).
- Both new ReasonCodes are dormant — added to the enum but emitted by no code path until S13 audience-ranking integration.

**Caveats / dormant behavior:** PlayCard stubs (`predicted_segment`, `model_card_ref`) stay None at S10 close; S13 wires them. KI-NEW-P open.

**Schema:** additive — two new `ReasonCode` enum values within `event_version=1`. **Suite:** +precedence-invariant test green. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s10-t3-summary.md](agent_outputs/code-refactor-engineer-s10-t3-summary.md) — commit `03c042e`.

## S10-CLOSE — Sprint 10 ML Predictive Layer Part 1 substrate complete (2026-05-26)

**Shipped:** All 7 S10 tickets shipped (T0 + T1 + T1.4 + T1.5 + T2 + T2.5 + T3). BG/NBD + Gamma-Gamma + four-state `ModelFitStatus` + ML-fit gate (dormant) + business-stage thresholds + parquet writers under `data/<store_id>/predictive/` + 2 new dormant `ReasonCode` values. Option γ posture verified: 5/5 pinned synthetic fixtures REFUSED / INSUFFICIENT_DATA (BG/NBD) → `chained_bgnbd_refusal` (G-G). VALIDATED path verified by in-code synthetic sanity for both BG/NBD and G-G.

**Load-bearing invariants:**
- Three orthogonal gates remain ACTIVE; ML-fit is the fourth gate but DORMANT at S10 close (no emitter — S13 audience-ranking integration consumes it).
- Pivot 5 honest synthetic outcome — no fixture was reshaped to manufacture VALIDATED ML-fit coverage; real VALIDATED evidence comes from S14 real-merchant data.

**Caveats / dormant behavior:** PlayCard stubs (`predicted_segment`, `model_card_ref`) stay None at S10 close — S13 wires them. KI-NEW-P (stage-grid threshold calibration suite) open; closure deferred to S14. KI-NEW-Q and KI-NEW-R remain founder-deferred.

**Schema:** additive within `event_version=1` (predictive_models slot + two dormant ReasonCodes). **Suite:** all targeted suites green; briefing.html byte-identical across all 5 pinned fixtures sprint-start → sprint-close.
**Next:** S11 — ML Predictive Layer Part 2 (survival via `scikit-survival` Cox PH for replenishment timing + collaborative filtering via `implicit`).

## S11-T1 — Cox PH survival substrate + ModelCard ext + business-stage thresholds (2026-05-26)

**Shipped:** New `src/predictive/survival.py` (Cox PH fit + dual-gate classifier + parquet writer) behind `ENGINE_V2_ML_SURVIVAL` (default OFF at T1). `scikit-survival>=0.22,<0.24` added to requirements (NOT `lifelines` — DS substitution per S11 plan review §B). `config/gate_calibration.yaml::model_fit_thresholds.survival` block (stage-keyed `c_index` + `brier@90d` dual-gate + relaxation factors). Additive `ModelCard` fields `holdout_c_index` + `holdout_brier_score_90d`. Synthetic Cox DGP positive control: c-index 0.838 VALIDATED.

**Load-bearing invariants:**
- Dual-gate `ModelFitStatus` for survival = `c_index ≥ stage_floor AND brier@90d ≤ stage_ceiling`.
- `lifelines` is NOT used; the Cox PH dependency is `scikit-survival>=0.22,<0.24`.

**Caveats / dormant behavior:** flag OFF at T1; orchestration wire deferred to T1.5.

**Schema:** additive (uses T1 `predictive_models` slot + additive `ModelCard` fields). **Suite:** +22 tests green. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s11-t1-summary.md](agent_outputs/code-refactor-engineer-s11-t1-summary.md) — commit `3cfa06b`.

## S11-T1.5 — Cox PH survival atomic flip + orchestration wire + rollback contract (2026-05-26)

**Shipped:** Atomic flip of `ENGINE_V2_ML_SURVIVAL` default ON; `fit_survival` wired into `src/main.py` immediately after the G-G block; rollback contract test landed. 5/5 pinned synthetic fixtures land at `chained_bgnbd_refusal` (survival chains BG/NBD per S11-T1 contract; BG/NBD already REFUSED/INSUFFICIENT_DATA on every fixture). Option γ posture preserved.

**Load-bearing invariants:**
- Survival orchestration runs strictly after BG/NBD + G-G and respects the chained-refusal short-circuit.
- Pivot 5 honest synthetic outcome preserved — no fixture reshape for VALIDATED survival coverage.

**Caveats / dormant behavior:** VALIDATED survival path verified only by in-code synthetic Cox DGP (c=0.838); real VALIDATED evidence deferred to S14.

**Schema:** unchanged. **Suite:** +rollback test green. **M0:** briefing.html byte-identical across all 5 pinned fixtures.
**Summary:** [agent_outputs/code-refactor-engineer-s11-t1.5-summary.md](agent_outputs/code-refactor-engineer-s11-t1.5-summary.md) — commit `46a2101`.

## S11-T2 — Collaborative Filtering substrate (implicit ALS) — INDEPENDENT of BG/NBD (2026-05-26)

**Shipped:** New `src/predictive/cf.py` (implicit ALS fit + top-K recall@10 gate + coverage@10 diagnostic + parquet writer) behind `ENGINE_V2_ML_CF` (default OFF at T2). `implicit>=0.7,<0.8` added to requirements. `config/gate_calibration.yaml::model_fit_thresholds.cf` block (stage-keyed `min_customers` / `min_items` / `min_interactions_per_user` + `top_k_recall_validated/provisional` + ALS hyperparameter sub-keys). Additive `ModelCard` fields `holdout_top_k_recall` (PRIMARY) + `coverage_at_k` (DIAGNOSTIC ONLY — does NOT gate). Synthetic latent-segment ALS DGP positive control: recall@10 = 0.344 VALIDATED.

**Load-bearing invariants:**
- **CF is INDEPENDENT of BG/NBD** — `fit_cf` signature takes no `bgnbd_model_card` argument; no chained-refusal path. Pinned 4-layer (docstring + API + test + YAML comment).
- `coverage_at_k` is operator-visible popularity-bias diagnostic only; never enters the four-state classifier.

**Caveats / dormant behavior:** flag OFF at T2; orchestration wire deferred to T2.5.

**Schema:** additive (uses T1 `predictive_models` slot + additive `ModelCard` fields). **Suite:** +22 tests green. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s11-t2-summary.md](agent_outputs/code-refactor-engineer-s11-t2-summary.md) — commit `7690d2a`.

## S11-T2.5 — CF (implicit ALS) atomic flip + orchestration wire + rollback contract (2026-05-28)

**Shipped:** Atomic flip of `ENGINE_V2_ML_CF` default ON; `fit_cf` wired into `src/main.py` immediately after the survival PREDICTIVE_FIT block (NO `bgnbd_model_card` argument passed — independence preserved at the call site); rollback contract test landed, including Case D INDEPENDENCE PIN (BG/NBD OFF + CF ON → CF still fits; `chained_bgnbd_refusal` MUST NOT appear in `fit_warnings`). 5/5 pinned synthetic fixtures land INSUFFICIENT_DATA (`n_active_customers` < stage `min_customers` floor on Beauty's synthetic repeat-buyer ceiling). Option γ posture preserved.

**Load-bearing invariants:**
- CF independence pinned at orchestration call site — no `bgnbd_model_card` argument under any flag combination.
- Case D rollback test forbids `chained_bgnbd_refusal` from CF `fit_warnings`.

**Caveats / dormant behavior:** VALIDATED CF path verified only by in-code synthetic latent-segment DGP (recall@10=0.344); real VALIDATED evidence deferred to S14.

**Schema:** unchanged. **Suite:** +4-case rollback test green. **M0:** briefing.html byte-identical across all 5 pinned fixtures.
**Summary:** [agent_outputs/code-refactor-engineer-s11-t2.5-summary.md](agent_outputs/code-refactor-engineer-s11-t2.5-summary.md) — commit `b98eb0a`.

## S11-T3 — Sprint 11 close docs + KI-NEW-Q/R/S filings + KI-NEW-P extension (2026-05-28)

**Shipped:** Documentation-only close. `docs/engine_flags.md` updated with survival + CF gate rows + DS-locked ranking-strategy fallback chain (BG/NBD → CF → survival → RFM → recency) + the audit copy ("INSUFFICIENT_DATA on Beauty's first 90 days is EXPECTED..."). `docs/DECISIONS.md::D-S6.5-16` footnote records the `lifelines → scikit-survival` substitution rationale. `ROADMAP.md` §1 L13 + §2 L42 updated `lifelines → scikit-survival`. `STATE.md` §4 updated (predictive layer now 4 models; ML-fit still DORMANT). `KNOWN_ISSUES.md`: KI-NEW-P extended to ~30 numbers across 4 ML models; KI-NEW-Q (operator parquet query CLI), KI-NEW-R (3-library vendor-fork escape hatch — `lifetimes` + `scikit-survival` + `implicit`), KI-NEW-S (wall-clock flake on `test_inventory_updated_at_is_fresh`) filed.

**Load-bearing invariants:**
- Ranking-strategy fallback chain (DS-locked): `BG/NBD → CF → survival → RFM → recency`. RFM = floor; recency = last-resort.
- ML library substitution at S6.5: `lifelines` replaced by `scikit-survival` (Cox PH math identical; better-maintained; sklearn-ecosystem).

**Caveats / dormant behavior:** ML-fit gate still DORMANT at S11 close; S13 wires consumers. PIVOTS.md unchanged (DS confirmed no direction shift at S11 close).

**Schema:** unchanged (documentation-only). **Suite:** unchanged (no code). **M0:** byte-identical by construction.
**Summary:** [agent_outputs/code-refactor-engineer-s11-t3-close-summary.md](agent_outputs/code-refactor-engineer-s11-t3-close-summary.md) — commit pending (this one).

## S11-CLOSE — Sprint 11 ML Predictive Layer Part 2 substrate complete (2026-05-28)

**Shipped:** All 5 S11 tickets shipped (T1 + T1.5 + T2 + T2.5 + T3). Cox PH survival (scikit-survival; dual-gate c_index + Brier@90d) + Collaborative Filtering (implicit ALS; recall@10 stage-keyed) substrates + 2 atomic flips + sprint-close docs. Option γ posture extended to 5/5 synthetic REFUSED (survival chains BG/NBD) / INSUFFICIENT_DATA (CF). VALIDATED paths verified by in-code synthetic sanity for both substrates (Cox PH c=0.838; ALS recall@10=0.344). No fixture reshaped to manufacture VALIDATED coverage.

**Load-bearing invariants:**
- Three orthogonal gates remain ACTIVE; ML-fit substrate now spans 4 models (BG/NBD + G-G + survival + CF) but the gate remains DORMANT (no emitter — S13 consumes).
- Survival CHAINS BG/NBD; CF is INDEPENDENT of BG/NBD. Both pinned at API + test + docstring level.

**Caveats / dormant behavior:** PlayCard stubs (`predicted_segment`, `model_card_ref`) stay None at S11 close — S13 wires them. KI-NEW-P extended (~30 numbers across 4 ML models); KI-NEW-Q/R/S filed.

**Schema:** additive within `event_version=1` (predictive_models slot extension + additive ModelCard fields). **Suite:** all targeted suites green; briefing.html byte-identical across all 5 pinned fixtures sprint-start → sprint-close.
**Next:** S12 — ML Predictive Layer Part 3 (statistical RFM + cohort retention curves with bootstrapped CIs).

## S12-T1 — RFM substrate (custom code, 11 named segments, internal-consistency Spearman + quintile-coverage REFUSED guard) (2026-05-28)

**Shipped:** New `src/predictive/rfm.py` (~485 LoC, custom code; no third-party library) behind `ENGINE_V2_ML_RFM` (default OFF at T1). 11 named segments (Champions / Cannot Lose Them / Loyal Customers / At Risk / Need Attention / Potential Loyalists / Promising / New Customers / About To Sleep / Hibernating / Lost). `config/gate_calibration.yaml::model_fit_thresholds.rfm` (stage-keyed Spearman 0.60/0.65/0.70/0.70 VALIDATED + PROVISIONAL 0.40; `quintile_coverage_min < 0.05` REFUSED guard; `absolute_customers_floor=50`). Additive `ModelCard` fields `segment_monotonicity_spearman` + `quintile_coverage_min` (internal-consistency, NOT holdout). Synthetic monotone-LTV DGP positive control: Spearman=0.8909 VALIDATED.

**Load-bearing invariants:**
- RFM is INDEPENDENT of BG/NBD — `fit_rfm` signature takes no `bgnbd_model_card` argument (4-layer pin: docstring + signature + behavioral test + YAML comment).
- `segment_monotonicity_spearman` is internal-consistency-of-segmentation, NOT a holdout / fit-quality metric.

**Caveats / dormant behavior:** flag OFF at T1; orchestration wire deferred to T1.5.

**Schema:** additive (uses T1 `predictive_models` slot + additive `ModelCard` fields). **Suite:** +21 tests green. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s12-t1-summary.md](agent_outputs/code-refactor-engineer-s12-t1-summary.md) — commit `717f55f`.

## S12-T1.5 — RFM atomic flip + orchestration wire + rollback contract (2026-05-28)

**Shipped:** Atomic flip of `ENGINE_V2_ML_RFM` default ON; `fit_rfm` wired into `src/main.py` immediately after the CF block (NO `bgnbd_model_card` argument — INDEPENDENT mirrors CF, NOT chained survival/G-G); rollback contract test landed (4 cases incl. Case D INDEPENDENCE PIN). 1/5 pinned fixtures VALIDATED (`small_sm`, Spearman=0.93); 4/5 REFUSED via `quintile_collapse` (Beauty / Supplements / mid_shopify / micro_coldstart — synthetic monetary distributions don't exercise quintile breadth under `pd.qcut`). 5-layer independence pin (added behavioral test on synthetic-Beauty path). Pivot 5 honest synthetic outcome preserved.

**Load-bearing invariants:**
- RFM independence pinned at orchestration call site — no `bgnbd_model_card` argument under any flag combination.
- `quintile_collapse` REFUSED is the gate working as designed on synthetic-DGP shape, NOT a calibration miss (KI-NEW-V.2).

**Caveats / dormant behavior:** VALIDATED `small_sm` is structural-correctness signal per Pivot 5 S12-T2.5 clarifier, NOT predictive-accuracy claim; closure remains S14 real-merchant calibration.

**Schema:** unchanged. **Suite:** +rollback test green. **M0:** briefing.html byte-identical across all 5 pinned fixtures.
**Summary:** [agent_outputs/code-refactor-engineer-s12-t1.5-summary.md](agent_outputs/code-refactor-engineer-s12-t1.5-summary.md) — commit `61e63d8`.

## S12-T2 — Retention curves substrate + RetentionCard + cohort_diagnostics slot + monotonicity REFUSED gate (2026-05-28)

**Shipped:** New `src/predictive/retention.py` (~530 LoC, custom code + numpy percentile bootstrap; no third-party library) behind `ENGINE_V2_ML_RETENTION` (default OFF at T2). NEW `RetentionCard` dataclass (separate from `ModelCard`; reuses `ModelFitStatus` enum via Option A vocab-stacking). NEW top-level `EngineRun.cohort_diagnostics: Dict[str, Any]` slot — architecturally distinct from `predictive_models` (per DS S12 plan review §C, locked at `docs/DECISIONS.md::D-S12-1`). `config/gate_calibration.yaml::model_fit_thresholds.retention` (CI-width ceilings 0.25/0.20/0.15/0.15 VALIDATED; cohort_count floors 6/12/12/12; `min_cohort_size_floor=20`). **REFUSED gate: cumulative-retention monotonicity violation** (DS-locked promotion from tertiary diagnostic per §G). DS-mandated positive control (12 cohorts × 400 customers @ p=0.40): VALIDATED at CI=0.095 (DS spec accepted as Option (d) — cohort_size adjusted 200→400 per Bernoulli arithmetic floor of CI<0.10).

**Load-bearing invariants:**
- Retention is INDEPENDENT of BG/NBD; lives in `cohort_diagnostics`, NOT `predictive_models`. NO parquet artifact (curves JSON-shaped on slot).
- `cumulative_retention_monotonicity_violation == True` → REFUSED (data-shape pathology, not calibration miss).

**Caveats / dormant behavior:** flag OFF at T2; orchestration wire + atomic flip deferred to T2.5.

**Schema:** additive (NEW `cohort_diagnostics` top-level slot; tolerant `_from_dict_engine_run` round-trip; `RetentionCard` dataclass). **Suite:** +24 tests green. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s12-t2-summary.md](agent_outputs/code-refactor-engineer-s12-t2-summary.md) — commit `48abbe4`.

## S12-T2.5 — Retention atomic flip + cohort_diagnostics seam + first-occupant write (2026-05-28)

**Shipped:** Atomic flip of `ENGINE_V2_ML_RETENTION` default ON; `fit_retention` wired into `src/main.py` immediately after the RFM block (NO `bgnbd_model_card`, NO `data_dir` argument — retention writes NO parquet); rollback contract test landed (4 cases incl. architectural pin that `"retention"` is in `cohort_diagnostics` NOT `predictive_models`). Determinism comparator extended with first nested path under `cohort_diagnostics` (`cohort_diagnostics.retention.fit_timestamp`). Per-fixture: Beauty PROVISIONAL `cohort_count=6` below MATURE 12 VALIDATED floor (matches DS T2 §I prediction); Supplements VALIDATED via degenerate bootstrap CI=0.0 on n=38 cohort (Pivot-5-consistent ACCEPT per DS T2.5 review §E → KI-NEW-T).

**Load-bearing invariants:**
- Retention writes to `cohort_diagnostics["retention"]`, NOT `predictive_models` — architectural pin in rollback test Case B (D-S12-1).
- INDEPENDENCE pin (Case D): retention fits with all 5 other ML flags OFF; no `chained_bgnbd_refusal` in `fit_warnings`.

**Caveats / dormant behavior:** Supplements CI=0.0 VALIDATED is structural-correctness signal per Pivot 5 S12-T2.5 clarifier; closure trigger = S14 `min_cohort_size_floor` recalibration (KI-NEW-T).

**Schema:** unchanged from T2. **Suite:** +rollback test green. **M0:** briefing.html byte-identical across all 5 pinned fixtures.
**Summary:** [agent_outputs/code-refactor-engineer-s12-t2.5-summary.md](agent_outputs/code-refactor-engineer-s12-t2.5-summary.md) — commit `b312d48`.

## S12-T3-CLOSE — Sprint 12 close docs + KI-NEW-T/U/V filings + KI-NEW-P extension to 6 substrates (2026-05-28)

**Shipped:** Documentation-only close. `docs/engine_flags.md` renamed "S10-S11 predictive layer" → "S10-S12 predictive layer"; gate-row entries added for `ENGINE_V2_ML_RFM` + `ENGINE_V2_ML_RETENTION`; RFM documented as explicit floor of `BG/NBD → CF → survival → RFM (floor) → recency` ranking chain; S12 audit copy (RFM `quintile_collapse` working-as-designed; retention monotonicity = data-shape pathology). `docs/DECISIONS.md::D-S12-1` records `cohort_diagnostics`-vs-`predictive_models` architectural separation. `STATE.md` §4 updated (6-substrate predictive layer; new `cohort_diagnostics` slot; ML-fit still DORMANT). `PIVOTS.md` Pivot 5 gains one-line S12-T2.5 clarifier (NOT a new pivot). `ROADMAP.md` S12 SHIPPED 2026-05-28; S13 queued (audience-ranking consumer wiring + ranking-chain activation + S13-T0 ModelCard refactor candidate). `KNOWN_ISSUES.md`: KI-NEW-P extended to ~30+ numbers across 6 substrates with 3 distinct closure-criteria shapes; KI-NEW-T (CI=0.0 degenerate bootstrap), KI-NEW-U (stale tests cleanup), KI-NEW-V (DS T1.5/T2.5 nits backlog) filed. ARCHITECTURE_PLAN.md SKIP (archived per Phase 2 cutover).

**Load-bearing invariants:**
- KI letter discipline confirmed: A–S used; T/U/V next-available (Q/R/S used at S11).
- Pivot 5 S12-T2.5 clarifier is additive, NOT a new pivot number.

**Caveats / dormant behavior:** documentation-only commit; no code/test/fixture changes; PIVOTS.md changes scoped to single clarifier on Pivot 5.

**Schema:** unchanged. **Suite:** unchanged (no code). **M0:** byte-identical by construction.
**Summary:** [agent_outputs/code-refactor-engineer-s12-t3-close-summary.md](agent_outputs/code-refactor-engineer-s12-t3-close-summary.md) — commit pending (this one).

## S12-CLOSE — Sprint 12 ML Predictive Layer Part 3 substrate complete (2026-05-28)

**Shipped:** All 4 S12 substrate tickets shipped (T1 + T1.5 + T2 + T2.5) + sprint-close docs (T3-CLOSE). Statistical RFM (custom code; 11 named segments; internal-consistency Spearman + quintile-coverage REFUSED guard; INDEPENDENT of BG/NBD; floor of ranking chain) + cohort retention curves (custom code + numpy bootstrap; `RetentionCard` separate from `ModelCard`; NEW `cohort_diagnostics` slot; cumulative-monotonicity REFUSED gate; INDEPENDENT; NO parquet). Option γ posture extends — 10 fixture × substrate cells: 2 VALIDATED (RFM `small_sm` Spearman=0.93; retention Supplements via degenerate bootstrap n=38), 1 PROVISIONAL (retention Beauty), 7 REFUSED / INSUFFICIENT_DATA (4× RFM `quintile_collapse` on synthetic monetary distributions; 3× retention non-validated). Synthetic VALIDATEDs are structural-correctness signals per Pivot 5 S12-T2.5 clarifier, NOT predictive-accuracy claims.

**Load-bearing invariants:**
- Three orthogonal gates remain ACTIVE; ML-fit substrate now spans 6 predictive substrates (BG/NBD + G-G + survival + CF + RFM + retention); the gate remains DORMANT (no emitter — S13 consumes).
- Survival CHAINS BG/NBD; CF + RFM + retention are INDEPENDENT of BG/NBD. `cohort_diagnostics` slot architecturally distinct from `predictive_models` (D-S12-1).

**Caveats / dormant behavior:** PlayCard stubs (`predicted_segment`, `model_card_ref`) stay None at S12 close — S13 wires them. KI-NEW-P extended (~30+ numbers across 6 substrates with 3 closure shapes); KI-NEW-T/U/V filed. S13-T0 ModelCard refactor is a candidate ticket (DEFER-or-refactor at S13-T0 per DS S12 plan review §H).

**Schema:** additive within `event_version=1` (`predictive_models` slot extension + additive ModelCard fields + NEW top-level `cohort_diagnostics` slot + `RetentionCard` dataclass). **Suite:** all targeted suites green; briefing.html byte-identical across all 5 pinned fixtures sprint-start → sprint-close.
**Next:** S13 — Integration (audience-ranking consumer wiring + ranking-strategy fallback chain activation + S13-T0 ModelCard refactor candidate).

## S13-T0 — ModelCard refactor to `Dict[str, float] metrics` (FLAG-OFF; substrate-only) (2026-05-29)

**Shipped:** `ModelCard.metrics: Dict[str, float]` authoritative storage; 9 `InitVar` legacy kwargs + `__post_init__` migration + `__getattr__` shim (closed allowlist `_LEGACY_METRIC_KEYS`) for read-side back-compat. `asdict()` emits ONLY `metrics` — no duplicative legacy keys. Substrate producers in `bgnbd.py / gamma_gamma.py / survival.py / cf.py / rfm.py` write `metrics={...}` directly. RetentionCard untouched.

**Load-bearing invariants:**
- `metrics` is the authoritative storage; legacy `card.holdout_X` is a read-only shim — DO NOT add new typed fields, extend the dict.
- engine_run.json carries `metrics={...}` and no legacy top-level keys per substrate.

**Caveats / dormant behavior:** No flag (pure substrate refactor); no consumer wiring; renderer non-consumption grep-verified.

**Schema:** additive within `event_version=1` (Dict[str,float] field; legacy kwargs accepted via InitVar). **Suite:** green; back-compat read/write paths pinned. **M0:** briefing.html byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s13-t0-summary.md](agent_outputs/code-refactor-engineer-s13-t0-summary.md) — commit `722bcb3`.

## S13-T1 — Ranking-strategy module + AudienceIntent enum + intent-conditional chains (FLAG-OFF) (2026-05-29)

**Shipped:** NEW `src/predictive/ranking_strategy.py`; `AudienceIntent` str-Enum (GENERAL / REPLENISHMENT_TIMING / LOOKALIKE_EXPANSION); frozen `_CHAIN_ORDER_BY_INTENT` map; `RankingStrategyResult` dataclass; pure `rank_audience()` chain walker reading `card.fit_status` as a real dataclass field (NOT the legacy `__getattr__` shim). NEW flag `ENGINE_V2_RANKING_STRATEGY_CHAIN` default `false`. 17 positive-control synthetic tests + 3 flag-default tests + 1 ReasonCode-dormancy invariant allowlist update (chain-walker fit_warnings are operator-trace strings, NOT ReasonCode emissions).

**Load-bearing invariants:**
- DS-LOCKED selection rule (S13 plan review §D.1): PROVISIONAL never falls through to a downstream VALIDATED.
- `fit_warnings` grammar `"{LEVEL}:{substrate}"` strict; INSUFFICIENT_DATA vs REFUSED preserved.

**Caveats / dormant behavior:** FLAG-OFF at T1; T1.5 owns the atomic flip; no consumer wire.

**Schema:** unchanged (module only). **Suite:** +20 tests green. **M0:** briefing.html byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s13-t1-summary.md](agent_outputs/code-refactor-engineer-s13-t1-summary.md) — commit `4c087dc`.

## S13-T1.5 — Ranking-strategy atomic flag flip (FLAG-ON; NO consumer wire) (2026-05-29)

**Shipped:** Atomic flip of `ENGINE_V2_RANKING_STRATEGY_CHAIN` default `false → true`. Inline-inverted the T1 flag-default-OFF test (no KI-NEW-U growth, per S12-T1.5/T2.5 precedent). NO consumer wire-up (consumer wiring is T2's scope); no orchestration change in `src/main.py`; no PlayCard schema change.

**Load-bearing invariants:**
- Flag flip is a posture statement only; the chain walker is invoked exclusively by T2 consumer-wiring.
- Inline-invert pattern preserves test coverage post-flip; do NOT split into a separate KI.

**Caveats / dormant behavior:** Functionally dormant until T2 wires the consumer; this is intentional sequencing.

**Schema:** unchanged. **Suite:** unchanged count (in-place invert). **M0:** briefing.html byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s13-t1.5-summary.md](agent_outputs/code-refactor-engineer-s13-t1.5-summary.md) — commit `b646d29`.

## S13-T2 — PlayCard consumer wiring + Q-S13-4 LOCK + ML-fit-never-demotes test (FLAG-OFF) (2026-05-29)

**Shipped:** NEW `src/predictive/consumer_wiring.py` (`populate_play_card_consumers`); `src/engine_run.py` L167-183 comment revised per **Q-S13-4 LOCK** (ML-fit ReasonCodes emit ONLY on `model_card_ref.fit_warnings`, NEVER on `RejectedPlay.reason_code`); `PredictedSegment` + `ModelCardRef` extended additively (segment_name + audience_modal_share + n_audience + strategy_used + fit_status_chain + fit_warnings); Option II post-injection wire-site at `src/main.py` (after `apply_guardrails_to_injected`); DS-LOCKED modal-segment stability floor (`n<50` OR `share<0.30` → segment_name=None; audit fields uncensored); AST-aware `test_reason_code_precedence_invariant.py` refactor (ranking_strategy.py allowlist REMOVED — no longer needed); REQUIRED `tests/test_s13_ml_fit_never_demotes.py` 5-fixture runtime test; NEW flag `ENGINE_V2_PLAY_PREDICTED_SEGMENT` default `false`.

**Load-bearing invariants:**
- Q-S13-4 LOCK: ML-fit ReasonCodes emit ONLY on `model_card_ref.fit_warnings`; NEVER on `RejectedPlay.reason_code`. Pinned at L167-183 comment + AST grep + runtime 5-fixture test.
- Modal-segment stability floor (D-S13-2): `n_audience<50` OR `audience_modal_share<0.30` → `segment_name=None`.

**Caveats / dormant behavior:** FLAG-OFF at T2; T2.5 owns the atomic flip; Option II wire-site chosen by refactor-engineer without surfacing first (DS adjudicated technical decision correct; process should have been "raise then proceed" — see KI-NEW-Z).

**Schema:** additive (PredictedSegment + ModelCardRef extended; round-trip helpers extended). **Suite:** +20 tests green (9 unit + 11 invariant/positive-control). **M0:** briefing.html byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s13-t2-summary.md](agent_outputs/code-refactor-engineer-s13-t2-summary.md) — commit `187af49`.

## S13-T2.5 — PlayCard consumer atomic flip + ML-fit gate DORMANT→LIVE (2026-05-29)

**Shipped:** Atomic flip of `ENGINE_V2_PLAY_PREDICTED_SEGMENT` default `false → true`. **ML-fit gate transitioned DORMANT → LIVE** (emitter wired via `model_card_ref.fit_warnings` per Q-S13-4 LOCK; never demotes between slate roles). Sha ledger column added; renderer non-consumption grep pin extended (briefing.html does not consume `predicted_segment` or `model_card_ref`); 4-case rollback contract test landed.

**Load-bearing invariants:**
- ML-fit gate is LIVE but **NEVER demotes** between slate roles — precedence-pin held by `tests/test_s13_ml_fit_never_demotes.py` 5-fixture runtime + AST-aware `tests/test_reason_code_precedence_invariant.py`.
- Renderer non-consumption grep pin is the runtime contract anchor preserving briefing.html byte-identity.

**Caveats / dormant behavior:** First intentional engine_run.json schema change in S13 (additive only; pre-T2 payloads round-trip via tolerant helpers).

**Schema:** additive (flag-flip exposes T2 fields). **Suite:** +4-case rollback test green. **M0:** briefing.html byte-identical across all 5 pinned fixtures.
**Summary:** [agent_outputs/code-refactor-engineer-s13-t2.5-summary.md](agent_outputs/code-refactor-engineer-s13-t2.5-summary.md) — commit `af2a80e`.

## S13-T3 — month_2_delta typed slot + lineage-keyed detection (FLAG-OFF) (2026-05-29)

**Shipped:** NEW `MonthDelta` dataclass + `EngineRun.month_2_delta` slot + round-trip helper in `src/engine_run.py`; NEW isolated `src/predictive/month_2_delta.py` (~340 lines) — 6 substrates diffed (BG/NBD + G-G + survival + CF + RFM + retention); 21-day floor (D-S13-3 LOCKED); **lineage-change constraint** suppresses `segment_shifts` when `audience_definition_version` bumps (D-S13-3); orchestration wire AFTER T2 consumer-wiring at `src/main.py:2040+` (NOT in forbidden `L1380-1597` zone); NEW flag `ENGINE_V2_MONTH_2_DELTA` default `false`; 3 carry-forward nits (DS T2 §G nit 2 / DS T2.5 §J nit 1 + 2); REQUIRED positive-control synthetic (11 tests, Option E3 hybrid).

**Load-bearing invariants:**
- 21-day floor (D-S13-3): MonthDelta does NOT populate when `days_between < 21`.
- Lineage-change constraint (D-S13-3): `segment_shifts=None` (suppressed) when `audience_definition_version` bumps; substrate-fit-status comparable; retention CI delta comparable.

**Caveats / dormant behavior:** FLAG-OFF at T3; T3.5 owns the atomic flip; Pivot 8 contract is substrate-state-delta (NOT realized-outcome delta) — cold-start month-2 flows through EB n_observed shift, not ML refit.

**Schema:** additive within `event_version=1` (MonthDelta + EngineRun.month_2_delta slot). **Suite:** +15 tests green. **M0:** briefing.html byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s13-t3-summary.md](agent_outputs/code-refactor-engineer-s13-t3-summary.md) — commit `a97ab54`.

## S13-T3.5 — month_2_delta atomic flag flip + ML-fit month-2 extension (2026-05-29)

**Shipped:** Atomic flip of `ENGINE_V2_MONTH_2_DELTA` default `false → true` (second intentional engine_run.json schema change in S13). Inline-inverted T3 flag-default-OFF test. NEW 4-case rollback contract test (Case D = INDEPENDENCE PIN — detector still runs when other ML flags OFF; reports REFUSED → ABSENT honestly). Cascade env overrides on 7 prior rollback tests. Extension of `test_s13_ml_fit_never_demotes.py` with a month-2 sequence per DS S13 plan review §F. `tests/fixtures/pinned_sha_ledger.json` updated with `post_s13_t3_5` columns + _meta block.

**Load-bearing invariants:**
- ML-fit-never-demotes extended to month-2 sequence (current-run-after-prior-run); MonthDelta never routes to `RejectedPlay.reason_code`.
- Case D INDEPENDENCE PIN: detector RUNS with all other ML flags OFF — no crash, no fabrication, honest REFUSED→ABSENT.

**Caveats / dormant behavior:** None — both T2.5 and T3.5 schema changes now LIVE; briefing.html still byte-identical via renderer non-consumption.

**Schema:** unchanged from T3 (flag-flip only). **Suite:** +4-case rollback + month-2 extension; cascade-env retrofit on 7 prior tests. **M0:** briefing.html byte-identical across all 5 pinned fixtures.
**Summary:** [agent_outputs/code-refactor-engineer-s13-t3.5-summary.md](agent_outputs/code-refactor-engineer-s13-t3.5-summary.md) — commit `43e2ffe`.

## S13-T4-CLOSE — Sprint 13 close docs + KI-NEW-W/X/Y/Z + KI-NEW-P extension + KI-NEW-L S13.5 commitment (2026-05-29)

**Shipped:** Documentation-only sprint-close. `STATE.md` §4 ML-fit gate revised DORMANT → **LIVE** (precedence-pin); 6-substrates-with-CONSUMERS noted; PlayCard.predicted_segment + model_card_ref + EngineRun.month_2_delta LIVE bullets. `PIVOTS.md` Pivot 5 gains **§G.3 three-precondition clarifier** (NOT a new pivot). `ROADMAP.md` S13 SHIPPED 2026-05-29; S13.5 (KI-NEW-L collapse) + S14 (real-merchant private beta) queued. `docs/engine_flags.md` S10–S12 section renamed to **S10–S13 predictive layer + consumer wiring**; 3 flag rows added (`ENGINE_V2_RANKING_STRATEGY_CHAIN`, `ENGINE_V2_PLAY_PREDICTED_SEGMENT`, `ENGINE_V2_MONTH_2_DELTA`); Q-S13-4 LOCK + grammar + intent enum + month_2_delta floor/lineage constraint documented. `docs/DECISIONS.md`: **D-S13-1 / D-S13-2 / D-S13-3 / D-S13-4 NEW (LOCKED)**. `KNOWN_ISSUES.md`: KI-NEW-P extended to ~30+ numbers across S13 consumer-side calibration cells; KI-NEW-W/X/Y/Z filed; KI-NEW-L S13.5 commitment restated per DS Q-S13-6. `agent_outputs/INDEX.md` Sprint 13 section. ARCHITECTURE_PLAN.md SKIP (archived per Phase 2 cutover).

**Load-bearing invariants:**
- KI letter discipline confirmed: A–V used; W/X/Y/Z next-available (Q/R/S at S11; T/U/V at S12).
- Pivot 5 §G.3 clarifier is additive, NOT a new pivot number.

**Caveats / dormant behavior:** Documentation-only commit; no code/test/fixture changes; PIVOTS.md changes scoped to single clarifier on Pivot 5.

**Schema:** unchanged. **Suite:** unchanged (no code). **M0:** byte-identical by construction.
**Summary:** [agent_outputs/code-refactor-engineer-s13-t4-close-summary.md](agent_outputs/code-refactor-engineer-s13-t4-close-summary.md) — commit pending (this one).

## S13.6-T7.5 — NULL-REASON ENUM REGISTRY comment block + coverage test (2026-06-01)

**Shipped:** `# NULL-REASON ENUM REGISTRY` 30-line comment block in `src/engine_run.py` immediately before `class RevenueRangeSuppressionReason`; NEW `tests/test_null_reason_registry.py` (1 test pinning all 3 shipped pairs + 4 deferred documented); T7.5 CHANGELOG entry in v2.0.0 block.

**Load-bearing invariants:**
- Registry block documents 3 shipped pairs (RevenueRange / MonthDelta / PredictedSegment) + 4 deferred (CustomerIds / StoreProfile / ModelCard / CohortDiagnostics).
- Comment-only source change — no dataclass shapes, no new enums, no producer/consumer changes.

**Caveats / dormant behavior:** SHA ledger not re-pinned (comment-only change does not affect serialized output).

**Schema:** unchanged. **Suite:** 596 passed, 1 pre-existing failure, 7 skipped. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s13.6-t7.5-summary.md](agent_outputs/code-refactor-engineer-s13.6-t7.5-summary.md) — commit `015dd06`.

## S13.7-T4-CLOSE — Sprint 13.7 close docs + D-S13.7 decisions + KI-NEW-AC (2026-06-01)

**Shipped:** Documentation-only sprint-close. `PRODUCT.md` §8 Approval-State Seam paragraph. `docs/DECISIONS.md` D-S13.7-1 through D-S13.7-5 LOCKED. `ROADMAP.md` S13.7 SHIPPED 2026-06-01 + beta-sequence table updated. `STATE.md` §10 refreshed + agent-handoff key files + S13.7 pinning tests. `memory.md` S13.7-T1/T2/T3/T7b entries. `agent_outputs/INDEX.md` S13.7 section. `KNOWN_ISSUES.md` KI-NEW-AA confirmed resolved; KI-NEW-AB partial; KI-NEW-AC filed.

**Load-bearing invariants:**
- D-S13.7-5 LOCKED: filesystem-only handoff through S14 synthetic validation; no Postgres/API layer.
- PRODUCT.md §8 Approval-State Seam is the canonical seam doc for agents + narration swarm.

**Caveats / dormant behavior:** Doc-only. No Python source files modified.

**Schema:** unchanged (doc-only). **Suite:** no tests run (doc-only ticket). **M0:** byte-identical by construction.
**Summary:** [agent_outputs/code-refactor-engineer-s13.7-t4-summary.md](agent_outputs/code-refactor-engineer-s13.7-t4-summary.md) — commit `c21f63b`.

## S-FE — Evidence Layer spec landed + handoff-layer agents (2026-06-02)

**Shipped:** NEW `docs/evidence_layer.md` — the Evidence Layer as a first-class DS spec: the closed 9-member set (M1–M9) each bound to a frozen field, viz as a member, unified suppression, the descriptive/inferential frame (§8). Locks L-EV-1..12 (consumer-side view; assemblable from v2.0.0, convention-only) + L-EV-13..20 (descriptive/inferential viz gating, refused-data posture, dashboard boundary, per-mechanism selection map, the `Audience.descriptive_distribution` primitive). New handoff-layer subagents created (narration / MCP-integration / assembly) + a `root-cause-debugger` (prove-don't-assume) agent.

**Load-bearing invariants:**
- L-EV-2: closed 9-member set; `Audience.descriptive_distribution` is a richer M4 rendering, NOT a 10th member.
- L-EV-6: dollar axis only M3-VIZ / M8-VIZ on non-suppressed `source==BLEND`; L-EV-20: distribution charts are descriptive-only (count axis, no lift overlay).

**Caveats / dormant behavior:** Spec doc; zero engine behavior change. Visual projection is FRONTEND (Phase 3); narration is the claim projection (Phase 1).

**Schema:** unchanged (spec doc; describes the 2.1.0 additive shapes shipped below). **Suite:** no tests (doc + agents). **M0:** byte-identical.
**Summary:** `docs/evidence_layer.md` (the spec is its own authority) — commits `8fcf44c`, `ad305ba`, `a46757e`.

## S-FE — `Audience.descriptive_distribution` additive primitive (2026-06-02)

**Shipped:** FOUNDER-AUTHORIZED additive engine change. NEW `DescriptiveDistribution` atom on `Audience` (`kind`/`bins`/`counts`/`marker` + RULE-A `suppressed`/`suppression_reason`); `DistributionKind` closed 4-member enum (`DORMANCY_DAYS`/`AOV_GAP`/`REORDER_GAP_DAYS`/`DISCOUNT_FRACTION`); `DescriptiveDistributionSuppressionReason` closed 3-member enum. The 4 distributional builders stash their series; `measurement_builder` bins + types at the prior-anchored `Audience(...)` site. `schema_version` `2.0.0 → 2.1.0` (additive within the 2.x freeze).

**Load-bearing invariants:**
- Descriptive-only (L-EV-20): no dollar/lift/projected field on the atom; engine emits the binned series, never a chart-spec (L-EV-3 Stop-Coding Line).
- Outer Optional is `null_reason_exempt` (absence-typing lives inside the atom, mirroring `PlayCard.revenue_range`).

**Caveats / dormant behavior:** Marker `None` for 3 of 4 kinds by design (threshold scalars are TODO(S14)). DS APPROVE.

**Schema:** additive — `schema_version` 2.1.0; +3 $defs. **Suite:** 22 new tests; 822 passed (3 pre-existing failures unrelated). **M0:** byte-identical (renderer does not consume the field).
**Summary:** [agent_outputs/code-refactor-engineer-s-fe-descriptive-distribution-summary.md](agent_outputs/code-refactor-engineer-s-fe-descriptive-distribution-summary.md) — commit `1a5d989`.

## S-FE — detect.py stash-passthrough fix (KI-NEW-AE filed) (2026-06-03)

**Shipped:** Root-cause fix: the `AudienceResult → Candidate` conversion in `detect.py` dropped the `descriptive_distribution` stash, so the binned series never reached the producer. Proven by the `root-cause-debugger` agent (instrumented the drop site before editing, per prove-don't-assume) — not a fix-on-a-guess. Threaded the three stash fields through `Candidate`.

**Load-bearing invariants:**
- The stash (`descriptive_kind` / `descriptive_series` / `descriptive_marker`) survives `AudienceResult → Candidate`; the producer is the only site that bins + types it.

**Caveats / dormant behavior:** KI-NEW-AE FILED — `descriptive_distribution` cannot reach the Considered lane (`RejectedPlay` has no `Audience` atom); deferred to the frontend per-mechanism viz work OR S14. So M-DIST lights up only on a distributional play in the recommended lane.

**Schema:** unchanged (wiring fix on an additive 2.1.0 field). **Suite:** covered by the descriptive-distribution suite. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s-fe-descriptive-distribution-summary.md](agent_outputs/code-refactor-engineer-s-fe-descriptive-distribution-summary.md) — commit `4270616`.

## S-FE — RFM ModelCard `segment_distribution` (KI-NEW-AF filed) (2026-06-03)

**Shipped:** FOUNDER-AUTHORIZED additive. NEW `SegmentBand` (`{segment_name, n, share}` aggregate-only) + `RfmSegmentDistributionSuppressionReason` (closed 2-member) on the RFM `ModelCard`. Populated from `rfm_table["segment_name"].value_counts()` (already-computed, previously discarded — the L-EV-18 discarded-series diagnosis applied to RFM) ONLY when `fit_status ∈ {VALIDATED, PROVISIONAL}`; RFM suppresses as a UNIT on REFUSED/INSUFFICIENT_DATA (L-EV-15, no descriptive twin). Additive WITHIN 2.1.0 — no second version bump (the literal was already `2.1.0`).

**Load-bearing invariants:**
- Aggregate + descriptive only (L-EV-17/20): no per-customer rows, no monetary/lift field; n DESCENDING, ties broken by canonical LTV rank.
- RULE-A `FIT_NOT_VALIDATED` on the 7 short-circuit `fit_rfm` returns — never a fabricated/partial distribution.

**Caveats / dormant behavior:** KI-NEW-AF FILED — stale `test_flag_default_off_at_t1` (ENGINE_V2_ML_RFM flipped ON at S12-T1.5); pre-existing clean-tree failure, deferred to S14 test cleanup with KI-NEW-U. `FLAG_OFF` enum member declared but not emitted today. DS APPROVE.

**Schema:** additive within 2.1.0; +2 $defs. **Suite:** 11 new tests; affected suites green. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s-fe-rfm-segment-distribution-summary.md](agent_outputs/code-refactor-engineer-s-fe-rfm-segment-distribution-summary.md) — commit `ad2c92e`.

## S13.7-T7b — Deferred null-reason enums + dead-code sweep (2026-06-01)

**Shipped:** `StoreProfileNullReason` (2 members) + `EngineRun.store_profile_null_reason` paired field on `EngineRun` (additive v2.x); `ModelCardAbsenceReason` (3 members) + `CohortDiagnosticsAbsenceReason` (2 members) declared as agent-reference vocabulary. `_surface_mechanism_for_play` dead code deleted from `src/decide.py` (C2). KI-NEW-AA RESOLVED. KI-NEW-AB partial (C2 shipped; C1 deferred S14).

**Load-bearing invariants:**
- RULE A (D-S13.6-5): `store_profile_null_reason` paired with `store_profile` under default-ON `ENGINE_V2_STORE_PROFILE` flag.
- `_surface_mechanism_for_play` gone; zero call sites confirmed before deletion.

**Caveats / dormant behavior:** `ONBOARDING_INCOMPLETE` declared but not yet emitted — TODO(S14). `targeting_non_causal_prior` in `src/sizing.py` deferred to S14 (active call sites).

**Schema:** additive (new field + 3 enums on EngineRun). **Suite:** 7 passed, 1 skipped. **M0:** `"store_profile_null_reason": null` added to all existing fixtures (additive).
**Summary:** [agent_outputs/code-refactor-engineer-s13.7-t7b-summary.md](agent_outputs/code-refactor-engineer-s13.7-t7b-summary.md) — commit `910cb13`.

## S13.7-T3 — `docs/mechanism_contract.md` narration-agent spec (2026-06-01)

**Shipped:** NEW `docs/mechanism_contract.md` (193 lines) — DS-locked spec for all 10 `MechanismType` values + `parameters` dict key/type shapes. Zero Python files touched. Parameter key cross-check against `src/decide.py::_parameters_for_mechanism` — zero mismatches post DS Q5 revision.

**Load-bearing invariants:**
- `docs/mechanism_contract.md` is the single narration-agent spec surface. Changes require DS review + `engine_run.py` version bump per D-S13.7-3.
- 4 types carry `None` parameter values with TODO(S14) markers — correctly reflected in the contract file with `Implementation note` callouts.

**Caveats / dormant behavior:** `LOOKALIKE_HIGH_VALUE_PROSPECT` has no active emission site at v2.0.0 — documented for completeness. Wiring is S14+ scope.

**Schema:** unchanged (doc-only). **Suite:** no tests (doc-only). **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s13.7-t3-summary.md](agent_outputs/code-refactor-engineer-s13.7-t3-summary.md) — commit `75f54e9`.

## S13.7-T2 — JSON Schema export + run manifest (2026-06-01)

**Shipped:** `src/run_manifest.py` (NEW `write_run_manifest`); `tools/generate_schema.py` (NEW schema generator); `tools/validate_engine_run.py` (NEW round-trip validator, jsonschema soft dep); `schemas/engine_run.v2.json` (NEW — 47 $defs). Per-run `manifest.json` written on every successful engine run. `materialize_audience_csvs` return type `None → dict[str, str]` (status per aud_def_id).

**Load-bearing invariants:**
- `manifest.json` at `data/<store_id>/runs/<run_id>/manifest.json` is the agent artifact-discovery contract (D-S13.7-2).
- `audience_materialization_status: "SUPPRESSED_SUBSTRATE_REFUSED"` annotated for refused substrates.

**Caveats / dormant behavior:** `jsonschema` not in requirements.txt — soft import in `validate_engine_run.py`. `StoreProfile` nested types not fully enumerated in schema $defs.

**Schema:** unchanged (runtime). **Suite:** 13 new tests (7 manifest + 6 schema); 1 pre-existing failure. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s13.7-t2-summary.md](agent_outputs/code-refactor-engineer-s13.7-t2-summary.md) — commit `39767d5`.

## S13.7-T1 — Audience customer-ID resolver (2026-06-01)

**Shipped:** NEW `src/audience_resolver.py` with `materialize_audience_csvs()`; per-PlayCard CSV at `data/<store_id>/runs/<run_id>/audiences/<aud_def_id>.csv` (columns: customer_id, aov_individual, predicted_segment, rank_score). SUBSTRATE_REFUSED: empty CSV with header row. `src/segments.py` hard-retired (raises `NotImplementedError`). `CustomerIdsNullReason` enum (2 members) declared in `engine_run.py`.

**Load-bearing invariants:**
- SUBSTRATE_REFUSED path: never silent absence — always writes empty CSV with header row (D-S13.7-1).
- `src/segments.py` retired; no legacy segment CSV path. `run_summary.json["segments"]` is `[]` going forward.

**Caveats / dormant behavior:** `aov_individual = 0.0` (RFM parquet schema v1 gap). `CustomerIdsNullReason` declared but field pairing on `Audience` deferred to S14.

**Schema:** additive (`CustomerIdsNullReason` enum in engine_run.py). **Suite:** 6 passed; 3 golden re-pinned. **M0:** byte-identical (engine_run.json unchanged; resolver is pure side-effect).
**Summary:** [agent_outputs/code-refactor-engineer-s13.7-t1-summary.md](agent_outputs/code-refactor-engineer-s13.7-t1-summary.md) — commit `14ba7e4`.

## S13.6-T8 — Sprint close: renderer rewire + doc hardening (2026-06-01)

**Shipped:** `storytelling_v2.py` rewired — renderer reads `PlayCard.mechanism_intent.type.value` directly; `_mechanism_for_play` YAML-lookup function deleted; shim in `render_rejected_card` retired; `MechanismIntent` import added. `PIVOTS.md` Pivot 2 T6/T8 addendum. `docs/engine_flags.md` standalone `INCLUDE_DEBUG_FIELDS` section. `docs/DECISIONS.md` D-S13.6-1 through D-S13.6-5 LOCKED. `ROADMAP.md` S13.6 SHIPPED 2026-06-01. `STATE.md` §10 (output contract v2.0.0). `KNOWN_ISSUES.md` KI-NEW-AA / KI-NEW-AB confirmed correct.

**Load-bearing invariants:**
- Renderer reads `mechanism_intent.type.value` directly; no YAML-lookup fallback for any PlayCard or RejectedPlay mechanism slot.
- `_mechanism_for_play` deleted — its 3 call sites were the only consumers.

**Caveats / dormant behavior:** `briefing.html` mechanism line now reflects the typed enum value string (e.g., `WINBACK_REACTIVATION_EMAIL`); narration agents will render prose from this atom downstream.

**Schema:** unchanged (renderer-only + doc-only). **Suite:** 596 passed, 1 pre-existing failure, 7 skipped. **M0:** byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s13.6-t8-summary.md](agent_outputs/code-refactor-engineer-s13.6-t8-summary.md) — commit `787a721`.

## S13-CLOSE — Sprint 13 Integration / consumer-wiring substrate complete (2026-05-29)

**Shipped:** All 8 S13 tickets shipped (T0 + T1 + T1.5 + T2 + T2.5 + T3 + T3.5 + T4-CLOSE). The most architecturally important sprint in S10-S13: the beta-blocking consumer-wiring sprint. All 6 predictive substrates (BG/NBD + G-G + survival + CF + RFM + retention) now have CONSUMERS via `src/predictive/ranking_strategy.py` (intent-conditional chains: GENERAL / REPLENISHMENT_TIMING / LOOKALIKE_EXPANSION) + `src/predictive/consumer_wiring.py` (modal-segment floor) + `src/predictive/month_2_delta.py` (21-day floor + lineage-change constraint). PlayCard.predicted_segment + PlayCard.model_card_ref LIVE. EngineRun.month_2_delta LIVE (substrate-state-delta per Pivot 8, NOT realized-outcome delta). ML-fit gate transitioned DORMANT → LIVE at T2.5 (emitter via `model_card_ref.fit_warnings` ONLY per Q-S13-4 LOCK; **never demotes between slate roles**; pinned by `tests/test_s13_ml_fit_never_demotes.py` 5-fixture + month-2 extension + AST-aware `tests/test_reason_code_precedence_invariant.py`).

**Load-bearing invariants:**
- Q-S13-4 LOCK (D-S13-1): ML-fit ReasonCodes emit ONLY on `model_card_ref.fit_warnings`; NEVER on `RejectedPlay.reason_code`.
- Three orthogonal gates still ACTIVE; **fourth gate (ML-fit) now LIVE but lowest precedence** — never demotes between slate roles. 6 predictive substrates all have consumers.

**Caveats / dormant behavior:** small_sm framing per the §G.3 three-precondition clarifier on Pivot 5 (predicted_segment.segment_name populates only when (a) RFM VALIDATED, (b) modal-segment floor cleared, AND (c) DECIDE produces ≥1 PlayCard for the audience). KI-NEW-L collapse honored as **S13.5 commitment** between S13-T4 and S14-T1. KI-NEW-W/X/Y/Z filed; KI-NEW-P extended (~30+ numbers across S13 consumer cells).

**Schema:** additive within `event_version=1` (`metrics: Dict[str,float]` + extended `PredictedSegment`/`ModelCardRef` + `MonthDelta` + `EngineRun.month_2_delta` slot). **Suite:** all targeted suites green; briefing.html byte-identical across all 5 pinned fixtures sprint-start → sprint-close.
**Next:** S13.5 — KI-NEW-L collapse (5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` → 1 PRIOR_ANCHORED dispatch). After S13.5: S14 — real-merchant private beta onboarding → KI-NEW-P closure window across all 6 substrates + S13 consumer-side cells.
