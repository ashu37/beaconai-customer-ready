"""The narrator — assembles prompts, calls the injected LLM, runs guards.

Flow per card:
  PlayCard --project--> CardAtoms --prompt--> LLM --parse--> narration dict
  --run_all_guards--> {clean: return | violations: fail-closed fallback}

The narration artifact is keyed (run_id, play_id) and is NEVER written
back to the engine. The narrator returns a dict; the server/caller decides
where to persist it (a separate artifact, per handoff_architecture.md §2b).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...engine_run import EngineRun
from .atoms import CardAtoms, project_play_card, project_rejected_play
from .config import NarrationConfig
from .guards import GuardViolation, run_all_guards, safe_fallback_narration
from .llm_client import LLMClient, MockLLMClient

# Stable system preamble — cached across cards (Anthropic prompt caching).
_SYSTEM_PREAMBLE = """You are the BeaconAI narration writer. You turn typed decision atoms \
emitted by the BeaconAI engine into concise, merchant-facing prose for an \
e-commerce store owner. You author LANGUAGE ONLY. You NEVER invent numbers.

Hard rules (violating any is a defect):
- Never state a dollar figure that is not in the card's `allowed_dollar_figures`.
  If that list is empty, state no dollar figure at all.
- Never frame any dollar figure as "lift", "incremental", or "expected from \
sending" unless the card's evidence_source is exactly "STORE_MEASURED".
- If `mechanism` is null, write NO mechanism/sequence line. Silence on \
mechanism is correct, not a missing-data error.
- If `mechanism` is present, name the mechanism type but use ONLY the \
parameters present in `mechanism.parameters`. Invent no dollar gap, share, \
SKU, lift %, or audience size that is not in the atoms.
- Never mention model fit, model fallback, BG/NBD, survival, or any internal \
ML machinery. Never claim "we measured this on your store".
- Never state an average order value (AOV).
- Use `segment_name` only if it is present.

Output STRICT JSON with exactly these keys and nothing else:
{"play_thesis": "...", "what_we_d_send": "...", "evidence_summary": "..."}
- play_thesis: 1-2 sentences on why this play matters for this store.
- what_we_d_send: 1 sentence on the outreach. Honor the mechanism rules above.
- evidence_summary: 1-2 sentences sizing the opportunity from the atoms. \
Respect the `revenue_note` guidance verbatim.
"""


@lru_cache(maxsize=1)
def _mechanism_contract_text() -> str:
    """Load the DS-locked mechanism contract for the cached system block.

    This is large and reused on every card — exactly the content prompt
    caching is for. Loaded once per process.
    """
    repo_root = Path(__file__).resolve().parents[3]
    contract = repo_root / "docs" / "mechanism_contract.md"
    try:
        return contract.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return "(mechanism_contract.md unavailable)"


def _system_blocks() -> List[Dict[str, Any]]:
    """Anthropic content blocks for the system prompt, with cache_control on
    the stable preamble + the (large) mechanism contract so they are not
    re-billed per card."""
    return [
        {
            "type": "text",
            "text": _SYSTEM_PREAMBLE,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": "MECHANISM CONTRACT (DS-locked, verbatim):\n\n"
            + _mechanism_contract_text(),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _user_text(atoms: CardAtoms) -> str:
    """Embed the lock-clean atoms as a tagged JSON block."""
    block = json.dumps(atoms.to_prompt_dict(), indent=2, sort_keys=True)
    return (
        "Narrate the following PlayCard. Use ONLY the atoms below; invent "
        "nothing.\n\n<atoms>\n" + block + "\n</atoms>"
    )


_REQUIRED_KEYS = ("play_thesis", "what_we_d_send", "evidence_summary")


def _parse_narration(raw: str) -> Optional[Dict[str, str]]:
    """Parse the model's JSON output to the 3-key narration dict."""
    if not raw:
        return None
    text = raw.strip()
    # Tolerate code fences.
    if text.startswith("```"):
        text = text.strip("`")
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1 :]
    # Find the outermost JSON object.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None
    out = {k: str(obj.get(k, "") or "") for k in _REQUIRED_KEYS}
    if not any(out.values()):
        return None
    return out


@dataclass
class CardNarration:
    """The narration result for one card."""

    run_id: str
    store_id: str
    play_id: str
    role: str
    play_thesis: str
    what_we_d_send: str
    evidence_summary: str
    guard_violations: List[str] = field(default_factory=list)
    used_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "store_id": self.store_id,
            "play_id": self.play_id,
            "role": self.role,
            "play_thesis": self.play_thesis,
            "what_we_d_send": self.what_we_d_send,
            "evidence_summary": self.evidence_summary,
            "guard_violations": self.guard_violations,
            "used_fallback": self.used_fallback,
        }


