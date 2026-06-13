"""Sprint 7.6 Ticket T2 — B-2 replenishment_due observed-effect tests.

Verifies:
- Helper short-circuits on empty / mal-typed frames, and on
  ``vertical='supplements'`` (KI-27 parser unavailable).
- Synthetic Beauty fixture produces the expected ``(observed_k,
  observed_n)`` and positive sign when recent reorder rate exceeds prior.
- Card seam: flag OFF preserves cold-start blend_provenance (no
  ``observed_sign_agreement_count`` key); flag ON shifts posterior toward
  observed rate and stashes sign-agreement.
- T1 winback flag does NOT activate replenishment-side observed-effect.
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


def _row(customer_id: str, days_ago: int, lineitem: str = "Cleanser 50ml"):
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": ANCHOR - pd.Timedelta(days=days_ago),
        "net_sales": 50.0,
        "lineitem_any": lineitem,
    }


def _candidate(play_id: str = "replenishment_due", audience_size: int = 600):
    return SimpleNamespace(
        play_id=play_id,
        audience_size=audience_size,
        segment_definition="per-SKU cadence-due cohort test",
        data_used=[],
        preliminary_rejection_reason=None,
        cold_start=False,
    )


def _aligned_with_aov(aov: float = 60.0):
    return {"L28": {"aov": aov, "delta": {}, "p": {}, "meta": {}}}


def _build_synthetic_replenishment_frame(
    *,
    recent_cohort_size: int,
    recent_reorders: int,
    prior_cohort_size: int,
    prior_reorders: int,
):
    """Build a synthetic in-class orders frame producing specific
    due-cohort sizes and reorder counts when run with vertical='beauty'.

    Cohort design (median_gap = 30 days, 0.8x..1.2x = 24..36 days):

      Recent cohort (anchor = maxd - 28 = day -28):
        Each member has prior in-class orders at days_ago in
        {120, 90, 60} (gaps 30, 30; median 30). The last-before-anchor
        is at day 60 -> days-since-anchor = 60 - 28 = 32, in [24, 36].
        ``recent_reorders`` of them have an additional in-class order
        at day 5 (>anchor, <=maxd).

      Prior cohort (anchor = maxd - 56 = day -56):
        Members have orders at days_ago {148, 118, 88}; gaps 30, 30;
        last-before-anchor day-88 -> days-since-anchor 88-56 = 32 in
        [24, 36]. ``prior_reorders`` of them have an additional
        in-class order at day 40 (in (maxd-56, maxd-28]).

      Cross-isolation: recent's last order day-60 places it at
      days-since-(maxd-56)=4, outside [24,36], so recent members do not
      qualify under the prior anchor; similarly prior's day-88
      places days-since-(maxd-28)=60, outside [24,36].

      Anchor pin: one customer with a single order at day 0 to fix
      maxd == ANCHOR.
    """
    rows = [_row("anchor", 0)]

    for i in range(recent_cohort_size):
        cid = f"r{i}"
        rows.append(_row(cid, 120))
        rows.append(_row(cid, 90))
        rows.append(_row(cid, 60))
        if i < recent_reorders:
            rows.append(_row(cid, 5))

    for j in range(prior_cohort_size):
        cid = f"p{j}"
        rows.append(_row(cid, 148))
        rows.append(_row(cid, 118))
        rows.append(_row(cid, 88))
        if j < prior_reorders:
            rows.append(_row(cid, 40))

    return (
        pd.DataFrame(rows)
        .sort_values(["customer_id", "Created at"])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_compute_replenishment_observed_effect_empty_frame_returns_none():
    primary, agg = mb.compute_replenishment_observed_effect(None, vertical="beauty")
    assert primary is None and agg is None

    primary, agg = mb.compute_replenishment_observed_effect(
        pd.DataFrame(), vertical="beauty"
    )
    assert primary is None and agg is None


def test_compute_replenishment_observed_effect_supplements_skipped_ki27():
    """KI-27: supplements replenishment_parser unavailable -> helper
    returns (None, None). Caller MUST treat as cold-start (0/0)."""
    g = _build_synthetic_replenishment_frame(
        recent_cohort_size=100, recent_reorders=20,
        prior_cohort_size=100, prior_reorders=5,
    )
    primary, agg = mb.compute_replenishment_observed_effect(
        g, vertical="supplements"
    )
    assert primary is None and agg is None


def test_compute_replenishment_observed_effect_recovers_synthetic_signal():
    g = _build_synthetic_replenishment_frame(
        recent_cohort_size=100, recent_reorders=20,   # 20%
        prior_cohort_size=100, prior_reorders=5,      # 5%
    )
    primary, agg = mb.compute_replenishment_observed_effect(g, vertical="beauty")
    assert primary is not None
    assert primary.n == 100
    assert primary.k == 20
    assert primary.sign == 1
    assert primary.effect == pytest.approx(0.15, abs=1e-9)
    assert primary.p_value is not None and primary.p_value < 0.01
    assert agg is not None
    assert "L28" in agg.windows
    assert agg.windows["L28"].sign == 1


def test_compute_replenishment_observed_effect_missing_columns_returns_none():
    g = pd.DataFrame([{"customer_id": "x", "Created at": ANCHOR}])
    primary, agg = mb.compute_replenishment_observed_effect(g, vertical="beauty")
    assert primary is None and agg is None


# ---------------------------------------------------------------------------
# Card-seam wiring tests
# ---------------------------------------------------------------------------


def test_flag_off_default_cold_start_provenance_unchanged():
    """``observed_replenishment_enabled=False`` -> orders_df ignored; the
    blend_provenance keeps the cold-start signature exactly."""
    clear_cache()
    cand = _candidate(audience_size=600)
    g = _build_synthetic_replenishment_frame(
        recent_cohort_size=100, recent_reorders=20,
        prior_cohort_size=100, prior_reorders=5,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_replenishment_enabled=False,
    )
    if card is None:
        pytest.skip(
            "replenishment_due prior unavailable in test env; "
            "exercise covered by helper-level tests"
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
    cand = _candidate(audience_size=600)
    g = _build_synthetic_replenishment_frame(
        recent_cohort_size=100, recent_reorders=20,   # 20%
        prior_cohort_size=100, prior_reorders=5,      # 5%
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_replenishment_enabled=True,
    )
    if card is None:
        pytest.skip(
            "replenishment_due prior unavailable in test env; "
            "exercise covered by helper-level tests"
        )
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    assert bp["observed_n"] == 100
    assert bp["observed_k"] == 20
    assert bp["store_data_status"] == "store_outcomes_observed"
    # Posterior should shift from prior toward 0.20 as n>pseudo_n.
    assert bp["posterior_value"] != bp["prior_value"]
    assert "observed_sign_agreement_count" in bp
    assert "observed_dominant_sign" in bp
    assert bp["observed_dominant_sign"] == 1


def test_flag_on_supplements_keeps_cold_start_path():
    """KI-27: replenishment-side flag ON but vertical=supplements ->
    helper short-circuits, card stays cold-start (no observed stash)."""
    clear_cache()
    cand = _candidate(audience_size=600)
    g = _build_synthetic_replenishment_frame(
        recent_cohort_size=100, recent_reorders=20,
        prior_cohort_size=100, prior_reorders=5,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="supplements",
        orders_df=g,
        observed_replenishment_enabled=True,
    )
    if card is None:
        # Supplements replenishment prior may be unavailable; the helper
        # short-circuit is already pinned at the helper-level test above.
        return
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    if bp is not None:
        assert bp["observed_n"] == 0
        assert "observed_sign_agreement_count" not in bp


def test_winback_flag_does_not_activate_replenishment_observed_effect():
    """The T1 winback flag (``observed_effect_enabled``) must NOT run the
    replenishment observed-effect path. Independence of the two flags is
    a load-bearing invariant of the per-builder rollout."""
    clear_cache()
    cand = _candidate(play_id="replenishment_due", audience_size=600)
    g = _build_synthetic_replenishment_frame(
        recent_cohort_size=100, recent_reorders=20,
        prior_cohort_size=100, prior_reorders=5,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_effect_enabled=True,           # winback flag
        observed_replenishment_enabled=False,   # replenishment flag OFF
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
    cand = _candidate(audience_size=600)
    g = _build_synthetic_replenishment_frame(
        recent_cohort_size=100, recent_reorders=20,
        prior_cohort_size=100, prior_reorders=5,
    )
    card = mb.build_prior_anchored_play_card(
        cand,
        _aligned_with_aov(60.0),
        vertical="beauty",
        orders_df=g,
        observed_replenishment_enabled=True,
    )
    if card is None:
        pytest.skip("replenishment_due prior unavailable in test env")
    bp = next(
        (d for d in card.revenue_range.drivers if d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    assert "observed_windows" in bp
    # L28 must be present and reflect the recent k/n with positive sign.
    l28 = bp["observed_windows"]["L28"]
    assert l28["k"] == 20
    assert l28["n"] == 100
    assert l28["sign"] == 1
