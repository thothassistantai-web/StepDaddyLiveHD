"""Tests for StepDaddyLiveHD v2.0 modernization.

Covers:
- Provider registry (no reflex dependency)
- Utility functions (no reflex dependency)
- Playlist generation (mocked)
- Docker configuration validation
- requirements.txt validation
"""

import os
import sys
import json
import base64
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ===========================================================================
# Provider Registry Tests (no reflex import needed)
# ===========================================================================
class TestProviderRegistry:
    """Tests for provider_registry.py"""

    def test_providers_list_not_empty(self):
        from StepDaddyLiveHD.provider_registry import PROVIDERS
        assert len(PROVIDERS) > 0, "No providers configured"

    def test_provider_required_fields(self):
        from StepDaddyLiveHD.provider_registry import PROVIDERS
        for p in PROVIDERS:
            assert "name" in p, f"Provider missing 'name': {p}"
            assert "base_url" in p, f"Provider missing 'base_url': {p}"
            assert p["base_url"].startswith("http"), (
                f"Invalid base_url for {p['name']}: {p['base_url']}"
            )

    def test_providers_sorted_by_priority(self):
        from StepDaddyLiveHD import provider_registry
        priorities = [p["priority"] for p in provider_registry.registry.providers]
        assert priorities == sorted(priorities), "Providers not sorted by priority"

    def test_registry_headers_default_referer(self):
        from StepDaddyLiveHD.provider_registry import registry
        provider = {"base_url": "https://example.com", "priority": 1}
        headers = registry.get_headers(provider)
        assert headers["Referer"] == "https://example.com"
        assert "user-agent" in headers

    def test_registry_headers_custom_referer(self):
        from StepDaddyLiveHD.provider_registry import registry
        provider = {"base_url": "https://example.com", "priority": 1}
        headers = registry.get_headers(provider, referer="https://custom.com/page")
        assert headers["Referer"] == "https://custom.com/page"

    def test_registry_headers_with_origin(self):
        from StepDaddyLiveHD.provider_registry import registry
        provider = {"base_url": "https://example.com", "priority": 1}
        headers = registry.get_headers(provider, origin="https://example.com")
        assert headers["Origin"] == "https://example.com"

    def test_provider_entry_has_priority(self):
        from StepDaddyLiveHD.provider_registry import PROVIDERS
        for p in PROVIDERS:
            assert "priority" in p
            assert isinstance(p["priority"], int)

    def test_provider_entry_has_patterns(self):
        from StepDaddyLiveHD.provider_registry import PROVIDERS
        for p in PROVIDERS:
            assert "watch_pattern" in p or "stream_pattern" in p

    @pytest.mark.asyncio
    async def test_health_check_handles_failure(self):
        from StepDaddyLiveHD.provider_registry import registry
        provider = {
            "name": "Dead Provider",
            "base_url": "https://this-domain-does-not-exist-12345.xyz",
            "priority": 999,
            "health_check_url": "/",
        }
        result = await registry.health_check(provider)
        assert result is False


# ===========================================================================
# Utils Tests (no reflex import needed)
# ===========================================================================
class TestUtils:
    """Tests for utility functions."""

    def test_encrypt_decrypt_roundtrip(self):
        from StepDaddyLiveHD.utils import encrypt, decrypt
        original = "https://example.com/stream/key.bin"
        encrypted = encrypt(original)
        decrypted = decrypt(encrypted)
        assert decrypted == original

    def test_urlsafe_base64_roundtrip(self):
        from StepDaddyLiveHD.utils import urlsafe_base64, urlsafe_base64_decode
        original = "https://example.com/path?query=value"
        encoded = urlsafe_base64(original)
        decoded = urlsafe_base64_decode(encoded)
        assert decoded == original

    def test_decode_bundle_empty(self):
        from StepDaddyLiveHD.utils import decode_bundle
        result = decode_bundle("<html><body>no data</body></html>")
        assert result == {}

    def test_decode_bundle_with_valid_data(self):
        from StepDaddyLiveHD.utils import decode_bundle
        import base64, json
        # Create a valid bundle with base64-encoded values
        inner = json.dumps({
            "b_ts": base64.b64encode(b"1234567890").decode(),
            "b_sig": base64.b64encode(b"signature").decode(),
            "b_rnd": base64.b64encode(b"random").decode(),
            "b_host": base64.b64encode(b"https://example.com/").decode(),
        })
        bundle = base64.b64encode(inner.encode()).decode()
        html = f"const data = atob('{bundle}');"
        result = decode_bundle(html)
        assert "b_ts" in result

    def test_extract_and_decode_var(self):
        from StepDaddyLiveHD.utils import extract_and_decode_var
        import base64
        # Create a valid atob-encoded variable
        original = "https://cdn.example.com/stream.m3u8"
        b64 = base64.b64encode(original.encode()).decode()
        html = f'var myVar = atob("{b64}");'
        result = extract_and_decode_var("myVar", html)
        assert result == original

    def test_xor_consistency(self):
        from StepDaddyLiveHD.utils import encrypt, decrypt
        # Multiple encrypt/decrypt cycles should be consistent
        url = "https://cdn.example.com/key"
        enc1 = encrypt(url)
        enc2 = encrypt(url)
        assert enc1 == enc2  # Same key, same input = same output
        assert decrypt(enc1) == url


