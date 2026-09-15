// The audience and final-review panels.
//
// Extracted from the workspace so they can be rendered on their own — for
// design review, and because a panel whose only route to the screen is a fully
// seeded backend never gets looked at until it is too late to change.
//
// These render presenter output and nothing else. Every judgement about what is
// known, unknown or merely planned lives in audienceSummary.js; this decides how
// it looks, not what it claims.
import React, { useEffect, useRef, useState } from "react";
import {
  FINISH_IN_KLAVIYO_STEPS,
  HANDOFF_SUGGESTION_NOTE,
  SUGGESTED_MESSAGING_NOTE,
  finishesInKlaviyo,
} from "./handoffMode";

// The fields a merchant copies into their own Klaviyo template, in the order
// they would use them. Empty ones are left out rather than shown blank.
const MESSAGING_FIELDS = [
  { key: "subject", label: "Subject" },
  { key: "previewText", label: "Preview text" },
  { key: "bodyH2", label: "Headline" },
  { key: "bodyP1", label: "Body" },
  { key: "bodyP2", label: "Support paragraph" },
  { key: "cta", label: "Button text" },
  { key: "destinationUrl", label: "Button link" },
];

function CopyButton({ text, label }) {
  const [state, setState] = useState("idle");
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch (_) {
      // Clipboard access can be refused (permissions, an insecure page). Say so;
      // the text is on screen to select by hand.
      setState("failed");
    }
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), 2000);
  };
  return (
    <button type="button" className="btn small copy-btn" onClick={copy} aria-label={`Copy ${label}`}>
      {state === "copied" ? "Copied" : state === "failed" ? "Select to copy" : "Copy"}
    </button>
  );
}

/**
 * Suggested messaging for a campaign finished in Klaviyo.
 *
 * Never called "the email": the merchant chooses the template and finishes the
 * content in Klaviyo. After handoff it is the suggestion that was handed over,
 * and says so — nothing here reads back what Klaviyo finally sent.
 */
export function SuggestedMessaging({ copy, destinationUrl = null, handedOffAt = null, headingLevel = "section" }) {
  const values = { ...(copy || {}), destinationUrl: destinationUrl || copy?.destinationUrl || null };
  const rows = MESSAGING_FIELDS
    .map((field) => ({ ...field, value: String(values[field.key] ?? "").trim() }))
    .filter((row) => row.value);
  const handedOff = Boolean(handedOffAt);
  return (
    <div className="suggested-messaging" aria-label={handedOff ? "Handoff suggestion" : "Suggested messaging"}>
      <span className={headingLevel === "section" ? "section-kicker" : "section-meta"}>
        {handedOff ? "Handoff suggestion" : "Suggested messaging"}
      </span>
      <p className="suggested-messaging-note">
        {handedOff
          ? `${HANDOFF_SUGGESTION_NOTE}${typeof handedOffAt === "string" ? ` Handed off ${handedOffAt}.` : ""}`
          : SUGGESTED_MESSAGING_NOTE}
      </p>
      {rows.length ? (
        <dl className="suggested-messaging-rows">
          {rows.map((row) => (
            <div key={row.key} className="suggested-messaging-row">
              <dt>{row.label}</dt>
              <dd>
                <span className="suggested-messaging-value">{row.value}</span>
                <CopyButton text={row.value} label={row.label.toLowerCase()} />
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="final-review-meta">No messaging was suggested for this campaign.</p>
      )}
      {!handedOff ? (
        <p className="final-review-meta">The subject and preview text are added to the Klaviyo draft when it's created.</p>
      ) : null}
    </div>
  );
}

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
  handoffMode = "rendered_email", handoffCopy = null,
}) {
  const frozen = Boolean(frozenHtml || frozenAt);
  const inKlaviyo = finishesInKlaviyo(handoffMode);
  return (
    <div className="final-review">
      <div className="final-review-block">
        <div className="final-review-head">
          <span className="section-kicker">{inKlaviyo ? "Suggested messaging" : "Email"}</span>
          {onEditStep ? (
            <button type="button" className="link-btn" onClick={() => onEditStep("copy")}>{inKlaviyo ? "Edit messaging" : "Edit email"}</button>
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

      {inKlaviyo ? (
        <div className="final-review-block final-review-klaviyo">
          {frozen ? (
            <SuggestedMessaging
              copy={handoffCopy || campaign}
              destinationUrl={handoffCopy ? handoffCopy.destinationUrl : effectiveDestination}
              handedOffAt={frozenAt || true}
            />
          ) : (
            <>
              <span className="section-kicker">Finish in Klaviyo</span>
              <p className="final-review-meta">
                Creating the draft adds this audience, the subject, the preview text and your Klaviyo sender. It has no
                design yet. In Klaviyo:
              </p>
              <ol className="finish-steps">
                {FINISH_IN_KLAVIYO_STEPS.map((step) => <li key={step}>{step}</li>)}
              </ol>
              <p className="final-review-meta">
                BeaconAI never sends email. Changes you make in Klaviyo stay there; BeaconAI doesn't change the draft after
                creating it.
              </p>
            </>
          )}
        </div>
      ) : (
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
      )}

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
