"""B-3 (Sprint 1, Engineer B) — Hardcoded-fallback regression test.

Pure trust-contract test. No behavior change.

Scope: scan the rendered ``engine_run.json`` from end-to-end runs of the
Beauty pinned slate (``healthy_beauty_240d``) AND a synthetic supplements
run (``supplement_replenishment_240d``). For every PlayCard whose
``play_id`` is in the Phase 2 hardcoded-fallback risk set, assert that
neither ``measurement.effect_abs`` nor ``measurement.p_internal`` matches
any of the known fabricated constants.

Risk set = ``TARGETING_RECLASSIFY_PLAYS`` (the M4b reclassify list, which
covers ``subscription_nudge``, ``routine_builder``, ``empty_bottle``,
``category_expansion``, ``bestseller_amplify``, ``vip_no_discount_nurture``,
``replenishment_reminder``) plus a defensive ``empty_bottle`` membership
guard. The audit (``post-6b-stop-coding-audit.md`` §B-3) names these as the
plays whose Phase 2 emitters carry the constants:

- ``subscription_nudge`` ``effect=0.05``
- ``routine_builder`` ``effect=0.08``
- ``empty_bottle`` ``effect=0.10``, ``p=0.05/0.06``
- ``category_expansion`` similar shape
- ``discount_hygiene`` similar shape

Forbidden constant set (mirrors the audit / ticket scope): ``{0.02, 0.03,
0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40}``.

Scoping the assertion to the risk set + ``empty_bottle`` keeps false
positives manageable: a legitimately-computed ``effect_abs == 0.05`` on
e.g. ``first_to_second_purchase`` (which is wired through the real M3 +
multiwindow combiner path) would NOT trip this test, only the same value
on a play that is structurally at risk of holding a hardcoded fallback.

Per-ticket spec: failing this test means a Phase 2 fallback constant has
leaked into the rendered payload — a trust-contract regression. Re-pin
this test before any fix.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Phase 2 fallback constants the audit (post-6b-stop-coding-audit.md §B-3)
# names verbatim. These values appearing as ``measurement.effect_abs`` or
# ``measurement.p_internal`` on a structurally-at-risk play is a trust-
# contract violation — the engine has reverted to a hardcoded fallback
# rather than computing a real statistic.
FORBIDDEN_CONSTANTS: Tuple[float, ...] = (
    0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40,
)

# Equality tolerance: float exact-equality is brittle; the audit's
# constants are all 2-3 sigfigs so a 1e-9 tolerance is safe.
EQUALITY_TOL: float = 1e-9


def _is_forbidden(value: Optional[float]) -> Optional[float]:
    """Return the matching forbidden constant if ``value`` is ~equal to one."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    for c in FORBIDDEN_CONSTANTS:
        if abs(v - c) <= EQUALITY_TOL:
            return c
    return None


# ---------------------------------------------------------------------------
# Risk set
# ---------------------------------------------------------------------------


def _load_risk_set() -> frozenset:
    """The structural at-risk play_ids: TARGETING_RECLASSIFY_PLAYS plus a
    defensive ``empty_bottle`` membership guard (already in the set, but
    pinned here in case the source frozenset is ever pruned).
    """
    from src.evidence import TARGETING_RECLASSIFY_PLAYS

    return frozenset(TARGETING_RECLASSIFY_PLAYS | {"empty_bottle"})


