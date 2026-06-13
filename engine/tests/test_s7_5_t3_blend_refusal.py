"""Sprint 7.5 Ticket T3 — cold-start blend refusal + SOFT_PRIOR_UNVALIDATED.

Pins the flag-gated behavior of:

- ``src.sizing.size_play`` refusing the blend on priors whose
  ``validation_status`` is not in the blend-permitted set
  ``{validated_external, validated_internal, elicited_expert}``.
- ``src.sizing.PSEUDO_N_BY_STATUS`` table + ``bayesian_blend`` helper
  numerics (founder Q4 locked at 30/15/10).
- ``src.priors_loader.resolve_mixed_prior`` KI-19 conservative-min rule:
  the mixed-blended PriorEntry inherits the LESS validated of the two
  per-vertical sides (no silent upgrade through mixing).
- ``src.decide.decide`` emitting ``Abstain.mode=SOFT_PRIOR_UNVALIDATED``
  and routing refused plays to ``considered`` with
  ``ReasonCode.PRIOR_UNVALIDATED`` when the flag is ON.
- Flag default OFF: identical behavior to T2 close (parity).

All tests are pure / hermetic; no fixtures touched. The flag is read
through the ``cfg`` mapping plumbed by ``src.main``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.priors_loader as PL  # noqa: E402
import src.sizing as SZ  # noqa: E402
from src.decide import _compute_abstain_mode, _route_prior_unvalidated_holds, decide  # noqa: E402
from src.engine_run import (  # noqa: E402
    Abstain,
    AbstainMode,
    DecisionState,
    EngineRun,
    EvidenceClass,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
)
from src.priors_loader import PriorEntry, PriorValidationStatus  # noqa: E402
from src.sizing import (  # noqa: E402
    PSEUDO_N_BY_STATUS,
    SizingInputs,
    bayesian_blend,
    size_play,
)


# ---------------------------------------------------------------------------
# Fixtures: minimal-yaml priors loaded into the loader cache
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    PL.clear_cache()
    PL.load_priors(path)


def _patch_loader_path(monkeypatch, path: Path) -> None:
    """Make ``src.sizing.get_prior`` consult the fixture YAML."""

    real_get_prior = PL.get_prior

    def _fake(*args, **kwargs):
        kwargs["path"] = path
        return real_get_prior(*args, **kwargs)

    monkeypatch.setattr(SZ, "get_prior", _fake)


# ---------------------------------------------------------------------------
# PSEUDO_N table + bayesian_blend
# ---------------------------------------------------------------------------


def test_pseudo_n_table_is_30_15_10_per_founder_q4():
    """Founder Q4 locks the table at 30 / 15 / 10."""

    assert PSEUDO_N_BY_STATUS == {
        PriorValidationStatus.VALIDATED_EXTERNAL: 30,
        PriorValidationStatus.VALIDATED_INTERNAL: 15,
        PriorValidationStatus.ELICITED_EXPERT: 10,
    }


def test_pseudo_n_table_does_not_admit_unvalidated_statuses():
    """``heuristic_unvalidated`` / ``placeholder`` MUST NOT appear in the
    pseudo_N table — they trigger refusal, not a downgraded weight."""

    assert PriorValidationStatus.HEURISTIC_UNVALIDATED not in PSEUDO_N_BY_STATUS
    assert PriorValidationStatus.PLACEHOLDER not in PSEUDO_N_BY_STATUS


def test_bayesian_blend_validated_external_weight_is_30():
    """With ``pseudo_n=30`` and ``n_observed=0`` the posterior is the prior."""

    out = bayesian_blend(prior_value=0.08, pseudo_n=30, store_value=0.20, n_observed=0)
    assert out == pytest.approx(0.08)


def test_bayesian_blend_dominated_by_store_when_n_observed_large():
    """When n_observed dwarfs pseudo_n, posterior collapses to store value."""

    out = bayesian_blend(prior_value=0.08, pseudo_n=30, store_value=0.20, n_observed=10000)
    assert out == pytest.approx(0.20, abs=0.001)


def test_bayesian_blend_numerical_sanity_30_pseudo_n():
    """30 * 0.08 + 30 * 0.20 over (30 + 30) = 0.14 — pinpoint check."""

    out = bayesian_blend(prior_value=0.08, pseudo_n=30, store_value=0.20, n_observed=30)
    assert out == pytest.approx(0.14)


def test_bayesian_blend_zero_zero_falls_back_to_mean():
    """Pathological denom-zero: arithmetic mean rather than ZeroDivisionError."""

    out = bayesian_blend(prior_value=0.10, pseudo_n=0, store_value=0.30, n_observed=0)
    assert out == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# size_play refusal rule
# ---------------------------------------------------------------------------


_HEURISTIC_TARGETING_YAML = """
schema_version: "1.0.0"
last_reviewed: "2026-05-17"
plays:
  fancy_targeting_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: observational
      validation_status: heuristic_unvalidated
      applies_to: { vertical: beauty }
