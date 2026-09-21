import test from "node:test";
import assert from "node:assert/strict";
import { triggerAll, triggerMonitor } from "../src/index.js";

test("both workflows are dispatched with the main branch", async () => {
  const calls = [];
  await triggerAll({ GITHUB_TOKEN: "test" }, async (url, options) => {
    calls.push(url);
    assert.equal(options.method, "POST");
    assert.deepEqual(JSON.parse(options.body), { ref: "main" });
    return new Response(null, { status: 204 });
  });
  assert.equal(calls.length, 2);
  assert.ok(calls.some(url => url.includes("/youtube-live-notify/")));
  assert.ok(calls.some(url => url.includes("/douyin-live-notify/")));
});

test("one project's authorization failure does not block the other", async () => {
  const calls = [];
  await assert.rejects(triggerAll({ GITHUB_TOKEN: "test" }, async url => {
    calls.push(url);
    return new Response(null, { status: url.includes("/youtube-live-notify/") ? 403 : 204 });
  }), AggregateError);
  assert.equal(calls.length, 2);
});

test("transient server failures retry, permanent errors do not", async () => {
  let attempts = 0;
  await triggerMonitor({ GITHUB_TOKEN: "test" }, "youtube-live-notify", async () =>
    new Response(null, { status: ++attempts === 1 ? 503 : 204 }));
  assert.equal(attempts, 2);
  attempts = 0;
  await assert.rejects(triggerMonitor({ GITHUB_TOKEN: "test" }, "youtube-live-notify", async () => {
    attempts++;
    return new Response(null, { status: 401 });
  }), /401/);
  assert.equal(attempts, 1);
});

test("missing credentials never dispatch", async () => {
  await assert.rejects(triggerAll({}, () => assert.fail("unexpected request")), AggregateError);
});
