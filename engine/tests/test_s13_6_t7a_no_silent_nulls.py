"""S13.6-T7a tests — RULE A (flag-aware) absence-of-data pattern.

Per DS adjudication 2026-06-01 + founder approved 2026-06-01:

- 3 new closed-set null-reason enums (RevenueRangeSuppressionReason — 9
  members; MonthDeltaNullReason — 5 members; PredictedSegmentNullReason
  — 4 members).
- 3 new paired ``_null_reason`` fields (``RevenueRange.suppression_reason``,
  ``EngineRun.month_2_delta_null_reason``,
  ``PredictedSegment.segment_name_null_reason``).
- Revised RULE A (DS verbatim): "For every Optional field F on a contract
  surface, if F is None AND the relevant feature flag is ON, then F's
  paired ``<F>_null_reason`` MUST be set. Flag-OFF default-None is
  exempt and MUST be marked with a source-level annotation:
  ``# null_reason_exempt: default-None when ENGINE_V2_<FLAG_NAME> is
  OFF``. The AST sweep test enforces: every Optional field either (i)
  has a paired ``_null_reason`` on the same contract, OR (ii) carries
  the ``null_reason_exempt:`` annotation with a named flag. No silent
  Optionals."

Test coverage:

1.  AST sweep — every ``Optional[...]`` AnnAssign on a contract
    dataclass in ``src/engine_run.py`` is either paired or annotated.
2.  Per-row strict invariants on a hand-built EngineRun + on a fixture.
3.  Closed-set enum coverage — exact membership pin per the DS-verdict
    list (regression pin against future drift).
4.  Re-export coverage — the 3 enums import directly from
    ``src.engine_run``.
5.  Round-trip — serializer + deserializer carry the new fields.
"""
from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

import src.engine_run as engine_run_mod
from src.engine_run import (
    EngineRun,
    MonthDelta,
    MonthDeltaNullReason,
    PlayCard,
    PredictedSegment,
    PredictedSegmentNullReason,
    RevenueRange,
    RevenueRangeSuppressionReason,
)


# ---------------------------------------------------------------------------
# (3) Closed-set enum coverage — exact membership pin (regression).
# ---------------------------------------------------------------------------


EXPECTED_REVENUE_RANGE_SUPPRESSION = {
    "COLD_START_NO_N_OBSERVED": "cold_start",
    "AUDIENCE_ZERO": "audience_zero",
    "AOV_ZERO": "aov_zero",
    "OBSERVED_EFFECT_INVALID": "observed_effect_invalid",
    "NO_PRIOR_BASE_RATE": "no_prior_base_rate",
    "PRIOR_UNVALIDATED": "prior_unvalidated",
    "AOV_UNAVAILABLE": "aov_unavailable",
    "DIRECTIONAL_NO_INTERVENTION_EFFECT": "directional_no_intervention_effect",
    "EXPERIMENT_NO_CALIBRATED_LIFT": "experiment_no_calibrated_lift",
}

EXPECTED_MONTH_DELTA_NULL = {
    "NO_STORE_ID": "no_store_id",
    "NO_PRIOR_RUN": "no_prior_run",
    "ANCHOR_DATE_UNPARSEABLE": "anchor_date_unparseable",
    "UNDER_21D_FLOOR": "under_21d_floor",
    "LINEAGE_CHANGED": "lineage_changed",
}

EXPECTED_PREDICTED_SEGMENT_NULL = {
    "MODAL_FLOOR_NOT_CLEARED": "modal_floor_not_cleared",
    "PARQUET_MISSING": "parquet_missing",
    "PARQUET_UNREADABLE": "parquet_unreadable",
    "NO_AUDIENCE_INTERSECTION": "no_audience_intersection",
}


def _enum_to_dict(enum_cls) -> Dict[str, str]:
    return {m.name: m.value for m in enum_cls}


def test_revenue_range_suppression_reason_closed_set():
    assert _enum_to_dict(RevenueRangeSuppressionReason) == EXPECTED_REVENUE_RANGE_SUPPRESSION


def test_month_delta_null_reason_closed_set():
    assert _enum_to_dict(MonthDeltaNullReason) == EXPECTED_MONTH_DELTA_NULL


def test_predicted_segment_null_reason_closed_set():
    assert _enum_to_dict(PredictedSegmentNullReason) == EXPECTED_PREDICTED_SEGMENT_NULL


# ---------------------------------------------------------------------------
# (4) Re-export coverage.
# ---------------------------------------------------------------------------


def test_three_null_reason_enums_reexported():
    # The brief requires direct import.
    from src.engine_run import (  # noqa: F401
        MonthDeltaNullReason as _MD,
        PredictedSegmentNullReason as _PS,
        RevenueRangeSuppressionReason as _RR,
    )
    assert "RevenueRangeSuppressionReason" in engine_run_mod.__all__
    assert "MonthDeltaNullReason" in engine_run_mod.__all__
    assert "PredictedSegmentNullReason" in engine_run_mod.__all__


