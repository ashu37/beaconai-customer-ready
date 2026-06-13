"""Play Library — first-class per-play directory layout (S8-T4 wave 1).

This package is the canonical home of the Play Library refactor (ARCHITECTURE_PLAN.md
Part I §E). Each play has its own subdirectory ``plays/<play_id>/`` containing:

- ``spec.yaml``        — thin metadata: id, display_name, audience/measurement
                         module refs, prior keys, would_be_measured_by enum value.
- ``audience.py``      — re-exports the audience builder callable from
                         ``src/audience_builders.py`` (no behavior moved in wave 1).
- ``builder.py``       — re-exports the prior-anchored ``_PriorAnchoredSignal``
                         metadata from ``src/measurement_builder.py::_PRIOR_ANCHORED``
                         (no behavior moved in wave 1).
- ``copy.md``          — documentation-only display_name + mechanism copy
                         extracted from the legacy locations for future
                         renderer routing (wave 2+; renderer still reads from
                         existing sources today).

**Wave 1 plays (DS verdict 2026-05-24 §3 Q6, LOCKED):**

1. ``winback_dormant_cohort``       (S6-T2 first-builder)
2. ``replenishment_due``            (S6-T3 second-builder; honest-dormant on Beauty
                                     per KI-NEW-G — load-bearing migration test)
3. ``discount_dependency_hygiene``  (S7-T1 first-builder)

The 11 unmigrated plays continue to live in the legacy locations and are
served by ``src/play_registry.py`` + ``src/audience_builders.py`` +
``src/measurement_builder.py`` unchanged.

**Byte-identical contract (sacred, DS verdict §5 invariant 13):**

The wave-1 migration is a refactor-only restructure. ``plays/<play_id>/audience.py``
and ``plays/<play_id>/builder.py`` are *re-exports* — they bind to the exact
same Python objects as the legacy modules. ``get_play_definition()`` is a
consult-and-verify helper: when ``ENGINE_V2_PLAY_LIBRARY_WAVE1`` is ON,
``src/play_registry.py`` calls ``assert_identity_with_legacy()`` to verify
that the spec.yaml-resolved callables are the same Python objects as the
legacy registry's, and then continues with the legacy code path. Output is
byte-identical at BOTH flag states.

**KI-NEW-G honest-dormancy preserved:** ``replenishment_due`` is dormant on
the Beauty pinned fixture by design (per-SKU repeat-buyer distribution sits
below D-S6-4's N>=30 floor). The migration does not alter the audience
builder; ``replenishment_due`` continues to produce zero audience on Beauty
at both flag states post-T4.5.

**Future waves (out of scope for T4):** wave 2+ migrates additional plays
incrementally. The KI-NEW-L collapse of the 5 V2 prior-anchored injection
blocks at ``src/main.py:1380-1597`` into a single PRIOR_ANCHORED dispatch
is scheduled for S13.5 per DS verdict.
"""
from __future__ import annotations

from ._registry import (
    PlayDefinition,
    WAVE1_PLAY_IDS,
    get_play_definition,
    iter_wave1_play_definitions,
    assert_identity_with_legacy,
)

__all__ = [
    "PlayDefinition",
    "WAVE1_PLAY_IDS",
    "get_play_definition",
    "iter_wave1_play_definitions",
    "assert_identity_with_legacy",
]
