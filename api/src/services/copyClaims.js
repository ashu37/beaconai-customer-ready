// What customer-facing email copy may claim about the person reading it.
//
// Enforced on OUTPUT, never left to a prompt instruction. A generated email told
// 413 first-time buyers "You picked up the Hyaluronic Daily Moisturizer" when the
// audience was every first-time buyer, whatever they bought (merchant walkthrough,
// 2026-09-14). A claim like that goes to real customers, so it is decided by the
// audience definition, not by the model's confidence.
//
// Rules, applied to every generated slot — initial copy, rewrites, and copy served
// from the cache — and to the starting templates:
//   1. A PRODUCT-SPECIFIC purchase claim is never allowed. No audience today is
//      defined by a purchased product, so none guarantees it. Name the product
//      neutrally instead ("Explore Hyaluronic Daily Moisturizer").
//   2. A GENERIC purchase claim ("your first order") is allowed only when the
//      play's audience is defined by having ordered.
//   3. Preference, interest and usage claims ("your favorites", "still thinking
//      about", "running low") are never allowed: nothing records them.
//   4. Product-performance, stock and popularity claims ("no pilling",
//      "clinically proven", "back in stock", "everyone keeps reordering") are
//      never allowed: nothing the merchant can inspect supports them.
//   5. Offer implications ("come back and save", "a little something") are never
//      allowed: the app creates no offer.
//
// Text the MERCHANT writes is theirs and is not checked here.

// Plays whose audience definition requires at least one prior order. Anything
// not listed — including plays added later — is treated as not guaranteeing it.
const PRIOR_PURCHASE_AUDIENCES = new Set([
  "winback_dormant_cohort",       // last order 21–45d ago, >= 2 prior orders
  "winback_21_45",
  "cohort_journey_first_to_second", // first-time buyers: exactly one order
  "discount_dependency_hygiene",  // >= 50% of historical orders discounted
  "at_risk_repeat_buyer_rescue",
  "subscription_nudge",
  "replenishment_due",
  "empty_bottle",
  "frequency_accelerator",
  "routine_builder",
]);

const FIRST_ORDER_ONLY_AUDIENCES = new Set(["cohort_journey_first_to_second"]);

function audienceGuarantees(playId) {
  const id = String(playId || "");
  return {
    priorPurchase: PRIOR_PURCHASE_AUDIENCES.has(id),
    firstOrderOnly: FIRST_ORDER_ONLY_AUDIENCES.has(id),
    // No audience is defined by a specific purchased product.
    purchasedProduct: false,
  };
}

