"""G-2 + S6-T2 — vertical-dispatched replenishment-size parser.

Loads ``config/replenishment_sizes.yaml`` and exposes per-vertical
matching surfaces used by ``empty_bottle`` (and any future replenishment-
timing emitter) to interpret SKU line-items.

Two surfaces:

1. Legacy boolean form — ``get_size_regex(vertical) -> Optional[str]``
   returns the per-vertical single regex string. Beauty + mixed use this
   form (M0 byte-identical contract).

2. S6-T2 unit-coherent form — ``parse_unit_coherent(vertical, text) ->
   Optional[tuple[str, int]]`` walks the vertical's ``coherent_units``
   list in declared order (precedence: ``count > day_supply > serving``)
   and returns the first match as ``(coherence_key, integer_value)``.
   Supplements uses this form. Unknown / un-parseable SKUs return
   ``None`` rather than fabricating a unit.

Coverage:

- ``beauty`` / ``mixed``: verbatim pre-G-2 Beauty regex via
  ``get_size_regex``; no ``coherent_units`` block.
- ``supplements``: ``coherent_units`` block covering count / day_supply
  / serving forms via ``parse_unit_coherent`` (S6-T2; closes KI-18).
- Unknown vertical: returns ``None`` from both surfaces (defensive).

This module is pure; load is cached at module level. No side effects.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "replenishment_sizes.yaml"


_cache: Optional[Dict[str, Any]] = None


def _load() -> Dict[str, Any]:
    """Load the YAML once and cache. Empty dict on missing/unreadable."""
    global _cache
    if _cache is not None:
        return _cache
    if not _CONFIG_PATH.exists():
        _cache = {}
        return _cache
    try:
        loaded = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        loaded = {}
    if not isinstance(loaded, dict):
        loaded = {}
    _cache = loaded
    return _cache


def _reset_cache_for_tests() -> None:
    """Invalidate the cache so tests can substitute config paths.

    Production code MUST NOT call this. Exposed for unit-test use only.
    """
    global _cache
    _cache = None
    _compiled_cache.clear()


def load_replenishment_sizes() -> Dict[str, Any]:
    """Public accessor for the parsed YAML (read-only contract)."""
    return dict(_load())


def get_size_regex(vertical: Optional[str]) -> Optional[str]:
    """Return the per-vertical size-regex string, or ``None`` if no
    parser coverage exists for this vertical.

    A ``None`` return means "the caller MUST treat this play as
    vertical-not-applicable rather than fall back to a hard-coded
    regex." Production callers should additionally check
    ``play_registry.PLAYS["empty_bottle"].vertical_applicable`` so the
    play is filtered upstream of the parser entirely.
    """
    if vertical is None:
        return None
    cfg = _load()
    block = cfg.get(str(vertical).strip().lower())
    if not isinstance(block, dict):
        return None
    rx = block.get("size_regex")
    if not isinstance(rx, str) or not rx.strip():
        return None
    return rx


_compiled_cache: Dict[str, List[Tuple[str, "re.Pattern[str]"]]] = {}


def _get_compiled_coherent_units(vertical: str) -> List[Tuple[str, "re.Pattern[str]"]]:
    """Return the per-vertical compiled ``(key, pattern)`` list.

    Compiles once per vertical and caches at module level. The compiled
    list preserves YAML declaration order, which is the precedence
    contract (count > day_supply > serving for supplements).
    """
    key = str(vertical).strip().lower()
    if key in _compiled_cache:
        return _compiled_cache[key]
    cfg = _load()
    block = cfg.get(key)
    compiled: List[Tuple[str, "re.Pattern[str]"]] = []
    if isinstance(block, dict):
        units = block.get("coherent_units")
        flags = re.IGNORECASE if (block.get("case_insensitive") is not False) else 0
        if isinstance(units, list):
            for entry in units:
                if not isinstance(entry, dict):
                    continue
                ck = entry.get("key")
                rx = entry.get("regex")
                if not isinstance(ck, str) or not isinstance(rx, str) or not rx.strip():
                    continue
                try:
                    compiled.append((ck, re.compile(rx, flags)))
                except re.error:
                    continue
    _compiled_cache[key] = compiled
    return compiled


def parse_unit_coherent(
    vertical: Optional[str], text: Optional[str]
) -> Optional[Tuple[str, int]]:
    """Parse a SKU/lineitem ``text`` against the vertical's coherent-unit
    regex list, returning the first match as ``(coherence_key, value)``.

    Precedence is YAML declaration order — for supplements:
    ``count > day_supply > serving``. ``None`` is returned for unknown
    verticals, missing text, or SKUs that match no pattern. Pure;
    deterministic; idempotent.
    """
    if vertical is None or text is None:
        return None
    if not isinstance(text, str) or not text.strip():
        return None
    units = _get_compiled_coherent_units(vertical)
    if not units:
        return None
    for ck, pattern in units:
        m = pattern.search(text)
        if m is None:
            continue
        try:
            value = int(m.group(1))
        except (IndexError, ValueError):
            continue
        return (ck, value)
    return None


def get_case_insensitive(vertical: Optional[str]) -> bool:
    """Return whether the per-vertical regex should match case-insensitive.

    Defaults to ``True`` (the Beauty pre-G-2 behavior used ``.str.lower()``
    before matching, which is equivalent).
    """
    if vertical is None:
        return True
    cfg = _load()
    block = cfg.get(str(vertical).strip().lower())
    if not isinstance(block, dict):
        return True
    val = block.get("case_insensitive")
    return True if val is None else bool(val)
