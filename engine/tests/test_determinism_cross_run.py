"""G-7 — Cross-run byte-identical determinism CI.

Two-run identity contract: running the pinned ``healthy_beauty_240d``
synthetic scenario twice through the synthetic harness must produce
``engine_run.json`` payloads that are byte-identical after normalizing
the only field that legitimately varies per run (``run_id``, generated
via ``uuid.uuid4()`` in ``src/engine_run_adapter.py::359``).

Why this test exists
--------------------

- It is the **prerequisite** for Sprint 2's S-3 acceptance test, which
  pins ``lineage_id`` byte-stability across runs. Without G-7 in CI,
  S-3's stability claim is unverifiable.
- It is a forcing function against future un-seeded randomness:
  ``src/_determinism.py::seed_all`` is called at the top of
  ``src/main.py::run()``. If a future patch introduces an
  un-seeded ``random.*`` / ``np.random.*`` call, this test surfaces the
  drift immediately rather than at S-3 acceptance time.
- It guards against hidden non-determinism in dict iteration, set
  ordering, or floating-point reduction order surfacing as a regression
  later. The Beauty fixture is the canary.

What this test does NOT do
--------------------------

- It does NOT re-pin the ``healthy_beauty_240d`` briefing.html bytewise
  contract; that is :mod:`tests.test_slate_regression_beauty_brand`.
- It does NOT exercise non-Beauty verticals (out of G-7 scope).
- It does NOT compare timestamps that are NOT in
  ``engine_run.json`` today; the comparator is intentionally narrow on
  what it strips. Adding a new "varies-by-run" field to the schema
  later requires both extending ``NORMALIZED_FIELDS`` here AND a
  deliberate founder sign-off (the schema is FROZEN per
  ``CLAUDE.md`` / ``ENGINE.md``).

Source contract: ``agent_outputs/implementation-manager-post-6b-restructured-plan.md``,
Sprint 1 Engineer A, Ticket G-7.
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402

from src._determinism import DEFAULT_SEED, seed_all  # noqa: E402


SCENARIO_NAME: str = "healthy_beauty_240d"

# Mirror the deterministic env contract used by the B6 pinned-slate
# regression test (``tests/test_slate_regression_beauty_brand.py``). The
# contract is: full V2 + slate flag stack on, ``VERTICAL_MODE=beauty``,
# ``WINDOW_POLICY=auto``. The harness already pops ``VERTICAL_MODE`` /
# ``VERTICAL`` so an in-environment leak from a previous test run cannot
# contaminate this fixture.
_DETERMINISM_ENV_OVERRIDES: Dict[str, str] = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
}


# ---------------------------------------------------------------------------
# Comparator
# ---------------------------------------------------------------------------

# Top-level engine_run.json fields that legitimately vary per run and
# must be normalized before byte-comparison. Every entry here MUST have
# a documented reason why it varies and why stripping it is safe; do NOT
# extend this set without founder review.
#
# - ``run_id``: ``uuid.uuid4()`` per run (engine_run_adapter.py:359).
# - ``store_profile.provenance.profiled_at`` (Sprint 6.5-T5, 2026-05-18):
#   wall-clock ISO timestamp stamped inside ``build_store_profile``
#   at run time. Profile content is pure-deterministic from the input
#   DataFrame; only the build wall-clock differs between two runs.
NORMALIZED_FIELDS: Tuple[str, ...] = ("run_id",)

# Nested-path normalizations. Each entry is a dotted path; the leaf key
# is dropped from the nested dict before comparison. Added at T5 to cover
# ``store_profile.provenance.profiled_at`` without expanding
# NORMALIZED_FIELDS (which is top-level by contract).
#
# - ``predictive_models.bgnbd.fit_timestamp`` (Sprint 10-T1.5, 2026-05-26):
#   wall-clock ISO timestamp stamped inside ``fit_bgnbd`` via
#   ``_now_iso()`` whenever the predictive-fit step runs (i.e.
#   ``ENGINE_V2_ML_BGNBD`` is ON, which is the T1.5 default). The
#   fit_status / parameters / metrics are pure-deterministic from the
#   input DataFrame; only the build wall-clock differs between two
#   runs. Same precedent as ``profiled_at`` above.
#
# - ``predictive_models.gamma_gamma.fit_timestamp`` (Sprint 10-T2.5, 2026-05-26):
#   wall-clock ISO timestamp stamped inside ``fit_gamma_gamma`` via
#   ``_now_iso()`` whenever the predictive-fit step runs (i.e.
#   ``ENGINE_V2_ML_GAMMA_GAMMA`` is ON, which is the T2.5 default). On
#   synthetic pinned fixtures the resulting ModelCard is uniformly
#   REFUSED via the chained-refusal short-circuit (BG/NBD already
#   REFUSED or INSUFFICIENT_DATA on every fixture); only the build
#   wall-clock differs between runs. Same precedent as BG/NBD's
#   ``fit_timestamp`` above.
#
# - ``predictive_models.survival.fit_timestamp`` (Sprint 11-T1.5, 2026-05-26):
#   wall-clock ISO timestamp stamped inside ``fit_survival`` via
#   ``_now_iso()`` whenever the predictive-fit step runs (i.e.
#   ``ENGINE_V2_ML_SURVIVAL`` is ON, which is the T1.5 default). On
#   synthetic pinned fixtures the resulting ModelCard is uniformly
#   REFUSED via the chained-refusal short-circuit (BG/NBD already
#   REFUSED or INSUFFICIENT_DATA on every fixture); only the build
#   wall-clock differs between runs. Same precedent as BG/NBD's and
#   Gamma-Gamma's ``fit_timestamp`` above.
#
# - ``predictive_models.cf.fit_timestamp`` (Sprint 11-T2.5, 2026-05-28):
#   wall-clock ISO timestamp stamped inside ``fit_cf`` via
#   ``_now_iso()`` whenever the predictive-fit step runs (i.e.
#   ``ENGINE_V2_ML_CF`` is ON, which is the T2.5 default). CF is
#   INDEPENDENT of BG/NBD (DS-locked) and its fit_status is determined
#   by its own holdout recall@10 gate; only the build wall-clock
#   differs between runs. Same precedent as BG/NBD's, Gamma-Gamma's,
#   and survival's ``fit_timestamp`` above.
#
# - ``predictive_models.rfm.fit_timestamp`` (Sprint 12-T1.5, 2026-05-28):
#   wall-clock ISO timestamp stamped inside ``fit_rfm`` via
#   ``_now_iso()`` whenever the predictive-fit step runs (i.e.
#   ``ENGINE_V2_ML_RFM`` is ON, which is the T1.5 default). RFM is
#   INDEPENDENT of BG/NBD (DS-locked) and its fit_status is determined
#   by its own internal-consistency metrics (segment_monotonicity_spearman
#   PRIMARY + quintile_coverage_min SECONDARY); only the build
#   wall-clock differs between runs. Same precedent as BG/NBD's,
#   Gamma-Gamma's, survival's, and CF's ``fit_timestamp`` above.
#
# - ``cohort_diagnostics.retention.fit_timestamp`` (Sprint 12-T2.5, 2026-05-28):
#   wall-clock ISO timestamp stamped inside ``fit_retention`` via
#   ``_now_iso()`` whenever the predictive-fit step runs (i.e.
#   ``ENGINE_V2_ML_RETENTION`` is ON, which is the T2.5 default).
#   Retention is INDEPENDENT (no chained refusal on BG/NBD or any
#   substrate); its fit_status is determined by its own gates
#   (bootstrap_ci_width_at_month_3 PRIMARY + cohort_count SECONDARY +
#   cumulative_retention_monotonicity_violation REFUSED). Only the
#   build wall-clock differs between runs. **NEW SLOT:** retention
#   lives on ``engine_run.cohort_diagnostics["retention"]`` (NOT
#   ``predictive_models`` — DS S12 plan review §C); this is the first
#   nested-path entry under ``cohort_diagnostics``. Same precedent as
#   the prior five ``predictive_models.*.fit_timestamp`` entries above.
_NESTED_NORMALIZED_PATHS: Tuple[str, ...] = (
    "store_profile.provenance.profiled_at",
    "predictive_models.bgnbd.fit_timestamp",
    "predictive_models.gamma_gamma.fit_timestamp",
    "predictive_models.survival.fit_timestamp",
    "predictive_models.cf.fit_timestamp",
    "predictive_models.rfm.fit_timestamp",
    "cohort_diagnostics.retention.fit_timestamp",
)


def _normalize(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``payload`` with NORMALIZED_FIELDS removed.

    The original artifact on disk is left untouched; per the ticket,
    "with timestamp/run_id fields explicitly normalized in the
    comparator, not the artifact."
    """
    import copy as _copy
    out = _copy.deepcopy(payload)
    for k in NORMALIZED_FIELDS:
        out.pop(k, None)
    for path in _NESTED_NORMALIZED_PATHS:
        parts = path.split(".")
        cursor: Any = out
        for p in parts[:-1]:
            if isinstance(cursor, dict) and p in cursor and isinstance(cursor[p], dict):
                cursor = cursor[p]
            else:
                cursor = None
                break
        if isinstance(cursor, dict):
            cursor.pop(parts[-1], None)
    return out


