# Campaign UI specification — pilot scope

Status: **draft, awaiting founder review.** The C/D checkpoint in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) requires this to be reviewed
once before the UI is implemented. Every field named here exists today unless
marked *(D, not built)*.

Scope: the merchant journey from editing a campaign's copy to handing a draft to
Klaviyo and reconciling what happened. Not in scope: a template picker, an email
builder, a registry redesign, direct send from BeaconAI.

One shell per store, configured and approved by the founder. The "starting copy"
options choose *words*, never *visual templates* — the wording below keeps that
distinction visible so the control is not read as a Klaviyo template picker.

---

## 1. Desktop layout

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Campaigns                                                                     │
├──────────────┬────────────────────────────────────────────────────────────────┤
│ RAIL         │ ① Header: <campaign name>          Step: Copy · Review · Send  │
│              │    Store email design: Shop A, v3               [Saved]        │
│ Ready (2)    ├───────────────────────────────┬────────────────────────────────┤
│ ▸ Winback    │ ② EDITOR                      │ ③ PREVIEW                      │
│ ▸ Restock    │                               │  ┌──────────────────────────┐  │
│              │  Starting copy: Winback       │  │                          │  │
│ Sent (1)     │  [Change wording]             │  │  rendered email          │  │
│ ▸ Lapsed     │                               │  │  (600px, scaled to fit)  │  │
│              │  Subject          [________]  │  │                          │  │
│ Earlier (4)  │  Preview text     [________]  │  └──────────────────────────┘  │
│ ▸ …          │  Headline         [________]  │  ⚠ This preview is out of date  │
│              │  Body             [________]  │     — refresh to see what would │
│              │  Support text     [________]  │       actually be sent.         │
│              │   (optional)                  │     [Refresh preview]           │
│              │  Button label     [________]  │                                 │
│              │  Button links to  [________]  │                                 │
│              │                               │                                 │
│              │  [Continue to review →]       │                                 │
└──────────────┴───────────────────────────────┴─────────────────────────────────┘
```

**① Header.** Campaign name (`campaign.displayName`, falling back to
`campaign.playId`). Step indicator. `Store email design: <brand.brandName>, v<active.version>`
— read-only, from `GET /api/brand/email-template`. It is a statement of which
approved shell is in force, not a control; there is nothing here to pick.

**② Editor.** Column ~440px, min 380px. Field order is fixed and matches the
order those fields appear in the rendered email, so the editor reads as the email
does. "Support text" is labelled *(optional)* because deleting it is a real
choice the renderer honours.

**③ Preview.** Column ~600px, sticky below the header on scroll. Always the
output of the same renderer the send uses.

Rail groups: **Ready**, **Sent**, **Earlier campaigns** (previous runs,
collapsed). Selecting a campaign puts its id in the URL so a refresh reopens it.

## 2. Narrow screens (< 900px)

Single column, stacked: header → **preview** → editor → actions. Preview above
the editor, collapsed to a 240px-tall window with **[Expand preview]**, because
on a phone the merchant is checking *what this looks like* far more often than
they are typing into it. The stale/failure banner is never collapsed.

The step indicator becomes a back link plus "Step 2 of 3". Actions pin to the
bottom of the viewport; a disabled action keeps its reason visible above it
rather than in a tooltip.

---

## 3. Copy and branding (Ticket C)

| Control | Label | Notes |
|---|---|---|
| Starting copy | `Starting copy: <name>` + `[Change wording]` | Picks phrasing, not layout. Never "template". |
| Subject | `Subject` | |
| Preview text | `Preview text` | Inbox preheader. |
| Headline | `Headline` | |
| Body | `Body` | |
| Support text | `Support text (optional)` | Empty is honoured, not refilled. |
| Button label | `Button label` | |
| Destination | `Button links to` | `campaign.destinationUrl`; placeholder shows the store default when one exists. |

**Changing the starting wording** discards edits, so it confirms first — and only
when there is something to lose:

> Switching starting copy will discard your edits to this email. Continue?
> **[Switch wording]** [Keep my edits]

**Save states** (`saveState`, shown beside the header):

| State | Label | Behaviour |
|---|---|---|
| saving | `Saving…` | No action. |
| saved | `Saved` | Fades after 2s; the underlying state persists. |
| failed | `Not saved` + `[Retry]` | Persistent, amber. Blocks handoff. |
| conflict | `Changed elsewhere` + `[Reload]` | Persistent, amber. Blocks handoff. |

Failed and conflicted states are **sticky until resolved** — they do not clear
because a later request happened to find nothing pending.

## 4. Branded preview (Ticket C)

| State | What is shown | Action |
|---|---|---|
| `loading` | Previous render, dimmed + `Updating preview…` | — |
| `fresh` | Render, no banner | — |
| `stale` | Previous render + `This preview is out of date — refresh to see what would actually be sent.` | `[Refresh preview]` |
| `failed` | Previous render + `The preview couldn't be refreshed. What you see may not match what would be sent.` | `[Refresh preview]` |
| `unavailable` | Empty frame + `No approved email shell is configured for this store yet.` | — (founder task) |
| `missing_destination` | Empty frame + `This campaign has no destination link. Set where its button should send customers.` | Focus the destination field |
| `slot_value_rejected` | Empty frame + the field-specific message | Focus the named field |

