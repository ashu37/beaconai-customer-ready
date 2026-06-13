# S6.5-T2 — Sub-vertical token classifier + config/subvertical_taxonomy.yaml

**Owner:** code-refactor-engineer (Sprint 6.5, ticket T2)
**Date:** 2026-05-17
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-s6_5-store-profile-layer-plan.md](./implementation-manager-s6_5-store-profile-layer-plan.md) §2 (S6.5-T2)
**Predecessor:** [S6.5-T1](./code-refactor-engineer-s6_5-t1-summary.md)
**Status:** Complete. Flag still default OFF. The 5 pinned fixtures byte-identical (no consumer reads `taxonomy.subvertical` in S6.5 until T4).

---

## 1. Approved scope

Author `config/subvertical_taxonomy.yaml` + implement the revenue-weighted
sub-vertical token classifier (`detect_subvertical`). Wire it into
`detect_taxonomy` so `Taxonomy.subvertical` + `Taxonomy.subvertical_confidence`
populate for every profile whose vertical is `beauty` or `supplements`.
`mixed` / `other_refused` verticals keep `subvertical=None`.

Founder Q1 (2026-05-17): Sephora + iHerb scraped vocabulary is the
source-of-truth. Every cell is tagged `validation_status:
heuristic_unvalidated`.

## 2. Token source URLs + per-cell token counts

`config/subvertical_taxonomy.yaml` — schema_version 1.0.0, validation_status
`heuristic_unvalidated`, last_reviewed 2026-05-17.

| Vertical | Sub-vertical | Source URL (accessed 2026-05-17) | Token count |
|---|---|---|---|
| beauty | skincare | https://www.sephora.com/shop/skincare | 25 |
| beauty | cosmetics | https://www.sephora.com/shop/makeup-cosmetics | 22 |
| beauty | haircare | https://www.sephora.com/shop/hair | 20 |
| beauty | personal_care | https://www.sephora.com/shop/bath-body | 20 |
| supplements | protein | https://www.iherb.com/c/sports-nutrition | 20 |
| supplements | multivitamin | https://www.iherb.com/c/multivitamins | 21 |
| supplements | probiotics | https://www.iherb.com/c/probiotics | 16 |
| supplements | nootropics | https://www.iherb.com/c/brain-cognitive-function | 18 |
| supplements | functional | https://www.iherb.com/c/adaptogens | 20 |

Every cell is ≥15 tokens (hard-stop floor) and carries
`source_authority` + `validation_status: heuristic_unvalidated`. Each
cell additionally lists `excluded_tokens` so misclassifications across
sub-verticals are suppressed (e.g. a "Hair Vitamin" SKU is not pulled
into `multivitamin`).

## 3. Classifier algorithm

`src/profile/builder.py::detect_subvertical` follows DS architect §8.1:

1. Tokenize each product title (lowercase + whitespace-normalize).
2. Per-SKU score per sub-vertical = sum(positive token matches) − sum(excluded token matches).
3. Per-SKU argmax sub-vertical (ties → drop SKU, do not vote).
4. Aggregate revenue-weighted share across SKUs (`net_sales` weights;
   uniform when `net_sales` absent).
5. Confidence:
   - HIGH if leader-share / runner-up-share ≥ 3.0
   - MEDIUM if ≥ 2.0
   - LOW if ≥ 1.3
   - else return `mixed_<vertical>` + LOW confidence
6. Single-leader edge case (only one sub-vertical has positive matches):
   confidence by absolute leader-share (≥50% HIGH, ≥25% MEDIUM, else LOW).

YAML loader: `load_subvertical_taxonomy` caches the parsed YAML on a
module-level singleton keyed on the default path. Pass an explicit path
to bypass the cache (used by tests).

## 4. Plumbing into `detect_taxonomy`

After T1 sets `vertical`, the T2 path:

- Returns `(None, REFUSED)` if vertical is `mixed` / `other_refused`.
- Otherwise calls `detect_subvertical(g, vertical)` and records the
  classification in `provenance.rules_fired` as `subvertical_detected`.
- Classification failures (malformed YAML / missing column) emit
  `subvertical_classification_failed` + fall back to `(None, REFUSED)`.

## 5. Tests

New: `tests/test_s6_5_t2_subvertical_classifier.py` (23 tests).

Coverage:

