import fs from "node:fs";
import path from "node:path";
import { REGIONS, nearestNowcast } from "../hk-web/core.mjs";
const root = "wechat-miniprogram/miniprogram";
fs.mkdirSync(root + "/data", { recursive: true });
fs.mkdirSync(root + "/utils", { recursive: true });
const snapshot = JSON.parse(
  fs.readFileSync("hk-web/data/snapshot.json", "utf8"),
);
snapshot.nowcast = {
  ...snapshot.nowcast,
  data: REGIONS.flatMap((r) =>
    nearestNowcast(snapshot.nowcast.data, r.lat, r.lon),
  ),
  derivation: "18地区中心最近网格；sha256指向原始官方文件",
};
for (const [name, data] of [
  ["snapshot", snapshot],
  [
    "knowledge",
    JSON.parse(fs.readFileSync("hk-web/data/knowledge.json", "utf8")),
  ],
])
  fs.writeFileSync(
    root + "/data/" + name + ".js",
    "module.exports=" + JSON.stringify(data) + ";\n",
  );
for (const [name, exports] of [
  [
    "core",
    "SOURCES,REGIONS,numeric,observationTime,isStale,regionRain,nearestNowcast,evaluate",
  ],
  ["retrieval", "tokens,retrieve"],
  ["simplify", "toSimple"],
]) {
  let source = fs.readFileSync("hk-web/" + name + ".mjs", "utf8");
  if (name === "simplify")
    source = source.slice(0, source.indexOf("export function simplifyPage"));
  source = source.replaceAll(".sort().at(-1)", ".sort().slice(-1)[0]");
  source = source
    .replace(
      /import \{toSimple\} from '.\/simplify.mjs';/,
      "const {toSimple}=require('./simplify');",
    )
    .replaceAll("export ", "");
  fs.writeFileSync(
    root + "/utils/" + name + ".js",
    source + "\nmodule.exports={" + exports + "};\n",
  );
}
function bytes(dir) {
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .reduce(
      (n, e) =>
        n +
        (e.isDirectory()
          ? bytes(path.join(dir, e.name))
          : fs.statSync(path.join(dir, e.name)).size),
      0,
    );
}
console.log(
  "Native bundle:",
  bytes(root),
  "bytes; documents:",
  JSON.parse(fs.readFileSync("hk-web/data/knowledge.json")).documents.length,
);
if (bytes(root) > 1900000)
  throw Error("Main package exceeds reserved size budget");
