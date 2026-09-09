const express = require("express");
const { config } = require("./config");
const { fetchShopifyData } = require("./services/shopifyClient");
const {
  saveRawShopifyData,
  upsertAllShopifyData,
  getEngineInput,
  getWeeklySeries,
} = require("./services/shopifyRepository");
const { narrateAtulRun, readLatestRun, runAtulEngine } = require("./services/atulEngineService");
const { presentEngineRun } = require("./services/engineRunPresenter");
const {
  testKlaviyo,
  getKlaviyoLists,
  getKlaviyoProfiles,
  getKlaviyoTemplates,
  campaignHtml,
  createCampaignSendPackage,
  sendCampaign,
  saveKlaviyoAsset,
} = require("./services/klaviyoClient");
const {
  buildShopifyStartUrl,
  handleShopifyCallback,
  buildKlaviyoStartUrl,
  handleKlaviyoCallback,
  getConnectionStatus,
  resolveStoredShopifyToken,
  resolveStoredKlaviyoToken,
} = require("./services/oauthService");
const { resolveCampaignAudience } = require("./services/campaignAudienceService");
const {
  assertReadyForAnalysis,
  getActiveInputSnapshot,
  assertInputVerifiedForHandoff,
  getRunProvenance,
  getSyncStatus,
  runSync,
  SyncNotReadyError,
  UnverifiedInputError,
} = require("./services/syncService");
const {
  applyBrandVoiceToCampaign,
  buildBeaconTemplates,
  buildBrandContext,
} = require("./services/brandContextService");
const { getStartupState } = require("./startupState");
const { generateCampaignCopy } = require("./services/copywriterService");
const { splitAudience } = require("./services/holdoutService");
const {
  measureCampaign,
  summarizeCampaign,
  summarizeProgram,
  staleCampaignIds,
} = require("./services/measurementService");
const {
  CampaignFrozen,
  CampaignRevisionConflict,
  upsertCampaign,
  recordRecipients,
  cacheCopyOnCampaign,
  freezeCampaignAtHandoff,
  getCampaign,
  listCampaigns,
  updateCampaign,
  findCachedCopy,
} = require("./services/campaignService");

// One shape for both write conflicts, so the client can tell "someone else
// changed this" from "this has already been sent" and recover rather than
// retrying blindly. 409, never 500: neither is a server fault.
function campaignConflictResponse(res, error) {
  if (error instanceof CampaignRevisionConflict) {
    res.status(409).json({
      ok: false, error: error.message, conflict: "revision",
      expectedRevision: error.expectedRevision, campaign: error.campaign,
    });
    return true;
  }
  if (error instanceof CampaignFrozen) {
    res.status(409).json({
      ok: false, error: error.message, conflict: "frozen",
      fields: error.fields, campaign: error.campaign,
    });
    return true;
  }
  return false;
}

const router = express.Router();

async function resolveShopifyConfig(body = {}) {
  const shopDomain = body.shopDomain || config.shopify.shopDomain;
  return {
    shopDomain,
    accessToken: body.accessToken || await resolveStoredShopifyToken(shopDomain),
  };
}

async function resolveKlaviyoKey(body = {}) {
  const shopDomain = body.shopDomain || config.shopify.shopDomain;
  return body.privateKey || await resolveStoredKlaviyoToken(shopDomain);
}

router.get("/health", (req, res) => {
  // Liveness — always 200 while the process is up. See server.js: this path is
  // render.yaml's healthCheckPath, so a 503 here would block deploys during a
  // database outage. Database state is in the body; /api/ready is the readiness
  // probe that actually fails.
  res.json({ ok: true, service: "beaconai-api", startup: getStartupState() });
});

router.get("/ready", (req, res) => {
  const startup = getStartupState();
  const ready = startup.database.ready;
  res.status(ready ? 200 : 503).json({ ok: ready, service: "beaconai-api", startup });
});

