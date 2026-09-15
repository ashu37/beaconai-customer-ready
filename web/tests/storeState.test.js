import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import React from "react";
import { act, cleanup, fireEvent, render } from "@testing-library/react";

// Store state against the REAL app (merchant walkthrough #1, #6, #26): selecting
// the store already open changes nothing, a different store never shows the
// previous store's data, and "not loaded yet" is never presented as "empty".
const require = createRequire(import.meta.url);
const { presentEngineRun } = require("../../api/src/services/engineRunPresenter.js");

const STORE_A = "store-a.myshopify.com";
const STORE_B = "store-b.myshopify.com";
const WINBACK = "winback_dormant_cohort";
const DISCOUNT = "discount_dependency_hygiene";
const SYNCED_AT = "2026-09-08T12:00:00.000Z"; // midday UTC: the same day in any US or European zone

function briefing(runId, playId) {
  return presentEngineRun(
    { run_id: runId, abstain: { state: "publish", mode: null }, data_quality_flags: [], considered: [], watching: [],
      recommendations: [{ play_id: playId, evidence_source: "STORE_OBSERVED", confidence_label: "Emerging", audience: { size: 234 } }] },
    null, null, { analysedAt: "2026-09-10T12:00:00.000Z", currency: "USD" }
  );
}

// Each store's server, chosen by the store the request is made for.
let stores;
let hooks;
const calls = [];
const shopNow = () => apiModule.api.shopDomain;
const record = (name, fn) => async (...args) => { calls.push({ name, shop: shopNow(), args }); return fn(...args); };
const forShop = (key) => async (...args) => {
  const store = stores[shopNow()];
  if (hooks[key]) await hooks[key](shopNow());
  return store[key](...args);
};

const apiModule = await import("../src/api.js");
apiModule.api.setShopDomain(STORE_A);
Object.assign(apiModule.api, {
  health: record("health", () => ({ ok: true })),
  session: record("session", () => ({ ok: true, authenticated: true, shopDomain: shopNow() })),
  connectionStatus: record("connectionStatus", () => ({ ok: true, status: { shopify: { connected: true }, klaviyo: { connected: true } } })),
  testShopify: record("testShopify", () => ({ ok: true })),
  testKlaviyo: record("testKlaviyo", () => ({ ok: true })),
  brandContext: record("brandContext", () => ({ ok: true, brandContext: null })),
  brandEmailTemplate: record("brandEmailTemplate", () => ({ ok: true, configured: false })),
  klaviyoSender: record("klaviyoSender", () => ({ ok: true, sender: null })),
  getEngineInput: record("getEngineInput", forShop("input")),
  getLatestEngineRun: record("getLatestEngineRun", forShop("latest")),
  listCampaigns: record("listCampaigns", forShop("campaigns")),
  syncStatus: record("syncStatus", () => ({
    ok: true, ready: true, reasons: [],
    active: { syncRunId: 9, publishedAt: SYNCED_AT, coverage: { known: true, daysCovered: 240 } },
    latest: { syncRunId: 9, status: "complete" },
    analysis: { provenance: "verified", stale: false },
  })),
  getStatsSeries: record("getStatsSeries", () => ({ ok: true, weeks: [] })),
  getKlaviyoTemplates: record("getKlaviyoTemplates", () => ({
    ok: true, templates: [{ id: "beacon-winback-clean", source: "beacon", name: "Winback", subject: "Come back", previewText: "p", bodyH2: "h", bodyP1: "b", cta: "Shop" }],
  })),
  generateCopy: record("generateCopy", () => ({ ok: true, available: false })),
  previewCampaignHtml: record("previewCampaignHtml", () => ({ ok: true, html: "<p>email</p>", templateVersion: 1, renderFingerprint: "f" })),
  campaignDelivery: record("campaignDelivery", () => ({ ok: true, delivery: { state: "not_started" } })),
  getResults: record("getResults", forShop("results")),
  saveCampaign: record("saveCampaign", async (payload) => {
    if (hooks.save) await hooks.save(shopNow(), payload);
    const store = stores[shopNow()];
    const row = store.rows.find((r) => r.runId === payload.runId && r.playId === payload.playId);
    Object.assign(row, { draftEdits: payload.draftEdits ?? row.draftEdits });
    row.revision += 1;
    return { ok: true, campaign: { ...row } };
  }),
  syncShopify: record("syncShopify", () => ({
    ok: true, published: false, status: "reconnect_required",
    validationFailures: [{ code: "reconnect_for_history", action: "reconnect_shopify", message: "Reconnect Shopify so BeaconAI can read your full order history." }],
  })),
  runAtulEngine: record("runAtulEngine", () => ({ ok: true, accepted: true, job: { id: 1, status: "running" } })),
  getLatestAnalysisJob: record("getLatestAnalysisJob", async () => {
    if (hooks.job) return hooks.job(shopNow());
    return new Promise(() => {});
  }),
});

