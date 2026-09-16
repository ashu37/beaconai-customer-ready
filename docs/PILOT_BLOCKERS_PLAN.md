# Pilot blockers: implementation plan

Written 2026-09-11 against `main` @ `d6ce830`. Resolves the four blockers in
[PILOT_READINESS_ASSESSMENT.md](PILOT_READINESS_ASSESSMENT.md). Hardening and
configuration (Gate 2) are out of scope here.

## Code vs. system work

| # | Blocker | Code | System / provider | Long pole |
|---|---|---|---|---|
| 1 | Klaviyo draft creation throws | **Yes** — one-line bug plus test seam | Clean up stuck campaign rows; verify in a real Klaviyo account | none |
| 2 | Shopify gives 60 days, sync needs 90 | Small — scopes, reconnect prompt | **Mostly** — request `read_all_orders` and protected customer data in the Partner Dashboard, update Render env, reinstall | **Shopify approval.** Start day 1. |
| 3 | Klaviyo OAuth lacks PKCE | **Yes** — verifier on the OAuth state, challenge and verifier on the wire | Confirm redirect URI in the Klaviyo app; reconnect after deploy | none |
| 4 | Direct send skips campaign checks | **Yes** — refuse on the server, delete dead UI code | none | none |

## Order

1. **Day 1, first thing:** submit the Shopify access requests (2a). Everything else runs while that waits.
2. Blocker 4 — smallest, removes the riskiest path.
3. Blocker 1 — unblocks every draft test that follows.
4. Blocker 3 — needed before the rehearsal connects a real Klaviyo account.
5. Blocker 2 code, merged once Shopify approves; then reinstall and verify.

One PR per blocker. Each keeps both suites green: `npm test` and `npm run test:api:db`.

---

## Blocker 4 — Disable direct send

**Where:** `POST /api/klaviyo/campaigns/send`, [routes.js:1229](../api/src/routes.js). The UI caller `sendKlaviyoCampaign` ([App.jsx:3042](../web/src/App.jsx)) is defined but never called; `api.sendCampaign` ([api.js:123](../web/src/api.js)) is its only use.

**Change**

- Keep `authorizedShop(...)` as the first line so unauthenticated calls still get 401 and cross-shop calls 403 — `session.integration.test.js` lists this route in both suites.
- After it, return `410` with `{ ok: false, code: "direct_send_disabled", error: "Sending from BeaconAI is turned off. Review and send this campaign in Klaviyo." }`. Remove the `sendCampaign` call and the `saveKlaviyoAsset` write.
- No environment flag to re-enable it. Re-enabling later means building the checks the assessment lists (ownership, approval revision, import completion, send-attempt record), not flipping a switch.
- Delete `sendKlaviyoCampaign` and `sendingCampaignId` state in `App.jsx`, and `sendCampaign` in `web/src/api.js`. Leave `klaviyoClient.sendCampaign` exported for later, unused.

**Tests**

- New: a valid session for the owning shop gets `410`, and a stubbed `klaviyoClient.sendCampaign` that throws if called is never reached.
- Existing 401/403 assertions in `session.integration.test.js` stay unchanged and must pass.

**Done when:** the endpoint refuses a valid session on the deployed app.

---

## Blocker 1 — Fix Klaviyo draft creation

**Where:** [klaviyoClient.js:274–292](../api/src/services/klaviyoClient.js). The outer function receives `options = { html }` from [routes.js:1055](../api/src/routes.js); `createCampaignSendPackageInner` has no `options` parameter and calls `createTemplate(privateKey, campaign)` without HTML, which throws.

**Change**

1. Add `options` to `createCampaignSendPackageInner` and pass `options.html` to `createTemplate`.
2. Check for HTML **before** `progress.stage = "template"`. A missing-HTML failure then reports `provenNothingCreated: true`, so the route releases the reservation and marks the row `failed` instead of `uncertain`. Advance the stage only when a request is about to leave.
3. Add a test seam: `config.klaviyo.apiBaseUrl` from `KLAVIYO_API_BASE_URL`, default `https://a.klaviyo.com/api`, used by `createKlaviyoClient`. Same pattern for the OAuth URLs in blocker 3. Refuse a non-HTTPS override when `NODE_ENV=production`.

**Tests (against a fake HTTP server, not a replaced helper)**

