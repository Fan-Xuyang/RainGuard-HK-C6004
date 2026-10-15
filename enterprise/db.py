import os, time, uuid
from sqlalchemy import create_engine, String, Text, Integer, Float, JSON, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def uid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "wf_users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(24))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Session(Base):
    __tablename__ = "wf_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40))
    expires: Mapped[float] = mapped_column(Float)


class Run(Base):
    __tablename__ = "wf_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(200))
    region: Mapped[str] = mapped_column(String(40))
    facility: Mapped[str] = mapped_column(String(200))
    question: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(20))
    engine: Mapped[str] = mapped_column(String(20))
    creator: Mapped[str] = mapped_column(String(40))
    assignee: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    due_at: Mapped[float] = mapped_column(Float)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)
    trigger_key: Mapped[str | None] = mapped_column(
        String(200), unique=True, nullable=True
    )


class Job(Base):
    __tablename__ = "wf_jobs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[float] = mapped_column(Float, default=time.time)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    worker: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Event(Base):
    __tablename__ = "wf_events"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    time: Mapped[float] = mapped_column(Float, default=time.time)


class Notice(Base):
    __tablename__ = "wf_notices"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Rule(Base):
    __tablename__ = "wf_rules"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(40))
    facility: Mapped[str] = mapped_column(String(200))
    threshold: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_check: Mapped[float] = mapped_column(Float, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class LoginLimit(Base):
    __tablename__ = "wf_login_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    until: Mapped[float] = mapped_column(Float)


class Artifact(Base):
    __tablename__ = "wf_artifacts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    sha256: Mapped[str] = mapped_column(String(64))
    mime: Mapped[str] = mapped_column(String(30))
    uploader: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


def connect(url=None):
    url = url or os.getenv("DATABASE_URL", "sqlite:///runtime/enterprise.sqlite")
    if url.startswith("sqlite:"):
        os.makedirs("runtime", exist_ok=True)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 30}
        if url.startswith("sqlite:")
        else {},
        pool_pre_ping=True,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def event(s, run_id, kind, actor, detail=None):
    s.add(Event(run_id=run_id, kind=kind, actor=actor, detail=detail or {}))
