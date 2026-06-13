"""S-FE-descriptive-distribution (L-EV-19 / L-EV-20) — tests.

FOUNDER-AUTHORIZED additive schema 2.0.0 -> 2.1.0 (docs/evidence_layer.md
§7 L-EV-19). Covers:

1.  Atom serialize / deserialize round-trip + descriptive-only guard
    (no dollar / lift field exists on the atom).
2.  The pure binning helper (build_descriptive_distribution) for each of
    the 4 kinds; convention (len(counts) == len(bins) - 1; clamping).
3.  Empty / absent / integrity-failed source -> suppressed + typed reason.
4.  Marker None pass-through when the parameter is None/TODO(S14); real
    marker carried for winback.
5.  Each of the 4 distributional builders stashes its kind + observed
    series; the producer (measurement_builder) binds the typed atom onto
    Audience.
6.  from_dict tolerates the field's absence (2.0.0 back-compat).
"""
from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import audience_builders as ab  # noqa: E402
from src import measurement_builder as mb  # noqa: E402
from src.engine_run import (  # noqa: E402
    Audience,
    DescriptiveDistribution,
    DescriptiveDistributionSuppressionReason,
    DistributionKind,
    EngineRun,
    PlayCard,
    build_descriptive_distribution,
)

ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


# ---------------------------------------------------------------------------
# (1) Atom round-trip + descriptive-only guard
# ---------------------------------------------------------------------------


def test_descriptive_distribution_round_trip_via_audience():
    dd = DescriptiveDistribution(
        kind=DistributionKind.DORMANCY_DAYS,
        bins=[0.0, 21.0, 45.0],
        counts=[3, 7],
        marker=45.0,
        suppressed=False,
        suppression_reason=None,
    )
    aud = Audience(id="a", definition="d", size=10, descriptive_distribution=dd)
    pc = PlayCard(play_id="winback_dormant_cohort", audience=aud)
    er = EngineRun(recommendations=[pc])
    payload = er.to_dict()
    # Serialized shape: enum values, bins/counts lists.
    aud_d = payload["recommendations"][0]["audience"]["descriptive_distribution"]
    assert aud_d["kind"] == "DORMANCY_DAYS"
    assert aud_d["bins"] == [0.0, 21.0, 45.0]
    assert aud_d["counts"] == [3, 7]
    assert aud_d["marker"] == 45.0
    assert aud_d["suppressed"] is False
    assert aud_d["suppression_reason"] is None
    # Round-trip back.
    er2 = EngineRun.from_dict(payload)
    dd2 = er2.recommendations[0].audience.descriptive_distribution
    assert dd2 is not None
    assert dd2.kind is DistributionKind.DORMANCY_DAYS
    assert dd2.bins == [0.0, 21.0, 45.0]
    assert dd2.counts == [3, 7]
    assert dd2.marker == 45.0
    assert dd2.suppressed is False
    assert dd2.suppression_reason is None


def test_descriptive_only_no_dollar_or_lift_field_on_atom():
    """L-EV-20: the atom carries observed counts + an optional marker only.
    No dollar / lift / rate / projection field may exist on it."""
    field_names = {f.name for f in fields(DescriptiveDistribution)}
    assert field_names == {
        "kind",
        "bins",
        "counts",
        "marker",
        "suppressed",
        "suppression_reason",
    }
    forbidden_substrings = (
        "dollar",
        "revenue",
        "value",
        "lift",
        "rate",
        "projected",
        "forecast",
        "p50",
        "p10",
        "p90",
        "aov",
    )
    for fn in field_names:
        for bad in forbidden_substrings:
            assert bad not in fn.lower(), (
                f"DescriptiveDistribution.{fn} looks inferential/monetary "
                f"({bad!r}); the atom is DESCRIPTIVE-ONLY (L-EV-20)."
            )


def test_distribution_kind_closed_set():
    assert {m.value for m in DistributionKind} == {
        "DORMANCY_DAYS",
        "AOV_GAP",
        "REORDER_GAP_DAYS",
        "DISCOUNT_FRACTION",
    }


def test_suppression_reason_closed_set():
    assert {m.value for m in DescriptiveDistributionSuppressionReason} == {
        "source_series_empty",
        "source_series_absent",
        "integrity_failed",
    }


# ---------------------------------------------------------------------------
# (2) Pure binning helper — convention + each kind
# ---------------------------------------------------------------------------


