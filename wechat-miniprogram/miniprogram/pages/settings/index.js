const s = require("../../utils/service");
Page({
  data: {
    regions: s.regions,
    baseUrl: "",
    actor: "",
    regionIndex: 13,
    snapshot: false,
    status: "尚未检查",
  },
  onShow() {
    const c = s.config();
    this.setData({
      baseUrl: c.baseUrl,
      actor: c.actor,
      regionIndex: s.regions.findIndex((r) => r.name === c.region),
      snapshot: c.mode === "snapshot",
    });
  },
  input(e) {
    this.setData({ [e.currentTarget.dataset.field]: e.detail.value });
  },
  region(e) {
    this.setData({ regionIndex: +e.detail.value });
  },
  mode(e) {
    this.setData({ snapshot: e.detail.value });
  },
  save() {
    const base = this.data.baseUrl.trim().replace(/\/$/, "");
    if (
      !/^https?:\/\/([a-zA-Z0-9.-]+|\[[a-fA-F0-9:]+\])(:\d{1,5})?$/.test(base)
    ) {
      s.toast("请输入完整的 http(s) 服务地址，不含路径");
      return false;
    }
    getApp().saveConfig({
      baseUrl: base,
      actor: this.data.actor.trim().slice(0, 60),
      region: s.regions[this.data.regionIndex].name,
      mode: this.data.snapshot ? "snapshot" : "live",
    });
    s.toast("设置已保存");
    return true;
  },
  async check() {
    if (!this.save()) return;
    this.setData({ status: "正在连接…" });
    try {
      const [a, w] = await Promise.all([
        s.request("/api/assistant/status"),
        s.request("/api/workspace/status"),
      ]);
      this.setData({
        status:
          "连接成功 · DeepSeek " +
          (a.configured ? "已配置" : "未配置（来源核验可用）") +
          " · 共享工作台 " +
          (w.configured ? "已启用" : "未启用"),
      });
    } catch (e) {
      this.setData({ status: e.message });
    }
  },
  github() {
    s.copy("https://github.com/Fan-Xuyang/RainGuard-HK-C6004");
  },
});
