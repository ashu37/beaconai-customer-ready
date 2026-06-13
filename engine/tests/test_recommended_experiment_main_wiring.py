"""Phase 6A Ticket A4.5 — main.py wiring of M3 candidates into decide().

This file pins the wiring between ``src/main.py`` and
``src.decide.decide()`` for the new Recommended Experiment slate.

Ticket A4 added ``_select_recommended_experiments`` and the
``ENGINE_V2_SLATE`` flag, but ``main.py`` did not yet plumb the
already-built Phase 5 / M3 candidate list (``_phase5_cands``) into
``decide()``. As a result, even with ``ENGINE_V2_SLATE=true`` the
selector ran on ``candidates=None`` and always returned ``[]``.

Ticket A4.5 fixes that wiring. These tests pin:

1. ``decide()`` accepts and acts on the ``candidates=`` kwarg when the
   flag is on (live wiring contract).
2. ``decide()`` is defensive when no candidates are passed
   (``None`` / ``[]``).
3. ``decide()`` remains a no-op for the slate when the flag is off,
   even when candidates are passed.
4. ``src/main.py`` source contains the ``candidates=`` kwarg on the
   V2 decide call site (structural pin to prevent future regressions
   silently dropping the wiring).

The file does NOT exercise the full ``main.py`` pipeline end-to-end;
that requires CSV + filesystem fixtures and is covered by the
synthetic-harness tests (``tests/synthetic_harness.py``) when
``RUN_MAIN_E2E=1`` is set on the environment in B6.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import priors_loader as PL
from src.engine_run import (
    Audience,
    BriefingMeta,
    EngineRun,
    EvidenceClass,
    PlayCard,
)


@pytest.fixture(autouse=True)
def _reset_priors_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


class _Cand:
    """Duck-typed Candidate stand-in matching the selector contract.

    The selector reads ``play_id``, ``audience_size``,
    ``segment_definition``, ``preliminary_rejection_reason``, and
    ``audience_overlap``. The real ``src.detect.Candidate`` exposes the
    same surface; this stand-in keeps the test cheap and avoids pulling
    pandas in.
    """

    def __init__(
        self,
        play_id: str,
        audience_size: int,
        *,
        segment_definition: str = "test segment",
        preliminary_rejection_reason: Optional[str] = None,
        audience_overlap: Optional[Dict[str, float]] = None,
    ) -> None:
        self.play_id = play_id
        self.audience_size = audience_size
        self.segment_definition = segment_definition
        self.preliminary_rejection_reason = preliminary_rejection_reason
        self.audience_overlap = dict(audience_overlap or {})


def _measured_card(play_id: str = "first_to_second_purchase") -> PlayCard:
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.DIRECTIONAL,
        audience=Audience(size=1000, definition="recent first-time buyers"),
    )


def _engine_run_with_recs() -> EngineRun:
    return EngineRun(
        recommendations=[_measured_card()],
        briefing_meta=BriefingMeta(vertical="beauty"),
    )


# ---------------------------------------------------------------------------
# 1. Live wiring contract: when the slate flag is on AND candidates are
#    passed, the selector populates ``recommended_experiments``.
#
#    This is the test that replicates what ``main.py`` should do once the
#    ticket lands. Before A4.5, ``main.py`` does NOT pass ``candidates=``
#    to ``decide()`` at all; this test exercises the function-level
#    contract so we can prove the selector actually consumes them.
# ---------------------------------------------------------------------------


def test_main_wires_candidates_into_decide_when_decide_flag_on():
    from src.decide import decide

    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    run = _engine_run_with_recs()

    out = decide(
        run,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )

    assert len(out.recommended_experiments) == 2
    play_ids = sorted(c.play_id for c in out.recommended_experiments)
    assert play_ids == ["bestseller_amplify", "discount_hygiene"]


# ---------------------------------------------------------------------------
# 2. Defensive: ``candidates=None`` does not crash; selector returns [].
#
#    ``main.py`` falls back to ``None`` when the Phase 5 candidate-build
#    try/except branch fails. This test pins the contract.
# ---------------------------------------------------------------------------


def test_decide_handles_none_candidates_gracefully():
    from src.decide import decide

    run = _engine_run_with_recs()

    out = decide(
        run,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=None,
    )

    assert out.recommended_experiments == []


# ---------------------------------------------------------------------------
# 3. Defensive: ``candidates=[]`` does not crash; selector returns [].
# ---------------------------------------------------------------------------


def test_decide_handles_empty_candidates_gracefully():
    from src.decide import decide

    run = _engine_run_with_recs()

    out = decide(
        run,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=[],
    )

    assert out.recommended_experiments == []


# ---------------------------------------------------------------------------
# 4. Structural pin on ``src/main.py``: the V2 decide call site MUST pass
#    ``candidates=`` as a kwarg. This is a static-source assertion so that
#    a future refactor cannot silently drop the wiring.
# ---------------------------------------------------------------------------


def test_main_module_v2_decide_call_passes_candidates():
    main_path = REPO_ROOT / "src" / "main.py"
    src_text = main_path.read_text(encoding="utf-8")

    # The wiring contract: every ``_v2_decide(engine_run, ...)`` call must
    # include a ``candidates=`` kwarg literal. We allow flexible whitespace
    # and any value expression (we just want the kwarg present).
    pattern = re.compile(
        r"_v2_decide\s*\(\s*engine_run\s*,\s*cfg\s*=\s*cfg\s*,\s*candidates\s*=",
        re.MULTILINE,
    )
    assert pattern.search(src_text), (
        "Expected `_v2_decide(engine_run, cfg=cfg, candidates=...)` in src/main.py "
        "after Phase 6A Ticket A4.5; the slate selector cannot operate without "
        "candidates plumbed through. See the implementation manager A4.5 plan."
    )

    # And: every occurrence of `_v2_decide(` that is a call (not a comment
    # or string) must include a ``candidates=`` kwarg. Defensive: catch a
    # second call that forgets the kwarg.
    call_pattern = re.compile(r"_v2_decide\s*\(", re.MULTILINE)
    for match in call_pattern.finditer(src_text):
        # Walk from the open paren forward and confirm a ``candidates=``
        # appears before the matching close paren on this call. Use a
        # simple paren-balance scan — the call site is short and well
        # formed.
        start = match.end()
        depth = 1
        idx = start
        while idx < len(src_text) and depth > 0:
            ch = src_text[idx]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            idx += 1
        call_args = src_text[start : idx - 1]
        assert "candidates=" in call_args, (
            f"`_v2_decide(...)` call missing `candidates=` kwarg. "
            f"Call args were: {call_args!r}"
        )


# ---------------------------------------------------------------------------
# 5. Flag-off invariant: even when ``main.py`` would have plumbed
#    candidates, ``ENGINE_V2_SLATE=false`` keeps ``recommended_experiments``
#    empty. This pins the kill-switch promise.
# ---------------------------------------------------------------------------


def test_flag_off_keeps_recommended_experiments_empty_via_decide():
    from src.decide import decide

    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    run = _engine_run_with_recs()

    out = decide(
        run,
        cfg={"ENGINE_V2_SLATE": False, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )

    assert out.recommended_experiments == []
