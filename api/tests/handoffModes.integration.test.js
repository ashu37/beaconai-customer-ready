const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");
const { startFakeKlaviyo } = require("./helpers/fakeKlaviyo");
const { runSync } = require("../src/services/syncService");
const { getCampaign, upsertCampaign, updateCampaign } = require("../src/services/campaignService");
const { saveBrandTemplate } = require("../src/services/brandEmailTemplateService");
const { buildStarterShell } = require("../src/services/brandEmailRenderer");
const { klaviyoCampaignUrl } = require("../src/services/klaviyoClient");

// The two handoff modes. "Finish design in Klaviyo" creates the draft without a
// BeaconAI email, so it must not need a design or a preview — and must keep every
// other safeguard the rendered-email handoff has.

const SHOP = "modes-shop.myshopify.com";
const PLAY = "play-winback";
const COPY = {
  play_id: PLAY,
  play_name: "Bring back lapsed customers",
  subject: "It's been a little while",
  previewText: "Take another look around the shop.",
  bodyH2: "Take another look",
  bodyP1: "A few picks worth a look.",
  cta: "Take a look",
};

let api;
test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

async function seedCampaign({ provenance = "verified", withKlaviyoKey = true, withDesign = false } = {}) {
  await db.resetDatabase();
  const sync = await runSync({
    shopDomain: SHOP, accessToken: "t", shopifyScope: "read_orders,read_all_orders",
    fetchData: async () => db.shopifyPayload({ orders: db.ordersSpanning(200) }),
  });
  await query(
    `INSERT INTO clean.engine_run_snapshots
       (run_id, shop_domain, store_id, engine_run, sync_run_id, input_provenance)
     VALUES ('run-1', $1, 'store', '{}'::jsonb, $2, $3)`,
    // An unverified run is one with no verified sync behind it.
    provenance === "verified" ? [SHOP, sync.syncRunId, "verified"] : [SHOP, null, null]
  );
  const ids = Array.from({ length: 40 }, (_, i) => `c-${i + 1}`);
  for (const id of ids) {
    await query(
      `INSERT INTO clean.customers (id, shop_domain, email, created_at)
       VALUES ($1, $2, $3, NOW()) ON CONFLICT (id) DO NOTHING`,
      [id, SHOP, `${id}@example.com`]
    );
  }
  await query(
    `INSERT INTO clean.engine_audiences (run_id, audience_definition_id, play_id, materialization_status, customer_ids)
     VALUES ('run-1', 'aud-1', $1, 'MATERIALIZED', $2)`,
    [PLAY, ids]
  );
  if (withDesign) {
    await saveBrandTemplate({
      shopDomain: SHOP, html: buildStarterShell(),
      brand: { brandName: "Modes Shop", ctaUrl: "https://modes-shop.example/collections/all" },
      approvedBy: "founder",
    });
  }
  if (withKlaviyoKey) await connectKlaviyo();
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY, status: "approved" });
  // The merchant's holdout choice, saved before handoff.
  return updateCampaign(created.id, { holdoutPct: 0.25, expectedRevision: created.revision });
}

async function connectKlaviyo() {
  await query(
    `INSERT INTO clean.connections (shop_domain, klaviyo_private_key) VALUES ($1, 'pk_test')
     ON CONFLICT (shop_domain) DO UPDATE SET klaviyo_private_key = EXCLUDED.klaviyo_private_key`,
    [SHOP]
  );
}

function handOff(campaign, extra = {}) {
  return api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: SHOP, campaignId: campaign.id, expectedRevision: campaign.revision,
    campaign: COPY, handoffMode: "klaviyo_design", ...extra,
  });
}

async function recipients(campaignId) {
  const { rows } = await query(
    `SELECT arm, COUNT(*)::int AS n FROM clean.campaign_recipients WHERE campaign_id = $1 GROUP BY arm ORDER BY arm`,
    [campaignId]
  );
  return Object.fromEntries(rows.map((r) => [r.arm, r.n]));
}

