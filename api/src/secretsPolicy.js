// What production needs before it may start.
//
// Every failure here is a configuration a real deployment could have by mistake,
// and each one weakens the boundary silently: a forgeable session, a token key
// shared with session signing, or a founder credential short enough to guess.
// Refusing to start is louder than any of them.
//
// Messages name the variable and the rule, never a value.

const { DEV_SECRET } = require("./config");

const MIN_SECRET_LENGTH = 32;

function secretProblems(name, value) {
  if (!value) return [`${name} is not set.`];
  const problems = [];
  if (value === DEV_SECRET) problems.push(`${name} is the public development default.`);
  if (String(value).length < MIN_SECRET_LENGTH) problems.push(`${name} must be at least ${MIN_SECRET_LENGTH} characters.`);
  return problems;
}

/**
 * Schema changes belong to the table owner, and requests to the least-privilege
 * role. Unset, MIGRATION_DATABASE_URL falls back to DATABASE_URL — fine in
 * development, wrong in production, where it silently runs CREATE SCHEMA as the
 * application role and fails with "permission denied for database".
 *
 * @param {Record<string, string|undefined>} env
 * @returns {string[]} problems
 */
function productionDatabaseProblems(env = process.env) {
  if (env.NODE_ENV !== "production") return [];
  const problems = [];
  if (!env.MIGRATION_DATABASE_URL) {
    problems.push("MIGRATION_DATABASE_URL is not set. It must be the owner connection used for schema changes, grants and policies.");
  } else if (env.MIGRATION_DATABASE_URL === env.DATABASE_URL) {
    problems.push("MIGRATION_DATABASE_URL must differ from DATABASE_URL: the owner makes schema changes, the application role serves requests.");
  }
  return problems;
}

/**
 * @param {Record<string, string|undefined>} env
 * @returns {string[]} problems; empty when the configuration may run
 */
function productionSecretProblems(env = process.env) {
  if (env.NODE_ENV !== "production") return [];
  const problems = [
    ...secretProblems("SESSION_SECRET", env.SESSION_SECRET),
    ...secretProblems("TOKEN_ENCRYPTION_SECRET", env.TOKEN_ENCRYPTION_SECRET),
  ];
  if (env.SESSION_SECRET && env.SESSION_SECRET === env.TOKEN_ENCRYPTION_SECRET) {
    problems.push("SESSION_SECRET and TOKEN_ENCRYPTION_SECRET must be different values.");
  }
  if (env.TOKEN_ENCRYPTION_SECRET_PREVIOUS && env.TOKEN_ENCRYPTION_SECRET_PREVIOUS === env.SESSION_SECRET) {
    problems.push("TOKEN_ENCRYPTION_SECRET_PREVIOUS must not equal SESSION_SECRET.");
  }
  // Optional, but when set it acts for every store.
  if (env.BEACONAI_ADMIN_TOKEN && env.BEACONAI_ADMIN_TOKEN.length < MIN_SECRET_LENGTH) {
    problems.push(`BEACONAI_ADMIN_TOKEN must be at least ${MIN_SECRET_LENGTH} characters.`);
  }
  if (env.SHOPIFY_CLIENT_ID && !env.SHOPIFY_CLIENT_SECRET) {
    problems.push("SHOPIFY_CLIENT_SECRET is required to verify Shopify webhooks and callbacks.");
  }
  return problems;
}

module.exports = { MIN_SECRET_LENGTH, productionDatabaseProblems, productionSecretProblems };
