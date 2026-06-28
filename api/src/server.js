require("dotenv").config();

const path = require("path");
const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const morgan = require("morgan");
const { config } = require("./config");
const { initSchema } = require("./schema");
const { router } = require("./routes");

const app = express();

app.use(helmet());
app.use(cors());
app.use(express.json({ limit: "10mb" }));
app.use(morgan("dev"));

app.use("/api", router);

app.get("/health", (req, res) => {
  res.json({ ok: true, service: "beaconai-api" });
});

app.get("/api", (req, res) => {
  res.json({
    ok: true,
    name: "BeaconAI API MVP",
    docs: {
      health: "/api/health",
      syncShopify: "POST /api/sync/shopify",
      engineInput: "GET /api/engine/input/:shopDomain",
      demoRun: "POST /api/demo/run",
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
  await initSchema();

  app.listen(config.port, () => {
    console.log(`BeaconAI API running on http://localhost:${config.port}`);
  });
}

start().catch((error) => {
  console.error("Failed to start server", error);
  process.exit(1);
});
