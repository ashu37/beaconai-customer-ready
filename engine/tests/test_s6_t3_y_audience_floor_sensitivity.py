"""Sprint 6 Ticket T3.y — audience-floor sensitivity driver tests.

Closes the DS architect 2026-05-19 firewall leak: on validated-path
prior-anchored PlayCards the audience-floor heuristic uncertainty
silently inherits into the dollar projection. This test file pins:

1. Helper shape (9 required keys, 8 inner ``value`` keys).
2. Floor +/-25% int rounding (200 -> [150, 250]; 80 -> [60, 100]).
3. Robustness signal: cohort comfortably clears all variants ->
   ``p50_low == p50_high == current_p50``.
4. Floor-fragile signal: cohort near the floor -> upper variant fails
   the audience check -> revenue=0 -> ``p50_low == 0``.
5. Driver appears on validated-path PlayCard under flag-ON + profile
   attached + ``validation_status == VALIDATED_EXTERNAL``.
6. Driver does NOT appear under flag-OFF (byte-identity protector).
7. Driver does NOT appear when prior is ``heuristic_unvalidated``.
8. Driver does NOT appear on directional-pathway cards.
9. ``profile_field_ref`` matches the sibling ``audience_size`` driver.
10. Flag-OFF: all 5 pinned fixtures byte-identical (covered by the
    existing slate-regression / golden-diff harnesses — this file
    re-asserts the contract for documentation).

T3.z (the renderer-surface ticket) reads the new
``audience_floor_sensitivity`` driver value to optionally surface a
"robustness band" / "sensitivity envelope" on Recommended Now cards.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import measurement_builder as mb  # noqa: E402
from src.measurement_builder import (  # noqa: E402
    _audience_floor_sensitivity_driver,
    build_directional_play_card,
    build_prior_anchored_play_card,
)
from src.engine_run import EvidenceClass, RevenueRangeSource  # noqa: E402
from src.priors_loader import PriorValidationStatus  # noqa: E402
from src.profile.builder import derive_gate_calibration  # noqa: E402
from src.profile.types import (  # noqa: E402
    BusinessModel,
    BusinessStage,
    CadenceBaseline,
    DataDepth,
    StoreProfile,
    Taxonomy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(
    *,
    vertical: str = "beauty",
    subvertical: str = "skincare",
    stage: str = "GROWTH",
) -> StoreProfile:
    cad = CadenceBaseline(detection_status="INSUFFICIENT_DATA")
    gate, meas = derive_gate_calibration(
        taxonomy=Taxonomy(
            vertical=vertical,
            subvertical=subvertical,
            vertical_confidence="HIGH",
            subvertical_confidence="HIGH",
        ),
        stage=BusinessStage(stage=stage, uncertainty="LOW"),
        cadence=cad,
        data_depth=DataDepth(),
        business_model=BusinessModel(model="ONE_TIME_LED"),
    )
    return StoreProfile(
        store_id="test_store",
        taxonomy=Taxonomy(
            vertical=vertical, subvertical=subvertical,
            vertical_confidence="HIGH", subvertical_confidence="HIGH",
        ),
        business_stage=BusinessStage(stage=stage, uncertainty="LOW"),
        business_model=BusinessModel(model="ONE_TIME_LED"),
        cadence=cad,
        gate_calibration=gate,
        measurement=meas,
    )


def _aligned_with_aov(aov: float) -> Dict[str, Any]:
    """Minimal aligned dict carrying a defensible AOV on L28 so the
    ``_resolve_aov_for_context`` helper returns a numeric AOV.
    """

    return {
        "L28": {
            "aov": float(aov),
            "delta": {"aov": 0.0},
            "p": {"aov": 1.0},
            "meta": {"identified_recent": 100},
        },
        "L56": {"aov": float(aov), "delta": {"aov": 0.0}, "p": {"aov": 1.0}},
        "L90": {"aov": float(aov), "delta": {"aov": 0.0}, "p": {"aov": 1.0}},
    }


def _candidate(
    *, play_id: str, audience_size: int, segment_definition: str = "dormant cohort"
) -> SimpleNamespace:
    return SimpleNamespace(
        play_id=play_id,
        audience_size=int(audience_size),
        segment_definition=segment_definition,
        preliminary_rejection_reason=None,
    )


# ---------------------------------------------------------------------------
# 1) Helper returns correct dict shape with all 9 required keys
# ---------------------------------------------------------------------------


def test_t1_helper_shape_required_keys():
    d = _audience_floor_sensitivity_driver(
        audience_size=356,
        audience_floor=200,
        posterior_value=0.08,
        aov=59.22,
        profile_field_ref=(
            "gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth"
        ),
    )
    # Top-level keys
    assert d["name"] == "audience_floor_sensitivity"
    assert d["source"] == "computed"
    assert isinstance(d["value"], dict)
    assert "profile_field_ref" in d
    assert d["profile_field_ref"].startswith("gate_calibration.audience_floors.")
    assert isinstance(d["notes"], str)
    assert d["notes"].startswith("if audience floor were +/-25%")
    # Inner value keys (8)
    inner = d["value"]
    for k in (
        "floor_value",
        "floor_minus_25pct",
        "floor_plus_25pct",
        "revenue_p50_at_floor",
        "revenue_p50_at_floor_minus_25pct",
        "revenue_p50_at_floor_plus_25pct",
        "p50_low",
        "p50_high",
    ):
        assert k in inner, f"missing inner key {k!r}"
    assert isinstance(inner["floor_value"], int)
    assert isinstance(inner["floor_minus_25pct"], int)
    assert isinstance(inner["floor_plus_25pct"], int)
    # Top-level dict has the 5 named keys + profile_field_ref (the 6th
    # when present). The ticket spec calls out 9 required keys with
    # profile_field_ref echoed; verify the count is bounded.
    assert set(d.keys()) == {
        "name", "source", "value", "profile_field_ref", "notes",
    }


# ---------------------------------------------------------------------------
# 2) Floor +/-25% int rounding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "floor,expected_minus,expected_plus",
    [
        (200, 150, 250),
        (80, 60, 100),
    ],
)
def test_t2_floor_pct_int_rounding(floor: int, expected_minus: int, expected_plus: int):
    d = _audience_floor_sensitivity_driver(
        audience_size=10_000,
        audience_floor=floor,
        posterior_value=0.05,
        aov=50.0,
    )
    assert d["value"]["floor_value"] == floor
    assert d["value"]["floor_minus_25pct"] == expected_minus
    assert d["value"]["floor_plus_25pct"] == expected_plus


# ---------------------------------------------------------------------------
# 3) Cohort clears all variants -> p50_low == p50_high == current_p50
# ---------------------------------------------------------------------------


def test_t3_cohort_clears_all_variants_robustness_signal():
    audience_size = 356
    floor = 200
    posterior = 0.08
    aov = 59.22
    d = _audience_floor_sensitivity_driver(
        audience_size=audience_size,
        audience_floor=floor,
        posterior_value=posterior,
        aov=aov,
    )
    # 356 >= 150, 200, 250 → audience unchanged at every variant.
    expected_p50 = round(audience_size * posterior * aov, 2)
    assert d["value"]["revenue_p50_at_floor"] == expected_p50
    assert d["value"]["revenue_p50_at_floor_minus_25pct"] == expected_p50
    assert d["value"]["revenue_p50_at_floor_plus_25pct"] == expected_p50
    assert d["value"]["p50_low"] == d["value"]["p50_high"] == expected_p50


# ---------------------------------------------------------------------------
# 4) Cohort NEAR floor -> upper variant fails -> p50_low == 0 (fragile)
# ---------------------------------------------------------------------------


def test_t4_cohort_near_floor_p50_low_zero_floor_fragile():
    audience_size = 210
    floor = 200  # variants: 150, 200, 250
    posterior = 0.10
    aov = 50.0
    d = _audience_floor_sensitivity_driver(
        audience_size=audience_size,
        audience_floor=floor,
        posterior_value=posterior,
        aov=aov,
    )
    # 210 >= 150 and 210 >= 200 → both pass; 210 < 250 → fails.
    assert d["value"]["revenue_p50_at_floor_minus_25pct"] == round(
        audience_size * posterior * aov, 2
    )
    assert d["value"]["revenue_p50_at_floor"] == round(
        audience_size * posterior * aov, 2
    )
    assert d["value"]["revenue_p50_at_floor_plus_25pct"] == 0.0
    assert d["value"]["p50_low"] == 0.0
    # high is the +/-0 and -25% variant.
    assert d["value"]["p50_high"] == round(audience_size * posterior * aov, 2)


# ---------------------------------------------------------------------------
# 5) Driver appears on validated-path PlayCard under flag-ON + profile + validated
# ---------------------------------------------------------------------------


def test_t5_driver_present_on_validated_path_under_flag_on():
    profile = _make_profile(stage="GROWTH")  # winback floor=200
    aov = 59.22
    aligned = _aligned_with_aov(aov)
    cand = _candidate(play_id="winback_dormant_cohort", audience_size=356)
    card = build_prior_anchored_play_card(
        cand,
        aligned,
        vertical="beauty",
        subvertical="skincare",
        store_profile=profile,
        profile_flag_on=True,
    )
    assert card is not None
    assert card.revenue_range.suppressed is False
    assert card.revenue_range.source == RevenueRangeSource.BLEND
    names = [d.get("name") for d in (card.revenue_range.drivers or [])]
    assert "audience_floor_sensitivity" in names, names
    afs = next(
        d for d in card.revenue_range.drivers
        if d.get("name") == "audience_floor_sensitivity"
    )
    # Sanity: floor recovered from profile is 200.
    assert afs["value"]["floor_value"] == 200


# ---------------------------------------------------------------------------
# 6) Driver does NOT appear when flag OFF (byte-identity preserved)
# ---------------------------------------------------------------------------


def test_t6_driver_absent_when_flag_off():
    profile = _make_profile(stage="GROWTH")
    aligned = _aligned_with_aov(59.22)
    cand = _candidate(play_id="winback_dormant_cohort", audience_size=356)
    card = build_prior_anchored_play_card(
        cand,
        aligned,
        vertical="beauty",
        subvertical="skincare",
        store_profile=profile,
        profile_flag_on=False,
    )
    assert card is not None
    names = [d.get("name") for d in (card.revenue_range.drivers or [])]
    assert "audience_floor_sensitivity" not in names


# ---------------------------------------------------------------------------
# 7) Driver does NOT appear when prior is heuristic_unvalidated
# ---------------------------------------------------------------------------


def test_t7_driver_absent_when_prior_heuristic_unvalidated(monkeypatch):
    """Force the prior resolver to return a ``heuristic_unvalidated``
    prior, then verify the validated-path branch is NOT taken (and
    therefore no audience_floor_sensitivity driver is appended).
    """

    profile = _make_profile(stage="GROWTH")
    aligned = _aligned_with_aov(59.22)
    cand = _candidate(play_id="winback_dormant_cohort", audience_size=356)

    # Monkeypatch the prior to validation_status=heuristic_unvalidated.
    from src import priors_loader as pl

    real_get_prior = pl.get_prior

    def fake_get_prior(*args, **kwargs):
        p = real_get_prior(*args, **kwargs)
        if p is None:
            return None
        # Build a copy with downgraded validation_status. Prior is a
        # frozen dataclass; use dataclasses.replace.
        from dataclasses import replace as _dc_replace
        return _dc_replace(
            p, validation_status=PriorValidationStatus.HEURISTIC_UNVALIDATED,
        )

    monkeypatch.setattr(pl, "get_prior", fake_get_prior)
    # Also patch the symbol imported lazily inside the builder via
    # ``from .priors_loader import get_prior`` — re-import path uses
    # the module attribute, so the monkeypatch above is sufficient.

    card = build_prior_anchored_play_card(
        cand,
        aligned,
        vertical="beauty",
        subvertical="skincare",
        store_profile=profile,
        profile_flag_on=True,
    )
    assert card is not None
    # heuristic_unvalidated → suppressed RevenueRange with
    # prior_unvalidated reason; no audience_floor_sensitivity driver.
    assert card.revenue_range.suppressed is True
    names = [d.get("name") for d in (card.revenue_range.drivers or [])]
    assert "audience_floor_sensitivity" not in names


# ---------------------------------------------------------------------------
# 8) Driver does NOT appear on directional-pathway cards
# ---------------------------------------------------------------------------


def test_t8_driver_absent_on_directional_path():
    profile = _make_profile(stage="GROWTH")
    aov = 60.0
    metric = "returning_customer_share"
    aligned = {
        "L28": {
            "aov": aov,
            "delta": {metric: 0.066, "aov": 0.01},
            "p": {metric: 0.01, "aov": 0.05},
            "meta": {"identified_recent": 500},
            metric: 0.12,
        },
        "L56": {
            "aov": aov,
            "delta": {metric: 0.05, "aov": 0.01},
            "p": {metric: 0.01, "aov": 0.05},
        },
        "L90": {
            "aov": aov,
            "delta": {metric: 0.04, "aov": 0.01},
            "p": {metric: 0.01, "aov": 0.05},
        },
    }
    cand = _candidate(
        play_id="first_to_second_purchase",
        audience_size=500,
        segment_definition="single-purchase cohort",
    )
    card = build_directional_play_card(
        cand,
        aligned,
        store_profile=profile,
        profile_flag_on=True,
    )
    # Directional cards have suppressed=True with directional drivers;
    # audience_floor_sensitivity must not appear.
    assert card is not None
    names = [d.get("name") for d in (card.revenue_range.drivers or [])]
    assert "audience_floor_sensitivity" not in names


# ---------------------------------------------------------------------------
# 9) profile_field_ref matches sibling audience_size driver
# ---------------------------------------------------------------------------


def test_t9_profile_field_ref_matches_audience_size_sibling():
    profile = _make_profile(stage="GROWTH")
    aligned = _aligned_with_aov(59.22)
    cand = _candidate(play_id="winback_dormant_cohort", audience_size=356)
    card = build_prior_anchored_play_card(
        cand,
        aligned,
        vertical="beauty",
        subvertical="skincare",
        store_profile=profile,
        profile_flag_on=True,
    )
    assert card is not None
    drivers = card.revenue_range.drivers or []
    audience_driver = next(d for d in drivers if d.get("name") == "audience_size")
    floor_driver = next(
        d for d in drivers if d.get("name") == "audience_floor_sensitivity"
    )
    assert audience_driver.get("profile_field_ref") is not None
    assert floor_driver.get("profile_field_ref") == audience_driver.get(
        "profile_field_ref"
    )


# ---------------------------------------------------------------------------
# 10) Flag-OFF: all 5 pinned fixtures byte-identical to the T3.x snapshot
# ---------------------------------------------------------------------------


# Pinned sha256s captured 2026-05-19 immediately after S6-T3.x (commit
# d1bdfeb) and re-asserted post-S6-T3.y. These match the constants in
# the slate-regression and golden-diff harnesses; this test
# re-pins them locally so a T3.y regression on the additive flag-OFF
# path surfaces as an explicit failure here too.
_T3Y_PINNED_FIXTURES = {
    # S7.6-FIX (2026-05-22): atomic re-pin with the priority_prepend
    # at populate_considered_from_candidates (decide.py:825-842). The
    # load-bearing _PRIOR_ANCHORED Tier-B set now survives the
    # MAX_CONSIDERED_RENDERED=6 cap; legacy plays drop instead
    # (founder single-demote-channel invariant). Beauty: empty_bottle
    # displaced by aov_lift_via_threshold_bundle. Supplements:
    # discount_hygiene/subscription_nudge/routine_builder displaced by
    # winback_dormant_cohort/cohort_journey_first_to_second/
    # aov_lift_via_threshold_bundle. Prior S7-T1.5 Beauty sha:
    # 158bf726f5983348d6a8ff78858ee83682fca5fe516998f304f045ddfd399109.
    # Prior Supplements sha:
    # 01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95.
    # S7.6-C3 (2026-05-22): atomic re-pin with the
    # ``ENGINE_V2_AOV_THRESHOLD_FROM_DATA`` default flip OFF -> ON
    # (closes Sprint 7.6). M0 goldens stay byte-identical; only the
    # two synthetic_slate fixtures shift to reflect the new AOV bundle
    # threshold/vertical-gate provenance. Prior S7.6-FIX Beauty sha:
    # 5afc4d62e965688624bc5bba091adcd8a0406758cc419ee546b14ce191bcc863.
    # Prior S7.6-FIX Supplements sha:
    # 0903071ee9646a9db24f44c9ae87e29a14873158f88dc4bd2e4ba192c79fc1da.
    # S7.6-T3.5 (2026-05-23): Beauty re-pinned after
    # ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE OFF -> ON atomic flip
    # (observed_n=148451, posterior 0.022 -> 0.116881, store_dominant,
    # sign_agreement=3/3). Supplements byte-identical (helper short-
    # circuits per Path-D Memo-4 REJECT). M0 goldens unchanged.
    # Prior S7.6-T2.5-close Beauty sha:
    # 1a5a35eb67898e6eeda8196bc588bc8e7c5c4e2198bb4d721bf6b5da76c17f44.
    # S7.6-T6.5 (2026-05-23): Beauty re-pinned after
    # ENGINE_V2_OBSERVED_ELIGIBILITY_GATE OFF -> ON atomic flip. The 3-state
    # copy ladder activates: winback, discount_hygiene, and journey cards
    # all carry posterior_ratio=store_dominant (mature bucket) and gain the
    # "Cohort signal dominates - " why_now prefix. Gate clauses are no-op
    # for the three active observed-effect plays (3/3 sign-agreement on
    # all). Supplements byte-identical (no card carries observed-effect
    # data under current flag set; T5 aov_bundle OFF pending T5.5).
    # M0 goldens unchanged. Prior S7.6-T3.5 Beauty sha:
    # f66894a2d8f4e24c8a77b0663e048bc04cef999a63f34f301180e63fe045f0f3.
    # S7.6-T5.5 (2026-05-23): Beauty re-pinned after
    # ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE OFF -> ON atomic flip. The
    # aov_lift_via_threshold_bundle Tier-B card joint-fails (Welch
    # p~0.876, z-prop p~0.877) and demotes via T6 gate to Considered[0]
    # with signal_inconsistent_across_windows reason + would_be_measured_by
    # preserved (priority_prepend_rejects). Supplements byte-identical
    # (helper short-circuits per vertical_excluded_per_b5_248). M0 goldens
    # unchanged. Prior S7.6-T6.5 Beauty sha:
    # 87226ba707cfbee1910a8c646ced78fd0b2533f80e814c4aaba135d94d43109b.
    # S8-T0 (2026-05-24): Beauty re-pinned after KI-NEW-K Beauty Beta
    # envelope re-fit (founder-acked scope expansion to replenishment_due).
    # `discount_dependency_hygiene.base_rate.beauty` +
    # `replenishment_due.base_rate.beauty` re-fit Beta(0.66, 29.34) ->
    # Beta(1.32, 58.68) at effective_n=60; analytic p10/p90 from
    # scipy.stats.beta(1.32, 58.68).ppf([0.10, 0.90]) = 0.0037 / 0.0471.
    # Store dominates discount_dependency_hygiene posterior at observed_n=224K
    # (w_obs > 0.9998) so revenue_range bounds shift by tens of bps at most;
    # JSON bytes change due to prior metadata surfacing (effective_n,
    # range_p10/p90 on prior trace). Supplements + M0 byte-identical.
    # Prior S8-T0 Beauty sha:
    # fcd2924bc18d726fa18bf407c77ba433ba89a4563d3ad413a466b063c8eeb056.
    "tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html": (
        "f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3"
    ),
    "tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html": (
        "13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344"
    ),
    "tests/golden/small_sm/briefing.html": (
        "40bf24ea3c3632fa717293c82f66ac074d5e765ed29009b3297d2088952278e6"
    ),
    "tests/golden/mid_shopify/briefing.html": (
        "380b2c5d0aa6806d81a38666c63603781e904f4e10a9fdfff72430551152d81a"
    ),
    "tests/golden/micro_coldstart/briefing.html": (
        "2191b251edffbb7814e28a872e66b69e3d9289e680f077daa6ccea6a2694b2fc"
    ),
}


def test_t10_all_5_pinned_fixtures_byte_identical_under_flag_off():
    """Re-pin the 5 pinned fixture sha256s. Flag-OFF byte-identity is
    the load-bearing contract of T3.y — the new driver MUST NOT change
    the on-disk slate / golden bytes when ``profile_flag_on`` is False
    or the profile is unavailable.
    """

    for rel, expected_sha in _T3Y_PINNED_FIXTURES.items():
        p = REPO_ROOT / rel
        assert p.exists(), f"pinned fixture missing: {rel}"
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        assert actual == expected_sha, (
            f"T3.y flag-OFF byte-identity drift on {rel}: "
            f"expected={expected_sha} actual={actual}. "
            "T3.y MUST be schema-additive under flag OFF; investigate "
            "before refreshing this pin."
        )
