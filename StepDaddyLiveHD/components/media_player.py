"""MediaPlayer component — wraps @vidstack/react player for Reflex 0.9.x."""
import reflex as rx
from reflex.components.component import NoSSRComponent


class MediaPlayer(NoSSRComponent):
    """Vidstack-based media player for HLS streams."""

    library = "$/public/player"
    lib_dependencies: list[str] = ["@vidstack/react@next"]
    tag = "Player"

    title: rx.Var[str]
    src: rx.Var[str]
    autoplay: bool = True
