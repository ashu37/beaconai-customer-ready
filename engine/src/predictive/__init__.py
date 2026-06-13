"""Predictive layer (Sprint 10 — ML Part 1; Sprint 11 — ML Part 2; Sprint 12 — RFM/Retention).

The ML predictive layer fits per-merchant probabilistic models
(BG/NBD, Gamma-Gamma, Cox PH survival, implicit ALS collaborative
filtering, RFM segmentation) and emits typed ``ModelCard`` objects
describing fit health. At S10/S11/S12 the layer ships **flag-OFF**
behind ``ENGINE_V2_ML_BGNBD`` / ``ENGINE_V2_ML_GAMMA_GAMMA`` /
``ENGINE_V2_ML_SURVIVAL`` / ``ENGINE_V2_ML_CF`` / ``ENGINE_V2_ML_RFM``;
no PlayCard consumes its output until S13.

CF (S11-T2) is INDEPENDENT of BG/NBD per DS S11 plan review §A.6 — the
user-item co-occurrence signal does not structurally depend on the
gap-time signal that BG/NBD/survival evaluate. ``fit_cf`` takes no
``bgnbd_model_card`` argument and does not chain on BG/NBD; this is a
deliberate architectural divergence from ``fit_survival``.

RFM (S12-T1) is INDEPENDENT of BG/NBD per DS S12 plan review §F — the
deterministic R/F/M quintile substrate has no held-out object and no
gap-time coupling. ``fit_rfm`` takes no ``bgnbd_model_card`` argument
and does not chain on BG/NBD. Validation uses **internal-consistency**
metrics (named-segment-to-realized-LTV Spearman + quintile coverage),
not holdout / fit-quality metrics.

Retention (S12-T2) is INDEPENDENT — no chained refusal on BG/NBD or
any other substrate (mirrors CF + RFM posture). Architecturally
distinct from prior substrates: cohort-aggregate (not per-customer
ranker), lives in NEW top-level ``EngineRun.cohort_diagnostics`` slot
(NOT ``predictive_models``), uses new ``RetentionCard`` dataclass (NOT
``ModelCard``) which REUSES the ``ModelFitStatus`` enum (Option A
vocab-stacking). Validation uses bootstrap CI width at month 3 as the
PRIMARY gate; cumulative-retention monotonicity violation is a REFUSED
condition (DS S12 plan review §C, §G). No parquet artifact — retention
curves are JSON-shaped and live directly in ``cohort_diagnostics``.

See ``model_card.py`` for the four-state ``ModelFitStatus`` vocabulary
and the ``ModelCard`` + ``RetentionCard`` dataclass contracts.
"""