- Start a local `http` server that records requests and answers `/templates`, `/lists`, `/profile-bulk-import-jobs`, `/campaigns`, the messages lookup and template assignment with minimal JSON:API bodies.
- `createCampaignSendPackage` with HTML → `POST /templates` body carries those exact bytes; the result's `html` matches.
- Without HTML → throws, `provenNothingCreated === true`, the fake server saw **zero** requests.
- Route level: `POST /klaviyo/campaigns/from-engine` against the fake server → row reaches `created`, the frozen HTML equals the rendered HTML, one template and one campaign created.
- Failure at the `campaign` step → row is `uncertain` and the reservation is kept (today's behaviour, now tested for real).

**One-off cleanup (system, before the pilot)**

Every handoff so far failed at the template step with no provider request, but was recorded as uncertain. List them:

```sql
SELECT id, shop_domain, delivery_state, handoff_reserved_at, frozen_at, klaviyo_campaign_id, updated_at
  FROM clean.campaigns
 WHERE delivery_state IN ('creating', 'uncertain')
    OR (handoff_reserved_at IS NOT NULL AND frozen_at IS NULL);
```

For each row, search that store's Klaviyo account for a template or campaign with the campaign's name. If nothing exists, run `POST /api/campaigns/:id/reconcile` (founder token). From `uncertain`, "not found" moves the row to `failed` and releases the reservation. A `creating` row needs two calls: the first moves it to `uncertain` (`attempt_abandoned`), the second to `failed`. Don't hand-edit `delivery_state`.

**Found on the real account (2026-09-11):** fixing the HTML wasn't enough. Klaviyo refused the old Create Campaign body with a 400: `channel` isn't a campaign field, `send_strategy.method: "manual"` isn't valid, and `is_add_utm`/`utm_params` were renamed to `add_tracking_params`/`custom_tracking_params`. The approved subject, preview text and sender were never sent at all. `createCampaign` now sends `campaign-messages` with the subject, preview text and the account's default sender, and no send strategy. The fake server enforces those rules, and `npm run smoke:klaviyo` runs the real path against a test account.

**Done when:** one real draft appears in a test Klaviyo account with the approved HTML, the list and recipients are correct, and the query above returns nothing. **Met on the test account 2026-09-11:** status Draft, subject, preview and sender present, template assigned, 3 of 3 profiles imported.

---

## Blocker 3 — Klaviyo OAuth PKCE

**Where:** `createOauthState` / `consumeOauthState` ([oauthService.js:68–89](../api/src/services/oauthService.js)), `buildKlaviyoStartUrl` (~170), `handleKlaviyoCallback` (~188), table `clean.oauth_states` ([schema.js:30](../api/src/schema.js)).

**Change**

1. Schema: `ALTER TABLE clean.oauth_states ADD COLUMN IF NOT EXISTS code_verifier TEXT;`. Add it to `initSchema` like the other additive columns.
2. `createOauthState({ ..., pkce: true })` generates `crypto.randomBytes(32).toString("base64url")` (43 characters), stores it encrypted with `encryptToken` (rows already expire in 15 minutes and are single-use), and returns `{ state, codeChallenge }`, where `codeChallenge = sha256(verifier)` in base64url.
3. `buildKlaviyoStartUrl` adds `code_challenge` and `code_challenge_method=S256`.
4. `consumeOauthState` also returns `code_verifier`, decrypted. `handleKlaviyoCallback` refuses if it's missing and sends `code_verifier` in the token exchange.
5. Refresh (`resolveStoredKlaviyoToken`, ~297) needs no verifier. Leave the logic alone, but point it and the token exchange at the configurable base URL so both can be tested.
6. Shopify stays as it is: its authorization-code flow doesn't use PKCE.

**Tests**

- Start URL: `code_challenge` equals the S256 of the verifier stored for that state; method is `S256`.
- Callback against a fake token endpoint: the form includes the matching `code_verifier`; a state without a verifier is refused; a second use of the state fails.
- Refresh against the fake endpoint: new tokens stored, refresh token rotated when returned.

**System**

- In the Klaviyo developer app, confirm the redirect URI is exactly `https://<render-origin>/api/oauth/klaviyo/callback` and the scopes match `KLAVIYO_SCOPES`.
- After deploy, reconnect every Klaviyo connection made through OAuth. Check `clean.connections` for rows with `klaviyo_refresh_token` set.

**Done when:** a fresh install on a test Klaviyo account succeeds, and a forced refresh (set `klaviyo_expires_at` to the past) returns a working token.

---

## Blocker 2 — Full Shopify order history

### 2a. System work (start first)

1. **Partner Dashboard → the app → API access:** request **read all orders** access with a one-line reason (e.g. "analyses 90–365 days of order history to size the store and pick audiences"). This needs Shopify's approval.
2. **Same page → Protected customer data:** request access, including the **email** field (and name, if the audience or preview uses it). Without it, customer emails come back empty on real stores even with the scope granted.
3. **Distribution:** confirm the pilot store can install the app. Custom distribution is one store and can't be changed later; consider a separate pilot app if this one is meant for the App Store.
4. **Render env:** set `SHOPIFY_SCOPES=read_products,read_customers,read_orders,read_all_orders`.
5. **Reinstall:** existing tokens keep their old scopes. Each store must go through Connect Shopify again to grant the new one.

### 2b. Code

1. `render.yaml:27` — add `read_all_orders`. `config.js:39` default — same, and drop `write_orders`: nothing writes orders, and the deployed value already omits it.
2. **Ask before syncing, not after.** When a sync is requested and the stored `shopify_scope` lacks `read_all_orders`, return a readiness reason `reconnect_for_history` with a "Reconnect Shopify" action, instead of fetching and failing at coverage. Keep the post-fetch coverage check as the backstop.
3. **Fix the ceiling hint.** `validateCoverage` measures the span by `processed_at`, but Shopify's 60-day limit goes by `created_at`. Backdated or migrated orders (like the seeded dev store) can pass coverage without the scope; a real store fails with a less precise message. Compute a second span on `created_at` for `looksLikeScopeCeiling`, and record both in `declared_coverage`.
4. **Optional, same PR:** move `config.shopify.apiVersion` off `2023-10` to a currently supported quarterly version, then rerun `shopifyClient.test.js` and one real sync. Shopify silently serves a newer version for unsupported ones, so today's successes don't prove which API is in use.

**Built (PR feat/full-order-history), with these deviations from the plan above:**
- `render.yaml` is unchanged, and the code default no longer requests `write_orders` or `read_all_orders`. The switch is **`SHOPIFY_SCOPES` on Render**. Asking for the scope before Shopify approves it would break the install, so the code is safe to merge first.
- The reconnect check runs in `POST /sync/shopify` before anything is fetched. It applies only when the app requests the scope and the store's token is known to lack it; an environment token, or one granted before scopes were stored, counts as unknown. Settings shows the same state with a Reconnect link, and a failed sync or first-run shows **Reconnect Shopify** instead of Retry.
- API version bump (item 4) left out; do it with a real sync.

**Tests:** readiness returns `reconnect_for_history` when the scope is missing; the ceiling hint fires on a fixture where `created_at` spans about 60 days and `processed_at` spans more; a scope string with `read_all_orders` skips the hint.

**Done when:** the pilot store reconnects, `clean.connections.shopify_scope` includes `read_all_orders`, a full sync shows at least 90 days measured by **`created_at`**, and orders carry customer emails.

**Dev store note:** its seeded orders were created Jul 15–17, 2026, so without the new scope they drop out of Shopify's window around Sep 13–15 and re-syncs will fail with `no_orders`. Reconnecting with `read_all_orders` brings them back.

---

## Parked (found 2026-09-12, fix after the four blockers)

**Campaigns disagree with the briefing after "Re-run analysis".** The open tab loads campaign rows once ([App.jsx:2251](../web/src/App.jsx)) and keeps them bound to their original run (`runIdByPlay`, [App.jsx:2369](../web/src/App.jsx)); a reload shows only the current run's campaigns in the workspace ([App.jsx:2269](../web/src/App.jsx)) and moves the rest to "Earlier campaigns". Seen on acme: plays added on the Sep 8 run, a re-run on Sep 10, an approval saved at 04:23 UTC to the Sep 8 row; after reload the briefing showed 0 / 0. Nothing was lost; the rows are under Earlier campaigns. Decision pending: **A** re-hydrate on run change, add a notice linking to earlier campaigns and a confirmation before re-running (recommended), or **B** carry unfinished campaigns onto the new briefing (they would still send to the old run's audience). Related wording issue: the briefing's "Approved" badge means "added to Campaigns" (status `draft`), not the Campaigns page's "Approved".

