// Keeping the campaign workspace consistent with the briefing on screen.
//
// Campaign rows were read once per page load, against whichever run happened to
// be showing first. A reload painted the cached previous briefing, bound its
// campaigns, and never re-read them when the server's newer run arrived — so a
// new briefing showed "Approved" for another run's campaign (2026-09-14). And a
// same-tab re-run kept the old run's bindings for good.
//
// Two rules live here, both pure so they can be tested without the app:
//   1. Which briefing may replace the one on screen (shouldApplyBriefing).
//   2. How a fresh read of campaign rows is merged into the play-keyed workspace
//      without disturbing a campaign the merchant is working on (mergeByPlay).
//
// The workspace is still keyed by play here. Moving it to campaign ids is the
// next step; until then, "protected" plays — an open editor, or edits waiting to
// save — keep every binding they have, so their saves keep going to their own
// campaign row.

const NARRATION_RANK = { complete: 2, failed: 2, pending: 1 };

// What the page needs to order two briefings. `authoritative` is false only for
// the copy cached in this browser, which is painted for speed and never allowed
// to replace something the server has already said.
export function briefingOrder(presentedRun, { authoritative }) {
  if (!presentedRun) return null;
  const analysedAt = Date.parse(presentedRun.generated_at || "");
  return {
    runId: presentedRun.run_id || null,
    analysedAtMs: Number.isFinite(analysedAt) ? analysedAt : null,
    narrationRank: NARRATION_RANK[presentedRun.narration_status] || 0,
    authoritative: Boolean(authoritative),
  };
}

export function shouldApplyBriefing(current, incoming) {
  if (!incoming) return false;
  if (!current) return true;

  // The same run: an update in place (its explanations landing). Never step back
  // from a run whose narration settled to an earlier read where it was pending.
  if (incoming.runId && incoming.runId === current.runId) {
    return incoming.narrationRank >= current.narrationRank;
  }

  // This browser's cached copy only fills an empty page.
  if (!incoming.authoritative) return false;
  // The server replaces whatever the cache painted.
  if (!current.authoritative) return true;

  // Two server answers for different runs: the newer analysis wins, so a slow
  // response that left before a re-run finished cannot put the old briefing back.
  if (incoming.analysedAtMs == null || current.analysedAtMs == null) return true;
  return incoming.analysedAtMs >= current.analysedAtMs;
}

// The play-keyed maps a campaign read produces for the run on screen. Rows from
// other runs are listed separately: two runs can share a play id, and merging
// them by play would show one campaign's state on the other's row.
export function runMapsFromCampaigns(campaigns = [], runId) {
  const thisRun = campaigns.filter((c) => c.runId === runId);
  const live = thisRun.filter((c) => c.status !== "dismissed");
  const byPlay = (rows, pick) => Object.fromEntries(rows.map((c) => [c.playId, pick(c)]));
  return {
    thisRunPlayIds: thisRun.map((c) => c.playId),
    livePlayIds: live.map((c) => c.playId),
    historicalCampaigns: campaigns.filter((c) => c.runId !== runId && c.status !== "dismissed"),
    campaignIdByPlay: byPlay(thisRun, (c) => c.id),
    revisionByPlay: byPlay(thisRun, (c) => c.revision),
    runIdByPlay: byPlay(thisRun, (c) => c.runId),
    campaignRowByPlay: byPlay(thisRun, (c) => c),
    destinationByPlay: byPlay(thisRun.filter((c) => c.destinationUrl), (c) => c.destinationUrl),
    selectedTemplateByPlay: byPlay(live.filter((c) => c.templateId), (c) => c.templateId),
    draftEditsByPlay: byPlay(live.filter((c) => c.draftEdits), (c) => c.draftEdits),
    agentCopyByPlay: byPlay(live.filter((c) => c.copy?.copy), (c) => c.copy.copy),
    approvedPlayIds: live.filter((c) => c.status === "approved" || c.status === "sent").map((c) => c.playId),
    authorizedPlayIds: live.filter((c) => c.klaviyoCampaignId).map((c) => c.playId),
  };
}

// A protected play keeps exactly what it has — including having nothing, so a
// fresh read cannot attach another run's row to it. Every other play takes the
// server's answer for the run on screen, and loses entries the server no longer
// has for that run: that is what clears another run's "Approved".
export function mergeByPlay(prev = {}, fromServer = {}, protectedPlayIds = new Set()) {
  const next = {};
  for (const [playId, value] of Object.entries(fromServer)) {
    if (!protectedPlayIds.has(playId)) next[playId] = value;
  }
  for (const playId of protectedPlayIds) {
    if (Object.prototype.hasOwnProperty.call(prev, playId)) next[playId] = prev[playId];
  }
  return next;
}

export function mergePlayIdList(prev = [], fromServer = [], protectedPlayIds = new Set()) {
  const kept = prev.filter((playId) => protectedPlayIds.has(playId));
  const added = fromServer.filter((playId) => !protectedPlayIds.has(playId));
  return Array.from(new Set([...kept, ...added]));
}
