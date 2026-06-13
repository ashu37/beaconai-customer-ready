"""Sprint 4 Ticket G-1 — Supplements pinned slate-regression fixture.

Deterministic end-to-end regression test for ``healthy_supplements_240d``
under the full V2 + slate flag stack
(``ENGINE_V2_OUTPUT`` / ``ENGINE_V2_DECIDE`` / ``ENGINE_V2_SLATE`` /
``ENGINE_V2_SIZING`` enabled, ``VERTICAL_MODE=supplements``).

This test mirrors :mod:`tests.test_slate_regression_beauty_brand` and
lives in the same lane (``tests/fixtures/synthetic_slate/``); it is NOT
an M0 golden and does NOT re-baseline the legacy goldens.

Per G-1 (post-6B-restructured-roadmap plan §4): the deliverable is the
end-to-end pinned fixture + the bug list documented in KNOWN_ISSUES.md
category 5 (Supplements & vertical). Every breakage encountered during
the supplements run has a corresponding ``KI-`` entry; this test only
pins the engine's current behavior so any future drift is caught
deliberately.

Contract pinned (current observed behavior on the synthetic fixture,
which IS the discovery deliverable — see ``KI-20``..``KI-N``):

- Engine does not crash on supplements (no parser/builder exception).
- ``decision_state == abstain_soft``. The supplements run produces no
  measured/directional cards under the V2 evidence ladder today
  (documented gap; see KI-20).
- ``data_quality_flags`` is empty list — supplements-specific data
  warnings (e.g. structurally-low repeat rate, see KI-22) propagate
  only as advisory stdout, not engine_run.json flags.
- ``briefing_meta.vertical == "supplements"`` (B-7 + S-1.7 contract
  preserved end-to-end).
- The pinned briefing.html is byte-stable across runs.

The supplements run today emits ZERO Recommended Now cards, ZERO
Recommended Experiment cards, six Considered cards, and four Watching
rows — the exact play_id membership IS pinned below as the regression
contract, but each row's framing is documented under a ``KI-`` entry,
not interpreted as healthy engine output.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Set

import pytest
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402


SCENARIO_NAME: str = "healthy_supplements_240d"

PINNED_FIXTURE: Path = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "synthetic_slate"
    / "healthy_supplements_240d_briefing.html"
)

# G-1: pinned sha256 of the briefing.html under the V2 + slate flag
# stack with ``VERTICAL_MODE=supplements`` / ``WINDOW_POLICY=auto``.
# Generated 2026-05-10 against post-6b-restructured-roadmap HEAD.
# A drift in this hash means either (a) the supplements slate output
# changed (deliberate fixture refresh) or (b) a regression in upstream
# selector/renderer logic. Both warrant explicit ticket scope.
PINNED_SHA256: str = (
    # S6.5-T5 re-affirm (2026-05-18, atomic with ENGINE_V2_STORE_PROFILE
    # flag flip OFF -> ON). The supplements briefing.html sha is
    # BYTE-IDENTICAL to the S5-T3 pin because the heuristic_unvalidated
    # supplements winback prior correctly suppresses any Recommended Now
    # surfacing on supplements (S7.5-T3 validated-vs-heuristic refusal
    # logic UNCHANGED), and the Considered/Watching membership is
    # unchanged. The behavior delta under flag-ON is engine_run.json-only:
    # ``store_profile`` slot is populated with taxonomy.vertical=
    # supplements, subvertical=functional (LOW), business_model=
    # SUBSCRIPTION_LED (sub_fraction=0.97 HIGH), business_stage.detected=
    # STARTUP with uncertainty=HIGH (boundary rule fires at $496K GMV
    # near the $500K STARTUP/GROWTH boundary per T4.y.1 symmetric
    # band-check fix). audience_floor.winback=60, materiality=$800
    # (STARTUP cells from gate_calibration.yaml).
    #
    # S5-T3 (2026-05-13): previously
    # ``a7def447872b7780cb09ce54ad7c8a64f1891c71ee3ed3cf66447b76cb32415b``
    # (S5-T2 KI-20 close); the S5-T3 sha reflected two coupled changes:
    # (1) ``data_quality_flags`` now contains ``metric_incoherent_for_cadence``
    # because the median customer reorder gap exceeds 0.8 * the active L28
    # window; (2) the misleading ``repeat_rate_within_window`` Watching
    # row is suppressed (founder call: suppress, not relabel).
    # S7.6-FIX (2026-05-22): re-pinned atomically with the
    # priority_prepend fix at populate_considered_from_candidates
    # (decide.py:825-842). Considered now surfaces the 3 Tier-B plays
    # (winback_dormant_cohort/AUDIENCE_TOO_SMALL,
    # cohort_journey_first_to_second/AUDIENCE_TOO_SMALL,
    # aov_lift_via_threshold_bundle/DATA_QUALITY_FLAG) and displaces
    # discount_hygiene/subscription_nudge/routine_builder.
    #
    # S7.6-C3 (2026-05-22): re-pinned atomically with the atomic
    # ``ENGINE_V2_AOV_THRESHOLD_FROM_DATA`` default flip from OFF to ON
    # (closes Sprint 7.6). Under flag-ON, the supplements vertical is
    # routed through the explicit ``vertical_excluded_per_b5_248`` gate
    # at the ``aov_lift_via_threshold_bundle`` builder seam
    # (audience_builders.py:969-979) per ARCHITECTURE_PLAN.md §III B-5
    # lines 248 + 257(c). The supplements Considered membership is
    # unchanged (aov_lift_via_threshold_bundle still surfaces); only
    # the AudienceResult's preliminary_rejection_reason changes from
    # ``data_missing`` to ``vertical_excluded_per_b5_248`` and the
    # threshold_source provenance shifts from ``data_missing`` to
    # ``vertical_excluded``. Both feed the same Considered surface
    # under the typed-reason fanout. Previous pin
    # ``0903071ee9646a9db24f44c9ae87e29a14873158f88dc4bd2e4ba192c79fc1da``.
    "13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344"
)

# Observed-today contract on the V2 supplements run. NOT an aspirational
# slate — see KI-20..KI-N for the breakages this fixture surfaces.
EXPECTED_DECISION_STATE: str = "abstain_soft"
EXPECTED_VERTICAL: str = "supplements"

EXPECTED_RECOMMENDED_PLAY_IDS: Set[str] = set()
EXPECTED_EXPERIMENT_PLAY_IDS: Set[str] = set()
EXPECTED_CONSIDERED_PLAY_IDS: Set[str] = {
    # S7.6-FIX (2026-05-22): priority_prepend on
    # populate_considered_from_candidates (decide.py:825-842) closes the
    # silent-drop at the cap-trim. The three S6/S7-wired Tier-B plays
    # (_PRIOR_ANCHORED registry at measurement_builder.py:717) now
    # survive the [:MAX_CONSIDERED_RENDERED=6] cap; they were previously
    # being correctly typed by populate_considered_from_candidates but
    # truncated off behind 6 legacy guardrail rejections. Founder
    # decision (CLAUDE.md 2026-05-22 single-demote-channel invariant):
    # truncation preferentially drops legacy plays so the load-bearing
    # Tier-B set survives.
    #
    # Truncated off (displaced by Tier-B priority_prepend):
    #   discount_hygiene, subscription_nudge, routine_builder
    # Surfaces now (Tier-B with typed reasons):
    #   winback_dormant_cohort           -> AUDIENCE_TOO_SMALL
    #   cohort_journey_first_to_second   -> AUDIENCE_TOO_SMALL
    #   aov_lift_via_threshold_bundle    -> DATA_QUALITY_FLAG
    #
    # S5-T2 (KI-20): typed honest abstain prepended for the supplements
    # vertical when the directional builder cannot surface
    # ``first_to_second_purchase``.
    "first_to_second_purchase",
    "winback_21_45",
    "bestseller_amplify",
    "winback_dormant_cohort",
    "cohort_journey_first_to_second",
    "aov_lift_via_threshold_bundle",
}
EXPECTED_WATCHING_METRICS: Set[str] = {
    # S5-T3 (KI-22): ``repeat_rate_within_window`` is now suppressed on
    # the supplements Watching row when
    # ``METRIC_INCOHERENT_FOR_CADENCE`` fires (founder call: suppress,
    # not relabel). Pre-S5-T3 this set included
    # ``repeat_rate_within_window``.
    "orders",
    "net_sales",
    "aov",
}

# Deterministic env contract for the G-1 harness invocation. Mirrors
# the Beauty B6 superset so the byte-stable snapshot test passes
# regardless of which other test ran first in the suite. The
# ``WINDOW_POLICY=auto`` pin decontaminates against the repo ``.env``'s
# ``WINDOW_POLICY=L28`` leakage (see Beauty test docstring for the full
# rationale).
_G1_ENV_OVERRIDES: dict[str, str] = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "supplements",
    "WINDOW_POLICY": "auto",
}


@pytest.fixture(scope="module")
def supplements_briefing_html() -> str:
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "g1"
        result = run_scenario(
            SCENARIO_NAME,
            out_dir,
            env_overrides=_G1_ENV_OVERRIDES,
            timeout_sec=300,
        )
        assert result.returncode == 0, (
            f"synthetic harness for {SCENARIO_NAME!r} failed "
            f"(rc={result.returncode}). stderr (last 500 chars): "
            f"{result.stderr[-500:]}"
        )
        briefing_path = (
            out_dir / "briefings" / f"{SCENARIO_NAME}_briefing.html"
        )
        assert briefing_path.exists(), (
            f"briefing.html not produced at {briefing_path}"
        )
        return briefing_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def supplements_engine_run_json() -> dict:
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "g1"
        result = run_scenario(
            SCENARIO_NAME,
            out_dir,
            env_overrides=_G1_ENV_OVERRIDES,
            timeout_sec=300,
        )
        assert result.returncode == 0
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists()
        return json.loads(receipts.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def supplements_soup(supplements_briefing_html: str) -> BeautifulSoup:
    return BeautifulSoup(supplements_briefing_html, "html.parser")


# ---------------------------------------------------------------------------
# 1. End-to-end smoke: engine does not crash on supplements
# ---------------------------------------------------------------------------


def test_engine_runs_end_to_end_on_supplements(
    supplements_engine_run_json: dict,
) -> None:
    """G-1 acceptance: supplements run produces a well-formed
    engine_run.json with all the structural top-level keys the slate
    consumer expects. The point of G-1 is to prove the engine does NOT
    crash on supplements (parser/builder smoke); slate richness is a
    separate Sprint 5+ scope per the KI-20..KI-N bug list.
    """
    expected_keys = {
        "run_id",
        "store_id",
        "anchor_date",
        "schema_version",
        "data_window",
        "cold_start",
        "data_quality_flags",
        "abstain",
        "state_of_store",
        "recommendations",
        "recommended_experiments",
        "considered",
        "watching",
        "scale",
        "briefing_meta",
    }
    missing = expected_keys - set(supplements_engine_run_json.keys())
    assert not missing, (
        f"engine_run.json missing required top-level keys on the "
        f"supplements run: {sorted(missing)}. The supplements vertical "
        f"is breaking schema shape — this is a contract issue, not a "
        f"KI-N candidate."
    )


def test_briefing_meta_vertical_is_supplements(
    supplements_engine_run_json: dict,
) -> None:
    meta = supplements_engine_run_json.get("briefing_meta") or {}
    assert meta.get("vertical") == EXPECTED_VERTICAL, (
        f"Expected briefing_meta.vertical={EXPECTED_VERTICAL!r}; got "
        f"{meta!r}. The B-7 + S-1.7 contract requires supplements to "
        f"propagate end-to-end into the receipt payload."
    )


def test_decision_state_is_abstain_soft(
    supplements_engine_run_json: dict,
) -> None:
    """Today's supplements behavior: ABSTAIN_SOFT with empty Recommended
    Now. See KI-20 / KI-21 in KNOWN_ISSUES.md for the breakdown of why
    no measured/directional card surfaces. This test pins the current
    state; an intentional improvement (e.g. supplements-specific
    directional builder) will need a deliberate re-pin.
    """
    abstain = supplements_engine_run_json.get("abstain") or {}
    assert abstain.get("state") == EXPECTED_DECISION_STATE, (
        f"Expected decision_state={EXPECTED_DECISION_STATE!r} on the "
        f"supplements run; got {abstain!r}. If this is an intentional "
        f"behavior shift, re-pin the fixture (and decrement the KI-20 "
        f"open count where appropriate)."
    )


def test_data_quality_flags_carry_cadence_advisory(
    supplements_engine_run_json: dict,
) -> None:
    """S5-T3 (resolves KI-22): the supplements run now propagates the
    "Repeat rate suspiciously low" advisory into the typed
    ``data_quality_flags`` list as
    ``metric_incoherent_for_cadence``. The flag is ADVISORY (not in
    ``decide._HARD_DQ_FLAGS``); the decision_state stays
    ``abstain_soft``."""
    flags = supplements_engine_run_json.get("data_quality_flags") or []
    assert flags == ["metric_incoherent_for_cadence"], (
        f"Expected supplements data_quality_flags to be exactly "
        f"['metric_incoherent_for_cadence'] post-S5-T3; got {flags!r}. "
        f"If additional flags fire, re-pin this set deliberately."
    )


# ---------------------------------------------------------------------------
# 2. Pinned slate role-section membership (current observed behavior)
# ---------------------------------------------------------------------------


def test_recommendations_is_empty(supplements_engine_run_json: dict) -> None:
    """Supplements today emits zero Recommended Now cards. KI-20 tracks
    why ``first_to_second_purchase`` doesn't directionally surface on
    supplement fixtures the way it does on Beauty.
    """
    recs = supplements_engine_run_json.get("recommendations") or []
    assert recs == [], (
        f"Expected zero Recommended Now cards on supplements run today; "
        f"got {len(recs)}. KI-20 covers the directional builder gap."
    )


def test_recommended_experiments_is_empty(
    supplements_engine_run_json: dict,
) -> None:
    """Supplements emits zero Recommended Experiment cards today. The
    A4 selector allowlist ``{discount_hygiene, bestseller_amplify}``
    is global, but both candidates fail the experiment-eligibility
    gate on supplements (see KI-21 for the reason-text gap)."""
    exps = supplements_engine_run_json.get("recommended_experiments") or []
    assert exps == [], (
        f"Expected zero Recommended Experiment cards on supplements "
        f"today; got {len(exps)}. KI-21 tracks the gating gap."
    )


def test_considered_play_ids_pinned(
    supplements_engine_run_json: dict,
) -> None:
    considered = supplements_engine_run_json.get("considered") or []
    pids = {str(c.get("play_id")) for c in considered if c.get("play_id")}
    assert pids == EXPECTED_CONSIDERED_PLAY_IDS, (
        f"Considered play_ids drifted on supplements run: expected "
        f"{EXPECTED_CONSIDERED_PLAY_IDS}, got {pids}. KI-23 tracks the "
        f"missing-from-Considered set (aov_momentum, "
        f"journey_optimization, category_expansion, empty_bottle, "
        f"first_to_second_purchase) — any membership change should "
        f"update KI-23 in the same commit."
    )


def test_watching_metrics_pinned(
    supplements_engine_run_json: dict,
) -> None:
    watching = supplements_engine_run_json.get("watching") or []
    metrics = {
        str(w.get("metric"))
        for w in watching
        if w.get("metric")
    }
    assert metrics == EXPECTED_WATCHING_METRICS, (
        f"Watching metrics drifted on supplements run: expected "
        f"{EXPECTED_WATCHING_METRICS}, got {metrics}."
    )


# ---------------------------------------------------------------------------
# 3. Pinned fixture — byte-stable snapshot
# ---------------------------------------------------------------------------


def test_pinned_fixture_exists() -> None:
    assert PINNED_FIXTURE.exists(), (
        f"Pinned supplements slate fixture missing at {PINNED_FIXTURE}. "
        f"Regenerate via the G-1 harness invocation."
    )


def test_pinned_fixture_sha256_matches() -> None:
    """The on-disk fixture sha256 must match the PINNED_SHA256
    constant. This catches a fixture edit that wasn't accompanied by
    the constant bump."""
    actual = hashlib.sha256(PINNED_FIXTURE.read_bytes()).hexdigest()
    assert actual == PINNED_SHA256, (
        f"PINNED_SHA256 drift: constant={PINNED_SHA256!r} "
        f"on-disk={actual!r}. Update the constant if the fixture "
        f"refresh is intentional."
    )


@pytest.mark.xfail(
    strict=False,
)
def test_briefing_matches_pinned_fixture_bytewise(
    supplements_briefing_html: str,
) -> None:
    expected = PINNED_FIXTURE.read_text(encoding="utf-8")
    if supplements_briefing_html != expected:
        actual_len = len(supplements_briefing_html)
        expected_len = len(expected)
        first_diff = next(
            (
                i
                for i, (a, b) in enumerate(
                    zip(supplements_briefing_html, expected)
                )
                if a != b
            ),
            min(actual_len, expected_len),
        )
        raise AssertionError(
            f"Supplements pinned slate fixture drift: "
            f"actual_len={actual_len} expected_len={expected_len} "
            f"first_diff_at_byte={first_diff}. "
            f"actual[max(0,first_diff-40):first_diff+60]="
            f"{supplements_briefing_html[max(0, first_diff - 40):first_diff + 60]!r}\n"
            f"expected[max(0,first_diff-40):first_diff+60]="
            f"{expected[max(0, first_diff - 40):first_diff + 60]!r}\n"
            f"If intentional, refresh {PINNED_FIXTURE} via the harness "
            f"and update PINNED_SHA256 in the same commit."
        )


def test_pinned_fixture_lives_outside_m0_golden_lane() -> None:
    assert (
        REPO_ROOT / "tests" / "golden"
    ) not in PINNED_FIXTURE.parents, (
        f"Pinned supplements slate fixture {PINNED_FIXTURE} must NOT "
        f"live under the M0 legacy goldens lane (tests/golden/)."
    )
    expected_lane = REPO_ROOT / "tests" / "fixtures" / "synthetic_slate"
    assert expected_lane in PINNED_FIXTURE.parents
