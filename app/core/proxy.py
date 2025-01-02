# app/core/proxy.py

import os
import re
import itertools
import asyncio
import logging

logger = logging.getLogger("uvicorn")

PROXY_URLS = os.getenv('PROXY_URLS', '')
ENABLE_PROXY = os.getenv('ENABLE_PROXY', 'false').lower() == 'true'

def is_valid_url(url):
    return re.match(r'^(http|https):\/\/[^\s\/$.?#].[^\s]*$', url) is not None

# Parse the PROXY_URLS into a list
PROXY_LIST = [url.strip() for url in PROXY_URLS.split(',') if is_valid_url(url.strip())]

# Use an asyncio.Lock for async thread safety
_proxy_lock = asyncio.Lock()

def get_available_proxies():
    return PROXY_LIST

AVAILABLE_PROXIES = get_available_proxies()

_proxy_iter = itertools.cycle(AVAILABLE_PROXIES) if AVAILABLE_PROXIES else None

async def get_proxy():
    """
    Returns a single proxy URL string, or None if proxying is disabled or no valid URLs exist.
    Example return: 'http://localhost:8030'
    """
    if ENABLE_PROXY and PROXY_LIST:
        async with _proxy_lock:
            proxy_url = next(_proxy_iter)
        logger.debug(f"Selected proxy: {proxy_url}")
        return proxy_url
    return None
