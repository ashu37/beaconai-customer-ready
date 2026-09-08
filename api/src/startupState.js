const { config } = require("./config");

// Which database this instance is actually pointed at — host, port and user
// only, never the password. An env var edited in the Render dashboard does not
// always restart the instance, so "the value I see in the dashboard" and "the
// value this process is using" can differ, and there is otherwise no way to
// tell them apart from outside.
function databaseTarget() {
  try {
    const url = new URL(config.databaseUrl);
    return {
      host: url.hostname,
      port: url.port || "5432",
      user: url.username || null,
      database: url.pathname.replace(/^\//, "") || null,
    };
  } catch (_) {
    return { host: null, port: null, user: null, database: null, malformedUrl: true };
  }
}

const state = {
  database: {
    status: "starting",
    ready: false,
    error: null,
    checkedAt: null,
    target: databaseTarget(),
  },
};

function markDatabaseReady() {
  state.database = {
    status: "ready",
    ready: true,
    error: null,
    checkedAt: new Date().toISOString(),
    target: databaseTarget(),
  };
}

function markDatabaseFailed(error) {
  state.database = {
    status: "error",
    ready: false,
    error: error.message,
    cause: error.cause?.message || null,
    checkedAt: new Date().toISOString(),
    target: databaseTarget(),
  };
}

function getStartupState() {
  return state;
}

module.exports = {
  getStartupState,
  markDatabaseReady,
  markDatabaseFailed,
};
