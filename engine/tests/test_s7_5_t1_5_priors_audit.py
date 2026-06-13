"""Sprint 7.5 Ticket T1.5 — Priors YAML audit pass.

T1 (closed-enum strict loader) defaulted missing ``validation_status``
to ``HEURISTIC_UNVALIDATED`` so every pre-T1 entry would parse
unchanged. T1.5 walks ``config/priors.yaml`` and authors the field
explicitly on every entry so the YAML is the source of truth (no
implicit Python default in production). This test pins that contract:
every prior entry in the live YAML carries an explicit
``validation_status`` string.

Also pins the per-status distribution recorded in the T1.5 summary so
a future drift (e.g., a silent demotion of a validated_external entry
to heuristic_unvalidated) is caught by the structural test.

See ``agent_outputs/implementation-manager-s7_5-priors-validation-plan.md``
S7.5-T1.5 spec.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

yaml = pytest.importorskip("yaml")

from src import priors_loader as PL
from src.priors_loader import PriorValidationStatus


PRIORS_YAML_PATH = REPO_ROOT / "config" / "priors.yaml"


@pytest.fixture(autouse=True)
def _reset_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


def _iter_raw_priors():
    """Yield ``(play_id, prior_index, raw_dict)`` for every prior entry
    in the on-disk YAML, supporting both legacy-list and Phase 6A
    dict-form play blocks."""

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


def test_every_prior_entry_has_authored_validation_status():
    """The T1.5 contract: no implicit defaults left.

    Walks the raw YAML (not the loader, so we catch the case where the
    loader's default would mask a missing YAML field). Every dict
    entry must carry a ``validation_status`` key whose value is one of
    the closed-enum strings.
    """

    valid_strings = {m.value for m in PriorValidationStatus}
    missing: list[tuple[str, int, dict]] = []
    invalid: list[tuple[str, int, str]] = []

    count = 0
    for play_id, idx, raw in _iter_raw_priors():
        count += 1
        if "validation_status" not in raw:
            missing.append((play_id, idx, raw))
            continue
        v = raw["validation_status"]
        if v not in valid_strings:
            invalid.append((play_id, idx, repr(v)))

    assert count > 0, "no prior entries found — fixture broken"
    assert not missing, (
        f"{len(missing)} prior entries missing validation_status: "
        + ", ".join(f"plays[{p}][{i}].name={r.get('name')!r}" for p, i, r in missing[:5])
    )
    assert not invalid, (
        f"{len(invalid)} prior entries carry an unknown validation_status string "
        f"(must be one of {sorted(valid_strings)}): "
        + ", ".join(f"plays[{p}][{i}]={v}" for p, i, v in invalid[:5])
    )


def test_validation_status_distribution_pin():
    """Pin the per-status distribution recorded in the T1.5 summary doc.

    A future drift in either direction is intentional and should
    update this pin (and the summary). The two placeholder entries
    are named explicitly so a typo on the YAML side cannot silently
    swap one for the other.
    """

    from collections import Counter

    counts: Counter[str] = Counter()
    placeholders: list[tuple[str, str]] = []
    for play_id, _, raw in _iter_raw_priors():
        status = raw["validation_status"]
        counts[status] += 1
        if status == "placeholder":
            placeholders.append((play_id, raw.get("name")))

    # Distribution post-T2 (T1.5 baseline was 82 heuristic + 2 placeholder;
    # T2 promoted 3 entries to validated_external).
    # S6-T3.x re-key (2026-05-19): +1 validated_external on
    # ``replenishment_due.base_rate.beauty`` (Klaviyo PERL Cosmetics +
    # H&B 2026 memo); brings total to 4. See D-S6-2.1.
    # S7 priors-wiring (2026-05-20): +2 validated_external
    # (``discount_dependency_hygiene.base_rate.beauty`` Klaviyo H&B 2026
    # memo + ``aov_lift_via_threshold_bundle.base_rate.beauty`` Klaviyo
    # cross-sell memo) and +1 elicited_expert
    # (``aov_lift_via_threshold_bundle.base_rate.supplements``,
    # DS-architect DOWNGRADED from claimed validated_external due to
    # beauty-evidence laundering per D-S6-2 pattern).
    assert counts["heuristic_unvalidated"] == 79, counts
    assert counts["placeholder"] == 2, counts
    assert counts["validated_external"] == 6, counts
    assert counts["validated_internal"] == 0, counts
    assert counts["elicited_expert"] == 1, counts

    assert set(placeholders) == {
        ("first_to_second_purchase", "second_purchase_lift"),
        ("at_risk_repeat_buyer_rescue", "base_rate"),
    }, placeholders


def test_loader_resolves_every_entry_with_an_enum_value():
    """Sanity: the on-disk authored strings load through the closed-enum
    loader without raising. This is partial overlap with T1's tests, but
    pins it specifically against the audited YAML so a typo in T1.5
    surfaces here (not only in the parametrized test above)."""

    doc = PL.load_priors()
    plays = doc.get("plays") or {}
    seen = 0
    for play_id in plays:
        prior_list, _ = PL._extract_play_block(doc, play_id)
        if prior_list is None:
            continue
        for raw in prior_list:
            entry = PL._coerce_entry(play_id, raw)
            if entry is None:
                continue
            assert isinstance(entry.validation_status, PriorValidationStatus)
            seen += 1
    # S6-T3.x re-key (2026-05-19): +1 entry on
    # ``replenishment_due.base_rate.beauty`` (validated_external); brings
    # total to 85. See D-S6-2.1.
    # S7 priors-wiring (2026-05-20): +3 entries
    # (``discount_dependency_hygiene.base_rate.beauty``,
    # ``aov_lift_via_threshold_bundle.base_rate.beauty``,
    # ``aov_lift_via_threshold_bundle.base_rate.supplements``); brings
    # total to 88.
    assert seen == 88, seen
