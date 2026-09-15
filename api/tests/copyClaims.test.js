const test = require("node:test");
const assert = require("node:assert/strict");
const Module = require("node:module");

// The copywriter's model call, replaced by a scripted response. The rules below
// are enforced on OUTPUT, so the test controls exactly what the "model" says.
let modelReply = "{}";
const modelCalls = [];
class FakeAnthropic {
  constructor() {
    this.messages = {
      create: async (request) => {
        modelCalls.push(request);
        return { content: [{ type: "text", text: modelReply }] };
      },
    };
  }
}
const originalLoad = Module._load;
Module._load = function load(request, ...rest) {
  if (request === "@anthropic-ai/sdk") return FakeAnthropic;
  return originalLoad.call(this, request, ...rest);
};
process.env.ANTHROPIC_API_KEY = "test-key";

const { audienceGuarantees, copyClaimViolation } = require("../src/services/copyClaims");
const { generateCampaignCopy, sanitizeStoredCopy, validateAndFallback } = require("../src/services/copywriterService");
const { presentEngineRun } = require("../src/services/engineRunPresenter");
const { buildBeaconTemplates } = require("../src/services/brandContextService");

test.after(() => { Module._load = originalLoad; });

const PRODUCTS = [
  { id: "1", title: "Hyaluronic Daily Moisturizer" },
  { id: "2", title: "Niacinamide Pore Serum" },
];
const FIRST_TO_SECOND = "cohort_journey_first_to_second";

test("the walkthrough's purchase claim is refused for an audience not defined by that product", () => {
  const claim = "You picked up the Hyaluronic Daily Moisturizer. Niacinamide Pore Serum is the natural next step.";
  assert.match(copyClaimViolation(claim, { playId: FIRST_TO_SECOND, products: PRODUCTS }), /specific product/);
  // Refused even when the catalog is not at hand: a purchase verb naming a product.
  assert.match(copyClaimViolation(claim, { playId: FIRST_TO_SECOND, products: [] }), /specific product/);
  // Naming the product neutrally is fine.
  assert.equal(copyClaimViolation("Explore Hyaluronic Daily Moisturizer.", { playId: FIRST_TO_SECOND, products: PRODUCTS }), null);
});

test("every common purchase construction is refused, with typographic apostrophes too", () => {
  const broad = { playId: FIRST_TO_SECOND, products: PRODUCTS };
  const noCatalog = { playId: FIRST_TO_SECOND, products: [] };
  for (const text of [
    "Thanks for purchasing Hyaluronic Daily Moisturizer.",
    "You’ve bought Hyaluronic Daily Moisturizer.",
    "You've bought Hyaluronic Daily Moisturizer.",
    "Thank you for your order of the Hyaluronic Daily Moisturizer!",
    "Thanks for choosing Hyaluronic Daily Moisturizer.",
    "Your recent purchase of Hyaluronic Daily Moisturizer is on its way.",
    "Hope you’re enjoying your Hyaluronic Daily Moisturizer.",
    "How’s your Hyaluronic Daily Moisturizer?",
  ]) {
    assert.match(copyClaimViolation(text, broad) || "", /specific product/, `with the catalog: ${text}`);
    assert.match(copyClaimViolation(text, noCatalog) || "", /specific product/, `without the catalog: ${text}`);
  }

  // Through the full validator: the review's two sentences never survive as copy.
  const { copy } = validateAndFallback({
    subject_variants: ["You’ve bought Hyaluronic Daily Moisturizer"],
    body: "Thanks for purchasing Hyaluronic Daily Moisturizer.",
    cta: "Shop the serum",
  }, { subject: "Thanks for your first order", body: "Thanks for your first order. Here are a few more things to explore.", cta: "Shop the picks" }, PRODUCTS, { playId: FIRST_TO_SECOND });
  assert.deepEqual(copy.subject_variants, ["Thanks for your first order"]);
  assert.equal(copy.body, "Thanks for your first order. Here are a few more things to explore.");

  // Generic thanks, where the audience guarantees an order, stays allowed.
  assert.equal(copyClaimViolation("Thanks for purchasing with us.", broad), null);
  assert.equal(copyClaimViolation("Thanks for your first order.", broad), null);
});

test("a generic purchase claim is allowed only where the audience guarantees an order", () => {
  assert.equal(audienceGuarantees(FIRST_TO_SECOND).priorPurchase, true);
  assert.equal(copyClaimViolation("Thanks for your first order.", { playId: FIRST_TO_SECOND }), null);
  assert.match(copyClaimViolation("Thanks for your first order.", { playId: "bestseller_amplify" }), /no prior order/);
  assert.match(copyClaimViolation("Thanks for your first order.", { playId: "a_play_added_later" }), /no prior order/, "unknown plays guarantee nothing");
  assert.match(copyClaimViolation("You keep coming back for more.", { playId: FIRST_TO_SECOND }), /repeat purchase/, "first-time buyers have one order");
});

test("preference, usage, performance, stock and offer claims are refused", () => {
  const ctx = { playId: "winback_dormant_cohort", products: PRODUCTS };
  for (const text of [
    "Your favorites are still here.",
    "Still thinking about Niacinamide Pore Serum?",
    "Running low? Reorder in a tap.",
    "No pilling, no wait time.",
    "Clinically proven to hydrate.",
    "Back in stock and selling fast.",
    "The ones everyone keeps reordering.",
    "Come back and save.",
    "We've kept your favorites in stock.",
  ]) {
    assert.ok(copyClaimViolation(text, ctx), `refused: ${text}`);
  }
  assert.equal(copyClaimViolation("It's been a little while. Take another look around the shop.", ctx), null);
});

