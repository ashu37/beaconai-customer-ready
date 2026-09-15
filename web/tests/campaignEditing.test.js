import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import React from "react";
import { act, cleanup, fireEvent, render } from "@testing-library/react";

// Campaign editing against the REAL app (merchant walkthrough #2–#5, #21): saves
// for one campaign are queued so they never conflict with each other, a genuine
// conflict offers recovery, approval waits for saves, holdout controls wait for
// the audience, and a handed-off campaign is locked and described as such.
const require = createRequire(import.meta.url);
const { presentEngineRun } = require("../../api/src/services/engineRunPresenter.js");

const SHOP = "acme-c.myshopify.com";
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
  brandEmailTemplate: record("brandEmailTemplate", () => ({ ok: true, configured: false })),
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
  campaignDelivery: record("campaignDelivery", () => ({ ok: true, delivery: { state: "not_started" } })),
  saveCampaign: record("saveCampaign", saveCampaign),
  createSendPackage: record("createSendPackage", () => ({ ok: true, template: { data: { id: "T" } }, list: { data: { id: "L" } }, klaviyoCampaign: { data: { id: "K" } } })),
});

const { App } = await import("../src/App.jsx");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function settle(ms = 150) { await act(async () => { await sleep(ms); }); }
const text = () => document.body.textContent || "";
const button = (pred) => [...document.querySelectorAll("button")].find((b) => pred((b.textContent || "").trim()));
async function click(el, ms = 250) { assert.ok(el, "element to click exists"); await act(async () => { el.click(); await sleep(ms); }); }
const railRows = () => [...document.querySelectorAll("button.rail-row")];
const earlierRail = () => railRows().find((b) => /Earlier analysis/.test(b.textContent));
const currentRail = (name = /Bring back lapsed customers/) => railRows().find((b) => name.test(b.textContent) && !/Earlier analysis/.test(b.textContent));
const briefingRow = (name) => [...document.querySelectorAll("button.recommendation-row")].find((b) => name.test(b.textContent));
const subject = () => [...document.querySelectorAll("label.review-field")]
  .find((l) => (l.querySelector(".review-field-label")?.textContent || "").startsWith("Subject"))
  ?.querySelector("input");
const saves = () => calls.filter((c) => c.name === "saveCampaign").map((c) => c.args[0]);

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

// An older campaign: an unfinished draft is already in the rail (step 3); a
// handed-off one is opened from Earlier campaigns.
async function openEarlier(name = /Bring back lapsed customers|Winback/) {
  const link = earlierRail() || [...document.querySelectorAll(".earlier-campaigns-list button")].find((b) => name.test(b.textContent));
  await click(link, 300);
  await settle(200);
}

async function type(value) {
  await act(async () => { fireEvent.change(subject(), { target: { value } }); });
}

const campaignRow = (fields = {}) => ({
  id: 4, runId: "run-b", playId: WINBACK, status: "draft", revision: 1, templateId: "beacon-winback-clean",
  draftEdits: { subject: "Current draft" }, holdoutPct: 0.1, deliveryState: "not_started", ...fields,
});
const field = (label, tag = "input") => [...document.querySelectorAll("label.review-field")]
  .find((l) => (l.querySelector(".review-field-label")?.textContent || "").startsWith(label))
  ?.querySelector(tag);
const slowSaves = (ms) => { hooks.beforeSave = () => sleep(ms); };

test.beforeEach(() => {
  calls.length = 0;
  hooks = {};
  localStorage.clear();
  apiModule.api.setShopDomain(SHOP);
  window.confirm = () => true;
});
test.afterEach(() => cleanup());

test("overlapping saves for one campaign are queued, each quoting the previous save's revision", async () => {
  rows = [campaignRow()];
  await mount();
  await openCampaigns();
  slowSaves(1500);

  await type("Edited subject");
  await settle(700); // the copy save is now on the wire, and stays there for 1.5 s
  // A destination change while it runs: its save fires ~600 ms later, before
  // the first returns. Sent concurrently, both quoted revision 1 and the second
  // came back "changed elsewhere" in a single tab.
  await act(async () => { fireEvent.change(field("Button destination"), { target: { value: "https://shop.example/new" } }); });
  await settle(3800); // the second save waits for the first, then takes its own 1.5 s

  assert.deepEqual(saves().map((p) => p.expectedRevision), [1, 2], "the second save quoted the revision the first returned");
  assert.doesNotMatch(text(), /Changed elsewhere/);
  assert.equal(rows[0].draftEdits.subject, "Edited subject");
  assert.equal(rows[0].destinationUrl, "https://shop.example/new");
  assert.equal(rows[0].revision, 3);
});

test("rapid holdout changes wait for the audience, and zero holdout shows as selected", async () => {
  rows = [campaignRow()];
  await mount();
  await openCampaigns();
  await click(button((t) => t === "Continue to audience"), 500);
  slowSaves(300);

  const select = () => document.querySelector(".holdout-controls select");
  await act(async () => { fireEvent.change(select(), { target: { value: "0.05" } }); await sleep(30); });
  assert.match(text(), /Updating the audience/);
  assert.equal(select().disabled, true, "no second choice while the first is being applied");
  const cont = button((t) => t === "Updating…");
  assert.ok(cont?.disabled, "Continue waits too");

  await settle(700);
  await click(button((t) => t === "Send to everyone"), 900);
  assert.equal(select().value, "0", "the dropdown shows the active choice");
  assert.match(select().selectedOptions[0].textContent, /None/);
  assert.doesNotMatch(text(), /Changed elsewhere/);
  assert.deepEqual(saves().map((p) => [p.holdoutPct, p.expectedRevision]), [[0.05, 1], [0, 2]]);
});

