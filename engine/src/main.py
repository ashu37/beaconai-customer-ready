# src/main.py
from __future__ import annotations
import argparse
from pathlib import Path
from os.path import relpath
import shutil

from .utils import (
    get_config, safe_make_dirs, write_json,
    choose_window, financial_floor,
    kpi_snapshot_with_deltas,
    identity_coverage,
    detect_growth_stage, select_priority_charts, generate_growth_insights,
    calculate_aura_score, enhance_actions_with_health_impact,
)
from .utils import normalize_product_name
import pandas as pd
from .load import (
    load_csv, load_inventory_csv, compute_inventory_metrics,
    load_orders_csv, load_order_items_csv, preprocess
)
from .features import compute_features, aligned_periods_summary
from .contracts import IngestionContract, FeatureContract
# S13.7-T1: src/segments.py retired; build_segments removed.
# Legacy segment CSVs (out_dir/segments/) are superseded by the per-PlayCard
# audience CSVs at data/<store_id>/runs/<run_id>/audiences/.
# src/segments.py raises NotImplementedError("Retired at S13.7-T1; use audience_resolver").
from .charts import generate_charts
from .briefing import render_briefing
from .action_engine import (
    select_actions,
    write_actions_log,
    build_receipts,
    evidence_for_action,
)
from .copykit import render_copy_for_actions
from .validation import DataValidationEngine  # NEW IMPORT
from .engine_run_adapter import build_engine_run_from_legacy  # M1 T1.3
from .engine_run import DecisionState  # B-1: sticky-abstain check
from .store_id import (
    resolve_store_id,
    ensure_store_dir,
    migrate_legacy_recommended_history,
)  # B-4/S-1
from .engine_run import EngineRun, PlayCard, RejectedPlay, WouldBeMeasuredBy
from .memory import (
    RECOMMENDATION_EVENT_VERSION,
    EvidenceSnapshot,
    ExpectedOutcome,
    RecommendationConsideredPayload,
    RecommendationEmittedPayload,
    compute_lineage_id,
    open_memory,
    write_immutable_snapshot,
)


# ---------------------------------------------------------------------------
# S-3 substrate event emission (Sprint 2 closeout)
# ---------------------------------------------------------------------------
#
# Single writer of ``recommendation_emitted`` / ``recommendation_considered``
# event types — see ``tests/test_single_writer_per_event_type.py``.
# Lineage tuple is ``(store_id, play_id, audience_definition_id,
# audience_definition_version)`` per founder decision D-1.
#
# ``audience_definition_id`` falls back to ``PlayCard.audience.id`` (or
# ``RejectedPlay.play_id`` for rejections that did not run an audience
# builder) until S-2/S-3 introduces an explicit audience_definition_id
# field on the Audience dataclass. ``audience_definition_version``
# defaults to 1 in this transition window; it bumps once the audience
# builder pipeline carries the integer per D-1. The founder-defined gap
# is documented in memory.md S-3 prep entry.

#: Default observation window per WouldBeMeasuredBy enum value, in days.
#: Used to default ``ExpectedOutcome.expected_observation_window_days``
#: when a PlayCard does not carry an explicit pre-registered window.
_OUTCOME_WINDOW_DAYS: dict[str, int] = {
    "REPEAT_PURCHASE_IN_30D": 30,
    "EMAIL_ATTRIBUTED_REVENUE_IN_7D": 7,
    "INCREMENTAL_ORDERS_IN_14D": 14,
}

#: Default minimum-interesting effect size, used to default the
#: ``ExpectedOutcome.min_interesting_effect_size`` field at emission.
#: A merchant-relevant 2 percentage-point lift is the working default
#: for the calibration consumer (Phase 9 L-D #1) until per-play
#: pre-registered values are wired through priors.yaml.
_DEFAULT_MIN_EFFECT: float = 0.02


def _audience_definition_id(card: PlayCard | RejectedPlay) -> str:
    """Return a non-empty audience_definition_id for the lineage tuple.

    Falls back to ``audience.id`` when set; otherwise to the play_id so
    the lineage tuple is always shaped (D-1 requires a non-empty
    string). When the audience-builder pipeline gains an explicit
    ``audience_definition_id`` field, swap this resolver to read it
    directly.
    """

    aud = getattr(card, "audience", None)
    aud_id = getattr(aud, "id", None) if aud is not None else None
    if isinstance(aud_id, str) and aud_id:
        return aud_id
    return str(getattr(card, "play_id", "unknown"))


def _audience_definition_version(card: PlayCard | RejectedPlay) -> int:
    """Return the audience_definition_version (D-1).

    Defaults to 1 until the Audience dataclass carries an explicit
    integer field. The founder-defined gap is documented in memory.md.
    """

    return 1


def _evidence_snapshot_for(card: PlayCard, dq_flags: list[str]) -> EvidenceSnapshot:
    """Build a typed EvidenceSnapshot from a PlayCard.

    ``targeting`` plays have ``measurement is None`` per the M4+ hard
    rule; the snapshot accepts ``None`` for ``effect_abs`` and
    ``p_internal`` in that case.
    """

    ec_raw = getattr(card, "evidence_class", None)
    ec_str = str(getattr(ec_raw, "value", ec_raw) or "targeting").lower()
    if ec_str not in ("measured", "directional", "targeting"):
        ec_str = "targeting"

    m = getattr(card, "measurement", None)
    if m is not None:
        window_label = str(getattr(m, "primary_window", None) or "multiwindow")
        effect_abs = getattr(m, "observed_effect", None)
        p_internal = getattr(m, "p_internal", None)
        sample_size = getattr(m, "n", None)
        consistency = getattr(m, "consistency_across_windows", None)
        try:
            multiwindow_agreement = (
                float(consistency) if consistency is not None else None
            )
        except (TypeError, ValueError):
            multiwindow_agreement = None
    else:
        window_label = "multiwindow"
        effect_abs = None
        p_internal = None
        sample_size = None
        multiwindow_agreement = None

    return EvidenceSnapshot(
        evidence_class=ec_str,  # type: ignore[arg-type]
        window_label=window_label,
        effect_abs=(float(effect_abs) if effect_abs is not None else None),
        p_internal=(float(p_internal) if p_internal is not None else None),
        sample_size=(int(sample_size) if sample_size is not None else None),
        multiwindow_agreement=multiwindow_agreement,
        data_quality_flags=list(dq_flags),
        measurement_design_version=1,
    )


def _expected_outcome_for(card: PlayCard) -> ExpectedOutcome:
    """Build a typed ExpectedOutcome (audit L-E pre-registration).

    Direction defaults to ``"increase"`` (every shipped play in the
    registry today predicts an increase in the outcome metric;
    explicit two-sided plays will need to override). The window is
    keyed off the play's ``would_be_measured_by`` enum, defaulting to
    30 days when unset.
    """

    wbmb = getattr(card, "would_be_measured_by", None)
    wbmb_str = str(getattr(wbmb, "value", wbmb) or "REPEAT_PURCHASE_IN_30D")
    window_days = _OUTCOME_WINDOW_DAYS.get(wbmb_str, 30)
    return ExpectedOutcome(
        expected_direction="increase",
        min_interesting_effect_size=_DEFAULT_MIN_EFFECT,
        expected_observation_window_days=window_days,
    )


def _emit_substrate_events(
    *,
    engine_run: EngineRun,
    store_id: str,
    snapshot_path: str | None = None,
    snapshot_sha256: str | None = None,
) -> None:
    """Append recommendation_* events to the per-store memory.db.

    Single writer of ``recommendation_emitted`` and
    ``recommendation_considered`` (plan §8 cross-track coupling).
    Substrate writes are purely additive — caller wraps in try/except
    so a substrate failure cannot crash the engine.

    ``snapshot_path`` / ``snapshot_sha256`` (S-4) are populated on every
    emitted event payload so a downstream auditor can re-hash the
    immutable ``data/<store_id>/runs/<run_id>.json`` and verify the
    bytes match what the engine claimed at emission time.
    """

    run_id = str(getattr(engine_run, "run_id", "") or "")
    dq_flags_raw = list(getattr(engine_run, "data_quality_flags", []) or [])
    dq_flags: list[str] = []
    for f in dq_flags_raw:
        v = getattr(f, "value", f)
        if v is None:
            continue
        dq_flags.append(str(v))

    memory = open_memory(store_id)
    try:
        # Recommended Now
        for card in list(getattr(engine_run, "recommendations", []) or []):
            _emit_one_play_card(
                memory=memory,
                engine_run=engine_run,
                card=card,
                role="recommendation",
                run_id=run_id,
                store_id=store_id,
                dq_flags=dq_flags,
                snapshot_path=snapshot_path,
                snapshot_sha256=snapshot_sha256,
            )
        # Recommended Experiment
        for card in list(getattr(engine_run, "recommended_experiments", []) or []):
            _emit_one_play_card(
                memory=memory,
                engine_run=engine_run,
                card=card,
                role="experiment",
                run_id=run_id,
                store_id=store_id,
                dq_flags=dq_flags,
                snapshot_path=snapshot_path,
                snapshot_sha256=snapshot_sha256,
            )
        # Considered (rejected)
        for rej in list(getattr(engine_run, "considered", []) or []):
            _emit_one_rejected_play(
                memory=memory,
                rej=rej,
                run_id=run_id,
                store_id=store_id,
                snapshot_path=snapshot_path,
                snapshot_sha256=snapshot_sha256,
            )
    finally:
        memory.close()


def _emit_one_play_card(
    *,
    memory,
    engine_run: EngineRun,
    card: PlayCard,
    role: str,
    run_id: str,
    store_id: str,
    dq_flags: list[str],
    snapshot_path: str | None = None,
    snapshot_sha256: str | None = None,
) -> None:
    play_id = str(getattr(card, "play_id", "") or "")
    if not play_id:
        return
    aud_def_id = _audience_definition_id(card)
    aud_def_ver = _audience_definition_version(card)
    lineage_id = compute_lineage_id(store_id, play_id, aud_def_id, aud_def_ver)

    payload = RecommendationEmittedPayload(
        event_version=RECOMMENDATION_EVENT_VERSION,
        run_id=run_id,
        lineage_id=lineage_id,
        store_id=store_id,
        play_id=play_id,
        audience_definition_id=aud_def_id,
        audience_definition_version=aud_def_ver,
        role="experiment" if role == "experiment" else "recommendation",
        evidence_snapshot=_evidence_snapshot_for(card, dq_flags),
        expected_outcome=_expected_outcome_for(card),
        snapshot_path=snapshot_path,
        snapshot_sha256=snapshot_sha256,
    )
    memory.append_event(
        event_type="recommendation_emitted",
        payload=payload.to_dict(),
        lineage_id=lineage_id,
        run_id=run_id,
        play_id=play_id,
        audience_definition_id=aud_def_id,
        audience_definition_version=aud_def_ver,
        event_version=RECOMMENDATION_EVENT_VERSION,
    )


def _emit_one_rejected_play(
    *,
    memory,
    rej: RejectedPlay,
    run_id: str,
    store_id: str,
    snapshot_path: str | None = None,
    snapshot_sha256: str | None = None,
) -> None:
    play_id = str(getattr(rej, "play_id", "") or "")
    if not play_id:
        return
    aud_def_id = _audience_definition_id(rej)
    aud_def_ver = _audience_definition_version(rej)
    lineage_id = compute_lineage_id(store_id, play_id, aud_def_id, aud_def_ver)

    rc = getattr(rej, "reason_code", None)
    rc_str = str(getattr(rc, "value", rc) or "no_measured_signal")

    payload = RecommendationConsideredPayload(
        event_version=RECOMMENDATION_EVENT_VERSION,
        run_id=run_id,
        lineage_id=lineage_id,
        store_id=store_id,
        play_id=play_id,
        audience_definition_id=aud_def_id,
        audience_definition_version=aud_def_ver,
        reason_code=rc_str,
        # A held play may not have run a measurement; leave None until a
        # held-with-measurement signal exists. (held_reason_detail on
        # RejectedPlay is the Stop-Coding-Line typed slot for the
        # numeric context behind reason_code.)
        evidence_snapshot=None,
        expected_outcome=None,
        snapshot_path=snapshot_path,
        snapshot_sha256=snapshot_sha256,
    )
    memory.append_event(
        event_type="recommendation_considered",
        payload=payload.to_dict(),
        lineage_id=lineage_id,
        run_id=run_id,
        play_id=play_id,
        audience_definition_id=aud_def_id,
        audience_definition_version=aud_def_ver,
        event_version=RECOMMENDATION_EVENT_VERSION,
    )


