// Campaign measurement.
//
// Compares what the treated arm did against what the held-out arm did, over a
// window starting at the send. No new data source: the orders were already
// synced from Shopify, which is a better basis than Klaviyo's attributed
// revenue — Klaviyo decides what to credit itself, these are just orders.
//
// The product's whole claim is that it says what it knows and refuses to say
// what it doesn't. So every number here carries an interval, and a campaign
// whose interval spans zero reports "no effect found" rather than a hopeful
// point estimate.

const { query } = require("../db");
const { getCampaign } = require("./campaignService");

const DEFAULT_WINDOWS = [30, 60, 90];

// Matches campaignAudienceService's EMAIL_RE. A recipient's customer_id is
// either a real Shopify id or the customer's EMAIL used as an id — the engine's
// export derives it as `order.customer_id || raw.customer.id || <email>`. The
// join has to handle both, which is precisely the bug fixed in d64dc5b
// ("0 matched emails root cause"). Getting it wrong here would not error: the
// arms would silently under-count and every campaign would look weak.
const ORDER_MATCH = `(o.customer_id = r.customer_id OR o.email = r.customer_id)`;

// Per-customer revenue in the window, for every recipient of a campaign —
// including recipients who bought nothing, who are the majority and who the
// variance depends on.
//
// DISTINCT ON (o.id) so an order is credited once even if it could match two
// recipient rows. Refunds are netted: a refunded order is not revenue, and
// reporting it as such would inflate exactly the number merchants check.
const PER_CUSTOMER_SQL = `
  WITH matched AS (
    SELECT DISTINCT ON (o.id)
           o.id            AS order_id,
           r.customer_id   AS recipient_id,
           r.arm           AS arm,
           GREATEST(
             COALESCE(o.total_price, 0)
             - COALESCE((SELECT SUM(f.transaction_amount)
                           FROM clean.refunds f
                          WHERE f.shop_domain = o.shop_domain
                            AND f.order_id = o.id), 0),
             0
           )               AS net_revenue
      FROM clean.campaign_recipients r
      JOIN clean.orders o
        ON ${ORDER_MATCH}
       AND o.shop_domain = $2
       AND o.processed_at >= $3
       AND o.processed_at < $4
       AND o.cancelled_at IS NULL
       AND COALESCE(o.test, false) = false
     WHERE r.campaign_id = $1
     ORDER BY o.id, r.customer_id
  )
  SELECT r.arm,
         r.customer_id,
         COALESCE(SUM(m.net_revenue), 0) AS revenue,
         COUNT(m.order_id)               AS orders
    FROM clean.campaign_recipients r
    LEFT JOIN matched m ON m.recipient_id = r.customer_id AND m.arm = r.arm
   WHERE r.campaign_id = $1
   GROUP BY r.arm, r.customer_id
`;

// Sample variance of per-customer revenue, from the stored sufficient
// statistics. n < 2 has no variance to speak of.
function variance(n, sum, sumSq) {
  if (n < 2) return 0;
  return Math.max(0, (sumSq - (sum * sum) / n) / (n - 1));
}

/**
 * Compare two arms. Welch (unpooled) rather than a pooled test: the treated arm
 * almost always has the larger variance — it contains the people the campaign
 * moved — and pooling would understate the interval, which is the direction of
 * error this product cannot afford.
 */
function compareArms(treated, holdout) {
  if (!treated || !holdout || treated.n_customers < 2 || holdout.n_customers < 2) return null;

  const meanT = treated.revenue / treated.n_customers;
  const meanH = holdout.revenue / holdout.n_customers;
  const varT = variance(treated.n_customers, treated.revenue, treated.revenue_sq);
  const varH = variance(holdout.n_customers, holdout.revenue, holdout.revenue_sq);

  const se = Math.sqrt(varT / treated.n_customers + varH / holdout.n_customers);
  const diff = meanT - meanH;
  // 1.96: normal approximation. Arms here are hundreds to tens of thousands of
  // customers, where the t correction is immaterial.
  const margin = 1.96 * se;

  return {
    perCustomer: { treated: meanT, holdout: meanH, difference: diff, low: diff - margin, high: diff + margin },
    // Scaled to the treated arm: what the campaign added by being sent to them.
    incremental: {
      total: diff * treated.n_customers,
      low: (diff - margin) * treated.n_customers,
      high: (diff + margin) * treated.n_customers,
    },
    significant: se > 0 && (diff - margin > 0 || diff + margin < 0),
  };
}