test("a genuine conflict stops queued saves and offers the latest version", async () => {
  rows = [campaignRow()];
  await mount();
  await openCampaigns();
  // Another session saved this campaign.
  Object.assign(rows[0], { revision: 5, draftEdits: { subject: "Saved elsewhere" } });

  await type("My edit");
  await settle(900);
  assert.match(text(), /Changed elsewhere/);
  const before = saves().length;

  await type("My second edit");
  await settle(900);
  assert.equal(saves().length, before, "nothing is written over the other session's edit");
  assert.equal(rows[0].draftEdits.subject, "Saved elsewhere");

  await click(button((t) => t === "Load the latest version"), 400);
  assert.equal(subject()?.value, "Saved elsewhere");
  assert.doesNotMatch(text(), /Changed elsewhere/);
  await type("Continuing from theirs");
  await settle(900);
  assert.equal(saves().at(-1).expectedRevision, 5);
  assert.equal(rows[0].draftEdits.subject, "Continuing from theirs");
});

test("approval waits for pending saves and stays in review if one fails", async () => {
  rows = [campaignRow()];
  await mount();
  await openCampaigns();
  await type("Typed just before approving");
  await click(button((t) => t === "Continue to audience"), 50);
  await click(button((t) => t === "Continue to send"), 900);
  const order = saves().map((p) => (p.status ? `status:${p.status}` : `edit:${p.draftEdits?.subject}`));
  assert.deepEqual(order, ["edit:Typed just before approving", "status:approved"], "the edit saved before the approval");
  assert.equal(rows[0].status, "approved");

  cleanup();
  calls.length = 0;
  rows = [campaignRow()];
  await mount();
  await openCampaigns();
  hooks.beforeSave = (payload) => { if (payload.draftEdits) throw new Error("Server unavailable"); };
  await type("This will not save");
  await click(button((t) => t === "Continue to audience"), 50);
  await click(button((t) => t === "Continue to send"), 900);
  assert.equal(rows[0].status, "draft", "not approved");
  assert.match(document.querySelector(".step.current")?.textContent || "", /Review audience/);
  assert.match(text(), /haven't saved yet/);
});

test("a handed-off campaign is locked and called handed off; a sent one is called sent", async () => {
  for (const [deliveryState, wording, notWording] of [
    ["awaiting_send", /handed off to Klaviyo/, /was sent/],
    ["sent", /was sent/, /handed off/],
  ]) {
    cleanup();
    rows = [
      campaignRow(),
      { id: 9, runId: "run-a", playId: WINBACK, status: "approved", revision: 7, templateId: "beacon-winback-clean", draftEdits: { subject: "Handed off" }, displayName: "Winback (Sep 10)", frozen: true, klaviyoCampaignId: "K1", deliveryState },
    ];
    await mount();
    await openCampaigns();
    await openEarlier(/Winback \(Sep 10\)/);
    assert.match(text(), wording);
    assert.doesNotMatch(text(), /already sent/);
    assert.doesNotMatch(document.querySelector(".toast")?.textContent || "", notWording);

    if (!/Edit email/.test(document.querySelector(".step.current")?.textContent || "")) {
      await click(button((t) => t.endsWith("Edit email")), 300);
    }
    assert.equal(subject()?.disabled, true, "fields are disabled, not only styled");
    assert.ok(!button((t) => t === "Change starting copy"));
    assert.ok(!button((t) => t === "Rewrite"));
    assert.ok(!button((t) => t === "Restore suggested"));
    assert.ok(!button((t) => t === "Back to review"));
  }
});

test("a cleared optional paragraph stays empty through saving, reloading and the preview", async () => {
  rows = [campaignRow({ copy: { copy: { subject_variants: ["Agent subject"], support: "Agent support paragraph", body: "Agent body" } } })];
  await mount();
  await openCampaigns();
  await act(async () => { fireEvent.change(field("Support", "textarea"), { target: { value: "" } }); });
  await settle(900);
  assert.deepEqual(rows[0].draftEdits, { subject: "Current draft", bodyP2: "" });

  cleanup();
  calls.length = 0;
  await mount();
  await openCampaigns();
  await settle(400);
  assert.equal(field("Support", "textarea")?.value, "");
  const previews = calls.filter((c) => c.name === "previewCampaignHtml").map((c) => c.args[0].bodyP2);
  assert.ok(previews.length && previews.every((v) => v === ""), `previews: ${JSON.stringify(previews)}`);
});

test("the audience headline states assignment, not delivery; counts wait for campaigns", async () => {
  rows = [campaignRow()];
  await mount();
  await openCampaigns();
  await click(button((t) => t === "Continue to audience"), 500);
  assert.match(text(), /are assigned to the email group\. Klaviyo confirms actual delivery\./);
  assert.doesNotMatch(text(), /will receive this/);

  cleanup();
  let release;
  apiModule.api.listCampaigns = record("listCampaigns", () => new Promise((resolve) => { release = () => resolve({ ok: true, campaigns: clone(rows) }); }));
  await mount();
  const tile = (label) => [...document.querySelectorAll(".metric-tile")].find((t) => t.textContent.startsWith(label))?.textContent;
  assert.match(tile("Needs review") || "", /—/, "unknown, not zero");
  await act(async () => { release(); await sleep(300); });
  assert.match(tile("Needs review") || "", /1/);
  apiModule.api.listCampaigns = record("listCampaigns", () => ({ ok: true, campaigns: clone(rows) }));
});