def debug_dataframe_consistency(df, g, aligned, df_for_charts=None, receipts_dir="receipts"):
    """Debug dataframe inconsistencies that cause erroneous results"""
    import json as _json
    from pathlib import Path as _Path
    import pandas as _pd
    debug_report = {}

    print("🔍 DATAFRAME CONSISTENCY DEBUG")
    print("=" * 50)

    # 1. Basic shape comparison
    debug_report['shapes'] = {
        'df_raw_rows': len(df),
        'g_features_rows': len(g),
        'df_charts_rows': len(df_for_charts) if df_for_charts is not None else None
    }
    print(f"📊 Shapes: df={len(df)}, g={len(g)}, charts={len(df_for_charts) if df_for_charts is not None else 'None'}")

    # 2. Date range comparison
    try:
        df_dates = _pd.to_datetime(df['Created at'], errors='coerce')
        g_dates = _pd.to_datetime(g['Created at'], errors='coerce') if 'Created at' in g.columns else _pd.Series([], dtype='datetime64[ns]')

        debug_report['date_ranges'] = {
            'df_min': df_dates.min(),
            'df_max': df_dates.max(),
            'g_min': g_dates.min() if len(g_dates) else None,
            'g_max': g_dates.max() if len(g_dates) else None,
            'anchor': aligned.get('anchor')
        }

        print(f"📅 Date ranges:")
        print(f"   df: {df_dates.min()} to {df_dates.max()}")
        print(f"   g:  {g_dates.min() if len(g_dates) else None} to {g_dates.max() if len(g_dates) else None}")
        print(f"   anchor: {aligned.get('anchor')}")

        # Check for date misalignment
        try:
            if len(g_dates) and abs((df_dates.max() - g_dates.max()).days) > 0:
                print("⚠️  DATE MISMATCH between df and g!")
        except Exception:
            pass
    except Exception as e:
        print(f"❌ Date comparison failed: {e}")

    # 3. Customer identity comparison
    try:
        from .utils import standardize_customer_key

        df_customers = standardize_customer_key(df).dropna().unique()
        g_customers = g['customer_id'].dropna().unique() if 'customer_id' in g.columns else []

        debug_report['customers'] = {
            'df_unique': int(len(df_customers)),
            'g_unique': int(len(g_customers)),
            'overlap': int(len(set(df_customers) & set(g_customers))) if len(g_customers) > 0 else 0
        }

        print(f"👥 Customer counts: df={len(df_customers)}, g={len(g_customers)}")
        if len(g_customers) > 0 and len(df_customers) > 0:
            overlap = len(set(df_customers) & set(g_customers))
            print(f"   Overlap: {overlap} ({overlap/len(df_customers)*100:.1f}%)")

            if overlap < len(df_customers) * 0.9:
                print("⚠️  CUSTOMER MISMATCH: <90% overlap between df and g!")

    except Exception as e:
        print(f"❌ Customer comparison failed: {e}")

    # 4. Revenue calculation comparison
    try:
        def _money(s):
            return _pd.to_numeric(s, errors='coerce')

        # Method 1: Subtotal - Discount (order level)
        if all(c in df.columns for c in ['Subtotal', 'Total Discount', 'Name']):
            df_dedup = df.drop_duplicates(subset=['Name'])
            rev1 = (_money(df_dedup['Subtotal']) - _money(df_dedup['Total Discount'])).sum()
        else:
            rev1 = None

        # Method 2: From g features
        rev2 = g['net_sales'].sum() if 'net_sales' in g.columns else None

        # Method 3: L28 from aligned
        rev3 = (aligned.get('L28', {}) or {}).get('net_sales')
        
        # Determine data source type for better validation messaging
        revenue_source = df.get('_revenue_source', pd.Series(['unknown'])).iloc[0] if len(df) > 0 else 'unknown'

        debug_report['revenue_methods'] = {
            'raw_csv_subtotal_discount': float(rev1) if rev1 is not None else None,
            'processed_net_sales': float(rev2) if rev2 is not None else None,
            'aligned_l28_window': float(rev3) if rev3 is not None else None,
            'data_source_type': revenue_source
        }
        
        print("💰 Revenue validation:")
        print(f"   Data source: {revenue_source}")
        print(f"   Processed revenue: ${rev2:,.0f}" if rev2 is not None else "   Processed revenue: None")
        
        if revenue_source == 'line_items_only':
            print(f"   Raw CSV calc: ${rev1:,.0f} (⚠️  uses line-item values as order totals)" if rev1 is not None else "   Raw CSV calc: None")
            if rev1 is not None and rev2 is not None:
                correction = rev2 - rev1
                correction_pct = (correction / rev1) * 100
                print(f"   ✅ Load.py correction: +${correction:,.0f} ({correction_pct:+.1f}%) from proper aggregation")
        else:
            print(f"   Raw CSV calc: ${rev1:,.0f}" if rev1 is not None else "   Raw CSV calc: None")
            if rev1 is not None and rev2 is not None:
                diff_pct = abs(rev1 - rev2) / rev1 if rev1 > 0 else 0
                if diff_pct > 0.1:
                    print("   ⚠️  DISCREPANCY: >10% difference - investigate processing")
                else:
                    print("   ✅ Revenue methods consistent")
        
        print(f"   L28 window: ${rev3:,.0f}" if rev3 is not None else "   L28 window: None")

    except Exception as e:
        print(f"❌ Revenue comparison failed: {e}")

    # 5. Order count comparison
    try:
        df_orders = df['Name'].nunique() if 'Name' in df.columns else len(df)
        g_orders = g['Name'].nunique() if 'Name' in g.columns else len(g)
        aligned_orders = (aligned.get('L28', {}) or {}).get('orders')

        debug_report['order_counts'] = {
            'df_unique_orders': int(df_orders),
            'g_unique_orders': int(g_orders),
            'aligned_l28_orders': int(aligned_orders) if aligned_orders is not None else None
        }

        print("📦 Order counts:")
        print(f"   df unique: {df_orders}")
        print(f"   g unique: {g_orders}")
        print(f"   aligned L28: {aligned_orders}")

        if abs(df_orders - g_orders) > df_orders * 0.05:
            print("⚠️  ORDER COUNT MISMATCH: >5% difference between df and g!")

    except Exception as e:
        print(f"❌ Order count comparison failed: {e}")

    # 6. Window alignment check
    try:
        anchor = aligned.get('anchor')
        if anchor:
            anchor = _pd.Timestamp(anchor)
            l28_window_days = (aligned.get('L28', {}) or {}).get('window_days', 28)

            # Expected L28 range
            l28_end = anchor.normalize() + _pd.Timedelta(hours=23, minutes=59, seconds=59)
            l28_start = l28_end.normalize() - _pd.Timedelta(days=l28_window_days - 1)

            # Count orders in expected L28 window
            df_in_window = df[
                (_pd.to_datetime(df['Created at'], errors='coerce') >= l28_start) &
                (_pd.to_datetime(df['Created at'], errors='coerce') <= l28_end)
            ]
            window_orders = df_in_window['Name'].nunique() if 'Name' in df_in_window.columns else len(df_in_window)

            debug_report['window_check'] = {
                'l28_start': str(l28_start),
                'l28_end': str(l28_end),
                'expected_orders': int(window_orders),
                'aligned_orders': int(aligned.get('L28', {}).get('orders')) if (aligned.get('L28', {}) or {}).get('orders') is not None else None
            }

            print(f"🎯 L28 Window: {l28_start.date()} to {l28_end.date()}")
            print(f"   Orders in window: {window_orders}")
            print(f"   Aligned reports: {aligned.get('L28', {}).get('orders')}")

            try:
                ao = (aligned.get('L28', {}) or {}).get('orders')
                if ao and abs(window_orders - ao) > max(window_orders, ao) * 0.1:
                    print("⚠️  WINDOW MISMATCH: Aligned L28 doesn't match expected window!")
            except Exception:
                pass

    except Exception as e:
        print(f"❌ Window check failed: {e}")

    # Save debug report
    debug_path = _Path(receipts_dir) / "dataframe_debug.json"
    with open(debug_path, 'w') as f:
        _json.dump(debug_report, f, indent=2, default=str)

    print(f"\n📋 Debug report saved to: {debug_path}")

    return debug_report


