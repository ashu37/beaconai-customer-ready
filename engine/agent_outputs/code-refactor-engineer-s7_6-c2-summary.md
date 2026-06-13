# S7.6-C2 — apply_guardrails_to_injected helper — restore single-demote-channel invariant

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `6d248fd`

---

## 1. Ticket scope

Replace the T7-FIX materiality-only re-invocation block (`6f8b891`) with a unified helper running **inventory + materiality + cannibalization + portfolio-cap + recently-run** (when flag ON) on cards injected by V2 prior-anchored builders at `src/main.py:1380-1597`. Restores the day-1 contract: every drop produces a typed RejectedPlay through one demote channel.

Helper is forward-correct insurance for cannibalization/inventory cases on real-merchant data (per DS verdict `afb1fb2f81eebf88f`, 2026-05-22). On current synthetic Beauty + Supplements pinned fixtures the helper is empirically inert — injected Tier-B cards clear all gates; briefings stay byte-identical.

Without this helper, the CLAUDE.md 2026-05-22 single-demote-channel invariant has no callable target. Next agent adding a sixth injection block would have nothing to import, and the bypass-then-patch pattern returns silently — the exact failure class `bb9fd32` just closed.

Founder ICP (small DTC merchants, ~50 SKU catalogs) will trigger the cannibalization/inventory gates on injected Tier-B cards within days-to-weeks of beta launch per DS analysis.

## 2. Files changed

- `src/guardrails.py` (+141 lines): `apply_guardrails_to_injected` helper exported.
- `src/main.py` (+121/-60 lines): five V2 prior-anchored injection blocks (`main.py:1380-1597`) re-route through the new helper.

## 3. Behavior change

Beauty briefing.html sha256: **byte-identical**.
Supplements briefing.html sha256: **byte-identical**.
M0 byte-identical confirmed.

Empirically inert on synthetic fixtures; forward-correct on real-merchant data.

## 4. Tests added / modified

Not explicitly recorded in commit message. The C1 xfail invariant tests (`test_considered_truncated_count_zero_on_beauty/_on_supplements`) were targeted by C2 as their flip-to-xpass criterion per the C1 contract; C2's commit does not call out the xfail status transition explicitly.

## 5. Risks + mitigations

- **Single-demote-channel invariant DS-locked 2026-05-22.** This commit is the **origin of the DS-locked invariant**: any new builder must route through `apply_guardrails_to_injected`. No new injection block at `src/main.py:1380-1597` is permitted without explicit founder + DS sign-off documented in the architectural plan. Subsequent CLAUDE.md text (2026-05-22 lock) memorializes this requirement.
- **Empirically inert today** — pin tests + invariant tests prevent silent regression when real-merchant data activates the cannibalization / inventory channels.

## 6. Follow-ups / known-issues opened

- **CLAUDE.md handoff discipline** updated at C3 (`d6053d0`) to memorialize the invariant.
- **KI-NEW-L** (opened at C3): collapse the 5 V2 prior-anchored injection blocks into a single `_PRIOR_ANCHORED` dispatch — broader cleanup of the surface this helper hardens.

## 7. Commit ref

`6d248fd`
