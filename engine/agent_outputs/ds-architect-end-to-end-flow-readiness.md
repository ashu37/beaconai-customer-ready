# DS Architect — End-to-End Flow Readiness (Post-S13.6)

**Date:** 2026-05-30
**Founder question:** Post-S13.6, can I validate the 6-stage app flow end-to-end on synthetic data (Shopify integration deferred)?
**Verdict:** **Mostly yes, but +1 small sprint (S13.7) needed before agent build can start.**

---

## One-sentence verdict

**Post-S13.6 the engine carries stages 1–3 end-to-end on synthetic data, but stages 4–6 require S13.7 (audience customer_id resolver + JSON-Schema export + mechanism_type enum spec) before the agent/frontend build can start.**

---

## Per-stage status

| Stage | Status | Detail |
|---|---|---|
| 1. CSV ingest (synthetic data → engine) | **WORKS post-S13.6** | Already wired today. `python -m src.main --csv <path> --brand <store_id> --out <dir>`. Multi-store = shell loop. |
| 2. Run engine per merchant | **WORKS post-S13.6** | Per-merchant substrate parquets at `data/<store_id>/predictive/`; per-merchant `memory.db`. |
| 3. Handoff JSON | **PARTIALLY WORKS post-S13.6** | Contract clean post-S13.6, but no published JSON-Schema — agent builders reverse-engineer from src code. **Needs S13.7-T2.** |
| 4. Narration + frontend + evidence viz | **NEEDS NON-ENGINE WORK** | Founder/team scope; engine ships enough atoms post-S13.6. Approval state correctly NOT in engine (immutable runs). |
| 5. Post-approval Klaviyo bundle assembly | **NEEDS NEW ENGINE WORK (S13.7-T1)** | `PlayCard.audience_definition_id` does NOT materialize a customer_id list today. Legacy `segments/*.csv` covers hardcoded segments only, NOT v2 ML-ranked audiences. |
| 6. Manually ready for upload | **PARTIALLY WORKS** | Works mechanically via legacy CSV writer; needs S13.7-T1 audience resolver to map approved PlayCards to the right segment CSVs. |

---

## Critical gaps beyond S13.6

1. **Audience customer_id resolver (P0).** `PlayCard.audience_definition_id` must materialize `data/<store_id>/runs/<run_id>/audiences/<aud_def_id>.csv` (columns: `customer_id`, `aov_individual`, `predicted_segment`, `rank_score`). Without this, Stage 5 has no concrete deliverable on synthetic data.

2. **JSON-Schema / pydantic export for v2.0.0 contract (P0).** Without a published schema, every agent builder reverse-engineers from `src/engine_run.py` dataclasses. Ship `schemas/engine_run.v2.json` (generated from dataclasses) + `tools/validate_engine_run.py`.

3. **Per-run filesystem manifest (P1).** A `data/<store_id>/runs/<run_id>/manifest.json` enumerating: `engine_run.json` path, audience CSV paths, parquet artifact paths, retention curves path. Agents scan one file to find everything.

