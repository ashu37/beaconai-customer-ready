const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");
const {
  buildStarterShell,
  renderBrandEmail,
  slotValuesForCampaign,
  validateShell,
} = require("../src/services/brandEmailRenderer");
const {
  getActiveBrandTemplate,
  getBrandTemplateVersion,
  requireActiveBrandTemplate,
  saveBrandTemplate,
} = require("../src/services/brandEmailTemplateService");

const SHOP_A = "brand-a.myshopify.com";
const SHOP_B = "brand-b.myshopify.com";

let api;
test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

const draft = {
  bodyH2: "Your favourite is back",
  bodyP1: "We restocked the one you kept coming back for.",
  bodyP2: "Only a few left.",
  cta: "Shop the restock",
  ctaUrl: "https://shop-a.example/collections/restock",
  featuredProduct: { title: "Night Serum", imageUrl: "https://cdn.shop-a.example/serum.jpg" },
};

suite("two shops keep their own shells", async () => {
  await db.resetDatabase();
  await saveBrandTemplate({
    shopDomain: SHOP_A,
    html: buildStarterShell({ accentColor: "#aa0000" }),
    brand: { brandName: "Shop A", footerText: "Sent by Shop A" },
    approvedBy: "founder",
  });
  await saveBrandTemplate({
    shopDomain: SHOP_B,
    html: buildStarterShell({ accentColor: "#0000bb" }),
    brand: { brandName: "Shop B", footerText: "Sent by Shop B" },
    approvedBy: "founder",
  });

  const a = await requireActiveBrandTemplate(SHOP_A);
  const b = await requireActiveBrandTemplate(SHOP_B);

  const htmlA = renderBrandEmail(a, slotValuesForCampaign(draft, a.brand));
  const htmlB = renderBrandEmail(b, slotValuesForCampaign(draft, b.brand));

  assert.ok(htmlA.includes("#aa0000") && htmlA.includes("Sent by Shop A"));
  assert.ok(htmlB.includes("#0000bb") && htmlB.includes("Sent by Shop B"));
  assert.ok(!htmlA.includes("Shop B"), "one merchant's branding never renders into another's email");
  assert.ok(!htmlB.includes("Shop A"));
});

suite("an unconfigured shop is told setup is required, not given BeaconAI styling", async () => {
  await db.resetDatabase();

  await assert.rejects(() => requireActiveBrandTemplate(SHOP_A), (error) => {
    assert.equal(error.code, "brand_setup_required");
    return true;
  });

  const status = await api.get(`/brand/email-template?shopDomain=${encodeURIComponent(SHOP_A)}`);
  assert.equal(status.body.configured, false);
  assert.equal(status.body.code, "brand_setup_required");

  const preview = await api.post("/klaviyo/campaigns/preview-html", {
    shopDomain: SHOP_A, campaign: draft, brandContext: { brandName: "Shop A" },
  });
  assert.equal(preview.status, 409);
  assert.equal(preview.body.code, "brand_setup_required");
  // The failure mode this replaces: silently rendering an unapproved shell.
  assert.ok(!preview.body.html, "no email is produced at all");
});

suite("copy is escaped and links are validated", async () => {
  await db.resetDatabase();
  const template = await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell(), approvedBy: "founder",
  });

  const html = renderBrandEmail(template, slotValuesForCampaign({
    ...draft,
    bodyH2: '"Best" <script>alert(1)</script> & more',
  }, { brandName: "Shop A" }));
  assert.ok(!html.includes("<script>"), "model-written copy cannot inject markup");
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(html.includes("&amp; more"));

  // A CTA that quietly lost its destination would send a dead button the
  // merchant had already approved, so an unusable URL is refused outright.
  for (const bad of ["javascript:alert(1)", "data:text/html,<b>x</b>", "not a url"]) {
    assert.throws(
      () => renderBrandEmail(template, slotValuesForCampaign({ ...draft, ctaUrl: bad }, {})),
      (error) => {
        assert.equal(error.name, "SlotValueRejected");
        assert.equal(error.slot, "cta_url");
        return true;
      }
    );
  }
});

