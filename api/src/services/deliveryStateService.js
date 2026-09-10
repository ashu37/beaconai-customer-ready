// Durable provider delivery state.
//
// Implements docs/PROVIDER_HANDOFF_CONTRACT.md, which was written first and is
// the authority for what each state means. The single rule: BeaconAI may only
// assert what the provider has confirmed.
//
// These writes deliberately do NOT bump `campaigns.revision`. That counter
// guards REVIEWED CONTENT — it is what a save and a handoff quote to prove they
// are acting on the version a merchant approved. Provider bookkeeping is not a
// content change, and letting it move the counter would make a merchant's
// in-flight save conflict because a status check happened to land.

const { query } = require("../db");

const DELIVERY_STATES = [
  "not_started", "creating", "created", "awaiting_send",
  "scheduled", "sent", "failed", "uncertain",
];

// Contract §1. `uncertain` has no edge back to `creating`: a request that timed
// out may still have been executed, and a duplicate campaign is worse than a
// stalled one. Only reconciliation can move a campaign out of it.
const TRANSITIONS = {
  not_started: ["creating"],
  creating: ["created", "failed", "uncertain"],
  created: ["awaiting_send", "scheduled", "sent", "uncertain"],
  awaiting_send: ["scheduled", "sent", "uncertain"],
  scheduled: ["sent", "awaiting_send", "uncertain"],
  sent: [],
  failed: ["creating"],
  uncertain: ["created", "failed"],
};

// States only reconciliation may write. Nothing local may claim a send.
const PROVIDER_CONFIRMED_ONLY = new Set(["awaiting_send", "scheduled", "sent"]);

class DeliveryTransitionRejected extends Error {
  constructor(from, to, reason) {
    super(reason || `A campaign cannot go from ${from} to ${to}.`);
    this.name = "DeliveryTransitionRejected";
    this.statusCode = 409;
    this.from = from;
    this.to = to;
  }
}

function rowToDelivery(row) {
  if (!row) return null;
  return {
    campaignId: row.id,
    state: row.delivery_state,
    provider: row.provider,
    providerCampaignId: row.provider_campaign_id,
    // Null unless a provider response gave us one. The UI falls back to
    // "open Klaviyo and find <name>" rather than following a guess.
    providerCampaignUrl: row.provider_campaign_url,
    lastCheckedAt: row.last_checked_at,
    lastCheckOk: row.last_check_ok,
    lastCheckError: row.last_check_error,
    lastConfirmedAt: row.last_confirmed_at,
    providerSentAt: row.provider_sent_at,
    // Nullable, and never coalesced. Null is "not known", not zero.
    providerSentCount: row.provider_sent_count,
    providerSendStatus: row.provider_send_status,
    // Local bookkeeping, carried so callers can see it is NOT the same thing.
    localStatus: row.status,
    localSentAt: row.sent_at,
    frozen: Boolean(row.frozen_at),
    handoffReservedAt: row.handoff_reserved_at,
  };
}

async function getDelivery(campaignId) {
  const { rows } = await query(`SELECT * FROM clean.campaigns WHERE id = $1`, [campaignId]);
  return rowToDelivery(rows[0]);
}

/**
 * Move a campaign's delivery state, refusing anything the contract forbids.
 *
 * The transition is a predicate on the UPDATE, so two concurrent writers cannot
 * both read a state, both find their move legal, and both apply it.
 */
async function transitionDelivery(campaignId, to, fields = {}, options = {}) {
  if (!DELIVERY_STATES.includes(to)) throw new Error(`Unknown delivery state: ${to}`);

  if (PROVIDER_CONFIRMED_ONLY.has(to) && !options.fromProvider) {
    throw new DeliveryTransitionRejected(
      null, to,
      `"${to}" may only be written from a provider response. Local state is not evidence of a send.`
    );
  }

  const allowedFrom = Object.entries(TRANSITIONS)
    .filter(([, targets]) => targets.includes(to))
    .map(([from]) => from);
  if (!allowedFrom.length) {
    throw new DeliveryTransitionRejected(null, to, `Nothing may transition to ${to}.`);
  }

  const { rows } = await query(
    `UPDATE clean.campaigns
        SET delivery_state        = $2,
            provider              = COALESCE($3, provider),
            provider_campaign_id  = COALESCE($4, provider_campaign_id),
            provider_campaign_url = COALESCE($5, provider_campaign_url),
            provider_sent_at      = COALESCE($6, provider_sent_at),
            -- NOT COALESCE: a provider that reports 0 must be able to say 0, and
            -- one that reports nothing must leave this null.
            provider_sent_count   = CASE WHEN $9 THEN $7 ELSE provider_sent_count END,
            provider_send_status  = COALESCE($8, provider_send_status),
            last_confirmed_at     = CASE WHEN $10 THEN NOW() ELSE last_confirmed_at END,
            updated_at            = NOW()
      WHERE id = $1
        AND delivery_state = ANY($11)
      RETURNING *`,
    [
      campaignId, to,
      fields.provider || null,
      fields.providerCampaignId || null,
      fields.providerCampaignUrl || null,
      fields.providerSentAt || null,
      fields.providerSentCount ?? null,
      fields.providerSendStatus || null,
      Object.prototype.hasOwnProperty.call(fields, "providerSentCount"),
      Boolean(options.fromProvider),
      allowedFrom,
    ]
  );
  if (rows.length) return rowToDelivery(rows[0]);

  const current = await getDelivery(campaignId);
  if (!current) return null;
  throw new DeliveryTransitionRejected(current.state, to);
}

/**
 * Record that a status check happened, whatever came of it.
 *
 * Deliberately separate from the state itself: a check that could not reach the
 * provider must move `last_checked_at` and leave `last_confirmed_at` alone, or a
 * stale state would look freshly confirmed because someone pressed refresh.
 */
async function recordStatusCheck(campaignId, { ok, error = null }) {
  const { rows } = await query(
    `UPDATE clean.campaigns
        SET last_checked_at = NOW(),
            last_check_ok = $2,
            last_check_error = $3,
            updated_at = NOW()
      WHERE id = $1
      RETURNING *`,
    [campaignId, Boolean(ok), ok ? null : (error || "unknown error")]
  );
  return rowToDelivery(rows[0]);
}

module.exports = {
  DELIVERY_STATES,
  DeliveryTransitionRejected,
  PROVIDER_CONFIRMED_ONLY,
  TRANSITIONS,
  getDelivery,
  recordStatusCheck,
  transitionDelivery,
};
