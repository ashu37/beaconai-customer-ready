const axios = require("axios");
const { config } = require("../config");
const { query } = require("../db");

function createKlaviyoClient(privateKey) {
  if (!privateKey) {
    throw new Error("Klaviyo private key is required");
  }

  return axios.create({
    baseURL: "https://a.klaviyo.com/api",
    timeout: 30000,
    headers: {
      Authorization: `Klaviyo-API-Key ${privateKey}`,
      accept: "application/json",
      "content-type": "application/json",
      revision: config.klaviyo.revision,
    },
  });
}

async function testKlaviyo(privateKey) {
  const client = createKlaviyoClient(privateKey);
  const response = await client.get("/accounts");
  return response.data;
}

async function getKlaviyoLists(privateKey) {
  const client = createKlaviyoClient(privateKey);
  const response = await client.get("/lists");
  return response.data;
}

async function getKlaviyoProfiles(privateKey) {
  const client = createKlaviyoClient(privateKey);
  const response = await client.get("/profiles");
  return response.data;
}

async function getKlaviyoTemplates(privateKey) {
  if (!privateKey) {
    return {
      data: [],
      mock: true,
    };
  }

  const client = createKlaviyoClient(privateKey);
  const response = await client.get("/templates");
  return response.data;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function campaignTemplateName(campaign) {
  return campaign.klaviyo?.template_name
    || campaign.templateName
    || `BeaconAI - ${campaign.playTitle || campaign.play_name || "Campaign"}`;
}

function campaignHtml(campaign) {
  if (campaign.email?.html) return campaign.email.html;

  return `
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f7f5f0;font-family:Arial,sans-serif;color:#151515;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f7f5f0;padding:24px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border:1px solid #ded7cc;">
            <tr>
              <td style="padding:32px;">
                <p style="margin:0 0 12px;color:#f08a24;font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:1.5px;">BeaconAI</p>
                <h1 style="margin:0 0 16px;font-size:30px;line-height:1.15;color:#111111;">${escapeHtml(campaign.bodyH2 || campaign.subject || campaign.playTitle)}</h1>
                <p style="margin:0 0 16px;font-size:16px;line-height:1.55;color:#3f3a34;">${escapeHtml(campaign.bodyP1 || campaign.previewText)}</p>
                ${campaign.bodyP2 ? `<p style="margin:0 0 24px;font-size:16px;line-height:1.55;color:#3f3a34;">${escapeHtml(campaign.bodyP2)}</p>` : ""}
                <a href="{{ organization.url|default:'#' }}" style="display:inline-block;background:#f08a24;color:#111111;text-decoration:none;font-weight:bold;padding:14px 20px;border-radius:4px;">${escapeHtml(campaign.cta || "Shop now")}</a>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>`;
}

async function createTemplate(privateKey, campaign) {
  const client = createKlaviyoClient(privateKey);

  const payload = {
    data: {
      type: "template",
      attributes: {
        name: campaignTemplateName(campaign),
        editor_type: "CODE",
        html: campaignHtml(campaign),
      },
    },
  };

  const response = await client.post("/templates", payload);
  return response.data;
}

async function saveKlaviyoAsset({ shopDomain, assetType, externalId, payload }) {
  const result = await query(
    `
    INSERT INTO clean.klaviyo_assets (shop_domain, asset_type, external_id, payload)
    VALUES ($1, $2, $3, $4)
    RETURNING *
    `,
    [shopDomain || null, assetType, externalId || null, JSON.stringify(payload)]
  );

  return result.rows[0];
}

module.exports = {
  createKlaviyoClient,
  testKlaviyo,
  getKlaviyoLists,
  getKlaviyoProfiles,
  getKlaviyoTemplates,
  createTemplate,
  saveKlaviyoAsset,
};
