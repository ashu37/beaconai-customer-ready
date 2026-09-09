# BeaconAI V2 — final sellability and UX review

Updated September 9, 2026. This version supersedes the earlier review and the minimal Results mockup. It is a product specification for an implementation plan, not a request to rebuild the engine.


**Pre-revenue delivery scope:** [IMPLEMENTATION_PLAN.md](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/IMPLEMENTATION_PLAN.md) supersedes this review’s build sequencing. In particular, defer the full UX-04 registry and daily charts; preserve basic history, truthful comparisons and measurement collection.

## 1. Decision and sales proposition

**The product has enough substance for a narrow, founder-assisted paid pilot after a focused app pass. The immediate investment should be complete and trustworthy input data, merchant-approved branded email, reliable campaign workflow, and a useful Results workspace including repaired program measurement.** This is an assessment of pilot readiness, not proof of product-market fit or production certification.

Sell: **“Know which retention campaign to try next, prepare its audience and email, and keep seeing what happened after you send.”**

Start with a Shopify/Klaviyo beauty merchant using USD, matching the inspected API's vertical and currency assumptions. Use assisted onboarding and manual commercial arrangements. Do not spend the next cycle building billing, a full email editor, or a general experimentation platform.

The earlier Results direction removed too much useful evidence. Merchants need a clear decision at the top **and enough substance underneath to inspect it**. Simplification should remove interpretation work, not remove signals.

The mentor's useful lesson is persistence: each campaign becomes an enduring record with its rationale, audience, execution, comparison, and later outcomes. A merchant returns to review existing work as well as discover new recommendations. This supports a recurring product proposition; whether merchants value it enough to renew still needs a paid pilot.

## 2. Review basis and engine implications

Reviewed the current app and API, populated seed Results, and the engine's CLAUDE.md, PRODUCT.md, STATE.md, PIVOTS.md, ROADMAP.md, decision records, evidence/handoff contracts, known issues, and recent frontend evidence work. UI inspection covered approximately 990px, 1440px, and 390px. Source-level risks below were not all reproduced as induced failures. No campaign was sent, seed data replaced, or engine rerun for this review.

The supplied Intelligems screenshots and mentor transcript are design references. They demonstrate a durable registry, comparison views, and post-test observation. They do not establish capabilities BeaconAI already has.

### What the engine work changes about this recommendation

- **Use the current schema and later decisions.** CLAUDE.md describes a frozen 2.0.0 contract, but current `engine_run.py` emits 2.1.0 and later decisions document additive evidence work. Older statements about no frontend or no ML are not a complete description of this repository.
- **The engine already has useful depth.** Existing work includes retention, RFM, predictive models, and audience distributions. Expose approved, typed evidence; do not propose building these capabilities again. Model ranking is not proof that a campaign caused lift.
- **Rich evidence is consistent with the product.** The evidence contract asks, “what decision does this pixel justify?” A chart explaining an audience or campaign outcome passes that test. An unrelated analytics dashboard does not.
- **Keep descriptive facts separate from inference.** Valid observed facts can remain useful when a prediction is unavailable. A predictive precision failure need not erase valid observed history; a data-integrity failure can require suppressing the affected visualization entirely. Apply the exact typed rules, rather than one generic confidence switch.
- **Preserve evidence provenance.** The handoff contract says narration consumes `evidence_source`, not `evidence_class`. Store observations must not become “similar stores,” and modeled opportunity must not become measured incremental revenue.
- **Keep engine output immutable.** PRODUCT.md explicitly places approval state in the application database. Campaign execution, saved edits, provider status, and measurement history belong there too. Historic filesystem-only constraints in the engine track are not a reason to remove the current API/database.
- **Do not confuse changes in store state with campaign outcomes.** `month_2_delta` is not realized campaign lift. The API's existing holdout measurement is also not the deferred engine outcome-to-calibration loop.

The design below uses these boundaries. It requires application work and modest reporting additions, not another engine research phase.

## 3. Why the current app feels unfinished

These are the highest-impact gaps across the complete merchant journey.