// Measure one window and store the per-arm aggregates. Idempotent: re-measuring
// the same window overwrites, which is what happens as a window matures.
async function measureWindow(campaign, windowDays) {
  const sentAt = new Date(campaign.sentAt);
  const windowEnd = new Date(sentAt.getTime() + windowDays * 86400000);

  const { rows } = await query(PER_CUSTOMER_SQL, [
    campaign.id, campaign.shopDomain, sentAt.toISOString(), windowEnd.toISOString(),
  ]);

  const byArm = new Map();
  for (const row of rows) {
    const revenue = Number(row.revenue) || 0;
    const arm = byArm.get(row.arm) || { n_customers: 0, n_orders: 0, revenue: 0, revenue_sq: 0 };
    arm.n_customers += 1;
    arm.n_orders += Number(row.orders) || 0;
    arm.revenue += revenue;
    arm.revenue_sq += revenue * revenue;
    byArm.set(row.arm, arm);
  }

  for (const [arm, totals] of byArm) {
    await query(
      `INSERT INTO clean.campaign_measurements
         (campaign_id, window_days, arm, n_customers, n_orders, revenue, revenue_sq, measured_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
       ON CONFLICT (campaign_id, window_days, arm) DO UPDATE SET
         n_customers = EXCLUDED.n_customers,
         n_orders    = EXCLUDED.n_orders,
         revenue     = EXCLUDED.revenue,
         revenue_sq  = EXCLUDED.revenue_sq,
         measured_at = NOW()`,
      [campaign.id, windowDays, arm, totals.n_customers, totals.n_orders,
       totals.revenue.toFixed(2), totals.revenue_sq.toFixed(4)]
    );
  }

  return Object.fromEntries(byArm);
}

async function measureCampaign(campaignId, { windows = DEFAULT_WINDOWS } = {}) {
  const campaign = await getCampaign(campaignId);
  if (!campaign) return { measurable: false, reason: "no_campaign" };
  if (!campaign.sentAt) return { measurable: false, reason: "not_sent" };

  for (const windowDays of windows) await measureWindow(campaign, windowDays);
  return summarizeCampaign(campaignId, { windows });
}

// Read stored measurements and turn them into something reportable — with the
// verdict a merchant should act on, and no verdict at all where none is earned.
async function summarizeCampaign(campaignId, { windows = DEFAULT_WINDOWS } = {}) {
  const campaign = await getCampaign(campaignId);
  if (!campaign) return { measurable: false, reason: "no_campaign" };
  if (!campaign.sentAt) return { measurable: false, reason: "not_sent" };

  const { rows } = await query(
    `SELECT window_days, arm, n_customers, n_orders, revenue, revenue_sq, measured_at
       FROM clean.campaign_measurements
      WHERE campaign_id = $1
      ORDER BY window_days, arm`,
    [campaignId]
  );

  const daysElapsed = (Date.now() - new Date(campaign.sentAt).getTime()) / 86400000;

  const results = windows.map((windowDays) => {
    const forWindow = rows.filter((r) => r.window_days === windowDays);
    const arm = (name) => {
      const row = forWindow.find((r) => r.arm === name);
      if (!row) return null;
      return {
        n_customers: Number(row.n_customers),
        n_orders: Number(row.n_orders),
        revenue: Number(row.revenue),
        revenue_sq: Number(row.revenue_sq),
      };
    };

    const treated = arm("treated");
    const holdout = arm("holdout");
    const complete = daysElapsed >= windowDays;
    const comparison = compareArms(treated, holdout);

    // The verdict vocabulary is deliberately small and honest. "worked" is only
    // claimed when the interval excludes zero; an interval spanning zero is
    // reported as no effect found, never as a hopeful point estimate.
    let verdict;
    if (!treated) verdict = "not_measured";
    else if (!holdout || holdout.n_customers === 0) verdict = "no_holdout";
    else if (!complete) verdict = "measuring";
    else if (!comparison) verdict = "too_small";
    else if (comparison.significant) verdict = comparison.perCustomer.difference > 0 ? "worked" : "hurt";
    else verdict = "no_effect_found";

    return {
      windowDays,
      complete,
      daysElapsed: Math.floor(daysElapsed),
      verdict,
      treated,
      holdout,
      comparison,
    };
  });

  return {
    measurable: true,
    campaignId,
    playId: campaign.playId,
    sentAt: campaign.sentAt,
    holdoutPct: campaign.holdoutPct,
    windows: results,
  };
}

