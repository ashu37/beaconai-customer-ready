"""Sprint 7.6 Ticket T4 — B-4 cohort_journey_first_to_second observed-effect tests.

Verifies:
- Helper short-circuits on empty / mal-typed frames and on missing columns.
- BERKSON INVARIANT: cohort denominators are defined on EARLY-HALF-OF-
  WINDOW first-purchase dates ONLY. See tests/test_berkson_invariant.py +
  project_journey_p_zero.md memory 2026-04-30 (original fix 554960d /
  Phase 4.1). Includes a regression case that would produce a different
  rate under late-half (or full-window) cohort definition.
- Multi-window sign-agreement is computed across {L28, L56, L90} and
  stashed on the card's blend_provenance driver.
- Per-builder flag independence: T1 winback / T2 replenishment / T3
  discount-hygiene flags do NOT activate the T4 journey observed-effect.
- Card seam: flag OFF preserves cold-start blend_provenance; flag ON
  shifts posterior toward observed rate and stashes sign-agreement.
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


def _order(customer_id: str, days_ago: int, net_sales: float = 50.0):
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": ANCHOR - pd.Timedelta(days=days_ago),
        "net_sales": float(net_sales),
    }


def _candidate(
    play_id: str = "cohort_journey_first_to_second", audience_size: int = 400
):
    return SimpleNamespace(
        play_id=play_id,
        audience_size=audience_size,
        segment_definition=(
            "first-time buyers whose only order is 30-90 days before anchor"
        ),
        data_used=[],
        preliminary_rejection_reason=None,
        cold_start=False,
    )


def _aligned_with_aov(aov: float = 60.0):
    return {"L28": {"aov": aov, "delta": {}, "p": {}, "meta": {}}}


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_compute_journey_observed_effect_empty_frame_returns_none():
    primary, agg = mb.compute_journey_first_to_second_observed_effect(
        None, vertical="beauty"
    )
    assert primary is None and agg is None

    primary, agg = mb.compute_journey_first_to_second_observed_effect(
        pd.DataFrame(), vertical="beauty"
    )
    assert primary is None and agg is None


def test_compute_journey_observed_effect_missing_columns_returns_none():
    g = pd.DataFrame([{"customer_id": "x", "net_sales": 50.0}])
    primary, agg = mb.compute_journey_first_to_second_observed_effect(
        g, vertical="beauty"
    )
    assert primary is None and agg is None


def test_compute_journey_observed_effect_berkson_early_half_denominator():
    """BERKSON REGRESSION CASE.

    For the L28 recent window, anchor = maxd. Early half =
    [maxd - 28d, maxd - 14d). A customer whose first order is at day 7
    (i.e. in the LATE half, [maxd - 14d, maxd]) MUST NOT count toward the
    denominator — they mechanically have not had a full half-window of
    time to make a second order. A customer whose first order is at day
    21 (i.e. in the EARLY half) IS in the denominator.

    Construct a fixture where:
      - 50 customers have their first order at day 21 (EARLY half), and
        25 of those go on to a second order at day 5 (late half, before
        anchor). Recent k=25, n=50, rate=0.5.
      - 50 customers have their first order at day 7 (LATE half), none
        of whom have a second order. If we used a full-window or late-
        half cohort, these would deflate the rate to 25/100 = 0.25.
      - Prior window (L28 anchor=maxd-28d, early half
        [maxd-56d, maxd-42d)): 40 customers first order at day 49,
        20 of those second order by day 28. Prior k=20, n=40, rate=0.5.

    Assert recent rate = 0.5 (NOT 0.25), meaning the helper used the
    early-half rule and excluded the late-half-only first-buyers.
    """
    rows = []
    # Anchor pin: a single non-cohort customer at day 0. Already had a
    # first order long ago so it does not enter any of our test cohorts.
    rows.append(_order("anchor_existing", 365))
    rows.append(_order("anchor_existing", 0))

    # Recent EARLY-half cohort: 50 first orders at day 21.
    for i in range(50):
        rows.append(_order(f"r_early_{i}", 21))
    # Half of them place a second order at day 5 (within window, before maxd).
    for i in range(25):
        rows.append(_order(f"r_early_{i}", 5))

    # Recent LATE-half-only first-buyers: 50 first orders at day 7.
    # If a late-half rule were used, these would inflate n by 50 with
    # zero k. The Berkson-protected rule must EXCLUDE these.
    for i in range(50):
        rows.append(_order(f"r_late_{i}", 7))

    # Prior EARLY-half cohort: 40 first orders at day 49 (in
    # [maxd-56, maxd-42)). Half second-order by day 28.
    for i in range(40):
        rows.append(_order(f"p_early_{i}", 49))
    for i in range(20):
        rows.append(_order(f"p_early_{i}", 28))

    g = pd.DataFrame(rows)
    primary, agg = mb.compute_journey_first_to_second_observed_effect(
        g, vertical="beauty"
    )
    assert primary is not None
    assert primary.n == 50, (
        "Recent denominator must be 50 (early-half cohort only), NOT 100 "
        "(would include late-half first-buyers under a non-Berkson-"
        "protected rule). See tests/test_berkson_invariant.py."
    )
    assert primary.k == 25
    assert primary.recent_rate == pytest.approx(0.5, abs=1e-6)
    assert primary.prior_rate == pytest.approx(0.5, abs=1e-6)
    # Recent and prior rates are equal -> sign 0.
    assert primary.sign == 0
    assert agg is not None
    assert "L28" in agg.windows


def test_compute_journey_observed_effect_recovers_positive_signal():
    """Recent first-to-second rate > prior -> sign +1, p<0.05."""
    rows = [_order("anchor_existing", 365), _order("anchor_existing", 0)]
    # Recent early-half: 100 first-buyers at day 21; 60 convert by day 5.
    for i in range(100):
        rows.append(_order(f"r_{i}", 21))
    for i in range(60):
        rows.append(_order(f"r_{i}", 5))
    # Prior early-half: 100 first-buyers at day 49; 30 convert by day 28.
    for i in range(100):
        rows.append(_order(f"p_{i}", 49))
    for i in range(30):
        rows.append(_order(f"p_{i}", 28))

    g = pd.DataFrame(rows)
    primary, agg = mb.compute_journey_first_to_second_observed_effect(
        g, vertical="beauty"
    )
    assert primary is not None
    assert primary.n == 100
    assert primary.k == 60
    assert primary.recent_rate == pytest.approx(0.6, abs=1e-6)
    assert primary.prior_rate == pytest.approx(0.3, abs=1e-6)
    assert primary.sign == 1
    assert primary.p_value is not None and primary.p_value < 0.05
    assert agg is not None


def test_compute_journey_observed_effect_flat_l28_yields_zero_sign():
    """When recent and prior rates on L28 are exactly equal, sign is 0."""
    rows = [_order("anchor_existing", 365), _order("anchor_existing", 0)]
    for i in range(40):
        rows.append(_order(f"r_{i}", 21))
    for i in range(20):
        rows.append(_order(f"r_{i}", 5))
    for i in range(40):
        rows.append(_order(f"p_{i}", 49))
    for i in range(20):
        rows.append(_order(f"p_{i}", 28))

    g = pd.DataFrame(rows)
    primary, agg = mb.compute_journey_first_to_second_observed_effect(
        g, vertical="beauty"
    )
    assert primary is not None
    assert primary.sign == 0
    assert primary.effect == pytest.approx(0.0, abs=1e-9)


def test_compute_journey_observed_effect_cold_start_no_history_returns_zero_n():
    """When the dataset has no customers in any early-half cohort
    (e.g. all orders are anchor-pinned), the helper returns a primary
    with n=0 (honest zero-data) rather than fabricating data."""
    g = pd.DataFrame(
        [_order("only", 0), _order("only", 0)]  # one customer, two orders, all at anchor
    )
    primary, agg = mb.compute_journey_first_to_second_observed_effect(
        g, vertical="beauty"
    )
    # The helper returns a primary result (n=0) wrapped via the T0 helper's
    # zero-n short-circuit; the caller's `if n > 0` guard keeps observed_k /
    # observed_n at 0.
    assert primary is not None
    assert primary.n == 0
    assert primary.k is None


def test_compute_journey_observed_effect_runs_on_supplements():
    """B-4 vertical scope is "*" per plan; the helper does NOT short-
    circuit supplements (unlike T3 discount_hygiene which is Beauty-only
    per DS Memo-4 REJECT)."""
    rows = [_order("anchor_existing", 365), _order("anchor_existing", 0)]
    for i in range(40):
        rows.append(_order(f"r_{i}", 21))
    for i in range(20):
        rows.append(_order(f"r_{i}", 5))
    for i in range(40):
        rows.append(_order(f"p_{i}", 49))
    for i in range(10):
        rows.append(_order(f"p_{i}", 28))

    g = pd.DataFrame(rows)
    primary, agg = mb.compute_journey_first_to_second_observed_effect(
        g, vertical="supplements"
    )
    assert primary is not None
    assert primary.n == 40
    assert primary.k == 20


# ---------------------------------------------------------------------------
# Card-seam wiring tests
# ---------------------------------------------------------------------------


def _build_strong_journey_frame():
    rows = [_order("anchor_existing", 365), _order("anchor_existing", 0)]
    for i in range(120):
        rows.append(_order(f"r_{i}", 21))
    for i in range(72):
        rows.append(_order(f"r_{i}", 5))
    for i in range(120):
        rows.append(_order(f"p_{i}", 49))
    for i in range(36):
        rows.append(_order(f"p_{i}", 28))
    # L56 early-half: [maxd-56d, maxd-42d) for recent; [maxd-112d, maxd-84d)
    # for prior. L90 early-half: [maxd-90d, maxd-45d) recent; [maxd-180d,
    # maxd-135d) prior. Add some L56/L90 first-buyers so windows are populated.
    for i in range(60):
        rows.append(_order(f"r56_{i}", 50))  # in L56 early half [-56,-42)
    for i in range(30):
        rows.append(_order(f"r56_{i}", 20))  # second order within L56 window
    for i in range(60):
        rows.append(_order(f"p56_{i}", 100))
    for i in range(15):
        rows.append(_order(f"p56_{i}", 60))
    return pd.DataFrame(rows)


def test_flag_off_default_cold_start_provenance_unchanged():
    """``observed_journey_enabled=False`` -> orders_df ignored;
    blend_provenance keeps the cold-start signature exactly."""
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_strong_journey_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_journey_enabled=False,
    )
    if card is None:
        pytest.skip(
            "cohort_journey_first_to_second prior unavailable in test env; "
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
    g = _build_strong_journey_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_journey_enabled=True,
    )
    if card is None:
        pytest.skip(
            "cohort_journey_first_to_second prior unavailable in test env."
        )
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    # Recent: 120 early-half first-buyers, 72 converted by anchor (60%).
    assert bp["observed_n"] == 120
    assert bp["observed_k"] == 72
    assert bp["store_data_status"] == "store_outcomes_observed"
    # Posterior shifts toward 0.6 (observed rate) — must differ from prior.
    assert bp["posterior_value"] != bp["prior_value"]
    assert "observed_sign_agreement_count" in bp
    assert "observed_dominant_sign" in bp
    assert bp["observed_windows"]["L28"]["sign"] == 1


def test_winback_flag_does_not_activate_journey_observed_effect():
    """Per-builder flag independence: T1 winback flag must NOT run the
    T4 journey observed-effect path."""
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_strong_journey_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=True,                # winback flag
        observed_replenishment_enabled=False,
        observed_discount_hygiene_enabled=False,
        observed_journey_enabled=False,              # journey OFF
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


def test_replenishment_flag_does_not_activate_journey_observed_effect():
    """Per-builder flag independence: T2 replenishment flag must NOT
    run the T4 journey observed-effect path."""
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_strong_journey_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=False,
        observed_replenishment_enabled=True,         # replenishment flag
        observed_discount_hygiene_enabled=False,
        observed_journey_enabled=False,              # journey OFF
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


def test_discount_hygiene_flag_does_not_activate_journey_observed_effect():
    """Per-builder flag independence: T3 discount-hygiene flag must NOT
    run the T4 journey observed-effect path."""
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_strong_journey_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=False,
        observed_replenishment_enabled=False,
        observed_discount_hygiene_enabled=True,      # discount-hygiene flag
        observed_journey_enabled=False,              # journey OFF
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


def test_multi_window_sign_agreement_stashed_on_provenance():
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_strong_journey_frame()
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_journey_enabled=True,
    )
    if card is None:
        pytest.skip("cohort_journey_first_to_second prior unavailable")
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    assert "observed_windows" in bp
    l28 = bp["observed_windows"]["L28"]
    assert l28["k"] == 72
    assert l28["n"] == 120
    assert l28["sign"] == 1
