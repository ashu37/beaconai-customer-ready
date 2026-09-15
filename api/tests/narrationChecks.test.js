const test = require("node:test");
const assert = require("node:assert/strict");

const { checkNarrationText, inactivityBound } = require("../src/services/narrationChecks");
const { presentEngineRun } = require("../src/services/engineRunPresenter");

// Cards and sentences from the stored acme run the merchant walkthrough read
// (2026-09-14): the engine's structured fields, and what the narration said.
const WINBACK = {
  play_id: "winback_dormant_cohort",
  evidence_source: "STORE_OBSERVED",
  audience: { size: 234, definition: "last order 21-45d ago, >=2 prior orders, no order in last 28d" },
  measurement: { metric: "reactivation_rate", observed_effect: -0.205607, n: 107, primary_window: "L56" },
  mechanism_intent: { type: "WINBACK_REACTIVATION_EMAIL", parameters: { offer_type: "percent_off", dormancy_window_days: 21, measurement_window_days: 30 } },
};
const DISCOUNT = {
  play_id: "discount_dependency_hygiene",
  evidence_source: "STORE_OBSERVED",
  audience: { size: 555, definition: "customers whose >=50% of historical orders carried a discount" },
  measurement: { metric: "discount_dependency_hygiene_full_price_conversion_rate", observed_effect: 0.053333, n: 60528, primary_window: "L56" },
  mechanism_intent: { type: "DISCOUNT_DEPENDENCY_HYGIENE", parameters: {} },
};
const FIRST_TO_SECOND = {
  play_id: "cohort_journey_first_to_second",
  evidence_source: "STORE_OBSERVED",
  audience: { size: 413, definition: "first-time buyers whose only order is 30-90 days before anchor" },
  measurement: { metric: "first_to_second_conversion_rate", observed_effect: 0.004842, n: 290, primary_window: "L56" },
  mechanism_intent: { type: "FIRST_TO_SECOND_NUDGE", parameters: { measurement_window_days: 30, days_since_first_order_window: [30, 90] } },
};
const points = (value) => ({ unit: "percentage_points", value });
const rules = (text, card, change) => checkNarrationText(text, { card, observedChange: change }).map((v) => v.rule);

test("a change in percentage points is not presented as the current rate", () => {
  assert.deepEqual(
    rules("Across 290 observed customers, the store's first-to-second conversion rate sits at roughly 0.5% in the last 56 days.", FIRST_TO_SECOND, points(0.5)),
    ["percentage_wrong_unit"],
  );
  assert.deepEqual(
    rules("The second-purchase rate sits at 0.5 percentage points.", FIRST_TO_SECOND, points(0.5)),
    ["change_presented_as_rate"],
  );
  assert.deepEqual(rules("The second-purchase rate is up 0.5 percentage points on the 56 days before.", FIRST_TO_SECOND, points(0.5)), []);
  assert.deepEqual(rules("Reactivation is down 20.6 points.", WINBACK, points(-20.6)), []);
  assert.deepEqual(rules("Reactivation is down 35 points.", WINBACK, points(-20.6)), ["percentage_untraceable"]);
});

test("a change reported in the wrong direction is refused, however it is signed", () => {
  // Observed: reactivation DOWN 20.6 points; second purchases UP 0.5 points.
  assert.deepEqual(rules("Reactivation is up 20.6 percentage points.", WINBACK, points(-20.6)), ["direction_reversed"]);
  assert.deepEqual(rules("Reactivation moved +20.6 points on the prior period.", WINBACK, points(-20.6)), ["direction_reversed"]);
  assert.deepEqual(rules("Reactivation is 20.6 points higher than before.", WINBACK, points(-20.6)), ["direction_reversed"]);
  assert.deepEqual(rules("The second-purchase rate fell 0.5 percentage points.", FIRST_TO_SECOND, points(0.5)), ["direction_reversed"]);
  assert.deepEqual(rules("The second-purchase rate moved −0.5 points.", FIRST_TO_SECOND, points(0.5)), ["direction_reversed"]);

  // The right direction, by word or sign, passes; so does naming no direction.
  assert.deepEqual(rules("Reactivation is down 20.6 percentage points.", WINBACK, points(-20.6)), []);
  assert.deepEqual(rules("Reactivation moved −20.6 points.", WINBACK, points(-20.6)), []);
  assert.deepEqual(rules("The second-purchase rate is 0.5 percentage points higher.", FIRST_TO_SECOND, points(0.5)), []);
  assert.deepEqual(rules("Reactivation changed by 20.6 percentage points.", WINBACK, points(-20.6)), []);
});

