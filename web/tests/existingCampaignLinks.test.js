import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import React from "react";
import { act, cleanup, fireEvent, render } from "@testing-library/react";

// Campaign continuity, step 3, against the REAL app: a new analysis's briefing
// card links to the merchant's existing campaign for that play, and an updated
// draft is made only when they ask for one (docs/CAMPAIGN_CONTINUITY_SPEC.md).
const require = createRequire(import.meta.url);
const { presentEngineRun } = require("../../api/src/services/engineRunPresenter.js");

const SHOP = "acme-c.myshopify.com";
const WINBACK = "winback_dormant_cohort";
const DISCOUNT = "discount_dependency_hygiene";
const JOURNEY = "cohort_journey_first_to_second";

function card(playId, size = 238) {
  return {
    play_id: playId,
    evidence_class: "directional",
    evidence_source: "STORE_OBSERVED",
    confidence_label: "Emerging",
    audience: { size },
    measurement: { metric: "reactivation_rate", observed_effect: -0.2, n: 107, primary_window: "L56" },
    revenue_range: { p10: 400, p50: 4500, p90: 4500, source: "blend", suppressed: false },
  };
}
// The latest analysis recommends winback and discount only.
const RUN_B = presentEngineRun(
  { run_id: "run-b", abstain: { state: "publish", mode: null }, data_quality_flags: [], recommendations: [card(WINBACK), card(DISCOUNT)], considered: [], watching: [] },
  null, null, { analysedAt: "2026-09-14T18:00:00.000Z", currency: "USD" }
);
// Midday UTC, so the calendar day is the same in any US or European time zone.
const RUN_A_AT = "2026-09-10T12:00:00.000Z";

let rows;
let hooks;
let delivery;
const calls = [];
const record = (name, fn) => async (...args) => { calls.push({ name, args }); return fn(...args); };
const clone = (value) => JSON.parse(JSON.stringify(value));

async function saveCampaign(payload) {
  if (hooks.beforeSave) await hooks.beforeSave(payload);
  const existing = rows.find((r) => r.runId === payload.runId && r.playId === payload.playId);
  if (existing) {
    if (Number(payload.expectedRevision) !== existing.revision) {
      throw Object.assign(new Error("Campaign changed"), { status: 409, conflict: "revision", campaign: clone(existing) });
    }
    for (const field of ["status", "templateId", "draftEdits", "destinationUrl", "displayName"]) {
      if (payload[field] !== undefined) existing[field] = payload[field];
    }
    existing.revision += 1;
    return { ok: true, campaign: clone(existing) };
  }
  const created = { id: Math.max(0, ...rows.map((r) => r.id)) + 1, runId: payload.runId, playId: payload.playId, status: payload.status || "draft", revision: 1, templateId: payload.templateId || null, draftEdits: payload.draftEdits || null, displayName: payload.displayName || null };
  rows.push(created);
  return { ok: true, campaign: clone(created) };
}

// The server's replacement rules, in miniature.
async function createReplacementDraft(campaignId, { runId, expectedRevision }) {
  if (hooks.beforeReplace) await hooks.beforeReplace();
  const old = rows.find((r) => String(r.id) === String(campaignId));
  if (old.supersededById) return { ok: true, campaign: clone(rows.find((r) => r.id === old.supersededById)), previous: clone(old) };
  if (old.revision !== expectedRevision) {
    throw Object.assign(new Error("Campaign changed"), { status: 409, conflict: "revision", campaign: clone(old) });
  }
  const created = {
    id: Math.max(...rows.map((r) => r.id)) + 1, runId, playId: old.playId, status: "draft", revision: 1,
    templateId: old.templateId, draftEdits: clone(old.draftEdits), destinationUrl: old.destinationUrl,
    displayName: old.displayName, supersedesId: old.id, runAnalysedAt: RUN_B.generated_at,
  };
  rows.push(created);
  Object.assign(old, { supersededById: created.id, revision: old.revision + 1 });
  return { ok: true, campaign: clone(created), previous: clone(old) };
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
  previewCampaignHtml: record("previewCampaignHtml", (draft) => ({ ok: true, html: `<p>${draft.subject}</p>`, templateVersion: 1, renderFingerprint: `f-${draft.id}` })),
  previewCampaignAudience: record("previewCampaignAudience", () => ({ ok: true, audience: { count: 212, recipients: [], materialized: true } })),
  campaignDelivery: record("campaignDelivery", (id) => ({ ok: true, delivery: delivery[id] || { state: "not_started" } })),
  getResults: record("getResults", () => ({ ok: true, campaigns: [], program: null })),
  saveCampaign: record("saveCampaign", saveCampaign),
  createReplacementDraft: record("createReplacementDraft", createReplacementDraft),
});