# ---------------------------------------------------------------------------
# (1) AST sweep — RULE A flag-aware invariant.
# ---------------------------------------------------------------------------


# Contract dataclasses (the schema surface). Defined as the closed set of
# @dataclass classes that participate in the contract carried by
# EngineRun. New dataclasses added later either land in this set or live
# elsewhere (the sweep does not enforce on non-contract dataclasses).
_CONTRACT_DATACLASSES = {
    "DataWindow",
    "Abstain",
    "Observation",
    "WatchedSignal",
    "Audience",
    "Measurement",
    "RevenueRange",
    "Sensitivity",
    "Provenance",
    "Inventory",
    "Conflicts",
    "LaunchWindow",
    "NonLiftAtom",
    "OpportunityContext",
    "MechanismIntent",
    "PredictedSegment",
    "FitWarning",
    "ModelCardRef",
    "PlayCard",
    "RejectedPlay",
    "Scale",
    "BriefingMeta",
    "MonthDelta",
    "EngineRun",
}


def _source_path() -> Path:
    return Path(engine_run_mod.__file__)


def _line_comments(source: str) -> Dict[int, str]:
    """Return {lineno: full_comment_text} for every ``# ...`` comment."""
    out: Dict[int, str] = {}
    try:
        toks = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in toks:
            if tok.type == tokenize.COMMENT:
                out[tok.start[0]] = tok.string
    except tokenize.TokenizeError:
        pass
    return out


def _is_optional_annotation(node: ast.AST) -> bool:
    """Detect ``Optional[X]`` annotations (handles string forms under
    ``from __future__ import annotations``).
    """
    if isinstance(node, ast.Subscript):
        val = node.value
        if isinstance(val, ast.Name) and val.id == "Optional":
            return True
        if isinstance(val, ast.Attribute) and val.attr == "Optional":
            return True
    # AnnAssign.annotation can also be a Constant str when stringified.
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.strip().startswith("Optional[")
    return False


