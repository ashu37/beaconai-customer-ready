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

async function createTemplate(privateKey, campaign) {
  const client = createKlaviyoClient(privateKey);

  const payload = {
    data: {
      type: "template",
      attributes: {
        name: campaign.klaviyo?.template_name || `BeaconAI - ${campaign.play_name}`,
        editor_type: "CODE",
        html: campaign.email.html,
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
