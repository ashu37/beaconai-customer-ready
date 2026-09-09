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

const crypto = require("node:crypto");
const { pool, query } = require("../db");

/**
 * A save that lost a race. Carries the row as it actually stands so the caller
 * can show the merchant what changed instead of silently discarding one of the
 * two edits.
 */
class CampaignRevisionConflict extends Error {
  constructor(campaign, expectedRevision) {
    super(
      `This campaign was changed elsewhere (revision ${campaign.revision}, you had ${expectedRevision}). ` +
      `Reload it before saving again.`
    );
    this.name = "CampaignRevisionConflict";
    this.statusCode = 409;
    this.campaign = campaign;
    this.expectedRevision = expectedRevision;
  }
}

/**
 * An edit to content that has already been sent.
 *
 * Once a campaign is handed off, its approved copy, rendered HTML and audience
 * are the record of an email that has left. Editing them in place would not
 * change what the recipients got — it would only make the record disagree with
 * it. Sending again is a new campaign, not a mutation of this one.
 */
class CampaignFrozen extends Error {
  constructor(campaign, fields) {
    super(
      `This campaign was handed off on ${new Date(campaign.frozenAt).toISOString()} and its approved ` +
      `content is now read-only (${fields.join(", ")}). Start a new draft to send a changed version.`
    );
    this.name = "CampaignFrozen";
    this.statusCode = 409;
    this.campaign = campaign;
    this.fields = fields;
  }
}

// Fields that describe WHAT WAS SENT. Frozen at handoff. Status bookkeeping,
// the Klaviyo id and measurement counts are deliberately not here: those record
// what happened to the send and must stay writable afterwards.
const FROZEN_FIELDS = new Set([
  "templateId", "copy", "draftEdits", "holdoutPct",
  "approvedCopy", "renderedHtml", "templateVersion", "audienceRef", "audienceHash",
]);

