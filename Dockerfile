ARG PORT=3000
ARG PROXY_CONTENT=TRUE
ARG SOCKS5
ARG API_URL

FROM python:3.13 AS builder

RUN mkdir -p /app/.web
RUN python -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY rxconfig.py ./
RUN reflex init

COPY reflex_compat_patch.py /tmp/reflex_compat_patch.py
RUN python - <<'PY'
import pathlib
import shutil
import site

src = pathlib.Path("/tmp/reflex_compat_patch.py")
for base in site.getsitepackages():
    compat = pathlib.Path(base) / "reflex/utils/compat.py"
    if compat.exists():
        shutil.copy2(src, compat)
        print(f"patched {compat}")
        break
else:
    raise SystemExit("reflex utils compat file not found")
PY

COPY . .

ARG PORT API_URL PROXY_CONTENT SOCKS5
RUN REFLEX_API_URL=${API_URL:-http://localhost:$PORT} reflex export --loglevel debug --frontend-only --no-zip && mv .web/build/client/* /srv/ && rm -rf .web

FROM python:3.13-slim

RUN apt-get update -y && apt-get install -y caddy redis-server && rm -rf /var/lib/apt/lists/*

ARG PORT=3000
ARG API_URL
ARG PROXY_CONTENT=TRUE
ARG SOCKS5
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=$PORT \
    REFLEX_API_URL=${API_URL:-http://localhost:$PORT} \
    REDIS_URL=redis://localhost \
    PYTHONUNBUFFERED=1 \
    PROXY_CONTENT=${PROXY_CONTENT} \
    SOCKS5=${SOCKS5}

WORKDIR /app
COPY --from=builder /app /app
COPY --from=builder /srv /srv
COPY Caddyfile /etc/caddy/Caddyfile

STOPSIGNAL SIGKILL
EXPOSE $PORT

CMD caddy start && \
    redis-server --daemonize yes && \
    exec reflex run --env prod --backend-only
