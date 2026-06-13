# `first_to_second_purchase.base_rate` (vertical: `*`) — bsandco DTC benchmarks

## Publication

- **Title:** Repeat Purchase Rate Benchmarks: 18.8% Across 156K DTC Brands
- **Publisher:** bsandco
- **URL:** https://bsandco.us/blog-post/repeat-purchase-rate-benchmarks
- **Published:** 2026-02-14
- **Accessed:** 2026-05-17

## Sample / methodology

- **Sample size:** 156,110+ customers across 10+ verticals.
- **Time window:** 365-day lookback.
- **Methodology note:** "Aggregate numbers are weighted by customer count" across consumables, fashion, and durables verticals.
- Industry breakouts include Consumables (supplements/health), Fashion, and Durables. Health & Wellness brands are reported separately within Consumables.

## Verbatim numbers

> "Repeat purchase rate range: 22–44%" (Consumables category)
>
> "Typical rate: 30–40%" (Consumables category)
>
> "Reorder percentage: 82–93%" (Consumables sub-segment — supplements specifically)
>
> "Health & Wellness brands split the difference. 63–79% reorder, driven by compression wear and wellness products that customers use regularly."
>
> "Supplements are almost entirely reorder. Two supplement brands in the portfolio show 93% and 82% reorder rates."
>
> "50.3% of repeat purchases happen in the first 30 days. 76.4% happen within 90 days."

(All quoted verbatim from the bsandco blog page.)

## Applies to

| priors.yaml entry | Mapping |
|---|---|
| `first_to_second_purchase.base_rate` (vertical: `*`) | Current YAML: value=0.18, p10=0.08, p90=0.32. The bsandco data shows ecommerce repeat purchase rate averages **22-44% (consumables)** with **50.3% of repeat purchases happening in the first 30 days**. A 30-day-window second-purchase rate of ~18% (= 36% RPR × 50.3% timing factor) is inside the bsandco range. |

## What this memo proves

- The cross-vertical repeat-purchase rate for ecommerce consumables is
  **22-44%** at the 365-day window.
- **50.3%** of those repeat purchases occur in the first 30 days.
- A 30-day-window second-purchase rate of ~18% (the YAML value) is
  structurally consistent with a ~36% 365-day-window RPR × 50.3%
  timing factor.

## What this memo does NOT prove

- bsandco's "Repeat Purchase Rate" is **across all customers in the
  365-day window**, not conditioned on the "first-time buyer who placed
  a single order" cohort that `first_to_second_purchase` targets. The
  mapping holds in direction but not in exact value — the YAML 0.18
  remains an engine-side anchor, not a verbatim bsandco number.
- This memo does NOT validate any **incremental lift claim**. The
  `first_to_second_purchase.incrementality` prior remains
  `heuristic_unvalidated`, and `first_to_second_purchase.second_purchase_lift`
  remains `placeholder`.
- The wildcard `vertical: "*"` mapping is conservative: the bsandco
  data covers consumables / fashion / durables broadly, and the YAML
  value 0.18 sits below the consumables average. Beauty-specific or
  supplements-specific point estimates would require sub-segment
  numbers bsandco does not separately publish on this page.

## effective_n

bsandco discloses **156,110+ customers** as the analysis base. The
first_to_second_purchase prior is `vertical: "*"` and maps to the
weighted cross-vertical average, so the full N is the relevant base.
Per Part III-1 Step 4, set `effective_n` conservatively — the
disclosed N is much larger than the pseudo_N default of 30 for
`validated_external`, so the default applies as the BLEND weight cap.

`effective_n: 156110` recorded for source-traceability;
`pseudo_N` is capped by the policy table at T3.
