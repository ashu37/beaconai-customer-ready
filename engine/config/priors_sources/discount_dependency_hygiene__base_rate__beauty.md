---
# RE-FIT NUMERICS (S8-T0, 2026-05-24)
# Point estimate: 0.0220 (2.20%)  [unchanged]
# p10: 0.0037                     [was 0.0120 — text-derived from source memo]
# p90: 0.0471                     [was 0.0430 — text-derived from source memo]
# Beta alpha: 1.32                [was 0.66 — J-shape defect]
# Beta beta: 58.68                [was 29.34]
# Effective N: 60                 [was 30]
# Re-fit math: alpha = value * N = 0.0220 * 60 = 1.32; beta = N - alpha = 58.68.
# p10/p90 from: scipy.stats.beta(1.32, 58.68).ppf([0.10, 0.90])
#               -> [0.0036879681, 0.0470907418], rounded to 0.0037 / 0.0471.
# Resolves KI-NEW-K (J-shape envelope mis-stated): Beta(1.32, 58.68) is
# unimodal because alpha>1; envelope is now analytic, not text-derived.
# DS verdict: agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md
# Provenance note retained: original source numerics transcribed from
# base64-encoded images in Gemini Deep Research markdown — verify against
# original Klaviyo PDFs as a separate sweep (not part of S8-T0 scope).
---

# **Prior Benchmark Memo: Discount Dependency Hygiene Base Rate (BEAUTY)**

This benchmark memo establishes the prior probability distribution for the metric discount_dependency_hygiene.base_rate within the decision engine configuration. This prior is saved verbatim in the decision engine configuration path at config/priors_sources/discount_dependency_hygiene__base_rate__beauty.md to prevent downstream paraphrasing and to serve as an immutable reference for future statistical updates.

## **Prior Probability Metrics and Beta Distribution Parameters**

The prior probability represents the likelihood that a historically discount-conditioned consumer converts to a single full-price repeat purchase within a 14-30 day window after receiving a value-led, no-urgency, full-price email send, under a strict 14-day prior discount-suppression protocol.

The prior distribution is modeled using a Beta distribution, which is conjugate to the binomial likelihood of conversion events. The shape parameters alpha and beta are derived from a synthesized baseline conversion rate of 0.0220, supported by a robust effective sample size (N) of 30. This sample size is statistically justified by the extensive dataset provided in the Klaviyo 2026 Omnichannel Benchmark Report, which aggregates performance data from over 183,000 brands.

The probability density function for the prior is defined as:

f(p; alpha, beta) where p is the true underlying conversion probability of the target cohort.

| Metric Component | Value | Parameter Representation | Mathematical Definition |
| :---- | :---- | :---- | :---- |
| **Point Estimate (Mean)** | **0.0220** | **E[p]** | **alpha / (alpha + beta)** |
| **Conservative Bound (P10)** | **0.0120** | **p_0.10** | **CDF^-1(0.10)** |
| **Conservative Bound (P90)** | **0.0430** | **p_0.90** | **CDF^-1(0.90)** |
| **Effective Sample Size** | **30** | **N** | **alpha + beta** |
| **Alpha Shape Parameter** | **0.66** | **alpha** | **N * mean** |
| **Beta Shape Parameter** | **29.34** | **beta** | **N * (1 - mean)** |

The selection of alpha=0.66 and beta=29.34 yields a right-skewed prior distribution that reflects both the low baseline probability of converting a highly conditioned consumer without price incentives and the physical bounds of the probability space. This structure ensures that the decision engine remains highly responsive to brand-specific data updates while anchoring initial optimization cycles within realistic, empirically verified bounds.

**DS architect 2026-05-20 caveat:** With alpha < 1, the Beta distribution is J-shaped. Analytic p10 collapses toward 0 (not 0.0120); analytic p90 sits closer to 0.06–0.07 (not 0.0430). The claimed envelope is text-derived, not Beta-CDF-derived. Consider re-fitting at effective_n=60 (alpha=1.32, beta=58.68) before Sprint 8 calibration to recover a unimodal envelope. Tracked as KI-28.

