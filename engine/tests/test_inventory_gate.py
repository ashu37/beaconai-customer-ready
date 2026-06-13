"""Milestone 5 T5.1 — inventory gate forcing-function tests.

Specifically pins:
- "no inventory data => gate is no-op, log warning, do not block plays"
  (plan M5 T5.1).
- "Below threshold blocks SKU-pushing plays."
- "Non SKU-push plays are not gated."
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import (  # noqa: E402
    EngineRun,
    Inventory,
    PlayCard,
    ReasonCode,
    RevenueRange,
    Scale,
)
from src.guardrails import apply_guardrails, gate_inventory  # noqa: E402


def test_no_inventory_data_is_noop_for_sku_push_play():
    cand = PlayCard(play_id="bestseller_amplify")
    # The forcing function: inventory_metrics=None => no-op, NOT a block.
    assert gate_inventory(cand, None) is None


def test_no_inventory_data_apply_guardrails_does_not_block():
    run = EngineRun(
        recommendations=[
            PlayCard(
                play_id="bestseller_amplify",
                revenue_range=RevenueRange(p50=20_000.0),
            )
        ],
        scale=Scale(monthly_revenue=200_000.0),
    )
    out = apply_guardrails(
        run, inventory_metrics=None, cfg={"INVENTORY_GATE_ENABLED": True}
    )
    rec_ids = [c.play_id for c in out.recommendations]
    assert rec_ids == ["bestseller_amplify"]
    # Critically: no inventory_blocked rejection added.
    rej_codes = [r.reason_code for r in out.considered]
    assert ReasonCode.INVENTORY_BLOCKED not in rej_codes


def test_low_cover_blocks_bestseller_amplify():
    inv = pd.DataFrame({"sku": ["a"], "cover_days": [5.0]})
    cand = PlayCard(play_id="bestseller_amplify")
    rej = gate_inventory(cand, inv, min_cover_days=21)
    assert rej is not None
    assert rej.reason_code == ReasonCode.INVENTORY_BLOCKED


def test_low_cover_does_not_block_non_sku_push_play():
    inv = pd.DataFrame({"sku": ["a"], "cover_days": [5.0]})
    cand = PlayCard(play_id="winback_21_45")
    rej = gate_inventory(cand, inv, min_cover_days=21)
    assert rej is None


def test_candidate_inventory_takes_precedence():
    cand = PlayCard(
        play_id="bestseller_amplify",
        inventory=Inventory(skus=["a"], days_of_cover=2.0),
    )
    rej = gate_inventory(cand, None, min_cover_days=21)
    assert rej is not None
    # The reason_text should include the candidate-level cover number.


def test_candidate_inventory_passes_when_high():
    cand = PlayCard(
        play_id="bestseller_amplify",
        inventory=Inventory(skus=["a"], days_of_cover=60.0),
    )
    assert gate_inventory(cand, None, min_cover_days=21) is None


def test_threshold_inclusive_at_21_days():
    inv = pd.DataFrame({"sku": ["a"], "cover_days": [21.0]})
    cand = PlayCard(play_id="bestseller_amplify")
    assert gate_inventory(cand, inv, min_cover_days=21) is None
    inv2 = pd.DataFrame({"sku": ["a"], "cover_days": [20.999]})
    assert gate_inventory(cand, inv2, min_cover_days=21) is not None


def test_min_cover_days_from_cfg_map():
    inv = pd.DataFrame({"sku": ["a"], "cover_days": [25.0]})
    cand = PlayCard(play_id="bestseller_amplify")
    cfg = {"INVENTORY_MIN_COVER_DAYS": {"default": 30}}
    # cover_days=25 < cfg default=30 => block.
    assert gate_inventory(cand, inv, cfg=cfg) is not None


def test_empty_inventory_dataframe_is_noop():
    inv = pd.DataFrame(columns=["sku", "cover_days"])
    cand = PlayCard(play_id="bestseller_amplify")
    assert gate_inventory(cand, inv, min_cover_days=21) is None


def test_inventory_metrics_without_cover_days_column_is_noop():
    inv = pd.DataFrame({"sku": ["a"], "available": [100]})
    cand = PlayCard(play_id="bestseller_amplify")
    assert gate_inventory(cand, inv, min_cover_days=21) is None
