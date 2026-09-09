const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");
const { runSync } = require("../src/services/syncService");
const { resolveCampaignAudience } = require("../src/services/campaignAudienceService");

const SHOP = "handoff-shop.myshopify.com";
const OTHER_SHOP = "handoff-other.myshopify.com";
const PLAY = "play-winback";

let api;

test.before(async () => {
  if (db.available) api = await startApi();
});
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

async function publishSync(shopDomain = SHOP) {
  return runSync({
    shopDomain,
    accessToken: "token",
    shopifyScope: "read_orders,read_all_orders",
    fetchData: async () => db.shopifyPayload({ orders: db.ordersSpanning(200) }),
  });
}

// A run with one materialized audience for PLAY.
async function seedRun({ runId, shopDomain = SHOP, syncRunId = null, provenance = "verified", members = [] }) {
  await query(
    `INSERT INTO clean.engine_run_snapshots
       (run_id, shop_domain, store_id, engine_run, sync_run_id, input_provenance)
     VALUES ($1, $2, 'store', '{}'::jsonb, $3, $4)`,
    [runId, shopDomain, syncRunId, provenance]
  );
  await query(
    `INSERT INTO clean.engine_audiences
       (run_id, audience_definition_id, play_id, materialization_status, customer_ids)
     VALUES ($1, $2, $3, 'MATERIALIZED', $4)`,
    [runId, `aud-${runId}`, PLAY, members]
  );
}

async function seedCustomers(ids) {
  for (const id of ids) {
    await query(
      `INSERT INTO clean.customers (id, shop_domain, email, created_at)
       VALUES ($1, $2, $3, NOW())
       ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email`,
      [id, SHOP, `${id}@example.com`]
    );
  }
}

suite("the audience comes from the run that was verified, not the newest one", async () => {
  await db.resetDatabase();
  const sync = await publishSync();
  await seedCustomers(["old-1", "old-2", "new-1", "new-2", "new-3"]);

  // An older, verified run the merchant is sending from...
  await seedRun({ runId: "run-old", syncRunId: sync.syncRunId, members: ["old-1", "old-2"] });
  // ...and a newer run with completely different membership.
  await seedRun({ runId: "run-new", syncRunId: sync.syncRunId, members: ["new-1", "new-2", "new-3"] });

  // Regression: audience resolution used to ignore the pinned run and take the
  // newest, so sending an older campaign silently used today's membership.
  const pinned = await resolveCampaignAudience(SHOP, { play_id: PLAY }, { runId: "run-old" });
  assert.equal(pinned.runId, "run-old");
  assert.deepEqual(pinned.recipients.map((r) => r.customerId).sort(), ["old-1", "old-2"]);

  const unpinned = await resolveCampaignAudience(SHOP, { play_id: PLAY });
  assert.equal(unpinned.runId, "run-new", "without a pin it still falls back to the newest run");
});

suite("a pinned run is never substituted for the latest", async () => {
  await db.resetDatabase();
  const sync = await publishSync();
  await seedRun({ runId: "run-present", syncRunId: sync.syncRunId, members: ["c-1"] });

  // The pinned run has no audience for this play. The answer is "no audience",
  // not "here is another run's".
  const result = await resolveCampaignAudience(SHOP, { play_id: PLAY }, { runId: "run-absent" });
  assert.equal(result.materialized, false);
  assert.equal(result.reason, "no_audience_for_play");
  assert.equal(result.runId, "run-absent");
});

suite("a verified run id cannot authorize an unverified run's audience", async () => {
  await db.resetDatabase();
  const sync = await publishSync();
  await seedCustomers(["legacy-1"]);
  // Newest run is legacy_unverified; an older run IS verified.
  await seedRun({ runId: "run-verified", syncRunId: sync.syncRunId, members: ["legacy-1"] });
  await seedRun({ runId: "run-unverified", syncRunId: null, provenance: null, members: ["legacy-1"] });

  // The exact attack the split created: quote the verified run, get the
  // unverified (newest) run's membership. Both must now refer to run-verified.
  const preview = await api.post("/campaigns/audience/preview", {
    shopDomain: SHOP,
    campaign: { play_id: PLAY, run_id: "run-verified" },
  });
  assert.equal(preview.status, 200);
  assert.equal(preview.body.runId, "run-verified");
  assert.equal(preview.body.inputProvenance, "verified");
  assert.equal(preview.body.sendable, true);

  // And quoting the unverified run is refused rather than silently upgraded.
  const blocked = await api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: SHOP,
    campaign: { play_id: PLAY, run_id: "run-unverified" },
  });
  assert.equal(blocked.status, 409);
  assert.equal(blocked.body.blocked, "unverified_input");
  assert.equal(blocked.body.inputProvenance, "legacy_unverified");
});

suite("handoff refuses a run belonging to another store", async () => {
  await db.resetDatabase();
  const mine = await publishSync(SHOP);
  const theirs = await publishSync(OTHER_SHOP);
  await seedRun({ runId: "run-mine", shopDomain: SHOP, syncRunId: mine.syncRunId, members: ["c-1"] });
  await seedRun({ runId: "run-theirs", shopDomain: OTHER_SHOP, syncRunId: theirs.syncRunId, members: ["c-9"] });

  // run-theirs is genuinely verified — for a different shop. Run ids arrive in
  // the request body, so without the shop check it would authorize this send.
  const response = await api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: SHOP,
    campaign: { play_id: PLAY, run_id: "run-theirs" },
  });
  assert.equal(response.status, 409);
  assert.equal(response.body.inputProvenance, "foreign_run");

  const preview = await api.post("/campaigns/audience/preview", {
    shopDomain: SHOP,
    campaign: { play_id: PLAY, run_id: "run-theirs" },
  });
  assert.equal(preview.body.sendable, false);
  assert.equal(preview.body.inputProvenance, "foreign_run");
});

suite("a blocked handoff writes no campaign row", async () => {
  await db.resetDatabase();
  await publishSync();
  await seedCustomers(["c-1"]);
  await seedRun({ runId: "run-fixture", syncRunId: null, provenance: "fixture", members: ["c-1"] });

  const response = await api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: SHOP,
    campaign: { play_id: PLAY, run_id: "run-fixture" },
  });
  assert.equal(response.status, 409);
  assert.match(response.body.error, /sample data/);

  // The check runs before the audience is split or persisted, so nothing is
  // left half-made for a merchant to find later.
  const campaigns = await query(`SELECT count(*)::int AS n FROM clean.campaigns WHERE shop_domain = $1`, [SHOP]);
  assert.equal(campaigns.rows[0].n, 0);
  const recipients = await query(`SELECT count(*)::int AS n FROM clean.campaign_recipients`);
  assert.equal(recipients.rows[0].n, 0);
});
