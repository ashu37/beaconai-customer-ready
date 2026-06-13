# BeaconAI Handoff Architecture

**Status:** Approved architecture (founder GO 2026-06-01). Basis for the IM phase-level milestone plan.
**Scope:** The handoff layer between the immutable Python engine, two Python MCP agents (narration + assembly), the agent DB, and the React/Express frontend. Local end-to-end fully specified; AWS is a marked, deferred block.
**Review chain:** Plan-agent architecture → `ecommerce-ds-architect` review (APPROVE WITH CHANGES) → founder GO.
**Authority honored:** `PRODUCT.md` §4/§8/§9, `STATE.md`, `docs/DECISIONS.md` D-S13-1/-2/-3 + D-S13.7-1/-5, `docs/mechanism_contract.md`, `src/engine_run.py` (v2.0.0 schema authority), `src/run_manifest.py`, `src/audience_resolver.py`.

---

## 1. Component map

| Component | Repo / location | Owns | Built by |
|---|---|---|---|
| **Decision engine** | beaconai `src/` | Typed atoms only. Writes immutable `runs/<run_id>.json` snapshot, `manifest.json`, audience CSVs, parquets. Emits NO prose. | *(immutable — shipped at S13.7)* |
| **Narration MCP** | beaconai, new module (e.g. `src/mcp/narration/`) | Reads a finalized run via manifest pointer; produces merchant-facing prose per PlayCard. Authors language; invents NO numbers; honors RULE A. Stateless. | narration-mcp-engineer |
| **Assembly MCP** | beaconai, new module (e.g. `src/mcp/assembly/`) | Post-approval. Reads approved play_ids from agent DB, resolves audience CSVs via manifest, assembles the Klaviyo bundle honoring materialization status. Writes a NEW artifact; never mutates engine output. | assembly-mcp-engineer |
| **Agent DB (approval store)** | TBD backend behind a thin interface (KI-FE-1 DEFERRED) | Approval state: `(run_id, play_id) → {approved\|rejected\|deferred, ts}`. The only mutable state in the handoff. Outside the engine (§8). | mcp-integration-engineer (interface only) |
| **Integration layer** | beaconai (MCP transport) + Express broker | Run discovery, MCP transport + registration, approval-store interface, end-to-end wiring. | mcp-integration-engineer |
| **Express server** | beaconai-frontend-app `server/index.ts` | Today static-only. Becomes the browser↔MCP broker + approval-store HTTP facade. Browser never speaks MCP. | mcp-integration-engineer (broker) + frontend-engineer (static) |
| **React frontend** | beaconai-frontend-app `client/src/` | Renders the slate (Dark Command Center), displays narration, approve/reject/defer UI, triggers assembly, surfaces CSV download. Renders only contract-carried numbers. | frontend-engineer |

### Data / control flow (local)

```
                        (offline, monthly, immutable)
  python -m src.main ──► data/<store>/runs/<run_id>.json   (snapshot, FILE)
                         data/<store>/runs/<run_id>/manifest.json
                         data/<store>/runs/<run_id>/audiences/*.csv
                         data/<store>/predictive/rfm.parquet
                                  │
            ┌─────────────────────┴───── manifest.json is the path index ──────────┐
            ▼                                                                        ▼
   ┌──────────────────┐   reads snapshot via         approved play_ids   ┌──────────────────┐
   │  Narration MCP   │   manifest pointer           (from agent DB)      │  Assembly MCP    │
   │ (Python, stdio)  │──► prose per PlayCard         ─────────────────►  │ (Python, stdio)  │
   └────────▲─────────┘                                                   └────────▲─────────┘
            │ MCP                                                                  │ MCP
   ┌────────┴──────────────── Express broker (server/index.ts) ──────────────────┴────────┐
   │  - holds MCP client sessions (stdio) to both Python servers                           │
   │  - exposes plain HTTP/JSON to browser: /api/run, /api/narrate, /api/approve, /api/bundle│
   │  - hosts the ApprovalStore interface (KI-FE-1 backend TBD)                            │
   └───────────────────────────────────▲───────────────────────────────────────────────────┘
                                        │ fetch() JSON
                              ┌─────────┴──────────┐
                              │   React frontend   │
                              └────────────────────┘
```

---

## 2. The handoff contract

### 2a. Run discovery + manifest-pointer resolution (load-bearing)

