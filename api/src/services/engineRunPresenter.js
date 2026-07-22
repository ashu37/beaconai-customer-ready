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

// P1-4: merchant-facing reasons for held / considered plays.
// Pattern: state the gap + what unlocks it.
const REASON_DISPLAY = {
  insufficient_sample: "Not enough order history yet — this unlocks as more orders sync.",
  insufficient_data: "Not enough store data yet — this unlocks as more orders sync.",
  audience_too_small: "Only a few customers match right now — this unlocks as the audience grows.",
  low_confidence: "The signal isn't strong enough yet — this unlocks as more orders sync.",
  no_measurement: "Not enough measured history yet — this unlocks as more orders sync.",
  guardrail: "Held by a safety guardrail — this unlocks as the supporting data strengthens.",
  cooldown: "Recently active for this audience — this unlocks again after a short cooldown.",
  monitor_only: "This is a signal to watch, not a campaign to send right now.",
};

const REASON_FALLBACK = "BeaconAI needs more store data before recommending this.";

function reasonDisplay(reasonCode, card) {
  if (!reasonCode) return REASON_FALLBACK;
  const key = String(reasonCode).toLowerCase();
  if (key === "audience_too_small") {
    const n = Number(card?.audience_size);
    if (Number.isFinite(n) && n > 0) {
      return `Only ${n.toLocaleString()} customers match right now — this unlocks as the audience grows.`;
    }
  }
  return REASON_DISPLAY[key] || REASON_FALLBACK;
}

function compactSentence(value, fallback) {
  const text = String(value || "").trim();
  return text || fallback;
}

