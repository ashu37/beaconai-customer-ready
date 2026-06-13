"""EngineRun typed schema (Milestone 1, T1.1).

This module defines the canonical structured-output contract for the
BeaconAI decision engine, per the PM-Q2 specification frozen in
``agent_outputs/product-strategy-pm-overhaul-requirements.md`` and
referenced by ``agent_outputs/implementation-manager-overhaul-plan-final.md``
Milestone 1.

M1 scope:
- Add the dataclasses, enums, and ``to_dict()`` serialization. No methods
  beyond serialization. No validation logic. Receipts-only — nothing in M1
  is rendered to the merchant.

Downstream milestones consume this contract:
- M2 populates ``PlayCard`` from a play registry.
- M4a/M4b populate ``Measurement.p_internal``/``ci_internal``.
- M5 produces ``RejectedPlay`` + ``Abstain`` from guardrails.
- M6 populates ``RevenueRange`` via the sizing module.
- M7 finalizes the EngineRun via ``decide()``.
- M8 renders the EngineRun.
- M9 reads ``measurement.p_internal`` for calibration and writes
  ``recommended_history.json``.

Hard contract invariants (NOT enforced in M1; documented for M4+):
- ``evidence_class == "targeting"`` REQUIRES ``measurement is None``.
- ``evidence_class == "measured"`` REQUIRES non-null
  ``measurement.observed_effect``, non-null ``measurement.n``, and
  ``measurement.consistency_across_windows >= 2``.
- ``revenue_range.suppressed == True`` ⇒ renderer hides $ entirely.
- ``sum(recommendations[].revenue_range.p50) <= scale.monthly_revenue * 0.25``.
- Any populated ``data_quality_flags`` ⇒ ``abstain.state = "abstain_hard"``,
  ``recommendations = []``.
- ``briefing.html`` MUST NOT contain ``p =``, ``q =``, ``CI``,
  ``confidence_score``, or ``final_score``.

Round-trip: ``EngineRun.to_dict()`` followed by ``EngineRun.from_dict()``
preserves all fields. Enums round-trip through their string values.

---

CHANGELOG — engine_run.py contract surface
==========================================

The ``EngineRun.schema_version`` literal default is the single source of
truth for the contract version. Bump it whenever the contract surface
changes in a way that downstream agents (narration / assembly) must be
aware of. SemVer-ish: additive changes within ``2.x.x`` are allowed;
breaking changes go to ``3.0.0``.

v2.1.0 — 2026-06-02 (S-FE-descriptive-distribution; FOUNDER-AUTHORIZED additive)
--------------------------------------------------------------------------------

Additive within the ``2.x.x`` freeze (founder lock-in #3 permits additive
``2.x`` changes). FOUNDER-AUTHORIZED 2026-06-02 per ``docs/evidence_layer.md``
§7 L-EV-19 ("`Audience.descriptive_distribution` — one generic additive
primitive ... 2.0.0 -> 2.1.0") + L-EV-20 (descriptive-only gating).

- ADDED ``Audience.descriptive_distribution: Optional[DescriptiveDistribution]
  = None`` — a richer rendering of M4 (audience) for the four distributional
  plays (winback / threshold-bundle / replenishment / discount-hygiene),
  carrying out the observed series the audience builders already compute and
  currently discard (L-EV-18 discarded-series diagnosis). NOT a 10th evidence
  member — the closed 9-member set (L-EV-2) is preserved.
- ADDED ``DescriptiveDistribution`` dataclass (``kind`` + ``bins`` +
  ``counts`` + optional ``marker`` + paired RULE-A ``suppressed`` +
  ``suppression_reason``). DESCRIPTIVE-ONLY (L-EV-20): observed counts + an
  optional real marker; NO projected rate, NO dollar field, NO lift. The
  engine emits the binned series only, NEVER a chart-spec (L-EV-3
  Stop-Coding Line).
- ADDED ``DistributionKind(str, Enum)`` — closed 4-member set
  (DORMANCY_DAYS / AOV_GAP / REORDER_GAP_DAYS / DISCOUNT_FRACTION); no
  generic fallback per the L-EV-19 lock.
- ADDED ``DescriptiveDistributionSuppressionReason(str, Enum)`` — closed
  3-member RULE-A null-reason paired with ``DescriptiveDistribution.suppressed``
  (SOURCE_SERIES_EMPTY / SOURCE_SERIES_ABSENT / INTEGRITY_FAILED). An
  empty / absent / integrity-failed series is typed, never silently omitted.
- ADDED ``build_descriptive_distribution`` — the single pure binning seam the
  producer (``measurement_builder``) calls so audience builders stay pure and
  histogram logic lives in one place. Binning convention: fixed per-kind bin
  edges; ``counts[i]`` counts ``[edges[i], edges[i+1])`` with the final bin
  closed on the right; out-of-range observations clamp into the edge bins
  (no observation dropped); ``len(counts) == len(bins) - 1``.
- ALL four symbols exported via ``__all__`` per DS R6 single-file authority.
- Producer wiring: ``src/audience_builders.py`` stashes the already-computed
  observed series on three new ``AudienceResult`` fields
  (``descriptive_kind`` / ``descriptive_series`` / ``descriptive_marker``);
  ``src/measurement_builder.build_prior_anchored_play_card`` bins them via
  ``build_descriptive_distribution`` and attaches the atom to ``Audience``.
- Markers: winback marker = dormancy-window upper bound (real,
  builder-derived). threshold-bundle / replenishment / discount-hygiene
  markers = ``None`` today (threshold_aov / replenishment_window_days /
  target_discount_share are None/TODO(S14)) — the typed-absence of the
  annotation line per L-EV-20, NOT a series suppression.
- Strict-cutover carry-forward: pre-2.1.0 snapshots have no
  ``audience.descriptive_distribution`` key -> ``None``
  (``_from_dict_audience`` tolerates absence; ``from_dict`` back-compat).
- ``schema_version`` literal default ``"2.0.0"`` -> ``"2.1.0"``.
  ``schemas/engine_run.v2.json`` regenerated via ``tools/generate_schema.py``
  (auto-discovers the new dataclass + enums; title bumped to v2.1.0).

v2.1.0 addendum — 2026-06-03 (S-FE-rfm-segment-distribution; FOUNDER-AUTHORIZED additive)
----------------------------------------------------------------------------------------

Additive WITHIN the existing ``2.1.0`` (NO second version bump — the
``schema_version`` literal is already ``"2.1.0"`` from the
descriptive-distribution change above). FOUNDER-AUTHORIZED per
``docs/evidence_layer.md`` §7 L-EV-17 (the RFM segment_distribution
additive candidate) + L-EV-15 (RFM has no descriptive twin → suppresses
as a unit). Unblocks the merchant-facing RFM segment-distribution chart.

- ADDED ``SegmentBand`` dataclass (``src/predictive/model_card.py``):
  ``{segment_name: str, n: int, share: float}``. AGGREGATE-ONLY +
  DESCRIPTIVE (L-EV-17/20): the named segment, its observed customer
  count, and its fraction of the analyzed base. NO per-customer rows, NO
  monetary magnitude, NO projected rate / lift / dollar — the three
  fields are the complete closed shape (contrast ``NonLiftAtom``, the
  only addressable-dollar surface).
- ADDED ``ModelCard.segment_distribution: Optional[List[SegmentBand]] =
  None`` — RFM-SCOPED: populated ONLY on the ``rfm`` ModelCard, ONLY when
  ``fit_status in {VALIDATED, PROVISIONAL}``. Other substrates'
  ModelCards (bgnbd / gamma_gamma / survival / cf) have no named-segment
  concept and leave it ``None``. The bands come from
  ``rfm_table["segment_name"].value_counts()`` (already computed,
  previously reduced to ``n_segments_observed`` and discarded — the
  L-EV-18 discarded-series diagnosis applied to RFM). Ordering: ``n``
  DESCENDING, ties broken by canonical LTV rank
  (``SEGMENT_LTV_RANK_ORDER``).
- ADDED ``ModelCard.segment_distribution_suppression_reason:
  Optional[RfmSegmentDistributionSuppressionReason] = None`` — paired
  RULE-A null-reason. On an ``rfm`` card whose segmentation was attempted
  but did NOT clear the inferential gate (REFUSED / INSUFFICIENT_DATA),
  ``segment_distribution`` is ``None`` and the reason is
  ``FIT_NOT_VALIDATED``. RFM suppresses as a unit (no descriptive twin,
  L-EV-15), never a fabricated/partial distribution.
- ADDED ``RfmSegmentDistributionSuppressionReason(str, Enum)`` — closed
  2-member set (FIT_NOT_VALIDATED / FLAG_OFF) in
  ``src/predictive/model_card.py`` (lowercase string values, mirroring
  ``DescriptiveDistributionSuppressionReason``).
- Population: ``src/predictive/rfm.py::_compute_segment_distribution``
  (pure, computes from its own ``rfm_table``; no new cross-module
  coupling). Engine emits the typed bands only — NO chart-spec (no axis /
  color / type) per L-EV-3.
- Serialization: round-trips via the existing ``_to_jsonable`` recursion
  (``asdict`` reaches ``SegmentBand``, the enum unwraps to its string
  value). ``predictive_models`` ModelCards pass through as-is on
  ``EngineRun.from_dict``; older runs / non-RFM cards have no
  ``segment_distribution`` key -> ``None`` (additive optional field,
  back-compat).
- ``schemas/engine_run.v2.json`` regenerated via
  ``tools/generate_schema.py`` — ADDED ``$defs.SegmentBand`` +
  ``$defs.RfmSegmentDistributionSuppressionReason`` + the two new
  ``ModelCard`` properties (purely additive; title remains v2.1.0).

v2.0.0 — 2026-05-31 (S13.6-T5; contract FREEZE)
-----------------------------------------------

**Hard freeze** per founder lock-in #3 (2026-05-30): subsequent
additions require a major version bump + coordinated narration +
assembly agent update. Additive changes within ``2.x.x`` are allowed;
breaking changes go to ``3.0.0``.

S13.6 (T1a..T7.5):

- T1a (``a607bb8``) — STRIP engine-authored prose bundle (Pivot 2 +
  S13.6-T1a Option D, founder + DS approved 2026-05-30). Six prose
  slots removed from the dataclasses:
  ``PlayCard.recommendation_text``, ``PlayCard.why_now``,
  ``RejectedPlay.reason_text``, ``RejectedPlay.evidence_snapshot``,
  ``RejectedPlay.would_fire_if``, ``Abstain.reason``. The
  ``notes: List[str]`` debris on Sensitivity / Provenance /
  PredictedSegment / ModelCardRef / MonthDelta is gated by
  ``INCLUDE_DEBUG_FIELDS`` (default OFF). DECIDE-seam ``why_now`` copy
  ladder REMOVED. ``briefing.html`` byte-identity canary RETIRED
  (replaced by the ``engine_run.json`` SHA pin + the upcoming S13.7-T2
  JSON-Schema round-trip).
- T1b (``7d77dc3``) — STRIP ``Observation.text`` from the contract
  surface. The state-of-store sentence is now synthesized at render
  time from typed numerics (``supporting_metric`` / ``classification``
  / ``delta_pct`` / ``anomaly_flags`` / ``n_days_observed`` /
  ``n_days_expected``) via ``src.storytelling_v2.
  _synthesize_observation_sentence``; debug-only per the Pivot 2
  addendum.
- T2 (``25a4488``) — TYPE the three ``Any`` slots on ``EngineRun``:

      store_profile: Optional[StoreProfile]
      predictive_models: Dict[str, ModelCard]
      cohort_diagnostics: Dict[str, RetentionCard]

  REMOVE the legacy Klaviyo-brief-inputs slot on ``PlayCard``
  entirely (founder lock-in #6 + D-5 manual-Klaviyo); see the T2
  breadcrumb comment on ``PlayCard`` for the field-name reference.
  DS R6 re-export block added at the top of this module so downstream
  agents read ONE file for the contract surface.
- T3 (``5674f4b``) — ``OpportunityContext`` ``NonLiftAtom`` typed
  wrapper (DS R1, HIGHEST contract-shape risk). Stripped the duplicate
  ``aov`` + ``addressable_value`` keys; wrapped the four monetary
  numerics in ``NonLiftAtom`` so the "NOT projected lift" constraint
  is now structural. Strict deserialization: pre-T3 snapshots ->
  ``opportunity_context = None``.
- T4 (``f914a98``) — Typed ``FitWarning`` grammar replaces the
  ``List[str]`` ``"{LEVEL}:{substrate}"`` strings on
  ``ModelCardRef.fit_warnings`` (D-S13-4 grammar lock). Closed-set
  ``FitWarningLevel`` enum (three members). Q-S13-4 LOCK preserved
  (ML-fit emits ONLY on ``model_card_ref.fit_warnings``, NEVER on
  ``RejectedPlay.reason_code``). Strict deserialization: pre-T4
  snapshots -> ``fit_warnings = []``.
- T5 (this commit) — ``schema_version`` literal default
  ``"1.0.0"`` -> ``"2.0.0"`` + this CHANGELOG block. Contract FROZEN
  at ``2.x.x`` per founder lock-in #3.
- T6 (this commit) — ``MechanismIntent`` typed atom + ``MechanismType``
  closed enum (DS §(d) verdict + DS adjudication on T6 halt 2026-05-31;
  founder approved Option C). Per founder lock-in #4 (2026-05-30):
  "Engine ships structured atoms only; narration agents render copy."

  * ADDED ``PlayCard.mechanism_intent: Optional[MechanismIntent]`` —
    new additive field (additive within v2.0.0 contract freeze per
    founder lock-in #3); narration agents read the typed atom from the
    contract, no longer need to re-implement priors.yaml lookup.
    Producer wiring: a ``play_id``-keyed
    ``_build_mechanism_intent`` helper in ``src/decide.py`` populates
    the field at PlayCard assembly for the 9 mapped play_ids.
  * RETYPED ``RejectedPlay.mechanism: Optional[str]`` ->
    ``Optional[MechanismIntent]`` — completion of T1a prose-strip
    discipline (the field T1a missed by accident). Producer wiring:
    the 4 RejectedPlay emit sites in ``src/decide.py`` swap from
    ``_surface_mechanism_for_play`` (which returns YAML prose) to
    ``_build_mechanism_intent`` (which returns the typed atom).
  * ``MechanismType``: closed 10-member str-Enum (DS §(d) verbatim);
    each member's string value equals its name (upper-snake), matching
    the ``WouldBeMeasuredBy`` enum convention. Free-text rejection
    enforced by the standard enum constructor.
  * ``MechanismIntent``: ``type: MechanismType`` +
    ``parameters: Dict[str, Any] = field(default_factory=dict)``. The
    parameters dict carries DS §(d) per-type keys for the 5 spec'd
    types (WINBACK_REACTIVATION_EMAIL, FIRST_TO_SECOND_NUDGE,
    THRESHOLD_BUNDLE_OFFER, DISCOUNT_DEPENDENCY_HYGIENE,
    REPLENISHMENT_REMINDER); the 4 Tier-B types (BESTSELLER_AMPLIFY,
    CATEGORY_EXPANSION, SUBSCRIPTION_NUDGE, ROUTINE_BUILDER) and
    LOOKALIKE_HIGH_VALUE_PROSPECT carry an empty dict per DS §(d)
    acceptance ("Tier-B types: parameters empty dict acceptable for
    v2.0.0; flesh out at S14+"). Per-type parameters shape spec lands
    at S13.7-T3 (``docs/mechanism_contract.md``).
  * Strict deserialization (T3/T4 precedent): legacy
    ``engine_run.json`` snapshots have no ``PlayCard.mechanism_intent``
    key -> ``None``. Legacy ``RejectedPlay.mechanism: str`` shape ->
    ``None`` (strict cutover by design; not silently parsed).
  * DEFERRED to S13.6-T8 per DS Q7: storytelling_v2
    ``_render_what_we_send`` / ``_mechanism_for_play`` consumer rewire
    to read ``PlayCard.mechanism_intent`` from the contract. T6 leaves
    the renderer's priors.yaml lookup path intact; the renderer adds a
    small compatibility shim at the ``RejectedPlay.mechanism`` read
    seam so a ``MechanismIntent`` value falls back to the YAML
    ``_mechanism_for_play`` lookup (no engine-authored prose; the YAML
    fallback is the established path). The full structured render
    lands at T8.
  * ``priors.yaml metadata.mechanism`` UNCHANGED at T6; becomes a
    renderer-side debug-only fallback post-T8.
  * Pivot 2 reaffirmation addendum on PIVOTS.md lands at T8 close
    (NOT this commit; DS Q7 sequencing).
- T7a (this commit) — RULE A flag-aware absence-of-data pattern + 3
  null-reason enums + 3 paired ``_null_reason`` fields (DS adjudication
  2026-06-01; founder approved 2026-06-01).

  * ADDED ``RevenueRangeSuppressionReason(str, Enum)`` — 9 closed-set
    members matching the producer string literals byte-for-byte
    (``cold_start``, ``audience_zero``, ``aov_zero``,
    ``observed_effect_invalid``, ``no_prior_base_rate``,
    ``prior_unvalidated``, ``aov_unavailable``,
    ``directional_no_intervention_effect``,
    ``experiment_no_calibrated_lift``). NO producer rewrites — the enum
    wraps existing string literals at the seam per DS Q1.
  * ADDED ``MonthDeltaNullReason(str, Enum)`` — 5 closed-set members
    (``no_store_id``, ``no_prior_run``, ``anchor_date_unparseable``,
    ``under_21d_floor``, ``lineage_changed``). ``LINEAGE_CHANGED`` is
    forward-compat per DS verdict — S13-T3 lineage-bump nulls the inner
    ``MonthDelta.segment_shifts`` field, not the wrapper.
  * ADDED ``PredictedSegmentNullReason(str, Enum)`` — 4 closed-set
    members (``modal_floor_not_cleared``, ``parquet_missing``,
    ``parquet_unreadable``, ``no_audience_intersection``). Applies to
    ``PredictedSegment.segment_name`` (INNER field), NOT the wrapper —
    audit fields (``audience_modal_share`` + ``n_audience``) stay
    populated under the D-S13-2 modal-segment floor.
  * ADDED ``RevenueRange.suppression_reason:
    Optional[RevenueRangeSuppressionReason] = None`` paired with the
    existing ``suppressed: bool`` flag.
    Invariant: ``suppressed=True`` ⇔ ``suppression_reason is set``.
  * ADDED ``EngineRun.month_2_delta_null_reason:
    Optional[MonthDeltaNullReason] = None`` paired with
    ``month_2_delta: Optional[MonthDelta]``. Producer
    (:func:`src.predictive.month_2_delta.detect_month_2_delta`) now
    returns a 2-tuple ``(Optional[MonthDelta],
    Optional[MonthDeltaNullReason])`` so the (value, reason) pair is
    always emitted together at the seam (Option (a), pin-able).
  * ADDED ``PredictedSegment.segment_name_null_reason:
    Optional[PredictedSegmentNullReason] = None`` paired with
    ``segment_name: Optional[str]``.
  * REVISED RULE A (DS adjudication 2026-06-01 verbatim): **For every
    Optional field F on a contract surface, if F is None AND the
    relevant feature flag is ON, then F's paired ``<F>_null_reason``
    MUST be set. Flag-OFF default-None is exempt and MUST be marked
    with a source-level annotation:
    ``# null_reason_exempt: default-None when ENGINE_V2_<FLAG_NAME>
    is OFF``. The AST sweep test enforces: every Optional field either
    (i) has a paired ``_null_reason`` on the same contract, OR (ii)
    carries the ``null_reason_exempt:`` annotation with a named flag.
    No silent Optionals.**
  * AST sweep test at ``tests/test_s13_6_t7a_no_silent_nulls.py``
    walks every ``Optional[X]`` AnnAssign on a contract dataclass and
    asserts the rule.
  * DS retracts/revises the original §(e) triage. The "single registry
    block" framing is dropped — 3 enums declared individually next to
    their dataclasses per the existing class-locality pattern. The
    substrate-refusal-card audit and ``CustomerIdsNullReason`` are
    DEFERRED to S13.7 (T7b) per founder approval 2026-06-01.
  * Strict-cutover carry-forward: pre-T7a snapshots deserialize with
    ``suppression_reason = None``, ``month_2_delta_null_reason =
    None``, ``segment_name_null_reason = None``.
- T7.5 (this commit) — NULL-REASON ENUM REGISTRY comment block +
  coverage test (see ``tests/test_null_reason_registry.py``). Comment-
  only change to ``src/engine_run.py``; no dataclass shapes altered,
  no new enums added. Pins the 3 shipped T7a pairs as a single source-
  of-truth for agents and documents deferred pairs (S13.7-T7b /
  KI-NEW-AA) with TODO markers in the test.
- T7b (S13.7-T7b) — 3 deferred RULE A enums declared + 1 paired field
  added (closes KI-NEW-AA). Dead-code sweep: ``_surface_mechanism_for_play``
  removed from ``src/decide.py`` (zero call sites confirmed).
  ``targeting_non_causal_prior`` in ``src/sizing.py`` NOT removed (active
  call sites + pinned test assertions; deferred per KI-NEW-AB).

  * ADDED ``StoreProfileNullReason(str, Enum)`` — 2 members
    (``profile_not_loaded``, ``onboarding_incomplete``). Paired with
    ``EngineRun.store_profile`` per revised RULE A. TODO(S14): distinguish
    ``ONBOARDING_INCOMPLETE`` when onboarding-state taxonomy is formalized.
  * ADDED ``EngineRun.store_profile_null_reason:
    Optional[StoreProfileNullReason] = None`` immediately after
    ``store_profile: Optional[StoreProfile]``. Wired in ``src/main.py``
    at the ``ENGINE_V2_STORE_PROFILE`` block: ``PROFILE_NOT_LOADED`` when
    ``build_store_profile`` raises; ``None`` when flag is OFF or profile
    loaded successfully.
  * ADDED ``ModelCardAbsenceReason(str, Enum)`` — 3 members
    (``substrate_not_run``, ``substrate_refused``, ``insufficient_data``).
    Dict field — enum declared for agent reference only; no paired
    ``_null_reason`` field per DS T7b retraction of Dict[k, AbsenceReason].
  * ADDED ``CohortDiagnosticsAbsenceReason(str, Enum)`` — 2 members
    (``insufficient_cohort_depth``, ``substrate_refused``). Dict field
    — enum declared for agent reference only; same pattern as above.
  * All 3 new enums exported via ``__all__`` per DS R6 single-file authority.
  * Registry comment block updated: DEFERRED → SHIPPED for all 3.
  * ``store_profile`` annotation updated: TODO(S13.7-T7b) comment removed;
    ``# null_reason_exempt:`` annotation replaced by ``# paired field`` note.
  * Strict-cutover carry-forward: pre-T7b ``engine_run.json`` snapshots
    deserialize with ``store_profile_null_reason = None``.

v1.0.0 — 2026-05-29 (S13 close; ``cee0e3c`` S13-T4-CLOSE)
---------------------------------------------------------

Substrate of consumer wiring complete; pre-freeze contract.

S13 (Integration / consumer wiring):

- S13-T0 (``722bcb3``) — ``ModelCard`` refactor; authoritative
  ``metrics: Dict[str, float]`` storage with ``InitVar`` legacy
  kwargs + ``__getattr__`` shim for back-compat.
- S13-T1 / T1.5 (``4c087dc`` / ``b646d29``) — NEW
  ``src/predictive/ranking_strategy.py`` module with
  ``AudienceIntent`` str-Enum and intent-conditional chains;
  ``ENGINE_V2_RANKING_STRATEGY_CHAIN`` flipped ON at T1.5.
- S13-T2 / T2.5 (``187af49`` / ``af2a80e``) — ``PlayCard`` consumer
  wiring (``predicted_segment`` + ``model_card_ref``); Q-S13-4 LOCK
  comment block at L167-183; ML-fit gate DORMANT -> LIVE; modal-segment
  stability floor; AST-aware reason-code precedence test refactor.
- S13-T3 / T3.5 (``a97ab54`` / ``43e2ffe``) — ``MonthDelta`` typed
  slot ``EngineRun.month_2_delta`` per Pivot 8 (substrate-state-delta);
  lineage-keyed detection; ``ENGINE_V2_MONTH_2_DELTA`` flipped ON at
  T3.5 with the 4-case rollback contract (Case D = INDEPENDENCE PIN).

S12 (2026-05-28) — ML Predictive Layer Part 3:

- Statistical RFM substrate (custom; INDEPENDENT of BG/NBD; floor of
  the ranking chain).
- Cohort retention curves substrate (custom + numpy bootstrap);
  ``RetentionCard`` dataclass + ``EngineRun.cohort_diagnostics``
  top-level slot per D-S12-1.

S11 (2026-05-28) — ML Predictive Layer Part 2:

- Cox PH survival substrate via ``scikit-survival`` chained on BG/NBD.
- Collaborative filtering substrate via ``implicit`` ALS; INDEPENDENT
  of BG/NBD (4-layer pin).

S10 (2026-05-26) — ML Predictive Layer Part 1:

- BG/NBD + Gamma-Gamma + ``ModelFitStatus`` 4-state enum.
- ``ModelCard`` typed dataclass; ``EngineRun.predictive_models`` slot.

S8 (2026-05-24) — Trust-surface + EB blend:

- ``evidence_source`` chip (``EvidenceSourceChip`` enum).
- ``Sensitivity`` six-key dataclass.
- ``Provenance`` EB-audit object.
- ``pseudo_N`` table locked at ``{30, 15, 10}``.

S7.6 (2026-05-22) — Single-demote-channel invariant (Pivot 7);
``apply_guardrails_to_injected`` helper; three-channel
``priority_prepend``.

S6 / S7 (origin):

- 4-lane slate (``recommendations``, ``recommended_experiments``,
  ``considered``, ``watching``) per the role-uniqueness invariant.
- ``ReasonCode`` enum (typed held-reason).
- 4 evidence tiers (A causal / B directional / C prior /
  D observational).

End CHANGELOG.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

# ---------------------------------------------------------------------------
# DS R6 (S13.6-T2, founder + DS approved 2026-05-30/31) — schema authority =
# ``src/engine_run.py``. Re-export the canonical types used by the three
# typed EngineRun slots so downstream narration + assembly agents read ONE
# file for the contract surface. Per the T1a pattern these are pure
# re-exports — the canonical definitions still live in the producer modules
# and we do not relocate or rename anything.
#
# Mappings (audited 2026-05-31 via grep ``class StoreProfile|class ModelCard
# |class RetentionCard|class ModelFitStatus`` over ``src/``):
#   StoreProfile     -> ``src.profile.types``
#   ModelCard        -> ``src.predictive.model_card``
#   ModelFitStatus   -> ``src.predictive.model_card`` (REUSED enum, S12
#                       vocab-stacking Option A; shared by ModelCard +
#                       RetentionCard per DS S12-T2 lock)
#   RetentionCard    -> ``src.predictive.model_card`` (NOT
#                       ``src.predictive.retention`` — the dataclass lives
#                       alongside ModelCard; ``src/predictive/retention.py``
#                       only holds the substrate ``fit_retention``
#                       function. Flagged per the inventory-grep note in
#                       the T2 brief).
#
# Re-exports MUST stay lazy-safe: the modules below are import-clean (no
# heavy side effects at import time) so this top-of-file block does not
# regress import ordering.
# ---------------------------------------------------------------------------
from .profile.types import StoreProfile
from .predictive.model_card import ModelCard, ModelFitStatus, RetentionCard

__all__ = [
    # Re-exported canonical types (DS R6 schema-authority surface):
    "StoreProfile",
    "ModelCard",
    "ModelFitStatus",
    "RetentionCard",
    # S13.6-T3 (DS R1, founder approved 2026-05-30): NonLiftAtom wraps the
    # four addressable-opportunity numerics on OpportunityContext so the
    # "NOT projected lift / NOT p50 / NOT forecast" constraint is expressed
    # AT THE TYPE — narration agents see a NonLiftAtom, not a raw float with
    # a sticker. Defined locally in this module; exported here for the
    # DS-R6 single-file schema surface.
    "NonLiftAtom",
    # S13.6-T4 (D-S13-4 structural, founder + DS approved 2026-05-31):
    # FitWarning + FitWarningLevel express the ML-fit-warning grammar
    # ("{LEVEL}:{substrate}", LEVEL ∈ {PROVISIONAL_SELECTED,
    # MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED}) STRUCTURALLY at
    # the type system rather than in code comments. Q-S13-4 LOCK is
    # preserved: ML-fit warnings emit ONLY on
    # PlayCard.model_card_ref.fit_warnings, NEVER on
    # RejectedPlay.reason_code. See ModelCardRef.fit_warnings.
    "FitWarning",
    "FitWarningLevel",
    # S13.6-T6 (DS §(d) + founder approved Option C 2026-05-31):
    # MechanismType (closed 10-member enum) + MechanismIntent (typed
    # atom: type + parameters dict) — engine ships structured atoms
    # only per founder lock-in #4 (2026-05-30); narration agents
    # render merchant-facing copy from these atoms. Both defined
    # locally in this module; exported here for the DS-R6 single-file
    # schema surface so narration + assembly agents read ONE file for
    # the contract surface.
    "MechanismType",
    "MechanismIntent",
    # S13.6-T7a (DS adjudication 2026-06-01 + founder approved
    # 2026-06-01): 3 closed-set null-reason enums paired with the
    # corresponding Optional fields per the revised flag-aware RULE A.
    # See the v2.0.0 CHANGELOG block above + the per-enum docstrings.
    "RevenueRangeSuppressionReason",
    "MonthDeltaNullReason",
    "PredictedSegmentNullReason",
    # S13.7-T1: CustomerIdsNullReason — declared per registry block above.
    # PlayCard.audience.customer_ids field pairing deferred to S13.7-T7b.
    "CustomerIdsNullReason",
    # S13.7-T7b (DS adjudication 2026-06-01 + founder approved 2026-06-01):
    # 3 deferred null-reason / absence-reason enums shipped (KI-NEW-AA closed).
    # StoreProfileNullReason: paired with EngineRun.store_profile_null_reason.
    # ModelCardAbsenceReason + CohortDiagnosticsAbsenceReason: dict fields —
    # enum declared for agent reference; no paired _null_reason field.
    "StoreProfileNullReason",
    "ModelCardAbsenceReason",
    "CohortDiagnosticsAbsenceReason",
    # S-FE-descriptive-distribution (L-EV-19 / L-EV-20; FOUNDER-AUTHORIZED
    # 2026-06-02; schema 2.0.0 -> 2.1.0): one generic additive primitive
    # carrying the descriptive observed series the audience builders already
    # compute and currently discard (dormancy days / AOV-gap / reorder-gap /
    # discount-fraction). A richer rendering of M4 (audience), NOT a 10th
    # evidence member — the closed 9-member set (L-EV-2) is preserved.
    # DESCRIPTIVE-ONLY: observed counts + an optional real marker; NO
    # projected rate, NO dollar figure, NO lift (L-EV-20). Suppression is
    # typed via the paired ``suppressed`` + ``suppression_reason`` enum on
    # the atom (RevenueRange precedent). ``build_descriptive_distribution``
    # is the pure binning helper the producer (measurement_builder) calls.
    "DistributionKind",
    "DescriptiveDistributionSuppressionReason",
    "DescriptiveDistribution",
    "build_descriptive_distribution",
]


# ---------------------------------------------------------------------------
# Enums (typed string enums; serialize to their string values)
# ---------------------------------------------------------------------------


class EvidenceClass(str, Enum):
    """Internal evidence class. NOT merchant-facing.

    Maps to the ``confidence_label`` 3-bucket via M7. See PM-Q3.
    """

    MEASURED = "measured"
    DIRECTIONAL = "directional"
    TARGETING = "targeting"
    # WEAK is internal-only per PM-Q3. Not surfaced merchant-facing.
    WEAK = "weak"


class DecisionState(str, Enum):
    """Top-level EngineRun state. See PM-Q4."""

    PUBLISH = "publish"
    ABSTAIN_SOFT = "abstain_soft"
    ABSTAIN_HARD = "abstain_hard"


class ReasonCode(str, Enum):
    """The 11-code RejectedPlay reason enum (PM-Q3).

    Both the briefing renderer (M8) and the future Klaviyo agent must
    understand all 11 codes. M1 declares the enum; downstream milestones
    populate it. ``cap_exceeded`` is added per M7 T7.3 (12th code).

    Phase 6B Stop-Coding-Line Task 3 — equivalence to the contract-final
    minimum required code set (no new codes invented; existing codes
    already cover every required concept):

    - ``AUDIENCE_BELOW_FLOOR``         -> :data:`AUDIENCE_TOO_SMALL`
    - ``EVIDENCE_BELOW_THRESHOLD``     -> :data:`NO_MEASURED_SIGNAL`,
                                          :data:`SIGNAL_INCONSISTENT_ACROSS_WINDOWS`,
                                          :data:`MATERIALITY_BELOW_FLOOR`
    - ``ANOMALOUS_WINDOW``             -> :data:`ANOMALOUS_WINDOW`
    - ``ROLE_CONFLICT``                -> :data:`AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY`,
                                          :data:`CANNIBALIZATION_DEMOTED`
    - ``DUPLICATE_AUDIENCE``           -> :data:`AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY`
    - ``TARGETING_HELD_UNDER_ABSTAIN`` -> :data:`TARGETING_HELD_UNDER_ABSTAIN`

    Free-text reason assignment is forbidden: ``decide.py`` always assigns
    a typed :class:`ReasonCode` value; downstream agents read the enum
    string + :attr:`RejectedPlay.held_reason_detail` (Task 3) for any
    structured numeric context.
    """

    AUDIENCE_TOO_SMALL = "audience_too_small"
    AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY = "audience_overlap_with_higher_priority"
    INVENTORY_BLOCKED = "inventory_blocked"
    NO_MEASURED_SIGNAL = "no_measured_signal"
    SIGNAL_INCONSISTENT_ACROSS_WINDOWS = "signal_inconsistent_across_windows"
    ANOMALOUS_WINDOW = "anomalous_window"
    COLD_START_INSUFFICIENT_DATA = "cold_start_insufficient_data"
    CANNIBALIZATION_DEMOTED = "cannibalization_demoted"
    RECENTLY_RUN_FATIGUE = "recently_run_fatigue"
    MATERIALITY_BELOW_FLOOR = "materiality_below_floor"
    DATA_QUALITY_FLAG = "data_quality_flag"
    # M7 T7.3 adds this as the 12th code when the top-3 cap drops a candidate.
    CAP_EXCEEDED = "cap_exceeded"
    # Synthetic Blocker Fix 3: held targeting plays under ABSTAIN_SOFT.
    # PM-resolved contract: ``decision_state == abstain_soft`` ⇒ zero
    # Recommended cards. The targeting cards that decide() ranked into
    # the head are re-routed into ``considered`` with this typed reason
    # code so the Considered section explains the hold without re-using
    # NO_MEASURED_SIGNAL (which has different upstream M3 semantics).
    TARGETING_HELD_UNDER_ABSTAIN = "targeting_held_under_abstain"
    # Sprint 5 Ticket S5-T2 (resolves KI-20): supplements directional
    # ``first_to_second_purchase`` no-signal abstain. The Phase 5.6
    # directional builder reads ``returning_customer_share`` deltas on
    # the L28 primary window. Supplement reorder cadences (commonly
    # 28-45 days) straddle the L28 boundary, so the supporting state
    # statistic is structurally too stable on the supplements vertical
    # to clear ``PHASE5_DIRECTIONAL_P_MAX``. Rather than widen the
    # window (which would force a fresh cohort-definition design and
    # risk re-introducing Berkson-shaped confounding the B-5 invariant
    # blocks), the engine emits this typed abstain so the Considered
    # section explains the hold honestly. Beauty path unchanged.
    SUPPLEMENT_CADENCE_OUTSIDE_WINDOW = "supplement_cadence_outside_window"
    # Sprint 7.5 Ticket T3: a Tier-C play whose base_rate prior carries
    # ``validation_status in {heuristic_unvalidated, placeholder}`` (per
    # ``PriorValidationStatus``) is routed to Considered with this typed
    # reason rather than being silently dropped or reusing
    # ``NO_MEASURED_SIGNAL`` (which has different upstream M3 semantics).
    # Surfaces only when ``ENGINE_V2_PRIORS_VALIDATION`` is ON; additive
    # within the Sprint 2 ``event_version=1`` schema freeze.
    PRIOR_UNVALIDATED = "prior_unvalidated"
    # Sprint 6.5 Ticket T4 — R1 window_corroboration. Multi-window evidence
    # disagrees: at least one non-primary window in the agreement set shows
    # an opposite-sign delta at p<0.10 vs. the primary window. The card is
    # routed to Considered with this typed reason rather than reusing
    # SIGNAL_INCONSISTENT_ACROSS_WINDOWS (different upstream semantics:
    # that code is set by directional-pathway sign-count minimums; this
    # code is set by the profile-driven R1 corroboration check that runs
    # on both directional AND prior-anchored pathways). Surfaces only
    # when ``ENGINE_V2_STORE_PROFILE`` is ON; additive within the
    # Sprint 2 ``event_version=1`` schema freeze.
    WINDOW_DISAGREEMENT = "window_disagreement"
    # Sprint 10 Ticket T3 — predictive-layer ML-fit gate dormant codes.
    # Dormant at S10 close; consumed at S13 audience-ranking integration.
    # Distinguishes per-play ML-fit-level cold-start/refusal from the
    # existing :data:`COLD_START_INSUFFICIENT_DATA` (run-level data-quality
    # cold start). Additive within ``event_version=1`` (same Sprint 2 freeze
    # carve-out precedent as :data:`SUPPLEMENT_CADENCE_OUTSIDE_WINDOW`,
    # :data:`PRIOR_UNVALIDATED`, :data:`WINDOW_DISAGREEMENT`).
    #
    # Precedence (DS-locked 2026-05-26): the four orthogonal demotion gates
    # rank as (1) audience-floor → (2) cohort p-value → (3) prior-validation
    # → (4) ML-fit. ML-fit is LOWEST precedence: when MODEL_FIT_REFUSED or
    # MODEL_FIT_INSUFFICIENT_DATA is the only failing gate, the card stays
    # in Recommended Now / Recommended Experiment and the audience-ranking
    # strategy silently falls back through the chain
    # ``BG/NBD → CF → survival → RFM → recency``. ML-fit NEVER demotes a
    # card between slate roles. Only gates (1)-(3) route to Considered.
    #
    # Q-S13-4 LOCK (DS verdict 2026-05-28, S13 plan review §B): ML-fit
    # ReasonCodes (MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED) emit
    # ONLY on ``PlayCard.model_card_ref.fit_warnings`` per PlayCard.
    # **NEVER on ``RejectedPlay.reason_code``** — ML-fit never demotes
    # between slate roles; only gates (1)-(3) above route to Considered.
    # The ``fit_warnings`` channel (S13.6-T4: typed
    # ``List[FitWarning]`` with ``level: FitWarningLevel`` ∈
    # {PROVISIONAL_SELECTED, MODEL_FIT_INSUFFICIENT_DATA,
    # MODEL_FIT_REFUSED} + ``substrate: str``; pre-T4 the same grammar
    # lived as ``List[str]`` of the form ``"{LEVEL}:{substrate}"``) is
    # the single audit surface for ML-fit outcomes. If a card stays in
    # Recommended/Experiment, there is no ``RejectedPlay`` to attach
    # to — emission on ``RejectedPlay.reason_code`` is structurally
    # incoherent and would conceptually re-open a fourth demote channel
    # (threatening Pivot 7 single-demote-channel). Test contract pin:
    # ``tests/test_s13_ml_fit_never_demotes.py`` (runtime) +
    # ``tests/test_reason_code_precedence_invariant.py::test_model_fit_codes_not_emitted_in_s10_close``
    # (AST). Producer at S13-T2 in the consumer-wiring pass
    # (src/predictive/consumer_wiring.py).
    MODEL_FIT_INSUFFICIENT_DATA = "model_fit_insufficient_data"
    MODEL_FIT_REFUSED = "model_fit_refused"


class AbstainMode(str, Enum):
    """Typed abstain-mode tag (Sprint 7.5 Ticket T3).

    The legacy ``Abstain.reason`` string carries a merchant-readable
    sentence. The new ``Abstain.mode`` field carries a typed enum so
    downstream consumers (Klaviyo agent, calibration jobs, reviewers)
    can branch on the abstain *cause* without parsing prose.

    Values:

    - ``SOFT_AWAITING_MEASUREMENT``: ABSTAIN_SOFT because no measured /
      directional play cleared evidence gates this month. Validated
      priors exist; the store simply lacks store-specific evidence yet.
      This is the default mapping for any pre-T3 ABSTAIN_SOFT run.
    - ``SOFT_PRIOR_UNVALIDATED``: ABSTAIN_SOFT specifically because
      every surfaceable play's prior is unvalidated under the T3
      refusal rule (no Tier-B builder fired AND every Tier-C play got
      its base_rate prior refused). Emitted only when
      ``ENGINE_V2_PRIORS_VALIDATION`` is ON.
    - ``SOFT_BELOW_FLOOR``: ABSTAIN_SOFT where the dominant typed hold
      class is :data:`ReasonCode.MATERIALITY_BELOW_FLOOR` (sized
      impact does not clear the scale-aware materiality floor). Sprint
      7 Ticket T4 — emitted only when ``ENGINE_V2_ABSTAIN_4STATE`` is
      ON.
    - ``SOFT_AUDIENCE_TOO_SMALL``: ABSTAIN_SOFT where the dominant
      typed hold class is :data:`ReasonCode.AUDIENCE_TOO_SMALL`
      (audience size below the per-play minimum-cell floor). Sprint 7
      Ticket T4 — emitted only when ``ENGINE_V2_ABSTAIN_4STATE`` is
      ON.

    Additive within ``event_version=1`` (Sprint 2 freeze carve-out for
    typed enum additions; same precedent as
    :data:`ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW`).
    """

    SOFT_AWAITING_MEASUREMENT = "soft_awaiting_measurement"
    SOFT_PRIOR_UNVALIDATED = "soft_prior_unvalidated"
    SOFT_BELOW_FLOOR = "soft_below_floor"
    SOFT_AUDIENCE_TOO_SMALL = "soft_audience_too_small"


class DataQualityFlag(str, Enum):
    """Anomaly detector codes. Populated by ``src.anomaly`` (M1 T1.2).

    Sprint 1 Ticket B-7 (post-6B restructured plan): ``VERTICAL_NOT_SUPPORTED``
    is set by the vertical hard-refuse guard at engine entry
    (``src.vertical_guard``) when the resolved ``vertical_mode`` is outside
    the supported set ``{beauty, supplements, mixed}``. It is a HARD flag
    (see ``src.decide._HARD_DQ_FLAGS``) and reuses the existing
    ``data_quality_flags`` slot — the EngineRun schema is not extended.
    """

    BFCM_OVERLAP = "bfcm_overlap"
    POST_PROMO_WINDOW = "post_promo_window"
    REFUND_STORM = "refund_storm"
    TEST_ORDER_ANOMALY = "test_order_anomaly"
    INSUFFICIENT_CLEAN_HISTORY = "insufficient_clean_history"
    VERTICAL_NOT_SUPPORTED = "vertical_not_supported"
    # Sprint 5 Ticket S5-T3 (resolves KI-22): advisory flag — the
    # within-window repeat-rate metric is structurally incoherent when
    # the median customer reorder gap exceeds the active primary
    # window. Set by ``src.main.run`` AFTER ``decide()`` based on the
    # pure helper in ``src.cadence_coherence``. This is an ADVISORY
    # (non-HARD) flag and is intentionally absent from
    # ``src.decide._HARD_DQ_FLAGS`` — it must NOT push the run to
    # ``ABSTAIN_HARD``. Additive within Sprint 2 ``event_version=1``
    # freeze (additive enum values on ``data_quality_flags`` are the
    # carve-out documented in the implementation plan §11).
    METRIC_INCOHERENT_FOR_CADENCE = "metric_incoherent_for_cadence"


class ObservationClassification(str, Enum):
    """Per-observation classification per PM-Q2 ``Observation`` schema."""

    MOVED = "moved"
    HELD = "held"
    ANOMALOUS = "anomalous"


class RevenueRangeSource(str, Enum):
    """Provenance of the revenue range estimate (PM-Q3)."""

    STORE_OBSERVED = "store_observed"
    VERTICAL_PRIOR = "vertical_prior"
    BLEND = "blend"


class WouldBeMeasuredBy(str, Enum):
    """Outcome metric a Recommended Experiment card would be measured against.

    Phase 6A Ticket A2: this enum is purely additive. The field
    ``PlayCard.would_be_measured_by`` exists, defaults to ``None``, and
    round-trips through ``to_dict`` / ``from_dict``. NO producer in the
    engine populates this field in Ticket A2 — it becomes load-bearing in
    later Phase 6A tickets (priors-metadata wiring + Recommended Experiment
    selection).

    Hard contract (per ``agent_outputs/campaign-slate-contract-final.md``):

    - Free-text rejection is enforced by the standard enum constructor
      (``WouldBeMeasuredBy(<str>)`` raises ``ValueError`` for non-members).
    - String values are UPPER_SNAKE_CASE and equal to the member name. This
      matches the casing used in priors-metadata YAML and the contract-final
      spec; it deliberately differs from the lowercase convention of
      ``EvidenceClass`` and ``DecisionState`` because outcome-metric names
      are externally referenced in priors and history files.
    - The merchant never sees the raw enum string. The renderer maps each
      value to a short merchant-readable phrase (e.g.
      ``EMAIL_ATTRIBUTED_REVENUE_IN_7D`` ->
      "We will measure email-attributed revenue in 7 days.").
    """

    INCREMENTAL_ORDERS_IN_14D = "INCREMENTAL_ORDERS_IN_14D"
    EMAIL_ATTRIBUTED_REVENUE_IN_7D = "EMAIL_ATTRIBUTED_REVENUE_IN_7D"
    REPEAT_PURCHASE_IN_30D = "REPEAT_PURCHASE_IN_30D"
    # Sprint 6 Ticket T1 — winback_dormant_cohort builder (additive).
    LAPSED_REACTIVATION_IN_30D = "LAPSED_REACTIVATION_IN_30D"
    # Sprint 6 Ticket T3 — replenishment_due builder (additive).
    REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW = "REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW"
    # Sprint 7 priors-wiring (2026-05-20) — additive within event_version=1
    # per A2 precedent. Authored alongside the priors.yaml metadata blocks
    # for ``discount_dependency_hygiene`` and ``aov_lift_via_threshold_bundle``
    # (cross-pinned via tests/test_s7_priors_enum_cross_pin.py). The S7-T1 /
    # S7-T3 builder + measurement dispatch that would populate these values
    # on real cards is OUT OF SCOPE for the priors-wiring ticket; the enum
    # surface is consumer-dormant until those builders ship.
    DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D = (
        "DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D"
    )
    AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D = (
        "AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D"
    )
    # Sprint 7 Ticket T2 — cohort_journey_first_to_second builder (additive
    # within event_version=1 per A2 precedent). The Tier-B builder anchors
    # on the validated_external ``first_to_second_purchase.base_rate`` prior
    # (S7.5-T2 promotion, effective_n=156110, wildcard vertical) via
    # ``measurement_builder._PRIOR_ANCHORED["cohort_journey_first_to_second"]``.
    # Authored alongside the S7-T2 builder; cross-pinned via
    # ``tests/test_s7_t2_cohort_journey_first_to_second_builder.py``.
    FIRST_TO_SECOND_PURCHASE_IN_30D = "FIRST_TO_SECOND_PURCHASE_IN_30D"


class MechanismType(str, Enum):
    """S13.6-T6 — DS-locked closed enum (DS §(d), founder approved
    Option C 2026-05-31).

    Per DS plan-review verdict §(d) + DS adjudication 2026-05-31 on the
    T6 halt (audit lesson: the original brief framed T6 as a retype of
    ``PlayCard.mechanism`` which did NOT exist; the actual prose field
    survives on ``RejectedPlay.mechanism`` only). 10 members are
    audit-locked from current emission across the ``_PRIOR_ANCHORED``
    registry + Tier-B builders + legacy plays. Zero unmapped emission
    sites confirmed by the T6 audit.

    Per founder lock-in #4 (2026-05-30): "Engine ships structured atoms
    only; narration agents render copy." This enum is the typed
    substrate; narration agents render merchant-facing copy from
    ``MechanismIntent.type`` + ``MechanismIntent.parameters``.

    String values equal member names (UPPER_SNAKE_CASE) per the
    :class:`WouldBeMeasuredBy` precedent. Free-text rejection is
    enforced by the standard enum constructor
    (``MechanismType(<str>)`` raises ``ValueError`` for non-members).
    """

    WINBACK_REACTIVATION_EMAIL = "WINBACK_REACTIVATION_EMAIL"
    FIRST_TO_SECOND_NUDGE = "FIRST_TO_SECOND_NUDGE"
    THRESHOLD_BUNDLE_OFFER = "THRESHOLD_BUNDLE_OFFER"
    DISCOUNT_DEPENDENCY_HYGIENE = "DISCOUNT_DEPENDENCY_HYGIENE"
    REPLENISHMENT_REMINDER = "REPLENISHMENT_REMINDER"
    BESTSELLER_AMPLIFY = "BESTSELLER_AMPLIFY"
    CATEGORY_EXPANSION = "CATEGORY_EXPANSION"
    SUBSCRIPTION_NUDGE = "SUBSCRIPTION_NUDGE"
    ROUTINE_BUILDER = "ROUTINE_BUILDER"
    LOOKALIKE_HIGH_VALUE_PROSPECT = "LOOKALIKE_HIGH_VALUE_PROSPECT"


class EvidenceSourceChip(str, Enum):
    """Sprint 8 Ticket T1 — typed evidence-source chip (Tier A/B/C/D vocabulary).

    Additional trust-surface dimension on :class:`PlayCard`, additive within
    ``event_version=1``. Does NOT replace the existing :class:`EvidenceClass`
    enum — :class:`EvidenceClass` (``measured`` / ``directional`` / ``targeting``
    / ``weak``) tags the *internal evidence class* used by the M3/M4 statistical
    machinery; :class:`EvidenceSourceChip` tags the *epistemic provenance*
    surfaced merchant-facing (eventual frontend / operator inspection of
    ``engine_run.json``).

    The four values match the Tier A/B/C/D chip names documented in
    ``ENGINE_OVERVIEW.md`` §8 ("Evidence tiers — the redesign's core
    vocabulary") and ``ARCHITECTURE_PLAN.md`` Part I §A ("The Four Evidence
    Tiers (formal spec)"):

    - :attr:`STORE_MEASURED` — Tier A. Effect estimate is grounded in a
      within-store causal comparison (Phase-9 outcome confirmation or
      DiD/RD with documented identifying assumptions). Zero Tier-A plays
      exist today; Phase 9 unlocks the first.
    - :attr:`STORE_OBSERVED` — Tier B. A store-observed metric moved in
      a direction that justifies an intervention; the metric is not
      itself the causal estimate of the intervention's lift. The four
      currently-wired Tier-B builders (winback_dormant_cohort,
      discount_dependency_hygiene, cohort_journey_first_to_second,
      aov_lift_via_threshold_bundle) surface under this chip when
      ``ENGINE_V2_TIER_CHIP`` is ON.
    - :attr:`INDUSTRY_PRIOR` — Tier C. Audience is store-specific; the
      expected behavior is calibrated by an industry/expert prior in
      ``config/priors.yaml``. NO producer populates this in S8-T1 (Tier-C
      population is follow-up work; S8-T1 scope caps at the 4 wired
      Tier-B builders per IM plan + DS verdict).
    - :attr:`OBSERVATIONAL` — Tier D. Audience identified, no effect
      claim. NO producer populates this in S8-T1.

    Casing convention: UPPER_SNAKE for both member name and string value,
    mirroring :class:`WouldBeMeasuredBy` (which uses UPPER_SNAKE because
    its values are externally referenced in priors.yaml and history files;
    same precedent applies here — these chip names are externally
    referenced in ``ENGINE_OVERVIEW.md`` §8 and the architectural plan).
    The renderer is responsible for any merchant-readable mapping
    ("Store-measured" / "Store-observed" / "Industry prior" /
    "Observational"); the data layer never emits a pre-formatted display
    string.

    Flag gate: populated only when ``ENGINE_V2_TIER_CHIP`` is ON. Default
    OFF at the T1 commit; T1.5 atomically flips ON with a fixture re-pin
    per S7.6 atomic-flip discipline (memory.md S7.6 T*N*.5 pattern). Flag
    OFF means every PlayCard's ``evidence_source = None`` and the M0 +
    Beauty + Supplements pinned fixtures stay byte-identical.
    """

    STORE_MEASURED = "STORE_MEASURED"
    STORE_OBSERVED = "STORE_OBSERVED"
    INDUSTRY_PRIOR = "INDUSTRY_PRIOR"
    OBSERVATIONAL = "OBSERVATIONAL"


# ---------------------------------------------------------------------------
# Sprint 8 Ticket T2 — typed Sensitivity dataclass (forward-declared here so
# PlayCard can reference the type; the full block sits after RevenueRange
# below to keep the sub-record ordering — see the @dataclass Sensitivity
# definition further down). This Enum block is the natural insertion point
# for the EvidenceSourceChip enum (S8-T1); the Sensitivity dataclass lives
# alongside the other sub-records (Measurement / RevenueRange / etc.) per
# the existing module convention.
# ---------------------------------------------------------------------------


class WindowCorroboration(str, Enum):
    """Sprint 6.5 Ticket T4 (R1) — multi-window evidence corroboration.

    Populated on ``PlayCard.measurement.window_corroboration`` by both
    ``build_directional_play_card`` and ``build_prior_anchored_play_card``
    when ``ENGINE_V2_STORE_PROFILE`` is ON. ``None`` (default) under
    flag-OFF so the M0 / Beauty / supplements pinned fixtures stay
    byte-identical.

    The check is sign-only at MVP (magnitude-ratio band deferred): for
    each non-primary window in ``profile.measurement.agreement_windows``,
    compare the cohort's signed delta vs. the primary window's signed
    delta at p<0.10.

    Values:

    - ``CORROBORATED``: both non-primary windows show same-sign delta
      as the primary window at p<0.10 each. ``decide.py`` bumps
      ``confidence_label`` one notch within the MEASURED/DIRECTIONAL
      tier ceiling (Targeting never bumps).
    - ``CONTRADICTED``: at least one non-primary window shows an
      opposite-sign delta at p<0.10. ``decide.py`` routes the card to
      Considered with :data:`ReasonCode.WINDOW_DISAGREEMENT`.
    - ``NEUTRAL``: low data on agreement windows, mixed signs, or no
      significant deltas. No behavior change.
    """

    CORROBORATED = "CORROBORATED"
    NEUTRAL = "NEUTRAL"
    CONTRADICTED = "CONTRADICTED"


class DistributionKind(str, Enum):
    """S-FE-descriptive-distribution (L-EV-19) — closed kind enum for the
    four distributional plays.

    Each member names the observed quantity the audience builder computes
    and that :class:`DescriptiveDistribution` carries out as a binned
    series:

    - ``DORMANCY_DAYS`` — winback_dormant_cohort: days-since-last-order for
      the dormant repeat-buyer cohort. Marker = dormancy_window upper bound
      (e.g. 45) — a real builder-derived value.
    - ``AOV_GAP`` — aov_lift_via_threshold_bundle: per-customer typical AOV
      (the band the threshold sits above). Marker = the resolved AOV
      threshold when one was derived; ``None`` (suppressed-marker) when the
      threshold parameter is None/TODO(S14).
    - ``REORDER_GAP_DAYS`` — replenishment_due: per-customer days-since-last
      in-class purchase (the reorder-gap the cadence window brackets).
      Marker = replenishment_window_days when a real value exists; ``None``
      today (TODO(S14)).
    - ``DISCOUNT_FRACTION`` — discount_dependency_hygiene: per-customer
      fraction of historical orders that carried a discount. Marker =
      target_discount_share when a real value exists; ``None`` today
      (TODO(S14)).

    Closed set per the L-EV-19 lock — no generic fallback member (the four
    distributional plays are the complete beta set; new kinds require a DS
    re-review). String values equal member names (UPPER_SNAKE_CASE) per the
    :class:`WouldBeMeasuredBy` / :class:`MechanismType` precedent.
    """

    DORMANCY_DAYS = "DORMANCY_DAYS"
    AOV_GAP = "AOV_GAP"
    REORDER_GAP_DAYS = "REORDER_GAP_DAYS"
    DISCOUNT_FRACTION = "DISCOUNT_FRACTION"


class DescriptiveDistributionSuppressionReason(str, Enum):
    """S-FE-descriptive-distribution (L-EV-20) — RULE-A paired null-reason
    for :class:`DescriptiveDistribution`.

    Paired with :attr:`DescriptiveDistribution.suppressed`: when
    ``suppressed=True`` a member MUST be set; when ``suppressed=False`` it
    MUST be ``None`` (RevenueRange precedent). An absent / empty /
    integrity-failed source series is typed, never silently omitted
    (L-EV-20).

    Members:

    - ``SOURCE_SERIES_EMPTY`` — the builder produced no observed values to
      bin (empty cohort / no resolvable per-customer series). The
      descriptive viz suppresses; the typed reason renders, never a
      fabricated distribution.
    - ``SOURCE_SERIES_ABSENT`` — the builder did not stash a series for
      this play (the discarded-series wiring did not run on this path).
    - ``INTEGRITY_FAILED`` — the observed series failed the data-integrity
      check (e.g. all non-finite values). DESCRIPTIVE gating is a
      data-integrity check, NOT a forward-precision check (L-EV-13/14).
    """

    SOURCE_SERIES_EMPTY = "source_series_empty"
    SOURCE_SERIES_ABSENT = "source_series_absent"
    INTEGRITY_FAILED = "integrity_failed"


# ---------------------------------------------------------------------------
# Sub-records
# ---------------------------------------------------------------------------


@dataclass
class DataWindow:
    """``EngineRun.data_window``."""

    # null_reason_exempt: structural schema slot; absence means the
    # upstream data_window resolver had no primary window to declare
    # (cold-start / insufficient-history). Not a suppression decision.
    primary_window: Optional[str] = None  # e.g., "L28"
    available_windows: List[str] = field(default_factory=list)
    # null_reason_exempt: structural schema slot; mirrors
    # ``primary_window`` exemption rationale above.
    anchor_quality: Optional[str] = None  # "good" | "noisy" | "insufficient"


@dataclass
class Abstain:
    """``EngineRun.abstain`` — decision_state + human-readable reason.

    M1: defaults to ``state=PUBLISH`` because no decision logic ships yet.
    M5/M7 wire the actual state machine.
    """

    state: DecisionState = DecisionState.PUBLISH
    # S13.6-T1a (Option D, founder + DS approved 2026-05-30): the legacy
    # ``reason: Optional[str]`` slot has been stripped per Pivot 2
    # (engine emits typed contract surface only; downstream narrates).
    # The typed ``mode`` enum below replaces the freeform reason string
    # for downstream agent consumption.
    # Sprint 7.5 Ticket T3: typed abstain-mode tag (additive, optional).
    # ``None`` for ABSTAIN_HARD / PUBLISH and for pre-T3 ABSTAIN_SOFT runs
    # to preserve the M0 byte-identical contract until T3.5 flips the
    # ``ENGINE_V2_PRIORS_VALIDATION`` flag. The field round-trips through
    # :func:`_from_dict_abstain` (it is omitted from serialization when
    # ``None`` because the dataclass-asdict default emits ``None``; the
    # fixture-rendered briefing does not surface the field).
    # null_reason_exempt: default-None when ENGINE_V2_ABSTAIN_4STATE is
    # OFF (and on PUBLISH / ABSTAIN_HARD where there is no mode tag).
    # Sprint 7.5 T3 / Sprint 7 T4: populated only when the abstain
    # state is SOFT and the relevant flag (ENGINE_V2_PRIORS_VALIDATION
    # for SOFT_PRIOR_UNVALIDATED; ENGINE_V2_ABSTAIN_4STATE for
    # SOFT_BELOW_FLOOR / SOFT_AUDIENCE_TOO_SMALL) is ON.
    mode: Optional[AbstainMode] = None


@dataclass
class Observation:
    """One typed fact about state-of-store. Built by ``src.state_of_store``.

    Phase 6B Stop-Coding-Line Task 2: ``current``, ``prior``, and
    ``delta_pct`` carry the raw typed numerics. ``delta_pct`` is a raw
    ratio (e.g. ``0.066`` for a +6.6% move), NOT a percentage string.
    Renderers / downstream agents are responsible for any string
    formatting (percent signs, ``"vs prior"`` framing).

    Phase 6B Stop-Coding-Line Task 4: ``anomaly_flags``,
    ``n_days_observed``, and ``n_days_expected`` reserve the typed slot
    for window-anomaly metadata. Detection is a Phase 6C concern; today
    these default to safe values (empty list / zero) so agents can read
    them but cannot misinterpret them as a real signal.

    Sprint 13.6 Ticket T1b (Option D, founder + DS approved 2026-05-31):
    ``text: str`` was stripped from this dataclass per Pivot 2. The
    engine emits only typed numerics on the contract surface; the
    state-of-store paragraph in :mod:`src.storytelling_v2` is now
    synthesized from ``supporting_metric`` + ``classification`` +
    ``delta_pct`` + ``anomaly_flags`` at render time.
    """

    # null_reason_exempt: structural schema slot — absence means the
    # state-of-store builder had no metric label for this Observation
    # (legacy / cold-start paths). Not a suppression decision.
    supporting_metric: Optional[str] = None
    # null_reason_exempt: structural schema slot — paired with
    # ``current`` / ``prior`` via the typed numerics below.
    change_magnitude: Optional[float] = None
    classification: ObservationClassification = ObservationClassification.HELD
    # Phase 6B Stop-Coding-Line Task 2: raw typed numerics behind ``text``.
    # ``delta_pct`` is a raw ratio (0.066 = +6.6%), never a "%" string.
    # null_reason_exempt: typed numerics behind the (now stripped)
    # ``text`` slot; absence means the observation has no prior-vs-
    # current pair to compare (e.g. first-month cold-start).
    current: Optional[float] = None
    # null_reason_exempt: see ``current`` annotation above.
    prior: Optional[float] = None
    # null_reason_exempt: see ``current`` annotation above.
    delta_pct: Optional[float] = None
    # Phase 6B Stop-Coding-Line Task 4: reserved typed slot for window
    # anomaly metadata. Detector is stubbed for now (returns []); the
    # Phase 6C anomaly module will populate these.
    anomaly_flags: List[str] = field(default_factory=list)
    n_days_observed: int = 0
    n_days_expected: int = 0


@dataclass
class WatchedSignal:
    """One ``EngineRun.watching`` entry."""

    metric: str
    # null_reason_exempt: WatchedSignal is a forward-watch entry, not a
    # measurement claim — absent values mean the watcher has no
    # current/prior data yet (cold-start watch).
    current: Optional[float] = None
    # null_reason_exempt: see ``current`` annotation above.
    prior: Optional[float] = None
    # null_reason_exempt: structural schema slot.
    trend: Optional[str] = None  # "up" | "down" | "flat"
    # null_reason_exempt: structural schema slot (free-text label).
    threshold_to_act: Optional[str] = None


@dataclass
class DescriptiveDistribution:
    """S-FE-descriptive-distribution (L-EV-19 / L-EV-20) — a generic,
    DESCRIPTIVE-ONLY binned series for the four distributional plays.

    A richer rendering of M4 (audience) — NOT a 10th evidence member; the
    closed 9-member set (L-EV-2) is preserved. The engine emits the binned
    observed series only; it emits NO chart-spec (no axis / color / type)
    per L-EV-3 (the Stop-Coding Line). Frontend renders pixels from the
    typed series.

    **DESCRIPTIVE-ONLY (L-EV-20, structural):** the atom carries observed
    counts (``counts``) over value bins (``bins``) plus an OPTIONAL real
    threshold/window ``marker``. It carries NO projected rate, NO dollar
    figure, and NO lift — an inferential overlay on a descriptive
    distribution is a REJECT-class breach. There is deliberately no dollar
    field on this atom (contrast :class:`NonLiftAtom`, which is the only
    addressable-dollar surface).

    Fields:

    - ``kind`` — :class:`DistributionKind` (closed): which observed quantity
      this series describes.
    - ``bins`` — bin edges of the observed value, ascending. Length
      ``len(counts) + 1`` (standard histogram-edge convention: ``counts[i]``
      is the count of observations in ``[bins[i], bins[i+1])``, with the
      final bin closed on the right to capture the max).
    - ``counts`` — observed count per bin. Non-negative integers;
      ``len(counts) == len(bins) - 1``.
    - ``marker`` — the window/threshold to annotate (e.g. the dormancy
      window upper bound, the AOV threshold) when a real builder-derived
      value exists; ``None`` when the underlying scalar parameter is
      ``None`` / ``TODO(S14)`` (``threshold_aov`` / ``replenishment_window_days``
      / ``target_discount_share``). A ``None`` marker is the typed-absence
      of the annotation line, NOT a suppression of the whole series
      (L-EV-20) — the descriptive series still renders.
    - ``suppressed`` + ``suppression_reason`` — RULE-A paired typed
      absence (RevenueRange precedent). When the source series is
      empty / absent / integrity-failed, ``suppressed=True`` and a
      :class:`DescriptiveDistributionSuppressionReason` member is set, and
      ``bins`` / ``counts`` are empty. Invariant: ``suppressed=True`` ⇔
      ``suppression_reason is set``; ``suppressed=False`` ⇔
      ``suppression_reason is None``.
    """

    kind: DistributionKind
    bins: List[float] = field(default_factory=list)
    counts: List[int] = field(default_factory=list)
    # null_reason_exempt: ``marker`` is a DESCRIPTIVE nullable parameter,
    # NOT a suppression decision (L-EV-20). It is the real threshold/window
    # annotation when the builder has one (e.g. dormancy window upper
    # bound); ``None`` when the underlying scalar parameter is None/TODO(S14)
    # (threshold_aov / replenishment_window_days / target_discount_share).
    # A None marker still renders the descriptive series — only the
    # annotation line is absent. Whole-series suppression is carried by the
    # paired ``suppressed`` + ``suppression_reason`` fields below.
    marker: Optional[float] = None
    suppressed: bool = False
    # S-FE-descriptive-distribution: paired null-reason for ``suppressed``
    # (RevenueRange precedent). Closed-set enum; set iff ``suppressed=True``.
    suppression_reason: Optional[DescriptiveDistributionSuppressionReason] = None


def build_descriptive_distribution(
    kind: "DistributionKind",
    series: Optional[List[float]],
    *,
    marker: Optional[float] = None,
    bin_edges: Optional[List[float]] = None,
) -> DescriptiveDistribution:
    """Pure helper — bin an observed series into a typed
    :class:`DescriptiveDistribution` (L-EV-19 / L-EV-20).

    DESCRIPTIVE-ONLY: this only counts observations into bins. It never
    computes a rate, a dollar value, or a lift. It is the single binning
    seam so the producer (``measurement_builder``) stays free of histogram
    logic and the audience builders stay pure.

    Suppression discipline (L-EV-20): a ``None`` / empty series, or a
    series with no finite values, yields ``suppressed=True`` with a typed
    :class:`DescriptiveDistributionSuppressionReason` and empty
    ``bins`` / ``counts`` — never a fabricated distribution.

    Binning convention (chosen, fixed):

    - When ``bin_edges`` is provided (the per-kind fixed edges the producer
      passes), observations are counted into ``[edges[i], edges[i+1])`` with
      the final bin closed on the right. Out-of-range low values fall in the
      first bin; out-of-range high values fall in the last bin (clamped) so
      no observation is silently dropped.
    - When ``bin_edges`` is omitted, a degenerate single-bin
      ``[min, max]`` envelope is emitted (used only when a caller wants the
      raw envelope; producers pass explicit edges).

    Marker passes through unchanged (may be ``None`` per L-EV-20).
    """

    if series is None:
        return DescriptiveDistribution(
            kind=kind,
            bins=[],
            counts=[],
            marker=marker,
            suppressed=True,
            suppression_reason=DescriptiveDistributionSuppressionReason.SOURCE_SERIES_ABSENT,
        )

    finite = [float(x) for x in series if isinstance(x, (int, float)) and _is_finite(x)]
    if not finite:
        reason = (
            DescriptiveDistributionSuppressionReason.SOURCE_SERIES_EMPTY
            if len(list(series)) == 0
            else DescriptiveDistributionSuppressionReason.INTEGRITY_FAILED
        )
        return DescriptiveDistribution(
            kind=kind,
            bins=[],
            counts=[],
            marker=marker,
            suppressed=True,
            suppression_reason=reason,
        )

    if bin_edges and len(bin_edges) >= 2:
        edges = [float(e) for e in bin_edges]
    else:
        lo = min(finite)
        hi = max(finite)
        if hi <= lo:
            hi = lo + 1.0
        edges = [lo, hi]

    n_bins = len(edges) - 1
    counts = [0] * n_bins
    for x in finite:
        # Clamp to range so out-of-range observations land in the edge bins
        # rather than being dropped (descriptive integrity — every observed
        # value is counted).
        if x <= edges[0]:
            idx = 0
        elif x >= edges[-1]:
            idx = n_bins - 1
        else:
            idx = 0
            for i in range(n_bins):
                if edges[i] <= x < edges[i + 1]:
                    idx = i
                    break
        counts[idx] += 1

    return DescriptiveDistribution(
        kind=kind,
        bins=edges,
        counts=counts,
        marker=marker,
        suppressed=False,
        suppression_reason=None,
    )


def _is_finite(x: Any) -> bool:
    """True for a finite real number (rejects NaN / +-inf). Local helper so
    the binning seam does not import numpy/math at module scope."""
    try:
        import math

        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


@dataclass
class Audience:
    """``PlayCard.audience``."""

    # null_reason_exempt: structural schema slot — absence means the
    # audience-builder did not surface a canonical id (legacy / cold-
    # start). Not a suppression decision.
    id: Optional[str] = None
    # null_reason_exempt: structural schema slot.
    definition: Optional[str] = None
    # null_reason_exempt: structural schema slot — absent on cold-start
    # paths before any audience build runs.
    size: Optional[int] = None
    # null_reason_exempt: structural schema slot — paired with
    # ``size``; absence is a missing-denominator condition (no scale
    # estimate yet), not a suppression decision.
    fraction_of_base: Optional[float] = None
    overlap_with: List[str] = field(default_factory=list)
    # S-FE-descriptive-distribution (L-EV-19; FOUNDER-AUTHORIZED 2026-06-02;
    # schema 2.0.0 -> 2.1.0): a richer rendering of M4 (audience) for the 4
    # distributional plays — the binned observed series the audience
    # builders already compute and currently discard. NOT a 10th evidence
    # member (L-EV-2 closed set preserved). Populated by
    # ``measurement_builder.build_prior_anchored_play_card`` for the 4
    # distributional play_ids (winback_dormant_cohort / replenishment_due /
    # discount_dependency_hygiene / aov_lift_via_threshold_bundle); ``None``
    # for every other play (legacy / scalar-story plays). Absence-typing for
    # an absent/empty/integrity-failed series lives INSIDE the atom via its
    # paired ``suppressed`` + ``suppression_reason`` fields (RevenueRange /
    # PlayCard.revenue_range precedent), so the outer Optional is exempt.
    # null_reason_exempt: suppression-typing lives INSIDE the
    # DescriptiveDistribution atom (``suppressed`` + ``suppression_reason``,
    # RULE-A paired); the outer ``descriptive_distribution is None`` is the
    # structural "this play is not a distributional play" case (mirrors the
    # PlayCard.revenue_range exemption, where suppression lives on the inner
    # RevenueRange).
    descriptive_distribution: Optional[DescriptiveDistribution] = None


@dataclass
class Measurement:
    """``PlayCard.measurement`` — null for ``evidence_class == targeting``.

    ``p_internal`` and ``ci_internal`` are persisted but NEVER rendered.
    They are the M9 ML-readiness hook.
    """

    # null_reason_exempt: Measurement is structurally None for the
    # entire dataclass when ``PlayCard.evidence_class == TARGETING``
    # (hard contract invariant; see PlayCard docstring). Within a
    # populated Measurement, missing inner fields encode "the M4
    # populator had no value to plumb" and are NOT suppression
    # decisions on their own — the PlayCard slate-routing reads the
    # outer ``measurement is None`` check, not per-inner-field nulls.
    metric: Optional[str] = None
    # null_reason_exempt: see ``metric`` annotation above.
    observed_effect: Optional[float] = None
    # null_reason_exempt: see ``metric`` annotation above.
    n: Optional[int] = None
    # null_reason_exempt: see ``metric`` annotation above.
    primary_window: Optional[str] = None
    # null_reason_exempt: see ``metric`` annotation above.
    consistency_across_windows: Optional[int] = None
    # null_reason_exempt: ``p_internal`` / ``ci_internal`` are the M9
    # ML-readiness hook (never rendered); absence is structural.
    p_internal: Optional[float] = None
    # null_reason_exempt: see ``p_internal`` annotation above.
    ci_internal: Optional[List[float]] = None  # [low, high]
    # Sprint 6.5 Ticket T4 (R1): multi-window evidence corroboration.
    # ``None`` (default) under ``ENGINE_V2_STORE_PROFILE`` flag-OFF so
    # M0 / Beauty / supplements pinned fixtures stay byte-identical.
    # Populated by both directional + prior-anchored pathways when the
    # flag is ON. ``decide.py`` reads the typed value:
    # CORROBORATED → confidence bump; CONTRADICTED → Considered with
    # WINDOW_DISAGREEMENT; NEUTRAL → no-op.
    # null_reason_exempt: default-None when ENGINE_V2_STORE_PROFILE is
    # OFF (Sprint 6.5 T4 R1 — see the field docstring above). Under
    # flag ON, None means the multi-window corroboration check did not
    # surface a comparable second window — no suppression decision.
    window_corroboration: Optional[WindowCorroboration] = None


# =============================================================================
# NULL-REASON ENUM REGISTRY — RULE A absence-of-data taxonomy
# Every Optional field on a contract dataclass that is not null_reason_exempt
# must be paired with one of the enums below. Agents: read this block to find
# every absence-reason type in the contract surface. Producers: wrap existing
# string literals at the seam — no producer rewrites per DS Q1.
#
# SHIPPED (S13.6-T7a):
#   RevenueRangeSuppressionReason  → RevenueRange.suppression_reason
#                                     (paired with RevenueRange.suppressed bool;
#                                      invariant: suppressed=True ⟺ reason set)
#   MonthDeltaNullReason           → EngineRun.month_2_delta_null_reason
#                                     (paired with EngineRun.month_2_delta:
#                                      Optional[MonthDelta])
#   PredictedSegmentNullReason     → PredictedSegment.segment_name_null_reason
#                                     (inner-field shape; paired with
#                                      PredictedSegment.segment_name: Optional[str])
#
# SHIPPED (S13.7-T1):
#   CustomerIdsNullReason          → declared enum for the audience CSV resolver
#                                     side-effect path. PlayCard.audience.customer_ids
#                                     field pairing is DEFERRED to S13.7-T7b (field
#                                     is not yet on the Audience dataclass — schema
#                                     v2.0.0 is frozen; the enum is declared here per
#                                     the registry-test fail-forward contract so the
#                                     test can assert it EXISTS as of S13.7-T1).
#
# SHIPPED (S13.7-T7b):
#   StoreProfileNullReason         → EngineRun.store_profile_null_reason
#                                     (paired with EngineRun.store_profile:
#                                      Optional[StoreProfile]; closes KI-NEW-AA)
#   ModelCardAbsenceReason         → EngineRun.predictive_models absence
#                                     (Dict field — enum declared for agent reference;
#                                      no paired _null_reason field; dict key absence
#                                      is self-documenting)
#   CohortDiagnosticsAbsenceReason → EngineRun.cohort_diagnostics absence
#                                     (Dict field — enum declared for agent reference;
#                                      no paired _null_reason field; dict key absence
#                                      is self-documenting)
#
# SHIPPED (S-FE-descriptive-distribution; schema 2.0.0 -> 2.1.0):
#   DescriptiveDistributionSuppressionReason
#                                  → DescriptiveDistribution.suppression_reason
#                                     (paired with DescriptiveDistribution.suppressed
#                                      bool at the seam, RevenueRange precedent;
#                                      invariant: suppressed=True ⟺ reason set). The
#                                      outer Audience.descriptive_distribution Optional
#                                      is null_reason_exempt — absence-typing lives
#                                      inside the atom (mirrors PlayCard.revenue_range).
#
# Coverage test: tests/test_null_reason_registry.py (S13.6-T7.5)
# AST sweep test: tests/test_s13_6_t7a_no_silent_nulls.py (S13.6-T7a)
# =============================================================================


class RevenueRangeSuppressionReason(str, Enum):
    """RULE A null-reason enum (DS adjudication 2026-06-01, expanded
    from §(e) 3-member sketch to match producer surface byte-for-byte).

    Values match the legacy producer string literals so T7a wraps the
    existing strings at the seam without producer rewrites (DS Q1).
    Paired with :attr:`RevenueRange.suppressed`: when ``suppressed=True``
    a member MUST be set; when ``suppressed=False`` it MUST be ``None``.
    """

    COLD_START_NO_N_OBSERVED = "cold_start"
    AUDIENCE_ZERO = "audience_zero"
    AOV_ZERO = "aov_zero"
    OBSERVED_EFFECT_INVALID = "observed_effect_invalid"
    NO_PRIOR_BASE_RATE = "no_prior_base_rate"
    PRIOR_UNVALIDATED = "prior_unvalidated"
    AOV_UNAVAILABLE = "aov_unavailable"
    DIRECTIONAL_NO_INTERVENTION_EFFECT = "directional_no_intervention_effect"
    EXPERIMENT_NO_CALIBRATED_LIFT = "experiment_no_calibrated_lift"


@dataclass
class RevenueRange:
    """``PlayCard.revenue_range`` — sized in M6.

    ``suppressed=True`` ⇒ renderer hides $; shows audience + AOV only.

    S13.6-T7a (DS adjudication 2026-06-01 + founder approved
    2026-06-01): ``suppression_reason`` is the paired closed-set null-
    reason enum per the revised flag-aware RULE A. Invariant:
    ``suppressed=True`` ⇔ ``suppression_reason is set``;
    ``suppressed=False`` ⇔ ``suppression_reason is None``.
    """

    # null_reason_exempt: p10/p50/p90/source absence is encoded by the
    # paired ``suppressed`` flag + ``suppression_reason`` enum below;
    # when ``suppressed=False`` the values are non-None by construction
    # of size_play / measurement_builder. The null-reason discipline is
    # expressed on ``suppression_reason`` (the seam field).
    p10: Optional[float] = None
    # null_reason_exempt: paired with ``suppression_reason`` via the
    # ``suppressed`` boolean — see ``p10`` annotation above.
    p50: Optional[float] = None
    # null_reason_exempt: paired with ``suppression_reason`` via the
    # ``suppressed`` boolean — see ``p10`` annotation above.
    p90: Optional[float] = None
    # null_reason_exempt: paired with ``suppression_reason`` via the
    # ``suppressed`` boolean — see ``p10`` annotation above.
    source: Optional[RevenueRangeSource] = None
    drivers: List[Dict[str, Any]] = field(default_factory=list)
    suppressed: bool = False
    # S13.6-T7a: paired null-reason for ``suppressed``. Closed-set
    # enum (9 members) wraps the existing producer string literals at
    # the seam per DS Q1 — NO producer rewrites. See
    # :class:`RevenueRangeSuppressionReason` for member semantics.
    suppression_reason: Optional[RevenueRangeSuppressionReason] = None


@dataclass
class Sensitivity:
    """Sprint 8 Ticket T2 — typed one-up-one-down scenario block on
    ``PlayCard.sensitivity``.

    Additive within ``event_version=1``; default ``None`` on
    :class:`PlayCard` keeps every existing fixture byte-identical when
    ``ENGINE_V2_SENSITIVITY`` is OFF. Populated by
    :func:`measurement_builder.build_prior_anchored_play_card` on the 4
    wired Tier-B builders (winback_dormant_cohort,
    discount_dependency_hygiene, cohort_journey_first_to_second,
    aov_lift_via_threshold_bundle) when the flag is ON, provided the
    PlayCard's ``revenue_range.source == BLEND`` (i.e. a validated,
    non-suppressed range exists to perturb). Suppressed-range cards,
    targeting cards, and prior-unvalidated cards leave the block as
    ``None`` per IM plan Part B S8-T2 acceptance criterion 2.

    Each scenario is a :class:`RevenueRange` produced by re-running the
    same ``audience * posterior * aov`` math the live ``revenue_range``
    uses, with **one** input perturbed — observed_n halved/doubled
    (re-blended via :func:`sizing.bayesian_blend`) or prior point value
    shifted -25%/+25% (re-blended). No parallel sizing math; the helper
    in :mod:`src.sizing` re-uses the same ``bayesian_blend`` and the
    same revenue formula so the Sensitivity surface stays honest as the
    EB blend layer evolves at S8-T3.

    Fields:

    - ``scenario_observed_n_halved`` — re-blend at ``n_observed // 2``;
      shows how a less-confident store signal would shift the posterior.
    - ``scenario_observed_n_doubled`` — re-blend at ``n_observed * 2``;
      shows how a more-confident store signal would shift the posterior.
    - ``scenario_prior_shifted_down`` — re-blend at ``prior_value * 0.75``;
      shows how a 25% lower prior anchor would shift the posterior.
    - ``scenario_prior_shifted_up`` — re-blend at ``prior_value * 1.25``;
      shows how a 25% higher prior anchor would shift the posterior.

    Each scenario is itself an :class:`Optional[RevenueRange]` so the
    helper can return ``None`` on degenerate inputs (e.g.
    ``n_observed == 0`` halves to 0; ``prior_value == 0`` shift is a
    no-op) without polluting the JSON shape with malformed envelopes.

    ``pseudo_n_used`` records the per-status / profile-capped pseudo_n
    that the live posterior used. Surfaced so a reviewer auditing the
    block can reproduce the blend without re-deriving it from
    drivers[*].blend_provenance.

    ``notes`` is a small free-text list (rarely populated) — reserved
    for documenting any per-scenario degeneracy (e.g.
    ``["observed_n=0; halved scenario suppressed"]``). Renderers must
    treat it as optional / debug-only.

    Casing convention: the field on :class:`PlayCard` is
    ``sensitivity`` (snake_case, matching every other PlayCard field).
    The dataclass name :class:`Sensitivity` is CamelCase per the
    existing dataclass convention in this module.
    """

    # null_reason_exempt: default-None on degenerate inputs (n_observed
    # == 0 halves to 0; prior_value == 0 shift is a no-op) per the
    # docstring above — the helper returns None rather than emitting a
    # malformed envelope. Not a suppression decision; the live
    # ``revenue_range`` already carries its own ``suppression_reason``.
    scenario_observed_n_halved: Optional["RevenueRange"] = None
    # null_reason_exempt: see ``scenario_observed_n_halved`` annotation.
    scenario_observed_n_doubled: Optional["RevenueRange"] = None
    # null_reason_exempt: see ``scenario_observed_n_halved`` annotation.
    scenario_prior_shifted_down: Optional["RevenueRange"] = None
    # null_reason_exempt: see ``scenario_observed_n_halved`` annotation.
    scenario_prior_shifted_up: Optional["RevenueRange"] = None
    pseudo_n_used: int = 0
    notes: List[str] = field(default_factory=list)


@dataclass
class Provenance:
    """Sprint 8 Ticket T3 — typed empirical-Bayes blend audit object on
    ``PlayCard.provenance``.

    THIRD and final S8 additive PlayCard field (chip at S8-T1, sensitivity
    at S8-T2, provenance this commit) per DS verdict 2026-05-24 §5
    invariant 12. Additive within ``event_version=1``; default ``None`` on
    :class:`PlayCard` keeps every existing fixture byte-identical when
    ``ENGINE_V2_EB_BLEND`` is OFF.

    **What it is:** A documented audit-surface that records the exact
    inputs to the live Bayesian blend — which prior the engine consumed,
    which validation_status it carried, what pseudo_N was actually used
    (after the per-status cap + optional store-profile lowering), how many
    store observations entered the blend, and the resulting prior/observed
    weights. Lets a reviewer reproduce the live posterior without re-
    deriving it from ``drivers[*].blend_provenance``.

    **What it is NOT:** It is not the blend math. The math already ships
    at :func:`src.sizing.bayesian_blend` (S7.5-T3) and is consumed live by
    the 4 wired Tier-B builders today. S8-T3 formalizes the audit contract;
    the math is unchanged. Pinned-fixture byte-identity at flag OFF
    verifies this.

    Population gate (mirrors :class:`Sensitivity`): populated by
    :func:`measurement_builder.build_prior_anchored_play_card` on the 4
    wired Tier-B builders when ``ENGINE_V2_EB_BLEND`` is ON AND the card's
    ``revenue_range.source == BLEND`` AND ``not revenue_range.suppressed``.
    Suppressed cards, targeting cards, and prior-unvalidated cards
    (``HEURISTIC_UNVALIDATED`` / ``PLACEHOLDER`` — DS verdict §5
    invariant 2 refusal) leave the field ``None``: there is no audit
    object to emit because no blend happened.

    Fields:

    - ``prior_play_id``: the ``play_id`` under which the prior is authored
      in ``config/priors.yaml`` (e.g. ``"winback_21_45"``). May differ
      from the ``PlayCard.play_id`` (e.g. the
      ``cohort_journey_first_to_second`` card anchors on the
      ``first_to_second_purchase`` prior).
    - ``prior_key``: the prior sub-key consumed (e.g. ``"base_rate"``).
    - ``validation_status``: the prior's :class:`PriorValidationStatus`
      string value (``"validated_external"`` / ``"validated_internal"`` /
      ``"elicited_expert"``). Refused statuses
      (``"heuristic_unvalidated"`` / ``"placeholder"``) never appear here
      because the gate above leaves provenance ``None``.
    - ``pseudo_n_used``: the effective pseudo_N that the live posterior
      actually used. Equals ``min(pseudo_n_cap, store_profile_default)``
      per :func:`src.sizing.effective_pseudo_n`. Per DS verdict §5
      invariant 5 (pin), MUST NOT exceed ``pseudo_n_cap``.
    - ``pseudo_n_cap``: the per-status cap from
      :data:`src.sizing.PSEUDO_N_BY_STATUS` (30 / 15 / 10 for
      ``VALIDATED_EXTERNAL`` / ``VALIDATED_INTERNAL`` /
      ``ELICITED_EXPERT``). DS-locked through S14.
    - ``observed_n``: the store observation count that entered the blend.
      0 for the cold-start path (posterior collapses to prior).
    - ``weight_observed``: ``observed_n / (observed_n + pseudo_n_used)``.
      Range [0.0, 1.0]. Equals 0.0 when ``observed_n == 0`` (cold-start).
    - ``weight_prior``: ``pseudo_n_used / (observed_n + pseudo_n_used)``.
      Range [0.0, 1.0]. ``weight_observed + weight_prior == 1.0`` always
      (pinned by test). Pathological case (both zero) collapses to 0.5 /
      0.5 per :func:`bayesian_blend`'s arithmetic-mean fallback.
    - ``prior_source``: the prior's ``source_artifact`` if set, else the
      ``source_class`` (free-text). Documents the provenance source the
      reviewer should pull up to audit the prior itself.
    - ``notes``: small free-text list (rarely populated) for documenting
      blend-specific edge cases (e.g. cold-start, profile-lowered
      pseudo_n). Renderers must treat as optional / debug-only.

    Casing convention: dataclass name ``Provenance`` is CamelCase;
    instance field ``provenance`` is snake_case (matches every other
    PlayCard field). The audit string values inside the dataclass
    (``validation_status``) preserve the priors.yaml lowercase casing.

    DS verdict 2026-05-24 references:
      §5 invariant 1  — ``PSEUDO_N_BY_STATUS`` is the only pseudo_N source.
      §5 invariant 2  — HEURISTIC_UNVALIDATED + PLACEHOLDER refusal.
      §5 invariant 5  — no new ``Prior.pseudo_N`` per-prior override.
      §5 invariant 9  — reuse existing ``blend`` ``RevenueRange.source``.
      §5 invariant 12 — S8 PlayCard additive surface caps at 3 fields.
      §5 invariant 16 — harness parametrize row added for this flag.
    """

    prior_play_id: str = ""
    prior_key: str = ""
    validation_status: str = ""
    pseudo_n_used: int = 0
    pseudo_n_cap: int = 0
    observed_n: int = 0
    weight_observed: float = 0.0
    weight_prior: float = 0.0
    prior_source: str = ""
    notes: List[str] = field(default_factory=list)


@dataclass
class Inventory:
    """``PlayCard.inventory`` — null if N/A. M5 inventory gate populates it."""

    skus: List[str] = field(default_factory=list)
    # null_reason_exempt: default-None when INVENTORY_GATE_ENABLED is
    # OFF or no inventory SKUs were resolved for the play (structural).
    days_of_cover: Optional[float] = None
    # null_reason_exempt: see ``days_of_cover`` annotation above.
    gate_passed: Optional[bool] = None


@dataclass
class Conflicts:
    """``PlayCard.conflicts`` — populated by M5 cannibalization gate."""

    cannibalized_by: List[str] = field(default_factory=list)
    # null_reason_exempt: default-None when
    # CANNIBALIZATION_GATE_ENABLED is OFF or no overlap pair was
    # surfaced (structural — empty ``cannibalized_by`` carries the
    # absence at the list level).
    audience_overlap_pct: Optional[float] = None


@dataclass
class LaunchWindow:
    """``PlayCard.launch_window`` — advisory copy, not gating."""

    # null_reason_exempt: advisory copy (not gating per docstring);
    # absence means no recommended window was surfaced.
    recommended: Optional[str] = None
    # null_reason_exempt: see ``recommended`` annotation above.
    reason: Optional[str] = None


@dataclass
class NonLiftAtom:
    """Addressable opportunity (NOT lift, NOT p50, NOT forecast).

    Wrapping these numerics in a NonLiftAtom expresses the semantic
    constraint AT THE TYPE — schema consumers see ``NonLiftAtom``, not a
    raw float with a "please don't narrate as lift" sticker.

    Per DS R1 (S13.6-T3, 2026-05-30) + founder approval 2026-05-30.
    Source of the constraint: ``OpportunityContext`` previously carried
    an in-code comment block warning "NOT projected lift / NOT p50 / NOT
    forecast"; now expressed structurally at the field type.

    Fields:
        value: ``audience_size * aov_used`` — the multiplicative addressable
            order value. NEVER a forecast, NEVER a probability-weighted
            number, NEVER a causal claim.
        semantic: closed-set Literal ``"addressable_opportunity"`` — the
            ONLY acceptable value. Assemblers / agents validate against it.
        aov_used: the dollar-AOV the engine multiplied against the
            audience_size (provenance documented on the enclosing
            ``OpportunityContext.aov_window`` + ``aov_source`` fields).
        monthly_revenue_estimate: typed equivalent of ``value`` under the
            contract-final agent-facing key name; equals ``value`` by
            construction.
    """

    value: float
    semantic: Literal["addressable_opportunity"]
    aov_used: float
    monthly_revenue_estimate: float


@dataclass
class OpportunityContext:
    """Phase 5.1 follow-up: addressable opportunity context.

    Surfaced ONLY on cards where ``revenue_range.suppressed == True`` and a
    defensible recent AOV is available.

    S13.6-T3 (DS R1, founder approved 2026-05-30) restructure:
    - The four monetary/addressable-opportunity numerics (``value``,
      ``semantic``, ``aov_used``, ``monthly_revenue_estimate``) now live
      inside the typed ``non_lift: NonLiftAtom`` wrapper. The constraint
      is expressed AT THE TYPE — narration agents that read the JSON
      shape see ``NonLiftAtom``, not a raw float.
    - DUPLICATES stripped: ``aov`` (replaced by ``non_lift.aov_used`` —
      more explicit about provenance) and ``addressable_value`` (replaced
      by ``non_lift.value`` / ``non_lift.monthly_revenue_estimate`` — the
      latter is the actual semantic).
    - Non-monetary fields (``audience_size``, ``aov_window``,
      ``aov_source``) remain at the OpportunityContext top level.
    - The prior in-code "NOT projected lift / NOT p50 / NOT forecast"
      comment block is removed: the constraint is now structural.
    """

    audience_size: int
    non_lift: NonLiftAtom
    aov_window: str = "L28"
    aov_source: str = "store_observed"


@dataclass
class MechanismIntent:
    """S13.6-T6 — typed mechanism atom (DS §(d) + Option C 2026-05-31).

    Replaces engine-authored mechanism prose with a structured atom:

    - **ADDED** on :class:`PlayCard.mechanism_intent` as new scaffolding
      for downstream narration agents (additive within v2.0.0 contract
      freeze per founder lock-in #3).
    - **RETYPED** on :class:`RejectedPlay.mechanism` from
      ``Optional[str]`` (the field T1a's prose-strip missed by
      accident). Completion of T1a discipline.

    Per founder lock-in #4 (2026-05-30): "Engine ships structured atoms
    only; narration agents render copy." The engine emits ``type +
    parameters``; narration agents render merchant-facing prose.

    Per-type parameters shape spec lands at S13.7-T3
    (``docs/mechanism_contract.md``). For T6:

    - **5 spec'd types** carry DS §(d) parameter dicts (sourced from
      :data:`src.measurement_builder._PRIOR_ANCHORED` registry
      constants where applicable):
      ``WINBACK_REACTIVATION_EMAIL``, ``FIRST_TO_SECOND_NUDGE``,
      ``THRESHOLD_BUNDLE_OFFER``, ``DISCOUNT_DEPENDENCY_HYGIENE``,
      ``REPLENISHMENT_REMINDER``.
    - **4 Tier-B types** + ``LOOKALIKE_HIGH_VALUE_PROSPECT`` carry
      ``parameters={}`` per DS §(d) acceptance: "Tier-B types:
      parameters empty dict acceptable for v2.0.0; flesh out at S14+."

    Note on field name: DS §(d) verdict picked ``type`` (NOT
    ``mechanism_type``) — followed verbatim. JSON serializes as
    ``{"type": "<MEMBER_NAME>", "parameters": {...}}``.
    """

    type: MechanismType
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictedSegment:
    """ML-derived per-audience modal-segment summary.

    Reserved at Sprint 6 Ticket T1 (forward-scaffolded as ``notes``-only
    slot); extended at Sprint 13 Ticket T2 with the actual modal-segment
    payload populated from the per-store RFM parquet artifact.

    Population (T2 consumer-wiring pass behind
    ``ENGINE_V2_PLAY_PREDICTED_SEGMENT``):

    - ``segment_name``: most-frequent RFM ``segment_name`` among the
      audience's customer set (1-of-11 from
      :data:`src.predictive.rfm.SEGMENT_LTV_RANK_ORDER`). **Modal-segment
      stability floor (DS-LOCKED §D.4):** suppressed to ``None`` when
      ``n_audience < 50`` OR ``audience_modal_share < 0.30``. Below
      either floor the ranking chain still proceeds; only this surfaced
      name suppresses.
    - ``audience_modal_share``: fraction of the audience in the modal
      segment (always populated when modal computation succeeded — the
      stability floor only suppresses ``segment_name``, NOT the audit
      counter).
    - ``n_audience``: audience size at evaluation (always populated when
      modal computation succeeded).
    - ``notes``: legacy free-text slot (S6 forward-scaffold; kept for
      back-compat round-trip).

    All four fields default to ``None`` so flag-OFF round-trip stays
    byte-identical to the S6 schema shape. Schema-additive within
    ``event_version=1`` (same additive precedent as
    :class:`Sensitivity` / :class:`Provenance`).
    """

    # S13.6-T7a: paired null-reason for ``segment_name`` (the INNER
    # field; the PredictedSegment wrapper itself stays populated under
    # D-S13-2 with audit fields ``audience_modal_share`` + ``n_audience``).
    # See :class:`PredictedSegmentNullReason` for member semantics.
    segment_name: Optional[str] = None
    # null_reason_exempt: ``audience_modal_share`` is an audit counter
    # always populated when modal computation succeeds (D-S13-2). When
    # the producer cannot compute (parquet missing / no intersection),
    # both ``audience_modal_share`` and ``n_audience`` are None and the
    # paired ``segment_name_null_reason`` below carries the reason.
    audience_modal_share: Optional[float] = None
    # null_reason_exempt: see ``audience_modal_share`` annotation above.
    n_audience: Optional[int] = None
    # null_reason_exempt: legacy S6 forward-scaffold debug slot; gated
    # at serialization time by INCLUDE_DEBUG_FIELDS (default OFF).
    notes: Optional[str] = None
    # S13.6-T7a (DS adjudication 2026-06-01): paired null-reason for
    # ``segment_name``. Inner-field shape — applies to
    # ``PredictedSegment.segment_name``, NOT to the wrapper
    # ``PlayCard.predicted_segment`` (which has its own null_reason
    # contract via the audit fields above per D-S13-2).
    segment_name_null_reason: Optional["PredictedSegmentNullReason"] = None


class PredictedSegmentNullReason(str, Enum):
    """RULE A null-reason enum (DS adjudication 2026-06-01).

    Inner-field shape — applies to :attr:`PredictedSegment.segment_name`
    (NOT to the wrapper :attr:`PlayCard.predicted_segment`). The wrapper
    stays populated (with audit fields ``audience_modal_share`` +
    ``n_audience``) under D-S13-2 modal-segment floor; only the inner
    ``segment_name`` is None when the floor doesn't clear.
    """

    MODAL_FLOOR_NOT_CLEARED = "modal_floor_not_cleared"
    PARQUET_MISSING = "parquet_missing"
    PARQUET_UNREADABLE = "parquet_unreadable"
    NO_AUDIENCE_INTERSECTION = "no_audience_intersection"


class CustomerIdsNullReason(str, Enum):
    """RULE A null-reason enum for audience customer-ID materialization.

    Declared at S13.7-T1 per the NULL-REASON ENUM REGISTRY block above.
    The ``PlayCard.audience.customer_ids`` field pairing is DEFERRED to
    S13.7-T7b (the Audience dataclass is not extended in this ticket;
    schema v2.0.0 is frozen). This enum is declared here so:

    1. The registry comment block above and ``test_null_reason_registry.py``
       can assert it EXISTS as of S13.7-T1 (fail-forward prompt pattern).
    2. ``src/audience_resolver.py`` can reference the typed vocabulary
       for the ``audience_materialization_status`` field in the upcoming
       S13.7-T2 manifest.

    The producer that sets ``AUDIENCE_RESOLVER_NOT_INVOKED`` is the
    ``materialize_audience_csvs`` function in
    ``src/audience_resolver.py`` when it runs but finds no PlayCards.
    ``SUBSTRATE_REFUSED`` is set when the RFM parquet is missing or
    unreadable and the resolver falls through to the empty-CSV path.
    """

    SUBSTRATE_REFUSED = "substrate_refused"
    AUDIENCE_RESOLVER_NOT_INVOKED = "audience_resolver_not_invoked"


class StoreProfileNullReason(str, Enum):
    """RULE A null-reason enum for EngineRun.store_profile (S13.7-T7b / KI-NEW-AA).

    Paired with :attr:`EngineRun.store_profile`: when ``store_profile is None``
    AND ``ENGINE_V2_STORE_PROFILE`` is ON, this enum documents why the profile
    was not populated. Invariant: when ``store_profile is None`` and flag is ON,
    ``store_profile_null_reason`` MUST be set; when ``store_profile`` is populated
    or flag is OFF, ``store_profile_null_reason`` MUST be ``None``.

    Members:

    - ``PROFILE_NOT_LOADED``: ``build_store_profile`` was attempted but raised an
      exception (e.g. missing data, unexpected format). The exception is logged
      as a warning at the orchestration callsite.
    - ``ONBOARDING_INCOMPLETE``: reserved for future use when the engine can
      distinguish an incomplete-onboarding state from a load failure. Currently
      not emitted by the producer; present as forward-compat per DS §(e).
      TODO(S14): distinguish ONBOARDING_INCOMPLETE from PROFILE_NOT_LOADED when
      the onboarding-state taxonomy is formalized.
    """

    PROFILE_NOT_LOADED = "profile_not_loaded"
    ONBOARDING_INCOMPLETE = "onboarding_incomplete"


class ModelCardAbsenceReason(str, Enum):
    """RULE A null-reason enum for EngineRun.predictive_models absence (S13.7-T7b).

    Dict field — enum declared for agent reference; no paired ``_null_reason``
    field on ``EngineRun`` (dict key absence is self-documenting per the
    DS T7b retraction of the Dict[k, AbsenceReason] pattern).

    When a model substrate is NOT present as a key in ``predictive_models``,
    the reason falls into one of these categories:

    - ``SUBSTRATE_NOT_RUN``: the relevant ENGINE_V2_ML_* flag is OFF, so
      the substrate was never attempted this run.
    - ``SUBSTRATE_REFUSED``: the substrate was attempted but refused to fit
      (e.g. ``ModelFitStatus.REFUSED``). The attempt is audited in ``ModelCard``
      with ``fit_status=REFUSED`` if a card was produced; absence means the
      attempt itself failed before producing a card.
    - ``INSUFFICIENT_DATA``: the substrate was attempted but the input data
      did not meet the minimum-N requirement to produce a card.
    """

    SUBSTRATE_NOT_RUN = "substrate_not_run"
    SUBSTRATE_REFUSED = "substrate_refused"
    INSUFFICIENT_DATA = "insufficient_data"


class CohortDiagnosticsAbsenceReason(str, Enum):
    """RULE A null-reason enum for EngineRun.cohort_diagnostics absence (S13.7-T7b).

    Dict field — enum declared for agent reference; no paired ``_null_reason``
    field on ``EngineRun`` (dict key absence is self-documenting per the
    DS T7b retraction of the Dict[k, AbsenceReason] pattern).

    When a cohort-aggregate diagnostic is NOT present as a key in
    ``cohort_diagnostics``, the reason falls into one of these categories:

    - ``INSUFFICIENT_COHORT_DEPTH``: the cohort did not meet the minimum
      observation depth for retention-curve fitting (e.g. too few months
      of order history to fit a reliable retention curve).
    - ``SUBSTRATE_REFUSED``: the retention-curve substrate was attempted
      but refused to fit (e.g. numpy bootstrap failed; data shape mismatch).
    """

    INSUFFICIENT_COHORT_DEPTH = "insufficient_cohort_depth"
    SUBSTRATE_REFUSED = "substrate_refused"


class FitWarningLevel(str, Enum):
    """Typed level for ML-fit-warning grammar (S13.6-T4 / D-S13-4).

    Closed set of 3 members; matches the LEVEL prefixes of the legacy
    ``"{LEVEL}:{substrate}"`` string grammar that lived in code comments
    only (DS §D.3 / §B.0). Serializes to its string value, identical to
    every other ``str, Enum`` in this module.
    """

    PROVISIONAL_SELECTED = "PROVISIONAL_SELECTED"
    MODEL_FIT_INSUFFICIENT_DATA = "MODEL_FIT_INSUFFICIENT_DATA"
    MODEL_FIT_REFUSED = "MODEL_FIT_REFUSED"


@dataclass
class FitWarning:
    """Typed grammar for ML-fit warnings (S13.6-T4 — DS-locked at D-S13-4).

    Replaces the string grammar ``"{LEVEL}:{substrate}"`` that lived in
    code comments only. The ``(level, substrate)`` pair is the structural
    expression of that grammar at the type system; downstream consumers
    read ``.level`` and ``.substrate`` rather than parsing colons.

    Per **Q-S13-4 LOCK** (DS verdict 2026-05-28, S13 plan review §B),
    these warnings emit ONLY on
    :attr:`PlayCard.model_card_ref.fit_warnings` and **NEVER on
    :attr:`RejectedPlay.reason_code`** — the ML-fit gate never demotes
    between slate roles. Production at
    :mod:`src.predictive.ranking_strategy` (rank_audience) and surfaced
    to PlayCard via :mod:`src.predictive.consumer_wiring`.

    Fields:

    - ``level``: closed-set :class:`FitWarningLevel` (3 members).
    - ``substrate``: substrate-name string (e.g. ``"bgnbd"``, ``"cf"``,
      ``"survival"``, ``"rfm"``, plus retention / gamma_gamma where the
      grammar extends). Lowercase by convention (matches the
      ``predictive_models`` dict keys).

    Per IM plan §5 T4 (S13.6) + founder-locked at
    ``docs/DECISIONS.md::D-S13-4``.
    """

    level: FitWarningLevel
    substrate: str


@dataclass
class ModelCardRef:
    """Audit reference to the ranking-strategy chain consumed for a PlayCard.

    Reserved at Sprint 6 Ticket T1 (forward-scaffolded as ``notes``-only
    slot); extended at Sprint 13 Ticket T2 with the actual chain-walk
    payload populated from :func:`src.predictive.ranking_strategy.rank_audience`.

    Population (T2 consumer-wiring pass behind
    ``ENGINE_V2_PLAY_PREDICTED_SEGMENT``):

    - ``strategy_used``: canonical uppercase strategy name selected by
      the chain — one of ``"BGNBD" | "CF" | "SURVIVAL" | "RFM" |
      "RECENCY"``. ``None`` only when the wiring pass did not run (flag
      OFF; default).
    - ``fit_status_chain``: ordered list of ``(substrate_name,
      fit_status_value)`` tuples for every position the chain walker
      visited (up to and including the selected substrate). The
      ``"recency"`` last-resort floor does NOT contribute (no
      ``predictive_models`` lookup for it).
    - ``fit_warnings``: operator-readable summary per the DS-LOCKED
      grammar (DS §D.3 / §B.0). **S13.6-T4 (D-S13-4 structural):** the
      historical ``List[str]`` shape with prefix
      ``"{LEVEL}:{substrate}"`` is replaced by the typed
      :class:`FitWarning` dataclass. Each entry carries
      ``level: FitWarningLevel`` (closed 3-member enum:
      ``PROVISIONAL_SELECTED`` / ``MODEL_FIT_INSUFFICIENT_DATA`` /
      ``MODEL_FIT_REFUSED``) and ``substrate: str``. **This remains
      the single audit surface for ML-fit outcomes per Q-S13-4 LOCK** —
      ML-fit ReasonCodes NEVER appear on ``RejectedPlay.reason_code``.
    - ``notes``: legacy free-text slot (S6 forward-scaffold; kept for
      back-compat round-trip).

    All fields default-empty so flag-OFF round-trip stays byte-identical
    to the S6 schema shape. Schema-additive within ``event_version=1``.
    """

    # null_reason_exempt: default-None when
    # ENGINE_V2_PLAY_PREDICTED_SEGMENT is OFF (S13-T2 consumer-wiring
    # pass did not run). Under flag ON, the chain walker always
    # selects a strategy (including the ``"RECENCY"`` last-resort
    # floor) — None is therefore unreachable on the flag-ON path.
    strategy_used: Optional[str] = None
    fit_status_chain: List[Tuple[str, str]] = field(default_factory=list)
    # S13.6-T4 (D-S13-4 structural): typed FitWarning grammar replaces
    # the legacy ``List[str]`` ``"{LEVEL}:{substrate}"`` shape. Q-S13-4
    # LOCK preserved — ML-fit warnings emit ONLY here, never on
    # ``RejectedPlay.reason_code``.
    fit_warnings: List[FitWarning] = field(default_factory=list)
    # null_reason_exempt: legacy S6 forward-scaffold debug slot; gated
    # at serialization time by INCLUDE_DEBUG_FIELDS (default OFF).
    notes: Optional[str] = None


@dataclass
class PlayCard:
    """One recommended play.

    Hard rule (M4+): ``evidence_class == "targeting"`` ⇒ ``measurement is None``.
    """

    play_id: str
    evidence_class: EvidenceClass = EvidenceClass.TARGETING
    # null_reason_exempt: structural — confidence label is computed
    # from ``evidence_class`` at the M7 seam; None on pre-M7 paths is
    # structural (not a suppression decision).
    confidence_label: Optional[str] = None  # merchant-facing: Strong / Emerging / Targeting
    # S13.6-T1a (Option D, founder + DS approved 2026-05-30):
    # ``recommendation_text`` and ``why_now`` (the engine-authored prose
    # slots) have been stripped per Pivot 2. Downstream narration agents
    # compose merchant-facing copy from the typed contract surface
    # (play_id, audience, measurement, mechanism via priors metadata,
    # blend provenance, confidence_label). The DECIDE-layer copy ladder
    # at decide.py was removed in the same atomic commit.
    # null_reason_exempt: structural sub-object; absence means the
    # audience builder did not surface a typed Audience for this play.
    audience: Optional[Audience] = None
    # null_reason_exempt: hard contract — ``evidence_class == TARGETING``
    # ⇒ ``measurement is None`` (M4+ invariant in module docstring).
    # This is the canonical null-encoding for the targeting case.
    measurement: Optional[Measurement] = None  # null for targeting
    # null_reason_exempt: structural sub-object; suppression encoding
    # lives INSIDE the RevenueRange via ``suppressed`` +
    # ``suppression_reason`` (S13.6-T7a paired field). The outer
    # ``revenue_range is None`` is the pre-sizing-step / non-sizable
    # case (the M6 sizer ran but produced no envelope).
    revenue_range: Optional[RevenueRange] = None
    # null_reason_exempt: structural sub-object; absence means the
    # inventory gate did not surface a typed Inventory for this play.
    inventory: Optional[Inventory] = None
    # null_reason_exempt: structural sub-object; absence means no
    # cannibalization conflict was surfaced for this play.
    conflicts: Optional[Conflicts] = None
    # null_reason_exempt: advisory copy (not gating); absence means no
    # launch-window guidance was surfaced for this play.
    launch_window: Optional[LaunchWindow] = None
    # null_reason_exempt: Phase 5.1 follow-up sub-object; absence
    # means no defensible AOV was available so the addressable-value
    # sentence is structurally omitted (renderer hides on None).
    opportunity_context: Optional[OpportunityContext] = None  # Phase 5.1 follow-up
    # Phase 6A Ticket A2 (additive, schema-only): outcome metric a future
    # Recommended Experiment card would be measured against. ``None`` for
    # every PlayCard built today; no producer populates this in Ticket A2.
    # Round-trips via the standard enum coercion path.
    # null_reason_exempt: default-None when this PlayCard is NOT a
    # Recommended Experiment (the field is populated only on
    # experiment cards per Phase 6A A2/A4 contract; structural absence
    # on Recommended Now + targeting cards).
    would_be_measured_by: Optional[WouldBeMeasuredBy] = None
    # S13.6-T2 (founder lock-in #6, 2026-05-30): ``klaviyo_brief_inputs``
    # field REMOVED ENTIRELY (no flag, no default-empty stub). Klaviyo
    # upload is manual post-approval per D-5 (PRODUCT.md). Re-addition
    # post-AWS-migration is out of v1 scope and would require explicit
    # founder + DS sign-off documented in PIVOTS.md. Legacy dicts carrying
    # a stale ``klaviyo_brief_inputs`` key round-trip via
    # ``_from_dict_play_card`` by dropping the key silently.
    # null_reason_exempt: structural — the receipts-ref pointer is
    # populated by the future receipts emitter (out of v1 scope).
    receipts_ref: Optional[str] = None
    # Sprint 6 Ticket T1 forward-scaffolding for the Sprint 10-13 ML
    # AUDIENCE layer. Both default to ``None``; no producer populates
    # them in S6. Schema-additive within ``event_version=1`` — the
    # ``asdict`` serializer emits ``None`` and the renderer never reads
    # these fields, so the M0 byte-identical contract is preserved.
    # null_reason_exempt: default-None when
    # ENGINE_V2_PLAY_PREDICTED_SEGMENT is OFF. Under flag-ON, the
    # ``PredictedSegment`` wrapper stays populated when computation
    # succeeds (audit fields per D-S13-2); inner ``segment_name``
    # carries its own paired ``segment_name_null_reason`` enum
    # (S13.6-T7a). The outer ``predicted_segment is None`` encodes
    # "consumer-wiring pass did not run on this card".
    predicted_segment: Optional[PredictedSegment] = None
    # null_reason_exempt: default-None when
    # ENGINE_V2_PLAY_PREDICTED_SEGMENT is OFF (consumer-wiring pass
    # did not run). Under flag ON, ModelCardRef populates on every
    # recommendation card per ``populate_play_card_consumers``.
    model_card_ref: Optional[ModelCardRef] = None
    # Sprint 8 Ticket T1 — typed evidence-source chip (Tier A/B/C/D
    # vocabulary). Additive within ``event_version=1``; default ``None``
    # keeps every existing fixture byte-identical when
    # ``ENGINE_V2_TIER_CHIP`` is OFF. Populated by
    # ``measurement_builder.build_prior_anchored_play_card`` on the 4
    # wired Tier-B builders (winback_dormant_cohort,
    # discount_dependency_hygiene, cohort_journey_first_to_second,
    # aov_lift_via_threshold_bundle) when the flag is ON. Tier-C/Tier-D
    # population is follow-up work (out of S8-T1 scope per DS verdict
    # §5 invariant 12). See :class:`EvidenceSourceChip` for the value
    # semantics + flag contract.
    # null_reason_exempt: default-None when ENGINE_V2_TIER_CHIP is OFF
    # OR on plays whose builder did not declare a tier chip (Tier-C /
    # Tier-D population is follow-up work per S8-T1 scope).
    evidence_source: Optional[EvidenceSourceChip] = None
    # Sprint 8 Ticket T2 — typed Sensitivity block (one-up-one-down
    # scenario perturbations of the live ``revenue_range``). Additive
    # within ``event_version=1``; default ``None`` keeps every existing
    # fixture byte-identical when ``ENGINE_V2_SENSITIVITY`` is OFF.
    # Populated by ``measurement_builder.build_prior_anchored_play_card``
    # on the 4 wired Tier-B builders (winback_dormant_cohort,
    # discount_dependency_hygiene, cohort_journey_first_to_second,
    # aov_lift_via_threshold_bundle) when the flag is ON AND the card's
    # ``revenue_range.source == BLEND`` (suppressed and prior-unvalidated
    # paths leave the field ``None`` per IM plan Part B S8-T2). See
    # :class:`Sensitivity` for the per-scenario semantics + flag contract.
    # Second of three S8 additive PlayCard fields (chip done at S8-T1,
    # sensitivity this commit, ``provenance`` pending at S8-T3) per DS
    # verdict 2026-05-24 §5 invariant 12.
    # null_reason_exempt: default-None when ENGINE_V2_SENSITIVITY is
    # OFF OR ``revenue_range.source != BLEND`` OR suppressed /
    # unvalidated paths (per IM plan Part B S8-T2). Suppression
    # encoding lives on ``revenue_range.suppression_reason``;
    # sensitivity is downstream of that and absent by construction.
    sensitivity: Optional[Sensitivity] = None
    # Sprint 8 Ticket T3 — typed Provenance audit object (third and final
    # S8 additive PlayCard field per DS verdict 2026-05-24 §5 invariant
    # 12). Additive within ``event_version=1``; default ``None`` keeps
    # every existing fixture byte-identical when ``ENGINE_V2_EB_BLEND``
    # is OFF. Populated by
    # ``measurement_builder.build_prior_anchored_play_card`` on the 4
    # wired Tier-B builders (winback_dormant_cohort,
    # discount_dependency_hygiene, cohort_journey_first_to_second,
    # aov_lift_via_threshold_bundle) when the flag is ON AND the card's
    # ``revenue_range.source == BLEND`` (suppressed and prior-unvalidated
    # paths leave the field ``None`` — per DS verdict §5 invariant 2,
    # HEURISTIC_UNVALIDATED + PLACEHOLDER are refusal, so no audit object
    # to emit). See :class:`Provenance` for field semantics + flag
    # contract.
    # null_reason_exempt: default-None when ENGINE_V2_EB_BLEND is OFF
    # OR ``revenue_range.source != BLEND`` OR suppressed / unvalidated
    # paths. Suppression encoding lives on
    # ``revenue_range.suppression_reason``; provenance is downstream
    # of the blend and absent by construction when no blend happened.
    provenance: Optional[Provenance] = None
    # S13.6-T6 (DS §(d) verdict + DS adjudication on T6 halt +
    # founder approved Option C 2026-05-31) — typed mechanism atom.
    # Additive within v2.0.0 contract freeze per founder lock-in #3.
    # Populated by ``src.decide._build_mechanism_intent(play_id)`` at
    # PlayCard assembly for the 9 mapped play_ids (5 spec'd types
    # carry DS §(d) parameter dicts; 4 Tier-B types + lookalike carry
    # empty ``parameters={}`` per DS §(d) acceptance). Returns ``None``
    # for any unmapped play_id (legacy plays without typed atom —
    # strict, do not invent). Pivot 2 reaffirmation: narration agents
    # read the typed atom from the contract, no longer need to
    # re-implement ``priors.yaml`` lookup. See :class:`MechanismIntent`
    # for shape + per-type parameters; storytelling_v2 consumer rewire
    # to read this field lands at S13.6-T8 (DS Q7 sequencing).
    # null_reason_exempt: None when play_id is not in
    # ``_PLAY_ID_TO_MECHANISM_TYPE`` (legacy unmapped plays); strict
    # — do not invent per S13.6-T6 / DS §(d) closed-enum lock.
    mechanism_intent: Optional[MechanismIntent] = None


@dataclass
class RejectedPlay:
    """One rejected candidate. Populated by M5 guardrails + M7 selection.

    Phase 6B Stop-Coding-Line Task 3: ``held_reason_detail`` carries the
    structured numeric context behind ``reason_code`` (e.g.
    ``{"observed": 312, "floor": 500}`` for an audience-below-floor hold).
    Optional — may be ``None`` for legacy producers that have not yet
    been wired to populate it. Downstream agents read both ``reason_code``
    (typed enum) and ``held_reason_detail`` (typed dict) to narrate the
    hold without hallucinating from the freeform ``reason_text`` string.
    """

    play_id: str
    reason_code: ReasonCode
    # S13.6-T1a (Option D, founder + DS approved 2026-05-30): the legacy
    # freeform prose slots (``reason_text``, ``evidence_snapshot``,
    # ``would_fire_if``) have been stripped per Pivot 2. Downstream
    # narration agents compose hold narration from the typed
    # ``reason_code`` enum plus the structured ``held_reason_detail``
    # dict. ``outcome_log.py`` synthesizes a textual ``reason_text``
    # locally at write time from those two typed inputs so the
    # already-written outcome-log JSON schema remains stable (D-2
    # forever-retention).
    # Phase 6B Stop-Coding-Line Task 3: structured numeric context for the
    # ``reason_code``. Renderers / agents read both the typed enum and
    # this dict to narrate the hold.
    # null_reason_exempt: structural — None for legacy producers that
    # have not yet been wired to populate the typed detail dict (per
    # docstring above). The typed ``reason_code`` enum carries the
    # hold reason; the dict carries optional numeric context only.
    held_reason_detail: Optional[Dict[str, Any]] = None
    # S6-T3.z: merchant-facing Considered surface render pass. All three
    # fields are Optional / default None so pre-T3.z payloads round-trip
    # unchanged and the renderer falls through to the pre-T3.z shape
    # (preserving M0 / Beauty / supplements byte-identity under flag OFF).
    # Schema-additive within ``event_version=1`` — no enum change, no
    # producer is forced to populate. T3.5 owns activation.
    # null_reason_exempt: structural — None on pre-T3.z payloads / on
    # producers not yet wired to populate the merchant-facing
    # Considered fields. Not a suppression decision.
    audience_size: Optional[int] = None
    # null_reason_exempt: see ``audience_size`` annotation above.
    audience_definition: Optional[str] = None
    # S13.6-T6 (DS §(d) verdict + founder approved Option C
    # 2026-05-31) — RETYPED from ``Optional[str]`` to
    # ``Optional[MechanismIntent]``. This field is the prose slot the
    # T1a Pivot-2 strip missed by accident; the T6 retype is the
    # natural completion of T1a discipline. Producer wiring: the 4
    # RejectedPlay emit sites in ``src/decide.py`` (assemble_considered
    # / WINDOW_DISAGREEMENT / PRIOR_UNVALIDATED /
    # SIGNAL_INCONSISTENT_ACROSS_WINDOWS) swap from
    # ``_surface_mechanism_for_play`` (returns YAML prose) to
    # ``_build_mechanism_intent`` (returns the typed atom).
    # Strict deserialization (T3/T4 precedent): legacy
    # ``mechanism: <prose string>`` shape on pre-T6 snapshots returns
    # ``None`` — NOT silently parsed. The storytelling_v2 consumer
    # rewire lands at S13.6-T8; T6 leaves a renderer-side
    # compatibility shim that falls back to ``_mechanism_for_play``
    # (priors.yaml lookup) when the field is a ``MechanismIntent``.
    # null_reason_exempt: None when play_id is not in
    # ``_PLAY_ID_TO_MECHANISM_TYPE`` (legacy unmapped plays); strict
    # — do not invent per S13.6-T6 / DS §(d) closed-enum lock. Legacy
    # ``mechanism: "<prose str>"`` snapshots also deserialize to None
    # (strict cutover, not silently re-parsed).
    mechanism: Optional[MechanismIntent] = None
    # S7.6-T5.6 (DS verdict 2026-05-23): preserves the Tier-B
    # prior-anchored discriminator across demote channels
    # (eligibility_gate / prior_unvalidated / window_disagreement) so
    # ``decide.py`` can partition reject streams into the
    # ``priority_prepend_rejects`` slot of ``assemble_considered`` and
    # protect Tier-B cards from the ``[:MAX_CONSIDERED_RENDERED]=6``
    # truncation regardless of which channel demoted them. Schema-additive
    # within ``event_version=1`` — default None, renderer ignores.
    # null_reason_exempt: structural — populated only on Tier-B
    # prior-anchored RejectedPlays per S7.6-T5.6 (preserves the
    # eligibility-gate discriminator across demote channels). None on
    # non-Tier-B rejects by construction.
    would_be_measured_by: Optional[WouldBeMeasuredBy] = None


@dataclass
class Scale:
    """``EngineRun.scale``."""

    # null_reason_exempt: structural — None on cold-start paths
    # before any monthly aggregate can be computed (not a suppression
    # decision).
    monthly_revenue: Optional[float] = None
    # null_reason_exempt: see ``monthly_revenue`` annotation above.
    customer_base_est: Optional[int] = None
    # null_reason_exempt: structural — materiality floor is derived
    # from ``monthly_revenue`` per the scale-aware ladder; None when
    # ``monthly_revenue`` is itself None.
    materiality_floor: Optional[float] = None


@dataclass
class BriefingMeta:
    """``EngineRun.briefing_meta``."""

    # null_reason_exempt: structural — populated from the merchant
    # ``CONFIDENCE_MODE`` env var; absent when no env is configured.
    confidence_mode: Optional[str] = None
    # null_reason_exempt: structural — vertical label sourced from the
    # ``VERTICAL_MODE`` env var / store profile.
    vertical: Optional[str] = None
    # null_reason_exempt: structural — sub-vertical refinement is
    # optional metadata.
    subvertical: Optional[str] = None
    # null_reason_exempt: structural — ``BUSINESS_STAGE`` env metadata.
    stage: Optional[str] = None
    # null_reason_exempt: structural — seasonality tag is advisory
    # metadata only.
    seasonality_tag: Optional[str] = None


class MonthDeltaNullReason(str, Enum):
    """RULE A null-reason enum (DS adjudication 2026-06-01, expanded
    from §(e) 3-member sketch to match the 4 None-paths in
    :func:`src.predictive.month_2_delta.detect_month_2_delta`).

    Paired with :attr:`EngineRun.month_2_delta` (the wrapper). Per
    DS adjudication, ``LINEAGE_CHANGED`` is forward-compat: S13-T3
    lineage-bump nulls the inner :attr:`MonthDelta.segment_shifts`
    field, NOT the wrapper. Reserved for a future ticket that promotes
    lineage-bump to whole-MonthDelta suppression.
    """

    NO_STORE_ID = "no_store_id"
    NO_PRIOR_RUN = "no_prior_run"
    ANCHOR_DATE_UNPARSEABLE = "anchor_date_unparseable"
    UNDER_21D_FLOOR = "under_21d_floor"
    # null_reason_exempt: LINEAGE_CHANGED is forward-compatible (DS
    # adjudication 2026-06-01). S13-T3 lineage-bump nulls
    # ``MonthDelta.segment_shifts`` (inner field), not the wrapper.
    LINEAGE_CHANGED = "lineage_changed"


@dataclass
class MonthDelta:
    """Substrate-state delta between the current run and a prior month-1 run.

    Sprint 13 Ticket T3 (Pivot 8 month-2-return). Populated by
    :func:`src.predictive.month_2_delta.detect_month_2_delta` when
    ``ENGINE_V2_MONTH_2_DELTA`` is ON AND a prior engine run exists for
    the same ``store_id`` AND the gap exceeds the 21-day floor
    (DS §D.2 LOCKED).

    This is a **substrate-state-delta**, NOT a realized-outcome delta
    (DS §G.2 load-bearing). For cold-start merchants, month-2-return
    value flows through the EB path (`n_observed` shift in
    ``bayesian_blend``), NOT through ML refit. ML refusal degrades
    silently within audience ranking.

    Fields:
      prior_run_id:
        ``EngineRun.run_id`` of the month-1 run being compared against.
      current_run_id:
        ``EngineRun.run_id`` of the current month-2 run.
      days_between:
        Wall-clock days between the prior run and the current run.
        Used to enforce the 21-day floor (DS §D.2 LOCKED — lineage-keyed,
        NOT wall-clock-gated on the calendar; the floor is on
        prior→current temporal distance).
      substrate_fit_status_changes:
        Mapping ``{substrate_name: (prior_status, current_status)}`` for
        every ML substrate observed (bgnbd, gamma_gamma, survival, cf,
        rfm, retention). Remains comparable across lineage bumps per
        DS §D.2 (substrate fits are not lineage-sensitive).
      segment_shifts:
        Optional mapping ``{customer_id: {"prior": str, "current": str}}``
        of per-customer RFM segment shifts. **None when
        ``prior_run.audience_definition_version !=
        current_run.audience_definition_version``** (DS §D.2 LOCKED):
        only customer-level segment shifts are lineage-sensitive.
        Populated only when the lineage key is stable.
      retention_ci_at_month_3_delta:
        Optional float; signed delta ``current_ci_width - prior_ci_width``
        for the retention curve's month-3 bootstrap CI. Remains
        comparable across lineage bumps per DS §D.2. ``None`` if either
        side lacks a retention substrate.
      notes:
        Operator-readable typed notes. Carries
        ``"lineage_changed_segment_shift_incomparable"`` when
        ``segment_shifts`` is suppressed by the D-1 lineage constraint.

    Schema-additive within ``event_version=1`` (no bump). The
    serializer emits a JSON-safe dict via ``_to_jsonable``; round-trips
    via :func:`_from_dict_month_delta`.
    """

    prior_run_id: str = ""
    current_run_id: str = ""
    days_between: int = 0
    substrate_fit_status_changes: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    # null_reason_exempt: D-S13-3 LOCKED — None when the D-1
    # audience_definition_version bumps between prior and current
    # runs (lineage-keyed suppression). The typed note
    # ``"lineage_changed_segment_shift_incomparable"`` on ``notes``
    # carries the operator-readable reason at the inner-field grain
    # — DS adjudication 2026-06-01 keeps this as an inner-list note
    # rather than a paired enum (LINEAGE_CHANGED is reserved as
    # forward-compat on MonthDeltaNullReason for a future ticket).
    segment_shifts: Optional[Dict[str, Dict[str, str]]] = None
    # null_reason_exempt: structural — None when either side lacks a
    # retention substrate (per docstring above). Substrate absence is
    # already encoded on ``substrate_fit_status_changes`` via the
    # ``ABSENT`` marker.
    retention_ci_at_month_3_delta: Optional[float] = None
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level EngineRun
# ---------------------------------------------------------------------------


@dataclass
class EngineRun:
    """The canonical engine output object.

    M1: produced via legacy adapter (``build_engine_run_from_legacy``).
    M7: produced directly by ``decide()``.
    """

    # null_reason_exempt: structural top-level identifier; absence
    # means the run-id generator has not assigned an id yet (pre-M1).
    run_id: Optional[str] = None
    # null_reason_exempt: structural — store_id resolver returns
    # ``"unknown"`` rather than None per S1-B4/S-1; None here is
    # pre-resolver legacy state only.
    store_id: Optional[str] = None
    # null_reason_exempt: structural top-level identifier — the anchor
    # date is set by the data-window resolver; absence is pre-resolver
    # legacy state only.
    anchor_date: Optional[str] = None  # ISO-8601 string
    # S13.6-T5 (founder lock-in #3, 2026-05-30): contract FROZEN at
    # ``2.x.x``. Bumped from ``"1.0.0"`` -> ``"2.0.0"`` at the S13.6
    # close (T1a..T4 contract-restructure bundle). See the CHANGELOG
    # block at the top of this module for the S8 -> S13.6 additive
    # growth history. Additive changes within ``2.x.x`` allowed;
    # breaking changes -> ``3.0.0``.
    # S-FE-descriptive-distribution (L-EV-19; FOUNDER-AUTHORIZED 2026-06-02):
    # ``"2.0.0"`` -> ``"2.1.0"`` — additive ``Audience.descriptive_distribution``
    # (paired RULE-A ``suppressed`` + ``suppression_reason`` on the atom).
    schema_version: str = "2.1.0"
    data_window: DataWindow = field(default_factory=DataWindow)
    cold_start: bool = False
    data_quality_flags: List[DataQualityFlag] = field(default_factory=list)
    abstain: Abstain = field(default_factory=Abstain)
    state_of_store: List[Observation] = field(default_factory=list)
    recommendations: List[PlayCard] = field(default_factory=list)
    # Sprint 6.5 Ticket T1 (additive, default ``None``): typed
    # ``StoreProfile`` slot. Populated when ``ENGINE_V2_STORE_PROFILE``
    # is ON; ``None`` when OFF and on pre-S6.5 fixtures. Schema-additive
    # within the ``event_version=1`` frozen contract.
    # S13.6-T2 (DS R6, founder + DS approved 2026-05-30): typed via the
    # canonical ``StoreProfile`` re-export at the top of this module.
    # S13.7-T7b: paired with ``store_profile_null_reason`` below per
    # revised RULE A. Flag-OFF → both fields stay ``None`` (exempt from
    # the paired-reason invariant; ``store_profile_null_reason`` must be
    # ``None`` when flag is OFF). Flag-ON + profile loaded → both ``None``.
    # Flag-ON + load failure → ``store_profile=None`` +
    # ``store_profile_null_reason=PROFILE_NOT_LOADED``.
    # null_reason_exempt: default-None when ENGINE_V2_STORE_PROFILE is OFF
    store_profile: Optional[StoreProfile] = None
    # S13.7-T7b (DS adjudication 2026-06-01 + founder approved 2026-06-01):
    # paired null-reason for ``store_profile`` per revised RULE A (closes
    # KI-NEW-AA). Invariant: when ``ENGINE_V2_STORE_PROFILE`` is ON and
    # ``store_profile is None``, this field MUST be set. When flag is OFF
    # or ``store_profile`` is populated, this field MUST be ``None``.
    # Producer wiring: ``src/main.py`` StoreProfile block sets
    # ``PROFILE_NOT_LOADED`` on exception; ``None`` on success.
    # TODO(S14): distinguish ``ONBOARDING_INCOMPLETE`` from
    # ``PROFILE_NOT_LOADED`` when the onboarding-state taxonomy is
    # formalized in the beta onboarding flow.
    store_profile_null_reason: Optional[StoreProfileNullReason] = None
    # Phase 6A Ticket A4 (additive, default empty): Recommended Experiment
    # cards. Populated only when ``ENGINE_V2_SLATE=true`` and the decide
    # layer is in the PUBLISH branch. ABSTAIN_SOFT and ABSTAIN_HARD always
    # produce ``[]`` here. Cards are TARGETING with suppressed
    # ``revenue_range`` and a populated ``would_be_measured_by`` enum.
    recommended_experiments: List[PlayCard] = field(default_factory=list)
    considered: List[RejectedPlay] = field(default_factory=list)
    watching: List[WatchedSignal] = field(default_factory=list)
    scale: Scale = field(default_factory=Scale)
    briefing_meta: BriefingMeta = field(default_factory=BriefingMeta)
    # S7.6-C1 (additive, founder-internal-only): counts entries silently
    # dropped by the ``[:MAX_CONSIDERED_RENDERED]`` truncation cap inside
    # ``decide.assemble_considered`` and
    # ``decide.populate_considered_from_candidates``. The single-
    # demote-channel invariant (DS-locked 2026-05-22) requires this to
    # stay 0 on pinned fixtures; CI invariant tests fail on regression.
    # NOT merchant copy — never rendered. Mirrors the ``cold_start: bool``
    # additive-scalar precedent; tolerated as missing by
    # ``_from_dict_engine_run`` so the Sprint 2 schema freeze contract
    # holds (additive with safe default; no event_version bump).
    considered_truncated_count: int = 0

    # Sprint 10 Ticket T1 (additive, default empty): typed slot for the
    # ML predictive layer's ``ModelCard`` instances, keyed by model name
    # (``"bgnbd"`` / ``"gamma_gamma"``). Populated only when the relevant
    # flag is ON (e.g. ``ENGINE_V2_ML_BGNBD``) AND a fit is attempted.
    # Flag-OFF default is ``{}`` so all S8-pinned fixtures round-trip
    # byte-identical (``_to_jsonable`` emits an empty dict). Operator-
    # only surface — NOT merchant-rendered (S10 is operator-only via
    # engine_run.json per IM plan §A.2 / DS verdict). Schema-additive
    # within the Sprint 2 ``event_version=1`` frozen contract; tolerated
    # as missing by ``_from_dict_engine_run`` so pre-S10 fixtures
    # round-trip with ``predictive_models={}``.
    # S13.6-T2 (DS R6, founder + DS approved 2026-05-30): typed via the
    # canonical ``ModelCard`` re-export at the top of this module. The
    # value type is the per-substrate ``ModelCard`` written by S10-T1
    # (BG/NBD), S11 (Gamma-Gamma / survival / CF / RFM).
    predictive_models: Dict[str, ModelCard] = field(default_factory=dict)

    # Sprint 12 Ticket T2 (additive, default empty): typed slot for
    # COHORT-AGGREGATE diagnostics (e.g. retention curves). Architecturally
    # distinct from ``predictive_models`` — that Dict is contractually a
    # per-customer-ranker shape (holdout_rank_spearman, c_index, top-K
    # recall, parquet artifacts). Cohort-aggregate diagnostics have no
    # held-out object and no per-customer parquet; forcing them into the
    # ranker Dict would invert its invariants (DS S12 plan review §C).
    # Populated only when the relevant flag is ON (e.g.
    # ``ENGINE_V2_ML_RETENTION``). Flag-OFF default ``{}`` keeps all
    # S8-pinned fixtures byte-identical (``_to_jsonable`` emits empty
    # dict). Operator-only surface — NOT merchant-rendered (S12 is
    # operator-only via engine_run.json; S13 wires consumers). Schema-
    # additive within the Sprint 2 ``event_version=1`` frozen contract;
    # tolerated as missing by ``_from_dict_engine_run`` so pre-S12
    # fixtures round-trip with ``cohort_diagnostics={}``.
    # S13.6-T2 (DS R6, founder + DS approved 2026-05-30): typed via the
    # canonical ``RetentionCard`` re-export at the top of this module.
    # Architecturally distinct from ``predictive_models`` per the S12-T2
    # DS lock (D-S12-1) — RetentionCard is a cohort-aggregate diagnostic,
    # NOT a per-customer ranker. Dict shape (rather than a single Optional)
    # preserves room for additional cohort-aggregate substrates without a
    # further schema bump.
    cohort_diagnostics: Dict[str, RetentionCard] = field(default_factory=dict)

    # Sprint 13 Ticket T3 (additive, default ``None``): typed
    # ``MonthDelta`` slot carrying the Pivot 8 month-2-return
    # substrate-state-delta. ``None`` when ``ENGINE_V2_MONTH_2_DELTA`` is
    # OFF (default) OR no prior engine run exists for the same
    # ``store_id`` OR the 21-day floor (DS §D.2 LOCKED) is not yet
    # cleared. Populated by
    # ``src.predictive.month_2_delta.detect_month_2_delta`` at the
    # orchestration callsite after the T2 consumer-wiring pass. Schema-
    # additive within ``event_version=1``; tolerated as missing by
    # ``_from_dict_engine_run`` so pre-T3 fixtures round-trip with
    # ``month_2_delta=None``. Operator-only surface — NOT merchant-
    # rendered (briefing.html byte-identity preserved structurally by the
    # T2.5 renderer-non-consumption grep pin; this field name is also
    # absent from ``src/briefing.py``).
    month_2_delta: Optional[MonthDelta] = None

    # S13.6-T7a (DS adjudication 2026-06-01 + founder approved
    # 2026-06-01): paired null-reason for ``month_2_delta``. Closed-set
    # enum (5 members) carries the producer-side reason when
    # ``month_2_delta is None`` under the flag-ON path
    # (``ENGINE_V2_MONTH_2_DELTA`` is default-ON at T3.5 / 43e2ffe).
    # Always-paired emission is enforced at the seam: the producer
    # :func:`src.predictive.month_2_delta.detect_month_2_delta` returns
    # a 2-tuple ``(Optional[MonthDelta], Optional[MonthDeltaNullReason])``
    # so the caller cannot drop the reason. See
    # :class:`MonthDeltaNullReason` for member semantics.
    month_2_delta_null_reason: Optional[MonthDeltaNullReason] = None

    # ---- serialization -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict.

        Enums become their string values. Empty lists are preserved (T1.6:
        ``data_quality_flags`` must serialize even when empty).
        """
        return _to_jsonable(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "EngineRun":
        """Inverse of ``to_dict``. Used by tests for round-trip checks."""
        return _from_dict_engine_run(payload)


# ---------------------------------------------------------------------------
# Serialization helpers (kept private; tests round-trip via to_dict/from_dict)
# ---------------------------------------------------------------------------


# S13.6-T1a (Option D): operator-debug ``notes: List[str]`` debris on S6+
# typed slots is gated at serialization time behind ``INCLUDE_DEBUG_FIELDS``.
# Default OFF (Pivot 2 — engine emits contract surface only). Flip ON via
# the env var to round-trip the legacy ``notes`` arrays for local debug.
# Gate is scoped to the dataclass NAMES below so the load-bearing
# ``EngineRun.data_quality_flags`` (a ``List[DataQualityFlag]``, not
# ``notes``) and ``EngineRun.recommendations`` lists are untouched.
_NOTES_DEBRIS_DATACLASS_NAMES: set = {
    "Sensitivity",
    "Provenance",
    "PredictedSegment",
    "ModelCardRef",
    "MonthDelta",
}


def _include_debug_fields() -> bool:
    """Lazy lookup of ``INCLUDE_DEBUG_FIELDS`` from DEFAULTS / env.

    Default OFF. Reads via ``src.utils.DEFAULTS`` if importable; falls
    back to the raw env var. Kept lazy so circular-import risk is zero.
    """
    try:
        from .utils import DEFAULTS as _D  # local import to avoid cycle
        v = _D.get("INCLUDE_DEBUG_FIELDS", False)
    except Exception:
        import os
        v = os.getenv("INCLUDE_DEBUG_FIELDS", "false").lower() == "true"
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "on", "y"}


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses + enums to JSON-safe primitives."""
    if obj is None:
        return None
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj):
        out: Dict[str, Any] = {}
        gate_notes = (
            type(obj).__name__ in _NOTES_DEBRIS_DATACLASS_NAMES
            and not _include_debug_fields()
        )
        for k, v in asdict(obj).items():
            # S13.6-T1a: drop ``notes`` debris on S6+ typed dataclasses
            # when ``INCLUDE_DEBUG_FIELDS`` is OFF (default).
            if gate_notes and k == "notes":
                continue
            # asdict already recurses, but it does not unwrap enums on nested
            # fields. Re-walk through the live attribute to capture enums.
            live = getattr(obj, k)
            out[k] = _to_jsonable(live)
        return out
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    # Primitive (int, float, str, bool) — JSON-safe.
    return obj


def _coerce_enum(enum_cls, value):
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    return enum_cls(value)


def _from_dict_data_window(d: Optional[Dict[str, Any]]) -> DataWindow:
    if not d:
        return DataWindow()
    return DataWindow(
        primary_window=d.get("primary_window"),
        available_windows=list(d.get("available_windows") or []),
        anchor_quality=d.get("anchor_quality"),
    )


def _from_dict_abstain(d: Optional[Dict[str, Any]]) -> Abstain:
    if not d:
        return Abstain()
    raw_mode = d.get("mode")
    mode = _coerce_enum(AbstainMode, raw_mode) if raw_mode is not None else None
    return Abstain(
        state=_coerce_enum(DecisionState, d.get("state", DecisionState.PUBLISH.value)),
        # S13.6-T1a: ``reason`` field stripped from Abstain (Pivot 2).
        # Legacy dicts carrying a ``reason`` key round-trip by dropping it
        # silently — the typed ``mode`` enum is the contract surface.
        mode=mode,
    )


def _from_dict_observation(d: Dict[str, Any]) -> Observation:
    def _opt_float(v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    raw_flags = d.get("anomaly_flags") or []
    if not isinstance(raw_flags, list):
        raw_flags = []
    anomaly_flags = [str(x) for x in raw_flags if isinstance(x, str)]

    def _opt_int(v: Any, default: int = 0) -> int:
        if v is None:
            return default
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    # S13.6-T1b: ``text`` key dropped silently from legacy dicts.
    return Observation(
        supporting_metric=d.get("supporting_metric"),
        change_magnitude=d.get("change_magnitude"),
        classification=_coerce_enum(
            ObservationClassification,
            d.get("classification", ObservationClassification.HELD.value),
        ),
        current=_opt_float(d.get("current")),
        prior=_opt_float(d.get("prior")),
        delta_pct=_opt_float(d.get("delta_pct")),
        anomaly_flags=anomaly_flags,
        n_days_observed=_opt_int(d.get("n_days_observed"), 0),
        n_days_expected=_opt_int(d.get("n_days_expected"), 0),
    )


def _from_dict_watched(d: Dict[str, Any]) -> WatchedSignal:
    return WatchedSignal(
        metric=d.get("metric", ""),
        current=d.get("current"),
        prior=d.get("prior"),
        trend=d.get("trend"),
        threshold_to_act=d.get("threshold_to_act"),
    )


def _from_dict_descriptive_distribution(
    d: Optional[Dict[str, Any]],
) -> Optional[DescriptiveDistribution]:
    """S-FE-descriptive-distribution — round-trip the DescriptiveDistribution
    atom.

    Absent / null payloads round-trip to ``None`` (pre-2.1.0 snapshots +
    every non-distributional play). ``kind`` is required; a missing or
    unknown ``kind`` returns ``None`` (strict — the closed enum constructor
    would otherwise raise; we degrade to None so a malformed legacy payload
    does not crash the round-trip). ``bins`` / ``counts`` coerce
    defensively; the paired ``suppression_reason`` round-trips via the
    standard enum coercion path.
    """
    if not d:
        return None
    raw_kind = d.get("kind")
    if raw_kind is None:
        return None
    try:
        kind = _coerce_enum(DistributionKind, raw_kind)
    except (ValueError, TypeError):
        return None
    raw_bins = d.get("bins") or []
    bins: List[float] = []
    if isinstance(raw_bins, list):
        for b in raw_bins:
            try:
                bins.append(float(b))
            except (TypeError, ValueError):
                continue
    raw_counts = d.get("counts") or []
    counts: List[int] = []
    if isinstance(raw_counts, list):
        for c in raw_counts:
            try:
                counts.append(int(c))
            except (TypeError, ValueError):
                continue
    raw_marker = d.get("marker")
    marker: Optional[float]
    if raw_marker is None:
        marker = None
    else:
        try:
            marker = float(raw_marker)
        except (TypeError, ValueError):
            marker = None
    raw_reason = d.get("suppression_reason")
    return DescriptiveDistribution(
        kind=kind,
        bins=bins,
        counts=counts,
        marker=marker,
        suppressed=bool(d.get("suppressed", False)),
        suppression_reason=(
            _coerce_enum(DescriptiveDistributionSuppressionReason, raw_reason)
            if raw_reason is not None
            else None
        ),
    )


def _from_dict_audience(d: Optional[Dict[str, Any]]) -> Optional[Audience]:
    if d is None:
        return None
    return Audience(
        id=d.get("id"),
        definition=d.get("definition"),
        size=d.get("size"),
        fraction_of_base=d.get("fraction_of_base"),
        overlap_with=list(d.get("overlap_with") or []),
        # S-FE-descriptive-distribution: round-trip the typed atom. Absent /
        # null payloads round-trip to ``None`` (pre-2.1.0 snapshots + every
        # non-distributional play).
        descriptive_distribution=_from_dict_descriptive_distribution(
            d.get("descriptive_distribution")
        ),
    )


def _from_dict_measurement(d: Optional[Dict[str, Any]]) -> Optional[Measurement]:
    if d is None:
        return None
    wc = d.get("window_corroboration")
    return Measurement(
        metric=d.get("metric"),
        observed_effect=d.get("observed_effect"),
        n=d.get("n"),
        primary_window=d.get("primary_window"),
        consistency_across_windows=d.get("consistency_across_windows"),
        p_internal=d.get("p_internal"),
        ci_internal=list(d["ci_internal"]) if d.get("ci_internal") is not None else None,
        window_corroboration=_coerce_enum(WindowCorroboration, wc) if wc is not None else None,
    )


def _from_dict_revenue_range(d: Optional[Dict[str, Any]]) -> Optional[RevenueRange]:
    if d is None:
        return None
    src = d.get("source")
    # S13.6-T7a: paired ``suppression_reason`` round-trips via the
    # standard enum coercion path. Pre-T7a snapshots have no key →
    # ``None`` (strict cutover carry-forward).
    raw_reason = d.get("suppression_reason")
    return RevenueRange(
        p10=d.get("p10"),
        p50=d.get("p50"),
        p90=d.get("p90"),
        source=_coerce_enum(RevenueRangeSource, src) if src is not None else None,
        drivers=list(d.get("drivers") or []),
        suppressed=bool(d.get("suppressed", False)),
        suppression_reason=(
            _coerce_enum(RevenueRangeSuppressionReason, raw_reason)
            if raw_reason is not None
            else None
        ),
    )


def _from_dict_inventory(d: Optional[Dict[str, Any]]) -> Optional[Inventory]:
    if d is None:
        return None
    return Inventory(
        skus=list(d.get("skus") or []),
        days_of_cover=d.get("days_of_cover"),
        gate_passed=d.get("gate_passed"),
    )


def _from_dict_conflicts(d: Optional[Dict[str, Any]]) -> Optional[Conflicts]:
    if d is None:
        return None
    return Conflicts(
        cannibalized_by=list(d.get("cannibalized_by") or []),
        audience_overlap_pct=d.get("audience_overlap_pct"),
    )


def _from_dict_launch_window(d: Optional[Dict[str, Any]]) -> Optional[LaunchWindow]:
    if d is None:
        return None
    return LaunchWindow(recommended=d.get("recommended"), reason=d.get("reason"))


def _from_dict_opportunity_context(d: Optional[Dict[str, Any]]) -> Optional[OpportunityContext]:
    """Round-trip OpportunityContext from its JSON dict shape.

    S13.6-T3 (DS R1, founder approved 2026-05-30): the four monetary
    numerics now live inside the ``non_lift`` sub-object. No legacy
    fallback — strict cutover per the brief ("Do NOT add fallbacks").
    A payload missing ``non_lift`` returns ``None``.
    """
    if d is None:
        return None
    nl_raw = d.get("non_lift")
    if not isinstance(nl_raw, dict):
        return None
    try:
        audience_size = int(d.get("audience_size") or 0)
        value = float(nl_raw.get("value") or 0.0)
        aov_used = float(nl_raw.get("aov_used") or 0.0)
        monthly_revenue_estimate = float(
            nl_raw.get("monthly_revenue_estimate") or 0.0
        )
    except (TypeError, ValueError):
        return None
    semantic = nl_raw.get("semantic")
    if semantic != "addressable_opportunity":
        return None
    non_lift = NonLiftAtom(
        value=value,
        semantic="addressable_opportunity",
        aov_used=aov_used,
        monthly_revenue_estimate=monthly_revenue_estimate,
    )
    return OpportunityContext(
        audience_size=audience_size,
        non_lift=non_lift,
        aov_window=str(d.get("aov_window") or "L28"),
        aov_source=str(d.get("aov_source") or "store_observed"),
    )


def _from_dict_predicted_segment(d: Optional[Dict[str, Any]]) -> Optional[PredictedSegment]:
    """Sprint 13 Ticket T2 — round-trip the typed PredictedSegment block.

    Absent / null payloads round-trip to ``None`` (every PlayCard at flag
    OFF and every pre-T2 fixture). When present, the four additive fields
    are read defensively so a partially-populated payload survives.
    """

    if not d:
        return None
    segment_name = d.get("segment_name")
    if segment_name is not None:
        segment_name = str(segment_name)
    raw_share = d.get("audience_modal_share")
    audience_modal_share: Optional[float]
    if raw_share is None:
        audience_modal_share = None
    else:
        try:
            audience_modal_share = float(raw_share)
        except (TypeError, ValueError):
            audience_modal_share = None
    raw_n = d.get("n_audience")
    n_audience: Optional[int]
    if raw_n is None:
        n_audience = None
    else:
        try:
            n_audience = int(raw_n)
        except (TypeError, ValueError):
            n_audience = None
    notes = d.get("notes")
    if notes is not None:
        notes = str(notes)
    # S13.6-T7a: paired ``segment_name_null_reason`` round-trips via
    # the standard enum coercion path. Pre-T7a snapshots have no key
    # → ``None`` (strict cutover carry-forward).
    raw_seg_reason = d.get("segment_name_null_reason")
    return PredictedSegment(
        segment_name=segment_name,
        audience_modal_share=audience_modal_share,
        n_audience=n_audience,
        notes=notes,
        segment_name_null_reason=(
            _coerce_enum(PredictedSegmentNullReason, raw_seg_reason)
            if raw_seg_reason is not None
            else None
        ),
    )


def _from_dict_fit_warning(d: Any) -> Optional[FitWarning]:
    """S13.6-T4 — round-trip a single FitWarning entry (strict cutover).

    Accepts the post-T4 dict shape ``{"level": "<LEVEL>", "substrate":
    "<name>"}`` only. Legacy pre-T4 ``"{LEVEL}:{substrate}"`` strings
    return ``None`` (strict cutover per T3 precedent — operator-only
    audit field, no rehydration needed; callers filter Nones). Unknown
    LEVEL values likewise return ``None``.
    """

    if not isinstance(d, dict):
        return None
    raw_level = d.get("level")
    substrate = d.get("substrate")
    if raw_level is None or substrate is None:
        return None
    # Accept already-typed enum (e.g. when callers route through
    # ``dataclasses.asdict`` which does NOT unwrap nested Enum values)
    # in addition to the canonical string-value shape produced by
    # ``EngineRun.to_dict`` / ``_to_jsonable``.
    if isinstance(raw_level, FitWarningLevel):
        level = raw_level
    else:
        try:
            level = FitWarningLevel(raw_level)
        except (ValueError, TypeError):
            return None
    return FitWarning(level=level, substrate=str(substrate))


def _from_dict_model_card_ref(d: Optional[Dict[str, Any]]) -> Optional[ModelCardRef]:
    """Sprint 13 Ticket T2 — round-trip the typed ModelCardRef block.

    Absent / null payloads round-trip to ``None``. ``fit_status_chain``
    is stored as a list-of-lists in JSON (asdict round-trips tuples to
    lists); rehydration reconstructs ``(substrate, fit_status_value)``
    tuples.

    **S13.6-T4 (D-S13-4 structural):** ``fit_warnings`` is now
    ``List[FitWarning]``. Each entry round-trips via
    :func:`_from_dict_fit_warning`. Per **strict cutover** (T3 precedent
    per DS Q12), pre-T4 ``List[str]`` snapshots of the legacy
    ``"{LEVEL}:{substrate}"`` shape deserialize to an **empty list**
    (operator-only audit field; no rehydration needed). T5 CHANGELOG
    note: "Pre-T4 engine_run.json snapshots:
    model_card_ref.fit_warnings deserializes to empty list."
    """

    if not d:
        return None
    strategy_used = d.get("strategy_used")
    if strategy_used is not None:
        strategy_used = str(strategy_used)

    chain_raw = d.get("fit_status_chain") or []
    fit_status_chain: List[Tuple[str, str]] = []
    if isinstance(chain_raw, list):
        for item in chain_raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                fit_status_chain.append((str(item[0]), str(item[1])))

    warnings_raw = d.get("fit_warnings") or []
    fit_warnings: List[FitWarning] = []
    if isinstance(warnings_raw, list):
        for item in warnings_raw:
            fw = _from_dict_fit_warning(item)
            if fw is not None:
                fit_warnings.append(fw)

    notes = d.get("notes")
    if notes is not None:
        notes = str(notes)
    return ModelCardRef(
        strategy_used=strategy_used,
        fit_status_chain=fit_status_chain,
        fit_warnings=fit_warnings,
        notes=notes,
    )


def _from_dict_sensitivity(d: Optional[Dict[str, Any]]) -> Optional[Sensitivity]:
    """Sprint 8 Ticket T2 — round-trip the typed Sensitivity block.

    Absent / null payloads round-trip to ``None`` (pre-T2 fixtures, plus
    every PlayCard whose builder leaves the block unpopulated under flag
    OFF or on suppressed / unvalidated paths). Each scenario is itself an
    Optional RevenueRange round-tripped via :func:`_from_dict_revenue_range`
    so ``None`` scenarios (degenerate inputs in the helper) survive.
    """
    if not d:
        return None
    raw_notes = d.get("notes") or []
    if not isinstance(raw_notes, list):
        raw_notes = []
    notes = [str(x) for x in raw_notes if isinstance(x, str)]
    try:
        pseudo_n_used = int(d.get("pseudo_n_used") or 0)
    except (TypeError, ValueError):
        pseudo_n_used = 0
    return Sensitivity(
        scenario_observed_n_halved=_from_dict_revenue_range(
            d.get("scenario_observed_n_halved")
        ),
        scenario_observed_n_doubled=_from_dict_revenue_range(
            d.get("scenario_observed_n_doubled")
        ),
        scenario_prior_shifted_down=_from_dict_revenue_range(
            d.get("scenario_prior_shifted_down")
        ),
        scenario_prior_shifted_up=_from_dict_revenue_range(
            d.get("scenario_prior_shifted_up")
        ),
        pseudo_n_used=pseudo_n_used,
        notes=notes,
    )


def _from_dict_provenance(d: Optional[Dict[str, Any]]) -> Optional[Provenance]:
    """Sprint 8 Ticket T3 — round-trip the typed Provenance audit object.

    Absent / null payloads round-trip to ``None`` (pre-T3 fixtures, plus
    every PlayCard whose builder leaves the block unpopulated under flag
    OFF or on suppressed / unvalidated paths). Defensive coercions on all
    numeric fields so a partially-malformed payload degrades to a
    well-typed object rather than raising.
    """
    if not d:
        return None
    raw_notes = d.get("notes") or []
    if not isinstance(raw_notes, list):
        raw_notes = []
    notes = [str(x) for x in raw_notes if isinstance(x, str)]

    def _opt_int(v: Any, default: int = 0) -> int:
        if v is None:
            return default
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def _opt_float(v: Any, default: float = 0.0) -> float:
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    return Provenance(
        prior_play_id=str(d.get("prior_play_id") or ""),
        prior_key=str(d.get("prior_key") or ""),
        validation_status=str(d.get("validation_status") or ""),
        pseudo_n_used=_opt_int(d.get("pseudo_n_used"), 0),
        pseudo_n_cap=_opt_int(d.get("pseudo_n_cap"), 0),
        observed_n=_opt_int(d.get("observed_n"), 0),
        weight_observed=_opt_float(d.get("weight_observed"), 0.0),
        weight_prior=_opt_float(d.get("weight_prior"), 0.0),
        prior_source=str(d.get("prior_source") or ""),
        notes=notes,
    )


def _from_dict_mechanism_intent(d: Any) -> Optional[MechanismIntent]:
    """S13.6-T6: round-trip the typed MechanismIntent atom.

    Strict per T3/T4 precedent:

    - ``None`` / falsy / non-dict -> ``None`` (pre-T6 snapshots; legacy
      ``RejectedPlay.mechanism: <prose str>`` shape is also a non-dict
      and therefore returns ``None`` — NOT silently re-parsed).
    - Missing or non-string ``type`` -> ``None``.
    - Unknown ``type`` (not in :class:`MechanismType`) -> the
      ``MechanismType(<str>)`` constructor raises ``ValueError``; we
      propagate the raise per the closed-enum lock (DS §(d)).
    - ``parameters`` defaults to ``{}`` when absent or non-dict.
    """
    if not d or not isinstance(d, dict):
        return None
    type_raw = d.get("type")
    if not isinstance(type_raw, str) or not type_raw:
        return None
    mtype = MechanismType(type_raw)
    params_raw = d.get("parameters")
    parameters: Dict[str, Any] = dict(params_raw) if isinstance(params_raw, dict) else {}
    return MechanismIntent(type=mtype, parameters=parameters)


def _from_dict_play_card(d: Dict[str, Any]) -> PlayCard:
    # Phase 6A Ticket A2: ``would_be_measured_by`` is optional; absent or
    # null payloads round-trip to ``None``. Free-text strings raise
    # ``ValueError`` via ``_coerce_enum`` -> ``WouldBeMeasuredBy(<str>)``.
    return PlayCard(
        play_id=d.get("play_id", ""),
        evidence_class=_coerce_enum(
            EvidenceClass, d.get("evidence_class", EvidenceClass.TARGETING.value)
        ),
        confidence_label=d.get("confidence_label"),
        # S13.6-T1a: ``recommendation_text`` + ``why_now`` stripped from
        # PlayCard (Pivot 2). Legacy dicts carrying these keys round-trip
        # by dropping them silently.
        audience=_from_dict_audience(d.get("audience")),
        measurement=_from_dict_measurement(d.get("measurement")),
        revenue_range=_from_dict_revenue_range(d.get("revenue_range")),
        inventory=_from_dict_inventory(d.get("inventory")),
        conflicts=_from_dict_conflicts(d.get("conflicts")),
        launch_window=_from_dict_launch_window(d.get("launch_window")),
        opportunity_context=_from_dict_opportunity_context(d.get("opportunity_context")),
        would_be_measured_by=_coerce_enum(WouldBeMeasuredBy, d.get("would_be_measured_by")),
        # S13.6-T2: ``klaviyo_brief_inputs`` removed per founder lock-in #6.
        # Legacy dicts carrying this key round-trip by dropping it silently.
        receipts_ref=d.get("receipts_ref"),
        predicted_segment=_from_dict_predicted_segment(d.get("predicted_segment")),
        model_card_ref=_from_dict_model_card_ref(d.get("model_card_ref")),
        # S8-T1: round-trip the typed evidence-source chip. Absent or
        # null payloads round-trip to ``None`` (pre-T1 fixtures); free-text
        # strings raise ``ValueError`` via the standard enum constructor.
        evidence_source=_coerce_enum(EvidenceSourceChip, d.get("evidence_source")),
        # S8-T2: round-trip the typed Sensitivity block. Absent or null
        # payloads round-trip to ``None`` (pre-T2 fixtures + flag-OFF
        # / suppressed / unvalidated paths).
        sensitivity=_from_dict_sensitivity(d.get("sensitivity")),
        # S8-T3: round-trip the typed Provenance audit object. Absent or
        # null payloads round-trip to ``None`` (pre-T3 fixtures + flag-OFF
        # / suppressed / unvalidated paths). See :class:`Provenance` for
        # the per-field semantics + flag contract.
        provenance=_from_dict_provenance(d.get("provenance")),
        # S13.6-T6: round-trip the typed MechanismIntent atom. Absent or
        # null payloads round-trip to ``None`` (pre-T6 snapshots — strict
        # cutover by design per T3/T4 precedent; not silently parsed).
        mechanism_intent=_from_dict_mechanism_intent(d.get("mechanism_intent")),
    )


def _from_dict_rejected(d: Dict[str, Any]) -> RejectedPlay:
    detail = d.get("held_reason_detail")
    if detail is not None and not isinstance(detail, dict):
        detail = None
    audience_size = d.get("audience_size")
    if audience_size is not None:
        try:
            audience_size = int(audience_size)
        except (TypeError, ValueError):
            audience_size = None
    return RejectedPlay(
        play_id=d.get("play_id", ""),
        reason_code=_coerce_enum(ReasonCode, d.get("reason_code")),
        # S13.6-T1a: ``reason_text`` / ``evidence_snapshot`` / ``would_fire_if``
        # stripped from RejectedPlay (Pivot 2). Legacy dicts carrying these
        # keys round-trip by dropping them silently — the typed
        # ``reason_code`` + ``held_reason_detail`` are the contract surface.
        held_reason_detail=dict(detail) if detail is not None else None,
        audience_size=audience_size,
        audience_definition=d.get("audience_definition"),
        # S13.6-T6: strict deserialization per T3/T4 precedent. Legacy
        # pre-T6 snapshots carrying ``mechanism: "<prose str>"`` shape
        # are non-dict and therefore round-trip to ``None`` (not
        # silently re-parsed). Post-T6 emission is the typed
        # ``MechanismIntent`` dict ``{"type": ..., "parameters": {...}}``.
        mechanism=_from_dict_mechanism_intent(d.get("mechanism")),
        would_be_measured_by=_coerce_enum(
            WouldBeMeasuredBy, d.get("would_be_measured_by")
        ),
    )


def _from_dict_scale(d: Optional[Dict[str, Any]]) -> Scale:
    if not d:
        return Scale()
    return Scale(
        monthly_revenue=d.get("monthly_revenue"),
        customer_base_est=d.get("customer_base_est"),
        materiality_floor=d.get("materiality_floor"),
    )


def _from_dict_briefing_meta(d: Optional[Dict[str, Any]]) -> BriefingMeta:
    if not d:
        return BriefingMeta()
    return BriefingMeta(
        confidence_mode=d.get("confidence_mode"),
        vertical=d.get("vertical"),
        subvertical=d.get("subvertical"),
        stage=d.get("stage"),
        seasonality_tag=d.get("seasonality_tag"),
    )


def _from_dict_store_profile_payload(d: Any) -> Any:
    """Sprint 6.5 Ticket T1: round-trip the ``store_profile`` slot.

    Lazy-imported so this module does not depend on ``src.profile`` at
    import time (keeps the legacy ``ENGINE_V2_STORE_PROFILE=false`` path
    unaffected by any future profile-side import error).
    """
    if d is None:
        return None
    try:
        from .profile.types import store_profile_from_dict
    except Exception:
        return None
    return store_profile_from_dict(d)


def _from_dict_month_delta(d: Optional[Dict[str, Any]]) -> Optional[MonthDelta]:
    """Round-trip ``EngineRun.month_2_delta`` from a JSON-safe dict.

    Tolerates ``None`` (T3 flag-OFF default) and missing fields (pre-T3
    payloads). Re-hydrates ``substrate_fit_status_changes`` list-of-lists
    → dict-of-tuples (asdict serializes tuples as lists).
    """

    if not d:
        return None
    raw_changes = d.get("substrate_fit_status_changes") or {}
    changes: Dict[str, Tuple[str, str]] = {}
    if isinstance(raw_changes, dict):
        for k, v in raw_changes.items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                changes[str(k)] = (str(v[0]), str(v[1]))
    raw_shifts = d.get("segment_shifts")
    shifts: Optional[Dict[str, Dict[str, str]]]
    if raw_shifts is None:
        shifts = None
    elif isinstance(raw_shifts, dict):
        shifts = {}
        for cust_id, pair in raw_shifts.items():
            if isinstance(pair, dict):
                shifts[str(cust_id)] = {
                    "prior": str(pair.get("prior", "")),
                    "current": str(pair.get("current", "")),
                }
    else:
        shifts = None
    raw_delta = d.get("retention_ci_at_month_3_delta")
    delta_val: Optional[float]
    if raw_delta is None:
        delta_val = None
    else:
        try:
            delta_val = float(raw_delta)
        except (TypeError, ValueError):
            delta_val = None
    raw_notes = d.get("notes") or []
    notes = [str(n) for n in raw_notes if isinstance(n, (str, int, float))]
    try:
        days_between = int(d.get("days_between") or 0)
    except (TypeError, ValueError):
        days_between = 0
    return MonthDelta(
        prior_run_id=str(d.get("prior_run_id") or ""),
        current_run_id=str(d.get("current_run_id") or ""),
        days_between=days_between,
        substrate_fit_status_changes=changes,
        segment_shifts=shifts,
        retention_ci_at_month_3_delta=delta_val,
        notes=notes,
    )


def _from_dict_engine_run(payload: Dict[str, Any]) -> EngineRun:
    if payload is None:
        return EngineRun()
    return EngineRun(
        run_id=payload.get("run_id"),
        store_id=payload.get("store_id"),
        anchor_date=payload.get("anchor_date"),
        schema_version=payload.get("schema_version", "1.0.0"),
        data_window=_from_dict_data_window(payload.get("data_window")),
        cold_start=bool(payload.get("cold_start", False)),
        data_quality_flags=[
            _coerce_enum(DataQualityFlag, v) for v in (payload.get("data_quality_flags") or [])
        ],
        abstain=_from_dict_abstain(payload.get("abstain")),
        state_of_store=[_from_dict_observation(o) for o in (payload.get("state_of_store") or [])],
        recommendations=[_from_dict_play_card(p) for p in (payload.get("recommendations") or [])],
        store_profile=_from_dict_store_profile_payload(payload.get("store_profile")),
        # S13.7-T7b: paired ``store_profile_null_reason`` round-trips via the
        # standard enum coercion path. Pre-T7b snapshots have no key → ``None``
        # (strict cutover carry-forward; tolerated as missing).
        store_profile_null_reason=(
            _coerce_enum(StoreProfileNullReason, payload.get("store_profile_null_reason"))
            if payload.get("store_profile_null_reason") is not None
            else None
        ),
        recommended_experiments=[
            _from_dict_play_card(p) for p in (payload.get("recommended_experiments") or [])
        ],
        considered=[_from_dict_rejected(r) for r in (payload.get("considered") or [])],
        watching=[_from_dict_watched(w) for w in (payload.get("watching") or [])],
        scale=_from_dict_scale(payload.get("scale")),
        briefing_meta=_from_dict_briefing_meta(payload.get("briefing_meta")),
        # S7.6-C1: tolerate absence on pre-C1 payloads (default 0).
        considered_truncated_count=int(payload.get("considered_truncated_count") or 0),
        # S10-T1: tolerate absence on pre-S10 payloads (default ``{}``).
        # Values are passed through as-is — ModelCard re-hydration is
        # handled by the predictive-layer consumer at S13, not at the
        # EngineRun round-trip seam (the JSON-safe asdict form already
        # round-trips fine for the operator-only surface).
        predictive_models=dict(payload.get("predictive_models") or {}),
        # S12-T2: tolerate absence on pre-S12 payloads (default ``{}``).
        # Values pass through as-is — RetentionCard re-hydration is handled
        # by the predictive-layer consumer at S13, not at the EngineRun
        # round-trip seam (the JSON-safe asdict form already round-trips
        # fine for the operator-only surface). Mirrors predictive_models
        # round-trip precedent.
        cohort_diagnostics=dict(payload.get("cohort_diagnostics") or {}),
        # S13-T3: tolerate absence on pre-T3 payloads (default ``None``).
        month_2_delta=_from_dict_month_delta(payload.get("month_2_delta")),
        # S13.6-T7a: paired ``month_2_delta_null_reason`` round-trips
        # via the standard enum coercion path. Pre-T7a snapshots have
        # no key → ``None`` (strict cutover carry-forward).
        month_2_delta_null_reason=(
            _coerce_enum(MonthDeltaNullReason, payload.get("month_2_delta_null_reason"))
            if payload.get("month_2_delta_null_reason") is not None
            else None
        ),
    )
