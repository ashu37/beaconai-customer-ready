const { query } = require("../db");

function json(value) {
  return value == null ? null : JSON.stringify(value);
}

async function saveRawShopifyData(shopDomain, data) {
  for (const [resourceType, payload] of Object.entries(data)) {
    await query(
      `
      INSERT INTO raw.shopify_events (shop_domain, resource_type, payload)
      VALUES ($1, $2, $3)
      `,
      [shopDomain, resourceType, json(payload)]
    );
  }
}

async function upsertShop(shopDomain, shop) {
  await query(
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

async function upsertCustomers(shopDomain, customers) {
  for (const customer of customers || []) {
    await query(
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

async function upsertProducts(shopDomain, products) {
  for (const product of products || []) {
    await query(
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
      await query(
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

async function upsertOrders(shopDomain, orders) {
  for (const order of orders || []) {
    await query(
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
      await query(
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

    await upsertRefundsFromOrder(shopDomain, order);
  }
}

async function upsertRefundsFromOrder(shopDomain, order) {
  for (const refund of order.refunds || []) {
    const transactionAmount = (refund.transactions || []).reduce(
      (sum, txn) => sum + Number(txn.amount || 0),
      0
    );

    for (const refundItem of refund.refund_line_items || []) {
      await query(
        `
        INSERT INTO clean.refunds
        (shop_domain, order_id, created_at, line_item_id, quantity, transaction_amount, raw)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        `,
        [
          shopDomain,
          String(order.id),
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

async function upsertAllShopifyData(shopDomain, data) {
  await upsertShop(shopDomain, data.shop);
  await upsertProducts(shopDomain, data.products);
  await upsertCustomers(shopDomain, data.customers);
  await upsertOrders(shopDomain, data.orders);
}

async function getEngineInput(shopDomain) {
  const [shop, orders, orderLineItems, customers, products, productVariants, refunds] =
    await Promise.all([
      query(`SELECT * FROM clean.shop WHERE shop_domain = $1`, [shopDomain]),
      query(
        `SELECT clean.orders.*, clean.orders.created_at AS shopify_order_created_at
         FROM clean.orders
         WHERE shop_domain = $1
         ORDER BY created_at DESC`,
        [shopDomain]
      ),
      query(`SELECT * FROM clean.order_line_items WHERE shop_domain = $1`, [shopDomain]),
      query(`SELECT * FROM clean.customers WHERE shop_domain = $1`, [shopDomain]),
      query(`SELECT * FROM clean.products WHERE shop_domain = $1 AND status = 'active'`, [shopDomain]),
      query(
        `SELECT pv.*
         FROM clean.product_variants pv
         JOIN clean.products p
           ON p.shop_domain = pv.shop_domain
          AND p.id = pv.product_id
         WHERE pv.shop_domain = $1
           AND p.status = 'active'`,
        [shopDomain]
      ),
      query(`SELECT * FROM clean.refunds WHERE shop_domain = $1`, [shopDomain]),
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

module.exports = {
  saveRawShopifyData,
  upsertAllShopifyData,
  getEngineInput,
};
