# `replenishment_due.base_rate` (vertical: beauty) — External Benchmark Memo

**Source-of-truth:** Klaviyo Case Study: PERL Cosmetics & Klaviyo 2026 Omnichannel Benchmark Report (Health & Beauty Vertical)

- https://www.klaviyo.com/uk/customers/case-studies/beauty-startup-email-revenue-increase [1]
- https://www.klaviyo.com/uk/blog/email-marketing-benchmarks-open-click-and-conversion-rates [2]

**Date accessed:** May 19, 2026
**Validation status candidate:** validated_external

## 1. The benchmark value

- **value:** 0.0220  *(unchanged — point estimate is correct)*
- **range_p10:** 0.0037  *(was 0.0120 — text-derived from source memo)*
- **range_p90:** 0.0471  *(was 0.0430 — text-derived from source memo)*
- **effective_n:** 60  *(was 30)*

### S8-T0 re-fit (2026-05-24)

Re-fit at `effective_n=60` to Beta(1.32, 58.68) — unimodal because alpha>1.
- alpha = value * N = 0.0220 * 60 = 1.32
- beta  = N - alpha = 58.68
- p10/p90 from: `scipy.stats.beta(1.32, 58.68).ppf([0.10, 0.90])`
                -> `[0.0036879681, 0.0470907418]`, rounded to 0.0037 / 0.0471.

This entry shared the same Beta(0.66, 29.34) defect as
`discount_dependency_hygiene.base_rate.beauty` (KI-NEW-K). Re-fit as a
**founder-acked scope expansion** beyond the KI-NEW-K text — identical
defect, identical source class, atomic fix in the same commit.

DS verdict: `agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md` §3 + §6 F1.

## 2. What this measures

The core metric represents the probability that a customer, identified by a behavior-triggered predictive engine as approaching their consumable beauty product depletion date, completes a repeat transaction within a 7-to-30-day post-intervention tracking window. [1] The marketing intervention is a personalized, automated email flow that dynamically populates the recipient's previously purchased SKU and matches their individual consumption frequency. [1] This trigger executes a set number of days after the initial purchase, typically timed five to ten days before the predicted empty date to account for order processing, shipping, and transit lag. [3]

The primary benchmark is denominated strictly against delivered emails, excluding bounced addresses and bot-generated opens to isolate authentic customer interactions. [6] The conversion event is recorded as a "Placed Order" when the target recipient executes a transaction on the host e-commerce store. [6] This benchmark is derived from direct-to-consumer skincare, cosmetics, and personal care brands operating with average order values under $100. [1]

## 3. What this does NOT measure

The specified metric does not represent the holistic, store-wide repeat purchase rate, which captures the total proportion of historical customers who place multiple orders over an unrestricted time horizon. [9]

It does not measure general site-wide conversion rates denominated against sessions rather than targeted email recipients. [10]

It excludes winback, sunset, and re-engagement flows that target dormant subscribers who have already drifted past their replenishment window, typically defined as 60 to 90+ days of inactivity. [11]

Additionally, this metric does not measure high-intent checkout-recovery or cart-abandonment flows, which capture active checkout sessions and convert at structurally higher baseline rates. [8] It does not quantify passive subscription renewals powered by automated billing platforms, which rely on recurring credit-card captures rather than active consumer decisions. [14]

Finally, this is a pure probability rate (0.0 to 1.0) and does not represent monetary values such as revenue-per-recipient, average order value, or overall customer lifetime value uplift. [4]

## 4. Source methodology

The primary benchmark value of 2.20% is derived from Klaviyo's longitudinal case studies and verified against its global benchmark database. [1] Klaviyo's 2026 Omnichannel Benchmark Report aggregates performance data from over 183,000 integrated e-commerce merchants. [2] This dataset represents billions of email communications, which are cleaned of non-human interactions and categorized by industry verticals. [6] For the broader Health & Beauty vertical, Klaviyo establishes a baseline campaign open rate of 30.5%, a campaign click rate of 1.24%, and an automated flow placed order rate of 1.96%. [2]

