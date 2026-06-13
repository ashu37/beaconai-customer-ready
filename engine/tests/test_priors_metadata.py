"""Phase 6A Ticket A3 — priors metadata schema + loader tests.

Pins:

- ``bestseller_amplify`` and ``discount_hygiene`` load with a typed
  :class:`PlayMetadata` containing the five required fields.
- All other plays in ``config/priors.yaml`` continue to load via
  ``load_priors`` and ``list_priors_for_play`` without raising.
- ``get_play_metadata("<play with no metadata>")`` returns ``None``.
- Invalid scalar / enum values inside a ``metadata:`` block raise a
  clear, named error at load time.
- The ``WouldBeMeasuredBy`` enum from :mod:`src.engine_run` (Phase 6A
  Ticket A2) is reused on the metadata side; ``AudienceArchetype`` is
  the loader-side companion enum locked by the campaign-slate contract.

This ticket is **config + loader only**. No runtime engine behavior
changes. Goldens must pass without re-baseline.
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
from src.engine_run import WouldBeMeasuredBy


@pytest.fixture(autouse=True)
def _reset_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_audience_archetype_enum_is_importable():
    from src.priors_loader import AudienceArchetype

    assert issubclass(AudienceArchetype, str)
    # The two values referenced by the first-ship YAML must exist.
    assert AudienceArchetype("hero_sku_buyer") is AudienceArchetype.HERO_SKU_BUYER
    assert AudienceArchetype("discount_buyer") is AudienceArchetype.DISCOUNT_BUYER


def test_play_metadata_dataclass_is_importable():
    import dataclasses

    from src.priors_loader import PlayMetadata

    # Loader uses frozen dataclasses; mirror the existing PriorEntry shape.
    assert dataclasses.is_dataclass(PlayMetadata)
    field_names = {f.name for f in dataclasses.fields(PlayMetadata)}
    assert "audience_floor" in field_names
    assert "mechanism" in field_names
    assert "vertical_applicability" in field_names
    assert "would_be_measured_by" in field_names
    assert "audience_archetype" in field_names


def test_get_play_metadata_is_importable():
    assert callable(PL.get_play_metadata)


# ---------------------------------------------------------------------------
# Real config: the two first-ship-eligible plays load
# ---------------------------------------------------------------------------


def test_bestseller_amplify_metadata_loaded_and_typed():
    from src.priors_loader import AudienceArchetype, PlayMetadata

    md = PL.get_play_metadata("bestseller_amplify")
    assert md is not None
    assert isinstance(md, PlayMetadata)
    assert md.audience_floor == 500
    assert isinstance(md.mechanism, str)
    assert md.mechanism.strip() != ""
    assert "beauty" in md.vertical_applicability
    assert "mixed" in md.vertical_applicability
    assert md.would_be_measured_by == WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D
    assert md.audience_archetype == AudienceArchetype.HERO_SKU_BUYER


def test_discount_hygiene_metadata_loaded_and_typed():
    from src.priors_loader import AudienceArchetype, PlayMetadata

    md = PL.get_play_metadata("discount_hygiene")
    assert md is not None
    assert isinstance(md, PlayMetadata)
    assert md.audience_floor == 200
    assert isinstance(md.mechanism, str)
    assert md.mechanism.strip() != ""
    assert "beauty" in md.vertical_applicability
    assert "supplements" in md.vertical_applicability
    assert "mixed" in md.vertical_applicability
    assert md.would_be_measured_by == WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D
    assert md.audience_archetype == AudienceArchetype.DISCOUNT_BUYER


def test_first_to_second_purchase_metadata_loaded_and_typed():
    """Phase 6B Ticket C1.5: ``first_to_second_purchase`` opted into the
    dict form (``metadata`` + ``priors``) so the V2 renderer's C1
    "What we'd send:" line surfaces a merchant-readable mechanism on the
    Beauty Brand Recommended Now card. Pin the typed shape parallel to
    the discount_hygiene / bestseller_amplify pins above.
    """
    from src.priors_loader import AudienceArchetype, PlayMetadata

    md = PL.get_play_metadata("first_to_second_purchase")
    assert md is not None
    assert isinstance(md, PlayMetadata)
    assert md.audience_floor == 500
    assert isinstance(md.mechanism, str)
    assert md.mechanism.strip() != ""
    # Mechanism content discipline: 15-35 words, no offer specifics, no
    # causal claims, no projected-lift / forecast / confidence language.
    word_count = len(md.mechanism.split())
    assert 15 <= word_count <= 35, (
        f"first_to_second_purchase mechanism word count {word_count} out "
        f"of bounds [15, 35]; got {md.mechanism!r}"
    )
    assert "beauty" in md.vertical_applicability
    assert "supplements" in md.vertical_applicability
    assert "mixed" in md.vertical_applicability
    assert md.would_be_measured_by == WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D
    assert md.audience_archetype == AudienceArchetype.FIRST_TIME_BUYER


# ---------------------------------------------------------------------------
# All other plays continue to load
# ---------------------------------------------------------------------------


def test_existing_plays_still_load_via_load_priors():
    """The full document parses; the ``plays`` mapping is intact."""
    doc = PL.load_priors()
    assert isinstance(doc, dict)
    plays = doc.get("plays")
    assert isinstance(plays, dict)
    expected_legacy = {
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
        "first_to_second_purchase",
        "at_risk_repeat_buyer_rescue",
        "onsite_funnel_watch",
    }
    missing = expected_legacy - set(plays.keys())
    assert not missing, f"plays mapping missing: {sorted(missing)}"


def test_get_prior_still_resolves_for_metadata_carrying_play():
    """``bestseller_amplify`` priors must still resolve via ``get_prior``."""
    e = PL.get_prior("bestseller_amplify", vertical="beauty", key="base_rate")
    assert e is not None
    assert e.name == "base_rate"
    assert e.value == 0.18


def test_get_prior_still_resolves_for_discount_hygiene():
    e = PL.get_prior("discount_hygiene", vertical="beauty", key="margin_recovery_rate")
    assert e is not None
    assert e.name == "margin_recovery_rate"


def test_list_priors_for_play_still_returns_priors_for_metadata_play():
    rows = PL.list_priors_for_play("bestseller_amplify")
    assert isinstance(rows, list)
    assert len(rows) > 0
    names = {r.get("name") for r in rows}
    assert "base_rate" in names
    assert "incrementality" in names


def test_get_prior_still_resolves_for_legacy_list_form_plays():
    """Plays NOT carrying metadata stay in their original list form."""
    e = PL.get_prior("winback_21_45", vertical="beauty", key="base_rate")
    assert e is not None
    assert e.name == "base_rate"


# ---------------------------------------------------------------------------
# Plays without metadata return None (no raise)
# ---------------------------------------------------------------------------


def test_play_without_metadata_returns_none():
    """Plays without a ``metadata:`` block must not raise; just return None.

    Sprint 4 Ticket G-3 (2026-05-10) promoted ``routine_builder`` to the
    A3 dict form so it could carry per-vertical audience floors; it now
    DOES return a :class:`PlayMetadata`. The remaining plays in this
    assert keep the legacy list form.
    """
    assert PL.get_play_metadata("winback_21_45") is None
    assert PL.get_play_metadata("subscription_nudge") is None
    assert PL.get_play_metadata("frequency_accelerator") is None


def test_unknown_play_returns_none():
    assert PL.get_play_metadata("nonexistent_play_id") is None


# ---------------------------------------------------------------------------
# Validation: invalid metadata blocks raise
# ---------------------------------------------------------------------------


def _write_yaml(p: Path, body: str) -> None:
    p.write_text(body, encoding="utf-8")


_VALID_PRIORS_BODY = """
    priors:
      - name: base_rate
        value: 0.10
        range_p10: 0.05
        range_p90: 0.20
        source_class: expert
        last_updated: "2026-05-04"
        applies_to: { vertical: "*" }
