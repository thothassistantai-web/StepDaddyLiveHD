#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PORT="${PORT:-3000}"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose ps
fi

if command -v curl >/dev/null 2>&1; then
  curl -fsS "http://127.0.0.1:${PORT}/healthz" || true
  printf '\n'
fi
