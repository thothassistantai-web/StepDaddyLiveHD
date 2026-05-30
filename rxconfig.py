import reflex as rx
import os


proxy_content = os.environ.get("PROXY_CONTENT", "TRUE").upper() == "TRUE"
socks5 = os.environ.get("SOCKS5", "")
port = os.environ.get("PORT", "3000")
api_url = os.environ.get("API_URL") or f"http://127.0.0.1:{port}"
api_url = api_url.rstrip("/")

print(f"PROXY_CONTENT: {proxy_content}\nSOCKS5: {socks5}\nAPI_URL: {api_url}")

config = rx.Config(
    app_name="StepDaddyLiveHD",
    api_url=api_url,
    proxy_content=proxy_content,
    socks5=socks5,
    show_built_with_reflex=False,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
