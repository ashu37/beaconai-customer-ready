"""T9.2 — verify ``measurement.p_internal`` and ``ci_internal`` survive
serialization end-to-end without being rendered to HTML.

The fields are added to ``Measurement`` in M1 and populated in M4a/M4b. M9
locks the contract: they must round-trip through ``to_dict()`` /
``from_dict()`` AND through the M9 outcome-log writer AND through the
M9 debug renderer (visible there only).

They must NOT appear in any merchant-facing renderer output.
"""

from __future__ import annotations

import json

from src.engine_run import (
    Audience,
    EngineRun,
    EvidenceClass,
    Measurement,
    PlayCard,
)
from src.debug_renderer import render_debug_html
from src.outcome_log import build_record
from src.storytelling_v2 import render_engine_run


def _engine_run_with_internal_stats() -> EngineRun:
    return EngineRun(
        run_id="r",
        store_id="s",
        recommendations=[
            PlayCard(
                play_id="winback_21_45",
                evidence_class=EvidenceClass.MEASURED,
                audience=Audience(id="aud", size=300),
                measurement=Measurement(
                    metric="reactivation_rate",
                    observed_effect=0.123456,
                    n=300,
                    primary_window="L28",
                    consistency_across_windows=2,
                    p_internal=0.0042,
                    ci_internal=[0.05, 0.18],
                ),
            )
        ],
    )


def test_p_internal_and_ci_internal_round_trip_through_to_dict():
    er = _engine_run_with_internal_stats()
    payload = er.to_dict()
    blob = json.dumps(payload)
    revived = EngineRun.from_dict(json.loads(blob))
    m = revived.recommendations[0].measurement
    assert m.p_internal == 0.0042
    assert m.ci_internal == [0.05, 0.18]
    assert m.observed_effect == 0.123456
    assert m.n == 300
    assert m.consistency_across_windows == 2


def test_p_internal_and_ci_internal_appear_in_outcome_log_record():
    er = _engine_run_with_internal_stats()
    rec = build_record(er)
    measured = rec["recommended"][0]
    assert measured["measurement"]["p_internal"] == 0.0042
    assert measured["measurement"]["ci_internal"] == [0.05, 0.18]


def test_p_internal_and_ci_internal_appear_in_debug_html():
    er = _engine_run_with_internal_stats()
    html_doc = render_debug_html(er)
    assert "p_internal" in html_doc
    assert "ci_internal" in html_doc
    # Token appears as the formatted six-digit float.
    assert "0.004200" in html_doc


def test_p_internal_and_ci_internal_do_not_appear_in_briefing_v2():
    er = _engine_run_with_internal_stats()
    html_doc = render_engine_run(er)
    assert "p_internal" not in html_doc
    assert "ci_internal" not in html_doc
    # The numeric stat itself must not appear as a labelled stat.
    assert "0.0042" not in html_doc


def test_targeting_evidence_class_carries_no_measurement_round_trip():
    """Hard schema invariant: targeting => measurement is None.

    Round-tripping a serialized targeting card preserves measurement=None.
    """
    er = EngineRun(
        recommendations=[
            PlayCard(
                play_id="category_expansion",
                evidence_class=EvidenceClass.TARGETING,
                measurement=None,
            )
        ]
    )
    blob = json.dumps(er.to_dict())
    revived = EngineRun.from_dict(json.loads(blob))
    assert revived.recommendations[0].measurement is None
