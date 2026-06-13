# `winback_21_45.base_rate` (vertical: beauty) — Klaviyo Health & Beauty benchmarks

## Publication

- **Title:** Email marketing benchmarks 2026: open rates, click-through rates, and conversion rates
- **Publisher:** Klaviyo
- **URL:** https://www.klaviyo.com/uk/blog/email-marketing-benchmarks-open-click-and-conversion-rates
- **Published:** 2026-02-24
- **Accessed:** 2026-05-17

## Sample / methodology

- "Over 183,000 brands" analysed (Klaviyo platform-wide).
- Health & Beauty industry segment is broken out as a category.
- Benchmarks reported for both campaign emails (one-off blasts) and
  automated flows (winback, abandoned-cart, post-purchase, etc.).
- Methodology section is not exhaustively published on the page; the
  metrics represent observed industry-aggregate averages over Klaviyo's
  customer base.

## Verbatim numbers (Health & Beauty)

> Campaign open rate: **30.5%**
> Campaign click rate: **1.24%**
> Campaign placed order rate: **0.19%**
> Flow click rate: **4.8%**
> Flow placed order rate: **1.96%**

(All quoted verbatim from the Klaviyo blog page's Health & Beauty section.)

## Applies to

| priors.yaml entry | Mapping |
|---|---|
| `winback_21_45.base_rate` (vertical: beauty) | Current YAML: value=0.08 (8% of winback recipients place an order in the 21-45 day window). Klaviyo's Flow placed-order rate for Health & Beauty is **1.96% per email**. Over a multi-send winback flow (typical 3-5 emails over the 21-45 day window), expected cumulative conversion lands in the 4-10% range, consistent with the YAML value 8%. |

## What this memo proves

- The H&B-industry-aggregate **per-email** placed order rate in
  automated flows (which winback campaigns are a subset of) is **1.96%**.
- A multi-touch winback flow's cumulative conversion in the 21-45 day
  window is plausibly bounded above by per-email rate × send count.
  An 8% cumulative rate over a 3-5 send sequence is inside that range.

## What this memo does NOT prove

- Klaviyo's "Flow placed order rate" is a **per-email-send rate**, not a
  per-cohort 21-45 day conversion rate. The mapping to
  `winback_21_45.base_rate` is structurally compatible (more email
  sends in the window → more aggregate conversion), but the **point
  estimate of 0.08 is a model-derived value, not a verbatim Klaviyo
  number**.
- This memo does NOT validate any **incremental lift claim**. The
  `winback_21_45.incrementality` prior remains `heuristic_unvalidated`.
- Klaviyo's benchmark is platform-aggregate; individual brands' winback
  performance varies widely (the page also discloses "top 10% of
  performers" achieve significantly higher rates).
- The mapping holds for the **beauty vertical only** here. Supplements
  (vertical: supplements) is NOT promoted in this T2 pass — Klaviyo
  does not publish a "Health & Wellness" placed-order-rate breakdown
  on the same page (only "Health & Beauty" as a combined category).

## effective_n

Klaviyo discloses "over 183,000 brands" as the analysis base, but does
NOT disclose per-industry sample size. Health & Beauty is a subset,
sample size unknown. Per Part III-1 Step 4, when source discloses a
broad N but not the subgroup N, set `effective_n` conservatively. Use
**effective_n: 30** as the pseudo_N default for `validated_external`
priors (Part III-1 §III-1 default table, founder-accepted Q4 value).