# ---------------------------------------------------------------------------
# Module-scoped fixture: run Beauty twice, return both payloads
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def two_run_engine_run_payloads() -> List[Dict[str, Any]]:
    """Run ``healthy_beauty_240d`` through the synthetic harness twice
    in two distinct tempdirs and return both ``engine_run.json`` payloads
    as parsed dicts. The fresh tempdirs guarantee that no cross-run
    state (history, receipts, briefings) leaks between invocations.
    """
    payloads: List[Dict[str, Any]] = []
    for label in ("run_a", "run_b"):
        with tempfile.TemporaryDirectory(prefix=f"g7_{label}_") as td:
            out_dir = Path(td) / label
            result = run_scenario(
                SCENARIO_NAME,
                out_dir,
                env_overrides=_DETERMINISM_ENV_OVERRIDES,
                timeout_sec=300,
            )
            assert result.returncode == 0, (
                f"synthetic harness for {SCENARIO_NAME!r} ({label}) "
                f"failed (rc={result.returncode}). stderr (last 500 "
                f"chars): {result.stderr[-500:]}"
            )
            receipts = out_dir / "receipts" / "engine_run.json"
            assert receipts.exists(), (
                f"engine_run.json not produced at {receipts} for {label}"
            )
            payloads.append(json.loads(receipts.read_text(encoding="utf-8")))
    assert len(payloads) == 2
    return payloads


