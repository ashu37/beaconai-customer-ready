require("dotenv").config();

const path = require("path");
const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const { config } = require("./config");
const { productionSecretProblems } = require("./secretsPolicy");
const { requestLogger } = require("./requestLog");
const { initSchema } = require("./schema");
const { router } = require("./routes");
const { getStartupState, markDatabaseFailed, markDatabaseReady, recordDatabaseSecurity } = require("./startupState");
const { query } = require("./db");
const { databaseSecurityProblems, inspectDatabaseSecurity } = require("./services/databaseSecurity");

const app = express();

app.use(helmet());
// Credentialed CORS. The session cookie only travels on requests the browser
// considers same-site or explicitly allowed, and `Access-Control-Allow-Origin: *`
// is rejected outright when credentials are included — so a wildcard here would
// silently break every authenticated call from the browser while leaving the
// HTTP tests green.
//
// The list is explicit for a second reason: with credentials enabled, reflecting
// any origin would let any page a merchant visits call this API as them.
const allowedOrigins = new Set([...config.corsOrigins, config.webBaseUrl].filter(Boolean));

// In development the frontend's port moves — vite picks another when one is
// taken — so a hardcoded port list is a guess that fails silently and looks like
// a broken app. Any loopback origin is accepted instead. NOT in production: with
// credentials enabled, a permissive rule would let a page a merchant visits call
// this API as them, and loopback is not a meaningful restriction there.
const isDevelopment = process.env.NODE_ENV !== "production";
const LOOPBACK = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i;

function originAllowed(origin) {
  if (allowedOrigins.has(origin)) return true;
  return isDevelopment && LOOPBACK.test(origin);
}

app.use(cors({
  origin(origin, callback) {
    // No Origin header: same-origin, curl, or a server-to-server call. Nothing
    // to allow or refuse.
    if (!origin) return callback(null, true);
    if (originAllowed(origin)) return callback(null, true);
    // Refused by omitting the header rather than erroring, so the browser
    // reports a normal CORS failure instead of a 500.
    return callback(null, false);
  },
  credentials: true,
}));
// Webhooks are verified against the exact bytes Shopify signed, so their bodies
// stay raw. express.json skips a body this has already read.
app.use("/api/webhooks", express.raw({ type: "*/*", limit: "1mb" }));
app.use(express.json({ limit: "10mb" }));
app.use(requestLogger());

app.use("/api", router);

// LIVENESS, not readiness — this is render.yaml's healthCheckPath, and a 503
// here blocks the deploy from being promoted. Gating that on the database means
// you cannot ship a fix while the database is down, which is exactly when you
// need to. So: 200 whenever the process is up, with the database state in the
// body for humans and monitoring to read.
//
// `ok` reflects the process. `startup.database` reports the truth about data
// routes, including which host this instance is actually pointed at.
app.get("/health", (req, res) => {
  res.json({ ok: true, service: "beaconai-api", startup: getStartupState() });
});

// READINESS — 503 when data routes cannot serve. Safe to alert on; do NOT wire
// this to healthCheckPath for the reason above.
app.get("/ready", (req, res) => {
  const startup = getStartupState();
  const ready = startup.database.ready;
  res.status(ready ? 200 : 503).json({ ok: ready, service: "beaconai-api", startup });
});

app.get("/api", (req, res) => {
  res.json({
    ok: true,
    name: "BeaconAI API MVP",
    docs: {
      health: "/api/health",
      syncShopify: "POST /api/sync/shopify",
      engineInput: "GET /api/engine/input/:shopDomain",
      engineRun: "POST /api/engine/atul/run",
      latestRun: "GET /api/engine/atul/latest/:shopDomain",
    },
  });
});

const publicDir = path.join(__dirname, "..", "public");
app.use(express.static(publicDir));
app.get("*", (req, res, next) => {
  if (req.path.startsWith("/api")) return next();
  res.sendFile(path.join(publicDir, "index.html"), (error) => {
    if (error) next();
  });
});

async function start() {
  // Before listening: a production instance with a missing, default, short or
  // shared secret must not serve a single request.
  const secretProblems = productionSecretProblems(process.env);
  if (secretProblems.length) {
    for (const problem of secretProblems) console.error(`[config] ${problem}`);
    console.error("[config] Refusing to start. Fix the environment and redeploy.");
    process.exit(1);
  }

  app.listen(config.port, () => {
    console.log(`BeaconAI API running on http://localhost:${config.port}`);
  });

  try {
    await initSchema();
    // The boundary as the APPLICATION connection sees it. In production a
    // superuser, BYPASSRLS or owner runtime role, or any API-role access to
    // clean/raw, keeps the instance not-ready rather than serving customer data
    // over a boundary that isn't there.
    const report = await inspectDatabaseSecurity(query, { appRole: config.appDbRole });
    const problems = databaseSecurityProblems(report);
    recordDatabaseSecurity({ report, problems });
    if (problems.length) {
      for (const problem of problems) console.error(`[database-security] ${problem}`);
    }
    if (problems.length && process.env.NODE_ENV === "production") {
      markDatabaseFailed(new Error("Database security check failed. See the server log or `npm run security:db-check`."));
      return;
    }
    markDatabaseReady();
    console.log("Database schema is ready.");
  } catch (error) {
    markDatabaseFailed(error);
    console.error("Database schema initialization failed", error);
  }
}

start().catch((error) => {
  console.error("Failed to start server", error);
  process.exit(1);
});
