const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

// Never reach the real model: the cached path answers before any model call.
process.env.ANTHROPIC_API_KEY = "";

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");
const { upsertCampaign } = require("../src/services/campaignService");

// Generated copy saved BEFORE the claim rules must not reach a draft just because
// it was saved: both routes that serve stored copy check it on the way out.
const SHOP = "copy-serving.myshopify.com";
const PLAY = "cohort_journey_first_to_second";
const CLAIMING_COPY = {
  copy: {
    subject_variants: ["You picked up the Hyaluronic Daily Moisturizer", "A few picks for your next order"],
    preview_text: "A few picks worth a look",
    headline: "Explore Niacinamide Pore Serum",
    body: "You picked up the Hyaluronic Daily Moisturizer. No pilling, no wait time.",
    support: "",
    cta: "Shop the serum",
    rationale: "",
    featured_product_id: "p1",
    featured_product: { title: "Hyaluronic Daily Moisturizer", imageUrl: "https://cdn.example/moisturizer.png" },
  },
  fallback_slots: [],
  playbook_version: "test",
};

let api;
test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

async function seed() {
  await db.resetDatabase();
  const engineRun = {
    run_id: "run-copy", abstain: { state: "publish", mode: null }, data_quality_flags: [], considered: [], watching: [],
    recommendations: [{ play_id: PLAY, evidence_source: "STORE_OBSERVED", audience: { size: 413, definition: "first-time buyers whose only order is 30-90 days before anchor" } }],
  };
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run, input_provenance)
     VALUES ('run-copy', $1, 'store', $2::jsonb, 'verified')`,
    [SHOP, JSON.stringify(engineRun)]
  );
  await query(`INSERT INTO clean.products (id, shop_domain, title) VALUES ('p1', $1, 'Hyaluronic Daily Moisturizer')`, [SHOP]);
  return upsertCampaign({
    shopDomain: SHOP, runId: "run-copy", playId: PLAY, status: "draft", templateId: "beacon-second-purchase",
    copy: CLAIMING_COPY, draftEdits: { cta: "You picked up something great" },
  });
}

suite("the campaign list serves stored copy through the claim rules, leaving merchant edits alone", async () => {
  await seed();
  const response = await api.get(`/campaigns/${SHOP}`);
  assert.equal(response.status, 200);
  const [campaign] = response.body.campaigns;
  assert.deepEqual(campaign.copy.copy.subject_variants, ["A few picks for your next order"]);
  assert.equal(campaign.copy.copy.body, "", "blanked, so the draft uses its starting template");
  assert.equal(campaign.copy.copy.headline, "Explore Niacinamide Pore Serum");
  assert.deepEqual(campaign.draftEdits, { cta: "You picked up something great" }, "the merchant's own words are theirs");
  // Saved without a name: served with the play's merchant-facing name, not its id.
  assert.equal(campaign.displayName, "Turn first-time buyers into repeat buyers");
  // A real product of this store stays featured, image and all.
  assert.equal(campaign.copy.copy.featured_product_id, "p1");
  assert.deepEqual(campaign.copy.copy.featured_product, { title: "Hyaluronic Daily Moisturizer", imageUrl: "https://cdn.example/moisturizer.png" });
});

suite("cached copy is checked again before it is returned", async () => {
  await seed();
  const response = await api.post("/copy/generate", { shopDomain: SHOP, playId: PLAY, templateId: "beacon-second-purchase" });
  assert.equal(response.status, 200, JSON.stringify(response.body));
  assert.equal(response.body.cached, true);
  assert.ok(!response.body.copy.subject_variants.some((s) => /picked up/i.test(s)));
  assert.doesNotMatch(response.body.copy.body, /picked up|pilling/i);
});