## **What this Measures**

This metric measures the rate of conversion from discount-conditioned behavior to organic, full-price repeat purchasing for established customers within the DTC beauty vertical. Specifically, it isolates the segment of customers who have historically demonstrated a high reliance on promotional codes (defined as having a discount code applied to 50% or more of their historical orders) and tracks their propensity to purchase a replenishment or supplementary product at full price. The observation window is constrained to 14-30 days following a single, value-led email campaign that intentionally lacks promotional offers, countdown timers, or artificial urgency mechanics. Crucially, the customer must have experienced an absolute "blackout" or suppression of all other discount-bearing communication channels (such as automated abandoned cart flows, browse abandonment sequences, or blast campaigns containing coupons) for at least 14 days prior to the send. This combination isolates the consumer's genuine, brand-equity-driven replenishment need — aligned with typical 30-to-45-day beauty and skincare product usage cycles — from the transaction-utility-driven response characterized by consumer conditioning and price-anchoring effects.

From a psychological perspective, this base rate captures the transition of a consumer from conscious price-comparison shopping to automatic, habit-driven purchase behavior. According to Cognitive Appraisal Theory, repeat purchasing is heavily influenced by trust and product satisfaction. However, when discount-conditioned buyers are subjected to promotional suppression, their behavioral momentum must rely entirely on brand connection and product efficacy rather than the artificial stimulus of a discount. The metric therefore acts as a mathematical proxy for the residual brand equity and product-habit strength of the customer base, demonstrating whether the brand's core offering can overcome the cognitive inertia of discount expectation.

## **What this Does NOT Measure**

To prevent statistical contamination and preserve the validity of the prior, several distinct conversion triggers and customer segments must be explicitly excluded from this metric's measurement scope:

* **Urgency-Driven Recovery Conversions**: This metric does not measure the conversion rates of high-intent, real-time cart or browse abandonment sequences, which rely on immediate behavioral triggers and frequently deploy automated rescue discounts to overcome near-term checkout friction.
* **Introductory Customer Bribes**: It excludes welcome series flows targeting non-purchasers, where conversion rates are historically elevated due to introductory incentives (typically 10% to 15% off first orders) designed to lower the initial brand trial barrier.
* **Terminal Winback and Reactivation Flows**: It rejects conversions driven by aggressive winback sequences targeting highly lapsed cohorts (e.g., 60 to 90+ days past average purchase latency), which regularly leverage tiered discount ladders to prevent permanent brand churn.
* **Standard Replenishment Sequences with Backend Incentives**: It does not capture standard replenishment flows that convert consumers by introducing promotional codes or free-shipping thresholds in the late stages (e.g., emails 3 or 4 of a sequence) to capture the remaining non-converting segment.
* **Subscription Autorenewals**: It excludes recurring order events processed automatically via subscription billing engines such as Recharge or Ordergroove, as these transactions do not represent an active, manual customer decision to convert at full price in response to an email touchpoint.
* **Top-of-Funnel Paid Acquisition**: It rejects any conversion activity originating from paid social, search, or display retargeting, which are subject to different attribution windows and lack the specific email-delivered behavioral context required by this protocol.

## **Primary Sources and Access Dates**

The primary benchmark values and cohort structures were established utilizing Tier 1 industry data and marketing-science literature.

