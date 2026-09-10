// Assembling the draft that gets previewed, rendered and sent.
//
// Extracted from the component so it can be tested directly: this function
// decides WHAT email exists, and a field silently dropped here is a field the
// merchant sets and never sees applied. That is exactly how a typed destination
// could sit in its own state while the email kept using the shop default.

// This used to read "Standard suppressions apply — recent buyers and
// unsubscribers are excluded." BeaconAI applies neither: consent and suppression
// are the provider's, at send. Stating it as ours was a claim about a check
// nobody had run, on the one screen where a merchant decides whether an email is
// safe to send.
export const STANDARD_SUPPRESSIONS_NOTE =
  "Klaviyo applies consent and suppression at send. The actual sent count is confirmed afterwards.";

export function agentCopyToDraftFields(agentCopy) {
  if (!agentCopy) return {};
  const out = {};
  const variants = Array.isArray(agentCopy.subject_variants) ? agentCopy.subject_variants : [];
  if (variants[0]) out.subject = variants[0];
  if (agentCopy.preview_text != null) out.previewText = agentCopy.preview_text;
  if (agentCopy.headline != null) out.bodyH2 = agentCopy.headline;
  if (agentCopy.body != null) out.bodyP1 = agentCopy.body;
  if (agentCopy.support != null) out.bodyP2 = agentCopy.support;
  if (agentCopy.cta != null) out.cta = agentCopy.cta;
  return out;
}

export function buildCampaignFromSelection(play, template, edits = {}, agentCopy = null, destinationUrl = null) {
  if (!play || !template) return null;
  const prompt = play.template_prompt || {};
  // Base copy precedence: LLM agent copy (CA-4) > selected template > static
  // template_prompt > neutral placeholder. Merchant edits always layer on top.
  const agentFields = agentCopyToDraftFields(agentCopy);
  const draft = {
    // Key by play id (1:1 with its selected template). A composite id broke every
    // downstream lookup (grouping, audience preview, klaviyo assets) that keys by play.id.
    id: play.id,
    playTitle: play.play_name || play.play_id,
    templateName: template.name,
    templateSource: template.source,
    status: "draft",
    customers: play.audience_size || 0,
    segment: play.audience_archetype || "—",
    subject: agentFields.subject || template.subject || prompt.subject || `${play.play_name} campaign`,
    previewText: agentFields.previewText || template.previewText || prompt.previewText || "Selected template ready for campaign review.",
    bodyH2: agentFields.bodyH2 || template.bodyH2 || prompt.headline || play.play_name || "BeaconAI campaign",
    bodyP1: agentFields.bodyP1 || template.bodyP1 || prompt.body || prompt.support || "",
    bodyP2: agentFields.bodyP2 != null ? agentFields.bodyP2 : (prompt.support || ""),
    cta: agentFields.cta || template.cta || prompt.cta || "",
    // CA-5: featured product for the image block (resolved from the agent copy).
    featuredProduct: agentCopy?.featured_product || null,
    // Where the button goes. Part of the DRAFT, not a field alongside it: the
    // preview and the handoff both render from this object, so a destination
    // kept outside it meant the merchant could type one and still get the shop
    // default — or a missing-link error — in the actual email.
    destinationUrl: destinationUrl || null,
    sendTime: "Manual review",
    suppression: STANDARD_SUPPRESSIONS_NOTE,
  };
  return {
    ...draft, ...edits,
    id: draft.id, playTitle: draft.playTitle, templateName: draft.templateName,
    templateSource: draft.templateSource, status: draft.status,
    destinationUrl: draft.destinationUrl,
  };
}

