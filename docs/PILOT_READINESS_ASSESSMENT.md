# One-merchant pilot readiness assessment

Assessment date: September 10, 2026. Scope: current local checkout, deployment configuration, existing tests, and current official provider documentation. Render/Supabase dashboards, deployed commit, real OAuth installs, production database permissions, live inbox delivery, and engine resource usage were not inspected. No application code or deployment was changed.

**Decision: do not share this as an unattended, live-data campaign pilot yet.** Free hosting is viable for a supervised pilot if the fixes and checks below pass. Buying a plan does not fix the integration bugs.

## Verified locally

- API suite against disposable real Postgres: **193 passed, zero skipped**.
- Web suite: **88 passed**, lint passed. Production frontend build passed.
- Root `npm test` alone skips 143 database-dependent tests; use `npm run test:api:db` as well.
- A no-network call to the actual Klaviyo package helper, supplying approved HTML, reproducibly throws `createCampaignSendPackage requires rendered html`. It reports stage `template` and `provenNothingCreated: false` despite making no provider request.
- `npm audit --omit=dev`: **7 affected dependency entries, 3 high and 4 moderate**, fixes available. Entries: axios, body-parser, express, morgan, nanoid, postcss, qs. This is dependency-level evidence, not proof of exploitable application paths; frontend build dependencies are included in this workspace's production dependency classification. Docker installs from separate API/web lockfiles, so audit the actual image too.

## Must fix or verify before the real-data pilot

1. **Fix broken Klaviyo draft creation.** `api/src/services/klaviyoClient.js:287` drops the `options` argument and calls `createTemplate` without the required HTML. Pass the reviewed bytes through, validate before marking an external request started, and test the actual client against a fake HTTP provider. Existing route tests replace the provider helper, so they miss this. Current failure can leave a campaign reserved/uncertain even though no draft was created. Check for existing stuck rows and reconcile deliberately.

