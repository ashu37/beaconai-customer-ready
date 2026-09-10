const { spawn } = require("child_process");
const fs = require("fs/promises");
const os = require("os");
const path = require("path");
const { pool, query } = require("../db");
const { buildEngineInputSnapshot, snapshotToCsv } = require("./engineInputSnapshot");

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

// Find the manifest the engine just wrote for THIS run. We pass `--brand` to the
// engine ourselves, so sanitizeStoreId(brand) is the directory it wrote under —
// no guessing, and no scanning of other stores' directories.
//
// `notBeforeMs` is the time the engine process started: without it, an engine
// that exits 0 but writes nothing would silently hand back the PREVIOUS run, and
// the merchant would see a stale briefing presented as fresh.
async function newestManifestForStore(engineDir, storeId, notBeforeMs = 0) {
  const runsDir = path.join(engineDir, "data", storeId, "runs");
  if (!(await pathExists(runsDir))) return null;

  const entries = await fs.readdir(runsDir, { withFileTypes: true });
  const candidates = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const manifestPath = path.join(runsDir, entry.name, "manifest.json");
    if (!(await pathExists(manifestPath))) continue;
    const { mtimeMs } = await fs.stat(manifestPath);
    if (mtimeMs >= notBeforeMs) candidates.push({ manifestPath, mtimeMs });
  }
  if (!candidates.length) return null;

  candidates.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return candidates[0].manifestPath;
}

async function readEngineRunFromManifest(manifestPath) {
  const manifest = await readJson(manifestPath);
  const engineRunRelPath = manifest?.artifacts?.engine_run;
  if (!engineRunRelPath) {
    throw new Error(`Manifest is missing artifacts.engine_run: ${manifestPath}`);
  }
  // Resolve relative to the manifest's own directory (../<run_id>.json).
  const engineRunPath = path.resolve(path.dirname(manifestPath), engineRunRelPath);
  const engineRun = await readJson(engineRunPath);
  return { manifest, engineRun, manifestPath };
}

// Read the customer_id column from an engine audience CSV. Header is
// `customer_id,aov_individual,predicted_segment,rank_score`; we take ONLY
// customer_id — aov_individual is hardcoded 0.0 upstream and predicted_segment
// is never a merchant-facing figure.
function parseCustomerIds(csvText) {
  const lines = String(csvText || "").split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length <= 1) return []; // header-only or empty
  const header = lines[0].split(",").map((cell) => cell.trim());
  const idIndex = header.indexOf("customer_id");
  if (idIndex === -1) return [];

  const ids = [];
  for (let i = 1; i < lines.length; i += 1) {
    const id = (lines[i].split(",")[idIndex] || "").trim();
    if (id) ids.push(id);
  }
  return ids;
}

// Read every audience CSV the manifest points at, so the whole run can be
// written in one transaction. SUBSTRATE_REFUSED / NOT_MATERIALIZED entries are
// kept too, with an empty list — a typed absence has to stay auditable (RULE B),
// never silently vanish.
async function readAudiencesFromManifest(manifest, manifestPath) {
  const entries = manifest?.artifacts?.audiences || [];
  const audiences = [];

  for (const entry of entries) {
    if (!entry.audience_definition_id) continue;
    let customerIds = [];
    if (entry.path) {
      try {
        const csvPath = path.resolve(path.dirname(manifestPath), entry.path);
        customerIds = parseCustomerIds(await fs.readFile(csvPath, "utf8"));
      } catch (_) {
        customerIds = []; // unreadable CSV → empty membership; status still recorded
      }
    }
    audiences.push({
      audienceDefinitionId: entry.audience_definition_id,
      playId: entry.play_id || "",
      status: entry.audience_materialization_status || "UNKNOWN",
      customerIds,
    });
  }

  return audiences;
}

