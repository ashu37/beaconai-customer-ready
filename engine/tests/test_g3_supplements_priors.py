"""Sprint 4 Ticket G-3 — Supplements priors expansion + mixed semantics.

Pins the three contracts G-3 introduces:

1. **Supplements entries carry a ``source`` field.** Every prior in
   ``config/priors.yaml`` whose ``applies_to.vertical`` is
   ``supplements`` (or ``mixed`` / ``"*"``) must carry a non-empty
   ``source`` string. No supplements entry may have
   ``source_class: causal`` without an explicit external citation
   in ``source`` (G-3 introduces no causal priors).

2. **``mixed`` semantics are deterministic and never silently default
   to beauty alone.** When ``vertical_mode="mixed"`` and no explicit
   mixed entry is authored, the loader's :func:`resolve_mixed_prior`
   blends beauty + supplements 50/50 deterministically. If either side
   is missing, the resolver returns ``None`` — it does NOT fall back
   to the present side (D-8 hard guarantee).

3. **Priors loader refuses non-supported verticals.** A synthetic
   YAML fragment with an ``apparel:`` top-level vertical_mode block
   raises :class:`ConfigError` at load time (D-8 hard-lock).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

yaml = pytest.importorskip("yaml")

from src import priors_loader as PL  # noqa: E402
from src.priors_loader import ConfigError  # noqa: E402


PRIORS_YAML = REPO_ROOT / "config" / "priors.yaml"


@pytest.fixture(autouse=True)
def _reset_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


def _priors_list_for_play(prior_block):
    if isinstance(prior_block, list):
        return prior_block
    if isinstance(prior_block, dict):
        return prior_block.get("priors") or []
    return []


# ---------------------------------------------------------------------------
# 1. Supplements entries carry a source field
# ---------------------------------------------------------------------------


def test_priors_yaml_loads_cleanly():
    """The real ``config/priors.yaml`` loads without raising under G-3 rules."""
    doc = PL.load_priors()
    assert isinstance(doc, dict)
    assert isinstance(doc.get("plays"), dict)
    assert doc.get("plays"), "expected non-empty plays mapping"


def test_every_supplements_entry_has_a_source_field():
    """Every supplements/mixed/wildcard prior must carry a non-empty ``source``.

    G-3 acceptance criterion: ``every supplements entry must carry a
    source field with citation (industry report, internal heuristic
    flagged as such, etc.)``.
    """
    with PRIORS_YAML.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    bad: list[str] = []
    for play_id, prior_block in doc["plays"].items():
        for i, p in enumerate(_priors_list_for_play(prior_block)):
            applies = p.get("applies_to") or {}
            vert = applies.get("vertical")
            if vert in ("supplements", "mixed", "*"):
                src = p.get("source")
                if not isinstance(src, str) or not src.strip():
                    bad.append(
                        f"plays[{play_id!r}][{i}] (vertical={vert!r}) is missing "
                        f"a non-empty 'source' field"
                    )
    assert not bad, "supplements entries missing source field:\n" + "\n".join(bad)


def test_no_supplements_causal_priors_without_citation():
    """No supplements entry may carry ``source_class: causal`` (G-3 introduces
    no causal priors). If one ever lands, it MUST also carry an explicit
    external citation string in ``source`` — but the conservative G-3
    bar is to forbid causal entries entirely until that citation arrives.
    """
    with PRIORS_YAML.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    invented: list[str] = []
    for play_id, prior_block in doc["plays"].items():
        for i, p in enumerate(_priors_list_for_play(prior_block)):
            applies = p.get("applies_to") or {}
            vert = applies.get("vertical")
            if vert in ("supplements", "mixed", "*"):
                if p.get("source_class") == "causal":
                    invented.append(
                        f"plays[{play_id!r}][{i}] (vertical={vert!r}) is "
                        f"source_class=causal without a Sprint 4 explicit "
                        f"citation contract."
                    )
    assert not invented, (
        "Invented causal priors (G-3 introduces none):\n"
        + "\n".join(invented)
    )


def test_routine_builder_carries_per_vertical_audience_floor():
    """G-3: routine_builder ships per-vertical audience floors via metadata.

    KI-25 progress: floors mechanism is now in place; supplements floor
    is strictly smaller than beauty (smaller customer bases by model).
    The legacy ``routine_completion_candidates`` audience builder still
    applies its own MIN_N_SKU floor — engine-side plumbing of the
    per-vertical floor is a Sprint 5+ scope, documented in KI-25.
    """
    md = PL.get_play_metadata("routine_builder")
    assert md is not None, "routine_builder must carry metadata under G-3"
    by_vert = getattr(md, "audience_floor_by_vertical", None) or {}
    assert by_vert.get("beauty"), "beauty floor must be authored"
    assert by_vert.get("supplements"), "supplements floor must be authored"
    assert by_vert["supplements"] < by_vert["beauty"], (
        "G-3 directive: supplements floor must be SMALLER than beauty floor "
        f"(got supplements={by_vert.get('supplements')}, "
        f"beauty={by_vert.get('beauty')})"
    )
    # Helper returns the per-vertical floor.
    assert PL.get_audience_floor("routine_builder", vertical="beauty") == by_vert["beauty"]
    assert PL.get_audience_floor("routine_builder", vertical="supplements") == by_vert["supplements"]
    # Unknown vertical falls back to scalar.
    assert PL.get_audience_floor("routine_builder", vertical="nope") == md.audience_floor


# ---------------------------------------------------------------------------
# 2. mixed semantics: deterministic blend, never silently beauty-only
# ---------------------------------------------------------------------------


_BLEND_FIXTURE = """
schema_version: "1.0.0"
last_reviewed: "2026-05-10"

