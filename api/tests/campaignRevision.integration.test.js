const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");
const { runSync } = require("../src/services/syncService");
const {
  freezeCampaignAtHandoff,
  releaseHandoffReservation,
  reserveCampaignForHandoff,
  getCampaign,
  hashAudience,
  listCampaigns,
  upsertCampaign,
  updateCampaign,
} = require("../src/services/campaignService");

const { saveBrandTemplate } = require("../src/services/brandEmailTemplateService");
const { buildStarterShell } = require("../src/services/brandEmailRenderer");

const SHOP = "campaign-shop.myshopify.com";

// Ticket C: a handoff renders the shop's approved shell before it touches the
// provider, so any test that expects to REACH the provider needs one configured.
async function configureBrandShell(shopDomain = SHOP) {
  return saveBrandTemplate({
    shopDomain, html: buildStarterShell(), brand: { brandName: "Test Shop" }, approvedBy: "founder",
  });
}
const PLAY = "play-winback";

let api;

test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

async function seedRun(runId) {
  const sync = await runSync({
    shopDomain: SHOP, accessToken: "t", shopifyScope: "read_orders,read_all_orders",
    fetchData: async () => db.shopifyPayload({ orders: db.ordersSpanning(200) }),
  });
  await query(
    `INSERT INTO clean.engine_run_snapshots
       (run_id, shop_domain, store_id, engine_run, sync_run_id, input_provenance)
     VALUES ($1, $2, 'store', '{}'::jsonb, $3, 'verified')`,
    [runId, SHOP, sync.syncRunId]
  );
  return runId;
}

suite("a draft survives a refresh and a new engine run", async () => {
  await db.resetDatabase();
  await seedRun("run-1");

  const saved = await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY, status: "draft",
    displayName: "Win back lapsed buyers",
    draftEdits: { subject: "We saved your spot" },
    templateId: "tpl-a",
  });
  assert.equal(saved.revision, 1);

  // A new run arrives. The campaign belongs to run-1 and must still be there,
  // with its edits, its template and its name.
  await seedRun("run-2");
  const all = await listCampaigns(SHOP);
  const found = all.find((c) => c.runId === "run-1" && c.playId === PLAY);
  assert.ok(found, "retrievable across runs");
  assert.deepEqual(found.draftEdits, { subject: "We saved your spot" });
  assert.equal(found.templateId, "tpl-a");
  assert.equal(found.displayName, "Win back lapsed buyers");
});

suite("a campaign missing from the latest slate keeps its name", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY,
    status: "sent", displayName: "Win back lapsed buyers",
  });

  // run-2 has no audience and no play by this id — the engine dropped it.
  await seedRun("run-2");

  const [campaign] = await listCampaigns(SHOP, { runId: "run-1" });
  assert.equal(campaign.displayName, "Win back lapsed buyers",
    "history does not become nameless because a later slate omits the play");

  // And a later write that does not carry the name must not blank it.
  const patched = await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY, status: "sent",
    expectedRevision: campaign.revision,
  });
  assert.equal(patched.displayName, "Win back lapsed buyers");
});

suite("a stale write is refused rather than overwriting a newer one", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const first = await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY, draftEdits: { subject: "A" },
  });

  // Someone else saves. The row moves to revision 2.
  const second = await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY, draftEdits: { subject: "B" }, expectedRevision: first.revision,
  });
  assert.equal(second.revision, first.revision + 1);

  // The stale tab tries to save against the revision it last read.
  await assert.rejects(
    () => upsertCampaign({
      shopDomain: SHOP, runId: "run-1", playId: PLAY,
      draftEdits: { subject: "C" }, expectedRevision: first.revision,
    }),
    (error) => {
      assert.equal(error.name, "CampaignRevisionConflict");
      assert.equal(error.campaign.revision, second.revision);
      assert.deepEqual(error.campaign.draftEdits, { subject: "B" }, "the conflict carries the row for recovery");
      return true;
    }
  );

  const current = await getCampaign(first.id);
  assert.deepEqual(current.draftEdits, { subject: "B" }, "the newer edit stands");
});

suite("the conflict reaches the client as a recoverable 409", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });
  await updateCampaign(created.id, { status: "approved" });

  const response = await api.post("/campaigns", {
    shopDomain: SHOP, runId: "run-1", playId: PLAY,
    draftEdits: { subject: "stale" }, expectedRevision: created.revision,
  });
  assert.equal(response.status, 409);
  assert.equal(response.body.conflict, "revision");
  assert.equal(response.body.campaign.revision, created.revision + 1);
});

