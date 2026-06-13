"""Narration MCP configuration.

Model + transport config read from env with safe defaults. NOTHING here
reads or requires ``ANTHROPIC_API_KEY`` at import time — the server must
import and run in MOCK mode without a key (see ``llm_client``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Default model. Sonnet is the default for cost (per the Phase 1 brief);
# override via NARRATION_MODEL env if a card's reasoning demands opus.
DEFAULT_MODEL = "claude-sonnet-4-6"

# Env var names — surfaced here so the "what I need to go live" note is
# single-sourced. The founder provides ANTHROPIC_API_KEY; the rest are
# optional overrides.
ENV_API_KEY = "ANTHROPIC_API_KEY"
ENV_MODEL = "NARRATION_MODEL"
ENV_MAX_TOKENS = "NARRATION_MAX_TOKENS"


@dataclass(frozen=True)
class NarrationConfig:
    """Runtime config for the narration layer.

    ``api_key`` is read lazily and may be ``None`` — when absent the
    server runs in MOCK mode (deterministic, no network). It is never
    required at import or construction time.
    """

    model: str = DEFAULT_MODEL
    max_tokens: int = 700
    api_key_present: bool = False

    @classmethod
    def from_env(cls) -> "NarrationConfig":
        model = os.getenv(ENV_MODEL, DEFAULT_MODEL).strip() or DEFAULT_MODEL
        raw_max = os.getenv(ENV_MAX_TOKENS, "").strip()
        try:
            max_tokens = int(raw_max) if raw_max else 700
        except ValueError:
            max_tokens = 700
        api_key_present = bool(os.getenv(ENV_API_KEY, "").strip())
        return cls(model=model, max_tokens=max_tokens, api_key_present=api_key_present)


__all__ = [
    "NarrationConfig",
    "DEFAULT_MODEL",
    "ENV_API_KEY",
    "ENV_MODEL",
    "ENV_MAX_TOKENS",
]
