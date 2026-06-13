"""tests/test_synthetic_fixtures_8_11.py

Fixture-validation tests for synthetic blocker Fixes 8-11.

These tests pin the post-Fix-8/9/10/11 properties of the four retuned
synthetic scenarios so a future regeneration cannot silently regress
the merchant-visible behavior they unblock:

* Fix 8: ``healthy_beauty_240d`` -- L28 returning_customer_share at the
  Sep 18 anchor must be POSITIVE relative to the prior 28-day window,
  with sign-stable agreement across L56/L90, so the Phase 5.6 directional
  ``first_to_second_purchase`` pathway has a non-zero chance of firing.
  The engine itself decides whether to fire; the fixture only needs to
  carry the signal it claims to.
* Fix 9: ``supplement_replenishment_240d`` -- ``returning_customer_share``
  at the anchor must be strictly below 100% (post-Fix-9 the generator
  spreads first-order dates across the entire window so a non-zero
  fraction of L28 customers are genuinely new); ``subscription_nudge``
  must surface as an M3 base candidate with a non-degenerate audience.
  No supplement directional pathway is added or required.
* Fix 10: ``promo_anomaly_240d`` -- the promo spike must be inside the
  L56 lookback of the Sep 18 anchor (i.e. the promo month must be after
  the L56-prior cutoff). Pre-Fix-10 the May spike was outside L90; the
  fixture validated nothing about anomaly behavior. The fix is fixture
  realism only -- no anomaly threshold is changed.
* Fix 11: ``healthy_beauty_low_inventory_240d`` -- the inventory CSV's
  ``Updated At`` must be fresh against today's wall clock so the engine's
  ``compute_inventory_metrics`` does not drop the data as 200+ days
  stale. Tested by checking the max ``Updated At`` is within the engine's
  default ``INVENTORY_MAX_AGE_DAYS`` window.

Run with::

    pytest tests/test_synthetic_fixtures_8_11.py -v

These tests do NOT spin up the full engine. They read the regenerated
CSVs directly and compute the load-bearing slice of each metric. The
end-to-end DOM-level assertions live with the synthetic harness +
reporter (``tests/synthetic_harness.py`` / ``tests/synthetic_reporter.py``).
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_YAML = REPO_ROOT / "tests" / "fixtures" / "synthetic_scenarios.yaml"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "synthetic"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scenarios():
    with open(SCENARIOS_YAML) as f:
        return yaml.safe_load(f)["scenarios"]


def _load_orders(name: str) -> pd.DataFrame:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = pd.read_csv(FIXTURES_DIR / f"{name}_orders.csv", low_memory=False)
    return df


def _load_inventory(name: str) -> pd.DataFrame:
    return pd.read_csv(FIXTURES_DIR / f"{name}_inventory.csv", low_memory=False)


def _orders_with_dates(name: str) -> pd.DataFrame:
    df = _load_orders(name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df["_date"] = pd.to_datetime(
            df["Created at"], errors="coerce", utc=True
        ).dt.tz_localize(None)
    return df


def _identify_customer_columns(df: pd.DataFrame) -> pd.Series:
    return (
        df["Customer Email"].astype(str).str.strip().str.lower().replace({"": pd.NA})
    )


def _returning_share_at_window(
    df: pd.DataFrame, anchor: pd.Timestamp, days: int
) -> tuple[float, int]:
    """Return (returning_customer_share, identified_count) for a window
    of ``days`` ending at ``anchor`` (inclusive).

    Mirrors the engine's ``returning_customer_share`` definition: the
    fraction of customers in the recent window whose first-ever order
    occurred BEFORE the recent-window start.
    """
    paid = df[df["Financial Status"].astype(str).str.lower() == "paid"].copy()
    paid = paid.drop_duplicates(subset=["Name"]) if "Name" in paid.columns else paid
    keys = _identify_customer_columns(paid)
    paid = paid.assign(_key=keys).dropna(subset=["_key"])
    if paid.empty:
        return float("nan"), 0
    first_seen = paid.groupby("_key")["_date"].min()
    rec_end = anchor.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
    rec_start = rec_end.normalize() - pd.Timedelta(days=days - 1)
    rec = paid[(paid["_date"] >= rec_start) & (paid["_date"] <= rec_end)]
    if rec.empty:
        return float("nan"), 0
    unique = rec["_key"].dropna().unique()
    if len(unique) == 0:
        return float("nan"), 0
    returning = sum(first_seen.get(k, rec_start) < rec_start for k in unique)
    return float(returning) / float(len(unique)), int(len(unique))


# ---------------------------------------------------------------------------
# Fix 8 -- healthy_beauty_240d L28 returning_customer_share sign
# ---------------------------------------------------------------------------


class TestFix8HealthyBeautyL28Sign:
    """Pin the post-Fix-8 retune of ``healthy_beauty_240d``:

    The L28 returning_customer_share at the Sep 18 anchor must be POSITIVE
    relative to the prior 28-day window. Sign-stability across L56/L90
    is also pinned so the Phase 5.6 ``consistency_across_windows >= 2``
    gate has a chance to fire.
    """

    SCENARIO = "healthy_beauty_240d"

    def _shares(self, scenarios) -> dict:
        df = _orders_with_dates(self.SCENARIO)
        anchor = pd.Timestamp(scenarios[self.SCENARIO]["anchor_date"])
        out = {}
        for w in (28, 56, 90):
            rec_share, rec_n = _returning_share_at_window(df, anchor, w)
            prior_share, prior_n = _returning_share_at_window(
                df, anchor - pd.Timedelta(days=w), w
            )
            if prior_share == 0 or pd.isna(prior_share) or pd.isna(rec_share):
                delta = float("nan")
            else:
                delta = (rec_share - prior_share) / abs(prior_share)
            out[f"L{w}"] = {
                "recent": rec_share,
                "prior": prior_share,
                "delta": delta,
                "n_recent": rec_n,
                "n_prior": prior_n,
            }
        return out

    def test_l28_returning_share_delta_is_positive(self, scenarios):
        s = self._shares(scenarios)["L28"]
        assert not pd.isna(s["delta"]), (
            f"healthy_beauty L28 delta unavailable: rec={s['recent']!r} "
            f"prior={s['prior']!r}"
        )
        assert s["delta"] > 0, (
            f"healthy_beauty L28 returning_customer_share delta must be >0 "
            f"post-Fix-8; got {s['delta']:.4f} (rec={s['recent']:.4f}, "
            f"prior={s['prior']:.4f}). Pre-Fix-8 baseline was -0.017."
        )

    def test_l56_l90_share_signs_agree_with_l28(self, scenarios):
        s = self._shares(scenarios)
        l28_sign = 1 if s["L28"]["delta"] > 0 else -1
        agree = sum(
            1
            for w in ("L28", "L56", "L90")
            if not pd.isna(s[w]["delta"]) and (s[w]["delta"] > 0) == (l28_sign > 0)
        )
        assert agree >= 2, (
            f"healthy_beauty L28/L56/L90 returning-share sign agreement must "
            f"be >=2 post-Fix-8; got {agree} (L28={s['L28']['delta']:.3f}, "
            f"L56={s['L56']['delta']:.3f}, L90={s['L90']['delta']:.3f})."
        )

    def test_l28_window_has_enough_identified_customers(self, scenarios):
        s = self._shares(scenarios)["L28"]
        # Engine's default min_identified is 10. Healthy_beauty should
        # comfortably clear this.
        assert s["n_recent"] >= 50, (
            f"healthy_beauty L28 identified count too low: {s['n_recent']}"
        )


# ---------------------------------------------------------------------------
# Fix 9 -- supplement_replenishment_240d realism
# ---------------------------------------------------------------------------


class TestFix9SupplementRealism:
    """Pin the post-Fix-9 retune of ``supplement_replenishment_240d``:

    * ``returning_customer_share`` < 100%.
    * Internal consistency: not every customer in L28 has prior history.
    * Customer pool large enough for ``subscription_nudge`` style cohorts
      to exceed the engine's MIN_N_CUSTOMER_AUDIENCE floor (typically 60).
    """

    SCENARIO = "supplement_replenishment_240d"

    def test_l28_returning_share_capped_below_100pct(self, scenarios):
        df = _orders_with_dates(self.SCENARIO)
        anchor = pd.Timestamp(scenarios[self.SCENARIO]["anchor_date"])
        share, n = _returning_share_at_window(df, anchor, 28)
        assert not pd.isna(share), (
            f"supplement L28 returning share unavailable; n={n}"
        )
        assert share < 1.0, (
            f"supplement L28 returning_customer_share must be < 100% "
            f"post-Fix-9; got {share:.4f} (pre-Fix-9 baseline was 1.0). "
            f"The Fix-9 retune spreads first-order dates across the "
            f"whole window so some L28 customers are genuinely new."
        )

    def test_some_customers_first_order_lands_inside_l28(self, scenarios):
        """A direct check that the Fix 9 retune actually puts some
        customers' first-ever order inside the L28 window."""
        df = _orders_with_dates(self.SCENARIO)
        anchor = pd.Timestamp(scenarios[self.SCENARIO]["anchor_date"])
        paid = df[df["Financial Status"].astype(str).str.lower() == "paid"].copy()
        paid = paid.drop_duplicates(subset=["Name"])
        keys = _identify_customer_columns(paid)
        paid = paid.assign(_key=keys).dropna(subset=["_key"])
        first_seen = paid.groupby("_key")["_date"].min()
        l28_start = (anchor.normalize() - pd.Timedelta(days=27))
        l28_end = anchor.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
        new_in_l28 = ((first_seen >= l28_start) & (first_seen <= l28_end)).sum()
        assert int(new_in_l28) >= 5, (
            f"supplement scenario must have at least a handful of "
            f"customers whose first-ever order lands inside L28; got "
            f"{int(new_in_l28)}. Pre-Fix-9 every customer's first "
            f"order was inside the early 60d window so this count was 0."
        )

    def test_repeat_customers_population_supports_subscription_nudge(self, scenarios):
        """The supplement scenario should have many customers with 2+
        orders so ``subscription_nudge`` (and similar repeat-cohort
        plays) can build a non-degenerate audience.
        """
        df = _load_orders(self.SCENARIO)
        paid = df[df["Financial Status"].astype(str).str.lower() == "paid"].copy()
        paid = paid.drop_duplicates(subset=["Name"])
        cust_orders = paid.groupby("Customer Email").size()
        repeat = int((cust_orders >= 2).sum())
        # Pre-Fix-9 the subscription_nudge audience was 12 (degenerate).
        # Post-Fix-9 it should be in the hundreds.
        assert repeat >= 100, (
            f"supplement repeat-customer count too low: {repeat} (need "
            f">=100 to support subscription_nudge-style audience floors)"
        )

    def test_supplement_product_size_tokens_present(self, scenarios):
        """Fix 9 explicitly preserves the size-token product metadata
        (e.g. ``30ct``, ``90ct``, ``2lb``, ``1lb``, ``16oz``) in
        ``Lineitem name`` so any SKU-anchored or replenishment-style
        play has size data available. We do NOT assert ``empty_bottle``
        fires -- its current parser is beauty-coded for ml/oz volumes,
        and extending it to ct/lb is engine work, not fixture work.
        """
        df = _load_orders(self.SCENARIO)
        names = df["Lineitem name"].astype(str).str.lower().unique().tolist()
        size_token_patterns = ["ct", "lb", "oz", "g ", "mg"]
        with_size = [
            n
            for n in names
            if any(tok in n for tok in size_token_patterns)
        ]
        assert len(with_size) >= 5, (
            f"supplement product names should carry size tokens for at "
            f"least 5 distinct line items; got {len(with_size)}: {names[:10]}"
        )


