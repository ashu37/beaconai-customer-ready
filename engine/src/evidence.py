"""Evidence classification module (Milestones 4a + 4b).

This module owns the deterministic boundary at which a candidate's
``evidence_class`` is decided, the NaN-handling invariant the DS Architect
QA Change 3 specified, and (M4b) the ``consistency_across_windows``
robustness signal that sits alongside ``combine_multiwindow_statistics``.

Contract (DS Architect QA Change 3, frozen in memory.md):

* A NaN p-value combined with an ``evidence_class == "targeting"`` candidate
  deterministically maps to ``Targeting``. This is the EXPECTED state for
  fabricated-stat plays once the M4a flag NaNs out their hardcoded p/effect/CI
  constants.
* A NaN p-value combined with an ``evidence_class == "measured"`` candidate
  represents an ENGINE BUG. The classifier must raise rather than silently
  downgrade; downgrading would let a buggy detector smuggle a measured play
  through the gate path with no statistical evidence at all.

M4b additions:

* ``TARGETING_RECLASSIFY_PLAYS`` — frozenset of play_ids that the engine
  must deterministically classify as ``targeting`` regardless of whether
  the legacy emitter computed any p/effect/CI for them. This is the
  T4b.1 reclassification list. It is consumed by ``action_engine`` when
  ``STATS_NAN_FOR_HARDCODED`` and ``EVIDENCE_CLASS_ENFORCED`` are both
  on.
* ``compute_consistency_across_windows(window_results, combined_effect)``
  — the load-bearing T4b.2 / DS Architect QA Change 1 specification.
  See its docstring for the exact formula. It is a **pre-combination
  sign-agreement count**, NOT a post-combination p-vote. It is used as a
  robustness signal alongside ``combine_multiwindow_statistics``; it
  must NOT be used to upgrade a play's evidence class and must NOT be
  multiplied into confidence as if it were a separate test.

The module imports ``play_registry.PLAYS`` to look up
``evidence_class_default``, and ``engine_run.EvidenceClass`` for the typed
return value. It does NOT import from ``action_engine`` (leaf-level guarantee
preserved from M2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .engine_run import EvidenceClass
from .play_registry import PLAYS, PlayDef


# ---------------------------------------------------------------------------
# T4b.1 — Targeting reclassification list.
#
# Plays in this set are deterministically classified as ``targeting`` by the
# engine when the M4b flags are on, regardless of any computed p/effect/CI.
# Their ``measurement.*`` block must be ``None`` in the EngineRun mapper.
#
# Source: implementation-manager-overhaul-plan-final.md, T4b.1.
#
# Note: the registry default for ``empty_bottle`` is ``directional`` (it has
# a measured reorder_rate). T4b.1 explicitly overrides that here because the
# legacy emitter today fabricates the effect_abs constant; until the emitter
# is rewritten to use a defensible directional measurement, the play must be
# served as ``targeting``.
#
# ``vip_no_discount_nurture`` and ``replenishment_reminder`` are listed in
# T4b.1 but are NOT currently emitted by ``_compute_candidates`` (the
# legacy emitter uses ``empty_bottle`` for replenishment). They are kept in
# the set as a defensive guard so that if/when those play_ids are added to
# the emitter, they are reclassified by default rather than silently
# inheriting an unreviewed default.
# ---------------------------------------------------------------------------

TARGETING_RECLASSIFY_PLAYS: frozenset = frozenset({
    "subscription_nudge",
    "routine_builder",
    "empty_bottle",
    "category_expansion",
    "bestseller_amplify",
    "vip_no_discount_nurture",
    "replenishment_reminder",
})


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EvidenceClassificationError(ValueError):
    """Raised when a candidate violates the M4a evidence-classification invariants.

    The most important case is NaN-p with ``evidence_class == "measured"``: a
    measured play with no p-value indicates the detector or stats path failed
    silently, and the engine must surface the failure rather than render a
    "measured" card with nothing behind it.
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_nan(value: Any) -> bool:
    """Return True if ``value`` is a NaN float, otherwise False.

    None, ints, strings, and finite floats all return False. Non-numeric
    values are treated as "not NaN" for classification purposes; the caller
    is responsible for upstream validation.
    """

    if value is None:
        return False
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return math.isnan(f)


def _coerce_evidence_class(value: Any, *, fallback: EvidenceClass) -> EvidenceClass:
    """Coerce a string or EvidenceClass value into the typed enum.

    Unknown strings fall back to ``fallback`` to keep the function total. The
    caller is expected to pass a valid value; this helper exists so tests can
    exercise the function with raw strings without ceremony.
    """

    if isinstance(value, EvidenceClass):
        return value
    if isinstance(value, str):
        try:
            return EvidenceClass(value)
        except ValueError:
            return fallback
    return fallback


