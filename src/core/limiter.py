import asyncio
import inspect
# Monkeypatch to prevent slowapi Python 3.14+ deprecation warnings
if hasattr(inspect, "iscoroutinefunction"):
    asyncio.iscoroutinefunction = inspect.iscoroutinefunction  # type: ignore

from slowapi import Limiter
from slowapi.util import get_remote_address
from src.core.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url
)
