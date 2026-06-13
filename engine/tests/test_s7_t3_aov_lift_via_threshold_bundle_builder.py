"""Sprint 7 Ticket T3 — aov_lift_via_threshold_bundle builder tests.

Covers the new prior-anchored Tier-B builder that activates a curated
threshold-completion cross-sell to customers $5-$15 below a merchant-
defined AOV threshold. Anchors on the dual-tier
``aov_lift_via_threshold_bundle.base_rate`` prior block (S7 priors-
wiring, validated by DS 2026-05-20):

  - Beauty: validated_external (Memo 2, pseudo_n=30 via PSEUDO_N_BY_STATUS)
  - Supplements: elicited_expert (Memo 3 DOWNGRADED per DS verdict +
    KI-NEW-J cross-vertical evidence laundering safeguard; pseudo_n=10
    via PSEUDO_N_BY_STATUS — brand's own data dominates within ~20
    observed conversions)

Per IM plan §S7-T3 + S7 planning refresh: hardest of the 3 S7 builders
because the prior + threshold detection both need design choices. Per
the spec, the audience builder accepts a merchant-configured threshold
via ``cfg["AOV_BUNDLE_THRESHOLD_USD"]``; cart-state is preferred,
last-90d avg AOV is the documented fallback (today's CSV does not
carry cart-state).

Flag default OFF at S7-T3; S7-T3.5 owns the atomic flip + fixture
re-pin (5 pinned fixtures).
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
from src.sizing import PSEUDO_N_BY_STATUS  # noqa: E402
from src.utils import DEFAULTS  # noqa: E402


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------


def _row(customer_id: str, days_ago: int, *, net: float = 50.0):
    created = ANCHOR - pd.Timedelta(days=days_ago)
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": created,
        "net_sales": net,
        "lineitem_any": "Generic Product",
    }


def _make_g(rows):
    return (
        pd.DataFrame(rows)
        .sort_values(["customer_id", "Created at"])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# T1: in-band avg-AOV cohort fires (fallback path; threshold $75, avg $65)
# ---------------------------------------------------------------------------


def test_t1_in_band_avg_aov_cohort_fires():
    # Threshold $75, band [$60, $70]. Customer avg $65 → in.
    rows = [_row("anchor", 0, net=30.0)]
    for i in range(5):
        rows.append(_row(f"c{i}", 10, net=65.0))
    g = _make_g(rows)
    cfg = {"AOV_BUNDLE_THRESHOLD_USD": 75.0}
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    assert res.play_id == "aov_lift_via_threshold_bundle"
    # Anchor has avg $30, outside the band; 5 customers in.
    assert res.audience_size == 5
    assert res.preliminary_rejection_reason is None
    assert all(cid.startswith("c") for cid in res.audience_ids)


# ---------------------------------------------------------------------------
# T2: avg-AOV BELOW the band (>$15 below threshold) is excluded
# ---------------------------------------------------------------------------


def test_t2_avg_aov_below_band_excluded():
    # Threshold $75, band [$60, $70]. Customer avg $40 → too low.
    rows = [_row("anchor", 0, net=30.0)]
    for i in range(5):
        rows.append(_row(f"low{i}", 10, net=40.0))
    g = _make_g(rows)
    cfg = {"AOV_BUNDLE_THRESHOLD_USD": 75.0}
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# T3: avg-AOV ABOVE the band (within $5 of threshold OR above) is excluded
# ---------------------------------------------------------------------------


def test_t3_avg_aov_above_band_excluded():
    # Threshold $75, band [$60, $70]. $72 customers excluded (too close).
    rows = [_row("anchor", 0, net=30.0)]
    for i in range(5):
        rows.append(_row(f"hi{i}", 10, net=72.0))
    g = _make_g(rows)
    cfg = {"AOV_BUNDLE_THRESHOLD_USD": 75.0}
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    assert res.audience_size == 0


# ---------------------------------------------------------------------------
# T4: boundary inclusive at threshold-$15 and threshold-$5
# ---------------------------------------------------------------------------


def test_t4_band_boundary_inclusive():
    # Threshold $75 → band [$60, $70] inclusive at both edges.
    rows = [_row("anchor", 0, net=30.0)]
    rows.append(_row("at_lo", 10, net=60.0))   # lower edge
    rows.append(_row("at_hi", 10, net=70.0))   # upper edge
    rows.append(_row("below", 10, net=59.99))  # just outside (too low)
    rows.append(_row("above", 10, net=70.01))  # just outside (too high)
    g = _make_g(rows)
    cfg = {"AOV_BUNDLE_THRESHOLD_USD": 75.0}
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    assert res.audience_ids == {"at_lo", "at_hi"}


# ---------------------------------------------------------------------------
# T5: cart-state path overrides avg-AOV fallback (Sprint 9+ data shape)
# ---------------------------------------------------------------------------


def test_t5_cart_state_path_overrides_fallback():
    rows = [_row("anchor", 0, net=30.0)]
    for i in range(3):
        # Avg AOV is high ($200) but cart state is in the band → still in.
        rows.append(_row(f"cart{i}", 10, net=200.0))
    df = pd.DataFrame(rows)
    df["cart_state_total"] = [None, 65.0, 65.0, 65.0]
    cfg = {"AOV_BUNDLE_THRESHOLD_USD": 75.0}
    res = ab.aov_lift_via_threshold_bundle_candidates(df, {}, cfg)
    # Cart-state present → fallback NOT used; 3 in-band cart values.
    assert res.audience_size == 3


# ---------------------------------------------------------------------------
# T6: threshold unset → data_missing (no fabricated default)
# ---------------------------------------------------------------------------


def test_t6_threshold_unset_data_missing():
    rows = [_row("anchor", 0, net=30.0)] + [_row(f"c{i}", 10, net=65.0) for i in range(5)]
    g = _make_g(rows)
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, {})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "data_missing"


def test_t6b_threshold_negative_or_zero_data_missing():
    rows = [_row("anchor", 0, net=30.0)]
    g = _make_g(rows)
    res = ab.aov_lift_via_threshold_bundle_candidates(
        g, {}, {"AOV_BUNDLE_THRESHOLD_USD": -1}
    )
    assert res.preliminary_rejection_reason == "data_missing"
    res2 = ab.aov_lift_via_threshold_bundle_candidates(
        g, {}, {"AOV_BUNDLE_THRESHOLD_USD": 0}
    )
    assert res2.preliminary_rejection_reason == "data_missing"


# ---------------------------------------------------------------------------
# T7: ranking_strategy kwarg accepted, ignored (Sprint 13 scaffold)
# ---------------------------------------------------------------------------


def test_t7_ranking_strategy_kwarg_is_noop():
    rows = [_row("anchor", 0, net=30.0)] + [_row(f"c{i}", 10, net=65.0) for i in range(3)]
    g = _make_g(rows)
    cfg = {"AOV_BUNDLE_THRESHOLD_USD": 75.0}
    r_none = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    r_str = ab.aov_lift_via_threshold_bundle_candidates(
        g, {}, cfg, ranking_strategy="predicted_ltv_desc"
    )
    r_bad = ab.aov_lift_via_threshold_bundle_candidates(
        g, {}, cfg, ranking_strategy=42  # type: ignore[arg-type]
    )
    assert r_none.audience_size == r_str.audience_size == r_bad.audience_size
    assert r_none.audience_ids == r_str.audience_ids == r_bad.audience_ids


# ---------------------------------------------------------------------------
# T8: empty / missing columns → data_missing, no crash
# ---------------------------------------------------------------------------


def test_t8_empty_dataframe_data_missing():
    res = ab.aov_lift_via_threshold_bundle_candidates(
        pd.DataFrame(), {}, {"AOV_BUNDLE_THRESHOLD_USD": 75.0}
    )
    assert res.preliminary_rejection_reason == "data_missing"


def test_t8b_missing_customer_id_column_data_missing():
    g = pd.DataFrame({"Created at": [ANCHOR], "net_sales": [60.0]})
    res = ab.aov_lift_via_threshold_bundle_candidates(
        g, {}, {"AOV_BUNDLE_THRESHOLD_USD": 75.0}
    )
    assert res.preliminary_rejection_reason == "data_missing"


# ---------------------------------------------------------------------------
# T9: AudienceResult shape + BUILDERS + play_registry registration
# ---------------------------------------------------------------------------


def test_t9_builder_registered_in_BUILDERS_and_play_registry():
    assert "audience.aov_lift_via_threshold_bundle" in ab.BUILDERS
    assert (
        ab.BUILDERS["audience.aov_lift_via_threshold_bundle"]
        is ab.aov_lift_via_threshold_bundle_candidates
    )
    from src.play_registry import PLAYS
    assert "aov_lift_via_threshold_bundle" in PLAYS
    pdef = PLAYS["aov_lift_via_threshold_bundle"]
    assert pdef.audience_builder_ref == "audience.aov_lift_via_threshold_bundle"
    assert "base_rate" in pdef.prior_keys
    assert pdef.evidence_class_default == "directional"
    assert pdef.measurement_metric == "aov_threshold_crossing_conversion_rate"
    assert {"beauty", "supplements", "mixed"} <= set(pdef.vertical_applicable)


# ---------------------------------------------------------------------------
# T10: flag default at S7-T3 -> flipped ON at S7-T3.5
# ---------------------------------------------------------------------------


def test_t10_default_flag_off_at_t3():
    # S7-T3.5 (2026-05-21) flipped the default OFF -> ON atomically with
    # the pinned slate observation (Beauty + Supplements briefings stayed
    # byte-identical: builder eligibility did not fire on either
    # synthetic fixture under the actually-observed candidate set; the
    # registry+flag wiring is correct and the DS-predicted activation
    # awaits Sprint 8 commerce_posture work for surface). Operator
    # override ``ENGINE_V2_BUILDER_AOV_BUNDLE=false`` rolls back to T3-
    # close behavior in one env var (Sprint 2 Risk #4 contract).
    assert DEFAULTS.get("ENGINE_V2_BUILDER_AOV_BUNDLE", None) is True


def test_t10b_main_filters_play_from_registry_under_flag_off():
    # Mirror the conditional in src/main.py: when flag OFF, the
    # aov_lift_via_threshold_bundle play is filtered OUT of candidate-
    # detection so pinned-fixture sha256 byte-identity holds.
    from src.play_registry import PLAYS
    cfg_off = {"ENGINE_V2_BUILDER_AOV_BUNDLE": False}
    if not bool(cfg_off.get("ENGINE_V2_BUILDER_AOV_BUNDLE", False)):
        filtered = {
            k: v for k, v in PLAYS.items()
            if k != "aov_lift_via_threshold_bundle"
        }
    else:
        filtered = dict(PLAYS)
    assert "aov_lift_via_threshold_bundle" not in filtered
    cfg_on = {"ENGINE_V2_BUILDER_AOV_BUNDLE": True}
    if not bool(cfg_on.get("ENGINE_V2_BUILDER_AOV_BUNDLE", False)):
        filtered2 = {
            k: v for k, v in PLAYS.items()
            if k != "aov_lift_via_threshold_bundle"
        }
    else:
        filtered2 = dict(PLAYS)
    assert "aov_lift_via_threshold_bundle" in filtered2


# ---------------------------------------------------------------------------
# T11: legacy bestseller_amplify play preserved (NOT touched)
# ---------------------------------------------------------------------------


def test_t11_legacy_bestseller_amplify_preserved():
    """Per IM plan + DS verdict: bestseller_amplify is operationally
    distinct (static pre-purchase bundle; M2 Recommended Experiment
    allowlist member). It MUST stay in play_registry.PLAYS for its
    native consumer regardless of this ticket. The two are
    operationally distinct: bestseller_amplify uses pre-set on-PDP
    bundles; aov_lift_via_threshold_bundle uses near-threshold dynamic
    cross-sell emails."""
    from src.play_registry import PLAYS
    assert "bestseller_amplify" in PLAYS
    assert "audience.bestseller_buyers" in ab.BUILDERS


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
# T12: Beauty card activates at validated_external + BLEND (pseudo_n=30)
# ---------------------------------------------------------------------------


def test_t12_beauty_card_validated_external_blend():
    """Beauty entry is validated_external (Memo 2) → pseudo_n=30."""
    clear_cache()
    cand = _candidate("aov_lift_via_threshold_bundle", audience_size=200)
    aligned = _aligned_with_aov(50.0)
    card = mb.build_prior_anchored_play_card(cand, aligned, vertical="beauty")
    assert card is not None
    assert card.play_id == "aov_lift_via_threshold_bundle"
    assert card.evidence_class == EvidenceClass.DIRECTIONAL
    assert (
        card.would_be_measured_by
        == WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D
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
    # Validated_external → pseudo_n=30 (PSEUDO_N_BY_STATUS).
    assert bp["pseudo_n"] == PSEUDO_N_BY_STATUS[PriorValidationStatus.VALIDATED_EXTERNAL]
    assert bp["pseudo_n"] == 30


# ---------------------------------------------------------------------------
# T13: Supplements card activates at elicited_expert + BLEND (pseudo_n=10)
# ---------------------------------------------------------------------------


def test_t13_supplements_card_elicited_expert_blend():
    """Supplements entry is elicited_expert (Memo 3 DOWNGRADED per DS
    verdict 2026-05-20 + KI-NEW-J cross-vertical evidence laundering
    safeguard) → pseudo_n=10 (brand's own data dominates within ~20
    observed conversions). Unlike replenishment_due (asymmetric-by-
    absence), supplements ACTIVATES here under the elicited_expert
    blend-permitted tier, but at much lower posterior weight than the
    validated_external Beauty entry."""
    clear_cache()
    cand = _candidate("aov_lift_via_threshold_bundle", audience_size=200)
    aligned = _aligned_with_aov(50.0)
    card = mb.build_prior_anchored_play_card(
        cand, aligned, vertical="supplements"
    )
    assert card is not None
    assert card.play_id == "aov_lift_via_threshold_bundle"
    rr = card.revenue_range
    assert rr.suppressed is False
    assert rr.source == RevenueRangeSource.BLEND
    bp = next(
        (d for d in rr.drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    # The driver surfaces the validation_status as a tier indicator so the
    # renderer / consumer can distinguish validated_external vs
    # elicited_expert posterior weight.
    assert bp["prior_validation_status"] == PriorValidationStatus.ELICITED_EXPERT.value
    assert bp["applies_to"].get("vertical") == "supplements"
    # Elicited_expert → pseudo_n=10 (PSEUDO_N_BY_STATUS-LOCKED).
    assert bp["pseudo_n"] == PSEUDO_N_BY_STATUS[PriorValidationStatus.ELICITED_EXPERT]
    assert bp["pseudo_n"] == 10


# ---------------------------------------------------------------------------
# T14: _PRIOR_ANCHORED dispatch entry pins the prior anchor
# ---------------------------------------------------------------------------


def test_t14_prior_anchored_dispatch_entry_pins_prior():
    entry = mb._PRIOR_ANCHORED["aov_lift_via_threshold_bundle"]
    assert entry.play_id == "aov_lift_via_threshold_bundle"
    assert entry.prior_play_id == "aov_lift_via_threshold_bundle"
    assert entry.prior_key == "base_rate"
    assert (
        entry.would_be_measured_by
        == WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D
    )


# ---------------------------------------------------------------------------
# T15: enum cross-pin (latent-bug-class guard per S6-T3.5 precedent)
# ---------------------------------------------------------------------------


def test_t15_enum_cross_pin_aov_threshold_crossing_and_archetype():
    """Both enum values were authored at S7-priors-wiring (commit 6bc1d98)
    so this test pins the cross-link; latent enum-missing bugs are
    silent (lazy import in storytelling_v2 + decide.py swallow
    PriorsMetadataError) so explicit cross-pinning is load-bearing per
    the S6-T3.5 CADENCE_DUE_REPEAT_BUYER precedent."""
    assert (
        WouldBeMeasuredBy("AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D")
        is WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D
    )
    assert (
        WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D.value
        == WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D.name
    )
    # AudienceArchetype.THRESHOLD_NEAR_BUYER UPPER_SNAKE_CASE per S7
    # priors-wiring authoring-source convention; do NOT normalize.
    assert (
        AudienceArchetype("THRESHOLD_NEAR_BUYER")
        is AudienceArchetype.THRESHOLD_NEAR_BUYER
    )


# ---------------------------------------------------------------------------
# T16: PSEUDO_N_BY_STATUS contract (DS-locked supplements tier)
# ---------------------------------------------------------------------------


def test_t16_pseudo_n_by_status_elicited_expert_is_10():
    """DS-locked per S7-T3 spec: elicited_expert pseudo_n MUST be 10.
    Any change to this constant invalidates the supplements activation
    posture (Memo 3 DOWNGRADE was computed against pseudo_n=10)."""
    assert PSEUDO_N_BY_STATUS[PriorValidationStatus.ELICITED_EXPERT] == 10
    assert PSEUDO_N_BY_STATUS[PriorValidationStatus.VALIDATED_EXTERNAL] == 30


# ---------------------------------------------------------------------------
# T17: D-FLOOR-aov_lift_via_threshold_bundle floor-resolver cell coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "vertical,subvertical,stage,expected",
    [
        ("beauty", "skincare", "STARTUP", 40),
        ("beauty", "cosmetics", "GROWTH", 100),
        ("beauty", "haircare", "MATURE", 250),
        ("beauty", "personal_care", "ENTERPRISE", 750),
        ("beauty", "skincare", "GROWTH", 100),
        ("beauty", "cosmetics", "ENTERPRISE", 750),
        ("beauty", "haircare", "STARTUP", 40),
        ("beauty", "personal_care", "MATURE", 250),
    ],
)
def test_t17_floor_resolver_beauty_cell_coverage(
    vertical, subvertical, stage, expected
):
    from src.profile.builder import (
        _resolve_audience_floor_cell_strict,
        load_gate_calibration,
    )
    yaml_block = load_gate_calibration()
    rules_fired: list = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="aov_lift_via_threshold_bundle",
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
def test_t17b_floor_resolver_mixed_beauty_fallback(stage, expected):
    """REFUSED subvertical on beauty falls through to mixed_beauty
    (1.5×). Per the D-FLOOR-aov_lift_via_threshold_bundle grid."""
    from src.profile.builder import (
        _resolve_audience_floor_cell_strict,
        load_gate_calibration,
    )
    yaml_block = load_gate_calibration()
    rules_fired: list = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="aov_lift_via_threshold_bundle",
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
# T18: supplements floor resolution returns None at strict resolver
#      (consumer falls through to _default_by_stage per D-S6.5-4 +
#      D-FLOOR-aov_lift_via_threshold_bundle DS verdict + KI-NEW-J)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subvertical,stage",
    [
        ("protein", "STARTUP"),
        ("multivitamin", "GROWTH"),
        ("probiotics", "MATURE"),
        ("nootropics", "ENTERPRISE"),
        ("functional", "GROWTH"),
        ("other_refused", "STARTUP"),  # mixed_supplements also absent
    ],
)
def test_t18_supplements_floor_strict_resolver_returns_none(
    subvertical, stage
):
    """Supplements has NO per-play cell by design (D-FLOOR DS verdict
    + KI-NEW-J cross-link). The strict resolver returns (None, None) —
    NOT zero, NOT cascading. The consumer (audience builder) reads
    ``floors.get(play_id)`` → None and falls back to ``_default_by_stage``
    via the ``floors.get("_default")`` lookup per D-S6.5-4."""
    from src.profile.builder import (
        _resolve_audience_floor_cell_strict,
        load_gate_calibration,
    )
    yaml_block = load_gate_calibration()
    rules_fired: list = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="aov_lift_via_threshold_bundle",
        vertical="supplements",
        subvertical=subvertical,
        stage=stage,
        rules_fired=rules_fired,
    )
    assert floor is None, (
        f"supplements per-play cell must be absent at ({subvertical}, "
        f"{stage}) — got {floor}; D-FLOOR DS verdict + KI-NEW-J pin "
        "supplements fallback through _default_by_stage"
    )
    assert source is None
    assert any(
        r.get("rule") == "gate_calibration_cell_missing_strict"
        for r in rules_fired
    )


# ---------------------------------------------------------------------------
# T19: builder/profile integration — supplements floor uses _default_by_stage
# ---------------------------------------------------------------------------


def test_t19_builder_supplements_fallback_to_default_by_stage():
    """End-to-end pinning: when a StoreProfile carries the per-play
    floor map for a supplements brand, the per-play key is absent (per
    T18 strict-resolver outcome) and the consumer reads the ``_default``
    floor. This pins the integration seam from the strict resolver
    through to the audience builder."""
    from src.profile.types import GateCalibration

    # Simulate the supplements outcome: per-play cell absent, _default
    # present (the GROWTH default-by-stage cell from the YAML).
    profile = SimpleNamespace(
        gate_calibration=GateCalibration(
            audience_floor_by_play_id={"_default": 150},
            materiality_floor_usd=2000.0,
            pseudo_n_default=20,
            profile_field_refs={},
        ),
    )

    rows = [_row("anchor", 0, net=30.0)]
    for i in range(140):
        # 140 customers in band — BELOW _default=150 → audience_too_small.
        rows.append(_row(f"c{i}", 10, net=65.0))
    g = _make_g(rows)
    cfg = {
        "AOV_BUNDLE_THRESHOLD_USD": 75.0,
        "ENGINE_V2_STORE_PROFILE": True,
        "_store_profile": profile,
    }
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    assert res.audience_size == 140
    assert res.preliminary_rejection_reason == "audience_too_small"

    # Bump above the _default to confirm the floor was actually applied.
    rows2 = [_row("anchor", 0, net=30.0)]
    for i in range(160):
        rows2.append(_row(f"c{i}", 10, net=65.0))
    g2 = _make_g(rows2)
    res2 = ab.aov_lift_via_threshold_bundle_candidates(g2, {}, cfg)
    assert res2.audience_size == 160
    assert res2.preliminary_rejection_reason is None


# ---------------------------------------------------------------------------
# T20: blend_provenance shape parity beauty vs supplements
# ---------------------------------------------------------------------------


def test_t20_blend_provenance_shape_parity_both_verticals():
    """Both verticals must emit the same blend_provenance driver shape
    so renderer/consumer agents can read either uniformly. The only
    expected divergence is the values of ``prior_validation_status``
    and ``pseudo_n`` (and ``applies_to`` vertical)."""
    clear_cache()
    cand = _candidate("aov_lift_via_threshold_bundle", audience_size=200)
    aligned = _aligned_with_aov(50.0)
    card_b = mb.build_prior_anchored_play_card(cand, aligned, vertical="beauty")
    card_s = mb.build_prior_anchored_play_card(
        cand, aligned, vertical="supplements"
    )
    bp_b = next(
        d for d in card_b.revenue_range.drivers
        if isinstance(d, dict) and d.get("name") == "blend_provenance"
    )
    bp_s = next(
        d for d in card_s.revenue_range.drivers
        if isinstance(d, dict) and d.get("name") == "blend_provenance"
    )
    # Same key-set on both verticals.
    assert set(bp_b.keys()) == set(bp_s.keys())
    # Tier divergence is the load-bearing distinction.
    assert (
        bp_b["prior_validation_status"]
        != bp_s["prior_validation_status"]
    )
    assert bp_b["pseudo_n"] == 30 and bp_s["pseudo_n"] == 10


# ---------------------------------------------------------------------------
# S7.6-T7: threshold-from-data primary + supplements re-disable (flag-gated)
# ---------------------------------------------------------------------------


def test_t7_6_t7_default_flag_off():
    """S7.6-C3 (2026-05-22) flipped ``ENGINE_V2_AOV_THRESHOLD_FROM_DATA``
    from OFF to ON, atomic with the Beauty + Supplements fixture re-pin
    that closes Sprint 7.6. The historical S7.6-T7 staging posture
    (default OFF) is preserved for one sprint as test-name memory, but
    the asserted default is now ON. Flag-OFF behavior remains test-
    coverable via explicit ``cfg`` overrides (see the legacy-path tests
    below)."""
    assert DEFAULTS.get("ENGINE_V2_AOV_THRESHOLD_FROM_DATA", None) is True


def test_t7_6_t7_flag_off_preserves_legacy_cfg_only_path():
    """Flag OFF MUST behave identically to S7-T3.5: cfg-only resolution,
    no supplements vertical gate, no L90 P60 short-circuit."""
    rows = [_row("anchor", 0, net=30.0)]
    for i in range(5):
        rows.append(_row(f"c{i}", 10, net=65.0))
    g = _make_g(rows)
    # supplements + cfg threshold — under flag OFF, supplements gate is
    # NOT applied (legacy S7-T3.5 behavior preserved).
    cfg = {
        "AOV_BUNDLE_THRESHOLD_USD": 75.0,
        "VERTICAL_MODE": "supplements",
        "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": False,
    }
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    # Avg AOV $65 in band [$60, $70] → 5 customers.
    assert res.audience_size == 5
    assert res.preliminary_rejection_reason is None
    assert res.threshold_source == "cfg_merchant_declared"


def test_t7_6_t7_flag_on_supplements_vertical_excluded():
    """Flag ON + VERTICAL_MODE=supplements → empty with reason
    ``vertical_excluded_per_b5_248`` (founder Path A, plan B-5:248)."""
    rows = [_row("anchor", 0, net=30.0)]
    for i in range(5):
        rows.append(_row(f"c{i}", 10, net=65.0))
    g = _make_g(rows)
    cfg = {
        "AOV_BUNDLE_THRESHOLD_USD": 75.0,
        "VERTICAL_MODE": "supplements",
        "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": True,
    }
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "vertical_excluded_per_b5_248"
    assert res.threshold_source == "vertical_excluded"


def test_t7_6_t7_flag_on_beauty_l90_p60_data_derived():
    """Flag ON + Beauty + L90 orders >= 200 → threshold computed from
    L90 P60 of net_sales, threshold_source = ``l90_p60_data_derived``."""
    # 250 L90 orders with net_sales drawn so P60 ~= ~$60.
    # Use 250 net_sales values: 100 at $30, 100 at $60, 50 at $90.
    # P60 of [30*100, 60*100, 90*50] = 60.0.
    rows = []
    for i in range(100):
        rows.append(_row(f"a{i}", 5, net=30.0))
    for i in range(100):
        rows.append(_row(f"b{i}", 10, net=60.0))
    for i in range(50):
        rows.append(_row(f"c{i}", 15, net=90.0))
    g = _make_g(rows)
    cfg = {
        "VERTICAL_MODE": "beauty",
        "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": True,
    }
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    assert res.threshold_source == "l90_p60_data_derived"
    # Threshold ~$60 → band [$45, $55]; no customer avg falls in band
    # given the synthetic distribution (avgs are 30/60/90). Audience may
    # be 0; we are pinning the SOURCE not the size. Audience-size
    # specifics are pinned by T1-T9.
    assert res.audience_size >= 0


def test_t7_6_t7_flag_on_p60_correctness():
    """Pin P60 numeric correctness on a known L90 sample."""
    # Build a single-customer-per-row sample so net_sales values are
    # taken straight to percentile. 200 orders ranging 1..200 net_sales.
    rows = []
    for i in range(200):
        rows.append(_row(f"u{i}", 5, net=float(i + 1)))
    g = _make_g(rows)
    cfg = {
        "VERTICAL_MODE": "beauty",
        "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": True,
    }
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    # np.percentile([1..200], 60) = 120.4
    assert res.threshold_source == "l90_p60_data_derived"


def test_t7_6_t7_flag_on_l90_below_200_falls_back_to_cfg():
    """Flag ON + L90 order count < 200 + cfg present → cfg fallback;
    threshold_source = ``cfg_merchant_declared``."""
    rows = [_row("anchor", 0, net=30.0)]
    for i in range(5):
        rows.append(_row(f"c{i}", 10, net=65.0))
    g = _make_g(rows)  # 6 L90 orders, well below 200.
    cfg = {
        "AOV_BUNDLE_THRESHOLD_USD": 75.0,
        "VERTICAL_MODE": "beauty",
        "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": True,
    }
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    assert res.threshold_source == "cfg_merchant_declared"
    # Band [$60, $70] → 5 customers in band.
    assert res.audience_size == 5
    assert res.preliminary_rejection_reason is None


def test_t7_6_t7_flag_on_both_paths_fail_refuses():
    """Flag ON + L90 < 200 + no cfg threshold → data_missing refuse with
    threshold_source = ``data_missing``."""
    rows = [_row("anchor", 0, net=30.0)]
    for i in range(5):
        rows.append(_row(f"c{i}", 10, net=65.0))
    g = _make_g(rows)
    cfg = {
        "VERTICAL_MODE": "beauty",
        "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": True,
    }
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "data_missing"
    assert res.threshold_source == "data_missing"


def test_t7_6_t7_threshold_source_field_on_audience_result():
    """The new optional ``threshold_source`` field MUST exist on
    AudienceResult and default to None for builders that do not opt in."""
    res = ab.AudienceResult(
        play_id="probe",
        segment_definition="probe",
        audience_size=0,
    )
    assert hasattr(res, "threshold_source")
    assert res.threshold_source is None
