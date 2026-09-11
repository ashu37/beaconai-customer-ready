const { pool, query } = require("./db");

async function initSchema() {
  await query(`CREATE SCHEMA IF NOT EXISTS raw;`);
  await query(`CREATE SCHEMA IF NOT EXISTS clean;`);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.connections (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT UNIQUE NOT NULL,
      shopify_access_token TEXT,
      klaviyo_private_key TEXT,
      shopify_scope TEXT,
      klaviyo_access_token TEXT,
      klaviyo_refresh_token TEXT,
      klaviyo_scope TEXT,
      klaviyo_expires_at TIMESTAMP,
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
    );
  `);

  await query(`ALTER TABLE clean.connections ADD COLUMN IF NOT EXISTS shopify_scope TEXT;`);
  await query(`ALTER TABLE clean.connections ADD COLUMN IF NOT EXISTS klaviyo_access_token TEXT;`);
  await query(`ALTER TABLE clean.connections ADD COLUMN IF NOT EXISTS klaviyo_refresh_token TEXT;`);
  await query(`ALTER TABLE clean.connections ADD COLUMN IF NOT EXISTS klaviyo_scope TEXT;`);
  await query(`ALTER TABLE clean.connections ADD COLUMN IF NOT EXISTS klaviyo_expires_at TIMESTAMP;`);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.oauth_states (
      state TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      shop_domain TEXT,
      return_to TEXT,
      created_at TIMESTAMP DEFAULT NOW(),
      expires_at TIMESTAMP NOT NULL
    );
  `);

  // PKCE: the verifier belongs to ONE authorization request, so it lives with
  // that request's state row and dies with it. Stored encrypted like every other
  // secret at rest, even though these rows expire in 15 minutes.
  await query(`ALTER TABLE clean.oauth_states ADD COLUMN IF NOT EXISTS code_verifier TEXT;`);

  await query(`
    CREATE TABLE IF NOT EXISTS raw.shopify_events (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      resource_type TEXT NOT NULL,
      payload JSONB NOT NULL,
      created_at TIMESTAMP DEFAULT NOW()
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS raw.klaviyo_events (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT,
      resource_type TEXT NOT NULL,
      payload JSONB NOT NULL,
      created_at TIMESTAMP DEFAULT NOW()
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.shop (
      shop_domain TEXT PRIMARY KEY,
      iana_timezone TEXT,
      currency TEXT,
      plan_name TEXT,
      raw JSONB,
      updated_at TIMESTAMP DEFAULT NOW()
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.orders (
      id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      name TEXT,
      created_at TIMESTAMP,
      processed_at TIMESTAMP,
      customer_id TEXT,
      email TEXT,
      currency TEXT,
      subtotal_price NUMERIC,
      total_discounts NUMERIC,
      total_price NUMERIC,
      total_tax NUMERIC,
      total_shipping_price_set JSONB,
      financial_status TEXT,
      cancelled_at TIMESTAMP,
      test BOOLEAN,
      tags TEXT,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.order_line_items (
      id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      order_id TEXT NOT NULL,
      product_id TEXT,
      variant_id TEXT,
      sku TEXT,
      title TEXT,
      quantity INTEGER,
      price NUMERIC,
      total_discount NUMERIC,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.customers (
      id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      email TEXT,
      created_at TIMESTAMP,
      state TEXT,
      email_marketing_consent JSONB,
      tags TEXT,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.products (
      id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      title TEXT,
      product_type TEXT,
      tags TEXT,
      status TEXT,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.product_variants (
      id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      product_id TEXT NOT NULL,
      sku TEXT,
      price NUMERIC,
      inventory_item_id TEXT,
      inventory_quantity INTEGER,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.refunds (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      order_id TEXT NOT NULL,
      created_at TIMESTAMP,
      line_item_id TEXT,
      quantity INTEGER,
      transaction_amount NUMERIC,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.klaviyo_assets (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT,
      asset_type TEXT NOT NULL,
      external_id TEXT,
      payload JSONB NOT NULL,
      created_at TIMESTAMP DEFAULT NOW()
    );
  `);

  // Engine runs are immutable: inserted once, never updated — except `narration`,
  // which is written once by the narration pass that follows the same run.
  // The container filesystem the engine writes to is ephemeral on Render, so
  // these rows (not `engine/data/`) are what survives a restart.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.engine_run_snapshots (
      run_id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      store_id TEXT NOT NULL,
      schema_version TEXT,
      engine_run JSONB NOT NULL,
      manifest JSONB,
      narration JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  await query(`
    CREATE INDEX IF NOT EXISTS engine_run_snapshots_latest
      ON clean.engine_run_snapshots (shop_domain, created_at DESC);
  `);

  // Membership is stored whole, as the engine materialized it. An array rather
  // than a row per customer: a 100k audience is ~1.2MB here vs ~100k rows, and
  // it is always read in full at send time.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.engine_audiences (
      run_id TEXT NOT NULL
        REFERENCES clean.engine_run_snapshots(run_id) ON DELETE CASCADE,
      audience_definition_id TEXT NOT NULL,
      play_id TEXT NOT NULL,
      materialization_status TEXT NOT NULL,
      customer_ids TEXT[] NOT NULL DEFAULT '{}',
      PRIMARY KEY (run_id, audience_definition_id)
    );
  `);

  await query(`
    CREATE INDEX IF NOT EXISTS engine_audiences_play
      ON clean.engine_audiences (run_id, play_id);
  `);

  // A campaign is one play the merchant acted on, in one run. Rows outlive the
  // run that produced them: the engine emits a new slate every month, and the
  // record of what was sent has to survive that. Nothing here is ever deleted.
  //
  // Keyed (shop_domain, run_id, play_id) so approving the same play twice
  // updates one row instead of creating a second campaign for the same send.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.campaigns (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      run_id TEXT NOT NULL
        REFERENCES clean.engine_run_snapshots(run_id),
      play_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'draft',
      template_id TEXT,
      copy JSONB,
      holdout_pct NUMERIC(4,3) NOT NULL DEFAULT 0.100,
      audience_size INTEGER,
      holdout_size INTEGER,
      klaviyo_campaign_id TEXT,
      approved_at TIMESTAMPTZ,
      sent_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (shop_domain, run_id, play_id)
    );
  `);

  // What the MERCHANT changed, kept apart from `copy` (what the model wrote).
  // The Copy step's Suggested/Edited badge exists only to tell those apart, and
  // "Restore suggested" works by deleting a merchant key so the field falls back
  // to the agent value. They also have different lifecycles: `copy` is replaced
  // wholesale when the model reruns, `draft_edits` has to survive that untouched.
  await query(`
    ALTER TABLE clean.campaigns
      ADD COLUMN IF NOT EXISTS draft_edits JSONB;
  `);

  await query(`
    CREATE INDEX IF NOT EXISTS campaigns_by_shop
      ON clean.campaigns (shop_domain, created_at DESC);
  `);

  // Ticket C — the per-shop branded email shell.
  //
  // Versioned and append-only. A campaign freezes the template version it
  // rendered with, so a later brand revision must not be able to change what an
  // already-sent email looked like — which means old versions stay readable
  // rather than being edited in place.
  //
  // `html` is a SHELL containing [[slot:name]] placeholders, reviewed by the
  // founder before it is stored. Slot values are escaped at render time; the
  // shell itself is trusted markup and therefore never accepted from a public
  // endpoint.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.brand_email_templates (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      version INTEGER NOT NULL,
      html TEXT NOT NULL,
      slots JSONB NOT NULL DEFAULT '[]'::jsonb,
      brand JSONB NOT NULL DEFAULT '{}'::jsonb,
      source TEXT NOT NULL DEFAULT 'founder_configured',
      approved_at TIMESTAMPTZ,
      approved_by TEXT,
      notes TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (shop_domain, version)
    );
  `);

  await query(`
    CREATE INDEX IF NOT EXISTS brand_email_templates_by_shop
      ON clean.brand_email_templates (shop_domain, version DESC);
  `);

  // Which version a shop currently sends with. Separate from the versions table
  // for the same reason active_sync is separate from sync_runs: "the newest row"
  // and "the one approved for use" are different questions, and only the second
  // may reach a merchant's customers.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.brand_email_active (
      shop_domain TEXT PRIMARY KEY,
      template_id INTEGER NOT NULL REFERENCES clean.brand_email_templates(id),
      activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  // Ticket B — durable campaign revision.
  //
  // A campaign row is the record of what the merchant reviewed and sent. Two
  // things previously made that record unreliable: a later write could silently
  // overwrite a newer one with no way to notice, and the row described a send by
  // POINTING at things that move (the latest run's copy, today's audience) rather
  // than by holding what was actually approved. All columns are additive and
  // nullable — nothing is backfilled, because a value invented for a historical
  // campaign is indistinguishable from one that was really reviewed.
  await query(`
    ALTER TABLE clean.campaigns
      ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1;
  `);

  // The play's merchant-facing name, copied onto the row. The engine emits a new
  // slate each run, so a play that drops out of the latest slate would otherwise
  // leave its campaign nameless in history — a sent campaign the merchant can no
  // longer identify.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS display_name TEXT;`);

  // What was actually approved, frozen at handoff, as opposed to `copy` (what the
  // model most recently wrote) and `draft_edits` (what the merchant is currently
  // typing). Those two keep changing; this must not, because it is the record of
  // the email that went out.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS approved_copy JSONB;`);
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS rendered_html TEXT;`);
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS template_version TEXT;`);

  // The audience as a REFERENCE — (run_id, audience_definition_id) plus counts —
  // not a re-derivation. audience_hash is over the member id list, so a later
  // read can tell whether the audience it resolves is the one that was reviewed.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS audience_ref JSONB;`);
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS audience_hash TEXT;`);

  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;`);

  // Where this campaign's button sends people. Per-campaign because a winback
  // and a restock rarely point at the same place; the shop's brand default
  // covers the common case. Frozen with the rest of the sent record, so the
  // destination in the record is the one that was actually mailed.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS destination_url TEXT;`);

  // Ticket D — durable provider delivery state. See
  // docs/PROVIDER_HANDOFF_CONTRACT.md, which was written before this and is the
  // authority for what each value means.
  //
  // The rule these columns exist to enforce: BeaconAI may only assert what the
  // provider has confirmed. `status` and `sent_at` are local bookkeeping and are
  // not evidence of anything happening at Klaviyo.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS delivery_state TEXT NOT NULL DEFAULT 'not_started';`);
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS provider TEXT;`);
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS provider_campaign_id TEXT;`);
  // Stored ONLY when derived from a provider response. Never constructed from an
  // id and a guessed account path: a link that 404s in front of a merchant
  // mid-handoff is worse than no link.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS provider_campaign_url TEXT;`);

  // The EXACT name sent to the provider at handoff. Reconciliation's only
  // reliable way to find a campaign it has no id for: re-deriving the name later
  // from a stored row produced a different string, so the lookup searched for a
  // campaign that was never created under that name and reported absence.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS provider_campaign_name TEXT;`);

  // "When did we last look" and "when did the provider last tell us this" are
  // different questions. A failed check updates the first and not the second, so
  // a stale state cannot pass as fresh because someone retried.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ;`);
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS last_check_ok BOOLEAN;`);
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS last_check_error TEXT;`);
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS last_confirmed_at TIMESTAMPTZ;`);

  // NULLABLE on purpose. A campaign that sent to 900 people and reported no
  // count is not a campaign that sent to nobody, and coalescing to 0 would make
  // those indistinguishable.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS provider_sent_at TIMESTAMPTZ;`);
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS provider_sent_count INTEGER;`);
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS provider_send_status TEXT;`);

  // Claimed at the START of a handoff, before any provider call. Two
  // simultaneous sends cannot both hold it, which is what stops a duplicate
  // draft being created while the first request is still in flight.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS handoff_reserved_at TIMESTAMPTZ;`);

  // Set at handoff. After this the approved content and audience are immutable:
  // editing them would rewrite the record of an email that has already left.
  await query(`ALTER TABLE clean.campaigns ADD COLUMN IF NOT EXISTS frozen_at TIMESTAMPTZ;`);

  // Which arm each customer landed in. Written at send time and never after —
  // without this row the campaign cannot be measured later, because there is no
  // other record of who was held back.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.campaign_recipients (
      campaign_id INTEGER NOT NULL
        REFERENCES clean.campaigns(id) ON DELETE CASCADE,
      customer_id TEXT NOT NULL,
      arm TEXT NOT NULL,
      PRIMARY KEY (campaign_id, customer_id)
    );
  `);

  await query(`
    CREATE INDEX IF NOT EXISTS campaign_recipients_arm
      ON clean.campaign_recipients (campaign_id, arm);
  `);

  // Ticket F collection. The email a recipient was reached at, so a later
  // analysis can reconcile a person who carries two ids (a Shopify id and an
  // email) instead of treating them as two customers.
  await query(`ALTER TABLE clean.campaign_recipients ADD COLUMN IF NOT EXISTS email TEXT;`);

  // Engine members who never reached the split, and why. They were previously
  // dropped without a trace; a design that needs to know who was excluded
  // cannot recover that later.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.campaign_recipient_exclusions (
      campaign_id INTEGER NOT NULL
        REFERENCES clean.campaigns(id) ON DELETE CASCADE,
      customer_ref TEXT NOT NULL,
      reason TEXT NOT NULL,
      recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (campaign_id, customer_ref)
    );
  `);

  // One row per campaign per window per arm. Recomputed as windows mature, so
  // this is the one table here that is updated rather than append-only.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.campaign_measurements (
      campaign_id INTEGER NOT NULL
        REFERENCES clean.campaigns(id) ON DELETE CASCADE,
      window_days INTEGER NOT NULL,
      arm TEXT NOT NULL,
      n_customers INTEGER NOT NULL,
      n_orders INTEGER NOT NULL,
      revenue NUMERIC(12,2) NOT NULL,
      measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (campaign_id, window_days, arm)
    );
  `);

  // Sum of each customer's squared revenue. Storing this sufficient statistic
  // alongside the sum is what lets the interval be recomputed at read time
  // without re-scanning orders — and an estimate without an interval is the
  // thing this product exists not to publish.
  await query(`
    ALTER TABLE clean.campaign_measurements
      ADD COLUMN IF NOT EXISTS revenue_sq NUMERIC(18,4) NOT NULL DEFAULT 0;
  `);

  // Ticket G: unique purchasers per window and arm, counted separately from
  // orders. Null on rows measured before this existed; those are recomputed.
  await query(`ALTER TABLE clean.campaign_measurements ADD COLUMN IF NOT EXISTS n_purchasers INTEGER;`);

  // The sync a calculation read. A figure is only as current as the store data
  // behind it: when the active sync changes, figures from an older one are
  // recalculated, and until they are they keep saying which sync they used.
  await query(`ALTER TABLE clean.campaign_measurements ADD COLUMN IF NOT EXISTS source_sync_run_id INTEGER;`);

  // Seeded demonstration shops. Results shows a persistent "Sample data" banner
  // for them, so a screenshot shared without context is still labelled.
  await query(`ALTER TABLE clean.shop ADD COLUMN IF NOT EXISTS sample_data BOOLEAN NOT NULL DEFAULT false;`);

  // clean.refunds has no natural key, so before this every re-sync appended a
  // second copy of every refund and doubled the store's refund total. The fix
  // needs three steps, and the first two are what make the third work at all.
  await query(`ALTER TABLE clean.refunds ADD COLUMN IF NOT EXISTS refund_id TEXT;`);

  // 1. Backfill Shopify's own refund id onto rows written before the column
  //    existed. Without this every legacy row keeps refund_id NULL, the
  //    NOT EXISTS guard in shopifyRepository has nothing to match on, and the
  //    very next sync appends yet another copy alongside them.
  await query(`
    UPDATE clean.refunds
       SET refund_id = raw->>'id'
     WHERE refund_id IS NULL
       AND raw ? 'id'
       AND raw->>'id' IS NOT NULL;
  `);

  // 2. Move pre-existing duplicates OUT rather than deleting them. Quarantine
  //    is the non-destructive form of this migration: the rows are still
  //    readable and restorable, they simply stop being counted twice. Keeping
  //    them in place was not an option — a doubled refund total is a number the
  //    merchant would act on.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.refunds_quarantine (
      LIKE clean.refunds INCLUDING DEFAULTS
    );
  `);
  await query(`
    ALTER TABLE clean.refunds_quarantine
      ADD COLUMN IF NOT EXISTS quarantined_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
  `);
  await query(`
    ALTER TABLE clean.refunds_quarantine
      ADD COLUMN IF NOT EXISTS quarantine_reason TEXT;
  `);

  // Keep the earliest row of each (shop, refund, line item) group; quarantine
  // the rest. Rows with no refund_id (Shopify sent no id) are left alone: they
  // cannot be grouped safely, and guessing would be worse than the duplicate.
  const deduped = await query(`
    WITH ranked AS (
      SELECT id,
             row_number() OVER (
               PARTITION BY shop_domain, refund_id, line_item_id
               ORDER BY id ASC
             ) AS copy_number
        FROM clean.refunds
       WHERE refund_id IS NOT NULL
    ),
    extra AS (
      SELECT id FROM ranked WHERE copy_number > 1
    ),
    moved AS (
      INSERT INTO clean.refunds_quarantine
        (id, shop_domain, order_id, created_at, line_item_id, quantity,
         transaction_amount, raw, refund_id, quarantine_reason)
      SELECT r.id, r.shop_domain, r.order_id, r.created_at, r.line_item_id,
             r.quantity, r.transaction_amount, r.raw, r.refund_id,
             'duplicate_from_resync_before_refund_id'
        FROM clean.refunds r
        JOIN extra e ON e.id = r.id
      RETURNING id
    )
    DELETE FROM clean.refunds
     WHERE id IN (SELECT id FROM moved)
    RETURNING id;
  `);

  if (deduped.rowCount > 0) {
    // Loud on purpose: this changes a number the merchant may already have been
    // shown, and the count is what makes it auditable afterwards.
    console.warn(
      `[schema] quarantined ${deduped.rowCount} duplicate refund row(s) into clean.refunds_quarantine ` +
      `(re-sync duplicates predating refund_id). Refund totals for affected shops change accordingly.`
    );
  }

  // 3. Only now can the guard's lookup index exist over clean data.
  await query(`
    CREATE INDEX IF NOT EXISTS refunds_by_refund_id
      ON clean.refunds (shop_domain, refund_id, line_item_id);
  `);

  // One row per attempt to pull a store into the clean tables. The reason this
  // exists: a sync that stops early still returns 200 OK and still leaves rows
  // behind, so "we have data" and "we have the store's data" were previously
  // the same observation. This table is what separates them.
  //
  // status:
  //   running    — fetching or publishing; no claim about completeness yet
  //   failed     — the attempt errored; nothing was published
  //   incomplete — the fetch succeeded but is known-partial (a cap truncated a
  //                resource, or coverage is too short to analyse); NOT published
  //   complete   — fetched whole, validated, and published in one transaction
  //
  // Only `complete` rows are ever published, and only a published row can back
  // an analysis. Rows are never deleted: a failed sync is evidence.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.sync_runs (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      status TEXT NOT NULL,
      provenance TEXT NOT NULL DEFAULT 'verified',
      started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      finished_at TIMESTAMPTZ,
      published_at TIMESTAMPTZ,
      schema_version TEXT,
      requested_limit TEXT,
      resource_manifest JSONB,
      declared_coverage JSONB,
      validation_failures JSONB NOT NULL DEFAULT '[]'::jsonb,
      input_snapshot JSONB,
      input_snapshot_ref TEXT,
      failure_reason TEXT
    );
  `);

  await query(`
    CREATE INDEX IF NOT EXISTS sync_runs_by_shop
      ON clean.sync_runs (shop_domain, started_at DESC);
  `);

  // The active sync pointer: which published sync the clean tables currently
  // represent. Separate from sync_runs so the swap is a single row update
  // inside the publishing transaction, and so "latest attempt" can never be
  // mistaken for "what analysis may read".
  await query(`
    CREATE TABLE IF NOT EXISTS clean.active_sync (
      shop_domain TEXT PRIMARY KEY,
      sync_run_id INTEGER NOT NULL REFERENCES clean.sync_runs(id),
      published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ
    );
  `);

  // Which verified input a briefing was built from. Nullable: runs that predate
  // this column keep a null, which reads as unknown provenance — not as
  // verified. Never backfilled.
  await query(`
    ALTER TABLE clean.engine_run_snapshots
      ADD COLUMN IF NOT EXISTS sync_run_id INTEGER REFERENCES clean.sync_runs(id);
  `);

  // 'verified' | 'fixture' | 'legacy_unverified'. Fixture runs are demo data and
  // must never be mistaken for a merchant's own; legacy runs are the ones whose
  // input nothing vouches for. Existing rows keep a null, which the status API
  // reports as legacy_unverified rather than assuming anything.
  await query(`
    ALTER TABLE clean.engine_run_snapshots
      ADD COLUMN IF NOT EXISTS input_provenance TEXT;
  `);

  // ---------------------------------------------------------------------------
  // Order/customer/refund dates: TIMESTAMP WITHOUT TIME ZONE -> TIMESTAMPTZ
  //
  // WHAT WAS WRONG. These columns were declared without a time zone, and
  // Postgres IGNORES the offset when casting into such a column: both
  // '2025-11-15T16:15:35-08:00' and '2025-11-15T16:15:35Z' stored the identical
  // naked value 2025-11-15 16:15:35. node-postgres then read that back
  // interpreted in the READER's zone, so the same row produced a different
  // instant depending on where the process ran.
  //
  // Why it mattered: engineInputSnapshot projects these columns into the orders
  // CSV the engine buckets into L7/L28/L56/L90 windows, getWeeklySeries buckets
  // them by week, and measurementService compares processed_at against
  // campaign sent_at (already TIMESTAMPTZ) — so a naive value was being
  // silently coerced through the session zone on every attribution query. A
  // whole-offset shift moves an order across a day, week, or window boundary.
  //
  // WHAT THE STORED DIGITS MEAN. The corruption was on READ, not write: the
  // digits are the wall clock exactly as Shopify sent it, which for order
  // timestamps is the SHOP's local time. Nothing was destroyed. But the digits
  // alone cannot say which zone they belong to — a row written from a
  // Z-suffixed string (seeds, fixtures) has UTC digits, one written from a real
  // Shopify payload has shop-local digits. Guessing one rule for both would
  // rewrite real history on an assumption.
  //
  // So the zone is not assumed. It is recovered per row from that row's own
  // `raw` payload, which retains the original offset. Rows whose payload lacks
  // the field cannot be recovered and are FLAGGED rather than quietly rewritten.
  // ATOMIC. Every step below runs on one connection inside one transaction.
  // Postgres has transactional DDL, so the ALTERs roll back with the data.
  //
  // It has to be atomic because the "already migrated?" check keys off the
  // column TYPE. If the process died after the ALTERs but before the
  // re-derivation, the columns would be timestamptz holding placeholder digits,
  // and every subsequent boot would see timestamptz, conclude the migration was
  // done, and skip the re-derivation forever — silent corruption that a restart
  // could never repair.
  const client = await pool.connect();
  let migrationReport = null;
  try {
    await client.query("BEGIN");
    const q = (text, params) => client.query(text, params);

    const needsTimestamptz = await q(`
      SELECT data_type FROM information_schema.columns
       WHERE table_schema = 'clean' AND table_name = 'orders' AND column_name = 'processed_at'
    `);
    const migrating = needsTimestamptz.rows[0]?.data_type === "timestamp without time zone";

    if (migrating) {
      // Back up first. The re-derivation below rewrites values, and a migration
      // that rewrites dates must leave the originals readable.
      await q(`
        CREATE TABLE IF NOT EXISTS clean.orders_date_backup (
          id TEXT PRIMARY KEY,
          shop_domain TEXT,
          created_at_naive TIMESTAMP,
          processed_at_naive TIMESTAMP,
          cancelled_at_naive TIMESTAMP,
          backed_up_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
      `);
      await q(`
        INSERT INTO clean.orders_date_backup
          (id, shop_domain, created_at_naive, processed_at_naive, cancelled_at_naive)
        SELECT id, shop_domain, created_at, processed_at, cancelled_at FROM clean.orders
        ON CONFLICT (id) DO NOTHING;
      `);
    }

    // AT TIME ZONE 'UTC' here is a PLACEHOLDER, not a claim: it preserves the
    // stored digits exactly while giving the column a type that can hold an
    // instant. The re-derivation immediately after is what establishes the true
    // zone; anything it cannot reach keeps these digits and is flagged.
    //
    // Each column is guarded by its CURRENT type, and must be. Run against a
    // column that is already TIMESTAMPTZ, `x AT TIME ZONE 'UTC'` converts it
    // back to a naive UTC wall clock and the assignment then re-reads that in
    // the session's zone — so an unguarded ALTER shifts every date by the
    // server's offset on every single startup. initSchema runs on every boot.
    for (const [table, column] of [
      ["orders", "created_at"],
      ["orders", "processed_at"],
      ["orders", "cancelled_at"],
      ["customers", "created_at"],
      ["refunds", "created_at"],
      ["shop", "updated_at"],
    ]) {
      const current = await q(
        `SELECT data_type FROM information_schema.columns
          WHERE table_schema = 'clean' AND table_name = $1 AND column_name = $2`,
        [table, column]
      );
      if (current.rows[0]?.data_type !== "timestamp without time zone") continue;
      await q(`
        ALTER TABLE clean.${table}
          ALTER COLUMN ${column} TYPE TIMESTAMPTZ
          USING ${column} AT TIME ZONE 'UTC';
      `);
    }

    // Which rows carry a date we can stand behind.
    //   rederived_from_raw     — the offset came from that row's own Shopify payload
    //   unverified_assumed_utc — no payload field; digits kept, read as UTC, flagged
    await q(`ALTER TABLE clean.orders ADD COLUMN IF NOT EXISTS date_provenance TEXT;`);
    await q(`ALTER TABLE clean.customers ADD COLUMN IF NOT EXISTS date_provenance TEXT;`);

    if (migrating) {
      // Ground truth: the row's own payload, offset intact. ::timestamptz honours
      // that offset, so this yields the instant Shopify actually meant.
      const orders = await q(`
        UPDATE clean.orders
           SET created_at   = CASE WHEN raw ? 'created_at'   AND raw->>'created_at'   IS NOT NULL
                                   THEN (raw->>'created_at')::timestamptz   ELSE created_at   END,
               processed_at = CASE WHEN raw ? 'processed_at' AND raw->>'processed_at' IS NOT NULL
                                   THEN (raw->>'processed_at')::timestamptz ELSE processed_at END,
               cancelled_at = CASE WHEN raw ? 'cancelled_at' AND raw->>'cancelled_at' IS NOT NULL
                                   THEN (raw->>'cancelled_at')::timestamptz ELSE cancelled_at END,
               date_provenance = CASE
                 WHEN raw ? 'created_at' AND raw->>'created_at' IS NOT NULL
                   THEN 'rederived_from_raw'
                 ELSE 'unverified_assumed_utc'
               END
         WHERE date_provenance IS NULL
         RETURNING date_provenance;
      `);
      const customers = await q(`
        UPDATE clean.customers
           SET created_at = CASE WHEN raw ? 'created_at' AND raw->>'created_at' IS NOT NULL
                                 THEN (raw->>'created_at')::timestamptz ELSE created_at END,
               date_provenance = CASE
                 WHEN raw ? 'created_at' AND raw->>'created_at' IS NOT NULL
                   THEN 'rederived_from_raw'
                 ELSE 'unverified_assumed_utc'
               END
         WHERE date_provenance IS NULL
         RETURNING date_provenance;
      `);
      await q(`
        UPDATE clean.refunds
           SET created_at = (raw->>'created_at')::timestamptz
         WHERE raw ? 'created_at' AND raw->>'created_at' IS NOT NULL;
      `);

      // Any briefing already produced was computed over the pre-conversion dates,
      // so its window boundaries may have sat a whole offset out. Those runs are
      // not deleted — they stay readable as history — but they stop being
      // sendable until the store is re-analysed, the same rule Ticket A applies
      // to any recommendation whose input cannot be vouched for.
      const affectedRuns = await q(`
        UPDATE clean.engine_run_snapshots
           SET input_provenance = 'predates_timezone_fix'
         WHERE input_provenance = 'verified'
         RETURNING run_id;
      `);

      // The published input snapshot is FROZEN normalized CSV rows, not a view
      // over the clean tables — so converting those tables does not touch it.
      // It still holds the old dates, and getActiveInputSnapshot feeds it
      // straight to the engine, which would run a "verified" analysis on the
      // very values this migration exists to correct.
      //
      // Rewriting a frozen snapshot in place would be re-deriving an artifact
      // whose whole purpose is to be immutable. So instead the active pointer is
      // dropped: the sync_runs rows and their snapshots stay for audit, no sync
      // is active, and the store must re-sync before it can be analysed again.
      const droppedPointers = await q(`DELETE FROM clean.active_sync RETURNING shop_domain;`);

      migrationReport = {
        orders: orders.rowCount,
        customers: customers.rowCount,
        unverified: orders.rows.filter((r) => r.date_provenance === "unverified_assumed_utc").length,
        runs: affectedRuns.rowCount,
        shops: droppedPointers.rowCount,
      };
    }

    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    throw error;
  } finally {
    client.release();
  }

  // Announced only after the transaction actually commits.
  if (migrationReport && (migrationReport.orders || migrationReport.customers || migrationReport.runs)) {
    console.warn(
      `[schema] converted order/customer dates to TIMESTAMPTZ. ` +
      `${migrationReport.orders} order row(s), ${migrationReport.customers} customer row(s); ` +
      `${migrationReport.unverified} order row(s) had no original payload date and are flagged ` +
      `date_provenance='unverified_assumed_utc'. Originals kept in clean.orders_date_backup. ` +
      `${migrationReport.runs} existing engine run(s) were computed over the pre-conversion ` +
      `dates and are now marked 'predates_timezone_fix': readable as history, blocked at handoff. ` +
      `${migrationReport.shops} shop(s) had their active sync pointer cleared — their published ` +
      `input snapshots still hold pre-conversion dates, so each must re-sync before a new analysis.`
    );
  }
}

module.exports = { initSchema };
