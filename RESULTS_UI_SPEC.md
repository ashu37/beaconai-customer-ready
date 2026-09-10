# Results UI specification — Ticket G pilot scope

**Status: DRAFT for founder review. Ticket G's UI implementation waits for approval.** Measurement-correctness fixes that don't change the screen may proceed meanwhile.

Scope authority: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), "Before Ticket G" and Ticket G. Baseline: `main` at `86f939d` (Ticket F collection merged). Design context: [SELLABILITY_UX_REVIEW.md](SELLABILITY_UX_REVIEW.md) §4 — used for wording and hierarchy only. This spec does **not** bring back its deferred items: tabs, search, date filters, a separate detail route, four comparison cards, or daily charts.

All example numbers here are **seed examples**, and are labelled as such wherever they appear.

## 1. What changes from the existing UI

Keep the Results page, the chronological campaign list, the one-row-at-a-time inline expansion, the 30/60/90 selector, and the existing typography and buttons.

| Today | Pilot change | Why |
|---|---|---|
| A row's verdict follows the 30-day window, while its detail follows whichever window is selected | The row **always** shows the 30-day window, labelled "30-day result". The detail selector changes only the detail. | This removes the mixed-window state (a row saying "Worked" while its detail was at day 45 of 60). |
| "4,680 sent · 456 held" | "4,224 assigned to receive · 456 held back", plus "Klaviyo sent 4,130" or "sent count unavailable" | The whole audience was never sent. Assignment and provider sends are different counts. |
| An interval shown on a campaign still measuring | While measuring: "Early observation · day 5 of 30" with each group's revenue per customer. No difference, no interval, no verdict. | Early data is factual; a verdict isn't earned yet. |
| Verdicts: Worked / Cost you money / No effect found / Too small to tell | **Positive result / Negative result / No clear difference / More data needed / Measuring / Comparison unavailable** | "No effect found" overclaims. "No clear difference" doesn't mean the campaign had no effect. |
| A "more data" floor counted orders | Floors count **unique purchasers** | Ten orders from one customer are one purchaser (protocol §4.9). |
| The program band showed an invalid pooled number | The band states the program's measurement status (§7). No figure until Ticket H. | The comparison was withdrawn in Ticket F. |
| A selected campaign is lost on refresh | `?campaign=<id>` in the URL; refresh reopens that row expanded | Uses the existing URL parameter mechanism. No router. |
| Original email and rationale aren't shown | An "Original campaign" section in the detail | The merchant should see what was sent and why, beside the result. |
| Stale or failed measurement is silent | A freshness line, and a failed refresh that keeps the last result visible | Old numbers must be labelled as old, not hidden or passed off as current. |

**Not included:** tabs, search or filters, date pickers, pagination beyond a "Load more" button, a separate detail page, purchase-rate / orders-per-100 / AOV cards, daily or cumulative charts, a revision timeline, export, or a program figure before Ticket H.

## 2. What a merchant can answer from this page

What did we send, and when did Klaviyo confirm it? Which result is this, and how far through its window is it? What can be concluded now — or why nothing can? When should I look again? What did the email say, and why was it suggested?

## 3. Desktop wireframe (≥ 1024px)

```text
┌ Results ───────────────────────────────────────────────────────────────────┐
│ Campaign results                                                            │
│ What happened after each campaign, compared with customers held back.       │
│                                                                             │
│ ┌ PROGRAM ─────────────────────────────────────────────────────────── [§7] ┐│
│ │ Program results haven't started.                                        ││
│ │ They need a fixed group of customers held back from every BeaconAI      ││
│ │ campaign. Until then, each campaign below is measured on its own.       ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│ CAMPAIGNS · 30-DAY RESULT                              Newest first · 4 shown│
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │ Bring back lapsed customers            [Measuring]     Early observation ││
│ │ Sent Sep 2 · 211 assigned · 23 held back day 5 of 30    $4.10 vs $3.95  ▸││
│ ├──────────────────────────────────────────────────────────────────────────┤│
│ │ Reduce discount dependency       [No clear difference]   +$1.20 / cust  ▾││
│ │ Sent Aug 1 · 499 assigned · 56 held back                 −$3.40 to +$5.80 ││
│ │ ┌ DETAIL (expanded; §5.2) ──────────────────────────────────────────────┐││
│ │ │ …                                                                     │││
│ │ └───────────────────────────────────────────────────────────────────────┘││
│ ├──────────────────────────────────────────────────────────────────────────┤│
│ │ Turn first-time buyers into repeat…  [Draft created]  Results start when ││
│ │ Not sent yet                                          Klaviyo confirms ▸ ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│                                              [ Load more ]  (only if capped) │
└─────────────────────────────────────────────────────────────────────────────┘
```

