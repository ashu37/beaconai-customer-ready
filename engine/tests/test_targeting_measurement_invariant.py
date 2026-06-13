"""Synthetic Blocker Fix 2 — targeting-measurement structural invariant.

Hard contract (from `memory.md` Phase 1, "Final approved architecture
invariants"):

    `evidence_class == "targeting"` ⇒ `measurement is None`.

The merchant-facing renderer hides ``measurement`` on targeting cards via
M8 (the targeting-no-dollar-headline invariant). That is a *cosmetic*
guarantee. This file pins the *structural* guarantee on
``EngineRun.recommendations[]`` and ``EngineRun.considered[]`` so that:

- Internal receipts (``engine_run.json``, debug.html, outcome log) cannot
  carry saturated ``p_internal`` values on targeting cards.
- Future regressions in the renderer cannot reintroduce the leak by
  forgetting to special-case targeting.
- The ML-readiness writers (M9) and any future calibration consumer
  cannot accidentally train on targeting "measurements".

The leak path the synthetic Phase 5 e2e review surfaced:

- A legacy action enters the adapter with a populated ``p``,
  ``effect_abs``, etc., but WITHOUT a ``evidence_class`` field on the
  action dict.
- ``_coerce_evidence(None)`` defaults the PlayCard to
  ``EvidenceClass.TARGETING``.
- ``_build_measurement_from_legacy`` only short-circuits when the action
  dict explicitly stamps ``evidence_class == "targeting"`` (line 112).
  When the stamp is missing, it builds a full ``Measurement`` containing
  saturated ``p_internal`` (e.g., 1.6e-72 from the ``promo_anomaly``
  fixture).
- The resulting ``PlayCard`` carries ``evidence_class=TARGETING`` AND a
  non-null ``Measurement``, violating the invariant.

Fix 2's job: enforce the invariant *structurally* at the terminal
PlayCard creation step, not at render time.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

from src.engine_run import (
    Audience,
    EngineRun,
    EvidenceClass,
    Measurement,
    PlayCard,
)
from src.engine_run_adapter import (
    _action_to_play_card,
    build_engine_run_from_legacy,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC_RUNS_DIR = REPO_ROOT / "tests" / "fixtures" / "synthetic_runs"


# ---------------------------------------------------------------------------
# Unit tests — adapter terminal step
# ---------------------------------------------------------------------------


def test_action_to_play_card_clears_measurement_when_targeting_no_evidence_stamp():
    """Leak path: action has a populated p/effect/n but NO ``evidence_class``.

    The action's ``evidence_class`` field is missing so the adapter's
    ``_coerce_evidence`` defaults the PlayCard to TARGETING. The
    ``_build_measurement_from_legacy`` early-return only fires when the
    action explicitly stamps "targeting", so it would otherwise build a
    full ``Measurement`` here.

    The structural invariant must coerce ``measurement`` to ``None`` at
    the terminal ``_action_to_play_card`` step regardless of the
    upstream stamp.
    """
    action = {
        "play_id": "leaky_targeting",
        # NOTE: deliberately no "evidence_class" key.
        "p": 1.6e-72,
        "effect_abs": 0.0,
        "n": 1234,
        "ci_low": 0.0,
        "ci_high": 0.0,
        "metric": "saturated_metric",
        "primary_window": "L28",
        "consistency_across_windows": 3,
    }

    card = _action_to_play_card(action)

    assert card.evidence_class == EvidenceClass.TARGETING, (
        "Sanity: leak path requires the PlayCard to coerce to TARGETING "
        "when the action has no evidence_class stamp."
    )
    assert card.measurement is None, (
        "Targeting PlayCards MUST have measurement=None structurally, "
        "regardless of whether the upstream legacy action carried "
        "p/effect/CI fields."
    )


def test_action_to_play_card_explicit_targeting_stamp_keeps_measurement_none():
    """When the action explicitly stamps targeting, measurement is None.

    This case is already handled by ``_build_measurement_from_legacy``'s
    early-return, but the assertion still pins it so a regression in
    that early-return path would be caught by the same test file.
    """
    action = {
        "play_id": "explicit_targeting",
        "evidence_class": "targeting",
        "p": 0.001,
        "effect_abs": 0.05,
        "n": 500,
    }
    card = _action_to_play_card(action)
    assert card.evidence_class == EvidenceClass.TARGETING
    assert card.measurement is None


def test_action_to_play_card_measured_keeps_measurement():
    """Negative test: measured PlayCards must keep their Measurement.

    The structural clear must NOT over-fire onto measured cards.
    """
    action = {
        "play_id": "measured_winback",
        "evidence_class": "measured",
        "p": 0.004,
        "effect_abs": 0.12,
        "n": 800,
        "metric": "reactivation_rate",
        "primary_window": "L28",
        "consistency_across_windows": 2,
    }
    card = _action_to_play_card(action)
    assert card.evidence_class == EvidenceClass.MEASURED
    assert card.measurement is not None
    assert card.measurement.p_internal == 0.004
    assert card.measurement.observed_effect == 0.12


def test_action_to_play_card_directional_keeps_measurement():
    """Negative test: directional PlayCards must keep their Measurement."""
    action = {
        "play_id": "directional_play",
        "evidence_class": "directional",
        "p": 0.03,
        "effect_abs": 0.04,
        "n": 600,
        "metric": "returning_customer_share",
        "primary_window": "L28",
        "consistency_across_windows": 2,
    }
    card = _action_to_play_card(action)
    assert card.evidence_class == EvidenceClass.DIRECTIONAL
    assert card.measurement is not None


def test_build_engine_run_targeting_recommendations_have_no_measurement():
    """End-to-end through ``build_engine_run_from_legacy``.

    The adapter is the terminal step that produces ``EngineRun``
    receipts on the legacy path. After this call, every PlayCard with
    ``evidence_class == TARGETING`` in ``recommendations`` must have
    ``measurement is None``.
    """
    actions_bundle = {
        "actions": [
            # Leak shape: targeting (default) + populated stats.
            {
                "play_id": "leaky_targeting",
                "p": 0.0,
                "effect_abs": 0.05,
                "n": 200,
                "metric": "saturated",
                "primary_window": "L28",
            },
            # Explicit targeting stamp + populated stats.
            {
                "play_id": "explicit_targeting",
                "evidence_class": "targeting",
                "p": 1e-30,
                "effect_abs": 0.10,
                "n": 400,
                "metric": "saturated",
            },
        ]
    }
    er = build_engine_run_from_legacy(actions_bundle, aligned={}, df=None, cfg={})

    targeting_cards = [
        c for c in er.recommendations if c.evidence_class == EvidenceClass.TARGETING
    ]
    assert targeting_cards, "Sanity: fixture should produce at least one targeting card."
    for c in targeting_cards:
        assert c.measurement is None, (
            f"PlayCard {c.play_id!r} violates the targeting-measurement "
            f"invariant: evidence_class=TARGETING but measurement={c.measurement!r}."
        )


# ---------------------------------------------------------------------------
# Matrix-wide regression test (DS-required forcing function)
# ---------------------------------------------------------------------------


def _collect_engine_run_files() -> List[Path]:
    """Return the list of synthetic-matrix ``engine_run.json`` files.

    Search locations (in order):
      - ``tests/fixtures/synthetic_runs/<scenario>/engine_run.json``
      - ``tests/fixtures/synthetic/<scenario>/engine_run.json``

    If neither directory contains durable ``engine_run.json`` artifacts,
    returns an empty list. The matrix-wide test below skips with a
    clear reason in that case (see Fix 2 plan: matrix artifacts depend
    on the harness/runner work landing in Fix 6/7).
    """
    candidates: List[Path] = []
    for root in (
        SYNTHETIC_RUNS_DIR,
        REPO_ROOT / "tests" / "fixtures" / "synthetic",
    ):
        if root.exists():
            candidates.extend(sorted(root.rglob("engine_run.json")))
    return candidates


def test_matrix_no_targeting_with_measurement():
    """Iterate every persisted synthetic ``engine_run.json`` and assert
    that no ``recommendations[]`` or ``considered[]`` PlayCard with
    ``evidence_class == "targeting"`` carries a non-null ``measurement``.

    NOTE: Skipped when the synthetic matrix runner does not produce
    durable ``engine_run.json`` artifacts in the repo. The matrix-runner
    upgrade is Fix 6/7 in the synthetic-blocker-fix plan; this test
    will activate automatically once those fixes land.
    """
    files = _collect_engine_run_files()
    if not files:
        pytest.skip(
            "No synthetic-matrix engine_run.json artifacts on disk yet "
            "(Fix 6/7 will produce them). Unit tests in this file pin "
            "the invariant at the adapter level in the meantime."
        )

    offenders: List[str] = []
    for path in files:
        try:
            payload = json.loads(path.read_text())
        except Exception as exc:  # pragma: no cover - file-IO defense only
            offenders.append(f"{path}: unreadable ({exc!r})")
            continue
        for section in ("recommendations", "considered"):
            for card in payload.get(section) or []:
                # ``considered`` carries RejectedPlay shape, which has no
                # ``evidence_class`` field. Only PlayCards do; the
                # invariant only applies to those.
                ev = card.get("evidence_class")
                if ev != EvidenceClass.TARGETING.value:
                    continue
                if card.get("measurement") is not None:
                    offenders.append(
                        f"{path} :: {section} :: play_id={card.get('play_id')!r} "
                        f"carries a non-null measurement under evidence_class=targeting."
                    )

    assert not offenders, (
        "Targeting cards with non-null measurement found in matrix "
        "artifacts (violates structural invariant):\n  - "
        + "\n  - ".join(offenders)
    )


# ---------------------------------------------------------------------------
# Direct construction guard via the adapter terminal step
# ---------------------------------------------------------------------------


def test_terminal_adapter_clears_measurement_on_pre_built_targeting_card():
    """Defensive: even if a targeting card with measurement somehow
    arrives at the adapter terminal step (e.g., because a future
    builder constructed it directly), the structural clear at the
    terminal step in ``_action_to_play_card`` prevents the leak.

    This is the closest unit-level analog to the matrix-wide regression
    test on persisted EngineRun artifacts: any code path that funnels
    through ``_action_to_play_card`` is structurally safe.
    """
    # Construct a leak-shaped legacy action: caller forgot to stamp
    # ``evidence_class`` and the default falls to targeting, but the
    # action carries the same saturated stats the synthetic
    # ``promo_anomaly`` fixture produced.
    action = {
        "play_id": "synthetic_leak_repro",
        "p": 1.6e-72,
        "effect_abs": 0.0,
        "n": 1234,
    }

    card = _action_to_play_card(action)

    assert card.evidence_class == EvidenceClass.TARGETING
    assert card.measurement is None, (
        "Adapter terminal step must structurally clear measurement on "
        "targeting cards. Found: " + repr(card.measurement)
    )
