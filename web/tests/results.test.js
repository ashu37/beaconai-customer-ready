import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

// Ticket F, as the merchant sees it today: a campaign the provider hasn't
// confirmed is listed with its reason, and the withdrawn program comparison
// says it hasn't started instead of showing a number.
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
    program: { available: false, reason: "protocol_not_live", sinceDays: 90, campaigns: 1 },
    results: [
      { measurable: false, reason: "awaiting_send_confirmation", campaignId: 7, playId: "winback_dormant_cohort", sentAt: null },
    ],
  }),
});

const { App } = await import("../src/App.jsx");
test.afterEach(() => cleanup());

test("an unconfirmed campaign is listed with its reason, and no program figure is shown", async () => {
  await act(async () => {
    render(React.createElement(App));
    await new Promise((resolve) => setTimeout(resolve, 50));
  });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Results" }));
    await new Promise((resolve) => setTimeout(resolve, 50));
  });
  const text = document.body.textContent || "";

  assert.match(text, /Awaiting send confirmation/);
  assert.match(text, /Waiting for Klaviyo to confirm the send/);
  assert.match(text, /Program-level results haven't started yet/);
  assert.doesNotMatch(text, /range crosses zero|What BeaconAI added|Received campaigns/);
  assert.doesNotMatch(text, /Invalid Date|NaN/);
});
