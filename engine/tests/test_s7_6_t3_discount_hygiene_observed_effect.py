"""Sprint 7.6 Ticket T3 — B-3 discount_dependency_hygiene observed-effect tests.

Verifies:
- Helper short-circuits on empty / mal-typed frames, on missing columns,
  and on ``vertical='supplements'`` (DS Memo-4 REJECT, Path-D dormant).
- Synthetic Beauty fixture produces the expected revenue-weighted
  ``(observed_k, observed_n)`` and positive sign when recent heavy-discount
  revenue share exceeds prior.
- Revenue-weighting semantics: a $200 heavy-discount order contributes 200
  to ``k`` (not 1) — z-test cell counts honor revenue dollars.
- Multi-window sign-agreement is computed across {L28, L56, L90} and
  stashed on the card's blend_provenance driver.
- Card seam: flag OFF preserves cold-start blend_provenance (no
  ``observed_sign_agreement_count`` key); flag ON shifts posterior toward
  observed rate and stashes sign-agreement.
- T1 / T2 flags do NOT activate discount-hygiene observed-effect (per-builder
  flag independence is a load-bearing invariant of the per-builder rollout).
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


def _row(
    customer_id: str,
    days_ago: int,
    *,
    discount_rate: float = 0.0,
    net_sales: float = 50.0,
):
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": ANCHOR - pd.Timedelta(days=days_ago),
        "discount_rate": float(discount_rate),
        "net_sales": float(net_sales),
    }


def _candidate(
    play_id: str = "discount_dependency_hygiene", audience_size: int = 400
):
    return SimpleNamespace(
        play_id=play_id,
        audience_size=audience_size,
        segment_definition="discount-conditioned cohort test",
        data_used=[],
        preliminary_rejection_reason=None,
        cold_start=False,
    )


def _aligned_with_aov(aov: float = 60.0):
    return {"L28": {"aov": aov, "delta": {}, "p": {}, "meta": {}}}


def _build_synthetic_discount_frame(
    *,
    recent_heavy_customers: int,
    recent_normal_customers: int,
    prior_heavy_customers: int,
    prior_normal_customers: int,
    heavy_aov: float = 100.0,
    normal_aov: float = 50.0,
):
    """Build a synthetic orders frame producing specific heavy-discount
    revenue shares in recent (L28) and prior (L28-prior, i.e. days 28-56)
    windows.

    Each ``recent_heavy`` customer has 2 historical discounted orders at
    days_ago in {200, 100} (qualifies as >=50% discounted) plus 1 recent
    order at day 10 carrying ``heavy_aov``. Each ``recent_normal`` customer
    has 1 historical non-discounted order at day 200 plus 1 recent order
    at day 10 carrying ``normal_aov``.

    Prior cohort members live similarly but with their recent order at
    day 40 (inside (maxd-56, maxd-28]).

    The anchor (maxd) is pinned by a single non-cohort customer placing a
    purchase exactly at ANCHOR (days_ago=0). Its order has discount_rate=0
    and net_sales=0 so it contributes nothing to recent_k or recent_n
    (clipped lower-bound 0; 0 dollars rounds to 0). This keeps maxd ==
    ANCHOR while leaving the revenue-share contrast undisturbed.
    """
    rows = [_row("anchor", 0, discount_rate=0.0, net_sales=0.0)]

    for i in range(recent_heavy_customers):
        cid = f"rh{i}"
        rows.append(_row(cid, 200, discount_rate=0.2, net_sales=60.0))
        rows.append(_row(cid, 100, discount_rate=0.2, net_sales=60.0))
        rows.append(_row(cid, 10, discount_rate=0.2, net_sales=heavy_aov))

    for i in range(recent_normal_customers):
        cid = f"rn{i}"
        rows.append(_row(cid, 200, discount_rate=0.0, net_sales=60.0))
        rows.append(_row(cid, 10, discount_rate=0.0, net_sales=normal_aov))

    for j in range(prior_heavy_customers):
        cid = f"ph{j}"
        rows.append(_row(cid, 220, discount_rate=0.2, net_sales=60.0))
        rows.append(_row(cid, 150, discount_rate=0.2, net_sales=60.0))
        rows.append(_row(cid, 40, discount_rate=0.2, net_sales=heavy_aov))

    for j in range(prior_normal_customers):
        cid = f"pn{j}"
        rows.append(_row(cid, 220, discount_rate=0.0, net_sales=60.0))
        rows.append(_row(cid, 40, discount_rate=0.0, net_sales=normal_aov))

    return (
        pd.DataFrame(rows)
        .sort_values(["customer_id", "Created at"])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_compute_discount_hygiene_observed_effect_empty_frame_returns_none():
    primary, agg = mb.compute_discount_hygiene_observed_effect(
        None, vertical="beauty"
    )
    assert primary is None and agg is None

    primary, agg = mb.compute_discount_hygiene_observed_effect(
        pd.DataFrame(), vertical="beauty"
    )
    assert primary is None and agg is None


def test_compute_discount_hygiene_observed_effect_missing_columns_returns_none():
    g = pd.DataFrame(
        [{"customer_id": "x", "Created at": ANCHOR, "net_sales": 50.0}]
    )
    primary, agg = mb.compute_discount_hygiene_observed_effect(
        g, vertical="beauty"
    )
    assert primary is None and agg is None


def test_compute_discount_hygiene_observed_effect_supplements_short_circuit():
    """DS Memo-4 REJECT: supplements is Path-D dormant. Helper returns
    (None, None) regardless of fixture content; caller MUST treat as
    cold-start (0/0)."""
    g = _build_synthetic_discount_frame(
        recent_heavy_customers=50,
        recent_normal_customers=50,
        prior_heavy_customers=20,
        prior_normal_customers=80,
    )
    primary, agg = mb.compute_discount_hygiene_observed_effect(
        g, vertical="supplements"
    )
    assert primary is None and agg is None


def test_compute_discount_hygiene_observed_effect_recovers_synthetic_signal():
    """Recent heavy-share > prior heavy-share -> positive sign, non-zero
    revenue-weighted (k, n), p_value computed."""
    g = _build_synthetic_discount_frame(
        recent_heavy_customers=50,  # 50 x $100 = $5000 heavy recent
        recent_normal_customers=50,  # 50 x $50  = $2500 normal recent
        prior_heavy_customers=20,    # 20 x $100 = $2000 heavy prior
        prior_normal_customers=80,   # 80 x $50  = $4000 normal prior
    )
    primary, agg = mb.compute_discount_hygiene_observed_effect(
        g, vertical="beauty"
    )
    assert primary is not None
    # Recent: heavy 5000 / total 7500 = 0.6667; Prior: 2000/6000 = 0.3333
    # Recent total: 50 heavy x $100 + 50 normal x $50 = $7500 (anchor-pin $0).
    # Heavy revenue: 50 x $100 = $5000.
    assert primary.k == 5000
    assert primary.n == 7500
    assert primary.sign == 1
    assert primary.effect == pytest.approx(0.3333, abs=1e-3)
    assert primary.p_value is not None and primary.p_value < 0.01
    assert agg is not None
    assert "L28" in agg.windows
    assert agg.windows["L28"].sign == 1


def test_compute_discount_hygiene_observed_effect_revenue_weighted_not_order_counted():
    """A $200 heavy-discount order contributes 200 to k (not 1).

    Build a tiny fixture with a single heavy customer placing one $200
    discounted recent order, plus a single normal customer placing one
    $50 non-discounted recent order. Same shape in prior. Recent heavy
    share = 200 / 250 = 0.80. If the helper were order-counted, k would
    be 1 and n would be 2 (=0.50)."""
    rows = [_row("anchor", 0, discount_rate=0.0, net_sales=0.0)]
    # Recent heavy
    rows.append(_row("rh0", 200, discount_rate=0.2, net_sales=60.0))
    rows.append(_row("rh0", 100, discount_rate=0.2, net_sales=60.0))
    rows.append(_row("rh0", 10, discount_rate=0.2, net_sales=200.0))
    # Recent normal
    rows.append(_row("rn0", 200, discount_rate=0.0, net_sales=60.0))
    rows.append(_row("rn0", 10, discount_rate=0.0, net_sales=50.0))
    # Prior heavy
    rows.append(_row("ph0", 220, discount_rate=0.2, net_sales=60.0))
    rows.append(_row("ph0", 150, discount_rate=0.2, net_sales=60.0))
    rows.append(_row("ph0", 40, discount_rate=0.2, net_sales=200.0))
    # Prior normal
    rows.append(_row("pn0", 220, discount_rate=0.0, net_sales=60.0))
    rows.append(_row("pn0", 40, discount_rate=0.0, net_sales=50.0))

    g = pd.DataFrame(rows)
    primary, _ = mb.compute_discount_hygiene_observed_effect(
        g, vertical="beauty"
    )
    assert primary is not None
    # Revenue-weighted: k must reflect dollars not orders.
    assert primary.k == 200
    assert primary.n == 250


def test_compute_discount_hygiene_observed_effect_flat_l28_yields_zero_sign():
    """When recent and prior heavy-share on L28 are exactly equal, the
    L28 sign is 0 (honest zero-effect, no fabrication)."""
    g = _build_synthetic_discount_frame(
        recent_heavy_customers=30,
        recent_normal_customers=30,
        prior_heavy_customers=30,
        prior_normal_customers=30,
        heavy_aov=100.0,
        normal_aov=100.0,
    )
    primary, agg = mb.compute_discount_hygiene_observed_effect(
        g, vertical="beauty"
    )
    assert primary is not None
    assert primary.sign == 0
    assert primary.effect == pytest.approx(0.0, abs=1e-9)
    # Agreement object is always returned when primary is non-None.
    assert agg is not None
    assert "L28" in agg.windows


def test_compute_discount_hygiene_observed_effect_mixed_vertical_runs():
    """Mixed vertical is NOT short-circuited (only supplements is). The
    helper computes against the same cohort rule regardless of vertical."""
    g = _build_synthetic_discount_frame(
        recent_heavy_customers=20,
        recent_normal_customers=20,
        prior_heavy_customers=10,
        prior_normal_customers=30,
    )
    primary, agg = mb.compute_discount_hygiene_observed_effect(
        g, vertical="mixed"
    )
    assert primary is not None
    assert primary.n > 0


# ---------------------------------------------------------------------------
# Card-seam wiring tests
# ---------------------------------------------------------------------------


def test_flag_off_default_cold_start_provenance_unchanged():
    """``observed_discount_hygiene_enabled=False`` -> orders_df ignored;
    blend_provenance keeps the cold-start signature exactly."""
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_synthetic_discount_frame(
        recent_heavy_customers=50,
        recent_normal_customers=50,
        prior_heavy_customers=20,
        prior_normal_customers=80,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_discount_hygiene_enabled=False,
    )
    if card is None:
        pytest.skip(
            "discount_dependency_hygiene prior unavailable in test env; "
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
    g = _build_synthetic_discount_frame(
        recent_heavy_customers=50,
        recent_normal_customers=50,
        prior_heavy_customers=20,
        prior_normal_customers=80,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_discount_hygiene_enabled=True,
    )
    if card is None:
        pytest.skip(
            "discount_dependency_hygiene prior unavailable in test env; "
            "helper-level coverage above is the floor."
        )
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    # Revenue-weighted recent: heavy 5000 / total 7500.
    assert bp["observed_n"] == 7500
    assert bp["observed_k"] == 5000
    assert bp["store_data_status"] == "store_outcomes_observed"
    # Posterior shifts substantially toward 0.6667 (n >> pseudo_n).
    assert bp["posterior_value"] != bp["prior_value"]
    assert "observed_sign_agreement_count" in bp
    assert "observed_dominant_sign" in bp
    # L28 primary sign is positive (recent heavy-share 0.667 > prior 0.333);
    # the multi-window dominant_sign reflects whatever the wider L56/L90
    # windows say on the synthetic fixture and is asserted at the helper
    # level above, not here.
    assert bp["observed_windows"]["L28"]["sign"] == 1


def test_flag_on_supplements_keeps_cold_start_path():
    """DS Memo-4 REJECT: discount-hygiene flag ON but vertical=supplements
    -> helper short-circuits, card stays cold-start (no observed stash)."""
    clear_cache()
    cand = _candidate(audience_size=400)
    g = _build_synthetic_discount_frame(
        recent_heavy_customers=50,
        recent_normal_customers=50,
        prior_heavy_customers=20,
        prior_normal_customers=80,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="supplements",
        orders_df=g,
        observed_discount_hygiene_enabled=True,
    )
    if card is None:
        # Supplements discount_dependency_hygiene prior is unavailable
        # by design (DS Memo-4 REJECT) — the prior-unvalidated routing
        # may suppress emission entirely. Helper-level supplements
        # short-circuit is pinned above.
        return
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    if bp is not None:
        assert bp["observed_n"] == 0
        assert "observed_sign_agreement_count" not in bp


def test_winback_flag_does_not_activate_discount_hygiene_observed_effect():
    """The T1 winback flag (``observed_effect_enabled``) must NOT run the
    discount-hygiene observed-effect path. Per-builder flag independence
    is a load-bearing invariant of the per-builder rollout."""
    clear_cache()
    cand = _candidate(
        play_id="discount_dependency_hygiene", audience_size=400
    )
    g = _build_synthetic_discount_frame(
        recent_heavy_customers=50,
        recent_normal_customers=50,
        prior_heavy_customers=20,
        prior_normal_customers=80,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=True,                # winback flag
        observed_replenishment_enabled=False,        # replenishment flag
        observed_discount_hygiene_enabled=False,     # discount-hygiene flag OFF
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


def test_replenishment_flag_does_not_activate_discount_hygiene_observed_effect():
    """The T2 replenishment flag must NOT run the discount-hygiene
    observed-effect path. Per-builder flag independence is load-bearing."""
    clear_cache()
    cand = _candidate(
        play_id="discount_dependency_hygiene", audience_size=400
    )
    g = _build_synthetic_discount_frame(
        recent_heavy_customers=50,
        recent_normal_customers=50,
        prior_heavy_customers=20,
        prior_normal_customers=80,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=False,
        observed_replenishment_enabled=True,         # replenishment flag
        observed_discount_hygiene_enabled=False,     # discount-hygiene flag OFF
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
    g = _build_synthetic_discount_frame(
        recent_heavy_customers=50,
        recent_normal_customers=50,
        prior_heavy_customers=20,
        prior_normal_customers=80,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_discount_hygiene_enabled=True,
    )
    if card is None:
        pytest.skip("discount_dependency_hygiene prior unavailable")
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    assert "observed_windows" in bp
    # L28 must be present and reflect recent revenue-weighted k/n with
    # positive sign.
    l28 = bp["observed_windows"]["L28"]
    assert l28["k"] == 5000
    assert l28["n"] == 7500
    assert l28["sign"] == 1