To isolate replenishment-specific flows from general automated sequences, the case study of PERL Cosmetics provides an empirical anchor. [1] This direct-to-consumer beauty brand deployed behavior-triggered replenishment sequences, isolating an email-based replenishment flow conversion rate of 2.20%. [1] This is supported by another premium beauty case study, Balance Me, which utilized SKU-level usage data to trigger timely replenishment reminders. [8] Balance Me achieved an 83% overall lift in repeat purchase rates and isolated a targeted skincare cross-sell flow conversion rate of 1.90% alongside a high-intent back-in-stock flow conversion rate of 4.90%. [8]

### Performance Comparison Matrix

The table below contextualizes the primary beauty replenishment benchmark against broader industry flow types and campaign baselines:

| Flow/Campaign Category | Channel | Average Open Rate | Average Click Rate | Placed Order Rate (CVR) | Primary Source |
|---|---|---|---|---|---|
| Health & Beauty Campaign Baseline | Email | 30.50% | 1.24% | 0.19% | [2] |
| Health & Beauty Broad Flow Baseline | Email (Flow Avg) | 32.20% | 4.80% | 1.96% | [2] |
| PERL Cosmetics Replenishment Flow | Email | — | 9.00% (Post-Purchase Avg) | 2.20% | [1] |
| Balance Me Skincare Cross-Sell Flow | Email | — | — | 1.90% | [8] |
| Balance Me Back-in-Stock Flow | Email | 69.00% | — | 4.90% | [8] |
| Grind Consumable Replenishment Flow | Email | — | — | 4.40% | [19] |
| DTC General Welcome Flow (Top 10%) | Email | 45.80% | 10.48% | 4.30% | [2] |

### Consumable Product Consumption Cycles

When programming replenishment intervals, consumption rates dictate the optimal send delay. The table below outlines typical consumption cycles used to map triggers:

| Beauty Product Class | Typical Package Volume | Median Consumption Cycle | Optimal Reminder Send Window | Reference Source |
|---|---|---|---|---|
| Nutritional Supplements | 30-Day Supply | 25–30 Days | Day 20–22 | [5] |
| Face Serum | 30ml | 45–60 Days | Day 35–40 | [5] |
| Facial Moisturizer | 50ml | 60–75 Days | Day 50 | [5] |
| Shampoo & Haircare | 250ml | 60–90 Days | Day 50–60 | [5] |

## 5. Limitations

The primary benchmark carries several structural and methodological limitations that a data scientist must account for when deploying this prior in a production environment:

- **Store-Wide Attribution Inflation:** Klaviyo's standard "Placed Order" tracking operates on a last-touch attribution model (defaulting to a 5-day window). [6] This metric counts *any* transaction executed by the recipient, meaning if a customer receives a replenishment email for a face serum but purchases a lipstick instead, the system records a conversion. [20] This over-attributes conversion compared to a strict, same-SKU replenishment rate. [21]

- **Flow Aggregation Bias:** Automated flow benchmarks (1.96% for the Health & Beauty sector) consolidate a diverse mix of post-purchase, transactional, and abandon-recovery behaviors. [2] This aggregates high-converting sequences, such as welcome series (13% conversion) and checkout abandonment (7.7% to 9.0%), introducing an upward bias if applied strictly to replenishment-only events. [1]

- **Email vs. SMS Channel Discrepancy:** The baseline numbers represent an email-centric architecture. SMS-based replenishment automations operate under different friction and deliverability constraints. [10] Postscript reports a 13.6% median click-through rate for SMS replenishment reminders. [10] Standalone SMS reorder systems, such as Repeat SMS, drive conversion rates between 9.0% and 16.0% by introducing preloaded carts that reduce checkout friction. [23]

- **Fixed-Interval Errors:** Static-interval triggers (e.g., standardizing a trigger to fire exactly 30 days post-purchase) fail to account for individual product volumes, personal usage frequencies, and shipping delays. [3] This mismatch leads to poor user experiences and elevated unsubscribe rates if emails arrive too early, or missed purchase windows if they arrive too late. [21]

## 6. Alternative sources considered + rejected

