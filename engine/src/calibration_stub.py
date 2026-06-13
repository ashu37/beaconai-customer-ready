"""Calibration stub — Milestone 9 (T9.4) + S-5 read-view rewire.

Originally a pure contract-anchor returning an empty three-key dict.
S-5 (Sprint 3) rewires the loader to project the substrate's
``v_calibration_state`` view (over ``calibration_updated`` events) into
the same ``{prior_overrides, evidence_thresholds, materiality_overrides}``
dict shape.

Behavioural contract preserved end-to-end:

  * With zero ``calibration_updated`` events present (today's state — no
    writer ships before Phase 9), the function returns a freshly-built
    empty-shape dict, byte-equal to the pre-S-5 stub return value.
  * The function NEVER raises on a missing/unreadable substrate —
    operator-friendly: `data/<store_id>/memory.db` may not exist yet on
    a fresh install, and that must not crash the engine.
  * The function NEVER raises on arbitrary ``history_path`` arguments
    (legacy contract from M9: callers may pass ``None``, a path, or
    forward-shape junk). Strange inputs short-circuit to the empty dict.
  * The function does NOT mutate the substrate. The single-writer grep
    test (``tests/test_single_writer_per_event_type.py``) keeps
    ``calibration_updated`` writers gated to this module's allowlist
    entry, but no write call lives here yet — Phase 9 will add it as a
    consumer.

Hard NOT-IN-SCOPE (still):

- Do NOT compute realization factors, ratios, deltas, lifts, or
  treatment effects — that's Phase 9 ``compute_realized_outcome`` +
  L-D #1 calibration consumer.
- Do NOT introduce uplift / Bayesian / hierarchical-prior language.
- Do NOT change the engine's decision logic or sizing.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .memory.views import empty_calibration_state, read_calibration_state


def load_realization_factors(
    history_path: Any = None,
    *,
    store_id: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Return the calibration-overrides contract dict.

    Args:
        history_path: legacy positional argument from M9. Accepted for
            backward-compat with existing call sites; the value is not
            inspected. The substrate path is derived from ``store_id``,
            not from this argument.
        store_id: optional per-merchant scope. When provided, the
            function opens the store's ``memory.db`` (if it exists) and
            projects ``v_calibration_state`` into the contract dict.
            When omitted, the function returns the canonical empty-shape
            dict — preserving the pre-S-5 default behaviour for legacy
            call sites that haven't been updated to pass ``store_id``.

    Returns:
        A dict with EXACTLY three keys, each a dict:

            - ``prior_overrides``: ``{prior_key: override_value}``
            - ``evidence_thresholds``: ``{play_id: {threshold_name: value}}``
            - ``materiality_overrides``: ``{scale_band: {floor_param: value}}``

        Freshly constructed on every call so callers can mutate safely.
    """
    # No store scope → empty-shape contract (matches pre-S-5 behaviour
    # exactly, including the legacy ``test_calibration_stub_shape``
    # assertions that pass arbitrary junk in ``history_path``).
    if not store_id or not isinstance(store_id, str):
        return empty_calibration_state()

    # Defensive open: a fresh install may not have a memory.db yet, and
    # the calibration consumer (Phase 9) hasn't written any
    # ``calibration_updated`` events yet either. Either failure mode
    # short-circuits to the empty-shape dict — the engine MUST keep
    # running when the substrate is absent or empty.
    try:
        from .memory.store import open_memory  # local import: avoid eager substrate load
        store = open_memory(store_id)
    except Exception:
        return empty_calibration_state()

    try:
        return read_calibration_state(store)
    except Exception:
        # View read failure (corrupt db, missing migration on a stale
        # file) must not crash the engine. Return empty-shape.
        return empty_calibration_state()
    finally:
        try:
            store.close()
        except Exception:
            pass


__all__ = ["load_realization_factors"]
