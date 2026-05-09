#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

exec engine/backend/.venv/bin/python scripts/launch_local_end4d.py
