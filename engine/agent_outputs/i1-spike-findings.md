# i1-Spike Phase 1 — Design Memo

**Headline verdict:** **FITS-WITH-CAVEATS.** The candidate-registry seam will admit a model-derived audience candidate at `evidence_class=targeting` without an `engine_run.json` schema change, *provided* the engineer routes the affinity output through the existing `bestseller_amplify` slot rather than introducing a new `play_id`. Three caveats below have material risk of forcing a halt on day 1–2 if not handled in the order specified.

**Top two empirical questions for engineer phase:**
1. Does FP-growth on Beauty's 18,933 line items / 10 SKUs at min-support ≥ 0.05 yield ≥ 1 lift-≥2.0 antecedent→consequent pair where the consequent SKU is the top-revenue SKU (so the audience can validly inherit the `bestseller_amplify` allowlist slot)? If not, the prototype has no candidate to wire and the spike is empirically inert even though the seam fits.
2. Does the synthetic candidate produced by the affinity miner pass the `_select_recommended_experiments` gate at `audience_size >= 500` (the metadata floor for `bestseller_amplify` in `config/priors.yaml:117`) without breaking M0 Beauty pinned slate sha256 `dcb45cee...` byte-identity (since the slot is currently occupied — see Caveat C below)?

---

## 1. Candidate-registry seam — exact shape

**The seam is the `Candidate` dataclass at [`src/detect.py:73-109`](src/detect.py).** All Phase 5 candidates flow through it on their way from `detect_candidates(...)` → `main.py:1114` → `_phase5_cands_for_decide` → `decide(..., candidates=...)` → `_select_recommended_experiments(...)`.

**Required fields on the candidate the engineer must produce:**
- `play_id: str` — MUST equal `"bestseller_amplify"` to land in the allowlist (`RECOMMENDED_EXPERIMENT_ALLOWLIST` at `src/decide.py:118`).
- `audience_size: int` — MUST be ≥ 500 (`audience_floor` in `config/priors.yaml:117`).
- `segment_definition: str` — short rule string. This is the *only* surface where the audience definition leaks; it is rendered as the merchant-facing card body and MUST contain no model name, no probability, no score. Example acceptable: `"buyers of SPF 50 Daily Defense Cream who have not bought Vitamin C Brightening Serum"`. Example forbidden: `"FP-growth-derived cohort, lift=3.2, confidence=0.81"`.
- `data_used: List[str]` — internal trace, safe field. Recommended: `["g.lineitem_any", "g.customer_id", "fp_growth_v1"]`. The string `"fp_growth_v1"` is fine here because `data_used` is internal-only (not rendered).
- `preliminary_rejection_reason: Optional[str]` — must be `None` for the candidate to clear `_select_recommended_experiments`'s gate. Inventory-blocked SKUs at the consequent are short-circuited at `src/decide.py:1115`.
- `cold_start: bool` — set False (the affinity rule needs ≥ 90d to be defensible anyway).
- `audience_overlap: Dict[str, float]` — must be populated with Jaccard against the *current* `bestseller_buyers` audience to be < 0.30 (`RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD` at `src/decide.py:125`). Otherwise the role-uniqueness/overlap gate drops it. **This is a real gate** (see Caveat A).

**Forbidden fields (FORBIDDEN_CANDIDATE_FIELDS, `src/detect.py:46-70`):** `p_value`, `p`, `q_value`, `q`, `confidence`, `confidence_label`, `confidence_score`, `revenue`, `expected_$`, `expected_dollars`, `ci_low`, `ci_high`, `ci_internal`, `measured_effect`, `observed_effect`, `effect_abs`, `effect_size`, `score`, `final_score`, `rank`, `recommended`. Enforced by `tests/test_detect_candidates.py`. **The lift ratio (3.2x co-occurrence) and any FP-growth confidence MUST live in the audience builder's local scope only — never on the Candidate object.** The audience-selection threshold is internal; the audience size IS the artifact.

**D-6 compliance:** The model name `fp_growth_v1` is acceptable inside `data_used` (internal trace). It MUST NOT appear in `segment_definition`. The substrate `evidence_snapshot.source` field on `recommendation_emitted` (event_version=1, frozen) is the right home for `"affinity_v1"` provenance per the I-1 ticket spec at the implementation plan §4. No new schema fields are needed.

---

## 2. Path from candidate → Recommended Experiment slot

The flow is fully built and gated; **no engine code change is required to admit the candidate** — only an audience builder and a registry hook.