| Gap | Evidence in the inspected app | Required product change |
|---|---|---|
| Email does not match the merchant brand | Generated HTML hard-codes orange, Arial, and a text brand name rather than a merchant logo. | Merchant-approved branded email is a first-send prerequisite; see §6. |
| Partial input can look ready | Sync returns counts without a persisted completeness/coverage contract; analysis reads mutable clean tables. | Publish only validated sync generations to analysis; preserve the last complete input. |
| Fragile layout | Detail numbers fragment at laptop widths; preview clips; mobile retains a large sidebar and squeezed metrics. | Responsive workbench, readable measures, collapsible navigation, and full-page campaign details. |
| Unclear evidence | All three inspected recommendations were `STORE_OBSERVED` but labeled as modeled from similar stores. “Observed effect,” L56, and generic “Orders analyzed” lack correct business meaning. | Explicit provenance mapping, actual metric and denominator units, readable dates, and plain-language rationale. |
| Weak decision hierarchy | Selecting a recommendation makes it “Primary”; inventory counts precede useful action. | Stable engine priority; selection styled separately; lead with next action. |
| Lost engine information | Watching/abstention data is passed through but unused; different hold reasons collapse into “more data.” | Meaningful held and watching states, with reasons and next review steps. |
| Unreliable work continuity | Hydration filters by current run; audience resolution chooses latest run; save failures are swallowed and pending edits can be cleared on unmount. | Durable campaign identity, origin-bound audience/copy, visible saving/retry, and historical retrieval. |
| Ambiguous execution | “Approval in Klaviyo” conflicts with “Send now”; an accepted asynchronous job becomes “sent.” | One clear approval path and distinct draft, queued, sent, and failed states. |
| Counts overclaim | Whole audience is sometimes labeled as sent although a holdout is excluded. | Separate audience, assignment, eligible estimate, actual sent, and delivered counts. |
| Weak return experience | Results is a compact verdict list without a substantial permanent campaign workspace. | Searchable program history and rich campaign details with follow-up. |

There are additional practical trust fixes: distinguish Shopify sync time from analysis time; mark stale email previews; preserve edits on template changes; make destination links editable; and review sender, category, and brand context before sending. A mixed sports/skincare demo is not proof every real store has incorrect categorization, but the demo must be coherent and explicitly labeled.

The vague confidence meter should be replaced with a specific evidence status and explanation. A lower confidence signal is not necessarily an invalid audience or a reason to block all observation.

## 4. Results: the final product direction

### 4.1 Keep three clear destinations

- **Briefing:** What is worth trying next, and why?
- **Campaigns:** What are we preparing or sending?
- **Results:** What happened, what is still being measured, and what did we learn?

Results should have two levels: a **campaign registry** and a **permanent campaign detail page**. Use stable campaign IDs and navigable URLs. Preserve filters when returning from a detail page. Do not make a narrow expandable row carry the whole analysis.

### 4.2 Program overview: operational truth first

Header: **Campaign results**. Supporting copy: “Track your campaigns and the customers assigned to each comparison.” Show a visible date filter, initially the last 90 days, with access to all history. Define it as campaign send dates; display each campaign's actual measurement window separately.

Use three or four compact summary metrics:

1. Campaigns sent in the selected period, based on reconciled execution status.
2. Campaigns still measuring.
3. Campaigns with a completed primary window.
4. Unique customers assigned across the selected campaigns, only with proper deduplication and an explicit assignment label.

**Repair program measurement as a committed product workstream; do not abandon the program number.** Do not ship the current aggregate incremental-revenue hero as the central promise before that repair. The inspected program calculation mixes exposure histories, can include revenue before a customer's first send, and returns zero aggregate orders. It needs a validated definition before it supports a causal program total; §5 defines the required engineering design gate. Do not replace it with a sum of per-campaign lift: recipients and windows can overlap.

An observed program revenue total is optional, only after deduplicating orders and defining the included customers and dates. This descriptive fallback can support the demo while the repair is in progress. The target experience includes a defensible program estimate with interval, cohort size, dates, freshness, and its actual assessment status. An inconclusive program estimate must remain inconclusive.

### 4.3 Registry: a working list of campaigns

Tabs: **All / Measuring / Completed / Needs attention**. These filter measurement progress; delivery failures should also appear in Needs attention. Search by campaign name. Show total count and pagination, without a silent history cap.

Use five primary columns on desktop:

| Campaign | Progress | Revenue per customer | Estimated difference | Review |
|---|---|---|---|---|
| Name; sent date; treatment/holdout counts | Measuring · day 12 of 30 | Email group vs holdout | Measuring, or eligible estimate and interval | Open results |

