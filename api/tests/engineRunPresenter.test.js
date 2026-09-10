const test = require("node:test");
const assert = require("node:assert/strict");

const { presentEngineRun, REASON_DISPLAY, EVIDENCE_SOURCE_DISPLAY } = require("../src/services/engineRunPresenter");

// Ticket E presenter fixtures. The cards mirror a real stored run for the local
// test store (Sep 8, 2026): three STORE_OBSERVED directional recommendations and
// six held plays across three different reason codes.
function card(overrides = {}) {
  return {
    play_id: "winback_dormant_cohort",
    evidence_class: "directional",
    evidence_source: "STORE_OBSERVED",
    confidence_label: "Emerging",
    audience: { id: null, definition: null, size: 234, fraction_of_base: null },
    measurement: { metric: "reactivation_rate", observed_effect: -0.205607, n: 107, primary_window: "L56" },
    revenue_range: { p10: 422.54, p50: 4480.73, p90: 4480.73, source: "blend", suppressed: false, suppression_reason: null },
    ...overrides,
  };
}

function run(overrides = {}) {
  return {
    run_id: "run-1",
    store_id: "store-1",
    abstain: { state: "publish", mode: null },
    data_quality_flags: [],
    recommendations: [
      card(),
      card({ play_id: "discount_dependency_hygiene" }),
      card({ play_id: "cohort_journey_first_to_second" }),
    ],
    considered: [
      { play_id: "aov_lift_via_threshold_bundle", reason_code: "signal_inconsistent_across_windows", audience_size: 40 },
      { play_id: "winback_21_45", reason_code: "no_measured_signal", audience_size: 80 },
      { play_id: "subscription_nudge", reason_code: "data_quality_flag", audience_size: 12 },
    ],
    watching: [
      { metric: "net_sales", current: null, prior: null, trend: "down", threshold_to_act: "+/- 10% to revisit revenue plays" },
    ],
    ...overrides,
  };
}

test("every evidence source in the contract maps to its own label", () => {
  // The engine's EvidenceSourceChip enum, verbatim.
  const contract = ["STORE_MEASURED", "STORE_OBSERVED", "INDUSTRY_PRIOR", "OBSERVATIONAL"];
  assert.deepEqual(Object.keys(EVIDENCE_SOURCE_DISPLAY).sort(), [...contract].sort());

  const labels = contract.map((source) => {
    const presented = presentEngineRun(run({ recommendations: [card({ evidence_source: source })] }));
    return presented.recommendations[0].evidence_facts.evidence_source_label;
  });
  assert.equal(new Set(labels).size, contract.length, "no two sources share a label");
});

test("store-observed evidence is labelled as the store's own data, not other stores'", () => {
  // The reported defect: all three inspected recommendations were STORE_OBSERVED
  // and the app said "Modeled from similar stores".
  const presented = presentEngineRun(run());
  for (const rec of presented.recommendations) {
    assert.equal(rec.evidence_line, "Observed in your store");
    assert.doesNotMatch(JSON.stringify(rec.evidence_facts), /similar stores/i);
  }
});

test("a missing or unknown source says so instead of guessing", () => {
  for (const source of [null, "SOMETHING_NEW"]) {
    const presented = presentEngineRun(run({ recommendations: [card({ evidence_source: source })] }));
    assert.equal(presented.recommendations[0].evidence_line, "Evidence source not recorded");
  }
});

test("the observed change is the metric, its window and what it is compared with", () => {
  const facts = presentEngineRun(run()).recommendations[0].evidence_facts;
  // The engine's two-proportion effect is recent_rate − prior_rate, so
  // -0.205607 is a fall of 20.6 percentage points — not 20.6%.
  assert.deepEqual(facts.observed_change, {
    metric: "reactivation_rate",
    metric_label: "Reactivation rate",
    unit: "percentage_points",
    value: -20.6,
    currency: null,
    direction: "down",
    note: null,
    window: { id: "L56", days: 56, label: "last 56 days", comparison: "compared with the 56 days before" },
  });
});

function changeFor(metric, observed_effect, options) {
  return presentEngineRun(
    run({ recommendations: [card({ measurement: { metric, observed_effect, n: 10, primary_window: "L28" } })] }),
    null, null, options,
  ).recommendations[0].evidence_facts.observed_change;
}

