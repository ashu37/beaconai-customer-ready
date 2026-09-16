# Security and data-protection hardening before a real merchant

Status: planned 2026-09-15. Scope: close the items below before importing a real merchant's customer
data. A focused hardening pass, not a rearchitecture.

## What was verified (2026-09-15, read-only)

| Check | Result |
|---|---|
| Session forged with the public dev secret, sent to Render `/api/session` | Rejected: production does not use the dev default |
| Supabase `anon` / `authenticated` USAGE on `clean`, `raw` | None |
| Table grants to `anon` / `authenticated` in `clean`, `raw`, `public` | None; `public` has no tables |
| RLS on `clean.*`, `raw.*` | Off on all 25 tables |
| Role the API uses | `postgres` (table owner, `BYPASSRLS`) |
| Default privileges on `public` | `anon` and `authenticated` get full rights on future tables |
| Supabase exposed schemas (Data API setting) | Not visible from SQL; check in the dashboard |
| OAuth `returnTo` | Stored and redirected to without validation |
| OAuth state | Not bound to the initiating browser |
| Request logs | `morgan("dev")` logs full URLs, including OAuth `code`, `state`, `hmac` |
| Logout / revocation / uninstall | None; sessions are signature-only for 14 days |
| AI payloads (code reading, not yet a captured request) | Store and product names, keywords, aggregate figures, merchant steer text; no customer identifiers |
| `clean.customers.raw` | Full Shopify customer JSON (names, phone, addresses, notes) |
| `clean.klaviyo_assets.payload` | Full audience including recipient emails |
| `clean.orders_date_backup` | 3,938 rows; written only by the one-off timezone migration; no readers, views or foreign keys |
| Production data from the local seed | 24,040 synthetic customers under `seed-demo.myshopify.com` |
| Production DB credentials on the founder laptop | `api/.env` connects to production as `postgres` |

## PR A — access, secrets and database boundary

### A1. Database role and exposure (tested together)

- A runtime role `beaconai_app`: `LOGIN NOSUPERUSER NOBYPASSRLS`, owns nothing. Created once by the founder
  in the Supabase SQL editor (password generated there, never in the repo).
- Schema changes run under the owner connection (`MIGRATION_DATABASE_URL`); requests run under
  `DATABASE_URL` = `beaconai_app`. In development both may be the same URL.
- Applied idempotently at boot by the owner: `USAGE` on `clean`, `raw` and DML on their tables and
  sequences to `beaconai_app` only; explicit `REVOKE ALL` from `anon`, `authenticated`, `PUBLIC`; RLS
  enabled on every `clean`/`raw` table with a single policy `TO beaconai_app`; default privileges so new
  tables follow.
- Boot self-check in production refuses to report ready when the runtime role is a superuser, has
  `BYPASSRLS`, or owns application tables, or when `anon`/`authenticated` hold any privilege on
  `clean`/`raw`.
- `npm run security:db-check` prints the same evidence (roles, grants, policies, RLS, owners) for review.
- Founder: confirm in Supabase → API settings which schemas the Data API exposes (expected: not `clean`
  or `raw`), and tighten `public` default privileges.
- Tests (embedded Postgres, with `anon`/`authenticated` created to mirror Supabase): the runtime role can
  read and write application tables; `anon`/`authenticated` cannot select from any `clean`/`raw` table;
  the self-check fails for a `BYPASSRLS` or owner runtime role.

### A2. Secrets, with a migration that keeps integrations connected

- New `SESSION_SECRET` signs sessions only. `TOKEN_ENCRYPTION_SECRET` encrypts integration tokens only.
- Production refuses to start unless both are set, at least 32 characters, distinct, and not the
  development default. No fallback from one to the other in production.
- Token decryption uses a keyring: the current `TOKEN_ENCRYPTION_SECRET`, then optional
  `TOKEN_ENCRYPTION_SECRET_PREVIOUS`. Encryption always uses the current key. A legacy plaintext value still
  works, so no store disconnects, and is counted in readiness so it can be re-encrypted (none exist in
  production today).
- Readiness reports (counts only, founder view) how many stored tokens decrypt with the current key, the
  previous key, or neither.
- Migration order, before merging: in Render, confirm which of `TOKEN_ENCRYPTION_SECRET` /
  `SESSION_SECRET` is set today. The secret that currently encrypts tokens stays as
  `TOKEN_ENCRYPTION_SECRET` (copy it there if it was only in `SESSION_SECRET`); generate a new, different
  `SESSION_SECRET`. After deploy, readiness must show every token decrypting with the current key.
  Existing browser sessions end once (they are replaced by server-side sessions, A4); integrations stay.
- Tests: tokens encrypted under the old effective secret still decrypt after the split; a previous-key
  token decrypts and re-encrypts under the current key; production config rejects missing, short, equal
  or default secrets.

