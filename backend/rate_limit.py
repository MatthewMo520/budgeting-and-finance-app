"""Shared rate limiter.

Uses a Redis backend when REDIS_URL is set so limits hold across multiple
instances and survive restarts (slowapi's default in-memory store does neither).
The key function reads X-Forwarded-For first, since behind Railway's proxy
request.client.host is the proxy, not the real client.
"""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def client_ip(request):
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


_redis_url = os.getenv("REDIS_URL")
if _redis_url:
    limiter = Limiter(key_func=client_ip, storage_uri=_redis_url)
else:
    print("WARNING: REDIS_URL not set — rate limiting is in-memory (per-instance, resets on restart).")
    limiter = Limiter(key_func=client_ip)
