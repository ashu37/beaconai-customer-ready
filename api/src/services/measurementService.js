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
const { config } = require("../config");

const DEFAULT_WINDOWS = [30, 60, 90];
const DAY_MS = 86400000;
// Founder decision (RESULTS_UI_SPEC §1): 24 hours, applied SEPARATELY to the
// store data and to the calculation. Recalculating old data does not make it
// fresh.
const FRESHNESS_MS = 24 * 3600000;

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
function compareArms(treated, holdout, criticalValue = 1.96) {
  if (!treated || !holdout || treated.n_customers < 2 || holdout.n_customers < 2) return null;

  const meanT = treated.revenue / treated.n_customers;
  const meanH = holdout.revenue / holdout.n_customers;
  const varT = variance(treated.n_customers, treated.revenue, treated.revenue_sq);
  const varH = variance(holdout.n_customers, holdout.revenue, holdout.revenue_sq);

  const se = Math.sqrt(varT / treated.n_customers + varH / holdout.n_customers);
  const diff = meanT - meanH;
  // 1.96: normal approximation. Arms here are hundreds to tens of thousands of
  // customers, where the t correction is immaterial.
  const margin = criticalValue * se;

  // Degenerate-arm guard.
  //
  // The failure this exists for is an arm with ZERO purchases: its variance is
  // exactly 0, so the interval collapses onto the other arm and a difference
  // looks certain when it rests on nothing. A 21-person holdout that happened to
  // buy nothing would otherwise report "worked".
  //
  // A SMALL non-zero count is noisy, not degenerate, and must still resolve.
  // 200 treated purchases against 4 held-out ones is a real effect — roughly
  // z = 7 on the underlying proportions — and refusing to report it would be its
  // own kind of dishonesty. So the gate is: at least one purchase in each arm,
  // and enough purchases overall to be worth a verdict.
  //
  // `thinEvidence` still flags an arm under five purchases so the reader can see
  // the result leans on few events, without the verdict being withheld.
  const MIN_BUYERS_PER_ARM = 1;
  const MIN_BUYERS_TOTAL = 10;
  const THIN_EVIDENCE_BELOW = 5;
  const tOrders = treated.n_orders ?? 0;
  const hOrders = holdout.n_orders ?? 0;
  const enoughEvents = tOrders >= MIN_BUYERS_PER_ARM
    && hOrders >= MIN_BUYERS_PER_ARM
    && tOrders + hOrders >= MIN_BUYERS_TOTAL;
  const thinEvidence = tOrders < THIN_EVIDENCE_BELOW || hOrders < THIN_EVIDENCE_BELOW;

  return {
    perCustomer: { treated: meanT, holdout: meanH, difference: diff, low: diff - margin, high: diff + margin },
    // Scaled to the treated arm: what the campaign added by being sent to them.
    incremental: {
      total: diff * treated.n_customers,
      low: (diff - margin) * treated.n_customers,
      high: (diff + margin) * treated.n_customers,
    },
    enoughEvents,
    thinEvidence,
    significant: enoughEvents && se > 0 && (diff - margin > 0 || diff + margin < 0),
  };
}

// Windows run from the PROVIDER-CONFIRMED send (Ticket D contract, Ticket F).
// `sent_at` is local bookkeeping stamped when a status changed; measuring from
// it would count orders placed before any customer could have seen the email.
//
// Measurement starts only when BOTH hold: the durable delivery state is `sent`
// (which only a provider response can write), and the provider gave a send
// time. A scheduled campaign can carry a scheduled time, and a created draft
// carries none; neither is a send.
function sendConfirmed(campaign) {
  return campaign.deliveryState === "sent" && Boolean(campaign.providerSentAt);
}

// Why a campaign has no measurement, in the contract's own terms. Nothing here
// invents a send time or starts a window.
function notMeasurable(campaign) {
  const state = campaign.deliveryState || "not_started";
  let reason;
  if (state === "sent") reason = "send_time_unknown";
  else if (state !== "not_started") reason = "send_not_confirmed";
  else if (campaign.sentAt) reason = "no_provider_record";
  else reason = "not_handed_off";
  return {
    measurable: false,
    reason,
    deliveryState: state,
    campaignId: campaign.id,
    playId: campaign.playId,
  };
}

