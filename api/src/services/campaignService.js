// Campaign persistence.
//
// A campaign is one play the merchant acted on, in one run. Until now this state
// lived in localStorage under a key that embedded the run id, so every new
// engine run discarded the entire history of what had been approved and sent.
// These rows outlive the run that produced them.
//
// Nothing here decides anything: the audience is still the engine's decision
// (see campaignAudienceService), and this module only records what the merchant
// did with it.

const { query } = require("../db");

const STATUSES = new Set(["draft", "approved", "sent", "failed"]);

function rowToCampaign(row) {
  return {
    id: row.id,
    shopDomain: row.shop_domain,
    runId: row.run_id,
    playId: row.play_id,
    status: row.status,
    templateId: row.template_id,
    copy: row.copy,
    holdoutPct: row.holdout_pct === null ? null : Number(row.holdout_pct),
    audienceSize: row.audience_size,
    holdoutSize: row.holdout_size,
    klaviyoCampaignId: row.klaviyo_campaign_id,
    approvedAt: row.approved_at,
    sentAt: row.sent_at,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

// Idempotent on (shop_domain, run_id, play_id): approving the same play twice
// updates the existing row rather than opening a second campaign for one send.
// COALESCE on the optional columns so a partial upsert never blanks a field that
// was already set — a later call carrying only a status must not erase the copy.
async function upsertCampaign({ shopDomain, runId, playId, status, templateId, copy }) {
  if (!shopDomain) throw new Error("shopDomain is required");
  if (!runId) throw new Error("runId is required");
  if (!playId) throw new Error("playId is required");
  if (status && !STATUSES.has(status)) throw new Error(`Unknown status: ${status}`);

  const { rows } = await query(
    `INSERT INTO clean.campaigns (shop_domain, run_id, play_id, status, template_id, copy)
     VALUES ($1, $2, $3, COALESCE($4, 'draft'), $5, $6)
     ON CONFLICT (shop_domain, run_id, play_id) DO UPDATE SET
       status      = COALESCE($4, clean.campaigns.status),
       template_id = COALESCE($5, clean.campaigns.template_id),
       copy        = COALESCE($6, clean.campaigns.copy),
       approved_at = CASE
                       WHEN $4 = 'approved' AND clean.campaigns.approved_at IS NULL
                       THEN NOW() ELSE clean.campaigns.approved_at
                     END,
       updated_at  = NOW()
     RETURNING *`,
    [shopDomain, runId, playId, status || null, templateId || null, copy ? JSON.stringify(copy) : null]
  );
  return rowToCampaign(rows[0]);
}

// Every campaign for a shop, across every run — newest first. The point of the
// table: a campaign from three runs ago is still here.
async function listCampaigns(shopDomain, { runId = null, limit = 200 } = {}) {
  const { rows } = await query(
    `SELECT * FROM clean.campaigns
      WHERE shop_domain = $1
        AND ($2::text IS NULL OR run_id = $2)
      ORDER BY created_at DESC
      LIMIT $3`,
    [shopDomain, runId, limit]
  );
  return rows.map(rowToCampaign);
}

async function getCampaign(id) {
  const { rows } = await query(`SELECT * FROM clean.campaigns WHERE id = $1`, [id]);
  return rows.length ? rowToCampaign(rows[0]) : null;
}

// Partial update by id. Only the named columns are touched; anything omitted
// keeps its current value.
async function updateCampaign(id, patch = {}) {
  const allowed = {
    status: "status",
    templateId: "template_id",
    copy: "copy",
    audienceSize: "audience_size",
    holdoutSize: "holdout_size",
    holdoutPct: "holdout_pct",
    klaviyoCampaignId: "klaviyo_campaign_id",
  };

  if (patch.status && !STATUSES.has(patch.status)) {
    throw new Error(`Unknown status: ${patch.status}`);
  }

  const sets = [];
  const values = [id];
  for (const [key, column] of Object.entries(allowed)) {
    if (patch[key] === undefined) continue;
    values.push(key === "copy" ? JSON.stringify(patch[key]) : patch[key]);
    sets.push(`${column} = $${values.length}`);
  }
  if (!sets.length) return getCampaign(id);

  // Stamp approved_at / sent_at the first time the campaign reaches that state,
  // so the timestamps record when it happened rather than when it was last touched.
  if (patch.status === "approved") sets.push("approved_at = COALESCE(approved_at, NOW())");
  if (patch.status === "sent") sets.push("sent_at = COALESCE(sent_at, NOW())");
  sets.push("updated_at = NOW()");

  const { rows } = await query(
    `UPDATE clean.campaigns SET ${sets.join(", ")} WHERE id = $1 RETURNING *`,
    values
  );
  return rows.length ? rowToCampaign(rows[0]) : null;
}

// The copy the LLM authored for this play, if it has been generated before.
// Replaces copywriterService's in-memory Map, which was lost on every restart —
// so copy silently regenerated and changed under the merchant.
async function findCachedCopy({ shopDomain, runId, playId, templateId }) {
  const { rows } = await query(
    `SELECT copy FROM clean.campaigns
      WHERE shop_domain = $1 AND run_id = $2 AND play_id = $3
        AND template_id IS NOT DISTINCT FROM $4
        AND copy IS NOT NULL`,
    [shopDomain, runId, playId, templateId || null]
  );
  return rows.length ? rows[0].copy : null;
}

module.exports = {
  upsertCampaign,
  listCampaigns,
  getCampaign,
  updateCampaign,
  findCachedCopy,
};
