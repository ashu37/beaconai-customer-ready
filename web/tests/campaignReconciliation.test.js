import test from "node:test";
import assert from "node:assert/strict";
import {
  briefingCampaignKeyByPlay, briefingOrder, earlierCampaigns, mergeByKey, mergeKeyList,
  railCampaignKeys, shouldApplyBriefing, workspaceMapsFromCampaigns, workspacePlay,
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
  { id: 1, runId: "run-a", playId: "winback", status: "approved", revision: 4, templateId: "tpl", draftEdits: { subject: "Old run" }, displayName: "Winback", audienceSize: 234 },
  { id: 2, runId: "run-b", playId: "discount", status: "draft", revision: 1, templateId: "tpl-d", draftEdits: null },
  { id: 3, runId: "run-b", playId: "journey", status: "dismissed", revision: 2 },
  { id: 4, runId: "run-b", playId: "winback", status: "draft", revision: 1, draftEdits: { subject: "New run" } },
];

test("campaigns are keyed by campaign id, so two runs' campaigns for one play stay apart", () => {
  const maps = workspaceMapsFromCampaigns(rows);
  assert.deepEqual(maps.draftEditsByKey, { 1: { subject: "Old run" }, 4: { subject: "New run" } });
  assert.deepEqual(maps.approvedKeys, ["1"], "run-a's approval stays on run-a's campaign");
});

test("the briefing links a play only to the run on screen's live campaign", () => {
  const { rowsByKey } = workspaceMapsFromCampaigns(rows);
  assert.deepEqual(briefingCampaignKeyByPlay(rowsByKey, "run-b"), { discount: "2", winback: "4" });
  assert.deepEqual(briefingCampaignKeyByPlay(rowsByKey, "run-c"), {}, "an older campaign never marks a newer recommendation");
  assert.deepEqual(earlierCampaigns(rowsByKey, "run-b").map((c) => c.id), [1], "older work stays listed");
});

test("the rail lists this run's live campaigns plus what the merchant holds open", () => {
  const { rowsByKey } = workspaceMapsFromCampaigns(rows);
  assert.deepEqual(railCampaignKeys({ rowsByKey, runId: "run-b" }), ["2", "4"]);
  assert.deepEqual(railCampaignKeys({ rowsByKey, runId: "run-b", keep: ["1"] }), ["2", "4", "1"], "both winback campaigns, side by side");
});

test("a fresh read replaces unprotected campaigns and leaves protected or newer ones alone", () => {
  const knownKeys = new Set(["1", "2"]);
  const prev = { 1: { subject: "typing" }, 2: { subject: "stale" }, 9: { subject: "created after the read" } };
  const fromServer = { 1: { subject: "server" }, 2: { subject: "server" } };

  assert.deepEqual(mergeByKey(prev, fromServer, { knownKeys }), { 1: { subject: "server" }, 2: { subject: "server" }, 9: { subject: "created after the read" } });
  assert.deepEqual(
    mergeByKey(prev, fromServer, { protectedKeys: new Set(["1"]), knownKeys }),
    { 1: { subject: "typing" }, 2: { subject: "server" }, 9: { subject: "created after the read" } },
  );
  // A protected campaign with nothing stays with nothing.
  assert.deepEqual(mergeByKey({}, { 1: "x" }, { protectedKeys: new Set(["1"]), knownKeys }), {});
});

test("approval lists follow the same rule", () => {
  const knownKeys = new Set(["1", "2", "3"]);
  assert.deepEqual(mergeKeyList(["1", "2"], ["3"], { knownKeys }), ["3"]);
  assert.deepEqual(mergeKeyList(["1", "2"], ["3"], { protectedKeys: new Set(["1"]), knownKeys }), ["1", "3"]);
});

test("a workspace entry takes its identity from the campaign and content only from its own run", () => {
  const briefing = [{ id: "winback", play_id: "winback", play_name: "Bring back lapsed customers", audience_size: 238 }];
  const current = workspacePlay(rows[3], briefing, "run-b");
  assert.equal(current.id, "4");
  assert.equal(current.run_id, "run-b");
  assert.equal(current.audience_size, 238);
  assert.equal(current.fromEarlierRun, false);

  const older = workspacePlay(rows[0], briefing, "run-b");
  assert.equal(older.id, "1");
  assert.equal(older.run_id, "run-a");
  assert.equal(older.audience_size, 234, "its own audience, not the newer analysis's");
  assert.equal(older.fromEarlierRun, true);
});
