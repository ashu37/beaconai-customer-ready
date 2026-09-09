# BeaconAI — first paid pilot implementation plan

September 9, 2026. Based on SELLABILITY_UX_REVIEW.md and the inspected repository. Assumption: “pr revenue” means pre-revenue. This plan is the delivery priority authority where the broader review asks for more UI than a first pilot needs. It does not change the review's correctness requirements.

## Objective and stopping rule

Get one merchant through a trustworthy, on-brand campaign and a useful results review. Begin customer conversations and show an explicitly labeled demo now; do not wait for all implementation to ask for a paid pilot.

Use founder-assisted onboarding, one approved email shell, one campaign at a time, and manual review appointments. Do not require a statistically significant result to declare the product usable. Do not promise proven ROI before evidence supports it.

Stop expanding the release once the first-send gate below passes. Build later reporting alongside the pilot's observation period. No engine model changes are in scope.

## What to keep, reduce, and defer

| Review item | Pre-revenue decision | Smallest useful version / return trigger |
|---|---|---|
| UX-00A sync integrity | Required before real recommendations | Complete validated input, explicit failure, server-side analysis gate. |
| UX-00B branded email | Required before first send | One founder-configured, merchant-approved shell; no automatic brand extraction or general editor. |
| UX-01 evidence correctness | Required | Correct source/units/claims. Additional evidence visualizations wait for merchant questions. |
| UX-02 persistence | Required | Stable campaign identity, saved edits, fixed origin/audience, historical access. |
| **UX-04 registry** | **Defer the redesign** | Keep a plain chronological campaign list and campaign-ID detail selection. Defer search, filter tabs, date selectors, pagination UI and new routing framework until retrieval becomes difficult. Never silently drop older records. |
| UX-03 Results truth | Required before any merchant sees Results | Correct window, counts, reasons, timestamps and unavailable states; remove misleading aggregate presentation. |
| UX-03P program measurement | Split collection from presentation | Decide and collect valid assignments before affected sends. Implement validated aggregate output during pilot; do not abandon it or fabricate retrospective lift. |
| UX-05 rich Outcomes page | Reduce | Outcome explanation, revenue/customer comparison, raw group table and original email. Defer four-card redesign and daily trend API/chart until review calls demonstrate need. |
| UX-06 follow-up | Reduce | Preserve 30/60/90 aggregates and simple selector. Defer dedicated Follow-up tab, daily incremental-period charts and visible revision timeline. Keep calculation timestamps and stored revisions. |
| UX-07 responsiveness | Fix broken workflow | Prioritize normal laptop widths and readable phone fallback. Defer a bespoke mobile workspace. |
| UX-08 send/access | Required | Reviewed Klaviyo draft handoff, tenant ownership, consent check, actual send reconciliation. Defer direct-send UI and batch execution. |
| UX-09 onboarding/states | Reduce | Assisted setup, meaningful errors and holds, clear sync/run state. Defer self-service wizard and integration polish. |
| UX-10 validation | Required, focused | Failure tests for trust/data boundaries and one end-to-end pilot rehearsal. |

Also defer billing automation, automatic re-sends, subscription LTV/profit, additional channels, variants, arbitrary reporting periods, full report exports, enterprise roles, and both future engine refinements. Manual invoicing and review notes are sufficient initially.

## Delivery sequence

1. **P0: reconcile current state and protect real data.** Diagnose the reported partial-sync incident; verify deployment access boundaries; add isolated fixtures.
2. **P1: make one campaign trustworthy and sendable.** Sync publication, durable campaign state, branded email, clear evidence, and Klaviyo handoff. Fix essential layout along the way.
3. **P2: make measurement valid from the first send.** Settle the program measurement protocol and record required assignments/timestamps. Correct existing Results semantics before exposure to merchants.
4. **Launch the assisted pilot when the first-send gate passes.** P2 data collection must be ready; elaborate reporting need not be.
5. **P3: finish the first review during the observation period.** Minimal campaign Results and validated program summary. Set an internal delivery date before the first promised merchant review.
6. **Expand only against observed friction.** Retrieve/search history when merchants cannot find campaigns; add a trend when totals fail to answer their question; add self-service when assisted setup repeats reliably.

Tickets below are implementation slices. Named new fields/endpoints are proposed contracts, not existing capabilities. Engineers may adapt naming to repository conventions without weakening behavior. Record material alternatives before changing scope.

## Ticket A — verified sync input (P1, blocker)

**Files:** `api/src/services/shopifyClient.js`, `shopifyRepository.js`, `atulEngineService.js`, `api/src/routes.js`, `api/src/schema.js`, `web/src/App.jsx`.

