import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import React from "react";
import { act, cleanup, fireEvent, render } from "@testing-library/react";

// Campaign identity in the workspace, against the REAL app. A play id repeats
// across analyses; a campaign id does not. Two campaigns for the same play — an
// older draft and the current analysis's — must never share copy, saves,
// previews, approval or handoff (docs/CAMPAIGN_CONTINUITY_SPEC.md, step 2).
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
  // A store with a BeaconAI design: these tests cover the rendered-email handoff.
  brandEmailTemplate: record("brandEmailTemplate", () => ({ ok: true, configured: true, active: { version: 1 } })),
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
  previewCampaignAudience: record("previewCampaignAudience", (draft) => ({
    ok: true, audience: { count: 212, recipients: [], materialized: true }, originRunId: draft.run_id,
  })),
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

// An older draft (run A) and the current analysis's campaign (run B) for the same play.
function twoWinbackCampaigns() {
  return [
    { id: 1, runId: "run-a", playId: WINBACK, status: "draft", revision: 3, templateId: "beacon-winback-clean", draftEdits: { subject: "Older draft" }, displayName: "Winback (Sep 10)", audienceSize: 234 },
    { id: 4, runId: "run-b", playId: WINBACK, status: "draft", revision: 1, templateId: "beacon-winback-clean", draftEdits: { subject: "Current draft" } },
  ];
}

test.beforeEach(() => {
  calls.length = 0;
  hooks = {};
  localStorage.clear();
  apiModule.api.setShopDomain(SHOP);
});
test.afterEach(() => cleanup());

test("two campaigns for one play: editing and approving one never touches the other", async () => {
  rows = twoWinbackCampaigns();
  await mount();
  await openCampaigns();
  assert.equal(railRows().length, 2, "the older unfinished draft stays in the rail beside this analysis's campaign");
  assert.equal(subject()?.value, "Current draft");

  await openEarlier(/Winback \(Sep 10\)/);
  assert.ok(earlierRail(), "and is labelled as coming from an earlier analysis");
  assert.equal(subject()?.value, "Older draft", "its own copy, not the current campaign's");

  await type("Older draft, edited");
  await settle(900);
  const edit = saves().find((p) => p.draftEdits?.subject === "Older draft, edited");
  assert.ok(edit, "the edit saved");
  assert.equal(edit.runId, "run-a", "to the older campaign's run");
  assert.equal(edit.expectedRevision, 3, "quoting the older campaign's revision");

  await click(currentRail());
  assert.equal(subject()?.value, "Current draft", "the current campaign's copy is untouched");

  // Approve the OLDER campaign only.
  await click(earlierRail());
  await click(button((t) => t === "Continue to audience"));
  await click(button((t) => t === "Review draft"), 400);
  const approval = saves().find((p) => p.status === "approved");
  assert.equal(approval?.runId, "run-a");
  assert.equal(rows.find((r) => r.id === 4).status, "draft", "the current campaign was not approved");

  const readyGroup = [...document.querySelectorAll(".rail-group")].find((g) => /Ready for Klaviyo/.test(g.textContent));
  const reviewGroup = [...document.querySelectorAll(".rail-group")].find((g) => /Needs review/.test(g.textContent));
  assert.match(readyGroup?.textContent || "", /Earlier analysis/, "the older campaign is ready to send");
  assert.doesNotMatch(reviewGroup?.textContent || "", /Earlier analysis/);
  assert.match(reviewGroup?.textContent || "", /Bring back lapsed customers/, "the current one still needs review");
});

test("an edit still waiting to save when the merchant switches campaigns saves to its own campaign", async () => {
  rows = twoWinbackCampaigns();
  await mount();
  await openCampaigns();
  await openEarlier(/Winback \(Sep 10\)/);

  await type("Older, typed then switched away");
  // Switch before the 600 ms debounce fires.
  await click(currentRail(), 100);
  await settle(900);

  const edit = saves().find((p) => p.draftEdits?.subject === "Older, typed then switched away");
  assert.ok(edit, "the waiting edit was saved");
  assert.equal(edit.runId, "run-a", "to the campaign it was typed into, not the one now open");
  assert.equal(edit.expectedRevision, 3);
  assert.equal(rows.find((r) => r.id === 4).draftEdits.subject, "Current draft", "the open campaign was not overwritten");
  assert.equal(subject()?.value, "Current draft");
});

test("a save that resolves after switching campaigns stays with the campaign that made it", async () => {
  rows = twoWinbackCampaigns();
  await mount();
  await openCampaigns();
  await openEarlier(/Winback \(Sep 10\)/);

  let release;
  hooks.beforeSave = (payload) => (payload.runId === "run-a" ? new Promise((resolve) => { release = resolve; }) : null);
  await type("Older, slow save");
  await settle(700); // debounce fired; A's save is on the wire
  assert.ok(release, "A's save is in flight");

  await click(currentRail());
  assert.equal(subject()?.value, "Current draft");

  hooks.beforeSave = null;
  await act(async () => { release(); await sleep(100); });
  await settle(100);
  assert.equal(subject()?.value, "Current draft", "A's response did not land in B's editor");
  assert.equal(rows.find((r) => r.id === 4).revision, 1, "B was never written");

  // B's next save quotes B's revision, and A's next save quotes A's new one.
  await type("Current, edited");
  await settle(900);
  const bSave = saves().find((p) => p.draftEdits?.subject === "Current, edited");
  assert.equal(bSave.runId, "run-b");
  assert.equal(bSave.expectedRevision, 1);

  await click(earlierRail());
  assert.equal(subject()?.value, "Older, slow save");
  await type("Older, second edit");
  await settle(900);
  const aSave = saves().find((p) => p.draftEdits?.subject === "Older, second edit");
  assert.equal(aSave.runId, "run-a");
  assert.equal(aSave.expectedRevision, 4, "the revision A's own slow save returned");
});