Annotations:
- **A. Row grid:** campaign (name, then sent line) | status chip | 30-day figure (value, then range or sub-label) | chevron. The chevron is decorative; the whole row is the button.
- **B. Sent line:** "Sent {provider-confirmed date}" — or the delivery label (§6.1) when there is no confirmed send — then assigned and held-back counts. The word "sent" is never paired with an assignment count.
- **C. 30-day figure:** a completed window shows the per-customer difference and its 95% range; measuring shows each group's per-customer value; otherwise "—" with the reason.
- **D. Order:** newest send first, by provider-confirmed time. Unconfirmed campaigns sort by handoff time. Nothing is ever dropped.

## 4. Narrow screens (< 720px)

The list becomes stacked cards in the same order:

```text
┌──────────────────────────────────────┐
│ Bring back lapsed customers          │
│ [Measuring]  Early observation · 5/30│
│ Sent Sep 2 · 211 assigned · 23 held  │
│ Received $4.10 · Held back $3.95     │
│                         View result ▸│
└──────────────────────────────────────┘
```

The detail opens inline below its card, full width. The comparison becomes one group per line, and the group table becomes a two-column list (label, then Received / Held back). Touch targets are at least 44px. The window selector wraps; the page never scrolls sideways.

## 5. Exact components, order and wording

### 5.1 Row
| Element | Wording / rule |
|---|---|
| Name | The campaign's saved display name (`campaigns.display_name`), never today's slate. |
| Sent line | `Sent {Mon D, YYYY}` from `provider_sent_at`, then ` · {assigned} assigned · {held} held back`. With no confirmed send: the delivery label (§6.1) instead of "Sent …". |
| Status chip | §6 vocabulary. Text always present; colour only reinforces it. |
| 30-day figure | Completed: `+$1.20 / customer` over `−$3.40 to +$5.80`. Measuring: `Early observation` over `day 5 of 30`, then `$4.10 vs $3.95` (received vs held back). Other states: `—` over the reason. |
| Action | The entire row is a `button` with `aria-expanded`. |

### 5.2 Detail (expanded row), top to bottom
1. **Header line:** `Sent {date and time}, confirmed by Klaviyo` · `Klaviyo sent {n}` or `Sent count unavailable` · delivery label if not sent.
2. **Window selector:** `30 days (primary)` · `60 days` · `90 days`, each with ` · open` until complete. A radio group. Default: 30.
3. **Freshness:** `Orders synced through {date} · Calculated {date time}`. If older than 24 hours: `Last calculated {relative} ago` plus the refresh action (§6).
4. **Outcome and next step:** one sentence from the selected window's typed state (§6). For example, "Still measuring. Review the 30-day result on Oct 2."
5. **Comparison** (all three values from the selected window only):
   `Received campaign  $X.XX per customer` · `Held back  $Y.YY per customer` · `Difference  +$Z.ZZ (95% range $L to $H)`. The difference and range appear only when the window is complete and the floors pass.
6. **Group table:**

   | | Assigned to receive | Held back |
   |---|---|---|
   | Customers | 211 | 23 |
   | Unique purchasers | 31 | 3 |
   | Orders | 38 | 3 |
   | Revenue, net of refunds | $1,240 | $96 |
   | Revenue per customer | $5.88 | $4.17 |

