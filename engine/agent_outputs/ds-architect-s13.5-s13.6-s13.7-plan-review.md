# DS Architect — S13.5 + S13.6 + S13.7 Plan Review

**Date:** 2026-05-30
**Reviewer:** DS Architect
**Plan under review:** `agent_outputs/implementation-manager-s13.5-s13.6-s13.7-plan.md`
**Verdict:** **APPROVE-WITH-CHANGES**

---

## (a) Plan verdict

**APPROVE-WITH-CHANGES.** The plan correctly absorbs all 4 P0 + 7 P1 items from the agent-readiness verdict, all 3 S13.7 tickets from the end-to-end-flow verdict, and the 6 founder lock-ins. Sprint sequencing (S13.5 → S13.6 → S13.7 → handoff → S14) is sound. Ticket sizing is reasonable. Byte-identity gates on `briefing.html` and re-pin discipline on `engine_run.json` SHA are correctly identified. Single-demote-channel and 3-channel `priority_prepend` invariants are preserved by reference at S13.5-T1 and by non-touching at S13.6/S13.7.

The changes required are precise, not structural: T6 needs the enum audit-locked in this verdict (below), T7 needs Pattern A confirmed and the Optional-by-Optional triage spelled out, T3 needs the guardrail upgraded from a flag to a wrapper, T1 (S13.7) needs an explicit RFM-refusal branch, and 3 minor ticket splits.

---

## (b) Adjudications on the 6 IM open questions

| # | Question | DS adjudication | Rationale |
|---|---|---|---|
| 1 | T7 Pattern A vs B | **Pattern A (paired `_null_reason`)** | Additive, preserves current JSON shape, no rename churn, AST-aware test is sufficient to pin "no new Optional without paired reason." Pattern B is more elegant but the migration cost is not justified pre-beta. |
| 2 | T6 enum scope (closed vs open) | **Closed set, audited at T6** | RULE A demands typed atoms; an open set defers the audit and leaves the contract's most-touched field as effectively `str`. Forces the audit while the dataset is still small. |
| 3 | T3 mechanism contract doc location | **Standalone `docs/mechanism_contract.md`** | Narration agent codes against this file; it deserves its own surface. `docs/DECISIONS.md` is for the *decision*, not the *spec*. |
| 4 | `src/segments.py` retirement: hard cut vs deprecation | **Hard cut at S13.7-T1**, with one addition: T1 dispatch brief MUST first run an AST grep for all importers of `src.segments` and either remove call sites or fail loudly. No silent deprecation — replace by `raise NotImplementedError("Retired at S13.7-T1; use audience_resolver")`. |
| 5 | T6 enum + T3 spec doc ordering | **Keep split as planned** (enum at S13.6-T6 lives in `engine_run.py` typed surface; spec doc at S13.7-T3). Enum-without-spec for one sprint is acceptable because the enum *is* the contract; the spec just documents per-type parameters. |
| 6 | Schema generator tooling | **Hand-written generator at `tools/generate_schema.py`** | Preserves dataclass-native posture. `dataclasses-jsonschema` adds a dep with marginal benefit; `pydantic` migration is out of scope. The generator only needs to walk `engine_run.py` dataclasses, enums, and `Optional/List/Dict` — straightforward. Round-trip test on pinned fixtures is the canonical correctness check. |

---

## (c) Required v2 IM revisions

### R1 — T3 (OpportunityContext): upgrade guardrail from flag to wrapper

A `bool _do_not_narrate_as_lift = True` field on the dataclass is **type-safety theatre**. An agent that ignores it sees the numbers and narrates them. Replace with a wrapper dataclass at the field type level:

```python
@dataclass
class NonLiftAtom:
    value: float
    semantic: Literal["addressable_opportunity"]  # not lift, not p50, not forecast
    aov_used: float
    monthly_revenue_estimate: float
```

The wrapper *names* the constraint at the type system, not via a sibling flag. Schema consumers see `NonLiftAtom`, not a number with a "please don't narrate as lift" sticker. **This is the DS-flagged HIGHEST SINGLE RISK on the contract — the guardrail must be expressed at the type, not at a field.**

Dedup decisions (DS-locked):
- KEEP `aov_used` (more explicit about provenance); STRIP `aov`.
- KEEP `monthly_revenue_estimate` (the actual semantic); STRIP `addressable_value`.

### R2 — T6: enum audit-locked in this verdict (see section d)

T6 dispatch brief MUST cite this verdict's enum list as the audit anchor. Refactor-engineer audits emission sites and verifies completeness/no-extras.

### R3 — T7: Optional-by-Optional triage table required in T7 dispatch brief

T7 cannot dispatch with "walk every Optional." Brief must enumerate every Optional field with a DS-pre-assigned classification: (i) needs null_reason, (ii) None is unambiguous and acceptable (e.g., backref fields like `prior_run_id` where absence = "no prior run, not suppressed for a reason"). See section (e) below for the cut.

### R4 — S13.7-T1: explicit RFM-REFUSED behavior