The registry always summarizes the **30-day primary window**, clearly labeled. A 60-day detail selection must not silently change what the registry means. Show early descriptive comparison values with “Early observation”; withhold conclusive verdicts until the relevant requirements pass.

Use a short outcome vocabulary: **Measuring / More data needed / Positive result / Negative result / No clear difference / Comparison unavailable**. “No clear difference” is not “the campaign had no effect.” Keep delivery status separate from outcome status.

On mobile, render the same information as compact campaign rows/cards with the campaign name, stage, primary comparison, and a clear detail action. Do not compress five columns into unreadable text.

### 4.4 Permanent campaign detail: information hierarchy

The page should feel like a saved business object, not a generated report. It has a name, dates, an actual email, a defined audience, a status, a history, and usable navigation.

```text
Results / Campaign name                         Open email in Klaviyo
Sent date · Delivery status · Original audience

Outcomes | Follow-up | Original campaign

30 days [primary]   60 days   90 days
Day 12 of 30 · Orders synced through [timestamp] · Calculated [timestamp]

Outcome and next step
“Still measuring. Your 30-day review is on [date].”

Revenue/customer    Purchase rate    Orders/100 customers    AOV
Email vs holdout    Email vs holdout Email vs holdout        Email vs holdout

Cumulative revenue per assigned customer [observed days only]

Group comparison table

How this is measured · Data notes
```

**Outcome and next step.** Give one sentence explaining what can currently be concluded, one concrete reason, and one appropriate action. Examples:

- “Still measuring. Review the 30-day result on October 9.”
- “The email group generated more revenue per assigned customer. The estimated range is above zero for this window.” Only when maturity, data quality, and the implemented evidence checks pass.
- “The result is not clear yet. The estimated range includes both a decrease and an increase.”
- “Too few purchases to assess a difference reliably.” Only if the backend reports that reason; do not use it as a generic fallback.
- “Comparison unavailable. No usable holdout was recorded.” Descriptive observations can still be shown when valid.

Use green/red only for supported positive/negative conclusions. A positive point estimate alone must not color the entire page as a win.

**Four comparison cards.** Lead with revenue per assigned customer. Then purchase rate, orders per 100 assigned customers, and average order value. Use paired horizontal bars or compact paired values; identify Email group and Holdout consistently. Each card has units, its own meaningful scale, raw supporting counts, and a short definition. AOV is a secondary order-based metric, not proof of incremental success.

Do not display a confidence score on every card. Keep the primary estimate and interval in one prominent place, with other metrics providing context rather than multiple competing winner verdicts.

**One useful trend chart.** Plot cumulative revenue per assigned customer by day since send, for both groups. Use actual daily aggregates and a shared scale. Stop at the last observed date, leave future days blank, and show freshness. Never manufacture a daily curve by interpolating 30/60/90-day summaries. Until daily reporting exists, use the comparison table; a fabricated chart is worse than an honest table.

**Comparison table.** Show both groups side by side:

- Assigned customers, actual sent where available, and distinct purchasers.
- Orders and refund-adjusted revenue.
- Revenue per assigned customer, purchase rate, orders per 100 customers, and AOV.

Expose the raw denominators. A larger group's total revenue is not evidence it performed better. Keep the assigned group as the comparison denominator; do not retrospectively remove non-deliveries from treatment while leaving the holdout intact.

**Measurement explanation.** Expandable, with a short visible summary: “We compare purchases by customers assigned to the email group with customers assigned to the holdout over the same period.” Disclose window dates, group assignment, refunds/cancellations, freshness, and known interference. Do not claim isolation from all other marketing unless enforced.

### 4.5 Follow-up: the mentor's recurring-value requirement

The original campaign remains accessible after its primary window closes. Follow-up shows **30, 60, and 90 days from the same send**, using the original assigned groups.

- Default to the primary 30-day result; show later windows as additional observations.
- Clearly distinguish cumulative 60-day results from purchases during days 31–60. Do not mix their labels or denominators.
- Keep valid descriptive results visible while a later window is incomplete.
- Show upcoming review dates and which windows are ready. Completion of one window does not mean every later window is mature.
- Retain historical campaigns beyond 90 days. The pilot measurement horizon is 90 days; do not promise indefinite automated measurement or a year of updates.
- Reconcile late orders/refunds transparently. Closed-window figures may be revised, but preserve their calculation timestamps and a change note or snapshot history. Never silently rewrite the original send date or group assignment.
- A repeat campaign creates a new execution record with a fresh audience review. It does not overwrite the old campaign or blindly resend its frozen audience.

