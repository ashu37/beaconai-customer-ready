"""Sprint 7.6 Ticket T6 --- observed-effect eligibility gate + 3-state copy ladder.

Verifies:

- Predicate Clause 1 (sign-agreement): ``observed_n > min_eligibility_n``
  AND ``sign_agreement_count < 2`` downgrades to Considered with
  :data:`ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS`.
- Predicate Clause 2 (DS amendment, joint-p<0.10): for builders that
  stash ``*_band`` windows, the L28 AND L28_band p-values must BOTH
  be present and ``< 0.10``. Either failing → downgrade.
- Joint clause is a NO-OP for builders without ``*_band`` stash
  (T1 / T2 / T3 / T4 — pin per-builder flag independence).
- Cold-start (``observed_n=0`` or ``n <= floor``) → gate is no-op,
  ``why_now`` byte-identical to flag-OFF (cold ladder state).
- 3-state copy ladder by ``posterior_ratio``:
  cold (<0.2) → why_now unchanged;
  accumulating ([0.2, 0.6)) → "Cohort signal is accumulating — " prefix;
  mature (>=0.6) → "Cohort signal dominates — " prefix.
- Flag-OFF path is a strict no-op: kept = input, refused = [],
  why_now identical.
- Cards without ``blend_provenance`` driver (legacy / non-prior-anchored)
  pass through unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from src import decide as decide_mod  # noqa: E402
from src.engine_run import (  # noqa: E402
    Audience,
    EvidenceClass,
    Measurement,
    PlayCard,
    ReasonCode,
    RevenueRange,
    RevenueRangeSource,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _card(
    play_id: str,
    *,
    why_now: str = "Audience X over window Y.",
    blend_prov: dict | None = None,
    suppressed: bool = False,
) -> PlayCard:
    """Build a minimal PlayCard with a ``blend_provenance`` driver."""

    drivers: list[dict] = []
    if blend_prov is not None:
        drivers.append({"name": "blend_provenance", **blend_prov})
    rr = RevenueRange(
        p10=1.0 if not suppressed else None,
        p50=2.0 if not suppressed else None,
        p90=3.0 if not suppressed else None,
        source=RevenueRangeSource.BLEND if not suppressed else None,
        drivers=drivers,
        suppressed=suppressed,
    )
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.DIRECTIONAL,
        confidence_label="Emerging",
        audience=Audience(
            id="a", definition="seg", size=500, fraction_of_base=None
        ),
        measurement=Measurement(
            metric="m",
            observed_effect=None,
            n=500,
            primary_window="L28",
            consistency_across_windows=None,
            p_internal=None,
        ),
        revenue_range=rr,
    )


def _single_test_stash(
    *,
    obs_n: int,
    sign_agreement_count: int,
    pseudo_n: int = 100,
) -> dict:
    """Single-test (T1/T2/T3/T4) stash --- no ``*_band`` legs."""

    return {
        "source": "bayesian_blend",
        "observed_n": obs_n,
        "observed_k": int(obs_n * 0.2),
        "pseudo_n": pseudo_n,
        "observed_sign_agreement_count": sign_agreement_count,
        "observed_dominant_sign": 1,
        "observed_windows": {
            "L28": {"k": 10, "n": 50, "effect": 0.1, "p_value": 0.04, "sign": 1, "method": "z_pooled"},
            "L56": {"k": 12, "n": 60, "effect": 0.05, "p_value": 0.20, "sign": 1, "method": "z_pooled"},
            "L90": {"k": 15, "n": 80, "effect": 0.02, "p_value": 0.30, "sign": 0, "method": "z_pooled"},
        },
    }


def _band_stash(
    *,
    obs_n: int,
    sign_agreement_count: int,
    l28_p: float | None,
    l28_band_p: float | None,
    pseudo_n: int = 100,
) -> dict:
    """Band-stash (T5 aov_bundle) --- includes ``L*_band`` legs."""

    return {
        "source": "bayesian_blend",
        "observed_n": obs_n,
        "observed_k": int(obs_n * 0.3),
        "pseudo_n": pseudo_n,
        "observed_sign_agreement_count": sign_agreement_count,
        "observed_dominant_sign": 1,
        "observed_windows": {
            "L28": {"k": None, "n": 200, "effect": 1.5, "p_value": l28_p, "sign": 1, "method": "welch_t"},
            "L56": {"k": None, "n": 250, "effect": 1.2, "p_value": 0.15, "sign": 1, "method": "welch_t"},
            "L90": {"k": None, "n": 300, "effect": 0.8, "p_value": 0.20, "sign": 1, "method": "welch_t"},
            "L28_band": {"k": 60, "n": 200, "effect": 0.05, "p_value": l28_band_p, "sign": 1, "method": "z_pooled"},
            "L56_band": {"k": 70, "n": 250, "effect": 0.04, "p_value": 0.18, "sign": 1, "method": "z_pooled"},
            "L90_band": {"k": 80, "n": 300, "effect": 0.03, "p_value": 0.22, "sign": 1, "method": "z_pooled"},
        },
    }


# ---------------------------------------------------------------------------
# Flag-OFF path: strict no-op
# ---------------------------------------------------------------------------


def test_flag_off_is_strict_noop():
    card = _card(
        "aov_lift_via_threshold_bundle",
        blend_prov=_band_stash(
            obs_n=500, sign_agreement_count=3, l28_p=None, l28_band_p=None
        ),
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=False, min_eligibility_n=30
    )
    assert refused == []
    assert len(kept) == 1


def test_flag_off_card_without_blend_provenance_passes():
    card = _card("legacy_play", blend_prov=None)
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=False, min_eligibility_n=30
    )
    assert refused == []
    assert kept == [card]


# ---------------------------------------------------------------------------
# Clause 1 — sign-agreement (applies to all builders)
# ---------------------------------------------------------------------------


def test_clause1_sign_agreement_fail_downgrades_single_test():
    """T1/T3/T4 single-test builder with n>floor, sign_agreement_count<2."""

    card = _card(
        "winback_dormant_cohort",
        blend_prov=_single_test_stash(obs_n=200, sign_agreement_count=1),
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    assert kept == []
    assert len(refused) == 1
    assert refused[0].reason_code == ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS
    assert refused[0].play_id == "winback_dormant_cohort"


def test_clause1_sign_agreement_pass_keeps_card():
    card = _card(
        "winback_dormant_cohort",
        blend_prov=_single_test_stash(obs_n=200, sign_agreement_count=3),
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    assert refused == []
    assert len(kept) == 1
    assert kept[0].play_id == "winback_dormant_cohort"


# ---------------------------------------------------------------------------
# Clause 2 — joint p<0.10 (DS amendment, band-stash builders only)
# ---------------------------------------------------------------------------


def test_clause2_joint_pass_keeps_card():
    card = _card(
        "aov_lift_via_threshold_bundle",
        blend_prov=_band_stash(
            obs_n=200, sign_agreement_count=3, l28_p=0.04, l28_band_p=0.03
        ),
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    assert refused == []
    assert len(kept) == 1


def test_clause2_only_welch_passes_downgrades():
    """Welch p=0.04 < 0.10 but band p=0.20 >= 0.10 → joint fail."""

    card = _card(
        "aov_lift_via_threshold_bundle",
        blend_prov=_band_stash(
            obs_n=200, sign_agreement_count=3, l28_p=0.04, l28_band_p=0.20
        ),
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    assert kept == []
    assert len(refused) == 1
    assert refused[0].reason_code == ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS


def test_clause2_only_band_passes_downgrades():
    card = _card(
        "aov_lift_via_threshold_bundle",
        blend_prov=_band_stash(
            obs_n=200, sign_agreement_count=3, l28_p=0.30, l28_band_p=0.03
        ),
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    assert kept == []
    assert refused[0].reason_code == ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS


def test_clause2_none_p_value_downgrades():
    """Either leg with p=None must demote (cannot establish joint pass)."""

    card = _card(
        "aov_lift_via_threshold_bundle",
        blend_prov=_band_stash(
            obs_n=200, sign_agreement_count=3, l28_p=None, l28_band_p=0.04
        ),
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    assert kept == []
    assert refused[0].reason_code == ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS


def test_clause2_joint_fail_supersedes_sign_agreement_pass():
    """Beauty T5.5 probe case: 3-window AOV sign-agreement but band p>=0.10.

    The DS verdict 2026-05-23 load-bearing case. Without Clause 2 this
    card would post a 20x-noise-driven posterior shift to Recommended.
    """

    card = _card(
        "aov_lift_via_threshold_bundle",
        blend_prov=_band_stash(
            obs_n=500, sign_agreement_count=3, l28_p=0.05, l28_band_p=0.40
        ),
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    assert kept == []
    assert refused[0].reason_code == ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS


# ---------------------------------------------------------------------------
# Per-builder flag independence: joint clause is NO-OP for single-test stash
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "play_id",
    [
        "winback_dormant_cohort",
        "replenishment_due",
        "discount_dependency_hygiene",
        "cohort_journey_first_to_second",
    ],
)
def test_joint_clause_noop_for_single_test_builders(play_id):
    """T1/T2/T3/T4 stash has no ``*_band`` keys → Clause 2 is no-op."""

    # sign_agreement_count=3 → Clause 1 passes; no ``*_band`` → Clause 2 skipped.
    card = _card(
        play_id,
        blend_prov=_single_test_stash(obs_n=200, sign_agreement_count=3),
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    assert refused == []
    assert len(kept) == 1
    assert kept[0].play_id == play_id


# ---------------------------------------------------------------------------
# Cold-start: n <= floor → gate is no-op
# ---------------------------------------------------------------------------


def test_cold_start_below_floor_passes_with_no_ladder():
    card = _card(
        "winback_dormant_cohort",
        blend_prov={
            "source": "bayesian_blend",
            "observed_n": 0,
            "observed_k": 0,
            "pseudo_n": 100,
            # No ``observed_windows`` key → sign-agreement count absent.
        },
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    assert refused == []
    assert len(kept) == 1
    # Cold ladder state: why_now unchanged.


def test_cold_start_n_below_floor_with_failed_signature_does_not_demote():
    """n=10 with sign_agreement_count=0 must NOT demote (below floor)."""

    card = _card(
        "winback_dormant_cohort",
        blend_prov=_single_test_stash(obs_n=10, sign_agreement_count=0),
    )
    kept, refused = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    assert refused == []
    assert len(kept) == 1


# ---------------------------------------------------------------------------
# 3-state copy ladder
# ---------------------------------------------------------------------------


def test_ladder_state_cold():
    assert decide_mod._ladder_state_for_blend({"observed_n": 0, "pseudo_n": 100}) == "cold"
    # ratio = 10 / 110 ≈ 0.09 < 0.2 → cold
    assert decide_mod._ladder_state_for_blend({"observed_n": 10, "pseudo_n": 100}) == "cold"


def test_ladder_state_accumulating():
    # ratio = 50 / 150 ≈ 0.33 in [0.2, 0.6) → accumulating
    assert decide_mod._ladder_state_for_blend({"observed_n": 50, "pseudo_n": 100}) == "accumulating"


def test_ladder_state_mature():
    # ratio = 300 / 400 = 0.75 >= 0.6 → mature
    assert decide_mod._ladder_state_for_blend({"observed_n": 300, "pseudo_n": 100}) == "mature"


def test_ladder_boundary_at_0_2_is_accumulating():
    # ratio = 25 / 100 = 0.25 >= 0.2 → accumulating (boundary belongs to upper bucket)
    assert decide_mod._ladder_state_for_blend({"observed_n": 25, "pseudo_n": 75}) == "accumulating"


def test_ladder_boundary_at_0_6_is_mature():
    # ratio = 60 / 100 = 0.6 >= 0.6 → mature
    assert decide_mod._ladder_state_for_blend({"observed_n": 60, "pseudo_n": 40}) == "mature"


def test_ladder_zero_division_defends_to_cold():
    assert decide_mod._ladder_state_for_blend({"observed_n": 0, "pseudo_n": 0}) == "cold"


def test_ladder_accumulating_prefix_applied():
    card = _card(
        "winback_dormant_cohort",
        blend_prov={
            "source": "bayesian_blend",
            "observed_n": 50,
            "observed_k": 10,
            "pseudo_n": 100,
            "observed_sign_agreement_count": 3,
            "observed_dominant_sign": 1,
            "observed_windows": {
                "L28": {"k": 10, "n": 50, "effect": 0.1, "p_value": 0.04, "sign": 1, "method": "z_pooled"},
            },
        },
    )
    kept, _ = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )


def test_ladder_mature_prefix_applied():
    card = _card(
        "winback_dormant_cohort",
        blend_prov={
            "source": "bayesian_blend",
            "observed_n": 5000,
            "observed_k": 1000,
            "pseudo_n": 100,
            "observed_sign_agreement_count": 3,
            "observed_dominant_sign": 1,
            "observed_windows": {
                "L28": {"k": 10, "n": 50, "effect": 0.1, "p_value": 0.04, "sign": 1, "method": "z_pooled"},
            },
        },
    )
    kept, _ = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )


def test_ladder_idempotent_on_re_application():
    card = _card(
        "winback_dormant_cohort",
        blend_prov={
            "source": "bayesian_blend",
            "observed_n": 5000,
            "observed_k": 1000,
            "pseudo_n": 100,
            "observed_sign_agreement_count": 3,
            "observed_dominant_sign": 1,
            "observed_windows": {
                "L28": {"k": 10, "n": 50, "effect": 0.1, "p_value": 0.04, "sign": 1, "method": "z_pooled"},
            },
        },
    )
    kept, _ = decide_mod._route_observed_eligibility_holds(
        [card], flag_on=True, min_eligibility_n=30
    )
    # Idempotent: no double-prepend.
