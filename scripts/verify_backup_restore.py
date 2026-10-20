"""Restore this project's latest private backup into a disposable PostgreSQL database.

The business database is read only. The temporary database is dropped in finally.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, secrets, subprocess, re

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "--env-file", "runtime/enterprise.env", "-f", "compose.enterprise.yml"]


def command(args, data=None):
    result = subprocess.run(COMPOSE + ["exec", "-T", "database"] + args,
                            cwd=ROOT, input=data, capture_output=True)
    if result.returncode:
        raise RuntimeError("Backup restore verification command failed; private output suppressed")
    return result.stdout.decode().strip()


def main():
    root = (ROOT / "runtime/backups").resolve()
    candidates = sorted(p for p in root.iterdir() if (p / "database.dump").exists())
    if not candidates:
        raise RuntimeError("Run enterprise/backup.py first")
    backup = candidates[-1].resolve()
    assert backup.is_relative_to(root)
    manifest = json.loads((backup / "sha256.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        path = (backup / name).resolve()
        assert path.parent == backup and hashlib.sha256(path.read_bytes()).hexdigest() == expected
    target = "rainguard_restoreqa_" + secrets.token_hex(5)
    assert re.fullmatch(r"rainguard_restoreqa_[0-9a-f]{10}", target)
    created = False
    try:
        command(["createdb", "-U", "rainguard", target]); created = True
        command(["pg_restore", "-U", "rainguard", "--no-owner", "--no-privileges", "--exit-on-error", "-d", target], (backup / "database.dump").read_bytes())
        tables = ["wf_users", "wf_runs", "wf_jobs", "wf_events", "wf_artifacts"]
        def counts(database):
            return {table: int(command(["psql", "-U", "rainguard", "-d", database, "-At", "-c", "SELECT count(*) FROM " + table])) for table in tables}
        restored, business = counts(target), counts("rainguard")
        assert restored == business, "Row counts changed since backup; inspect private report before claiming equivalence"
        report = {"checkedAt": datetime.now(timezone.utc).isoformat(), "passed": True,
                  "backup": str(backup.relative_to(ROOT)), "hashesPassed": True,
                  "restoredRowCounts": restored, "businessDatabaseRestored": False,
                  "note": "Database restored only into a disposable database. Photo archive checksum verified; no formal photo-volume overwrite."}
        (ROOT / "runtime/interview-restore-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "backup"}))
    finally:
        if created:
            command(["dropdb", "-U", "rainguard", "--force", target])


if __name__ == "__main__":
    main()