This is enough of an ongoing program for the pilot. Subscription-specific lifetime value, profit, landing-page visitors, multiple creative variants, and arbitrary annual follow-up are outside scope. Purchase behavior among converters alone must not be presented as randomized campaign lift.

### 4.6 Original campaign: bring the engine's signals into the record

Preserve the exact originating recommendation and evidence snapshot, email revision, audience, treatment/holdout assignment, and send details. Show:

1. **Why this campaign was suggested:** a short rationale with the actual observed metric, dates, and source label.
2. **Who it was for:** audience size, plain-language definition, and the applicable typed distribution.
3. **Supporting store context:** eligible retention or segment evidence, clearly distinguished from this campaign's results.
4. **What was sent:** subject, email preview, destination link, provider reference, and send date.

Select evidence using `mechanism_intent.type` and the contract's rendering rules, not keywords guessed from a campaign title. A dormancy distribution can explain audience selection; a store retention curve is context, not the treatment group's outcome curve.

Do not promise distributions for all held plays: the current rejected-play shape does not carry the same Audience evidence. Do not derive missing audience membership in the frontend. Verify producer semantics before labeling AOV or reorder distributions; enum names alone are not sufficient. Do not reintroduce suppressed dollar figures through chart axes or tooltips.

## 5. Data and state contract needed for implementation

### Metric availability

| Signal | Current foundation | Work needed / rule |
|---|---|---|
| Assigned treatment/holdout counts | Persisted recipient arms | Preserve immutable assignment and origin; reconcile labels. |
| Orders and revenue by group | Existing 30/60/90 measurement service | Verify identity deduplication, actual send anchor, refunds, quality and freshness. |
| Revenue/customer and estimated difference | Existing aggregates and comparison logic | Fix predicates and units; apply one selected window everywhere. |
| Purchase rate | Distinct purchaser aggregate absent | Add distinct purchasers / assigned customers. Never substitute order count. |
| Orders/100 customers; AOV | Derivable from existing aggregates | Orders / assigned × 100; revenue / orders. Zero denominator yields unavailable, not zero. |
| Daily trend | Not provided by window totals | Add daily group aggregates in the application reporting API. |
| Actual sent / delivered | Assignment is not provider telemetry | Reconcile provider counts/status where available; otherwise show “Not available.” |
| Original evidence | Immutable run exists | Persist/retrieve campaign's originating run, not today's recommendation. |
| Measurement history | Latest aggregates are overwritten | Add snapshots/change metadata for revisions and follow-up. |
| Program incremental lift | Current calculation is unsuitable | Committed repair: specify assignment, estimand, exposure windows, overlap handling and uncertainty; validate before presenting as incremental. Required before claiming program ROI in a renewal conversation. |

Keep delivery state, measurement stage, and outcome assessment as separate fields. Each window response should contain window dates, observed-through time, calculated-at time, arm counts/metrics, estimate/interval where allowed, and typed reasons such as incomplete window, insufficient events, missing holdout, stale data, or integrity failure. Map actual backend conditions; do not invent reason strings from a boolean in React.

Every value, interval, progress label, and verdict in the selected detail window must come from that same window response. Unknown counts remain null. Zero means a known measured zero. Provider failure, measurement failure, and an inconclusive business result require different recovery actions.

### Program measurement: committed repair, with a design gate

The program number is a core retention/renewal hypothesis, not an optional dashboard decoration. Pooling may improve precision, but audience count alone does not establish adequate power: holdout size, revenue variability, repeat observations and effect size matter. Do not promise that this will be the only statistically resolvable result without inspecting those quantities.

The present `BOOL_OR(arm = treated)` grouping compares ever-treated customers with customers never treated among included campaigns. Fixing the start date and zero order count is necessary but does not make this a valid randomized program comparison.

Before implementing the replacement, write and approve a short measurement design covering:

- **Business question:** additional refund-adjusted revenue per eligible customer from the BeaconAI campaign program over a defined follow-up horizon. Distinguish this from total store revenue and provider attribution.
- **Assignment:** inspect whether existing records support a defensible pooled campaign estimate. If customers switch arms across campaigns, do not silently reinterpret them as persistent program assignments. Historical observed comparisons can remain descriptive; missing historical randomization cannot be reconstructed after the fact.
- **Prospective option:** evaluate a stable customer-level program holdout against campaign-specific holdouts. Specify enrollment eligibility/date, assignment persistence, treatment opportunities, exclusion from BeaconAI sends, and merchant agreement. This changes execution and requires a reviewed protocol; it is not merely a reporting query change.
- **Timing and population:** define each customer's enrollment/exposure anchor, common horizon, incomplete follow-up handling, and the population to which any total incremental estimate applies. Exclude pre-enrollment revenue from the outcome; retain it only as explicitly defined baseline context.
- **Overlap and uncertainty:** account for repeated customers/orders and campaign interference, rather than counting customers as independent each time. Specify how other marketing is treated and what claims the design supports.
- **Release proof:** independent expected-value fixtures, assignment checks, zero-event handling, interval/reason consistency, late refunds, changing eligibility, repeated campaigns and a realistic precision assessment. Show measuring/insufficient/unclear states when appropriate.

Deliver a versioned program response with cohort/assignment definition, dates, counts, observed revenue per customer, supported estimate and interval, typed assessment reasons, data coverage, and calculation timestamp. If retrospective lift cannot be recovered, start valid prospective measurement during the pilot; do not invent historical uplift to populate the hero. This is application measurement work, distinct from the two future engine priorities.

### Current Results defects to fix before restyling

The populated seed review exposed these specific contradictions:

- The program hero showed approximately **+$11,866, range $7,753–$15,978**, but said the range crossed zero. `summarizeProgram` returns zero aggregate orders and the UI treats a failed significance check as a zero-crossing explanation. Correct the data and reason mapping; do not relax evidence thresholds.
- A five-day campaign displayed a positive interval while still measuring its 30-day window. Early raw observations can be useful, but must not imply a completed positive result.
- Switching to 60 days left a row labeled “Worked” from its 30-day result while the detail was only around day 45 of 60. Eliminate mixed-window state.
- A row labeled **4,680 sent** included **456 held out**. Planned treatment was 4,224; actual sent still requires provider evidence.
- Historical names and context can depend on the latest slate. Store campaign display metadata and retrieve the immutable origin independently.

These are trust defects, not cosmetic issues. The exact seeded numbers are illustrative observations, not evidence of customer revenue or model accuracy.

## 6. Non-Results changes required to sell the workflow

### Merchant-branded email — first-send blocker

The earlier review underweighted this. In `klaviyoClient.js`, the generated `campaignHtml` path hard-codes Arial, orange `#f08a24`, background/button styles, and a text brand label. There is a custom `campaign.email.html` escape hatch, so this is a verified defect of the generated path, not proof that every possible custom email uses those styles. Pulling product images and brand copy is not equivalent to adopting a brand's visual identity.

For a brand with established creative standards, an email they refuse to send prevents all downstream value. Promote this above Results polish.

**Bounded pilot solution:** one merchant-approved reusable email shell per store, populated with BeaconAI's campaign copy/product slots. Prefer the merchant's existing approved Klaviyo HTML/template where compatible; otherwise configure logo, background/text/button colors, layout, typography with email-safe fallbacks, footer and links. Assisted configuration is acceptable. Automatic theme extraction is optional and its suggestions require review; do not assume Shopify contains an authoritative brand book. Do not build a general drag-and-drop editor.

Persist a versioned brand/template configuration and bind the exact rendered revision to each campaign. Preview and provider draft must use the same renderer and revision. Validate logo sizing/alt text, CTA destination, footer/unsubscribe behavior, mobile readability and representative email-client rendering. Never silently substitute BeaconAI branding when configuration is missing. Show “Brand setup needed” and allow preparation, but require merchant approval of the actual email before first handoff/send.

**Acceptance:** two deliberately different test brands produce distinct approved emails; their colors/logos do not leak between shops; missing assets have an explicit recovery path; refreshing or changing the default template does not alter a historical send. A merchant can approve the actual draft without rebuilding it in Klaviyo.

### Sync completeness — recommendation integrity blocker

