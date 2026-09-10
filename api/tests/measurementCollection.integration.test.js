const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");
const {
  upsertCampaign, updateCampaign, recordRecipients, freezeCampaignAtHandoff, RecipientsFrozen,
} = require("../src/services/campaignService");
const { transitionDelivery } = require("../src/services/deliveryStateService");
const { measureCampaign, summarizeProgram } = require("../src/services/measurementService");

// Ticket F §7: collection that has to be right under ANY measurement design.
// Provider states are reached through Ticket D's real transitions — never by
// writing delivery columns directly — so these tests exercise the same path a
// real handoff and reconciliation take.
const SHOP = "measure-shop.myshopify.com";
const DAY = 86400000;
const ago = (days) => new Date(Date.now() - days * DAY);

let api;
test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

async function seedCampaign(playId = "play-1") {
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run)
     VALUES ('run-1', $1, 'store', '{}'::jsonb) ON CONFLICT (run_id) DO NOTHING`, [SHOP]
  );
  return upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId, displayName: playId });
}

const people = (...ids) => ids.map((id) => ({ customerId: id, email: `${id}@example.invalid` }));

// The real handoff: reserve → creating, provider returns an id → created, then
// freeze. No local timestamp of any kind is written.
async function handOff(campaignId) {
  await transitionDelivery(campaignId, "creating");
  await transitionDelivery(campaignId, "created", { provider: "klaviyo", providerCampaignId: `kl-${campaignId}` });
  await freezeCampaignAtHandoff(campaignId, {});
}

// Reconciliation finding an executed send.
async function confirmSend(campaignId, at, extra = {}) {
  await transitionDelivery(campaignId, "sent", { providerSentAt: at, ...extra }, { fromProvider: true });
}

async function order(id, customerId, at, total) {
  await query(
    `INSERT INTO clean.orders (id, shop_domain, customer_id, email, processed_at, created_at, total_price, test)
     VALUES ($1, $2, $3, $4, $5, $5, $6, false)`,
    [id, SHOP, customerId, `${customerId}@example.invalid`, at, total]
  );
}

suite("recipients are fixed once the campaign is frozen at handoff", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await recordRecipients(campaign.id, { treated: people("a", "b"), holdout: people("h") });
  await freezeCampaignAtHandoff(campaign.id, {});

  await assert.rejects(
    () => recordRecipients(campaign.id, { treated: people("h"), holdout: people("a", "b") }),
    (error) => error instanceof RecipientsFrozen,
  );
  const { rows } = await query(
    `SELECT customer_id, arm FROM clean.campaign_recipients WHERE campaign_id = $1 ORDER BY customer_id`, [campaign.id]
  );
  assert.deepEqual(rows, [
    { customer_id: "a", arm: "treated" },
    { customer_id: "b", arm: "treated" },
    { customer_id: "h", arm: "holdout" },
  ]);
});

suite("a campaign still being prepared can be re-split", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await recordRecipients(campaign.id, { treated: people("a"), holdout: [] });
  await recordRecipients(campaign.id, { treated: people("b"), holdout: people("h") });
  const { rows } = await query(`SELECT customer_id FROM clean.campaign_recipients WHERE campaign_id = $1 ORDER BY 1`, [campaign.id]);
  assert.deepEqual(rows.map((r) => r.customer_id), ["b", "h"], "a retried handoff before freeze replaces, never duplicates");
});

suite("the email each recipient was reached at, and every exclusion with its reason, are recorded", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await recordRecipients(campaign.id, {
    treated: people("111"),
    holdout: [{ customerId: "someone@shop.test", email: "someone@shop.test" }],
    excluded: [{ customerRef: "222", reason: "no_email" }, { customerRef: "333", reason: "no_email" }],
  });

  const recipients = await query(
    `SELECT customer_id, arm, email FROM clean.campaign_recipients WHERE campaign_id = $1 ORDER BY customer_id`, [campaign.id]
  );
  assert.deepEqual(recipients.rows, [
    { customer_id: "111", arm: "treated", email: "111@example.invalid" },
    { customer_id: "someone@shop.test", arm: "holdout", email: "someone@shop.test" },
  ]);
  const exclusions = await query(
    `SELECT customer_ref, reason FROM clean.campaign_recipient_exclusions WHERE campaign_id = $1 ORDER BY customer_ref`, [campaign.id]
  );
  assert.deepEqual(exclusions.rows, [
    { customer_ref: "222", reason: "no_email" },
    { customer_ref: "333", reason: "no_email" },
  ]);
});

suite("measurement waits for the provider-confirmed send, and runs from it", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await recordRecipients(campaign.id, { treated: people("a", "b"), holdout: people("h", "i") });

  // Local status says sent 40 days ago. That is bookkeeping, not a send.
  await updateCampaign(campaign.id, { status: "sent" });
  await query(`UPDATE clean.campaigns SET sent_at = $2 WHERE id = $1`, [campaign.id, ago(40)]);
  const local = await measureCampaign(campaign.id);
  assert.equal(local.measurable, false);
  assert.equal(local.reason, "no_provider_record");

  // The provider confirms the send 20 days ago. An order placed between the
  // local stamp and the real send could not have been caused by the campaign.
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-1" });
  await confirmSend(campaign.id, ago(20));
  await order("o-before", "a", ago(30), 100);
  await order("o-after", "a", ago(10), 40);

  const summary = await measureCampaign(campaign.id);
  const w30 = summary.windows.find((w) => w.windowDays === 30);
  assert.equal(w30.treated.revenue, 40, "only the order after the confirmed send counts");
  assert.ok(Math.abs(new Date(summary.sentAt).getTime() - ago(20).getTime()) < 5000, "reported anchor is the provider send");
});

suite("treated customers the provider never delivered to stay in the analysis", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await recordRecipients(campaign.id, { treated: people("a", "b", "c"), holdout: people("h", "i") });
  // The provider reached one of three (the others unsubscribed or suppressed).
  // Intent-to-treat keeps all three: dropping them would compare a
  // consent-filtered group against an unfiltered holdout.
  await handOff(campaign.id);
  await confirmSend(campaign.id, ago(5), { providerSentCount: 1 });
  const summary = await measureCampaign(campaign.id);
  const w30 = summary.windows.find((w) => w.windowDays === 30);
  assert.equal(w30.treated.n_customers, 3);
  assert.equal(w30.holdout.n_customers, 2);
});

suite("the ever-treated program comparison is withdrawn, not computed", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await recordRecipients(campaign.id, { treated: people("a", "b", "c"), holdout: people("h", "i", "j") });
  await handOff(campaign.id);
  await confirmSend(campaign.id, ago(10));
  for (const [i, id] of ["a", "b", "h"].entries()) await order(`p-${i}`, id, ago(5), 50);

  const program = await summarizeProgram(SHOP);
  assert.equal(program.available, false);
  assert.equal(program.reason, "protocol_not_live");
  assert.equal(program.campaigns, 1);
  for (const key of ["comparison", "treated", "holdout"]) {
    assert.equal(program[key], undefined, `no ${key} figure is reported`);
  }
});

// The reported omission: a normal provider-created draft has NEITHER sent_at
// nor provider_sent_at, and the timestamp filter dropped it from Results.
suite("Results lists every handed-off campaign by delivery state, and measures none before a confirmed send", async () => {
  await db.resetDatabase();
  const draft = await seedCampaign("play-draft");
  const scheduled = await seedCampaign("play-scheduled");
  const uncertain = await seedCampaign("play-uncertain");
  const sentNoTime = await seedCampaign("play-sent-no-time");
  const untouched = await seedCampaign("play-untouched");
  for (const c of [draft, scheduled, uncertain, sentNoTime]) {
    await recordRecipients(c.id, { treated: people(`${c.id}-a`, `${c.id}-b`), holdout: people(`${c.id}-h`, `${c.id}-i`) });
  }

  await handOff(draft.id);
  await handOff(scheduled.id);
  // A scheduled send can carry the SCHEDULED time. It is still not a send.
  await transitionDelivery(scheduled.id, "scheduled", { providerSentAt: new Date(Date.now() + 2 * DAY) }, { fromProvider: true });
  await transitionDelivery(uncertain.id, "creating");
  await transitionDelivery(uncertain.id, "uncertain");
  await handOff(sentNoTime.id);
  await transitionDelivery(sentNoTime.id, "sent", {}, { fromProvider: true });

  // The real case, stated as data: frozen, provider-created, both times null.
  const { rows: [raw] } = await query(
    `SELECT frozen_at, delivery_state, sent_at, provider_sent_at FROM clean.campaigns WHERE id = $1`, [draft.id]
  );
  assert.ok(raw.frozen_at);
  assert.equal(raw.delivery_state, "created");
  assert.equal(raw.sent_at, null);
  assert.equal(raw.provider_sent_at, null);

  const { status, body } = await api.get(`/results/${SHOP}`);
  assert.equal(status, 200);
  const byId = Object.fromEntries(body.results.map((r) => [r.campaignId, r]));

  assert.equal(byId[untouched.id], undefined, "a campaign never handed off is not a result");
  assert.equal(body.results.length, 4, "every handed-off campaign is listed");

  for (const [campaign, state] of [[draft, "created"], [scheduled, "scheduled"], [uncertain, "uncertain"]]) {
    const result = byId[campaign.id];
    assert.equal(result.measurable, false, state);
    assert.equal(result.reason, "send_not_confirmed", state);
    assert.equal(result.deliveryState, state);
    assert.equal(result.delivery.state, state, "the durable record travels with the row");
    assert.equal(result.sentAt, null, `${state}: no send time is invented`);
  }
  assert.equal(byId[sentNoTime.id].reason, "send_time_unknown");
  assert.equal(byId[sentNoTime.id].sentAt, null);

  // Nothing was measured: no window was opened for any of them.
  const { rows: measured } = await query(`SELECT COUNT(*)::int AS n FROM clean.campaign_measurements`);
  assert.equal(measured[0].n, 0, "no measurement starts before a confirmed send");
  assert.equal(body.program.available, false);
});

suite("Results keeps a legacy campaign marked sent only locally, and says why it has no numbers", async () => {
  await db.resetDatabase();
  const legacy = await seedCampaign("play-legacy");
  await recordRecipients(legacy.id, { treated: people("a", "b"), holdout: people("h", "i") });
  await updateCampaign(legacy.id, { status: "sent" });

  const { body } = await api.get(`/results/${SHOP}`);
  assert.equal(body.results.length, 1);
  assert.equal(body.results[0].reason, "no_provider_record");
  assert.equal(body.results[0].sentAt, null);
});
