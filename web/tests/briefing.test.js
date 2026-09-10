import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

import {
  briefingHeadline, dataStatusItems, evidenceChipItems, heldLaneEmptyText,
  holdsAreDataVolume, truncatedNote,
} from "../src/briefingPresentation.js";

// The briefing is fed by the REAL presenter over a run shaped like the stored
// local test-store run (Sep 8, 2026): three STORE_OBSERVED recommendations, held
// plays across different reasons, and a watched metric. Running the presenter
// here — rather than hand-writing its output — means a presenter/screen
// mismatch fails this test instead of reaching a merchant.
const require = createRequire(import.meta.url);
const { presentEngineRun } = require("../../api/src/services/engineRunPresenter.js");

function card(playId, metric, effect, n) {
  return {
    play_id: playId,
    evidence_class: "directional",
    evidence_source: "STORE_OBSERVED",
    confidence_label: "Emerging",
    audience: { size: 234 },
    measurement: { metric, observed_effect: effect, n, primary_window: "L56" },
    revenue_range: { p10: 422.54, p50: 4480.73, p90: 4480.73, source: "blend", suppressed: false },
  };
}

const engineRun = {
  run_id: "run-e",
  abstain: { state: "publish", mode: null },
  data_quality_flags: [],
  recommendations: [
    card("winback_dormant_cohort", "reactivation_rate", -0.205607, 107),
    card("discount_dependency_hygiene", "discount_dependency_hygiene_full_price_conversion_rate", 0.053333, 60528),
    card("cohort_journey_first_to_second", "first_to_second_conversion_rate", 0.004842, 290),
  ],
  considered: [
    { play_id: "aov_lift_via_threshold_bundle", reason_code: "signal_inconsistent_across_windows", audience_size: 40 },
    { play_id: "winback_21_45", reason_code: "no_measured_signal", audience_size: 80 },
    { play_id: "subscription_nudge", reason_code: "data_quality_flag", audience_size: 12 },
  ],
  considered_truncated_count: 2,
  watching: [{ metric: "net_sales", trend: "down", threshold_to_act: "+/- 10% to revisit revenue plays" }],
};
const presentedRun = presentEngineRun(engineRun, null, null, { analysedAt: "2026-09-08T22:44:59.654Z", currency: "USD" });

const apiModule = await import("../src/api.js");
apiModule.api.setShopDomain("acme-e.myshopify.com");
const stub = (value) => async () => value;
Object.assign(apiModule.api, {
  health: stub({ ok: true }),
  session: stub({ ok: true, authenticated: true, shopDomain: "acme-e.myshopify.com" }),
  connectionStatus: stub({ ok: true, status: { shopify: { connected: true }, klaviyo: { connected: true } } }),
  testShopify: stub({ ok: true }),
  testKlaviyo: stub({ ok: true }),
  brandContext: stub({ ok: true, brandContext: null }),
  brandEmailTemplate: stub({ ok: true, configured: false }),
  klaviyoSender: stub({ ok: true, sender: null }),
  getEngineInput: stub({ ok: true, input: null }),
  getLatestEngineRun: stub({ ok: true, found: true, presentedRun }),
  listCampaigns: stub({ ok: true, campaigns: [] }),
  syncStatus: stub({
    ok: true, ready: true, reasons: [],
    active: { syncRunId: 9, publishedAt: "2026-09-08T22:40:00.000Z", coverage: { known: true, daysCovered: 120 } },
    latest: { syncRunId: 9, status: "published" },
    analysis: { runId: "run-e", provenance: "verified", stale: false },
  }),
  getStatsSeries: stub({ ok: true, weeks: [] }),
  getKlaviyoTemplates: stub({ ok: true, templates: [] }),
});

const { App } = await import("../src/App.jsx");

test.afterEach(() => cleanup());

async function mountBriefing() {
  await act(async () => {
    render(React.createElement(App));
    await new Promise((resolve) => setTimeout(resolve, 80));
  });
  return document.body.textContent || "";
}

test("the briefing labels store evidence as the store's, with units and no lift language", async () => {
  const text = await mountBriefing();

  assert.match(text, /Your briefing is ready — 3 plays/);
  assert.match(text, /Observed in your store/);
  // The reported defects, each of which is text that must no longer render.
  assert.doesNotMatch(text, /similar stores/i, "STORE_OBSERVED was labelled as other stores' data");
  assert.doesNotMatch(text, /Orders analyzed/i, "n is not an order count for any of these metrics");
  assert.doesNotMatch(text, /60,528/, "the discount metric's n is a dollar total, not a sample");
  assert.doesNotMatch(text, /Observed effect/i, "a metric's change is not the campaign's effect");
  assert.doesNotMatch(text, /Est\. opportunity|Estimated upside|\blift\b/i);
  assert.doesNotMatch(text, /\bL56\b/, "windows are written out");

  assert.match(text, /Reactivation rate/);
  assert.match(text, /Down 20\.6%/);
  assert.match(text, /last 56 days, compared with the 56 days before/);
  assert.match(text, /107 lapsed customers tracked/);
  assert.match(text, /Baseline revenue/);
});

