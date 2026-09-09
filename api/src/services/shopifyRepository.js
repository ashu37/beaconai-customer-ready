const { query } = require("../db");

function json(value) {
  return value == null ? null : JSON.stringify(value);
}

// Every write below goes through an injected executor rather than the pool
// directly. Passing a pg client makes the whole import one transaction, which
// is what lets a failure halfway through an order import roll back instead of
// leaving the clean tables half-updated and readable as if they were whole.
// Omitting it keeps the old autocommit behaviour for read paths and callers
// that have no transaction of their own.
function executor(client) {
  if (!client) return query;
  return (text, params) => client.query(text, params);
}

async function saveRawShopifyData(shopDomain, data, client) {
  const run = executor(client);
  // `resources` is fetch metadata, not a Shopify resource; it belongs on the
  // sync_runs row, not in the raw event log.
  for (const [resourceType, payload] of Object.entries(data)) {
    if (resourceType === "resources") continue;
    await run(
      `
      INSERT INTO raw.shopify_events (shop_domain, resource_type, payload)
      VALUES ($1, $2, $3)
      `,
      [shopDomain, resourceType, json(payload)]
    );
  }
}

async function upsertShop(shopDomain, shop, client) {
  await executor(client)(
    `
    INSERT INTO clean.shop
    (shop_domain, iana_timezone, currency, plan_name, raw, updated_at)
    VALUES ($1, $2, $3, $4, $5, NOW())
    ON CONFLICT (shop_domain) DO UPDATE SET
      iana_timezone = EXCLUDED.iana_timezone,
      currency = EXCLUDED.currency,
      plan_name = EXCLUDED.plan_name,
      raw = EXCLUDED.raw,
      updated_at = NOW()
    `,
    [
      shopDomain,
      shop?.iana_timezone || null,
      shop?.currency || null,
      shop?.plan_name || null,
      json(shop),
    ]
  );
}

async function upsertCustomers(shopDomain, customers, client) {
  const run = executor(client);
  for (const customer of customers || []) {
    await run(
      `
      INSERT INTO clean.customers
      (id, shop_domain, email, created_at, state, email_marketing_consent, tags, raw)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
      ON CONFLICT (id) DO UPDATE SET
        email = EXCLUDED.email,
        created_at = EXCLUDED.created_at,
        state = EXCLUDED.state,
        email_marketing_consent = EXCLUDED.email_marketing_consent,
        tags = EXCLUDED.tags,
        raw = EXCLUDED.raw
      `,
      [
        String(customer.id),
        shopDomain,
        customer.email || null,
        customer.created_at || null,
        customer.state || null,
        json(customer.email_marketing_consent || null),
        customer.tags || null,
        json(customer),
      ]
    );
  }
}

async function upsertProducts(shopDomain, products, client) {
  const run = executor(client);
  for (const product of products || []) {
    await run(
      `
      INSERT INTO clean.products
      (id, shop_domain, title, product_type, tags, status, raw)
      VALUES ($1,$2,$3,$4,$5,$6,$7)
      ON CONFLICT (id) DO UPDATE SET
        title = EXCLUDED.title,
        product_type = EXCLUDED.product_type,
        tags = EXCLUDED.tags,
        status = EXCLUDED.status,
        raw = EXCLUDED.raw
      `,
      [
        String(product.id),
        shopDomain,
        product.title || null,
        product.product_type || null,
        product.tags || null,
        product.status || null,
        json(product),
      ]
    );

    for (const variant of product.variants || []) {
      await run(
        `
        INSERT INTO clean.product_variants
        (id, shop_domain, product_id, sku, price, inventory_item_id, inventory_quantity, raw)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (id) DO UPDATE SET
          sku = EXCLUDED.sku,
          price = EXCLUDED.price,
          inventory_item_id = EXCLUDED.inventory_item_id,
          inventory_quantity = EXCLUDED.inventory_quantity,
          raw = EXCLUDED.raw
        `,
        [
          String(variant.id),
          shopDomain,
          String(product.id),
          variant.sku || null,
          variant.price || null,
          variant.inventory_item_id ? String(variant.inventory_item_id) : null,
          Number.isInteger(variant.inventory_quantity) ? variant.inventory_quantity : null,
          json(variant),
        ]
      );
    }
  }
}

