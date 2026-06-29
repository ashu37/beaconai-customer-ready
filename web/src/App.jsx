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
    role,
    lane: play.lane || role,
    reason_code: play.reason_code || play.null_reason || null,
    mechanism: narration.play_thesis || play.recommendation_text || play.mechanism || play.rationale || play.why || "Engine recommendation ready for merchant review.",
    audience_archetype: play.audience_archetype || play.audience?.definition || play.audience?.description || play.audience || "Engine audience",
    audience_size: audienceSize,
    confidence: play.confidence_label || play.confidence || play.model_confidence || "engine",
    evidence: play.evidence || { evidence_source: play.evidence_source || null, evidence_class: play.evidence_class || null },
    evidence_source: play.evidence_source || play.evidence?.evidence_source || null,
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
    segment: play.audience_archetype || "Engine audience",
    subject: template.subject || prompt.subject || `${play.play_name} campaign`,
    previewText: template.previewText || prompt.previewText || narration.evidence_summary || "Selected template ready for campaign review.",
    bodyH2: template.bodyH2 || prompt.headline || play.play_name || "BeaconAI campaign",
    bodyP1: template.bodyP1 || prompt.body || play.mechanism,
    bodyP2: prompt.support || narration.what_we_d_send || play.mechanism,
    cta: template.cta || prompt.cta || "Shop now",
    sendTime: "Manual review",
    suppression: "Recent purchasers, unsubscribes, suppressed profiles",
  };
  return { ...draft, ...edits, id: draft.id, playTitle: draft.playTitle, templateName: draft.templateName, templateSource: draft.templateSource };
}

function formatAudience(value) {
  return value?.toLocaleString?.() || "—";
}

function formatRevenueRange(play) {
  if (!play?.revenue_range) return "Not sized";
  const { low, high, currency } = play.revenue_range;
  if (low == null || high == null) return "Not sized";
  const prefix = currency === "USD" || !currency ? "$" : `${currency} `;
  return `${prefix}${low?.toLocaleString?.() || low}-${prefix}${high?.toLocaleString?.() || high}`;
}

function revenueRangeParts(play) {
  const range = play?.revenue_range;
  if (!range || range.low == null || range.high == null) return null;
  const prefix = range.currency === "USD" || !range.currency ? "$" : `${range.currency} `;
  const low = Number(range.low) || 0;
  const high = Number(range.high) || 0;
  const median = range.median ?? Math.round((low + high) / 2);
  return {
    low,
    high,
    median,
    labelLow: `${prefix}${low.toLocaleString()}`,
    labelHigh: `${prefix}${high.toLocaleString()}`,
    labelMedian: `${prefix}${Number(median).toLocaleString()}`,
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

function RecommendationRow({ play, selected, onSelect }) {
  const confidence = play.confidence || play.confidence_label || play.model_confidence || null;
  const evidenceSource = play.evidence_source || play.evidence?.evidence_source || null;
  const confidenceLabel = readableMetaLabel(confidence);
  const evidenceLabel = readableMetaLabel(evidenceSource);
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
            <span className="recommendation-meta-item">
              <span className={`confidence-dot ${confidenceTone(confidence)}`} />
              {confidenceLabel}
            </span>
          ) : null}
          {evidenceLabel && evidenceLabel !== confidenceLabel ? <span>{evidenceLabel}</span> : null}
          {selectedActionable ? <span>✓ Approved</span> : null}
        </span>
      </span>
      <span className="recommendation-chevron">›</span>
    </button>
  );
}