**Problem:** unbounded pagination is now the default, but an explicit limit can truncate successfully. Clean writes have no enclosing publication boundary; analysis reads mutable tables. The reported incident's exact cause remains to be established from logs/data, not inferred solely from these risks.

**Implementation:**

- Add `sync_runs`: ID, shop, status (`running`, `failed`, `incomplete`, `complete`), start/finish times, resource manifest, declared coverage, validation failures, input snapshot reference and schema version.
- Each resource manifest records fetched count, exhausted pagination, explicit cap/truncation, and accessible/requested date coverage where relevant. Unknown coverage is not verified coverage. Determine required input history from current engine/input contracts; do not invent a generic order-count threshold.
- Fetch and validate before publication. For the pilot, retain an immutable normalized engine-input snapshot for each accepted run using the existing JSON/artifact storage pattern. Audit expected pilot payload size before choosing DB JSON versus a referenced artifact. Do not create a new object-storage service solely for this task.
- Publish clean-table updates and the active sync pointer transactionally. Refactor repository writes to accept a shared transaction client. A failed write rolls back publication; incomplete fetches never enter it. Build analysis from the referenced immutable snapshot, not a later read of mutable tables.
- Serialize concurrent sync publication per shop and prevent an older sync from superseding a newer one. Persist failure status outside a rolled-back transaction.
- Link each engine run to `sync_run_id`. Return coverage and readiness from sync/status APIs. Enforce readiness at the engine-run endpoint, not only through a disabled button.
- Preserve the last complete snapshot after failure. For the assisted pilot, a failed/new incomplete sync blocks a new ready analysis until retry; existing analysis remains readable as historical, visibly stale. Block handoff from a recommendation known to use bad input.

**Migration:** existing input/runs are `legacy_unverified`; do not fabricate completeness. Resync before first live use. Preserve historical campaigns, but explain missing provenance. Diagnose yesterday's run and invalidate/reanalyze affected recommendations explicitly.

**Tests:** cap with remaining pages; page failure; write failure mid-import; unknown/insufficient history; concurrent syncs; retry without duplicate records; analysis during sync; old valid input preserved. Known fixture must generate the same normalized input before/after the refactor.

**Done:** no incomplete generation produces a ready briefing, and every new briefing identifies its input snapshot.

## Ticket B — durable campaign revision (P1, blocker)

**Files:** `campaignService.js`, `campaignAudienceService.js`, `schema.js`, `routes.js`, `web/src/App.jsx`.

- Continue using campaign ID as identity and existing `(shop, run, play)` uniqueness for one execution. Do not introduce a general execution hierarchy for this pilot. Repeating requires a new reviewed run/campaign; sent records cannot be repurposed.
- Retrieve campaigns across runs. Resolve audience from the campaign's origin, never the latest run. Persist display name so disappearance from the latest slate does not erase history.
- Add revision number and store approved copy, rendered HTML/template version, audience reference/hash and reviewed metadata. Enforce optimistic revision checks on save/handoff; return a recoverable conflict rather than overwriting a newer revision.
- Show saving/saved/failed. Flush pending edits on navigation or keep navigation pending until saved; external handoff requires a saved revision. Mark stale preview and support retry. Confirm replacement or support undo when changing templates.
- Freeze assignment and approved content at handoff; subsequent edits require a new draft/review flow and cannot silently mutate the record of a sent email.

**Migration:** recover origin and metadata only where present. Missing history is explicit; never backfill from today's audience/copy. Add fields without overwriting existing campaign content.

**Tests:** refresh and new engine run preserve draft; save failure/retry; revision conflict; old campaign missing from latest slate; origin resolution; sent record immutability.

## Ticket C — one approved branded email shell (P1, blocker)

**Files:** `klaviyoClient.js`, `brandContextService.js`, `campaignService.js`, `schema.js`, preview/handoff routes, `web/src/App.jsx`.

**Selected pilot approach:** founder configures a per-shop shell from merchant-approved HTML or a small parameterized template. No theme scraping, automatic brand-book inference, template marketplace, or visual builder.

- Add versioned `brand_email_templates`: shop, version, HTML/supported slot definition, approval metadata. Slots cover approved copy, product image and destination URL. Validate/escape slot values; preserve supported provider merge/unsubscribe syntax. Do not accept arbitrary unreviewed HTML from public endpoints.
- Support logo and merchant colors/layout, email-safe font fallbacks, footer and editable CTA destination. If an existing Klaviyo shell is used, validate its compatibility rather than promising universal import support.
- One renderer supplies preview and provider draft. Save exact output/version on the campaign revision. Missing configuration yields `brand_setup_required`, not silent BeaconAI styling.
- Founder and merchant approve the actual provider draft, including footer, sender, URLs and mobile view. Rendering failures block handoff with actionable error text.

