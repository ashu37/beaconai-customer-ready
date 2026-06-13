"""Milestone 3 T3.5: pure-function tests for audience overlap.

The overlap function is unit-tested against:

- disjoint sets (overlap = 0)
- identical sets (overlap = 1)
- partial overlap
- empty sets
- single-pair / multi-play registries
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.detect import compute_audience_overlap, jaccard  # noqa: E402


# ---------------------------------------------------------------------------
# jaccard()
# ---------------------------------------------------------------------------


def test_jaccard_identical_sets_is_one():
    s = {"a", "b", "c"}
    assert jaccard(s, s) == 1.0


def test_jaccard_disjoint_sets_is_zero():
    a = {"a", "b", "c"}
    b = {"x", "y", "z"}
    assert jaccard(a, b) == 0.0


def test_jaccard_partial_overlap():
    a = {"a", "b", "c"}
    b = {"b", "c", "d"}
    # |intersect|=2, |union|=4 -> 0.5
    assert jaccard(a, b) == 0.5


def test_jaccard_subset_overlap():
    a = {"a", "b"}
    b = {"a", "b", "c", "d"}
    # |intersect|=2, |union|=4 -> 0.5
    assert jaccard(a, b) == 0.5


def test_jaccard_both_empty_returns_zero():
    assert jaccard(set(), set()) == 0.0


def test_jaccard_one_empty_returns_zero():
    assert jaccard({"a"}, set()) == 0.0
    assert jaccard(set(), {"b"}) == 0.0


def test_jaccard_is_symmetric():
    a = {"x", "y", "z"}
    b = {"y", "z", "w"}
    assert jaccard(a, b) == jaccard(b, a)


# ---------------------------------------------------------------------------
# compute_audience_overlap()
# ---------------------------------------------------------------------------


def test_compute_overlap_three_plays_pairwise():
    audiences = {
        "a": {"c1", "c2", "c3"},
        "b": {"c2", "c3", "c4"},
        "c": {"c5"},
    }
    out = compute_audience_overlap(audiences)
    # Self-pairs are omitted.
    assert "a" not in out["a"]
    assert "b" not in out["b"]
    # a-b: |{c2,c3}|/|{c1,c2,c3,c4}| = 2/4 = 0.5
    assert out["a"]["b"] == 0.5
    # a-c: disjoint
    assert out["a"]["c"] == 0.0
    # b-c: disjoint
    assert out["b"]["c"] == 0.0


def test_compute_overlap_keys_match_input():
    audiences = {"x": {"1", "2"}, "y": {"2", "3"}}
    out = compute_audience_overlap(audiences)
    assert set(out.keys()) == {"x", "y"}
    assert set(out["x"].keys()) == {"y"}
    assert set(out["y"].keys()) == {"x"}


def test_compute_overlap_empty_input():
    assert compute_audience_overlap({}) == {}


def test_compute_overlap_single_play():
    out = compute_audience_overlap({"only": {"a", "b"}})
    # Single play -> no pairs.
    assert out == {"only": {}}


def test_compute_overlap_all_empty_audiences():
    audiences = {"a": set(), "b": set(), "c": set()}
    out = compute_audience_overlap(audiences)
    for pid in ("a", "b", "c"):
        for other, val in out[pid].items():
            assert val == 0.0


def test_compute_overlap_treats_missing_audience_as_empty():
    """If a value is None (defensive), treat as empty set."""

    audiences = {"a": {"x"}, "b": None}  # type: ignore[dict-item]
    out = compute_audience_overlap(audiences)
    assert out["a"]["b"] == 0.0
    assert out["b"]["a"] == 0.0


def test_compute_overlap_is_symmetric():
    audiences = {
        "p1": {"c1", "c2", "c3", "c4"},
        "p2": {"c3", "c4", "c5"},
    }
    out = compute_audience_overlap(audiences)
    assert out["p1"]["p2"] == out["p2"]["p1"]
