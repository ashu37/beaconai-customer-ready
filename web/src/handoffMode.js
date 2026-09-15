// How a campaign reaches Klaviyo, and what the merchant is told about it.
//
//   rendered_email  BeaconAI renders the store's approved design; the merchant
//                   reviews that exact email and it goes to Klaviyo as a template.
//   klaviyo_design  BeaconAI creates the Klaviyo draft with the audience, subject,
//                   preview text and sender. The merchant chooses their own
//                   Klaviyo template, finishes the email and sends it in Klaviyo.
//                   BeaconAI's copy is suggested messaging, not the email.
//
// The server enforces the difference (a preview binding is required only for
// rendered_email); this module decides which mode a campaign is in and keeps the
// wording for each in one place.

export const HANDOFF_MODE = Object.freeze({
  RENDERED_EMAIL: "rendered_email",
  KLAVIYO_DESIGN: "klaviyo_design",
});

/**
 * @param {object} args
 * @param {string|null} args.storedMode   what the server recorded at handoff
 * @param {boolean} args.handedOff        the campaign has been handed off
 * @param {string|null} args.chosenMode   the merchant's choice on this screen
 * @param {boolean} args.designConfigured the store has an approved BeaconAI design
 */
export function resolveHandoffMode({ storedMode = null, handedOff = false, chosenMode = null, designConfigured = false } = {}) {
  // After handoff, what actually happened — never today's settings.
  if (storedMode === HANDOFF_MODE.RENDERED_EMAIL || storedMode === HANDOFF_MODE.KLAVIYO_DESIGN) return storedMode;
  // Handed off before there was a choice: those all went out as rendered emails.
  if (handedOff) return HANDOFF_MODE.RENDERED_EMAIL;
  // No BeaconAI design: finishing in Klaviyo is the only way, and needs no setup.
  if (!designConfigured) return HANDOFF_MODE.KLAVIYO_DESIGN;
  return chosenMode === HANDOFF_MODE.KLAVIYO_DESIGN ? HANDOFF_MODE.KLAVIYO_DESIGN : HANDOFF_MODE.RENDERED_EMAIL;
}

export function finishesInKlaviyo(mode) {
  return mode === HANDOFF_MODE.KLAVIYO_DESIGN;
}

// What the merchant does in Klaviyo after the draft exists. Klaviyo's own labels
// (Campaigns, Next, Email: saved) as they appeared in a real account, 2026-09-15.
export const FINISH_IN_KLAVIYO_STEPS = [
  "Open the draft in Klaviyo and go to its Message step.",
  "Choose one of your templates (Email: saved) or start from Klaviyo's library.",
  "Add the suggested messaging where it fits and finish the design.",
  "Check the sender and recipients.",
  "Send or schedule it from Klaviyo.",
];

export const SUGGESTED_MESSAGING_NOTE =
  "Suggested messaging to use in your Klaviyo template. The email your customers receive is the one you finish in Klaviyo.";

export const HANDOFF_SUGGESTION_NOTE =
  "This is the messaging suggested when the draft was created. The email itself is finished in Klaviyo, and changes made there aren't shown here.";
