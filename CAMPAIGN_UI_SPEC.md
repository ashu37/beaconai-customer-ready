# Campaign UI specification — C/D pilot handoff

Status: founder-approved September 9, 2026; implementation tracked in Ticket C-UI, not yet complete.

Scope authority: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), Ticket C-UI (the approved C/D design checkpoint). Baseline inspected: Ticket C implementation through `1f0676e`, merged in `8eeaed7`. This document specifies the remaining campaign UI work; it does not reopen accepted backend fixes. Ticket C-UI owns the editor, preview, audience, review and status screens. D supplies handoff, authentication and provider reconciliation. References to C/D below identify capability dependencies, not separate UI implementation tickets.

## 1. What changes from the existing UI

Keep the campaign list, selected campaign workspace, three-step structure, editable copy, existing rewrite/restore behavior, audience details, and save/preview safety work. Use the existing app typography, spacing, and buttons. The merchant's email uses their approved brand design; app chrome retains BeaconAI styling.

| Existing implementation | Approved change | Why |
| --- | --- | --- |
| Copy → Audience → Send | Edit email → Review audience → Review & create draft | Explain the actual work and external outcome. |
| Phone preview defaults to Inbox | Default to the branded Email preview; Inbox remains secondary | The merchant needs to recognize the email they would send. |
| Starting-copy choices plus advanced Klaviyo template options | Starting copy stays a compact secondary control; remove visual-template selection from the merchant flow | Pilot has one approved email design per store. Copy choices do not select a Klaviyo shell. |
| Brand voice shown, but active design is not clearly identified | Separate “Email design: [Store] approved design” from collapsed “Writing style” | Changing words and changing branding are different actions. |
| Destination URL embedded in the starting-copy row | Destination directly below Button label | Keep the button's text and behavior together. |
| Save and preview warnings exist | Place persistent states beside the work they affect, with specific recovery actions | Merchant can resolve problems without interpreting a toast. |
| Final summary describes sending to matched customers and broadly claims suppressions | Review saved email, effective link, planned groups, actual exclusion evidence, and sender checks | Matched, planned, and actually sent are different counts. |
| Create Klaviyo send package, then Send campaign now | Create draft in Klaviyo, then Open draft in Klaviyo | Pilot completes sending in Klaviyo. No BeaconAI direct-send button. |
| Template creation can appear as overall success | Durable creating / draft created / awaiting send / sent / failure / unknown states | A template ID or creation request is not proof of a campaign or send. |

No template picker, drag-and-drop builder, automatic brand extraction, new campaign registry, scheduling UI, batch action, measurement redesign, or engine changes are included. Retain existing holdout controls; this spec does not change allocation policy.

### Copy agent remains part of the product

BeaconAI prepares the words; the approved store design supplies their visual presentation. The current app calls `/copy/generate` when a selected play/template has no loaded agent copy. The route uses recommendation and brand context, uses cached copy where available, and returns generated subject variants, preview text, headline, body, optional support and button text. The selected draft layers merchant edits over agent output, with starting copy as fallback.

C-UI must retain that behavior: show “Preparing suggested copy…” while generating; preserve current merchant edits; retain rewrite controls and their locked fields; never auto-regenerate a frozen handoff. If generation is unavailable, keep usable starting copy and label it “Starting copy” rather than claiming fresh agent output. The merchant reviews and personalizes a prepared email; no blank-page authoring requirement is introduced. The shell supplies logo, colors, layout and footer, not campaign-specific copy. Keep destination review explicit.

Acceptance must exercise the actual generation/rewrite path and saved-draft restoration, not only a static seeded template. No new copy model or prompt-refinement project is included.

## 2. Merchant journey

