# Program measurement protocol — Ticket F design gate

**Status: DRAFT v2. The design gate is OPEN.** The decisions in §3 are **proposed** for the first paid pilot. They take effect only after founder approval and review by someone competent in experiment analysis. Nothing in §4 is implemented, and the program estimator will not be built until the gate closes.

| | State |
|---|---|
| **Collection work** (§8) | **Complete.** Data collected from now on is analysable under this protocol or a revised one. |
| **Program measurement** (§4) | **Not ready.** Not built, not approved, not reviewed. No campaign may be sent as part of a measured program. |

September 10, 2026. Scoped to one merchant, one fixed cohort. Engine logic is untouched.

---

## 1. What the code does today

| Area | Behaviour |
|---|---|
| Campaign holdout | `holdoutService.bucketFor`: sha256(`shop:customer_id`) % 100 < 10, recomputed at each handoff. Stable, but nothing records enrollment, an enrollment date or a protocol version, and the bucket follows whichever key the customer carries (a Shopify id **or** an email). |
| Recipients | Frozen at handoff: immutable once the campaign is frozen, with email aliases and pre-split exclusions (and their reasons) recorded. *(§8)* |
| Send anchor | Measurement starts only when the Ticket D delivery state is `sent` **and** the provider gave a send time. Created drafts, scheduled sends and unknown outcomes are never measured. *(§8)* |
| Campaign comparison | Difference in mean refund-adjusted revenue per assigned customer. Standard error `sqrt(s_T²/n_T + s_H²/n_H)` — an unequal-variance (Welch) standard error — with a **normal critical value of 1.96**. This is **not** a Welch–Satterthwaite *t* interval. |
| Campaign reporting gate | Counts **orders** (`n_orders`): ≥ 1 per arm and ≥ 10 in total. Ten orders from one customer pass as ten "buyers". See §4.9. |
| Program comparison | **Withdrawn.** It grouped customers as ever-treated vs never-treated and counted revenue from a fixed start date. The API now reports `protocol_not_live`. |

## 2. Business question

> Over 90 days, did being assigned to receive BeaconAI campaigns change refund-adjusted revenue per customer, compared with customers held back from every BeaconAI campaign?

This is not total store revenue, and not provider-attributed revenue.

## 3. Proposed pilot decisions (pending founder approval and statistical review)

1. **Prospective only.** The program comparison starts at a future enrollment date. Nobody is enrolled retroactively, and no earlier campaign counts toward it.
2. **One fixed cohort,** selected before the first BeaconAI exposure it measures. No rolling enrollment.
3. **Persistent 10% holdout,** assigned once and stored.
4. **90-day primary horizon.**
5. **Every enrolled customer is followed** regardless of later targeting, purchases, unsubscribes, suppression, delivery or identity merges. Nobody is dropped after assignment.
6. **Other marketing:** the merchant's ordinary marketing continues for both groups. Holdout customers must not receive BeaconAI campaigns by any route, including manual targeting (§4.4).
7. **The promise:** an estimate with its uncertainty, which may be inconclusive. Not proven ROI, not significance, and not an interval guaranteed to narrow — with a fixed cohort it does not.

## 4. Protocol v1 (proposed)

### 4.1 Cohort and enrollment
- **Enrollment date T0** is set by the founder, before the first BeaconAI campaign this cohort will measure is handed off.
- **Eligible:** a customer with at least one non-test, non-cancelled order in the 365 days before T0, and an identity (§4.3). The list is taken once, at T0, and stored.
- **New customers** who first order after T0 are **not enrolled**. They can still receive BeaconAI campaigns; they are outside the program estimate.
- **Earlier BeaconAI sends:** if the shop had any before T0, they are history. The cohort's random assignment balances that history across arms; it is recorded, not adjusted for.

### 4.2 Assignment
- Arm = `holdout` if sha256(`shop:cohort_id:enrollment_key`) % 100 < 10, otherwise `program`. Computed **once at T0 and stored** on the enrollment row with the protocol version, and never recomputed.
- The cohort-specific salt makes the assignment independent of the older per-campaign bucket. Arms from before T0 do not carry over.

