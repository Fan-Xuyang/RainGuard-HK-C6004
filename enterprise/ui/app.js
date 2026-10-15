const $ = (s) => document.querySelector(s),
  esc = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
const simple = (s) =>
  String(s || "").replace(
    /[區觀灣龍黃東荃屯門離島葵青]/g,
    (c) =>
      ({
        區: "区",
        觀: "观",
        灣: "湾",
        龍: "龙",
        黃: "黄",
        東: "东",
        門: "门",
        離: "离",
        島: "岛",
      })[c] || c,
  );
const labels = {
    queued: "已排队",
    running: "Agent 执行中",
    retrying: "等待重试",
    failed: "执行失败",
    waiting_approval: "等待主管审批",
    waiting_field: "待现场核验",
    waiting_review: "等待独立复审",
    archived: "已归档",
  },
  roles = {
    admin: "管理员",
    supervisor: "主管",
    operator: "现场执行人",
    auditor: "审计员",
  };
let me,
  users = [],
  runs = [],
  tab = "runs",
  selected = null,
  detailRevision = "",
  uploaded = [],
  timer;
const time = (t) =>
  t
    ? new Date(t * 1000).toLocaleString("zh-CN", {
        timeZone: "Asia/Hong_Kong",
        hour12: false,
      }) + " HKT"
    : "—";
const badge = (status) =>
  `<span class="badge ${status === "failed" ? "red" : status.startsWith("waiting") ? "amber" : status === "running" ? "blue" : ""}">${esc(labels[status] || status)}</span>`;
function toast(s) {
  $("#toast").textContent = s;
  $("#toast").style.display = "block";
  clearTimeout(timer);
  timer = setTimeout(() => ($("#toast").style.display = "none"), 5000);
}
async function api(path, options = {}) {
  const r = await fetch(path, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });
  const d = await r.json().catch(() => ({ detail: "服务请求失败" }));
  if (!r.ok) {
    if (r.status === 401) {
      $("#appView").hidden = true;
      $("#loginView").hidden = false;
    }
    throw Error(
      typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail || d),
    );
  }
  return d;
}
const post = (path, data) =>
  api(path, { method: "POST", body: JSON.stringify(data || {}) });
const formData = (f) => Object.fromEntries(new FormData(f));
const username = (id) =>
  users.find((u) => u.id === id)?.username || id || "未指派";
