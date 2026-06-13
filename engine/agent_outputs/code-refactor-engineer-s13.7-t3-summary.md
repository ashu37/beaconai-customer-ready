# code-refactor-engineer — S13.7-T3 summary

**Ticket:** S13.7-T3 — `docs/mechanism_contract.md` (documentation-only)
**Date:** 2026-06-01
**Status:** COMPLETE

## Scope

Documentation-only ticket. Create `docs/mechanism_contract.md` — the single file that narration agents and assembly agents code against to understand the meaning and parameter shape of every `MechanismType` value. DS-locked at S13.6-T6; doc deferred to S13.7-T3 per DS adjudication #5.

## Patch summary

Created `docs/mechanism_contract.md` (193 lines, 11KB). No Python files touched. No tests added (doc-only ticket per ticket constraints).

## Files changed

| File | Change |
|---|---|
| `docs/mechanism_contract.md` | NEW — mechanism contract spec for all 10 `MechanismType` values. |
| `agent_outputs/code-refactor-engineer-s13.7-t3-summary.md` | NEW — this file. |

## Parameter key cross-check: DS §(d) vs `src/decide.py::_parameters_for_mechanism`

Cross-checked all 5 spec'd types after the DS Q5 revision (2026-06-01) that rewrote the 4 mismatched types. Result: **zero mismatches found.**

| Type | DS §(d) keys | Code keys | Match |
|---|---|---|---|
| `WINBACK_REACTIVATION_EMAIL` | `dormancy_window_days`, `offer_type`, `measurement_window_days` | `dormancy_window_days`, `offer_type`, `measurement_window_days` | YES |
| `FIRST_TO_SECOND_NUDGE` | `days_since_first_order_window`, `measurement_window_days` | `days_since_first_order_window`, `measurement_window_days` | YES |
| `THRESHOLD_BUNDLE_OFFER` | `threshold_aov`, `current_median_aov` | `threshold_aov`, `current_median_aov` | YES |
| `DISCOUNT_DEPENDENCY_HYGIENE` | `current_discount_share`, `target_discount_share` | `current_discount_share`, `target_discount_share` | YES |
| `REPLENISHMENT_REMINDER` | `replenishment_window_days`, `sku_class` | `replenishment_window_days`, `sku_class` | YES |
| Tier-B + LOOKALIKE | `{}` | `{}` | YES |

The 4 types that had mismatches pre-Q5 revision (`FIRST_TO_SECOND_NUDGE`, `THRESHOLD_BUNDLE_OFFER`, `DISCOUNT_DEPENDENCY_HYGIENE`, `REPLENISHMENT_REMINDER`) were corrected in the DS Q5 revision committed on 2026-06-01. This contract doc captures the post-revision state as the canonical record.

**Values note:** `THRESHOLD_BUNDLE_OFFER`, `DISCOUNT_DEPENDENCY_HYGIENE`, and `REPLENISHMENT_REMINDER` carry `None` values for all keys (with `TODO(S14)` markers in code) because the decide-seam does not yet have the per-merchant sources. This is accurately reflected in each per-type entry in the contract file with an `Implementation note` callout.

## Tests run

None — doc-only ticket, no test run required per ticket constraints.

## Behavior changes

None — no Python source files were modified.

## Artifacts added

- `/Users/atul.jena/Projects/Personal/beaconai/docs/mechanism_contract.md` (193 lines, 11KB)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s13.7-t3-summary.md` (this file)

## Remaining risks

1. `THRESHOLD_BUNDLE_OFFER`, `DISCOUNT_DEPENDENCY_HYGIENE`, and `REPLENISHMENT_REMINDER` have `None` values in their `parameters` dicts. Narration agents reading this contract will see the correct keys but `None` values. The contract file includes `Implementation note` callouts on each type warning agents to guard against `None`. This is the correct honest posture per DS Q5 revision.
2. `LOOKALIKE_HIGH_VALUE_PROSPECT` has no active emission site at v2.0.0 — the contract documents the type for completeness per DS §(d) inclusion.

## Follow-up work

- **S14+:** Wire `threshold_aov` / `current_median_aov` from the per-merchant bundle target and store_profile AOV to the `THRESHOLD_BUNDLE_OFFER` mechanism parameters.
- **S14+:** Wire `current_discount_share` / `target_discount_share` from `measurement_builder.compute_heavy_discount_share_of_revenue` to the `DISCOUNT_DEPENDENCY_HYGIENE` mechanism parameters.
- **S14+:** Wire `replenishment_window_days` / `sku_class` from the per-SKU cadence builder seam to the `REPLENISHMENT_REMINDER` mechanism parameters.
- **S14+:** Flesh out Tier-B mechanism parameter shapes and promote `LOOKALIKE_HIGH_VALUE_PROSPECT` to an active emission site.
- **S13.6-T8:** Rewire `storytelling_v2._render_what_we_send` + `_mechanism_for_play` to compose copy from `PlayCard.mechanism_intent` typed atom directly, retiring the YAML-string lookup.

## Deviation check: none
