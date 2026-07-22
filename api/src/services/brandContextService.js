const STOP_WORDS = new Set([
  "and", "are", "but", "for", "from", "has", "have", "into", "our", "the", "this", "that",
  "then", "they", "with", "your", "you", "all", "new", "set", "pack", "kit", "size", "color",
  "default", "title", "product", "products", "shop", "store",
  "testing", "dev", "vendor", "beaconai", "local", "seed",
]);

function compact(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function stripHtml(value) {
  return compact(String(value || "").replace(/<[^>]+>/g, " "));
}

function splitTags(value) {
  return compact(value)
    .split(",")
    .map((tag) => compact(tag).toLowerCase())
    .filter(Boolean);
}

function wordsFrom(value) {
  return compact(value)
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .map((word) => word.replace(/^-+|-+$/g, ""))
    .filter((word) => word.length > 2 && !STOP_WORDS.has(word));
}

function isUtilityProduct(product) {
  const text = `${product?.title || ""} ${product?.product_type || ""} ${product?.tags || ""}`.toLowerCase();
  return text.includes("gift card") || text.includes("giftcard");
}

function topEntries(items, limit = 8) {
  return [...items.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
}

function money(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? number : 0;
}

function titleize(value) {
  return compact(value)
    .split(/\s+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function inferCategory(products, tags) {
  const text = [
    ...products.map((product) => `${product.title || ""} ${product.product_type || ""} ${product.tags || ""}`),
    ...tags.map((tag) => tag.name),
  ].join(" ").toLowerCase();

  const rules = [
    { category: "outdoor sports", matches: ["snowboard", "snow", "ski", "wax", "winter", "sport", "outdoor"] },
    { category: "beauty and personal care", matches: ["beauty", "skin", "serum", "cream", "glow", "hair", "lip", "soap", "oil"] },
    { category: "apparel and accessories", matches: ["shirt", "dress", "tee", "hoodie", "jeans", "jacket", "bag", "wear"] },
    { category: "wellness", matches: ["vitamin", "supplement", "protein", "health", "wellness", "tea", "sleep"] },
    { category: "home and lifestyle", matches: ["home", "decor", "candle", "kitchen", "linen", "lamp", "living"] },
    { category: "food and beverage", matches: ["coffee", "snack", "sauce", "chocolate", "drink", "food", "spice"] },
  ];

  const scored = rules
    .map((rule) => ({
      category: rule.category,
      score: rule.matches.reduce((sum, match) => sum + (text.match(new RegExp(`\\b${match}\\b`, "g")) || []).length, 0),
    }))
    .sort((a, b) => b.score - a.score);

  return scored[0]?.score ? scored[0].category : "commerce";
}

function inferTone(category, keywords) {
  const keywordText = keywords.map((item) => item.name).join(" ");
  if (category.includes("beauty")) return ["warm", "clean", "helpful", "routine-led"];
  if (category.includes("outdoor")) return ["confident", "seasonal", "practical", "gear-led"];
  if (category.includes("wellness")) return ["reassuring", "clear", "benefit-led", "supportive"];
  if (category.includes("apparel")) return ["confident", "visual", "style-led", "concise"];
  if (category.includes("food")) return ["appetizing", "friendly", "sensory", "direct"];
  if (keywordText.includes("luxury") || keywordText.includes("premium")) return ["polished", "selective", "calm", "premium"];
  return ["helpful", "clear", "brand-safe", "commerce-focused"];
}

function buildBrandContext(input = {}) {
  const shopRaw = input.shop?.raw || {};
  const products = input.products || [];
  const variants = input.product_variants || [];
  const orders = input.orders || [];
  const lineItems = input.order_line_items || [];

  const productById = new Map(products.map((product) => [String(product.id), product]));
  const productTypes = new Map();
  const tagCounts = new Map();
  const keywordCounts = new Map();
  const productSales = new Map();
  const productRevenue = new Map();

  for (const product of products) {
    const type = compact(product.product_type || product.raw?.product_type);
    if (type) productTypes.set(type, (productTypes.get(type) || 0) + 1);

    for (const tag of splitTags(product.tags || product.raw?.tags)) {
      tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
    }

    const copy = [
      product.title,
      product.product_type,
      product.tags,
      stripHtml(product.raw?.body_html),
      product.raw?.vendor,
    ].join(" ");
    for (const word of wordsFrom(copy)) {
      keywordCounts.set(word, (keywordCounts.get(word) || 0) + 1);
    }
  }

  for (const item of lineItems) {
    const key = String(item.product_id || item.title || "unknown");
    const quantity = Number(item.quantity || 0);
    const revenue = quantity * money(item.price);
    productSales.set(key, (productSales.get(key) || 0) + quantity);
    productRevenue.set(key, (productRevenue.get(key) || 0) + revenue);
  }

  const topProducts = topEntries(productSales, 12).map((entry) => {
    const product = productById.get(entry.name);
    return {
      id: product?.id || entry.name,
      title: product?.title || entry.name,
      units: entry.count,
      revenue: Math.round(productRevenue.get(entry.name) || 0),
      productType: product?.product_type || null,
    };
  }).filter((product) => !isUtilityProduct(product)).slice(0, 6);

  const prices = variants.map((variant) => money(variant.price)).filter((price) => price > 0).sort((a, b) => a - b);
  const averageOrderValue = orders.length
    ? orders.reduce((sum, order) => sum + money(order.total_price), 0) / orders.length
    : 0;
  const category = inferCategory(products, topEntries(tagCounts, 12));
  const keywords = topEntries(keywordCounts, 14);
  const tone = inferTone(category, keywords);
  const topTags = topEntries(tagCounts, 10);
  const topProductTypes = topEntries(productTypes, 8);
  const priceRange = prices.length ? {
    low: Math.round(prices[0]),
    high: Math.round(prices[prices.length - 1]),
    median: Math.round(prices[Math.floor(prices.length / 2)]),
    currency: input.shop?.currency || shopRaw.currency || "USD",
  } : null;

  const categoryNoun = category === "commerce" ? "favorites" : category.replace(" and ", " ");
  const ctaStyle = [
    topProducts[0] ? `Shop ${topProducts[0].title}` : "Shop best sellers",
    category.includes("beauty") ? "Restock your routine" : "Find your next favorite",
    averageOrderValue > 75 ? "Complete your set" : "See what is new",
  ];

  // C4c: reject seed/test/brand-name tokens from surfacing as "brand words".
  const shopDomain = input.shop?.shop_domain || shopRaw.domain || null;
  const subdomain = String(shopDomain || "").split(".")[0].toLowerCase();
  const STOP_TOKENS = ["seed", "sample", "test", "demo", "fixture"];
  const isStopToken = (name) => {
    const token = String(name || "").toLowerCase();
    if (!token) return true;
    if (token.includes("beacon")) return true;
    if (subdomain && token.includes(subdomain)) return true;
    return STOP_TOKENS.some((stop) => token.includes(stop));
  };

  return {
    brandName: shopRaw.name || shopRaw.shop_owner || input.shop?.shop_domain || "your store",
    shopDomain,
    category,
    tone,
    currency: input.shop?.currency || shopRaw.currency || "USD",
    timezone: input.shop?.iana_timezone || shopRaw.iana_timezone || null,
    locale: shopRaw.primary_locale || null,
    priceRange,
    averageOrderValue: Math.round(averageOrderValue),
    productLanguage: {
      keywords: keywords.filter((item) => !isStopToken(item.name)),
      tags: topTags.filter((item) => !isStopToken(item.name)),
      productTypes: topProductTypes.filter((item) => !item.name.toLowerCase().includes("gift")),
      bestSellers: topProducts,
    },
    messaging: {
      useWords: keywords.filter((item) => !isStopToken(item.name)).slice(0, 8).map((item) => item.name),
      avoidWords: ["cheap", "blast", "spam", "last chance unless a real deadline exists"],
      ctaStyle,
      openingAngle: `A ${tone[0]} ${categoryNoun} message using the store's own product language.`,
    },
  };
}

function templateCopyForPlay(campaign, brandContext) {
  const title = campaign.playTitle || campaign.play_name || campaign.subject || "your next pick";
  const bestSeller = brandContext.productLanguage?.bestSellers?.[0]?.title;
  const category = brandContext.category || "favorites";
  const brand = brandContext.brandName || "your store";
  const cta = brandContext.messaging?.ctaStyle?.[1] || "Shop now";
  const words = brandContext.messaging?.useWords?.slice(0, 3).join(", ");

  return {
    subject: campaign.subject || `${brand}: ${title}`,
    previewText: campaign.previewText || `A ${brandContext.tone?.[0] || "helpful"} note matched to your ${category} shoppers.`,
    bodyH2: campaign.bodyH2 || (bestSeller ? `${bestSeller} and more picks worth revisiting.` : `${title} is ready for review.`),
    bodyP1: campaign.bodyP1 || `We used recent Shopify behavior, product language, and purchase history to shape this ${category} message for ${brand}.`,
    bodyP2: campaign.bodyP2 || (words
      ? `Keep the copy close to the brand vocabulary: ${words}.`
      : "Keep the copy direct, useful, and tied to the customer's recent shopping context."),
    cta: campaign.cta || cta,
  };
}

function applyBrandVoiceToCampaign(campaign = {}, brandContext) {
  if (!brandContext) return campaign;
  return {
    ...campaign,
    ...templateCopyForPlay(campaign, brandContext),
    brandContext,
  };
}

function buildBeaconTemplates(brandContext) {
  const brand = brandContext?.brandName || "your store";
  const bestSeller = brandContext?.productLanguage?.bestSellers?.[0]?.title;
  const category = brandContext?.category || "commerce";
  const cta = brandContext?.messaging?.ctaStyle || ["Shop best sellers", "Find your next favorite", "Complete your set"];

  return [
    {
      id: "beacon-winback-clean",
      source: "beacon",
      name: "Winback",
      // Bestseller appears at most twice per email: here in subject + headline.
      // Keep the body product-neutral so the same name isn't echoed a third time.
      subject: bestSeller ? `Still thinking about ${bestSeller}?` : `A fresh reason to come back to ${brand}`,
      previewText: "It's been a while — come see what's new.",
      bodyH2: bestSeller ? `${bestSeller} is a good place to restart.` : "Your next favorite is ready.",
      bodyP1: "Your favorites are still here, plus a few new arrivals you haven't met yet.",
      cta: cta[0],
      brandContext,
    },
    {
      id: "beacon-second-purchase",
      source: "beacon",
      name: "Second purchase",
      subject: "Make the most of your first order",
      previewText: "A few picks that pair well with your first order.",
      bodyH2: bestSeller ? `Pair your first pick with ${bestSeller}.` : "Here is what pairs well with your first pick.",
      bodyP1: "Great first pick. Here's what other customers added next — chosen to go with what you already have.",
      cta: cta[1],
      brandContext,
    },
    {
      id: "beacon-lifecycle-soft-nudge",
      source: "beacon",
      name: "Gentle nudge",
      subject: "Picked for where you are now",
      previewText: "A few things picked for you.",
      bodyH2: "A small nudge, matched to your timing.",
      bodyP1: "No rush — just a few picks we think fit what you've been shopping for.",
      cta: cta[2],
      brandContext,
    },
  ];
}

module.exports = {
  buildBrandContext,
  applyBrandVoiceToCampaign,
  buildBeaconTemplates,
};
