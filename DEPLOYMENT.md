# BeaconAI Customer Trial Deployment

This is the fastest path to a shareable MVP URL for friendly customer trials.

## Recommended MVP Stack

- App + API + Python engine: Render web service from the root `Dockerfile`
- Database: Supabase free Postgres for trial deployments
- Shopify/Klaviyo OAuth: app-level credentials owned by BeaconAI

## 1. Push The Repo

The deployment services should connect to the GitHub repo:

```bash
git submodule update --init --recursive
git status
```

Make sure the `engine/` submodule is available to the deploy provider.

## 2. Create Supabase Trial Database

Create a Supabase project on the Free plan, then copy its Postgres connection string.
Use the pooled connection string if Supabase offers both direct and pooled options.

Render will use this value as:

```env
DATABASE_URL=<Supabase Postgres connection string>
```

Supabase free is enough for a friendly pilot, but it has smaller compute/storage limits than paid production Postgres.

## 3. Deploy On Render

Create a Render Blueprint from `render.yaml`. This creates:

- `beaconai-app`: one Docker web service that serves the React app and `/api/*`

Manual settings:

```txt
Runtime: Docker
Dockerfile path: ./Dockerfile
Health check path: /api/health
```

Set these API environment variables:

```env
DATABASE_URL=<Supabase Postgres connection string>
PORT=4000
API_BASE_URL=https://YOUR-RENDER-APP.onrender.com/api
WEB_BASE_URL=https://YOUR-RENDER-APP.onrender.com
TOKEN_ENCRYPTION_SECRET=<long random generated secret>

SHOPIFY_CLIENT_ID=<BeaconAI Shopify app client id>
SHOPIFY_CLIENT_SECRET=<BeaconAI Shopify app client secret>
SHOPIFY_SCOPES=read_products,read_customers,read_orders

KLAVIYO_CLIENT_ID=<BeaconAI Klaviyo app client id>
KLAVIYO_CLIENT_SECRET=<BeaconAI Klaviyo app client secret>
KLAVIYO_SCOPES=accounts:read campaigns:read campaigns:write catalogs:read flows:read lists:read lists:write profiles:read profiles:write segments:read templates:read templates:write
KLAVIYO_REVISION=2026-04-15
```

Optional dev-only fallback credentials:

```env
SHOPIFY_SHOP_DOMAIN=testing-dev-utkexvrj.myshopify.com
SHOPIFY_ACCESS_TOKEN=<test store admin token>
KLAVIYO_PRIVATE_KEY=<test Klaviyo private key>
```

After deploy, verify:

```txt
https://YOUR-RENDER-APP.onrender.com/api/health
```

If Render cannot assign `https://beaconai-app.onrender.com` because the name is taken, update `API_BASE_URL` and `WEB_BASE_URL` to the actual Render service URL before testing OAuth.

## 4. Configure Shopify App

In the BeaconAI Shopify app settings, add:

```txt
https://YOUR-RENDER-APP.onrender.com/api/oauth/shopify/callback
```

Scopes:

```txt
read_products,read_customers,read_orders
```

Use `write_orders` only for development seeding, not for normal customer trials.

Copy the app client ID and client secret into Render.

## 5. Configure Klaviyo App

In the BeaconAI Klaviyo app settings, add:

```txt
https://YOUR-RENDER-APP.onrender.com/api/oauth/klaviyo/callback
```

Copy the app client ID and client secret into Render.

## 6. Trial Smoke Test

Open the Render app URL and run:

1. Onboarding -> Connect Shopify
2. Onboarding -> Connect Klaviyo
3. Home -> Sync Shopify
4. Briefing -> Refresh briefing
5. Review Queue -> Refresh templates
6. Select/edit template
7. Campaigns -> approve package

Connection status should show:

```txt
Shopify source: oauth
Klaviyo source: oauth
```

## Current Caveat

Real customer stores may not produce recommendations until they have enough order history for Atul's engine gates. Sparse stores should still complete onboarding, sync, and show held/considered plays where applicable.