Per S13-T2.5 small_store_240d observation, RFM can be REFUSED at runtime. T1 dispatch brief MUST specify: when the substrate that ranks a PlayCard's audience is REFUSED, the resolver:
- Emits an **empty CSV with the standard header row**, plus
- Records a typed `audience_materialization_status: SUPPRESSED_SUBSTRATE_REFUSED` in `manifest.json` for that PlayCard's audience entry, AND
- Sets the corresponding PlayCard's `audience.customer_ids_null_reason = SUBSTRATE_REFUSED` per RULE A.

The merchant-reputation killer is wrong customers, not zero customers. Empty audit-traceable CSV is correct behavior; silent absence is not.

### R5 — Split T1 (S13.6) into T1a (strip) + T1b (Observation.text decision)

`Observation.text` carries some downstream renderer consumption in older Tier-B paths per S6 history. Founder decision #1 says strip-all, but T1 dispatch must verify renderer non-consumption *per stripped field* before the strip lands, not as a single bundle. Two commits, two atomic flips. Minor.

### R6 — T2 (S13.6): add re-export source-of-truth note

`StoreProfile` lives at `src/profile/types.py` and `ModelCard` at `src/predictive/model_card.py` — fine. But the contract boundary MUST re-export these at `src/engine_run.py` so agents read one file. T2 brief should state: "schema authority = `src/engine_run.py`; re-export resolves to canonical type."

### R7 — Add a S13.6-T7.5 (between T7 and T8): RULE A null-reason enum registry

T7 introduces ~6-10 new enums (`SegmentNameNullReason`, `RevenueRangeSuppressionReason`, `StrategyUsedNullReason`, `MonthDeltaNullReason`, `CustomerIdsNullReason`, etc.). These deserve a single source-of-truth comment block in `engine_run.py` and a coverage test that the union of declared enums covers every Optional contract field. Small ticket; large agent ergonomic win.

---

## (d) Concrete enum values for `MechanismType`

Audited from `_PRIOR_ANCHORED` registry (`src/measurement_builder.py:721+`), Tier-B builders, and current fixture surface. **Closed set, DS-locked:**

```python
class MechanismType(str, Enum):
    WINBACK_REACTIVATION_EMAIL    # winback_dormant_cohort
    FIRST_TO_SECOND_NUDGE         # first_to_second_purchase, cohort_journey_first_to_second
    THRESHOLD_BUNDLE_OFFER        # aov_lift_via_threshold_bundle
    DISCOUNT_DEPENDENCY_HYGIENE   # discount_dependency_hygiene (suppression-style)
    REPLENISHMENT_REMINDER        # replenishment_due
    BESTSELLER_AMPLIFY            # bestseller_amplify (Tier-B)
    CATEGORY_EXPANSION            # category_expansion (Tier-B)
    SUBSCRIPTION_NUDGE            # subscription_nudge (Tier-B)
    ROUTINE_BUILDER               # routine_builder (Tier-B)
    LOOKALIKE_HIGH_VALUE_PROSPECT # if/when high-value lookalike play emits
```

**Per-type `parameters` shape (DS-locked at T3 spec doc):**
- `WINBACK_REACTIVATION_EMAIL`: `{ dormancy_window_days: int, offer_type: Literal["percent_off","dollar_off","none"], measurement_window_days: int }`
- `FIRST_TO_SECOND_NUDGE`: `{ days_since_first_order_window: [int,int], measurement_window_days: int }`
- `THRESHOLD_BUNDLE_OFFER`: `{ threshold_aov: float, current_median_aov: float }`
- `DISCOUNT_DEPENDENCY_HYGIENE`: `{ current_discount_share: float, target_discount_share: float }`
- `REPLENISHMENT_REMINDER`: `{ replenishment_window_days: int, sku_class: str }`
- Tier-B types: `parameters` empty dict acceptable for v2.0.0; flesh out at S14+ when builders are promoted out of Tier-B.

T6 refactor MUST verify by exhaustive emission audit that no current emission produces a mechanism string outside this set. If any extra appears, escalate before adding — DS gate, not refactor-engineer call.

---

## (e) RULE A pattern choice (confirmed) + Optional-by-Optional triage

**Pattern A (paired `<field>_null_reason: Optional[<Enum>]`). Confirmed.**

