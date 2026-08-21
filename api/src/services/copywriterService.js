// CA-1 + CA-3: the customer-facing email copywriter.
//
// Authors ALL email slots in one Anthropic call (cross-slot coherence is the
// point), validates each slot mechanically (CA-3), and falls back PER SLOT to
// the static template copy on any failure. The merchant never sees an error, a
// blank, or a guard message — absent key or a bad slot degrades silently to the
// static copy, exactly like the narration MCP's mock-mode parity.
//
// The Anthropic SDK is required lazily so this module loads (and the app boots)
// with no `@anthropic-ai/sdk` installed and no ANTHROPIC_API_KEY set.

const { PLAYBOOK, PLAYBOOK_VERSION } = require("./copyPlaybook");

const ENV_API_KEY = "ANTHROPIC_API_KEY";
const ENV_MODEL = "COPYWRITER_MODEL";
const DEFAULT_MODEL = "claude-sonnet-4-6";

// The slots the copywriter authors. `subject_variants` is exactly 3; the merchant
// draft uses one. `support` may be empty. `rationale` is merchant-facing (adopt
// #3) and never shown to the customer. `featured_product_id` must be a real id.
const SLOT_KEYS = [
  "subject_variants",
  "preview_text",
  "headline",
  "body",
  "support",
  "cta",
  "rationale",
  "featured_product_id",
];

// --- Config -----------------------------------------------------------------

function apiKeyPresent() {
  return Boolean(String(process.env[ENV_API_KEY] || "").trim());
}

function model() {
  return String(process.env[ENV_MODEL] || "").trim() || DEFAULT_MODEL;
}

// --- Validation (CA-3) ------------------------------------------------------

const EM_EN_DASH = /[—–]/;

// Anti-AI banned words + openers (case-insensitive, word-boundary where sensible).
const BANNED_WORDS = [
  "elevate", "unlock", "discover", "indulge", "seamless", "effortless",
  "curated", "handpicked", "treat yourself", "game-changer", "must-have",
  "obsessed", "bestie",
];
const BANNED_CONSTRUCTIONS = [
  "it's not just", "isn't just", "the best part?", "here's the thing",
  "let's be honest", "we get it",
];
const BANNED_OPENERS = [
  "we noticed", "just checking in", "we wanted to reach out", "hope you're doing well",
];
// Offer / discount vocabulary — always enforced in v1 (no offer input exists).
const OFFER_TERMS = ["discount", "sale", "% off", "free shipping", "coupon", "promo"];
// Internal vocabulary the customer-facing text must never contain.
const INTERNAL_TERMS = [
  "cohort", "play", "audience", "segment", "engine", "campaign", "ai",
  "algorithm", "dormant", "lapsed",
];

const LENGTH_CAPS = {
  subject: 45,
  preview_text: 90,
  headline: 60,
  body: 320,
  support: 200,
  cta: 30,
  rationale: 200,
};

// Weak/banned CTA phrases (playbook: CTA is verb-first and specific).
const BANNED_CTAS = ["shop now", "click here", "learn more", "buy now", "get started"];

const DOLLAR_OR_PERCENT = /\$\s?\d|\d\s?%/;
const EMOJI = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2B00}-\u{2BFF}]/u;

function containsAny(text, needles) {
  const lower = String(text || "").toLowerCase();
  return needles.some((n) => lower.includes(n));
}

