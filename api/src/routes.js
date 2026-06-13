const express = require("express");
const { config } = require("./config");
const { fetchShopifyData } = require("./services/shopifyClient");
const {
  saveRawShopifyData,
  upsertAllShopifyData,
  getEngineInput,
} = require("./services/shopifyRepository");
const { runMockEngine, saveEngineRun } = require("./services/engineService");
const { runAtulEngine } = require("./services/atulEngineService");
const { presentEngineRun } = require("./services/engineRunPresenter");
const {
  testKlaviyo,
  getKlaviyoLists,
  getKlaviyoProfiles,
  getKlaviyoTemplates,
  createTemplate,
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
  res.json({ ok: true, service: "beaconai-api" });
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
  const beaconTemplates = [
    {
      id: "beacon-winback-clean",
      source: "beacon",
      name: "BeaconAI winback offer",
      subject: "A fresh reason to come back",
      previewText: "A concise returning-customer campaign generated from the selected play.",
      bodyH2: "Your next favorite is ready.",
      bodyP1: "Use this draft when the engine recommends reactivating previous buyers.",
      cta: "Shop the edit",
    },
    {
      id: "beacon-second-purchase",
      source: "beacon",
      name: "BeaconAI second purchase journey",
      subject: "Make the most of your first order",
      previewText: "Education and complementary-product copy for first-time buyers.",
      bodyH2: "Here is what pairs well with your first pick.",
      bodyP1: "Use this draft for first-to-second purchase recommendations.",
      cta: "See recommendations",
    },
    {
      id: "beacon-lifecycle-soft-nudge",
      source: "beacon",
      name: "BeaconAI lifecycle nudge",
      subject: "Picked for where you are now",
      previewText: "A flexible lifecycle template for lower-confidence plays.",
      bodyH2: "A small nudge, matched to your timing.",
      bodyP1: "Use this draft when BeaconAI recommends a measured experiment.",
      cta: "Explore now",
    },
  ];

  try {
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
      source: data.mock ? "beacon-fallback" : "klaviyo",
    });
  } catch (error) {
    res.json({
      ok: true,
      templates: beaconTemplates,
      source: "beacon-fallback",
      warning: error.response?.data || error.message,
    });
  }
});

router.post("/sync/shopify", async (req, res) => {
  try {
    const { shopDomain, accessToken } = await resolveShopifyConfig(req.body);
    const limit = req.body.limit || 1000;

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
    const presentedRun = presentEngineRun(result.engineRun, result.manifest);

    res.json({
      ok: true,
      shopDomain,
      engineRun: result.engineRun,
      presentedRun,
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

router.post("/klaviyo/templates/from-engine", async (req, res) => {
  try {
    const shopDomain = req.body.shopDomain || config.shopify.shopDomain;
    const privateKey = await resolveKlaviyoKey(req.body);

    const input = await getEngineInput(shopDomain);
    const campaign = req.body.campaign || runMockEngine(input);

    const template = await createTemplate(privateKey, campaign);
    await saveKlaviyoAsset({
      shopDomain,
      assetType: "template",
      externalId: template?.data?.id,
      payload: template,
    });

    res.json({ ok: true, campaign, template });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
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
    const campaign = runMockEngine(input);
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
      klaviyoTemplate: template,
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

module.exports = { router };
