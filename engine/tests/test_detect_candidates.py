"""Milestone 3 T3.2: detect_candidates contract tests.

These tests assert the M3 detector contract:

- Output shape: list[Candidate], every entry serializable.
- No forbidden fields on the Candidate.
- Registry coverage: one entry per registered play_id.
- cold_start flag is computed and attached.
- audience_overlap is attached and is a dict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.detect import (  # noqa: E402
    Candidate,
    FORBIDDEN_CANDIDATE_FIELDS,
    candidates_to_jsonable,
    detect_candidates,
    detect_cold_start,
)
from src.play_registry import PLAYS  # noqa: E402


ANCHOR = pd.Timestamp("2025-08-25 12:00:00")


def _row(customer_id: str, days_ago: int, **kw):
    created = ANCHOR - pd.Timedelta(days=days_ago)
    base = {
        "Name": kw.get("Name") or f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": created,
        "net_sales": float(kw.get("net_sales", 50.0)),
        "discount_rate": float(kw.get("discount_rate", 0.0)),
        "units_per_order": int(kw.get("units_per_order", 1)),
        "lineitem_any": kw.get("lineitem_any", "Cleanser 50ml"),
        "category": kw.get("category", "skincare"),
    }
    return base


def _build_g(rows):
    df = pd.DataFrame(rows)
    df = df.sort_values(["customer_id", "Created at"]).reset_index(drop=True)
    df["first_seen"] = df.groupby("customer_id")["Created at"].transform("min")
    df["is_repeat"] = (df["Created at"] > df["first_seen"]).astype(int)
    df["prev_purchase"] = df.groupby("customer_id")["Created at"].shift(1)
    df["days_since_last"] = (df["Created at"] - df["prev_purchase"]).dt.days
    # Patch days_since_last for first orders to "days since order"
    fallback = (ANCHOR - df["Created at"]).dt.days
    df["days_since_last"] = df["days_since_last"].fillna(fallback)
    return df


@pytest.fixture(scope="module")
def small_g():
    rows = []
    # 60 winback cohort (last purchase 30 days ago)
    for i in range(60):
        rows.append(_row(f"w{i}", 30, lineitem="Cleanser 50ml"))
    # 50 single-purchase recent customers (frequency_accelerator excluded)
    for i in range(50):
        rows.append(_row(f"s{i}", 10, lineitem="Cream 30ml"))
    # 50 repeat-cohort (2+ orders, last >14d ago)
    for i in range(50):
        rows.append(_row(f"r{i}", 60, lineitem="Toner 50ml"))
        rows.append(_row(f"r{i}", 30, lineitem="Toner 50ml"))
    return _build_g(rows)


def test_detect_candidates_returns_list_of_candidate(small_g):
    cands = detect_candidates(small_g, {"window_days": 28}, {}, PLAYS)
    assert isinstance(cands, list)
    assert all(isinstance(c, Candidate) for c in cands)


def test_detect_candidates_covers_full_registry(small_g):
    cands = detect_candidates(small_g, {"window_days": 28}, {}, PLAYS)
    emitted = {c.play_id for c in cands}
    assert emitted == set(PLAYS.keys()), (
        f"Registry coverage mismatch. Missing: {set(PLAYS.keys()) - emitted}; "
        f"Extra: {emitted - set(PLAYS.keys())}"
    )


def test_detect_candidates_no_forbidden_fields(small_g):
    cands = detect_candidates(small_g, {"window_days": 28}, {}, PLAYS)
    for c in cands:
        d = c.to_dict()
        offenders = [k for k in d.keys() if k in FORBIDDEN_CANDIDATE_FIELDS]
        assert not offenders, f"forbidden fields on Candidate.to_dict(): {offenders}"
        # Sanity: Candidate dataclass attributes must not contain stats either.
        attrs = set(c.__dict__.keys())
        bad = attrs & FORBIDDEN_CANDIDATE_FIELDS
        assert not bad, f"forbidden attributes on Candidate dataclass: {bad}"


def test_detect_candidates_carries_cold_start(small_g):
    cands = detect_candidates(small_g, {"window_days": 28}, {}, PLAYS)
    for c in cands:
        assert isinstance(c.cold_start, bool)
    # All candidates share the same cold_start flag (it is a single-store
    # observation, not a per-play signal).
    flags = {c.cold_start for c in cands}
    assert len(flags) == 1


def test_detect_candidates_carries_overlap_dict(small_g):
    cands = detect_candidates(small_g, {"window_days": 28}, {}, PLAYS)
    for c in cands:
        assert isinstance(c.audience_overlap, dict)
        # The candidate should not appear as its own overlap key.
        assert c.play_id not in c.audience_overlap
        # All values must be in [0, 1].
        for v in c.audience_overlap.values():
            assert 0.0 <= v <= 1.0


def test_detect_candidates_emits_rejection_reasons_not_filtered(small_g):
    cands = detect_candidates(small_g, {"window_days": 28}, {}, PLAYS)
    # The synthetic fixture is small, so several plays should reject;
    # candidates with rejection reasons MUST be present (not filtered).
    rejected = [c for c in cands if c.preliminary_rejection_reason is not None]
    assert rejected, "expected at least one rejected candidate on the small fixture"


def test_detect_candidates_jsonable(small_g, tmp_path):
    cands = detect_candidates(small_g, {"window_days": 28}, {}, PLAYS)
    payload = candidates_to_jsonable(cands)
    s = json.dumps(payload, indent=2, default=str)
    parsed = json.loads(s)
    assert isinstance(parsed, list)
    assert len(parsed) == len(cands)
    keys_seen = set()
    for entry in parsed:
        keys_seen.update(entry.keys())
    expected = {
        "play_id",
        "audience_size",
        "segment_definition",
        "data_used",
        "preliminary_rejection_reason",
        "cold_start",
        "audience_overlap",
    }
    assert keys_seen <= expected, f"unexpected keys: {keys_seen - expected}"


def test_detect_candidates_handles_empty_dataframe():
    g = pd.DataFrame(columns=["customer_id", "Created at"])
    cands = detect_candidates(g, {"window_days": 28}, {}, PLAYS)
    # Shape preserved; every play emits a (rejected) candidate.
    assert len(cands) == len(PLAYS)
    for c in cands:
        # Empty data either rejects or short-circuits; never null.
        assert isinstance(c.audience_size, int)
        assert c.preliminary_rejection_reason is not None


def test_detect_cold_start_short_history_is_true():
    rows = [_row("c1", 5, lineitem="X")]
    g = _build_g(rows)
    assert detect_cold_start(g) is True


def test_detect_cold_start_long_history_is_false():
    rows = [_row("c1", 200), _row("c1", 5)]
    g = _build_g(rows)
    assert detect_cold_start(g) is False


def test_detect_cold_start_empty_is_true():
    assert detect_cold_start(None) is True
    assert detect_cold_start(pd.DataFrame()) is True


def test_detect_cold_start_threshold_override():
    rows = [_row("c1", 50), _row("c1", 5)]
    g = _build_g(rows)
    # Default 90 days -> cold_start True (range = 45 days)
    assert detect_cold_start(g) is True
    # Override to 30 days -> cold_start False
    assert detect_cold_start(g, {"COLD_START_DAYS": 30}) is False
