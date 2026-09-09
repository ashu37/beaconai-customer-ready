// The ONE renderer.
//
// Preview and the provider draft must be the same bytes, so they come from the
// same function called once. Rendering twice — once for the merchant to look at,
// once for what actually gets sent — is how a merchant approves an email that is
// not the email their customers receive.
//
// A shell is trusted markup reviewed by the founder. Slot VALUES are not: they
// carry model-written copy, merchant edits and product URLs, so every one is
// escaped or validated on the way in.

// Deliberately NOT `{{ }}` or `{% %}`. Those are Klaviyo's, and the shell has to
// be able to carry `{% unsubscribe %}` and `{{ organization.url }}` through to
// the provider untouched. A separate marker means slot substitution can never
// consume a provider tag, and a provider tag can never be mistaken for a slot.
const SLOT_PATTERN = /\[\[slot:([a-z0-9_]+)\]\]/gi;

const TEXT_SLOTS = new Set([
  "brand_name", "headline", "body", "support_copy", "cta_text",
  "product_title", "footer_text", "preview_text",
]);
const URL_SLOTS = new Set(["cta_url", "product_image_url", "logo_url"]);

// Provider syntax the shell may contain and the renderer must leave alone.
const REQUIRED_PROVIDER_TAGS = [/\{%\s*unsubscribe\s*%\}/i];

class BrandTemplateInvalid extends Error {
  constructor(problems) {
    super(`This email shell cannot be used: ${problems.join("; ")}`);
    this.name = "BrandTemplateInvalid";
    this.statusCode = 400;
    this.problems = problems;
  }
}

class BrandSetupRequired extends Error {
  constructor(shopDomain) {
    super(
      `No approved email shell is configured for ${shopDomain}. ` +
      `Configure and approve one before previewing or sending.`
    );
    this.name = "BrandSetupRequired";
    this.code = "brand_setup_required";
    this.statusCode = 409;
    this.shopDomain = shopDomain;
  }
}

class SlotValueRejected extends Error {
  constructor(slot, reason) {
    super(`The "${slot}" value was rejected: ${reason}`);
    this.name = "SlotValueRejected";
    this.statusCode = 400;
    this.slot = slot;
    this.reason = reason;
  }
}

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// Only absolute http(s). Rejected rather than silently blanked: a CTA that
// quietly loses its destination sends an email with a dead button, and the
// merchant would have approved it without knowing.
function safeUrl(value, slot) {
  const raw = String(value == null ? "" : value).trim();
  if (!raw) return "";
  let parsed;
  try {
    parsed = new URL(raw);
  } catch (_) {
    throw new SlotValueRejected(slot, "it is not a valid absolute URL");
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new SlotValueRejected(slot, `"${parsed.protocol}" links are not allowed in email`);
  }
  return escapeHtml(parsed.toString());
}

/**
 * Check a shell before it is ever stored. The founder reviews the markup; this
 * checks the things review reliably misses.
 */
function validateShell(html, { requiredSlots = ["headline", "body", "cta_text", "cta_url"] } = {}) {
  const problems = [];
  const source = String(html || "");

  if (!source.trim()) problems.push("it is empty");
  if (/<script\b/i.test(source)) problems.push("it contains a <script> tag, which email clients strip and providers reject");
  if (/\son[a-z]+\s*=/i.test(source)) problems.push("it contains an inline event handler attribute");

  const present = new Set();
  for (const match of source.matchAll(SLOT_PATTERN)) present.add(match[1].toLowerCase());

  for (const slot of requiredSlots) {
    if (!present.has(slot)) problems.push(`it has no [[slot:${slot}]] placeholder`);
  }
  for (const slot of present) {
    if (!TEXT_SLOTS.has(slot) && !URL_SLOTS.has(slot)) {
      problems.push(`[[slot:${slot}]] is not a slot this renderer knows how to fill`);
    }
  }

  // An email a merchant cannot unsubscribe from is not one this product sends.
  // Checked here rather than trusted to review, because it is invisible in a
  // rendered preview.
  if (!REQUIRED_PROVIDER_TAGS.some((tag) => tag.test(source))) {
    problems.push("it has no {% unsubscribe %} tag");
  }

  if (problems.length) throw new BrandTemplateInvalid(problems);
  return { slots: [...present].sort() };
}

/**
 * Fill a shell. Returns the exact bytes that go to both the preview and the
 * provider.
 *
 * An unfilled slot renders empty rather than leaving the placeholder visible —
 * `[[slot:support_copy]]` reaching a customer's inbox is worse than an absent
 * paragraph. Required slots are checked at validation time instead, so a shell
 * cannot be stored without them.
 */
