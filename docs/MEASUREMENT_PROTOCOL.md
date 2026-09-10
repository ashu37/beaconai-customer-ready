# Program measurement protocol — Ticket F design gate

**Status: DRAFT — awaiting founder approval of the merchant-facing scope, and review by someone competent in experiment analysis.** Nothing in §4–§6 is implemented. §7 lists the collection fixes needed under any design; they are safe to build before approval.

September 10, 2026. Based on the code at `main` 1457637 and aggregate statistics from the local test store. Test-store numbers are illustrative: that store is not a merchant, and its variability may not match one.

---

## 1. What the code does today

| Area | Current behaviour | Problem |
|---|---|---|
| Assignment | `holdoutService.bucketFor`: sha256(`shop:customer_id`) % 100 < 10 → holdout. Stable, never rotated, applied at every handoff. | Effectively a persistent customer-level holdout, but nothing records it. There is no enrollment row, enrollment date, eligibility rule or protocol version. The arm is recomputed each time rather than stored. |
| Identity | A recipient's `customer_id` is a Shopify id **or an email** (`campaignAudienceService.hydrateEmails`). | One person can carry two keys, and so land in two buckets. The bucket follows the key, not the person. |
| Exclusions | Engine members with no resolvable email are dropped before the split (`suppressedCount`) and never recorded. | Symmetric across arms, but neither the excluded identities nor the reasons are kept. |
| Recipients | `recordRecipients` DELETEs and rewrites the campaign's rows. | Recipients are not frozen. A later write could change who was in which arm after outcomes exist. |
| Send anchor | Windows start at `campaigns.sent_at`, stamped `NOW()` when local status becomes `sent`. | This is bookkeeping time. Ticket D's contract says the provider-confirmed `provider_sent_at` is the send time. |
| Campaign estimate | Intent-to-treat over the recorded arms, net of refunds, with a Welch 95% interval. The customer is the unit. | Sound in shape. The anchor and the recipient immutability need fixing (§7). |
| Program estimate | `summarizeProgram`: every recipient of a campaign sent in the last 90 days, grouped by `BOOL_OR(arm = 'treated')`. Revenue counts from a fixed start 90 days ago, and orders are hard-coded to 0. | **Not accepted (plan, Ticket F).** It compares ever-treated with never-treated, counts revenue from before a customer's first exposure, uses one fixed start for everyone, and its zero order count feeds the verdict gate. This produced the seed's contradictory "range crosses zero". |

Stored data today: 5 campaign rows (3 sent) and 24,040 recipient rows across 2 shops — seed and test data only. **No merchant program exists to recover. Historical rows stay descriptive (§8).**

## 2. Business question

> Over a fixed horizon after BeaconAI first had the chance to reach a customer, how much additional refund-adjusted revenue per customer did the BeaconAI campaign program produce, compared with not running it?

This is **not** total store revenue, and **not** Klaviyo-attributed revenue. The merchant's own marketing (flows, other campaigns, ads) continues for both groups, so the estimate is *incremental over what the merchant already does* (§5.6).

## 3. Options considered

**A. Keep a pooled comparison over existing campaign records.** Rejected as the program number. Because the bucket is stable, customers never actually switch arms, so the grouping is less broken than "ever-treated" suggests. But there are no enrollment dates, the start is fixed rather than tied to each customer's exposure, and the unit is anyone who happened to be in an audience. Existing records support per-campaign reads only.

**B. Per-campaign holdouts only; no program number.** Valid and simple, but underpowered at pilot scale (§6). It cannot answer the renewal question. It is the fallback if the founder does not want a program claim.

**C. Prospective program cohort with a persistent customer-level holdout. Recommended.** Formalise what the hash bucket already approximates: enroll customers explicitly, store their arm permanently, keep holdout customers out of every BeaconAI send, and measure from each customer's first treatment opportunity. It adds no new behaviour for the merchant beyond the holdout they already have.

## 4. Recommended design (option C)

