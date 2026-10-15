"""Generate local-only credentials. Never print them or commit generated files."""

from pathlib import Path
import secrets, os


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / "runtime" / "enterprise.env"
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        print("Existing local configuration retained: runtime/enterprise.env")
        return
    values = {
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "INTERNAL_WORKFLOW_TOKEN": secrets.token_urlsafe(40),
        "BOOTSTRAP_ADMIN_USER": "admin",
        "BOOTSTRAP_ADMIN_PASSWORD": secrets.token_urlsafe(24),
        "DEEPSEEK_API_KEY": "",
        "DEEPSEEK_MODEL": "deepseek-flash",
        "LANGSMITH_TRACING": "false",
    }
    # Reuse an existing local server configuration only when the owner already configured it.
    existing = root / ".env.local"
    if existing.exists():
        for line in existing.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL") and value.strip():
                values[key] = value.strip().strip("\"'")
    with target.open("x", encoding="utf-8") as f:
        f.write("\n".join(k + "=" + v for k, v in values.items()) + "\n")
    if os.name != "nt":
        target.chmod(0o600)
    print("Local credentials generated in runtime/enterprise.env (values hidden).")


if __name__ == "__main__":
    main()
