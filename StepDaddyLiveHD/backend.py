"""FastAPI backend for StepDaddyLiveHD.

Provides endpoints for:
- Stream resolution (M3U8 playlists)
- Decryption key proxying
- Content segment proxying
- Playlist generation
- Schedule/event discovery
- Logo caching
- Provider health checks
"""

import os
import asyncio
import logging
from typing import List

import httpx
from fastapi import Response, status, FastAPI
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from StepDaddyLiveHD.step_daddy import StepDaddy, Channel
from .provider_registry import registry
from .utils import urlsafe_base64_decode

logger = logging.getLogger(__name__)

fastapi_app = FastAPI(title="StepDaddyLiveHD", version="2.0.0")

# CORS – allow all origins for IPTV client compatibility
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

step_daddy = StepDaddy()

# Shared HTTP client for proxying (no verify=False)
_proxy_client = httpx.AsyncClient(
    http2=True,
    timeout=httpx.Timeout(60.0, connect=10.0),
    verify=True,
    follow_redirects=True,
)


# ---------------------------------------------------------------------------
# Provider health endpoint
# ---------------------------------------------------------------------------
@fastapi_app.get("/health")
async def health():
    """Return provider health status."""
    results = {}
    healthy = False
    for provider in registry.providers:
        ok = await registry.health_check(provider)
        results[provider["name"]] = {
            "base_url": provider["base_url"],
            "healthy": ok,
            "priority": provider["priority"],
        }
        if ok:
            healthy = True
    return JSONResponse(
        content={
            "status": "healthy" if healthy else "degraded",
            "providers": results,
        },
        status_code=200 if healthy else 503,
    )


# ---------------------------------------------------------------------------
# Stream endpoints
# ---------------------------------------------------------------------------
@fastapi_app.get("/stream/{channel_id}.m3u8")
async def stream(channel_id: str):
    """Resolve and return the stream playlist/manifest for a channel.

    Supports both HLS (.m3u8) and DASH (.mpd) manifests.
    """
    try:
        content = await step_daddy.stream(channel_id)
        # Detect DASH manifest vs HLS playlist
        is_dash = content.lstrip().startswith("<MPD") or content.lstrip().startswith("<?xml")
        media_type = "application/dash+xml" if is_dash else "application/vnd.apple.mpegurl"
        ext = ".mpd" if is_dash else ".m3u8"
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{channel_id}{ext}"',
                "Access-Control-Allow-Origin": "*",
            },
        )
    except IndexError:
        return JSONResponse(
            content={"error": "Stream not found"},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    except ValueError as e:
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception("Stream error for channel %s", channel_id)
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@fastapi_app.get("/key/{url}/{host}")
async def key(url: str, host: str):
    """Proxy the decryption key."""
    try:
        content = await step_daddy.key(url, host)
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename=key",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        logger.exception("Key fetch error")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@fastapi_app.get("/content/{path:path}")
async def content(path: str):
    """Proxy media content segments."""
    try:
        target_url = step_daddy.content_url(path)
        is_dash = target_url.endswith(".mpd") or "/premiumtv/" in target_url

        async def proxy_stream():
            # Use a fresh client per stream to avoid connection reuse issues
            async with httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(None, connect=10.0),
                verify=True,
                follow_redirects=True,
            ) as client:
                async with client.stream("GET", target_url) as response:
                    async for chunk in response.aiter_bytes(
                        chunk_size=64 * 1024
                    ):
                        yield chunk

        media_type = "application/dash+xml" if is_dash else "application/octet-stream"

        return StreamingResponse(
            proxy_stream(),
            media_type=media_type,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except Exception as e:
        logger.exception("Content proxy error")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ---------------------------------------------------------------------------
# Playlist
# ---------------------------------------------------------------------------
@fastapi_app.get("/playlist.m3u8")
def playlist():
    """Return the full M3U playlist."""
    try:
        data = step_daddy.playlist()
        return Response(
            content=data,
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Content-Disposition": 'attachment; filename="playlist.m3u8"',
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        logger.exception("Playlist generation error")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------
@fastapi_app.get("/schedule")
async def schedule():
    """Return the event schedule."""
    try:
        data = await step_daddy.schedule()
        return JSONResponse(content=data)
    except Exception as e:
        logger.exception("Schedule fetch error")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ---------------------------------------------------------------------------
# Logo proxy / cache
# ---------------------------------------------------------------------------
@fastapi_app.get("/logo/{logo}")
async def logo(logo: str):
    """Fetch and cache channel logos."""
    url = urlsafe_base64_decode(logo)
    file = url.split("/")[-1]
    cache_dir = "./logo-cache"
    cache_path = os.path.join(cache_dir, file)

    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)

    if os.path.exists(cache_path):
        return FileResponse(cache_path)

    try:
        response = await _proxy_client.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:137.0) "
                    "Gecko/20100101 Firefox/137.0"
                )
            },
        )
        if response.status_code == 200:
            with open(cache_path, "wb") as f:
                f.write(response.content)
            return FileResponse(cache_path)
        return JSONResponse(
            content={"error": "Logo not found"},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    except httpx.ConnectTimeout:
        return JSONResponse(
            content={"error": "Request timed out"},
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )
    except Exception as e:
        logger.exception("Logo fetch error")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ---------------------------------------------------------------------------
# Helpers for Reflex state
# ---------------------------------------------------------------------------
def get_channels() -> List[Channel]:
    return step_daddy.channels


def get_channel(channel_id: str) -> Channel | None:
    if not channel_id:
        return None
    return next(
        (ch for ch in step_daddy.channels if ch.id == channel_id),
        None,
    )


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------
async def update_channels():
    """Periodically refresh the channel list."""
    while True:
        try:
            await step_daddy.load_channels()
            await asyncio.sleep(300)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("Channel update failed")
            await asyncio.sleep(60)
