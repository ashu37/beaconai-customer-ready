function titleizeId(value) {
  return String(value || "recommendation")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
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

function normalizeRevenueRange(range) {
  if (!range || range.suppressed) {
    return {
      low: null,
      mid: null,
      high: null,
      currency: "USD",
      source: range?.source || null,
      suppressed: Boolean(range?.suppressed),
      suppression_reason: range?.suppression_reason || null,
    };
  }

  const low = range.p10 ?? range.low ?? null;
  const mid = range.p50 ?? range.mid ?? null;
  const high = range.p90 ?? range.high ?? null;

  return {
    low,
    mid,
    high,
    currency: "USD",
    source: range.source || null,
    suppressed: false,
    suppression_reason: null,
  };
}

function formatRevenue(range) {
  if (!range || range.low == null || range.high == null) {
    return "No dollar figure is stated for this play yet.";
  }
  const low = Math.round(Number(range.low));
  const high = Math.round(Number(range.high));
  if (!Number.isFinite(low) || !Number.isFinite(high)) {
    return "No dollar figure is stated for this play yet.";
  }
  if (low === high) return `The opportunity is sized around $${low.toLocaleString()}.`;
  return `The opportunity is sized in the $${low.toLocaleString()}-$${high.toLocaleString()} range.`;
}

function narrationForCard(card, role) {
  const playName = titleizeId(card.play_id);
  const audienceSize = card.audience?.size;
  const audiencePhrase = audienceText(card.audience);
  const mechanism = mechanismLabel(card.mechanism_intent);
  const revenueRange = normalizeRevenueRange(card.revenue_range);

  const playThesis = [
    `${playName} is ready for review because BeaconAI found a defined customer group: ${audiencePhrase}.`,
    Number.isFinite(Number(audienceSize)) ? `It covers ${Number(audienceSize).toLocaleString()} customers in this run.` : "",
  ].filter(Boolean).join(" ");

  const whatWeWouldSend = mechanism
    ? `Use a ${mechanism} message sequence, then choose or edit the final Klaviyo template in Review Queue.`
    : "Use a tailored message for this audience, then choose or edit the final Klaviyo template in Review Queue.";

  const evidenceSummary = card.evidence_source === "STORE_MEASURED"
    ? formatRevenue(revenueRange)
    : `${formatRevenue(revenueRange)} This is opportunity sizing, not a promised lift from sending.`;

  return {
    role,
    play_thesis: playThesis,
    what_we_d_send: whatWeWouldSend,
    evidence_summary: evidenceSummary,
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

function normalizeCard(card, role, index, manifest, narrationMap) {
  const id = card.play_id || `${role}-${index + 1}`;
  const revenueRange = normalizeRevenueRange(card.revenue_range);
  const guardedNarration = narrationFor(narrationMap, id, role);
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
    play_name: titleizeId(id),
    role,
    lane: role === "recommended_experiment" ? "experiment" : "recommendation",
    source: "atul-engine",
    mechanism: narration.play_thesis,
    audience_archetype: audienceText(card.audience),
    audience_size: card.audience?.size ?? 0,
    confidence: card.confidence_label || "Review",
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
    template_prompt: {
      subject: `${titleizeId(id)} for your next campaign`,
      previewText: narration.evidence_summary,
      headline: titleizeId(id),
      body: narration.play_thesis,
      support: narration.what_we_d_send,
      cta: "Shop now",
    },
    raw: card,
  };
}

function normalizeRejectedCard(card, index, narrationMap) {
  const id = card.play_id || `considered-${index + 1}`;
  const guardedNarration = narrationFor(narrationMap, id, "considered");
  return {
    id,
    play_id: id,
    play_name: titleizeId(id),
    role: "considered",
    reason_code: card.reason_code || null,
    audience_size: card.audience_size ?? 0,
    audience_archetype: card.audience_definition || "Held for more evidence",
    mechanism: guardedNarration?.play_thesis || "This play was considered and held by the engine.",
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

function presentEngineRun(engineRun, manifest = null, narration = null) {
  const narrationMap = narrationByPlay(narration);
  const recommendations = [
    ...(engineRun?.recommendations || []).map((card, index) => normalizeCard(card, "recommendation", index, manifest, narrationMap)),
    ...(engineRun?.recommended_experiments || []).map((card, index) => normalizeCard(card, "recommended_experiment", index, manifest, narrationMap)),
  ];

  return {
    schema: "beaconai.ui_recommendations.v1",
    run_id: engineRun?.run_id || manifest?.run_id || null,
    store_id: manifest?.store_id || engineRun?.store_id || null,
    engine_schema_version: engineRun?.schema_version || null,
    generated_at: engineRun?.created_at || manifest?.created_at || null,
    recommendation_count: recommendations.length,
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
