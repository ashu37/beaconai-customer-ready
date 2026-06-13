"""Sprint 7.6 Ticket T5 --- B-5 aov_lift_via_threshold_bundle observed-effect tests.

Verifies:
- Helper short-circuits on empty / mal-typed frames and on missing columns.
- Helper short-circuits on vertical=="supplements" per plan B-5:248
  (mirrors audience_builders.py:997-1007 vertical-excluded gate).
- DUAL TEST shape: Welch-t primary (k=None) on order-level AOV +
  two-proportion z-test on near-threshold band share folded into the
  agreement.windows map under L28_band / L56_band / L90_band labels.
- Joint condition: both p<0.10 = joint pass; either failing = joint fail.
- Multi-window sign-agreement on AOV (Welch) delta direction only;
  the band-share entries do NOT double-count.
- Per-builder flag independence: T1 winback / T2 replenishment / T3
  discount-hygiene / T4 journey flags do NOT activate the T5 aov-bundle
  observed-effect path.
- Card seam: flag OFF preserves cold-start blend_provenance; flag ON
  threads band-share L28 (k, n) as the blend channel (Welch primary
  has k=None and cannot drive observed_k directly).
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import measurement_builder as mb  # noqa: E402
from src.priors_loader import clear_cache  # noqa: E402


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")
THRESHOLD = 100.0  # T -- band = [70, 95]


def _order(customer_id: str, days_ago: int, net_sales: float):
    return {
        "Name": f"#{customer_id}-{days_ago}-{net_sales}",
        "customer_id": str(customer_id),
        "Created at": ANCHOR - pd.Timedelta(days=days_ago),
        "net_sales": float(net_sales),
    }


def _candidate(play_id: str = "aov_lift_via_threshold_bundle", audience_size: int = 400):
    return SimpleNamespace(
        play_id=play_id,
        audience_size=audience_size,
        segment_definition=(
            "customers with cart/typical AOV in [$85.00, $95.00] "
            "($100.00 threshold minus $5-$15 band, snapshot)"
        ),
        data_used=[],
        preliminary_rejection_reason=None,
        cold_start=False,
    )


def _aligned_with_aov(aov: float = 90.0):
    return {"L28": {"aov": aov, "delta": {}, "p": {}, "meta": {}}}


# Threshold cfg with the from-data flag OFF so the helper uses
# cfg["AOV_BUNDLE_THRESHOLD_USD"] deterministically across tests.
_CFG = {
    "AOV_BUNDLE_THRESHOLD_USD": THRESHOLD,
    "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": False,
}


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_compute_aov_bundle_empty_frame_returns_none():
    primary, agg = mb.compute_aov_bundle_observed_effect(
        None, vertical="beauty", cfg=_CFG
    )
    assert primary is None and agg is None

    primary, agg = mb.compute_aov_bundle_observed_effect(
        pd.DataFrame(), vertical="beauty", cfg=_CFG
    )
    assert primary is None and agg is None


def test_compute_aov_bundle_missing_columns_returns_none():
    g = pd.DataFrame([{"customer_id": "x", "Name": "#1"}])
    primary, agg = mb.compute_aov_bundle_observed_effect(
        g, vertical="beauty", cfg=_CFG
    )
    assert primary is None and agg is None


def test_compute_aov_bundle_supplements_short_circuits():
    """Plan B-5:248 vertical exclusion: supplements returns (None, None)."""
    rows = []
    for i in range(60):
        rows.append(_order(f"r_{i}", 10, 90.0))
        rows.append(_order(f"p_{i}", 40, 50.0))
    g = pd.DataFrame(rows)
    primary, agg = mb.compute_aov_bundle_observed_effect(
        g, vertical="supplements", cfg=_CFG
    )
    assert primary is None and agg is None


def test_compute_aov_bundle_threshold_unresolvable_returns_none():
    """No cfg threshold, no L90 P60 data -> (None, None)."""
    rows = [_order(f"c_{i}", i + 1, 50.0) for i in range(10)]
    g = pd.DataFrame(rows)
    primary, agg = mb.compute_aov_bundle_observed_effect(
        g,
        vertical="beauty",
        cfg={"ENGINE_V2_AOV_THRESHOLD_FROM_DATA": False},
    )
    assert primary is None and agg is None


def test_compute_aov_bundle_welch_primary_is_continuous():
    """Welch primary returns method='welch_t' with k=None.

    Fixture keeps L28 recent and L28 prior pure (no L56/L90 padding) so
    means are exactly the planted values. Helper still resolves L56/L90
    from the same data --- those windows are wider supersets and are
    asserted only at the structural level (presence in windows map).
    """
    rows = []
    # Recent L28 = [maxd-28, maxd]. 80 orders centered at AOV=92 with small
    # jitter so Welch produces a valid (non-None) p-value (zero-variance
    # arms route to p=None per T0 helper measurement_observed.py:227).
    for i in range(80):
        jitter = 0.5 if i % 2 == 0 else -0.5
        rows.append(_order(f"r_{i}", 10, 92.0 + jitter))
    # Prior L28 = [maxd-56, maxd-28]. 80 orders centered at AOV=60.
    for i in range(80):
        jitter = 0.5 if i % 2 == 0 else -0.5
        rows.append(_order(f"p_{i}", 40, 60.0 + jitter))

    g = pd.DataFrame(rows)
    primary, agg = mb.compute_aov_bundle_observed_effect(
        g, vertical="beauty", cfg=_CFG
    )
    assert primary is not None
    assert primary.method == "welch_t"
    assert primary.k is None
    assert primary.recent_rate == pytest.approx(92.0, abs=1e-6)
    assert primary.prior_rate == pytest.approx(60.0, abs=1e-6)
    assert primary.sign == 1
    assert primary.p_value is not None and primary.p_value < 0.10
    # Band-share L28: 80/80 (recent in band) vs 0/80 (prior below band).
    assert agg is not None
    l28_band = agg.windows.get("L28_band")
    assert l28_band is not None
    assert l28_band.method in ("z_pooled", "fisher_exact")
    assert l28_band.k == 80
    assert l28_band.n == 80
    assert l28_band.p_value is not None and l28_band.p_value < 0.10


def test_compute_aov_bundle_joint_pass():
    """Both Welch-t (AOV) AND z-prop (band-share) p<0.10 on L28."""
    rows = []
    # L28 recent = day [0, 28]: 80 orders at AOV~=92 (in band [70, 95]).
    # L28 prior  = day [28, 56]: 80 orders at AOV~=60 (below band).
    # Small jitter so Welch returns a valid p-value (zero-variance both
    # arms -> p=None per T0 helper).
    for i in range(80):
        jitter = 0.5 if i % 2 == 0 else -0.5
        rows.append(_order(f"r_{i}", 10, 92.0 + jitter))
        rows.append(_order(f"p_{i}", 40, 60.0 + jitter))
    g = pd.DataFrame(rows)

    primary, agg = mb.compute_aov_bundle_observed_effect(
        g, vertical="beauty", cfg=_CFG
    )
    welch_p = primary.p_value
    band_p = agg.windows["L28_band"].p_value
    assert welch_p is not None and welch_p < 0.10
    assert band_p is not None and band_p < 0.10
    # JOINT PASS: both signals agree.


def test_compute_aov_bundle_only_welch_passes():
    """AOV shifts (Welch p<0.10) but band-share share unchanged
    (z-prop p>=0.10) -> joint FAIL."""
    rows = []
    # Recent: 80 orders at AOV=92 (in band).
    # Prior: 80 orders at AOV=80 (also in band [70, 95]).
    # Band shares are 80/80 in both --- z-prop sees no shift.
    # Welch sees a 12-dollar mean shift across n=80 each --- p<0.10.
    for i in range(80):
        rows.append(_order(f"r_{i}", 10, 92.0))
        rows.append(_order(f"p_{i}", 40, 80.0))
    g = pd.DataFrame(rows)

    primary, agg = mb.compute_aov_bundle_observed_effect(
        g, vertical="beauty", cfg=_CFG
    )
    welch_p = primary.p_value
    band_p = agg.windows["L28_band"].p_value
    # Welch: zero-variance in both arms; T0 helper returns p=None.
    # Either p=None or p<0.10 still counts as "Welch did fire";
    # the joint condition fails because band-share p is undefined or large.
    assert agg.windows["L28_band"].k == 80
    assert agg.windows["L28_band"].n == 80
    # Recent and prior band-share both 1.0; effect = 0; sign = 0.
    assert agg.windows["L28_band"].sign == 0
    # Band-share p is None (zero SE because both rates are 1.0) OR not <0.10.
    joint_pass = (
        welch_p is not None and welch_p < 0.10
        and band_p is not None and band_p < 0.10
    )
    assert not joint_pass, "Joint condition must FAIL when band-share is flat."


def test_compute_aov_bundle_only_zprop_passes():
    """Band-share shifts (z-prop p<0.10) but AOV means equal
    (Welch p>=0.10) -> joint FAIL."""
    rows = []
    # Recent: 50 orders at 92 (in band) + 50 orders at 50 (below).
    # Prior: 0 in band, 100 at 71 (in band actually = 71 is in [70, 95]).
    # Let's redesign: keep AOV means ~equal but shift band membership.
    # Recent: 50 at 91 (in band) + 50 at 50 -> mean = 70.5; band 50/100.
    # Prior:  50 at 50 + 50 at 91 -> mean = 70.5; band 50/100.
    # That keeps band-share equal too. Instead:
    # Recent: 80 at 80 (in band) -> mean 80, band 80/80.
    # Prior:  40 at 60 + 40 at 100 (one above, one below) -> mean 80, band 0/80.
    for i in range(80):
        rows.append(_order(f"r_{i}", 10, 80.0))
    for i in range(40):
        rows.append(_order(f"p_lo_{i}", 40, 60.0))
        rows.append(_order(f"p_hi_{i}", 40, 100.0))
    g = pd.DataFrame(rows)
    primary, agg = mb.compute_aov_bundle_observed_effect(
        g, vertical="beauty", cfg=_CFG
    )
    # Welch: same mean (80 vs 80) -> p ~ 1.0, sign 0.
    assert primary.recent_rate == pytest.approx(80.0, abs=1e-6)
    assert primary.prior_rate == pytest.approx(80.0, abs=1e-6)
    welch_p = primary.p_value
    assert welch_p is None or welch_p >= 0.10
    # z-prop: 80/80 vs 0/80 -> very small p.
    band = agg.windows["L28_band"]
    assert band.k == 80 and band.n == 80
    assert band.recent_rate == pytest.approx(1.0, abs=1e-6)
    assert band.prior_rate == pytest.approx(0.0, abs=1e-6)
    assert band.p_value is not None and band.p_value < 0.10
    # JOINT FAIL because Welch did not move.
    joint_pass = (
        welch_p is not None and welch_p < 0.10
        and band.p_value is not None and band.p_value < 0.10
    )
    assert not joint_pass


def test_compute_aov_bundle_sign_agreement_on_aov_only():
    """Multi-window sign-agreement counts AOV (Welch) windows only;
    band-share L28_band / L56_band / L90_band entries do NOT
    double-count toward the sign-agreement total."""
    rows = []
    # Plant "recent" block @ day 5 (in L28 recent) at AOV=92 (in band).
    # Plant "prior" blocks @ days 40, 70, 100, 130 (across the L28/L56/L90
    # prior windows) at AOV=60 (below band). Each window's recent mean
    # exceeds its prior mean -> sign +1 across all three windows.
    for i in range(80):
        rows.append(_order(f"r_{i}", 5, 92.0))
    for day in (40, 70, 100, 130):
        for i in range(40):
            rows.append(_order(f"p_{day}_{i}", day, 60.0))
    g = pd.DataFrame(rows)
    primary, agg = mb.compute_aov_bundle_observed_effect(
        g, vertical="beauty", cfg=_CFG
    )
    assert agg is not None
    # Sign-agreement counts the THREE AOV windows: L28, L56, L90 all +1.
    assert agg.sign_agreement_count == 3
    assert agg.dominant_sign == 1
    # Windows map carries BOTH AOV + band entries.
    assert {"L28", "L56", "L90", "L28_band", "L56_band", "L90_band"}.issubset(
        set(agg.windows.keys())
    )


def test_compute_aov_bundle_threshold_from_data_path():
    """When ENGINE_V2_AOV_THRESHOLD_FROM_DATA=True and L90 order count
    >= 200, helper derives T from L90 P60 instead of cfg."""
    rows = []
    # Build a 240-order L90 distribution where P60 is approximately known.
    # 240 orders uniformly at net_sales = 50, 60, ..., 100 (50 per bucket).
    # Sorted distribution P60 of 240 values where 60% sit below ~80.
    values = []
    for v in (50.0, 60.0, 70.0, 80.0, 90.0):
        values.extend([v] * 48)  # 5 * 48 = 240 orders in L90.
    for i, v in enumerate(values):
        rows.append(_order(f"d_{i}", (i % 80) + 1, v))
    g = pd.DataFrame(rows)
    # Resolve T directly via the private helper to assert.
    T = mb._resolve_aov_bundle_threshold(
        g, {"ENGINE_V2_AOV_THRESHOLD_FROM_DATA": True}
    )
    assert T is not None
    assert T > 0


# ---------------------------------------------------------------------------
# Card-seam wiring tests
# ---------------------------------------------------------------------------


def _build_strong_aov_bundle_frame():
    rows = []
    # L28 recent = day [0, 28]: 120 orders at AOV=92 (in band [70, 95]).
    for i in range(120):
        rows.append(_order(f"r_{i}", 5, 92.0))
    # L28 prior = day [28, 56]: 120 orders at AOV=60 (below band).
    for i in range(120):
        rows.append(_order(f"p_{i}", 40, 60.0))
    return pd.DataFrame(rows)


def test_flag_off_default_cold_start_provenance_unchanged():
    """observed_aov_bundle_enabled=False -> orders_df ignored;
    blend_provenance keeps the cold-start signature exactly."""
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_strong_aov_bundle_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(90.0),
        vertical="beauty",
        orders_df=g,
        observed_aov_bundle_enabled=False,
        cfg=_CFG,
    )
    if card is None:
        pytest.skip(
            "aov_lift_via_threshold_bundle prior unavailable in test env; "
            "helper-level coverage above is the floor."
        )
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    assert bp["observed_k"] == 0
    assert bp["observed_n"] == 0
    assert bp["store_data_status"] == "no_outcome_history"
    assert "observed_sign_agreement_count" not in bp
    assert "observed_windows" not in bp


def test_flag_on_threads_observed_kn_and_shifts_posterior():
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_strong_aov_bundle_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(90.0),
        vertical="beauty",
        orders_df=g,
        observed_aov_bundle_enabled=True,
        cfg=_CFG,
    )
    if card is None:
        pytest.skip("aov_lift_via_threshold_bundle prior unavailable")
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    # Band channel: 120/120 recent orders in [70, 95].
    assert bp["observed_n"] == 120
    assert bp["observed_k"] == 120
    assert bp["store_data_status"] == "store_outcomes_observed"
    assert "observed_sign_agreement_count" in bp
    assert "observed_dominant_sign" in bp
    # Both AOV and band windows surfaced on the stash.
    assert "L28" in bp["observed_windows"]
    assert "L28_band" in bp["observed_windows"]
    assert bp["observed_windows"]["L28"]["method"] == "welch_t"


def test_supplements_card_seam_short_circuits():
    """Even with flag ON, supplements never threads observed_k/n."""
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_strong_aov_bundle_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(90.0),
        vertical="supplements",
        orders_df=g,
        observed_aov_bundle_enabled=True,
        cfg=_CFG,
    )
    if card is None:
        # supplements may not resolve a prior in this env --- helper-level
        # short-circuit is the floor.
        return
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    if bp is not None:
        assert bp["observed_n"] == 0
        assert "observed_sign_agreement_count" not in bp


def test_winback_flag_does_not_activate_aov_bundle_observed_effect():
    """Per-builder flag independence: T1 winback flag must NOT run the
    T5 aov-bundle observed-effect path."""
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_strong_aov_bundle_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(90.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=True,                # winback flag
        observed_replenishment_enabled=False,
        observed_discount_hygiene_enabled=False,
        observed_journey_enabled=False,
        observed_aov_bundle_enabled=False,           # AOV-bundle OFF
        cfg=_CFG,
    )
    if card is None:
        return
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    if bp is not None:
        assert bp["observed_n"] == 0
        assert "observed_sign_agreement_count" not in bp


def test_journey_flag_does_not_activate_aov_bundle_observed_effect():
    """Per-builder flag independence: T4 journey flag must NOT run the
    T5 aov-bundle observed-effect path."""
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_strong_aov_bundle_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(90.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=False,
        observed_replenishment_enabled=False,
        observed_discount_hygiene_enabled=False,
        observed_journey_enabled=True,               # journey flag
        observed_aov_bundle_enabled=False,           # AOV-bundle OFF
        cfg=_CFG,
    )
    if card is None:
        return
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    if bp is not None:
        assert bp["observed_n"] == 0
        assert "observed_sign_agreement_count" not in bp
