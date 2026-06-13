"""Sprint 13 Ticket T2 — PlayCard predicted_segment + model_card_ref unit tests.

Unit coverage for the consumer-wiring module at
:mod:`src.predictive.consumer_wiring`. Covers:

1. Flag default OFF — flag-not-in-cfg path leaves PlayCards untouched.
2. Flag ON, RFM VALIDATED — modal segment + model_card_ref populate.
3. Modal-segment stability floor (n_audience < 50) — segment_name None.
4. Modal-segment stability floor (modal_share < 0.30) — segment_name None.
5. model_card_ref.strategy_used reflects the chain walk.
6. fit_warnings grammar (``"{LEVEL}:{substrate}"``) for fall-through.

These are pure unit tests on synthetic ModelCard fixtures + fabricated
RFM parquets. No engine harness, no real audience builder dependency.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import EngineRun, FitWarning, FitWarningLevel, PlayCard  # noqa: E402
from src.predictive.consumer_wiring import (  # noqa: E402
    populate_play_card_consumers,
)
from src.predictive.model_card import ModelCard, ModelFitStatus  # noqa: E402
from src.utils import DEFAULTS  # noqa: E402


# ---------------------------------------------------------------------------
# Flag default
# ---------------------------------------------------------------------------


def test_engine_v2_play_predicted_segment_default_on_after_t2_5() -> None:
    """ENGINE_V2_PLAY_PREDICTED_SEGMENT default ON after S13-T2.5 atomic flip.

    Per S12-T2.5 / S13-T1.5 precedent (Option a), the default-OFF
    assertion was inverted in place at the atomic-flip ticket rather
    than left to grow KI-NEW-U's stale flag-default-off test list.
    """

    import os

    if "ENGINE_V2_PLAY_PREDICTED_SEGMENT" in os.environ:
        pytest.skip(
            "ENGINE_V2_PLAY_PREDICTED_SEGMENT env override present; "
            "default test n/a"
        )
    assert DEFAULTS["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] is True


# ---------------------------------------------------------------------------
# Synthetic ModelCard helpers
# ---------------------------------------------------------------------------


def _mc(name: str, status: ModelFitStatus) -> ModelCard:
    """Build a minimal ModelCard with a specific fit_status.

    The chain walker only reads ``fit_status``; all other fields can be
    defaults / minimal.
    """

    return ModelCard(
        model_name=name,
        fit_status=status,
        fit_warnings=[],
        n_observed=100,
        fit_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _make_engine_run_with_recommendations(
    play_ids: list[str],
    predictive_models: Dict[str, ModelCard],
) -> EngineRun:
    """Construct an EngineRun with a list of PlayCards on .recommendations."""

    cards = [PlayCard(play_id=pid) for pid in play_ids]
    return EngineRun(recommendations=cards, predictive_models=predictive_models)


def _write_rfm_parquet(
    tmp_path: Path,
    customer_segments: Dict[str, str],
) -> Path:
    """Write a per-store RFM parquet with the given customer->segment map."""

    target = tmp_path / "rfm.parquet"
    df = pd.DataFrame(
        {
            "customer_id": list(customer_segments.keys()),
            "segment_name": list(customer_segments.values()),
        }
    )
    df.to_parquet(target, index=False)
    return target


# ---------------------------------------------------------------------------
# Flag-OFF behavior is enforced by the orchestration callsite in main.py,
# not the module itself — the module is unconditionally pure when called.
# We assert that here by NOT calling populate_play_card_consumers in the
# OFF case and confirming defaults stay None.
# ---------------------------------------------------------------------------


def test_flag_off_predicted_segment_none() -> None:
    """Without calling the consumer-wiring pass, PlayCards stay None.

    Mirrors the flag-OFF code path in main.py — the orchestrator skips
    the populate call when ``ENGINE_V2_PLAY_PREDICTED_SEGMENT`` is
    False, so the PlayCard defaults of ``None`` are preserved.
    """

    engine_run = _make_engine_run_with_recommendations(
        ["winback_dormant_cohort"], predictive_models={}
    )
    # Do NOT call populate_play_card_consumers.
    assert engine_run.recommendations[0].predicted_segment is None
    assert engine_run.recommendations[0].model_card_ref is None


# ---------------------------------------------------------------------------
# Flag-ON behavior — module called explicitly.
# ---------------------------------------------------------------------------


def test_model_card_ref_populated_with_strategy_used(tmp_path: Path) -> None:
    """Calling the wiring pass populates model_card_ref.strategy_used."""

    predictive_models = {
        "bgnbd": _mc("bgnbd", ModelFitStatus.VALIDATED),
    }
    engine_run = _make_engine_run_with_recommendations(
        ["winback_dormant_cohort"], predictive_models=predictive_models
    )
    out = populate_play_card_consumers(
        engine_run,
        audience_ids_resolver=lambda _pid: set(),
        rfm_parquet_path=None,
    )
    mcr = out.recommendations[0].model_card_ref
    assert mcr is not None
    assert mcr.strategy_used == "BGNBD"
    # No warnings on the happy path.
    assert mcr.fit_warnings == []
    # Selected position is on the chain.
    assert ("bgnbd", "VALIDATED") in mcr.fit_status_chain


def test_model_card_ref_fit_warnings_grammar(tmp_path: Path) -> None:
    """Fall-through fit_warnings match the LOCKED grammar.

    BG/NBD REFUSED → CF INSUFFICIENT_DATA → survival REFUSED →
    RFM PROVISIONAL → terminal selection on RFM with PROVISIONAL_SELECTED
    warning.
    """

    predictive_models = {
        "bgnbd": _mc("bgnbd", ModelFitStatus.REFUSED),
        "cf": _mc("cf", ModelFitStatus.INSUFFICIENT_DATA),
        "survival": _mc("survival", ModelFitStatus.REFUSED),
        "rfm": _mc("rfm", ModelFitStatus.PROVISIONAL),
    }
    engine_run = _make_engine_run_with_recommendations(
        ["winback_dormant_cohort"], predictive_models=predictive_models
    )
    out = populate_play_card_consumers(
        engine_run,
        audience_ids_resolver=lambda _pid: set(),
        rfm_parquet_path=None,
    )
    mcr = out.recommendations[0].model_card_ref
    assert mcr is not None
    assert mcr.strategy_used == "RFM"
    # Grammar pin (S13.6-T4: typed): every entry is a typed FitWarning
    # with ``level: FitWarningLevel`` ∈ {PROVISIONAL_SELECTED,
    # MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED} + ``substrate: str``.
    for entry in mcr.fit_warnings:
        assert isinstance(entry, FitWarning), (
            f"S13.6-T4 typed-grammar pin: fit_warnings entries must be "
            f"FitWarning instances, got {type(entry).__name__}: {entry!r}"
        )
        assert isinstance(entry.level, FitWarningLevel)
        assert entry.substrate, f"missing substrate on {entry!r}"
    # The terminal PROVISIONAL_SELECTED warning is present for RFM.
    assert FitWarning(FitWarningLevel.PROVISIONAL_SELECTED, "rfm") in mcr.fit_warnings
    # The fall-through warnings cite the right LEVEL per substrate.
    assert FitWarning(FitWarningLevel.MODEL_FIT_REFUSED, "bgnbd") in mcr.fit_warnings
    assert FitWarning(FitWarningLevel.MODEL_FIT_INSUFFICIENT_DATA, "cf") in mcr.fit_warnings
    assert FitWarning(FitWarningLevel.MODEL_FIT_REFUSED, "survival") in mcr.fit_warnings


def test_predicted_segment_populates_when_rfm_audience_clears_floor(
    tmp_path: Path,
) -> None:
    """Synthetic 100-customer audience, 60% Champions → segment_name populated."""

    # 100 customers; 60 Champions, 40 At Risk. Modal share = 0.60 (above
    # 0.30 floor); n = 100 (above 50 floor).
    segments = {f"c{i:03d}": "Champions" for i in range(60)}
    segments.update({f"c{i:03d}": "At Risk" for i in range(60, 100)})
    rfm_path = _write_rfm_parquet(tmp_path, segments)

    audience: Set[str] = {f"c{i:03d}" for i in range(100)}
    predictive_models = {
        "bgnbd": _mc("bgnbd", ModelFitStatus.VALIDATED),
    }
    engine_run = _make_engine_run_with_recommendations(
        ["winback_dormant_cohort"], predictive_models=predictive_models
    )
    out = populate_play_card_consumers(
        engine_run,
        audience_ids_resolver=lambda _pid: audience,
        rfm_parquet_path=rfm_path,
    )
    ps = out.recommendations[0].predicted_segment
    assert ps is not None
    assert ps.segment_name == "Champions"
    assert ps.n_audience == 100
    assert ps.audience_modal_share == pytest.approx(0.60, abs=1e-6)


def test_modal_segment_floor_n_below_50_segment_name_none(tmp_path: Path) -> None:
    """Audience n=30 (below 50 floor) → segment_name suppressed; audit fields populated."""

    # 30 customers, all Champions (100% modal share). n=30 < 50 floor.
    segments = {f"c{i:03d}": "Champions" for i in range(30)}
    rfm_path = _write_rfm_parquet(tmp_path, segments)

    audience: Set[str] = {f"c{i:03d}" for i in range(30)}
    predictive_models = {"bgnbd": _mc("bgnbd", ModelFitStatus.VALIDATED)}
    engine_run = _make_engine_run_with_recommendations(
        ["winback_dormant_cohort"], predictive_models=predictive_models
    )
    out = populate_play_card_consumers(
        engine_run,
        audience_ids_resolver=lambda _pid: audience,
        rfm_parquet_path=rfm_path,
    )
    ps = out.recommendations[0].predicted_segment
    assert ps is not None
    # Stability floor: segment_name suppressed, audit fields uncensored.
    assert ps.segment_name is None
    assert ps.n_audience == 30
    assert ps.audience_modal_share == pytest.approx(1.0, abs=1e-6)


def test_modal_segment_floor_modal_share_below_30_pct_segment_name_none(
    tmp_path: Path,
) -> None:
    """100 customers split evenly across 5 segments (20% modal) → segment_name None."""

    # 100 customers, 5 segments of 20 each → modal share = 0.20.
    names = ["Champions", "At Risk", "Loyal Customers", "Promising", "Hibernating"]
    segments = {}
    for idx in range(100):
        segments[f"c{idx:03d}"] = names[idx % 5]
    rfm_path = _write_rfm_parquet(tmp_path, segments)

    audience: Set[str] = set(segments.keys())
    predictive_models = {"bgnbd": _mc("bgnbd", ModelFitStatus.VALIDATED)}
    engine_run = _make_engine_run_with_recommendations(
        ["winback_dormant_cohort"], predictive_models=predictive_models
    )
    out = populate_play_card_consumers(
        engine_run,
        audience_ids_resolver=lambda _pid: audience,
        rfm_parquet_path=rfm_path,
    )
    ps = out.recommendations[0].predicted_segment
    assert ps is not None
    assert ps.segment_name is None
    assert ps.n_audience == 100
    # 0.20 < 0.30 floor.
    assert ps.audience_modal_share == pytest.approx(0.20, abs=1e-6)


def test_predicted_segment_none_when_rfm_parquet_absent(tmp_path: Path) -> None:
    """No RFM parquet → predicted_segment stays None; model_card_ref still populates."""

    predictive_models = {"bgnbd": _mc("bgnbd", ModelFitStatus.VALIDATED)}
    engine_run = _make_engine_run_with_recommendations(
        ["winback_dormant_cohort"], predictive_models=predictive_models
    )
    missing = tmp_path / "nope" / "rfm.parquet"
    out = populate_play_card_consumers(
        engine_run,
        audience_ids_resolver=lambda _pid: {"c001", "c002"},
        rfm_parquet_path=missing,
    )
    assert out.recommendations[0].predicted_segment is None
    # Chain-walk audit is independent of RFM availability.
    assert out.recommendations[0].model_card_ref is not None
    assert out.recommendations[0].model_card_ref.strategy_used == "BGNBD"


def test_replenishment_due_uses_replenishment_timing_intent(tmp_path: Path) -> None:
    """replenishment_due routes to REPLENISHMENT_TIMING chain (survival head)."""

    predictive_models = {
        "bgnbd": _mc("bgnbd", ModelFitStatus.VALIDATED),
        "survival": _mc("survival", ModelFitStatus.VALIDATED),
    }
    engine_run = _make_engine_run_with_recommendations(
        ["replenishment_due"], predictive_models=predictive_models
    )
    out = populate_play_card_consumers(
        engine_run,
        audience_ids_resolver=lambda _pid: set(),
        rfm_parquet_path=None,
    )
    mcr = out.recommendations[0].model_card_ref
    assert mcr is not None
    # REPLENISHMENT_TIMING chain head is survival, not BG/NBD.
    assert mcr.strategy_used == "SURVIVAL"


def test_predicted_segment_roundtrip(tmp_path: Path) -> None:
    """Extended PredictedSegment + ModelCardRef round-trip through to_dict/from_dict."""

    from src.engine_run import _from_dict_model_card_ref, _from_dict_predicted_segment
    from dataclasses import asdict

    segments = {f"c{i:03d}": "Champions" for i in range(60)}
    segments.update({f"c{i:03d}": "At Risk" for i in range(60, 100)})
    rfm_path = _write_rfm_parquet(tmp_path, segments)

    audience: Set[str] = {f"c{i:03d}" for i in range(100)}
    predictive_models = {"rfm": _mc("rfm", ModelFitStatus.VALIDATED)}
    # BG/NBD missing → INSUFFICIENT_DATA fall-through to CF (missing →
    # INSUFFICIENT_DATA), survival (missing → INSUFFICIENT_DATA), then
    # RFM VALIDATED.
    engine_run = _make_engine_run_with_recommendations(
        ["winback_dormant_cohort"], predictive_models=predictive_models
    )
    out = populate_play_card_consumers(
        engine_run,
        audience_ids_resolver=lambda _pid: audience,
        rfm_parquet_path=rfm_path,
    )
    pc = out.recommendations[0]

    ps_d = asdict(pc.predicted_segment)
    mcr_d = asdict(pc.model_card_ref)
    ps_back = _from_dict_predicted_segment(ps_d)
    mcr_back = _from_dict_model_card_ref(mcr_d)
    assert ps_back == pc.predicted_segment
    # fit_status_chain round-trips list-of-lists -> list-of-tuples.
    assert mcr_back.strategy_used == pc.model_card_ref.strategy_used
    assert mcr_back.fit_warnings == pc.model_card_ref.fit_warnings
    assert mcr_back.fit_status_chain == pc.model_card_ref.fit_status_chain


def test_rfm_refused_with_parquet_present_segment_name_none(
    tmp_path: Path,
) -> None:
    """DS T2 §G nit 2 carry-forward (S13-T3): RFM REFUSED + parquet present.

    DS T2 §G nit 2 PREDICTED that when ``rfm.fit_status=REFUSED`` AND a
    parquet artifact exists on disk AND the audience intersects with
    it, the consumer-wiring pass would emit
    ``predicted_segment.segment_name=None`` AND
    ``model_card_ref.fit_warnings`` would carry the
    ``MODEL_FIT_REFUSED:rfm`` entry per the LOCKED
    ``"{LEVEL}:{substrate}"`` grammar.

    **OBSERVED BEHAVIOR (S13-T3, honest report per Pivot 5 + Pivot 6
    instrumentation-over-prediction):** the current implementation in
    ``src/predictive/consumer_wiring.py`` reads the parquet artifact
    directly without consulting ``rfm.fit_status``. When BG/NBD is
    VALIDATED (so the chain selects BG/NBD, not RFM), the RFM substrate
    is NOT visited by the chain walker and consequently no
    ``MODEL_FIT_REFUSED:rfm`` warning is emitted on
    ``fit_warnings``. The modal segment IS computed from parquet
    (because the parquet read is gated on parquet presence, NOT on
    upstream RFM fit_status).

    Per S13-T3 dispatch constraint "DO NOT touch consumer_wiring.py",
    this test does NOT enforce the DS prediction (which would require
    a consumer_wiring.py source change to gate the parquet read on
    ``predictive_models["rfm"].fit_status``). Instead, the test pins
    the OBSERVED behavior verbatim and surfaces the discrepancy for
    DS review:

    - **DS-predicted contract** (not yet enforced): RFM REFUSED →
      parquet read suppressed → ``segment_name=None`` AND
      ``MODEL_FIT_REFUSED:rfm`` on fit_warnings (when RFM is visited).
    - **Observed contract** (current code): parquet read unconditional
      when path is provided; ``MODEL_FIT_REFUSED:rfm`` emitted only when
      the chain WALKS to RFM (i.e., upstream BG/NBD/CF/SURVIVAL also
      REFUSED/INSUFFICIENT). Selection by BG/NBD short-circuits the
      walk; downstream substrate fit-statuses are not surfaced.

    Open question for DS S13-T3-close: should the parquet read gate on
    ``rfm.fit_status`` (DS-predicted), or is it acceptable for
    parquet-derived segment_name to surface when BG/NBD selects (parquet
    is independent ground truth, RFM fit-status is about *ranking
    monotonicity*, not segment-name labeling)? Surface to DS for
    resolution.
    """

    # Construct a synthetic 100-customer audience with a 60/40 modal
    # split (would clear the floor IF the parquet read were gated on
    # rfm.fit_status; currently it is NOT gated).
    segments = {f"c{i:03d}": "Champions" for i in range(60)}
    segments.update({f"c{i:03d}": "At Risk" for i in range(60, 100)})
    rfm_path = _write_rfm_parquet(tmp_path, segments)
    audience: Set[str] = {f"c{i:03d}" for i in range(100)}

    predictive_models = {
        # bgnbd VALIDATED → chain selects BG/NBD; does NOT walk to RFM.
        "bgnbd": _mc("bgnbd", ModelFitStatus.VALIDATED),
        "rfm": _mc("rfm", ModelFitStatus.REFUSED),
    }
    engine_run = _make_engine_run_with_recommendations(
        ["winback_dormant_cohort"], predictive_models=predictive_models
    )
    out = populate_play_card_consumers(
        engine_run,
        audience_ids_resolver=lambda _pid: audience,
        rfm_parquet_path=rfm_path,
    )
    pc = out.recommendations[0]

    # OBSERVED contract pin (verbatim of current behavior):
    # 1. strategy_used == "BGNBD" (chain selects BG/NBD; does not walk to RFM).
    assert pc.model_card_ref is not None
    assert pc.model_card_ref.strategy_used == "BGNBD"
    # 2. Because the chain did NOT visit RFM, fit_warnings does NOT
    #    contain MODEL_FIT_REFUSED:rfm. This is the observed behavior;
    #    if DS rules the predicted contract is the intended one, a
    #    follow-up ticket must add fit_status gating to consumer_wiring.
    assert not any(
        fw.level == FitWarningLevel.MODEL_FIT_REFUSED and fw.substrate == "rfm"
        for fw in pc.model_card_ref.fit_warnings
    ), (
        "Observed-behavior pin: chain selected BG/NBD, so RFM was not "
        f"walked, so fit_warnings should NOT mention rfm. Got: "
        f"{pc.model_card_ref.fit_warnings!r}"
    )
    # 3. predicted_segment IS populated from parquet (current behavior
    #    is parquet-read-unconditional-on-presence). Document the
    #    observed segment_name + modal_share + n_audience.
    assert pc.predicted_segment is not None
    assert pc.predicted_segment.segment_name == "Champions"
    assert pc.predicted_segment.audience_modal_share == pytest.approx(0.60)
    assert pc.predicted_segment.n_audience == 100


def test_rfm_refused_when_chain_walks_to_rfm_surfaces_warning(
    tmp_path: Path,
) -> None:
    """Companion to DS T2 §G nit 2: when the chain ACTUALLY walks to RFM
    (all upstream substrates REFUSED/INSUFFICIENT), an
    ``rfm.fit_status=REFUSED`` MUST surface ``MODEL_FIT_REFUSED:rfm``
    on ``fit_warnings`` per the LOCKED grammar.

    This pins the side of the contract that IS enforced today by the
    chain walker (independent of the parquet-read-gating discussion).
    """

    segments = {f"c{i:03d}": "Champions" for i in range(60)}
    segments.update({f"c{i:03d}": "At Risk" for i in range(60, 100)})
    rfm_path = _write_rfm_parquet(tmp_path, segments)
    audience: Set[str] = {f"c{i:03d}" for i in range(100)}

    predictive_models = {
        "bgnbd": _mc("bgnbd", ModelFitStatus.REFUSED),
        "cf": _mc("cf", ModelFitStatus.INSUFFICIENT_DATA),
        "survival": _mc("survival", ModelFitStatus.REFUSED),
        "rfm": _mc("rfm", ModelFitStatus.REFUSED),
    }
    engine_run = _make_engine_run_with_recommendations(
        ["winback_dormant_cohort"], predictive_models=predictive_models
    )
    out = populate_play_card_consumers(
        engine_run,
        audience_ids_resolver=lambda _pid: audience,
        rfm_parquet_path=rfm_path,
    )
    pc = out.recommendations[0]
    assert pc.model_card_ref is not None
    # Chain walks all the way down — RECENCY is the terminal floor when
    # RFM is also REFUSED.
    assert pc.model_card_ref.strategy_used == "RECENCY"
    # MODEL_FIT_REFUSED:rfm IS emitted per LOCKED grammar when the
    # chain visits the REFUSED RFM substrate.
    assert any(
        fw.level == FitWarningLevel.MODEL_FIT_REFUSED and fw.substrate == "rfm"
        for fw in pc.model_card_ref.fit_warnings
    ), (
        "MODEL_FIT_REFUSED:rfm grammar entry missing from fit_warnings="
        f"{pc.model_card_ref.fit_warnings!r}"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
