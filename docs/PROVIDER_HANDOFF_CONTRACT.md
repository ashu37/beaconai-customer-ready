# Provider handoff and delivery contract (Ticket D)

Status: proposed by the engineer, September 10, 2026. Written before implementation so the
states are decided rather than discovered. Consumed by Ticket C-UI's review and status screens.

The rule everything here follows: **BeaconAI may only assert what the provider has confirmed.**
A local write, a template id, or a request that was sent are not evidence that a campaign exists
or that anything was delivered. Where we do not know, the contract has a value for not knowing,
and that value is never rendered as zero.

## 1. Durable states

`campaign.delivery_state`, persisted, one of:

| State | Means | Reached by |
| --- | --- | --- |
| `not_started` | No handoff attempted. | Default. |
| `creating` | A handoff holds the campaign; a provider call may be in flight. | Reservation taken (`handoff_reserved_at`). |
| `created` | The provider **confirmed** a campaign exists, and we hold its id. | Provider returned a campaign id. |
| `awaiting_send` | Draft exists; no confirmed send. | `created`, once reconciliation has run at least once and found no send. |
| `scheduled` | Provider reports a scheduled send. Still not sent. | Reconciliation. |
| `sent` | Provider reports the send **executed**. | Reconciliation only. |
| `failed` | The attempt failed and the provider is known not to hold a campaign. | Proven pre-creation failure. |
| `uncertain` | We could not confirm whether the provider created anything. | Any failure that is not proven pre-creation. |

Only reconciliation may write `sent`, `scheduled` or `awaiting_send`. Nothing local may.

`uncertain` is a first-class outcome, not an error state to be cleared by retrying. It exists
because a request that times out may still have been executed, and a duplicate campaign is worse
than a stalled one.

### Permitted transitions

```
not_started → creating
creating    → created | failed | uncertain
failed      → creating              (retry is safe: nothing exists there)
uncertain   → created | failed      (ONLY via reconciliation, never via retry)
created     → awaiting_send → scheduled → sent
```

`uncertain → creating` is not permitted. Neither is any transition out of `sent`.

## 2. Provider reference and link

| Field | Type | Rule |
| --- | --- | --- |
| `provider` | text | `"klaviyo"` for the pilot. |
| `provider_campaign_id` | text, nullable | The provider's campaign id. Null until confirmed. A template or list id must never be stored here. |
| `provider_campaign_url` | text, nullable | A deep link, stored **only** when derived from a provider response. |
| `provider_account_url` | text, nullable | Fallback entry point. |

We never construct a campaign URL from an id and a guessed account path. The one address we do
build is `https://www.klaviyo.com/campaign/{provider_campaign_id}/wizard/1`, from an id Klaviyo
returned at handoff: it carries no account path, and it was checked against a real account
(2026-09-15) — it opens that draft, and a wrong id shows Klaviyo's "Not Found" page. It only opens
in a browser signed in to that Klaviyo account, so the campaign's exact name is always shown beside
it. Without a stored link the UI shows "Draft created. In Klaviyo, open Campaigns and find the
draft named [campaign name]". A link that 404s in front of a merchant mid-handoff is worse than no
link.

## 2a. Handoff modes

`handoff_mode` records how a campaign reached Klaviyo. Null until handoff, and for campaigns handed
off before modes existed (those were all rendered emails).

| Mode | What BeaconAI creates | Preview binding | Recorded at freeze |
| --- | --- | --- | --- |
| `rendered_email` (default when absent) | Template from the store's approved design, list, campaign, template assigned | Required: `expectedTemplateVersion` and `expectedRenderFingerprint` must match the render | Approved copy, rendered HTML, template version |
| `klaviyo_design` | List and campaign with subject, preview text and sender. No template. | None: nothing BeaconAI renders is sent | The suggested copy (the handoff suggestion), no HTML |

Everything else is shared and unchanged by mode: store authorization, verified input provenance, the
revision reservation, the saved holdout split and recorded recipients, duplicate protection, the
`uncertain` state after a possible creation, and the provider campaign id. In `klaviyo_design` the
merchant chooses a template, finishes the email and sends it in Klaviyo; BeaconAI never updates the
draft after creating it, and its stored copy describes what was suggested, not what was sent.

## 3. Status checks

| Field | Type | Rule |
| --- | --- | --- |
| `last_checked_at` | timestamptz, nullable | When reconciliation last **completed**, successfully or not. |
| `last_check_ok` | boolean, nullable | Whether that check reached the provider. |
| `last_check_error` | text, nullable | Why it did not. |
| `last_confirmed_at` | timestamptz, nullable | When the provider last confirmed the state now displayed. |

`last_checked_at` and `last_confirmed_at` are different questions: "when did we last look" and
"when did the provider last tell us this". A failed check updates the first and not the second, so
a stale state cannot pass as fresh because someone retried.

Null `last_checked_at` renders "Not checked yet", never "just now".

## 4. Send confirmation

| Field | Type | Rule |
| --- | --- | --- |
| `provider_sent_at` | timestamptz, nullable | The provider's send time. Never `NOW()`, never `sent_at` written locally at approval. |
| `provider_sent_count` | integer, **nullable** | Recipients the provider reports. |
| `provider_send_status` | text, nullable | The provider's own status string, kept verbatim for audit. |

`provider_sent_count` is nullable **on purpose**. Klaviyo may not report a count, or may report it
late. Null means "not known", and the UI shows "Sent count unavailable". It must never be
coalesced to 0: a campaign that sent to 900 people and reported no count is not a campaign that
sent to nobody, and the difference is the whole reason this field is nullable.

The existing `campaigns.sent_at` stays as the local bookkeeping stamp it already is. Measurement
windows move to `provider_sent_at` when present — a window anchored on when someone clicked a
button is not anchored on when the email went out. Where `provider_sent_at` is null, measurement
continues to use `sent_at` and says so.

## 5. Retry and reconciliation

**Retry is permitted only from `failed`,** which is only reached on a proven pre-creation failure —
the request never left us, so nothing can exist at the provider.

From `uncertain` there is no retry. The only way forward is reconciliation:

1. Look up campaigns at the provider matching this campaign's recorded name and window.
2. **One match** → adopt its id, move to `created`, continue normally.
3. **No match** → the provider holds nothing; move to `failed`; retry becomes available.
4. **More than one match** → stay `uncertain` and report the ambiguity. Do not guess. A human
   resolves it.

Reconciliation is idempotent, may run repeatedly, and never creates anything. It is the only
operation permitted to move a campaign out of `uncertain`.

For the pilot the founder triggers reconciliation. A merchant sees the last check time and
"Your pilot contact can refresh this status." No automatic polling — out of scope per Ticket C-UI.

## 6. Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/campaigns/:id/delivery` | The durable state above. Safe to poll from the UI. |
| `POST /api/campaigns/:id/reconcile` | Founder-triggered. Reads the provider, updates state, never creates. |

`POST /klaviyo/campaigns/from-engine` keeps its existing contract and additionally writes
`delivery_state`, the provider reference, and on failure `failed` or `uncertain` per §1.

## 7. What this does not decide

Authentication and tenant isolation (Ticket D, separately), consent and suppression evidence
(D/F), measurement eligibility (F), and any Results presentation (G). This contract covers what we
know about the provider and how confident we are — nothing about who may ask.