// Statements about what the reader bought. One list of constructions, so every
// check below uses the same coverage:
//   "you bought / you've purchased / you just picked up …"
//   "thanks for purchasing / thank you for your order of / thanks for choosing …"
//   "your purchase of … / your recent order …"
//   "hope you're enjoying your …"
// Checked on normalized text, so curly apostrophes ("You’ve") match too.
const PURCHASE_VERBS = "(?:picked up|bought|purchased|ordered|got|grabbed|tried|chose|chosen|added|went with|snagged|shopped)";
const PURCHASE_CONSTRUCTIONS = [
  `\\byou(?:'ve| have| had)?\\s+(?:recently\\s+|already\\s+|just\\s+|previously\\s+)?${PURCHASE_VERBS}\\b`,
  "\\bthanks?(?: you)?\\s+(?:so much\\s+)?for\\s+(?:purchasing|buying|ordering|choosing|picking up|shopping for|trying|getting|your (?:purchase|order)(?: of)?)\\b",
  "\\byour\\s+(?:recent\\s+|latest\\s+|last\\s+|new\\s+)?(?:purchase|order)\\s+of\\b",
  "\\b(?:hope|hoping)\\s+you(?:'re| are)?\\s+(?:enjoying|loving|liking)\\b",
  "\\bhow(?:'s| is| are)\\s+(?:your|you liking)\\b",
];
const PURCHASE_CONSTRUCTION = new RegExp(PURCHASE_CONSTRUCTIONS.join("|"), "i");
// The same constructions, found one by one so the words after each can be read.
const PURCHASE_CONSTRUCTION_ALL = new RegExp(PURCHASE_CONSTRUCTIONS.join("|"), "gi");
// "… the Hyaluronic Daily Moisturizer": a capitalized name right after a purchase
// construction. Catches the product-specific claim when the catalog is not at
// hand. Case-sensitive on the name, which is why it is a separate test.
const NAMED_THING_AFTER = /^\s+(?:(?:the|a|an|your|our|that|this)\s+)?[A-Z][\w'-]+/;
// "your first order", "since your last purchase", "your first pick"
const GENERIC_PURCHASE = /\b(?:your|since your)\s+(?:first|last|latest|recent|previous|most recent)\s+(?:order|purchase|pick|visit)\b|\bgreat first pick\b|\bwhat you (?:already )?(?:have|own|bought|ordered)\b/i;

// Typographic punctuation a model or a merchant's keyboard produces, folded to
// the plain forms the patterns are written against.
function normalize(text) {
  return String(text || "")
    .replace(/[\u2018\u2019\u201B\u02BC\uFF07]/g, "'")
    .replace(/[\u201C\u201D\u201F]/g, '"')
    .replace(/\u00A0/g, " ");
}

function namesThingAfterPurchase(sentence) {
  for (const match of sentence.matchAll(PURCHASE_CONSTRUCTION_ALL)) {
    if (NAMED_THING_AFTER.test(sentence.slice(match.index + match[0].length))) return true;
  }
  return false;
}
const REPEAT_PURCHASE = /\b(?:you reorder|you keep coming back|your (?:second|next) order again|every order you've placed|your orders)\b/i;

const PREFERENCE_OR_USAGE = [
  /\byour (?:(?:old |all-time )?favou?rites?|go-tos?)\b/i,
  /\b(?:you|you've|you have)\s+(?:loved?|enjoyed|had your eye on|been eyeing|been shopping for|been using|been looking at)\b/i,
  /\bstill thinking about\b/i,
  /\bwhat you(?:'ve| have)? (?:been )?(?:love|loved|like|liked|shopping for|browsing)\b/i,
  /\bleft (?:in|behind in) your (?:cart|bag)\b/i,
  /\b(?:running low|run(?:ning)? out|due for a refill|time for a refill|about due)\b/i,
  /\bpicked (?:just )?for you based on\b/i,
];

const PERFORMANCE_OR_STOCK = [
  /\b(?:clinically|scientifically|dermatologist[- ]|lab[- ]tested|proven|guaranteed?|award[- ]winning)\b/i,
  /\bno (?:pilling|residue|wait(?:ing)? time|breakouts?|irritation|greasiness|shedding)\b/i,
  /\b(?:lasts? all day|all[- ]day wear|long[- ]lasting|quality that lasts|built to last)\b/i,
  /\b(?:reduces?|eliminates?|prevents?|repairs?|cures?|heals?|clears? up|visibly)\b/i,
  /\b(?:back in stock|restock(?:ed)?|kept (?:\w+ )?in stock|selling (?:out|fast)|sold out|only \d+ left|limited (?:stock|time|edition)|while (?:stocks|supplies) last)\b/i,
  /\b(?:everyone (?:keeps|is|loves)|customers (?:keep|love|can't stop)|other customers|most people|fan[- ]favou?rite|cult[- ]favou?rite|keep reordering)\b/i,
];

const OFFER_IMPLICATION = [
  /\b(?:and save|save on|save big|a little something|thank-you gift|free gift|reward|get more for your order|unlock(?:ing)? more|something extra)\b/i,
];

// Sentences, so a product name and a purchase verb are judged together.
function sentences(text) {
  return String(text || "").split(/(?<=[.!?])\s+|\n+/).filter((s) => s.trim());
}

function mentionsProduct(sentence, productNames) {
  const lower = sentence.toLowerCase();
  return productNames.some((name) => name.length >= 4 && lower.includes(name));
}

// Returns a reason string for the first unsupported claim, or null.
function copyClaimViolation(text, { playId = null, products = [] } = {}) {
  const value = normalize(text);
  if (!value.trim()) return null;
  const guarantees = audienceGuarantees(playId);
  const productNames = (products || []).map((p) => normalize(p.title || p.name || "").toLowerCase().trim()).filter(Boolean);

  for (const sentence of sentences(value)) {
    const purchaseClaim = PURCHASE_CONSTRUCTION.test(sentence) || GENERIC_PURCHASE.test(sentence);
    const namesProduct = mentionsProduct(sentence, productNames) || namesThingAfterPurchase(sentence);
    if (purchaseClaim && namesProduct && !guarantees.purchasedProduct) {
      return "unsupported purchase claim (specific product)";
    }
    if (purchaseClaim && !guarantees.priorPurchase) {
      return "unsupported purchase claim (no prior order guaranteed)";
    }
    if (REPEAT_PURCHASE.test(sentence) && (!guarantees.priorPurchase || guarantees.firstOrderOnly)) {
      return "unsupported purchase claim (repeat purchase)";
    }
  }
  if (PREFERENCE_OR_USAGE.some((re) => re.test(value))) return "unsupported preference or usage claim";
  if (PERFORMANCE_OR_STOCK.some((re) => re.test(value))) return "unsupported product, stock or popularity claim";
  if (OFFER_IMPLICATION.some((re) => re.test(value))) return "implied offer";
  return null;
}

module.exports = {
  audienceGuarantees,
  copyClaimViolation,
};
