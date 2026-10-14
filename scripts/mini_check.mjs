import automator from "miniprogram-automator";
import fs from "node:fs";
import assert from "node:assert/strict";
fs.mkdirSync("runtime", { recursive: true });
let mini;
const results = [];
const timeout = setTimeout(() => {
  mini?.disconnect();
  console.error(
    "Simulator timeout: verify that the IDE simulator and base library have initialized. No simulator pass is recorded.",
  );
  process.exit(1);
}, 90000);
try {
  mini = await automator.connect({
    wsEndpoint: "ws://127.0.0.1:" + (process.env.MINI_AUTO_PORT || 9435),
  });
  mini.on("exception", (e) =>
    results.push({ exception: String(e.message || e) }),
  );
  // The simulator QA uses the genuine frozen source. No fake weather or model calls.
  await mini.evaluate(() => {
    const a = getApp();
    a.saveConfig({ ...a.globalData.config, mode: "snapshot" });
  });
  let p = await mini.reLaunch("/pages/home/index");
  await p.waitFor(500);
  let d = await p.data();
  assert.ok(d.sources.length >= 7);
  assert.equal(d.historical, true);
  results.push({ page: "home", sources: d.sources.length });
  await mini.screenshot({ path: "runtime/mini-home.png" });
  p = await mini.switchTab("/pages/observations/index");
  await p.waitFor(200);
  d = await p.data();
  assert.equal(d.rows.length, 36);
  results.push({ page: "observations", stations: d.rows.length });
  p = await mini.navigateTo("/pages/knowledge/index");
  await p.waitFor(200);
  d = await p.data();
  assert.equal(d.count, 22);
  assert.ok(d.results.length);
  results.push({
    page: "knowledge",
    documents: d.count,
    hits: d.results.length,
  });
  await mini.screenshot({ path: "runtime/mini-knowledge.png" });
  p = await mini.switchTab("/pages/assistant/index");
  await p.setData({ agent: false, question: "请核对沙田暴雨应对资料" });
  await p.callMethod("send");
  await p.waitFor(async () => !(await p.data()).busy);
  d = await p.data();
  assert.ok(d.answer.includes("未调用语言模型"));
  assert.ok(d.trace.length);
  results.push({
    page: "assistant",
    citations: d.citations.length,
    tools: d.trace.length,
  });
  // Workbench data should be empty or user-entered; avoid creating invented field records in the user's storage.
  p = await mini.switchTab("/pages/workspace/index");
  d = await p.data();
  assert.ok(Array.isArray(d.tasks));
  assert.equal(d.checkedFlags.length, 3);
  results.push({ page: "workspace", loaded: true });
  p = await mini.navigateTo("/pages/settings/index");
  d = await p.data();
  assert.ok(d.baseUrl.startsWith("http"));
  results.push({ page: "settings", loaded: true });
  await mini.evaluate(() => {
    const a = getApp();
    a.saveConfig({ ...a.globalData.config, mode: "live" });
  });
  await mini.reLaunch("/pages/home/index");
  fs.writeFileSync(
    "runtime/mini-check.json",
    JSON.stringify({ checkedAt: new Date().toISOString(), results }, null, 2),
  );
  console.log("Simulator checks passed:", JSON.stringify(results));
} catch (e) {
  console.error("Simulator checks failed:", e.message);
  process.exitCode = 1;
} finally {
  clearTimeout(timeout);
  mini?.disconnect();
}
