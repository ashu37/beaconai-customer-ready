import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api";
import { campaignSignature, canHandoff, draftSignature } from "./campaignSaveGate";
import { STANDARD_SUPPRESSIONS_NOTE, agentCopyToDraftFields, buildCampaignFromSelection } from "./campaignDraft";
import { PREVIEW_STATE } from "./previewFreshness";
import { presentDelivery } from "./deliveryPresentation";
import { summarizeAudience, summarizeSender } from "./audienceSummary";
import { usePreview } from "./usePreview";
import { AudiencePanel, FinalReviewPanel } from "./CampaignReviewPanels";
import { signInState } from "./signInState";
import {
  BASELINE_REVENUE_NOTE, briefingHeadline, dataStatusItems, evidenceChipItems, formatChange,
  heldLaneEmptyText, holdsAreDataVolume, truncatedNote,
} from "./briefingPresentation";
import "./styles.css";

// C3: play → starting-copy template. Merchants who never touch template choice
// still get play-appropriate copy. Anything unmapped falls back to the soft nudge.
const PLAY_TEMPLATE_MAP = {
  winback_dormant_cohort: "beacon-winback-clean",
  winback_21_45: "beacon-winback-clean",
  at_risk_repeat_buyer_rescue: "beacon-winback-clean",
  cohort_journey_first_to_second: "beacon-second-purchase",
};
const DEFAULT_STARTING_TEMPLATE = "beacon-lifecycle-soft-nudge";

// The engine emits NO per-play suppression rules (verified: not in the audience
// CSV header nor the manifest audience entry). So this is an HONEST, generic
// platform disclosure — true of every Klaviyo send — not a per-play data claim.
// Do NOT reword this into a play-specific sentence (that would be invented prose).


function templateForPlay(play) {
  const key = play?.play_id || play?.id;
  return PLAY_TEMPLATE_MAP[key] || DEFAULT_STARTING_TEMPLATE;
}

// D0: single inline-SVG icon system (no icon library). Each entry is the inner
// markup of a 24-viewBox, stroke-1.75, round-cap icon. Fallback: "play".
const ICON_PATHS = {
  winback: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v4h4"/>',
  discount: '<line x1="19" y1="5" x2="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
  journey: '<path d="M4 8h12a4 4 0 0 1 0 8H8"/><path d="M8 4 4 8l4 4"/>',
  bundle: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/>',
  replenish: '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v4h-4"/>',
  bestseller: '<path d="m12 3 2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 21l1.1-6.5L2.6 9.8l6.5-.9L12 3Z"/>',
  subscription: '<path d="M17 2l4 4-4 4"/><path d="M3 10V8a4 4 0 0 1 4-4h14"/><path d="M7 22l-4-4 4-4"/><path d="M21 14v2a4 4 0 0 1-4 4H3"/>',
  watch: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  play: '<circle cx="12" cy="12" r="9"/><path d="m10 8 5 4-5 4Z"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  lock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  users: '<path d="M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="8" r="3.5"/><path d="M22 20v-2a4 4 0 0 0-3-3.9"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/>',
  spark: '<path d="M12 3v4"/><path d="M12 17v4"/><path d="M3 12h4"/><path d="M17 12h4"/><path d="m6 6 2.5 2.5"/><path d="m15.5 15.5 2.5 2.5"/><path d="m18 6-2.5 2.5"/><path d="m8.5 15.5-2.5 2.5"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  close: '<path d="M6 6 18 18"/><path d="M18 6 6 18"/>',
  arrowRight: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
  alert: '<path d="M12 9v4"/><path d="M12 17h.01"/><circle cx="12" cy="12" r="9"/>',
};

function Icon({ name, size = 18, className }) {
  const inner = ICON_PATHS[name] || ICON_PATHS.play;
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: inner }}
    />
  );
}

// D0: play → icon. Fallback "play".
const PLAY_ICON_MAP = {
  winback_dormant_cohort: "winback",
  winback_21_45: "winback",
  at_risk_repeat_buyer_rescue: "winback",
  cohort_journey_first_to_second: "journey",
  aov_lift_via_threshold_bundle: "bundle",
  discount_dependency_hygiene: "discount",
  discount_hygiene: "discount",
  bestseller_amplify: "bestseller",
  replenishment_due: "replenish",
  empty_bottle: "replenish",
  subscription_nudge: "subscription",
  frequency_accelerator: "spark",
  routine_builder: "bundle",
  onsite_funnel_watch: "watch",
};

function iconForPlay(play, lane) {
  if (lane === "experiment") return "spark";
  const key = play?.play_id || play?.id;
  return PLAY_ICON_MAP[key] || "play";
}

// P-D1: compact connection chip. Connected → a green dot with a title-attr label.
// Not connected + actionable → a clickable chip that starts OAuth.
function StatusChip({ label, ok, onConnect }) {
  if (ok) {
    return <span className="status-dot ok" title={`${label}: Connected`} aria-label={`${label} connected`} />;
  }
  if (onConnect) {
    return <button type="button" className="status-chip pending" onClick={onConnect}>Connect {label}</button>;
  }
  return <span className="status-chip pending">{label}: Pending</span>;
}

function JsonBlock({ title, value }) {
  return (
    <details className="json-block">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function statusLabel(value) {
  return String(value || "pending")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function readableMetaLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const normalized = raw.toLowerCase().replaceAll("_", " ");
  if (["engine", "review", "pending", "placeholder"].includes(normalized)) return null;
  if (normalized === "store observed") return "Observed in store data";
  return normalized.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function titleizeId(value) {
  return String(value || "Untitled play").replaceAll("_", " ").replaceAll("-", " ");
}

function normalizeAtulPlay(play, index) {
  const audienceSize = play.audience_size ?? play.audience?.size ?? play.audience?.n ?? play.segment_size ?? 0;
  const narration = play.narration || {};
  const title = play.play_name || play.title || titleizeId(play.play_id || play.id);
  const role = play.role || play.lane || (play.reason_code ? "considered" : "recommendation");
  return {
    id: play.play_id || play.id || `atul-play-${index + 1}`,
    play_id: play.play_id || play.id || `atul-play-${index + 1}`,
    play_name: title,
    play_one_liner: play.play_one_liner || null,
    role,
    lane: play.lane || role,
    reason_code: play.reason_code || play.null_reason || null,
    reason_display: play.reason_display || null,
    // The typed hold (code, category, text) and the engine's rank in its lane.
    reason: play.reason || null,
    rank: play.rank ?? null,
    // Prose is the LLM's or NOTHING (Pivot 2). null → the UI renders the
    // evidence chip grid, never a canned "recommendation ready" sentence.
    mechanism: narration.play_thesis || play.mechanism || null,
    audience_archetype: play.audience_archetype || play.audience?.definition || play.audience?.description || play.audience || null,
    // Formal chip payload from the presenter. The card face reads from here.
    evidence_facts: play.evidence_facts || null,
    audience_size: audienceSize,
    confidence: play.confidence_label || play.confidence || play.model_confidence || "Review",
    evidence: play.evidence || { evidence_source: play.evidence_source || null, evidence_class: play.evidence_class || null },
    evidence_source: play.evidence_source || play.evidence?.evidence_source || null,
    evidence_line: play.evidence_line || null,
    revenue_range: play.revenue_range || null,
    narration,
    template_prompt: play.template_prompt || null,
    source: play.source || "atul",
    raw: play,
  };
}

function buildWorkflowPlays({ atulEngineResult, campaignPackages }) {
  const presented = atulEngineResult?.presentedRun?.recommendations || [];
  const presentedConsidered = atulEngineResult?.presentedRun?.considered || [];
  const rawEngineCards = [
    ...(atulEngineResult?.engineRun?.recommendations || []),
    ...(atulEngineResult?.engineRun?.recommended_experiments || []),
    ...(atulEngineResult?.engineRun?.considered || []),
  ];
  const atulPlays = (presented.length || presentedConsidered.length ? [...presented, ...presentedConsidered] : rawEngineCards).map(normalizeAtulPlay);
  if (atulPlays.length) return atulPlays;

  const packagePlays = campaignPackages.map((item) => ({
    id: item.id,
    play_id: item.id,
    play_name: item.playTitle,
    mechanism: item.bodyP1 || item.previewText,
    audience_archetype: item.segment,
    audience_size: item.customers,
    confidence: item.status,
    source: "workflow",
    raw: item,
  }));
  return packagePlays;
}

// CA-4: map the copywriter's slot object to the draft's field shape. subject_variants[0]
// is the pre-selected subject (adopt #5). Returns {} when no agent copy present.
function formatAudience(value) {
  return value?.toLocaleString?.() || "—";
}

// "Last updated" for the briefing: a compact relative label + the exact
// date/time (used as a tooltip). Returns null for an unparseable/missing date.
function formatUpdatedAt(iso) {
  if (!iso) return null;
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return null;
  const diffMs = Date.now() - then.getTime();
  const min = Math.round(diffMs / 60000);
  let relative;
  if (min < 1) relative = "just now";
  else if (min < 60) relative = `${min}m ago`;
  else if (min < 1440) relative = `${Math.round(min / 60)}h ago`;
  else relative = `${Math.round(min / 1440)}d ago`;
  const absolute = then.toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
  });
  return { relative, absolute };
}

function moneyPrefix(currency) {
  return currency === "USD" || !currency ? "$" : `${currency} `;
}

// P0-4: median precedes range wherever both exist; never render "Not sized" as a hero stat.
function formatRevenueRange(play) {
  const parts = revenueRangeParts(play);
  if (!parts) return null;
  if (parts.median != null) return `~${parts.labelMedian} typical · ${parts.labelLow}–${parts.labelHigh}`;
  return `${parts.labelLow}–${parts.labelHigh}`;
}

function revenueRangeParts(play) {
  const range = play?.revenue_range;
  if (!range || range.suppressed || range.low == null || range.high == null) return null;
  const prefix = moneyPrefix(range.currency);
  const low = Number(range.low) || 0;
  const high = Number(range.high) || 0;
  const hasMedian = range.median != null || range.mid != null;
  const median = hasMedian ? Number(range.median ?? range.mid) : null;
  return {
    low,
    high,
    median,
    labelLow: `${prefix}${low.toLocaleString()}`,
    labelHigh: `${prefix}${high.toLocaleString()}`,
    labelMedian: median != null ? `${prefix}${median.toLocaleString()}` : null,
  };
}

function classifyPlayLane(play) {
  const lane = String(play?.lane || play?.role || "").toLowerCase();
  if (play?.reason_code || lane.includes("considered") || lane.includes("held")) return "considered";
  if (lane.includes("experiment")) return "experiment";
  return "recommended";
}

function confidenceTone(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("strong") || text.includes("approved")) return "strong";
  if (text.includes("emerging") || text.includes("trend")) return "emerging";
  return "neutral";
}

const CONFIDENCE_TITLE = "The analysis's confidence label for this play. The Evidence tab says where it comes from.";

function RecommendationRow({ play, selected, approved = false, onSelect }) {
  const confidence = play.confidence || play.confidence_label || play.model_confidence || null;
  const confidenceLabel = readableMetaLabel(confidence);
  const lane = classifyPlayLane(play);
  // A held play's row carries its reason, so "Not ready yet" can be scanned
  // without opening each one. Recommended rows carry their evidence source.
  const evidenceLine = lane === "considered" ? (play.reason?.text || play.reason_display || null) : (play.evidence_line || null);
  // The engine's order, not the merchant's click. Selecting a row used to
  // relabel it "Primary", so the top recommendation moved with the cursor.
  const topRanked = lane === "recommended" && play.rank === 1;
  return (
    <button className={`recommendation-row ${selected ? "selected" : ""}`} aria-pressed={selected} onClick={() => onSelect(play.play_id || play.id)}>
      <span className={`recommendation-icon ${lane}`}><Icon name={iconForPlay(play, lane)} size={18} /></span>
      <span className="recommendation-row-body">
        {topRanked ? <span className="recommendation-overline">Top recommendation</span> : null}
        <span className="recommendation-title">{play.play_name || play.play_id}</span>
        <span className="recommendation-meta">
          <span>{formatAudience(play.audience_size)} customers</span>
          {confidenceLabel ? (
            <span className="recommendation-meta-item" title={CONFIDENCE_TITLE}>
              <span className={`confidence-dot ${confidenceTone(confidence)}`} />
              {confidenceLabel} confidence
            </span>
          ) : null}
          {approved ? <span className="approved-pill"><Icon name="check" size={12} /> Approved</span> : null}
        </span>
        {evidenceLine ? <span className="recommendation-evidence-line">{evidenceLine}</span> : null}
      </span>
      <span className="recommendation-chevron"><Icon name="chevron" size={16} /></span>
    </button>
  );
}

// The evidence grid — 100% data-derived from the presenter's `evidence_facts`.
// Stands alone when the LLM authored no prose. Every item states its unit.
function EvidenceChips({ play, omitRevenue = false }) {
  // `omitRevenue` where the range bar, with its own explanation, sits directly
  // below — the same number and caveat twice in one view reads as two findings.
  const chips = evidenceChipItems(play, omitRevenue ? null : formatRevenueRange(play));
  if (!chips.length) return null;
  return (
    <div className="evidence-chip-grid">
      {chips.map((chip) => (
        <div className="evidence-chip" key={chip.label}>
          <span className="evidence-chip-label">{chip.label}</span>
          <strong className="evidence-chip-value">{chip.value}</strong>
          {chip.note ? <span className="evidence-chip-note">{chip.note}</span> : null}
        </div>
      ))}
    </div>
  );
}

