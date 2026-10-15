"""Start an isolated local QA deployment. Contains no production workflow writes."""

import os, json, secrets, subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
runtime = root / "runtime"
runtime.mkdir(exist_ok=True)
env = os.environ.copy()
for line in (runtime / "enterprise.env").read_text(encoding="utf-8").splitlines():
    k, _, v = line.partition("=")
    env[k] = v
password = secrets.token_urlsafe(24)
env.update(
    DATABASE_URL="sqlite:///" + (runtime / "enterprise-qa.sqlite").as_posix(),
    CHECKPOINT_DATABASE_URL="",
    CHECKPOINT_PATH=(runtime / "enterprise-qa-checkpoints.sqlite").as_posix(),
    BOOTSTRAP_ADMIN_PASSWORD=password,
    ARTIFACT_ROOT=str(runtime / "enterprise-qa-artifacts"),
    WEATHER_SERVICE_URL="http://127.0.0.1:8096",
    LANGSMITH_TRACING="false",
)
# A unique QA database each run avoids stale passwords and never touches the Docker business database.
suffix = secrets.token_hex(5)
env["DATABASE_URL"] = (
    "sqlite:///" + (runtime / ("enterprise-qa-" + suffix + ".sqlite")).as_posix()
)
env["CHECKPOINT_PATH"] = str(
    runtime / ("enterprise-qa-checkpoints-" + suffix + ".sqlite")
)
python = (
    root / ".venv" / "Scripts" / "python.exe"
    if os.name == "nt"
    else root / ".venv" / "bin" / "python"
)
flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
children = []
for name, args in [
    (
        "api",
        [
            "-m",
            "uvicorn",
            "enterprise.api:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "8110",
        ],
    ),
    ("worker", ["-m", "enterprise.worker"]),
]:
    log = (runtime / ("enterprise-qa-" + name + ".log")).open("w", encoding="utf-8")
    p = subprocess.Popen(
        [str(python), *args],
        cwd=root,
        env=env,
        stdout=log,
        stderr=log,
        creationflags=flags,
    )
    children.append(p.pid)
(runtime / "enterprise-qa-access.json").write_text(
    json.dumps({"username": "admin", "password": password, "pids": children}),
    encoding="utf-8",
)
print(
    "Isolated QA started on port 8110; credentials are stored only under ignored runtime/."
)