### 4.1 Population and enrollment
- **Cohort:** one per shop per protocol version (e.g. `shop:v1`). It starts when the founder turns program measurement on for that shop.
- **Eligible:** a customer with a canonical identity (§4.4) who has at least one non-test, non-cancelled order in the 365 days before enrollment, or who first orders while the cohort is open.
- **Enrolled at:** cohort start for existing customers; first qualifying order time for new ones. Recorded once, never changed.
- **Arm:** `holdout` if sha256(`shop:cohort:canonical_key`) % 100 < holdout share, otherwise `program`. **Stored at enrollment** and never recomputed. A salt change or a new cohort version cannot silently move anyone.

### 4.2 Treatment opportunity
A customer has an *opportunity* when a BeaconAI campaign whose audience includes them is **confirmed sent by the provider**. The audience is computed by the engine without reference to arm, so holdout customers get opportunities too; they simply receive nothing. This is what makes the two arms comparable.
- **Opportunity anchor:** the `provider_sent_at` of the customer's first such campaign.
- A campaign that was created but never confirmed sent creates no opportunity for anyone.

### 4.3 Exclusion at handoff
At every BeaconAI handoff, audience members in the program's `holdout` arm are removed from the treated list and recorded with reason `program_holdout`. This replaces the per-campaign hash call. The per-campaign holdout becomes *program holdout members who were in this audience*, so campaign reads keep working (§4.6).

### 4.4 Identity
The canonical key is the Shopify customer id when one is known for the email, otherwise the lower-cased email. Enrollment stores both the key and every alias seen. Assignment is keyed on the canonical key, so a person has one arm.

### 4.5 Estimand
**Primary (recommended): opportunity-restricted intent-to-treat.** Among enrolled customers with at least one opportunity: the mean refund-adjusted net revenue per customer in `[anchor, anchor + H)`, program arm minus holdout arm.
- **Total:** per-customer difference × number of program-arm customers with an opportunity.
- **Horizon H:** 90 days (recommended; §6). A customer is included only once their horizon has fully elapsed. Incomplete follow-up is reported as "measuring", never extrapolated.
- **Pre-anchor revenue:** excluded from the outcome. Kept only as a labelled baseline covariate.
- **ITT throughout:** program-arm customers the provider did not deliver to (unsubscribed, suppressed, bounced) stay in the program arm. Consent filtering applies to the program arm only, so dropping non-deliveries would bias the comparison.

*Alternative, not recommended as primary:* ITT over all enrolled customers, whether or not they ever had an opportunity. It is equally valid but diluted by customers BeaconAI never targeted, and needs far larger samples.

### 4.6 Program control vs campaign control
These are different questions with different denominators, and are never mixed:
- **Program control:** enrolled holdout customers with an opportunity, anchored at their first opportunity, horizon H.
- **Campaign control:** holdout customers in *that campaign's* audience, anchored at *that campaign's* `provider_sent_at`, windows 30/60/90.

A customer is counted once per program estimate, however many campaigns reached them.

### 4.7 Overlap and repeated campaigns
The program estimate treats the whole sequence of BeaconAI sends as the treatment, so overlapping campaigns are not an interference problem for it. Per-campaign reads for customers reached by more than one campaign are *not* independent of earlier sends, and are labelled as such. Summing per-campaign increments is never presented as the program number.

### 4.8 Uncertainty and required counts
- **Unit:** the customer, one row per customer. **Interval:** Welch difference in means, 95%, as the campaign estimate uses today.
- **Reporting gate:** a comparison is reported only with ≥ 100 customers per arm with a completed horizon and ≥ 10 purchasers in each arm. Below that, the state is "insufficient data", which is distinct from "no clear difference".
- The interval is always shown. No verdict is inferred from a failed significance check.
- **For the reviewer:** whether heavy-tailed revenue calls for a bootstrap or a winsorized/trimmed mean alongside Welch; whether to adjust for pre-period revenue (CUPED-style) to gain precision; and whether the 100 / 10 floors are adequate.

## 5. What each design supports claiming

1. With **C**: "customers BeaconAI reached spent $X more per customer over 90 days than comparable customers it held back (95% interval $L–$H)."
2. **Not** total store lift. **Not** revenue caused by any single email. **Not** a significant result on demand.
3. Per-campaign reads: descriptive intervals. "No clear difference" is the expected outcome at pilot scale.
4. Historical campaigns: descriptive only. No program claim before enrollment.
5. Campaigns sent before the protocol is live cannot join the program retroactively.
6. Other marketing: the merchant's own flows still reach holdout customers. The estimate is incremental over the merchant's existing marketing, provided the merchant does not manually target BeaconAI audiences. **The merchant agrees to that at onboarding.**

