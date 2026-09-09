// The normalized engine input, and the one place it is defined.
//
// The engine consumes exactly one thing: an orders CSV. Everything else in
// `getEngineInput()` is used by brand context and the presenter, not by the
// analysis. So "the input the briefing was built from" is these rows — and
// snapshotting them, rather than the clean tables they came from, is what makes
// a run reproducible after the tables move on.
//
// STORAGE DECISION (Ticket A): the snapshot is stored as JSONB on
// clean.sync_runs, following the existing clean.engine_run_snapshots pattern —
// no new object-storage service. Audit: the projection below is ~19 short
// columns per ORDER LINE ITEM, ~200 bytes of JSON each. A pilot merchant at
// 25k line items is ~5MB before TOAST compression, well inside a JSONB column.
// If a later merchant makes that untrue, `input_snapshot_ref` on the same row
// is the escape hatch: point at an artifact, leave the column null.
const SNAPSHOT_SCHEMA_VERSION = "engine-input/1";

// Column order is the CSV's contract with the engine. Do not reorder.
const ORDER_CSV_HEADERS = [
  "Name",
  "Created at",
  "Lineitem name",
  "Lineitem quantity",
  "Lineitem price",
  "Lineitem discount",
  "Financial Status",
  "Fulfillment Status",
  "Subtotal",
  "Total Discount",
  "Shipping",
  "Taxes",
  "Total",
  "Currency",
  "Customer Email",
  "customer_id",
  "Billing Name",
  "Shipping Province",
  "Shipping Country",
];

