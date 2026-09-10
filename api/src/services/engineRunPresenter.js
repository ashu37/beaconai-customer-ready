// C4b: belt-and-braces tautology guard. The narration service's templated
// fallback sentence ("This play targets the <play_id> opportunity...") can slip
// through even without used_fallback set; reject any guarded narration carrying it.
const TAUTOLOGY_THESIS = /^This play targets the .* opportunity/i;

function isTautologyNarration(narration) {
  return Boolean(narration && TAUTOLOGY_THESIS.test(String(narration.play_thesis || "")));
}

function titleizeId(value) {
  return String(value || "recommendation")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const PLAY_DISPLAY = {
  winback_dormant_cohort: {
    display_name: "Bring back lapsed customers",
    one_liner: "Customers who bought before but have gone quiet",
    subject: "We saved something for you",
    cta: "Come back and save",
    customer_body: "It's been a while — here's what's new since your last order.",
  },
  winback_21_45: {
    display_name: "Win back recent lapses (21–45 days)",
    one_liner: "Buyers who lapsed in the last 21–45 days — still warm",
    subject: "It's been a minute — come see what's new",
    cta: "Come back and save",
    customer_body: "It's been a few weeks — we've kept your favorites in stock and added a few new picks.",
  },
  cohort_journey_first_to_second: {
    display_name: "Turn first-time buyers into repeat buyers",
    one_liner: "One-time buyers who haven't come back yet",
    subject: "Your next favorite is waiting",
    cta: "Shop the picks",
    customer_body: "Thanks for your first order — here are a few things we think you'll love next.",
  },
  aov_lift_via_threshold_bundle: {
    display_name: "Raise order size with a bundle offer",
    one_liner: "Shoppers near a spend threshold worth nudging up",
    subject: "So close to something extra",
    cta: "Build your bundle",
    customer_body: "You're close to unlocking more — pair a few favorites and get more for your order.",
  },
  discount_dependency_hygiene: {
    display_name: "Reduce discount dependency",
    one_liner: "Customers who only buy on discount — rebuild full-price habits",
    subject: "Worth full price — here's why",
    cta: "Shop the picks",
    customer_body: "Here's what makes these worth it — quality that lasts, at everyday value.",
  },
  discount_hygiene: {
    display_name: "Protect your margins on promos",
    one_liner: "Tighten who gets discounts and how deep",
    subject: "A little something, just for you",
    cta: "Shop the picks",
    customer_body: "A small thank-you, just for you — enjoy something you've had your eye on.",
  },
  bestseller_amplify: {
    display_name: "Amplify your bestsellers",
    one_liner: "Put proven products in front of the right buyers",
    subject: "The ones everyone keeps reordering",
    cta: "Shop the picks",
    customer_body: "These are the picks customers keep coming back for — see what all the fuss is about.",
  },
  replenishment_due: {
    display_name: "Remind customers to reorder",
    one_liner: "Customers likely running low, based on reorder timing",
    subject: "Running low? Right on time",
    cta: "Reorder now",
    customer_body: "You might be running low — reorder in a couple of taps and never miss a beat.",
  },
  at_risk_repeat_buyer_rescue: {
    display_name: "Rescue at-risk repeat buyers",
    one_liner: "Loyal customers showing early signs of drifting away",
    subject: "We miss you already",
    cta: "Come back and save",
    customer_body: "We've missed you — here's a little something to welcome you back.",
  },
  subscription_nudge: {
    display_name: "Nudge repeat buyers toward subscription",
    one_liner: "Frequent buyers ready for a subscribe-and-save offer",
    subject: "Never run out again",
    cta: "Subscribe & save",
    customer_body: "Since you reorder regularly, subscribe and save — delivered right on schedule.",
  },
  frequency_accelerator: {
    display_name: "Increase purchase frequency",
    one_liner: "Good customers who could buy more often",
    subject: "Your routine, upgraded",
    cta: "Shop the picks",
    customer_body: "Ready to level up your routine? Here are a few picks to add to the mix.",
  },
  routine_builder: {
    display_name: "Build routines with cross-category offers",
    one_liner: "Buyers of one category likely to add a second",
    subject: "Complete the routine",
    cta: "Shop the picks",
    customer_body: "Round out your routine — these pair perfectly with what you already love.",
  },
  onsite_funnel_watch: {
    display_name: "Watch your onsite funnel",
    one_liner: "Conversion signal to monitor — not a send",
    subject: null,
    cta: "Shop the picks",
    customer_body: null,
  },
  empty_bottle: {
    display_name: "Time reorders to the empty bottle",
    one_liner: "Reorder reminders timed to product usage",
    subject: "Time for a refill?",
    cta: "Reorder now",
    customer_body: "You're probably about due for a refill — reorder now and stay stocked.",
  },
};

function playDisplay(playId) {
  return PLAY_DISPLAY[playId] || null;
}

function playDisplayName(playId) {
  return playDisplay(playId)?.display_name || titleizeId(playId);
}

function playOneLiner(playId) {
  return playDisplay(playId)?.one_liner || null;
}

// Ticket E: every reason code the engine contract defines (engine_run.py
// ReasonCode), each translated for what it actually means. The previous table
// was keyed on codes the engine never emits — `insufficient_sample`,
// `low_confidence` — so every real hold except `audience_too_small` fell through
// to "needs more store data", including holds that more orders will never fix.
//
// `category` lets the screen tell a store that is simply young (more data
// fixes it) from one where the held plays are blocked for other reasons.
const REASON_DISPLAY = {
  audience_too_small: {
    category: "audience",
    text: "Too few customers match this play right now.",
    next: "It becomes available as more customers qualify.",
  },
  audience_overlap_with_higher_priority: {
    category: "overlap",
    text: "These customers are already in a higher-ranked recommendation.",
    next: "Sending both would email the same people twice.",
  },
  inventory_blocked: {
    category: "inventory",
    text: "The products this play would feature are low or out of stock.",
    next: "It becomes available when stock recovers.",
  },
  no_measured_signal: {
    category: "signal",
    text: "Your store data doesn't show a signal for this play.",
    next: "It's re-checked each time the store is analysed.",
  },
  signal_inconsistent_across_windows: {
    category: "signal",
    text: "The signal points in different directions depending on the time period looked at, so it isn't reliable yet.",
    next: "It's re-checked each time the store is analysed.",
  },
  window_disagreement: {
    category: "signal",
    text: "Recent and longer-term data disagree about this signal.",
    next: "It's re-checked each time the store is analysed.",
  },
  anomalous_window: {
    category: "data_quality",
    text: "The analysis period includes unusual activity, so the signal can't be trusted yet.",
    next: "It's re-checked once the period is behind you.",
  },
  cold_start_insufficient_data: {
    category: "data_volume",
    text: "There isn't enough order history yet to assess this play.",
    next: "It becomes available as more orders sync.",
  },
  cannibalization_demoted: {
    category: "overlap",
    text: "This play would compete with a higher-ranked recommendation for the same sales.",
    next: null,
  },
  recently_run_fatigue: {
    category: "timing",
    text: "A similar campaign reached these customers recently.",
    next: "It becomes available again after a cooldown.",
  },
  materiality_below_floor: {
    category: "impact",
    text: "The potential impact is too small to be worth a campaign right now.",
    next: null,
  },
  data_quality_flag: {
    category: "data_quality",
    text: "A data-quality issue in the analysis period is holding this back.",
    next: null,
  },
  cap_exceeded: {
    category: "slate",
    text: "Other plays ranked higher, and BeaconAI recommends at most three at a time.",
    next: null,
  },
  targeting_held_under_abstain: {
    category: "slate",
    text: "No campaign is recommended from this analysis, so this audience is held as well.",
    next: null,
  },
  supplement_cadence_outside_window: {
    category: "signal",
    text: "Your customers reorder on a longer cycle than this analysis can see.",
    next: null,
  },
  prior_unvalidated: {
    category: "benchmark",
    text: "The benchmark this play relies on hasn't been validated for your kind of store.",
    next: null,
  },
  // Contractually never emitted on a held play (ML fit never demotes), but a
  // code the contract defines is still mapped rather than left to a fallback.
  model_fit_insufficient_data: {
    category: "data_volume",
    text: "There isn't enough history to fit the customer model for this play.",
    next: "It becomes available as more orders sync.",
  },
  model_fit_refused: {
    category: "signal",
    text: "The customer model for this play didn't fit your data reliably.",
    next: null,
  },
};

// An unrecognised code is reported as unrecognised. Guessing "more data" is how
// this screen used to tell merchants their store was too small when it wasn't.
const REASON_UNKNOWN = {
  category: "unknown",
  text: "The analysis held this play for a reason this screen doesn't recognise.",
  next: null,
};

function heldReason(reasonCode, card) {
  const key = reasonCode ? String(reasonCode).toLowerCase() : null;
  const entry = (key && REASON_DISPLAY[key]) || REASON_UNKNOWN;
  let text = entry.text;
  // The engine's structured detail, when it supplies one. Only the observed
  // count and its floor are used; anything else in the dict stays internal.
  const detail = card?.held_reason_detail;
  const observed = Number(detail?.observed);
  const floor = Number(detail?.floor);
  if (key === "audience_too_small" && Number.isFinite(observed) && Number.isFinite(floor) && floor > 0) {
    text = `Only ${observed.toLocaleString()} customers match; this play needs at least ${floor.toLocaleString()}.`;
  }
  return { code: key, category: entry.category, text, next: entry.next };
}

function reasonDisplay(reasonCode, card) {
  const reason = heldReason(reasonCode, card);
  return reason.next ? `${reason.text} ${reason.next}` : reason.text;
}

// Every evidence_source value the contract defines (EvidenceSourceChip), mapped
// explicitly. The old mapping sent everything that wasn't STORE_MEASURED to
// "Modeled from similar stores" — so every STORE_OBSERVED recommendation, which
// is built from this store's own data, was labelled as coming from other stores.
const EVIDENCE_SOURCE_DISPLAY = {
  STORE_MEASURED: {
    label: "Measured in your store",
    detail: "Estimated from a controlled comparison in your store's own data.",
  },
  STORE_OBSERVED: {
    label: "Observed in your store",
    detail: "A metric in your store's data moved in a way that suggests this campaign. That change is not a measurement of what the campaign itself will do.",
  },
  INDUSTRY_PRIOR: {
    label: "Based on industry benchmarks",
    detail: "The audience comes from your store. How it's expected to respond comes from published benchmarks, not your store's history.",
  },
  OBSERVATIONAL: {
    label: "Audience identified",
    detail: "BeaconAI found this audience in your data. It makes no claim about how the audience will respond.",
  },
};

const EVIDENCE_SOURCE_MISSING = {
  label: "Evidence source not recorded",
  detail: "This analysis didn't record where its evidence came from.",
};

function evidenceSourceDisplay(source) {
  if (!source) return EVIDENCE_SOURCE_MISSING;
  return EVIDENCE_SOURCE_DISPLAY[String(source).toUpperCase()] || EVIDENCE_SOURCE_MISSING;
}

// Engine metric identifiers, in words. Unknown ones are titleized rather than
// dropped, so a new metric still reads as a metric.
const MEASUREMENT_METRIC_LABELS = {
  reactivation_rate: "Reactivation rate",
  first_to_second_conversion_rate: "Second-purchase rate",
  replenishment_conversion_rate: "Reorder rate",
  returning_customer_share: "Returning-customer share",
  repeat_rate_within_window: "Repeat purchase rate",
  conversion: "Conversion rate",
  aov: "Average order value",
  orders: "Orders",
  net_sales: "Net sales",
};

function metricLabel(metric) {
  if (!metric) return null;
  return MEASUREMENT_METRIC_LABELS[metric] || titleizeId(metric);
}

// "L56" → the last 56 days. The engine compares a recent window with the
// window of the same length immediately before it.
function windowDisplay(windowId) {
  const match = /^L(\d+)$/i.exec(String(windowId || ""));
  if (!match) return null;
  const days = Number(match[1]);
  return {
    id: String(windowId).toUpperCase(),
    days,
    label: `last ${days} days`,
    comparison: `compared with the ${days} days before`,
  };
}

// What one unit of `measurement.n` is, per metric — only where the engine code
// establishes it (engine/src/measurement_builder.py, measurement_observed.py).
// The contract gives `n` no unit and the builders disagree, so a metric not
// listed shows no sample figure rather than a guessed one. "Orders analyzed",
// the old label, was wrong for every one of them. Notably:
//   - discount_dependency_hygiene_full_price_conversion_rate: `n` is NET SALES
//     in the window, in currency (_revenue_in_window). A store with 670 orders
//     showed "60,528 orders analyzed".
//   - aov_threshold_crossing_conversion_rate: two tests feed it; which `n`
//     lands on the card is not stated. Omitted until it is.
const SAMPLE_UNITS = {
  // compute_winback_observed_effect: the dormant cohort at the window's anchor.
  reactivation_rate: "lapsed customers tracked",
  // compute_replenishment_observed_effect: customers due to reorder at the anchor.
  replenishment_conversion_rate: "customers due to reorder",
  // compute_journey_first_to_second_observed_effect: first-time buyers in the cell.
  first_to_second_conversion_rate: "first-time buyers tracked",
  // Directional builder: unique identified customers ordering in the window.
  returning_customer_share: "customers who ordered in the period",
  repeat_rate_within_window: "customers who ordered in the period",
};

// What `observed_effect` IS, per metric. The builders do not share a unit, so
// none is applied universally (engine/src/measurement_observed.py and the
// builders in measurement_builder.py):
//   - two-proportion builders emit recent_rate − prior_rate: a difference in
//     PERCENTAGE POINTS, not a percent change. -0.2056 is "down 20.6 points".
//   - the discount builder's rate is k/n with k = revenue from the heavy-discount
//     cohort and n = all revenue: the SHARE OF REVENUE from heavy-discount
//     customers. A rise means more dependency, not more full-price buying.
//   - the AOV-bundle builder puts its Welch result on the card: the difference
//     in mean order value, in CURRENCY. The metric name says threshold crossing;
//     the number is not that.
//   - the directional builder emits aligned[w].delta: a RELATIVE change.
// A metric not listed shows no change at all rather than one in a guessed unit.
const OBSERVED_CHANGE = {
  reactivation_rate: { label: "Reactivation rate", unit: "percentage_points" },
  replenishment_conversion_rate: { label: "Reorder rate", unit: "percentage_points" },
  first_to_second_conversion_rate: { label: "Second-purchase rate", unit: "percentage_points" },
  discount_dependency_hygiene_full_price_conversion_rate: {
    label: "Share of revenue from heavy-discount customers",
    unit: "percentage_points",
    note: "A rise means more of your revenue is coming from customers who mostly buy on discount.",
  },
  aov_threshold_crossing_conversion_rate: { label: "Average order value", unit: "currency" },
  returning_customer_share: { label: "Returning-customer share", unit: "percent" },
  repeat_rate_within_window: { label: "Repeat purchase rate", unit: "percent" },
};

function observedChange(measurement, currency = null) {
  if (measurement?.observed_effect == null) return null;
  const effect = Number(measurement.observed_effect);
  const spec = OBSERVED_CHANGE[measurement.metric];
  if (!spec || !Number.isFinite(effect)) return null;
  const value = spec.unit === "currency"
    ? Math.round(effect * 100) / 100
    // Points and percent are both stored as fractions (0.206 → 20.6).
    : Math.round(effect * 1000) / 10;
  return {
    metric: measurement.metric,
    metric_label: spec.label,
    unit: spec.unit,
    value,
    currency: spec.unit === "currency" ? currency : null,
    direction: value > 0 ? "up" : value < 0 ? "down" : "flat",
    note: spec.note || null,
    window: windowDisplay(measurement.primary_window),
  };
}

function sampleFor(measurement) {
  // No observed effect means the builder filled `n` with the audience size,
  // which is already shown as the audience. Repeating it as a "sample" would
  // present one number as two pieces of evidence.
  if (measurement?.observed_effect == null) return null;
  const n = Number(measurement?.n);
  const unit = SAMPLE_UNITS[measurement?.metric];
  if (!unit || !Number.isFinite(n) || n <= 0) return null;
  return { size: n, unit };
}

function compactSentence(value, fallback) {
  const text = String(value || "").trim();
  return text || fallback;
}

function audienceText(audience) {
  if (!audience) return "Recommended audience";
  return compactSentence(audience.definition, "Recommended audience");
}

function roundMoney(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  if (Math.abs(num) < 100) return Math.round(num / 10) * 10;
  return Math.round(num / 100) * 100;
}

// DS lock 8: the only dollar figure a merchant sees is a non-suppressed
// revenue_range whose source is BLEND. Anything else — a suppressed range, a
// prior-only range — carries no amount, and says why.
//
// DS lock 2: for any card that is not STORE_MEASURED (today, every card) the
// range is "a prior-anchored posterior on a baseline rate, not predicted lift":
// what this audience would spend at the expected purchase rate. It is labelled
// as that, never as upside, lift or revenue from sending.
function isDisplayableRange(range) {
  if (!range || range.suppressed) return false;
  if (String(range.source || "").toLowerCase() !== "blend") return false;
  return [range.p10 ?? range.low, range.p90 ?? range.high].every((v) => v != null && Number.isFinite(Number(v)));
}

function normalizeRevenueRange(range, currency = null) {
  if (!isDisplayableRange(range)) {
    return {
      low: null,
      mid: null,
      high: null,
      median: null,
      currency,
      source: range?.source || null,
      suppressed: true,
      suppression_reason: range?.suppression_reason || (range && !range.suppressed ? "not_blend" : null),
    };
  }

  const low = roundMoney(range.p10 ?? range.low ?? null);
  const mid = roundMoney(range.p50 ?? range.mid ?? range.median ?? null);
  const high = roundMoney(range.p90 ?? range.high ?? null);

  return {
    low,
    mid,
    median: mid,
    high,
    currency,
    source: range.source || null,
    suppressed: false,
    suppression_reason: null,
    // Rendered beside the number wherever it appears.
    meaning: "baseline",
  };
}

// The card face: where the evidence comes from, in words.
function evidenceLineForCard(card) {
  return evidenceSourceDisplay(card.evidence_source).label;
}

// The formal chip payload per card. DATA-DERIVED VALUES the frontend renders —
// never hand-written marketing prose. The frontend reads ONLY from here, never
// from `raw`.
function evidenceFactsForCard(card, currency) {
  const range = normalizeRevenueRange(card.revenue_range, currency);
  const source = evidenceSourceDisplay(card.evidence_source);
  return {
    audience_size: card.audience?.size ?? null,
    audience_fraction_of_base: card.audience?.fraction_of_base ?? null,
    evidence_source: card.evidence_source || null,
    evidence_source_label: source.label,
    evidence_source_detail: source.detail,
    observed_change: observedChange(card.measurement, currency),
    sample: sampleFor(card.measurement),
    confidence_label: card.confidence_label || null,
    revenue_range: range,
  };
}

function audienceArtifactFor(card, manifest) {
  const audiences = manifest?.artifacts?.audiences || [];
  const audienceId = card.audience?.id;
  return audiences.find((entry) => entry.play_id === card.play_id || entry.audience_definition_id === audienceId) || null;
}

function narrationByPlay(narration) {
  const cards = narration?.cards || [];
  const map = new Map();
  for (const card of cards) {
    map.set(`${card.role}:${card.play_id}`, card);
    map.set(card.play_id, card);
  }
  return map;
}

function narrationFor(map, id, role) {
  return map.get(`${role}:${id}`) || map.get(id) || null;
}

// P1-5: merchant-voiced, customer-safe template prompt.
// Never leaks revenue, evidence sizing, or internal vocabulary.
function buildTemplatePrompt(card, id) {
  const display = playDisplay(id);
  // onsite_funnel_watch (and any monitor-only play) has no template.
  if (display && display.subject === null) return null;

  const displayName = playDisplayName(id);
  const oneLiner = playOneLiner(id) || audienceText(card.audience);
  const customerBody = display?.customer_body || `${displayName}.`;
  const subject = display?.subject || displayName;
  const cta = display?.cta || "Shop the picks";

  return {
    subject,
    previewText: customerBody,
    headline: displayName,
    body: customerBody,
    support: customerBody,
    cta,
  };
}

function normalizeCard(card, role, index, manifest, narrationMap, currency) {
  const id = card.play_id || `${role}-${index + 1}`;
  const revenueRange = normalizeRevenueRange(card.revenue_range, currency);
  const rawGuardedNarration = narrationFor(narrationMap, id, role);
  // If the narration service itself fell back, its text is the templated
  // "This play targets the <play_id> opportunity..." sentence — prefer our
  // merchant-language narration instead of surfacing that tautology.
  // Phase 1: prose is the LLM's or NOTHING. When narration didn't clear the
  // guards (or ran on mock → used_fallback), `narration` is null and the
  // frontend renders the evidence chip grid instead of a canned sentence.
  // No templated fallback is authored here anymore (Pivot 2).
  const guardedNarration = rawGuardedNarration
    && !rawGuardedNarration.used_fallback
    && !isTautologyNarration(rawGuardedNarration)
    ? rawGuardedNarration
    : null;
  const narration = guardedNarration ? {
    role,
    play_thesis: guardedNarration.play_thesis,
    what_we_d_send: guardedNarration.what_we_d_send,
    evidence_summary: guardedNarration.evidence_summary,
    guard_violations: guardedNarration.guard_violations || [],
    used_fallback: false,
    llm_mode: "atul-narration",
  } : null;
  const audienceArtifact = audienceArtifactFor(card, manifest);

  return {
    id,
    play_id: id,
    play_name: playDisplayName(id),
    play_one_liner: playOneLiner(id),
    role,
    lane: role === "recommended_experiment" ? "experiment" : "recommendation",
    source: "atul-engine",
    // Prose only when the LLM authored it; null otherwise (frontend → chips).
    mechanism: narration ? narration.play_thesis : null,
    audience_archetype: audienceText(card.audience),
    audience_size: card.audience?.size ?? 0,
    confidence: card.confidence_label || "Review",
    evidence_line: evidenceLineForCard(card),
    evidence_source: card.evidence_source || null,
    // The engine's order within this lane. Stable across selection: the row a
    // merchant clicks is "selected", never promoted to "primary".
    rank: index + 1,
    evidence_facts: evidenceFactsForCard(card, currency),
    measurement: card.measurement || null,
    revenue_range: revenueRange,
    mechanism_intent: card.mechanism_intent || null,
    predicted_segment: card.predicted_segment || null,
    would_be_measured_by: card.would_be_measured_by || null,
    audience_artifact: audienceArtifact,
    narration,
    template_prompt: buildTemplatePrompt(card, id),
    raw: card,
  };
}

function normalizeRejectedCard(card, index, narrationMap) {
  const id = card.play_id || `considered-${index + 1}`;
  const rawGuardedNarration = narrationFor(narrationMap, id, "considered");
  // C4b: reject the templated tautology sentence here too.
  const guardedNarration = isTautologyNarration(rawGuardedNarration) ? null : rawGuardedNarration;
  return {
    id,
    play_id: id,
    play_name: playDisplayName(id),
    play_one_liner: playOneLiner(id),
    role: "considered",
    reason_code: card.reason_code || null,
    // DATA-DERIVED from the engine's typed reason_code (and its structured
    // detail) — what is holding the play and, where true, what would release it.
    reason: heldReason(card.reason_code, card),
    reason_display: reasonDisplay(card.reason_code, card),
    audience_size: card.audience_size ?? 0,
    audience_archetype: card.audience_definition || "Held for more evidence",
    // Prose only when the LLM authored it; null otherwise. The held-reason is
    // surfaced via `reason_display`, so no templated sentence is needed here.
    mechanism: guardedNarration?.play_thesis || null,
    narration: guardedNarration ? {
      role: "considered",
      play_thesis: guardedNarration.play_thesis,
      what_we_d_send: guardedNarration.what_we_d_send,
      evidence_summary: guardedNarration.evidence_summary,
      guard_violations: guardedNarration.guard_violations || [],
      used_fallback: Boolean(guardedNarration.used_fallback),
      llm_mode: "atul-narration",
    } : null,
    raw: card,
  };
}

// B1: engineRun.state_of_store is a LIST of typed observations, not a string.
// The header SENTENCE is authored by the narration MCP (guarded), not here —
// the former stateOfStoreSentence() templated prose was retired (Pivot 2). These
// labels remain for the DATA chip row below (a chip value, not a sentence).
const METRIC_LABELS = {
  aov: "average order value",
  repeat_rate_within_window: "repeat purchase rate",
  orders: "orders",
  returning_customer_share: "returning-customer share",
  net_sales: "net sales",
};

// D6a: structured delta observations for the briefing chip row. Top 2 movers by
// magnitude, plus AOV always if present. `flat` when the rounded pct is 0 or the
// metric is held (not "moved").
function stateOfStoreObservations(engineRun) {
  const observations = engineRun?.state_of_store;
  if (!Array.isArray(observations)) return [];

  const known = observations.filter((obs) =>
    obs && Object.prototype.hasOwnProperty.call(METRIC_LABELS, obs.supporting_metric));

  const toChip = (obs) => {
    const moved = obs.classification === "moved" && Number.isFinite(obs.delta_pct);
    const pct = moved ? Math.round(Math.abs(obs.delta_pct) * 100) : 0;
    const direction = !moved || pct === 0 ? "flat" : obs.delta_pct >= 0 ? "up" : "down";
    return { label: METRIC_LABELS[obs.supporting_metric], direction, pct, metric: obs.supporting_metric };
  };

  const movers = known
    .filter((obs) => obs.classification === "moved" && Number.isFinite(obs.delta_pct) && Math.round(Math.abs(obs.delta_pct) * 100) !== 0)
    .sort((a, b) => Math.abs(b.delta_pct) - Math.abs(a.delta_pct))
    .slice(0, 2)
    .map(toChip);

  const chips = [...movers];
  // AOV always included if present and not already shown.
  const aov = known.find((obs) => obs.supporting_metric === "aov");
  if (aov && !chips.some((c) => c.metric === "aov")) chips.push(toChip(aov));

  return chips.map(({ metric, ...chip }) => chip);
}

// A run that recommends nothing is a result, not an empty screen. The engine
// says why in a typed state and mode; each is given its own sentence rather than
// collapsing into "needs more data".
const ABSTAIN_DISPLAY = {
  soft_awaiting_measurement: "Your store data doesn't yet show a strong enough signal for any play.",
  soft_prior_unvalidated: "The benchmarks these plays rely on haven't been validated for your kind of store.",
  soft_below_floor: "Each play's potential impact is too small to be worth a campaign right now.",
  soft_audience_too_small: "The audiences these plays would target are too small right now.",
};

const DATA_QUALITY_LABELS = {
  bfcm_overlap: "The analysis period overlaps Black Friday / Cyber Monday.",
  post_promo_window: "The analysis period follows a promotion.",
  refund_storm: "Refunds were unusually high in the analysis period.",
  test_order_anomaly: "Test orders were detected in the store data.",
  insufficient_clean_history: "There isn't enough clean order history to analyse.",
  vertical_not_supported: "This store's category isn't supported by the analysis yet.",
  metric_incoherent_for_cadence: "Customers reorder on a longer cycle than the analysis window, so repeat-rate figures are unreliable.",
};

function dataQualityFlags(engineRun) {
  return (engineRun?.data_quality_flags || []).map((flag) => ({
    code: String(flag),
    label: DATA_QUALITY_LABELS[String(flag).toLowerCase()] || `Data-quality flag: ${titleizeId(flag)}.`,
  }));
}

function decisionFor(engineRun) {
  const state = String(engineRun?.abstain?.state || "publish").toLowerCase();
  const mode = engineRun?.abstain?.mode ? String(engineRun.abstain.mode).toLowerCase() : null;
  if (state === "abstain_hard") {
    return {
      state,
      mode,
      headline: "BeaconAI couldn't make recommendations from this analysis",
      detail: "A problem with the store data stopped the analysis from recommending anything. The issues found are listed below.",
    };
  }
  if (state === "abstain_soft") {
    return {
      state,
      mode,
      headline: "No campaign is recommended from this analysis",
      detail: ABSTAIN_DISPLAY[mode] || "None of the plays cleared the bar for a recommendation this time.",
    };
  }
  return { state: "publish", mode, headline: null, detail: null };
}

// Watching entries carry no measurement claim — the engine is only saying which
// metric it is keeping an eye on and what would make it act.
function watchingFor(engineRun) {
  return (engineRun?.watching || []).map((signal) => ({
    metric: signal.metric || null,
    metric_label: metricLabel(signal.metric) || "Metric",
    trend: ["up", "down", "flat"].includes(signal.trend) ? signal.trend : null,
    threshold_to_act: signal.threshold_to_act || null,
  }));
}

function presentEngineRun(engineRun, manifest = null, narration = null, options = {}) {
  const narrationMap = narrationByPlay(narration);
  const currency = options.currency || null;
  const recommendations = [
    ...(engineRun?.recommendations || []).map((card, index) => normalizeCard(card, "recommendation", index, manifest, narrationMap, currency)),
    ...(engineRun?.recommended_experiments || []).map((card, index) => normalizeCard(card, "recommended_experiment", index, manifest, narrationMap, currency)),
  ];
  // Briefing header prose is LLM-authored by the narration MCP (guarded) or
  // NOTHING — the observation chips carry the data when no summary was authored.
  const summaryPayload = narration?.state_of_store_summary || null;
  const stateOfStore = summaryPayload && !summaryPayload.used_fallback && summaryPayload.summary
    ? summaryPayload.summary
    : null;
  const stateOfStoreObs = stateOfStoreObservations(engineRun);

  return {
    schema: "beaconai.ui_recommendations.v1",
    run_id: engineRun?.run_id || manifest?.run_id || null,
    store_id: manifest?.store_id || engineRun?.store_id || null,
    engine_schema_version: engineRun?.schema_version || null,
    // When the ANALYSIS ran. The engine run carries no timestamp of its own, so
    // this comes from the stored run row; it is never the sync time.
    generated_at: options.analysedAt || engineRun?.created_at || manifest?.created_at || null,
    currency,
    recommendation_count: recommendations.length,
    ...(stateOfStore ? { state_of_store: stateOfStore } : {}),
    ...(stateOfStoreObs.length ? { state_of_store_observations: stateOfStoreObs } : {}),
    decision: decisionFor(engineRun),
    data_quality_flags: dataQualityFlags(engineRun),
    recommendations,
    considered: (engineRun?.considered || []).map((card, index) => normalizeRejectedCard(card, index, narrationMap)),
    // Held plays the engine dropped from the list. Without this, a truncated
    // list reads as the complete set.
    considered_truncated_count: Number(engineRun?.considered_truncated_count) || 0,
    watching: watchingFor(engineRun),
    abstain: engineRun?.abstain || null,
    manifest: manifest ? {
      schema_version: manifest.schema_version,
      run_id: manifest.run_id,
      store_id: manifest.store_id,
      created_at: manifest.created_at,
      audiences: manifest.artifacts?.audiences || [],
    } : null,
  };
}

module.exports = {
  presentEngineRun,
  // Exported for the presenter fixtures.
  REASON_DISPLAY,
  EVIDENCE_SOURCE_DISPLAY,
};