// Stable over membership, order-independent. Lets a later read tell whether the
// audience it resolved is the one the merchant reviewed.
function hashAudience(customerIds) {
  if (!Array.isArray(customerIds) || !customerIds.length) return null;
  const sorted = [...customerIds].map(String).sort();
  return crypto.createHash("sha256").update(sorted.join("\n")).digest("hex").slice(0, 32);
}

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
    revision: row.revision,
    displayName: row.display_name,
    status: row.status,
    templateId: row.template_id,
    copy: row.copy,
    draftEdits: row.draft_edits,
    holdoutPct: row.holdout_pct === null ? null : Number(row.holdout_pct),
    audienceSize: row.audience_size,
    holdoutSize: row.holdout_size,
    klaviyoCampaignId: row.klaviyo_campaign_id,
    approvedCopy: row.approved_copy,
    renderedHtml: row.rendered_html,
    templateVersion: row.template_version,
    audienceRef: row.audience_ref,
    audienceHash: row.audience_hash,
    reviewedAt: row.reviewed_at,
    frozenAt: row.frozen_at,
    frozen: Boolean(row.frozen_at),
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
//
// `expectedRevision`, when given, makes the write conditional: it applies only
// if the row still reads as the caller last saw it. Two people editing one
// campaign, or one person with a stale tab, previously produced a last-write-
// wins overwrite with nothing recording that an edit had been lost.
async function upsertCampaign({
  shopDomain, runId, playId, status, templateId, copy, draftEdits, klaviyoCampaignId,
  holdoutPct, displayName, expectedRevision,
}) {
  if (!shopDomain) throw new Error("shopDomain is required");
  if (!runId) throw new Error("runId is required");
  if (!playId) throw new Error("playId is required");
  if (status && !STATUSES.has(status)) throw new Error(`Unknown status: ${status}`);

  const existing = await findCampaign({ shopDomain, runId, playId });
  if (existing) {
    assertRevision(existing, expectedRevision);
    assertNotFrozen(existing, { templateId, copy, draftEdits, holdoutPct });
  }

  const { rows } = await query(
    `INSERT INTO clean.campaigns
       (shop_domain, run_id, play_id, status, template_id, copy, draft_edits, klaviyo_campaign_id,
        holdout_pct, display_name, approved_at, sent_at)
     VALUES ($1, $2, $3, COALESCE($4, 'draft'), $5, $6, $7, $8, COALESCE($9, 0.100), $10,
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
       -- The name is kept once known and never blanked by a later write that
       -- happens not to carry it; that is the whole point of storing it.
       display_name        = COALESCE($10, clean.campaigns.display_name),
       revision            = clean.campaigns.revision + 1,
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
     holdoutPct === undefined || holdoutPct === null ? null : Number(holdoutPct),
     displayName || null]
  );
  return rowToCampaign(rows[0]);
}

function assertRevision(campaign, expectedRevision) {
  if (expectedRevision === undefined || expectedRevision === null) return;
  const expected = Number(expectedRevision);
  if (!Number.isFinite(expected)) return;
  if (campaign.revision !== expected) throw new CampaignRevisionConflict(campaign, expected);
}

// Refuses only the fields that describe what was sent, and only the ones this
// write actually carries — so recording a Klaviyo id or a send failure against a
// frozen campaign still works.
function assertNotFrozen(campaign, patch) {
  if (!campaign.frozenAt) return;
  const touched = Object.keys(patch).filter(
    (key) => patch[key] !== undefined && FROZEN_FIELDS.has(key)
  );
  if (touched.length) throw new CampaignFrozen(campaign, touched);
}

async function findCampaign({ shopDomain, runId, playId }) {
  const { rows } = await query(
    `SELECT * FROM clean.campaigns
      WHERE shop_domain = $1 AND run_id = $2 AND play_id = $3`,
    [shopDomain, runId, playId]
  );
  return rows.length ? rowToCampaign(rows[0]) : null;
}

/**
 * Freeze what was sent, at handoff.
 *
 * Writes the approved copy, the exact rendered HTML, the template version and
 * the audience REFERENCE onto the row, then stamps frozen_at. After this the
 * campaign still records delivery state, but the description of the email and
 * who it went to cannot change.
 */
async function freezeCampaignAtHandoff(id, {
  approvedCopy, renderedHtml, templateVersion, audienceRef, customerIds, expectedRevision,
}) {
  const current = await getCampaign(id);
  if (!current) return null;
  assertRevision(current, expectedRevision);
  // Re-freezing an already-frozen campaign is refused rather than ignored: it
  // means a second handoff is being attempted against a record that already
  // describes a completed one.
  if (current.frozenAt) throw new CampaignFrozen(current, ["frozen_at"]);

  const { rows } = await query(
    `UPDATE clean.campaigns
        SET approved_copy    = COALESCE($2::jsonb, approved_copy, copy),
            rendered_html    = COALESCE($3, rendered_html),
            template_version = COALESCE($4, template_version),
            audience_ref     = COALESCE($5::jsonb, audience_ref),
            audience_hash    = COALESCE($6, audience_hash),
            reviewed_at      = COALESCE(reviewed_at, NOW()),
            frozen_at        = NOW(),
            revision         = revision + 1,
            updated_at       = NOW()
      WHERE id = $1
      RETURNING *`,
    [
      id,
      approvedCopy ? JSON.stringify(approvedCopy) : null,
      renderedHtml || null,
      templateVersion || null,
      audienceRef ? JSON.stringify(audienceRef) : null,
      hashAudience(customerIds),
    ]
  );
  return rows.length ? rowToCampaign(rows[0]) : null;
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
    displayName: "display_name",
  };

  if (patch.status && !STATUSES.has(patch.status)) {
    throw new Error(`Unknown status: ${patch.status}`);
  }

  const current = await getCampaign(id);
  if (!current) return null;
  assertRevision(current, patch.expectedRevision);
  assertNotFrozen(current, patch);

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
  sets.push("revision = revision + 1");
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
        SET copy = $5, template_id = COALESCE($4, template_id),
            revision = revision + 1, updated_at = NOW()
      WHERE shop_domain = $1 AND run_id = $2 AND play_id = $3
        -- A frozen campaign describes an email that has already gone out.
        -- Regenerating copy must not rewrite it; the cache miss is harmless.
        AND frozen_at IS NULL`,
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
  CampaignFrozen,
  CampaignRevisionConflict,
  findCampaign,
  freezeCampaignAtHandoff,
  hashAudience,
  upsertCampaign,
  recordRecipients,
  cacheCopyOnCampaign,
  listCampaigns,
  getCampaign,
  updateCampaign,
  findCachedCopy,
};
