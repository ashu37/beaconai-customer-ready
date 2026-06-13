# S7 priors-wiring slice — closeout summary (2026-05-20)

**Agent:** code-refactor-engineer
**Ticket:** S7 priors-wiring (re-authored after founder-rejection of prior pass)
**Branch:** `post-6b-restructured-roadmap`
**Date:** 2026-05-20
**Status:** COMPLETE. 5 of 6 commits re-authored from scratch per the founder
corrections doc; Commit 1 (dc1f22d, memos + DS verdict) preserved verbatim
from the prior pass.

---

## Scope

Wire the 4 Gemini Deep Research memos validated by the DS architect on
2026-05-20 (Memos 1, 2, 3 -> priors.yaml entries; Memo 4 -> operational
reference only, NO priors.yaml entry). Refactor the two new priors blocks
to DICT FORM with metadata, matching the `replenishment_due` structural
template. Land the supporting enum surface additions (4 enum members,
all additive within `event_version=1`) + a load-bearing enum/metadata
cross-pin test (S6-T3.5 latent-`CADENCE_DUE_REPEAT_BUYER` precedent).

Founder-mandated corrections applied to the prior pass:
1. Refactor priors blocks from legacy list-form to dict-form with metadata.
2. Restore enum surface additions (the prior pass deferred these to S7-T1
   / S7-T3 impl, which left the dict-form blocks unparseable).
3. Revert floor-grid DECISIONS.md entries from the prior pass (out of scope
   for this ticket; floor grids land in a separate founder-lock turn).
4. Resequence to match the original spec commit boundaries.
5. Cross-pin discipline (load-bearing invariant from S6-T3.5).

---

## Commit chain

| # | SHA | Title |
|---|---|---|
| 1 | `dc1f22d` (preserved) | save 4 Gemini Deep Research memos + DS verdict verbatim |
| 2 | `6bc1d98` | priors.yaml dict-form blocks for Memos 1, 2, 3 + supporting enum additions |
| 3 | `d8e9788` | enum/metadata cross-pin test (S6-T3.5 precedent) |
| 4 | `0395987` | file KI-NEW-J + KI-NEW-K |
| 5 | `405801b` | memory.md Sprint 7 priors-wiring entry |
| 6 | (this commit) | agent_outputs summary |

---

## Files changed (Commits 2-6, new from re-author)

### Commit 2 — priors.yaml dict-form + enums + audit-pin updates

- `config/priors.yaml` — 2 NEW play_id blocks (`discount_dependency_hygiene`,
  `aov_lift_via_threshold_bundle`) authored in DICT FORM with `metadata:` +
  `priors:` sections; 3 NEW prior entries total (1 beauty in
  discount_dependency_hygiene, 2 in aov_lift_via_threshold_bundle).
- `src/engine_run.py::WouldBeMeasuredBy` — 2 additive enum members:
  `DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D`,
  `AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D`.
- `src/priors_loader.py::AudienceArchetype` — 2 additive enum members:
  `DISCOUNT_CONDITIONED_REPEAT_BUYER`, `THRESHOLD_NEAR_BUYER`. Casing is
  UPPER_SNAKE_CASE per founder-spec mandate.
- `src/priors_loader.py::PlayMetadata` — `audience_floor` typed as
  `Optional[int]`; `_coerce_metadata` accepts `None` (positive-int
  validation still binds when value IS authored).
- `tests/test_s7_5_t1_5_priors_audit.py` — distribution pin
  `validated_external 4 -> 6`, `elicited_expert 0 -> 1`; loader-resolves
  pin `85 -> 88`.
- `tests/test_would_be_measured_by_enum.py` — pinned enum surface 5 -> 7.
- `tests/test_engine_run_schema.py` — UPPER_SNAKE_CASE pin 5 -> 7.

### Commit 3 — cross-pin test

- `tests/test_s7_priors_enum_cross_pin.py` (NEW) — 5 tests pinning the
  YAML metadata <-> enum membership invariant in both directions for
  every dict-form priors block, plus explicit assertions on the two new
  S7 metadata blocks and the four new enum members.