// Measure one window and store the per-arm aggregates. Idempotent: re-measuring
// the same window overwrites, which is what happens as a window matures.
//
// Purchasers are counted separately from orders: ten orders from one customer
// are one purchaser. Any floor on "people who bought" reads this, never orders.
async function measureWindow(campaign, windowDays) {
  const sentAt = new Date(campaign.providerSentAt);
  const windowEnd = new Date(sentAt.getTime() + windowDays * DAY_MS);

  const { rows } = await query(PER_CUSTOMER_SQL, [
    campaign.id, campaign.shopDomain, sentAt.toISOString(), windowEnd.toISOString(),
  ]);

  const byArm = new Map();
  for (const row of rows) {
    const revenue = Number(row.revenue) || 0;
    const orders = Number(row.orders) || 0;
    const arm = byArm.get(row.arm) || { n_customers: 0, n_purchasers: 0, n_orders: 0, revenue: 0, revenue_sq: 0 };
    arm.n_customers += 1;
    arm.n_purchasers += orders > 0 ? 1 : 0;
    arm.n_orders += orders;
    arm.revenue += revenue;
    arm.revenue_sq += revenue * revenue;
    byArm.set(row.arm, arm);
  }

  for (const [arm, totals] of byArm) {
    await query(
      `INSERT INTO clean.campaign_measurements
         (campaign_id, window_days, arm, n_customers, n_purchasers, n_orders, revenue, revenue_sq, measured_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
       ON CONFLICT (campaign_id, window_days, arm) DO UPDATE SET
         n_customers  = EXCLUDED.n_customers,
         n_purchasers = EXCLUDED.n_purchasers,
         n_orders     = EXCLUDED.n_orders,
         revenue      = EXCLUDED.revenue,
         revenue_sq   = EXCLUDED.revenue_sq,
         measured_at  = NOW()`,
      [campaign.id, windowDays, arm, totals.n_customers, totals.n_purchasers, totals.n_orders,
       totals.revenue.toFixed(2), totals.revenue_sq.toFixed(4)]
    );
  }

  return Object.fromEntries(byArm);
}

async function measureCampaign(campaignId, options = {}) {
  const windows = options.windows || DEFAULT_WINDOWS;
  const campaign = await getCampaign(campaignId);
  if (!campaign) return { measurable: false, reason: "no_campaign" };
  if (!sendConfirmed(campaign)) return notMeasurable(campaign);

  for (const windowDays of windows) await measureWindow(campaign, windowDays);
  return summarizeCampaign(campaignId, { ...options, windows });
}

// The store data results are computed from, and how current it is. Two times:
// when the last successful sync finished (`lastSuccessfulSyncAt`), and how far
// its orders reach (`ordersCoveredThrough` — the sync's start, since orders
// placed after the fetch began are not in it).
function sourceFreshness(source = {}, now = Date.now()) {
  const last = source?.lastSuccessfulSyncAt ? new Date(source.lastSuccessfulSyncAt) : null;
  const covered = source?.ordersCoveredThrough ? new Date(source.ordersCoveredThrough) : null;
  const old = last ? now - last.getTime() > FRESHNESS_MS : true;
  return {
    lastSuccessfulSyncAt: last ? last.toISOString() : null,
    ordersCoveredThrough: covered ? covered.toISOString() : null,
    stale: old,
    reason: !last ? "no_successful_sync" : old ? "sync_older_than_24h" : null,
  };
}

function figures(arm) {
  if (!arm) return null;
  return {
    customers: arm.n_customers,
    // Null for rows written before purchasers were counted. Unknown, not zero.
    purchasers: arm.n_purchasers,
    orders: arm.n_orders,
    revenue: arm.revenue,
    revenuePerCustomer: arm.n_customers > 0 ? arm.revenue / arm.n_customers : null,
  };
}

/**
 * The typed assessment for one window. Pure, so each rule is testable alone.
 *
 * Order matters: a window is never assessed before it has closed, before the
 * store's orders are known to reach its end, or on figures missing the
 * purchaser count. After that come STRUCTURAL minimums only — fewer than two
 * customers leaves no variance to estimate, and a group with no purchasers has
 * a variance of exactly zero, collapsing the interval onto the other group.
 * Neither is a chosen threshold.
 *
 * Anything beyond that needs the campaign assessment policy (floors and the
 * interval's critical value), which is awaiting statistical review. Without
 * one, the result is `assessment_policy_pending`: the group figures are shown
 * as observations and no comparison is reported. With one, the 95%-style range
 * decides between higher, lower and no clear difference.
 */
