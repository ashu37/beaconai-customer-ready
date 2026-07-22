const express = require("express");
const { config } = require("./config");
const { fetchShopifyData } = require("./services/shopifyClient");
const {
  saveRawShopifyData,
  upsertAllShopifyData,
  getEngineInput,
} = require("./services/shopifyRepository");
const { runMockEngine, saveEngineRun } = require("./services/engineService");
const { narrateAtulRun, readLatestRun, runAtulEngine } = require("./services/atulEngineService");
const { presentEngineRun } = require("./services/engineRunPresenter");
const {
  testKlaviyo,
  getKlaviyoLists,
  getKlaviyoProfiles,
  getKlaviyoTemplates,
  campaignHtml,
  createTemplate,
  createCampaignSendPackage,
  sendCampaign,
  saveKlaviyoAsset,
} = require("./services/klaviyoClient");
const { buildPlaceholderEngineRun } = require("./services/placeholderEngineService");
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
  applyBrandVoiceToCampaign,
  buildBeaconTemplates,
  buildBrandContext,
} = require("./services/brandContextService");
const { getStartupState } = require("./startupState");

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
  res.json({ ok: true, service: "beaconai-api", startup: getStartupState() });
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
    // A caller may still pass an explicit numeric limit to bound the sync.
    const limit = req.body.limit;

    const data = await fetchShopifyData({ shopDomain, accessToken, limit });

    await saveRawShopifyData(shopDomain, data);
    await upsertAllShopifyData(shopDomain, data);

    res.json({
      ok: true,
      shopDomain,
      synced: {
        shop: Boolean(data.shop),
        products: data.products.length,
        customers: data.customers.length,
        orders: data.orders.length,
      },
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
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

router.get("/engine/placeholder/:shopDomain", async (req, res) => {
  try {
    const input = await getEngineInput(req.params.shopDomain);
    const engineRun = buildPlaceholderEngineRun(input);
    res.json({ ok: true, engineRun });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.post("/engine/run", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const input = await getEngineInput(shopDomain);
    const output = runMockEngine(input);
    const run = await saveEngineRun(shopDomain, input, output);

    res.json({ ok: true, engineRunId: run.id, campaign: output });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.post("/engine/atul/run", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const input = await getEngineInput(shopDomain);
    const result = await runAtulEngine(input, {
      shopDomain,
      useFixture: Boolean(req.body.useFixture),
    });
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
      runSummary: {
        data_quality: result.runSummary.data_quality,
        charts_rel: result.runSummary.charts_rel,
        segments: result.runSummary.segments,
        aura_score: result.runSummary.aura_score,
      },
      artifacts: result.artifacts,
      diagnostics: {
        useFixture: result.diagnostics.useFixture,
        exportedRows: result.diagnostics.exportedRows,
      },
    });
  } catch (error) {
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
    const presentedRun = presentEngineRun(latest.engineRun, latest.manifest, null);
    res.json({ ok: true, found: true, presentedRun });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.post("/klaviyo/templates/from-engine", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const privateKey = await resolveKlaviyoKey(req.body);

    const input = await getEngineInput(shopDomain);
    const brandContext = buildBrandContext(input);
    const campaign = applyBrandVoiceToCampaign(req.body.campaign || runMockEngine(input), brandContext);
    const audience = await resolveCampaignAudience(shopDomain, campaign);

    const template = await createTemplate(privateKey, campaign);
    await saveKlaviyoAsset({
      shopDomain,
      assetType: "template",
      externalId: template?.data?.id,
      payload: { template, campaign, audience },
    });

    res.json({ ok: true, campaign, template, audience, brandContext });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

router.post("/klaviyo/campaigns/from-engine", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const privateKey = await resolveKlaviyoKey(req.body);

    const input = await getEngineInput(shopDomain);
    const brandContext = buildBrandContext(input);
    const campaign = applyBrandVoiceToCampaign(req.body.campaign || runMockEngine(input), brandContext);
    const audience = await resolveCampaignAudience(shopDomain, campaign);
    const packageResult = await createCampaignSendPackage(privateKey, campaign, audience);
    const klaviyoCampaignId = packageResult.campaign?.data?.id;

    await saveKlaviyoAsset({
      shopDomain,
      assetType: "campaign_send_package",
      externalId: klaviyoCampaignId,
      payload: { campaign, audience, packageResult },
    });

    res.json({
      ok: true,
      campaign,
      audience,
      brandContext,
      template: packageResult.template,
      list: packageResult.list,
      importJob: packageResult.importJob,
      klaviyoCampaign: packageResult.campaign,
      messages: packageResult.messages,
      assignment: packageResult.assignment,
    });
  } catch (error) {
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

router.post("/campaigns/audience/preview", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const audience = await resolveCampaignAudience(shopDomain, req.body.campaign || {});
    res.json({ ok: true, shopDomain, audience });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.post("/demo/run", async (req, res) => {
  try {
    const { shopDomain, accessToken } = await resolveShopifyConfig(req.body);
    const privateKey = await resolveKlaviyoKey(req.body);
    const limit = req.body.limit || 1000;

    const shopifyData = await fetchShopifyData({ shopDomain, accessToken, limit });
    await saveRawShopifyData(shopDomain, shopifyData);
    await upsertAllShopifyData(shopDomain, shopifyData);

    const input = await getEngineInput(shopDomain);
    const brandContext = buildBrandContext(input);
    const campaign = applyBrandVoiceToCampaign(runMockEngine(input), brandContext);
    const engineRun = await saveEngineRun(shopDomain, input, campaign);

    const template = await createTemplate(privateKey, campaign);
    await saveKlaviyoAsset({
      shopDomain,
      assetType: "template",
      externalId: template?.data?.id,
      payload: template,
    });

    res.json({
      ok: true,
      shopDomain,
      synced: {
        shop: Boolean(shopifyData.shop),
        products: shopifyData.products.length,
        customers: shopifyData.customers.length,
        orders: shopifyData.orders.length,
      },
      engineRunId: engineRun.id,
      campaign,
      brandContext,
      klaviyoTemplate: template,
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

module.exports = { router };
