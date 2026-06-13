"""G-4 — permanent targeting reclassification for subscription_nudge + routine_builder.

Pins, structurally (not flag-gated), the post-G-4 contract:

1. ``subscription_nudge`` ALWAYS ships ``evidence_class == "targeting"``
   wherever it surfaces as a PlayCard (recommendations,
   recommended_experiments). measurement is None in EngineRun.
2. ``routine_builder`` ALWAYS ships ``evidence_class == "targeting"``
   wherever it surfaces as a PlayCard. measurement is None.
3. Neither play's candidate dict carries a fabricated ``effect_abs`` /
   ``p`` / ``effect_floor`` from the historical Phase-2 constants. NaN
   stat fields are the post-G-4 shape; the engine_run_adapter then
   drops the ``measurement`` block on the EvidenceClass.TARGETING
   branch.
4. The forbidden 0.05 / 0.08 literals that previously rode the
   ``cands.append({...})`` blocks for these two plays are gone from
   ``src/action_engine.py``. The narrow check is intentionally a
   substring-scoped scan over the ``subscription_nudge`` /
   ``routine_builder`` emit blocks, NOT a file-wide grep (other plays
   like aov_momentum legitimately carry a 0.05 effect_floor literal).

The test contract is STRUCTURAL: a violation means the engine has
re-introduced a fabricated measurement object on a Berkson-shaped play,
which would surface a hardcoded effect as if measured. The right
response is to fix the emitter, not the test.

See also:
- agent_outputs/code-refactor-engineer-g4-summary.md
- agent_outputs/code-refactor-engineer-b3-summary.md (hardcoded-fallback)
- agent_outputs/code-refactor-engineer-b5-summary.md (Berkson invariant)
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

# Plays whose Phase-2 inline ``effect_abs`` constants G-4 removed.
G4_TARGETING_PLAYS: frozenset = frozenset({"subscription_nudge", "routine_builder"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_play_cards(engine_run: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield every PlayCard from rec / experiment surfaces.

    Considered cards are RejectedPlay-shaped (no evidence_class field),
    skipped here.
    """
    for k in ("recommendations", "recommended_experiments"):
        for card in engine_run.get(k) or []:
            yield card


# ---------------------------------------------------------------------------
# Fixture: Beauty engine_run.json under the full V2 + slate flag stack.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def beauty_engine_run() -> Dict[str, Any]:
    from tests.synthetic_harness import run_scenario

    with tempfile.TemporaryDirectory() as td:
        res = run_scenario("healthy_beauty_240d", Path(td))
        return json.loads(Path(res.engine_run_json_path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# (a) + (b) + (c) — wherever the plays surface as PlayCards, contract holds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("play_id", sorted(G4_TARGETING_PLAYS))
def test_play_always_emits_evidence_class_targeting(
    beauty_engine_run: Dict[str, Any], play_id: str
) -> None:
    """G-4 (a)/(b): wherever subscription_nudge / routine_builder
    surface as a PlayCard, evidence_class MUST be ``"targeting"``.

    Vacuously true if the play doesn't surface at all on the fixture;
    that case is still in-contract (a targeting play held in Considered
    is RejectedPlay-shaped and doesn't carry evidence_class at all).
    """
    found = 0
    for card in _iter_play_cards(beauty_engine_run):
        if str(card.get("play_id") or "") != play_id:
            continue
        found += 1
        ec = card.get("evidence_class")
        assert ec == "targeting", (
            f"G-4 regression: {play_id!r} surfaced as a PlayCard with "
            f"evidence_class={ec!r}. The post-G-4 contract is "
            f"structural targeting (NOT flag-gated). See "
            f"agent_outputs/code-refactor-engineer-g4-summary.md."
        )
    # Document that this assertion may be vacuous for these play_ids
    # on the Beauty fixture (they're typically held in Considered). The
    # invariant still binds the moment they surface as PlayCards.
    assert found >= 0


@pytest.mark.parametrize("play_id", sorted(G4_TARGETING_PLAYS))
def test_play_measurement_is_none_on_any_playcard(
    beauty_engine_run: Dict[str, Any], play_id: str
) -> None:
    """G-4 (c): on any PlayCard surface, measurement MUST be None.

    The EngineRun mapper drops the measurement block when
    ``evidence_class == "targeting"`` (see
    ``engine_run_adapter._build_measurement_from_legacy``). This
    invariant pins that contract end-to-end through the rendered
    payload.
    """
    for card in _iter_play_cards(beauty_engine_run):
        if str(card.get("play_id") or "") != play_id:
            continue
        meas = card.get("measurement")
        assert meas is None, (
            f"G-4 regression: {play_id!r} surfaced as a PlayCard with "
            f"measurement={meas!r}. The post-G-4 contract is "
            f"measurement is None for targeting-class plays."
        )


# ---------------------------------------------------------------------------
# (d) — source-text invariant: no 0.05/0.08 effect_abs literal in the
#       subscription_nudge / routine_builder emit blocks of action_engine.py.
# ---------------------------------------------------------------------------


def _extract_play_emit_block(source: str, play_id: str) -> str:
    """Slice the ``_compute_candidates`` emit block for ``play_id``.

    Looks for the ``"play_id": "<play_id>"`` literal and returns a
    window of ~60 lines centered on it (covers the full ``cands.append``
    dict).
    """
    needle = f'"play_id": "{play_id}"'
    idx = source.find(needle)
    if idx < 0:
        raise AssertionError(
            f"Could not locate emit block for {play_id!r} in "
            f"action_engine.py — has the candidate-dict shape changed?"
        )
    # Walk back / forward by ~60 lines to capture the surrounding dict.
    pre = source[:idx]
    start_line = pre.count("\n") - 30
    if start_line < 0:
        start_line = 0
    lines = source.splitlines()
    end_line = min(len(lines), start_line + 90)
    return "\n".join(lines[start_line:end_line])


# Forbidden literals: the historical Phase-2 fallback constants. Tolerate
# 0.05 in the rationale text only by scanning structural assignments.
_FORBIDDEN_LITERAL_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r'"effect_abs"\s*:\s*0\.05\b'),
    re.compile(r'"effect_abs"\s*:\s*0\.08\b'),
    re.compile(r'"effect_floor"\s*:\s*0\.05\b'),
    re.compile(r'"effect_floor"\s*:\s*0\.08\b'),
    # Bare local-variable assignment shape that previously seeded these:
    re.compile(r"effect_rb\s*=\s*0\.08\b"),
]