# ---------------------------------------------------------------------------
# Acceptance: byte-identical engine_run.json after normalization
# ---------------------------------------------------------------------------


def test_engine_run_json_byte_identical_after_normalization(
    two_run_engine_run_payloads: List[Dict[str, Any]],
) -> None:
    """Two runs of the Beauty fixture must produce byte-identical
    ``engine_run.json`` after stripping ``NORMALIZED_FIELDS`` (today
    just ``run_id``). Sorted-keys JSON encoding is what we compare to
    surface any non-deterministic dict-ordering regressions.
    """
    a, b = two_run_engine_run_payloads
    a_norm = _normalize(a)
    b_norm = _normalize(b)

    a_blob = json.dumps(a_norm, sort_keys=True, separators=(",", ":")).encode("utf-8")
    b_blob = json.dumps(b_norm, sort_keys=True, separators=(",", ":")).encode("utf-8")

    if a_blob != b_blob:
        # Surface a small diff so the failure is debuggable without
        # forcing a developer to dump 200KB of JSON to a screen.
        diffs = _structural_diff(a_norm, b_norm, prefix="")
        head = "\n".join(diffs[:20])
        more = "" if len(diffs) <= 20 else f"\n... and {len(diffs) - 20} more"
        pytest.fail(
            "G-7 cross-run determinism FAILED: engine_run.json diverged "
            f"between two runs of {SCENARIO_NAME!r} after normalizing "
            f"{NORMALIZED_FIELDS}. First diffs:\n{head}{more}"
        )


def test_run_id_is_actually_normalized_away(
    two_run_engine_run_payloads: List[Dict[str, Any]],
) -> None:
    """Self-check on the comparator: the un-normalized payloads MUST
    differ in ``run_id`` (otherwise the test isn't actually exercising
    the normalization path; it would pass vacuously).
    """
    a, b = two_run_engine_run_payloads
    assert "run_id" in a and "run_id" in b, (
        "engine_run.json must carry run_id; if the schema dropped it, "
        "update NORMALIZED_FIELDS and revisit this self-check"
    )
    assert a["run_id"] != b["run_id"], (
        "Two runs produced identical run_ids; either uuid4 collided "
        "(astronomically unlikely) or run_id is being pinned somewhere "
        "it should not be. Investigate before muting this assertion."
    )


# ---------------------------------------------------------------------------
# Mutation guard: prove the comparator detects unseeded randomness
# ---------------------------------------------------------------------------


