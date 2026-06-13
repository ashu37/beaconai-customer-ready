"""BeaconAI MCP servers (handoff layer).

Phase 1+ of the handoff architecture (``docs/handoff_architecture.md``).
Subpackages:

- ``narration`` — Narration MCP server: reads a finalized engine_run
  snapshot via the manifest pointer and produces merchant-facing prose
  per PlayCard. Authors language; invents NO numbers; honors RULE A and
  the DS locks (1/2/3/6/7/8). Stateless; never writes back to the engine.
"""
