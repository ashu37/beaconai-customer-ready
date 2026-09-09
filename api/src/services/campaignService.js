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
 * An edit to content that has already been sent, or that a handoff currently
 * holds.
 *
 * Once a campaign is handed off, its approved copy, rendered HTML and audience
 * are the record of an email that has left. Editing them in place would not
 * change what the recipients got — it would only make the record disagree with
 * it. Sending again is a new campaign, not a mutation of this one.
 *
 * The same applies from the moment a handoff RESERVES the campaign: an edit
 * landing between the reservation and the freeze would be captured in the frozen
 * record without ever having been reviewed.
 */
/**
 * An update to an existing campaign that did not say which revision it was
 * based on. Refused rather than applied: a caller that has not read the row
 * cannot know what it is about to overwrite.
 */
/**
 * A handoff that arrived while another one for the same campaign was still in
 * flight. Refused rather than queued: the other request may already have created
 * a provider draft.
 */
class CampaignHandoffInProgress extends Error {
  constructor(campaign) {
    super("A send for this campaign is already in progress. Wait for it to finish before trying again.");
    this.name = "CampaignHandoffInProgress";
    this.statusCode = 409;
    this.campaign = campaign;
  }
}

class CampaignRevisionRequired extends Error {
  constructor(campaign) {
    super("This campaign already exists; saving it requires the revision you last read.");
    this.name = "CampaignRevisionRequired";
    this.statusCode = 409;
    this.campaign = campaign;
  }
}

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

