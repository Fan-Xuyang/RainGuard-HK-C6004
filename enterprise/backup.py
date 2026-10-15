"""Consistent local backup of this project's database and artifact volume."""

from pathlib import Path
from datetime import datetime, timezone, timedelta
import subprocess, hashlib, json, secrets


def main():
    root = Path(__file__).resolve().parents[1]
    destination = (
        root
        / "runtime"
        / "backups"
        / (
            datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S")
            + "-"
            + secrets.token_hex(3)
        )
    )
    destination.mkdir(parents=True)
    compose = [
        "docker",
        "compose",
        "--env-file",
        "runtime/enterprise.env",
        "-f",
        "compose.enterprise.yml",
    ]
    subprocess.run(
        compose + ["stop", "api", "worker", "scheduler"], cwd=root, check=True
    )
    try:
        with (destination / "database.dump").open("wb") as f:
            subprocess.run(
                compose
                + [
                    "exec",
                    "-T",
                    "database",
                    "pg_dump",
                    "-U",
                    "rainguard",
                    "-d",
                    "rainguard",
                    "-Fc",
                ],
                cwd=root,
                stdout=f,
                check=True,
            )
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                "rainguard-enterprise_artifacts:/data:ro",
                "-v",
                str(destination) + ":/backup",
                "postgres:16",
                "tar",
                "-C",
                "/data",
                "-czf",
                "/backup/artifacts.tgz",
                ".",
            ],
            check=True,
        )
        manifest = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in destination.iterdir()
            if p.is_file()
        }
        (destination / "sha256.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        print("Backup saved under runtime/backups/ (no credentials printed).")
    finally:
        subprocess.run(compose + ["up", "-d", "--wait"], cwd=root, check=True)


if __name__ == "__main__":
    main()
