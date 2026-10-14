const {
  SOURCES,
  REGIONS,
  isStale,
  observationTime,
  numeric,
} = require("./core");
const { toSimple } = require("./simplify");
const frozen = require("../data/snapshot");
const config = () => getApp().globalData.config;
function request(route, { method = "GET", data, token } = {}) {
  return new Promise((resolve, reject) =>
    wx.request({
      url: config().baseUrl + route,
      method,
      data,
      timeout: 45000,
      header: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: "Bearer " + token } : {}),
      },
      success: (r) =>
        r.statusCode >= 200 && r.statusCode < 300
          ? resolve(r.data)
          : reject(
              new Error(
                toSimple(
                  (r.data && r.data.error) || "服务返回 " + r.statusCode,
                ),
              ),
            ),
      fail: () => reject(new Error("连接失败，请检查设置中的服务地址")),
    }),
  );
}
function time(v) {
  if (!v) return "未知";
  const d = new Date(v);
  if (!Number.isFinite(d.getTime())) return "未知";
  return (
    new Date(d.getTime() + 8 * 3600000)
      .toISOString()
      .slice(0, 16)
      .replace("T", " ") + " 香港时间"
  );
}
async function load(keys) {
  const app = getApp();
  await Promise.all(
    keys.map(async (key) => {
      let packet,
        origin,
        error = "";
      try {
        if (config().mode === "snapshot") {
          packet = frozen[key];
          origin = "snapshot";
        } else {
          packet = await request("/api/" + key);
          origin = "online";
        }
      } catch (e) {
        packet = frozen[key];
        origin = "snapshot";
        error = e.message;
      }
      app.globalData.packets[key] = { ...packet, origin, error };
    }),
  );
  return app.globalData.packets;
}
function status(key, p) {
  const stale = isStale(key, p);
  return {
    key,
    name: toSimple(SOURCES[key].name),
    source: p.source,
    time: time(observationTime(key, p.data) || p.receivedAt),
    label:
      p.origin === "snapshot"
        ? "历史快照"
        : stale
          ? "在线 · 已过期"
          : "在线 · 时效有效",
    stale: stale || p.origin === "snapshot",
    error: p.error,
  };
}
function value(v) {
  const n = numeric(v);
  return n === null ? "—" : String(n);
}
const regions = REGIONS.map((r) => ({ ...r, label: toSimple(r.name) }));
function toast(e) {
  wx.showToast({
    title: typeof e === "string" ? e : e.message || "操作失败",
    icon: "none",
    duration: 3500,
  });
}
function copy(url) {
  wx.setClipboardData({ data: url });
}
function empty() {
  return {
    workspace: {
      favorites: [],
      facilities: [],
      tasks: [],
      rules: { rain: 30, tide: 2.5 },
    },
    incidents: [],
  };
}
function document() {
  return wx.getStorageSync("rg-document") || empty();
}
function saveDocument(d) {
  try {
    wx.setStorageSync("rg-document", d);
  } catch {
    throw Error("本机存储已满，请先导出记录");
  }
}
function newTask(title, region) {
  const packets = getApp().globalData.packets,
    r = packets.weather;
  const rain =
    r &&
    r.data.rainfall &&
    r.data.rainfall.data.find((x) => x.place === region);
  return {
    id: "task-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8),
    title,
    region,
    status: "open",
    owner: "",
    note: "",
    checks: [false, false, false],
    logs: [{ time: new Date().toISOString(), text: "从小程序人工创建" }],
    evidence: {
      rain: rain ? numeric(rain.max) : null,
      rainTime: r ? observationTime("weather", r.data) : null,
      rainOrigin: r ? r.origin : "unavailable",
      warnings: Object.values((packets.warnings && packets.warnings.data) || {})
        .filter((x) => x.actionCode !== "CANCEL")
        .map((x) => x.name),
    },
  };
}
module.exports = {
  config,
  request,
  load,
  time,
  status,
  value,
  regions,
  toast,
  copy,
  toSimple,
  document,
  saveDocument,
  newTask,
};
