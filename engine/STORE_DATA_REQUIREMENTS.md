# Store Data Requirements for beacon Engine

## Required Files

### 1. Orders Export (REQUIRED)
**File:** Orders CSV from your e-commerce platform (Shopify, WooCommerce, etc.)

**Required Columns:**
- `Created at` / `created_at` / `Order Date` - Order timestamp
- `Name` / `Order ID` / `Order Number` - Unique order identifier  
- `Customer Email` / `customer_email` - Customer email address
- `customer_id` - Customer ID (strongly recommended for accurate segmentation)
- `Subtotal` - Order subtotal before discounts
- `Total Discount` / `discount_amount` - Total discount applied
- `Shipping` / `shipping_amount` - Shipping costs
- `Taxes` / `tax_amount` - Tax amount
- `Total` / `total_amount` - Final order total

**Product Information (at least one method):**
- **Option A:** `Lineitem name` + `Lineitem quantity` + `Lineitem price` - For order-level data
- **Option B:** Multiple rows per order with line item details (auto-detected)
  - `Lineitem name` / `product_title` - Product name
  - `Lineitem quantity` / `quantity` - Quantity ordered
  - `Lineitem price` / `unit_price` - Price per unit
  - `Lineitem discount` / `line_item_discount` - Discount per line item
  - `SKU` / `Variant SKU` - Product identifier (optional)

**Optional but Helpful:**
- `Financial Status` - Payment status
- `Currency` - Order currency (defaults to USD)
- `Billing Name` - Customer name
- `Shipping Country` - Shipping destination

### 2. Inventory Export (OPTIONAL - Recommended)
**File:** Current inventory levels CSV

**Required Columns:**
- `SKU` / `Variant SKU` - Product SKU
- `Available` / `Inventory Quantity` / `On Hand` - Current stock
- `Updated At` / `Last Updated` - When inventory was last updated

**Optional Columns:**
- `Incoming` - Incoming inventory
- `Product Title` / `Title` - Product name
- `Location` - Warehouse location
- `Reorder Point` - Minimum stock threshold

## Important Notes

### Column Name Flexibility
✅ **Attribute names are very flexible!** Our system automatically maps common variations:
- `Created at` = `created_at` = `Order Date` = `Date`
- `Customer Email` = `customer_email` = `Email`  
- `Total Discount` = `discount_amount` = `Discounts`
- `SKU` = `Variant SKU` = `Product SKU`
- `Lineitem name` = `product_title` = `Product Name`
- `Lineitem quantity` = `quantity` = `Qty`
- `Lineitem price` = `unit_price` = `Price`
- `Name` = `order_id` = `Order Number`

⚠️ **Important:** The `customer_id` field should be preserved exactly as provided - it's critical for accurate customer segmentation and targeting.

### Export Instructions
1. **Include ALL orders** - Don't filter out refunds, returns, or test orders
2. **Use UTF-8 encoding** when exporting CSV files
3. **Keep original column headers** from your platform (we'll map them automatically)
4. **Export at least 90 days** of recent orders (6+ months preferred for seasonal patterns)
5. **Include raw data** - No pre-calculations or manual filtering needed

### Data Quality Guidelines
For optimal analysis results, ensure:

⚠️ **Critical for Statistical Accuracy:**
- Remove test/placeholder product names (e.g., "Test Product", "Sample Item")
- Verify date formats are consistent (YYYY-MM-DD HH:MM:SS preferred)
- Check for extreme AOV outliers that might skew analysis
- Ensure customer identifiers are consistent across orders

✅ **Recommended:**
- Orders should span recent time periods (avoid exports with 3+ year old orders only)
- Include customer contact information for segmentation accuracy
- Maintain consistent currency formatting
- Remove internal test orders before export

### File Format Options

**Orders can be provided in two formats:**

**Format 1: One row per order**
```csv
Name,Created at,Customer Email,customer_id,Subtotal,Total Discount,Lineitem name,Lineitem quantity,Lineitem price
#1001,2024-01-15,customer@email.com,CUST-123,50.00,5.00,Serum Pro,1,50.00
#1002,2024-01-16,another@email.com,CUST-456,75.00,0.00,Moisturizer,2,37.50
```

**Format 2: Multiple rows per order (line items) - RECOMMENDED**
```csv
Name,Created at,Customer Email,customer_id,Subtotal,Total Discount,Lineitem name,Lineitem quantity,Lineitem price,SKU
#1001,2024-01-15,customer@email.com,CUST-123,50.00,5.00,Serum Pro,1,45.00,SER-001
#1001,2024-01-15,customer@email.com,CUST-123,50.00,5.00,Cleanser,1,10.00,CLN-002  
#1002,2024-01-16,another@email.com,CUST-456,75.00,0.00,Moisturizer,2,37.50,MOI-003
```

*Our system automatically detects which format you're using.*

## Business Context Questions

Please also provide:
- **Gross margin %** (typical: 70%)
- **Inventory lead time** (days to restock, typical: 14 days)
- **Peak season months** (e.g., November, December)
- **Marketing channel preferences** (email, SMS limits)
- **Discount policy limits** (maximum discount %)

## Data Privacy & Security

- All data is processed securely and used only for analytics
- No customer data is stored permanently
- Reports contain only aggregated insights, not individual customer information
- Data is automatically deleted after analysis completion

## Troubleshooting Common Issues

### Revenue Calculations Showing $0
If your growth projections show $0 revenue, check:
1. **Data Quality**: Remove test products and extreme price outliers
2. **Date Range**: Ensure recent data (within 6 months) for statistical significance  
3. **Customer Data**: Verify `customer_id` or `Customer Email` is populated
4. **Sample Size**: At least 100+ orders recommended for meaningful analysis

### Segmentation Issues
If customer segments are empty or show "nan":
1. **Customer ID**: Ensure `customer_id` column is included and populated
2. **Email Consistency**: Check for consistent email formatting across orders
3. **Data Completeness**: Verify customer information isn't missing for large portions of orders

### Low Statistical Significance
Actions may be classified as "pilots" or "watchlist" due to:
1. **Small Sample Size**: Need sufficient order volume for statistical power
2. **Data Quality Issues**: Clean test data and outliers affect significance tests
3. **Short Time Windows**: Longer historical data improves statistical confidence

## Support

If you have questions about:
- Which export options to use in your platform
- Column mapping for unusual field names  
- File format or data quality issues
- Revenue calculation troubleshooting

Contact: [Your support contact information]

---

**Ready to get started?** Export your orders CSV and optionally your inventory CSV, then upload them to begin receiving personalized growth recommendations.