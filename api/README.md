# BeaconAI API MVP

API-first MVP backend for BeaconAI.

It connects:
- Shopify dev store/custom app token
- PostgreSQL clean/raw tables
- Mock engine contract
- Klaviyo dev private API key

## Stack

- Node.js
- Express
- PostgreSQL
- Axios
- Docker Compose for local Postgres

This can later deploy to:
- AWS ECS Fargate
- EC2
- Elastic Beanstalk
- App Runner

For production, prefer ECS Fargate + RDS Postgres.

## Local Setup

### 1. Install dependencies

```bash
npm install
```

### 2. Start Postgres

```bash
docker compose up -d
```

### 3. Create env file

```bash
cp .env.example .env
```

Update `.env` with:

```env
SHOPIFY_SHOP_DOMAIN=your-dev-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_shopify_admin_api_token
KLAVIYO_PRIVATE_KEY=your_klaviyo_private_key
```

### 4. Initialize DB

```bash
npm run db:init
```

### 5. Start server

```bash
npm run dev
```

Server runs at:

```txt
http://localhost:4000
```

## Main endpoints

### Health

```http
GET http://localhost:4000/health
```

### Test Shopify connection

```http
POST http://localhost:4000/api/connections/shopify/test
Content-Type: application/json

{
  "limit": 5
}
```

### Test Klaviyo connection

```http
POST http://localhost:4000/api/connections/klaviyo/test
Content-Type: application/json

{}
```

### Sync Shopify data into Postgres

```http
POST http://localhost:4000/api/sync/shopify
Content-Type: application/json

{
  "limit": 10
}
```

### Export clean engine input

```http
GET http://localhost:4000/api/engine/input/testing-dev-utkexvrj.myshopify.com
```

### Run mock engine

```http
POST http://localhost:4000/api/engine/run
Content-Type: application/json

{}
```

### Create Klaviyo template from engine output

```http
POST http://localhost:4000/api/klaviyo/templates/from-engine
Content-Type: application/json

{}
```

### Full demo

```http
POST http://localhost:4000/api/demo/run
Content-Type: application/json

{
  "limit": 10
}
```

Flow:

```txt
Shopify API → raw.shopify_events → clean tables → mock engine → Klaviyo template
```

## Engine tables

Clean tables:

- clean.shop
- clean.orders
- clean.order_line_items
- clean.customers
- clean.products
- clean.product_variants
- clean.refunds

## Notes

This MVP can use dev tokens directly or stored OAuth tokens.

OAuth routes:

```http
GET /api/oauth/shopify/start?shop=your-store.myshopify.com
GET /api/oauth/shopify/callback
GET /api/oauth/klaviyo/start?shop=your-store.myshopify.com
GET /api/oauth/klaviyo/callback
GET /api/connections/status?shopDomain=your-store.myshopify.com
```

Required env vars for OAuth:

```env
API_BASE_URL=http://127.0.0.1:4010/api
WEB_BASE_URL=http://127.0.0.1:5177
TOKEN_ENCRYPTION_SECRET=local-long-random-secret
SHOPIFY_CLIENT_ID=your_shopify_app_client_id
SHOPIFY_CLIENT_SECRET=your_shopify_app_client_secret
KLAVIYO_CLIENT_ID=your_klaviyo_app_client_id
KLAVIYO_CLIENT_SECRET=your_klaviyo_app_client_secret
```

For the App Store version:

- Shopify token should come from Shopify OAuth install flow.
- Klaviyo should use OAuth instead of manually pasted private key.
- Tokens should be encrypted and stored securely.
- Use AWS Secrets Manager/KMS or encrypted DB columns.
