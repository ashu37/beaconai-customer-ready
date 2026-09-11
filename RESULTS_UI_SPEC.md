# Results UI specification — Ticket G pilot scope

**Status: revised September 10, 2026 with the founder's UX choices, and implemented in Ticket G (PR #42).** **Ticket G's UI is separate from program measurement**, which stays gated by Ticket F's draft protocol. No program figure appears until Ticket H.

Scope authority: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), "Before Ticket G" and Ticket G. Design context: [SELLABILITY_UX_REVIEW.md](SELLABILITY_UX_REVIEW.md) §4, used for wording and hierarchy only. Excluded: tabs, search, date filters, a detail route, metric cards, charts, and an analytics framework.

Example numbers are **seed examples**.

## 1. Founder decisions (resolved)

| Question | Decision |
|---|---|
| Early numbers while measuring | Show each group's revenue per customer, labelled **"Early observation"**. No difference, interval, verdict or winner colour until the selected window is complete **and** its reporting checks pass. |
| Outcome wording | **Higher spending / Lower spending / No clear difference / Insufficient data / Measuring / Comparison unavailable** |
| Original campaign | Collapsed inside the expanded result. |
| Freshness | 24 hours. Source-data freshness and calculation freshness are checked and shown **separately**. |
| Program band | "Program comparison isn't available yet. Campaign-level observations appear below; they should not be added together." No program number before Ticket H. |

## 2. What changes from the existing UI

Kept: the Results page, the chronological list, one-row inline expansion, the 30/60/90 selector, delivery-state presentation, and the existing styles.

| Before | Now |
|---|---|
| The row's verdict and the detail could show different windows without saying so | The row always shows the **30-day result**, labelled. The detail defaults to 30 and can switch to 60 or 90. Everything in the detail follows the selected window. |
| "4,680 sent · 456 held" | "4,224 assigned to receive · 456 held back", and separately "Klaviyo sent 4,130" or "Sent count unavailable". |
| Verdicts from a boolean ("Worked", "No effect found") | A typed assessment from the API, with reasons, rendered in the §1 vocabulary. |
| Floors counted orders | Unique purchasers are counted separately from orders. |
| Invalid program number | The program band text from §1. |
| Selection lost on refresh | `?campaign=<id>` reopens the expanded result. |
| No original email | "Original campaign", collapsed: the frozen email plus the recommendation from its originating run. |
| Stale or failed calculation was silent | Persistent messages with a recovery action. |

## 3. Desktop wireframe (≥ 1024px)

```text
Campaign results
What happened after each campaign, compared with customers held back.

┌ PROGRAM ───────────────────────────────────────────────────────────────┐
│ Program comparison isn't available yet. Campaign-level observations    │
│ appear below; they should not be added together.                      │
└────────────────────────────────────────────────────────────────────────┘
[source/stale banner, only when needed — §6.4]

CAMPAIGNS · NEWEST FIRST
┌────────────────────────────────────────────────────────────────────────┐
│ Bring back lapsed customers        [Measuring]        30-DAY RESULT    │
│ Sent Sep 2 · 211 assigned to receive · 23 held back   Early observation│
│                                                       $4.10 · $3.95   ▸│
├────────────────────────────────────────────────────────────────────────┤
│ Reduce discount dependency  [Comparison unavailable]  30-DAY RESULT    │
│ Sent Aug 1 · 499 assigned to receive · 56 held back   $6.02 · $5.10   ▾│
│ ┌ EXPANDED ──────────────────────────────────────────────────────────┐ │
│ │ Sent Aug 1, 2026, 9:05 AM, confirmed by Klaviyo · Klaviyo sent 471 │ │
│ │ Window: (•) 30 days  ( ) 60 days  ( ) 90 days                      │ │
│ │ Aug 1 – Aug 31, 2026 · complete                                    │ │
│ │ Last successful sync Sep 10, 8:12 AM · Calculated Sep 10, 8:15 AM  │ │
│ │ OUTCOME  one sentence for the selected window (§6)                 │ │
│ │ Assigned to receive $6.02 / customer · Held back $5.10 / customer  │ │
│ │ [Difference and 95% range — only when the assessment permits]      │ │
│ │ Group table (§5.3)                                                 │ │
│ │ Notes: exposure note (§6.5) · other marketing (§6.6)               │ │
│ │ ▸ How this is measured       ▸ Original campaign                   │ │
│ └────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────┤
│ Turn first-time buyers into…   [Draft created]        30-DAY RESULT    │
│ Not sent yet                                          Results start    │
│                                                       once Klaviyo…   ▸│
└────────────────────────────────────────────────────────────────────────┘
                                   [ Show older campaigns ]  (only if more exist)
```

