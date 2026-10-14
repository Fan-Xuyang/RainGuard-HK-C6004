const s = require("../../utils/service");
Page({
  data: {
    regions: s.regions,
    regionIndex: 13,
    title: "",
    owner: "",
    note: "",
    checked: [],
    checkedFlags: [false, false, false],
    checks: [
      "核对官方来源及观测时间",
      "核对实际现场情况",
      "记录负责人和后续安排",
    ],
    tasks: [],
    facilities: [],
    facility: "",
    place: "",
    incidentNote: "",
    incidents: [],
    selected: "",
    photo: "",
    token: "",
    revision: null,
    busy: false,
    message: "记录保存在本机；共享同步需配置服务端口令。",
  },
  onShow() {
    this.doc = s.document();
    this.setData({
      regionIndex: s.regions.findIndex((r) => r.name === s.config().region),
      owner: s.config().actor || "",
    });
    const drafts = getApp().globalData.drafts;
    if (drafts.length) {
      const d = drafts.shift();
      this.setData({
        title: d.title,
        regionIndex: s.regions.findIndex((r) => r.name === d.region),
        selected: "",
        note: "",
        checked: [],
        checkedFlags: [false, false, false],
        photo: "",
      });
      s.toast("草稿已载入，请人工检查后创建");
    }
    this.render();
  },
  render() {
    this.setData({
      tasks: this.doc.workspace.tasks.map((t) => ({
        ...t,
        label: s.toSimple(t.region),
        statusLabel: { open: "待复核", working: "复核中", done: "已完成" }[
          t.status
        ],
        stamp: s.time(t.logs.length ? t.logs[t.logs.length - 1].time : null),
      })),
      facilities: this.doc.workspace.facilities.map((f) => ({
        ...f,
        label: s.toSimple(f.region),
      })),
      incidents: this.doc.incidents.map((i) => ({
        ...i,
        label: s.toSimple(i.region),
        stamp: s.time(i.time),
      })),
    });
  },
  input(e) {
    const f = e.currentTarget.dataset.field;
    this.setData({ [f]: e.detail.value });
    if (f === "token") getApp().globalData.sharedToken = e.detail.value;
  },
  region(e) {
    this.setData({ regionIndex: +e.detail.value });
  },
  check(e) {
    this.setData({
      checked: e.detail.value,
      checkedFlags: [0, 1, 2].map((i) => e.detail.value.includes(String(i))),
    });
  },
  persist() {
    s.saveDocument(this.doc);
    this.render();
  },
  save() {
    const title = this.data.title.trim(),
      owner = this.data.owner.trim(),
      note = this.data.note.trim();
    if (
      !title ||
      title.length > 240 ||
      owner.length > 100 ||
      note.length > 1200
    ) {
      s.toast("请检查标题、负责人和备注长度");
      return;
    }
    try {
      let task = this.doc.workspace.tasks.find(
        (t) => t.id === this.data.selected,
      );
      if (task && task.status === "done") {
        s.toast("已完成记录不可在此修改");
        return;
      }
      if (!task) {
        if (this.doc.workspace.tasks.length >= 200)
          throw Error("最多保存200个任务，请先导出整理");
        task = s.newTask(title, s.regions[this.data.regionIndex].name);
        this.doc.workspace.tasks.unshift(task);
      }
      Object.assign(task, {
        title,
        region: s.regions[this.data.regionIndex].name,
        owner,
        note,
        checks: this.data.checks.map((_, i) =>
          this.data.checked.includes(String(i)),
        ),
        ...(this.data.photo ? { attachment: this.data.photo } : {}),
      });
      task.logs.push({
        time: new Date().toISOString(),
        text: "人工保存复核记录",
      });
      this.persist();
      this.setData({ selected: task.id });
      s.toast("已保存到本机");
      return true;
    } catch (e) {
      s.toast(e);
      return false;
    }
  },
  select(e) {
    const t = this.doc.workspace.tasks.find(
      (t) => t.id === e.currentTarget.dataset.id,
    );
    this.setData({
      selected: t.id,
      title: t.title,
      owner: t.owner,
      note: t.note,
      regionIndex: s.regions.findIndex((r) => r.name === t.region),
      checked: t.checks.flatMap((v, i) => (v ? [String(i)] : [])),
      checkedFlags: t.checks,
      photo: t.attachment || "",
    });
  },
  newRecord() {
    this.setData({
      selected: "",
      title: "",
      note: "",
      photo: "",
      checked: [],
      checkedFlags: [false, false, false],
    });
  },
  finish() {
    const t = this.doc.workspace.tasks.find((t) => t.id === this.data.selected);
    if (!t) {
      s.toast("请先保存或选择任务");
      return;
    }
    if (t.status === "done") {
      s.toast("此记录已完成");
      return;
    }
    if (
      !this.data.owner.trim() ||
      !this.data.note.trim() ||
      this.data.checked.length !== 3
    ) {
      s.toast("请填写负责人、备注并完成三项核验");
      return;
    }
    if (!this.save()) return;
    if (!t.owner.trim() || !t.note.trim() || !t.checks.every(Boolean)) return;
    t.status = "done";
    t.logs.push({
      time: new Date().toISOString(),
      text: "由 " + t.owner + " 人工完成复核",
    });
    try {
      this.persist();
      s.toast("人工复核已完成");
    } catch (e) {
      s.toast(e);
    }
  },
  photo() {
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["camera", "album"],
      success: (r) => {
        const f = r.tempFiles[0];
        if (f.size > 700000) {
          s.toast("请选择700KB以下照片，以便保存与同步");
          return;
        }
        wx.getFileSystemManager().readFile({
          filePath: f.tempFilePath,
          encoding: "base64",
          success: (x) => {
            const jpeg = /\.jpe?g$/i.test(f.tempFilePath),
              png = /\.png$/i.test(f.tempFilePath);
            if (!jpeg && !png) {
              s.toast("仅支持JPEG或PNG");
              return;
            }
            this.setData({
              photo:
                "data:image/" + (jpeg ? "jpeg" : "png") + ";base64," + x.data,
            });
          },
          fail: () => s.toast("照片读取失败"),
        });
      },
      fail: () => {},
    });
  },
  facility() {
    const name = this.data.facility.trim();
    if (
      !name ||
      name.length > 120 ||
      this.doc.workspace.facilities.length >= 100
    ) {
      s.toast("请输入设施名称，最多100条");
      return;
    }
    this.doc.workspace.facilities.push({
      id: "facility-" + Date.now(),
      name,
      region: s.regions[this.data.regionIndex].name,
      notes: "",
      createdAt: new Date().toISOString(),
    });
    try {
      this.persist();
      this.setData({ facility: "" });
    } catch (e) {
      s.toast(e);
    }
  },
  incident() {
    const place = this.data.place.trim(),
      note = this.data.incidentNote.trim();
    if (
      !place ||
      !note ||
      place.length > 240 ||
      note.length > 2000 ||
      this.doc.incidents.length >= 200
    ) {
      s.toast("请填写实际地点和现场记录，最多200条");
      return;
    }
    this.doc.incidents.unshift({
      id: "incident-" + Date.now(),
      place,
      note,
      region: s.regions[this.data.regionIndex].name,
      kind: "人工现场记录",
      closed: false,
      time: new Date().toISOString(),
      weatherStatus: "人工录入；现场情况未经系统核验",
    });
    try {
      this.persist();
      this.setData({ place: "", incidentNote: "" });
    } catch (e) {
      s.toast(e);
    }
  },
  export() {
    const file =
      wx.env.USER_DATA_PATH + "/RainGuard-records-" + Date.now() + ".json";
    wx.getFileSystemManager().writeFile({
      filePath: file,
      data: JSON.stringify(this.doc, null, 2),
      encoding: "utf8",
      success: () => {
        if (wx.shareFileMessage)
          wx.shareFileMessage({
            filePath: file,
            fileName: "RainGuard-records.json",
            fail: () => s.toast("已备份到小程序本机文件目录"),
          });
        else s.toast("已备份到小程序本机文件目录");
      },
      fail: () => s.toast("备份失败"),
    });
  },
  async sync(e) {
    if (this.data.busy) return;
    const action = e.currentTarget.dataset.action,
      token = getApp().globalData.sharedToken;
    if (!token) {
      s.toast("请输入共享口令，口令仅在本次运行保存");
      return;
    }
    if (
      action === "push" &&
      (this.data.revision === null || !s.config().actor)
    ) {
      s.toast("请先载入共享版本并在设置中填写操作人");
      return;
    }
    if (action === "pull") {
      const ok = await new Promise((resolve) =>
        wx.showModal({
          title: "载入共享版本？",
          content: "将替换本机工作台。请先导出需要保留的本机记录。",
          success: (r) => resolve(r.confirm),
          fail: () => resolve(false),
        }),
      );
      if (!ok) return;
    }
    this.setData({ busy: true });
    try {
      if (action === "pull") {
        const r = await s.request("/api/workspace", { token });
        wx.setStorageSync("rg-document-backup", this.doc);
        s.saveDocument(r.document);
        this.doc = r.document;
        this.setData({
          revision: r.revision,
          message: "已载入共享版本 " + r.revision,
        });
        this.render();
      } else {
        const r = await s.request("/api/workspace", {
          method: "PUT",
          token,
          data: {
            revision: this.data.revision,
            actor: s.config().actor,
            document: this.doc,
          },
        });
        this.setData({
          revision: r.revision,
          message: "已同步共享版本 " + r.revision,
        });
      }
    } catch (e) {
      this.setData({ message: e.message });
      s.toast(e);
    } finally {
      this.setData({ busy: false });
    }
  },
});