### Commit 4 — KIs

- `KNOWN_ISSUES.md` — 2 NEW KIs (KI-NEW-J, KI-NEW-K). Architectural
  limitations 13 -> 15; Total 22 -> 24. Updated `Last updated` line.

### Commit 5 — memory.md

- `memory.md` — 1 new ticket entry (~80 lines) under a new `Sprint 7`
  banner. Documents scope, load-bearing invariants, caveats, founder Q.

### Commit 6 — this file

- `agent_outputs/code-refactor-engineer-s7-priors-wiring-summary.md` (NEW).

---

## What the rejected-pass deltas looked like, and what was reverted

Prior pass (6 commits dc1f22d, 1e0eb92, 76d1c35, 2b83a74, 1e97570, baf4c9a)
contained these founder-rejected deviations:

| Deviation | Status now |
|---|---|
| priors.yaml blocks authored in LEGACY LIST FORM (no metadata) | REVERTED — re-authored in DICT FORM with metadata (Commit 2). |
| WouldBeMeasuredBy + AudienceArchetype enum additions DEFERRED to S7-T1 / S7-T3 | REVERTED — enum additions land in Commit 2 (required for dict-form parse). |
| DECISIONS.md D-S7-1..D-S7-4 floor-grid entries added | REVERTED — entries not re-introduced (out of scope; floor-grid lock is a separate founder turn). |
| No cross-pin test | REVERTED — load-bearing cross-pin test added (Commit 3). |
| KI-NEW-J + KI-NEW-K | PRESERVED (founder-accepted; re-authored in Commit 4). |

---

## Behavior changes

- **No engine behavior change** at run time. All 4 new enum members are
  consumer-dormant until the S7-T1 / S7-T3 builders ship. Renderer
  display copy (`storytelling_v2::_WOULD_BE_MEASURED_BY_DISPLAY_COPY`)
  is not extended for the new members (same posture as the dormant
  S6 `LAPSED_REACTIVATION_IN_30D` / `REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW`
  additions).
- **No flag flipped.** No M0 golden change. Beauty pinned slate unchanged.
- **Loader contract change:** `PlayMetadata.audience_floor` is now
  `Optional[int]`. Callers of `get_audience_floor` were already
  resilient to `None` returns; no downstream consumer break observed
  in the suite.
- **Test surface grew by ~5 tests** (cross-pin file + parametrize fanout
  on new enum members).

---

## Tests / checks run

- `pytest tests/test_priors_metadata.py tests/test_s7_5_t1_5_priors_audit.py
  tests/test_s7_priors_enum_cross_pin.py tests/test_would_be_measured_by_enum.py
  tests/test_engine_run_schema.py` — 64 passed (smoke check after each commit).
- `pytest -q` (full suite) — **1506 passed / 14 skipped / 4 xfailed / 0 failed**
  on the final HEAD. Pre-S7 baseline was 1497p / 14s / 4xf / 0f
  (per `agent_outputs/implementation-manager-s7-planning-refresh.md`); +9
  net tests (5 new in cross-pin file + 4 from parametrize fanout on the
  2 new WouldBeMeasuredBy members across the round-trip parametrized test
  + similar).
- M0 byte-identity: the existing M0 golden tests pass within the full
  suite — no golden delta from this slice.

---

## Confirmations against the corrections doc

- [x] Commit 1 (dc1f22d) preserved verbatim; memos + DS verdict intact.
- [x] priors.yaml blocks in DICT FORM matching `replenishment_due` template.
- [x] `audience_floor: null` (TBD); no floor populated.
- [x] Beauty `discount_dependency_hygiene.metadata.vertical_applicability`
      = `[beauty]` (NOT supplements).
- [x] `aov_lift_via_threshold_bundle.metadata.vertical_applicability` =
      `[beauty, supplements]`.
- [x] Memo 1 notes field flags BOTH (a) Beta envelope issue + (b) base64-image
      provenance.
- [x] Supplements `aov_lift_via_threshold_bundle` priors entry uses
      `alpha=0.095, beta=9.905, effective_n=10` per DS downgrade.
