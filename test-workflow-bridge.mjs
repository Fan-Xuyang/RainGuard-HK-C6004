import assert from "node:assert/strict";
import fs from "node:fs";
import { workflowBridge } from "./workflow-bridge.mjs";
const assets = {};
for (const name of ["snapshot", "knowledge", "history", "experiments"])
  assets["/data/" + name + ".json"] = {
    body: fs.readFileSync("hk-web/data/" + name + ".json", "utf8"),
  };
const env = {
  INTERNAL_WORKFLOW_TOKEN: "isolated-test-only-bridge-token-123456789",
};
const request = (data, auth = true) =>
  new Request("http://localhost/api/internal/workflow/tool", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(auth
        ? { Authorization: "Bearer " + env.INTERNAL_WORKFLOW_TOKEN }
        : {}),
    },
    body: JSON.stringify(data),
  });
const run = (data, auth = true) =>
  workflowBridge(request(data, auth), assets, env, () => {
    throw Error("snapshot test must not fetch network");
  });
assert.equal((await run({ operation: "catalog" }, false)).status, 401);
assert.equal((await run({ operation: "catalog" })).status, 200);
const knowledge = await (
  await run({
    name: "search_knowledge",
    arguments: { query: "暴雨" },
    mode: "snapshot",
  })
).json();
assert.ok(knowledge.result.citations.length);
assert.ok(knowledge.result.citations[0].url.startsWith("https://"));
const rain = await (
  await run({
    name: "compare_regions",
    arguments: { regions: ["沙田"] },
    mode: "snapshot",
  })
).json();
assert.equal(rain.result.origin, "snapshot");
assert.equal(rain.result.stale, true);
const window = await (
  await run({
    name: "weather_window",
    arguments: { region: "沙田", maximum_halfhour_mm: 1, duration_minutes: 60 },
    mode: "snapshot",
  })
).json();
assert.equal(window.result.blocked, true);
assert.equal(
  (await run({ name: "arbitrary_shell", arguments: {}, mode: "snapshot" }))
    .status,
  502,
);
console.log(
  "Enterprise bridge: authentication, allowlisted tools, real official knowledge/snapshot and stale-window blocking passed",
);