## 6. Precision at pilot scale (test store, illustrative)

Per-customer net revenue among customers with prior orders. 30-day: mean $9.91, SD $20.29, 79% zero. **90-day: mean $33.93, SD $36.72, 44% zero** (N = 1,284).

"MDE" is the smallest true difference detectable with 80% power at a 5% two-sided level (2.8 × SE).

| Customers with an opportunity | Holdout | 90-day ±95% per customer | 90-day MDE | MDE as % of mean |
|---|---|---|---|---|
| 234 (one campaign) | 10% | ±$15.68 | $22.41 | 66% |
| 555 | 10% | ±$10.18 | $14.55 | 43% |
| 1,200 | 10% | ±$6.93 | $9.89 | 29% |
| 1,200 | 20% | ±$5.19 | $7.42 | 22% |
| 2,200 | 10% | ±$5.12 | $7.31 | 22% |
| 2,200 | 20% | ±$3.84 | $5.48 | 16% |

At 30 days the same MDEs are 41–125% of the mean.

**Reading:** a single campaign cannot resolve a realistic email effect. Even a pooled program of 2,200 customers detects only lifts of roughly 16–22% of baseline revenue. Email programs typically move far less than that. **The pilot must not promise a significant program result.** It can promise a valid estimate with an honest interval, which narrows as enrollment grows. Raising the holdout from 10% to 20% narrows the interval by about a quarter, at the cost of reach (§9).

## 7. Collection fixes required under any design (not gated)

These make data *collected now* usable later. Without them, a campaign sent during the pilot cannot be analysed under any protocol.

1. **Freeze recipients at handoff.** Once a campaign is frozen for handoff, its recipient rows are immutable: no DELETE, no rewrite. A retry reuses the stored split.
2. **Record identity and exclusions.** Store each recipient's alias(es) and the email used. Record engine members excluded before the split, with a reason (`no_email`, later `program_holdout`), instead of dropping them.
3. **Anchor on the confirmed send.** Measure windows from `provider_sent_at`. A campaign with no confirmed send is "awaiting send confirmation", not measured from local status time.
4. **Keep non-deliveries.** No analysis path filters the treated arm by delivery. This is already true; it gets a regression test so it stays true.
5. **Withdraw the ever-treated program comparison.** Until the protocol ships, the program summary returns "not yet measured" with a typed reason, instead of a number from `BOOL_OR`. The zero order count goes with it.

## 8. Migration

- Existing `campaign_recipients` rows stay as they are, labelled descriptive, and are never enrolled retroactively.
- No enrollment timestamps, randomization or program cohort are invented for the past.
- The program cohort starts at the founder's switch-on date, with protocol `v1`.
- Rollback turns off enrollment and exclusion but keeps every stored row.

## 9. Decisions for the founder (merchant-facing scope)

1. **Program claim.** Offer the program estimate (option C, prospective from switch-on)? Or run the pilot on per-campaign descriptive reads only (option B), with no program claim?
2. **Holdout share:** 10% (current) or 20%. 20% narrows the program interval by about a quarter; the cost is that 20% of eligible customers receive no BeaconAI campaigns.
3. **Horizon:** 90 days (recommended; 30 days is too noisy) or 60.
4. **Merchant agreement:** holdout customers receive no BeaconAI sends for the life of the cohort, and the merchant does not manually target BeaconAI audiences.
5. **Promise wording:** "a valid estimate with an interval that narrows over time". Not "proven ROI", and not "significance".

## 10. For the statistical reviewer

1. Is opportunity-restricted ITT valid here, given that audiences come from the engine independently of arm but the engine re-runs each month on data the program itself may influence?
2. Should the primary estimator be Welch, a bootstrap, a trimmed mean, or pre-period-adjusted (CUPED)?
3. Are the reporting floors (≥ 100 per arm, ≥ 10 purchasers per arm) adequate?
4. How should customers enrolled mid-cohort be handled, given their shorter or incomplete horizons?
5. Anything that should make us prefer option B for a single-merchant pilot.
