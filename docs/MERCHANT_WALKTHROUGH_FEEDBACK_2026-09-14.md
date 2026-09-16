# Merchant walkthrough feedback — September 14, 2026

Tested the deployed BeaconAI app at https://beaconai-app-kvre.onrender.com/ with `acme-0sp6bct4.myshopify.com`, starting in a fresh browser. The user completed Shopify login. This is feedback from interacting with the product, not a code review or an architecture proposal.

## Overall impression

The core journey exists and is usable: understand a recommendation, add it to Campaigns, edit an email, inspect the audience, and create a Klaviyo draft. The biggest weakness is confidence in the current state: what has been approved, what has actually been sent, what data is current, and whether a change has finished saving. Several messages contradict nearby controls or other screens.

I would want help from the founder before using this unsupervised. The fixes I would prioritize are small behavioral and communication corrections, not a redesign of the application.

## Most important functional faults

### 1. Reselecting my current store makes my work appear to disappear

**Reproduction:** Settings → leave the existing store unchanged → Use store → Campaigns/Briefing.

The campaign badge disappeared; Campaigns said “Approve a play in Briefing to start your first campaign.” Briefing showed zero products, customers, orders and recommendations. Before this action there were six visible campaigns, 35 products, 2,227 customers, and 3,628 orders. The page still showed a successful September 11 sync. A reload restored the saved campaigns.

**Merchant reaction:** “Did I just erase my work?”

**Expected:** Selecting the same store should preserve the workspace. If a refresh is needed, show loading while retaining the last known data. Do not show a first-use empty state for an existing store during recovery.

### 2. The optional support paragraph cannot be removed

**Reproduction:** Open the new first-to-second-purchase draft → clear Support paragraph (optional).

The suggested paragraph immediately returns. It also remains in the email preview and survives navigation. Other fields accept changes normally.

**Merchant reaction:** “Why does this copy keep coming back? Is it really optional?”

**Expected:** An intentionally empty optional paragraph stays empty and disappears from the email.

### 3. Rapid holdout changes produce a misleading conflict

**Reproduction:** Change 10% to 5%; choose Send to everyone; choose Hold back 10%; select 15%; continue to the next step before the previous updates settle.

The app displayed “This campaign changed elsewhere. Reload before editing further.” I was using a single review tab. I cannot rule out another operator's concurrent activity, but the conflict appeared during this sequence of local changes. Waiting for each change to settle allowed the choices to work.

**Expected:** Show that the audience is being updated and prevent incompatible next actions until it is ready. A merchant should not have to infer a safe waiting period. If a conflict does occur, offer a recovery action, not just a message and Dismiss.

### 4. Zero holdout contradicts the dropdown

**Reproduction:** Select 5%, then Send to everyone.

The summary correctly changed to 413 planned recipients and zero comparison customers, but the Hold back dropdown still showed 5% selected. It had no 0% option. The explanatory text correctly said the campaign's added revenue could not be estimated without a comparison group.

**Expected:** All controls agree with the active choice. “No holdout” should be visible as the selected state.

### 5. “Already sent” is used for a draft awaiting confirmation

**Reproduction:** Expand Earlier campaigns → open a locked Bring back lapsed customers campaign.

A toast said “This campaign was already sent — its content is read-only.” The same campaign's delivery panel said “Awaiting send confirmation” and “Draft created.” Results likewise did not have a confirmed send. This is more than a wording preference: whether customers have received an email is a crucial fact.

The campaign also offered Edit email and Back to review, and the edit screen exposed normal textboxes, starting-copy choices and rewrite controls despite the read-only message. I did not overwrite this existing locked campaign.

**Expected:** Say “Handed off to Klaviyo; content is locked here” when that is what is known. Make the edit experience visibly read-only or clearly explain what an edit would affect.

### 6. Store freshness and recovery messaging disagree

Settings and the sync failure banner say Shopify only permits 60 days of orders and requires reconnecting. The saved briefing says it has 240 days of orders from September 11. These can both be true, but the product does not explain the distinction between saved history and current connection permissions.

After Re-sync store from Results, the blocked-sync explanation appeared in Briefing. Store summary totals briefly became zero despite the saved recommendations remaining visible. Re-run analysis then displayed “Refreshing with your latest orders…” even though the most recent successful sync was still September 11. Its tooltip correctly says analysis does not pull new Shopify data.

