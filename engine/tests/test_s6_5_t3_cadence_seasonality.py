"""Sprint 6.5 Ticket T3 — cadence baseline + seasonality calendar lookup.

Covers (per IM plan §S6.5-T3, 14 items):

1.  Cadence median computed on Beauty skincare class — envelope [20, 60].
2.  Cadence median computed on supplements protein class — envelope
    [40, 120] OR INSUFFICIENT_DATA on the fixture.
3.  Below-N=30 class returns ``INSUFFICIENT_DATA`` and no entry in the
    per-class median map.
4.  Pure-pandas implementation — ``cadence.py`` does not import the
    banned ML modules (lifelines / sklearn / statsmodels / implicit /
    lightfm). D-6 invariant.
5.  Seasonality lookup: 2026-11-25 + beauty/skincare → BFCM_tail.
6.  Seasonality lookup: 2026-05-05 + beauty → Mothers_Day.
7.  Seasonality lookup: 2026-07-15 + supplements → no active window.
8.  Seasonality lookup: 2026-01-10 + supplements/multivitamin →
    January_resolution.
9.  ``expected_lift_range`` always ``[low, high]`` (never a point) for
    every YAML window AND on every active-context return.
10. ``source_artifact`` resolves to a file path under the
    config/priors_sources/seasonality/ directory.
11. Seasonality lookup produces annotations only — NEVER a revenue
    multiplier field on ``StoreProfile``.
12. Flag-OFF parity: no consumer reads cadence/seasonality at T3, so
    pinned fixtures (probed via ``engine_run.store_profile``-absent on
    flag OFF) stay byte-identical. Covered by the broader fixture-pin
    tests in the suite; here we assert the local invariant: the
    ``EngineRun.store_profile`` slot defaults to ``None`` on flag OFF.
13. YAML schema pin: exactly 5 named windows.
14. Calendar windows produce annotations only (no p-value adjustment).
    Asserted by checking the rendered context has no
    ``p_value_adjust`` / ``revenue_multiplier`` style fields.

Founder envelope acceptance criteria (from prompt):
- Beauty fixture: cadence skincare median inside [20, 60] days.
- Supplements fixture: cadence primary class inside [40, 120] OR
  INSUFFICIENT_DATA.
- 2026-05-17 (today) Mothers_Day closed; lookup returns no active
  window for that date.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.profile import build_store_profile  # noqa: E402
from src.profile.builder import load_subvertical_taxonomy  # noqa: E402
from src.profile.cadence import (  # noqa: E402
    build_subvertical_sku_assignment,
    compute_cadence_baseline,
)
from src.profile.seasonality import (  # noqa: E402
    _SEASONALITY_YAML_PATH,
    load_seasonality_calendars,
    lookup_active_seasonality,
)


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _order(cid: str, product: str, days_ago: int, *, net_sales: float = 50.0):
    return {
        "Name": f"#{cid}-{days_ago}",
        "customer_id": str(cid),
        "Created at": ANCHOR - pd.Timedelta(days=days_ago),
        "net_sales": float(net_sales),
        "lineitem_any": product,
        "product": product,
    }


def _df(rows):
    return pd.DataFrame(rows).reset_index(drop=True)


def _beauty_skincare_fixture(n_customers: int = 40, gap_days: int = 30):
    """N customers, 3 in-class orders each at fixed gap; expected median ~gap_days."""
    rows = []
    products = ["Vitamin C Serum 30ml", "Hyaluronic Acid Moisturizer", "Niacinamide Cleanser"]
    for i in range(n_customers):
        for k, days_ago in enumerate((200, 200 - gap_days, 200 - 2 * gap_days)):
            rows.append(_order(f"c{i}", products[k % len(products)], days_ago))
    return _df(rows)


def _supplements_protein_fixture(n_customers: int = 40, gap_days: int = 60):
    rows = []
    products = ["Whey Protein Isolate 1kg", "Plant Protein Blend", "Casein Protein Powder"]
    for i in range(n_customers):
        for k, days_ago in enumerate((200, 200 - gap_days, 200 - 2 * gap_days)):
            rows.append(_order(f"s{i}", products[k % len(products)], days_ago))
    return _df(rows)


def _build_assignment(df: pd.DataFrame, vertical: str):
    return build_subvertical_sku_assignment(df, vertical, load_subvertical_taxonomy())


# ---------------------------------------------------------------------------
# 1) Cadence — beauty skincare envelope
# ---------------------------------------------------------------------------


def test_cadence_beauty_skincare_in_envelope():
    df = _beauty_skincare_fixture(n_customers=40, gap_days=30)
    cadence = compute_cadence_baseline(df, _build_assignment(df, "beauty"))
    assert cadence.detection_status == "COMPUTED"
    skincare = cadence.median_reorder_days_by_sku_class.get("skincare")
    assert skincare is not None, cadence
    assert 20 <= skincare <= 60, skincare
    assert cadence.method_by_sku_class.get("skincare") == "empirical_median"


# ---------------------------------------------------------------------------
# 2) Cadence — supplements protein envelope OR INSUFFICIENT_DATA
# ---------------------------------------------------------------------------


def test_cadence_supplements_protein_in_envelope_or_insufficient():
    df = _supplements_protein_fixture(n_customers=40, gap_days=60)
    cadence = compute_cadence_baseline(df, _build_assignment(df, "supplements"))
    protein = cadence.median_reorder_days_by_sku_class.get("protein")
    method = cadence.method_by_sku_class.get("protein")
    if protein is None:
        assert method == "INSUFFICIENT_DATA"
    else:
        assert 40 <= protein <= 120, protein
        assert method == "empirical_median"


# ---------------------------------------------------------------------------
# 3) Below-N=30 class -> INSUFFICIENT_DATA, no median entry
# ---------------------------------------------------------------------------


def test_cadence_below_n30_returns_insufficient_data():
    df = _beauty_skincare_fixture(n_customers=10, gap_days=30)
    cadence = compute_cadence_baseline(df, _build_assignment(df, "beauty"))
    assert "skincare" not in cadence.median_reorder_days_by_sku_class
    assert cadence.method_by_sku_class.get("skincare") == "INSUFFICIENT_DATA"
    assert cadence.detection_status == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# 4) Pure-pandas D-6 invariant
# ---------------------------------------------------------------------------


def test_cadence_module_has_no_banned_ml_imports():
    source = (REPO_ROOT / "src" / "profile" / "cadence.py").read_text(encoding="utf-8")
    banned = ("lifelines", "sklearn", "statsmodels", "implicit", "lightfm")
    for mod in banned:
        assert f"import {mod}" not in source, mod
        assert f"from {mod}" not in source, mod


# ---------------------------------------------------------------------------
# 5) Seasonality lookup — BFCM_tail
# ---------------------------------------------------------------------------


def test_seasonality_bfcm_tail_active_on_nov25():
    ctx = lookup_active_seasonality(date(2026, 11, 25), "beauty", "skincare")
    assert ctx.active_window_name == "BFCM_tail"
    assert ctx.detection_status == "ACTIVE"
    assert ctx.expected_lift_direction == "+"


# ---------------------------------------------------------------------------
# 6) Seasonality lookup — Mothers_Day active 2026-05-05
# ---------------------------------------------------------------------------


def test_seasonality_mothers_day_active_on_may5():
    ctx = lookup_active_seasonality(date(2026, 5, 5), "beauty", "skincare")
    assert ctx.active_window_name == "Mothers_Day"
    assert ctx.detection_status == "ACTIVE"


def test_seasonality_mothers_day_closed_today_per_prompt_envelope():
    # Founder envelope check #3: Mothers_Day closed by 2026-05-17.
    ctx = lookup_active_seasonality(date(2026, 5, 17), "beauty", "skincare")
    assert ctx.active_window_name != "Mothers_Day"


# ---------------------------------------------------------------------------
# 7) Seasonality — no active window mid-July supplements
# ---------------------------------------------------------------------------


def test_seasonality_no_active_window_mid_july_supplements():
    ctx = lookup_active_seasonality(date(2026, 7, 15), "supplements", "protein")
    assert ctx.active_window_name is None
    assert ctx.detection_status == "NO_ACTIVE_WINDOW"


# ---------------------------------------------------------------------------
# 8) Seasonality — January_resolution + supplements/multivitamin
# ---------------------------------------------------------------------------


def test_seasonality_january_resolution_supplements_multivitamin():
    ctx = lookup_active_seasonality(date(2026, 1, 10), "supplements", "multivitamin")
    assert ctx.active_window_name == "January_resolution"
    assert ctx.detection_status == "ACTIVE"


# ---------------------------------------------------------------------------
# 9) expected_lift_range always [low, high] shape
# ---------------------------------------------------------------------------


def test_every_window_expected_lift_range_is_pair():
    cfg = load_seasonality_calendars()
    windows = cfg.get("windows") or []
    assert len(windows) == 5
    for w in windows:
        rng = w.get("expected_lift_range")
        assert isinstance(rng, list) and len(rng) == 2, (w.get("name"), rng)
        low, high = rng
        assert isinstance(low, (int, float)) and isinstance(high, (int, float))
        assert low <= high


def test_active_context_expected_lift_range_is_pair():
    ctx = lookup_active_seasonality(date(2026, 11, 25), "beauty", "skincare")
    assert isinstance(ctx.expected_lift_range, list) and len(ctx.expected_lift_range) == 2


# ---------------------------------------------------------------------------
# 10) source_artifact resolves to a memo file under priors_sources/seasonality/
# ---------------------------------------------------------------------------


def test_source_artifact_resolves_to_existing_memo_file():
    ctx = lookup_active_seasonality(date(2026, 11, 25), "beauty", "skincare")
    assert ctx.source_artifact is not None
    p = REPO_ROOT / ctx.source_artifact
    assert p.exists(), p
    assert "priors_sources/seasonality/" in ctx.source_artifact


# ---------------------------------------------------------------------------
# 11) Seasonality never adds a revenue multiplier to the profile
# ---------------------------------------------------------------------------


def test_seasonality_context_carries_no_revenue_multiplier_field():
    ctx = lookup_active_seasonality(date(2026, 11, 25), "beauty", "skincare")
    forbidden = (
        "revenue_multiplier",
        "p_value_adjust",
        "p_value_multiplier",
        "lift_multiplier",
        "scale_factor",
    )
    for f in forbidden:
        assert not hasattr(ctx, f), f


# ---------------------------------------------------------------------------
# 12) Flag-OFF parity — engine_run.store_profile slot is None on flag OFF
# ---------------------------------------------------------------------------


def test_engine_run_store_profile_slot_defaults_to_none_under_flag_off():
    # Flag is default OFF; pinned fixtures' engine_run.json round-trips
    # with ``store_profile=None``. Sanity-check that the slot still
    # accepts ``None`` and round-trips.
    from src.engine_run import EngineRun, _from_dict_store_profile_payload
    assert _from_dict_store_profile_payload(None) is None
    # The build does not break with no store_profile key.
    er = EngineRun()
    assert getattr(er, "store_profile", "missing") is None


# ---------------------------------------------------------------------------
# 13) YAML schema pin — exactly 5 named windows
# ---------------------------------------------------------------------------


def test_yaml_has_exactly_five_named_windows():
    cfg = load_seasonality_calendars()
    names = {w.get("name") for w in (cfg.get("windows") or [])}
    expected = {
        "BFCM_tail",
        "January_resolution",
        "Mothers_Day",
        "Back_to_school",
        "Summer_skin",
    }
    assert names == expected, names


def test_seasonality_yaml_path_is_pinned():
    assert _SEASONALITY_YAML_PATH.exists()
    assert _SEASONALITY_YAML_PATH.name == "seasonality_calendars.yaml"


# ---------------------------------------------------------------------------
# 14) Annotations only — every YAML window tagged heuristic_unvalidated
# ---------------------------------------------------------------------------


def test_every_yaml_window_tagged_heuristic_unvalidated():
    cfg = load_seasonality_calendars()
    for w in cfg.get("windows") or []:
        assert w.get("validation_status") == "heuristic_unvalidated", w.get("name")


# ---------------------------------------------------------------------------
# End-to-end: build_store_profile populates cadence + seasonality
# ---------------------------------------------------------------------------


def test_build_store_profile_populates_cadence_and_seasonality_e2e():
    df = _beauty_skincare_fixture(n_customers=40, gap_days=30)
    profile = build_store_profile(
        df,
        cfg={"VERTICAL_MODE": "beauty", "RUN_DATE": "2026-11-25"},
        store_id="t3_beauty_e2e",
    )
    assert profile.cadence.detection_status == "COMPUTED"
    assert "skincare" in profile.cadence.median_reorder_days_by_sku_class
    assert profile.seasonality.active_window_name == "BFCM_tail"
    assert profile.seasonality.detection_status == "ACTIVE"


def test_build_store_profile_seasonality_inactive_on_today():
    df = _beauty_skincare_fixture(n_customers=40, gap_days=30)
    profile = build_store_profile(
        df,
        cfg={"VERTICAL_MODE": "beauty", "RUN_DATE": "2026-05-17"},
        store_id="t3_beauty_today",
    )
    # Mothers_Day (05-01..05-12) closed by 2026-05-17.
    assert profile.seasonality.active_window_name != "Mothers_Day"
