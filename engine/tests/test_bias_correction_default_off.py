"""Milestone 5 T5.6 — bias correction default remains OFF and no bypass.

Two assertions:

1. The DEFAULTS dict in ``src.utils`` resolves
   ``ENABLE_REPEAT_RATE_BIAS_CORRECTION`` to False (M4a flipped this).
2. The call site in ``utils.kpi_snapshot_with_deltas`` uses
   ``cfg.get(..., False)`` -- the default-True bypass is removed. We
   pin this by reading the source so a future regression will be
   caught even if the bias_corrections multiplier branch is reached
   via some other path.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import utils  # noqa: E402


def test_default_is_false():
    cfg = utils.get_config()
    assert cfg.get("ENABLE_REPEAT_RATE_BIAS_CORRECTION") is False


def test_call_site_default_is_false_not_true():
    """Forcing function: the call site must NOT default to True.

    The pre-M5 call site read ``cfg.get("ENABLE_REPEAT_RATE_BIAS_CORRECTION", True)``
    which silently re-enabled the multiplier when the cfg key was
    missing. T5.6 removes that bypass; the default in the call site is
    now False.
    """
    src = inspect.getsource(utils.kpi_snapshot_with_deltas)
    assert 'cfg.get("ENABLE_REPEAT_RATE_BIAS_CORRECTION", True)' not in src, (
        "Bias correction default-True bypass found; T5.6 requires the call "
        "site to default to False so a missing cfg key does not silently "
        "re-enable the multiplier."
    )
    assert 'cfg.get("ENABLE_REPEAT_RATE_BIAS_CORRECTION", False)' in src


def test_no_other_bias_corrections_dict_reference_remains_active():
    """The hardcoded multiplier {7:1.0, 28:0.95, 56:0.90, 90:0.85} must
    only execute when the flag is explicitly on.

    We don't delete the code path (M10 owns deletion); we just confirm
    no other reachable site resurrects it with a True default.
    """
    src = inspect.getsource(utils)
    # The dict literal can appear in only the gated branch; that branch
    # is now under cfg.get(..., False).
    occurrences = src.count("bias_corrections = {")
    assert occurrences <= 1, (
        f"Expected at most one bias_corrections dict literal; found {occurrences}. "
        "Multiple sites raises the risk of one being mistakenly default-True."
    )