The final check confirmed that analysis completed: its timestamp advanced to September 14, 9:57 PM, while the successful sync remained September 11 and the reconnect warning remained visible. This was successful re-analysis of saved data, not a successful fresh Shopify sync.

**Expected:** Preserve existing values; identify them as last successfully synced. Say “Analysing saved data from Sep 11” when using that snapshot. Put the actionable sync failure where the user initiated the action, including Results.

## Recommendation and evidence feedback

### 7. Evidence prose confuses a rate with a change in rate

For Turn first-time buyers into repeat buyers, the prose said the conversion rate “sits at roughly 0.5%.” The evidence card said “Up 0.5 percentage points,” compared with the preceding period. A current rate and a change are different quantities; the screen provides no explanation reconciling them.

**Expected:** Use the actual current and previous rates, or consistently describe the change. Avoid presenting a delta as an absolute rate.

### 8. Generated email personalization is more specific than the audience

The first-to-second audience is broadly “first-time buyers whose only order is 30–90 days before anchor.” Generated copy told recipients “You picked up the Hyaluronic Daily Moisturizer,” then recommended Niacinamide Pore Serum.

I found no audience restriction to buyers of that moisturizer in the visible review. This does not prove every recipient would receive an incorrect claim, but the merchant has no evidence that the claim is safe for all 413 people.

**Expected:** Either demonstrate the purchased-product condition in the audience or avoid asserting a specific purchase for everyone. This is something I would stop and verify before sending.

### 9. Brand context feels inconsistent and cannot be corrected here

Writing style is “acme · outdoor sports.” Details list Niacinamide Pore Serum, snowboard, beauty, serum, sport and winter. Generated copy combines mountain/snowboard language and skincare, including product-performance statements such as “No pilling, no wait time.”

This may reflect the development store's mixed catalog rather than a problem with a real single-category merchant. Nevertheless, the visible experience gives me no way to tell BeaconAI which category or claims are appropriate. Refresh is available, but correcting the context is not.

**Expected:** Explain the basis of the style and provide a clear route to correct it. Do not make claims about customer purchases, restocking, product performance or preferences without evidence the merchant can inspect.

### 10. The winback strategy and email do not clearly match

Bring back lapsed customers describes at least 28 days of inactivity. What we'd send describes dormancy of at least 21 days, an email sequence, and a percent-off offer. Evidence adds a 21–45-day condition and at least two prior orders. The actual campaign editor contains a single email and no visible sequence or discount setup.

**Expected:** Describe the exact audience and the single draft the product will actually create. If an offer or sequence is only a suggestion, label it that way.

At the final check after re-analysis, the winback thesis used 21 days rather than the earlier 28 days. The discrepancy above describes the earlier observed version; I did not recheck every recommendation tab after regeneration.

### 11. Approval language means several things

“Approve & pick template” adds the recommendation but leaves me on Briefing; I then need In campaigns or the toast's Review action. Later, Continue to send changes the campaign to Ready to send before I have inspected the final review screen. Yet the final action creates a draft rather than sending.

**Expected:** Name the first action “Add to Campaigns,” or actually take me to the editor. Name the second action “Review draft.” Reserve “approved” and “ready” for an explicit review decision with a clear scope.

### 12. Counts need clearer scopes

Initially the briefing headline said three plays for review, the summary said Needs review 4, and the Campaigns badge said 5. After I added the third recommendation, Needs review became 5 and the badge became 6 while the headline still said three plays for review.

These likely describe recommendations versus campaign drafts, but the screen does not make that distinction obvious. Opening an earlier locked campaign also moved it into the main list and increased the badge from 6 to 7, despite no new campaign being created by that action.

**Expected:** Make the badge's meaning stable and label counts by what they count.

### 13. Held recommendations often stop at an unexplained reason

I opened all six listed held recommendations. Subscription says a data-quality issue blocks it but does not identify the issue or what the merchant should do. Other plays say there is no signal without showing the relevant metric or threshold. “8 more held plays aren't listed” has no visible expansion action.

**Expected:** For each held play, say whether I should fix something or simply wait. Either let me inspect the additional eight or avoid teasing inaccessible information.

### 14. Internal vocabulary leaks into merchant explanations

Examples include `winback_dormant_cohort`, `discount_dependency_hygiene`, `cohort_journey_first_to_second`, “before anchor,” “posterior estimate,” “considered play,” and “No revenue figure to state.” Watching uses phrases such as “+/- 1pp to fire a retention play.”

**Expected:** Use dates, ordinary campaign names, and plain explanations of the condition that would change a recommendation. “No revenue figure to state” reads like an instruction to a writer, not finished product copy.

