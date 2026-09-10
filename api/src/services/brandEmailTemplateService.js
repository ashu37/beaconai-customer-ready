// Storage and versioning for the per-shop email shell.
//
// Append-only by design. A campaign freezes the version it rendered with, so
// editing a shell in place would retroactively change what an already-sent email
// looked like. A change is a new version; the old one stays readable.

const { pool, query } = require("../db");
const { BrandSetupRequired, validateShell } = require("./brandEmailRenderer");

function rowToTemplate(row) {
  if (!row) return null;
  return {
    id: row.id,
    shopDomain: row.shop_domain,
    version: row.version,
    html: row.html,
    slots: row.slots || [],
    brand: row.brand || {},
    source: row.source,
    approvedAt: row.approved_at,
    approvedBy: row.approved_by,
    notes: row.notes,
    createdAt: row.created_at,
  };
}

/**
 * Store a new version and make it the active one.
 *
 * Both in one transaction: a stored-but-not-activated version and an active
 * pointer to a version that failed to store are each worse than neither.
 * Validation runs BEFORE the write, so an unusable shell never becomes a row
 * someone might later activate by hand.
 */
async function saveBrandTemplate({ shopDomain, html, brand = {}, source = "founder_configured", approvedBy, notes, activate = true }) {
  if (!shopDomain) throw new Error("shopDomain is required");
  const { slots } = validateShell(html);

  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    // Serialize version allocation per shop, so two concurrent saves cannot both
    // claim the same version number.
    await client.query("SELECT pg_advisory_xact_lock(hashtext($1))", [`brand-email:${shopDomain}`]);

    const next = await client.query(
      `SELECT COALESCE(MAX(version), 0) + 1 AS version
         FROM clean.brand_email_templates WHERE shop_domain = $1`,
      [shopDomain]
    );
    const version = next.rows[0].version;

    const inserted = await client.query(
      `INSERT INTO clean.brand_email_templates
         (shop_domain, version, html, slots, brand, source, approved_at, approved_by, notes)
       VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, NOW(), $7, $8)
       RETURNING *`,
      [shopDomain, version, html, JSON.stringify(slots), JSON.stringify(brand), source, approvedBy || null, notes || null]
    );

    if (activate) {
      await client.query(
        `INSERT INTO clean.brand_email_active (shop_domain, template_id, activated_at)
         VALUES ($1, $2, NOW())
         ON CONFLICT (shop_domain) DO UPDATE SET
           template_id = EXCLUDED.template_id, activated_at = EXCLUDED.activated_at`,
        [shopDomain, inserted.rows[0].id]
      );
    }

    await client.query("COMMIT");
    return rowToTemplate(inserted.rows[0]);
  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    throw error;
  } finally {
    client.release();
  }
}

// The shell this shop currently sends with, or null. Scoped by shop_domain
// throughout: one merchant's branding must never render into another's email.
async function getActiveBrandTemplate(shopDomain) {
  const { rows } = await query(
    `SELECT t.* FROM clean.brand_email_active a
       JOIN clean.brand_email_templates t ON t.id = a.template_id
      WHERE a.shop_domain = $1`,
    [shopDomain]
  );
  return rowToTemplate(rows[0]);
}

// A specific historical version, for re-rendering what a past campaign sent.
async function getBrandTemplateVersion(shopDomain, version) {
  const { rows } = await query(
    `SELECT * FROM clean.brand_email_templates WHERE shop_domain = $1 AND version = $2`,
    [shopDomain, Number(version)]
  );
  return rowToTemplate(rows[0]);
}

async function listBrandTemplates(shopDomain) {
  const { rows } = await query(
    `SELECT * FROM clean.brand_email_templates WHERE shop_domain = $1 ORDER BY version DESC`,
    [shopDomain]
  );
  return rows.map(rowToTemplate);
}

/**
 * The active shell, or a typed refusal.
 *
 * Refusing is the point. Falling back to BeaconAI's own styling would put an
 * email the merchant never approved, wearing someone else's brand, in front of
 * their customers — and it would look like it worked.
 */
async function requireActiveBrandTemplate(shopDomain) {
  const template = await getActiveBrandTemplate(shopDomain);
  if (!template) throw new BrandSetupRequired(shopDomain);
  return template;
}

module.exports = {
  getActiveBrandTemplate,
  getBrandTemplateVersion,
  listBrandTemplates,
  requireActiveBrandTemplate,
  saveBrandTemplate,
};
