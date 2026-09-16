# BeaconAI privacy notice

Last updated: 2026-09-16. This describes the pilot. It will be rewritten before
general availability, and any merchant in the pilot will be told before it
changes in a way that affects them.

BeaconAI is a Shopify app that reads a store's order history, finds groups of
customers worth emailing, and prepares a campaign draft the merchant finishes
and sends from their own Klaviyo account.

## What is collected

From **Shopify**, once the merchant installs the app and authorises it:

| Data | Why |
| --- | --- |
| Orders: dates, totals, discounts, taxes, currency, status, line items — plus, for now, the rest of Shopify's order payload (see below) | The whole analysis. Purchase timing and value are what the audiences are built from. |
| Customers: internal id, email address, marketing-consent state, tags, the date they were created | To build an audience and to hand a recipient list to Klaviyo. The email is the only contact detail stored. |
| Products and variants: title, type, status, SKU, price | To describe what a campaign is about and to suggest a product to feature. |
| Refunds | So refunded orders do not count as revenue. |
| Shop: time zone, currency, plan | So a store's dates and money are read in its own terms. |

For **customer records**, that list is exhaustive: the email address is the only
contact detail kept, and the name, phone number, addresses and notes that arrive
in Shopify's payload are dropped before the record is written.

For **orders**, it is not. BeaconAI keeps each order's full Shopify payload,
which includes the buyer's name, shipping and billing address, phone number and
IP address. The same details reach two further places: the input snapshot each
analysis is computed from, and a log of the raw payloads every sync received.

This is a known excess rather than a need — the analysis uses the dates, amounts
and line items — and it is being removed. Until it is, this notice says so
rather than claiming otherwise. What already limits it:

- **A redaction reaches all three.** When a customer is redacted, their name,
  address, phone number and email are removed from the order payloads, from
  every stored analysis input, and from the raw sync log. Their orders remain as
  the merchant's business record, under an internal reference that names nobody,
  and a later sync cannot write any of it back.
- **None of it leaves.** No part of an order payload is sent to Anthropic, and
  nothing reaches Klaviyo beyond the email addresses of a campaign's recipients.

From **Klaviyo**, when the merchant connects it: the account's sender addresses
and the identifiers of the lists and campaigns BeaconAI creates.

From the **merchant**: the email address they sign in with through Shopify, and
anything they type into a campaign draft.

## What it is used for

- Computing the analysis and the audiences.
- Producing a campaign draft: subject line, preview text, body and call to
  action, plus the recipient list handed to Klaviyo.
- Measuring what a campaign did, by comparing the group that was emailed with a
  held-back group.

It is not used to train models, not sold, and not shared with other merchants.
A store's data is never mixed with another store's.

## Who else receives it

| Processor | What reaches them | Where |
| --- | --- | --- |
| **Render** | Hosting; the application and its logs. Logs record the request path with query values removed, never request bodies. | United States |
| **Supabase** | The database, encrypted at rest. | United States |
| **Anthropic** | The campaign's subject, audience *description*, brand words, template name and product catalogue — no customer identifiers. The exact fields are captured by a test: `docs/ai-request-fields.json`. | United States |
| **Klaviyo** | The recipient email addresses for a campaign the merchant chose to create, sent to the merchant's own Klaviyo account. | Per the merchant's own Klaviyo agreement |
| **Shopify** | The source of the data; BeaconAI reads, it does not write back. | Per the merchant's own Shopify agreement |

Access tokens are encrypted before they are stored, with a key held only in the
deployment's environment.

## How long it is kept

- While the app is installed, the store's data is kept so the analysis and the
  campaign history stay available.
- After the app is uninstalled, the store's data is deleted within **30 days**,
  or sooner if the merchant asks.
- A deletion also removes the derived records: audiences, recipient lists,
  exclusions and measurements.
- Database backups are held by Supabase on that provider's own schedule and
  expire with it; a deleted store's rows disappear from backups as those expire.
  The current window is recorded in `docs/SECURITY_HARDENING_PLAN.md`.

## A customer's rights

Shopify's privacy webhooks are handled directly:

- **Data request** — what is stored about that customer is gathered and given to
  the merchant, who answers their own customer.
- **Redaction** — everything personal about that customer is removed, everywhere
  it is held: their email address, and every name, phone number and address in
  the stored order payloads, in each analysis input, and in the raw sync log.
  The order itself stays, as the merchant's own business record, attributed to
  an internal reference that names nobody. A later sync cannot put any of it
  back.
- **Shop redaction** — the whole store is erased.

A customer should contact the merchant they bought from. A merchant can ask
BeaconAI directly at the address below.

## Contact

[founder contact address — to be filled in before the notice is published]