**Tests:** two distinct shops, isolation of configuration, missing logo/template, unsafe slot text/URL, identical preview/handoff HTML revision, historical HTML unchanged after a new brand version. Review representative desktop/mobile email rendering and one provider preview/test-email flow with an authorized test recipient.

**Done:** merchant can send without rebuilding the email in Klaviyo.

## Ticket D — first-send safety and honest execution (P1/P2, blocker)

**Files:** `routes.js`, `klaviyoClient.js`, `campaignService.js`, `holdoutService.js`, `schema.js`, `web/src/App.jsx`.

- Verify existing gateway/session controls. Enforce authenticated shop ownership on campaign, input, sync and Results access, including lookup-by-ID. Do not trust a caller-provided shop string. Use existing authentication if present; if absent, add a minimal authenticated pilot access boundary before real data, not a cosmetic shop picker restriction.
- Pilot UI ends at **Create draft in Klaviyo → Open draft in Klaviyo**. Hide direct-send action. Confirm actual send through provider reconciliation before measurement starts; expose a founder-triggered refresh initially rather than a scheduler.
- Separate delivery state from draft approval and measurement. Store provider reference, reconciliation status, actual provider send timestamp and counts where supplied. Do not use local status-update time as send time.
- Verify the real consent/suppression behavior with the selected provider path. Distinguish planned treatment, holdout, eligible estimate, actual sent, and unknown counts. Keep valid unranked engine audiences usable.
- Ensure repeated handoff clicks/retries reuse the same provider draft or clearly reconcile an uncertain creation outcome. Do not create duplicate campaigns on retry.
- Review overlap manually and maintain the agreed holdout exclusions. No batch sends.

**Tests:** cross-shop requests fail; duplicate/retried handoff; provider failure/unknown status; actual-send reconciliation; null delivery count; no accidental holdout inclusion; unsaved revision blocked. Provider behavior must be verified against the integration used at implementation time.

## Ticket E — evidence and essential layout (P1)

**Files:** `engineRunPresenter.js`, `web/src/App.jsx`, `web/src/styles.css`.

Fix explicit evidence-source mapping, sample/metric units, unsupported revenue claims and selection-as-priority. Translate held reasons without treating every case as insufficient orders. Separate connected/sync/analysis status and correct contradictory empty states.

Repair clipping and unreadable metric text at 1440/1280/1024/990px; ensure the phone fallback has reachable navigation/actions and readable content. Keep the existing visual language. Display current typed evidence in readable sections; defer new custom charts.

**Tests:** presenter fixtures for supported provenance and held reasons; laptop/phone walkthrough, keyboard focus and save/error states. Do not change engine thresholds to improve the appearance of recommendations.

## Ticket F — measurement protocol and collection (P2, before affected sends)

**Files:** `holdoutService.js`, `campaignService.js`, `measurementService.js`, `schema.js`, handoff routes.

**Required design gate:** engineer documents the actual program estimand and assignment protocol; founder approves the merchant-facing scope. Statistical uncertainty/validity should be reviewed by someone competent in experiment analysis. This is the one area this plan intentionally does not turn into an unreviewed implementation formula.

Evaluate stable program-level customer assignment for prospective measurement versus a justified pooled campaign estimator. Existing ever-treated/never-treated grouping is not accepted. Record the chosen population, enrollment date, horizon, treatment opportunities, overlap rules, other-marketing interpretation, uncertainty method and required counts. Inspect realistic variability/holdout size; do not promise significance from audience size alone.

For a prospective program, add versioned program enrollment/assignment records with shop, customer, cohort, arm, enrolled-at and protocol version; immutable and unique within the defined cohort. Enforce program exclusion at each BeaconAI handoff. Record campaign exposure eligibility/opportunity separately. Program controls and campaign controls must have explicit definitions; do not silently reuse the same denominator for different questions.

Freeze campaign recipients before sending. Preserve actual send anchors, identity references, known exclusions and reasons. Do not discard assigned non-deliveries from analysis after observing outcomes.

**Migration:** historical assignments remain historical; label unsupported aggregate comparisons descriptive. No invented randomization, enrollment timestamps or preexisting program cohort. If historical program lift cannot be recovered, start a prospective cohort.

**Gate:** do not send a campaign advertised as part of a measured program until its protocol and collection are implemented. A qualitative concierge pilot can proceed without that promise, but it cannot recover missing program assignment later.

## Ticket G — truthful minimal Results (P2 fixes; P3 presentation)

**Files:** `measurementService.js`, Results routes, `schema.js`, `web/src/App.jsx`.

**Keep:** existing campaign list, basic detail expansion/selection, 30/60/90 selector. Add campaign ID to query state using the current navigation mechanism so refresh can reopen the result; no new router requirement. Fetch history without current-run restriction. If the existing cap is reachable, add a simple Load more rather than a full pagination/search product.

