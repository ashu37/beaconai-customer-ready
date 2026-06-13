"""S13-T1.5 — ENGINE_V2_RANKING_STRATEGY_CHAIN flag default ON after atomic flip.

S13-T1 introduced the substrate flag-OFF. S13-T1.5 flips the default ON
(consumer wiring lands at T2+). The default-OFF assertion was inverted
in-place per the S12-T2.5 precedent (Option a) — avoiding growth of
KI-NEW-U's stale flag-default-off test list.
"""

from __future__ import annotations

import importlib
import os

import pytest


def test_flag_default_on_after_t1_5() -> None:
    """ENGINE_V2_RANKING_STRATEGY_CHAIN default ON after S13-T1.5 atomic flip.

    Per S12-T2.5 precedent (Option a), the default-OFF assertion was
    inverted in-place rather than left stale under KI-NEW-U.
    """
    import src.utils as utils_mod

    importlib.reload(utils_mod)
    if "ENGINE_V2_RANKING_STRATEGY_CHAIN" in os.environ:
        pytest.skip(
            "ENGINE_V2_RANKING_STRATEGY_CHAIN env override present; default test n/a"
        )
    assert utils_mod.DEFAULTS.get("ENGINE_V2_RANKING_STRATEGY_CHAIN") is True


def test_flag_env_override_true(monkeypatch) -> None:
    """Env var ``true`` flips the flag on (coerced as bool via _coerce)."""
    import src.utils as utils_mod

    monkeypatch.setenv("ENGINE_V2_RANKING_STRATEGY_CHAIN", "true")
    importlib.reload(utils_mod)
    assert utils_mod.DEFAULTS.get("ENGINE_V2_RANKING_STRATEGY_CHAIN") is True


def test_flag_in_coerce_bool_set() -> None:
    """ENGINE_V2_RANKING_STRATEGY_CHAIN must be in the _coerce bool set
    (S10-T1.5 lesson — flag presence in defaults dict is not enough;
    _coerce routing is required for env override to coerce as bool)."""
    import src.utils as utils_mod

    importlib.reload(utils_mod)
    coerced = utils_mod._coerce("ENGINE_V2_RANKING_STRATEGY_CHAIN", "true")
    assert coerced is True
    coerced_false = utils_mod._coerce("ENGINE_V2_RANKING_STRATEGY_CHAIN", "false")
    assert coerced_false is False