Entry point is always `data/<store_id>/runs/<run_id>/manifest.json`. Never a hardcoded snapshot path, never `receipts/engine_run.json` (mutable mirror, NOT authoritative). Resolution (identical for both MCPs + the app):
1. Read `manifest.json` (`schema_version`, `run_id`, `store_id`, `created_at`, `artifacts`).
2. Snapshot = `(manifest_dir / artifacts.engine_run).resolve()`. Since `artifacts.engine_run == "../<run_id>.json"`, this resolves one level **up** — a sibling of the run *directory*. This is exactly why hardcoding fails (KI-FE-6, confirmed on disk).
3. Audience path = `(manifest_dir / audiences[i].path).resolve()` → `audiences/<aud_def_id>.csv`. Entries carry `audience_definition_id`, `play_id`, `audience_materialization_status` ∈ {`MATERIALIZED`, `SUPPRESSED_SUBSTRATE_REFUSED`, `NOT_MATERIALIZED`}.

### 2b. Narration consumes / emits
Consumes v2.0.0 `EngineRun` (import `src/engine_run.py`). Surfaceable fields: `play_id`, `evidence_source` (the chip), `confidence_label`, `audience.{definition,size,fraction_of_base}`, `measurement.{observed_effect,n,primary_window}`, `revenue_range.{p10,p50,p90,source,suppressed,suppression_reason}`, `mechanism_intent.{type,parameters}`, `model_card_ref.fit_warnings` (audit-only), `predicted_segment.segment_name` (+ null reason). Considered: `RejectedPlay.reason_code` + `held_reason_detail`. Emits a separate narration artifact keyed `(run_id, play_id)`; never writes back. **See §7 DS locks — several consume-list fields are footguns.**

### 2c. Frontend on approval
Sends `{ run_id, store_id, play_id, decision: "approved"|"rejected"|"deferred" }`. Engine snapshot never touched. Store keyed `(run_id, play_id)` (run-scoped only — see DS lock 5).

### 2d. Assembly consumes / emits
Consumes approved play_ids from the agent DB (NOT the engine); per play, the manifest's audience entry → resolves the CSV (columns `customer_id, aov_individual, predicted_segment, rank_score`). Emits a NEW Klaviyo bundle **outside** the run dir; honors materialization status; never fabricates customers; no Klaviyo API call (D-S13.7-5).

---

## 3. MCP transport (resolves KI-FE-5)

**stdio** between the Express broker and each Python MCP server; **plain HTTP/JSON** between browser and Express. The browser is never an MCP client. Rationale: MCP servers are Python and import `src/engine_run.py` directly — they belong on the engine host. Express already exists and becomes the broker (smallest change; zero-config stdio locally — no ports/CORS/auth). **AWS trade-off:** stdio assumes co-located child processes; AWS wants streamable HTTP MCP transport. Isolate behind one `McpClient` factory — local returns stdio, AWS returns HTTP; the browser-facing REST contract is unchanged.

---

## 4. Seams that must stay swappable for AWS

| Seam | Local impl | Interface | AWS swap |
|---|---|---|---|
| **Artifact storage** | Local FS, navigated via manifest pointers | `ArtifactStore`/run-locator: `(store_id, run_id)` → manifest → resolve relative pointers. No consumer does raw `open()` on hardcoded paths. | S3 with the **same** `data/<store_id>/runs/<run_id>/` key shape. |
| **Agent-DB / approval store** | TBD (KI-FE-1 DEFERRED) — code against `ApprovalStore` only | `ApprovalStore`: `setDecision(run_id, play_id, decision)`, `getApproved(run_id) → play_id[]`, `getAll(run_id)`. | Managed Postgres/Aurora; same interface. |
| **MCP transport** | stdio | `McpClient` factory in Express | streamable HTTP per container. |

---

## 5. Recommended phased path (milestone-level)

