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
    if ENABLE_PROXY:
        if _proxy_iter is not None:
            async with _proxy_lock:
                # Since _proxy_iter is not None, PROXY_LIST was not empty, so next() is safe.
                proxy_url = next(_proxy_iter)
            logger.debug(f"Selected proxy: {proxy_url}")
            return proxy_url
        else:
            # ENABLE_PROXY is true, but _proxy_iter is None (meaning PROXY_LIST was empty)
            logger.warning("Proxying is enabled, but no valid proxy URLs were found in PROXY_URLS or the list is empty.")
            return None
    return None


def get_proxy_sync():
    """
    Synchronous version of get_proxy.
    Returns a single proxy URL string, or None if proxying is disabled or no valid URLs exist.

    Note: This version does not use locking and should only be used in synchronous contexts
    where thread-safety is handled externally or not required.
    """
    if ENABLE_PROXY:
        if PROXY_LIST:
            # Return first proxy for sync contexts (no round-robin to avoid race conditions)
            proxy_url = PROXY_LIST[0]
            logger.debug(f"Selected proxy (sync): {proxy_url}")
            return proxy_url
        else:
            logger.warning("Proxying is enabled, but no valid proxy URLs were found in PROXY_URLS or the list is empty.")
            return None
    return None


def rotate_proxy():
    """
    Rotate to the next proxy in the list.
    Returns the next proxy URL string, or None if proxying is disabled or no valid URLs exist.

    This is a synchronous function used to get a different proxy when the current one fails.
    """
    if ENABLE_PROXY:
        if _proxy_iter is not None and PROXY_LIST:
            # Advance to next proxy in the cycle
            proxy_url = next(_proxy_iter)
            logger.debug(f"Rotated to proxy: {proxy_url}")
            return proxy_url
        else:
            logger.warning("Proxying is enabled, but no valid proxy URLs were found in PROXY_URLS or the list is empty.")
            return None
    return None
