// A local stand-in for Klaviyo's API, spoken to over real HTTP by the real
// provider client. Replacing the client's helpers instead is how a handoff that
// could never create a draft passed every test: the replaced function was the
// one with the bug.
//
// It is only as good as the rules it enforces, and a permissive fake is how a
// request Klaviyo refuses got past it once. The campaign rules below are the
// ones real Klaviyo applied at revision 2026-04-15 (checked with
// `npm run smoke:klaviyo` and a direct probe, 2026-09-11). Keep them in step
// with the provider, not with our client.
//
// Records every request it receives, in order, so a test can say both what was
// sent and — just as often the point — that nothing was.
const http = require("node:http");
const { config } = require("../../src/config");

const SEND_METHODS = ["static", "immediate", "throttled", "smart_send_time"];
const CAMPAIGN_FIELDS = ["name", "audiences", "send_strategy", "send_options", "tracking_options", "campaign-messages"];
const TRACKING_FIELDS = ["add_tracking_params", "custom_tracking_params", "is_tracking_opens", "is_tracking_clicks"];

function invalid(detail, pointer) {
  return { status: 400, title: "Invalid input.", detail, source: { pointer } };
}

// What Klaviyo refused on 2026-09-11, plus the documented required fields.
function campaignErrors(body) {
  const attrs = body?.data?.attributes || {};
  const errors = [];
  for (const field of Object.keys(attrs)) {
    if (!CAMPAIGN_FIELDS.includes(field)) {
      errors.push(invalid(`'${field}' is not a valid field for the resource 'campaign'.`, `/data/attributes/${field}`));
    }
  }
  if (!attrs.name) errors.push(invalid("'name' is required.", "/data/attributes/name"));
  if (!attrs.audiences?.included?.length) errors.push(invalid("'audiences.included' is required.", "/data/attributes/audiences"));
  if (attrs.send_strategy && !SEND_METHODS.includes(attrs.send_strategy.method)) {
    errors.push(invalid("Invalid value for 'method'.", "/data/attributes/send_strategy"));
  }
  for (const field of Object.keys(attrs.tracking_options || {})) {
    if (!TRACKING_FIELDS.includes(field)) {
      errors.push(invalid(`'${field}' is not a valid field for the resource 'tracking-options'.`, `/data/attributes/${field}`));
    }
  }
  const message = attrs["campaign-messages"]?.data?.[0]?.attributes?.definition;
  if (message?.channel !== "email") {
    errors.push(invalid("'campaign-messages' with an email definition is required.", "/data/attributes/campaign-messages"));
  }
  return errors;
}

/**
 * Start the fake and point the provider client at it.
 *
 * @param {object} [options]
 * @param {Record<string, number>} [options.failAt]  "METHOD /path" (without
 *   the /api prefix) → status to answer with instead, e.g. { "POST /campaigns": 500 }.
 * @param {{name?: string, email?: string}|null} [options.sender]  the account's
 *   default sender; null for an account with none set.
 */
async function startFakeKlaviyo({ failAt = {}, sender = { name: "Test Shop", email: "hello@test-shop.example" } } = {}) {
  const requests = [];
  const routes = {
    "GET /accounts": () => [200, {
      data: [{
        type: "account", id: "acct-1",
        attributes: {
          contact_information: {
            default_sender_name: sender?.name || null,
            default_sender_email: sender?.email || null,
            organization_name: "Test Shop",
          },
        },
      }],
    }],
    "POST /templates": (body) => (body?.data?.attributes?.html
      ? [201, { data: { type: "template", id: "tpl-1" } }]
      : [400, { errors: [invalid("'html' is required for a CODE template.", "/data/attributes/html")] }]),
    "POST /lists": () => [201, { data: { type: "list", id: "list-1" } }],
    "POST /profile-bulk-import-jobs": () => [202, { data: { type: "profile-bulk-import-job", id: "job-1" } }],
    "POST /campaigns": (body) => {
      const errors = campaignErrors(body);
      if (errors.length) return [400, { errors }];
      return [201, {
        data: {
          type: "campaign", id: "camp-1",
          attributes: { name: body.data.attributes.name, status: "Draft" },
          relationships: { "campaign-messages": { data: [{ type: "campaign-message", id: "msg-1" }] } },
        },
      }];
    },
    "GET /campaigns/camp-1/campaign-messages": () => [200, { data: [{ type: "campaign-message", id: "msg-1" }] }],
    "POST /campaign-message-assign-template": () => [200, { data: { type: "campaign-message", id: "msg-1" } }],
  };

  const server = http.createServer((req, res) => {
    let raw = "";
    req.on("data", (chunk) => { raw += chunk; });
    req.on("end", () => {
      const path = req.url.split("?")[0].replace(/^\/api/, "");
      const body = raw ? JSON.parse(raw) : null;
      requests.push({ method: req.method, path, headers: req.headers, body });

      const key = `${req.method} ${path}`;
      const failure = failAt[key];
      const [status, payload] = failure
        ? [failure, { errors: [{ status: failure, detail: "fake provider failure" }] }]
        : routes[key]?.(body) || [404, { errors: [{ status: 404, detail: `fake has no ${key}` }] }];
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify(payload));
    });
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));

  const original = config.klaviyo.apiBaseUrl;
  config.klaviyo.apiBaseUrl = `http://127.0.0.1:${server.address().port}/api`;

  return {
    requests,
    /** "METHOD /path" for each request, in order. */
    calls: () => requests.map((r) => `${r.method} ${r.path}`),
    /** Only the requests that can create something at the provider. */
    writes: () => requests.filter((r) => r.method !== "GET").map((r) => `${r.method} ${r.path}`),
    async close() {
      config.klaviyo.apiBaseUrl = original;
      await new Promise((resolve) => server.close(resolve));
    },
  };
}

module.exports = { startFakeKlaviyo };
