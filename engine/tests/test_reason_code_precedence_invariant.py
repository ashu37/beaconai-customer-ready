"""Sprint 10 Ticket T3 — ML-fit-gate precedence invariant (contract pin).

Precedence: (1) audience-floor → (2) cohort p-value → (3) prior-validation
→ (4) ML-fit. When MODEL_FIT_REFUSED / MODEL_FIT_INSUFFICIENT_DATA is the
only failing gate, the card stays in Recommended Now (or Recommended
Experiment) and the audience ranking falls back to RFM/recency. Only
audience-floor, cohort-p, and prior-validation failures route to
Considered.

The two ML-fit ReasonCode values are SCHEMA-ADDITIVE and DORMANT at S10
close — no production emitter wires them. S13 wires the audience-ranking
integration that consumes them.

This file pins three contract assertions:

1. ``test_model_fit_codes_exist_in_enum`` — the two enum values exist with
   exact string values.
2. ``test_model_fit_codes_not_emitted_in_s10_close`` — load-bearing
   dormancy assertion: grep the production ``src/`` tree and confirm
   neither code is referenced. If S13 wires the emitters, this test
   updates with that ticket.
3. ``test_precedence_ranking_order_documented`` — encodes the
   DS-locked precedence ordering as a tuple constant so a future
   reader (or test) cannot reorder the gates without touching this
   pin.

No emitter wiring is exercised here. The tests run statically against
the enum definition + a source-text grep, so they compile and pass even
though the codes are dormant.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.engine_run import ReasonCode


# ---------------------------------------------------------------------------
# DS-locked precedence order (2026-05-26).
# ---------------------------------------------------------------------------
#
# Position 1 (highest): audience-floor — AUDIENCE_TOO_SMALL.
# Position 2: cohort p-value — NO_MEASURED_SIGNAL,
#             SIGNAL_INCONSISTENT_ACROSS_WINDOWS, WINDOW_DISAGREEMENT,
#             MATERIALITY_BELOW_FLOOR (the cohort-test family).
# Position 3: prior-validation — PRIOR_UNVALIDATED.
# Position 4 (lowest): ML-fit — MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED.
#
# This tuple ranks REPRESENTATIVE codes per gate, in precedence order
# (highest to lowest). It is intentionally narrow: the test enforces
# that the four gates appear in this order, not that each gate's full
# code family is enumerated here.
PRECEDENCE_ORDER: tuple[tuple[str, ReasonCode], ...] = (
    ("audience_floor", ReasonCode.AUDIENCE_TOO_SMALL),
    ("cohort_p_value", ReasonCode.NO_MEASURED_SIGNAL),
    ("prior_validation", ReasonCode.PRIOR_UNVALIDATED),
    ("ml_fit", ReasonCode.MODEL_FIT_REFUSED),
)


def test_model_fit_codes_exist_in_enum() -> None:
    """Both new ML-fit ReasonCode values exist with exact string values."""
    assert ReasonCode.MODEL_FIT_INSUFFICIENT_DATA.value == "model_fit_insufficient_data"
    assert ReasonCode.MODEL_FIT_REFUSED.value == "model_fit_refused"
    # Distinct from the run-level cold-start code.
    assert (
        ReasonCode.MODEL_FIT_INSUFFICIENT_DATA
        is not ReasonCode.COLD_START_INSUFFICIENT_DATA
    )
    assert (
        ReasonCode.MODEL_FIT_INSUFFICIENT_DATA.value
        != ReasonCode.COLD_START_INSUFFICIENT_DATA.value
    )


def test_model_fit_codes_not_emitted_in_s10_close() -> None:
    """ML-fit ReasonCodes never assigned to ``RejectedPlay.reason_code``.

    **Q-S13-4 LOCK (DS verdict 2026-05-28)**: ML-fit ReasonCodes
    (``MODEL_FIT_INSUFFICIENT_DATA``, ``MODEL_FIT_REFUSED``) emit
    ONLY on ``PlayCard.model_card_ref.fit_warnings`` per PlayCard.
    **NEVER on ``RejectedPlay.reason_code``** — ML-fit never demotes
    between slate roles. If a card stays in Recommended/Experiment,
    there is no RejectedPlay to attach to; emission on
    ``RejectedPlay.reason_code`` is structurally incoherent and would
    conceptually re-open a fourth demote channel.

    **S13-T2 AST refactor (2026-05-29):** this test was originally a
    raw grep across ``src/`` (S10-T3). With T1 emitting the codes as
    operator-trace strings inside
    :mod:`src.predictive.ranking_strategy` (and T2 promoting them
    onto :attr:`ModelCardRef.fit_warnings`), a string grep would
    over-match. The AST-aware check enforces the actual Q-S13-4
    LOCK invariant: no assignment of the form
    ``RejectedPlay(reason_code=ReasonCode.MODEL_FIT_*)`` or
    ``<rejected_play>.reason_code = ReasonCode.MODEL_FIT_*`` exists
    anywhere in ``src/``. The codes may freely appear as fit_warning
    strings (T1) or as the dormant enum definition
    (``src/engine_run.py``) — only ``RejectedPlay.reason_code``
    assignments are forbidden. The S13-T1
    ``ranking_strategy.py`` allowlist is REMOVED here (T1 carve-out
    no longer needed at the AST contract level).
    """

    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    assert src_dir.is_dir(), f"expected src/ at {src_dir}"

    forbidden_attrs = {
        "MODEL_FIT_INSUFFICIENT_DATA",
        "MODEL_FIT_REFUSED",
    }

    def _name_of(node: ast.AST) -> str:
        """Return the trailing identifier of a Name or Attribute node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    def _is_reason_code_model_fit(value: ast.AST) -> bool:
        """True iff ``value`` is ``ReasonCode.MODEL_FIT_*``.

        Matches ``ReasonCode.MODEL_FIT_INSUFFICIENT_DATA`` and
        ``ReasonCode.MODEL_FIT_REFUSED`` regardless of how
        ``ReasonCode`` is imported (named directly, qualified, etc.).
        """
        if not isinstance(value, ast.Attribute):
            return False
        if value.attr not in forbidden_attrs:
            return False
        # Require the parent to be ``ReasonCode`` (Name or Attribute
        # whose trailing identifier is ReasonCode).
        return _name_of(value.value) == "ReasonCode"

    def _is_rejected_play_reason_code_target(target: ast.AST) -> bool:
        """True iff ``target`` is ``<x>.reason_code`` on a RejectedPlay-shaped object.

        Conservative: any ``.reason_code`` attribute target counts
        (we can't statically prove the receiver is a RejectedPlay,
        but ``.reason_code`` is only defined on RejectedPlay in the
        engine schema — see :class:`src.engine_run.RejectedPlay`).
        """
        return isinstance(target, ast.Attribute) and target.attr == "reason_code"

    offending: list[tuple[str, int, str]] = []
    for py_path in src_dir.rglob("*.py"):
        try:
            source = py_path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=str(py_path))
        except SyntaxError:
            continue
        rel = str(py_path.relative_to(repo_root))

        for node in ast.walk(tree):
            # Pattern 1: assignment to RejectedPlay.reason_code (or
            # any .reason_code attribute) of a ReasonCode.MODEL_FIT_*.
            if isinstance(node, ast.Assign):
                if not _is_reason_code_model_fit(node.value):
                    continue
                for target in node.targets:
                    if _is_rejected_play_reason_code_target(target):
                        offending.append(
                            (rel, node.lineno, ast.unparse(node).strip())
                        )
            elif isinstance(node, ast.AnnAssign):
                if node.value is not None and _is_reason_code_model_fit(node.value):
                    if _is_rejected_play_reason_code_target(node.target):
                        offending.append(
                            (rel, node.lineno, ast.unparse(node).strip())
                        )

            # Pattern 2: ``RejectedPlay(reason_code=ReasonCode.MODEL_FIT_*)``
            # as a Call expression (constructor invocation).
            if isinstance(node, ast.Call):
                func_name = _name_of(node.func)
                if func_name != "RejectedPlay":
                    continue
                for kw in node.keywords:
                    if kw.arg != "reason_code":
                        continue
                    if _is_reason_code_model_fit(kw.value):
                        offending.append(
                            (rel, node.lineno, ast.unparse(node).strip())
                        )

    assert not offending, (
        "Q-S13-4 LOCK violation: MODEL_FIT_* ReasonCodes must NEVER "
        "be assigned to RejectedPlay.reason_code. The audit surface "
        "is PlayCard.model_card_ref.fit_warnings (List[str]). "
        f"Offenders: {offending}"
    )


