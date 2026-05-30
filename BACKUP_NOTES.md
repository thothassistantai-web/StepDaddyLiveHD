# StepDaddyLiveHD Linux Backup Notes

This repository snapshot is the Linux-friendly backup of the working StepDaddyLiveHD deployment.

## Runtime Model

- Primary supported path: Docker Compose with Caddy + Redis + Reflex backend.
- Native fallback: `./install.sh` + `./start.sh` can also bootstrap a local `.venv` and run Reflex directly.
- Default port: `3000`
- Default local API URL: `http://127.0.0.1:3000`

## Environment Variables

- `PORT`: public port exposed by the app.
- `API_URL`: absolute URL the frontend uses for stream and playlist links.
- `PROXY_CONTENT`: `TRUE` or `FALSE` for proxied video content.
- `SOCKS5`: optional SOCKS5 proxy for upstream requests.
- `DLHD_BASE_URL`: optional upstream source override, defaults to `https://dlhd.sx`.

## Install Flow

1. Run `./install.sh`
2. If Docker is available, the stack comes up with `docker compose up -d --build`
3. If Docker is not available, the script falls back to a local virtualenv and Reflex
4. Use `./status.sh` to confirm the app is healthy
5. Use `./stop.sh` to shut it down cleanly

## Notes

- `requirements.txt` now includes the direct runtime dependencies used by the code.
- `rxconfig.py` now falls back to localhost automatically if `API_URL` is unset.
- Startup now preloads the channel list before background refresh begins, which avoids the blank first-load race.
