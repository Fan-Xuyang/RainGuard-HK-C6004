const s = require("../../utils/service");
const labels = {
  queued: "已排队",
  running: "Agent 执行中",
  retrying: "等待重试",
  failed: "执行失败",
  waiting_approval: "等待审批",
  waiting_field: "待现场核验",
  waiting_review: "等待复审",
  archived: "已归档",
};
Page({
  data: {
    base: "http://127.0.0.1:8100",
    username: "",
    password: "",
    user: null,
    rows: [],
    selected: null,
    regions: s.regions,
    regionIndex: 13,
    title: "",
    facility: "",
    question: "",
    snapshot: false,
    agent: false,
    note: "",
    facts: "",
    checked: [],
    operators: [],
    operatorIndex: 0,
    actions: [],
    trace: "",
    events: [],
    uploaded: [],
    busy: false,
  },
  onShow() {
    const draft = getApp().globalData.enterpriseDraft;
    if (draft) {
      this.setData({
        question: draft.question,
        regionIndex: s.regions.findIndex((r) => r.name === draft.region),
      });
      getApp().globalData.enterpriseDraft = null;
    }
    const session = getApp().globalData.enterpriseSession;
    if (session) {
      this.setData({ base: session.base, user: session.user });
      this.refresh();
    }
  },
  onPullDownRefresh() {
    this.refresh().finally(() => wx.stopPullDownRefresh());
  },
  input(e) {
    this.setData({ [e.currentTarget.dataset.field]: e.detail.value });
  },
  region(e) {
    this.setData({ regionIndex: +e.detail.value });
  },
  operator(e) {
    this.setData({ operatorIndex: +e.detail.value });
  },
  mode(e) {
    this.setData({ [e.currentTarget.dataset.field]: e.detail.value });
  },
  check(e) {
    this.setData({ checked: e.detail.value });
  },
  call(path, method = "GET", data) {
    return new Promise((resolve, reject) => {
      const session = getApp().globalData.enterpriseSession;
      wx.request({
        url: this.data.base.replace(/\/$/, "") + path,
        method,
        data,
        header: {
          "Content-Type": "application/json",
          ...(session ? { Authorization: "Bearer " + session.token } : {}),
        },
        success: (r) => {
          if (r.statusCode >= 200 && r.statusCode < 300) resolve(r.data);
          else {
            if (r.statusCode === 401) {
              getApp().globalData.enterpriseSession = null;
              this.setData({ user: null });
            }
            reject(
              Error(
                typeof r.data.detail === "string"
                  ? r.data.detail
                  : "操作失败，请检查输入及权限",
              ),
            );
          }
        },
        fail: () => reject(Error("无法连接企业工作流服务，请先启动 Docker")),
      });
    });
  },
  async login() {
    if (!/^https?:\/\/([A-Za-z0-9.-]+)(:\d{1,5})?\/?$/.test(this.data.base)) {
      s.toast("请输入不含路径的企业服务地址");
      return;
    }
    try {
      const r = await this.call("/api/auth/token", "POST", {
        username: this.data.username,
        password: this.data.password,
      });
      getApp().globalData.enterpriseSession = {
        base: this.data.base,
        token: r.token,
        user: { id: r.id, username: r.username, role: r.role },
      };
      this.setData({
        user: getApp().globalData.enterpriseSession.user,
        password: "",
      });
      await this.refresh();
    } catch (e) {
      s.toast(e);
    }
  },
  async logout() {
    try {
      await this.call("/api/auth/revoke", "POST");
    } catch {}
    getApp().globalData.enterpriseSession = null;
    this.setData({ user: null, password: "", rows: [], selected: null });
  },
  async refresh() {
    if (!this.data.user) return;
    try {
      const [rows, users] = await Promise.all([
        this.call("/api/runs"),
        this.call("/api/users"),
      ]);
      this.setData({
        rows: rows.map((r) => ({
          ...r,
          label: labels[r.status],
          region: s.toSimple(r.region),
        })),
        operators: users.filter((u) => u.role === "operator" && u.active),
      });
      if (this.data.selected) await this.open(this.data.selected.id);
    } catch (e) {
      s.toast(e);
    }
  },
  async create() {
    try {
      if (
        !this.data.title.trim() ||
        !this.data.facility.trim() ||
        !this.data.question.trim()
      )
        throw Error("请填写实际场地、标题和问题");
      const r = await this.call("/api/runs", "POST", {
        title: this.data.title,
        facility: this.data.facility,
        question: this.data.question,
        region: s.regions[this.data.regionIndex].name,
        mode: this.data.snapshot ? "snapshot" : "live",
        engine: this.data.agent ? "deepseek" : "evidence",
      });
      this.setData({ title: "", facility: "", question: "" });
      await this.refresh();
      await this.open(r.id);
    } catch (e) {
      s.toast(e);
    }
  },
  select(e) {
    this.open(e.currentTarget.dataset.id).catch(s.toast);
  },
  async open(id) {
    const d = await this.call("/api/runs/" + id),
      r = d.run,
      u = this.data.user,
      supervisor = ["admin", "supervisor"].includes(u.role);
    let actions = [];
    if (r.status === "waiting_approval" && supervisor && r.creator !== u.id)
      actions = [
        ["approve", "审批并指派"],
        ["rework", "退回重新分析"],
      ];
    if (
      r.status === "waiting_field" &&
      u.role === "operator" &&
      r.assignee === u.id
    )
      actions = [["submit", "提交现场核验"]];
    if (r.status === "waiting_field" && supervisor)
      actions = [["reassign", "重新指派执行人"]];
    if (
      r.status === "waiting_review" &&
      supervisor &&
      ![r.creator, r.assignee].includes(u.id)
    )
      actions = [
        ["accept", "复审通过归档"],
        ["return_field", "退回现场补充"],
      ];
    if (r.status === "failed" && supervisor)
      actions = [["retry", "修复配置后重试"]];
    this.setData({
      selected: { ...r, label: labels[r.status] },
      actions: actions.map(([action, label]) => ({ action, label })),
      trace: JSON.stringify(
        {
          evidence: r.state.evidence,
          tools: r.state.trace,
          field: r.state.field,
        },
        null,
        2,
      ),
      events: d.events.map((e) => ({
        ...e,
        stamp: s.time(new Date(e.time * 1000).toISOString()),
      })),
      note: "",
      facts: "",
      checked: [],
      uploaded: [],
    });
  },
  async decide(e) {
    if (this.data.busy) return;
    const action = e.currentTarget.dataset.action,
      r = this.data.selected;
    this.setData({ busy: true });
    try {
      await this.call("/api/runs/" + r.id + "/decide", "POST", {
        revision: r.revision,
        action,
        note: this.data.note,
        facts: this.data.facts,
        assignee:
          ["approve", "reassign"].includes(action) && this.data.operators.length
            ? this.data.operators[this.data.operatorIndex].id
            : null,
        checks: [0, 1, 2].map((i) => this.data.checked.includes(String(i))),
        artifacts: this.data.uploaded,
      });
      await this.refresh();
      s.toast("操作已记录，请刷新查看后台继续执行的结果");
    } catch (e) {
      s.toast(e);
    } finally {
      this.setData({ busy: false });
    }
  },
  photo() {
    if (this.data.uploaded.length >= 5) {
      s.toast("每次现场提交最多5张照片");
      return;
    }
    const session = getApp().globalData.enterpriseSession;
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      success: (r) => {
        if (r.tempFiles[0].size > 2000000) {
          s.toast("照片不能超过2MB");
          return;
        }
        wx.uploadFile({
          url:
            this.data.base +
            "/api/runs/" +
            this.data.selected.id +
            "/artifacts",
          filePath: r.tempFiles[0].tempFilePath,
          name: "file",
          header: { Authorization: "Bearer " + session.token },
          success: (r) => {
            try {
              const d = JSON.parse(r.data);
              if (r.statusCode !== 201) throw Error(d.detail || "上传失败");
              this.setData({ uploaded: [...this.data.uploaded, d.id] });
              s.toast("照片已上传，提交核验后纳入记录");
            } catch (e) {
              s.toast(e);
            }
          },
          fail: () => s.toast("上传失败"),
        });
      },
    });
  },
});
