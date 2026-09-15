import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import React from "react";
import { act, cleanup, fireEvent, render } from "@testing-library/react";

// The campaign workspace against the REAL app, through the three transitions
// that broke it on the deployed app (2026-09-14): a reload that paints a cached
// older briefing, a slow response for an older run, and a same-tab re-run while
// the merchant has edits waiting to save. Campaign identity and edits must
// survive each.
const require = createRequire(import.meta.url);
const { presentEngineRun } = require("../../api/src/services/engineRunPresenter.js");

const SHOP = "acme-c.myshopify.com";
const WINBACK = "winback_dormant_cohort";

function card(playId) {
  return {
    play_id: playId,
    evidence_class: "directional",
    evidence_source: "STORE_OBSERVED",
    confidence_label: "Emerging",
    audience: { size: 234 },
    measurement: { metric: "reactivation_rate", observed_effect: -0.2, n: 107, primary_window: "L56" },
    revenue_range: { p10: 400, p50: 4500, p90: 4500, source: "blend", suppressed: false },
  };
}
function presented(runId, analysedAt, playIds) {
  return presentEngineRun(
    { run_id: runId, abstain: { state: "publish", mode: null }, data_quality_flags: [], recommendations: playIds.map(card), considered: [], watching: [] },
    null, null, { analysedAt, currency: "USD" }
  );
}
// Older run: three plays. Newer run: two. "3 plays" vs "2 plays" tells them apart.
const RUN_A = presented("run-a", "2026-09-10T04:21:00.000Z", [WINBACK, "discount_dependency_hygiene", "cohort_journey_first_to_second"]);
const RUN_B = presented("run-b", "2026-09-14T05:07:00.000Z", [WINBACK, "discount_dependency_hygiene"]);

// What the stubbed server answers; each test sets its own.
let server;
const calls = [];
const record = (name, fn) => async (...args) => { calls.push({ name, args }); return fn(...args); };

const apiModule = await import("../src/api.js");
apiModule.api.setShopDomain(SHOP);
Object.assign(apiModule.api, {
  health: record("health", () => ({ ok: true })),
  session: record("session", () => ({ ok: true, authenticated: true, shopDomain: SHOP })),
  connectionStatus: record("connectionStatus", () => ({ ok: true, status: { shopify: { connected: true }, klaviyo: { connected: true } } })),
  testShopify: record("testShopify", () => ({ ok: true })),
  testKlaviyo: record("testKlaviyo", () => ({ ok: true })),
  brandContext: record("brandContext", () => ({ ok: true, brandContext: null })),
  brandEmailTemplate: record("brandEmailTemplate", () => ({ ok: true, configured: false })),
  klaviyoSender: record("klaviyoSender", () => ({ ok: true, sender: null })),
  getEngineInput: record("getEngineInput", () => ({ ok: true, input: null })),
  getLatestEngineRun: record("getLatestEngineRun", (...args) => server.latest(...args)),
  listCampaigns: record("listCampaigns", () => server.campaigns()),
  syncStatus: record("syncStatus", () => ({
    ok: true, ready: true, reasons: [],
    active: { syncRunId: 9, publishedAt: "2026-09-08T22:40:00.000Z", coverage: { known: true, daysCovered: 120 } },
    latest: { syncRunId: 9, status: "published" },
    analysis: { runId: "run-a", provenance: "verified", stale: false },
  })),
  getStatsSeries: record("getStatsSeries", () => ({ ok: true, weeks: [] })),
  getKlaviyoTemplates: record("getKlaviyoTemplates", () => ({
    ok: true,
    templates: [{ id: "beacon-winback-clean", source: "beacon", name: "Winback", subject: "Come back", previewText: "p", bodyH2: "h", bodyP1: "b", cta: "Shop" }],
  })),
  generateCopy: record("generateCopy", () => ({ ok: true, available: false })),
  previewCampaignHtml: record("previewCampaignHtml", () => ({ ok: true, html: "<p>email</p>", templateVersion: 1, renderFingerprint: "f1" })),
  previewCampaignAudience: record("previewCampaignAudience", () => ({ ok: true, count: 212 })),
  campaignDelivery: record("campaignDelivery", () => ({ ok: true, delivery: { state: "not_started" } })),
  saveCampaign: record("saveCampaign", (payload) => ({
    ok: true,
    campaign: { id: 7, runId: payload.runId, playId: payload.playId, revision: (payload.expectedRevision || 0) + 1, draftEdits: payload.draftEdits, status: payload.status || "draft" },
  })),
  runAtulEngine: record("runAtulEngine", () => ({ ok: true, accepted: true, job: { id: 5, status: "running" } })),
  getLatestAnalysisJob: record("getLatestAnalysisJob", () => ({ ok: true, job: { id: 5, status: "complete", runId: "run-b" } })),
});

const { App } = await import("../src/App.jsx");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function settle(ms = 150) { await act(async () => { await sleep(ms); }); }
const text = () => document.body.textContent || "";
const button = (pred) => [...document.querySelectorAll("button")].find((b) => pred((b.textContent || "").trim()));
const winbackRow = () => [...document.querySelectorAll("button.recommendation-row")].find((b) => /Bring back lapsed customers/.test(b.textContent));