// Write the run to Postgres. The engine's own output directory is ephemeral on
// Render, so this row — not engine/data/ — is what the app reads from afterwards.
//
// All-or-nothing: a snapshot without its audiences would look like a run whose
// plays have no auditable audience, which is indistinguishable from the engine
// deciding not to materialize one. Failing the run is better than persisting
// that ambiguity.
async function persistRunSnapshot({ shopDomain, storeId, engineRun, manifest, manifestPath, syncRunId, inputProvenance }) {
  const runId = engineRun?.run_id || manifest?.run_id;
  if (!runId) throw new Error("Engine run has no run_id; refusing to persist.");

  const audiences = await readAudiencesFromManifest(manifest, manifestPath);
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      `INSERT INTO clean.engine_run_snapshots
         (run_id, shop_domain, store_id, schema_version, engine_run, manifest,
          sync_run_id, input_provenance)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       ON CONFLICT (run_id) DO NOTHING`,
      [
        runId,
        shopDomain,
        storeId,
        engineRun?.schema_version || null,
        JSON.stringify(engineRun),
        manifest ? JSON.stringify(manifest) : null,
        syncRunId || null,
        inputProvenance || null,
      ]
    );

    for (const audience of audiences) {
      await client.query(
        `INSERT INTO clean.engine_audiences
           (run_id, audience_definition_id, play_id, materialization_status, customer_ids)
         VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (run_id, audience_definition_id) DO NOTHING`,
        [runId, audience.audienceDefinitionId, audience.playId, audience.status, audience.customerIds]
      );
    }

    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    throw error;
  } finally {
    client.release();
  }

  return runId;
}

async function runAtulEngine(input, options = {}) {
  const engineDir = path.resolve(options.engineDir || process.env.BEACONAI_ENGINE_DIR || defaultEngineDir());
  const pythonPath = process.env.BEACONAI_ENGINE_PYTHON || defaultPythonPath(engineDir);
  const runRoot = await fs.mkdtemp(path.join(os.tmpdir(), "beaconai-atul-engine-"));

  try {
    const outDir = path.join(runRoot, "out");
    const mplConfigDir = path.join(runRoot, "mpl");
    await fs.mkdir(outDir, { recursive: true });
    await fs.mkdir(mplConfigDir, { recursive: true });

    // The briefing is built from the immutable snapshot the sync published, not
    // from a fresh read of the clean tables. Those tables are mutable: a sync
    // running alongside this one would otherwise leave the analysis reading a
    // store that is half old and half new, with nothing recording which.
    // `options.snapshot` is that published input; falling back to projecting
    // `input` here keeps fixture and legacy callers working, and both are
    // labelled as such on the row rather than passed off as verified.
    const snapshot = options.snapshot || buildEngineInputSnapshot(input);

    let ordersCsv;
    if (options.useFixture) {
      ordersCsv = path.join(engineDir, "tests", "fixtures", "synthetic", "healthy_beauty_240d_orders.csv");
    } else {
      ordersCsv = path.join(runRoot, "orders.csv");
      await fs.writeFile(ordersCsv, snapshotToCsv(snapshot), "utf8");
    }

    const brand = snapshot.shop?.shop_domain || input?.shop?.shop_domain || input?.shop?.raw?.name || options.shopDomain || "BeaconAI";
    const storeId = sanitizeStoreId(brand);
    const env = {
      ...process.env,
      ...ENGINE_FLAGS,
      MPLCONFIGDIR: mplConfigDir,
    };

    // Filesystem mtimes have 1s granularity on some systems; step back a second
    // so a run that finishes fast is not excluded by its own start time.
    const startedAtMs = Date.now() - 1000;
    await runProcess(
      pythonPath,
      ["-m", "src.main", "--orders", ordersCsv, "--brand", brand, "--out", outDir],
      { cwd: engineDir, env }
    );

    // The engine's canonical output lives under engine/data/<store_id>/runs/,
    // outside the temp dir. `receipts/engine_run.json` in outDir is the legacy
    // mutable mirror and is deliberately not read (engine CLAUDE.md).
    const manifestPath = await newestManifestForStore(engineDir, storeId, startedAtMs);
    if (!manifestPath) {
      throw new Error(`Engine exited 0 but wrote no new manifest for store "${storeId}".`);
    }

    const { manifest, engineRun } = await readEngineRunFromManifest(manifestPath);
    const shopDomain = options.shopDomain || brand;
    const inputProvenance = options.useFixture
      ? "fixture"
      : options.syncRunId
        ? "verified"
        : "legacy_unverified";
    const runId = await persistRunSnapshot({
      shopDomain, storeId, engineRun, manifest, manifestPath,
      syncRunId: options.useFixture ? null : options.syncRunId,
      inputProvenance,
    });

    return {
      engineRun,
      manifest,
      runId,
      storeId,
      syncRunId: options.useFixture ? null : options.syncRunId || null,
      inputProvenance,
      artifacts: { manifestPath },
    };
  } finally {
    // The temp dir holds only the orders CSV and the legacy mirror; the run
    // itself is already in Postgres and under engine/data/. Leaving these behind
    // filled the container's /tmp one briefing at a time.
    await fs.rm(runRoot, { recursive: true, force: true }).catch(() => {});
  }
}

