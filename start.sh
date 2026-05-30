#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

MODE="${RUN_MODE:-auto}"

has_docker_compose() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

start_native() {
  if [ ! -d .venv ]; then
    echo "Missing .venv. Run ./install.sh first." >&2
    exit 1
  fi

  # shellcheck disable=SC1091
  source .venv/bin/activate
  exec reflex run --env prod
}

start_docker() {
  docker compose up -d
  docker compose ps
}

case "$MODE" in
  docker)
    if ! has_docker_compose; then
      echo "Docker Compose is not available." >&2
      exit 1
    fi
    start_docker
    ;;
  native)
    start_native
    ;;
  auto)
    if has_docker_compose && [ -f docker-compose.yml ]; then
      start_docker
    else
      start_native
    fi
    ;;
  *)
    echo "Unknown RUN_MODE: $MODE" >&2
    exit 1
    ;;
esac
