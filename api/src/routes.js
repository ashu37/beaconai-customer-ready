const express = require("express");
const { config } = require("./config");
const { query } = require("./db");
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
  createCampaignSendPackage,
  sendCampaign,
  saveKlaviyoAsset,
  campaignNameForProvider,
  getKlaviyoSender,
} = require("./services/klaviyoClient");
// Referenced through the module object rather than destructured, so the provider
// lookups the reconcile route performs can be intercepted. The bug this guards
// against was a lambda quietly dropping an argument on its way to the client —
// invisible at every level except the wiring itself.
const klaviyoClient = require("./services/klaviyoClient");
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
  authorizedForShop,
  authorizedShop,
  issueSession,
  requireShopSession,
  sessionCookie,
  sessionFromRequest,
} = require("./services/sessionService");
const {
  DeliveryTransitionRejected,
  getDelivery,
  transitionDelivery,
} = require("./services/deliveryStateService");
const { reconcileCampaign } = require("./services/reconciliationService");
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
  BrandSetupRequired,
  BrandTemplateInvalid,
  MissingDestination,
  SlotValueRejected,
  buildStarterShell,
  renderBrandEmail,
  slotValuesForCampaign,
} = require("./services/brandEmailRenderer");
const {
  getActiveBrandTemplate,
  getBrandTemplateVersion,
  listBrandTemplates,
  requireActiveBrandTemplate,
  saveBrandTemplate,
} = require("./services/brandEmailTemplateService");
const {
  applyBrandVoiceToCampaign,
  buildBeaconTemplates,
  buildBrandContext,
  finalizeCampaignForRender,
} = require("./services/brandContextService");
const crypto = require("node:crypto");

// A short fingerprint of the exact bytes that were previewed. The merchant
// approves a specific rendering; this is how the handoff proves it is sending
// that one and not something rebuilt differently in the meantime.
function renderFingerprint(html) {
  return crypto.createHash("sha256").update(String(html)).digest("hex").slice(0, 16);
}
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
  CampaignHandoffInProgress,
  CampaignRevisionConflict,
  CampaignRevisionRequired,
  releaseHandoffReservation,
  reserveCampaignForHandoff,
  upsertCampaign,
  recordRecipients,
  cacheCopyOnCampaign,
  freezeCampaignAtHandoff,
  getCampaign,
  listCampaigns,
  updateCampaign,
  findCachedCopy,
} = require("./services/campaignService");

// The only fields a client may set through the public patch route. Notably
// absent: holdsReservation, which is internal authority and now travels as a
// separate argument to the service rather than inside the patch.
const PUBLIC_CAMPAIGN_PATCH_FIELDS = [
  "status", "templateId", "copy", "draftEdits", "displayName", "destinationUrl",
  "audienceSize", "holdoutSize", "holdoutPct", "klaviyoCampaignId",
  "expectedRevision",
];

// Writing an email shell is founder work, not merchant work: the shell is
// trusted markup that renders to every recipient. Until Ticket D establishes the
// real authenticated boundary, this is an explicit shared secret that must be
// configured — CLOSED by default, so an unconfigured deployment refuses rather
// than accepting arbitrary HTML from anyone who finds the endpoint.
function requireFounderAuth(req, res) {
  const expected = process.env.BEACONAI_ADMIN_TOKEN;
  if (!expected) {
    res.status(503).json({
      ok: false,
      error: "Email-shell configuration is disabled: BEACONAI_ADMIN_TOKEN is not set on this deployment.",
    });
    return false;
  }
  const provided = req.get("x-beaconai-admin-token") || "";
  // Length-independent comparison is not the concern here; an attacker cannot
  // observe timing across a network for a secret of this shape. Constant-time
  // would be better hygiene and is worth doing when Ticket D replaces this.
  if (provided !== expected) {
    res.status(403).json({ ok: false, error: "Not authorized to configure the email shell." });
    return false;
  }
  return true;
}

