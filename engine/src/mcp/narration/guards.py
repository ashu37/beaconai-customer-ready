"""Output-validation guards for the DS locks (1/2/3/6/7/8).

The atoms projection (``atoms.py``) keeps footgun fields out of the
prompt. THESE guards verify the LLM's *output* — they are what make the
Stop-Coding Line structural rather than prompt-dependent. The LLM authors
language; the guards prove it invented no number and laundered no signal.

Each guard returns a list of :class:`GuardViolation`. The narrator's
policy is FAIL-CLOSED: on any violation it scrubs the offending dollar
figure / falls back to a safe template line rather than emitting an
unverified claim (lock 8 master guard).

Guard map:

- L8 (master) — :func:`scrub_dollar_figures`: any ``$`` figure in the
  prose that is not traceable to ``atoms.allowed_dollar_figures`` (a
  non-suppressed, source=BLEND p10/p50/p90) is a violation.
- L2 — :func:`check_no_lift_framing`: a non-STORE_MEASURED card may not
  frame its revenue as lift / incremental / expected-from-sending.
- L7 / RULE A — :func:`check_no_fabricated_mechanism`: when
  ``atoms.mechanism is None`` the prose must contain no mechanism line.
- L1 — :func:`check_no_evidence_class_leak`: the internal evidence-class
  vocabulary ("measured"/"directional"/"targeting"/"weak" as an evidence
  *claim*) must not appear; only the chip is surfaceable.
- L3 — :func:`check_no_fit_warning_leak`: fit-warning vocabulary
  (incl. MODEL_FIT_REFUSED) must not appear as a reason.
- L6 — :func:`check_no_aov_or_csv_segment`: no merchant-facing AOV
  figure exists in v2.0.0; segment claims only from the projected
  segment_name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

from .atoms import CardAtoms

# A dollar figure: $1,234 or $1234.50 etc.
_DOLLAR_RE = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)")

# Lift / incremental framing forbidden for non-STORE_MEASURED cards (L2).
_LIFT_TERMS = [
    "lift",
    "incremental",
    "expected from sending",
    "expected gain",
    "you will earn",
    "you'll earn",
    "additional revenue from",
    "extra revenue from",
    "revenue you'll gain",
    "uplift",
]

# Internal evidence-class vocabulary used AS AN EVIDENCE CLAIM (L1). We do
# NOT ban the words wholesale (e.g. "measured" can appear innocently) — we
# ban the overclaim phrasings that launder the internal class.
_EVIDENCE_CLASS_CLAIMS = [
    "we measured this on your store",
    "we measured this",
    "measured on your store",
    "this is a measured result",
    "measured evidence",
    "evidence class",
]

# Fit-warning vocabulary (L3) — audit-only, never a merchant-facing reason.
_FIT_WARNING_TERMS = [
    "model_fit_refused",
    "model fit refused",
    "fit_warning",
    "fit warning",
    "provisional_selected",
    "model_fit_insufficient_data",
    "model fit insufficient",
    "bg/nbd",
    "bgnbd",
    "survival model",
    "collaborative filtering fell back",
    "model fell back",
    "ml fit",
]

# AOV vocabulary (L6) — no merchant-facing AOV figure exists in v2.0.0.
_AOV_TERMS = [
    "average order value",
    "aov of $",
    "aov is $",
    "their aov",
    "individual aov",
    "per-customer aov",
]


@dataclass(frozen=True)
class GuardViolation:
    lock: str  # e.g. "L8"
    detail: str


def _all_text(narration: Dict[str, str]) -> str:
    return " ".join(str(v or "") for v in narration.values())


def _figures_match(found: float, allowed: List[float], tol: float = 0.5) -> bool:
    """A found $ figure matches an allowed one if it equals it, OR is a
    sensible rounding of it (whole-dollar / thousands). We allow the LLM
    to round 13034.50 -> 13,034 or 13,035, but not to invent a new number.
    """
    for a in allowed:
        if abs(found - a) <= tol:
            return True
        # rounding to nearest dollar
        if abs(found - round(a)) <= tol:
            return True
        # rounding to nearest 10 / 100 / 1000 (common copy rounding)
        for unit in (10, 100, 1000):
            if abs(found - round(a / unit) * unit) <= tol:
                return True
    return False


def scrub_dollar_figures(narration: Dict[str, str], atoms: CardAtoms) -> List[GuardViolation]:
    """L8 master guard: every $ figure in prose must trace to an allowed one."""
    violations: List[GuardViolation] = []
    allowed = list(atoms.allowed_dollar_figures or [])
    for field_name, text in narration.items():
        if not text:
            continue
        for m in _DOLLAR_RE.finditer(text):
            raw = m.group(1).replace(",", "")
            try:
                val = float(raw)
            except ValueError:
                continue
            if not allowed:
                violations.append(
                    GuardViolation(
                        "L8",
                        f"dollar figure ${m.group(1)} in '{field_name}' but no "
                        "allowed (non-suppressed, source=BLEND) range exists",
                    )
                )
            elif not _figures_match(val, allowed):
                violations.append(
                    GuardViolation(
                        "L8",
                        f"dollar figure ${m.group(1)} in '{field_name}' is not "
                        f"traceable to allowed figures {allowed}",
                    )
                )
    return violations


def check_no_lift_framing(narration: Dict[str, str], atoms: CardAtoms) -> List[GuardViolation]:
    """L2: non-STORE_MEASURED cards may not frame revenue as lift."""
    if atoms.evidence_source == "STORE_MEASURED":
        return []  # Tier-A may claim lift — but zero such cards exist today.
    text = _all_text(narration).lower()
    return [
        GuardViolation("L2", f"forbidden lift-framing term '{term}' on a "
                             f"non-STORE_MEASURED card")
        for term in _LIFT_TERMS
        if term in text
    ]


def check_no_fabricated_mechanism(
    narration: Dict[str, str], atoms: CardAtoms
) -> List[GuardViolation]:
    """L7 / RULE A: mechanism is None => no mechanism line in 'what_we_d_send'.

    We approximate "mechanism line" by checking the ``what_we_d_send`` field
    for sequence/mechanism-naming verbs when ``atoms.mechanism is None``.
    """
    if atoms.mechanism is not None:
        return []
    what = (narration.get("what_we_d_send") or "").lower()
    mechanism_signals = [
        "winback",
        "win-back",
        "reactivation email",
        "bundle offer",
        "discount dependency",
        "replenishment reminder",
        "subscription nudge",
        "routine builder",
        "lookalike",
        "category expansion",
        "bestseller amplify",
        "nudge sequence",
    ]
    return [
        GuardViolation("L7", f"mechanism term '{sig}' present but mechanism_intent "
                             "is None (RULE A: no mechanism line)")
        for sig in mechanism_signals
        if sig in what
    ]


def check_no_evidence_class_leak(
    narration: Dict[str, str], atoms: CardAtoms
) -> List[GuardViolation]:
    """L1: the internal evidence-class overclaim phrasings must not appear."""
    text = _all_text(narration).lower()
    return [
        GuardViolation("L1", f"evidence-class overclaim phrase '{phrase}'")
        for phrase in _EVIDENCE_CLASS_CLAIMS
        if phrase in text
    ]


def check_no_fit_warning_leak(
    narration: Dict[str, str], atoms: CardAtoms
) -> List[GuardViolation]:
    """L3: fit-warning vocabulary is audit-only, never narrated."""
    text = _all_text(narration).lower()
    return [
        GuardViolation("L3", f"fit-warning term '{term}' (audit-only) appeared")
        for term in _FIT_WARNING_TERMS
        if term in text
    ]


def check_no_aov_or_csv_segment(
    narration: Dict[str, str], atoms: CardAtoms
) -> List[GuardViolation]:
    """L6: no merchant-facing AOV figure exists in v2.0.0; segment claims
    only from the projected segment_name."""
    text = _all_text(narration).lower()
    violations = [
        GuardViolation("L6", f"AOV term '{term}' (no merchant-facing AOV in v2.0.0)")
        for term in _AOV_TERMS
        if term in text
    ]
    return violations


_ALL_GUARDS = [
    scrub_dollar_figures,
    check_no_lift_framing,
    check_no_fabricated_mechanism,
    check_no_evidence_class_leak,
    check_no_fit_warning_leak,
    check_no_aov_or_csv_segment,
]


def run_all_guards(narration: Dict[str, str], atoms: CardAtoms) -> List[GuardViolation]:
    """Run every guard; return the aggregated violation list (empty == clean)."""
    out: List[GuardViolation] = []
    for guard in _ALL_GUARDS:
        out.extend(guard(narration, atoms))
    return out


def safe_fallback_narration(atoms: CardAtoms) -> Dict[str, str]:
    """Deterministic, lock-clean fallback used when guards fail closed.

    States NO dollar figure, NO mechanism unless one is typed, NO lift
    framing. This is the safe line the master guard falls back to rather
    than emitting an unverified number.
    """
    size = (atoms.audience or {}).get("size")
    aud_clause = ""
    if isinstance(size, int):
        aud_clause = f" The audience is approximately {size:,} customers."

    if atoms.mechanism is None:
        what = "We would reach this audience with a tailored campaign."
    else:
        mtype = str(atoms.mechanism.get("type", "")).lower().replace("_", " ")
        what = f"We would run a {mtype} campaign for this audience."

    return {
        "play_thesis": f"This is the {atoms.play_id} play.{aud_clause}",
        "what_we_d_send": what,
        "evidence_summary": (
            "We are sizing this on audience and context; no dollar figure "
            "is stated for this play."
        ),
    }


__all__ = [
    "GuardViolation",
    "scrub_dollar_figures",
    "check_no_lift_framing",
    "check_no_fabricated_mechanism",
    "check_no_evidence_class_leak",
    "check_no_fit_warning_leak",
    "check_no_aov_or_csv_segment",
    "run_all_guards",
    "safe_fallback_narration",
]
