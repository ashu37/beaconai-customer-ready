"""Play Registry (Milestone 2, tickets T2.1, T2.2, T2.3).

This module defines the typed, single-source-of-truth registry of plays the
BeaconAI Action Engine can recommend. The registry is **schema-only** in
Milestone 2 — it is NOT read at runtime, NOT used to alter scoring, and NOT
used to change merchant-facing labels yet. Subsequent milestones consume
this contract:

- M3 detect_candidates() reads ``PLAYS`` to gate which play_ids may be
  emitted at all and to look up ``audience_builder_ref``.
- M4a/M4b read ``evidence_class_default`` to enforce "targeting plays
  cannot expose p/q/CI/measured effect".
- M6 reads ``prior_keys`` to look up sizing priors from
  ``config/priors.yaml``.
- M8 may read ``display_name`` for V2 merchant copy (still gated by
  ``ENGINE_V2_OUTPUT``; M2 itself does NOT rename anything merchant-facing).

Source of truth for entries:
- agent_outputs/implementation-manager-overhaul-plan-final.md (M2, T2.1-T2.3)
- agent_outputs/product-strategy-pm-overhaul-requirements.md (Q3 play table)
- memory.md "Play classification" section
- The legacy candidate emitters in ``src/action_engine.py`` (the inventory
  of currently-emitted ``play_id`` values).

Hard guardrails for M2:
- M0 golden tests must still pass (no behavior change).
- This module imports nothing from ``action_engine``. It is leaf-only.
- Every legacy ``play_id`` ever emitted by ``_compute_candidates`` MUST be
  represented in ``PLAYS`` (verified by ``tests/test_play_registry.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional


# ---------------------------------------------------------------------------
# Allowed evidence classes for ``evidence_class_default``.
#
# These mirror ``src.engine_run.EvidenceClass`` string values. We do NOT
# import EvidenceClass here to keep this module leaf-level (no risk of an
# import cycle when M3 starts wiring detection). The test suite asserts the
# values agree.
# ---------------------------------------------------------------------------

EVIDENCE_CLASSES: FrozenSet[str] = frozenset({"measured", "directional", "targeting"})


# ---------------------------------------------------------------------------
# PlayDef — the typed schema for one play.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlayDef:
    """Typed definition of one play in the Action Engine registry.

    Fields per implementation-manager M2 spec:

    - ``play_id``: stable internal identifier. Must match the ``play_id``
      string the legacy candidate emitters use today (or be a NEW id for
      a not-yet-emitted M3 play). Used as the dict key in ``PLAYS``.
    - ``display_name``: merchant-facing title. M2 does NOT change merchant
      labels; this field is captured for M8.
    - ``evidence_class_default``: one of ``{"measured", "directional",
      "targeting"}``. The DEFAULT class for a candidate of this play
      before evidence (n, p, consistency) is evaluated. M4a/M4b enforce
      this contract.
    - ``requires_inventory``: True if M5 must check stock-on-hand before
      this play can recommend demand generation (e.g., ``bestseller_amplify``).
    - ``audience_builder_ref``: free-text reference to the M3 audience
      builder that produces the candidate. M3 reads this; M2 just records.
    - ``measurement_metric``: the observed effect metric, e.g.,
      ``"reactivation_rate"``. ``None`` for pure targeting plays.
    - ``vertical_applicable``: set of vertical_mode strings this play
      applies to (e.g., ``{"beauty", "supplements", "mixed"}``). Empty
      means "all".
    - ``subvertical_applicable``: optional set of subverticals (e.g.,
      ``{"skincare", "haircare"}``). ``None`` means "all" for the
      applicable verticals.
    - ``prior_keys``: list of keys this play looks up in
      ``config/priors.yaml`` (e.g., ``["base_rate", "incrementality",
      "bundle_value"]``). M6 reads this; M2 just records.
    - ``targeting_disclaimer``: optional merchant-facing copy snippet for
      cards classified as ``targeting``. ``None`` means "use the default
      targeting disclaimer".
    - ``notes``: free-text notes for downstream milestones (e.g., open
      questions, deferred work).

    The dataclass is frozen so the registry cannot be mutated at runtime.
    """

    play_id: str
    display_name: str
    evidence_class_default: str
    requires_inventory: bool
    audience_builder_ref: str
    measurement_metric: Optional[str]
    vertical_applicable: FrozenSet[str]
    subvertical_applicable: Optional[FrozenSet[str]]
    prior_keys: List[str]
    targeting_disclaimer: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        # Light schema validation; raised at import time if a definition is
        # malformed. We do NOT validate cross-references here (e.g., that
        # prior_keys exist in priors.yaml) — M6 owns that.
        if not isinstance(self.play_id, str) or not self.play_id:
            raise ValueError(f"PlayDef.play_id must be a non-empty string: {self.play_id!r}")
        if self.evidence_class_default not in EVIDENCE_CLASSES:
            raise ValueError(
                f"PlayDef[{self.play_id}].evidence_class_default must be one of "
                f"{sorted(EVIDENCE_CLASSES)}; got {self.evidence_class_default!r}"
            )
        if not isinstance(self.display_name, str) or not self.display_name:
            raise ValueError(f"PlayDef[{self.play_id}].display_name must be non-empty")
        if not isinstance(self.requires_inventory, bool):
            raise ValueError(f"PlayDef[{self.play_id}].requires_inventory must be bool")
        if not isinstance(self.audience_builder_ref, str) or not self.audience_builder_ref:
            raise ValueError(
                f"PlayDef[{self.play_id}].audience_builder_ref must be a non-empty string"
            )
        if self.evidence_class_default == "targeting" and self.measurement_metric is not None:
            # PM-Q2 hard rule: targeting plays have measurement = null.
            # The registry mirrors this expectation: a default-targeting
            # play declares no measurement metric.
            raise ValueError(
                f"PlayDef[{self.play_id}] is default-targeting but declares a "
                f"measurement_metric={self.measurement_metric!r}. Targeting plays must "
                f"have measurement_metric=None."
            )
        if not isinstance(self.prior_keys, list):
            raise ValueError(f"PlayDef[{self.play_id}].prior_keys must be a list")


# ---------------------------------------------------------------------------
# Helper: standard verticals as a frozenset.
# ---------------------------------------------------------------------------

# mixed = literal beauty+supplements blend, NOT an unknown-vertical fallback.
_ALL_VERTICALS: FrozenSet[str] = frozenset({"beauty", "supplements", "mixed"})


# ---------------------------------------------------------------------------
# PLAYS — the registry.
#
# Inventory of legacy emitted play_ids (from ``_compute_candidates``):
#   1.  winback_21_45
#   2.  bestseller_amplify
#   3.  discount_hygiene
#   4.  subscription_nudge
#   5.  routine_builder
#   6.  empty_bottle             (replenishment-reminder candidate)
#   7.  frequency_accelerator
#   8.  aov_momentum
#   9.  retention_mastery
#   10. journey_optimization
#   11. category_expansion
#
# Plus three new entries from T2.3 (registry-only — no engine logic yet):
#   12. first_to_second_purchase
#   13. at_risk_repeat_buyer_rescue   (rename target for retention_mastery)
#   14. onsite_funnel_watch           (demoted journey_optimization)
#
# T2.3 note: ``at_risk_repeat_buyer_rescue`` and ``onsite_funnel_watch``
# coexist with their legacy counterparts (``retention_mastery``,
# ``journey_optimization``) in the registry. The legacy IDs remain because
# the legacy emitters still produce them today; the new IDs are reserved
# for M3+ to use under the V2 flag. M2 does NOT rename anything merchant-
# facing.
#
# Evidence-class assignments follow memory.md "Play classification" and
# the PM doc Q3 table:
#   - measured/directional-eligible: winback, frequency_accelerator,
#     discount_hygiene, empty_bottle, retention_mastery (legacy emitter
#     today; new ID at_risk_repeat_buyer_rescue is targeting until churn-
#     reduction is properly measured).
#   - directional-only by default: aov_momentum (memory.md: "directional
#     only; do not forecast lift").
#   - targeting-only: bestseller_amplify, routine_builder, subscription_nudge,
#     journey_optimization (until onsite funnel data exists; per memory.md),
#     category_expansion, first_to_second_purchase (preferred replacement
#     for journey_optimization, but lacks onsite data),
#     at_risk_repeat_buyer_rescue, onsite_funnel_watch.
#
# When in doubt about source_class for priors, prefer the more conservative
# evidence_class_default (targeting > directional > measured).
# ---------------------------------------------------------------------------


PLAYS: Dict[str, PlayDef] = {
    # -----------------------------------------------------------------
    # Legacy plays (already emitted by _compute_candidates today).
    # -----------------------------------------------------------------
    "winback_21_45": PlayDef(
        play_id="winback_21_45",
        display_name="Lapsed-buyer reactivation (3–6 weeks since last order)",
        evidence_class_default="measured",
        requires_inventory=False,
        audience_builder_ref="audience.winback_21_45_inactive",
        measurement_metric="reactivation_rate",
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate", "incrementality", "orders_per_customer"],
        notes=(
            "MVP-safe and evidence-based when sufficient inactive cohort exists. "
            "Memory.md: 'Winback: MVP-safe, evidence-based if enough history.'"
        ),
    ),
    "bestseller_amplify": PlayDef(
        play_id="bestseller_amplify",
        display_name="Top-product re-targeting",
        evidence_class_default="targeting",
        requires_inventory=True,
        audience_builder_ref="audience.bestseller_buyers",
        measurement_metric=None,
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate", "incrementality", "bundle_value"],
        targeting_disclaimer=(
            "Audience-targeting recommendation. No measured lift; effect "
            "depends on creative and inventory."
        ),
        notes=(
            "Targeting only + inventory gate (memory.md). M5 enforces stock "
            "check; M2 records the requires_inventory bit."
        ),
    ),
    "discount_hygiene": PlayDef(
        play_id="discount_hygiene",
        display_name="Discount-dependence cleanup",
        evidence_class_default="measured",
        requires_inventory=False,
        audience_builder_ref="audience.discount_dependent_buyers",
        measurement_metric="margin_recovery_rate",
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["margin_recovery_rate", "incrementality"],
        notes=(
            "MVP-safe IF discount data is reliable (memory.md). Detector "
            "in M3 must validate discount_code presence before emitting."
        ),
    ),
    "subscription_nudge": PlayDef(
        play_id="subscription_nudge",
        display_name="Subscribe-and-save invitation for repeat buyers",
        evidence_class_default="targeting",
        requires_inventory=False,
        audience_builder_ref="audience.subscription_candidates",
        measurement_metric=None,
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate", "incrementality", "subscription_multiplier"],
        targeting_disclaimer=(
            "Audience-targeting recommendation. No measured subscription "
            "uplift; subscription mechanics depend on storefront support."
        ),
        notes=(
            "Targeting only (memory.md). Phase 4.2 deferred per memory: "
            "multiplier-vs-baseline-rate conflation + survivorship bias on "
            "the >=3-SKU audience."
        ),
    ),
    "routine_builder": PlayDef(
        play_id="routine_builder",
        display_name="Complete-the-routine bundle",
        evidence_class_default="targeting",
        requires_inventory=False,
        audience_builder_ref="audience.routine_completion_candidates",
        measurement_metric=None,
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=frozenset({"skincare", "haircare", "wellness"}),
        prior_keys=["base_rate", "incrementality", "bundle_value"],
        targeting_disclaimer=(
            "Audience-targeting recommendation. No measured bundle uplift."
        ),
        notes=(
            "Targeting only (memory.md). Phase 4.2 deferred per memory: "
            "Welch-t produces p only; no measured effect without unit-coherence "
            "design work."
        ),
    ),
    "empty_bottle": PlayDef(
        play_id="empty_bottle",
        display_name="Replenishment timing",
        evidence_class_default="directional",
        requires_inventory=False,
        audience_builder_ref="audience.depletion_window_buyers",
        measurement_metric="reorder_rate",
        # G-2: restrict to verticals with parser coverage in
        # ``config/replenishment_sizes.yaml``. ``supplements`` is
        # excluded until Sprint 4 G-3 ships a unit-coherent parser
        # (count / lb / mg / serving-per-container). ``mixed`` is
        # included because the Beauty regex catches the Beauty half
        # of the blend and the supplements half is a no-op.
        # decide.py:614's vertical-applicable filter consumes this
        # set and clean-skips the play (vs emitting a misleading
        # ``no_measured_signal`` Considered card).
        vertical_applicable=frozenset({"beauty", "mixed"}),
        subvertical_applicable=frozenset({"skincare", "haircare", "wellness", "supplements"}),
        prior_keys=["base_rate", "incrementality"],
        notes=(
            "Replenishment Reminder play (memory.md: 'MVP-safe with caveats; "
            "usually targeting unless reorder pattern is strong'). Default is "
            "directional because the engine already runs a two-proportion z-test "
            "between depleted and non-depleted cohorts; M4a/M4b will demote to "
            "targeting when n is below the directional threshold."
        ),
    ),
    "frequency_accelerator": PlayDef(
        play_id="frequency_accelerator",
        display_name="Repeat-purchase cadence nudge",
        evidence_class_default="measured",
        requires_inventory=False,
        audience_builder_ref="audience.repeat_cohort",
        measurement_metric="orders_per_customer",
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate", "incrementality", "frequency_lift"],
        notes=(
            "MVP-safe with caveats (memory.md). M4a removes the assumed lift; "
            "the engine must report only the observed cohort effect."
        ),
    ),
    "aov_momentum": PlayDef(
        play_id="aov_momentum",
        display_name="Basket-size momentum watch",
        evidence_class_default="directional",
        requires_inventory=False,
        audience_builder_ref="audience.aov_growth_cohort",
        measurement_metric="aov_growth_rate",
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate", "incrementality", "growth_acceleration"],
        notes=(
            "Directional only (memory.md): 'do not forecast lift from observed "
            "AOV drift'. M4a/M4b enforce; M2 records the default class."
        ),
    ),
    "retention_mastery": PlayDef(
        play_id="retention_mastery",
        display_name="At-risk repeat-buyer rescue (legacy emitter)",
        evidence_class_default="targeting",
        requires_inventory=False,
        audience_builder_ref="audience.retention_at_risk",
        measurement_metric=None,
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate", "incrementality", "churn_reduction"],
        targeting_disclaimer=(
            "Audience-targeting recommendation. The legacy assumed-churn "
            "reduction has been removed; effect is unmeasured."
        ),
        notes=(
            "Memory.md: 'Retention Mastery: rename to At-Risk Repeat Buyer "
            "Rescue; remove assumed churn reduction.' The legacy ID remains "
            "in the registry because action_engine still emits it; the new "
            "ID at_risk_repeat_buyer_rescue is also registered for M3+."
        ),
    ),
    "journey_optimization": PlayDef(
        play_id="journey_optimization",
        display_name="Post-first-purchase journey nudge",
        evidence_class_default="targeting",
        requires_inventory=False,
        audience_builder_ref="audience.journey_one_purchase_cohort",
        measurement_metric=None,
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate", "incrementality", "conversion_improvement"],
        targeting_disclaimer=(
            "Audience-targeting recommendation. Onsite funnel data is not "
            "available in the local CSV pipeline; conversion-improvement claim "
            "is unmeasured."
        ),
        notes=(
            "Memory.md: 'Journey Optimization: rename or demote until onsite "
            "funnel data exists.' Demoted to targeting; the new ID "
            "onsite_funnel_watch is also registered as a watching-only signal."
        ),
    ),
    "category_expansion": PlayDef(
        play_id="category_expansion",
        display_name="Cross-category discovery for single-category buyers",
        evidence_class_default="targeting",
        requires_inventory=False,
        audience_builder_ref="audience.single_category_buyers",
        measurement_metric=None,
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate", "incrementality", "expansion_rate"],
        targeting_disclaimer=(
            "Audience-targeting recommendation. No measured cross-category lift."
        ),
        notes=(
            "Targeting only; remove fabricated stats (memory.md). M4a NaNs the "
            "fabricated p-value/effect; M2 records the targeting default."
        ),
    ),
    # -----------------------------------------------------------------
    # T2.3: Three new registry entries (no engine logic yet).
    # -----------------------------------------------------------------
    "first_to_second_purchase": PlayDef(
        play_id="first_to_second_purchase",
        display_name="Second-purchase nudge for one-and-done buyers",
        evidence_class_default="measured",
        requires_inventory=False,
        audience_builder_ref="audience.single_purchase_cohort",
        measurement_metric="second_purchase_rate",
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate", "incrementality", "second_purchase_lift"],
        notes=(
            "Memory.md: 'MVP-safe and preferred replacement for Journey "
            "Optimization.' M2 reserves the play_id; M3 will wire detection. "
            "Default is measured because the metric is a binary first->second "
            "conversion rate that is computable from CSV history alone."
        ),
    ),
    "winback_dormant_cohort": PlayDef(
        play_id="winback_dormant_cohort",
        display_name="Dormant repeat-buyer winback",
        evidence_class_default="directional",
        requires_inventory=False,
        audience_builder_ref="audience.winback_dormant_cohort",
        measurement_metric="reactivation_rate",
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate"],
        notes=(
            "Sprint 6 Tier-B builder (architecture plan Part I §B-1). Cohort "
            "is dormant repeat-buyers in a vertical-aware winback window "
            "(beauty 21-45d, supplements 60-120d), with >=2 prior orders "
            "and no order in the past 28 days. Evidence is cohort existence; "
            "the measurement-builder anchors the PlayCard posterior on "
            "winback_21_45.base_rate (beauty validated_external Klaviyo, "
            "supplements heuristic_unvalidated). Gated behind "
            "ENGINE_V2_BUILDER_WINBACK_DORMANT."
        ),
    ),
    "replenishment_due": PlayDef(
        play_id="replenishment_due",
        display_name="Replenishment-due cadence nudge",
        evidence_class_default="directional",
        requires_inventory=False,
        audience_builder_ref="audience.replenishment_due",
        measurement_metric="replenishment_conversion_rate",
        vertical_applicable=frozenset({"beauty", "supplements", "mixed"}),
        subvertical_applicable=None,
        prior_keys=["bundle_value"],
        notes=(
            "Sprint 6 Tier-B builder (S6-T3). Per-customer × per-SKU "
            "cadence inference; audience is customers whose most-recent "
            "in-class purchase has reached cadence_median +/- floor(cadence/2). "
            "Beauty consumes the legacy size_regex; supplements consumes the "
            "S6-T2 unit-coherent parser; mixed unions both cohorts (G-3). "
            "N=30 customers-with->=2-repeat-purchases per SKU floor "
            "(founder Q2 decision, memory.md e87e431). Measurement anchors "
            "on bestseller_amplify.bundle_value (Beauty validated_external "
            "bsandco; supplements heuristic_unvalidated -> routes to "
            "Considered with PRIOR_UNVALIDATED per S7.5-T3 contract). "
            "Gated behind ENGINE_V2_BUILDER_REPLENISHMENT_DUE (default OFF "
            "at S6-T3; T3.5 owns atomic flag flip + fixture re-pin)."
        ),
    ),
    "cohort_journey_first_to_second": PlayDef(
        play_id="cohort_journey_first_to_second",
        display_name="First-to-second cohort journey nudge",
        evidence_class_default="directional",
        requires_inventory=False,
        audience_builder_ref="audience.cohort_journey_first_to_second",
        measurement_metric="first_to_second_conversion_rate",
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate"],
        notes=(
            "Sprint 7 Tier-B builder (S7-T2). Cohort is first-time buyers "
            "whose only order is 30-90 days before the anchor; no second "
            "purchase yet. Measurement anchors on the validated_external "
            "first_to_second_purchase.base_rate prior (S7.5-T2 promotion; "
            "bsandco DTC RPR 2026 memo, effective_n=156110, wildcard "
            "vertical) via build_prior_anchored_play_card. Retires the "
            "Phase 5.6 first_to_second_purchase directional proxy at "
            "S7-T2.5 (this S7-T2 ticket ships the impl + flag OFF; the "
            "legacy proxy stays one sprint of cushion past T2.5 per IM "
            "preserved-out-of-scope discipline). Gated behind "
            "ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND (default OFF at "
            "S7-T2; T2.5 owns atomic flag flip + fixture re-pin)."
        ),
    ),
    "aov_lift_via_threshold_bundle": PlayDef(
        play_id="aov_lift_via_threshold_bundle",
        display_name="AOV-threshold near-cohort cross-sell",
        evidence_class_default="directional",
        requires_inventory=False,
        audience_builder_ref="audience.aov_lift_via_threshold_bundle",
        measurement_metric="aov_threshold_crossing_conversion_rate",
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate"],
        notes=(
            "Sprint 7 Tier-B builder (S7-T3). Snapshot near-threshold "
            "cohort: customers whose current cart or typical AOV is $5-$15 "
            "BELOW the merchant-defined AOV threshold (free-shipping tier, "
            "spend-X-get-Y milestone, tiered bundle-pricing). Cart-state "
            "is the preferred source; falls back to last-90d avg AOV when "
            "no cart-state column is present (the standard CSV today). "
            "Measurement anchors on the dual-tier aov_lift_via_threshold_"
            "bundle.base_rate prior — Beauty validated_external Memo 2 "
            "(pseudo_n=30); supplements elicited_expert Memo 3 DOWNGRADED "
            "per DS verdict 2026-05-20 + KI-NEW-J cross-vertical evidence "
            "laundering safeguard (pseudo_n=10, brand's own data dominates "
            "within ~20 observed conversions). The legacy bestseller_amplify "
            "play is operationally distinct (static pre-purchase bundle; M2 "
            "Recommended Experiment allowlist) and preserved untouched. "
            "Gated behind ENGINE_V2_BUILDER_AOV_BUNDLE (default OFF at "
            "S7-T3; T3.5 owns atomic flag flip + fixture re-pin)."
        ),
    ),
    "discount_dependency_hygiene": PlayDef(
        play_id="discount_dependency_hygiene",
        display_name="Discount-dependency full-price re-engagement",
        evidence_class_default="directional",
        requires_inventory=False,
        audience_builder_ref="audience.discount_dependency_hygiene",
        measurement_metric="discount_dependency_hygiene_full_price_conversion_rate",
        vertical_applicable=frozenset({"beauty", "mixed"}),
        subvertical_applicable=None,
        prior_keys=["base_rate"],
        notes=(
            "Sprint 7 Tier-B builder (S7-T1). Cohort is customers whose "
            ">=50% of historical orders carried a discount (Memo 1 "
            "canonical ≥50% threshold). Mechanism: 14-day discount "
            "suppression across all channels (upstream campaign-config "
            "owns the suppression window) followed by a value-led, "
            "no-urgency, full-price email send. Measurement anchors on "
            "the Beauty-only validated_external "
            "discount_dependency_hygiene.base_rate.beauty prior "
            "(DS-validated 2026-05-20; Klaviyo H&B 2026 omnichannel "
            "benchmark; KI-NEW-K envelope re-fit deferred to Sprint 8). "
            "Beauty-only activation by design — supplements rejects per "
            "DS Memo-4 verdict (no priors block, no gate_calibration "
            "cell; supplements routes to PRIOR_UNVALIDATED Considered "
            "via S7.5-T3 refusal logic when invoked). Legacy "
            "``discount_hygiene`` play_id is preserved untouched for "
            "the M2 measured-margin pathway (KI-21 Recommended "
            "Experiment allowlist); the two coexist by founder Q1 "
            "default 2026-05-20. Gated behind "
            "ENGINE_V2_BUILDER_DISCOUNT_HYGIENE (default OFF at S7-T1; "
            "S7-T1.5 owns atomic flag flip + fixture re-pin)."
        ),
    ),
    "at_risk_repeat_buyer_rescue": PlayDef(
        play_id="at_risk_repeat_buyer_rescue",
        display_name="At-risk repeat-buyer rescue",
        evidence_class_default="targeting",
        requires_inventory=False,
        audience_builder_ref="audience.at_risk_repeat_buyers",
        measurement_metric=None,
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=["base_rate", "incrementality"],
        targeting_disclaimer=(
            "Audience-targeting recommendation. No measured churn reduction."
        ),
        notes=(
            "Memory.md: rename of Retention Mastery; 'remove assumed churn "
            "reduction'. Targeting until a defensible churn-reduction "
            "measurement design is in place. M2 reserves the play_id; legacy "
            "retention_mastery emitter still produces output today."
        ),
    ),
    "onsite_funnel_watch": PlayDef(
        play_id="onsite_funnel_watch",
        display_name="Onsite funnel watch",
        evidence_class_default="targeting",
        requires_inventory=False,
        audience_builder_ref="audience.onsite_funnel_observation",
        measurement_metric=None,
        vertical_applicable=_ALL_VERTICALS,
        subvertical_applicable=None,
        prior_keys=[],
        targeting_disclaimer=(
            "Onsite funnel data is not available in the local CSV pipeline. "
            "Treat as a watching signal until storefront analytics integration."
        ),
        notes=(
            "Memory.md: demoted journey_optimization. Targeting (per T2.3 "
            "instruction: 'Mark the latter as evidence_class_default=\"targeting\" "
            "until onsite data exists'). Reserved for the M7 watching list."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Helpers (read-only, no runtime wiring in M2).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase 6B Stop-Coding-Line Task 1: display_name uniqueness invariant.
#
# Two active plays sharing the same merchant-facing ``display_name`` would
# collide in the rendered slate (Recommended Now / Recommended Experiment /
# Considered) and confuse downstream agents. We assert uniqueness at
# import time (load point of the registry) so a future YAML / registry
# edit that re-introduces a collision fails loudly at startup, not
# silently at render time.
# ---------------------------------------------------------------------------


def _assert_display_name_uniqueness(plays: Dict[str, "PlayDef"]) -> None:
    """Raise ``ValueError`` if any two plays share a ``display_name``.

    The error message lists the offending ``display_name`` and all
    ``play_id`` values that share it so the fix is unambiguous.
    """

    seen: Dict[str, List[str]] = {}
    for play_id, defn in plays.items():
        name = (defn.display_name or "").strip()
        if not name:
            continue
        seen.setdefault(name, []).append(play_id)
    collisions = {name: ids for name, ids in seen.items() if len(ids) > 1}
    if collisions:
        details = "; ".join(
            f"{name!r} -> {sorted(ids)}" for name, ids in sorted(collisions.items())
        )
        raise ValueError(
            "PlayDef.display_name uniqueness violated across active plays: "
            + details
        )


# Fire at module import time. If a future edit reintroduces a collision,
# the registry import fails and tests / runs surface the violation.
_assert_display_name_uniqueness(PLAYS)


def get(play_id: str) -> Optional[PlayDef]:
    """Return the PlayDef for ``play_id`` or ``None`` if unregistered.

    M2 callers: tests only. M3+ will use this from the candidate detector.
    """

    return PLAYS.get(play_id)


def all_play_ids() -> List[str]:
    """Return all registered play_ids in insertion order."""

    return list(PLAYS.keys())


__all__ = [
    "PlayDef",
    "PLAYS",
    "EVIDENCE_CLASSES",
    "get",
    "all_play_ids",
    "consult_play_library_if_enabled",
]


# ---------------------------------------------------------------------------
# Sprint 8 Ticket T4 — Play Library wave 1 consult-and-verify integration.
#
# When ``ENGINE_V2_PLAY_LIBRARY_WAVE1`` is ON, ``run_action_engine`` calls
# this helper once at startup. It delegates to
# ``plays.assert_identity_with_legacy()`` which loads each wave-1
# ``plays/<play_id>/spec.yaml`` and asserts:
#
#   1. The audience builder callable resolved from the spec.yaml dotted
#      ref is the exact same Python object as the legacy registry's
#      ``src.audience_builders.BUILDERS[audience_builder_ref]``.
#   2. The ``_PRIOR_ANCHORED`` measurement entry exists under the
#      wave-1 play_id.
#   3. The spec.yaml-declared ``prior_keys`` are a subset of the legacy
#      registry's ``prior_keys``.
#
# If any check fails, the helper raises RuntimeError and the engine refuses
# to start under flag ON — preserving the byte-identical contract by
# refusing to render inconsistent output.
#
# At flag OFF (default at T4 impl) this helper is a no-op: the
# ``plays/`` directory is not consulted; legacy behavior is unchanged.
#
# At flag ON (deferred T4.5 atomic flip) the integrity check fires; if it
# passes, the engine continues with the legacy code path (same Python
# objects in use) and produces byte-identical output. This is the
# refactor-only contract per DS verdict 2026-05-24 §3 Q6 + IM plan
# Part B S8-T4 (zero re-pin target).
# ---------------------------------------------------------------------------


def consult_play_library_if_enabled(cfg: Optional[Dict[str, object]] = None) -> None:
    """Run the Play Library wave-1 integrity check when the flag is ON.

    No-op when ``cfg`` is None or ``ENGINE_V2_PLAY_LIBRARY_WAVE1`` is OFF.

    Raises ``RuntimeError`` if the spec.yaml-resolved callables drift from
    the legacy registry callables (preserves the byte-identical contract
    by refusing to start the engine).
    """
    if not cfg:
        return
    flag = cfg.get("ENGINE_V2_PLAY_LIBRARY_WAVE1")
    if not flag:
        return
    # Deferred import — only when the flag is ON. Avoids any import cost
    # for the default-OFF path.
    from plays import assert_identity_with_legacy  # noqa: WPS433

    assert_identity_with_legacy()
