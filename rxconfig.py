import reflex as rx
import os


proxy_content = os.environ.get("PROXY_CONTENT", "TRUE").upper() == "TRUE"
socks5 = os.environ.get("SOCKS5", "")
api_url = os.environ.get("API_URL", "http://localhost:3000")
dlhd_base_url = os.environ.get("DLHD_BASE_URL", "https://dlhd.pk")

config = rx.Config(
    app_name="StepDaddyLiveHD",
    proxy_content=proxy_content,
    socks5=socks5,
    api_url=api_url,
    dlhd_base_url=dlhd_base_url,
    show_built_with_reflex=False,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