async function upsertOrders(shopDomain, orders, client) {
  const run = executor(client);
  for (const order of orders || []) {
    await run(
      `
      INSERT INTO clean.orders
      (
        id, shop_domain, name, created_at, processed_at, customer_id, email,
        currency, subtotal_price, total_discounts, total_price, total_tax,
        total_shipping_price_set, financial_status, cancelled_at, test, tags, raw
      )
      VALUES
      ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
      ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        created_at = EXCLUDED.created_at,
        processed_at = EXCLUDED.processed_at,
        customer_id = EXCLUDED.customer_id,
        email = EXCLUDED.email,
        currency = EXCLUDED.currency,
        subtotal_price = EXCLUDED.subtotal_price,
        total_discounts = EXCLUDED.total_discounts,
        total_price = EXCLUDED.total_price,
        total_tax = EXCLUDED.total_tax,
        total_shipping_price_set = EXCLUDED.total_shipping_price_set,
        financial_status = EXCLUDED.financial_status,
        cancelled_at = EXCLUDED.cancelled_at,
        test = EXCLUDED.test,
        tags = EXCLUDED.tags,
        raw = EXCLUDED.raw
      `,
      [
        String(order.id),
        shopDomain,
        order.name || null,
        order.created_at || null,
        order.processed_at || null,
        order.customer?.id ? String(order.customer.id) : null,
        order.email || null,
        order.currency || null,
        order.subtotal_price || null,
        order.total_discounts || null,
        order.total_price || null,
        order.total_tax || null,
        json(order.total_shipping_price_set || null),
        order.financial_status || null,
        order.cancelled_at || null,
        Boolean(order.test),
        order.tags || null,
        json(order),
      ]
    );

    for (const item of order.line_items || []) {
      await run(
        `
        INSERT INTO clean.order_line_items
        (id, shop_domain, order_id, product_id, variant_id, sku, title, quantity, price, total_discount, raw)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        ON CONFLICT (id) DO UPDATE SET
          product_id = EXCLUDED.product_id,
          variant_id = EXCLUDED.variant_id,
          sku = EXCLUDED.sku,
          title = EXCLUDED.title,
          quantity = EXCLUDED.quantity,
          price = EXCLUDED.price,
          total_discount = EXCLUDED.total_discount,
          raw = EXCLUDED.raw
        `,
        [
          String(item.id),
          shopDomain,
          String(order.id),
          item.product_id ? String(item.product_id) : null,
          item.variant_id ? String(item.variant_id) : null,
          item.sku || null,
          item.title || null,
          item.quantity || 0,
          item.price || null,
          item.total_discount || null,
          json(item),
        ]
      );
    }

    await upsertRefundsFromOrder(shopDomain, order, client);
  }
}

async function upsertRefundsFromOrder(shopDomain, order, client) {
  const run = executor(client);
  for (const refund of order.refunds || []) {
    const transactionAmount = (refund.transactions || []).reduce(
      (sum, txn) => sum + Number(txn.amount || 0),
      0
    );

    for (const refundItem of refund.refund_line_items || []) {
      // Unlike every other clean table this one has no natural primary key, so
      // a re-sync used to append a second copy of every refund and quietly
      // double the store's refund total. Shopify's own refund id plus the line
      // item it applies to is that key; the NOT EXISTS guard (rather than ON
      // CONFLICT) enforces it without a unique index, which cannot be created
      // over rows an earlier sync already duplicated. Publication is serialized
      // per shop, so there is no concurrent writer to race with.
      await run(
        `
        INSERT INTO clean.refunds
        (shop_domain, order_id, refund_id, created_at, line_item_id, quantity, transaction_amount, raw)
        SELECT $1,$2,$3,$4,$5,$6,$7,$8
        WHERE $3::text IS NULL OR NOT EXISTS (
          SELECT 1 FROM clean.refunds
           WHERE shop_domain = $1 AND refund_id = $3
             AND line_item_id IS NOT DISTINCT FROM $5
        )
        `,
        [
          shopDomain,
          String(order.id),
          refund.id ? String(refund.id) : null,
          refund.created_at || null,
          refundItem.line_item_id ? String(refundItem.line_item_id) : null,
          refundItem.quantity || null,
          transactionAmount || null,
          json(refund),
        ]
      );
    }
  }
}

async function upsertAllShopifyData(shopDomain, data, client) {
  await upsertShop(shopDomain, data.shop, client);
  await upsertProducts(shopDomain, data.products, client);
  await upsertCustomers(shopDomain, data.customers, client);
  await upsertOrders(shopDomain, data.orders, client);
}

/**
 * The engine's input, read out of the clean tables.
 *
 * `generation`, when given, restricts the read to the exact records ONE fetch
 * returned — `{ orderIds, lineItemIds, customerIds, productIds }`. Without it
 * the read is the accumulated tables: everything ever synced, including records
 * Shopify has since stopped returning.
 *
 * That distinction is the whole point. The clean tables are upserted, never
 * pruned, so they are a union of every sync rather than a picture of the store.
 * An order deleted in Shopify, a line item removed from an order, a product
 * archived — all of them stay. Publishing that union as "the verified input"
 * would attach a verification to records this sync never saw, and no date range
 * catches it: a record missing from the middle of the fetched period sits
 * inside the covered dates and looks accounted for.
 *
 * Unscoped reads remain correct for brand context and previews, which want
 * whatever is known about the store rather than one fetch's contents.
 */
