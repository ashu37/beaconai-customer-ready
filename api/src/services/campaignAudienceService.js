const { query } = require("../db");

function normalizeText(value) {
  return String(value || "").toLowerCase();
}

function daysBetween(date, now = new Date()) {
  if (!date) return 0;
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return 0;
  return Math.max(0, Math.floor((now.getTime() - parsed.getTime()) / 86400000));
}

function audienceMode(campaign = {}) {
  const text = normalizeText([
    campaign.id,
    campaign.playTitle,
    campaign.segment,
    campaign.subject,
    campaign.bodyH2,
    campaign.bodyP1,
  ].filter(Boolean).join(" "));

  if (text.includes("first-to-second") || text.includes("second purchase") || text.includes("first time")) return "first_to_second";
  if (text.includes("discount")) return "discount";
  if (text.includes("aov") || text.includes("bundle")) return "aov_bundle";
  if (text.includes("dormant") || text.includes("winback") || text.includes("hibernating")) return "dormant";
  return "all_marketable";
}

function customerKey(row) {
  return row.customer_id || row.email;
}

async function resolveCampaignAudience(shopDomain, campaign = {}) {
  const ordersResult = await query(
    `
    SELECT customer_id, email, created_at, total_price, total_discounts
    FROM clean.orders
    WHERE shop_domain = $1
      AND COALESCE(email, '') <> ''
      AND cancelled_at IS NULL
    ORDER BY created_at ASC
    `,
    [shopDomain]
  );

  const customersResult = await query(
    `
    SELECT id, email, email_marketing_consent, state
    FROM clean.customers
    WHERE shop_domain = $1
      AND COALESCE(email, '') <> ''
    `,
    [shopDomain]
  );

  const consentByEmail = new Map();
  for (const customer of customersResult.rows) {
    const consent = customer.email_marketing_consent || {};
    const state = normalizeText(consent.state || customer.state);
    consentByEmail.set(normalizeText(customer.email), state);
  }

  const grouped = new Map();
  for (const order of ordersResult.rows) {
    const key = customerKey(order);
    if (!key) continue;
    const existing = grouped.get(key) || {
      customerId: order.customer_id,
      email: order.email,
      orders: [],
      totalRevenue: 0,
      totalDiscounts: 0,
    };
    existing.orders.push(order);
    existing.email = existing.email || order.email;
    existing.customerId = existing.customerId || order.customer_id;
    existing.totalRevenue += Number(order.total_price || 0);
    existing.totalDiscounts += Number(order.total_discounts || 0);
    grouped.set(key, existing);
  }

  const mode = audienceMode(campaign);
  const now = new Date();
  const candidates = Array.from(grouped.values()).filter((customer) => {
    const consentState = consentByEmail.get(normalizeText(customer.email));
    if (consentState && consentState !== "subscribed") return false;

    const orderCount = customer.orders.length;
    const firstOrder = customer.orders[0];
    const lastOrder = customer.orders[customer.orders.length - 1];
    const daysSinceFirst = daysBetween(firstOrder?.created_at, now);
    const daysSinceLast = daysBetween(lastOrder?.created_at, now);
    const discountRatio = customer.totalRevenue > 0 ? customer.totalDiscounts / customer.totalRevenue : 0;
    const averageOrderValue = orderCount ? customer.totalRevenue / orderCount : 0;

    if (mode === "first_to_second") return orderCount === 1 && daysSinceFirst >= 30;
    if (mode === "discount") return discountRatio >= 0.1 || customer.totalDiscounts > 0;
    if (mode === "aov_bundle") return averageOrderValue >= 50;
    if (mode === "dormant") return daysSinceLast >= 45;
    return true;
  });

  const limit = Math.max(1, Math.min(Number(campaign.customers || candidates.length || 100), 1000));
  const recipients = candidates.slice(0, limit).map((customer) => ({
    customerId: customer.customerId,
    email: customer.email,
    orderCount: customer.orders.length,
    totalRevenue: Number(customer.totalRevenue.toFixed(2)),
  }));

  return {
    mode,
    count: recipients.length,
    recipients,
    suppressedCount: Math.max(0, candidates.length - recipients.length),
  };
}

module.exports = {
  resolveCampaignAudience,
};
