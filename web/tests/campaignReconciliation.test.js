import test from "node:test";
import assert from "node:assert/strict";
import {
  briefingOrder, mergeByPlay, mergePlayIdList, runMapsFromCampaigns, shouldApplyBriefing,
} from "../src/campaignReconciliation.js";

const run = (runId, generatedAt, narration) => ({ run_id: runId, generated_at: generatedAt, narration_status: narration });
const server = (r) => briefingOrder(r, { authoritative: true });
const cached = (r) => briefingOrder(r, { authoritative: false });

test("the server's briefing replaces the cached one, and the cache never replaces the server", () => {
  const old = run("run-a", "2026-09-10T04:21:00Z");
  const fresh = run("run-b", "2026-09-14T05:07:00Z");
  assert.equal(shouldApplyBriefing(null, cached(old)), true, "cache fills an empty page");
  assert.equal(shouldApplyBriefing(cached(old), server(fresh)), true, "server replaces the cached paint");
  assert.equal(shouldApplyBriefing(server(fresh), cached(old)), false, "a cached copy never overwrites the server");
});

test("a slow response for an older run cannot put the old briefing back", () => {
  const older = run("run-a", "2026-09-13T22:00:00Z");
  const newer = run("run-b", "2026-09-13T22:07:00Z");
  assert.equal(shouldApplyBriefing(server(newer), server(older)), false);
  assert.equal(shouldApplyBriefing(server(older), server(newer)), true);
});

test("the same run updates in place, but never back to a pending narration", () => {
  const pending = run("run-b", "2026-09-13T22:07:00Z", "pending");
  const complete = run("run-b", "2026-09-13T22:07:00Z", "complete");
  assert.equal(shouldApplyBriefing(server(pending), server(complete)), true, "explanations landing");
  assert.equal(shouldApplyBriefing(server(complete), server(pending)), false, "a late pending read is stale");
});

const rows = [
  { id: 1, runId: "run-a", playId: "winback", status: "approved", revision: 4, templateId: "tpl", draftEdits: { subject: "Old run" }, klaviyoCampaignId: null },
  { id: 2, runId: "run-b", playId: "discount", status: "draft", revision: 1, templateId: "tpl-d", draftEdits: null },
  { id: 3, runId: "run-b", playId: "journey", status: "dismissed", revision: 2 },
];

test("a campaign read binds only the run on screen; other runs are history", () => {
  const maps = runMapsFromCampaigns(rows, "run-b");
  assert.deepEqual(maps.campaignIdByPlay, { discount: 2, journey: 3 });
  assert.deepEqual(maps.livePlayIds, ["discount"], "dismissed is not in the pipeline");
  assert.deepEqual(maps.approvedPlayIds, [], "run-a's approval does not belong to run-b");
  assert.deepEqual(maps.historicalCampaigns.map((c) => c.id), [1]);
});

test("a new briefing clears another run's bindings but keeps a protected play exactly as it is", () => {
  const prev = { winback: 1, discount: 99 };
  const fromServer = runMapsFromCampaigns(rows, "run-b").campaignIdByPlay;

  // Nobody is editing: winback's run-a binding goes, discount takes run-b's row.
  assert.deepEqual(mergeByPlay(prev, fromServer, new Set()), { discount: 2, journey: 3 });

  // The merchant has winback open with edits waiting: it stays on campaign 1.
  assert.deepEqual(mergeByPlay(prev, fromServer, new Set(["winback"])), { winback: 1, discount: 2, journey: 3 });

  // A protected play with no binding stays unbound — never handed another run's row.
  assert.deepEqual(mergeByPlay({}, { winback: 7 }, new Set(["winback"])), {});
});

test("approval lists follow the same rule", () => {
  assert.deepEqual(mergePlayIdList(["winback", "discount"], ["journey"], new Set()), ["journey"]);
  assert.deepEqual(mergePlayIdList(["winback", "discount"], ["journey"], new Set(["winback"])), ["winback", "journey"]);
});