test("each builder's change is reported in the unit that builder produces", () => {
  // Two-proportion builders: percentage points.
  for (const metric of ["reactivation_rate", "replenishment_conversion_rate", "first_to_second_conversion_rate"]) {
    assert.equal(changeFor(metric, 0.05).unit, "percentage_points", metric);
  }

  // The directional builder's aligned delta is a relative change.
  const relative = changeFor("returning_customer_share", 0.062);
  assert.equal(relative.unit, "percent");
  assert.equal(relative.value, 6.2);

  // An effect whose unit isn't established is not shown in a guessed one.
  assert.equal(changeFor("conversion", 0.76), null);
  assert.equal(changeFor("some_new_metric", 0.1), null);
});

test("the discount change is labelled as the heavy-discount revenue share it is", () => {
  // The builder's rate is heavy-discount-cohort revenue over all revenue. It was
  // labelled "Full-price purchase rate" — so a rise in discount dependency read
  // as more full-price buying.
  const change = changeFor("discount_dependency_hygiene_full_price_conversion_rate", 0.053333);
  assert.equal(change.metric_label, "Share of revenue from heavy-discount customers");
  assert.equal(change.unit, "percentage_points");
  assert.equal(change.value, 5.3);
  assert.equal(change.direction, "up");
  assert.match(change.note, /more of your revenue is coming from customers who mostly buy on discount/);
  assert.doesNotMatch(JSON.stringify(change), /full-price/i);
});

test("the AOV-bundle change is an average order value difference in the store's currency", () => {
  // The value on the card is the Welch difference in mean order value. It was
  // labelled "Spend-threshold crossing rate" and would have rendered as a percent.
  const change = changeFor("aov_threshold_crossing_conversion_rate", -3.204, { currency: "CAD" });
  assert.equal(change.metric_label, "Average order value");
  assert.equal(change.unit, "currency");
  assert.equal(change.value, -3.2);
  assert.equal(change.currency, "CAD");
  assert.doesNotMatch(change.metric_label, /threshold|crossing|rate/i);
});

test("a sample figure appears only where its unit is established", () => {
  // Reactivation's n is the lapsed cohort the engine tracked.
  assert.deepEqual(
    presentEngineRun(run()).recommendations[0].evidence_facts.sample,
    { size: 107, unit: "lapsed customers tracked" },
  );

  // The reported figure. For the discount metric the engine's n is net sales in
  // dollars; the app showed it as "60,528 orders analyzed" for a 670-order store.
  const discount = presentEngineRun(run({
    recommendations: [card({
      play_id: "discount_dependency_hygiene",
      measurement: { metric: "discount_dependency_hygiene_full_price_conversion_rate", observed_effect: 0.053333, n: 60528, primary_window: "L56" },
    })],
  })).recommendations[0].evidence_facts;
  assert.equal(discount.sample, null, "a dollar total is not a sample size");
  assert.equal(discount.observed_change.metric_label, "Share of revenue from heavy-discount customers");

  const known = presentEngineRun(run({
    recommendations: [card({ measurement: { metric: "returning_customer_share", observed_effect: 0.06, n: 412, primary_window: "L28" } })],
  })).recommendations[0].evidence_facts.sample;
  assert.deepEqual(known, { size: 412, unit: "customers who ordered in the period" });

  // No observed change: the builder put the audience size in `n`. It is shown
  // once, as the audience — not a second time as evidence.
  const coldStart = presentEngineRun(run({
    recommendations: [card({ measurement: { metric: "returning_customer_share", observed_effect: null, n: 234, primary_window: "L28" } })],
  })).recommendations[0].evidence_facts;
  assert.equal(coldStart.sample, null);
  assert.equal(coldStart.observed_change, null);
});

test("no dollar figure without a non-suppressed BLEND range, and never as lift", () => {
  const blend = presentEngineRun(run(), null, null, { currency: "CAD" }).recommendations[0].revenue_range;
  assert.equal(blend.suppressed, false);
  assert.equal(blend.meaning, "baseline");
  assert.equal(blend.currency, "CAD", "the store's currency, not an assumed USD");
  assert.equal(blend.low, 400);
  assert.equal(blend.high, 4500);

  const cases = [
    { p10: 100, p50: 200, p90: 300, source: "vertical_prior", suppressed: false },
    { p10: 100, p50: 200, p90: 300, source: "store_observed", suppressed: false },
    { p10: null, p50: null, p90: null, source: null, suppressed: true, suppression_reason: "cold_start" },
  ];
  for (const revenue_range of cases) {
    const range = presentEngineRun(run({ recommendations: [card({ revenue_range })] })).recommendations[0].revenue_range;
    assert.equal(range.low, null, `${revenue_range.source} must not produce an amount`);
    assert.equal(range.high, null);
    assert.equal(range.suppressed, true);
  }
});