suite("finish in Klaviyo: a draft without a design, a preview or a template", async () => {
  // No BeaconAI design is configured for this store at all.
  const campaign = await seedCampaign({ withDesign: false });
  const fake = await startFakeKlaviyo();
  try {
    const response = await handOff(campaign);
    assert.equal(response.status, 200, JSON.stringify(response.body));
    assert.equal(response.body.handoffMode, "klaviyo_design");

    // The draft carries the audience and envelope, and nothing BeaconAI designed.
    assert.deepEqual(fake.calls(), [
      "GET /accounts",
      "POST /lists",
      "POST /profile-bulk-import-jobs",
      "POST /campaigns",
    ]);
    const attrs = fake.requests.find((r) => r.path === "/campaigns").body.data.attributes;
    assert.deepEqual(attrs.audiences.included, ["list-1"]);
    assert.equal(attrs.name, "BeaconAI - Bring back lapsed customers", "the searchable name");
    const content = attrs["campaign-messages"].data[0].attributes.definition.content;
    assert.equal(content.subject, COPY.subject);
    assert.equal(content.preview_text, COPY.previewText);
    assert.equal(content.from_email, "hello@test-shop.example");

    // The saved holdout was applied: only the email group is imported, and both
    // groups are recorded for measurement.
    const arms = await recipients(campaign.id);
    const imported = fake.requests.find((r) => r.path === "/profile-bulk-import-jobs")
      .body.data.attributes.profiles.data.length;
    assert.equal(arms.treated, imported);
    assert.ok(arms.holdout > 0, `a 25% holdout on 40 customers holds some back: ${JSON.stringify(arms)}`);
    assert.equal(response.body.holdout.pct, 0.25);

    const after = await getCampaign(campaign.id);
    assert.equal(after.frozen, true);
    assert.equal(after.handoffMode, "klaviyo_design");
    assert.equal(after.renderedHtml, null, "no BeaconAI email was sent, so none is recorded as sent");
    assert.equal(after.templateVersion, null);
    assert.equal(after.approvedCopy.subject, COPY.subject, "the handoff suggestion is kept");
    assert.equal(after.klaviyoCampaignId, "camp-1");
    assert.equal(after.deliveryState, "created", "created, never sent: sending happens in Klaviyo");
    assert.equal(after.providerCampaignName, "BeaconAI - Bring back lapsed customers");

    const delivery = await api.get(`/campaigns/${campaign.id}/delivery`, { session: SHOP });
    assert.equal(delivery.body.delivery.providerCampaignUrl, "https://www.klaviyo.com/campaign/camp-1/wizard/1");

    const original = await api.get(`/campaigns/${campaign.id}/original`, { session: SHOP });
    assert.equal(original.body.handoffMode, "klaviyo_design");
    assert.equal(original.body.renderedHtml, null);
  } finally {
    await fake.close();
  }
});

suite("the rendered-email mode still requires its preview and design", async () => {
  const campaign = await seedCampaign({ withDesign: false });
  const fake = await startFakeKlaviyo();
  try {
    // No mode named: the original mode, with its original refusal.
    for (const extra of [{ handoffMode: undefined }, { handoffMode: "rendered_email" }]) {
      const response = await handOff(campaign, extra);
      assert.equal(response.status, 409, JSON.stringify(response.body));
      assert.equal(response.body.code, "preview_required");
    }
    // A preview binding without a design to render it from is still refused.
    const noDesign = await handOff(campaign, {
      handoffMode: "rendered_email", expectedTemplateVersion: 1, expectedRenderFingerprint: "abc",
    });
    assert.equal(noDesign.status, 409);
    assert.equal(noDesign.body.code, "brand_setup_required");
    assert.deepEqual(fake.writes(), [], "nothing reached Klaviyo");
    const after = await getCampaign(campaign.id);
    assert.equal(after.frozen, false);
    assert.equal(after.handoffReservedAt, null, "the refusal handed the reservation back");
  } finally {
    await fake.close();
  }
});

suite("an unknown handoff mode is refused before anything is reserved", async () => {
  const campaign = await seedCampaign();
  const fake = await startFakeKlaviyo();
  try {
    const response = await handOff(campaign, { handoffMode: "figma" });
    assert.equal(response.status, 400);
    assert.equal(response.body.code, "invalid_handoff_mode");
    assert.deepEqual(fake.calls(), []);
    assert.deepEqual(await recipients(campaign.id), {});
    assert.equal((await getCampaign(campaign.id)).handoffReservedAt, null);
  } finally {
    await fake.close();
  }
});

