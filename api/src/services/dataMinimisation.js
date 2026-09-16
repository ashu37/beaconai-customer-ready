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

module.exports = { minimiseKlaviyoAssetPayload };
