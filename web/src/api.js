const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:4000/api";
const SHOP_DOMAIN = import.meta.env.VITE_SHOP_DOMAIN || "testing-dev-utkexvrj.myshopify.com";

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
  shopDomain: SHOP_DOMAIN,
  oauthStartUrl: (provider, returnTo = window.location.href) => `${API_BASE_URL}/oauth/${provider}/start?shop=${encodeURIComponent(SHOP_DOMAIN)}&returnTo=${encodeURIComponent(returnTo)}`,
  health: () => request("/health"),
  connectionStatus: () => request(`/connections/status?shopDomain=${encodeURIComponent(SHOP_DOMAIN)}`),
  brandContext: () => request(`/brand/context?shopDomain=${encodeURIComponent(SHOP_DOMAIN)}`),
  testShopify: () => request("/connections/shopify/test", { method: "POST", body: JSON.stringify({ limit: 1 }) }),
  testKlaviyo: () => request("/connections/klaviyo/test", { method: "POST", body: JSON.stringify({}) }),
  syncShopify: (limit = 250) => request("/sync/shopify", { method: "POST", body: JSON.stringify({ limit }) }),
  runEngine: () => request("/engine/run", { method: "POST", body: JSON.stringify({ shopDomain: SHOP_DOMAIN }) }),
  runAtulEngine: (useFixture = false) => request("/engine/atul/run", { method: "POST", body: JSON.stringify({ shopDomain: SHOP_DOMAIN, useFixture }) }),
  getKlaviyoTemplates: () => request(`/klaviyo/templates?shopDomain=${encodeURIComponent(SHOP_DOMAIN)}`),
  previewCampaignAudience: (campaign) => request("/campaigns/audience/preview", { method: "POST", body: JSON.stringify({ shopDomain: SHOP_DOMAIN, campaign }) }),
  createTemplate: (campaign) => request("/klaviyo/templates/from-engine", { method: "POST", body: JSON.stringify({ shopDomain: SHOP_DOMAIN, campaign }) }),
  createSendPackage: (campaign) => request("/klaviyo/campaigns/from-engine", { method: "POST", body: JSON.stringify({ shopDomain: SHOP_DOMAIN, campaign }) }),
  sendCampaign: (campaignId) => request("/klaviyo/campaigns/send", { method: "POST", body: JSON.stringify({ shopDomain: SHOP_DOMAIN, campaignId }) }),
  demoRun: (limit = 250) => request("/demo/run", { method: "POST", body: JSON.stringify({ limit }) }),
  getEngineInput: () => request(`/engine/input/${encodeURIComponent(SHOP_DOMAIN)}`),
  getPlaceholderEngineRun: () => request(`/engine/placeholder/${encodeURIComponent(SHOP_DOMAIN)}`),
};
