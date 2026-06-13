# Klaviyo Benchmarks landing page — attempted, partial yield

## URLs tried (2026-05-17)

| URL | Result | What was missing |
|---|---|---|
| https://www.klaviyo.com/marketing-resources/email-benchmarks | HTTP 404 | URL no longer resolves |
| https://www.klaviyo.com/marketing-resources/email-marketing-benchmarks | HTTP 404 | URL no longer resolves |
| https://www.klaviyo.com/marketing-resources/email-benchmarks-by-industry-2024 | HTTP 200, landing page only | Page is a download-gate for the 2024 report PDF; no numerical tables in HTML |
| https://www.klaviyo.com/products/email-marketing/benchmarks | HTTP 200, partial | Section headers present (open rate / click rate / placed order rate / RPR) but the numerical tables render via JS / dynamic data; not extractable via WebFetch |
| https://www.klaviyo.com/blog/health-and-beauty-industry-benchmarks | HTTP 200 | Article cites Klaviyo's "2024 state of ecommerce report" but does NOT inline the email-channel benchmarks; only secondary findings (price sensitivity, loyalty program adoption, channel mix) |

## What ultimately worked

https://www.klaviyo.com/uk/blog/email-marketing-benchmarks-open-click-and-conversion-rates (2026-02-24, published date disclosed on page) yielded verbatim Health & Beauty benchmarks: open rate 30.5%, click rate 1.24%, placed order rate 0.19% (campaigns); click rate 4.8%, placed order rate 1.96% (flows); "over 183,000 brands" analysis base.

See `../winback_21_45__base_rate__beauty.md` for the successful memo.

## Not pursued

- The full 2024 / 2026 Klaviyo Industry Benchmark PDF report is
  download-gated. It would likely supply per-industry sample sizes and
  more granular breakouts (per-flow-type, per-region), but per founder Q1
  this T2 pass is scoped to free public web sources only.
- Klaviyo's "Health & Wellness" (vs "Health & Beauty") industry
  breakout is referenced in the landing pages but does not appear in
  the public blog version. Supplements-vertical promotions therefore
  could not be backed by a Klaviyo memo in this pass; supplements
  base_rate entries stay `heuristic_unvalidated`.
