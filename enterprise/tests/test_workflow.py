import os, time, json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import AIMessage
from enterprise.api import create_app
from enterprise.db import Run, Job, User, Notice, Rule, Event
from enterprise.graph import build_graph
from enterprise.worker import work_one
from enterprise.scheduler import tick


class OfflineBridge:
    """Explicit test double. Production never uses these synthetic observations."""

    def call(self, name, args, mode):
        if name == "compare_regions":
            return {
                "origin": mode if mode == "snapshot" else "online",
                "stale": mode == "snapshot",
                "observedAt": "2026-10-15T00:00:00+08:00",
                "rows": [{"region": "沙田", "mm": 35}],
            }
        if name == "weather_window":
            return {"blocked": True, "reason": "Test fixture, not live weather"}
        return {"citations": []}

    def catalog(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_knowledge",
                    "description": "test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            }
        ]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "isolated-test-password-123")
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = create_app("sqlite:///" + str(tmp_path / "business.sqlite"))
    with TestClient(app) as admin:
        assert (
            admin.post(
                "/api/auth/login",
                json={"username": "admin", "password": "isolated-test-password-123"},
            ).status_code
            == 200
        )
        for name, role in [
            ("field", "operator"),
            ("field2", "operator"),
            ("supervisor", "supervisor"),
            ("auditor", "auditor"),
        ]:
            assert (
                admin.post(
                    "/api/users",
                    json={
                        "username": name,
                        "password": "isolated-test-password-123",
                        "role": role,
                    },
                ).status_code
                == 201
            )
        clients = {}
        for name in ["field", "field2", "supervisor", "auditor"]:
            c = TestClient(app)
            c.post(
                "/api/auth/login",
                json={"username": name, "password": "isolated-test-password-123"},
            )
            clients[name] = c
        with SqliteSaver.from_conn_string(
            str(tmp_path / "checkpoints.sqlite")
        ) as saver:
            yield app, admin, clients, build_graph(saver, OfflineBridge()), tmp_path


def create(c, **changes):
    d = {
        "title": "隔离自动化测试流程",
        "region": "沙田",
        "facility": "仅测试数据库中的虚构场地",
        "question": "核验来源",
        "mode": "snapshot",
        "engine": "evidence",
        **changes,
    }
    r = c.post("/api/runs", json=d)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def current(c, rid):
    return c.get("/api/runs/" + rid).json()["run"]


def decide(c, rid, action, **kwargs):
    return c.post(
        "/api/runs/" + rid + "/decide",
        json={
            "revision": current(c, rid)["revision"],
            "action": action,
            "note": "隔离测试操作记录",
            **kwargs,
        },
    )


def work(app, g):
    assert work_one(app.state.factory, g, app.state.factory.kw["bind"])


def test_full_lifecycle_restart_and_permissions(env):
    app, admin, c, g, tmp = env
    rid = create(c["field"])
    work(app, g)
    assert current(admin, rid)["status"] == "waiting_approval"
    assert decide(c["auditor"], rid, "approve").status_code == 403
    operator = next(
        u["id"] for u in admin.get("/api/users").json() if u["username"] == "field"
    )
    assert decide(admin, rid, "approve", assignee=operator).status_code == 200
    # Rebuild graph with another connection to prove an actual process restart can resume a durable interrupt.
    with SqliteSaver.from_conn_string(str(tmp / "checkpoints.sqlite")) as saver:
        restored = build_graph(saver, OfflineBridge())
        work(app, restored)
        assert current(admin, rid)["status"] == "waiting_field"
        assert (
            decide(
                c["supervisor"], rid, "submit", facts="test", checks=[True] * 3
            ).status_code
            == 403
        )
        assert (
            decide(
                c["field"], rid, "submit", facts="test", checks=[True, False, True]
            ).status_code
            == 400
        )
        assert (
            decide(
                c["field"], rid, "submit", facts="隔离测试现场事实", checks=[True] * 3
            ).status_code
            == 200
        )
        work(app, restored)
        assert current(admin, rid)["status"] == "waiting_review"
        assert decide(admin, rid, "return_field").status_code == 200
        work(app, restored)
        assert current(admin, rid)["status"] == "waiting_field"
        assert (
            decide(
                c["field"], rid, "submit", facts="隔离测试补充事实", checks=[True] * 3
            ).status_code
            == 200
        )
        work(app, restored)
        assert decide(admin, rid, "accept").status_code == 200
        work(app, restored)
    r = current(admin, rid)
    assert r["status"] == "archived"
    assert r["state"]["archive"]["mode"] == "snapshot"
    assert any(
        e["kind"] == "decision.return_field"
        for e in admin.get("/api/runs/" + rid).json()["events"]
    )


