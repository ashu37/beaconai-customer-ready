// The database boundary, applied and then checked.
//
// Row-level security alone is not a boundary: a table's owner and any role with
// BYPASSRLS ignore it, and a grant to Supabase's API roles (anon, authenticated)
// would expose a table through the Data API whatever the backend checks. So the
// controls are applied together and inspected together:
//
//   - the application role gets USAGE on clean/raw and DML on their tables, and
//     nothing else; it must not be a superuser, have BYPASSRLS, or own tables
//   - anon, authenticated and PUBLIC get nothing on clean/raw, now or for tables
//     created later
//   - every clean/raw table has row-level security enabled, with one policy, for
//     the application role only
//
// Applied by the owner connection at the end of initSchema. Inspected at startup
// (production refuses to report ready on a problem) and by
// `npm run security:db-check`.

const SCHEMAS = ["clean", "raw"];
const API_ROLES = ["anon", "authenticated"];
const POLICY = "beaconai_app_access";

function ident(name) {
  return `"${String(name).replace(/"/g, '""')}"`;
}

async function roleExists(query, role) {
  const { rows } = await query(`SELECT 1 FROM pg_roles WHERE rolname = $1`, [role]);
  return rows.length > 0;
}

async function applicationTables(query) {
  const { rows } = await query(
    `SELECT n.nspname AS schema, c.relname AS name
       FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relkind IN ('r', 'p') AND n.nspname = ANY($1)
      ORDER BY 1, 2`,
    [SCHEMAS]
  );
  return rows;
}

/**
 * Idempotent. Safe to run while the application still connects as the owner:
 * owners are not subject to row-level security, so enabling it changes nothing
 * for them until DATABASE_URL moves to the application role.
 */
async function applyAccessControls(query, { appRole }) {
  const schemas = SCHEMAS.map(ident).join(", ");

  await query(`REVOKE ALL ON SCHEMA ${schemas} FROM PUBLIC`);
  for (const role of API_ROLES) {
    if (!(await roleExists(query, role))) continue;
    await query(`REVOKE ALL ON SCHEMA ${schemas} FROM ${ident(role)}`);
    await query(`REVOKE ALL ON ALL TABLES IN SCHEMA ${schemas} FROM ${ident(role)}`);
    await query(`REVOKE ALL ON ALL SEQUENCES IN SCHEMA ${schemas} FROM ${ident(role)}`);
    await query(`REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ${schemas} FROM ${ident(role)}`);
    for (const kind of ["TABLES", "SEQUENCES", "FUNCTIONS"]) {
      await query(`ALTER DEFAULT PRIVILEGES IN SCHEMA ${schemas} REVOKE ALL ON ${kind} FROM ${ident(role)}`);
    }
  }

  const appRoleExists = appRole && await roleExists(query, appRole);
  if (appRoleExists) {
    const role = ident(appRole);
    await query(`GRANT USAGE ON SCHEMA ${schemas} TO ${role}`);
    await query(`GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ${schemas} TO ${role}`);
    await query(`GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA ${schemas} TO ${role}`);
    await query(`ALTER DEFAULT PRIVILEGES IN SCHEMA ${schemas} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${role}`);
    await query(`ALTER DEFAULT PRIVILEGES IN SCHEMA ${schemas} GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ${role}`);
  }

  for (const { schema, name } of await applicationTables(query)) {
    const table = `${ident(schema)}.${ident(name)}`;
    await query(`ALTER TABLE ${table} ENABLE ROW LEVEL SECURITY`);
    if (!appRoleExists) continue;
    const { rows } = await query(
      `SELECT roles::text[] AS roles FROM pg_policies WHERE schemaname = $1 AND tablename = $2 AND policyname = $3`,
      [schema, name, POLICY]
    );
    if (rows.length && rows[0].roles.length === 1 && rows[0].roles[0] === appRole) continue;
    if (rows.length) await query(`DROP POLICY ${ident(POLICY)} ON ${table}`);
    await query(`CREATE POLICY ${ident(POLICY)} ON ${table} FOR ALL TO ${ident(appRole)} USING (true) WITH CHECK (true)`);
  }
}

/**
 * What the boundary actually is, as seen from `query`'s connection. Values only
 * describe roles, grants and policies; no data is read.
 */