The defect is bigger than timestamp wording. The current client paginates without the old default cap, which is useful, but accepts explicit finite limits. The sync route returns `ok: true` and row counts without an explicit completeness/coverage record. Clean-table writes occur sequentially without an enclosing generation publication contract, and engine input reads those mutable tables. Thus a bounded import or interrupted write can lack a trustworthy readiness distinction. Yesterday's incorrect briefing is user-reported; this review has not reconstructed that incident's logs or established its exact cause.

**Required contract:** persist a sync generation with per-resource status, counts, pagination exhaustion/truncation, requested and accessible history coverage, start/finish times, error details and validation outcome. “Connected,” “fetched some rows,” and “ready for analysis” are different states. Completion means complete for declared and adequate coverage, not merely that the last HTTP request succeeded.

Stage and validate a generation before publishing it as the active engine input, using an atomic promotion or equivalent consistent snapshot. A failed generation must not replace the last validated complete input or mix old/new resources in a new analysis. Link every engine run to the exact input generation. Block analysis server-side when there is no eligible generation; if the last valid generation is retained, label its age and require the configured freshness policy rather than silently treating it as current. Mark existing recommendations affected by known bad input as needing reanalysis, and block stale audience handoff until revalidated.

**Acceptance:** simulate a late-page fetch failure, finite-limit truncation, a write failure after customers but before orders, insufficient accessible history, and a retry. None may appear as a complete new input or drive a new ready briefing. Retry must be idempotent; the previous valid generation remains identifiable. The UI explains what is incomplete and offers retry. Diagnose the reported incident using its run/input records before declaring it fixed.

### Briefing and evidence

Lead with the next campaign, audience, reason, and action. Move Products/Customers/Orders into a compact data panel. Preserve stable engine ordering. Translate “Play thesis” to “Why this campaign” and use action labels that describe actual behavior.

Map `STORE_OBSERVED`, `STORE_MEASURED`, and other supported sources explicitly. Show metric-specific sample units, not generic “orders analyzed.” Do not call recommendation opportunity ranges lift or expected revenue from sending when the engine contract does not authorize it.

Render distinct loading, failed, no-run, no-recommendation, held, and watching states. Explain inconsistent windows, missing measured signals, and data-quality holds individually. “No campaign recommended this week” can be useful; contradictory claims that everything was strong enough to recommend cannot.

### Campaign preparation and persistence

Show Saving / Saved / Save failed with retry. Flush or persist pending edits before navigation and external actions. Label stale previews and recover without discarding copy. Give merchants a safe way to replace a template while preserving or restoring their edits.

Use campaign IDs for persistence and URLs. Bind copy, audience and provider assets to the originating run. The current unique run/play association needs an explicit policy for repeat execution: the pilot can start a new campaign from a fresh recommendation; never overwrite an earlier send to simulate a repeat.

History must survive refresh, a new engine run, and the absence of that play from the latest recommendations. Paginate beyond the current listing cap.

### Send readiness

Choose one coherent pilot path: **create a Klaviyo draft, review there, then reconcile the actual send back into BeaconAI**. If BeaconAI retains direct sending, require saved revision, reviewed links/sender, verified audience readiness, and separate queued/processing/sent/failed states. An accepted send job is not a completed send.

Show a count reconciliation: engine audience → matched identities → assignment → holdout/treatment → provider eligibility where known → actual sent. Validate the real consent/suppression path before the first live send; engine known issue AJ explicitly leaves enforcement unconfirmed. Do not claim all unsubscribers are excluded based on copy or comments alone.

Cold-start `MATERIALIZED_UNRANKED` membership can be valid; lack of ML ranking alone must not block a usable campaign. Preserve engine membership instead of reconstructing audience heuristics. For the pilot, review overlapping campaigns manually; do not add batch sends before customer-level suppression is resolved.

### Access, onboarding, and freshness

The inspected API routes accept shop/campaign identifiers without visible route-level authentication/tenant checks. Verify any deployment gateway protection and enforce shop ownership before exposing real merchant data. This is a live-pilot prerequisite, not an invitation to expand into a full enterprise security project.

Show connected store, brand context, supported currency, latest successful sync, and latest analysis separately. Refreshing analysis must not masquerade as syncing Shopify. Give failed sync/analysis a clear retry action. Keep setup founder-assisted until the repeatable onboarding path is understood.

