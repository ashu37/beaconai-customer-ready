"""S6-T2 — supplements serving-count parser coverage tests.

15 tests per IM plan §S6-T2 (lines 187-194):
 1-10. Per-SKU positive-projection extraction on the 10 unique SKUs in the
       G-1 supplements fixture (tests/fixtures/synthetic/healthy_supplements
       _240d_orders.csv). Positive-projection means: each SKU's expected
       (coherence_key, value) outcome is pinned explicitly. SKUs whose
       names lack a unit-coherent signal (weight-only forms like ``1lb``
       / ``500g``; named blends like ``Pre-Workout Energy Complex``) are
       pinned to ``None`` as the documented, intentional outcome — not a
       silent fall-through. This documents the G-1-fixture coverage rate
       (5/10) and surfaces KI-27's continued ``accepted`` posture (founder
       confirmation required before ``empty_bottle.vertical_applicable``
       expansion).
 11. Day-supply variant (``30-day supply``) parses to ``("day_supply", 30)``.
 12. Serving-count variant (``30 servings``) parses to ``("serving", 30)``.
 13. Capsule-count variant (``120 capsules``) parses to ``("count", 120)``.
 14. Unknown / un-parseable supplement SKU returns ``None`` (no crash).
 15. Beauty SKUs still parse via the existing beauty ``size_regex`` block
     (no cross-contamination between vertical blocks).
"""
from __future__ import annotations

import re

import pytest

from src.replenishment_parser import (
    get_size_regex,
    parse_unit_coherent,
    _reset_cache_for_tests,
)


# ---------------------------------------------------------------------------
# Tests 1-10: per-SKU positive-projection on the 10 G-1 supplements SKUs.
# Source: tests/fixtures/synthetic/healthy_supplements_240d_orders.csv
# (verified 2026-05-18; `awk -F, 'NR>1 {print $4}' ... | sort -u` → 10 SKUs).
# ---------------------------------------------------------------------------

# (sku_text, expected) — None entries are intentional documented gaps
# (weight-only forms + named blend; see KI-18 closeout note).
G1_SUPPLEMENTS_SKUS = [
    ("Ashwagandha KSM-66 300mg 60ct", ("count", 60)),
    ("Collagen Peptides Powder 1lb", None),
    ("Creatine Monohydrate 500g", None),
    ("Magnesium Glycinate 200mg 60ct", ("count", 60)),
    ("Omega-3 Fish Oil 1000mg 120ct", ("count", 120)),
    ("Pre-Workout Energy Complex", None),
    ("Probiotics 50 Billion CFU 30ct", ("count", 30)),
    ("Vitamin D3 + K2 Capsules 90ct", ("count", 90)),
    ("Whey Protein Powder Vanilla 2lb", None),
    ("Zinc + Quercetin Immune Formula", None),
]


@pytest.mark.parametrize("sku,expected", G1_SUPPLEMENTS_SKUS)
def test_g1_supplements_sku_parses_as_pinned(sku, expected):
    """Tests 1-10: per-SKU outcome pinned on every G-1 supplements SKU."""
    _reset_cache_for_tests()
    assert parse_unit_coherent("supplements", sku) == expected


def test_g1_supplements_coverage_rate_documented():
    """Documents the 5/10 coverage rate explicitly so a future regression
    that drops coverage (e.g., a regex shape change) trips this test
    rather than silently changing the supplements posture."""
    _reset_cache_for_tests()
    parsed = sum(
        1 for sku, _ in G1_SUPPLEMENTS_SKUS
        if parse_unit_coherent("supplements", sku) is not None
    )
    assert parsed == 5, (
        f"Expected 5 of 10 G-1 supplements SKUs to parse via "
        f"unit-coherent regexes; got {parsed}. If you intentionally "
        f"expanded coverage, update the pinned expectation here and "
        f"reconsider KI-27 close criteria."
    )


# ---------------------------------------------------------------------------
# Tests 11-13: variant-form parses.
# ---------------------------------------------------------------------------

def test_day_supply_variant_parses():
    """Test 11."""
    _reset_cache_for_tests()
    assert parse_unit_coherent("supplements", "Multivitamin 30-day supply") == (
        "day_supply",
        30,
    )
    # space-separated variant
    assert parse_unit_coherent("supplements", "Greens Powder 60 day supply") == (
        "day_supply",
        60,
    )
    # 90 day supply (no hyphen)
    assert parse_unit_coherent("supplements", "Iron 90 day supply") == (
        "day_supply",
        90,
    )