A previous render stays visible **only** while explicitly marked out of date. It
is never presented as current.

Review is invalidated by: any edited field, a new active shell version, or a
failed refresh. Invalidated review means the send action is disabled with its
reason shown.

## 5. Review and handoff *(Ticket D — not built)*

Read-only summary of what will happen:

```
Email          <subject>                              [View full email]
Button links to <destination>
Audience       <n> customers from <run date> briefing
Send to        <treated> · Held back <holdout> (<pct>%)
Sender         <from Klaviyo account, or "Set in Klaviyo">
Shell          <brand name>, v<n>

[Create draft in Klaviyo]
```

**No direct-send action exists in the pilot.** The primary path is
**Create draft in Klaviyo → Open draft in Klaviyo**; the send itself happens in
Klaviyo, by a person.

Unknown values are labelled as unknown — `Sender: set in Klaviyo`, never a
guessed default. Checks BeaconAI has *not* performed are named as such:
`Consent and suppression are applied by Klaviyo at send.`

## 6. Execution states *(Ticket D — not built)*

| State | Message | Primary | Disabled |
|---|---|---|---|
| ready | — | `Create draft in Klaviyo` | — |
| creating | `Creating the draft in Klaviyo…` | — (spinner) | all edits, the create action |
| draft created | `Draft created in Klaviyo. Review and send it there.` | `Open draft in Klaviyo` | all edits |
| awaiting send | `Waiting for this to be sent in Klaviyo.` | `Open draft in Klaviyo` · `Refresh status` | all edits |
| sent | `Sent <date> to <n> customers.` | `View results` | everything |
| known failure | the provider's message | `Try again` | edits |
| **uncertain** | `We couldn't confirm whether this reached Klaviyo. Open Klaviyo and check before trying again.` | `Open Klaviyo` | **`Try again` is not offered** |

- `creating` corresponds to `campaign.handoffReservedAt` being set. A second
  handoff is refused server-side (`conflict: handoff_in_progress`); the UI shows
  the creating state rather than a second button.
- **Uncertain never offers a blind retry.** A retry could create a duplicate
  campaign. Recovery is manual reconciliation.
- **Only a confirmed provider send becomes "Sent."** A created draft is not a
  send, and `campaign.sentAt` must come from provider reconciliation, not from a
  local status write. *(D)*

## 7. Continuity

Returning to a campaign restores its real state and the content that was
reviewed, from `campaign` — not from the current briefing.

After handoff (`campaign.frozen`), the editor is read-only with:

> This campaign was handed off on <date>. Its content is locked.
> Sending a changed version means starting a new campaign.

