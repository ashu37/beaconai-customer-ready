#!/usr/bin/env node
//
// Creates ONE Klaviyo draft through the real handoff code, against a real
// account, and reports what Klaviyo actually holds afterwards.
//
//   npm run smoke:klaviyo
//
// Needs, in api/.env:
//   KLAVIYO_SMOKE_API_KEY     private key of a TEST Klaviyo account
//   KLAVIYO_SMOKE_RECIPIENTS  comma-separated inboxes you control
//
// WHY IT EXISTS
// The unit and route tests speak to a local fake Klaviyo. A fake is only as
// right as the person who wrote it: the handoff once sent a request Klaviyo
// refuses, and a permissive fake accepted it. This is the check the fake cannot
// make — whether Klaviyo itself takes these requests, at the pinned revision.
//
// WHAT IT NEVER DOES
// It never sends. There is no send call anywhere in this path, and the campaign
// is created without a schedule. It reads no database and no store's stored
// credentials: the key comes only from KLAVIYO_SMOKE_API_KEY, so it cannot touch
// a merchant's account by accident.
//
// Each run leaves a template, a list, its profiles and a draft campaign in the
// test account. Delete them in Klaviyo when you are done.

require("dotenv").config();
const { config } = require("../config");
const { createCampaignSendPackage, getKlaviyoCampaign } = require("../services/klaviyoClient");
const { buildStarterShell, renderBrandEmail, slotValuesForCampaign } = require("../services/brandEmailRenderer");
const axios = require("axios");

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function fail(message) {
  console.error(`\n✖ ${message}\n`);
  process.exit(1);
}

function providerDetail(error) {
  const errors = error.response?.data?.errors;
  if (Array.isArray(errors) && errors.length) {
    return errors.map((e) => `${e.status || ""} ${e.title || ""}: ${e.detail || ""}${e.source?.pointer ? ` (at ${e.source.pointer})` : ""}`).join("\n    ");
  }
  return error.message;
}

function klaviyo(privateKey) {
  return axios.create({
    baseURL: config.klaviyo.apiBaseUrl,
    timeout: 30000,
    headers: {
      Authorization: `Klaviyo-API-Key ${privateKey}`,
      accept: "application/json",
      revision: config.klaviyo.revision,
    },
  });
}

// Bulk imports are asynchronous; the handoff does not wait for them. This does,
// because "the list is empty" and "the import has not finished" look the same
// in Klaviyo's UI and have different fixes.
async function waitForImport(client, jobId, { timeoutMs = 90000 } = {}) {
  const started = Date.now();
  for (;;) {
    const { data } = await client.get(`/profile-bulk-import-jobs/${jobId}`);
    const attrs = data?.data?.attributes || {};
    if (["complete", "cancelled", "failed"].includes(attrs.status) || Date.now() - started > timeoutMs) return attrs;
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
}

async function main() {
  const privateKey = process.env.KLAVIYO_SMOKE_API_KEY;
  const recipients = String(process.env.KLAVIYO_SMOKE_RECIPIENTS || "")
    .split(",").map((s) => s.trim()).filter(Boolean);

  if (!privateKey) fail("KLAVIYO_SMOKE_API_KEY is not set in api/.env.");
  if (!recipients.length) fail("KLAVIYO_SMOKE_RECIPIENTS is not set in api/.env.");
  const bad = recipients.filter((e) => !EMAIL_RE.test(e));
  if (bad.length) fail(`These don't look like email addresses: ${bad.length} of ${recipients.length}.`);

  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const campaign = {
    playTitle: `Smoke test ${stamp}`,
    subject: `BeaconAI smoke test ${stamp}`,
    previewText: "If you can read this, the envelope reached Klaviyo.",
    bodyH2: "This is a BeaconAI smoke test.",
    bodyP1: "It was created as a draft and should never be sent to anyone.",
    cta: "Nothing to see",
  };
  // The real renderer and the real starter shell: the same path a merchant's
  // approved email takes, including the unsubscribe link Klaviyo requires.
  const html = renderBrandEmail(
    { html: buildStarterShell(), shopDomain: "smoke-test" },
    slotValuesForCampaign(campaign, { brandName: "BeaconAI smoke test", ctaUrl: "https://example.com/" })
  );

  console.log(`Klaviyo revision ${config.klaviyo.revision} · ${recipients.length} recipient(s)`);
  console.log(`Creating draft "BeaconAI - ${campaign.playTitle}" …`);

  let result;
  try {
    result = await createCampaignSendPackage(
      privateKey,
      campaign,
      { recipients: recipients.map((email, i) => ({ email, customerId: `smoke-${i + 1}` })) },
      { html }
    );
  } catch (error) {
    fail(
      `Stopped at stage "${error.providerStage}" ` +
      `(${error.provenNothingCreated ? "nothing was created" : "earlier steps may have created objects — check Klaviyo"}).\n` +
      `    ${providerDetail(error)}`
    );
  }

  const campaignId = result.campaign?.data?.id;
  console.log("\n✔ Package created");
  console.log(`  template   ${result.template?.data?.id || "—"}`);
  console.log(`  list       ${result.list?.data?.id || "—"}`);
  console.log(`  import job ${result.importJob?.data?.id || "—"}`);
  console.log(`  campaign   ${campaignId || "—"}`);
  console.log(`  message    ${result.messages?.data?.[0]?.id || "—"}`);
  console.log(`  template assigned: ${result.assignment ? "yes" : "NO"}`);

  const client = klaviyo(privateKey);

  // What Klaviyo now holds, read back rather than assumed from our request.
  const stored = campaignId ? await getKlaviyoCampaign(privateKey, campaignId) : null;
  console.log(`\nCampaign status: ${stored?.status || "unknown"}  (expected: Draft)`);

  const { data: messages } = await client.get(`/campaigns/${campaignId}/campaign-messages`);
  const message = messages?.data?.[0]?.attributes || {};
  const content = message.definition?.content || message.content || {};
  console.log(`Subject:      ${content.subject || "MISSING"}`);
  console.log(`Preview text: ${content.preview_text || "—"}`);
  console.log(`From:         ${content.from_label || "—"} <${content.from_email || "MISSING"}>`);

  const importJobId = result.importJob?.data?.id;
  if (importJobId) {
    process.stdout.write("\nWaiting for the profile import … ");
    const job = await waitForImport(client, importJobId);
    console.log(`${job.status}: ${job.completed_count ?? "?"} of ${job.total_count ?? "?"} imported, ${job.failed_count ?? 0} failed`);
  }

  console.log("\nNext: open this campaign in the test Klaviyo account, check the email with");
  console.log("Preview & test, then delete the campaign, list and template. Do not send it.\n");
  process.exit(0);
}

main().catch((error) => fail(providerDetail(error)));