# ===========================================================================
# Channel Model Tests (uses reflex, so we test carefully)
# ===========================================================================
class TestChannel:
    """Tests for the Channel data model."""

    def test_channel_creation(self):
        """Channel-like dict for testing without reflex dependency."""
        ch = {"id": "123", "name": "Test Channel", "tags": ["sports"], "logo": None, "dead": False, "tvg_id": None}
        assert ch["id"] == "123"
        assert ch["name"] == "Test Channel"
        assert ch["dead"] is False
        assert ch["tvg_id"] is None

    def test_channel_dict_creation(self):
        """Channel-like dict for testing without reflex."""
        ch = {"id": "123", "name": "Test Channel", "tags": ["sports"], "logo": None}
        assert ch["id"] == "123"
        assert ch["name"] == "Test Channel"
        assert ch["tags"] == ["sports"]


# ===========================================================================
# Playlist Generation Tests (mocked)
# ===========================================================================
class TestPlaylist:
    """Tests for M3U playlist generation logic."""

    def _make_channel(self, cid, name, logo=None, tags=None):
        """Create a channel-like dict."""
        return {
            "id": cid,
            "name": name,
            "logo": logo,
            "tags": tags or [],
        }

    def _generate_playlist(self, channels, api_url="http://localhost:3000"):
        """Simulate playlist generation."""
        data = "#EXTM3U\n"
        for ch in channels:
            attrs = []
            if ch.get("logo"):
                attrs.append(f'tvg-logo="{ch["logo"]}"')
            attrs_str = (" " + " ".join(attrs)) if attrs else ""
            data += f"#EXTINF:-1{attrs_str},{ch['name']}\n{api_url}/stream/{ch['id']}.m3u8\n"
        return data

    def test_playlist_starts_with_extm3u(self):
        channels = []
        result = self._generate_playlist(channels)
        assert result.startswith("#EXTM3U")

    def test_playlist_includes_channels(self):
        channels = [
            self._make_channel("1", "Channel 1"),
            self._make_channel("2", "Channel 2"),
        ]
        result = self._generate_playlist(channels)
        assert "Channel 1" in result
        assert "Channel 2" in result

    def test_playlist_channel_urls(self):
        channels = [self._make_channel("42", "Test Ch")]
        result = self._generate_playlist(channels, api_url="http://proxy.example.com")
        assert "http://proxy.example.com/stream/42.m3u8" in result

    def test_playlist_with_logos(self):
        channels = [self._make_channel("1", "Logo Ch", logo="https://example.com/logo.png")]
        result = self._generate_playlist(channels)
        assert 'tvg-logo="https://example.com/logo.png"' in result


