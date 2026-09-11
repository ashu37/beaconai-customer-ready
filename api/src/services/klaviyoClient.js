const axios = require("axios");
const { config } = require("../config");
const { query } = require("../db");

function createKlaviyoClient(privateKey) {
  if (!privateKey) {
    throw new Error("Klaviyo private key is required");
  }

  return axios.create({
    baseURL: config.klaviyo.apiBaseUrl,
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
  const brand = campaign.brandContext?.brandName || "BeaconAI";
  const bestSeller = campaign.brandContext?.productLanguage?.bestSellers?.[0]?.title;
  const headline = campaign.bodyH2 || campaign.subject || campaign.playTitle;
  const body = campaign.bodyP1 || campaign.previewText;
  // Support paragraph: never re-introduce the bestseller if the headline or body
  // already names it — the copy shouldn't repeat the product across every slot.
  const namesBestSeller = (text) => Boolean(bestSeller) && String(text || "").includes(bestSeller);
  const bestSellerAlreadyShown = namesBestSeller(campaign.subject) || namesBestSeller(headline) || namesBestSeller(body);
  const supportCopy = campaign.bodyP2
    || (bestSeller && !bestSellerAlreadyShown ? `A customer favorite from the current catalog: ${bestSeller}.` : "");

  // CA-5: featured product image block (merchant's own Shopify CDN asset only).
  // Rendered between headline and body; skipped entirely when no imageUrl.
  const featured = campaign.featuredProduct;
  const imageBlock = featured?.imageUrl
    ? `<div style="text-align:center;margin:0 0 16px;">
         <img src="${escapeHtml(featured.imageUrl)}" alt="${escapeHtml(featured.title || "")}" style="max-width:260px;width:100%;height:auto;border-radius:4px;" />
         ${featured.title ? `<p style="margin:6px 0 0;font-size:13px;color:#8a8578;">${escapeHtml(featured.title)}</p>` : ""}
       </div>`
    : "";

  return `
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body style="margin:0;padding:0;background:#f7f5f0;font-family:Arial,sans-serif;color:#151515;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f7f5f0;padding:16px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border:1px solid #ded7cc;">
            <tr>
              <td style="padding:24px 20px;">
                <p style="margin:0 0 12px;color:#f08a24;font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:1.5px;">${escapeHtml(brand)}</p>
                <h1 style="margin:0 0 16px;font-size:24px;line-height:1.2;color:#111111;">${escapeHtml(headline)}</h1>
                ${imageBlock}
                <p style="margin:0 0 16px;font-size:16px;line-height:1.55;color:#3f3a34;">${escapeHtml(body)}</p>
                ${supportCopy ? `<p style="margin:0 0 24px;font-size:16px;line-height:1.55;color:#3f3a34;">${escapeHtml(supportCopy)}</p>` : ""}
                <a href="{{ organization.url|default:'#' }}" style="display:inline-block;background:#f08a24;color:#111111;text-decoration:none;font-weight:bold;padding:14px 20px;border-radius:4px;">${escapeHtml(campaign.cta || "See what's new")}</a>
              </td>
            </tr>
            <tr>
              <td style="padding:20px;border-top:1px solid #ded7cc;">
                <p style="margin:0;font-size:12px;line-height:1.5;color:#8a8578;">
                  You're receiving this because you shopped with ${escapeHtml(brand)}.
                  <a href="{% unsubscribe %}" style="color:#8a8578;">Unsubscribe</a>
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

async function createTemplate(privateKey, campaign, prerenderedHtml) {
  const client = createKlaviyoClient(privateKey);

  // The caller renders and passes the bytes in — Ticket C: ONE renderer for both
  // the preview and the provider draft. There is deliberately no fallback: a
  // default here would silently put BeaconAI's own styling in front of a
  // merchant's customers on any path that forgot to render, and it would look
  // like it worked. Refusing is the whole point of brand_setup_required.
  if (!prerenderedHtml) {
    throw new Error(
      "createCampaignSendPackage requires rendered html. Render the shop's approved brand shell first."
    );
  }
  const html = prerenderedHtml;
  const payload = {
    data: {
      type: "template",
      attributes: {
        name: campaignTemplateName(campaign),
        editor_type: "CODE",
        html,
      },
    },
  };

  const response = await client.post("/templates", payload);
  return { ...response.data, html };
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

// The envelope of the email: who it is from and what the inbox shows. The HTML
// body goes in separately as a template. Reply-to is left to Klaviyo, which
// uses the sender address; the account does not report a separate one.
function emailContent(campaign, sender) {
  const content = {
    subject: campaign.subject,
    preview_text: campaign.previewText || null,
    from_email: sender.email,
    from_label: sender.name || null,
  };
  return Object.fromEntries(Object.entries(content).filter(([, value]) => value));
}

// Klaviyo's Create Campaign body. `campaign-messages` is required and carries
// the envelope; without it the request is refused, after the template, list
// and import have already been created.
//
// No send_strategy. Creating a campaign does not send it — the merchant sends
// or schedules it in Klaviyo — and the old "manual" value is not one Klaviyo
// accepts.
async function createCampaign(privateKey, campaign, listId, sender) {
  const client = createKlaviyoClient(privateKey);
  const response = await client.post("/campaigns", {
    data: {
      type: "campaign",
      attributes: {
        name: campaignName(campaign),
        audiences: {
          included: [listId],
          excluded: [],
        },
        send_options: {
          use_smart_sending: true,
        },
        tracking_options: {
          add_tracking_params: true,
          custom_tracking_params: [
            { type: "static", name: "utm_source", value: "beaconai" },
            { type: "static", name: "utm_medium", value: "email" },
            { type: "static", name: "utm_campaign", value: campaign.playTitle || campaign.play_name || "beaconai" },
          ],
        },
        "campaign-messages": {
          data: [{
            type: "campaign-message",
            attributes: {
              definition: {
                channel: "email",
                label: campaignName(campaign),
                content: emailContent(campaign, sender),
              },
            },
          }],
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

// Every provider call this makes is recorded on `error.providerStage` when it
// throws, because the caller's decision — retry, or keep the campaign locked for
// reconciliation — depends entirely on whether anything can already exist at the
// provider. "not_started" is the ONLY stage that proves nothing was created.
const PROVIDER_STAGES = ["not_started", "template", "list", "import", "campaign", "message", "assignment"];

// Everything that can be known to fail without asking the provider is checked
// here, while the stage is still "not_started". A failure found only once the
// sequence has begun is reported as "something may exist at the provider",
// which locks the campaign for reconciliation; these failures prove nothing was
// sent, so the merchant can fix the cause and retry.
function assertPackageSendable(privateKey, campaign, audience, options) {
  if (!privateKey) {
    throw new Error("Klaviyo is not connected for this store. Connect Klaviyo, then try again.");
  }
  if (!options.html) {
    throw new Error(
      "createCampaignSendPackage requires rendered html. Render the shop's approved brand shell first."
    );
  }
  if (!String(campaign?.subject || "").trim()) {
    throw new Error("This campaign has no subject line. Add one, then try again.");
  }
  if (!(audience?.recipients || []).some((recipient) => recipient.email)) {
    throw new Error("Cannot create a Klaviyo audience list without recipient emails.");
  }
}

// The sender the review screen showed, read from the same account setting. A
// read creates nothing, so a missing sender is still a proven pre-creation
// failure — and a campaign with no "from" is not one to leave in Klaviyo.
async function requireSender(privateKey) {
  const sender = await getKlaviyoSender(privateKey);
  if (!sender?.email) {
    throw new Error(
      "The Klaviyo account has no default sender email. Set one in Klaviyo (Settings → Account), then try again."
    );
  }
  return sender;
}

async function createCampaignSendPackage(privateKey, campaign, audience, options = {}) {
  const progress = { stage: "not_started" };
  try {
    assertPackageSendable(privateKey, campaign, audience, options);
    const sender = await requireSender(privateKey);
    return await createCampaignSendPackageInner(privateKey, campaign, audience, progress, { ...options, sender });
  } catch (error) {
    error.providerStage = progress.stage;
    // True only before the first provider request is issued. Anything later may
    // have created a template, a list or a campaign.
    error.provenNothingCreated = progress.stage === "not_started";
    throw error;
  }
}

async function createCampaignSendPackageInner(privateKey, campaign, audience, progress, options) {
  // The stage is advanced BEFORE each call, not after: a request that times out
  // may still have been executed by the provider, so "we were at the campaign
  // step" has to mean "a campaign may exist".
  progress.stage = "template";
  // The reviewed bytes. Dropping this argument once meant every handoff threw
  // here — and, being past "not_started", locked the campaign as uncertain
  // although nothing had been sent.
  const template = await createTemplate(privateKey, campaign, options.html);
  const templateId = template?.data?.id;
  progress.stage = "list";
  const list = await createList(privateKey, `${campaignName(campaign)} - Audience`);
  const listId = list?.data?.id;
  progress.stage = "import";
  const importJob = await importProfilesToList(privateKey, listId, audience.recipients || []);
  progress.stage = "campaign";
  const klaviyoCampaign = await createCampaign(privateKey, campaign, listId, options.sender);
  const campaignId = klaviyoCampaign?.data?.id;
  progress.stage = "message";
  const messages = await getCampaignMessages(privateKey, campaignId);
  const messageId = messages?.data?.[0]?.id;
  progress.stage = "assignment";
  const assignment = messageId && templateId
    ? await assignTemplateToCampaignMessage(privateKey, messageId, templateId)
    : null;

  return {
    template,
    // The exact html pushed to Klaviyo, for the campaign record.
    html: template?.html || null,
    list,
    importJob,
    campaign: klaviyoCampaign,
    messages,
    assignment,
  };
}

function klaviyoCampaignToMatch(item) {
  return {
    provider: "klaviyo",
    id: item.id,
    name: item.attributes?.name || null,
    // Deliberately NOT item.links.self. That is an API resource URL, not a page
    // a merchant can open, and treating its presence as a usable Klaviyo editor
    // link would put a dead "Open draft" button in front of them. Until a URL is
    // verified as a UI destination we have none, and the find-by-name fallback
    // is what the merchant gets.
    url: null,
    status: item.attributes?.status || null,
    sentAt: item.attributes?.send_time || null,
    // Present-but-null when the provider reports no count. Not zero.
    sentCount: item.attributes?.recipient_count ?? null,
  };
}

/**
 * Fetch one campaign by the id we already hold.
 *
 * Always tried first. An id we were given by the provider is a far stronger
 * identity than any name search, and skipping it was how reconciliation managed
 * to "not find" a campaign it already had a reference to.
 */
async function getKlaviyoCampaign(privateKey, campaignId) {
  const client = createKlaviyoClient(privateKey);
  try {
    const response = await client.get(`/campaigns/${encodeURIComponent(campaignId)}`);
    const item = response.data?.data;
    return item ? klaviyoCampaignToMatch(item) : null;
  } catch (error) {
    // A 404 is a real answer: the provider does not have it. Anything else is a
    // failed lookup and must not be reported as absence.
    if (error.response?.status === 404) return null;
    throw error;
  }
}

/**
 * Look a campaign up at the provider by the EXACT name we sent at handoff.
 *
 * Reconciliation's eyes when there is no id. Returns EVERY match — more than one
 * is a real answer ("we cannot tell which is yours") and must not be collapsed
 * into a guess. Never creates anything.
 *
 * Pages to the end. A partial listing that happens not to contain the campaign
 * is indistinguishable from the campaign not existing, and this function's
 * caller treats absence as permission to retry — so stopping early could
 * authorise a duplicate send.
 */
async function findKlaviyoCampaigns(privateKey, providerCampaignName, { maxPages = 50, createdAtOrAfter = null } = {}) {
  if (!providerCampaignName) return { matches: [], complete: false, reason: "no_recorded_name" };
  const notBefore = createdAtOrAfter ? new Date(createdAtOrAfter).getTime() : null;

  const client = createKlaviyoClient(privateKey);
  let path = `/campaigns?filter=${encodeURIComponent(`equals(messages.channel,'email')`)}`;
  const matches = [];
  let pages = 0;

  while (path && pages < maxPages) {
    const response = await client.get(path);
    for (const item of response.data?.data || []) {
      if ((item.attributes?.name || "") !== providerCampaignName) continue;
      // Attempt-scoped: a campaign created before this attempt started belongs
      // to an earlier one, and adopting it would resolve this attempt with
      // someone else's evidence.
      if (notBefore !== null) {
        const createdAt = Date.parse(item.attributes?.created_at || "");
        if (Number.isFinite(createdAt) && createdAt < notBefore) continue;
      }
      matches.push(klaviyoCampaignToMatch(item));
    }
    pages += 1;
    const next = response.data?.links?.next || null;
    path = next ? next.replace(/^https?:\/\/[^/]+\/api/, "") : null;
  }

  // `complete` says whether we actually reached the end. The caller may only
  // declare absence when it did.
  return { matches, complete: !path, pages };
}

/**
 * The account's configured sender, if the provider reports one.
 *
 * Returns null rather than anything derived. A from-address assembled from the
 * store domain would look verified and be a guess, and the merchant would only
 * find out when the email arrived from an address that does not exist.
 */
async function getKlaviyoSender(privateKey) {
  const client = createKlaviyoClient(privateKey);
  const response = await client.get("/accounts");
  const account = response.data?.data?.[0]?.attributes || null;
  if (!account) return null;

  const contact = account.contact_information || {};
  const name = contact.default_sender_name || null;
  const email = contact.default_sender_email || null;
  if (!name && !email) return null;

  return {
    name,
    email,
    // Klaviyo does not report a reply-to on the account; it is set per campaign.
    // Saying so is better than leaving the field to be read as "same as sender".
    replyTo: null,
    source: "klaviyo_account",
    organizationName: account.contact_information?.organization_name || null,
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
  PROVIDER_STAGES,
  // Exported so the handoff route can RECORD the exact name it is about to send.
  // Re-deriving it later from a stored campaign row produced a different string,
  // and reconciliation then searched for a campaign that never existed.
  campaignNameForProvider: campaignName,
  findKlaviyoCampaigns,
  getKlaviyoCampaign,
  getKlaviyoSender,
  testKlaviyo,
  getKlaviyoLists,
  getKlaviyoProfiles,
  getKlaviyoTemplates,
  campaignHtml,
  createCampaignSendPackage,
  sendCampaign,
  saveKlaviyoAsset,
};
