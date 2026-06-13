"""Tests for the M4b T4b.2 multi-window combiner reroute.

Pins the rule that, on the V2 measured/directional path,
``_compute_multiwindow_candidates`` calls
``_combine_multiwindow_candidates_v2`` (which uses
``stats.combine_multiwindow_statistics``) and does NOT call the legacy
``_merge_multiwindow_candidates`` (min-p window shopping).

The reroute is gated behind both M4b flags:
``STATS_NAN_FOR_HARDCODED=true`` AND ``EVIDENCE_CLASS_ENFORCED=true``. With
either flag off, the legacy min-p path remains in use and these tests
verify both code paths.
"""

from __future__ import annotations

import math

import pytest

from src.action_engine import (
    _combine_multiwindow_candidates_v2,
    _merge_multiwindow_candidates,
)


# ---------------------------------------------------------------------------
# V2 combiner: measured/directional plays use combine_multiwindow_statistics
# ---------------------------------------------------------------------------


def _make_window_cand(
    *,
    play_id: str,
    metric: str,
    window: str,
    p: float,
    effect_abs: float,
    n: int,
    ci_low: float | None = None,
    ci_high: float | None = None,
    evidence_class: str = "measured",
    score: float = 1.0,
) -> dict:
    return {
        "play_id": play_id,
        "metric": metric,
        "source_window": window,
        "window_weight": 0.25,
        "p": p,
        "effect_abs": effect_abs,
        "n": n,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "evidence_class": evidence_class,
        "score": score,
    }


def test_v2_combiner_called_for_measured_play():
    """3 windows of a measured play -> combined output, not min-p selection."""
    cands = [
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L28",
            p=0.10, effect_abs=0.04, n=200, ci_low=0.01, ci_high=0.07,
            evidence_class="measured",
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L56",
            p=0.05, effect_abs=0.05, n=400, ci_low=0.02, ci_high=0.08,
            evidence_class="measured",
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L90",
            p=0.20, effect_abs=0.03, n=600, ci_low=-0.01, ci_high=0.07,
            evidence_class="measured",
        ),
    ]

    out = _combine_multiwindow_candidates_v2(cands)
    assert len(out) == 1
    merged = out[0]
    # Combiner stamp.
    assert merged["statistical_method"] == "combine_multiwindow_statistics"
    # All three windows contributed (none NaN).
    assert sorted(merged["contributing_windows"]) == ["L28", "L56", "L90"]
    # consistency_across_windows is computed (sign-agreement count).
    assert merged["consistency_across_windows"] >= 0
    # The combined p is NOT min(0.05, 0.10, 0.20) = 0.05; it is Fisher-combined.
    # We do not pin the exact value, but it must not equal the min p.
    # (Fisher's combined p of 0.05/0.10/0.20 is well below 0.05.)
    assert merged["p"] != 0.05 or merged["p"] != min(0.10, 0.05, 0.20)
    # The combined effect is inverse-variance weighted; it lies between
    # the min and max window effect.
    assert 0.03 <= merged["effect_abs"] <= 0.05


def test_v2_combiner_takes_n_from_combiner_total():
    """combine_multiwindow_statistics returns n_total = sum(window n)."""
    cands = [
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L28",
            p=0.05, effect_abs=0.05, n=200, ci_low=0.02, ci_high=0.08,
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L56",
            p=0.05, effect_abs=0.05, n=300, ci_low=0.02, ci_high=0.08,
        ),
    ]
    out = _combine_multiwindow_candidates_v2(cands)
    assert out[0]["n"] == 500


def test_v2_combiner_carries_ci_from_combined_se():
    cands = [
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L28",
            p=0.05, effect_abs=0.05, n=200, ci_low=0.02, ci_high=0.08,
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L56",
            p=0.05, effect_abs=0.05, n=300, ci_low=0.02, ci_high=0.08,
        ),
    ]
    out = _combine_multiwindow_candidates_v2(cands)
    merged = out[0]
    # CI low <= effect <= CI high.
    assert merged["ci_low"] <= merged["effect_abs"] <= merged["ci_high"]
    # CI is the combined-SE 1.96-margin output; not just min/max of inputs.


# ---------------------------------------------------------------------------
# V2 combiner: targeting plays SKIP combination; measurement is null
# ---------------------------------------------------------------------------


