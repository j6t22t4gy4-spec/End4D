"""One-shot local launcher for End4D.

Starts backend and frontend together so the engine feels like a local app
instead of two separate developer services.
"""
from __future__ import annotations

import argparse
import atexit
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "engine" / "backend"
FRONTEND_DIR = ROOT / "engine" / "frontend"
BACKEND_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000/health"
DEFAULT_FRONTEND_URL = "http://127.0.0.1:3000"


class ManagedProcess:
    def __init__(self, name: str, popen: subprocess.Popen[str]):
        self.name = name
        self.popen = popen

    def terminate(self) -> None:
        if self.popen.poll() is not None:
            return
        self.popen.terminate()
        try:
            self.popen.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.popen.kill()
            self.popen.wait(timeout=4)


def _request_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= int(response.status) < 500
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
        return False


def _wait_until_ready(url: str, *, timeout_s: float, name: str) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _request_ok(url):
            return
        time.sleep(0.4)
    raise RuntimeError(f"{name} did not become ready at {url} within {timeout_s:.0f}s")


def _frontend_command(frontend_port: int) -> List[str]:
    build_id = FRONTEND_DIR / ".next" / "BUILD_ID"
    if build_id.exists():
        return ["npm", "run", "start", "--", "--port", str(frontend_port), "--hostname", "127.0.0.1"]
    return ["npm", "run", "dev", "--", "--port", str(frontend_port), "--hostname", "127.0.0.1"]


def _backend_command(backend_port: int) -> List[str]:
    return [
        str(BACKEND_PYTHON),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(backend_port),
    ]


def _check_prerequisites() -> None:
    if not BACKEND_PYTHON.exists():
        raise RuntimeError("Backend virtualenv is missing: engine/backend/.venv")
    if not (FRONTEND_DIR / "node_modules").exists():
        raise RuntimeError("Frontend dependencies are missing: engine/frontend/node_modules")


def _spawn(name: str, command: List[str], cwd: Path, env: Dict[str, str]) -> ManagedProcess:
    popen = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
    )
    return ManagedProcess(name, popen)


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch End4D locally like a desktop app.")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=3000)
    parser.add_argument("--frontend-api-url", default="")
    parser.add_argument("--runtime-profile", default="local-pro")
    parser.add_argument("--backend-timeout", type=float, default=25.0)
    parser.add_argument("--frontend-timeout", type=float, default=45.0)
    args = parser.parse_args()

    _check_prerequisites()

    backend_url = f"http://127.0.0.1:{args.backend_port}/health"
    frontend_url = f"http://127.0.0.1:{args.frontend_port}"
    api_url = args.frontend_api_url or f"http://127.0.0.1:{args.backend_port}"

    if _request_ok(backend_url) or _request_ok(frontend_url):
        print("Existing service detected on the target ports. Stop it first or use different ports.")
        return 2

    managed: List[ManagedProcess] = []

    def _cleanup() -> None:
        for proc in reversed(managed):
            proc.terminate()

    atexit.register(_cleanup)

    def _signal_handler(signum, frame) -> None:  # type: ignore[no-untyped-def]
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    backend_env = os.environ.copy()
    backend_env.setdefault("ORGANIC4D_RUNTIME_PROFILE", args.runtime_profile)

    frontend_env = os.environ.copy()
    frontend_env["NEXT_PUBLIC_API_URL"] = api_url

    print("Launching End4D local runtime...")
    backend = _spawn("backend", _backend_command(args.backend_port), BACKEND_DIR, backend_env)
    managed.append(backend)
    _wait_until_ready(backend_url, timeout_s=args.backend_timeout, name="Backend")
    print(f"Backend ready: {backend_url}")

    frontend = _spawn("frontend", _frontend_command(args.frontend_port), FRONTEND_DIR, frontend_env)
    managed.append(frontend)
    _wait_until_ready(frontend_url, timeout_s=args.frontend_timeout, name="Frontend")
    print(f"Frontend ready: {frontend_url}")
    print("End4D is running locally. Press Ctrl+C to stop both services.")

    try:
        while True:
            for proc in managed:
                code = proc.popen.poll()
                if code is not None:
                    raise RuntimeError(f"{proc.name} exited early with status {code}")
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping End4D local runtime...")
        return 0
    except RuntimeError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
