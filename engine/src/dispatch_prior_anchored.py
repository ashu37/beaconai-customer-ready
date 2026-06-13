"""Sprint 13.5 Ticket T1 — KI-NEW-L collapse.

This module is the **single dispatch point** for the V2 prior-anchored
Tier-B builders that previously lived as five near-duplicate injection
blocks at ``src/main.py:1380-1597`` (S6-T1 winback / S6-T3
replenishment / S7-T1 discount-hygiene / S7-T2 journey-first-to-second /
S7-T3 AOV-bundle).

The five blocks each:

1. Gated on a ``ENGINE_V2_BUILDER_*`` flag.
2. Called :func:`src.measurement_builder.build_prior_anchored_recommendations`
   with ``allowed_play_ids={one_play_id}`` and a play-specific
   ``observed_*_enabled`` kwarg.
3. Appended the result to ``engine_run.recommendations``.

All five then shared a single :func:`src.guardrails.apply_guardrails_to_injected`
re-invocation at the end (the single demote channel — Pivot 7).

KI-NEW-L collapses the five-block + single-guardrails-call pattern into
this dispatch helper keyed off the ``_PRIOR_ANCHORED`` registry at
``src/measurement_builder.py:721``.

**Behavior contract (DS-locked, S13.5-T1):**

- Byte-identical to the pre-collapse 5-block path on the Beauty +
  supplements pinned fixtures.
- **Single demote channel (Pivot 7) preserved.** The
  ``apply_guardrails_to_injected`` invocation lives here, once.
- **Three-channel ``priority_prepend`` preserved.** The helper does not
  touch ``priority_prepend``; the existing post-helper assemble path in
  ``src/decide.py`` continues to prepend ``eligibility_rejects``,
  ``prior_unvalidated_rejects``, and ``window_disagreement_rejects``
  into Considered ahead of ``pre_existing`` so the
  ``MAX_CONSIDERED_RENDERED=6`` truncation cannot silently drop them.
- **Observed-effect surfacing tripwire preserved.** The five per-play
  ``ENGINE_V2_OBSERVED_EFFECT_*`` flags are still threaded through to
  :func:`build_prior_anchored_recommendations` per its existing kwarg
  surface; the surfacing at
  ``src/measurement_builder.py:2252-2270`` is unchanged.
- **Per-builder iteration order preserved.** The dispatch table is
  ordered ``winback_dormant_cohort → replenishment_due →
  cohort_journey_first_to_second → discount_dependency_hygiene →
  aov_lift_via_threshold_bundle`` — the exact order the legacy 5-block
  emitter used. Append order into ``engine_run.recommendations`` matters
  for downstream rank/truncation; preserving it is what makes the
  collapse byte-identical.

**Single-emission-point contract (S13.5-T1 LOAD-BEARING):**
``dispatch_prior_anchored_builders`` is the ONLY callsite in
``src/main.py`` that appends V2 prior-anchored builder results to
``engine_run.recommendations``. New prior-anchored builders MUST extend
the ``_DISPATCH_TABLE`` here; appending elsewhere violates the
single-demote-channel invariant and is enforced by
``tests/test_s13_5_single_emission_point.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace as _dc_replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Tuple


# ---------------------------------------------------------------------------
# Dispatch table — ordered tuple, NOT a dict, because per-builder iteration
# order is load-bearing on byte-identity of the Beauty + supplements pinned
# fixtures. Adding a new prior-anchored builder = appending to this tuple;
# do NOT reorder.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DispatchEntry:
    """One row of the prior-anchored dispatch table.

    ``play_id`` — registry key in :data:`src.measurement_builder._PRIOR_ANCHORED`.
    ``builder_flag`` — ``cfg`` key that gates the consumer (default OFF
        on each builder's introduction sprint; atomic flip on the
        corresponding ``.5`` ticket).
    ``observed_kwarg`` — the play-specific ``observed_*_enabled`` kwarg
        on :func:`build_prior_anchored_recommendations`. None means the
        play does not have an observed-effect kwarg (purely cold-start).
    ``observed_flag`` — ``cfg`` key the helper consults to set
        ``observed_kwarg``. None when ``observed_kwarg`` is None.
    """

    play_id: str
    builder_flag: str
    observed_kwarg: Optional[str]
    observed_flag: Optional[str]


_DISPATCH_TABLE: Tuple[_DispatchEntry, ...] = (
    # S6-T1 — winback_dormant_cohort.
    _DispatchEntry(
        play_id="winback_dormant_cohort",
        builder_flag="ENGINE_V2_BUILDER_WINBACK_DORMANT",
        observed_kwarg="observed_effect_enabled",
        observed_flag="ENGINE_V2_OBSERVED_EFFECT_WINBACK",
    ),
    # S6-T3 — replenishment_due.
    _DispatchEntry(
        play_id="replenishment_due",
        builder_flag="ENGINE_V2_BUILDER_REPLENISHMENT_DUE",
        observed_kwarg="observed_replenishment_enabled",
        observed_flag="ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT",
    ),
    # S7-T2 — cohort_journey_first_to_second.
    _DispatchEntry(
        play_id="cohort_journey_first_to_second",
        builder_flag="ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND",
        observed_kwarg="observed_journey_enabled",
        observed_flag="ENGINE_V2_OBSERVED_EFFECT_JOURNEY",
    ),
    # S7-T1 — discount_dependency_hygiene.
    _DispatchEntry(
        play_id="discount_dependency_hygiene",
        builder_flag="ENGINE_V2_BUILDER_DISCOUNT_HYGIENE",
        observed_kwarg="observed_discount_hygiene_enabled",
        observed_flag="ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE",
    ),
    # S7-T3 — aov_lift_via_threshold_bundle.
    _DispatchEntry(
        play_id="aov_lift_via_threshold_bundle",
        builder_flag="ENGINE_V2_BUILDER_AOV_BUNDLE",
        observed_kwarg="observed_aov_bundle_enabled",
        observed_flag="ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE",
    ),
)


def _cfg_flag(cfg: Optional[Mapping[str, Any]], key: str) -> bool:
    if not cfg or not key:
        return False
    return bool(cfg.get(key, False))


def dispatch_prior_anchored_builders(
    engine_run: Any,
    *,
    phase5_cands: Iterable[Any],
    aligned_for_template: Optional[Mapping[str, Any]],
    vertical: Optional[str],
    subvertical: Optional[str],
    store_profile: Any,
    profile_flag_on: bool,
    gate_routed: bool,
    orders_df: Any,
    inventory_metrics: Optional[Any],
    store_dir: Path,
    store_id: Optional[str],
    cfg: Optional[Mapping[str, Any]],
) -> Any:
    """Collapse-target: run every gated prior-anchored builder then the
    single :func:`apply_guardrails_to_injected` invocation.

    Replaces the five legacy injection blocks + single guardrails-to-
    injected call at ``src/main.py:1604-1970`` (S6-T1 / S6-T3 / S7-T1 /
    S7-T2 / S7-T3 + S7.6-C2). See module docstring for invariant
    preservation contract.

    Args:
        engine_run: the typed ``EngineRun`` carrying the
            pre-prior-anchored ``recommendations`` list.
        phase5_cands: the M3 candidate list (``_phase5_cands`` in
            ``main.py``) — passed to every builder.
        aligned_for_template: the aligned-metrics dict the builders read.
        vertical / subvertical: PROFILE-derived strings; same values
            every legacy block read from the enclosing scope.
        store_profile / profile_flag_on: same threaded values used by
            every legacy block (Sprint 6.5 Ticket T4 surface).
        gate_routed: if True (data-quality / anomaly held the run), the
            entire dispatch is a no-op — matches the legacy
            ``not _gate_routed`` guard on every block.
        orders_df: the orders DataFrame ``g`` from ``main.py`` (threaded
            into every builder for the per-play observed-effect helpers
            under each ``ENGINE_V2_OBSERVED_EFFECT_*`` flag).
        inventory_metrics / store_dir / store_id / cfg: forwarded to
            :func:`apply_guardrails_to_injected` exactly as the legacy
            single call did.

    Returns:
        A new ``EngineRun`` with the post-guardrails-to-injected
        ``recommendations`` + ``considered``. When ``gate_routed`` is
        True or no builder fires, the input ``engine_run`` is returned
        unchanged.
    """

    # Single-demote-channel invariant: the gate-routed branch must
    # short-circuit BEFORE any prior-anchored builder appends. Matches
    # legacy ``if not _gate_routed and bool(cfg.get("ENGINE_V2_BUILDER_*"))``.
    if gate_routed:
        return engine_run

    # Lazy imports so the helper does not perturb the import graph for
    # callers that never hit the V2 decide branch (legacy path stays
    # cold).
    from .measurement_builder import (
        build_prior_anchored_recommendations as _build_prior_anchored,
    )
    from .guardrails import (
        apply_guardrails_to_injected as _apply_guardrails_to_injected,
    )
    from .play_registry import PLAYS as _PLAYS
    from .detect import compute_audience_overlap as _compute_overlap
    from .audience_builders import get_builder as _get_audience_builder

    # S7.6-T7-FIX snapshot of pre-prior-anchored play_ids — used by
    # ``apply_guardrails_to_injected`` to identify which cards are
    # "injected" (pre-existing cards already cleared apply_guardrails
    # at ``src/main.py:994`` and are passed through untouched).
    pre_prior_anchored_play_ids: set[str] = {
        str(getattr(pc, "play_id", ""))
        for pc in (engine_run.recommendations or [])
    }

    cfg_local: Mapping[str, Any] = cfg or {}
    v = str(vertical) if vertical else None
    sv = str(subvertical) if subvertical else None

    any_builder_fired = False

    # ---- 5-block collapse: iterate dispatch table in load-bearing order.
    for entry in _DISPATCH_TABLE:
        if not _cfg_flag(cfg_local, entry.builder_flag):
            continue
        try:
            existing_ids = [
                pc.play_id for pc in (engine_run.recommendations or [])
            ]
            extra_kwargs: dict = {}
            if entry.observed_kwarg is not None:
                extra_kwargs[entry.observed_kwarg] = _cfg_flag(
                    cfg_local, entry.observed_flag or ""
                )
            cards = _build_prior_anchored(
                phase5_cands,
                aligned_for_template,
                vertical=v,
                subvertical=sv,
                existing_recommendation_ids=existing_ids,
                store_profile=store_profile,
                profile_flag_on=profile_flag_on,
                allowed_play_ids={entry.play_id},
                orders_df=orders_df,
                cfg=cfg_local,
                **extra_kwargs,
            )
            if cards:
                new_recs = list(engine_run.recommendations or []) + list(cards)
                engine_run = _dc_replace(engine_run, recommendations=new_recs)
                any_builder_fired = True
        except Exception as _ae:
            # Preserve legacy per-block failure isolation: a builder
            # that raises does NOT cancel downstream builders. The
            # legacy code printed ``[V2 ... prior-anchored builder]
            # Warning: ...`` on each block; we emit one tagged with
            # the play_id for traceability.
            print(
                f"[V2 prior-anchored dispatch:{entry.play_id}] Warning: {_ae}"
            )

    # ---- Single demote channel (Pivot 7): one call regardless of how
    # many builders fired. Matches the legacy single S7.6-C2 block at
    # ``src/main.py:1900-1970``. Wrapped in try/except to mirror the
    # legacy ``print warning`` failure mode (so a guardrails-helper
    # error never aborts the run).
    try:
        injected_overlap_map: dict = {}
        if _cfg_flag(cfg_local, "CANNIBALIZATION_GATE_ENABLED"):
            injected_audience_sets: dict = {}
            for _pc in engine_run.recommendations or []:
                _pdef_i = _PLAYS.get(_pc.play_id)
                if _pdef_i is None:
                    continue
                _builder_i = _get_audience_builder(
                    _pdef_i.audience_builder_ref
                )
                if _builder_i is None:
                    continue
                try:
                    _res_i = _builder_i(
                        orders_df, aligned_for_template or {}, cfg_local or {}
                    )
                    injected_audience_sets[_pc.play_id] = set(
                        _res_i.audience_ids or set()
                    )
                except Exception:
                    injected_audience_sets[_pc.play_id] = set()
            if injected_audience_sets:
                injected_overlap_map = _compute_overlap(injected_audience_sets)

        engine_run = _apply_guardrails_to_injected(
            engine_run,
            pre_injection_play_ids=pre_prior_anchored_play_ids,
            inventory_metrics=inventory_metrics,
            audience_overlap=injected_overlap_map,
            history_path=str(store_dir / "recommended_history.json"),
            cfg=cfg_local,
            store_id=store_id,
        )
    except Exception as _rm_e:
        print(
            f"[V2 S7.6-C2 apply_guardrails_to_injected] Warning: {_rm_e}"
        )

    # Suppress unused-warning if nothing fired (the call still runs for
    # invariant reasons — matches legacy: ``apply_guardrails_to_injected``
    # ran post-block regardless of whether any block appended).
    _ = any_builder_fired

    return engine_run


__all__ = [
    "dispatch_prior_anchored_builders",
]