test("every reason code in the contract has its own translation", () => {
  // engine_run.py ReasonCode, verbatim.
  const contract = [
    "audience_too_small", "audience_overlap_with_higher_priority", "inventory_blocked",
    "no_measured_signal", "signal_inconsistent_across_windows", "anomalous_window",
    "cold_start_insufficient_data", "cannibalization_demoted", "recently_run_fatigue",
    "materiality_below_floor", "data_quality_flag", "cap_exceeded",
    "targeting_held_under_abstain", "supplement_cadence_outside_window", "prior_unvalidated",
    "window_disagreement", "model_fit_insufficient_data", "model_fit_refused",
  ];
  assert.deepEqual(Object.keys(REASON_DISPLAY).sort(), [...contract].sort());
});

test("held plays are not all told they need more orders", () => {
  const considered = presentEngineRun(run()).considered;
  const byId = Object.fromEntries(considered.map((c) => [c.play_id, c]));

  assert.equal(byId.aov_lift_via_threshold_bundle.reason.category, "signal");
  assert.equal(byId.winback_21_45.reason.category, "signal");
  assert.equal(byId.subscription_nudge.reason.category, "data_quality");
  // The real run held six plays for three different reasons, and the old table
  // gave all six the same "needs more store data" sentence.
  assert.equal(new Set(considered.map((c) => c.reason_display)).size, 3);
  for (const c of considered) {
    assert.doesNotMatch(c.reason_display, /more orders|more store data/i, c.play_id);
  }

  // Only a genuine data-volume hold says more orders will help.
  const young = presentEngineRun(run({ considered: [{ play_id: "x", reason_code: "cold_start_insufficient_data" }] })).considered[0];
  assert.equal(young.reason.category, "data_volume");
  assert.match(young.reason_display, /more orders sync/);
});

test("the engine's structured hold detail is used when present", () => {
  const held = presentEngineRun(run({
    considered: [{ play_id: "x", reason_code: "audience_too_small", held_reason_detail: { observed: 312, floor: 500 } }],
  })).considered[0];
  assert.equal(held.reason.text, "Only 312 customers match; this play needs at least 500.");
});

test("an unknown reason code is reported as unknown, not as insufficient data", () => {
  const held = presentEngineRun(run({ considered: [{ play_id: "x", reason_code: "brand_new_code" }] })).considered[0];
  assert.equal(held.reason.category, "unknown");
  assert.doesNotMatch(held.reason_display, /data/i);
});

test("rank is the engine's order, independent of anything the merchant selects", () => {
  const presented = presentEngineRun(run());
  assert.deepEqual(presented.recommendations.map((r) => r.rank), [1, 2, 3]);
});

test("a run that recommends nothing explains why, per abstain mode", () => {
  const soft = presentEngineRun(run({
    abstain: { state: "abstain_soft", mode: "soft_audience_too_small" },
    recommendations: [],
  })).decision;
  assert.equal(soft.state, "abstain_soft");
  assert.match(soft.detail, /audiences .* too small/);

  const hard = presentEngineRun(run({
    abstain: { state: "abstain_hard", mode: null },
    data_quality_flags: ["refund_storm"],
    recommendations: [],
    considered: [],
  }));
  assert.equal(hard.decision.state, "abstain_hard");
  assert.deepEqual(hard.data_quality_flags, [{ code: "refund_storm", label: "Refunds were unusually high in the analysis period." }]);

  assert.equal(presentEngineRun(run()).decision.state, "publish");
});

test("watching signals and a truncated held list reach the screen", () => {
  const presented = presentEngineRun(run({ considered_truncated_count: 4 }));
  assert.equal(presented.considered_truncated_count, 4);
  assert.deepEqual(presented.watching, [
    { metric: "net_sales", metric_label: "Net sales", trend: "down", threshold_to_act: "+/- 10% to revisit revenue plays" },
  ]);
});

test("the analysis time comes from the stored run, never the sync", () => {
  const presented = presentEngineRun(run(), null, null, { analysedAt: "2026-09-08T22:44:59.654Z" });
  assert.equal(presented.generated_at, "2026-09-08T22:44:59.654Z");
});
