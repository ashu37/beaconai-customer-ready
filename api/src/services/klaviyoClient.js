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

function campaignName(campaign) {
  return `BeaconAI - ${campaign.playTitle || campaign.play_name || campaign.subject || "Campaign"}`;
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

async function createList(privateKey, name) {
  const client = createKlaviyoClient(privateKey);
  const response = await client.post("/lists", {
    data: {
      type: "list",
      attributes: { name },
    },
  });
  return response.data;
}

async function importProfilesToList(privateKey, listId, recipients = []) {
  const client = createKlaviyoClient(privateKey);
  const profiles = recipients
    .filter((recipient) => recipient.email)
    .map((recipient) => ({
      type: "profile",
      attributes: {
        email: recipient.email,
        properties: {
          beaconai_customer_id: recipient.customerId || null,
          beaconai_order_count: recipient.orderCount || 0,
          beaconai_total_revenue: recipient.totalRevenue || 0,
        },
      },
    }));

  if (!profiles.length) {
    throw new Error("Cannot create a Klaviyo audience list without recipient emails.");
  }

  const response = await client.post("/profile-bulk-import-jobs", {
    data: {
      type: "profile-bulk-import-job",
      attributes: {
        profiles: {
          data: profiles,
        },
      },
      relationships: {
        lists: {
          data: [{ type: "list", id: listId }],
        },
      },
    },
  });
  return response.data;
}

async function createCampaign(privateKey, campaign, listId) {
  const client = createKlaviyoClient(privateKey);
  const response = await client.post("/campaigns", {
    data: {
      type: "campaign",
      attributes: {
        name: campaignName(campaign),
        channel: "email",
        send_strategy: {
          method: "manual",
        },
        audiences: {
          included: [listId],
          excluded: [],
        },
        send_options: {
          use_smart_sending: true,
        },
        tracking_options: {
          is_add_utm: true,
          utm_params: [
            { name: "utm_source", value: "beaconai" },
            { name: "utm_medium", value: "email" },
            { name: "utm_campaign", value: campaign.playTitle || campaign.play_name || "beaconai" },
          ],
        },
      },
    },
  });
  return response.data;
}

async function getCampaignMessages(privateKey, campaignId) {
  const client = createKlaviyoClient(privateKey);
  const response = await client.get(`/campaigns/${campaignId}/campaign-messages`);
  return response.data;
}

async function assignTemplateToCampaignMessage(privateKey, messageId, templateId) {
  const client = createKlaviyoClient(privateKey);
  const response = await client.post("/campaign-message-assign-template", {
    data: {
      type: "campaign-message",
      id: messageId,
      relationships: {
        template: {
          data: {
            type: "template",
            id: templateId,
          },
        },
      },
    },
  });
  return response.data;
}

async function createCampaignSendPackage(privateKey, campaign, audience) {
  const template = await createTemplate(privateKey, campaign);
  const templateId = template?.data?.id;
  const list = await createList(privateKey, `${campaignName(campaign)} - Audience`);
  const listId = list?.data?.id;
  const importJob = await importProfilesToList(privateKey, listId, audience.recipients || []);
  const klaviyoCampaign = await createCampaign(privateKey, campaign, listId);
  const campaignId = klaviyoCampaign?.data?.id;
  const messages = await getCampaignMessages(privateKey, campaignId);
  const messageId = messages?.data?.[0]?.id;
  const assignment = messageId && templateId
    ? await assignTemplateToCampaignMessage(privateKey, messageId, templateId)
    : null;

  return {
    template,
    list,
    importJob,
    campaign: klaviyoCampaign,
    messages,
    assignment,
  };
}

async function sendCampaign(privateKey, campaignId) {
  const client = createKlaviyoClient(privateKey);
  const response = await client.post("/campaign-send-jobs", {
    data: {
      type: "campaign-send-job",
      relationships: {
        campaign: {
          data: {
            type: "campaign",
            id: campaignId,
          },
        },
      },
    },
  });
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
  createCampaignSendPackage,
  sendCampaign,
  saveKlaviyoAsset,
};
