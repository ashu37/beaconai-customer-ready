// The audience and final-review panels.
//
// Extracted from the workspace so they can be rendered on their own — for
// design review, and because a panel whose only route to the screen is a fully
// seeded backend never gets looked at until it is too late to change.
//
// These render presenter output and nothing else. Every judgement about what is
// known, unknown or merely planned lives in audienceSummary.js; this decides how
// it looks, not what it claims.
import React from "react";

export function AudiencePanel({ summary }) {
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
      {/* Only exclusions the API can evidence, each with its own reason.
          Silence where there is none. */}
      {summary.exclusions.map((exclusion) => (
        <p key={exclusion.code} className="audience-note">{exclusion.label}</p>
      ))}
      {summary.noComparisonWarning ? (
        <p className="audience-note warn">{summary.noComparisonWarning}</p>
      ) : null}
      {summary.providerNote ? <p className="audience-note">{summary.providerNote}</p> : null}
      <p className="audience-note">Actual sent: <strong>{summary.actualSentLabel}</strong></p>
      {summary.stale ? (
        <p className="audience-note">This campaign uses an earlier verified briefing.</p>
      ) : null}
    </div>
  );
}

export function FinalReviewPanel({
  campaign, summary, sender, design, effectiveDestination,
  previewHtml, frozenHtml, frozenAt, onEditStep,
}) {
  const frozen = Boolean(frozenHtml || frozenAt);
  return (
    <div className="final-review">
      <div className="final-review-block">
        <div className="final-review-head">
          <span className="section-kicker">Email</span>
          {onEditStep ? (
            <button type="button" className="link-btn" onClick={() => onEditStep("copy")}>Edit email</button>
          ) : null}
        </div>
        <p><strong>{campaign.subject}</strong></p>
        <p className="final-review-meta">{campaign.previewText}</p>
        <p className="final-review-meta">Design: {design}</p>
        <p className="final-review-meta">Button: {campaign.cta}</p>
        {/* The link the rendered button actually carries, not the input's
            contents — those differ whenever a design default is in play. */}
        <p className="final-review-meta">Link: <code>{effectiveDestination || "Not set"}</code></p>
      </div>

      <div className="final-review-block">
        <div className="final-review-head">
          <span className="section-kicker">Audience</span>
          {onEditStep ? (
            <button type="button" className="link-btn" onClick={() => onEditStep("audience")}>Review audience</button>
          ) : null}
        </div>
        {summary.available ? (
          <>
            {summary.rows.map((row) => (
              <p key={row.key} className="final-review-meta">{row.label}: <strong>{row.value}</strong></p>
            ))}
            {summary.exclusions.map((e) => (
              <p key={e.code} className="final-review-meta">{e.label}</p>
            ))}
          </>
        ) : <p className="final-review-meta">{summary.message}</p>}
      </div>

      <div className="final-review-block final-review-preview">
        <span className="section-kicker">{frozen ? "Handoff email" : "Current email preview"}</span>
        {/* The spec requires the actual email here, not only its subject.
            Confirming a send from a summary is confirming something you cannot
            see. After handoff this is the FROZEN snapshot, labelled "handoff
            email" and never "final sent email" — edits made in Klaviyo
            afterwards are invisible to us. */}
        {frozenHtml || previewHtml ? (
          <>
            <iframe
              title={frozenHtml ? "Email handed to Klaviyo" : "Current email preview"}
              className="final-review-frame"
              srcDoc={frozenHtml || previewHtml}
            />
            {frozenHtml ? (
              <p className="final-review-meta">
                Email handed to Klaviyo{frozenAt ? ` on ${frozenAt}` : ""}. Changes made later in Klaviyo aren't reflected here.
              </p>
            ) : null}
          </>
        ) : (
          // A legacy record with no stored HTML. Never regenerated from today's
          // design: that would show an email nobody ever sent.
          <p className="final-review-meta">
            {frozen ? "The original email wasn't recorded." : "Go back to Edit email to load the preview."}
          </p>
        )}
      </div>

      <div className="final-review-block">
        <span className="section-kicker">Sender</span>
        {/* Reported by the provider, or an honest absence. Never assembled from
            the store domain. */}
        <p className="final-review-meta">Sender: <strong>{sender.display}</strong></p>
        <p className="final-review-meta">Reply-to: <strong>{sender.replyTo}</strong></p>
      </div>
    </div>
  );
}