async function getEngineInput(shopDomain, client, generation = null) {
  const run = executor(client);
  const ids = (values) => (generation ? (values || []).map(String) : null);
  const orderIds = ids(generation?.orderIds);
  const lineItemIds = ids(generation?.lineItemIds);
  const customerIds = ids(generation?.customerIds);
  const productIds = ids(generation?.productIds);

  const [shop, orders, orderLineItems, customers, products, productVariants, refunds] =
    await Promise.all([
      run(`SELECT * FROM clean.shop WHERE shop_domain = $1`, [shopDomain]),
      run(
        `SELECT clean.orders.*, clean.orders.created_at AS shopify_order_created_at
         FROM clean.orders
         WHERE shop_domain = $1
           AND ($2::text[] IS NULL OR id = ANY($2))
         ORDER BY created_at DESC`,
        [shopDomain, orderIds]
      ),
      run(
        `SELECT * FROM clean.order_line_items
          WHERE shop_domain = $1
            AND ($2::text[] IS NULL OR id = ANY($2))`,
        [shopDomain, lineItemIds]
      ),
      run(
        `SELECT * FROM clean.customers
          WHERE shop_domain = $1
            AND ($2::text[] IS NULL OR id = ANY($2))`,
        [shopDomain, customerIds]
      ),
      run(
        `SELECT * FROM clean.products
          WHERE shop_domain = $1 AND status = 'active'
            AND ($2::text[] IS NULL OR id = ANY($2))`,
        [shopDomain, productIds]
      ),
      run(
        `SELECT pv.*
         FROM clean.product_variants pv
         JOIN clean.products p
           ON p.shop_domain = pv.shop_domain
          AND p.id = pv.product_id
         WHERE pv.shop_domain = $1
           AND p.status = 'active'
           AND ($2::text[] IS NULL OR p.id = ANY($2))`,
        [shopDomain, productIds]
      ),
      run(
        `SELECT * FROM clean.refunds
          WHERE shop_domain = $1
            AND ($2::text[] IS NULL OR order_id = ANY($2))`,
        [shopDomain, orderIds]
      ),
    ]);

  return {
    shop: shop.rows[0] || null,
    orders: orders.rows,
    order_line_items: orderLineItems.rows,
    customers: customers.rows,
    products: products.rows,
    product_variants: productVariants.rows,
    refunds: refunds.rows,
  };
}

/**
 * What the clean tables hold for this shop that the given fetch did NOT return.
 *
 * Membership, not dates. A record absent from the fetch but sitting inside the
 * fetched date range is invisible to any range check, and that is exactly the
 * case that matters: an order cancelled and removed in Shopify last week is
 * still in clean.orders, still dated inside the covered period, and still read
 * by anything that treats the accumulated tables as the store.
 */
async function reconcileGeneration(shopDomain, generation, client) {
  const run = executor(client);
  const orderIds = (generation?.orderIds || []).map(String);
  const lineItemIds = (generation?.lineItemIds || []).map(String);

  const { rows } = await run(
    `SELECT
       (SELECT count(*)::int FROM clean.orders
         WHERE shop_domain = $1 AND NOT (id = ANY($2))) AS orders,
       (SELECT count(*)::int FROM clean.order_line_items
         WHERE shop_domain = $1 AND NOT (id = ANY($3))) AS line_items,
       (SELECT min(COALESCE(processed_at, created_at)) FROM clean.orders
         WHERE shop_domain = $1 AND NOT (id = ANY($2))) AS earliest,
       (SELECT max(COALESCE(processed_at, created_at)) FROM clean.orders
         WHERE shop_domain = $1 AND NOT (id = ANY($2))) AS latest`,
    [shopDomain, orderIds, lineItemIds]
  );

  const row = rows[0];
  return {
    orders: row.orders,
    lineItems: row.line_items,
    earliestOrderAt: row.earliest ? new Date(row.earliest).toISOString() : null,
    latestOrderAt: row.latest ? new Date(row.latest).toISOString() : null,
  };
}

// D6b: weekly order counts + weekly first-time-customer counts for sparklines.
// Read-only. A customer's first-time week is the week of their earliest order.
async function getWeeklySeries(shopDomain, weeks = 12) {
  const span = Math.max(1, Math.min(52, Number(weeks) || 12));
  const result = await query(
    `WITH bounded AS (
       SELECT id, customer_id, created_at,
              date_trunc('week', created_at) AS week
       FROM clean.orders
       WHERE shop_domain = $1
         AND created_at >= date_trunc('week', now()) - ($2::int - 1) * interval '1 week'
         AND (test IS NULL OR test = false)
         AND cancelled_at IS NULL
     ),
     first_order AS (
       SELECT customer_id, MIN(created_at) AS first_at
       FROM clean.orders
       WHERE shop_domain = $1
         AND customer_id IS NOT NULL
         AND (test IS NULL OR test = false)
         AND cancelled_at IS NULL
       GROUP BY customer_id
     )
     SELECT b.week,
            COUNT(*) AS orders,
            COUNT(*) FILTER (
              WHERE b.customer_id IS NOT NULL
                AND fo.first_at = b.created_at
            ) AS new_customers
     FROM bounded b
     LEFT JOIN first_order fo ON fo.customer_id = b.customer_id
     GROUP BY b.week
     ORDER BY b.week ASC`,
    [shopDomain, span]
  );
  return result.rows.map((row) => ({
    week: row.week,
    orders: Number(row.orders) || 0,
    newCustomers: Number(row.new_customers) || 0,
  }));
}

module.exports = {
  saveRawShopifyData,
  upsertAllShopifyData,
  getEngineInput,
  getWeeklySeries,
  reconcileGeneration,
};