2. **Fix Shopify history permissions.** `render.yaml` requests `read_products,read_customers,read_orders`; `syncService.js:51` requires at least 90 days of history. Shopify normally exposes only 60 days without `read_all_orders`. Obtain the appropriate access, update the provider app and deployment scopes, reauthorize, and verify actual fetched coverage. Select a merchant with at least 90 days of orders, preferably 180. Also verify access to customer email fields on the real store. Do not treat a successful connection or a development-store sync as evidence of production data access. [Shopify access scopes](https://shopify.dev/docs/api/usage/access-scopes), [protected customer data](https://shopify.dev/docs/apps/launch/protected-customer-data).

3. **Implement Klaviyo PKCE.** `oauthService.js:170` constructs authorization without a challenge; the token exchange omits the verifier. Klaviyo requires PKCE for both public and confidential clients. Store a fresh verifier with each expiring OAuth state; send its challenge and exchange with the corresponding verifier. Test a fresh install and token refresh. [Official OAuth flow](https://developers.klaviyo.com/en/docs/set_up_oauth).

4. **Close the direct-send bypass for this pilot.** `routes.js:1229` accepts a provider campaign ID and invokes send without looking up the local campaign's approval, frozen content, import completion, or delivery state. Store authentication is present, but the campaign workflow checks are absent. The minimum is to disable this endpoint server-side and have the merchant approve/send in Klaviyo. The current draft-oriented UI is not protection for a callable endpoint. If retaining in-app sending later, enforce ownership, approval revision, provider readiness, and a durable send-attempt/reconciliation protocol on the server.

5. **Make secrets mandatory and access revocable.** `config.js:33` falls back to a public development secret. In production, refuse startup without a strong secret; verify Render has a stable generated value. Set a separate strong `BEACONAI_ADMIN_TOKEN` for founder operations, never in the frontend. Sessions are signed for 14 days and have no per-session revocation/logout endpoint. Add logout and a shop-level revocation/disable mechanism for the pilot. Do not casually rotate the encryption secret: it also decrypts stored provider tokens, so rotation requires migration or reconnecting integrations.

6. **Harden OAuth redirects and browser binding.** `returnTo` is stored and later passed to `res.redirect` without an origin restriction. Permit only the configured app origin or safe relative paths. Random single-use state is already present, but it is not bound to the initiating browser; add that binding to prevent login/connection flow swapping.

7. **Patch dependencies and verify database exposure.** Apply compatible security updates, use deterministic installs, and repeat the tests and image audit. The database tables live in `raw` and `clean`, and the API uses `pg`, not Supabase Auth. No RLS or grant hardening is defined in the schema. This alone does not prove public exposure: inspect Supabase's exposed schemas and role grants. For this server-only design, disable the unused Data API or keep both schemas unexposed and unavailable to anonymous/authenticated API roles. A database owner can bypass RLS, so RLS alone would not replace the app's shop authorization. [Supabase production checklist](https://supabase.com/docs/guides/deployment/going-into-prod).

8. **Verify database TLS.** `db.js` explicitly disables certificate verification for matching Supabase URLs and only detects `.supabase.com`, whereas direct DB hosts can use `.supabase.co`. Configure TLS explicitly for the actual connection URL, with certificate validation. Keep `PGSSLMODE=disable` out of production. Supabase's session pooler is a suitable IPv4 connection option for this persistent Node server; verify it against the deployment. [Connection guidance](https://supabase.com/docs/guides/database/connecting-to-postgres).

## Connections and merchant setup

- Keep React and `/api` on the same HTTPS Render origin. Set `WEB_BASE_URL` to that origin and `API_BASE_URL` to that origin plus `/api`. Ensure the built frontend does not target localhost. `VITE_*` settings are public build-time values, never secrets.
- Register exact `/api/oauth/shopify/callback` and `/api/oauth/klaviyo/callback` URLs in the provider apps.
- Confirm Shopify distribution allows installation on the pilot's actual store. Custom distribution supports one store, but Shopify says distribution choice cannot be changed afterward; consider a separate pilot app if the main app is intended for public distribution. [Distribution options](https://shopify.dev/docs/apps/launch/distribution/select-distribution-method).
- Replace Shopify API version `2023-10` with a supported, tested version. Shopify falls forward from unsupported versions, so current success would not prove the code is using the API it requests. [Versioning](https://shopify.dev/docs/api/admin-rest/usage/versioning).
- Remove development Shopify tokens/Klaviyo private keys from Render unless deliberately using a scoped, reviewed setup. Confirm connection source is OAuth and the merchant/account is correct.
- Configure and approve the merchant's branded email shell using the founder endpoint. Without it, preview/handoff intentionally fails. Verify logo, sender/reply-to, footer, unsubscribe, CTA URL, subject, and mobile inbox rendering with the merchant.
- Profile import uses an asynchronous bulk-import job, but package creation does not wait for job completion or inspect its failures. Before sending, verify import finished, intended recipients are present, consent/suppression rules are respected, and holdout customers are excluded. The code filters for email existence; it does not establish marketing consent. Do not infer consent from Shopify purchase history.
- Verify list membership does not trigger unintended existing Klaviyo flows. Check smart sending and existing campaigns/flows when interpreting treated/holdout results.
- The app also uses Anthropic for copy/narration. Check `ANTHROPIC_API_KEY`, available credit, and spend limits if AI output is part of the pilot. Without a key, copy uses static fallback and narration supports mock mode. These settings are absent from `render.yaml`; Render/Supabase free plans do not provide AI API credit.

## Free-tier operating limits

| Service | Pilot consequence | Bare minimum |
|---|---|---|
| Render Free | Sleeps after 15 minutes idle; wake-up is about a minute. Files vanish on restarts/redeploys/spin-down. | Open and exercise the app before a scheduled session; tell the merchant about cold starts. Verify persisted state survives an actual restart. |
| Render engine workload | This app runs Python data science alongside Node, with uncapped full-store fetches and no subprocess deadline. One merchant may still have a large store. | Run the real store's full sync and analysis on the deployed instance; inspect peak memory, duration, and restarts. Serialize engine runs, add deadlines and safe retry messages. Upgrade compute if it cannot complete reliably. |
| Supabase Free | 500 MB database limit; low-activity projects may pause after seven days. Raw payloads, snapshots, audiences, and campaign copies can grow with each run. | Check size after a full import and repeated syncs; define safe retention for obsolete raw snapshots without deleting campaign evidence. Check project state before a session. |
| Supabase backups | Free-tier users should make their own exports. | Take an encrypted off-site backup before the pilot and deployments, then daily while active. Test restoration into a separate database. Include `raw` and `clean`. |
| Klaviyo, if also Free | Up to 250 active profiles and 500 email sends/month. Importing an audience can affect account limits. | Check the merchant account's existing profiles, send allowance, and actual audience before importing/sending. |

Sources: [Render Free](https://render.com/docs/free), [Supabase database size](https://supabase.com/docs/guides/platform/database-size), [project pausing](https://supabase.com/docs/guides/platform/free-project-pausing), [backups](https://supabase.com/docs/guides/platform/backups), [Klaviyo free-plan limits](https://help.klaviyo.com/hc/en-us/articles/360050759151).

Free hosting can be adequate for scheduled feedback with manual support. For someone opening the link at unpredictable times, always-on Render is the first hosting improvement to consider; choose memory from measured engine usage. A paid instance's local filesystem is still ephemeral unless separately persisted. A custom domain, enterprise auth, billing, Redis, and a separate job platform are not required for one supervised merchant.

## Results require founder operations today

`POST /api/campaigns/:id/reconcile` is founder-only. It reads Klaviyo and records provider-confirmed send status/time. Results are computed from Shopify data and require that confirmed send evidence. Viewing Results recalculates existing data; it does not fetch new Shopify orders or automatically reconcile Klaviyo.

For one pilot, manually reconcile after sending and when scheduled sends complete, then re-sync Shopify before results reviews. Document this sequence and retain campaign IDs. Without it, the user can see “not sent” or stale/no results despite real activity. Keep assessment policy unset until its statistical thresholds are justified; show descriptive outcomes and sample size, not unsupported causal claims. For immediate UI feedback, use clearly labelled sample results separately from real campaigns.

## Reliability and security housekeeping

- `/api/ready` reports startup state, not a current database query. It can remain green after a later outage, or red after recovery from startup failure. Add a bounded live DB probe, startup recovery, and a Postgres pool error handler. Strip DB target/error details from public health responses.
- OAuth token calls have no explicit Axios timeout; provider clients have 30-second request timeouts but no general 429 backoff. Add bounded timeout/retry for safe reads and token operations. Never blindly retry an uncertain campaign creation/send.
- Add pilot shop allowlisting and modest request limits, particularly public OAuth and expensive engine/copy routes. Restrict fixture runs in production. A secret URL is not access control.
- Morgan's URL logging includes OAuth query strings. Redact authorization codes/state and keep provider errors/engine stdout from leaking into normal user responses. Preserve enough sanitized logs to diagnose failures.
- Startup runs schema changes. Back up before deployment, verify migration completion, and rehearse restart against representative data. An application rollback is not a database rollback.
- Docker has no `.dockerignore` and copies entire API/web/engine directories. A Git-based Render checkout should omit ignored `.env` files, but local builds can bake them in and can overwrite Linux dependencies with local ones. Exclude secrets, local dependency directories, virtual environments, and generated customer data; verify the engine submodule is fetched at the intended commit.
- Give the merchant a brief pilot note describing stored data, providers used, whether actual campaigns will be sent, how to disconnect/delete data, and a direct support contact. Verify applicable provider privacy/deletion requirements for the app's distribution before launch. Have a tested manual per-shop deletion/revocation procedure.
- Enable MFA for hosting/provider operator accounts. Keep a known working release and a written procedure to stop new sends, inspect Klaviyo, and restore data if needed.

## Acceptance checks before sharing

1. Deploy the intended commit and engine submodule; verify HTTPS, browser API origin, database connectivity, and migrations.
2. In a fresh browser, sign in as the pilot merchant, connect both providers, and verify wrong-shop/unauthenticated reads and mutations fail.
3. Fully sync the actual store; verify order counts, customer email access, currency/timezone, and at least 90 days of coverage. Run analysis within the instance's memory/time budget.
4. Review/edit/approve a campaign. Reload and use a second signed-in browser; confirm saved content and status return. Restart Render and repeat.
5. Create exactly one Klaviyo draft. Compare subject, HTML, links, sender, and treated/holdout membership with what was approved. Confirm import completion and test the email to authorized inboxes before any customer send.
6. Exercise double-click, stale approval, disconnect, provider timeout, and reconnect paths in a test account. An uncertain operation must not invite a duplicate creation/send.
7. For the live-results phase, have the merchant send from Klaviyo, reconcile delivery, sync new Shopify data, and verify Results shows true send time, freshness, sample sizes, and the frozen original email. Do not fabricate production orders for testing.
8. Complete and restore a backup in isolation; check logs and rehearse founder support/reconciliation.
9. Send only the app link (optionally with `?shop=the-pilot-store.myshopify.com`), the task list, cold-start expectation, and support contact. The shop parameter selects a store; it is not authorization. Never send founder tokens or database/provider keys.

Suggested feedback tasks: connect the store; explain what the first recommendation means; edit and approve a campaign; find it again after refresh; interpret Results. Ask where the user hesitated and what evidence they needed before approving. Actual campaign outcome feedback takes time; a single UI session can use labelled sample results.

The older root `PROD_READINESS.md` is stale regarding briefing/campaign persistence: current code stores engine snapshots/audiences/narration and campaign state in Postgres. Verify deployed restart behavior, but do not rebuild those features based only on that old document.