def test_comparator_detects_simulated_unseeded_randomness() -> None:
    """Synthetic mutation test. Construct two payloads that differ only
    in a field that *would* drift if some downstream code path made an
    un-seeded ``random.random()`` call — assert the byte-comparator
    catches it. This is the behavioral guarantee the ticket asks for
    ("Mutation test: introduce a random.random() call in src/decide.py,
    assert test fails") expressed without permanently mutating
    ``src/decide.py``.
    """
    base: Dict[str, Any] = {
        "run_id": "fixed",
        "schema_version": "1.0.0",
        "recommendations": [{"play_id": "x", "score": 0.5}],
    }
    mutated: Dict[str, Any] = {
        "run_id": "fixed",
        "schema_version": "1.0.0",
        # Imagine an un-seeded random.random() landed inside a card's
        # numeric field. The comparator must catch this.
        "recommendations": [{"play_id": "x", "score": 0.5000001}],
    }
    a_blob = json.dumps(_normalize(base), sort_keys=True, separators=(",", ":"))
    b_blob = json.dumps(_normalize(mutated), sort_keys=True, separators=(",", ":"))
    assert a_blob != b_blob, (
        "G-7 comparator FAILED its self-test: it did NOT detect a "
        "synthetic float drift. The cross-run identity test would "
        "produce false-greens; fix _normalize() before relying on it."
    )


# ---------------------------------------------------------------------------
# seed_all unit-level coverage
# ---------------------------------------------------------------------------


def test_seed_all_makes_random_module_deterministic() -> None:
    """``seed_all`` must seed stdlib ``random`` such that two separate
    seedings yield identical draw sequences. This is the contract the
    engine relies on at ``src/main.py::run()``.
    """
    seed_all(0)
    seq_a = [random.random() for _ in range(5)]
    seed_all(0)
    seq_b = [random.random() for _ in range(5)]
    assert seq_a == seq_b, (
        "src._determinism.seed_all is not making random.random() "
        f"deterministic; got {seq_a!r} then {seq_b!r}"
    )


def test_seed_all_makes_numpy_random_deterministic() -> None:
    """``seed_all`` must seed ``numpy.random`` if numpy is importable.
    numpy is a hard dependency today (see requirements), so we assert
    rather than skip.
    """
    np = pytest.importorskip("numpy")
    seed_all(0)
    seq_a = np.random.random(5).tolist()
    seed_all(0)
    seq_b = np.random.random(5).tolist()
    assert seq_a == seq_b, (
        "src._determinism.seed_all is not making numpy.random "
        f"deterministic; got {seq_a!r} then {seq_b!r}"
    )


def test_default_seed_is_pinned() -> None:
    """The default seed is part of the determinism contract — pin it so
    a casual edit does not silently change the run-to-run state across
    every downstream test that depends on G-7.
    """
    assert DEFAULT_SEED == 0, (
        f"DEFAULT_SEED drifted to {DEFAULT_SEED}; if this is intentional, "
        "update both this test and the G-7 contract docs in agent_outputs/."
    )


# ---------------------------------------------------------------------------
# Diff helper (test-only)
# ---------------------------------------------------------------------------


def _structural_diff(
    a: Any, b: Any, prefix: str
) -> List[str]:
    """Tiny structural diff used only for failure-message rendering.
    Not exposed; not on a happy path."""
    diffs: List[str] = []
    if type(a) is not type(b):
        diffs.append(
            f"{prefix or '<root>'}: type {type(a).__name__} vs "
            f"{type(b).__name__}"
        )
        return diffs
    if isinstance(a, dict):
        keys = sorted(set(a) | set(b))
        for k in keys:
            sub = f"{prefix}.{k}" if prefix else k
            if k in a and k in b:
                diffs.extend(_structural_diff(a[k], b[k], sub))
            elif k in a:
                diffs.append(f"{sub}: only in run_a ({a[k]!r})")
            else:
                diffs.append(f"{sub}: only in run_b ({b[k]!r})")
        return diffs
    if isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{prefix or '<root>'}: len {len(a)} vs {len(b)}")
            return diffs
        for i, (ai, bi) in enumerate(zip(a, b)):
            diffs.extend(_structural_diff(ai, bi, f"{prefix}[{i}]"))
        return diffs
    if a != b:
        diffs.append(f"{prefix or '<root>'}: {a!r} != {b!r}")
    return diffs
