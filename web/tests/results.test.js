import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";

// Ticket G's Results screen against RESULTS_UI_SPEC.md, fed a payload shaped
// exactly like GET /results. Sample data.
const HOUR = 3600000;
const DAY = 24 * HOUR;
const iso = (ms) => new Date(ms).toISOString();
const now = Date.now();

const figures = (customers, purchasers, orders, revenue) =>
  ({ customers, purchasers, orders, revenue, revenuePerCustomer: revenue / customers });
function win(days, sentMs, overrides = {}) {
  const end = sentMs + days * DAY;
  return {
    windowDays: days, start: iso(sentMs), end: iso(end), complete: now >= end,
    daysElapsed: Math.min(days, Math.floor((now - sentMs) / DAY)),
    calculatedAt: iso(now - 5 * 60000), calculationStale: false,
    assigned: null, heldBack: null,
    assessment: { state: "measuring", reasons: ["window_open"] }, comparison: null,
    otherExposure: { status: "none", customers: 0 },
    calculatedFrom: { syncRunId: 9, lastSuccessfulSyncAt: iso(now - HOUR), ordersCoveredThrough: iso(now - HOUR), stale: false, reason: null },
    sourceSuperseded: false,
    ...overrides,
  };
}
const FRESH = { syncRunId: 9, lastSuccessfulSyncAt: iso(now - HOUR), ordersCoveredThrough: iso(now - HOUR), stale: false, reason: null };

// 1. Measuring: day 5 of 30.
const s1 = now - 5 * DAY;
const measuring = {
  measurable: true, campaignId: 1, playId: "winback_dormant_cohort", displayName: "Bring back lapsed customers",
  sentAt: iso(s1), assignment: { assigned: 211, heldBack: 23 }, source: FRESH,
  delivery: { state: "sent", providerSentAt: iso(s1), providerSentCount: 198 },
  windows: [30, 60, 90].map((d) => win(d, s1, {
    assigned: figures(211, 9, 11, 865.1), heldBack: figures(23, 1, 1, 90.85),
  })),
};
// 2. Completed 30 and 60 (policy pending), 90 open. 60-day figures differ, and
//    another BeaconAI campaign lands inside the 60-day window only.
const s2 = now - 70 * DAY;
const completed = {
  measurable: true, campaignId: 2, playId: "discount_dependency_hygiene", displayName: "Reduce discount dependency",
  sentAt: iso(s2), assignment: { assigned: 499, heldBack: 56 }, source: FRESH,
  delivery: { state: "sent", providerSentAt: iso(s2), providerSentCount: null },
  windows: [
    win(30, s2, { assigned: figures(499, 61, 70, 3003.98), heldBack: figures(56, 6, 6, 285.6), assessment: { state: "assessment_policy_pending", reasons: ["assessment_policy_pending"] } }),
    win(60, s2, { assigned: figures(499, 88, 104, 4740.5), heldBack: figures(56, 9, 9, 448), assessment: { state: "assessment_policy_pending", reasons: ["assessment_policy_pending"] }, otherExposure: { status: "present", customers: 41 } }),
    win(90, s2, { assigned: figures(499, 90, 107, 4800), heldBack: figures(56, 9, 9, 450) }),
  ],
};
// 3. Insufficient data, and a failed recalculation.
const s3 = now - 45 * DAY;
const insufficient = {
  measurable: true, campaignId: 3, playId: "cohort_journey_first_to_second", displayName: "Turn first-time buyers into repeat buyers",
  sentAt: iso(s3), assignment: { assigned: 60, heldBack: 7 }, source: FRESH, calculationFailed: true,
  delivery: { state: "sent", providerSentAt: iso(s3), providerSentCount: 58 },
  windows: [30, 60, 90].map((d) => win(d, s3, {
    assigned: figures(60, 4, 5, 212), heldBack: figures(7, 0, 0, 0),
    assessment: d === 30 ? { state: "insufficient_data", reasons: ["no_purchasers_in_a_group"] } : { state: "measuring", reasons: ["window_open"] },
    calculatedAt: iso(now - 3 * DAY), calculationStale: true,
  })),
};
// 4. Handed off, not confirmed.
const draft = {
  measurable: false, reason: "send_not_confirmed", deliveryState: "created", campaignId: 4,
  playId: "replenishment_due", displayName: "Remind customers to reorder", sentAt: null,
  delivery: { state: "created", providerCampaignUrl: null, lastCheckedAt: null },
};

