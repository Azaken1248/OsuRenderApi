import asyncio
import inspect
# Monkeypatch to prevent slowapi Python 3.14+ deprecation warnings
if hasattr(inspect, "iscoroutinefunction"):
    asyncio.iscoroutinefunction = inspect.iscoroutinefunction  # type: ignore

from slowapi import Limiter
from slowapi.util import get_remote_address
from src.core.config import get_settings

settings = get_settings()

def get_real_ip(request):
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(
    key_func=get_real_ip,
    storage_uri=settings.redis_url
)