Several secondary e-commerce data pools were evaluated but ultimately excluded from the primary model parameterization to maintain methodological rigor:

- **Recharge Annual Subscription Commerce Reports:** Recharge's dataset provides highly robust physical replenishment statistics, including a benchmark of 45% subscriber retention at 12 months. [25] However, this retention represents passive credit-card capture on a pre-existing autoship contract. [14] Because it does not measure active response conversion triggered by an outbound marketing intervention, it was rejected to prevent severe prior inflation. [14]

- **AudienceTap and Text-to-Buy Channel Reports:** Conversational SMS engines like AudienceTap demonstrate average replenishment conversion rates of 5.5%, with single-brand implementations like Tinker Coffee reaching 8.6%. [27] These were rejected as primary priors because "reply-to-buy" interactions bypass web checkout forms entirely. [27] Mixing this frictionless behavioral loop with standard web-redirect email flows would create a significant channel-mismatch error. [27]

- **Broad Category Scorecards (e.g., WebMedic):** These sources outline standard performance targets, such as a 5.0%+ conversion rate on replenishment reminders and open rates exceeding 40%. [5] While useful as optimistic operational goals, they are classified as unvalidated agency metrics because they lack auditable sample populations (N stores, N orders) and fail to control for brand scale. [5]

## 7. Recommendation

The benchmark value is designated as **validated_external**. [1] The tight mathematical alignment between the isolated beauty replenishment case study (2.20% conversion) [1] and the broad Health & Beauty automated flow baseline (1.96% conversion across 183,000+ brands) [2] validates this value as a reliable starting point.

For integration into a Bayesian decision engine, the conversion probability θ is modeled using a Beta distribution:

```
θ ~ Beta(α, β)
```

To initialize this prior with an expected mean of μ = 0.0220 and a conservative effective sample size of N = 30 (reflecting our confidence in the Tier 1 datasets), the shape parameters are calculated as:

```
α = μ × N = 0.0220 × 30 = 0.6600
β = (1 − μ) × N = (1 − 0.0220) × 30 = 29.3400
```

This parameterization grounds the decision engine in established industry performance while allowing the system to update the distribution as brand-specific transaction data is ingested.

To refine this prior, future iterations should deploy a 10% random holdout cohort (control group) to isolate true incremental lift from organic repurchasing patterns. [28]

## Works cited

