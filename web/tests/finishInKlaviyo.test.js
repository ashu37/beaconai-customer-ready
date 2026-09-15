import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import React from "react";
import { act, cleanup, fireEvent, render } from "@testing-library/react";

// "Finish design in Klaviyo" against the REAL app: a store without a BeaconAI
// design gets suggested messaging and a draft with no preview; a store with one
// can choose either; the handoff keeps its save checks; and after handoff the
// merchant is told what to do in Klaviyo, with the retained copy called the
// handoff suggestion.
const require = createRequire(import.meta.url);
const { presentEngineRun } = require("../../api/src/services/engineRunPresenter.js");

const SHOP = "acme-k.myshopify.com";
const WINBACK = "winback_dormant_cohort";
const DISCOUNT = "discount_dependency_hygiene";

function card(playId) {
  return {
    play_id: playId,
    evidence_class: "directional",
    evidence_source: "STORE_OBSERVED",
    confidence_label: "Emerging",
    audience: { size: 238 },
    measurement: { metric: "reactivation_rate", observed_effect: -0.2, n: 107, primary_window: "L56" },
    revenue_range: { p10: 400, p50: 4500, p90: 4500, source: "blend", suppressed: false },
  };
}
const RUN_B = presentEngineRun(
  { run_id: "run-b", abstain: { state: "publish", mode: null }, data_quality_flags: [], recommendations: [card(WINBACK), card(DISCOUNT)], considered: [], watching: [] },
  null, null, { analysedAt: "2026-09-14T05:07:00.000Z", currency: "USD" }
);

// A small campaign store with the server's real rules: unique per (run, play),
// and an update must quote the current revision.
let rows;
let hooks;
let designConfigured = false;
let delivery = { state: "not_started" };
let original = {};
const calls = [];
const record = (name, fn) => async (...args) => { calls.push({ name, args }); return fn(...args); };
const clone = (value) => JSON.parse(JSON.stringify(value));

function conflict(row) {
  return Object.assign(new Error("Campaign changed"), { status: 409, conflict: "revision", campaign: clone(row) });
}

async function saveCampaign(payload) {
  if (hooks.beforeSave) await hooks.beforeSave(payload);
  const existing = rows.find((r) => r.runId === payload.runId && r.playId === payload.playId);
  if (existing) {
    if (Number(payload.expectedRevision) !== existing.revision) throw conflict(existing);
    for (const field of ["status", "templateId", "draftEdits", "destinationUrl", "displayName", "holdoutPct", "klaviyoCampaignId"]) {
      if (payload[field] !== undefined) existing[field] = payload[field];
    }
    existing.revision += 1;
    return { ok: true, campaign: clone(existing) };
  }
  const created = {
    id: Math.max(0, ...rows.map((r) => r.id)) + 1,
    runId: payload.runId, playId: payload.playId, status: payload.status || "draft",
    revision: 1, templateId: payload.templateId || null, draftEdits: payload.draftEdits || null,
    displayName: payload.displayName || null,
  };
  rows.push(created);
  return { ok: true, campaign: clone(created) };
}