def test_precedence_ranking_order_documented() -> None:
    """The four-gate precedence is fixed: audience > cohort-p > prior > ML-fit.

    Pinning the order as a tuple ensures a future refactor cannot silently
    reorder the gates without updating this test.
    """
    names = [gate for gate, _ in PRECEDENCE_ORDER]
    assert names == [
        "audience_floor",
        "cohort_p_value",
        "prior_validation",
        "ml_fit",
    ]
    # ML-fit is LAST (lowest precedence) — the load-bearing claim.
    assert PRECEDENCE_ORDER[-1][0] == "ml_fit"
    assert PRECEDENCE_ORDER[-1][1] == ReasonCode.MODEL_FIT_REFUSED
    # Audience-floor is FIRST (highest precedence).
    assert PRECEDENCE_ORDER[0][0] == "audience_floor"
    assert PRECEDENCE_ORDER[0][1] == ReasonCode.AUDIENCE_TOO_SMALL


def test_ml_fit_codes_are_string_enum_members() -> None:
    """Round-trip via .value works — same shape as every other ReasonCode.

    Defensive: confirms the new codes inherit the str-Enum shape so
    ``to_dict()`` serialization (and any downstream ``from_dict()``
    round-trip) treats them identically to the pre-existing codes.
    """
    for code in (ReasonCode.MODEL_FIT_INSUFFICIENT_DATA, ReasonCode.MODEL_FIT_REFUSED):
        assert isinstance(code, ReasonCode)
        assert isinstance(code.value, str)
        # Round-trip through the string value.
        assert ReasonCode(code.value) is code


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