7. **"How this is measured"** (collapsed): the fixed text in §6.3, the window dates, "Revenue is net of refunds; cancelled and test orders are excluded. Not profit." and the repeated-exposure note when it applies (§6.3).
8. **"Original campaign"** (collapsed): subject line, preview text, destination link, `View email` (the frozen rendered HTML in a sandboxed frame), the audience definition and size, and "Why it was suggested" (the evidence line and observed change from the originating run's presenter output, as in Ticket E).
9. **Footer:** `Open in Klaviyo` only when the provider gave a URL; otherwise "Find “{name}” in Klaviyo".

## 6. States

Each state has: what shows, the chip, the outcome sentence, and the recovery action. Seed examples are in brackets.

### 6.1 Not measurable yet (delivery)
The label comes from `presentDelivery`, the same as the Campaigns page.

| Delivery | Chip | Row text | Recovery |
|---|---|---|---|
| created / awaiting_send | Draft created / Awaiting send confirmation | "Results start once Klaviyo confirms the send." | Open the draft in Klaviyo |
| scheduled | Scheduled in Klaviyo | same | none |
| uncertain | Needs checking | same | Founder: Check Klaviyo status |
| failed | Draft not created | "The draft wasn't created, so nothing was sent." | Go to Campaigns |
| sent, no time | Sent | "Klaviyo reports this as sent but not when, so results can't start yet." | Founder: Check Klaviyo status |
| local only | Not confirmed | "Marked sent in BeaconAI, but Klaviyo hasn't confirmed a send." | none |

### 6.2 Measurement states (selected window)
| State | Chip | Outcome sentence | Shows |
|---|---|---|---|
| Loading | — | "Loading results…" (skeleton rows) | Last rows, if cached |
| No campaigns | — | "Results appear after Klaviyo confirms your first campaign was sent." | Link: Go to Campaigns |
| Measuring [day 5 of 30] | Measuring | "Still measuring. Review the 30-day result on Oct 2." | Early per-customer values for both groups; no difference or range |
| Positive [+$4.80, range $1.10 to $8.50] | Positive result | "Customers who received the campaign spent more per customer. The range is above zero for this window." | Full comparison |
| Negative [−$3.90, range −$7.20 to −$0.60] | Negative result | "Customers who received the campaign spent less per customer. The range is below zero for this window." | Full comparison |
| No clear difference [+$1.20, range −$3.40 to +$5.80] | No clear difference | "The result isn't clear. The range includes both a decrease and an increase." | Full comparison. **Never** "no effect". |
| Insufficient data [2 held-back purchasers] | More data needed | "Too few customers bought in one group to compare them reliably." | Group table; no difference or range |
| No holdout | Comparison unavailable | "No customers were held back, so there's nothing to compare against." | Received group's figures only |
| Stale [calculated 3 days ago] | *unchanged* | Freshness line: "Last calculated 3 days ago." | Last result stays, plus `Recalculate` |
| Failed refresh | *unchanged* | "Couldn't recalculate. Showing the result from {date}." | Last result stays, plus `Try again` |

Green and red appear only on Positive and Negative results. A positive point estimate alone never turns the row green.

### 6.3 Fixed measurement text
> "We compare customers assigned to receive this campaign with customers held back from it, over the same days after the send. Held-back customers were chosen at random and received no BeaconAI campaigns. Your other marketing reached both groups."

**Repeated exposure,** shown when the customers had earlier BeaconAI campaigns:
> "Some of these customers received earlier BeaconAI campaigns and the held-back group received none, so this compares BeaconAI campaigns so far — not this email alone."

## 7. Program summary — placement and states (Ticket H)
A band at the top of the page, above the list. Its data contract depends on Ticket F's approved protocol; until then only the first state exists.

| State | Band text |
|---|---|
| Not started *(today)* | "Program results haven't started. They need a fixed group of customers held back from every BeaconAI campaign. Until then, each campaign below is measured on its own." |
| Enrolled, not yet started | "Program cohort set on {T0}: {n} customers, {h} held back. Measurement starts when Klaviyo confirms the first BeaconAI send." |
| Measuring | "Program measurement · day {d} of 90 · {n} customers assigned to receive, {h} held back. First result {date}." No figure. |
| Result | Per-customer difference with its 95% range, the cohort's dates and sizes, and the §6.2 vocabulary (it may say "No clear difference"). A total only as per-customer difference × assigned customers, labelled as an estimate. |
| Unavailable | "Program result unavailable: {reason}." For example, the cohort closed without a confirmed send, or an identity or contamination flag needs review. |

## 8. Field mapping (existing / planned)
| Element | Source | Null handling |
|---|---|---|
| Name | `campaigns.display_name` (existing) | Fall back to the play's display name; never the latest slate |
| Sent date | `delivery.providerSentAt` when state is `sent` (existing) | No date is shown; the delivery label replaces it |
| Assigned / held back | recipient counts by arm (existing: `audience_size` minus `holdout_size`, and `holdout_size`) — **planned:** count from `campaign_recipients` | "—" |
| Klaviyo sent | `delivery.providerSentCount` (existing) | "Sent count unavailable" (never 0) |
| Window, day N, complete | `windows[].windowDays`, `daysElapsed`, `complete` (existing) | — |
| Window start/end dates | **planned** `windows[].start`, `windows[].end` | Hide the dates line |
| Calculated at | **planned** `windows[].calculatedAt` (the stored `measured_at`) | "Not calculated yet" |
| Orders synced through | **planned** from the active sync (`sync/status` `active.publishedAt`) | "Sync time unavailable" |
| State | **planned** typed `windows[].assessment` (measuring / insufficient / unclear / positive / negative / unavailable) and `reasons[]`; replaces `verdict` | Never inferred in React from a boolean |
| Group figures | `treated` / `holdout`: `n_customers`, `n_orders`, `revenue` (existing); **planned** `purchasers` | Unique purchasers "—" until provided; zero shown only when known |
| Difference / range | `comparison.perCustomer` (existing) | Omitted unless the assessment permits it |
| Repeated-exposure note | **planned** `windows[].priorExposure: boolean` | Omitted |
| Original email | `campaigns.approved_copy`, `rendered_html`, `destination_url` (existing, frozen) | "Original email not stored" for pre-freeze campaigns |
| Why suggested | the originating run's presenter output, looked up by `run_id` and `play_id` (existing) | "Recommendation details not available for this run" |
| Selection | `?campaign=<id>` (planned; the existing URL-parameter mechanism) | An unknown id opens nothing and shows no error |
| Load more | `listCampaigns` limit 200 (existing) | The button is shown only when 200 are returned |

## 9. Accessibility
- Each row is a button with `aria-expanded` and `aria-controls`. Enter or Space toggles it, and the detail receives focus on open.
- The window selector is a radio group operated with the arrow keys.
- Every status is carried by text as well as colour.
- A 2px focus ring is visible on the rows, the selector and every action.
- The table uses `<th scope>`. The frozen email frame is sandboxed and has a title.

## 10. Acceptance (seed examples)
The seed shop shows every state in §6, visibly labelled "Sample data". The page is checked at 1440, 1024 and 390px, with keyboard only, and after a refresh with `?campaign=`. The row and its detail never show different windows. No page ever shows "sent" beside an assignment count.

## 11. Decisions for the founder
1. **Early observations while measuring:** show each group's per-customer value with no difference (proposed), or hide all numbers until the window closes?
2. **Verdict wording** in §6.2: "Positive result / Negative result / No clear difference / More data needed / Comparison unavailable".
3. **Original campaign** placement: collapsed inside the detail (proposed), or open by default?
4. **Freshness threshold** for "stale": 24 hours (proposed).
5. **Program band wording** for the "Not started" state (§7).
