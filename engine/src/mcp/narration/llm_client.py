"""Injectable LLM client for narration — Anthropic (Claude) + a mock.

Design constraints (Phase 1 brief):

- The Anthropic SDK is imported LAZILY (inside the method that needs it),
  so this module imports cleanly with no ``anthropic`` package and no
  ``ANTHROPIC_API_KEY``.
- The client is INJECTABLE: the narrator takes an ``LLMClient`` instance.
  Tests pass :class:`MockLLMClient` (deterministic, no network).
- ``AnthropicLLMClient`` uses prompt caching on the stable system prompt +
  the mechanism-contract text via ``cache_control`` so the large reused
  preamble is not re-billed per card.

The client speaks a tiny protocol: ``complete(system_blocks, user_text)``
returns a single string of model text. The narrator owns prompt assembly
and JSON parsing so the client stays transport-only.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .config import DEFAULT_MODEL, ENV_API_KEY


@runtime_checkable
class LLMClient(Protocol):
    """Minimal completion protocol the narrator depends on."""

    def complete(self, system_blocks: List[Dict[str, Any]], user_text: str) -> str:
        """Return the model's text for the given system blocks + user msg.

        ``system_blocks`` is a list of Anthropic content blocks (each a
        dict with ``type``/``text`` and optionally ``cache_control``).
        """
        ...

    @property
    def mode(self) -> str:
        """``"anthropic"`` or ``"mock"`` — for diagnostics/reporting."""
        ...


class MockLLMClient:
    """Deterministic offline client. NO network. Used by all tests.

    It echoes a structured JSON narration assembled purely from the atoms
    embedded in ``user_text`` (the narrator embeds the card atoms as a
    JSON block). This lets us exercise the full pipeline + guards without
    a key, and gives stable, assertable output.

    A pluggable ``responder`` callable can override the default behavior
    for tests that want to simulate a *misbehaving* LLM (e.g. one that
    fabricates a dollar figure) so the guards can be tested.
    """

    def __init__(self, responder: Optional[Any] = None) -> None:
        self._responder = responder

    @property
    def mode(self) -> str:
        return "mock"

    def complete(self, system_blocks: List[Dict[str, Any]], user_text: str) -> str:
        if self._responder is not None:
            return self._responder(system_blocks, user_text)
        atoms = _extract_atoms_block(user_text)
        return json.dumps(_default_mock_narration(atoms))


def _extract_atoms_block(user_text: str) -> Dict[str, Any]:
    """Pull the ``<atoms>...</atoms>`` JSON the narrator embeds."""
    start = user_text.find("<atoms>")
    end = user_text.find("</atoms>")
    if start == -1 or end == -1:
        return {}
    raw = user_text[start + len("<atoms>") : end].strip()
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}


def _default_mock_narration(atoms: Dict[str, Any]) -> Dict[str, Any]:
    """Build a safe, deterministic narration from atoms.

    Crucially the mock NEVER invents a dollar figure that is not in
    ``allowed_dollar_figures``, and emits NO mechanism line when
    ``mechanism`` is None. This makes the happy-path tests assert real
    lock conformance rather than a fixed string.
    """
    play_id = atoms.get("play_id", "play")
    mechanism = atoms.get("mechanism")
    allowed = atoms.get("allowed_dollar_figures") or []
    audience = atoms.get("audience") or {}
    size = audience.get("size")

    # play_thesis
    thesis = f"This play targets the {play_id} opportunity"
    if isinstance(size, int):
        thesis += f" across an audience of {size:,} customers"
    thesis += "."

    # what_we_d_send — only mention a mechanism if one is present (RULE A)
    if mechanism is None:
        what = "We would reach this audience with a tailored campaign."
    else:
        mtype = mechanism.get("type", "")
        what = f"We would run a {mtype.lower().replace('_', ' ')} sequence."

    # evidence_summary — dollar figure only if allowed; framed as sizing
    if allowed:
        lo = min(allowed)
        hi = max(allowed)
        if lo == hi:
            evidence = f"The opportunity is sized at approximately ${lo:,.0f}."
        else:
            evidence = f"The opportunity is sized in the ${lo:,.0f}-${hi:,.0f} range."
    else:
        evidence = "We are sizing this on audience and context; no dollar figure is stated."

    return {
        "play_thesis": thesis,
        "what_we_d_send": what,
        "evidence_summary": evidence,
    }


class AnthropicLLMClient:
    """Real Anthropic client. Lazily imports the SDK; reads the key from
    env (or an explicit arg). Uses prompt caching on system blocks.

    Construction does NOT require a key — it raises only if ``complete`` is
    called without one. This keeps import + MOCK-mode construction safe.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 700,
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._api_key = api_key or os.getenv(ENV_API_KEY) or None
        self._client = None  # lazily constructed

    @property
    def mode(self) -> str:
        return "anthropic"

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError(
                f"{ENV_API_KEY} is not set; AnthropicLLMClient cannot make a "
                "network call. Use MockLLMClient for offline/test runs."
            )
        try:
            import anthropic  # lazy import — not required at module import
        except ImportError as e:  # pragma: no cover - exercised only with SDK absent
            raise RuntimeError(
                "the 'anthropic' package is not installed; "
                "install it with: pip install anthropic"
            ) from e
        self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(self, system_blocks: List[Dict[str, Any]], user_text: str) -> str:
        client = self._ensure_client()
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_blocks,  # blocks may carry cache_control
            messages=[{"role": "user", "content": user_text}],
        )
        # Concatenate text blocks from the response.
        parts: List[str] = []
        for block in getattr(resp, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts)


__all__ = ["LLMClient", "MockLLMClient", "AnthropicLLMClient"]