def test_v2_targeting_plays_skip_combination():
    """A targeting play does NOT have its stats combined. Stats become NaN."""
    cands = [
        _make_window_cand(
            play_id="subscription_nudge", metric="ltv_cohort", window="L28",
            p=0.04, effect_abs=0.05, n=120,
            evidence_class="targeting",
        ),
        _make_window_cand(
            play_id="subscription_nudge", metric="ltv_cohort", window="L56",
            p=0.03, effect_abs=0.05, n=200,
            evidence_class="targeting",
        ),
    ]
    out = _combine_multiwindow_candidates_v2(cands)
    assert len(out) == 1
    merged = out[0]
    assert merged["statistical_method"] == "targeting_no_combination"
    # Stats are NaN'd so the EngineRun mapper drops the measurement block.
    assert math.isnan(merged["p"])
    assert math.isnan(merged["effect_abs"])
    assert math.isnan(merged["ci_low"])
    assert math.isnan(merged["ci_high"])
    # consistency is None (no signed direction to agree with).
    assert merged["consistency_across_windows"] is None


def test_v2_targeting_does_not_use_min_p():
    """For targeting, the combined ``p`` is NaN — NOT min(window ps).

    This is the load-bearing assertion: legacy ``_merge_multiwindow_candidates``
    would have promoted the min-p window's stats to the merged record. The V2
    path drops them.
    """
    cands = [
        _make_window_cand(
            play_id="category_expansion", metric="cross_cat", window="L28",
            p=0.001, effect_abs=0.40, n=150,
            evidence_class="targeting",
        ),
        _make_window_cand(
            play_id="category_expansion", metric="cross_cat", window="L56",
            p=0.5, effect_abs=0.30, n=200,
            evidence_class="targeting",
        ),
    ]
    out = _combine_multiwindow_candidates_v2(cands)
    merged = out[0]
    # If min-p selection had been used, p would be 0.001. V2 NaNs it.
    assert math.isnan(merged["p"])
    assert merged["p"] != 0.001


# ---------------------------------------------------------------------------
# V2 combiner: NaN'd windows do not contribute (T4b.5 / fabricated stats)
# ---------------------------------------------------------------------------


def test_v2_combiner_skips_nan_windows():
    """A measured play whose per-window p is NaN has that window excluded."""
    cands = [
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L28",
            p=float("nan"), effect_abs=float("nan"), n=200,
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L56",
            p=0.05, effect_abs=0.05, n=400, ci_low=0.02, ci_high=0.08,
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L90",
            p=0.10, effect_abs=0.04, n=300, ci_low=0.01, ci_high=0.07,
        ),
    ]
    out = _combine_multiwindow_candidates_v2(cands)
    merged = out[0]
    assert merged["statistical_method"] == "combine_multiwindow_statistics"
    # Only L56 and L90 contributed; L28 was NaN.
    assert sorted(merged["contributing_windows"]) == ["L56", "L90"]


def test_v2_combiner_all_nan_windows_yields_no_combination():
    """If every window is NaN, the combiner has nothing to combine."""
    cands = [
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L28",
            p=float("nan"), effect_abs=float("nan"), n=200,
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L56",
            p=float("nan"), effect_abs=float("nan"), n=400,
        ),
    ]
    out = _combine_multiwindow_candidates_v2(cands)
    merged = out[0]
    assert merged["statistical_method"] == "combiner_no_valid_windows"
    # Stats are NaN; consistency is 0 (no valid combiner direction).
    assert math.isnan(merged["p"])
    assert math.isnan(merged["effect_abs"])
    assert merged["consistency_across_windows"] == 0


# ---------------------------------------------------------------------------
# Negative test: legacy min-p path is bypassed when V2 combiner runs
# ---------------------------------------------------------------------------


def test_legacy_min_p_path_not_used_on_v2_combiner_output():
    """V2 combiner does NOT pick min-p source_window like legacy did.

    The legacy ``_merge_multiwindow_candidates`` set ``source_window`` to the
    window with the lowest p-value (min-p shopping). The V2 path picks the
    first contributing window deterministically.
    """
    cands = [
        # First window has higher p.
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L28",
            p=0.20, effect_abs=0.03, n=200, ci_low=0.0, ci_high=0.06,
        ),
        # Second window has the lowest p — would be min-p winner.
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L56",
            p=0.001, effect_abs=0.05, n=400, ci_low=0.02, ci_high=0.08,
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L90",
            p=0.10, effect_abs=0.04, n=300, ci_low=0.01, ci_high=0.07,
        ),
    ]
    out_v2 = _combine_multiwindow_candidates_v2(cands)
    v2_merged = out_v2[0]
    # V2 picks the FIRST contributing window — L28 — not min-p L56.
    assert v2_merged["source_window"] == "L28"

    # Compare with legacy: legacy promotes L56 (min-p) into source_window.
    out_legacy = _merge_multiwindow_candidates(cands)
    legacy_merged = out_legacy[0]
    assert legacy_merged["source_window"] == "L56"


