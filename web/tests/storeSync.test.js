import "./setup.js";
import test from "node:test";
import assert from "node:assert/strict";
import { act, cleanup, renderHook } from "@testing-library/react";
import { useStoreSync } from "../src/useStoreSync.js";

test.afterEach(cleanup);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test("a stalled request becomes uncertain and a new completed sync recovers it", async () => {
  let latest = { latest: { syncRunId: 4, status: "complete" } };
  let refreshed = 0;
  const { result } = renderHook(() => useStoreSync({
    start: () => new Promise(() => {}), status: async () => latest,
    onStatus: () => {}, onComplete: async () => { refreshed++; }, pollMs: 10, timeoutMs: 20,
  }));
  await act(async () => { void result.current.run(4); await sleep(35); });
  assert.equal(result.current.phase, "uncertain");
  assert.equal(result.current.busy, true);
  assert.equal(refreshed, 0, "the previous completed sync is not this attempt");
  latest = { latest: { syncRunId: 5, status: "complete" } };
  await act(async () => { await result.current.check(); });
  assert.equal(result.current.phase, "complete");
  assert.equal(result.current.busy, false);
  assert.equal(refreshed, 1);
});

test("duplicate clicks do not start another sync and a failed run stays visible", async () => {
  let calls = 0;
  const { result } = renderHook(() => useStoreSync({
    start: () => { calls++; return new Promise(() => {}); },
    status: async () => ({ latest: { syncRunId: 7, status: "incomplete", validationFailures: [{ message: "Order history was truncated" }] } }),
    onStatus: () => {}, onComplete: async () => {}, timeoutMs: 20, pollMs: 10000,
  }));
  await act(async () => { void result.current.run(6); void result.current.run(6); await sleep(35); });
  assert.equal(calls, 1);
  assert.equal(result.current.phase, "failed");
  assert.match(result.current.message, /truncated/);
  assert.equal(result.current.busy, false);
});

test("an unreachable status check never claims the server stopped", async () => {
  const { result } = renderHook(() => useStoreSync({
    start: async () => { throw new Error("Network disconnected"); },
    status: async () => { throw new Error("Offline"); }, onStatus: () => {}, onComplete: async () => {},
  }));
  await act(async () => { await result.current.run(1); });
  assert.equal(result.current.phase, "uncertain");
  assert.match(result.current.checkError, /may still be working/);
});