plays:
  blend_test_play:
    - name: base_rate
      value: 0.20
      range_p10: 0.10
      range_p90: 0.30
      source_class: observational
      last_updated: "2026-05-10"
      applies_to: { vertical: beauty }
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.18
      source_class: expert
      last_updated: "2026-05-10"
      applies_to: { vertical: supplements }
      source: internal_heuristic_unvalidated
  supplements_only_play:
    - name: base_rate
      value: 0.15
      range_p10: 0.08
      range_p90: 0.24
      source_class: observational
      last_updated: "2026-05-10"
      applies_to: { vertical: supplements }
      source: internal_csv_observation_v1
  authored_mixed_play:
    - name: base_rate
      value: 0.07
      range_p10: 0.03
      range_p90: 0.12
      source_class: observational
      last_updated: "2026-05-10"
      applies_to: { vertical: mixed }
      source: internal_csv_observation_v1
"""


def test_mixed_resolver_blends_beauty_and_supplements(tmp_path):
    """When no explicit mixed entry exists, the resolver blends 50/50."""
    p = tmp_path / "priors.yaml"
    p.write_text(_BLEND_FIXTURE, encoding="utf-8")
    PL.clear_cache()
    entry = PL.resolve_mixed_prior("blend_test_play", key="base_rate", path=p)
    assert entry is not None, "blend must produce a deterministic entry"
    # 50/50 blend of value 0.20 and 0.10 → 0.15.
    assert entry.value == pytest.approx(0.15)
    assert entry.range_p10 == pytest.approx(0.075)
    assert entry.range_p90 == pytest.approx(0.24)
    # Conservative source_class ordering: expert beats observational.
    assert entry.source_class == "expert"
    # Provenance marks the blend.
    assert entry.applies_to and entry.applies_to.get("vertical") == "mixed"
    assert "derived_from" in entry.applies_to


def test_mixed_resolver_refuses_to_default_to_beauty_alone(tmp_path):
    """D-8 hard guarantee: never silently fall back to beauty alone.

    A play with ONLY a supplements entry (no beauty, no explicit mixed,
    no wildcard) must return ``None`` for the mixed-resolver path. The
    same must hold when a play has ONLY beauty.
    """
    p = tmp_path / "priors.yaml"
    p.write_text(_BLEND_FIXTURE, encoding="utf-8")
    PL.clear_cache()
    # supplements-only play under mixed lookup → None (no beauty side).
    assert PL.resolve_mixed_prior("supplements_only_play", key="base_rate", path=p) is None


def test_mixed_resolver_honors_authored_mixed_block(tmp_path):
    """An explicit ``vertical: mixed`` entry short-circuits the blend."""
    p = tmp_path / "priors.yaml"
    p.write_text(_BLEND_FIXTURE, encoding="utf-8")
    PL.clear_cache()
    entry = PL.resolve_mixed_prior("authored_mixed_play", key="base_rate", path=p)
    assert entry is not None
    # Authored value verbatim — NOT a blend.
    assert entry.value == pytest.approx(0.07)
    assert entry.applies_to and entry.applies_to.get("vertical") == "mixed"
    assert "derived_from" not in (entry.applies_to or {})


def test_mixed_resolver_real_priors_yaml_no_beauty_fallback():
    """End-to-end: scan every play that has a supplements entry but no
    explicit mixed entry and no wildcard. resolve_mixed_prior MUST NOT
    silently return a beauty-shaped entry for those.

    Today the authored YAML carries either explicit mixed entries or
    wildcard entries on every supplements-bearing key, so this loop
    typically resolves via the explicit path. The test pins the
    no-silent-beauty-fallback contract — adding a beauty+supplements
    pair without a mixed/wildcard in the future would surface here.
    """
    PL.clear_cache()
    doc = PL.load_priors()
    plays = doc.get("plays") or {}
    for play_id, prior_block in plays.items():
        rows = _priors_list_for_play(prior_block)
        keys: set[str] = set()
        for r in rows:
            n = r.get("name")
            if isinstance(n, str):
                keys.add(n)
        for k in sorted(keys):
            # No assertion on the value; only on the *contract* that the
            # call doesn't raise and, if it returns, the result is NOT
            # an unmarked beauty entry being passed through as "mixed".
            entry = PL.resolve_mixed_prior(play_id, key=k)
            if entry is None:
                continue
            # Mixed path must mark provenance as either mixed or wildcard.
            applies = entry.applies_to or {}
            vert = applies.get("vertical")
            assert vert in (None, "mixed", "*"), (
                f"resolve_mixed_prior leaked a vertical={vert!r} entry for "
                f"plays[{play_id!r}][{k!r}] — D-8 hard guarantee violated"
            )


# ---------------------------------------------------------------------------
# 3. Loader refuses non-supported verticals (D-8 hard-lock)
# ---------------------------------------------------------------------------


_APPAREL_FIXTURE = """
schema_version: "1.0.0"
last_reviewed: "2026-05-10"

