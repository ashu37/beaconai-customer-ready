# `bestseller_amplify.bundle_value` (vertical: beauty) — Shopify

## Publication

- **Title:** Average Order Value (AOV): Formula, Benchmarks and 7 Ways to Increase It
- **Publisher:** Shopify (shopify.com/blog)
- **URL:** https://www.shopify.com/blog/average-order-value
- **Accessed:** 2026-05-17

## Date

Page is on Shopify's evergreen blog and references current ecommerce data. No explicit report year disclosed on the page; Shopify retains and continuously updates this resource.

## Sample / methodology

- Shopify is the underlying commerce platform for hundreds of thousands of merchants; the figures cited reflect aggregate AOV ranges observed across the platform.
- Shopify attributes the specific range cited below to a third-party source: `marketing.dynamicyield.com/benchmarks/average-order-value/`. The page does NOT disclose the underlying sample size from that source.
- This is therefore an **observational AOV range**, not a per-merchant ground truth.

## Verbatim numbers

> "Beauty and personal care average closer to $15 to $90."

(Direct quote from the Shopify blog page, in the section discussing global AOV averages.)

## Applies to

| priors.yaml entry | Mapping |
|---|---|
| `bestseller_amplify.bundle_value` (vertical: beauty) | Current YAML: value=45.0, p10=25.0, p90=75.0. Sits inside Shopify's quoted $15-$90 beauty range. |

The YAML `bundle_value` prior represents the dollar value of a bundled
order in the bestseller-amplify play (a curated bundle of the hero SKU
plus complementary products). Shopify's quoted Beauty-and-personal-care
AOV range is the matching anchor: average order size in the beauty
vertical from an aggregate Shopify-platform observation.

## What this memo proves

- Beauty AOV in the $15-$90 range is consistent with industry-wide
  Shopify-platform observation.
- The YAML value 45.0 is inside the cited range; p10=25.0 and p90=75.0
  are conservative-but-inside the same range.

## What this memo does NOT prove

- This is an **observational AOV range across all Beauty orders**, not a
  per-bestseller-amplify-cohort number. Bundled-bestseller orders may
  have a different AOV distribution than the typical Beauty order.
- This memo does NOT validate any **incremental lift claim**. The
  `bestseller_amplify.incrementality` prior remains `heuristic_unvalidated`.
- Shopify discloses the range in narrative text; no sample size,
  geography filter, or time window is published on the page.

## effective_n

Unknown. The source page does not disclose the sample size from the
third-party Dynamic Yield benchmark it cites. `effective_n` left
null.