## 4. Narrow screens (< 720px)

Each row becomes a stacked card: name → status chip → sent line → "30-day result" block. Group values are labelled **"Assigned to receive $4.10"** and **"Held back $3.95"**, one per line; values are never shown unlabelled. The expanded detail follows the same order as desktop, full width. The group table becomes label/value pairs, one group at a time. The window radio buttons wrap. Touch targets are at least 44px, and the page never scrolls sideways.

## 5. Components and exact wording

### 5.1 Row (collapsed) — always the 30-day window
- **Name:** `campaigns.display_name` (saved), falling back to the play's display name. Never today's slate.
- **Sent line:** `Sent {Mon D, YYYY}` from the provider-confirmed send, then `· {assigned} assigned to receive · {held} held back`. With no confirmed send, the delivery label from `presentDelivery` replaces "Sent …".
- **Status chip:** the 30-day assessment (§6.2), or the delivery label (§6.1). Colour only for Higher / Lower spending.
- **30-day block:** the label **"30-day result"**, then one of:
  - early observation: `Early observation` over `{assigned $} · {held $}`
  - a permitted comparison: `+$1.20 / customer` over `−$3.40 to +$5.80`
  - descriptive only: both per-customer values
  - otherwise: `—` over the reason
- **Interaction:** the whole row is a `button` with `aria-expanded` and `aria-controls`.

### 5.2 Expanded detail — follows the selected window
1. **Header:** `Sent {date, time}, confirmed by Klaviyo` · `Klaviyo sent {n}` or `Sent count unavailable`.
2. **Window selector:** a radio group, `30 days` (default) · `60 days` · `90 days`, each with ` · open` until complete.
3. **Window dates:** `{start} – {end}` · `complete` or `day {d} of {n}`.
4. **Freshness:** `Last successful sync {date time}` · `Calculated {date time} from the store sync of {date time}`, with the §6.4 messages when needed. Every calculation records the sync it read.
5. **Outcome sentence** for the selected window (§6).
6. **Comparison:** `Assigned to receive $X.XX per customer` · `Held back $Y.YY per customer`. Then `Difference +$Z.ZZ per customer (95% range $L to $H)` **only** when the assessment permits it.
7. **Group table** (§5.3).
8. **Notes:** the exposure note (§6.5) when applicable, and the other-marketing note (§6.6) always.
9. **"How this is measured"** (collapsed): the window dates, and "Revenue is net of refunds; cancelled and test orders are excluded. Not profit. Customers Klaviyo did not deliver to stay in the assigned group."
10. **"Original campaign"** (collapsed; loaded when opened): subject, preview text, destination link, and the **Handoff email** frame (sandboxed) captioned with C-UI's wording: "Email handed to Klaviyo on {time}. Changes made later in Klaviyo aren't reflected here." It is never called "as sent". Then "Why it was suggested": the originating run's recommendation (evidence source and observed change, as in Ticket E), with its audience size and definition.

### 5.3 Group table (selected window)
| | Assigned to receive | Held back |
|---|---|---|
| Customers | 211 | 23 |
| Unique purchasers | 31 | 3 |
| Orders | 38 | 3 |
| Revenue, net of refunds | $1,240.00 | $96.00 |
| Revenue per customer | $5.88 | $4.17 |

"Unique purchasers" means customers with at least one qualifying order in the window. It is never an order count.

