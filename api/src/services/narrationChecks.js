// Checks that a recommendation's generated prose agrees with its own evidence.
//
// The engine's narration guards trace dollar figures. These trace the rest of
// what a merchant reads, against the card's STRUCTURED fields — never against the
// model's say-so (merchant walkthrough, 2026-09-14):
//
//   1. Percentages. The engine's observed effect for a two-proportion metric is a
//      CHANGE in percentage points, not a rate. "The conversion rate sits at
//      roughly 0.5%" presented +0.5 points as the current rate. A percentage must
//      be the observed change, in its own unit, described as a change.
//   2. Day counts. Every "N days" must come from the audience definition or the
//      measurement windows, and an inactivity claim ("quiet for 21 or more days")
//      must use the definition's actual bound (no order in the last 28 days).
//   3. What is created. The app creates ONE email and no offer. Prose describing
//      a sequence, follow-ups or a discount describes something that won't exist.
//   4. Sample units. `measurement.n` means different things per metric; for the
//      discount play it is revenue, so "Across 60,528 orders" is false.
//   5. Internal vocabulary. "a prior-anchored estimate", "a considered play",
//      "No revenue figure to state" and play ids are the engine talking to
//      itself, not an explanation a merchant can use (walkthrough #14).
//
// A field that fails is dropped, not repaired. The briefing then shows the
// card's factual evidence for that tab instead of prose (Pivot 2: prose is the
// model's or nothing).

const NARRATION_FIELDS = ["play_thesis", "what_we_d_send", "evidence_summary"];

// SAMPLE_UNITS from the presenter, by metric: what one unit of `n` is.
const CUSTOMER_SAMPLE_METRICS = new Set([
  "reactivation_rate",
  "replenishment_conversion_rate",
  "first_to_second_conversion_rate",
  "returning_customer_share",
  "repeat_rate_within_window",
]);

function sentences(text) {
  return String(text || "").split(/(?<=[.!?])\s+/).filter((s) => s.trim());
}

function sentenceAt(text, index) {
  let start = 0;
  for (const sentence of sentences(text)) {
    const at = text.indexOf(sentence, start);
    if (index >= at && index < at + sentence.length) return sentence;
    start = at + sentence.length;
  }
  return text;
}

// --- 1. Percentages ---------------------------------------------------------

// An optional explicit sign is part of the figure: "+20.6 points", "−20.6 points".
const PERCENT_FIGURE = /([+\-\u2212]?)(\d+(?:\.\d+)?)\s*(percentage points?|percent\b|pp\b|points?\b|%)/gi;
const UP_WORDS = "up|rose|risen|rising|increased?|increasing|grew|grown|growing|higher|gained?|climbed|jumped|improved|improving";
const DOWN_WORDS = "down|fell|fallen|falling|dropped|dropping|declined?|declining|decreased?|decreasing|lower|lost|slipped|shrank|shrunk|worsened";
const CHANGE_WORDS = new RegExp(`\\b(?:${UP_WORDS}|${DOWN_WORDS}|shift(?:ed)?|changed?|moved)\\b`, "i");
const DIRECTION_WORD = new RegExp(`\\b(${UP_WORDS}|${DOWN_WORDS})\\b`, "gi");
const IS_UP = new RegExp(`^(?:${UP_WORDS})$`, "i");

// The direction a sentence claims for the figure at `index`: its explicit sign,
// else the direction word nearest to it ("down 20.6 points", "20.6 points
// lower"). null when the sentence names no direction ("changed by 20.6 points").
function claimedDirection(sentence, figureIndex, sign) {
  if (sign === "+") return "up";
  if (sign === "-" || sign === "\u2212") return "down";
  let nearest = null;
  for (const match of sentence.matchAll(DIRECTION_WORD)) {
    const distance = Math.abs(match.index - figureIndex);
    if (!nearest || distance < nearest.distance) nearest = { distance, up: IS_UP.test(match[1]) };
  }
  return nearest ? (nearest.up ? "up" : "down") : null;
}
const RATE_FRAMING = /\b(?:sits? at|stands? at|is at|at roughly|at approximately|at about|at around|rate of|currently)\b/i;