### A3. OAuth

- `returnTo` accepts only a same-origin path (`/…`, not `//…`) or a URL on the configured web origin;
  anything else is ignored in favour of the default success page.
- State is bound to the browser: the start route sets a short-lived `HttpOnly`, `SameSite=Lax`, `Secure`
  cookie with a random nonce, the state row stores its hash, and the callback requires the matching
  cookie before exchanging the code. The cookie is cleared after use. Applies to Shopify and Klaviyo.
- Tests: foreign `returnTo` is dropped; a callback without the initiating browser's cookie is refused
  before any token exchange; a replayed state is refused.

### A4. Revocation, defined precisely

- Server-side sessions: `clean.sessions` (id, shop, created, expires, revoked_at, reason). The signed
  token carries the session id; every request checks the row.
- Logout revokes that session row and clears the cookie; the same token is refused afterwards.
- Founder disable (`POST /api/admin/stores/:shop/disable`, founder token): records the disable, revokes
  every session for the store, cancels queued or running analysis and sync work, and refuses new work
  for that store from any caller. Enable reverses the block; sessions are not restored.
- Shopify `app/uninstalled` webhook: HMAC verified over the raw body with the app secret (constant-time)
  before anything is read. Revokes every session, disables the store, deletes stored Shopify and Klaviyo
  tokens, stops background work, and records `uninstalled_at`. Deletion of store data follows the
  retention policy (PR B), not the webhook.
- The webhook subscription is registered after each successful install.
- Background work checks the store is active before starting and before persisting each stage.
- Founder token comparison is constant-time everywhere.
- Tests: logged-out and revoked tokens are refused; disable blocks sessions, sync and analysis starts
  and a running job's persistence; an unsigned or wrongly signed webhook changes nothing; a valid
  uninstall removes tokens and refuses the old session.

### A5. Logs

- Request logs redact query values for `code`, `state`, `hmac`, `host`, `timestamp`, `session`, and any
  key containing `token`, `secret`, `password` or `email`; webhook bodies and customer payloads are never
  logged. OAuth error responses return a generic message; details go to the log without credentials.
- Test: the logged line for an OAuth callback contains none of the sensitive values.

### PR A deployment runbook (order matters)

Production refuses to start with a missing, default, short or shared secret, and stays not-ready while
the database boundary check fails. Render keeps the previous deploy live if a new one fails to start.

`DATABASE_URL` moves to the application role LAST, because the grants that role needs are applied by
the new code at boot. Pointing the currently running code at it earlier would leave the live app with a
role that cannot read anything.

1. Supabase: create the application role, password generated locally and kept in a password manager.
   ```sql
   CREATE ROLE beaconai_app WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
   -- then set its password: psql \password beaconai_app, or ALTER ROLE ... WITH PASSWORD '…'
   ```
   Through the Supabase pooler its user name is `beaconai_app.<project-ref>`; keep the host, port and
   database of the existing `DATABASE_URL`. Verify before going further: the role logs in, is not a
   superuser, does not bypass RLS, and cannot yet read `clean` (done 2026-09-15).
2. Render, while the current code is still live (each of these is inert for it, so nothing breaks):
   - Confirm `TOKEN_ENCRYPTION_SECRET` is already set. If it is NOT, stop: today's code falls back to
     `SESSION_SECRET` for token encryption, so adding a new `SESSION_SECRET` would make every stored
     integration token unreadable. Copy the effective value into `TOKEN_ENCRYPTION_SECRET` first.
   - `MIGRATION_DATABASE_URL` = today's `DATABASE_URL` (the owner connection).
   - `SESSION_SECRET` = a new random value, at least 32 characters, different from the token secret.
   - `BEACONAI_ADMIN_TOKEN` at least 32 characters.
3. Merge and deploy. The owner connection applies grants, row-level security and policies. The instance
   serves normally but reports not-ready, because it is still connected as the owner.
4. Now set `DATABASE_URL` to the `beaconai_app` connection string and let it redeploy.
5. Verify with the founder token: `GET /api/ready` returns `security.database.problems: []` and
   `security.tokens` with every stored token under `current`. If any report `undecryptable`, set
   `TOKEN_ENCRYPTION_SECRET_PREVIOUS` to the old value and redeploy before anything else.
6. Everyone signs in again once (old signature-only sessions are refused). Signing in to Shopify
   subscribes that store to `app/uninstalled`.
7. Remove production credentials from the local `api/.env`.

## PR B — data minimisation, deletion and privacy requests

### B1. Minimise what is stored

- Stop storing the full Shopify customer JSON; keep id, email, marketing consent, tags, and the dates the
  engine needs. Migrate existing rows by clearing `raw` for customers.