- **YAML loader (4 tests)**: schema shape, source URLs populated,
  every cell tagged `heuristic_unvalidated` + `source_authority`,
  token count floor ≥15 per cell (hard-stop guard).
- **Per-sub-vertical smoke (9 tests)**: one positive SKU per cell
  classifies HIGH for all 9 sub-verticals.
- **Revenue-weighted gap thresholds (3 tests)**: 4x → HIGH, 2x →
  MEDIUM, 1.125x → `mixed_beauty` LOW.
- **Mixed-vertical + override (4 tests)**: vertical=mixed →
  `subvertical=None`; case-insensitive token match; excluded-token
  suppression (haircare "Hair Oil for Dry Scalp" not personal_care).
- **End-to-end via `build_store_profile` (2 tests)**: Beauty +
  Supplements fixtures populate `taxonomy.subvertical` with at least
  MEDIUM confidence on synthetic single-product cohorts.
- **YAML path pin (1 test)**.

Plus one T1 test updated: `test_detect_taxonomy_subvertical_populated_at_t2`
now asserts `subvertical == "skincare"` with HIGH/MEDIUM confidence
(replaces the T1 `assert subvertical is None` stub).

## 6. Per-fixture probe (founder envelope check)

Run via `src.profile.build_store_profile` on the pinned synthetic fixtures
(features computed by `src.features.compute_features`):

### Beauty pinned slate (`healthy_beauty_240d_orders.csv`, VERTICAL_MODE=beauty)

| Profile field | Value |
|---|---|
| `taxonomy.vertical` | beauty |
| `taxonomy.detected_vertical` | beauty |
| `taxonomy.override_disagrees` | False |
| **`taxonomy.subvertical`** | **skincare** ✓ |
| **`taxonomy.subvertical_confidence`** | **HIGH** ✓ |
| `business_stage.stage` | GROWTH |
| `business_stage.annualized_gmv_usd` | $1,282,092 |
| `business_stage.uncertainty` | LOW |
| `business_model.model` | ONE_TIME_LED |
| `data_depth.n_orders` / `n_customers` | 15133 / 9404 |

**Hard-stop check #2 (Beauty fixture classifies as skincare ≥MEDIUM):
PASSED.**

### Supplements G-1 (`healthy_supplements_240d_orders.csv`, VERTICAL_MODE=supplements)

| Profile field | Value |
|---|---|
| `taxonomy.vertical` | supplements |
| `taxonomy.detected_vertical` | supplements |
| **`taxonomy.subvertical`** | **functional** |
| **`taxonomy.subvertical_confidence`** | **LOW** |
| `business_stage.stage` | STARTUP |
| `business_stage.detected_stage` | STARTUP |
| `business_stage.annualized_gmv_usd` | $496,394 |
| `business_stage.uncertainty` | HIGH (within ±25% of $500K boundary) |
| `business_model.model` | SUBSCRIPTION_LED (`subscription_fraction = 0.97`) |

**Hard-stop check #3 ("Supplements G-1 classifies as mixed_supplements
LOW AND data clearly intended single subvertical"): NOT TRIPPED.** The
fixture classifies as `functional` (LOW confidence) rather than
`mixed_supplements`. The synthetic supplements fixture appears to
contain adaptogen / functional-supplement vocabulary; a LOW confidence
on `functional` is the contract-correct posture (not a hard-stop). T4
will calibrate gate cells for the LOW-confidence path.

### M0 fixtures (small_sm / mid_shopify / micro_coldstart)

No-op at T2: M0 fixtures hit the legacy `ENGINE_V2_SIZING=false` path
and the flag is OFF, so `engine_run.store_profile` is `None` on M0.
Byte-identical.

## 7. Behavior change

**None.** Flag still default OFF (`ENGINE_V2_STORE_PROFILE=false`). No
consumer reads `taxonomy.subvertical` in S6.5 until T4 wires
audience / measurement / decide / sizing. The 5 pinned fixtures are
byte-identical.

## 8. Hard constraints respected

- Schema additive only (`event_version=1` intact; `Taxonomy.subvertical`
  was already defined at T1).
- D-5 / D-6 / D-8 unchanged.
- All 5 pinned fixtures byte-identical under flag OFF.
- Subscription-led slate-ordering: still deferred to S6-T3 per founder
  Q5 (T2 only populates `business_model.model` via T1's emit-only
  detector; T2 does NOT consume it).
