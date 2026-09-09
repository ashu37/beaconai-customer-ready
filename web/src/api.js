const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || `${window.location.origin}/api`;
const SHOP_DOMAIN_STORAGE_KEY = "beaconai:shop-domain";
const initialShopDomain =
  new URLSearchParams(window.location.search).get("shop") ||
  localStorage.getItem(SHOP_DOMAIN_STORAGE_KEY) ||
  import.meta.env.VITE_SHOP_DOMAIN ||
  "";

let shopDomain = normalizeShopDomain(initialShopDomain);

function normalizeShopDomain(value) {
  const raw = String(value || "").trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/.*$/, "");
  if (!raw) return "";
  return raw.endsWith(".myshopify.com") ? raw : `${raw}.myshopify.com`;
}

function setShopDomain(value) {
  shopDomain = normalizeShopDomain(value);
  if (shopDomain) {
    localStorage.setItem(SHOP_DOMAIN_STORAGE_KEY, shopDomain);
    const url = new URL(window.location.href);
    url.searchParams.set("shop", shopDomain);
    window.history.replaceState({}, "", url.toString());
  } else {
    localStorage.removeItem(SHOP_DOMAIN_STORAGE_KEY);
  }
  return shopDomain;
}

function requireShopDomain() {
  if (!shopDomain) {
    throw new Error("Enter a Shopify store domain before connecting.");
  }
  return shopDomain;
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok || data?.ok === false) {
    const detail = data?.error || data || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail, null, 2));
  }

  return data;
}

export const api = {
  get shopDomain() {
    return shopDomain;
  },
  setShopDomain,
  oauthStartUrl: (provider, returnTo = window.location.href) => `${API_BASE_URL}/oauth/${provider}/start?shop=${encodeURIComponent(requireShopDomain())}&returnTo=${encodeURIComponent(returnTo)}`,
  health: () => request("/health"),
  connectionStatus: () => request(`/connections/status?shopDomain=${encodeURIComponent(shopDomain)}`),
  brandContext: () => request(`/brand/context?shopDomain=${encodeURIComponent(shopDomain)}`),
  testShopify: () => request("/connections/shopify/test", { method: "POST", body: JSON.stringify({ shopDomain, limit: 1 }) }),
  testKlaviyo: () => request("/connections/klaviyo/test", { method: "POST", body: JSON.stringify({}) }),
  // No limit by default → backend paginates the whole store. Pass a number to bound the sync.
  syncShopify: (limit) => request("/sync/shopify", { method: "POST", body: JSON.stringify({ shopDomain: requireShopDomain(), ...(limit != null ? { limit } : {}) }) }),
  // Which sync the store data comes from, how much history it covers, and
  // whether a new analysis is allowed to run.
  syncStatus: () => request(`/sync/status/${encodeURIComponent(shopDomain)}`),
  runAtulEngine: (useFixture = false) => request("/engine/atul/run", { method: "POST", body: JSON.stringify({ shopDomain, useFixture }) }),
  getLatestEngineRun: () => request(`/engine/atul/latest/${encodeURIComponent(shopDomain)}`),
  getKlaviyoTemplates: () => request(`/klaviyo/templates?shopDomain=${encodeURIComponent(shopDomain)}`),
  // Campaign state. Replaces the run-scoped localStorage blob: approvals, copy
  // edits and send state now survive an engine run, a new browser and a new device.
  listCampaigns: (runId) => request(`/campaigns/${encodeURIComponent(shopDomain)}${runId ? `?runId=${encodeURIComponent(runId)}` : ""}`),
  saveCampaign: (campaign) => request("/campaigns", { method: "POST", body: JSON.stringify({ shopDomain, ...campaign }) }),
  patchCampaign: (id, patch) => request(`/campaigns/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  previewCampaignAudience: (campaign) => request("/campaigns/audience/preview", { method: "POST", body: JSON.stringify({ shopDomain, campaign }) }),
  createSendPackage: (campaign) => request("/klaviyo/campaigns/from-engine", { method: "POST", body: JSON.stringify({ shopDomain, campaign }) }),
  previewCampaignHtml: (draft) => request("/klaviyo/campaigns/preview-html", { method: "POST", body: JSON.stringify({ shopDomain, campaign: draft }) }),
  // CA-1: customer-facing copywriter. Fails soft (available:false => static copy).
  generateCopy: ({ playId, templateId, regenerate, lockedSlots, steer } = {}) =>
    request("/copy/generate", { method: "POST", body: JSON.stringify({ shopDomain, playId, templateId, regenerate, lockedSlots, steer }) }),
  sendCampaign: (campaignId) => request("/klaviyo/campaigns/send", { method: "POST", body: JSON.stringify({ shopDomain, campaignId }) }),
  getEngineInput: () => request(`/engine/input/${encodeURIComponent(shopDomain)}`),
  // Measured results: the program-level holdout comparison plus every sent
  // campaign, across every run.
  getResults: () => request(`/results/${encodeURIComponent(shopDomain)}`),
  getStatsSeries: (weeks = 12) => request(`/stats/series/${encodeURIComponent(shopDomain)}?weeks=${weeks}`),
};