function checkPercentages(text, change) {
  const violations = [];
  for (const match of text.matchAll(PERCENT_FIGURE)) {
    const sign = match[1];
    const value = Number(match[2]);
    const unitToken = match[3].toLowerCase();
    const sentence = sentenceAt(text, match.index);
    if (!change || !["percentage_points", "percent"].includes(change.unit)) {
      violations.push({ rule: "percentage_untraceable", figure: match[0] });
      continue;
    }
    const expected = Math.abs(Number(change.value));
    const close = Math.abs(value - expected) <= Math.max(0.1, expected * 0.1);
    const pointsToken = /point|pp/.test(unitToken);
    const unitMatches = change.unit === "percentage_points" ? pointsToken : !pointsToken;
    if (!close) {
      violations.push({ rule: "percentage_untraceable", figure: match[0] });
    } else if (!unitMatches) {
      violations.push({ rule: "percentage_wrong_unit", figure: match[0], expectedUnit: change.unit });
    } else if (RATE_FRAMING.test(sentence) || !(sign || CHANGE_WORDS.test(sentence))) {
      violations.push({ rule: "change_presented_as_rate", figure: match[0] });
    } else {
      // The right size in the wrong direction is the opposite finding.
      const actual = Number(change.value) > 0 ? "up" : Number(change.value) < 0 ? "down" : null;
      const claimed = claimedDirection(sentence, match.index - text.indexOf(sentence), sign);
      if (actual && claimed && claimed !== actual) {
        violations.push({ rule: "direction_reversed", figure: match[0], observed: actual });
      }
    }
  }
  return violations;
}

// --- 2. Day counts ----------------------------------------------------------

function numbersIn(value) {
  return (String(value || "").match(/\d+/g) || []).map(Number);
}

// Every day count the card itself establishes: the audience definition, the
// measurement window (L56 → 56), and the mechanism's *_days parameters.
function allowedDays(card) {
  const allowed = new Set(numbersIn(card?.audience?.definition));
  const window = /^L(\d+)$/i.exec(String(card?.measurement?.primary_window || ""));
  if (window) allowed.add(Number(window[1]));
  for (const [key, param] of Object.entries(card?.mechanism_intent?.parameters || {})) {
    if (!/day|window/i.test(key)) continue;
    for (const n of numbersIn(JSON.stringify(param))) allowed.add(n);
  }
  return allowed;
}

// The inactivity the audience definition actually requires. "last order 21-45d
// ago … no order in last 28d" means at least 28 days without an order.
function inactivityBound(card) {
  const definition = String(card?.audience?.definition || "");
  const bounds = [];
  const noOrder = /no (?:order|purchase)s? in (?:the )?last\s*(\d+)\s*d/i.exec(definition);
  if (noOrder) bounds.push(Number(noOrder[1]));
  const lastOrder = /last order\s*(\d+)\s*(?:-|–|to)\s*(\d+)\s*d/i.exec(definition);
  if (lastOrder) bounds.push(Number(lastOrder[1]));
  if (bounds.length) return Math.max(...bounds);
  const fromIntent = Number(card?.mechanism_intent?.parameters?.dormancy_window_days);
  return Number.isFinite(fromIntent) ? fromIntent : null;
}

