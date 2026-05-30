#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

MODE="${INSTALL_MODE:-auto}"
PORT="${PORT:-3000}"

has_docker_compose() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

install_native() {
  local python_bin="${PYTHON_BIN:-python3}"

  if ! command -v "$python_bin" >/dev/null 2>&1; then
    echo "python3 is required for the native install path." >&2
    exit 1
  fi

  if [ ! -d .venv ]; then
    "$python_bin" -m venv .venv
  fi

  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt

  if ! command -v reflex >/dev/null 2>&1; then
    echo "reflex was not installed correctly." >&2
    exit 1
  fi

  if [ ! -d .web ]; then
    reflex init
  fi

  echo "Native install complete."
  echo "Run ./start.sh to launch on port ${PORT}."
}

install_docker() {
  if [ ! -f .env ]; then
    cat > .env <<EOF
PORT=${PORT}
API_URL=http://127.0.0.1:${PORT}
PROXY_CONTENT=TRUE
SOCKS5=
EOF
  fi

  docker compose up -d --build
  echo "Docker install complete."
  echo "Open http://127.0.0.1:${PORT}"
}

case "$MODE" in
  docker)
    if ! has_docker_compose; then
      echo "Docker Compose is not available. Install Docker or use INSTALL_MODE=native." >&2
      exit 1
    fi
    install_docker
    ;;
  native)
    install_native
    ;;
  auto)
    if has_docker_compose; then
      install_docker
    else
      install_native
    fi
    ;;
  *)
    echo "Unknown INSTALL_MODE: $MODE" >&2
    exit 1
    ;;
esac
