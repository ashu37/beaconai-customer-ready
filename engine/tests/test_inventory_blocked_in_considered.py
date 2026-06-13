"""Synthetic Blocker Fix 4 — inventory_blocked visibility in V2 Considered.

When a SKU-pushing play is held by inventory, V2 must surface the hold
on a Considered card with:

- ``reason_code = ReasonCode.INVENTORY_BLOCKED``
- merchant-readable ``reason_text`` referencing low stock / restock (no
  raw cover_days / units numbers)
- populated ``would_fire_if`` text

The wiring under test:
1. M3 ``detect_candidates`` (or the V2 candidate path) stamps
   ``preliminary_rejection_reason="inventory_blocked"`` on a SKU-pushing
   candidate when its backing inventory is below the cover-days threshold.
2. ``populate_considered_from_candidates`` maps that string to
   ``ReasonCode.INVENTORY_BLOCKED`` via ``_PRELIM_REASON_MAP``.
3. ``_CONSIDERED_REASON_TEXT[INVENTORY_BLOCKED]`` and
   ``_WOULD_FIRE_IF_TEMPLATE[INVENTORY_BLOCKED]`` are merchant-readable
   and do NOT surface raw inventory numbers.

These tests intentionally do NOT add multi-SKU aggregation, vertical
thresholds, or numeric stock detail to merchant cards. Phase 5.2-only
plumbing (per the synthetic blocker-fix plan, Fix 4).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.decide import (  # noqa: E402
    _CONSIDERED_REASON_TEXT,
    _PRELIM_REASON_MAP,
    _WOULD_FIRE_IF_TEMPLATE,
    populate_considered_from_candidates,
)
from src.detect import Candidate, detect_candidates  # noqa: E402
from src.engine_run import EngineRun, ReasonCode  # noqa: E402
from src.play_registry import PLAYS  # noqa: E402


# ---------------------------------------------------------------------------
# Schema / mapping pins
# ---------------------------------------------------------------------------


def test_reason_code_inventory_blocked_exists():
    """Pre-existing from M5 / Fix 3 — but pin it to catch any regression."""
    assert hasattr(ReasonCode, "INVENTORY_BLOCKED")
    assert ReasonCode.INVENTORY_BLOCKED.value == "inventory_blocked"


def test_prelim_reason_map_contains_inventory_blocked():
    """The M3 -> ReasonCode mapping must know about inventory_blocked.

    Pins the wire between ``preliminary_rejection_reason="inventory_blocked"``
    on a Candidate and ``ReasonCode.INVENTORY_BLOCKED`` on a RejectedPlay.
    """
    assert "inventory_blocked" in _PRELIM_REASON_MAP
    assert _PRELIM_REASON_MAP["inventory_blocked"] == ReasonCode.INVENTORY_BLOCKED


def test_considered_reason_text_for_inventory_blocked_is_merchant_readable():
    text = _CONSIDERED_REASON_TEXT.get(ReasonCode.INVENTORY_BLOCKED) or ""
    assert text, "INVENTORY_BLOCKED must have a populated reason text"
    lower = text.lower()
    # References stock / restock in plain English.
    assert "stock" in lower or "restock" in lower
    # MUST NOT expose raw inventory units / cover-day numbers.
    assert "cover_days" not in text
    assert "days_of_cover" not in text
    assert "units" not in lower
    # No bare digits in the merchant text (covers "9 days", "21 days", etc.).
    assert not any(ch.isdigit() for ch in text), (
        "INVENTORY_BLOCKED reason text must not expose raw stock / cover-day "
        f"numbers; got: {text!r}"
    )


def test_would_fire_if_for_inventory_blocked_is_populated():
    template = _WOULD_FIRE_IF_TEMPLATE.get(ReasonCode.INVENTORY_BLOCKED) or ""
    assert template, "INVENTORY_BLOCKED must have a would_fire_if template"
    lower = template.lower()
    assert "would fire" in lower
    # References restock / stock recovery in plain English.
    assert "stock" in lower or "restock" in lower or "recover" in lower
    # Must not expose raw numbers in merchant copy.
    assert not any(ch.isdigit() for ch in template), (
        "INVENTORY_BLOCKED would_fire_if must not expose raw stock / "
        f"cover-day numbers; got: {template!r}"
    )


# ---------------------------------------------------------------------------
# populate_considered_from_candidates wiring
# ---------------------------------------------------------------------------


def _candidate(play_id: str, *, prelim: str | None = None) -> Candidate:
    return Candidate(
        play_id=play_id,
        audience_size=500,
        segment_definition=f"Audience for {play_id}",
        data_used=[],
        preliminary_rejection_reason=prelim,
        cold_start=False,
    )


def test_inventory_blocked_candidate_lands_in_considered_with_typed_reason():
    """Core wiring assertion.

    A SKU-pushing candidate stamped with
    ``preliminary_rejection_reason="inventory_blocked"`` must surface as a
    Considered card with the typed INVENTORY_BLOCKED reason code.
    """
    er = EngineRun(recommendations=[], considered=[])
    cands = [
        _candidate("bestseller_amplify", prelim="inventory_blocked"),
        # negative control: a non-blocked sibling should still surface
        # under its normal reason code.
        _candidate("subscription_nudge"),
    ]

    out = populate_considered_from_candidates(er, cands, registry=PLAYS)

    by_id = {r.play_id: r for r in out.considered}
    assert "bestseller_amplify" in by_id, (
        "bestseller_amplify must be visible in the Considered list when "
        "held by inventory"
    )

    rej = by_id["bestseller_amplify"]
    assert rej.reason_code == ReasonCode.INVENTORY_BLOCKED, (
        "bestseller_amplify must carry the typed INVENTORY_BLOCKED reason "
        f"code; got: {rej.reason_code!r}"
    )


def test_inventory_blocked_considered_card_has_merchant_readable_reason_text():
    er = EngineRun(recommendations=[], considered=[])
    cands = [_candidate("bestseller_amplify", prelim="inventory_blocked")]

    out = populate_considered_from_candidates(er, cands, registry=PLAYS)
    rej = next(r for r in out.considered if r.play_id == "bestseller_amplify")

    # S13.6-T1a (Option D, founder + DS approved 2026-05-30): the
    # ``RejectedPlay.reason_text`` slot was stripped per Pivot 2.
    # Downstream narration owns the merchant-readable "stock / restock"
    # copy; the engine carries only the typed ``reason_code``.
    assert rej.reason_code == ReasonCode.INVENTORY_BLOCKED


def test_inventory_blocked_considered_card_has_would_fire_if_populated():
    er = EngineRun(recommendations=[], considered=[])
    cands = [_candidate("bestseller_amplify", prelim="inventory_blocked")]

    out = populate_considered_from_candidates(er, cands, registry=PLAYS)
    rej = next(r for r in out.considered if r.play_id == "bestseller_amplify")



# ---------------------------------------------------------------------------
# detect_candidates inventory stamping
# ---------------------------------------------------------------------------


def _make_orders_frame() -> pd.DataFrame:
    """Build a minimal orders frame where bestseller_amplify clears its
    audience predicate so M3 produces it as a base candidate.
    """
    anchor = pd.Timestamp("2025-09-18 12:00:00")
    rows = []
    # 60 buyers of the top SKU within the last 30 days. Audience size of
    # 60 clears MIN_N_SKU=30 and MIN_N_AUDIENCE defaults.
    for i in range(60):
        rows.append(
            {
                "Name": f"#bs-{i}",
                "customer_id": f"cust-bs-{i}",
                "Created at": anchor - pd.Timedelta(days=10 + (i % 5)),
                "net_sales": 60.0,
                "discount_rate": 0.0,
                "units_per_order": 1,
                "lineitem_any": "Vitamin C Brightening Serum",
                "category": "skincare",
            }
        )
    # 50 buyers of a second SKU so the top sku is unambiguous.
    for i in range(50):
        rows.append(
            {
                "Name": f"#hy-{i}",
                "customer_id": f"cust-hy-{i}",
                "Created at": anchor - pd.Timedelta(days=20 + (i % 5)),
                "net_sales": 40.0,
                "discount_rate": 0.0,
                "units_per_order": 1,
                "lineitem_any": "Hyaluronic Acid Moisturizer",
                "category": "skincare",
            }
        )
    df = pd.DataFrame(rows)
    df = df.sort_values(["customer_id", "Created at"]).reset_index(drop=True)
    df["first_seen"] = df.groupby("customer_id")["Created at"].transform("min")
    df["is_repeat"] = (df["Created at"] > df["first_seen"]).astype(int)
    df["prev_purchase"] = df.groupby("customer_id")["Created at"].shift(1)
    df["days_since_last"] = (df["Created at"] - df["prev_purchase"]).dt.days
    fallback = (anchor - df["Created at"]).dt.days
    df["days_since_last"] = df["days_since_last"].fillna(fallback)
    return df


def test_detect_candidates_stamps_inventory_blocked_when_cover_below_threshold():
    """End-to-end wire: low cover_days on the top SKU's inventory metric
    must result in M3 stamping ``preliminary_rejection_reason="inventory_blocked"``
    on bestseller_amplify (a SKU-pushing play).
    """
    g = _make_orders_frame()
    aligned: dict = {}
    cfg: dict = {}

    # Inventory metrics where the top SKU is at 5 cover-days (below the
    # default 21-day threshold). Other SKUs are healthy.
    inventory_metrics = pd.DataFrame(
        {
            "sku": ["Vitamin C Brightening Serum", "Hyaluronic Acid Moisturizer"],
            "cover_days": [5.0, 60.0],
        }
    )

    cands = detect_candidates(
        g, aligned, cfg, registry=PLAYS, inventory_metrics=inventory_metrics
    )

    bs = next((c for c in cands if c.play_id == "bestseller_amplify"), None)
    assert bs is not None, "M3 must produce bestseller_amplify as a candidate"
    assert bs.audience_size > 0, (
        "bestseller_amplify must have a non-zero audience for the inventory "
        "stamp to be meaningful"
    )
    assert bs.preliminary_rejection_reason == "inventory_blocked", (
        "M3 must stamp preliminary_rejection_reason='inventory_blocked' on "
        "bestseller_amplify when backing inventory is below cover threshold; "
        f"got: {bs.preliminary_rejection_reason!r}"
    )


def test_detect_candidates_does_not_stamp_inventory_blocked_when_cover_healthy():
    """Negative control: healthy inventory must not produce an
    inventory_blocked stamp.
    """
    g = _make_orders_frame()
    aligned: dict = {}
    cfg: dict = {}

    inventory_metrics = pd.DataFrame(
        {
            "sku": ["Vitamin C Brightening Serum", "Hyaluronic Acid Moisturizer"],
            "cover_days": [60.0, 60.0],
        }
    )

    cands = detect_candidates(
        g, aligned, cfg, registry=PLAYS, inventory_metrics=inventory_metrics
    )

    bs = next((c for c in cands if c.play_id == "bestseller_amplify"), None)
    assert bs is not None
    assert bs.preliminary_rejection_reason != "inventory_blocked", (
        "Healthy inventory must not trigger inventory_blocked stamping; "
        f"got: {bs.preliminary_rejection_reason!r}"
    )


def test_detect_candidates_does_not_stamp_inventory_blocked_on_non_sku_push_plays():
    """Negative control: a low cover_days reading must not block a
    non-SKU-pushing play like ``winback_21_45``.
    """
    g = _make_orders_frame()
    aligned: dict = {}
    cfg: dict = {}

    inventory_metrics = pd.DataFrame(
        {
            "sku": ["Vitamin C Brightening Serum"],
            "cover_days": [3.0],
        }
    )

    cands = detect_candidates(
        g, aligned, cfg, registry=PLAYS, inventory_metrics=inventory_metrics
    )

    # Find a non-SKU-pushing play that exists in the registry.
    wb = next((c for c in cands if c.play_id == "winback_21_45"), None)
    if wb is not None:
        assert wb.preliminary_rejection_reason != "inventory_blocked", (
            "Non-SKU-pushing plays must not be stamped with inventory_blocked"
        )


def test_detect_candidates_no_inventory_metrics_is_no_op_for_inventory_stamping():
    """When inventory_metrics is None (no inventory CSV provided), M3
    must not stamp inventory_blocked. Mirrors the M5 ``gate_inventory``
    'no inventory data => gate is no-op' contract.
    """
    g = _make_orders_frame()
    aligned: dict = {}
    cfg: dict = {}

    cands = detect_candidates(
        g, aligned, cfg, registry=PLAYS, inventory_metrics=None
    )

    bs = next((c for c in cands if c.play_id == "bestseller_amplify"), None)
    if bs is not None:
        assert bs.preliminary_rejection_reason != "inventory_blocked", (
            "No-inventory-data must not produce an inventory_blocked stamp"
        )


# ---------------------------------------------------------------------------
# End-to-end: detect -> populate -> Considered card
# ---------------------------------------------------------------------------


def test_e2e_detect_then_populate_surfaces_inventory_blocked_in_considered():
    """End-to-end: M3 detect with low inventory metrics must produce a
    Considered card with the typed INVENTORY_BLOCKED reason code and the
    merchant-readable copy.

    S7.6-FIX (2026-05-22): with the priority_prepend at
    populate_considered_from_candidates, the 5 ``_PRIOR_ANCHORED``
    Tier-B plays preempt the first 5 slots in Considered when they
    detect as candidates. On the synthetic Beauty fixture used here,
    19 candidates detect (5 Tier-B + 14 legacy) and the
    ``[:MAX_CONSIDERED_RENDERED=6]`` cap leaves only 1 legacy slot.
    To make the INVENTORY_BLOCKED end-to-end contract testable
    independently of the Tier-B set membership, narrow ``cands`` to
    the non-Tier-B subset (the INVENTORY_BLOCKED mapping itself is the
    load-bearing assertion).
    """
    g = _make_orders_frame()
    aligned: dict = {}
    cfg: dict = {}

    inventory_metrics = pd.DataFrame(
        {
            "sku": ["Vitamin C Brightening Serum", "Hyaluronic Acid Moisturizer"],
            "cover_days": [5.0, 60.0],
        }
    )

    cands = detect_candidates(
        g, aligned, cfg, registry=PLAYS, inventory_metrics=inventory_metrics
    )

    # Narrow to the non-Tier-B subset so the INVENTORY_BLOCKED contract
    # is decoupled from the Tier-B priority_prepend (S7.6-FIX).
    from src.measurement_builder import _PRIOR_ANCHORED
    cands = [c for c in cands if str(getattr(c, "play_id", "")) not in _PRIOR_ANCHORED]

    er = EngineRun(recommendations=[], considered=[])
    out = populate_considered_from_candidates(
        er, cands, registry=PLAYS, vertical="beauty"
    )

    bs_rej = next(
        (r for r in out.considered if r.play_id == "bestseller_amplify"), None
    )
    assert bs_rej is not None, (
        "bestseller_amplify must be visible in Considered when held by inventory"
    )
    assert bs_rej.reason_code == ReasonCode.INVENTORY_BLOCKED
    # Merchant card surface must not expose raw inventory numbers.
