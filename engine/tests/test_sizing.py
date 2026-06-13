"""Tests for ``src.sizing.size_play`` (Milestone 6, T6.2-T6.4).

Pinned behavior:

- audience x p_action x incremental_orders x AOV formula;
- conservative-suppression policy:
    * cold_start -> suppressed=True
    * targeting + non-causal prior -> suppressed=True
    * audience<=0 / aov<=0 -> suppressed=True
- drivers[] provenance: every non-suppressed range has named, source-
  labeled drivers; every suppressed range carries a suppression_reason
  driver;
- p10 < p50 < p90 invariant for non-suppressed ranges (or all equal
  when collapsed by an observed point estimate with no incremental-
  orders prior);
- source labels: store_observed | vertical_prior | blend.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

yaml = pytest.importorskip("yaml")

from src import priors_loader as PL
from src.engine_run import RevenueRangeSource
from src.sizing import SizingInputs, shadow_compare, size_play


@pytest.fixture(autouse=True)
def _reset_priors_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


# ---------------------------------------------------------------------------
# T6.2 acceptance: winback formula
# ---------------------------------------------------------------------------


def test_winback_measured_with_observed_effect():
    """200 customers, AOV $80, observed reactivation 4pp.

    Per the M6 plan T6.2 acceptance test, the formula is:
        revenue = audience x p_action x incremental_orders x AOV

    With observed_effect=0.04 and the default winback_21_45 prior for
    orders_per_customer (~1.30 across all verticals), the p50 should be:

        200 x 0.04 x 1.30 x $80 = $832

    p10/p90 widen via the orders_per_customer prior range_p10/p90.
    """

    out = size_play(
        SizingInputs(
            play_id="winback_21_45",
            evidence_class="measured",
            audience_size=200,
            aov=80.0,
            observed_effect=0.04,
            observed_metric_name="reactivation_rate",
            observed_n=200,
            vertical="beauty",
        )
    )

    assert out.suppressed is False
    assert out.source == RevenueRangeSource.BLEND  # observed effect + prior orders/customer
    # Centered point at observed_effect; the prior orders_per_customer adds the spread.
    assert out.p10 < out.p50 <= out.p90  # p10 strict less, p50 may equal p90 if value==range_p90
    assert abs(out.p50 - 832.0) < 5.0  # 200 * 0.04 * 1.30 * 80
    # Drivers carry reactivation_rate (observed) + audience + aov + incremental_orders
    names = [d["name"] for d in out.drivers]
    assert "audience_size" in names
    assert "aov" in names
    assert "reactivation_rate" in names
    assert "incremental_orders" in names
    # observed driver must be source-labeled store_observed
    rr_drv = next(d for d in out.drivers if d["name"] == "reactivation_rate")
    assert rr_drv["source"] == "store_observed"


def test_directional_with_observed_effect_no_prior_orders():
    """Directional play with observed effect but no orders_per_customer prior.

    discount_hygiene has no orders_per_customer in priors.yaml. The
    range collapses to a point (incremental_orders defaults to 1.0).
    """

    out = size_play(
        SizingInputs(
            play_id="discount_hygiene",
            evidence_class="directional",
            audience_size=300,
            aov=50.0,
            observed_effect=0.01,  # margin recovery
            observed_metric_name="margin_recovery_rate",
            observed_n=300,
            vertical="beauty",
        )
    )

    assert out.suppressed is False
    assert out.source == RevenueRangeSource.STORE_OBSERVED  # no prior used for inc_orders
    # Collapsed range: 300 * 0.01 * 1.0 * 50 = $150 across p10/p50/p90.
    assert out.p10 == out.p50 == out.p90 == 150.0


# ---------------------------------------------------------------------------
# T6.3 acceptance: cold-start suppression
# ---------------------------------------------------------------------------


def test_cold_start_suppression_for_measured():
    out = size_play(
        SizingInputs(
            play_id="winback_21_45",
            evidence_class="measured",
            audience_size=200,
            aov=80.0,
            observed_effect=0.04,
            observed_metric_name="reactivation_rate",
            vertical="beauty",
            cold_start=True,
        )
    )
    assert out.suppressed is True
    assert out.p10 is None and out.p50 is None and out.p90 is None
    assert out.source is None
    # Suppression reason is recorded for receipts.
    reasons = [d for d in out.drivers if d["name"] == "suppression_reason"]
    assert reasons and reasons[0]["reason"] == "cold_start"


def test_cold_start_suppression_for_targeting():
    out = size_play(
        SizingInputs(
            play_id="bestseller_amplify",
            evidence_class="targeting",
            audience_size=500,
            aov=60.0,
            vertical="beauty",
            cold_start=True,
        )
    )
    assert out.suppressed is True
    assert out.p50 is None


# ---------------------------------------------------------------------------
# T6.3 acceptance: targeting + non-causal prior suppression
# ---------------------------------------------------------------------------


def test_targeting_with_expert_prior_is_suppressed():
    """bestseller_amplify base_rate is 'expert' source_class -> suppressed."""
    out = size_play(
        SizingInputs(
            play_id="bestseller_amplify",
            evidence_class="targeting",
            audience_size=500,
            aov=60.0,
            vertical="beauty",
        )
    )
    assert out.suppressed is True
    assert out.source is None
    reasons = [d for d in out.drivers if d["name"] == "suppression_reason"]
    assert reasons and reasons[0]["reason"] == "targeting_non_causal_prior"
    # The base_rate prior is still recorded in drivers for the audit trail.
    base = [d for d in out.drivers if d["name"] == "base_rate"]
    assert base and base[0]["source_class"] == "expert"


def test_targeting_with_causal_prior_is_not_suppressed(tmp_path):
    """If the prior is causal, targeting plays are eligible (no suppression).

    No causal prior exists today; tests use a fixture YAML.
    """

    p = tmp_path / "priors.yaml"
    p.write_text(
        """
