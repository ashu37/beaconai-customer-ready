"""Sprint 6 Ticket T1.5 — flag flip pin tests.

S6-T1.5 flipped ``ENGINE_V2_BUILDER_WINBACK_DORMANT`` default OFF -> ON.
Per the fixture probe captured in
``agent_outputs/code-refactor-engineer-s6-t1_5-summary.md``, on the
pinned synthetic fixtures the cohort audience is BELOW the 500 floor
(Beauty=356 customers; supplements=0), so the candidate routes to
``audience_too_small`` via the M3 preliminary_rejection_reason path
and is trimmed by the existing populate_considered_from_candidates
cap. The merchant-facing briefing.html is byte-identical pre/post
flip — both Beauty and supplements pinned briefings render the same
sha256 under flag-OFF and flag-ON.

Per orchestrator decision (2026-05-17, captured in
code-refactor-engineer-s6-t1-summary.md §6 + §11): cohort-below-floor
is the expected branch, NOT a hard-stop. The Klaviyo validated_external
prior activation moment is deferred to whenever a beta brand with
>=500 lapsed repeat-buyers in the 21-45d window runs the engine.

These tests pin:
1. The flag default is ON (commit 4 of S6 sequence).
2. The supplements G-1 ``PINNED_SHA256`` constant in
   ``test_slate_regression_supplements_brand`` is unchanged. (The
   Beauty slate-regression test does not pin a sha256.)
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_t1_5_flag_default_is_on():
    from src import utils

    assert utils.get_config().get("ENGINE_V2_BUILDER_WINBACK_DORMANT") is True


def test_t1_5_supplements_pinned_sha_unchanged():
    """The supplements G-1 fixture sha256 was re-pinned atomically with
    the S7.6-C3 ``ENGINE_V2_AOV_THRESHOLD_FROM_DATA`` default flip from
    OFF to ON (closes Sprint 7.6). Supplements is now routed through the
    explicit ``vertical_excluded_per_b5_248`` seam at
    ``audience_builders.py:969-979`` per ARCHITECTURE_PLAN.md §III B-5
    lines 248 + 257(c). The T1.5 winback_dormant_cohort builder remains
    structurally inert on the supplements fixture in terms of
    recommendations (cohort=0); the new sha reflects the Tier-B set
    surfacing in Considered with typed reasons including the
    vertical-exclusion provenance for AOV bundle. Prior S7.6-FIX sha:
    0903071ee9646a9db24f44c9ae87e29a14873158f88dc4bd2e4ba192c79fc1da.
    Prior S5-T3 sha:
    01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95.
    """
    from tests.test_slate_regression_supplements_brand import PINNED_SHA256

    assert PINNED_SHA256 == (
        "13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344"
    )