// One shape for the three ways rendering can refuse, so the UI can tell "nothing
// is configured yet" from "the shell is broken" from "this copy is unusable".
function brandRenderErrorResponse(res, error) {
  if (error instanceof MissingDestination) {
    res.status(400).json({ ok: false, error: error.message, code: "missing_destination", slot: error.slot });
    return true;
  }
  if (error && error.code === "preview_required") {
    res.status(409).json({ ok: false, error: error.message, code: "preview_required" });
    return true;
  }
  if (error && error.code === "preview_out_of_date") {
    res.status(409).json({
      ok: false, error: error.message, code: "preview_out_of_date",
      reviewedVersion: error.reviewedVersion ?? null, activeVersion: error.activeVersion ?? null,
    });
    return true;
  }
  if (error instanceof BrandSetupRequired) {
    res.status(409).json({ ok: false, error: error.message, code: "brand_setup_required" });
    return true;
  }
  if (error instanceof BrandTemplateInvalid) {
    res.status(400).json({ ok: false, error: error.message, code: "brand_template_invalid", problems: error.problems });
    return true;
  }
  if (error instanceof SlotValueRejected) {
    res.status(400).json({ ok: false, error: error.message, code: "slot_value_rejected", slot: error.slot });
    return true;
  }
  return false;
}

function publicCampaignPatch(body) {
  const patch = {};
  for (const field of PUBLIC_CAMPAIGN_PATCH_FIELDS) {
    if (body[field] !== undefined) patch[field] = body[field];
  }
  return patch;
}

// One shape for both write conflicts, so the client can tell "someone else
// changed this" from "this has already been sent" and recover rather than
// retrying blindly. 409, never 500: neither is a server fault.
function campaignConflictResponse(res, error) {
  if (error instanceof CampaignRevisionRequired) {
    res.status(409).json({
      ok: false, error: error.message, conflict: "revision_required", campaign: error.campaign,
    });
    return true;
  }
  if (error instanceof CampaignHandoffInProgress) {
    res.status(409).json({
      ok: false, error: error.message, conflict: "handoff_in_progress", campaign: error.campaign,
    });
    return true;
  }
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

// Everything that must work BEFORE a session can exist. Liveness and readiness
// are probes; the OAuth dance is how a session is obtained in the first place;
// /session reports whether the caller has one. `/connections/status` is here
// because onboarding has to render "Connect Shopify" for a shop nobody has
// authorised yet — it answers with booleans only when unauthenticated.
const PUBLIC_PATHS = [
  /^\/health$/,
  /^\/ready$/,
  /^\/session$/,
  /^\/oauth\//,
  /^\/connections\/status$/,
  /^\/connections\/(shopify|klaviyo)\/test$/,
  /^\/$/,
];

// Applied to every other route. Naming a shop is a claim; this is what turns the
// claim into something checked. Individual routes then call authorizedShop() to
// resolve WHICH shop they may act on — the middleware only establishes who is
// asking.
router.use((req, res, next) => {
  if (PUBLIC_PATHS.some((pattern) => pattern.test(req.path))) return next();
  return requireShopSession(req, res, next);
});

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
      // The ONE place a session is minted: a completed Shopify OAuth callback is
      // the only point at which the shop has demonstrably authorised us.
      if (provider === "shopify" && result.shopDomain) {
        res.setHeader("Set-Cookie", sessionCookie(issueSession(result.shopDomain)));
      }
      res.redirect(result.redirectTo);
    })
    .catch((error) => {
      res.status(500).json({ ok: false, error: error.message });
    });
});

// The shop this caller is authenticated as, if any. The client uses it to know
// whether to show a sign-in prompt; it is not itself a credential.
router.get("/session", (req, res) => {
  const session = sessionFromRequest(req);
  res.json({
    ok: true,
    authenticated: Boolean(session),
    shopDomain: session?.shopDomain || null,
    expiresAt: session?.expiresAt || null,
  });
});