const { App } = await import("../src/App.jsx");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function settle(ms = 150) { await act(async () => { await sleep(ms); }); }
const button = (pred) => [...document.querySelectorAll("button")].find((b) => pred((b.textContent || "").trim()));
async function click(el, ms = 250) { assert.ok(el, "element to click exists"); await act(async () => { el.click(); await sleep(ms); }); }
const detail = () => document.querySelector(".recommendation-detail")?.textContent || "";
const briefingRow = (name) => [...document.querySelectorAll("button.recommendation-row")].find((b) => name.test(b.textContent));
const railRows = () => [...document.querySelectorAll("button.rail-row")];
const subject = () => [...document.querySelectorAll("label.review-field")]
  .find((l) => (l.querySelector(".review-field-label")?.textContent || "").startsWith("Subject"))
  ?.querySelector("input");
const named = (name) => calls.filter((c) => c.name === name);

async function mount() {
  await act(async () => { render(React.createElement(App)); await sleep(50); });
  await settle(300);
}
async function goTo(page) { await click(button((t) => t.startsWith(page)), 300); await settle(200); }

function olderWinbackDraft(fields = {}) {
  return {
    id: 1, runId: "run-a", playId: WINBACK, status: "draft", revision: 3, templateId: "beacon-winback-clean",
    draftEdits: { subject: "My winback subject", bodyP2: "" }, destinationUrl: "https://shop.example/winback",
    displayName: "Bring back lapsed customers", audienceSize: 234, runAnalysedAt: RUN_A_AT, createdAt: RUN_A_AT,
    ...fields,
  };
}

test.beforeEach(() => {
  calls.length = 0;
  hooks = {};
  delivery = {};
  localStorage.clear();
  apiModule.api.setShopDomain(SHOP);
});
test.afterEach(() => cleanup());

test("an older draft is linked, never shown as approved, and nothing is copied until asked", async () => {
  rows = [olderWinbackDraft({ status: "approved" })];
  await mount();

  assert.doesNotMatch(briefingRow(/Bring back lapsed customers/)?.textContent || "", /In Campaigns/);
  assert.match(detail(), /You already have a draft for this play from your Sep 10 analysis/);
  assert.ok(!button((t) => t === "Add to Campaigns"), "no second, duplicate campaign by default");
  assert.equal(named("createReplacementDraft").length, 0, "loading the briefing copies nothing");
  assert.equal(named("saveCampaign").length, 0, "and changes nothing");

  await click(button((t) => t === "Continue draft"), 400);
  await settle(300);
  assert.match(document.querySelector(".step.current")?.textContent || "", /Review & create draft/, "an approved draft reopens where it was left");
  await click(button((t) => t.endsWith("Edit email")), 400);
  assert.equal(subject()?.value, "My winback subject", "Continue draft opens the existing campaign");
  assert.match(railRows()[0]?.textContent || "", /Earlier analysis/);
});

test("Create updated draft saves pending edits first, then opens an unapproved copy on the latest analysis", async () => {
  rows = [olderWinbackDraft({ status: "approved" })];
  await mount();
  await goTo("Campaigns");
  // An approved draft opens on its final step; go back to editing.
  await click(button((t) => t.endsWith("Edit email")), 400);
  // An edit whose save is still on the wire when the merchant goes to update
  // the draft: the copy must wait for it, or it copies the older text.
  hooks.beforeSave = () => sleep(2500);
  await act(async () => { fireEvent.change(subject(), { target: { value: "Edited just before updating" } }); });
  await goTo("Briefing");

  await click(button((t) => t === "Review latest recommendation"));
  assert.match(detail(), /Your draft\s*Sep 10 analysis · 234 customers/);
  assert.match(detail(), /Latest recommendation\s*Sep 14 analysis · 238 customers/);

  const create = button((t) => t === "Create updated draft");
  await act(async () => { create.click(); create.click(); await sleep(700); });
  await settle(2800);
  hooks.beforeSave = null;

  const order = calls.map((c) => c.name).filter((n) => n === "saveCampaign" || n === "createReplacementDraft");
  assert.deepEqual(order.slice(-2), ["saveCampaign", "createReplacementDraft"], "the pending edit saved before the copy was made");
  assert.equal(named("createReplacementDraft").length, 1, "a double click asks once");
  const [oldKey, request] = named("createReplacementDraft")[0].args;
  assert.equal(oldKey, "1");
  assert.equal(request.runId, "run-b");
  assert.equal(request.expectedRevision, 4, "the revision the flushed save returned");

  // The updated draft is open, unapproved, with the merchant's saved content.
  assert.equal(subject()?.value, "Edited just before updating");
  const groups = [...document.querySelectorAll(".rail-group")].map((g) => g.textContent);
  assert.equal(railRows().length, 1, "the replaced draft left the rail");
  assert.match(groups.join("|"), /Needs review/, "the updated draft must be reviewed and approved again");
  assert.doesNotMatch(groups.join("|"), /Ready for Klaviyo/);
  assert.match(document.querySelector(".earlier-campaigns")?.textContent || "", /replaced by an updated draft/);

  // The briefing now links the latest analysis's own campaign.
  await goTo("Briefing");
  assert.match(briefingRow(/Bring back lapsed customers/)?.textContent || "", /In Campaigns/);
});