def test_legacy_min_p_keeps_min_p_value_on_merged_record():
    """Pin the legacy min-p semantic that the V2 path replaces."""
    cands = [
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L28",
            p=0.20, effect_abs=0.03, n=200,
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L56",
            p=0.001, effect_abs=0.05, n=400,
        ),
    ]
    out_legacy = _merge_multiwindow_candidates(cands)
    # Legacy promotes the smallest p-value to the merged record.
    assert out_legacy[0]["p"] == 0.001

    out_v2 = _combine_multiwindow_candidates_v2(cands)
    # V2 does NOT promote min-p; it produces a Fisher-combined p that is not
    # equal to either window's p in general. (Both windows here pass the NaN
    # filter and contribute via combine_multiwindow_statistics.)
    v2_p = out_v2[0]["p"]
    assert v2_p != 0.001  # not min-p shopping
    # Sanity: combined p exists and is in [0, 1].
    assert 0.0 <= v2_p <= 1.0


# ---------------------------------------------------------------------------
# Per-play independence: targeting + measured plays in same batch
# ---------------------------------------------------------------------------


def test_v2_handles_mixed_targeting_and_measured_plays():
    """Mixed batch: targeting play is skipped; measured play is combined."""
    cands = [
        # Measured play.
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L28",
            p=0.05, effect_abs=0.05, n=200, ci_low=0.02, ci_high=0.08,
            evidence_class="measured",
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L56",
            p=0.10, effect_abs=0.04, n=400, ci_low=0.01, ci_high=0.07,
            evidence_class="measured",
        ),
        # Targeting play.
        _make_window_cand(
            play_id="subscription_nudge", metric="ltv_cohort", window="L28",
            p=0.04, effect_abs=0.05, n=120,
            evidence_class="targeting",
        ),
    ]
    out = _combine_multiwindow_candidates_v2(cands)
    by_play = {c["play_id"]: c for c in out}
    assert set(by_play) == {"winback_21_45", "subscription_nudge"}
    assert by_play["winback_21_45"]["statistical_method"] == "combine_multiwindow_statistics"
    assert by_play["subscription_nudge"]["statistical_method"] == "targeting_no_combination"
    assert math.isnan(by_play["subscription_nudge"]["p"])
    assert not math.isnan(by_play["winback_21_45"]["p"])


# ---------------------------------------------------------------------------
# Reroute call-site: _compute_multiwindow_candidates routes to V2 only
# when both M4b flags are set
# ---------------------------------------------------------------------------


def test_compute_multiwindow_routes_v2_when_both_flags_on(monkeypatch):
    """When both M4b flags are on, _compute_multiwindow_candidates calls
    ``_combine_multiwindow_candidates_v2`` and NOT ``_merge_multiwindow_candidates``.
    """
    import src.action_engine as ae

    v2_calls = []
    legacy_calls = []

    def _fake_v2(cands):
        v2_calls.append(list(cands))
        return list(cands)

    def _fake_legacy(cands):
        legacy_calls.append(list(cands))
        return list(cands)

    monkeypatch.setattr(ae, "_combine_multiwindow_candidates_v2", _fake_v2)
    monkeypatch.setattr(ae, "_merge_multiwindow_candidates", _fake_legacy)

    # Stub out the per-window candidate generation entirely so we can drive
    # the dispatch logic in isolation.
    def _fake_compute(g, single_window_aligned, cfg):
        return [
            {
                "play_id": "winback_21_45",
                "metric": "repeat_rate",
                "source_window": f"L{single_window_aligned['window_days']}",
                "window_weight": 0.25,
                "p": 0.05,
                "effect_abs": 0.05,
                "n": 100,
                "score": 1.0,
                "evidence_class": "measured",
            }
        ]

    monkeypatch.setattr(ae, "_compute_candidates", _fake_compute)
    monkeypatch.setattr(ae, "_enhance_candidates_with_cohorts", lambda g, cands, cfg: cands)
    monkeypatch.setattr(
        ae, "enhance_template_action_with_real_stats", lambda c, g, a, w: c
    )
    monkeypatch.setattr(ae, "extract_business_metrics", lambda aligned: {})

    aligned = {
        "L28": {"orders": 100, "net_sales": 1000.0, "p": {}, "sig": {}, "delta": {}, "meta": {}},
        "L56": {"orders": 100, "net_sales": 1000.0, "p": {}, "sig": {}, "delta": {}, "meta": {}},
    }
    cfg = {
        "STATS_NAN_FOR_HARDCODED": True,
        "EVIDENCE_CLASS_ENFORCED": True,
        "ENABLE_ENHANCED_STATISTICS": False,
    }

    ae._compute_multiwindow_candidates(g=None, aligned_dict=aligned, cfg=cfg)

    assert len(v2_calls) == 1, "V2 combiner must be called exactly once when both M4b flags are on"
    assert len(legacy_calls) == 0, "Legacy min-p merge must NOT be called when both M4b flags are on"