- Klaviyo assets: remove recipient emails from stored descriptions, metadata, HTML and diagnostic
  payloads (keep counts and ids). Recipient data genuinely needed to build the audience stays where the
  audience is built (`campaign_recipients`). Tests: audience membership, the holdout split and the
  recorded exclusions are unchanged by the change.

### B2. Leftovers

- `orders_date_backup`: confirm the timezone migration is complete (`orders.processed_at` is
  `timestamptz` in production) and nothing references the table, then drop it in a migration. This is
  not a disaster-recovery backup; those are Supabase backups (see founder tasks).
- Remove `seed-demo.myshopify.com` data from production via the seed script's clean mode, and make the
  seed refuse to run against a production database.

### B3. Per-store export and deletion

- One documented function per store that covers primary and derived data: connections and tokens,
  customers and customer identifiers, orders and line items, refunds, products, raw events, sync runs
  and input snapshots, engine runs, audiences and audience snapshots, narration, analysis jobs, campaigns,
  recipients and exclusions, measurements, Klaviyo assets, brand templates, sessions, OAuth states, and
  temporary engine files on disk.
- Export produces the store's data as files for the merchant; deletion is transactional and verified by
  a test that counts zero rows for the store in every table afterwards.
- Retention (to decide and publish): active stores keep data while installed; after uninstall, data is
  deleted within N days unless the merchant asks sooner; database backups expire on the provider's
  schedule (document the actual window once confirmed).

### B4. Individual customer privacy requests (distinct from store deletion)

- `customers/data_request`: produce that customer's stored data for the merchant.
- `customers/redact`: remove or anonymise that customer across customers, orders, audiences, recipients,
  exclusions and assets, without deleting the store's other data. Campaign measurement keeps aggregate
  counts only.
- `shop/redact`: runs the per-store deletion.
- All three verify the webhook HMAC and are recorded with their completion time.

### B5. Documents

- Short privacy notice: what is collected, why, where it goes, retention, deletion and support contact.
- Processor list: Render (hosting), Supabase (database), Anthropic (analysis narration and copy
  suggestions; confirmed payload fields from a captured request), Klaviyo (the merchant's own account;
  receives recipient emails), Shopify (source).
- Incident response one-pager.

## Founder tasks (not code)

1. MFA on Render, Supabase, Shopify Partners, Klaviyo, Anthropic, GitHub; remove shared or unused access.
2. Supabase Data API: confirm exposed schemas; tighten `public` default privileges.
3. Backups: confirm the actual recovery method on the current Supabase plan and test a restore into a
   scratch project. Record the backup retention window. (Longer than the account checks.)
4. Move production credentials out of the local `api/.env`; use a separate development database.
5. Create `beaconai_app` in Supabase and set `DATABASE_URL` / `MIGRATION_DATABASE_URL` in Render (PR A).
6. Secrets migration in Render (PR A, A2).
7. Shopify app configuration, for each app (the acme dev app now, the pilot merchant's app later):
   - Turn off "Embed app in Shopify admin" (or `embedded = false` in the app TOML) and release the
     configuration.
   - App URL points at the deployed BeaconAI site; allowed redirection URLs are exactly
     `…/api/oauth/shopify/callback`.
   - Compliance webhook URLs (PR B) point at `…/api/webhooks/shopify`.
8. Merchant journey test after both: install → authorize → open from Shopify Apps → arrives at the
   correct store → close and reopen. Repeat in a fresh browser session.

## PR A verified on Render (2026-09-16)

| Check | Result |
|---|---|
| Runtime role | `beaconai_app`: not superuser, no BYPASSRLS, owns no tables |
| Boundary self-check | No problems; RLS on all 28 tables, each with the application policy |
| Supabase API roles | `anon`, `authenticated`: no schema usage, no table grants, no policies |
| Stored integration tokens | 3 of 3 open with the current key; none previous, plaintext or undecryptable |
| Reads under the new role | Campaigns, sync status, latest run and results all load |
| Sign-in | Old signature-only sessions refused; Shopify sign-in issues a new server-side session |
| Sign out | Session revoked server-side; the app returns to signed-out |
| Unsigned webhook | 401 |

Deployment notes: `beaconai_app` needed `GRANT CONNECT ON DATABASE postgres` (Supabase does not grant it
by default), and `MIGRATION_DATABASE_URL` must hold the OWNER connection — unset, the schema step ran as
the application role and failed with "permission denied for database postgres" (fixed in #62: production
refuses that configuration and startup errors name the connection).

Still to do from the founder list: MFA everywhere, Supabase Data API exposed-schemas check, a tested
restore, Shopify app configuration (embedded off, App URL, callbacks), and removing production
credentials from the local `api/.env`.