suite("provider merge and unsubscribe syntax survives rendering", async () => {
  await db.resetDatabase();
  const template = await saveBrandTemplate({
    shopDomain: SHOP_A,
    html: buildStarterShell().replace("[[slot:footer_text]]", "[[slot:footer_text]] {{ organization.name }}"),
    approvedBy: "founder",
  });
  const html = renderBrandEmail(template, slotValuesForCampaign(draft, {}));
  assert.ok(html.includes("{% unsubscribe %}"), "the provider's unsubscribe tag is untouched");
  assert.ok(html.includes("{{ organization.name }}"), "and its merge tags too");
});

suite("a shell missing required parts is refused before it is stored", async () => {
  await db.resetDatabase();

  const cases = [
    ["<html><body>[[slot:headline]][[slot:body]][[slot:cta_text]][[slot:cta_url]]</body></html>", /unsubscribe/],
    ["<html><body>{% unsubscribe %}[[slot:body]][[slot:cta_text]][[slot:cta_url]]</body></html>", /headline/],
    ["<html><body><script>x</script>{% unsubscribe %}[[slot:headline]][[slot:body]][[slot:cta_text]][[slot:cta_url]]</body></html>", /script/],
    ["<html><body onload=\"x()\">{% unsubscribe %}[[slot:headline]][[slot:body]][[slot:cta_text]][[slot:cta_url]]</body></html>", /event handler/],
    ["<html><body>{% unsubscribe %}[[slot:headline]][[slot:body]][[slot:cta_text]][[slot:cta_url]][[slot:mystery]]</body></html>", /mystery/],
  ];
  for (const [html, expected] of cases) {
    assert.throws(() => validateShell(html), (error) => {
      assert.equal(error.name, "BrandTemplateInvalid");
      assert.match(error.problems.join("; "), expected);
      return true;
    });
  }

  await assert.rejects(
    () => saveBrandTemplate({ shopDomain: SHOP_A, html: "<html><body>nothing</body></html>" }),
    { name: "BrandTemplateInvalid" }
  );
  const stored = await query(`SELECT count(*)::int AS n FROM clean.brand_email_templates`);
  assert.equal(stored.rows[0].n, 0, "an unusable shell never becomes a row someone could activate");
});

suite("an existing Klaviyo shell is checked, not assumed compatible", async () => {
  process.env.BEACONAI_ADMIN_TOKEN = "test-token";
  const compatible = await fetch(`${api.base}/brand/email-template/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-beaconai-admin-token": "test-token" },
    body: JSON.stringify({ html: buildStarterShell() }),
  });
  const okBody = await compatible.json();
  assert.equal(okBody.compatible, true);
  assert.ok(okBody.slots.includes("headline"));

  const incompatible = await fetch(`${api.base}/brand/email-template/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-beaconai-admin-token": "test-token" },
    body: JSON.stringify({ html: "<html><body>A pretty template with no slots</body></html>" }),
  });
  const badBody = await incompatible.json();
  assert.equal(badBody.compatible, false, "reported as incompatible rather than imported and broken");
  assert.ok(badBody.problems.length);
  delete process.env.BEACONAI_ADMIN_TOKEN;
});

suite("shell configuration is closed unless explicitly enabled", async () => {
  await db.resetDatabase();
  delete process.env.BEACONAI_ADMIN_TOKEN;

  // Arbitrary HTML from an unauthenticated caller is exactly what must not be
  // accepted, so an unconfigured deployment refuses rather than defaulting open.
  const noToken = await api.post("/brand/email-template", {
    shopDomain: SHOP_A, html: buildStarterShell(),
  });
  assert.equal(noToken.status, 503);

  process.env.BEACONAI_ADMIN_TOKEN = "test-token";
  const wrongToken = await api.post("/brand/email-template", {
    shopDomain: SHOP_A, html: buildStarterShell(),
  });
  assert.equal(wrongToken.status, 403);

  const authorized = await fetch(`${api.base}/brand/email-template`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-beaconai-admin-token": "test-token" },
    body: JSON.stringify({ shopDomain: SHOP_A, html: buildStarterShell(), approvedBy: "founder" }),
  });
  assert.equal(authorized.status, 200);
  assert.ok(await getActiveBrandTemplate(SHOP_A));
  delete process.env.BEACONAI_ADMIN_TOKEN;
});

