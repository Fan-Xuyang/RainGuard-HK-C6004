"""One bounded real-model run, isolated from the business database. Explicit opt-in only."""

import os, secrets, json
from pathlib import Path
import psycopg
from psycopg import sql
from langgraph.checkpoint.postgres import PostgresSaver
from .graph import build_graph, Bridge


def main():
    source = os.environ["CHECKPOINT_DATABASE_URL"]
    parent = source.rsplit("/", 1)[0]
    name = "rainguard_modelqa_" + secrets.token_hex(5)
    assert name.startswith("rainguard_modelqa_") and len(name) == 28
    test_url = parent + "/" + name
    with psycopg.connect(parent + "/postgres", autocommit=True) as c:
        c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        with PostgresSaver.from_conn_string(test_url) as saver:
            saver.setup()
            graph = build_graph(saver, Bridge())
            result = graph.invoke(
                {
                    "run_id": "real-model-check",
                    "question": "请查询SHA站从2025年开始日雨量至少100mm的真实记录，并读取SHA站trace_policy=exclude的已完成模型实验结果。请分别调用historical_events和model_results取得实际数值，以简体中文写一个带日期和来源的复核计划。不要生成虚构现场事实。",
                    "region": "沙田",
                    "facility": "隔离模型验收用的虚拟场地，非真实设施",
                    "mode": "snapshot",
                    "engine": "deepseek",
                },
                {
                    "configurable": {"thread_id": "real-model-check"},
                    "recursion_limit": 40,
                },
            )
            assert result["__interrupt__"][0].value["phase"] == "waiting_approval"
            tools = [t["tool"] for t in result["trace"]]
            assert "historical_events" in tools and "model_results" in tools
            report = {
                "passed": True,
                "model": os.getenv("DEEPSEEK_MODEL"),
                "phase": "waiting_approval",
                "tools": tools,
                "analysis": result["analysis"],
                "mode": "snapshot",
                "billable": True,
                "businessWrites": False,
            }
            Path("runtime/real-agent-check.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                json.dumps(
                    {k: v for k, v in report.items() if k != "analysis"},
                    ensure_ascii=False,
                )
            )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "passed": False,
                    "errorType": type(exc).__name__,
                    "providerStatus": getattr(exc, "status_code", None),
                    "keyPrinted": False,
                }
            )
        )
        raise SystemExit(1)
    finally:
        with psycopg.connect(parent + "/postgres", autocommit=True) as c:
            c.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


if __name__ == "__main__":
    main()
