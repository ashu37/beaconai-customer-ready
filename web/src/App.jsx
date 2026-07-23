import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api";
import { baseEngineRun } from "./engineMock";
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

function templateForPlay(play) {
  const key = play?.play_id || play?.id;
  return PLAY_TEMPLATE_MAP[key] || DEFAULT_STARTING_TEMPLATE;
}

function StatCard({ label, value, detail }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {detail ? <div className="stat-detail">{detail}</div> : null}
    </div>
  );
}

function HomeMetricCard({ label, value, detail, tone = "neutral" }) {
  return (
    <div className={`home-metric-card ${tone}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {detail ? <div className="stat-detail">{detail}</div> : null}
    </div>
  );
}

function HomeModule({ title, detail, action, onAction, children }) {
  return (
    <div className="home-module">
      <div className="home-module-head">
        <div>
          <h3>{title}</h3>
          {detail ? <p>{detail}</p> : null}
        </div>
        {action ? <button className="btn" onClick={onAction}>{action}</button> : null}
      </div>
      {children}
    </div>
  );
}

function ConnectionCard({ label, connected, detail, onAction }) {
  return (
    <div className={`connection-card ${connected ? "connected" : ""}`}>
      <div>
        <span className="connection-dot" />
        <strong>{label}</strong>
        <p>{detail}</p>
      </div>
      <button className="btn" onClick={onAction}>{connected ? "Refresh" : "Connect"}</button>
    </div>
  );
}

function OnboardingStep({ number, title, detail, done, action, onAction, secondaryAction, onSecondaryAction }) {
  return (
    <div className={`onboarding-step ${done ? "done" : ""}`}>
      <div className="onboarding-step-num">{done ? "✓" : number}</div>
      <div className="onboarding-step-body">
        <div className="onboarding-step-head">
          <div>
            <h3>{title}</h3>
            <p>{detail}</p>
          </div>
          <span className={`onboarding-status ${done ? "done" : ""}`}>{done ? "Complete" : "Next"}</span>
        </div>
        <div className="action-row">
          {action ? <button className="btn primary" onClick={onAction}>{action}</button> : null}
          {secondaryAction ? <button className="btn" onClick={onSecondaryAction}>{secondaryAction}</button> : null}
        </div>
      </div>
    </div>
  );
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

function EmailPreview({ campaign }) {
  if (!campaign) return <div className="empty-panel">Run analysis to generate a campaign preview.</div>;
  return (
    <div className="email-preview">
      <div className="email-topline">
        <span>Subject</span>
        <strong>{campaign.email?.subject}</strong>
      </div>
      <div className="email-body" dangerouslySetInnerHTML={{ __html: campaign.email?.html || "" }} />
      <div className="sms-box">
        <div className="section-kicker">SMS copy</div>
        {campaign.sms}
      </div>
    </div>
  );
}

function JsonBlock({ title, value }) {
  return (
    <details className="json-block">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function PlaceholderPlay({ play }) {
  return (
    <div className="placeholder-play">
      <div className="play-num">{play.play_id}</div>
      <h3>{play.play_name || play.play_id}</h3>
      <p>{play.mechanism}</p>
      <div className="evidence-row">
        {play.audience_archetype ? <span>{play.audience_archetype}</span> : null}
        {play.audience_size ? <span>Audience: {play.audience_size}</span> : null}
        {play.evidence?.evidence_class ? <span>Evidence: {play.evidence.evidence_class}</span> : null}
      </div>
    </div>
  );
}

function statusLabel(value) {
  return String(value || "pending").replaceAll("_", " ");
}

function readableMetaLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const normalized = raw.toLowerCase().replaceAll("_", " ");
  if (["engine", "review", "pending", "placeholder"].includes(normalized)) return null;
  if (normalized === "store observed") return "Observed in store data";
  return normalized.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function buildDashboardRun(placeholderRun, counts) {
  const productCount = placeholderRun?.input_summary?.products ?? counts.products ?? 0;
  const customerCount = placeholderRun?.input_summary?.customers ?? counts.customers ?? 0;
  const orderCount = placeholderRun?.input_summary?.orders ?? counts.orders ?? 0;
  const total = Math.max(productCount + customerCount + orderCount, 1);

  if (!placeholderRun) {
    return {
      ...baseEngineRun,
      audience_segments: baseEngineRun.audience_segments.map((segment) => {
        const value = segment.label === "Known customers" ? customerCount : segment.label === "Purchased orders" ? orderCount : segment.label === "Catalog products" ? productCount : Math.max(customerCount - orderCount, 0);
        return { ...segment, n: value, pct: Math.round((value / total) * 100) };
      }),
    };
  }

  return {
    ...baseEngineRun,
    ...placeholderRun,
    slate: {
      ...baseEngineRun.slate,
      ...placeholderRun.slate,
    },
    predictive_models: {
      ...baseEngineRun.predictive_models,
      ...placeholderRun.predictive_models,
    },
    audience_segments: (placeholderRun.audience_segments || baseEngineRun.audience_segments).map((segment) => ({
      ...segment,
      pct: Math.round(((segment.n || 0) / total) * 100),
      color_role: segment.color_role || "loyal",
    })),
    cohort_retention: baseEngineRun.cohort_retention,
    month_2_delta: baseEngineRun.month_2_delta,
  };
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
    mechanism: narration.play_thesis || play.recommendation_text || play.mechanism || play.rationale || play.why || "Recommendation ready for your review.",
    audience_archetype: play.audience_archetype || play.audience?.definition || play.audience?.description || play.audience || "Recommended audience",
    audience_size: audienceSize,
    confidence: play.confidence_label || play.confidence || play.model_confidence || "engine",
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

function buildWorkflowPlays({ atulEngineResult, campaignPackages, campaign }) {
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
  if (packagePlays.length) return packagePlays;

  if (!campaign) return [];

  return [{
    id: "mock-engine-campaign",
    play_id: "mock-engine-campaign",
    play_name: campaign.play_name,
    mechanism: campaign.opportunity_context?.reason || "Mock engine campaign generated.",
    audience_archetype: campaign.audience?.description,
    audience_size: campaign.audience?.size,
    confidence: campaign.confidence_label,
    source: "mock",
    raw: campaign,
  }];
}

function buildCampaignFromSelection(play, template, edits = {}) {
  if (!play || !template) return null;
  const prompt = play.template_prompt || {};
  const narration = play.narration || {};
  const draft = {
    // Key by play id (1:1 with its selected template). A composite id broke every
    // downstream lookup (grouping, audience preview, klaviyo assets) that keys by play.id.
    id: play.id,
    playTitle: play.play_name || play.play_id,
    templateName: template.name,
    templateSource: template.source,
    status: "draft",
    customers: play.audience_size || 0,
    segment: play.audience_archetype || "Recommended audience",
    subject: template.subject || prompt.subject || `${play.play_name} campaign`,
    previewText: template.previewText || prompt.previewText || "Selected template ready for campaign review.",
    bodyH2: template.bodyH2 || prompt.headline || play.play_name || "BeaconAI campaign",
    bodyP1: template.bodyP1 || prompt.body || prompt.support || "Here's what's new for you.",
    bodyP2: prompt.support || "You'll pick and edit the exact template before anything is sent.",
    cta: template.cta || prompt.cta || "Shop the picks",
    sendTime: "Manual review",
    suppression: "Recent purchasers, unsubscribes, suppressed profiles",
  };
  return { ...draft, ...edits, id: draft.id, playTitle: draft.playTitle, templateName: draft.templateName, templateSource: draft.templateSource, status: draft.status };
}

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

const CONFIDENCE_TITLE = "How strongly your store's data supports this play. Improves as more orders sync.";

function RecommendationRow({ play, selected, approved = false, onSelect }) {
  const confidence = play.confidence || play.confidence_label || play.model_confidence || null;
  const confidenceLabel = readableMetaLabel(confidence);
  const evidenceLine = play.evidence_line || null;
  const lane = classifyPlayLane(play);
  const selectedActionable = selected && lane !== "considered";
  return (
    <button className={`recommendation-row ${selected ? "selected" : ""}`} onClick={() => onSelect(play.play_id || play.id)}>
      <span className={`recommendation-icon ${lane}`}>{lane === "experiment" ? "✦" : lane === "considered" ? "□" : "▷"}</span>
      <span className="recommendation-row-body">
        {selectedActionable ? <span className="recommendation-overline">Primary</span> : null}
        <span className="recommendation-title">{play.play_name || play.play_id}</span>
        <span className="recommendation-meta">
          <span>{formatAudience(play.audience_size)} customers</span>
          {confidenceLabel ? (
            <span className="recommendation-meta-item" title={CONFIDENCE_TITLE}>
              <span className={`confidence-dot ${confidenceTone(confidence)}`} />
              {confidenceLabel} confidence
            </span>
          ) : null}
          {approved ? <span className="approved-pill">✓ Approved</span> : null}
        </span>
        {evidenceLine ? <span className="recommendation-evidence-line">{evidenceLine}</span> : null}
      </span>
      <span className="recommendation-chevron">›</span>
    </button>
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
  const oneLiner = play.play_one_liner || play.audience_archetype || "";
  const audienceLabel = formatAudience(play.audience_size);
  const bannerText = oneLiner
    ? `${oneLiner} — ${audienceLabel} customers.`
    : `${audienceLabel} customers in this group.`;
  const heldReason = play.reason_display || "BeaconAI needs more store data before recommending this.";
  const tabLabels = [
    ["thesis", "Play thesis"],
    ["send", "What we'd send"],
    ["evidence", "Evidence"],
    ["audience", "Audience"],
    ...(showAdvanced ? [["sensitivity", "Sensitivity"]] : []),
  ];

  return (
    <div className="recommendation-detail">
      <div className="recommendation-detail-head">
        <span className={`recommendation-icon large ${lane}`}>{lane === "experiment" ? "✦" : lane === "considered" ? "□" : "▷"}</span>
        <div>
          <div className="section-kicker">{lane === "experiment" ? "Recommended experiment" : lane === "considered" ? "Not ready yet" : "Primary recommendation"}</div>
          <h2>{play.play_name || play.play_id}</h2>
        </div>
        <button className="icon-menu" type="button" aria-label="More actions">...</button>
      </div>

      {play.evidence_line ? <div className="detail-evidence-line">{play.evidence_line}</div> : null}

      <div className="recommendation-stat-strip">
        <div>
          <strong>{audienceLabel}</strong>
          <span>Customers</span>
        </div>
        {revenueLabel ? (
          <div>
            <strong>{revenueLabel}</strong>
            <span>Est. opportunity</span>
          </div>
        ) : null}
        <div>
          <strong>{statusLabel(confidence)}</strong>
          <span title={CONFIDENCE_TITLE}>Confidence</span>
        </div>
      </div>

      <div className="recommendation-banner">{bannerText}</div>

      <div className="recommendation-tabs">
        {tabLabels.map(([key, label]) => (
          <button
            key={key}
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
            <div className="detail-copy-block">
              <div className="section-kicker">Play thesis</div>
              <p>{narration.play_thesis || play.mechanism || "Recommendation ready for merchant review."}</p>
            </div>
            {revenue ? (
              <div className="revenue-range">
                <div className="section-kicker">Est. opportunity</div>
                <div className="range-track">
                  <span className="range-fill" />
                  <span className="range-marker" style={{ left: "88%" }} />
                </div>
                <div className="range-labels">
                  <span>{revenue.labelLow}</span>
                  {revenue.labelMedian ? <span>median {revenue.labelMedian}</span> : null}
                  <span>{revenue.labelHigh}</span>
                </div>
              </div>
            ) : null}
          </>
        ) : null}

        {activeTab === "send" ? (
          <>
            <div className="model-row">
              <span>Message angle</span>
              <strong>{narration.what_we_d_send || play.template_prompt?.support || play.play_name || "BeaconAI recommendation"}</strong>
            </div>
            <div className="model-row">
              <span>Template step</span>
              <strong>Choose in Campaigns after approving</strong>
            </div>
            <div className="model-row">
              <span>CTA</span>
              <strong>{play.template_prompt?.cta || "Personalized offer or reminder"}</strong>
            </div>
          </>
        ) : null}

        {activeTab === "evidence" ? (
          <>
            <div className="model-row">
              <span>Evidence summary</span>
              <strong>{narration.evidence_summary || play.evidence?.evidence_class || statusLabel(confidence)}</strong>
            </div>
            <div className="model-row">
              <span>Signal source</span>
              <strong>{play.evidence_source || play.evidence?.evidence_source || "Engine output"}</strong>
            </div>
            <div className="model-row">
              <span>Decision status</span>
              <strong>{play.reason_code ? statusLabel(play.reason_code) : "Ready for review"}</strong>
            </div>
            <div className="evidence-fineprint">{play.play_id || play.id}</div>
          </>
        ) : null}

        {activeTab === "audience" ? (
          <>
            <div className="model-row">
              <span>Audience</span>
              <strong>{play.audience_archetype || "Recommended audience"}</strong>
            </div>
            <div className="model-row">
              <span>Estimated size</span>
              <strong>{formatAudience(play.audience_size)} customers</strong>
            </div>
            <div className="model-row">
              <span>Suppression</span>
              <strong>Recent purchasers, unsubscribes</strong>
            </div>
          </>
        ) : null}

        {activeTab === "sensitivity" ? (
          <>
            <div className="model-row">
              <span>Confidence</span>
              <strong>{statusLabel(confidence)}</strong>
            </div>
            <div className="model-row">
              <span>Estimated upside</span>
              <strong>{formatRevenueRange(play)}</strong>
            </div>
            <div className="model-row">
              <span>Review note</span>
              <strong>{play.reason_code ? "Held for now — needs more store data" : "Merchant approval required before template work"}</strong>
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
                ✓ In campaigns →
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

function EnginePlayCard({ play, onGreenlight, onViewEvidence }) {
  const gates = play.gate_status || {};
  return (
    <div className={`engine-play-card ${play.role === "recommended_experiment" ? "experiment" : ""}`}>
      <div className="play-role-badge">{play.reason_code ? "Considered - held" : "Recommendation"}</div>
      <h3>{play.play_name || play.play_id}</h3>
      <div className="play-archetype">{play.audience_archetype || "ENGINE_PLACEHOLDER"}</div>
      <p>{play.mechanism}</p>
      <div className="evidence-class-row">
        <span className="evidence-class">{play.evidence?.evidence_class || play.reason_code || "placeholder"}</span>
        <span className="evidence-class-desc">
          {play.evidence?.p_value ? `p = ${play.evidence.p_value}` : "Awaiting real engine evidence"}
        </span>
      </div>
      <div className="gates-row">
        <span className={`gate-pill ${gates.cohort_pvalue ? "pass" : ""}`}>Cohort p-value</span>
        <span className={`gate-pill ${gates.prior_validation ? "pass" : ""}`}>Prior validation</span>
        <span className={`gate-pill ${gates.ml_fit ? "pass" : ""}`}>ML fit</span>
      </div>
      <div className="play-meta-row">
        <div>
          <span className="play-meta-label">Audience</span>
          <strong>{play.audience_size?.toLocaleString?.() || "—"}</strong>
        </div>
        <div>
          <span className="play-meta-label">Revenue</span>
          <strong>{play.revenue_range ? `$${play.revenue_range.low}-$${play.revenue_range.high}` : "—"}</strong>
        </div>
        <div>
          <span className="play-meta-label">Model</span>
          <strong>{play.model || "placeholder"}</strong>
        </div>
      </div>
      <div className="play-cta-row">
        <button className="btn primary" onClick={() => onGreenlight?.(play)}>Greenlight play</button>
        <button className="btn" onClick={() => onViewEvidence?.(play)}>View evidence</button>
      </div>
    </div>
  );
}

function ModelCardPanel({ model }) {
  return (
    <div className="model-card">
      <div className="model-card-head">
        <div>
          <h3>{model.display_name}</h3>
          <span>{model.name || model.handoff_status || "placeholder"}</span>
        </div>
        <strong>{model.fit_status}</strong>
      </div>
      <div className="model-stats">
        <span>Observed <strong>{model.n_observed?.toLocaleString?.() || "—"}</strong></span>
        <span>Window <strong>{model.training_window_days ? `${model.training_window_days}d` : "—"}</strong></span>
        <span>MAPE <strong>{model.holdout_mape ? `${(model.holdout_mape * 100).toFixed(1)}%` : "—"}</strong></span>
      </div>
      {(model.fit_warnings || []).map((warning) => <div className="model-warning" key={warning}>{warning}</div>)}
    </div>
  );
}

function SegmentBars({ segments }) {
  const max = Math.max(...segments.map((segment) => segment.n || 0), 1);
  return (
    <div className="chart-panel">
      {segments.map((segment) => (
        <div className="segment-row" key={segment.label}>
          <div className="segment-meta">
            <span>{segment.label}</span>
            <strong>{segment.n?.toLocaleString?.() || 0}</strong>
          </div>
          <div className="segment-track">
            <div className={`segment-fill ${segment.color_role || "loyal"}`} style={{ width: `${Math.max(((segment.n || 0) / max) * 100, 4)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function CohortRetentionChart({ curves }) {
  return (
    <div className="chart-panel cohort-panel">
      {curves.map((curve) => (
        <div className="cohort-row" key={curve.cohort_label}>
          <div className="cohort-label">{curve.cohort_label}</div>
          <div className="cohort-points">
            {curve.points.map((point) => (
              <span key={point.month} style={{ height: `${Math.max(point.p50 * 100, 10)}%` }} title={`M${point.month}: ${(point.p50 * 100).toFixed(0)}%`} />
            ))}
          </div>
        </div>
      ))}
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
        Send “{selected.subject}” to {selected.customers} matched customers through your Klaviyo account.
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
        <div className="success-box">
          Created Klaviyo campaign <strong>{selected.klaviyoCampaignId || selected.klaviyoTemplateId}</strong>
          {selected.klaviyoAudience ? ` for ${selected.klaviyoAudience.count} run-matched recipients.` : "."}
          {selected.klaviyoSendJobId ? ` Send job: ${selected.klaviyoSendJobId}.` : ""}
        </div>
      ) : null}
    </div>
  );
}

function EditableCampaignDraft({ draft, onChange, onSendToCampaigns }) {
  if (!draft) return null;

  const update = (field) => (event) => onChange(field, event.target.value);

  return (
    <div className="draft-editor">
      <div className="draft-editor-form">
        <label>
          <span>Subject line</span>
          <input value={draft.subject} onChange={update("subject")} />
        </label>
        <label>
          <span>Preview text</span>
          <input value={draft.previewText} onChange={update("previewText")} />
        </label>
        <label>
          <span>Headline</span>
          <input value={draft.bodyH2} onChange={update("bodyH2")} />
        </label>
        <label>
          <span>Main message</span>
          <textarea value={draft.bodyP1} onChange={update("bodyP1")} rows={4} />
        </label>
        <label>
          <span>Support copy</span>
          <textarea value={draft.bodyP2} onChange={update("bodyP2")} rows={3} />
        </label>
        <div className="draft-editor-row">
          <label>
            <span>CTA</span>
            <input value={draft.cta} onChange={update("cta")} />
          </label>
          <label>
            <span>Send timing</span>
            <input value={draft.sendTime} onChange={update("sendTime")} />
          </label>
        </div>
        <label>
          <span>Suppression</span>
          <input value={draft.suppression} onChange={update("suppression")} />
        </label>
      </div>

      <div className="campaign-detail-panel draft-preview-panel">
        <div className="pkg-origin">
          <span>Template</span>
          <strong>{draft.templateName} · {draft.templateSource}</strong>
        </div>
        <div className="email-preview">
          <div className="email-topline">
            <span>Subject</span>
            <strong>{draft.subject}</strong>
          </div>
          <div className="email-topline">
            <span>Preview</span>
            <strong>{draft.previewText}</strong>
          </div>
          <div className="email-body">
            <h1>{draft.bodyH2}</h1>
            <p>{draft.bodyP1}</p>
            <p>{draft.bodyP2}</p>
            <p><strong>{draft.cta}</strong></p>
          </div>
        </div>
        <div className="segment-spec">
          <div><span>Audience</span><strong>{draft.segment}</strong></div>
          <div><span>Send</span><strong>{draft.sendTime}</strong></div>
          <div><span>Suppression</span><strong>{draft.suppression}</strong></div>
        </div>
        <div className="action-row">
          <button className="btn primary" onClick={onSendToCampaigns}>Send to Campaigns</button>
        </div>
      </div>
    </div>
  );
}

// A3: per-field mapping from a draft field to the play's template_prompt value.
// "Restore suggested" resets a field to the suggested copy from the presenter's
// PLAY_DISPLAY (template_prompt) added in the first refactor.
function suggestedValueForField(play, field) {
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

function CampaignReviewPane({
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
}) {
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  // Phone preview mode: "inbox" = iOS-Mail list row, "email" = opened message.
  const [previewMode, setPreviewMode] = useState("inbox");
  const debounceRef = useRef(null);

  const refreshPreview = React.useCallback(async (currentDraft) => {
    if (!currentDraft) return;
    setPreviewLoading(true);
    try {
      const result = await api.previewCampaignHtml({ ...currentDraft, brandContext });
      setPreviewHtml(result.html || "");
    } catch (err) {
      // Leave the last good preview in place on transient failures.
    } finally {
      setPreviewLoading(false);
    }
  }, [brandContext]);

  // Immediate refresh when the play or selected template changes.
  useEffect(() => {
    if (draft) refreshPreview(draft);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [play?.id, selectedTemplate?.id]);

  // Debounced refresh (600ms) while the merchant types.
  useEffect(() => {
    if (!draft) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => refreshPreview(draft), 600);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft?.subject, draft?.previewText, draft?.bodyH2, draft?.bodyP1, draft?.bodyP2, draft?.cta]);

  const handleBlur = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    refreshPreview(draft);
  };

  const [changeOpen, setChangeOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const senderName = brandContext?.brandName || "Your store";
  const editFields = [
    { field: "subject", label: "Subject", type: "input" },
    { field: "previewText", label: "Preview text", type: "input" },
    { field: "bodyH2", label: "Headline", type: "input" },
    { field: "bodyP1", label: "Body", type: "textarea" },
    { field: "bodyP2", label: "Support line (optional)", type: "textarea" },
    { field: "cta", label: "Button label", type: "input" },
  ];
  const startingName = selectedTemplate?.name || "—";

  return (
    <div className="review-pane">
      {/* C4d: brand voice collapsed to a single line, expandable inline. */}
      {brandContext ? (
        <div className="voice-chip">
          <button type="button" className="voice-chip-line" onClick={() => setVoiceOpen((p) => !p)}>
            Voice: {brandContext.brandName} · {brandContext.category}
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

      {/* C3: auto-selected starting copy, one line + inline change. */}
      <div className="starting-copy">
        <span className="starting-copy-line">
          Starting copy: <strong>{startingName}</strong>
          <button type="button" className="link-btn" onClick={() => setChangeOpen((p) => !p)}>Change</button>
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
            {editFields.map(({ field, label, type }) => {
              // P-D4: field diverges from the suggested copy → show "Edited" +
              // offer Restore; when it matches, neither is shown.
              const edited = (draft[field] || "") !== (suggestedValueForField(play, field) || "");
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

            {/* C3: Advanced Klaviyo pairing moves to the bottom of the Copy step. */}
            <button
              type="button"
              className="advanced-toggle"
              onClick={() => setAdvancedOpen((prev) => !prev)}
            >
              Advanced: pair with an existing Klaviyo template
            </button>
            {advancedOpen ? (
              <div className="advanced-panel">
                <p className="advanced-help">Pairing keeps your Klaviyo template's name on the campaign. The email content below is still what gets sent.</p>
                <button type="button" className="btn small" onClick={onRefreshTemplates}>Refresh templates</button>
                <div className="template-grid">
                  {klaviyoTemplates.length ? klaviyoTemplates.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`template-option ${selectedTemplate?.id === item.id ? "selected" : ""}`}
                      onClick={() => onChooseTemplate(item.id)}
                    >
                      <span>Klaviyo</span>
                      <strong>{item.name}</strong>
                      <small>{item.previewText}</small>
                    </button>
                  )) : <div className="empty-panel">No existing Klaviyo templates. Connect Klaviyo and refresh to pair one.</div>}
                </div>
              </div>
            ) : null}
          </div>

          <div className="review-preview-pane">
            <div className="preview-toggle" role="tablist" aria-label="Preview mode">
              <button
                type="button"
                role="tab"
                aria-selected={previewMode === "inbox"}
                className={`preview-toggle-btn ${previewMode === "inbox" ? "active" : ""}`}
                onClick={() => setPreviewMode("inbox")}
              >
                Inbox
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={previewMode === "email"}
                className={`preview-toggle-btn ${previewMode === "email" ? "active" : ""}`}
                onClick={() => setPreviewMode("email")}
              >
                Email
              </button>
            </div>

            <div className="phone-frame">
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
                    title="Email preview"
                    className="phone-frame-iframe"
                    srcDoc={previewHtml}
                  />
                </div>
              )}
            </div>
            {previewLoading ? <div className="preview-status">Updating preview…</div> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MonthTwoDeltaPanel({ delta }) {
  return (
    <div className="delta-grid">
      <StatCard label="Previous p50 LTV" value={`$${delta.ltv_evolution.prev_p50}`} detail="placeholder" />
      <StatCard label="Current p50 LTV" value={`$${delta.ltv_evolution.curr_p50}`} detail="placeholder" />
      <StatCard label="Delta" value={`${delta.ltv_evolution.delta_pct >= 0 ? "+" : ""}${delta.ltv_evolution.delta_pct}%`} detail="month over month" />
      <div className="placeholder-panel">
        <div className="section-kicker">Audience movement</div>
        <div className="model-row"><span>Grew</span><strong>{delta.audiences_grew.join(", ")}</strong></div>
        <div className="model-row"><span>Shrank</span><strong>{delta.audiences_shrank.join(", ")}</strong></div>
      </div>
    </div>
  );
}

function BriefingStatStrip({ products, customers, orders, reviewPending, campaignsPending }) {
  const items = [
    ["Products", products],
    ["Customers", customers],
    ["Orders", orders],
    ["Needs review", reviewPending],
    ["In pipeline", campaignsPending],
  ];
  return (
    <div className="briefing-stat-strip">
      {items.map(([label, value]) => (
        <div key={label} className="briefing-stat">
          <strong>{value}</strong>
          <span>{label}</span>
        </div>
      ))}
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

function ResultsPage({ campaigns }) {
  const sent = campaigns.filter((item) => item.status === "created" || item.klaviyoSendJobId);
  const tracked = sent.length ? sent : campaigns;
  if (!tracked.length) {
    return (
      <div className="empty-panel">
        Results appear here after your first campaign goes out. BeaconAI tracks the customers each campaign targeted and reports what they did over the following 30 days.
      </div>
    );
  }
  return (
    <div className="results-list">
      {tracked.map((item) => {
        const base = item.sentAt || item.approvedAt || item.builtAt;
        const parsed = base ? new Date(base) : new Date();
        const reportDate = new Date(parsed.getTime());
        reportDate.setDate(reportDate.getDate() + 30);
        const reportLabel = reportDate.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        const sentLabel = base ? parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "Pending send";
        return (
          <div key={item.id} className="results-row">
            <div>
              <strong>{item.playTitle}</strong>
              <span>{sentLabel} · {formatAudience(item.customers)} customers</span>
            </div>
            <p className="results-status">Measurement in progress — first report {reportLabel}.</p>
          </div>
        );
      })}
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
    syncing: { title: "Syncing your store…", sub: "Pulling products, customers, and orders from Shopify." },
    synced: { title: "Store synced.", sub: null },
    analyzing: {
      title: `Analyzing ${orders} orders for opportunities…`,
      sub: "BeaconAI is sizing audiences and checking the evidence. This can take a minute.",
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
    "Reading your latest store snapshot…",
    "Sizing audiences…",
    "Checking the evidence behind each play…",
    "Estimating revenue opportunity…",
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
    <div className="briefing-working" role="status" aria-live="polite">
      <div className="first-run-spinner" aria-hidden="true" />
      <div className="briefing-working-text">
        <span>{messages[index]}</span>
        <div className="briefing-working-bar" aria-hidden="true">
          <div className="briefing-working-bar-fill" />
        </div>
      </div>
    </div>
  );
}

function App() {
  const [activePage, setActivePage] = useState("briefing");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [shopDomain, setShopDomain] = useState(api.shopDomain);
  const [shopDomainDraft, setShopDomainDraft] = useState(api.shopDomain);
  const [status, setStatus] = useState({ api: false, shopify: false, klaviyo: false, shopifySource: "none", klaviyoSource: "none" });
  const [sync, setSync] = useState(null);
  const [campaign, setCampaign] = useState(null);
  const [engineInput, setEngineInput] = useState(null);
  const [brandContext, setBrandContext] = useState(null);
  const [placeholderRun, setPlaceholderRun] = useState(null);
  const [atulEngineResult, setAtulEngineResult] = useState(null);
  const [klaviyoTemplates, setKlaviyoTemplates] = useState([]);
  // C3: true only when Klaviyo is connected but its template fetch failed/fell back.
  const [klaviyoTemplatesFailed, setKlaviyoTemplatesFailed] = useState(false);
  const [selectedTemplateByPlay, setSelectedTemplateByPlay] = useState({});
  const [draftEditsByPlay, setDraftEditsByPlay] = useState({});
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
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [flashCampaignId, setFlashCampaignId] = useState("");
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

  const counts = sync?.synced || {};
  const currentRunId = atulEngineResult?.presentedRun?.run_id || null;
  const pipelineStorageKey = shopDomain && currentRunId ? `beaconai:${shopDomain}:${currentRunId}:pipeline` : null;
  // O3 fix: persist first-run completion per shop so a page refresh does not
  // re-trigger a full Shopify sync (which surfaced a false "sync hit a problem").
  const firstRunDoneKey = shopDomain ? `beaconai:${shopDomain}:first-run-complete` : null;
  const dashboardRun = useMemo(() => buildDashboardRun(placeholderRun, counts), [placeholderRun, counts]);
  const workflowPlays = useMemo(
    () => buildWorkflowPlays({ atulEngineResult, campaignPackages, campaign }),
    [atulEngineResult, campaignPackages, campaign]
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
  const selectedDraft = reviewPlay && selectedTemplate ? buildCampaignFromSelection(reviewPlay, selectedTemplate, draftEditsByPlay[reviewPlay.id]) : null;
  const finalCampaigns = approvedPlays
    .map((play) => buildCampaignFromSelection(play, klaviyoTemplates.find((item) => item.id === selectedTemplateByPlay[play.id]), draftEditsByPlay[play.id]))
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
  const productCount = counts.products ?? engineInput?.products?.length ?? placeholderRun?.input_summary?.products ?? "—";
  const customerCount = counts.customers ?? engineInput?.customers?.length ?? placeholderRun?.input_summary?.customers ?? "—";
  const orderCount = counts.orders ?? engineInput?.orders?.length ?? placeholderRun?.input_summary?.orders ?? "—";
  const hasStoreSnapshot = productCount !== "—" && customerCount !== "—" && orderCount !== "—";
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
  const briefingUpdatedAt = formatUpdatedAt(atulEngineResult?.presentedRun?.generated_at);
  const briefingHeading = !workflowPlays.length
    ? "Run your briefing to see recommendations"
    : readyRowsCount
      ? `Your briefing is ready — ${readyRowsCount} plays for your review`
      : `No campaign-ready plays yet — ${consideredRows.length} need more data`;

  useEffect(() => {
    checkConnections();
    preloadStoreSnapshot();
    loadBrandContext();
    loadLatestRun();
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

  // O4: rehydrate pipeline state after O1's latest-run load resolves.
  // Stored key embeds the run_id, so a stale run's state is never read (discarded).
  useEffect(() => {
    if (!pipelineStorageKey || pipelineHydratedRef.current) return;
    pipelineHydratedRef.current = true;
    try {
      const raw = localStorage.getItem(pipelineStorageKey);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (saved.run_id && saved.run_id !== currentRunId) return; // stale → discard
      if (Array.isArray(saved.authorizedPackageIds)) setAuthorizedPackageIds(saved.authorizedPackageIds);
      if (Array.isArray(saved.approvedForSend)) setApprovedForSend(saved.approvedForSend);
      if (saved.selectedTemplateByPlay) setSelectedTemplateByPlay(saved.selectedTemplateByPlay);
      if (saved.draftEditsByPlay) setDraftEditsByPlay(saved.draftEditsByPlay);
      if (Array.isArray(saved.approvedPlayIds)) setRestoredApprovedPlayIds(saved.approvedPlayIds);
    } catch (_) {
      // Corrupt stored state is non-fatal; the merchant can re-approve.
    }
  }, [pipelineStorageKey, currentRunId]);

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
          segment: play.audience_archetype || "Recommended audience",
          subject: "Placeholder subject from engine play",
          previewText: "Waiting for real engine copy.",
          bodyH2: play.play_name || play.play_id,
          bodyP1: play.mechanism,
          bodyP2: "Replace this package with Atul engine output when available.",
          cta: "Review package",
          sendTime: "Manual review",
          suppression: "Recent purchasers, unsubscribes",
        }));
      if (!additions.length) return prev;
      return [...prev, ...additions];
    });
    setRestoredApprovedPlayIds([]);
  }, [restoredApprovedPlayIds, workflowPlays]);

  // O4: persist minimal pipeline state. TODO(auth): move to DB.
  useEffect(() => {
    if (!pipelineStorageKey) return;
    const approvedPlayIds = campaignPackages.map((item) => item.id);
    const payload = {
      run_id: currentRunId,
      approvedPlayIds,
      selectedTemplateByPlay,
      draftEditsByPlay,
      authorizedPackageIds,
      approvedForSend,
    };
    try {
      localStorage.setItem(pipelineStorageKey, JSON.stringify(payload));
    } catch (_) {
      // Storage may be unavailable (private mode); persistence is best-effort.
    }
  }, [pipelineStorageKey, currentRunId, campaignPackages, selectedTemplateByPlay, draftEditsByPlay, authorizedPackageIds, approvedForSend]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reviewPlayId]);

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

  async function checkConnections() {
    setLoading(true);
    setError("");
    const next = { api: false, shopify: false, klaviyo: false, shopifySource: "none", klaviyoSource: "none" };
    try {
      await api.health();
      next.api = true;
      try {
        const connection = await api.connectionStatus();
        next.shopify = Boolean(connection.status?.shopify?.connected);
        next.klaviyo = Boolean(connection.status?.klaviyo?.connected);
        next.shopifySource = connection.status?.shopify?.source || "none";
        next.klaviyoSource = connection.status?.klaviyo?.source || "none";
      } catch (_) {}
      try { await api.testShopify(); next.shopify = true; } catch (_) {}
      try { await api.testKlaviyo(); next.klaviyo = true; } catch (_) {}
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
      await preloadStoreSnapshot();
      showToast({ message: "Store synced" });
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

  async function runAnalysis() {
    const result = await runStep("Engine run", () => api.runEngine());
    setCampaign(result.campaign);
    setActivePage("campaigns");
    return result;
  }

  // Shared result-handling path for both a fresh engine run and O1 rehydration.
  function applyEngineResult(result) {
    setAtulEngineResult(result);
    setActivePage("briefing");
  }

  async function runAtulEngine(useFixture = false) {
    const result = await runStep(useFixture ? "Sample briefing refresh" : "Briefing refresh", () => api.runAtulEngine(useFixture));
    applyEngineResult(result);
    return result;
  }

  // O1: read-only rehydration of the latest run on mount. Never triggers an engine run.
  async function loadLatestRun() {
    if (!api.shopDomain) {
      setLatestRunChecked(true);
      setRehydrating(false);
      return;
    }
    setRehydrating(true);
    try {
      const result = await api.getLatestEngineRun();
      setLatestRunErrored(false);
      if (result.found) {
        applyEngineResult({ presentedRun: result.presentedRun });
        setLatestRunFound(true);
      } else {
        setLatestRunFound(false);
      }
    } catch (_) {
      // Fetch failed — this is NOT "no run yet". Flag the error so first-run
      // detection holds instead of kicking off a full sync on a transient blip.
      setLatestRunErrored(true);
      setLatestRunFound(false);
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

  async function runFullDemo() {
    const result = await runStep("Full demo", () => api.demoRun());
    setSync({ synced: result.synced, shopDomain: result.shopDomain });
    setCampaign(result.campaign);
    setActivePage("campaigns");
  }

  async function loadEngineInput() {
    const result = await runStep("Engine input load", () => api.getEngineInput());
    setEngineInput(result.input);
  }

  async function loadPlaceholderEngineRun() {
    const result = await runStep("Placeholder engine load", () => api.getPlaceholderEngineRun());
    setPlaceholderRun(result.engineRun);
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
        segment: play.audience_archetype || "Recommended audience",
        subject: "Placeholder subject from engine play",
        previewText: "Waiting for real engine copy.",
        bodyH2: play.play_name || play.play_id,
        bodyP1: play.mechanism,
        bodyP2: "Replace this package with Atul engine output when available.",
        cta: "Review package",
        sendTime: "Manual review",
        suppression: "Recent purchasers, unsubscribes",
      },
    ]);
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
    setPublishingCampaignId(campaignDraft.id);
    try {
      const result = await api.createSendPackage(campaignDraft);
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
      showToast({ message: "Created in Klaviyo" });
      return result;
    } catch (err) {
      showToast({
        message: "Couldn't create the Klaviyo package.",
        error: true,
        actionLabel: "Retry",
        onAction: () => { setToast(null); createCampaignTemplateInKlaviyo(campaignDraft); },
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
    const confirmed = window.confirm(`Send this campaign now in Klaviyo to ${campaignDraft.klaviyoAudience?.count || "the matched"} recipients?`);
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
      return result;
    } finally {
      setSendingCampaignId("");
    }
  }

  async function previewCampaignAudience(campaignDraft) {
    setPreviewingCampaignId(campaignDraft.id);
    try {
      const result = await runStep("Campaign audience preview", () => api.previewCampaignAudience(campaignDraft));
      setAudiencePreviewsByCampaign((prev) => ({ ...prev, [campaignDraft.id]: result.audience }));
      return result;
    } finally {
      setPreviewingCampaignId("");
    }
  }

  function chooseTemplate(playId, templateId) {
    setSelectedTemplateByPlay((prev) => ({ ...prev, [playId]: templateId }));
    setDraftEditsByPlay((prev) => ({ ...prev, [playId]: {} }));
  }

  // Explicit sign-off: move a reviewed campaign to "Ready to send".
  function approveForSend(playId) {
    setApprovedForSend((prev) => (prev.includes(playId) ? prev : [...prev, playId]));
    setWorkspaceStep("send");
  }

  // Send it back to review (edits or a mistaken approval).
  function unapproveForSend(playId) {
    setApprovedForSend((prev) => prev.filter((id) => id !== playId));
    setWorkspaceStep("copy");
  }

  function updateDraftField(playId, field, value) {
    setDraftEditsByPlay((prev) => ({
      ...prev,
      [playId]: {
        ...(prev[playId] || {}),
        [field]: value,
      },
    }));
  }

  // A3: reset a single field to the play's suggested template_prompt value.
  function restoreDraftField(playId, play, field) {
    const suggested = suggestedValueForField(play, field);
    updateDraftField(playId, field, suggested);
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
          <button key={key} className={`nav-item ${activePage === key ? "active" : ""}`} onClick={() => setActivePage(key)}>
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

        <section className="page">
          {toast ? (
            <div className={`toast ${toast.error ? "error" : ""}`} role="status" aria-live="polite">
              <span className="toast-check" aria-hidden="true">{toast.error ? "!" : "✓"}</span>
              <span className="toast-message">{toast.message}</span>
              {toast.actionLabel && toast.onAction ? (
                <button type="button" className="toast-action" onClick={toast.onAction}>{toast.actionLabel}</button>
              ) : null}
              <button type="button" className="toast-close" aria-label="Dismiss" onClick={() => setToast(null)}>×</button>
            </div>
          ) : null}
          {error ? <div className="error-box">{error}</div> : null}
          {loading && activePage === "briefing" ? <BriefingWorking /> : null}

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

          {activePage === "briefing" && !firstRunActive && !rehydrating && (
            <>
              {showSparseInterstitial ? (
                <div className="sparse-interstitial">
                  <p>Your store has {orderCount} orders. BeaconAI holds recommendations until the data can back them — here's what's tracking toward unlock.</p>
                  <button className="btn small" onClick={() => setSparseInterstitialDismissed(true)}>Dismiss</button>
                </div>
              ) : null}
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
              />
              {stateOfStore ? <div className="state-of-store">{stateOfStore}</div> : null}
              <div className="briefing-titlebar">
                <div>
                  <h2>{briefingHeading}</h2>
                  <p>
                    <strong>{recommendedRows.length}</strong> recommended now{experimentRows.length ? <> · <strong>{experimentRows.length}</strong> experiments</> : null} · <strong>{consideredRows.length}</strong> not ready yet.
                  </p>
                </div>
                <div className="briefing-refresh">
                  {briefingUpdatedAt ? (
                    <span className="briefing-updated" title={`Last updated ${briefingUpdatedAt.absolute}`}>
                      Updated {briefingUpdatedAt.relative}
                    </span>
                  ) : null}
                  <button className="btn" onClick={() => runAtulEngine(false)} disabled={loading}>Refresh briefing</button>
                </div>
              </div>
              <div className="briefing-workbench">
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
                      {!selectableRows.length ? <div className="empty-panel inline">Refresh your briefing to load recommendations.</div> : null}
                      {selectableRows.length && !recommendedRows.length ? <div className="empty-panel inline">Nothing is ready for campaign review yet. See Not ready yet below for what needs more data.</div> : null}
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
                    ) : (
                      <div className="empty-panel inline">Everything BeaconAI considered this run was strong enough to recommend.</div>
                    )}
                  </div>
                </div>

                <RecommendationDetail
                  play={selectedBriefingRow?.play}
                  onSendToReview={greenlightEnginePlay}
                  onViewEvidence={setSelectedEvidence}
                  onOpenInCampaigns={(play) => { setReviewPlayId(play.play_id || play.id); setActivePage("campaigns"); }}
                  approved={selectedBriefingRow ? approvedPlayIdSet.has(selectedBriefingRow.play.play_id || selectedBriefingRow.play.id) : false}
                  showAdvanced={showAdvanced}
                />
              </div>
            </>
          )}

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
                          className={`rail-row ${reviewPlay?.id === play.id ? "selected" : ""} ${flashCampaignId === play.id ? "flash" : ""}`}
                          onClick={() => setReviewPlayId(play.id)}
                        >
                          <span className={`rail-dot ${g}`} />
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
                      { key: "copy", label: "Copy", enabled: true },
                      { key: "audience", label: "Audience", enabled: hasTemplate },
                      { key: "send", label: "Send", enabled: isApproved },
                    ];
                    const preview = selectedCampaign ? (audiencePreviewsByCampaign[selectedCampaign.id] || selectedCampaign.klaviyoAudience || null) : null;
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
                                  <span className="step-marker">{state === "done" ? "✓" : i + 1}</span>
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
                              <div className="recipient-preview">
                                <div className="recipient-preview-head">
                                  <div>
                                    <span className="section-meta">Recipient preview</span>
                                    <strong>{preview ? `${preview.count} matched emails` : "Not loaded"}</strong>
                                  </div>
                                  <button className="btn" onClick={() => previewCampaignAudience(selectedCampaign)} disabled={previewingCampaignId === selectedCampaign.id}>
                                    {previewingCampaignId === selectedCampaign.id ? "Loading..." : "Show emails"}
                                  </button>
                                </div>
                                {preview?.recipients?.length ? (
                                  <div className="recipient-list">
                                    {preview.recipients.slice(0, 25).map((recipient) => (
                                      <div key={`${recipient.customerId || recipient.email}-${recipient.email}`} className="recipient-row">
                                        <strong>{recipient.email}</strong>
                                        <span>{recipient.orderCount} orders · ${recipient.totalRevenue}</span>
                                      </div>
                                    ))}
                                    {preview.recipients.length > 25 ? <small>Showing first 25 of {preview.recipients.length} recipients.</small> : null}
                                  </div>
                                ) : preview ? (
                                  <div className="empty-panel inline">No subscribed recipient emails matched this campaign yet.</div>
                                ) : null}
                              </div>
                            </div>
                          ) : null}

                          {workspaceStep === "send" && selectedCampaign ? (
                            <CampaignSendPanel campaign={selectedCampaign} onEditStep={setWorkspaceStep} />
                          ) : null}
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

                          {workspaceStep === "send" ? (
                            isSent ? (
                              <span className="send-done">✓ Sent</span>
                            ) : !status.klaviyo ? (
                              // P-D2: never a dead/erroring send button when Klaviyo is unconnected.
                              <button className="btn primary" onClick={() => startOAuth("klaviyo")}>Connect Klaviyo to send</button>
                            ) : selectedCampaign?.klaviyoCampaignId ? (
                              <button className="btn danger" onClick={() => sendKlaviyoCampaign(selectedCampaign)} disabled={sendingCampaignId === selectedCampaign.id || Boolean(selectedCampaign.klaviyoSendJobId)}>
                                {selectedCampaign.klaviyoSendJobId ? "Campaign sent" : sendingCampaignId === selectedCampaign.id ? "Sending…" : "Send campaign now"}
                              </button>
                            ) : (
                              <button className="btn primary" onClick={() => createCampaignTemplateInKlaviyo(selectedCampaign)} disabled={publishing || created}>
                                {created ? "Send package ready" : publishing ? "Creating…" : "Create Klaviyo send package"}
                              </button>
                            )
                          ) : null}
                        </div>

                        {/* P-B4: truthful what-happens-next (verified: create = draft only, no send) */}
                        {workspaceStep === "send" && !isSent && status.klaviyo && !selectedCampaign?.klaviyoCampaignId ? (
                          <p className="whats-next">This creates the template and campaign in your Klaviyo account — nothing sends until you approve it there.</p>
                        ) : null}
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
            <ResultsPage campaigns={finalCampaigns} />
          )}

          {activePage === "ledger" && (
            <>
              <div className="hero-card compact">
                <div className="eyebrow">Engine handoff</div>
                <h2>Normalized data Atul’s Python engine can consume.</h2>
                <p>Tables: shop, orders, order_line_items, customers, products, product_variants, refunds.</p>
                <button className="btn primary" onClick={loadEngineInput}>Refresh engine input</button>
              </div>
              <JsonBlock title="Engine input JSON" value={engineInput || "Click Refresh engine input"} />
            </>
          )}

          {activePage === "intelligence" && (
            <>
              <div className="hero-card compact">
                <div className="eyebrow">Statistical intelligence</div>
                <h2>Placeholder model cards and audience views.</h2>
                <p>These panels mirror the richer `beaconai-frontend-app` direction while waiting for the real engine output.</p>
                <button className="btn primary" onClick={loadPlaceholderEngineRun}>Load live placeholder counts</button>
              </div>
              <div className="model-grid">
                {Object.entries(dashboardRun.predictive_models || {}).map(([key, model]) => <ModelCardPanel key={key} model={model} />)}
              </div>
              <div className="placeholder-grid">
                <div>
                  <div className="section-kicker">RFM-style segments</div>
                  <SegmentBars segments={dashboardRun.audience_segments || []} />
                </div>
                <div>
                  <div className="section-kicker">Cohort retention</div>
                  <CohortRetentionChart curves={dashboardRun.cohort_retention?.curves || []} />
                </div>
              </div>
            </>
          )}

          {activePage === "considered" && (
            <>
              <div className="hero-card compact">
                <div className="eyebrow">Considered and held</div>
                <h2>Plays BeaconAI would hold until stronger evidence exists.</h2>
                <p>Reason codes explain why a recommendation is not ready for campaign review yet.</p>
              </div>
              {(dashboardRun.slate?.considered || []).map((play) => <EnginePlayCard key={play.play_id} play={play} onViewEvidence={setSelectedEvidence} />)}
              {dashboardRun.month_2_delta ? <MonthTwoDeltaPanel delta={dashboardRun.month_2_delta} /> : <div className="empty-panel">No month-over-month comparison yet.</div>}
            </>
          )}

          {activePage === "placeholder" && (
            <>
              <div className="hero-card compact">
                <div className="eyebrow">Engine placeholder</div>
                <h2>Temporary richer engine run until Atul’s engine is wired in.</h2>
                <p>
                  This mirrors the direction of the polished `beaconai-frontend-app` dashboard: slate, evidence,
                  model cards, audience segments, and a stable handoff contract.
                </p>
                <button className="btn primary" onClick={loadPlaceholderEngineRun}>Refresh placeholder</button>
              </div>

              {placeholderRun ? (
                <>
                  <div className="stats-grid">
                    <StatCard label="Products" value={placeholderRun.input_summary?.products ?? "—"} detail="input summary" />
                    <StatCard label="Customers" value={placeholderRun.input_summary?.customers ?? "—"} detail="input summary" />
                    <StatCard label="Orders" value={placeholderRun.input_summary?.orders ?? "—"} detail="input summary" />
                    <StatCard label="Contract" value={placeholderRun.contract_version || "—"} detail="engine run shape" />
                  </div>

                  <div className="placeholder-grid">
                    <div>
                      <div className="section-kicker">Recommendations</div>
                      {[
                        ...(placeholderRun.slate?.recommended_now || []),
                        ...(placeholderRun.slate?.recommended_experiment || []),
                      ].map((play) => <PlaceholderPlay key={play.play_id} play={play} />)}
                    </div>
                  </div>

                  <div className="placeholder-grid">
                    <div className="placeholder-panel">
                      <div className="section-kicker">Model placeholders</div>
                      {Object.entries(placeholderRun.predictive_models || {}).map(([key, model]) => (
                        <div className="model-row" key={key}>
                          <span>{model.display_name}</span>
                          <strong>{model.fit_status}</strong>
                        </div>
                      ))}
                    </div>
                    <div className="placeholder-panel">
                      <div className="section-kicker">Audience segments</div>
                      {(placeholderRun.audience_segments || []).map((segment) => (
                        <div className="model-row" key={segment.label}>
                          <span>{segment.label}</span>
                          <strong>{segment.n}</strong>
                        </div>
                      ))}
                    </div>
                  </div>

                  <JsonBlock title="Placeholder engine_run JSON" value={placeholderRun} />
                </>
              ) : (
                <div className="empty-panel">Click Refresh placeholder to load the temporary engine contract.</div>
              )}
            </>
          )}

          {activePage === "setup" && (
            <>
              <div className="hero-card compact">
                <div className="eyebrow">Account settings</div>
                <h2>Manage connected accounts.</h2>
                <p>
                  Use this page after onboarding to refresh or reconnect Shopify and Klaviyo.
                </p>
              </div>

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
                  <h3>1. Shopify</h3>
                  <p>{status.shopify ? `Connected via ${status.shopifySource}. Production users connect once with Shopify OAuth, then BeaconAI refreshes data automatically.` : "Connect Shopify with OAuth to load products, customers, orders, and order line items."}</p>
                  <div className="action-row">
                    <button className="btn primary" onClick={status.shopify ? syncShopify : () => startOAuth("shopify")} disabled={status.shopify && loading}>{status.shopify ? (loading ? "Syncing…" : "Refresh Shopify now") : "Connect Shopify"}</button>
                    <button className="btn" onClick={checkConnections}>Test connection</button>
                  </div>
                </div>
                <div className="integration-card">
                  <h3>2. Klaviyo</h3>
                  <p>{status.klaviyo ? `Connected via ${status.klaviyoSource}. Production users connect once with Klaviyo OAuth, then templates can refresh in the background.` : "Connect Klaviyo with OAuth to fetch existing templates and prepare BeaconAI template suggestions."}</p>
                  <div className="action-row">
                    <button className="btn primary" onClick={status.klaviyo ? loadKlaviyoTemplates : () => startOAuth("klaviyo")}>{status.klaviyo ? "Refresh templates" : "Connect Klaviyo"}</button>
                    <button className="btn" onClick={checkConnections}>Test connection</button>
                  </div>
                </div>
              </div>
            </>
          )}

          {selectedEvidence ? (
            <div className="drawer-backdrop" onClick={() => setSelectedEvidence(null)}>
              <div className="evidence-drawer" onClick={(event) => event.stopPropagation()}>
                <button className="drawer-close" onClick={() => setSelectedEvidence(null)}>Close</button>
                <div className="section-kicker">Evidence drawer</div>
                <h2>{selectedEvidence.play_name || selectedEvidence.play_id}</h2>
                <p>{selectedEvidence.mechanism}</p>
                <JsonBlock title="Play JSON" value={selectedEvidence} />
              </div>
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
