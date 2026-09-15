// Shopify webhooks.
//
// Nothing in a webhook is trusted until its HMAC — SHA-256 over the exact raw
// body, keyed with the app's client secret — matches the X-Shopify-Hmac-Sha256
// header, compared in constant time. A body parsed before verification can
// differ from the bytes Shopify signed, so verification runs on the Buffer.
//
//   app/uninstalled        access ends now (storeAccessService.uninstallStore)
//   customers/data_request recorded for the privacy-request work (PR B)
//   customers/redact       recorded for the privacy-request work (PR B)
//   shop/redact            recorded for the privacy-request work (PR B)
//
// Each privacy request is stored with only what identifies its subject.

const crypto = require("node:crypto");
const { config } = require("../config");
const { query } = require("../db");
const { uninstallStore } = require("./storeAccessService");

const SHOP_RE = /^[a-z0-9][a-z0-9-]*\.myshopify\.com$/;
const PRIVACY_TOPICS = new Set(["customers/data_request", "customers/redact", "shop/redact"]);

function header(headers, name) {
  const value = headers?.[name] ?? headers?.[name.toLowerCase()];
  return Array.isArray(value) ? value[0] : value;
}

function verifyShopifyWebhookHmac(rawBody, providedHmac, secret = config.shopify.clientSecret) {
  if (!secret || !providedHmac || !Buffer.isBuffer(rawBody)) return false;
  const expected = crypto.createHmac("sha256", secret).update(rawBody).digest();
  let provided;
  try {
    provided = Buffer.from(String(providedHmac), "base64");
  } catch (_) {
    return false;
  }
  return provided.length === expected.length && crypto.timingSafeEqual(provided, expected);
}

// What a privacy request needs to be carried out, and nothing else.
function subjectOf(topic, payload) {
  if (topic === "shop/redact") {
    return { shop_id: payload?.shop_id ?? null, shop_domain: payload?.shop_domain ?? null };
  }
  return {
    shop_id: payload?.shop_id ?? null,
    customer_id: payload?.customer?.id ?? null,
    customer_email: payload?.customer?.email ?? null,
    customer_phone: payload?.customer?.phone ?? null,
    orders: payload?.orders_requested || payload?.orders_to_redact || [],
    data_request_id: payload?.data_request?.id ?? null,
  };
}

/**
 * @returns {Promise<{status: number, body: object}>}
 */
async function handleShopifyWebhook({ rawBody, headers }) {
  if (!verifyShopifyWebhookHmac(rawBody, header(headers, "x-shopify-hmac-sha256"))) {
    return { status: 401, body: { ok: false } };
  }

  const topic = String(header(headers, "x-shopify-topic") || "");
  const shopDomain = String(header(headers, "x-shopify-shop-domain") || "").toLowerCase();
  const webhookId = header(headers, "x-shopify-webhook-id") || null;
  if (!SHOP_RE.test(shopDomain)) return { status: 400, body: { ok: false } };

  if (topic === "app/uninstalled") {
    await uninstallStore(shopDomain);
    console.log(`[webhook] app/uninstalled: access ended for ${shopDomain}`);
    return { status: 200, body: { ok: true } };
  }

  if (PRIVACY_TOPICS.has(topic)) {
    let payload = null;
    try {
      payload = JSON.parse(rawBody.toString("utf8"));
    } catch (_) {
      return { status: 400, body: { ok: false } };
    }
    await query(
      `INSERT INTO clean.privacy_requests (shop_domain, topic, webhook_id, payload)
       VALUES ($1, $2, $3, $4::jsonb)
       ON CONFLICT (webhook_id) WHERE webhook_id IS NOT NULL DO NOTHING`,
      [shopDomain, topic, webhookId, JSON.stringify(subjectOf(topic, payload))]
    );
    console.log(`[webhook] ${topic} recorded for ${shopDomain}`);
    return { status: 200, body: { ok: true } };
  }

  // A topic this app does not handle: acknowledged so Shopify stops retrying.
  return { status: 200, body: { ok: true, ignored: true } };
}

module.exports = { PRIVACY_TOPICS, handleShopifyWebhook, verifyShopifyWebhookHmac };