# ---------------------------------------------------------------------------
# classify_evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceContext:
    """Inputs to ``classify_evidence`` packaged as a typed record.

    A dict-like ``candidate`` is also accepted by the wrapper below; this
    dataclass exists for tests that want to build an explicit, minimal
    context without committing to the legacy candidate dict shape.
    """

    play_id: str
    p_value: Any = None
    effect_abs: Any = None
    ci_low: Any = None
    ci_high: Any = None


def classify_evidence(
    candidate: Mapping[str, Any] | EvidenceContext,
    registry: Optional[Dict[str, PlayDef]] = None,
) -> EvidenceClass:
    """Map a candidate to its M4a evidence class.

    Parameters
    ----------
    candidate:
        Either a legacy candidate dict (see ``_compute_candidates`` in
        ``action_engine``) carrying at minimum ``play_id`` and optionally
        ``p``/``effect_abs``/``ci_low``/``ci_high`` keys, or an
        ``EvidenceContext`` instance.
    registry:
        Optional override for the play registry. Defaults to
        ``play_registry.PLAYS``. Tests pass a custom registry to exercise
        unknown play_ids and to confirm the registry is the source of truth.

    Returns
    -------
    EvidenceClass
        The deterministic class for this candidate in M4a:

        * ``EvidenceClass.TARGETING`` if the registry default is
          ``"targeting"``, regardless of whether p/effect/CI are NaN.
        * ``EvidenceClass.TARGETING`` if the registry default is
          ``"measured"`` or ``"directional"`` BUT the candidate has a NaN
          p-value AND an unknown play_id (defensive default; see below).
          For known measured plays with NaN p, the function raises.
        * Otherwise the registry default (measured or directional).

    Raises
    ------
    EvidenceClassificationError
        If ``candidate`` has a NaN p-value AND its registry default is
        ``"measured"``. This signals an engine bug — a measured play with
        no statistic must surface as a failure, not a silent targeting
        downgrade. (DS Architect QA Change 3.)
    EvidenceClassificationError
        If ``candidate`` is missing ``play_id`` entirely.

    Notes
    -----
    The M4a invariants are:

    1. Targeting NaN-p is expected and OK.
    2. Measured NaN-p is an engine bug; raise.
    3. Directional NaN-p is treated like measured-NaN (raises) because a
       directional class still implies an observed effect; the "no measurement"
       boundary applies. M4b may relax this if the directional contract
       becomes "p may be absent if a |t-stat| is present"; it does not yet.
    """

    if isinstance(candidate, EvidenceContext):
        play_id = candidate.play_id
        p_value = candidate.p_value
    else:
        play_id = candidate.get("play_id")
        p_value = candidate.get("p")
    if not play_id or not isinstance(play_id, str):
        raise EvidenceClassificationError(
            "classify_evidence requires a non-empty play_id; got "
            f"{play_id!r}"
        )

    reg = registry if registry is not None else PLAYS
    play_def = reg.get(play_id)
    if play_def is None:
        # Unknown play_id: defensive default. M2 registry sanity test guarantees
        # every legacy emitter is registered, so reaching this branch implies a
        # new emitter that bypassed registration. We do not raise here because
        # M4a is additive and must not break the legacy path; the registry test
        # is the forcing function for engineering hygiene.
        return EvidenceClass.TARGETING

    default_class = _coerce_evidence_class(
        play_def.evidence_class_default, fallback=EvidenceClass.TARGETING
    )

    p_is_nan = _is_nan(p_value)

    if default_class == EvidenceClass.TARGETING:
        # Invariant 1: Targeting NaN-p is expected and safe. The registry
        # default wins regardless of the p-value state.
        return EvidenceClass.TARGETING

    if default_class in (EvidenceClass.MEASURED, EvidenceClass.DIRECTIONAL):
        if p_is_nan:
            # Invariant 2/3: NaN-p on a measured/directional play is a bug.
            # Raise so the engine surfaces the failure rather than silently
            # downgrading to a targeting card with no measurement behind it.
            raise EvidenceClassificationError(
                f"classify_evidence: play_id={play_id!r} declares "
                f"evidence_class_default={default_class.value!r} but the "
                "candidate has a NaN p-value. This is an engine bug: a "
                "measured/directional play must produce a real p-value or "
                "be reclassified to targeting before reaching this function."
            )
        return default_class

    # Defensive fallthrough; should be unreachable given EVIDENCE_CLASSES.
    return EvidenceClass.TARGETING  # pragma: no cover


