// Request logging without credentials.
//
// The default request line logs the full URL, and some URLs carry secrets: an
// OAuth callback's `code`, `state` and `hmac`, a webhook's shop and timestamp.
// Query values for those keys, and for any key that looks like a credential or
// an email address, are replaced before the line is written. Bodies are never
// logged.

const morgan = require("morgan");

const SENSITIVE_KEYS = new Set(["code", "state", "hmac", "signature", "host", "timestamp", "session", "id_token"]);
const SENSITIVE_PATTERN = /token|secret|password|email|key/i;

function redactUrl(url) {
  const raw = String(url || "");
  const index = raw.indexOf("?");
  if (index === -1) return raw;
  const path = raw.slice(0, index);
  let params;
  try {
    params = new URLSearchParams(raw.slice(index + 1));
  } catch (_) {
    return `${path}?[redacted]`;
  }
  const parts = [];
  for (const [key, value] of params) {
    const hide = SENSITIVE_KEYS.has(key.toLowerCase()) || SENSITIVE_PATTERN.test(key);
    parts.push(`${encodeURIComponent(key)}=${hide ? "[redacted]" : encodeURIComponent(value)}`);
  }
  return parts.length ? `${path}?${parts.join("&")}` : path;
}

morgan.token("safe-url", (req) => redactUrl(req.originalUrl || req.url));

// The "dev" format's fields, with the redacted URL.
const FORMAT = ":method :safe-url :status :response-time ms - :res[content-length]";

function requestLogger(options = {}) {
  return morgan(FORMAT, options);
}

module.exports = { redactUrl, requestLogger };
