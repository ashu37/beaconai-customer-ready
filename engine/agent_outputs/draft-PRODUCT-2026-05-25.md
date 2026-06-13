# BeaconAI — Product

*Stable doc. Monthly review at most. Survives engine pivots.*
*Last updated: 2026-05-25.*

---

## 1. What BeaconAI is

BeaconAI is a Shopify app for DTC merchants in **beauty, supplements, and mixed** verticals. Once a month it reads the merchant's store data, runs a local decision engine, and produces a typed slate of marketing **action cards** the merchant reviews and approves. Approved cards become Klaviyo campaigns.

The product is not a dashboard. It does not summarize "metrics that moved." It makes monthly **decisions** — and refuses to make a decision when the evidence is weak.

Today the engine runs locally against a Shopify CSV export and emits JSON the founder inspects via a debug HTML page. Future-state is a hosted app where merchants connect Shopify + Klaviyo and the same engine runs on their tenant.

---

## 2. The merchant journey

| Step | Today (local scaffolding) | Future (hosted Shopify app) |
|---|---|---|
| Onboard | Founder runs CLI on merchant CSV | Merchant installs Shopify app, OAuths Klaviyo |
| Ingest | Shopify orders CSV + optional inventory CSV (see `STORE_DATA_REQUIREMENTS.md`) | Shopify + Klaviyo connectors; same shape |
| Run | Monthly `python -m src.main` | Monthly scheduled job per tenant |
| Review | Founder reads `engine_run.json` + `briefing.html` | Merchant reviews Play Thesis cards in app UI |
| Approve | Manual | One-touch approve per card |
| Publish | Manual Klaviyo build by founder/merchant | Engine bundles Klaviyo campaign (audience CSV + flow + send time); pushes via Klaviyo on approval |
| Observe | Manual JSON import of `campaign_sent` / `outcome_observed` (D-5) | Same import-driven loop until Phase 9 (post-beta) |
| Recalibrate | Priors refit monthly | Same; ML predictive layer refits on 30 more days of data |

The CSV→HTML workflow is **scaffolding**, not the product. It is preserved while the engine matures and is the artifact a real frontend will eventually render.

---

## 3. What the merchant sees — the Play Thesis card surface

The monthly slate has **four lanes**:

| Lane | What it means | Cap |
|---|---|---|
| **Recommended Now** | "Send this. The evidence is on your store." | 3 |
| **Recommended Experiment** | "Try this. Industry pattern + your audience fits. We'll measure after." | 2 |
| **Considered** | "We looked at this and held it. Here is the typed reason." | unbounded |
| **Watching** | "Not ready, but tracking the signal that would trigger it." | 4 |

If nothing clears the gates, the engine **ABSTAINS** with a typed reason. Abstaining is a feature.

Each card is a **Play Thesis** with typed fields:

- **Evidence chip** — A (Causal) / B (Directional) / C (Prior) / D (Observational).
- **Mechanism** — "What we'd send" (intervention-only string; measurement instructions stripped).
- **Audience** — typed definition + size (e.g., "lapsed 60–120d, n=1,842").
- **Revenue range** — defensible posterior when the prior is validated; suppressed otherwise.
- **State-of-store context** — typed `{current, prior, delta_pct}` per metric, with anomaly flags.
- **Held reason** (Considered only) — enum + detail struct (e.g., `EVIDENCE_BELOW_THRESHOLD`, `AUDIENCE_BELOW_FLOOR`).

The **product contract is `engine_run.json`.** The frontend app (unbuilt) reads this and renders the cards. `briefing.html` is a debug renderer that retires when the frontend ships.

---

## 4. The Stop-Coding Line — engine emits typed, swarm narrates

A founder-locked split, reconciled 2026-05-06:

- The **engine** owns: typed fields, math, audience definitions, evidence tiers, gates, play-id and display-name uniqueness, revenue posteriors, anomaly flags.
- The **downstream agent swarm** owns: framing, phrasing, narrative tone, dollar contextualization, percent framing, card layout, copy.

The engine is forbidden from writing merchant prose. The swarm is forbidden from inventing numbers the engine didn't emit. Source: `agent_outputs/phase6b-stop-coding-line-reconciled.md`.

---

## 5. Beta posture — month-1-wow, month-2-return

Beta success is **not** a 6-month outcome-calibration loop. It is two things:

1. **Month-1 wow** — the first slate the merchant sees is dense, defensible, grounded in their data, and includes at least one card they would actually run.
2. **Month-2 return** — when the merchant comes back 30 days later, the slate has visibly evolved. That evolution comes from the **ML predictive layer refit** on 30 more days of data, not from realized outcomes.

The ML predictive layer (Sprints 10–13) gives audience-level intelligence (per-customer LTV, P(alive), reorder-gap survival, co-purchase, RFM). **ML does not add plays.** It ranks customers within each play's audience and gates itself via `ModelFitStatus` (VALIDATED / PROVISIONAL / REFUSED).

**Phase 9 outcome loop is deferred post-beta.** The "did the campaign work" calibration matters in month 3+, not for the wow-then-return arc.