function mechanismLabel(mechanismIntent) {
  const type = mechanismIntent?.type;
  if (!type) return "";
  return titleizeId(type).toLowerCase();
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

function normalizeRevenueRange(range) {
  if (!range || range.suppressed) {
    return {
      low: null,
      mid: null,
      high: null,
      median: null,
      currency: "USD",
      source: range?.source || null,
      suppressed: Boolean(range?.suppressed),
      suppression_reason: range?.suppression_reason || null,
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
    currency: "USD",
    source: range.source || null,
    suppressed: false,
    suppression_reason: null,
  };
}

function moneyLabel(value, currency) {
  const prefix = currency === "USD" || !currency ? "$" : `${currency} `;
  return `${prefix}${Number(value).toLocaleString()}`;
}

// Merchant-facing short label. Leads with median where available.
// e.g. "~$2,400 typical · range $400–$4,500".
function formatRevenue(range) {
  if (!range || range.low == null || range.high == null) return null;
  const low = range.low;
  const high = range.high;
  if (!Number.isFinite(Number(low)) || !Number.isFinite(Number(high))) return null;
  const currency = range.currency;
  const rangeLabel = low === high
    ? moneyLabel(low, currency)
    : `${moneyLabel(low, currency)}–${moneyLabel(high, currency)}`;
  if (range.median != null && Number.isFinite(Number(range.median))) {
    return `~${moneyLabel(range.median, currency)} typical · range ${rangeLabel}`;
  }
  return `range ${rangeLabel}`;
}

function formatAudienceSize(size) {
  const num = Number(size);
  if (!Number.isFinite(num) || num <= 0) return null;
  return num.toLocaleString();
}

function lowerFirst(text) {
  const value = String(text || "").trim();
  if (!value) return "";
  return value.charAt(0).toLowerCase() + value.slice(1);
}

// P1-3: short evidence line for the card face.
function evidenceLineForCard(card) {
  if (card.evidence_source === "STORE_MEASURED") {
    const n = Number(card.measurement?.n);
    return Number.isFinite(n) && n > 0
      ? `Based on ${n.toLocaleString()} orders from your store`
      : "Based on your store's order history";
  }
  return "Based on patterns from similar stores";
}

// P0-2 evidence sentence (full narration form).
function evidenceSentence(card) {
  if (card.evidence_source === "STORE_MEASURED") {
    const n = Number(card.measurement?.n);
    const nClause = Number.isFinite(n) && n > 0 ? ` (${n.toLocaleString()} orders analyzed)` : "";
    return `Based on your store's own order history${nClause}.`;
  }
  return "Based on patterns from similar stores — your store's data will sharpen this over time.";
}

// P0-4: revenue sentence for the thesis. Omitted when unsized.
function revenueSentence(card) {
  const range = normalizeRevenueRange(card.revenue_range);
  if (range.suppressed || range.low == null || range.high == null || range.median == null) return "";
  return `Estimated opportunity: ${moneyLabel(range.low, range.currency)}–${moneyLabel(range.high, range.currency)} (median ~${moneyLabel(range.median, range.currency)}) if this campaign performs in the typical range.`;
}

function narrationForCard(card, role) {
  const audienceCount = formatAudienceSize(card.audience?.size);
  const oneLiner = playOneLiner(card.play_id) || audienceText(card.audience);
  const mechanism = mechanismLabel(card.mechanism_intent);

  // WHO + WHY NOW + EXPECTED OUTCOME
  // One-liners already name the group ("Customers who...", "Buyers who...")
  // so the count is appended, never prepended, to avoid "234 customers customers who...".
  const whoWhy = audienceCount
    ? `${oneLiner} — ${audienceCount} customers match right now.`
    : `${oneLiner}.`;
  const evidence = evidenceSentence(card);
  const revenue = revenueSentence(card);

  const playThesis = [whoWhy, evidence, revenue].filter(Boolean).join(" ");

  const whatWeWouldSend = mechanism
    ? `A ${mechanism} email to this group. You'll pick and edit the exact template before anything is sent.`
    : `A tailored email to this group. You'll pick and edit the exact template before anything is sent.`;

  return {
    role,
    play_thesis: playThesis,
    what_we_d_send: whatWeWouldSend,
    evidence_summary: revenue || evidence,
    used_fallback: true,
    llm_mode: "api-deterministic",
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

function normalizeCard(card, role, index, manifest, narrationMap) {
  const id = card.play_id || `${role}-${index + 1}`;
  const revenueRange = normalizeRevenueRange(card.revenue_range);
  const rawGuardedNarration = narrationFor(narrationMap, id, role);
  // If the narration service itself fell back, its text is the templated
  // "This play targets the <play_id> opportunity..." sentence — prefer our
  // merchant-language narration instead of surfacing that tautology.
  const guardedNarration = rawGuardedNarration
    && !rawGuardedNarration.used_fallback
    && !isTautologyNarration(rawGuardedNarration)
    ? rawGuardedNarration
    : null;
  const fallbackNarration = narrationForCard(card, role);
  const narration = guardedNarration ? {
    role,
    play_thesis: guardedNarration.play_thesis,
    what_we_d_send: guardedNarration.what_we_d_send,
    evidence_summary: guardedNarration.evidence_summary,
    guard_violations: guardedNarration.guard_violations || [],
    used_fallback: Boolean(guardedNarration.used_fallback),
    llm_mode: "atul-narration",
  } : fallbackNarration;
  const audienceArtifact = audienceArtifactFor(card, manifest);

  return {
    id,
    play_id: id,
    play_name: playDisplayName(id),
    play_one_liner: playOneLiner(id),
    role,
    lane: role === "recommended_experiment" ? "experiment" : "recommendation",
    source: "atul-engine",
    mechanism: narration.play_thesis,
    audience_archetype: audienceText(card.audience),
    audience_size: card.audience?.size ?? 0,
    confidence: card.confidence_label || "Review",
    evidence_line: evidenceLineForCard(card),
    evidence_source: card.evidence_source || null,
    evidence: {
      evidence_source: card.evidence_source || null,
      evidence_class: card.evidence_class || null,
      measurement_metric: card.measurement?.metric || null,
      observed_effect: card.measurement?.observed_effect ?? null,
      sample_size: card.measurement?.n ?? null,
      primary_window: card.measurement?.primary_window || null,
    },
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
    reason_display: reasonDisplay(card.reason_code, card),
    audience_size: card.audience_size ?? 0,
    audience_archetype: card.audience_definition || "Held for more evidence",
    mechanism: guardedNarration?.play_thesis || reasonDisplay(card.reason_code, card),
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
// The engine intentionally emits no prose (Pivot 2); the presenter authors the
// language. We synthesize a header sentence from the top-moved metrics. Never
// fabricated numbers — magnitudes come straight from the engine's delta_pct.
const METRIC_LABELS = {
  aov: "average order value",
  repeat_rate_within_window: "repeat purchase rate",
  orders: "orders",
  returning_customer_share: "returning-customer share",
  net_sales: "net sales",
};

function stateOfStoreSentence(engineRun) {
  const observations = engineRun?.state_of_store;
  if (!Array.isArray(observations)) return null;

  const clauses = observations
    .filter((obs) =>
      obs
      && obs.classification === "moved"
      && Number.isFinite(obs.delta_pct)
      && Object.prototype.hasOwnProperty.call(METRIC_LABELS, obs.supporting_metric))
    .sort((a, b) => Math.abs(b.delta_pct) - Math.abs(a.delta_pct))
    .slice(0, 2)
    .map((obs) => {
      const pct = Math.round(Math.abs(obs.delta_pct) * 100);
      if (pct === 0) return null;
      const direction = obs.delta_pct >= 0 ? "up" : "down";
      return `${METRIC_LABELS[obs.supporting_metric]} ${direction} ${pct}%`;
    })
    .filter(Boolean);

  if (!clauses.length) return null;
  return `Since the prior period: ${clauses.join(" · ")}`;
}

function presentEngineRun(engineRun, manifest = null, narration = null) {
  const narrationMap = narrationByPlay(narration);
  const recommendations = [
    ...(engineRun?.recommendations || []).map((card, index) => normalizeCard(card, "recommendation", index, manifest, narrationMap)),
    ...(engineRun?.recommended_experiments || []).map((card, index) => normalizeCard(card, "recommended_experiment", index, manifest, narrationMap)),
  ];
  const stateOfStore = stateOfStoreSentence(engineRun);

  return {
    schema: "beaconai.ui_recommendations.v1",
    run_id: engineRun?.run_id || manifest?.run_id || null,
    store_id: manifest?.store_id || engineRun?.store_id || null,
    engine_schema_version: engineRun?.schema_version || null,
    generated_at: engineRun?.created_at || manifest?.created_at || null,
    recommendation_count: recommendations.length,
    ...(stateOfStore ? { state_of_store: stateOfStore } : {}),
    recommendations,
    considered: (engineRun?.considered || []).map((card, index) => normalizeRejectedCard(card, index, narrationMap)),
    watching: engineRun?.watching || [],
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
};
