// Seed-state harness for design review.
//
// Renders the campaign editor/preview in each state the approved specification
// requires screenshots for, with synthetic data only. It stubs the API rather
// than running the stack because several required states — a failed save, a
// changed design, an unreachable preview — cannot be produced on demand from a
// healthy backend, and faking them by breaking the real one would prove less.
//
// Sample mode cannot create a provider draft: there is no handoff action here.
import React from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api";
import { CampaignReviewPane } from "./App";
import "./styles.css";

const BRAND_CONTEXT = {
  brandName: "Acme Skincare",
  category: "beauty and personal care",
  productLanguage: { bestSellers: [{ title: "Night Serum" }] },
  messaging: { useWords: ["clean", "gentle", "daily"] },
};

const PLAY = {
  id: "play-winback",
  play_id: "play-winback",
  play_name: "Bring back first-time buyers",
  play_one_liner: "Customers who bought once and haven't returned in 90 days.",
  audience_size: 1200,
};

const TEMPLATE = {
  id: "beacon-winback-clean", source: "beacon", name: "Win-back",
  subject: "Your next favourite is waiting",
  previewText: "A reason to come back to Acme Skincare.",
  bodyH2: "Still thinking about Night Serum?",
  bodyP1: "Your favourites are here, plus a few new arrivals you haven't met yet.",
  cta: "Explore the collection",
};

const SAMPLE_HTML = `<!doctype html><html><body style="margin:0;font-family:Helvetica,Arial,sans-serif;background:#f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:16px 0;"><tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;">
<tr><td style="padding:20px 24px 0;"><div style="font:700 15px Helvetica;color:#1f2933;">ACME SKINCARE</div></td></tr>
<tr><td style="padding:24px;">
<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;color:#1f2933;">Still thinking about Night Serum?</h1>
<p style="margin:0 0 16px;font-size:16px;line-height:1.55;color:#333;">Your favourites are here, plus a few new arrivals you haven't met yet.</p>
<div style="text-align:center;margin:0 0 20px;"><div style="width:260px;height:150px;background:#ece7e0;line-height:150px;color:#8a8578;font-size:13px;">Product image</div></div>
<a href="https://acme.example/collections/serums" style="display:inline-block;background:#1f2933;color:#fff;text-decoration:none;font-weight:bold;padding:14px 22px;">Explore the collection</a>
</td></tr>
<tr><td style="padding:20px 24px;border-top:1px solid #e4e4e4;"><p style="margin:0;font-size:12px;color:#777;">You're receiving this because you shopped with Acme Skincare.<br/><a href="#" style="color:#777;">Unsubscribe</a></p></td></tr>
</table></td></tr></table></body></html>`;

// Each entry is one screenshot in the specification's list.
const SCENARIOS = {
  ready: { label: "Ready branded email", preview: "ok" },
  "empty-support": { label: "Empty optional support paragraph", preview: "ok", edits: { bodyP2: "" } },
  "invalid-destination": { label: "Invalid destination", preview: "invalid", destination: "acme.example" },
  "no-destination": { label: "No destination set", preview: "missing", destination: "" },
  "save-failed": { label: "Failed save", preview: "ok", saveState: "failed" },
  "save-conflict": { label: "Revision conflict", preview: "ok", saveState: "conflict" },
  "design-changed": { label: "Design changed / stale preview", preview: "ok", designVersion: 3 },
  "preview-failed": { label: "Preview refresh failed", preview: "error" },
  "no-design": { label: "No configured design", preview: "setup" },
};

function stubApi(scenario) {
  api.previewCampaignHtml = async () => {
    if (scenario.preview === "setup") {
      const error = new Error("Your store's email design isn't set up yet.");
      error.code = "brand_setup_required";
      throw error;
    }
    if (scenario.preview === "missing") {
      const error = new Error("This campaign has no destination link.");
      error.code = "missing_destination"; error.slot = "cta_url";
      throw error;
    }
    if (scenario.preview === "invalid") {
      const error = new Error('The "cta_url" value was rejected: it is not a valid absolute URL');
      error.code = "slot_value_rejected"; error.slot = "cta_url";
      throw error;
    }
    if (scenario.preview === "error") throw new Error("network");
    return {
      html: SAMPLE_HTML, templateVersion: 2, renderFingerprint: "seedfingerprint0",
      effectiveDestinationUrl: scenario.destination || "https://acme.example/collections/serums",
    };
  };
}

function Harness() {
  const key = new URLSearchParams(window.location.search).get("state") || "ready";
  const scenario = SCENARIOS[key] || SCENARIOS.ready;
  stubApi(scenario);

  const draft = {
    ...TEMPLATE, id: PLAY.id, playTitle: PLAY.play_name,
    bodyP2: scenario.edits?.bodyP2 ?? "Only a few left in this size.",
    destinationUrl: scenario.destination ?? "https://acme.example/collections/serums",
  };

  return (
    <div style={{ padding: 20, maxWidth: 1180, margin: "0 auto", background: "#f7f5f0", minHeight: "100vh" }}>
      <div className="sample-banner" role="note">
        Sample campaign — no live recipients. State: {scenario.label}
      </div>
      <CampaignReviewPane
        play={PLAY}
        brandContext={BRAND_CONTEXT}
        brandDesign={scenario.preview === "setup"
          ? { configured: false }
          : { configured: true, active: { version: 2, approvedAt: "2026-09-08T00:00:00Z" } }}
        beaconTemplates={[TEMPLATE]}
        klaviyoTemplates={[TEMPLATE]}
        selectedTemplate={TEMPLATE}
        onChooseTemplate={() => {}}
        draft={draft}
        onChange={() => {}}
        onRestoreField={() => {}}
        onRefreshBrandContext={() => {}}
        onRefreshTemplates={() => {}}
        klaviyoFailed={false}
        // Seeded so the Suggested/Edited badges are accurate. Without it every
        // field reads as "Edited", which would look like a defect in a review
        // screenshot rather than an artifact of the harness.
        agentCopy={{
          subject_variants: [TEMPLATE.subject],
          preview_text: TEMPLATE.previewText,
          headline: TEMPLATE.bodyH2,
          body: TEMPLATE.bodyP1,
          support: draft.bodyP2,
          cta: TEMPLATE.cta,
        }}
        copyStatus="ready"
        draftEdits={scenario.edits || {}}
        saveState={scenario.saveState || "saved"}
        onRetrySave={() => {}}
        activeBrandTemplateVersion={scenario.designVersion || 2}
        onPreviewRendered={() => {}}
        destinationUrl={draft.destinationUrl}
        onChangeDestination={() => {}}
        campaignSignature="seed-signature"
      />
    </div>
  );
}

createRoot(document.getElementById("root")).render(<Harness />);