## After all four

Run the Gate 3 rehearsal from the runbook: fresh browser → connect both → sync → analyse → edit and approve → reload → restart Render → create one draft → verify it in Klaviyo → test send. It exercises all four fixes on the deployed app.

## End-to-end test on the deployed app (2026-09-11 → 2026-09-14)

Blockers 1, 3, 4 merged (#44, #45, #46) plus a fix found during the test (#47). Tested on Render with the dev store `acme-0sp6bct4` and the Klaviyo **test** account.

**Verified working in production**
- PKCE: authorize URL carries `code_challenge` + `S256`; exchange succeeds; access + refresh token stored; state consumed. Token refresh after expiry works.
- Klaviyo OAuth scopes: full set granted after adding them to the Klaviyo app (it initially had only `accounts:read`).
- Own Shopify app ("BeaconAI", Dev Dashboard): sync 45 s, 3,628 orders / 35 products / 2,227 customers, all with emails (protected customer data step 1 saved).
- Engine analysis ~2.5 min on Render free; 3 audiences materialised (234 / 555 / 413).
- Branded email shell v2 created via founder endpoint.
- Draft handoff: exactly one Klaviyo campaign `01M2EZKYN19AV9QWTWV67JTD0D`, status Draft, no send time; subject, preview text, sender (beaconai @ runbeacon.ai), template with unsubscribe + CTA + footer; list `WvjsC7` with 212 profiles (treated arm only, 22 held back). DB row frozen, `created`.
- Reconciliation: `awaiting_send`, provider status `Draft`.
- Anonymous reads refused (401).

**Bugs found**
1. *(fixed, #47)* OAuth access tokens were sent as `Klaviyo-API-Key` instead of `Bearer` → every OAuth-connected call got 401.
2. *(open)* `cacheCopyOnCampaign` bumps `revision` but `/copy/generate` doesn't return it, so the first approval on every fresh campaign is refused as a conflict ("This campaign changed elsewhere"). Reload is the workaround. Feedback is a 5-second toast while the UI keeps showing "Ready to send".
3. *(open, UX)* A reloaded approved campaign opens on step 3 with "Audience not loaded yet" / no preview; the merchant must go back to step 1 before creating the draft.
4. *(open)* Narration: 10 sequential Sonnet calls after the engine run, request held open for the whole time, no subprocess deadline, no run serialisation. A briefing loaded between snapshot and narration shows no play thesis. One run (b2bfc6b0) never got narration while overlapping runs were active.
5. *(hardening)* `/api/health` exposes DB host/user; expired `oauth_states` rows are never deleted.

**Cleanup in the Klaviyo test account (after review — do not send)**
- Campaign `01M2EZKYN19AV9QWTWV67JTD0D` "BeaconAI - Bring back lapsed customers"
- List `WvjsC7` and its 212 `beacon-seed.test` profiles
- Template `SPQrfK` (and the message's cloned template)
- From the earlier smoke test, if not yet deleted: list `X8F8Kr`, template `RKpudY`

## Fixes for the end-to-end findings (2026-09-14)

| PR | Fixes |
|---|---|
| #48 | Copy caching no longer bumps the campaign revision (first approval conflict); approval shown only after the server accepts it; the final step renders the email and loads the audience after a reload |
| #49 | Analyses run as background jobs (202 + polling), one per store (DB-enforced), engine 10 min / narration 5 min deadlines, `narration_status` with a "writing the explanation" placeholder, no engine output in responses |
| #50 | Public `/health` and `/ready` no longer expose the database target or errors (founder token still sees them); `/ready` does a live DB check; expired OAuth states are swept |

Combined locally on `main`: API 220 passed, web 93 passed, build passes. #48 and #49 both change the `campaignSaveGate` import in `App.jsx`; whichever merges second needs that one line resolved (keep both imports).

Still parked: "campaigns after Re-run analysis" (A/B decision).

## Post-merge retest of #48–#50 (2026-09-14)

| Check | Result |
|---|---|
| #50 health redaction / live ready | Pass: no DB target publicly; `/api/ready` → `database.live: true` |
| Double analysis | Pass: one job; button disabled while running; direct second POST → 409 `analysis_in_progress` |
| Background job | Pass: job 1 run at +171 s, complete at +256 s; job 3 complete in 210 s |
| Narration placeholder | Pass: tab loaded mid-narration showed "Writing the explanation…" and updated without reload |
| Approve → draft, no reload | Pass: campaign 41 revision 2 after copy cache, approved, draft `01M2F4V0KV3Q96DY2Q94NRQFYW` (list `Ty7tZ2`, 212 profiles) |
| Reload → create from final step | Pass (handoff): campaign 45 draft `01M2FFV2TJRAXCG85NZZYNAJ8P`; audience and sender not shown on the restored step |

**New bugs → PR #51 (open):** one failed poll (HTML proxy page) ended the analysis wait; concurrent Klaviyo token refreshes; restored final step didn't load audience / retry sender.

**Parked bug is worse than thought:** on any reload after a new analysis, the cached previous briefing binds campaign hydration to the old run, so a play shows "Approved" for another run's campaign until storage is cleared.

**Narration quality:** winback card fell back (guard L2 "incremental") — consider one retry for guard-rejected cards.

**Klaviyo cleanup additions:** campaigns `01M2F4V0KV3Q96DY2Q94NRQFYW` (list `Ty7tZ2`) and `01M2FFV2TJRAXCG85NZZYNAJ8P` (its list — check in Klaviyo), plus their templates.

## Campaign continuity step 1 verified on Render (2026-09-14, PR #52, bundle index-DmB5dIeV.js)

| Check | Result |
|---|---|
| Control: campaign on the current run shows Approved | Pass (winback, campaign 45 on b2bee0e1) |
| Same-tab re-run with the editor open | Pass: new run c8f9c798 applied without leaving Campaigns; editor stayed on campaign 49 (run b2bee0e1); edits before and after the run change both saved to campaign 49 (rev 3 → 4); no campaign created on the new run |
| Stale badge after same-tab re-run | Pass for winback (not open). Discount still shows "Approved" in that tab because its draft was the open editor — intended step-1 behaviour; step 3 replaces the badge with "You already have a draft for this play → Continue draft" |
| Reload with an older cached briefing (cache c8f9c798, server e75d2a85) | Pass: server run replaced the cache; campaigns read twice (once per run); no Approved badges; Needs review / In pipeline 0 |
| Earlier work reachable | Pass: "Earlier campaigns (7)" lists campaign 49 and the winback campaigns |

No Klaviyo objects were created by this verification. Cosmetic: the two oldest campaign rows show play ids instead of names (created before display names were stored).

## Campaign continuity step 2 verified on Render (2026-09-14, PR #53, bundle index-D9aqvG4Y.js)

Current run e75d2a85; seven campaigns from earlier runs (winback 45/41/36/33/21, discount 49/1).

| Check | Result |
|---|---|
| Briefing badges with only older campaigns | Pass: no "Approved" on any card, although older winback and discount campaigns exist (several approved) |
| Approve winback (double click) | Pass: exactly one campaign created (53, run e75d2a85); follow-up template save quoted rev 1; copy request sent `runId` e75d2a85; winback card shows Approved |
| Two campaigns for one play side by side | Pass: reopened older winback 36 (run 999ee987) joins the rail as "Earlier analysis" under Ready to send, approval kept; 53 stays in Needs review; 36's preview and audience requests carried run 999ee987 and campaign id 36 |
| Edit waiting to save, then switch campaigns | Pass: typed into older draft 49 and switched to 53 within 150 ms; the save went to discount / run b2bee0e1 / rev 4; 53's editor kept its own subject |
| Edit current campaign | Pass: saved to winback / run e75d2a85 / rev 2; server shows 53 and 49 each with only their own edit; 36 and 45 unchanged; 8 campaigns total |
| Reload | Pass: only winback shows Approved; rail lists 53 with its saved edit; earlier campaigns still listed; tiles Needs review 1 / In pipeline 0 |
| "In campaigns" link from the briefing | Pass: switches from older draft 49 to this run's campaign 53 |

No Klaviyo objects were created (stopped before "Create draft in Klaviyo"; the handoff path is covered by web tests). Test data left in place: campaign 53 (draft, subject "Step 2 check: campaign 53 edit") and a new subject on draft 49. The briefing has no remove control for an approved play, so 53 was not dismissed.

Cosmetic: an older campaign without a stored audience size shows "— customers" in the rail (49). Not a bug: metric tiles read 0 in a background tab because their count-up animation only runs when the tab is visible.

## Campaign continuity step 3 verified on Render (2026-09-14, PR #54, bundle index-Ds7bJ8F3.js)

Current run e75d2a85. Before: winback 53 on the current run; unfinished earlier drafts 49 (discount), 33, 21 (winback), 1 (discount, approved); handed-off winback 45, 41 (created), 36 (awaiting_send).

| Check | Result |
|---|---|
| Migration | Pass: every campaign row carries `supersededById`, `supersedesId` and `runAnalysedAt` |
| Card: play with a current-run campaign (winback) | Pass: Approved badge and "In campaigns" |
| Card: play with only an earlier draft (discount) | Pass: "You already have a draft for this play from your Sep 13 analysis" with Continue draft and Review latest recommendation; no Approved badge |
| Card: play with no campaign (first-time buyers) | Pass: Approve & pick template |
| Campaigns rail | Pass: 53 plus unfinished earlier drafts 49, 33, 21, 1; handed-off 45/41/36 under Earlier campaigns |
| Continue draft | Pass: opens campaign 49 with its saved subject |
| Review latest, then Create updated draft (double click) | Pass: exactly one replacement (57, run e75d2a85, draft, not approved, template/subject copied, supersedes 49); 49 now superseded_by 57 (rev 5 → 6); opened on Edit email in Needs review; 49 listed as "replaced by an updated draft" |
| Handoff of replaced draft 49 | Pass: 409 `superseded`, replacementId 57; 49 not reserved, frozen or sent to Klaviyo, revision unchanged |
| Reload | Pass: discount now shows Approved / In campaigns (its own campaign 57); opening 49 shows "This draft was replaced by an updated draft" and the link opens 57 |

No Klaviyo objects created. Scheduled and sent cards were checked on a local fixture before merge (PR #54 comment); the acme store has no scheduled or sent campaign for a play without a current-run campaign. The page-side request log counted each POST twice because two fetch wrappers were installed during the check; the server shows one replacement.

Test data left: replacement campaign 57 (discount, draft) and superseded draft 49. Cosmetic, unchanged: older rows without a stored audience size show "— customers", and the two oldest rows show play ids as names.

## Walkthrough PR 1 (claims) verified on Render (2026-09-15, PR #56, bundle index-RQ6WFgw-.js)

Latest acme run fa76499d.

| Check | Result |
|---|---|
| Winback narration | Pass: thesis ("21 or more days") and send ("sequence", "percent-off", 21 days) dropped; evidence summary kept; the thesis tab shows evidence chips |
| Discount narration | Pass: evidence summary ("5.3%" as a rate, "60,528 orders") dropped; thesis and send kept |
| First-to-second narration | Pass: send ("sequence") and evidence ("0.5%" as a rate) dropped; thesis kept |
| "What we'd send" tab | Pass: "One email draft for the N customers in this audience. No discount or follow-up emails are added." |
| Starting copy | Pass: headlines are customer subjects ("Come take another look", "A closer look at the range", "Thanks for your first order"), not play names |
| Stored campaign copy served by GET /campaigns | Rules applied (body slots with claims blanked; featured product ids kept) |

**Gap found:** real stored copy on 10 campaigns still carries unsupported claims the pattern list does not cover:
- possessive product claims: "Your Hyaluronic Daily Moisturizer is back"
- popularity: "The one people keep coming back to", "The one people reorder most", "The one people add second"
- performance and outcome: "your skin holds water through a full day…", "It holds up without the wait."
- usage and preference: "every single day you use it", "You already know what works."
- sales: "Why this serum sells at full price"

Needs a follow-up before the rehearsal.

## Walkthrough PR 2 (store state) verified on Render (2026-09-15, PR #57, bundle index-BnnbGl_K.js)

| Check | Result |
|---|---|
| Store totals | Pass: 35 / 2,227 / 3,628 render at once, including in a background tab (no count-up from 0) |
| Same store → Use store | Pass: zero requests; Campaigns still lists 5; no "Approve a play…" empty state |
| Results on open | Pass: "Loading results…" first, then the results page; no false first-use message |
| Sync from Settings | Pass: failure shown on Settings with the reconnect message, "still use your last successful sync, from Sep 11, 2026, 3:32 PM", and Reconnect Shopify |
| Switch to another store | Pass: acme's briefing and campaigns disappear immediately; URL `?shop=` updated; the other store's own signed-in-elsewhere state |
| Switch back to acme | Pass: acme's briefing, totals and 5 campaigns return |

Not exercised live: starting an analysis before switching stores, and a failed save blocking a switch. Both are covered by app-level tests. Small remaining false zero: "Needs review 0 / In pipeline 0" shows for a moment while a store's campaigns load. Fold into PR 3.

## Walkthrough PR 3 (campaign editing) verified on Render (2026-09-15, PR #58, bundle index-Cd8w_G8u.js)

| Check | Result |
|---|---|
| Handed-off campaign opened from Earlier campaigns | Pass: toast and notice "handed off to Klaviyo, so its content is locked here"; no "already sent"; subject field disabled; no Change starting copy, Rewrite, Restore suggested or Back to review |
| Holdout dropdown | Pass: None (send to everyone) / 5% / 10% / 15%; "Send to everyone" leaves None selected |
| Audience headline | Pass: "507 of 555 customers are assigned to the email group. Klaviyo confirms actual delivery." |
| Holdout change in progress | Pass: within 2 ms "Updating the audience…", select disabled, Continue shows "Updating…" and is disabled for about 2.3 s, then re-enabled |
| Sequential saves on test draft 57 | Pass: 0.05 → 0 → 0.1 → 0.15 → 0.1 saved in order at revisions 2→3→4→5→6→7; no conflicts. Holdout restored to 10% |

Not exercised live: cross-session conflict recovery, and failed saves hidden by later saves. Both are covered by app-level tests.

## Walkthrough PR 4 (wording, counts, vocabulary) verified on Render (2026-09-15, PR #59, bundle index-DMUT5mAo.js)

Browser session for acme had expired; signing in again needs a Shopify OAuth grant (scopes now include read_all_orders), so UI checks were limited to the live bundle and server responses read with the founder token.

| Check | Result |
|---|---|
| Live bundle labels | Pass: Add to Campaigns, In Campaigns, Review draft, Ready for Klaviyo, Drafts to review, Matched customers, Refresh list, handed off to Klaviyo, preview link wording, Klaviyo find-the-draft and status wording present; "Approve & pick template", "In pipeline", "approved · locked" gone |
| Audience definitions (run fa76499d…) | Pass: "30–90 days before the latest order date in the analysed data"; "21–45 days ago … (counted back from the latest order date in the analysed data)"; no "anchor" or "this analysis" in any shown definition |
| Watching thresholds | Pass: "A change of 1 percentage point either way could bring a retention recommendation." and similar; no "pp to fire" |
| Internal vocabulary in narration | Pass: "prior-anchored", "considered play", "No revenue figure to state" dropped (recorded as internal_vocabulary); remaining occurrences only in raw engine data and violation records |
| GET /campaigns displayName | Pass: all 11 campaigns carry play names |
| Results handedOffAt | Pass: campaigns 58, 45, 41, 36 carry handed-off timestamps |

**Gap found:** the AOV bundle held play still shows engine shorthand: "customers with cart/typical AOV in [$28.00, $38.00] ($43.00 threshold minus $5-$15 band, snapshot)".

UI checked afterwards in the founder's Chrome session (acme):

| Check | Result |
|---|---|
| Tiles and badge | Pass: Drafts to review 4, Ready for Klaviyo 1, Campaigns badge 5 = the 5 rail rows; unchanged after opening a handed-off earlier campaign |
| Briefing | Pass: "Your briefing is ready — 3 recommendations"; "In Campaigns" pill; no play ids in the default view |
| Earlier campaigns | Pass: "Sep 14 analysis · handed off to Klaviyo", "Sep 13 analysis · replaced by an updated draft · draft"; rail "Earlier analysis, Sep 14" |
| Handed-off campaign 58 | Pass: opens on the final step with "In Klaviyo, open Campaigns and find the draft named “BeaconAI - Turn first-time buyers into repeat buyers”" and "Status updates when your pilot contact checks Klaviyo."; no edit controls |
| Audience step | Pass: "Matched customers", "Refresh list", scope note, "Review draft" button, assignment headline "212 of 234 customers…" |
| Results | Pass: "Handed off Sep 14, 2026. Results start once the send is confirmed in Klaviyo." |
| Mobile width | Pass: rail readable, no horizontal overflow |

**Reconnect with read_all_orders on the unapproved app:** fails. Shopify returns "Oauth error missing_shopify_permission: read_all_orders" before any grant screen, so acme cannot reconnect while SHOPIFY_SCOPES includes it; the dashboard shows Shopify "Not connected".

## "Finish design in Klaviyo" — Klaviyo path check (2026-09-15, beaconai test account RGLJ89, API revision 2026-04-15)

| Check | Result |
|---|---|
| 1. Draft with no template | Pass: POST /campaigns with audience list, subject, preview text and sender, and no template assignment, returns status Draft; the message has no template (GET /campaign-messages/{id}/template → null) |
| Draft findable by name | Pass: listed in Klaviyo → Campaigns under its exact name "BeaconAI check - finish in Klaviyo (delete)" |
| 2. Merchant picks a saved template in Klaviyo | Pass: Campaigns → draft → Next → Message step shows our subject, preview text and sender beside Klaviyo's template picker (Email: saved / Email library) → Use template → editor → Save. Afterwards the campaign id, message id, name, audience list, subject and preview text are unchanged; the message carries a non-reusable copy "2026-09-15 14:38 Winback"; the saved templates are untouched |
| 3. Link to the draft | Pass: https://www.klaviyo.com/campaign/{campaign id}/wizard/1 opens the draft directly; a wrong id shows Klaviyo "Not Found". Not a documented URL, and it only opens in a browser signed in to that Klaviyo account (multi-account behaviour untested), so the exact name and directions stay alongside it |
| API template assignment (fallback) | Not needed; already proven by the existing rendered-email handoff (POST /campaign-message-assign-template, which clones the template) |

Tested with a CODE template only; drag-and-drop saved templates use the same message-template assignment but were not exercised.
Test objects left for manual deletion: campaign 01M2K5RDG9NZGQ21Q1D9PP4HYG and list RgF72f ("BeaconAI check - finish in Klaviyo (delete) - Audience").

## "Finish design in Klaviyo" verified on Render (2026-09-15, PR #60, bundle index-CH_xMevy.js)

acme has a BeaconAI design (v2); its Klaviyo connection is the beaconai test account. One live draft created from campaign 86 (agreed).

| Check | Result |
|---|---|
| Unknown mode | Pass: 400 `invalid_handoff_mode` |
| Schema | Pass: every campaign carries `handoffMode` (null before handoff) |
| Store with a design | Pass: "Use the acme design" selected by default, preview up to date; "Finish design in Klaviyo" offered |
| Switch to finish in Klaviyo | Pass: design chip "finish in Klaviyo", Suggested messaging with Copy buttons replaces the preview, no preview requests |
| Audience and final step | Pass: 212 of 234 assigned (22 held back); "Suggested messaging", "Design: you choose a template in Klaviyo", Finish in Klaviyo checklist, caption "Creates a Klaviyo draft… No email is sent." |
| Create draft | Pass: request `handoffMode: klaviyo_design`, no fingerprint, revision 2; 200; record frozen, created, revision 6; no save afterwards, no conflict; Handoff suggestion shown immediately; toast "Choose a template and finish the email there." |
| After handoff | Pass: "Open draft in Klaviyo" → https://www.klaviyo.com/campaign/01M2KCW8QF9GB51TV70N0K4BCV/wizard/1, name "BeaconAI - Bring back lapsed customers", next steps, pilot-contact status line |
| In Klaviyo | Pass: link opens the draft; audience list "… Audience (212)"; Message step has our subject, preview text and sender with the template picker (no template) |
| Reload | Pass: Handoff suggestion, "Design: you choose a template in Klaviyo", no create button, no preview requests |
| Server record | Pass: `handoff_mode` klaviyo_design, no rendered HTML or template version, audience 234 / holdout 22 / 10%, provider id and URL stored |

Not exercised live: Results → Original campaign for this draft (pending rows don't expand; the endpoint returns handoffMode klaviyo_design), uncertain outcome and reconciliation (covered by integration tests).
Found: stored subject variants and support copy on draft 86 still carry unsupported claims ("The one people reorder most", "Your Hyaluronic Daily Moisturizer is back", "It layers well under sunscreen…") — the open claims gap, now in copyable suggestions.
Test object to delete later: Klaviyo campaign 01M2KCW8QF9GB51TV70N0K4BCV and its list "BeaconAI - Bring back lapsed customers - Audience"; BeaconAI campaign 86.

## Pilot walkthrough prep (2026-09-15)

- acme reconnected with read_all_orders (approved by Shopify); full sync: 3,645 orders over 240 days in 41 s; new analysis run 0b298773.
- Walkthrough artifact: https://claude.ai/code/artifact/0f5ff632-affe-4086-b5cf-9b4d525fc2d6 (screens from acme on Render; Results from the local seed demo, labelled example data).
- Second live finish-in-Klaviyo draft created for the walkthrough: campaign "BeaconAI - Reduce discount dependency" (Klaviyo 01M2KEHY7VYKCH8HZKN554NERK), from an updated draft of 57 with copy rewritten to neutral wording.
- Found: connection status flashes "Not connected" with Connect chips while it loads; generated subject variants still show unsupported claims (claims gap).
