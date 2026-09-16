// What a stored record is allowed to keep.
//
// Two rules, both about the same thing: a copy of customer data that nothing
// reads is a copy that can only leak.
//
//   - clean.customers keeps the columns the engine and the audience build
//     actually use. The full Shopify customer JSON (names, addresses, phone,
//     order history, notes) had no reader at all — `getEngineInput` counts the
//     rows and nothing looks at `raw` — so it is no longer written, and the
//     column is dropped.
//
//   - clean.klaviyo_assets records WHAT was handed off, not WHO received it.
//     The recipient list is built and kept in clean.campaign_recipients, which
//     is where the audience, the holdout split and the exclusions are read
//     from; the asset row only ever needed ids and counts. It had no reader
//     either, but it is the larger copy: one row per handoff, every recipient
//     email inside it.
//
// Recipient data the product genuinely needs is untouched: hydrateEmails still
// resolves emails to build the audience, the handoff still sends them to
// Klaviyo, and campaign_recipients still stores membership and exclusions.

/** Ids and counts from a Klaviyo API resource; never its attributes. */
function resourceRef(resource) {
  const data = resource?.data ?? resource;
  if (!data || typeof data !== "object") return null;
  return {
    type: data.type ?? null,
    id: data.id ?? null,
  };
}

/**
 * The asset payload, with recipient identifiers removed.
 *
 * `audience.recipients` is the list of {customerId, email} the handoff sent;
 * it collapses to counts. `packageResult` collapses to the provider ids the
 * reconciliation path needs. `campaign` is the suggested copy — subject,
 * preview text, body, CTA — which names no one and is what "the handoff
 * suggestion" means, so it stays.
 */
function minimiseKlaviyoAssetPayload(payload = {}) {
  const { campaign, audience, packageResult, ...rest } = payload || {};
  const minimal = { ...rest };

  if (campaign !== undefined) minimal.campaign = campaign;

  if (audience !== undefined) {
    const a = audience || {};
    minimal.audience = {
      runId: a.runId ?? null,
      audienceDefinitionId: a.audienceDefinitionId ?? null,
      status: a.status ?? null,
      materialized: a.materialized ?? null,
      // Counts, not members. `count` is what was sent; memberCount is what the
      // engine produced; the difference is the suppressed rows.
      count: a.count ?? null,
      memberCount: a.memberCount ?? null,
      suppressedCount: a.suppressedCount ?? null,
      unresolvedCount: Array.isArray(a.unresolvedIds) ? a.unresolvedIds.length : null,
    };
  }

  if (packageResult !== undefined) {
    const p = packageResult || {};
    minimal.packageResult = {
      template: resourceRef(p.template),
      list: resourceRef(p.list),
      importJob: resourceRef(p.importJob),
      campaign: resourceRef(p.campaign),
      messageId: p.messages?.data?.[0]?.id ?? null,
      templateAssigned: Boolean(p.assignment),
    };
  }

  return minimal;
}

// Keys in a Shopify order payload that name or reach a person. Everything else
// — the money, the dates, the line items — is the merchant's business record.
//
// Applied in two places, and it has to be both: redactCustomer scrubs the
// payloads already stored, and upsertOrders scrubs the ones a later sync brings
// back. Shopify keeps returning a redacted customer's orders in full, so
// without the second the first undoes itself on the next sync.
const PERSONAL_ORDER_KEYS = new Set([
  "customer",
  "email",
  "contact_email",
  "phone",
  "billing_address",
  "shipping_address",
  "customer_locale",
  "note",
  "note_attributes",
  "client_details",
  "browser_ip",
  "landing_site",
  "referring_site",
  "checkout_id",
  "checkout_token",
  "order_status_url",
]);

/**
 * An order payload with nothing personal in it.
 *
 * `customer` goes entirely rather than being reduced to its id: the id is
 * already its own column (`clean.orders.customer_id`), which is what the engine
 * and the measurement read, so keeping a second copy inside the payload would
 * buy nothing and risk carrying a sibling field along with it.
 */
function scrubOrderPayload(raw) {
  if (!raw || typeof raw !== "object") return raw;
  const out = {};
  for (const [key, value] of Object.entries(raw)) {
    if (PERSONAL_ORDER_KEYS.has(key)) continue;
    out[key] = value;
  }
  return out;
}

// --- Redacting one customer out of the derived copies ------------------------
//
// An order's details are stored in more than one place, and a redaction that
// reaches only clean.orders is not a redaction:
//
//   clean.sync_runs.input_snapshot   the rows each analysis was computed from,
//                                    carrying the buyer's email, name and
//                                    shipping region per order line
//   raw.shopify_events               the complete Shopify payloads, written on
//                                    every sync and read by nothing
//
// Identity is preserved, detail is removed — the same policy as everywhere
// else. In the snapshot that matters mechanically as well: the engine groups by
// `Customer Email` when the column is present, so blanking it would merge every
// redacted buyer into one customer. A stable pseudonym keeps one distinct value
// per person and carries no address.

function matchesSubject(customerId, email, subject) {
  if (customerId != null && subject.customerIds.has(String(customerId))) return true;
  if (email && subject.emails.has(String(email).toLowerCase())) return true;
  return false;
}

/** `{ customerIds: Set, emails: Set }` from the rows a lookup found. */
function subjectKeys(rows) {
  return {
    customerIds: new Set(rows.map((r) => String(r.id))),
    emails: new Set(rows.map((r) => r.email).filter(Boolean).map((e) => String(e).toLowerCase())),
  };
}

/** The pseudonym that replaces an email in a stored analysis input. */
function snapshotPseudonym(customerId) {
  return `redacted-${customerId}`;
}

/**
 * One stored input snapshot with the subject's personal columns removed.
 * Returns null when nothing in it matched, so the caller can skip the write.
 */
function redactSnapshot(snapshot, subject) {
  const rows = snapshot?.orderRows;
  if (!Array.isArray(rows)) return null;

  let changed = false;
  const redacted = rows.map((row) => {
    const id = row.customer_id;
    if (!matchesSubject(id, row["Customer Email"], subject)) return row;
    changed = true;
    return {
      ...row,
      // Identity kept as a pseudonym; the address itself goes.
      "Customer Email": snapshotPseudonym(id),
      "Billing Name": "",
      "Shipping Province": "",
      "Shipping Country": "",
    };
  });

  return changed ? { ...snapshot, orderRows: redacted } : null;
}

/**
 * One raw Shopify event payload with the subject removed. Returns null when
 * nothing matched.
 *
 * Nothing reads this log, so a matched customer record is reduced to its id
 * rather than carefully rewritten: keeping the shape is worth something for
 * anyone debugging, keeping the person is not.
 */
function redactRawEventPayload(resourceType, payload, subject) {
  if (!Array.isArray(payload)) return null;
  let changed = false;

  if (resourceType === "customers") {
    const out = payload.map((customer) => {
      if (!matchesSubject(customer?.id, customer?.email, subject)) return customer;
      changed = true;
      return { id: customer?.id ?? null, beaconai_redacted: true };
    });
    return changed ? out : null;
  }

  if (resourceType === "orders") {
    const out = payload.map((order) => {
      if (!matchesSubject(order?.customer?.id, order?.email || order?.customer?.email, subject)) return order;
      changed = true;
      return scrubOrderPayload(order);
    });
    return changed ? out : null;
  }

  return null;
}

module.exports = {
  PERSONAL_ORDER_KEYS,
  minimiseKlaviyoAssetPayload,
  redactRawEventPayload,
  redactSnapshot,
  scrubOrderPayload,
  snapshotPseudonym,
  subjectKeys,
};