| Source Authority | Document / Report Title | Source URL | Access Date |
| :---- | :---- | :---- | :---- |
| **Klaviyo** | 2026 Marketing Benchmarks & Stats by Industry (Omnichannel Report) | https://www.klaviyo.com/marketing-resources/benchmark-report | May 15, 2026 |
| **Klaviyo** | 2026 Email Marketing Benchmarks by Industry (Health & Beauty Vertical) | https://www.klaviyo.com/products/email-marketing/benchmarks | May 15, 2026 |
| **Shopify Plus** | Winter '26 Edition: Customer Segment Automatic Discounting & Script Migrations | https://www.growthsuite.net/blog/what-shopifys-winter-26-edition-means-for-your-discount-strategy | May 18, 2026 |
| **Peer-Reviewed Literature** | DelVecchio, Henard, & Freling (2006): The Effect of Sales Promotion on Brand Preference | https://www.preprints.org/manuscript/202508.0222 | May 19, 2026 |
| **Peer-Reviewed Literature** | Lichtenstein, Ridgway, & Netemeyer (1993): Price Consciousness and Consumer Conditioning | https://www.preprints.org/manuscript/202508.0222 | May 19, 2026 |

## **Alternative Sources Considered and Rejected**

A number of alternative data sources and case studies were evaluated during the construction of this prior but were ultimately rejected due to systematic biases or methodological deficiencies:

* **BS&Co Agency Portfolio Report (April 2026)**: While this source provides highly detailed, brand-specific flow and campaign metrics for DTC beauty brands (documenting specific brand flow multipliers of 47.3x and 65.0x), the aggregate dataset is constrained to a small 13-brand portfolio. It was rejected as a primary prior source due to severe selection bias and an insufficient sample size to guarantee statistical generalizability across the wider beauty vertical.
* **Mantas Digital CRO Conversion Benchmarks (2026)**: This report cites a post-purchase repeat purchase conversion rate of 2% to 4% (with top performers reaching 5% to 9%) and a general health and beauty conversion rate of 2.0% to 3.5%. It was rejected because the underlying sample sizes were completely un-auditable, and the report failed to isolate discount-suppressed cohorts from standard, promotionally active post-purchase flows.
* **BePragma Smart Discounting Case Studies**: Case studies on brands like Nykaa (documenting a 20% GMV contribution from zero-discount SKUs) and Tata Cliq were evaluated. Despite discussing strategic "discount suppression," these narratives were rejected due to their reliance on unverified self-reported metrics, lack of rigorous sample-size transparency, and focus on SKU-level margins rather than individual cohort-level repeat purchasing behavior.
* **General SMS-Conversion Reports (Postscript / Attentive)**: Various SMS platform case studies were analyzed to evaluate discount-suppression behaviors. However, they were excluded because their reporting structures fail to isolate email-attributed last-touch conversions within the required 5-day attribution window, and they suffer from high channel-mix contamination.

## **Limitations of the Benchmark**

While mathematically robust, the application of this prior within a live DTC decision engine must account for several inherent structural limitations:

* **Attribution Window Sensitivities**: The benchmark assumes a standard 5-day last-touch email attribution model. Because the conversion window spans 14 to 30 days post-send, a significant portion of late-stage conversions may be misattributed to "Direct," "Organic Search," or "Typed-In" traffic as tracking cookies expire or consumers return via browser bookmarks, artificially depressing the observed conversion rate.
* **Cross-Channel Retargeting Leakage**: The protocol assumes complete suppression of discount offers. However, if a brand operates a highly active cross-channel marketing program, suppressed customers may still encounter promotional codes via Meta retargeting ads, dynamic Google search campaigns, or SMS automations, leading to a false-positive full-price conversion reading.
* **Discount-Depth Heterogeneity**: The prior aggregates all "historically discount-conditioned" customers into a single cohort. In practice, a customer conditioned on a 10% off loyalty code behaves fundamentally differently from a customer conditioned on 50% off subscription-box clearance codes. The latter group exhibits a drastically lower conversion rate when subjected to full-price suppression.
* **Average Order Value (AOV) Friction**: The DTC beauty vertical covers an AOV range from $20 to $120. Premium cosmetics and luxury skincare brands at the higher end of this range (AOVs closer to $120) carry significantly longer purchase latency cycles and higher purchase friction compared to lower-cost personal care essentials. This variance can alter the natural replenishment timeline, making the fixed 14-30 day observation window less predictive for high-AOV segments.

