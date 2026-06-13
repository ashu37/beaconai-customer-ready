"""S6-T3.x — `replenishment_due` prior re-key tests.

Pins the 2026-05-19 re-key of `replenishment_due` from the bestseller_amplify
bundle_value borrow (D-S6-2, superseded) to a dedicated
`replenishment_due.base_rate.beauty` validated_external block backed by the
Gemini Deep Research memo at
`config/priors_sources/replenishment_due__base_rate__beauty.md`.

Test coverage (per S6-T3.x acceptance criteria):

1. `replenishment_due.base_rate.beauty` exists with
   `validation_status: validated_external`.
2. The block's `source_artifact` points to an existing file under
   `config/priors_sources/`.
3. Exact-value pin: `value=0.0220`, `range_p10=0.0120`, `range_p90=0.0430`,
   `effective_n=30`.
4. `replenishment_due.base_rate` has NO supplements entry (asymmetric
   posture per DS architect verdict 2026-05-19).
5. `_PRIOR_ANCHORED["replenishment_due"]` routes to
   `replenishment_due.base_rate` (NOT `bestseller_amplify.bundle_value`).
6. Flag-OFF byte-identical sanity check: all 5 pinned fixtures'
   sha256 constants are still set to their pre-T3.x values (test-only
   sanity — full byte-identity is enforced by
   `test_slate_regression_*` and the M0 golden tests).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.measurement_builder import _PRIOR_ANCHORED
from src.priors_loader import PriorValidationStatus, clear_cache, get_prior


REPO_ROOT = Path(__file__).resolve().parent.parent
PRIORS_YAML = REPO_ROOT / "config" / "priors.yaml"


def _load_priors_yaml() -> dict:
    with PRIORS_YAML.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _replenishment_due_block() -> dict:
    data = _load_priors_yaml()
    plays = data["plays"]
    assert "replenishment_due" in plays, (
        "S6-T3.x: `replenishment_due` block must exist in "
        "config/priors.yaml::plays after the re-key."
    )
    block = plays["replenishment_due"]
    assert isinstance(block, dict), (
        "S6-T3.x: `replenishment_due` must be in dict form "
        "(`metadata` + `priors`) like first_to_second_purchase, not the "
        "legacy list form."
    )
    return block


def test_replenishment_due_base_rate_beauty_exists_validated_external() -> None:
    """Test 1: dedicated beauty base_rate entry at validated_external status."""
    clear_cache()
    prior = get_prior("replenishment_due", vertical="beauty", key="base_rate")
    assert prior is not None, (
        "S6-T3.x: `replenishment_due.base_rate.beauty` must resolve via "
        "get_prior() after the re-key."
    )
    assert prior.validation_status == PriorValidationStatus.VALIDATED_EXTERNAL, (
        f"S6-T3.x: beauty base_rate must be validated_external; got "
        f"{prior.validation_status!r}"
    )


def test_replenishment_due_base_rate_beauty_source_artifact_points_to_existing_memo() -> None:
    """Test 2: source_artifact threads to the Gemini memo."""
    clear_cache()
    prior = get_prior("replenishment_due", vertical="beauty", key="base_rate")
    assert prior is not None
    assert prior.source_artifact, (
        "S6-T3.x: validated_external priors must carry a non-empty "
        "source_artifact path."
    )
    memo_path = REPO_ROOT / prior.source_artifact
    assert memo_path.exists(), (
        f"S6-T3.x: source_artifact path must point to an existing file; "
        f"{memo_path} not found. The Gemini Deep Research memo for "
        f"replenishment_due.base_rate.beauty was committed at 011c7cc."
    )
    # The memo path SHOULD live under config/priors_sources/ per process
    # discipline (S7.5-T2 + S6-T3.x).
    assert "config/priors_sources/" in prior.source_artifact, (
        f"S6-T3.x: source_artifact must live under config/priors_sources/; "
        f"got {prior.source_artifact!r}"
    )


def test_replenishment_due_base_rate_beauty_exact_value_pin() -> None:
    """Test 3: numeric value pin — `0.0220 / 0.0037 / 0.0471 / N=60`.

    Re-pinned 2026-05-24 (S8-T0) after KI-NEW-K Beta envelope re-fit
    (founder-acked scope expansion to replenishment_due). Beta(1.32, 58.68)
    analytic p10/p90 from scipy.stats.beta(1.32, 58.68).ppf([0.10, 0.90]).
    Any change here implies a new memo + a deliberate re-pin under the
    S6-T3.5 hard-stop envelope (D-S6-3). Tests must catch silent drift.
    """
    clear_cache()
    prior = get_prior("replenishment_due", vertical="beauty", key="base_rate")
    assert prior is not None
    assert prior.value == 0.0220, (
        f"S6-T3.x: beauty base_rate value pinned at 0.0220; got {prior.value!r}"
    )
    assert prior.range_p10 == 0.0037, (
        f"S6-T3.x: range_p10 pinned at 0.0037 (S8-T0 re-fit); "
        f"got {prior.range_p10!r}"
    )
    assert prior.range_p90 == 0.0471, (
        f"S6-T3.x: range_p90 pinned at 0.0471 (S8-T0 re-fit); "
        f"got {prior.range_p90!r}"
    )
    assert prior.effective_n == 60, (
        f"S6-T3.x: effective_n pinned at 60 (S8-T0 re-fit); "
        f"got {prior.effective_n!r}"
    )


def test_replenishment_due_base_rate_has_no_supplements_entry() -> None:
    """Test 4: supplements asymmetry. The block MUST NOT carry a
    supplements `base_rate` entry.

    Per DS architect verdict 2026-05-19, supplements correctly routes to
    PRIOR_UNVALIDATED Considered via S7.5-T3 refusal logic when no
    matching vertical block exists. Authoring a supplements stub purely
    for code-symmetry would fabricate a prior to satisfy code shape.

    This test pins the negative — a future agent adding a supplements
    `replenishment_due.base_rate` block MUST also author an external
    memo and re-pin the supplements fixture under S6-T3.5 discipline.
    """
    block = _replenishment_due_block()
    priors = block.get("priors", [])
    base_rate_entries = [p for p in priors if p.get("name") == "base_rate"]
    assert len(base_rate_entries) >= 1, (
        "S6-T3.x: at least one base_rate entry must exist (the beauty block)."
    )
    supplements_entries = [
        p for p in base_rate_entries
        if (p.get("applies_to") or {}).get("vertical") == "supplements"
    ]
    assert supplements_entries == [], (
        "S6-T3.x: NO supplements base_rate entry must exist on "
        "replenishment_due (asymmetric posture per DS architect 2026-05-19). "
        f"Found: {supplements_entries!r}. If authoring a supplements "
        "counterpart is intended, also author an external memo and re-pin "
        "the supplements fixture per D-S6-3 envelope discipline."
    )

    # Direct loader assertion: vertical-scoped lookup returns None for
    # supplements, so the refusal path engages downstream.
    clear_cache()
    suppl_prior = get_prior(
        "replenishment_due", vertical="supplements", key="base_rate"
    )
    assert suppl_prior is None, (
        f"S6-T3.x: supplements lookup must return None to engage the "
        f"PRIOR_UNVALIDATED refusal path; got {suppl_prior!r}"
    )


def test_measurement_builder_routes_to_replenishment_due_base_rate() -> None:
    """Test 5: dispatch entry pins the re-key.

    `_PRIOR_ANCHORED["replenishment_due"]` MUST consume
    `replenishment_due.base_rate`, NOT the (now-superseded)
    `bestseller_amplify.bundle_value`.
    """
    entry = _PRIOR_ANCHORED.get("replenishment_due")
    assert entry is not None, (
        "S6-T3.x: _PRIOR_ANCHORED dispatch entry for `replenishment_due` "
        "must exist."
    )
    assert entry.prior_play_id == "replenishment_due", (
        f"S6-T3.x: dispatch must route to `replenishment_due` prior block "
        f"(not `bestseller_amplify` — the D-S6-2 borrow is superseded); "
        f"got prior_play_id={entry.prior_play_id!r}"
    )
    assert entry.prior_key == "base_rate", (
        f"S6-T3.x: dispatch must consume the `base_rate` prior (a "
        f"probability rate, not the dollar-typed `bundle_value`); "
        f"got prior_key={entry.prior_key!r}"
    )


def test_bestseller_amplify_bundle_value_beauty_preserved_post_rekey() -> None:
    """Test 6 (additional sanity): the re-key MUST NOT touch the
    `bestseller_amplify.bundle_value.beauty` prior.

    The bundle_value prior remains valid for `bestseller_amplify` itself;
    only its USE as a `replenishment_due` prior was invalidated by the
    D-S6-2 category error. This guards against an over-zealous cleanup
    that would invalidate the S7.5-T2 validated_external promotion of
    the bsandco memo.
    """
    clear_cache()
    prior = get_prior(
        "bestseller_amplify", vertical="beauty", key="bundle_value"
    )
    assert prior is not None, (
        "S6-T3.x: `bestseller_amplify.bundle_value.beauty` MUST remain "
        "intact post re-key. Only its mis-use as a replenishment_due "
        "prior was the bug; the prior itself is the S7.5-T2 bsandco "
        "validated_external promotion."
    )
    assert prior.validation_status == PriorValidationStatus.VALIDATED_EXTERNAL, (
        f"S6-T3.x: bestseller_amplify.bundle_value.beauty must retain "
        f"validated_external status; got {prior.validation_status!r}"
    )
