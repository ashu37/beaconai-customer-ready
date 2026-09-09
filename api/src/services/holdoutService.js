// Holdout assignment.
//
// A holdout is the only way to say what a campaign actually EARNED rather than
// what happened after it. Without one, "these customers bought $X" is just the
// revenue those customers would partly have produced anyway.
//
// The assignment is GLOBAL and STABLE: a customer's bucket depends only on
// (shop_domain, customer_id), so the same ~10% of customers are held out of
// EVERY campaign. That is what makes the program-level comparison valid — over a
// quarter, the held-out group is a clean counterfactual for the treated group.
//
// It is deliberately NOT random per campaign. Independent per-campaign holdouts
// would give clean per-campaign reads but no program number, because a customer
// held out of one campaign and treated in the next is in both groups.

const crypto = require("crypto");

// 0-99, uniform, deterministic. sha256 rather than a cheap hash because the
// bucket has to be stable forever — changing the function silently reassigns
// every customer and invalidates every measurement taken before the change.
function bucketFor(shopDomain, customerId) {
  const digest = crypto.createHash("sha256")
    .update(`${shopDomain}:${customerId}`)
    .digest();
  return digest.readUInt32BE(0) % 100;
}

// Split resolved recipients into the arm that receives the campaign and the arm
// held back to measure it.
//
// There is deliberately NO minimum-audience floor. Skipping the holdout on small
// audiences would be tempting — 10% of 28 people buys no statistical power and
// costs real reach — but it would put held-out customers into the treated group
// for those sends, contaminating the quarter-level comparison that is the whole
// point of a global holdout. Consistency is worth more than the reach.
function splitAudience(shopDomain, recipients = [], holdoutPct = 0.1) {
  const pct = Number(holdoutPct);
  const threshold = Number.isFinite(pct) ? Math.round(Math.max(0, Math.min(1, pct)) * 100) : 10;

  const treated = [];
  const holdout = [];
  for (const recipient of recipients) {
    const id = recipient?.customerId;
    if (!id) continue;
    // threshold 0 => nobody is held out (holdout switched off for this campaign).
    if (bucketFor(shopDomain, id) < threshold) holdout.push(recipient);
    else treated.push(recipient);
  }

  return { treated, holdout, holdoutPct: threshold / 100 };
}

module.exports = { bucketFor, splitAudience };