function assessWindow({ complete, end, assigned, heldBack, source, policy }) {
  if (!assigned) return { state: "not_calculated", reasons: ["not_calculated"], comparison: null };
  if (!heldBack || heldBack.n_customers === 0) return { state: "no_holdout", reasons: ["no_holdout"], comparison: null };
  if (!complete) return { state: "measuring", reasons: ["window_open"], comparison: null };

  const covered = source?.ordersCoveredThrough ? new Date(source.ordersCoveredThrough).getTime() : null;
  if (covered == null) return { state: "awaiting_order_data", reasons: ["no_successful_sync"], comparison: null };
  if (covered < new Date(end).getTime()) {
    return { state: "awaiting_order_data", reasons: ["orders_not_synced_through_window_end"], comparison: null };
  }
  if (assigned.n_purchasers == null || heldBack.n_purchasers == null) {
    return { state: "not_calculated", reasons: ["purchasers_not_recorded"], comparison: null };
  }

  const structural = [];
  if (assigned.n_customers < 2 || heldBack.n_customers < 2) structural.push("fewer_than_two_customers");
  if (assigned.n_purchasers === 0 || heldBack.n_purchasers === 0) structural.push("no_purchasers_in_a_group");
  if (structural.length) return { state: "insufficient_data", reasons: structural, comparison: null };

  if (!policy) return { state: "assessment_policy_pending", reasons: ["assessment_policy_pending"], comparison: null };

  const floors = [];
  if (assigned.n_customers < policy.minCustomersPerArm || heldBack.n_customers < policy.minCustomersPerArm) floors.push("below_customer_floor");
  if (assigned.n_purchasers < policy.minPurchasersPerArm || heldBack.n_purchasers < policy.minPurchasersPerArm) floors.push("below_purchaser_floor");
  if (floors.length) return { state: "insufficient_data", reasons: floors, comparison: null };

  const cmp = compareArms(assigned, heldBack, policy.criticalValue);
  if (!cmp) return { state: "insufficient_data", reasons: ["fewer_than_two_customers"], comparison: null };
  const { difference, low, high } = cmp.perCustomer;
  const state = low > 0 ? "higher_spending" : high < 0 ? "lower_spending" : "no_clear_difference";
  // Per customer only. A total would invite adding campaigns together.
  return { state, reasons: [], comparison: { difference, low, high, criticalValue: policy.criticalValue } };
}

// Were this campaign's customers assigned to receive another BeaconAI campaign
// before this send or during the window? Confirmed sends before the window's
// end make it `present`. A handed-off campaign with no confirmed send time could
// have gone out inside the window, so it makes the answer `unknown` — never
// `none`. Failed drafts sent nothing and are ignored.
async function otherExposure(campaign, windowEnd) {
  const { rows } = await query(
    `SELECT
       COUNT(DISTINCT mine.customer_id) FILTER (
         WHERE oc.delivery_state = 'sent' AND oc.provider_sent_at IS NOT NULL AND oc.provider_sent_at < $3
       )::int AS exposed,
       COUNT(DISTINCT oc.id) FILTER (
         WHERE NOT (oc.delivery_state = 'sent' AND oc.provider_sent_at IS NOT NULL)
           AND (oc.delivery_state IN ('creating', 'created', 'awaiting_send', 'scheduled', 'uncertain', 'sent')
                OR oc.sent_at IS NOT NULL)
       )::int AS unconfirmed
       FROM clean.campaign_recipients mine
       JOIN clean.campaign_recipients other
         ON other.customer_id = mine.customer_id
        AND other.campaign_id <> mine.campaign_id
        AND other.arm = 'treated'
       JOIN clean.campaigns oc ON oc.id = other.campaign_id AND oc.shop_domain = $2
      WHERE mine.campaign_id = $1`,
    [campaign.id, campaign.shopDomain, windowEnd.toISOString()]
  );
  const exposed = rows[0]?.exposed || 0;
  const unconfirmed = rows[0]?.unconfirmed || 0;
  if (exposed > 0) return { status: "present", customers: exposed };
  if (unconfirmed > 0) return { status: "unknown", customers: null };
  return { status: "none", customers: 0 };
}

// Who was assigned, from the recorded split itself — not from audience totals.
async function assignmentCounts(campaignId) {
  const { rows } = await query(
    `SELECT arm, COUNT(*)::int AS n FROM clean.campaign_recipients WHERE campaign_id = $1 GROUP BY arm`,
    [campaignId]
  );
  if (!rows.length) return { assigned: null, heldBack: null };
  const n = (arm) => rows.find((r) => r.arm === arm)?.n ?? 0;
  return { assigned: n("treated"), heldBack: n("holdout") };
}

