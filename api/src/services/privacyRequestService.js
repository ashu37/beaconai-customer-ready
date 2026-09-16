// One customer's data, produced or removed — as distinct from deleting a store.
//
// The policy is pseudonymisation, not obliteration: every piece of personal
// data about the customer goes (email, name, phone, addresses, consent, tags),
// while the internal customer id stays where it holds the store's own history
// together — which orders belong to one buyer, who was in an audience, who was
// treated and who was held back. Removing the id as well would silently rewrite
// the merchant's revenue figures and their campaign results, which are the
// merchant's records, not the customer's personal data.
//
// A redacted customer is marked, so a later sync cannot quietly refill the
// fields this cleared — see shopifyRepository.upsertCustomers and upsertOrders.
//
// The same details are stored in more than one place, and all of them are
// reached here: clean.customers, clean.orders (columns and payload),
// clean.campaign_recipients, clean.sync_runs.input_snapshot (the rows each
// analysis was computed from) and raw.shopify_events (the payloads every sync
// wrote). A redaction that stops at the first two is the bug this is shaped
// around.

const fs = require("node:fs/promises");
const path = require("node:path");

const { pool, query } = require("../db");
const {
  redactRawEventPayload,
  redactSnapshot,
  scrubOrderPayload,
  subjectKeys,
} = require("./dataMinimisation");

/** Resolve the subject Shopify named to the customer rows we hold. */
async function findCustomer(shopDomain, { customerId = null, email = null } = {}, run = query) {
  const { rows } = await run(
    `SELECT id, email FROM clean.customers
      WHERE shop_domain = $1
        AND (($2::text IS NOT NULL AND id = $2) OR ($3::text IS NOT NULL AND lower(email) = lower($3)))`,
    [shopDomain, customerId == null ? null : String(customerId), email]
  );
  return rows;
}

/**
 * What is stored about one customer, for the merchant to pass on.
 * Includes the derived rows — being in an audience or a campaign arm is data
 * about them too.
 */
async function exportCustomerData(shopDomain, subject) {
  const found = await findCustomer(shopDomain, subject);
  if (!found.length) return { shopDomain, subject, found: false, customers: [] };
  const ids = found.map((r) => r.id);

  const [customers, orders, recipients, exclusions, audiences] = await Promise.all([
    query(`SELECT * FROM clean.customers WHERE shop_domain = $1 AND id = ANY($2)`, [shopDomain, ids]),
    query(
      `SELECT id, name, created_at, processed_at, currency, subtotal_price, total_discounts,
              total_price, total_tax, financial_status, cancelled_at, tags, email
         FROM clean.orders WHERE shop_domain = $1 AND customer_id = ANY($2) ORDER BY created_at`,
      [shopDomain, ids]
    ),
    query(
      `SELECT r.campaign_id, r.customer_id, r.arm, c.display_name, c.play_id
         FROM clean.campaign_recipients r JOIN clean.campaigns c ON c.id = r.campaign_id
        WHERE c.shop_domain = $1 AND r.customer_id = ANY($2)`,
      [shopDomain, ids]
    ),
    query(
      `SELECT e.campaign_id, e.customer_ref, e.reason
         FROM clean.campaign_recipient_exclusions e JOIN clean.campaigns c ON c.id = e.campaign_id
        WHERE c.shop_domain = $1 AND e.customer_ref = ANY($2)`,
      [shopDomain, ids]
    ),
    query(
      `SELECT a.run_id, a.audience_definition_id, a.play_id
         FROM clean.engine_audiences a JOIN clean.engine_run_snapshots s ON s.run_id = a.run_id
        WHERE s.shop_domain = $1 AND a.customer_ids && $2::text[]`,
      [shopDomain, ids]
    ),
  ]);

  return {
    shopDomain,
    subject,
    found: true,
    customers: customers.rows,
    orders: orders.rows,
    campaignMemberships: recipients.rows,
    campaignExclusions: exclusions.rows,
    audiences: audiences.rows,
  };
}

/**
 * Remove everything personal about one customer, in one transaction.
 *
 * Campaign measurements are untouched: they hold counts and revenue totals per
 * arm, no identifiers. A campaign RE-measured after a redaction can report
 * different numbers from the ones already stored, because the orders it counts
 * no longer carry that buyer's details — the stored measurement is the record.
 *
 * @returns {Promise<{found: boolean, customerIds: string[], changed: object}>}
 */
