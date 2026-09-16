#!/usr/bin/env node
//
// The founder's side of a data request. Each one names the store, so nothing
// here can act on "the current store" by accident.
//
//   npm run store:report  -- --shop acme.myshopify.com
//   npm run store:export  -- --shop acme.myshopify.com --out ./acme-export
//   npm run store:delete  -- --shop acme.myshopify.com --confirm acme.myshopify.com
//   npm run privacy:pending
//
// Deletion is irreversible and is not undone by re-installing: --confirm has to
// repeat the shop domain, so a wrong terminal or a stale scrollback does not
// erase a merchant.

const path = require("node:path");

const { pool } = require("../db");
const { countStoreData, deleteStoreData, exportStoreData } = require("../services/storeDataService");
const { pendingPrivacyRequests } = require("../services/privacyRequestService");

function arg(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i === -1 ? null : process.argv[i + 1] || null;
}

function printCounts(counts) {
  const width = Math.max(...Object.keys(counts).map((k) => k.length));
  let total = 0;
  for (const [table, n] of Object.entries(counts)) {
    total += n;
    console.log(`  ${table.padEnd(width)}  ${String(n).padStart(7)}`);
  }
  console.log(`  ${"total".padEnd(width)}  ${String(total).padStart(7)}`);
}

async function main() {
  const command = process.argv[2];
  const shop = arg("shop");
  if (command === "pending") {
    const rows = await pendingPrivacyRequests(shop);
    if (!rows.length) return console.log("No privacy request is outstanding.");
    console.log(`${rows.length} privacy request(s) not yet completed:`);
    for (const r of rows) console.log(`  #${r.id}  ${r.topic}  ${r.shop_domain}  received ${r.received_at.toISOString()}`);
    process.exitCode = 1;
    return;
  }

  if (!shop) {
    console.error("Name the store: --shop acme.myshopify.com");
    process.exitCode = 1;
    return;
  }

  if (command === "report") {
    console.log(`What BeaconAI holds for ${shop}:`);
    printCounts(await countStoreData(shop));
    return;
  }

  if (command === "export") {
    const outDir = path.resolve(arg("out") || `./${shop.replace(/\W+/g, "-")}-export`);
    const manifest = await exportStoreData(shop, outDir);
    console.log(`Exported ${shop} to ${outDir}`);
    printCounts(manifest.counts);
    console.log(`\nAccess tokens are redacted. ${manifest.files.length} file(s) plus manifest.json.`);
    return;
  }

  if (command === "delete") {
    if (arg("confirm") !== shop) {
      console.error(
        `Refusing to delete ${shop}: repeat the shop domain to confirm.\n` +
        `  npm run store:delete -- --shop ${shop} --confirm ${shop}`
      );
      process.exitCode = 1;
      return;
    }
    console.log(`Deleting ${shop}. Before:`);
    printCounts(await countStoreData(shop));
    const result = await deleteStoreData(shop);
    console.log(`\nDeleted:`);
    printCounts(result.deleted);
    for (const [table, info] of Object.entries(result.retained)) {
      console.log(`\nKept ${info.rows} row(s) in ${table}: ${info.reason}.`);
    }
    if (result.engineFiles.length) console.log(`Removed engine files: ${result.engineFiles.join(", ")}`);
    console.log(`\nAfter:`);
    printCounts(await countStoreData(shop));
    return;
  }

  console.error("Usage: report | export | delete | pending (see the header of this file)");
  process.exitCode = 1;
}

main()
  .catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  })
  .finally(() => pool.end());