function renderBrandEmail(template, values = {}) {
  if (!template || !template.html) throw new BrandSetupRequired(template?.shopDomain || "this shop");

  return String(template.html).replace(SLOT_PATTERN, (_, rawName) => {
    const slot = String(rawName).toLowerCase();
    const value = values[slot];
    if (URL_SLOTS.has(slot)) return safeUrl(value, slot);
    if (TEXT_SLOTS.has(slot)) return escapeHtml(value);
    // Unknown slots cannot appear in a stored shell (validateShell refuses
    // them), so reaching here means the shell bypassed validation.
    throw new SlotValueRejected(slot, "it is not a slot this renderer knows how to fill");
  });
}

// The campaign draft, flattened into slot values. One place, so preview and
// handoff cannot disagree about what goes where.
function slotValuesForCampaign(campaign = {}, brand = {}) {
  const featured = campaign.featuredProduct || campaign.featured_product || null;
  return {
    brand_name: brand.brandName || campaign.brandContext?.brandName || "",
    headline: campaign.bodyH2 || campaign.subject || campaign.playTitle || "",
    preview_text: campaign.previewText || "",
    body: campaign.bodyP1 || campaign.previewText || "",
    support_copy: campaign.bodyP2 || "",
    cta_text: campaign.cta || "Shop now",
    cta_url: campaign.ctaUrl || brand.ctaUrl || "",
    product_title: featured?.title || "",
    product_image_url: featured?.imageUrl || "",
    logo_url: brand.logoUrl || "",
    footer_text: brand.footerText || "",
  };
}

module.exports = {
  BrandSetupRequired,
  BrandTemplateInvalid,
  SlotValueRejected,
  SLOT_PATTERN,
  TEXT_SLOTS,
  URL_SLOTS,
  escapeHtml,
  renderBrandEmail,
  safeUrl,
  slotValuesForCampaign,
  validateShell,
};

// A starting shell built from a merchant's own colours, logo and footer.
//
// This is the "small parameterized template" half of the pilot approach: a
// founder either pastes the merchant's approved HTML, or fills these few values
// and reviews the result. It is a STARTING POINT that gets stored as a normal
// version and reviewed like any other — not a live theme, and not applied
// automatically to anyone.
//
// Table-based layout with inline styles, because that is what email clients
// render. Fonts are stacks ending in a generic family: webfonts do not load in
// most clients, so naming one without a fallback silently yields Times.
function buildStarterShell({
  accentColor = "#1f2933",
  backgroundColor = "#f4f4f4",
  bodyColor = "#333333",
  fontStack = "Helvetica, Arial, sans-serif",
  buttonTextColor = "#ffffff",
  showLogo = true,
} = {}) {
  const logoBlock = showLogo
    ? `<tr><td style="padding:20px 24px 0;"><img src="[[slot:logo_url]]" alt="[[slot:brand_name]]" style="max-height:40px;width:auto;border:0;" /></td></tr>`
    : "";

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>[[slot:headline]]</title>
  </head>
  <body style="margin:0;padding:0;background:${backgroundColor};font-family:${fontStack};color:${bodyColor};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">[[slot:preview_text]]</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:${backgroundColor};padding:16px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;">
            ${logoBlock}
            <tr>
              <td style="padding:24px;">
                <h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;color:${accentColor};font-family:${fontStack};">[[slot:headline]]</h1>
                <p style="margin:0 0 16px;font-size:16px;line-height:1.55;color:${bodyColor};font-family:${fontStack};">[[slot:body]]</p>
                <p style="margin:0 0 24px;font-size:16px;line-height:1.55;color:${bodyColor};font-family:${fontStack};">[[slot:support_copy]]</p>
                <div style="text-align:center;margin:0 0 20px;">
                  <img src="[[slot:product_image_url]]" alt="[[slot:product_title]]" style="max-width:260px;width:100%;height:auto;border:0;" />
                </div>
                <a href="[[slot:cta_url]]" style="display:inline-block;background:${accentColor};color:${buttonTextColor};text-decoration:none;font-weight:bold;padding:14px 22px;font-family:${fontStack};">[[slot:cta_text]]</a>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 24px;border-top:1px solid #e4e4e4;">
                <p style="margin:0;font-size:12px;line-height:1.5;color:#777777;font-family:${fontStack};">
                  [[slot:footer_text]]
                  <br />
                  <a href="{% unsubscribe %}" style="color:#777777;">Unsubscribe</a>
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>`;
}

module.exports.buildStarterShell = buildStarterShell;