def run(csv_path: str, brand: str, out_dir: str, inventory_path: str | None = None, order_items_path: str | None = None) -> None:
    cfg = get_config()

    # --- S8-T4: Play Library wave 1 consult-and-verify (flag-gated) --------
    # When ENGINE_V2_PLAY_LIBRARY_WAVE1 is ON, run the integrity check
    # that asserts each wave-1 play_id's spec.yaml-resolved callables are
    # the exact same Python objects as the legacy registry's. This is a
    # pure validation step — no behavior change at either flag state.
    # See plays/__init__.py for the byte-identical contract. KI-NEW-G
    # honest-dormancy for replenishment_due is preserved because the
    # audience builder callable is identity-equal to the legacy one.
    from .play_registry import consult_play_library_if_enabled as _s8_t4_consult
    _s8_t4_consult(cfg)

    # --- G-7: deterministic seeding ----------------------------------------
    # Seed stdlib random + numpy.random at engine entry so any future
    # randomness lands in a fixed state. Today's engine uses no
    # randomness on the Beauty pinned fixture; this is a forcing function
    # backed by tests/test_determinism_cross_run.py.
    from ._determinism import seed_all as _g7_seed_all
    _g7_seed_all()

    # --- output dirs
    safe_make_dirs(out_dir)
    receipts_dir = Path(out_dir) / "receipts"
    safe_make_dirs(str(receipts_dir))
    qa_path = str(receipts_dir / "qa_report.json")

    # --- B-7: hard-refuse non-supported verticals ---------------------------
    # Engine scope is hard-locked at {beauty, supplements, mixed}. If the
    # resolved vertical_mode is outside that set, refuse at the
    # orchestration boundary BEFORE the priors loader, feature builder, or
    # play registry run. Insertion point is non-negotiable: a guard inside
    # decide.py would let the priors loader's mixed-fallback silently mask
    # the refusal.
    from .vertical_guard import (
        is_supported as _vg_is_supported,
        build_vertical_refusal_engine_run as _vg_build_refusal,
    )
    _vertical_mode = (
        cfg.get("VERTICAL_MODE")
        or cfg.get("VERTICAL")
        or None
    )
    if not _vg_is_supported(_vertical_mode):
        _refusal_run = _vg_build_refusal(
            store_id=brand,
            vertical_mode=_vertical_mode,
        )
        try:
            write_json(
                str(receipts_dir / "engine_run.json"),
                _refusal_run.to_dict(),
            )
        except Exception as _we:
            print(f"[B-7 vertical refuse] Warning: failed to write engine_run.json: {_we}")
        print(
            "[B-7 vertical refuse] vertical_mode="
            f"{_vertical_mode!r} is not in supported set "
            "{beauty, supplements, mixed}; emitting ABSTAIN_HARD with "
            "data_quality_flag=vertical_not_supported and skipping "
            "feature build / decide / briefing render."
        )
        return

    # --- B-4/S-1: per-merchant data dir + store_id resolution
    # Resolved once here; threaded into guardrails (history_path) and the
    # outcome-log writer (_hist_path). All tenant-data artifacts live under
    # ``data/<store_id>/``. Migration of any pre-existing shared
    # ``data/recommended_history.json`` is best-effort and never fatal.
    store_id = resolve_store_id(csv_path, brand_arg=brand)
    store_dir = ensure_store_dir(store_id)
    try:
        _mig_status = migrate_legacy_recommended_history(store_id)
        if _mig_status.get("status") == "error":
            print(f"[store_id] migration warning: {_mig_status}")
    except Exception as _me:
        print(f"[store_id] migration warning: {_me}")

    # KI-3 fix (S5-T1): plumb ``store_id`` into the calibration stub's
    # substrate read path. S-5 added the optional ``store_id`` kwarg to
    # ``load_realization_factors`` but no call site passed it, leaving
    # ``v_calibration_state`` unreachable in production. Today there is
    # no live ``calibration_updated`` writer (Phase 9 owns it), so the
    # projection is the canonical empty-shape dict and engine behavior
    # is identical to today — this is dormant-but-correct wiring. The
    # store_id passed here is the same value the substrate writer uses
    # (``_emit_substrate_events`` later in this function), preserving
    # read/write symmetry once Phase 9 lights up the consumer.
    try:
        from .calibration_stub import load_realization_factors as _load_calib
        _calibration_overrides = _load_calib(store_id=store_id)
    except Exception as _ce:
        # The stub is contractually non-raising; this branch is defensive
        # against import-time surprises and must never crash the engine.
        print(f"[calibration] load warning: {_ce}")
        _calibration_overrides = None

    # --- load & features (flexible orders/items)
    items_df = None
    if order_items_path:
        orders_denorm, _, _ = load_orders_csv(csv_path, has_line_items=False)
        items_df = load_order_items_csv(order_items_path)
    else:
        orders_denorm, has_items, items_df = load_orders_csv(csv_path, has_line_items=None)
    # Preprocess orders for engine features
    df, qa = preprocess(orders_denorm)

    # Phase 1: Data contracts + shims (non-breaking)
    try:
        ic = IngestionContract(orders_df=orders_denorm, items_df=items_df)
        dq_contract = ic.data_quality()
    except Exception:
        dq_contract = {}

    # Optional enrichment behind feature flag
    try:
        if bool(cfg.get('FEATURES_DYNAMIC_PRODUCTS', False)):
            df_enriched, meta = FeatureContract.build_g_orders(df, items_df=items_df)
            # Only add additive fields to preserve existing behavior
            for col in ['primary_product','products_concat','products_concat_qty','products_struct','has_sample','has_supplement','category_mode_qty']:
                if col in df_enriched.columns:
                    df[col] = df_enriched[col]
            # Prefer category_mode_qty if available
            if 'category_mode_qty' in df.columns:
                df['category'] = df['category_mode_qty'].fillna(df['category'])
            # Debug sample of products_struct (write whenever dynamic products is enabled)
            try:
                if 'products_struct' in df.columns:
                    sample_df = df[['Name','products_struct']].copy()
                    # keep rows where struct is a non-empty list
                    def _non_empty(x):
                        try:
                            return isinstance(x, (list, tuple)) and len(x) > 0
                        except Exception:
                            return False
                    sample_df = sample_df[sample_df['products_struct'].apply(_non_empty)]
                    sample = sample_df.head(50).to_dict(orient='records')
                    write_json(str(receipts_dir/'products_struct_sample.json'), sample)
            except Exception as e:
                print(f"[warn] failed to write products_struct_sample.json: {e}")

            # Normalization debug: sample raw titles and parsed (base,size)
            try:
                titles = []
                # Prefer items_df product_title; else fall back to Lineitem name
                if items_df is not None and 'product_title' in items_df.columns:
                    tser = items_df['product_title'].astype(str).dropna().unique().tolist()
                    titles = tser[:200]
                elif 'Lineitem name' in df.columns:
                    tser = df['Lineitem name'].astype(str).dropna().unique().tolist()
                    titles = tser[:200]
                if titles:
                    dbg = []
                    for t in titles[:200]:
                        base, size = normalize_product_name(t)
                        dbg.append({'title': t, 'base': base, 'size': size})
                    write_json(str(receipts_dir/'normalization_debug.json'), dbg)
            except Exception as e:
                print(f"[warn] failed to write normalization_debug.json: {e}")
    except Exception as e:
        print(f"[warn] FeatureContract enrichment skipped: {e}")
    g = compute_features(df)

    # NOTE: We standardize on a single canonical orders frame (df) for KPIs and engine.
    # Features (g) are derived 1:1 from df and should not change the row set.

    # S13.7-T1: legacy segments.py retired; per-PlayCard audience CSVs now
    # written at data/<store_id>/runs/<run_id>/audiences/ by audience_resolver.
    seg_files: list = []

    # (charts generation moved to after actions are selected)

    # --- KPI snapshot with deltas (use canonical df)
    aligned_for_template = kpi_snapshot_with_deltas(
        df,
        seasonally_adjust=bool(cfg.get("SEASONAL_ADJUST", False)),
        seasonal_period=int(cfg.get("SEASONAL_PERIOD", 7)),
        cfg=cfg,
    )

    # --- adaptive knobs from snapshot
    l7_orders  = int(aligned_for_template.get("L7", {}).get("orders") or 0)
    l28_orders = int(aligned_for_template.get("L28", {}).get("orders") or 0)
    l56_orders = int(aligned_for_template.get("L56", {}).get("orders") or 0)
    l90_orders = int(aligned_for_template.get("L90", {}).get("orders") or 0)
    cfg["CHOSEN_WINDOW"] = choose_window(
        l7_orders=l7_orders, l28_orders=l28_orders, 
        l56_orders=l56_orders, l90_orders=l90_orders,
        policy=str(cfg.get("WINDOW_POLICY", "auto")).lower(),
    )
    l28_net_sales = float(aligned_for_template.get("L28", {}).get("net_sales") or 0.0)
    if str(cfg.get("FINANCIAL_FLOOR_MODE", "auto")).lower() == "auto":
        cfg["FINANCIAL_FLOOR"] = float(
            financial_floor(l28_net_sales, float(cfg.get("GROSS_MARGIN", 0.70)))
        )

    # --- inventory (optional)
    inventory_df = None
    inventory_metrics = None
    if inventory_path:
        try:
            inventory_df = load_inventory_csv(inventory_path)
            inventory_metrics = compute_inventory_metrics(
                inventory_df, df,
                lead_time_days=int(cfg.get('INVENTORY_LEAD_TIME_DAYS', 14)),
                z=float(cfg.get('INVENTORY_SAFETY_Z', 1.64)),
                safety_floor=int(cfg.get('INVENTORY_SAFETY_STOCK', 0))
            )
        except Exception as e:
            print(f"[warn] inventory load/metrics failed: {e}")

    # --- actions
    plays = str(Path(Path(__file__).resolve().parent.parent) / "templates" / "playbooks.yml")
    # Pass the nested KPI snapshot directly; the engine normalizes internally
    actions = select_actions(g, aligned_for_template, cfg, plays, str(receipts_dir), inventory_metrics=inventory_metrics)

    receipts = build_receipts(aligned_for_template, actions)

    # --- Charts (new): generate with feature df and copy near the HTML ---
    chart_out_dir = Path(out_dir) / "charts"

    # Charts should read from the same canonical orders frame for consistency
    df_for_charts = df

    # Run a consistency debug snapshot before charts for easier diagnosis
    try:
        debug_dataframe_consistency(
            df=df,
            g=g,
            aligned=aligned_for_template,
            df_for_charts=df_for_charts,
            receipts_dir=str(receipts_dir)
        )
    except Exception as e:
        print(f"[warn] dataframe consistency debug failed: {e}")

    chart_data = generate_charts(
        g=g,
        aligned=aligned_for_template,
        actions=actions,
        out_dir=str(chart_out_dir),
        df=df_for_charts,
        chosen_window=str(cfg.get("CHOSEN_WINDOW", "L28")),
        charts_mode=str(cfg.get("CHARTS_MODE", "detailed")),
        inventory_metrics=inventory_metrics
    ) or {}

    # Write a small debug sample for product charts troubleshooting
    try:
        debug_sample = (df_for_charts.head(50) if isinstance(df_for_charts, pd.DataFrame) else pd.DataFrame())
        debug_sample.to_csv(Path(out_dir)/"receipts"/"df_for_charts_sample.csv", index=False)
        # Basic counts
        debug_counts = {
            'rows': int(len(df_for_charts)) if isinstance(df_for_charts, pd.DataFrame) else 0,
            'recent_30_rows': int(
                df_for_charts[df_for_charts['Created at'] >= pd.to_datetime(df_for_charts['Created at'], errors='coerce').max() - pd.Timedelta(days=30)].shape[0]
            ) if isinstance(df_for_charts, pd.DataFrame) and 'Created at' in df_for_charts.columns else 0,
            'has_customer_email': bool(isinstance(df_for_charts, pd.DataFrame) and 'Customer Email' in df_for_charts.columns),
            'has_customer_id': bool(isinstance(df_for_charts, pd.DataFrame) and 'customer_id' in df_for_charts.columns),
            'has_lineitem_name': bool(isinstance(df_for_charts, pd.DataFrame) and 'Lineitem name' in df_for_charts.columns),
        }
        write_json(str(receipts_dir/"df_for_charts_counts.json"), debug_counts)
    except Exception:
        pass

    briefing_dir = Path(out_dir) / "briefings"
    briefing_dir.mkdir(parents=True, exist_ok=True)
    charts_brief_dir = briefing_dir / "charts"
    charts_brief_dir.mkdir(parents=True, exist_ok=True)

    charts_map_rel: dict[str, str] = {}
    chart_paths_abs_resolved: list[str] = []
    for name, src in chart_data.items():
        try:
            src_path = Path(src)
            if not src_path.exists():
                print(f"[warn] chart missing on disk: {src}")
                continue
            dst_path = charts_brief_dir / src_path.name
            shutil.copy2(src_path, dst_path)
            charts_map_rel[name] = str(dst_path.relative_to(briefing_dir))
            chart_paths_abs_resolved.append(str(src_path.resolve()))
        except Exception as e:
            print(f"[warn] failed to copy chart {src} -> {dst_path}: {e}")
    
    # --- DATA VALIDATION (NEW) ---
    validator = DataValidationEngine()
    validation_results = validator.run_all_checks(
        df=df,
        aligned=aligned_for_template,
        actions=actions.get("actions", []),
        qa=qa,
        inventory=inventory_df,
        inventory_metrics=inventory_metrics,
        config=cfg,
        orders_df=orders_denorm,
        items_df=items_df
    )

    # Gate downstream action lists on critical validation failures (e.g., AOV inconsistency)
    try:
        checks = (validation_results or {}).get('checks', {})
        aov_check = checks.get('AOV Consistency', {})
        overall = (validation_results or {}).get('overall_status')
        should_gate = (aov_check.get('status') == 'red') or (overall == 'red')
        if should_gate:
            reason = aov_check.get('message') or 'Critical data validation issues'
            # Demote actions to watchlist; annotate with blocking reason
            blocked = []
            for key in ['actions', 'pilot_actions']:
                lst = actions.get(key, []) or []
                for a in lst:
                    a.setdefault('notes', []).append(f"Blocked by validation: {reason}")
                    a['__blocked_by_validation__'] = True
                blocked.extend(lst)
                actions[key] = []
            actions['watchlist'] = (actions.get('watchlist', []) or []) + blocked
    except Exception:
        # Never fail the run due to gating logic; surfaces via validation report anyway
        pass
    
    # Save validation report
    validation_path = receipts_dir / "validation_report.json"
    write_json(str(validation_path), validation_results)
    
    # Generate HTML panel for briefing
    validation_html = validator.to_html_panel(validation_results)
    
    # Print validation summary to console
    print(f"\nData Validation: {validation_results['summary']}")
    if validation_results['critical_issues']:
        print("Critical Issues:")
        for issue in validation_results['critical_issues']:
            print(f"  - {issue}")
    if validation_results['warnings']:
        print("Warnings:")
        for warning in validation_results['warnings']:
            print(f"  - {warning}")

    # copy assets for selected actions/pilots
    assets_dir = Path(out_dir) / "briefings" / "assets"
    selected_for_copy = (actions.get("actions", []) + actions.get("pilot_actions", []))
    for a in selected_for_copy:
        a["brand"] = brand
    copy_assets = render_copy_for_actions(
        str(Path(Path(__file__).resolve().parent.parent) / "templates"),
        str(assets_dir),
        selected_for_copy,
    )

    # --- Performance tracking summary for template (if any)
    performance_summary = {}  # Tracking system removed
    pending_actions = []      # Tracking system removed

    # receipts summary file
    summary_path = receipts_dir / "run_summary.json"
    # Data quality snapshot (Phase 0)
    dq_orders = identity_coverage(df)
    has_line_items = bool(items_df is not None and not getattr(items_df, 'empty', True))
    has_sku = bool(has_line_items and any(c in items_df.columns for c in ['sku','variant_id','product_id']))
    product_coverage = 0.0
    try:
        if 'Lineitem name' in orders_denorm.columns:
            s = orders_denorm['Lineitem name'].astype(str).str.strip()
            product_coverage = float((s != '').mean())
    except Exception:
        pass

    # Calculate beacon Score and add to aligned data
    aura_data = calculate_aura_score(aligned_for_template)
    aligned_for_template['aura_score'] = aura_data
    print(f"[beacon Score] Calculated: {aura_data['overall']}/100 ({aura_data['tier']}) with {len(aura_data['components'])} components")
    
    write_json(str(summary_path), {
        # Use KPI snapshot (customer-based) as primary aligned for run_summary
        "aligned": aligned_for_template,
        # Keep same aligned structure for engine/briefing reference
        "aligned_order": aligned_for_template,
        "data_quality": {
            **dq_orders,
            **dq_contract,  # contract's assessment (superset, safe to merge)
            "has_line_items": has_line_items,
            "has_sku": has_sku,
            "product_coverage": product_coverage,
        },
        "charts_abs": chart_paths_abs_resolved,
        "charts_rel": list(charts_map_rel.values()),
        "charts_map": charts_map_rel,
        "segments": seg_files,
        "actions": actions.get("actions", []),
        "watchlist": actions.get("watchlist", []),
        "pilot_actions": actions.get("pilot_actions", []),
        "backlog": actions.get("backlog", []),
        "performance_summary": performance_summary,
        "pending_actions": pending_actions,
        "aura_score": aura_data,
    })
    write_actions_log(str(receipts_dir), actions.get("actions", []))

    # --- M1 (T1.3, T1.6): EngineRun receipts-only artifact -----------------
    # Build the typed EngineRun from the legacy actions bundle and serialize
    # to receipts/engine_run.json. This is additive and not consumed by the
    # briefing renderer; M8 will flip the renderer to read EngineRun.
    # Wrapped in try/except so an adapter bug never breaks the run.
    engine_run = None  # M8: hoisted out of the try-block so the renderer router can read it.
    try:
        engine_run = build_engine_run_from_legacy(
            actions_bundle=actions,
            aligned=aligned_for_template,
            df=df,
            cfg=cfg,
            store_id=brand,
            anchor_date=aligned_for_template.get("anchor"),
        )

        # --- Sprint 6.5 Ticket T1: Store Profile layer ---------------------
        # When ``ENGINE_V2_STORE_PROFILE`` is ON, build the typed
        # StoreProfile and attach to ``engine_run.store_profile``. T1
        # ships detection-only; no downstream gate consumes the profile
        # in S6.5 until T4 wires consumers. Flag OFF -> slot stays
        # ``None`` and every existing fixture is byte-identical.
        try:
            if bool(cfg.get("ENGINE_V2_STORE_PROFILE", False)):
                from .profile import build_store_profile as _build_store_profile
                from dataclasses import replace as _dc_replace_profile
                from .engine_run import StoreProfileNullReason as _StoreProfileNullReason

                _profile = _build_store_profile(g, cfg, store_id=brand)
                engine_run = _dc_replace_profile(engine_run, store_profile=_profile)
                # store_profile_null_reason stays None (profile loaded successfully).
        except Exception as _spe:
            print(f"[StoreProfile] Warning: build_store_profile failed: {_spe}")
            # S13.7-T7b (KI-NEW-AA): set paired null_reason on load failure.
            # Only wire when ENGINE_V2_STORE_PROFILE is ON (flag-OFF → both
            # fields stay None, which is the flag-exempt default posture).
            if bool(cfg.get("ENGINE_V2_STORE_PROFILE", False)):
                try:
                    from .engine_run import StoreProfileNullReason as _StoreProfileNullReason
                    from dataclasses import replace as _dc_replace_profile_nr

                    engine_run = _dc_replace_profile_nr(
                        engine_run,
                        store_profile_null_reason=_StoreProfileNullReason.PROFILE_NOT_LOADED,
                    )
                except Exception:
                    pass  # Enum import failure — null_reason stays None silently.

        # --- Sprint 10 Ticket T1.5: BG/NBD predictive-fit step --------------
        # Fits BG/NBD per merchant when ``ENGINE_V2_ML_BGNBD`` is ON. The
        # resulting ``ModelCard`` lands on
        # ``engine_run.predictive_models["bgnbd"]``. Per-customer parquet at
        # ``data/<store_id>/predictive/bgnbd.parquet`` is written only when
        # ``fit_status in {VALIDATED, PROVISIONAL}`` (parquet writer
        # internal contract). The renderer does NOT consume
        # ``predictive_models`` — briefing.html byte-identical at S10.
        # PlayCard.predicted_segment / model_card_ref stay None until S13.
        # Flag-OFF reproduces pre-T1.5 behavior exactly (rollback contract).
        try:
            if bool(cfg.get("ENGINE_V2_ML_BGNBD", False)):
                from .predictive.bgnbd import fit_bgnbd as _fit_bgnbd
                from dataclasses import replace as _dc_replace_pm

                _profile_for_fit = getattr(engine_run, "store_profile", None)
                _orders_for_fit = pd.DataFrame({
                    "customer_id": g["customer_id"].astype(str),
                    "order_date": pd.to_datetime(g["Created at"]),
                }).dropna()
                _bgnbd_card = _fit_bgnbd(
                    _orders_for_fit,
                    _profile_for_fit,
                    store_id=store_id,
                    data_dir=Path(cfg.get("DATA_DIR", "data")),
                )
                _pm = dict(getattr(engine_run, "predictive_models", {}) or {})
                _pm["bgnbd"] = _bgnbd_card
                engine_run = _dc_replace_pm(engine_run, predictive_models=_pm)
        except Exception as _bgnbde:
            print(f"[BGNBD] Warning: fit_bgnbd failed: {_bgnbde}")

        # --- Sprint 10 Ticket T2.5: Gamma-Gamma predictive-fit step ---------
        # Fits Gamma-Gamma per merchant when ``ENGINE_V2_ML_GAMMA_GAMMA`` is
        # ON. Reads the same-run BG/NBD ``ModelCard`` from
        # ``engine_run.predictive_models["bgnbd"]`` as a chained-refusal
        # input (per IM plan §C.2 / DS Option γ 2026-05-26): when BG/NBD is
        # REFUSED or INSUFFICIENT_DATA, Gamma-Gamma short-circuits to
        # REFUSED with ``chained_bgnbd_refusal``. The resulting ``ModelCard``
        # lands on ``engine_run.predictive_models["gamma_gamma"]``.
        # Per-customer parquet at
        # ``data/<store_id>/predictive/gamma_gamma.parquet`` is written
        # only when ``fit_status in {VALIDATED, PROVISIONAL}``. The
        # renderer does NOT consume ``predictive_models`` — briefing.html
        # byte-identical at S10. PlayCard.predicted_segment /
        # model_card_ref stay None until S13. Flag-OFF reproduces pre-T2.5
        # behavior exactly (rollback contract).
        try:
            if bool(cfg.get("ENGINE_V2_ML_GAMMA_GAMMA", False)):
                from .predictive.gamma_gamma import fit_gamma_gamma as _fit_gg
                from dataclasses import replace as _dc_replace_gg

                _profile_for_gg = getattr(engine_run, "store_profile", None)
                _bgnbd_card_for_gg = (
                    getattr(engine_run, "predictive_models", {}) or {}
                ).get("bgnbd")
                _orders_for_gg = pd.DataFrame({
                    "customer_id": g["customer_id"].astype(str),
                    "order_date": pd.to_datetime(g["Created at"]),
                    "order_value": pd.to_numeric(
                        g["net_sales"] if "net_sales" in g.columns else 0.0,
                        errors="coerce",
                    ),
                }).dropna(subset=["customer_id", "order_date"])
                _gg_card = _fit_gg(
                    _orders_for_gg,
                    _profile_for_gg,
                    _bgnbd_card_for_gg,
                    store_id=store_id,
                    data_dir=Path(cfg.get("DATA_DIR", "data")),
                )
                _pm = dict(getattr(engine_run, "predictive_models", {}) or {})
                _pm["gamma_gamma"] = _gg_card
                engine_run = _dc_replace_gg(engine_run, predictive_models=_pm)
        except Exception as _gge:
            print(f"[GammaGamma] Warning: fit_gamma_gamma failed: {_gge}")

        # --- Sprint 11 Ticket T1.5: Cox PH survival predictive-fit step -----
        # Fits Cox PH survival per merchant when ``ENGINE_V2_ML_SURVIVAL`` is
        # ON. Reads the same-run BG/NBD ``ModelCard`` from
        # ``engine_run.predictive_models["bgnbd"]`` as a chained-refusal
        # input (per S11-T1 module contract / DS Option γ extends 2026-05-26):
        # when BG/NBD is REFUSED or INSUFFICIENT_DATA, survival
        # short-circuits to REFUSED with ``chained_bgnbd_refusal``. The
        # resulting ``ModelCard`` lands on
        # ``engine_run.predictive_models["survival"]``. Per-customer parquet
        # at ``data/<store_id>/predictive/survival.parquet`` is written
        # only when ``fit_status in {VALIDATED, PROVISIONAL}``. The
        # renderer does NOT consume ``predictive_models`` — briefing.html
        # byte-identical at S11. PlayCard.predicted_segment /
        # model_card_ref stay None until S13. Flag-OFF reproduces pre-T1.5
        # behavior exactly (rollback contract).
        try:
            if bool(cfg.get("ENGINE_V2_ML_SURVIVAL", False)):
                from .predictive.survival import fit_survival as _fit_surv
                from dataclasses import replace as _dc_replace_surv

                _profile_for_surv = getattr(engine_run, "store_profile", None)
                _bgnbd_card_for_surv = (
                    getattr(engine_run, "predictive_models", {}) or {}
                ).get("bgnbd")
                _orders_for_surv = pd.DataFrame({
                    "customer_id": g["customer_id"].astype(str),
                    "order_date": pd.to_datetime(g["Created at"]),
                }).dropna()
                _surv_card = _fit_surv(
                    _orders_for_surv,
                    _profile_for_surv,
                    _bgnbd_card_for_surv,
                    store_id=store_id,
                    data_dir=Path(cfg.get("DATA_DIR", "data")),
                )
                _pm = dict(getattr(engine_run, "predictive_models", {}) or {})
                _pm["survival"] = _surv_card
                engine_run = _dc_replace_surv(engine_run, predictive_models=_pm)
        except Exception as _surve:
            print(f"[Survival] Warning: fit_survival failed: {_surve}")

        # --- Sprint 11 Ticket T2.5: Collaborative Filtering (implicit ALS) --
        # Fits CF per merchant when ``ENGINE_V2_ML_CF`` is ON. **CF is
        # INDEPENDENT of BG/NBD (DS-locked S11 plan review §A.6 +
        # S11-T1.5 review §F).** Unlike Gamma-Gamma / survival, this
        # orchestration step DOES NOT read
        # ``engine_run.predictive_models["bgnbd"]`` and passes NO
        # ``bgnbd_model_card`` argument. ``fit_cf``'s signature
        # explicitly forbids one (test
        # ``test_fit_cf_signature_does_not_accept_bgnbd_model_card``
        # pins the API surface). CF fits on user-item co-occurrence
        # signal directly and produces its own state under the four-state
        # ModelFitStatus vocabulary based on its own holdout recall@10
        # gate. The resulting ``ModelCard`` lands on
        # ``engine_run.predictive_models["cf"]``. Per-customer look-alikes
        # parquet at ``data/<store_id>/predictive/cf.parquet`` is written
        # only when ``fit_status in {VALIDATED, PROVISIONAL}``. The
        # renderer does NOT consume ``predictive_models`` — briefing.html
        # byte-identical at S11. PlayCard.predicted_segment /
        # model_card_ref stay None until S13. Flag-OFF reproduces
        # pre-T2.5 behavior exactly (rollback contract).
        #
        # Item column note: ``fit_cf._resolve_item_column`` looks for
        # ``sku`` -> ``product_id`` -> ``product_title``. The Shopify
        # CSV uses ``Lineitem name``; we surface it as ``product_title``
        # in the orders frame passed to ``fit_cf`` so CF has a usable
        # item-identifier column on real fixtures.
        try:
            if bool(cfg.get("ENGINE_V2_ML_CF", False)):
                from .predictive.cf import fit_cf as _fit_cf
                from dataclasses import replace as _dc_replace_cf

                _profile_for_cf = getattr(engine_run, "store_profile", None)
                _orders_cols_cf = {
                    "customer_id": g["customer_id"].astype(str),
                    "order_date": pd.to_datetime(g["Created at"]),
                }
                # Plumb item column if available. ``compute_features``
                # aggregates one row per (Name, customer_id) order and
                # exposes the line-item product name on ``g`` under
                # ``lineitem_any`` (renamed from ``Lineitem name``) plus
                # an alias ``product``. We surface whichever is present
                # as ``product_title`` (last column the resolver checks).
                # Absent column => fit_cf surfaces INSUFFICIENT_DATA
                # cleanly via its item-column gate.
                _item_src = None
                for _c in ("lineitem_any", "product"):
                    if _c in g.columns:
                        _item_src = _c
                        break
                if _item_src is not None:
                    _orders_cols_cf["product_title"] = g[_item_src].astype(str)
                _orders_for_cf = pd.DataFrame(_orders_cols_cf).dropna(
                    subset=["customer_id", "order_date"]
                )
                # NOTE: NO bgnbd_model_card argument. CF is INDEPENDENT.
                _cf_card = _fit_cf(
                    _orders_for_cf,
                    _profile_for_cf,
                    store_id=store_id,
                    data_dir=Path(cfg.get("DATA_DIR", "data")),
                    seed=0,
                )
                _pm = dict(getattr(engine_run, "predictive_models", {}) or {})
                _pm["cf"] = _cf_card
                engine_run = _dc_replace_cf(engine_run, predictive_models=_pm)
        except Exception as _cfe:
            print(f"[CF] Warning: fit_cf failed: {_cfe}")

        # --- Sprint 12 Ticket T1.5: RFM segmentation (deterministic) -------
        # Fits RFM (Recency × Frequency × Monetary) segmentation per
        # merchant when ``ENGINE_V2_ML_RFM`` is ON. **RFM is INDEPENDENT
        # of BG/NBD (DS-locked S12 plan review §F + S11 plan review §A.6
        # precedent — mirrors CF posture, NOT survival/G-G).** This
        # orchestration step DOES NOT read
        # ``engine_run.predictive_models["bgnbd"]`` and passes NO
        # ``bgnbd_model_card`` argument. ``fit_rfm``'s signature
        # explicitly forbids one (test
        # ``test_fit_rfm_signature_does_not_accept_bgnbd_model_card``
        # pins the API surface). RFM produces its own state under the
        # four-state ModelFitStatus vocabulary based on its own
        # internal-consistency metrics (segment_monotonicity_spearman
        # PRIMARY + quintile_coverage_min SECONDARY REFUSED guard) — NOT
        # holdout metrics. The resulting ``ModelCard`` lands on
        # ``engine_run.predictive_models["rfm"]``. Per-customer
        # assignment parquet at ``data/<store_id>/predictive/rfm.parquet``
        # is written only when ``fit_status in {VALIDATED, PROVISIONAL}``.
        # The renderer does NOT consume ``predictive_models`` —
        # briefing.html byte-identical at S12. PlayCard.predicted_segment
        # / model_card_ref stay None until S13. Flag-OFF reproduces
        # pre-T1.5 behavior exactly (rollback contract — tested by
        # ``tests/test_s12_t1_5_rfm_rollback.py``).
        try:
            if bool(cfg.get("ENGINE_V2_ML_RFM", False)):
                from .predictive.rfm import fit_rfm as _fit_rfm
                from dataclasses import replace as _dc_replace_rfm

                _profile_for_rfm = getattr(engine_run, "store_profile", None)
                # Surface ``net_sales`` (per-order net revenue computed
                # upstream in ``compute_features``) as ``total`` so
                # ``fit_rfm._resolve_monetary_column`` picks it up. Mirrors
                # the Gamma-Gamma wire's monetary-column choice (which
                # uses ``net_sales`` directly under ``order_value``).
                _orders_for_rfm = pd.DataFrame(
                    {
                        "customer_id": g["customer_id"].astype(str),
                        "order_date": pd.to_datetime(g["Created at"]),
                        "total": pd.to_numeric(
                            g["net_sales"] if "net_sales" in g.columns else 0.0,
                            errors="coerce",
                        ).fillna(0.0),
                    }
                ).dropna(subset=["customer_id", "order_date"])
                # NOTE: NO bgnbd_model_card argument. RFM is INDEPENDENT.
                _rfm_card = _fit_rfm(
                    _orders_for_rfm,
                    _profile_for_rfm,
                    store_id=store_id,
                    data_dir=Path(cfg.get("DATA_DIR", "data")),
                    seed=0,
                )
                _pm = dict(getattr(engine_run, "predictive_models", {}) or {})
                _pm["rfm"] = _rfm_card
                engine_run = _dc_replace_rfm(engine_run, predictive_models=_pm)
        except Exception as _rfme:
            print(f"[RFM] Warning: fit_rfm failed: {_rfme}")

        # --- Sprint 12 Ticket T2.5: retention curves (cohort-aggregate) ----
        # Fits empirical cohort retention curves with bootstrap CIs per
        # merchant when ``ENGINE_V2_ML_RETENTION`` is ON. **Retention is
        # INDEPENDENT of BG/NBD (DS-locked S12 plan review §C + DS T2
        # verdict — mirrors CF + RFM posture, NOT survival/G-G chained-
        # refusal).** This orchestration step DOES NOT read
        # ``engine_run.predictive_models["bgnbd"]`` (or any other model)
        # and passes NO ``bgnbd_model_card`` argument. ``fit_retention``'s
        # signature explicitly forbids one (T2 signature pin test
        # ``test_fit_retention_signature_does_not_accept_bgnbd_model_card``).
        # Retention produces its own state under the four-state
        # ``ModelFitStatus`` vocabulary based on its own gates
        # (bootstrap_ci_width_at_month_3 PRIMARY + cohort_count_validated
        # SECONDARY + cumulative_retention_monotonicity_violation REFUSED).
        #
        # **Architectural separation:** the resulting ``RetentionCard``
        # lands on ``engine_run.cohort_diagnostics["retention"]`` — NOT
        # ``predictive_models`` (which is contractually a per-customer
        # ranker shape). Cohort-aggregate diagnostics get their own typed
        # slot per DS verdict §C. **NO parquet artifact** — the curves
        # dict is JSON-shaped and lives directly inside cohort_diagnostics.
        #
        # The renderer does NOT consume ``cohort_diagnostics`` (verified
        # via grep src/render_* — empty). briefing.html byte-identical at
        # S12-T2.5 for all 5 pinned fixtures. PlayCard.predicted_segment /
        # model_card_ref stay None until S13. Flag-OFF reproduces pre-T2.5
        # behavior exactly (rollback contract — tested by
        # ``tests/test_s12_t2_5_retention_rollback.py``).
        try:
            if bool(cfg.get("ENGINE_V2_ML_RETENTION", False)):
                from .predictive.retention import fit_retention as _fit_retention
                from dataclasses import replace as _dc_replace_ret

                _profile_for_ret = getattr(engine_run, "store_profile", None)
                _orders_for_ret = pd.DataFrame(
                    {
                        "customer_id": g["customer_id"].astype(str),
                        "order_date": pd.to_datetime(g["Created at"]),
                    }
                ).dropna(subset=["customer_id", "order_date"])
                # NOTE: NO bgnbd_model_card argument. Retention is
                # INDEPENDENT. NO data_dir argument — retention does not
                # write parquet (JSON-shaped curves live in
                # cohort_diagnostics).
                _ret_card = _fit_retention(
                    _orders_for_ret,
                    _profile_for_ret,
                    store_id=store_id,
                    seed=0,
                )
                _cd = dict(getattr(engine_run, "cohort_diagnostics", {}) or {})
                _cd["retention"] = _ret_card
                engine_run = _dc_replace_ret(engine_run, cohort_diagnostics=_cd)
        except Exception as _rete:
            print(f"[Retention] Warning: fit_retention failed: {_rete}")

        # --- M5: guardrail engine ------------------------------------------
        # Each gate is independently flag-gated and default-OFF. With every
        # flag off, ``apply_guardrails`` returns the input EngineRun
        # unchanged in semantics. RejectedPlay records (with reason codes)
        # are populated in ``EngineRun.considered``; HARD data-quality flags
        # set ``abstain.state = ABSTAIN_HARD`` and clear recommendations.
        try:
            from .guardrails import apply_guardrails as _apply_guardrails
            from .detect import compute_audience_overlap as _compute_overlap
            from .audience_builders import get_builder as _get_audience_builder
            from .play_registry import PLAYS as _PLAYS

            # Build audience overlap map only when the cannibalization gate
            # is on. We re-run the audience builders (pure functions) for
            # each play in the recommendations list; this is the M3 shadow
            # mechanism reused at gate time. Empty {} when disabled.
            overlap_map = {}
            if bool(cfg.get("CANNIBALIZATION_GATE_ENABLED", False)):
                _audience_sets = {}
                for _pc in engine_run.recommendations or []:
                    _pdef = _PLAYS.get(_pc.play_id)
                    if _pdef is None:
                        continue
                    _builder = _get_audience_builder(_pdef.audience_builder_ref)
                    if _builder is None:
                        continue
                    try:
                        _res = _builder(g, aligned_for_template or {}, cfg or {})
                        _audience_sets[_pc.play_id] = set(_res.audience_ids or set())
                    except Exception:
                        _audience_sets[_pc.play_id] = set()
                if _audience_sets:
                    overlap_map = _compute_overlap(_audience_sets)

            engine_run = _apply_guardrails(
                engine_run,
                inventory_metrics=inventory_metrics,
                audience_overlap=overlap_map,
                history_path=str(store_dir / "recommended_history.json"),
                store_id=store_id,
                cfg=cfg,
            )
        except Exception as _ge:
            print(f"[Guardrails] Warning: apply_guardrails failed: {_ge}")

        # --- M6 (T6.2-T6.6): V2 conservative economic sizing -----------
        # Behind ENGINE_V2_SIZING=true ONLY. When enabled, replace each
        # PlayCard.revenue_range with sizing.size_play(...). The legacy
        # ``expected_$`` (mapped to legacy revenue_range.p50 by the M1
        # adapter) is preserved in a shadow-compare artifact for review
        # but no longer emitted on the EngineRun's revenue_range. The
        # legacy ``calculate_28d_revenue`` and the legacy actions list
        # are NOT touched (T6.5 / M10 deletes them).
        try:
            if bool(cfg.get("ENGINE_V2_SIZING", False)):
                from .sizing import SizingInputs, size_play, shadow_compare
                from .detect import detect_cold_start as _detect_cold_start
                from dataclasses import replace as _dc_replace

                _l28 = (aligned_for_template or {}).get("L28") or {}
                try:
                    _aov = float(_l28.get("aov") or 0.0)
                except (TypeError, ValueError):
                    _aov = 0.0
                _vertical = (
                    cfg.get("VERTICAL_MODE")
                    or cfg.get("VERTICAL")
                    or "mixed"
                )
                _subvertical = cfg.get("SUBVERTICAL")
                if isinstance(_subvertical, str) and _subvertical.lower() in ("", "general", "none"):
                    _subvertical = None
                try:
                    _cold_start = bool(_detect_cold_start(g, cfg))
                except Exception:
                    _cold_start = False

                _shadow_records: list[dict] = []
                _new_recs = []
                for _pc in engine_run.recommendations or []:
                    # Pull legacy expected_$ from the existing revenue_range.p50
                    # (the M1 adapter mapped legacy expected_$ there).
                    _legacy_p50 = (
                        _pc.revenue_range.p50
                        if (_pc.revenue_range is not None) else None
                    )
                    _aud_size = (
                        _pc.audience.size if (_pc.audience is not None and _pc.audience.size is not None) else 0
                    )
                    _ec = (
                        _pc.evidence_class.value
                        if hasattr(_pc.evidence_class, "value")
                        else str(_pc.evidence_class)
                    )
                    _meas = _pc.measurement
                    _obs_eff = _meas.observed_effect if _meas is not None else None
                    _obs_metric = _meas.metric if _meas is not None else None
                    _obs_n = _meas.n if _meas is not None else None

                    _v2_range = size_play(
                        SizingInputs(
                            play_id=_pc.play_id,
                            evidence_class=_ec,
                            audience_size=int(_aud_size or 0),
                            aov=float(_aov),
                            observed_effect=_obs_eff,
                            observed_metric_name=_obs_metric,
                            observed_n=_obs_n,
                            vertical=str(_vertical) if _vertical else None,
                            subvertical=str(_subvertical) if _subvertical else None,
                            cold_start=_cold_start,
                            allow_targeting_unsuppressed=False,
                            # Sprint 7.5 T3: thread the validation-status
                            # refusal flag. Default OFF preserves M0 +
                            # Beauty + supplements byte-identity until
                            # T3.5 flips the cfg default ON.
                            priors_validation_enabled=bool(
                                cfg.get("ENGINE_V2_PRIORS_VALIDATION", False)
                            ),
                        )
                    )
                    _shadow_records.append({
                        "play_id": _pc.play_id,
                        "evidence_class": _ec,
                        "audience_size": int(_aud_size or 0),
                        "aov": float(_aov),
                        "cold_start": _cold_start,
                        **shadow_compare(_legacy_p50, _v2_range),
                    })
                    _new_recs.append(_dc_replace(_pc, revenue_range=_v2_range))

                engine_run = _dc_replace(engine_run, recommendations=_new_recs, cold_start=_cold_start)

                # T6.6: write the shadow-compare artifact. This is
                # receipts-only and is NOT consumed by any renderer.
                try:
                    write_json(
                        str(receipts_dir / "v2_sizing_shadow.json"),
                        {
                            "schema_version": "1.0.0",
                            "store_id": brand,
                            "vertical": str(_vertical) if _vertical else None,
                            "subvertical": str(_subvertical) if _subvertical else None,
                            "aov": float(_aov),
                            "cold_start": _cold_start,
                            "records": _shadow_records,
                        },
                    )
                except Exception as _se:
                    print(f"[V2 sizing shadow] Warning: write failed: {_se}")
        except Exception as _se:
            print(f"[V2 sizing] Warning: size_play failed: {_se}")

        # --- Phase 5.2 + 5.6: populate considered + wire one
        # measured/directional pathway from M3 candidates -----------------
        # Even when the legacy adapter produced zero recommendations and
        # the M5 guardrails fired no rejections, the V2 briefing should
        # still explain WHAT was evaluated and WHY each play was held.
        # We run M3 detect (pure / cheap) and:
        #   (5.6) try to build a directional PlayCard for one wired
        #         play (first_to_second_purchase) when its supporting
        #         signal meets the Phase 5.6 bar; on success the card
        #         is appended to ``recommendations`` BEFORE the M7
        #         ranker so it can survive cap + abstain logic.
        #   (5.2) map every remaining Candidate to a ReasonCode and
        #         merge into ``engine_run.considered`` before
        #         ``decide()`` so abstain-soft reason text can reflect
        #         the dominant gate.
        # Behind ENGINE_V2_DECIDE only; legacy path is unchanged.
        #
        # Phase 6A Ticket A4.5: declare ``_phase5_cands_for_decide`` at
        # the outer scope BEFORE the Phase 5 try/except so the V2 decide
        # block below can reach it even if the Phase 5 candidate-build
        # branch raised. Default ``None`` keeps the legacy / flag-off
        # behavior unchanged.
        _phase5_cands_for_decide = None
        try:
            if bool(cfg.get("ENGINE_V2_DECIDE", False)):
                from dataclasses import replace as _dc_replace
                from .detect import detect_candidates as _detect_candidates
                from .decide import (
                    populate_considered_from_candidates as _populate_considered,
                )
                from .measurement_builder import (
                    build_directional_recommendations as _build_directional_recs,
                )
                from .play_registry import PLAYS as _PLAYS

                # Synthetic Blocker Fix 4: pass inventory_metrics into M3
                # so SKU-pushing plays whose backing SKUs are below the
                # cover-days threshold are stamped with
                # ``preliminary_rejection_reason="inventory_blocked"`` and
                # surface in the V2 considered list with the typed
                # ``ReasonCode.INVENTORY_BLOCKED``. ``inventory_metrics``
                # is None when the merchant did not provide an inventory
                # CSV; M3 treats None as a no-op (no stamping).
                #
                # Sprint 6.5 Ticket T4.x: inject the typed StoreProfile
                # (built around line 955 when ``ENGINE_V2_STORE_PROFILE``
                # is ON) into ``cfg`` so audience-builders invoked inside
                # ``_detect_candidates`` (e.g. winback_dormant_cohort at
                # src/audience_builders.py:298) can read the cohort-floor
                # override from ``profile.gate_calibration``. When the
                # flag is OFF or the profile build raised, the value is
                # ``None`` and the audience-builder branch is a no-op,
                # preserving today's default-500 floor.
                cfg["_store_profile"] = getattr(engine_run, "store_profile", None)
                cfg["_profile_flag_on"] = bool(cfg.get("ENGINE_V2_STORE_PROFILE", False))
                # Sprint 6 Ticket T3: flag-gate the ``replenishment_due``
                # play OUT of the candidate-detection iteration when
                # ``ENGINE_V2_BUILDER_REPLENISHMENT_DUE`` is OFF. This
                # keeps pinned-fixture sha256 byte-identity at flag-OFF
                # (hard-stop #4) — without this filter the populate-
                # considered seam would surface a new
                # ``replenishment_due`` Considered card and shift the
                # 5 pinned fixtures. The gate is at the consumer seam,
                # not at registry-definition time (per IM ticket scope:
                # "Gate the CONSUMPTION (not the function definition)").
                _registry_for_detect = _PLAYS
                if not bool(cfg.get("ENGINE_V2_BUILDER_REPLENISHMENT_DUE", False)):
                    _registry_for_detect = {
                        k: v for k, v in _registry_for_detect.items()
                        if k != "replenishment_due"
                    }
                # Sprint 7 Ticket T2 — flag-gate cohort_journey_first_to_second
                # OUT of the candidate-detection iteration when
                # ``ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND`` is OFF. Mirrors
                # the replenishment_due pattern (S6-T3) to preserve pinned-
                # fixture sha256 byte-identity at flag-OFF. T2.5 will flip
                # the default to ON atomically with the fixture re-pin
                # (Sprint 2 Risk #4 discipline).
                if not bool(cfg.get("ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND", False)):
                    _registry_for_detect = {
                        k: v for k, v in _registry_for_detect.items()
                        if k != "cohort_journey_first_to_second"
                    }
                # Sprint 7 Ticket T1 — flag-gate discount_dependency_hygiene
                # OUT of the candidate-detection iteration when
                # ``ENGINE_V2_BUILDER_DISCOUNT_HYGIENE`` is OFF. Mirrors
                # the replenishment_due (S6-T3) + cohort_journey_first_to_second
                # (S7-T2) patterns to preserve pinned-fixture sha256 byte-
                # identity at flag-OFF. S7-T1.5 will flip the default to ON
                # atomically with the 5-fixture re-pin (Sprint 2 Risk #4).
                if not bool(cfg.get("ENGINE_V2_BUILDER_DISCOUNT_HYGIENE", False)):
                    _registry_for_detect = {
                        k: v for k, v in _registry_for_detect.items()
                        if k != "discount_dependency_hygiene"
                    }
                # Sprint 7 Ticket T3 — flag-gate aov_lift_via_threshold_bundle
                # OUT of the candidate-detection iteration when
                # ``ENGINE_V2_BUILDER_AOV_BUNDLE`` is OFF. Mirrors the
                # replenishment_due (S6-T3) + cohort_journey_first_to_second
                # (S7-T2) + discount_dependency_hygiene (S7-T1) patterns to
                # preserve pinned-fixture sha256 byte-identity at flag-OFF.
                # S7-T3.5 will flip the default to ON atomically with the
                # 5-fixture re-pin (Sprint 2 Risk #4 discipline).
                if not bool(cfg.get("ENGINE_V2_BUILDER_AOV_BUNDLE", False)):
                    _registry_for_detect = {
                        k: v for k, v in _registry_for_detect.items()
                        if k != "aov_lift_via_threshold_bundle"
                    }
                _phase5_cands = _detect_candidates(
                    g,
                    aligned_for_template,
                    cfg,
                    _registry_for_detect,
                    inventory_metrics=inventory_metrics,
                )
                # Phase 6A Ticket A4.5: pin the live candidate list so the
                # downstream V2 decide block can plumb it into the new
                # Recommended Experiment selector. The selector itself
                # gates on ``ENGINE_V2_SLATE`` and is a no-op when the
                # slate flag is OFF, so this assignment is safe to make
                # unconditionally inside the V2 decide branch.
                _phase5_cands_for_decide = _phase5_cands
                _vertical = (
                    cfg.get("VERTICAL_MODE")
                    or cfg.get("VERTICAL")
                    or "mixed"
                )
                _subvertical = cfg.get("SUBVERTICAL")
                if isinstance(_subvertical, str) and _subvertical.lower() in ("", "general", "none"):
                    _subvertical = None

                # Phase 5.6: build a directional PlayCard if a wired
                # supporting signal meets the bar.
                # B-1: skip directional rebuild when the data-quality
                # layer has already routed the run to abstain on a
                # populated ``data_quality_flags`` list. The legacy
                # adapter's "legacy actions list is empty" ABSTAIN_SOFT
                # default does NOT count -- that's the cold-start /
                # zero-V1-actions case the Phase 5.6 builder is
                # specifically designed to recover from. We gate strictly
                # on ABSTAIN_HARD OR (ABSTAIN_SOFT with at least one
                # data-quality flag), which is exactly the
                # ``apply_guardrails`` anomaly-route signature.
                _abstain_state = (
                    engine_run.abstain.state if engine_run.abstain else None
                )
                _has_dq = bool(engine_run.data_quality_flags)
                _gate_routed = (
                    _abstain_state == DecisionState.ABSTAIN_HARD
                    or (
                        _abstain_state == DecisionState.ABSTAIN_SOFT
                        and _has_dq
                    )
                )
                # Sprint 6.5 Ticket T4: thread the typed StoreProfile +
                # ENGINE_V2_STORE_PROFILE flag into the directional +
                # prior-anchored builders so R1 window_corroboration is
                # emitted and R2 cadence-derived primary_window
                # overrides the L28 default under flag-ON. Flag-OFF
                # path is byte-identical to today's behavior.
                _profile_flag_on = bool(cfg.get("ENGINE_V2_STORE_PROFILE", False))
                _store_profile = getattr(engine_run, "store_profile", None)

                if _gate_routed:
                    _directional_cards = []
                else:
                    _existing_ids = [
                        pc.play_id for pc in (engine_run.recommendations or [])
                    ]
                    _directional_cards = _build_directional_recs(
                        _phase5_cands,
                        aligned_for_template,
                        existing_recommendation_ids=_existing_ids,
                        store_profile=_store_profile,
                        profile_flag_on=_profile_flag_on,
                    )
                if _directional_cards:
                    _new_recs = list(engine_run.recommendations or []) + list(_directional_cards)
                    engine_run = _dc_replace(engine_run, recommendations=_new_recs)

                # S13.5-T1 (KI-NEW-L collapse, 2026-05-30): the five
                # legacy V2 prior-anchored injection blocks
                # (S6-T1 winback / S6-T3 replenishment / S7-T2 journey /
                # S7-T1 discount-hygiene / S7-T3 AOV-bundle) plus the
                # single S7.6-C2 ``apply_guardrails_to_injected`` call
                # collapsed into one dispatch helper keyed off the
                # ``_PRIOR_ANCHORED`` registry. The helper:
                #
                #  - takes its own pre-snapshot of
                #    ``engine_run.recommendations[*].play_id`` (the
                #    S7.6-T7-FIX snapshot) BEFORE any prior-anchored
                #    builder fires;
                #  - iterates the dispatch table in load-bearing order
                #    (winback → replenishment → journey → discount →
                #    AOV-bundle) and calls
                #    :func:`build_prior_anchored_recommendations` once
                #    per gated builder;
                #  - finishes with exactly ONE call to
                #    :func:`apply_guardrails_to_injected` — the single
                #    demote channel (Pivot 7).
                #
                # Byte-identical on Beauty + supplements pinned slates;
                # the three load-bearing invariants are preserved:
                #
                #  (1) single demote channel via
                #      :func:`apply_guardrails_to_injected`;
                #  (2) three-channel ``priority_prepend`` (handled
                #      downstream in :mod:`src.decide`, untouched);
                #  (3) observed-effect surfacing at
                #      ``src/measurement_builder.py:2252-2270``
                #      (per-play ``observed_*_enabled`` kwargs still
                #      threaded through the helper).
                #
                # Pinned by ``tests/test_s13_5_single_emission_point.py``
                # (AST-aware: ``engine_run.recommendations`` reassignment
                # inside ``src/main.py`` may not append V2 prior-anchored
                # builder results outside this dispatch helper).
                from .dispatch_prior_anchored import (
                    dispatch_prior_anchored_builders as _dispatch_prior_anchored_builders,
                )
                engine_run = _dispatch_prior_anchored_builders(
                    engine_run,
                    phase5_cands=_phase5_cands,
                    aligned_for_template=aligned_for_template,
                    vertical=_vertical,
                    subvertical=_subvertical,
                    store_profile=_store_profile,
                    profile_flag_on=_profile_flag_on,
                    gate_routed=_gate_routed,
                    orders_df=g,
                    inventory_metrics=inventory_metrics,
                    store_dir=store_dir,
                    store_id=store_id,
                    cfg=cfg,
                )

                # Sprint 13 Ticket T2 — PlayCard consumer wiring
                # (predicted_segment + model_card_ref population from
                # rank_audience + RFM modal segment). FLAG-OFF at T2:
                # this block is a no-op behind
                # ``ENGINE_V2_PLAY_PREDICTED_SEGMENT`` (default false).
                # T2.5 owns the atomic flip + first intentional
                # engine_run.json re-pin (renderer non-consumption
                # pinned at T2.5; briefing.html stays byte-identical).
                # The pass mutates PlayCard.predicted_segment + .model_
                # card_ref IN-PLACE on engine_run.recommendations. **It
                # does NOT append to engine_run.recommendations and does
                # NOT append to engine_run.considered.** Pivot 7 single-
                # demote-channel invariant preserved structurally — the
                # one apply_guardrails_to_injected helper above remains
                # the only post-injection guardrails re-invocation. ML-
                # fit ReasonCodes (MODEL_FIT_INSUFFICIENT_DATA /
                # MODEL_FIT_REFUSED) emit ONLY via
                # ``model_card_ref.fit_warnings`` per Q-S13-4 LOCK; this
                # callsite NEVER sets RejectedPlay.reason_code.
                if bool(cfg.get("ENGINE_V2_PLAY_PREDICTED_SEGMENT", False)):
                    try:
                        from .predictive.consumer_wiring import (
                            populate_play_card_consumers as _populate_play_card_consumers,
                        )

                        # Per-play audience-IDs resolver. Re-runs the
                        # audience builder (the same pattern used at
                        # L1937-1954 for cannibalization overlap) so we
                        # have customer-id sets for RFM modal-segment
                        # intersection. Failures degrade to an empty
                        # set so the consumer-wiring pass still emits a
                        # well-typed ModelCardRef (chain-walk audit is
                        # independent of audience-id availability).
                        def _resolve_audience_ids_for_play(
                            play_id: str,
                        ) -> set:
                            _pdef = _PLAYS.get(play_id)
                            if _pdef is None:
                                return set()
                            _builder = _get_audience_builder(
                                _pdef.audience_builder_ref
                            )
                            if _builder is None:
                                return set()
                            try:
                                _res = _builder(
                                    g, aligned_for_template or {}, cfg or {}
                                )
                                return set(_res.audience_ids or set())
                            except Exception:
                                return set()

                        _rfm_parquet = (
                            Path(cfg.get("DATA_DIR", "data"))
                            / store_id
                            / "predictive"
                            / "rfm.parquet"
                        )
                        engine_run = _populate_play_card_consumers(
                            engine_run,
                            audience_ids_resolver=_resolve_audience_ids_for_play,
                            rfm_parquet_path=_rfm_parquet,
                        )
                    except Exception as _cwe:
                        print(
                            f"[V2 S13-T2 consumer-wiring] Warning: {_cwe}"
                        )

                # Sprint 13 Ticket T3 — month_2_delta detection
                # (Pivot 8 month-2-return substrate-state-delta).
                # FLAG-OFF at T3: this block is a no-op behind
                # ``ENGINE_V2_MONTH_2_DELTA`` (default false). T3.5
                # owns the atomic flip + rollback contract +
                # pinned_sha_ledger re-pin. The detector reads the
                # prior month-1 ``EngineRun`` via the injected loader
                # (``data/<store_id>/runs/<run_id>.json`` immutable
                # archive — see ``src/decide.py:2185``) and computes
                # the substrate-state-delta + lineage-keyed segment
                # shifts. **It does NOT append to
                # engine_run.recommendations and does NOT append to
                # engine_run.considered.** Pivot 7 single-demote-
                # channel invariant preserved structurally — the one
                # apply_guardrails_to_injected helper above (S7.6 C2)
                # remains the only post-injection guardrails re-
                # invocation. Failures degrade silently (warning-log
                # only); the engine run proceeds with
                # ``engine_run.month_2_delta`` left as ``None``.
                if bool(cfg.get("ENGINE_V2_MONTH_2_DELTA", False)):
                    try:
                        from .predictive.month_2_delta import (
                            detect_month_2_delta as _detect_month_2_delta,
                        )

                        _runs_dir = (
                            Path(cfg.get("DATA_DIR", "data"))
                            / store_id
                            / "runs"
                        )

                        def _prior_engine_run_loader(
                            _store_id: str,
                        ):
                            """Load the most-recent prior ``engine_run.json``.

                            Reads from the immutable per-store run
                            archive at ``data/<store_id>/runs/``,
                            EXCLUDING the current run (matched by
                            ``run_id``). Returns ``None`` when no prior
                            run exists or the read fails — the
                            detector treats both as "first month;
                            nothing to compare."
                            """

                            if not _runs_dir.exists():
                                return None
                            current_rid = str(
                                getattr(engine_run, "run_id", "") or ""
                            )
                            candidates = sorted(
                                p
                                for p in _runs_dir.glob("*.json")
                                if p.stem != current_rid
                            )
                            if not candidates:
                                return None
                            # Newest = lexicographically largest run-id
                            # (run_ids are timestamp-prefixed in S-2
                            # lineage; ``sorted`` ascending → take last).
                            for prior_path in reversed(candidates):
                                try:
                                    import json as _json

                                    return _json.loads(
                                        prior_path.read_text(
                                            encoding="utf-8"
                                        )
                                    )
                                except Exception:
                                    continue
                            return None

                        # S13.6-T7a: tuple-return enforces always-paired
                        # (value, null_reason) emission at the seam per
                        # the revised flag-aware RULE A. Assign both
                        # fields atomically.
                        _md, _md_null_reason = _detect_month_2_delta(
                            engine_run,
                            store_id,
                            _prior_engine_run_loader,
                        )
                        if _md is not None:
                            engine_run.month_2_delta = _md
                            engine_run.month_2_delta_null_reason = None
                        else:
                            engine_run.month_2_delta = None
                            engine_run.month_2_delta_null_reason = _md_null_reason
                    except Exception as _mde:
                        print(
                            f"[V2 S13-T3 month_2_delta] Warning: {_mde}"
                        )

                # Sprint 5 Ticket S5-T2 (resolves KI-20): supplements
                # ``first_to_second_purchase`` honest abstain. When the
                # run's vertical is ``supplements`` and the directional
                # builder did NOT emit a Recommended card for this
                # play, surface a typed Considered card with
                # ``SUPPLEMENT_CADENCE_OUTSIDE_WINDOW``. Prepended so the
                # cap-trim inside ``populate_considered_from_candidates``
                # cannot displace it. Beauty / mixed paths untouched.
                # The directional builder's own cohort/window logic is
                # NOT modified by this ticket; B-5 Berkson invariant
                # stays vacuously preserved on this surface.
                try:
                    from .engine_run import RejectedPlay as _RejectedPlay, ReasonCode as _ReasonCode
                    from .decide import (
                        _CONSIDERED_REASON_TEXT as _CRT,
                        _WOULD_FIRE_IF_TEMPLATE as _WFI,
                        _evidence_snapshot_for_candidate as _esc,
                    )
                    if str(_vertical or "").strip().lower() == "supplements":
                        _ftsp_in_recs = any(
                            str(getattr(pc, "play_id", "")) == "first_to_second_purchase"
                            for pc in (engine_run.recommendations or [])
                        )
                        if not _ftsp_in_recs:
                            _ftsp_cand = next(
                                (
                                    c for c in _phase5_cands
                                    if str(getattr(c, "play_id", "")) == "first_to_second_purchase"
                                ),
                                None,
                            )
                            if _ftsp_cand is not None:
                                _code = _ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW
                                # S13.6-T1a (Option D): ``reason_text`` /
                                # ``evidence_snapshot`` / ``would_fire_if``
                                # stripped per Pivot 2.
                                _rejected = _RejectedPlay(
                                    play_id="first_to_second_purchase",
                                    reason_code=_code,
                                )
                                _existing_considered = list(engine_run.considered or [])
                                # Prepend so the cap-trim in populate_*
                                # cannot displace this typed card.
                                engine_run = _dc_replace(
                                    engine_run,
                                    considered=[_rejected] + _existing_considered,
                                )
                except Exception as _se:
                    print(f"[V2 S5-T2] Warning: supplement-cadence abstain emit failed: {_se}")

                # Phase 5.2: populate the considered list from
                # candidates that did NOT make it into recommendations.
                engine_run = _populate_considered(
                    engine_run,
                    _phase5_cands,
                    registry=_PLAYS,
                    vertical=str(_vertical) if _vertical else None,
                    subvertical=str(_subvertical) if _subvertical else None,
                )
        except Exception as _ce:
            print(f"[V2 considered] Warning: populate failed: {_ce}")

        # --- M7 (T7.1-T7.9): V2 Decision Selector ----------------------
        # Behind ENGINE_V2_DECIDE=true ONLY. When enabled, ``src.decide.decide``
        # composes the M1+M5+M6 EngineRun into the final V2 decision layer:
        # class-aware ranking, top-3 cap, abstain state machine,
        # rejected-play assembly with would_fire_if text, deterministic
        # Watching section. Renderer is NOT touched (M8 owns the renderer
        # flip). With the flag OFF, this block is a no-op and the
        # EngineRun is identical to the M6 output.
        #
        # Phase 6A Ticket A4.5: plumb the already-built Phase 5 / M3
        # candidate list into ``decide()`` so the new Recommended
        # Experiment selector (Ticket A4) can operate end-to-end. When
        # the Phase 5 candidate-build branch above raised or was skipped,
        # ``_phase5_cands_for_decide`` remains ``None`` and ``decide()``
        # treats it as an empty candidate set (selector returns ``[]``).
        # The slate selector itself gates on ``ENGINE_V2_SLATE``; passing
        # candidates here is a no-op when the slate flag is OFF.
        try:
            if bool(cfg.get("ENGINE_V2_DECIDE", False)):
                from .decide import decide as _v2_decide

                # Phase 6A Ticket B1.5: pass ``aligned_for_template`` so
                # the Recommended Experiment selector can populate the
                # Phase 5.1 ``opportunity_context`` block on experiment
                # cards using the same store-observed AOV the directional
                # builder uses (``aligned[L28]['aov']`` with L56 / L90
                # fallback). The selector self-omits opportunity_context
                # when ``aligned`` is None / empty / missing AOV — never
                # fabricates an addressable value. The slate selector
                # itself gates on ``ENGINE_V2_SLATE``; passing aligned
                # here is a no-op when the slate flag is OFF.
                engine_run = _v2_decide(
                    engine_run,
                    cfg=cfg,
                    candidates=_phase5_cands_for_decide,
                    aligned=aligned_for_template,
                )
        except Exception as _de:
            print(f"[V2 decide] Warning: decide() failed: {_de}")

        # --- S5-T3 (resolves KI-22): supplements cadence-coherence flag --
        # When the median customer-level reorder gap exceeds 0.8 * the
        # active primary window (L28), the within-window
        # ``repeat_rate_within_window`` metric is structurally
        # incoherent. Propagate the advisory into the typed
        # ``data_quality_flags`` list AND suppress the misleading
        # Watching row (founder call inside the ticket — either is
        # contract-safe). Gated to ``vertical == supplements`` so the
        # Beauty / mixed paths stay byte-identical. The new flag is
        # ADVISORY (not in ``_HARD_DQ_FLAGS``); it must NOT push the
        # run to ABSTAIN_HARD. Heuristic threshold is pinned in
        # ``src.cadence_coherence.DEFAULT_THRESHOLD_RATIO`` so the test
        # imports it rather than re-deriving a magic constant.
        try:
            _vertical_for_cc = locals().get("_vertical", None) or cfg.get("VERTICAL_MODE") or cfg.get("VERTICAL") or "mixed"
            if engine_run is not None and str(_vertical_for_cc or "").strip().lower() == "supplements":
                from .cadence_coherence import evaluate as _cc_eval
                from .engine_run import DataQualityFlag as _DQF
                _window_days = int(
                    (aligned_for_template or {}).get("L28", {}).get("window_days", 28)
                    or 28
                )
                _should_flag, _ = _cc_eval(df, _window_days)
                if _should_flag:
                    _existing_flags = list(engine_run.data_quality_flags or [])
                    if _DQF.METRIC_INCOHERENT_FOR_CADENCE not in _existing_flags:
                        engine_run = _dc_replace(
                            engine_run,
                            data_quality_flags=_existing_flags + [_DQF.METRIC_INCOHERENT_FOR_CADENCE],
                        )
                    # Suppress the misleading repeat_rate_within_window
                    # Watching row when the flag fires.
                    _watching = list(engine_run.watching or [])
                    _filtered = [
                        w for w in _watching
                        if str(getattr(w, "metric", "")) != "repeat_rate_within_window"
                    ]
                    if len(_filtered) != len(_watching):
                        engine_run = _dc_replace(engine_run, watching=_filtered)
        except Exception as _ce:
            print(f"[V2 S5-T3] Warning: cadence-coherence flag emit failed: {_ce}")

        # --- S-4 immutable snapshot + sha256 -----------------------------
        # Write the slate JSON to ``data/<store_id>/runs/<run_id>.json``
        # (immutable, never overwritten) and mirror it byte-identically
        # to ``receipts/engine_run.json`` for backward-compat with
        # current Swarm consumers. Compute sha256 over the on-disk
        # bytes and thread it through to the substrate event emitter so
        # every recommendation_* event payload pins the snapshot it was
        # produced against.
        _snapshot_path_str: str | None = None
        _snapshot_sha256: str | None = None
        try:
            _immutable_path, _snapshot_sha256 = write_immutable_snapshot(
                engine_run_dict=engine_run.to_dict(),
                store_dir=store_dir,
                receipts_dir=receipts_dir,
                run_id=str(getattr(engine_run, "run_id", "") or ""),
            )
            _snapshot_path_str = str(_immutable_path)
        except Exception as _we:
            # If immutable write fails, fall back to the legacy mutable
            # path so the engine still produces engine_run.json. Emit a
            # warning so ops sees the cause; substrate event sha256
            # fields stay None for this run (they are Optional[str]).
            print(
                f"[Snapshot] Warning: immutable snapshot write failed: {_we}; "
                "falling back to mutable receipts/engine_run.json"
            )
            try:
                write_json(
                    str(receipts_dir / "engine_run.json"),
                    engine_run.to_dict(),
                )
            except Exception as _we2:
                print(
                    f"[Snapshot] Warning: mutable engine_run.json write also "
                    f"failed: {_we2}"
                )

        # --- S13.7-T1: audience CSV materialization ----------------------
        # For every PlayCard in recommendations + recommended_experiments,
        # write data/<store_id>/runs/<run_id>/audiences/<aud_def_id>.csv.
        # Columns: customer_id, aov_individual, predicted_segment, rank_score.
        # Pure side-effect — does NOT mutate engine_run or recommendations.
        # Single-demote-channel invariant preserved structurally.
        # SUBSTRATE_REFUSED (parquet missing/unreadable) → empty CSV with
        # header row at the expected path (never silent absence).
        # Failures degrade non-fatally (warning log only).
        try:
            from .audience_resolver import materialize_audience_csvs as _materialize_audience_csvs

            _mat_run_id = str(getattr(engine_run, "run_id", "") or "")
            _mat_data_dir = str(cfg.get("DATA_DIR", "data"))

            if not _mat_run_id:
                print("[AudienceResolver] Warning: run_id is empty; skipping audience CSV materialization.")
            else:
                # Re-use the same audience_ids_resolver pattern as the S13-T2
                # consumer-wiring pass (src/predictive/consumer_wiring.py L279).
                # Resolves play_id -> Set[str] of customer IDs from the
                # audience-builder registry. Defined inline so it captures the
                # live g / aligned_for_template / cfg from the enclosing scope.
                def _mat_resolve_audience_ids(play_id: str) -> set:
                    try:
                        from .play_registry import PLAYS as _MAT_PLAYS
                        from .audience_builders import get_builder as _mat_get_builder
                        _pdef = _MAT_PLAYS.get(play_id)
                        if _pdef is None:
                            return set()
                        _builder = _mat_get_builder(_pdef.audience_builder_ref)
                        if _builder is None:
                            return set()
                        _res = _builder(g, aligned_for_template or {}, cfg or {})
                        return set(_res.audience_ids or set())
                    except Exception:
                        return set()

                _mat_audience_statuses = _materialize_audience_csvs(
                    engine_run,
                    store_id,
                    _mat_run_id,
                    _mat_data_dir,
                    audience_ids_resolver=_mat_resolve_audience_ids,
                )
                # S13.7-T2: write per-run manifest.json immediately after
                # audience CSVs are materialized. Reads engine_run; does NOT
                # mutate it (single-demote-channel invariant preserved).
                try:
                    from .run_manifest import write_run_manifest as _write_run_manifest
                    _write_run_manifest(
                        engine_run,
                        store_id,
                        _mat_run_id,
                        _mat_data_dir,
                        audience_statuses=_mat_audience_statuses or {},
                    )
                except Exception as _mf_err:
                    print(f"[RunManifest] Warning: write_run_manifest failed: {_mf_err}")
        except Exception as _mat_err:
            print(f"[AudienceResolver] Warning: materialize_audience_csvs failed: {_mat_err}")
        # ------------------------------------------------------------------

        # --- S-3 substrate event emission (Sprint 2 closeout) ------------
        # Per implementation plan §2 ticket S-3: after engine_run.json is
        # written, append one ``recommendation_emitted`` event per
        # PlayCard in ``recommendations`` and ``recommended_experiments``,
        # and one ``recommendation_considered`` event per RejectedPlay in
        # ``considered``. Lineage tuple is
        # ``(store_id, play_id, audience_definition_id,
        # audience_definition_version)`` per founder decision D-1.
        #
        # Substrate writes are PURELY ADDITIVE to runtime — the engine
        # still works if memory.db cannot be opened (we catch + log; we
        # never crash). ``recommended_history.json`` is preserved (the
        # plan's parallel-write phase).
        try:
            _emit_substrate_events(
                engine_run=engine_run,
                store_id=store_id,
                snapshot_path=_snapshot_path_str,
                snapshot_sha256=_snapshot_sha256,
            )
        except Exception as _se:
            # Catch-all: substrate is additive; never block the run.
            print(f"[Substrate] Warning: event emission failed: {_se}")
        # ------------------------------------------------------------------

        # --- M9 (T9.5): merchant-INVISIBLE receipts/debug.html -----------
        # Pure function on the same EngineRun. Surfaces internal stats
        # (evidence_class, p_internal, ci_internal, observed effect, n,
        # drivers, suppression reasons) for internal review only. Not
        # linked from the merchant briefing.html. Failure is non-fatal.
        try:
            from .debug_renderer import render_debug_html as _render_debug_html

            debug_html = _render_debug_html(engine_run)
            (receipts_dir / "debug.html").write_text(debug_html, encoding="utf-8")
        except Exception as _de:
            print(f"[Debug] Warning: failed to write receipts/debug.html: {_de}")

        # --- M9 (T9.1): outcome log append --------------------------------
        # Behind OUTCOME_LOG_ENABLED. Default true; the file is gitignored
        # and lives at data/recommended_history.json. The writer never
        # raises and reports through a status dict. Malformed history
        # files are moved aside as ``.corrupt-<ts>.bak`` rather than
        # crashing the run.
        try:
            from .outcome_log import write_recommended_history as _write_recommended_history

            _hist_path = cfg.get("OUTCOME_LOG_PATH") or str(store_dir / "recommended_history.json")
            _hist_status = _write_recommended_history(
                engine_run,
                _hist_path,
                enabled=bool(cfg.get("OUTCOME_LOG_ENABLED", True)),
            )
            if _hist_status.get("status") not in ("ok", "disabled"):
                print(f"[Outcome log] {_hist_status}")
        except Exception as _ole:
            print(f"[Outcome log] Warning: write_recommended_history failed: {_ole}")
    except Exception as e:
        print(f"[EngineRun] Warning: failed to build/write engine_run.json: {e}")

    # --- M3 (T3.3): shadow candidate detector --------------------------------
    # Behind ENGINE_V2_SHADOW=true ONLY. When the env flag is unset/false
    # (the default), this block is a no-op and produces zero side effects on
    # the legacy pipeline. M0 goldens must remain byte-identical with the
    # flag off; the integration test exercises both branches.
    try:
        import os as _os

        _shadow = str(_os.environ.get("ENGINE_V2_SHADOW", "false")).strip().lower()
        if _shadow in ("1", "true", "yes", "on"):
            # Imports are gated inside the flag check so an import-time bug
            # in the shadow path cannot affect the default run.
            from .detect import detect_candidates, candidates_to_jsonable
            from .play_registry import PLAYS

            try:
                # Synthetic Blocker Fix 4: pass inventory_metrics so the
                # shadow v2_candidates.json receipt reflects the same
                # inventory_blocked stamp the V2 decide path uses.
                v2_cands = detect_candidates(
                    g,
                    aligned_for_template,
                    cfg,
                    PLAYS,
                    inventory_metrics=inventory_metrics,
                )
                write_json(
                    str(receipts_dir / "v2_candidates.json"),
                    candidates_to_jsonable(v2_cands),
                )
                # Log a tiny diff summary against the legacy emitted set.
                legacy_play_ids = {
                    a.get("play_id")
                    for a in (
                        actions.get("actions", [])
                        + actions.get("watchlist", [])
                        + actions.get("pilot_actions", [])
                        + actions.get("backlog", [])
                    )
                    if a.get("play_id")
                }
                v2_play_ids = {c.play_id for c in v2_cands if c.preliminary_rejection_reason is None}
                only_legacy = sorted(legacy_play_ids - v2_play_ids)
                only_v2 = sorted(v2_play_ids - legacy_play_ids)
                both = sorted(legacy_play_ids & v2_play_ids)
                print(
                    f"[ENGINE_V2_SHADOW] candidates={len(v2_cands)} "
                    f"both={both} only_legacy={only_legacy} only_v2={only_v2}"
                )
            except Exception as _e:
                print(f"[ENGINE_V2_SHADOW] Warning: shadow detector failed: {_e}")
    except Exception as _e:
        # Never let shadow wiring fail the run.
        print(f"[ENGINE_V2_SHADOW] Warning: outer guard caught: {_e}")

    # Generate multi-window engine validation report
    try:
        from src.engine_validator import MultiWindowValidator
        validator = MultiWindowValidator(str(summary_path), str(receipts_dir))
        engine_validation_report = validator.validate_all()

        engine_validation_path = receipts_dir / "engine_validation_report.json"
        write_json(str(engine_validation_path), engine_validation_report)
        print(f"[Engine Validation] Multi-window analysis report generated: {engine_validation_path}")
    except Exception as e:
        print(f"[Engine Validation] Warning: Could not generate engine validation report: {e}")

    # render briefing
    outputs = {
        "charts": list(charts_map_rel.values()),  # backward-compat (not used by new template)
        "charts_map": charts_map_rel,
        "segments_bundle": [s for s in seg_files if s.endswith(".zip")][0] if seg_files else "",
        "actions": actions.get("actions", []),
        "watchlist": actions.get("watchlist", []),
        "pilot_actions": actions.get("pilot_actions", []),
        "backlog": actions.get("backlog", []),
        "confidence_mode": actions.get("confidence_mode"),
        "cfg": cfg,
        "copy_assets": copy_assets,
        "receipts": receipts,
        "validation_html": validation_html,  # Pass to template
        "validation_results": validation_results,  # Pass full results too
        "performance_summary": performance_summary,
        "pending_actions": pending_actions,
        "inventory": inventory_df.to_dict(orient='records') if inventory_df is not None else None,
        "inventory_metrics": inventory_metrics.to_dict(orient='records') if inventory_metrics is not None else None,
        "aura_score": aura_data,  # Add beacon Score to template outputs
    }

    # Build a concise inventory summary for the briefing
    if inventory_metrics is not None:
        try:
            mm = inventory_metrics.copy()
            default_cover = int(float(((cfg.get('INVENTORY_MIN_COVER_DAYS') or {}).get('default')) or 21))
            low = mm[pd.to_numeric(mm.get('cover_days'), errors='coerce') < default_cover][['sku','product','cover_days','available']].copy()
            low = low.sort_values('cover_days').head(5)
            alerts = mm[(mm.get('below_reorder') == True)][['sku','product','available']].head(5)
            outputs['inventory_summary'] = {
                'default_cover_days': default_cover,
                'low_cover': low.to_dict(orient='records'),
                'reorder_alerts': alerts.to_dict(orient='records'),
            }
        except Exception as e:
            print(f"[warn] failed to build inventory summary: {e}")

    for a in outputs["actions"]:
        a["evidence"] = evidence_for_action(a, aligned_for_template)
    for p in outputs.get("pilot_actions", []):
        p["evidence"] = evidence_for_action(p, aligned_for_template)
        
    # Phase 3: Add health impact predictions to all actions
    current_aura_components = aura_data.get('components', {})
    print(f"[Health Impact] Starting enhancement with components: {current_aura_components}")
    
    outputs["actions"] = enhance_actions_with_health_impact(outputs["actions"], current_aura_components)
    outputs["pilot_actions"] = enhance_actions_with_health_impact(outputs.get("pilot_actions", []), current_aura_components)
    outputs["watchlist"] = enhance_actions_with_health_impact(outputs.get("watchlist", []), current_aura_components)
    
    # Debug: Show sample health impacts
    if outputs["actions"]:
        sample_action = outputs["actions"][0]
        has_health_impact = 'health_impact' in sample_action
        if has_health_impact:
            summary = sample_action['health_impact'].get('impact_summary', 'No summary')
            print(f"[Health Impact] Sample action '{sample_action.get('title', 'Unknown')}': {summary}")
        else:
            print(f"[Health Impact] WARNING: Sample action has no health_impact field")
    
    print(f"[Health Impact] Enhanced {len(outputs['actions'])} actions with health impact predictions")

    briefing_out = Path(out_dir) / "briefings" / f"{brand}_briefing.html"

    # M8 T8.6: route through the V2 renderer behind ENGINE_V2_OUTPUT=true.
    # Default OFF preserves the legacy CSV->HTML workflow. The V2 path
    # requires a populated EngineRun (built above behind ENGINE_V2_DECIDE);
    # if engine_run is None (e.g. the EngineRun build block raised), fall
    # back to the legacy renderer so the page still renders.
    _use_v2_output = bool(cfg.get("ENGINE_V2_OUTPUT", False)) and engine_run is not None
    render_briefing(
        str(Path(Path(__file__).resolve().parent.parent) / "templates"),
        str(briefing_out),
        brand,
        aligned_for_template,
        outputs,
        engine_run=engine_run,
        use_v2=_use_v2_output,
    )

    # --- console summary
    print("Do next:")
    if outputs["actions"]:
        for i, a in enumerate(outputs["actions"], start=1):
            how = "; ".join((a.get("how_to_launch") or [])[:3])
            print(f"{i}) {a.get('title','')} — {a.get('do_this','')}. Steps: {how}. Assets: {a.get('attachment','')}")
    else:
        for p in outputs.get("pilot_actions", []):
            how = "; ".join((p.get("how_to_launch") or [])[:3])
            frac = int((p.get("pilot_audience_fraction", 0.2) or 0.2) * 100)
            budg = int(p.get("pilot_budget_cap", 200) or 200)
            print(f"Pilot) {p.get('title','')} — {p.get('do_this','')}. Pilot {frac}%, Budget ${budg}. Steps: {how}. Assets: {p.get('attachment','')}")

    if outputs["watchlist"]:
        print("Watchlist (needs more data or $; failed ≥1 gate):")
        for w in outputs["watchlist"]:
            failed = ", ".join(w.get("failed", [])) if w.get("failed") else (", ".join(w.get("reasons", [])) or "directional")
            print(f"- {w.get('title','')} — {failed}")

    if outputs["backlog"]:
        print("Backlog (passed all gates; deferred):")
        for b in outputs["backlog"]:
            print(f"- {b.get('title','')} — {b.get('reason','ranked below top actions')}")

    print(f"QA report: {qa_path}")
    print(f"Charts (copied under briefings): {[p for p in outputs['charts']]}")
    print(f"Segments bundle: {outputs['segments_bundle']}")
    print(f"Briefing: {briefing_out}")