// Read stored measurements and turn them into a per-window response. Every
// figure, date, assessment and exposure note for a window comes from that
// window's own entry, so a screen following the selected window cannot mix them.
async function summarizeCampaign(campaignId, {
  windows = DEFAULT_WINDOWS, source = null, policy = config.campaignAssessmentPolicy || null, now = Date.now(),
} = {}) {
  const campaign = await getCampaign(campaignId);
  if (!campaign) return { measurable: false, reason: "no_campaign" };
  const assignment = await assignmentCounts(campaignId);
  if (!sendConfirmed(campaign)) return { ...notMeasurable(campaign), assignment };

  const { rows } = await query(
    `SELECT window_days, arm, n_customers, n_purchasers, n_orders, revenue, revenue_sq, measured_at
       FROM clean.campaign_measurements
      WHERE campaign_id = $1`,
    [campaignId]
  );

  const sentAt = new Date(campaign.providerSentAt);
  const freshness = sourceFreshness(source || {}, now);
  const results = [];
  for (const windowDays of windows) {
    const end = new Date(sentAt.getTime() + windowDays * DAY_MS);
    const forWindow = rows.filter((r) => r.window_days === windowDays);
    const raw = (name) => {
      const row = forWindow.find((r) => r.arm === name);
      if (!row) return null;
      return {
        n_customers: Number(row.n_customers),
        n_purchasers: row.n_purchasers == null ? null : Number(row.n_purchasers),
        n_orders: Number(row.n_orders),
        revenue: Number(row.revenue),
        revenue_sq: Number(row.revenue_sq),
      };
    };
    const assigned = raw("treated");
    const heldBack = raw("holdout");
    const measuredTimes = forWindow.map((r) => new Date(r.measured_at).getTime());
    const calculatedAt = measuredTimes.length ? new Date(Math.max(...measuredTimes)) : null;
    const complete = now >= end.getTime();
    const assessment = assessWindow({ complete, end, assigned, heldBack, source: freshness, policy });

    results.push({
      windowDays,
      start: sentAt.toISOString(),
      end: end.toISOString(),
      complete,
      daysElapsed: Math.max(0, Math.min(windowDays, Math.floor((now - sentAt.getTime()) / DAY_MS))),
      calculatedAt: calculatedAt ? calculatedAt.toISOString() : null,
      calculationStale: calculatedAt ? now - calculatedAt.getTime() > FRESHNESS_MS : true,
      assigned: figures(assigned),
      heldBack: figures(heldBack),
      assessment: { state: assessment.state, reasons: assessment.reasons },
      comparison: assessment.comparison,
      otherExposure: await otherExposure(campaign, end),
    });
  }

  return {
    measurable: true,
    campaignId,
    playId: campaign.playId,
    displayName: campaign.displayName,
    sentAt: campaign.providerSentAt,
    holdoutPct: campaign.holdoutPct,
    assignment,
    source: freshness,
    windows: results,
  };
}

// The program-level number is WITHDRAWN until the Ticket F protocol is live.
//
// It used to group every recipient by BOOL_OR(arm = 'treated') — ever-treated
// against never-treated — and count revenue from a fixed date 90 days ago, so a
// customer's pre-exposure spending landed in the outcome, and its order count was
// hard-coded to zero. That is not a valid program comparison (plan, Ticket F).
// The replacement is a prospective cohort with stored enrollment and assignment
// (docs/MEASUREMENT_PROTOCOL.md); until it exists, this reports that no program
// number is available and why.
async function summarizeProgram(shopDomain, { sinceDays = 90 } = {}) {
  const since = new Date(Date.now() - sinceDays * DAY_MS).toISOString();
  const { rows } = await query(
    `SELECT COUNT(*)::int AS n FROM clean.campaigns
      WHERE shop_domain = $1 AND delivery_state = 'sent'
        AND provider_sent_at IS NOT NULL AND provider_sent_at >= $2`,
    [shopDomain, since]
  );
  return {
    available: false,
    reason: "protocol_not_live",
    sinceDays,
    campaigns: Number(rows[0]?.n || 0),
  };
}

// Campaigns whose stored measurement needs recomputing: confirmed sent, and
// never measured, measured over a day ago, or measured before purchasers were
// counted. Cheap enough at this volume to run on read.
async function staleCampaignIds(shopDomain, { olderThanHours = 24 } = {}) {
  const { rows } = await query(
    `SELECT c.id
       FROM clean.campaigns c
       LEFT JOIN LATERAL (
         SELECT MAX(measured_at) AS measured_at,
                BOOL_OR(n_purchasers IS NULL) AS missing_purchasers
           FROM clean.campaign_measurements m
          WHERE m.campaign_id = c.id
       ) m ON true
      WHERE c.shop_domain = $1
        AND c.delivery_state = 'sent'
        AND c.provider_sent_at IS NOT NULL
        AND (m.measured_at IS NULL
             OR m.missing_purchasers
             OR m.measured_at < NOW() - ($2 || ' hours')::interval)`,
    [shopDomain, String(olderThanHours)]
  );
  return rows.map((r) => r.id);
}

module.exports = {
  assessWindow,
  measureCampaign,
  summarizeProgram,
  summarizeCampaign,
  sourceFreshness,
  staleCampaignIds,
  compareArms,
  variance,
  FRESHNESS_MS,
};
