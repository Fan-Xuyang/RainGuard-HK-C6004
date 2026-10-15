"""Actual PostgreSQL/LangGraph/Node integration, in a disposable dedicated database."""

import os, secrets
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres import PostgresSaver
from .api import create_app
from .graph import build_graph, Bridge
from .worker import work_one
from .db import connect


def main():
    source = os.environ["CHECKPOINT_DATABASE_URL"]
    name = "rainguard_qa_" + secrets.token_hex(6)
    assert name.startswith("rainguard_qa_") and len(name) == 25
    parent = source.rsplit("/", 1)[0]
    test_url = parent + "/" + name
    with psycopg.connect(parent + "/postgres", autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    engine = None
    try:
        app = create_app(test_url.replace("postgresql://", "postgresql+psycopg://"))
        factory = app.state.factory
        engine = factory.kw["bind"]
        password = os.environ["BOOTSTRAP_ADMIN_PASSWORD"]
        with TestClient(app) as admin:
            assert (
                admin.post(
                    "/api/auth/login", json={"username": "admin", "password": password}
                ).status_code
                == 200
            )
            role_ids = {}
            for username, role in [
                ("qa-operator", "operator"),
                ("qa-supervisor", "supervisor"),
            ]:
                r = admin.post(
                    "/api/users",
                    json={"username": username, "password": password, "role": role},
                )
                assert r.status_code == 201
                r.raise_for_status()
                role_ids[role] = r.json()["id"]
            r = admin.post(
                "/api/runs",
                json={
                    "title": "PostgreSQL isolated integration",
                    "facility": "Isolated test fixture, not a real property",
                    "question": "暴雨应对官方资料",
                    "region": "沙田",
                    "mode": "snapshot",
                    "engine": "evidence",
                },
            )
            assert r.status_code == 201
            rid = r.json()["id"]
            with PostgresSaver.from_conn_string(test_url) as saver:
                saver.setup()
                g = build_graph(saver, Bridge())
                assert work_one(factory, g, engine)
            detail = admin.get("/api/runs/" + rid).json()
            assert detail["run"]["status"] == "waiting_approval"
            state = detail["run"]["state"]
            assert state["evidence"]["search_knowledge"]["citations"]
            assert state["evidence"]["compare_regions"]["origin"] == "snapshot"
            assert state["evidence"]["weather_window"]["blocked"] is True
            with TestClient(app) as supervisor, TestClient(app) as operator:
                for c, u in [(supervisor, "qa-supervisor"), (operator, "qa-operator")]:
                    assert (
                        c.post(
                            "/api/auth/login",
                            json={"username": u, "password": password},
                        ).status_code
                        == 200
                    )
                for client, action, extra in [
                    (supervisor, "approve", {"assignee": role_ids["operator"]}),
                    (
                        operator,
                        "submit",
                        {
                            "facts": "Isolated integration facts, no real observation",
                            "checks": [True] * 3,
                        },
                    ),
                    (supervisor, "accept", {}),
                ]:
                    run = client.get("/api/runs/" + rid).json()["run"]
                    r = client.post(
                        "/api/runs/" + rid + "/decide",
                        json={
                            "revision": run["revision"],
                            "action": action,
                            "note": "Isolated integration test",
                            **extra,
                        },
                    )
                    assert r.status_code == 200, r.text
                    with PostgresSaver.from_conn_string(test_url) as saver:
                        assert work_one(factory, build_graph(saver, Bridge()), engine)
            assert admin.get("/api/runs/" + rid).json()["run"]["status"] == "archived"
        print(
            "PASS: actual Docker PostgreSQL + LangGraph durable saver + authenticated Node tools; independent-role full lifecycle; fresh saver at every stage; business database untouched."
        )
    finally:
        if engine:
            engine.dispose()
        with psycopg.connect(parent + "/postgres", autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


if __name__ == "__main__":
    main()
