# S-1.7 — Vertical Resolution Hardening

**Owner:** code-refactor-engineer (Engineer B)
**Date:** 2026-05-09
**Sprint:** Sprint 2 prelude (single commit, ~30–60 min budget)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §2, ticket S-1.7
**Status:** Complete; full suite green; M0 Beauty pinned fixture byte-identical.

---

## Scope delivered

S-1.7 surfaced during Sprint 1 merge manual-validation (founder, 2026-05-09). Two correctness bugs in vertical resolution were silently undermining B-7's hard-refuse contract. The ecommerce-ds-architect review confirmed they are correctness issues, not hygiene.

1. **Bug 1: `get_vertical_mode()` laundered unknown verticals into `'mixed'`.** Any input outside `{beauty, supplements, mixed}` (e.g. `apparel`, `food`, `home`, `wellness`) was silently rewritten to `'mixed'`. Because `'mixed'` is in `SUPPORTED_VERTICALS`, B-7's vertical_guard never fired for these inputs — the engine ran on mixed priors instead of refusing. **This defeated the B-7 hard-refuse contract.**
2. **Bug 2: manual `.env` fallback overrode exported env vars.** When `python-dotenv` is missing, `src/utils.py:14-27` did `os.environ[k] = v` unconditionally. Exported `VERTICAL_MODE=beauty` would be clobbered by `.env`'s `VERTICAL_MODE=apparel`. Documented as a known caveat in `memory.md:912` (Synthetic Blocker Fix 6) but never closed.
3. **Two regression tests + one grep guard** pin the fix end-to-end so a future refactor can't silently re-introduce the laundering.
4. **M0 Beauty pinned fixture stays byte-identical** — Beauty is in the supported set, so the only behavior change is for unsupported verticals which never used to reach this fixture.

## Files changed

| File | Change |
|---|---|
| [src/utils.py](../src/utils.py) | `get_vertical_mode()` — pass through unknown verticals as-is (lowercased + stripped); default when env unset stays `'mixed'`. Manual `.env` fallback — assignment changed from `os.environ[k] = v` to `os.environ.setdefault(k, v)`. |
| [tests/test_s1_7_vertical_resolution.py](../tests/test_s1_7_vertical_resolution.py) | NEW — 12 tests pinning pass-through behavior, end-to-end B-7 refusal via env, `.env` setdefault semantics, and a grep guard. |

## Two bugs + fixes

### Bug 1 — `get_vertical_mode()` laundering

**Before:**
```python
def get_vertical_mode() -> str:
    v = os.getenv('VERTICAL_MODE') or os.getenv('VERTICAL') or 'mixed'
    v = str(v).strip().lower()
    return v if v in VERTICAL_CONFIG else 'mixed'  # <-- silent laundering
```

**After:**
```python
def get_vertical_mode() -> str:
    """Return vertical mode from env, lowercased and trimmed.

    S-1.7: pass through unknown verticals as-is rather than laundering
    them into ``'mixed'``. The B-7 vertical_guard at the engine entry
    boundary is the single point of refusal for unsupported verticals.
    """
    v = os.getenv('VERTICAL_MODE') or os.getenv('VERTICAL') or 'mixed'
    return str(v).strip().lower()
```

**Why pass-through is safe at every caller site:** every downstream consumer (`get_vertical()`, `get_window_weights()`, `subscription_threshold_for_product()`, `action_engine.py` callers) already uses `VERTICAL_CONFIG.get(mode, VERTICAL_CONFIG['mixed'])` as a graceful default — the dictionary lookup falls back to mixed config for any unknown key, so passing through `'apparel'` doesn't crash anything. The point of the fix is to preserve the **information** (the actual vertical the user asked for) up to the B-7 guard's `is_supported()` check, which now correctly rejects it.

### Bug 2 — `.env` fallback overriding exported env vars

**Before:**
```python
key, value = line.split('=', 1)
os.environ[key.strip()] = value.strip()  # <-- overrides exported value
```

**After:**
```python
key, value = line.split('=', 1)
os.environ.setdefault(key.strip(), value.strip())  # <-- exported wins
```

