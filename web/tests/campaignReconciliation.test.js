import test from "node:test";
import assert from "node:assert/strict";
import {
  briefingCampaignKeyByPlay, briefingOrder, campaignStage, earlierCampaigns, existingCampaignForPlay, mergeByKey, mergeKeyList,
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

test("the rail lists this run's live campaigns, earlier unfinished drafts, and what the merchant holds open", () => {
  const withHandedOff = [
    ...rows,
    { id: 5, runId: "run-a", playId: "journey", status: "approved", revision: 2, frozen: true, deliveryState: "created", klaviyoCampaignId: "K" },
    { id: 6, runId: "run-a", playId: "discount", status: "draft", revision: 3, supersededById: 2 },
  ];
  const { rowsByKey } = workspaceMapsFromCampaigns(withHandedOff);
  assert.deepEqual(
    [...railCampaignKeys({ rowsByKey, runId: "run-b" })].sort(),
    ["1", "2", "4"],
    "run-a's approved-but-not-handed-off winback stays; handed-off and replaced ones do not",
  );
  assert.ok(railCampaignKeys({ rowsByKey, runId: "run-b", keep: ["5"] }).includes("5"), "a campaign the merchant opened stays");
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

test("a campaign's stage: editable draft, handed off to Klaviyo, or sent", () => {
  assert.equal(campaignStage({ status: "approved", deliveryState: "not_started" }), "draft", "approved but not handed off is still a draft");
  assert.equal(campaignStage({ status: "draft", deliveryState: "failed" }), "draft", "a creation that provably failed can be retried");
  assert.equal(campaignStage({ status: "approved", frozen: true }), "in_klaviyo");
  assert.equal(campaignStage({ status: "approved", deliveryState: "uncertain" }), "in_klaviyo", "an unconfirmed creation is never treated as editable");
  assert.equal(campaignStage({ status: "approved", deliveryState: "sent", providerSentAt: "2026-09-10T12:00:00Z" }), "sent");
  // A scheduled campaign carries its scheduled time in providerSentAt. It has not been sent.
  assert.equal(campaignStage({ status: "approved", frozen: true, deliveryState: "scheduled", providerSentAt: "2026-09-20T12:00:00Z" }), "in_klaviyo");
  assert.equal(campaignStage({ status: "approved", frozen: true, deliveryState: "awaiting_send", providerSentAt: "2026-09-10T12:00:00Z" }), "in_klaviyo");
});

test("the briefing card's existing campaign: this run's first, then the most actionable earlier one", () => {
  const at = (day) => `2026-09-${day}T12:00:00Z`;
  const list = [
    { id: 10, runId: "r1", playId: "winback", status: "approved", deliveryState: "sent", providerSentAt: at(1), createdAt: at(1) },
    { id: 11, runId: "r2", playId: "winback", status: "draft", createdAt: at(5) },
    { id: 12, runId: "r3", playId: "winback", status: "approved", frozen: true, deliveryState: "created", createdAt: at(8) },
    { id: 13, runId: "r3", playId: "discount", status: "draft", supersededById: 14, createdAt: at(8) },
    { id: 15, runId: "r3", playId: "journey", status: "dismissed", createdAt: at(8) },
  ];
  const { rowsByKey } = workspaceMapsFromCampaigns(list);

  assert.deepEqual(
    (({ kind, key }) => ({ kind, key }))(existingCampaignForPlay(rowsByKey, "winback", "r9")),
    { kind: "draft", key: "11" },
    "an unfinished draft outranks a newer handed-off campaign and an older send",
  );
  assert.equal(existingCampaignForPlay(rowsByKey, "winback", "r2").kind, "current", "the run on screen's own campaign comes first");
  assert.equal(existingCampaignForPlay(rowsByKey, "discount", "r9"), null, "a replaced draft is not existing work");
  assert.equal(existingCampaignForPlay(rowsByKey, "journey", "r9"), null, "nor is a dismissed one");

  const { rowsByKey: sentOnly } = workspaceMapsFromCampaigns([list[0], list[2]]);
  assert.equal(existingCampaignForPlay(sentOnly, "winback", "r9").kind, "in_klaviyo");
});
