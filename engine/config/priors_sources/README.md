# Priors source memos (S7.5-T2)

This directory holds the external-benchmark memos cited by
`config/priors.yaml` entries with `validation_status: validated_external`.

Each memo is plain markdown with this minimum shape:

- **Publication:** title + URL
- **Date:** report publication date or accessed date
- **Sample:** sample size, composition, time period, methodology if stated
- **Verbatim numbers:** exact quoted figures from the source, no rounding
- **Applies to:** which `config/priors.yaml` entries this memo backs, with
  the explicit applicability note (what the source DOES prove and what it
  does NOT prove — observational benchmarks are NEVER causal lift claims)
- **effective_n:** integer if the source discloses sample size; omit otherwise

Memos under `_attempted/` document fetch attempts that failed (paywall,
404, redirect, missing data) so future agents don't re-try them blindly.

## Naming convention

`<play_id>__<prior_name>.md` (note the double underscore separating
play_id from prior_name). For per-vertical promotions, the per-vertical
applies_to is documented inside the memo body, not in the filename.

## Promotion contract (Part III-1 Step 4)

External benchmarks are observational. They CAN back base_rate and
AOV-style priors. They CANNOT back incrementality / `*_lift` /
`churn_reduction` / `growth_acceleration` / `conversion_improvement` /
`expansion_rate` / `subscription_multiplier` / `bundle_value` priors
unless the cited source is a randomized causal study. Today, every
memo here is observational — incrementality priors stay
`heuristic_unvalidated` until a causal source is cited.

The `bundle_value` exception: a bundle_value prior is an AOV anchor
(dollars per repeat-buyer order), not a lift claim. AOV benchmarks
back it directly.

## T2 scope (2026-05-17)

Free public sources only per founder Q1:
  - Klaviyo Industry Benchmarks (free, public web pages)
  - Shopify Plus blog (free)
  - bsandco DTC benchmarks (free, public blog post)
DTC Power Index skipped (paid). Three priors promoted in this pass.
