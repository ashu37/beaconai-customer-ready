"""S-FE-rfm-segment-distribution — aggregate ``segment_distribution`` on the
RFM ModelCard (FOUNDER-AUTHORIZED additive within 2.1.0; L-EV-17).

Covers:

- ``SegmentBand`` + ``segment_distribution`` serialize / deserialize through
  the EngineRun ``_to_jsonable`` recursion (enum unwrap on the paired
  null-reason).
- Populated on a VALIDATED RFM fit (reuses the monotone DGP positive control
  from ``test_s12_t1_rfm_fit``): bands' ``n`` sum to ``n_observed``, shares
  sum to ~1.0, ordering is ``n`` descending, no paired suppression reason.
- ``None`` + ``FIT_NOT_VALIDATED`` reason when RFM REFUSED / INSUFFICIENT_DATA
  (no fabricated/partial distribution — RFM suppresses as a unit, L-EV-15).
- ``from_dict`` tolerates absence (older runs / non-RFM cards -> ``None``).
- AGGREGATE-ONLY guard: ``SegmentBand`` carries ONLY {segment_name, n, share}
  — no monetary / dollar / per-customer / lift field.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from src.engine_run import EngineRun
from src.predictive.model_card import (
    ModelCard,
    ModelFitStatus,
    RfmSegmentDistributionSuppressionReason,
    SegmentBand,
)
from src.predictive.rfm import (
    SEGMENT_LTV_RANK_ORDER,
    _compute_segment_distribution,
    fit_rfm,
)
from src.profile.types import BusinessStage, StoreProfile, Taxonomy

# Reuse the proven monotone-RFM DGP positive control from the S12-T1 suite.
from tests.test_s12_t1_rfm_fit import (
    _build_orders_minimal,
    _build_orders_with_monotone_rfm_structure,
)


def _profile_mature_beauty() -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical="beauty"),
        business_stage=BusinessStage(stage="MATURE"),
    )


# ---------------------------------------------------------------------------
# SegmentBand shape — AGGREGATE-ONLY conformance
# ---------------------------------------------------------------------------


def test_segment_band_shape_is_aggregate_only():
    """SegmentBand carries ONLY {segment_name, n, share} — no monetary /
    per-customer / lift field (L-EV-17/20)."""
    field_names = {f.name for f in dataclasses.fields(SegmentBand)}
    assert field_names == {"segment_name", "n", "share"}

    forbidden_substrings = (
        "monetary",
        "dollar",
        "value",
        "revenue",
        "ltv",
        "lift",
        "rate",
        "projected",
        "customer_id",
        "customer",
        "amount",
        "spend",
        "aov",
    )
    for name in field_names:
        for bad in forbidden_substrings:
            assert bad not in name.lower(), (
                f"SegmentBand field {name!r} looks monetary/per-customer "
                f"({bad!r}); aggregate-only breach (L-EV-17/20)"
            )


def test_segment_band_serializes_round_trip():
    band = SegmentBand(segment_name="Champions", n=189, share=0.123)
    band2 = SegmentBand(**dataclasses.asdict(band))
    assert band == band2


# ---------------------------------------------------------------------------
# Pure aggregator: ordering + share + count invariants
# ---------------------------------------------------------------------------


def test_compute_segment_distribution_counts_shares_ordering():
    series = pd.Series(
        ["Hibernating"] * 5
        + ["Champions"] * 3
        + ["Lost"] * 2
    )
    bands = _compute_segment_distribution(series)

    # Sum of n equals total; shares sum to ~1.0.
    assert sum(b.n for b in bands) == len(series)
    assert sum(b.share for b in bands) == pytest.approx(1.0)

    # Ordering: n DESCENDING.
    ns = [b.n for b in bands]
    assert ns == sorted(ns, reverse=True)
    assert bands[0].segment_name == "Hibernating"

    # Per-band share == n / total.
    for b in bands:
        assert b.share == pytest.approx(b.n / len(series))


def test_compute_segment_distribution_tie_break_canonical_rank():
    # Two segments with equal counts; tie broken by canonical LTV rank
    # (Champions ahead of Lost).
    series = pd.Series(["Lost"] * 4 + ["Champions"] * 4)
    bands = _compute_segment_distribution(series)
    assert [b.segment_name for b in bands] == ["Champions", "Lost"]


def test_compute_segment_distribution_empty_series():
    assert _compute_segment_distribution(pd.Series([], dtype=object)) == []


# ---------------------------------------------------------------------------
# Populated on a VALIDATED / PROVISIONAL RFM fit
# ---------------------------------------------------------------------------


def test_segment_distribution_populated_on_validated_fit():
    orders = _build_orders_with_monotone_rfm_structure(n_customers=1100)
    card = fit_rfm(orders, _profile_mature_beauty())

    assert card.fit_status in {ModelFitStatus.VALIDATED, ModelFitStatus.PROVISIONAL}
    assert card.segment_distribution is not None
    assert card.segment_distribution_suppression_reason is None

    bands = card.segment_distribution
    assert len(bands) >= 1
    assert len(bands) <= len(SEGMENT_LTV_RANK_ORDER)

    # Bands' n sum to the analyzed base (n_observed).
    assert sum(b.n for b in bands) == card.n_observed
    # Shares sum to ~1.0.
    assert sum(b.share for b in bands) == pytest.approx(1.0, abs=1e-9)
    # Ordering: n descending.
    ns = [b.n for b in bands]
    assert ns == sorted(ns, reverse=True)
    # Every band names a real canonical segment.
    for b in bands:
        assert b.segment_name in SEGMENT_LTV_RANK_ORDER
        assert isinstance(b.n, int) and b.n > 0
        assert 0.0 < b.share <= 1.0


# ---------------------------------------------------------------------------
# RULE-A typed suppression on REFUSED / INSUFFICIENT_DATA
# ---------------------------------------------------------------------------


def test_segment_distribution_suppressed_on_insufficient_data():
    # Below the absolute customer floor (50) -> INSUFFICIENT_DATA.
    orders = _build_orders_minimal(n_customers=10)
    card = fit_rfm(orders, _profile_mature_beauty())

    assert card.fit_status in {
        ModelFitStatus.INSUFFICIENT_DATA,
        ModelFitStatus.REFUSED,
    }
    # RULE-A: None bands + paired typed reason (never a fabricated/partial
    # distribution — RFM suppresses as a unit, L-EV-15).
    assert card.segment_distribution is None
    assert (
        card.segment_distribution_suppression_reason
        is RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED
    )


def test_segment_distribution_suppressed_on_refused_degenerate():
    # Single dominant monetary value -> quintile collapse -> REFUSED.
    rng = np.random.default_rng(0)
    rows = []
    start = pd.Timestamp("2025-01-01")
    for c in range(200):
        rows.append(
            {
                "customer_id": f"cust{c:05d}",
                "order_date": start + pd.Timedelta(days=int(rng.integers(0, 30))),
                "total": 50.0,  # constant -> degenerate quintiles
            }
        )
    card = fit_rfm(pd.DataFrame(rows), _profile_mature_beauty())

    assert card.fit_status in {ModelFitStatus.REFUSED, ModelFitStatus.INSUFFICIENT_DATA}
    assert card.segment_distribution is None
    assert (
        card.segment_distribution_suppression_reason
        is RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED
    )


# ---------------------------------------------------------------------------
# Serialization through EngineRun + from_dict absence tolerance
# ---------------------------------------------------------------------------


def test_segment_distribution_serializes_through_engine_run():
    card = ModelCard(
        model_name="rfm",
        fit_status=ModelFitStatus.VALIDATED,
        segment_distribution=[
            SegmentBand(segment_name="Champions", n=189, share=0.45),
            SegmentBand(segment_name="Lost", n=236, share=0.55),
        ],
    )
    run = EngineRun(predictive_models={"rfm": card})
    payload = run.to_dict()

    bands = payload["predictive_models"]["rfm"]["segment_distribution"]
    assert bands == [
        {"segment_name": "Champions", "n": 189, "share": 0.45},
        {"segment_name": "Lost", "n": 236, "share": 0.55},
    ]
    # Paired reason None on a populated card; serializes as JSON null.
    assert payload["predictive_models"]["rfm"][
        "segment_distribution_suppression_reason"
    ] is None


def test_suppression_reason_enum_unwraps_in_serialization():
    card = ModelCard(
        model_name="rfm",
        fit_status=ModelFitStatus.REFUSED,
        segment_distribution=None,
        segment_distribution_suppression_reason=(
            RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED
        ),
    )
    run = EngineRun(predictive_models={"rfm": card})
    payload = run.to_dict()
    rfm = payload["predictive_models"]["rfm"]
    assert rfm["segment_distribution"] is None
    # Enum unwraps to its string value (not the enum repr).
    assert rfm["segment_distribution_suppression_reason"] == "fit_not_validated"


def test_modelcard_tolerates_field_absence():
    # Older / non-RFM cards constructed without the new kwargs default to None
    # (additive optional field; from_dict tolerance).
    card = ModelCard(model_name="bgnbd", fit_status=ModelFitStatus.VALIDATED)
    assert card.segment_distribution is None
    assert card.segment_distribution_suppression_reason is None

    # An EngineRun.from_dict on a payload with no segment_distribution key
    # round-trips without error (predictive_models pass through as-is).
    payload = {"schema_version": "2.1.0", "predictive_models": {}}
    run = EngineRun.from_dict(payload)
    assert run.predictive_models == {}