function RecommendationDetail({ play, onSendToReview, onViewEvidence }) {
  const [activeTab, setActiveTab] = useState("thesis");

  if (!play) {
    return <div className="recommendation-detail empty-panel">Select a recommendation to review the details.</div>;
  }

  const confidence = play.confidence || play.confidence_label || play.model_confidence || "Review";
  const narration = play.narration || {};
  const lane = classifyPlayLane(play);
  const revenue = revenueRangeParts(play);
  const tabLabels = [
    ["thesis", "Play thesis"],
    ["send", "What we'd send"],
    ["evidence", "Evidence"],
    ["audience", "Audience"],
    ["sensitivity", "Sensitivity"],
  ];

  return (
    <div className="recommendation-detail">
      <div className="recommendation-detail-head">
        <span className={`recommendation-icon large ${lane}`}>{lane === "experiment" ? "✦" : lane === "considered" ? "□" : "▷"}</span>
        <div>
          <div className="section-kicker">{lane === "experiment" ? "Recommended experiment" : lane === "considered" ? "Considered and held" : "Primary recommendation"}</div>
          <h2>{play.play_name || play.play_id}</h2>
          <span className="detail-id-chip">{play.play_id || play.id}</span>
        </div>
        <button className="icon-menu" type="button" aria-label="More actions">...</button>
      </div>

      <div className="recommendation-stat-strip">
        <div>
          <strong>{formatAudience(play.audience_size)}</strong>
          <span>Customers</span>
        </div>
        <div>
          <strong>{formatRevenueRange(play)}</strong>
          <span>Est. revenue range</span>
        </div>
        <div>
          <strong>{statusLabel(confidence)}</strong>
          <span>Confidence</span>
        </div>
      </div>

      <div className="recommendation-banner">{narration.play_thesis || play.mechanism || "BeaconAI has prepared this recommendation for review."}</div>

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
                <div className="section-kicker">Est. revenue range</div>
                <div className="range-track">
                  <span className="range-fill" />
                  <span className="range-marker" style={{ left: "88%" }} />
                </div>
                <div className="range-labels">
                  <span>{revenue.labelLow}</span>
                  <span>median {revenue.labelMedian}</span>
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
              <strong>Choose in Review Queue</strong>
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
              <strong>{play.reason_code ? "Held by engine guardrail" : "Merchant approval required before template work"}</strong>
            </div>
          </>
        ) : null}
      </div>

      <div className="recommendation-detail-footer">
        {lane === "considered" ? (
          <button className="btn" onClick={() => onViewEvidence?.(play)}>Held by engine</button>
        ) : (
          <button className="btn primary" onClick={() => onSendToReview(play)}>✓ Approve</button>
        )}
        <button className="btn danger" onClick={() => onViewEvidence?.(play)}>Reject</button>
        <button className="btn" onClick={() => onViewEvidence?.(play)}>Defer</button>
      </div>
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