suite("an insert needs no revision, but an update does", async () => {
  await db.resetDatabase();
  await seedRun("run-1");

  // First greenlight: nothing exists, so there is nothing to overwrite.
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });
  assert.equal(created.revision, 1);

  // A second write with no revision is refused. A caller that has not read the
  // row cannot know what it is about to destroy — and this is the shape a stale
  // tab takes after a reload elsewhere.
  await assert.rejects(
    () => upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY, status: "approved" }),
    (error) => {
      assert.equal(error.name, "CampaignRevisionRequired");
      assert.equal(error.campaign.revision, 1);
      return true;
    }
  );

  const unchanged = await getCampaign(created.id);
  assert.equal(unchanged.status, "draft", "the revision-less write applied nothing");

  const updated = await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY, status: "approved",
    expectedRevision: created.revision,
  });
  assert.equal(updated.revision, 2);
  assert.equal(updated.status, "approved");
});

suite("only one of many concurrent writers wins", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });

  // The check used to be a SELECT before the write, so writers quoting the same
  // revision all read it, all passed, and all wrote — the last one silently
  // destroying the rest. The guard is now a predicate on the write itself, so
  // the database picks exactly one.
  const writers = 12;
  const results = await Promise.allSettled(
    Array.from({ length: writers }, (_, i) =>
      upsertCampaign({
        shopDomain: SHOP, runId: "run-1", playId: PLAY,
        draftEdits: { subject: `writer-${i}` },
        expectedRevision: created.revision,
      })
    )
  );

  const winners = results.filter((r) => r.status === "fulfilled");
  assert.equal(winners.length, 1, `exactly one write applies, got ${winners.length}`);
  for (const loser of results.filter((r) => r.status === "rejected")) {
    assert.equal(loser.reason.name, "CampaignRevisionConflict");
  }

  const final = await getCampaign(created.id);
  assert.equal(final.revision, created.revision + 1, "one increment, not twelve");
  assert.deepEqual(final.draftEdits, winners[0].value.draftEdits,
    "the row holds exactly what the winner wrote");
});

suite("only one of two simultaneous handoffs may proceed", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });

  // Reserving is what makes this safe: it happens BEFORE any provider call, so
  // two clicks cannot both reach Klaviyo and create two drafts.
  const results = await Promise.allSettled([
    reserveCampaignForHandoff(created.id, created.revision),
    reserveCampaignForHandoff(created.id, created.revision),
  ]);
  assert.equal(results.filter((r) => r.status === "fulfilled").length, 1);
  const rejected = results.find((r) => r.status === "rejected");
  assert.ok(["CampaignHandoffInProgress", "CampaignRevisionConflict"].includes(rejected.reason.name));

  // A third attempt, arriving later with a correct revision, is still refused
  // while the first is in flight.
  const reserved = await getCampaign(created.id);
  await assert.rejects(
    () => reserveCampaignForHandoff(created.id, reserved.revision),
    (error) => {
      assert.equal(error.name, "CampaignHandoffInProgress");
      return true;
    }
  );
});

suite("a handoff of a campaign edited since approval is refused", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });
  // The merchant approved revision 1; an edit landed afterwards.
  await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY,
    draftEdits: { subject: "changed after approval" }, expectedRevision: created.revision,
  });

  await assert.rejects(
    () => reserveCampaignForHandoff(created.id, created.revision),
    (error) => {
      assert.equal(error.name, "CampaignRevisionConflict");
      return true;
    }
  );
  const after = await getCampaign(created.id);
  assert.equal(after.handoffReservedAt, null, "no reservation was taken");
});

suite("a released reservation can be retried", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });

  const reserved = await reserveCampaignForHandoff(created.id, created.revision);
  assert.ok(reserved.handoffReservedAt);

  // Released only when nothing can have reached the provider.
  const released = await releaseHandoffReservation(created.id);
  assert.equal(released.handoffReservedAt, null);

  const again = await reserveCampaignForHandoff(created.id, released.revision);
  assert.ok(again.handoffReservedAt);
});