1. Beauty brand increases monthly email revenue x3 with Klaviyo, accessed May 19, 2026, https://www.klaviyo.com/uk/customers/case-studies/beauty-startup-email-revenue-increase
2. Email marketing benchmarks 2026: open rates, click rates and conversion rates by industry, accessed May 19, 2026, https://www.klaviyo.com/uk/blog/email-marketing-benchmarks-open-click-and-conversion-rates
3. Create added value with Klaviyo replenishment flows (2022) - Relo, accessed May 19, 2026, https://www.reloapp.co/ultimate-guide-to-klaviyo-flows/klaviyo-replenishment-flows-2022
4. Post-Purchase Email Flow for DTC Brands: The 2026 Playbook - Top Growth Marketing, accessed May 19, 2026, https://topgrowthmarketing.com/post-purchase-email-flow-for-dtc-brands/
5. Refill Reminder Campaigns: Automate Repeat Purchases for Consumable Products, accessed May 19, 2026, https://webmedic.com/refill-campaign
6. Email and SMS performance data to guide your marketing strategy - Klaviyo, accessed May 19, 2026, https://klaviyocms.wpengine.com/wp-content/uploads/2025/02/2025-Benchmark-Report_AMER.pdf
7. 2024 SMS Benchmarks - Postscript, accessed May 19, 2026, https://postscript.io/sms-benchmarks-2024
8. Balance Me boosts repeat purchases 83% with Klaviyo - Klaviyo UK, accessed May 19, 2026, https://www.klaviyo.com/uk/customers/case-studies/balanceme-replenishment-emails
9. What is a good repeat purchase rate in marketing? - Klaviyo, accessed May 19, 2026, https://www.klaviyo.com/glossary/what-is-a-good-repeat-purchase-rate
10. SMS Marketing Statistics 2026: 110+ Open and CTR Data - Digital Applied, accessed May 19, 2026, https://www.digitalapplied.com/blog/sms-marketing-statistics-2026-open-ctr-data
11. How to Optimize Email Flows for Higher eCommerce Conversions - Mantas Digital, accessed May 19, 2026, https://www.mantasdigital.com/cro-2/optimize-email-flows-ecommerce/
12. Winback Flow Benchmarks - Klaviyo Community, accessed May 19, 2026, https://community.klaviyo.com/marketing-30/winback-flow-benchmarks-5148
13. Email Flows That Increase Repeat Purchases for D2C - 23HubLab, accessed May 19, 2026, https://23hublab.com/email-flows-that-increase-repeat-purchases-for-d2c/
14. Subscription Commerce: The Ultimate Guide to Ecommerce Subscription Models (2026), accessed May 19, 2026, https://www.techrepublic.com/article/subscription-commerce-guide/
15. The Beginner's Guide to eCommerce Subscriptions - Ordergroove, accessed May 19, 2026, https://www.ordergroove.com/guides/ecommerce-subscriptions-for-beginners/
16. 2026 Email Marketing Benchmarks by Industry - Klaviyo, accessed May 19, 2026, https://www.klaviyo.com/products/email-marketing/benchmarks
17. 2024 Email Marketing Benchmarks by Industry - Klaviyo, accessed May 19, 2026, https://www.klaviyo.com/marketing-resources/email-benchmarks-by-industry-2024
18. 80+ Email Marketing Benchmarks for Ecommerce (2026) - Branvas, accessed May 19, 2026, https://branvas.com/blogs/news/ecommerce-email-marketing-benchmarks
19. Drip Email Campaigns: Practitioner's Guide (2026) - Prospeo, accessed May 19, 2026, https://prospeo.io/s/drip-email-campaign
20. The 7 Klaviyo Flows That Drive 30–45% of Email Revenue (With Templates), accessed May 19, 2026, https://www.outbrandthem.com/blog/the-7-klaviyo-flows-that-drive-3045-of-email-revenue-with-templates
21. Klaviyo Replenishment Flow: 5 Strategies for Repeat Sales (2025) - Titan Marketing Agency, accessed May 19, 2026, https://www.titanmarketingagency.com/articles/klaviyo-replenishment-flow
22. 10 Email Marketing Automation Examples for 2025 - Klaviyo, accessed May 19, 2026, https://www.klaviyo.com/blog/top-email-automation-examples
23. Dr. Squatch's 9% CVR reordering experience on SMS, accessed May 19, 2026, https://blog.getrepeat.io/dr-squatchs-9-cvr-reordering-experience-on-sms/
24. Which Email Marketing Flows are Important for eCommerce? - Create8, accessed May 19, 2026, https://www.create8.co.uk/email-marketing-flows-for-ecommerce/
25. Subscription Automation Platforms Compared: Recharge vs Bold vs Full Orchestration, accessed May 19, 2026, https://ustechautomations.com/resources/blog/ecommerce-subscription-recurring-order-management-comparison-2026
26. DTC Subscription Retention: A Playbook by Subscription Model - SubJolt, accessed May 19, 2026, https://www.subjolt.com/guides/dtc-subscription-retention/
27. SMS Conversion Rate | Benchmarks & How to Improve - AudienceTap, accessed May 19, 2026, https://www.audiencetap.com/glossary/sms-conversion-rate
28. Boost Shopify Repeat Revenue in 5 Minutes | Replenit, accessed May 19, 2026, https://replen.it/retail-agents/shopify

---

## Source provenance

**Research method:** Gemini Deep Research, prompted 2026-05-19. Original prompt drafted by orchestrator (Claude Code) following the format established at S7.5-T2 for the prior 3 validated_external memos. Memo content saved verbatim as the canonical source artifact; subsequent engineering work cites this file, never paraphrases it.

**Filed as discrete commit per process discipline:** raw research output is preserved in git history so future agents and merchant DS reviewers can audit the research provenance independent of downstream YAML wiring or code changes.
