// Integration tokens at rest: AES-256-GCM under a key derived from
// TOKEN_ENCRYPTION_SECRET.
//
// Decryption uses a keyring — the current key, then the optional previous one —
// so the key can change without disconnecting every store. Encryption only ever
// uses the current key. Session signing uses a different secret entirely
// (sessionService.js), so revoking sessions never involves this key.

const crypto = require("node:crypto");
const { config } = require("../config");

function keyFrom(secret) {
  return crypto.createHash("sha256").update(String(secret)).digest();
}

function keyring() {
  const keys = [];
  if (config.tokenEncryptionSecret) keys.push({ id: "current", key: keyFrom(config.tokenEncryptionSecret) });
  if (config.tokenEncryptionPreviousSecret) keys.push({ id: "previous", key: keyFrom(config.tokenEncryptionPreviousSecret) });
  return keys;
}

function encryptToken(value) {
  if (!value) return null;
  if (!config.tokenEncryptionSecret) throw new Error("TOKEN_ENCRYPTION_SECRET is not configured.");
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", keyFrom(config.tokenEncryptionSecret), iv);
  const encrypted = Buffer.concat([cipher.update(String(value), "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return `v1:${iv.toString("base64")}:${tag.toString("base64")}:${encrypted.toString("base64")}`;
}

// Which key opens a stored value: "current", "previous", "plaintext" (a legacy
// unencrypted value) or "undecryptable". Never the value itself.
function inspectToken(value) {
  if (!value) return { status: "empty", plaintext: null };
  if (!String(value).startsWith("v1:")) return { status: "plaintext", plaintext: String(value) };
  const [, ivB64, tagB64, encryptedB64] = String(value).split(":");
  for (const { id, key } of keyring()) {
    try {
      const decipher = crypto.createDecipheriv("aes-256-gcm", key, Buffer.from(ivB64, "base64"));
      decipher.setAuthTag(Buffer.from(tagB64, "base64"));
      const plaintext = Buffer.concat([
        decipher.update(Buffer.from(encryptedB64, "base64")),
        decipher.final(),
      ]).toString("utf8");
      return { status: id, plaintext };
    } catch (_) {
      // Wrong key: try the next one.
    }
  }
  return { status: "undecryptable", plaintext: null };
}

function decryptToken(value) {
  const { status, plaintext } = inspectToken(value);
  if (status === "empty") return null;
  if (status === "undecryptable") {
    throw new Error("A stored integration token could not be decrypted with the configured keys.");
  }
  // A legacy plaintext value still works (so a store is not disconnected by this
  // change) but is counted by tokenKeyHealth so it can be re-encrypted.
  return plaintext;
}

const TOKEN_COLUMNS = ["shopify_access_token", "klaviyo_access_token", "klaviyo_refresh_token", "klaviyo_private_key"];

/**
 * Counts, per key status, across every stored integration token. For the
 * founder's readiness view after a secrets change: every token should report
 * "current". Values never leave this function.
 */
async function tokenKeyHealth(queryFn) {
  const { rows } = await queryFn(`SELECT ${TOKEN_COLUMNS.join(", ")} FROM clean.connections`);
  const counts = { current: 0, previous: 0, plaintext: 0, undecryptable: 0 };
  for (const row of rows) {
    for (const column of TOKEN_COLUMNS) {
      const { status } = inspectToken(row[column]);
      if (status in counts) counts[status] += 1;
    }
  }
  return counts;
}

module.exports = { decryptToken, encryptToken, inspectToken, tokenKeyHealth, TOKEN_COLUMNS };