// Reservation-owner authority is passed as a SEPARATE argument, never as part
// of the patch object. A patch can arrive from a request body; a second
// positional argument cannot. Carrying it inside the patch meant any caller who
// could reach the public update route could claim to hold a reservation it did
// not hold, which nullified the guard it was there to enforce.

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
    handoffReservedAt: row.handoff_reserved_at,
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
// ONE statement. The revision and frozen checks are predicates on the write
// itself, not a SELECT beforehand: with a separate check, two saves quoting the
// same revision both read it, both pass, and both write — the later one silently
// destroying the earlier. `ON CONFLICT ... DO UPDATE ... WHERE` makes the
// database decide, so exactly one of any number of concurrent writers wins.
//
// An UPDATE therefore REQUIRES expectedRevision. A caller with no revision has
// not read the row, so it cannot know what it is about to overwrite. Inserts
// need none — there is nothing there to lose.
async function upsertCampaign({
  shopDomain, runId, playId, status, templateId, copy, draftEdits, klaviyoCampaignId,
  holdoutPct, displayName, expectedRevision,
}, internal = {}) {
  if (!shopDomain) throw new Error("shopDomain is required");
  if (!runId) throw new Error("runId is required");
  if (!playId) throw new Error("playId is required");
  if (status && !STATUSES.has(status)) throw new Error(`Unknown status: ${status}`);

  const expected = normalizeRevision(expectedRevision);
  const touchesFrozen = touchedFrozenFields({ templateId, copy, draftEdits, holdoutPct });

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
     -- $11 NULL fails this comparison, which is what refuses a revision-less
     -- update. $12 lets delivery bookkeeping through on a frozen or reserved
     -- campaign while refusing any write that touches what was sent. $13 is the
     -- handoff route itself, which already holds the reservation.
     WHERE clean.campaigns.revision = $11
       AND (NOT $12 OR clean.campaigns.frozen_at IS NULL)
       AND (NOT $12 OR $13 OR clean.campaigns.handoff_reserved_at IS NULL)
     RETURNING *`,
    [shopDomain, runId, playId, status || null, templateId || null,
     copy ? JSON.stringify(copy) : null,
     draftEdits === undefined ? null : JSON.stringify(draftEdits),
     klaviyoCampaignId || null,
     // NOT `|| null` — holdoutPct 0 means "send to everyone" and must survive.
     holdoutPct === undefined || holdoutPct === null ? null : Number(holdoutPct),
     displayName || null,
     expected,
     touchesFrozen,
     Boolean(internal.holdsReservation)]
  );

  if (rows.length) return rowToCampaign(rows[0]);

  // No row came back: the conflict target matched but the WHERE refused it.
  // Read the row to say WHY — the caller needs to tell "someone else changed
  // this" from "this has already been sent".
  const current = await findCampaign({ shopDomain, runId, playId });
  if (!current) throw new Error("Campaign write affected no row and none exists");
  throw conflictFor(current, expected, touchesFrozen, { templateId, copy, draftEdits, holdoutPct });
}

function normalizeRevision(value) {
  if (value === undefined || value === null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function touchedFrozenFields(patch) {
  return Object.keys(patch).some((key) => patch[key] !== undefined && FROZEN_FIELDS.has(key));
}

// Which of the two refusals applies. Frozen is reported first: "this has already
// been sent" is the more actionable answer, and a stale revision against a
// frozen campaign is not something a reload would fix.
function conflictFor(current, expected, touchesFrozen, patch) {
  if (touchesFrozen && current.handoffReservedAt && !current.frozenAt) {
    return new CampaignHandoffInProgress(current);
  }
  if (touchesFrozen && current.frozenAt) {
    return new CampaignFrozen(
      current,
      Object.keys(patch).filter((key) => patch[key] !== undefined && FROZEN_FIELDS.has(key))
    );
  }
  if (expected === null) return new CampaignRevisionRequired(current);
  return new CampaignRevisionConflict(current, expected);
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
  approvedCopy, renderedHtml, templateVersion, audienceRef, customerIds,
}) {
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
      -- Refuses a second freeze in the statement itself: a campaign already
      -- frozen describes a completed handoff, and re-freezing would overwrite
      -- the record of what actually went out.
      WHERE id = $1 AND frozen_at IS NULL
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
  if (rows.length) return rowToCampaign(rows[0]);

  const current = await getCampaign(id);
  if (!current) return null;
  throw new CampaignFrozen(current, ["frozen_at"]);
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
async function updateCampaign(id, patch = {}, internal = {}) {
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

  const expected = normalizeRevision(patch.expectedRevision);
  const touchesFrozen = touchedFrozenFields(patch);

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

  // The guards are predicates on this UPDATE, not a SELECT before it. A write
  // that touches what was sent requires the campaign to be unfrozen, and a write
  // that touches content requires the caller to name the revision it read.
  // Delivery bookkeeping — status, the Klaviyo id, measured counts — needs
  // neither: it records what happened TO a send and must work afterwards.
  const guards = [];
  if (touchesFrozen) {
    values.push(expected);
    guards.push(`revision = $${values.length}`);
    guards.push("frozen_at IS NULL");
    // A handoff in flight owns the content until it freezes or releases. The
    // route driving that handoff passes holdsReservation, because it IS the
    // holder — everyone else is refused.
    if (!internal.holdsReservation) guards.push("handoff_reserved_at IS NULL");
  } else if (expected !== null) {
    values.push(expected);
    guards.push(`revision = $${values.length}`);
  }

  const { rows } = await query(
    `UPDATE clean.campaigns SET ${sets.join(", ")}
      WHERE id = $1${guards.length ? ` AND ${guards.join(" AND ")}` : ""}
      RETURNING *`,
    values
  );
  if (rows.length) return rowToCampaign(rows[0]);

  const current = await getCampaign(id);
  if (!current) return null;
  throw conflictFor(current, expected, touchesFrozen, patch);
}

/**
 * Claim a campaign for handoff, atomically, BEFORE any external work.
 *
 * Reserving is a single conditional UPDATE, so two simultaneous handoffs cannot
 * both proceed to create a provider draft. Checking `frozen` in JavaScript and
 * then calling Klaviyo left a window in which both requests passed the check and
 * both sent.
 *
 * The reservation also requires the revision the merchant reviewed: handing off
 * a campaign whose content changed since they approved it would freeze a record
 * of something nobody signed off.
 */
async function reserveCampaignForHandoff(id, expectedRevision) {
  const expected = normalizeRevision(expectedRevision);

  // No NULL bypass. A handoff without a revision cannot state which version of
  // the content the merchant reviewed, and the freeze that follows would record
  // whatever happened to be in the row — which is the exact thing the
  // reservation exists to pin down.
  if (expected === null) {
    const current = await getCampaign(id);
    if (!current) return null;
    throw new CampaignRevisionRequired(current);
  }

  const { rows } = await query(
    `UPDATE clean.campaigns
        SET handoff_reserved_at = NOW(), revision = revision + 1, updated_at = NOW()
      WHERE id = $1
        AND frozen_at IS NULL
        AND handoff_reserved_at IS NULL
        AND revision = $2
      RETURNING *`,
    [id, expected]
  );
  if (rows.length) return rowToCampaign(rows[0]);

  const current = await getCampaign(id);
  if (!current) return null;
  if (current.frozenAt) throw new CampaignFrozen(current, ["handoff"]);
  if (current.handoffReservedAt) {
    throw new CampaignHandoffInProgress(current);
  }
  throw new CampaignRevisionConflict(current, expected);
}

/**
 * Give the reservation back so the merchant can retry.
 *
 * ONLY safe when nothing was created at the provider. If a draft may exist,
 * releasing would let a second handoff create a duplicate — so the caller keeps
 * the reservation and the campaign is left needing reconciliation (Ticket D).
 */
async function releaseHandoffReservation(id) {
  const { rows } = await query(
    `UPDATE clean.campaigns
        SET handoff_reserved_at = NULL, revision = revision + 1, updated_at = NOW()
      WHERE id = $1 AND frozen_at IS NULL
      RETURNING *`,
    [id]
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
  CampaignHandoffInProgress,
  CampaignRevisionRequired,
  releaseHandoffReservation,
  reserveCampaignForHandoff,
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