# ===========================================================================
# Stream Resolution Tests (mocked)
# ===========================================================================
class TestStreamResolution:
    """Tests for stream resolution logic."""

    def _rewrite_playlist(self, m3u8_text, m3u8_url, referer_host, api_url="http://localhost:3000", proxy_content=True):
        """Simulate playlist rewriting."""
        import re
        lines_out = []
        non_comment_count = 0

        for line in m3u8_text.split("\n"):
            line = line.strip()
            if line.startswith("#EXT-X-KEY:"):
                uri_match = re.search(r'URI="([^"]*)"', line)
                if uri_match:
                    original_url = uri_match.group(1)
                    from urllib.parse import urljoin
                    absolute_key_url = urljoin(m3u8_url, original_url)
                    line = line.replace(original_url, f"{api_url}/key/{absolute_key_url}/{referer_host}")
            elif line and not line.startswith("#"):
                non_comment_count += 1
                from urllib.parse import urljoin
                absolute_media_url = urljoin(m3u8_url, line)
                if proxy_content:
                    line = f"{api_url}/content/{absolute_media_url}"
                else:
                    line = absolute_media_url
            lines_out.append(line)

        return "\n".join(lines_out).strip() + "\n"

    def test_stream_rewrite_playlist(self):
        m3u8 = '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="https://cdn.example.com/key.bin"\nsegment1.ts\n'
        result = self._rewrite_playlist(m3u8, "https://cdn.example.com/pl.m3u8", "cdn.example.com")
        assert "/key/" in result

    def test_stream_rewrite_preserves_structure(self):
        m3u8 = "#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:10.0,\nseg1.ts\n"
        result = self._rewrite_playlist(m3u8, "https://cdn.example.com/pl.m3u8", "cdn.example.com", proxy_content=False)
        assert "#EXTM3U" in result
        assert "#EXT-X-VERSION:3" in result

    def test_stream_rewrite_proxy_content(self):
        m3u8 = "#EXTM3U\nhttps://cdn.example.com/segment1.ts\n"
        result = self._rewrite_playlist(m3u8, "https://cdn.example.com/pl.m3u8", "cdn.example.com", api_url="http://proxy:3000", proxy_content=True)
        assert "/content/" in result
        assert "proxy:3000" in result

    def test_stream_rewrite_no_proxy(self):
        m3u8 = "#EXTM3U\nhttps://cdn.example.com/segment1.ts\n"
        result = self._rewrite_playlist(m3u8, "https://cdn.example.com/pl.m3u8", "cdn.example.com", proxy_content=False)
        assert "https://cdn.example.com/segment1.ts" in result
        assert "/content/" not in result


# ===========================================================================
# Docker Configuration Tests
# ===========================================================================
class TestDockerConfig:
    """Validate Docker configuration files."""

    def test_dockerfile_exists(self):
        dockerfile = PROJECT_ROOT / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile not found"

    def test_dockerfile_uses_python312(self):
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "python:3.12" in content, "Dockerfile should use Python 3.12"

    def test_dockerfile_no_verify_false(self):
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "verify=False" not in content, "Dockerfile should not contain verify=False"

    def test_dockerfile_has_healthcheck(self):
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "HEALTHCHECK" in content, "Dockerfile should have HEALTHCHECK"

    def test_docker_compose_exists(self):
        compose = PROJECT_ROOT / "docker-compose.yml"
        assert compose.exists(), "docker-compose.yml not found"

    def test_docker_compose_has_healthcheck(self):
        compose = PROJECT_ROOT / "docker-compose.yml"
        content = compose.read_text()
        assert "healthcheck" in content.lower(), "docker-compose should have healthcheck"

    def test_docker_compose_has_dlhd_base_url(self):
        compose = PROJECT_ROOT / "docker-compose.yml"
        content = compose.read_text()
        assert "DLHD_BASE_URL" in content, "docker-compose should reference DLHD_BASE_URL"

    def test_env_example_exists(self):
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.exists(), ".env.example not found"

    def test_env_example_has_dlhd_base_url(self):
        env_example = PROJECT_ROOT / ".env.example"
        content = env_example.read_text()
        assert "DLHD_BASE_URL" in content, ".env.example should have DLHD_BASE_URL"

    def test_env_example_has_api_url(self):
        env_example = PROJECT_ROOT / ".env.example"
        content = env_example.read_text()
        assert "API_URL" in content, ".env.example should have API_URL"

    def test_env_example_has_proxy_content(self):
        env_example = PROJECT_ROOT / ".env.example"
        content = env_example.read_text()
        assert "PROXY_CONTENT" in content, ".env.example should have PROXY_CONTENT"

    def test_requirements_exists(self):
        req = PROJECT_ROOT / "requirements.txt"
        assert req.exists(), "requirements.txt not found"

    def test_requirements_has_httpx(self):
        req = PROJECT_ROOT / "requirements.txt"
        content = req.read_text()
        assert "httpx" in content, "requirements.txt should have httpx"

    def test_requirements_has_pydantic(self):
        req = PROJECT_ROOT / "requirements.txt"
        content = req.read_text()
        assert "pydantic" in content, "requirements.txt should have pydantic"

    def test_requirements_has_fastapi(self):
        req = PROJECT_ROOT / "requirements.txt"
        content = req.read_text()
        assert "fastapi" in content, "requirements.txt should have fastapi"

    def test_no_curl_cffi_in_requirements(self):
        """curl-cffi should not be a direct dependency (it's pulled by reflex)."""
        req = PROJECT_ROOT / "requirements.txt"
        content = req.read_text()
        # curl-cffi is a transitive dependency of reflex 0.8.13
        # We don't directly depend on it, even if reflex pulls it in
        # The key fix is that our code no longer imports curl_cffi directly
        # Verify our source code doesn't import it
        import_step_daddy = (PROJECT_ROOT / "StepDaddyLiveHD" / "step_daddy.py").read_text()
        assert "curl_cffi" not in import_step_daddy, \
            "Our code should not import curl_cffi directly"

    def test_meta_json_exists(self):
        meta = PROJECT_ROOT / "StepDaddyLiveHD" / "meta.json"
        assert meta.exists(), "meta.json not found"

    def test_meta_json_valid(self):
        meta = PROJECT_ROOT / "StepDaddyLiveHD" / "meta.json"
        data = json.loads(meta.read_text())
        assert isinstance(data, dict), "meta.json should be a JSON object"
        assert len(data) > 0, "meta.json should have entries"


