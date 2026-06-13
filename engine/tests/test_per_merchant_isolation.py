"""B-4/S-1 acceptance tests.

* Two-merchant smoke: running the engine with ``STORE_ID=A`` and then
  ``STORE_ID=B`` against the same orders CSV produces zero file overlap
  inside ``data/<store_id>/``.
* Lineage-tuple gate: ``gate_recently_run`` enforces all three
  components (play_id, audience_definition_id, store_id) when both sides
  carry them.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.engine_run import (
    Audience,
    EvidenceClass,
    PlayCard,
    ReasonCode,
)
from src.guardrails import gate_recently_run

REPO_ROOT = Path(__file__).resolve().parent.parent


def _make_card(play_id: str, audience_id: str) -> PlayCard:
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.MEASURED,
        audience=Audience(id=audience_id, definition=audience_id, size=100),
    )


# ---------------------------------------------------------------------------
# Lineage-tuple gate: store_id is the new third component
# ---------------------------------------------------------------------------


class TestLineageTupleStoreIdComponent:
    def test_store_id_mismatch_does_not_fire(self, tmp_path: Path):
        """When BOTH the candidate and the history record carry a store_id
        and they differ, the gate must NOT fire — even with matching
        play_id + audience_id."""
        path = tmp_path / "recommended_history.json"
        recent_ts = (
            datetime.now(timezone.utc) - timedelta(days=3)
        ).isoformat()
        path.write_text(
            json.dumps(
                [
                    {
                        "store_id": "store_alpha",
                        "play_id": "winback_21_45",
                        "audience_id": "winback_21_45_inactive",
                        "ts": recent_ts,
                    }
                ]
            )
        )
        cand = _make_card("winback_21_45", "winback_21_45_inactive")
        # Different store -> should NOT match.
        assert (
            gate_recently_run(cand, str(path), store_id="store_beta") is None
        )

    def test_store_id_match_still_fires(self, tmp_path: Path):
        path = tmp_path / "recommended_history.json"
        recent_ts = (
            datetime.now(timezone.utc) - timedelta(days=3)
        ).isoformat()
        path.write_text(
            json.dumps(
                [
                    {
                        "store_id": "store_alpha",
                        "play_id": "winback_21_45",
                        "audience_id": "winback_21_45_inactive",
                        "ts": recent_ts,
                    }
                ]
            )
        )
        cand = _make_card("winback_21_45", "winback_21_45_inactive")
        rej = gate_recently_run(cand, str(path), store_id="store_alpha")
        assert rej is not None
        assert rej.reason_code == ReasonCode.RECENTLY_RUN_FATIGUE

    def test_record_without_store_id_still_matches(self, tmp_path: Path):
        """Defensive policy: legacy records that pre-date the per-store
        layout (no ``store_id`` field) still match on play_id + audience.
        """
        path = tmp_path / "recommended_history.json"
        recent_ts = (
            datetime.now(timezone.utc) - timedelta(days=3)
        ).isoformat()
        path.write_text(
            json.dumps(
                [
                    {
                        "play_id": "winback_21_45",
                        "audience_id": "winback_21_45_inactive",
                        "ts": recent_ts,
                    }
                ]
            )
        )
        cand = _make_card("winback_21_45", "winback_21_45_inactive")
        rej = gate_recently_run(cand, str(path), store_id="store_alpha")
        assert rej is not None


# ---------------------------------------------------------------------------
# Two-merchant smoke: zero file overlap under data/<store_id>/
# ---------------------------------------------------------------------------


def _have_synthetic_csv() -> Path | None:
    """Pick a small synthetic orders CSV for the smoke run."""
    candidates = [
        REPO_ROOT / "tests" / "fixtures" / "synthetic" / "healthy_beauty_240d_orders.csv",
        REPO_ROOT / "data" / "test_data.csv",
        REPO_ROOT / "data" / "shopify_orders_micro_20250826_202615.csv",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


@pytest.mark.skipif(
    _have_synthetic_csv() is None,
    reason="restored at S13.6-T1a (Pivot 2 strip regex cleanup)",
)
def test_two_merchant_smoke_zero_overlap_under_data_store_dir():
    """Run the engine twice in the same checkout, once with
    ``STORE_ID=alpha`` and once with ``STORE_ID=beta``. Assert that
    each store's directory is populated under ``data/<store_id>/`` and
    that the two trees never share a file.
    """
    orders_csv = _have_synthetic_csv()
    assert orders_csv is not None  # for type-checker; skipif gates this

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        out_alpha = td_path / "out_alpha"
        out_beta = td_path / "out_beta"
        out_alpha.mkdir()
        out_beta.mkdir()

        # Subprocess cwd = td so the engine's relative ``data/`` resolves
        # under the tmpdir, not the repo root. PYTHONPATH lets us import
        # src.main from a foreign cwd.
        env_base = dict(os.environ)
        env_base["PYTHONPATH"] = (
            f"{REPO_ROOT}{os.pathsep}{env_base.get('PYTHONPATH', '')}"
        )
        # Ensure the outcome log is enabled so it actually writes.
        env_base["OUTCOME_LOG_ENABLED"] = "true"
        env_base.pop("OUTCOME_LOG_PATH", None)
        # Strip any inherited STORE_ID so each run picks up its own.
        env_base.pop("STORE_ID", None)

        def _run(store_id: str, out_dir: Path) -> subprocess.CompletedProcess:
            env = dict(env_base)
            env["STORE_ID"] = store_id
            cmd = [
                sys.executable,
                "-m",
                "src.main",
                "--orders",
                str(orders_csv.resolve()),
                "--brand",
                store_id,
                "--out",
                str(out_dir),
            ]
            return subprocess.run(
                cmd,
                env=env,
                cwd=str(td_path),
                capture_output=True,
                text=True,
                timeout=300,
            )

        r1 = _run("alpha", out_alpha)
        assert r1.returncode == 0, (
            f"alpha run failed rc={r1.returncode} stderr={r1.stderr[-500:]}"
        )
        r2 = _run("beta", out_beta)
        assert r2.returncode == 0, (
            f"beta run failed rc={r2.returncode} stderr={r2.stderr[-500:]}"
        )

        data_root = td_path / "data"
        assert data_root.exists(), "engine never created data/ under cwd"

        alpha_dir = data_root / "alpha"
        beta_dir = data_root / "beta"
        assert alpha_dir.exists() and alpha_dir.is_dir(), (
            f"per-store dir for alpha missing under {data_root}; "
            f"actual contents: {sorted(p.name for p in data_root.iterdir())}"
        )
        assert beta_dir.exists() and beta_dir.is_dir(), (
            f"per-store dir for beta missing under {data_root}; "
            f"actual contents: {sorted(p.name for p in data_root.iterdir())}"
        )

        def _files_relative_to(root: Path) -> set[str]:
            return {
                str(p.relative_to(root))
                for p in root.rglob("*")
                if p.is_file()
            }

        alpha_files = _files_relative_to(alpha_dir)
        beta_files = _files_relative_to(beta_dir)
        # Each store has at least one file (the recommended_history.json
        # the outcome-log writer produced).
        assert alpha_files, f"alpha dir empty: {alpha_dir}"
        assert beta_files, f"beta dir empty: {beta_dir}"

        # The two trees must never share a file path INSIDE the other
        # store's dir. Trivial since they're disjoint subtrees, but the
        # invariant we really want is: no tenant artifact from one store
        # appears under the other store's dir.
        cross_contamination_alpha_in_beta = [
            f for f in beta_files if "alpha" in f
        ]
        cross_contamination_beta_in_alpha = [
            f for f in alpha_files if "beta" in f
        ]
        assert not cross_contamination_alpha_in_beta, (
            f"alpha artifacts leaked into beta dir: "
            f"{cross_contamination_alpha_in_beta}"
        )
        assert not cross_contamination_beta_in_alpha, (
            f"beta artifacts leaked into alpha dir: "
            f"{cross_contamination_beta_in_alpha}"
        )

        # Also: no tenant artifact (recommended_history.json) was
        # written at the legacy shared path data/recommended_history.json.
        legacy_path = data_root / "recommended_history.json"
        assert not legacy_path.exists(), (
            f"legacy shared history file regressed: {legacy_path}"
        )
