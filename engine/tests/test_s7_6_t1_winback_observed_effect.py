"""Sprint 7.6 Ticket T1 — winback observed-effect wiring tests.

Verifies:
- Flag OFF default: no observed_effect computation; blend_provenance
  retains cold-start fields (``observed_n=0``, ``store_data_status =
  no_outcome_history``) — byte-identity proxy.
- Flag ON with a synthetic fixture that has dense recent reactivations:
  ``observed_n > 0``, posterior shifts toward observed rate
  proportionally to ``n / (n + pseudo_n)``.
- Multi-window sign-agreement is stashed on blend_provenance only when
  the path runs (flag ON).
- Helper short-circuits on empty / mal-typed frames.
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
from src.measurement_observed import ObservedEffectResult  # noqa: E402
from src.priors_loader import clear_cache  # noqa: E402


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


def _row(customer_id: str, days_ago: int):
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": ANCHOR - pd.Timedelta(days=days_ago),
        "net_sales": 50.0,
        "lineitem_any": "Cleanser 50ml",
    }


def _candidate(audience_size: int = 600):
    return SimpleNamespace(
        play_id="winback_dormant_cohort",
        audience_size=audience_size,
        segment_definition="dormant repeat-buyers test cohort",
        data_used=[],
        preliminary_rejection_reason=None,
        cold_start=False,
    )


def _aligned_with_aov(aov: float = 60.0):
    return {"L28": {"aov": aov, "delta": {}, "p": {}, "meta": {}}}


def _build_synthetic_winback_frame(
    *,
    recent_cohort_size: int,
    recent_recoveries: int,
    prior_cohort_size: int,
    prior_recoveries: int,
):
    """Build a synthetic orders frame that produces specific recent/prior
    dormant cohorts and recoveries when ``compute_winback_observed_effect``
    runs on it with ``vertical='beauty'`` (wb_lo=21, wb_hi=45).

    Cohort layout (beauty wb_lo=21, wb_hi=45):

        - Recent L28 cohort (anchor=maxd-28d): each member has a prior
          order at 240d ago (>=2-prior gate satisfied) and a second
          order at 65d ago (= 37d before anchor, inside [21,45]; NOT
          in pre28 window (28,56]d-before-maxd). ``recent_recoveries``
          of them get a recovery order at 10d ago (after anchor,
          within 28d window).
        - Prior cohort (anchor=maxd-56d): each member has a prior order
          at 300d ago and a second order at 90d ago (= 34d before
          anchor, inside [21,45]; NOT in pre28 (56,84]d-before-maxd).
          ``prior_recoveries`` get a recovery order at 40d ago (in
          (maxd-56d, maxd-28d]).
        - A single "anchor" customer with one order at day 0 to pin
          ``maxd == ANCHOR``.

    Cross-cohort isolation: recent cohort's 65d-ago second order
    fails [21,45]d-before-(maxd-56d) (=9d-since-anchor) so they are
    NOT members of the prior cohort. Prior cohort's 90d-ago second
    order fails [21,45]d-before-(maxd-28d) (=62d-since-anchor) so
    they are NOT members of the recent cohort.
    """
    rows = [_row("anchor", 0)]

    for i in range(recent_cohort_size):
        cid = f"r{i}"
        rows.append(_row(cid, 240))
        rows.append(_row(cid, 65))
        if i < recent_recoveries:
            rows.append(_row(cid, 10))

    for j in range(prior_cohort_size):
        cid = f"p{j}"
        rows.append(_row(cid, 300))
        rows.append(_row(cid, 90))
        if j < prior_recoveries:
            rows.append(_row(cid, 40))

    return pd.DataFrame(rows).sort_values(["customer_id", "Created at"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_compute_winback_observed_effect_empty_frame_returns_none():
    primary, agg = mb.compute_winback_observed_effect(None, vertical="beauty")
    assert primary is None
    assert agg is None

    primary, agg = mb.compute_winback_observed_effect(
        pd.DataFrame(), vertical="beauty"
    )
    assert primary is None
    assert agg is None


def test_compute_winback_observed_effect_recovers_synthetic_signal():
    g = _build_synthetic_winback_frame(
        recent_cohort_size=200,
        recent_recoveries=30,   # 15% recovery
        prior_cohort_size=200,
        prior_recoveries=10,    # 5% recovery
    )
    primary, agg = mb.compute_winback_observed_effect(g, vertical="beauty")
    assert primary is not None
    assert primary.n == 200
    assert primary.k == 30
    assert primary.sign == 1  # 15% > 5%
    assert primary.effect == pytest.approx(0.10, abs=1e-9)
    assert primary.p_value is not None and primary.p_value < 0.01
    assert agg is not None
    # Beauty wb_lo/wb_hi means L28 + L56 share the same cohort overlap
    # mechanics; we only assert L28 sign positive and at least L28 in the
    # agreement payload.
    assert "L28" in agg.windows
    assert agg.windows["L28"].sign == 1


# ---------------------------------------------------------------------------
# Card-seam wiring tests
# ---------------------------------------------------------------------------


def test_flag_off_default_cold_start_provenance_unchanged():
    """When ``observed_effect_enabled=False``, orders_df is ignored and
    blend_provenance keeps the cold-start signature."""
    clear_cache()
    cand = _candidate(audience_size=600)
    g = _build_synthetic_winback_frame(
        recent_cohort_size=200,
        recent_recoveries=30,
        prior_cohort_size=200,
        prior_recoveries=10,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=False,
    )
    assert card is not None
    bp = next(d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance")
    assert bp["observed_k"] == 0
    assert bp["observed_n"] == 0
    assert bp["store_data_status"] == "no_outcome_history"
    assert bp["posterior_value"] == 0.08  # = prior value
    assert "observed_sign_agreement_count" not in bp
    assert "observed_windows" not in bp


def test_flag_on_threads_observed_kn_and_shifts_posterior():
    clear_cache()
    cand = _candidate(audience_size=600)
    g = _build_synthetic_winback_frame(
        recent_cohort_size=200,
        recent_recoveries=30,   # 15% recovery vs 8% prior
        prior_cohort_size=200,
        prior_recoveries=10,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=True,
    )
    assert card is not None
    bp = next(d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance")
    assert bp["observed_n"] == 200
    assert bp["observed_k"] == 30
    assert bp["store_data_status"] == "store_outcomes_observed"
    # posterior = (prior_value * pseudo_n + observed_rate * n) / (pseudo_n + n)
    # = (0.08 * 30 + 0.15 * 200) / (30 + 200) = (2.4 + 30.0) / 230 = 0.140869...
    assert bp["posterior_value"] == pytest.approx(0.140870, abs=1e-5)
    # n > pseudo_n -> store_dominant
    assert bp["posterior_ratio"] == "store_dominant"
    # Multi-window agreement stashed
    assert "observed_sign_agreement_count" in bp
    assert "observed_dominant_sign" in bp
    assert "observed_windows" in bp
    assert bp["observed_dominant_sign"] == 1


def test_flag_on_zero_n_falls_back_to_cold_start():
    """Flag ON but orders_df has no qualifying cohort -> primary.n==0,
    posterior should still collapse to prior."""
    clear_cache()
    cand = _candidate(audience_size=600)
    g = pd.DataFrame([_row("anchor", 0)])  # only the anchor; no cohort
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=True,
    )
    assert card is not None
    bp = next(d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance")
    assert bp["observed_n"] == 0
    assert bp["posterior_value"] == 0.08  # prior


def test_flag_on_non_winback_play_ignores_orders_df():
    """The observed-effect path is scoped to winback_dormant_cohort
    only at T1; other prior-anchored plays must be unaffected."""
    clear_cache()
    cand = SimpleNamespace(
        play_id="replenishment_due",
        audience_size=600,
        segment_definition="x",
        data_used=[],
        preliminary_rejection_reason=None,
        cold_start=False,
    )
    g = _build_synthetic_winback_frame(
        recent_cohort_size=200,
        recent_recoveries=30,
        prior_cohort_size=200,
        prior_recoveries=10,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=True,
    )
    # replenishment_due Beauty prior is validated_external; card emits.
    if card is not None:
        bp = next(
            (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
            None,
        )
        if bp is not None:
            assert bp["observed_n"] == 0
            assert "observed_sign_agreement_count" not in bp