1. **Open a campaign.** Select it from the existing list. Restore by campaign ID, with its originating run, saved copy, destination, and actual handoff state. Show its persisted name and one-sentence purpose. Never substitute today's recommendation for missing historical content.
2. **Edit email.** Suggested copy is already filled. The merchant edits words and the button destination while seeing their branded email. Auto-save and preview refresh are visible. “Continue to audience” flushes edits; failed saves or conflicts prevent progression. Missing brand setup can still allow audience inspection, but remains a visible blocker to creating a draft.
3. **Review audience.** Explain who matched, the planned email group, and the comparison group. Keep individual addresses collapsed under “View sample recipients”. Show the origin briefing and data state. “Continue to review” waits for any allocation save and current audience response; unresolved or unavailable audiences cannot progress to creation.
4. **Review & create draft.** Show the exact current email alongside a compact audience, destination, and sender summary. Merchant can return to either edit step. The primary button is “Create draft in Klaviyo”; adjacent copy says “Creates a draft. No email is sent.” Clicking is the review confirmation—no additional approval modal or ceremonial checkbox.
5. **Finish in Klaviyo.** After confirmed creation, show “Draft created in Klaviyo”, “Open draft in Klaviyo”, and the final checks: sender/reply-to, recipient eligibility, links, footer, and provider preview. The stored BeaconAI handoff becomes read-only.
6. **Return and check status.** Reopening restores the provider reference and last confirmed state. Only confirmed provider execution yields “Sent”. Until then show “Awaiting send confirmation” with the last check. For this pilot the founder performs reconciliation; a merchant sees when it was last checked and “Your pilot contact can refresh this status.”

An email refresh is not itself merchant approval. Final creation requires the saved campaign revision, reviewed preview version/fingerprint, and origin audience to still match. Changes invalidate review; server checks remain authoritative.

## 3. Desktop wireframes

Layout at 1280–1440px: retain the existing app sidebar and campaign list. Give the workspace the remaining width, with a compact campaign header and a sticky bottom action bar. Within the email step use two columns only when each can remain readable (editor at least 280px, preview at least 320px, 24px gap). Otherwise stack; do not squeeze a phone frame into an unreadable column.

### Edit email

```text
Campaigns [existing list] | Bring back first-time buyers         [Draft]
                         | Customers who haven't returned…
                         | 1 Edit email — 2 Review audience — 3 Review & create draft
                         |
                         | Email design: Acme approved design    [Design details]
                         | Writing style: Acme · concise          [Details]
                         |
                         | EMAIL COPY                  | PREVIEW
                         | Starting copy: Win-back     | [Email] [Inbox]
                         | [Change starting copy]      | [Desktop] [Mobile]
                         |                             | Preview up to date
                         | Subject                     | ┌──────────────────────┐
                         | [Your next favourite…     ] | │ Merchant logo        │
                         | Preview text                | │ Headline             │
                         | [A reason to come back…   ] | │ Body / product image │
                         | Headline / Body             | │ [Merchant button]    │
                         | Support paragraph (optional)| │ Approved footer      │
                         | Button label                | └──────────────────────┘
                         | [Explore the collection   ] | Rendered email preview.
                         | Button destination          | Check in Klaviyo before sending.
                         | [https://acme.example/... ] |
                         | Saved                       |
                         |_____________________________|_________________________
                         |                              [Continue to audience]
```

Annotations:

- Use the shared rendered HTML in the preview; never reconstruct the email using app components. Default to Email. Desktop fits the supported shell width within the pane; Mobile uses a 375px viewport scaled only if needed, with readable expansion. Inbox is an illustrative subject/preview-text view, not evidence that a sender address is configured.
- “Design details” shows store identity, configured version, and approval date if known. Fallback name: “[Store] approved design”; do not invent a shell name. Copy: “This design was configured for your store. Contact your pilot contact for design changes.” No merchant HTML/font/color controls.
- Field labels in order: **Subject**, **Preview text**, **Headline**, **Body**, **Support paragraph (optional)**, **Button label**, **Button destination**. Preserve intentionally empty optional text.
- Destination helper: “Where the email button takes customers.” Show the effective link used by the renderer, including any approved design default; if no link exists, show “Add a destination for this button.” An empty input must not hide a default link the email actually uses. Keep validation consistent with the renderer's allowed HTTP(S) URLs.
- Keep rewrite controls secondary and preserve merchant edits. “Change starting copy” changes words only. If it replaces edits, dialog: “Replace your edited copy?” / “Your copy edits will be replaced. Your email design and button destination will stay the same.” Actions: “Keep editing” and “Replace copy”. Only use that wording if implementation preserves those fields.
- Product images remain render-provided; no image browser. Missing optional image/logo follows the configured shell's omission behavior; do not show broken images.

### Review audience

