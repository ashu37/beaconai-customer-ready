const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");
const { upsertCampaign, recordRecipients, freezeCampaignAtHandoff } = require("../src/services/campaignService");
const { transitionDelivery } = require("../src/services/deliveryStateService");
const { measureCampaign, summarizeCampaign, assessWindow } = require("../src/services/measurementService");

// Ticket G: the per-window Results response, against RESULTS_UI_SPEC §5–§8.
// Provider states are reached through Ticket D's real transitions.
const SHOP = "results-g.myshopify.com";
const OTHER = "other-g.myshopify.com";
const DAY = 86400000;
const ago = (days) => new Date(Date.now() - days * DAY);
const FRESH = () => ({ lastSuccessfulSyncAt: new Date(), ordersCoveredThrough: new Date() });

let api;
test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

const people = (...ids) => ids.map((id) => ({ customerId: id, email: `${id}@example.invalid` }));

async function seedRun(runId = "run-g", engineRun = {}, shop = SHOP) {
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run)
     VALUES ($1, $2, 'store', $3) ON CONFLICT (run_id) DO NOTHING`, [runId, shop, engineRun]
  );
}
async function seedCampaign(playId, { runId = "run-g", shop = SHOP } = {}) {
  await seedRun(runId, {}, shop);
  return upsertCampaign({ shopDomain: shop, runId, playId, displayName: `Saved name for ${playId}` });
}
async function handOff(id, extra = {}) {
  await transitionDelivery(id, "creating");
  await transitionDelivery(id, "created", { provider: "klaviyo", providerCampaignId: `kl-${id}` });
  await freezeCampaignAtHandoff(id, extra);
}
async function confirmSend(id, at, extra = {}) {
  await transitionDelivery(id, "sent", { providerSentAt: at, ...extra }, { fromProvider: true });
}
async function sentCampaign(playId, at, { treated, held, count } = {}) {
  const c = await seedCampaign(playId);
  await recordRecipients(c.id, { treated: people(...treated), holdout: people(...held) });
  await handOff(c.id);
  await confirmSend(c.id, at, count == null ? {} : { providerSentCount: count });
  return c;
}
let seq = 0;
async function order(customerId, at, total, shop = SHOP) {
  await query(
    `INSERT INTO clean.orders (id, shop_domain, customer_id, email, processed_at, created_at, total_price, test)
     VALUES ($1, $2, $3, $4, $5, $5, $6, false)`,
    [`g-${seq += 1}`, shop, customerId, `${customerId}@example.invalid`, at, total]
  );
}
// Publishes a sync and makes it the active one, as a real sync would.
async function activeSync({ startedAt, publishedAt }, shop = SHOP) {
  const { rows } = await query(
    `INSERT INTO clean.sync_runs (shop_domain, status, started_at, finished_at, published_at)
     VALUES ($1, 'complete', $2, $3, $3) RETURNING id`, [shop, startedAt, publishedAt]
  );
  await query(
    `INSERT INTO clean.active_sync (shop_domain, sync_run_id, published_at, started_at) VALUES ($1, $2, $3, $4)
     ON CONFLICT (shop_domain) DO UPDATE SET sync_run_id = EXCLUDED.sync_run_id,
       published_at = EXCLUDED.published_at, started_at = EXCLUDED.started_at`,
    [shop, rows[0].id, publishedAt, startedAt]
  );
  return { syncRunId: rows[0].id, lastSuccessfulSyncAt: publishedAt, ordersCoveredThrough: startedAt };
}
const win = (summary, days) => summary.windows.find((w) => w.windowDays === days);

suite("unique purchasers are counted separately from orders", async () => {
  await db.resetDatabase();
  const c = await sentCampaign("play-p", ago(40), { treated: ["a", "b", "c"], held: ["h", "i"] });
  // Three orders from one customer are one purchaser.
  await order("a", ago(35), 10); await order("a", ago(30), 10); await order("a", ago(25), 10);
  await order("b", ago(20), 10);
  await order("h", ago(30), 10);

  const w30 = win(await measureCampaign(c.id, { source: FRESH() }), 30);
  assert.deepEqual(
    { customers: w30.assigned.customers, purchasers: w30.assigned.purchasers, orders: w30.assigned.orders },
    { customers: 3, purchasers: 2, orders: 4 },
  );
  assert.equal(w30.heldBack.purchasers, 1);
  assert.equal(w30.heldBack.orders, 1);
});

suite("every figure, date and assessment follows its own window", async () => {
  await db.resetDatabase();
  const sent = ago(70);
  // A real, current sync: coverage is judged against the sync a calculation read.
  const current = await activeSync({ startedAt: new Date(), publishedAt: new Date() });
  const c = await sentCampaign("play-w", sent, { treated: ["a", "b"], held: ["h", "i"] });
  await order("a", ago(60), 100); // day 10: in 30, 60, 90
  await order("a", ago(25), 50);  // day 45: in 60 and 90, not 30
  await order("h", ago(60), 20);

  const summary = await measureCampaign(c.id, { source: current });
  const [w30, w60, w90] = [30, 60, 90].map((d) => win(summary, d));

  assert.equal(w30.start, sent.toISOString());
  assert.equal(w30.end, new Date(sent.getTime() + 30 * DAY).toISOString());
  assert.equal(w60.end, new Date(sent.getTime() + 60 * DAY).toISOString());
  assert.equal(w30.assigned.revenue, 100);
  assert.equal(w60.assigned.revenue, 150, "the 60-day window has its own figures");
  assert.equal(w30.complete, true);
  assert.equal(w60.complete, true);
  assert.equal(w90.complete, false);
  assert.equal(w90.daysElapsed, 70);
  assert.equal(w90.assessment.state, "measuring");
  assert.equal(w90.comparison, null, "no comparison while measuring");
  assert.ok(w90.assigned.revenuePerCustomer > 0, "early observation figures are still present");
  // Complete, adequate, but no campaign assessment policy is configured.
  assert.equal(w30.assessment.state, "assessment_policy_pending");
  assert.equal(w30.comparison, null);
});

suite("recalculating over old store data is a fresh calculation, not fresh data", async () => {
  await db.resetDatabase();
  await activeSync({ startedAt: ago(3.1), publishedAt: ago(3) });
  await sentCampaign("play-s", ago(40), { treated: ["a", "b"], held: ["h", "i"] });
  await order("a", ago(35), 30); await order("h", ago(35), 20);

  const { body } = await api.get(`/results/${SHOP}`);
  const w30 = win(body.results[0], 30);
  // Measured just now, on read…
  assert.ok(Date.now() - new Date(w30.calculatedAt).getTime() < 60000);
  assert.equal(w30.calculationStale, false);
  // …over a store last synced three days ago.
  assert.equal(body.source.stale, true);
  assert.equal(body.source.reason, "sync_older_than_24h");
  assert.equal(body.results[0].source.stale, true);
});

suite("a completed window is not assessed until orders are synced through its end", async () => {
  await db.resetDatabase();
  const c = await sentCampaign("play-c", ago(40), { treated: ["a", "b"], held: ["h", "i"] });
  await order("a", ago(35), 30); await order("h", ago(35), 20);

  // No successful sync at all.
  let { body } = await api.get(`/results/${SHOP}`);
  assert.equal(win(body.results[0], 30).assessment.state, "awaiting_order_data");
  assert.deepEqual(win(body.results[0], 30).assessment.reasons, ["no_successful_sync"]);

  // A sync whose orders stop 20 days ago; the 30-day window ended 10 days ago.
  await activeSync({ startedAt: ago(20), publishedAt: ago(20) });
  ({ body } = await api.get(`/results/${SHOP}`));
  const w30 = win(body.results.find((r) => r.campaignId === c.id), 30);
  assert.equal(w30.assessment.state, "awaiting_order_data");
  assert.deepEqual(w30.assessment.reasons, ["orders_not_synced_through_window_end"]);
  assert.equal(w30.comparison, null);
});

suite("customers the provider didn't deliver to stay in the assigned group", async () => {
  await db.resetDatabase();
  await activeSync({ startedAt: new Date(), publishedAt: new Date() });
  const c = await sentCampaign("play-u", ago(5), { treated: ["a", "b", "c"], held: ["h", "i"], count: 1 });
  const { body } = await api.get(`/results/${SHOP}`);
  const result = body.results.find((r) => r.campaignId === c.id);
  assert.deepEqual(result.assignment, { assigned: 3, heldBack: 2 });
  assert.equal(result.delivery.providerSentCount, 1, "the provider count is carried separately");
  assert.equal(win(result, 30).assigned.customers, 3);
  assert.equal(result.displayName, "Saved name for play-u");
});

suite("a group with no purchasers is insufficient data, with figures still shown", async () => {
  await db.resetDatabase();
  await activeSync({ startedAt: new Date(), publishedAt: new Date() });
  await sentCampaign("play-i", ago(40), { treated: ["a", "b"], held: ["h", "i"] });
  await order("a", ago(35), 30);
  const { body } = await api.get(`/results/${SHOP}`);
  const w30 = win(body.results[0], 30);
  assert.equal(w30.assessment.state, "insufficient_data");
  assert.deepEqual(w30.assessment.reasons, ["no_purchasers_in_a_group"]);
  assert.equal(w30.heldBack.purchasers, 0);
  assert.equal(w30.comparison, null);
});

// The assessment, rule by rule. A policy is passed explicitly: none is
// configured in the product until the statistical review sets one.
const arm = (n, purchasers, revenue, revenueSq, orders = purchasers) =>
  ({ n_customers: n, n_purchasers: purchasers, n_orders: orders, revenue, revenue_sq: revenueSq });
const POLICY = { minCustomersPerArm: 20, minPurchasersPerArm: 5, criticalValue: 1.96 };
const base = { complete: true, end: ago(10), source: { ordersCoveredThrough: new Date() } };

suite("assessment: nothing is judged early, without coverage, or on missing purchasers", () => {
  const T = arm(100, 30, 1000, 50000); const H = arm(50, 15, 450, 24050);
  assert.equal(assessWindow({ ...base, complete: false, assigned: T, heldBack: H, policy: POLICY }).state, "measuring");
  assert.equal(assessWindow({ ...base, assigned: T, heldBack: null, policy: POLICY }).state, "no_holdout");
  assert.equal(assessWindow({ ...base, source: { ordersCoveredThrough: ago(20) }, assigned: T, heldBack: H, policy: POLICY }).state, "awaiting_order_data");
  assert.equal(assessWindow({ ...base, assigned: { ...T, n_purchasers: null }, heldBack: H, policy: POLICY }).state, "not_calculated");
});

suite("assessment: only structural minimums without a policy, then policy pending", () => {
  const H = arm(50, 15, 450, 24050);
  assert.deepEqual(assessWindow({ ...base, assigned: arm(1, 1, 10, 100), heldBack: H, policy: null }).reasons, ["fewer_than_two_customers"]);
  // Ten orders from one purchaser is still one purchaser; zero is zero.
  assert.equal(assessWindow({ ...base, assigned: arm(100, 30, 1000, 50000), heldBack: arm(50, 0, 0, 0, 0), policy: null }).state, "insufficient_data");
  const pending = assessWindow({ ...base, assigned: arm(100, 1, 100, 10000, 10), heldBack: H, policy: null });
  assert.equal(pending.state, "assessment_policy_pending", "no invented floor fires between the structural minimum and a policy");
  assert.equal(pending.comparison, null);
});

suite("assessment: with a policy, floors use purchasers and the range decides", () => {
  const H = arm(50, 15, 450, 24050);
  // Ten orders, one purchaser: below a purchaser floor of five.
  const floor = assessWindow({ ...base, assigned: arm(100, 1, 100, 10000, 10), heldBack: H, policy: POLICY });
  assert.equal(floor.state, "insufficient_data");
  assert.deepEqual(floor.reasons, ["below_purchaser_floor"]);

  const higher = assessWindow({ ...base, assigned: arm(100, 60, 1000, 10000), heldBack: arm(50, 20, 250, 1250), policy: POLICY });
  assert.equal(higher.state, "higher_spending");
  assert.deepEqual(Object.keys(higher.comparison).sort(), ["criticalValue", "difference", "high", "low"], "per customer only; no total to add up");

  const lower = assessWindow({ ...base, assigned: arm(100, 60, 250 * 2, 2500 * 2), heldBack: arm(50, 20, 500, 5000), policy: POLICY });
  assert.equal(lower.state, "lower_spending");

  const unclear = assessWindow({ ...base, assigned: arm(100, 30, 1000, 50000), heldBack: H, policy: POLICY });
  assert.equal(unclear.state, "no_clear_difference");
  assert.ok(unclear.comparison.low < 0 && unclear.comparison.high > 0);
});

suite("other BeaconAI exposure is checked per window: none, unknown, present", async () => {
  await db.resetDatabase();
  await activeSync({ startedAt: new Date(), publishedAt: new Date() });
  const x = await sentCampaign("play-x", ago(70), { treated: ["a", "b"], held: ["h", "i"] });
  const exposure = async (days) => win((await api.get(`/results/${SHOP}`)).body.results.find((r) => r.campaignId === x.id), days).otherExposure;

  assert.deepEqual(await exposure(30), { status: "none", customers: 0 });

  // A failed draft sent nothing.
  const failed = await seedCampaign("play-failed");
  await recordRecipients(failed.id, { treated: people("a"), holdout: [] });
  await transitionDelivery(failed.id, "creating");
  await transitionDelivery(failed.id, "failed");
  assert.equal((await exposure(30)).status, "none");

  // A draft with no confirmed send could go out inside the window: unknown, not none.
  const draft = await seedCampaign("play-draft");
  await recordRecipients(draft.id, { treated: people("b"), holdout: [] });
  await handOff(draft.id);
  assert.equal((await exposure(30)).status, "unknown");

  // Confirmed 20 days ago: after the 30-day window closed, inside the 60-day one.
  await confirmSend(draft.id, ago(20));
  assert.equal((await exposure(30)).status, "none", "outside the 30-day window");
  assert.deepEqual(await exposure(60), { status: "present", customers: 1 });
});

suite("the original campaign is the frozen email and its originating recommendation, for the owner only", async () => {
  await db.resetDatabase();
  const card = {
    play_id: "winback_dormant_cohort", evidence_class: "directional", evidence_source: "STORE_OBSERVED",
    confidence_label: "Emerging", audience: { size: 234 },
    measurement: { metric: "reactivation_rate", observed_effect: -0.205607, n: 107, primary_window: "L56" },
    revenue_range: { p10: 400, p50: 4500, p90: 4500, source: "blend", suppressed: false },
  };
  await seedRun("run-origin", { run_id: "run-origin", recommendations: [card], considered: [] });
  const c = await upsertCampaign({ shopDomain: SHOP, runId: "run-origin", playId: "winback_dormant_cohort", displayName: "Winback" });
  await handOff(c.id, {
    approvedCopy: { subject: "We saved something for you", previewText: "Welcome back" },
    renderedHtml: "<html><body>Frozen email</body></html>",
  });
  // A later run must not change what the campaign's origin says.
  await seedRun("run-later", { run_id: "run-later", recommendations: [], considered: [] });

  const { status, body } = await api.get(`/campaigns/${c.id}/original`, { session: SHOP });
  assert.equal(status, 200);
  assert.equal(body.approvedCopy.subject, "We saved something for you");
  assert.equal(body.renderedHtml, "<html><body>Frozen email</body></html>");
  assert.ok(body.frozenAt, "the handoff time travels with the snapshot");
  assert.equal(body.recommendation.playName, "Bring back lapsed customers");
  assert.equal(body.recommendation.evidenceLine, "Observed in your store");
  assert.equal(body.recommendation.observedChange.unit, "percentage_points");

  assert.equal((await api.get(`/campaigns/${c.id}/original`, { session: OTHER })).status, 404, "another shop learns nothing");
  assert.equal((await api.get(`/campaigns/${c.id}/original`, { session: null })).status, 401);
});

suite("older campaigns are offered only when more exist", async () => {
  await db.resetDatabase();
  for (const p of ["one", "two", "three"]) {
    const c = await seedCampaign(`play-${p}`);
    await handOff(c.id);
  }
  const small = (await api.get(`/results/${SHOP}?limit=2`)).body;
  assert.equal(small.hasMore, true);
  assert.equal(small.results.length, 2);
  const all = (await api.get(`/results/${SHOP}?limit=5`)).body;
  assert.equal(all.hasMore, false);
  assert.equal(all.results.length, 3);
});

// The reported defect, reproduced as a route test: calculate, add a $123 order,
// publish a newer sync, reload. Results reported $0 with both freshness
// warnings cleared.
suite("a newer sync recalculates the figures, which record the sync they used", async () => {
  await db.resetDatabase();
  const first = await activeSync({ startedAt: new Date(Date.now() - 2 * 3600000), publishedAt: new Date(Date.now() - 3600000) });
  const c = await sentCampaign("play-fresh", ago(40), { treated: ["a", "b"], held: ["h", "i"] });

  let w30 = win((await api.get(`/results/${SHOP}`)).body.results[0], 30);
  assert.equal(w30.assigned.revenue, 0);
  assert.equal(w30.calculatedFrom.syncRunId, first.syncRunId);

  await order("a", ago(35), 123);
  const second = await activeSync({ startedAt: new Date(), publishedAt: new Date() });

  const { body } = await api.get(`/results/${SHOP}`);
  w30 = win(body.results.find((r) => r.campaignId === c.id), 30);
  assert.equal(w30.assigned.revenue, 123, "the newer sync's order is counted");
  assert.equal(w30.calculatedFrom.syncRunId, second.syncRunId, "figures name the sync they were calculated from");
  assert.equal(w30.sourceSuperseded, false);
  assert.equal(body.source.syncRunId, second.syncRunId);
});

// If recalculation does not happen (it failed), the old figures stand as a
// record of the OLD sync: flagged as superseded, and judged against the old
// sync's coverage. A newer sync must never certify them as complete.
suite("a newer sync never certifies figures calculated from an older one", async () => {
  await db.resetDatabase();
  // The old sync's orders stop 20 days ago; the 30-day window ended 10 days ago.
  const old = await activeSync({ startedAt: ago(20), publishedAt: ago(20) });
  const c = await sentCampaign("play-old", ago(40), { treated: ["a", "b"], held: ["h", "i"] });
  await order("a", ago(35), 30); await order("h", ago(35), 20);
  await measureCampaign(c.id, { source: old });

  const fresh = await activeSync({ startedAt: new Date(), publishedAt: new Date() });
  await order("b", ago(35), 99); // only the new sync would see this
  const summary = await summarizeCampaign(c.id, { source: fresh });
  const w30 = win(summary, 30);

  assert.equal(w30.sourceSuperseded, true);
  assert.equal(w30.calculatedFrom.syncRunId, old.syncRunId, "provenance stays with the original sync");
  assert.equal(w30.calculatedFrom.stale, true);
  assert.equal(w30.assigned.revenue, 30, "the old figures are kept, not silently replaced");
  assert.equal(w30.assessment.state, "awaiting_order_data", "completeness is judged by the data used, not the newest sync");
  assert.deepEqual(w30.assessment.reasons, ["orders_not_synced_through_window_end"]);
  assert.equal(summary.source.syncRunId, fresh.syncRunId, "the page still knows the current sync");
});

suite("a seeded demonstration shop is labelled sample data; a real one is not", async () => {
  await db.resetDatabase();
  await query(`INSERT INTO clean.shop (shop_domain, currency) VALUES ($1, 'USD')`, [SHOP]);
  assert.equal((await api.get(`/results/${SHOP}`)).body.sampleData, false);
  await query(`UPDATE clean.shop SET sample_data = true WHERE shop_domain = $1`, [SHOP]);
  assert.equal((await api.get(`/results/${SHOP}`)).body.sampleData, true);
});

// The reported defect: arms were written one statement at a time, so a failure
// on the second write left one arm from the new sync beside the other from the
// old — labelled as the new sync, fresh, not superseded. A trigger fails the
// SECOND measurement write of the new sync, whichever arm comes first.
suite("a recalculation that fails halfway leaves the previous result whole", async () => {
  await db.resetDatabase();
  const first = await activeSync({ startedAt: new Date(Date.now() - 2 * 3600000), publishedAt: new Date(Date.now() - 3600000) });
  const c = await sentCampaign("play-atomic", ago(40), { treated: ["a", "b"], held: ["h", "i"] });
  await order("a", ago(35), 30);
  await order("h", ago(35), 20);
  const before = win((await api.get(`/results/${SHOP}`)).body.results[0], 30);
  assert.equal(before.assigned.revenue, 30);
  assert.equal(before.heldBack.revenue, 20);
  assert.equal(before.calculatedFrom.syncRunId, first.syncRunId);

  // New data in both arms, and a newer sync.
  await order("b", ago(33), 70);
  await order("i", ago(33), 100);
  const second = await activeSync({ startedAt: new Date(), publishedAt: new Date() });

  await query(`CREATE TABLE IF NOT EXISTS public.test_fault_count (n INTEGER NOT NULL)`);
  await query(`DELETE FROM public.test_fault_count`);
  await query(`INSERT INTO public.test_fault_count VALUES (0)`);
  await query(`
    CREATE OR REPLACE FUNCTION public.test_fail_second_write() RETURNS trigger AS $$
    BEGIN
      IF NEW.source_sync_run_id = ${Number(second.syncRunId)} THEN
        UPDATE public.test_fault_count SET n = n + 1;
        IF (SELECT n FROM public.test_fault_count) >= 2 THEN
          RAISE EXCEPTION 'injected failure on the second measurement write';
        END IF;
      END IF;
      RETURN NEW;
    END $$ LANGUAGE plpgsql`);
  await query(`
    CREATE TRIGGER test_fail_second_write BEFORE INSERT OR UPDATE ON clean.campaign_measurements
      FOR EACH ROW EXECUTE FUNCTION public.test_fail_second_write()`);
  try {
    const { body } = await api.get(`/results/${SHOP}`);
    const result = body.results.find((r) => r.campaignId === c.id);
    const w30 = win(result, 30);

    assert.equal(result.calculationFailed, true, "the failure is reported");
    // Both previous figures, from the previous sync — neither half of the new one.
    assert.equal(w30.assigned.revenue, 30);
    assert.equal(w30.heldBack.revenue, 20);
    assert.equal(w30.calculatedFrom.syncRunId, first.syncRunId, "provenance is still the first sync");
    assert.equal(w30.sourceSuperseded, true, "and it is labelled as superseded, not fresh");
    assert.equal(w30.mixedCalculation, false);

    const { rows } = await query(
      `SELECT arm, source_sync_run_id FROM clean.campaign_measurements WHERE campaign_id = $1 AND window_days = 30 ORDER BY arm`,
      [c.id]
    );
    assert.deepEqual(rows.map((r) => r.source_sync_run_id), [first.syncRunId, first.syncRunId], "no row from the failed attempt survived");
  } finally {
    await query(`DROP TRIGGER IF EXISTS test_fail_second_write ON clean.campaign_measurements`);
    await query(`DROP FUNCTION IF EXISTS public.test_fail_second_write()`);
    await query(`DROP TABLE IF EXISTS public.test_fault_count`);
  }

  // With the fault gone, the next load recalculates from the second sync.
  const after = win((await api.get(`/results/${SHOP}`)).body.results[0], 30);
  assert.equal(after.assigned.revenue, 100);
  assert.equal(after.heldBack.revenue, 120);
  assert.equal(after.calculatedFrom.syncRunId, second.syncRunId);
});

suite("rows from different calculations are never presented as one result", async () => {
  await db.resetDatabase();
  const first = await activeSync({ startedAt: new Date(), publishedAt: new Date() });
  const c = await sentCampaign("play-mixed", ago(40), { treated: ["a", "b"], held: ["h", "i"] });
  await order("a", ago(35), 30); await order("h", ago(35), 20);
  await measureCampaign(c.id, { source: first });
  const second = await activeSync({ startedAt: new Date(), publishedAt: new Date() });
  // Simulate a mixed window, as the old non-atomic writes could leave behind.
  await query(
    `UPDATE clean.campaign_measurements SET source_sync_run_id = $2 WHERE campaign_id = $1 AND arm = 'holdout'`,
    [c.id, second.syncRunId]
  );
  const w30 = win(await summarizeCampaign(c.id, { source: second }), 30);
  assert.equal(w30.mixedCalculation, true);
  assert.equal(w30.assigned, null, "no figures are shown");
  assert.equal(w30.heldBack, null);
  assert.deepEqual(w30.assessment, { state: "not_calculated", reasons: ["mixed_calculation"] });
  assert.equal(w30.calculatedFrom.syncRunId, null, "no single sync is claimed");
  assert.equal(w30.sourceSuperseded, true);
});
