// Audience resolution for the send preview.
//
// CONTRACT (DS-adjudicated 2026-08-21): the send audience is the ENGINE's
// decision, not an app re-derivation. Membership = the per-play customer_id list
// the engine materialized, keyed by audience_definition_id and matched by
// play_id. The DB is used ONLY to hydrate email for those ids — never to SELECT
// who is in the audience. This traces every recipient to
// (run_id, audience_definition_id) per RULE B.
//
// Phase 1 note: that list now comes from clean.engine_audiences instead of
// reading the engine's CSV off disk. This changes WHERE the engine's decision is
// read back from, never HOW it is made — the rows are a verbatim copy of the
// engine's own materialized CSV, written once at run time. The container
// filesystem the CSVs live on does not survive a restart, which silently turned
// a sendable audience into "not materialized". Never replace this with a SELECT
// over clean.customers: re-deriving membership is precisely what R4 forbids.
//
// Guards (DS-locked, non-negotiable):
//  R1: honor audience_materialization_status. != MATERIALIZED => typed absence
//      ("no auditable audience this run"), NEVER a DB fallback.
//  R2: never surface aov_individual (hardcoded 0.0) or predicted_segment as a
//      merchant figure. Preview shows count + play identity only.
//  R3: consent is NOT gated here — Klaviyo enforces consent at send (founder
//      decision 2026-08-21). We hydrate emails and hand off; we do not filter.
//  R4: no audienceMode() / heuristic thresholds. Re-deriving membership is the bug.

const { query } = require("../db");
const { readLatestRun } = require("./atulEngineService");

// Statuses that carry a sendable, audit-traceable customer list. MATERIALIZED =
// ranked (RFM substrate present); MATERIALIZED_UNRANKED = same audit-traceable
// order-history membership but no predictive ranking (substrate absent — cold
// start). Both are sendable; the merchant never sees the ranked/unranked
// distinction. SUPPRESSED_SUBSTRATE_REFUSED / NOT_MATERIALIZED are NOT sendable.
const SENDABLE_STATUSES = new Set(["MATERIALIZED", "MATERIALIZED_UNRANKED"]);

// The engine's materialized membership for one play of one run, as stored at
// run time. Returns null when the run produced no audience for this play.
async function audienceEntryForPlay(runId, playId) {
  const { rows } = await query(
    `SELECT audience_definition_id, materialization_status, customer_ids
       FROM clean.engine_audiences
      WHERE run_id = $1 AND play_id = $2
      LIMIT 1`,
    [runId, playId]
  );
  if (!rows.length) return null;
  return {
    status: rows[0].materialization_status || null,
    audienceDefinitionId: rows[0].audience_definition_id || null,
    customerIds: rows[0].customer_ids || [],
  };
}

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// Hydrate emails for a set of engine customer_ids. Returns [{ customerId, email }].
// Consent is NOT filtered here (R3) — Klaviyo enforces it at send.
//
// The engine's customer_id can take two shapes, because the app's order-export
// derives it as `order.customer_id || order.raw.customer.id || <email>`
// (atulEngineService.js customerId()): a real Shopify id, OR — when no id is
// present — the customer's EMAIL used as the id. So an audience CSV frequently
// carries emails in the customer_id column. We must resolve BOTH:
//   - email-shaped id  → the id IS the email; use it directly.
//   - other id         → join to clean.customers.id / clean.orders.customer_id.
async function hydrateEmails(shopDomain, customerIds) {
  if (!customerIds.length) return [];

  const recipients = [];
  const nonEmailIds = [];
  for (const id of customerIds) {
    const s = String(id).trim();
    if (EMAIL_RE.test(s)) {
      // Email-as-id: already deliverable, no DB lookup needed.
      recipients.push({ customerId: s, email: s });
    } else if (s) {
      nonEmailIds.push(s);
    }
  }

  if (nonEmailIds.length) {
    const [customers, orders] = await Promise.all([
      query(
        `SELECT id::text AS customer_id, email FROM clean.customers
         WHERE shop_domain = $1 AND COALESCE(email,'') <> '' AND id::text = ANY($2)`,
        [shopDomain, nonEmailIds]
      ),
      query(
        `SELECT DISTINCT customer_id::text AS customer_id, email FROM clean.orders
         WHERE shop_domain = $1 AND COALESCE(email,'') <> '' AND customer_id::text = ANY($2)`,
        [shopDomain, nonEmailIds]
      ),
    ]);
    const emailById = new Map();
    for (const row of orders.rows) if (!emailById.has(row.customer_id)) emailById.set(row.customer_id, row.email);
    for (const row of customers.rows) emailById.set(row.customer_id, row.email); // customers table wins
    for (const id of nonEmailIds) {
      const email = emailById.get(id);
      if (email) recipients.push({ customerId: id, email });
    }
  }

  return recipients;
}

/**
 * Resolve the send audience for a campaign from the ENGINE's materialized CSV.
 * @param {string} shopDomain
 * @param {object} campaign  the draft; campaign.id is the play_id.
 * @returns {Promise<{count, recipients, materialized, status, reason?, audienceDefinitionId?}>}
 */
async function resolveCampaignAudience(shopDomain, campaign = {}) {
  const playId = campaign.play_id || campaign.id || null;
  if (!playId) {
    return { count: 0, recipients: [], materialized: false, status: null, reason: "no_play_id" };
  }

  const latest = await readLatestRun({ shopDomain });
  if (!latest?.runId) {
    return { count: 0, recipients: [], materialized: false, status: null, reason: "no_run" };
  }

  const entry = await audienceEntryForPlay(latest.runId, playId);
  if (!entry) {
    return { count: 0, recipients: [], materialized: false, status: null, reason: "no_audience_for_play" };
  }

  // R1: only a sendable (MATERIALIZED or MATERIALIZED_UNRANKED) audience yields
  // recipients. Anything else is a typed absence — the engine deliberately did
  // not produce an auditable audience.
  if (!SENDABLE_STATUSES.has(entry.status)) {
    return {
      count: 0,
      recipients: [],
      materialized: false,
      status: entry.status,
      audienceDefinitionId: entry.audienceDefinitionId,
      reason: "not_materialized",
    };
  }

  const customerIds = entry.customerIds;
  const recipients = await hydrateEmails(shopDomain, customerIds);
  // suppressedCount = engine members whose email we could not resolve in the DB
  // (data gap, not a consent decision — R3 leaves consent to Klaviyo).
  const suppressedCount = Math.max(0, customerIds.length - recipients.length);

  return {
    count: recipients.length,
    recipients,
    materialized: true,
    status: entry.status,
    audienceDefinitionId: entry.audienceDefinitionId,
    memberCount: customerIds.length,
    suppressedCount,
  };
}

module.exports = {
  resolveCampaignAudience,
};