test("a preview that resolves after switching campaigns is never shown or approved for the other", async () => {
  rows = twoWinbackCampaigns();
  await mount();
  await openCampaigns();

  let release;
  hooks.beforePreview = (draft) => (draft.id === "1" ? new Promise((resolve) => { release = resolve; }) : null);
  await openEarlier(/Winback \(Sep 10\)/);
  await settle(200);
  assert.ok(release, "A's preview is in flight");

  await click(currentRail(), 400);
  await act(async () => { release(); await sleep(150); });
  hooks.beforePreview = null;

  // Approve and hand off B. Its handoff must bind to B's own rendering.
  await click(button((t) => t === "Continue to audience"));
  await click(button((t) => t === "Review draft"), 500);
  await settle(300);
  await click(button((t) => t.startsWith("Create draft in Klaviyo")), 500);
  const handoff = calls.find((c) => c.name === "createSendPackage")?.args[0];
  assert.ok(handoff, "B was handed off");
  assert.equal(handoff.campaignId, "4");
  assert.equal(handoff.expectedRenderFingerprint, "f-4", "bound to B's rendering, not A's late one");
  assert.doesNotMatch(document.querySelector(".review-pane, .final-review")?.innerHTML || "", /Older draft/);
});

test("a conflict on one campaign leaves the other's saving and handoff unaffected", async () => {
  rows = twoWinbackCampaigns();
  await mount();
  await openCampaigns();
  await openEarlier(/Winback \(Sep 10\)/);

  // Someone else moved campaign 1 on.
  rows.find((r) => r.id === 1).revision = 9;
  await type("Older, will conflict");
  await settle(900);
  assert.match(text(), /Changed elsewhere/, "A reports its conflict");

  await click(currentRail());
  assert.doesNotMatch(document.querySelector(".review-pane")?.textContent || "", /Changed elsewhere/, "B does not inherit A's state");
  await type("Current, fine");
  await settle(900);
  assert.match(document.querySelector(".review-pane")?.textContent || "", /Saved/);

  await click(button((t) => t === "Continue to audience"));
  await click(button((t) => t === "Review draft"), 500);
  await settle(300);
  const approvedRevision = rows.find((r) => r.id === 4).revision;
  await click(button((t) => t.startsWith("Create draft in Klaviyo")), 500);
  const handoff = calls.find((c) => c.name === "createSendPackage")?.args[0];
  assert.ok(handoff, "B's handoff was not blocked by A's conflict");
  assert.equal(handoff.campaignId, "4");
  assert.equal(handoff.expectedRevision, approvedRevision, "the revision B was approved at");
});

test("the handoff and audience use the selected campaign's own run", async () => {
  rows = twoWinbackCampaigns();
  await mount();
  await openCampaigns();
  await openEarlier(/Winback \(Sep 10\)/);

  await click(button((t) => t === "Continue to audience"), 400);
  const audience = calls.filter((c) => c.name === "previewCampaignAudience").map((c) => c.args[0]).pop();
  assert.equal(audience?.run_id, "run-a", "the older campaign's audience, not the latest analysis's");
  assert.equal(audience?.play_id, WINBACK);

  await click(button((t) => t === "Review draft"), 500);
  await settle(300);
  await click(button((t) => t.startsWith("Create draft in Klaviyo")), 500);
  const handoff = calls.find((c) => c.name === "createSendPackage")?.args[0];
  assert.equal(handoff?.campaignId, "1");
  assert.equal(handoff?.run_id, "run-a");
  assert.equal(handoff?.play_id, WINBACK);
  assert.equal(handoff?.expectedRenderFingerprint, "f-1");
});

test("a reload after a re-run shows the right badges, and older approvals are kept", async () => {
  rows = [
    { id: 1, runId: "run-a", playId: WINBACK, status: "approved", revision: 5, templateId: "beacon-winback-clean", draftEdits: { subject: "Approved last week" }, displayName: "Winback (Sep 10)" },
    { id: 4, runId: "run-b", playId: DISCOUNT, status: "draft", revision: 1, templateId: "beacon-winback-clean", draftEdits: { subject: "Discount draft" } },
  ];
  localStorage.setItem(`beaconai:${SHOP}:latest-briefing`, JSON.stringify({ presentedRun: RUN_B }));
  await mount();

  assert.doesNotMatch(briefingRow(/Bring back lapsed customers/)?.textContent || "", /In Campaigns/, "last week's approval is not this analysis's");
  assert.match(briefingRow(/discount/i)?.textContent || "", /In Campaigns/, "this analysis's campaign is linked");

  await openCampaigns();
  assert.equal(railRows().length, 2, "this analysis's campaign and the older approved one, not yet handed off");
  assert.equal(subject()?.value, "Discount draft");

  await openEarlier(/Winback \(Sep 10\)/);
  const readyGroup = [...document.querySelectorAll(".rail-group")].find((g) => /Ready for Klaviyo/.test(g.textContent));
  assert.match(readyGroup?.textContent || "", /Earlier analysis/, "its approval was kept, not reset");
  assert.equal(saves().length, 0, "nothing was written just by loading");
});