### 4.3 Identity
- **Key at T0:** the Shopify customer id where a customer record exists, otherwise the lower-cased, trimmed email. Identifiers already linked at T0 (a customer record with an email; orders carrying both) are deduplicated **before** assignment, so one person gets one enrollment.
- **Aliases:** every identifier known for an enrollee at T0 is stored against the enrollment id. Handoff exclusion and outcome matching both resolve through aliases to the enrollment id — never through the current key alone.
- **Email → Shopify id upgrade:** when an email-keyed enrollee later gets a Shopify id, the id is added as an alias of the **same enrollment**. Enrollment date and arm are unchanged.
- **Conflicting existing assignments** (an identifier found after T0 to link two enrollments):
  - **Survivor:** the earlier enrollment id; the other is marked `merged_into` with a timestamp.
  - **Arm:** the survivor keeps its original arm. Arms are never reassigned from later data, because linkage can be caused by purchasing, which the treatment may affect.
  - **Outcomes:** both identifiers' orders count toward the survivor.
  - **Conflicting arms:** recorded as `arm_conflict`. The survivor stays in the analysis under its original arm (intent-to-treat).
  - **Sends:** any enrollment in a conflict that includes a holdout is excluded from BeaconAI sends, so a holdout customer is never contacted under another key.
  - **Reporting:** every estimate states the merge and conflict counts. Above 1% of the cohort, the estimate is flagged for review.
- This is the whole identity scope. No general identity-management system is built.

### 4.4 Holdout enforcement
- At each BeaconAI handoff, audience members resolving to a **holdout** enrollment are removed from the send and recorded as excluded (`program_holdout`).
- **Program-arm enrollees** get no additional per-campaign holdout: when they are in an audience, they are sent.
- **Customers outside the cohort** keep the existing per-campaign bucket.
- **Manual targeting.** The merchant agrees not to add recipients to a BeaconAI draft in Klaviyo, and not to send BeaconAI content to held-back customers. Reconciliation flags a provider sent count above the planned recipient count as possible contamination.

### 4.5 Common start rule
- **Start S** = the provider-confirmed send time (delivery state `sent`, with `provider_sent_at`) of the **first BeaconAI campaign confirmed sent after T0**.
- S is the **same calendar instant for every enrollee in both arms**, whether or not they were in that campaign's audience. Follow-up is `[S, S + 90 days)`.
- **If the first campaign is never confirmed sent** — the draft was never sent, creation failed, the outcome stayed uncertain, or a scheduled send was cancelled — it does not start the clock. S is set by the first campaign that *is* confirmed sent. Enrollment and assignment are unchanged meanwhile, and holdout exclusion applies from T0.
- **If no campaign is confirmed sent within 30 days of T0,** the cohort closes as `not_started`, with no estimate. A new cohort needs a new T0 and a fresh enrollment; nothing is backdated.
- Orders before S are not outcomes. They may be reported as labelled baseline context only.

### 4.6 Estimand
- **Intent-to-treat over the whole cohort:** mean refund-adjusted net revenue per enrolled customer in `[S, S + 90d)`, program arm minus holdout arm.
- **Total:** the per-customer difference × the number of program-arm enrollees.
- **Dilution:** program-arm customers who were never in an audience are included. That dilutes the effect, but it is the question the program actually answers, and it removes any dependence on who the engine chose to target.
- **Before `S + 90d` the state is "measuring".** No interim verdict is given.

### 4.7 Wording
These counts are distinct and never interchangeable:

| Term | Meaning |
|---|---|
| **Assigned to receive BeaconAI campaigns** | Program-arm enrollees |
| **Held back** | Holdout enrollees |
| **In a campaign audience** | Engine membership for a campaign |
| **Confirmed sent** | The provider's reported recipient count, if it gave one; "unavailable" otherwise |
| **Delivered** | Not available in the pilot; never shown |

A count of assigned customers is never labelled "sent".

### 4.8 Repeated campaigns and per-campaign comparisons
Because the holdout is persistent, a campaign's held-back group has also missed every earlier BeaconAI campaign, while its program-arm recipients may have received several. A per-campaign comparison therefore measures *customers in this audience assigned to receive BeaconAI campaigns vs held back, from this campaign's send*. That is the cumulative effect of BeaconAI exposure, **not the effect of this one email**, and it must be labelled that way.

Per-campaign results are never summed into a program figure: the same customers and orders would be counted more than once.

