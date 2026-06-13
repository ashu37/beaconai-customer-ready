const { spawn } = require("child_process");
const fs = require("fs/promises");
const os = require("os");
const path = require("path");

const ENGINE_FLAGS = {
  ENGINE_V2_DECIDE: "true",
  ENGINE_V2_OUTPUT: "true",
  ENGINE_V2_SHADOW: "true",
  ENGINE_V2_SIZING: "true",
  STATS_NAN_FOR_HARDCODED: "true",
  EVIDENCE_CLASS_ENFORCED: "true",
  VERTICAL_MODE: "beauty",
  OUTCOME_LOG_ENABLED: "false",
};

function repoRoot() {
  return path.resolve(__dirname, "../../..");
}

function defaultEngineDir() {
  return path.join(repoRoot(), "engine");
}

function defaultPythonPath(engineDir) {
  return path.join(engineDir, ".venv", "bin", "python");
}

function csvCell(value) {
  if (value == null) return "";
  const text = String(value);
  if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function money(value, fallback = "0") {
  if (value == null || value === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? String(parsed) : fallback;
}

function dateValue(value) {
  if (!value) return "";
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

function shippingAmount(order) {
  return order.total_shipping_price_set?.shop_money?.amount || order.raw?.total_shipping_price_set?.shop_money?.amount || "0";
}

function customerEmail(order) {
  return order.email || order.raw?.email || order.raw?.customer?.email || "";
}

function customerId(order) {
  return order.customer_id || order.raw?.customer?.id || customerEmail(order);
}

function customerName(order) {
  const first = order.raw?.customer?.first_name || "";
  const last = order.raw?.customer?.last_name || "";
  return `${first} ${last}`.trim();
}

function shippingProvince(order) {
  return order.raw?.shipping_address?.province_code || order.raw?.shipping_address?.province || "";
}

function shippingCountry(order) {
  return order.raw?.shipping_address?.country_code || order.raw?.shipping_address?.country || "";
}

function lineItemsForOrder(input, order) {
  const items = input.order_line_items.filter((item) => item.order_id === order.id);
  if (items.length) return items;
  return [
    {
      title: "Order",
      quantity: 1,
      price: order.subtotal_price || order.total_price || "0",
      total_discount: order.total_discounts || "0",
    },
  ];
}

function orderRows(input) {
  const rows = [];
  for (const order of input.orders || []) {
    for (const item of lineItemsForOrder(input, order)) {
      rows.push({
        "Name": order.name || order.id,
        "Created at": dateValue(order.created_at),
        "Lineitem name": item.title || item.raw?.title || item.raw?.name || "Product",
        "Lineitem quantity": item.quantity || item.raw?.quantity || 1,
        "Lineitem price": money(item.price || item.raw?.price),
        "Lineitem discount": money(item.total_discount || item.raw?.total_discount),
        "Financial Status": order.financial_status || order.raw?.financial_status || "paid",
        "Fulfillment Status": order.raw?.fulfillment_status || "",
        "Subtotal": money(order.subtotal_price),
        "Total Discount": money(order.total_discounts),
        "Shipping": money(shippingAmount(order)),
        "Taxes": money(order.total_tax),
        "Total": money(order.total_price),
        "Currency": order.currency || input.shop?.currency || "USD",
        "Customer Email": customerEmail(order),
        "customer_id": customerId(order),
        "Billing Name": customerName(order),
        "Shipping Province": shippingProvince(order),
        "Shipping Country": shippingCountry(order),
      });
    }
  }
  return rows;
}

async function writeOrdersCsv(input, csvPath) {
  const headers = [
    "Name",
    "Created at",
    "Lineitem name",
    "Lineitem quantity",
    "Lineitem price",
    "Lineitem discount",
    "Financial Status",
    "Fulfillment Status",
    "Subtotal",
    "Total Discount",
    "Shipping",
    "Taxes",
    "Total",
    "Currency",
    "Customer Email",
    "customer_id",
    "Billing Name",
    "Shipping Province",
    "Shipping Country",
  ];
  const rows = orderRows(input);
  const lines = [headers.join(",")];
  for (const row of rows) {
    lines.push(headers.map((header) => csvCell(row[header])).join(","));
  }
  await fs.writeFile(csvPath, `${lines.join("\n")}\n`, "utf8");
  return rows.length;
}

function runProcess(command, args, options) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, options);
    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else {
        const error = new Error(`Atul engine exited with code ${code}`);
        error.code = code;
        error.stdout = stdout;
        error.stderr = stderr;
        reject(error);
      }
    });
  });
}

async function readJson(filePath) {
  return JSON.parse(await fs.readFile(filePath, "utf8"));
}

async function pathExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch (_) {
    return false;
  }
}

function sanitizeStoreId(value) {
  const text = String(value || "unknown").trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^[-_]+|[-_]+$/g, "");
  return text || "unknown";
}

