# DS Architect Verdict — T6 priority_prepend gap (2026-05-23)

**Author:** ecommerce-ds-architect
**Scope:** Verdict-only. No code edits. Responds to T5.5 probe empirical finding (aov_bundle vanishes when T6 gate fires because eligibility_rejects channel lacks priority_prepend protection).

---

**Q1 — Pick the fix: Option X.** Generalize `priority_prepend` to cover `eligibility_rejects`, and by the same change `prior_unvalidated_rejects` + `window_disagreement_rejects` (see Q4). Rationale, one verdict per criterion bundled: (a) honest-placement — X preserves `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` as the merchant-visible reason (the truthful gate verdict emitted at `src/decide.py:1674`); Y rewrites it to `CAP_EXCEEDED` which is mechanically true but diagnostically empty. (b) Cleanest precedent — X is literally the same shape the C1 mechanism established at `src/decide.py:2412-2414` and `:343-410`; it extends, doesn't relocate. (c) Smallest scope — X is the ~20-line partition + new `assemble_considered` kwarg the agent described; Y reorders the gate vs `rank_recommendations` at `src/decide.py:2185-2195` and forces re-deriving Tier-B status post-tail, which is the larger refactor. (d) Architectural drift — X codifies the invariant once at the assembly seam so any future demote channel inherits coverage by routing into the same partition; Y leaves three already-existing sibling channels (Q4) still uncovered. **Verdict: X.**

**Q2 — Yes, restate the invariant.** The 2026-05-22 single-demote-channel invariant was correct but underspecified. The complete statement is: *"Every drop produces a typed RejectedPlay through one demote channel, AND any demoted card whose original PlayCard carried `would_be_measured_by is not None` (Tier-B prior-anchored) MUST be emitted into Considered ahead of `pre_existing` so the `[:MAX_CONSIDERED_RENDERED]=6` truncation at `src/decide.py:assemble_considered` cannot silently drop it — regardless of which channel demoted it."* I own this gap: my T6 verdict named the gate but not the assembly seam. The pattern is now twice-observed (C1 → bb9fd32; T6 → this verdict); the restated invariant must land in `ARCHITECTURE_PLAN.md` as part of the X fix commit.

**Q3 — Extend the test alongside the fix, not before.** Red-test-first is the correct general discipline, but here the scope expands per Q4 to three channels, not one. A single test commit asserting "Tier-B card demoted via {eligibility_gate, prior_unvalidated, window_disagreement} survives a flood of 12+ `pre_existing` rejections in the rendered slate" — parameterized across all three routing helpers in `tests/test_s7_6_c1_priority_prepend_invariant.py` — is the right unit. Land it in the same commit as the wiring change. Red-test-first across three sibling channels would force three separate broken-CI windows at sprint-close with no diagnostic gain.

**Q4 — Yes, two more channels have the same gap.** Both `prior_unvalidated_rejects` (built at `src/decide.py:1428-1439`, routed at `_route_prior_unvalidated_holds`) and `window_disagreement_rejects` (built at `src/decide.py:1325-1336`, routed at `_route_window_disagreement_holds`) flow into the `pre_existing` slot of `assemble_considered` at the merge points `src/decide.py:2418-2422`, `:2363-2369`, and `:2237-2242` — none participate in the `priority_prepend` partition computed at `:2412-2414`, which is derived **only** from `tail` (cap-exceeded). Worse: the original PlayCard is discarded inside each routing helper (only a `RejectedPlay` survives), so `would_be_measured_by` cannot be re-derived downstream. The X fix must (a) have each routing helper return `(kept, refused_rejected_plays, refused_priority_cards)` or carry `would_be_measured_by` onto `RejectedPlay`, and (b) partition all three reject streams into the `priority_prepend` slot at the assembly seam. Cover all three in one commit.

**Q5 — Option X meets the founder criterion; Option Y does not.** Honest placement requires both visibility AND truthful reason. Under X the aov_bundle card lands in Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` (the gate's actual verdict at `src/decide.py:1674`) — merchant sees "the L28 vs L28_band joint test failed", which is the true reason it was held. Under Y the card lands with `CAP_EXCEEDED` — mechanically accurate but the underlying signal-noise reason is lost; merchant sees "slate was full" and cannot distinguish "we don't trust this signal yet" from "we trusted three other plays more". For a founder whose differentiator is "evaluated honestly for each merchant", that diagnostic collapse is the exact failure mode the slate is meant to prevent. **X is honest; Y is technically visible but diagnostically dishonest.**

---

**Refactor agent should implement Option X, extended to cover `eligibility_rejects`, `prior_unvalidated_rejects`, and `window_disagreement_rejects` in one commit with the parameterized Q3 test — no other deviation.**

---

**Key file paths referenced:**
- `src/decide.py` (lines 343-410, 1325-1336, 1428-1439, 1671-1690, 2185-2195, 2363-2369, 2412-2422, 2237-2242)
- `tests/test_s7_6_c1_priority_prepend_invariant.py`
- `ARCHITECTURE_PLAN.md`
