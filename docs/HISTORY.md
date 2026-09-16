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
| [#63](../../pull/63) | **PR B** — data minimisation, per-store export and deletion, customer privacy requests, privacy notice and incident response. A redaction reaches every copy: the customer row, the order columns and payload, campaign recipients, each stored analysis input, and the raw sync log |
| [#65](../../pull/65) | The privacy notice's contact address |

### The database boundary, in more detail

Most of this lives in [#61](../../pull/61) and [#63](../../pull/63), but a fair part of it was done by hand
in the Supabase and Render consoles and appears in no pull request at all. That part is recorded here
because it is the part that cannot be recovered by reading the diff.

**Two roles, two connections.** Before this, the application connected to Supabase as the table owner — a
superuser, for whom row-level security does not apply and every grant is moot. Now:

| | Role | Used for |
|---|---|---|
| `DATABASE_URL` | `beaconai_app` — `LOGIN NOSUPERUSER NOBYPASSRLS`, owns nothing | every request the app serves |
| `MIGRATION_DATABASE_URL` | the owner (`postgres`) | schema changes, grants and policies, at boot only |

`api/src/db.js` keeps a pool for each. Development may point both at the same URL; production refuses to
start if they are equal or if the owner connection is missing ([#62](../../pull/62)).

**What the boundary actually is.** Row-level security alone is not one: a table's owner and any role with
`BYPASSRLS` ignore it, and a grant to Supabase's API roles would expose a table through the Data API
whatever the backend checks. So `services/databaseSecurity.js` applies and inspects the whole set together
— `USAGE` and DML on `clean`/`raw` to `beaconai_app` only; explicit `REVOKE ALL` from `anon`,
`authenticated` and `PUBLIC`, including default privileges so new tables inherit nothing; row-level
security on every table with a single policy naming only the application role.

**Done by hand, once, and not in any PR:**

- Created `beaconai_app` in the Supabase SQL editor, password generated there and kept in a password
  manager — never in the repo. Through Supabase's pooler the user name is `beaconai_app.<project-ref>`.
- Set `MIGRATION_DATABASE_URL`, `SESSION_SECRET`, `TOKEN_ENCRYPTION_SECRET` and `BEACONAI_ADMIN_TOKEN` in
  Render *before* merging, then moved `DATABASE_URL` to the new role *after* — the grants that role needs
  are applied by the new code at boot, so switching earlier would have left the live app unable to read
  anything.

**Two things that cost time, worth knowing before the next environment:**

1. Supabase does not grant `CONNECT` on the database to a new role. Without
   `GRANT CONNECT ON DATABASE postgres TO beaconai_app;` the app cannot connect at all.
2. `MIGRATION_DATABASE_URL` must be the *owner* connection. Left unset, the schema step ran as the
   application role and failed with `permission denied for database postgres`. [#62](../../pull/62) makes
   production refuse that configuration rather than fail obscurely.

**Verified on Render, 16 Sep 2026** (`GET /api/ready` with the founder token): runtime role `beaconai_app`,
not a superuser, no `BYPASSRLS`, owns 0 application tables; row-level security and the application policy
on all 28 tables; `anon` and `authenticated` hold no schema usage, no table grants and appear in no policy;
all 3 stored integration tokens decrypt with the current key. Sign-in, sign-out and an unsigned webhook
(401) all behaved. `npm --prefix api run security:db-check` prints the same evidence at any time.

**Still the founder's, in the Supabase and provider consoles:**

- Confirm which schemas the Data API exposes (expected: neither `clean` nor `raw`) and tighten `public`
  default privileges.
- A *tested* restore into a scratch project, and the actual backup retention window recorded — the privacy
  notice refers to it.
- MFA on Render, Supabase, Shopify Partners, Klaviyo, Anthropic and GitHub.
- Shopify app configuration: embedded off, App URL, OAuth callbacks, compliance webhook URLs.

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

## Contracts that used to be separate documents

Four specs were deleted once the code they described could be read directly and the tests enforced them.
They drifted: the Results spec still described the layout that [#64](../../pull/64) replaced. What was
load-bearing is here; the rest is in the PRs.

### Results assessments

The state is typed by the API (`assessWindow` in `api/src/services/measurementService.js`) and rendered by
`ASSESSMENT_CHIP` / `assessmentSentence` in `web/src/App.jsx`. Nothing infers a verdict from numbers.

| State | Shown as | When |
|---|---|---|
| `measuring` | Measuring | the window is still open |
| `insufficient_data` | Insufficient data | **structural** impossibility only: fewer than 2 customers, or zero purchasers, in either group |
| `awaiting_order_data` | Comparison unavailable | the window closed but order data does not reach its end |
| `no_holdout` | Comparison unavailable | nobody was held back |
| `assessment_policy_pending` | Comparison unavailable | a complete window with adequate data, and no configured policy — today, every completed campaign |
| `higher_spending` / `lower_spending` | coloured | the 95% range sits entirely above or below zero |
| `no_clear_difference` | No clear difference | the range includes zero |

No threshold is invented anywhere else: the last three need a configured policy, and `insufficient_data`
never stands in for one.

### Program comparison

Adding campaigns together is not reported, and will not be until a protocol is agreed: enrollment, identity
across campaigns, holdout enforcement, a common start rule and an estimand. `measurementService.js` returns
the reason instead of a figure, and the Results page prints it. A per-campaign result is not evidence about
a programme.

### Provider handoff

`api/src/services/deliveryStateService.js` owns the delivery states; `web/src/deliveryPresentation.js`
decides only what to call them. Two rules survive from the contract: a state advances to `created` **only**
on a provider-confirmed campaign id, never a template or list id; and a provider call that may have acted
but did not answer becomes `uncertain`, never `failed`. BeaconAI never sends.

### Campaign continuity

A campaign belongs to the run that produced it and survives a later analysis: the workspace is keyed by
campaign, not by play ([#53](../../pull/53)); a new draft is created only when the merchant asks for one
([#52](../../pull/52)); and an updated draft is explicit rather than a silent replacement
([#54](../../pull/54)). A handed-off campaign is frozen.

## Where the living documents are

Planning and review documents are not kept: they are in the pull requests that used them. What remains in
`docs/` is referenced by code or shown to merchants.

| Document | Why it stays |
|---|---|
| `SECURITY_HARDENING_PLAN.md` | The security record and the retention policy the privacy notice depends on |
| `PRIVACY_NOTICE.md` | Merchant-facing |
| `INCIDENT_RESPONSE.md` | The one you reach for at 2am |
| `../DEPLOYMENT.md` | How to stand a deployment up, including the two database roles |
| `../README.md`, `../api/README.md`, `../web/README.md` | How to run it |

Everything else is the code and its tests. A spec that disagrees with the code is worse than no spec, and
these did.
