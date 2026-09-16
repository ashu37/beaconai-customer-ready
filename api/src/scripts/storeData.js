#!/usr/bin/env node
//
// The founder's side of a data request. Each one names the store, so nothing
// here can act on "the current store" by accident.
//
//   npm run store:report  -- --shop acme.myshopify.com
//   npm run store:export  -- --shop acme.myshopify.com --out ./acme-export
//   npm run store:delete  -- --shop acme.myshopify.com --confirm acme.myshopify.com
//   npm run privacy:pending
//   npm run privacy:export  -- --request 12 --out ./exports
//   npm run privacy:deliver -- --request 12 --note "emailed the merchant"
//   npm run store:cleanup-files
//
// Deletion is irreversible and is not undone by re-installing: --confirm has to
// repeat the shop domain, so a wrong terminal or a stale scrollback does not
// erase a merchant.

const path = require("node:path");

const { pool } = require("../db");
const {
  countStoreData, deleteStoreData, exportStoreData, pendingFileCleanup, runFileCleanup,
} = require("../services/storeDataService");
const {
  pendingPrivacyRequests, recordDelivery, writeCustomerExport,
} = require("../services/privacyRequestService");

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
    const requests = await pendingPrivacyRequests(shop);
    const files = await pendingFileCleanup(shop);
    if (!requests.length && !files.length) return console.log("Nothing outstanding.");

    if (requests.length) {
      console.log(`${requests.length} privacy request(s) not yet completed:`);
      for (const r of requests) {
        console.log(`  #${r.id}  ${r.topic}  ${r.shop_domain}  received ${r.received_at.toISOString()}`);
        if (r.topic === "customers/data_request") {
          console.log(`        npm run privacy:export  -- --request ${r.id} --out ./exports`);
          console.log(`        npm run privacy:deliver -- --request ${r.id} --note "how it reached the merchant"`);
        }
      }
    }
    if (files.length) {
      console.log(`\n${files.length} deletion(s) whose engine files are still on disk:`);
      for (const f of files) {
        console.log(`  ${f.shop_domain}  store ${f.store_id}  recorded ${f.recorded_at.toISOString()}`);
        if (f.last_error) console.log(`        last error: ${f.last_error}`);
      }
      console.log(`  Retry with: npm run store:cleanup-files`);
    }
    process.exitCode = 1;
    return;
  }

  if (command === "cleanup-files") {
    const { removed, failed } = await runFileCleanup(shop);
    if (!removed.length && !failed.length) return console.log("No engine files are waiting to be removed.");
    for (const dir of removed) console.log(`Removed ${dir}`);
    for (const f of failed) console.error(`Could not remove ${f.dir}: ${f.error}`);
    if (failed.length) process.exitCode = 1;
    return;
  }

  if (command === "privacy-export" || command === "privacy-deliver") {
    const id = Number(arg("request"));
    if (!Number.isInteger(id)) {
      console.error("Name the request: --request 12  (see `npm run privacy:pending`)");
      process.exitCode = 1;
      return;
    }
    if (command === "privacy-export") {
      const { file, found } = await writeCustomerExport(id, path.resolve(arg("out") || "./exports"));
      console.log(found ? `Wrote ${file}` : `Wrote ${file} — no customer of that store matched the request.`);
      console.log(
        `\nThe request stays open until you record the delivery:\n` +
        `  npm run privacy:deliver -- --request ${id} --note "how it reached the merchant"`
      );
      return;
    }
    const done = await recordDelivery(id, arg("note"));
    console.log(`Request #${done.id} (${done.topic}) recorded as delivered at ${done.completed_at.toISOString()}.`);
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
    if (result.engineFileFailures.length) {
      // The rows are gone and these files are not. Said plainly, because a
      // deletion that reports success over files still on disk is the failure
      // this whole path exists to avoid.
      console.error(`\nThe database rows are deleted, but these files could NOT be removed:`);
      for (const f of result.engineFileFailures) console.error(`  ${f.dir}: ${f.error}`);
      console.error(`Fix the cause and run: npm run store:cleanup-files`);
      process.exitCode = 1;
    }
    console.log(`\nAfter:`);
    printCounts(await countStoreData(shop));
    return;
  }

  console.error("Usage: report | export | delete | pending | cleanup-files | privacy-export | privacy-deliver");
  process.exitCode = 1;
}

main()
  .catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  })
  .finally(() => pool.end());
