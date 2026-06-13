---
# OPERATIONAL REFERENCE — NOT A PRIOR
#
# DS architect 2026-05-20 verdict: REJECT as validated_external prior.
#
# This memo does NOT propose a point estimate, effective N, or Beta parameters.
# It is an operational/econometric playbook covering channel cost structures,
# margin/LTV math (Jedidi/Mela/Gupta 40% intercept erosion, CM2 formula),
# programmatic exclusions, audience tiering, and case studies.
#
# Saved under config/priors_sources/ as a Phase-D economic-model reference.
# NO priors.yaml entry. supplements discount_dependency_hygiene play remains
# PRIOR_UNVALIDATED, routes to Considered (Path-D dormant per founder Q5
# conditional-yes 2026-05-20: research-thin auto-accept).
#
# Tracked: KI-27 (re-run Deep Research with explicit point-estimate prompt later).
---

# Dynamic Analysis of the discount_dependency_hygiene.base_rate Prior: Market Benchmarks and Margin Preservation Strategies in the Supplements Vertical

## Baseline Definition and Validated External Promotion Framework

Model promotion within a direct-to-consumer (DTC) ecommerce decision engine involves transitioning a structural prior, such as the discount_dependency_hygiene.base_rate, from an internally calibrated state to a validated_external state. This operational promotion validates that the engine's discount-mitigation and margin-preservation logic is successfully anchored to verified, real-world baseline parameters compiled from external data suppliers and enterprise platform APIs. For direct-to-consumer operators in the supplements vertical, establishing a robust hygiene prior is not merely an optimization exercise but a core financial requirement. Unlike higher-margin categories such as home goods, which achieve first-order payback metrics exceeding 200%, the supplements vertical demonstrates an average first-order payback rate of only 82%. This structural deficit means that supplement brands incur a net loss on customer acquisition and must rely on rapid, high-margin replenishment cycles within the first 60 to 90 days to achieve profitability.

The broader direct-to-consumer macro environment reveals that while 66% of large health, wellness, and beauty brands experienced profit expansion in 2024, consumers remain highly sensitive to price and quality. Specifically, 53% of surveyed consumers plan to maintain their wellness spending, 32% plan to increase spending, and 42% of those increasing spending attribute this to anticipated inflationary price adjustments. Brand-switching behaviors are highly pronounced, as quality (78%) and price are the top-ranked purchase considerations, far outperforming brand reputation (42%) and customer reviews (39%). To navigate this volatility, a direct-to-consumer decision engine must enforce strict baseline discount hygiene limits to prevent margin dilution while maintaining replenishment velocity.

The discount_dependency_hygiene.base_rate serves as the primary operational threshold within the decision engine, representing the target proportion of total transactions containing promotional concessions. In the supplements vertical, where repeat purchase behavior dictates long-term survival, establishing this prior under the validated_external standard requires a precise understanding of the marketing channel economics and the baseline retention parameters of consumable brands.

## Channel Cost Structures and Operational Performance Baselines

A critical component of validating the baseline hygiene prior is analyzing the historical performance of automated flows relative to standard promotional campaigns across email and SMS. Automated email flows generate 41% of email-attributed revenue from just 5.3% of sends, demonstrating an 18-times higher revenue per recipient (RPR) compared to manual campaigns. Flows are also highly efficient at customer acquisition, driving 48% of their revenue from new buyers compared to only 16% for campaigns. Similarly, SMS flows represent only 7.6% of message sends but drive 45.2% of total SMS revenue, with 64.4% of SMS flow revenue originating from new buyers.

Under the validated_external standard, these metrics must be mapped against health, beauty, and supplement baselines to calibrate the decision engine.

| Metric Category | Email Campaign (Average) | Email Flows (Average) | Email Flows (Top 10%) |
| :---- | :---- | :---- | :---- |
| Open Rate | 30.50% | 45.00% - 65.00% | 65.34% |
| Click Rate | 1.24% | 4.80% | 10.48% |
| Placed Order Rate | 0.11% | 1.39% | 4.75% |
| Revenue Per Recipient | $0.10 | $1.18 | $8.78 |

In the SMS channel, consumable and replenishment-focused orders under a $100 average order value (AOV) represent a distinct product persona. Standard campaigns in this category yield lower engagement and revenue compared to behavioral triggers, which capture high purchase intent.