suite("a sent campaign's record cannot be rewritten", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY,
    templateId: "tpl-a", copy: { subject: "Original subject" },
  });

  const frozen = await freezeCampaignAtHandoff(created.id, {
    approvedCopy: { subject: "Original subject" },
    renderedHtml: "<html>original</html>",
    templateVersion: "tpl-a",
    audienceRef: { runId: "run-1", audienceDefinitionId: "aud-1", treated: 90, holdout: 10 },
    customerIds: ["c-1", "c-2", "c-3"],
  });
  assert.ok(frozen.frozen);
  assert.ok(frozen.reviewedAt);
  assert.equal(frozen.audienceHash, hashAudience(["c-3", "c-1", "c-2"]), "hash is order-independent");

  // Editing what was sent is refused.
  for (const patch of [
    { copy: { subject: "Rewritten" } },
    { draftEdits: { subject: "Rewritten" } },
    { templateId: "tpl-b" },
    { holdoutPct: 0.5 },
  ]) {
    await assert.rejects(() => updateCampaign(created.id, patch), (error) => {
      assert.equal(error.name, "CampaignFrozen");
      return true;
    });
  }

  // Delivery state is NOT frozen: what happened to the send must stay writable.
  const delivered = await updateCampaign(created.id, { klaviyoCampaignId: "kl-123", status: "sent" });
  assert.equal(delivered.klaviyoCampaignId, "kl-123");
  assert.equal(delivered.status, "sent");

  const after = await getCampaign(created.id);
  assert.equal(after.renderedHtml, "<html>original</html>");
  assert.deepEqual(after.approvedCopy, { subject: "Original subject" });
});

suite("regenerated copy does not rewrite a sent campaign", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY, templateId: "tpl-a", copy: { subject: "Original" },
  });
  await freezeCampaignAtHandoff(created.id, {
    approvedCopy: { subject: "Original" }, renderedHtml: "<html>original</html>", customerIds: ["c-1"],
  });

  const { cacheCopyOnCampaign } = require("../src/services/campaignService");
  const cached = await cacheCopyOnCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY, templateId: "tpl-a",
    copy: { copy: { subject: "Freshly generated" } },
  });
  assert.equal(cached, false, "the cache write finds no unfrozen row, and that is harmless");

  const after = await getCampaign(created.id);
  assert.deepEqual(after.copy, { subject: "Original" });
});

suite("a second handoff of the same campaign is refused", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });
  await freezeCampaignAtHandoff(created.id, { approvedCopy: { subject: "S" }, customerIds: ["c-1"] });

  await assert.rejects(
    () => freezeCampaignAtHandoff(created.id, { approvedCopy: { subject: "S" }, customerIds: ["c-1"] }),
    (error) => {
      assert.equal(error.name, "CampaignFrozen");
      return true;
    }
  );
});

suite("handoff resolves the audience from the campaign's own run", async () => {
  await db.resetDatabase();
  await seedRun("run-old");
  await seedRun("run-new");
  for (const id of ["old-1", "old-2", "new-1"]) {
    await query(
      `INSERT INTO clean.customers (id, shop_domain, email, created_at)
       VALUES ($1, $2, $3, NOW()) ON CONFLICT (id) DO NOTHING`,
      [id, SHOP, `${id}@example.com`]
    );
  }
  await query(
    `INSERT INTO clean.engine_audiences (run_id, audience_definition_id, play_id, materialization_status, customer_ids)
     VALUES ('run-old', 'aud-old', $1, 'MATERIALIZED', $2),
            ('run-new', 'aud-new', $1, 'MATERIALIZED', $3)`,
    [PLAY, ["old-1", "old-2"], ["new-1"]]
  );

  await configureBrandShell();
  const campaign = await upsertCampaign({ shopDomain: SHOP, runId: "run-old", playId: PLAY, status: "approved" });

  // Only the campaign id is sent — no run_id anywhere in the body. run-new is
  // the latest run and has different membership, so if origin resolution fell
  // back to "latest" this would split and record new-1.
  //
  // The request fails at the Klaviyo call (no key in tests), which is AFTER the
  // audience is resolved, split and recorded — so the recipient rows are the
  // evidence of which run's membership was actually used.
  const response = await api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: SHOP,
    campaignId: campaign.id,
    expectedRevision: campaign.revision,
    campaign: { play_id: PLAY },
  });
  assert.equal(response.status, 500, "the Klaviyo call fails, well past run resolution");

  const recipients = await query(
    `SELECT customer_id FROM clean.campaign_recipients WHERE campaign_id = $1 ORDER BY customer_id`,
    [campaign.id]
  );
  assert.deepEqual(recipients.rows.map((r) => r.customer_id), ["old-1", "old-2"],
    "the campaign's OWN run supplied the audience, not the latest run");

  const after = await getCampaign(campaign.id);
  assert.equal(after.runId, "run-old");
  assert.equal(after.frozen, false, "a failed handoff does not freeze the record");
});

