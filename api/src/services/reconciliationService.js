// Reconciliation: find out what the provider actually has.
//
// Contract §5. This is the ONLY operation permitted to move a campaign out of
// `uncertain`, and it never creates anything. It exists because a request that
// times out may still have been executed, so "try again" is not a safe answer —
// a duplicate campaign is worse than a stalled one.

const { getCampaign } = require("./campaignService");
const { getDelivery, recordStatusCheck, transitionDelivery } = require("./deliveryStateService");

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
async function reconcileCampaign(campaignId, { findProviderCampaigns }) {
  const campaign = await getCampaign(campaignId);
  if (!campaign) return null;
  const delivery = await getDelivery(campaignId);

  let result;
  try {
    result = await findProviderCampaigns({ campaign, delivery });
  } catch (error) {
    // The check happened and failed. last_checked_at moves; last_confirmed_at
    // does not, so the state on screen stays visibly as old as it is.
    const after = await recordStatusCheck(campaignId, { ok: false, error: error.message });
    return { ok: false, reason: "check_failed", error: error.message, delivery: after };
  }

  const matches = result?.matches || [];

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
    // Nothing exists there, so a retry is now provably safe.
    if (delivery.state === "uncertain" || delivery.state === "creating") {
      await transitionDelivery(campaignId, "failed", {}, { fromProvider: true });
    }
    return { ok: true, reason: "not_found", delivery: await getDelivery(campaignId) };
  }

  const match = matches[0];
  await recordStatusCheck(campaignId, { ok: true });

  // Adopt the reference first, so a campaign we now know exists is never left
  // looking like one that does not.
  if (delivery.state === "uncertain" || delivery.state === "creating") {
    await transitionDelivery(campaignId, "created", {
      provider: match.provider || "klaviyo",
      providerCampaignId: match.id,
      providerCampaignUrl: match.url || null,
    }, { fromProvider: true });
  }

  const mapped = mapProviderStatus(match.status);
  if (mapped) {
    const fields = {
      provider: match.provider || "klaviyo",
      providerCampaignId: match.id,
      providerCampaignUrl: match.url || null,
      providerSendStatus: match.status || null,
    };
    if (mapped === "sent") {
      // The provider's send time, never ours. A window anchored on when someone
      // clicked a button is not anchored on when the email went out.
      fields.providerSentAt = match.sentAt || null;
      // Present-but-null is meaningful: "the provider reported no count".
      fields.providerSentCount = match.sentCount ?? null;
    }
    await transitionDelivery(campaignId, mapped, fields, { fromProvider: true })
      .catch((error) => {
        // A refused transition is not a failed check; the check succeeded and
        // told us something the contract does not allow us to apply.
        if (error.name !== "DeliveryTransitionRejected") throw error;
      });
  }

  return { ok: true, reason: mapped || "reference_only", delivery: await getDelivery(campaignId) };
}

module.exports = { mapProviderStatus, reconcileCampaign };