const apiModule = await import("../src/api.js");
apiModule.api.setShopDomain(SHOP);
Object.assign(apiModule.api, {
  health: record("health", () => ({ ok: true })),
  session: record("session", () => ({ ok: true, authenticated: true, shopDomain: SHOP })),
  connectionStatus: record("connectionStatus", () => ({ ok: true, status: { shopify: { connected: true }, klaviyo: { connected: true } } })),
  testShopify: record("testShopify", () => ({ ok: true })),
  testKlaviyo: record("testKlaviyo", () => ({ ok: true })),
  brandContext: record("brandContext", () => ({ ok: true, brandContext: null })),
  // Per test: with or without a BeaconAI design.
  brandEmailTemplate: record("brandEmailTemplate", () => (designConfigured
    ? { ok: true, configured: true, active: { version: 1 } }
    : { ok: true, configured: false })),
  klaviyoSender: record("klaviyoSender", () => ({ ok: true, sender: null })),
  getEngineInput: record("getEngineInput", () => ({ ok: true, input: null })),
  getLatestEngineRun: record("getLatestEngineRun", () => ({ ok: true, found: true, presentedRun: RUN_B })),
  listCampaigns: record("listCampaigns", () => ({ ok: true, campaigns: clone(rows) })),
  syncStatus: record("syncStatus", () => ({
    ok: true, ready: true, reasons: [],
    active: { syncRunId: 9, publishedAt: "2026-09-08T22:40:00.000Z", coverage: { known: true, daysCovered: 120 } },
    latest: { syncRunId: 9, status: "published" },
    analysis: { runId: "run-b", provenance: "verified", stale: false },
  })),
  getStatsSeries: record("getStatsSeries", () => ({ ok: true, weeks: [] })),
  getKlaviyoTemplates: record("getKlaviyoTemplates", () => ({
    ok: true,
    templates: [{ id: "beacon-winback-clean", source: "beacon", name: "Winback", subject: "Come back", previewText: "p", bodyH2: "h", bodyP1: "b", cta: "Shop" }],
  })),
  generateCopy: record("generateCopy", () => ({ ok: true, available: false })),
  previewCampaignHtml: record("previewCampaignHtml", async (draft) => {
    if (hooks.beforePreview) await hooks.beforePreview(draft);
    return { ok: true, html: `<p>${draft.subject}</p>`, templateVersion: 1, renderFingerprint: `f-${draft.id}` };
  }),
  previewCampaignAudience: record("previewCampaignAudience", async (draft) => {
    if (hooks.beforeAudience) await hooks.beforeAudience(draft);
    const row = rows.find((r) => String(r.id) === String(draft.id));
    const pct = row?.holdoutPct ?? 0.1;
    const held = Math.round(413 * pct);
    return { ok: true, audience: { count: 413, recipients: [], materialized: true }, holdout: { treated: 413 - held, held, pct }, originRunId: draft.run_id };
  }),
  campaignDelivery: record("campaignDelivery", () => ({ ok: true, delivery: clone(delivery) })),
  campaignOriginal: record("campaignOriginal", () => ({ ok: true, ...clone(original) })),
  saveCampaign: record("saveCampaign", saveCampaign),
  createSendPackage: record("createSendPackage", async (payload) => {
    if (hooks.beforeHandoff) await hooks.beforeHandoff(payload);
    delivery = {
      state: "created", providerCampaignId: "K1",
      providerCampaignUrl: "https://www.klaviyo.com/campaign/K1/wizard/1",
    };
    const row = rows.find((r) => String(r.id) === String(payload.campaignId));
    Object.assign(row, {
      frozen: true, frozenAt: "2026-09-15T12:00:00.000Z", deliveryState: "created", klaviyoCampaignId: "K1",
      handoffMode: payload.handoffMode || "rendered_email", providerCampaignName: "BeaconAI - Bring back lapsed customers",
      approvedCopy: { subject: payload.subject, previewText: payload.previewText, bodyH2: payload.bodyH2, bodyP1: payload.bodyP1, cta: payload.cta },
    });
    return { ok: true, list: { data: { id: "L" } }, klaviyoCampaign: { data: { id: "K1" } }, campaign_record: clone(row) };
  }),
});

const { App } = await import("../src/App.jsx");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function settle(ms = 150) { await act(async () => { await sleep(ms); }); }
const text = () => document.body.textContent || "";
const button = (pred) => [...document.querySelectorAll("button")].find((b) => pred((b.textContent || "").trim()));
async function click(el, ms = 250) { assert.ok(el, "element to click exists"); await act(async () => { el.click(); await sleep(ms); }); }
const saves = () => calls.filter((c) => c.name === "saveCampaign").map((c) => c.args[0]);
const handoffs = () => calls.filter((c) => c.name === "createSendPackage").map((c) => c.args[0]);
const previews = () => calls.filter((c) => c.name === "previewCampaignHtml");
const messaging = () => document.querySelector(".suggested-messaging");
const field = (label, tag = "input") => [...document.querySelectorAll("label.review-field")]
  .find((l) => (l.querySelector(".review-field-label")?.textContent || "").startsWith(label))
  ?.querySelector(tag);

async function mount() {
  await act(async () => {
    render(React.createElement(App));
    await sleep(50);
  });
  await settle(300);
}
async function openCampaigns() {
  await click(button((t) => t.startsWith("Campaigns")), 300);
  await settle(200);
}

const campaignRow = (fields = {}) => ({
  id: 4, runId: "run-b", playId: WINBACK, status: "draft", revision: 1, templateId: "beacon-winback-clean",
  draftEdits: { subject: "It's been a little while", previewText: "Take another look around." },
  destinationUrl: "https://acme.example/collections/all",
  holdoutPct: 0.1, deliveryState: "not_started", ...fields,
});

