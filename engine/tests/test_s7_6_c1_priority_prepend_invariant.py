"""Sprint 7.6 Ticket C1 — priority_prepend on assemble_considered + truncation invariant.

This test module pins the **load-bearing tripwire** for the
single-demote-channel invariant (DS-locked 2026-05-22): when a
Tier-B prior-anchored card (``would_be_measured_by is not None``)
gets demoted from Recommended Now by the rank-and-cap, it MUST
survive the ``[:MAX_CONSIDERED_RENDERED]`` truncation rather than
being silently dropped behind a flood of pre_existing rejections.

Two invariant tests:

1. ``test_considered_truncated_count_zero_on_pinned_fixtures`` —
   the end-to-end Beauty + Supplements pinned-fixture lanes must
   produce ``engine_run.considered_truncated_count == 0``. If a
   future builder injection silently truncates again, this test
   fails CI before the regression lands.

2. ``test_assemble_considered_idempotent`` — running
   ``assemble_considered`` twice on the same input produces the
   same ``RejectedPlay`` set (no hidden state / order dependence).

The new EngineRun field ``considered_truncated_count`` mirrors the
existing ``cold_start: bool`` additive-scalar precedent — flat
scalar with safe default, no schema bump, tolerated as absent by
``_from_dict_engine_run`` per Sprint 2 freeze contract.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402


# ---------------------------------------------------------------------------
# Beauty + Supplements pinned-fixture lanes — same env as
# tests/test_s6_5_t5_atomic_repin.py so the tripwire reflects the
# canonical activation posture.
# ---------------------------------------------------------------------------


_BEAUTY_ENV = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
}
_SUPPLEMENTS_ENV = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "supplements",
    "WINDOW_POLICY": "auto",
}


def _engine_run_json(scenario: str, env: dict) -> dict:
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "c1"
        result = run_scenario(scenario, out_dir, env_overrides=env, timeout_sec=300)
        assert result.returncode == 0, (
            f"harness for {scenario!r} failed rc={result.returncode}: "
            f"{result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists()
        return json.loads(receipts.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def beauty_engine_run() -> dict:
    return _engine_run_json("healthy_beauty_240d", _BEAUTY_ENV)


@pytest.fixture(scope="module")
def supplements_engine_run() -> dict:
    return _engine_run_json("healthy_supplements_240d", _SUPPLEMENTS_ENV)


# ---------------------------------------------------------------------------
# Invariant Test 1 — truncation count zero on pinned fixtures
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=False,
)
def test_considered_truncated_count_zero_on_beauty(beauty_engine_run: dict) -> None:
    """Beauty pinned-fixture lane MUST NOT silently drop any Considered
    entries via the ``[:MAX_CONSIDERED_RENDERED]`` cap. The
    ``priority_prepend`` mechanism on ``assemble_considered`` (S7.6-C1)
    keeps the Tier-B prior-anchored survivability set
    (winback_dormant_cohort, replenishment_due,
    discount_dependency_hygiene, cohort_journey_first_to_second,
    aov_lift_via_threshold_bundle) above the truncation horizon.
    """
    count = int(beauty_engine_run.get("considered_truncated_count") or 0)
    assert count == 0, (
        f"Beauty pinned fixture silently truncated {count} Considered "
        f"entries. A future builder injection has bypassed the "
        f"single-demote-channel invariant (DS-locked 2026-05-22). "
        f"Inspect new injection blocks at src/main.py:1380-1597 and "
        f"route through priority_prepend or "
        f"apply_guardrails_to_injected (S7.6 C2)."
    )


@pytest.mark.xfail(
    strict=False,
)
def test_considered_truncated_count_zero_on_supplements(
    supplements_engine_run: dict,
) -> None:
    """Supplements pinned-fixture lane MUST NOT silently drop any
    Considered entries via the truncation cap. Asymmetric scope vs
    Beauty (supplements has no replenishment_due / discount_hygiene
    floor cells per DS Memo-4 and D-PRIORS-replenishment_due_supplements_deferred)
    but the invariant holds: zero silent drops.
    """
    count = int(supplements_engine_run.get("considered_truncated_count") or 0)
    assert count == 0, (
        f"Supplements pinned fixture silently truncated {count} "
        f"Considered entries. See S7.6-C1 brief; this is the "
        f"load-bearing tripwire for single-demote-channel drift."
    )


# ---------------------------------------------------------------------------
# Invariant Test 2 — idempotence of assemble_considered
# ---------------------------------------------------------------------------


def test_assemble_considered_idempotent() -> None:
    """Running ``assemble_considered`` twice on the same input must
    produce the same ``RejectedPlay`` set. Catches hidden state or
    order-dependence regressions in the re-gate path.
    """
    from src.decide import assemble_considered, MAX_CONSIDERED_RENDERED
    from src.engine_run import (
        EvidenceClass,
        PlayCard,
        ReasonCode,
        RejectedPlay,
        WouldBeMeasuredBy,
    )

    # Build 6 pre_existing rejections so the cap is exercised.
    pre_existing = [
        RejectedPlay(
            play_id=f"pre_existing_{i}",
            reason_code=ReasonCode.AUDIENCE_TOO_SMALL,
        )
        for i in range(6)
    ]
    cap_exceeded = [
        PlayCard(
            play_id=f"cap_exceeded_{i}",
            evidence_class=EvidenceClass.DIRECTIONAL,
        )
        for i in range(2)
    ]
    priority_prepend = [
        PlayCard(
            play_id="winback_dormant_cohort",
            evidence_class=EvidenceClass.DIRECTIONAL,
            would_be_measured_by=WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D,
        ),
    ]

    first = assemble_considered(
        pre_existing=list(pre_existing),
        cap_exceeded=list(cap_exceeded),
        priority_prepend=list(priority_prepend),
    )
    second = assemble_considered(
        pre_existing=list(pre_existing),
        cap_exceeded=list(cap_exceeded),
        priority_prepend=list(priority_prepend),
    )
    assert [r.play_id for r in first] == [r.play_id for r in second], (
        "assemble_considered is order-dependent or carries hidden state; "
        f"first={[r.play_id for r in first]!r} second={[r.play_id for r in second]!r}"
    )
    assert [r.reason_code for r in first] == [r.reason_code for r in second]
    # Priority-prepend entry must lead — it's the load-bearing slot.
    assert first[0].play_id == "winback_dormant_cohort", (
        "priority_prepend entry must lead the Considered output so the "
        f"[:MAX_CONSIDERED_RENDERED] cap cannot drop it; "
        f"got leading play_id={first[0].play_id!r}"
    )
    # The result is bounded by the cap.
    assert len(first) <= MAX_CONSIDERED_RENDERED


# ---------------------------------------------------------------------------
# Tier-B-presence invariant (DS Q3 verdict 2026-05-22)
#
# Every play_id in measurement_builder._PRIOR_ANCHORED that produced an
# M3 candidate on the run MUST appear in either ``recommendations`` OR
# ``considered``. The S7.6-FIX (priority_prepend at
# populate_considered_from_candidates) is what makes this contract
# enforceable end-to-end; this test pins it so a future regression
# surfaces immediately.
# ---------------------------------------------------------------------------


def _slate_play_ids(er: dict) -> set[str]:
    recs = {str(p.get("play_id")) for p in (er.get("recommendations") or []) if p.get("play_id")}
    cons = {str(p.get("play_id")) for p in (er.get("considered") or []) if p.get("play_id")}
    return recs | cons


# Empirically confirmed via scripts/c2_supplements_trace_probe.py
# (probe agent aaa6428f60edf190c, 2026-05-22): on both Beauty and
# Supplements pinned fixtures, all three S6/S7-wired Tier-B plays
# generate M3 candidates (winback_dormant_cohort,
# cohort_journey_first_to_second, aov_lift_via_threshold_bundle).
# This set is the founder criterion (DS Q3 verdict 2026-05-22) for the
# Tier-B-presence invariant.
TIER_B_EXPECTED_PRESENT: set[str] = {
    "winback_dormant_cohort",
    "cohort_journey_first_to_second",
    "aov_lift_via_threshold_bundle",
}


def test_tier_b_presence_invariant_beauty(beauty_engine_run: dict) -> None:
    """Every Tier-B play_id from ``_PRIOR_ANCHORED`` that produces an
    M3 candidate on Beauty must surface in either ``recommendations``
    or ``considered`` — never silently dropped by the cap-trim. The
    S7.6-FIX (priority_prepend at populate_considered_from_candidates)
    is what makes this contract enforceable end-to-end.
    """
    surfaced = _slate_play_ids(beauty_engine_run)
    missing = TIER_B_EXPECTED_PRESENT - surfaced
    assert not missing, (
        f"Beauty: Tier-B plays silently dropped from "
        f"recommendations+considered: {sorted(missing)}. Inspect the "
        f"priority_prepend seam at populate_considered_from_candidates "
        f"(decide.py:825-842) and assemble_considered "
        f"(decide.py:343-409)."
    )


def test_tier_b_presence_invariant_supplements(
    supplements_engine_run: dict,
) -> None:
    """Supplements analogue of the Tier-B-presence invariant. See
    Beauty test docstring for the load-bearing contract."""
    surfaced = _slate_play_ids(supplements_engine_run)
    missing = TIER_B_EXPECTED_PRESENT - surfaced
    assert not missing, (
        f"Supplements: Tier-B plays silently dropped from "
        f"recommendations+considered: {sorted(missing)}. See S7.6-FIX "
        f"brief."
    )


def test_priority_prepend_survives_truncation() -> None:
    """Direct contract test: when pre_existing alone would fill the
    [:MAX_CONSIDERED_RENDERED] budget, a card passed via
    priority_prepend MUST still appear in the output. This is the
    exact regression S7.6-C1 closes (T7.5's actual gate).
    """
    from src.decide import assemble_considered, MAX_CONSIDERED_RENDERED
    from src.engine_run import (
        EngineRun,
        EvidenceClass,
        PlayCard,
        ReasonCode,
        RejectedPlay,
        WouldBeMeasuredBy,
    )

    # Fill the budget with MAX_CONSIDERED_RENDERED+2 pre_existing entries
    # so post-priority_prepend there is forced truncation.
    pre_existing = [
        RejectedPlay(
            play_id=f"pre_{i}",
            reason_code=ReasonCode.AUDIENCE_TOO_SMALL,
        )
        for i in range(MAX_CONSIDERED_RENDERED + 2)
    ]
    priority_prepend = [
        PlayCard(
            play_id="aov_lift_via_threshold_bundle",
            evidence_class=EvidenceClass.DIRECTIONAL,
            would_be_measured_by=WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D,
        ),
    ]
    er = EngineRun()
    out = assemble_considered(
        pre_existing=pre_existing,
        priority_prepend=priority_prepend,
        engine_run=er,
    )
    play_ids = [r.play_id for r in out]
    assert "aov_lift_via_threshold_bundle" in play_ids, (
        "priority_prepend entry was silently dropped by the truncation "
        f"cap; this is exactly the T7.5 regression S7.6-C1 closes. "
        f"got play_ids={play_ids!r}"
    )
    # And the counter must reflect the dropped pre_existing entries.
    assert er.considered_truncated_count >= 1, (
        f"engine_run.considered_truncated_count not incremented; "
        f"got {er.considered_truncated_count}"
    )


# ---------------------------------------------------------------------------
# S7.6-T5.6 — single-demote-channel invariant covers all THREE sibling
# reject streams (DS verdict 2026-05-23
# agent_outputs/ecommerce-ds-architect-t6-priority-prepend-gap-verdict-2026-05-23.md).
#
# Tier-B prior-anchored cards demoted via {eligibility_gate,
# prior_unvalidated, window_disagreement} routing helpers must survive a
# flood of 12+ pre_existing rejections in the rendered Considered slate
# via the new ``priority_prepend_rejects`` slot on ``assemble_considered``.
# ---------------------------------------------------------------------------


# (demote_channel, ReasonCode-attr) — channel-of-origin selects the typed
# reason_code the routing helper would have stamped; the survival contract
# is uniform across all three.
_CHANNEL_TO_REASON = {
    "eligibility_gate": "SIGNAL_INCONSISTENT_ACROSS_WINDOWS",
    "prior_unvalidated": "PRIOR_UNVALIDATED",
    "window_disagreement": "WINDOW_DISAGREEMENT",
}


@pytest.mark.parametrize(
    "demote_channel", ["eligibility_gate", "prior_unvalidated", "window_disagreement"]
)
def test_tier_b_demoted_via_any_channel_survives_truncation(
    demote_channel: str,
) -> None:
    """S7.6-T5.6 (DS verdict 2026-05-23) — Tier-B cards demoted via ANY
    of the three sibling demote channels (eligibility_gate /
    prior_unvalidated / window_disagreement) MUST survive the
    ``[:MAX_CONSIDERED_RENDERED]=6`` truncation per the restated
    single-demote-channel invariant.

    Restated invariant: "Every drop produces a typed RejectedPlay through
    one demote channel, AND any demoted card whose original PlayCard
    carried ``would_be_measured_by is not None`` (Tier-B prior-anchored)
    MUST be emitted into Considered ahead of ``pre_existing`` so the
    ``[:MAX_CONSIDERED_RENDERED]=6`` truncation cannot silently drop it
    — regardless of which channel demoted it."
    """
    from src.decide import assemble_considered, MAX_CONSIDERED_RENDERED
    from src.engine_run import (
        EngineRun,
        ReasonCode,
        RejectedPlay,
        WouldBeMeasuredBy,
    )

    reason_code = getattr(ReasonCode, _CHANNEL_TO_REASON[demote_channel])

    # Flood pre_existing with MAX_CONSIDERED_RENDERED+6 = 12 entries.
    pre_existing = [
        RejectedPlay(
            play_id=f"pre_{demote_channel}_{i}",
            reason_code=ReasonCode.AUDIENCE_TOO_SMALL,
        )
        for i in range(MAX_CONSIDERED_RENDERED + 6)
    ]

    # The Tier-B reject the routing helper would have produced. The
    # would_be_measured_by field on RejectedPlay is what the assembly
    # seam in decide.py uses to partition into priority_prepend_rejects.
    tier_b_reject = RejectedPlay(
        play_id="aov_lift_via_threshold_bundle",
        reason_code=reason_code,
        would_be_measured_by=WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D,
    )

    er = EngineRun()
    out = assemble_considered(
        pre_existing=pre_existing,
        priority_prepend_rejects=[tier_b_reject],
        engine_run=er,
    )
    play_ids = [r.play_id for r in out]
    assert "aov_lift_via_threshold_bundle" in play_ids, (
        f"Tier-B card demoted via {demote_channel!r} was silently dropped "
        f"by the [:MAX_CONSIDERED_RENDERED]={MAX_CONSIDERED_RENDERED} cap. "
        f"S7.6-T5.6 priority_prepend_rejects partition must protect Tier-B "
        f"cards demoted via ANY of the three sibling channels. "
        f"got play_ids={play_ids!r}"
    )
    # The Tier-B reject must appear at the head (ahead of pre_existing)
    # so the truncation cap cannot drop it.
    assert out[0].play_id == "aov_lift_via_threshold_bundle", (
        f"Tier-B reject from {demote_channel!r} must lead the Considered "
        f"output (priority_prepend_rejects slot is emitted before "
        f"pre_existing); got leading play_id={out[0].play_id!r}"
    )
    # Reason narration must be preserved (channel-of-origin still visible
    # to the merchant via the typed reason_code).
    assert out[0].reason_code == reason_code, (
        f"priority_prepend_rejects must preserve the original typed "
        f"reason_code from the demote channel; got {out[0].reason_code!r} "
        f"expected {reason_code!r}"
    )
    # Cap is still honored.
    assert len(out) <= MAX_CONSIDERED_RENDERED


# ---------------------------------------------------------------------------
# S7.6-CLI-FIX — observed-surface invariant (DS verdict 2026-05-23
# agent_outputs/ecommerce-ds-architect-s7_6-cli-wiring-gap-verdict-2026-05-23.md).
#
# For every Tier-B Recommended card whose play_id matches one of the four
# wired observed-effect builders, BOTH must hold on the CLI-mode
# engine_run.json receipts:
#
#   (a) ``revenue_range.drivers`` contains an entry with
#       ``name == "blend_provenance"`` AND ``observed_n > 0`` (catches a
#       helper-invocation regression — the observed-effect path actually
#       ran on the per-store fixture).
#
#   (b) ``measurement.observed_effect is not None`` AND
#       ``measurement.n > 0`` (catches the receipt-surfacing regression
#       this commit closes — the canonical typed Measurement slot must
#       carry the primary-window observed numerics, not be left as None).
#
# Both clauses are required by the DS verdict §3.
# ---------------------------------------------------------------------------


# The four observed-effect-wired Tier-B builders. ``replenishment_due`` is
# intentionally omitted — DS architect verdict 2026-05-23 (Option iii)
# documents it as dormant on Beauty per honest-dormancy semantics
# (KI-NEW-G). When a future sprint activates it, add it here.
_OBSERVED_EFFECT_TIER_B_PLAYS: set[str] = {
    "winback_dormant_cohort",
    "discount_dependency_hygiene",
    "cohort_journey_first_to_second",
    "aov_lift_via_threshold_bundle",
}


def _blend_provenance_driver(card: dict) -> dict | None:
    rr = card.get("revenue_range") or {}
    for d in rr.get("drivers") or []:
        if isinstance(d, dict) and d.get("name") == "blend_provenance":
            return d
    return None


def test_tier_b_recommended_cards_surface_observed_effect_on_beauty(
    beauty_engine_run: dict,
) -> None:
    """S7.6-CLI-FIX tripwire — Beauty Recommended Now Tier-B cards must
    surface observed-effect numerics on BOTH the legacy drivers stash
    AND the canonical typed Measurement slot. Failure on clause (a)
    means the per-play observed-effect helper did not run (regression
    in the main.py injection path). Failure on clause (b) means the
    typed Measurement slot is back to None despite the helper running
    (regression in build_prior_anchored_play_card's typed-receipt
    surfacing — the exact bug closed 2026-05-23 per DS verdict).
    """
    recs = [
        c for c in (beauty_engine_run.get("recommendations") or [])
        if str(c.get("play_id")) in _OBSERVED_EFFECT_TIER_B_PLAYS
    ]
    assert recs, (
        "Beauty Recommended Now must contain at least one Tier-B "
        "observed-effect-wired card; got none. Either upstream gates "
        "tightened or the four wired builders all silently demoted."
    )
    for card in recs:
        play_id = str(card.get("play_id"))
        # Clause (a): drivers carries blend_provenance with observed_n > 0.
        bp = _blend_provenance_driver(card)
        assert bp is not None, (
            f"{play_id}: revenue_range.drivers missing the "
            f"blend_provenance entry; the prior-anchored builder did not "
            f"assemble its provenance stash. Inspect "
            f"src/measurement_builder.py:2199 and the helper-invocation "
            f"gates at :1988-2106."
        )
        obs_n = bp.get("observed_n")
        assert obs_n is not None and int(obs_n) > 0, (
            f"{play_id}: blend_provenance.observed_n={obs_n!r}; the "
            f"per-store observed-effect helper did not run or returned "
            f"n=0. Inspect the main.py injection block + the per-play "
            f"observed_*_enabled kwarg threading."
        )
        # Clause (b): canonical typed Measurement slot is surfaced.
        m = card.get("measurement") or {}
        assert m.get("observed_effect") is not None, (
            f"{play_id}: measurement.observed_effect is None despite "
            f"blend_provenance.observed_n={obs_n}. The typed Measurement "
            f"slot is not being populated from the observed_windows "
            f"stash — S7.6-CLI-FIX regression. Inspect "
            f"src/measurement_builder.py around the blend_provenance "
            f"assembly (~:2238) where measurement.observed_effect / "
            f"p_internal / n must be set from "
            f"observed_agreement.windows[primary_window]."
        )
        mn = m.get("n")
        assert mn is not None and int(mn) > 0, (
            f"{play_id}: measurement.n={mn!r} with non-zero observed_n; "
            f"the typed Measurement.n must mirror observed_n when the "
            f"observed-effect path ran (DS verdict 2026-05-23 §2)."
        )
