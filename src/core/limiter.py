import asyncio
import inspect

if hasattr(inspect, "iscoroutinefunction"):
    asyncio.iscoroutinefunction = inspect.iscoroutinefunction  # type: ignore

from slowapi import Limiter
from slowapi.util import get_remote_address
from src.core.config import get_settings

settings = get_settings()


def get_real_ip(request):
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    return get_remote_address(request)


limiter = Limiter(key_func=get_real_ip, storage_uri=settings.redis_url)
