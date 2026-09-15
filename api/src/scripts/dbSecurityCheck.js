#!/usr/bin/env node
//
// Prints the database boundary as the application connection sees it: the
// runtime role, what Supabase's API roles can reach, row-level security and
// policies. Reads catalog metadata only, never table data.
//
//   npm run security:db-check
//
// Exits 1 when databaseSecurityProblems finds anything. Supabase's Data API
// "exposed schemas" setting is not visible from SQL; confirm it in the
// dashboard (Settings → API) as well.

require("dotenv").config();
const { config } = require("../config");
const { closePools, query } = require("../db");
const { databaseSecurityProblems, inspectDatabaseSecurity } = require("../services/databaseSecurity");

(async () => {
  const report = await inspectDatabaseSecurity(query, { appRole: config.appDbRole });
  const problems = databaseSecurityProblems(report);
  console.log(JSON.stringify({ report, problems }, null, 2));
  await closePools();
  process.exit(problems.length ? 1 : 0);
})().catch(async (error) => {
  console.error(`[security:db-check] ${error.message}`);
  await closePools().catch(() => {});
  process.exit(1);
});