Define each window response: window days/start/end, observed-through/calculated-at timestamps, maturity, quality, typed assessment reasons, arm assigned counts/orders/revenue, revenue/customer and permitted estimate/interval. Add distinct purchasers if displaying purchase rate; otherwise omit that metric initially. Known zero and unavailable/null are different.

All progress, metric and verdict values use the same selected response. Separate measuring, insufficient evidence, no clear difference, supported positive/negative and unavailable. Correct the aggregate zero-order bug and false zero-crossing explanation. Do not label whole audience as sent. Preserve factual early observations without premature verdicts.

Detail must include a short outcome explanation, email-versus-holdout revenue/customer, eligible primary estimate/interval, raw group comparison, originating rationale/email, freshness and next review date. This retains substance without building the full UX-04/05 redesign.

Retain calculation revisions with version/as-of metadata for later corrections; a polished timeline can wait. Existing 60/90 reporting remains accessible with a simple selector. Daily series and four-card analytics layout are deferred.

**Tests:** fixed clock, window boundaries, positive/negative/unclear, unequal groups, no holdout, zero orders, repeated orders/refunds, stale refresh, changed window, old campaign retrieval. Expected values must be independently calculated, not copied from implementation output.

## Ticket H — validated program summary (P3, committed)

Depends on F and G. Implement the approved protocol's response and independent fixtures. Show program population and dates, arm sizes, observed revenue/customer, eligible estimate/interval, freshness and assessment reason. Do not sum overlapping campaign lift or include pre-enrollment revenue as outcome.

Until valid, the hero says why it is measuring/unavailable and shows operational counts; no invented positive total. Show an inconclusive valid estimate honestly. This is a delivery commitment for the pilot review/renewal case, not a promise that lift will resolve. Founder schedules the review based on the agreed horizon and observed data readiness.

**Tests:** duplicates, repeat exposures, late enrollment, unequal follow-up, contamination, zero events, refunds and synthetic known-value cases according to the approved estimator. Document what is estimated and what cannot be inferred.

## Migration, rollout and rollback

Use additive, repeatable schema changes consistent with current initialization tooling; verify both fresh DB and existing seed DB. Avoid destructive reseeding. Keep merchant and demo fixtures separate. There is no current API test script: add a small service/integration test harness using repository-compatible tooling and a disposable database, rather than an engine-wide test project.

Deploy behind shop-level pilot enablement for new sync readiness and handoff paths. Existing unverified data remains readable but cannot bypass the new send gate. Back up affected records before migration. Rollback may disable analysis/handoff and retain read access; it must not re-enable sending from incomplete input or remove historical records. Keep new columns/snapshots on rollback.

Log IDs, statuses, revisions and failure reasons needed to diagnose a run without exposing tokens or recipient data unnecessarily.

## First-send acceptance gate

- Merchant store access is isolated; demo and live data cannot be confused.
- Order dates survive the database without a timezone shift. `clean.orders.created_at` / `processed_at` are `TIMESTAMP WITHOUT TIME ZONE`, so a stored date comes back offset by the server's zone and can move an order across an L7/L28/L56/L90 or week boundary. Found during Ticket A, out of its scope, and a blocker before a merchant sees a live recommendation because it changes the windows recommendations are computed over. Existing values must have their intended zone established — preferably re-derived from `raw.shopify_events` — not reinterpreted on assumption.
- Complete verified sync produces the briefing; induced partial failure cannot do so.
- Merchant recognizes and approves the actual branded email.
- Copy/audience/template survive refresh and new analysis.
- Handoff is idempotent, consent path verified, holdouts respected, send state truthful.
- Measurement protocol and required collection precede any send included in promised program measurement.
- Existing visible Results has no known contradictory labels or unsupported revenue claim.

Once these pass, stop pre-launch feature expansion and onboard the first paying merchant. Founder handles brand setup, onboarding, overlap review, invoice and review scheduling.

## Engineer deliverables and remaining decisions

Deliver small PRs for A–H, each with migration notes, focused tests, screenshots where UI changed and the gate it satisfies. Do not bundle an engine refactor or full App.jsx rewrite into this work.

Before coding dependent portions, record: required input coverage and snapshot storage choice (A), existing authentication boundary (D), approved branded shell/slots (C), and measurement protocol (F). Resolve these from code, deployment and merchant setup first; ask the founder only for actual product choices or missing access. Estimate after this short investigation; no ungrounded calendar commitment is made here.

Reference: [SELLABILITY_UX_REVIEW.md](/Users/atul.jena/Projects/Personal/beaconai-customer-ready/SELLABILITY_UX_REVIEW.md). No application implementation or new test execution is claimed by this plan.
