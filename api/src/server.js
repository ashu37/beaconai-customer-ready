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
app.use(cors());
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