"""


def test_invalid_would_be_measured_by_raises(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, f"""
schema_version: "1.0.0"
last_reviewed: "2026-05-04"
plays:
  test_play:
    metadata:
      audience_floor: 100
      mechanism: "Test mechanism."
      vertical_applicability: [beauty]
      would_be_measured_by: NOT_A_REAL_OUTCOME_METRIC
      audience_archetype: discount_buyer
{_VALID_PRIORS_BODY}
""")
    PL.clear_cache()
    with pytest.raises((ValueError, PL.PriorsMetadataError)):
        PL.get_play_metadata("test_play", path=p)


def test_invalid_audience_archetype_raises(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, f"""
schema_version: "1.0.0"
last_reviewed: "2026-05-04"
plays:
  test_play:
    metadata:
      audience_floor: 100
      mechanism: "Test mechanism."
      vertical_applicability: [beauty]
      would_be_measured_by: REPEAT_PURCHASE_IN_30D
      audience_archetype: not_a_real_archetype
{_VALID_PRIORS_BODY}
""")
    PL.clear_cache()
    with pytest.raises((ValueError, PL.PriorsMetadataError)):
        PL.get_play_metadata("test_play", path=p)


def test_zero_audience_floor_raises(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, f"""
schema_version: "1.0.0"
last_reviewed: "2026-05-04"
plays:
  test_play:
    metadata:
      audience_floor: 0
      mechanism: "Test mechanism."
      vertical_applicability: [beauty]
      would_be_measured_by: REPEAT_PURCHASE_IN_30D
      audience_archetype: discount_buyer
{_VALID_PRIORS_BODY}
""")
    PL.clear_cache()
    with pytest.raises((ValueError, PL.PriorsMetadataError)):
        PL.get_play_metadata("test_play", path=p)


def test_negative_audience_floor_raises(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, f"""
schema_version: "1.0.0"
last_reviewed: "2026-05-04"
plays:
  test_play:
    metadata:
      audience_floor: -1
      mechanism: "Test mechanism."
      vertical_applicability: [beauty]
      would_be_measured_by: REPEAT_PURCHASE_IN_30D
      audience_archetype: discount_buyer
{_VALID_PRIORS_BODY}
""")
    PL.clear_cache()
    with pytest.raises((ValueError, PL.PriorsMetadataError)):
        PL.get_play_metadata("test_play", path=p)


# S7 priors-wiring Q5 (2026-05-20): pin the ``Optional[int]`` relaxation.
# ``audience_floor: null`` must round-trip clean (loads as ``None``, no error);
# ``0`` and negatives must still raise. The latter two are already pinned by
# the two tests immediately above — this case adds the null round-trip leg
# so the three-way contract (null OK, 0 raises, negative raises) is explicit
# in one neighborhood of the test file.
def test_null_audience_floor_round_trips(tmp_path):
    """``audience_floor: null`` loads as ``None`` without raising."""
    p = tmp_path / "priors.yaml"
    _write_yaml(p, f"""
