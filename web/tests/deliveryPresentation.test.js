import test from "node:test";
import assert from "node:assert/strict";
import { presentDelivery } from "../src/deliveryPresentation.js";

const d = (state, extra = {}) => ({ state, ...extra });

test("nothing but a confirmed provider send says Sent", () => {
  for (const state of ["not_started", "creating", "created", "awaiting_send", "scheduled", "failed", "uncertain"]) {
    const view = presentDelivery(d(state));
    assert.notEqual(view.label, "Sent", `${state} must not read as sent`);
  }
  // Scheduled is the one most likely to be mistaken for sent. It is not.
  assert.equal(presentDelivery(d("scheduled")).label, "Scheduled in Klaviyo");
  assert.equal(presentDelivery(d("sent")).label, "Sent");
});

test("an unknown outcome offers no way to try again", () => {
  const view = presentDelivery(d("uncertain"));
  // A retry here could create a second campaign, and a duplicate send cannot be
  // taken back.
  assert.equal(view.primary, null);
  assert.equal(view.allowsCreate, false);
  assert.match(view.message, /couldn't confirm/);
});

test("a proven pre-creation failure is the only place retry is offered", () => {
  const failed = presentDelivery(d("failed"));
  assert.equal(failed.allowsCreate, true);
  assert.equal(failed.primary.label, "Retry creation");
  assert.match(failed.message, /saved email is unchanged/);
});

test("an unknown sent count is not zero", () => {
  const unknown = presentDelivery(d("sent", { providerSentAt: "2026-09-02T09:30:00Z", providerSentCount: null }));
  assert.match(unknown.sentSummary, /Sent count unavailable/);
  assert.ok(!unknown.sentSummary.includes("0 recipients"));

  const known = presentDelivery(d("sent", { providerSentAt: "2026-09-02T09:30:00Z", providerSentCount: 873 }));
  assert.match(known.sentSummary, /873 recipients/);

  // A provider that genuinely reports zero is a different statement.
  const zero = presentDelivery(d("sent", { providerSentAt: "2026-09-02T09:30:00Z", providerSentCount: 0 }));
  assert.match(zero.sentSummary, /0 recipients/);
});

test("a link is offered only when the provider gave us one", () => {
  const withLink = presentDelivery(d("created", { providerCampaignUrl: "https://klaviyo.example/c/1" }));
  assert.equal(withLink.primary.action, "open");
  assert.equal(withLink.primary.label, "Open draft in Klaviyo");
  assert.equal(withLink.findHint, null);

  // No verified deep link: tell the merchant how to find it rather than sending
  // them to a URL we made up.
  const without = presentDelivery(d("created", { campaignName: "Win-back" }));
  assert.equal(without.primary.action, "find");
  assert.match(without.findHint, /In Klaviyo, open Campaigns and find the draft named/);
  assert.match(without.findHint, /Win-back/);
});

test("an unchecked campaign says so rather than implying freshness", () => {
  assert.equal(presentDelivery(d("awaiting_send")).lastChecked, "Status updates when your pilot contact checks Klaviyo.");
  const checked = presentDelivery(d("awaiting_send", { lastCheckedAt: "2026-09-09T12:00:00Z" }));
  assert.match(checked.lastChecked, /^Last checked /);
});

test("a failed status check is surfaced, not swallowed", () => {
  const view = presentDelivery(d("created", {
    lastCheckedAt: "2026-09-09T12:00:00Z", lastCheckOk: false, lastCheckError: "timeout",
  }));
  assert.equal(view.lastCheckError, "timeout");
  const ok = presentDelivery(d("created", { lastCheckedAt: "2026-09-09T12:00:00Z", lastCheckOk: true }));
  assert.equal(ok.lastCheckError, null);
});

test("reconciliation is a founder action; a merchant is told who can do it", () => {
  const founder = presentDelivery(d("uncertain"), { isFounder: true });
  assert.equal(founder.founderAction.action, "reconcile");
  assert.equal(founder.merchantNote, null);

  const merchant = presentDelivery(d("uncertain"), { isFounder: false });
  assert.equal(merchant.founderAction, null);
  assert.match(merchant.merchantNote, /pilot contact/);
});

test("editing stops once a handoff holds the campaign", () => {
  assert.equal(presentDelivery(d("not_started")).editable, true);
  assert.equal(presentDelivery(d("failed")).editable, true);
  for (const state of ["creating", "created", "awaiting_send", "scheduled", "sent", "uncertain"]) {
    assert.equal(presentDelivery(d(state)).editable, false, state);
  }
});

test("a disconnected provider is asked for, not a dead create button", () => {
  const view = presentDelivery(d("not_started"), { klaviyoConnected: false });
  assert.equal(view.primary.action, "connect");
  assert.equal(view.allowsCreate, false);
  assert.match(view.message, /Connect Klaviyo/);
});

test("creation says plainly that nothing is sent", () => {
  assert.equal(presentDelivery(d("not_started")).caption, "Creates a draft. No email is sent.");
});

test("unloaded and unavailable are not 'nothing has happened yet'", () => {
  // Showing "Create draft" for a campaign that was already handed off is the
  // failure here — the merchant clicks it and creates a second one.
  const loading = presentDelivery(undefined);
  assert.equal(loading.state, "loading");
  assert.equal(loading.allowsCreate, false);

  const explicitLoading = presentDelivery({ state: "not_started" }, { loading: true });
  assert.equal(explicitLoading.allowsCreate, false);

  const unavailable = presentDelivery(null);
  assert.equal(unavailable.state, "unavailable");
  assert.equal(unavailable.allowsCreate, false);
  assert.match(unavailable.message, /Reload before creating/);
});

test("a campaign finished in Klaviyo is told what to do there, with the draft's name beside the link", () => {
  const mode = { handoffMode: "klaviyo_design" };
  const ready = presentDelivery(d("not_started"), mode);
  assert.equal(ready.primary.label, "Create draft in Klaviyo");
  assert.match(ready.caption, /You choose the template and send it in Klaviyo\. No email is sent\./);

  const created = presentDelivery(d("created", {
    providerCampaignUrl: "https://www.klaviyo.com/campaign/K1/wizard/1", campaignName: "BeaconAI - Win-back",
  }), mode);
  assert.equal(created.primary.action, "open");
  assert.match(created.detail, /choose a template, finish the email, check the sender and recipients, then send it from Klaviyo/);
  assert.equal(created.nameHint, "In Klaviyo it's named “BeaconAI - Win-back” (Campaigns).");
  assert.equal(created.lastChecked, "Status updates when your pilot contact checks Klaviyo.");

  // Refusals are the mode's too: an uncertain outcome still offers no retry.
  const uncertain = presentDelivery(d("uncertain"), mode);
  assert.equal(uncertain.primary, null);
  assert.equal(uncertain.allowsCreate, false);

  // The rendered-email wording is unchanged.
  assert.equal(presentDelivery(d("not_started")).caption, "Creates a draft. No email is sent.");
  assert.equal(presentDelivery(d("created", { providerCampaignUrl: "https://x" })).detail, "Finish reviewing the sender, recipients, links and footer in Klaviyo.");
});