const copied = [];
test.beforeEach(() => {
  calls.length = 0;
  copied.length = 0;
  hooks = {};
  designConfigured = false;
  delivery = { state: "not_started" };
  original = {};
  localStorage.clear();
  apiModule.api.setShopDomain(SHOP);
  window.confirm = () => true;
  Object.defineProperty(window.navigator, "clipboard", {
    configurable: true,
    value: { writeText: async (value) => { copied.push(value); } },
  });
});
test.afterEach(() => cleanup());

async function reviewAndApprove() {
  await click(button((t) => t === "Continue to audience"), 500);
  await click(button((t) => t === "Review draft"), 900);
  assert.match(document.querySelector(".step.current")?.textContent || "", /Review & create draft/);
}

test("without a BeaconAI design: suggested messaging to copy, and a draft with no preview", async () => {
  rows = [campaignRow()];
  await mount();
  await openCampaigns();

  assert.match(text(), /Email design: finish in Klaviyo/);
  assert.ok(!document.querySelector(".handoff-mode-choice"), "no choice to make without a design");
  assert.ok(messaging(), "suggested messaging replaces the preview");
  assert.match(messaging().textContent, /Suggested messaging/);
  assert.match(messaging().textContent, /The email your customers receive is the one you finish in Klaviyo/);
  assert.doesNotMatch(text(), /Rendered email preview|Handoff email/);

  // Every suggestion can be copied; empty ones are left out.
  const rowsShown = [...messaging().querySelectorAll(".suggested-messaging-row dt")].map((dt) => dt.textContent);
  assert.ok(rowsShown.includes("Subject") && rowsShown.includes("Preview text") && rowsShown.includes("Button link"), rowsShown.join());
  await click(messaging().querySelector('button[aria-label="Copy subject"]'), 50);
  assert.deepEqual(copied, ["It's been a little while"]);
  assert.match(messaging().querySelector('button[aria-label="Copy subject"]').textContent, /Copied/);

  // Editing the messaging updates the suggestion, and nothing is rendered.
  await act(async () => { fireEvent.change(field("Subject"), { target: { value: "A new subject" } }); });
  await settle(900);
  assert.match(messaging().textContent, /A new subject/);

  await reviewAndApprove();
  assert.match(text(), /Finish in Klaviyo/);
  assert.match(text(), /Choose one of your templates/);
  assert.match(text(), /Check the sender and recipients/);
  assert.match(text(), /BeaconAI never sends email/);
  assert.match(text(), /Design: you choose a template in Klaviyo/);
  assert.match(text(), /Creates a Klaviyo draft with this audience, subject and preview text/);

  let savedRevision = null;
  hooks.beforeHandoff = () => { savedRevision = rows[0].revision; };
  await click(button((t) => t === "Create draft in Klaviyo"), 900);
  assert.equal(previews().length, 0, "no BeaconAI email was ever rendered");
  const [payload] = handoffs();
  assert.equal(payload.handoffMode, "klaviyo_design");
  assert.equal(payload.expectedRenderFingerprint, null);
  assert.equal(payload.expectedTemplateVersion, null);
  assert.equal(payload.expectedRevision, savedRevision, "the handoff quotes the campaign's saved revision");
  assert.equal(payload.subject, "A new subject");

  // After handoff: a verified link, the exact name beside it, and what to do next.
  const open = [...document.querySelectorAll("a")].find((a) => /Open draft in Klaviyo/.test(a.textContent));
  assert.equal(open?.getAttribute("href"), "https://www.klaviyo.com/campaign/K1/wizard/1");
  assert.match(text(), /In Klaviyo it's named “BeaconAI - Bring back lapsed customers”/);
  assert.match(text(), /Next, in Klaviyo: choose a template, finish the email, check the sender and recipients, then send it from Klaviyo/);
  assert.match(text(), /Status updates when your pilot contact checks Klaviyo/);
  assert.doesNotMatch(text(), /\bSent\b ·/);
});

test("with a BeaconAI design: the design is the default, and finishing in Klaviyo can be chosen", async () => {
  designConfigured = true;
  rows = [campaignRow()];
  await mount();
  await openCampaigns();
  await settle(900);

  const choice = document.querySelector(".handoff-mode-choice");
  assert.ok(choice, "the store has a design, so the merchant can choose");
  assert.equal(choice.querySelector('[aria-checked="true"]')?.textContent.startsWith("Use the"), true, "the design is selected by default");
  assert.ok(previews().length > 0, "the design's email is previewed as before");
  assert.ok(!messaging());

  await click(button((t) => t.startsWith("Finish design in Klaviyo")), 300);
  assert.ok(messaging(), "suggested messaging shown instead");
  const previewsBefore = previews().length;
  await act(async () => { fireEvent.change(field("Subject"), { target: { value: "Edited for Klaviyo" } }); });
  await settle(1200);
  assert.equal(previews().length, previewsBefore, "no rendering while finishing in Klaviyo");

  await reviewAndApprove();
  await click(button((t) => t === "Create draft in Klaviyo"), 900);
  assert.equal(handoffs()[0].handoffMode, "klaviyo_design");
  assert.equal(handoffs()[0].expectedRenderFingerprint, null);
});

test("with a BeaconAI design and no choice made, the handoff is the rendered email with its preview binding", async () => {
  designConfigured = true;
  rows = [campaignRow()];
  await mount();
  await openCampaigns();
  await settle(900);
  await reviewAndApprove();
  await settle(600);
  await click(button((t) => t === "Create draft in Klaviyo"), 900);
  const [payload] = handoffs();
  assert.equal(payload.handoffMode, "rendered_email");
  assert.ok(payload.expectedRenderFingerprint, "bound to the reviewed rendering");
  assert.equal(payload.expectedTemplateVersion, 1);
});

test("with a BeaconAI design, the rendered email still can't be handed off without its preview", async () => {
  designConfigured = true;
  rows = [campaignRow()];
  // The design's preview never renders.
  hooks.beforePreview = () => { throw new Error("Preview unavailable"); };
  await mount();
  await openCampaigns();
  await settle(900);
  await reviewAndApprove();
  await settle(600);
  await click(button((t) => t === "Create draft in Klaviyo"), 900);
  assert.equal(handoffs().length, 0, "refused before reaching the server");
  assert.match(text(), /Wait for the preview to load/);

  // The same campaign, finished in Klaviyo instead, needs no preview.
  await click(button((t) => t.endsWith("Edit email")), 300);
  await click(button((t) => t.startsWith("Finish design in Klaviyo")), 300);
  await click(button((t) => t === "Continue to audience"), 500);
  await click(button((t) => t === "Review draft"), 900);
  await click(button((t) => t === "Create draft in Klaviyo"), 900);
  assert.equal(handoffs().length, 1);
  assert.equal(handoffs()[0].handoffMode, "klaviyo_design");
});

test("finishing in Klaviyo still refuses a handoff whose last edit didn't save", async () => {
  rows = [campaignRow()];
  await mount();
  await openCampaigns();
  hooks.beforeSave = (payload) => { if (payload.draftEdits) throw new Error("Server unavailable"); };
  await act(async () => { fireEvent.change(field("Subject"), { target: { value: "This will not save" } }); });
  await click(button((t) => t === "Continue to audience"), 50);
  await click(button((t) => t === "Review draft"), 900);
  // Approval waits for saves and stays put when one fails, in either mode.
  assert.equal(handoffs().length, 0);
  assert.equal(rows[0].status, "draft");
  assert.match(text(), /haven't saved yet|didn't save|Not saved/);
});

test("a campaign finished in Klaviyo keeps its handoff suggestion, never called the sent email", async () => {
  rows = [campaignRow({
    id: 9, status: "approved", revision: 7, frozen: true, frozenAt: "2026-09-14T12:00:00.000Z",
    deliveryState: "created", klaviyoCampaignId: "K9", handoffMode: "klaviyo_design",
    providerCampaignName: "BeaconAI - Bring back lapsed customers",
    approvedCopy: { subject: "Handed-off subject", previewText: "Handed-off preview", cta: "Take a look" },
  })];
  delivery = { state: "created", providerCampaignId: "K9", providerCampaignUrl: "https://www.klaviyo.com/campaign/K9/wizard/1" };
  await mount();
  await openCampaigns();
  await settle(600);

  assert.match(document.querySelector(".step.current")?.textContent || "", /Review & create draft/);
  const suggestion = messaging();
  assert.ok(suggestion, "the handoff suggestion is shown");
  assert.match(suggestion.textContent, /Handoff suggestion/);
  assert.match(suggestion.textContent, /The email itself is finished in Klaviyo, and changes made there aren't shown here/);
  assert.match(suggestion.textContent, /Handed-off subject/);
  assert.doesNotMatch(text(), /Handoff email|Email handed to Klaviyo|Current email preview/);
  assert.ok(!button((t) => t === "Create draft in Klaviyo"), "no second draft");
  assert.equal(previews().length, 0);
});
