"""Conservative economic sizing (Milestone 6, T6.2-T6.4).

Replaces the legacy stacked-multiplier ``calculate_28d_revenue`` on the V2
path with an audience-economics formula:

    revenue = audience x p_action x incremental_orders x AOV

Where:

- ``audience``      = number of unique customers in the play's audience.
- ``p_action``      = probability that a customer in the audience takes the
                      target action over the play's window. For
                      measured/directional plays, this comes from the store-
                      observed effect (e.g., observed reactivation rate).
                      For targeting plays, this comes from
                      ``config/priors.yaml`` ranges (p10 -> p90).
- ``incremental_orders`` = expected number of incremental orders per acting
                      customer. Conservative; defaults to 1 unless a prior
                      ``orders_per_customer`` exists.
- ``AOV``           = the store's L28 average order value, supplied by the
                      caller (read from the aligned KPI snapshot).

The output is a typed :class:`~src.engine_run.RevenueRange` with:

- ``p10`` / ``p50`` / ``p90``: low / mid / high revenue, in dollars.
- ``source``: ``store_observed`` (measured / directional with observed
  effect), ``vertical_prior`` (targeting with priors only), or ``blend``
  (rare; e.g., observed conversion + prior orders-per-customer).
- ``drivers``: a list of named, source-labeled provenance entries
  (T6.4). Every non-suppressed range has at least one driver.
- ``suppressed``: True when the dollar range MUST be hidden by the
  renderer:
    * cold-start stores;
    * targeting plays whose vertical prior is NOT ``causal``
      (since the resulting estimate has no defensible measured basis).

Hard rules (T6.3, per the M6 ticket):

- ``cold_start=True``  -> ``suppressed=True``.
- targeting + non-causal prior -> ``suppressed=True`` (unless caller
  explicitly opts in via ``allow_targeting_unsuppressed=True``; only
  used by tests).

This module does NOT mutate any input. ``size_play`` is a pure function.
The legacy ``calculate_28d_revenue`` path is untouched (T6.5). The V2
adapter call site uses ``size_play`` only when ``ENGINE_V2_SIZING=true``;
the default behavior is byte-identical to M5.

Per the M6 plan and memory.md, this code MUST NOT:

- introduce stacked multipliers (e.g., conversion x lift x recovery);
- claim measured uplift it does not have;
- silently fill a missing prior with a heuristic;
- inflate ranges to look more impressive.

When in doubt, suppress.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from .engine_run import Provenance, RevenueRange, RevenueRangeSource, Sensitivity
from .priors_loader import PriorEntry, PriorValidationStatus, get_prior


# ---------------------------------------------------------------------------
# Sprint 7.5 Ticket T3 — pseudo_N policy table + Bayesian blend helper.
#
# Per ARCHITECTURE_PLAN.md Part III-1 §III-1 (founder Q4 locked at
# 30/15/10): the per-status pseudo_N caps the prior's weight on the
# posterior. When ``ENGINE_V2_PRIORS_VALIDATION=true`` the sizing layer
# refuses to blend on ``HEURISTIC_UNVALIDATED`` / ``PLACEHOLDER`` priors.
# The actual posterior math is consumed by Tier-B builders in Sprint 6;
# T3 lands the table + helper as the contract surface so S6 builders
# import a single typed target.
#
# The cap is load-bearing: even when a prior carries ``effective_n``
# (e.g., the bsandco first-to-second_purchase entry with effective_n=
# 156110), the pseudo_N stays at the per-status cap (30 for
# validated_external). The effective_n is metadata for traceability, NOT
# a weight override. See Part III-1 §III-1 "default table" + the T2
# summary §9 risk #5.
# ---------------------------------------------------------------------------

PSEUDO_N_BY_STATUS: Dict[PriorValidationStatus, int] = {
    PriorValidationStatus.VALIDATED_EXTERNAL: 30,
    PriorValidationStatus.VALIDATED_INTERNAL: 15,
    PriorValidationStatus.ELICITED_EXPERT: 10,
}

# Closed set of validation statuses that PERMIT blending under the T3
# refusal rule. ``HEURISTIC_UNVALIDATED`` and ``PLACEHOLDER`` are
# explicitly absent — those trigger refusal, not a downgraded weight.
_BLEND_PERMITTED_STATUSES = frozenset(PSEUDO_N_BY_STATUS.keys())


def effective_pseudo_n(
    status: PriorValidationStatus,
    *,
    store_profile: Optional[Any] = None,
    profile_flag_on: bool = False,
) -> int:
    """Return the cold-start blend weight for one ``PriorValidationStatus``.

    Sprint 6.5 Ticket T4 contract:

    - ``HEURISTIC_UNVALIDATED`` / ``PLACEHOLDER`` → 0 (validated-path
      refusal logic in S7.5-T3 still owns the outright refusal; this
      helper is consulted only INSIDE the validated path).
    - Validated statuses → status-cap from ``PSEUDO_N_BY_STATUS``.
    - When ``profile_flag_on`` is True AND ``store_profile`` carries a
      typed ``GateCalibration.pseudo_n_default``, the effective weight
      is ``min(status_cap, profile_default)`` — the profile can only
      LOWER the weight, never raise it above the per-status cap
      (Part III-1 pseudo_N policy invariant).
    """

    status_cap = int(PSEUDO_N_BY_STATUS.get(status, 0))
    if not profile_flag_on or store_profile is None:
        return status_cap
    if status not in _BLEND_PERMITTED_STATUSES:
        # Heuristic/placeholder still refuses — profile does NOT relax
        # the S7.5-T3 refusal logic.
        return status_cap
    gc = getattr(store_profile, "gate_calibration", None)
    if gc is None:
        return status_cap
    profile_pn = getattr(gc, "pseudo_n_default", None)
    if profile_pn is None:
        return status_cap
    try:
        pn = int(profile_pn)
    except (TypeError, ValueError):
        return status_cap
    if pn <= 0:
        return status_cap
    return min(status_cap, pn)


def bayesian_blend(
    prior_value: float,
    pseudo_n: int,
    store_value: float,
    n_observed: int,
) -> float:
    """Return the Bayesian-posterior blend of a prior and a store observation.

    Formula::

        posterior = (pseudo_n * prior_value + n_observed * store_value)
                    / (pseudo_n + n_observed)

    Per Part III-1's pseudo_N policy: ``pseudo_n`` is the per-status cap
    (see :data:`PSEUDO_N_BY_STATUS`). ``n_observed`` is the store's
    measured n underlying ``store_value``. When ``n_observed`` is zero
    the posterior collapses to the prior; when ``n_observed`` dwarfs
    ``pseudo_n`` the posterior collapses to the store value.

    Returns a non-negative ``float``. Pure function; never raises.

    Sprint 7.5 Ticket T3 ships this helper as the contract surface for
    Sprint 6 Tier-B builders. T3 itself does NOT call ``bayesian_blend``
    from ``size_play`` — the current sizing path computes range-as-prior
    (p10/p50/p90) for the base_rate driver, not a single posterior.
    The helper is exported here so S6 builders import one target.
    """

    p_n = max(0, int(pseudo_n))
    n_obs = max(0, int(n_observed))
    pv = max(0.0, float(prior_value))
    sv = max(0.0, float(store_value))
    denom = p_n + n_obs
    if denom <= 0:
        # Pathological: both weights zero. Fall back to the conservative
        # arithmetic mean rather than dividing by zero or raising.
        return (pv + sv) / 2.0
    return (p_n * pv + n_obs * sv) / float(denom)


# ---------------------------------------------------------------------------
# Sprint 8 Ticket T2 — typed Sensitivity helper.
#
# Reuses :func:`bayesian_blend` and the same ``audience * posterior * aov``
# revenue formula that :func:`measurement_builder.build_prior_anchored_play_card`
# uses to compute the live ``revenue_range``. No parallel sizing math: a
# Sensitivity scenario IS a re-blend of the live posterior with one input
# perturbed, plumbed through the identical revenue formula. This keeps the
# block honest as the EB blend layer evolves at S8-T3.
#
# Each scenario perturbs exactly one input:
#   - observed_n halved -> re-blend at ``n_observed // 2``
#   - observed_n doubled -> re-blend at ``n_observed * 2``
#   - prior shifted down -> re-blend at ``prior_value * 0.75``
#   - prior shifted up -> re-blend at ``prior_value * 1.25``
#
# The ±25% prior shift is a documented neutral default; the IM plan Part B
# S8-T2 left the magnitude open ("±1 σ") but the prior carries no σ at the
# helper interface — only point + range_p10/range_p90 envelope, and
# range_p10/range_p90 are already surfaced on the live revenue_range. A
# percent-shift is the cleanest perturbation that does not require the
# helper to reach back into the prior envelope. If beta merchant feedback
# wants a different perturbation magnitude, this is a one-line edit
# captured by KI-NEW-Q (proposed).
# ---------------------------------------------------------------------------


def _revenue_range_from_blend(
    *,
    prior_value: float,
    pseudo_n: int,
    store_value: float,
    n_observed: int,
    prior_range_p10: float,
    prior_range_p90: float,
    audience_size: int,
    aov: float,
) -> Optional[RevenueRange]:
    """Apply the canonical Tier-B revenue formula to a re-blended posterior.

    Mirrors the math in
    :func:`measurement_builder.build_prior_anchored_play_card` (the
    validated, non-suppressed branch at L2356-2412):

        posterior = bayesian_blend(prior_value, pseudo_n, store_value, n_observed)
        rev_p10  = audience * max(0, prior.range_p10) * aov
        rev_p50  = audience * posterior * aov  (lower-bounded by rev_p10)
        rev_p90  = audience * max(p50/au/aov, prior.range_p90) * aov

    Returns ``None`` when audience or aov are non-positive (no meaningful
    revenue projection); otherwise returns a :class:`RevenueRange` with
    ``source = BLEND`` and an empty drivers list (Sensitivity scenarios
    are not surfaced via drivers — the Sensitivity block IS the surface).
    """
    if audience_size <= 0 or aov <= 0.0:
        return None
    posterior = bayesian_blend(
        prior_value=float(prior_value),
        pseudo_n=int(pseudo_n),
        store_value=float(store_value),
        n_observed=int(n_observed),
    )
    p10 = max(0.0, float(prior_range_p10))
    p50 = float(posterior)
    p90 = max(p50, float(prior_range_p90))
    rev_p10 = round(audience_size * p10 * aov, 2)
    rev_p50 = round(max(rev_p10, audience_size * p50 * aov), 2)
    rev_p90 = round(max(rev_p50, audience_size * p90 * aov), 2)
    return RevenueRange(
        p10=rev_p10,
        p50=rev_p50,
        p90=rev_p90,
        source=RevenueRangeSource.BLEND,
        drivers=[],
        suppressed=False,
    )


def compute_sensitivity(
    *,
    prior_value: float,
    prior_range_p10: float,
    prior_range_p90: float,
    pseudo_n: int,
    store_value: float,
    n_observed: int,
    audience_size: int,
    aov: float,
) -> Sensitivity:
    """Produce the typed Sensitivity block for a validated, non-suppressed
    Tier-B prior-anchored PlayCard.

    Inputs mirror :func:`bayesian_blend` plus the audience / aov / prior
    envelope that the live ``revenue_range`` math reads. The four
    scenarios re-run the blend with one perturbation each (per the
    module docstring above); ``pseudo_n_used`` records the per-status /
    profile-capped pseudo_n that the live posterior used.

    Degenerate scenarios (e.g. ``n_observed == 0`` halves to 0;
    ``prior_value == 0`` shift produces an identical posterior) are
    surfaced as either a valid RevenueRange (when the math still
    produces a meaningful envelope) or a documented note. The block
    itself always returns a :class:`Sensitivity` instance — callers
    decide whether to attach it to the PlayCard based on the upstream
    flag + suppression gates.
    """

    notes: List[str] = []

    # observed_n halved scenario. Integer floor to honor the
    # ``int(n_observed)`` convention of bayesian_blend. n=0 halves to 0
    # which is the cold-start collapse-to-prior case; we still emit the
    # range (it equals the prior-range projection), with a note.
    n_halved = max(0, int(n_observed) // 2)
    if int(n_observed) == 0:
        notes.append("observed_n=0; halved/doubled scenarios collapse to prior")
    scen_n_halved = _revenue_range_from_blend(
        prior_value=prior_value,
        pseudo_n=pseudo_n,
        store_value=store_value,
        n_observed=n_halved,
        prior_range_p10=prior_range_p10,
        prior_range_p90=prior_range_p90,
        audience_size=audience_size,
        aov=aov,
    )

    # observed_n doubled scenario.
    n_doubled = max(0, int(n_observed)) * 2
    scen_n_doubled = _revenue_range_from_blend(
        prior_value=prior_value,
        pseudo_n=pseudo_n,
        store_value=store_value,
        n_observed=n_doubled,
        prior_range_p10=prior_range_p10,
        prior_range_p90=prior_range_p90,
        audience_size=audience_size,
        aov=aov,
    )

    # prior_value shifted -25% scenario. Floor at 0 (bayesian_blend
    # already clamps non-negative; explicit here for readability).
    prior_down = max(0.0, float(prior_value) * 0.75)
    if float(prior_value) <= 0.0:
        notes.append("prior_value<=0; shifted scenarios are degenerate")
    scen_prior_down = _revenue_range_from_blend(
        prior_value=prior_down,
        pseudo_n=pseudo_n,
        store_value=store_value,
        n_observed=n_observed,
        prior_range_p10=prior_range_p10,
        prior_range_p90=prior_range_p90,
        audience_size=audience_size,
        aov=aov,
    )

    # prior_value shifted +25% scenario.
    prior_up = max(0.0, float(prior_value) * 1.25)
    scen_prior_up = _revenue_range_from_blend(
        prior_value=prior_up,
        pseudo_n=pseudo_n,
        store_value=store_value,
        n_observed=n_observed,
        prior_range_p10=prior_range_p10,
        prior_range_p90=prior_range_p90,
        audience_size=audience_size,
        aov=aov,
    )

    return Sensitivity(
        scenario_observed_n_halved=scen_n_halved,
        scenario_observed_n_doubled=scen_n_doubled,
        scenario_prior_shifted_down=scen_prior_down,
        scenario_prior_shifted_up=scen_prior_up,
        pseudo_n_used=max(0, int(pseudo_n)),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Sprint 8 Ticket T3 — typed Provenance audit object helper.
#
# Formalizes the empirical-Bayes blend audit contract surface. Per DS
# verdict 2026-05-24 §1 + §2, the blend math itself is ALREADY SHIPPED
# (S7.5-T3, lines 87-91 + 99-139 + 142-179 above); S8-T3 does NOT add
# new pseudo_N numbers, a new ``Prior.pseudo_N`` per-prior override field
# (§6 F2 rejected), or a new ``RevenueRange.source`` literal (Q5 closed —
# reuse ``blend``). The helper below reuses :func:`effective_pseudo_n` to
# compute ``pseudo_n_used`` and the locked :data:`PSEUDO_N_BY_STATUS`
# table to compute ``pseudo_n_cap`` — no parallel pseudo_N policy.
#
# Refusal contract (DS §5 invariant 2): callers must NOT invoke this
# helper on ``HEURISTIC_UNVALIDATED`` / ``PLACEHOLDER`` priors. Those
# refuse blend at the routing seam (suppressed revenue range; no
# posterior; no audit object to emit). The production callsite at
# :func:`measurement_builder.build_prior_anchored_play_card` only invokes
# this helper on the validated, non-suppressed BLEND path; the helper
# itself returns ``None`` if a refused status leaks through, defending
# the invariant.
# ---------------------------------------------------------------------------


def compute_provenance(
    *,
    prior: PriorEntry,
    prior_key: str,
    observed_n: int,
    store_profile: Optional[Any] = None,
    profile_flag_on: bool = False,
) -> Optional[Provenance]:
    """Produce the typed :class:`Provenance` audit object for one prior-anchored,
    validated, non-suppressed BLEND PlayCard.

    Inputs mirror the bayesian_blend / effective_pseudo_n contract the
    live posterior consumes; the helper does NOT re-derive the blend
    math, only reports what the live blend used. ``pseudo_n_used`` is
    computed via :func:`effective_pseudo_n` (reuses the per-status cap +
    optional store-profile lowering); ``pseudo_n_cap`` is read directly
    from :data:`PSEUDO_N_BY_STATUS`.

    Returns ``None`` when the prior's ``validation_status`` is not in
    :data:`_BLEND_PERMITTED_STATUSES` (HEURISTIC_UNVALIDATED + PLACEHOLDER
    refusal — DS §5 invariant 2). The production callsite guards on this
    upstream; the helper-side guard is a defense-in-depth pin.

    The weights satisfy ``weight_observed + weight_prior == 1.0`` when
    the denominator is positive. Pathological case (both
    ``pseudo_n_used`` and ``observed_n`` zero) produces 0.5 / 0.5 to
    mirror :func:`bayesian_blend`'s arithmetic-mean fallback.

    DS verdict 2026-05-24 §5 invariant 5 pin: ``pseudo_n_used`` MUST NOT
    exceed ``pseudo_n_cap``. :func:`effective_pseudo_n` already enforces
    this (``min(status_cap, profile_default)``); this helper does not
    re-derive.
    """
    status = prior.validation_status
    if status not in _BLEND_PERMITTED_STATUSES:
        # DS §5 invariant 2 refusal: never emit an audit object for a
        # refused status. Callers should already have routed the card to
        # suppressed; defense-in-depth here.
        return None

    pseudo_n_cap = int(PSEUDO_N_BY_STATUS.get(status, 0))
    pseudo_n_used = int(
        effective_pseudo_n(
            status,
            store_profile=store_profile,
            profile_flag_on=profile_flag_on,
        )
    )
    obs_n = max(0, int(observed_n or 0))
    denom = pseudo_n_used + obs_n
    if denom <= 0:
        # Mirrors bayesian_blend's arithmetic-mean fallback when both
        # weights are zero. Documented as a degenerate case in notes.
        weight_observed = 0.5
        weight_prior = 0.5
    else:
        weight_observed = float(obs_n) / float(denom)
        weight_prior = float(pseudo_n_used) / float(denom)

    notes: List[str] = []
    if obs_n == 0:
        notes.append("observed_n=0; posterior collapses to prior (cold-start)")
    if (
        profile_flag_on
        and store_profile is not None
        and pseudo_n_used < pseudo_n_cap
    ):
        notes.append(
            f"pseudo_n_used={pseudo_n_used} lowered below per-status cap "
            f"{pseudo_n_cap} by store_profile.gate_calibration.pseudo_n_default"
        )

    # Document the provenance source the reviewer should pull up. Prefer
    # the source_artifact path (e.g. ``config/priors_sources/<file>.md``)
    # when set; fall back to source_class (free-text) so the audit object
    # always carries something traceable.
    prior_source = (
        str(prior.source_artifact)
        if prior.source_artifact
        else str(prior.source_class or "")
    )
    prior_play_id = str(prior.play_id or prior.name or "")

    return Provenance(
        prior_play_id=prior_play_id,
        prior_key=str(prior_key or ""),
        validation_status=status.value,
        pseudo_n_used=pseudo_n_used,
        pseudo_n_cap=pseudo_n_cap,
        observed_n=obs_n,
        weight_observed=round(weight_observed, 6),
        weight_prior=round(weight_prior, 6),
        prior_source=prior_source,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Sizing input bundle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SizingInputs:
    """Typed inputs to :func:`size_play`.

    Construct this from the V2 adapter call-site. Keeping the inputs in
    one struct keeps the sizing function pure and easy to test.

    Fields:
        play_id:           registry-id of the play being sized.
        evidence_class:    one of "measured" | "directional" | "targeting"
                           | "weak". String form (M2 contract).
        audience_size:     number of customers in the play's audience.
        aov:               store-level L28 AOV in dollars.
        observed_effect:   store-observed effect, if available. For
                           measured/directional plays this is the
                           probability used as ``p_action`` (e.g.,
                           reactivation rate). ``None`` for targeting
                           and any play that does not yet measure.
        observed_metric_name: optional human-readable metric name used
                           as the driver name when ``observed_effect``
                           is supplied (e.g., ``"reactivation_rate"``).
        observed_n:        n underlying ``observed_effect`` (for the
                           driver provenance line).
        vertical:          vertical scope for prior lookup (e.g., "beauty").
        subvertical:       optional finer-grained scope.
        cold_start:        True if the store is cold-start. Forces
                           ``suppressed=True``.
        allow_targeting_unsuppressed: tests-only escape hatch. False
                           in production. When False, targeting plays
                           whose prior source_class != "causal" are
                           suppressed per T6.3.
    """

    play_id: str
    evidence_class: str
    audience_size: int
    aov: float
    observed_effect: Optional[float] = None
    observed_metric_name: Optional[str] = None
    observed_n: Optional[int] = None
    vertical: Optional[str] = None
    subvertical: Optional[str] = None
    cold_start: bool = False
    allow_targeting_unsuppressed: bool = False
    # Sprint 7.5 Ticket T3: when True, sizing applies the validation-status
    # refusal rule (refuse blend on ``HEURISTIC_UNVALIDATED`` /
    # ``PLACEHOLDER`` priors and route the play to suppression with
    # reason ``prior_unvalidated``). Default False preserves the M6/T6.3
    # ``source_class != causal -> suppressed`` rule byte-identically. The
    # caller in :mod:`src.main` reads ``cfg["ENGINE_V2_PRIORS_VALIDATION"]``
    # and threads it through. The flag is per-call so unit tests can pin
    # both branches without monkeypatching :mod:`src.utils`.
    priors_validation_enabled: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _driver(name: str, value: Any, source: str, **extras: Any) -> Dict[str, Any]:
    """Build one ``revenue_range.drivers[]`` entry.

    Each driver is named (``name``) and source-labeled (``source``).
    Per the M6 plan T6.4: drivers are the ML hook for future
    realized-vs-predicted analysis (M9 reads them).
    """

    out: Dict[str, Any] = {"name": name, "source": source}
    if value is not None:
        out["value"] = value
    out.update(extras)
    return out


def _pct_for_p10_p90(prior: PriorEntry) -> tuple[float, float, float]:
    """Return ``(p10, p50, p90)`` in [0,1] order from a numeric prior.

    Defensive: clamps to non-negative and ensures the trio is monotonic.
    The YAML schema test already enforces ``range_p10 <= value <= range_p90``,
    but we belt-and-braces here in case a future schema change relaxes it.
    """

    p10 = max(0.0, float(prior.range_p10))
    p50 = max(p10, float(prior.value))
    p90 = max(p50, float(prior.range_p90))
    return p10, p50, p90


def _suppressed_range(reason: str, drivers: List[Dict[str, Any]]) -> RevenueRange:
    """Return a suppressed :class:`RevenueRange` with provenance preserved.

    Per the contract, ``suppressed=True`` ⇒ renderer hides $. We still
    populate ``drivers`` so receipts and the future ML hook can see why
    the range was suppressed (the driver list is the audit trail).

    S13.6-T7a (DS adjudication 2026-06-01 + founder approved
    2026-06-01): the legacy ``reason`` string is wrapped in the closed-
    set :class:`RevenueRangeSuppressionReason` enum at this seam per
    DS Q1 (NO producer rewrites). The 7 in-tree producer-site strings
    match enum member values byte-for-byte. The legacy
    ``targeting_non_causal_prior`` string is structurally unreachable
    under ``ENGINE_V2_PRIORS_VALIDATION=true`` (default at S7.5-T3.5);
    when emitted it maps to ``OBSERVED_EFFECT_INVALID`` defensively
    per DS Q1 ("if reachable populate OBSERVED_EFFECT_INVALID; file
    cleanup KI for S13.7 dead-code sweep").
    """

    # Local import to avoid bumping module-import surface; the enum is
    # the schema-authority surface in src/engine_run.py.
    from .engine_run import RevenueRangeSuppressionReason as _RRSR

    # TODO(S13.7-cleanup): legacy producer string
    # ``targeting_non_causal_prior`` is dead-code under
    # ENGINE_V2_PRIORS_VALIDATION=true per DS adjudication 2026-06-01.
    # Maps to OBSERVED_EFFECT_INVALID defensively here; remove the
    # producer site at L744 in the S13.7 dead-code sweep.
    if reason == "targeting_non_causal_prior":
        enum_reason: Optional[_RRSR] = _RRSR.OBSERVED_EFFECT_INVALID
    else:
        try:
            enum_reason = _RRSR(reason)
        except ValueError:
            # Defensive: if a new producer adds a string before the
            # enum learns it, fall through with reason=None and let
            # the AST sweep / round-trip test catch the regression.
            # Pivot 7 single-demote-channel invariant is unaffected.
            enum_reason = None

    return RevenueRange(
        p10=None,
        p50=None,
        p90=None,
        source=None,
        drivers=drivers
        + [_driver("suppression_reason", reason, source="sizing_v2", reason=reason)],
        suppressed=True,
        suppression_reason=enum_reason,
    )


# ---------------------------------------------------------------------------
# Core: size_play
# ---------------------------------------------------------------------------


def size_play(inputs: SizingInputs) -> RevenueRange:
    """Compute a conservative revenue_range for one play.

    Returns a :class:`RevenueRange`. Never raises. On any uncertainty
    (cold start, missing prior, zero audience) the range is suppressed
    rather than guessed.

    Conservative-suppression policy (T6.3):
        - ``cold_start=True``       -> suppressed=True
        - audience_size <= 0        -> suppressed=True
        - aov <= 0                  -> suppressed=True
        - targeting + prior source_class != causal -> suppressed=True
          (unless ``allow_targeting_unsuppressed=True``)

    Sizing policy:
        - measured/directional with ``observed_effect``:
              p_action_p10 = p_action_p50 = p_action_p90 = observed_effect
          The range comes from incremental_orders prior alone (or, if
          unavailable, both p10/p90 collapse to the point estimate).
          Driver: ``observed_<metric>`` (source=store_observed).
        - targeting (causal-only by default suppressed; otherwise):
              p_action_p10/p50/p90 = prior.range_p10/value/range_p90
              from base_rate prior under (vertical[, subvertical]).
              Driver: ``base_rate`` (source=vertical_prior).
        - incremental_orders prior optional; defaults to 1.0 across
          p10/p50/p90 if no ``orders_per_customer`` prior exists.
        - Source label:
              store_observed if p_action came from observed_effect AND
                  no prior was used to widen the range;
              vertical_prior if p_action came from priors only;
              blend if observed_effect was used for p_action AND a
                  prior was used for incremental_orders.
    """

    drivers: List[Dict[str, Any]] = []

    # -- input sanity ------------------------------------------------------
    audience = max(0, int(inputs.audience_size or 0))
    aov = _safe_float(inputs.aov) or 0.0
    drivers.append(_driver("audience_size", audience, source="store_observed"))
    drivers.append(_driver("aov", round(aov, 2), source="store_observed", window="L28"))

    # T6.3: cold-start always suppressed.
    if inputs.cold_start:
        return _suppressed_range("cold_start", drivers)

    if audience <= 0:
        return _suppressed_range("audience_zero", drivers)
    if aov <= 0:
        return _suppressed_range("aov_zero", drivers)

    ec = (inputs.evidence_class or "").lower()

    # -- p_action --------------------------------------------------------
    p_action_p10: Optional[float] = None
    p_action_p50: Optional[float] = None
    p_action_p90: Optional[float] = None
    p_action_source: Optional[str] = None  # "store_observed" | "vertical_prior"

    if ec in ("measured", "directional") and inputs.observed_effect is not None:
        eff = _safe_float(inputs.observed_effect)
        if eff is None or eff < 0:
            return _suppressed_range("observed_effect_invalid", drivers)
        # Conservative point: do NOT widen with a prior. Range collapses
        # unless an incremental-orders prior is present below.
        p_action_p10 = p_action_p50 = p_action_p90 = float(eff)
        p_action_source = "store_observed"
        drivers.append(
            _driver(
                inputs.observed_metric_name or "observed_effect",
                round(float(eff), 6),
                source="store_observed",
                n=inputs.observed_n,
            )
        )
    else:
        # Targeting (or measured/directional without an observed effect).
        prior = get_prior(
            inputs.play_id,
            vertical=inputs.vertical,
            subvertical=inputs.subvertical,
            key="base_rate",
        )
        if prior is None:
            return _suppressed_range("no_prior_base_rate", drivers)
        if ec == "targeting":
            # Sprint 7.5 Ticket T3: validation-status refusal rule (flag-gated).
            # When ``priors_validation_enabled`` is True the rule
            # GENERALISES (and replaces) the legacy ``source_class !=
            # causal`` rule per Part III-1 §III-1 Step 5. Specifically:
            #
            #   - validation_status in {heuristic_unvalidated, placeholder}
            #       => refuse blend, suppress with reason
            #          ``prior_unvalidated``.
            #   - validation_status in {validated_external,
            #          validated_internal, elicited_expert}
            #       => blend permitted; source_class no longer gates.
            #
            # This is the load-bearing change of T3.5 (the flag flip) —
            # the 3 T2-promoted validated_external priors are
            # observational (not causal), so the legacy rule would still
            # suppress them; under the new flag-on rule, they survive.
            if inputs.priors_validation_enabled:
                if (
                    prior.validation_status not in _BLEND_PERMITTED_STATUSES
                    and not inputs.allow_targeting_unsuppressed
                ):
                    drivers.append(
                        _driver(
                            "base_rate",
                            round(float(prior.value), 6),
                            source="vertical_prior",
                            source_class=prior.source_class,
                            validation_status=prior.validation_status.value,
                            applies_to=dict(prior.applies_to or {}),
                        )
                    )
                    return _suppressed_range("prior_unvalidated", drivers)
                # Else: validation_status is in the blend-permitted set;
                # SKIP the legacy ``source_class != causal`` rule. Fall
                # through to the prior-driven range population below.
            elif prior.source_class != "causal" and not inputs.allow_targeting_unsuppressed:
                # Still record the prior in drivers so receipts know which
                # prior would have been used.
                drivers.append(
                    _driver(
                        "base_rate",
                        round(float(prior.value), 6),
                        source="vertical_prior",
                        source_class=prior.source_class,
                        applies_to=dict(prior.applies_to or {}),
                    )
                )
                return _suppressed_range("targeting_non_causal_prior", drivers)
        p10, p50, p90 = _pct_for_p10_p90(prior)
        p_action_p10, p_action_p50, p_action_p90 = p10, p50, p90
        p_action_source = "vertical_prior"
        drivers.append(
            _driver(
                "base_rate",
                round(float(p50), 6),
                source="vertical_prior",
                source_class=prior.source_class,
                p10=round(p10, 6),
                p90=round(p90, 6),
                applies_to=dict(prior.applies_to or {}),
            )
        )

    # -- incremental_orders ---------------------------------------------
    # Conservative default: 1 incremental order per acting customer.
    inc_p10 = inc_p50 = inc_p90 = 1.0
    inc_prior = get_prior(
        inputs.play_id,
        vertical=inputs.vertical,
        subvertical=inputs.subvertical,
        key="orders_per_customer",
    )
    used_inc_prior = False
    if inc_prior is not None:
        ip10, ip50, ip90 = _pct_for_p10_p90(inc_prior)
        # Conservative: incremental_orders > 1 is allowed but the
        # incremental piece (order-count above 1) is what we apply.
        # Modeling: if a prior is supplied, use it directly as the
        # multiplier on (audience x p_action x AOV). This matches the
        # winback-style legacy formula.
        inc_p10, inc_p50, inc_p90 = ip10, ip50, ip90
        used_inc_prior = True
        drivers.append(
            _driver(
                "incremental_orders",
                round(float(ip50), 4),
                source="vertical_prior",
                source_class=inc_prior.source_class,
                p10=round(ip10, 4),
                p90=round(ip90, 4),
                applies_to=dict(inc_prior.applies_to or {}),
            )
        )
    else:
        drivers.append(
            _driver(
                "incremental_orders",
                1.0,
                source="default",
                note="no orders_per_customer prior; conservative default 1.0",
            )
        )

    # -- assemble revenue ------------------------------------------------
    # Do not stack additional multipliers (incrementality, frequency lift,
    # etc.). Memory.md and the M6 plan explicitly forbid that. Each prior
    # used here is named in drivers[] so the source can be audited.
    rev_p10 = float(audience) * p_action_p10 * inc_p10 * aov
    rev_p50 = float(audience) * p_action_p50 * inc_p50 * aov
    rev_p90 = float(audience) * p_action_p90 * inc_p90 * aov

    # Belt-and-braces: enforce monotonic p10 <= p50 <= p90 (rounded).
    rev_p10 = round(max(0.0, rev_p10), 2)
    rev_p50 = round(max(rev_p10, rev_p50), 2)
    rev_p90 = round(max(rev_p50, rev_p90), 2)

    # -- source label ----------------------------------------------------
    if p_action_source == "store_observed" and used_inc_prior:
        source = RevenueRangeSource.BLEND
    elif p_action_source == "store_observed":
        source = RevenueRangeSource.STORE_OBSERVED
    else:
        source = RevenueRangeSource.VERTICAL_PRIOR

    return RevenueRange(
        p10=rev_p10,
        p50=rev_p50,
        p90=rev_p90,
        source=source,
        drivers=drivers,
        suppressed=False,
    )


# ---------------------------------------------------------------------------
# Convenience: shadow comparison (T6.6)
# ---------------------------------------------------------------------------


def shadow_compare(
    legacy_expected_dollars: Optional[float],
    v2_range: Optional[RevenueRange],
) -> Dict[str, Any]:
    """Build a per-play shadow-comparison record (T6.6).

    Returns a dict the V2 adapter writes into
    ``receipts/v2_sizing_shadow.json`` so reviewers can inspect
    ``legacy_$`` vs ``v2_p50`` (and the ratio) per fixture without
    affecting the merchant briefing.

    Per the M6 acceptance criterion: "V2 p50 should be smaller than
    legacy on heuristic plays (because legacy multiplied by Klaviyo
    benchmarks); approximately equal on measured plays."
    """

    legacy = _safe_float(legacy_expected_dollars)
    v2_p50 = _safe_float(v2_range.p50) if v2_range is not None else None
    suppressed = bool(v2_range.suppressed) if v2_range is not None else None
    source = (
        v2_range.source.value if (v2_range is not None and v2_range.source is not None) else None
    )
    ratio: Optional[float] = None
    if legacy is not None and v2_p50 is not None and legacy > 0:
        ratio = round(v2_p50 / legacy, 4)
    return {
        "legacy_expected_dollars": legacy,
        "v2_p10": _safe_float(v2_range.p10) if v2_range is not None else None,
        "v2_p50": v2_p50,
        "v2_p90": _safe_float(v2_range.p90) if v2_range is not None else None,
        "v2_source": source,
        "v2_suppressed": suppressed,
        "ratio_v2_over_legacy": ratio,
    }


__all__ = [
    "SizingInputs",
    "size_play",
    "shadow_compare",
    "bayesian_blend",
    "PSEUDO_N_BY_STATUS",
    "effective_pseudo_n",
    "compute_sensitivity",
    "compute_provenance",
]
