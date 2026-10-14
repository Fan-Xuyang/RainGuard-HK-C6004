import { randomUUID } from "node:crypto";
// Node server only: keep long model calls outside the mobile request lifetime.
export function createMiniAgentJobs({
  execute,
  configured,
  now = Date.now,
  capacity = 4,
  ttl = 600000,
}) {
  const jobs = new Map();
  let active = 0;
  const json = (body, status = 200) =>
    Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
  function cleanup() {
    for (const [id, j] of jobs)
      if (now() - j.createdAt > ttl && j.state !== "running") jobs.delete(id);
  }
  function pump() {
    for (const j of jobs.values()) {
      if (active >= capacity) break;
      if (j.state !== "queued") continue;
      j.state = "running";
      active++;
      Promise.resolve()
        .then(() => execute(j.input))
        .then(
          (result) => {
            j.result = result;
            j.state = "done";
          },
          () => {
            j.error = "助手执行失败，请稍后重试";
            j.state = "failed";
          },
        )
        .finally(() => {
          delete j.input;
          active--;
          pump();
        });
    }
  }
  return {
    async handle(request) {
      cleanup();
      const u = new URL(request.url);
      const origin = request.headers.get("origin");
      if (origin && origin !== u.origin)
        return json({ error: "跨站请求被拒绝" }, 403);
      if (u.pathname === "/api/mini/agent-jobs") {
        if (request.method !== "POST")
          return json({ error: "方法不支持" }, 405);
        if (!configured())
          return json(
            { error: "服务端尚未配置模型密钥，可使用来源核验模式" },
            503,
          );
        if (
          jobs.size >= 64 ||
          [...jobs.values()].filter((j) => j.state === "queued").length >= 20
        )
          return json({ error: "助手繁忙，请稍后重试" }, 429);
        let input;
        try {
          const reader = request.body.getReader();
          let size = 0;
          const chunks = [];
          while (true) {
            const r = await reader.read();
            if (r.done) break;
            size += r.value.length;
            if (size > 60000) {
              await reader.cancel();
              return json({ error: "请求过大" }, 413);
            }
            chunks.push(r.value);
          }
          input = JSON.parse(Buffer.concat(chunks).toString());
        } catch {
          return json({ error: "请求格式无效" }, 400);
        }
        if (
          typeof input.question !== "string" ||
          !input.question.trim() ||
          input.question.length > 2000 ||
          !["live", "snapshot"].includes(input.mode)
        )
          return json({ error: "问题或数据模式无效" }, 400);
        const id = randomUUID();
        jobs.set(id, { state: "queued", createdAt: now(), input });
        pump();
        return json({ jobId: id }, 202);
      }
      if (request.method !== "GET") return json({ error: "方法不支持" }, 405);
      const j = jobs.get(u.pathname.split("/").pop());
      return j
        ? json({ state: j.state, result: j.result, error: j.error })
        : json({ error: "任务不存在或已过期" }, 404);
    },
  };
}
