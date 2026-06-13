"""Narration MCP server (stdio transport).

Per handoff_architecture.md §3: the Express broker speaks stdio to this
Python server; the browser never speaks MCP. The MCP SDK is imported
LAZILY inside ``build_server`` / ``main`` so this module imports cleanly
without the ``mcp`` package (tests do not require the SDK).

Tools exposed:
- ``narrate_run``    {store_id, run_id, data_root?} -> full run narration
- ``narrate_card``   {store_id, run_id, play_id, data_root?} -> one card

Both resolve the snapshot via the manifest pointer, validate, parse with
the schema authority, and narrate through the injected LLM client
(defaults to mock; swap to Anthropic once the key lands).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .config import NarrationConfig
from .llm_client import AnthropicLLMClient, LLMClient, MockLLMClient
from .narrator import Narrator
from .run_locator import load_run, validate_snapshot

DEFAULT_DATA_ROOT = "data"


def _default_llm(config: NarrationConfig) -> LLMClient:
    """Pick the LLM client. Anthropic when a key is present, else mock.

    Construction never crashes on a missing key — mock is the safe
    default so the server runs end-to-end offline.
    """
    if config.api_key_present:
        return AnthropicLLMClient(model=config.model, max_tokens=config.max_tokens)
    return MockLLMClient()


def narrate_run_payload(
    store_id: str,
    run_id: str,
    *,
    data_root: str = DEFAULT_DATA_ROOT,
    narrator: Optional[Narrator] = None,
) -> Dict[str, Any]:
    """Resolve -> validate -> parse -> narrate a full run. Pure read."""
    resolved = load_run(Path(data_root), store_id, run_id)
    warn = validate_snapshot(resolved.snapshot_path)
    nar = narrator or Narrator(_default_llm(NarrationConfig.from_env()))
    out = nar.narrate_run(resolved.engine_run)
    if warn:
        out["validation_warning"] = warn
    out["snapshot_path"] = str(resolved.snapshot_path)
    out["manifest_path"] = str(resolved.manifest_path)
    return out


def narrate_card_payload(
    store_id: str,
    run_id: str,
    play_id: str,
    *,
    data_root: str = DEFAULT_DATA_ROOT,
    narrator: Optional[Narrator] = None,
) -> Dict[str, Any]:
    """Narrate a single card by play_id (searches all three lanes)."""
    resolved = load_run(Path(data_root), store_id, run_id)
    warn = validate_snapshot(resolved.snapshot_path)
    er = resolved.engine_run
    nar = narrator or Narrator(_default_llm(NarrationConfig.from_env()))

    for c in er.recommendations or []:
        if c.play_id == play_id:
            res = nar.narrate_card(c, "recommendation", run_id=er.run_id, store_id=er.store_id)
            return _wrap(res.to_dict(), resolved, warn)
    for c in er.recommended_experiments or []:
        if c.play_id == play_id:
            res = nar.narrate_card(
                c, "recommended_experiment", run_id=er.run_id, store_id=er.store_id
            )
            return _wrap(res.to_dict(), resolved, warn)
    for rp in er.considered or []:
        if rp.play_id == play_id:
            res = nar.narrate_considered(rp, run_id=er.run_id, store_id=er.store_id)
            return _wrap(res.to_dict(), resolved, warn)

    return {"error": f"play_id '{play_id}' not found in run {run_id}"}


def _wrap(card_dict: Dict[str, Any], resolved, warn: Optional[str]) -> Dict[str, Any]:
    out = {"schema": "beaconai.narration.v1", "card": card_dict}
    if warn:
        out["validation_warning"] = warn
    out["snapshot_path"] = str(resolved.snapshot_path)
    return out


def build_server(narrator: Optional[Narrator] = None):
    """Construct the MCP server. Lazily imports the MCP SDK.

    Returns the configured ``FastMCP`` instance. The handler closures call
    the pure ``narrate_*_payload`` functions above so the MCP layer is a
    thin transport shim (and the payload functions stay unit-testable
    without the SDK).
    """
    try:
        from mcp.server.fastmcp import FastMCP  # lazy — SDK not required for tests
    except ImportError as e:  # pragma: no cover - exercised only without SDK
        raise RuntimeError(
            "the 'mcp' package is not installed; install it with: "
            "pip install mcp"
        ) from e

    server = FastMCP("beaconai-narration")

    @server.tool()
    def narrate_run(store_id: str, run_id: str, data_root: str = DEFAULT_DATA_ROOT) -> str:
        """Narrate every PlayCard in a finalized run (resolved via manifest)."""
        return json.dumps(
            narrate_run_payload(store_id, run_id, data_root=data_root, narrator=narrator)
        )

    @server.tool()
    def narrate_card(
        store_id: str, run_id: str, play_id: str, data_root: str = DEFAULT_DATA_ROOT
    ) -> str:
        """Narrate a single PlayCard by play_id."""
        return json.dumps(
            narrate_card_payload(
                store_id, run_id, play_id, data_root=data_root, narrator=narrator
            )
        )

    return server


def main() -> None:  # pragma: no cover - process entry point
    """stdio entry point for the Express broker."""
    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = [
    "build_server",
    "narrate_run_payload",
    "narrate_card_payload",
    "main",
]