RISK_SET: frozenset = _load_risk_set()


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def _iter_play_cards(engine_run: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield every PlayCard-shaped dict from a serialized EngineRun.

    Covers the three role surfaces a card can land in:
    ``recommendations``, ``recommended_experiments``, and
    ``considered`` (which is ``RejectedPlay``-shaped, not PlayCard, but
    we pass it through the same scan because Phase 2 fallback constants
    can still ride along in evidence-snapshot blocks).
    """
    for k in ("recommendations", "recommended_experiments"):
        for card in engine_run.get(k) or []:
            yield card
    # Considered list is RejectedPlay-shaped; it does not carry a
    # ``measurement`` block under the current contract so it's a no-op
    # for this scan, but iterate anyway to future-proof against
    # ``evidence_snapshot`` ever holding a typed measurement.
    for card in engine_run.get("considered") or []:
        yield card


def _measurement_violations(card: Dict[str, Any]) -> List[Tuple[str, float, float]]:
    """Return list of ``(field_name, observed_value, forbidden_constant)``
    tuples for every ``measurement`` field in ``card`` that matches a
    forbidden constant. Empty list ⇒ clean.
    """
    play_id = str(card.get("play_id") or "")
    if play_id not in RISK_SET:
        return []
    meas = card.get("measurement")
    if not isinstance(meas, dict):
        return []
    out: List[Tuple[str, float, float]] = []
    for field in ("effect_abs", "observed_effect", "p_internal"):
        # NOTE: the engine_run.py Measurement dataclass uses
        # ``observed_effect`` as the public field name; ``effect_abs`` is
        # checked too because some legacy serialization paths emit it.
        val = meas.get(field)
        hit = _is_forbidden(val)
        if hit is not None:
            out.append((field, float(val), hit))
    return out


def _scan(engine_run: Dict[str, Any]) -> List[Tuple[str, str, float, float]]:
    """Scan an EngineRun dict; return ``[(play_id, field, value, constant), ...]``."""
    failures: List[Tuple[str, str, float, float]] = []
    for card in _iter_play_cards(engine_run):
        play_id = str(card.get("play_id") or "")
        for field, value, constant in _measurement_violations(card):
            failures.append((play_id, field, value, constant))
    return failures


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def beauty_engine_run() -> Dict[str, Any]:
    """Run the Beauty pinned slate scenario; return parsed engine_run.json."""
    from tests.synthetic_harness import run_scenario

    with tempfile.TemporaryDirectory() as td:
        res = run_scenario("healthy_beauty_240d", Path(td))
        return json.loads(Path(res.engine_run_json_path).read_text())


@pytest.fixture(scope="module")
def supplements_engine_run() -> Dict[str, Any]:
    """Run the synthetic supplements scenario; return parsed engine_run.json.

    Per the ticket: full G-1 supplements pinned fixture is forthcoming
    (Sprint 4); the existing ``supplement_replenishment_240d`` synthetic
    is the closest available substitute and exercises the at-risk
    candidate paths (``empty_bottle``, ``subscription_nudge``,
    ``routine_builder``).
    """
    from tests.synthetic_harness import run_scenario

    with tempfile.TemporaryDirectory() as td:
        res = run_scenario("supplement_replenishment_240d", Path(td))
        return json.loads(Path(res.engine_run_json_path).read_text())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_risk_set_membership_pin():
    """Defensive: the at-risk play_ids must remain in the scan set even if
    ``TARGETING_RECLASSIFY_PLAYS`` is later pruned. A change to this
    assertion forces explicit founder-level review of the trust-contract
    surface area.
    """
    must_be_present = {
        "subscription_nudge",
        "routine_builder",
        "empty_bottle",
        "category_expansion",
        "bestseller_amplify",
    }
    missing = must_be_present - RISK_SET
    assert not missing, (
        f"Hardcoded-fallback risk set lost coverage of {missing!r}. "
        f"This is a trust-contract regression; re-add the play_id to "
        f"src/evidence.TARGETING_RECLASSIFY_PLAYS or extend the local "
        f"defensive set in this test."
    )


def test_no_hardcoded_fallbacks_on_beauty_pinned_slate(beauty_engine_run):
    """Beauty pinned slate must not surface any Phase 2 fallback constant
    on a structurally-at-risk play.
    """
    failures = _scan(beauty_engine_run)
    assert not failures, (
        f"Hardcoded-fallback constant leaked into Beauty pinned slate "
        f"engine_run.json. Each entry is (play_id, field, observed, "
        f"forbidden_constant): {failures!r}. This is a trust-contract "
        f"regression — the play emitter has reverted to a Phase 2 "
        f"hardcoded fallback rather than a computed statistic. Per audit "
        f"§B-3, fix the emitter, do not whitelist the value."
    )


def test_no_hardcoded_fallbacks_on_synthetic_supplements_run(supplements_engine_run):
    """Synthetic supplements run must not surface any Phase 2 fallback
    constant on a structurally-at-risk play. The G-1 pinned supplements
    fixture is forthcoming (Sprint 4); this test exercises the
    ``supplement_replenishment_240d`` synthetic in the meantime.
    """
    failures = _scan(supplements_engine_run)
    assert not failures, (
        f"Hardcoded-fallback constant leaked into supplements synthetic "
        f"engine_run.json. Each entry is (play_id, field, observed, "
        f"forbidden_constant): {failures!r}. This is a trust-contract "
        f"regression — the play emitter has reverted to a Phase 2 "
        f"hardcoded fallback rather than a computed statistic. Per audit "
        f"§B-3, fix the emitter, do not whitelist the value."
    )


# ---------------------------------------------------------------------------
# Self-tests for the scanner (so a future rewrite can't regress its own
# detection logic without flagging it).
# ---------------------------------------------------------------------------


def test_scanner_self_test_detects_forbidden_constant():
    """Synthetic at-risk card with effect_abs=0.05 must be flagged."""
    fake = {
        "recommendations": [
            {
                "play_id": "subscription_nudge",
                "measurement": {"effect_abs": 0.05, "p_internal": 0.0123},
            }
        ]
    }
    failures = _scan(fake)
    assert failures, "Scanner failed to flag a deliberately-forbidden constant."
    assert any(f[1] == "effect_abs" and f[3] == 0.05 for f in failures)


def test_scanner_self_test_ignores_non_risk_play():
    """Synthetic non-risk card with effect_abs=0.05 must NOT be flagged
    (legitimately-computed values that happen to equal a forbidden
    constant are out of scope unless the play_id is structurally at
    risk).
    """
    fake = {
        "recommendations": [
            {
                "play_id": "first_to_second_purchase",
                "measurement": {"effect_abs": 0.05, "p_internal": 0.012},
            }
        ]
    }
    failures = _scan(fake)
    assert not failures, (
        f"Scanner incorrectly flagged a non-risk play; the assertion is "
        f"intentionally scoped to TARGETING_RECLASSIFY_PLAYS + "
        f"empty_bottle. Got: {failures!r}"
    )


def test_scanner_self_test_ignores_missing_measurement():
    """Targeting-class cards with ``measurement=None`` are clean by
    construction (Phase 4.2 / G-4 reclassification ships these without
    a measurement block at all).
    """
    fake = {
        "recommendations": [
            {"play_id": "subscription_nudge", "measurement": None}
        ]
    }
    failures = _scan(fake)
    assert not failures