schema_version: "1.0.0"
last_reviewed: "2026-05-02"
plays:
  fancy_targeting_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: causal
      last_updated: "2026-05-02"
      applies_to: { vertical: beauty }
""",
        encoding="utf-8",
    )
    PL.clear_cache()
    PL.load_priors(p)  # warm cache to the test fixture path
    # Patch loader path so size_play uses the fixture.
    import src.sizing as SZ
    import src.priors_loader as PL2
    real_get_prior = PL2.get_prior

    def _fake(*args, **kwargs):
        kwargs["path"] = p
        return real_get_prior(*args, **kwargs)

    SZ.get_prior = _fake  # type: ignore[attr-defined]
    try:
        out = size_play(
            SizingInputs(
                play_id="fancy_targeting_play",
                evidence_class="targeting",
                audience_size=500,
                aov=60.0,
                vertical="beauty",
            )
        )
    finally:
        SZ.get_prior = real_get_prior  # type: ignore[attr-defined]

    assert out.suppressed is False
    assert out.source == RevenueRangeSource.VERTICAL_PRIOR
    # 500 * 0.10 * 1.0 * 60 = $3,000 (mid)
    assert abs(out.p50 - 3000.0) < 1.0


def test_targeting_unsuppressed_via_test_escape_hatch():
    """allow_targeting_unsuppressed=True bypasses T6.3 (tests-only)."""
    out = size_play(
        SizingInputs(
            play_id="bestseller_amplify",
            evidence_class="targeting",
            audience_size=500,
            aov=60.0,
            vertical="beauty",
            allow_targeting_unsuppressed=True,
        )
    )
    assert out.suppressed is False
    assert out.source == RevenueRangeSource.VERTICAL_PRIOR
    # 500 * 0.18 * 1.0 * 60 = $5,400 (mid for beauty bestseller_amplify)
    assert abs(out.p50 - 5400.0) < 1.0


# ---------------------------------------------------------------------------
# Hard suppression (audience / aov)
# ---------------------------------------------------------------------------


def test_zero_audience_suppressed():
    out = size_play(
        SizingInputs(
            play_id="winback_21_45",
            evidence_class="measured",
            audience_size=0,
            aov=80.0,
            observed_effect=0.04,
            vertical="beauty",
        )
    )
    assert out.suppressed is True
    reasons = [d for d in out.drivers if d["name"] == "suppression_reason"]
    assert reasons and reasons[0]["reason"] == "audience_zero"


def test_zero_aov_suppressed():
    out = size_play(
        SizingInputs(
            play_id="winback_21_45",
            evidence_class="measured",
            audience_size=100,
            aov=0.0,
            observed_effect=0.04,
            vertical="beauty",
        )
    )
    assert out.suppressed is True
    reasons = [d for d in out.drivers if d["name"] == "suppression_reason"]
    assert reasons and reasons[0]["reason"] == "aov_zero"


def test_no_observed_effect_no_prior_returns_suppressed():
    out = size_play(
        SizingInputs(
            play_id="onsite_funnel_watch",  # registry has no priors
            evidence_class="targeting",
            audience_size=100,
            aov=60.0,
            vertical="beauty",
        )
    )
    assert out.suppressed is True
    reasons = [d for d in out.drivers if d["name"] == "suppression_reason"]
    assert reasons and reasons[0]["reason"] == "no_prior_base_rate"


# ---------------------------------------------------------------------------
# T6.4 acceptance: drivers provenance
# ---------------------------------------------------------------------------


def test_drivers_are_named_and_source_labeled():
    """Every driver MUST carry a non-empty ``name`` and ``source``."""
    out = size_play(
        SizingInputs(
            play_id="winback_21_45",
            evidence_class="measured",
            audience_size=200,
            aov=80.0,
            observed_effect=0.04,
            observed_metric_name="reactivation_rate",
            observed_n=200,
            vertical="beauty",
        )
    )
    assert out.drivers
    for d in out.drivers:
        assert d.get("name"), f"missing name in driver: {d}"
        assert d.get("source"), f"missing source in driver: {d}"


def test_drivers_record_audience_and_aov_for_every_call():
    """audience_size and aov are always recorded as drivers."""
    inputs = SizingInputs(
        play_id="winback_21_45",
        evidence_class="measured",
        audience_size=150,
        aov=72.0,
        observed_effect=0.05,
        observed_metric_name="reactivation_rate",
        observed_n=150,
        vertical="beauty",
    )
    out = size_play(inputs)
    names = [d["name"] for d in out.drivers]
    assert names.count("audience_size") == 1
    assert names.count("aov") == 1


def test_drivers_for_targeting_with_causal_prior_carry_applies_to(tmp_path):
    p = tmp_path / "priors.yaml"
    p.write_text(
        """
