# G-2 — `empty_bottle` parser unit-coherence (vertical_applicable filter)

**Owner:** code-refactor-engineer
**Date:** 2026-05-09
**Sprint:** Sprint 1 (Engineer B track, GA blocker; recommended path b — filter, not full parser)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §1, ticket G-2
**Audit reference:** [agent_outputs/post-6b-stop-coding-audit.md](./post-6b-stop-coding-audit.md) §G-2
**Status:** Complete; full suite green; M0 Beauty pinned fixture byte-identical.

---

## Scope delivered

Per the audit's two options, shipped option (b) — vertical-dispatched parser + `vertical_applicable` filter — and explicitly deferred the supplements unit-coherent parser to Sprint 4 G-3. The dispatcher is a thin loader so Sprint 4 only needs to fill in the `supplements` YAML block.

## Files changed

| File | Change |
|---|---|
| [config/replenishment_sizes.yaml](../config/replenishment_sizes.yaml) | NEW per-vertical regex configuration (Beauty/mixed verbatim, supplements stub `null`) |
| [src/replenishment_parser.py](../src/replenishment_parser.py) | NEW thin pure-function loader (~95 lines including docstrings) |
| [src/action_engine.py](../src/action_engine.py) | `_targeted_skus_for_play` for `empty_bottle` (line 1698) refactored to use the dispatched regex; vertical resolved from `cfg` |
| [src/play_registry.py](../src/play_registry.py) | `empty_bottle.vertical_applicable` restricted from `_ALL_VERTICALS` to `frozenset({"beauty", "mixed"})` |
| [tests/test_g2_empty_bottle_vertical_dispatch.py](../tests/test_g2_empty_bottle_vertical_dispatch.py) | NEW — 9 tests across the three contracts |

## Three contracts pinned

1.  **Vertical-dispatched parser:** Beauty / mixed return the verbatim pre-G-2 regex; supplements / unknown return `None`. Beauty regex is byte-identical to the inline string at the previous line 1698 of `action_engine.py`.
2.  **Vertical-applicable filter:** `empty_bottle.vertical_applicable == frozenset({"beauty", "mixed"})`. The pre-existing decide.py:614 filter consumes this set and clean-skips the play upstream of reason-code assignment.
3.  **End-to-end behavior:** Beauty fixture continues to surface `empty_bottle` in Considered exactly as before (parser coverage exists). Supplements scenario clean-skips it from every surface (Recommended / Recommended Experiment / Considered) — no misleading `no_measured_signal` Considered card any more.

## Beauty regex — verbatim preservation

```
30ml|1 oz|1oz|50ml|1.7 oz|1.7oz|100ml|3.4 oz|3.4oz
```

Preserved bit-for-bit from the pre-G-2 inline regex at `action_engine.py:1698`. The YAML block is documented as "M0 byte-identical contract — refresh the pin in the same commit if you change this regex." A test (`test_replenishment_parser_beauty_returns_verbatim_pre_g2_regex`) pins the exact string.

## Supplements stub design

`config/replenishment_sizes.yaml::supplements.size_regex = null`. Documented inline as Sprint 4 G-3 work. The `empty_bottle.vertical_applicable` filter ensures this branch is unreachable in production today; the YAML stub merely advertises the gap explicitly so a future contributor doesn't accidentally fall back to the Beauty regex on a supplements run.

## Defensive layering

The parser dispatch and the registry filter are independent guards:

- If the registry filter is silently widened (e.g., someone re-adds `supplements` to `vertical_applicable` without writing the parser), `_targeted_skus_for_play` still returns `[]` because the dispatcher returns `None` for supplements. No misleading SKU targeting.
- If the parser is somehow called directly bypassing the registry filter, the dispatcher's `None` return is the safe fallback.

Both surfaces would need to regress simultaneously for a misleading supplements `empty_bottle` to ship.

## Hard constraints respected

- `engine_run.json` schema unchanged.
- M0 Beauty pinned fixture byte-identical (regex preserved verbatim; only supplements behavior changed).
- `engine_run.json` for Beauty: identical considered list including `empty_bottle`.
- Vertical scope hard-lock untouched (B-7 still refuses non-supported verticals at engine entry).
- No banned ML scaffolding.
- Engine remains runnable after every patch.

## Test results

| Suite | Result |
|---|---|
| `tests/test_g2_empty_bottle_vertical_dispatch.py` | 9/9 |
| **Full suite** | **975 passed, 14 skipped, 0 failed** (~4 min 24 s) |

## Out of scope (deliberately not touched)

- Supplements count / lb / mg / serving-per-container parser — Sprint 4 G-3 will fill in `config/replenishment_sizes.yaml::supplements.size_regex` and re-add `supplements` to `empty_bottle.vertical_applicable`. The dispatch surface is in place; G-3 is just data.
- Other Beauty-flavored size logic at `src/segments.py:176-180` and `src/action_engine.py:3591-3636` — tied to a different code path (segment building, `_calculate_28d_revenue`) that is M10 deletion territory or vertical-bound by other means. Per the ticket's "pick whichever path is smaller" recommendation, only the audit's specific target (line 1698) was refactored.
- Apparel / food / home vertical refusal — already covered by B-7 (Engineer A's ticket, landed earlier).
- Any change to the Beauty regex itself — outside G-2's scope; would need a separate goldens-refresh ticket.

## Risks observed (none unresolved)

- **Supplements customer impact:** before G-2, supplements scenarios saw `empty_bottle` in Considered with `no_measured_signal` (which was misleading — the parser returned audience=0 silently because the regex didn't match supplement product names). After G-2, `empty_bottle` is absent. If a downstream consumer (Swarm Brief renderer?) hard-codes an expectation that `empty_bottle` always appears in the Considered list for some role, that breaks. None known today; the Considered list is a flexible-membership surface.
- **Cache invalidation:** the parser caches the YAML at module import. If a test mutates the YAML on disk, it would not see the change. `_reset_cache_for_tests()` is exposed for that case but is not used today (no test mutates the YAML).

## Commit shape

Single commit (`b63a9b6`) for the ticket, separate commit for `memory.md` (`dff535f`).

## Next ticket

This is the LAST ticket on the Engineer B Sprint 1 track. All five (B-1, B-3, B-5, B-6, G-2) shipped. Engineer A's track (B-4/S-1 done; B-7 in flight; G-7 next) reconciles with this branch in a single founder-led merge once both tracks are green.