**Causal uplift modeling** waits for accumulated Phase 9 outcomes. Post-PMF.

---

## 6. Founder decisions that bound the space

Canonical source: `memory.md` L173-182. Text below is verbatim.

- **D-1** — `audience_definition_version` policy. Any change to SQL/Python audience-definition logic MUST increment `audience_definition_version` by 1. Old lineages remain readable but fork to a new `lineage_id`. Required arg in `compute_lineage_id`.
- **D-2** — Retention forever. No TTLs, auto-deletion, archival tiers. SQLite grows monotonically.
- **D-3** — Merchant deletion = full wipe only. Per-store `data/<store_id>/memory.db` is the deletion unit. No row-level deletion APIs, soft-delete flags, or partial redaction.
- **D-4** — Full per-store JSON export from Day 1 (`tools/export_store.py`). Round-trip test required.
- **D-5** — Manual JSON import ONLY for v1. NO Klaviyo API pollers, OAuth flows, or webhook receivers in Beacon-track scope.
- **D-6** — ML models EXPLICITLY BANNED for the planning horizon: quiz contextual bandits (LinUCB/Thompson), VIP/loyalty tier optimization, new product launch targeting, bundle combinatorial optimization, stockout prediction, cause/limited-edition→core conversion. NO empty modules, placeholder classes, prior entries, or `play_id` registrations for these. Re-additions require explicit founder approval + new addendum.
- **D-7** — I-1 affinity audience-builder spec deferred to Sprint 3 spike memo.
- **D-8** — Vertical scope hard-locked at `{beauty, supplements, mixed}`. `mixed` = literal beauty+supplements blend, NOT a fallback for unknown verticals. Apparel, food/bev, home goods, wellness are out of scope PERMANENTLY — refused at engine entry, never absorbed by `mixed`. Cross-merchant pooling (if/when it lands Year 2) within {beauty, supplements} only.

---

## 7. Today vs. future

| Surface | Today | Future |
|---|---|---|
| Hosting | Local CLI on founder's machine | AWS-hosted Shopify app, per-tenant |
| Data ingress | Shopify orders CSV + optional inventory CSV | Shopify connector + Klaviyo connector |
| Storage | `data/<store_id>/` (SQLite memory.db + immutable run snapshots) | S3 (immutable snapshots) + managed Postgres/Aurora (event log) |
| Run trigger | Manual `python -m src.main` | Scheduled monthly per tenant |
| Output | `engine_run.json` + `briefing.html` (debug) | `engine_run.json` rendered by frontend Play Thesis cards |
| Approval | Manual founder review | One-touch merchant approve in app |
| Publish | Manual Klaviyo build | Engine bundles Klaviyo campaign (audience CSV + flow + send time) and publishes via Klaviyo |
| Outcome ingest | Manual JSON import (`campaign_sent`, `outcome_observed`) | Same import-driven loop through beta; Phase 9 outcome loop post-beta |
| ML refit | Once month-2 of beta lands | Same; refit monthly on 30 more days of data |

The substrate API (`open_memory`, `append_event`, `write_immutable_snapshot`) is already abstracted; storage backend swaps without engine changes. **No disk-growth optimization, no TTLs, no local-disk cleanup logic today** — D-2 holds; AWS migration is the right time to revisit.

---

## 8. What we are NOT building

- **Other verticals.** Apparel, food/bev, home goods, generic wellness — refused at engine entry. D-8.
- **ML for banned use-cases.** Contextual bandits, VIP optimization, new-product-launch targeting, bundle combinatorial, stockout prediction, cause→core conversion. D-6.
- **Causal uplift in beta.** Needs accumulated Phase 9 outcomes. Post-PMF.
- **A dashboard.** No "metrics that moved" view; the engine makes decisions, not summaries.
- **A live Klaviyo integration in v1.** Manual import only until AWS migration. D-5.
- **A frontend app, today.** `briefing.html` is the debug renderer. The merchant-facing UI is unbuilt; the engine ships typed JSON ready for it.
- **Cross-merchant pooling outside the locked verticals.** If/when it lands Year 2, beauty + supplements only.

---

## Sources

- `ENGINE_OVERVIEW.md` §1 (L9–16), §3 (L37–48), §6 (L88–117), §10 (L193–204) — product framing of engine purpose, slate lanes, ML layer, beta criterion
- `ARCHITECTURE_PLAN.md` Executive Summary L75–87 "What This Plan Delivers"; L70–84 S7.6 close beta-readiness statement
- `memory.md` L169–182 — Founder Decisions D-1..D-8 + 2026-05-10 storage backend note
- `memory.md` beta success criterion entries (S6-S7 closeouts)
- `agent_outputs/phase6b-stop-coding-line-reconciled.md` L1–62 — Stop-Coding Line; engine emits typed / swarm narrates
- `STORE_DATA_REQUIREMENTS.md` L1–60 — merchant onboarding data spec
- `KNOWN_ISSUES.md` KI-7 (L68–73) — Klaviyo `provider` enum coordination posture
- `src/engine_run.py` PlayCard schema — Play Thesis card typed fields (referenced, not copied)
- `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` — current execution roadmap context for beta posture