def test_build_helper_bins_and_counts_convention():
    dd = build_descriptive_distribution(
        DistributionKind.DORMANCY_DAYS,
        [22.0, 25.0, 31.0, 46.0],
        marker=45.0,
        bin_edges=[0.0, 21.0, 30.0, 45.0, 60.0],
    )
    assert dd.suppressed is False
    assert dd.suppression_reason is None
    # len(counts) == len(bins) - 1
    assert len(dd.counts) == len(dd.bins) - 1
    # sum of counts == number of observations (no observation dropped).
    assert sum(dd.counts) == 4
    assert dd.marker == 45.0


def test_build_helper_clamps_out_of_range_low_and_high():
    # values below first edge and above last edge land in the edge bins.
    dd = build_descriptive_distribution(
        DistributionKind.AOV_GAP,
        [-5.0, 1000.0],
        marker=None,
        bin_edges=[0.0, 50.0, 100.0],
    )
    assert sum(dd.counts) == 2  # both counted, none dropped
    assert dd.counts[0] >= 1  # clamped-low landed in first bin
    assert dd.counts[-1] >= 1  # clamped-high landed in last bin


@pytest.mark.parametrize(
    "kind",
    [
        DistributionKind.DORMANCY_DAYS,
        DistributionKind.AOV_GAP,
        DistributionKind.REORDER_GAP_DAYS,
        DistributionKind.DISCOUNT_FRACTION,
    ],
)
def test_build_helper_each_kind_produces_descriptive_atom(kind):
    edges = mb._DESCRIPTIVE_BIN_EDGES[kind.value]
    # mid-range observations for the kind.
    mid = (edges[0] + edges[-1]) / 2.0
    dd = build_descriptive_distribution(kind, [mid, mid, mid], bin_edges=edges)
    assert dd.kind is kind
    assert dd.suppressed is False
    assert sum(dd.counts) == 3
    assert len(dd.counts) == len(dd.bins) - 1


# ---------------------------------------------------------------------------
# (3) Suppression — empty / absent / integrity-failed
# ---------------------------------------------------------------------------


def test_absent_series_is_typed_suppressed():
    dd = build_descriptive_distribution(DistributionKind.AOV_GAP, None)
    assert dd.suppressed is True
    assert (
        dd.suppression_reason
        is DescriptiveDistributionSuppressionReason.SOURCE_SERIES_ABSENT
    )
    assert dd.bins == [] and dd.counts == []


def test_empty_series_is_typed_suppressed():
    dd = build_descriptive_distribution(DistributionKind.AOV_GAP, [])
    assert dd.suppressed is True
    assert (
        dd.suppression_reason
        is DescriptiveDistributionSuppressionReason.SOURCE_SERIES_EMPTY
    )


def test_non_finite_only_series_is_integrity_failed():
    dd = build_descriptive_distribution(
        DistributionKind.AOV_GAP, [float("nan"), float("inf")]
    )
    assert dd.suppressed is True
    assert (
        dd.suppression_reason
        is DescriptiveDistributionSuppressionReason.INTEGRITY_FAILED
    )


def test_suppressed_invariant_round_trips():
    dd = build_descriptive_distribution(DistributionKind.AOV_GAP, [])
    aud = Audience(descriptive_distribution=dd)
    pc = PlayCard(play_id="aov_lift_via_threshold_bundle", audience=aud)
    er2 = EngineRun.from_dict(EngineRun(recommendations=[pc]).to_dict())
    dd2 = er2.recommendations[0].audience.descriptive_distribution
    assert dd2.suppressed is True
    assert dd2.suppression_reason is not None


# ---------------------------------------------------------------------------
# (4) Marker None pass-through
# ---------------------------------------------------------------------------


def test_marker_none_passes_through():
    dd = build_descriptive_distribution(
        DistributionKind.DISCOUNT_FRACTION,
        [0.6, 0.7],
        marker=None,
        bin_edges=mb._DESCRIPTIVE_BIN_EDGES["DISCOUNT_FRACTION"],
    )
    assert dd.marker is None
    assert dd.suppressed is False  # None marker does NOT suppress the series


# ---------------------------------------------------------------------------
# (5) Builders stash kind + series; producer binds the atom
# ---------------------------------------------------------------------------


def _row(customer_id, days_ago, *, net_sales=50.0, discount_rate=0.0,
         lineitem="Cleanser 50ml"):
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": ANCHOR - pd.Timedelta(days=days_ago),
        "net_sales": float(net_sales),
        "discount_rate": float(discount_rate),
        "lineitem_any": lineitem,
    }


def _make_g(rows):
    return (
        pd.DataFrame(rows)
        .sort_values(["customer_id", "Created at"])
        .reset_index(drop=True)
    )