let payload;
let failNext = false;
const originalCalls = [];
const apiModule = await import("../src/api.js");
apiModule.api.setShopDomain("results-g.myshopify.com");
const stub = (value) => async () => value;
Object.assign(apiModule.api, {
  health: stub({ ok: true }),
  session: stub({ ok: true, authenticated: true, shopDomain: "results-g.myshopify.com" }),
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
  getResults: async () => {
    if (failNext) { failNext = false; throw new Error("Network down"); }
    return payload;
  },
  campaignOriginal: async (id) => {
    originalCalls.push(id);
    return {
      ok: true, campaignId: id,
      approvedCopy: { subject: "Worth full price — here's why", previewText: "Quality that lasts" },
      frozenAt: "2026-07-02T16:01:00.000Z",
      renderedHtml: "<html><body>Frozen email</body></html>",
      destinationUrl: "https://shop.example/collections/all",
      recommendation: {
        playName: "Reduce discount dependency", evidenceLine: "Observed in your store",
        observedChange: { metric_label: "Share of revenue from heavy-discount customers", unit: "percentage_points", value: 5.3, direction: "up",
          window: { label: "last 56 days", comparison: "compared with the 56 days before" }, note: null },
        audienceSize: 555, audienceDefinition: "Customers who mostly buy on discount",
      },
    };
  },
});
const { App } = await import("../src/App.jsx");

function freshPayload(overrides = {}) {
  return {
    ok: true,
    program: { available: false, reason: "protocol_not_live", sinceDays: 90, campaigns: 3 },
    results: [measuring, completed, insufficient, draft],
    source: FRESH, hasMore: false, limit: 100, loadedAt: iso(now),
    ...overrides,
  };
}

async function openResults({ url = "/" } = {}) {
  window.history.replaceState({}, "", url);
  await act(async () => {
    render(React.createElement(App));
    await new Promise((r) => setTimeout(r, 40));
  });
  if (!document.querySelector(".results-page")) {
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Results" }));
      await new Promise((r) => setTimeout(r, 40));
    });
  }
}
const rowButton = (name) => [...document.querySelectorAll("button.result-row")].find((b) => b.textContent.includes(name));

test.beforeEach(() => { payload = freshPayload(); failNext = false; originalCalls.length = 0; });
test.afterEach(() => cleanup());