```text
2 Review audience
First-time buyers who haven't returned
From briefing: [date]                 [Data current / Earlier sync / Blocked]

Matched customers         Planned email group       Comparison group
1,200                     900                       100

200 matched customers have no email address on file. [Example reason]
100 customers are held out of this campaign so we can compare later purchases.
Klaviyo may exclude additional recipients. Actual sent count is confirmed later.

Hold back [10% v]       [existing no-holdout option, with explanation]
[View sample recipients]

[Back to email]                                    [Continue to review]
```

All numbers above are seed examples, not product defaults. The example has 1,000 records available for the split after 200 have no email. Display exclusions only when the API supplies their actual reason/count. Do not relabel all missing emails as unsubscribes, or claim “standard suppressions applied” without verified provider behavior. Zero and unavailable must be different states.

Planned email group means assigned for handoff, not guaranteed delivery. Comparison group means excluded from this campaign, not necessarily every marketing message. If no holdout is selected: “Without a comparison group, Results can show later purchases but cannot estimate this campaign's added revenue.” Preserve any plan-level allocation restrictions; no new policy here.

### Final review and confirmed creation

```text
3 Review & create draft                         [Ready to create draft]

EMAIL [Edit email]                 | CURRENT EMAIL PREVIEW
Subject + preview text             | Branded HTML from the reviewed render
Design: Acme approved design       | [Desktop] [Mobile]
Button: Explore the collection     |
Link: https://acme.example/...      |
                                  |
AUDIENCE [Review audience]         |
Planned email group: 900           |
Comparison group: 100              |
From briefing: [date]              |
                                  |
SENDER                            |
Sender/reply-to: Check in Klaviyo  |
                                  |
[Back]                            [Create draft in Klaviyo]
                                  Creates a draft. No email is sent.

After confirmed creation, replace the primary action area:
Draft created in Klaviyo
Finish reviewing the sender, recipients, links and footer in Klaviyo.
[Open draft in Klaviyo]
Awaiting send confirmation · Last checked [date and time / Not checked yet]
```

The final review must show a current branded email, not only its subject line. Do not treat a preview loaded only in the editor as proof of review after subsequent changes. Flush pending edits, refresh as needed, and present any change before allowing creation. Use a verified provider campaign link; never construct an unverified account URL. If a campaign exists but its deep link is unavailable, show “Draft created. Open Klaviyo and find [campaign name].” Link to the known account entry point only if available; do not recreate the campaign.

## 4. Narrow-screen adaptation

At insufficient workspace width (including 1024/990px with app navigation), stack editor and preview. At phone width, show the existing campaign list first; selecting a campaign opens its workspace with “Back to campaigns”. No new routing framework is required. Preserve draft state when returning.

```text
< Back to campaigns
Bring back first-time buyers
Step 1 of 3 · Edit email
Email design: Acme approved design

Subject …
Preview text …
Headline / Body …
Button label / Button destination …
Saved

Email preview     [Email] [Inbox]
[Full-width mobile email, not a tiny phone illustration]
Preview up to date

[sticky: Continue to audience]
```

Final review stacks summary, then actual preview, then action. A sticky action must not cover fields, validation, footer, or focused controls; allow for device safe areas and keyboard. Use 44px touch targets, wrap long URLs, and avoid horizontal page scrolling. Desktop/mobile preview is a viewport check, not a guarantee of identical rendering in every email client.

## 5. Exact state and action contract

Show messages persistently at the relevant editor/preview/status region. Toasts may supplement them. Creation is enabled only when all required checks pass; explain the first blocking problem beside the button and expose other problems inline. Navigating backward remains available except while a content reservation prevents editing.

