"""ModelCard + ModelFitStatus + threshold loader (Sprint 10 — T1).

This module is the typed surface for the ML predictive layer's fit
health. ``ModelCard`` instances are populated by per-model fit
functions (e.g. ``src/predictive/bgnbd.py::fit_bgnbd``) and surface to
operators via ``engine_run.predictive_models`` (when
``ENGINE_V2_ML_BGNBD`` is ON).

ModelFitStatus — four-state vocabulary (DS-locked 2026-05-25)
=============================================================

Closed enum. Four values:

- ``VALIDATED`` — fit converged, the cold-start floor cleared (months /
  repeat / orders), holdout MAPE strictly below the validated cutoff,
  no warnings. **Ranking + magnitudes both usable** at S13.

- ``PROVISIONAL`` — fit converged but envelope thin (floor cleared at
  relaxed multipliers OR MAPE between the validated cutoff and
  ``validated + provisional_mape_addend``). **Ranking usable;
  absolute LTV magnitudes must not be quoted to merchant.** This is
  load-bearing for S13 audience-builder consumption: PROVISIONAL fits
  flow through ranking; REFUSED / INSUFFICIENT_DATA do not.

- ``INSUFFICIENT_DATA`` — engine **DECLINED** to fit (below the
  cold-start floor on months / repeat / orders). Silent fallback (no
  operator alert). **No parquet artifact written.** ModelCard entry is
  present in ``engine_run.predictive_models`` with empty
  ``parameters`` — the audit story is "we didn't try."

- ``REFUSED`` — engine **TRIED**, fit failed (ConvergenceWarning, MAPE
  above the relaxed threshold, or the Gamma-Gamma
  frequency-monetary-correlation sanity check above its REFUSED
  cutoff). **Operator alert.** ModelCard present with ``fit_warnings``
  populated; parquet still not written. The audit story is "we tried
  and it didn't work."

INSUFFICIENT_DATA and REFUSED have different audit stories and
different privacy semantics. INSUFFICIENT_DATA produces no per-customer
artifact at all (D-3 deletion is a no-op). REFUSED produces a
ModelCard with diagnostic state but no parquet either.

Vocabulary-stacking discipline (DS Option A — no rename)
========================================================

The ``ModelFitStatus`` enum **reuses the VALIDATED / PROVISIONAL
labels** also used by ``src/priors_validation.py::PriorValidationStatus``.
The two are namespace-disambiguated by:

- **Different dataclasses.** ``Prior.validation_status: PriorValidationStatus``
  vs ``ModelCard.fit_status: ModelFitStatus``. Two distinct typed slots.
- **Different casing.** ``PriorValidationStatus`` values are lowercase
  (``validated_external``, ``heuristic_unvalidated``, ``placeholder``).
  ``ModelFitStatus`` values are uppercase
  (``VALIDATED``, ``PROVISIONAL``, ``INSUFFICIENT_DATA``, ``REFUSED``).
- **Docstring cross-reference.** (This block.)

The Gamma-Gamma ``|pearson_r|`` cutoffs are **advisory cutoffs, not a
theoretical independence test.** The Fader-Hardie-Lee (2005) derivation
assumes frequency-monetary independence; our thresholds are the
empirical envelope above which magnitude quoting becomes unsafe.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


# ---------------------------------------------------------------------------
# ModelFitStatus enum (closed; four values)
# ---------------------------------------------------------------------------


class ModelFitStatus(str, Enum):
    """Four-state ML fit health (S10-T1 DS-locked).

    See module docstring for the audit-story / privacy distinction
    between ``INSUFFICIENT_DATA`` and ``REFUSED``. Closed enum — adding
    a fifth value requires explicit founder + DS sign-off.
    """

    VALIDATED = "VALIDATED"
    PROVISIONAL = "PROVISIONAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REFUSED = "REFUSED"


# ---------------------------------------------------------------------------
# RFM segment-distribution aggregate (S-FE-rfm-segment-distribution — L-EV-17)
# ---------------------------------------------------------------------------


class RfmSegmentDistributionSuppressionReason(str, Enum):
    """S-FE-rfm-segment-distribution (L-EV-15/17) — RULE-A paired null-reason
    for :attr:`ModelCard.segment_distribution`.

    Paired with the aggregate's presence: when
    ``segment_distribution is None`` AND the ModelCard is an ``rfm`` card,
    ``segment_distribution_suppression_reason`` MUST be set; when
    ``segment_distribution`` is populated it MUST be ``None``. RFM has no
    descriptive twin (the segmentation IS the inferential product, L-EV-15)
    — it suppresses as a unit, never a fabricated/partial distribution.

    Members:

    - ``FIT_NOT_VALIDATED`` — RFM ``fit_status not in {VALIDATED,
      PROVISIONAL}`` (REFUSED / INSUFFICIENT_DATA). The segmentation did
      not clear the inferential gate; the typed reason renders, never a
      distribution.
    - ``FLAG_OFF`` — the segment-distribution producer did not run on this
      path (``ENGINE_V2_ML_RFM`` OFF, or a non-VALIDATED short-circuit
      ModelCard constructed before the band-population seam).
    """

    FIT_NOT_VALIDATED = "fit_not_validated"
    FLAG_OFF = "flag_off"


@dataclass
class SegmentBand:
    """One named-segment band of the RFM aggregate ``segment_distribution``.

    AGGREGATE-ONLY + DESCRIPTIVE (L-EV-17/20): carries the named segment,
    its observed customer ``count``, and its ``share`` of the analyzed
    customer base. It carries NO per-customer rows, NO monetary magnitude,
    NO projected rate / lift / dollar — an inferential or monetary field on
    this band is a REJECT-class breach. The three fields below are the
    complete, closed shape.

    Fields:

    - ``segment_name`` — one of the 11 industry-canonical named segments
      (e.g. ``"Champions"``, ``"Hibernating"``). Real, builder-assigned.
    - ``n`` — observed count of customers in this segment. Non-negative
      integer.
    - ``share`` — ``n / n_customers`` (fraction of the analyzed base).
      Range [0.0, 1.0]; the bands' shares sum to ~1.0 (float rounding).
    """

    segment_name: str
    n: int
    share: float


# ---------------------------------------------------------------------------
# ModelCard dataclass (typed slot for engine_run.predictive_models[...])
# ---------------------------------------------------------------------------


@dataclass
class ModelCard:
    """Aggregate fit metadata for one ML predictive model.

    Populated by per-model fit functions (e.g. ``fit_bgnbd``). Round-trips
    through ``engine_run.to_dict()`` / ``from_dict()`` via the existing
    ``_to_jsonable`` recursion (enums unwrap to their string value).

    Fields:
    - ``model_name``: ``"bgnbd"`` / ``"gamma_gamma"``.
    - ``fit_status``: ``ModelFitStatus`` (four-value closed enum).
    - ``fit_warnings``: list of advisory warning codes (empty when
      VALIDATED). Convergence + correlation diagnostics surface here.
    - ``parameters``: dict of fitted parameters
      (e.g. BG/NBD's ``r``, ``alpha``, ``a``, ``b``). Empty ``{}`` when
      ``fit_status in {INSUFFICIENT_DATA, REFUSED}``.
    - ``training_window_days``: observation window length used for fit.
    - ``n_observed``: number of customers observed during training.
    - ``holdout_mape``: holdout-set mean absolute percentage error.
      **DS-deprecated 2026-05-26 as the GATING metric** (per-customer
      MAPE denominator clamps to 1.0 for single-purchase customers, so
      the mean collapses to "mean predicted 30d repeat rate" and does
      not measure error — see ``src/predictive/bgnbd.py`` module
      docstring). Retained for operator-diagnostic continuity. ``None``
      when no fit was attempted.
    - ``holdout_rank_spearman``: **PRIMARY GATING METRIC** (DS-locked
      2026-05-26). Spearman rank correlation between predicted
      expected purchases (over the holdout window, using train-fit
      params + train RFM) and observed per-customer purchase counts in
      the holdout window. Maps directly to the operational goal of
      within-audience ranking for Klaviyo dispatch. ``None`` when
      observed counts have zero variance (rank undefined).
    - ``holdout_agg_ratio``: aggregate calibration ratio
      ``sum(predicted) / max(sum(observed), 1.0)``. Operator-visible
      diagnostic (predicted-vs-actual total repeat count). **Does NOT
      gate** — this is the Fader-Hardie-Lee (2005) aggregate
      calibration view, surfaced for transparency.
    - ``holdout_c_index``: Harrell's C-index (concordance index between
      predicted risk and observed event times). **PRIMARY GATING METRIC
      for survival** (DS-locked 2026-05-26, S11-T1). Parallel surface
      slot to ``holdout_rank_spearman`` for BG/NBD / Gamma-Gamma. ``None``
      when survival not fit. Range [0.0, 1.0]; 0.5 = random; > 0.5 means
      higher predicted risk → earlier observed event.
    - ``holdout_brier_score_90d``: time-dependent integrated Brier score
      at the 90-day horizon. **SECONDARY GATING METRIC for survival**
      (calibration check; pure rank discrimination alone can ship
      miscalibrated absolute times). ``None`` when survival not fit.
      Range [0.0, 1.0]; lower = better calibrated.
    - ``holdout_top_k_recall``: top-K recall @ K=10 on a time-based
      holdout. **PRIMARY GATING METRIC for CF** (collaborative filtering,
      DS-locked 2026-05-26, S11-T2). For each held-out customer×item
      interaction, the implicit-ALS top-10 recommendation list is checked;
      recall = fraction of held-out interactions in top-10. ``None`` when
      CF not fit. Range [0.0, 1.0]; higher = better rank recovery.
    - ``coverage_at_k``: fraction of catalog items appearing in any
      user's top-10 recommendation list. **DIAGNOSTIC ONLY for CF** —
      operator-visible (popularity-bias warning surface); does NOT gate
      acceptance. ``None`` when CF not fit. Range [0.0, 1.0].
    - ``segment_monotonicity_spearman``: Spearman rank correlation between
      the named-segment LTV-rank-order and observed mean monetary value
      per segment. **PRIMARY GATING METRIC for RFM** (DS-locked
      2026-05-28, S12-T1). Note: this is an **internal-consistency**
      metric (the segmentation IS the answer; there is no held-out
      object), NOT a holdout / fit-quality metric — structurally
      different from ``holdout_rank_spearman`` / ``holdout_c_index`` /
      ``holdout_top_k_recall``. ``None`` when RFM not fit. Range
      [-1.0, 1.0]; higher = stronger monotonicity between named-segment
      order and realized economic value.
    - ``quintile_coverage_min``: minimum quintile occupancy ratio
      (smallest of {R-quintile-coverage, F-quintile-coverage,
      M-quintile-coverage}, where each is ``min(quintile_count) /
      n_customers``). **SECONDARY REFUSED guard for RFM**: below
      ``refused_quintile_coverage_min`` (default 0.05) → REFUSED
      (degenerate quintile collapse, ``pd.qcut`` ties dominate).
      Internal-consistency metric, NOT a holdout metric. ``None`` when
      RFM not fit. Range [0.0, 0.2]; 0.2 = perfectly balanced quintiles.
    - Holdout split is **TIME-BASED**: train on ``[t0, t_split]``,
      observe on ``(t_split, t_end]`` where ``t_split = t_end -
      window_days`` (not the original T1 20% customer-hash holdout).
    - ``fit_timestamp``: ISO-8601 UTC timestamp of fit attempt.
    - ``parquet_schema_version``: schema version of the per-customer
      parquet artifact written for VALIDATED/PROVISIONAL fits. Pinned
      to ``1`` at S10-T1.
    """

    model_name: str = ""
    fit_status: ModelFitStatus = ModelFitStatus.INSUFFICIENT_DATA
    fit_warnings: List[str] = field(default_factory=list)
    parameters: Dict[str, float] = field(default_factory=dict)
    training_window_days: int = 0
    n_observed: int = 0
    # S13-T0 (2026-05-29): authoritative metric storage. Per-substrate
    # ModelCards keep their identity at the ``predictive_models[<substrate>]``
    # dict-key level; metric-key namespace is therefore implicit at the
    # ModelCard level (NOT inside ``metrics`` keys — e.g.
    # ``metrics["holdout_rank_spearman"]`` not ``metrics["bgnbd.holdout_rank_spearman"]``).
    # Legacy typed Optional fields (``holdout_rank_spearman``,
    # ``holdout_agg_ratio``, ``holdout_mape``, ``holdout_c_index``,
    # ``holdout_brier_score_90d``, ``holdout_top_k_recall``,
    # ``coverage_at_k``, ``segment_monotonicity_spearman``,
    # ``quintile_coverage_min``) are preserved as read-only ``@property``
    # shims reading from ``metrics``; they will be deprecated at S15+
    # post-beta consolidation. The shims keep ``card.holdout_rank_spearman``
    # working at the Python-object level for existing tests and chained
    # consumers; JSON serialization carries ONLY the ``metrics`` dict (the
    # legacy keys do NOT appear at the engine_run.json level — JSON
    # consumers must read from ``metrics``).
    metrics: Dict[str, float] = field(default_factory=dict)
    fit_timestamp: str = ""
    parquet_schema_version: int = 1

    # S-FE-rfm-segment-distribution (2026-06-03; additive within 2.1.0,
    # FOUNDER-AUTHORIZED per docs/evidence_layer.md §7 L-EV-17). RFM-SCOPED:
    # populated ONLY on the ``rfm`` ModelCard, ONLY when
    # ``fit_status in {VALIDATED, PROVISIONAL}``. Other substrates'
    # ModelCards (bgnbd / gamma_gamma / survival / cf) have no named-segment
    # concept and leave this ``None`` (with the FLAG_OFF reason). AGGREGATE-
    # ONLY + DESCRIPTIVE: list of per-segment {name, n, share} bands — NO
    # per-customer rows, NO monetary magnitude (L-EV-17/20). RULE-A typed
    # absence: when ``None`` on an ``rfm`` card the paired
    # ``segment_distribution_suppression_reason`` is set; RFM suppresses as a
    # unit (no descriptive twin — L-EV-15), never a fabricated/partial
    # distribution. Older runs / non-RFM cards deserialize with ``None``
    # (additive optional field; from_dict tolerates absence).
    segment_distribution: Optional[List[SegmentBand]] = None
    # Paired RULE-A null-reason for ``segment_distribution`` (RevenueRange /
    # DescriptiveDistribution precedent). Set iff ``segment_distribution is
    # None`` on a card whose segmentation was attempted; ``None`` when bands
    # are populated.
    segment_distribution_suppression_reason: Optional[
        RfmSegmentDistributionSuppressionReason
    ] = None

    # ------------------------------------------------------------------
    # S13-T0 legacy-field constructor-kwarg back-compat (InitVar; not stored).
    # These accept the pre-S13 typed-Optional-field constructor calls and
    # route the value into ``metrics[<key>]`` via ``__post_init__``. They
    # do NOT become dataclass fields and therefore do NOT appear in
    # ``asdict(card)`` / engine_run.json — only the ``metrics`` dict does.
    # Existing tests (S10-T1, S11-T1, S11-T2, S12-T1) that construct
    # ``ModelCard(..., holdout_X=value, ...)`` continue to work; their
    # subsequent ``card.holdout_X`` reads route via the ``@property`` shim
    # below. New producer code SHOULD pass ``metrics={...}`` directly.
    # ------------------------------------------------------------------
    holdout_mape: InitVar[Optional[float]] = None
    holdout_rank_spearman: InitVar[Optional[float]] = None
    holdout_agg_ratio: InitVar[Optional[float]] = None
    holdout_c_index: InitVar[Optional[float]] = None
    holdout_brier_score_90d: InitVar[Optional[float]] = None
    holdout_top_k_recall: InitVar[Optional[float]] = None
    coverage_at_k: InitVar[Optional[float]] = None
    segment_monotonicity_spearman: InitVar[Optional[float]] = None
    quintile_coverage_min: InitVar[Optional[float]] = None

    def __post_init__(
        self,
        holdout_mape: Optional[float],
        holdout_rank_spearman: Optional[float],
        holdout_agg_ratio: Optional[float],
        holdout_c_index: Optional[float],
        holdout_brier_score_90d: Optional[float],
        holdout_top_k_recall: Optional[float],
        coverage_at_k: Optional[float],
        segment_monotonicity_spearman: Optional[float],
        quintile_coverage_min: Optional[float],
    ) -> None:
        # Migrate any legacy-typed constructor kwargs into ``metrics``.
        # Caller-passed ``metrics={...}`` takes precedence for any key already
        # present; legacy kwargs only fill keys not already supplied.
        legacy = {
            "holdout_mape": holdout_mape,
            "holdout_rank_spearman": holdout_rank_spearman,
            "holdout_agg_ratio": holdout_agg_ratio,
            "holdout_c_index": holdout_c_index,
            "holdout_brier_score_90d": holdout_brier_score_90d,
            "holdout_top_k_recall": holdout_top_k_recall,
            "coverage_at_k": coverage_at_k,
            "segment_monotonicity_spearman": segment_monotonicity_spearman,
            "quintile_coverage_min": quintile_coverage_min,
        }
        for k, v in legacy.items():
            if v is not None and k not in self.metrics:
                self.metrics[k] = v

    # ------------------------------------------------------------------
    # S13-T0 legacy-field read shim via ``__getattr__``.
    #
    # ``__getattr__`` fires only when the normal attribute lookup misses
    # — so it does NOT conflict with the same-named ``InitVar`` declared
    # above (those names are consumed by the dataclass-generated
    # ``__init__`` and do not become instance attributes after
    # construction). Reads of ``card.holdout_rank_spearman`` etc. route
    # to ``metrics.get(<key>)`` and return ``None`` when absent. New
    # producer code SHOULD write to ``metrics[<key>]`` directly. The
    # shim will be removed at S15+ post-beta consolidation.
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        if name in _LEGACY_METRIC_KEYS:
            # ``self.metrics`` access is safe here: ``__getattr__`` only
            # fires after normal lookup misses, and ``metrics`` is a true
            # dataclass field that resolves via the normal path.
            return self.metrics.get(name)
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r}"
        )


# Closed allowlist of legacy metric-field names — back-compat constructor
# kwargs + ``__getattr__`` shim keys. Extending this list requires DS
# sign-off (S13-T0 closure contract: substrate producers should write to
# ``ModelCard.metrics[<key>]`` directly going forward).
_LEGACY_METRIC_KEYS = frozenset({
    "holdout_mape",
    "holdout_rank_spearman",
    "holdout_agg_ratio",
    "holdout_c_index",
    "holdout_brier_score_90d",
    "holdout_top_k_recall",
    "coverage_at_k",
    "segment_monotonicity_spearman",
    "quintile_coverage_min",
})


# Strip the class-level ``None`` attributes that ``@dataclass`` leaves
# behind from the ``InitVar[Optional[float]] = None`` declarations above.
# Without this strip, normal attribute lookup on a ModelCard instance
# would find ``None`` at the class level for these names and short-
# circuit before reaching the ``__getattr__`` shim — defeating the
# read-from-metrics behavior. Safe because ``InitVar`` machinery has
# already captured the defaults into ``__init__``; the lingering class
# attributes are vestigial.
for _legacy_key in _LEGACY_METRIC_KEYS:
    if _legacy_key in ModelCard.__dict__:
        delattr(ModelCard, _legacy_key)
del _legacy_key


# ---------------------------------------------------------------------------
# RetentionCard dataclass (typed slot for engine_run.cohort_diagnostics[...])
# ---------------------------------------------------------------------------


@dataclass
class RetentionCard:
    """Aggregate fit metadata for the cohort-aggregate retention substrate.

    Populated by ``src/predictive/retention.py::fit_retention``. Lives in
    ``engine_run.cohort_diagnostics["retention"]`` (NOT
    ``predictive_models``) — retention is a cohort-aggregate diagnostic,
    not a per-customer ranker. Forcing it into the ranker Dict would
    invert that slot's invariants (DS S12 plan review §C).

    **Reuses the ``ModelFitStatus`` four-state enum** (vocab-stacking
    Option A precedent from S11 — labels shared, namespace-disambiguated
    by dataclass identity). The four states have the same semantics:

    - ``VALIDATED`` — bootstrap CI width at month 3 ≤ stage-keyed
      VALIDATED floor; cohort_count ≥ stage VALIDATED floor; no
      cumulative-retention monotonicity violation.
    - ``PROVISIONAL`` — CI width ≤ provisional ceiling (default 0.35);
      cohort_count ≥ 0.5 × stage floor; no monotonicity violation.
    - ``INSUFFICIENT_DATA`` — engine DECLINED to fit (below absolute
      cohort_count floor=3 OR below min_cohort_size floor=20). No
      retention curves computed.
    - ``REFUSED`` — engine TRIED, the curve is data-shape-bug-indicating
      (cumulative-retention monotonicity violation) OR CI width above
      the provisional ceiling (>0.35) OR cohort_count below absolute
      floor=3 OR min_cohort_size below floor=20 after attempted fit.

    Fields:

    - ``model_name``: ``"retention"``.
    - ``fit_status``: ``ModelFitStatus`` (REUSED enum).
    - ``fit_warnings``: list of advisory warning codes (empty when
      VALIDATED).
    - ``cohort_count``: number of cohorts analyzed (first-purchase
      month buckets meeting the ``min_cohort_size`` floor).
    - ``min_cohort_size``: smallest analyzed cohort size.
    - ``bootstrap_ci_width_at_month_3``: PRIMARY gate metric (CI width
      averaged across analyzed cohorts at month 3). ``None`` when not
      computed (INSUFFICIENT_DATA early-exit).
    - ``cumulative_retention_monotonicity_violation``: REFUSED gate —
      ``True`` if ANY cohort has a non-monotone "still-active"
      cumulative-retention curve (mathematically impossible on the
      chosen definition; signals a data-shape bug).
    - ``months_horizon``: months projected forward per cohort (default 12).
    - ``cohorts``: per-cohort retention curves + bootstrap CIs, shape::

          {
              "2024-01": {
                  "period_retention": [1.0, 0.50, 0.42, ...],
                  "cumulative_retention": [1.0, 0.50, 0.42, ...],
                  "ci_lower": [...],
                  "ci_upper": [...],
                  "n_customers": 200,
              },
              ...
          }

      Empty ``{}`` when fit_status in {INSUFFICIENT_DATA}.
    - ``bootstrap_iterations``: number of resamples used (default 1000).
    - ``seed``: bootstrap RNG seed (default 0; pinned for determinism).
    - ``fit_timestamp``: ISO-8601 UTC timestamp (normalized at T2.5
      determinism comparator).
    - ``parquet_schema_version``: nominal version tag for forward-compat;
      **retention does NOT write a parquet artifact** (the cohorts dict
      is JSON-shaped and lives directly in ``engine_run.cohort_diagnostics``).
      Pinned to ``1`` for forward-compat with the ``ModelCard`` precedent.

    Cumulative-retention definition (DS-locked 2026-05-28)
    ======================================================

    ``cumulative_retention[M]`` = fraction of cohort C still active at
    month M after first purchase = fraction with ≥1 order in calendar
    months [0, M] (the "ever-returned-by-month-M" view, equivalent to
    "still active" on the cumulative survival framing). This curve is
    **monotonically non-DECREASING** as M increases (a customer who has
    ever returned cannot un-return). A monotonicity VIOLATION
    (cumulative retention DECREASES as M increases) is mathematically
    impossible on this definition — it signals a data-shape bug
    (duplicate orders excluded, cohort drift, mis-bucketed dates).
    Hence REFUSED.

    Note on definition choice: the DS verdict §G framed monotonicity
    on the "still-active = cumulative" semantics either way ("ever
    returned" non-decreasing OR "still active" non-increasing); both
    semantics permit a REFUSED gate on violation. Module implements
    "ever returned in [0, M]" (non-decreasing) which is the
    standard empirical-cohort retention curve framing in DTC
    analytics; the gate is on monotone direction violation, not on
    the sign of the trend.
    """

    model_name: str = "retention"
    fit_status: ModelFitStatus = ModelFitStatus.INSUFFICIENT_DATA
    fit_warnings: List[str] = field(default_factory=list)
    cohort_count: int = 0
    min_cohort_size: int = 0
    bootstrap_ci_width_at_month_3: Optional[float] = None
    cumulative_retention_monotonicity_violation: bool = False
    months_horizon: int = 12
    cohorts: Dict[str, Any] = field(default_factory=dict)
    bootstrap_iterations: int = 1000
    seed: int = 0
    fit_timestamp: str = ""
    parquet_schema_version: int = 1


# ---------------------------------------------------------------------------
# Threshold loader (business-stage-keyed via config/gate_calibration.yaml)
# ---------------------------------------------------------------------------

_GATE_CAL_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "gate_calibration.yaml"
)

# Stage order for stage-uncertainty broader-cell fallback. Mirrors
# ``src/profile/builder.py::_STAGE_ORDER``.
_STAGE_ORDER = ("startup", "growth", "mature", "enterprise")

# Hardcoded fallback when profile is None / flag is OFF / YAML missing.
# Matches the ``mature`` cell numbers in config/gate_calibration.yaml so
# the loader degrades gracefully without silently shifting acceptance.
_FALLBACK_MATURE_BGNBD = {
    "months_data_validated": 6,
    "repeat_customers_validated": 500,
    "orders_validated": 1500,
    # T1.4 (2026-05-26): MAPE retained as diagnostic only; Spearman gates.
    "holdout_mape_validated": 0.25,
    "holdout_rank_spearman_validated": 0.20,
}
_FALLBACK_RELAXATION = {
    "provisional_n_multiplier": 0.5,
    "provisional_mape_addend": 0.10,  # deprecated; retained for back-compat read
    "provisional_rank_spearman_floor": 0.10,
}
_FALLBACK_GAMMA_GAMMA = {
    "independence_pearson_r_validated": 0.3,
    "independence_pearson_r_provisional": 0.5,
}

# S10-T2 (2026-05-26) — DS-locked Gamma-Gamma classifier thresholds.
# Same value across stages by design (G-G is more universal than BG/NBD
# heuristically — see config/gate_calibration.yaml inline notes). Kept
# stage-keyed for forward-compat. Speculative-until-S14; KI-NEW-Q
# territory (parallel to KI-NEW-P-v2 for BG/NBD Spearman thresholds).
_FALLBACK_GAMMA_GAMMA_STAGE_CELL = {
    "repeat_customers_validated": 50,
    "holdout_rank_spearman_validated": 0.20,
    "agg_ratio_min": 0.5,
    "agg_ratio_max": 1.5,
}
_FALLBACK_GAMMA_GAMMA_RELAXATION = {
    "provisional_rank_spearman_floor": 0.10,
    "provisional_agg_ratio_min": 0.4,
    "provisional_agg_ratio_max": 1.6,
}
_FALLBACK_GAMMA_GAMMA_INDEPENDENCE = {
    "pearson_r_violation_threshold": 0.10,
}

# S11-T1 (2026-05-26) — DS-locked Cox PH survival classifier thresholds.
# Same shape as bgnbd / gamma_gamma blocks: per-stage cell +
# relaxation factors. Mature cell is the fallback when YAML is missing or
# stage cell not found.
_FALLBACK_SURVIVAL_STAGE_CELL = {
    "months_data_validated": 6,
    "repeat_customers_validated": 500,
    "censored_events_validated": 100,
    "holdout_c_index_validated": 0.63,
    "holdout_brier_score_90d_validated_max": 0.25,
}
_FALLBACK_SURVIVAL_RELAXATION = {
    "provisional_n_multiplier": 0.5,
    "provisional_c_index_floor": 0.55,
    "provisional_brier_score_90d_max": 0.35,
}

# S11-T2 (2026-05-26) — DS-locked CF (implicit ALS) classifier thresholds.
# Per-stage cell + relaxation factors + hyperparameters (ALS factors /
# regularization / iterations, top_k, top_n_lookalikes_per_customer).
# Mature cell is the fallback when YAML is missing or stage cell absent.
_FALLBACK_CF_STAGE_CELL = {
    "min_customers": 200,
    "min_items": 100,
    "min_interactions_per_user": 2,
    "top_k_recall_validated": 0.08,
}
_FALLBACK_CF_RELAXATION = {
    "provisional_n_multiplier": 0.5,
    "provisional_top_k_recall_floor": 0.03,
}
# S12-T1 (2026-05-28) — DS-locked RFM (Recency × Frequency × Monetary)
# segmentation classifier thresholds. PRIMARY gate:
# ``segment_monotonicity_spearman_validated`` per stage. SECONDARY REFUSED
# guard: ``quintile_coverage_min`` below ``refused_quintile_coverage_min``.
# Mature cell is the fallback when YAML is missing or stage cell absent.
_FALLBACK_RFM_STAGE_CELL = {
    "n_customers_validated": 500,
    "segment_monotonicity_spearman_validated": 0.70,
    "quintile_coverage_min_validated": 0.10,
}
_FALLBACK_RFM_RELAXATION = {
    "provisional_n_multiplier": 0.5,
    "provisional_segment_monotonicity_spearman_floor": 0.40,
    "provisional_quintile_coverage_min_floor": 0.05,
}
_FALLBACK_RFM_GUARDS = {
    "absolute_customers_floor": 50,
    "refused_quintile_coverage_min": 0.05,
}

# S12-T2 (2026-05-28) — DS-locked Retention curves cohort-aggregate
# thresholds. PRIMARY gate: ``bootstrap_ci_width_at_month_3`` (≤ stage-
# keyed VALIDATED floor; AND cohort_count ≥ stage floor; AND no
# cumulative-retention monotonicity violation). REFUSED gate: cumulative-
# retention monotonicity violation (DS-mandated; promoted from tertiary
# diagnostic in v1). Retention lives in NEW top-level
# ``EngineRun.cohort_diagnostics`` slot — NOT predictive_models (cohort-
# aggregate, no per-customer ranker artifact). Mature cell is the
# fallback when YAML is missing or stage cell absent.
_FALLBACK_RETENTION_STAGE_CELL = {
    "cohort_count_validated": 12,
    "bootstrap_ci_width_at_month_3_max_validated": 0.15,
}
_FALLBACK_RETENTION_RELAXATION = {
    "provisional_n_multiplier": 0.5,
    "provisional_bootstrap_ci_width_at_month_3_max": 0.35,
}
_FALLBACK_RETENTION_GUARDS = {
    "absolute_cohort_count_floor": 3,
    "bootstrap_iterations": 1000,
    "months_horizon": 12,
    "min_cohort_size_floor": 20,
    "cumulative_retention_monotonicity_violation_refused": True,
}

_FALLBACK_CF_HYPERPARAMS = {
    "coverage_at_10_warning_threshold": 0.20,
    "top_k": 10,
    "top_n_lookalikes_per_customer": 20,
    "als_factors": 32,
    "als_regularization": 0.01,
    "als_iterations": 15,
}


def _load_yaml_block(yaml_path: Optional[Path] = None) -> Dict[str, Any]:
    """Read ``config/gate_calibration.yaml`` and return the parsed dict.

    Returns ``{}`` if the file is missing (callers fall back to the
    hardcoded ``mature`` cell). Not cached — the threshold loader is
    invoked per-store at engine start, not in tight loops.
    """

    target = Path(yaml_path) if yaml_path is not None else _GATE_CAL_PATH
    if not target.exists():
        return {}
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _broader_stage(stage: str) -> Optional[str]:
    """Next-smaller stage for the HIGH-uncertainty broadening rule.

    Mirrors ``src/profile/builder.py::_broader_stage``. Returns ``None``
    when already at the smallest stage (``startup``).
    """

    s = str(stage).strip().lower()
    if s not in _STAGE_ORDER:
        return None
    idx = _STAGE_ORDER.index(s)
    if idx == 0:
        return None
    return _STAGE_ORDER[idx - 1]


def _load_model_fit_thresholds(
    profile: Any,
    *,
    yaml_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Resolve the business-stage-keyed ML-fit threshold dict.

    Lookup precedence (most-specific wins):

    1. Resolve ``stage = profile.business_stage.stage`` (case-insensitive)
       → read ``model_fit_thresholds.bgnbd.by_business_stage[stage]``.
    2. For ``months_data_validated`` only: if
       ``by_vertical_months_override[profile.taxonomy.vertical]`` exists,
       **replace** the stage cell's months value.
    3. If ``profile.business_stage.uncertainty == "HIGH"`` apply the
       stage-uncertainty broadening rule (read the next-smaller stage's
       cell). Mirrors ``derive_gate_calibration``.
    4. Flag-OFF / ``profile is None`` / YAML missing → hardcoded
       ``mature`` cell.

    Returns a dict with the shape::

        {
            "bgnbd": {
                "months_data_validated": int,
                "repeat_customers_validated": int,
                "orders_validated": int,
                "holdout_mape_validated": float,
            },
            "relaxation_factors": {
                "provisional_n_multiplier": float,
                "provisional_mape_addend": float,
            },
            "gamma_gamma": {
                "independence_pearson_r_validated": float,
                "independence_pearson_r_provisional": float,
            },
            "resolved_stage": str,        # the stage actually consulted
            "vertical_override_applied": bool,
        }
    """

    yaml_block = _load_yaml_block(yaml_path)
    mft = (yaml_block.get("model_fit_thresholds") or {}) if isinstance(yaml_block, dict) else {}
    bgnbd_block = (mft.get("bgnbd") or {}) if isinstance(mft, dict) else {}
    by_stage = bgnbd_block.get("by_business_stage") or {}
    by_vertical = bgnbd_block.get("by_vertical_months_override") or {}
    relax = bgnbd_block.get("relaxation_factors") or {}
    gg = (mft.get("gamma_gamma") or {}) if isinstance(mft, dict) else {}

    # --- Resolve stage cell ---
    stage_key: Optional[str] = None
    vertical: Optional[str] = None
    uncertainty: str = "LOW"

    if profile is not None:
        try:
            stage_attr = getattr(profile.business_stage, "stage", None)
            if stage_attr:
                stage_key = str(stage_attr).strip().lower()
            uncertainty = str(
                getattr(profile.business_stage, "uncertainty", "LOW") or "LOW"
            ).strip().upper()
        except AttributeError:
            stage_key = None
        try:
            v = getattr(profile.taxonomy, "vertical", None)
            if v:
                vertical = str(v).strip().lower()
        except AttributeError:
            vertical = None

    # Stage-uncertainty broadening (DS architect §2.3 pattern).
    resolved_stage = stage_key
    if stage_key and uncertainty == "HIGH":
        broader = _broader_stage(stage_key)
        if broader is not None:
            resolved_stage = broader

    # Read stage cell from YAML; fall back if missing.
    cell: Optional[Dict[str, Any]] = None
    if resolved_stage and isinstance(by_stage, dict):
        raw = by_stage.get(resolved_stage)
        if isinstance(raw, dict):
            cell = dict(raw)

    if cell is None:
        cell = dict(_FALLBACK_MATURE_BGNBD)
        resolved_stage = resolved_stage or "mature"

    # Vertical override on months_data_validated only.
    vertical_override_applied = False
    if vertical and isinstance(by_vertical, dict):
        override_months = by_vertical.get(vertical)
        if override_months is not None:
            try:
                cell["months_data_validated"] = int(override_months)
                vertical_override_applied = True
            except (TypeError, ValueError):
                pass

    # Normalize types.
    bgnbd_out = {
        "months_data_validated": int(cell.get("months_data_validated", 6)),
        "repeat_customers_validated": int(cell.get("repeat_customers_validated", 500)),
        "orders_validated": int(cell.get("orders_validated", 1500)),
        # T1.4 (2026-05-26): MAPE retained as diagnostic only (DS-deprecated
        # from gating); Spearman is the primary gating threshold.
        "holdout_mape_validated": float(cell.get("holdout_mape_validated", 0.25)),
        "holdout_rank_spearman_validated": float(
            cell.get("holdout_rank_spearman_validated", 0.20)
        ),
    }

    relax_out = {
        "provisional_n_multiplier": float(
            relax.get("provisional_n_multiplier", _FALLBACK_RELAXATION["provisional_n_multiplier"])
        ),
        # provisional_mape_addend retained read-side for legacy fixtures; not
        # consumed by the Spearman-gated classifier.
        "provisional_mape_addend": float(
            relax.get("provisional_mape_addend", _FALLBACK_RELAXATION["provisional_mape_addend"])
        ),
        "provisional_rank_spearman_floor": float(
            relax.get(
                "provisional_rank_spearman_floor",
                _FALLBACK_RELAXATION["provisional_rank_spearman_floor"],
            )
        ),
    }

    # ---- Gamma-Gamma stage cell + relaxation + independence (S10-T2) ----
    # YAML shape (per ``config/gate_calibration.yaml::model_fit_thresholds.gamma_gamma``):
    #   gamma_gamma:
    #     by_business_stage:
    #       <stage>: {repeat_customers_validated, holdout_rank_spearman_validated,
    #                 agg_ratio_min, agg_ratio_max}
    #     relaxation_factors:
    #       provisional_rank_spearman_floor, provisional_agg_ratio_min,
    #       provisional_agg_ratio_max
    #     independence_check:
    #       pearson_r_violation_threshold
    # Legacy ``independence_pearson_r_validated`` / ``_provisional`` keys
    # are read-only retained for back-compat with pre-T2 fixtures.
    gg_by_stage = gg.get("by_business_stage") or {}
    gg_relax = gg.get("relaxation_factors") or {}
    gg_indep = gg.get("independence_check") or {}

    gg_cell: Optional[Dict[str, Any]] = None
    if resolved_stage and isinstance(gg_by_stage, dict):
        raw = gg_by_stage.get(resolved_stage)
        if isinstance(raw, dict):
            gg_cell = dict(raw)
    if gg_cell is None:
        gg_cell = dict(_FALLBACK_GAMMA_GAMMA_STAGE_CELL)

    gg_out = {
        # Legacy independence cutoffs (back-compat read; advisory only).
        "independence_pearson_r_validated": float(
            gg.get(
                "independence_pearson_r_validated",
                _FALLBACK_GAMMA_GAMMA["independence_pearson_r_validated"],
            )
        ),
        "independence_pearson_r_provisional": float(
            gg.get(
                "independence_pearson_r_provisional",
                _FALLBACK_GAMMA_GAMMA["independence_pearson_r_provisional"],
            )
        ),
        # S10-T2 DS-locked thresholds.
        "repeat_customers_validated": int(
            gg_cell.get(
                "repeat_customers_validated",
                _FALLBACK_GAMMA_GAMMA_STAGE_CELL["repeat_customers_validated"],
            )
        ),
        "holdout_rank_spearman_validated": float(
            gg_cell.get(
                "holdout_rank_spearman_validated",
                _FALLBACK_GAMMA_GAMMA_STAGE_CELL["holdout_rank_spearman_validated"],
            )
        ),
        "agg_ratio_min": float(
            gg_cell.get(
                "agg_ratio_min", _FALLBACK_GAMMA_GAMMA_STAGE_CELL["agg_ratio_min"]
            )
        ),
        "agg_ratio_max": float(
            gg_cell.get(
                "agg_ratio_max", _FALLBACK_GAMMA_GAMMA_STAGE_CELL["agg_ratio_max"]
            )
        ),
    }

    gg_relax_out = {
        "provisional_rank_spearman_floor": float(
            gg_relax.get(
                "provisional_rank_spearman_floor",
                _FALLBACK_GAMMA_GAMMA_RELAXATION["provisional_rank_spearman_floor"],
            )
        ),
        "provisional_agg_ratio_min": float(
            gg_relax.get(
                "provisional_agg_ratio_min",
                _FALLBACK_GAMMA_GAMMA_RELAXATION["provisional_agg_ratio_min"],
            )
        ),
        "provisional_agg_ratio_max": float(
            gg_relax.get(
                "provisional_agg_ratio_max",
                _FALLBACK_GAMMA_GAMMA_RELAXATION["provisional_agg_ratio_max"],
            )
        ),
    }

    gg_indep_out = {
        "pearson_r_violation_threshold": float(
            gg_indep.get(
                "pearson_r_violation_threshold",
                _FALLBACK_GAMMA_GAMMA_INDEPENDENCE["pearson_r_violation_threshold"],
            )
        ),
    }

    # ---- Survival stage cell + relaxation (S11-T1) ----
    # YAML shape (per ``config/gate_calibration.yaml::model_fit_thresholds.survival``):
    #   survival:
    #     by_business_stage:
    #       <stage>: {months_data_validated, repeat_customers_validated,
    #                 censored_events_validated, holdout_c_index_validated,
    #                 holdout_brier_score_90d_validated_max}
    #     relaxation_factors:
    #       provisional_n_multiplier, provisional_c_index_floor,
    #       provisional_brier_score_90d_max
    surv = (mft.get("survival") or {}) if isinstance(mft, dict) else {}
    surv_by_stage = surv.get("by_business_stage") or {}
    surv_relax = surv.get("relaxation_factors") or {}

    surv_cell: Optional[Dict[str, Any]] = None
    if resolved_stage and isinstance(surv_by_stage, dict):
        raw = surv_by_stage.get(resolved_stage)
        if isinstance(raw, dict):
            surv_cell = dict(raw)
    if surv_cell is None:
        surv_cell = dict(_FALLBACK_SURVIVAL_STAGE_CELL)

    surv_out = {
        "months_data_validated": int(
            surv_cell.get(
                "months_data_validated",
                _FALLBACK_SURVIVAL_STAGE_CELL["months_data_validated"],
            )
        ),
        "repeat_customers_validated": int(
            surv_cell.get(
                "repeat_customers_validated",
                _FALLBACK_SURVIVAL_STAGE_CELL["repeat_customers_validated"],
            )
        ),
        "censored_events_validated": int(
            surv_cell.get(
                "censored_events_validated",
                _FALLBACK_SURVIVAL_STAGE_CELL["censored_events_validated"],
            )
        ),
        "holdout_c_index_validated": float(
            surv_cell.get(
                "holdout_c_index_validated",
                _FALLBACK_SURVIVAL_STAGE_CELL["holdout_c_index_validated"],
            )
        ),
        "holdout_brier_score_90d_validated_max": float(
            surv_cell.get(
                "holdout_brier_score_90d_validated_max",
                _FALLBACK_SURVIVAL_STAGE_CELL["holdout_brier_score_90d_validated_max"],
            )
        ),
    }

    surv_relax_out = {
        "provisional_n_multiplier": float(
            surv_relax.get(
                "provisional_n_multiplier",
                _FALLBACK_SURVIVAL_RELAXATION["provisional_n_multiplier"],
            )
        ),
        "provisional_c_index_floor": float(
            surv_relax.get(
                "provisional_c_index_floor",
                _FALLBACK_SURVIVAL_RELAXATION["provisional_c_index_floor"],
            )
        ),
        "provisional_brier_score_90d_max": float(
            surv_relax.get(
                "provisional_brier_score_90d_max",
                _FALLBACK_SURVIVAL_RELAXATION["provisional_brier_score_90d_max"],
            )
        ),
    }

    # ---- CF stage cell + relaxation + hyperparameters (S11-T2) ----
    # YAML shape (per ``config/gate_calibration.yaml::model_fit_thresholds.cf``):
    #   cf:
    #     by_business_stage:
    #       <stage>: {min_customers, min_items, min_interactions_per_user,
    #                 top_k_recall_validated}
    #     relaxation_factors:
    #       provisional_n_multiplier, provisional_top_k_recall_floor
    #     coverage_at_10_warning_threshold, top_k,
    #     top_n_lookalikes_per_customer, als_factors, als_regularization,
    #     als_iterations
    cf = (mft.get("cf") or {}) if isinstance(mft, dict) else {}
    cf_by_stage = cf.get("by_business_stage") or {}
    cf_relax = cf.get("relaxation_factors") or {}

    cf_cell: Optional[Dict[str, Any]] = None
    if resolved_stage and isinstance(cf_by_stage, dict):
        raw = cf_by_stage.get(resolved_stage)
        if isinstance(raw, dict):
            cf_cell = dict(raw)
    if cf_cell is None:
        cf_cell = dict(_FALLBACK_CF_STAGE_CELL)

    cf_out = {
        "min_customers": int(
            cf_cell.get("min_customers", _FALLBACK_CF_STAGE_CELL["min_customers"])
        ),
        "min_items": int(
            cf_cell.get("min_items", _FALLBACK_CF_STAGE_CELL["min_items"])
        ),
        "min_interactions_per_user": int(
            cf_cell.get(
                "min_interactions_per_user",
                _FALLBACK_CF_STAGE_CELL["min_interactions_per_user"],
            )
        ),
        "top_k_recall_validated": float(
            cf_cell.get(
                "top_k_recall_validated",
                _FALLBACK_CF_STAGE_CELL["top_k_recall_validated"],
            )
        ),
    }

    cf_relax_out = {
        "provisional_n_multiplier": float(
            cf_relax.get(
                "provisional_n_multiplier",
                _FALLBACK_CF_RELAXATION["provisional_n_multiplier"],
            )
        ),
        "provisional_top_k_recall_floor": float(
            cf_relax.get(
                "provisional_top_k_recall_floor",
                _FALLBACK_CF_RELAXATION["provisional_top_k_recall_floor"],
            )
        ),
    }

    cf_hyper_out = {
        "coverage_at_10_warning_threshold": float(
            cf.get(
                "coverage_at_10_warning_threshold",
                _FALLBACK_CF_HYPERPARAMS["coverage_at_10_warning_threshold"],
            )
        ),
        "top_k": int(cf.get("top_k", _FALLBACK_CF_HYPERPARAMS["top_k"])),
        "top_n_lookalikes_per_customer": int(
            cf.get(
                "top_n_lookalikes_per_customer",
                _FALLBACK_CF_HYPERPARAMS["top_n_lookalikes_per_customer"],
            )
        ),
        "als_factors": int(
            cf.get("als_factors", _FALLBACK_CF_HYPERPARAMS["als_factors"])
        ),
        "als_regularization": float(
            cf.get(
                "als_regularization",
                _FALLBACK_CF_HYPERPARAMS["als_regularization"],
            )
        ),
        "als_iterations": int(
            cf.get("als_iterations", _FALLBACK_CF_HYPERPARAMS["als_iterations"])
        ),
    }

    # ---- RFM stage cell + relaxation + guards (S12-T1) ----
    # YAML shape (per ``config/gate_calibration.yaml::model_fit_thresholds.rfm``):
    #   rfm:
    #     by_business_stage:
    #       <stage>: {n_customers_validated,
    #                 segment_monotonicity_spearman_validated,
    #                 quintile_coverage_min_validated}
    #     relaxation_factors:
    #       provisional_n_multiplier,
    #       provisional_segment_monotonicity_spearman_floor,
    #       provisional_quintile_coverage_min_floor
    #     absolute_customers_floor, refused_quintile_coverage_min
    rfm = (mft.get("rfm") or {}) if isinstance(mft, dict) else {}
    rfm_by_stage = rfm.get("by_business_stage") or {}
    rfm_relax = rfm.get("relaxation_factors") or {}

    rfm_cell: Optional[Dict[str, Any]] = None
    if resolved_stage and isinstance(rfm_by_stage, dict):
        raw = rfm_by_stage.get(resolved_stage)
        if isinstance(raw, dict):
            rfm_cell = dict(raw)
    if rfm_cell is None:
        rfm_cell = dict(_FALLBACK_RFM_STAGE_CELL)

    rfm_out = {
        "n_customers_validated": int(
            rfm_cell.get(
                "n_customers_validated",
                _FALLBACK_RFM_STAGE_CELL["n_customers_validated"],
            )
        ),
        "segment_monotonicity_spearman_validated": float(
            rfm_cell.get(
                "segment_monotonicity_spearman_validated",
                _FALLBACK_RFM_STAGE_CELL["segment_monotonicity_spearman_validated"],
            )
        ),
        "quintile_coverage_min_validated": float(
            rfm_cell.get(
                "quintile_coverage_min_validated",
                _FALLBACK_RFM_STAGE_CELL["quintile_coverage_min_validated"],
            )
        ),
    }

    rfm_relax_out = {
        "provisional_n_multiplier": float(
            rfm_relax.get(
                "provisional_n_multiplier",
                _FALLBACK_RFM_RELAXATION["provisional_n_multiplier"],
            )
        ),
        "provisional_segment_monotonicity_spearman_floor": float(
            rfm_relax.get(
                "provisional_segment_monotonicity_spearman_floor",
                _FALLBACK_RFM_RELAXATION[
                    "provisional_segment_monotonicity_spearman_floor"
                ],
            )
        ),
        "provisional_quintile_coverage_min_floor": float(
            rfm_relax.get(
                "provisional_quintile_coverage_min_floor",
                _FALLBACK_RFM_RELAXATION["provisional_quintile_coverage_min_floor"],
            )
        ),
    }

    rfm_guards_out = {
        "absolute_customers_floor": int(
            rfm.get(
                "absolute_customers_floor",
                _FALLBACK_RFM_GUARDS["absolute_customers_floor"],
            )
        ),
        "refused_quintile_coverage_min": float(
            rfm.get(
                "refused_quintile_coverage_min",
                _FALLBACK_RFM_GUARDS["refused_quintile_coverage_min"],
            )
        ),
    }

    # ---- Retention stage cell + relaxation + guards (S12-T2) ----
    # YAML shape (per ``config/gate_calibration.yaml::model_fit_thresholds.retention``):
    #   retention:
    #     by_business_stage:
    #       <stage>: {cohort_count_validated,
    #                 bootstrap_ci_width_at_month_3_max_validated}
    #     relaxation_factors:
    #       provisional_n_multiplier,
    #       provisional_bootstrap_ci_width_at_month_3_max
    #     absolute_cohort_count_floor, bootstrap_iterations,
    #     months_horizon, min_cohort_size_floor,
    #     cumulative_retention_monotonicity_violation_refused
    retention = (mft.get("retention") or {}) if isinstance(mft, dict) else {}
    retention_by_stage = retention.get("by_business_stage") or {}
    retention_relax = retention.get("relaxation_factors") or {}

    retention_cell: Optional[Dict[str, Any]] = None
    if resolved_stage and isinstance(retention_by_stage, dict):
        raw = retention_by_stage.get(resolved_stage)
        if isinstance(raw, dict):
            retention_cell = dict(raw)
    if retention_cell is None:
        retention_cell = dict(_FALLBACK_RETENTION_STAGE_CELL)

    retention_out = {
        "cohort_count_validated": int(
            retention_cell.get(
                "cohort_count_validated",
                _FALLBACK_RETENTION_STAGE_CELL["cohort_count_validated"],
            )
        ),
        "bootstrap_ci_width_at_month_3_max_validated": float(
            retention_cell.get(
                "bootstrap_ci_width_at_month_3_max_validated",
                _FALLBACK_RETENTION_STAGE_CELL[
                    "bootstrap_ci_width_at_month_3_max_validated"
                ],
            )
        ),
    }

    retention_relax_out = {
        "provisional_n_multiplier": float(
            retention_relax.get(
                "provisional_n_multiplier",
                _FALLBACK_RETENTION_RELAXATION["provisional_n_multiplier"],
            )
        ),
        "provisional_bootstrap_ci_width_at_month_3_max": float(
            retention_relax.get(
                "provisional_bootstrap_ci_width_at_month_3_max",
                _FALLBACK_RETENTION_RELAXATION[
                    "provisional_bootstrap_ci_width_at_month_3_max"
                ],
            )
        ),
    }

    retention_guards_out = {
        "absolute_cohort_count_floor": int(
            retention.get(
                "absolute_cohort_count_floor",
                _FALLBACK_RETENTION_GUARDS["absolute_cohort_count_floor"],
            )
        ),
        "bootstrap_iterations": int(
            retention.get(
                "bootstrap_iterations",
                _FALLBACK_RETENTION_GUARDS["bootstrap_iterations"],
            )
        ),
        "months_horizon": int(
            retention.get(
                "months_horizon", _FALLBACK_RETENTION_GUARDS["months_horizon"]
            )
        ),
        "min_cohort_size_floor": int(
            retention.get(
                "min_cohort_size_floor",
                _FALLBACK_RETENTION_GUARDS["min_cohort_size_floor"],
            )
        ),
        "cumulative_retention_monotonicity_violation_refused": bool(
            retention.get(
                "cumulative_retention_monotonicity_violation_refused",
                _FALLBACK_RETENTION_GUARDS[
                    "cumulative_retention_monotonicity_violation_refused"
                ],
            )
        ),
    }

    return {
        "bgnbd": bgnbd_out,
        "relaxation_factors": relax_out,
        "gamma_gamma": gg_out,
        "gamma_gamma_relaxation_factors": gg_relax_out,
        "gamma_gamma_independence_check": gg_indep_out,
        "survival": surv_out,
        "survival_relaxation_factors": surv_relax_out,
        "cf": cf_out,
        "cf_relaxation_factors": cf_relax_out,
        "cf_hyperparameters": cf_hyper_out,
        "rfm": rfm_out,
        "rfm_relaxation_factors": rfm_relax_out,
        "rfm_guards": rfm_guards_out,
        "retention": retention_out,
        "retention_relaxation_factors": retention_relax_out,
        "retention_guards": retention_guards_out,
        "resolved_stage": resolved_stage or "mature",
        "vertical_override_applied": vertical_override_applied,
    }


__all__ = [
    "ModelFitStatus",
    "ModelCard",
    "RetentionCard",
    "SegmentBand",
    "RfmSegmentDistributionSuppressionReason",
    "_load_model_fit_thresholds",
]
