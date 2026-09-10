// How a durable delivery state is shown to a merchant.
//
// One place, testable, because these strings are claims. The contract
// (docs/PROVIDER_HANDOFF_CONTRACT.md) decides what we know; this decides what we
// say about it, and the two must not drift.
//
// Two rules run through everything here:
//   - Only a confirmed provider send may say "Sent".
//   - An unknown outcome offers no retry. A retry there can create a second
//     campaign, and a duplicate send cannot be taken back.

export const DELIVERY_PRESENTATION = {
  not_started: {
    label: "Ready to create draft",
    message: null,
    primary: { action: "create", label: "Create draft in Klaviyo" },
    caption: "Creates a draft. No email is sent.",
    editable: true,
  },
  creating: {
    label: "Creating draft",
    message: "Creating your draft in Klaviyo…",
    primary: null,
    // Content is reserved: an edit landing now would be frozen without review.
    editable: false,
  },
  created: {
    label: "Draft created",
    message: "Draft created in Klaviyo",
    detail: "Finish reviewing the sender, recipients, links and footer in Klaviyo.",
    primary: { action: "open", label: "Open draft in Klaviyo" },
    editable: false,
  },
  awaiting_send: {
    label: "Awaiting send confirmation",
    message: "Awaiting send confirmation",
    primary: { action: "open", label: "Open draft in Klaviyo" },
    editable: false,
  },
  scheduled: {
    // Scheduled is not sent, and must never be shown as if it were.
    label: "Scheduled in Klaviyo",
    message: "Scheduled in Klaviyo",
    primary: { action: "open", label: "Open draft in Klaviyo" },
    editable: false,
  },
  sent: {
    label: "Sent",
    message: null,
    primary: { action: "open", label: "Open campaign in Klaviyo" },
    editable: false,
  },
  failed: {
    label: "Draft not created",
    message: "The draft wasn't created. Your saved email is unchanged.",
    // Only reachable on a proven pre-creation failure, so retry is safe here
    // and nowhere else.
    primary: { action: "create", label: "Retry creation" },
    editable: true,
  },
  uncertain: {
    label: "Needs checking",
    message: "We couldn't confirm whether Klaviyo created the draft. We'll check before trying again.",
    // Deliberately no create action of any kind.
    primary: null,
    founderAction: { action: "reconcile", label: "Check Klaviyo status" },
    merchantNote: "Your pilot contact can refresh this status.",
    editable: false,
  },
};

function formatWhen(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
  });
}

/**
 * @param {object} delivery  the GET /campaigns/:id/delivery payload
 * @param {object} options
 * @param {boolean} options.isFounder      founder-only actions are hidden otherwise
 * @param {boolean} options.klaviyoConnected
 */
export function presentDelivery(delivery, { isFounder = false, klaviyoConnected = true, loading = false } = {}) {
  // "We have not loaded this yet" is not "nothing has happened yet". Treating
  // an unloaded campaign as not_started would show "Create draft" for one that
  // has already been handed off.
  if (loading || delivery === undefined) {
    return {
      state: "loading", label: "Checking status…", message: null, primary: null,
      caption: null, editable: false, allowsCreate: false, findHint: null, detail: null,
      lastChecked: null, lastCheckError: null, sentSummary: null,
      founderAction: null, merchantNote: null,
    };
  }
  if (delivery === null) {
    return {
      state: "unavailable",
      label: "Status unavailable",
      message: "We couldn't load this campaign's status. Reload before creating a draft.",
      primary: null, caption: null, editable: false, allowsCreate: false,
      findHint: null, detail: null, lastChecked: null, lastCheckError: null,
      sentSummary: null, founderAction: null, merchantNote: null,
    };
  }

  const state = delivery?.state || "not_started";
  const base = DELIVERY_PRESENTATION[state] || DELIVERY_PRESENTATION.not_started;

  // Nothing can be created without a provider connection, and offering the
  // button anyway produces a dead action.
  if (!klaviyoConnected && base.primary?.action === "create") {
    return {
      state, label: base.label,
      message: "Connect Klaviyo to create this draft.",
      primary: { action: "connect", label: "Connect Klaviyo" },
      caption: null, editable: base.editable, lastChecked: null,
      allowsCreate: false, findHint: null, detail: null,
      lastCheckError: null, sentSummary: null, founderAction: null, merchantNote: null,
    };
  }

  const primary = base.primary ? { ...base.primary } : null;
  // A link is offered only when the provider gave us one. Otherwise the merchant
  // is told how to find it, rather than sent to a URL we invented.
  if (primary?.action === "open" && !delivery?.providerCampaignUrl) {
    primary.action = "find";
    primary.label = null;
  }

  const findHint = primary?.action === "find"
    ? `Draft created. Open Klaviyo and find “${delivery?.campaignName || "this campaign"}”.`
    : null;

  // "When did we last look" — distinct from when the provider last confirmed
  // anything, and null renders as "not checked yet", never "just now".
  const checkedAt = formatWhen(delivery?.lastCheckedAt);
  const lastChecked = ["created", "awaiting_send", "scheduled", "uncertain"].includes(state)
    ? (checkedAt ? `Last checked ${checkedAt}` : "Not checked yet")
    : null;

  let sentSummary = null;
  if (state === "sent") {
    const when = formatWhen(delivery?.providerSentAt);
    // A count we do not have is not zero, and must not be rendered as one.
    const count = delivery?.providerSentCount == null
      ? "Sent count unavailable"
      : `${delivery.providerSentCount.toLocaleString()} recipients`;
    sentSummary = when ? `Sent · ${when} · ${count}` : `Sent · ${count}`;
  }

  return {
    state,
    label: state === "sent" ? "Sent" : base.label,
    message: base.message,
    detail: base.detail || null,
    primary,
    findHint,
    caption: base.caption || null,
    editable: base.editable,
    lastChecked,
    lastCheckError: delivery?.lastCheckOk === false ? delivery?.lastCheckError || null : null,
    sentSummary,
    founderAction: isFounder ? base.founderAction || null : null,
    merchantNote: !isFounder ? base.merchantNote || null : null,
    // The single question the action bar asks.
    allowsCreate: primary?.action === "create",
  };
}