```
audience_builders.bestseller_buyers (today: top-SKU buyers)
   ↓  REPLACED-OR-EXTENDED-BY → affinity_buyers (FP-growth output)
detect_candidates(g, aligned, cfg, PLAYS) at src/detect.py
   → emits Candidate(play_id="bestseller_amplify", audience_size=N, ...)
main.py:1114 builds _phase5_cands
main.py:1218 decide(engine_run, cfg, candidates=_phase5_cands_for_decide, aligned=...)
   ↓
decide._select_recommended_experiments at src/decide.py:1010-1232
   gates (must ALL pass):
     1. ENGINE_V2_SLATE flag on
     2. decision_state == PUBLISH (or publish_shadow=True)
     3. play_id ∈ {"discount_hygiene","bestseller_amplify"}
     4. play_id NOT already in recommendations[]
     5. preliminary_rejection_reason != "inventory_blocked"
     6. metadata_lookup(play_id) returns PlayMetadata (priors.yaml dict form)
     7. metadata.mechanism non-empty
     8. audience_size >= metadata.audience_floor (500)
     9. vertical ∈ metadata.vertical_applicability ([beauty, mixed])
    10. would_be_measured_by present (REPEAT_PURCHASE_IN_30D)
    11. ALL pairwise overlaps with recommendations[] < 0.30
    12. archetype dedupe within slate
    13. hard cap 2
   ↓ stamps PlayCard with:
     evidence_class=TARGETING,
     measurement=None,                          ← targeting invariant satisfied
     revenue_range=RevenueRange(suppressed=True), ← no projected lift surfaces
     opportunity_context (audience-sizing only, ALREADY plumbed),
     would_be_measured_by=REPEAT_PURCHASE_IN_30D ← already in metadata
```

**`evidence_class=targeting` requires (and gets, by construction):** `measurement is null` (load-bearing invariant from `memory.md:58`). The selector unconditionally sets `measurement=None` at `src/decide.py:1226`. The PlayCard renderer's no-dollar-headline invariant on targeting is enforced by `revenue_range.suppressed=True` at line 1207. Both invariants are satisfied automatically — the engineer cannot violate them without editing `_select_recommended_experiments`.

**`would_be_measured_by=REPEAT_PURCHASE_IN_30D` is plumbable today, no changes needed.** It already exists in `config/priors.yaml:120` for `bestseller_amplify`, is read by `priors_loader.get_play_metadata`, and is stamped onto the PlayCard at `src/decide.py:1229`. The `WouldBeMeasuredBy` enum is defined under Phase 6A Ticket A2 with `UPPER_SNAKE_CASE` values matching priors YAML — do not normalize (per `memory.md:129`).

---

## 3. Beauty fixture data sufficiency

**Counts (verified from filesystem):**
- File: `tests/fixtures/synthetic/healthy_beauty_240d_orders.csv`
- Line-item rows: **18,933** (each row = one Lineitem within an order; multi-line orders share the same `Name` order id).
- Distinct SKUs (from `tests/fixtures/synthetic/healthy_beauty_240d_inventory.csv`): **10** (BEAU-001..BEAU-010, all skincare).
- Window: **240 days** (Jan 2025 – ~Sep 2025 by header inspection).
- Order count: not exhaustively counted, but with 18,933 line items, 10 SKUs, and observed multi-line orders ≈10–15% of rows, the engineer should expect **~14k–17k orders**, **~6k–10k unique customers** (consistent with a $1.5–2M ARR Beauty fixture).