# ---------------------------------------------------------------------------
# Fix 10 -- promo_anomaly_240d anchor / spike alignment
# ---------------------------------------------------------------------------


class TestFix10PromoAnomalyInsideL56:
    """Pin the post-Fix-10 retune of ``promo_anomaly_240d``:

    The promo spike month must overlap the L56 lookback of the Sep 18
    anchor so the engine's anomaly logic can actually exercise the
    spike. Pre-Fix-10 the spike was in May (m_idx=4), entirely outside
    L56 of a Sep anchor. Post-Fix-10 it is in August (m_idx=7).
    """

    SCENARIO = "promo_anomaly_240d"

    def test_promo_month_index_inside_l56_lookback(self, scenarios):
        cfg = scenarios[self.SCENARIO]
        anchor = pd.Timestamp(cfg["anchor_date"])
        promo_idx = int(cfg.get("promo_month_index", 4))

        df = _orders_with_dates(self.SCENARIO)
        paid = df[df["Financial Status"].astype(str).str.lower() == "paid"].copy()
        paid = paid.drop_duplicates(subset=["Name"])
        paid["_month"] = paid["_date"].dt.to_period("M")
        months = sorted(paid["_month"].dropna().unique())
        assert promo_idx < len(months), (
            f"promo_anomaly: promo_month_index={promo_idx} but only "
            f"{len(months)} months of data."
        )
        promo_month = months[promo_idx]
        promo_start = promo_month.to_timestamp()
        promo_end = (promo_month + 1).to_timestamp() - pd.Timedelta(seconds=1)

        l56_start = (anchor.normalize() - pd.Timedelta(days=55))
        l56_end = anchor.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
        # Spike must overlap L56.
        overlap = (promo_start <= l56_end) and (promo_end >= l56_start)
        assert overlap, (
            f"promo_anomaly spike month {promo_month} must overlap L56 "
            f"({l56_start.date()}..{l56_end.date()}) of anchor "
            f"{anchor.date()}; pre-Fix-10 the May spike was outside L90."
        )

    def test_promo_month_revenue_actually_spikes(self, scenarios):
        """The new promo month index must actually carry the spike (the
        generator is deterministic per seed; we still pin the property)."""
        cfg = scenarios[self.SCENARIO]
        promo_idx = int(cfg.get("promo_month_index", 4))

        df = _orders_with_dates(self.SCENARIO)
        paid = df[df["Financial Status"].astype(str).str.lower() == "paid"].copy()
        paid = paid.drop_duplicates(subset=["Name"])
        paid["_month"] = paid["_date"].dt.to_period("M")
        monthly_rev = paid.groupby("_month")["Subtotal"].sum().sort_index()
        if len(monthly_rev) <= promo_idx:
            pytest.skip("Not enough months for spike check")
        promo_rev = float(monthly_rev.iloc[promo_idx])
        baseline = [
            float(r) for i, r in enumerate(monthly_rev.values) if i != promo_idx and r > 0
        ]
        if not baseline:
            pytest.skip("No baseline months")
        baseline_avg = sum(baseline) / len(baseline)
        assert promo_rev >= baseline_avg * 1.5, (
            f"promo_anomaly promo-month revenue ${promo_rev:,.0f} should "
            f"be >= 1.5x baseline ${baseline_avg:,.0f}."
        )


