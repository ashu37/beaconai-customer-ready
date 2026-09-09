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

const { pool, query } = require("../db");

// draft     — greenlit into the pipeline
// approved  — merchant signed off for send
// sent      — deployed to Klaviyo
// failed    — send attempted and failed
// dismissed — greenlit, then pulled back out. NOT a delete: the record that the
//             merchant considered and dropped it is signal worth keeping.
const STATUSES = new Set(["draft", "approved", "sent", "failed", "dismissed"]);

function rowToCampaign(row) {
  return {
    id: row.id,
    shopDomain: row.shop_domain,
    runId: row.run_id,
    playId: row.play_id,
    status: row.status,
    templateId: row.template_id,
    copy: row.copy,
    draftEdits: row.draft_edits,
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
async function upsertCampaign({ shopDomain, runId, playId, status, templateId, copy, draftEdits, klaviyoCampaignId, holdoutPct }) {
  if (!shopDomain) throw new Error("shopDomain is required");
  if (!runId) throw new Error("runId is required");
  if (!playId) throw new Error("playId is required");
  if (status && !STATUSES.has(status)) throw new Error(`Unknown status: ${status}`);

  const { rows } = await query(
    `INSERT INTO clean.campaigns
       (shop_domain, run_id, play_id, status, template_id, copy, draft_edits, klaviyo_campaign_id,
        holdout_pct, approved_at, sent_at)
     VALUES ($1, $2, $3, COALESCE($4, 'draft'), $5, $6, $7, $8, COALESCE($9, 0.100),
             -- Stamped on INSERT too, not only on conflict. A campaign created
             -- straight into 'sent' still has to record WHEN: measurement
             -- windows run from sent_at, so a missing stamp makes the campaign
             -- permanently unmeasurable rather than visibly broken.
             CASE WHEN $4 = 'approved' THEN NOW() END,
             CASE WHEN $4 = 'sent'     THEN NOW() END)
     ON CONFLICT (shop_domain, run_id, play_id) DO UPDATE SET
       status              = COALESCE($4, clean.campaigns.status),
       template_id         = COALESCE($5, clean.campaigns.template_id),
       copy                = COALESCE($6, clean.campaigns.copy),
       draft_edits         = COALESCE($7, clean.campaigns.draft_edits),
       klaviyo_campaign_id = COALESCE($8, clean.campaigns.klaviyo_campaign_id),
       holdout_pct         = COALESCE($9, clean.campaigns.holdout_pct),
       approved_at = CASE
                       WHEN $4 = 'approved' AND clean.campaigns.approved_at IS NULL
                       THEN NOW() ELSE clean.campaigns.approved_at
                     END,
       -- sent_at is what Phase 5 measures windows from, so it has to be stamped
       -- on whichever path marks the send — not only on PATCH.
       sent_at     = CASE
                       WHEN $4 = 'sent' AND clean.campaigns.sent_at IS NULL
                       THEN NOW() ELSE clean.campaigns.sent_at
                     END,
       updated_at  = NOW()
     RETURNING *`,
    [shopDomain, runId, playId, status || null, templateId || null,
     copy ? JSON.stringify(copy) : null,
     draftEdits === undefined ? null : JSON.stringify(draftEdits),
     klaviyoCampaignId || null,
     // NOT `|| null` — holdoutPct 0 means "send to everyone" and must survive.
     holdoutPct === undefined || holdoutPct === null ? null : Number(holdoutPct)]
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
    draftEdits: "draft_edits",
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
    const jsonColumn = key === "copy" || key === "draftEdits";
    values.push(jsonColumn ? JSON.stringify(patch[key]) : patch[key]);
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

// Cache generated copy on an EXISTING campaign. Deliberately an UPDATE, not an
// upsert: a campaign row means "the merchant put this play in their pipeline",
// and generating copy must not smuggle a play in there as a side effect. When no
// row exists the copy simply isn't cached — the same fail-soft behavior as
// before it was cached at all.
async function cacheCopyOnCampaign({ shopDomain, runId, playId, templateId, copy }) {
  const { rowCount } = await query(
    `UPDATE clean.campaigns
        SET copy = $5, template_id = COALESCE($4, template_id), updated_at = NOW()
      WHERE shop_domain = $1 AND run_id = $2 AND play_id = $3`,
    [shopDomain, runId, playId, templateId || null, JSON.stringify(copy)]
  );
  return rowCount > 0;
}

// The copy the model authored for this play, if it has been generated before.
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

// Record which arm every recipient landed in. Written once, at send time —
// after this there is no other record of who was held back, so a campaign
// without these rows can never be measured.
//
// Replaces the whole set for the campaign so a retried send cannot leave a
// customer in two arms, and runs in a transaction so a partial write never
// produces a half-recorded split.
async function recordRecipients(campaignId, { treated = [], holdout = [] }) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query(`DELETE FROM clean.campaign_recipients WHERE campaign_id = $1`, [campaignId]);
    for (const [arm, list] of [["treated", treated], ["holdout", holdout]]) {
      if (!list.length) continue;
      const ids = list.map((r) => r.customerId ?? r).filter(Boolean);
      await client.query(
        `INSERT INTO clean.campaign_recipients (campaign_id, customer_id, arm)
         SELECT $1, unnest($2::text[]), $3
         ON CONFLICT (campaign_id, customer_id) DO NOTHING`,
        [campaignId, ids, arm]
      );
    }
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    throw error;
  } finally {
    client.release();
  }
}

module.exports = {
  upsertCampaign,
  recordRecipients,
  cacheCopyOnCampaign,
  listCampaigns,
  getCampaign,
  updateCampaign,
  findCachedCopy,
};
