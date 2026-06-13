"""S12-T2: Retention curves substrate fit + four-state ModelFitStatus coverage.

Tests ``src/predictive/retention.py::fit_retention``. Covers:

- INSUFFICIENT_DATA below absolute cohort_count floor (3).
- INSUFFICIENT_DATA below min_cohort_size floor (20).
- **Retention is INDEPENDENT** — no chained refusal on BG/NBD (or any
  other substrate). ``fit_retention`` does not accept ``bgnbd_model_card``
  at all.
- **Positive-control synthetic** (DS-mandated, LOAD-BEARING): 12 monthly
  cohorts × 200 customers each @ stable 40% month-1 retention by
  construction. Expect VALIDATED with bootstrap_ci_width_at_month_3 < 0.10
  and no monotonicity violation.
- Cumulative-retention monotonicity violation → REFUSED (data-shape-bug
  simulation).
- Bootstrap determinism: same seed → identical CI widths across two fits.
- No parquet artifact for retention (it is JSON-shaped).
- ``fit_retention`` signature pin (no ``bgnbd_model_card`` argument).
- Independence from BG/NBD REFUSED state (behavioral).
- ``ENGINE_V2_ML_RETENTION`` default OFF.
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.predictive.model_card import ModelFitStatus, RetentionCard
from src.predictive.retention import fit_retention
from src.profile.types import BusinessStage, StoreProfile, Taxonomy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile_mature_beauty() -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical="beauty"),
        business_stage=BusinessStage(stage="MATURE"),
    )


def _profile_startup() -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical="beauty"),
        business_stage=BusinessStage(stage="STARTUP"),
    )


def _add_months(ts: pd.Timestamp, n: int) -> pd.Timestamp:
    """Add ``n`` calendar months to a Timestamp (day=1 floor)."""
    year = ts.year + (ts.month - 1 + n) // 12
    month = ((ts.month - 1 + n) % 12) + 1
    return pd.Timestamp(year=year, month=month, day=1)


def _build_positive_control_fixture(
    n_cohorts: int = 12,
    cohort_size: int = 200,
    month_1_retention: float = 0.40,
    seed: int = 7,
) -> pd.DataFrame:
    """Deterministic positive-control fixture.

    Constructs ``n_cohorts`` monthly cohorts × ``cohort_size`` customers
    each. Each cohort C, starting at month ``M_c``:
      - All ``cohort_size`` customers have an order in month M_c (cohort
        definition by first-purchase month).
      - A constant fraction ``month_1_retention`` (default 40%) have a
        return order at month M_c + 1.
      - The same constant retains at M_c + 2, M_c + 3, ... — i.e., the
        "ever returned" cumulative retention rises from 0% (pre-M0) to
        100% at M0 to ``month_1_retention`` at M1 and stays flat
        (because the same returners keep being counted in cumulative).

    Wait — that's not quite right. cumulative retention is per
    *customer*: a customer who returns at M1 is counted as "ever
    returned" at M1, M2, M3, ... . So cumulative_retention[1] =
    cumulative_retention[2] = ... = 0.40 (still-returners stay flat).

    For the DS test: CI width at month-3 for the cumulative should be
    tight on 200-customer cohorts (Bernoulli with p=0.40 has SE ~
    sqrt(0.4·0.6/200) ~ 0.0346; 95% CI width ~ 0.135 from normal-approx,
    but the percentile bootstrap CI tightens further with replacement).

    Note: To meet the DS-required CI<0.10, we use a slightly higher
    retention rate (0.40) and exactly cohort_size=200. The variance of
    the bootstrap distribution scales as 1/sqrt(n), so 200 customers at
    p=0.40 should comfortably clear CI<0.10 on the percentile bootstrap.
    """
    rng = np.random.default_rng(seed)
    rows = []
    base_month = pd.Timestamp("2024-01-01")  # first cohort

    for c_idx in range(n_cohorts):
        cohort_month = _add_months(base_month, c_idx)
        for cust_idx in range(cohort_size):
            cust_id = f"c{c_idx:02d}_u{cust_idx:04d}"
            # First-month purchase (defines cohort membership).
            order_day = cohort_month + pd.Timedelta(
                days=int(rng.integers(0, 25))
            )
            rows.append(
                {
                    "customer_id": cust_id,
                    "order_date": order_day,
                }
            )
            # Constant-retention return purchases at months 1, 2, ... up
            # to 12 ahead. Each customer either is a "returner" (prob =
            # month_1_retention) or never returns. Deterministic per
            # customer via rng draw.
            is_returner = rng.random() < month_1_retention
            if is_returner:
                # Returner places an order in months 1..12 after first
                # purchase, all of them (so ever-returned-by-M cumulative
                # rises sharply to 40% at M1 and stays flat).
                for m_ahead in range(1, 13):
                    ret_month = _add_months(cohort_month, m_ahead)
                    ret_day = ret_month + pd.Timedelta(
                        days=int(rng.integers(0, 25))
                    )
                    rows.append(
                        {
                            "customer_id": cust_id,
                            "order_date": ret_day,
                        }
                    )

    return pd.DataFrame(rows)


def _build_monotonicity_violation_fixture(seed: int = 11) -> pd.DataFrame:
    """Construct a fixture that triggers a (synthetic) data-shape bug.

    We can't actually make cumulative ever-returned go *down* via real
    orders (mathematically impossible). To simulate the data-shape bug
    REFUSED gate we instead **patch the computation** in this test by
    injecting an extra synthetic customer row that registers in month
    0 and *vanishes* from the cohort thereafter. The cleanest way to
    exercise the REFUSED gate is to verify the monotonicity check
    detection directly with a hand-crafted cumulative vector — see
    ``test_cumulative_monotonicity_violation_refuses``.
    """
    # 4 cohorts of 25 customers each, very simple structure.
    rng = np.random.default_rng(seed)
    rows = []
    base_month = pd.Timestamp("2024-01-01")
    for c_idx in range(4):
        cohort_month = _add_months(base_month, c_idx)
        for cust_idx in range(25):
            cust_id = f"c{c_idx:02d}_u{cust_idx:04d}"
            rows.append(
                {
                    "customer_id": cust_id,
                    "order_date": cohort_month + pd.Timedelta(days=int(rng.integers(0, 25))),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1. Independence pin (signature)
# ---------------------------------------------------------------------------


def test_fit_retention_signature_does_not_accept_bgnbd_model_card():
    """fit_retention is INDEPENDENT — no chained refusal on BG/NBD.

    Structural pin: the signature must NOT accept ``bgnbd_model_card`` or
    any other model-card chained argument. Mirrors S11-T2 CF + S12-T1 RFM
    independence posture.
    """
    sig = inspect.signature(fit_retention)
    param_names = set(sig.parameters.keys())
    forbidden = {
        "bgnbd_model_card",
        "bgnbd_card",
        "gamma_gamma_model_card",
        "survival_model_card",
        "cf_model_card",
        "rfm_model_card",
    }
    overlap = param_names & forbidden
    assert not overlap, (
        f"fit_retention signature must NOT accept chained model-card args; "
        f"found: {overlap}"
    )


# ---------------------------------------------------------------------------
# 2. INSUFFICIENT_DATA gates
# ---------------------------------------------------------------------------


def test_insufficient_data_below_cohort_count_floor():
    """Below the absolute cohort_count floor (3) → INSUFFICIENT_DATA."""
    # 2 cohorts of 30 customers each (above min_cohort_size_floor but
    # below absolute_cohort_count_floor=3).
    rng = np.random.default_rng(0)
    rows = []
    base = pd.Timestamp("2024-01-01")
    for c_idx in range(2):
        cohort_month = _add_months(base, c_idx)
        for cust in range(30):
            rows.append(
                {
                    "customer_id": f"c{c_idx:02d}u{cust:04d}",
                    "order_date": cohort_month + pd.Timedelta(days=int(rng.integers(0, 25))),
                }
            )
    df = pd.DataFrame(rows)
    card = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=0)
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    assert card.bootstrap_ci_width_at_month_3 is None
    assert card.cohorts == {}


def test_insufficient_data_below_min_cohort_size_floor():
    """Cohorts of <20 customers each → INSUFFICIENT_DATA (no eligible cohorts)."""
    rng = np.random.default_rng(1)
    rows = []
    base = pd.Timestamp("2024-01-01")
    for c_idx in range(6):
        cohort_month = _add_months(base, c_idx)
        # Only 10 customers per cohort (below min_cohort_size_floor=20).
        for cust in range(10):
            rows.append(
                {
                    "customer_id": f"c{c_idx:02d}u{cust:04d}",
                    "order_date": cohort_month + pd.Timedelta(days=int(rng.integers(0, 25))),
                }
            )
    df = pd.DataFrame(rows)
    card = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=0)
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    assert card.cohorts == {}


def test_insufficient_data_on_empty_input():
    df = pd.DataFrame(columns=["customer_id", "order_date"])
    card = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=0)
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    assert card.bootstrap_ci_width_at_month_3 is None


# ---------------------------------------------------------------------------
# 3. Independence from BG/NBD (behavioral)
# ---------------------------------------------------------------------------


def test_independent_of_bgnbd_no_chained_refusal():
    """A REFUSED BG/NBD ModelCard does not affect retention's fit decision.

    Behavioral pin: retention fits independently. We construct a healthy
    positive-control fixture and a REFUSED BG/NBD ModelCard alongside,
    then verify the retention fit decision is determined by retention's
    own data alone — no ``chained_bgnbd_refusal`` warning, status is
    determined by the data.
    """
    from src.predictive.model_card import ModelCard, ModelFitStatus as MFS

    bgnbd_refused = ModelCard(
        model_name="bgnbd",
        fit_status=MFS.REFUSED,
        fit_warnings=["convergence_failed"],
    )
    # Intentionally NOT passed to fit_retention — there is no such argument.
    df = _build_positive_control_fixture()
    card = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=0)
    # Status should be VALIDATED (the data is healthy); no chained-refusal
    # warning should appear.
    assert card.fit_status in {MFS.VALIDATED, MFS.PROVISIONAL}
    assert not any("chained_bgnbd" in w for w in card.fit_warnings)
    # Sanity-touch on bgnbd_refused so the local isn't unused.
    assert bgnbd_refused.fit_status == MFS.REFUSED


# ---------------------------------------------------------------------------
# 4. Positive-control synthetic (DS-required, LOAD-BEARING)
# ---------------------------------------------------------------------------


def test_synthetic_retention_dgp_sanity():
    """DS-required positive-control synthetic.

    Original DS spec: 12 monthly cohorts × 200 customers each @ stable
    40% month-1 retention. Assertions:
      - fit_status == VALIDATED
      - bootstrap_ci_width_at_month_3 < 0.10
      - cumulative_retention_monotonicity_violation == False

    **DEVIATION FROM DS SPEC (documented, requires DS review):** at
    cohort_size=200 and p=0.40, Bernoulli sampling variance gives a
    theoretical 95% CI width of ~0.136 (1.96 × sqrt(0.4·0.6/200) ≈ 0.068
    half-width; full width ≈ 0.136). The percentile bootstrap converges
    to this Wald CI in the large-n limit. The CI<0.10 threshold therefore
    requires cohort_size ≥ ~370 at p=0.40 (math: 2·1.96·sqrt(p(1-p)/n)
    < 0.10 ⇒ n > (2·1.96/0.10)² · 0.24 ≈ 369). The implementation is
    correct; the original DS spec's cohort_size=200 cannot satisfy
    CI<0.10 by Bernoulli arithmetic alone.

    To preserve the DS-mandated positive-control posture (VALIDATED with
    CI<0.10 on a healthy DGP), this test uses **cohort_size=400** instead
    of 200, which clears the threshold with comfortable margin. The
    "stable 40% month-1 retention by construction" semantics are
    preserved. Flag for DS review at T2 sign-off.
    """
    df = _build_positive_control_fixture(
        n_cohorts=12,
        cohort_size=400,  # DEVIATION: was 200; see docstring math
        month_1_retention=0.40,
        seed=7,
    )
    card = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=0)

    # The DGP guarantees no monotonicity violation (cumulative is
    # constructed monotone-non-decreasing by definition).
    assert card.cumulative_retention_monotonicity_violation is False, (
        f"positive-control DGP must have monotone cumulative retention; "
        f"got violation=True. Cohorts: {list(card.cohorts.keys())}"
    )

    # CI width must be tight — DS expects < 0.10.
    assert card.bootstrap_ci_width_at_month_3 is not None
    assert card.bootstrap_ci_width_at_month_3 < 0.10, (
        f"positive-control bootstrap_ci_width_at_month_3 = "
        f"{card.bootstrap_ci_width_at_month_3:.4f}, DS expects < 0.10. "
        f"Bootstrap implementation may have a bug."
    )

    # Status must be VALIDATED.
    assert card.fit_status == ModelFitStatus.VALIDATED, (
        f"positive-control DGP must VALIDATE; got {card.fit_status}. "
        f"CI width: {card.bootstrap_ci_width_at_month_3}, "
        f"cohort_count: {card.cohort_count}, "
        f"min_cohort_size: {card.min_cohort_size}, "
        f"warnings: {card.fit_warnings}"
    )

    # Sanity on cohort_count: should be 12 (all 12 monthly cohorts visible
    # at the snapshot, all with ≥3 months of look-forward).
    # Note: the 12th cohort is the snapshot month itself so it gets 0
    # months of forward visibility and is excluded. Expect 9-12 cohorts.
    assert card.cohort_count >= 9, (
        f"expected ≥9 eligible cohorts, got {card.cohort_count}"
    )
    assert card.min_cohort_size >= 20


# ---------------------------------------------------------------------------
# 5. Monotonicity violation → REFUSED
# ---------------------------------------------------------------------------


def test_cumulative_monotonicity_violation_refuses(monkeypatch):
    """Synthetic data-shape bug: cumulative retention rises (data bug
    simulation) → REFUSED.

    Mathematically the "ever-returned-in-[0,M]" cumulative can ONLY
    monotonically non-decrease. To exercise the REFUSED gate we patch
    the monotonicity detector to return True for at least one cohort,
    simulating what would happen if a real data bug surfaced a
    decreasing cumulative curve.
    """
    from src.predictive import retention as retention_mod

    original = retention_mod._detect_monotonicity_violation
    call_count = {"n": 0}

    def fake_detect(cumulative):
        call_count["n"] += 1
        # Trip violation on the first cohort only — sufficient for REFUSED.
        return call_count["n"] == 1

    monkeypatch.setattr(retention_mod, "_detect_monotonicity_violation", fake_detect)
    df = _build_positive_control_fixture(
        n_cohorts=6, cohort_size=40, month_1_retention=0.40, seed=3
    )
    card = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=0)
    assert card.fit_status == ModelFitStatus.REFUSED
    assert card.cumulative_retention_monotonicity_violation is True
    assert "cumulative_retention_monotonicity_violation" in card.fit_warnings

    # Restore (monkeypatch handles this on teardown, just for clarity).
    assert retention_mod._detect_monotonicity_violation is fake_detect
    _ = original  # silence unused


def test_monotonicity_detector_correctness():
    """Direct unit on the monotonicity detector — invariance properties."""
    from src.predictive.retention import _detect_monotonicity_violation

    assert _detect_monotonicity_violation([0.0, 0.2, 0.4, 0.5, 0.6]) is False
    assert _detect_monotonicity_violation([0.0, 0.0, 0.0, 0.0]) is False
    assert _detect_monotonicity_violation([0.5, 0.5, 0.5]) is False
    # Decrease anywhere → violation.
    assert _detect_monotonicity_violation([0.0, 0.4, 0.3, 0.5]) is True
    assert _detect_monotonicity_violation([1.0, 0.9]) is True


# ---------------------------------------------------------------------------
# 6. Bootstrap determinism
# ---------------------------------------------------------------------------


def test_bootstrap_seed_determinism():
    """Same seed → identical CI widths across two fits."""
    df = _build_positive_control_fixture(
        n_cohorts=6, cohort_size=50, month_1_retention=0.40, seed=42
    )
    card_a = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=0)
    card_b = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=0)

    assert card_a.bootstrap_ci_width_at_month_3 == card_b.bootstrap_ci_width_at_month_3
    # Per-cohort CIs identical.
    for key in card_a.cohorts:
        assert card_a.cohorts[key]["ci_lower"] == card_b.cohorts[key]["ci_lower"]
        assert card_a.cohorts[key]["ci_upper"] == card_b.cohorts[key]["ci_upper"]


def test_bootstrap_different_seed_yields_different_ci():
    """Different seed → typically different CI bounds (sanity check on seed wiring)."""
    df = _build_positive_control_fixture(
        n_cohorts=6, cohort_size=50, month_1_retention=0.40, seed=42
    )
    card_a = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=0)
    card_b = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=999)
    # At least one cohort × bound × month should differ across seeds.
    differ = False
    for key in card_a.cohorts:
        for bound in ("ci_lower", "ci_upper"):
            a = card_a.cohorts[key][bound]
            b = card_b.cohorts[key][bound]
            if a != b:
                differ = True
                break
        if differ:
            break
    assert differ, "expected at least one CI bound to differ across seeds"


# ---------------------------------------------------------------------------
# 7. No parquet artifact for retention
# ---------------------------------------------------------------------------


def test_no_parquet_artifact_for_retention(tmp_path, monkeypatch):
    """Retention is JSON-shaped (lives in cohort_diagnostics); no parquet path created."""
    # Run a healthy fit and verify nothing under tmp_path / "predictive"
    # got a retention.parquet artifact.
    df = _build_positive_control_fixture(
        n_cohorts=6, cohort_size=40, month_1_retention=0.40, seed=5
    )
    # store_id intentionally pointed at tmp_path so we can scan for parquet writes.
    card = fit_retention(df, _profile_mature_beauty(), store_id=str(tmp_path), seed=0)
    # Walk tmp_path looking for any *.parquet referencing retention.
    matches = list(tmp_path.rglob("*retention*.parquet"))
    assert matches == [], f"retention should not write parquet; found: {matches}"
    # And of course not at any standard predictive path either.
    assert not (tmp_path / "predictive" / "retention.parquet").exists()
    # Card should have its JSON-shaped cohorts dict.
    assert card.cohorts is not None


# ---------------------------------------------------------------------------
# 8. ENGINE_V2_ML_RETENTION default OFF
# ---------------------------------------------------------------------------


def test_engine_v2_ml_retention_flag_default_off(monkeypatch):
    """The ENGINE_V2_ML_RETENTION flag default is ``false`` at T2.

    T2.5 (separate ticket) flips the default to ``true`` atomically with
    the orchestration wire-up.
    """
    # Clear any pre-set env var to read the DEFAULTS shape.
    monkeypatch.delenv("ENGINE_V2_ML_RETENTION", raising=False)
    # Re-import the module to refresh DEFAULTS.
    import importlib

    import src.utils as utils_mod

    importlib.reload(utils_mod)
    assert utils_mod.DEFAULTS["ENGINE_V2_ML_RETENTION"] is False


# ---------------------------------------------------------------------------
# 9. Round-trip through EngineRun.cohort_diagnostics
# ---------------------------------------------------------------------------


def test_cohort_diagnostics_round_trips_via_engine_run():
    """RetentionCard payload (as dict) round-trips through EngineRun
    to_dict/from_dict via the new cohort_diagnostics slot."""
    from dataclasses import asdict

    from src.engine_run import EngineRun

    df = _build_positive_control_fixture(
        n_cohorts=4, cohort_size=30, month_1_retention=0.40, seed=11
    )
    card = fit_retention(df, _profile_mature_beauty(), store_id="t", seed=0)
    run = EngineRun()
    run.cohort_diagnostics["retention"] = asdict(card)
    payload = run.to_dict()
    assert "cohort_diagnostics" in payload
    assert "retention" in payload["cohort_diagnostics"]
    rehydrated = EngineRun.from_dict(payload)
    assert rehydrated.cohort_diagnostics["retention"]["model_name"] == "retention"


def test_cohort_diagnostics_default_empty():
    """Pre-S12 payloads (no cohort_diagnostics key) round-trip with {}."""
    from src.engine_run import EngineRun

    payload = {"store_profile": {}}  # no cohort_diagnostics key
    rehydrated = EngineRun.from_dict(payload)
    assert rehydrated.cohort_diagnostics == {}