async function listManifestCandidates(engineDir, runId, storeIds = []) {
  const dataDir = path.join(engineDir, "data");
  const candidates = [];
  const uniqueStoreIds = [...new Set(storeIds.filter(Boolean).map(sanitizeStoreId))];

  async function maybeAdd(filePath) {
    if (await pathExists(filePath)) candidates.push(filePath);
  }

  for (const storeId of uniqueStoreIds) {
    if (runId) {
      await maybeAdd(path.join(dataDir, storeId, "runs", runId, "manifest.json"));
    }
  }

  const storeRoots = uniqueStoreIds.length
    ? uniqueStoreIds.map((storeId) => path.join(dataDir, storeId))
    : (await pathExists(dataDir) ? (await fs.readdir(dataDir, { withFileTypes: true }))
      .filter((entry) => entry.isDirectory())
      .map((entry) => path.join(dataDir, entry.name)) : []);

  for (const storeRoot of storeRoots) {
    const runsDir = path.join(storeRoot, "runs");
    if (!(await pathExists(runsDir))) continue;
    const entries = await fs.readdir(runsDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const manifestPath = path.join(runsDir, entry.name, "manifest.json");
      if (!(await pathExists(manifestPath))) continue;
      if (!runId || entry.name === runId) candidates.push(manifestPath);
    }
  }

  const unique = [...new Set(candidates)];
  const withStat = await Promise.all(unique.map(async (filePath) => ({
    filePath,
    stat: await fs.stat(filePath),
  })));
  return withStat.sort((a, b) => b.stat.mtimeMs - a.stat.mtimeMs).map((item) => item.filePath);
}

async function readEngineRunFromManifest(manifestPath) {
  const manifest = await readJson(manifestPath);
  const engineRunRelPath = manifest?.artifacts?.engine_run;
  if (!engineRunRelPath) {
    throw new Error(`Manifest is missing artifacts.engine_run: ${manifestPath}`);
  }
  const engineRunPath = path.resolve(path.dirname(manifestPath), engineRunRelPath);
  const engineRun = await readJson(engineRunPath);

  return {
    manifest,
    engineRun,
    manifestPath,
    engineRunPath,
  };
}

async function runAtulEngine(input, options = {}) {
  const engineDir = path.resolve(options.engineDir || process.env.BEACONAI_ENGINE_DIR || defaultEngineDir());
  const pythonPath = process.env.BEACONAI_ENGINE_PYTHON || defaultPythonPath(engineDir);
  const runRoot = await fs.mkdtemp(path.join(os.tmpdir(), "beaconai-atul-engine-"));
  const outDir = path.join(runRoot, "out");
  const mplConfigDir = path.join(runRoot, "mpl");
  await fs.mkdir(outDir, { recursive: true });
  await fs.mkdir(mplConfigDir, { recursive: true });

  let ordersCsv;
  let exportedRows = 0;
  if (options.useFixture) {
    ordersCsv = path.join(engineDir, "tests", "fixtures", "synthetic", "healthy_beauty_240d_orders.csv");
  } else {
    ordersCsv = path.join(runRoot, "orders.csv");
    exportedRows = await writeOrdersCsv(input, ordersCsv);
  }

  const brand = input.shop?.shop_domain || input.shop?.raw?.name || options.shopDomain || "BeaconAI";
  const env = {
    ...process.env,
    ...ENGINE_FLAGS,
    MPLCONFIGDIR: mplConfigDir,
  };

  const result = await runProcess(
    pythonPath,
    ["-m", "src.main", "--orders", ordersCsv, "--brand", brand, "--out", outDir],
    { cwd: engineDir, env }
  );

  const receiptsDir = path.join(outDir, "receipts");
  const briefingPath = path.join(outDir, "briefings", `${brand}_briefing.html`);
  const legacyEngineRunPath = path.join(receiptsDir, "engine_run.json");
  const legacyEngineRun = await readJson(legacyEngineRunPath);
  const runSummary = await readJson(path.join(receiptsDir, "run_summary.json"));
  const manifestCandidates = await listManifestCandidates(engineDir, legacyEngineRun.run_id, [
    legacyEngineRun.store_id,
    brand,
    options.shopDomain,
  ]);

  let manifestResult = null;
  if (manifestCandidates[0]) {
    manifestResult = await readEngineRunFromManifest(manifestCandidates[0]);
  }

  const engineRun = manifestResult?.engineRun || legacyEngineRun;

  return {
    engineRun,
    manifest: manifestResult?.manifest || null,
    runSummary,
    artifacts: {
      runRoot,
      outDir,
      receiptsDir,
      briefingPath,
      manifestPath: manifestResult?.manifestPath || null,
      engineRunPath: manifestResult?.engineRunPath || legacyEngineRunPath,
      charts: runSummary.charts_abs || [],
      segments: runSummary.segments || [],
    },
    diagnostics: {
      useFixture: Boolean(options.useFixture),
      exportedRows,
      stdout: result.stdout,
      stderr: result.stderr,
    },
  };
}

module.exports = {
  runAtulEngine,
  writeOrdersCsv,
};
