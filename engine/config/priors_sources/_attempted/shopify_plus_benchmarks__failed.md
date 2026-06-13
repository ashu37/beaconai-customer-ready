# Shopify Plus benchmarks report — attempted, partial yield

## URLs tried (2026-05-17)

| URL | Result | What was missing |
|---|---|---|
| https://www.shopify.com/blog/benchmarks | HTTP 200 | Product/feature page; describes the in-admin Benchmarks feature but publishes no numerical tables in the article body |
| https://www.shopify.com/blog/average-order-value | HTTP 200, partial | Beauty AOV range "$15 to $90" cited verbatim with attribution to dynamicyield.com; this number IS usable and backs `bestseller_amplify.bundle_value` (beauty). See `../bestseller_amplify__bundle_value__beauty.md` |

## Not pursued

- Shopify Plus's annual "Future of Commerce" / "State of Commerce" PDF
  reports periodically include AOV / conversion benchmarks. They are
  free but historically gated by email signup, and per founder Q1 this
  T2 pass is scoped to free public web sources only (no email-gate
  workaround attempted).
- Per-vertical AOV breakouts beyond "Beauty and personal care $15-$90"
  are not present on the public Shopify blog and would require the
  gated PDF to source.

## Why this is logged as a partial yield

The single Shopify quote ($15-$90 Beauty AOV) is enough to back one
prior promotion (bestseller_amplify.bundle_value beauty). Deeper
Shopify-platform breakouts (per-vertical conversion rate, repeat-rate
distributions) would back additional promotions but require the gated
PDF; deferred to a future T2-followup ticket if founder revises Q1.
