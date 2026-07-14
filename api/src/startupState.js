const state = {
  database: {
    status: "starting",
    ready: false,
    error: null,
    checkedAt: null,
  },
};

function markDatabaseReady() {
  state.database = {
    status: "ready",
    ready: true,
    error: null,
    checkedAt: new Date().toISOString(),
  };
}

function markDatabaseFailed(error) {
  state.database = {
    status: "error",
    ready: false,
    error: error.message,
    checkedAt: new Date().toISOString(),
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