def _collect_optional_fields_per_dataclass(
    source: str,
) -> Dict[str, List[Tuple[str, int]]]:
    """Return {dataclass_name: [(field_name, lineno), ...]} for every
    Optional AnnAssign on a contract dataclass in the source.
    """
    tree = ast.parse(source)
    out: Dict[str, List[Tuple[str, int]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name not in _CONTRACT_DATACLASSES:
            continue
        fields: List[Tuple[str, int]] = []
        for child in node.body:
            if not isinstance(child, ast.AnnAssign):
                continue
            if not isinstance(child.target, ast.Name):
                continue
            if not _is_optional_annotation(child.annotation):
                continue
            fields.append((child.target.id, child.lineno))
        out[node.name] = fields
    return out


def _collect_all_field_names_per_dataclass(source: str) -> Dict[str, Set[str]]:
    tree = ast.parse(source)
    out: Dict[str, Set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name not in _CONTRACT_DATACLASSES:
            continue
        names: Set[str] = set()
        for child in node.body:
            if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                names.add(child.target.id)
        out[node.name] = names
    return out


def _has_null_reason_exempt_annotation(
    field_lineno: int, comments_by_line: Dict[int, str]
) -> bool:
    """Walk preceding lines for a ``# null_reason_exempt:`` comment.

    Walks UP from ``field_lineno - 1`` consuming contiguous comment
    lines (allows multi-line rationales). Stops on the first non-
    comment line. Returns True if any comment in the contiguous block
    contains ``null_reason_exempt:``.
    """
    line = field_lineno - 1
    while line >= 1 and line in comments_by_line:
        if "null_reason_exempt:" in comments_by_line[line]:
            return True
        line -= 1
    return False


def test_ast_sweep_no_silent_optionals():
    """RULE A flag-aware invariant — every Optional on a contract
    dataclass is either paired with a ``<field>_null_reason`` field on
    the SAME dataclass, OR carries a ``# null_reason_exempt: <text>``
    annotation on the immediately-preceding comment line(s).
    """

    src = _source_path().read_text(encoding="utf-8")
    optionals = _collect_optional_fields_per_dataclass(src)
    all_fields = _collect_all_field_names_per_dataclass(src)
    comments = _line_comments(src)

    # Paired ``_null_reason`` fields (and aliases like
    # ``suppression_reason`` on RevenueRange) are themselves the
    # pairing — they don't need a paired-of-paired.
    _PAIRED_FIELD_NAMES = {
        "suppression_reason",
        "month_2_delta_null_reason",
        "segment_name_null_reason",
    }

    violations: List[str] = []
    for dataclass_name, fields in optionals.items():
        siblings = all_fields.get(dataclass_name, set())
        for field_name, lineno in fields:
            # Skip the paired null-reason fields themselves.
            if field_name in _PAIRED_FIELD_NAMES or field_name.endswith(
                "_null_reason"
            ):
                continue
            paired_name = f"{field_name}_null_reason"
            if paired_name in siblings:
                continue
            # Also accept ``suppression_reason`` as the paired field
            # for ``suppressed`` / range fields on RevenueRange (the
            # T7a contract uses the suppression_reason alias rather
            # than ``<field>_null_reason`` per DS Q1 producer-byte
            # alignment).
            if (
                dataclass_name == "RevenueRange"
                and "suppression_reason" in siblings
                and field_name in {"p10", "p50", "p90", "source"}
            ):
                # These are paired via ``suppressed`` boolean + the
                # ``suppression_reason`` enum at the seam. The exempt
                # annotation already documents this — but if the
                # annotation is somehow stripped, fall back to the
                # paired-suppression_reason detection.
                if _has_null_reason_exempt_annotation(lineno, comments):
                    continue
            if _has_null_reason_exempt_annotation(lineno, comments):
                continue
            violations.append(
                f"{dataclass_name}.{field_name} (line {lineno}) — "
                f"no paired '{paired_name}' field AND no "
                f"'# null_reason_exempt:' annotation on preceding "
                f"comment line(s)."
            )

    assert not violations, (
        "RULE A (flag-aware) sweep failed — silent Optionals on "
        "contract dataclasses:\n  - " + "\n  - ".join(violations)
    )


def test_ast_sweep_finds_the_three_paired_fields():
    """Pin the 3 T7a paired _null_reason fields are present on the
    expected dataclasses; protects against future refactors that might
    move or rename them.
    """
    src = _source_path().read_text(encoding="utf-8")
    all_fields = _collect_all_field_names_per_dataclass(src)
    assert "suppression_reason" in all_fields["RevenueRange"]
    assert "segment_name_null_reason" in all_fields["PredictedSegment"]
    assert "month_2_delta_null_reason" in all_fields["EngineRun"]


# ---------------------------------------------------------------------------
# (2) Per-row strict invariants.
# ---------------------------------------------------------------------------


def test_revenue_range_paired_invariant_suppressed_true():
    rr = RevenueRange(
        suppressed=True,
        suppression_reason=RevenueRangeSuppressionReason.AUDIENCE_ZERO,
    )
    assert rr.suppressed is True
    assert rr.suppression_reason is not None


def test_revenue_range_paired_invariant_suppressed_false():
    rr = RevenueRange(p10=1.0, p50=2.0, p90=3.0, suppressed=False)
    assert rr.suppressed is False
    assert rr.suppression_reason is None


def test_month_2_delta_paired_invariant_null():
    er = EngineRun(
        month_2_delta=None,
        month_2_delta_null_reason=MonthDeltaNullReason.NO_PRIOR_RUN,
    )
    assert er.month_2_delta is None
    assert er.month_2_delta_null_reason is MonthDeltaNullReason.NO_PRIOR_RUN


def test_month_2_delta_paired_invariant_populated():
    md = MonthDelta(
        prior_run_id="r1",
        current_run_id="r2",
        days_between=30,
    )
    er = EngineRun(month_2_delta=md, month_2_delta_null_reason=None)
    assert er.month_2_delta is md
    assert er.month_2_delta_null_reason is None


def test_predicted_segment_paired_invariant_floor_not_cleared():
    ps = PredictedSegment(
        segment_name=None,
        audience_modal_share=0.22,
        n_audience=30,
        segment_name_null_reason=PredictedSegmentNullReason.MODAL_FLOOR_NOT_CLEARED,
    )
    assert ps.segment_name is None
    assert ps.audience_modal_share == 0.22
    assert ps.n_audience == 30
    assert (
        ps.segment_name_null_reason
        is PredictedSegmentNullReason.MODAL_FLOOR_NOT_CLEARED
    )


def test_predicted_segment_paired_invariant_populated():
    ps = PredictedSegment(
        segment_name="Loyalists",
        audience_modal_share=0.42,
        n_audience=120,
    )
    assert ps.segment_name == "Loyalists"
    assert ps.segment_name_null_reason is None


# ---------------------------------------------------------------------------
# (5) Round-trip — serializer + deserializer carry the new fields.
# ---------------------------------------------------------------------------


def test_round_trip_revenue_range_suppression_reason():
    rr = RevenueRange(
        suppressed=True,
        suppression_reason=RevenueRangeSuppressionReason.PRIOR_UNVALIDATED,
    )
    from dataclasses import asdict

    payload = engine_run_mod._to_jsonable(rr)
    assert payload["suppression_reason"] == "prior_unvalidated"
    rt = engine_run_mod._from_dict_revenue_range(payload)
    assert rt.suppressed is True
    assert rt.suppression_reason is RevenueRangeSuppressionReason.PRIOR_UNVALIDATED


def test_round_trip_predicted_segment_null_reason():
    ps = PredictedSegment(
        segment_name=None,
        audience_modal_share=0.18,
        n_audience=40,
        segment_name_null_reason=PredictedSegmentNullReason.MODAL_FLOOR_NOT_CLEARED,
    )
    payload = engine_run_mod._to_jsonable(ps)
    assert payload["segment_name_null_reason"] == "modal_floor_not_cleared"
    rt = engine_run_mod._from_dict_predicted_segment(payload)
    assert rt.segment_name is None
    assert (
        rt.segment_name_null_reason
        is PredictedSegmentNullReason.MODAL_FLOOR_NOT_CLEARED
    )


def test_round_trip_engine_run_month_2_delta_null_reason():
    er = EngineRun(
        month_2_delta=None,
        month_2_delta_null_reason=MonthDeltaNullReason.UNDER_21D_FLOOR,
    )
    payload = er.to_dict()
    assert payload["month_2_delta_null_reason"] == "under_21d_floor"
    rt = EngineRun.from_dict(payload)
    assert rt.month_2_delta is None
    assert rt.month_2_delta_null_reason is MonthDeltaNullReason.UNDER_21D_FLOOR


def test_pre_t7a_snapshot_carry_forward():
    """Strict-cutover carry-forward: pre-T7a snapshots have no
    ``suppression_reason`` / ``segment_name_null_reason`` /
    ``month_2_delta_null_reason`` keys — round-trip to ``None`` per the
    T3/T4 precedent.
    """
    pre_t7a_payload = {
        "run_id": "r1",
        "store_id": "s1",
        "anchor_date": "2026-05-01",
        # No month_2_delta_null_reason key.
        "recommendations": [
            {
                "play_id": "winback_dormant_cohort",
                "evidence_class": "directional",
                # Pre-T7a RevenueRange shape — no suppression_reason key.
                "revenue_range": {
                    "p10": None,
                    "p50": None,
                    "p90": None,
                    "source": None,
                    "drivers": [],
                    "suppressed": True,
                },
                # Pre-T7a PredictedSegment shape — no
                # segment_name_null_reason key.
                "predicted_segment": {
                    "segment_name": None,
                    "audience_modal_share": 0.2,
                    "n_audience": 30,
                    "notes": None,
                },
            }
        ],
    }
    er = EngineRun.from_dict(pre_t7a_payload)
    assert er.month_2_delta_null_reason is None
    pc = er.recommendations[0]
    assert pc.revenue_range.suppressed is True
    assert pc.revenue_range.suppression_reason is None
    assert pc.predicted_segment.segment_name is None
    assert pc.predicted_segment.segment_name_null_reason is None


# ---------------------------------------------------------------------------
# (6) Producer wire — confirm the 4 month_2_delta null-paths emit the
# expected reason via the tuple return.
# ---------------------------------------------------------------------------


def test_detect_month_2_delta_returns_tuple_no_store_id():
    from src.predictive.month_2_delta import detect_month_2_delta

    md, reason = detect_month_2_delta(
        EngineRun(),
        store_id="",
        prior_engine_run_loader=lambda _s: None,
    )
    assert md is None
    assert reason is MonthDeltaNullReason.NO_STORE_ID


def test_detect_month_2_delta_returns_tuple_no_prior_run():
    from src.predictive.month_2_delta import detect_month_2_delta

    md, reason = detect_month_2_delta(
        EngineRun(),
        store_id="store_a",
        prior_engine_run_loader=lambda _s: None,
    )
    assert md is None
    assert reason is MonthDeltaNullReason.NO_PRIOR_RUN


def test_detect_month_2_delta_returns_tuple_under_floor():
    from src.predictive.month_2_delta import detect_month_2_delta

    current = EngineRun(anchor_date="2026-05-20")
    prior_blob = {"anchor_date": "2026-05-10", "run_id": "prior_r"}

    md, reason = detect_month_2_delta(
        current,
        store_id="store_a",
        prior_engine_run_loader=lambda _s: prior_blob,
    )
    assert md is None
    assert reason is MonthDeltaNullReason.UNDER_21D_FLOOR


def test_detect_month_2_delta_returns_tuple_anchor_unparseable():
    from src.predictive.month_2_delta import detect_month_2_delta

    current = EngineRun(anchor_date="not-a-date")
    prior_blob = {"anchor_date": None, "run_id": "prior_r"}

    md, reason = detect_month_2_delta(
        current,
        store_id="store_a",
        prior_engine_run_loader=lambda _s: prior_blob,
    )
    assert md is None
    assert reason is MonthDeltaNullReason.ANCHOR_DATE_UNPARSEABLE
