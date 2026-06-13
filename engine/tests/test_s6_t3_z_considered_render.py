"""S6-T3.z tests — merchant-facing Considered render pass + audience_floor
sensitivity surfacing on validated-path Recommended Now cards.

T3.z is render-layer only. The 5 pinned fixtures MUST stay byte-identical
under flag OFF (the legacy lede + legacy CSS hold when no producer
populates the new fields and no Recommended Now card carries a
``audience_floor_sensitivity`` driver that renders a non-empty branch).

These tests pin:

- The Considered cohort row, mechanism line, and PRIOR_UNVALIDATED
  honest-dollar copy as conditional render branches.
- The 3 audience_floor_sensitivity render branches (robust / floor-fragile
  / typical band) on Recommended Now cards.
- The new ``render_considered_section`` lede copy flips only when at
  least one Considered card carries a T3.z field.
- HTML escaping on the new branches.
- The byte-identity contract on all 5 pinned fixtures under flag OFF.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.engine_run import (
    Audience,
    EngineRun,
    EvidenceClass,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    RevenueRangeSource,
)
from src.storytelling_v2 import (
    CONSIDERED_LEDE_LEGACY,
    CONSIDERED_LEDE_T3Z,
    FLOOR_FRAGILE_SENSITIVITY_COPY,
    PRIOR_UNVALIDATED_NO_PROJECTION_COPY,
    render_considered_section,
    render_play_card,
    render_rejected_card,
)


# ---------------------------------------------------------------------------
# Considered render-pass branches
# ---------------------------------------------------------------------------


def _rej(
    *,
    play_id: str = "replenishment_due",
    reason_code: ReasonCode = ReasonCode.PRIOR_UNVALIDATED,
    audience_size=None,
    audience_definition=None,
    mechanism=None,
) -> RejectedPlay:
    return RejectedPlay(
        play_id=play_id,
        reason_code=reason_code,
        audience_size=audience_size,
        audience_definition=audience_definition,
        mechanism=mechanism,
    )


def test_considered_card_with_audience_size_renders_cohort_row():
    rej = _rej(
        audience_size=412,
        audience_definition="customers within +/-3d of next replenishment",
    )
    html = render_rejected_card(rej)
    assert 'class="play-card-aud play-card-aud--considered"' in html
    assert "<strong>412</strong> people" in html
    assert "customers within +/-3d of next replenishment" in html


def test_considered_card_audience_size_none_omits_cohort_row():
    html = render_rejected_card(_rej(audience_size=None))
    assert "play-card-aud--considered" not in html


def test_considered_card_audience_size_zero_omits_cohort_row():
    html = render_rejected_card(
        _rej(audience_size=0, audience_definition="some def")
    )
    assert "play-card-aud--considered" not in html


def test_considered_card_with_mechanism_renders_what_we_send():
    rej = _rej(
        audience_size=200,
        mechanism="Email a replenishment reminder 3 days before the predicted run-out.",
    )
    html = render_rejected_card(rej)
    assert "play-card__what-we-send" in html
    assert "<strong>What we&#x27;d send:</strong>" in html
    assert (
        "Email a replenishment reminder 3 days before the predicted run-out."
        in html
    )


def test_prior_unvalidated_renders_no_projection_copy():
    rej = _rej(reason_code=ReasonCode.PRIOR_UNVALIDATED, audience_size=300)
    html = render_rejected_card(rej)
    assert "play-card__no-projection" in html
    # Apostrophe is escaped by ``html.escape(..., quote=True)``.
    assert (
        "We&#x27;re not projecting dollars on this play until we measure "
        "outcomes from a campaign on your store." in html
    )


def test_non_prior_unvalidated_does_not_render_no_projection_copy():
    rej = _rej(reason_code=ReasonCode.NO_MEASURED_SIGNAL, audience_size=300)
    html = render_rejected_card(rej)
    assert "play-card__no-projection" not in html
    # Even the escaped form must be absent.
    assert "not projecting dollars" not in html


def test_considered_card_html_escapes_audience_definition_and_mechanism():
    rej = _rej(
        audience_size=100,
        audience_definition="cohort <script>alert('xss')</script>",
        mechanism="send <b>html</b> & be sneaky",
    )
    html = render_rejected_card(rej)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;html&lt;/b&gt;" in html
    assert "&amp;" in html


# ---------------------------------------------------------------------------
# render_considered_section lede flip
# ---------------------------------------------------------------------------


def _esc_for_html(s: str) -> str:
    # Mirror src.storytelling_v2._esc for assertion purposes.
    import html as _html

    return _html.escape(s, quote=True)


def test_considered_section_legacy_lede_when_no_t3z_fields():
    items = [
        RejectedPlay(
            play_id="first_to_second_purchase",
            reason_code=ReasonCode.NO_MEASURED_SIGNAL,
        )
    ]
    html = render_considered_section(items)
    assert _esc_for_html(CONSIDERED_LEDE_LEGACY) in html
    assert _esc_for_html(CONSIDERED_LEDE_T3Z) not in html


def test_considered_section_t3z_lede_when_any_card_has_t3z_fields():
    items = [
        RejectedPlay(
            play_id="first_to_second_purchase",
            reason_code=ReasonCode.NO_MEASURED_SIGNAL,
        ),
        _rej(audience_size=300),
    ]
    html = render_considered_section(items)
    assert _esc_for_html(CONSIDERED_LEDE_T3Z) in html
    assert _esc_for_html(CONSIDERED_LEDE_LEGACY) not in html


# ---------------------------------------------------------------------------
# Recommended Now audience_floor_sensitivity branches
# ---------------------------------------------------------------------------


def _measured_card_with_sensitivity_driver(
    *, p50_low, p50_high, p50=1500.0
) -> PlayCard:
    """Build a minimal validated-path-shaped MEASURED PlayCard carrying a
    T3.y ``audience_floor_sensitivity`` driver. T3.z reads the driver
    value; the renderer never recomputes the band.
    """
    drivers = [
        {
            "name": "audience_size",
            "source": "store_observed",
            "value": 356,
        },
        {
            "name": "audience_floor_sensitivity",
            "source": "computed",
            "value": {
                "floor_value": 200,
                "floor_minus_25pct": 150,
                "floor_plus_25pct": 250,
                "revenue_p50_at_floor": p50,
                "p50_low": p50_low,
                "p50_high": p50_high,
            },
            "notes": "if audience floor were +/-25%, revenue_p50 ...",
            "profile_field_ref": "gate_calibration.audience_floors.x.y.z",
        },
    ]
    return PlayCard(
        play_id="winback_dormant_cohort",
        evidence_class=EvidenceClass.MEASURED,
        confidence_label="Strong",
        audience=Audience(size=356, definition="dormant repeat"),
        revenue_range=RevenueRange(
            p10=800.0,
            p50=p50,
            p90=2900.0,
            source=RevenueRangeSource.BLEND,
            drivers=drivers,
            suppressed=False,
        ),
    )


def test_robust_collapse_omits_sensitivity_band():
    card = _measured_card_with_sensitivity_driver(
        p50_low=1686.59, p50_high=1686.59
    )
    html = render_play_card(card, scale=None)
    assert "play-card__sensitivity-edge" not in html
    assert "play-card-range-chip__sensitivity" not in html
    # And we explicitly do not surface "robust to" microcopy.
    assert "robust" not in html.lower()


def test_floor_fragile_renders_edge_warning_paragraph():
    card = _measured_card_with_sensitivity_driver(
        p50_low=0.0, p50_high=1050.0
    )
    html = render_play_card(card, scale=None)
    assert "play-card__sensitivity-edge" in html
    assert _esc_for_html(FLOOR_FRAGILE_SENSITIVITY_COPY) in html
    # Not the chip variant.
    assert "play-card-range-chip__sensitivity" not in html


def test_typical_band_renders_floor_sensitivity_chip():
    card = _measured_card_with_sensitivity_driver(
        p50_low=1200.0, p50_high=1900.0
    )
    html = render_play_card(card, scale=None)
    assert "play-card-range-chip__sensitivity" in html
    assert "Floor sensitivity:" in html
    assert "$1,200" in html
    assert "$1,900" in html


def test_recommended_now_card_without_driver_byte_identical_to_pre_t3z():
    """A MEASURED card with NO ``audience_floor_sensitivity`` driver in
    ``revenue_range.drivers`` must render exactly the pre-T3.z HTML
    (no extra <span>/<p>, no extra whitespace). T3.z is purely
    additive: the absence of the driver means the absence of the
    band.
    """
    card = PlayCard(
        play_id="winback_dormant_cohort",
        evidence_class=EvidenceClass.DIRECTIONAL,
        confidence_label="Emerging",
        audience=Audience(size=356, definition="dormant repeat"),
        revenue_range=RevenueRange(
            p10=800.0,
            p50=1500.0,
            p90=2900.0,
            source=RevenueRangeSource.BLEND,
            drivers=[{"name": "audience_size", "source": "store_observed", "value": 356}],
            suppressed=False,
        ),
    )
    html = render_play_card(card, scale=None)
    assert "play-card__sensitivity-edge" not in html
    assert "play-card-range-chip__sensitivity" not in html
    assert "Floor sensitivity" not in html


# ---------------------------------------------------------------------------
# Pinned-fixture byte-identity under flag OFF
# ---------------------------------------------------------------------------


_PINNED_FIXTURES = {
    # S7.6-C3 (2026-05-22): atomic re-pin with the
    # ``ENGINE_V2_AOV_THRESHOLD_FROM_DATA`` default flip from OFF to ON
    # (closes Sprint 7.6). Beauty AOV bundle now resolves threshold from
    # L90 P60 ($71.88 on the synthetic fixture); Supplements AOV bundle
    # routes through the explicit ``vertical_excluded_per_b5_248`` seam
    # per ARCHITECTURE_PLAN.md §III B-5 lines 248 + 257(c). Considered
    # membership unchanged on both fixtures; only AOV bundle
    # threshold_source and preliminary_rejection_reason provenance shifts.
    # M0 goldens (small_sm/mid_shopify/micro_coldstart) remain byte-
    # identical (Sprint 7.6 invariant). Prior S7.6-FIX Beauty sha:
    # 5afc4d62e965688624bc5bba091adcd8a0406758cc419ee546b14ce191bcc863.
    # Prior S7.6-FIX Supplements sha:
    # 0903071ee9646a9db24f44c9ae87e29a14873158f88dc4bd2e4ba192c79fc1da.
    # S7.6-T3.5 (2026-05-23): Beauty re-pinned after
    # ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE OFF -> ON atomic flip.
    # Supplements byte-identical; M0 goldens unchanged. Prior
    # S7.6-T2.5-close Beauty sha:
    # 1a5a35eb67898e6eeda8196bc588bc8e7c5c4e2198bb4d721bf6b5da76c17f44.
    # S7.6-T6.5 (2026-05-23): Beauty re-pinned after
    # ENGINE_V2_OBSERVED_ELIGIBILITY_GATE OFF -> ON atomic flip. 3-state
    # copy ladder activates ("Cohort signal dominates - " mature prefix on
    # winback / discount_hygiene / journey). Supplements byte-identical.
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
    # See test_s6_t3_y_audience_floor_sensitivity for full re-pin notes.
    # Prior S8-T0 Beauty sha:
    # fcd2924bc18d726fa18bf407c77ba433ba89a4563d3ad413a466b063c8eeb056.
    "tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html":
        "f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3",
    "tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html":
        "13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344",
    "tests/golden/small_sm/briefing.html":
        "40bf24ea3c3632fa717293c82f66ac074d5e765ed29009b3297d2088952278e6",
    "tests/golden/mid_shopify/briefing.html":
        "380b2c5d0aa6806d81a38666c63603781e904f4e10a9fdfff72430551152d81a",
    "tests/golden/micro_coldstart/briefing.html":
        "2191b251edffbb7814e28a872e66b69e3d9289e680f077daa6ccea6a2694b2fc",
}


@pytest.mark.parametrize(
    "rel_path,expected_sha",
    sorted(_PINNED_FIXTURES.items()),
)
def test_pinned_fixture_byte_identical_under_flag_off(rel_path, expected_sha):
    """All 5 pinned fixtures must remain byte-identical under flag OFF.

    T3.z adds new render branches behind field-presence guards; today's
    producers do not populate the new fields, so the pre-T3.z bytes are
    preserved. T3.5 owns the atomic re-pin at activation.
    """
    repo = Path(__file__).resolve().parents[1]
    p = repo / rel_path
    assert p.exists(), f"pinned fixture missing: {p}"
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    assert actual == expected_sha, (
        f"{rel_path}: sha256 drift\n  expected={expected_sha}\n  actual={actual}"
    )