suite("a campaign id from another shop is not found", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const mine = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });

  const response = await api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: "someone-else.myshopify.com",
    campaignId: mine.id,
    expectedRevision: mine.revision,
    campaign: { play_id: PLAY },
  });
  assert.equal(response.status, 404);
});

suite("existing campaigns gain the new fields without inventing history", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  // A row as it existed before Ticket B: no name, no approved copy, no audience
  // reference, and content the migration must not touch.
  await query(
    `INSERT INTO clean.campaigns (shop_domain, run_id, play_id, status, template_id, copy, sent_at)
     VALUES ($1, 'run-1', $2, 'sent', 'tpl-legacy', '{"subject":"Legacy subject"}'::jsonb, NOW())`,
    [SHOP, PLAY]
  );

  const { initSchema } = require("../src/schema");
  await initSchema();

  const [campaign] = await listCampaigns(SHOP);
  // Missing history stays missing. Filling displayName from today's slate, or
  // approvedCopy from today's copy, would fabricate a record of a review that
  // never happened for an email that has already been sent.
  assert.equal(campaign.displayName, null);
  assert.equal(campaign.approvedCopy, null);
  assert.equal(campaign.renderedHtml, null);
  assert.equal(campaign.audienceRef, null);
  assert.equal(campaign.audienceHash, null);
  assert.equal(campaign.reviewedAt, null);
  assert.equal(campaign.frozenAt, null, "a historical send is not retroactively claimed as frozen");

  // What was already there is untouched.
  assert.equal(campaign.templateId, "tpl-legacy");
  assert.deepEqual(campaign.copy, { subject: "Legacy subject" });
  assert.equal(campaign.status, "sent");
  assert.equal(campaign.revision, 1, "the counter starts, rather than claiming prior revisions");
});

suite("a handoff without a revision is refused outright", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });

  // Accepting a missing revision meant the freeze recorded whatever happened to
  // be in the row, which is the one thing the reservation exists to pin down.
  await assert.rejects(
    () => reserveCampaignForHandoff(created.id, undefined),
    (error) => {
      assert.equal(error.name, "CampaignRevisionRequired");
      return true;
    }
  );
  await assert.rejects(
    () => reserveCampaignForHandoff(created.id, null),
    (error) => {
      assert.equal(error.name, "CampaignRevisionRequired");
      return true;
    }
  );

  const after = await getCampaign(created.id);
  assert.equal(after.handoffReservedAt, null, "nothing was reserved");
});

suite("content cannot change while a handoff holds the campaign", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY, copy: { subject: "Reviewed" },
  });
  const reserved = await reserveCampaignForHandoff(created.id, created.revision);

  // An edit landing between the reservation and the freeze would be captured in
  // the frozen record without ever having been reviewed.
  for (const patch of [
    { draftEdits: { subject: "Snuck in" } },
    { copy: { subject: "Snuck in" } },
    { templateId: "tpl-other" },
    { holdoutPct: 0.4 },
  ]) {
    await assert.rejects(
      () => updateCampaign(created.id, { ...patch, expectedRevision: reserved.revision }),
      (error) => {
        assert.equal(error.name, "CampaignHandoffInProgress");
        return true;
      }
    );
  }

  // The upsert path is guarded the same way.
  await assert.rejects(
    () => upsertCampaign({
      shopDomain: SHOP, runId: "run-1", playId: PLAY,
      draftEdits: { subject: "Snuck in" }, expectedRevision: reserved.revision,
    }),
    (error) => {
      assert.equal(error.name, "CampaignHandoffInProgress");
      return true;
    }
  );

  // The route driving the handoff holds the reservation, so it may still write.
  const bookkeeping = await updateCampaign(
    created.id,
    { holdoutPct: 0.1, audienceSize: 100, holdoutSize: 10, expectedRevision: reserved.revision },
    { holdsReservation: true }
  );
  assert.equal(Number(bookkeeping.holdoutPct), 0.1);

  // And delivery state is writable by anyone: it records what happened TO a send.
  const delivered = await updateCampaign(created.id, { klaviyoCampaignId: "kl-9" });
  assert.equal(delivered.klaviyoCampaignId, "kl-9");

  const final = await getCampaign(created.id);
  assert.deepEqual(final.copy, { subject: "Reviewed" }, "the reviewed content is intact");
});