- **Phase 0 — Fixture (Step 0).** Owner: mcp-integration-engineer (drives) + engine. Green run on disk: `healthy_beauty_240d` (fallback `small_sm`), all 5 artifacts, ≥1 `MATERIALIZED` audience, non-abstain slate. **Must include** ≥1 suppressed-`revenue_range` card and ≥1 `SUPPRESSED_SUBSTRATE_REFUSED` audience so laundering branches are exercised before prose templates exist (DS §6). Never relax cold-start gates via `.env`. Closes KI-FE-3/4. **Blocks everything.**
- **Phase 1 — Narration MCP.** Owner: narration-mcp-engineer. Reads run via manifest pointer, validates, emits prose per card. **Bakes in all DS locks 1/2/3/6/7/8 from the start** (§7). Deps: Phase 0.
- **Phase 2 — Integration spine.** Owner: mcp-integration-engineer. Express broker spawns narration MCP over stdio; `/api/run` + `/api/narrate`. Define `ApprovalStore`, `ArtifactStore`, `McpClient` interfaces + `/api/approve`. Deps: Phase 1.
- **Phase 3 — Frontend slate + approval.** Owner: frontend-engineer. Reconcile `mockData.ts` to real v2.0.0 (KI-FE-2). Render slate, display narration, wire approve/reject/defer. Honors DS lock 3 (no `fit_warnings` co-located with slate-role copy). Deps: Phase 2.
- **Phase 4 — Assembly MCP + download (LOCAL E2E MILESTONE).** Owners: assembly-mcp-engineer + mcp-integration-engineer (`/api/bundle`) + frontend-engineer (download UI). Honors DS lock 4 (`MATERIALIZED` ≠ correct audience) + 6 (CSV columns list-construction only). Deps: Phases 2 + 3.
- **Phase 5 — AWS hosting. DEFERRED — do not open until founder signals.** Owner: aws-infra-engineer. Containerize; S3 same key shape; swap the three seams via Phase-2 interfaces. No logic changes; local stays runnable without AWS; no Shopify/Klaviyo prod integration (§9). Fleshed out only after local works end-to-end.

---

## 6. Open risks / decisions (cross-ref KI-FE-*)

- **KI-FE-1** approval-store backend — DEFERRED; code against `ApprovalStore` interface, don't pick backend.
- **KI-FE-2** mockData drift — confirmed real; Phase 3 reconciles types from `src/engine_run.py` first.
- **KI-FE-5** MCP transport — resolved: stdio broker + REST to browser (§3).
- Cross-repo type coupling — frontend mirrors `src/engine_run.py` with no shared package; contract frozen at 2.0.0 (additive-only). Consider schema-derived types later; no codegen now.
- Abstain path must be **rendered**, not dodged — frontend shows the typed abstain reason, never an empty screen.
- Bundle artifact location — assembly writes **outside** `runs/<run_id>/` (e.g. sibling `bundles/<run_id>/`) to preserve immutability.

---

## 7. DS-LOCKED CONSTRAINTS (ecommerce-ds-architect, 2026-06-01 — APPROVE WITH CHANGES)

These are **pinned constraints**, not prose notes. They have an established silent-regression risk (handoff discipline, single-demote-channel). They MUST be carried into the Phase 1 narration brief and Phase 4 assembly brief.

1. **Narration consumes `evidence_source` (the chip), NEVER `evidence_class`.** Per `src/engine_run.py:729-732`: `EvidenceClass` (`measured`/`directional`/`targeting`/`weak`) "tags the *internal evidence class* used by the M3/M4 statistical machinery"; `EvidenceSourceChip` "tags the *epistemic provenance* surfaced merchant-facing." Narrating `evidence_class == "measured"` as "we measured this on your store" overclaims — **"Zero Tier-A plays exist today"** (`src/engine_run.py:743`).

2. **No card with `evidence_source != STORE_MEASURED` may have its `revenue_range` narrated as lift / incremental / expected-from-sending.** Per `src/engine_run.py:744-746`, `STORE_OBSERVED` means "a store-observed metric moved in a direction that justifies an intervention; **the metric is not itself the causal estimate of the intervention's lift.**" Today that is *every* card (no Tier-A plays). The range is a prior-anchored posterior on a baseline rate, not predicted lift.

3. **`fit_warnings` (incl. the literal `MODEL_FIT_REFUSED` level) is an audit/operator surface only** — never narrated as a reason on a Recommended card, never co-located with slate-role copy. Preserves D-S13-1 (ML-fit ReasonCodes emit ONLY on `model_card_ref.fit_warnings`, NEVER on `RejectedPlay.reason_code`) at the presentation layer. ML-fit silent fallback (BG/NBD → CF → survival → RFM → recency) is invisible-by-design.