- [x] Supplements `discount_dependency_hygiene` has NO priors.yaml entry.
- [x] WouldBeMeasuredBy + AudienceArchetype enums extended.
- [x] Cross-pin test passes for ALL priors-blocks-with-metadata (covers
      bestseller_amplify, discount_hygiene, routine_builder,
      first_to_second_purchase, replenishment_due,
      discount_dependency_hygiene, aov_lift_via_threshold_bundle).
- [x] No DECISIONS.md edits in this ticket (rejected D-S7-1..D-S7-4 NOT
      re-introduced).
- [x] No flag flipped.
- [x] M0 byte-identical.
- [x] No fake p-values / fake CIs / hardcoded effects / forced
      recommendations / fake ML introduced.

---

## Founder Q surface

### Q1 (raised in prior pass, still applies) — KI naming collision

The DS verdict doc references "KI-27" / "KI-28" as the new-KI labels,
but the existing `KNOWN_ISSUES.md` already has KI-27 and KI-28 assigned
to unrelated topics (empty_bottle supplements skip and mixed-vertical
G-1 fixture gap respectively). Filed under the prevailing KI-NEW-*
naming pattern instead. Founder accepted the collision-avoidance pattern
in the corrections doc — preserved.

### Q2 (NEW) — Commit 2 / Commit 3 bundling

The corrections doc specifies:
- Commit 2: priors.yaml dict-form blocks
- Commit 3: enum additions + cross-pin tests

The dict-form metadata blocks fail to parse without the enum additions
(`_coerce_metadata` raises `PriorsMetadataError` on unknown enum strings),
so landing priors-only in Commit 2 would break loader invariants and
violate the "engine must remain runnable after every patch" constraint.

Resolution: bundled enum additions into Commit 2 alongside the priors
blocks they parse; Commit 3 delivers ONLY the cross-pin test. This
preserves the spec's intent (separation of priors-data from test-pinning)
while keeping the suite green at every commit. Surface for review.

### Q3 (NEW) — Existing dict-form blocks NOT on the corrections-doc list

The corrections doc says the cross-pin test should cover "ALL 5
priors-blocks-with-metadata (the existing replenishment_due + winback_21_45
+ bestseller_amplify + first_to_second_purchase blocks if they use
dict-form, plus the 2 new ones)". Inspection of `config/priors.yaml`:

- `winback_21_45` is LEGACY LIST FORM (no metadata). Excluded from the
  cross-pin test by design.
- `routine_builder` IS dict-form (S4 Ticket G-3 promotion). Was not
  named on the corrections-doc list but is in scope of the cross-pin
  invariant.
- `discount_hygiene` IS dict-form (Phase 6A A3). Was not named on the
  corrections-doc list but is in scope.

The cross-pin test is scoped to "every block using metadata", which is
the load-bearing invariant per S6-T3.5 precedent. Effective coverage:
7 dict-form blocks (5 pre-existing + 2 new S7). Surface for review.

### Q4 (NEW) — UPPER_SNAKE_CASE on AudienceArchetype S7 additions

The existing `AudienceArchetype` enum convention is LOWERCASE
(`hero_sku_buyer`, `discount_buyer`, `cadence_due_repeat_buyer`, etc.,
with docstring explicitly mandating lowercase for future additions).
The corrections doc spec for S7 explicitly authors `DISCOUNT_CONDITIONED_REPEAT_BUYER`
and `THRESHOLD_NEAR_BUYER` in UPPER_SNAKE_CASE on the YAML side and says
"do not normalize". I shipped UPPER on both sides (YAML + enum) to match.
This is a founder-locked deviation from the prior convention; documented
in `src/priors_loader.py::AudienceArchetype` docstring + in memory.md as
load-bearing invariant. Confirm intentional or normalize in a follow-up.

### Q5 (NEW) — `audience_floor: null` loader carve-out

To honor the corrections-doc constraint that `audience_floor` "stays
null/TBD in priors.yaml metadata for now", I made
`PlayMetadata.audience_floor` `Optional[int]` and accepted `None` in
`_coerce_metadata`. The positive-int validation still binds when an
integer IS authored. `get_audience_floor` was already resilient (its
`int()` fallback returns `None`). This is a minor loader-contract
change — surface for review.

