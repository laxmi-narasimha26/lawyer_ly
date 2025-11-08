#!/usr/bin/env python3
"""
Single-file launcher: starts Postgres + Redis + Backend + Frontend via docker compose,
injects OPENAI_API_KEY securely (via a temporary .env), waits for health, and runs a quick smoke test.

Usage:
  python scripts/launch_local_demo.py --api-key sk-... [--no-smoke]

Notes:
  - The script writes a .env in repo root for compose to read, then leaves it in place (git-ignored).
  - Never commit your .env. Rotate keys if ever leaked.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE = str(REPO_ROOT / "docker-compose.local.app.yml")
ENV_FILE = REPO_ROOT / ".env"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    print("$", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd or REPO_ROOT)
    if check and proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc.returncode


def write_env(api_key: str):
    lines = []
    if ENV_FILE.exists():
        existing = ENV_FILE.read_text(encoding="utf-8").splitlines()
        for line in existing:
            if not line.startswith("OPENAI_API_KEY="):
                lines.append(line)
    lines.append(f"OPENAI_API_KEY={api_key}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {ENV_FILE} (git-ignored)")


def wait_health(url: str, timeout: int = 120):
    import urllib.request
    import urllib.error
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    print("Backend health OK")
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def smoke():
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import smoke_test_local  # type: ignore
    smoke_test_local.main()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", dest="api_key", default=os.environ.get("OPENAI_API_KEY", ""))
    ap.add_argument("--no-smoke", action="store_true")
    args = ap.parse_args()

    if not args.api_key:
        print("ERROR: Provide --api-key or set OPENAI_API_KEY env var.")
        raise SystemExit(2)

    write_env(args.api_key)
    # docker compose up
    run(["docker", "compose", "-f", COMPOSE, "up", "-d", "--build"])

    if not wait_health("http://localhost:8000/health", timeout=150):
        print("Backend not healthy in time. Check logs:")
        run(["docker", "logs", "legal-ai-backend-local", "--tail=200"], check=False)
        raise SystemExit(1)

    print("\nUI available at: http://localhost:5173")
    print("API docs at:    http://localhost:8000/docs")

    if not args.no_smoke:
        print("\nRunning smoke test...")
        smoke()


if __name__ == "__main__":
    main()

