import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

// Ticket F, as the merchant sees it today: every handed-off campaign is listed
// in the delivery contract's own words, none shows a result before a confirmed
// send, and the withdrawn program comparison says it hasn't started.
const delivery = (state, extra = {}) => ({ state, providerCampaignUrl: null, lastCheckedAt: null, ...extra });
const row = (campaignId, playId, state, reason) => ({
  measurable: false, reason, deliveryState: state, campaignId, playId, sentAt: null, delivery: delivery(state),
});

const apiModule = await import("../src/api.js");
apiModule.api.setShopDomain("results-f.myshopify.com");
const stub = (value) => async () => value;
Object.assign(apiModule.api, {
  health: stub({ ok: true }),
  session: stub({ ok: true, authenticated: true, shopDomain: "results-f.myshopify.com" }),
  connectionStatus: stub({ ok: true, status: { shopify: { connected: true }, klaviyo: { connected: true } } }),
  testShopify: stub({ ok: true }),
  testKlaviyo: stub({ ok: true }),
  brandContext: stub({ ok: true, brandContext: null }),
  brandEmailTemplate: stub({ ok: true, configured: false }),
  klaviyoSender: stub({ ok: true, sender: null }),
  getEngineInput: stub({ ok: true, input: null }),
  getLatestEngineRun: stub({ ok: true, found: false }),
  listCampaigns: stub({ ok: true, campaigns: [] }),
  syncStatus: stub({ ok: true, ready: true, reasons: [] }),
  getStatsSeries: stub({ ok: true, weeks: [] }),
  getKlaviyoTemplates: stub({ ok: true, templates: [] }),
  getResults: stub({
    ok: true,
    program: { available: false, reason: "protocol_not_live", sinceDays: 90, campaigns: 0 },
    results: [
      row(1, "winback_dormant_cohort", "created", "send_not_confirmed"),
      row(2, "discount_dependency_hygiene", "scheduled", "send_not_confirmed"),
      row(3, "cohort_journey_first_to_second", "uncertain", "send_not_confirmed"),
      row(4, "replenishment_due", "sent", "send_time_unknown"),
    ],
  }),
});

const { App } = await import("../src/App.jsx");
test.afterEach(() => cleanup());

test("handed-off campaigns are listed by delivery state, with no result before a confirmed send", async () => {
  await act(async () => {
    render(React.createElement(App));
    await new Promise((resolve) => setTimeout(resolve, 50));
  });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Results" }));
    await new Promise((resolve) => setTimeout(resolve, 50));
  });
  const text = document.body.textContent || "";

  // The same labels the Campaigns page uses (presentDelivery), never "Sent" for
  // a draft or a scheduled send.
  assert.match(text, /Draft created/);
  assert.match(text, /Scheduled in Klaviyo/);
  assert.match(text, /Needs checking/);
  assert.equal((text.match(/Results start once Klaviyo confirms the send/g) || []).length, 3);
  assert.match(text, /reports this as sent but not when/);

  assert.match(text, /Program-level results haven't started yet/);
  assert.doesNotMatch(text, /range crosses zero|What BeaconAI added|Received campaigns/);
  assert.doesNotMatch(text, /Invalid Date|NaN|day \d+ of/);
});