class Narrator:
    """Stateless narrator over an injected LLM client.

    If no client is provided, defaults to :class:`MockLLMClient` so the
    server runs end-to-end without a key. Pass ``AnthropicLLMClient`` once
    the founder provides ANTHROPIC_API_KEY.
    """

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        config: Optional[NarrationConfig] = None,
    ) -> None:
        self.config = config or NarrationConfig.from_env()
        self.llm: LLMClient = llm or MockLLMClient()

    @property
    def mode(self) -> str:
        return self.llm.mode

    def narrate_atoms(
        self, atoms: CardAtoms, *, run_id: str, store_id: str
    ) -> CardNarration:
        """Narrate one already-projected card atom bundle (with guards)."""
        raw = ""
        try:
            raw = self.llm.complete(_system_blocks(), _user_text(atoms))
        except Exception as e:  # noqa: BLE001 — LLM failure => fail closed
            return self._fallback(
                atoms, run_id=run_id, store_id=store_id,
                violations=[f"LLM error: {e}"],
            )

        narration = _parse_narration(raw)
        if narration is None:
            return self._fallback(
                atoms, run_id=run_id, store_id=store_id,
                violations=["LLM output was not parseable JSON"],
            )

        violations = run_all_guards(narration, atoms)
        if violations:
            # FAIL CLOSED (lock-8 policy): drop the unverified output and
            # emit the safe template line rather than a laundered claim.
            return self._fallback(
                atoms, run_id=run_id, store_id=store_id,
                violations=[f"{v.lock}: {v.detail}" for v in violations],
            )

        return CardNarration(
            run_id=run_id,
            store_id=store_id,
            play_id=atoms.play_id,
            role=atoms.role,
            play_thesis=narration["play_thesis"],
            what_we_d_send=narration["what_we_d_send"],
            evidence_summary=narration["evidence_summary"],
            guard_violations=[],
            used_fallback=False,
        )

    def _fallback(
        self, atoms: CardAtoms, *, run_id: str, store_id: str, violations: List[str]
    ) -> CardNarration:
        safe = safe_fallback_narration(atoms)
        # The fallback itself must be clean — assert defensively.
        residual = run_all_guards(safe, atoms)
        viol = list(violations)
        if residual:
            viol += [f"FALLBACK-{v.lock}: {v.detail}" for v in residual]
        return CardNarration(
            run_id=run_id,
            store_id=store_id,
            play_id=atoms.play_id,
            role=atoms.role,
            play_thesis=safe["play_thesis"],
            what_we_d_send=safe["what_we_d_send"],
            evidence_summary=safe["evidence_summary"],
            guard_violations=viol,
            used_fallback=True,
        )

    # --- run-level convenience ---------------------------------------------

    def narrate_card(self, card, role: str, *, run_id: str, store_id: str) -> CardNarration:
        atoms = project_play_card(card, role)
        return self.narrate_atoms(atoms, run_id=run_id, store_id=store_id)

    def narrate_considered(self, rp, *, run_id: str, store_id: str) -> CardNarration:
        atoms = project_rejected_play(rp)
        return self.narrate_atoms(atoms, run_id=run_id, store_id=store_id)

    def narrate_run(self, engine_run: EngineRun) -> Dict[str, Any]:
        """Narrate every card in a run. Returns the narration artifact dict
        keyed (run_id, play_id). Pure read; never writes back."""
        run_id = str(engine_run.run_id or "unknown")
        store_id = str(engine_run.store_id or "unknown")

        cards: List[CardNarration] = []
        for c in engine_run.recommendations or []:
            cards.append(self.narrate_card(c, "recommendation", run_id=run_id, store_id=store_id))
        for c in engine_run.recommended_experiments or []:
            cards.append(
                self.narrate_card(c, "recommended_experiment", run_id=run_id, store_id=store_id)
            )
        for rp in engine_run.considered or []:
            cards.append(self.narrate_considered(rp, run_id=run_id, store_id=store_id))

        return {
            "schema": "beaconai.narration.v1",
            "run_id": run_id,
            "store_id": store_id,
            "engine_schema_version": engine_run.schema_version,
            "llm_mode": self.mode,
            "model": self.config.model if self.mode == "anthropic" else None,
            "cards": [c.to_dict() for c in cards],
        }


__all__ = ["Narrator", "CardNarration"]
