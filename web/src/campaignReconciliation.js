// Keeping the campaign workspace consistent with the briefing on screen.
//
// Two identities meet here. A play id names a KIND of recommendation and repeats
// across analyses; a campaign id names one piece of the merchant's work. The
// workspace used to key drafts by play, so two campaigns for the same play (an
// older draft and a newer analysis's) shared one slot: copy, saves, previews and
// approval could land on the wrong one (2026-09-14). Everything the merchant
// edits is keyed by campaign id now; the play id is used only to find a play's
// campaign from the briefing.
//
// Pure, so the rules can be tested without the app:
//   1. Which briefing may replace the one on screen (shouldApplyBriefing).
//   2. How a fresh read of campaign rows is merged into the workspace without
//      disturbing a campaign the merchant is working on (mergeByKey).
//   3. Which campaigns the briefing and the Campaigns rail show.

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

export const campaignKey = (row) => (row?.id == null ? null : String(row.id));

// The workspace maps a campaign read produces, keyed by campaign id, for EVERY
// run. Keying by campaign is what lets rows from different runs share a play id.
export function workspaceMapsFromCampaigns(campaigns = []) {
  const rows = campaigns.filter((c) => c && c.id != null);
  const byKey = (list, pick) => Object.fromEntries(list.map((c) => [campaignKey(c), pick(c)]));
  return {
    rowsByKey: byKey(rows, (c) => c),
    selectedTemplateByKey: byKey(rows.filter((c) => c.templateId), (c) => c.templateId),
    draftEditsByKey: byKey(rows.filter((c) => c.draftEdits), (c) => c.draftEdits),
    agentCopyByKey: byKey(rows.filter((c) => c.copy?.copy), (c) => c.copy.copy),
    destinationByKey: byKey(rows.filter((c) => c.destinationUrl), (c) => c.destinationUrl),
    // Every run's approvals. Only the BRIEFING limits itself to the run on
    // screen; an older campaign's approval is still that campaign's.
    approvedKeys: rows.filter((c) => c.status === "approved" || c.status === "sent").map(campaignKey),
  };
}

// A fresh read replaces what the workspace holds, except:
//   - a PROTECTED campaign (open editor, edits waiting or on the wire) keeps
//     exactly what it has, including having nothing;
//   - a campaign the read does not know about keeps its entry. Campaigns are
//     never deleted, so an unknown key was created after the read left.
export function mergeByKey(prev = {}, fromServer = {}, { protectedKeys = new Set(), knownKeys = new Set() } = {}) {
  const next = {};
  for (const [key, value] of Object.entries(fromServer)) {
    if (!protectedKeys.has(key)) next[key] = value;
  }
  for (const [key, value] of Object.entries(prev)) {
    if (protectedKeys.has(key) || !knownKeys.has(key)) next[key] = value;
  }
  return next;
}

export function mergeKeyList(prev = [], fromServer = [], { protectedKeys = new Set(), knownKeys = new Set() } = {}) {
  const kept = prev.filter((key) => protectedKeys.has(key) || !knownKeys.has(key));
  const added = fromServer.filter((key) => !protectedKeys.has(key));
  return Array.from(new Set([...kept, ...added]));
}

const isLive = (row) => row && row.status !== "dismissed";

// The briefing's link from a play to the merchant's campaign for it — on the
// run on screen only. A campaign from an older analysis never makes the new
// recommendation read as already in Campaigns.
export function briefingCampaignKeyByPlay(rowsByKey = {}, runId) {
  const out = {};
  for (const row of Object.values(rowsByKey)) {
    if (runId && row.runId === runId && isLive(row)) out[row.playId] = campaignKey(row);
  }
  return out;
}

// Campaigns in the rail: the run on screen's live campaigns, plus whatever the
// merchant is still holding open (an older draft they reopened or are editing).
export function railCampaignKeys({ rowsByKey = {}, runId, keep = [] }) {
  const current = Object.values(rowsByKey).filter((row) => row.runId === runId && isLive(row)).map(campaignKey);
  return Array.from(new Set([...current, ...keep]));
}

// Campaigns on other runs, for the "Earlier campaigns" list.
export function earlierCampaigns(rowsByKey = {}, runId) {
  return Object.values(rowsByKey).filter((row) => row.runId !== runId && isLive(row));
}

// The play a workspace entry shows. The campaign supplies identity — its id is
// the workspace key, its run and play go with every request — and the briefing
// supplies the play's content only when the campaign belongs to the run on
// screen. An older campaign is shown from its own record, never from a newer
// analysis's version of the same play.
export function workspacePlay(row, briefingPlays = [], runId) {
  if (!row) return null;
  const fromBriefing = row.runId === runId
    ? briefingPlays.find((play) => (play.play_id || play.id) === row.playId)
    : null;
  const base = fromBriefing || {
    play_name: row.displayName || null,
    audience_size: row.audienceSize ?? null,
    source: "campaign",
  };
  return {
    ...base,
    id: campaignKey(row),
    play_id: row.playId,
    run_id: row.runId,
    fromEarlierRun: row.runId !== runId,
  };
}
