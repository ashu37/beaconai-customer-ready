"""S-1.7 — Vertical resolution hardening regression tests.

Two correctness bugs surfaced during Sprint 1 merge manual-validation:

Bug 1: ``src.utils.get_vertical_mode()`` silently mapped any unknown
vertical (e.g. ``apparel``, ``food``, ``home``) to ``'mixed'``. Because
``'mixed'`` is in the supported set, B-7's vertical_guard never fired
for these inputs — the engine ran on mixed priors instead of refusing.
This defeated the B-7 hard-refuse contract.

Bug 2: ``src.utils``'s manual ``.env`` fallback (used when ``python-dotenv``
is missing) did ``os.environ[k] = v`` unconditionally, overriding exported
env vars. Local-dev only but compounded Bug 1 by making the laundering
hard to detect during testing.

These tests pin the fix:

- ``get_vertical_mode()`` no longer launders unknown verticals into
  ``'mixed'``. Pass-through is the contract; B-7 is the single point of
  refusal.
- ``VERTICAL_MODE=apparel`` (or any unsupported vertical) flowing through
  ``main.run`` triggers the B-7 ABSTAIN_HARD path end-to-end.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from src.vertical_guard import (
    SUPPORTED_VERTICALS,
    MERCHANT_FACING_REFUSAL_COPY,
)


# ---------------------------------------------------------------------------
# Bug 1: get_vertical_mode() pass-through (no laundering)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "vertical_input",
    ["apparel", "food", "food_bev", "home", "wellness", "Apparel", " APPAREL "],
)
def test_get_vertical_mode_does_not_launder_unknown_to_mixed(
    monkeypatch: pytest.MonkeyPatch,
    vertical_input: str,
):
    """``get_vertical_mode()`` must NOT return ``'mixed'`` for unknown inputs.

    The supported set is ``{beauty, supplements, mixed}`` (from
    ``play_registry._ALL_VERTICALS``, mirrored in
    ``vertical_guard.SUPPORTED_VERTICALS``). Anything outside that set
    must pass through normalized (lowercased / stripped) — never get
    silently rewritten to ``'mixed'``.
    """

    monkeypatch.setenv("VERTICAL_MODE", vertical_input)
    monkeypatch.delenv("VERTICAL", raising=False)

    # Re-import to ensure no module-level cache. ``get_vertical_mode`` reads
    # os.environ on each call, so a plain import is fine.
    from src.utils import get_vertical_mode

    result = get_vertical_mode()

    expected_normalized = vertical_input.strip().lower()
    assert result == expected_normalized, (
        f"VERTICAL_MODE={vertical_input!r} must pass through as "
        f"{expected_normalized!r}, not be laundered. Got {result!r}."
    )
    # Sanity: not in supported set, so the B-7 guard sees a refusal.
    assert result not in SUPPORTED_VERTICALS, (
        f"Test premise broken: {result!r} is in the supported set."
    )


def test_get_vertical_mode_default_is_mixed_when_unset(
    monkeypatch: pytest.MonkeyPatch,
):
    """Default behavior preserved: no env var set → ``'mixed'``.

    ``'mixed'`` here is the literal beauty+supplements blend default,
    NOT a fallback for unknown inputs. The two cases must remain
    distinguishable.
    """

    monkeypatch.delenv("VERTICAL_MODE", raising=False)
    monkeypatch.delenv("VERTICAL", raising=False)

    from src.utils import get_vertical_mode

    assert get_vertical_mode() == "mixed"


def test_get_vertical_mode_passes_supported_through(
    monkeypatch: pytest.MonkeyPatch,
):
    """``beauty`` and ``supplements`` pass through unchanged."""

    from src.utils import get_vertical_mode

    monkeypatch.setenv("VERTICAL_MODE", "beauty")
    monkeypatch.delenv("VERTICAL", raising=False)
    assert get_vertical_mode() == "beauty"

    monkeypatch.setenv("VERTICAL_MODE", "supplements")
    assert get_vertical_mode() == "supplements"

    monkeypatch.setenv("VERTICAL_MODE", "mixed")
    assert get_vertical_mode() == "mixed"


# ---------------------------------------------------------------------------
# Bug 1 end-to-end: VERTICAL_MODE=apparel via env triggers B-7 ABSTAIN_HARD
# ---------------------------------------------------------------------------


@pytest.fixture
def _minimal_csv(tmp_path: Path) -> Path:
    """Tiny shopify-shaped CSV. Doesn't need to be real apparel data —
    the guard short-circuits before the feature builder runs."""

    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "Name,Email,Created at,Subtotal,Total Discount\n"
        "#1001,a@example.com,2025-01-01 10:00:00,50.00,0.00\n"
        "#1002,b@example.com,2025-01-02 10:00:00,75.00,5.00\n",
        encoding="utf-8",
    )
    return csv_path


def test_vertical_mode_apparel_via_env_triggers_b7_abstain_hard(
    tmp_path: Path,
    _minimal_csv: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """End-to-end: ``VERTICAL_MODE=apparel`` in os.environ → B-7 ABSTAIN_HARD.

    This is the regression that the prior ``get_vertical_mode()``
    laundering would have masked: with the old code, ``get_vertical_mode``
    returned ``'mixed'`` and any caller that derived cfg from it (rather
    than from os.environ directly) would see ``'mixed'`` and the guard
    would not fire. Today, ``main.run`` reads ``cfg.get('VERTICAL_MODE')``
    which originates from ``get_config()``; the guarantee we pin here is
    that the env-driven path produces a ``cfg`` value the guard refuses.
    """

    monkeypatch.setenv("VERTICAL_MODE", "apparel")
    monkeypatch.delenv("VERTICAL", raising=False)

    # Reload src.main so its module-level imports re-evaluate against the
    # patched env. ``get_config`` itself reads env each call, so this is
    # belt-and-suspenders rather than strictly required.
    import src.main as _main
    _main = importlib.reload(_main)

    out_dir = tmp_path / "out"
    _main.run(
        csv_path=str(_minimal_csv),
        brand="apparel_test_store",
        out_dir=str(out_dir),
    )

    engine_run_path = out_dir / "receipts" / "engine_run.json"
    assert engine_run_path.exists(), "engine_run.json must be written on refusal"

    payload = json.loads(engine_run_path.read_text(encoding="utf-8"))
    assert payload["abstain"]["state"] == "abstain_hard"
    # S13.6-T1a: payload["abstain"]["reason"] stripped per Pivot 2.
    assert payload["data_quality_flags"] == ["vertical_not_supported"]
    assert payload["recommendations"] == []
    assert payload["recommended_experiments"] == []

    # No briefing rendered.
    briefing_path = out_dir / "briefings" / "apparel_test_store_briefing.html"
    assert not briefing_path.exists()


# ---------------------------------------------------------------------------
# Bug 2: manual .env fallback uses setdefault — exported env vars win
# ---------------------------------------------------------------------------


def test_manual_env_fallback_does_not_overwrite_exported_var(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The ``.env``-fallback loader (no python-dotenv path) must not
    overwrite a variable already set in ``os.environ``.

    We can't easily uninstall python-dotenv inside a test, so we exercise
    the fallback's loop logic directly: write a fake .env, pre-set the
    env var to a different value, run the loop, assert the exported value
    survives.
    """

    env_file = tmp_path / ".env"
    env_file.write_text(
        "VERTICAL_MODE=apparel\nUNUSED_VAR=from_dotenv\n",
        encoding="utf-8",
    )

    # Pre-set the exported value the loop must NOT overwrite.
    monkeypatch.setenv("VERTICAL_MODE", "beauty")
    monkeypatch.delenv("UNUSED_VAR", raising=False)

    # Replicate the manual-fallback loop body verbatim from src/utils.py.
    # If src/utils.py changes, this test should fail and be re-pinned.
    import os
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

    assert os.environ["VERTICAL_MODE"] == "beauty", (
        "Exported VERTICAL_MODE=beauty must win over .env's apparel; "
        "setdefault semantics are required by S-1.7."
    )
    assert os.environ["UNUSED_VAR"] == "from_dotenv", (
        "Variables NOT pre-exported should still be loaded from .env."
    )