// Public, because onboarding must render "Connect Shopify" for a shop nobody has
// authorised yet. An unauthenticated caller gets booleans only: enough to drive
// the connect button, not enough to learn a shop's granted scopes.
router.get("/connections/status", async (req, res) => {
  try {
    const shopDomain = req.query.shopDomain || config.shopify.shopDomain;
    if (!shopDomain) {
      res.status(400).json({ ok: false, error: "shopDomain is required" });
      return;
    }
    const status = await getConnectionStatus(shopDomain);
    const session = sessionFromRequest(req);
    const authenticated = Boolean(session && session.shopDomain === shopDomain);
    res.json({
      ok: true,
      status: authenticated ? status : {
        shopDomain,
        shopify: { connected: Boolean(status?.shopify?.connected) },
        klaviyo: { connected: Boolean(status?.klaviyo?.connected) },
      },
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

// What shell this shop sends with, and every version it has had. Read-only, so
// the founder can check setup without a token.
router.get("/brand/email-template", async (req, res) => {
  try {
    const shopDomain = authorizedShop(req, res, req.query.shopDomain);
    if (!shopDomain) return;
    const active = await getActiveBrandTemplate(shopDomain);
    const versions = await listBrandTemplates(shopDomain);
    res.json({
      ok: true,
      shopDomain,
      configured: Boolean(active),
      // `brand_setup_required` is a state the UI renders, not only an error it
      // catches — the merchant should see that setup is outstanding before they
      // try to preview an email.
      code: active ? null : "brand_setup_required",
      active: active ? { version: active.version, slots: active.slots, brand: active.brand, approvedAt: active.approvedAt, approvedBy: active.approvedBy } : null,
      versions: versions.map((v) => ({ version: v.version, source: v.source, approvedAt: v.approvedAt, approvedBy: v.approvedBy, createdAt: v.createdAt })),
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

// Store a new version and make it active. Founder-only.
router.post("/brand/email-template", async (req, res) => {
  if (!requireFounderAuth(req, res)) return;
  try {
    const shopDomain = authorizedShop(req, res, req.body.shopDomain);
    if (!shopDomain) return;
    if (!shopDomain) {
      res.status(400).json({ ok: false, error: "shopDomain is required" });
      return;
    }
    // Either the merchant's own approved HTML, or the parameterized starter
    // filled from their colours. Both become an ordinary reviewed version.
    const html = req.body.html || buildStarterShell(req.body.style || {});
    const template = await saveBrandTemplate({
      shopDomain,
      html,
      brand: req.body.brand || {},
      source: req.body.html ? "merchant_html" : "starter_template",
      approvedBy: req.body.approvedBy || null,
      notes: req.body.notes || null,
    });
    res.json({
      ok: true,
      template: { version: template.version, slots: template.slots, source: template.source, approvedAt: template.approvedAt },
    });
  } catch (error) {
    if (brandRenderErrorResponse(res, error)) return;
    res.status(500).json({ ok: false, error: error.message });
  }
});

// Check a shell WITHOUT storing it — so an existing Klaviyo template can be
// tested for compatibility rather than promised universal support.
router.post("/brand/email-template/validate", async (req, res) => {
  if (!requireFounderAuth(req, res)) return;
  try {
    const { validateShell } = require("./services/brandEmailRenderer");
    const result = validateShell(req.body.html || "");
    res.json({ ok: true, compatible: true, slots: result.slots });
  } catch (error) {
    if (error instanceof BrandTemplateInvalid) {
      res.status(200).json({ ok: true, compatible: false, problems: error.problems });
      return;
    }
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.get("/brand/context", async (req, res) => {
  try {
    const shopDomain = authorizedShop(req, res, req.query.shopDomain);
    if (!shopDomain) return;
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
    const shopDomain = authorizedShop(req, res, req.body.shopDomain);
    if (!shopDomain) return;
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

// The verified sender identity, or an explicit absence.
//
// There is no sender-management feature here and none is needed: the merchant
// finishes in Klaviyo, where the sender is set. This exists so the review screen
// can show a REAL from-address when the provider gives us one and say "Check in
// Klaviyo" when it does not — never a guess assembled from the store domain.
router.get("/klaviyo/sender", async (req, res) => {
  try {
    const sender = await getKlaviyoSender(await resolveKlaviyoKey(req.query));
    res.json({ ok: true, sender });
  } catch (error) {
    // An unreachable provider is not evidence of a missing sender. Both render
    // the same way to the merchant, but the reason is recorded.
    res.json({ ok: true, sender: null, reason: error.response?.data || error.message });
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
    const shopDomain = authorizedShop(req, res, req.query.shopDomain);
    if (!shopDomain) return;
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
    const input = await getEngineInput(authorizedShop(req, res, req.query.shopDomain) || config.shopify.shopDomain);
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
    const shopDomain = authorizedShop(req, res, req.params.shopDomain);
    if (!shopDomain) return;
    const status = await getSyncStatus(shopDomain);
    res.json({ ok: true, ...status });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.get("/engine/input/:shopDomain", async (req, res) => {
  try {
    const shopDomain = authorizedShop(req, res, req.params.shopDomain);
    if (!shopDomain) return;
    const input = await getEngineInput(shopDomain);
    res.json({ ok: true, input });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

// D6b: weekly order + new-customer series for briefing sparklines. Read-only.
router.get("/stats/series/:shopDomain", async (req, res) => {
  try {
    const weeks = req.query.weeks || 12;
    const shopDomain = authorizedShop(req, res, req.params.shopDomain);
    if (!shopDomain) return;
    const series = await getWeeklySeries(shopDomain, weeks);
    res.json({ ok: true, weeks: series });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

router.post("/engine/atul/run", async (req, res) => {
  try {
    const shopDomain = authorizedShop(req, res, req.body.shopDomain);
    if (!shopDomain) return;
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
    const shopDomain = authorizedShop(req, res, req.params.shopDomain);
    if (!shopDomain) return;
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
    const shopDomain = authorizedShop(req, res, req.body.shopDomain);
    if (!shopDomain) return;
    const privateKey = await resolveKlaviyoKey(req.body);
    if (!req.body.campaign) {
      res.status(400).json({ ok: false, error: "campaign is required" });
      return;
    }

    const input = await getEngineInput(shopDomain);
    const brandContext = buildBrandContext(input);
    const campaign = finalizeCampaignForRender(req.body.campaign, brandContext);
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

    // After ownership and provenance — those refusals hold whatever the preview
    // state is — but before anything is reserved, split or written. A handoff
    // with no approval binding cannot succeed, so refusing it here leaves no
    // recipient rows or audience counts behind. Only the COMPARISON needs the
    // rendered bytes; the requirement itself does not.
    if (req.body.expectedTemplateVersion == null || !req.body.expectedRenderFingerprint) {
      res.status(409).json({
        ok: false,
        code: "preview_required",
        error: "This campaign has not been previewed. Refresh the preview and review the email before sending.",
      });
      return;
    }
    const audience = await resolveCampaignAudience(shopDomain, campaign, { runId });

    // Split the audience before anything reaches Klaviyo. The held-out arm is
    // what turns "these customers bought $X" into "this campaign earned $X".
    const playId = existingCampaign?.playId || campaign.play_id || campaign.id;
    let split = { treated: audience.recipients || [], holdout: [], holdoutPct: 0 };
    let campaignRow = null;
    let templateVersionUsed = null;

    if (audience.materialized && playId) {
      campaignRow = existingCampaign || await upsertCampaign({
        shopDomain, runId, playId,
        displayName: campaign.play_name || campaign.name || null,
        expectedRevision: req.body.expectedRevision,
      });

      // Claim the campaign BEFORE anything external happens. Reading `frozen`
      // here and calling Klaviyo afterwards left a window in which two requests
      // both passed the check and both created a draft. The reservation is one
      // conditional UPDATE, so exactly one can hold it — and it requires the
      // revision the merchant reviewed, so a campaign edited since approval
      // cannot be handed off as if it had been signed off.
      campaignRow = await reserveCampaignForHandoff(campaignRow.id, req.body.expectedRevision);
      // Durable from the moment we claim it, so a crash here is visible as
      // `creating` rather than as a campaign that was never touched.
      await transitionDelivery(campaignRow.id, "creating").catch(() => {});
      split = splitAudience(shopDomain, audience.recipients, campaignRow.holdoutPct ?? 0.1);

      // Recipients are persisted BEFORE the send, deliberately. If this write
      // fails we must not send: a campaign whose split was never recorded can
      // never be measured, and an unmeasurable send is worse than a late one.
      await recordRecipients(campaignRow.id, split);
      // Quotes the revision the reservation just returned. This route holds the
      // campaign, so it is not guessing — but it still names what it is writing
      // over, the same rule every other caller follows.
      campaignRow = await updateCampaign(campaignRow.id, {
        audienceSize: split.treated.length + split.holdout.length,
        holdoutSize: split.holdout.length,
        holdoutPct: split.holdoutPct,
        expectedRevision: campaignRow.revision,
      }, {
        // This route holds the reservation, so it is the one caller allowed to
        // write content while the campaign is reserved. Second argument, out of
        // reach of any request body.
        holdsReservation: true,
      });
    }

    // Only the treated arm goes to Klaviyo. The holdout is, by definition, the
    // group that receives nothing.
    const sendAudience = { ...audience, recipients: split.treated, count: split.treated.length };
    // Rendered HERE, once, by the same function the preview used — then handed
    // to the provider as bytes. Letting the provider client render again would
    // reintroduce exactly the divergence this ticket exists to remove.
    // Recorded BEFORE the provider is called. If the call ends uncertain, this
    // is the only identity reconciliation has to find the campaign by — and
    // re-deriving it later from the stored row produced a different string.
    const providerCampaignName = campaignNameForProvider(campaign);
    if (campaignRow) {
      await query(
        `UPDATE clean.campaigns SET provider_campaign_name = $2, updated_at = NOW() WHERE id = $1`,
        [campaignRow.id, providerCampaignName]
      ).catch(() => {});
    }

    let renderedHtml;
    try {
      const brandTemplate = await requireActiveBrandTemplate(shopDomain);

      // The shell the merchant REVIEWED, not whichever is active now. A version
      // activated between the preview and the send would otherwise change an
      // already-approved email without anyone seeing it.
      //
      // REQUIRED, both of them. Skipping the check when a field was absent made
      // the binding optional exactly where it mattered: a caller with no
      // successful preview sent null and the send proceeded unverified. There is
      // no such thing as approving an email nobody rendered.
      const reviewedVersion = req.body.expectedTemplateVersion;
      const expectedFingerprint = req.body.expectedRenderFingerprint;
      if (Number(reviewedVersion) !== brandTemplate.version) {
        throw Object.assign(
          new Error(
            `The email shell changed since this was previewed (you reviewed version ` +
            `${reviewedVersion}, the store now uses ${brandTemplate.version}). ` +
            `Refresh the preview and review it again before sending.`
          ),
          { code: "preview_out_of_date", statusCode: 409, reviewedVersion, activeVersion: brandTemplate.version }
        );
      }

      renderedHtml = renderBrandEmail(brandTemplate, slotValuesForCampaign(
        campaign,
        { ...(brandTemplate.brand || {}), brandName: brandContext?.brandName }
      ));

      // Byte-level binding. Whatever changed — copy, destination, shell — if the
      // rendering is not the one that was approved, this refuses rather than
      // sending something nobody reviewed.
      const actualFingerprint = renderFingerprint(renderedHtml);
      if (expectedFingerprint !== actualFingerprint) {
        throw Object.assign(
          new Error(
            "This email is not the one that was previewed. Refresh the preview and review it again before sending."
          ),
          { code: "preview_out_of_date", statusCode: 409, expectedFingerprint, actualFingerprint }
        );
      }

      templateVersionUsed = brandTemplate.version;
    } catch (renderError) {
      // A rendering failure blocks the handoff with something actionable, and
      // hands the reservation back: nothing reached the provider.
      if (campaignRow) await releaseHandoffReservation(campaignRow.id).catch(() => {});
      throw renderError;
    }

    let packageResult;
    try {
      packageResult = await createCampaignSendPackage(privateKey, campaign, sendAudience, { html: renderedHtml });
    } catch (providerError) {
      // Hand the reservation back ONLY on a PROVEN pre-creation failure — the
      // request never left us, so nothing can exist at the provider and a retry
      // is safe. Anything later keeps the reservation: a timeout at the campaign
      // step may still have created a campaign, and releasing would let the next
      // click create a second one. A campaign left reserved is visible and
      // fixable; a duplicate send is not.
      //
      // This previously keyed off `providerError.partialPackage`, which nothing
      // ever set — so every failure released, including ones that may have
      // created a draft.
      if (campaignRow && providerError.provenNothingCreated === true) {
        // Proven pre-creation: nothing exists there, so retry is safe.
        await transitionDelivery(campaignRow.id, "failed").catch(() => {});
        await releaseHandoffReservation(campaignRow.id).catch(() => {});
      } else if (campaignRow) {
        // Anything else may have created a campaign. `uncertain` has no retry
        // edge; only reconciliation can resolve it.
        await transitionDelivery(campaignRow.id, "uncertain").catch(() => {});
        providerError.reconciliationRequired = true;
        providerError.campaignId = campaignRow.id;
      }
      throw providerError;
    }
    const klaviyoCampaignId = packageResult.campaign?.data?.id;

    // Freeze what was actually sent: the approved copy, the exact HTML that went
    // to Klaviyo, and the audience as a reference plus a hash of its membership.
    // From here the row records delivery state and nothing else changes.
    if (campaignRow) {
      campaignRow = await freezeCampaignAtHandoff(campaignRow.id, {
        approvedCopy: campaign,
        // The exact bytes that went out, and the shell version that produced
        // them — so a later brand version cannot change what this email was.
        renderedHtml,
        templateVersion: templateVersionUsed == null ? null : String(templateVersionUsed),
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
        // CONFIRMED: the provider returned a campaign id. A template or list id
        // would not qualify and is never stored here.
        await transitionDelivery(campaignRow.id, "created", {
          provider: "klaviyo",
          providerCampaignId: klaviyoCampaignId,
          // Only from a provider response. We do not build a link out of an id
          // and a guessed account path.
          // Deliberately null. links.self is an API resource URL, not a page a
          // merchant can open; storing it would put a dead "Open draft in
          // Klaviyo" button in front of them.
          providerCampaignUrl: null,
        }, { fromProvider: true }).catch(() => {});
      } else {
        // The package call returned without a campaign id. That is not a
        // created campaign, whatever else succeeded.
        await transitionDelivery(campaignRow.id, "uncertain").catch(() => {});
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
    if (brandRenderErrorResponse(res, error)) return;
    if (campaignConflictResponse(res, error)) return;
    res.status(500).json({
      ok: false,
      error: error.response?.data || error.message,
      providerStage: error.providerStage || null,
      // The send may or may not exist at the provider. The campaign stays
      // reserved so nothing can retry blindly; clearing it is a manual
      // reconciliation step (Ticket D).
      reconciliationRequired: Boolean(error.reconciliationRequired),
      campaignId: error.campaignId || null,
    });
  }
});

// Read-only preview of the exact html that would be pushed to Klaviyo as a CODE
// template. Makes zero Klaviyo API calls and works with Klaviyo disconnected.
// Must NOT create templates, lists, or campaigns.
//
// Ticket C: this and the handoff call the SAME renderer with the same inputs, so
// the bytes previewed are the bytes sent.
router.post("/klaviyo/campaigns/preview-html", async (req, res) => {
  try {
    const shopDomain = authorizedShop(req, res, req.body.shopDomain);
    if (!shopDomain) return;
    const draft = req.body.campaign || req.body;
    let brandContext = draft.brandContext || req.body.brandContext;
    if (!brandContext) {
      const input = await getEngineInput(shopDomain);
      brandContext = buildBrandContext(input);
    }

    // The SAME finalization and the SAME renderer the send uses. The preview
    // used to render the raw draft while the handoff applied brand-copy defaults
    // first, so the email approved and the email sent were built from different
    // inputs — an intentionally emptied paragraph came back as filler.
    const finalized = finalizeCampaignForRender(draft, brandContext);
    const template = await requireActiveBrandTemplate(shopDomain);
    const slots = slotValuesForCampaign(
      finalized,
      { ...(template.brand || {}), brandName: brandContext?.brandName }
    );
    const html = renderBrandEmail(template, slots);

    res.json({
      ok: true,
      html,
      // The version this preview was rendered with, and a fingerprint of the
      // bytes. The handoff requires both back, so approval binds to THIS
      // rendering rather than to whatever is active later.
      templateVersion: template.version,
      renderFingerprint: renderFingerprint(html),
      renderedForRevision: req.body.expectedRevision ?? null,
      // The link the button ACTUALLY carries, after the campaign's own
      // destination and the shop default have been resolved. Without this the
      // editor cannot tell an empty input that falls back to a working default
      // from an empty input that means the email has no link at all — and it
      // would show "add a destination" for an email that has one.
      effectiveDestinationUrl: slots.cta_url || null,
      brandDefaultDestinationUrl: template.brand?.ctaUrl || null,
    });
  } catch (error) {
    if (brandRenderErrorResponse(res, error)) return;
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
  }
});

router.post("/klaviyo/campaigns/send", async (req, res) => {
  try {
    const shopDomain = authorizedShop(req, res, req.body.shopDomain);
    if (!shopDomain) return;
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
    const shopDomain = authorizedShop(req, res, req.body.shopDomain);
    if (!shopDomain) return;
    const {
      runId, playId, status, templateId, copy, draftEdits, klaviyoCampaignId,
      holdoutPct, displayName, destinationUrl, expectedRevision,
    } = req.body;
    const campaign = await upsertCampaign({
      shopDomain, runId, playId, status, templateId, copy, draftEdits, klaviyoCampaignId,
      holdoutPct, displayName, destinationUrl, expectedRevision,
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
    const shopDomain = authorizedShop(req, res, req.params.shopDomain);
    if (!shopDomain) return;
    const campaigns = await listCampaigns(shopDomain, { runId: req.query.runId || null });
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
    // Allowlisted. Forwarding the body wholesale let a caller set
    // `holdsReservation` — the flag meant only for the handoff route that
    // actually holds the reservation — and edit content mid-handoff. Anything
    // not named here is ignored rather than trusted.
    // A campaign id is not a credential. Confirm it belongs to the caller's
    // shop before touching it — same 404 as a missing campaign, so an id cannot
    // be probed for existence from another shop's session.
    const existing = await getCampaign(id);
    if (!existing || !authorizedForShop(req, existing.shopDomain)) {
      res.status(404).json({ ok: false, error: `No campaign ${id}` });
      return;
    }
    const campaign = await updateCampaign(id, publicCampaignPatch(req.body || {}));
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

// The durable provider state for one campaign. Safe to poll: reads only.
//
// AUTHENTICATED. The shop comes from the signed session, never from the query —
// comparing against a name the caller supplied is not a boundary, it is a
// formality anyone can satisfy.
router.get("/campaigns/:id/delivery", requireShopSession, async (req, res) => {
  try {
    const id = Number.parseInt(req.params.id, 10);
    if (!Number.isFinite(id)) {
      res.status(400).json({ ok: false, error: "campaign id must be numeric" });
      return;
    }
    const campaign = await getCampaign(id);
    // Same 404 for "does not exist" and "not yours", so an id cannot be probed
    // for existence from the wrong shop.
    if (!campaign || !authorizedForShop(req, campaign.shopDomain)) {
      res.status(404).json({ ok: false, error: `No campaign ${id}` });
      return;
    }
    const delivery = await getDelivery(id);
    res.json({ ok: true, delivery });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

// Founder-triggered. Reads the provider and updates state; never creates.
router.post("/campaigns/:id/reconcile", async (req, res) => {
  if (!requireFounderAuth(req, res)) return;
  try {
    const id = Number.parseInt(req.params.id, 10);
    if (!Number.isFinite(id)) {
      res.status(400).json({ ok: false, error: "campaign id must be numeric" });
      return;
    }
    const campaign = await getCampaign(id);
    if (!campaign) {
      res.status(404).json({ ok: false, error: `No campaign ${id}` });
      return;
    }
    // Credentials for the campaign's OWN store, not whatever the request body
    // says. A founder token is not a licence to reconcile one shop's campaign
    // against another shop's Klaviyo account.
    const privateKey = await resolveStoredKlaviyoToken(campaign.shopDomain);
    const result = await reconcileCampaign(id, {
      lookupById: (providerCampaignId) => klaviyoClient.getKlaviyoCampaign(privateKey, providerCampaignId),
      // Options forwarded. Dropping them silently discarded the attempt-time
      // scope, so the real endpoint could still adopt an older campaign that
      // happened to share this one's name.
      findByName: (name, options) => klaviyoClient.findKlaviyoCampaigns(privateKey, name, options),
    });
    res.json({ ok: true, ...result });
  } catch (error) {
    if (error instanceof DeliveryTransitionRejected) {
      res.status(409).json({ ok: false, error: error.message, from: error.from, to: error.to });
      return;
    }
    res.status(500).json({ ok: false, error: error.response?.data || error.message });
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
    const existing = await getCampaign(id);
    if (!existing || !authorizedForShop(req, existing.shopDomain)) {
      res.status(404).json({ ok: false, error: `No campaign ${id}` });
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
    const shopDomain = authorizedShop(req, res, req.params.shopDomain);
    if (!shopDomain) return;
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
    const shopDomain = authorizedShop(req, res, req.body.shopDomain);
    if (!shopDomain) return;
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
    // A typed breakdown, because "matched", "planned to email" and "actually
    // sent" are three different numbers and collapsing them is how a merchant
    // ends up believing an email reached people it never reached.
    //
    // `exclusions` carries only what we can EVIDENCE. The engine matched N
    // customers; some have no email address on file, which is a data gap, not a
    // consent decision — and we say exactly that. Consent and suppression are
    // applied by Klaviyo at send, and we do not claim to have applied them.
    const matched = audience.memberCount ?? audience.count ?? null;
    const noEmail = audience.suppressedCount ?? null;
    const breakdown = audience.materialized ? {
      matched,
      plannedEmailGroup: holdout ? holdout.treated : audience.count ?? null,
      comparisonGroup: holdout ? holdout.held : null,
      comparisonPct: holdout ? holdout.pct : null,
      exclusions: noEmail
        ? [{
            code: "no_email_on_file",
            count: noEmail,
            label: `${noEmail} matched customer${noEmail === 1 ? "" : "s"} have no email address on file.`,
          }]
        : [],
      // Named so the UI cannot present provider behaviour as ours.
      providerAppliesAtSend: "Klaviyo applies consent and suppression at send. The actual sent count is confirmed afterwards.",
      // Never inferred. Populated only by provider reconciliation.
      actualSentCount: null,
    } : null;

    res.json({
      ok: true,
      shopDomain,
      audience,
      holdout,
      breakdown,
      originRunId: runId,
      // So the UI can say why a send is blocked before the merchant clicks it,
      // rather than only after.
      inputProvenance: foreign ? "foreign_run" : provenance?.provenance || (runId ? "unknown_run" : null),
      sendable: Boolean(provenance) && !foreign && !["fixture", "legacy_unverified"].includes(provenance.provenance),
    });
  } catch (error) {
    res.status(500).json({ ok: false, error: error.message });
  }
});

module.exports = { router };
