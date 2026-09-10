#!/usr/bin/env node
//
// Seeds a measurable campaign history so the Results page can be exercised
// today rather than in thirty days.
//
//   npm run seed:results            -- seed
//   npm run seed:results -- --clean -- remove everything it created
//
// WHY A SEPARATE SHOP DOMAIN
// Measurement reads clean.orders, so a demo needs orders in there — and the
// engine reads the same table. Seeding into your real store would silently
// change the audiences the engine computes on its next run. Everything here
// lives under a seed shop domain instead, so your synced store is untouched and
// cleanup is a single delete.
//
// WHAT IT PROVES
// The lift is planted, so the script knows the right answer before it asks.
// It plants a known per-customer difference, runs the REAL measurement code,
// and checks the reported confidence interval contains it. That tests whether
// the number is correct, not merely whether the page renders.
//
// It uses the real splitAudience, the real recordRecipients and the real
// measureCampaign — no mocks — so a bug in any of them fails this script.

const { pool, query } = require("../db");
const { initSchema } = require("../schema");
const { splitAudience } = require("../services/holdoutService");
const { upsertCampaign, recordRecipients } = require("../services/campaignService");
const { measureCampaign, summarizeProgram } = require("../services/measurementService");

const SEED_SHOP = process.env.SEED_SHOP_DOMAIN || "seed-demo.myshopify.com";
const SEED_RUN = "seed-run-0001";
const AOV = 60;

// Multiply audience sizes. Your dev store's audiences (a few hundred) are thin
// enough that most campaigns land on "too small to tell" — which is the honest
// answer at that scale, not a bug. Pass --scale 10 to see what the same page
// looks like for a store at the top of the ICP, where the intervals tighten and
// verdicts actually resolve.
const SCALE = (() => {
  const i = process.argv.indexOf("--scale");
  const n = i === -1 ? 1 : Number(process.argv[i + 1]);
  return Number.isFinite(n) && n > 0 ? n : 1;
})();

// Plays and audience sizes are mirrored from the real store when one has been
// synced, so the demo looks like the merchant's own briefing rather than a
// generic fixture. Falls back to these when there is no run to copy.
const FALLBACK_PLAYS = [
  { playId: "winback_dormant_cohort", size: 234 },
  { playId: "discount_dependency_hygiene", size: 555 },
  { playId: "cohort_journey_first_to_second", size: 413 },
];

// Per-play effects, chosen to cover the three verdicts the page must handle.
// treatedRate/holdoutRate are 30-day purchase probabilities; the expected
// per-customer lift is (treatedRate - holdoutRate) * AOV.
const EFFECTS = {
  0: { label: "a real, detectable lift", treatedRate: 0.021, holdoutRate: 0.006, daysAgo: 45 },
  1: { label: "no real effect", treatedRate: 0.012, holdoutRate: 0.0115, daysAgo: 40 },
  2: { label: "still measuring", treatedRate: 0.020, holdoutRate: 0.006, daysAgo: 5 },
};

// Deterministic RNG so a run is reproducible and a failure can be re-examined.
function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const daysAgo = (n) => new Date(Date.now() - n * 86400000);

async function realStorePlays() {
  const { rows } = await query(
    `SELECT a.play_id, COALESCE(array_length(a.customer_ids, 1), 0) AS size
       FROM clean.engine_audiences a
       JOIN clean.engine_run_snapshots s ON s.run_id = a.run_id
      WHERE s.shop_domain <> $1
        AND COALESCE(array_length(a.customer_ids, 1), 0) > 50
      ORDER BY s.created_at DESC, size DESC
      LIMIT 3`,
    [SEED_SHOP]
  );
  return rows.map((r) => ({ playId: r.play_id, size: Number(r.size) }));
}

async function clean() {
  // campaign_recipients and campaign_measurements cascade from campaigns;
  // engine_audiences cascades from the run snapshot.
  await query(`DELETE FROM clean.campaigns WHERE shop_domain = $1`, [SEED_SHOP]);
  await query(`DELETE FROM clean.engine_run_snapshots WHERE run_id = $1`, [SEED_RUN]);
  const orders = await query(`DELETE FROM clean.orders WHERE shop_domain = $1`, [SEED_SHOP]);
  await query(`DELETE FROM clean.customers WHERE shop_domain = $1`, [SEED_SHOP]);
  console.log(`Removed seed data for ${SEED_SHOP} (${orders.rowCount} orders).`);
}

