const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

// Never reach the real model from a test. With no key the copywriter answers
// available:false, which is all these assertions need: whether the play was FOUND.
// Set empty rather than deleted, so a later dotenv load cannot fill it back in.
process.env.ANTHROPIC_API_KEY = "";

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");

const SHOP = "copy-scope.myshopify.com";
const OTHER_SHOP = "copy-scope-other.myshopify.com";
const PLAY = "winback_dormant_cohort";

let api;
test.before(async () => {
  if (db.available) api = await startApi();
});
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

async function seedRun({ runId, shopDomain = SHOP, playIds }) {
  const engineRun = {
    run_id: runId,
    abstain: { state: "publish", mode: null },
    data_quality_flags: [],
    recommendations: playIds.map((playId) => ({
      play_id: playId, evidence_class: "directional", evidence_source: "STORE_OBSERVED", audience: { size: 10 },
    })),
    considered: [],
    watching: [],
  };
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run, input_provenance)
     VALUES ($1, $2, 'store', $3::jsonb, 'verified')`,
    [runId, shopDomain, JSON.stringify(engineRun)]
  );
}

// A campaign from an older analysis asks for copy for its own play. Resolving the
// play against the LATEST run instead found nothing (or the newer run's version
// of the play) and cached the copy on the newer run's campaign.
suite("copy generation uses the campaign's own run when it names one", async () => {
  await db.resetDatabase();
  await seedRun({ runId: "run-old", playIds: [PLAY] });
  await seedRun({ runId: "run-new", playIds: ["discount_dependency_hygiene"] });
  await seedRun({ runId: "run-foreign", shopDomain: OTHER_SHOP, playIds: [PLAY] });

  const own = await api.post("/copy/generate", { shopDomain: SHOP, playId: PLAY, runId: "run-old" });
  assert.equal(own.status, 200);
  assert.notEqual(own.body.reason, "play_not_found", "found in the campaign's own run");

  const latest = await api.post("/copy/generate", { shopDomain: SHOP, playId: PLAY });
  assert.equal(latest.body.reason, "play_not_found", "without a run it still reads the latest, which lacks this play");

  const foreign = await api.post("/copy/generate", { shopDomain: SHOP, playId: PLAY, runId: "run-foreign" });
  assert.equal(foreign.body.reason, "play_not_found", "another shop's run is never used, and never swapped for the latest");
});
