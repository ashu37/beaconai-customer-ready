"""G-7: deterministic-seeding helper.

Seeds Python's stdlib ``random`` and ``numpy.random`` so that any future
randomness introduced into ``src/`` runs against a fixed seed. The engine
today uses no randomness on the Beauty pinned fixture; this module is a
forcing function. If a future patch introduces ``random.random()`` /
``np.random.*`` without re-seeding, the cross-run byte-identity test in
``tests/test_determinism_cross_run.py`` is what surfaces the drift.

Contract:

- ``seed_all(seed)`` is idempotent and side-effect-only.
- ``numpy`` seeding is best-effort: if numpy is not importable, the
  stdlib seed still applies. (numpy is a hard dep today, so this is just
  defensive.)
- The fixed seed is exposed as ``DEFAULT_SEED`` so tests can import it.
"""
from __future__ import annotations

import random as _random


DEFAULT_SEED: int = 0


def seed_all(seed: int = DEFAULT_SEED) -> None:
    """Seed Python ``random`` and ``numpy.random`` (if available).

    Called at engine entry (``src/main.py::run()``) so that any
    downstream code path that lands a ``random.*`` or ``np.random.*``
    call enters a deterministic state. Re-callable; no return value.
    """
    _random.seed(seed)
    try:
        import numpy as _np
    except ImportError:
        return
    _np.random.seed(seed)
