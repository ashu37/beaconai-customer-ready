# T2.5 Floor Scope Card — D-S6-4 N≥30 per-SKU floor

**Date:** 2026-05-22
**Author:** ecommerce-ds-architect (dispatched per S7.6 continuation plan, T2.5-RESOLUTION)
**Scope:** Doc-only. No code edits.

---

**Q1 — Current shape of D-S6-4.** The floor lives at `src/audience_builders.py:418-423` as `min_customers_per_sku = _safe_int_cfg(cfg, "MIN_N_REPLENISHMENT_DUE_PER_SKU", 30)` and is enforced at line 509 (`if len(gaps_by_cust) < min_customers_per_sku: continue`). It is **env-configurable** (not profile-driven, NOT in `gate_calibration.yaml`). The requirement is precise: **per SKU-class key (beauty size-regex token or supplements unit-coherent key), the count of customers who contributed ≥1 inter-purchase gap (i.e. customers with ≥2 purchases of that SKU bucket) must be ≥30**. SKUs failing the gate are silently skipped; the downstream cohort_n collapses to 0 when all SKUs fail. This is a different floor from the **audience-level** `_default_by_stage` floor at `src/audience_builders.py:559-573` (currently 50/150/400/1200) and from the per-play `replenishment_due` cell at `config/gate_calibration.yaml:127-153` (60/150/350/1000).

**Q2 — Why N=30 originally.** Per `memory.md:540, 687` and `agent_outputs/code-refactor-engineer-s6-t3-summary.md:88`, N=30 was a **founder Q2 acceptance of the IM-plan default** with DS architect rationale recorded as *"defensible heuristic (Wilks-style 'stable empirical-median regime' threshold, but not specifically derived for this problem)"*. It is the textbook normal-approximation rule of thumb applied to **empirical median stability**, NOT to a proportion z-test, NOT to a Klaviyo benchmark, NOT to an internal validation result. The conditional commitment at the time was *"if <3 SKUs clear, lower to N=15 with typed LOW_CONFIDENCE_CADENCE flag"* (s6-t3-summary.md:88, 147). That probe was deferred — `memory.md:746` shows only the supplements G-1 probe was completed (4/4 keys clear); the Beauty path was never probed against the synthetic fixture.

**Q3 — Is N=30 right for ICP?** No, the floor is structurally mis-shaped for small DTC. For a ~50-SKU, ~1,200-customer / 240d fixture (Beauty: 18,933 orders across the file, ~16 orders/customer avg, hero SPF SKU appears in ~1,883 lines), the per-SKU repeat-buyer count compresses badly. If 50 SKUs share ~1,883 hero-class purchases, mean per-SKU is ~38 line-items, but the unique-customers-with-≥2-purchases-of-that-specific-SKU number is much smaller — typically 5-15 per SKU at this catalog/customer ratio because the SKU regex bucketing in `_beauty_key` (line 444) groups on the *matched substring* (size token like "50ml"), not on the product. A merchant must have **≥30 customers each repeat-buying within the SAME size token** for ANY SKU bucket to clear. At ICP scale this clears for **almost no merchants** — the floor was sized for an enterprise-replenishment shop (~10K+ customers per SKU class), not a 50-SKU DTC store. Estimated ICP clearance rate: **<20%** of representative small DTC merchants.

**Q4 — Structurally correct floor.** **(a) is the answer.** N=30 is too tight for the ICP. (b) is wrong because aggregation level is actually fine — the SKU-class bucket (size token / coherent unit) is already coarser than per-SKU; aggregating higher would conflate genuinely different cadences (a 50ml serum and a 30ml retinol have different replenishment rhythms). (c) is wrong because the ±½-cadence tolerance window (line 522) is generous — narrowing it would compound the problem. (d) no. The defect is that N=30 was imported as a stats rule-of-thumb for median stability without checking against an addressable-universe simulation at ICP catalog/customer scale.

**Q5 — Smallest correct change.** Change the default at `src/audience_builders.py:422` from `30` to `10`, and add a per-play cell `replenishment_due_per_sku_floor: {startup: 8, growth: 12, mature: 20, enterprise: 30}` to `config/gate_calibration.yaml` consumed by reading `cfg["_store_profile"].gate_calibration` via the same pattern as lines 559-573. N=10 retains the spirit of "you need at least a small handful of repeat-buyers to estimate a median that isn't a coin-flip" while making the floor clearable at ICP scale. The audience-level floor at line 559 (`_default_by_stage` 50/150/400/1200) remains the binding sample-size gate downstream — N=10 per SKU only governs which SKUs *contribute* to the cadence median, not whether the final cohort is big enough to act on.

**Q6 — If floor is correct and fixture is genuinely wrong-shape.** This is **not** the scenario — the Beauty fixture shape (1,199 customers, 50 SKUs, 18,933 orders) is representative of the founder ICP; calling the fixture "wrong-shape" against an N=30 floor is the floor accusing the merchant. The defensible posture is (i)-as-stated-only-if floor stays at 30: document `replenishment_due` as permanently absent on representative small DTC fixtures and explain it to merchants as "your catalog is too SKU-fragmented for per-SKU cadence inference." That is a bad merchant story. (ii) defers the question without resolving it. **Neither (i) nor (ii) is the right path because the floor itself is mis-sized for ICP.**

---

**Founder should lower D-S6-4 from N=30 to N=10** at `src/audience_builders.py:422` (one default-value change + one new profile cell in `gate_calibration.yaml`) — sprint scope adds 1 code commit (plus the existing T2.5 atomic flip + Beauty re-pin already planned) to address.

**Key file paths referenced:**
- `src/audience_builders.py` (lines 418-423, 509, 559-573)
- `config/gate_calibration.yaml` (lines 45-153)
- `config/priors.yaml` (lines 200-275)
- `agent_outputs/code-refactor-engineer-s6-t3-summary.md` (lines 14, 76, 88, 147)
- `agent_outputs/code-refactor-engineer-s7_6-t2_5-deferred-summary.md`
- `memory.md` (lines 540, 687, 746, 806, 1583)
- `tests/fixtures/synthetic/healthy_beauty_240d_orders.csv` (18,933 order lines)
