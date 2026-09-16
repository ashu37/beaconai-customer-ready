// Where the engine writes, in one place.
//
// This used to be resolved twice: the runner fell back to `<repo>/engine` when
// BEACONAI_ENGINE_DIR was unset, while store deletion skipped the filesystem
// entirely in that same configuration — so a deletion could report success and
// leave the engine's audience CSVs on disk. One resolver, used by both.

const path = require("node:path");

function repoRoot() {
  return path.resolve(__dirname, "../../..");
}

/** The engine's directory: the environment's, or the one beside this app. */
function engineDir(override = null) {
  return path.resolve(override || process.env.BEACONAI_ENGINE_DIR || path.join(repoRoot(), "engine"));
}

/** Where a store's runs live. */
function engineDataRoot(override = null) {
  return path.join(engineDir(override), "data");
}

/**
 * One store's directory, or null when `storeId` would escape the data root.
 * The id comes from our own column, but it becomes a path here, so it is
 * resolved and checked rather than trusted.
 */
function engineStoreDir(storeId, override = null) {
  const root = engineDataRoot(override);
  const dir = path.resolve(root, String(storeId));
  if (dir === root || !dir.startsWith(root + path.sep)) return null;
  return dir;
}

module.exports = { engineDataRoot, engineDir, engineStoreDir, repoRoot };