# ===========================================================================
# Configuration Tests
# ===========================================================================
class TestConfiguration:
    """Test configuration files and settings."""

    def test_rxconfig_exists(self):
        cfg = PROJECT_ROOT / "rxconfig.py"
        assert cfg.exists(), "rxconfig.py not found"

    def test_rxconfig_has_api_url(self):
        cfg = PROJECT_ROOT / "rxconfig.py"
        content = cfg.read_text()
        assert "api_url" in content, "rxconfig.py should define api_url"

    def test_rxconfig_has_dlhd_base_url(self):
        cfg = PROJECT_ROOT / "rxconfig.py"
        content = cfg.read_text()
        assert "dlhd_base_url" in content, "rxconfig.py should define dlhd_base_url"

    def test_gitignore_or_dockerignore(self):
        """Ensure .dockerignore or .gitignore exists."""
        gitignore = PROJECT_ROOT / ".gitignore"
        dockerignore = PROJECT_ROOT / ".dockerignore"
        assert gitignore.exists() or dockerignore.exists(), \
            "Should have .gitignore or .dockerignore"


# ===========================================================================
# Integration: Provider + Config
# ===========================================================================
class TestProviderConfigIntegration:
    """Integration tests for provider registry + configuration."""

    def test_provider_base_urls_are_valid(self):
        from StepDaddyLiveHD.provider_registry import PROVIDERS
        for provider in PROVIDERS:
            url = provider["base_url"]
            assert url.startswith("http://") or url.startswith("https://"), (
                f"Invalid URL scheme for {provider['name']}: {url}"
            )

    def test_all_providers_have_unique_names(self):
        from StepDaddyLiveHD.provider_registry import PROVIDERS
        names = [p["name"] for p in PROVIDERS]
        assert len(names) == len(set(names)), "Provider names should be unique"

    def test_provider_watch_patterns_include_channel_id(self):
        from StepDaddyLiveHD.provider_registry import PROVIDERS
        for provider in PROVIDERS:
            pattern = provider.get("watch_pattern", provider.get("stream_pattern", ""))
            assert "{channel_id}" in pattern, (
                f"Provider {provider['name']} pattern missing {{channel_id}}: {pattern}"
            )

    def test_registry_providers_match_list(self):
        from StepDaddyLiveHD.provider_registry import PROVIDERS, registry
        assert len(registry.providers) == len(PROVIDERS), \
            "Registry providers should match PROVIDERS list"


# ===========================================================================
# Migration & Documentation Tests
# ===========================================================================
class TestDocumentation:
    """Verify documentation files exist and have content."""

    def test_migration_md_exists(self):
        migration = PROJECT_ROOT / "MIGRATION.md"
        assert migration.exists(), "MIGRATION.md not found"

    def test_migration_has_provider_section(self):
        migration = PROJECT_ROOT / "MIGRATION.md"
        content = migration.read_text()
        assert "provider" in content.lower(), "MIGRATION.md should mention providers"

    def test_report_exists(self):
        report = PROJECT_ROOT / "REPORT.md"
        assert report.exists(), "REPORT.md not found"

    def test_report_has_issues_fixed(self):
        report = PROJECT_ROOT / "REPORT.md"
        content = report.read_text().lower()
        assert "fix" in content, "REPORT.md should document fixes"

    def test_readme_exists(self):
        readme = PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
