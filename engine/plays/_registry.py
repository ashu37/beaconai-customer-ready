"""Play Library central registry (S8-T4 wave 1).

Loads each ``plays/<play_id>/spec.yaml`` at import time, resolves the
``audience_builder_ref`` and ``measurement_builder_ref`` dotted module paths
to the actual Python callables, and exposes ``get_play_definition(play_id)``.

This module is leaf-level: it imports from ``src.audience_builders`` and
``src.measurement_builder`` to resolve refs, but the imports are deferred to
first access so that test environments which mock those modules continue to
work.

See ``plays/__init__.py`` for the byte-identical contract and the
consult-and-verify pattern used by ``src/play_registry.py`` when the
``ENGINE_V2_PLAY_LIBRARY_WAVE1`` flag is ON.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, Iterator, List, Optional, Tuple

import yaml


# Wave 1 play_ids — LOCKED per DS verdict 2026-05-24 §3 Q6.
# Order is the migration order from ARCHITECTURE_PLAN.md Part I §E item 1-4
# (re-ordered so the load-bearing dormant play is verified mid-sequence).
WAVE1_PLAY_IDS: FrozenSet[str] = frozenset(
    {
        "winback_dormant_cohort",
        "replenishment_due",
        "discount_dependency_hygiene",
    }
)


@dataclass(frozen=True)
class PlayDefinition:
    """Typed Play Library definition resolved from ``plays/<play_id>/spec.yaml``.

    Field shape mirrors the relevant parts of ``src/play_registry.py::PlayDef``
    plus the resolved callables for audience + measurement builders. The shape
    is intentionally thin in wave 1 — additional fields (eligibility, post-launch
    outcome, mechanism copy) will land in wave 2+ when behavior actually moves
    into ``plays/<play_id>/``.

    Identity contract: ``audience_builder`` and ``measurement_signal_entry``
    are the exact same Python objects as the legacy registry's. The
    consult-and-verify helper ``assert_identity_with_legacy()`` raises if
    that contract breaks.
    """

    play_id: str
    display_name: str
    audience_builder_ref: str
    audience_builder: Callable[..., Any]
    measurement_builder_ref: str
    measurement_signal_entry: Any  # _PriorAnchoredSignal (avoid import cycle)
    prior_keys: List[str]
    would_be_measured_by_name: str
    spec_yaml_path: Path


# ---------------------------------------------------------------------------
# Lazy import helpers (avoid import cycles at module load time).
# ---------------------------------------------------------------------------


def _resolve_dotted_ref(ref: str) -> Any:
    """Resolve ``a.b.c.symbol`` to the actual Python object."""
    module_path, _, symbol = ref.rpartition(".")
    if not module_path or not symbol:
        raise ValueError(
            f"plays/_registry: invalid dotted ref {ref!r}; "
            f"expected ``module.path.symbol``."
        )
    mod = importlib.import_module(module_path)
    try:
        return getattr(mod, symbol)
    except AttributeError as exc:
        raise ValueError(
            f"plays/_registry: cannot resolve {symbol!r} on {module_path!r}: {exc}"
        ) from exc


def _measurement_signal_entry(play_id: str) -> Any:
    """Look up the ``_PRIOR_ANCHORED`` entry for ``play_id``.

    Returns ``None`` if not present (the legacy seam handles missing entries
    via its own fall-through). Deferred import avoids cycles when measurement
    builder transitively imports anything from ``plays/``.
    """
    from src.measurement_builder import _PRIOR_ANCHORED  # local import

    return _PRIOR_ANCHORED.get(play_id)


# ---------------------------------------------------------------------------
# spec.yaml loader.
# ---------------------------------------------------------------------------


_PLAYS_DIR = Path(__file__).resolve().parent


def _load_spec(play_id: str) -> Optional[Dict[str, Any]]:
    spec_path = _PLAYS_DIR / play_id / "spec.yaml"
    if not spec_path.exists():
        return None
    with spec_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(
            f"plays/{play_id}/spec.yaml must be a mapping; got {type(raw).__name__}."
        )
    raw["__spec_yaml_path__"] = spec_path
    return raw


def _build_definition(spec: Dict[str, Any]) -> PlayDefinition:
    play_id = str(spec["play_id"])
    audience_ref = str(spec["audience_builder_ref"])
    measurement_ref = str(spec["measurement_builder_ref"])
    audience_builder = _resolve_dotted_ref(audience_ref)
    measurement_signal_entry = _measurement_signal_entry(play_id)
    prior_keys = list(spec.get("prior_keys") or [])
    would_be = str(spec.get("would_be_measured_by") or "")
    return PlayDefinition(
        play_id=play_id,
        display_name=str(spec.get("display_name") or play_id),
        audience_builder_ref=audience_ref,
        audience_builder=audience_builder,
        measurement_builder_ref=measurement_ref,
        measurement_signal_entry=measurement_signal_entry,
        prior_keys=prior_keys,
        would_be_measured_by_name=would_be,
        spec_yaml_path=spec["__spec_yaml_path__"],
    )


# ---------------------------------------------------------------------------
# Cache.
# ---------------------------------------------------------------------------


_CACHE: Dict[str, PlayDefinition] = {}
_CACHE_BUILT = False


def _build_cache() -> None:
    global _CACHE_BUILT
    if _CACHE_BUILT:
        return
    for play_id in WAVE1_PLAY_IDS:
        spec = _load_spec(play_id)
        if spec is None:
            # Spec missing for a wave-1 play — surface loudly. The artifact
            # invariant (DS verdict §5 invariant 13) requires every wave-1
            # play_id to have a spec.yaml file present in the repo.
            raise FileNotFoundError(
                f"plays/{play_id}/spec.yaml is missing; wave-1 artifact "
                f"invariant violated (DS verdict 2026-05-24 §5 invariant 13)."
            )
        _CACHE[play_id] = _build_definition(spec)
    _CACHE_BUILT = True


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


def get_play_definition(play_id: str) -> Optional[PlayDefinition]:
    """Return the Play Library definition for ``play_id``.

    Returns ``None`` for any play_id not in wave 1 — callers fall through
    to the legacy ``src/play_registry.py`` entry.
    """
    if play_id not in WAVE1_PLAY_IDS:
        return None
    _build_cache()
    return _CACHE.get(play_id)


def iter_wave1_play_definitions() -> Iterator[PlayDefinition]:
    """Yield each wave-1 ``PlayDefinition`` in deterministic play_id order."""
    _build_cache()
    for play_id in sorted(WAVE1_PLAY_IDS):
        defn = _CACHE.get(play_id)
        if defn is not None:
            yield defn


def assert_identity_with_legacy() -> None:
    """Consult-and-verify integrity check (consumed by ``src/play_registry.py``
    when ``ENGINE_V2_PLAY_LIBRARY_WAVE1`` is ON).

    Asserts, for each wave-1 play, that:

    1. The spec.yaml-resolved audience builder callable is the exact same
       Python object as ``src/audience_builders.BUILDERS[audience_builder_ref]``.
    2. The ``_PRIOR_ANCHORED`` measurement entry resolves under the same
       ``play_id`` key.
    3. The spec.yaml-declared ``prior_keys`` are a subset of the legacy
       ``src/play_registry.PLAYS[play_id].prior_keys`` (additive-only check;
       wave-1 spec.yaml may declare fewer keys if the play uses only a
       subset for prior-anchored sizing).

    Raises ``RuntimeError`` if any contract breaks. This is the
    load-bearing safety net that lets the flag-ON code path remain
    byte-identical to flag-OFF: if the spec.yaml drifts from the legacy
    registry, the engine refuses to start under flag ON rather than
    silently rendering inconsistent output.
    """
    from src.audience_builders import BUILDERS as _LEGACY_BUILDERS
    from src.play_registry import PLAYS as _LEGACY_PLAYS

    failures: List[str] = []
    _build_cache()
    for play_id in sorted(WAVE1_PLAY_IDS):
        defn = _CACHE.get(play_id)
        if defn is None:
            failures.append(f"{play_id}: spec.yaml did not load")
            continue

        legacy_play = _LEGACY_PLAYS.get(play_id)
        if legacy_play is None:
            failures.append(
                f"{play_id}: missing from src/play_registry.PLAYS (legacy registry)"
            )
            continue

        # (1) audience builder identity.
        #
        # Two indirections need to agree:
        #   (a) spec.yaml's dotted Python ref (e.g.
        #       ``src.audience_builders.winback_dormant_cohort_candidates``)
        #       resolves at import time to ``defn.audience_builder``.
        #   (b) legacy ``PlayDef.audience_builder_ref`` (e.g.
        #       ``"audience.winback_dormant_cohort"``) maps via
        #       ``src.audience_builders.BUILDERS`` to a callable.
        # Both must point at the exact same Python object.
        legacy_audience = _LEGACY_BUILDERS.get(legacy_play.audience_builder_ref)
        if legacy_audience is None:
            failures.append(
                f"{play_id}: legacy audience_builder_ref "
                f"{legacy_play.audience_builder_ref!r} not in "
                f"src/audience_builders.BUILDERS"
            )
        elif legacy_audience is not defn.audience_builder:
            failures.append(
                f"{play_id}: audience_builder identity drift — spec.yaml "
                f"dotted ref {defn.audience_builder_ref!r} resolved to a "
                f"different callable than the legacy registry "
                f"({legacy_play.audience_builder_ref!r} in BUILDERS)"
            )

        # (2) measurement signal entry presence (None is permitted for plays
        # that are not prior-anchored, but all 3 wave-1 plays ARE
        # prior-anchored so the entry must exist).
        if defn.measurement_signal_entry is None:
            failures.append(
                f"{play_id}: _PRIOR_ANCHORED has no entry under {play_id!r} "
                f"(wave-1 plays must be prior-anchored)"
            )

        # (3) prior_keys subset check
        legacy_keys = set(legacy_play.prior_keys or [])
        spec_keys = set(defn.prior_keys or [])
        extra = spec_keys - legacy_keys
        if extra:
            failures.append(
                f"{play_id}: spec.yaml declares prior_keys {sorted(extra)} "
                f"not present in src/play_registry.PLAYS[{play_id!r}].prior_keys "
                f"({sorted(legacy_keys)})"
            )

    if failures:
        raise RuntimeError(
            "plays.assert_identity_with_legacy: wave-1 spec.yaml drift "
            "detected (ENGINE_V2_PLAY_LIBRARY_WAVE1 contract violated). "
            "Engine refuses to start to preserve byte-identical contract.\n  - "
            + "\n  - ".join(failures)
        )