**The stored HTML is what BeaconAI handed over, not necessarily what was sent.**
If someone edits the draft in Klaviyo afterwards, BeaconAI does not know. Label
it exactly that way — `Handed to Klaviyo on <date>` — and never
"the email that was sent" unless provider reconciliation confirms it *(D)*.

Blocked from handoff: a failed save, an unresolved conflict, a stale preview, a
changed shell version, a missing destination. Each states its own reason.

## 8. Field mapping

| UI element | Field | Source | Owner |
|---|---|---|---|
| Campaign name | `campaign.displayName` → `playId` | `GET /campaigns/:shop` | C |
| Copy fields | `campaign.draftEdits` over `campaign.copy.copy` | same | C |
| Destination | `campaign.destinationUrl` → brand `ctaUrl` | same | C |
| Save state | request outcome; revision `campaign.revision` | `POST /campaigns` | C |
| Shell name/version | `active.version`, `active.brand.brandName` | `GET /brand/email-template` | C |
| Preview HTML | `html` | `POST /klaviyo/campaigns/preview-html` | C |
| Preview freshness | `templateVersion`, `renderFingerprint` | same | C |
| Setup / destination errors | `code` | same | C |
| Audience counts | `audienceSize`, `holdoutSize`, `holdoutPct` | `GET /campaigns/:shop` | C/D |
| Originating run | `campaign.runId`, `audienceRef` | same | D |
| Provider reference | `campaign.klaviyoCampaignId` | same | D |
| Creating state | `campaign.handoffReservedAt` | same | D |
| Locked state | `campaign.frozen`, `frozenAt` | same | D |
| Uncertain outcome | `reconciliationRequired`, `providerStage` | handoff 500 | D |
| Sent time / counts | provider reconciliation | *not built* | D |
| Sender identity | Klaviyo account | *not built* | D |

**Null handling:** a null count renders `—` with `Not known yet`, never `0`.
`audienceSize` absent means the audience has not been resolved, which is
different from an audience of zero.

## 9. Accessibility

- Every status is text, never colour alone. Amber states carry `⚠`; success
  carries `✓`.
- Blocking banners are `role="status"`; a blocked action is `disabled` with
  `aria-describedby` pointing at its reason.
- Focus order follows the visual order; the editor's field order matches the
  email's. After a blocked handoff, focus moves to the reason.
- `[Refresh preview]` and `[Retry]` are real buttons, keyboard reachable.
- The preview iframe has a title; it is decorative for screen readers, so the
  editor fields remain the accessible source of the copy.

## 10. Review examples

Seed examples only — clearly labelled, never a live recipient list.

1. Healthy: saved, fresh preview, destination set, ready.
2. Unsaved: `Not saved` + retry, handoff blocked.
3. Stale: edited body, preview marked out of date, handoff blocked.
4. Not configured: `brand_setup_required`, empty preview.
5. No destination: `missing_destination`, field focused.
6. Shell changed: reviewed v2, active v3, handoff refused, refresh prompted.
7. Locked: handed off, read-only, `Handed to Klaviyo on <date>`.
8. Uncertain: no retry offered, `Open Klaviyo` only.

## 11. Exit criteria

Founder reviews this once. Then:

- **C closes** when items 3, 4, 7 (editor side) and 8 (C-owned rows) are
  implemented, with desktop and narrow-screen screenshots, and the renderer
  checks pass.
- **D closes** when items 5, 6, 7 (locked/reconciliation) and 8 (D-owned rows)
  are implemented, with the execution states verified.
- **Before the first live handoff**, walk the combined flow: edit → save →
  current preview → create draft → open Klaviyo → reconcile status. Also verify
  failed save, changed shell, failed preview, and uncertain-handoff recovery.

### Already implemented against this spec (C)

Save states (§3), preview freshness including stale/failed/unavailable (§4),
destination field (§3, §8), starting-copy confirmation (§3), reopening earlier
campaigns (§7). Screenshots and the narrow-screen adaptation are outstanding, as
is the header's shell name/version line.