async function loginReady() {
  me = await api("/api/me");
  document.querySelector("[data-tab=audit]").hidden = me.role === "operator";
  users = await api("/api/users");
  $("#loginView").hidden = true;
  $("#appView").hidden = false;
  $("#identity").textContent = me.username + " · " + roles[me.role];
  $("#modelBadge").textContent = me.modelConfigured
    ? "DeepSeek 已配置"
    : "来源核验可用 · 模型未配置";
  $("#regionInput").innerHTML = me.regions
    .map((r) => `<option value="${esc(r)}">${esc(simple(r))}</option>`)
    .join("");
  $('#engineInput option[value="deepseek"]').disabled = !me.modelConfigured;
  $("#newRun").hidden = me.role === "auditor";
  await refresh();
}
$("#loginForm").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await post("/api/auth/login", formData(e.target));
    e.target.reset();
    $("#loginError").textContent = "";
    await loginReady();
  } catch (x) {
    $("#loginError").textContent = x.message;
  }
};
$("#logout").onclick = async () => {
  try {
    await post("/api/auth/logout");
  } finally {
    location.reload();
  }
};
$("#newRun").onclick = () => $("#createDialog").showModal();
$("#passwordButton").onclick = () => $("#passwordDialog").showModal();
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-close]");
  if (b) $("#" + b.dataset.close).close();
});
$("#createForm").onsubmit = async (e) => {
  e.preventDefault();
  try {
    const r = await post("/api/runs", formData(e.target));
    $("#createDialog").close();
    e.target.reset();
    selected = r.id;
    tab = "runs";
    detailRevision = "";
    await refresh();
    toast("流程已提交，后台将持久化执行");
  } catch (x) {
    toast(x.message);
  }
};
$("#passwordForm").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await post("/api/auth/password", formData(e.target));
    location.reload();
  } catch (x) {
    toast(x.message);
  }
};
document.querySelectorAll("nav [data-tab]").forEach(
  (b) =>
    (b.onclick = () => {
      tab = b.dataset.tab;
      detailRevision = "";
      refresh().catch((x) => toast(x.message));
    }),
);
$("#refresh").onclick = () => {
  detailRevision = "";
  refresh().catch((x) => toast(x.message));
};
async function refresh() {
  if (!me) return;
  document
    .querySelectorAll("[data-tab]")
    .forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $("#pageName").textContent = {
    runs: "工作流中心",
    notices: "待办与超时",
    rules: "自动触发规则",
    team: "团队与权限",
    audit: "审计记录",
  }[tab];
  const loaded = await Promise.all([api("/api/runs"), api("/api/overview")]);
  runs = loaded[0];
  const stats = loaded[1];
  $("#metrics").innerHTML = [
    ["流程总数", stats.total],
    ["待人工处理", stats.waiting],
    ["执行 / 重试中", stats.active],
    ["已审核归档", stats.archived],
  ]
    .map(
      ([a, b]) =>
        `<div class="metric"><span>${a}</span><strong>${b}</strong></div>`,
    )
    .join("");
  if (tab === "runs") {
    if (!$("#runList"))
      $("#content").innerHTML =
        '<div class="split"><div><div class="card"><h3>团队工作流</h3><p class="muted small">最近200条记录，按最近更新排序。</p></div><div id="runList"></div></div><div id="detail"></div></div>';
    $("#runList").innerHTML =
      runs
        .map(
          (r) =>
            `<button class="run-item ${selected === r.id ? "selected" : ""}" data-run="${esc(r.id)}"><h3>${esc(r.title)}</h3>${badge(r.status)}<p class="run-meta">${esc(simple(r.region))} · ${esc(r.facility)}</p><span class="run-meta">${time(r.updated_at)}</span></button>`,
        )
        .join("") ||
      '<div class="card empty"><h3>从一次真实复核开始</h3><p>发起流程后，审批与现场核验会显示在这里。</p></div>';
    $("#runList")
      .querySelectorAll("[data-run]")
      .forEach(
        (b) =>
          (b.onclick = () => {
            selected = b.dataset.run;
            detailRevision = "";
            uploaded = [];
            refresh().catch((x) => toast(x.message));
          }),
      );
    if (selected) await loadDetail();
    else
      $("#detail").innerHTML =
        '<div class="card empty"><h3>让 Agent 处理信息，让人负责行动</h3><p>选择流程查看证据、责任人、审批和执行轨迹。</p></div>';
    return;
  }
  $("#content").innerHTML = '<div class="card" id="tabContent"></div>';
  if (tab === "team") {
    users = await api("/api/users");
    $("#tabContent").innerHTML =
      `<h2>独立账号，明确责任</h2><p class="muted">主管不能审批自己创建的流程；现场提交只对被指派人开放，归档需要独立主管复审。</p><table class="table"><tr><th>账号</th><th>角色</th><th>状态</th><th></th></tr>${users.map((u) => `<tr><td>${esc(u.username)}</td><td>${roles[u.role]}</td><td>${u.active ? "有效" : "已停用"}</td><td>${me.role === "admin" && u.id !== me.id && u.active ? `<button data-disable="${esc(u.id)}" class="secondary">停用</button>` : ""}</td></tr>`).join("")}</table>${me.role === "admin" ? '<h3>创建团队成员</h3><form id="userForm"><div class="formgrid"><label>实际成员账号<input name="username" required maxlength="80"></label><label>角色<select name="role"><option value="operator">现场执行人</option><option value="supervisor">主管</option><option value="auditor">审计员</option><option value="admin">管理员</option></select></label></div><label>初始密码（至少16字符）<input name="password" type="password" required minlength="16" maxlength="160"></label><button class="primary">创建账号</button></form>' : ""}`;
    if ($("#userForm"))
      $("#userForm").onsubmit = async (e) => {
        e.preventDefault();
        try {
          await post("/api/users", formData(e.target));
          await refresh();
          toast("账号已创建");
        } catch (x) {
          toast(x.message);
        }
      };
    document.querySelectorAll("[data-disable]").forEach(
      (b) =>
        (b.onclick = async () => {
          if (confirm("停用此账号并撤销其会话？")) {
            try {
              await post("/api/users/" + b.dataset.disable + "/disable");
              refresh();
            } catch (x) {
              toast(x.message);
            }
          }
        }),
    );
    return;
  }
  if (tab === "rules") {
    const rules = await api("/api/rules");
    $("#tabContent").innerHTML =
      `<h2>真实天气变化，触发人工责任链</h2><p class="muted">每5分钟核验在线地区雨量，只有未过期且达到阈值的官方观测才触发流程。同一规则、同一观测时间去重。阈值不代表官方暴雨信号或设施积水。</p>${rules.map((r) => `<div class="card"><h3>${esc(r.name)}</h3><p>${esc(simple(r.region))} · ${esc(r.facility)} · 地区一小时雨量上限 ≥ ${r.threshold} mm</p><span class="badge">${r.enabled ? "启用" : "已停用"}</span><p class="error small">${esc(r.last_error || "")}</p>${["admin", "supervisor"].includes(me.role) ? `<button class="secondary" data-rule="${esc(r.id)}">切换启用状态</button>` : ""}</div>`).join("") || '<div class="empty">尚未配置真实设施的触发规则</div>'}${["admin", "supervisor"].includes(me.role) ? `<form id="ruleForm"><h3>新增实际场地规则</h3><label>规则名称<input name="name" required maxlength="120"></label><div class="formgrid"><label>地区<select name="region">${me.regions.map((r) => `<option>${esc(r)}</option>`).join("")}</select></label><label>实际设施<input name="facility" required maxlength="200"></label></div><label>关注值（mm）<input name="threshold" type="number" min="1" max="200" required value="30"></label><button class="primary">启用规则</button></form>` : ""}`;
    if ($("#ruleForm"))
      $("#ruleForm").onsubmit = async (e) => {
        e.preventDefault();
        try {
          const d = formData(e.target);
          d.threshold = +d.threshold;
          await post("/api/rules", d);
          refresh();
        } catch (x) {
          toast(x.message);
        }
      };
    document.querySelectorAll("[data-rule]").forEach(
      (b) =>
        (b.onclick = async () => {
          try {
            await post("/api/rules/" + b.dataset.rule + "/toggle");
            refresh();
          } catch (x) {
            toast(x.message);
          }
        }),
    );
    return;
  }
  if (tab === "notices") {
    const n = await api("/api/notices");
    $("#tabContent").innerHTML =
      '<h2>待办与超时提醒</h2><p class="muted">站内持久化通知，不会自动向外部发送消息。当前阶段默认1小时后提醒。</p>' +
      n
        .map(
          (x) =>
            `<div class="card"><p>${esc(x.text)}</p><p class="muted small">${time(x.created_at)}</p><button class="secondary" data-notice="${esc(x.run_id)}">查看流程</button></div>`,
        )
        .join("");
    document.querySelectorAll("[data-notice]").forEach(
      (b) =>
        (b.onclick = () => {
          tab = "runs";
          selected = b.dataset.notice;
          detailRevision = "";
          refresh();
        }),
    );
    return;
  }
  if (tab === "audit") {
    const events = await api("/api/audit");
    $("#tabContent").innerHTML =
      '<h2>操作审计</h2><p class="muted">最近500条应用审计。记录由服务端写入，业务界面不提供删除入口。</p>' +
      eventList(events);
    return;
  }
}
function eventList(events) {
  return (
    '<div class="timeline">' +
    events
      .map(
        (e) =>
          `<div><b>${esc(e.kind)}</b> · ${esc(username(e.actor))}<time>${time(e.time)}</time><span class="muted">${esc(JSON.stringify(e.detail))}</span></div>`,
      )
      .join("") +
    "</div>"
  );
}
async function loadDetail() {
  const d = await api("/api/runs/" + selected),
    r = d.run,
    key = r.id + ":" + r.revision + ":" + r.status;
  if (key === detailRevision) return;
  detailRevision = key;
  const state = r.state || {},
    supervisor = ["admin", "supervisor"].includes(me.role);
  let action = "";
  if (r.status === "waiting_approval" && supervisor && r.creator !== me.id)
    action = `<label>指派现场执行人<select id="assignee"><option value="">请选择实际执行人</option>${users
      .filter((u) => u.active && u.role === "operator")
      .map((u) => `<option value="${esc(u.id)}">${esc(u.username)}</option>`)
      .join(
        "",
      )}</select></label><div class="actions"><button data-action="approve" class="primary">审批并指派</button><button data-action="rework" class="secondary">退回重新分析</button></div>`;
  if (
    r.status === "waiting_field" &&
    r.assignee === me.id &&
    me.role === "operator"
  )
    action =
      '<label>现场实际观察<textarea id="facts" maxlength="3000" placeholder="填写实际观察，不能用模型建议代替现场事实" required></textarea></label><div id="checks"><label class="check"><input type="checkbox">来源和时间已核对</label><label class="check"><input type="checkbox">实际现场已检查</label><label class="check"><input type="checkbox">负责人及后续安排已确认</label></div><label>现场照片（每张PNG/JPEG ≤ 2MB）<input type="file" id="photo" accept="image/png,image/jpeg"></label><p id="uploadStatus" class="muted small"></p><div class="actions"><button data-action="submit" class="primary">提交现场核验</button></div>';
  if (r.status === "waiting_field" && supervisor)
    action = `<label>重新指派执行人<select id="assignee">${users
      .filter((u) => u.active && u.role === "operator")
      .map((u) => `<option value="${esc(u.id)}">${esc(u.username)}</option>`)
      .join(
        "",
      )}</select></label><div class="actions"><button data-action="reassign" class="secondary">记录说明并重新指派</button></div>`;
  if (
    r.status === "waiting_review" &&
    supervisor &&
    ![r.creator, r.assignee].includes(me.id)
  )
    action =
      '<div class="actions"><button data-action="accept" class="primary">审核通过并归档</button><button data-action="return_field" class="secondary">退回现场补充</button></div>';
  if (r.status === "failed" && supervisor)
    action =
      '<div class="actions"><button data-action="retry" class="primary">修复配置后重试</button></div>';
  const phases = [
      "collect",
      "waiting_approval",
      "waiting_field",
      "waiting_review",
      "archived",
    ],
    pos = Math.max(0, phases.indexOf(r.status));
  $("#detail").innerHTML =
    `<div class="card"><div class="detailhead"><div><span class="eyebrow">DURABLE WORKFLOW / V${r.revision}</span><h2>${esc(r.title)}</h2></div>${badge(r.status)}</div><div class="stagebar">${phases.map((_, i) => `<span class="stage ${i < pos ? "done" : i === pos ? "active" : ""}"></span>`).join("")}</div><div class="facts"><div class="fact">实际地点<b>${esc(r.facility)} · ${esc(simple(r.region))}</b></div><div class="fact">当前执行人<b>${esc(username(r.assignee))}</b></div><div class="fact">创建者<b>${esc(username(r.creator))}</b></div><div class="fact">阶段到期时间<b>${time(r.due_at)}</b></div></div>${r.mode === "snapshot" ? '<div class="notice">历史快照流程：不代表当前天气；归档也不代表现场安全判断。</div>' : ""}<p class="bodytext">${esc(r.question)}</p><div class="actions"><button class="secondary" id="exportRun">导出流程与审计 JSON</button></div></div><div class="card"><h3>${r.engine === "deepseek" ? "Agent 分析（待人工核对）" : "官方来源核验（非模型回答）"}</h3><p class="bodytext">${esc(state.analysis || "后台正在处理。执行状态与重试记录见下方。")}</p><details><summary>官方证据与来源</summary><pre>${esc(JSON.stringify(state.evidence || {}, null, 2))}</pre></details><details><summary>工具调用轨迹</summary><pre>${esc(JSON.stringify(state.trace || [], null, 2))}</pre></details></div>${state.field ? `<div class="card"><h3>已提交的现场事实</h3><p class="bodytext">${esc(state.field.facts)}</p><p class="muted small">提交人 ${esc(username(state.field.actor))} · ${time(state.field.time)}</p>${(state.field.artifacts || []).map((a) => `<a href="/api/artifacts/${esc(a)}" target="_blank" rel="noopener">下载现场照片 ${esc(a.slice(0, 8))}</a><br>`).join("")}</div>` : ""}<div class="card"><h3>责任与下一步</h3>${action ? '<label>操作说明 / 审核意见<textarea id="decisionNote" maxlength="1200" required placeholder="记录本次操作的依据和意见"></textarea></label>' + action : '<p class="muted">' + (r.status === "archived" ? "流程已由人工审核归档。" : "请由当前阶段的授权人员操作。创建者不能自我审批，复审须独立于创建者与执行人。") + "</p>"}</div><div class="card"><h3>执行与审计时间线</h3>${eventList(d.events)}<details><summary>持久化任务与重试</summary><pre>${esc(JSON.stringify(d.jobs, null, 2))}</pre></details></div>`;
  $("#exportRun").onclick = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(
      new Blob([JSON.stringify(d, null, 2)], { type: "application/json" }),
    );
    a.download = "RainGuard-" + r.id + ".json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  $("#detail")
    .querySelectorAll("[data-action]")
    .forEach(
      (b) =>
        (b.onclick = async () => {
          const data = {
            revision: r.revision,
            action: b.dataset.action,
            note: $("#decisionNote").value,
            assignee: $("#assignee")?.value || null,
            facts: $("#facts")?.value || "",
            checks: [...document.querySelectorAll("#checks input")].map(
              (i) => i.checked,
            ),
            artifacts: uploaded,
          };
          try {
            b.disabled = true;
            await post("/api/runs/" + r.id + "/decide", data);
            detailRevision = "";
            uploaded = [];
            await refresh();
            toast("操作已记录，后台将从检查点继续");
          } catch (x) {
            b.disabled = false;
            toast(x.message);
          }
        }),
    );
  if ($("#photo"))
    $("#photo").onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (uploaded.length >= 5) {
        toast("每次现场提交最多5张照片");
        return;
      }
      const form = new FormData();
      form.append("file", file);
      try {
        const a = await api("/api/runs/" + r.id + "/artifacts", {
          method: "POST",
          body: form,
        });
        uploaded.push(a.id);
        $("#uploadStatus").textContent =
          "本次已上传 " +
          uploaded.length +
          " 张照片；提交现场核验后纳入责任记录。";
      } catch (x) {
        toast(x.message);
      }
    };
}
setInterval(() => {
  if (
    me &&
    tab === "runs" &&
    !document.querySelector("dialog[open]") &&
    !document.activeElement.matches("input,textarea,select")
  )
    refresh().catch(() => {});
}, 10000);
loginReady().catch(() => {});