This closes the synthetic-fix-6 caveat at `memory.md:912`. Local dev workflow no longer needs the documented workaround of "running subprocesses from an `.env`-free cwd with `PYTHONPATH` set to repo root."

## Tests

`tests/test_s1_7_vertical_resolution.py` — 12 tests:

| # | Test | Asserts |
|---|---|---|
| 1–7 | `test_get_vertical_mode_does_not_launder_unknown_to_mixed[…]` (parametrized over `apparel`, `food`, `food_bev`, `home`, `wellness`, `Apparel`, ` APPAREL `) | Result equals normalized input (lowercased + stripped); is NOT in `SUPPORTED_VERTICALS`. |
| 8 | `test_get_vertical_mode_default_is_mixed_when_unset` | No env var → `'mixed'` (default preserved). |
| 9 | `test_get_vertical_mode_passes_supported_through` | `beauty`, `supplements`, `mixed` pass through. |
| 10 | `test_vertical_mode_apparel_via_env_triggers_b7_abstain_hard` | End-to-end via `main.run`: `engine_run.json` carries `abstain_hard` + `vertical_not_supported` flag; no slate; no briefing rendered. |
| 11 | `test_manual_env_fallback_does_not_overwrite_exported_var` | Pre-exported `VERTICAL_MODE=beauty` survives `.env`'s `VERTICAL_MODE=apparel`; un-exported `UNUSED_VAR` still loads from `.env`. |
| 12 | `test_no_unsupported_vertical_mode_in_test_suite` | Grep guard: no test file outside the B-7 allowlist sets `VERTICAL_MODE` to `apparel|food|food_bev|home|wellness`. Expected zero offenders. |

## Hard constraints respected

- `engine_run.json` schema **unchanged** (no new fields, no removed fields).
- M0 Beauty pinned fixture **byte-identical** — verified via `tests/test_slate_regression_beauty_brand.py::test_briefing_matches_pinned_fixture_bytewise`.
- B-7 vertical_guard contract **strengthened, not changed** — same `is_supported()` surface, same refusal payload, same merchant-facing copy.
- `RECENTLY_RUN_FATIGUE_ENABLED` and other flags untouched.
- No substrate work (S-2+ scope).
- No banned ML scaffolding (D-6).
- Engine remains runnable after the patch.
- Single-writer-per-event-type discipline preserved (no event-type writers added).

## Acceptance results

| Suite | Result |
|---|---|
| `tests/test_s1_7_vertical_resolution.py` | 12/12 |
| `tests/test_vertical_hard_refuse.py` (B-7) | 21/21 |
| `tests/test_slate_regression_beauty_brand.py` (M0) | 19/19 (byte-identical) |
| **Full suite** | **1047 passed, 14 skipped, 0 failed** (~5 min) |

## Out of scope (deliberately deferred)

- **Per-merchant `store_profile.vertical` resolver** — architectural recommendation surfaced by ecommerce-ds-architect review; folds into S-2's per-merchant substrate work, NOT this ticket.
- **M10 collapse of legacy `VERTICAL_MODE` env paths** — Phase 9.
- **Renaming `VERTICAL` env var (legacy)** — kept for backward compat; deprecation is a Phase 10+ cleanup.
- **Any change to `vertical_guard.is_supported()` or `MERCHANT_FACING_REFUSAL_COPY`** — surface is correct as-is; the bug was upstream of the guard, not in it.

## Commit shape

Single commit on `sprint2-engineer-b`:

```
46713bb S-1.7: harden vertical resolution (no laundering + .env setdefault)
```

The per-ticket-ritual companion commits (memory.md update + this summary file) follow as separate documentation-only commits per the established repo pattern (B-1, B-3, B-5, B-6, G-2 all shipped this way).

## Next ticket

S-3 prep (NON-merging, branch only): reason-code fan-out + typed event schemas. Stubs the wire-up for the substrate event emission path; awaits Engineer A's S-2 (substrate writer + lineage helper) before final S-3 wiring can land.
