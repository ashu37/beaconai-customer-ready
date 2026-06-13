"""Narration MCP server package (Phase 1, handoff_architecture.md §2b/§3).

Reads a finalized engine_run snapshot via the manifest pointer, validates
it, parses via the schema authority (``src.engine_run``), and produces
merchant-facing prose per PlayCard. Authors language; invents NO numbers.

Imports here are all SDK-free (anthropic / mcp are imported lazily in
``llm_client`` / ``server``) so this package imports and tests run with no
``ANTHROPIC_API_KEY`` and no SDKs installed.
"""

from .atoms import CardAtoms, project_play_card, project_rejected_play
from .config import NarrationConfig
from .guards import GuardViolation, run_all_guards, safe_fallback_narration
from .llm_client import AnthropicLLMClient, LLMClient, MockLLMClient
from .narrator import CardNarration, Narrator
from .run_locator import (
    ResolvedRun,
    RunLocatorError,
    load_run,
    load_run_from_manifest,
    resolve_snapshot_path,
    validate_snapshot,
)

__all__ = [
    "CardAtoms",
    "project_play_card",
    "project_rejected_play",
    "NarrationConfig",
    "GuardViolation",
    "run_all_guards",
    "safe_fallback_narration",
    "LLMClient",
    "MockLLMClient",
    "AnthropicLLMClient",
    "Narrator",
    "CardNarration",
    "ResolvedRun",
    "RunLocatorError",
    "load_run",
    "load_run_from_manifest",
    "resolve_snapshot_path",
    "validate_snapshot",
]