test.beforeEach(() => {
  calls.length = 0;
  localStorage.clear();
  apiModule.api.setShopDomain(SHOP);
});
test.afterEach(() => cleanup());

async function mount() {
  await act(async () => {
    render(React.createElement(App));
    await sleep(50);
  });
  await settle(250);
}

test("control: a campaign on the run on screen shows as approved", async () => {
  server = {
    latest: () => ({ ok: true, found: true, presentedRun: RUN_A }),
    campaigns: () => ({ ok: true, campaigns: [{ id: 1, runId: "run-a", playId: WINBACK, status: "approved", revision: 4, templateId: "beacon-winback-clean" }] }),
  };
  await mount();
  assert.match(text(), /3 recommendations/);
  assert.match(winbackRow()?.textContent || "", /In Campaigns/, "the badge appears for this run's own campaign");
});

test("a reload that paints a cached older briefing re-binds campaigns when the server's run arrives", async () => {
  // The cache holds run A (with an approved winback campaign); the server's latest is run B.
  localStorage.setItem(`beaconai:${SHOP}:latest-briefing`, JSON.stringify({ presentedRun: RUN_A }));
  server = {
    latest: async () => { await sleep(80); return { ok: true, found: true, presentedRun: RUN_B }; },
    campaigns: () => ({ ok: true, campaigns: [{ id: 1, runId: "run-a", playId: WINBACK, status: "approved", revision: 4, templateId: "beacon-winback-clean" }] }),
  };
  await mount();
  await settle(300);

  assert.match(text(), /2 recommendations/, "the server's newer run replaced the cached paint");
  assert.doesNotMatch(winbackRow()?.textContent || "", /In Campaigns/, "run A's approval is not shown on run B's play");
  assert.ok(calls.filter((c) => c.name === "listCampaigns").length >= 2, "campaigns were re-read for the new run");
});

test("a slow campaign read for an older run cannot re-bind the newer briefing", async () => {
  // Reload: cached run A paints and its campaign read starts, slowly. The server's
  // run B arrives and is read quickly. Then run A's slow answer lands — it must be
  // dropped, or run A's approval reappears on run B's play.
  localStorage.setItem(`beaconai:${SHOP}:latest-briefing`, JSON.stringify({ presentedRun: RUN_A }));
  const approvedOnA = [{ id: 1, runId: "run-a", playId: WINBACK, status: "approved", revision: 4, templateId: "beacon-winback-clean" }];
  let campaignReads = 0;
  server = {
    latest: async () => { await sleep(60); return { ok: true, found: true, presentedRun: RUN_B }; },
    campaigns: async () => {
      campaignReads += 1;
      if (campaignReads === 1) await sleep(700); // the read started for run A
      return { ok: true, campaigns: approvedOnA };
    },
  };
  await mount();
  await settle(200);
  assert.match(text(), /2 recommendations/, "run B is on screen");
  assert.doesNotMatch(winbackRow()?.textContent || "", /In Campaigns/);

  await settle(900); // run A's slow read has now landed
  assert.equal(campaignReads, 2, "one read per run");
  assert.doesNotMatch(winbackRow()?.textContent || "", /In Campaigns/, "the late read for run A was ignored");
});

test("a same-tab re-run keeps an edit waiting to save attached to its original campaign", async () => {
  server = {
    latest: () => ({ ok: true, found: true, presentedRun: RUN_A }),
    campaigns: () => ({
      ok: true,
      campaigns: [{ id: 7, runId: "run-a", playId: WINBACK, status: "draft", revision: 2, templateId: "beacon-winback-clean", draftEdits: { subject: "Mine" } }],
    }),
  };
  await mount();

  // Open the campaign and start typing.
  await act(async () => { button((t) => t.startsWith("Campaigns")).click(); await sleep(300); });
  await settle(300);
  const subject = () => [...document.querySelectorAll("label.review-field")]
    .find((l) => (l.querySelector(".review-field-label")?.textContent || "").startsWith("Subject"))
    ?.querySelector("input");
  assert.equal(subject()?.value, "Mine", "the saved draft is open");
  await act(async () => { fireEvent.change(subject(), { target: { value: "Mine, edited" } }); });

  // Before the debounced save fires (600 ms), a re-run lands run B, whose own
  // campaign read has nothing for this play.
  server.latest = () => ({ ok: true, found: true, presentedRun: RUN_B });
  await act(async () => { button((t) => t.startsWith("Briefing")).click(); await sleep(50); });
  await act(async () => { button((t) => t === "Re-run analysis").click(); await sleep(150); });
  assert.match(text(), /2 recommendations/, "run B is on screen");

  await settle(900); // the debounced save has fired
  const saves = calls.filter((c) => c.name === "saveCampaign").map((c) => c.args[0]);
  const edit = saves.find((payload) => payload.draftEdits?.subject === "Mine, edited");
  assert.ok(edit, `the pending edit was saved (saves: ${JSON.stringify(saves)})`);
  assert.equal(edit.runId, "run-a", "to its original campaign's run, not the new briefing's");
  assert.equal(edit.playId, WINBACK);
  assert.equal(edit.expectedRevision, 2, "quoting the revision it was editing");

  await act(async () => { button((t) => t.startsWith("Campaigns")).click(); await sleep(300); });
  await settle(200);
  assert.equal(subject()?.value, "Mine, edited", "and the editor still holds the merchant's text");
});
