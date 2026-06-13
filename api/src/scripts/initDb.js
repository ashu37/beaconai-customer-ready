require("dotenv").config();
const { initSchema } = require("../schema");
const { pool } = require("../db");

initSchema()
  .then(() => {
    console.log("Database initialized");
  })
  .catch((err) => {
    console.error("Failed to initialize database", err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await pool.end();
  });