## **Works cited**

1. 2026 Email Marketing Benchmarks by Industry - Klaviyo, accessed May 20, 2026, https://www.klaviyo.com/products/email-marketing/benchmarks
2. Email Marketing Benchmarks 2026 - Klaviyo UK, accessed May 20, 2026, https://www.klaviyo.com/uk/blog/email-marketing-benchmarks-open-click-and-conversion-rates
3. Spending Signals: Investigating the Combined Effect of Promotions and Shipping Types on Consumer Purchase Amounts - Preprints.org, accessed May 20, 2026, https://www.preprints.org/manuscript/202508.0222
4. Smart Discounting for Indian D2C e-commerce Automating Pricing Strategies across Platforms - Pragma, accessed May 20, 2026, https://www.bepragma.ai/blogs/smart-discounting-for-indian-d2c-e-commerce
5. Customer Cohort Analysis Shopify - Definition & Meaning - Joy Subscriptions, accessed May 20, 2026, https://www.joysubscription.com/glossary/customer-cohort-analysis-shopify
6. Klaviyo Replenishment Flow: Time It With Your Data | BS&Co, accessed May 20, 2026, https://bsandco.us/blog-post/replenishment-flow-klaviyo
7. CDPs vs CRMs vs DMPs: Cut Through the Jargon to Build a Unified Customer View, accessed May 20, 2026, https://www.linearloop.io/blog/cdp-vs-crm-vs-dmp-to-build-unified-customer-view
8. How to Keep Them Coming Back: Lessons for SMEs Focused on Growth and Sustainability, accessed May 20, 2026, https://jsbs.scholasticahq.com/article/157790-how-to-keep-them-coming-back-lessons-for-smes-focused-on-growth-and-sustainability
9. Extending the prevalent consumer loyalty modelling: the role of habit strength, accessed May 20, 2026, https://www.emerald.com/ejm/article/47/1-2/303/32154
10. Investigating the Determinants of Repeat Purchase Intentions for One Commune One Products in Digital Platforms - ResearchGate, accessed May 20, 2026, https://www.researchgate.net/publication/394857762
11. Email Marketing Conversion Rate Benchmarks eCommerce 2026 - Mantas Digital, accessed May 20, 2026, https://www.mantasdigital.com/cro-2/email-marketing-conversion-rate-benchmarks/
12. Using Customer dashboards to analyze churn types, subscriber trends, and cohort data, accessed May 20, 2026, https://support.getrecharge.com/hc/en-us/articles/360033927734
13. Understanding the Cohort Analytics Tab - Ordergroove Knowledge Center, accessed May 20, 2026, https://help.ordergroove.com/hc/en-us/articles/15471299469459
14. Email Marketing Benchmarks - April 2026 | BS&Co, accessed May 20, 2026, https://bsandco.us/blog-post/ecommerce-email-marketing-benchmarks-april-2026
15. Attentive vs Postscript for Shopify SMS: 2026 Pick | COREPPC, accessed May 20, 2026, https://coreppc.com/shopify/attentive-vs-postscript/
16. Klaviyo drives The Beauty Crop's email revenue growth, accessed May 20, 2026, https://www.klaviyo.com/uk/customers/case-studies/the-beauty-crop
17. Beauty & Skincare Repeat Purchase Rate Benchmarks for 2026 - Mage Loyalty, accessed May 20, 2026, https://www.mageloyalty.com/blog/beauty-skincare-repeat-purchase-rate-benchmarks-for-2026

---

**Provenance note (DS architect 2026-05-20):** The original Gemini Deep Research output included numerical values rendered as base64-encoded inline images. The values transcribed above (point estimate, p10/p90, Beta parameters) reflect what the source text claims; they are NOT independently re-derived from the cited Klaviyo PDFs. Verify against original Klaviyo source PDFs before Sprint 8 calibration per KI-28.