const { App } = await import("../src/App.jsx");

function freshStores() {
  const store = (runId, playId, products) => ({
    rows: [{ id: runId === "run-a" ? 1 : 2, runId, playId, status: "draft", revision: 1, templateId: "beacon-winback-clean", draftEdits: { subject: `${runId} subject` }, displayName: null }],
    input: () => ({ ok: true, input: { products: Array.from({ length: products }, (_, i) => ({ id: i })), customers: [], orders: [] } }),
    latest: () => ({ ok: true, found: true, presentedRun: briefing(runId, playId) }),
    campaigns() { return { ok: true, campaigns: this.rows.map((r) => ({ ...r })) }; },
    results: () => ({ ok: true, results: [], loadedAt: "2026-09-10T12:00:00.000Z" }),
  });
  return { [STORE_A]: store("run-a", WINBACK, 35), [STORE_B]: store("run-b", DISCOUNT, 12) };
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function settle(ms = 150) { await act(async () => { await sleep(ms); }); }
const text = () => document.body.textContent || "";
const button = (pred) => [...document.querySelectorAll("button")].find((b) => pred((b.textContent || "").trim()));
async function click(el, ms = 250) { assert.ok(el, "element to click exists"); await act(async () => { el.click(); await sleep(ms); }); }
const goTo = (page, ms = 300) => click(button((t) => t.startsWith(page)), ms);
const count = (name) => calls.filter((c) => c.name === name).length;
const subject = () => [...document.querySelectorAll("label.review-field")]
  .find((l) => (l.querySelector(".review-field-label")?.textContent || "").startsWith("Subject"))
  ?.querySelector("input");

async function mount() {
  await act(async () => { render(React.createElement(App)); await sleep(50); });
  await settle(300);
}

async function useStore(domain, ms = 250) {
  await goTo("Settings");
  const input = document.querySelector("#shop-domain");
  await act(async () => { fireEvent.change(input, { target: { value: domain } }); });
  await click(button((t) => t === "Use store"), ms);
}

test.beforeEach(() => {
  calls.length = 0;
  hooks = {};
  stores = freshStores();
  localStorage.clear();
  apiModule.api.setShopDomain(STORE_A);
});
test.afterEach(() => cleanup());

test("selecting the store that is already open changes nothing", async () => {
  await mount();
  await goTo("Campaigns");
  assert.equal(document.querySelectorAll("button.rail-row").length, 1);
  const reads = { latest: count("getLatestEngineRun"), campaigns: count("listCampaigns") };

  await useStore(STORE_A);
  await goTo("Campaigns");
  assert.equal(document.querySelectorAll("button.rail-row").length, 1, "the campaign is still there");
  assert.doesNotMatch(text(), /Approve a play in Briefing to start/);
  await goTo("Briefing");
  assert.match(text(), /Bring back lapsed customers/, "the briefing is still there");
  assert.equal(count("getLatestEngineRun"), reads.latest, "nothing was reloaded");
  assert.equal(count("listCampaigns"), reads.campaigns);
});

test("a different store shows its own loading state, never the previous store's data", async () => {
  await mount();
  assert.match(text(), /Bring back lapsed customers/);

  let releaseB;
  hooks.latest = (shop) => (shop === STORE_B ? new Promise((resolve) => { releaseB = resolve; }) : null);
  await useStore(STORE_B, 100);

  assert.equal(apiModule.api.shopDomain, STORE_B);
  assert.doesNotMatch(text(), /Bring back lapsed customers/, "store A's briefing is gone");
  assert.doesNotMatch(text(), /run-a subject/);
  assert.match(text(), /Loading your briefing/);
  const leakedToB = calls.filter((c) => c.shop === STORE_B && c.name === "saveCampaign");
  assert.equal(leakedToB.length, 0);

  await act(async () => { releaseB(); await sleep(300); });
  await settle(200);
  assert.match(text(), /Reduce discount dependency/, "store B's own briefing");
  assert.doesNotMatch(text(), /Bring back lapsed customers/);
});

test("an edit waiting to save is written to its own store before the switch", async () => {
  await mount();
  await goTo("Campaigns");
  await settle(200);
  await act(async () => { fireEvent.change(subject(), { target: { value: "Store A, edited" } }); });

  await useStore(STORE_B, 300); // well inside the 600 ms debounce
  const save = calls.find((c) => c.name === "saveCampaign" && c.args[0].draftEdits?.subject === "Store A, edited");
  assert.ok(save, "the pending edit was saved");
  assert.equal(save.shop, STORE_A, "to the store it was typed in");
  assert.equal(stores[STORE_B].rows[0].draftEdits.subject, "run-b subject", "store B was not written");
});

test("Results and Campaigns say they are loading until their data arrives", async () => {
  let releaseResults;
  hooks.results = () => new Promise((resolve) => { releaseResults = resolve; });
  await mount();
  await goTo("Results", 100);
  assert.doesNotMatch(text(), /Results appear after your first campaign/, "not loaded is not empty");
  assert.match(text(), /Loading results/);
  await act(async () => { releaseResults(); await sleep(200); });
  assert.match(text(), /Results appear after your first campaign/, "now it really is empty");

  cleanup();
  let releaseCampaigns;
  hooks = { campaigns: () => new Promise((resolve) => { releaseCampaigns = resolve; }) };
  await mount();
  await goTo("Campaigns", 100);
  assert.doesNotMatch(text(), /Approve a play in Briefing to start/);
  assert.match(text(), /Loading your campaigns/);
  await act(async () => { releaseCampaigns(); await sleep(300); });
  assert.equal(document.querySelectorAll("button.rail-row").length, 1);
});

test("store totals show their values at once, never a count-up from zero", async () => {
  await mount();
  const products = [...document.querySelectorAll(".metric-tile")].find((tile) => /Products/.test(tile.textContent));
  assert.match(products?.textContent || "", /35/);
});

test("a sync started from Settings reports there, and says what is still on screen", async () => {
  await mount();
  await goTo("Settings");
  await click(button((t) => t === "Refresh Shopify now"), 400);
  const panel = document.querySelector(".sync-progress");
  assert.ok(panel, "the sync result is shown on Settings, where it was started");
  assert.match(panel.textContent, /Reconnect Shopify so BeaconAI can read your full order history/);
  assert.match(panel.textContent, /still use your last successful sync, from Sep 8, 2026/);
});

test("re-running analysis says it analyses saved data, not latest orders", async () => {
  await mount();
  await click(button((t) => t === "Re-run analysis"), 300);
  assert.match(text(), /Analysing your saved store data from Sep 8, 2026/);
  assert.doesNotMatch(text(), /Refreshing with your latest orders/);
});

test("clearing the store also clears it from the URL", () => {
  apiModule.api.setShopDomain(STORE_A);
  assert.match(window.location.search, /shop=store-a/);
  apiModule.api.setShopDomain("");
  assert.doesNotMatch(window.location.search, /shop=/);
  apiModule.api.setShopDomain(STORE_A);
});

test("an analysis started for one store never reads or caches another store's briefing", async () => {
  await mount();
  const cacheA = () => JSON.parse(localStorage.getItem(`beaconai:${STORE_A}:latest-briefing`) || "null")?.presentedRun?.run_id;
  assert.equal(cacheA(), "run-a");

  let finishJob;
  hooks.job = () => new Promise((resolve) => { finishJob = () => resolve({ ok: true, job: { id: 1, status: "complete", runId: "run-a" } }); });
  await click(button((t) => t === "Re-run analysis"), 200);
  assert.ok(finishJob, "store A's analysis is waiting on its job");

  await useStore(STORE_B, 300);
  const bReadsBefore = calls.filter((c) => c.name === "getLatestEngineRun" && c.shop === STORE_B).length;
  hooks.job = null;
  await act(async () => { finishJob(); await sleep(400); });
  await settle(300);

  assert.equal(
    calls.filter((c) => c.name === "getLatestEngineRun" && c.shop === STORE_B).length,
    bReadsBefore,
    "store A's finished analysis did not read the newly open store's briefing",
  );
  assert.equal(cacheA(), "run-a", "store A's cache still holds store A's briefing");

  // Back to A, with its server slow: store B's briefing never appears while it
  // loads, and A's own briefing is what arrives.
  hooks.latest = (shop) => (shop === STORE_A ? sleep(600) : null);
  await useStore(STORE_A, 150);
  assert.doesNotMatch(text(), /Reduce discount dependency/);
  await settle(900);
  assert.doesNotMatch(text(), /Reduce discount dependency/);
  assert.match(text(), /Bring back lapsed customers/);
});

test("a save that already failed keeps the store from switching and the text on screen", async () => {
  await mount();
  await goTo("Campaigns");
  await settle(200);
  hooks.save = () => { throw new Error("Server unavailable"); };
  await act(async () => { fireEvent.change(subject(), { target: { value: "Store A, not saved" } }); });
  await settle(900); // the debounced save has run and failed

  await useStore(STORE_B, 300);
  assert.equal(apiModule.api.shopDomain, STORE_A, "the store did not switch");
  assert.match(text(), /changes that didn't save, so the store wasn't switched/);

  hooks.save = null;
  await goTo("Campaigns");
  assert.equal(subject()?.value, "Store A, not saved", "the unsaved text is still there to retry");
});