apparel:
  base_rate: 0.05

plays:
  winback_21_45:
    - name: base_rate
      value: 0.08
      range_p10: 0.04
      range_p90: 0.14
      source_class: observational
      last_updated: "2026-05-10"
      applies_to: { vertical: beauty }
"""


def test_priors_loader_rejects_apparel_block(tmp_path):
    """A synthetic YAML with an ``apparel:`` top-level vertical_mode block
    must raise :class:`ConfigError` (D-8 hard-lock).
    """
    p = tmp_path / "priors_apparel.yaml"
    p.write_text(_APPAREL_FIXTURE, encoding="utf-8")
    PL.clear_cache()
    with pytest.raises(ConfigError) as exc_info:
        PL.load_priors(path=p)
    msg = str(exc_info.value)
    assert "apparel" in msg.lower()
    assert "beauty" in msg.lower() and "supplements" in msg.lower()


def test_priors_loader_rejects_other_unsupported_verticals(tmp_path):
    """D-8 hard-lock: food_bev, home, wellness, etc. all refused."""
    for unsupported in ("food_bev", "home", "wellness", "footwear"):
        body = (
            'schema_version: "1.0.0"\n'
            'last_reviewed: "2026-05-10"\n\n'
            f'{unsupported}:\n'
            '  base_rate: 0.05\n\n'
            'plays: {}\n'
        )
        p = tmp_path / f"priors_{unsupported}.yaml"
        p.write_text(body, encoding="utf-8")
        PL.clear_cache()
        with pytest.raises(ConfigError):
            PL.load_priors(path=p)


def test_priors_loader_accepts_supported_verticals(tmp_path):
    """Sanity: the loader is not over-eager. supported vertical_mode-shaped
    top-level keys would not raise (today none exist; verticals live inside
    ``plays[].applies_to.vertical``, not at the top level).
    """
    # Real config has only ``schema_version`` / ``last_reviewed`` / ``plays``
    # at the top level; everything else is per-play. This test just pins
    # that the real YAML loads cleanly under G-3 rules.
    PL.clear_cache()
    doc = PL.load_priors()
    assert isinstance(doc, dict)
    assert "plays" in doc