test("rows say 'assigned to receive' and carry an explicit 30-day result; the program band has no figure", async () => {
  await openResults();
  const text = document.body.textContent;
  assert.match(text, /Program comparison isn't available yet\. Campaign-level observations appear below; they should not be added together\./);
  assert.equal(document.querySelectorAll(".result-30-label").length, 4, "every row labels its 30-day result");
  assert.match(text, /211 assigned to receive · 23 held back/);
  assert.doesNotMatch(text, /Received|\d[\d,]* sent\b/, "no assignment count is called received or sent");
  assert.doesNotMatch(text, /Worked|No effect found|Cost you money/);
});

test("an early observation shows both groups and nothing else", async () => {
  await openResults();
  const row = rowButton("Bring back lapsed customers");
  assert.match(row.textContent, /Early observation/);
  assert.match(row.textContent, /Assigned to receive \$4\.10/);
  assert.match(row.textContent, /Held back \$3\.95/);
  assert.match(row.textContent, /day 5 of 30/);
  assert.doesNotMatch(row.textContent, /Difference|range|\+\$|−\$/);
  assert.equal(row.querySelector(".verdict").className.includes("verdict-pos"), false, "no winner colour");
});

test("the expanded detail follows the selected window; the row stays on 30 days", async () => {
  await openResults();
  const row = rowButton("Reduce discount dependency");
  await act(async () => { fireEvent.click(row); });
  assert.equal(row.getAttribute("aria-expanded"), "true");
  const detail = document.getElementById("result-detail-2");
  assert.ok(detail, "aria-controls points at the detail");

  // Default: 30 days.
  assert.match(detail.textContent, /\$6\.02/);
  assert.doesNotMatch(detail.textContent, /may have been included in other BeaconAI campaigns/, "no other exposure in the 30-day window");
  assert.match(detail.textContent, /A comparison isn't reported yet/);
  assert.match(detail.textContent, /Sent count unavailable/);

  // Switch to 60: figures, dates, exposure all follow.
  await act(async () => { fireEvent.click(within(detail).getByLabelText(/^60 days/)); });
  assert.match(detail.textContent, /\$9\.50/);
  assert.doesNotMatch(detail.textContent, /\$6\.02/);
  assert.match(detail.textContent, new RegExp(new Date(s2 + 60 * DAY).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })));
  assert.match(detail.textContent, /These customers may have been included in other BeaconAI campaigns\. This comparison does not isolate this email's effect\./);
  assert.match(detail.textContent, /Your other marketing may also affect these results\./);

  // The collapsed row still says 30 days.
  assert.match(row.textContent, /30-day result/);
  assert.match(row.textContent, /\$6\.02/);
  assert.doesNotMatch(row.textContent, /\$9\.50/);
});

test("unique purchasers and orders are separate rows of the group table", async () => {
  await openResults();
  await act(async () => { fireEvent.click(rowButton("Reduce discount dependency")); });
  const table = document.querySelector("#result-detail-2 table");
  const cells = (label) => [...table.querySelectorAll("tr")].find((tr) => tr.querySelector("th")?.textContent === label)
    ?.querySelectorAll("td");
  assert.deepEqual([...cells("Unique purchasers")].map((td) => td.textContent), ["61", "6"]);
  assert.deepEqual([...cells("Orders")].map((td) => td.textContent), ["70", "6"]);
  assert.equal(table.querySelector("thead").textContent, "Assigned to receiveHeld back");
});

test("insufficient data, and a failed recalculation that keeps its last result with a retry", async () => {
  await openResults();
  const row = rowButton("Turn first-time buyers");
  assert.match(row.textContent, /Insufficient data/);
  await act(async () => { fireEvent.click(row); });
  const detail = document.getElementById("result-detail-3");
  assert.match(detail.textContent, /Too few customers or purchasers in one group to compare them\./);
  assert.match(detail.textContent, /Couldn't recalculate\. Showing the result calculated/);
  assert.ok(within(detail).getByRole("button", { name: "Try again" }));
});

test("stale store data is flagged even when the calculation is fresh, with a re-sync action", async () => {
  payload = freshPayload({
    source: { lastSuccessfulSyncAt: iso(now - 3 * DAY), ordersCoveredThrough: iso(now - 3 * DAY), stale: true, reason: "sync_older_than_24h" },
  });
  // Recalculated just now — but from that same three-day-old sync.
  payload.results = payload.results.map((r) => (r.measurable ? {
    ...r,
    source: payload.source,
    windows: r.windows.map((w) => ({ ...w, calculatedFrom: { ...payload.source } })),
  } : r));
  await openResults();
  assert.match(document.body.textContent, /Store data last synced 3 days ago\. Results can't include orders since then\./);
  assert.ok(screen.getByRole("button", { name: "Re-sync store" }));
  await act(async () => { fireEvent.click(rowButton("Reduce discount dependency")); });
  const detail = document.getElementById("result-detail-2");
  assert.match(detail.textContent, /Calculated/);
  assert.match(detail.textContent, /The store data behind these figures is over 24 hours old/);
});

test("an unconfirmed send is listed with its delivery state and no result", async () => {
  await openResults();
  const text = document.body.textContent;
  assert.match(text, /Remind customers to reorder/);
  assert.match(text, /Draft created/);
  assert.match(text, /Results start once Klaviyo confirms the send\./);
  assert.equal(rowButton("Remind customers to reorder"), undefined, "nothing measured to expand");
});

test("a refresh failure keeps the loaded results, with a persistent retry", async () => {
  await openResults();
  failNext = true;
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Briefing" }));
    await new Promise((r) => setTimeout(r, 20));
  });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Results" }));
    await new Promise((r) => setTimeout(r, 40));
  });
  assert.match(document.body.textContent, /Couldn't refresh results/);
  assert.ok(rowButton("Reduce discount dependency"), "the loaded rows are still there");
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await new Promise((r) => setTimeout(r, 40));
  });
  assert.doesNotMatch(document.body.textContent, /Couldn't refresh results/);
});