def test_winback_builder_stashes_dormancy_with_real_marker():
    rows = [_row("anchor", 0)]
    for i in range(600):
        rows.append(_row(f"c{i}", 180))
        rows.append(_row(f"c{i}", 30))  # last order 30d ago, inside 21-45 window
    g = _make_g(rows)
    res = ab.winback_dormant_cohort_candidates(g, {}, {"VERTICAL_MODE": "beauty"})
    assert res.descriptive_kind == "DORMANCY_DAYS"
    assert res.descriptive_series  # non-empty
    assert all(v >= 0 for v in res.descriptive_series)
    assert res.descriptive_marker == 45.0  # dormancy window upper bound (real)


def test_discount_builder_stashes_discount_fraction_marker_none():
    rows = []
    for i in range(40):
        # 2 of 2 orders discounted -> frac 1.0 (>= 0.5 eligible)
        rows.append(_row(f"d{i}", 60, discount_rate=0.2))
        rows.append(_row(f"d{i}", 30, discount_rate=0.2))
    g = _make_g(rows)
    res = ab.discount_dependency_hygiene_candidates(g, {}, {"VERTICAL_MODE": "beauty"})
    assert res.descriptive_kind == "DISCOUNT_FRACTION"
    assert res.descriptive_series
    assert all(0.0 <= v <= 1.0 for v in res.descriptive_series)
    assert res.descriptive_marker is None  # target_discount_share None/TODO(S14)


def test_producer_binds_typed_atom_onto_audience():
    """The full producer seam: builder series -> Audience.descriptive_distribution."""
    rows = [_row("anchor", 0)]
    for i in range(600):
        rows.append(_row(f"c{i}", 180))
        rows.append(_row(f"c{i}", 30))
    g = _make_g(rows)
    res = ab.winback_dormant_cohort_candidates(g, {}, {"VERTICAL_MODE": "beauty"})
    dd = mb._maybe_build_descriptive_distribution(res)
    assert isinstance(dd, DescriptiveDistribution)
    assert dd.kind is DistributionKind.DORMANCY_DAYS
    assert dd.suppressed is False
    assert sum(dd.counts) == res.audience_size  # every cohort member binned
    assert dd.marker == 45.0


def test_producer_returns_none_for_non_distributional_candidate():
    from types import SimpleNamespace

    cand = SimpleNamespace(
        descriptive_kind=None, descriptive_series=None, descriptive_marker=None
    )
    assert mb._maybe_build_descriptive_distribution(cand) is None


def test_full_prior_anchored_card_carries_descriptive_distribution():
    """End-to-end seam: a real winback_dormant_cohort builder result ->
    build_prior_anchored_play_card -> PlayCard.audience.descriptive_distribution."""
    from src.priors_loader import clear_cache

    clear_cache()
    rows = [_row("anchor", 0)]
    for i in range(600):
        rows.append(_row(f"c{i}", 180))
        rows.append(_row(f"c{i}", 30))
    g = _make_g(rows)
    cand = ab.winback_dormant_cohort_candidates(g, {}, {"VERTICAL_MODE": "beauty"})
    assert cand.preliminary_rejection_reason is None
    aligned = {"L28": {"aov": 60.0, "delta": {}, "p": {}, "meta": {}}}
    card = mb.build_prior_anchored_play_card(cand, aligned, vertical="beauty")
    assert card is not None
    dd = card.audience.descriptive_distribution
    assert isinstance(dd, DescriptiveDistribution)
    assert dd.kind is DistributionKind.DORMANCY_DAYS
    assert dd.suppressed is False
    assert dd.marker == 45.0
    assert sum(dd.counts) == card.audience.size


# ---------------------------------------------------------------------------
# (6) from_dict tolerates absence (2.0.0 back-compat)
# ---------------------------------------------------------------------------


def test_from_dict_tolerates_absent_field_2_0_0_backcompat():
    # A pre-2.1.0 audience dict has no descriptive_distribution key.
    legacy_audience = {
        "id": "a",
        "definition": "d",
        "size": 12,
        "fraction_of_base": None,
        "overlap_with": [],
    }
    payload = {
        "schema_version": "2.0.0",
        "recommendations": [
            {"play_id": "winback_dormant_cohort", "audience": legacy_audience}
        ],
    }
    er = EngineRun.from_dict(payload)
    aud = er.recommendations[0].audience
    assert aud is not None
    assert aud.descriptive_distribution is None  # tolerated, defaults to None


def test_from_dict_null_descriptive_distribution_is_none():
    legacy_audience = {"id": "a", "size": 5, "descriptive_distribution": None}
    payload = {"recommendations": [{"play_id": "p", "audience": legacy_audience}]}
    er = EngineRun.from_dict(payload)
    assert er.recommendations[0].audience.descriptive_distribution is None
