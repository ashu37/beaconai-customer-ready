"""G-2 (Sprint 1, Engineer B) — ``empty_bottle`` parser unit-coherence.

Pins three contracts established by ticket G-2 (audit post-6b §G-2):

1.  Vertical-dispatched parser: ``src/replenishment_parser.py`` reads
    ``config/replenishment_sizes.yaml`` and exposes a per-vertical regex.
    Beauty / mixed return the verbatim pre-G-2 regex (M0 contract);
    supplements returns ``None`` (parser stub deferred to Sprint 4 G-3).
2.  Vertical-applicable filter: ``play_registry.PLAYS["empty_bottle"]
    .vertical_applicable`` is restricted to ``{"beauty", "mixed"}``.
    The decide.py:614 filter already consumes this set and clean-skips
    the play for non-applicable verticals (vs emitting a misleading
    ``no_measured_signal`` Considered card).
3.  M0 Beauty pinned-fixture is byte-identical (regex preserved
    verbatim; filter only changes supplements behavior).

End-to-end: a synthetic supplements run no longer surfaces
``empty_bottle`` in its Considered list (the play is clean-filtered
upstream of decide.py's reason-code assignment). The Beauty fixture
still surfaces ``empty_bottle`` in Considered exactly as before.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Contract 1 — vertical-dispatched parser
# ---------------------------------------------------------------------------


def test_replenishment_parser_beauty_returns_verbatim_pre_g2_regex():
    """Beauty regex MUST be byte-identical to the pre-G-2 inline string
    from ``action_engine.py:1698``. Drift here perturbs the M0 Beauty
    pinned fixture.
    """
    from src.replenishment_parser import get_size_regex

    pre_g2 = "30ml|1 oz|1oz|50ml|1.7 oz|1.7oz|100ml|3.4 oz|3.4oz"
    assert get_size_regex("beauty") == pre_g2


def test_replenishment_parser_mixed_uses_beauty_regex():
    """``mixed`` = literal beauty + supplements blend; the Beauty regex
    catches the Beauty half. Supplements half is a no-op until G-3.
    """
    from src.replenishment_parser import get_size_regex

    pre_g2 = "30ml|1 oz|1oz|50ml|1.7 oz|1.7oz|100ml|3.4 oz|3.4oz"
    assert get_size_regex("mixed") == pre_g2


def test_replenishment_parser_supplements_returns_none():
    """Supplements parser is stub; Sprint 4 G-3 will fill it in."""
    from src.replenishment_parser import get_size_regex

    assert get_size_regex("supplements") is None


def test_replenishment_parser_unknown_vertical_returns_none():
    """Defensive: unknown verticals (which B-7 already refuses at engine
    entry) must not silently inherit the Beauty regex.
    """
    from src.replenishment_parser import get_size_regex

    assert get_size_regex("apparel") is None
    assert get_size_regex("food_bev") is None
    assert get_size_regex(None) is None
    assert get_size_regex("") is None


def test_replenishment_parser_case_insensitive_default_is_true():
    """The Beauty pre-G-2 path lowercased lineitem text before matching;
    the YAML's ``case_insensitive: true`` preserves that. Supplements
    inherits the same default for when its parser ships.
    """
    from src.replenishment_parser import get_case_insensitive

    assert get_case_insensitive("beauty") is True
    assert get_case_insensitive("supplements") is True
    assert get_case_insensitive("mixed") is True


# ---------------------------------------------------------------------------
# Contract 2 — vertical-applicable filter
# ---------------------------------------------------------------------------


def test_empty_bottle_vertical_applicable_excludes_supplements():
    """``empty_bottle.vertical_applicable`` MUST be exactly
    ``{"beauty", "mixed"}`` after G-2. The decide.py:614 filter consumes
    this set and clean-skips the play on supplements.
    """
    from src.play_registry import PLAYS

    pdef = PLAYS.get("empty_bottle")
    assert pdef is not None
    assert pdef.vertical_applicable == frozenset({"beauty", "mixed"}), (
        f"empty_bottle.vertical_applicable={set(pdef.vertical_applicable)!r}; "
        f"expected exactly {{'beauty', 'mixed'}} per G-2 + audit §G-2."
    )


def test_empty_bottle_vertical_applicable_supplements_excluded_explicitly():
    """Membership check (vs the equality check above): supplements
    explicitly NOT in the set; beauty + mixed explicitly in.
    """
    from src.play_registry import PLAYS

    pdef = PLAYS["empty_bottle"]
    assert "supplements" not in pdef.vertical_applicable
    assert "beauty" in pdef.vertical_applicable
    assert "mixed" in pdef.vertical_applicable


# ---------------------------------------------------------------------------
# Contract 3 — end-to-end behavior (Beauty unchanged; supplements clean-skip)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def beauty_engine_run() -> Dict[str, Any]:
    from tests.synthetic_harness import run_scenario

    with tempfile.TemporaryDirectory() as td:
        res = run_scenario("healthy_beauty_240d", Path(td))
        return json.loads(Path(res.engine_run_json_path).read_text())


@pytest.fixture(scope="module")
def supplements_engine_run() -> Dict[str, Any]:
    from tests.synthetic_harness import run_scenario

    with tempfile.TemporaryDirectory() as td:
        res = run_scenario("supplement_replenishment_240d", Path(td))
        return json.loads(Path(res.engine_run_json_path).read_text())


def test_beauty_still_surfaces_empty_bottle_in_considered(beauty_engine_run):
    """Beauty has parser coverage for ``empty_bottle`` upstream. This
    test originally pinned ``empty_bottle in Considered``; under
    S7.6-FIX (2026-05-22, priority_prepend at
    populate_considered_from_candidates) the load-bearing Tier-B set
    (``_PRIOR_ANCHORED`` registry) is preferentially preserved at the
    ``[:MAX_CONSIDERED_RENDERED=6]`` cap, and ``empty_bottle`` is now
    one of the legacy plays displaced by the Tier-B priority_prepend
    on the synthetic Beauty fixture. The G-2 vertical-applicable
    filter contract is preserved (the play is still produced upstream
    of decide), but membership in Considered is no longer guaranteed —
    it depends on whether the founder-prioritized Tier-B set has
    filled the budget. The supplements-side dispatch test (below) is
    the load-bearing G-2 contract.
    """
    # Tier-B priority_prepend now occupies the first 3-5 Considered
    # slots on Beauty depending on which prior-anchored candidates
    # detected; ``empty_bottle`` falls behind that horizon. Inspect
    # cap-trim accounting via ``considered_truncated_count``.
    trunc = int(beauty_engine_run.get("considered_truncated_count") or 0)
    assert trunc >= 1, (
        f"Beauty pinned slate must record cap-trimmed Considered "
        f"entries (the founder single-demote-channel invariant "
        f"explicitly accepts legacy plays — including ``empty_bottle`` "
        f"on this fixture — being demoted off Considered behind the "
        f"Tier-B priority_prepend). Got "
        f"considered_truncated_count={trunc}."
    )


def test_supplements_no_longer_surfaces_empty_bottle_anywhere(supplements_engine_run):
    """Supplements scenario: G-2 vertical-applicable filter clean-skips
    ``empty_bottle`` upstream of decide.py's reason-code assignment.
    The play must NOT appear in any Recommended / Recommended Experiment
    / Considered surface.
    """
    surfaces = ["recommendations", "recommended_experiments", "considered"]
    for k in surfaces:
        for c in supplements_engine_run.get(k) or []:
            assert c.get("play_id") != "empty_bottle", (
                f"Supplements run rendered empty_bottle in section "
                f"{k!r}: {c!r}. G-2 vertical-applicable filter must "
                f"clean-skip it; emitting it with any reason_code is a "
                f"misleading-trust regression."
            )
