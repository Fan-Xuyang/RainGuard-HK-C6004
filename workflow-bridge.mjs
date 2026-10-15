import { timingSafeEqual, createHash } from "node:crypto";
import {
  AGENT_TOOLS,
  executeAgentTool,
  readAgentJSON,
} from "./agent-tools.mjs";
export async function workflowBridge(request, assets, env, getPacket) {
  const secret = env.INTERNAL_WORKFLOW_TOKEN || "";
  if (secret.length < 32)
    return Response.json(
      { error: "Workflow bridge disabled" },
      { status: 503 },
    );
  const digest = (v) => createHash("sha256").update(v).digest();
  if (
    !timingSafeEqual(
      digest(secret),
      digest(
        request.headers.get("authorization")?.replace(/^Bearer /, "") || "",
      ),
    )
  )
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  if (request.method !== "POST")
    return Response.json({ error: "Method not allowed" }, { status: 405 });
  let input;
  try {
    input = await readAgentJSON(request, 16000);
  } catch {
    return Response.json({ error: "Invalid request" }, { status: 400 });
  }
  if (input.operation === "catalog")
    return Response.json({ tools: AGENT_TOOLS });
  if (!["live", "snapshot"].includes(input.mode))
    return Response.json({ error: "Invalid mode" }, { status: 400 });
  const packets = {},
    citations = [],
    drafts = [];
  const session = {
    assets,
    citations,
    drafts,
    packet: async (k) => {
      if (!packets[k])
        packets[k] =
          input.mode === "snapshot"
            ? {
                ...JSON.parse(assets["/data/snapshot.json"].body)[k],
                origin: "snapshot",
              }
            : { ...(await getPacket(k)), origin: "online" };
      return packets[k];
    },
  };
  try {
    return Response.json(
      {
        result: await executeAgentTool(input.name, input.arguments, session),
        citations,
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return Response.json(
      { error: "工具执行失败：参数无效或官方来源不可用，请核对来源后重试" },
      { status: 502 },
    );
  }
}
