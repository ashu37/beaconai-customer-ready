"""Sprint 7 Ticket T1 — discount_dependency_hygiene builder tests.

Covers the new prior-anchored Tier-B builder anchored on the Beauty-only
validated_external ``discount_dependency_hygiene.base_rate.beauty`` prior
(DS-validated 2026-05-20; Klaviyo H&B 2026 omnichannel benchmark;
KI-NEW-K envelope re-fit deferred to Sprint 8 calibration sweep — see
test docstring T11 caveat). Supplements ROUTES to PRIOR_UNVALIDATED
Considered via S7.5-T3 refusal logic (no supplements prior block by
design per DS Memo-4 REJECT verdict).

Flag default OFF at T1; S7-T1.5 owns the atomic flip + fixture re-pin.
Legacy ``discount_hygiene`` play_id is PRESERVED untouched for the M2
measured-margin pathway (KI-21 Recommended Experiment allowlist) per
founder Q1 default 2026-05-20.
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

from src import audience_builders as ab  # noqa: E402
from src import measurement_builder as mb  # noqa: E402
from src.engine_run import (  # noqa: E402
    EvidenceClass,
    RevenueRangeSource,
    WouldBeMeasuredBy,
)
from src.priors_loader import (  # noqa: E402
    AudienceArchetype,
    PriorValidationStatus,
    clear_cache,
)
from src.utils import DEFAULTS  # noqa: E402


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------


def _row(customer_id: str, days_ago: int, *, discount_rate: float = 0.0, net: float = 30.0):
    created = ANCHOR - pd.Timedelta(days=days_ago)
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": created,
        "net_sales": net,
        "discount_rate": float(discount_rate),
        "lineitem_any": "Generic Product",
    }


def _make_g(rows):
    return (
        pd.DataFrame(rows)
        .sort_values(["customer_id", "Created at"])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# T1: customer with 2/2 discounted orders is in the cohort
# ---------------------------------------------------------------------------


def test_t1_all_discounted_customer_in_cohort():
    rows = []
    # 3 customers with 100% discount fraction.
    for i in range(3):
        rows.append(_row(f"d{i}", 50, discount_rate=0.20))
        rows.append(_row(f"d{i}", 25, discount_rate=0.15))
    g = _make_g(rows)
    res = ab.discount_dependency_hygiene_candidates(g, {}, {})
    assert res.play_id == "discount_dependency_hygiene"
    assert res.audience_size == 3
    assert res.preliminary_rejection_reason is None
    assert res.audience_ids == {"d0", "d1", "d2"}


# ---------------------------------------------------------------------------
# T2: 50% boundary inclusive (>=0.5 fires)
# ---------------------------------------------------------------------------


def test_t2_fifty_percent_boundary_inclusive():
    # Customer "edge": 1 of 2 orders discounted -> frac = 0.5 -> INCLUDED.
    rows = [
        _row("edge", 60, discount_rate=0.20),
        _row("edge", 30, discount_rate=0.0),
    ]
    # Customer "low": 1 of 3 orders discounted -> frac = 0.333 -> EXCLUDED.
    rows.extend([
        _row("low", 70, discount_rate=0.20),
        _row("low", 40, discount_rate=0.0),
        _row("low", 10, discount_rate=0.0),
    ])
    g = _make_g(rows)
    res = ab.discount_dependency_hygiene_candidates(g, {}, {})
    assert res.audience_ids == {"edge"}


# ---------------------------------------------------------------------------
# T3: full-price-only customer excluded
# ---------------------------------------------------------------------------


def test_t3_full_price_only_customer_excluded():
    rows = [
        _row("fp", 50, discount_rate=0.0),
        _row("fp", 20, discount_rate=0.0),
    ]
    g = _make_g(rows)
    res = ab.discount_dependency_hygiene_candidates(g, {}, {})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# T4: NaN discount_rate treated as no discount (safe default)
# ---------------------------------------------------------------------------


def test_t4_nan_discount_rate_treated_as_no_discount():
    # Customer "nans": 3 orders, all discount_rate=NaN -> treated as
    # 0.0 -> frac = 0 -> EXCLUDED.
    rows = [
        {
            "Name": f"#nans-{d}",
            "customer_id": "nans",
            "Created at": ANCHOR - pd.Timedelta(days=d),
            "net_sales": 30.0,
            "discount_rate": float("nan"),
            "lineitem_any": "Generic Product",
        }
        for d in (50, 30, 10)
    ]
    g = _make_g(rows)
    res = ab.discount_dependency_hygiene_candidates(g, {}, {})
    assert "nans" not in res.audience_ids


# ---------------------------------------------------------------------------
# T5: ranking_strategy kwarg is accepted, validated, ignored (no-op)
# ---------------------------------------------------------------------------


def test_t5_ranking_strategy_kwarg_is_noop():
    rows = [
        _row("d0", 50, discount_rate=0.2),
        _row("d0", 25, discount_rate=0.2),
    ]
    g = _make_g(rows)
    r_none = ab.discount_dependency_hygiene_candidates(g, {}, {})
    r_str = ab.discount_dependency_hygiene_candidates(
        g, {}, {}, ranking_strategy="predicted_ltv_desc"
    )
    r_bad = ab.discount_dependency_hygiene_candidates(
        g, {}, {}, ranking_strategy=42  # type: ignore[arg-type]
    )
    assert r_none.audience_size == r_str.audience_size == r_bad.audience_size
    assert r_none.audience_ids == r_str.audience_ids == r_bad.audience_ids


# ---------------------------------------------------------------------------
# T6: AudienceResult shape contract
# ---------------------------------------------------------------------------


def test_t6_audience_result_shape():
    rows = [
        _row("d0", 50, discount_rate=0.2),
        _row("d0", 20, discount_rate=0.15),
    ]
    g = _make_g(rows)
    res = ab.discount_dependency_hygiene_candidates(g, {}, {})
    # M3 forbidden-fields contract — no stats, no revenue.
    assert hasattr(res, "audience_size")
    assert hasattr(res, "audience_ids")
    assert hasattr(res, "segment_definition")
    assert isinstance(res.audience_ids, set)
    assert isinstance(res.audience_size, int)
    # No p / q / effect / revenue / score fields.
    for forbidden in ("p_value", "q_value", "effect", "revenue", "score", "confidence"):
        assert not hasattr(res, forbidden)


# ---------------------------------------------------------------------------
# T7: empty / missing-column data_missing
# ---------------------------------------------------------------------------


def test_t7_empty_dataframe_data_missing():
    res = ab.discount_dependency_hygiene_candidates(pd.DataFrame(), {}, {})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "data_missing"


def test_t7b_missing_discount_rate_column_data_missing():
    g = pd.DataFrame({"customer_id": ["a"], "Created at": [ANCHOR]})
    res = ab.discount_dependency_hygiene_candidates(g, {}, {})
    assert res.preliminary_rejection_reason == "data_missing"


# ---------------------------------------------------------------------------
# T8: registered in BUILDERS + play_registry
# ---------------------------------------------------------------------------


def test_t8_builder_registered_in_BUILDERS_and_play_registry():
    assert "audience.discount_dependency_hygiene" in ab.BUILDERS
    assert (
        ab.BUILDERS["audience.discount_dependency_hygiene"]
        is ab.discount_dependency_hygiene_candidates
    )
    from src.play_registry import PLAYS
    assert "discount_dependency_hygiene" in PLAYS
    pdef = PLAYS["discount_dependency_hygiene"]
    assert pdef.audience_builder_ref == "audience.discount_dependency_hygiene"
    assert "base_rate" in pdef.prior_keys
    assert pdef.evidence_class_default == "directional"
    assert pdef.measurement_metric == "discount_dependency_hygiene_full_price_conversion_rate"
    # Beauty-only activation per DS Memo-4 REJECT for supplements.
    assert "beauty" in pdef.vertical_applicable
    assert "supplements" not in pdef.vertical_applicable


# ---------------------------------------------------------------------------
# T9: flag default ON post-S7-T1.5 (flip landed 2026-05-21)
# ---------------------------------------------------------------------------


def test_t9_default_flag_on_post_t1_5():
    # S7-T1.5 (2026-05-21) flipped the default OFF -> ON atomically with
    # the Beauty pinned slate re-pin. Operator override
    # ``ENGINE_V2_BUILDER_DISCOUNT_HYGIENE=false`` rolls back to T1-close
    # behavior in one env var (Sprint 2 Risk #4 contract).
    assert DEFAULTS.get("ENGINE_V2_BUILDER_DISCOUNT_HYGIENE", None) is True


def test_t9b_main_filters_play_from_registry_under_flag_off():
    # Mirror the conditional in src/main.py: when flag OFF, the
    # discount_dependency_hygiene play is filtered OUT of candidate-
    # detection so pinned-fixture sha256 byte-identity holds.
    from src.play_registry import PLAYS
    cfg_off = {"ENGINE_V2_BUILDER_DISCOUNT_HYGIENE": False}
    if not bool(cfg_off.get("ENGINE_V2_BUILDER_DISCOUNT_HYGIENE", False)):
        filtered = {
            k: v for k, v in PLAYS.items()
            if k != "discount_dependency_hygiene"
        }
    else:
        filtered = dict(PLAYS)
    assert "discount_dependency_hygiene" not in filtered
    cfg_on = {"ENGINE_V2_BUILDER_DISCOUNT_HYGIENE": True}
    if not bool(cfg_on.get("ENGINE_V2_BUILDER_DISCOUNT_HYGIENE", False)):
        filtered2 = {
            k: v for k, v in PLAYS.items()
            if k != "discount_dependency_hygiene"
        }
    else:
        filtered2 = dict(PLAYS)
    assert "discount_dependency_hygiene" in filtered2


# ---------------------------------------------------------------------------
# T10: legacy discount_hygiene play_id is PRESERVED (founder Q1 default 2026-05-20)
# ---------------------------------------------------------------------------


def test_t10_legacy_discount_hygiene_play_preserved():
    """Founder Q1 lock 2026-05-20: legacy ``discount_hygiene`` is the M2
    measured-margin pathway (KI-21 Recommended Experiment allowlist) and
    is operationally distinct from the new ``discount_dependency_hygiene``
    full-price-conversion play. Both MUST coexist in play_registry.PLAYS
    after S7-T1.
    """
    from src.play_registry import PLAYS
    assert "discount_hygiene" in PLAYS
    assert "discount_dependency_hygiene" in PLAYS
    # The two are independent play_ids; their PlayDefs must NOT be the
    # same instance.
    assert PLAYS["discount_hygiene"] is not PLAYS["discount_dependency_hygiene"]
    # Legacy stays with the legacy audience_builder_ref.
    assert PLAYS["discount_hygiene"].audience_builder_ref == "audience.discount_dependent_buyers"
    # The legacy audience builder function MUST still resolve.
    assert "audience.discount_dependent_buyers" in ab.BUILDERS


# ---------------------------------------------------------------------------
# Measurement-builder fixtures
# ---------------------------------------------------------------------------


def _candidate(play_id: str, audience_size: int, *, prelim=None):
    return SimpleNamespace(
        play_id=play_id,
        audience_size=audience_size,
        segment_definition=f"{play_id} test cohort",
        data_used=[],
        preliminary_rejection_reason=prelim,
        cold_start=False,
    )


def _aligned_with_aov(aov: float):
    return {"L28": {"aov": aov, "delta": {}, "p": {}, "meta": {}}}


# ---------------------------------------------------------------------------
# T11: Beauty path fires validated_external + BLEND
# ---------------------------------------------------------------------------


def test_t11_beauty_card_validated_external_blend():
    """Beauty path consumes the validated_external Beauty-only
    discount_dependency_hygiene.base_rate.beauty prior.

    KI-NEW-K caveat (envelope re-fit deferred to Sprint 8): today's
    range_p10=0.0120 / range_p90=0.0430 are text-derived from the source
    Klaviyo H&B 2026 memo, NOT re-fit from the Beta(0.66, 29.34) CDF.
    The Beta is J-shaped because alpha<1 at effective_n=30; re-fit at
    effective_n=60 (alpha=1.32, beta=58.68) to recover a unimodal
    envelope before Sprint 8 calibration. This test does NOT re-fit;
    it pins the values as authored at S7 priors-wiring.
    """
    clear_cache()
    cand = _candidate("discount_dependency_hygiene", audience_size=200)
    aligned = _aligned_with_aov(50.0)
    card = mb.build_prior_anchored_play_card(cand, aligned, vertical="beauty")
    assert card is not None
    assert card.play_id == "discount_dependency_hygiene"
    assert card.evidence_class == EvidenceClass.DIRECTIONAL
    assert (
        card.would_be_measured_by
        == WouldBeMeasuredBy.DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D
    )
    rr = card.revenue_range
    assert rr.suppressed is False
    assert rr.source == RevenueRangeSource.BLEND
    bp = next(
        (d for d in rr.drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    assert bp["prior_validation_status"] == PriorValidationStatus.VALIDATED_EXTERNAL.value
    assert bp["applies_to"].get("vertical") == "beauty"


# ---------------------------------------------------------------------------
# T12: supplements path returns None (no prior block — refused via PRIOR_UNVALIDATED)
# ---------------------------------------------------------------------------


def test_t12_supplements_returns_none_no_prior_block():
    """Supplements has NO discount_dependency_hygiene.base_rate block by
    design (DS Memo-4 REJECT verdict). When the resolver finds no
    matching prior, ``build_prior_anchored_play_card`` returns None —
    decide.py's PRIOR_UNVALIDATED refusal logic then routes the
    candidate to Considered via the standard S7.5-T3 path (when the
    upstream cohort survives detection at all under flag ON).
    """
    clear_cache()
    cand = _candidate("discount_dependency_hygiene", audience_size=200)
    aligned = _aligned_with_aov(50.0)
    card = mb.build_prior_anchored_play_card(
        cand, aligned, vertical="supplements"
    )
    assert card is None


# ---------------------------------------------------------------------------
# T13: enum cross-pin (S6-T3.5 latent-bug-class guard, S7-priors-wiring reuse)
# ---------------------------------------------------------------------------


def test_t13_enum_cross_pin_discount_dependency_hygiene():
    """Cross-pin the WouldBeMeasuredBy + AudienceArchetype enum members
    landed at S7-priors-wiring (commit 6bc1d98). Latent enum-missing
    bugs are silent (lazy import in storytelling_v2 + decide.py swallow
    PriorsMetadataError) so explicit cross-pinning is load-bearing per
    the S6-T3.5 CADENCE_DUE_REPEAT_BUYER precedent.
    """
    assert (
        WouldBeMeasuredBy("DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D")
        is WouldBeMeasuredBy.DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D
    )
    # A2 round-trip: value == name.
    assert (
        WouldBeMeasuredBy.DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D.value
        == WouldBeMeasuredBy.DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D.name
    )
    # AudienceArchetype DISCOUNT_CONDITIONED_REPEAT_BUYER is UPPER_SNAKE
    # (founder spec S7 provenance rule); do NOT migrate to lowercase.
    assert (
        AudienceArchetype("DISCOUNT_CONDITIONED_REPEAT_BUYER")
        is AudienceArchetype.DISCOUNT_CONDITIONED_REPEAT_BUYER
    )


# ---------------------------------------------------------------------------
# T14: _PRIOR_ANCHORED dispatch entry pins the prior anchor
# ---------------------------------------------------------------------------


def test_t14_prior_anchored_dispatch_entry_pins_prior():
    entry = mb._PRIOR_ANCHORED["discount_dependency_hygiene"]
    assert entry.play_id == "discount_dependency_hygiene"
    assert entry.prior_play_id == "discount_dependency_hygiene"
    assert entry.prior_key == "base_rate"
    assert (
        entry.would_be_measured_by
        == WouldBeMeasuredBy.DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D
    )
    assert entry.metric == "discount_dependency_hygiene_full_price_conversion_rate"


# ---------------------------------------------------------------------------
# T15: D-FLOOR-discount_dependency_hygiene floor-resolver cell coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "vertical,subvertical,stage,expected",
    [
        # Beauty subverticals (uniform per D-FLOOR-discount_dependency_hygiene)
        ("beauty", "skincare", "STARTUP", 40),
        ("beauty", "cosmetics", "GROWTH", 100),
        ("beauty", "haircare", "MATURE", 250),
        ("beauty", "personal_care", "ENTERPRISE", 750),
        ("beauty", "skincare", "GROWTH", 100),
        ("beauty", "cosmetics", "STARTUP", 40),
        ("beauty", "haircare", "ENTERPRISE", 750),
        ("beauty", "personal_care", "MATURE", 250),
    ],
)
def test_t15_floor_resolver_beauty_cell_coverage(vertical, subvertical, stage, expected):
    from src.profile.builder import (
        _resolve_audience_floor_cell_strict,
        load_gate_calibration,
    )
    yaml_block = load_gate_calibration()
    rules_fired: list = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="discount_dependency_hygiene",
        vertical=vertical,
        subvertical=subvertical,
        stage=stage,
        rules_fired=rules_fired,
    )
    assert floor == expected, (
        f"floor mismatch for ({vertical}, {subvertical}, {stage}): "
        f"got {floor}, expected {expected}"
    )
    assert source is not None


@pytest.mark.parametrize(
    "stage,expected",
    [
        ("STARTUP", 60),
        ("GROWTH", 150),
        ("MATURE", 375),
        ("ENTERPRISE", 1125),
    ],
)
def test_t15b_floor_resolver_mixed_beauty_fallback(stage, expected):
    """REFUSED beauty subvertical falls through to ``mixed_beauty`` row
    (1.5× per-subvertical cell)."""
    from src.profile.builder import (
        _resolve_audience_floor_cell_strict,
        load_gate_calibration,
    )
    yaml_block = load_gate_calibration()
    rules_fired: list = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="discount_dependency_hygiene",
        vertical="beauty",
        subvertical="other_refused",
        stage=stage,
        rules_fired=rules_fired,
    )
    assert floor == expected
    assert source is not None
    assert any(
        r.get("rule") == "gate_calibration_mixed_vertical_fallback"
        for r in rules_fired
    )


# ---------------------------------------------------------------------------
# T16: supplements floor returns None (asymmetric-no-cell, NOT zero, NOT cascade)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subvertical,stage",
    [
        ("protein", "STARTUP"),
        ("multivitamin", "GROWTH"),
        ("probiotics", "MATURE"),
        ("nootropics", "ENTERPRISE"),
        ("functional", "GROWTH"),
        ("other_refused", "STARTUP"),
        ("other_refused", "ENTERPRISE"),
    ],
)
def test_t16_supplements_floor_returns_none(subvertical, stage):
    """Per D-FLOOR-discount_dependency_hygiene: supplements has NO cell
    by design (DS Memo-4 REJECT verdict). The strict resolver returns
    ``(None, None)`` — NOT zero, NOT cascading to _default_by_stage —
    matching the D-FLOOR-replenishment_due supplements-deferred pattern.
    """
    from src.profile.builder import (
        _resolve_audience_floor_cell_strict,
        load_gate_calibration,
    )
    yaml_block = load_gate_calibration()
    rules_fired: list = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="discount_dependency_hygiene",
        vertical="supplements",
        subvertical=subvertical,
        stage=stage,
        rules_fired=rules_fired,
    )
    assert floor is None
    assert source is None
    assert any(
        r.get("rule") == "gate_calibration_cell_missing_strict"
        for r in rules_fired
    )


# ---------------------------------------------------------------------------
# T17: profile builder includes discount_dependency_hygiene in strict-resolver list
# ---------------------------------------------------------------------------


def test_t17_profile_builder_strict_resolver_includes_play():
    """derive_gate_calibration MUST iterate discount_dependency_hygiene
    in the strict-resolver play_id tuple (so a Beauty store's
    profile.gate_calibration.audience_floor_by_play_id surfaces the
    cell). Supplements stores will have the key omitted by design.
    """
    import inspect
    from src.profile import builder as pb
    src_text = inspect.getsource(pb.derive_gate_calibration)
    assert '"discount_dependency_hygiene"' in src_text
    assert '"replenishment_due"' in src_text
    assert '"cohort_journey_first_to_second"' in src_text


# ---------------------------------------------------------------------------
# T18: heavy-promo conditional bump is documented but DORMANT (founder Q surfaced)
# ---------------------------------------------------------------------------


def test_t18_heavy_promo_bump_dormant_no_commerce_posture_attribute():
    """Per D-FLOOR-discount_dependency_hygiene conditional rule: when
    store-level discount-fraction > 40%, floor BUMPS UP from base
    (40/100/250/750) to heavy-promo (80/200/500/1500). The bump logic
    is CURRENTLY DORMANT because ``StoreProfile`` does not yet carry a
    ``commerce_posture.discount_fraction`` attribute. This test pins
    the dormancy as INTENTIONAL — the bump lands alongside the profile
    attribute, not invented here. Founder Q surfaced at S7-T1 closeout.
    """
    from src.profile.types import StoreProfile
    # The attribute is INTENTIONALLY missing from the typed dataclass
    # surface at S7-T1. When it lands (a future ticket), the resolver
    # will gain the conditional bump.
    sample_fields = {f.name for f in StoreProfile.__dataclass_fields__.values()}
    assert "commerce_posture" not in sample_fields


# ---------------------------------------------------------------------------
# T19: BUILDERS map count grew by 1 (load-bearing for play_registry uniqueness)
# ---------------------------------------------------------------------------


def test_t19_builders_map_includes_both_legacy_and_new():
    """Legacy ``audience.discount_dependent_buyers`` and new
    ``audience.discount_dependency_hygiene`` must coexist in BUILDERS
    (they emit independent play_ids: ``discount_hygiene`` vs
    ``discount_dependency_hygiene``).
    """
    assert "audience.discount_dependent_buyers" in ab.BUILDERS
    assert "audience.discount_dependency_hygiene" in ab.BUILDERS
    # And the underlying functions must be distinct.
    assert (
        ab.BUILDERS["audience.discount_dependent_buyers"]
        is not ab.BUILDERS["audience.discount_dependency_hygiene"]
    )