## 6. States

### 6.1 Before a confirmed send (from the delivery contract)
| Delivery state | Chip (`presentDelivery`) | Text |
|---|---|---|
| created / awaiting_send | Draft created / Awaiting send confirmation | "Results start once Klaviyo confirms the send." |
| scheduled | Scheduled in Klaviyo | same |
| uncertain | Needs checking | same |
| failed | Draft not created | "The draft wasn't created, so nothing was sent." |
| sent, no time | Sent | "Klaviyo reports this as sent but not when, so results can't start yet." |
| local only | Not confirmed | "Marked sent in BeaconAI, but Klaviyo hasn't confirmed a send, so results can't be measured." |

### 6.2 Assessment (selected window; typed by the API)
| Assessment | Chip | Sentence | Numbers shown |
|---|---|---|---|
| `measuring` | Measuring | "Still measuring. Review the {n}-day result on {end date}." | Early observation only |
| `insufficient_data` | Insufficient data | "Too few customers or purchasers in one group to compare them." | Group table |
| `awaiting_order_data` | Comparison unavailable | "This window ended {end}, but order data only runs to {coverage}. Re-sync the store to complete it." | Group table, labelled incomplete |
| `no_holdout` | Comparison unavailable | "No customers were held back, so there's nothing to compare against." | Assigned group only |
| `assessment_policy_pending` | Comparison unavailable | "Group figures are shown as observations. A comparison isn't reported yet." | Group table; no difference |
| `higher_spending` | Higher spending | "Customers assigned to receive the campaign spent more per customer. The 95% range is above zero for this window." | Full comparison |
| `lower_spending` | Lower spending | "Customers assigned to receive the campaign spent less per customer. The 95% range is below zero for this window." | Full comparison |
| `no_clear_difference` | No clear difference | "The result isn't clear. The 95% range includes both lower and higher spending." | Full comparison |

**The campaign assessment policy is unresolved.** Numeric floors, the estimator and the critical value await the statistical review (protocol §10). Until a policy is configured, a complete window with adequate data reports `assessment_policy_pending`.

`insufficient_data` is used only for **structural** impossibility: fewer than 2 customers, or zero purchasers, in either group. No other threshold is invented. The last three rows apply only once a policy exists.

### 6.3 Page-level
| State | Shows | Recovery |
|---|---|---|
| Loading | "Loading results…" | — |
| No campaigns | "Results appear after your first campaign is created in Klaviyo." | Go to Campaigns |
| Load failed (nothing cached) | "Couldn't load results." | Try again |
| Load failed (results shown) | Persistent banner: "Couldn't refresh results. Showing what was loaded at {time}." | Try again |

### 6.4 Freshness (each checked independently; threshold 24 hours)
| Condition | Message | Recovery |
|---|---|---|
| Last successful sync more than 24h ago | "Store data last synced {relative} ago. Results can't include orders since then." Shown even when the calculation itself is recent — recalculating old data doesn't make it fresh. | Re-sync store |
| No successful sync | "No successful store sync, so results can't be checked against complete order data." | Re-sync store |
| Calculated more than 24h ago | "Last calculated {relative} ago." | Recalculate |
| Figures use an older sync than the active one | "Newer store data is available. These figures still use the sync from {date}." Coverage and freshness are judged against **that** sync, never the newer one. | Recalculate |
| The sync behind the figures is more than 24h old | "The store data behind these figures is over 24 hours old, so recent orders may be missing from this window." | Re-sync store |
| Recalculation failed | "Couldn't recalculate. Showing the result calculated {date}." The old figures keep their original sync: each window's arms are published in one transaction, so a failure leaves the previous result whole. | Try again |
| A window's rows come from different calculations | "This window's stored figures come from different calculations, so they aren't shown. Recalculate to refresh them." No figures, no provenance claim. | Recalculate |

**Recalculation:** figures are recalculated when they are over 24 hours old **or** when the active sync differs from the sync they used. A newer sync never marks an older calculation as fresh or complete.

