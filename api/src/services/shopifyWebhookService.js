// Shopify webhooks.
//
// Nothing in a webhook is trusted until its HMAC — SHA-256 over the exact raw
// body, keyed with the app's client secret — matches the X-Shopify-Hmac-Sha256
// header, compared in constant time. A body parsed before verification can
// differ from the bytes Shopify signed, so verification runs on the Buffer.
//
//   app/uninstalled        access ends now (storeAccessService.uninstallStore)
//   customers/data_request that customer's stored data, gathered
//   customers/redact       everything personal about that customer, removed
//   shop/redact            the store erased (storeDataService.deleteStoreData)
//
// A privacy request is RECORDED before it is carried out, with only what
// identifies its subject, and the identifiers are dropped when it completes.
// Recording first is what makes it recoverable: Shopify retries a webhook it
// considers slow, and the row — not the request — is what says whether the work
// is still outstanding.

const crypto = require("node:crypto");
const { config } = require("../config");
const { query } = require("../db");
const { uninstallStore } = require("./storeAccessService");
const { deleteStoreData } = require("./storeDataService");
const { completePrivacyRequest, exportCustomerData, redactCustomer } = require("./privacyRequestService");

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
 * Do what a recorded privacy request asks.
 *
 *   customers/data_request  gathered and attached to the request row, for the
 *                           founder to pass to the merchant. Producing it is
 *                           not the same as sending it: it goes to the
 *                           merchant, who answers their own customer.
 *   customers/redact        everything personal about that customer removed.
 *   shop/redact             the whole store erased.
 *
 * Errors are logged and swallowed: the webhook has already been recorded, and
 * a 500 back to Shopify would only bring the same request again. The unfinished
 * row is the signal.
 */
async function carryOut({ id, topic, shopDomain, subject }) {
  try {
    if (topic === "customers/data_request") {
      const data = await exportCustomerData(shopDomain, {
        customerId: subject.customer_id,
        email: subject.customer_email,
      });
      await completePrivacyRequest(id, { found: data.found, counts: {
        customers: data.customers.length,
        orders: (data.orders || []).length,
        campaignMemberships: (data.campaignMemberships || []).length,
      } });
    } else if (topic === "customers/redact") {
      const result = await redactCustomer(shopDomain, {
        customerId: subject.customer_id,
        email: subject.customer_email,
      });
      await completePrivacyRequest(id, result);
    } else if (topic === "shop/redact") {
      const result = await deleteStoreData(shopDomain);
      await completePrivacyRequest(id, { deleted: result.deleted });
    }
  } catch (error) {
    console.error(`[webhook] ${topic} for ${shopDomain} could not be completed: ${error.message}`);
  }
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
    const subject = subjectOf(topic, payload);
    const recorded = await query(
      `INSERT INTO clean.privacy_requests (shop_domain, topic, webhook_id, payload)
       VALUES ($1, $2, $3, $4::jsonb)
       ON CONFLICT (webhook_id) WHERE webhook_id IS NOT NULL DO NOTHING
       RETURNING id`,
      [shopDomain, topic, webhookId, JSON.stringify(subject)]
    );
    console.log(`[webhook] ${topic} recorded for ${shopDomain}`);

    // Recorded first, then carried out. Shopify retries a slow webhook, and a
    // redaction is not something to run twice concurrently — so the row is the
    // durable part, and the work runs after it. A failure leaves completed_at
    // null, which is what `npm run privacy:pending` lists.
    const id = recorded.rows[0]?.id;
    if (id) await carryOut({ id, topic, shopDomain, subject });
    return { status: 200, body: { ok: true } };
  }

  // A topic this app does not handle: acknowledged so Shopify stops retrying.
  return { status: 200, body: { ok: true, ignored: true } };
}

module.exports = { PRIVACY_TOPICS, handleShopifyWebhook, subjectOf, verifyShopifyWebhookHmac };
