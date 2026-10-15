import { chromium } from "playwright-core";
import fs from "node:fs";
import assert from "node:assert/strict";
const access = JSON.parse(fs.readFileSync("runtime/enterprise-qa-access.json"));
const base = "http://127.0.0.1:8110",
  out = "docs/screenshots/enterprise";
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
    "C:/Users/35348/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe",
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } }),
  errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const call = async (path, data) => {
  const r = await page.request.fetch(base + path, {
    method: data ? "POST" : "GET",
    ...(data ? { data } : {}),
  });
  assert.ok(r.ok(), path + " " + r.status());
  return r.json();
};
const login = async (username, password) => {
  await page.goto(base + "/enterprise/");
  await page.locator("#loginForm input[name=username]").fill(username);
  await page.locator("#loginForm input[name=password]").fill(password);
  await page.locator("#loginForm button").click();
  await page.locator("#appView").waitFor({ state: "visible" });
};
const waitStatus = async (id, status) => {
  for (let n = 0; n < 80; n++) {
    const r = (await call("/api/runs/" + id)).run;
    if (r.status === status) return r;
    if (r.status === "failed") throw Error("Workflow failed");
    await page.waitForTimeout(500);
  }
  throw Error("Workflow did not reach " + status);
};
try {
  await page.goto(base + "/enterprise/");
  await page.screenshot({ path: out + "/login-desktop.png", fullPage: true });
  await login(access.username, access.password);
  await page.screenshot({
    path: out + "/dashboard-desktop.png",
    fullPage: true,
  });
  for(const language of ["en","yue-HK","zh-CN"]){
    await page.locator('[data-language-picker]:visible').selectOption(language);
    assert.equal(await page.locator('html').getAttribute('lang'),language);
    if(language==='en')assert((await page.locator('nav button').allTextContents()).every(text=>!/[\u3400-\u9fff]/.test(text)));
    if(language!=='zh-CN')await page.screenshot({path:`docs/screenshots/multilingual/enterprise-${language}.png`,fullPage:false});
  }
  const tag = Date.now().toString(36),
    operatorName = "qa-field-" + tag,
    supervisorName = "qa-supervisor-" + tag,
    password = "isolated-browser-test-" + tag;
  let users = await call("/api/users");
  for (const [username, role] of [
    [operatorName, "operator"],
    [supervisorName, "supervisor"],
  ])
    if (!users.some((u) => u.username === username))
      await call("/api/users", { username, password, role });
  users = await call("/api/users");
  const operator = users.find((u) => u.username === operatorName).id;
  const { id } = await call("/api/runs", {
    title: "隔离验收流程 · 官方快照核验",
    region: "沙田",
    facility: "仅自动化验收使用的虚拟场地",
    question: "核对沙田暴雨应对的官方资料及降雨窗口",
    mode: "snapshot",
    engine: "evidence",
  });
  await waitStatus(id, "waiting_approval");
  await page.locator("#refresh").click();
  await page.locator(`[data-run="${id}"]`).click();
  await page.locator("#detail h2").waitFor();
  await page.screenshot({
    path: out + "/workflow-desktop.png",
    fullPage: true,
  });
  await Promise.all([
    page.waitForEvent("load"),
    page.locator("#logout").click(),
  ]);
  await login(supervisorName, password);
  await page.locator(`[data-run="${id}"]`).click();
  await page.locator("#assignee").selectOption(operator);
  await page
    .locator("#decisionNote")
    .fill("隔离验收：核对真实历史快照，不视为当前天气。");
  await page.locator("[data-action=approve]").click();
  await waitStatus(id, "waiting_field");
  await Promise.all([
    page.waitForEvent("load"),
    page.locator("#logout").click(),
  ]);
  await login(operatorName, password);
  await page.locator(`[data-run="${id}"]`).click();
  await page.locator("#facts").fill("隔离自动化验收文本；并非真实现场观察。");
  await page
    .locator("#decisionNote")
    .fill("仅验证角色授权和表单提交，不产生真实事故记录。");
  for (const c of await page.locator("#checks input").all()) await c.check();
  await page.locator("[data-action=submit]").click();
  await waitStatus(id, "waiting_review");
  await Promise.all([
    page.waitForEvent("load"),
    page.locator("#logout").click(),
  ]);
  await login(supervisorName, password);
  await page.locator(`[data-run="${id}"]`).click();
  await page
    .locator("#decisionNote")
    .fill("隔离验收通过，正式业务库未写入测试记录。");
  await page.locator("[data-action=accept]").click();
  await waitStatus(id, "archived");
  await page.locator("#refresh").click();
  await page.screenshot({
    path: out + "/archived-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: out + "/workflow-mobile.png", fullPage: true });
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  );
  assert.deepEqual(errors, []);
  console.log(
    "Browser QA passed: three-role approval/field/review/archive using genuine official frozen data; desktop/mobile responsive; no page exceptions. All writes were in isolated QA SQLite.",
  );
} finally {
  await browser.close();
}
