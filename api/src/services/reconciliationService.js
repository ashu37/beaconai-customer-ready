// Reconciliation: find out what the provider actually has.
//
// Contract §5. This is the ONLY operation permitted to move a campaign out of
// `uncertain`, and it never creates anything. It exists because a request that
// times out may still have been executed, so "try again" is not a safe answer —
// a duplicate campaign is worse than a stalled one.

const { getCampaign } = require("./campaignService");
const { releaseHandoffReservation } = require("./campaignService");
const {
  applyConfirmedFacts,
  getDelivery,
  recordStatusCheck,
  transitionDelivery,
} = require("./deliveryStateService");

// Provider states mapped onto ours. Anything unrecognised leaves the campaign
// where it is rather than being guessed into a state we would then display.
function mapProviderStatus(status) {
  const value = String(status || "").toLowerCase();
  if (["sent", "complete", "completed", "done"].includes(value)) return "sent";
  if (["scheduled", "queued"].includes(value)) return "scheduled";
  if (["draft", "created"].includes(value)) return "awaiting_send";
  return null;
}

/**
 * @param {object} deps
 * @param {(args: {campaign, delivery}) => Promise<{matches: Array}>} deps.findProviderCampaigns
 *   Looks the campaign up at the provider by its recorded name and window.
 *   Returns every match — the ambiguous case is a real answer, not an error.
 */
async function reconcileCampaign(campaignId, { lookupById, findByName }) {
  const campaign = await getCampaign(campaignId);
  if (!campaign) return null;
  const delivery = await getDelivery(campaignId);

  let matches;
  let complete;
  try {
    if (delivery.providerCampaignId && lookupById) {
      // An id the provider gave us is a far stronger identity than any name
      // search. Skipping it was how reconciliation managed to "not find" a
      // campaign it already held a reference to.
      const found = await lookupById(delivery.providerCampaignId);
      matches = found ? [found] : [];
      complete = true;
    } else {
      const result = await findByName(campaign.providerCampaignName || null);
      matches = result?.matches || [];
      complete = Boolean(result?.complete);
    }
  } catch (error) {
    // The check happened and failed. last_checked_at moves; last_confirmed_at
    // does not, so the state on screen stays visibly as old as it is.
    const after = await recordStatusCheck(campaignId, { ok: false, error: error.message });
    return { ok: false, reason: "check_failed", error: error.message, delivery: after };
  }

  if (matches.length > 1) {
    // Do not guess. Adopting one of several would attach a merchant's campaign
    // record to an arbitrary provider object.
    await recordStatusCheck(campaignId, { ok: true });
    return {
      ok: true, reason: "ambiguous", matches: matches.length,
      delivery: await getDelivery(campaignId),
    };
  }

  if (matches.length === 0) {
    await recordStatusCheck(campaignId, { ok: true });

    // Absence may only be DECLARED when the lookup actually finished. A partial
    // listing that happens not to contain the campaign looks exactly like the
    // campaign not existing — and absence is what authorises a retry, so
    // guessing here could authorise a duplicate send.
    if (!complete) {
      return {
        ok: true, reason: "inconclusive",
        delivery: await getDelivery(campaignId),
      };
    }

    if (delivery.state === "uncertain" || delivery.state === "creating") {
      await transitionDelivery(campaignId, "failed", {}, { fromProvider: true });
      // "Safe to retry" has to mean retry actually works. The reservation is
      // what blocks the next attempt, so establishing absence must release it —
      // otherwise the campaign reads as retryable and refuses with
      // "a send is already in progress".
      await releaseHandoffReservation(campaignId).catch(() => {});
    }
    return { ok: true, reason: "not_found", delivery: await getDelivery(campaignId) };
  }

  const match = matches[0];
  await recordStatusCheck(campaignId, { ok: true });

  const reference = {
    provider: match.provider || "klaviyo",
    providerCampaignId: match.id,
    providerCampaignUrl: match.url || null,
    providerSendStatus: match.status || null,
  };

  // Adopt the reference first, so a campaign we now know exists is never left
  // looking like one that does not.
  if (delivery.state === "uncertain" || delivery.state === "creating") {
    await transitionDelivery(campaignId, "created", reference, { fromProvider: true });
  }

  const mapped = mapProviderStatus(match.status);
  if (mapped) {
    const fields = { ...reference };
    if (mapped === "sent") {
      // The provider's send time, never ours. A window anchored on when someone
      // clicked a button is not anchored on when the email went out.
      fields.providerSentAt = match.sentAt || null;
      // Present-but-null is meaningful: "the provider reported no count".
      fields.providerSentCount = match.sentCount ?? null;
    }
    await transitionDelivery(campaignId, mapped, fields, { fromProvider: true })
      .catch(async (error) => {
        if (error.name !== "DeliveryTransitionRejected") throw error;
        // A refused transition is not a failed check: the provider told us
        // something the state machine will not apply. The FACTS it carried are
        // still new and still true — a send count that arrived on a second check
        // must not be discarded because the state had not moved.
        await applyConfirmedFacts(campaignId, fields);
      });
  }

  return { ok: true, reason: mapped || "reference_only", delivery: await getDelivery(campaignId) };
}

module.exports = { mapProviderStatus, reconcileCampaign };
