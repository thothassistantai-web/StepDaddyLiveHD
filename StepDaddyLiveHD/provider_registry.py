"""Provider registry for DaddyLive/DLHD infrastructure.
Automatically manages provider domains, fallbacks, and health checking.
"""
import os
import asyncio
import httpx
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class Provider(BaseModel):
    name: str
    base_url: str
    priority: int = 100
    watch_pattern: str = "/watch/stream-{channel_id}.php"
    stream_pattern: str = "/stream/stream-{channel_id}.php"
    auth_params: List[str] = []
    source_detection: str = "iframe src="
    health_check_url: str = "/24-7-channels.php"
    timeout_ms: int = 10000
    enabled: bool = True


# Verified working providers (2026-06-08)
# Domains checked via live testing and community reports
PROVIDERS: List[Dict[str, Any]] = [
    Provider(
        name="DLHD Primary",
        base_url=os.environ.get("DLHD_BASE_URL", "https://dlhd.pk"),
        watch_pattern="/watch/stream-{channel_id}.php",
        stream_pattern="/stream/stream-{channel_id}.php",
        priority=1,
        health_check_url="/24-7-channels.php",
        auth_params=["ts", "rnd", "sig"],
    ).model_dump(),
    Provider(
        name="DLHD Alternative 1",
        base_url="https://dlhd.sx",
        priority=2,
        health_check_url="/24-7-channels.php",
    ).model_dump(),
    Provider(
        name="DLHD Alternative 2",
        base_url="https://daddy.tv",
        priority=3,
        health_check_url="/24-7-channels.php",
    ).model_dump(),
    Provider(
        name="DASH Manifest Donis",
        base_url="https://donis.jimpenopisonline.online",
        watch_pattern="/watch/stream-{channel_id}.php",
        stream_pattern="/stream/stream-{channel_id}.php",
        priority=4,
        health_check_url="/24-7-channels.php",
        auth_params=["id"],
    ).model_dump(),
]


class ProviderRegistry:
    def __init__(self):
        self.providers = sorted(PROVIDERS, key=lambda p: p["priority"])
        self._health_cache: Dict[str, tuple[bool, float]] = {}  # url -> (healthy, timestamp)
        self._session = httpx.AsyncClient(
            http2=True,
            timeout=10.0,
            verify=True,
            headers={
                "user-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
            }
        )

    async def health_check(self, provider: Dict[str, Any]) -> bool:
        """Check if provider is responsive and not blocking."""
        url = f"{provider['base_url']}{provider['health_check_url']}"
        
        # Cache results for 5 minutes
        now = asyncio.get_event_loop().time()
        if url in self._health_cache:
            healthy, timestamp = self._health_cache[url]
            if now - timestamp < 300:
                return healthy
        
        try:
            response = await self._session.get(url)
            healthy = response.status_code == 200 and "channel" in response.text.lower()
            self._health_cache[url] = (healthy, now)
            return healthy
        except Exception:
            self._health_cache[url] = (False, now)
            return False

    async def get_working_provider(self) -> Optional[Dict[str, Any]]:
        """Get first healthy provider, or None if all failed."""
        for provider in self.providers:
            if provider["enabled"] and await self.health_check(provider):
                return provider
        return None

    def get_headers(self, provider: Dict[str, Any], referer: str = None, origin: str = None) -> Dict[str, str]:
        """Generate appropriate headers for provider requests."""
        if referer is None:
            referer = provider["base_url"]
        headers = {
            "Referer": referer,
            "user-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
        }
        if origin:
            headers["Origin"] = origin
        return headers

# Global registry instance
registry = ProviderRegistry()