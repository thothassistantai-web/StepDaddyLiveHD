# StepDaddyLiveHD v2.0 — Migration Guide

## Overview

StepDaddyLiveHD v2.0 is a complete modernization of the original archived project.
It upgrades Python compatibility, replaces the HTTP client, introduces a provider
registry for automatic domain failover, and improves security and error handling.

## Breaking Changes

### 1. Dependencies
- **Removed:** `curl-cffi` — replaced with `httpx` (native async, better maintained)
- **Removed:** `reflex` frontend build chain simplified (still uses Reflex 0.8.13)
- **Added:** `pydantic` v2 for data validation
- **Added:** `python-dotenv` for local development

### 2. Stream Resolution
- **New flow:** `watch/stream-{id}.php` → iframe → `window.atob()` → m3u8
- **Legacy flow:** `stream/stream-{id}.php` → iframe → `auth.php` → `server_lookup.php`
- The new flow is tried first; legacy flow is the fallback.

### 3. Configuration
- **NEW:** `DLHD_BASE_URL` env var — controls the primary provider domain
- **NEW:** `provider_registry.py` — manages multiple provider domains with auto-fallback
- **Removed:** Hardcoded `self._base_url = "https://dlhd.dad"` in step_daddy.py

### 4. Security
- **Removed:** `verify=False` from all HTTP clients — SSL verification is now enforced
- **Added:** Proper CORS headers for IPTV client compatibility
- **Added:** `/health` endpoint for monitoring

### 5. Channel Model
- **Added:** `dead` flag for dead channels
- **Added:** `tvg_id` field for EPG mapping
- Changed from `rx.Base` to `rx.Base` (still compatible)

## Step-by-Step Migration

### From v1.x (original archived)

1. **Update `.env` file:**
   ```bash
   # Old
   PORT="3000"
   API_URL="http://localhost:3000"
   PROXY_CONTENT="TRUE"
   SOCKS5=""

   # New — add DLHD_BASE_URL
   PORT="3000"
   API_URL="http://localhost:3000"
   PROXY_CONTENT="TRUE"
   SOCKS5=""
   DLHD_BASE_URL="https://dlhd.pk"
   ```

2. **Update dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Rebuild Docker:**
   ```bash
   docker-compose build --no-cache
   docker-compose up -d
   ```

4. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

5. **Verify health:**
   ```bash
   curl http://localhost:3000/health
   ```

## Provider Registry

The provider registry (`StepDaddyLiveHD/provider_registry.py`) contains a list
of verified DaddyLive/DLHD domains. The application automatically tries each
provider in priority order when resolving streams or loading channels.

### Adding a new provider

Edit `provider_registry.py` and add a new entry:

```python
Provider(
    name="My Custom Provider",
    base_url="https://dlhd.example.com",
    priority=10,
).model_dump(),
```

Lower priority number = tried first.

## Stream Resolution Flow

```
Client Request
      │
      ▼
 ┌─────────────────────┐
 │  Provider Registry   │ ──── Try provider 1 (priority 1)
 │  (sorted by priority)│ ──── Try provider 2 (priority 2)
 │                      │ ──── ... fallback ...
 └────────┬────────────┘
          │
          ▼
 ┌─────────────────────┐
 │  New Flow           │
 │  watch/stream-*.php │
 │  → iframe src       │
 │  → window.atob()    │
 │  → m3u8 URL         │
 └────────┬────────────┘
          │ (if new flow fails)
          ▼
 ┌─────────────────────┐
 │  Legacy Flow        │
 │  stream/stream-*.php│
 │  → iframe src       │
 │  → decode_bundle    │
 │  → auth.php         │
 │  → server_lookup.php│
 │  → m3u8 URL         │
 └────────┬────────────┘
          │
          ▼
 ┌─────────────────────┐
 │  Rewrite Playlist   │
  │  ─ Proxy key URLs  │
  │  ─ Proxy segments  │
  └─────────────────────┘
```

## Verified Provider Domains (2026-06-08)

| Provider | Base URL | Priority | Status |
|----------|----------|----------|--------|
| DLHD Primary | https://dlhd.pk | 1 | ✅ Active |
| DLHD Alternative 1 | https://dlhd.sx | 2 | ⚠️ Check |
| DLHD Alternative 2 | https://daddy.tv | 3 | ⚠️ Check |

> **Note:** Domains marked ⚠️ should be verified before relying on them.
> DaddyLive frequently changes domains; update `provider_registry.py` as needed.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test class
pytest tests/ -v -k TestProviderRegistry

# Run with coverage
pytest tests/ -v --cov=StepDaddyLiveHD --cov-report=term-missing
```

## Troubleshooting

### "Failed to resolve stream for channel"
- Check provider health: `GET /health`
- Update `DLHD_BASE_URL` in `.env` to a working domain
- Add fallback domains to `provider_registry.py`

### "No channels loaded"
- Verify `DLHD_BASE_URL` is accessible
- Check `meta.json` exists at `StepDaddyLiveHD/meta.json`
- Run `curl -I https://dlhd.pk/24-7-channels.php`

### Docker build fails
- Ensure Docker is running
- Clear build cache: `docker-compose build --no-cache`
- Check Python 3.12 availability