function wordBoundaryHit(text, words) {
  const lower = String(text || "").toLowerCase();
  return words.some((w) => {
    // For multi-word phrases fall back to substring; for single words use \b.
    if (/\s/.test(w)) return lower.includes(w);
    const re = new RegExp(`\\b${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
    return re.test(lower);
  });
}

// Common per-slot text checks. Returns a reason string on first failure, or null.
function slotTextViolation(text, capKey) {
  const value = String(text || "");
  if (EM_EN_DASH.test(value)) return "em/en dash";
  if (wordBoundaryHit(value, BANNED_WORDS)) return "banned word";
  if (containsAny(value, BANNED_CONSTRUCTIONS)) return "banned construction";
  if (containsAny(value, BANNED_OPENERS)) return "banned opener";
  if (containsAny(value, OFFER_TERMS)) return "offer/discount term";
  if (wordBoundaryHit(value, INTERNAL_TERMS)) return "internal vocabulary";
  if (DOLLAR_OR_PERCENT.test(value)) return "dollar/percent figure";
  if (EMOJI.test(value)) return "emoji";
  if (capKey && LENGTH_CAPS[capKey] && value.length > LENGTH_CAPS[capKey]) {
    return `over length cap (${LENGTH_CAPS[capKey]})`;
  }
  return null;
}

function jaccard(a, b) {
  const setA = new Set(String(a || "").toLowerCase().split(/\W+/).filter(Boolean));
  const setB = new Set(String(b || "").toLowerCase().split(/\W+/).filter(Boolean));
  if (!setA.size || !setB.size) return 0;
  let inter = 0;
  for (const w of setA) if (setB.has(w)) inter += 1;
  return inter / (setA.size + setB.size - inter);
}

function totalExclamations(slots) {
  return Object.values(slots)
    .flatMap((v) => (Array.isArray(v) ? v : [v]))
    .reduce((sum, v) => sum + (String(v || "").match(/!/g) || []).length, 0);
}

// Validate the parsed copy against a static fallback. Returns
// { copy, fallback_slots } where failing slots are replaced by the static value.
function validateAndFallback(parsed, staticCopy, products) {
  const out = {};
  const fallback = [];
  const productNames = (products || []).map((p) => String(p.title || "").toLowerCase()).filter(Boolean);
  const productIds = new Set((products || []).map((p) => String(p.id)));

  // subject_variants: exactly 3, each valid; else fall back to a single static subject.
  const variants = Array.isArray(parsed.subject_variants) ? parsed.subject_variants : [];
  const validVariants = variants
    .map((v) => String(v || "").trim())
    .filter((v) => v && !slotTextViolation(v, "subject"));
  if (validVariants.length >= 1) {
    out.subject_variants = validVariants.slice(0, 3);
  } else {
    out.subject_variants = [staticCopy.subject].filter(Boolean);
    fallback.push("subject_variants");
  }

  // Simple text slots.
  const textSlots = [
    ["preview_text", "preview_text", staticCopy.previewText],
    ["headline", "headline", staticCopy.headline],
    ["body", "body", staticCopy.body],
    ["support", "support", staticCopy.support],
    ["cta", "cta", staticCopy.cta],
    ["rationale", "rationale", ""],
  ];
  for (const [key, capKey, staticValue] of textSlots) {
    const raw = parsed[key];
    // support + rationale may be empty strings; that's valid.
    if ((key === "support" || key === "rationale") && (raw === "" || raw == null)) {
      out[key] = "";
      continue;
    }
    let violation = slotTextViolation(raw, capKey);
    // CTA-specific: reject weak/banned call-to-action phrases (playbook).
    if (!violation && key === "cta" && containsAny(raw, BANNED_CTAS)) {
      violation = "banned CTA phrase";
    }
    if (violation) {
      out[key] = staticValue || "";
      // rationale has no static equivalent — omit rather than surface a template.
      if (key !== "rationale") fallback.push(key);
      else out[key] = "";
    } else {
      out[key] = String(raw);
    }
  }

  // featured_product_id must be a real id (else null).
  out.featured_product_id = productIds.has(String(parsed.featured_product_id))
    ? String(parsed.featured_product_id)
    : null;

  // Cross-slot: featured product name count <= 2 across chosen slots.
  const featuredName = (products || []).find((p) => String(p.id) === out.featured_product_id);
  if (featuredName && featuredName.title) {
    const name = String(featuredName.title).toLowerCase();
    const chosen = [out.subject_variants?.[0], out.preview_text, out.headline, out.body, out.support, out.cta];
    const count = chosen.reduce((n, s) => n + (String(s || "").toLowerCase().includes(name) ? 1 : 0), 0);
    if (count > 2) {
      // Too many mentions — drop support first, then fall back body.
      if (String(out.support || "").toLowerCase().includes(name)) { out.support = ""; }
    }
  }

  // Cross-slot: body/support Jaccard overlap < 0.5.
  if (out.support && jaccard(out.body, out.support) >= 0.5) {
    out.support = "";
  }

  // <= 1 exclamation mark total across all slots.
  if (totalExclamations(out) > 1) {
    // Strip exclamations from the softest slots first (support, preview, body).
    for (const key of ["support", "preview_text", "body", "headline"]) {
      if (out[key]) out[key] = String(out[key]).replace(/!/g, ".");
      if (totalExclamations(out) <= 1) break;
    }
  }

  return { copy: out, fallback_slots: fallback };
}

// --- Prompt assembly --------------------------------------------------------

const OUTPUT_CONTRACT = `Output STRICT JSON with EXACTLY these keys and nothing else:
{
  "subject_variants": ["...", "...", "..."],
  "preview_text": "...",
  "headline": "...",
  "body": "...",
  "support": "...",
  "cta": "...",
  "rationale": "...",
  "featured_product_id": "<one id from the provided products, or null>"
}
- subject_variants: EXACTLY 3, each under 45 characters.
- support may be an empty string.
- featured_product_id must be one of the provided product ids, or null.
- Output ONLY the JSON object. No prose, no code fences, no explanation.`;

function userMessage({ play, brandContext, template, products, lockedSlots, steer }) {
  const mechanism = play?.mechanism_intent?.type || play?.mechanism_type || "GENERAL";
  const audienceOneLiner = play?.play_one_liner || play?.audience_archetype || "this audience";
  const productList = (products || []).map((p) => ({ id: String(p.id), name: p.title, type: p.productType || null }));

  const lockedBlock = lockedSlots && Object.keys(lockedSlots).length
    ? "\n\nThe merchant has LOCKED these slots (they wrote them). Do NOT change them. "
      + "Write every other slot to fit and cohere with these locked values:\n"
      + JSON.stringify(lockedSlots, null, 2)
    : "";

  const steerBlock = steer
    ? `\n\nRevision note from the merchant (honor it within the rules): "${steer}"`
    : "";

  return (
    `Mechanism: ${mechanism}\n`
    + `Audience (do not name the customer with internal words): ${audienceOneLiner}\n`
    + `Brand: ${brandContext?.brandName || "the store"} (${brandContext?.category || "products"})\n`
    + `Store words to favor: ${(brandContext?.messaging?.useWords || []).slice(0, 8).join(", ") || "the catalog's own language"}\n`
    + `Starting template name: ${template?.name || "—"}\n`
    + `Products (choose one to feature by id, or null):\n${JSON.stringify(productList, null, 2)}`
    + lockedBlock
    + steerBlock
    + `\n\n${OUTPUT_CONTRACT}`
  );
}

// --- JSON parsing -----------------------------------------------------------

function parseCopyJson(raw) {
  if (!raw) return null;
  let text = String(raw).trim();
  if (text.startsWith("```")) {
    text = text.replace(/^```[a-zA-Z]*\n?/, "").replace(/```\s*$/, "");
  }
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start === -1 || end === -1) return null;
  try {
    const obj = JSON.parse(text.slice(start, end + 1));
    return obj && typeof obj === "object" ? obj : null;
  } catch (_) {
    return null;
  }
}

// --- Anthropic call ---------------------------------------------------------

let _client = null;
function anthropicClient() {
  if (_client) return _client;
  // Lazy require so the app boots without the SDK installed.
  const Anthropic = require("@anthropic-ai/sdk");
  _client = new Anthropic({ apiKey: process.env[ENV_API_KEY] });
  return _client;
}

async function callModel(userText) {
  const client = anthropicClient();
  const resp = await client.messages.create({
    model: model(),
    max_tokens: 900,
    system: [{ type: "text", text: PLAYBOOK, cache_control: { type: "ephemeral" } }],
    messages: [{ role: "user", content: userText }],
  });
  const parts = (resp.content || []).map((b) => b.text).filter(Boolean);
  return parts.join("");
}

// --- Cache (in-memory; TODO(auth): move to DB) ------------------------------

const CACHE_TTL_MS = 24 * 60 * 60 * 1000;
const _cache = new Map(); // key -> { at, value }

function cacheGet(key) {
  const hit = _cache.get(key);
  if (!hit) return null;
  if (Date.now() - hit.at > CACHE_TTL_MS) { _cache.delete(key); return null; }
  return hit.value;
}
function cacheSet(key, value) {
  _cache.set(key, { at: Date.now(), value });
}

// --- Public API -------------------------------------------------------------

/**
 * Generate (or rewrite) all email copy slots for a play.
 *
 * @param {object} args
 * @param {object} args.play             normalized play (mechanism, one-liner, template_prompt)
 * @param {object} args.brandContext     brand voice + product language
 * @param {object} args.template         selected starting template
 * @param {Array}  args.products         [{ id, title, productType }]
 * @param {string} [args.cacheKey]       ${shopDomain}:${runId}:${playId}:${templateId}
 * @param {boolean}[args.regenerate]     true = rewrite: skip cache read, LLM always called
 * @param {object} [args.lockedSlots]    edited slots to preserve (rewrite; adopt #1)
 * @param {string} [args.steer]          optional revision note (adopt #4)
 * @returns {Promise<{available:boolean, copy?:object, fallback_slots?:string[], playbook_version?:string}>}
 */
async function generateCampaignCopy(args) {
  const { play, brandContext, template, products, cacheKey, regenerate, lockedSlots, steer } = args || {};

  if (!apiKeyPresent()) return { available: false };

  // Initial generate is cacheable; a rewrite (regenerate) always calls fresh
  // because it depends on the locked slots (adopt #1 / founder-locked cache rule).
  if (cacheKey && !regenerate) {
    const cached = cacheGet(cacheKey);
    if (cached) return cached;
  }

  const staticCopy = staticCopyFromPlay(play, template);
  const userText = userMessage({ play, brandContext, template, products, lockedSlots, steer });

  let parsed = null;
  try {
    parsed = parseCopyJson(await callModel(userText));
    if (parsed === null) {
      // Retry ONCE with a strict-JSON reminder.
      parsed = parseCopyJson(await callModel(userText + "\n\nReturn ONLY valid JSON. No other text."));
    }
  } catch (_) {
    return { available: false };
  }
  if (parsed === null) return { available: false };

  const { copy, fallback_slots } = validateAndFallback(parsed, staticCopy, products);

  // adopt #1: the server returns fresh copy for ALL slots (it saw the locked
  // slots as prompt context, so the result coheres with them). The FRONTEND
  // owns which slots are edited and applies the result to Suggested slots only,
  // never overwriting a merchant edit. So no server-side re-injection is needed.
  const result = { available: true, copy, fallback_slots, playbook_version: PLAYBOOK_VERSION };
  // Cache the latest result under the key for both initial and rewrite; a
  // rewrite overwrites so a later cache-read serves the freshest copy.
  if (cacheKey) cacheSet(cacheKey, result);
  return result;
}

// Map the play's static template_prompt into the slot shape the validator uses
// as its per-slot fallback source.
function staticCopyFromPlay(play, template) {
  const prompt = play?.template_prompt || {};
  return {
    subject: template?.subject || prompt.subject || "",
    previewText: template?.previewText || prompt.previewText || "",
    headline: template?.bodyH2 || prompt.headline || play?.play_name || "",
    body: template?.bodyP1 || prompt.body || prompt.support || "",
    support: prompt.support || "",
    cta: template?.cta || prompt.cta || "",
  };
}

module.exports = {
  generateCampaignCopy,
  // exported for tests / verification
  validateAndFallback,
  slotTextViolation,
  parseCopyJson,
  SLOT_KEYS,
  DEFAULT_MODEL,
};