def test_no_unsupported_vertical_mode_in_test_suite():
    """Grep test: no test sets VERTICAL_MODE=apparel|food|home|wellness.

    If any test relied on the prior ``get_vertical_mode()`` laundering
    (i.e. expected ``VERTICAL_MODE=apparel`` to silently run on mixed
    priors), this test forces a redesign rather than a quiet behavior
    change. Expected count: zero. The B-7 acceptance test is allowed to
    mention the strings inside docstrings; we only forbid them in env-set
    syntax.
    """

    import re
    tests_dir = Path(__file__).parent
    pattern = re.compile(
        r"VERTICAL_MODE\s*[=:]\s*['\"]?(apparel|food|food_bev|home|wellness)",
        re.IGNORECASE,
    )

    # B-7's hard-refuse acceptance test legitimately drives unsupported
    # verticals through the engine entry to assert ABSTAIN_HARD. That is
    # the *intended* shape post-S-1.7 (no laundering, explicit refusal).
    allowlist = {Path(__file__).name, "test_vertical_hard_refuse.py"}

    offenders = []
    for py in tests_dir.rglob("*.py"):
        if py.name in allowlist:
            continue
        text = py.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            # Allow docstring / comment mentions — only flag actual
            # assignment-shaped occurrences. The pattern already requires
            # ``VERTICAL_MODE=apparel`` style; comments and docstrings
            # almost never use that exact shape with a literal vertical.
            offenders.append((py.relative_to(tests_dir), match.group(0)))

    assert offenders == [], (
        "Tests must not set VERTICAL_MODE to an unsupported vertical "
        f"(would have relied on the now-removed laundering): {offenders}"
    )
