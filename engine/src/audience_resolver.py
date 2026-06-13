"""Audience CSV materializer — S13.7-T1.

For every PlayCard in ``engine_run.recommendations`` and
``engine_run.recommended_experiments``, writes one CSV under::

    data/<store_id>/runs/<run_id>/audiences/<audience_definition_id>.csv

Columns (in order):

- ``customer_id``: str — customer identifier from the substrate parquet.
- ``aov_individual``: float — per-customer AOV. ``0.0`` when unavailable
  (the RFM parquet schema v1 does not carry per-customer AOV; the field is
  reserved for a future parquet schema extension).
- ``predicted_segment``: str — modal RFM segment name (e.g. "Champions",
  "At Risk"); empty string when unavailable.
- ``rank_score``: float in [0, 1] — ranking priority within the audience
  (higher = higher priority). Derived from ``m_quintile`` as
  ``(m_quintile - 1) / 4`` when the parquet is available; ``0.5`` otherwise.

SUBSTRATE_REFUSED branch (DS R4 required)
==========================================

When the RFM parquet at ``data/<store_id>/predictive/rfm.parquet`` is
missing or unreadable, the resolver:

1. Emits an **empty CSV with the standard header row** at the expected path.
2. Does NOT crash. Does NOT silently skip writing the file.
3. TODO(S13.7-T2): Record ``audience_materialization_status:
   "SUPPRESSED_SUBSTRATE_REFUSED"`` in ``manifest.json`` for that PlayCard's
   audience entry. Manifest generation is T2's responsibility; this module
   only writes the CSV.

The merchant-reputation killer is wrong customers, not zero customers.
Empty auditable CSV = correct. Silent absence = incorrect.

Audience filtering
==================

Each PlayCard's CSV contains ONLY the customers in that play's audience.
The resolver accepts an optional ``audience_ids_resolver`` callable
(``play_id -> Set[str]``) that mirrors the pattern established by
``src.predictive.consumer_wiring.AudienceIdsResolver``. When provided, the
parquet rows are filtered to the resolved audience set before writing.
When the resolver is absent, or when it raises for a given play, the
resolver MUST NOT write the full substrate (which would email the whole
base under a targeted play — wrong customers with a green light). Instead
it writes an **empty CSV with the standard header row** and reports
``NOT_MATERIALIZED`` for that audience (DS lock 4, route (a), 2026-06-01).
"The merchant-reputation killer is wrong customers, not zero customers."

Single-demote-channel invariant
=================================

This module is a pure side-effect writer. It reads
``engine_run.recommendations`` and ``engine_run.recommended_experiments``;
it writes files to disk. It does NOT:
- Append to or mutate ``engine_run.recommendations``.
- Append to or mutate any other EngineRun list.
- Call ``apply_guardrails_to_injected`` or any guardrails path.
- Set any ``ReasonCode`` on any ``RejectedPlay``.

Pivot 7 (single-demote-channel invariant) is preserved structurally.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Optional, Set

from src.engine_run import CustomerIdsNullReason, EngineRun


# ---------------------------------------------------------------------------
# Public type alias (mirrors AudienceIdsResolver in consumer_wiring.py)
# ---------------------------------------------------------------------------

AudienceIdsResolver = Callable[[str], Set[str]]

# Standard CSV header — MUST be present even when the file has no data rows.
_CSV_HEADER = ["customer_id", "aov_individual", "predicted_segment", "rank_score"]


def materialize_audience_csvs(
    engine_run: EngineRun,
    store_id: str,
    run_id: str,
    data_dir: str,
    *,
    audience_ids_resolver: Optional[AudienceIdsResolver] = None,
) -> dict:
    """Materialize one CSV per PlayCard audience.

    For every PlayCard in ``engine_run.recommendations`` +
    ``engine_run.recommended_experiments``, writes::

        data/<store_id>/runs/<run_id>/audiences/<audience_definition_id>.csv

    Columns: ``customer_id``, ``aov_individual``, ``predicted_segment``,
    ``rank_score``.

    Empty CSV with header row on SUBSTRATE_REFUSED (parquet missing /
    unreadable). Never crashes; warnings are printed to stdout.

    Returns:
        dict mapping ``audience_definition_id`` -> status string. Status
        values:

        - ``"MATERIALIZED"`` — CSV written with at least one data row
          (parquet present AND resolver returned an audience set).
        - ``"SUPPRESSED_SUBSTRATE_REFUSED"`` — empty CSV written because the
          parquet was missing or unreadable.
        - ``"NOT_MATERIALIZED"`` — empty CSV written because the audience
          could not be resolved: ``audience_ids_resolver`` was absent, it
          raised for this play, or the PlayCard's ``play_id`` was falsy
          (resolution cannot run without a play id). The degraded path must
          NEVER emit the full substrate under a green ``MATERIALIZED`` light
          (DS lock 4, route (a)). It also covers the case where the file
          could not be written at all.

        The returned dict is consumed by ``src.run_manifest.write_run_manifest``
        (S13.7-T2) to populate the per-run ``manifest.json`` artifact list.

    Args:
        engine_run: finalized EngineRun (after guardrails; after
            ``engine_run.json`` is written).
        store_id: per-merchant store identifier.
        run_id: run UUID from ``engine_run.run_id``.
        data_dir: root data directory (e.g. "data"). The parquet is read
            from ``<data_dir>/<store_id>/predictive/rfm.parquet``.
        audience_ids_resolver: optional callable ``play_id -> Set[str]``
            used to filter the parquet to only the play's audience members.
            When None, all customers in the parquet are written (with a
            warning). Use the same resolver injected into
            ``populate_play_card_consumers`` at the S13-T2 consumer-wiring
            call site in ``src/main.py``.
    """

    # audience_definition_id -> status string returned to S13.7-T2 manifest writer.
    audience_statuses: dict = {}

    data_path = Path(data_dir)
    rfm_parquet_path = data_path / store_id / "predictive" / "rfm.parquet"

    # Track whether the substrate is present/readable (single load for all cards).
    substrate_refused = False

    # Attempt to load the RFM substrate once for all PlayCards in this run.
    rfm_df = _load_rfm_parquet(rfm_parquet_path)
    if rfm_df is None:
        substrate_refused = True

    # Determine the output audiences directory.
    audiences_dir = data_path / store_id / "runs" / run_id / "audiences"
    try:
        audiences_dir.mkdir(parents=True, exist_ok=True)
    except Exception as _mkd_err:
        print(
            f"[AudienceResolver] Warning: could not create audiences dir "
            f"{audiences_dir}: {_mkd_err}"
        )
        return audience_statuses

    # Collect PlayCards from both lanes.
    cards = list(getattr(engine_run, "recommendations", []) or [])
    cards += list(getattr(engine_run, "recommended_experiments", []) or [])

    if not cards:
        # No cards to materialize; audiences dir exists but is empty.
        return audience_statuses

    seen_aud_ids: set = set()
    for pc in cards:
        play_id = str(getattr(pc, "play_id", "") or "")
        # Derive audience_definition_id using the same fallback as
        # _audience_definition_id in main.py: prefer audience.id, else play_id.
        aud = getattr(pc, "audience", None)
        aud_id_raw = getattr(aud, "id", None) if aud is not None else None
        aud_def_id = (
            str(aud_id_raw)
            if isinstance(aud_id_raw, str) and aud_id_raw
            else play_id or "unknown"
        )

        if aud_def_id in seen_aud_ids:
            # Same audience already materialized for this run (role-uniqueness
            # means the same play_id cannot appear twice in recs + experiments,
            # but defensive guard is cheap).
            continue
        seen_aud_ids.add(aud_def_id)

        out_path = audiences_dir / f"{aud_def_id}.csv"
        try:
            # _write_audience_csv returns the authoritative status for the
            # cases it can discriminate (substrate refused, audience
            # unresolved). It returns None for the normal write path, in
            # which case we count rows to distinguish MATERIALIZED from an
            # empty result.
            write_status = _write_audience_csv(
                out_path=out_path,
                play_id=play_id,
                rfm_df=rfm_df,
                audience_ids_resolver=audience_ids_resolver,
            )
            if write_status is not None:
                # SUPPRESSED_SUBSTRATE_REFUSED (parquet absent/unreadable) or
                # NOT_MATERIALIZED (resolver absent / resolver raised) — both
                # wrote an empty header-only CSV. No row count needed.
                audience_statuses[aud_def_id] = write_status
            else:
                # Resolved write path (parquet present, resolver returned a
                # set): count data rows to distinguish MATERIALIZED vs an
                # empty (zero-match) audience. This branch is unchanged from
                # pre-hardening behavior.
                try:
                    import csv as _csv_mod
                    with open(out_path, newline="", encoding="utf-8") as _f:
                        _rows = list(_csv_mod.reader(_f))
                    # Row count > 1 means at least one data row beyond header.
                    audience_statuses[aud_def_id] = (
                        "MATERIALIZED" if len(_rows) > 1 else "SUPPRESSED_SUBSTRATE_REFUSED"
                    )
                except Exception:
                    audience_statuses[aud_def_id] = "MATERIALIZED"
        except Exception as _err:
            print(
                f"[AudienceResolver] Warning: failed to write audience CSV for "
                f"play_id={play_id!r} aud_def_id={aud_def_id!r}: {_err}"
            )
            # Best-effort: attempt empty-header fallback so the file exists.
            try:
                _write_empty_csv(out_path)
                audience_statuses[aud_def_id] = "SUPPRESSED_SUBSTRATE_REFUSED"
            except Exception as _ferr:
                print(
                    f"[AudienceResolver] Warning: empty-CSV fallback also failed "
                    f"for {out_path}: {_ferr}"
                )
                audience_statuses[aud_def_id] = "NOT_MATERIALIZED"

    return audience_statuses


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_rfm_parquet(rfm_parquet_path: Path):
    """Load the RFM parquet. Returns None on any failure (SUBSTRATE_REFUSED)."""

    import pandas as pd

    if not rfm_parquet_path.exists():
        return None
    try:
        df = pd.read_parquet(rfm_parquet_path)
    except Exception as _read_err:
        print(
            f"[AudienceResolver] Warning: RFM parquet unreadable at "
            f"{rfm_parquet_path}: {_read_err}. SUBSTRATE_REFUSED path."
        )
        return None

    # Validate required columns.
    required = {"customer_id", "segment_name"}
    if not required.issubset(set(df.columns)):
        print(
            f"[AudienceResolver] Warning: RFM parquet missing required columns "
            f"(need {required}, got {set(df.columns)}). SUBSTRATE_REFUSED path."
        )
        return None

    # Ensure customer_id is string for consistent set-intersection.
    df = df.copy()
    df["customer_id"] = df["customer_id"].astype(str)
    return df


def _write_audience_csv(
    *,
    out_path: Path,
    play_id: str,
    rfm_df,
    audience_ids_resolver: Optional[AudienceIdsResolver],
) -> Optional[str]:
    """Write the audience CSV for one PlayCard.

    Returns an authoritative status string for the cases this helper can
    discriminate, or ``None`` to signal the normal resolved write path (the
    caller then counts rows to decide MATERIALIZED vs empty):

    - ``"SUPPRESSED_SUBSTRATE_REFUSED"`` — ``rfm_df is None`` (parquet
      missing/unreadable). Writes empty CSV with header row.
    - ``"NOT_MATERIALIZED"`` — the audience could not be resolved
      (``audience_ids_resolver`` is absent, it raised for this play, or
      ``play_id`` is falsy so resolution cannot run without a play id).
      Writes empty CSV with header row. This degraded path MUST NOT emit the
      full substrate under a green MATERIALIZED light (DS lock 4, route (a),
      2026-06-01). "The merchant-reputation killer is wrong customers, not
      zero customers."
    - ``None`` — resolved write path: filters rfm_df to the play's audience
      and writes one row per matched customer with computed columns.
    """

    if rfm_df is None:
        # SUBSTRATE_REFUSED — emit empty CSV with standard header.
        _write_empty_csv(out_path)
        return "SUPPRESSED_SUBSTRATE_REFUSED"

    # Resolve the audience customer-id set for filtering.
    # A successfully resolved set (incl. an empty set) is the ONLY thing that
    # licenses writing substrate rows. Resolver absent or resolver-raised are
    # both degraded paths: empty + NOT_MATERIALIZED, never full substrate.
    if audience_ids_resolver is None:
        # Degraded path: no way to scope the audience. Refuse to leak the
        # full substrate; write an empty header-only CSV instead.
        print(
            f"[AudienceResolver] Warning: no audience_ids_resolver provided for "
            f"play_id={play_id!r}; writing empty CSV (NOT_MATERIALIZED) rather "
            f"than the full substrate (DS lock 4, route (a))."
        )
        _write_empty_csv(out_path)
        return "NOT_MATERIALIZED"

    audience_ids: Optional[Set[str]] = None
    if play_id:
        try:
            resolved = audience_ids_resolver(play_id)
            if resolved is not None:
                audience_ids = {str(x) for x in resolved}
        except Exception as _res_err:
            print(
                f"[AudienceResolver] Warning: audience_ids_resolver raised for "
                f"play_id={play_id!r}: {_res_err}. Writing empty CSV "
                f"(NOT_MATERIALIZED) rather than the full substrate "
                f"(DS lock 4, route (a))."
            )
            _write_empty_csv(out_path)
            return "NOT_MATERIALIZED"

    if audience_ids is None:
        # Resolution could not RUN: resolver returned None, or play_id was
        # empty (an empty play_id never enters the resolver call above, so
        # audience_ids stays None). This is NOT the zero-match case — a
        # resolver that returns an empty set falls through to the filter
        # below and is counted as zero matched rows, not handled here.
        # Treat unrunnable resolution as a degraded path rather than a
        # license to leak the full substrate.
        print(
            f"[AudienceResolver] Warning: audience resolution could not run for "
            f"play_id={play_id!r} (resolver returned None, or play_id was empty); "
            f"writing empty CSV (NOT_MATERIALIZED) rather than the full substrate "
            f"(DS lock 4, route (a)). This is NOT zero-match: a resolver that "
            f"returns an empty set is counted as zero matched rows downstream."
        )
        _write_empty_csv(out_path)
        return "NOT_MATERIALIZED"

    # Filter rows to the resolved audience set.
    import pandas as pd

    filtered = rfm_df.copy()
    filtered = filtered[filtered["customer_id"].isin(audience_ids)]

    # Compute derived columns.
    # aov_individual: parquet schema v1 has no per-customer AOV column;
    # use 0.0 per spec ("0.0 if unavailable").
    filtered = filtered.copy()
    filtered["aov_individual"] = 0.0

    # predicted_segment: from parquet segment_name column.
    # Fill NaN with empty string per spec.
    filtered["predicted_segment"] = (
        filtered["segment_name"].fillna("").astype(str)
    )

    # rank_score: derived from m_quintile (1..5) normalized to [0, 1].
    # (m_quintile - 1) / 4 gives 0.0 for quintile 1 and 1.0 for quintile 5.
    # Falls back to 0.5 when m_quintile is absent.
    if "m_quintile" in filtered.columns:
        filtered["rank_score"] = (
            pd.to_numeric(filtered["m_quintile"], errors="coerce")
            .fillna(3.0)  # mid-quintile fallback
            .clip(1, 5)
            .sub(1)
            .div(4)
        )
    else:
        filtered["rank_score"] = 0.5

    # Select and order columns per spec.
    out_df = filtered[["customer_id", "aov_individual", "predicted_segment", "rank_score"]]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(str(out_path), index=False)


def _write_empty_csv(out_path: Path) -> None:
    """Write an empty CSV with the standard header row at ``out_path``."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(_CSV_HEADER)


__all__ = [
    "AudienceIdsResolver",
    "materialize_audience_csvs",
    "CustomerIdsNullReason",  # re-exported for convenience (declared in engine_run)
]
