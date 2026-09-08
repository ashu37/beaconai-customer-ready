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

// 503 while the database is unreachable. The API deliberately stays up without
// it (so OAuth and static assets still serve), but every route that touches data
// fails — reporting 200 there made Render's health check pass on an instance
// that could not serve a single request.
app.get("/health", (req, res) => {
  const startup = getStartupState();
  const healthy = startup.database.status !== "error";
  res.status(healthy ? 200 : 503).json({ ok: healthy, service: "beaconai-api", startup });
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
