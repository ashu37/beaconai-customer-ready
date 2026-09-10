// What a merchant is told about who this email goes to.
//
// Matched, planned-to-email, held back, and actually sent are four different
// numbers. Collapsing them is how a merchant ends up believing an email reached
// people it never reached, so each has its own label and its own absence.
//
// Nothing here invents an exclusion. If the API supplies no evidence for one, we
// say nothing rather than reassuring the merchant that "standard suppressions
// apply" — a claim the product was making without having applied any.

export const AUDIENCE_UNAVAILABLE = {
  not_loaded: "Audience not loaded yet.",
  not_materialized: "This run didn't produce a sendable audience for this play.",
  foreign_run: "This campaign's briefing belongs to a different store.",
  unknown_run: "The briefing behind this campaign isn't on record.",
};

// A number we do not have is not zero.
function count(value) {
  return value === null || value === undefined ? null : value;
}

function label(value) {
  return value === null || value === undefined ? "—" : value.toLocaleString();
}

export function summarizeAudience({ audience, breakdown, originRunId, inputProvenance, originRunDate } = {}) {
  if (!audience) {
    return { available: false, message: AUDIENCE_UNAVAILABLE.not_loaded, rows: [], exclusions: [] };
  }
  if (inputProvenance === "foreign_run" || inputProvenance === "unknown_run") {
    return { available: false, message: AUDIENCE_UNAVAILABLE[inputProvenance], rows: [], exclusions: [] };
  }
  if (!audience.materialized || !breakdown) {
    return {
      available: false,
      // A typed absence: the engine deliberately produced no auditable audience.
      // Not "0 matched".
      message: audience.reason === "no_audience_for_play"
        ? AUDIENCE_UNAVAILABLE.not_materialized
        : AUDIENCE_UNAVAILABLE.not_materialized,
      rows: [], exclusions: [],
    };
  }

  const rows = [
    {
      key: "matched",
      label: "Matched customers",
      value: label(count(breakdown.matched)),
      help: "Customers the briefing identified for this play.",
    },
    {
      key: "planned",
      label: "Planned email group",
      value: label(count(breakdown.plannedEmailGroup)),
      // "Assigned for handoff" — deliberately not "will receive".
      help: "Assigned to receive this email. Klaviyo confirms actual delivery.",
    },
    {
      key: "comparison",
      label: "Comparison group",
      value: label(count(breakdown.comparisonGroup)),
      help: "Held out of this campaign so later purchases can be compared.",
    },
  ];

  return {
    available: true,
    rows,
    // Only evidenced exclusions, each carrying its own reason.
    exclusions: breakdown.exclusions || [],
    providerNote: breakdown.providerAppliesAtSend || null,
    // Explicitly unknown until reconciliation says otherwise.
    actualSent: count(breakdown.actualSentCount),
    actualSentLabel: breakdown.actualSentCount == null
      ? "Confirmed after sending"
      : label(breakdown.actualSentCount),
    noComparisonWarning: breakdown.comparisonGroup === 0
      ? "Without a comparison group, Results can show later purchases but can't estimate this campaign's added revenue."
      : null,
    originRunId: originRunId || null,
    originRunDate: originRunDate || null,
    stale: inputProvenance === "verified_stale",
  };
}

export function summarizeSender(sender) {
  if (!sender || (!sender.name && !sender.email)) {
    return {
      verified: false,
      // The merchant finishes in Klaviyo, where the sender is set. Saying so is
      // honest; assembling a from-address out of the store domain would look
      // verified and be a guess.
      display: "Check in Klaviyo",
      replyTo: "Check in Klaviyo",
    };
  }
  return {
    verified: true,
    display: sender.name && sender.email ? `${sender.name} <${sender.email}>` : sender.name || sender.email,
    // Klaviyo sets reply-to per campaign, so an account-level lookup cannot
    // report it. Left explicit rather than implying it matches the sender.
    replyTo: sender.replyTo || "Check in Klaviyo",
  };
}