test("a failed update leaves the existing draft exactly where it was", async () => {
  rows = [olderWinbackDraft()];
  hooks.beforeReplace = () => { throw new Error("Server unavailable"); };
  await mount();
  await click(button((t) => t === "Review latest recommendation"));
  await click(button((t) => t === "Create updated draft"), 500);

  assert.match(document.body.textContent, /The updated draft wasn't created. Your draft is unchanged./);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].supersededById, undefined);
  await goTo("Campaigns");
  assert.equal(railRows().length, 1);
  assert.equal(subject()?.value, "My winback subject");
});

test("a campaign in Klaviyo shows its status and link, with no way to duplicate it", async () => {
  rows = [olderWinbackDraft({ status: "approved", frozen: true, klaviyoCampaignId: "K1", deliveryState: "created" })];
  delivery = { 1: { state: "created", providerCampaignUrl: "https://www.klaviyo.com/campaign/K1/edit" } };
  await mount();
  await settle(300);

  assert.match(detail(), /Draft created · from your Sep 10 analysis/);
  const link = [...document.querySelectorAll(".recommendation-detail a")].find((a) => /Open in Klaviyo/.test(a.textContent));
  assert.equal(link?.getAttribute("href"), "https://www.klaviyo.com/campaign/K1/edit");
  assert.ok(!button((t) => t === "Add to Campaigns" || t === "Create updated draft" || t === "Continue draft"));
  await goTo("Campaigns");
  assert.equal(railRows().length, 0, "a handed-off campaign is listed under Earlier campaigns, not reopened as work");
});

test("a scheduled campaign with a scheduled time is shown as in Klaviyo, never as sent", async () => {
  // Klaviyo reports the SCHEDULED time where a sent campaign has its send time.
  const scheduledFor = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString();
  rows = [olderWinbackDraft({ status: "approved", frozen: true, klaviyoCampaignId: "K1", deliveryState: "scheduled", providerSentAt: scheduledFor })];
  delivery = { 1: { state: "scheduled", providerCampaignUrl: "https://www.klaviyo.com/campaign/K1/edit", providerSentAt: scheduledFor } };
  await mount();
  await settle(300);

  assert.doesNotMatch(detail(), /Sent|Measuring/, "not presented as sent");
  assert.match(detail(), /Scheduled in Klaviyo · from your Sep 10 analysis/);
  assert.ok(!button((t) => t === "Start a new campaign"), "no duplicate offered for a campaign that has not gone out");
  assert.ok(!button((t) => t === "View results"));
  assert.ok([...document.querySelectorAll(".recommendation-detail a")].some((a) => /Open in Klaviyo/.test(a.textContent)));
});

test("a sent campaign shows when it went out, links to results, and allows only an explicit new campaign", async () => {
  const sentAt = new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString();
  rows = [olderWinbackDraft({ status: "approved", frozen: true, klaviyoCampaignId: "K1", deliveryState: "sent", providerSentAt: sentAt })];
  await mount();

  const expected = new Date(sentAt).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  assert.match(detail(), new RegExp(`Sent ${expected} · Measuring`));
  assert.match(detail(), /A new campaign can reach customers who received the earlier send/);

  await click(button((t) => t === "View results"), 400);
  assert.ok(named("getResults").length >= 1, "Results opened");
  assert.match(window.location.search, /campaign=1/);

  await goTo("Briefing");
  await click(button((t) => t === "Start a new campaign"), 400);
  const created = named("saveCampaign").map((c) => c.args[0]).find((p) => p.runId === "run-b");
  assert.equal(created?.playId, WINBACK, "a new campaign on the latest analysis, only when asked");
});

test("a draft whose play left the briefing stays in Campaigns, labelled", async () => {
  rows = [{ id: 2, runId: "run-a", playId: JOURNEY, status: "draft", revision: 1, templateId: "beacon-winback-clean", draftEdits: { subject: "Journey draft" }, displayName: "Turn first-time buyers into repeat buyers", runAnalysedAt: RUN_A_AT, createdAt: RUN_A_AT }];
  await mount();
  await goTo("Campaigns");
  assert.equal(railRows().length, 1);
  assert.match(railRows()[0].textContent, /Not included in the latest analysis/);
  assert.match(document.querySelector(".workspace-pane")?.textContent || "", /Not included in the latest analysis/);
  assert.equal(subject()?.value, "Journey draft");
});

test("with no existing campaign the card offers the normal approve action", async () => {
  rows = [];
  await mount();
  assert.ok(button((t) => t === "Add to Campaigns"));
  assert.doesNotMatch(detail(), /You already have a draft/);
});