| Message Trigger Archetype | Unsubscribe Rate | Click-Through Rate | Conversion Rate | Earnings Per Message |
| :---- | :---- | :---- | :---- | :---- |
| Standard SMS Campaign | 0.00% - 1.00% | 4.00% - 13.00% | 0.00% - 2.00% | $0.16 - $1.05 |
| SMS Welcome Series | 2.00% - 6.00% | 8.00% - 13.00% | 4.00% - 10.00% | $1.86 - $5.60 |
| SMS Abandoned Cart | 0.00% - 1.00% | 12.00% - 20.00% | 7.00% - 16.00% | $3.61 - $9.84 |
| SMS Keyword Opt-In | 1.00% - 2.00% | 25.00% - 38.00% | 10.00% - 26.00% | $5.09 - $14.79 |

A key operational factor in calibrating the decision engine's messaging overhead is the fixed cost associated with the underlying SMS delivery platform. Choosing between platforms like Postscript and Attentive has a direct impact on unit economics. Postscript is highly native and cost-effective for operators seeking direct control ($0.0075 to $0.0105 per message), whereas Attentive focuses on enterprise managed services at a premium ($0.0160 to $0.0220 per message). At a scale of 1,000,000 monthly sends, this per-message gap introduces an operational overhead difference of $7,000 to $12,000 per month.

| Monthly Sends (Approx.) | Subscriber Base | Postscript All-In Monthly Cost | Attentive All-In Monthly Cost |
| :---- | :---- | :---- | :---- |
| ~40,000 Sends | 10,000 Subscribers | $400 - $550 | $700 - $1,200 |
| ~200,000 Sends | 50,000 Subscribers | $1,800 - $2,400 | $3,200 - $4,500 |
| ~1,000,000 Sends | 250,000 Subscribers | $7,500 - $10,500 | $14,000 - $22,000 |
| ~2,000,000 Sends | 500,000 Subscribers | $14,000 - $20,000 | $28,000 - $45,000 |

These benchmarks demonstrate that automated, behavior-triggered flows are highly efficient. To optimize channel profitability, the decision engine should suppress high-frequency, manual campaigns and prioritize automated flows.

## Econometric Foundations and Behavioral Economics of Discount Conditioning

To model the discount_dependency_hygiene.base_rate prior accurately, the decision engine must account for the long-term impact of promotions on brand equity. Econometric modeling shows that while advertising investments build long-term brand preference, price promotions act as a negative tax on brand equity. Over several years, frequent price cuts reduce the dynamic brand intercept, which serves as a proxy for baseline brand equity. The cumulative long-term negative effect of promotions on sales is estimated to be approximately two-fifths (40%) of the magnitude of their short-term promotional spike, meaning that continuous price promotions cannibalize future full-price revenue.

This brand erosion is driven by three behavioral and psychological mechanisms:

