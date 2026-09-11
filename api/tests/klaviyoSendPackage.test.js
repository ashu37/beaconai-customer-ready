const test = require("node:test");
const assert = require("node:assert/strict");
const axios = require("axios");

const { config } = require("../src/config");
const { createCampaignSendPackage } = require("../src/services/klaviyoClient");
const { startFakeKlaviyo } = require("./helpers/fakeKlaviyo");

// A marker no default or fallback rendering could produce, so finding it in the
// provider request proves these are the caller's bytes.
const APPROVED_HTML = "<!doctype html><html><body><p>approved-bytes-7f3a</p></body></html>";
const CAMPAIGN = {
  playTitle: "Win back lapsed buyers",
  subject: "We saved your spot",
  previewText: "Your favourites are still here.",
};
const AUDIENCE = {
  recipients: [
    { email: "a@example.com", customerId: "c-1", orderCount: 2, totalRevenue: 80 },
    { email: "b@example.com", customerId: "c-2", orderCount: 1, totalRevenue: 40 },
  ],
};

async function rejection(promise) {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  assert.fail("expected the package call to fail");
}

test("a draft is created from the approved bytes, in the provider's order", async () => {
  const fake = await startFakeKlaviyo();
  try {
    const result = await createCampaignSendPackage("pk_test", CAMPAIGN, AUDIENCE, { html: APPROVED_HTML });

    assert.deepEqual(fake.calls(), [
      "GET /accounts",
      "POST /templates",
      "POST /lists",
      "POST /profile-bulk-import-jobs",
      "POST /campaigns",
      "GET /campaigns/camp-1/campaign-messages",
      "POST /campaign-message-assign-template",
    ]);

    const template = fake.requests.find((r) => r.path === "/templates");
    assert.equal(template.body.data.attributes.html, APPROVED_HTML, "the reviewed bytes, unchanged");
    assert.equal(template.body.data.attributes.editor_type, "CODE");
    assert.equal(template.headers.authorization, "Klaviyo-API-Key pk_test");
    assert.equal(result.html, APPROVED_HTML, "and the record of what was sent says the same");

    const imported = fake.requests.find((r) => r.path === "/profile-bulk-import-jobs");
    assert.deepEqual(imported.body.data.attributes.profiles.data.map((p) => p.attributes.email), ["a@example.com", "b@example.com"]);
    assert.equal(imported.body.data.relationships.lists.data[0].id, "list-1");

    const assignment = fake.requests.find((r) => r.path === "/campaign-message-assign-template").body.data;
    assert.equal(assignment.id, "msg-1");
    assert.equal(assignment.relationships.template.data.id, "tpl-1");
    assert.equal(result.campaign.data.id, "camp-1");
  } finally {
    await fake.close();
  }
});

test("the draft carries the approved subject and the account's sender", async () => {
  const fake = await startFakeKlaviyo({ sender: { name: "Acme Goods", email: "hello@acme.example" } });
  try {
    await createCampaignSendPackage("pk_test", CAMPAIGN, AUDIENCE, { html: APPROVED_HTML });
    const attrs = fake.requests.find((r) => r.path === "/campaigns").body.data.attributes;
    const definition = attrs["campaign-messages"].data[0].attributes.definition;
    assert.equal(definition.channel, "email");
    assert.deepEqual(definition.content, {
      subject: "We saved your spot",
      preview_text: "Your favourites are still here.",
      from_email: "hello@acme.example",
      from_label: "Acme Goods",
    });
    assert.deepEqual(attrs.audiences.included, ["list-1"]);
    // Creating a campaign must never schedule it.
    assert.equal(attrs.send_strategy, undefined);
  } finally {
    await fake.close();
  }
});

// The body main shipped before this fix, sent verbatim. Real Klaviyo refused it
// with these four errors on 2026-09-11; the fake must refuse it too, or it is
// not guarding the contract.
test("the fake refuses the campaign body Klaviyo refused", async () => {
  const fake = await startFakeKlaviyo();
  try {
    const error = await rejection(axios.post(`${config.klaviyo.apiBaseUrl}/campaigns`, {
      data: {
        type: "campaign",
        attributes: {
          name: "BeaconAI - old body", channel: "email", send_strategy: { method: "manual" },
          audiences: { included: ["list-1"], excluded: [] }, send_options: { use_smart_sending: true },
          tracking_options: { is_add_utm: true, utm_params: [{ name: "utm_source", value: "beaconai" }] },
        },
      },
    }));
    assert.equal(error.response.status, 400);
    const pointers = error.response.data.errors.map((e) => e.source.pointer);
    for (const pointer of [
      "/data/attributes/channel", "/data/attributes/send_strategy",
      "/data/attributes/is_add_utm", "/data/attributes/utm_params",
    ]) {
      assert.ok(pointers.includes(pointer), `refuses ${pointer}`);
    }
  } finally {
    await fake.close();
  }
});

// Each of these can be known without creating anything at Klaviyo. Found before
// the first write, they prove nothing exists there — so the campaign is released
// for a retry instead of being locked as uncertain.
for (const [name, key, campaign, audience, options, fakeOptions] of [
  ["no rendered html", "pk_test", CAMPAIGN, AUDIENCE, {}],
  ["no Klaviyo key", null, CAMPAIGN, AUDIENCE, { html: APPROVED_HTML }],
  ["no subject line", "pk_test", { ...CAMPAIGN, subject: "  " }, AUDIENCE, { html: APPROVED_HTML }],
  ["no recipient with an email", "pk_test", CAMPAIGN, { recipients: [{ customerId: "c-1" }] }, { html: APPROVED_HTML }],
  ["no default sender on the account", "pk_test", CAMPAIGN, AUDIENCE, { html: APPROVED_HTML }, { sender: null }],
]) {
  test(`${name}: refused before anything is created, and reported as such`, async () => {
    const fake = await startFakeKlaviyo(fakeOptions);
    try {
      const error = await rejection(createCampaignSendPackage(key, campaign, audience, options));
      assert.equal(error.providerStage, "not_started");
      assert.equal(error.provenNothingCreated, true);
      assert.deepEqual(fake.writes(), [], "nothing was written to Klaviyo");
    } finally {
      await fake.close();
    }
  });
}

test("a failure once requests have gone out never claims nothing was created", async () => {
  const fake = await startFakeKlaviyo({ failAt: { "POST /campaigns": 500 } });
  try {
    const error = await rejection(
      createCampaignSendPackage("pk_test", CAMPAIGN, AUDIENCE, { html: APPROVED_HTML })
    );
    assert.equal(error.providerStage, "campaign");
    assert.equal(error.provenNothingCreated, false);
    // A template, a list and an import already exist at the provider.
    assert.deepEqual(fake.writes(), ["POST /templates", "POST /lists", "POST /profile-bulk-import-jobs", "POST /campaigns"]);
  } finally {
    await fake.close();
  }
});
