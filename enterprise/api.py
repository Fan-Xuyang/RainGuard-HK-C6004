import os, time, secrets, hashlib
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, delete, func
from .db import (
    connect,
    User,
    Session,
    Run,
    Job,
    Event,
    Notice,
    Rule,
    LoginLimit,
    Artifact,
    event,
    uid,
)
from .auth import current, require, bootstrap, verify, password_hash, digest, DUMMY_HASH
from .service import new_run, transition, serialize, REGIONS
from .limits import BodyLimit


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Strict):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=160)


class NewUser(Login):
    role: str


class Password(Strict):
    old: str = Field(max_length=160)
    new: str = Field(min_length=16, max_length=160)


class CreateRun(Strict):
    title: str = Field(min_length=1, max_length=200)
    region: str
    facility: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=2000)
    mode: str = "live"
    engine: str = "evidence"


class Decision(Strict):
    revision: int = Field(ge=0)
    action: str
    note: str = Field(min_length=1, max_length=1200)
    assignee: str | None = None
    facts: str = Field(default="", max_length=3000)
    checks: list[bool] = Field(default_factory=list, max_length=3)
    artifacts: list[str] = Field(default_factory=list, max_length=5)


class CreateRule(Strict):
    name: str = Field(min_length=1, max_length=120)
    region: str
    facility: str = Field(min_length=1, max_length=200)
    threshold: float = Field(ge=1, le=200)