| Field | Needs null_reason? | Reason enum |
|---|---|---|
| `PlayCard.predicted_segment` | YES | `PredictedSegmentNullReason` = `MODAL_FLOOR_NOT_CLEARED \| SUBSTRATE_REFUSED \| AUDIENCE_TOO_SMALL` |
| `PlayCard.model_card_ref.strategy_used` | YES | `StrategyUsedNullReason` = `CHAIN_ABSTAINED \| NO_SUBSTRATE_VALIDATED` |
| `PlayCard.revenue_range` (when suppressed) | YES | `RevenueRangeSuppressionReason` = `PRIOR_UNVALIDATED \| COLD_START_NO_N_OBSERVED \| AUDIENCE_TOO_SMALL` |
| `PlayCard.audience.customer_ids` (S13.7) | YES | `CustomerIdsNullReason` = `SUBSTRATE_REFUSED \| AUDIENCE_RESOLVER_NOT_INVOKED` |
| `EngineRun.month_2_delta` | YES | `MonthDeltaNullReason` = `UNDER_21D_FLOOR \| LINEAGE_CHANGED \| NO_PRIOR_RUN` |
| `EngineRun.predictive_models[*]` (when absent for a key) | YES | `ModelCardAbsenceReason` = `SUBSTRATE_NOT_RUN \| SUBSTRATE_REFUSED \| INSUFFICIENT_DATA` |
| `EngineRun.cohort_diagnostics[*]` | YES | `CohortDiagnosticsAbsenceReason` = `INSUFFICIENT_COHORT_DEPTH \| SUBSTRATE_REFUSED` |
| `EngineRun.abstain` (when absent) | NO — unambiguous | None means "engine did not abstain"; structurally clear |
| `RejectedPlay.held_reason_detail` keys | per-key check | Most can stay bare-Optional; if `held_reason_detail.observed_effect=None`, that's a typed signal not noise |
| `EngineRun.store_profile` | YES (low priority) | `StoreProfileNullReason` = `PROFILE_NOT_LOADED \| ONBOARDING_INCOMPLETE` (matters for beta surface) |
| `EngineRun.prior_run_id` / backrefs | NO — unambiguous | Absence = no prior run; not a suppression decision |
| `Sensitivity` / `Provenance` fields when debug-stripped | NO | Stripping is a flag-level concern, not a null_reason concern |

T7 brief should pin: AST sweep ensures any **new** `Optional[X]` added to `src/engine_run.py` post-S13.6 freeze either (a) has paired `_null_reason`, or (b) is annotated `# null_reason_exempt: <justification>`.

---

## (f) Product-level questions for founder beyond IM's 6

1. **NonLiftAtom wrapper (R1 above).** This is a contract-shape decision with downstream agent implications. The wrapper changes the JSON shape of `opportunity_context` more than a flag does. Founder: approve the wrapper shape OR accept the weaker `_do_not_narrate_as_lift` flag and own the risk of agent misnarration on first run? **DS recommends wrapper.**

2. **Empty audience CSV vs no CSV under SUBSTRATE_REFUSED (R4).** Operator-facing question: does the merchant see an empty audience file in the `audiences/` folder for a SUPPRESSED PlayCard, or does that PlayCard's entry simply not materialize? **DS recommends empty CSV with header row + manifest annotation** — auditable absence > silent absence — but the operator UX call is founder's.

3. **`INCLUDE_DEBUG_FIELDS` default.** Plan defaults OFF. Confirm: founder/internal-dev runs flip it ON; merchant-handoff runs leave it OFF. If yes, document in `docs/engine_flags.md` at T8.

4. **`audience_definition_version` source.** S13.7-T1 spec references this as a RULE B trace anchor. Founder: is this version pinned at builder definition (code-version) or at run-time (config-snapshot)? DS recommends code-version (`git sha` of `src/audience_builders.py` at run time), but the choice has merchant-reproducibility implications if builder code evolves.

5. **`recommendation_text` strip is also a Pivot 2 reaffirmation.** Worth a one-line addendum at `PIVOTS.md` Pivot 2 at T8: "S13.6 ratified the strip — engine emits zero prose on contract surface."

---

## Cross-cutting confirmations

- Every ticket carries `agent_outputs/code-refactor-engineer-<ticket>-summary.md` — confirmed in plan §3 and §11.
- `Deviation check: none` on every commit — confirmed.
- Single-demote-channel preserved — confirmed; S13.5 reinforces it; S13.6 does not touch demote paths; S13.7-T1 wires resolver AFTER `apply_guardrails_to_injected`.
- `briefing.html` byte-identity preserved — confirmed at S13 close; plan correctly notes S13.6 will change `engine_run.json` SHA only.
- `pinned_sha_ledger.json` re-pin at atomic flip — confirmed in plan §13.

## Risk surface confirmation

- **S13.5: LOW** — confirmed. Invariant-preserving.
- **S13.6-T3 + T7: HIGH novelty** — mitigations adequate WITH R1 (wrapper) and R3 (triage table) applied. As-written, T3 mitigation is weak.
- **S13.7-T1: HIGHEST single-ticket risk** — mitigations adequate WITH R4 (RFM-refused branch) applied. As-written, the resolver could silently emit no file under refusal, which violates RULE A from the audience side.

## Coverage of prior verdicts

- All 4 P0 from agent-readiness verdict: covered (T2 types Any; T1 strips prose; T3 OpportunityContext; S13.5 KI-NEW-L).
- All 7 P1 from agent-readiness verdict: covered.
- All 3 end-to-end-flow tickets: covered.
- `src/segments.py` hard-cut: covered, with R4 AST-grep prerequisite.
- "Engine produces immutable runs; approval state is agent-DB concern" at S13.7-T4: covered.

---

**End of verdict. APPROVE-WITH-CHANGES — proceed to v2 IM plan incorporating R1–R7 + section (d) enum lock + section (e) triage table.**
