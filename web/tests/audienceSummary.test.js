import test from "node:test";
import assert from "node:assert/strict";
import { summarizeAudience, summarizeSender } from "../src/audienceSummary.js";

const materialized = { materialized: true };
const breakdown = {
  matched: 1200, plannedEmailGroup: 900, comparisonGroup: 100,
  exclusions: [{ code: "no_email_on_file", count: 200, label: "200 matched customers have no email address on file." }],
  providerAppliesAtSend: "Klaviyo applies consent and suppression at send.",
  actualSentCount: null,
};

test("matched, planned and held back are three separate numbers", () => {
  const view = summarizeAudience({ audience: materialized, breakdown });
  assert.deepEqual(view.rows.map((r) => [r.key, r.value]), [
    ["matched", "1,200"], ["planned", "900"], ["comparison", "100"],
  ]);
  // Planned is assignment, not delivery.
  assert.match(view.rows[1].help, /Klaviyo confirms actual delivery/);
});

test("the actual sent count is unknown until it is confirmed", () => {
  const view = summarizeAudience({ audience: materialized, breakdown });
  assert.equal(view.actualSent, null);
  assert.equal(view.actualSentLabel, "Confirmed after sending");
  assert.notEqual(view.actualSentLabel, "0");
});

test("only evidenced exclusions are shown, with their reason", () => {
  const view = summarizeAudience({ audience: materialized, breakdown });
  assert.equal(view.exclusions.length, 1);
  assert.equal(view.exclusions[0].code, "no_email_on_file");
  // The claim the product used to make without applying anything.
  assert.ok(!JSON.stringify(view).toLowerCase().includes("standard suppressions"));
});

test("no evidence means no exclusions claimed", () => {
  const view = summarizeAudience({
    audience: materialized, breakdown: { ...breakdown, exclusions: [] },
  });
  assert.deepEqual(view.exclusions, [], "an empty list, not a reassurance");
});

test("no comparison group is explained rather than silently allowed", () => {
  const view = summarizeAudience({
    audience: materialized, breakdown: { ...breakdown, comparisonGroup: 0 },
  });
  assert.match(view.noComparisonWarning, /can't estimate this campaign's added revenue/);
});

test("an unmaterialized audience is a typed absence, not zeroes", () => {
  const view = summarizeAudience({ audience: { materialized: false }, breakdown: null });
  assert.equal(view.available, false);
  assert.deepEqual(view.rows, []);
  assert.match(view.message, /didn't produce a sendable audience/);
});

test("a campaign whose briefing belongs elsewhere shows no audience at all", () => {
  for (const provenance of ["foreign_run", "unknown_run"]) {
    const view = summarizeAudience({ audience: materialized, breakdown, inputProvenance: provenance });
    assert.equal(view.available, false, provenance);
    assert.deepEqual(view.rows, []);
  }
});

test("a missing number renders as unknown, never as zero", () => {
  const view = summarizeAudience({
    audience: materialized,
    breakdown: { ...breakdown, matched: null, comparisonGroup: null },
  });
  assert.equal(view.rows[0].value, "—");
  assert.equal(view.rows[2].value, "—");
});

test("an unverified sender says to check in Klaviyo", () => {
  for (const value of [null, undefined, {}, { name: null, email: null }]) {
    const view = summarizeSender(value);
    assert.equal(view.verified, false);
    assert.equal(view.display, "Check in Klaviyo");
  }
});

test("a verified sender is shown as the provider reported it", () => {
  const view = summarizeSender({ name: "Acme Skincare", email: "hello@acme.example" });
  assert.equal(view.verified, true);
  assert.equal(view.display, "Acme Skincare <hello@acme.example>");
  // Klaviyo sets reply-to per campaign, so an account lookup cannot report it.
  // Left explicit rather than implying it matches the sender.
  assert.equal(view.replyTo, "Check in Klaviyo");
});