test("inactivity claims use the audience definition's own bound", () => {
  assert.equal(inactivityBound(WINBACK), 28, "no order in the last 28 days, not the 21-day parameter");
  assert.deepEqual(
    rules("You have 234 customers who placed at least two orders but have gone quiet for 21 or more days.", WINBACK, points(-20.6)),
    ["inactivity_mismatch"],
  );
  assert.deepEqual(rules("They've ordered at least twice but nothing in the last 28 days.", WINBACK, points(-20.6)), []);
  assert.deepEqual(rules("Customers inactive for at least 12 days.", WINBACK, points(-20.6)), ["days_untraceable", "inactivity_mismatch"]);
  assert.deepEqual(rules("413 first-time buyers placed their only order between 30 and 90 days ago.", FIRST_TO_SECOND, points(0.5)), []);
});

test("prose may only describe the one email the app creates, with no offer", () => {
  assert.deepEqual(
    rules("A winback reactivation email sequence targeting customers dormant for at least 21 days, featuring a percent-off offer, measured within a 30-day window.", WINBACK, points(-20.6)),
    ["inactivity_mismatch", "describes_multiple_emails", "describes_offer"],
  );
  assert.deepEqual(rules("A carefully sequenced outreach, without leading with a promotional offer.", DISCOUNT, points(5.3)), [], "a negated offer is not an offer");
  assert.deepEqual(rules("A first-to-second nudge email to customers whose first order was 30-90 days ago.", FIRST_TO_SECOND, points(0.5)), []);
});

test("a sample count is described in its own unit", () => {
  assert.deepEqual(
    rules("Across 60,528 orders in the last 56 days, the full-price conversion rate sits at approximately 5.3%.", DISCOUNT, points(5.3)),
    ["percentage_wrong_unit", "sample_wrong_unit"],
  );
  assert.deepEqual(rules("Across 107 customers observed in the last 56 days, reactivation is down 20.6 points.", WINBACK, points(-20.6)), []);
});

test("the briefing drops only the prose that contradicts the evidence", () => {
  const presented = presentEngineRun({
    run_id: "run-1", abstain: { state: "publish", mode: null }, data_quality_flags: [], considered: [], watching: [],
    recommendations: [WINBACK, FIRST_TO_SECOND],
  }, null, {
    cards: [
      {
        play_id: "winback_dormant_cohort", role: "recommendation", used_fallback: false,
        play_thesis: "They've ordered at least twice but nothing in the last 28 days, so now is the moment to reach them.",
        what_we_d_send: "A winback email sequence with a percent-off offer.",
        evidence_summary: "Across 107 customers observed in the last 56 days, reactivation is down 20.6 points.",
      },
      {
        play_id: "cohort_journey_first_to_second", role: "recommendation", used_fallback: false,
        play_thesis: "413 first-time buyers placed their only order between 30 and 90 days ago.",
        what_we_d_send: "A first-to-second nudge email to customers whose first order was 30-90 days ago.",
        evidence_summary: "The store's first-to-second conversion rate sits at roughly 0.5%.",
      },
    ],
  });
  const [winback, journey] = presented.recommendations;

  assert.ok(winback.narration.play_thesis, "consistent thesis kept");
  assert.equal(winback.narration.what_we_d_send, null, "sequence and offer dropped");
  assert.ok(winback.narration.evidence_summary);
  assert.equal(winback.mechanism, winback.narration.play_thesis);

  assert.equal(journey.narration.evidence_summary, null, "delta-as-rate dropped");
  assert.ok(journey.narration.play_thesis);
  assert.deepEqual(journey.narration.claim_violations.map((v) => `${v.field}:${v.rule}`), ["evidence_summary:percentage_wrong_unit"]);
  // The evidence itself is still there for the tab.
  assert.equal(journey.evidence_facts.observed_change.unit, "percentage_points");
});
