"""Sprint 7.5 Ticket T2 — External benchmark memos + validated_external promotions.

For every prior entry in ``config/priors.yaml`` whose
``validation_status`` is ``validated_external`` (or ``validated_internal``,
when T2 backfill produces any):

  - the ``source_artifact`` field is non-null and points to a file
    under ``config/priors_sources/``;
  - the file exists on disk;
  - the file contains at least one URL line (basic shape check — every
    memo MUST cite a public source).

Additionally, the T2 invariant from Part III-1 Step 4 is pinned: no
incrementality / *_lift / churn_reduction style prior may be
``validated_external`` until a causal source is cited (and none has
been cited as of T2 close).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

yaml = pytest.importorskip("yaml")

PRIORS_YAML_PATH = REPO_ROOT / "config" / "priors.yaml"


# Prior names that observational external benchmarks CANNOT validate
# (Part III-1 Step 4 critical distinction). Any of these promoted to
# validated_external would be an invalid causal-from-observational
# inference.
LIFT_LIKE_PRIOR_NAMES = frozenset(
    {
        "incrementality",
        "frequency_lift",
        "second_purchase_lift",
        "subscription_multiplier",
        "churn_reduction",
        "conversion_improvement",
        "expansion_rate",
        "growth_acceleration",
    }
)

VALIDATED_STATUSES = frozenset({"validated_external", "validated_internal"})


def _iter_raw_priors():
    """Yield ``(play_id, prior_index, raw_dict)`` for every prior entry."""

    doc = yaml.safe_load(PRIORS_YAML_PATH.read_text())
    plays = doc.get("plays") or {}
    for play_id, block in plays.items():
        if isinstance(block, list):
            prior_list = block
        elif isinstance(block, dict):
            prior_list = block.get("priors") or []
        else:
            continue
        for i, raw in enumerate(prior_list):
            if isinstance(raw, dict):
                yield play_id, i, raw


def _validated_entries():
    return [
        (play_id, idx, raw)
        for play_id, idx, raw in _iter_raw_priors()
        if raw.get("validation_status") in VALIDATED_STATUSES
    ]


def test_t2_minimum_three_priors_promoted_to_validated_external():
    """Orchestrator-prescribed minimum: ≥3 entries promoted in T2 pass."""

    entries = [
        (p, i, r)
        for p, i, r in _iter_raw_priors()
        if r.get("validation_status") == "validated_external"
    ]
    assert len(entries) >= 3, (
        f"only {len(entries)} validated_external entries; T2 minimum is 3"
    )


def test_every_validated_entry_has_source_artifact_path():
    """No validated_* entry may exist without a source_artifact pointer."""

    missing: list[tuple[str, int, str]] = []
    for play_id, idx, raw in _validated_entries():
        sa = raw.get("source_artifact")
        if not isinstance(sa, str) or not sa.strip():
            missing.append((play_id, idx, raw.get("name", "?")))

    assert not missing, (
        f"{len(missing)} validated_* entries missing source_artifact: " + repr(missing)
    )


def test_every_source_artifact_file_exists_and_cites_a_url():
    """Each source_artifact file must exist relative to repo root AND
    contain at least one URL-shaped line (``https://`` or ``http://``)."""

    failures: list[str] = []
    seen = 0
    for play_id, idx, raw in _validated_entries():
        sa = raw.get("source_artifact")
        if not isinstance(sa, str):
            continue
        seen += 1
        path = REPO_ROOT / sa
        if not path.exists():
            failures.append(f"{play_id}[{idx}]: file missing at {sa}")
            continue
        text = path.read_text()
        if "https://" not in text and "http://" not in text:
            failures.append(f"{play_id}[{idx}]: memo at {sa} has no URL line")

    assert seen >= 3, f"expected >=3 validated entries to check, saw {seen}"
    assert not failures, "T2 memo shape failures:\n" + "\n".join(failures)


def test_no_lift_like_prior_is_validated_external():
    """Part III-1 Step 4 invariant: observational external benchmarks
    cannot validate causal lift claims. Any lift-like prior name with
    validation_status in the validated_* set is a violation."""

    violations = []
    for play_id, idx, raw in _validated_entries():
        name = raw.get("name")
        if name in LIFT_LIKE_PRIOR_NAMES:
            violations.append((play_id, idx, name, raw.get("validation_status")))

    assert not violations, (
        "lift-like priors must not be validated_* without a causal source: "
        + repr(violations)
    )


def test_priors_sources_readme_exists():
    """The README documenting memo shape must exist so future agents
    have a contract to follow."""

    readme = REPO_ROOT / "config" / "priors_sources" / "README.md"
    assert readme.exists()
    assert "validated_external" in readme.read_text()