4. **mechanism_type enum + parameters dict shape (P0, founder rec #4).** This is *new* contract surface, not just stripping prose. Needs concrete enum values per `_PRIOR_ANCHORED` registry × current legacy plays. Should be specified inside S13.6, not punted.

5. **Approval-state seam doc (P1).** Engine does not own approval state, but must document that runs are immutable and approval state lives in the agent DB. One paragraph in `PRODUCT.md`.

6. **Send-time recommendation atom (P2, deferrable).** Mechanism parameters dict can carry `send_time_hint: Literal["transactional_window", "engagement_peak", null]`. Punt to narration agent if it has brand-voice timing logic.

---

## Recommended additional ticket: S13.7 (3 tickets, ~3 days)

**S13.7 — Agent handoff completion.** Insert after S13.6, before S14.

- **T1: Audience customer_id resolver.** For each `PlayCard` in `recommendations` + `recommended_experiments`, materialize `data/<store_id>/runs/<run_id>/audiences/<audience_definition_id>.csv` from substrate parquets + audience builder logic. Keys off `audience_definition_id` for D-1 lineage stability.
- **T2: JSON-Schema export + run manifest.** Generate `schemas/engine_run.v2.json` from `src/engine_run.py` dataclasses; emit `manifest.json` per run enumerating all artifacts; ship `tools/validate_engine_run.py` round-trip test.
- **T3: mechanism_type enum + parameters dict specification.** Lock the closed set of `mechanism_type` values + per-type `parameters` dict shape. This is the contract the narration agent codes against.

**Total additional delay:** ~3 days. Without it, agent build will hit the audience-resolver gap on first end-to-end synthetic run.

---

## Founder action items

1. **Confirm S13.7 scope (3 tickets above) and sequencing between S13.6 and S14.**
2. **Decide where `mechanism_type` enum lives** — in `src/engine_run.py` (recommended, alongside other typed enums) or `src/mechanisms.py` (cleaner separation).
3. **Decide who owns send-time logic** — engine emits a hint atom OR narration agent infers. **DS recommends narration-agent ownership** (engine stays decision-shaped, not scheduler-shaped).
4. **Confirm that legacy `segments/*.csv` writer can be retired** once S13.7-T1 audience resolver ships. Two parallel artifact paths will confuse agents.
5. **Approve "engine produces immutable runs; approval state is agent-DB concern" as documented seam** in PRODUCT.md.
6. **Confirm filesystem-only handoff through synthetic validation** (no Postgres / API layer between engine and agents until AWS migration). DS strongly recommends.

---

## Sequencing summary

```
[Today: S13 SHIPPED]
↓
S13.5 — KI-NEW-L collapse (1 ticket, ~1 week; committed)
↓
S13.6 — engine_run.json agent-contract cleanup (3-4 tickets, ~1-2 weeks; from prior verdict)
↓
S13.7 — Agent handoff completion (3 tickets, ~3 days)
↓
[FOUNDER/TEAM: build narration MCP agent + assembly MCP agent + frontend]
↓
S14 — Real-merchant private beta onboarding (when agents/frontend ready)
```

**Total engine work before founder handoff:** ~2.5 sprints (S13.5 + S13.6 + S13.7).
**S14 timing:** gated on founder/team's agent + frontend build, not on more engine sprints.

---

## What works synthetically end-to-end post-S13.7

After S13.5 + S13.6 + S13.7 ship, a founder running:
```bash
python -m src.main --csv data/synthetic_beauty/orders.csv --brand synthetic_beauty --out runs/
```
will get in `data/synthetic_beauty/runs/<run_id>/`:
- `engine_run.json` (typed v2.0.0, no prose, no Any)
- `manifest.json` (enumerates artifacts)
- `audiences/<audience_definition_id>.csv` (per approved PlayCard's customer list)
- `predictive/*.parquet` (substrate artifacts)
- `cohort_diagnostics/retention.json` (retention curves)

The narration MCP agent reads `engine_run.json` + business context (discount policy, brand voice) → produces narration. Frontend renders for approval. Post-approval, operator opens the `audiences/` folder, uploads matching CSVs to Klaviyo manually. Loop closed.

---

## Relevant files (absolute paths)

- `/Users/atul.jena/Projects/Personal/beaconai/PRODUCT.md` (merchant journey table L20–29; D-1..D-8 L91–98)
- `/Users/atul.jena/Projects/Personal/beaconai/STATE.md` (pipeline §1; substrate parquets §4 L74–89)
- `/Users/atul.jena/Projects/Personal/beaconai/PIVOTS.md` (Pivot 2 Stop-Coding Line L24–30; Pivot 8 L86–92)
- `/Users/atul.jena/Projects/Personal/beaconai/ROADMAP.md` (S13.5 L13; S13–S14 sequence L72–80)
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` (`run()` L539; predictive parquet paths L975–1257)
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` (PlayCard schema; no `customer_ids` on Audience confirmed)
- `/Users/atul.jena/Projects/Personal/beaconai/src/store_id.py` (`resolve_store_id`)
- `/Users/atul.jena/Projects/Personal/beaconai/src/segments.py` (legacy segment CSV writer L9)
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/consumer_wiring.py` (modal-segment population from RFM parquet)
- `/Users/atul.jena/Projects/Personal/beaconai/tools/export_store.py` (D-4 per-store full export)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ds-architect-engine-readiness-for-agents.md` (prior verdict; 4 P0 + 7 P1)