async function seed() {
  await clean();

  const fromStore = await realStorePlays();
  const plays = fromStore.length ? fromStore : FALLBACK_PLAYS;
  console.log(fromStore.length
    ? `Mirroring ${plays.length} plays from your synced store: ${plays.map((p) => `${p.playId} (${p.size})`).join(", ")}`
    : `No synced store found — using fallback audience sizes.`);
  if (SCALE !== 1) console.log(`Scaling audiences x${SCALE} (ICP-scale simulation).`);

  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run, created_at)
     VALUES ($1, $2, 'seed', '{"run_id":"seed-run-0001"}'::jsonb, $3)`,
    [SEED_RUN, SEED_SHOP, daysAgo(60)]
  );

  let orderSeq = 0;
  const checks = [];

  for (let i = 0; i < plays.length; i += 1) {
    const { playId, size: baseSize } = plays[i];
    const size = Math.round(baseSize * SCALE);
    const effect = EFFECTS[i] || EFFECTS[0];
    const sentAt = daysAgo(effect.daysAgo);
    const random = rng(1000 + i);

    // Customers exist only so the audience is made of plausible ids.
    const customers = Array.from({ length: size }, (_, n) => ({
      customerId: `seed-${i}-${n}`,
      email: `seed-${i}-${n}@example.invalid`,
    }));
    for (const c of customers) {
      await query(
        `INSERT INTO clean.customers (id, shop_domain, email, created_at)
         VALUES ($1, $2, $3, $4) ON CONFLICT (id) DO NOTHING`,
        [c.customerId, SEED_SHOP, c.email, daysAgo(300)]
      );
    }

    // The REAL split — same function the send path uses.
    const split = splitAudience(SEED_SHOP, customers, 0.1);

    const campaign = await upsertCampaign({
      shopDomain: SEED_SHOP, runId: SEED_RUN, playId, status: "sent",
    });
    // Demo campaigns are "confirmed sent" by construction: measurement anchors on
    // the provider send time, never on local status.
    await query(`UPDATE clean.campaigns SET sent_at = $2, provider_sent_at = $2, delivery_state = 'sent', audience_size = $3, holdout_size = $4 WHERE id = $1`,
      [campaign.id, sentAt, customers.length, split.holdout.length]);
    await recordRecipients(campaign.id, split);

    // Orders inside the window, at the planted rates.
    const place = async (people, rate) => {
      let placed = 0;
      for (const person of people) {
        if (random() >= rate) continue;
        const when = new Date(sentAt.getTime() + Math.floor(random() * 25 + 1) * 86400000);
        if (when > new Date()) continue;
        await query(
          `INSERT INTO clean.orders (id, shop_domain, customer_id, email, processed_at, created_at, total_price, test)
           VALUES ($1, $2, $3, $4, $5, $5, $6, false)`,
          [`seed-o-${orderSeq += 1}`, SEED_SHOP, person.customerId, person.email, when, AOV]
        );
        placed += 1;
      }
      return placed;
    };

    const tOrders = await place(split.treated, effect.treatedRate);
    const hOrders = await place(split.holdout, effect.holdoutRate);

    // What the data actually contains, which is what the measurement must find.
    const actualLift = (tOrders / split.treated.length - hOrders / Math.max(1, split.holdout.length)) * AOV;
    checks.push({ playId, campaignId: campaign.id, effect, split, tOrders, hOrders, actualLift });

    console.log(
      `  ${playId.padEnd(34)} ${String(customers.length).padStart(5)} customers ` +
      `-> ${split.treated.length} treated / ${split.holdout.length} held, ` +
      `${tOrders}/${hOrders} orders, sent ${effect.daysAgo}d ago (${effect.label})`
    );
  }

  console.log("\nMeasuring with the real measurement code...\n");
  let failures = 0;

  for (const c of checks) {
    // SELF-CHECK ONLY. The product's campaign assessment policy is unresolved
    // (RESULTS_UI_SPEC §6.2); this script supplies one explicitly so it can
    // check the interval against the planted lift. It is not what merchants see.
    const summary = await measureCampaign(c.campaignId, {
      policy: { minCustomersPerArm: 2, minPurchasersPerArm: 1, criticalValue: 1.96 },
      source: { lastSuccessfulSyncAt: new Date(), ordersCoveredThrough: new Date() },
    });
    const w30 = summary.windows.find((w) => w.windowDays === 30);
    const cmp = w30.comparison;

    const line = `  ${c.playId.padEnd(34)} assessment=${w30.assessment.state}`;
    if (w30.assessment.state === "measuring") {
      console.log(`${line}  (day ${w30.daysElapsed} of 30 — correct, window still open)`);
      continue;
    }
    if (!cmp) { console.log(`${line}  (no comparison)`); continue; }

    const contains = c.actualLift >= cmp.low && c.actualLift <= cmp.high;
    if (!contains) failures += 1;
    console.log(
      `${line}\n` +
      `      planted lift  $${c.actualLift.toFixed(4)} per customer\n` +
      `      measured      $${cmp.difference.toFixed(4)}  ` +
      `[${cmp.low.toFixed(4)}, ${cmp.high.toFixed(4)}]\n` +
      `      interval contains the planted lift: ${contains ? "YES" : "NO  <-- WRONG"}`
    );
  }

  const program = await summarizeProgram(SEED_SHOP, { sinceDays: 90 });
  if (program.available === false) {
    console.log(`\n  PROGRAM  not reported (${program.reason}) — see docs/MEASUREMENT_PROTOCOL.md`);
  } else if (program.comparison) {
    const p = program.comparison;
    console.log(
      `\n  PROGRAM  ${program.campaigns} campaigns · ` +
      `${program.treated.n_customers} treated vs ${program.holdout.n_customers} held\n` +
      `      per customer  $${p.perCustomer.difference.toFixed(4)} ` +
      `[${p.perCustomer.low.toFixed(4)}, ${p.perCustomer.high.toFixed(4)}]\n` +
      `      incremental   $${p.incremental.total.toFixed(0)} ` +
      `[${p.incremental.low.toFixed(0)}, ${p.incremental.high.toFixed(0)}]`
    );
  }

  console.log(
    `\nOpen the app with ?shop=${SEED_SHOP} and go to Results.\n` +
    `Remove it all with:  npm run seed:results -- --clean\n`
  );

  if (failures) {
    console.error(`${failures} campaign(s) reported an interval that does NOT contain the planted lift.`);
    process.exitCode = 1;
  }
}

(async () => {
  try {
    await initSchema();
    if (process.argv.includes("--clean")) await clean();
    else await seed();
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  } finally {
    await pool.end();
  }
})();
