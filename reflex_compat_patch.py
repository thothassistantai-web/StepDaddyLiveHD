"""Compatibility hacks and helpers."""

import contextlib
import sys
from typing import Any


async def windows_hot_reload_lifespan_hack():
    import asyncio
    import sys
    try:
        while True:
            sys.stderr.write("\0")
            sys.stderr.flush()
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass


@contextlib.contextmanager
def pydantic_v1_patch():
    """No-op: pydantic v2 is used natively."""
    yield


with pydantic_v1_patch():
    import sqlmodel as sqlmodel


def sqlmodel_field_has_primary_key(field: Any) -> bool:
    if getattr(field.field_info, "primary_key", None) is True:
        return True
    if getattr(field.field_info, "sa_column", None) is None:
        return False
    return bool(getattr(field.field_info.sa_column, "primary_key", None))