"""


_VALIDATED_EXTERNAL_TARGETING_YAML = """
schema_version: "1.0.0"
last_reviewed: "2026-05-17"
plays:
  fancy_targeting_play:
    - name: base_rate
      value: 0.08
      range_p10: 0.04
      range_p90: 0.15
      source_class: observational
      validation_status: validated_external
      source_artifact: config/priors_sources/fake_memo.md
      effective_n: 30
      applies_to: { vertical: beauty }
"""


_PLACEHOLDER_TARGETING_YAML = """
schema_version: "1.0.0"
last_reviewed: "2026-05-17"
plays:
  fancy_targeting_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: observational
      validation_status: placeholder
      applies_to: { vertical: beauty }
"""


def test_flag_off_heuristic_unvalidated_falls_back_to_legacy_source_class_rule(
    tmp_path, monkeypatch
):
    """Flag OFF: T2-close behavior. Heuristic prior + non-causal source_class
    still suppresses via ``targeting_non_causal_prior`` (legacy rule),
    NOT the new ``prior_unvalidated``."""

    p = tmp_path / "priors.yaml"
    _write_yaml(p, _HEURISTIC_TARGETING_YAML)
    _patch_loader_path(monkeypatch, p)

    out = size_play(
        SizingInputs(
            play_id="fancy_targeting_play",
            evidence_class="targeting",
            audience_size=500,
            aov=60.0,
            vertical="beauty",
            priors_validation_enabled=False,
        )
    )

    assert out.suppressed is True
    reasons = [d for d in out.drivers if d["name"] == "suppression_reason"]
    # Legacy rule fires when validation flag is OFF.
    assert reasons and reasons[0]["reason"] == "targeting_non_causal_prior"


def test_flag_on_heuristic_unvalidated_refuses_blend(tmp_path, monkeypatch):
    """Flag ON: heuristic_unvalidated prior triggers ``prior_unvalidated``
    suppression (new rule wins over the legacy fallback)."""

    p = tmp_path / "priors.yaml"
    _write_yaml(p, _HEURISTIC_TARGETING_YAML)
    _patch_loader_path(monkeypatch, p)

    out = size_play(
        SizingInputs(
            play_id="fancy_targeting_play",
            evidence_class="targeting",
            audience_size=500,
            aov=60.0,
            vertical="beauty",
            priors_validation_enabled=True,
        )
    )

    assert out.suppressed is True
    reasons = [d for d in out.drivers if d["name"] == "suppression_reason"]
    assert reasons and reasons[0]["reason"] == "prior_unvalidated"
    # The base_rate driver carries the validation_status for audit.
    base = [d for d in out.drivers if d["name"] == "base_rate"]
    assert base and base[0]["validation_status"] == "heuristic_unvalidated"


def test_flag_on_placeholder_refuses_blend(tmp_path, monkeypatch):
    """Flag ON: placeholder priors are refused the same way as heuristic."""

    p = tmp_path / "priors.yaml"
    _write_yaml(p, _PLACEHOLDER_TARGETING_YAML)
    _patch_loader_path(monkeypatch, p)

    out = size_play(
        SizingInputs(
            play_id="fancy_targeting_play",
            evidence_class="targeting",
            audience_size=500,
            aov=60.0,
            vertical="beauty",
            priors_validation_enabled=True,
        )
    )

    assert out.suppressed is True
    reasons = [d for d in out.drivers if d["name"] == "suppression_reason"]
    assert reasons and reasons[0]["reason"] == "prior_unvalidated"


def test_flag_on_validated_external_permits_blend(tmp_path, monkeypatch):
    """Flag ON: validated_external priors are not refused; the range is
    populated from the prior just like the legacy ``allow_targeting_unsuppressed``
    test."""

    p = tmp_path / "priors.yaml"
    _write_yaml(p, _VALIDATED_EXTERNAL_TARGETING_YAML)
    _patch_loader_path(monkeypatch, p)

    out = size_play(
        SizingInputs(
            play_id="fancy_targeting_play",
            evidence_class="targeting",
            audience_size=500,
            aov=60.0,
            vertical="beauty",
            priors_validation_enabled=True,
            # No escape hatch: under the T3 contract, validation_status
            # in the blend-permitted set REPLACES (not supplements) the
            # legacy ``source_class != causal`` rule. The validated_external
            # prior here is observational; flag-on path must NOT fall
            # through to legacy suppression.
        )
    )

    # The validated_external prior is NOT refused under the T3 rule. The
    # range is populated; no ``prior_unvalidated`` reason in drivers.
    assert out.suppressed is False
    reasons = [d for d in out.drivers if d["name"] == "suppression_reason"]
    assert not reasons


# ---------------------------------------------------------------------------
# KI-19 conservative-min on resolve_mixed_prior
# ---------------------------------------------------------------------------


_MIXED_HEURISTIC_PLUS_VALIDATED_YAML = """
schema_version: "1.0.0"
last_reviewed: "2026-05-17"
plays:
  conservative_min_play:
    - name: base_rate
      value: 0.08
      range_p10: 0.04
      range_p90: 0.15
      source_class: observational
      validation_status: validated_external
      source_artifact: config/priors_sources/fake_memo.md
      applies_to: { vertical: beauty }
    - name: base_rate
      value: 0.12
      range_p10: 0.05
      range_p90: 0.25
      source_class: observational
      validation_status: heuristic_unvalidated
      applies_to: { vertical: supplements }