def test_serving_count_variant_parses():
    """Test 12."""
    _reset_cache_for_tests()
    assert parse_unit_coherent("supplements", "Greens Powder 30 servings") == (
        "serving",
        30,
    )
    assert parse_unit_coherent("supplements", "Hydration Mix 60 servings") == (
        "serving",
        60,
    )
    # singular "serving"
    assert parse_unit_coherent("supplements", "Pre-Workout 90 serving") == (
        "serving",
        90,
    )


def test_capsule_count_variant_parses():
    """Test 13: capsules / caps / tablets / softgels / gummies."""
    _reset_cache_for_tests()
    assert parse_unit_coherent("supplements", "Vitamin C 120 capsules") == (
        "count",
        120,
    )
    assert parse_unit_coherent("supplements", "Magnesium 90 caps") == ("count", 90)
    assert parse_unit_coherent("supplements", "Iron 30 tablets") == ("count", 30)
    assert parse_unit_coherent("supplements", "Fish Oil 60 softgels") == (
        "count",
        60,
    )
    assert parse_unit_coherent("supplements", "Elderberry 90 gummies") == (
        "count",
        90,
    )


# ---------------------------------------------------------------------------
# Test 14: unknown SKU → None, no crash.
# ---------------------------------------------------------------------------

def test_unknown_supplement_sku_returns_none_no_crash():
    """Test 14: un-parseable supplement SKU returns None, does NOT raise."""
    _reset_cache_for_tests()
    assert parse_unit_coherent("supplements", "Just A Mystery Bottle") is None
    assert parse_unit_coherent("supplements", "") is None
    assert parse_unit_coherent("supplements", None) is None
    # Whitespace-only
    assert parse_unit_coherent("supplements", "   ") is None
    # Weight-only is the documented gap (per KI-18 closeout note)
    assert parse_unit_coherent("supplements", "Collagen 1lb") is None


# ---------------------------------------------------------------------------
# Test 15: beauty SKUs still parse via beauty size_regex; no cross-contam.
# ---------------------------------------------------------------------------

def test_beauty_skus_still_parse_via_size_regex():
    """Test 15: beauty regex path unchanged; supplements parser does NOT
    bleed into the beauty surface."""
    _reset_cache_for_tests()
    # Beauty regex pre-G-2 contract: returns a regex string.
    rx = get_size_regex("beauty")
    assert rx is not None
    # The literal beauty regex (M0 byte-identical contract).
    assert rx == "30ml|1 oz|1oz|50ml|1.7 oz|1.7oz|100ml|3.4 oz|3.4oz"

    # Beauty lineitems still match the regex (positive projection).
    pat = re.compile(rx, re.IGNORECASE)
    beauty_skus = [
        "Hydrating Serum 30ml",
        "Vitamin C Cream 1oz",
        "Cleanser 100ml",
        "Toner 1.7 oz",
        "Body Lotion 3.4 oz",
        "Eye Cream 50ml",
    ]
    for sku in beauty_skus:
        assert pat.search(sku.lower()) is not None, sku

    # Beauty does NOT acquire a coherent_units block — supplements parser
    # surface returns None on beauty vertical (no cross-contamination).
    assert parse_unit_coherent("beauty", "Hydrating Serum 30ml") is None

    # Supplements parser does NOT match beauty volume forms either —
    # supplements has no ml/oz patterns by design.
    assert parse_unit_coherent("supplements", "Hydrating Serum 30ml") is None


# ---------------------------------------------------------------------------
# Determinism check — same input twice → same output (hard-stop #3).
# ---------------------------------------------------------------------------

def test_parser_is_deterministic_across_repeated_calls():
    """Hard-stop #3: same input → same output across two runs."""
    _reset_cache_for_tests()
    first = [parse_unit_coherent("supplements", sku) for sku, _ in G1_SUPPLEMENTS_SKUS]
    _reset_cache_for_tests()
    second = [parse_unit_coherent("supplements", sku) for sku, _ in G1_SUPPLEMENTS_SKUS]
    assert first == second