function RecommendationDetail({ play, onSendToReview, onViewEvidence, onOpenInCampaigns, approved = false, showAdvanced = false }) {
  const [activeTab, setActiveTab] = useState("thesis");

  if (!play) {
    return <div className="recommendation-detail empty-panel">Select a recommendation to review the details.</div>;
  }

  const confidence = play.confidence || play.confidence_label || play.model_confidence || "Review";
  const narration = play.narration || {};
  const lane = classifyPlayLane(play);
  const revenue = revenueRangeParts(play);
  const revenueLabel = formatRevenueRange(play);
  const audienceLabel = formatAudience(play.audience_size);
  const heldReason = play.reason_display || "The analysis held this play.";
  const evidenceLabel = play.evidence_facts?.evidence_source_label || null;
  const tabLabels = [
    ["thesis", "Play thesis"],
    ["send", "What we'd send"],
    ["evidence", "Evidence & audience"],
    ...(showAdvanced ? [["sensitivity", "Sensitivity"]] : []),
  ];

  return (
    <div className="recommendation-detail">
      <div className="recommendation-detail-head">
        <span className={`recommendation-icon large ${lane}`}><Icon name={iconForPlay(play, lane)} size={22} /></span>
        <div>
          <div className="section-kicker">{lane === "experiment" ? "Recommended experiment" : lane === "considered" ? "Not ready yet" : play.rank ? `Recommended now · #${play.rank}` : "Recommended now"}</div>
          <h2>{play.play_name || play.play_id}</h2>
        </div>
      </div>

      {/* The evidence source is in the stat strip below; repeating it under the
          title made one fact read as three. Held plays have no strip, so their
          reason is in the footer instead. */}

      <div className="recommendation-stat-strip">
        <div>
          <strong>{audienceLabel}</strong>
          <span>Customers</span>
        </div>
        {revenueLabel ? (
          <div>
            <strong>{revenueLabel}</strong>
            <span>Baseline revenue</span>
          </div>
        ) : null}
        {/* Where the evidence comes from, in words — not a three-bar meter whose
            segments meant nothing a merchant could check. */}
        <div>
          <strong className="stat-evidence" title={play.evidence_facts?.evidence_source_detail || undefined}>
            {evidenceLabel || statusLabel(confidence)}
          </strong>
          <span>{evidenceLabel ? "Evidence" : "Confidence"}</span>
        </div>
      </div>

      <div className="recommendation-tabs" role="tablist">
        {tabLabels.map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={activeTab === key}
            className={activeTab === key ? "active" : ""}
            onClick={() => setActiveTab(key)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>

      <div className="recommendation-tab-body">
        {activeTab === "thesis" ? (
          <>
            {/* Prose only when the LLM authored it; otherwise the chip grid is
                the thesis surface (Pivot 2 typed-absence — no canned sentence). */}
            {narration.play_thesis ? (
              <div className="detail-copy-block">
                <div className="section-kicker">Play thesis</div>
                <p>{narration.play_thesis}</p>
              </div>
            ) : (
              <div className="detail-copy-block">
                <div className="section-kicker">Why this play</div>
                <EvidenceChips play={play} omitRevenue={Boolean(revenue)} />
              </div>
            )}
            {revenue ? (() => {
              // D1: marker position derived from data, not hardcoded. Clamp 4–96%.
              const span = revenue.high - revenue.low;
              const raw = revenue.median != null && span > 0
                ? ((revenue.median - revenue.low) / span) * 100
                : 50;
              const markerLeft = Math.min(96, Math.max(4, raw));
              return (
                <div className="revenue-range">
                  <div className="section-kicker">Baseline revenue</div>
                  <div className="range-track">
                    <span className="range-fill" />
                    <span className="range-marker" style={{ left: `${markerLeft}%` }} />
                  </div>
                  <div className="range-labels">
                    <span>{revenue.labelLow}</span>
                    {revenue.labelMedian ? <span>median {revenue.labelMedian}</span> : null}
                    <span>{revenue.labelHigh}</span>
                  </div>
                  <p className="revenue-note">{BASELINE_REVENUE_NOTE}</p>
                </div>
              );
            })() : null}
          </>
        ) : null}

        {activeTab === "send" ? (
          <>
            {/* Message angle is LLM prose — shown only when authored. The exact
                copy is re-authored at approval #2, so absence just hides the row. */}
            {narration.what_we_d_send ? (
              <div className="model-row">
                <span>Message angle</span>
                <strong>{narration.what_we_d_send}</strong>
              </div>
            ) : null}
            <div className="model-row">
              <span>Template step</span>
              <strong>Choose in Campaigns after approving</strong>
            </div>
            <div className="model-row">
              <span>Next</span>
              <strong>You'll pick and edit the exact email before anything sends.</strong>
            </div>
          </>
        ) : null}

        {activeTab === "evidence" ? (
          <>
            {/* Evidence summary is LLM prose — shown only when authored. The
                chip grid below always carries the data. */}
            {narration.evidence_summary ? (
              <div className="detail-copy-block">
                <div className="section-kicker">Evidence summary</div>
                <p>{narration.evidence_summary}</p>
              </div>
            ) : null}
            <EvidenceChips play={play} />
            {play.evidence_facts?.evidence_source_detail ? (
              <p className="evidence-source-detail">{play.evidence_facts.evidence_source_detail}</p>
            ) : null}
            {play.audience_archetype ? (
              <div className="model-row">
                <span>Audience</span>
                <strong>{play.audience_archetype}</strong>
              </div>
            ) : null}
            <div className="model-row">
              <span>At send</span>
              <strong>{STANDARD_SUPPRESSIONS_NOTE}</strong>
            </div>
            <div className="evidence-fineprint">{play.play_id || play.id}</div>
          </>
        ) : null}

        {activeTab === "sensitivity" ? (
          <>
            <div className="model-row">
              <span>Confidence</span>
              <strong>{statusLabel(confidence)}</strong>
            </div>
            <div className="model-row">
              <span>Baseline revenue</span>
              <strong>{formatRevenueRange(play) || "Not available"}</strong>
            </div>
            <div className="model-row">
              <span>Review note</span>
              <strong>{play.reason_code ? heldReason : "Merchant approval required before template work"}</strong>
            </div>
          </>
        ) : null}
      </div>

      {lane === "considered" ? (
        <div className="recommendation-detail-footer held">
          <p className="held-reason">Held for now — {heldReason}</p>
        </div>
      ) : (
        <div className="recommendation-approve-block">
          <p className="approve-note">
            {approved
              ? "Approved — it's in your campaign pipeline. Review the copy and pick a template in Campaigns."
              : "Approving moves this to your campaign pipeline. Nothing is sent to customers until you approve the final email."}
          </p>
          <p className="approve-note measurement">We'll track what these customers do for 30 days after send and report it in Results.</p>
          <div className="recommendation-detail-footer">
            {approved ? (
              // P-C3: approved plays show a state chip that jumps to Campaigns,
              // not a second Approve control.
              <button type="button" className="in-campaigns-chip" onClick={() => onOpenInCampaigns(play)}>
                <Icon name="check" size={14} /> In campaigns <Icon name="arrowRight" size={14} />
              </button>
            ) : (
              <button className="btn primary" onClick={() => onSendToReview(play)}>Approve &amp; pick template</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// C2: Send step — detail for a single selected campaign (no internal list; the
// master-detail left rail owns selection now).
// P-B: Send is a confirmation, not a workspace. Statement + three summary rows
// (each with an Edit link back to its step) + a truthful what-happens-next line.
// The primary action lives in the sticky action bar (P-A3), not here.
function CampaignSendPanel({ campaign, onEditStep }) {
  const selected = campaign;
  if (!selected) {
    return <div className="empty-panel">No campaign package is ready yet.</div>;
  }

  return (
    <div className="send-confirm">
      <p className="send-statement">
        Send “{selected.subject}” to {formatAudience(selected.customers)} matched customers through your Klaviyo account.
      </p>

      <div className="send-summary">
        <div className="send-summary-row">
          <div className="send-summary-body">
            <span className="send-summary-label">Copy</span>
            <span className="send-summary-value">{selected.subject}</span>
            <span className="send-summary-meta">{selected.templateName || "Starting copy"}</span>
          </div>
          <button type="button" className="link-btn" onClick={() => onEditStep("copy")}>Edit</button>
        </div>

        <div className="send-summary-row">
          <div className="send-summary-body">
            <span className="send-summary-label">Audience</span>
            <span className="send-summary-value">{selected.segment}</span>
            <span className="send-summary-meta">Suppressed: recent purchasers, unsubscribes, suppressed profiles</span>
          </div>
          <button type="button" className="link-btn" onClick={() => onEditStep("audience")}>Edit</button>
        </div>

        <div className="send-summary-row">
          <div className="send-summary-body">
            <span className="send-summary-label">Delivery</span>
            <span className="send-summary-value">Created as a draft in Klaviyo for your final approval</span>
          </div>
        </div>
      </div>

      {selected.klaviyoTemplateId ? (
        <div className="success-box" title={`Template ${selected.klaviyoTemplateId}${selected.klaviyoCampaignId ? ` · Campaign ${selected.klaviyoCampaignId}` : ""}${selected.klaviyoSendJobId ? ` · Send job ${selected.klaviyoSendJobId}` : ""}`}>
          Created in Klaviyo — “{selected.templateName || "your campaign"}” is waiting as a draft.
          {selected.klaviyoAudience ? ` List matched ${formatAudience(selected.klaviyoAudience.count)} recipients.` : ""}
        </div>
      ) : null}
    </div>
  );
}

// CA-4: the "Suggested" value for a field = what the AGENT wrote (agentCopy),
// falling back to the static template_prompt when no agent copy exists. This is
// the anchor for the Edited badge (#2: a field with a badge = merchant changed it
// from the agent's suggestion) and edit-preserving rewrite (#1).
function suggestedValueForField(play, field, agentCopy = null) {
  const agentFields = agentCopyToDraftFields(agentCopy);
  if (agentFields[field] != null) return agentFields[field];
  const prompt = play?.template_prompt || {};
  switch (field) {
    case "subject": return prompt.subject ?? "";
    case "previewText": return prompt.previewText ?? "";
    case "bodyH2": return prompt.headline ?? "";
    case "bodyP1": return prompt.body ?? prompt.support ?? "";
    case "bodyP2": return prompt.support ?? "";
    case "cta": return prompt.cta ?? "";
    default: return "";
  }
}

export function CampaignReviewPane({
  play,
  brandContext,
  beaconTemplates,
  klaviyoTemplates,
  selectedTemplate,
  onChooseTemplate,
  draft,
  onChange,
  onRestoreField,
  onRefreshBrandContext,
  onRefreshTemplates,
  klaviyoFailed,
  agentCopy,
  copyStatus,
  draftEdits,
  onRewrite,
  saveState,
  onRetrySave,
  activeBrandTemplateVersion,
  onPreviewRendered,
  destinationUrl,
  onChangeDestination,
  campaignSignature: currentCampaignSignature,
  brandDesign,
}) {
  // Phone preview mode: "inbox" = iOS-Mail list row, "email" = opened message.
  // Default to the branded EMAIL. A merchant has to recognise the email they
  // would send; the inbox row shows a subject line, which is not that.
  const [previewMode, setPreviewMode] = useState("email");
  // A viewport check, not a guarantee of identical rendering in every client.
  const [previewViewport, setPreviewViewport] = useState("desktop");
  const [steer, setSteer] = useState(null); // active rewrite-steer chip (adopt #4)
  const copyLoading = copyStatus === "loading";
  const subjectVariants = Array.isArray(agentCopy?.subject_variants) ? agentCopy.subject_variants : [];

  // Preview + freshness live in usePreview so the binding between a request and
  // what it approves is testable. See web/src/usePreview.js.
  const { html: previewHtml, freshness, renderedFrom, problem: previewProblem, refresh: refreshPreview, flush: flushPreview } = usePreview({
    draft,
    campaignSignature: currentCampaignSignature,
    campaignKey: `${play?.id || ""}:${selectedTemplate?.id || ""}`,
    brandContext,
    activeBrandTemplateVersion,
    fetchPreview: (payload) => api.previewCampaignHtml(payload),
    onPreviewRendered,
  });

  const handleBlur = () => flushPreview();

  const [changeOpen, setChangeOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [designOpen, setDesignOpen] = useState(false);
  const destinationFieldRef = useRef(null);
  const focusDestination = () => {
    const input = destinationFieldRef.current?.querySelector("input");
    if (input) { input.focus(); input.scrollIntoView({ block: "center", behavior: "smooth" }); }
  };
  const effectiveDestination = renderedFrom?.effectiveDestinationUrl || null;
  // A typed value that is not a usable link. Empty is NOT invalid: the approved
  // design may supply a default, and the effective link below says which.
  const destinationInvalid = Boolean(
    destinationUrl && !/^https?:\/\/[^\s]+$/i.test(String(destinationUrl).trim())
  );
  const senderName = brandContext?.brandName || "Your store";
  const editFields = [
    { field: "subject", label: "Subject", type: "input" },
    { field: "previewText", label: "Preview text", type: "input" },
    { field: "bodyH2", label: "Headline", type: "input" },
    { field: "bodyP1", label: "Body", type: "textarea" },
    { field: "bodyP2", label: "Support paragraph (optional)", type: "textarea" },
    { field: "cta", label: "Button label", type: "input" },
  ];
  const startingName = selectedTemplate?.name || "—";
  // Persistent, not a toast. An edit that failed to save must stay visible:
  // the merchant is otherwise typing into a draft nothing is storing.
  const saveLabel = {
    saving: "Saving…",
    saved: "Saved",
    failed: "Not saved",
    conflict: "Changed elsewhere",
  }[saveState] || null;

  return (
    <div className="review-pane">
      {/* The approved store design, named separately from the writing style.
          Changing words and changing branding are different actions, and the
          merchant has no controls over the second — it is stated, not offered. */}
      <div className="voice-chip">
        <button type="button" className="voice-chip-line" onClick={() => setDesignOpen((p) => !p)}>
          Email design: {brandDesign?.configured
            ? `${brandContext?.brandName || "Your store"} approved design`
            : "not set up yet"}
          <span className="voice-chip-toggle">{designOpen ? "Hide" : "Design details"}</span>
        </button>
        {designOpen ? (
          <div className="voice-chip-body">
            {brandDesign?.configured ? (
              <p>
                Configured for your store
                {brandDesign.active?.version ? `, version ${brandDesign.active.version}` : ""}
                {brandDesign.active?.approvedAt
                  ? `, approved ${new Date(brandDesign.active.approvedAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`
                  : ""}.
                {" "}Contact your pilot contact for design changes.
              </p>
            ) : (
              <p>Your store's email design isn't set up yet. Your pilot contact needs to finish setup.</p>
            )}
          </div>
        ) : null}
      </div>

      {/* C4d: brand voice collapsed to a single line, expandable inline. */}
      {brandContext ? (
        <div className="voice-chip">
          <button type="button" className="voice-chip-line" onClick={() => setVoiceOpen((p) => !p)}>
            Writing style: {brandContext.brandName} · {brandContext.category}
            <span className="voice-chip-toggle">{voiceOpen ? "Hide" : "Details"}</span>
          </button>
          {voiceOpen ? (
            <div className="voice-chip-body">
              <p>
                Using {brandContext.productLanguage?.bestSellers?.[0]?.title || "top products"}
                {brandContext.productLanguage?.productTypes?.[0]?.name ? `, ${brandContext.productLanguage.productTypes[0].name}` : ""}
                {" "}and store words like {(brandContext.messaging?.useWords || []).slice(0, 5).join(", ") || "catalog language"}.
              </p>
              <button type="button" className="btn small" onClick={onRefreshBrandContext}>Refresh</button>
            </div>
          ) : null}
        </div>
      ) : null}

      {klaviyoFailed ? (
        <div className="notice-line">Couldn't reach Klaviyo for your existing templates — using BeaconAI starting copy.</div>
      ) : null}

      {/* Starting copy chooses WORDS. It is deliberately compact and secondary:
          the pilot has one approved design per store, and this must not read as
          a template picker. */}
      <div className="starting-copy">
        <span className="starting-copy-line">
          Starting copy: <strong>{startingName}</strong>
          <button type="button" className="link-btn" onClick={() => setChangeOpen((p) => !p)}>
            Change starting copy
          </button>
          {saveLabel ? (
            <span className={`save-state ${saveState}`} role="status">
              {saveLabel}
              {saveState === "failed" && onRetrySave ? (
                <button type="button" className="link-btn" onClick={onRetrySave}>Retry save</button>
              ) : null}
            </span>
          ) : null}
        </span>
        {changeOpen ? (
          <div className="starting-copy-options">
            {beaconTemplates.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`radio-card ${selectedTemplate?.id === item.id ? "selected" : ""}`}
                onClick={() => { onChooseTemplate(item.id); setChangeOpen(false); }}
              >
                <strong>{item.name}</strong>
                <small>{item.previewText}</small>
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {draft ? (
        <div className="review-two-pane">
          <div className="review-edit-pane">
            {/* Narrow screens only: the preview sits below the fields, so give
                keyboard and touch users a way to it without scrolling past
                every input. */}
            <a className="preview-jump link-btn" href="#campaign-email-preview">View preview</a>
            {/* adopt #3: one merchant-facing "why" line above the fields. LLM-authored
                + guarded server-side; shown only when present. */}
            {agentCopy?.rationale ? (
              <p className="copy-rationale">{agentCopy.rationale}</p>
            ) : null}

            {/* adopt #1/#4: rewrite regenerates only agent-written (Suggested) fields,
                never a merchant edit. Optional steer chips nudge the rewrite. */}
            {onRewrite ? (() => {
              const allEdited = editFields.every(
                ({ field }) => (draft[field] || "") !== (suggestedValueForField(play, field, agentCopy) || "")
              );
              return (
                <div className="copy-rewrite-row">
                  <div className="steer-chips" role="group" aria-label="Rewrite style">
                    {["Shorter", "Warmer", "More direct"].map((label) => (
                      <button
                        key={label}
                        type="button"
                        className={`steer-chip ${steer === label ? "active" : ""}`}
                        disabled={copyLoading || allEdited}
                        onClick={() => setSteer((prev) => (prev === label ? null : label))}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="btn small rewrite-btn"
                    disabled={copyLoading || allEdited}
                    title={allEdited ? "All fields are yours — restore a field to rewrite it." : undefined}
                    onClick={() => onRewrite(steer ? steer.toLowerCase() : null)}
                  >
                    {copyLoading ? "Writing…" : "Rewrite"}
                  </button>
                </div>
              );
            })() : null}

            {/* adopt #9: the agent reads as a copywriter, not a system. No "AI",
                no "generating", no "validation". Just the honest activity line. */}
            {copyLoading ? (
              <div className="copy-shimmer-line">Writing your copy from your store's data…</div>
            ) : null}

            {/* adopt #5: subject variant chips, pre-selected to variant 1 (already
                in the subject field). Tapping swaps; a hand-edited subject deselects. */}
            {subjectVariants.length > 1 ? (
              <div className="subject-variants" role="group" aria-label="Subject options">
                {subjectVariants.map((variant) => (
                  <button
                    key={variant}
                    type="button"
                    className={`subject-chip ${draft.subject === variant ? "active" : ""}`}
                    onClick={() => onChange("subject", variant)}
                  >
                    {variant}
                  </button>
                ))}
              </div>
            ) : null}

            {editFields.map(({ field, label, type }) => {
              // CA-4 #2: a field carries the "Edited" badge only when the merchant
              // changed it from what the AGENT wrote (quiet Suggested, loud Edited).
              // Agent-written & untouched → no badge.
              const edited = (draft[field] || "") !== (suggestedValueForField(play, field, agentCopy) || "");
              return (
              <label key={field} className="review-field">
                <span className="review-field-head">
                  <span className="review-field-label">
                    {label}
                    {edited ? <span className="edited-chip">Edited</span> : null}
                  </span>
                  {edited ? (
                    <button type="button" className="restore-link" onClick={() => onRestoreField(field)}>
                      Restore suggested
                    </button>
                  ) : null}
                </span>
                {type === "textarea" ? (
                  <textarea
                    value={draft[field] || ""}
                    rows={field === "bodyP1" ? 4 : 3}
                    onChange={(event) => onChange(field, event.target.value)}
                    onBlur={handleBlur}
                  />
                ) : (
                  <input
                    value={draft[field] || ""}
                    onChange={(event) => onChange(field, event.target.value)}
                    onBlur={handleBlur}
                  />
                )}
              </label>
            );
            })}

            {/* Directly below Button label: the button's text and where it goes
                are one decision. An empty input is not the same as "no link" —
                the design can supply a default, so the EFFECTIVE link is shown
                rather than left for the merchant to infer from a blank box. */}
            {onChangeDestination ? (
              <label className="review-field" ref={destinationFieldRef}>
                <span className="review-field-head">
                  <span className="review-field-label">Button destination</span>
                </span>
                <input
                  type="url"
                  inputMode="url"
                  placeholder="https://yourstore.example/collections/..."
                  value={destinationUrl || ""}
                  aria-invalid={destinationInvalid ? "true" : undefined}
                  aria-describedby="destination-help"
                  onChange={(event) => onChangeDestination(event.target.value)}
                  onBlur={handleBlur}
                />
                <span className="review-field-help" id="destination-help">
                  {destinationInvalid
                    ? "Enter a valid http:// or https:// link."
                    : effectiveDestination
                      ? <>Where the email button takes customers. Currently: <code>{effectiveDestination}</code></>
                      : "Add a destination for this button."}
                </span>
              </label>
            ) : null}

            {/* The Klaviyo template picker that used to live here is gone. The
                pilot has ONE approved design per store, configured by the
                founder; offering a visual-template choice alongside it implied
                the merchant could change the email's design here, and that two
                different things — words and branding — were the same control. */}
          </div>

          <div className="review-preview-pane" id="campaign-email-preview">
            {/* Wireframe order: [Email] [Inbox], then [Desktop] [Mobile]. Email
                is first because it is the default and the thing the merchant has
                to recognise; the inbox row is a subject line, not the email. */}
            <div className="preview-toggle" role="tablist" aria-label="Preview mode">
              <button
                type="button"
                role="tab"
                aria-selected={previewMode === "email"}
                className={`preview-toggle-btn ${previewMode === "email" ? "active" : ""}`}
                onClick={() => setPreviewMode("email")}
              >
                Email
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={previewMode === "inbox"}
                className={`preview-toggle-btn ${previewMode === "inbox" ? "active" : ""}`}
                onClick={() => setPreviewMode("inbox")}
              >
                Inbox
              </button>
            </div>
            {previewMode === "email" ? (
              <div className="preview-viewport" role="group" aria-label="Preview width">
                {["desktop", "mobile"].map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={`preview-viewport-btn ${previewViewport === mode ? "active" : ""}`}
                    aria-pressed={previewViewport === mode}
                    onClick={() => setPreviewViewport(mode)}
                  >
                    {mode === "desktop" ? "Desktop" : "Mobile"}
                  </button>
                ))}
              </div>
            ) : null}

            {/* Persistent, beside the work it affects, and it stays until the
                preview is actually current. The whole risk here is a merchant
                approving a picture of an email that is not the email their
                customers would receive. */}
            <div
              className={`preview-status ${freshness.state}`}
              role="status"
              aria-live="polite"
            >
              <span className="preview-status-icon" aria-hidden="true">
                {freshness.state === PREVIEW_STATE.fresh ? "✓" : freshness.blocksCreation ? "⚠" : ""}
              </span>
              {/* A field-specific refusal names the field. "We couldn't update
                  the preview" would send the merchant looking for a network
                  problem when the answer is a missing link. */}
              {previewProblem
                ? (previewProblem.code === "missing_destination"
                    ? "Add a destination for this button."
                    : previewProblem.message)
                : freshness.message}
              {!previewProblem && freshness.action ? (
                <button type="button" className="link-btn" onClick={() => refreshPreview(draft)}>
                  {freshness.action}
                </button>
              ) : null}
              {previewProblem?.slot === "cta_url" ? (
                <button type="button" className="link-btn" onClick={focusDestination}>
                  Edit destination
                </button>
              ) : null}
            </div>
            <div className={`phone-frame ${previewMode === "email" && previewViewport === "mobile" ? "preview-frame-mobile" : ""}`}>
              {previewMode === "inbox" ? (
                <div className="phone-inbox">
                  {/* P-A4: this is the customer's mail app, not the brand — static label. */}
                  <div className="phone-inbox-title">Inbox</div>
                  {/* The merchant's email as the top row — the open/no-open decision. */}
                  <div className="inbox-mail-row unread">
                    <span className="inbox-mail-dot" aria-hidden="true" />
                    <div className="inbox-mail-main">
                      <div className="inbox-mail-toprow">
                        <span className="inbox-mail-sender">{senderName}</span>
                        <span className="inbox-mail-time">now</span>
                      </div>
                      <div className="inbox-mail-subject">{draft.subject || "(no subject)"}</div>
                      <div className="inbox-mail-preview">{draft.previewText || "(no preview text)"}</div>
                    </div>
                  </div>
                  {/* Dummy rows for realism — make the merchant's row read as one of many. */}
                  {[
                    { sender: "Orders", subject: "Your receipt", preview: "Thanks for your purchase — here's your order summary.", time: "9:41 AM" },
                    { sender: "Community", subject: "This week's picks", preview: "Fresh arrivals and a few things we think you'll like.", time: "Yesterday" },
                  ].map((row) => (
                    <div key={row.sender} className="inbox-mail-row">
                      <span className="inbox-mail-dot placeholder" aria-hidden="true" />
                      <div className="inbox-mail-main">
                        <div className="inbox-mail-toprow">
                          <span className="inbox-mail-sender muted">{row.sender}</span>
                          <span className="inbox-mail-time">{row.time}</span>
                        </div>
                        <div className="inbox-mail-subject muted">{row.subject}</div>
                        <div className="inbox-mail-preview">{row.preview}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="phone-email">
                  {/* Mail-client header bar — where the subject appears above the body. */}
                  <div className="phone-email-header">
                    <div className="phone-email-sender">{senderName}</div>
                    <div className="phone-email-subject">{draft.subject || "(no subject)"}</div>
                  </div>
                  <iframe
                    title="Rendered email preview"
                    className="phone-frame-iframe"
                    srcDoc={previewHtml}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function BriefingStatStrip({ products, customers, orders, reviewPending, campaignsPending, ordersSeries, customersSeries }) {
  // D1: metric tiles — micro label above a 22px value. Accent when actionable > 0.
  const items = [
    { label: "Products", value: products },
    { label: "Customers", value: customers, series: customersSeries, seriesTone: "muted" },
    { label: "Orders", value: orders, series: ordersSeries, seriesTone: "accent" },
    { label: "Needs review", value: reviewPending, accentWhenPositive: true },
    { label: "In pipeline", value: campaignsPending, accentWhenPositive: true },
  ];
  return (
    <div className="briefing-stat-strip">
      {items.map(({ label, value, accentWhenPositive, series, seriesTone }) => (
        <div key={label} className="briefing-stat metric-tile">
          <span className="metric-tile-label">{label}</span>
          <strong className={accentWhenPositive && Number(value) > 0 ? "metric-tile-value accent" : "metric-tile-value"}>
            <MetricValue value={value} />
          </strong>
          {series && series.length > 1 ? <Sparkline points={series} tone={seriesTone} /> : null}
        </div>
      ))}
    </div>
  );
}

// D4: metric value with count-up. Non-numeric (e.g. "—") renders as-is.
function MetricValue({ value }) {
  const numeric = typeof value === "number" || (typeof value === "string" && value !== "" && Number.isFinite(Number(value)));
  const animated = useCountUp(numeric ? Number(value) : NaN);
  if (!numeric) return <>{value}</>;
  return <>{animated.toLocaleString()}</>;
}

// D6b: tiny inline sparkline (110×26, no axes). Points are numbers.
function Sparkline({ points, tone = "accent" }) {
  const w = 110, h = 26, pad = 2;
  const max = Math.max(...points), min = Math.min(...points);
  const span = max - min || 1;
  const step = (w - pad * 2) / (points.length - 1);
  const coords = points.map((p, i) => {
    const x = pad + i * step;
    const y = h - pad - ((p - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg className={`sparkline ${tone}`} width={w} height={h} viewBox={`0 0 ${w} ${h}`} fill="none" aria-hidden="true">
      <polyline points={coords} stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// PERSISTENT data-provenance state. Deliberately not a toast: a toast says
// "this went wrong" once and then the screen looks normal again, which is
// exactly wrong for a briefing that is still on screen and no longer trustworthy.
// This stays up until the underlying state changes.
function DataStateBanner({ syncStatus, busy, onSync }) {
  if (!syncStatus) return null;

  const { ready, reasons = [], active, latest, analysis } = syncStatus;
  const blocking = reasons[0] || null;

  // Ordered by what the merchant most needs to know. A stale or unverifiable
  // briefing outranks a failed sync, because the briefing is the thing they are
  // currently reading.
  let tone = null;
  let title = null;
  let detail = null;

  if (analysis?.provenance === "fixture") {
    tone = "warn";
    title = "This is a sample briefing";
    detail = "It was generated from demo data, not from your store. Campaigns from it cannot be sent.";
  } else if (analysis?.provenance === "predates_timezone_fix") {
    tone = "warn";
    title = "This briefing needs refreshing";
    detail = "It was computed over order dates stored without a time zone, so its analysis windows may be shifted by up to a day. Refresh the briefing before sending anything from it.";
  } else if (analysis?.provenance === "legacy_unverified") {
    tone = "warn";
    title = "This briefing's data can't be verified";
    detail = "It predates verified sync, so we can't confirm the store data behind it was complete. Re-sync and refresh the briefing before sending anything from it.";
  } else if (analysis?.provenance === "verified_stale") {
    tone = "info";
    title = "This briefing is from an earlier sync";
    detail = "Your store has been synced again since. Refresh the briefing to analyse the newer data.";
  } else if (!ready && blocking) {
    tone = "warn";
    title = blocking.code === "sync_running" ? "Sync in progress" : "Store data needs attention";
    detail = blocking.message;
  }

  const failures = latest?.validationFailures || [];
  const coverage = active?.coverage;

  if (!tone && !failures.length) return null;
  if (!tone) {
    tone = "warn";
    title = "Last sync came back incomplete";
    detail = failures[0].message;
  }

  return (
    <div className={`data-state-banner ${tone}`} role="status">
      <div className="data-state-main">
        <strong>{title}</strong>
        <span>{detail}</span>
        {coverage?.known && (
          <span className="data-state-meta">
            Analysing {coverage.daysCovered} days of order history
            {coverage.meetsPreferred ? "" : coverage.meetsRequired ? " (under 180 days, so yearly figures are extrapolated)" : ""}
            {coverage.residual?.orders > 0
              ? ` · ${coverage.residual.orders} older order${coverage.residual.orders === 1 ? "" : "s"} held as history, not analysed`
              : ""}
          </span>
        )}
      </div>
      {onSync && blocking?.code !== "sync_running" ? (
        <button className="btn small" onClick={onSync} disabled={busy}>
          {busy ? "Syncing…" : "Re-sync store"}
        </button>
      ) : null}
    </div>
  );
}

function OnboardingBanner({ status, hasStoreSnapshot, approvedCount, readyToFinish, busy = false, onConnectShopify, onSyncShopify, onConnectKlaviyo, onLoadTemplates, onFinish }) {
  const steps = [
    { label: "Shopify", done: Boolean(status.shopify && hasStoreSnapshot) },
    { label: "Klaviyo", done: Boolean(status.klaviyo) },
    { label: "First campaign", done: Boolean(approvedCount) },
  ];
  const doneCount = steps.filter((step) => step.done).length;

  let nextAction = null;
  if (!status.shopify) nextAction = { label: "Connect Shopify", onClick: onConnectShopify };
  else if (!hasStoreSnapshot) nextAction = { label: "Sync Shopify", onClick: onSyncShopify };
  else if (!status.klaviyo) nextAction = { label: "Connect Klaviyo", onClick: onConnectKlaviyo };
  else if (!approvedCount) nextAction = { label: "Approve a play below", onClick: null };

  return (
    <div className="onboarding-strip">
      <span className="onboarding-strip-label">Getting started · {doneCount} of {steps.length}</span>
      <div className="onboarding-strip-steps">
        {steps.map((step) => (
          <span key={step.label} className={`onboarding-chip ${step.done ? "done" : ""}`}>
            {step.done ? "✓ " : ""}{step.label}
          </span>
        ))}
      </div>
      {readyToFinish ? (
        <button className="btn primary" onClick={onFinish}>Finish setup</button>
      ) : nextAction?.onClick ? (
        <button className="btn primary" onClick={nextAction.onClick} disabled={busy}>
          {busy && nextAction.label === "Sync Shopify" ? "Syncing…" : nextAction.label}
        </button>
      ) : nextAction ? (
        <span className="onboarding-strip-hint">{nextAction.label}</span>
      ) : null}
    </div>
  );
}

function money(value, { cents = false } = {}) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const digits = cents || abs < 10 ? 2 : 0;
  return `${n < 0 ? "-" : ""}$${abs.toLocaleString("en-US", {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  })}`;
}

// A range, drawn to scale, with the estimate marked and zero shown. The point of
// the chart is that an interval crossing zero LOOKS like it crosses zero — the
// reader should not have to parse small grey text under a large green number to
// learn that the result is uncertain.
function IntervalBar({ low, high, point, tone = "null" }) {
  const span = Math.max(Math.abs(low), Math.abs(high), 1e-9) * 1.25;
  const pos = (v) => `${((v + span) / (2 * span)) * 100}%`;
  return (
    <div className={`interval interval-${tone}`}>
      <div className="interval-track">
        <span className="interval-axis" />
        <span className="interval-range" style={{ left: pos(low), width: `calc(${pos(high)} - ${pos(low)})` }} />
        <span className="interval-zero" style={{ left: pos(0) }} />
        <span className="interval-point" style={{ left: pos(point) }} />
      </div>
      <div className="interval-labels">
        <span>{money(low)}</span>
        <span>{money(high)}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Results — Ticket G, as specified in RESULTS_UI_SPEC.md.
//
// Every figure, date and sentence in an expanded result comes from ONE window
// entry of the API response, so the detail can never mix windows. The row always
// shows the 30-day window and says so. Assessments are typed by the API; nothing
// here infers a verdict from numbers.
// ---------------------------------------------------------------------------

const RESULT_WINDOWS = [30, 60, 90];

// Colour only for a supported higher/lower result (§6.2).
const ASSESSMENT_CHIP = {
  measuring: { label: "Measuring", tone: "warn" },
  insufficient_data: { label: "Insufficient data", tone: "null" },
  awaiting_order_data: { label: "Comparison unavailable", tone: "null" },
  no_holdout: { label: "Comparison unavailable", tone: "null" },
  assessment_policy_pending: { label: "Comparison unavailable", tone: "null" },
  not_calculated: { label: "Comparison unavailable", tone: "null" },
  higher_spending: { label: "Higher spending", tone: "pos" },
  lower_spending: { label: "Lower spending", tone: "neg" },
  no_clear_difference: { label: "No clear difference", tone: "null" },
};
const UNKNOWN_CHIP = { label: "Comparison unavailable", tone: "null" };

// Why a handed-off campaign has no results yet. The delivery label itself comes
// from presentDelivery, so Results and Campaigns say the same thing.
const UNMEASURED_NOTE = {
  send_not_confirmed: "Results start once Klaviyo confirms the send.",
  send_time_unknown: "Klaviyo reports this as sent but not when, so results can't start yet.",
  no_provider_record: "Marked sent in BeaconAI, but Klaviyo hasn't confirmed a send, so results can't be measured.",
};

const PROGRAM_BAND_TEXT =
  "Program comparison isn't available yet. Campaign-level observations appear below; they should not be added together.";
const OTHER_MARKETING_NOTE = "Your other marketing may also affect these results.";
// Exposure matching uses recorded customer ids; a person known by two ids can
// be missed. Always said, so "no note" is never read as "no other exposure".
const EXPOSURE_CAVEAT = "Other BeaconAI campaign exposure may not be fully identified.";
const SAMPLE_BANNER = "Sample data — illustrative results";
const EXPOSURE_NOTE = {
  present: "These customers may have been included in other BeaconAI campaigns. This comparison does not isolate this email's effect.",
  unknown: "Other BeaconAI campaigns may have reached these customers; their send times aren't confirmed, so this comparison does not isolate this email's effect.",
};

function formatDay(value, { time = false } = {}) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    ...(time ? { hour: "numeric", minute: "2-digit" } : {}),
  });
}

function relativeAge(value, now = Date.now()) {
  const ms = now - new Date(value).getTime();
  if (!Number.isFinite(ms)) return null;
  const hours = Math.round(ms / 3600000);
  if (hours < 48) return `${Math.max(hours, 1)} hour${hours === 1 ? "" : "s"}`;
  return `${Math.round(hours / 24)} days`;
}

function perCustomer(value) {
  return value == null ? "—" : money(value, { cents: true });
}

function signedMoney(value) {
  return `${value >= 0 ? "+" : "−"}${money(Math.abs(value), { cents: true })}`;
}

function countOrDash(value) {
  return value == null ? "—" : Number(value).toLocaleString("en-US");
}

function Chip({ label, tone }) {
  return <span className={`verdict verdict-${tone}`}><span className="verdict-dot" aria-hidden="true" />{label}</span>;
}

function assessmentSentence(w, source) {
  switch (w?.assessment?.state) {
    case "measuring":
      return `Still measuring. Review the ${w.windowDays}-day result on ${formatDay(w.end)}.`;
    case "insufficient_data":
      return "Too few customers or purchasers in one group to compare them.";
    case "awaiting_order_data":
      return w.assessment.reasons.includes("no_successful_sync")
        ? "This window has ended, but there's no successful store sync to check it against. Re-sync the store to complete it."
        : `This window ended ${formatDay(w.end)}, but order data only runs to ${formatDay(source?.ordersCoveredThrough)}. Re-sync the store to complete it.`;
    case "no_holdout":
      return "No customers were held back, so there's nothing to compare against.";
    case "assessment_policy_pending":
      return "Group figures are shown as observations. A comparison isn't reported yet.";
    case "not_calculated":
      return w.assessment.reasons.includes("mixed_calculation")
        ? "This window's stored figures come from different calculations, so they aren't shown. Recalculate to refresh them."
        : "This window hasn't been calculated yet.";
    case "higher_spending":
      return "Customers assigned to receive the campaign spent more per customer. The 95% range is above zero for this window.";
    case "lower_spending":
      return "Customers assigned to receive the campaign spent less per customer. The 95% range is below zero for this window.";
    case "no_clear_difference":
      return "The result isn't clear. The 95% range includes both lower and higher spending.";
    default:
      return "";
  }
}

// Program band (Ticket H placement). No figure of any kind until H ships.
function ProgramBand() {
  return (
    <div className="program-band" role="note">
      <span className="program-label">Program</span>
      <p className="program-note">{PROGRAM_BAND_TEXT}</p>
    </div>
  );
}

// Store-data freshness, independent of when anything was calculated.
function SourceNotice({ source, onResync, busy }) {
  if (!source || !source.stale) return null;
  const text = source.reason === "no_successful_sync"
    ? "No successful store sync, so results can't be checked against complete order data."
    : `Store data last synced ${relativeAge(source.lastSuccessfulSyncAt)} ago. Results can't include orders since then.`;
  return (
    <div className="data-state-banner warn" role="status">
      <div className="data-state-main"><strong>Store data is out of date</strong><span>{text}</span></div>
      {onResync ? <button type="button" className="btn small" onClick={onResync} disabled={busy}>{busy ? "Syncing…" : "Re-sync store"}</button> : null}
    </div>
  );
}

// The collapsed row's figure — always the 30-day window, always labelled.
function ThirtyDayBlock({ w }) {
  let main = "—";
  let sub = null;
  if (w?.comparison) {
    main = `${signedMoney(w.comparison.difference)} / customer`;
    sub = `${signedMoney(w.comparison.low)} to ${signedMoney(w.comparison.high)}`;
  } else if (w?.assigned) {
    main = w.assessment.state === "measuring" ? "Early observation" : null;
    sub = (
      <>
        <span>Assigned to receive {perCustomer(w.assigned.revenuePerCustomer)}</span>
        <span>Held back {perCustomer(w.heldBack?.revenuePerCustomer)}</span>
      </>
    );
  }
  return (
    <span className="result-30">
      <span className="result-30-label">30-day result</span>
      {main ? <span className="result-30-main">{main}</span> : null}
      {sub ? <span className="result-30-sub">{sub}</span> : null}
      {w?.assessment?.state === "measuring" ? <span className="result-30-sub">day {w.daysElapsed} of {w.windowDays}</span> : null}
    </span>
  );
}

function Disclosure({ label, children, onOpen }) {
  const [open, setOpen] = useState(false);
  const id = useRef(`disclosure-${Math.random().toString(36).slice(2)}`).current;
  return (
    <div className="disclosure">
      <button
        type="button"
        className="disclosure-btn"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => { if (!open && onOpen) onOpen(); setOpen(!open); }}
      >
        <span aria-hidden="true">{open ? "▾" : "▸"}</span>{label}
      </button>
      {open ? <div id={id} className="disclosure-body">{children}</div> : null}
    </div>
  );
}

// What was sent and why it was suggested — the frozen email and the
// recommendation from the campaign's ORIGINATING run. Loaded when opened.
function OriginalCampaign({ campaignId }) {
  const [state, setState] = useState({ status: "idle" });
  const load = () => {
    setState({ status: "loading" });
    api.campaignOriginal(campaignId)
      .then((data) => setState({ status: "ready", data }))
      .catch((err) => setState({ status: "error", message: err.message }));
  };
  const data = state.data;
  const copy = data?.approvedCopy || {};
  const rec = data?.recommendation;
  const change = rec?.observedChange ? formatChange(rec.observedChange) : null;
  return (
    <Disclosure label="Original campaign" onOpen={() => { if (state.status === "idle") load(); }}>
      {state.status === "loading" ? <p>Loading the original campaign…</p> : null}
      {state.status === "error" ? (
        <p className="result-warn" role="alert">
          Couldn't load the original campaign.
          <button type="button" className="btn small" onClick={load}>Try again</button>
        </p>
      ) : null}
      {state.status === "ready" ? (
        <>
          {!data.approvedCopy && !data.renderedHtml ? <p>The original email wasn't stored for this campaign.</p> : null}
          {copy.subject ? <p><strong>Subject</strong> · {copy.subject}</p> : null}
          {copy.previewText ? <p><strong>Preview text</strong> · {copy.previewText}</p> : null}
          {data.destinationUrl ? (
            <p><strong>Button link</strong> · <a href={data.destinationUrl} target="_blank" rel="noopener noreferrer">{data.destinationUrl}</a></p>
          ) : null}
          {data.renderedHtml ? (
            <>
              {/* C-UI's wording: this is the handoff snapshot. The merchant can
                  still edit the draft in Klaviyo, and nothing here reads back
                  what Klaviyo finally sent. */}
              <p>
                <strong>Handoff email</strong> · Email handed to Klaviyo
                {data.frozenAt ? ` on ${formatDay(data.frozenAt, { time: true })}` : ""}. Changes made later in Klaviyo aren't reflected here.
              </p>
              <iframe className="original-email-frame" title="Handoff email" sandbox="" srcDoc={data.renderedHtml} />
            </>
          ) : null}
          <p><strong>Why it was suggested</strong></p>
          {rec ? (
            <ul className="result-notes">
              <li>{rec.playName}{rec.evidenceLine ? ` — ${rec.evidenceLine}` : ""}</li>
              {change ? <li>{change.label}: {change.value}{change.note ? ` (${change.note})` : ""}</li> : null}
              {rec.audienceSize != null ? <li>{Number(rec.audienceSize).toLocaleString("en-US")} customers{rec.audienceDefinition ? ` · ${rec.audienceDefinition}` : ""}</li> : null}
            </ul>
          ) : <p>Recommendation details aren't available for this campaign's analysis.</p>}
        </>
      ) : null}
    </Disclosure>
  );
}

function ResultDetail({ result, onRetry }) {
  const [windowDays, setWindowDays] = useState(30);
  const ref = useRef(null);
  useEffect(() => { ref.current?.focus(); }, []);
  const windows = result.windows || [];
  const w = windows.find((x) => x.windowDays === windowDays) || windows[0];
  const chip = ASSESSMENT_CHIP[w?.assessment?.state] || UNKNOWN_CHIP;
  const count = result.delivery?.providerSentCount;
  const exposureNote = EXPOSURE_NOTE[w?.otherExposure?.status] || null;
  const detailId = `result-detail-${result.campaignId}`;

  return (
    <div id={detailId} className="result-detail" role="region" aria-label={`Result details, ${windowDays} days`} tabIndex={-1} ref={ref}>
      <div className="result-meta">
        <span>Sent {formatDay(result.sentAt, { time: true })}, confirmed by Klaviyo</span>
        <span>{count == null ? "Sent count unavailable" : `Klaviyo sent ${count.toLocaleString("en-US")}`}</span>
      </div>

      <fieldset className="window-radios">
        <legend>Window</legend>
        {RESULT_WINDOWS.map((days) => {
          const entry = windows.find((x) => x.windowDays === days);
          return (
            <label key={days} className="window-radio">
              <input
                type="radio"
                name={`window-${result.campaignId}`}
                value={days}
                checked={windowDays === days}
                onChange={() => setWindowDays(days)}
              />
              {days} days{entry && !entry.complete ? " · open" : ""}
            </label>
          );
        })}
      </fieldset>

      {w ? (
        <>
          <div className="result-meta">
            <span>{formatDay(w.start)} – {formatDay(w.end)} · {w.complete ? "complete" : `day ${w.daysElapsed} of ${w.windowDays}`}</span>
            <span>
              Last successful sync {formatDay(result.source?.lastSuccessfulSyncAt, { time: true }) || "not available"}
              {" · "}Calculated {formatDay(w.calculatedAt, { time: true }) || "not yet"}
              {w.calculatedFrom?.lastSuccessfulSyncAt ? ` from the store sync of ${formatDay(w.calculatedFrom.lastSuccessfulSyncAt, { time: true })}` : ""}
            </span>
          </div>
          {w.sourceSuperseded ? (
            <p className="result-warn" role="status">
              Newer store data is available. These figures still use the sync from {formatDay(w.calculatedFrom?.lastSuccessfulSyncAt, { time: true }) || "an earlier sync"}.
              {!result.calculationFailed ? <button type="button" className="btn small" onClick={onRetry}>Recalculate</button> : null}
            </p>
          ) : null}
          {w.calculatedFrom?.stale ? (
            <p className="result-warn">The store data behind these figures is over 24 hours old, so recent orders may be missing from this window.</p>
          ) : null}
          {result.calculationFailed ? (
            <p className="result-warn" role="alert">
              Couldn't recalculate. Showing the result calculated {formatDay(w.calculatedAt, { time: true }) || "earlier"}.
              <button type="button" className="btn small" onClick={onRetry}>Try again</button>
            </p>
          ) : w.calculationStale && w.calculatedAt ? (
            <p className="result-warn">
              Last calculated {relativeAge(w.calculatedAt)} ago.
              <button type="button" className="btn small" onClick={onRetry}>Recalculate</button>
            </p>
          ) : null}

          <p className="result-outcome"><Chip {...chip} /> {assessmentSentence(w, result.source)}</p>

          {w.assigned ? (
            <div className="result-comparison">
              {w.assessment.state === "measuring" ? <span className="result-early">Early observation</span> : null}
              <span>Assigned to receive <strong>{perCustomer(w.assigned.revenuePerCustomer)}</strong> per customer</span>
              <span>Held back <strong>{perCustomer(w.heldBack?.revenuePerCustomer)}</strong> per customer</span>
              {w.comparison ? (
                <span>
                  Difference <strong>{signedMoney(w.comparison.difference)}</strong> per customer
                  {" "}(95% range {signedMoney(w.comparison.low)} to {signedMoney(w.comparison.high)})
                </span>
              ) : null}
            </div>
          ) : null}
          {w.comparison ? (
            <IntervalBar
              low={w.comparison.low} high={w.comparison.high} point={w.comparison.difference}
              tone={chip.tone === "pos" ? "pos" : chip.tone === "neg" ? "neg" : "null"}
            />
          ) : null}

          {w.assigned ? (
            <div className="group-table-wrap">
              <table className="group-table">
                <caption className="sr-only">Group figures for the {w.windowDays}-day window</caption>
                <thead>
                  <tr><td /><th scope="col">Assigned to receive</th><th scope="col">Held back</th></tr>
                </thead>
                <tbody>
                  <tr><th scope="row">Customers</th><td>{countOrDash(w.assigned.customers)}</td><td>{countOrDash(w.heldBack?.customers)}</td></tr>
                  <tr><th scope="row">Unique purchasers</th><td>{countOrDash(w.assigned.purchasers)}</td><td>{countOrDash(w.heldBack?.purchasers)}</td></tr>
                  <tr><th scope="row">Orders</th><td>{countOrDash(w.assigned.orders)}</td><td>{countOrDash(w.heldBack?.orders)}</td></tr>
                  <tr><th scope="row">Revenue, net of refunds</th><td>{w.assigned.revenue == null ? "—" : money(w.assigned.revenue, { cents: true })}</td><td>{w.heldBack?.revenue == null ? "—" : money(w.heldBack.revenue, { cents: true })}</td></tr>
                  <tr><th scope="row">Revenue per customer</th><td>{perCustomer(w.assigned.revenuePerCustomer)}</td><td>{perCustomer(w.heldBack?.revenuePerCustomer)}</td></tr>
                </tbody>
              </table>
            </div>
          ) : null}

          <ul className="result-notes">
            {exposureNote ? <li>{exposureNote}</li> : null}
            <li>{EXPOSURE_CAVEAT}</li>
            <li>{OTHER_MARKETING_NOTE}</li>
          </ul>

          <Disclosure label="How this is measured">
            <p>
              We compare customers assigned to receive this campaign with customers held back from it, from{" "}
              {formatDay(w.start)} to {formatDay(w.end)}. Revenue is net of refunds; cancelled and test orders are
              excluded. It is not profit. Customers Klaviyo did not deliver to stay in the assigned group.
            </p>
          </Disclosure>
        </>
      ) : null}

      <OriginalCampaign campaignId={result.campaignId} />
    </div>
  );
}

function ResultRow({ result, title, open, onToggle, onRetry }) {
  // Handed off but not confirmed by the provider: listed with the reason, never
  // dropped, and not expandable — there is nothing measured to show.
  if (result.measurable === false) {
    const delivery = presentDelivery(result.delivery ?? null);
    const note = result.deliveryState === "failed"
      ? "The draft wasn't created, so nothing was sent."
      : UNMEASURED_NOTE[result.reason] || "Not measured.";
    return (
      <div className="result-item">
        <div className="result-row result-row-pending">
          <span className="result-name">
            <strong>{title}</strong>
            <span>{note}</span>
          </span>
          <Chip label={delivery.label} tone="warn" />
          <span className="result-30">
            <span className="result-30-label">30-day result</span>
            <span className="result-30-sub">Starts at the confirmed send</span>
          </span>
          <span />
        </div>
      </div>
    );
  }

  const w30 = (result.windows || []).find((x) => x.windowDays === 30);
  const chip = ASSESSMENT_CHIP[w30?.assessment?.state] || UNKNOWN_CHIP;
  const detailId = `result-detail-${result.campaignId}`;
  return (
    <div className="result-item">
      <button
        type="button"
        className={`result-row ${open ? "open" : ""}`}
        aria-expanded={open}
        aria-controls={detailId}
        onClick={onToggle}
      >
        <span className="result-name">
          <strong>{title}</strong>
          <span>
            Sent {formatDay(result.sentAt)} · {countOrDash(result.assignment?.assigned)} assigned to receive
            {" · "}{countOrDash(result.assignment?.heldBack)} held back
          </span>
        </span>
        <Chip {...chip} />
        <ThirtyDayBlock w={w30} />
        <span className="result-chevron" aria-hidden="true">{open ? "▾" : "▸"}</span>
      </button>
      {open ? <ResultDetail result={result} onRetry={onRetry} /> : null}
    </div>
  );
}

function ResultsPage({ data, loading, error, openId, onToggle, onRetry, onLoadMore, onResync, resyncBusy, onGoToCampaigns, playTitleFor }) {
  const results = data?.results;
  if (loading && !results) return <div className="empty-panel">Loading results…</div>;
  if (error && !results) {
    return (
      <div className="empty-panel" role="alert">
        Couldn't load results. {error}{" "}
        <button type="button" className="btn small" onClick={onRetry}>Try again</button>
      </div>
    );
  }

  return (
    <div className="results-page">
      {data?.sampleData ? (
        // Persistent, first on the page: a screenshot shared without context
        // must still say these are not a store's real results.
        <div className="sample-banner" role="note">
          {SAMPLE_BANNER}. These campaigns and figures were generated for a demonstration, not taken from a real store.
        </div>
      ) : null}
      <div className="results-head">
        <h2>Campaign results</h2>
        <p>What happened after each campaign, compared with customers held back.</p>
      </div>
      <ProgramBand />
      {error ? (
        <div className="data-state-banner warn" role="status">
          <div className="data-state-main">
            <strong>Couldn't refresh results</strong>
            <span>Showing what was loaded {formatDay(data?.loadedAt, { time: true }) ? `at ${formatDay(data.loadedAt, { time: true })}` : "earlier"}.</span>
          </div>
          <button type="button" className="btn small" onClick={onRetry}>Try again</button>
        </div>
      ) : null}
      <SourceNotice source={data?.source} onResync={onResync} busy={resyncBusy} />

      {!results?.length ? (
        <div className="empty-panel">
          Results appear after your first campaign is created in Klaviyo.{" "}
          {onGoToCampaigns ? <button type="button" className="link-btn" onClick={onGoToCampaigns}>Go to Campaigns</button> : null}
        </div>
      ) : (
        <>
          <div className="ledger-head">
            <span className="program-label">Campaigns · newest first</span>
          </div>
          <div className="ledger">
            {results.map((result) => (
              <ResultRow
                key={result.campaignId}
                result={result}
                title={result.displayName || playTitleFor(result.playId)}
                open={openId === result.campaignId}
                onToggle={() => onToggle(result.campaignId)}
                onRetry={onRetry}
              />
            ))}
          </div>
          {data?.hasMore ? (
            <button type="button" className="btn" onClick={onLoadMore} disabled={loading}>
              {loading ? "Loading…" : "Show older campaigns"}
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}

function StoreGate({ draft, onDraftChange, onSubmit, error }) {
  return (
    <div className="store-gate">
      <div className="store-gate-inner">
        <div className="wordmark" aria-label="beacon">beac<span className="wordmark-dot" />n</div>
        <h1>Let's look at your store.</h1>
        <p className="store-gate-sub">Connect your Shopify store and BeaconAI will find your next revenue opportunities.</p>
        <form className="store-gate-form" onSubmit={onSubmit}>
          <input
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder="your-store.myshopify.com"
            autoFocus
          />
          <button className="btn primary" type="submit">Connect Shopify</button>
        </form>
        {error ? <div className="store-gate-error">{error}</div> : null}
      </div>
    </div>
  );
}

function FirstRunProgress({ stage, counts, orders, error, onRetry }) {
  const stageCopy = {
    syncing: { title: "Connecting your store…", sub: "Importing your products, customers, and orders from Shopify. First-time setup — this only happens once." },
    synced: { title: "Store connected.", sub: null },
    analyzing: {
      title: `Building your first briefing…`,
      sub: `Reading ${orders} orders to find your best campaigns and who to send them to. This takes a minute.`,
    },
  };

  if (error) {
    return (
      <div className="first-run-panel">
        <div className="first-run-inner">
          <p className="first-run-error">{error.message}</p>
          <button className="btn primary" onClick={onRetry}>Retry</button>
        </div>
      </div>
    );
  }

  const copy = stageCopy[stage] || stageCopy.syncing;
  const showStats = stage === "synced" && counts;

  return (
    <div className="first-run-panel">
      <div className="first-run-inner">
        {stage !== "synced" ? <div className="first-run-spinner" aria-hidden="true" /> : null}
        <h2>{copy.title}</h2>
        {copy.sub ? <p className="first-run-sub">{copy.sub}</p> : null}
        {showStats ? (
          <div className="first-run-stats">
            {counts.products} products · {counts.customers} customers · {counts.orders} orders
          </div>
        ) : null}
      </div>
    </div>
  );
}

// A moving progress indicator for the manual briefing refresh, so a run that
// takes a while never looks frozen the way the static "Working..." box did.
// Reuses the first-run spinner; cycles reassuring copy on a timer.
function BriefingWorking() {
  const messages = [
    "Refreshing with your latest orders…",
    "Finding your best campaigns this cycle…",
    "Sizing the audience for each one…",
    "Checking the evidence behind each play…",
    "Writing your briefing…",
  ];
  const [index, setIndex] = useState(0);
  useEffect(() => {
    // Advance but hold on the last message — the run may outlast the list.
    const id = setInterval(() => {
      setIndex((i) => Math.min(i + 1, messages.length - 1));
    }, 2200);
    return () => clearInterval(id);
  }, []);
  return (
    <div role="status" aria-live="polite">
      {/* Rotating caption ABOVE the skeleton cards — it labels what's being
          computed; the skeletons below occupy the recommendation cards' footprint
          so it's unambiguous where the result will land. */}
      <div className="briefing-skeleton-caption">
        <div className="first-run-spinner small" aria-hidden="true" />
        <span>{messages[index]}</span>
      </div>
      <div className="briefing-skeleton-cards" aria-hidden="true">
        <div className="skeleton skeleton-reccard" />
        <div className="skeleton skeleton-reccard" />
        <div className="skeleton skeleton-reccard" />
      </div>
    </div>
  );
}

// D4: count-up on mount (integers). Returns the display value; skips on reduced-motion.
function useCountUp(target, duration = 500) {
  const [value, setValue] = useState(0);
  const rafRef = useRef(null);
  useEffect(() => {
    const end = Number(target);
    if (!Number.isFinite(end)) { setValue(target); return undefined; }
    const reduce = typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || end === 0) { setValue(end); return undefined; }
    let startTs = null;
    const tick = (ts) => {
      if (startTs == null) startTs = ts;
      const p = Math.min(1, (ts - startTs) / duration);
      setValue(Math.round(end * p));
      if (p < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [target, duration]);
  return value;
}

export function App() {
  // A shared or refreshed Results link (`?campaign=<id>`) reopens that result.
  // Read once at mount; cleared as soon as the merchant navigates, so it only
  // decides where a page LOAD lands.
  const initialCampaignParam = useRef(
    Number.parseInt(new URLSearchParams(window.location.search).get("campaign") || "", 10) || null
  );
  const [activePage, setActivePage] = useState(initialCampaignParam.current ? "results" : "briefing");
  const [openResultId, setOpenResultId] = useState(initialCampaignParam.current);
  const [resultsLimit, setResultsLimit] = useState(100);
  const [resultsReload, setResultsReload] = useState(0);
  const [loading, setLoading] = useState(false);
  // Distinct from generic `loading`: true ONLY while a briefing recompute is in
  // flight (not sync). Drives the in-lane skeleton state so the store cards +
  // page shape persist and only the recommendations region shows loading.
  const [refreshingBriefing, setRefreshingBriefing] = useState(false);
  const [error, setError] = useState("");
  const [shopDomain, setShopDomain] = useState(api.shopDomain);
  const [shopDomainDraft, setShopDomainDraft] = useState(api.shopDomain);
  const [status, setStatus] = useState({ api: false, shopify: false, klaviyo: false, shopifySource: "none", klaviyoSource: "none" });
  const [sync, setSync] = useState(null);
  // Which sync the store data comes from, and whether the briefing on screen
  // was built from it. Drives DataStateBanner.
  const [syncStatus, setSyncStatus] = useState(null);
  const [engineInput, setEngineInput] = useState(null);
  const [brandContext, setBrandContext] = useState(null);
  const [atulEngineResult, setAtulEngineResult] = useState(null);
  const [klaviyoTemplates, setKlaviyoTemplates] = useState([]);
  // C3: true only when Klaviyo is connected but its template fetch failed/fell back.
  const [klaviyoTemplatesFailed, setKlaviyoTemplatesFailed] = useState(false);
  const [selectedTemplateByPlay, setSelectedTemplateByPlay] = useState({});
  const [draftEditsByPlay, setDraftEditsByPlay] = useState({});
  // CA-4: LLM-authored copy per play, keyed by play id. The "Suggested" value
  // for a field reads from here (falling back to static template_prompt) so the
  // Edited badge + edit-preserving rewrite know what the AGENT wrote vs. what the
  // MERCHANT edited (draftEditsByPlay). Persisted so it survives refresh (#8v1).
  const [agentCopyByPlay, setAgentCopyByPlay] = useState({});
  // Per-play copy-generation status: "loading" | "ready" | "static" (fell back).
  const [copyStatusByPlay, setCopyStatusByPlay] = useState({});
  // Explicit merchant sign-off (end of stepper) that moves a campaign from
  // "Needs review" to "Ready to send". Distinct from a template being selected,
  // which auto-happens on view and only means "has a draft".
  const [approvedForSend, setApprovedForSend] = useState([]);
  const [authorizedPackageIds, setAuthorizedPackageIds] = useState([]);
  const [klaviyoAssetsByCampaign, setKlaviyoAssetsByCampaign] = useState({});
  const [publishingCampaignId, setPublishingCampaignId] = useState("");
  const [sendingCampaignId, setSendingCampaignId] = useState("");
  const [audiencePreviewsByCampaign, setAudiencePreviewsByCampaign] = useState({});
  const [previewingCampaignId, setPreviewingCampaignId] = useState("");
  const [reviewPlayId, setReviewPlayId] = useState("");
  // C2: which stepper step (copy | audience | send) the workspace shows.
  const [workspaceStep, setWorkspaceStep] = useState("copy");
  const rightPaneRef = useRef(null);
  const [selectedBriefingPlayId, setSelectedBriefingPlayId] = useState("");
  const [onboardingHidden, setOnboardingHidden] = useState(() => localStorage.getItem("beaconai:onboarding-complete") === "true");
  const [campaignPackages, setCampaignPackages] = useState([]);
  // Per-play "saving" | "saved" | "failed" | "conflict". A silent write failure
  // used to leave the merchant editing a draft that was no longer being stored.
  const [saveStateByPlay, setSaveStateByPlay] = useState({});
  // Revision each play's campaign was last read at, for optimistic checks.
  const [revisionByPlay, setRevisionByPlay] = useState({});
  // The run each play's campaign actually belongs to — its origin, which is not
  // necessarily the current run.
  const [runIdByPlay, setRunIdByPlay] = useState({});
  // Campaigns from earlier runs, kept so the merchant can still find them.
  const [historicalCampaigns, setHistoricalCampaigns] = useState([]);
  // Ticket C: the brand shell version this shop currently sends with. A new
  // approved version makes every existing preview out of date.
  const [brandTemplateVersion, setBrandTemplateVersion] = useState(null);
  const [brandDesign, setBrandDesign] = useState(null);
  // Which shop, if any, this browser is actually signed in as. Independent of
  // whether the integration is connected.
  const [signedInShop, setSignedInShop] = useState(null);
  const [signedInChecked, setSignedInChecked] = useState(false);
  const [signInView, setSignInView] = useState({ state: "checking", needsSignIn: false, message: null });
  // Durable provider state per campaign, from the Ticket D contract. Never
  // inferred from local status — that is the whole point of the contract.
  const [deliveryByCampaignId, setDeliveryByCampaignId] = useState({});
  // Reported by the provider, or absent. Never derived from the store domain.
  const [senderIdentity, setSenderIdentity] = useState(null);
  const [campaignRowByPlay, setCampaignRowByPlay] = useState({});
  // The html the preview last rendered, lifted so the final review can show the
  // same email rather than a description of it.
  const [reviewPreviewHtmlByPlay, setReviewPreviewHtmlByPlay] = useState({});

  const loadDelivery = useCallback(async (campaignId) => {
    if (!campaignId) return null;
    try {
      const result = await api.campaignDelivery(campaignId);
      setDeliveryByCampaignId((prev) => ({ ...prev, [campaignId]: result.delivery }));
      return result.delivery;
    } catch (_) {
      // null, not undefined: "we tried and could not" is a state the presenter
      // renders as unavailable rather than as a fresh campaign.
      setDeliveryByCampaignId((prev) => ({ ...prev, [campaignId]: null }));
      // No durable state available is not the same as "nothing happened"; the
      // UI keeps whatever it last knew rather than claiming a fresh start.
      return null;
    }
  }, []);
  const [destinationByPlay, setDestinationByPlay] = useState({});
  // The rendering the merchant actually looked at, per play. Handoff sends this
  // back so approval binds to that email rather than to whatever renders later.
  const approvedRender = useRef({});
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  // D6b: weekly series for the Orders / Customers sparklines.
  const [statsSeries, setStatsSeries] = useState(null);
  // Transient confirmation toast: { message, actionLabel?, onAction? }.
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [shopDomainError, setShopDomainError] = useState("");
  const [latestRunChecked, setLatestRunChecked] = useState(false);
  const [latestRunFound, setLatestRunFound] = useState(false);
  // True when the latest-run fetch FAILED (vs a definitive "no run yet"). An error
  // must never be read as first-run — that would trigger a full re-sync on refresh.
  const [latestRunErrored, setLatestRunErrored] = useState(false);
  const [rehydrating, setRehydrating] = useState(Boolean(api.shopDomain));
  const [firstRunStage, setFirstRunStage] = useState(null); // null | syncing | synced | analyzing | done
  const [firstRunError, setFirstRunError] = useState(null); // { phase: "sync"|"engine", message }
  const [sparseInterstitialDismissed, setSparseInterstitialDismissed] = useState(false);
  const [restoredApprovedPlayIds, setRestoredApprovedPlayIds] = useState([]);
  const firstRunStartedRef = useRef(false);
  const pipelineHydratedRef = useRef(false);
  // playId -> campaigns.id, so a mutation can patch the row it already has.
  const [campaignIdByPlay, setCampaignIdByPlay] = useState({});
  const [resultsData, setResultsData] = useState(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsError, setResultsError] = useState("");

  const counts = sync?.synced || {};
  const currentRunId = atulEngineResult?.presentedRun?.run_id || null;
  // O3 fix: persist first-run completion per shop so a page refresh does not
  // re-trigger a full Shopify sync (which surfaced a false "sync hit a problem").
  const firstRunDoneKey = shopDomain ? `beaconai:${shopDomain}:first-run-complete` : null;
  // Briefing content cache — shop-keyed (no run_id needed at mount) so a browser
  // refresh repaints the last briefing instantly, independent of the server.
  const briefingCacheKey = shopDomain ? `beaconai:${shopDomain}:latest-briefing` : null;
  const workflowPlays = useMemo(
    () => buildWorkflowPlays({ atulEngineResult, campaignPackages }),
    [atulEngineResult, campaignPackages]
  );
  const reviewablePlays = useMemo(() => workflowPlays.filter((play) => classifyPlayLane(play) !== "considered"), [workflowPlays]);
  // Only plays the merchant explicitly approved in Briefing (greenlightEnginePlay
  // pushes them into campaignPackages) appear on the Campaigns page. reviewablePlays
  // is the full universe; the campaigns view is the approved subset.
  const approvedPlayIdSet = useMemo(() => new Set(campaignPackages.map((item) => item.id)), [campaignPackages]);
  const approvedPlays = useMemo(
    () => reviewablePlays.filter((play) => approvedPlayIdSet.has(play.play_id || play.id)),
    [reviewablePlays, approvedPlayIdSet]
  );
  const reviewPlay = approvedPlays.find((play) => play.id === reviewPlayId) || approvedPlays[0];
  const beaconTemplates = useMemo(() => klaviyoTemplates.filter((item) => item.source !== "klaviyo"), [klaviyoTemplates]);
  const klaviyoOnlyTemplates = useMemo(() => klaviyoTemplates.filter((item) => item.source === "klaviyo"), [klaviyoTemplates]);
  const selectedTemplate = reviewPlay ? klaviyoTemplates.find((item) => item.id === selectedTemplateByPlay[reviewPlay.id]) : null;
  // Memoized so the object identity only changes when its inputs do. Rebuilding
  // it every render is what let a preview response trigger the next request.
  const selectedDraft = useMemo(
    () => (reviewPlay && selectedTemplate
      ? buildCampaignFromSelection(reviewPlay, selectedTemplate, draftEditsByPlay[reviewPlay.id], agentCopyByPlay[reviewPlay.id], destinationByPlay[reviewPlay.id])
      : null),
    [reviewPlay, selectedTemplate, draftEditsByPlay, agentCopyByPlay, destinationByPlay]
  );
  const finalCampaigns = approvedPlays
    .map((play) => buildCampaignFromSelection(play, klaviyoTemplates.find((item) => item.id === selectedTemplateByPlay[play.id]), draftEditsByPlay[play.id], agentCopyByPlay[play.id], destinationByPlay[play.id]))
    .map((item) => {
      if (!item) return item;
      const asset = klaviyoAssetsByCampaign[item.id];
      // draft (in review) → approved (merchant signed off) → created (deployed to Klaviyo).
      const status = asset ? "created" : approvedForSend.includes(item.id) ? "approved" : "draft";
      return {
        ...item,
        status,
        klaviyoTemplateId: asset?.templateId || null,
        klaviyoListId: asset?.listId || null,
        klaviyoCampaignId: asset?.campaignId || null,
        klaviyoSendJobId: asset?.sendJobId || null,
        klaviyoAudience: asset?.audience || null,
      };
    })
    .filter(Boolean);

  // CA-4: generate LLM copy for a play. On rewrite, the merchant's edited fields
  // are sent as LOCKED context (adopt #1) and the result is applied to Suggested
  // slots only. Fails soft: available:false leaves the static copy untouched.
  const fetchCopyForPlay = React.useCallback(async (play, template, { regenerate = false, steer = null } = {}) => {
    if (!play || !template) return;
    const playId = play.id;
    // Map the merchant's current edits back to copywriter slot names to lock them.
    const edits = draftEditsByPlay[playId] || {};
    const lockedSlots = {};
    if (regenerate) {
      if (edits.subject != null) lockedSlots.subject = edits.subject;
      if (edits.previewText != null) lockedSlots.preview_text = edits.previewText;
      if (edits.bodyH2 != null) lockedSlots.headline = edits.bodyH2;
      if (edits.bodyP1 != null) lockedSlots.body = edits.bodyP1;
      if (edits.bodyP2 != null) lockedSlots.support = edits.bodyP2;
      if (edits.cta != null) lockedSlots.cta = edits.cta;
    }
    setCopyStatusByPlay((prev) => ({ ...prev, [playId]: "loading" }));
    try {
      const res = await api.generateCopy({
        playId, templateId: template.id, regenerate,
        lockedSlots: regenerate ? lockedSlots : null, steer,
      });
      if (res && res.available && res.copy) {
        setAgentCopyByPlay((prev) => ({ ...prev, [playId]: res.copy }));
        setCopyStatusByPlay((prev) => ({ ...prev, [playId]: "ready" }));
      } else {
        // No key / fell back → keep static copy, no message (adopt #9).
        setCopyStatusByPlay((prev) => ({ ...prev, [playId]: "static" }));
      }
    } catch (_) {
      setCopyStatusByPlay((prev) => ({ ...prev, [playId]: "static" }));
    }
  }, [draftEditsByPlay]);

  // Fire once when the merchant enters the Copy step for a play/template with no
  // cached agent copy yet (adopt: fetch-on-enter, once per play/template).
  useEffect(() => {
    if (!reviewPlay || !selectedTemplate) return;
    if (agentCopyByPlay[reviewPlay.id]) return;            // already have copy
    if (copyStatusByPlay[reviewPlay.id] === "loading") return; // in flight
    fetchCopyForPlay(reviewPlay, selectedTemplate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reviewPlay?.id, selectedTemplate?.id]);

  // Counts reflect only approved campaigns: those still needing review sign-off.
  const reviewPendingCount = approvedPlays.filter((play) => !approvedForSend.includes(play.id)).length;
  const sentCampaigns = finalCampaigns.filter((item) => item.klaviyoSendJobId);
  const readyToSendCampaigns = finalCampaigns.filter((item) => (item.status === "approved" || item.status === "created") && !item.klaviyoSendJobId);
  const approvedCount = readyToSendCampaigns.length;

  // C1: unified master-detail item list, keyed off reviewable PLAYS so a play
  // appears the moment it's approved in Briefing. Grouping is driven by the
  // explicit approvedForSend sign-off — NOT by template selection (which
  // auto-happens on view and only means "has a draft").
  const finalCampaignById = new Map(finalCampaigns.map((item) => [item.id, item]));
  const campaignGroupFor = (play) => {
    const campaign = finalCampaignById.get(play.id);
    if (campaign && campaign.klaviyoSendJobId) return "sent";
    if (approvedForSend.includes(play.id)) return "ready";
    return "review";
  };
  const campaignItems = approvedPlays.map((play) => ({
    play,
    campaign: finalCampaignById.get(play.id) || null,
    group: campaignGroupFor(play),
  }));
  const campaignGroups = [
    { key: "review", label: "Needs review", rows: campaignItems.filter((c) => c.group === "review") },
    { key: "ready", label: "Ready to send", rows: campaignItems.filter((c) => c.group === "ready") },
    { key: "sent", label: "Sent", rows: campaignItems.filter((c) => c.group === "sent") },
  ].filter((g) => g.rows.length);
  const selectedCampaign = finalCampaignById.get(reviewPlay?.id) || null;
  const selectedCampaignGroup = reviewPlay ? campaignGroupFor(reviewPlay) : null;
  const productCount = counts.products ?? engineInput?.products?.length ?? "—";
  const customerCount = counts.customers ?? engineInput?.customers?.length ?? "—";
  const orderCount = counts.orders ?? engineInput?.orders?.length ?? "—";
  // Whether this store has any SYNCED DATA — not whether the snapshot request
  // has resolved. /engine/input returns arrays, so an unsynced store yields
  // length 0, not undefined; comparing against the "—" placeholder therefore
  // read as "has data" for every store that had none. That suppressed first-run
  // (which requires !hasStoreSnapshot), so the auto-sync never fired, and it
  // marked the onboarding banner's Shopify step done without ever offering Sync.
  const hasStoreSnapshot = [productCount, customerCount, orderCount]
    .some((value) => typeof value === "number" && value > 0);
  // O3: first-run detection — Shopify connected, no snapshot, and the latest-run
  // check DEFINITIVELY returned no run. Never true while rehydrating, on a fetch
  // error, or once a run exists — so a refresh can't be mistaken for first-run.
  const isFirstRun =
    Boolean(shopDomain) &&
    status.shopify &&
    !hasStoreSnapshot &&
    latestRunChecked &&
    !rehydrating &&
    !latestRunErrored &&
    !latestRunFound &&
    !atulEngineResult;
  const firstRunActive = isFirstRun && ((firstRunStage && firstRunStage !== "done") || Boolean(firstRunError));
  const onboardingReadyToFinish = status.shopify && status.klaviyo;
  const briefingRows = workflowPlays.map((play) => ({ play, lane: classifyPlayLane(play) }));
  const recommendedRows = briefingRows.filter((row) => row.lane === "recommended");
  const experimentRows = briefingRows.filter((row) => row.lane === "experiment");
  const consideredRows = briefingRows.filter((row) => row.lane === "considered");
  const selectableRows = [...recommendedRows, ...experimentRows, ...consideredRows];
  const selectedBriefingRow = selectableRows.find((row) => row.play.play_id === selectedBriefingPlayId) || selectableRows[0] || null;
  const readyRowsCount = recommendedRows.length + experimentRows.length;
  // O3: sparse-store framing after a first run completes with 0 recs but held plays.
  const showSparseInterstitial =
    isFirstRun &&
    firstRunStage === "done" &&
    !sparseInterstitialDismissed &&
    recommendedRows.length === 0 &&
    experimentRows.length === 0 &&
    consideredRows.length > 0;
  const stateOfStore = atulEngineResult?.presentedRun?.state_of_store || null;
  const stateOfStoreObservations = atulEngineResult?.presentedRun?.state_of_store_observations || null;
  const briefingRun = atulEngineResult?.presentedRun || null;
  const briefingHead = briefingHeadline({
    decision: briefingRun?.decision,
    readyCount: readyRowsCount,
    heldCount: consideredRows.length,
    hasRun: Boolean(briefingRun) || workflowPlays.length > 0,
  });
  const heldTruncatedCount = briefingRun?.considered_truncated_count || 0;
  const heldEmptyText = heldLaneEmptyText({ heldCount: consideredRows.length, truncatedCount: heldTruncatedCount });
  const watchingSignals = briefingRun?.watching || [];
  const runDataQualityFlags = briefingRun?.data_quality_flags || [];
  const briefingStatus = dataStatusItems({
    connected: Boolean(status.shopify),
    syncStatus,
    analysedAt: briefingRun?.generated_at,
  });

  useEffect(() => {
    checkConnections();
    preloadStoreSnapshot();
    loadBrandContext();
    loadBrandEmailTemplate();
    loadSenderIdentity();
    loadLatestRun();
  }, []);

  // D6b: fetch weekly series once for sparklines. On failure, tiles render
  // without sparklines — no error surfaced.
  useEffect(() => {
    if (!api.shopDomain) return;
    let alive = true;
    api.getStatsSeries(12)
      .then((res) => { if (alive) setStatsSeries(res.weeks || []); })
      .catch(() => { if (alive) setStatsSeries(null); });
    return () => { alive = false; };
  }, []);

  // Clear any pending toast timer on unmount.
  useEffect(() => () => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
  }, []);

  // P-D3: tab identity — "BeaconAI — {store}", fallback "BeaconAI".
  useEffect(() => {
    document.title = shopDomain ? `BeaconAI — ${shopDomain}` : "BeaconAI";
  }, [shopDomain]);

  // Keep the selected campaign valid against the APPROVED set (the campaigns view).
  useEffect(() => {
    if (reviewPlayId && !approvedPlays.some((play) => play.id === reviewPlayId)) {
      setReviewPlayId("");
      return;
    }
    if (!reviewPlayId && approvedPlays[0]) {
      setReviewPlayId(approvedPlays[0].id);
    }
  }, [reviewPlayId, approvedPlays]);

  useEffect(() => {
    if (!selectableRows.length) return;
    const stillPresent = selectableRows.some((row) => row.play.play_id === selectedBriefingPlayId);
    if (!stillPresent) setSelectedBriefingPlayId(selectableRows[0].play.play_id);
  }, [selectableRows, selectedBriefingPlayId]);

  // Load measured results when the Results page is opened. The server
  // recomputes anything stale on read, so this is also what refreshes the
  // numbers as windows mature.
  //
  // A failed refresh keeps the last loaded results on screen with a persistent
  // banner — clearing them would turn "couldn't refresh" into "no results".
  useEffect(() => {
    if (activePage !== "results" || !shopDomain) return;
    let cancelled = false;
    setResultsLoading(true);
    setResultsError("");
    api.getResults(resultsLimit)
      .then((data) => { if (!cancelled) setResultsData(data); })
      .catch((err) => { if (!cancelled) setResultsError(err.message || "Request failed."); })
      .finally(() => { if (!cancelled) setResultsLoading(false); });
    return () => { cancelled = true; };
  }, [activePage, shopDomain, resultsLimit, resultsReload]);

  // Keep the open result in the URL, so a refresh reopens it.
  useEffect(() => {
    const url = new URL(window.location.href);
    if (activePage === "results" && openResultId) url.searchParams.set("campaign", String(openResultId));
    else url.searchParams.delete("campaign");
    window.history.replaceState({}, "", url.toString());
  }, [activePage, openResultId]);

  // Rehydrate pipeline state from the database once the run is known.
  //
  // This used to read a localStorage blob keyed on the run id, which meant every
  // new engine run discarded every approval, copy edit and send state — and none
  // of it existed outside the one browser that made it. Campaign rows outlive the
  // run, so the same work is here on any device.
  useEffect(() => {
    if (!shopDomain || !currentRunId || pipelineHydratedRef.current) return;
    pipelineHydratedRef.current = true;

    let cancelled = false;
    (async () => {
      try {
        // EVERY campaign, across every run — not just the current one. Scoping
        // this to currentRunId meant a campaign from a previous run existed in
        // the database but had no way into the merchant's workflow: the moment a
        // new engine run landed, last month's drafts and sends vanished from the
        // UI. The rows always survived; the route to them did not.
        const { campaigns = [] } = await api.listCampaigns();
        if (cancelled) return;

        // The current slate's campaigns drive the workspace, which is keyed by
        // play. Everything older is listed separately rather than merged in:
        // two runs can carry the same play_id, and collapsing them by play would
        // silently show one campaign's state on another's row.
        const thisRun = campaigns.filter((c) => c.runId === currentRunId);
        const earlier = campaigns.filter((c) => c.runId !== currentRunId && c.status !== "dismissed");
        setHistoricalCampaigns(earlier);

        // `dismissed` is a play the merchant pulled back out. The row stays (it
        // records that they considered it) but it is not in the pipeline.
        const live = thisRun.filter((c) => c.status !== "dismissed");

        setCampaignIdByPlay(Object.fromEntries(thisRun.map((c) => [c.playId, c.id])));
        setRevisionByPlay(Object.fromEntries(thisRun.map((c) => [c.playId, c.revision])));
        setRunIdByPlay(Object.fromEntries(thisRun.map((c) => [c.playId, c.runId])));
        // The stored rows, which carry the frozen handoff snapshot. The
        // workspace's own campaign objects are built from today's slate and
        // have no record of what was actually sent.
        setCampaignRowByPlay(Object.fromEntries(thisRun.map((c) => [c.playId, c])));
        setDestinationByPlay(Object.fromEntries(
          thisRun.filter((c) => c.destinationUrl).map((c) => [c.playId, c.destinationUrl])
        ));
        for (const c of thisRun) {
          latestRevision.current[c.playId] = c.revision;
          savedSignatureRef.current[c.playId] = campaignSignature({
            edits: c.draftEdits, destinationUrl: c.destinationUrl,
          });
          saveStatusRef.current[c.playId] = "saved";
        }
        setRestoredApprovedPlayIds(live.map((c) => c.playId));
        setApprovedForSend(live.filter((c) => c.status === "approved" || c.status === "sent").map((c) => c.playId));
        setAuthorizedPackageIds(live.filter((c) => c.klaviyoCampaignId).map((c) => c.playId));

        const templates = {};
        const edits = {};
        const agentCopy = {};
        for (const c of live) {
          if (c.templateId) templates[c.playId] = c.templateId;
          if (c.draftEdits) edits[c.playId] = c.draftEdits;
          if (c.copy?.copy) agentCopy[c.playId] = c.copy.copy;
        }
        setSelectedTemplateByPlay(templates);
        setDraftEditsByPlay(edits);
        setAgentCopyByPlay(agentCopy);
      } catch (_) {
        // A hydration failure must not block the briefing; the merchant can
        // re-approve, and the next mutation re-establishes the row.
      }
    })();

    return () => { cancelled = true; };
  }, [shopDomain, currentRunId]);

  // O4: once workflow plays are loaded, rebuild campaign packages for restored approved ids.
  useEffect(() => {
    if (!restoredApprovedPlayIds.length || !workflowPlays.length) return;
    setCampaignPackages((prev) => {
      const existing = new Set(prev.map((item) => item.id));
      const additions = restoredApprovedPlayIds
        .filter((id) => !existing.has(id))
        .map((id) => workflowPlays.find((play) => (play.play_id || play.id) === id))
        .filter(Boolean)
        .map((play) => ({
          id: play.play_id || play.id,
          playTitle: play.play_name || play.play_id,
          status: "building",
          customers: play.audience_size || 0,
          segment: play.audience_archetype || "—",
          subject: "Placeholder subject from engine play",
          previewText: "Waiting for real engine copy.",
          bodyH2: play.play_name || play.play_id,
          bodyP1: play.mechanism,
          bodyP2: "Replace this package with Atul engine output when available.",
          cta: "Review package",
          sendTime: "Manual review",
          suppression: STANDARD_SUPPRESSIONS_NOTE,
        }));
      if (!additions.length) return prev;
      return [...prev, ...additions];
    });
    setRestoredApprovedPlayIds([]);
  }, [restoredApprovedPlayIds, workflowPlays]);

  // Write one play's campaign state through to the database. Upsert rather than
  // patch-by-id: the row may not exist yet (first greenlight), and the endpoint
  // is idempotent on (shop, run, play). Returns the row so the caller can learn
  // its id for later patches.
  const latestRevision = useRef({});
  // Saves already sent to the server. The debounce timer map only knows about
  // edits still WAITING; once a save fires it leaves that map, so a flush that
  // consulted only the timers would report "nothing pending" while a write was
  // still in flight.
  const inFlightSaves = useRef({});
  // The LAST SETTLED outcome per draft, and the signature of what was actually
  // persisted. Both are refs: a handoff handler closes over state from the
  // render that created it, which by definition predates the save it needs to
  // judge. A failure stays here until a later save succeeds — that is what stops
  // a settled failure from looking like "nothing pending".
  const saveStatusRef = useRef({});
  const savedSignatureRef = useRef({});
  const saveCampaignState = useCallback(async (playId, fields) => {
    // A campaign belongs to the run it was created in. Writing it against
    // whatever run is current would open a second campaign for the same play the
    // moment a new engine run lands, orphaning the one the merchant was editing.
    const runId = runIdByPlay[playId] || currentRunId;
    if (!runId || !playId) return null;
    setSaveStateByPlay((prev) => ({ ...prev, [playId]: "saving" }));
    const tracked = (async () => {
    try {
      const { campaign } = await api.saveCampaign({
        runId, playId,
        // Optimistic check: the server refuses the write if the row moved on
        // since we last read it, rather than overwriting someone else's edit.
        expectedRevision: revisionByPlay[playId],
        ...fields,
      });
      setCampaignIdByPlay((prev) => (prev[playId] === campaign.id ? prev : { ...prev, [playId]: campaign.id }));

      setRevisionByPlay((prev) => ({ ...prev, [playId]: campaign.revision }));
      setRunIdByPlay((prev) => (prev[playId] === campaign.runId ? prev : { ...prev, [playId]: campaign.runId }));
      setSaveStateByPlay((prev) => ({ ...prev, [playId]: "saved" }));
      saveStatusRef.current[playId] = "saved";
      // Record WHAT was persisted, not merely that something was. The handoff
      // compares the draft on screen against this.
      // Recorded from the row the server returned, so it reflects what was
      // actually persisted rather than what was sent.
      savedSignatureRef.current[playId] = campaignSignature({
        edits: campaign.draftEdits, destinationUrl: campaign.destinationUrl,
      });
      // Kept in a ref as well as state: a handoff started in the same tick as a
      // save needs the revision the server just returned, and setState has not
      // landed yet.
      latestRevision.current[playId] = campaign.revision;
      return { ok: true, campaign, revision: campaign.revision, playId };
    } catch (error) {
      // A conflict is not a failure to save — it is a save that would have
      // destroyed a newer edit. Take the server's version as the new baseline so
      // a retry is against reality, and tell the merchant rather than silently
      // dropping either copy.
      if (error.conflict && error.campaign) {
        // The server's revision is recorded for display, but NOT adopted as the
        // reviewed revision: the merchant's copy has not been resolved against
        // it, so handing off would freeze one of the two arbitrarily.
        setRevisionByPlay((prev) => ({ ...prev, [playId]: error.campaign.revision }));
        saveStatusRef.current[playId] = "conflict";
        setSaveStateByPlay((prev) => ({ ...prev, [playId]: "conflict" }));
        showToast({
          message: error.conflict === "frozen"
            ? "This campaign has already been sent, so its content can't be changed."
            : "This campaign changed elsewhere. Reload before editing further.",
          error: true,
        });
        return { ok: false, reason: error.conflict, campaign: error.campaign, playId };
      }
      // Anything else is a real write failure. Surfaced, not swallowed: the
      // merchant is otherwise editing a draft that is no longer being stored.
      setSaveStateByPlay((prev) => ({ ...prev, [playId]: "failed" }));
      saveStatusRef.current[playId] = "failed";
      return { ok: false, reason: "failed", playId };
    }
    })();

    inFlightSaves.current[playId] = tracked;
    try {
      return await tracked;
    } finally {
      if (inFlightSaves.current[playId] === tracked) delete inFlightSaves.current[playId];
    }
  }, [currentRunId, revisionByPlay, runIdByPlay]);

  // Copy edits fire on every keystroke, so they are debounced per play — one
  // request per pause, not per character. The whole edit object is sent rather
  // than a delta: "Restore suggested" works by DELETING a key, and a delta could
  // not express that.
  const editSaveTimers = useRef({});
  const pendingEdits = useRef({});
  // Every debounced field for a campaign goes through here, merged into ONE
  // pending payload. A second timer elsewhere would be invisible to the flush,
  // which is exactly how the destination could still be in flight when a handoff
  // decided nothing was pending.
  const scheduleCampaignSave = useCallback((playId, fields) => {
    clearTimeout(editSaveTimers.current[playId]);
    pendingEdits.current[playId] = { ...(pendingEdits.current[playId] || {}), ...fields };
    editSaveTimers.current[playId] = setTimeout(() => {
      delete editSaveTimers.current[playId];
      const payload = pendingEdits.current[playId];
      delete pendingEdits.current[playId];
      saveCampaignState(playId, payload);
    }, 600);
  }, [saveCampaignState]);

  const scheduleDraftEditsSave = useCallback(
    (playId, edits) => scheduleCampaignSave(playId, { draftEdits: edits }),
    [scheduleCampaignSave]
  );

  // Flush any pending edit when the workspace closes or the page unloads, so the
  // last few characters before navigating away are not lost.
  //
  // This used to only clearTimeout the pending saves, which did the opposite of
  // what the comment claimed: every debounced edit still in flight at unmount
  // was discarded rather than written. The pending edits are kept in a ref so
  // the flush can read them without re-running this effect on every keystroke.
  // Returns a promise that settles when every flushed save has actually
  // finished. Firing them and returning immediately meant a handoff could start
  // while the last edit was still in flight — and the record is frozen straight
  // afterwards, so the edit would be missing from the thing it can no longer be
  // added to.
  const flushPendingEdits = useCallback(async (playId = null) => {
    const timers = editSaveTimers.current;
    const ids = playId
      ? [playId]
      : Array.from(new Set([...Object.keys(timers), ...Object.keys(inFlightSaves.current)]));
    const saves = [];
    for (const id of ids) {
      if (timers[id]) {
        clearTimeout(timers[id]);
        delete timers[id];
      }
      const payload = pendingEdits.current[id];
      if (payload !== undefined) {
        delete pendingEdits.current[id];
        saves.push(saveCampaignState(id, payload));
      } else if (inFlightSaves.current[id]) {
        // Nothing queued, but a save is already on the wire. Waiting for it is
        // the whole point: it may still fail or conflict.
        saves.push(inFlightSaves.current[id]);
      }
    }
    const results = await Promise.all(saves);
    return {
      results,
      ok: results.every((r) => r?.ok !== false),
      failed: results.filter((r) => r?.ok === false),
    };
  }, [saveCampaignState]);

  useEffect(() => {
    const onHide = () => { flushPendingEdits(); };
    window.addEventListener("pagehide", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      flushPendingEdits();
    };
  }, [flushPendingEdits]);

  // O3: auto-start the first-run pipeline once per shop. The localStorage guard
  // prevents a page refresh from re-running a full sync — without it, every
  // refresh re-entered first-run and any hiccup showed "sync hit a problem".
  useEffect(() => {
    if (!isFirstRun || firstRunStartedRef.current) return;
    let alreadyDone = false;
    try {
      alreadyDone = firstRunDoneKey && localStorage.getItem(firstRunDoneKey) === "true";
    } catch (_) {
      // Storage unavailable (private mode) — fall through and let the run proceed.
    }
    if (alreadyDone) return;
    firstRunStartedRef.current = true;
    runFirstRunPipeline("sync");
  }, [isFirstRun, firstRunDoneKey]);

  useEffect(() => {
    if (onboardingReadyToFinish && !onboardingHidden) {
      localStorage.setItem("beaconai:onboarding-complete", "true");
      setOnboardingHidden(true);
    }
  }, [onboardingHidden, onboardingReadyToFinish]);

  // C1 fix: auto-load starting-copy templates once reviewable plays exist. The
  // template endpoint returns BeaconAI templates even without Klaviyo, so this
  // unblocks the whole campaigns workspace (auto-select → draft → preview)
  // instead of requiring a manual Refresh the empty page never surfaced.
  const templatesRequestedRef = useRef(false);
  useEffect(() => {
    if (!approvedPlays.length || klaviyoTemplates.length || templatesRequestedRef.current) return;
    templatesRequestedRef.current = true;
    loadKlaviyoTemplates().catch(() => {
      // Allow a later retry (e.g. after connecting Klaviyo) if this load failed.
      templatesRequestedRef.current = false;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [approvedPlays.length, klaviyoTemplates.length]);

  // C3: auto-apply the mapped starting template when a reviewable play has none.
  // Only fires once BeaconAI templates have loaded and the play is untouched.
  useEffect(() => {
    if (!reviewPlay || selectedTemplateByPlay[reviewPlay.id]) return;
    const wantedId = templateForPlay(reviewPlay);
    const match = beaconTemplates.find((item) => item.id === wantedId) || beaconTemplates[0];
    if (match) chooseTemplate(reviewPlay.id, match.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reviewPlay?.id, beaconTemplates.length, selectedTemplateByPlay]);

  // C1: reset the right pane to the top whenever the selected item changes, so
  // switching items never leaves the merchant scrolled past their own work.
  // C2: default the stepper — approved campaigns open on Send, others on Copy.
  useEffect(() => {
    if (rightPaneRef.current) rightPaneRef.current.scrollTop = 0;
    setWorkspaceStep(reviewPlayId && approvedForSend.includes(reviewPlayId) ? "send" : "copy");
    // The campaign id often arrives AFTER the play is selected — the row is
    // created by the first save. Watching only the play meant no delivery
    // request ran, and the loading guard then blocked creation until the
    // merchant switched campaigns and back.
    if (reviewPlayId && campaignIdByPlay[reviewPlayId]) loadDelivery(campaignIdByPlay[reviewPlayId]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reviewPlayId, campaignIdByPlay[reviewPlayId]]);

  // Auto-load the recipient preview when the merchant lands on the Audience step,
  // so the list isn't blank until they hunt for a "Show emails" button.
  const audienceRequestedRef = useRef("");
  useEffect(() => {
    if (workspaceStep !== "audience" || !reviewPlayId) return;
    const draft = finalCampaignById.get(reviewPlayId);
    if (!draft) return;
    if (audiencePreviewsByCampaign[reviewPlayId]) return; // already loaded
    if (audienceRequestedRef.current === reviewPlayId) return; // in-flight/attempted
    audienceRequestedRef.current = reviewPlayId;
    previewCampaignAudience(draft).catch(() => {
      audienceRequestedRef.current = ""; // allow retry via the button
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceStep, reviewPlayId]);

  async function runStep(label, fn) {
    setLoading(true);
    setError("");
    try {
      return await fn();
    } catch (err) {
      setError(`${label} failed: ${err.message}`);
      throw err;
    } finally {
      setLoading(false);
    }
  }

  async function loadSyncStatus() {
    if (!api.shopDomain) return null;
    try {
      const result = await api.syncStatus();
      setSyncStatus(result);
      return result;
    } catch (_) {
      // Provenance is additive to the page; never block a render on it.
      return null;
    }
  }

  async function checkConnections() {
    setLoading(true);
    setError("");
    const next = { api: false, shopify: false, klaviyo: false, shopifySource: "none", klaviyoSource: "none" };
    try {
      await api.health();
      next.api = true;

      // Signed in is a DIFFERENT question from connected, and conflating them
      // was the trap: a store stays connected while a session expires, so the
      // page said "Connected", hid the Shopify action, and every protected
      // request failed with no way back in.
      let session = null;
      try { session = await api.session(); } catch (_) {}
      const signIn = signInState({ session, viewingShop: api.shopDomain, checked: true });
      setSignInView(signIn);
      setSignedInShop(signIn.state === "signed_in" ? session.shopDomain : null);
      setSignedInChecked(true);
      next.signedIn = !signIn.needsSignIn;
      const authenticated = !signIn.needsSignIn;

      try {
        const connection = await api.connectionStatus();
        next.shopify = Boolean(connection.status?.shopify?.connected);
        next.klaviyo = Boolean(connection.status?.klaviyo?.connected);
        next.shopifySource = connection.status?.shopify?.source || "none";
        next.klaviyoSource = connection.status?.klaviyo?.source || "none";
      } catch (_) {}
      // These now require a session; skip them when there is none rather than
      // letting two guaranteed failures look like a broken integration.
      if (authenticated) {
        try { await api.testShopify(); next.shopify = true; } catch (_) {}
        try { await api.testKlaviyo(); next.klaviyo = true; } catch (_) {}
      }
      setStatus(next);
    } catch (err) {
      setError(`API health failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function preloadStoreSnapshot() {
    try {
      const result = await api.getEngineInput();
      setEngineInput(result.input);
    } catch (_) {
      // Home can still render connection and workflow state before data is synced.
    }
  }

  async function loadSenderIdentity() {
    try {
      const result = await api.klaviyoSender();
      setSenderIdentity(result.sender || null);
    } catch (_) {
      // Unreachable is not the same as absent, but both render as
      // "Check in Klaviyo" — the merchant's action is identical.
      setSenderIdentity(null);
    }
  }

  async function loadBrandEmailTemplate() {
    try {
      const result = await api.brandEmailTemplate();
      setBrandTemplateVersion(result.active?.version ?? null);
      setBrandDesign(result);
    } catch (_) {
      // Additive: the preview's own response still reports brand_setup_required.
    }
  }

  async function loadBrandContext() {
    try {
      const result = await api.brandContext();
      setBrandContext(result.brandContext || null);
    } catch (_) {
      // Brand context is additive; campaign review still works without it.
    }
  }

  async function syncShopify() {
    try {
      const result = await runStep("Shopify sync", () => api.syncShopify());
      setSync(result);

      // A sync that came back partial is NOT a synced store. It publishes
      // nothing, so the previous good data is still what is on screen — say
      // which, rather than showing a success toast over unchanged numbers.
      if (result?.published === false) {
        await loadSyncStatus();
        const reason = result.validationFailures?.[0]?.message
          || "Shopify returned an incomplete copy of the store.";
        showToast({
          message: `Store not updated: ${reason}`,
          error: true,
          actionLabel: "Retry",
          onAction: () => { setToast(null); syncShopify(); },
        });
        return result;
      }

      await preloadStoreSnapshot();
      await loadSyncStatus();
      const days = result?.coverage?.daysCovered;
      showToast({ message: days ? `Store synced · ${days} days of history` : "Store synced" });
      return result;
    } catch (err) {
      setError(""); // P-C1: surface this via toast, not the page-level error-box.
      showToast({
        message: "Store sync hit a problem.",
        error: true,
        actionLabel: "Retry",
        onAction: () => { setToast(null); syncShopify(); },
      });
      return null;
    }
  }

  // Shared result-handling path for both a fresh engine run and O1 rehydration.
  function applyEngineResult(result) {
    setAtulEngineResult(result);
    if (!initialCampaignParam.current) setActivePage("briefing");
    // Cache the presented run (incl. embedded narration) so a BROWSER refresh
    // repaints the briefing instantly from localStorage — independent of the
    // server /latest round-trip (which can miss on store_id mismatch or an
    // ephemeral-filesystem wipe). Keyed by shop so mount can read it without a
    // run_id. Only cache a real presented run, never an empty rehydrate.
    if (result?.presentedRun?.recommendations?.length && briefingCacheKey) {
      try {
        localStorage.setItem(briefingCacheKey, JSON.stringify({ presentedRun: result.presentedRun }));
      } catch (_) {
        // best-effort (storage may be unavailable in private mode)
      }
    }
  }

  async function runAtulEngine(useFixture = false) {
    setRefreshingBriefing(true);
    try {
      const result = await runStep(useFixture ? "Sample briefing refresh" : "Briefing refresh", () => api.runAtulEngine(useFixture));
      applyEngineResult(result);
      await loadSyncStatus();
      return result;
    } finally {
      setRefreshingBriefing(false);
    }
  }

  // O1: read-only rehydration of the latest run on mount. Never triggers an engine run.
  // Stale-while-revalidate: paint the cached briefing immediately (survives refresh
  // even when the server can't find the run), then reconcile with /latest.
  async function loadLatestRun() {
    if (!api.shopDomain) {
      setLatestRunChecked(true);
      setRehydrating(false);
      return;
    }

    // 1) Instant paint from the localStorage briefing cache, if present.
    let hadCache = false;
    try {
      const cachedRaw = briefingCacheKey && localStorage.getItem(briefingCacheKey);
      if (cachedRaw) {
        const cached = JSON.parse(cachedRaw);
        if (cached?.presentedRun?.recommendations?.length) {
          setAtulEngineResult({ presentedRun: cached.presentedRun });
          if (!initialCampaignParam.current) setActivePage("briefing");
          setLatestRunFound(true);
          hadCache = true;
        }
      }
    } catch (_) { /* ignore malformed cache */ }

    setRehydrating(true);
    try {
      const result = await api.getLatestEngineRun();
      loadSyncStatus();
      setLatestRunErrored(false);
      if (result.found) {
        // Server has a (possibly fresher) run — reconcile + refresh the cache.
        applyEngineResult({ presentedRun: result.presentedRun });
        setLatestRunFound(true);
      } else if (!hadCache) {
        // Only fall to "no run" when we ALSO had nothing cached to show.
        setLatestRunFound(false);
      }
    } catch (_) {
      // Fetch failed — NOT "no run yet". Keep any cached briefing on screen.
      setLatestRunErrored(true);
      if (!hadCache) setLatestRunFound(false);
    } finally {
      setLatestRunChecked(true);
      setRehydrating(false);
    }
  }

  async function loadKlaviyoTemplates() {
    const result = await runStep("Klaviyo templates load", () => api.getKlaviyoTemplates());
    setKlaviyoTemplates(result.templates || []);
    // Only flag a failure when connected to Klaviyo but its own templates didn't load.
    const hasKlaviyoTemplates = (result.templates || []).some((item) => item.source === "klaviyo");
    setKlaviyoTemplatesFailed(Boolean(status.klaviyo) && result.source !== "klaviyo" && !hasKlaviyoTemplates);
    if (result.brandContext) setBrandContext(result.brandContext);
    return result;
  }

  async function saveShopDomain(event) {
    event?.preventDefault();
    const next = api.setShopDomain(shopDomainDraft);
    setShopDomain(next);
    setShopDomainDraft(next);
    setSync(null);
    setEngineInput(null);
    setAtulEngineResult(null);
    setCampaignPackages([]);
    setSelectedTemplateByPlay({});
    if (!next) {
      setError("Enter a Shopify store domain before connecting.");
      return;
    }
    setError("");
    await checkConnections();
  }

  // O3: staged first-run pipeline — sync → auto engine run → first briefing.
  async function runFirstRunPipeline(fromStage = "sync") {
    setFirstRunError(null);

    let syncCounts = counts;
    if (fromStage === "sync") {
      setFirstRunStage("syncing");
      try {
        const result = await api.syncShopify();
        setSync(result);
        // Partial data must not flow into a first briefing — that briefing is
        // the merchant's first impression of whether this product can be
        // trusted with their store.
        if (result?.published === false) {
          setFirstRunError({
            phase: "sync",
            message: result.validationFailures?.[0]?.message
              || "Shopify returned an incomplete copy of the store. Retry the sync.",
          });
          return;
        }
        syncCounts = result.synced || {};
        await preloadStoreSnapshot();
      } catch (err) {
        setFirstRunError({ phase: "sync", message: "Shopify sync hit a problem. Retry, or check Settings → connections." });
        return;
      }
      setFirstRunStage("synced");
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }

    setFirstRunStage("analyzing");
    try {
      await runAtulEngine(false);
    } catch (err) {
      setFirstRunError({ phase: "engine", message: "Analysis hit a problem. Your store data is synced — retry the analysis." });
      return;
    }
    setFirstRunStage("done");
    // Persist completion so a refresh reads the snapshot instead of re-syncing.
    try {
      if (firstRunDoneKey) localStorage.setItem(firstRunDoneKey, "true");
    } catch (_) {
      // Best-effort; if storage is unavailable the derived isFirstRun guard
      // (snapshot present) still prevents a re-run in the common case.
    }
  }

  function retryFirstRun() {
    if (firstRunError?.phase === "engine") {
      runFirstRunPipeline("engine");
    } else {
      runFirstRunPipeline("sync");
    }
  }

  // O2: first-time store gate submit. Validate, save domain, then start OAuth.
  async function submitStoreGate(event) {
    event?.preventDefault();
    const raw = String(shopDomainDraft || "").trim().toLowerCase();
    const bare = raw.replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    const valid = bare.length > 0 && (bare.includes(".myshopify.com") || !bare.includes("."));
    if (!valid) {
      setShopDomainError("Enter your Shopify store address, like acme.myshopify.com.");
      return;
    }
    setShopDomainError("");
    const next = api.setShopDomain(bare);
    setShopDomain(next);
    setShopDomainDraft(next);
    if (!next) {
      setShopDomainError("Enter your Shopify store address, like acme.myshopify.com.");
      return;
    }
    startOAuth("shopify");
  }

  function showToast(next) {
    setToast(next);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(null), 5000);
  }

  // Approve toggles a play into (or out of) Campaigns. Stays on the briefing —
  // the merchant can approve several, then review copy in Campaigns via the toast link.
  function greenlightEnginePlay(play) {
    const playId = play.play_id || play.id;
    const alreadyApproved = campaignPackages.some((item) => item.id === playId);

    if (alreadyApproved) {
      setCampaignPackages((prev) => prev.filter((item) => item.id !== playId));
      // Dismissed, not deleted — the row records that the merchant considered
      // this play and pulled it back out.
      saveCampaignState(playId, { status: "dismissed" });
      showToast({ message: "Removed from Campaigns." });
      return;
    }

    setCampaignPackages((prev) => [
      ...prev,
      {
        id: playId,
        playTitle: play.play_name || playId,
        status: "building",
        builtAt: new Date().toLocaleDateString("en-US", { month: "short", day: "numeric" }),
        customers: play.audience_size || 0,
        segment: play.audience_archetype || "—",
        subject: "Placeholder subject from engine play",
        previewText: "Waiting for real engine copy.",
        bodyH2: play.play_name || play.play_id,
        bodyP1: play.mechanism,
        bodyP2: "Replace this package with Atul engine output when available.",
        cta: "Review package",
        sendTime: "Manual review",
        suppression: STANDARD_SUPPRESSIONS_NOTE,
      },
    ]);
    saveCampaignState(playId, { status: "draft", displayName: play.play_name || playId });
    showToast({
      message: "Added to Campaigns",
      actionLabel: "Review →",
      onAction: () => { setReviewPlayId(playId); setActivePage("campaigns"); setToast(null); },
    });
  }

  function authorizeCampaignPackage(campaignId) {
    setCampaignPackages((prev) => prev.map((item) => item.id === campaignId ? { ...item, status: "authorized" } : item));
    setAuthorizedPackageIds((prev) => prev.includes(campaignId) ? prev : [...prev, campaignId]);
  }

  async function createCampaignTemplateInKlaviyo(campaignDraft) {
    // A handoff has to carry a SAVED revision, and the save has to have
    // FINISHED. Anything still in the debounce would otherwise be in the email
    // the merchant is looking at but not in the record of what was approved —
    // and that record is frozen immediately afterwards, so it could never be
    // corrected. Awaited, not fired and forgotten.
    // Flush first so anything queued or in flight is settled, then ask the gate.
    // The gate is what actually decides, because a flush can legitimately report
    // "nothing pending" while the last save FAILED — the settled request has
    // already left every pending map by then.
    await flushPendingEdits(campaignDraft.id);

    const playId = campaignDraft.id;
    const currentSignature = campaignSignature({
      edits: draftEditsByPlay[playId], destinationUrl: destinationByPlay[playId],
    });
    // Focus the field that is actually blocking, so a keyboard user is not left
    // hunting for it after a refused action.
    const verdict = canHandoff({
      status: saveStatusRef.current[playId],
      currentSignature,
      savedSignature: savedSignatureRef.current[playId],
      savedRevision: latestRevision.current[playId],
      hasCampaignRow: Boolean(campaignIdByPlay[playId]),
      // The rendering the merchant actually looked at. The server refuses a
      // handoff without it, and it should never be attempted without one.
      approvedRenderSignature: approvedRender.current[playId]?.campaignSignature ?? null,
    });
    if (!verdict.ok) {
      showToast({ message: verdict.message, error: true });
      return;
    }
    const expectedRevision = verdict.revision;

    setPublishingCampaignId(campaignDraft.id);
    try {
      const result = await api.createSendPackage({
        ...campaignDraft,
        // Identify the campaign so the server resolves the audience from its
        // ORIGIN run rather than whatever the latest run happens to be.
        campaignId: campaignIdByPlay[campaignDraft.id],
        // Bind the send to the email that was actually reviewed. If the shell
        // was re-approved or the copy moved since, the server refuses rather
        // than sending something nobody looked at.
        expectedTemplateVersion: approvedRender.current[campaignDraft.id]?.templateVersion ?? null,
        expectedRenderFingerprint: approvedRender.current[campaignDraft.id]?.fingerprint ?? null,
        // The revision the merchant actually reviewed. The server reserves the
        // campaign against it before touching Klaviyo, so a campaign edited
        // since approval cannot be handed off as though it had been signed off.
        expectedRevision,
      });
      const templateId = result.template?.data?.id;
      const listId = result.list?.data?.id;
      const campaignId = result.klaviyoCampaign?.data?.id;
      setKlaviyoAssetsByCampaign((prev) => ({
        ...prev,
        [campaignDraft.id]: {
          templateId,
          listId,
          campaignId,
          template: result.template,
          list: result.list,
          klaviyoCampaign: result.klaviyoCampaign,
          importJob: result.importJob,
          assignment: result.assignment,
          audience: result.audience,
          createdAt: new Date().toISOString(),
        },
      }));
      setAuthorizedPackageIds((prev) => prev.includes(campaignDraft.id) ? prev : [...prev, campaignDraft.id]);
      if (campaignId) saveCampaignState(campaignDraft.id, { klaviyoCampaignId: campaignId });
      // Re-read the DURABLE state. Without this the screen kept showing "Create
      // draft" after a successful creation, and the next click made a second one.
      await loadDelivery(campaignIdByPlay[campaignDraft.id]);
      showToast({ message: "Draft created in Klaviyo" });
      return result;
    } catch (err) {
      // The server has already recorded whether this failed safely or ended
      // uncertain. Read that, and let the panel say what may be done next.
      await loadDelivery(campaignIdByPlay[campaignDraft.id]);
      // NO blind retry. The old toast offered one unconditionally, including
      // after an outcome we could not confirm — where a retry can create a
      // second campaign that cannot be taken back.
      showToast({
        message: err.reconciliationRequired
          ? "We couldn't confirm whether Klaviyo created the draft. Check Klaviyo before trying again."
          : "The draft wasn't created. Your saved email is unchanged.",
        error: true,
      });
      return null;
    } finally {
      setPublishingCampaignId("");
    }
  }

  async function sendKlaviyoCampaign(campaignDraft) {
    const campaignId = campaignDraft.klaviyoCampaignId;
    if (!campaignId) {
      setError("Create the Klaviyo send package before sending.");
      return null;
    }
    const holdoutPreview = audiencePreviewsByCampaign[campaignDraft.id]?.holdout;
    const heldNote = holdoutPreview?.held
      ? `\n\n${holdoutPreview.held.toLocaleString()} customers are held back and will receive nothing, so Results can measure what this earned.`
      : "";
    const confirmed = window.confirm(
      `Send this campaign now in Klaviyo to ${campaignDraft.klaviyoAudience?.count || "the matched"} recipients?${heldNote}`
    );
    if (!confirmed) return null;

    setSendingCampaignId(campaignDraft.id);
    try {
      const result = await runStep("Klaviyo campaign send", () => api.sendCampaign(campaignId));
      setKlaviyoAssetsByCampaign((prev) => ({
        ...prev,
        [campaignDraft.id]: {
          ...(prev[campaignDraft.id] || {}),
          sendJobId: result.sendJob?.data?.id || campaignId,
          sendJob: result.sendJob,
          sentAt: new Date().toISOString(),
        },
      }));
      // The send is the moment the campaign is deployed; stamp it on the row so
      // Results can report on it later.
      saveCampaignState(campaignDraft.id, { status: "sent" });
      return result;
    } finally {
      setSendingCampaignId("");
    }
  }

  // The merchant's holdout choice. Persisted on the campaign, then the preview
  // is re-run so the counts on screen are the ones the send will actually use.
  async function changeHoldout(playId, pct) {
    await saveCampaignState(playId, { holdoutPct: pct });
    const draft = finalCampaignById.get(playId) || campaignPackages.find((c) => c.id === playId);
    if (draft) await previewCampaignAudience(draft).catch(() => {});
  }

  async function previewCampaignAudience(campaignDraft) {
    setPreviewingCampaignId(campaignDraft.id);
    try {
      const result = await runStep("Campaign audience preview", () => api.previewCampaignAudience(campaignDraft));
      setAudiencePreviewsByCampaign((prev) => ({
        ...prev,
        [campaignDraft.id]: {
          ...result.audience,
          holdout: result.holdout || null,
          breakdown: result.breakdown || null,
          originRunId: result.originRunId || null,
          inputProvenance: result.inputProvenance || null,
        },
      }));
      return result;
    } finally {
      setPreviewingCampaignId("");
    }
  }

  // Reopen a campaign from an earlier run for editing.
  //
  // The workspace is keyed by play, and an old campaign's play is usually absent
  // from the current slate — so the campaign record itself supplies the play.
  // Its saved template, edits and copy are restored, and its ORIGIN run and
  // revision are registered so later saves write back to the same row rather
  // than opening a second campaign for the same play.
  function openHistoricalCampaign(campaign) {
    const playId = campaign.playId;

    // Two runs can carry the same play id. Merging them into the play-keyed maps
    // would show one campaign's state on the other's row, so this stops and says
    // so rather than quietly corrupting the current draft.
    if (campaignIdByPlay[playId] && campaignIdByPlay[playId] !== campaign.id) {
      showToast({
        message: "This play also has a campaign in the current briefing. Finish or dismiss that one first.",
        error: true,
      });
      return;
    }

    setCampaignIdByPlay((prev) => ({ ...prev, [playId]: campaign.id }));
    setRevisionByPlay((prev) => ({ ...prev, [playId]: campaign.revision }));
    setRunIdByPlay((prev) => ({ ...prev, [playId]: campaign.runId }));
    latestRevision.current[playId] = campaign.revision;
    savedSignatureRef.current[playId] = campaignSignature({
      edits: campaign.draftEdits, destinationUrl: campaign.destinationUrl,
    });
    saveStatusRef.current[playId] = "saved";
    if (campaign.templateId) setSelectedTemplateByPlay((prev) => ({ ...prev, [playId]: campaign.templateId }));
    setDraftEditsByPlay((prev) => ({ ...prev, [playId]: campaign.draftEdits || {} }));
    if (campaign.copy?.copy) setAgentCopyByPlay((prev) => ({ ...prev, [playId]: campaign.copy.copy }));

    // Put it in the workspace rail. Built from the campaign row, because the
    // engine play it came from may no longer be in any slate.
    setCampaignPackages((prev) => (
      prev.some((item) => item.id === playId) ? prev : [...prev, {
        id: playId,
        playTitle: campaign.displayName || playId,
        status: campaign.status === "sent" ? "sent" : "building",
        customers: campaign.audienceSize || 0,
        segment: "—",
        subject: campaign.approvedCopy?.subject || "",
        previewText: "",
        bodyH2: campaign.displayName || playId,
        bodyP1: "",
        cta: "Review package",
        sendTime: "Manual review",
        suppression: STANDARD_SUPPRESSIONS_NOTE,
        fromEarlierRun: true,
      }]
    ));
    setReviewPlayId(playId);
    setActivePage("campaigns");
    if (campaign.frozen) {
      showToast({ message: "This campaign was already sent — its content is read-only." });
    }
  }

  // The campaign's own destination. Debounced like copy edits, and persisted:
  // an email whose button goes nowhere is not a campaign, and the value has to
  // survive a refresh like everything else the merchant sets.
  // Retry has to resend EVERYTHING a save persists. Resending only the copy
  // could report "Saved" while a failed destination stayed unpersisted — and the
  // handoff would go on refusing, with the UI insisting the campaign was saved.
  function retrySave(playId) {
    return saveCampaignState(playId, {
      draftEdits: draftEditsByPlay[playId] || {},
      destinationUrl: destinationByPlay[playId] ?? null,
    });
  }

  function changeDestination(playId, value) {
    setDestinationByPlay((prev) => ({ ...prev, [playId]: value }));
    scheduleCampaignSave(playId, { destinationUrl: value });
  }

  function chooseTemplate(playId, templateId) {
    if (selectedTemplateByPlay[playId] === templateId) return;

    // Switching starting copy discards whatever the merchant has typed. Doing
    // that silently is at odds with the whole point of durable drafts, so it is
    // confirmed first — but only when there is actually something to lose.
    const edits = draftEditsByPlay[playId] || {};
    const hasEdits = Object.values(edits).some((value) => value !== undefined && value !== "");
    // The spec's wording, and it is only accurate because the implementation
    // really does preserve both: chooseTemplate touches copy alone.
    if (hasEdits && !window.confirm(
      "Replace your edited copy?\n\n" +
      "Your copy edits will be replaced. Your email design and button destination will stay the same."
    )) return;

    setSelectedTemplateByPlay((prev) => ({ ...prev, [playId]: templateId }));
    setDraftEditsByPlay((prev) => ({ ...prev, [playId]: {} }));
    // Switching template resets the edits, so persist both together.
    saveCampaignState(playId, { templateId, draftEdits: {} });
  }

  // Explicit sign-off: move a reviewed campaign to "Ready to send".
  function approveForSend(playId) {
    setApprovedForSend((prev) => (prev.includes(playId) ? prev : [...prev, playId]));
    saveCampaignState(playId, { status: "approved" });
    setWorkspaceStep("send");
  }

  // Send it back to review (edits or a mistaken approval).
  function unapproveForSend(playId) {
    setApprovedForSend((prev) => prev.filter((id) => id !== playId));
    saveCampaignState(playId, { status: "draft" });
    setWorkspaceStep("copy");
  }

  function updateDraftField(playId, field, value) {
    setDraftEditsByPlay((prev) => {
      const next = { ...prev, [playId]: { ...(prev[playId] || {}), [field]: value } };
      scheduleDraftEditsSave(playId, next[playId]);
      return next;
    });
  }

  // CA-4: "Restore suggested" DROPS the merchant's edit so the field reverts to
  // the base (agent copy, else static). Deleting the edit — rather than writing
  // the suggested value as a new edit — keeps the field in the un-Edited state so
  // its badge clears and a later rewrite can regenerate it (adopt #1/#2).
  function restoreDraftField(playId, play, field) {
    setDraftEditsByPlay((prev) => {
      const current = prev[playId];
      if (!current || !(field in current)) return prev;
      const next = { ...current };
      delete next[field];
      // Whole object, not a delta — a delta cannot express a deleted key.
      scheduleDraftEditsSave(playId, next);
      return { ...prev, [playId]: next };
    });
  }

  function startOAuth(provider) {
    try {
      window.location.href = api.oauthStartUrl(provider);
    } catch (err) {
      setError(err.message);
      setActivePage("setup");
    }
  }

  function finishOnboarding() {
    localStorage.setItem("beaconai:onboarding-complete", "true");
    setOnboardingHidden(true);
    setActivePage("briefing");
  }

  // Campaigns needing merchant action: approved in Briefing but not yet sent
  // (in review + ready to send). Was double-counting reviewPendingCount twice.
  const campaignsBadgeCount = approvedPlays.length - sentCampaigns.length;

  const nav = [
    ["briefing", "Briefing"],
    ["campaigns", "Campaigns"],
    ["results", "Results"],
    ["setup", "Settings"],
  ];

  const titleByPage = {
    briefing: "Briefing",
    campaigns: "Campaigns",
    results: "Results",
    setup: "Settings",
  };

  // No route dead-ends: retired pages fall back to Briefing.
  useEffect(() => {
    const validPages = new Set(["briefing", "campaigns", "results", "setup"]);
    if (!validPages.has(activePage)) {
      setActivePage("briefing");
    }
  }, [activePage]);

  // O2: no store domain → full-page gate, nothing else reachable.
  if (!shopDomain) {
    return (
      <StoreGate
        draft={shopDomainDraft}
        onDraftChange={setShopDomainDraft}
        onSubmit={submitStoreGate}
        error={shopDomainError}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="wordmark" aria-label="beacon">beac<span className="wordmark-dot" />n</div>
        <div className="store-name">{shopDomain || "No store selected"}</div>
        {nav.map(([key, label]) => (
          <button key={key} className={`nav-item ${activePage === key ? "active" : ""}`} onClick={() => { initialCampaignParam.current = null; setActivePage(key); }}>
            {label}
            {key === "campaigns" && campaignsBadgeCount ? <span className="badge">{campaignsBadgeCount}</span> : null}
          </button>
        ))}
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{titleByPage[activePage]}</h1>
            <p>{shopDomain ? `Marketing copilot for ${shopDomain}` : "Your marketing copilot"}</p>
          </div>
          <div className="status-row">
            <StatusChip label="Shopify" ok={status.shopify} onConnect={() => startOAuth("shopify")} />
            <StatusChip label="Klaviyo" ok={status.klaviyo} onConnect={() => startOAuth("klaviyo")} />
          </div>
        </header>

        <section className="page page-rise" key={activePage}>
          {toast ? (
            <div className={`toast ${toast.error ? "error" : ""}`} role="status" aria-live="polite">
              <span className="toast-check" aria-hidden="true"><Icon name={toast.error ? "alert" : "check"} size={13} /></span>
              <span className="toast-message">{toast.message}</span>
              {toast.actionLabel && toast.onAction ? (
                <button type="button" className="toast-action" onClick={toast.onAction}>{toast.actionLabel}</button>
              ) : null}
              <button type="button" className="toast-close" aria-label="Dismiss" onClick={() => setToast(null)}><Icon name="close" size={14} /></button>
            </div>
          ) : null}
          {error ? <div className="error-box">{error}</div> : null}

          {activePage === "briefing" && firstRunActive ? (
            <FirstRunProgress
              stage={firstRunStage}
              counts={counts}
              orders={orderCount}
              error={firstRunError}
              onRetry={retryFirstRun}
            />
          ) : null}

          {activePage === "briefing" && !firstRunActive && rehydrating ? (
            <div className="loading-box">Loading your briefing...</div>
          ) : null}

          {/* The store snapshot + page shape stay visible during a briefing
              refresh (those are stable synced facts). Only the recommendation
              lane below swaps to a skeleton state while the recompute runs — see
              the `refreshingBriefing` gate in briefing-workbench. */}
          {activePage === "briefing" && !firstRunActive && !rehydrating && (
            <>
              {showSparseInterstitial ? (
                <div className="sparse-interstitial">
                  <p>
                    {holdsAreDataVolume(consideredRows.map(({ play }) => play))
                      ? `Your store has ${orderCount} orders. BeaconAI holds recommendations until there's enough history to back them — the plays below unlock as more orders sync.`
                      : "BeaconAI isn't recommending a campaign from this analysis. Each play below says what's holding it back."}
                  </p>
                  <button className="btn small" onClick={() => setSparseInterstitialDismissed(true)}>Dismiss</button>
                </div>
              ) : null}
              {signInView.needsSignIn ? (
                // Shown regardless of connection state. A connected store with
                // an expired session is exactly the case that had no way back:
                // every protected request failed while the page said
                // "Connected" and hid the only action that would fix it.
                <div className="data-state-banner warn" role="status">
                  <div className="data-state-main">
                    <strong>
                      {signInView.state === "wrong_shop"
                        ? "You're signed in to a different store"
                        : "You're signed out of this store"}
                    </strong>
                    <span>{signInView.message}</span>
                  </div>
                  <button className="btn" onClick={() => startOAuth("shopify")}>Sign in with Shopify</button>
                </div>
              ) : null}
              <DataStateBanner
                syncStatus={syncStatus}
                busy={loading}
                onSync={syncShopify}
              />
              {!onboardingHidden ? (
                <OnboardingBanner
                  status={status}
                  hasStoreSnapshot={hasStoreSnapshot}
                  approvedCount={approvedCount}
                  readyToFinish={onboardingReadyToFinish}
                  busy={loading}
                  onConnectShopify={() => startOAuth("shopify")}
                  onSyncShopify={syncShopify}
                  onConnectKlaviyo={() => startOAuth("klaviyo")}
                  onLoadTemplates={loadKlaviyoTemplates}
                  onFinish={finishOnboarding}
                />
              ) : null}
              <BriefingStatStrip
                products={productCount}
                customers={customerCount}
                orders={orderCount}
                reviewPending={reviewPendingCount}
                campaignsPending={readyToSendCampaigns.length}
                ordersSeries={statsSeries ? statsSeries.map((w) => w.orders) : null}
                customersSeries={statsSeries ? statsSeries.map((w) => w.newCustomers) : null}
              />
              {stateOfStoreObservations && stateOfStoreObservations.length ? (
                <div className="delta-row">
                  {stateOfStoreObservations.map((obs, i) => (
                    <span key={i} className={`delta ${obs.direction}`}>
                      <span className="delta-tri" aria-hidden="true">{obs.direction === "down" ? "▼" : obs.direction === "up" ? "▲" : "—"}</span>
                      {obs.label} {obs.pct}%
                    </span>
                  ))}
                </div>
              ) : stateOfStore ? (
                <div className="state-of-store-banner"><Icon name="watch" size={16} /><span>{stateOfStore}</span></div>
              ) : null}
              <div className="briefing-titlebar">
                <div>
                  <h2>{briefingHead.title}</h2>
                  {briefingHead.detail ? <p className="briefing-decision-detail">{briefingHead.detail}</p> : null}
                  <p>
                    <strong>{recommendedRows.length}</strong> recommended now{experimentRows.length ? <> · <strong>{experimentRows.length}</strong> experiments</> : null} · <strong>{consideredRows.length}</strong> not ready yet.
                  </p>
                </div>
                <div className="briefing-refresh">
                  {/* Analysis only. It reads the last synced store data; syncing
                      Shopify is a separate action, and the status line below
                      shows the two times apart. */}
                  <button
                    className="btn"
                    onClick={() => runAtulEngine(false)}
                    disabled={loading}
                    title="Analyses the store data from the last sync. It doesn't pull new data from Shopify."
                  >
                    Re-run analysis
                  </button>
                </div>
              </div>
              {runDataQualityFlags.length ? (
                <ul className="briefing-dq-flags">
                  {runDataQualityFlags.map((flag) => <li key={flag.code}>{flag.label}</li>)}
                </ul>
              ) : null}
              <dl className="briefing-status" aria-label="Store data status">
                {briefingStatus.map((item) => (
                  <div key={item.key} className={`briefing-status-item ${item.tone}`}>
                    <dt>{item.label}</dt>
                    <dd>{item.value}</dd>
                  </div>
                ))}
              </dl>
              <div className="briefing-workbench">
                {refreshingBriefing ? <BriefingWorking /> : (<>
                <div className="recommendation-list">
                  <div className="lane-box">
                    <div className="lane-head">
                      <span>Recommended now</span>
                      <div className="lane-head-actions">
                        <strong>{recommendedRows.length}</strong>
                      </div>
                    </div>
                    <div className="recommendation-row-stack">
                      {recommendedRows.map(({ play }) => (
                        <RecommendationRow
                          key={play.play_id}
                          play={play}
                          selected={selectedBriefingRow?.play.play_id === play.play_id}
                          approved={approvedPlayIdSet.has(play.play_id || play.id)}
                          onSelect={setSelectedBriefingPlayId}
                        />
                      ))}
                      {!selectableRows.length && !briefingRun ? <div className="empty-panel inline">Run the analysis to load recommendations.</div> : null}
                      {(selectableRows.length || briefingRun) && !recommendedRows.length ? <div className="empty-panel inline">Nothing is recommended from this analysis.{consideredRows.length ? " Not ready yet, below, says why each play is held." : ""}</div> : null}
                    </div>
                  </div>

                  {experimentRows.length ? (
                    <div className="lane-box">
                      <div className="lane-head">
                        <span>Recommended experiment</span>
                        <strong>{experimentRows.length}</strong>
                      </div>
                      <div className="recommendation-row-stack">
                        {experimentRows.map(({ play }) => (
                          <RecommendationRow
                            key={play.play_id}
                            play={play}
                            selected={selectedBriefingRow?.play.play_id === play.play_id}
                            approved={approvedPlayIdSet.has(play.play_id || play.id)}
                            onSelect={setSelectedBriefingPlayId}
                          />
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <div className="lane-box compact-lane">
                    <div className="lane-head">
                      <span>Not ready yet</span>
                      <strong>{consideredRows.length}</strong>
                    </div>
                    {consideredRows.length ? (
                      <div className="recommendation-row-stack">
                        {consideredRows.map(({ play }) => (
                          <RecommendationRow
                            key={play.play_id}
                            play={play}
                            selected={selectedBriefingRow?.play.play_id === play.play_id}
                            onSelect={setSelectedBriefingPlayId}
                          />
                        ))}
                      </div>
                    ) : heldEmptyText ? (
                      <div className="empty-panel inline">{heldEmptyText}</div>
                    ) : null}
                    {truncatedNote(heldTruncatedCount) ? <div className="lane-note">{truncatedNote(heldTruncatedCount)}</div> : null}
                  </div>

                  {/* What the engine is keeping an eye on. No measurement claim —
                      only the metric, its direction and what would make it act. */}
                  {watchingSignals.length ? (
                    <div className="lane-box watching-lane">
                      <div className="lane-head">
                        <span>Watching</span>
                        <strong>{watchingSignals.length}</strong>
                      </div>
                      <ul className="watching-list">
                        {watchingSignals.map((signal) => (
                          <li key={signal.metric || signal.metric_label}>
                            <strong>{signal.metric_label}</strong>
                            {signal.trend ? (
                              <span className="watching-trend">
                                {signal.trend === "up" ? "Trending up" : signal.trend === "down" ? "Trending down" : "Flat"}
                              </span>
                            ) : null}
                            {signal.threshold_to_act ? <span className="watching-threshold">{signal.threshold_to_act}</span> : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>

                <RecommendationDetail
                  play={selectedBriefingRow?.play}
                  onSendToReview={greenlightEnginePlay}
                  onViewEvidence={setSelectedEvidence}
                  onOpenInCampaigns={(play) => { setReviewPlayId(play.play_id || play.id); setActivePage("campaigns"); }}
                  approved={selectedBriefingRow ? approvedPlayIdSet.has(selectedBriefingRow.play.play_id || selectedBriefingRow.play.id) : false}
                  showAdvanced={showAdvanced}
                />
                </>)}
              </div>
            </>
          )}

          {activePage === "campaigns" && historicalCampaigns.length ? (
            <details className="earlier-campaigns">
              <summary>Earlier campaigns ({historicalCampaigns.length})</summary>
              {/* Campaigns from previous engine runs. Listed rather than merged
                  into the workspace above: two runs can carry the same play id,
                  so keying them together would show one campaign's state on
                  another's row. Read-only for now — the record, reachable. */}
              <ul className="earlier-campaigns-list">
                {historicalCampaigns.map((c) => (
                  <li key={c.id}>
                    <button type="button" className="link-btn" onClick={() => openHistoricalCampaign(c)}>
                      {c.displayName || c.playId}
                    </button>
                    <span className="earlier-campaign-meta">
                      {c.status}
                      {c.sentAt ? ` · sent ${new Date(c.sentAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}` : ""}
                      {c.frozen ? " · locked" : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
          {activePage === "campaigns" && (
            approvedPlays.length ? (
              <div className="workspace">
                {/* C1: left rail — every approved play in one grouped list. */}
                <aside className="workspace-rail">
                  {campaignGroups.map((group) => (
                    <div key={group.key} className="rail-group">
                      <div className="rail-group-head">{group.label}</div>
                      {group.rows.map(({ play, group: g }) => (
                        <button
                          key={play.id}
                          className={`rail-row ${reviewPlay?.id === play.id ? "selected" : ""}`}
                          onClick={() => setReviewPlayId(play.id)}
                        >
                          <span className={`rail-icon ${g}`}><Icon name={iconForPlay(play)} size={16} /></span>
                          <span className="rail-row-body">
                            <strong>{play.play_name || play.play_id}</strong>
                            <small>{formatAudience(play.audience_size)} customers</small>
                          </span>
                        </button>
                      ))}
                    </div>
                  ))}
                </aside>

                {/* C2: right pane — single stepper workspace for the selected play. */}
                <section className="workspace-pane" ref={rightPaneRef}>
                  {reviewPlay ? (() => {
                    const hasTemplate = Boolean(selectedTemplateByPlay[reviewPlay.id]);
                    const isApproved = approvedForSend.includes(reviewPlay.id);
                    const isSent = selectedCampaignGroup === "sent";
                    // Send unlocks only after explicit approval — this is the gate
                    // that separates "reviewing" from "ready to send".
                    // P-A2: numbered steps. A step is "done" if a later step is
                    // reachable (its prerequisite is met); the current step is active.
                    const stepOrder = ["copy", "audience", "send"];
                    const currentIndex = stepOrder.indexOf(workspaceStep);
                    const steps = [
                      { key: "copy", label: "Edit email", enabled: true },
                      { key: "audience", label: "Review audience", enabled: hasTemplate },
                      { key: "send", label: "Review & create draft", enabled: isApproved },
                    ];
                    const preview = selectedCampaign ? (audiencePreviewsByCampaign[selectedCampaign.id] || selectedCampaign.klaviyoAudience || null) : null;
                    // The name actually sent to the provider, for the
                    // find-by-name fallback. Falls back to the display name only
                    // when no handoff has happened.
                    const storedName = campaignRowByPlay[reviewPlay.id]?.providerCampaignName
                      || campaignRowByPlay[reviewPlay.id]?.displayName
                      || selectedCampaign?.playTitle;
                    const publishing = selectedCampaign && publishingCampaignId === selectedCampaign.id;
                    const created = Boolean(selectedCampaign?.klaviyoTemplateId);
                    return (
                      <div className="workspace-card">
                        <div className="workspace-head">
                          <h3>{reviewPlay.play_name || reviewPlay.play_id}</h3>
                          {reviewPlay.play_one_liner ? <p className="workspace-oneliner">{reviewPlay.play_one_liner}</p> : null}
                          <span className="workspace-audience">{formatAudience(reviewPlay.audience_size)} customers matched</span>
                        </div>

                        {/* P-A2: numbered stepper connected by a rule */}
                        <ol className="stepper">
                          {steps.map((step, i) => {
                            const state = i === currentIndex ? "current" : i < currentIndex && step.enabled ? "done" : step.enabled ? "upcoming" : "locked";
                            return (
                              <li key={step.key} className={`step ${state}`}>
                                <button
                                  type="button"
                                  className="step-btn"
                                  disabled={!step.enabled}
                                  onClick={() => step.enabled && setWorkspaceStep(step.key)}
                                >
                                  <span className="step-marker">{state === "done" ? <Icon name="check" size={14} /> : state === "locked" ? <Icon name="lock" size={13} /> : i + 1}</span>
                                  <span className="step-label">{step.label}</span>
                                </button>
                              </li>
                            );
                          })}
                        </ol>

                        <div className="workspace-step-body">
                          {workspaceStep === "copy" ? (
                            beaconTemplates.length ? (
                              <CampaignReviewPane
                                play={reviewPlay}
                                brandContext={brandContext}
                                beaconTemplates={beaconTemplates}
                                klaviyoTemplates={klaviyoOnlyTemplates}
                                selectedTemplate={selectedTemplate}
                                onChooseTemplate={(templateId) => chooseTemplate(reviewPlay.id, templateId)}
                                draft={selectedDraft}
                                onChange={(field, value) => updateDraftField(reviewPlay.id, field, value)}
                                onRestoreField={(field) => restoreDraftField(reviewPlay.id, reviewPlay, field)}
                                onRefreshBrandContext={loadBrandContext}
                                onRefreshTemplates={loadKlaviyoTemplates}
                                klaviyoFailed={klaviyoTemplatesFailed}
                                agentCopy={agentCopyByPlay[reviewPlay.id] || null}
                                copyStatus={copyStatusByPlay[reviewPlay.id] || null}
                                draftEdits={draftEditsByPlay[reviewPlay.id] || {}}
                                saveState={saveStateByPlay[reviewPlay.id]}
                                activeBrandTemplateVersion={brandTemplateVersion}
                                brandDesign={brandDesign}
                                destinationUrl={destinationByPlay[reviewPlay.id]}
                                onChangeDestination={(value) => changeDestination(reviewPlay.id, value)}
                                onPreviewRendered={(info) => {
                                  approvedRender.current[reviewPlay.id] = info;
                                  // No-op when unchanged. A new object identity
                                  // here is enough to re-render the parent and
                                  // restart the cycle.
                                  setReviewPreviewHtmlByPlay((prev) => (
                                    prev[reviewPlay.id] === (info.html || "")
                                      ? prev
                                      : { ...prev, [reviewPlay.id]: info.html || "" }
                                  ));
                                }}
                                campaignSignature={campaignSignature({
                                  edits: draftEditsByPlay[reviewPlay.id],
                                  destinationUrl: destinationByPlay[reviewPlay.id],
                                })}
                                onRetrySave={() => retrySave(reviewPlay.id)}
                                onRewrite={(steer) => fetchCopyForPlay(reviewPlay, selectedTemplate, { regenerate: true, steer })}
                              />
                            ) : (
                              <div className="empty-panel">Loading starting copy…</div>
                            )
                          ) : null}

                          {workspaceStep === "audience" && selectedCampaign ? (
                            <div className="audience-step">
                              <div className="segment-spec">
                                <div><span>Audience</span><strong>{selectedCampaign.segment || reviewPlay.audience_archetype}</strong></div>
                                <div><span>Suppression</span><strong>{selectedCampaign.suppression || "Standard unsubscribe + recent-send suppression"}</strong></div>
                              </div>
                              {/* The holdout is stated before the send, never
                                  discovered after it. A merchant who chooses to
                                  hold a group back trusts the result; one who
                                  finds out later does not. */}
                              {preview?.holdout ? (
                                <div className="holdout-note">
                                  <strong>
                                    {formatAudience(preview.holdout.treated)} of {formatAudience(preview.holdout.treated + preview.holdout.held)} customers will receive this.
                                  </strong>
                                  {preview.holdout.held > 0 ? (
                                    <span>
                                      We hold back {formatAudience(preview.holdout.held)} and send them nothing. In 30 days we compare the
                                      two groups — it's the only way to tell you what this campaign earned, instead of what those
                                      customers would have bought anyway.
                                    </span>
                                  ) : (
                                    <span>
                                      Everyone matched will receive this. Because no group is held back, Results can show what these
                                      customers did afterwards, but not how much of it this campaign caused.
                                    </span>
                                  )}
                                  <div className="holdout-controls">
                                    <label>
                                      Hold back
                                      <select
                                        value={String(preview.holdout.pct)}
                                        onChange={(event) => changeHoldout(selectedCampaign.id, Number(event.target.value))}
                                      >
                                        <option value="0.05">5%</option>
                                        <option value="0.1">10%</option>
                                        <option value="0.15">15%</option>
                                      </select>
                                    </label>
                                    {preview.holdout.pct > 0 ? (
                                      <button type="button" className="link-btn" onClick={() => changeHoldout(selectedCampaign.id, 0)}>
                                        Send to everyone
                                      </button>
                                    ) : (
                                      <button type="button" className="link-btn" onClick={() => changeHoldout(selectedCampaign.id, 0.1)}>
                                        Hold back 10% so this can be measured
                                      </button>
                                    )}
                                  </div>
                                </div>
                              ) : null}
                              {(() => {
                                const summary = summarizeAudience({
                                  audience: preview,
                                  breakdown: preview?.breakdown,
                                  originRunId: preview?.originRunId,
                                  inputProvenance: preview?.inputProvenance,
                                });
                                if (!summary.available) {
                                  return <div className="notice-line">{summary.message}</div>;
                                }
                                return (
                                  <div className="audience-breakdown">
                                    <div className="audience-rows">
                                      {summary.rows.map((row) => (
                                        <div key={row.key} className="audience-row">
                                          <span className="audience-row-label">{row.label}</span>
                                          <strong className="audience-row-value">{row.value}</strong>
                                          <span className="audience-row-help">{row.help}</span>
                                        </div>
                                      ))}
                                    </div>
                                    {/* Only exclusions the API can evidence, each with its
                                        own reason. Silence where there is none. */}
                                    {summary.exclusions.map((exclusion) => (
                                      <p key={exclusion.code} className="audience-note">{exclusion.label}</p>
                                    ))}
                                    {summary.noComparisonWarning ? (
                                      <p className="audience-note warn">{summary.noComparisonWarning}</p>
                                    ) : null}
                                    {summary.providerNote ? (
                                      <p className="audience-note">{summary.providerNote}</p>
                                    ) : null}
                                    <p className="audience-note">
                                      Actual sent: <strong>{summary.actualSentLabel}</strong>
                                    </p>
                                    {summary.stale ? (
                                      <p className="audience-note">This campaign uses an earlier verified briefing.</p>
                                    ) : null}
                                  </div>
                                );
                              })()}

                              <div className="recipient-preview">
                                <div className="recipient-preview-head">
                                  <div>
                                    <span className="section-meta">Recipient preview</span>
                                    <strong>{preview ? (preview.materialized === false ? "Held this run" : `${preview.count} matched emails`) : "Not loaded"}</strong>
                                  </div>
                                  <button className="btn" onClick={() => previewCampaignAudience(selectedCampaign)} disabled={previewingCampaignId === selectedCampaign.id}>
                                    {previewingCampaignId === selectedCampaign.id ? "Loading..." : "Show emails"}
                                  </button>
                                </div>
                                {/* R1: the engine deliberately did not materialize an auditable audience
                                    this run — a correct typed absence, not "0 matched". Explain it. */}
                                {preview && preview.materialized === false ? (
                                  <div className="empty-panel inline">
                                    This audience isn't ready to send this run — BeaconAI held it until there's enough store data to build an auditable list. It unlocks as more orders sync.
                                  </div>
                                ) : preview?.recipients?.length ? (
                                  <div className="recipient-list">
                                    {preview.recipients.slice(0, 25).map((recipient) => (
                                      <div key={`${recipient.customerId || recipient.email}-${recipient.email}`} className="recipient-row">
                                        <strong>{recipient.email}</strong>
                                      </div>
                                    ))}
                                    {preview.suppressedCount ? <small>{preview.recipients.length} of {preview.memberCount} have an email on file{preview.recipients.length > 25 ? ` · showing first 25` : ""}.</small> : preview.recipients.length > 25 ? <small>Showing first 25 of {preview.recipients.length} recipients.</small> : null}
                                  </div>
                                ) : preview ? (
                                  <div className="empty-panel inline">No recipient emails on file for this audience yet.</div>
                                ) : null}
                              </div>
                            </div>
                          ) : null}

                          {workspaceStep === "send" && selectedCampaign ? (() => {
                            const preview = audiencePreviewsByCampaign[selectedCampaign.id] || null;
                            const summary = summarizeAudience({
                              audience: preview, breakdown: preview?.breakdown,
                              originRunId: preview?.originRunId, inputProvenance: preview?.inputProvenance,
                            });
                            const sender = summarizeSender(senderIdentity);
                            const rendered = approvedRender.current[reviewPlay.id] || null;
                            const storedRow = campaignRowByPlay[reviewPlay.id] || null;
                            const frozenHtml = storedRow?.renderedHtml || null;
                            const previewHtmlForReview = reviewPreviewHtmlByPlay[reviewPlay.id] || null;
                            return (
                              <FinalReviewPanel
                                campaign={selectedCampaign}
                                summary={summary}
                                sender={sender}
                                design={brandDesign?.configured
                                  ? `${brandContext?.brandName || "Your store"} approved design${brandDesign.active?.version ? `, v${brandDesign.active.version}` : ""}`
                                  : "not set up yet"}
                                effectiveDestination={rendered?.effectiveDestinationUrl || destinationByPlay[reviewPlay.id]}
                                previewHtml={previewHtmlForReview}
                                frozenHtml={frozenHtml}
                                frozenAt={storedRow?.frozenAt
                                  ? new Date(storedRow.frozenAt).toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" })
                                  : null}
                                onEditStep={setWorkspaceStep}
                              />
                            );
                          })() : null}
                        </div>

                        {/* P-A3: sticky action bar — current step's primary action, right-aligned */}
                        <div className="workspace-actionbar">
                          {workspaceStep === "send" && isApproved && !isSent && !created ? (
                            <button type="button" className="link-btn" onClick={() => unapproveForSend(reviewPlay.id)}>Back to review</button>
                          ) : currentIndex > 0 ? (
                            <button type="button" className="link-btn" onClick={() => setWorkspaceStep(stepOrder[currentIndex - 1])}>Back</button>
                          ) : <span />}

                          {workspaceStep === "copy" ? (
                            <button className="btn primary" disabled={!hasTemplate} onClick={() => setWorkspaceStep("audience")}>Continue to audience</button>
                          ) : null}

                          {workspaceStep === "audience" ? (
                            isApproved ? (
                              <button className="btn primary" onClick={() => setWorkspaceStep("send")}>Continue to send</button>
                            ) : (
                              <button className="btn primary" onClick={() => approveForSend(reviewPlay.id)}>Continue to send</button>
                            )
                          ) : null}

                          {workspaceStep === "send" ? (() => {
                            // Everything below follows the Ticket D contract, via
                            // one presenter. Local status is not consulted: it is
                            // not evidence that anything happened at Klaviyo.
                            const campaignRowId = campaignIdByPlay[reviewPlay.id];
                            // undefined = not loaded yet, null = load failed.
                            // Neither is "nothing has happened yet"; treating
                            // them as such showed "Create draft" for a campaign
                            // already handed off.
                            const delivery = campaignRowId
                              ? deliveryByCampaignId[campaignRowId]
                              : { state: "not_started" };
                            const view = presentDelivery(
                              delivery ? { ...delivery, campaignName: storedName } : delivery,
                              { isFounder: false, klaviyoConnected: Boolean(status.klaviyo) }
                            );

                            if (view.primary?.action === "connect") {
                              return <button className="btn primary" onClick={() => startOAuth("klaviyo")}>{view.primary.label}</button>;
                            }
                            if (view.primary?.action === "create") {
                              return (
                                <button
                                  className="btn primary"
                                  onClick={() => createCampaignTemplateInKlaviyo(selectedCampaign)}
                                  disabled={publishing}
                                >
                                  {publishing ? "Creating…" : view.primary.label}
                                </button>
                              );
                            }
                            if (view.primary?.action === "open" && delivery?.providerCampaignUrl) {
                              return (
                                <a
                                  className="btn primary"
                                  href={delivery.providerCampaignUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  {view.primary.label} (opens in a new tab)
                                </a>
                              );
                            }
                            // No verified link, or an outcome we cannot act on.
                            // Deliberately renders no button at all rather than
                            // a dead one.
                            return <span className="send-state-label">{view.label}</span>;
                          })() : null}
                        </div>

                        {workspaceStep === "send" ? (() => {
                          const campaignRowId = campaignIdByPlay[reviewPlay.id];
                          const delivery = campaignRowId
                            ? deliveryByCampaignId[campaignRowId]
                            : { state: "not_started" };
                          const view = presentDelivery(
                            delivery ? { ...delivery, campaignName: storedName } : delivery,
                            { isFounder: false, klaviyoConnected: Boolean(status.klaviyo) }
                          );
                          return (
                            <div className={`delivery-panel ${view.state}`} role="status" aria-live="polite">
                              {view.message ? <strong>{view.message}</strong> : null}
                              {view.sentSummary ? <strong>{view.sentSummary}</strong> : null}
                              {view.detail ? <p>{view.detail}</p> : null}
                              {view.findHint ? <p>{view.findHint}</p> : null}
                              {view.caption ? <p className="delivery-caption">{view.caption}</p> : null}
                              {view.lastChecked ? <p className="delivery-checked">{view.lastChecked}</p> : null}
                              {view.lastCheckError ? (
                                <p className="delivery-checked">Couldn't check Klaviyo: {view.lastCheckError}. Showing the last confirmed status.</p>
                              ) : null}
                              {view.merchantNote ? <p className="delivery-checked">{view.merchantNote}</p> : null}
                            </div>
                          );
                        })() : null}
                      </div>
                    );
                  })() : (
                    <div className="empty-panel">Select a campaign from the left to start.</div>
                  )}
                </section>
              </div>
            ) : (
              <div className="empty-panel">Approve a play in Briefing to start your first campaign.</div>
            )
          )}

          {activePage === "results" && (
            <ResultsPage
              data={resultsData}
              loading={resultsLoading}
              error={resultsError}
              openId={openResultId}
              onToggle={(id) => setOpenResultId((current) => (current === id ? null : id))}
              onRetry={() => setResultsReload((n) => n + 1)}
              onLoadMore={() => setResultsLimit((n) => n + 100)}
              onResync={async () => { await syncShopify(); setResultsReload((n) => n + 1); }}
              resyncBusy={loading}
              onGoToCampaigns={() => setActivePage("campaigns")}
              playTitleFor={(playId) =>
                workflowPlays.find((p) => (p.play_id || p.id) === playId)?.play_name
                || finalCampaigns.find((c) => c.id === playId)?.playTitle
                || titleizeId(playId)}
            />
          )}

          {activePage === "setup" && (
            <>
              <div className="integration-card settings-store-card">
                <h3>Shopify store</h3>
                <p>Choose which store BeaconAI is working with.</p>
                <form className="settings-store-form" onSubmit={saveShopDomain}>
                  <input
                    id="shop-domain"
                    value={shopDomainDraft}
                    onChange={(event) => setShopDomainDraft(event.target.value)}
                    placeholder="store.myshopify.com"
                  />
                  <button className="btn primary" type="submit">Use store</button>
                </form>
              </div>

              <div className="setup-grid">
                <div className="integration-card">
                  <h3>Shopify</h3>
                  <p>{status.shopify ? "Connected. BeaconAI refreshes products, customers, and orders from this store." : "Connect Shopify to load products, customers, and orders."}</p>
                  <div className="action-row">
                    <button className="btn primary" onClick={status.shopify ? syncShopify : () => startOAuth("shopify")} disabled={status.shopify && loading}>{status.shopify ? (loading ? "Syncing…" : "Refresh Shopify now") : "Connect Shopify"}</button>
                  </div>
                </div>
                <div className="integration-card">
                  <h3>Klaviyo</h3>
                  <p>{status.klaviyo ? "Connected. Templates and campaigns are created in this account." : "Connect Klaviyo to create campaign drafts from BeaconAI."}</p>
                  <div className="action-row">
                    <button className="btn primary" onClick={status.klaviyo ? loadKlaviyoTemplates : () => startOAuth("klaviyo")}>{status.klaviyo ? "Refresh templates" : "Connect Klaviyo"}</button>
                  </div>
                </div>
              </div>
            </>
          )}

          {selectedEvidence ? (
            <div className="drawer-backdrop" onClick={() => setSelectedEvidence(null)}>
              <div className="evidence-drawer" onClick={(event) => event.stopPropagation()}>
                <button className="drawer-close" aria-label="Close" onClick={() => setSelectedEvidence(null)}><Icon name="close" size={16} /></button>
                <div className="section-kicker">Evidence drawer</div>
                <h2>{selectedEvidence.play_name || selectedEvidence.play_id}</h2>
                {/* LLM prose when authored; else the data chip grid (Pivot 2). */}
                {selectedEvidence.mechanism
                  ? <p>{selectedEvidence.mechanism}</p>
                  : <EvidenceChips play={selectedEvidence} />}
                {showAdvanced ? <JsonBlock title="Play JSON" value={selectedEvidence} /> : null}
              </div>
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}

// Mounts only when there is somewhere to mount. Importing this module used to
// bootstrap the whole app as a side effect, which made it impossible to render
// App in a test — and so nothing ever did, which is how two missing imports
// reached a browser.
const rootElement = typeof document !== "undefined" ? document.getElementById("root") : null;
if (rootElement) createRoot(rootElement).render(<App />);
