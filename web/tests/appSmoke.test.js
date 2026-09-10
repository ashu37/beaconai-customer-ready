import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, cleanup, render } from "@testing-library/react";

// Renders the REAL app, not a harness around its parts.
//
// Both defects this covers shipped because the seed harness imported the
// extracted modules directly, so the panels rendered there while App.jsx had no
// import for them at all. A component that only ever renders inside its own
// harness proves nothing about the app.
//
// The api module is stubbed at the module level before App is imported, so
// startup runs its real sequence against predictable answers.
const calls = [];
const stub = (name, value) => async (...args) => { calls.push(name); return typeof value === "function" ? value(...args) : value; };

const apiModule = await import("../src/api.js");
Object.assign(apiModule.api, {
  health: stub("health", { ok: true }),
  session: stub("session", { ok: true, authenticated: false, shopDomain: null }),
  connectionStatus: stub("connectionStatus", { ok: true, status: { shopify: { connected: true }, klaviyo: { connected: true } } }),
  testShopify: stub("testShopify", { ok: true }),
  testKlaviyo: stub("testKlaviyo", { ok: true }),
  brandContext: stub("brandContext", { ok: true, brandContext: null }),
  brandEmailTemplate: stub("brandEmailTemplate", { ok: true, configured: false }),
  klaviyoSender: stub("klaviyoSender", { ok: true, sender: null }),
  getEngineInput: stub("getEngineInput", { ok: true, input: null }),
  getLatestEngineRun: stub("getLatestEngineRun", { ok: true, found: false }),
  listCampaigns: stub("listCampaigns", { ok: true, campaigns: [] }),
  syncStatus: stub("syncStatus", { ok: true, ready: false, reasons: [] }),
  getStatsSeries: stub("getStatsSeries", { ok: true, weeks: [] }),
  getKlaviyoTemplates: stub("getKlaviyoTemplates", { ok: true, templates: [] }),
});

const { App } = await import("../src/App.jsx");

test.afterEach(() => cleanup());

test("the app starts up signed out without throwing", async () => {
  // The reported failure: startup called signInState, which was never imported,
  // and the whole check died with "API health failed: signInState is not
  // defined" — leaving connection AND sign-in state unset.
  const errors = [];
  const originalError = console.error;
  console.error = (...args) => errors.push(args.join(" "));

  try {
    await act(async () => {
      render(React.createElement(App));
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
  } finally {
    console.error = originalError;
  }

  assert.ok(calls.includes("health"), "startup ran");
  assert.ok(calls.includes("session"), "and asked whether this browser is signed in");
  // The load-bearing assertion. The reported failure threw inside the sign-in
  // check, which aborted the rest of checkConnections — so connection state was
  // never set and the app silently fell back to the pre-connected screen. Any
  // throw between /session and here leaves this call unmade.
  assert.ok(
    calls.includes("connectionStatus"),
    "startup did not get past the sign-in check — something threw in between"
  );

  const referenceErrors = errors.filter((line) => /is not defined|ReferenceError/.test(line));
  assert.deepEqual(referenceErrors, [], "no undefined identifier logged on the startup path");

  // And crucially, what the MERCHANT sees. The reported failure never reached
  // console.error at all: checkConnections catches everything and turns it into
  // a banner, so the app rendered "API health failed: signInState is not
  // defined" while the test suite stayed green. Asserting on the console alone
  // would have missed it exactly as the last suite did.
  const rendered = document.body.textContent || "";
  assert.ok(!/is not defined/.test(rendered), `a ReferenceError reached the screen: ${rendered.slice(0, 200)}`);
  assert.ok(!/ReferenceError/.test(rendered), "a ReferenceError reached the screen");
});

test("every component the app renders is actually imported", async () => {
  // A cheap, total check for the class of defect above: read App.jsx and confirm
  // each JSX component it references resolves to an import, a local definition,
  // or React itself. The bundler does not do this, and a missing binding only
  // fails when a user opens that particular screen.
  const { readFileSync } = await import("node:fs");
  const source = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");

  const declared = new Set();
  for (const match of source.matchAll(/^import\s+(?:(\w+)\s*,\s*)?\{([^}]*)\}\s+from/gm)) {
    if (match[1]) declared.add(match[1]);
    for (const name of match[2].split(",")) {
      const clean = name.trim().split(/\s+as\s+/).pop().trim();
      if (clean) declared.add(clean);
    }
  }
  for (const match of source.matchAll(/^import\s+(\w+)\s+from/gm)) declared.add(match[1]);
  for (const match of source.matchAll(/^\s*(?:export\s+)?function\s+([A-Z]\w*)/gm)) declared.add(match[1]);
  for (const match of source.matchAll(/^\s*(?:export\s+)?const\s+([A-Z]\w*)\s*=/gm)) declared.add(match[1]);

  const missing = new Set();
  for (const match of source.matchAll(/<([A-Z]\w*)/g)) {
    if (!declared.has(match[1]) && match[1] !== "React") missing.add(match[1]);
  }

  assert.deepEqual([...missing], [], "components referenced but never imported or defined");
});
