// Ticket E: the briefing's run-level states and evidence wording, as pure
// functions so each can be tested without mounting the app. They read the
// presenter's typed fields; none of them derives a reason from a boolean.

const STATUS_TIME_FORMAT = { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" };

export function formatStatusTime(iso) {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString("en-US", STATUS_TIME_FORMAT);
}

// DS lock 2: the range is what this audience would spend at its expected
// purchase rate — a baseline, not lift. Said wherever the number appears.
export const BASELINE_REVENUE_NOTE =
  "What this audience would spend at its expected purchase rate — not extra revenue caused by the campaign.";

export function briefingHeadline({ decision, readyCount, heldCount, hasRun }) {
  if (!hasRun) return { title: "Run your briefing to see recommendations", detail: null };
  // The engine's own typed verdict wins: a run that abstained says why, instead
  // of every empty briefing reading "need more data".
  if (decision?.state && decision.state !== "publish" && decision.headline) {
    return { title: decision.headline, detail: decision.detail || null };
  }
  if (readyCount > 0) {
    return { title: `Your briefing is ready — ${readyCount} ${readyCount === 1 ? "play" : "plays"} for your review`, detail: null };
  }
  if (heldCount > 0) {
    return { title: "No campaign is recommended from this analysis", detail: "Each held play below says what is holding it back." };
  }
  return { title: "This analysis returned no plays", detail: "Nothing was recommended or held back. Run the analysis again after the next sync." };
}

// Only the fact. The old line — "Everything BeaconAI considered this run was
// strong enough to recommend" — appeared even when nothing was recommended.
export function heldLaneEmptyText({ heldCount, truncatedCount }) {
  if (heldCount > 0 || truncatedCount > 0) return null;
  return "No plays were held back in this analysis.";
}

export function truncatedNote(count) {
  if (!(count > 0)) return null;
  return `${count} more held ${count === 1 ? "play isn't" : "plays aren't"} listed.`;
}

// "Your store needs more orders" is the story only when every held play is held
// for data volume. A store with plenty of orders and a signal problem was being
// told it was too small.
export function holdsAreDataVolume(heldPlays) {
  return heldPlays.length > 0 && heldPlays.every((play) => play?.reason?.category === "data_volume");
}

// Connected, synced and analysed are three facts with three different times.
// The briefing used to show a single "Updated" time — the analysis — beside a
// button worded as if it refreshed the store.
export function dataStatusItems({ connected, syncStatus, analysedAt }) {
  const items = [
    { key: "store", label: "Shopify", value: connected ? "Connected" : "Not connected", tone: connected ? "ok" : "warn" },
  ];

  const active = syncStatus?.active;
  const latest = syncStatus?.latest;
  let syncValue;
  let syncTone = "ok";
  if (latest?.status === "running") {
    syncValue = "Sync in progress";
    syncTone = "info";
  } else if (active?.publishedAt) {
    syncValue = `Synced ${formatStatusTime(active.publishedAt)}`;
    const days = active.coverage?.daysCovered;
    if (days) syncValue += ` · ${days} days of orders`;
    if (latest?.status === "failed" || latest?.status === "incomplete") {
      syncValue += " · latest attempt failed";
      syncTone = "warn";
    }
  } else if (syncStatus) {
    syncValue = "Not synced yet";
    syncTone = "warn";
  } else {
    syncValue = "Not available";
    syncTone = "info";
  }
  items.push({ key: "sync", label: "Store data", value: syncValue, tone: syncTone });

  const analysed = formatStatusTime(analysedAt);
  let analysisValue = analysed ? `Analysed ${analysed}` : "Not analysed yet";
  let analysisTone = analysed ? "ok" : "warn";
  if (analysed && syncStatus?.analysis?.provenance === "verified_stale") {
    analysisValue += " · uses an earlier sync";
    analysisTone = "info";
  }
  items.push({ key: "analysis", label: "Analysis", value: analysisValue, tone: analysisTone });
  return items;
}

function titleCase(value) {
  return String(value).replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatChange(change) {
  if (!change) return null;
  const magnitude = Math.abs(change.change_pct).toLocaleString("en-US", { maximumFractionDigits: 1 });
  const value = change.direction === "flat" ? "No change" : `${change.direction === "up" ? "Up" : "Down"} ${magnitude}%`;
  return {
    label: change.metric_label || "Store metric",
    value,
    note: change.window ? `${change.window.label}, ${change.window.comparison}` : null,
  };
}

// The evidence grid, from the presenter's typed facts only. Each item states its
// unit: a metric's change carries its window and comparison; a sample carries
// what it counts; a dollar range says it is a baseline.
export function evidenceChipItems(play, revenueLabel) {
  const facts = play?.evidence_facts || {};
  const chips = [];
  if (facts.evidence_source_label) chips.push({ label: "Evidence", value: facts.evidence_source_label });
  const change = formatChange(facts.observed_change);
  if (change) chips.push(change);
  if (facts.sample) {
    chips.push({ label: "Based on", value: `${Number(facts.sample.size).toLocaleString("en-US")} ${facts.sample.unit}` });
  }
  const audience = facts.audience_size ?? play?.audience_size;
  if (audience != null && Number(audience) > 0) {
    chips.push({ label: "Audience", value: `${Number(audience).toLocaleString("en-US")} customers` });
  }
  if (facts.confidence_label) chips.push({ label: "Confidence", value: titleCase(facts.confidence_label) });
  if (revenueLabel) chips.push({ label: "Baseline revenue", value: revenueLabel, note: BASELINE_REVENUE_NOTE });
  return chips;
}