schema_version: "1.0.0"
last_reviewed: "2026-05-04"
plays:
  test_play:
    metadata:
      audience_floor: null
      mechanism: "Test mechanism."
      vertical_applicability: [beauty]
      would_be_measured_by: REPEAT_PURCHASE_IN_30D
      audience_archetype: discount_buyer
{_VALID_PRIORS_BODY}
""")
    PL.clear_cache()
    md = PL.get_play_metadata("test_play", path=p)
    assert md is not None
    assert md.audience_floor is None


def test_missing_required_key_raises(tmp_path):
    """Missing ``audience_floor`` (a required field) must raise."""
    p = tmp_path / "priors.yaml"
    _write_yaml(p, f"""
schema_version: "1.0.0"
last_reviewed: "2026-05-04"
plays:
  test_play:
    metadata:
      mechanism: "Test mechanism."
      vertical_applicability: [beauty]
      would_be_measured_by: REPEAT_PURCHASE_IN_30D
      audience_archetype: discount_buyer
{_VALID_PRIORS_BODY}
""")
    PL.clear_cache()
    with pytest.raises((KeyError, ValueError, PL.PriorsMetadataError)):
        PL.get_play_metadata("test_play", path=p)


def test_missing_mechanism_raises(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, f"""
schema_version: "1.0.0"
last_reviewed: "2026-05-04"
plays:
  test_play:
    metadata:
      audience_floor: 100
      vertical_applicability: [beauty]
      would_be_measured_by: REPEAT_PURCHASE_IN_30D
      audience_archetype: discount_buyer
{_VALID_PRIORS_BODY}
""")
    PL.clear_cache()
    with pytest.raises((KeyError, ValueError, PL.PriorsMetadataError)):
        PL.get_play_metadata("test_play", path=p)


def test_empty_mechanism_raises(tmp_path):
    p = tmp_path / "priors.yaml"
    _write_yaml(p, f"""
schema_version: "1.0.0"
last_reviewed: "2026-05-04"
plays:
  test_play:
    metadata:
      audience_floor: 100
      mechanism: ""
      vertical_applicability: [beauty]
      would_be_measured_by: REPEAT_PURCHASE_IN_30D
      audience_archetype: discount_buyer
{_VALID_PRIORS_BODY}
""")
    PL.clear_cache()
    with pytest.raises((ValueError, PL.PriorsMetadataError)):
        PL.get_play_metadata("test_play", path=p)


# ---------------------------------------------------------------------------
# Negative control: a fixture YAML that mirrors the real schema works
# ---------------------------------------------------------------------------


def test_synthetic_valid_metadata_loads(tmp_path):
    from src.priors_loader import AudienceArchetype, PlayMetadata

    p = tmp_path / "priors.yaml"
    _write_yaml(p, f"""
schema_version: "1.0.0"
last_reviewed: "2026-05-04"
plays:
  test_play:
    metadata:
      audience_floor: 250
      mechanism: "Send a coupon and watch redemption."
      vertical_applicability: [beauty, mixed]
      would_be_measured_by: EMAIL_ATTRIBUTED_REVENUE_IN_7D
      audience_archetype: discount_buyer
{_VALID_PRIORS_BODY}
""")
    PL.clear_cache()
    md = PL.get_play_metadata("test_play", path=p)
    assert isinstance(md, PlayMetadata)
    assert md.audience_floor == 250
    assert md.mechanism == "Send a coupon and watch redemption."
    assert md.vertical_applicability == ["beauty", "mixed"]
    assert md.would_be_measured_by == WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D
    assert md.audience_archetype == AudienceArchetype.DISCOUNT_BUYER


def test_synthetic_play_with_no_metadata_block_returns_none(tmp_path):
    """Legacy-style list-only play continues to load and returns None metadata."""
    p = tmp_path / "priors.yaml"
    _write_yaml(p, """
schema_version: "1.0.0"
last_reviewed: "2026-05-04"
plays:
  legacy_play:
    - name: base_rate
      value: 0.10
      range_p10: 0.05
      range_p90: 0.20
      source_class: expert
      last_updated: "2026-05-04"
      applies_to: { vertical: "*" }
""")
    PL.clear_cache()
    assert PL.get_play_metadata("legacy_play", path=p) is None
    # And get_prior still resolves on the legacy-list-form play.
    e = PL.get_prior("legacy_play", vertical="beauty", key="base_rate", path=p)
    assert e is not None
    assert e.value == 0.10
