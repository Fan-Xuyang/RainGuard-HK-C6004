"""Configure DeepSeek with hidden terminal input; never use a command-line key."""

import getpass, os
from pathlib import Path


def main():
    target = Path(__file__).resolve().parents[1] / "runtime" / "enterprise.env"
    if not target.exists():
        raise SystemExit("Run enterprise/bootstrap.py first")
    key = getpass.getpass("DeepSeek API key (hidden): ").strip()
    if not key.startswith("sk-") or not 20 <= len(key) <= 200:
        raise SystemExit("Invalid key format; nothing written")
    lines = target.read_text(encoding="utf-8").splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith("DEEPSEEK_API_KEY="):
            lines[i] = "DEEPSEEK_API_KEY=" + key
            found = True
    if not found:
        lines.append("DEEPSEEK_API_KEY=" + key)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if os.name != "nt":
        target.chmod(0o600)
    print("DeepSeek configured in local ignored file. Key value hidden.")


if __name__ == "__main__":
    main()