# ---------------------------------------------------------------------------
# T4b.2 — consistency_across_windows
#
# DS Architect QA Change 1 specification (frozen in memory.md):
#
#   ``consistency_across_windows`` is a PRE-COMBINATION sign-agreement count.
#   It is NOT a post-combination p-value vote. It is used as a robustness
#   signal alongside ``combine_multiwindow_statistics`` — it must NOT be
#   used to upgrade a play's evidence class, and confidence must NOT be
#   multiplied by it as if it were a separate independent test.
#
#   Default formula:
#       count of windows where
#         sign(observed_effect) == sign(combiner.effect) AND |t-stat| > 1
#
# Implementation choices documented here:
#
# * "sign(0) is treated as agreement-with-zero": a window whose observed
#   effect is exactly 0.0 contributes 0 to the count regardless of the
#   combiner sign, because a zero-effect window provides no directional
#   evidence. Tests pin this.
# * "|t-stat| > 1 is strict": a window whose t-stat magnitude equals 1.0
#   exactly does NOT contribute. Tests pin this.
# * "t-stat is derived from effect / std_error when not provided": the
#   combiner's ``window_results`` carry ``effect_abs`` and ``std_error``;
#   if a caller passes a ``t_stat`` field directly it is preferred.
# * "NaN inputs do not contribute": a window with NaN effect, NaN
#   std_error, or NaN t_stat is excluded from the count. This keeps the
#   helper safe to call with the M4a-NaN'd hardcoded plays without
#   raising.
# * "combiner sign of 0 short-circuits to 0 count": if the combined
#   effect is exactly 0 (or NaN), there is no direction to agree with,
#   and the count is 0. This is the conservative "no robustness claim"
#   default.
# ---------------------------------------------------------------------------


def _signum(value: Any) -> int:
    """Return +1, -1, or 0 for a numeric value; 0 for NaN/None/non-numeric."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0
    if math.isnan(f):
        return 0
    if f > 0.0:
        return 1
    if f < 0.0:
        return -1
    return 0


def _abs_t_stat(window: Mapping[str, Any]) -> Optional[float]:
    """Return |t-stat| for a window result.

    Preference order:
    1. Explicit ``t_stat`` field (used by tests that pass synthetic
       per-window stats).
    2. ``effect_abs / std_error`` derived from the combiner's input shape.

    Returns ``None`` when neither is computable (NaN or zero std_error
    with non-finite effect). A return of ``None`` causes the window to be
    excluded from the consistency count.
    """
    t_explicit = window.get("t_stat")
    if t_explicit is not None:
        try:
            t_val = float(t_explicit)
        except (TypeError, ValueError):
            t_val = float("nan")
        if not math.isnan(t_val):
            return abs(t_val)

    effect = window.get("effect_abs")
    se = window.get("std_error")
    try:
        effect_f = float(effect)
        se_f = float(se)
    except (TypeError, ValueError):
        return None
    if math.isnan(effect_f) or math.isnan(se_f):
        return None
    if se_f <= 0.0:
        # Zero or negative std_error: cannot derive a t-statistic. The
        # combiner uses a precision-weight surrogate (1e6) for zero SE; we
        # do not propagate that here because consistency is a robustness
        # signal that must not silently include a "perfect" window.
        return None
    return abs(effect_f / se_f)


def compute_consistency_across_windows(
    window_results: Iterable[Mapping[str, Any]],
    combined_effect: Any,
    *,
    t_stat_threshold: float = 1.0,
) -> int:
    """Count of windows whose sign agrees with the combiner AND |t| > 1.

    This is the T4b.2 / DS Architect QA Change 1 robustness signal. It is
    intentionally a pre-combination sign-only count and **must not** be
    used to upgrade a play's evidence class or be multiplied into
    confidence as if it were an independent test.

    Parameters
    ----------
    window_results:
        Iterable of per-window result dicts. Each dict carries at least
        ``effect_abs`` and ``std_error`` (the combiner's input shape),
        and optionally ``t_stat`` for callers passing synthetic test
        fixtures.
    combined_effect:
        The combiner's combined effect (typically
        ``MultiWindowResult.effect_abs``). If the combiner sign is 0 or
        NaN, the count is 0 (no direction to agree with).
    t_stat_threshold:
        Minimum |t-stat| for a window to contribute. Default 1.0 per the
        DS Architect QA Change 1 spec. The comparison is strict (``>``).

    Returns
    -------
    int
        The number of windows that pass both the sign-agreement and the
        |t-stat| > threshold tests. Always non-negative; 0 if no windows
        contribute.
    """
    combiner_sign = _signum(combined_effect)
    if combiner_sign == 0:
        return 0

    count = 0
    for w in window_results:
        if not isinstance(w, Mapping):
            continue
        effect = w.get("effect_abs")
        if _signum(effect) != combiner_sign:
            continue
        abs_t = _abs_t_stat(w)
        if abs_t is None:
            continue
        if abs_t > t_stat_threshold:
            count += 1
    return count


__all__ = [
    "EvidenceClass",
    "EvidenceClassificationError",
    "EvidenceContext",
    "TARGETING_RECLASSIFY_PLAYS",
    "classify_evidence",
    "compute_consistency_across_windows",
]
