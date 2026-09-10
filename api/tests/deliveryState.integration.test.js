const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");
const { issueSession } = require("../src/services/sessionService");
const { upsertCampaign, getCampaign } = require("../src/services/campaignService");
const {
  DELIVERY_STATES,
  getDelivery,
  recordStatusCheck,
  transitionDelivery,
} = require("../src/services/deliveryStateService");
const { reconcileCampaign } = require("../src/services/reconciliationService");

const SHOP = "delivery-shop.myshopify.com";
const PLAY = "play-1";

let api;
test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

async function seedCampaign() {
  await query(`INSERT INTO clean.sync_runs (shop_domain, status) VALUES ($1, 'complete')`, [SHOP]);
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run)
     VALUES ('run-1', $1, 'store', '{}'::jsonb)`, [SHOP]
  );
  return upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY, displayName: "Winback" });
}

suite("a new campaign starts with nothing claimed", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  const delivery = await getDelivery(campaign.id);

  assert.equal(delivery.state, "not_started");
  assert.equal(delivery.providerCampaignId, null);
  assert.equal(delivery.providerCampaignUrl, null);
  assert.equal(delivery.lastCheckedAt, null, "renders as 'not checked yet', never 'just now'");
  assert.equal(delivery.providerSentAt, null);
  assert.equal(delivery.providerSentCount, null);
});

suite("nothing local can claim a send", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-1" }, { fromProvider: true });

  // The whole contract in one assertion: only a provider response may say a
  // campaign was sent, scheduled, or is awaiting a send.
  for (const state of ["sent", "scheduled", "awaiting_send"]) {
    await assert.rejects(() => transitionDelivery(campaign.id, state), (error) => {
      assert.equal(error.name, "DeliveryTransitionRejected");
      assert.match(error.message, /may only be written from a provider response/);
      return true;
    });
  }

  // A local status write is not evidence either.
  await require("../src/services/campaignService").updateCampaign(campaign.id, { status: "sent" });
  const delivery = await getDelivery(campaign.id);
  assert.equal(delivery.state, "created", "local status did not move the durable state");
  assert.equal(delivery.localStatus, "sent", "and the two are visibly different things");
});

suite("an uncertain outcome has no retry edge", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  // A request that timed out may still have been executed. Retrying could
  // create a second campaign, which is worse than a stalled one.
  await assert.rejects(() => transitionDelivery(campaign.id, "creating"), (error) => {
    assert.equal(error.name, "DeliveryTransitionRejected");
    assert.equal(error.from, "uncertain");
    return true;
  });

  // A proven pre-creation failure DOES allow one, because nothing exists there.
  await db.resetDatabase();
  const safe = await seedCampaign();
  await transitionDelivery(safe.id, "creating");
  await transitionDelivery(safe.id, "failed");
  const retried = await transitionDelivery(safe.id, "creating");
  assert.equal(retried.state, "creating");
});

suite("a sent campaign is terminal", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-1" }, { fromProvider: true });
  await transitionDelivery(campaign.id, "sent", {
    providerSentAt: new Date("2026-09-01T10:00:00Z"), providerSentCount: 900,
  }, { fromProvider: true });

  for (const state of DELIVERY_STATES.filter((s) => s !== "sent")) {
    await assert.rejects(
      () => transitionDelivery(campaign.id, state, {}, { fromProvider: true }),
      (error) => { assert.equal(error.name, "DeliveryTransitionRejected"); return true; }
    );
  }
});

suite("an unknown sent count stays unknown", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-1" }, { fromProvider: true });

  // A campaign that sent to 900 people and reported no count is not a campaign
  // that sent to nobody. Coalescing to 0 would make those indistinguishable.
  const delivery = await transitionDelivery(campaign.id, "sent", {
    providerSentAt: new Date("2026-09-01T10:00:00Z"),
    providerSentCount: null,
    providerSendStatus: "sent",
  }, { fromProvider: true });

  assert.equal(delivery.providerSentCount, null);
  assert.notEqual(delivery.providerSentCount, 0);
  assert.ok(delivery.providerSentAt, "the send time is known even when the count is not");
});

suite("a provider that genuinely reports zero can say zero", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-1" }, { fromProvider: true });
  const delivery = await transitionDelivery(campaign.id, "sent", {
    providerSentAt: new Date(), providerSentCount: 0,
  }, { fromProvider: true });
  assert.equal(delivery.providerSentCount, 0, "zero and unknown are different values");
});

suite("a failed check ages the state instead of refreshing it", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  const created = await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-1" }, { fromProvider: true });
  const confirmedAt = created.lastConfirmedAt;
  assert.ok(confirmedAt);

  const after = await recordStatusCheck(campaign.id, { ok: false, error: "timeout" });
  assert.ok(after.lastCheckedAt, "we did look");
  assert.equal(after.lastCheckOk, false);
  assert.equal(after.lastCheckError, "timeout");
  assert.equal(after.lastConfirmedAt.getTime(), confirmedAt.getTime(),
    "but the provider told us nothing, so the state is exactly as old as it was");
});

suite("reconciliation adopts a single match", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  const result = await reconcileCampaign(campaign.id, {
    findByName: async () => ({ matches: [{ id: "kl-42", status: "draft" }], complete: true }),
  });

  assert.equal(result.ok, true);
  assert.equal(result.delivery.state, "awaiting_send");
  assert.equal(result.delivery.providerCampaignId, "kl-42");
  // No URL: the provider's links.self is an API resource, not a page a merchant
  // can open, so we hold none and the UI falls back to find-by-name.
  assert.equal(result.delivery.providerCampaignUrl, null);
});

suite("reconciliation refuses to guess between matches", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  const result = await reconcileCampaign(campaign.id, {
    findByName: async () => ({ matches: [{ id: "kl-1" }, { id: "kl-2" }], complete: true }),
  });

  // Adopting one of several would attach the merchant's record to an arbitrary
  // provider object. A human resolves this.
  assert.equal(result.reason, "ambiguous");
  assert.equal(result.matches, 2);
  assert.equal(result.delivery.state, "uncertain", "still unresolved");
  assert.equal(result.delivery.providerCampaignId, null, "and nothing was adopted");
});

suite("reconciliation finding nothing makes retry safe", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  const result = await reconcileCampaign(campaign.id, {
    findByName: async () => ({ matches: [], complete: true }),
  });
  assert.equal(result.reason, "not_found");
  assert.equal(result.delivery.state, "failed");

  // Now provably safe: the provider holds nothing.
  const retried = await transitionDelivery(campaign.id, "creating");
  assert.equal(retried.state, "creating");
});

suite("reconciliation records a failed lookup without inventing state", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  const result = await reconcileCampaign(campaign.id, {
    findByName: async () => { throw new Error("klaviyo unreachable"); },
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "check_failed");
  assert.equal(result.delivery.state, "uncertain", "unchanged");
  assert.equal(result.delivery.lastCheckOk, false);
  assert.ok(result.delivery.lastCheckedAt);
  assert.equal(result.delivery.lastConfirmedAt, null);
});

suite("reconciliation carries a provider send through", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-7" }, { fromProvider: true });

  const sentAt = new Date("2026-09-02T09:30:00Z");
  const result = await reconcileCampaign(campaign.id, {
    lookupById: async (id) => ({ id, status: "sent", sentAt, sentCount: 873 }),
  });

  assert.equal(result.delivery.state, "sent");
  assert.equal(result.delivery.providerSentAt.toISOString(), sentAt.toISOString(),
    "the PROVIDER's send time, not ours");
  assert.equal(result.delivery.providerSentCount, 873);
  assert.equal(result.delivery.providerSendStatus, "sent");
});

suite("an unrecognised provider status leaves the state alone", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-8" }, { fromProvider: true });

  const result = await reconcileCampaign(campaign.id, {
    lookupById: async (id) => ({ id, status: "something-new" }),
  });
  // Guessing would put a state on screen that no provider ever reported.
  assert.equal(result.delivery.state, "created");
  assert.equal(result.reason, "reference_only");
});

suite("the delivery endpoint reports the durable state", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  const response = await api.get(`/campaigns/${campaign.id}/delivery`, { session: SHOP });
  assert.equal(response.status, 200);
  assert.equal(response.body.delivery.state, "not_started");
  assert.equal(response.body.delivery.lastCheckedAt, null);

  const missing = await api.get("/campaigns/999999/delivery", { session: SHOP });
  assert.equal(missing.status, 404);
});

suite("reconciliation is founder-only", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  delete process.env.BEACONAI_ADMIN_TOKEN;

  const closed = await api.post(`/campaigns/${campaign.id}/reconcile`, {});
  assert.equal(closed.status, 503, "closed by default, like the shell endpoint");

  process.env.BEACONAI_ADMIN_TOKEN = "test-token";
  const wrong = await api.post(`/campaigns/${campaign.id}/reconcile`, {});
  assert.equal(wrong.status, 403);
  delete process.env.BEACONAI_ADMIN_TOKEN;
});

suite("reconciliation looks up the id it already holds", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-known" }, { fromProvider: true });

  let nameSearched = false;
  const result = await reconcileCampaign(campaign.id, {
    lookupById: async (id) => {
      assert.equal(id, "kl-known");
      return { id, status: "sent", sentAt: new Date("2026-09-03T08:00:00Z"), sentCount: 500 };
    },
    findByName: async () => { nameSearched = true; return { matches: [], complete: true }; },
  });

  // A provider-issued id is a far stronger identity than any name search, and
  // skipping it was how reconciliation "failed to find" a campaign it already
  // had a reference to.
  assert.equal(nameSearched, false, "no name search was needed");
  assert.equal(result.delivery.state, "sent");
  assert.equal(result.delivery.providerSentCount, 500);
});

suite("reconciliation searches by the name actually sent, not a re-derived one", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await query(
    `UPDATE clean.campaigns SET provider_campaign_name = $2 WHERE id = $1`,
    [campaign.id, "BeaconAI - Bring back first-time buyers"]
  );
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  let searchedFor = null;
  await reconcileCampaign(campaign.id, {
    lookupById: async () => null,
    findByName: async (name) => { searchedFor = name; return { matches: [], complete: true }; },
  });

  // Re-deriving the name from the stored row produced "BeaconAI - Campaign",
  // so the lookup searched for something that was never created.
  assert.equal(searchedFor, "BeaconAI - Bring back first-time buyers");
});

suite("an incomplete lookup cannot declare absence", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  // A partial listing that happens not to contain the campaign looks exactly
  // like the campaign not existing — and absence is what authorises a retry.
  const result = await reconcileCampaign(campaign.id, {
    findByName: async () => ({ matches: [], complete: false }),
  });
  assert.equal(result.reason, "inconclusive");
  assert.equal(result.delivery.state, "uncertain", "still unresolved, not cleared to retry");
});

suite("establishing absence actually makes a retry possible", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  const { reserveCampaignForHandoff, getCampaign: get } = require("../src/services/campaignService");
  await reserveCampaignForHandoff(campaign.id, campaign.revision);
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  await reconcileCampaign(campaign.id, {
    findByName: async () => ({ matches: [], complete: true }),
  });

  const after = await get(campaign.id);
  // "Safe to retry" has to mean retry works. The reservation is what blocks the
  // next attempt, so leaving it made the campaign read as retryable and then
  // refuse with "a send is already in progress".
  assert.equal(after.handoffReservedAt, null, "the reservation was released");
  const reserved = await reserveCampaignForHandoff(campaign.id, after.revision);
  assert.ok(reserved.handoffReservedAt, "and a real retry can now proceed");
});

suite("a later check that learns the sent count records it", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-9" }, { fromProvider: true });

  const sentAt = new Date("2026-09-04T10:00:00Z");
  const first = await reconcileCampaign(campaign.id, {
    lookupById: async (id) => ({ id, status: "sent", sentAt, sentCount: null }),
  });
  assert.equal(first.delivery.state, "sent");
  assert.equal(first.delivery.providerSentCount, null);

  // The provider now knows the count. The state has not moved, so the
  // transition is a no-op — but the FACT is new and must not be dropped.
  const second = await reconcileCampaign(campaign.id, {
    lookupById: async (id) => ({ id, status: "sent", sentAt, sentCount: 873 }),
  });
  assert.equal(second.delivery.providerSentCount, 873);
  assert.equal(second.delivery.state, "sent");
});

suite("a later check reporting no count cannot erase a known one", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "created", { providerCampaignId: "kl-10" }, { fromProvider: true });
  const sentAt = new Date("2026-09-04T10:00:00Z");

  await reconcileCampaign(campaign.id, {
    lookupById: async (id) => ({ id, status: "sent", sentAt, sentCount: 640 }),
  });
  const after = await reconcileCampaign(campaign.id, {
    lookupById: async (id) => ({ id, status: "sent", sentAt, sentCount: null }),
  });
  assert.equal(after.delivery.providerSentCount, 640, "a known number is not un-known by a quieter answer");
});

suite("one shop cannot read another shop's delivery state", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();

  // Naming the shop is a claim, not a credential: an unauthenticated request is
  // refused whatever shop it names.
  const anonymous = await api.get(`/campaigns/${campaign.id}/delivery?shopDomain=${encodeURIComponent(SHOP)}`);
  assert.equal(anonymous.status, 401, "supplying the target shop's name is not authentication");

  // Same 404 as a missing campaign, so an id cannot be probed for existence
  // from another shop's authenticated session.
  const foreign = await api.get(`/campaigns/${campaign.id}/delivery`, { session: "someone-else.myshopify.com" });
  assert.equal(foreign.status, 404);

  const own = await api.get(`/campaigns/${campaign.id}/delivery`, { session: SHOP });
  assert.equal(own.status, 200);
});

suite("an attempt that may still be running is not concluded about", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  const { reserveCampaignForHandoff, getCampaign: get } = require("../src/services/campaignService");
  await reserveCampaignForHandoff(campaign.id, campaign.revision);
  await transitionDelivery(campaign.id, "creating");

  // The provider request is still in flight. A lookup finding nothing proves
  // nothing — the call can create its campaign a moment later.
  const result = await reconcileCampaign(campaign.id, {
    findByName: async () => ({ matches: [], complete: true }),
  });
  assert.equal(result.reason, "attempt_in_flight");
  assert.equal(result.delivery.state, "creating", "unchanged");

  // And critically: the reservation still holds, so a second attempt cannot
  // start alongside the first.
  const after = await get(campaign.id);
  assert.ok(after.handoffReservedAt, "the reservation was not released");
  await assert.rejects(
    () => reserveCampaignForHandoff(campaign.id, after.revision),
    (error) => { assert.equal(error.name, "CampaignHandoffInProgress"); return true; }
  );
});

suite("a stale attempt becomes unknown, not failed", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  const { reserveCampaignForHandoff } = require("../src/services/campaignService");
  await reserveCampaignForHandoff(campaign.id, campaign.revision);
  await transitionDelivery(campaign.id, "creating");

  // Twenty minutes later, with nothing found. "We stopped waiting" is not
  // "nothing was created", so this is uncertain — which offers no retry.
  const result = await reconcileCampaign(campaign.id, {
    findByName: async () => ({ matches: [], complete: true }),
    now: Date.now() + 20 * 60 * 1000,
  });
  assert.equal(result.reason, "attempt_abandoned");
  assert.equal(result.delivery.state, "uncertain");
  assert.notEqual(result.delivery.state, "failed");
});

suite("an incomplete search cannot adopt a match either", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  // One match on an early page says nothing about a second on a later one.
  // Adopting it would attach the merchant's record to a campaign that may not
  // be theirs.
  const result = await reconcileCampaign(campaign.id, {
    findByName: async () => ({ matches: [{ id: "kl-maybe", status: "draft" }], complete: false }),
  });
  assert.equal(result.reason, "inconclusive");
  assert.equal(result.delivery.state, "uncertain");
  assert.equal(result.delivery.providerCampaignId, null, "nothing was adopted");
});

suite("the name search is scoped to this attempt", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  const { reserveCampaignForHandoff } = require("../src/services/campaignService");
  const reserved = await reserveCampaignForHandoff(campaign.id, campaign.revision);
  await query(`UPDATE clean.campaigns SET provider_campaign_name = 'BeaconAI - Winback' WHERE id = $1`, [campaign.id]);
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  let scope = null;
  await reconcileCampaign(campaign.id, {
    findByName: async (name, options) => { scope = options; return { matches: [], complete: true }; },
  });

  // Two attempts on the same campaign share a name; only the creation window
  // tells them apart.
  assert.ok(scope, "the search was given a scope");
  assert.equal(
    new Date(scope.createdAtOrAfter).toISOString(),
    new Date(reserved.handoffReservedAt).toISOString(),
    "scoped to when this attempt began"
  );
});

suite("the route forwards the attempt scope to the provider lookup", async () => {
  await db.resetDatabase();
  const campaign = await seedCampaign();
  const { reserveCampaignForHandoff } = require("../src/services/campaignService");
  const reserved = await reserveCampaignForHandoff(campaign.id, campaign.revision);
  await query(`UPDATE clean.campaigns SET provider_campaign_name = 'BeaconAI - Winback' WHERE id = $1`, [campaign.id]);
  await transitionDelivery(campaign.id, "creating");
  await transitionDelivery(campaign.id, "uncertain");

  // The service was scoping correctly and the ROUTE was dropping it: its
  // `findByName: (name) => ...` discarded the options argument, so the real
  // endpoint could still adopt an older campaign sharing this name.
  const klaviyoClient = require("../src/services/klaviyoClient");
  const original = klaviyoClient.findKlaviyoCampaigns;
  let received;
  klaviyoClient.findKlaviyoCampaigns = async (_key, name, options) => {
    received = { name, options };
    return { matches: [], complete: true };
  };

  process.env.BEACONAI_ADMIN_TOKEN = "test-token";
  try {
    const response = await fetch(`${api.base}/campaigns/${campaign.id}/reconcile`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-beaconai-admin-token": "test-token" },
      body: JSON.stringify({}),
    });
    assert.equal(response.status, 200);
  } finally {
    klaviyoClient.findKlaviyoCampaigns = original;
    delete process.env.BEACONAI_ADMIN_TOKEN;
  }

  assert.equal(received.name, "BeaconAI - Winback");
  assert.ok(received.options, "the options argument reached the provider client");
  assert.equal(
    new Date(received.options.createdAtOrAfter).toISOString(),
    new Date(reserved.handoffReservedAt).toISOString(),
    "scoped to when this attempt began"
  );
});