@pytest.mark.parametrize("play_id", sorted(G4_TARGETING_PLAYS))
def test_no_phase2_effect_constants_in_emit_block(play_id: str) -> None:
    """G-4 (d): no ``effect_abs=0.05`` / ``effect_abs=0.08`` /
    ``effect_floor=0.05/0.08`` literal remains in the
    ``subscription_nudge`` or ``routine_builder`` emit block of
    ``src/action_engine.py``.
    """
    src_path = REPO_ROOT / "src" / "action_engine.py"
    source = src_path.read_text(encoding="utf-8")
    block = _extract_play_emit_block(source, play_id)
    for pat in _FORBIDDEN_LITERAL_PATTERNS:
        m = pat.search(block)
        assert m is None, (
            f"G-4 regression: {play_id!r} emit block contains forbidden "
            f"Phase-2 constant {m.group(0)!r}. Drop the literal and "
            f"replace with float('nan') — these plays are permanently "
            f"targeting (no measured effect). See "
            f"agent_outputs/code-refactor-engineer-g4-summary.md."
        )


# ---------------------------------------------------------------------------
# Forbidden-fields invariant on the underlying Candidate objects.
# ---------------------------------------------------------------------------


_CANDIDATE_FORBIDDEN_FIELDS: frozenset = frozenset({
    "p_value",
    "q_value",
    "confidence",
    "confidence_score",
    "revenue_range",
    "ci",
    "ci_internal",
    "score",
    "final_score",
})


@pytest.mark.parametrize("play_id", sorted(G4_TARGETING_PLAYS))
def test_underlying_candidate_carries_no_forbidden_measured_fields(
    play_id: str,
) -> None:
    """The legacy candidate dict for these plays must not carry any of
    the M3 Candidate-forbidden fields (p/q/confidence/CI/score/etc).

    G-4 stamps ``evidence_class="targeting"`` directly on the candidate
    dict. The NaN ``p`` / ``q`` / ``effect_abs`` fields are tolerated
    because they're inputs to the legacy scoring path; they're stripped
    from the rendered payload by the EngineRun mapper's targeting
    short-circuit. The forbidden set here is the explicitly-NEW field
    names that would indicate a fabricated measurement object snuck
    back in (e.g. ``confidence_score``, ``p_value`` as a separate
    field, etc.).
    """
    src_path = REPO_ROOT / "src" / "action_engine.py"
    source = src_path.read_text(encoding="utf-8")
    block = _extract_play_emit_block(source, play_id)
    for f in _CANDIDATE_FORBIDDEN_FIELDS:
        pat = re.compile(rf'"{re.escape(f)}"\s*:')
        m = pat.search(block)
        assert m is None, (
            f"G-4 regression: {play_id!r} emit block declares forbidden "
            f"field {f!r}. Targeting plays must not carry "
            f"measurement-shaped fields on the candidate dict."
        )