### 15. Baseline revenue is easy to overinterpret

The app helpfully says this is not revenue caused by the campaign. But the largest numbers in a recommendation are still baseline revenue figures; the winback shows roughly $4,500 typical with a $400–$4,500 range. A merchant is likely to treat the largest number as the opportunity they can earn.

**Expected:** Keep the caveat close to the number and explain the time period. Use the evidence change and audience fit as the primary reason to act, rather than making the baseline look like a forecast of campaign lift.

## Editing, preview and audience details

### 16. Starting-copy changes do not reliably communicate what changed

I selected Gentle nudge, Winback, and Second purchase. At points the Starting copy label changed while the already-generated copy remained the same. Freshly opened copy also initially showed Edited labels before I had edited those fields.

**Expected:** Tell me whether changing starting copy replaces the email, only changes the next rewrite, or retains my existing text. “Edited” should identify actual merchant changes.

### 17. Rewrite needs a clearer contract

Shorter, Warmer and More direct look like actions, alongside a separate Rewrite button. There was not an obvious persistent selection indicator explaining whether the style click applied a rewrite or configured the next one. Rewrite itself showed Writing… and eventually produced different copy.

**Expected:** Make the selected style visible and explain whether edited fields are preserved. Afterward, indicate what changed and offer a straightforward way to return to the prior copy.

### 18. Preview sometimes temporarily shows another campaign's email

When switching between campaigns, the new campaign title and subject appeared while the iframe still showed the previous campaign's body. It was marked Updating preview and later corrected itself, so I did not observe a false up-to-date claim for that intermediate state.

**Expected:** Keep the loading indicator, but blank or visibly cover content belonging to another campaign. Seeing another campaign's email is alarming during review.

### 19. URL recovery works, but the error is too technical

Entering `not-a-url` produced the useful field message “Enter a valid http:// or https:// link.” The preview additionally said `The "cta_url" value was rejected: it is not a valid absolute URL`. Edit destination correctly returned focus to the field; correcting the URL recovered the preview.

**Expected:** Use the field-level explanation in both places. Avoid exposing `cta_url`. Clearly identify any still-displayed preview as the last valid preview.

### 20. Recipient preview is neither a toggle nor a complete audience inspection

Emails were already visible under a Show emails button. Clicking it reloaded rather than showing/hiding the list. Only the first 25 of 413 addresses were available, with no visible search, pagination, download, or treatment/holdout label for each address.

**Expected:** Call the action Refresh preview if that is what it does. At minimum, explain whether the visible addresses are all matched customers or only planned recipients; they are not interchangeable once a holdout exists.

### 21. Delivery certainty is overstated in the audience header

The prominent line says “372 of 413 customers will receive this” (or 347 with the later holdout). Below it, the app correctly says these are planned recipients and Klaviyo applies consent and suppression later.

**Expected:** Say “372 customers are assigned to the email group; actual delivery is confirmed by Klaviyo.” The smaller caveat should not have to correct the headline.

## Handoff, history and Results

### 22. Successful draft creation ends with manual searching

The test handoff completed and replaced the create button with Draft created. It then told me to open Klaviyo and find “Turn first-time buyers into repeat buyers.” There was no direct campaign link and the status said “Not checked yet.”

**Expected:** Provide a clear next step, including the exact account/name and how status gets refreshed. A direct campaign link would be preferable when available. “Not checked yet” needs context when the screen has just confirmed creation.

### 23. Sender identity is visible but not resolved in the app

Final review showed `beaconai <atul@runbeacon.ai>` while the email design was acme. Reply-to said “Check in Klaviyo.” This may be intentional development configuration, but it is something a merchant must notice and resolve before sending.

**Expected:** Explicitly flag a sender that does not match the merchant's intended brand. Make the handoff checklist clear enough that the user does not mistake draft creation for completion of sender setup.

### 24. Duplicate names make history and Results difficult to use

Results initially contained three Bring back lapsed customers entries, two Draft created and one Awaiting send confirmation. No visible dates or distinguishing IDs helped tell them apart, and clicking the campaign name did not open campaign detail. Earlier campaigns similarly had repeated titles, “approved · locked,” and no clear chronology.

**Expected:** Include creation/handoff dates and a way to open the corresponding campaign. A merchant needs to answer “Which one is the draft I just worked on?” without guessing.

### 25. Results does not help resolve unconfirmed sends

