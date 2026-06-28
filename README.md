# BeaconAI Customer Trial App

Clean customer-facing BeaconAI MVP package.

This repo is for hosted customer trials. It does not include local seed endpoints, synthetic order generation, or demo-only UI controls.

## Structure

```txt
api/       Node/Express API, OAuth, Shopify/Klaviyo sync, engine runner
web/       Vite React customer dashboard
engine/    Atul BeaconAI Python engine source
Dockerfile Render-compatible app + API + Python engine image
render.yaml Render app blueprint; expects Supabase DATABASE_URL
DEPLOYMENT.md hosted customer-trial checklist
```

## Customer Trial Flow

1. Customer opens the hosted BeaconAI frontend.
2. Customer connects Shopify through OAuth.
3. Customer connects Klaviyo through OAuth.
4. BeaconAI syncs Shopify data into Supabase Postgres.
5. Atul's engine runs on synced store data.
6. Customer reviews recommendations, chooses/edits a Klaviyo template, and approves a campaign package.

## Local Run

Install dependencies:

```bash
npm run install:all
```

Create env files:

```bash
cp api/.env.example api/.env
cp web/.env.example web/.env
```

Start Postgres:

```bash
cd api
docker compose up -d
npm run db:init
PORT=4010 npm run dev
```

Start the frontend:

```bash
cd web
npm run dev -- --port 5177
```

Open:

```txt
http://127.0.0.1:5177/?shop=your-store.myshopify.com
```

## Required OAuth Env

```env
API_BASE_URL=http://127.0.0.1:4010/api
WEB_BASE_URL=http://127.0.0.1:5177
TOKEN_ENCRYPTION_SECRET=replace_with_a_long_random_secret

SHOPIFY_CLIENT_ID=...
SHOPIFY_CLIENT_SECRET=...
SHOPIFY_SCOPES=read_products,read_customers,read_orders

KLAVIYO_CLIENT_ID=...
KLAVIYO_CLIENT_SECRET=...
KLAVIYO_SCOPES=accounts:read campaigns:read campaigns:write catalogs:read flows:read lists:read lists:write profiles:read profiles:write segments:read templates:read templates:write
```

## Deploy

Use [DEPLOYMENT.md](DEPLOYMENT.md).

## Notes

- Real customer recommendations depend on real Shopify order history.
- Stores with sparse history may show held/considered plays instead of ready recommendations.
- Local synthetic demo data lives in the separate `beaconai-local-demo` repo.
