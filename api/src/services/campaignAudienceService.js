// Audience resolution for the send preview.
//
// CONTRACT (DS-adjudicated 2026-08-21): the send audience is the ENGINE's
// decision, not an app re-derivation. Membership = the per-play audience CSV the
// engine materialized (customer_id list, keyed by audience_definition_id via the
// manifest, matched by play_id). The DB is used ONLY to hydrate email for those
// ids — never to SELECT who is in the audience. This traces every recipient to
// (run_id, audience_definition_id) per RULE B.
//
// Guards (DS-locked, non-negotiable):
//  R1: honor audience_materialization_status. != MATERIALIZED => typed absence
//      ("no auditable audience this run"), NEVER a DB fallback.
//  R2: never surface aov_individual (hardcoded 0.0) or CSV predicted_segment as a
//      merchant figure. Preview shows count + play identity only.
//  R3: consent is NOT gated here — Klaviyo enforces consent at send (founder
//      decision 2026-08-21). We hydrate emails and hand off; we do not filter.
//  R4: no audienceMode() / heuristic thresholds. Re-deriving membership is the bug.

const fs = require("fs/promises");
const path = require("path");
const { query } = require("../db");
const { readLatestRun } = require("./atulEngineService");

const MATERIALIZED = "MATERIALIZED";

// Parse the customer_id column from an engine audience CSV. Header is
// `customer_id,aov_individual,predicted_segment,rank_score`. We read ONLY
// customer_id (R2: never surface aov/segment). Returns an array of ids.
function parseCustomerIds(csvText) {
  const lines = String(csvText || "").split(/\r?\n/).filter((l) => l.trim() !== "");
  if (lines.length <= 1) return []; // header-only or empty
  const header = lines[0].split(",").map((h) => h.trim());
  const idIdx = header.indexOf("customer_id");
  if (idIdx === -1) return [];
  const ids = [];
  for (let i = 1; i < lines.length; i += 1) {
    const cols = lines[i].split(",");
    const id = (cols[idIdx] || "").trim();
    if (id) ids.push(id);
  }
  return ids;
}

// Find the manifest audience entry for a play and return { status, csvPath }.
function audienceEntryForPlay(manifest, manifestPath, playId) {
  const audiences = manifest?.artifacts?.audiences || [];
  const entry = audiences.find((a) => a.play_id === playId);
  if (!entry) return null;
  return {
    status: entry.audience_materialization_status || null,
    csvPath: path.resolve(path.dirname(manifestPath), entry.path),
    audienceDefinitionId: entry.audience_definition_id || null,
  };
}

// Hydrate emails for a set of customer_ids from the DB. Returns
// [{ customerId, email }] for ids that resolve to an email. Consent is NOT
// filtered here (R3) — Klaviyo enforces it at send.
async function hydrateEmails(shopDomain, customerIds) {
  if (!customerIds.length) return [];
  // Emails live on clean.customers (id) and/or clean.orders (customer_id).
  const [customers, orders] = await Promise.all([
    query(
      `SELECT id::text AS customer_id, email FROM clean.customers
       WHERE shop_domain = $1 AND COALESCE(email,'') <> '' AND id::text = ANY($2)`,
      [shopDomain, customerIds]
    ),
    query(
      `SELECT DISTINCT customer_id::text AS customer_id, email FROM clean.orders
       WHERE shop_domain = $1 AND COALESCE(email,'') <> '' AND customer_id::text = ANY($2)`,
      [shopDomain, customerIds]
    ),
  ]);
  const emailById = new Map();
  for (const row of orders.rows) if (!emailById.has(row.customer_id)) emailById.set(row.customer_id, row.email);
  for (const row of customers.rows) emailById.set(row.customer_id, row.email); // customers table wins
  const recipients = [];
  for (const id of customerIds) {
    const email = emailById.get(String(id));
    if (email) recipients.push({ customerId: id, email });
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
  if (!latest?.manifest || !latest?.manifestPath) {
    return { count: 0, recipients: [], materialized: false, status: null, reason: "no_run" };
  }

  const entry = audienceEntryForPlay(latest.manifest, latest.manifestPath, playId);
  if (!entry) {
    return { count: 0, recipients: [], materialized: false, status: null, reason: "no_audience_for_play" };
  }

  // R1: only a MATERIALIZED audience yields recipients. Anything else is a typed
  // absence — the engine deliberately did not produce an auditable audience.
  if (entry.status !== MATERIALIZED) {
    return {
      count: 0,
      recipients: [],
      materialized: false,
      status: entry.status,
      audienceDefinitionId: entry.audienceDefinitionId,
      reason: "not_materialized",
    };
  }

  let customerIds = [];
  try {
    customerIds = parseCustomerIds(await fs.readFile(entry.csvPath, "utf8"));
  } catch (_) {
    return { count: 0, recipients: [], materialized: false, status: entry.status, reason: "csv_unreadable" };
  }

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
  // exported for tests
  parseCustomerIds,
};