async function inspectDatabaseSecurity(query, { appRole }) {
  const runtime = (await query(
    `SELECT current_user AS name, r.rolsuper AS superuser, r.rolbypassrls AS bypass_rls
       FROM pg_roles r WHERE r.rolname = current_user`
  )).rows[0];
  const owned = (await query(
    `SELECT count(*)::int AS n FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = ANY($1) AND c.relkind IN ('r', 'p') AND pg_get_userbyid(c.relowner) = current_user`,
    [SCHEMAS]
  )).rows[0].n;

  const apiRoles = {};
  for (const role of API_ROLES) {
    if (!(await roleExists(query, role))) {
      apiRoles[role] = { exists: false };
      continue;
    }
    const usage = (await query(
      `SELECT nspname FROM pg_namespace WHERE nspname = ANY($1) AND has_schema_privilege($2, nspname, 'USAGE')`,
      [SCHEMAS, role]
    )).rows.map((r) => r.nspname);
    // has_table_privilege, not information_schema: the latter only lists grants
    // involving the current role, so run as the application role it would hide
    // a grant to anon.
    const grants = (await query(
      `SELECT count(*)::int AS n FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY($2) AND c.relkind IN ('r', 'p', 'v', 'm')
          AND has_table_privilege($1, c.oid, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')`,
      [role, SCHEMAS]
    )).rows[0].n;
    const policies = (await query(
      `SELECT count(*)::int AS n FROM pg_policies WHERE schemaname = ANY($1) AND $2 = ANY(roles)`,
      [SCHEMAS, role]
    )).rows[0].n;
    apiRoles[role] = { exists: true, schemaUsage: usage, tableGrants: grants, policies };
  }

  const tables = await applicationTables(query);
  const rlsOff = (await query(
    `SELECT n.nspname || '.' || c.relname AS name FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = ANY($1) AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity ORDER BY 1`,
    [SCHEMAS]
  )).rows.map((r) => r.name);
  const policies = (await query(
    `SELECT schemaname || '.' || tablename AS table, policyname, roles::text[] AS roles
       FROM pg_policies WHERE schemaname = ANY($1)`,
    [SCHEMAS]
  )).rows;
  const unexpectedPolicies = policies
    .filter((p) => p.policyname !== POLICY || p.roles.length !== 1 || p.roles[0] !== appRole)
    .map((p) => `${p.table}:${p.policyname}`);
  const tablesWithoutAppPolicy = tables
    .map((t) => `${t.schema}.${t.name}`)
    .filter((name) => !policies.some((p) => p.table === name && p.policyname === POLICY));

  return {
    appRole,
    appRoleExists: await roleExists(query, appRole),
    runtimeRole: { name: runtime.name, superuser: runtime.superuser, bypassRls: runtime.bypass_rls, ownsApplicationTables: owned },
    apiRoles,
    tables: tables.length,
    rlsDisabled: rlsOff,
    tablesWithoutAppPolicy,
    unexpectedPolicies,
  };
}

/** Human-readable problems; empty when the boundary holds. */
function databaseSecurityProblems(report) {
  const problems = [];
  const runtime = report.runtimeRole;
  if (runtime.superuser) problems.push(`The application connects as a superuser (${runtime.name}).`);
  if (runtime.bypassRls) problems.push(`The application role ${runtime.name} has BYPASSRLS.`);
  if (runtime.ownsApplicationTables > 0) problems.push(`The application role ${runtime.name} owns ${runtime.ownsApplicationTables} application table(s), so row-level security does not apply to it.`);
  if (runtime.name !== report.appRole) problems.push(`The application connects as ${runtime.name}, not ${report.appRole}.`);
  if (!report.appRoleExists) problems.push(`The role ${report.appRole} does not exist.`);
  for (const [role, info] of Object.entries(report.apiRoles)) {
    if (!info.exists) continue;
    if (info.schemaUsage.length) problems.push(`${role} can use schema(s): ${info.schemaUsage.join(", ")}.`);
    if (info.tableGrants) problems.push(`${role} holds ${info.tableGrants} table privilege(s) in clean/raw.`);
    if (info.policies) problems.push(`${role} is named in ${info.policies} policy(ies).`);
  }
  if (report.rlsDisabled.length) problems.push(`Row-level security is off on: ${report.rlsDisabled.join(", ")}.`);
  if (report.tablesWithoutAppPolicy.length) problems.push(`No application policy on: ${report.tablesWithoutAppPolicy.join(", ")}.`);
  if (report.unexpectedPolicies.length) problems.push(`Unexpected policies: ${report.unexpectedPolicies.join(", ")}.`);
  return problems;
}

module.exports = { API_ROLES, POLICY, SCHEMAS, applyAccessControls, databaseSecurityProblems, inspectDatabaseSecurity };