function App() {
  const [activePage, setActivePage] = useState("home");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
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
      if (activePage === "onboarding") setActivePage("home");
    }
  }, [activePage, onboardingHidden, onboardingReadyToFinish]);

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
    setActivePage("queue");
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
    setActivePage("queue");
  }

  async function loadEngineInput() {
    const result = await runStep("Engine input load", () => api.getEngineInput());
    setEngineInput(result.input);
    setActivePage("ledger");
  }

  async function loadPlaceholderEngineRun() {
    const result = await runStep("Placeholder engine load", () => api.getPlaceholderEngineRun());
    setPlaceholderRun(result.engineRun);
    setActivePage("placeholder");
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
          segment: play.audience_archetype || "Engine placeholder audience",
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
    setActivePage("queue");
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
    window.location.href = api.oauthStartUrl(provider);
  }

  function finishOnboarding() {
    localStorage.setItem("beaconai:onboarding-complete", "true");
    setOnboardingHidden(true);
    setActivePage("home");
  }

  const nav = [
    ["home", "Home"],
    ...(!onboardingHidden ? [["onboarding", "Onboarding"]] : []),
    ["briefing", "Briefing"],
    ["queue", "Review Queue"],
    ["campaigns", "Campaigns"],
    ["setup", "Connections"],
  ];

  const titleByPage = {
    home: "Home",
    onboarding: "Onboarding",
    briefing: "Monthly Briefing",
    queue: "Review Queue",
    campaigns: "Campaigns",
    setup: "Connections",
  };

  useEffect(() => {
    if (activePage === "onboarding" && onboardingHidden) {
      setActivePage("home");
    }
  }, [activePage, onboardingHidden]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="wordmark" aria-label="beacon">beac<span className="wordmark-dot" />n</div>
        <div className="store-name">{api.shopDomain}</div>
        {nav.map(([key, label]) => (
          <button key={key} className={`nav-item ${activePage === key ? "active" : ""}`} onClick={() => setActivePage(key)}>
            {label}
            {key === "queue" && reviewPendingCount ? <span className="badge">{reviewPendingCount}</span> : null}
            {key === "campaigns" && finalCampaigns.length ? <span className="badge">{finalCampaigns.length}</span> : null}
          </button>
        ))}
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{titleByPage[activePage]}</h1>
            <p>BeaconAI operator dashboard</p>
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

          {activePage === "home" && (
            <>
              <div className="home-hero">
                <div>
                  <div className="eyebrow">Command home</div>
                  <h2>BeaconAI campaign operations at a glance.</h2>
                  <p>
                    Connect accounts, watch synced store volume, and move recommendations from review to approved campaigns.
                  </p>
                </div>
                <div className="home-hero-actions">
                  <button className="btn primary" onClick={syncShopify}>Sync Shopify</button>
                  {!onboardingHidden ? <button className="btn" onClick={() => setActivePage("onboarding")}>Continue onboarding</button> : null}
                  <button className="btn" onClick={() => setActivePage("briefing")}>Open Briefing</button>
                  <button className="btn" onClick={() => setActivePage("queue")}>Review Queue</button>
                </div>
              </div>

              <div className="home-metric-grid">
                <HomeMetricCard label="Products" value={productCount} detail="active Shopify catalog" />
                <HomeMetricCard label="Customers" value={customerCount} detail="known Shopify customers" />
                <HomeMetricCard label="Orders" value={orderCount} detail="synced Shopify orders" />
                <HomeMetricCard label="Review pending" value={reviewPendingCount} detail={reviewPendingCount ? "plays needing templates" : "run briefing first"} tone={reviewPendingCount ? "attention" : "good"} />
                <HomeMetricCard label="Campaigns pending" value={campaignsPendingCount} detail="selected but not authorized" tone={campaignsPendingCount ? "attention" : "neutral"} />
                <HomeMetricCard label="Approved" value={approvedCount} detail="ready for final Klaviyo step" tone={approvedCount ? "good" : "neutral"} />
              </div>

              <div className="home-grid">
                <HomeModule title="Connect Accounts" detail="Current integration health for the demo store." action="Refresh" onAction={checkConnections}>
                  <div className="connection-list">
                    <ConnectionCard label="Shopify" connected={status.shopify} detail={status.shopify ? `Connected via ${status.shopifySource}. Store data can refresh in BeaconAI.` : "Connect Shopify once with OAuth to load products, customers, and orders."} onAction={status.shopify ? syncShopify : () => startOAuth("shopify")} />
                    <ConnectionCard label="Klaviyo" connected={status.klaviyo} detail={status.klaviyo ? `Connected via ${status.klaviyoSource}. Templates can refresh for campaign review.` : "Connect Klaviyo once with OAuth to fetch existing templates."} onAction={status.klaviyo ? loadKlaviyoTemplates : () => startOAuth("klaviyo")} />
                  </div>
                </HomeModule>

                <HomeModule title="Pending Review" detail={reviewPendingCount ? "Recommendations waiting for a template decision." : "Run the engine briefing before review starts."} action="Open" onAction={() => setActivePage("queue")}>
                  {reviewablePlays.length ? (
                    <div className="home-list">
                      {reviewablePlays.slice(0, 4).map((play) => (
                        <button key={play.id} className="home-list-row" onClick={() => { setReviewPlayId(play.id); setActivePage("queue"); }}>
                          <span>{selectedTemplateByPlay[play.id] ? "Template selected" : "Needs template"}</span>
                          <strong>{play.play_name || play.play_id}</strong>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-panel">Run Briefing to create reviewable recommendations.</div>
                  )}
                </HomeModule>

                <HomeModule title="Campaign Pipeline" detail="Selected templates and final approval status." action="Open" onAction={() => setActivePage("campaigns")}>
                  {finalCampaigns.length ? (
                    <div className="home-list">
                      {finalCampaigns.slice(0, 4).map((item) => (
                        <button key={item.id} className="home-list-row" onClick={() => setActivePage("campaigns")}>
                          <span>{statusLabel(item.status)}</span>
                          <strong>{item.playTitle}</strong>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-panel">Select a template in Review Queue to assemble a campaign.</div>
                  )}
                </HomeModule>
              </div>
            </>
          )}

          {activePage === "onboarding" && (
            <>
              <div className="onboarding-hero">
                <div>
                  <div className="eyebrow">Onboarding</div>
                  <h2>Connect your store and review your first campaign.</h2>
                  <p>
                    This appears for first-time setup only. Once the required accounts are connected, onboarding can be completed and hidden.
                  </p>
                </div>
              </div>

              <div className="onboarding-layout simple">
                <div className="onboarding-steps">
                  <OnboardingStep
                    number="1"
                    title="Connect Shopify"
                    detail="Let BeaconAI read products, customers, and orders from the store."
                    done={status.shopify && hasStoreSnapshot}
                    action={status.shopify ? "Refresh Shopify" : "Connect Shopify"}
                    onAction={status.shopify ? syncShopify : () => startOAuth("shopify")}
                  />
                  <OnboardingStep
                    number="2"
                    title="Connect Klaviyo"
                    detail="Let BeaconAI find existing templates and prepare campaign drafts."
                    done={status.klaviyo}
                    action={status.klaviyo ? "Fetch templates" : "Connect Klaviyo"}
                    onAction={status.klaviyo ? loadKlaviyoTemplates : () => startOAuth("klaviyo")}
                  />
                  <OnboardingStep
                    number="3"
                    title="Review first campaign"
                    detail="BeaconAI prepares recommendations. Review the template choice and approve the campaign."
                    done={Boolean(approvedCount)}
                    action="Open Briefing"
                    onAction={() => setActivePage("briefing")}
                    secondaryAction="Review Queue"
                    onSecondaryAction={() => setActivePage("queue")}
                  />

                  <div className="setup-next-row">
                    <div>
                      <div className="section-kicker">After setup</div>
                      <h3>Your daily workflow</h3>
                      <p>Use Briefing to understand recommendations, Review Queue to choose templates, and Campaigns to approve final packages.</p>
                    </div>
                    <div className="setup-next-actions">
                      <button className="btn primary" onClick={finishOnboarding} disabled={!onboardingReadyToFinish}>
                        {onboardingReadyToFinish ? "Finish onboarding" : "Connect accounts first"}
                      </button>
                      <button className="btn" onClick={() => setActivePage("briefing")}>Briefing</button>
                      <button className="btn" onClick={() => setActivePage("queue")}>Review Queue</button>
                      <button className="btn" onClick={() => setActivePage("campaigns")}>Campaigns</button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {activePage === "briefing" && (
            <>
              <div className="briefing-titlebar">
                <div>
                  <h2>{workflowPlays.length ? `Your briefing slate is ready — ${recommendedRows.length || workflowPlays.length} plays for your review` : "Run the engine briefing to create a review slate"}</h2>
                  <p>
                    <strong>{recommendedRows.length}</strong> recommended now · <strong>{experimentRows.length}</strong> experiments · <strong>{consideredRows.length}</strong> considered.
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
                      {(recommendedRows.length ? recommendedRows : selectableRows).map(({ play }) => (
                        <RecommendationRow
                          key={play.play_id}
                          play={play}
                          selected={selectedBriefingRow?.play.play_id === play.play_id}
                          onSelect={setSelectedBriefingPlayId}
                        />
                      ))}
                      {!selectableRows.length ? <div className="empty-panel inline">Refresh briefing to run the engine and load recommendations.</div> : null}
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
                      <span>Considered (not selected)</span>
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
                />
              </div>
            </>
          )}

          {activePage === "queue" && (
            <>
              <div className="queue-layout">
                <div className="draft-list">
                  <div className="section-kicker">Recommendations</div>
                  {reviewablePlays.length ? reviewablePlays.map((play) => {
                    const chosen = klaviyoTemplates.find((item) => item.id === selectedTemplateByPlay[play.id]);
                    return (
                      <button key={play.id} className={`draft-card ${reviewPlay?.id === play.id ? "selected" : ""}`} onClick={() => setReviewPlayId(play.id)}>
                        <div className="draft-state"><span className="dot" /> {chosen ? "Template selected" : "Needs template"}</div>
                        <h3>{play.play_name || play.play_id}</h3>
                        <p>{play.audience_archetype || "Recommended audience"}</p>
                      </button>
                    );
                  }) : <div className="empty-panel">Run Briefing before reviewing templates.</div>}
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
            </>
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

          {activePage === "campaigns" && (
            <>
              <div className="hero-card compact">
                <div className="eyebrow">Final campaign approval</div>
                <h2>Approved recommendation and selected template, together.</h2>
                <p>
                  This page is the final package view before Klaviyo creation: recommendation, chosen template,
                  audience, copy preview, suppression, and approval status.
                </p>
              </div>
              {finalCampaigns.length ? (
                <CampaignPackages
                  campaigns={finalCampaigns}
                  onCreateInKlaviyo={createCampaignTemplateInKlaviyo}
                  onSendCampaign={sendKlaviyoCampaign}
                  publishingId={publishingCampaignId}
                  sendingId={sendingCampaignId}
                  audiencePreviews={audiencePreviewsByCampaign}
                  onPreviewAudience={previewCampaignAudience}
                  previewingId={previewingCampaignId}
                />
              ) : (
                <div className="empty-panel">Select a template in Review Queue to assemble the final campaign package.</div>
              )}
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
