"""Milestone 2 T2.4: schema validation for ``config/priors.yaml``.

The YAML is config-only in M2 — it is NOT loaded by the engine at runtime.
These tests verify that the file is well-formed, every prior entry has the
required keys, and ``source_class`` is one of the three allowed values.

The test suite explicitly DOES NOT enforce that every play in
``src.play_registry.PLAYS`` has a corresponding entry in ``priors.yaml``:
M2 reserves ``onsite_funnel_watch`` (no priors yet), and we expect M6 to
add a stricter cross-validation pass once the loader is wired.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PRIORS_YAML = REPO_ROOT / "config" / "priors.yaml"


# yaml is already a transitive dep via src/anomaly.py thresholds loader.
yaml = pytest.importorskip("yaml")


ALLOWED_SOURCE_CLASSES = {"observational", "causal", "expert"}
REQUIRED_KEYS = {"name", "value", "range_p10", "range_p90", "source_class", "last_updated", "applies_to"}


def _priors_list_for_play(prior_block):
    """Return the list of prior dicts for a play, regardless of YAML form.

    Two YAML shapes are valid (Phase 6A Ticket A3):

    1. **Legacy list form**: ``plays.<play_id>: [ <prior_dict>, ... ]``.
    2. **Dict form** (opt-in for plays carrying a ``metadata:`` block):
       ``plays.<play_id>: { metadata: {...}, priors: [ <prior_dict>, ... ] }``.

    This helper normalises both into a list of prior dicts so the
    existing schema assertions can keep walking ``prior_list``.
    """

    if isinstance(prior_block, list):
        return prior_block
    if isinstance(prior_block, dict):
        return prior_block.get("priors") or []
    return []


@pytest.fixture(scope="module")
def priors_doc():
    assert PRIORS_YAML.exists(), f"Missing config artifact: {PRIORS_YAML}"
    with PRIORS_YAML.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_top_level_schema_present(priors_doc):
    assert isinstance(priors_doc, dict)
    assert priors_doc.get("schema_version"), "missing schema_version"
    assert priors_doc.get("last_reviewed"), "missing last_reviewed"
    assert isinstance(priors_doc.get("plays"), dict), "missing plays mapping"


def test_every_play_block_is_well_formed(priors_doc):
    """Phase 6A Ticket A3: a play block is either a list of priors (legacy)
    OR a dict ``{metadata: {...}, priors: [...]}`` (new opt-in form)."""
    for play_id, prior_block in priors_doc["plays"].items():
        if isinstance(prior_block, list):
            continue
        assert isinstance(prior_block, dict), (
            f"plays[{play_id!r}] must be a list of prior dicts OR a dict with "
            f"`metadata` + `priors` keys; got {type(prior_block).__name__}"
        )
        # Dict form: priors must be a list (possibly absent for plays whose
        # only purpose is carrying metadata; today both opted-in plays carry
        # priors, so we still assert presence).
        assert isinstance(prior_block.get("priors"), list), (
            f"plays[{play_id!r}] dict form must contain a `priors` list"
        )


def test_every_prior_has_required_keys(priors_doc):
    bad: list[str] = []
    for play_id, prior_block in priors_doc["plays"].items():
        prior_list = _priors_list_for_play(prior_block)
        for i, p in enumerate(prior_list):
            assert isinstance(p, dict), f"plays[{play_id}][{i}] is not a dict"
            missing = REQUIRED_KEYS - set(p.keys())
            if missing:
                bad.append(f"{play_id}[{i}] missing {sorted(missing)}")
    assert not bad, "Priors with missing keys:\n" + "\n".join(bad)


def test_every_prior_has_allowed_source_class(priors_doc):
    bad: list[str] = []
    for play_id, prior_block in priors_doc["plays"].items():
        prior_list = _priors_list_for_play(prior_block)
        for i, p in enumerate(prior_list):
            sc = p.get("source_class")
            if sc not in ALLOWED_SOURCE_CLASSES:
                bad.append(f"{play_id}[{i}].source_class={sc!r}")
    assert not bad, (
        f"Priors with invalid source_class (allowed: {sorted(ALLOWED_SOURCE_CLASSES)}):\n"
        + "\n".join(bad)
    )


def test_value_ranges_are_ordered(priors_doc):
    bad: list[str] = []
    for play_id, prior_block in priors_doc["plays"].items():
        prior_list = _priors_list_for_play(prior_block)
        for i, p in enumerate(prior_list):
            try:
                lo = float(p["range_p10"])
                hi = float(p["range_p90"])
                v = float(p["value"])
            except (TypeError, ValueError):
                bad.append(f"{play_id}[{i}] non-numeric value/range")
                continue
            if not (lo <= hi):
                bad.append(f"{play_id}[{i}] range_p10={lo} > range_p90={hi}")
            # value should not blatantly fall outside the documented range.
            # We allow equality at the bounds.
            if not (lo <= v <= hi):
                bad.append(f"{play_id}[{i}] value={v} outside [range_p10={lo}, range_p90={hi}]")
    assert not bad, "Range/value sanity violations:\n" + "\n".join(bad)


def test_applies_to_is_a_dict(priors_doc):
    for play_id, prior_block in priors_doc["plays"].items():
        prior_list = _priors_list_for_play(prior_block)
        for i, p in enumerate(prior_list):
            applies = p.get("applies_to")
            assert isinstance(applies, dict), (
                f"plays[{play_id}][{i}].applies_to must be a dict; got "
                f"{type(applies).__name__}"
            )
            # "vertical" is the only required scope key today; subvertical /
            # business_stage are optional. The vertical can be a specific
            # vertical name or "*" for all.
            assert "vertical" in applies, f"plays[{play_id}][{i}].applies_to missing 'vertical'"


def test_play_blocks_present_for_every_legacy_play(priors_doc):
    """Defensive: M2 should have priors for every legacy emitter we know of."""
    legacy = {
        "winback_21_45",
        "bestseller_amplify",
        "discount_hygiene",
        "subscription_nudge",
        "routine_builder",
        "empty_bottle",
        "frequency_accelerator",
        "aov_momentum",
        "retention_mastery",
        "journey_optimization",
        "category_expansion",
    }
    missing = legacy - set(priors_doc["plays"].keys())
    assert not missing, f"priors.yaml missing legacy play blocks: {sorted(missing)}"


def test_yaml_not_loaded_at_runtime():
    """M2 invariant: priors.yaml is NOT loaded at runtime yet.

    Look for actual file-loading patterns (``open(...)`` /
    ``yaml.safe_load(...)`` / ``Path(...)``) that reference ``priors.yaml``,
    not just any comment that mentions the filename. M2 lets the registry
    docstring talk about priors.yaml; what M2 forbids is *loading* the
    file from runtime modules. M6 (T6.1) will introduce
    ``src/priors_loader.py`` and flip this assertion.
    """

    import re as _re

    # Match the filename only when it appears next to a load/open token.
    load_pattern = _re.compile(
        r"""(open|safe_load|load|read_text|read_bytes|Path)\([^)]*priors\.yaml""",
    )

    src_root = REPO_ROOT / "src"
    bad_files: list[str] = []
    for py in src_root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        # Allow priors_loader.py to mention/load it (when M6 lands).
        if py.name == "priors_loader.py":
            continue
        if load_pattern.search(text):
            bad_files.append(str(py.relative_to(REPO_ROOT)))
    assert not bad_files, (
        "config/priors.yaml is loaded by runtime modules in M2; M2 scope "
        "is config-only. Affected files:\n  " + "\n  ".join(bad_files)
    )