suite("a new brand version does not change what an old campaign sent", async () => {
  await db.resetDatabase();
  const v1 = await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell({ accentColor: "#111111" }),
    brand: { brandName: "Shop A" }, approvedBy: "founder",
  });
  const sentHtml = renderBrandEmail(v1, slotValuesForCampaign(draft, v1.brand));

  const v2 = await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell({ accentColor: "#eeeeee" }),
    brand: { brandName: "Shop A" }, approvedBy: "founder",
  });
  assert.equal(v2.version, v1.version + 1);
  assert.equal((await getActiveBrandTemplate(SHOP_A)).version, v2.version);

  // The old version is still readable, and still renders what it always did.
  const historical = await getBrandTemplateVersion(SHOP_A, v1.version);
  assert.equal(renderBrandEmail(historical, slotValuesForCampaign(draft, historical.brand)), sentHtml);
  assert.ok(sentHtml.includes("#111111") && !sentHtml.includes("#eeeeee"));
});

suite("the preview is the bytes the send would use", async () => {
  await db.resetDatabase();
  const template = await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell(), brand: { brandName: "Shop A" }, approvedBy: "founder",
  });

  const preview = await api.post("/klaviyo/campaigns/preview-html", {
    shopDomain: SHOP_A, campaign: draft, brandContext: { brandName: "Shop A" },
  });
  assert.equal(preview.status, 200);
  assert.equal(preview.body.templateVersion, template.version);

  // The handoff path renders through the same FINALIZATION and the same
  // renderer. Not "similar output" — the same bytes, which is the only version
  // of this claim worth making.
  const { finalizeCampaignForRender } = require("../src/services/brandContextService");
  const direct = renderBrandEmail(template, slotValuesForCampaign(
    finalizeCampaignForRender(draft, { brandName: "Shop A" }),
    { ...template.brand, brandName: "Shop A" }
  ));
  assert.equal(preview.body.html, direct);
  assert.equal(preview.body.renderFingerprint.length, 16);
});

suite("a rendering failure blocks handoff with an actionable message", async () => {
  await db.resetDatabase();
  const preview = await api.post("/klaviyo/campaigns/preview-html", {
    shopDomain: SHOP_A, campaign: draft, brandContext: { brandName: "Shop A" },
  });
  assert.equal(preview.body.code, "brand_setup_required");
  assert.match(preview.body.error, /Configure and approve one/, "it says what to do, not just that it failed");

  await saveBrandTemplate({ shopDomain: SHOP_A, html: buildStarterShell(), approvedBy: "founder" });
  const badLink = await api.post("/klaviyo/campaigns/preview-html", {
    shopDomain: SHOP_A, campaign: { ...draft, ctaUrl: "javascript:alert(1)" },
  });
  assert.equal(badLink.status, 400);
  assert.equal(badLink.body.code, "slot_value_rejected");
  assert.equal(badLink.body.slot, "cta_url");
});