const DAY_FIGURE = /(\d+)(?:\s*(?:-|–|to)\s*(\d+))?\s*(?:\+\s*)?(?:or more\s+)?[- ]?(?:days?|d)\b/gi;
const INACTIVITY_WORDS = /\b(?:dormant|quiet|inactive|lapsed?|haven'?t (?:purchased|ordered|bought|returned)|no (?:order|purchase)s?|nothing|without (?:an? )?(?:order|purchase)|since their last)\b/i;
// Words just before a day figure that make it an open-ended inactivity bound
// ("at least 21 days", "for 21 days", "in the last 28 days"), or a "+"/"or more"
// inside the figure itself. Judged per figure: "within a 30-day window" in the
// same sentence is not an inactivity claim.
const OPEN_ENDED_BEFORE = /\b(?:at least|more than|over|for|last|beyond|past)\s*$/i;
const OPEN_ENDED_WITHIN = /\+|or more/i;

function checkDays(text, card) {
  const violations = [];
  const allowed = allowedDays(card);
  const bound = inactivityBound(card);
  for (const match of text.matchAll(DAY_FIGURE)) {
    const low = Number(match[1]);
    const high = match[2] == null ? null : Number(match[2]);
    for (const n of [low, high].filter((v) => v != null)) {
      if (!allowed.has(n)) violations.push({ rule: "days_untraceable", figure: match[0] });
    }
    const sentence = sentenceAt(text, match.index);
    const before = text.slice(Math.max(0, match.index - 20), match.index);
    const openEnded = OPEN_ENDED_BEFORE.test(before) || OPEN_ENDED_WITHIN.test(match[0]);
    if (high == null && bound != null && openEnded && INACTIVITY_WORDS.test(sentence) && low !== bound) {
      // The measurement window ("in the last 56 days") is not an inactivity claim.
      const window = /^L(\d+)$/i.exec(String(card?.measurement?.primary_window || ""));
      if (!(window && low === Number(window[1]))) {
        violations.push({ rule: "inactivity_mismatch", figure: match[0], definitionDays: bound });
      }
    }
  }
  return violations;
}

// --- 3. What the app creates ------------------------------------------------

const SEQUENCE = /\b(?:sequence|series|drip|flows?|cadence|multi[- ]?step|multi[- ]?touch|follow[- ]ups?|emails)\b/i;
const OFFER = /\b(?:percent[- ]off|\d+\s*%\s*off|discount (?:code|offer)|coupon|promo(?:tional)? code|incentive|offer)\b/gi;
const NEGATION_BEFORE = /\b(?:no|without|not|rather than|never)\b[^.]{0,40}$/i;

function checkCreates(text) {
  const violations = [];
  if (SEQUENCE.test(text)) violations.push({ rule: "describes_multiple_emails" });
  for (const match of text.matchAll(OFFER)) {
    const before = text.slice(Math.max(0, match.index - 60), match.index);
    if (!NEGATION_BEFORE.test(before)) {
      violations.push({ rule: "describes_offer", figure: match[0] });
      break;
    }
  }
  return violations;
}

// --- 4. Sample units --------------------------------------------------------

const COUNT_WITH_NOUN = /(\d{1,3}(?:,\d{3})+|\d+)\s+(?:\w+\s+)?(orders|customers|shoppers|buyers|people)\b/gi;

function checkSampleUnits(text, card) {
  const violations = [];
  const n = Number(card?.measurement?.n);
  const audienceSize = Number(card?.audience?.size);
  if (!Number.isFinite(n)) return violations;
  for (const match of text.matchAll(COUNT_WITH_NOUN)) {
    const count = Number(match[1].replace(/,/g, ""));
    if (count !== n || count === audienceSize) continue;
    const noun = match[2].toLowerCase();
    const customersOk = CUSTOMER_SAMPLE_METRICS.has(card?.measurement?.metric) && noun !== "orders";
    if (!customersOk) violations.push({ rule: "sample_wrong_unit", figure: match[0] });
  }
  return violations;
}

// --- 5. Internal vocabulary -------------------------------------------------

const INTERNAL_VOCABULARY = [
  /\bposterior\b/i,
  /\bprior[- ]anchored\b/i,
  /\bbefore (?:the )?anchor\b|\banchor date\b/i,
  /\bconsidered play\b/i,
  /\bno (?:revenue|dollar) figure (?:to state|is stated)\b/i,
  /\bpseudo[- ]?n\b|\bbayesian\b|\bp[- ]value\b/i,
  /\b\d+(?:\.\d+)?\s*pp\b/i,
  /\b[a-z0-9]+(?:_[a-z0-9]+){2,}\b/, // play ids such as winback_dormant_cohort
];

function checkVocabulary(text) {
  const hit = INTERNAL_VOCABULARY.find((re) => re.test(text));
  return hit ? [{ rule: "internal_vocabulary", figure: text.match(hit)[0] }] : [];
}

// ---------------------------------------------------------------------------

function checkNarrationText(text, { card, observedChange }) {
  const value = String(text || "");
  if (!value.trim()) return [];
  return [
    ...checkPercentages(value, observedChange),
    ...checkDays(value, card),
    ...checkCreates(value),
    ...checkSampleUnits(value, card),
    ...checkVocabulary(value),
  ];
}

// Returns the narration with every failing field set to null, and what failed.
function checkNarration(narration, { card, observedChange }) {
  if (!narration) return { narration, violations: [] };
  const checked = { ...narration };
  const violations = [];
  for (const field of NARRATION_FIELDS) {
    const found = checkNarrationText(narration[field], { card, observedChange });
    if (found.length) {
      checked[field] = null;
      violations.push(...found.map((v) => ({ field, ...v })));
    }
  }
  return { narration: checked, violations };
}

module.exports = {
  checkNarration,
  checkNarrationText,
  inactivityBound,
};