test("held plays each give their own reason, and the truncated remainder is counted", async () => {
  const text = await mountBriefing();
  assert.match(text, /points in different directions depending on the time period/);
  assert.match(text, /doesn't show a signal for this play/);
  assert.match(text, /data-quality issue/);
  assert.doesNotMatch(text, /needs more store data|need more data/i);
  assert.match(text, /2 more held plays aren't listed/);
  assert.doesNotMatch(text, /strong enough to recommend/);
  assert.match(text, /Watching/);
  assert.match(text, /Net sales/);
});

test("rank stays with the engine's first recommendation when another row is selected", async () => {
  await mountBriefing();
  const top = () => screen.getAllByText("Top recommendation");
  assert.equal(top().length, 1);
  assert.match(top()[0].closest("button").textContent, /Bring back lapsed customers/);

  const row = (name) => [...document.querySelectorAll("button.recommendation-row")].find((b) => b.textContent.includes(name));
  await act(async () => {
    fireEvent.click(row("Reduce discount dependency"));
  });
  assert.equal(top().length, 1);
  assert.match(top()[0].closest("button").textContent, /Bring back lapsed customers/, "selection does not promote a row");
  assert.equal(row("Reduce discount dependency").getAttribute("aria-pressed"), "true");
  assert.equal(row("Bring back lapsed customers").getAttribute("aria-pressed"), "false");
  assert.match(document.body.textContent, /Recommended now · #2/);
  assert.doesNotMatch(document.body.textContent, /\bPrimary\b/);
});

test("store connection, last sync and last analysis are shown apart, and the action says what it does", async () => {
  const text = await mountBriefing();
  assert.match(text, /ShopifyConnected/);
  assert.match(text, /Synced Sep 8, .* · 120 days of orders/);
  assert.match(text, /Analysed Sep 8/);
  assert.ok(screen.getByRole("button", { name: "Re-run analysis" }));
  assert.equal(screen.queryByRole("button", { name: "Refresh briefing" }), null);
});

// --- run-level states, without mounting ------------------------------------

test("an abstaining run uses the engine's reason, not a count of held plays", () => {
  const soft = presentEngineRun({ ...engineRun, recommendations: [], abstain: { state: "abstain_soft", mode: "soft_below_floor" } });
  const head = briefingHeadline({ decision: soft.decision, readyCount: 0, heldCount: 3, hasRun: true });
  assert.equal(head.title, "No campaign is recommended from this analysis");
  assert.match(head.detail, /impact is too small/);
  assert.doesNotMatch(head.title, /need more data/);
});

test("an empty run is not described as everything being strong enough", () => {
  const head = briefingHeadline({ decision: { state: "publish" }, readyCount: 0, heldCount: 0, hasRun: true });
  assert.equal(head.title, "This analysis returned no plays");
  assert.equal(heldLaneEmptyText({ heldCount: 0, truncatedCount: 0 }), "No plays were held back in this analysis.");
  // A truncated list is not "nothing held".
  assert.equal(heldLaneEmptyText({ heldCount: 0, truncatedCount: 3 }), null);
  assert.equal(truncatedNote(1), "1 more held play isn't listed.");
  assert.equal(truncatedNote(0), null);
});

test("only data-volume holds are framed as the store needing more orders", () => {
  const signal = presentedRun.considered;
  assert.equal(holdsAreDataVolume(signal), false);
  const young = presentEngineRun({ ...engineRun, considered: [{ play_id: "x", reason_code: "cold_start_insufficient_data" }] }).considered;
  assert.equal(holdsAreDataVolume(young), true);
  assert.equal(holdsAreDataVolume([]), false);
});

test("sync and analysis states each say their own thing", () => {
  const byKey = (items) => Object.fromEntries(items.map((i) => [i.key, i]));

  const failed = byKey(dataStatusItems({
    connected: true,
    syncStatus: { active: { publishedAt: "2026-09-01T10:00:00Z" }, latest: { status: "failed" }, analysis: { provenance: "verified_stale" } },
    analysedAt: "2026-09-01T11:00:00Z",
  }));
  assert.match(failed.sync.value, /latest attempt failed/);
  assert.equal(failed.sync.tone, "warn");
  assert.match(failed.analysis.value, /uses an earlier sync/);

  const never = byKey(dataStatusItems({ connected: false, syncStatus: { active: null, latest: null }, analysedAt: null }));
  assert.equal(never.store.value, "Not connected");
  assert.equal(never.sync.value, "Not synced yet");
  assert.equal(never.analysis.value, "Not analysed yet");

  // Status that never loaded is not presented as a state of the store.
  assert.equal(byKey(dataStatusItems({ connected: true, syncStatus: null, analysedAt: null })).sync.value, "Not available");
});

test("evidence items without a known unit are left out rather than guessed", () => {
  const discount = presentedRun.recommendations.find((r) => r.play_id === "discount_dependency_hygiene");
  const labels = evidenceChipItems(discount, null).map((c) => c.label);
  assert.ok(!labels.includes("Based on"));
  assert.ok(labels.includes("Full-price purchase rate"));
});