suite("a campaign freezes the exact bytes and the shell version that made them", async () => {
  await db.resetDatabase();
  const { upsertCampaign, freezeCampaignAtHandoff, getCampaign } = require("../src/services/campaignService");

  await query(`INSERT INTO clean.sync_runs (shop_domain, status) VALUES ($1, 'complete')`, [SHOP_A]);
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run)
     VALUES ('run-c', $1, 'store', '{}'::jsonb)`, [SHOP_A]
  );

  const v1 = await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell({ accentColor: "#111111" }),
    brand: { brandName: "Shop A" }, approvedBy: "founder",
  });
  const html = renderBrandEmail(v1, slotValuesForCampaign(draft, v1.brand));

  const campaign = await upsertCampaign({ shopDomain: SHOP_A, runId: "run-c", playId: "play-1" });
  await freezeCampaignAtHandoff(campaign.id, {
    approvedCopy: draft,
    renderedHtml: html,
    templateVersion: String(v1.version),
    customerIds: ["c-1"],
  });

  // A later brand version must not reach back and change what this campaign
  // sent — the frozen bytes are the record of an email that has already left.
  await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell({ accentColor: "#eeeeee" }),
    brand: { brandName: "Shop A" }, approvedBy: "founder",
  });

  const frozen = await getCampaign(campaign.id);
  assert.equal(frozen.renderedHtml, html);
  assert.equal(frozen.templateVersion, String(v1.version));
  assert.ok(frozen.renderedHtml.includes("#111111"));
  assert.ok(!frozen.renderedHtml.includes("#eeeeee"));
});

suite("one shop's shell cannot be reached through another shop's request", async () => {
  await db.resetDatabase();
  await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell({ accentColor: "#aa0000" }),
    brand: { brandName: "Shop A" }, approvedBy: "founder",
  });

  // SHOP_B has no shell of its own. It must be told to configure one, not
  // quietly handed the shell belonging to a different merchant.
  const preview = await api.post("/klaviyo/campaigns/preview-html", {
    shopDomain: SHOP_B, campaign: draft, brandContext: { brandName: "Shop B" },
  });
  assert.equal(preview.status, 409);
  assert.equal(preview.body.code, "brand_setup_required");
});

suite("an intentionally emptied paragraph stays empty in the sent email", async () => {
  await db.resetDatabase();
  const template = await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell(), brand: { brandName: "Shop A" }, approvedBy: "founder",
  });
  const { finalizeCampaignForRender } = require("../src/services/brandContextService");

  // A merchant deleting the support paragraph means they do not want one.
  // `||` treated "" as absent and refilled it with brand-voice filler — text
  // written as guidance to a copywriter, mailed to customers as body copy.
  const brandContext = {
    brandName: "Shop A",
    category: "beauty",
    messaging: { useWords: ["clean", "gentle", "daily"] },
    productLanguage: { bestSellers: [{ title: "Night Serum" }] },
  };
  const emptied = { ...draft, bodyP2: "" };

  const finalized = finalizeCampaignForRender(emptied, brandContext);
  assert.equal(finalized.bodyP2, "", "the deletion survives finalization");

  const html = renderBrandEmail(template, slotValuesForCampaign(finalized, template.brand));
  assert.ok(!html.includes("brand vocabulary"), "no filler reached the email");
  assert.ok(!html.includes("Keep the copy"));

  // An ABSENT field still gets its default — that is the difference being drawn.
  const absent = finalizeCampaignForRender({ ...draft, bodyP2: undefined }, brandContext);
  assert.ok(absent.bodyP2.length > 0);
});

suite("the handoff payload is byte-identical to the preview", async () => {
  await db.resetDatabase();
  const template = await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell(), brand: { brandName: "Shop A" }, approvedBy: "founder",
  });
  await query(`INSERT INTO clean.sync_runs (shop_domain, status) VALUES ($1, 'complete')`, [SHOP_A]);
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run, input_provenance, sync_run_id)
     VALUES ('run-p', $1, 'store', '{}'::jsonb, 'verified', (SELECT id FROM clean.sync_runs WHERE shop_domain = $1))`,
    [SHOP_A]
  );

  const emptied = { ...draft, play_id: "play-1", bodyP2: "" };
  const preview = await api.post("/klaviyo/campaigns/preview-html", {
    shopDomain: SHOP_A, campaign: emptied,
  });
  assert.equal(preview.status, 200);

  // Reproduce the handoff's own rendering path with the same inputs. It applies
  // the SAME finalization now; previously it applied brand-copy defaults the
  // preview never saw, so these bytes differed.
  const { finalizeCampaignForRender } = require("../src/services/brandContextService");
  const { buildBrandContext } = require("../src/services/brandContextService");
  const { getEngineInput } = require("../src/services/shopifyRepository");
  const brandContext = buildBrandContext(await getEngineInput(SHOP_A));
  const handoffHtml = renderBrandEmail(template, slotValuesForCampaign(
    finalizeCampaignForRender(emptied, brandContext),
    { ...template.brand, brandName: brandContext?.brandName }
  ));
  assert.equal(handoffHtml, preview.body.html);
});