* **Lowered Reference Prices:** Price perception theory indicates that consumers establish an internal reference price based on a rolling average of past observed prices. Frequent discounting suppresses this reference point, transforming the discounted price into the expected baseline and framing standard retail pricing as an unearned premium.
* **Shifts in Attribution:** Self-perception theory demonstrates that consumers who purchase under a deep promotion attribute their buying decision to an external cause (saving money) rather than an internal cause (valuing the product's quality). When the promotion is retracted, the lack of an internal affinity driver lowers the probability of a repeat purchase.
* **Quality Perceptions:** Object perception theory suggests that frequent price cuts signal a lack of product differentiation or underlying quality. In the supplements vertical, where trust, efficacy, and clinical validation are primary conversion drivers, continuous discounting can lower the customer's perception of product quality and safety.

This dynamic is supported by empirical findings on brand trust: brand image has a significant coefficient of 0.689 in building customer loyalty, and brand trust has a coefficient of 0.238. This proves that brand affinity is a much stronger driver of repeat buying behavior than transactional discounts.

## Dynamic Margin and Lifetime Value Modeling

To evaluate these dynamics, the decision engine must analyze promotional impact using three core mathematical formulas.

The first formula calculates Shopify Net Sales, which establishes the absolute revenue baseline after accounting for promotions and product returns:

Net Sales = Gross Sales - Discounts - Returns

The second formula models Contribution Margin 2 (CM2), which accounts for variable fulfillment, payment, and marketing costs:

CM2 = Net Sales - COGS - Shipping Cost - Payment Fees - Variable Marketing Spend

First-purchase CM2 must remain break-even or slightly positive for a healthy direct-to-consumer brand. A channel generating $300,000 at a 25% CM2 yields the exact same absolute dollar contribution as a $250,000 channel operating at 30% CM2, but the latter preserves brand equity and reduces long-term discount conditioning. When aggressive welcome codes drag first-purchase CM2 into the negative 5% to negative 15% range, the brand is paying twice for customer acquisition: once for the digital ad and once for the discount margin concession.

The third formula establishes Customer Lifetime Value (LTV), which projects the total net margin contribution of a cohort over its expected retention lifecycle:

LTV = AOV * Purchase Frequency * Gross Margin % * Customer Lifespan

Under a subscription model, this formula demonstrates significant expansion. A standard one-time buyer (AOV of $50, purchasing 2.2 times per year at a 55% gross margin over a 1-year lifespan) yields an LTV of $60.50. A subscriber ($40 per month, billing 12 times per year at a 55% gross margin over a 1-year lifespan) yields an LTV of $264.00, illustrating why supplement brands must prioritize subscription transition programs.

These margin calculations must be analyzed alongside price elasticity models. Standard CPG price elasticities are negative, typically falling between -2.8 and -0.7, with the vast majority concentrated between -2.4 and -1.2. Online customers exhibit higher price sensitivity than offline retail shoppers. Price anchoring strategies can increase perceived value by 32%. In contrast, dynamic pricing has a highly sensitive effect: personalized dynamic pricing drives a 25% increase in repeat purchase rates, whereas demand-based peak surge pricing leads to a 20% drop in repurchase intent. However, when dynamic pricing is presented with transparent explanations, 72% of shoppers report higher trust and a 60% higher likelihood of making repeat purchases.

## Programmatic Exclusions and Automated Decision-Engine Architecture

To automate discount dependency hygiene, the decision engine must configure programmatic exclusions within the commerce platform. Using Shopify Plus, this is achieved through automated collections and tags. High-performing "hero" products — which act as key retention drivers and exhibit strong natural repeat purchase patterns — should be tagged with no-discount or exclude-promo. Automated collections are then constructed using the rule condition Product Tag is not equal to no-discount or Compare at price is empty to restrict promotional codes exclusively to full-price inventory.

Moving from blanket promotional codes to behavioral, tiered discounting reduces margin waste on dedicated buyers. Across 47 brand audits in 2024 and 2025, transitioning from blanket codes to behavioral tiers lowered the average discount from 27% to 16% and increased overall conversion rates by 12% to 18% within 30 days.

This personalization requires identity resolution. Brands that invest in identity resolution (79%) report improved messaging performance, as it provides the programmatic foundation for automated behavioral flows, precise personalization, and cross-channel coordination.

To support recurring retention, the decision engine should configure the subscription platform to offer targeted incentives based on customer segments and order cycles.

| Feature Comparison | Ordergroove | Recharge | Loop |
| :---- | :---- | :---- | :---- |
| Enterprise Support | Multi-platform enterprise support, predictive analytics, Best Deal Guarantee. | High market dominance, extensive integration ecosystem. | High-efficiency migration tools, advanced customization options. |
| Operational Costs | Minimum $2,917/month plus undisclosed custom GMV charges. | Plus: $499/month + 1.34% of GMV + $0.19 per transaction. | Pro: $399/month + 0.75% of GMV (no order transaction fees). |
| Fulfillment Control | Program-wide and item-level dynamic one-time discount configurations. | Basic cancellation flows, standard coupon codes. | Advanced, interactive cancellation flows with multi-choice save offers. |
| Promotional Logic | Nth order rewards, tiered subscribe-more-save-more incentives. | Standard fixed percentage discount rules. | Custom discount structures for first and subsequent subscription orders. |

## Empirical Case Studies of Discount Detoxification and Alternate Value Loops

The viability of transition programs is illustrated by several direct-to-consumer brands that successfully reduced their promotional dependency.

### Mister Spex: The "SpexFocus" Program

During the second half of 2023, omnichannel retailer Mister Spex ran nine major promotional discounts. To stabilize margins, the brand launched the "SpexFocus" program in 2024, deliberately restricting the promotional volume to just three discounts in the second half of the year. This reduction in discount frequency had predictable operational effects:

* **Top-Line and Volume Adjustments:** The retraction of aggressive promotions contributed to a net revenue decline of 10% in FY24 and 16% in FY25, particularly impacting the price-sensitive online sunglasses and contact lens divisions.
* **Margin and Profitability Expansion:** The reduction in discounting improved gross margins by approximately 77 basis points in late 2024. Gross margin expanded further in FY25, increasing by 580 basis points to 55.6%. By the first quarter of 2026, the company's gross margin expanded by an additional 230 basis points, reaching 59%.
* **EBITDA Improvement:** Despite the contraction in total order volume, adjusted EBITDA improved by approximately €20 million over the course of the transformation phase, demonstrating that a selective, margin-positive customer base delivers superior enterprise value compared to high-volume, discount-conditioned traffic.

### Virus International: Transitioning Away from Discount-First Email Sales

Athletic apparel and wellness brand Virus International faced a severe margin-eroding issue, as its digital marketing revenue was almost entirely discount-driven. Working with Red Fox Web Technologies, the brand replatformed to Shopify Plus, consolidated custom applications, and rebuilt its automated flows on Klaviyo. By transitioning away from discount-first promotions, the brand was able to reduce its reliance on discounts by 4,100% while simultaneously increasing total sales.

### The Perfect Jean: Product Discovery and Interactive Quizzes

To avoid margin erosion from introductory discounts, apparel retailer The Perfect Jean developed the "Perfect Match" quiz. This interactive onboarding flow matches customers with their ideal fit based on body type, addressing purchase friction without relying on promotional codes. The quiz achieved a 15% conversion rate, delivered a 31-times ROI, and significantly lowered return rates, proving that interactive customer guidance can drive acquisition without margin concessions.

### Hair Gain: Checkout Flow Integration

Premium vegan haircare and wellness brand Hair Gain replaced intrusive discount popups with high-intent customer acquisition. Using Dataships, the brand integrated a dynamic, location-based marketing consent checkbox directly into the checkout flow. This natural integration captured high-intent customers at the moment of purchase, driving opt-ins and conversion rates without relying on upfront discounts.

## Algorithmic Decision-Engine Guidelines and Operational Recommendations

To support model promotion within the decision engine, this section provides structured operational guidelines to enforce the validated baseline of the prior metric discount_dependency_hygiene.base_rate in the Supplements vertical.

### Dynamic Audience Tiering

The decision engine must dynamically segment traffic based on engagement and purchase intent to prevent margin waste on high-intent buyers.

| Customer Segment | Behavioral Signals | Recommended Promotion | Operational Reason |
| :---- | :---- | :---- | :---- |
| VIP / Dedicated Buyers | High purchase frequency, active subscription, or high historical LTV. | 0% Discount | High baseline purchase intent; prioritize exclusive product drops, early access, or loyalty point multipliers. |
| High-Intent / Consideration | Multiple product pages viewed, cart active, or return visitor. | 5% - 10% Discount or Threshold Gift | Needs a minor nudge to convert; prioritize spend-and-save thresholds to protect margin and lift AOV. |
| Marginal / Low-Engagement | Quick browsing, short session duration, or exit intent detected. | 15% - 20% Discount (Time-Limited) | Higher trust barriers; deploy dynamic, single-use, expiring codes on exit only to drive incremental sales. |

### Implementation of Programmatic Guardrails

To enforce baseline discount hygiene, the decision engine should implement the following programmatic constraints across the direct-to-consumer tech stack:

* **Tag-Based Product Exclusions:** Tag core "hero" replenishment products with no-discount within Shopify Plus. Configure automated collections where Product Tag is not equal to no-discount and map all promotional campaigns exclusively to this collection, shielding core product margins from dilution.
* **Compare-At-Price Verification:** Configure promotional codes to apply only to collections matching the condition Compare at price is empty. This dynamically excludes markdown inventory, preventing margin-eroding "double-discounting" at checkout.
* **Enforced Coupon Cooldowns:** Programmatically restrict coupon eligibility within Klaviyo, Attentive, and Postscript by enforcing a 30-to-45-day post-redemption cooldown. Suppress standard campaign sends during this period, forcing the consumer to engage with the natural replenishment cycle before becoming eligible for subsequent offers.
* **Subscription Milestone Realignment:** Reconfigure subscription signup and retention flows in platforms like Loop or Ordergroove. Instead of offering a flat discount across all subscription orders, implement an Nth order milestone reward (e.g., standard 10% discount on orders 1 through 3, with an increased 15% discount or free product exclusively on the 4th order) to align discounting with customer acquisition payback thresholds.
* **First-Purchase Margin Audits:** Set a strict floor for first-purchase contribution margin, ensuring CM2 remains break-even or positive. If a channel's welcome offer drags first-purchase CM2 below negative 5%, the decision engine should automatically suppress the offer and transition to non-monetary incentives, such as free expedited shipping or a free gift with purchase.

## Works cited

1. 2026 Email Marketing Benchmarks by Industry - Klaviyo, accessed May 20, 2026, https://www.klaviyo.com/products/email-marketing/benchmarks
2. 2026 SMS Marketing Benchmarks & Stats by Industry - Klaviyo, accessed May 20, 2026, https://www.klaviyo.com/products/sms-marketing/benchmarks
3. Attentive vs Postscript for Shopify SMS: 2026 Pick | COREPPC, accessed May 20, 2026, https://coreppc.com/shopify/attentive-vs-postscript/
4. Mastering Price Elasticity Models for CPG: Beyond Basics | by Quation Solutions | Medium, accessed May 20, 2026, https://medium.com/@quation755/mastering-price-elasticity-models-for-cpg-beyond-basics-eadfefbeb45d
5. Go-to-Market Strategy for Ecommerce: 2026 Launch Guide - Prospeo, accessed May 20, 2026, https://prospeo.io/s/go-to-market-strategy-for-ecommerce
6. Customer Acquisition Cost: Ecommerce Benchmarks & CAC Guide - Retainful, accessed May 20, 2026, https://www.retainful.com/blog/customer-acquisition-cost-ecommerce
7. Health & Beauty Industry Benchmarks for 2024 - Klaviyo, accessed May 20, 2026, https://www.klaviyo.com/blog/health-and-beauty-industry-benchmarks
8. How to Exclude Items from Discount: Shopify Guide - MBC Bundles, accessed May 20, 2026, https://mbc-bundles.com/blogs/shopify-tips/how-to-exclude-items-from-discount-shopify
9. The BFCM Profit Leak: Why Your Biggest Sales Weekend Might Be Costing You Money - Ecommerce Fastlane, accessed May 20, 2026, https://ecommercefastlane.com/the-bfcm-profit-leak/
10. The Email Marketing for Small Business Guide - Klaviyo, accessed May 20, 2026, https://www.klaviyo.com/products/email-marketing/small-business
11. Email marketing benchmarks 2026 - Klaviyo UK, accessed May 20, 2026, https://www.klaviyo.com/uk/blog/email-marketing-benchmarks-open-click-and-conversion-rates
12. Ecommerce Email Open Rates: 2026 Benchmarks & Data - Prospeo, accessed May 20, 2026, https://prospeo.io/s/ecommerce-email-open-rates
13. Postscript SMS Benchmarks 2023, accessed May 20, 2026, https://postscript.io/sms-benchmarks-2023
14. SMS Benchmarks Report 2022 - Postscript, accessed May 20, 2026, https://postscript.io/sms-benchmarks-2022
15. Postscript vs Attentive for small ecommerce businesses - Zigpoll, accessed May 20, 2026, https://www.zigpoll.com/content/postscript-vs-attentive-compared-2026-1da7cf
16. The Attentive Marketer Pulse - Attentive, accessed May 20, 2026, https://www.attentive.com/blog/attentive-marketer-pulse-march-2026
17. The Long-Term Effects of Price Promotions on Category Incidence, Brand Choice and Purchase Quantity - ResearchGate, accessed May 20, 2026, https://www.researchgate.net/publication/242254388
18. Managing Advertising and Promotion for Long-Run Profitability (Jedidi/Mela/Gupta 1999), accessed May 20, 2026, https://people.duke.edu/~mela/Jedidi_Mela_Gupta_1999.pdf
19. The effect of sales promotion on post-promotion brand preference: A meta-analysis - ProQuest, accessed May 20, 2026, https://search.proquest.com/openview/7b1349fba34cb5de872bcf4358eef0ac/1.pdf
20. The Business of Coupons - Do coupons lead to repeat purchases?, accessed May 20, 2026, https://trace.tennessee.edu/cgi/viewcontent.cgi?article=2605&context=utk_chanhonoproj
21. The Daily Ritual Brand | Studio Folkore, accessed May 20, 2026, https://www.studiofolklore.co.uk/news/the-daily-ritual-ecommerce-brand
22. The Influence of Brand Marketing Strategy, Price Discounts and Formation of Loyalty on Consumer Repurchase Intentions on the Shopee - GREENATION RESEARCH, accessed May 20, 2026, https://research.e-greenation.org/GIJEA/article/download/317/275/1815
23. Mastering the Sales by Discount Report in Shopify - MBC Bundles, accessed May 20, 2026, https://mbc-bundles.com/blogs/shopify-tips/mastering-the-sales-by-discount-report-in-shopify
24. Shopify Reporting for DTC Brands - DataAgents, accessed May 20, 2026, https://www.dataagents.io/shopify-metrics-reporting
25. The Shopify Contribution Margin Audit - eCommerce Circle, accessed May 20, 2026, https://www.ecommercecircle.com.au/shopify-contribution-margin-audit-hidden-profit/
26. What will happen when we raise our price? (How to Apply Price Elasticity), accessed May 20, 2026, https://www.cpgdatainsights.com/answer-business-questions/how-to-apply-price-elasticity/
27. Price Perception and Repeated Buying - NHSJS, accessed May 20, 2026, https://nhsjs.com/2025/price-perception-and-repeated-buying-how-psychology-shapes-consumer-loyalty/
28. Dynamic Pricing Promotion Strategies on Consumer Repeat Purchase Behavior - ResearchGate, accessed May 20, 2026, https://www.researchgate.net/publication/382093403
29. Your Catalog Is Your Retention Strategy - The DTC Newsletter, accessed May 20, 2026, https://newsletter.retentionx.com/p/deep-dive-your-catalog-is-your-retention-strategy
30. Blanket Discounts Are Killing Your Margins - Growth Suite, accessed May 20, 2026, https://www.growthsuite.net/resources/shopify-conversion-rate/visitor-intelligence-guide/blanket-discounts-killing-margins
31. Ordergroove vs Recharge vs Loop: The 2026 Comparison - Loop Subscriptions, accessed May 20, 2026, https://www.loopwork.co/blog/ordergroove-vs-recharge-vs-loop
32. Ordergroove Feature Descriptions, accessed May 20, 2026, https://help.ordergroove.com/hc/en-us/articles/360052367594
33. Choosing The Right Incentive - Ordergroove Knowledge Center, accessed May 20, 2026, https://help.ordergroove.com/hc/en-us/articles/360034590194
34. One-Time Discounts - Ordergroove Knowledge Center, accessed May 20, 2026, https://help.ordergroove.com/hc/en-us/articles/360053562694
35. Mister Spex's Transformation on Track, accessed May 20, 2026, https://corporate.misterspex.com/en/press-releases/mister-spexs-transformation-on-track-significant-profitability-increase-expected-in-2025/
36. Media - Mister Spex Corporate Website, accessed May 20, 2026, https://corporate.misterspex.com/en/media/
37. Mister Spex SE FY24 results - mwb research hub, accessed May 20, 2026, https://downloads.research-hub.de/2025%2003%2027%20Mister%20Spex%20FY24%20results___astm84lh.pdf
38. Virus International - Red Fox Web Technologies, accessed May 20, 2026, https://www.redfoxwebtech.com/case-study/virus-international-case-study/
39. Detoxing from Discount Popups - Dataships, accessed May 20, 2026, https://www.dataships.io/blog-posts/detoxing-from-discount-popups
40. The Ultimate Guide to Shopify Time-Limited Offers & Discounts, accessed May 20, 2026, https://marketinglib.com/the-ultimate-guide-to-shopify-time-limited-offers-discounts/
41. Direct-to-Consumer (DTC) Sales: Definition, Benefits, and Tips (2026) - Shopify, accessed May 20, 2026, https://www.shopify.com/enterprise/blog/direct-to-consumer
42. How to Target Discounts for the Right Customers - Atom Commerce, accessed May 20, 2026, https://www.atomcommerce.io/blog/how-to-target-discounts-for-the-right-customers-without-losing-margin-11
43. "Repeat Purchase Strategy: Building Systems for Customer Loyalty and Recurring Revenue" - Rework, accessed May 20, 2026, https://resources.rework.com/libraries/ecommerce-growth/repeat-purchase-strategy
44. Retaining Your Subscribers - Ordergroove Knowledge Center, accessed May 20, 2026, https://help.ordergroove.com/hc/en-us/articles/360056592714

---

**Provenance note (DS architect 2026-05-20):** This memo does NOT propose a base_rate / Beta-parameterized prior. It is consumed as Phase-D economic-model operational reference only. Supplements discount_dependency_hygiene play remains PRIOR_UNVALIDATED → Considered (Path-D dormant per founder Q5 conditional-yes 2026-05-20). Re-research with explicit point-estimate prompt tracked in KI-27.
