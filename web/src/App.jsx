import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api";
import { baseEngineRun } from "./engineMock";
import "./styles.css";

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

function StatusPill({ label, ok }) {
  return (
    <span className={`status-pill ${ok ? "ok" : "pending"}`}>
      <span className="dot" /> {label}: {ok ? "Connected" : "Pending"}
    </span>
  );
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
    id: `${play.id}::${template.id}`,
    playTitle: play.play_name || play.play_id,
    templateName: template.name,
    templateSource: template.source,
    status: "ready",
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
  return { ...draft, ...edits, id: draft.id, playTitle: draft.playTitle, templateName: draft.templateName, templateSource: draft.templateSource };
}

function formatAudience(value) {
  return value?.toLocaleString?.() || "—";
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

function RecommendationRow({ play, selected, onSelect }) {
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
          {selectedActionable ? <span>✓ Approved</span> : null}
        </span>
        {evidenceLine ? <span className="recommendation-evidence-line">{evidenceLine}</span> : null}
      </span>
      <span className="recommendation-chevron">›</span>
    </button>
  );
}

function RecommendationDetail({ play, onSendToReview, onViewEvidence, showAdvanced = false }) {
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
          <p className="approve-note">Approving moves this to your campaign pipeline. Nothing is sent to customers until you approve the final email.</p>
          <p className="approve-note measurement">We'll track what these customers do for 30 days after send and report it in Results.</p>
          <div className="recommendation-detail-footer">
            <button className="btn primary" onClick={() => onSendToReview(play)}>Approve & pick template</button>
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

function CampaignPackages({ campaigns, onCreateInKlaviyo, onSendCampaign, publishingId, sendingId, audiencePreviews, onPreviewAudience, previewingId }) {
  const [selectedId, setSelectedId] = useState(campaigns[0]?.id || "");
  const selected = campaigns.find((item) => item.id === selectedId) || campaigns[0];
  const preview = audiencePreviews[selected?.id] || selected?.klaviyoAudience || null;

  if (!selected) {
    return <div className="empty-panel">No campaign packages are ready yet.</div>;
  }

  return (
    <div className="campaign-layout">
      <div className="campaign-list">
        {campaigns.map((item) => (
          <button key={item.id} className={`campaign-item ${selected?.id === item.id ? "selected" : ""}`} onClick={() => setSelectedId(item.id)}>
            <span className={`campaign-status ${item.status}`}>{item.status}</span>
            <strong>{item.playTitle}</strong>
            <small>{item.customers} customers</small>
          </button>
        ))}
      </div>
      <div className="campaign-detail-panel">
        <div className="pkg-origin">
          <span>From play</span>
          <strong>{selected.playTitle}</strong>
        </div>
        {selected.templateName ? (
          <div className="pkg-origin">
            <span>Template</span>
            <strong>{selected.templateName} · {selected.templateSource}</strong>
          </div>
        ) : null}
        <div className="email-preview">
          <div className="email-topline">
            <span>Subject</span>
            <strong>{selected.subject}</strong>
          </div>
          <div className="email-body">
            <h1>{selected.bodyH2}</h1>
            <p>{selected.bodyP1}</p>
            <p>{selected.bodyP2}</p>
            <p><strong>{selected.cta}</strong></p>
          </div>
        </div>
        <div className="segment-spec">
          <div><span>Audience</span><strong>{selected.segment}</strong></div>
          <div><span>Send</span><strong>{selected.sendTime}</strong></div>
          <div><span>Suppression</span><strong>{selected.suppression}</strong></div>
        </div>
        <div className="recipient-preview">
          <div className="recipient-preview-head">
            <div>
              <span className="section-meta">Recipient preview</span>
              <strong>{preview ? `${preview.count} matched emails` : "Not loaded"}</strong>
            </div>
            <button className="btn" onClick={() => onPreviewAudience(selected)} disabled={previewingId === selected.id}>
              {previewingId === selected.id ? "Loading..." : "Show emails"}
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
        {selected.klaviyoTemplateId ? (
          <div className="success-box">
            Created Klaviyo campaign <strong>{selected.klaviyoCampaignId || selected.klaviyoTemplateId}</strong>
            {selected.klaviyoAudience ? ` for ${selected.klaviyoAudience.count} run-matched recipients.` : "."}
            {selected.klaviyoListId ? ` Audience list: ${selected.klaviyoListId}.` : ""}
            {selected.klaviyoSendJobId ? ` Send job: ${selected.klaviyoSendJobId}.` : ""}
          </div>
        ) : null}
        <div className="action-row">
          <button className="btn primary" onClick={() => onCreateInKlaviyo(selected)} disabled={publishingId === selected.id || Boolean(selected.klaviyoTemplateId)}>
            {selected.klaviyoTemplateId ? "Send package ready" : publishingId === selected.id ? "Creating..." : "Create Klaviyo send package"}
          </button>
          {selected.klaviyoCampaignId ? (
            <button className="btn danger" onClick={() => onSendCampaign(selected)} disabled={sendingId === selected.id || Boolean(selected.klaviyoSendJobId)}>
              {selected.klaviyoSendJobId ? "Campaign sent" : sendingId === selected.id ? "Sending..." : "Send campaign now"}
            </button>
          ) : null}
          <button className="btn">Request changes</button>
        </div>
      </div>
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

function OnboardingBanner({ status, hasStoreSnapshot, approvedCount, readyToFinish, onConnectShopify, onSyncShopify, onConnectKlaviyo, onLoadTemplates, onFinish }) {
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
        <button className="btn primary" onClick={nextAction.onClick}>{nextAction.label}</button>
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
        Results appear here after your first campaign goes out. For each campaign, BeaconAI tracks the customers it targeted and reports what they did over the following 30 days.
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
  const [templateSource, setTemplateSource] = useState("");
  const [selectedTemplateByPlay, setSelectedTemplateByPlay] = useState({});
  const [draftEditsByPlay, setDraftEditsByPlay] = useState({});
  const [authorizedPackageIds, setAuthorizedPackageIds] = useState([]);
  const [klaviyoAssetsByCampaign, setKlaviyoAssetsByCampaign] = useState({});
  const [publishingCampaignId, setPublishingCampaignId] = useState("");
  const [sendingCampaignId, setSendingCampaignId] = useState("");
  const [audiencePreviewsByCampaign, setAudiencePreviewsByCampaign] = useState({});
  const [previewingCampaignId, setPreviewingCampaignId] = useState("");
  const [reviewPlayId, setReviewPlayId] = useState("");
  const [selectedBriefingPlayId, setSelectedBriefingPlayId] = useState("");
  const [onboardingHidden, setOnboardingHidden] = useState(() => localStorage.getItem("beaconai:onboarding-complete") === "true");
  const [campaignPackages, setCampaignPackages] = useState([]);
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [flashCampaignId, setFlashCampaignId] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const counts = sync?.synced || {};
  const dashboardRun = useMemo(() => buildDashboardRun(placeholderRun, counts), [placeholderRun, counts]);
  const workflowPlays = useMemo(
    () => buildWorkflowPlays({ atulEngineResult, campaignPackages, campaign }),
    [atulEngineResult, campaignPackages, campaign]
  );
  const reviewablePlays = useMemo(() => workflowPlays.filter((play) => classifyPlayLane(play) !== "considered"), [workflowPlays]);
  const reviewPlay = reviewablePlays.find((play) => play.id === reviewPlayId) || reviewablePlays[0];
  const selectedTemplate = reviewPlay ? klaviyoTemplates.find((item) => item.id === selectedTemplateByPlay[reviewPlay.id]) : null;
  const selectedDraft = reviewPlay && selectedTemplate ? buildCampaignFromSelection(reviewPlay, selectedTemplate, draftEditsByPlay[reviewPlay.id]) : null;
  const finalCampaigns = reviewablePlays
    .map((play) => buildCampaignFromSelection(play, klaviyoTemplates.find((item) => item.id === selectedTemplateByPlay[play.id]), draftEditsByPlay[play.id]))
    .map((item) => {
      if (!item) return item;
      const asset = klaviyoAssetsByCampaign[item.id];
      return {
        ...item,
        status: asset ? "created" : authorizedPackageIds.includes(item.id) ? "authorized" : item.status,
        klaviyoTemplateId: asset?.templateId || null,
        klaviyoListId: asset?.listId || null,
        klaviyoCampaignId: asset?.campaignId || null,
        klaviyoSendJobId: asset?.sendJobId || null,
        klaviyoAudience: asset?.audience || null,
      };
    })
    .filter(Boolean);
  const reviewPendingCount = reviewablePlays.filter((play) => !selectedTemplateByPlay[play.id]).length;
  const campaignsPendingCount = finalCampaigns.filter((item) => item.status !== "created").length;
  const approvedCount = finalCampaigns.filter((item) => item.status === "created").length;
  const sentCampaigns = finalCampaigns.filter((item) => item.status === "created" || item.klaviyoSendJobId);
  const readyToSendCampaigns = finalCampaigns.filter((item) => !(item.status === "created" || item.klaviyoSendJobId));
  const productCount = counts.products ?? engineInput?.products?.length ?? placeholderRun?.input_summary?.products ?? "—";
  const customerCount = counts.customers ?? engineInput?.customers?.length ?? placeholderRun?.input_summary?.customers ?? "—";
  const orderCount = counts.orders ?? engineInput?.orders?.length ?? placeholderRun?.input_summary?.orders ?? "—";
  const hasStoreSnapshot = productCount !== "—" && customerCount !== "—" && orderCount !== "—";
  const onboardingReadyToFinish = status.shopify && status.klaviyo;
  const briefingRows = workflowPlays.map((play) => ({ play, lane: classifyPlayLane(play) }));
  const recommendedRows = briefingRows.filter((row) => row.lane === "recommended");
  const experimentRows = briefingRows.filter((row) => row.lane === "experiment");
  const consideredRows = briefingRows.filter((row) => row.lane === "considered");
  const selectableRows = [...recommendedRows, ...experimentRows, ...consideredRows];
  const selectedBriefingRow = selectableRows.find((row) => row.play.play_id === selectedBriefingPlayId) || selectableRows[0] || null;
  const readyRowsCount = recommendedRows.length + experimentRows.length;
  const stateOfStore = atulEngineResult?.presentedRun?.state_of_store || null;
  const briefingHeading = !workflowPlays.length
    ? "Run your briefing to see recommendations"
    : readyRowsCount
      ? `Your briefing is ready — ${readyRowsCount} plays for your review`
      : `No campaign-ready plays yet — ${consideredRows.length} need more data`;

  useEffect(() => {
    checkConnections();
    preloadStoreSnapshot();
    loadBrandContext();
  }, []);

  useEffect(() => {
    if (reviewPlayId && !reviewablePlays.some((play) => play.id === reviewPlayId)) {
      setReviewPlayId("");
      return;
    }
    if (!reviewPlayId && reviewablePlays[0]) {
      setReviewPlayId(reviewablePlays[0].id);
    }
  }, [reviewPlayId, reviewablePlays]);

  useEffect(() => {
    if (!selectableRows.length) return;
    const stillPresent = selectableRows.some((row) => row.play.play_id === selectedBriefingPlayId);
    if (!stillPresent) setSelectedBriefingPlayId(selectableRows[0].play.play_id);
  }, [selectableRows, selectedBriefingPlayId]);

  useEffect(() => {
    if (onboardingReadyToFinish && !onboardingHidden) {
      localStorage.setItem("beaconai:onboarding-complete", "true");
      setOnboardingHidden(true);
    }
  }, [onboardingHidden, onboardingReadyToFinish]);

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
    const result = await runStep("Shopify sync", () => api.syncShopify());
    setSync(result);
    await preloadStoreSnapshot();
    return result;
  }

  async function runAnalysis() {
    const result = await runStep("Engine run", () => api.runEngine());
    setCampaign(result.campaign);
    setActivePage("campaigns");
    return result;
  }

  async function runAtulEngine(useFixture = false) {
    const result = await runStep(useFixture ? "Sample briefing refresh" : "Briefing refresh", () => api.runAtulEngine(useFixture));
    setAtulEngineResult(result);
    setActivePage("briefing");
    return result;
  }

  async function loadKlaviyoTemplates() {
    const result = await runStep("Klaviyo templates load", () => api.getKlaviyoTemplates());
    setKlaviyoTemplates(result.templates || []);
    setTemplateSource(result.source || "");
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

  function greenlightEnginePlay(play) {
    const playId = play.play_id || play.id;
    setCampaignPackages((prev) => {
      if (prev.some((item) => item.id === playId)) return prev;
      return [
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
      ];
    });
    setReviewPlayId(playId);
    setActivePage("campaigns");
    setFlashCampaignId(playId);
    setTimeout(() => setFlashCampaignId((current) => (current === playId ? "" : current)), 2200);
  }

  function authorizeCampaignPackage(campaignId) {
    setCampaignPackages((prev) => prev.map((item) => item.id === campaignId ? { ...item, status: "authorized" } : item));
    setAuthorizedPackageIds((prev) => prev.includes(campaignId) ? prev : [...prev, campaignId]);
  }

  async function createCampaignTemplateInKlaviyo(campaignDraft) {
    setPublishingCampaignId(campaignDraft.id);
    try {
      const result = await runStep("Klaviyo send package creation", () => api.createSendPackage(campaignDraft));
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
      return result;
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

  function updateDraftField(playId, field, value) {
    setDraftEditsByPlay((prev) => ({
      ...prev,
      [playId]: {
        ...(prev[playId] || {}),
        [field]: value,
      },
    }));
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

  const campaignsBadgeCount = reviewPendingCount + campaignsPendingCount;

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
            <StatusPill label="API" ok={status.api} />
            <StatusPill label="Shopify" ok={status.shopify} />
            <StatusPill label="Klaviyo" ok={status.klaviyo} />
          </div>
        </header>

        <section className="page">
          {error ? <div className="error-box">{error}</div> : null}
          {loading ? <div className="loading-box">Working...</div> : null}

          {activePage === "briefing" && (
            <>
              {!onboardingHidden ? (
                <OnboardingBanner
                  status={status}
                  hasStoreSnapshot={hasStoreSnapshot}
                  approvedCount={approvedCount}
                  readyToFinish={onboardingReadyToFinish}
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
                campaignsPending={campaignsPendingCount}
              />
              {stateOfStore ? <div className="state-of-store">{stateOfStore}</div> : null}
              <div className="briefing-titlebar">
                <div>
                  <h2>{briefingHeading}</h2>
                  <p>
                    <strong>{recommendedRows.length}</strong> recommended now{experimentRows.length ? <> · <strong>{experimentRows.length}</strong> experiments</> : null} · <strong>{consideredRows.length}</strong> not ready yet.
                  </p>
                </div>
                <button className="btn" onClick={() => runAtulEngine(false)} disabled={loading}>Refresh briefing</button>
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
                    ) : null}
                  </div>
                </div>

                <RecommendationDetail
                  play={selectedBriefingRow?.play}
                  onSendToReview={greenlightEnginePlay}
                  onViewEvidence={setSelectedEvidence}
                  showAdvanced={showAdvanced}
                />
              </div>
            </>
          )}

          {activePage === "campaigns" && (
            <>
              <div className="campaign-section">
                <div className="section-header">
                  <span className="section-title">Needs review</span>
                  <span className="section-meta">{reviewPendingCount} awaiting a template</span>
                </div>
              <div className="queue-layout">
                <div className="draft-list">
                  <div className="section-kicker">Recommendations</div>
                  {reviewablePlays.length ? reviewablePlays.map((play) => {
                    const chosen = klaviyoTemplates.find((item) => item.id === selectedTemplateByPlay[play.id]);
                    return (
                      <button key={play.id} className={`draft-card ${reviewPlay?.id === play.id ? "selected" : ""} ${flashCampaignId === play.id ? "flash" : ""}`} onClick={() => setReviewPlayId(play.id)}>
                        <div className="draft-state"><span className="dot" /> {chosen ? "Template selected" : "Needs template"}</div>
                        <h3>{play.play_name || play.play_id}</h3>
                        <p>{play.audience_archetype || "Recommended audience"}</p>
                      </button>
                    );
                  }) : <div className="empty-panel">Approve a play in Briefing before reviewing templates.</div>}
                </div>

                <div className="draft-detail">
                  <div className="template-detail-head">
                    <div>
                      <div className="section-kicker">Selected play</div>
                      <h3>{reviewPlay?.play_name || "No play selected"}</h3>
                      <p>{reviewPlay?.mechanism || "Choose a play to see template options."}</p>
                    </div>
                    <button className="btn" onClick={loadKlaviyoTemplates}>Refresh templates</button>
                  </div>

                  {templateSource ? <div className="success-box">Templates loaded from {templateSource}.</div> : null}

                  {brandContext ? (
                    <div className="brand-context-box">
                      <div>
                        <span className="section-kicker">Brand voice from Shopify</span>
                        <h4>{brandContext.brandName} · {brandContext.category}</h4>
                        <p>
                          Using {brandContext.productLanguage?.bestSellers?.[0]?.title || "top products"},
                          {brandContext.productLanguage?.productTypes?.[0]?.name ? ` ${brandContext.productLanguage.productTypes[0].name},` : ""}
                          {" "}and store words like {(brandContext.messaging?.useWords || []).slice(0, 5).join(", ") || "catalog language"}.
                        </p>
                      </div>
                      <button className="btn small" onClick={loadBrandContext}>Refresh</button>
                    </div>
                  ) : null}

                  <div className="template-grid">
                    {klaviyoTemplates.length ? klaviyoTemplates.map((item) => (
                      <button
                        key={item.id}
                        className={`template-option ${selectedTemplate?.id === item.id ? "selected" : ""}`}
                        onClick={() => reviewPlay && chooseTemplate(reviewPlay.id, item.id)}
                        disabled={!reviewPlay}
                      >
                        <span>{item.source === "klaviyo" ? "Klaviyo" : "BeaconAI"}</span>
                        <strong>{item.name}</strong>
                        <small>{item.previewText}</small>
                      </button>
                    )) : <div className="empty-panel">Fetch templates to show existing Klaviyo templates and BeaconAI suggestions.</div>}
                  </div>

                  {reviewPlay && selectedTemplate ? (
                    <>
                      <div className="section-header">
                        <span className="section-title">Edit campaign draft</span>
                        <span className="section-meta">template selected</span>
                      </div>
                      <EditableCampaignDraft
                        draft={selectedDraft}
                        onChange={(field, value) => updateDraftField(reviewPlay.id, field, value)}
                        onSendToCampaigns={() => setActivePage("campaigns")}
                      />
                    </>
                  ) : null}
                </div>
              </div>
              </div>

              <div className="campaign-section">
                <div className="section-header">
                  <span className="section-title">Ready to send</span>
                  <span className="section-meta">{readyToSendCampaigns.length} in the pipeline</span>
                </div>
                {readyToSendCampaigns.length ? (
                  <CampaignPackages
                    campaigns={readyToSendCampaigns}
                    onCreateInKlaviyo={createCampaignTemplateInKlaviyo}
                    onSendCampaign={sendKlaviyoCampaign}
                    publishingId={publishingCampaignId}
                    sendingId={sendingCampaignId}
                    audiencePreviews={audiencePreviewsByCampaign}
                    onPreviewAudience={previewCampaignAudience}
                    previewingId={previewingCampaignId}
                  />
                ) : (
                  <div className="empty-panel">Pick a template above to assemble a campaign package.</div>
                )}
              </div>

              <div className="campaign-section">
                <div className="section-header">
                  <span className="section-title">Sent</span>
                  <span className="section-meta">{sentCampaigns.length} sent</span>
                </div>
                {sentCampaigns.length ? (
                  <div className="campaign-list">
                    {sentCampaigns.map((item) => (
                      <div key={item.id} className="campaign-item">
                        <span className="campaign-status created">Sent</span>
                        <strong>{item.playTitle}</strong>
                        <small>{formatAudience(item.customers)} customers</small>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-panel">Campaigns you send will appear here.</div>
                )}
              </div>
            </>
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
                    <button className="btn primary" onClick={status.shopify ? syncShopify : () => startOAuth("shopify")}>{status.shopify ? "Refresh Shopify now" : "Connect Shopify"}</button>
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