suite("a send is refused when the shell changed since the preview", async () => {
  await db.resetDatabase();
  const { upsertCampaign } = require("../src/services/campaignService");
  await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell({ accentColor: "#111111" }),
    brand: { brandName: "Shop A", ctaUrl: "https://shop-a.example/" }, approvedBy: "founder",
  });
  await query(`INSERT INTO clean.sync_runs (shop_domain, status) VALUES ($1, 'complete')`, [SHOP_A]);
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run, input_provenance, sync_run_id)
     VALUES ('run-v', $1, 'store', '{}'::jsonb, 'verified', (SELECT id FROM clean.sync_runs WHERE shop_domain = $1))`,
    [SHOP_A]
  );
  await query(
    `INSERT INTO clean.customers (id, shop_domain, email, created_at) VALUES ('c-1', $1, 'c1@example.com', NOW())`,
    [SHOP_A]
  );
  await query(
    `INSERT INTO clean.engine_audiences (run_id, audience_definition_id, play_id, materialization_status, customer_ids)
     VALUES ('run-v', 'aud-v', 'play-1', 'MATERIALIZED', $1)`,
    [["c-1"]]
  );
  const campaign = await upsertCampaign({ shopDomain: SHOP_A, runId: "run-v", playId: "play-1" });

  // The merchant reviewed version 1. A new shell is approved before they send.
  await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell({ accentColor: "#eeeeee" }),
    brand: { brandName: "Shop A", ctaUrl: "https://shop-a.example/" }, approvedBy: "founder",
  });

  const response = await api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: SHOP_A, campaignId: campaign.id, expectedRevision: campaign.revision,
    expectedTemplateVersion: 1,
    campaign: { play_id: "play-1", ...draft },
  });
  assert.equal(response.status, 409);
  assert.equal(response.body.code, "preview_out_of_date");
  assert.equal(response.body.reviewedVersion, 1);
  assert.equal(response.body.activeVersion, 2);
  assert.match(response.body.error, /Refresh the preview/);

  // Nothing was sent, and the reservation was handed back so a retry is possible.
  const { getCampaign } = require("../src/services/campaignService");
  const after = await getCampaign(campaign.id);
  assert.equal(after.frozen, false);
  assert.equal(after.handoffReservedAt, null);
});

suite("a send is refused when the rendering is not the one approved", async () => {
  await db.resetDatabase();
  const { upsertCampaign } = require("../src/services/campaignService");
  await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell(),
    brand: { brandName: "Shop A", ctaUrl: "https://shop-a.example/" }, approvedBy: "founder",
  });
  await query(`INSERT INTO clean.sync_runs (shop_domain, status) VALUES ($1, 'complete')`, [SHOP_A]);
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run, input_provenance, sync_run_id)
     VALUES ('run-f', $1, 'store', '{}'::jsonb, 'verified', (SELECT id FROM clean.sync_runs WHERE shop_domain = $1))`,
    [SHOP_A]
  );
  await query(
    `INSERT INTO clean.customers (id, shop_domain, email, created_at) VALUES ('c-1', $1, 'c1@example.com', NOW())`,
    [SHOP_A]
  );
  await query(
    `INSERT INTO clean.engine_audiences (run_id, audience_definition_id, play_id, materialization_status, customer_ids)
     VALUES ('run-f', 'aud-f', 'play-1', 'MATERIALIZED', $1)`,
    [["c-1"]]
  );
  const campaign = await upsertCampaign({ shopDomain: SHOP_A, runId: "run-f", playId: "play-1" });

  const response = await api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: SHOP_A, campaignId: campaign.id, expectedRevision: campaign.revision,
    expectedRenderFingerprint: "0000000000000000",
    campaign: { play_id: "play-1", ...draft },
  });
  assert.equal(response.status, 409);
  assert.equal(response.body.code, "preview_out_of_date");
  assert.match(response.body.error, /not the one that was previewed/);
});

