const { query } = require("../db");

function runMockEngine(input) {
  const orderCount = input.orders.length;
  const customerCount = input.customers.length;
  const firstProduct = input.products[0];

  const output = {
    play_id: "winback_30_day_mvp",
    play_name: "30-Day Winback Campaign",
    confidence_label: customerCount >= 5 ? "High" : "Emerging",
    audience: {
      size: Math.max(customerCount, 1),
      description: "Customers with prior purchase history who may be ready for a reorder.",
    },
    opportunity_context: {
      addressable_value: orderCount * 25,
      currency: input.shop?.currency || "USD",
      reason: "Order history exists and can support a simple retention campaign.",
    },
    klaviyo: {
      template_name: "BeaconAI Winback Email",
    },
    email: {
      subject: "Ready for your next order?",
      html: `
        <html>
          <body>
            <h1>Ready for your next order?</h1>
            <p>Hi {{ first_name|default:'there' }},</p>
            <p>We thought you might be ready to restock soon.</p>
            ${
              firstProduct
                ? `<p>A popular item from your store is <strong>${firstProduct.title}</strong>.</p>`
                : ""
            }
            <p><a href="{{ organization.url }}">Shop now</a></p>
          </body>
        </html>
      `,
    },
    sms: "Hi {{ first_name|default:'there' }}, ready to restock? Shop your favorites today.",
  };

  return output;
}

async function saveEngineRun(shopDomain, input, output) {
  const result = await query(
    `
    INSERT INTO clean.engine_runs (shop_domain, input, output)
    VALUES ($1, $2, $3)
    RETURNING *
    `,
    [shopDomain, JSON.stringify(input), JSON.stringify(output)]
  );

  return result.rows[0];
}

module.exports = {
  runMockEngine,
  saveEngineRun,
};