---

## Remaining risks

- Memo 1 J-shape Beta envelope misbehavior: KI-NEW-K parks the re-fit to
  Sprint 8. Until then, the discount_dependency_hygiene play is
  consumer-dormant (no builder shipped), so the risk is research-locked
  not decision-relevant.
- Memo 1 base64-image provenance: KI-NEW-K parks verification to Sprint 8.
- Supplements `aov_lift_via_threshold_bundle` magnitude not independently
  sourced: KI-NEW-J parks supplements-specific re-research.
- Supplements `discount_dependency_hygiene` stays PRIOR_UNVALIDATED ->
  Path-D dormant until either a new memo with point estimate arrives OR
  the play is sunsetted (KI-NEW-J).
- The `audience_floor: null` carve-out means
  `get_audience_floor("discount_dependency_hygiene", ...)` and
  `get_audience_floor("aov_lift_via_threshold_bundle", ...)` will return
  `None` — callers must fall back to their legacy defaults (this is the
  same posture as plays without metadata blocks at all).

---

## Next milestone dependencies

- S7-T1 (discount_dependency_hygiene builder) can proceed once the
  floor-grid founder-lock turn lands the `audience_floor` cells.
- S7-T3 (aov_lift_via_threshold_bundle builder) same dependency.
- S7-T2 (cohort_journey_first_to_second) is INDEPENDENT — reuses the
  existing `first_to_second_purchase.base_rate` validated_external prior
  and can proceed immediately.
- S7-T4 (4-state abstain migration) is INDEPENDENT — pure contract
  evolution.
- KI-NEW-K Beta re-fit lands in a Sprint 8 calibration pass.
- KI-NEW-J supplements re-research is post-beta or a dedicated
  Deep Research re-run pass.

---

## Relevant file paths

- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml`
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/priors_loader.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s7_priors_enum_cross_pin.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s7_5_t1_5_priors_audit.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_would_be_measured_by_enum.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_engine_run_schema.py`
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md`
- `/Users/atul.jena/Projects/Personal/beaconai/memory.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-s7-planning-refresh.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ecommerce-ds-architect-s7-priors-validation-2026-05-20.md`
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors_sources/discount_dependency_hygiene__base_rate__beauty.md`
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors_sources/aov_lift_via_threshold_bundle__base_rate__beauty.md`
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors_sources/aov_lift_via_threshold_bundle__base_rate__supplements.md`
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors_sources/discount_dependency_hygiene__supplements__operational_reference.md`

## Backfill from memory.md (migration trim 2026-05-25)

## S7 priors-wiring — Memos 1/2/3/4 -> priors.yaml + enum surface (2026-05-20)

**Shipped:**
- 4 Gemini Deep Research memos + DS-architect verdict matrix saved verbatim
  under `config/priors_sources/` + `agent_outputs/` (Commit 1, dc1f22d).
- 2 NEW play_id blocks in `config/priors.yaml::plays` authored in DICT FORM
  with metadata (parallel to `replenishment_due` structural template):
  `discount_dependency_hygiene` (Memo 1 ACCEPT WITH MODIFICATION, beauty only)
  and `aov_lift_via_threshold_bundle` (Memo 2 ACCEPT beauty + Memo 3
  DOWNGRADED supplements).
- 4 enum additions, all additive within `event_version=1` per A2 precedent:
  `WouldBeMeasuredBy.DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D`,
  `WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D`,
  `AudienceArchetype.DISCOUNT_CONDITIONED_REPEAT_BUYER`,
  `AudienceArchetype.THRESHOLD_NEAR_BUYER`.
- Load-bearing enum/metadata cross-pin test
  (`tests/test_s7_priors_enum_cross_pin.py`) — closes the S6-T3.5
  latent-`CADENCE_DUE_REPEAT_BUYER` failure-mode class.
- 2 new KIs (KI-NEW-J + KI-NEW-K) document the supplements re-research
  target + Beta envelope re-fit.

**Load-bearing invariants:**
- The cross-pin test scoped to dict-form blocks pins YAML metadata <->
  enum membership in BOTH directions for all current dict-form blocks
  (bestseller_amplify, discount_hygiene, routine_builder,
  first_to_second_purchase, replenishment_due, discount_dependency_hygiene,
  aov_lift_via_threshold_bundle). Adding a new audience_archetype or
  would_be_measured_by string in any dict-form block REQUIRES adding the
  matching enum member in the same commit.
- The S7 AudienceArchetype additions use UPPER_SNAKE_CASE per founder-spec
  mandate (the YAML metadata strings are UPPER_SNAKE_CASE in this ticket).
  This DEVIATES from the existing lowercase convention on the enum but is
  founder-locked; do NOT normalize.
- `PlayMetadata.audience_floor` is now `Optional[int]`; `None` is a legal
  authored value for plays whose floor grid has not yet been founder-locked.
  Loader-side positive-int validation still binds when a value IS authored.
  The S7 entries carry `audience_floor: null` pending a separate floor-grid
  founder-lock turn against the DS-recommended grid.
- Supplements `discount_dependency_hygiene` has NO priors.yaml entry
  (asymmetric-no-cell, parallel to `replenishment_due` supplements absence).
  Memo 4 was REJECTED as a `validated_external` prior (operational playbook,
  no point estimate); the play stays PRIOR_UNVALIDATED -> Path-D dormant.
  Do NOT author a stub for code-symmetry.

**Caveats / dormant behavior:**
- All enum additions are CONSUMER-DORMANT until S7-T1 / S7-T3 ship the
  builders + measurement_builder dispatch. Renderer-side display copy
  (`storytelling_v2::_WOULD_BE_MEASURED_BY_DISPLAY_COPY`) is NOT extended
  in this ticket — same posture as the S6 `LAPSED_REACTIVATION_IN_30D` and
  `REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW` additions, which also lack
  display copy until activation.
- No flag flipped. No M0 golden change. No Beauty pinned slate change.
- Memo 1's Beta(alpha=0.66, beta=29.34) is J-shaped — KI-NEW-K defers
  re-fit at effective_n=60 to Sprint 8. Memo 1's numerics were transcribed
  from base64-encoded images — verify against original Klaviyo PDFs before
  Sprint 8 calibration.
- Floor-grid DECISIONS entries are intentionally OUT OF SCOPE — they land
  in a separate founder-lock turn against the DS-recommended Gap A/B/C/D/E/F
  grid (rejected-pass D-S7-1..D-S7-4 NOT re-introduced).
- Bundled enum additions in Commit 2 (not split into a separate Commit 3)
  because the dict-form metadata blocks fail to parse without them
  (`_coerce_metadata` raises `PriorsMetadataError` on unknown enum strings);
  splitting them would break engine-runnability mid-ticket. The originally-
  planned Commit 3 scope is delivered as the cross-pin test only.

**Schema:** event_version=1 additive (4 enum members + Optional audience_floor)
**Suite:** 1500 passed / 14 skipped / 4 xfailed / 0 failed (last full run 2026-05-20; +5 net tests via cross-pin file relative to pre-S7 baseline of ~1497).
**Summary:** [agent_outputs/code-refactor-engineer-s7-priors-wiring-summary.md](agent_outputs/code-refactor-engineer-s7-priors-wiring-summary.md)

**Founder Q surfaced:** KI naming collision — the DS verdict doc references
"KI-27" / "KI-28" as the new-KI labels, but those IDs are already assigned
to unrelated topics in `KNOWN_ISSUES.md` (empty_bottle supplements skip and
mixed-vertical G-1 fixture gap respectively). Filed under the prevailing
KI-NEW-* naming pattern instead. Confirm pattern is intended; rename if not.

**Commit chain:** Commit 1 dc1f22d (memos), Commit 2 (priors.yaml dict-form
+ enums + audit-pin updates), Commit 3 (cross-pin test), Commit 4
(KI-NEW-J + KI-NEW-K), Commit 5 (this entry), Commit 6 (summary file).
