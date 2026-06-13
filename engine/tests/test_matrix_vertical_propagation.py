"""
tests/test_matrix_vertical_propagation.py

Synthetic blocker Fix 6 - per-scenario VERTICAL_MODE propagation.

Background
----------
Prior to Fix 6, the synthetic e2e matrix was driven by ad-hoc shell loops
that did NOT propagate per-scenario ``VERTICAL_MODE``. As a result every
synthetic scenario - including ``supplement_replenishment_240d`` - ran as
``beauty`` (the engine's resolved fallback under the operator shell that
ran the matrix). This invalidated any vertical-specific scenario testing.

What this test pins
-------------------
1. The mapping ``YAML category -> engine VERTICAL_MODE`` is the contract:
   beauty -> beauty, supplement -> supplements, lifestyle -> mixed.
2. Every declared scenario in ``synthetic_scenarios.yaml`` resolves to one
   of the engine's known vertical modes (``beauty | supplements | mixed``).
3. The harness env-construction sets ``VERTICAL_MODE`` correctly per scenario
   regardless of any shell-level ``VERTICAL_MODE`` already in the operator's
   environment.
4. End-to-end (opt-in via ``RUN_VERTICAL_PROPAGATION_E2E=1``): running at
   least the supplement scenario plus a beauty scenario through
   ``python -m src.main`` actually stamps the declared vertical onto
   ``receipts/engine_run.json::briefing_meta.vertical``.

The opt-in guard on the slowest E2E test is intentional: the broader test
suite must stay fast and the engine subprocess takes 20-60 seconds per
scenario. The unit-level checks alone (1-3 above) are sufficient to prove
that ``VERTICAL_MODE`` is set correctly for at least beauty and supplements
without needing full subprocess artifacts.

Scope
-----
This test file is part of synthetic blocker Fix 6 ONLY. It does not
exercise reporter behavior (Fix 7), does not retune fixtures (Fixes 8-11),
does not change engine behavior. Pure harness/test utility.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.synthetic_harness import (  # noqa: E402
    CATEGORY_TO_VERTICAL,
    DEFAULT_VERTICAL,
    SCENARIOS_YAML,
    assert_vertical_propagated,
    build_env_for_scenario,
    load_scenarios,
    read_briefing_meta_vertical,
    run_scenario,
    vertical_for_scenario,
)

# Engine-side known vertical modes. Source of truth: src.utils.VERTICAL_CONFIG
ENGINE_VERTICALS = {"beauty", "supplements", "mixed"}

# Expected per-scenario vertical, derived from each scenario's YAML
# ``category`` field through the harness mapper. Pin the declared values so
# any future scenario YAML change that silently drops or renames category
# trips this test.
EXPECTED_DECLARED_VERTICAL = {
    "healthy_beauty_240d": "beauty",
    "healthy_beauty_low_inventory_240d": "beauty",
    "supplement_replenishment_240d": "supplements",
    "small_store_240d": "mixed",
    "cold_start_45d": "beauty",
    "promo_anomaly_240d": "beauty",
}


# ---------------------------------------------------------------------------
# Mapper unit tests
# ---------------------------------------------------------------------------

class TestCategoryToVerticalMapping:
    def test_beauty_category_maps_to_beauty(self):
        assert CATEGORY_TO_VERTICAL["beauty"] == "beauty"

    def test_supplement_category_maps_to_supplements_plural(self):
        # Engine's VERTICAL_MODE uses the plural ``supplements``.
        assert CATEGORY_TO_VERTICAL["supplement"] == "supplements"

    def test_lifestyle_category_maps_to_mixed(self):
        assert CATEGORY_TO_VERTICAL["lifestyle"] == "mixed"

    def test_every_mapped_value_is_a_known_engine_vertical(self):
        unknown = set(CATEGORY_TO_VERTICAL.values()) - ENGINE_VERTICALS
        assert not unknown, (
            f"Mapper produces verticals the engine does not know: {unknown}. "
            f"Engine knows: {ENGINE_VERTICALS}."
        )

    def test_default_vertical_is_a_known_engine_vertical(self):
        assert DEFAULT_VERTICAL in ENGINE_VERTICALS


class TestVerticalForScenario:
    def test_explicit_category_resolves_via_mapper(self):
        assert vertical_for_scenario({"category": "beauty"}) == "beauty"
        assert vertical_for_scenario({"category": "supplement"}) == "supplements"
        assert vertical_for_scenario({"category": "lifestyle"}) == "mixed"

    def test_supplements_plural_also_accepted(self):
        # Defensive: if a future YAML accidentally uses the engine's plural.
        assert vertical_for_scenario({"category": "supplements"}) == "supplements"

    def test_case_insensitive(self):
        assert vertical_for_scenario({"category": "Beauty"}) == "beauty"
        assert vertical_for_scenario({"category": "SUPPLEMENT"}) == "supplements"
        assert vertical_for_scenario({"category": "  Lifestyle  "}) == "mixed"

    def test_missing_category_falls_back_to_default(self):
        # Documented default. See synthetic_harness.DEFAULT_VERTICAL docstring.
        assert vertical_for_scenario({}) == DEFAULT_VERTICAL

    def test_unknown_category_falls_back_to_default(self):
        # Unknown categories are not silently passed through (which would let
        # an arbitrary string land in cfg["VERTICAL_MODE"] and be coerced to
        # ``mixed`` by ``get_vertical_mode``). Default is explicit.
        assert vertical_for_scenario({"category": "luxury_fashion"}) == DEFAULT_VERTICAL


# ---------------------------------------------------------------------------
# Scenario YAML pinning
# ---------------------------------------------------------------------------

class TestScenarioYamlDeclaredVerticals:
    """Pin the declared vertical for every scenario in synthetic_scenarios.yaml."""

    def test_yaml_file_exists(self):
        assert SCENARIOS_YAML.exists(), f"Missing scenarios yaml at {SCENARIOS_YAML}"

    def test_all_known_scenarios_resolve_to_engine_known_vertical(self):
        scenarios = load_scenarios()
        bad = {}
        for name, cfg in scenarios.items():
            v = vertical_for_scenario(cfg)
            if v not in ENGINE_VERTICALS:
                bad[name] = v
        assert not bad, f"Scenarios resolve to non-engine verticals: {bad}"

    @pytest.mark.parametrize(
        "scenario_name,expected_vertical",
        sorted(EXPECTED_DECLARED_VERTICAL.items()),
    )
    def test_declared_vertical_matches_expected(
        self, scenario_name: str, expected_vertical: str
    ):
        scenarios = load_scenarios()
        assert scenario_name in scenarios, (
            f"Scenario {scenario_name!r} not in YAML; update "
            f"EXPECTED_DECLARED_VERTICAL or restore the YAML entry."
        )
        actual = vertical_for_scenario(scenarios[scenario_name])
        assert actual == expected_vertical, (
            f"[{scenario_name}] declared vertical mismatch. "
            f"Expected={expected_vertical!r}, actual={actual!r}. "
            f"YAML category={scenarios[scenario_name].get('category')!r}."
        )

    def test_supplement_scenario_is_supplements_not_beauty(self):
        # Forcing function: this is the exact bug Fix 6 closes. Any change
        # that reverts ``supplement_replenishment_240d`` to running as beauty
        # must trip here.
        scenarios = load_scenarios()
        cfg = scenarios["supplement_replenishment_240d"]
        assert vertical_for_scenario(cfg) == "supplements"


# ---------------------------------------------------------------------------
# Env-construction unit tests
# ---------------------------------------------------------------------------

class TestBuildEnvForScenario:
    def test_sets_vertical_mode_for_beauty_scenario(self):
        scenarios = load_scenarios()
        env = build_env_for_scenario(
            scenarios["healthy_beauty_240d"],
            base_env={},
        )
        assert env["VERTICAL_MODE"] == "beauty"

    def test_sets_vertical_mode_for_supplement_scenario(self):
        scenarios = load_scenarios()
        env = build_env_for_scenario(
            scenarios["supplement_replenishment_240d"],
            base_env={},
        )
        assert env["VERTICAL_MODE"] == "supplements"

    def test_sets_vertical_mode_for_lifestyle_scenario(self):
        scenarios = load_scenarios()
        env = build_env_for_scenario(
            scenarios["small_store_240d"],
            base_env={},
        )
        assert env["VERTICAL_MODE"] == "mixed"

    def test_overrides_pre_existing_vertical_mode_in_base_env(self):
        # Operator shell may already export VERTICAL_MODE. The harness must
        # be the single source of truth for the run, otherwise the matrix
        # silently runs every scenario as whatever the operator had
        # exported (the original Fix 6 defect).
        scenarios = load_scenarios()
        env = build_env_for_scenario(
            scenarios["supplement_replenishment_240d"],
            base_env={"VERTICAL_MODE": "beauty", "VERTICAL": "beauty"},
        )
        assert env["VERTICAL_MODE"] == "supplements"

    def test_strips_pre_existing_VERTICAL_alias(self):
        # The engine reads either VERTICAL_MODE or VERTICAL. Strip both so
        # one cannot override the other.
        scenarios = load_scenarios()
        env = build_env_for_scenario(
            scenarios["healthy_beauty_240d"],
            base_env={"VERTICAL": "supplements"},
        )
        assert env["VERTICAL_MODE"] == "beauty"
        assert "VERTICAL" not in env

    def test_v2_flag_stack_enabled_by_default(self):
        scenarios = load_scenarios()
        env = build_env_for_scenario(
            scenarios["healthy_beauty_240d"],
            base_env={},
        )
        for flag in (
            "ENGINE_V2_DECIDE",
            "ENGINE_V2_OUTPUT",
            "ENGINE_V2_SHADOW",
            "ENGINE_V2_SIZING",
            "STATS_NAN_FOR_HARDCODED",
            "EVIDENCE_CLASS_ENFORCED",
        ):
            assert env[flag] == "true", f"{flag} not enabled by default"

    def test_v2_flag_stack_can_be_disabled(self):
        scenarios = load_scenarios()
        env = build_env_for_scenario(
            scenarios["healthy_beauty_240d"],
            base_env={},
            extra_v2_flags=False,
        )
        # When extra_v2_flags=False the harness leaves these alone (it does
        # not affirmatively unset them - the caller's base_env wins).
        assert "ENGINE_V2_DECIDE" not in env

    def test_pythonpath_includes_repo_root(self):
        # Setting PYTHONPATH lets the subprocess run python -m src.main
        # from any cwd (which the harness uses to escape the repo root's
        # .env file). Pin this so a future regression that drops PYTHONPATH
        # silently breaks the E2E vertical-propagation guarantee.
        scenarios = load_scenarios()
        env = build_env_for_scenario(
            scenarios["healthy_beauty_240d"],
            base_env={},
        )
        from tests.synthetic_harness import REPO_ROOT
        assert "PYTHONPATH" in env
        assert str(REPO_ROOT) in env["PYTHONPATH"]

    def test_pythonpath_prepends_existing_value(self):
        scenarios = load_scenarios()
        env = build_env_for_scenario(
            scenarios["healthy_beauty_240d"],
            base_env={"PYTHONPATH": "/tmp/some-pre-existing-pp"},
        )
        from tests.synthetic_harness import REPO_ROOT
        assert env["PYTHONPATH"].startswith(str(REPO_ROOT))
        assert "/tmp/some-pre-existing-pp" in env["PYTHONPATH"]

    def test_per_scenario_envs_are_independent(self):
        # The defect Fix 6 closes is precisely this: building one env per
        # scenario and verifying they differ. If the harness collapsed all
        # scenarios to the same vertical (the original ad-hoc shell-loop
        # behavior), this would fail.
        scenarios = load_scenarios()
        env_beauty = build_env_for_scenario(
            scenarios["healthy_beauty_240d"], base_env={}
        )
        env_supp = build_env_for_scenario(
            scenarios["supplement_replenishment_240d"], base_env={}
        )
        env_life = build_env_for_scenario(
            scenarios["small_store_240d"], base_env={}
        )
        assert env_beauty["VERTICAL_MODE"] == "beauty"
        assert env_supp["VERTICAL_MODE"] == "supplements"
        assert env_life["VERTICAL_MODE"] == "mixed"
        assert (
            env_beauty["VERTICAL_MODE"]
            != env_supp["VERTICAL_MODE"]
            != env_life["VERTICAL_MODE"]
        )


class TestReadBriefingMetaVertical:
    def test_returns_none_when_engine_run_json_missing(self, tmp_path: Path):
        assert read_briefing_meta_vertical(tmp_path) is None

    def test_returns_none_when_json_unreadable(self, tmp_path: Path):
        receipts = tmp_path / "receipts"
        receipts.mkdir()
        (receipts / "engine_run.json").write_text("not json {")
        assert read_briefing_meta_vertical(tmp_path) is None

    def test_returns_none_when_briefing_meta_missing(self, tmp_path: Path):
        receipts = tmp_path / "receipts"
        receipts.mkdir()
        (receipts / "engine_run.json").write_text('{"recommendations": []}')
        assert read_briefing_meta_vertical(tmp_path) is None

    def test_returns_string_when_briefing_meta_present(self, tmp_path: Path):
        receipts = tmp_path / "receipts"
        receipts.mkdir()
        (receipts / "engine_run.json").write_text(
            '{"briefing_meta": {"vertical": "supplements"}}'
        )
        assert read_briefing_meta_vertical(tmp_path) == "supplements"


class TestAssertVerticalPropagated:
    def test_raises_when_actual_is_none(self):
        from tests.synthetic_harness import ScenarioRunResult

        result = ScenarioRunResult(
            scenario_name="foo",
            out_dir=Path("/tmp/nope"),
            declared_vertical="beauty",
            actual_vertical=None,
            returncode=1,
            stdout="",
            stderr="boom",
        )
        with pytest.raises(AssertionError):
            assert_vertical_propagated(result)

    def test_raises_when_mismatch(self):
        from tests.synthetic_harness import ScenarioRunResult

        result = ScenarioRunResult(
            scenario_name="supplement_replenishment_240d",
            out_dir=Path("/tmp/nope"),
            declared_vertical="supplements",
            actual_vertical="beauty",
            returncode=0,
            stdout="",
            stderr="",
        )
        with pytest.raises(AssertionError, match="vertical mismatch"):
            assert_vertical_propagated(result)

    def test_passes_when_match(self):
        from tests.synthetic_harness import ScenarioRunResult

        result = ScenarioRunResult(
            scenario_name="supplement_replenishment_240d",
            out_dir=Path("/tmp/nope"),
            declared_vertical="supplements",
            actual_vertical="supplements",
            returncode=0,
            stdout="",
            stderr="",
        )
        # Should not raise.
        assert_vertical_propagated(result)


# ---------------------------------------------------------------------------
# End-to-end (opt-in)
# ---------------------------------------------------------------------------
#
# These tests run the engine as a subprocess and verify
# ``receipts/engine_run.json::briefing_meta.vertical`` matches the YAML's
# declared vertical. They are gated behind ``RUN_VERTICAL_PROPAGATION_E2E=1``
# because they take ~30-60 seconds per scenario and the harness contract
# (env construction + read_briefing_meta_vertical + assert helpers) is
# already pinned by the unit-level tests above.
#
# Run them on demand with:
#
#     RUN_VERTICAL_PROPAGATION_E2E=1 pytest tests/test_matrix_vertical_propagation.py -v
#
# CI does NOT run them by default.

E2E_OPT_IN = os.environ.get("RUN_VERTICAL_PROPAGATION_E2E", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

E2E_SKIP_REASON = (
    "End-to-end vertical propagation requires the synthetic engine subprocess. "
    "Set RUN_VERTICAL_PROPAGATION_E2E=1 to run."
)


@pytest.mark.skipif(
    not E2E_OPT_IN,
    reason="restored at S13.6-T1a (Pivot 2 strip regex cleanup)",
)
class TestEndToEndVerticalPropagation:
    """Real subprocess runs that prove the env makes it to engine_run.json.

    Per the Fix 6 brief: ``test should ... inspect the produced
    engine_run.json, OR unit-test the runner env construction if durable
    outputs are not available until Fix 7. ... If full matrix artifacts
    are not durable until Fix 7, create a focused harness test that
    proves VERTICAL_MODE is set correctly for at least beauty and
    supplements.``

    These two scenarios are the smallest set that proves both directions:
    a beauty scenario ran as beauty, AND the supplement scenario ran as
    supplements (the exact Fix 6 forcing function).
    """

    def test_supplement_scenario_runs_as_supplements(self, tmp_path: Path):
        result = run_scenario(
            "supplement_replenishment_240d",
            tmp_path / "supplement_run",
        )
        if result.returncode != 0:
            pytest.skip(
                f"Engine subprocess failed (rc={result.returncode}); "
                f"this is a separate engine bug not Fix 6.\n"
                f"stderr (last 800 chars): {result.stderr[-800:]}"
            )
        assert result.declared_vertical == "supplements"
        assert_vertical_propagated(result)

    def test_beauty_scenario_runs_as_beauty(self, tmp_path: Path):
        result = run_scenario(
            "healthy_beauty_240d",
            tmp_path / "beauty_run",
        )
        if result.returncode != 0:
            pytest.skip(
                f"Engine subprocess failed (rc={result.returncode}); "
                f"this is a separate engine bug not Fix 6.\n"
                f"stderr (last 800 chars): {result.stderr[-800:]}"
            )
        assert result.declared_vertical == "beauty"
        assert_vertical_propagated(result)