def main():
    ap = argparse.ArgumentParser()
    # Primary report args
    ap.add_argument("--csv", required=False, help="[Deprecated] Combined orders CSV; use --orders instead")
    ap.add_argument("--orders", required=False, help="Orders CSV (order or line-item level)")
    ap.add_argument("--order-items", required=False, help="Optional order items CSV (line-level)")
    ap.add_argument("--brand", required=False)
    ap.add_argument("--out", required=False)
    ap.add_argument("--inventory", required=False, help="Optional Shopify Inventory CSV path")


    args = ap.parse_args()


    # Determine source precedence
    orders_path = args.orders or (args.csv if args.csv else None)
    if (args.order_items) and (not args.orders and not args.csv):
        ap.error("--order-items requires --orders (orders table)")
    if not (orders_path and args.brand and args.out):
        ap.error("--orders (or --csv), --brand, --out are required for report generation")

    # Deprecation notice
    if args.csv and not args.orders:
        print("[warn] --csv is deprecated. Use --orders for clearer intent.")

    # Load orders/items with flexible detection, then run
    # We keep the current run() signature using --csv parameter; pass through via temp path var
    run(orders_path, args.brand, args.out, inventory_path=args.inventory, order_items_path=args.order_items)


if __name__ == "__main__":
    main()
