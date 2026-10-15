import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { createMiniAgentJobs } from "./mini-agent-jobs.mjs";
import { validDocument } from "./workspace-store.mjs";
const require = createRequire(import.meta.url),
  storage = new Map(),
  app = {
    globalData: {
      config: {
        baseUrl: "http://localhost:8095",
        region: "沙田",
        mode: "live",
        actor: "Test",
      },
      packets: {},
      drafts: [],
    },
  };
global.getApp = () => app;
global.wx = {
  getStorageSync: (k) => storage.get(k),
  setStorageSync: (k, v) => storage.set(k, structuredClone(v)),
  showToast: () => {},
  request: ({ fail }) => fail(),
};
const s = require("./wechat-miniprogram/miniprogram/utils/service.js");
assert.equal(s.value("M"), "—");
assert.equal(s.value("0"), "0");
const packets = await s.load(["rain", "weather"]);
assert.equal(packets.rain.origin, "snapshot");
assert.equal(s.status("rain", packets.rain).stale, true);
assert.match(s.status("rain", packets.rain).time, /2026-10-12/);
const kb = require("./wechat-miniprogram/miniprogram/data/knowledge.js");
const {
  retrieve,
} = require("./wechat-miniprogram/miniprogram/utils/retrieval.js");
assert(kb.documents.length >= 44);
assert.ok(retrieve("暴雨", kb.documents, 6).length);
let page;
global.Page = (p) => {
  page = p;
};
require("./wechat-miniprogram/miniprogram/pages/workspace/index.js");
page.setData = (v) => Object.assign(page.data, v);
page.onShow();
page.setData({
  title: "Actual inspection",
  owner: "Tester",
  note: "Reviewed actual site",
  checked: ["0", "1", "2"],
});
page.save();
assert.ok(validDocument(s.document()));
page.finish();
assert.equal(s.document().workspace.tasks[0].status, "done");
page.newRecord();
page.setData({ title: "Missing checks", owner: "", note: "", checked: [] });
page.save();
page.finish();
assert.equal(s.document().workspace.tasks[0].status, "open");
assert.ok(validDocument(s.document()));
const post = (q) =>
  new Request("http://localhost/api/mini/agent-jobs", {
    method: "POST",
    body: JSON.stringify(q),
  });
let clock = 0,
  resolve;
const jobs = createMiniAgentJobs({
  configured: () => true,
  now: () => clock,
  ttl: 10,
  execute: () => new Promise((r) => (resolve = r)),
});
assert.equal(
  (await jobs.handle(post({ question: "", mode: "live" }))).status,
  400,
);
const submitted = await jobs.handle(post({ question: "Rain?", mode: "live" }));
assert.equal(submitted.status, 202);
const { jobId } = await submitted.json();
const poll = () =>
  jobs.handle(new Request("http://localhost/api/mini/agent-jobs/" + jobId));
assert.equal((await (await poll()).json()).state, "running");
resolve({ answer: "Verified" });
await new Promise((r) => setTimeout(r, 10));
assert.equal((await (await poll()).json()).result.answer, "Verified");
clock = 20;
assert.equal((await poll()).status, 404);
const unavailable = createMiniAgentJobs({
  configured: () => false,
  execute: () => {
    throw Error("must not run");
  },
});
assert.equal(
  (await unavailable.handle(post({ question: "Rain?", mode: "live" }))).status,
  503,
);
console.log(
  "Mini program: genuine snapshot fallback, retrieval, completion validation and asynchronous agent jobs passed",
);
