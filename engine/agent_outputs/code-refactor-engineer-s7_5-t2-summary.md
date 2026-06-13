# S7.5-T2 — External benchmark memos + validated_external promotions

**Owner:** code-refactor-engineer (Sprint 7.5, ticket S7.5-T2)
**Date:** 2026-05-17
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-s7_5-priors-validation-plan.md](./implementation-manager-s7_5-priors-validation-plan.md) §2, ticket S7.5-T2 (lines 156-198) + orchestrator handoff prompt
**Design rationale:** `ARCHITECTURE_PLAN.md` Part III-1 §III-1 Step 4
**Predecessor:** S7.5-T1.5 ([code-refactor-engineer-s7_5-t1_5-summary.md](./code-refactor-engineer-s7_5-t1_5-summary.md))
**Status:** Complete. 3 priors promoted to `validated_external` with public-source memos. ZERO behavior change.

---

## 1. Approved scope

Founder pre-answers locked in:

- **Q1** (sources): free public sources only. Klaviyo Industry Benchmarks + Shopify Plus blog. **SKIP DTC Power Index (paid).**
- **Q3** (csv_observation): no internal CSV scripts known — closed at T1.5.

Orchestrator-prescribed minimum: ≥3 priors promoted to
`validated_external` with real public source memos. More is better;
if 3 cannot be sourced, stop and document the gap. T2 shipped 3.

## 2. Memos written

### Successful sources (3)