| State | Message | Actions and restrictions | Owner |
| --- | --- | --- | --- |
| Saving | “Saving…” | Flush/await on Continue; block creation until settled. | C |
| Saved | “Saved” | Only after response matches current copy and destination. | C |
| Save failed | “Your changes weren't saved.” | “Retry save” persists copy and destination; preserve local input; block creation. | C |
| Revision conflict | “This campaign changed elsewhere. Reload the saved version before continuing.” | “Reload saved version”; warn before discarding local edits, allow Cancel; no blind retry or handoff. | C |
| Preview loading | “Updating preview…” | Old HTML may remain with this label; block creation. | C |
| Preview current | “Preview up to date” | Current draft, campaign, design version, and fingerprint must agree. | C |
| Preview stale | “This preview is out of date.” | “Refresh preview”; block creation until updated and shown. | C |
| Design changed | “Your email design changed. Refresh the preview and review it again.” | “Refresh preview”; use newly approved version only after review. | C |
| Preview failure | “We couldn't update the preview. The email below is an earlier version.” | “Retry preview”; if no prior render, omit second sentence and show an empty preview placeholder. Block creation. | C |
| Missing design | “Your store's email design isn't set up yet. Your pilot contact needs to finish setup.” | “Check setup again”; editing/saving may continue; no BeaconAI-styled fallback or creation. | C |
| Missing/invalid link | “Add a destination for this button.” / “Enter a valid http:// or https:// link.” | Focus link field via “Edit destination”; no creation. | C |
| Audience unavailable | “This audience isn't available for this campaign.” | Show typed reason/remedy if supplied; “Review audience”; never substitute latest-run members. | D |
| Unverified source | “This campaign needs a new verified briefing before it can be used.” | Link to existing sync/briefing workflow; preserve historical record; no creation. | D |
| Earlier verified sync | “This campaign uses an earlier verified briefing from [date].” | Informational under current policy; permit review unless server supplies a blocking reason. | D |
| Klaviyo disconnected | “Connect Klaviyo to create this draft.” | “Connect Klaviyo”; retain saved work through connection flow. | D |
| Ready | “Ready to create draft” | “Create draft in Klaviyo”; no automatic send. | D |
| Creating/reserved | “Creating your draft in Klaviyo…” | Disable duplicate create and content/allocation edits; state survives reload. An old unresolved reservation becomes unknown, not an endless spinner. | D |
| Known creation failure | “The draft wasn't created. Your saved email is unchanged.” | “Retry creation” only when backend confirms safe retry/reuse; “Back to review” only after reservation release. | D |
| Unknown provider outcome | “We couldn't confirm whether Klaviyo created the draft. We'll check before trying again.” | No create retry or content edit. Founder action “Check Klaviyo status”; merchant sees last check and pilot-contact guidance. | D |
| Draft created | “Draft created in Klaviyo” | “Open draft in Klaviyo”; read-only handoff record. Requires confirmed campaign reference, not just template/list ID. | D |
| Awaiting send | “Awaiting send confirmation” | Keep provider link and last-check time; no “Sent” badge based on local approval/job ID. Scheduled status, if confirmed, is “Scheduled in Klaviyo”, still not Sent. | D |
| Status check failed | “Couldn't check Klaviyo. Showing the last confirmed status from [time].” | Retain known state/reference; founder can retry status lookup, never draft creation. | D |
| Sent | “Sent · [provider send time]” | “Open campaign in Klaviyo”; actual sent count or “Sent count unavailable”. Results link only where supported. | D |

Post-handoff caption: “Email handed to Klaviyo on [time]. Changes made later in Klaviyo aren't reflected here.” Label HTML “Handoff email”, not “Final sent email”, unless final provider content has been verified. Legacy records lacking HTML show “The original email wasn't recorded”; never regenerate from today's design. No reopen-for-edit, clone, or re-send feature is added by this spec.

## 6. Data mapping and implementation boundaries

Existing contracts below are verified repository names, not a declaration that every UI state already exists. Proposed D additions need an explicit API contract before its screens consume them; never infer missing provider facts from local state.

