# Incident response

One founder, one deployment, pilot merchants. This is written to be usable at
2am by the person who built it, not to satisfy an auditor.

## What counts as an incident

Any of these, whether or not it looks serious yet:

- A credential is exposed — a token in a log, a screenshot, a commit, a chat.
- A merchant's data appears somewhere it should not: another merchant's account,
  a public URL, an email.
- The database or a provider account is accessed by someone who should not have.
- An unexplained change to data: rows missing, campaigns nobody created,
  a send nobody authorised.
- A provider tells you they were breached.

Not an incident: a failed deploy, a bug in the analysis, a campaign the merchant
disliked. Those are ordinary work.

## First 30 minutes — stop it, then understand it

1. **Write down the time and what you saw.** Start a file. Every step below gets
   a line with a timestamp. Memory will not survive the next hour.
2. **Cut access, in this order.**
   - Suspected credential exposure: rotate it now. Shopify client secret and
     Klaviyo credentials in the Partner/Klaviyo consoles; `SESSION_SECRET`,
     `TOKEN_ENCRYPTION_SECRET` (move the old value to
     `TOKEN_ENCRYPTION_SECRET_PREVIOUS` first, or every stored token stops
     decrypting), and `BEACONAI_ADMIN_TOKEN` in Render.
   - Suspected database access: rotate the `beaconai_app` password in Supabase
     and update `DATABASE_URL` in Render.
   - A specific store affected: `disableStore(shopDomain)` refuses its sessions
     and stops its background work without deleting anything.
   - Rotating `SESSION_SECRET` signs every merchant out; that is the intended
     effect, not a side effect.
3. **Do not delete anything.** Logs, rows and Render deploy history are the
   evidence. A rollback that erases the state you are investigating turns a
   contained incident into an unexplainable one.

## Next few hours — establish the facts

- `npm run security:db-check` — the database boundary: roles, grants, policies,
  row-level security. `/api/ready` with the founder token reports the same from
  the running deployment.
- Render logs: what was requested, from where, when. Bodies are not logged and
  query values are redacted, so identify by path and timing.
- Supabase: the Data API's exposed schemas, and the log of connections.
- Shopify Partners and Klaviyo: recent API activity for the affected store.
- Answer, in writing: **which stores, which data, what window, and how do you
  know**. "Probably none" is not an answer; either the evidence shows the scope
  or the scope is unknown, and unknown is what you report.

## Telling people

- **Affected merchants**: within 72 hours of establishing that their data was
  involved, and sooner if they need to act (rotate their own credentials, warn
  their customers). Say what happened, what data, what you have done, and what
  they should do. Do not wait for a complete picture to send the first message —
  send what is established and say when the next update comes.
- **Customers of a merchant** are the merchant's to contact, not BeaconAI's.
  Give the merchant what they need to do it.
- **Providers**: Shopify Partners if the app itself is implicated, since an app
  compromise affects every install.
- If personal data was exposed, there may be a statutory reporting deadline in
  the merchant's jurisdiction — for the EU/UK, 72 hours to the supervisory
  authority. Check before assuming it does not apply.

## Afterwards

Within a week, write down: what happened, what made it possible, what was
changed, and what would have caught it earlier. Add the check that would have
caught it — a test, a startup refusal, an alert. An incident that produces only
an apology will happen again.

## Standing exposures, so they are not rediscovered mid-incident

- One `SHOPIFY_CLIENT_SECRET` per deployment: a compromise of it affects every
  installed store, not one. (Open decision in the hardening plan: per-merchant
  custom apps would narrow this.)
- Klaviyo sends from the merchant's own account, so a BeaconAI compromise cannot
  send email by itself — but it can create drafts and read lists.
- Supabase backups hold deleted rows until they expire.