## 7. Ordered implementation work packages

These are work packages, not yet fully specified engineering tickets or calendar estimates. Resolve the design gates below before treating them as an executable backlog. The core Results scope is the registry, full detail, comparison metrics, daily trend, and 30/60/90 follow-up. Do not reduce it back to a verdict-only screen.

| ID | Deliverable | Dependency | Acceptance |
|---|---|---|---|
| UX-00A | Sync completeness and input publication | None | Per-resource coverage and failure tests pass; analysis uses a validated generation; affected briefings require reanalysis. |
| UX-00B | Merchant-approved branded email | UX-02 for campaign snapshots | Per-store shell/configuration; identical preview/provider revision; two-brand and missing-asset checks pass. |
| UX-01 | Correct evidence and metric semantics | None | All source enums map correctly; actual units appear; no unauthorized lift language. |
| UX-02 | Durable campaign identity and saves | None | Refresh/new run preserves copy, origin audience and assets; failure is recoverable; old campaigns remain reachable. |
| UX-03 | Measurement response and truth fixes | UX-00A, UX-02 | Typed reasons, same-window values, correct denominators, null handling and timestamps; misleading program lift withheld. |
| UX-03P | Repair program measurement | UX-03; reviewed measurement design | Versioned population/window/assignment definition; independent validation; prospective collection if historical comparison is invalid. |
| UX-04 | Results registry and routing | UX-02, UX-03 | Search/filter/pagination, primary-window labels, stable detail URLs, working back navigation. |
| UX-05 | Rich Outcomes page | UX-03, UX-04 | Four contextual metrics, group table, primary interval, truthful state/action, daily observed trend after API aggregation. |
| UX-06 | Follow-up and original campaign | UX-02, UX-03 | 30/60/90 selection is consistent; historical evidence/email retained; revised measurements explain changes. |
| UX-07 | Responsive shared workbench | None; applied to UX-04–06 | Readable at 1440/1280/1024/990/768/390px; no clipped primary content or inaccessible action. |
| UX-08 | Reliable send handoff and access | UX-00A, UX-00B, UX-02 | Verified ownership/consent path; saved revision; reconciled execution; correct counts; no false “sent.” |
| UX-09 | Briefing, onboarding and recovery | UX-01, UX-07 | Distinct held/empty/error states; stable priority; separate sync/run timestamps; usable next step. |
| UX-10 | Seed acceptance and assisted pilot rehearsal | UX-01–09 | Truthful demo, reload/history checks, complete prepare→send-status→results walkthrough. |

For a sales demo, finish the truth fixes and demonstrate the richer Results shell against clearly marked seed data. Before a real campaign, finish sync integrity, merchant-approved email, persistence, access, and send readiness. Start the agreed program measurement collection before the relevant pilot sends; do not defer assignment design until renewal. Before calling the pilot measurement experience complete, finish the group metrics and follow-up behavior. Do not sell unfinished reporting as already live.

### Engineering handoff status and required next artifact

This document is an engineering-readable product review and scope agreement. **It is not yet a complete implementation plan.** Its acceptance criteria help, but an engineer would still have to make consequential choices about sync publication, brand-template integration and program measurement. Those choices should not be hidden inside UI tickets.

Convert it into a plan with one ticket per coherent slice. Each ticket needs: current behavior/reproduction, named files/services, exact data/API changes, UI states and copy, dependencies, migration/backfill policy, deterministic acceptance tests, rollout/rollback, and a clear definition of done. Mark source-verified defects separately from reported incidents and proposed features.

Resolve three explicit design gates first: (1) sync generation publication and input coverage eligibility, (2) supported branded template format and renderer/handoff parity, and (3) program assignment/estimand/uncertainty design. For each, document the selected approach, rejected alternatives briefly, and compatibility with existing records. Keep unresolved decisions visibly blocked rather than claiming the entire backlog is ready.

Recommended execution order: input truth and incident diagnosis → sendable branded email plus reliable persistence → valid measurement collection and send readiness → Results registry/detail/follow-up → program estimate presentation after validation. Responsive fixes can proceed alongside these foundations. Historical backfills must not manufacture missing send times, group assignments, or completeness metadata.

## 8. Seed tests and release acceptance