test("the original campaign stays collapsed until opened, then shows the frozen email and its recommendation", async () => {
  await openResults();
  await act(async () => { fireEvent.click(rowButton("Reduce discount dependency")); });
  const toggle = screen.getByRole("button", { name: /Original campaign/ });
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  assert.deepEqual(originalCalls, [], "nothing loaded while collapsed");
  await act(async () => {
    fireEvent.click(toggle);
    await new Promise((r) => setTimeout(r, 20));
  });
  assert.deepEqual(originalCalls, [2]);
  const text = document.body.textContent;
  assert.match(text, /Worth full price — here's why/);
  assert.match(text, /Why it was suggested/);
  assert.match(text, /Share of revenue from heavy-discount customers: Up 5\.3 percentage points/);
  const frame = document.querySelector("iframe.original-email-frame");
  assert.equal(frame.getAttribute("sandbox"), "", "the frozen email runs no scripts");
  // The handoff snapshot, in C-UI's words. Never "as sent": the merchant can edit
  // the draft in Klaviyo afterwards.
  assert.match(text, /Email handed to Klaviyo on Jul 2, 2026.*\. Changes made later in Klaviyo aren't reflected here\./);
  assert.equal(frame.getAttribute("title"), "Handoff email");
  assert.doesNotMatch(text, /as sent/i);
});

test("a campaign link reopens that result after a refresh", async () => {
  await openResults({ url: "/?shop=results-g.myshopify.com&campaign=2" });
  assert.ok(document.querySelector(".results-page"), "the page load lands on Results");
  assert.equal(rowButton("Reduce discount dependency").getAttribute("aria-expanded"), "true");
  assert.match(window.location.search, /campaign=2/);
});

test("older campaigns are offered only when the server says more exist", async () => {
  await openResults();
  assert.equal(screen.queryByRole("button", { name: "Show older campaigns" }), null);
  cleanup();
  payload = freshPayload({ hasMore: true });
  await openResults();
  assert.ok(screen.getByRole("button", { name: "Show older campaigns" }));
});

test("figures from a superseded sync say so and offer a recalculation; the exposure caveat is always shown", async () => {
  payload = freshPayload();
  payload.results = payload.results.map((r) => (r.campaignId === 2 ? {
    ...r,
    windows: r.windows.map((w) => ({ ...w, sourceSuperseded: true,
      calculatedFrom: { syncRunId: 8, lastSuccessfulSyncAt: "2026-09-01T10:00:00.000Z", ordersCoveredThrough: "2026-09-01T09:50:00.000Z", stale: true, reason: "sync_older_than_24h" } })),
  } : r));
  await openResults();
  await act(async () => { fireEvent.click(rowButton("Reduce discount dependency")); });
  const detail = document.getElementById("result-detail-2");
  assert.match(detail.textContent, /Newer store data is available\. These figures still use the sync from Sep 1, 2026/);
  assert.match(detail.textContent, /from the store sync of Sep 1, 2026/);
  assert.ok(within(detail).getByRole("button", { name: "Recalculate" }));
  assert.match(detail.textContent, /The store data behind these figures is over 24 hours old/);
  assert.match(detail.textContent, /Other BeaconAI campaign exposure may not be fully identified\./);
});

test("a seeded demonstration shows a persistent sample-data banner; a real shop does not", async () => {
  await openResults();
  assert.doesNotMatch(document.body.textContent, /Sample data — illustrative results/);
  cleanup();
  payload = freshPayload({ sampleData: true });
  await openResults();
  const banner = document.querySelector(".results-page > .sample-banner");
  assert.ok(banner, "the banner is the first thing on the page");
  assert.match(banner.textContent, /^Sample data — illustrative results\./);
});
