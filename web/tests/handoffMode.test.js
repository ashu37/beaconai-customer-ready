import test from "node:test";
import assert from "node:assert/strict";
import { HANDOFF_MODE, resolveHandoffMode } from "../src/handoffMode.js";

test("a store without a BeaconAI design finishes in Klaviyo; one with a design defaults to it", () => {
  assert.equal(resolveHandoffMode({ designConfigured: false }), HANDOFF_MODE.KLAVIYO_DESIGN);
  // Without a design there is nothing to choose, whatever was chosen.
  assert.equal(resolveHandoffMode({ designConfigured: false, chosenMode: HANDOFF_MODE.RENDERED_EMAIL }), HANDOFF_MODE.KLAVIYO_DESIGN);
  assert.equal(resolveHandoffMode({ designConfigured: true }), HANDOFF_MODE.RENDERED_EMAIL);
  assert.equal(resolveHandoffMode({ designConfigured: true, chosenMode: HANDOFF_MODE.KLAVIYO_DESIGN }), HANDOFF_MODE.KLAVIYO_DESIGN);
});

test("after handoff, the recorded mode decides, never today's settings", () => {
  assert.equal(resolveHandoffMode({ storedMode: "klaviyo_design", handedOff: true, designConfigured: true }), HANDOFF_MODE.KLAVIYO_DESIGN);
  assert.equal(resolveHandoffMode({ storedMode: "rendered_email", handedOff: true, designConfigured: false }), HANDOFF_MODE.RENDERED_EMAIL);
  // Handed off before modes existed: those were rendered emails.
  assert.equal(resolveHandoffMode({ storedMode: null, handedOff: true, designConfigured: false }), HANDOFF_MODE.RENDERED_EMAIL);
});
