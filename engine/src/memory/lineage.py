"""Lineage-id helper (S-2).

Per founder decision D-1 (2026-05-09):

    Any change to the SQL/Python logic that produces an audience definition
    MUST increment ``audience_definition_version`` by 1. Old lineages remain
    readable but fork to a new ``lineage_id`` by construction.

All four arguments are REQUIRED. None of ``store_id``, ``play_id``,
``audience_definition_id``, ``audience_definition_version`` may be ``None``
or empty. The function is pure and total; identical inputs yield an
identical sha1 hex digest across runs and across processes.

The hash is sha1 (not sha256) because lineage_id is a partition key, not
a security primitive — collision-resistance at 160 bits is plenty for the
bounded partition cardinality of {beauty, supplements, mixed} × O(20)
plays × O(50) audience definitions.
"""
from __future__ import annotations

import hashlib
from typing import Final

_VERSION: Final[int] = 1
_SEPARATOR: Final[str] = "\x1f"  # ASCII unit separator; cannot appear in any sane id


def compute_lineage_id(
    store_id: str,
    play_id: str,
    audience_definition_id: str,
    audience_definition_version: int,
) -> str:
    """Return a 40-char sha1 hex digest of the lineage tuple.

    Raises ``ValueError`` if any component is missing or shaped wrong.
    Coerces ``audience_definition_version`` strictly: must be ``int``
    (or losslessly representable as int) and ``>= 1``.
    """
    if not isinstance(store_id, str) or not store_id:
        raise ValueError("store_id must be a non-empty str")
    if not isinstance(play_id, str) or not play_id:
        raise ValueError("play_id must be a non-empty str")
    if not isinstance(audience_definition_id, str) or not audience_definition_id:
        raise ValueError("audience_definition_id must be a non-empty str")
    if isinstance(audience_definition_version, bool) or not isinstance(
        audience_definition_version, int
    ):
        raise ValueError("audience_definition_version must be an int")
    if audience_definition_version < 1:
        raise ValueError("audience_definition_version must be >= 1")

    # Length-prefix each component so ("a", "bc") cannot collide with
    # ("ab", "c"). Belt-and-braces alongside the unit separator.
    parts = [
        f"v{_VERSION}",
        f"{len(store_id)}:{store_id}",
        f"{len(play_id)}:{play_id}",
        f"{len(audience_definition_id)}:{audience_definition_id}",
        f"adv:{audience_definition_version}",
    ]
    payload = _SEPARATOR.join(parts).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


__all__ = ["compute_lineage_id"]
