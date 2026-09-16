// A seed script writes fabricated orders, campaigns and measurements. Run
// against a merchant's database it would corrupt the engine's input and the
// Results page's history, and the damage is not obvious afterwards.
//
// NODE_ENV is not the check that matters. The dangerous case is a founder
// laptop whose api/.env points at the hosted database — where NODE_ENV is
// unset and everything looks local. So the guard is on the connection: a seed
// runs against a database on this machine, and anything else has to be asked
// for by name.

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "0.0.0.0", ""]);

function hostOf(connectionString) {
  try {
    return new URL(connectionString).hostname;
  } catch {
    // A libpq keyword string or a socket path: no host to read, so treat it as
    // remote rather than guessing in the permissive direction.
    return null;
  }
}

/**
 * @returns {string|null} why this database must not be seeded, or null.
 */
function seedRefusal(env = process.env, { allowEnvVar = "SEED_ALLOW_REMOTE" } = {}) {
  if (env[allowEnvVar]) return null;
  const url = env.DATABASE_URL || "";
  if (!url) return "DATABASE_URL is not set.";
  const host = hostOf(url);
  if (host !== null && LOCAL_HOSTS.has(host)) return null;
  return (
    `Refusing to seed: DATABASE_URL points at ${host || "a database this check cannot read the host of"}, ` +
    `not a database on this machine. Seeding writes fabricated orders and campaigns, which would change ` +
    `the audiences the engine computes and the history the Results page reports.\n` +
    `If this really is a disposable database, re-run with ${allowEnvVar}=1.`
  );
}

/** Exits non-zero with the reason, or returns so the caller can continue. */
function assertSeedable(env = process.env) {
  const refusal = seedRefusal(env);
  if (!refusal) return;
  console.error(refusal);
  process.exit(1);
}

module.exports = { assertSeedable, seedRefusal };