| Component | Existing source | Required handling / gap |
| --- | --- | --- |
| Campaign identity/header | `id`, `runId`, `playId`, `displayName`, `revision` from campaign service; `listCampaigns` | Restore by campaign ID. Known historical selection limitations must not result in opening another campaign. Explicit unavailable state is preferable to substitution. |
| Copy/destination | `draftEdits`, `copy`, `destinationUrl`; `buildCampaignFromSelection`; `saveCampaign` | Preserve resolved copy and explicit empty optional fields. Retry whole editable payload; respect `expectedRevision`. |
| Design details | `GET /brand/email-template`: `configured`, `active.version`, `active.brand`, `active.approvedAt` | Shell display name is not supplied; use store-based fallback. Recheck on entering final review and explicit refresh. |
| Rendered preview | `previewCampaignHtml`: `html`, `templateVersion`, `renderFingerprint`; `usePreview` | Same effective destination and copy as handoff. If effective default URL isn't available to UI, expose it from the preview response (C follow-up). Ignore superseded responses; stale responses cannot approve a newer draft. |
| Audience | `previewCampaignAudience`: `audience`, `holdout.treated`, `holdout.held`, `holdout.pct`, `runId`, `inputProvenance` | D must pin preview to the stored campaign's origin and use the same readiness rules as handoff. A boolean preview flag alone must not override authoritative provenance checks. Confirm definitions of `memberCount`, `count`, and exclusion fields before labels. |
| Create draft | `createSendPackage`: `campaignId`, `expectedRevision`, `expectedTemplateVersion`, `expectedRenderFingerprint` | Flush all saves, bind reviewed content, prevent duplicate requests. Handle server conflict/stale errors inline. |
| Handoff record | `approvedCopy`, `renderedHtml`, `templateVersion`, `audienceRef`, `audienceHash`, `frozenAt`, `frozen`, `handoffReservedAt`, `klaviyoCampaignId` | Read-only approved snapshot. A reservation is not successful creation; provider reference must be persisted/recovered. |
| Sender details | Not established by inspected campaign DTO; brand name is not sender identity | D: verified sender name/address and reply-to if available; otherwise “Check in Klaviyo”. Do not fabricate from store domain. Missing here doesn't prevent draft creation if provider allows it; final provider checks remain required. |
| Reconciliation/status | Existing `status` / `sentAt` are insufficient evidence by themselves | D: define durable provider state, last checked timestamp, actual send timestamp, actual sent count (nullable), known-safe retry vs unresolved outcome, verified provider link where available. Use provider evidence to populate them. |

Allocation and consent verification stay in D/F per the implementation plan. This spec changes presentation and explicit state handling, not measurement eligibility or the engine. Authentication and tenant isolation remain server requirements, regardless of UI state.

## 7. Accessibility and recovery

- Every field has a persistent label; validation uses associated text and `aria-invalid`. Errors, saved states, and step progress use words as well as color.
- Use a polite live region for save/preview/status updates; avoid re-announcing unchanged messages on every render. Focus the first invalid field after an attempted progression.
- On step navigation, focus the new step heading. On modal close, restore focus to the invoking control. Dialogs trap focus and support Escape/Cancel. Disabled creation has a visible explanation outside the disabled button.
- Keyboard users can operate preview tabs, edit fields, open details, and reach every primary action. External Klaviyo links announce that they open a new tab.
- Keep local input after request failure. A deliberate reload that discards edits requires confirmation. After refresh/reopen, query durable campaign/provider state before offering creation or edits.

## 8. Seed examples and acceptance

All design screenshots use a conspicuous “Sample campaign — no live recipients” label and synthetic addresses under `example.com`. Sample mode cannot create a provider draft. For actual integration validation, use only the separately authorized test store/recipient workflow.

Prepare screenshots for: ready branded email; empty optional support text; invalid destination; failed save; changed design/stale preview; no configured design; revision conflict; unknown provider outcome; confirmed draft; confirmed sent with unavailable count. Use the 1,200/900/100/200 audience example consistently. Show both desktop and 390px phone layouts, and check the 1024/990px stacked transition.

Acceptance checklist:

- [x] Founder approved this flow, wording, wireframes and deferred scope on September 9, 2026; requested a separate implementation ticket (C-UI).
- [ ] C follow-up: branded Email is the default preview; copy/design controls are unambiguous; destination, save recovery, changed-design and failed-preview states match this spec.
- [ ] C follow-up: edit → save → preview → final review uses the same current content, including empty support and effective destination. A late old response cannot replace or approve a newer render.
- [ ] D: review shows origin audience, planned groups, evidence-based exclusions and honest sender fields; no direct-send action or misleading guaranteed-recipient language remains.
- [ ] D: create → provider draft → reopen retains exact snapshot/reference. Double-click, refresh during creation, provider timeout, safe retry, and unknown-outcome reconciliation do not duplicate drafts.
- [ ] D: only confirmed provider execution becomes Sent; unknown counts remain unknown; later Klaviyo edits do not rewrite the BeaconAI handoff snapshot.
- [ ] Walk through keyboard operation and narrow-screen editing/recovery. Attach implementation screenshots for comparison with the wireframes.
- [ ] Complete one authorized Klaviyo draft/preview or test-email walkthrough, checking sender, destination, footer, mobile view, recipients and holdout exclusions before live pilot handoff.

Delivery: Ticket C-UI implements all screens in this specification, starting with editor/preview and integrating D’s handoff/reconciliation contract when ready. D backend work can proceed in parallel. Keep the Results UI checkpoint separate; this spec adds no Results screens.
