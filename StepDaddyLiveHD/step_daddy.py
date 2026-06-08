import json
import re
import base64
import html
import logging
from typing import List, Optional
from urllib.parse import quote, urlparse, urljoin

import httpx
import reflex as rx
from pydantic import BaseModel

from .utils import encrypt, decrypt, urlsafe_base64, decode_bundle
from .provider_registry import registry

logger = logging.getLogger(__name__)


class Channel(BaseModel):
    id: str
    name: str
    tags: List[str] = []
    logo: Optional[str] = None
    dead: bool = False
    tvg_id: Optional[str] = None


class StepDaddy:
    """Stream resolver for DaddyLive/DLHD.

    Uses the provider registry to dynamically select a working provider
    domain instead of relying on a single hardcoded URL. Falls back
    through providers automatically when one fails.
    """

    def __init__(self):
        self._provider = None
        self._session: Optional[httpx.AsyncClient] = None
        self.channels: List[Channel] = []
        self._meta = {}
        self._load_meta()

    def _load_meta(self):
        try:
            with open("StepDaddyLiveHD/meta.json", "r") as f:
                self._meta = json.load(f)
        except FileNotFoundError:
            logger.warning("meta.json not found, channel metadata will be empty")
            self._meta = {}

    async def _get_session(self) -> httpx.AsyncClient:
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(30.0, connect=10.0),
                verify=True,
                follow_redirects=True,
            )
        return self._session

    async def close(self):
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    @property
    def base_url(self) -> str:
        if self._provider is None:
            self._provider = registry.providers[0]
        return self._provider["base_url"]

    def _headers(self, referer: str = None, origin: str = None) -> dict:
        if referer is None:
            referer = self.base_url
        headers = {
            "Referer": referer,
            "User-Agent": (
                "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:137.0) "
                "Gecko/20100101 Firefox/137.0"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
        }
        if origin:
            headers["Origin"] = origin
        return headers

    async def _try_with_provider(self, provider: dict, channel_id: str) -> Optional[str]:
        """Attempt to resolve a stream using a specific provider.

        Supports both HLS (.m3u8) and DASH (.mpd) manifest resolution.
        """
        base = provider["base_url"]
        session = await self._get_session()

        try:
            # --- New flow: watch page -> iframe -> atob source ---
            watch_url = f"{base}/watch/stream-{channel_id}.php"
            watch_response = await session.get(
                watch_url, headers=self._headers(base)
            )
            if watch_response.status_code == 200:
                # Extract all iframe src URLs
                iframe_urls = re.findall(
                    r'iframe\s+src="([^"]+)"', watch_response.text
                )
                for source_page_url in iframe_urls:
                    source_page_response = await session.get(
                        source_page_url,
                        headers=self._headers(watch_url),
                    )
                    # Extract Base64-encoded stream URLs from atob() calls
                    # Pattern handles both single and double quotes
                    atob_matches = re.findall(
                        r'source:\s*window\.atob\([\'"]([^\'"]+)[\'"]\)',
                        source_page_response.text,
                    )
                    for source_b64 in atob_matches:
                        try:
                            decoded_url = base64.b64decode(
                                source_b64
                            ).decode()
                            stream_response = await session.get(
                                decoded_url,
                                headers=self._headers(source_page_url),
                            )
                            if stream_response.status_code == 200:
                                content = stream_response.text
                                # Detect DASH manifest vs HLSL playlist
                                is_dash = (
                                    decoded_url.endswith(".mpd")
                                    or content.lstrip().startswith("<MPD")
                                    or content.lstrip().startswith('<?xml')
                                    and "MPD" in content[:500]
                                )
                                if is_dash:
                                    logger.info(
                                        "DASH manifest detected for channel %s via %s",
                                        channel_id, provider["name"],
                                    )
                                    return self._rewrite_manifest(
                                        content,
                                        decoded_url,
                                        urlparse(source_page_url).netloc,
                                    )
                                else:
                                    return self._rewrite_playlist(
                                        content,
                                        decoded_url,
                                        urlparse(source_page_url).netloc,
                                    )
                        except Exception:
                            continue

            # --- Legacy flow: stream page -> iframe -> auth -> server_lookup ---
            stream_url = f"{base}/stream/stream-{channel_id}.php"
            response = await session.get(
                stream_url, headers=self._headers(base)
            )
            if response.status_code != 200:
                return None

            matches = re.findall(
                r'iframe\s+src="([^"]+)"', response.text
            )
            if not matches:
                return None

            source_url = matches[0]
            source_response = await session.get(
                source_url, headers=self._headers(stream_url)
            )
            if source_response.status_code != 200:
                return None

            # Extract channel key
            channel_key_match = re.findall(
                r'const\s+CHANNEL_KEY\s*=\s*"([^\"]+)";',
                source_response.text,
            )
            if not channel_key_match:
                return None
            channel_key = channel_key_match[-1]

            # Decode auth bundle
            data = decode_bundle(source_response.text)
            auth_ts = data.get("b_ts", "")
            auth_sig = data.get("b_sig", "")
            auth_rnd = data.get("b_rnd", "")
            auth_url = data.get("b_host", "")

            auth_request_url = (
                f"{auth_url}auth.php?"
                f"channel_id={channel_key}&ts={auth_ts}"
                f"&rnd={auth_rnd}&sig={auth_sig}"
            )
            auth_response = await session.get(
                auth_request_url, headers=self._headers(source_url)
            )
            if auth_response.status_code != 200:
                return None

            # Get server key
            parsed = urlparse(source_url)
            key_url = (
                f"{parsed.scheme}://{parsed.netloc}"
                f"/server_lookup.php?channel_id={channel_key}"
            )
            key_response = await session.get(
                key_url, headers=self._headers(source_url)
            )
            server_key = key_response.json().get("server_key")
            if not server_key:
                return None

            # Build m3u8 URL
            if server_key == "top1/cdn":
                m3u8_url = (
                    f"https://top1.newkso.ru/top1/cdn/"
                    f"{channel_key}/mono.m3u8"
                )
            else:
                m3u8_url = (
                    f"https://{server_key}new.newkso.ru/"
                    f"{server_key}/{channel_key}/mono.m3u8"
                )

            m3u8_response = await session.get(
                m3u8_url,
                headers=self._headers(quote(str(source_url))),
            )
            if m3u8_response.status_code != 200:
                return None

            return self._rewrite_playlist(
                m3u8_response.text,
                m3u8_url,
                urlparse(source_url).netloc,
            )

        except Exception as e:
            logger.warning(
                "Provider %s failed for channel %s: %s",
                provider["name"], channel_id, e,
            )
            return None

    def _rewrite_playlist(
        self, m3u8_text: str, m3u8_url: str, referer_host: str
    ) -> str:
        """Rewrite an m3u8 playlist to route through the proxy."""
        import os

        api_url = os.environ.get("API_URL", "http://localhost:3000")
        proxy_content = (
            os.environ.get("PROXY_CONTENT", "TRUE").upper() == "TRUE"
        )

        lines_out = []
        non_comment_count = 0

        for line in m3u8_text.split("\n"):
            line = line.strip()
            if line.startswith("#EXT-X-KEY:"):
                uri_match = re.search(r'URI="([^"]*)"', line)
                if uri_match:
                    original_url = uri_match.group(1)
                    absolute_key_url = urljoin(m3u8_url, original_url)
                    line = line.replace(
                        original_url,
                        f"{api_url}/key/{encrypt(absolute_key_url)}"
                        f"/{encrypt(referer_host)}",
                    )
            elif line and not line.startswith("#"):
                non_comment_count += 1
                absolute_media_url = urljoin(m3u8_url, line)
                if proxy_content:
                    line = f"{api_url}/content/{encrypt(absolute_media_url)}"
                else:
                    line = absolute_media_url
            lines_out.append(line)

        has_extm3u = any(l.startswith("#EXTM3U") for l in lines_out)
        if not has_extm3u and non_comment_count == 1:
            media_line = next(
                (l for l in lines_out if l and not l.startswith("#")), ""
            )
            return (
                f"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=8000000\n"
                f"{media_line}\n"
            )

        return "\n".join(lines_out).strip() + "\n"

    def _rewrite_manifest(
        self, mpd_text: str, mpd_url: str, referer_host: str
    ) -> str:
        """Rewrite a DASH (.mpd) manifest to route segments through the proxy.

        Rewrites:
        - <SegmentTemplate> media/initialization URLs
        - <SegmentURL> media URLs
        - BaseURL elements
        - Any absolute HTTP(S) URLs found in the manifest
        """
        import os
        from xml.etree import ElementTree

        api_url = os.environ.get("API_URL", "http://localhost:3000")
        proxy_content = (
            os.environ.get("PROXY_CONTENT", "TRUE").upper() == "TRUE"
        )

        if not proxy_content:
            return mpd_text

        # Parse the XML manifest
        try:
            root = ElementTree.fromstring(mpd_text)
        except ElementTree.ParseError:
            logger.warning("Failed to parse DASH manifest, returning as-is")
            return mpd_text

        # Define namespace map for DASH
        ns = {"dash": "urn:mpeg:dash:schema:mpd:2011"}

        def _proxy_url(url: str) -> str:
            """Encrypt a URL for proxy routing."""
            absolute = urljoin(mpd_url, url)
            return f"{api_url}/content/{encrypt(absolute)}"

        def _rewrite_element_urls(elem):
            """Recursively rewrite URLs in manifest elements."""
            # Rewrite attributes that contain URLs
            for attr_name in ("media", "initialization", "sourceURL", "BaseURL"):
                attr_val = elem.get(attr_name)
                if attr_val and attr_val.startswith("http"):
                    elem.set(attr_name, _proxy_url(attr_val))

            # Handle text content of BaseURL elements
            if elem.tag.endswith("BaseURL") and elem.text:
                text = elem.text.strip()
                if text.startswith("http"):
                    elem.text = _proxy_url(text)

            # Handle SegmentList/SegmentURL elements
            if elem.tag.endswith("SegmentURL"):
                media_val = elem.get("media")
                if media_val and media_val.startswith("http"):
                    elem.set("media", _proxy_url(media_val))

            # Handle SegmentTemplate
            if elem.tag.endswith("SegmentTemplate"):
                for attr in ("media", "initialization", "index"):
                    val = elem.get(attr)
                    if val and val.startswith("http"):
                        elem.set(attr, _proxy_url(val))

            for child in elem:
                _rewrite_element_urls(child)

        # Walk all elements and rewrite URLs
        _rewrite_element_urls(root)

        # Also do a regex pass for any URL patterns the XML parser might have missed
        # This catches URLs in attributes without namespace prefixes
        rewritten = ElementTree.tostring(root, encoding="unicode", xml_declaration=True)

        # Regex fallback: catch any remaining http(s) URLs in the manifest
        def _rewrite_remaining(match):
            url = match.group(0)
            if api_url in url or url.startswith("data:"):
                return url
            return _proxy_url(url)

        rewritten = re.sub(
            r'https?://[^\s<>"\'\\{}|^`\\\\]+',
            _rewrite_remaining,
            rewritten,
        )

        return rewritten

    async def load_channels(self) -> List[Channel]:
        """Load channel list from the first working provider."""
        session = await self._get_session()

        for provider in sorted(
            registry.providers, key=lambda p: p["priority"]
        ):
            base = provider["base_url"]
            try:
                response = await session.get(
                    f"{base}/24-7-channels.php",
                    headers=self._headers(base),
                )
                if response.status_code != 200:
                    continue

                channels = []
                matches = re.findall(
                    r'<a class="card"\s+href="/watch\.php\?id=(\d+)"'
                    r"[^>]*>\s*<div class=\"card__title\">(.*?)</div>",
                    response.text,
                    re.DOTALL,
                )

                for channel_id, channel_name in matches:
                    channel_name = (
                        html.unescape(channel_name.strip()).replace("#", "")
                    )
                    meta_key = (
                        "18+"
                        if channel_name.startswith("18+")
                        else channel_name
                    )
                    meta = self._meta.get(meta_key, {})
                    logo = meta.get("logo", "")

                    import os
                    api_url = os.environ.get(
                        "API_URL", "http://localhost:3000"
                    )
                    if logo:
                        logo = (
                            f"{api_url}/logo/{urlsafe_base64(logo)}"
                        )

                    channels.append(
                        Channel(
                            id=channel_id,
                            name=channel_name,
                            tags=meta.get("tags", []),
                            logo=logo,
                        )
                    )

                self.channels = sorted(
                    channels,
                    key=lambda ch: (ch.name.startswith("18"), ch.name),
                )
                self._provider = provider
                logger.info(
                    "Loaded %d channels from %s",
                    len(channels), provider["name"],
                )
                return self.channels

            except Exception as e:
                logger.warning(
                    "Failed to load channels from %s: %s",
                    provider["name"], e,
                )
                continue

        logger.error("All providers failed to load channels")
        self.channels = []
        return self.channels

    async def stream(self, channel_id: str) -> str:
        """Resolve a stream URL for the given channel, trying all providers."""
        for provider in sorted(
            registry.providers, key=lambda p: p["priority"]
        ):
            result = await self._try_with_provider(provider, channel_id)
            if result is not None:
                self._provider = provider
                return result

        raise ValueError(
            f"Failed to resolve stream for channel {channel_id} "
            f"from any provider"
        )

    async def key(self, url: str, host: str) -> bytes:
        """Fetch the decryption key."""
        url = decrypt(url)
        host = decrypt(host)
        session = await self._get_session()
        response = await session.get(
            url,
            headers=self._headers(f"{host}/", host),
            timeout=60,
        )
        if response.status_code != 200:
            raise Exception("Failed to get key")
        return response.content

    @staticmethod
    def content_url(path: str) -> str:
        return decrypt(path)

    @staticmethod
    def is_dash_url(path: str) -> bool:
        """Check if the decrypted path points to a DASH manifest."""
        try:
            url = decrypt(path)
            return url.endswith(".mpd") or "/premiumtv/" in url
        except Exception:
            return False

    def playlist(self, channels: List[Channel] = None) -> str:
        """Generate an M3U playlist."""
        import os
        api_url = os.environ.get("API_URL", "http://localhost:3000")

        data = "#EXTM3U\n"
        items = channels if channels is not None else self.channels
        for channel in items:
            attrs = []
            if channel.tvg_id:
                attrs.append(f'tvg-id="{channel.tvg_id}"')
            if channel.logo:
                attrs.append(f'tvg-logo="{channel.logo}"')
            attrs_str = (" " + " ".join(attrs)) if attrs else ""
            data += (
                f"#EXTINF:-1{attrs_str},{channel.name}\n"
                f"{api_url}/stream/{channel.id}.m3u8\n"
            )
        return data

    async def schedule(self) -> list:
        """Fetch the event schedule."""
        session = await self._get_session()

        for provider in sorted(
            registry.providers, key=lambda p: p["priority"]
        ):
            base = provider["base_url"]
            try:
                response = await session.get(
                    f"{base}/schedule/schedule-generated.php",
                    headers=self._headers(base),
                )
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                return []
            except Exception as e:
                logger.warning(
                    "Failed to get schedule from %s: %s",
                    provider["name"], e,
                )
                continue
        return []