suite("finish in Klaviyo keeps the provenance, revision and ownership checks", async () => {
  // Unverified input.
  let campaign = await seedCampaign({ provenance: "legacy_unverified" });
  let fake = await startFakeKlaviyo();
  try {
    const response = await handOff(campaign);
    assert.equal(response.status, 409);
    assert.equal(response.body.blocked, "unverified_input");
    assert.deepEqual(fake.calls(), []);
  } finally {
    await fake.close();
  }

  // A revision the merchant did not review.
  campaign = await seedCampaign();
  fake = await startFakeKlaviyo();
  try {
    const response = await handOff(campaign, { expectedRevision: campaign.revision - 1 });
    assert.equal(response.status, 409, JSON.stringify(response.body));
    assert.deepEqual(fake.writes(), []);
    assert.equal((await getCampaign(campaign.id)).frozen, false);

    // Another store's session.
    const other = await api.post("/klaviyo/campaigns/from-engine", {
      shopDomain: SHOP, campaignId: campaign.id, expectedRevision: campaign.revision,
      campaign: COPY, handoffMode: "klaviyo_design",
    }, { session: "someone-else.myshopify.com" });
    assert.ok([403, 404].includes(other.status), `refused: ${other.status}`);
    assert.deepEqual(fake.writes(), []);
  } finally {
    await fake.close();
  }
});

suite("finish in Klaviyo creates one draft, and never touches it again", async () => {
  const campaign = await seedCampaign();
  const fake = await startFakeKlaviyo();
  try {
    const first = await handOff(campaign);
    assert.equal(first.status, 200, JSON.stringify(first.body));
    const before = fake.requests.length;

    // A second click, and a stale tab quoting the revision it last read. Neither
    // may create a second draft or write over what the merchant does in Klaviyo.
    const again = await handOff(await getCampaign(campaign.id));
    const stale = await handOff(campaign);
    assert.equal(again.status, 409);
    assert.equal(stale.status, 409);
    assert.equal(fake.requests.length, before, "Klaviyo was not contacted again");
    assert.equal(fake.calls().filter((c) => c === "POST /campaigns").length, 1);
  } finally {
    await fake.close();
  }
});

suite("finish in Klaviyo: an uncertain provider outcome stays locked", async () => {
  const campaign = await seedCampaign();
  const fake = await startFakeKlaviyo({ failAt: { "POST /campaigns": 500 } });
  try {
    const response = await handOff(campaign);
    assert.equal(response.status, 500);
    assert.equal(response.body.providerStage, "campaign");
    assert.equal(response.body.reconciliationRequired, true);

    const after = await getCampaign(campaign.id);
    assert.equal(after.deliveryState, "uncertain");
    assert.ok(after.handoffReservedAt, "kept: a campaign may exist in Klaviyo");

    const before = fake.requests.length;
    const retry = await handOff(after);
    assert.equal(retry.status, 409);
    assert.equal(fake.requests.length, before, "no blind retry");
  } finally {
    await fake.close();
  }
});

suite("finish in Klaviyo: a failure before Klaviyo is contacted can be retried", async () => {
  const campaign = await seedCampaign({ withKlaviyoKey: false });
  const fake = await startFakeKlaviyo();
  try {
    const response = await handOff(campaign);
    assert.equal(response.status, 500);
    assert.equal(response.body.providerStage, "not_started");
    assert.deepEqual(fake.calls(), []);

    const after = await getCampaign(campaign.id);
    assert.equal(after.deliveryState, "failed");
    assert.equal(after.handoffReservedAt, null);

    await connectKlaviyo();
    const retry = await handOff(after);
    assert.equal(retry.status, 200, JSON.stringify(retry.body));
    assert.equal((await getCampaign(campaign.id)).deliveryState, "created");
  } finally {
    await fake.close();
  }
});

test("the Klaviyo link is built only from a real campaign id", () => {
  assert.equal(klaviyoCampaignUrl("01M2K5RDG9NZGQ21Q1D9PP4HYG"), "https://www.klaviyo.com/campaign/01M2K5RDG9NZGQ21Q1D9PP4HYG/wizard/1");
  for (const bad of [null, undefined, "", "../settings", "a b", "id?x=1"]) {
    assert.equal(klaviyoCampaignUrl(bad), null, `no link for ${JSON.stringify(bad)}`);
  }
});