// O1: read-only latest-run rehydration. MUST NEVER trigger an engine run.
// Reads Postgres, not the filesystem — the engine's output directory does not
// survive a container restart, and it was keyed on a store id derived from the
// brand, which does not always match the shop domain we look up by.
function rowToRun(row) {
  return {
    runId: row.run_id,
    storeId: row.store_id,
    engineRun: row.engine_run,
    manifest: row.manifest,
    narration: row.narration,
    syncRunId: row.sync_run_id,
    inputProvenance: row.input_provenance || (row.sync_run_id == null ? "legacy_unverified" : "verified"),
    // When the analysis ran — distinct from when the store was last synced.
    createdAt: row.created_at,
    currency: row.currency || null,
  };
}

// The shop's currency rides along: the engine's dollar figures are in the
// store's own currency, and the presenter no longer assumes USD.
const RUN_SELECT = `SELECT r.run_id, r.store_id, r.engine_run, r.manifest, r.narration, r.sync_run_id,
                           r.input_provenance, r.created_at, s.currency
                      FROM clean.engine_run_snapshots r
                      LEFT JOIN clean.shop s ON s.shop_domain = r.shop_domain`;

async function readLatestRun({ shopDomain } = {}) {
  if (!shopDomain) return null;
  const { rows } = await query(
    `${RUN_SELECT} WHERE r.shop_domain = $1 ORDER BY r.created_at DESC LIMIT 1`,
    [shopDomain]
  );
  return rows.length ? rowToRun(rows[0]) : null;
}

// A specific run — a campaign's ORIGINATING run, not today's. Scoped to the
// shop, so a run id alone cannot read another store's analysis.
async function readRunById({ shopDomain, runId } = {}) {
  if (!shopDomain || !runId) return null;
  const { rows } = await query(`${RUN_SELECT} WHERE r.shop_domain = $1 AND r.run_id = $2`, [shopDomain, runId]);
  return rows.length ? rowToRun(rows[0]) : null;
}

async function narrateAtulRun(result, options = {}) {
  const manifestPath = result?.artifacts?.manifestPath;
  const runId = result?.runId || result?.engineRun?.run_id || result?.manifest?.run_id;
  if (!manifestPath || !runId) return null;

  const engineDir = path.resolve(options.engineDir || process.env.BEACONAI_ENGINE_DIR || defaultEngineDir());
  const pythonPath = process.env.BEACONAI_ENGINE_PYTHON || defaultPythonPath(engineDir);
  const storeDir = result?.storeId || path.basename(path.dirname(path.dirname(path.dirname(manifestPath))));
  const dataRoot = path.join(engineDir, "data");

  const code = `
import contextlib
import io
import json
from src.mcp.narration.server import narrate_run_payload

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    payload = narrate_run_payload(${JSON.stringify(storeDir)}, ${JSON.stringify(runId)}, data_root=${JSON.stringify(dataRoot)})
print(json.dumps(payload))
`;

  const output = await runProcess(pythonPath, ["-c", code], { cwd: engineDir, env: process.env });
  const narration = JSON.parse(output.stdout);

  // Narration is a pure function of the run's typed atoms, so it is immutable
  // per run. Store it on the run's own row and serve that copy on every
  // rehydrate — same run, same prose, no second LLM call, no TTL. Only a new
  // run (new run_id → new row) re-narrates.
  if (narration && !narration.error) {
    await query(
      `UPDATE clean.engine_run_snapshots SET narration = $2 WHERE run_id = $1`,
      [runId, JSON.stringify(narration)]
    );
  }

  return narration;
}

module.exports = {
  narrateAtulRun,
  readLatestRun,
  readRunById,
  runAtulEngine,
};
