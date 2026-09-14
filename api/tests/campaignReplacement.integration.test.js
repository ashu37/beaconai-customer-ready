const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");
const {
  createReplacementDraft,
  getCampaign,
  listCampaigns,
  upsertCampaign,
} = require("../src/services/campaignService");

// Campaign continuity, step 3: an updated draft on the latest analysis, made
// from an older draft only when the merchant asks for it
// (docs/CAMPAIGN_CONTINUITY_SPEC.md, rule 2).
const SHOP = "replacement-shop.myshopify.com";
const OTHER_SHOP = "replacement-other.myshopify.com";
const PLAY = "winback_dormant_cohort";

let api;
test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

async function seedRun(runId, shopDomain = SHOP) {
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run, input_provenance)
     VALUES ($1, $2, 'store', '{}'::jsonb, 'verified')`,
    [runId, shopDomain]
  );
}

async function olderDraft(fields = {}) {
  const created = await upsertCampaign({
    shopDomain: SHOP, runId: "run-old", playId: PLAY, status: "draft",
    displayName: "Bring back lapsed customers", templateId: "beacon-winback-clean",
    copy: { copy: { subject_variants: ["Generated subject"] } },
    // An intentional blank: the merchant removed the second paragraph.
    draftEdits: { subject: "Merchant subject", bodyP2: "" },
    destinationUrl: "https://shop.example/winback",
  });
  if (!Object.keys(fields).length) return created;
  return upsertCampaign({ shopDomain: SHOP, runId: "run-old", playId: PLAY, expectedRevision: created.revision, ...fields });
}

suite("an updated draft copies the merchant's saved content, starts unapproved, and links both", async () => {
  await db.resetDatabase();
  await seedRun("run-old");
  await seedRun("run-new");
  const old = await olderDraft({ status: "approved" });

  const response = await api.post(`/campaigns/${old.id}/replacement`, {
    shopDomain: SHOP, runId: "run-new", expectedRevision: old.revision,
  });
  assert.equal(response.status, 200, JSON.stringify(response.body));
  const { campaign, previous } = response.body;

  assert.equal(campaign.runId, "run-new");
  assert.equal(campaign.playId, PLAY);
  assert.equal(campaign.status, "draft", "the replacement is not approved");
  assert.equal(campaign.approvedAt, null);
  assert.deepEqual(campaign.draftEdits, { subject: "Merchant subject", bodyP2: "" }, "edits, including the intentional blank");
  assert.equal(campaign.templateId, "beacon-winback-clean");
  assert.deepEqual(campaign.copy, { copy: { subject_variants: ["Generated subject"] } }, "the copy they saw, so nothing is regenerated away");
  assert.equal(campaign.destinationUrl, "https://shop.example/winback");
  assert.equal(campaign.supersedesId, old.id);

  assert.equal(previous.id, old.id);
  assert.equal(previous.supersededById, campaign.id);
  assert.ok(previous.supersededAt);
  assert.equal(previous.status, "approved", "the old campaign keeps its own status");
  assert.equal(previous.revision, old.revision + 1);

  // The list carries each campaign's analysis date for the briefing.
  const listed = await listCampaigns(SHOP);
  assert.ok(listed.every((c) => c.runAnalysedAt), "analysis date joined in");
});

suite("asking twice returns the same replacement rather than a second one", async () => {
  await db.resetDatabase();
  await seedRun("run-old");
  await seedRun("run-new");
  const old = await olderDraft();

  const [a, b] = await Promise.all([
    api.post(`/campaigns/${old.id}/replacement`, { shopDomain: SHOP, runId: "run-new", expectedRevision: old.revision }),
    api.post(`/campaigns/${old.id}/replacement`, { shopDomain: SHOP, runId: "run-new", expectedRevision: old.revision }),
  ]);
  assert.equal(a.status, 200, JSON.stringify(a.body));
  assert.equal(b.status, 200, JSON.stringify(b.body));
  assert.equal(a.body.campaign.id, b.body.campaign.id);
  const onNew = (await listCampaigns(SHOP)).filter((c) => c.runId === "run-new");
  assert.equal(onNew.length, 1, "exactly one replacement exists");
});

suite("nothing is superseded when the replacement cannot be made", async () => {
  await db.resetDatabase();
  await seedRun("run-old");
  await seedRun("run-new");
  await seedRun("run-foreign", OTHER_SHOP);
  const old = await olderDraft();

  // A stale revision: the draft changed since the merchant read it.
  const stale = await api.post(`/campaigns/${old.id}/replacement`, { shopDomain: SHOP, runId: "run-new", expectedRevision: old.revision - 1 });
  assert.equal(stale.status, 409);
  assert.equal(stale.body.conflict, "revision");

  // Another shop's analysis.
  const foreign = await api.post(`/campaigns/${old.id}/replacement`, { shopDomain: SHOP, runId: "run-foreign", expectedRevision: old.revision });
  assert.equal(foreign.status, 409);
  assert.equal(foreign.body.code, "unknown_run");

  // The same analysis it already belongs to.
  const same = await api.post(`/campaigns/${old.id}/replacement`, { shopDomain: SHOP, runId: "run-old", expectedRevision: old.revision });
  assert.equal(same.body.code, "same_run");

  // The latest analysis already has a live campaign for this play.
  const existing = await upsertCampaign({ shopDomain: SHOP, runId: "run-new", playId: PLAY, status: "draft" });
  const taken = await api.post(`/campaigns/${old.id}/replacement`, { shopDomain: SHOP, runId: "run-new", expectedRevision: old.revision });
  assert.equal(taken.status, 409);
  assert.equal(taken.body.code, "campaign_exists");
  assert.equal(taken.body.campaign.id, existing.id);

  const after = await getCampaign(old.id);
  assert.equal(after.supersededById, null, "the old draft is untouched by every refusal");
  assert.equal(after.revision, old.revision);
});

suite("a handed-off campaign is never replaced, and a replaced draft cannot be handed off", async () => {
  await db.resetDatabase();
  await seedRun("run-old");
  await seedRun("run-new");
  const old = await olderDraft();

  await query(`UPDATE clean.campaigns SET klaviyo_campaign_id = 'K1', delivery_state = 'created' WHERE id = $1`, [old.id]);
  const handedOff = await api.post(`/campaigns/${old.id}/replacement`, { shopDomain: SHOP, runId: "run-new", expectedRevision: old.revision });
  assert.equal(handedOff.status, 409);
  assert.equal(handedOff.body.code, "not_editable");

  await query(`UPDATE clean.campaigns SET klaviyo_campaign_id = NULL, delivery_state = 'not_started' WHERE id = $1`, [old.id]);
  const made = await createReplacementDraft({ shopDomain: SHOP, campaignId: old.id, runId: "run-new", expectedRevision: old.revision });
  assert.ok(made.campaign.id);

  const handoff = await api.post("/klaviyo/campaigns/from-engine", {
    shopDomain: SHOP, campaignId: old.id, expectedRevision: made.previous.revision,
    expectedTemplateVersion: 1, expectedRenderFingerprint: "f",
    campaign: { id: String(old.id), play_id: PLAY, run_id: "run-old", subject: "s" },
  });
  assert.equal(handoff.status, 409);
  assert.equal(handoff.body.code, "superseded");
  assert.equal(handoff.body.replacementId, made.campaign.id);
});

suite("a dismissed campaign on the new analysis gives up its slot to the replacement", async () => {
  await db.resetDatabase();
  await seedRun("run-old");
  await seedRun("run-new");
  const old = await olderDraft();
  const dismissed = await upsertCampaign({ shopDomain: SHOP, runId: "run-new", playId: PLAY, status: "dismissed" });

  const made = await createReplacementDraft({ shopDomain: SHOP, campaignId: old.id, runId: "run-new", expectedRevision: old.revision });
  assert.equal(made.campaign.id, dismissed.id, "the unique (run, play) slot is reused");
  assert.equal(made.campaign.status, "draft");
  assert.deepEqual(made.campaign.draftEdits, { subject: "Merchant subject", bodyP2: "" });
  assert.equal(made.previous.supersededById, dismissed.id);
});

suite("another shop cannot replace this shop's campaign", async () => {
  await db.resetDatabase();
  await seedRun("run-old");
  await seedRun("run-new");
  const old = await olderDraft();
  const response = await api.post(
    `/campaigns/${old.id}/replacement`,
    { shopDomain: OTHER_SHOP, runId: "run-new", expectedRevision: old.revision },
  );
  assert.equal(response.status, 404);
  assert.equal((await getCampaign(old.id)).supersededById, null);
});

// A dismissed campaign on the new analysis can still have been handed off first.
// Dismissed says nothing about that; reusing its slot would overwrite the record
// of what went to the provider.
suite("a dismissed campaign that was handed off is never reused as the replacement", async () => {
  const lockedStates = [
    ["frozen", `frozen_at = NOW()`],
    ["reserved", `handoff_reserved_at = NOW()`],
    ["created in the provider", `klaviyo_campaign_id = 'K9', delivery_state = 'created'`],
    ["scheduled", `delivery_state = 'scheduled'`],
  ];
  for (const [label, setClause] of lockedStates) {
    await db.resetDatabase();
    await seedRun("run-old");
    await seedRun("run-new");
    const old = await olderDraft();
    const target = await upsertCampaign({
      shopDomain: SHOP, runId: "run-new", playId: PLAY, status: "draft",
      draftEdits: { subject: "What was handed off" },
    });
    await query(`UPDATE clean.campaigns SET status = 'dismissed', ${setClause} WHERE id = $1`, [target.id]);
    const before = await getCampaign(target.id);

    const response = await api.post(`/campaigns/${old.id}/replacement`, {
      shopDomain: SHOP, runId: "run-new", expectedRevision: old.revision,
    });
    assert.equal(response.status, 409, `${label}: ${JSON.stringify(response.body)}`);
    assert.equal(response.body.code, "campaign_exists", label);

    const after = await getCampaign(target.id);
    assert.deepEqual(after.draftEdits, { subject: "What was handed off" }, `${label}: its content is untouched`);
    assert.equal(after.revision, before.revision, `${label}: not written at all`);
    assert.equal(after.supersedesId, null, label);
    assert.equal((await getCampaign(old.id)).supersededById, null, `${label}: the source draft is not superseded`);
  }
});