// The program-level number: everyone who received ANY campaign in the period,
// against everyone held out of all of them.
//
// This is the only comparison here that is reliably well-powered, because it
// pools every send. A single campaign's holdout may be a few hundred people; the
// program's is every held-out customer across the quarter. It is also the number
// that answers the question a merchant actually renews on — "is this software
// making me money" — rather than "did campaign #3 work".
//
// It is valid only because the holdout is GLOBAL and STABLE (see
// holdoutService): a customer is on the same side of the line in every campaign,
// so the two groups stay clean when pooled. A customer who somehow appears on
// both sides is counted as treated — the conservative direction, since it can
// only shrink the measured lift.
async function summarizeProgram(shopDomain, { sinceDays = 90 } = {}) {
  const since = new Date(Date.now() - sinceDays * 86400000).toISOString();

  const { rows } = await query(
    `WITH members AS (
       SELECT r.customer_id,
              BOOL_OR(r.arm = 'treated') AS ever_treated
         FROM clean.campaign_recipients r
         JOIN clean.campaigns c ON c.id = r.campaign_id
        WHERE c.shop_domain = $1
          AND c.sent_at IS NOT NULL
          AND c.sent_at >= $2
        GROUP BY r.customer_id
     ),
     revenue AS (
       SELECT m.customer_id,
              m.ever_treated,
              COALESCE(SUM(
                GREATEST(
                  COALESCE(o.total_price, 0)
                  - COALESCE((SELECT SUM(f.transaction_amount)
                                FROM clean.refunds f
                               WHERE f.shop_domain = o.shop_domain
                                 AND f.order_id = o.id), 0),
                  0
                )
              ), 0) AS revenue
         FROM members m
         LEFT JOIN clean.orders o
           ON (o.customer_id = m.customer_id OR o.email = m.customer_id)
          AND o.shop_domain = $1
          AND o.processed_at >= $2
          AND o.cancelled_at IS NULL
          AND COALESCE(o.test, false) = false
        GROUP BY m.customer_id, m.ever_treated
     )
     SELECT ever_treated,
            COUNT(*)::int        AS n_customers,
            SUM(revenue)         AS revenue,
            SUM(revenue*revenue) AS revenue_sq
       FROM revenue
      GROUP BY ever_treated`,
    [shopDomain, since]
  );

  const pick = (everTreated) => {
    const row = rows.find((r) => r.ever_treated === everTreated);
    if (!row) return null;
    return {
      n_customers: Number(row.n_customers),
      revenue: Number(row.revenue) || 0,
      revenue_sq: Number(row.revenue_sq) || 0,
      n_orders: 0,
    };
  };

  const treated = pick(true);
  const holdout = pick(false);
  const { rows: campaignRows } = await query(
    `SELECT COUNT(*)::int AS n FROM clean.campaigns
      WHERE shop_domain = $1 AND sent_at IS NOT NULL AND sent_at >= $2`,
    [shopDomain, since]
  );

  return {
    sinceDays,
    campaigns: Number(campaignRows[0]?.n || 0),
    treated,
    holdout,
    comparison: compareArms(treated, holdout),
  };
}

// Campaigns whose stored measurement has gone stale — sent, and either never
// measured or last measured over a day ago. At this volume that is cheap enough
// to run on read; it does not need a scheduler.
async function staleCampaignIds(shopDomain, { olderThanHours = 24 } = {}) {
  const { rows } = await query(
    `SELECT c.id
       FROM clean.campaigns c
       LEFT JOIN LATERAL (
         SELECT MAX(measured_at) AS measured_at
           FROM clean.campaign_measurements m
          WHERE m.campaign_id = c.id
       ) m ON true
      WHERE c.shop_domain = $1
        AND c.sent_at IS NOT NULL
        AND (m.measured_at IS NULL OR m.measured_at < NOW() - ($2 || ' hours')::interval)`,
    [shopDomain, String(olderThanHours)]
  );
  return rows.map((r) => r.id);
}

module.exports = {
  measureCampaign,
  summarizeProgram,
  summarizeCampaign,
  staleCampaignIds,
  compareArms,
  variance,
};