"""


_MIXED_BOTH_VALIDATED_YAML = """
schema_version: "1.0.0"
last_reviewed: "2026-05-17"
plays:
  both_validated_play:
    - name: base_rate
      value: 0.08
      range_p10: 0.04
      range_p90: 0.15
      source_class: observational
      validation_status: validated_external
      source_artifact: config/priors_sources/fake_memo.md
      applies_to: { vertical: beauty }
    - name: base_rate
      value: 0.12
      range_p10: 0.05
      range_p90: 0.25
      source_class: observational
      validation_status: validated_internal
      source_artifact: config/priors_sources/internal_memo.md
      applies_to: { vertical: supplements }
"""


def test_resolve_mixed_prior_conservative_min_downgrades_to_heuristic(tmp_path):
    """KI-19: validated_external beauty + heuristic_unvalidated supplements
    => blended PriorEntry carries ``heuristic_unvalidated`` (the LESS
    validated side wins). This is the silent-upgrade guard."""

    p = tmp_path / "priors.yaml"
    _write_yaml(p, _MIXED_HEURISTIC_PLUS_VALIDATED_YAML)

    blended = PL.resolve_mixed_prior("conservative_min_play", key="base_rate", path=p)
    assert blended is not None
    assert blended.validation_status == PriorValidationStatus.HEURISTIC_UNVALIDATED


def test_resolve_mixed_prior_both_validated_picks_less_validated(tmp_path):
    """KI-19: validated_external + validated_internal -> the blended
    PriorEntry carries the LESS validated of the two
    (validated_internal)."""

    p = tmp_path / "priors.yaml"
    _write_yaml(p, _MIXED_BOTH_VALIDATED_YAML)

    blended = PL.resolve_mixed_prior("both_validated_play", key="base_rate", path=p)
    assert blended is not None
    # validated_internal sits BELOW validated_external in the rank;
    # conservative-min picks the less-validated side.
    assert blended.validation_status == PriorValidationStatus.VALIDATED_INTERNAL


def test_resolve_mixed_blended_prior_is_refused_under_flag_on(tmp_path, monkeypatch):
    """End-to-end: the blended heuristic prior is refused at the sizing
    seam under the T3 flag — silent upgrade through mixing is
    structurally impossible."""

    p = tmp_path / "priors.yaml"
    _write_yaml(p, _MIXED_HEURISTIC_PLUS_VALIDATED_YAML)

    # Resolve the mixed prior and assert the flag-on sizing path
    # refuses it. We use the blend output directly (rather than going
    # through size_play, which would consult the loader for the
    # mixed-vertical entry, which doesn't exist in this fixture) by
    # asserting the validation_status. The downstream size_play test on
    # _HEURISTIC_TARGETING_YAML already pins the sizing-side refusal.
    blended = PL.resolve_mixed_prior("conservative_min_play", key="base_rate", path=p)
    assert blended is not None
    # blended carries heuristic_unvalidated -> NOT in PSEUDO_N table.
    assert blended.validation_status not in PSEUDO_N_BY_STATUS


# ---------------------------------------------------------------------------
# decide() — SOFT_PRIOR_UNVALIDATED abstain mode + PRIOR_UNVALIDATED routing
# ---------------------------------------------------------------------------


def _make_targeting_card_with_refused_prior(play_id: str = "fancy_targeting_play") -> PlayCard:
    """A PlayCard whose revenue_range was suppressed under the T3 refusal
    rule (the driver carries ``reason=prior_unvalidated``)."""

    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.TARGETING,
        revenue_range=RevenueRange(
            p10=None,
            p50=None,
            p90=None,
            source=None,
            drivers=[
                {"name": "audience_size", "source": "store_observed", "value": 500},
                {
                    "name": "suppression_reason",
                    "source": "sizing_v2",
                    "value": "prior_unvalidated",
                    "reason": "prior_unvalidated",
                },
            ],
            suppressed=True,
        ),
    )


def _make_targeting_card_with_validated_range(play_id: str = "validated_play") -> PlayCard:
    """A PlayCard with a non-suppressed revenue_range (validated path)."""

    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.TARGETING,
        revenue_range=RevenueRange(
            p10=100.0, p50=200.0, p90=400.0, source=None, drivers=[], suppressed=False,
        ),
    )


def test_route_prior_unvalidated_flag_off_is_noop():
    """Flag OFF: refused cards are NOT moved to considered (preserves
    pre-T3 behavior; the legacy targeting_non_causal_prior path keeps
    its existing routing semantics)."""

    card = _make_targeting_card_with_refused_prior()
    kept, refused = _route_prior_unvalidated_holds([card], flag_on=False)
    assert kept == [card]
    assert refused == []


def test_route_prior_unvalidated_flag_on_routes_to_considered():
    """Flag ON: a PlayCard with a prior_unvalidated suppression reason is
    routed to a RejectedPlay with reason_code=PRIOR_UNVALIDATED."""

    card = _make_targeting_card_with_refused_prior(play_id="held_play")
    kept, refused = _route_prior_unvalidated_holds([card], flag_on=True)
    assert kept == []
    assert len(refused) == 1
    assert refused[0].play_id == "held_play"
    assert refused[0].reason_code == ReasonCode.PRIOR_UNVALIDATED


def test_route_prior_unvalidated_flag_on_keeps_non_refused_cards():
    """Flag ON: cards with a non-suppressed range pass through; only
    prior_unvalidated-suppressed ones are routed."""

    refused_card = _make_targeting_card_with_refused_prior(play_id="refused")
    ok_card = _make_targeting_card_with_validated_range(play_id="ok")
    kept, refused = _route_prior_unvalidated_holds(
        [refused_card, ok_card], flag_on=True
    )
    assert [c.play_id for c in kept] == ["ok"]
    assert [r.play_id for r in refused] == ["refused"]


def test_compute_abstain_mode_flag_off_returns_none():
    """Flag OFF: never emit a typed mode (preserves M0 / Beauty / supplements
    byte-identity)."""

    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT, considered=[], flag_on=False
    )
    assert mode is None


def test_compute_abstain_mode_publish_returns_none_even_when_flag_on():
    """A PUBLISH state never carries an abstain mode."""

    mode = _compute_abstain_mode(
        DecisionState.PUBLISH, considered=[], flag_on=True
    )
    assert mode is None


def test_compute_abstain_mode_soft_with_no_prior_unvalidated_is_awaiting_measurement():
    """Flag ON + ABSTAIN_SOFT + no PRIOR_UNVALIDATED considered -> the mode
    is SOFT_AWAITING_MEASUREMENT (validated priors exist; the store just
    lacks store-specific evidence)."""

    considered = [
        RejectedPlay(
            play_id="some_play",
            reason_code=ReasonCode.NO_MEASURED_SIGNAL,
        )
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT, considered=considered, flag_on=True
    )
    assert mode == AbstainMode.SOFT_AWAITING_MEASUREMENT


def test_compute_abstain_mode_soft_with_prior_unvalidated_picks_soft_prior_unvalidated():
    """Flag ON + ABSTAIN_SOFT + any PRIOR_UNVALIDATED in considered ->
    SOFT_PRIOR_UNVALIDATED. This is the distinguishing condition."""

    considered = [
        RejectedPlay(
            play_id="held_play",
            reason_code=ReasonCode.PRIOR_UNVALIDATED,
        )
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT, considered=considered, flag_on=True
    )
    assert mode == AbstainMode.SOFT_PRIOR_UNVALIDATED


# ---------------------------------------------------------------------------
# decide() end-to-end: SOFT_PRIOR_UNVALIDATED + PRIOR_UNVALIDATED routing
# ---------------------------------------------------------------------------


def test_decide_flag_on_routes_refused_to_considered_with_prior_unvalidated():
    """End-to-end decide() with one refused targeting card -> the card
    surfaces in ``considered`` with reason_code=PRIOR_UNVALIDATED and
    is absent from ``recommendations``."""

    refused_card = _make_targeting_card_with_refused_prior(play_id="held_play")
    er = EngineRun()
    er.recommendations = [refused_card]
    out = decide(er, cfg={"ENGINE_V2_PRIORS_VALIDATION": True})

    rec_ids = {c.play_id for c in (out.recommendations or [])}
    con_ids = {r.play_id for r in (out.considered or [])}
    assert "held_play" not in rec_ids
    assert "held_play" in con_ids
    held_in_con = [r for r in out.considered if r.play_id == "held_play"]
    assert held_in_con and held_in_con[0].reason_code == ReasonCode.PRIOR_UNVALIDATED


def test_decide_flag_on_emits_soft_prior_unvalidated_when_no_validated_play_survives():
    """End-to-end: the only candidate is a refused targeting card -> the
    run goes ABSTAIN_SOFT and the typed mode is SOFT_PRIOR_UNVALIDATED."""

    refused_card = _make_targeting_card_with_refused_prior(play_id="held_play")
    er = EngineRun()
    er.recommendations = [refused_card]
    out = decide(er, cfg={"ENGINE_V2_PRIORS_VALIDATION": True})

    assert out.abstain.state == DecisionState.ABSTAIN_SOFT
    assert out.abstain.mode == AbstainMode.SOFT_PRIOR_UNVALIDATED


def test_decide_flag_off_preserves_legacy_abstain_shape():
    """Flag OFF: end-to-end decide() does NOT emit a typed mode; the
    Abstain dataclass carries the pre-T3 (state, reason) tuple only."""

    refused_card = _make_targeting_card_with_refused_prior(play_id="held_play")
    er = EngineRun()
    er.recommendations = [refused_card]
    out = decide(er, cfg={"ENGINE_V2_PRIORS_VALIDATION": False})

    # ``mode`` defaults to None when the flag is OFF (M0 byte-identity).
    assert out.abstain.mode is None


# ---------------------------------------------------------------------------
# Parity: flag-OFF behavior is unchanged from T2 close (no new suppressions)
# ---------------------------------------------------------------------------


def test_sizing_inputs_default_flag_is_off():
    """Defensive contract: SizingInputs.priors_validation_enabled defaults
    to False. M0 / Beauty / supplements byte-identity depends on this."""

    inp = SizingInputs(
        play_id="any",
        evidence_class="targeting",
        audience_size=10,
        aov=10.0,
    )
    assert inp.priors_validation_enabled is False
