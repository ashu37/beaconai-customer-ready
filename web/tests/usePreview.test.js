import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, cleanup, render } from "@testing-library/react";

import { usePreview } from "../src/usePreview.js";
import { campaignSignature } from "../src/campaignSaveGate.js";
import { PREVIEW_STATE } from "../src/previewFreshness.js";

// Lets the debounce timer fire and the resulting promise settle. A microtask
// flush is not enough: the hook debounces with setTimeout.
const tick = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)); });

// A component that exercises the hook the way CampaignReviewPane does.
function Harness({ draft, campaignSignature: sig, campaignKey, fetchPreview, onPreviewRendered }) {
  const { html, freshness } = usePreview({
    draft,
    campaignSignature: sig,
    campaignKey,
    brandContext: { brandName: "Shop A" },
    activeBrandTemplateVersion: 1,
    fetchPreview,
    onPreviewRendered,
    debounceMs: 0,
  });
  return React.createElement("div", null,
    React.createElement("span", { "data-testid": "state" }, freshness.state),
    React.createElement("span", { "data-testid": "html" }, html));
}

test.afterEach(() => cleanup());

test("a refresh records the signature of the draft it actually sent", async () => {
  // The reported bug: the refresh function was memoized on brandContext, so it
  // captured the signature from the render that created it. Edit copy, save,
  // refresh — the email updated, and the handoff still called it out of date
  // because the recorded signature was the old one.
  const recorded = [];
  const seen = [];
  const fetchPreview = async (payload) => {
    seen.push(payload.subject);
    return { html: `<p>${payload.subject}</p>`, templateVersion: 1, renderFingerprint: "fp" };
  };

  const first = { subject: "Original", destinationUrl: "https://a.test/" };
  const view = render(React.createElement(Harness, {
    draft: first,
    campaignSignature: campaignSignature({ edits: { subject: "Original" }, destinationUrl: "https://a.test/" }),
    campaignKey: "play-1:tpl-1",
    fetchPreview,
    onPreviewRendered: (info) => recorded.push(info),
  }));
  await tick();

  const edited = { subject: "Edited", destinationUrl: "https://a.test/" };
  const editedSignature = campaignSignature({ edits: { subject: "Edited" }, destinationUrl: "https://a.test/" });
  await act(async () => {
    view.rerender(React.createElement(Harness, {
      draft: edited,
      campaignSignature: editedSignature,
      campaignKey: "play-1:tpl-1",
      fetchPreview,
      onPreviewRendered: (info) => recorded.push(info),
    }));
  });
  await tick();

  assert.ok(seen.includes("Edited"), "the request went out with the edited copy");
  const last = recorded[recorded.length - 1];
  assert.equal(last.campaignSignature, editedSignature,
    "and was recorded against the edited signature, not the one captured at mount");
  assert.equal(view.getByTestId("state").textContent, PREVIEW_STATE.fresh);
});

test("typing a destination refreshes the preview", async () => {
  // The debounce used to watch a fixed list of copy fields, so a changed
  // destination never triggered a refresh at all.
  const seen = [];
  const fetchPreview = async (payload) => {
    seen.push(payload.destinationUrl);
    return { html: "<p>ok</p>", templateVersion: 1, renderFingerprint: "fp" };
  };
  const base = { subject: "S", destinationUrl: "https://a.test/" };
  const view = render(React.createElement(Harness, {
    draft: base,
    campaignSignature: campaignSignature({ edits: { subject: "S" }, destinationUrl: "https://a.test/" }),
    campaignKey: "play-1:tpl-1", fetchPreview, onPreviewRendered: () => {},
  }));
  await tick();

  await act(async () => {
    view.rerender(React.createElement(Harness, {
      draft: { ...base, destinationUrl: "https://b.test/" },
      campaignSignature: campaignSignature({ edits: { subject: "S" }, destinationUrl: "https://b.test/" }),
      campaignKey: "play-1:tpl-1", fetchPreview, onPreviewRendered: () => {},
    }));
  });
  await tick();

  assert.ok(seen.includes("https://b.test/"), "the new destination was previewed");
});

test("a response for a campaign the merchant has left is discarded", async () => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  const fetchPreview = async (payload) => {
    if (payload.subject === "Slow") { await gate; return { html: "<p>SLOW</p>", templateVersion: 1, renderFingerprint: "slow" }; }
    return { html: "<p>FAST</p>", templateVersion: 1, renderFingerprint: "fast" };
  };
  const recorded = [];

  const view = render(React.createElement(Harness, {
    draft: { subject: "Slow" },
    campaignSignature: "sig-slow", campaignKey: "play-1:tpl-1",
    fetchPreview, onPreviewRendered: (i) => recorded.push(i),
  }));
  await tick();

  // Switch campaigns while the first request is still in flight.
  await act(async () => {
    view.rerender(React.createElement(Harness, {
      draft: { subject: "Fast" },
      campaignSignature: "sig-fast", campaignKey: "play-2:tpl-2",
      fetchPreview, onPreviewRendered: (i) => recorded.push(i),
    }));
  });
  await tick();
  await act(async () => { release(); });
  await tick();

  // Showing one campaign's email under another's name is the failure here.
  assert.ok(!view.getByTestId("html").textContent.includes("SLOW"));
  assert.ok(!recorded.some((r) => r.fingerprint === "slow"), "the abandoned request approved nothing");
});

test("a failed refresh keeps the last render but marks it not current", async () => {
  let fail = false;
  const fetchPreview = async () => {
    if (fail) throw new Error("network");
    return { html: "<p>good</p>", templateVersion: 1, renderFingerprint: "fp" };
  };
  const props = {
    draft: { subject: "S" }, campaignSignature: "sig", campaignKey: "k",
    fetchPreview, onPreviewRendered: () => {},
  };
  const view = render(React.createElement(Harness, props));
  await tick();
  assert.equal(view.getByTestId("state").textContent, PREVIEW_STATE.fresh);

  fail = true;
  await act(async () => {
    view.rerender(React.createElement(Harness, { ...props, draft: { subject: "S2" }, campaignSignature: "sig2" }));
  });
  await tick();

  assert.ok(view.getByTestId("html").textContent.includes("good"), "the last good render is still shown");
  assert.equal(view.getByTestId("state").textContent, PREVIEW_STATE.failed, "but not as current");
});