4. **Assembly must NOT treat `MATERIALIZED` as proof of correct audience.** `src/audience_resolver.py:300-307` has a degraded path: with no `audience_ids_resolver`, it writes the **entire RFM substrate** with only a stdout warning, and `:194-202` then labels it `MATERIALIZED` (row-count > 1). A bundle from that CSV emails the whole base under a targeted play — wrong customers with a green light. Invariant to quote: "The merchant-reputation killer is wrong customers, not zero customers."
   - **DS DECISION (2026-06-01, Phase 0): Route (a) — harden the resolver. NOT the manifest flag.** Production `main.py:2060-2066` always passes a resolver, so the full-substrate path is unreachable today — it is a latent tripwire for the future assembly-MCP caller. Hardening: the degraded path writes **empty + `NOT_MATERIALIZED`** (NOT a hard crash — that would violate D-S13.7-1 "never silent absence" + the non-fatal-write contract). The fix MUST cover the resolver-absent branch (`:300-307`), the resolver-raises fall-through (`:288-292`), AND a third trigger surfaced in implementation: **empty/falsy `play_id` ⇒ `NOT_MATERIALIZED`** (resolution cannot run without a play id). NOTE: a resolver that returns the **empty set** is NOT a degraded case — it is a legitimate zero-match audience that falls through to the filter and maps to `SUPPRESSED_SUBSTRATE_REFUSED` via the row-count fallback (pinned by `test_resolver_returns_empty_set_status_is_substrate_refused`). No `audience_filtered` field, no manifest schema bump. Route (b) deferred (additive `1.0.0→1.1.0` if ever needed). **SHIPPED Phase 0 (`src/audience_resolver.py`, 12 tests).**
   - **Standing constraint regardless:** route (a) fixes only the full-substrate-leak instance. `MATERIALIZED` is still NOT proof of correctness in general (`aov_individual=0.0`, CSV `predicted_segment` bypasses the D-S13-2 floor — lock 6). The assembly brief keeps this lock's sentence permanently.

5. **`(run_id, play_id)` is run-scoped only.** Honors D-1 (PRODUCT.md §6) + D-S13-3 (lineage bump → `segment_shifts` suppressed, not faked). The current manifest (`src/run_manifest.py:197-203`) carries no version/lineage.
   - **DS DECISION (2026-06-01, Phase 0): DEFER `audience_definition_version` on the manifest.** Beta is single-run (PRODUCT.md §5); `_audience_definition_version` is a constant `return 1` today (`main.py:109-116`); D-S13-3 lineage discipline already runs **engine-side** in `month_2_delta.py` BEFORE the handoff, so the manifest needs no version field during beta. **Mitigation (a hard constraint, not a note):** no narration/assembly/approval logic may cache, compare, or join across `run_id`s — two runs with the same `(play_id, audience_definition_id)` may carry different lineages the manifest does not distinguish. **Re-open L5** the moment `_audience_definition_version` becomes non-constant OR any consumer reasons across runs (then add the field + wire a real source in one change; additive `1.0.0→1.1.0`).

6. **CSV columns `aov_individual` and `predicted_segment` are for Klaviyo list construction ONLY, never narration.** `aov_individual` is hardcoded `0.0` (`src/audience_resolver.py:311-313`); CSV `predicted_segment` is the raw parquet `segment_name` and **bypasses the D-S13-2 modal-segment stability floor** (`n_audience<50` OR `audience_modal_share<0.30` → `segment_name=None`). Merchant-facing segment claims come only from `PlayCard.predicted_segment.segment_name` (which honors the floor). **No merchant-facing AOV figure exists in the v2.0.0 handoff at all.**

7. **The three TODO(S14) None-param mechanism types are named explicitly in the narration brief** and may emit no fabricated dollar/share figures: `THRESHOLD_BUNDLE_OFFER` (`threshold_aov`/`current_median_aov` both `None`), `DISCOUNT_DEPENDENCY_HYGIENE` (`current_discount_share`/`target_discount_share` both `None`), `REPLENISHMENT_REMINDER`. Plus the five Tier-B types carry `{}` parameters — name the mechanism, invent zero parameters. Two None-classes are distinct: `mechanism_intent is None` (RULE A — no mechanism line) vs `.type` populated with empty/None `parameters` (check before use).

8. **Narration emits NO merchant-facing dollar figure that is not a non-suppressed `revenue_range.{p10,p50,p90}` with `source=BLEND`.** This single rule subsumes the AOV trap, the `opportunity_context`/`NonLiftAtom` boundary, and the suppressed-range case. When `revenue_range.suppressed=True`, narrate audience + (real, if any) context only.

**Sequencing lock:** locks 1/2/3/6/7/8 go into the **Phase 1** narration brief (not Phase 3) — prose templates encode the laundering paths if they ship without these, and they're expensive to walk back after a merchant has seen the overclaim. **Lock 4's resolver hardening (route a) lands in Phase 0** (before the fixture is frozen); lock 4's standing "MATERIALIZED ≠ correct" sentence + lock 6 are enforced in **Phase 4** (assembly). Lock 5's deferral + run-scoped mitigation is carried into the **Phase 4** assembly brief. Phase 0's fixture must exercise the suppression branches (DS §6). No manifest schema bump, no fixture regeneration (DS decision, locks 4/5).
