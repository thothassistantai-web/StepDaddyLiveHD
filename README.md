# StepDaddyLiveHD Linux

StepDaddyLiveHD is a self-hosted IPTV proxy built with [Reflex](https://reflex.dev). It lets you browse live channels, search scheduled events, stream channels in the browser, and export a `playlist.m3u8` for IPTV clients.

This backup snapshot is the Linux-friendly version of the working app. It is set up to work out of the box with Docker Compose, and it also includes a native fallback install path.

## Quick Start

### Docker Compose

```bash
./install.sh
```

If Docker is available, that will build and start the stack automatically. Then open:

```text
http://127.0.0.1:3000
```

### Native Linux

If Docker is not available, the same `./install.sh` script falls back to a local virtual environment and Reflex runtime.

After installation, start it with:

```bash
./start.sh
```

## What It Needs

- Python 3.13 or newer for the native path
- Docker + Docker Compose for the recommended path
- Outbound internet access to reach the upstream channel source

## Environment Variables

- `PORT`: public port for the app, default `3000`
- `API_URL`: URL used in generated stream and playlist links
- `PROXY_CONTENT`: `TRUE` to proxy video content through this server, `FALSE` to expose direct upstream content URLs
- `SOCKS5`: optional SOCKS5 proxy for upstream requests
- `DLHD_BASE_URL`: optional upstream source override, defaults to `https://dlhd.sx`

If `API_URL` is not set, the app now falls back to `http://127.0.0.1:${PORT}` automatically.

## Scripts

- `install.sh`: install and start the app
- `start.sh`: launch the app again after installation
- `stop.sh`: stop the app cleanly
- `status.sh`: check the container or local runtime health

## Files Worth Knowing

- `Dockerfile`: Docker image definition for the Linux backup
- `docker-compose.yml`: compose stack with the app and runtime env
- `Caddyfile`: reverse proxy and static front-end serving
- `requirements.txt`: Python runtime dependencies
- `BACKUP_NOTES.md`: short operational notes for this snapshot

## Development Notes

- The startup path now loads channels before the refresh loop starts, which avoids the blank first-load race that caused the front end to hang.
- The dependency list now explicitly includes the packages imported by the app code.
- The Docker build restores the Reflex export flow so the front end and backend are packaged together again.

## Playlist

The playlist is available at:

```text
http://127.0.0.1:3000/playlist.m3u8
```

## Troubleshooting

- If the UI loads but channels are empty, check that outbound access to the upstream source is allowed.
- If Docker build fails, make sure the `docker` daemon is running and `docker compose version` works from the shell.
- If the native path fails, confirm `python3`, `venv`, and `pip` are installed on the host.

## Screenshots

- Home page
- Watch page
- Live events page

## License

This repository snapshot follows the same upstream project licensing and usage expectations as the original StepDaddyLiveHD project.
