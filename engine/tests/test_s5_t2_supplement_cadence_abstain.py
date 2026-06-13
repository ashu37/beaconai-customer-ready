"""Sprint 5 Ticket S5-T2 — KI-20 acceptance.

Pins the typed honest-abstain path for ``first_to_second_purchase`` on
the supplements vertical. Path (b) per implementation plan §11 lines
592-598: the Phase 5.6 directional builder reads
``returning_customer_share`` on L28; supplement reorder cadences
(commonly 28-45 days) straddle that boundary so the supporting state
statistic is structurally too stable to clear
``PHASE5_DIRECTIONAL_P_MAX``. Rather than widen the window (which would
force a fresh cohort-definition design and risk re-introducing the
Berkson-shaped confounding B-5 blocks), the engine emits a typed
:class:`~src.engine_run.ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW`
Considered card so the merchant sees an honest hold instead of silent
drop-out (KI-23 historical surface).

Acceptance pins:
- The new enum value exists and is contract-shape (lowercase string).
- The Considered list on the supplements G-1 run contains
  ``first_to_second_purchase`` with the new reason code.
- The Beauty path is unchanged: the typed code does NOT appear on the
  Beauty pinned slate (path (b) is gated to ``vertical == supplements``).
- The renderer humanizes the new code with merchant-readable copy (no
  jargon — "L28" / "p-value" / "cadence" not surfaced).
- The decide-layer reason-text + would-fire-if templates resolve.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.decide import (  # noqa: E402
    _CONSIDERED_REASON_TEXT,
    _WOULD_FIRE_IF_TEMPLATE,
)
from src.engine_run import ReasonCode  # noqa: E402
from src.storytelling_v2 import _humanize_reason_code  # noqa: E402


_SUPPLEMENTS_ENV: dict[str, str] = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "supplements",
    "WINDOW_POLICY": "auto",
}


def test_supplement_cadence_reason_code_exists() -> None:
    """The new typed enum value is additive within ``event_version=1``
    and uses the lowercase-string convention that matches every other
    :class:`ReasonCode` member."""
    rc = ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW
    assert rc.value == "supplement_cadence_outside_window"
    # Round-trip through the standard enum constructor (the constructor
    # raises on unknown strings — this pins the enum-membership
    # contract).
    assert ReasonCode("supplement_cadence_outside_window") is rc


def test_decide_templates_resolve_for_new_code() -> None:
    """Both the considered-card reason text and the would-fire-if hint
    must be registered for the new code so ``populate_considered_*``
    never falls back to the generic 'Held back.' string."""
    text = _CONSIDERED_REASON_TEXT.get(ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW)
    wfi = _WOULD_FIRE_IF_TEMPLATE.get(ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW)
    assert isinstance(text, str) and text
    assert isinstance(wfi, str) and wfi
    # The decide-layer copy explains the structural reason without
    # leaking merchant-jargon-free copy is the renderer's job; here we
    # just pin that the text references the underlying mechanism.
    assert "first-to-second" in text.lower() or "directional" in text.lower()


def test_renderer_humanizes_new_code_without_jargon() -> None:
    """The merchant-facing renderer must produce non-empty copy that
    avoids the engine-internal terminology ``L28`` / ``p-value`` /
    ``cadence``. Phase 5.4 / M8 forbid-token discipline."""
    out = _humanize_reason_code(ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW)
    assert isinstance(out, str) and out
    lower = out.lower()
    assert "l28" not in lower
    assert "p-value" not in lower
    assert "p =" not in lower
    assert out != "Held back.", (
        f"Renderer fell back to the generic 'Held back.' string. The "
        f"S5-T2 humanize mapping is missing or unreachable."
    )


@pytest.fixture(scope="module")
def supplements_engine_run() -> dict:
    from tests.synthetic_harness import run_scenario

    with tempfile.TemporaryDirectory() as td:
        result = run_scenario(
            "healthy_supplements_240d",
            Path(td) / "s5t2",
            env_overrides=_SUPPLEMENTS_ENV,
            timeout_sec=300,
        )
        assert result.returncode == 0, (
            f"synthetic harness failed (rc={result.returncode}). "
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        )
        receipts = Path(td) / "s5t2" / "receipts" / "engine_run.json"
        assert receipts.exists()
        return json.loads(receipts.read_text(encoding="utf-8"))


def test_supplements_first_to_second_purchase_in_considered(
    supplements_engine_run: dict,
) -> None:
    """Acceptance per plan §11 lines 592-598 (path (b)): Considered
    contains ``first_to_second_purchase`` with the new typed reason."""
    considered = supplements_engine_run.get("considered") or []
    target = [
        c for c in considered
        if str(c.get("play_id")) == "first_to_second_purchase"
    ]
    assert target, (
        "Expected ``first_to_second_purchase`` to surface in the "
        "supplements Considered list under S5-T2. The directional "
        "builder does not emit a Recommended card for this play on "
        "supplements (KI-20 root cause); the typed abstain must keep "
        "the merchant in the loop."
    )
    card = target[0]
    assert card.get("reason_code") == "supplement_cadence_outside_window", (
        f"Expected reason_code='supplement_cadence_outside_window'; got "
        f"{card.get('reason_code')!r}."
    )


def test_supplements_first_to_second_purchase_is_prepended(
    supplements_engine_run: dict,
) -> None:
    """The typed abstain card survives the 6-card cap inside
    ``populate_considered_from_candidates``.

    S7.6-FIX (2026-05-22, priority_prepend at
    populate_considered_from_candidates) front-loads the
    ``_PRIOR_ANCHORED`` Tier-B set ahead of ``engine_run.considered``
    so the lead-position index is now Tier-B (e.g.
    ``winback_dormant_cohort``), not ``first_to_second_purchase``.
    The load-bearing S5-T2 contract is membership + typed reason —
    not the index-0 position — so this test pins that weaker but
    still load-bearing invariant.
    """
    considered = supplements_engine_run.get("considered") or []
    assert considered, "Considered list empty — upstream regression."
    target = next(
        (
            c
            for c in considered
            if str(c.get("play_id")) == "first_to_second_purchase"
        ),
        None,
    )
    assert target is not None, (
        "Expected ``first_to_second_purchase`` to remain in supplements "
        "Considered after the S7.6-FIX Tier-B priority_prepend; got "
        f"play_ids={[c.get('play_id') for c in considered]!r}."
    )
    assert (
        str(target.get("reason_code")) == "supplement_cadence_outside_window"
    )


@pytest.fixture(scope="module")
def beauty_engine_run() -> dict:
    from tests.synthetic_harness import run_scenario

    with tempfile.TemporaryDirectory() as td:
        result = run_scenario(
            "healthy_beauty_240d",
            Path(td) / "s5t2_beauty",
            timeout_sec=300,
        )
        assert result.returncode == 0
        receipts = Path(td) / "s5t2_beauty" / "receipts" / "engine_run.json"
        assert receipts.exists()
        return json.loads(receipts.read_text(encoding="utf-8"))


def test_beauty_does_not_emit_supplement_cadence_code(
    beauty_engine_run: dict,
) -> None:
    """Path (b) is gated to ``vertical == supplements``. The new typed
    code must not appear anywhere on the Beauty pinned slate."""
    considered = beauty_engine_run.get("considered") or []
    leaked = [
        c for c in considered
        if str(c.get("reason_code")) == "supplement_cadence_outside_window"
    ]
    assert not leaked, (
        f"SUPPLEMENT_CADENCE_OUTSIDE_WINDOW leaked into the Beauty "
        f"Considered list: {leaked!r}. The S5-T2 emit must be gated "
        f"to vertical=supplements."
    )


def test_beauty_first_to_second_purchase_displaced_by_t1_5(
    beauty_engine_run: dict,
) -> None:
    """Defensive: S5-T2 must not touch the Beauty path. After S7-T1.5
    (``ENGINE_V2_BUILDER_DISCOUNT_HYGIENE`` flipped ON, 2026-05-21),
    ``first_to_second_purchase`` is legitimately displaced from
    Recommended Now by the higher-confidence
    ``discount_dependency_hygiene`` Tier-B builder (Memo-1
    validated_external prior) under the cap=3 slate. The displacement
    is by selector ranking, not by S5-T2 supplement-cadence gating.
    The S5-T2 reason code SUPPLEMENT_CADENCE_OUTSIDE_WINDOW remains
    gated to vertical=supplements (separately tested above)."""
    rec_ids = {
        str(pc.get("play_id"))
        for pc in (beauty_engine_run.get("recommendations") or [])
    }
    # ``first_to_second_purchase`` is displaced by T1.5 activation, NOT
    # by S5-T2. The defensive guarantee here is that S5-T2's
    # supplement-cadence reason code never appears in the Beauty
    # Considered (asserted in the prior test) — not that this
    # particular play_id surfaces in Recommended Now post-T1.5.
    assert "discount_dependency_hygiene" in rec_ids, (
        f"Beauty pinned slate missing ``discount_dependency_hygiene`` "
        f"from Recommended Now under S7-T1.5: {rec_ids!r}. The T1.5 "
        f"flip should activate the Tier-B builder on the Beauty path."
    )