“Results start once Klaviyo confirms the send” is sensible, but there is no visible check-status action, last-check information on these result rows, or explanation of whether the founder must perform a check. The newly created test draft appeared correctly as Draft created after the data loaded.

**Expected:** Explain who or what checks delivery and what the merchant should do now. Do not leave the user waiting for automation that may not be running.

### 26. Results briefly shows a false first-use state

After the test draft handoff, opening Results briefly showed “Results appear after your first campaign is created in Klaviyo” with Go to Campaigns, despite several campaigns already existing. It then loaded four draft rows.

**Expected:** Show loading until the app knows the account is empty. This is the same trust problem as zero totals during refresh.

### 27. “Program comparison” is unexplained

The first Results note says program comparison is unavailable and campaign observations should not be added together. It does not explain what Program means, what is missing, or when this might become available.

**Expected:** Lead with what the merchant can learn now. Explain unavailable analysis only when it helps them make a decision.

## First-use findings from before sign-in

28. The first visit showed Render's technical loading screen before BeaconAI. There was no product-branded explanation or expectation of how long to wait.
29. Blank store submission gave a useful validation message. However, `not a store` was accepted into a workspace as `not a store.myshopify.com` rather than being rejected in the form.
30. In that signed-out workspace, Re-run analysis was available and returned an authentication error. Results offered Try again for an error whose remedy was sign-in. The earlier Briefing error followed navigation into other sections.
31. Clearing the selected store returned to onboarding but left the old `shop` URL parameter. Reload restored the supposedly cleared store.
32. The initial form explains the benefit, but not what permissions/data are needed or what happens next. The store field relies on its placeholder for explanation. A short note would reduce hesitation before Connect Shopify.

## What worked well

- The user could complete Shopify login and reach a populated store.
- All three recommended plays and all six listed held plays could be opened; recommendation tabs worked.
- Adding the new recommendation was saved and produced an Added to Campaigns confirmation.
- Subject, preview text, headline, body, button label and URL edits were reflected in previews and survived reload/campaign switching.
- The five Restore suggested controls worked, as did selecting subject alternatives.
- Email/Inbox and Desktop/Mobile previews were useful. The observed mobile email was readable.
- Valid URL correction recovered from the invalid preview, and Edit destination focused the appropriate field.
- Holdout options updated the planned and comparison counts when allowed to finish. No-holdout messaging correctly explained the limit on causal interpretation.
- Back to review returned the new draft to editing; progressing again reached final review.
- Final review gathered subject, preview, design, CTA destination, audience groups, email body and sender in one place.
- The test Create draft in Klaviyo action completed, disabled repeat creation afterward, and the new draft appeared in Results.
- Results did not invent revenue or performance numbers for unconfirmed sends.

## Scope and remaining limits

I exercised the first-use form, main navigation, all visible recommendation rows, recommendation tabs, campaign history, existing campaign entries, new campaign approval, editing and restore controls, subject choices, starting-copy choices, rewrite controls, preview modes, holdout choices, recipient reload, approval/backtracking, draft creation, Settings, template refresh, store reselection, Results and sync recovery.

I did not send any campaign or test email, grant new provider permissions, disconnect accounts, delete campaigns, or fabricate sales. I did not inspect the draft inside a separately authenticated Klaviyo session. Success is confirmed by BeaconAI's visible handoff result, not independent inbox/provider verification. No campaign had a confirmed send in this store, so numerical Results, completed measurement windows, and their detail controls could not be exercised through the available UI.

The normal browser panel was narrow. Layout observations apply to that actual viewport; this was not an exhaustive multi-device compatibility test. The core functional findings above do not depend on treating that viewport as desktop.

I left a clearly marked test draft for the first-to-second-purchase campaign: subject **Merchant walkthrough — draft only**, with **This draft was created for the merchant walkthrough. Do not send.** in the support paragraph. Final holdout was 15%, with 347 planned recipients and 66 comparison customers reported by the app. Existing drafts were inspected; their text was not intentionally rewritten. No application code was changed.

## Smallest changes I would prioritize before the pilot

1. Fix same-store reselection and false empty/zero states.
2. Make optional copy truly optional.
3. Keep holdout controls and save-in-progress behavior consistent.
4. Correct draft-versus-sent wording and make locked campaigns visibly locked.
5. Make generated claims agree with the reviewed audience and evidence numbers.
6. Make approval labels, draft handoff, and Results next steps unambiguous.

These are the changes that would most improve merchant trust in the existing product.
