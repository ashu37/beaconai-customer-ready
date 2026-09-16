# What was built, and when

One line per piece of work, tagged with the pull request that carries it. The PR
is the detail: `gh pr view <n>` has the reasoning, the review findings and the
tests. This file exists so nobody has to reconstruct the order from 64 commits.

Dates are merge dates.

## Engine and merchant UX (Jul 2026)

| PRs | What |
|---|---|
| [#1](../../pull/1), [#2](../../pull/2) | Order date taken from `processed_at` with a `created_at` fallback; valid JSON for non-finite floats |
| [#3](../../pull/3)–[#9](../../pull/9) | Merchant-facing UX overhaul: onboarding, email preview, campaign workspace, approve-for-send, briefing persistence |
| [#10](../../pull/10), [#11](../../pull/11) | Layout polish and the full design uplift |

## Narration (Aug 2026)

| PRs | What |
|---|---|
| [#12](../../pull/12)–[#16](../../pull/16) | Merchant prose is LLM-authored or chips, never templated; narration persisted per run |
| [#17](../../pull/17) | Audiences resolve email-as-id customer ids — the root cause of zero matched emails |
| [#18](../../pull/18), [#19](../../pull/19) | Briefing loading states: a refresh no longer reads as an empty store |

## Durable state (8–9 Sep 2026)

| PRs | What |
|---|---|
| [#20](../../pull/20)–[#25](../../pull/25) | Engine runs persisted to Postgres; `/health` made liveness-only so a database outage cannot block deploys; a blocked TCP path isolated and the probes removed |
| [#26](../../pull/26) | An empty store counts as unsynced, so a first run actually syncs |
| [#27](../../pull/27), [#28](../../pull/28) | Campaign tables and routes; campaign state moved out of localStorage |
| [#29](../../pull/29), [#30](../../pull/30) | A stable 10% holdout recorded at send, and measurement against it |
| [#31](../../pull/31)–[#33](../../pull/33) | Results page; the seed script, and the degenerate-arm guard it exposed |

## Tickets A–G: truthfulness (9–11 Sep 2026)

| PRs | What |
|---|---|
| [#34](../../pull/34) | A: sync input that can be vouched for |
| [#35](../../pull/35), [#36](../../pull/36) | B: durable campaign revision |
| [#37](../../pull/37), [#38](../../pull/38) | C: one approved branded email shell; the provider handoff contract |
| [#39](../../pull/39) | D: the access boundary completed; audience and review screens |
| [#40](../../pull/40) | E: truthful evidence and held reasons |
| [#41](../../pull/41) | F: the measurement protocol (gate left open) |
| [#42](../../pull/42) | G: Results, minimal and truthful |

## Provider integration (11–14 Sep 2026)

| PRs | What |
|---|---|
| [#43](../../pull/43) | Sync progress that survives a reload |
| [#44](../../pull/44) | BeaconAI refuses to send directly; Klaviyo sends |
| [#45](../../pull/45)–[#47](../../pull/47) | Klaviyo drafts against the real API; PKCE on the OAuth connection; OAuth tokens as `Bearer`, private keys as `Klaviyo-API-Key` |
| [#48](../../pull/48), [#49](../../pull/49) | Approvals that stick; analyses in the background, one per store, under deadlines |
| [#50](../../pull/50), [#51](../../pull/51) | Database details kept out of public health checks; transient failures survived |
| [#52](../../pull/52)–[#54](../../pull/54) | Campaign continuity across analyses: the workspace keyed by campaign, not play |
| [#55](../../pull/55) | Stores asked to reconnect for full order history before syncing |

## Merchant trust (15 Sep 2026)

| PRs | What |
|---|---|
| [#56](../../pull/56) | Email copy and narration cannot outrun their evidence |
| [#57](../../pull/57) | Each store's workspace isolated; loading never shown as empty |
| [#58](../../pull/58) | Saves queued per campaign; handed-off campaigns locked |
| [#59](../../pull/59) | Plain labels and merchant vocabulary. Audience day windows are counted from the newest order in the analysed data, not the analysis date |
| [#60](../../pull/60) | **Finish in Klaviyo** as an explicit handoff mode: a draft with no template, for the merchant's own design |

## Security and data protection (15–16 Sep 2026)

| PRs | What |
|---|---|
| [#61](../../pull/61) | **PR A** — least-privilege database role, row-level security on every table, split secrets with no production fallback, OAuth browser binding, precise revocation, log redaction |
| [#62](../../pull/62) | Production refuses to start without the owner connection; startup errors name which connection failed |
| [#63](../../pull/63) | **PR B** — data minimisation, per-store export and deletion, customer privacy requests, privacy notice and incident response |
| [#65](../../pull/65) | The privacy notice's contact address |

## Results readability (16 Sep 2026)

| PRs | What |
|---|---|
| [#64](../../pull/64) | The expanded result leads with progress and the figures; provenance moved behind a disclosure |

## Still open

- **The campaign assessment policy is unset** (`campaignAssessmentPolicy` in `api/src/config.js`), so every
  completed campaign reports "Comparison unavailable". Three values — minimum customers per arm, minimum
  purchasers per arm, and the critical value — need a statistical review before they are set. Until then no
  campaign can resolve to a verdict, and no amount of UI work changes that.
- **Uninstall does not schedule the 30-day deletion** the privacy notice promises; it ends access, and the
  deletion is run by hand with `npm --prefix api run store:delete`.
- **Broad data minimisation is deferred.** `clean.orders.raw`, `sync_runs.input_snapshot` and
  `raw.shopify_events` still hold full Shopify payloads for customers who have not asked to be redacted.
  A redaction reaches all three; ordinary storage does not yet minimise them. `raw.shopify_events` has no
  reader at all and is the obvious next one to remove.
- **One `SHOPIFY_CLIENT_SECRET` per deployment**, so a compromise of it affects every install. Per-merchant
  custom apps would narrow this; not yet decided.

## Where the living documents are

Planning and review documents are not kept: they are in the pull requests that used them. What remains in
`docs/` is referenced by code or shown to merchants.

| Document | Why it stays |
|---|---|
| `MEASUREMENT_PROTOCOL.md` | Cited by `measurementService.js` for what a program comparison would require |
| `PROVIDER_HANDOFF_CONTRACT.md` | The handoff modes and their safeguards |
| `CAMPAIGN_CONTINUITY_SPEC.md` | How a campaign survives a new analysis |
| `SECURITY_HARDENING_PLAN.md` | The security record and the retention policy the privacy notice depends on |
| `PRIVACY_NOTICE.md`, `INCIDENT_RESPONSE.md` | Merchant-facing, and the one you reach for at 2am |
| `../RESULTS_UI_SPEC.md` | Cited by `App.jsx` and the Results tests |