# ---------------------------------------------------------------------------
# Fix 11 -- low_inventory runner-clock alignment
# ---------------------------------------------------------------------------


class TestFix11LowInventoryRunnerClock:
    """Pin the post-Fix-11 retune of the low_inventory inventory CSV:

    ``Updated At`` is written relative to ``pd.Timestamp.now()`` rather
    than the synthetic ``anchor_date`` so the engine's freshness check
    (which uses the wall-clock now) does not drop the data as stale.
    Pre-Fix-11 the CSV read as 200+ days stale at any reasonable run
    time after the fixture was generated.
    """

    SCENARIO = "healthy_beauty_low_inventory_240d"

    def test_inventory_updated_at_is_fresh(self, scenarios):
        inv = _load_inventory(self.SCENARIO)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            updated = pd.to_datetime(inv["Updated At"], errors="coerce")
        assert not updated.isna().all(), "Inventory Updated At all NaN"
        max_age_days = (pd.Timestamp.now() - updated.max()).days
        # Default INVENTORY_MAX_AGE_DAYS in the engine is 7.
        assert max_age_days <= 7, (
            f"Inventory CSV must be fresh against the runner clock "
            f"post-Fix-11; max age is {max_age_days} days. The engine's "
            f"default INVENTORY_MAX_AGE_DAYS is 7."
        )

    def test_inventory_updated_at_is_tz_naive(self, scenarios):
        """Pre-Fix-11 we used Pacific (-07:00) tz-aware order timestamps,
        which made ``compute_inventory_metrics`` raise tz-aware vs.
        tz-naive subtraction errors. Post-Fix-11 the orders are tz-naive
        and the inventory CSV likewise. Pin both so a future change to
        the generator that re-introduces offsets fails this test loudly.
        """
        inv = _load_inventory(self.SCENARIO)
        sample = str(inv["Updated At"].iloc[0])
        # Reject Pacific / UTC / numeric-suffix offsets.
        for forbidden in ("-07:00", "-08:00", "+00:00", "Z"):
            assert forbidden not in sample, (
                f"Inventory Updated At should not carry a timezone "
                f"suffix; got {sample!r}"
            )

    def test_orders_created_at_is_tz_naive(self, scenarios):
        """Same tz-naive contract for the orders CSV."""
        df = _load_orders(self.SCENARIO)
        sample = str(df["Created at"].iloc[0])
        for forbidden in ("-07:00", "-08:00", "+00:00"):
            assert forbidden not in sample, (
                f"Orders Created at should not carry a timezone offset "
                f"post-Fix-11; got {sample!r}"
            )

    def test_hero_sku_still_low(self, scenarios):
        """The hero SKU low-inventory property is preserved post-Fix-11."""
        inv = _load_inventory(self.SCENARIO)
        hero_avail = inv.iloc[0]["Available"]
        assert int(hero_avail) <= 10, (
            f"Low-inventory hero SKU should still have <=10 units; "
            f"got {hero_avail}."
        )