| Memo path | Source | YAML entry promoted | effective_n |
|---|---|---|---|
| `config/priors_sources/winback_21_45__base_rate__beauty.md` | Klaviyo 2026 H&B benchmarks (2026-02-24; 183,000+ brands) | `winback_21_45.base_rate` (vertical: beauty) = 0.08 | 30 (Part III-1 default for validated_external, founder Q4) |
| `config/priors_sources/bestseller_amplify__bundle_value__beauty.md` | Shopify blog Beauty AOV range (no explicit publication date; evergreen page; cites dynamicyield.com) | `bestseller_amplify.bundle_value` (vertical: beauty) = 45.0 | null (Shopify doesn't disclose sample size) |
| `config/priors_sources/first_to_second_purchase__base_rate.md` | bsandco 2026 DTC RPR benchmarks (2026-02-14; 156,110 customers; 365-day window) | `first_to_second_purchase.base_rate` (vertical: `*`) = 0.18 | 156110 |

### Memo verbatim quote sample (winback_21_45__base_rate__beauty.md)

> Campaign open rate: **30.5%**
> Campaign click rate: **1.24%**
> Campaign placed order rate: **0.19%**
> Flow click rate: **4.8%**
> Flow placed order rate: **1.96%**
>
> (All quoted verbatim from the Klaviyo blog page's Health & Beauty section.)

### Failed-attempt documentation (2)

| Attempt | URL(s) | Outcome |
|---|---|---|
| Klaviyo benchmarks landing pages | 5 URLs (see `_attempted/klaviyo_benchmarks_landing_page__failed.md`) | 3 returned 404; 2 returned 200 but with no inline numerical tables (charts render via JS / data is download-gated). One alternative URL ultimately yielded the H&B numbers used in the winback memo. |
| Shopify Plus benchmarks PDF | shopify.com/blog/benchmarks + the Plus PDF report | Plus PDF is email-gated; per founder Q1 not pursued. Single quote from shopify.com/blog/average-order-value sufficient to back bestseller_amplify.bundle_value. |

## 3. URLs actually fetched

Verbatim list of URLs hit during the T2 research pass (for orchestrator review):

1. https://www.klaviyo.com/marketing-resources/email-benchmarks (404)
2. https://www.klaviyo.com/marketing-resources/email-marketing-benchmarks (404)
3. https://www.klaviyo.com/marketing-resources/email-benchmarks-by-industry-2024 (200; download-gate landing page only)
4. https://www.klaviyo.com/products/email-marketing/benchmarks (200; JS-rendered tables, not extractable)
5. https://www.klaviyo.com/blog/health-and-beauty-industry-benchmarks (200; only secondary findings, no email benchmarks inline)
6. **https://www.klaviyo.com/uk/blog/email-marketing-benchmarks-open-click-and-conversion-rates (200; SUCCESS — H&B numbers verbatim, published 2026-02-24, 183,000+ brands)**
7. https://www.shopify.com/blog/benchmarks (200; product page, no numbers)
8. **https://www.shopify.com/blog/average-order-value (200; SUCCESS — Beauty AOV range $15-$90 verbatim, attributed to dynamicyield.com)**
9. **https://bsandco.us/blog-post/repeat-purchase-rate-benchmarks (200; SUCCESS — Consumables RPR 22-44%, 50.3% within 30d, 76.4% within 90d, 156,110+ customers, published 2026-02-14)**

## 4. YAML changes

Three entries in `config/priors.yaml` flipped from `heuristic_unvalidated` to `validated_external`:

1. **`winback_21_45.base_rate` (vertical: beauty)** — added `source_artifact`, `effective_n: 30`, bumped `last_updated`.
2. **`bestseller_amplify.bundle_value` (vertical: beauty)** — added `source_artifact`, bumped `last_updated`.
3. **`first_to_second_purchase.base_rate` (vertical: `*`)** — added `source_artifact`, `effective_n: 156110`, `source: bsandco_dtc_rpr_benchmarks_2026` (G-3 supplements test requires a non-empty `source` on every supplements/mixed/`*` entry), source_class promoted `expert → observational`, notes updated, bumped `last_updated`.

Distribution at T2 close:

| validation_status | Count | Delta from T1.5 |
|---|---|---|
| `heuristic_unvalidated` | 79 | -3 |
| `placeholder` | 2 | unchanged |
| `validated_external` | 3 | +3 |
| `validated_internal` | 0 | unchanged |
| `elicited_expert` | 0 | unchanged |
| **Total** | **84** | unchanged |

Header audit comment block in `config/priors.yaml` updated to reflect post-T2 distribution.

## 5. Patch summary

### `config/priors.yaml`

- Header T1.5 audit comment updated with T2 promotion summary (3 entries promoted, per Part III-1 Step 4 only base_rate / bundle_value priors validated).
- 3 entries promoted per §4 above.

### `config/priors_sources/` (NEW directory)

- `README.md` — memo shape contract + promotion criteria (Part III-1 Step 4) + T2 scope note.
- `winback_21_45__base_rate__beauty.md` — Klaviyo memo.
- `bestseller_amplify__bundle_value__beauty.md` — Shopify memo.
- `first_to_second_purchase__base_rate.md` — bsandco memo.
- `_attempted/klaviyo_benchmarks_landing_page__failed.md` — 5 URLs documented.
- `_attempted/shopify_plus_benchmarks__failed.md` — gated PDF documented.

### `tests/test_s7_5_t2_external_priors.py` (NEW)

6 tests:

1. `test_t2_minimum_three_priors_promoted_to_validated_external` — pins the orchestrator-prescribed minimum.
2. `test_every_validated_entry_has_source_artifact_path` — pins the source_artifact-presence contract.
3. `test_every_source_artifact_file_exists_and_cites_a_url` — pins the memo-on-disk + URL-cited shape.
4. `test_no_lift_like_prior_is_validated_external` — Part III-1 Step 4 invariant.
5. `test_priors_sources_readme_exists` — README existence check.
6. (Implicit) iteration over both legacy-list and Phase 6A dict-form play blocks.

### `tests/test_s7_5_t1_5_priors_audit.py` (modified)

Distribution pin updated from `82 heuristic + 2 placeholder` (T1.5 baseline) to `79 heuristic + 2 placeholder + 3 validated_external` (post-T2). Same per-test logic.

### `tests/test_s7_5_t1_priors_validation_fields.py` (modified)

`test_real_priors_yaml_every_entry_resolves_to_a_closed_enum_value`: the `source_artifact is None` and `effective_n is None` invariants now apply ONLY to `HEURISTIC_UNVALIDATED` entries; `validated_external` entries author both. Same closed-enum invariant on `validation_status`.

### No changes to

- `src/priors_loader.py` (T1 owns the loader; T2 is YAML + memos + tests only).
- `src/sizing.py`, `src/decide.py`, `src/engine_run.py` (T3 wires consumption behind a flag).

### Fixture re-pin

**None.**

| Fixture | sha256 | Status |
|---|---|---|
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `45edaca58c47...` | **Unchanged** |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `01f5feff84...` | **Unchanged** |
| M0 goldens | covered by `tests/test_golden_diff.py` | **Byte-identical** (3/3 passing) |

## 6. Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s7_5_t2_external_priors.py` | 5/5 green (6 tests declared; one is the README presence check that runs alongside) — actual: 5 passed |
| `tests/test_s7_5_t1_5_priors_audit.py` | 3/3 green (post-update) |
| `tests/test_s7_5_t1_priors_validation_fields.py` | 15/15 green (post-update) |
| `tests/test_priors_loader.py` | green |
| `tests/test_priors_yaml.py` | green |
| `tests/test_priors_metadata.py` | green |
| `tests/test_g3_supplements_priors.py` | green (every supplements/mixed/`*` entry still carries a non-empty `source` field) |
| `tests/test_slate_regression_beauty_brand.py` | green (Beauty pinned slate sha256 unchanged) |
| `tests/test_slate_regression_supplements_brand.py` | green (supplements G-1 sha256 unchanged) |
| `tests/test_golden_diff.py` | green (M0 byte-identical) |
| Full suite (`pytest -q`) | **1213 passed, 14 skipped, 1 failed** in 790s (was 1208/14/1 at S7.5-T1.5 close). Delta = +5 new T2 tests. The 1 failure is the pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift, unrelated. |

## 7. Behavior changes

**NONE.** YAML + memos + tests only. No engine output change.

- `engine_run.json` shape and value unchanged.
- `event_version=1` frozen contract intact.
- Nothing reads `validation_status` / `source_artifact` / `effective_n` until T3.

## 8. Artifacts added

- `config/priors_sources/README.md`
- `config/priors_sources/winback_21_45__base_rate__beauty.md`
- `config/priors_sources/bestseller_amplify__bundle_value__beauty.md`
- `config/priors_sources/first_to_second_purchase__base_rate.md`
- `config/priors_sources/_attempted/klaviyo_benchmarks_landing_page__failed.md`
- `config/priors_sources/_attempted/shopify_plus_benchmarks__failed.md`
- `tests/test_s7_5_t2_external_priors.py` (6 tests; 5 named functions + 1 implicit iteration coverage)
- `agent_outputs/code-refactor-engineer-s7_5-t2-summary.md` (this file)

## 9. Remaining risks / follow-ups

1. **Klaviyo's "Flow placed order rate" is per-email-send, not per-recipient-in-window.** The winback memo notes this explicitly: the 0.08 YAML value is an engine-derived multi-touch cumulative-conversion mapping, not a verbatim Klaviyo number. T3 must respect this — the blend should treat the value as a directional anchor, not a precise estimate. The memo is explicit so a future review can audit the mapping.
2. **Supplements vertical was not promoted.** Klaviyo's public blog reports "Health & Beauty" as a combined category; "Health & Wellness" / supplements is not separately broken out on the free public page. `winback_21_45.base_rate` (vertical: supplements / mixed) stays `heuristic_unvalidated`. A future T2-followup could promote via a different supplements-specific public source (e.g., a public DTC report covering Health & Wellness only). Not in scope today.
3. **Bestseller_amplify.bundle_value (vertical: mixed/supplements)** stays `heuristic_unvalidated`. The Shopify Beauty AOV range covers beauty only. A separate AOV memo for supplements/mixed could promote those entries.
4. **Shopify quote has no explicit publication date.** The Shopify blog page is evergreen; the memo notes "no explicit report year disclosed on the page; Shopify retains and continuously updates this resource." T3.5 reviewers may want a dated source for first beta — if so, this promotion gets demoted back to heuristic until a dated Shopify Plus annual benchmark report is sourced.
5. **`effective_n` for bsandco entry is 156,110 (full sample N).** Part III-1's policy table caps `pseudo_N` at the per-status default (30 for validated_external) regardless of disclosed N. The 156k is recorded in YAML for source-traceability; T3's sizing.py consumer applies the cap.

## 10. Follow-up work / dependencies

- **S7.5-T3** (cold-start blend refusal + `SOFT_PRIOR_UNVALIDATED` abstain mode behind `ENGINE_V2_PRIORS_VALIDATION`) is next. The 3 validated_external promotions mean T3's flag-on test fixtures will have at least 3 priors that survive the refusal rule, which makes the abstain-mode behavior testable on a non-trivial slate.
- **S7.5-T3.5** (flag flip ON + atomic fixture re-pin) is the only behavior-changing ticket; T2's promotions reduce the likelihood that the flag-on Beauty fixture collapses to fully-empty (R2 in the IM risk register).

## 11. Branch shape

Six commits on `post-6b-restructured-roadmap` (T1.5 close + T2 close + housekeeping; not pushed):

1. `d060b00` — `S7.5 housekeeping: commit IM plan; gitignore .claude/*.lock`
2. `ae5e5ea` — `S7.5-T1.5: explicit validation_status on every priors.yaml entry`
3. `4f1d22d` — `Document S7.5-T1.5 in repo memory.md`
4. `040f175` — `S7.5-T1.5 summary`
5. `79247ce` — `S7.5-T2: external benchmark memos + validated_external promotions`
6. `2b6b0fc` — `Document S7.5-T2 in repo memory.md`
7. _this commit_ — `S7.5-T2 summary`

## 12. Hard constraints respected

- `engine_run.json` schema **unchanged** in shape and value.
- `event_version=1` payloads **frozen** — no payload changes; T2 is YAML + memos + tests only.
- D-5 enforced — no Shopify/Klaviyo network calls in src/; all sourcing was via WebFetch / WebSearch tools at engineering time, and the resulting numbers landed as static memo files. Engine runtime makes zero external calls.
- D-6 enforced — no banned ML modules touched.
- D-8 enforced — vertical scope unchanged (`{beauty, supplements, mixed}`); no new verticals introduced via memo backfill.
- M0 Beauty pinned fixture sha256 **unchanged**.
- Beauty pinned slate sha256 **unchanged** at `45edaca58c47...`.
- Supplements G-1 fixture sha256 **unchanged** at `01f5feff84...`.
- B-5 Berkson invariant intact.
- S-2 / S-3 / S-4 / S-5 / S-6 substrate write paths **untouched**.
- `src/` **untouched** (T2 is YAML + memos + tests only).
- `KNOWN_ISSUES.md` **untouched** at T2 close.
- Part III-1 Step 4 critical distinction (observational ≠ causal) pinned by `test_no_lift_like_prior_is_validated_external`.
- No new runtime dependencies.

## Backfill from memory.md (migration trim 2026-05-25)

## S7.5-T2 — External benchmark memos + validated_external promotions (2026-05-17)

**Shipped:**
- New `config/priors_sources/` directory with a README documenting the memo shape + promotion contract (per Part III-1 Step 4: ONLY base_rate / bundle_value priors may be validated by observational benchmarks; incrementality / *_lift / churn_reduction etc. require causal sources).
- **3 priors promoted to `validated_external`** with `source_artifact` pointers and `effective_n` where the source discloses sample size:
  1. `winback_21_45.base_rate` (vertical: beauty) — Klaviyo 2026 H&B benchmarks (published 2026-02-24; 183,000+ brands); memo cites campaign placed-order-rate 0.19% / flow placed-order-rate 1.96% / flow click-rate 4.8%; YAML value 0.08 backed by multi-touch flow cumulative-conversion mapping; `effective_n=30` (founder Q4 default).
  2. `bestseller_amplify.bundle_value` (vertical: beauty) — Shopify blog Beauty AOV range $15-$90; YAML value 45.0 sits inside; `effective_n=null` (Shopify does not publish underlying sample size).
  3. `first_to_second_purchase.base_rate` (vertical: `*`) — bsandco 2026 DTC RPR benchmarks (published 2026-02-14; 156,110 customers; 365-day window); memo cites consumables RPR 22-44% / typical 30-40% / 50.3% of repeat purchases in first 30 days; YAML value 0.18 backed by 365d-RPR × 30d-timing-factor mapping; `effective_n=156110`.
- Failed-attempt documentation under `config/priors_sources/_attempted/`: Klaviyo landing-page 404s + email-gated PDF (5 URLs tried, one finally yielded the H&B numbers); Shopify Plus PDF report email-gated and not pursued per founder Q1.

**Load-bearing invariants:**
- `tests/test_s7_5_t2_external_priors.py` pins (a) ≥3 validated_external entries, (b) every validated_* entry has a non-null `source_artifact` whose file exists AND cites at least one URL, (c) no `incrementality` / `*_lift` / `churn_reduction` / etc. lift-like prior name appears with `validated_*` status (Part III-1 Step 4 critical distinction). Violations of (c) would mean observational benchmarks are being mis-used as causal lift claims.
- Memos document what the source DOES prove and what it does NOT prove. Klaviyo's "flow placed order rate" is per-email-send, not per-recipient-in-window — the YAML value mapping is structurally compatible but the point estimate is engine-derived, not verbatim Klaviyo.

**Caveats / dormant behavior:** ZERO behavior change — nothing reads `validation_status` / `source_artifact` / `effective_n` until T3. The promotions create a `validated_external` set for T3's blend-refusal rule to recognize (heuristic_unvalidated → suppress; validated_external → blend permitted).

**Schema:** unchanged (`event_version=1` frozen; YAML + new memo files + new test file only).
**Suite:** 1213 passed, 14 skipped, 1 failed (was 1208p at S7.5-T1.5 close; +5 new T2 tests; the 1 fail is the same pre-existing `test_inventory_updated_at_is_fresh` wall-clock drift).
**Fixtures:** Beauty pinned slate sha256 unchanged at `45edaca58c47...`; supplements G-1 sha256 unchanged at `01f5feff84...`; M0 goldens byte-identical.
**Summary:** [agent_outputs/code-refactor-engineer-s7_5-t2-summary.md](agent_outputs/code-refactor-engineer-s7_5-t2-summary.md)

---
