# Phase 6B → Stop-Coding-Line Reconciled Review
Date: 2026-05-06
Reviewers: product-strategy-pm + ecommerce-ds-architect
Frame: JSON contract is the product. HTML is a debug view. Narration / framing / phrasing is the downstream AI-agent swarm's job. Engine owns typed fields, math, audience math, and play-id / display-name uniqueness.

---

## Q1 — The Five Founder-Review Issues

| # | Issue | PM verdict | DS verdict | Reconciled |
|---|-------|------------|------------|------------|
| 1 | `discount_hygiene` mechanism contradicts play title | ENGINE FIX REQUIRED | ENGINE FIX REQUIRED | **ENGINE.** Typed `mechanism` contradicts typed posture / `would_be_measured_by`. No narration agent can reconcile. Fix `config/priors.yaml`. |
| 2 | "(102.3% vs prior)" framing | AGENT-LAYER | AGENT-LAYER (DUAL if `delta_pct` not yet emitted) | **AGENT-LAYER, with one engine check.** Verify the JSON exposes `current`, `prior`, and `delta_pct` as separate typed numerics. If it currently emits a pre-formatted ratio string, that's the only engine task — no copy work. |
| 3 | "$329.0k addressable" misreadability | DUAL | AGENT-LAYER w/ engine guardrail | **DUAL.** Engine must emit `audience_size`, `aov_used`, `aov_window`, `monthly_revenue_estimate` as separate typed fields, never a pre-formatted dollar string and never a single composite `addressable_revenue` scalar. Framing (cap vs MRR, suppress, label) is agent. |
| 4 | display_name collision (`retention_mastery` ≡ `at_risk_repeat_buyer_rescue`) | ENGINE FIX REQUIRED | ENGINE FIX REQUIRED | **ENGINE.** Uniqueness invariant on display_name across active play_ids. Fix YAML + add emit-time assertion. |
| 5 | Mechanism strings leak measurement instructions | ENGINE FIX REQUIRED | ENGINE FIX REQUIRED | **ENGINE.** `mechanism` is intervention-only; `would_be_measured_by` carries measurement. Strip "track X" suffixes in YAML. |

Net: **3 ENGINE fixes (#1, #4, #5), 1 DUAL (#3), 1 AGENT-LAYER (#2 with verification).**

---

## Q2 — Phase 6C Reconciliation

**(a) Considered reason-bucket overhaul → DO IN ENGINE (minimal).**
Both reviewers agree. Reason codes are typed decision metadata; agents need an enum, not free-text, to narrate *why* a play was held. Minimum surface: enum
`held_reason ∈ {AUDIENCE_BELOW_FLOOR, EVIDENCE_BELOW_THRESHOLD, ANOMALOUS_WINDOW, ROLE_CONFLICT, DUPLICATE_AUDIENCE, TARGETING_HELD_UNDER_ABSTAIN, …}`
plus `held_reason_detail` struct (e.g. `{observed: 312, floor: 500}`). 6–8 codes is enough. No new logic, just typed surfacing of state already known at decide time.

**(b) AnomalousWindow auto-registration → DO IN ENGINE. Non-negotiable per DS.**
This is the highest-trust item in 6C. If the engine emits `repeat_rate_l28=0.090` from a window containing a holiday spike or data gap, the JSON alone is unverifiable — the number *looks* clean. Minimum typed surface per metric:
`{value, window, n_days_observed, n_days_expected, anomaly_flags: [GAP|SPIKE|SEASONAL_BOUNDARY|LOW_VOLUME]}`.
Without this, the narration agent will confidently turn noise into momentum. Schema slot can ship now even if detection is initially a stub returning `[]`.

**(c) State-of-Store trend stats in Watching → DEFER TO AGENT-LAYER.**
Both reviewers agree. As long as the engine emits per-metric `{value, prior_value, delta_pct, direction, threshold_to_act}`, the narration agent assembles the Watching prose. Engine constraint: no string-only "down" signals; magnitude must be present in the typed payload. Nothing else to build.

---

## Q3 — The Stop-Coding Line

**Not yet clean. Land these 5, then freeze.**

1. **`config/priors.yaml`** — rewrite `discount_hygiene.mechanism` to suppression posture; strip "track redemption rate" / "track basket attach" trailing clauses from `discount_hygiene` and `bestseller_amplify`. *(Founder #1, #5)*
2. **`config/priors.yaml`** — break `retention_mastery` ↔ `at_risk_repeat_buyer_rescue` display_name collision; add emit-time uniqueness assertion in priors loader. *(Founder #4)*
3. **`src/decide.py` output serializer** — guarantee opportunity-context emits raw typed components (`audience_size`, `aov_used`, `aov_window`, `monthly_revenue_estimate`) and never a pre-formatted dollar string or composite `addressable_revenue` scalar; same for SoS deltas (`current`, `prior`, `delta_pct` as floats, never a "(X% vs prior)" string). *(Founder #2, #3)*
4. **Considered reason-codes (Phase 6C-a, minimal)** — replace freeform considered-reason strings with the 6–8-code typed enum + detail struct. *(Phase 6C-a)*
5. **AnomalousWindow contract slot (Phase 6C-b)** — add `anomaly_flags` + `n_days_observed/expected` per metric. Detector can stub-return `[]` initially; reserving the typed slot now prevents an agent-layer rewrite later. *(Phase 6C-b)*

**Explicitly out of scope for engine freeze (defer to agent swarm):**
- Percent framing ("+2.3%" vs "102.3% of prior")
- Dollar contextualization (cap vs MRR, suppress, relabel)
- Watching magnitude prose
- Replenishment / display-name polish
- Card layout, copy tone, narrative ordering
- State-of-Store trend prose (6C-c)

---

## STOP-CODING LINE
Ship items 1–5 above as one bundled engine commit. Lock the JSON schema. Freeze the engine. Pivot the next sprint to the downstream agent swarm.

Items 1–2 are YAML-only. Item 3 is serializer-shape work. Items 4–5 are typed-contract additions, not algorithmic. None of the five requires new statistical modeling. Total engine surface area remaining: small and bounded.

Everything else surfaced by the founder review is narration-layer and **must not** be solved in the engine.