suite("a campaign with nowhere to send is refused, not given an empty button", async () => {
  await db.resetDatabase();
  const template = await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell(), brand: { brandName: "Shop A" }, approvedBy: "founder",
  });

  // No campaign destination and no shop default.
  const { ctaUrl, ...noDestination } = draft;
  assert.throws(
    () => renderBrandEmail(template, slotValuesForCampaign(noDestination, template.brand)),
    (error) => {
      assert.equal(error.name, "MissingDestination");
      assert.equal(error.code, "missing_destination");
      assert.match(error.message, /Set where its button should send/);
      return true;
    }
  );

  const preview = await api.post("/klaviyo/campaigns/preview-html", {
    shopDomain: SHOP_A, campaign: noDestination,
  });
  assert.equal(preview.status, 400);
  assert.equal(preview.body.code, "missing_destination");

  // The campaign's own destination satisfies it...
  const withCampaignUrl = renderBrandEmail(template, slotValuesForCampaign(
    { ...noDestination, destinationUrl: "https://shop-a.example/collections/new" }, template.brand
  ));
  assert.ok(withCampaignUrl.includes("https://shop-a.example/collections/new"));
  assert.ok(!withCampaignUrl.includes('href=""'));

  // ...and so does the shop-level default.
  const withBrandDefault = renderBrandEmail(template, slotValuesForCampaign(
    noDestination, { ...template.brand, ctaUrl: "https://shop-a.example/" }
  ));
  assert.ok(withBrandDefault.includes('href="https://shop-a.example/"'));
});

suite("the campaign destination persists and freezes with the send", async () => {
  await db.resetDatabase();
  const { upsertCampaign, getCampaign, freezeCampaignAtHandoff, updateCampaign } = require("../src/services/campaignService");
  await query(`INSERT INTO clean.sync_runs (shop_domain, status) VALUES ($1, 'complete')`, [SHOP_A]);
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run)
     VALUES ('run-d', $1, 'store', '{}'::jsonb)`, [SHOP_A]
  );

  const created = await upsertCampaign({
    shopDomain: SHOP_A, runId: "run-d", playId: "play-1",
    destinationUrl: "https://shop-a.example/collections/restock",
  });
  assert.equal(created.destinationUrl, "https://shop-a.example/collections/restock");

  const reloaded = await getCampaign(created.id);
  assert.equal(reloaded.destinationUrl, "https://shop-a.example/collections/restock");

  await freezeCampaignAtHandoff(created.id, { approvedCopy: draft, customerIds: ["c-1"] });
  // The destination is part of what was sent, so it stops being editable.
  await assert.rejects(
    () => updateCampaign(created.id, { destinationUrl: "https://elsewhere.example/" }),
    { name: "CampaignFrozen" }
  );
});

suite("a missing logo or product image omits its block rather than breaking it", async () => {
  await db.resetDatabase();
  const template = await saveBrandTemplate({
    shopDomain: SHOP_A, html: buildStarterShell({ showLogo: true }),
    brand: { brandName: "Shop A", ctaUrl: "https://shop-a.example/" }, approvedBy: "founder",
  });

  // No logo configured, no featured product. Rendering src="" would show a
  // broken-image icon in most clients — in an email already approved.
  const html = renderBrandEmail(template, slotValuesForCampaign(
    { bodyH2: "Headline", bodyP1: "Body", cta: "Shop" }, template.brand
  ));
  assert.ok(!html.includes('src=""'), "no empty image sources");
  assert.ok(!html.includes("<img"), "the image blocks are omitted entirely");

  const withBoth = renderBrandEmail(template, slotValuesForCampaign(
    { ...draft, ctaUrl: "https://shop-a.example/" },
    { ...template.brand, logoUrl: "https://cdn.shop-a.example/logo.png" }
  ));
  assert.ok(withBoth.includes("logo.png") && withBoth.includes("serum.jpg"));
});