suite("a provider failure after creation keeps the campaign locked", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  for (const id of ["c-1", "c-2"]) {
    await query(
      `INSERT INTO clean.customers (id, shop_domain, email, created_at)
       VALUES ($1, $2, $3, NOW()) ON CONFLICT (id) DO NOTHING`,
      [id, SHOP, `${id}@example.com`]
    );
  }
  await query(
    `INSERT INTO clean.engine_audiences (run_id, audience_definition_id, play_id, materialization_status, customer_ids)
     VALUES ('run-1', 'aud-1', $1, 'MATERIALIZED', $2)`,
    [PLAY, ["c-1", "c-2"]]
  );
  await configureBrandShell();
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY, status: "approved" });

  // No Klaviyo key in tests, so the package call fails — but it fails INSIDE the
  // provider sequence, at the template step, which may already have created
  // something. Releasing there would let the next click create a duplicate.
  const response = await api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: SHOP, campaignId: created.id, expectedRevision: created.revision,
    campaign: { play_id: PLAY },
  });
  assert.equal(response.status, 500);
  assert.equal(response.body.providerStage, "template", "we were inside the provider sequence");
  assert.equal(response.body.reconciliationRequired, true);

  const after = await getCampaign(created.id);
  assert.ok(after.handoffReservedAt, "the reservation is KEPT, not handed back");
  assert.equal(after.frozen, false);

  // A retry is refused rather than creating a second draft. Clearing this is a
  // manual reconciliation step (Ticket D).
  const retry = await api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: SHOP, campaignId: created.id, expectedRevision: after.revision,
    campaign: { play_id: PLAY },
  });
  assert.equal(retry.status, 409);
  assert.equal(retry.body.conflict, "handoff_in_progress");
});

suite("a failure before any provider call releases the reservation", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });
  const reserved = await reserveCampaignForHandoff(created.id, created.revision);

  // provenNothingCreated is the only condition that permits a release, and it
  // is true only before the first provider request is issued.
  const { PROVIDER_STAGES } = require("../src/services/klaviyoClient");
  assert.equal(PROVIDER_STAGES[0], "not_started");

  const released = await releaseHandoffReservation(reserved.id);
  assert.equal(released.handoffReservedAt, null);
  const again = await reserveCampaignForHandoff(created.id, released.revision);
  assert.ok(again.handoffReservedAt, "and the merchant can retry");
});

suite("the public patch route cannot claim reservation authority", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({
    shopDomain: SHOP, runId: "run-1", playId: PLAY, copy: { subject: "Reviewed" },
  });
  const reserved = await reserveCampaignForHandoff(created.id, created.revision);

  // holdsReservation is internal authority. It used to be read straight off the
  // patch object, which came from the request body — so anyone who could call
  // this route could assert it and edit content mid-handoff, nullifying the
  // guard entirely.
  const patched = await fetch(`${api.base}/campaigns/${created.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      draftEdits: { subject: "Snuck in" },
      expectedRevision: reserved.revision,
      holdsReservation: true,
    }),
  });
  assert.equal(patched.status, 409);
  const body = await patched.json();
  assert.equal(body.conflict, "handoff_in_progress");

  const after = await getCampaign(created.id);
  assert.equal(after.draftEdits, null, "the smuggled edit did not land");
  assert.deepEqual(after.copy, { subject: "Reviewed" });
});

suite("unknown patch fields are ignored, not forwarded", async () => {
  await db.resetDatabase();
  await seedRun("run-1");
  const created = await upsertCampaign({ shopDomain: SHOP, runId: "run-1", playId: PLAY });

  const response = await fetch(`${api.base}/campaigns/${created.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      status: "approved",
      expectedRevision: created.revision,
      // None of these are patchable through the public route.
      frozenAt: new Date().toISOString(),
      revision: 999,
      shopDomain: "someone-else.myshopify.com",
      holdsReservation: true,
    }),
  });
  assert.equal(response.status, 200);

  const after = await getCampaign(created.id);
  assert.equal(after.status, "approved", "the allowlisted field applied");
  assert.equal(after.frozenAt, null);
  assert.equal(after.revision, created.revision + 1, "revision is the server's counter, not the client's");
  assert.equal(after.shopDomain, SHOP);
});