def test_compute_multiwindow_routes_legacy_when_flag_off(monkeypatch):
    """When EITHER M4b flag is off, legacy ``_merge_multiwindow_candidates``
    is used. This preserves the M4a / M0 baseline behavior with flags off.
    """
    import src.action_engine as ae

    v2_calls = []
    legacy_calls = []

    monkeypatch.setattr(
        ae, "_combine_multiwindow_candidates_v2",
        lambda cands: v2_calls.append(list(cands)) or list(cands),
    )
    monkeypatch.setattr(
        ae, "_merge_multiwindow_candidates",
        lambda cands: legacy_calls.append(list(cands)) or list(cands),
    )

    def _fake_compute(g, single_window_aligned, cfg):
        return [
            {
                "play_id": "winback_21_45",
                "metric": "repeat_rate",
                "source_window": f"L{single_window_aligned['window_days']}",
                "window_weight": 0.25,
                "p": 0.05,
                "effect_abs": 0.05,
                "n": 100,
                "score": 1.0,
            }
        ]

    monkeypatch.setattr(ae, "_compute_candidates", _fake_compute)
    monkeypatch.setattr(ae, "_enhance_candidates_with_cohorts", lambda g, cands, cfg: cands)
    monkeypatch.setattr(
        ae, "enhance_template_action_with_real_stats", lambda c, g, a, w: c
    )
    monkeypatch.setattr(ae, "extract_business_metrics", lambda aligned: {})

    aligned = {
        "L28": {"orders": 100, "net_sales": 1000.0, "p": {}, "sig": {}, "delta": {}, "meta": {}},
    }

    # Both flags off
    cfg_both_off = {
        "STATS_NAN_FOR_HARDCODED": False,
        "EVIDENCE_CLASS_ENFORCED": False,
        "ENABLE_ENHANCED_STATISTICS": False,
    }
    ae._compute_multiwindow_candidates(g=None, aligned_dict=aligned, cfg=cfg_both_off)
    assert len(legacy_calls) == 1
    assert len(v2_calls) == 0

    # Only one flag on — still legacy path (the reroute requires BOTH).
    legacy_calls.clear()
    v2_calls.clear()
    cfg_partial = {
        "STATS_NAN_FOR_HARDCODED": True,
        "EVIDENCE_CLASS_ENFORCED": False,
        "ENABLE_ENHANCED_STATISTICS": False,
    }
    ae._compute_multiwindow_candidates(g=None, aligned_dict=aligned, cfg=cfg_partial)
    assert len(legacy_calls) == 1, "STATS_NAN alone must NOT trigger V2 reroute"
    assert len(v2_calls) == 0


# ---------------------------------------------------------------------------
# Sanity: V2 combiner does not mutate inputs
# ---------------------------------------------------------------------------


def test_v2_combiner_does_not_mutate_inputs():
    cands = [
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L28",
            p=0.05, effect_abs=0.05, n=200, ci_low=0.02, ci_high=0.08,
        ),
        _make_window_cand(
            play_id="winback_21_45", metric="repeat_rate", window="L56",
            p=0.10, effect_abs=0.04, n=400, ci_low=0.01, ci_high=0.07,
        ),
    ]
    snapshot = [dict(c) for c in cands]
    _combine_multiwindow_candidates_v2(cands)
    for original, current in zip(snapshot, cands):
        assert original == current
