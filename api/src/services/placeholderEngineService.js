function buildPlaceholderEngineRun(input = {}) {
  const shopDomain = input.shop?.shop_domain || input.shop?.domain || "pending-shop";
  const productCount = input.products?.length || 0;
  const customerCount = input.customers?.length || 0;
  const orderCount = input.orders?.length || 0;
  const firstProduct = input.products?.[0];

  return {
    contract_version: "placeholder_engine_run_v1",
    source: "beaconai-frontend-app-inspired-placeholder",
    note: "Temporary engine shape for UI and integration work until Atul's production engine is wired in.",
    store_id: shopDomain,
    run_timestamp: new Date().toISOString(),
    input_summary: {
      products: productCount,
      customers: customerCount,
      orders: orderCount,
    },
    slate: {
      recommended_now: [
        {
          play_id: "winback_dormant_cohort",
          play_name: "Dormant buyer winback",
          audience_archetype: "DORMANT_BUYER",
          audience_size: Math.max(customerCount, 1),
          mechanism:
            "Re-engage customers with prior purchase history who have not purchased recently, using a personalized replenishment or discovery offer.",
          evidence: {
            evidence_class: "directional",
            p_value: null,
            effect: null,
            source: "live_shopify_clean_tables",
          },
          revenue_range: {
            low: orderCount * 20,
            high: orderCount * 45,
            currency: input.shop?.currency || "USD",
          },
          gate_status: {
            cohort_pvalue: false,
            prior_validation: true,
            ml_fit: false,
          },
        },
      ],
      recommended_experiment: [
        {
          play_id: "first_to_second_purchase",
          play_name: "First-to-second purchase journey",
          audience_archetype: "FIRST_TIME_BUYER",
          audience_size: Math.max(Math.floor(customerCount / 2), 1),
          mechanism:
            "Send education and cross-sell content after first purchase to create a second-purchase path.",
          evidence: {
            evidence_class: "prior-anchored",
            source: "placeholder_prior",
          },
          gate_status: {
            cohort_pvalue: false,
            prior_validation: true,
            ml_fit: false,
          },
        },
      ],
      considered: [
        {
          play_id: "replenishment_due",
          play_name: "Replenishment due",
          reason_code: "REAL_ENGINE_NOT_CONNECTED",
          mechanism:
            firstProduct?.title
              ? `Use ${firstProduct.title} as a candidate replenishment signal once SKU-level cadence is available.`
              : "Replenishment requires SKU-level cadence and survival model output.",
        },
      ],
      watching: [],
    },
    predictive_models: {
      bg_nbd: {
        display_name: "BG/NBD purchase probability",
        fit_status: "PLACEHOLDER",
        handoff_status: "waiting_for_engine_code",
      },
      gamma_gamma: {
        display_name: "Gamma-Gamma monetary value",
        fit_status: "PLACEHOLDER",
        handoff_status: "waiting_for_engine_code",
      },
      cohort_retention: {
        display_name: "Cohort retention curves",
        fit_status: "PLACEHOLDER",
        handoff_status: "waiting_for_engine_code",
      },
    },
    audience_segments: [
      {
        label: "Known customers",
        n: customerCount,
        source: "clean.customers",
      },
      {
        label: "Purchased orders",
        n: orderCount,
        source: "clean.orders",
      },
      {
        label: "Catalog products",
        n: productCount,
        source: "clean.products",
      },
    ],
    next_engine_handoff: {
      consume: "GET /api/engine/input/:shopDomain",
      replace_or_extend: "api/src/services/placeholderEngineService.js",
      production_target:
        "Return this richer engine_run shape from Atul's engine, then map it into the polished dashboard UI.",
    },
  };
}

module.exports = {
  buildPlaceholderEngineRun,
};