def test_self_approval_cas_and_fail_closed(env):
    app, admin, c, g, _ = env
    rid = create(admin)
    work(app, g)
    operator = next(
        u["id"] for u in admin.get("/api/users").json() if u["role"] == "operator"
    )
    assert decide(admin, rid, "approve", assignee=operator).status_code == 403
    old = current(admin, rid)["revision"]
    assert decide(c["supervisor"], rid, "rework").status_code == 200
    assert (
        c["supervisor"]
        .post(
            "/api/runs/" + rid + "/decide",
            json={"revision": old, "action": "rework", "note": "stale"},
        )
        .status_code
        == 409
    )
    assert (
        admin.post(
            "/api/runs",
            json={
                "title": "x",
                "region": "沙田",
                "facility": "x",
                "question": "x",
                "engine": "deepseek",
            },
        ).status_code
        == 503
    )
    assert TestClient(app).get("/api/runs").status_code == 401
    assert (
        admin.post(
            "/api/rules",
            headers={"Origin": "https://untrusted.invalid"},
            json={"name": "x", "facility": "x", "region": "沙田", "threshold": 30},
        ).status_code
        == 403
    )
    assert (
        c["auditor"]
        .post(
            "/api/runs",
            json={"title": "x", "facility": "x", "region": "沙田", "question": "x"},
        )
        .status_code
        == 403
    )


def test_retry_lease_recovery_command_dedup(env):
    app, admin, c, g, _ = env
    rid = create(c["field"])
    with app.state.factory.begin() as s:
        j = s.scalar(select(Job).where(Job.run_id == rid))
        j.status = "running"
        j.worker = "dead-worker"
        j.lease_until = time.time() - 1
    work(app, g)
    assert current(admin, rid)["status"] == "waiting_approval"
    operator = next(
        u["id"] for u in admin.get("/api/users").json() if u["role"] == "operator"
    )
    decide(admin, rid, "approve", assignee=operator)
    work(app, g)
    with app.state.factory.begin() as s:
        j = s.scalar(select(Job).where(Job.run_id == rid, Job.kind == "resume"))
        j.status = "pending"
        j.available_at = 0
    work(app, g)
    assert (
        current(admin, rid)["status"] == "waiting_field"
    )  # Duplicate command must not accidentally submit a field interrupt.


def test_dead_letter_and_manual_retry(env):
    app, admin, c, g, _ = env
    rid = create(c["field"])

    class Broken:
        def get_state(self, c):
            raise RuntimeError("injected crash")

    for _ in range(3):
        work(app, Broken())
        with app.state.factory.begin() as s:
            s.execute(update(Job).where(Job.run_id == rid).values(available_at=0))
    assert current(admin, rid)["status"] == "failed"
    assert decide(admin, rid, "retry").status_code == 200
    work(app, g)
    assert current(admin, rid)["status"] == "waiting_approval"


def test_scheduler_stale_dedup_sla_and_upload(env):
    app, admin, c, g, _ = env
    f = app.state.factory
    admin.post(
        "/api/rules",
        json={
            "name": "测试规则（隔离库）",
            "region": "沙田",
            "facility": "测试场地",
            "threshold": 30,
        },
    )
    tick(f, OfflineBridge(), now=time.time())
    tick(f, OfflineBridge(), now=time.time() + 301)
    with f() as s:
        assert len(list(s.scalars(select(Run).where(Run.creator == "system")))) == 1
    while work_one(f, g, f.kw["bind"]):
        pass
    rid = create(c["field"])
    work(app, g)
    with f.begin() as s:
        s.get(Run, rid).due_at = 0
    tick(f, OfflineBridge())
    tick(f, OfflineBridge())
    with f() as s:
        assert (
            len(list(s.scalars(select(Notice).where(Notice.id == rid + ":1:sla")))) == 1
        )
    operator = next(
        u["id"] for u in admin.get("/api/users").json() if u["role"] == "operator"
    )
    decide(admin, rid, "approve", assignee=operator)
    # Consume any scheduler-created queued start job first, then the approval resume.
    while work_one(f, g, f.kw["bind"]):
        pass
    assert (
        c["field"]
        .post(
            "/api/runs/" + rid + "/artifacts",
            files={"file": ("evil.svg", b"<svg/>", "image/svg+xml")},
        )
        .status_code
        == 400
    )
    assert (
        c["auditor"]
        .post(
            "/api/runs/" + rid + "/artifacts",
            files={"file": ("x.png", b"\x89PNG\r\n\x1a\nfixture", "image/png")},
        )
        .status_code
        == 403
    )