schema_version: "1.0.0"
last_reviewed: "2026-05-02"
plays:
  another_targeting_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: causal
      last_updated: "2026-05-02"
      applies_to: { vertical: beauty }
""",
        encoding="utf-8",
    )
    PL.clear_cache()
    import src.sizing as SZ
    import src.priors_loader as PL2

    real = PL2.get_prior

    def _fake(*args, **kwargs):
        kwargs["path"] = p
        return real(*args, **kwargs)

    SZ.get_prior = _fake  # type: ignore[attr-defined]
    try:
        out = size_play(
            SizingInputs(
                play_id="another_targeting_play",
                evidence_class="targeting",
                audience_size=200,
                aov=50.0,
                vertical="beauty",
            )
        )
    finally:
        SZ.get_prior = real  # type: ignore[attr-defined]
    base = next(d for d in out.drivers if d["name"] == "base_rate")
    assert base["source"] == "vertical_prior"
    assert base["source_class"] == "causal"
    assert base["applies_to"] == {"vertical": "beauty"}


# ---------------------------------------------------------------------------
# Range invariant
# ---------------------------------------------------------------------------


def test_p10_le_p50_le_p90_for_non_suppressed():
    out = size_play(
        SizingInputs(
            play_id="winback_21_45",
            evidence_class="measured",
            audience_size=200,
            aov=80.0,
            observed_effect=0.04,
            observed_metric_name="reactivation_rate",
            observed_n=200,
            vertical="beauty",
        )
    )
    assert out.suppressed is False
    assert out.p10 is not None and out.p50 is not None and out.p90 is not None
    assert out.p10 <= out.p50 <= out.p90


# ---------------------------------------------------------------------------
# T6.6 shadow compare
# ---------------------------------------------------------------------------


def test_shadow_compare_records_legacy_and_v2():
    out = size_play(
        SizingInputs(
            play_id="winback_21_45",
            evidence_class="measured",
            audience_size=200,
            aov=80.0,
            observed_effect=0.04,
            observed_metric_name="reactivation_rate",
            observed_n=200,
            vertical="beauty",
        )
    )
    rec = shadow_compare(legacy_expected_dollars=2500.0, v2_range=out)
    assert rec["legacy_expected_dollars"] == 2500.0
    assert rec["v2_p50"] == out.p50
    assert rec["v2_source"] == "blend"
    assert rec["v2_suppressed"] is False
    # V2 p50 should be much smaller than the legacy heuristic on this play.
    assert rec["ratio_v2_over_legacy"] is not None
    assert rec["ratio_v2_over_legacy"] < 1.0


def test_shadow_compare_handles_suppressed():
    out = size_play(
        SizingInputs(
            play_id="bestseller_amplify",
            evidence_class="targeting",
            audience_size=500,
            aov=60.0,
            vertical="beauty",
        )
    )
    rec = shadow_compare(legacy_expected_dollars=10_000.0, v2_range=out)
    assert rec["v2_suppressed"] is True
    assert rec["v2_p50"] is None
    assert rec["ratio_v2_over_legacy"] is None