test("generated copy with unsupported claims falls back slot by slot", () => {
  const { copy, fallback_slots } = validateAndFallback({
    subject_variants: ["You picked up the Hyaluronic Daily Moisturizer", "A few picks for your next order", "Your favorites are back"],
    preview_text: "A few picks worth a look",
    headline: "Explore Niacinamide Pore Serum",
    body: "No pilling, no wait time. Just a serum that works.",
    support: "",
    cta: "Shop the serum",
    rationale: "",
    featured_product_id: "2",
  }, {
    subject: "Thanks for your first order", previewText: "p", headline: "h",
    body: "Thanks for your first order. Here are a few more things to explore.", support: "", cta: "Shop the picks",
  }, PRODUCTS, { playId: FIRST_TO_SECOND });

  assert.deepEqual(copy.subject_variants, ["A few picks for your next order"], "claiming subjects are removed");
  assert.equal(copy.body, "Thanks for your first order. Here are a few more things to explore.");
  assert.ok(fallback_slots.includes("body"));
  assert.equal(copy.headline, "Explore Niacinamide Pore Serum", "clean slots are kept");
});

test("a fallback that itself makes a claim leaves the slot empty", () => {
  const { copy } = validateAndFallback(
    { subject_variants: [], body: "Your favorites are waiting.", cta: "Shop" },
    { subject: "Still thinking about it?", body: "Your favorites are still here.", cta: "Shop the picks" },
    PRODUCTS,
    { playId: "winback_dormant_cohort" },
  );
  assert.deepEqual(copy.subject_variants, []);
  assert.equal(copy.body, "");
});

test("initial generation and rewrites are both held to the rules", async () => {
  const play = { play_id: FIRST_TO_SECOND, template_prompt: { subject: "Thanks for your first order", body: "Thanks for your first order. Here are a few more things to explore." } };
  modelReply = JSON.stringify({
    subject_variants: ["You picked up the Hyaluronic Daily Moisturizer", "A few picks for you", "Take a look"],
    preview_text: "A few picks", headline: "Explore Niacinamide Pore Serum",
    body: "You bought the Hyaluronic Daily Moisturizer, so pair it with the serum.", support: "", cta: "Shop the serum", rationale: "", featured_product_id: "2",
  });

  const first = await generateCampaignCopy({ play, brandContext: {}, template: null, products: PRODUCTS });
  assert.equal(first.available, true);
  assert.ok(!first.copy.subject_variants.some((s) => /picked up/i.test(s)));
  assert.doesNotMatch(first.copy.body, /bought/);

  const rewrite = await generateCampaignCopy({
    play, brandContext: {}, template: null, products: PRODUCTS,
    regenerate: true, lockedSlots: { headline: "Explore Niacinamide Pore Serum" }, steer: "Warmer",
  });
  assert.doesNotMatch(rewrite.copy.body, /bought/, "a rewrite is validated the same way");
  assert.match(modelCalls.at(-1).messages[0].content, /Never say or imply what the reader bought/);
});

test("copy stored before the rules is checked again when served", () => {
  const stored = {
    copy: { subject_variants: ["Still thinking about it?"], body: "You picked up the Hyaluronic Daily Moisturizer.", headline: "Explore Niacinamide Pore Serum", featured_product_id: "2", featured_product: { title: "Niacinamide Pore Serum" } },
    fallback_slots: [],
    playbook_version: "v1",
  };
  const served = sanitizeStoredCopy(stored, { playId: FIRST_TO_SECOND, products: PRODUCTS });
  assert.deepEqual(served.copy.subject_variants, []);
  assert.equal(served.copy.body, "", "blanked, so the draft uses its starting template");
  assert.equal(served.copy.headline, "Explore Niacinamide Pore Serum");
  assert.equal(served.copy.featured_product.title, "Niacinamide Pore Serum");
  assert.equal(served.playbook_version, "v1");
});

test("every piece of starting copy passes the rules for every play it can be used with", () => {
  const playIds = [
    "winback_dormant_cohort", "winback_21_45", FIRST_TO_SECOND, "aov_lift_via_threshold_bundle",
    "discount_dependency_hygiene", "discount_hygiene", "bestseller_amplify", "replenishment_due",
    "at_risk_repeat_buyer_rescue", "subscription_nudge", "frequency_accelerator", "routine_builder", "empty_bottle",
  ];
  const presented = presentEngineRun({
    run_id: "r", abstain: { state: "publish", mode: null }, data_quality_flags: [], considered: [], watching: [],
    recommendations: playIds.map((play_id) => ({ play_id, audience: { size: 10 }, evidence_source: "STORE_OBSERVED" })),
  });
  for (const card of presented.recommendations) {
    for (const [slot, text] of Object.entries(card.template_prompt || {})) {
      assert.equal(copyClaimViolation(text, { playId: card.play_id, products: PRODUCTS }), null, `${card.play_id}.${slot}: ${text}`);
    }
  }

  const templates = buildBeaconTemplates({ brandName: "Acme", productLanguage: { bestSellers: [{ title: "Niacinamide Pore Serum" }] }, messaging: {} });
  for (const template of templates) {
    for (const slot of ["subject", "previewText", "bodyH2", "bodyP1", "cta"]) {
      for (const playId of playIds) {
        assert.equal(copyClaimViolation(template[slot], { playId, products: PRODUCTS }), null, `${template.id}.${slot} for ${playId}: ${template[slot]}`);
      }
    }
  }
});