router.post("/connections/shopify/test", async (req, res) => {
  try {
    const { shopDomain, accessToken } = await resolveShopifyConfig(req.body);
    const limit = req.body.limit || 1;

    const data = await fetchShopifyData({ shopDomain, accessToken, limit });

    res.json({
      ok: true,
      shopDomain,
      counts: {
        products: data.products.length,
        customers: data.customers.length,
        orders: data.orders.length,
        hasShop: Boolean(data.shop),
      },
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

router.post("/connections/klaviyo/test", async (req, res) => {
  try {
    const privateKey = await resolveKlaviyoKey(req.body);
    const data = await testKlaviyo(privateKey);
    res.json({ ok: true, data });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

router.get("/oauth/:provider/start", (req, res) => {
  Promise.resolve()
    .then(async () => {
      const provider = req.params.provider;
      const options = {
        shop: req.query.shop,
        returnTo: req.query.returnTo,
      };
      const url = provider === "shopify"
        ? await buildShopifyStartUrl(options)
        : provider === "klaviyo"
          ? await buildKlaviyoStartUrl(options)
          : null;
      if (!url) {
        res.status(404).json({ ok: false, error: `Unsupported OAuth provider: ${provider}` });
        return;
      }
      res.redirect(url);
    })
    .catch((error) => {
      res.status(500).json({ ok: false, error: error.message });
    });
});

router.get("/oauth/:provider/callback", (req, res) => {
  Promise.resolve()
    .then(async () => {
      const provider = req.params.provider;
      const result = provider === "shopify"
        ? await handleShopifyCallback(req.query)
        : provider === "klaviyo"
          ? await handleKlaviyoCallback(req.query)
          : null;
      if (!result) {
        res.status(404).json({ ok: false, error: `Unsupported OAuth provider: ${provider}` });
        return;
      }
      res.redirect(result.redirectTo);
    })
    .catch((error) => {
      res.status(500).json({ ok: false, error: error.message });
    });
});

router.get("/connections/status", async (req, res) => {
  try {
    const shopDomain = req.query.shopDomain || config.shopify.shopDomain;
    const status = await getConnectionStatus(shopDomain);
    res.json({ ok: true, status });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.get("/brand/context", async (req, res) => {
  try {
    const shopDomain = req.query.shopDomain || config.shopify.shopDomain;
    const input = await getEngineInput(shopDomain);
    const brandContext = buildBrandContext(input);
    res.json({ ok: true, shopDomain, brandContext });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

// CA-1: customer-facing copywriter. Context is assembled SERVER-SIDE (never
// trust client-sent brand context). Absent key or any failure => available:false
// and the UI silently keeps the static copy.
router.post("/copy/generate", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const { playId, templateId, regenerate, lockedSlots, steer } = req.body;
    if (!playId) {
      res.status(400).json({ ok: false, error: "playId is required" });
      return;
    }

    const input = await getEngineInput(shopDomain);
    const brandContext = buildBrandContext(input);
    const beaconTemplates = buildBeaconTemplates(brandContext);
    const template = beaconTemplates.find((t) => t.id === templateId) || beaconTemplates[0] || null;

    // Find the play in the latest run (read-only; never triggers an engine run).
    const latest = await readLatestRun({ shopDomain });
    const presented = latest ? presentEngineRun(latest.engineRun, latest.manifest, latest.narration || null) : null;
    const play = presented
      ? [...(presented.recommendations || []), ...(presented.considered || [])].find((p) => p.play_id === playId || p.id === playId)
      : null;
    if (!play) {
      res.json({ ok: true, available: false, reason: "play_not_found" });
      return;
    }

    const products = (brandContext.productLanguage?.bestSellers || []).map((p) => ({
      id: String(p.id),
      title: p.title,
      productType: p.productType || null,
      imageUrl: p.imageUrl || null,
    }));
    const runId = latest?.runId || presented?.run_id || null;
    const resolvedTemplateId = template?.id || null;

    // Generated copy is cached on the campaign row rather than in process
    // memory, so it survives a restart — copy that silently changes between
    // sessions reads as the product being unreliable. A rewrite (regenerate)
    // always calls the model fresh, because it depends on the locked slots.
    if (runId && !regenerate) {
      const cached = await findCachedCopy({ shopDomain, runId, playId, templateId: resolvedTemplateId });
      if (cached) {
        res.json({ ok: true, available: true, ...cached, cached: true });
        return;
      }
    }

    const result = await generateCampaignCopy({
      play, brandContext, template, products,
      regenerate: Boolean(regenerate), lockedSlots: lockedSlots || null, steer: steer || null,
    });

    if (result.available && runId) {
      // Best-effort: a caching failure must never fail copy generation.
      try {
        await cacheCopyOnCampaign({
          shopDomain, runId, playId, templateId: resolvedTemplateId,
          copy: {
            copy: result.copy,
            fallback_slots: result.fallback_slots,
            playbook_version: result.playbook_version,
          },
        });
      } catch (_) {}
    }

    // CA-5: resolve featured_product_id → { title, imageUrl } for the image block.
    if (result.available && result.copy?.featured_product_id) {
      const p = products.find((x) => String(x.id) === String(result.copy.featured_product_id));
      if (p && p.imageUrl) result.copy.featured_product = { title: p.title, imageUrl: p.imageUrl };
    }

    res.json({ ok: true, ...result });
  } catch (error) {
    // Fail soft: the Copy step must never show an error. available:false => static.
    res.json({ ok: true, available: false, reason: error.message });
  }
});

router.get("/klaviyo/lists", async (req, res) => {
  try {
    const data = await getKlaviyoLists(await resolveKlaviyoKey(req.query));
    res.json({ ok: true, data });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

router.get("/klaviyo/profiles", async (req, res) => {
  try {
    const data = await getKlaviyoProfiles(await resolveKlaviyoKey(req.query));
    res.json({ ok: true, data });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

router.get("/klaviyo/templates", async (req, res) => {
  try {
    const shopDomain = req.query.shopDomain || config.shopify.shopDomain;
    const input = await getEngineInput(shopDomain);
    const brandContext = buildBrandContext(input);
    const beaconTemplates = buildBeaconTemplates(brandContext);
    const data = await getKlaviyoTemplates(await resolveKlaviyoKey(req.query));
    const existingTemplates = (data.data || []).map((template) => ({
      id: template.id,
      source: "klaviyo",
      name: template.attributes?.name || template.id,
      subject: template.attributes?.name || "Existing Klaviyo template",
      previewText: "Existing template from Klaviyo.",
      bodyH2: template.attributes?.name || "Existing Klaviyo template",
      bodyP1: "This template already exists in Klaviyo and can be paired with a BeaconAI play.",
      cta: "Use existing template",
    }));

    res.json({
      ok: true,
      templates: [...existingTemplates, ...beaconTemplates],
      brandContext,
      source: data.mock ? "beacon-fallback" : "klaviyo",
    });
  } catch (error) {
    const input = await getEngineInput(req.query.shopDomain || config.shopify.shopDomain);
    const brandContext = buildBrandContext(input);
    res.json({
      ok: true,
      templates: buildBeaconTemplates(brandContext),
      brandContext,
      source: "beacon-fallback",
      warning: error.response?.data || error.message,
    });
  }
});

router.post("/sync/shopify", async (req, res) => {
  try {
    const { shopDomain, accessToken } = await resolveShopifyConfig(req.body);
    // No default cap: undefined limit paginates every resource to completion.
    // A caller may still pass an explicit numeric limit to bound the sync — and
    // if that limit stops a resource mid-stream, the sync is recorded as
    // INCOMPLETE and never published. A bounded fetch is a diagnostic, not
    // store data.
    const limit = req.body.limit;
    const connection = await getConnectionStatus(shopDomain).catch(() => null);

    const result = await runSync({
      shopDomain,
      accessToken,
      limit,
      shopifyScope: connection?.shopify?.scopes || null,
    });

    if (!result.published) {
      // 200, not 500: the fetch worked, and the honest answer is that what came
      // back is not usable. The body says which, so the UI can say so too.
      res.status(200).json({
        ok: true,
        published: false,
        shopDomain,
        syncRunId: result.syncRunId,
        status: result.status,
        validationFailures: result.validationFailures || [],
        resources: result.resourceManifest || null,
        coverage: result.declaredCoverage || null,
      });
      return;
    }

    res.json({
      ok: true,
      published: true,
      shopDomain,
      syncRunId: result.syncRunId,
      status: result.status,
      coverage: result.declaredCoverage,
      resources: result.resourceManifest,
      synced: {
        shop: result.counts.shop,
        products: result.counts.products,
        customers: result.counts.customers,
        orders: result.counts.orders,
      },
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      syncRunId: error.syncRunId || null,
      error: error.response?.data || error.message,
    });
  }
});

// What this store's data actually is: which sync the clean tables represent,
// how much history it covers, whether a new analysis may run, and whether the
// briefing on screen was built from the current input.
router.get("/sync/status/:shopDomain", async (req, res) => {
  try {
    const status = await getSyncStatus(req.params.shopDomain);
    res.json({ ok: true, ...status });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.get("/engine/input/:shopDomain", async (req, res) => {
  try {
    const input = await getEngineInput(req.params.shopDomain);
    res.json({ ok: true, input });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

// D6b: weekly order + new-customer series for briefing sparklines. Read-only.
router.get("/stats/series/:shopDomain", async (req, res) => {
  try {
    const weeks = req.query.weeks || 12;
    const series = await getWeeklySeries(req.params.shopDomain, weeks);
    res.json({ ok: true, weeks: series });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.post("/engine/atul/run", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const useFixture = Boolean(req.body.useFixture);

    // The gate lives here, not on a disabled button. A fixture run is exempt
    // because it reads none of the merchant's data — it is labelled `fixture`
    // on the run row so it can never be mistaken for their briefing.
    let snapshot = null;
    let syncRunId = null;
    if (!useFixture) {
      await assertReadyForAnalysis(shopDomain);
      const active = await getActiveInputSnapshot(shopDomain);
      if (!active) {
        throw new SyncNotReadyError({
          ready: false,
          reasons: [{ code: "no_input_snapshot", message: "The active sync has no stored input snapshot. Re-sync before running an analysis." }],
        });
      }
      snapshot = active.snapshot;
      syncRunId = active.syncRunId;
    }

    // getEngineInput still supplies brand/product context; the ORDERS the
    // engine reads come from `snapshot`.
    const input = await getEngineInput(shopDomain);
    const result = await runAtulEngine(input, { shopDomain, useFixture, snapshot, syncRunId });
    let narration = null;
    try {
      narration = await narrateAtulRun(result);
    } catch (narrationError) {
      narration = {
        error: narrationError.message,
      };
    }
    const presentedRun = presentEngineRun(result.engineRun, result.manifest, narration);

    res.json({
      ok: true,
      shopDomain,
      engineRun: result.engineRun,
      presentedRun,
      narration,
      manifest: result.manifest,
      syncRunId: result.syncRunId,
      inputProvenance: result.inputProvenance,
    });
  } catch (error) {
    if (error instanceof SyncNotReadyError) {
      res.status(409).json({ ok: false, error: error.message, readiness: error.readiness });
      return;
    }
    res.status(500).json({
      ok: false,
      error: error.message,
      stdout: error.stdout,
      stderr: error.stderr,
    });
  }
});

// O1: read-only latest-run rehydration. Never triggers an engine run.
router.get("/engine/atul/latest/:shopDomain", async (req, res) => {
  try {
    const shopDomain = req.params.shopDomain || config.shopify.shopDomain;
    const latest = await readLatestRun({ shopDomain });
    if (!latest) {
      res.json({ ok: true, found: false });
      return;
    }
    // Serve the narration PERSISTED at run time (keyed to run_id). No LLM call
    // on refresh — same run → same prose. null when a run predates persistence,
    // in which case the presenter renders data chips (no templated prose).
    const presentedRun = presentEngineRun(latest.engineRun, latest.manifest, latest.narration || null);
    res.json({
      ok: true,
      found: true,
      presentedRun,
      syncRunId: latest.syncRunId,
      inputProvenance: latest.inputProvenance,
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.post("/klaviyo/campaigns/from-engine", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const privateKey = await resolveKlaviyoKey(req.body);
    if (!req.body.campaign) {
      res.status(400).json({ ok: false, error: "campaign is required" });
      return;
    }

    const input = await getEngineInput(shopDomain);
    const brandContext = buildBrandContext(input);
    const campaign = applyBrandVoiceToCampaign(req.body.campaign, brandContext);
    // ONE run, resolved once, then used for everything: the provenance check,
    // the audience, and the campaign row. Verifying one run while the audience
    // came from another would let a verified run id authorize membership from a
    // different, unverified one — and would silently re-send an older campaign
    // to today's audience. Falling back to the latest run happens HERE, before
    // the check, never inside audience resolution afterwards.
    //
    // An EXISTING campaign settles it outright: the campaign's own run is its
    // origin, and the audience must come from there however old it is. Reading
    // the latest run instead would send a reviewed campaign to a membership
    // nobody reviewed.
    const existingCampaign = req.body.campaignId
      ? await getCampaign(Number.parseInt(req.body.campaignId, 10))
      : null;
    if (req.body.campaignId && !existingCampaign) {
      res.status(404).json({ ok: false, error: `No campaign ${req.body.campaignId}` });
      return;
    }
    if (existingCampaign && existingCampaign.shopDomain !== shopDomain) {
      res.status(404).json({ ok: false, error: `No campaign ${req.body.campaignId}` });
      return;
    }
    const runId = existingCampaign?.runId
      || campaign.run_id || req.body.runId
      || (await readLatestRun({ shopDomain }))?.runId || null;

    // Nothing built on input we cannot vouch for reaches a real customer. This
    // runs BEFORE the audience is resolved or anything is written, so a blocked
    // handoff leaves no half-made campaign behind. Every run predating verified
    // sync — including anything the partial-sync incident produced — is
    // legacy_unverified and stops here until the store is re-synced.
    const provenance = await assertInputVerifiedForHandoff(runId, shopDomain);
    const audience = await resolveCampaignAudience(shopDomain, campaign, { runId });

    // Split the audience before anything reaches Klaviyo. The held-out arm is
    // what turns "these customers bought $X" into "this campaign earned $X".
    const playId = existingCampaign?.playId || campaign.play_id || campaign.id;
    let split = { treated: audience.recipients || [], holdout: [], holdoutPct: 0 };
    let campaignRow = null;

    if (audience.materialized && playId) {
      campaignRow = existingCampaign || await upsertCampaign({
        shopDomain, runId, playId,
        displayName: campaign.play_name || campaign.name || null,
        expectedRevision: req.body.expectedRevision,
      });

      // A campaign already handed off cannot be handed off again. Sending a
      // changed version is a new campaign; re-running this one would rewrite the
      // record of an email that has already gone out.
      if (campaignRow.frozen) {
        throw new CampaignFrozen(campaignRow, ["handoff"]);
      }
      split = splitAudience(shopDomain, audience.recipients, campaignRow.holdoutPct ?? 0.1);

      // Recipients are persisted BEFORE the send, deliberately. If this write
      // fails we must not send: a campaign whose split was never recorded can
      // never be measured, and an unmeasurable send is worse than a late one.
      await recordRecipients(campaignRow.id, split);
      await updateCampaign(campaignRow.id, {
        audienceSize: split.treated.length + split.holdout.length,
        holdoutSize: split.holdout.length,
        holdoutPct: split.holdoutPct,
      });
    }

    // Only the treated arm goes to Klaviyo. The holdout is, by definition, the
    // group that receives nothing.
    const sendAudience = { ...audience, recipients: split.treated, count: split.treated.length };
    const packageResult = await createCampaignSendPackage(privateKey, campaign, sendAudience);
    const klaviyoCampaignId = packageResult.campaign?.data?.id;

    // Freeze what was actually sent: the approved copy, the exact HTML that went
    // to Klaviyo, and the audience as a reference plus a hash of its membership.
    // From here the row records delivery state and nothing else changes.
    if (campaignRow) {
      campaignRow = await freezeCampaignAtHandoff(campaignRow.id, {
        approvedCopy: campaign,
        renderedHtml: packageResult.html || packageResult.template?.html || null,
        templateVersion: campaign.template_id || campaign.templateId || null,
        audienceRef: {
          runId,
          audienceDefinitionId: audience.audienceDefinitionId || null,
          memberCount: audience.memberCount ?? null,
          treated: split.treated.length,
          holdout: split.holdout.length,
          holdoutPct: split.holdoutPct,
        },
        customerIds: (audience.recipients || []).map((r) => r.customerId),
      });
      if (klaviyoCampaignId) {
        campaignRow = await updateCampaign(campaignRow.id, { klaviyoCampaignId });
      }
    }

    await saveKlaviyoAsset({
      shopDomain,
      assetType: "campaign_send_package",
      externalId: klaviyoCampaignId,
      payload: { campaign, audience, packageResult, holdout: { treated: split.treated.length, held: split.holdout.length, pct: split.holdoutPct } },
    });

    res.json({
      ok: true,
      campaign,
      audience,
      // What the merchant is told at send time: who receives it, who is held
      // back, and why the held-back group exists.
      holdout: {
        treated: split.treated.length,
        held: split.holdout.length,
        pct: split.holdoutPct,
      },
      brandContext,
      campaign_record: campaignRow,
      inputProvenance: provenance.provenance,
      syncRunId: provenance.syncRunId,
      template: packageResult.template,
      list: packageResult.list,
      importJob: packageResult.importJob,
      klaviyoCampaign: packageResult.campaign,
      messages: packageResult.messages,
      assignment: packageResult.assignment,
    });
  } catch (error) {
    if (error instanceof UnverifiedInputError) {
      res.status(409).json({
        ok: false,
        error: error.message,
        inputProvenance: error.provenance,
        blocked: "unverified_input",
      });
      return;
    }
    if (campaignConflictResponse(res, error)) return;
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

// A2: read-only preview of the exact campaignHtml that would be pushed to
// Klaviyo as a CODE template. Makes zero Klaviyo API calls and works with
// Klaviyo disconnected. Must NOT create templates, lists, or campaigns.
router.post("/klaviyo/campaigns/preview-html", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const draft = req.body.campaign || req.body;
    let brandContext = draft.brandContext || req.body.brandContext;
    if (!brandContext) {
      const input = await getEngineInput(shopDomain);
      brandContext = buildBrandContext(input);
    }
    const html = campaignHtml({ ...draft, brandContext });
    res.json({ ok: true, html });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

router.post("/klaviyo/campaigns/send", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const privateKey = await resolveKlaviyoKey(req.body);
    const campaignId = req.body.campaignId;
    if (!campaignId) throw new Error("campaignId is required to send a Klaviyo campaign.");

    const sendJob = await sendCampaign(privateKey, campaignId);
    await saveKlaviyoAsset({
      shopDomain,
      assetType: "campaign_send_job",
      externalId: sendJob?.data?.id || campaignId,
      payload: { campaignId, sendJob },
    });

    res.json({ ok: true, campaignId, sendJob });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

// Campaign persistence. The frontend still keeps its own state in this phase;
// these endpoints give it somewhere durable to move to next.
router.post("/campaigns", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const {
      runId, playId, status, templateId, copy, draftEdits, klaviyoCampaignId,
      holdoutPct, displayName, expectedRevision,
    } = req.body;
    const campaign = await upsertCampaign({
      shopDomain, runId, playId, status, templateId, copy, draftEdits, klaviyoCampaignId,
      holdoutPct, displayName, expectedRevision,
    });
    res.json({ ok: true, campaign });
  } catch (error) {
    if (campaignConflictResponse(res, error)) return;
    res.status(400).json({ ok: false, error: error.message });
  }
});

// Every campaign for this shop, across every run — newest first. Pass ?runId= to
// scope to one run.
router.get("/campaigns/:shopDomain", async (req, res) => {
  try {
    const campaigns = await listCampaigns(req.params.shopDomain, { runId: req.query.runId || null });
    res.json({ ok: true, campaigns });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.patch("/campaigns/:id", async (req, res) => {
  try {
    const id = Number.parseInt(req.params.id, 10);
    if (!Number.isFinite(id)) {
      res.status(400).json({ ok: false, error: "campaign id must be numeric" });
      return;
    }
    const campaign = await updateCampaign(id, req.body || {});
    if (!campaign) {
      res.status(404).json({ ok: false, error: `No campaign ${id}` });
      return;
    }
    res.json({ ok: true, campaign });
  } catch (error) {
    if (campaignConflictResponse(res, error)) return;
    res.status(400).json({ ok: false, error: error.message });
  }
});

// One campaign's measurement. Recomputes when the stored numbers are stale —
// at this volume that is cheap enough to do on read rather than on a schedule.
router.get("/campaigns/:id/results", async (req, res) => {
  try {
    const id = Number.parseInt(req.params.id, 10);
    if (!Number.isFinite(id)) {
      res.status(400).json({ ok: false, error: "campaign id must be numeric" });
      return;
    }
    const summary = req.query.refresh === "false"
      ? await summarizeCampaign(id)
      : await measureCampaign(id);
    res.json({ ok: true, ...summary });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

// Every sent campaign for a shop, measured. Stale ones are recomputed first, so
// the page never reports numbers that are a week old without saying so.
router.get("/results/:shopDomain", async (req, res) => {
  try {
    const shopDomain = req.params.shopDomain;
    for (const id of await staleCampaignIds(shopDomain)) {
      await measureCampaign(id).catch(() => {});
    }
    const campaigns = await listCampaigns(shopDomain);
    const sent = campaigns.filter((c) => c.sentAt);
    const results = [];
    for (const campaign of sent) {
      const summary = await summarizeCampaign(campaign.id);
      results.push({ ...summary, playId: campaign.playId, sentAt: campaign.sentAt,
        audienceSize: campaign.audienceSize, holdoutSize: campaign.holdoutSize });
    }
    const program = await summarizeProgram(shopDomain);
    res.json({ ok: true, program, results });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.post("/campaigns/audience/preview", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const campaign = req.body.campaign || {};
    const runId = campaign.run_id || req.body.runId || (await readLatestRun({ shopDomain }))?.runId || null;
    const audience = await resolveCampaignAudience(shopDomain, campaign, { runId });

    // Show the merchant the same split the send will actually perform, computed
    // by the same function — so the number on screen is a promise, not an
    // estimate. Nobody should discover the holdout after the fact.
    let holdout = null;
    if (audience.materialized) {
      const playId = campaign.play_id || campaign.id;
      const existing = runId && playId
        ? (await listCampaigns(shopDomain, { runId })).find((c) => c.playId === playId)
        : null;
      const split = splitAudience(shopDomain, audience.recipients, existing?.holdoutPct ?? 0.1);
      holdout = { treated: split.treated.length, held: split.holdout.length, pct: split.holdoutPct };
    }

    const provenance = runId ? await getRunProvenance(runId) : null;
    const foreign = Boolean(provenance && provenance.shopDomain !== shopDomain);
    res.json({
      ok: true,
      shopDomain,
      audience,
      holdout,
      // So the UI can say why a send is blocked before the merchant clicks it,
      // rather than only after.
      runId,
      inputProvenance: foreign ? "foreign_run" : provenance?.provenance || (runId ? "unknown_run" : null),
      sendable: Boolean(provenance) && !foreign && !["fixture", "legacy_unverified"].includes(provenance.provenance),
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

module.exports = { router };
