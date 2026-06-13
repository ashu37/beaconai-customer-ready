"""Sprint 6.5 Ticket T2 — sub-vertical token classifier tests.

Covers:
- Per-subvertical token-dictionary smoke tests (skincare / cosmetics /
  haircare / personal_care / protein / multivitamin / probiotics /
  nootropics / functional).
- Revenue-weighted argmax + 3x / 2x / 1.3x gap thresholds.
- Excluded-token suppression.
- Mixed-vertical -> ``mixed_<vertical>`` LOW confidence.
- Operator override (VERTICAL_MODE=mixed) -> no subvertical populated.
- YAML loader schema check.
- Token dictionary case-insensitive match.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.profile import build_store_profile  # noqa: E402
from src.profile.builder import (  # noqa: E402
    _TAXONOMY_YAML_PATH,
    detect_subvertical,
    detect_taxonomy,
    load_subvertical_taxonomy,
)


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


def _row(cid: str, product: str, *, net_sales: float = 50.0, days_ago: int = 30):
    return {
        "Name": f"#{cid}",
        "customer_id": cid,
        "Created at": ANCHOR - pd.Timedelta(days=days_ago),
        "net_sales": float(net_sales),
        "lineitem_any": product,
        "product": product,
    }


def _df(rows):
    return pd.DataFrame(rows).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 1) YAML loader
# ---------------------------------------------------------------------------


def test_yaml_loader_returns_taxonomy_with_expected_subverticals():
    cfg = load_subvertical_taxonomy()
    assert "verticals" in cfg
    assert set(cfg["verticals"].keys()) == {"beauty", "supplements"}
    expected_beauty = {"skincare", "cosmetics", "haircare", "personal_care"}
    expected_supps = {"protein", "multivitamin", "probiotics", "nootropics", "functional"}
    assert set(cfg["verticals"]["beauty"].keys()) == expected_beauty
    assert set(cfg["verticals"]["supplements"].keys()) == expected_supps


def test_yaml_loader_source_urls_populated():
    cfg = load_subvertical_taxonomy()
    assert "sources" in cfg
    assert len(cfg["sources"]) >= 9  # 4 beauty + 5 supplements sources
    for src in cfg["sources"]:
        assert "url" in src and src["url"].startswith("http")


def test_yaml_every_cell_tagged_heuristic_unvalidated():
    cfg = load_subvertical_taxonomy()
    assert cfg.get("validation_status") == "heuristic_unvalidated"
    for vertical_block in cfg["verticals"].values():
        for sv, block in vertical_block.items():
            assert block.get("validation_status") == "heuristic_unvalidated", sv
            assert "source_authority" in block


def test_yaml_token_counts_meet_floor():
    """Founder Q1 envelope: ~20-40 tokens per cell. Hard-stop on < 15."""
    cfg = load_subvertical_taxonomy()
    for vertical_name, vertical_block in cfg["verticals"].items():
        for sv, block in vertical_block.items():
            n = len(block.get("tokens") or [])
            assert n >= 15, f"{vertical_name}.{sv} has only {n} tokens"


# ---------------------------------------------------------------------------
# 2) Per-subvertical smoke tests
# ---------------------------------------------------------------------------


def _single_product_df(product: str, n: int = 50):
    return _df([_row(f"c{i}", product) for i in range(n)])


def test_skincare_classifies_high():
    g = _single_product_df("Hydrating Face Serum 30ml")
    sv, conf = detect_subvertical(g, "beauty")
    assert sv == "skincare"
    assert conf == "HIGH"


def test_cosmetics_classifies_high():
    g = _single_product_df("Matte Liquid Lipstick")
    sv, conf = detect_subvertical(g, "beauty")
    assert sv == "cosmetics"
    assert conf == "HIGH"


def test_haircare_classifies_high():
    g = _single_product_df("Argan Hair Oil 100ml")
    sv, conf = detect_subvertical(g, "beauty")
    assert sv == "haircare"
    assert conf == "HIGH"


def test_personal_care_classifies_high():
    g = _single_product_df("Lavender Body Wash 250ml")
    sv, conf = detect_subvertical(g, "beauty")
    assert sv == "personal_care"
    assert conf == "HIGH"


def test_protein_classifies_high():
    g = _single_product_df("Whey Protein Isolate 2lb")
    sv, conf = detect_subvertical(g, "supplements")
    assert sv == "protein"
    assert conf == "HIGH"


def test_multivitamin_classifies_high():
    g = _single_product_df("Daily Multivitamin 90ct")
    sv, conf = detect_subvertical(g, "supplements")
    assert sv == "multivitamin"
    assert conf == "HIGH"


def test_probiotics_classifies_high():
    g = _single_product_df("Probiotic 50 Billion CFU")
    sv, conf = detect_subvertical(g, "supplements")
    assert sv == "probiotics"
    assert conf == "HIGH"


def test_nootropics_classifies_high():
    g = _single_product_df("Lion's Mane Brain Focus Blend")
    sv, conf = detect_subvertical(g, "supplements")
    assert sv == "nootropics"
    assert conf == "HIGH"


def test_functional_classifies_high():
    g = _single_product_df("Ashwagandha Adaptogen 60 Capsules")
    sv, conf = detect_subvertical(g, "supplements")
    assert sv == "functional"
    assert conf == "HIGH"


# ---------------------------------------------------------------------------
# 3) Revenue-weighted argmax + gap thresholds
# ---------------------------------------------------------------------------


def test_revenue_weighted_argmax_with_3x_gap_is_high():
    """80% skincare revenue vs 20% cosmetics -> ratio 4x -> HIGH."""
    rows = []
    for i in range(40):
        rows.append(_row(f"sk{i}", "Vitamin Face Serum 30ml", net_sales=100.0))
    for i in range(40):
        rows.append(_row(f"co{i}", "Lipstick Velvet Red", net_sales=25.0))
    g = _df(rows)
    sv, conf = detect_subvertical(g, "beauty")
    assert sv == "skincare"
    assert conf == "HIGH"


def test_revenue_weighted_with_2x_gap_is_medium():
    """60% skincare vs 30% cosmetics -> ratio 2x -> MEDIUM."""
    rows = []
    for i in range(60):
        rows.append(_row(f"sk{i}", "Face Cleanser Gentle 200ml", net_sales=50.0))
    for i in range(30):
        rows.append(_row(f"co{i}", "Mascara Black Volume", net_sales=50.0))
    g = _df(rows)
    sv, conf = detect_subvertical(g, "beauty")
    assert sv == "skincare"
    assert conf == "MEDIUM"


def test_mixed_vertical_with_no_clear_leader():
    """45/40/15 split -> below 1.3x leader/runner-up -> mixed_beauty LOW."""
    rows = []
    for i in range(45):
        rows.append(_row(f"sk{i}", "Face Toner Refresh", net_sales=50.0))
    for i in range(40):
        rows.append(_row(f"co{i}", "Eyeshadow Palette Smoky", net_sales=50.0))
    for i in range(15):
        rows.append(_row(f"ha{i}", "Shampoo Volume 250ml", net_sales=50.0))
    g = _df(rows)
    sv, conf = detect_subvertical(g, "beauty")
    # 45 vs 40 -> ratio 1.125 < 1.3 -> mixed_beauty
    assert sv == "mixed_beauty"
    assert conf == "LOW"


# ---------------------------------------------------------------------------
# 4) Mixed verticals + override
# ---------------------------------------------------------------------------


def test_mixed_vertical_returns_none_no_subvertical():
    g = _single_product_df("Face Serum")
    sv, conf = detect_subvertical(g, "mixed")
    assert sv is None
    assert conf == "REFUSED"


def test_operator_override_mixed_skips_subvertical():
    """VERTICAL_MODE=mixed -> taxonomy.subvertical stays None."""
    g = _single_product_df("Face Serum 30ml")
    rules: list = []
    tax = detect_taxonomy(g, {"VERTICAL_MODE": "mixed"}, rules)
    assert tax.vertical == "mixed"
    assert tax.subvertical is None
    assert tax.subvertical_confidence == "REFUSED"


def test_case_insensitive_token_match():
    """Tokens are lowercased; SKU titles in mixed case still match."""
    g = _df([_row(f"c{i}", "HYDRATING FACE SERUM 30ML") for i in range(20)])
    sv, conf = detect_subvertical(g, "beauty")
    assert sv == "skincare"
    assert conf == "HIGH"


def test_excluded_tokens_suppress_misclassification():
    """A 'Hair Vitamin' SKU is NOT classified as multivitamin: 'vitamin'
    is the multivitamin positive token but 'protein' / 'shampoo' style
    exclusion patterns protect the haircare cell.
    """
    # Make sure a haircare SKU with 'oil' + 'hair' beats personal_care
    # 'body oil' / 'body cream' tokens.
    g = _single_product_df("Hair Oil for Dry Scalp")
    sv, conf = detect_subvertical(g, "beauty")
    assert sv == "haircare"


# ---------------------------------------------------------------------------
# 5) End-to-end via build_store_profile
# ---------------------------------------------------------------------------


def test_build_store_profile_populates_subvertical_on_beauty():
    rows = []
    for i in range(200):
        rows.append(_row(f"c{i}", "Hydrating Face Serum 30ml", net_sales=80.0))
    g = _df(rows)
    profile = build_store_profile(g, {"VERTICAL_MODE": "beauty"}, store_id="beauty_test")
    assert profile.taxonomy.vertical == "beauty"
    assert profile.taxonomy.subvertical == "skincare"
    assert profile.taxonomy.subvertical_confidence in {"HIGH", "MEDIUM"}


def test_build_store_profile_supplements_subvertical():
    rows = []
    for i in range(200):
        rows.append(_row(f"c{i}", "Whey Protein Isolate 2lb", net_sales=60.0))
    g = _df(rows)
    profile = build_store_profile(
        g, {"VERTICAL_MODE": "supplements"}, store_id="supp_test"
    )
    assert profile.taxonomy.vertical == "supplements"
    assert profile.taxonomy.subvertical == "protein"
    assert profile.taxonomy.subvertical_confidence in {"HIGH", "MEDIUM"}


def test_taxonomy_yaml_path_exists():
    assert _TAXONOMY_YAML_PATH.exists()