### 6.5 Repeated exposure (checked per selected window)
The API checks whether any of this campaign's customers were assigned to receive another BeaconAI campaign that was confirmed sent **before this campaign's send or during the selected window**.

- **Found:** "These customers may have been included in other BeaconAI campaigns. This comparison does not isolate this email's effect."
- **Unknown** (another campaign's send time isn't confirmed, so it could fall in the window): "Other BeaconAI campaigns may have reached these customers; their send times aren't confirmed, so this comparison does not isolate this email's effect."
- **None established:** no specific note, and nothing claiming there were none.
- **Always shown:** "Other BeaconAI campaign exposure may not be fully identified." Matching uses recorded customer ids, so a customer known by two ids can be missed. Expanding identity handling is deferred.

### 6.6 Other marketing (always shown)
> "Your other marketing may also affect these results."

The page never claims the held-back group received no BeaconAI campaigns unless the records establish it.

## 7. Program band (Ticket H placement)
Today it shows only the §1 text. Its later states (enrolled / measuring / estimate / unavailable) follow Ticket H and the approved protocol. The band never shows a sum of campaign results.

## 8. Field mapping
| Element | API field | Null handling |
|---|---|---|
| Name | `displayName` (saved) | The play's display name |
| Sent date | `sentAt` — the provider send, only when confirmed | The delivery label replaces it |
| Assigned / held back | `assignment.assigned`, `assignment.heldBack` (counted from `campaign_recipients`) | "—" |
| Klaviyo sent | `delivery.providerSentCount` | "Sent count unavailable" |
| Window dates and progress | `windows[].start`, `.end`, `.complete`, `.daysElapsed` | — |
| Calculated | `windows[].calculatedAt` | "Not calculated yet" |
| Calculated from | `windows[].calculatedFrom` (`syncRunId`, `lastSuccessfulSyncAt`, `ordersCoveredThrough`, `stale`) and `windows[].sourceSuperseded` | No sync recorded: assessment becomes `awaiting_order_data` |
| Sample data | `sampleData` | No banner |
| Last successful sync | `source.lastSuccessfulSyncAt` (the active sync's `publishedAt`) | §6.4, no successful sync |
| Order coverage | `source.ordersCoveredThrough` (the active sync's start time) | Assessment becomes `awaiting_order_data` |
| Assessment | `windows[].assessment.state`, `.reasons[]` | Never inferred in React |
| Group figures | `windows[].assigned` / `windows[].heldBack`: `customers`, `purchasers`, `orders`, `revenue` | Zero only when known |
| Difference / range | `windows[].comparison` — present only when the assessment permits it | Omitted |
| Exposure | `windows[].otherExposure.status` (none / present / unknown), `.customers` | §6.5 |
| Original campaign | `GET /campaigns/:id/original` → frozen `approvedCopy`, `renderedHtml`, `destinationUrl`, `recommendation` | "Not stored for this campaign" |
| Selection | `?campaign=<id>` | An unknown id opens nothing |
| Older campaigns | `GET /results/:shop?limit=N` → `hasMore` | The button appears only when `hasMore` is true |

## 9. Accessibility
- Rows are buttons with `aria-expanded` and `aria-controls`; the detail region is labelled.
- The window selector is a native radio group, so arrow keys work.
- Every status is stated in text; colour appears only on Higher / Lower spending.
- A visible focus ring on every control; table headers use `scope`; the email frame is sandboxed and titled.

## 10. Acceptance
- **Sample data banner:** a seeded demonstration shop (`clean.shop.sample_data`) shows a persistent first-line banner: "Sample data — illustrative results." A screenshot shared without context still carries the label.
- **Seed screenshots** at 1440, 1024 and 390px: measuring, completed (policy pending), insufficient data, stale source / failed load, and an unconfirmed send.
- **Windows:** the row and the detail may show different windows **when each is labelled**. The row always reads "30-day result", and every figure, date and sentence in the detail follows the selected window.
- **Wording:** no page uses "received" or "sent" for an assignment count.