async function redactCustomer(shopDomain, subject) {
  const client = await pool.connect();
  const run = (text, params) => client.query(text, params);
  try {
    await run("BEGIN");
    const found = await findCustomer(shopDomain, subject, run);
    if (!found.length) {
      await run("COMMIT");
      return { found: false, customerIds: [], changed: {} };
    }
    const ids = found.map((r) => r.id);
    const changed = {};

    const customers = await run(
      `UPDATE clean.customers
          SET email = NULL, tags = NULL, email_marketing_consent = NULL, state = NULL,
              redacted_at = NOW()
        WHERE shop_domain = $1 AND id = ANY($2)`,
      [shopDomain, ids]
    );
    changed["clean.customers"] = customers.rowCount;

    // Columns first, then the payload the columns were read from — leaving the
    // payload is the mistake that makes a redaction look done and not be.
    const orderColumns = await run(
      `UPDATE clean.orders SET email = NULL WHERE shop_domain = $1 AND customer_id = ANY($2)`,
      [shopDomain, ids]
    );
    const payloads = await run(
      `SELECT id, raw FROM clean.orders WHERE shop_domain = $1 AND customer_id = ANY($2) AND raw IS NOT NULL`,
      [shopDomain, ids]
    );
    for (const row of payloads.rows) {
      await run(`UPDATE clean.orders SET raw = $2::jsonb WHERE id = $1`, [
        row.id,
        JSON.stringify(scrubOrderPayload(row.raw)),
      ]);
    }
    changed["clean.orders"] = orderColumns.rowCount;

    // Membership stays, the address goes: which arm someone was in is what the
    // measurement is computed from, and it names no one once the email is gone.
    const recipients = await run(
      `UPDATE clean.campaign_recipients SET email = NULL
        WHERE customer_id = ANY($2)
          AND campaign_id IN (SELECT id FROM clean.campaigns WHERE shop_domain = $1)`,
      [shopDomain, ids]
    );
    changed["clean.campaign_recipients"] = recipients.rowCount;

    // The order's details are not only in clean.orders. Every analysis stored
    // the rows it was computed from, and every sync stored the payload it came
    // from — so a redaction that stops at the orders table leaves the buyer's
    // name and address in both.
    const keys = subjectKeys(found);

    const snapshots = await run(
      `SELECT id, input_snapshot FROM clean.sync_runs
        WHERE shop_domain = $1 AND input_snapshot IS NOT NULL`,
      [shopDomain]
    );
    let snapshotsChanged = 0;
    for (const row of snapshots.rows) {
      const next = redactSnapshot(row.input_snapshot, keys);
      if (!next) continue;
      await run(`UPDATE clean.sync_runs SET input_snapshot = $2::jsonb WHERE id = $1`, [
        row.id,
        JSON.stringify(next),
      ]);
      snapshotsChanged += 1;
    }
    changed["clean.sync_runs.input_snapshot"] = snapshotsChanged;

    const events = await run(
      `SELECT id, resource_type, payload FROM raw.shopify_events
        WHERE shop_domain = $1 AND resource_type IN ('customers', 'orders')`,
      [shopDomain]
    );
    let eventsChanged = 0;
    for (const row of events.rows) {
      const next = redactRawEventPayload(row.resource_type, row.payload, keys);
      if (!next) continue;
      await run(`UPDATE raw.shopify_events SET payload = $2::jsonb WHERE id = $1`, [
        row.id,
        JSON.stringify(next),
      ]);
      eventsChanged += 1;
    }
    changed["raw.shopify_events"] = eventsChanged;

    await run("COMMIT");
    return { found: true, customerIds: ids, changed };
  } catch (error) {
    await run("ROLLBACK").catch(() => {});
    throw error;
  } finally {
    client.release();
  }
}

/**
 * Mark a recorded request done, and drop the subject identifiers it was stored
 * with — the request row is kept as evidence the request was handled, which
 * does not require keeping the email address it was about.
 */
async function completePrivacyRequest(id, result = null) {
  const { rows } = await query(
    `UPDATE clean.privacy_requests
        SET completed_at = NOW(),
            payload = jsonb_strip_nulls(jsonb_build_object('result', $2::jsonb))
      WHERE id = $1 AND completed_at IS NULL
      RETURNING id, shop_domain, topic, completed_at`,
    [id, result == null ? null : JSON.stringify(result)]
  );
  return rows[0] || null;
}

/** One recorded request, with the subject it was received with. */
async function privacyRequest(id) {
  const { rows } = await query(
    `SELECT id, shop_domain, topic, webhook_id, payload, received_at, completed_at
       FROM clean.privacy_requests WHERE id = $1`,
    [id]
  );
  return rows[0] || null;
}

/**
 * Write the export for a recorded data request to a file, without completing
 * it. Producing the export is not delivering it; `recordDelivery` is.
 */
async function writeCustomerExport(id, outDir) {
  const request = await privacyRequest(id);
  if (!request) throw new Error(`No privacy request #${id}.`);
  if (request.topic !== "customers/data_request") {
    throw new Error(`Request #${id} is ${request.topic}, not a data request.`);
  }
  if (request.completed_at) {
    throw new Error(`Request #${id} was already delivered on ${request.completed_at.toISOString()}.`);
  }

  const data = await exportCustomerData(request.shop_domain, {
    customerId: request.payload?.customer_id ?? null,
    email: request.payload?.customer_email ?? null,
  });
  await fs.mkdir(outDir, { recursive: true });
  const file = path.join(outDir, `privacy-request-${id}.json`);
  await fs.writeFile(file, JSON.stringify(data, null, 2) + "\n");
  return { file, found: data.found, request };
}

/**
 * Mark a data request delivered. The note is the record of HOW — this is the
 * only step that says the merchant actually has the data, so it is deliberately
 * separate from producing the file and cannot be inferred from it.
 */
async function recordDelivery(id, note) {
  if (!note || !String(note).trim()) {
    throw new Error("Say how it was delivered: --note \"emailed the merchant 2026-09-16\"");
  }
  const request = await privacyRequest(id);
  if (!request) throw new Error(`No privacy request #${id}.`);
  if (request.completed_at) throw new Error(`Request #${id} is already complete.`);
  return completePrivacyRequest(id, { delivered: String(note).trim() });
}

async function pendingPrivacyRequests(shopDomain = null) {
  const { rows } = await query(
    `SELECT id, shop_domain, topic, webhook_id, payload, received_at
       FROM clean.privacy_requests
      WHERE completed_at IS NULL AND ($1::text IS NULL OR shop_domain = $1)
      ORDER BY received_at`,
    [shopDomain]
  );
  return rows;
}

module.exports = {
  completePrivacyRequest,
  exportCustomerData,
  pendingPrivacyRequests,
  privacyRequest,
  recordDelivery,
  redactCustomer,
  writeCustomerExport,
};
