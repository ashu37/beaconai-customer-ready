require("dotenv").config();

const path = require("path");
const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const morgan = require("morgan");
const { config } = require("./config");
const { initSchema } = require("./schema");
const { router } = require("./routes");
const { getStartupState, markDatabaseFailed, markDatabaseReady } = require("./startupState");

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
app.use(express.json({ limit: "10mb" }));
app.use(morgan("dev"));

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
  app.listen(config.port, () => {
    console.log(`BeaconAI API running on http://localhost:${config.port}`);
  });

  try {
    await initSchema();
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