def create_app(url=None):
    engine, factory = connect(url)

    @asynccontextmanager
    async def lifespan(app):
        bootstrap(factory)
        yield

    app = FastAPI(
        title="RainGuard Enterprise Workflow", version="0.5.0", lifespan=lifespan
    )
    app.add_middleware(BodyLimit)
    app.state.factory = factory

    @app.middleware("http")
    async def security(request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and origin
            and origin
            != (
                os.getenv("WORKFLOW_PUBLIC_ORIGIN") or str(request.base_url).rstrip("/")
            )
        ):
            return Response("Cross-origin mutation rejected", 403)
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return Response("Invalid length", 400)
        if length > 2200000:
            return Response("Request too large", 413)
        response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "same-origin",
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'",
            }
        )
        return response

    @app.get("/health")
    def health():
        with factory() as s:
            s.execute(select(User.id).limit(1))
        return {
            "ok": True,
            "modelConfigured": bool(os.getenv("DEEPSEEK_API_KEY")),
            "engine": "LangGraph",
            "database": engine.dialect.name,
        }

    @app.post("/api/auth/login")
    def login(data: Login, request: Request, response: Response):
        key = digest(
            (request.client.host if request.client else "local") + ":" + data.username
        )
        now = time.time()
        with factory.begin() as s:
            limit = s.get(LoginLimit, key)
            if limit and limit.until > now and limit.count >= 8:
                raise HTTPException(429, "登录失败过多，请15分钟后重试")
            if not limit:
                limit = LoginLimit(key=key, count=0, until=now + 900)
                s.add(limit)
            if limit.until < now:
                limit.count = 0
                limit.until = now + 900
            user = s.scalar(select(User).where(User.username == data.username))
            good = (
                verify(data.password, user.password)
                if user
                else verify(data.password, DUMMY_HASH)
            )
            if not user or not user.active or not good:
                limit.count += 1
                s.flush()
                s.commit()
                raise HTTPException(401, "用户名或密码不正确")
            limit.count = 0
            token = secrets.token_urlsafe(32)
            s.add(
                Session(token_hash=digest(token), user_id=user.id, expires=now + 28800)
            )
            s.execute(delete(Session).where(Session.expires < now))
            response.set_cookie(
                "rg_session",
                token,
                httponly=True,
                samesite="strict",
                secure=os.getenv("SECURE_COOKIES") == "true",
                max_age=28800,
            )
            return {"id": user.id, "username": user.username, "role": user.role}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        with factory.begin() as s:
            s.execute(
                delete(Session).where(
                    Session.token_hash == digest(request.cookies.get("rg_session", ""))
                )
            )
        response.delete_cookie("rg_session")
        return {"ok": True}

    @app.post("/api/auth/token")
    def token_login(data: Login, request: Request):
        from http.cookies import SimpleCookie

        response = Response()
        user = login(data, request, response)
        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        return {**user, "token": cookie["rg_session"].value, "expiresIn": 28800}

    @app.post("/api/auth/revoke")
    def revoke(request: Request):
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        with factory.begin() as s:
            s.execute(delete(Session).where(Session.token_hash == digest(token)))
        return {"ok": True}

    @app.get("/api/me")
    def me(request: Request):
        with factory() as s:
            u = current(request, s)
            return {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "regions": REGIONS,
                "modelConfigured": bool(os.getenv("DEEPSEEK_API_KEY")),
            }

    @app.post("/api/auth/password")
    def change_password(data: Password, request: Request):
        with factory.begin() as s:
            u = current(request, s)
            if not verify(data.old, u.password):
                raise HTTPException(400, "原密码不正确")
            u.password = password_hash(data.new)
            s.execute(delete(Session).where(Session.user_id == u.id))
        return {"ok": True, "message": "密码已更改，请重新登录"}

    @app.get("/api/users")
    def users(request: Request):
        with factory() as s:
            current(request, s)
            return [
                {"id": u.id, "username": u.username, "role": u.role, "active": u.active}
                for u in s.scalars(select(User).order_by(User.username))
            ]

    @app.post("/api/users", status_code=201)
    def create_user(data: NewUser, request: Request):
        if (
            data.role not in ("admin", "supervisor", "operator", "auditor")
            or len(data.password) < 16
            or not data.username.strip()
        ):
            raise HTTPException(400, "请检查角色及密码（至少16字符）")
        with factory.begin() as s:
            u = current(request, s)
            require(u, "admin")
            if s.scalar(select(User).where(User.username == data.username)):
                raise HTTPException(409, "用户名已存在")
            n = User(
                id=uid(),
                username=data.username,
                password=password_hash(data.password),
                role=data.role,
            )
            s.add(n)
            event(s, "system", "user.created", u.id, {"user": n.id, "role": n.role})
            return {"id": n.id}

    @app.post("/api/users/{user_id}/disable")
    def disable(user_id: str, request: Request):
        with factory.begin() as s:
            u = current(request, s)
            require(u, "admin")
            target = s.get(User, user_id)
            if not target or target.id == u.id:
                raise HTTPException(400, "不能停用当前账号或不存在的用户")
            target.active = False
            s.execute(delete(Session).where(Session.user_id == user_id))
            event(s, "system", "user.disabled", u.id, {"user": user_id})
        return {"ok": True}

    @app.get("/api/overview")
    def overview(request: Request):
        with factory() as s:
            current(request, s)
            counts = dict(
                s.execute(select(Run.status, func.count()).group_by(Run.status)).all()
            )
            return {
                "total": sum(counts.values()),
                "waiting": sum(v for k, v in counts.items() if k.startswith("waiting")),
                "active": sum(
                    counts.get(k, 0) for k in ("queued", "running", "retrying")
                ),
                "archived": counts.get("archived", 0),
            }

    @app.get("/api/runs")
    def runs(request: Request):
        with factory() as s:
            current(request, s)
            return [
                {
                    k: v
                    for k, v in serialize(r).items()
                    if k not in ("state", "question")
                }
                for r in s.scalars(
                    select(Run).order_by(Run.updated_at.desc()).limit(200)
                )
            ]

    @app.post("/api/runs", status_code=201)
    def create(data: CreateRun, request: Request):
        if (
            data.region not in REGIONS
            or data.mode not in ("live", "snapshot")
            or data.engine not in ("evidence", "deepseek")
            or not all(x.strip() for x in (data.title, data.facility, data.question))
        ):
            raise HTTPException(400, "地区、模式或内容无效")
        if data.engine == "deepseek" and not os.getenv("DEEPSEEK_API_KEY"):
            raise HTTPException(503, "服务端未配置DeepSeek密钥；可选择来源核验模式")
        with factory.begin() as s:
            u = current(request, s)
            require(u, "admin", "supervisor", "operator")
            r = new_run(s, **data.model_dump(), creator=u.id)
            return {"id": r.id}

    @app.get("/api/runs/{run_id}")
    def detail(run_id: str, request: Request):
        with factory() as s:
            current(request, s)
            r = s.get(Run, run_id)
            if not r:
                raise HTTPException(404, "流程不存在")
            return {
                "run": serialize(r),
                "events": [
                    serialize(e)
                    for e in s.scalars(
                        select(Event).where(Event.run_id == run_id).order_by(Event.time)
                    )
                ],
                "jobs": [
                    serialize(j)
                    for j in s.scalars(select(Job).where(Job.run_id == run_id))
                ],
                "artifacts": [
                    serialize(a)
                    for a in s.scalars(
                        select(Artifact).where(Artifact.run_id == run_id)
                    )
                ],
            }

    @app.post("/api/runs/{run_id}/decide")
    def decide(run_id: str, data: Decision, request: Request):
        if not data.note.strip():
            raise HTTPException(400, "请填写操作说明")
        with factory.begin() as s:
            u = current(request, s)
            r = s.scalar(select(Run).where(Run.id == run_id).with_for_update())
            if not r:
                raise HTTPException(404, "流程不存在")
            transition(s, r, u, **data.model_dump())
        return {"ok": True}

    @app.post("/api/runs/{run_id}/artifacts", status_code=201)
    async def upload(run_id: str, request: Request, file: UploadFile = File(...)):
        data = await file.read(2000001)
        if len(data) > 2000000:
            raise HTTPException(413, "照片不能超过2MB")
        mime = (
            "image/png"
            if data.startswith(b"\x89PNG\r\n\x1a\n")
            else "image/jpeg"
            if data.startswith(b"\xff\xd8\xff")
            else None
        )
        if not mime:
            raise HTTPException(400, "只接受PNG或JPEG照片")
        with factory.begin() as s:
            u = current(request, s)
            r = s.get(Run, run_id)
            if not r:
                raise HTTPException(404, "流程不存在")
            if (
                r.status != "waiting_field"
                or r.assignee != u.id
                or u.role != "operator"
            ):
                raise HTTPException(403, "仅被指派的执行人可在现场阶段上传")
            aid = uid()
            root = Path(os.getenv("ARTIFACT_ROOT", "runtime/workflow-artifacts"))
            root.mkdir(parents=True, exist_ok=True)
            target = root / aid
            if (
                len(
                    list(
                        s.scalars(select(Artifact.id).where(Artifact.run_id == run_id))
                    )
                )
                >= 10
            ):
                raise HTTPException(400, "每个流程最多10张照片")
            target.write_bytes(data)
            s.add(
                Artifact(
                    id=aid,
                    run_id=run_id,
                    sha256=hashlib.sha256(data).hexdigest(),
                    mime=mime,
                    uploader=u.id,
                )
            )
            event(s, run_id, "artifact.uploaded", u.id, {"id": aid, "bytes": len(data)})
        return {"id": aid}

    @app.get("/api/artifacts/{aid}")
    def artifact(aid: str, request: Request):
        with factory() as s:
            current(request, s)
            a = s.get(Artifact, aid)
            if not a:
                raise HTTPException(404, "附件不存在")
            target = (
                Path(os.getenv("ARTIFACT_ROOT", "runtime/workflow-artifacts")) / a.id
            )
            if (
                not target.is_file()
                or hashlib.sha256(target.read_bytes()).hexdigest() != a.sha256
            ):
                raise HTTPException(409, "附件缺失或完整性检查失败")
            return FileResponse(
                target,
                media_type=a.mime,
                filename=a.id + (".png" if a.mime == "image/png" else ".jpg"),
            )

    @app.get("/api/runs/{run_id}/export")
    def export(run_id: str, request: Request):
        return detail(run_id, request)

    @app.get("/api/notices")
    def notices(request: Request):
        with factory() as s:
            current(request, s)
            return [
                serialize(n)
                for n in s.scalars(
                    select(Notice).order_by(Notice.created_at.desc()).limit(100)
                )
            ]

    @app.get("/api/rules")
    def rules(request: Request):
        with factory() as s:
            current(request, s)
            return [serialize(r) for r in s.scalars(select(Rule))]

    @app.post("/api/rules", status_code=201)
    def rule(data: CreateRule, request: Request):
        if data.region not in REGIONS:
            raise HTTPException(400, "地区无效")
        with factory.begin() as s:
            u = current(request, s)
            require(u, "admin", "supervisor")
            r = Rule(id=uid(), **data.model_dump())
            s.add(r)
            event(s, "system", "rule.created", u.id, {"rule": r.id})
            return {"id": r.id}

    @app.post("/api/rules/{rid}/toggle")
    def toggle(rid: str, request: Request):
        with factory.begin() as s:
            u = current(request, s)
            require(u, "admin", "supervisor")
            r = s.get(Rule, rid)
            if not r:
                raise HTTPException(404, "规则不存在")
            r.enabled = not r.enabled
            event(
                s, "system", "rule.toggled", u.id, {"rule": rid, "enabled": r.enabled}
            )
        return {"ok": True}

    @app.get("/api/audit")
    def audit(request: Request):
        with factory() as s:
            u = current(request, s)
            require(u, "admin", "supervisor", "auditor")
            return [
                serialize(e)
                for e in s.scalars(select(Event).order_by(Event.time.desc()).limit(500))
            ]

    app.mount(
        "/assets", StaticFiles(directory=Path(__file__).parent / "ui"), name="assets"
    )

    @app.get("/")
    def index():
        return FileResponse(Path(__file__).parent / "ui" / "index.html")

    return app