The seed data is valuable for demonstrating a positive, unclear, and still-measuring result. It is not sufficient to validate measurement correctness: the inspected generator uses simplified orders and fixed AOV, and checking a realized sample difference against its own interval does not establish calibration or causal validity.

Add deterministic app/reporting fixtures with a fixed clock and independently calculated expected values:

1. Positive, negative, and interval-crossing-zero outcomes; reason text and color agree.
2. Day 29/30, 59/60, and 89/90 boundaries; every selected-window value changes together.
3. Small samples and zero events; distinguish insufficient evidence from a clear zero result.
4. Missing holdout and missing provider counts; no invented comparison or sent total.
5. Unequal group sizes, repeat purchasers and multiple orders; purchase rate is not order rate.
6. Refunds, cancelled orders, late ingestion and revision history.
7. Duplicate identities/orders and overlapping campaigns; no duplicated program claims.
8. Failed/stale measurement refresh; timestamp and recovery remain visible.
9. Prior-run campaigns, missing latest-slate play, reload, pagination and saved deep links.
10. Valid descriptive evidence with withheld prediction, versus integrity failure requiring suppression.
11. Save failure, navigation with pending edits, template replacement and stale preview.
12. Narrow layouts, keyboard navigation, focus, readable chart labels and non-color status cues.

Do not rerun a destructive seeder against merchant data. Keep the demo isolated and label its outcomes as examples.

A pilot is ready when a merchant can answer without explanation: **Why this campaign? Who receives it? What action sends it? What happened? How sure are we? When should I return?** The app must survive the corresponding workflow without losing work or overstating results.

Judge PMF using actual behavior: willingness to pay, choosing and sending a recommendation, returning for a review, trusting the explanation, and wanting another campaign. A small pilot producing inconclusive lift is not automatically product failure; repeated confusion, lack of relevant actions, or no desire to return is useful product feedback.

## 9. Exactly two future engine priorities

These follow the paid pilot; neither should reopen the engine before fixing the app.

1. **Validate and calibrate existing recommendations on real merchant outcomes.** Test whether current rankings, opportunity estimates, and evidence labels correspond to useful decisions across actual stores. Focus on the existing model stack and abstention behavior. Synthetic coverage does not establish predictive accuracy; collect merchant decisions and outcomes before adding more models or plays.
2. **Close the deferred outcome-to-learning loop.** Once assignment and outcome records are trustworthy, use completed campaign evidence to update the engine's priors or future recommendations under explicit rules. Preserve provenance and avoid learning from contaminated or inconclusive comparisons as if they were wins. This is the deferred engine feedback phase, not something the current Results service already accomplishes.

## 10. Implementation source map

Paths are relative to this repository; links open the inspected local files. Line numbers in older findings may shift during implementation.

- Engine authority and chronology: [CLAUDE.md](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/engine/CLAUDE.md), [PRODUCT.md](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/engine/PRODUCT.md), [STATE.md](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/engine/STATE.md), [DECISIONS.md](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/engine/docs/DECISIONS.md).
- Evidence rules, including superseding L-EV-13–20: [evidence_layer.md](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/engine/docs/evidence_layer.md), [handoff_architecture.md](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/engine/docs/handoff_architecture.md), [engine_run.py](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/engine/src/engine_run.py).
- Audience and consent limitations AG–AJ: [KNOWN_ISSUES.md](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/engine/KNOWN_ISSUES.md).
- App layout, evidence labels, campaign state and Results: [App.jsx](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/web/src/App.jsx), [styles.css](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/web/src/styles.css), [engineRunPresenter.js](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/api/src/services/engineRunPresenter.js).
- Email rendering and sync input: [klaviyoClient.js](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/api/src/services/klaviyoClient.js), [shopifyClient.js](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/api/src/services/shopifyClient.js), [shopifyRepository.js](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/api/src/services/shopifyRepository.js).
- Persistence, identity and execution: [schema.js](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/api/src/schema.js), [campaignService.js](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/api/src/services/campaignService.js), [campaignAudienceService.js](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/api/src/services/campaignAudienceService.js), [routes.js](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/api/src/routes.js).
- Results calculation and demo coverage: [measurementService.js](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/api/src/services/measurementService.js), [seedResultsDemo.js](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/api/src/scripts/seedResultsDemo.js).

Deliverable scope: review/specification only. No app implementation or new test execution is claimed by this document.