- No new runtime dependencies (`yaml` already in `requirements.txt`).

## 9. Commit list

1. `S6.5-T2: subvertical token classifier + config/subvertical_taxonomy.yaml`
2. `Document S6.5-T2 in repo memory.md`
3. (this commit) — `S6.5-T2 summary`

## Backfill from memory.md (migration trim 2026-05-25)

## Sprint 6.5 Ticket T2 closeout (2026-05-17)

**Status:** Complete. Flag still default OFF. Pinned fixtures byte-identical (no consumer reads `taxonomy.subvertical` in S6.5 until T4).

**What shipped:**

- `config/subvertical_taxonomy.yaml` — schema_version 1.0.0, validation_status `heuristic_unvalidated`, last_reviewed 2026-05-17. 9 sub-vertical cells (beauty × {skincare, cosmetics, haircare, personal_care}, supplements × {protein, multivitamin, probiotics, nootropics, functional}). Each cell ≥15 tokens with `tokens`, `excluded_tokens`, `source_authority`, `validation_status` fields. Sources block lists Sephora + iHerb URLs per founder Q1 (2026-05-17).
- `src/profile/builder.py::detect_subvertical(g, vertical, taxonomy_config=None)` — revenue-weighted argmax with 3x / 2x / 1.3x gap thresholds (DS architect §8.1). Per-SKU score = sum(positive token matches) − sum(excluded matches); per-SKU argmax votes; revenue-share aggregation across SKUs; mixed_<vertical>+LOW for sub-1.3x leaders.
- `detect_taxonomy` now calls `detect_subvertical` after vertical is resolved; routes mixed/other_refused verticals to `subvertical=None` REFUSED.
- YAML loader `load_subvertical_taxonomy` caches the parsed dictionary on a module-level singleton (cache bypass via explicit `path` argument; used by tests).

**Tests:** 23 new in `tests/test_s6_5_t2_subvertical_classifier.py`. Coverage: YAML schema + source URLs + 15-token floor + heuristic_unvalidated tag; 9 per-cell smoke tests (HIGH confidence); 3 gap-threshold tests (4x→HIGH, 2x→MEDIUM, 1.125x→mixed_beauty LOW); mixed-vertical + override path; case-insensitive token match; excluded-token suppression (Hair Oil → haircare not personal_care); end-to-end via `build_store_profile`. One T1 test updated to `test_detect_taxonomy_subvertical_populated_at_t2` (was the T2-deferred stub).

**Per-fixture probe (envelope check):**

| Fixture | subvertical | confidence | notes |
|---|---|---|---|
| Beauty pinned slate (VERTICAL_MODE=beauty) | skincare | HIGH | Hard-stop check #2 PASSED |
| Supplements G-1 (VERTICAL_MODE=supplements) | functional | LOW | classifies as functional/adaptogen vocab — NOT mixed_supplements; hard-stop #3 not tripped |
| M0 small_sm / mid_shopify / micro_coldstart | n/a | n/a | Flag OFF → engine_run.store_profile is None |

**Hard-stops (per founder Q1 + handoff):**

- Token-dictionary < 15 unique tokens per cell → NOT TRIPPED (every cell ≥15; min is probiotics with 16; max is skincare with 25).
- Beauty fixture classifies anything other than skincare ≥MEDIUM → NOT TRIPPED (skincare HIGH).
- Supplements G-1 classifies as mixed_supplements LOW AND data clearly intended a single subvertical → NOT TRIPPED (classifies as `functional` LOW, not mixed).
- Pinned fixtures shift bytes → NOT TRIPPED (flag still OFF; no consumer reads subvertical until T4).

**Caveats:**

- `taxonomy.subvertical` is dormant in the engine until T4 wires consumers (audience floors keyed on subvertical + measurement primary_window per subvertical).
- The classifier's 1.3x LOW threshold may need tightening once T4's gate-calibration cells reveal which LOW-confidence routes survive into Recommended Now lanes. Outcome-driven recalibration deferred to S10 (Phase 9 outcome importer).
- Supplements G-1 LOW-confidence `functional` is the contract-correct posture, not a bug. T4 cell calibration for `supplements/functional` × stage will need attention; the synthetic fixture's `functional` classification reflects adaptogen / collagen / sleep / immunity vocabulary in the SKU titles.

**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t2-summary.md](agent_outputs/code-refactor-engineer-s6_5-t2-summary.md)
