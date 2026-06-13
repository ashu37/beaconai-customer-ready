Pilot Upload Guide

Purpose: Ensure pilot stores provide CSVs that the engine ingests cleanly for KPIs, actions, inventory metrics, and beacon.

Files to upload
- Orders CSV (required): Either order-level export OR line-item-level export.
- Order Items CSV (optional): Only if your Orders CSV is order-level and lacks per-line items.
- Inventory CSV (recommended): Shopify Inventory export to enable inventory-aware actions.

Orders CSV (required)
- Required fields (aliases accepted):
  - Order ID: Name | Order ID | Order Name | Order Number
  - Timestamp: Created at | created_at | Processed at | Date | Order Date
  - Customer Email: Customer Email | customer_email | email
  - Monetary (either set):
    - Preferred: Subtotal and Total Discount
    - Fallback: Total, Shipping, Taxes
- Recommended (enables product features):
  - Line item title: Lineitem name | Product | Product Title
  - Line item quantity: Lineitem quantity | quantity
- Nice to have: Currency, Financial Status, Fulfillment Status

Order Items CSV (optional)
- Only needed if Orders CSV is order-level and you can export line items separately.
- Required fields (aliases accepted):
  - order_id (maps from Name/Order ID)
  - created_at (order timestamp)
  - sku (or Variant SKU)
  - variant_id (optional if sku present)
  - product_title (Lineitem name/Product/Title)
  - quantity
  - line_item_price (unit price)
  - line_item_discount (optional)

Inventory CSV (recommended)
- Accepted aliases:
  - SKU: SKU | Variant SKU (or fallback to Variant ID)
  - Variant ID: Variant ID | Variantid
  - Product title: Product Title | Title | Product
  - Available on-hand: Available | Inventory Quantity | On Hand
  - Incoming: Incoming (optional)
  - Updated timestamp: Updated At | Last Updated | updated_at
  - Optional: Location, Reorder Point

Formatting & coverage
- Encoding: UTF-8 CSV. Dates in any common format (ISO recommended).
- Money values can include $, commas, parentheses for negatives.
- Time range: ≥90 days recommended for reliable L28/L56 metrics and product velocity.

Checklist before upload
- Orders CSV includes Order ID, Created at, Customer Email, and Subtotal + Total Discount (or Total+Shipping+Taxes).
- Orders CSV includes Lineitem name + Lineitem quantity (or provide Order Items CSV).
- Inventory CSV includes SKU (or Variant ID), Available, and Updated At.
- SKUs match between Orders/Items and Inventory where possible.

Sample templates (use these headers/format)
- See: templates/samples/orders_sample.csv
- See: templates/samples/order_items_sample.csv
- See: templates/samples/inventory_sample.csv

