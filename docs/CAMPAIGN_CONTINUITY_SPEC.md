# Campaign continuity across analyses

Agreed 2026-09-14. Governs what a merchant's campaign work does when a new analysis (briefing) arrives.

**Merchant promise:** *New analysis updates your recommendations. Your campaign work stays where you left it.*

## Identities

| Id | What it identifies | Used for |
|---|---|---|
| **Play id** | A kind of recommendation, stable across analyses (`winback_dormant_cohort`) | Discovery: connecting a new recommendation to earlier work on the same play |
| **Campaign id** | One draft, its approval, audience and send | All editing, saving, approval, preview binding and handoff |
| **Run id** | The analysis that produced a campaign's evidence and audience | Preserving where a campaign came from; resolving its audience at handoff |

Matching by play is for discovery only. **It never transfers approval, audience or send state to a newer recommendation.**

## Behaviour when a new briefing arrives

| Situation | What the merchant sees |
|---|---|
| Untouched recommendation | The newest recommendation. |
| Dismissed | "You set this aside on {date}" with **Restore**. Scoped to the merchant's decision; no campaign transition is invented. |
| Existing draft or approval | The campaign is unchanged. "You already have a draft for this play" → **Continue draft**. |
| New recommendation differs from the draft | **Review latest recommendation**: the merchant explicitly creates an updated draft from their saved copy. |
| In Klaviyo | Link to the existing campaign and its status. Never silently replaced or duplicated. |
| Sent | "Sent {date} · Measuring" → **View results**. The new recommendation is never shown as already approved. |
| Play absent from the latest analysis | The campaign stays in Campaigns with "Not included in the latest briefing." A reason is shown only if the engine supplies one. |

Example: a merchant approved a 234-person winback campaign; the new briefing recommends 238 people. The existing campaign still targets its original 234. The merchant can continue it, or review an updated draft; their copy survives either way, and adopting the new audience requires reviewing it.

## Rules

1. **No approval by threshold.** Approval is preserved only while the approved campaign itself is unchanged. Adopting a new audience keeps copy but requires audience and final review. When membership is available, show customers added, removed and retained — never size alone (234 → 238 can hide substantial replacement).
2. **Replacement drafts are explicit and atomic.**
   - Copy the merchant's saved content first — overrides, intentional blanks, destination — so generated copy never overwrites it. Preserve writing choices; validate against the current approved design and regenerate the preview.
   - The replacement starts **unapproved**. Link both records. Mark the old draft superseded only **after** the replacement persists. Prevent double-click duplicates.
   - Never supersede a handed-off or sent campaign as part of a briefing refresh.
3. **Audience-age warning** (a warning, not an exclusion claim): *"This audience comes from your Sep 3 analysis. In orders synced through Sep 30, 12 of these customers have ordered since."*
   - Count distinct audience members, not orders.
   - Use the snapshot's actual analysis cutoff where available, not the run timestamp.
   - If coverage or identity matching is incomplete, say so; missing data is never "0 customers".
   - Show during audience review; refresh before Klaviyo draft creation.
4. **Sent plays:** warn, don't block. Thirty days is a measurement window, not a contact cooldown. Show the existing send prominently and require an explicit new campaign. Don't promise recent-recipient exclusion until it is implemented and recorded. Never override persistent program holdouts.
5. **Re-running:** a light nudge ("Last analysed 2 days ago. Recommendations may be similar."), no minimum interval, no confirmation dialog, no predictions of change. A suggested monthly rhythm is fine.

## Implementation order

1. **Hydration and open-editor preservation** — reconcile when the authoritative run changes; reject stale responses; never replace an open editor or its pending saves. *(PR: fix/hydration-open-editor)*
   Acceptance: same-tab re-run, cached-briefing reload and a delayed older response all preserve campaign identity and edits.
2. **Campaign-keyed editing, save, preview and handoff state** *(PR: fix/campaign-keyed-workspace)*: copy, pending saves, revision, approved render, handoff package and approval all move together, so copy can never belong to one campaign while approval belongs to another. No new screens or state framework.
   - *Stable identity before editing.* Create or resolve the campaign record before initializing editable state. Never fall back to a play id when the campaign id is missing.
   - *Async work stays pinned.* Saves, debounce callbacks, preview responses and handoff requests capture their campaign id when they start. Switching editors never redirects an outstanding operation.
   - *Approval stays version-bound.* The campaign id alone is not enough: approval must still match the saved revision, rendered preview and template version.
   - *Historical campaigns stay accessible.* Limiting the briefing's Approved badge to the displayed run must not hide or reset approvals on older campaigns.
   - Step 1's stale-response protections stay. A wrong Approved badge can come from stale hydration (step 1) or from state shared by play id (step 2).

   Tests:
   - Two campaigns share a play id; editing one never changes, approves or hands off the other.
   - A save or preview starts for campaign A, the editor switches to B, then A's request resolves.
   - A's save fails or conflicts; B's save state and handoff eligibility are unaffected.
   - The handoff uses the selected campaign's origin run and audience.
   - A reload after a re-run shows the correct badge and draft state.
3. **Existing-campaign links and explicit replacement drafts** (rule 2). Step 2 fixes identity internally; step 3 makes continuity visible.

   | Existing campaign for this play | Briefing card shows |
   |---|---|
   | Draft or approved, not handed off | "You already have a draft" → **Continue draft** |
   | Created in Klaviyo | Its delivery status → **Open in Klaviyo**, when a provider link exists |
   | Sent | "Sent Sep 10 · Measuring" → **View results** |
   | None | The normal create-draft action |

   An existing campaign from an older analysis never makes the new recommendation "Approved". For an older editable draft, **Review latest recommendation**:
   1. Show the existing draft's analysis date next to the latest recommendation.
   2. The merchant explicitly chooses **Create updated draft**.
   3. Create a new campaign tied to the latest run, copying saved text, intentional blanks and destination.
   4. Require a fresh preview, audience review and approval.
   5. Only after creation succeeds, mark the old draft superseded and link the two.

   Nothing is copied, superseded or re-approved just because an analysis runs again. Handed-off and sent campaigns stay unchanged. A draft whose play leaves the briefing stays in Campaigns with "Not included in the latest analysis."
4. **Membership-change summaries and audience-age warnings** (rules 1 and 3); "currently measuring" shown separately from changes caused by the re-run.
5. **Later:** analysis provenance and reuse — record engine version, effective configuration and the actual date anchor first; unknown provenance means no reuse; failed runs stay retryable ("No changes to analyse; showing your latest briefing").

Out of scope for the pilot: automatic audience refresh, approval transfer, materiality thresholds, engine hysteresis (discuss with DS separately; it reduces flicker but does not address repeated testing), send-time audience rebuilding.