def test_real_langchain_tool_loop_with_mock_model(env):
    app, admin, c, _, tmp = env

    class Model:
        def __init__(self):
            self.n = 0

        def bind_tools(self, tools):
            assert tools
            return self

        def invoke(self, messages):
            self.n += 1
            return (
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "search_knowledge",
                            "args": {"query": "暴雨"},
                        }
                    ],
                )
                if self.n == 1
                else AIMessage(content="测试模型回答，非真实API调用。")
            )

    with SqliteSaver.from_conn_string(str(tmp / "model.sqlite")) as saver:
        graph = build_graph(saver, OfflineBridge(), Model)
        result = graph.invoke(
            {
                "run_id": "model-test",
                "question": "暴雨",
                "region": "沙田",
                "facility": "测试",
                "mode": "snapshot",
                "engine": "deepseek",
            },
            {"configurable": {"thread_id": "model-test"}},
        )
        assert result["__interrupt__"][0].value["phase"] == "waiting_approval"
        assert result["analysis"].startswith("测试模型")
        assert result["trace"][-1]["tool"] == "search_knowledge"


def test_login_lockout_and_disable(env):
    app, admin, c, _, _ = env
    bad = TestClient(app)
    for _ in range(8):
        assert (
            bad.post(
                "/api/auth/login", json={"username": "unknown", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        bad.post(
            "/api/auth/login", json={"username": "unknown", "password": "wrong"}
        ).status_code
        == 429
    )
    auditor = next(
        u["id"] for u in admin.get("/api/users").json() if u["role"] == "auditor"
    )
    admin.post("/api/users/" + auditor + "/disable")
    assert c["auditor"].get("/api/me").status_code == 401


def test_reassignment_token_and_chunked_limits(env):
    app, admin, c, g, _ = env
    rid = create(c["field"])
    work(app, g)
    users = admin.get("/api/users").json()
    first = next(u["id"] for u in users if u["username"] == "field")
    second = next(u["id"] for u in users if u["username"] == "field2")
    assert decide(admin, rid, "approve", assignee=first).status_code == 200
    work(app, g)
    assert decide(c["field"], rid, "reassign", assignee=second).status_code == 403
    assert decide(admin, rid, "reassign", assignee=second).status_code == 200
    work(app, g)
    assert (
        current(admin, rid)["assignee"] == second
        and current(admin, rid)["status"] == "waiting_field"
    )
    assert (
        decide(c["field"], rid, "submit", facts="test", checks=[True] * 3).status_code
        == 403
    )
    assert (
        decide(c["field2"], rid, "submit", facts="test", checks=[True] * 3).status_code
        == 200
    )
    native = TestClient(app)
    r = native.post(
        "/api/auth/token",
        json={"username": "field2", "password": "isolated-test-password-123"},
    )
    assert r.status_code == 200
    token = r.json()["token"]
    assert (
        native.get("/api/me", headers={"Authorization": "Bearer " + token}).status_code
        == 200
    )
    native.post("/api/auth/revoke", headers={"Authorization": "Bearer " + token})
    assert (
        native.get("/api/me", headers={"Authorization": "Bearer " + token}).status_code
        == 401
    )
    oversized = admin.post(
        "/api/runs",
        content=iter([b"{" * 33000, b"}" * 33000]),
        headers={"Content-Type": "application/json"},
    )
    assert oversized.status_code == 413
