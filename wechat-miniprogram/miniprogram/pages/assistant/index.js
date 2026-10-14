const s = require("../../utils/service");
Page({
  data: {
    question: "请核对沙田当前的雨量、降雨窗口和暴雨应对资料",
    agent: false,
    busy: false,
    answer: "",
    citations: [],
    trace: [],
    drafts: [],
    status: "",
    history: [],
  },
  onLoad() {
    this.alive = true;
    this.setData({ history: wx.getStorageSync("rg-chat") || [] });
  },
  onUnload() {
    this.alive = false;
    clearTimeout(this.pollTimer);
  },
  input(e) {
    this.setData({ question: e.detail.value });
  },
  mode(e) {
    this.setData({ agent: e.detail.value });
  },
  async send() {
    if (this.data.busy) return;
    const question = this.data.question.trim();
    if (!question || question.length > 2000) {
      s.toast("请输入不超过2000字的问题");
      return;
    }
    this.setData({
      busy: true,
      status: "正在核验来源…",
      answer: "",
      citations: [],
      trace: [],
      drafts: [],
    });
    const input = {
      question,
      region: s.config().region,
      mode: s.config().mode,
      history: this.data.history
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content.slice(0, 2200) })),
    };
    try {
      if (this.data.agent) {
        const { jobId } = await s.request("/api/mini/agent-jobs", {
          method: "POST",
          data: input,
        });
        this.setData({ status: "Agent 正在调用官方工具…" });
        await this.poll(jobId, question, 0);
      } else
        this.result(
          await s.request("/api/agent/inspect", {
            method: "POST",
            data: input,
          }),
          question,
        );
    } catch (e) {
      this.setData({ busy: false, status: e.message });
      s.toast(e);
    }
  },
  async poll(id, q, n) {
    if (!this.alive) return;
    if (n >= 65) {
      this.setData({ busy: false, status: "等待超过两分钟，请稍后重新提交" });
      return;
    }
    const j = await s.request("/api/mini/agent-jobs/" + id);
    if (j.state === "done") {
      this.result(j.result, q);
      return;
    }
    if (j.state === "failed") throw Error(j.error);
    this.pollTimer = setTimeout(
      () =>
        this.poll(id, q, n + 1).catch((e) => {
          if (this.alive) {
            this.setData({ busy: false, status: e.message });
            s.toast(e);
          }
        }),
      2000,
    );
  },
  result(r, q) {
    const history = [
      ...this.data.history,
      { role: "user", content: q },
      { role: "assistant", content: s.toSimple(r.answer) },
    ].slice(-20);
    wx.setStorageSync("rg-chat", history);
    this.setData({
      answer: s.toSimple(r.answer),
      citations: (r.citations || []).map((c, i) => ({
        ...c,
        id: c.id || "ref-" + i,
        title: s.toSimple(c.title || c.name || c.id),
        text: s.toSimple(c.excerpt || c.text || ""),
        url: c.url || c.source || "",
      })),
      trace: (r.toolTrace || []).map((t, i) => ({
        id: i,
        name: t.name || t.tool || "工具调用",
        text: s.toSimple(JSON.stringify(t, null, 2)),
      })),
      drafts: r.drafts || [],
      history,
      busy: false,
      status:
        s.toSimple(r.model) +
        " · " +
        s.time(r.generatedAt) +
        " · " +
        s.toSimple((r.context && r.context.mode) || ""),
    });
  },
  source(e) {
    if (e.currentTarget.dataset.url) s.copy(e.currentTarget.dataset.url);
  },
  draft(e) {
    const draft = this.data.drafts[+e.currentTarget.dataset.index];
    getApp().globalData.drafts.push(draft);
    wx.switchTab({ url: "/pages/workspace/index" });
  },
  clear() {
    wx.showModal({
      title: "清除本机对话？",
      content: "仅清除当前设备保存的助手对话。",
      success: (r) => {
        if (r.confirm) {
          wx.removeStorageSync("rg-chat");
          this.setData({
            history: [],
            answer: "",
            citations: [],
            trace: [],
            drafts: [],
          });
        }
      },
    });
  },
});