**FP-growth viability at this scale:**
- 10 SKUs is a **degenerate item set**: the FP-growth tree will have at most 10 items, and the number of frequent itemsets is bounded by 2^10 = 1,024 candidate subsets — but realistically only ~30–60 will pass any min-support floor. **FP-growth is total overkill for 10 items.** A naive 2-itemset enumeration over 45 (= 10C2) pairs is faster and equally interpretable.
- Min-support sanity: at ~15k orders, support = 0.01 → 150 orders containing the pair; 0.05 → 750; 0.10 → 1,500. Given 10 SKUs all in one subvertical (skincare), **expect most 2-pairs to clear support 0.05** because the data is dense. The engineer should anticipate a glut of "lift = 1.0–1.3" pairs and need to filter on lift ≥ 2.0 *and* require the consequent SKU to be the current top-revenue SKU (to align with `bestseller_buyers`'s existing semantics — see Caveat C).
- **Order-of-magnitude viable affinity pairs at min-support 0.05, lift ≥ 2.0:** likely **0–5 pairs**. The Beauty fixture is too synthetic (uniform price, no clustered routines) to produce strong affinity. **This is the most likely empirical halt path.** See halt criterion §7.
- Customer count for the audience: with 10 SKUs and ~6–10k unique customers, the "bought A but not B" cohort for any pair will be on the order of 500–2,500 customers. The 500 audience floor at `bestseller_amplify` is *barely* clearable. Engineer should compute the actual number on the strongest pair and report.

**ALS viability at this scale:** ALS on a 6k×10 customer×SKU matrix is mathematically valid but has near-zero degrees of freedom on the item side (10 items). It will produce factors but they will not generalize beyond what 2-pair lift already says. **ALS is not interpretable for "audience as artifact" with 10 SKUs.** Recommend FP-growth (or naive 2-pair lift) as primary; do not bother with ALS as a baseline — it costs days and proves nothing differentially. See §4.

---

## 4. FP-growth vs ALS for `evidence_class=targeting` under D-6

**Recommendation: FP-growth (or, more honestly, naive 2-pair co-occurrence lift) as primary. Drop ALS from the prototype.**

Reasoning:
- D-6 says **the audience IS the artifact**. FP-growth produces a transparent rule: "customers who bought SKU-A and not SKU-B." That rule is human-readable, copy-pasteable into `segment_definition`, and survives the forbidden-token sweep. The merchant sees the audience definition, not a model output.
- ALS produces latent factors. To turn factors into an audience you must threshold a continuous score — and that score is precisely what D-6 forbids surfacing. You can hide the score (use it only to pick the top-K customers) but then the `segment_definition` becomes "customers selected by ALS factor similarity to product X" which is opaque, untestable by the merchant, and indistinguishable from a black-box recommendation. It violates the spirit of D-6 even if it survives the forbidden-token regex.
- At 10 SKUs ALS is also empirically pointless — the rank-2 or rank-3 factorization has no room to learn anything 2-pair lift can't.
- FP-growth's output is also the right shape for the `evidence_snapshot.source="affinity_v1"` substrate field — one provenance string per audience, no per-customer score table to log.

**Do not let "ALS as a baseline comparison" expand spike scope.** The phase 2 engineer should run FP-growth (or naive 2-pair lift), report the top 3 pairs by lift, pick one, wire it. ALS is a Year-2 question.

---

## 5. Latency budget

I did not run the engine, but per the implementation plan §1 G-7 ticket the Beauty fixture runs the full pipeline twice in CI under reasonable wall time, and `memory.md:S-3` reports test suite at 1084 passed in 14s including the Beauty pinned fixture. **Engine run on Beauty is on the order of 1–5 seconds.**

FP-growth on 10 SKUs × ~15k orders is **<100ms in Python with mlxtend or a hand-rolled 2-pair counter**. ALS via `implicit` library on a 10-column matrix is also <1s but, per §4, should not be run.

**Recommended latency budget for the affinity step the engineer should respect:** ≤ 500ms added to engine run on Beauty fixture. Anything >2s indicates wrong algorithm (e.g., naive O(n²) over customers instead of items) and should be rewritten before benchmarking.

---

## 6. Concrete seam-fit risks (engineer day-1 checks)

### Caveat A — overlap with existing `bestseller_buyers` audience
The current `bestseller_buyers` builder at `src/audience_builders.py:182-230` selects all buyers of the top-revenue SKU (currently likely `Vitamin C Brightening Serum` per the inventory fixture's price ordering). The FP-growth audience for "bought A, not B" where A *is* the top SKU will be a **strict subset** of `bestseller_buyers` → Jaccard overlap with the existing card may be 1.0 or near it, failing the < 0.30 overlap gate at `src/decide.py:1157`. Day-1 check: compute Jaccard against the existing audience for the top 3 candidate pairs *before* picking which pair to wire.

### Caveat B — role uniqueness with `bestseller_amplify` Recommended Now
If `bestseller_amplify` is ALREADY in `engine_run.recommendations` on Beauty (it shouldn't be today — it's targeting-only and `bestseller_buyers` lands in Considered or Recommended Experiment), the gate at `src/decide.py:1111` drops the new candidate silently. Day-1 check: confirm the current Beauty pinned slate `dcb45cee...` does not have `bestseller_amplify` in `recommendations[]`. If it does, the seam still fits but the slot is occupied — see Caveat C.

### Caveat C — the slot is currently held by the legacy `bestseller_buyers` candidate
The B-6 pinned Beauty fixture (`memory.md:138` sha256 `48d61b89...`, since re-pinned at C2 `5fa9f697...` and C3 `dcb45cee...`) currently puts `bestseller_amplify` into the Recommended Experiment slot via the legacy top-SKU audience. Wiring an affinity candidate REPLACES that slot's audience definition. **This will perturb the pinned fixture sha256 and require a re-pin in the same commit (per the C2/C3 precedent).** The engineer must (a) confirm this is the expected diff, (b) re-pin Beauty fixture atomically with the audience-builder swap, (c) get founder sign-off on the new sha256 — same ritual as S-3's `45edaca5...` re-pin.

**This caveat does NOT force a schema change.** It is a fixture-pin discipline issue. Schema is unchanged; only the `segment_definition` string and `audience_size` value on the existing `bestseller_amplify` Recommended Experiment card change.

### Caveat D — `audience_definition_version` (D-1) bumps required
Per founder decision D-1 (`memory.md:171`), any change to audience-definition logic MUST increment `audience_definition_version`. Replacing the `bestseller_buyers` builder with an affinity builder for the same `play_id` IS a definition change → version bumps from 1 → 2. This forks the substrate `lineage_id` for every prior `bestseller_amplify` recommendation_emitted event. **This is intentional and desirable** (calibration shouldn't pool old top-SKU outcomes with new affinity-cohort outcomes), but the engineer must do the bump explicitly in the same commit and should note the forked lineage in the spike memo.

### Caveat E — `data_used` field not currently rendered, but verify
`data_used` is documented as internal-only (`src/detect.py:81-82`). The engineer should grep the renderer (`src/storytelling_v2.py` and any HTML templates) for `data_used` to confirm no surface accidentally renders it. If it does, putting `"fp_growth_v1"` there leaks model name to merchant — forbidden.

**None of A–E force a schema change. The seam fits.** They are correctness checks the engineer must run on day 1 before assuming the wire-up is mechanical.

---

## 7. Hand-off package for code-refactor-engineer phase

### Synthetic candidate spec to wire (one candidate; pick from FP-growth output)

```python
Candidate(
    play_id="bestseller_amplify",
    audience_size=<N from FP-growth, must be >= 500>,
    segment_definition=(
        "Customers who bought <SKU-A display name> but have not "
        "bought <SKU-B display name> in the last 90 days"
    ),
    data_used=["g.lineitem_any", "g.customer_id", "affinity_v1"],
    preliminary_rejection_reason=None,
    cold_start=False,
    audience_overlap={
        # Jaccard vs every other candidate's audience set, computed by
        # detect.compute_audience_overlap. Must be < 0.30 vs every
        # play_id in engine_run.recommendations or the slate gate
        # demotes it.
    },
)
```

### Assertions the prototype MUST pass to count as "seam fits"

1. **Schema unchanged:** `tests/test_play_card_contract.py` (or equivalent forbidden-fields test) green; `engine_run.json` carries no new top-level keys; `recommendation_emitted` event payload still at `event_version=1`.
2. **Targeting invariant:** the new card's `evidence_class == "targeting"` AND `measurement is None`.
3. **No-dollar-headline invariant:** card's `revenue_range.suppressed == True`.
4. **Forbidden-token sweep green** on the rendered briefing's `section.recommended-experiment` (B-2 test from `memory.md:134`). No "FP-growth", no "lift", no "confidence", no probability number on the merchant surface.
5. **Card lands in `recommended_experiments[]`,** not in `recommendations[]` and not silently dropped to Considered (verify by inspecting `engine_run.json`).
6. **Audience size ≥ 500** (the priors floor). If FP-growth produces audiences <500 on the strongest available pair, candidate is filtered and the test should report the filtered count.
7. **Substrate lineage bump:** `audience_definition_version` for `bestseller_amplify` advanced from 1 → 2 in the run; new `lineage_id` differs from prior runs' `lineage_id` for the same play (D-1 forking visible in `v_lineage_timeline`).
8. **No model name in slate:** grep the rendered HTML for `"fp_growth"`, `"FP"`, `"affinity"`, `"ALS"`, `"matrix factorization"` — all must be absent from merchant-facing copy. Internal substrate / debug.html may carry them.
9. **Beauty fixture re-pinned atomically** with the audience swap. New sha256 documented in spike memo §Phase 2.
10. **Latency:** total engine run on Beauty fixture ≤ legacy + 500ms.

### Halt criterion

**Halt and write a partial memo if any of the following is true by end of day 2:**
- FP-growth produces zero pairs at min-support 0.05 with lift ≥ 2.0 where the consequent is the top-revenue SKU and the resulting "bought A, not consequent" audience has size ≥ 500. (This means Beauty fixture is too synthetic to demonstrate the play; the seam fit is still proven on paper but the spike has no empirical candidate to wire.)
- The strongest audience candidate has Jaccard ≥ 0.30 against the current `bestseller_buyers` audience even after restricting to "did not buy consequent" — meaning the affinity audience is structurally indistinguishable from the legacy top-SKU audience and adds no information.
- The Beauty fixture re-pin requires changes to any field outside `recommended_experiments[N].audience.{size,definition}` and `recommended_experiments[N].opportunity_context.audience_size`. Any other field churn is an unexpected coupling and signals a schema risk worth escalating before merging.
- `audience_definition_version` bump cannot be threaded through the substrate writer without changing `RecommendationEmittedPayload` — this would breach the `event_version=1` schema freeze (Sprint 2 closeout) and requires founder approval, not engineer judgement.

### What NOT to do in Phase 2

- Do NOT introduce a new `play_id` (e.g., `affinity_amplify`). The allowlist in `src/decide.py:118` is hardcoded; adding a new id requires a full A4-style ticket, not a spike.
- Do NOT add per-customer score columns to the substrate. `evidence_snapshot.source="affinity_v1"` is the only provenance surface.
- Do NOT wire ALS as a "baseline comparison." See §4.
- Do NOT touch `src/decide.py` or `src/play_registry.py`. The seam is built; the only files that should change are `src/audience_builders.py` (new builder), `src/detect.py` (registry hook only if needed for the new builder), one fixture re-pin, and tests.
- Do NOT remove the legacy `bestseller_buyers` builder. Keep it as fallback for the case where FP-growth produces no qualifying pair (Beauty-shaped data); the new builder dispatches to it.

---

## 8. Files referenced (absolute paths)

- `/Users/atul.jena/Projects/Personal/beaconai/memory.md` — V2 invariants, S-3/S-4/S-5/S-6 substrate freeze
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-post-6b-restructured-plan.md` — §3 spike entry, §4 I-1, §D-7
- `/Users/atul.jena/Projects/Personal/beaconai/src/play_registry.py` — `bestseller_amplify` PlayDef (lines 212–230); `_ALL_VERTICALS` (line 143)
- `/Users/atul.jena/Projects/Personal/beaconai/src/detect.py` — `Candidate` dataclass (lines 73–109); `FORBIDDEN_CANDIDATE_FIELDS` (lines 46–70)
- `/Users/atul.jena/Projects/Personal/beaconai/src/audience_builders.py` — `bestseller_buyers` (lines 182–230); `BUILDERS` registry (line 782)
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` — `RECOMMENDED_EXPERIMENT_ALLOWLIST` (line 118); `_select_recommended_experiments` (lines 1010–1232)
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` — Phase 5 candidate plumbing (lines 1097–1226)
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml` — `bestseller_amplify` metadata (lines 115–122); `would_be_measured_by: REPEAT_PURCHASE_IN_30D` (line 120); `audience_floor: 500` (line 117)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic/healthy_beauty_240d_orders.csv` — 18,933 line items
- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic/healthy_beauty_240d_inventory.csv` — 10 SKUs
- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` — pinned slate fixture (sha256 history per memory.md C3 entry: `dcb45cee...`)

---

## Phase 2 — Empirical Results

*(Reserved for code-refactor-engineer. Append below this line; do not modify §1–§8 above.)*

**Headline verdict: HALTED on Day 1, halt criterion #1 (memo §7).**

The seam-fit assertions in §7 are confirmed against the live tree (no drift). But the Beauty fixture has **no embedded affinity structure** to mine: every 2-pair lift over the 10 SKUs is < 1.0, max 0.940. Zero pairs clear the memo's `lift ≥ 2.0 with consequent = top-revenue SKU` predicate. Wiring an affinity audience builder on this fixture would either (a) reduce to a random subset of one SKU's buyers, or (b) require fabricating a threshold to produce *any* candidate — both violate D-6 ("audience IS the artifact, not a model output dressed as one"). Branch `i1-spike` is closed at end-of-Day-1.

### Day 0 — branch + seam-fit verification

- Branch created: `i1-spike` off `post-6b-restructured-roadmap` (clean tree at branch time; only untracked file was the Phase-1 memo itself).
- All four memo §7 line-number assertions verified in current tree, no drift:
  - `Candidate` dataclass at `src/detect.py:73-109` — verified.
  - `RECOMMENDED_EXPERIMENT_ALLOWLIST` at `src/decide.py:118` — verified, contains `{"discount_hygiene", "bestseller_amplify"}`.
  - `bestseller_buyers` builder at `src/audience_builders.py:182-230` — verified, current `segment_definition="buyers of top-revenue product"`, top-SKU buyer set semantics intact.
  - `bestseller_amplify` priors at `config/priors.yaml:115-122` — verified, `audience_floor: 500`, `would_be_measured_by: REPEAT_PURCHASE_IN_30D`, `vertical_applicability: [beauty, mixed]` all present.

### Day 1 Risk Check A — slot occupancy on pinned Beauty fixture

Read `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`. The `section.recommended-experiment` slot today contains two cards in this order:
1. `data-play-id="discount_hygiene"` — audience 2,251, def "customers with discounted orders in last 28 days", measured-by 7d email-attributed revenue.
2. `data-play-id="bestseller_amplify"` — audience **1,475**, def **"buyers of top-revenue product"**, measured-by 30d repeat purchase.

**Memo prediction confirmed.** `bestseller_amplify` occupies the slot; wiring an affinity audience would replace the audience definition + size for card 2 and force a fixture re-pin (Caveat C scenario).

### Day 1 Risk Check B — 2-pair co-occurrence over Beauty fixture (`scripts/spike_i1_affinity.py`)

Source: `tests/fixtures/synthetic/healthy_beauty_240d_orders.csv` (18,933 line items). Customer key = `Customer Email`. SKU key = `Lineitem name`.

- **Customers (with email):** 9,404
- **Distinct SKUs:** 10 (matches inventory fixture; memo §3 prediction range 6k–10k confirmed)
- **Top revenue SKU:** `Peptide Eye Cream`, $146,221 (note: NOT `Vitamin C Brightening Serum` as memo §6 Caveat A speculated; this affects nothing but worth noting for the record)
- **Mean SKUs per customer:** 1.85 (highly uniform; SKU-count distribution: 1:4470, 2:2887, 3:1331, 4:500, 5:170, 6:34, 7:10, 8:2)

**All 9 candidate pairs where consequent = top-revenue SKU `Peptide Eye Cream` (sorted by lift desc):**

| antecedent                              | consequent          | support | lift  | audience(A-not-B) | buyers(A) | buyers(B) |
|-----------------------------------------|---------------------|--------:|------:|------------------:|----------:|----------:|
| SPF 50 Daily Defense Cream              | Peptide Eye Cream   | 0.0326  | 0.940 | 1,420             | 1,727     | 1,778     |
| Retinol Night Treatment                 | Peptide Eye Cream   | 0.0316  | 0.897 | 1,454             | 1,751     | 1,778     |
| Hyaluronic Acid Moisturizer             | Peptide Eye Cream   | 0.0304  | 0.882 | 1,430             | 1,716     | 1,778     |
| Gentle Foaming Cleanser                 | Peptide Eye Cream   | 0.0298  | 0.852 | 1,459             | 1,739     | 1,778     |
| Niacinamide Pore Refining Toner         | Peptide Eye Cream   | 0.0296  | 0.849 | 1,453             | 1,731     | 1,778     |
| Ceramide Barrier Repair Moisturizer     | Peptide Eye Cream   | 0.0298  | 0.827 | 1,510             | 1,790     | 1,778     |
| AHA/BHA Exfoliating Serum               | Peptide Eye Cream   | 0.0287  | 0.822 | 1,468             | 1,738     | 1,778     |
| Micellar Cleansing Water                | Peptide Eye Cream   | 0.0273  | 0.813 | 1,414             | 1,671     | 1,778     |
| Vitamin C Brightening Serum             | Peptide Eye Cream   | 0.0279  | 0.798 | 1,474             | 1,736     | 1,778     |

**Top 5 lift pairs unrestricted by consequent (max across all 45 unordered pairs):**

| pair                                                              | lift  | support | aud(A-not-B) |
|-------------------------------------------------------------------|------:|--------:|-------------:|
| Peptide Eye Cream <-> SPF 50 Daily Defense Cream                  | 0.940 | 0.0326  | 1,471        |
| Micellar Cleansing Water <-> SPF 50 Daily Defense Cream           | 0.922 | 0.0301  | 1,388        |
| Retinol Night Treatment <-> SPF 50 Daily Defense Cream            | 0.921 | 0.0315  | 1,455        |
| Micellar Cleansing Water <-> Retinol Night Treatment              | 0.913 | 0.0302  | 1,387        |
| Ceramide Barrier Repair Moisturizer <-> Retinol Night Treatment   | 0.912 | 0.0323  | 1,486        |

**Verdict (B):** **Zero pairs qualify** under the memo's filter (`lift ≥ 2.0` with consequent = top-revenue SKU). The *maximum lift across all 45 unordered pairs is 0.940* — i.e., every SKU pair on this fixture is at or slightly below independence. Memo §3 predicted "0–5 viable pairs"; the empirical answer is **0**, at the lower end of the prediction. The Beauty synthetic generator clearly samples line-items near-uniformly across SKUs, conditional on customer activity level, with no programmed cross-product affinity — exactly the failure mode the memo anticipated.

### Day 1 Risk Check C — Jaccard vs legacy `bestseller_buyers`

Computed Jaccard anyway, on the strongest (would-be-qualifying-if-the-bar-were-lift>=0) pair: `SPF 50 Daily Defense Cream → Peptide Eye Cream`.

- Affinity audience (`bought SPF 50, NOT bought Peptide Eye Cream`): 1,420 customers
- Legacy `bestseller_buyers` audience (buyers of `Peptide Eye Cream`): 1,778 customers
- Intersection: 0 (by construction — affinity audience excludes consequent buyers, legacy IS the consequent buyers)
- **Jaccard: 0.0000**

This is a **tautological zero**, not a "passes the < 0.30 overlap gate" result. The two audiences are disjoint *by construction of the `A and not B` rule*, regardless of underlying affinity. This means even if Day 1 Risk Check B had produced a qualifying pair, the overlap-gate signal would be uninformative on a same-vs-disjoint-cohort design: a Jaccard of 0 does not validate the audience is *meaningfully different* (it only validates that we excluded the consequent buyers, which is trivial). For future I-1 design (when the fixture has real affinity), the overlap gate test should be against a *non-consequent-exclusionary* baseline — e.g., random sample of N customers, or "any non-top-SKU buyer" cohort. The current `< 0.30` threshold is shaped for cohort-overlap detection, not for "we manually excluded the other side" disjointness.

### Halt-criterion fire

Per memo §7, **halt criterion #1** is hit:

> FP-growth produces zero pairs at min-support 0.05 with lift ≥ 2.0 where the consequent is the top-revenue SKU and the resulting "bought A, not consequent" audience has size ≥ 500.

Translation: the Beauty fixture is too synthetic to demonstrate the play; the seam fit is proven on paper (Day 0 line-number verification + the architecture in §1–§5 stands) but the spike has no empirical candidate to wire. Per the contract, I **did not proceed to Day 2** — no audience builder added, no `detect_candidates` hook added, no fixture re-pin attempted, no priors version bump, no engine wall-time benchmark.

### Did not run (because halted)

- Day 2 step 1 (new `affinity_buyers_for_amplify` audience builder) — skipped.
- Day 2 step 2 (`detect_candidates` wiring + `data_used=["affinity_v1"]`) — skipped.
- Day 2 step 3 (`audience_definition_version` 1→2 bump and substrate threading check) — skipped, but inspected `RecommendationEmittedPayload` enough to confirm it is **not** the blocker (the field already exists on the payload; bumping its value would not have required a schema change). Halt criterion #4 would NOT have fired.
- Day 2 step 4 (engine run on Beauty + `engine_run.json` slot/measurement/revenue_range checks) — skipped.
- Day 2 step 5 (atomic Beauty fixture re-pin) — skipped. **No new sha256.** Pinned fixture (current `dcb45cee...`-class sha) is untouched on the spike branch.
- Day 2 step 6 (forbidden-token sweep) — skipped.
- Day 2 step 7 (latency delta) — skipped. Not measured.

### Surprises / seam-fit notes for the record

1. **Top revenue SKU is `Peptide Eye Cream`, not `Vitamin C Brightening Serum`.** Memo §6 Caveat A guessed Vitamin C based on inventory-fixture price ordering; revenue-weighted ranking flips it. Affects no architecture; flag for future fixture-aware copy.
2. **The fixture's customer-SKU distribution is too uniform for affinity mining.** Mean 1.85 SKUs per customer with a Zipfian tail (4470 / 2887 / 1331 / 500 / 170 / 34 / 10 / 2 for SKU-counts 1..8) and uniform per-SKU buyer counts (1,671 – 1,790, a ~7% spread across all 10 SKUs) is the structural reason all lifts collapse to 0.80–0.94. The generator does not bake in routines or cross-sell propensity.
3. **The Jaccard tautology in Risk Check C is a contract-shape issue.** The `audience_overlap < 0.30` gate at `src/decide.py:125` is the right gate for normal candidate-vs-candidate overlap, but for a same-play audience-rule swap (legacy top-SKU buyers → affinity-cohort buyers within the same `play_id="bestseller_amplify"`), the affinity rule `A and not B` makes the cohorts disjoint by construction whenever the consequent is the top SKU. If I-1 ever lands with real affinity data, the overlap-gate semantics for this case should be revisited — likely by computing Jaccard against the *previous* version of `bestseller_amplify`'s audience (calibration-style), not against `discount_hygiene` (which is the only other candidate that would be in `recommendations[]`).
4. **The `evidence_snapshot.source = "affinity_v1"` substrate field plan from memo §1 is intact** — `RecommendationEmittedPayload` already accommodates it without schema change, so when a fixture with real affinity is available, the substrate path is unblocked.

### Recommended Sprint 4 I-1 scope (revised)

**Do not ship I-1 on the current Beauty fixture.** It cannot empirically demonstrate the play. Sprint 4 I-1 has two viable shapes; recommend **(B)** as the safer path.

**(A) Reshape the Beauty fixture, then ship I-1 (verified-empirical).** In scope:
- Modify `tests/fixtures/synthetic/healthy_beauty_240d_orders.csv` generator (whatever produced it) to embed a deliberate co-purchase routine — e.g., 30% of customers who buy `SPF 50 Daily Defense Cream` also buy `Vitamin C Brightening Serum` within 30 days, producing a lift ≥ 2.5 pair with audience size ≥ 1,000.
- Re-pin all Beauty-dependent fixtures (briefing HTML, engine_run.json fixtures, memory.db golden if any).
- Then wire `affinity_buyers_for_amplify` per memo §7 spec, atomic with fixture re-pin and `audience_definition_version` 1→2 bump.
- **Risk:** fixture re-pin touches every downstream test (memory.md S-3 records 1,084 tests; many will diff). Estimate 2–3 day diff-triage. Worth doing only if founder wants empirical I-1 on synthetic data before real-store rollout.

**(B) Defer I-1 until a real merchant fixture exists.** In scope for Sprint 4:
- Document the seam-fit verification (this memo) as the artifact closing the spike.
- Add `audience_definition_version` bump tooling (no behavior change) so I-1 can land atomically when affinity data arrives.
- Add a minimal `affinity_buyers_for_amplify` skeleton in `src/audience_builders.py` that *only* dispatches to legacy `bestseller_buyers` (no affinity mining yet) but has the right signature and `data_used=["g.lineitem_any", "g.customer_id", "affinity_v1_skeleton"]` provenance string. This is a no-op on Beauty (audience identical to legacy) and forces zero fixture re-pin.
- When a real merchant CSV with non-trivial cross-purchase shows up, swap the skeleton's internals to a real 2-pair miner (FP-growth not needed at 10 SKUs; pandas crosstab + lift filter suffices) and re-pin only the affected fixture in the same commit.

**Out of scope for either path (deferred to Year 2):**
- ALS / matrix factorization (memo §4 ruled it out; nothing learned in Phase 2 changes this).
- New `play_id="affinity_amplify"` (memo §7 forbids; nothing learned in Phase 2 changes this).
- Multi-antecedent rules (3-pair and beyond — overkill for any realistic DTC catalog under 20 SKUs).
- Per-customer score logging in substrate (D-6 violation; the audience IS the artifact, not a score column).

### Closeout

- Branch `i1-spike` is throwaway. **No merge to `post-6b-restructured-roadmap` or `main`.** No push.
- One spike-only file added: `scripts/spike_i1_affinity.py` (the Day 1 risk-check script). Reproducible by `python scripts/spike_i1_affinity.py` from repo root. Stdlib + nothing else.
- No `src/` files changed. No tests changed. No fixtures changed. No `memory.md` write. M0 pinned-slate sha256 untouched.
- All 10 §7 assertions: **not reached** (halted before Day 2 wire-up). Their applicability depends on the I-1 path the founder picks above.