### 4.9 Reporting floors
- **Unique purchasers,** not orders: distinct enrollees with at least one qualifying order in the window. Ten orders from one customer are one purchaser.
- **Proposed floors:** ≥ 100 enrollees per arm, and ≥ 10 unique purchasers per arm. Below either, the state is "insufficient data", which is distinct from "no clear difference".
- **The current campaign gate counts orders, not purchasers.** It must switch to unique purchasers before any merchant sees a campaign verdict (owner: Ticket G, Results truth).

### 4.10 Estimator
- **Current code:** an unequal-variance standard error with a 1.96 normal critical value (§1).
- **At pilot sizes** (e.g. a 23-person campaign holdout, about 22 degrees of freedom, *t* ≈ 2.07) a Welch *t* interval would be noticeably wider.
- **The final estimator** — normal approximation, Welch *t*, or a bootstrap — is **left to statistical review**. One estimator will be chosen and shown; multiple estimators are deferred.

## 5. What the design supports claiming
- "Over 90 days, customers assigned to receive BeaconAI campaigns spent $X more (or less) per customer than customers held back (95% interval $L–$H)." The result may well be "no clear difference".
- **Not** total store lift, **not** one email's effect, and **not** a guaranteed or narrowing interval.
- Campaigns before T0, and customers outside the cohort, are descriptive only.

## 6. Precision (test store, illustrative)
Among the test store's customers with prior orders, 90-day revenue has mean $33.93, SD $36.72, and 44% zero (N = 1,284). With a 10% holdout, the 95% interval on the per-customer difference is about:

| Cohort size | ±95% per customer | Smallest detectable (80% power) | As % of mean |
|---|---|---|---|
| 555 | ±$10.18 | $14.55 | 43% |
| 1,200 | ±$6.93 | $9.89 | 29% |
| 2,200 | ±$5.12 | $7.31 | 22% |

Intent-to-treat dilution makes a real effect *smaller* than these thresholds need. **An inconclusive result is the likely outcome at single-merchant scale,** which is why §3.7 promises only an estimate with its uncertainty.

## 7. Migration
- Existing recipient rows stay as they are, labelled descriptive.
- No enrollment, randomization or start date is invented for the past.
- Rollback disables enrollment and exclusion, and keeps every stored row.

## 8. Collection — complete (Ticket F PR #41)
1. Recipients are immutable once the campaign is frozen at handoff. The check runs under the campaign row lock.
2. Each recipient's email alias is stored, and engine members excluded before the split are recorded with a reason (`no_email`).
3. Measurement anchors on a provider-confirmed send only: state `sent` with `provider_sent_at`.
4. Treated customers the provider did not deliver to stay in the analysis (intent-to-treat), and a test pins this.
5. The ever-treated program number is withdrawn (`protocol_not_live`).
6. Results lists every handed-off campaign by its durable delivery state — draft created, scheduled, needs checking, draft not created, sent with no time — plus legacy local-only sends. None is measured before a confirmed send.

## 9. Deferred (not in the pilot)
Rolling enrollment; opportunity-restricted analysis; CUPED or other covariate adjustment; multiple estimators; a general identity-management system; holdout rotation or epochs; daily trends.

## 10. Still unresolved
1. **Founder approval** of §3 in full, including the merchant agreement wording (§4.4).
2. **T0 for the pilot shop,** and the 30-day no-start expiry (§4.5).
3. **The 365-day eligibility lookback** (§4.1).
4. **The reporting floors'** values (§4.9).
5. **The estimator** (§4.10) — statistical review.
6. **The 1% identity-conflict flag** threshold (§4.3).
7. **The contamination check:** whether a provider sent count above plan should block the estimate or only flag it (§4.4).
8. **When the campaign gate switches to unique purchasers** — due in Ticket G.

## 11. For the statistical reviewer
1. Is whole-cohort intent-to-treat with a common calendar start S appropriate when S depends on when the first send is confirmed?
2. Which estimator, given heavy-tailed revenue and a 10% holdout?
3. Are the floors adequate, and should an inconclusive result carry a stated minimum detectable effect?
4. Is the identity-conflict rule (survivor keeps its original arm, stays in the analysis) acceptable, and at what conflict rate should the estimate be withheld?
5. Anything that makes per-campaign descriptive reads alone the better choice for a single-merchant pilot.