function csvCell(value) {
  if (value == null) return "";
  const text = String(value);
  if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function money(value, fallback = "0") {
  if (value == null || value === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? String(parsed) : fallback;
}

function dateValue(value) {
  if (!value) return "";
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

function shippingAmount(order) {
  return order.total_shipping_price_set?.shop_money?.amount || order.raw?.total_shipping_price_set?.shop_money?.amount || "0";
}

function customerEmail(order) {
  return order.email || order.raw?.email || order.raw?.customer?.email || "";
}

function customerId(order) {
  return order.customer_id || order.raw?.customer?.id || customerEmail(order);
}

function customerName(order) {
  const first = order.raw?.customer?.first_name || "";
  const last = order.raw?.customer?.last_name || "";
  return `${first} ${last}`.trim();
}

function shippingProvince(order) {
  return order.raw?.shipping_address?.province_code || order.raw?.shipping_address?.province || "";
}

function shippingCountry(order) {
  return order.raw?.shipping_address?.country_code || order.raw?.shipping_address?.country || "";
}

function lineItemsForOrder(input, order) {
  const items = (input.order_line_items || []).filter((item) => item.order_id === order.id);
  if (items.length) return items;
  return [
    {
      title: "Order",
      quantity: 1,
      price: order.subtotal_price || order.total_price || "0",
      total_discount: order.total_discounts || "0",
    },
  ];
}

// Prefer processed_at (the transaction/placement date) over created_at.
// Rationale: Shopify's Admin API assigns created_at = server-now on any order
// created via orderCreate (there is no createdAt input field), so API-imported /
// backdated-seed orders all carry created_at = import time and lose their true
// history. processed_at is settable and reflects when the order was actually
// placed. For organically-created orders the two are the same day, so real
// merchants are unaffected; this only rescues imported history.
function orderCreatedAt(order) {
  return order.processed_at || order.shopify_order_created_at || order.created_at;
}

function orderRows(input) {
  const rows = [];
  for (const order of input.orders || []) {
    for (const item of lineItemsForOrder(input, order)) {
      rows.push({
        "Name": order.name || order.id,
        "Created at": dateValue(orderCreatedAt(order)),
        "Lineitem name": item.title || item.raw?.title || item.raw?.name || "Product",
        "Lineitem quantity": item.quantity || item.raw?.quantity || 1,
        "Lineitem price": money(item.price || item.raw?.price),
        "Lineitem discount": money(item.total_discount || item.raw?.total_discount),
        "Financial Status": order.financial_status || order.raw?.financial_status || "paid",
        "Fulfillment Status": order.raw?.fulfillment_status || "",
        "Subtotal": money(order.subtotal_price),
        "Total Discount": money(order.total_discounts),
        "Shipping": money(shippingAmount(order)),
        "Taxes": money(order.total_tax),
        "Total": money(order.total_price),
        "Currency": order.currency || input.shop?.currency || "USD",
        "Customer Email": customerEmail(order),
        "customer_id": customerId(order),
        "Billing Name": customerName(order),
        "Shipping Province": shippingProvince(order),
        "Shipping Country": shippingCountry(order),
      });
    }
  }
  return rows;
}

// Coverage over a list of date strings. `known: false` when none is parseable:
// unknown coverage is not verified coverage, and must never be reported as zero
// days.
function coverageFromDates(dates) {
  let earliest = null;
  let latest = null;
  let dated = 0;

  for (const value of dates) {
    const parsed = Date.parse(value);
    if (!Number.isFinite(parsed)) continue;
    dated += 1;
    if (earliest == null || parsed < earliest) earliest = parsed;
    if (latest == null || parsed > latest) latest = parsed;
  }

  if (earliest == null) {
    return { known: false, earliestOrderAt: null, latestOrderAt: null, daysCovered: null, datedRows: 0 };
  }

  return {
    known: true,
    earliestOrderAt: new Date(earliest).toISOString(),
    latestOrderAt: new Date(latest).toISOString(),
    // Inclusive span: a single-day store covers 1 day, not 0.
    daysCovered: Math.floor((latest - earliest) / 86400000) + 1,
    datedRows: dated,
  };
}

// Coverage of the PUBLISHED input — every clean row for the shop, which is what
// the engine will read. Computed from the same projection the engine consumes.
function observedCoverage(rows) {
  return coverageFromDates(rows.map((row) => row["Created at"]));
}

// Coverage of what ONE fetch actually reached, straight off the Shopify
// payload. This is deliberately not the same number as observedCoverage: the
// clean tables accumulate, so they hold rows earlier syncs wrote that Shopify
// no longer returns. Validating "did this sync reach far enough back?" against
// the accumulated tables lets residue from a previous sync vouch for a fetch
// that in fact reached nowhere near that far — which is exactly how a
// truncated sync passes for a healthy one.
//
// Same date precedence as the normalized projection (processed_at first), so
// the two numbers are comparable.
function fetchedOrderCoverage(orders) {
  return coverageFromDates(
    (orders || []).map((order) => order.processed_at || order.created_at)
  );
}

// Rows in the published input that fall outside what this fetch reached. They
// are real rows the engine will read, and no current sync vouches for them.
function residualRowsOutsideFetch(rows, fetched) {
  if (!fetched || fetched.known !== true) return null;
  const from = Date.parse(fetched.earliestOrderAt);
  const to = Date.parse(fetched.latestOrderAt);
  let outside = 0;
  for (const row of rows) {
    const at = Date.parse(row["Created at"]);
    if (!Number.isFinite(at)) continue;
    if (at < from || at > to) outside += 1;
  }
  return outside;
}

function buildEngineInputSnapshot(input) {
  const rows = orderRows(input);
  return {
    schemaVersion: SNAPSHOT_SCHEMA_VERSION,
    shop: input?.shop
      ? {
          shop_domain: input.shop.shop_domain || null,
          currency: input.shop.currency || null,
          iana_timezone: input.shop.iana_timezone || null,
          plan_name: input.shop.plan_name || null,
        }
      : null,
    orderRows: rows,
    rowCount: rows.length,
    orderCount: (input.orders || []).length,
    customerCount: (input.customers || []).length,
    productCount: (input.products || []).length,
    coverage: observedCoverage(rows),
  };
}

function snapshotToCsv(snapshot) {
  const lines = [ORDER_CSV_HEADERS.join(",")];
  for (const row of snapshot?.orderRows || []) {
    lines.push(ORDER_CSV_HEADERS.map((header) => csvCell(row[header])).join(","));
  }
  return `${lines.join("\n")}\n`;
}

module.exports = {
  SNAPSHOT_SCHEMA_VERSION,
  ORDER_CSV_HEADERS,
  buildEngineInputSnapshot,
  coverageFromDates,
  fetchedOrderCoverage,
  observedCoverage,
  orderRows,
  residualRowsOutsideFetch,
  snapshotToCsv,
};
