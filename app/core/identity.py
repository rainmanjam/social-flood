"""
Keyed digests for secrets that become storage keys.

Two subsystems turn a caller's API key into an identifier that is written to
Redis and to logs: the rate limiter (bucket keys) and the record store (owner
partitions). Neither may store the raw key.

Both previously used a bare ``sha256(api_key)``. That is weak for this input:
API keys are short and often human-chosen, so an attacker holding a leaked
Redis dump can recover them by hashing a wordlist. There is no salt and no
secret, so the whole attack precomputes.

The fix is a *keyed* digest, not a slow one. A password KDF (bcrypt, scrypt,
argon2) is the usual answer for password hashing, but it is the wrong tool
here: the rate limiter calls this on **every request**, so a deliberately slow
function would be a self-inflicted denial of service. HMAC-SHA256 under a
secret the attacker does not have is both fast and not precomputable, which is
exactly the property needed.

If ``SECRET_KEY`` is unset, this falls back to a **process-random** salt rather
than to an unkeyed digest, so there is never a brute-forceable path. The
trade-off is that identifiers are then not stable across restarts. That is
acceptable because it only arises in development: the application refuses to
start in production on a missing or default ``SECRET_KEY``.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import threading

logger = logging.getLogger(__name__)

__all__ = ["keyed_digest"]

# Used only when SECRET_KEY is unavailable. Random per process, so a digest
# cannot be precomputed from a wordlist even in that degraded mode.
_FALLBACK_SALT = secrets.token_bytes(32)
_warned = False
_warn_lock = threading.Lock()


def _secret() -> bytes:
    """Return the application secret, or an empty value if unavailable."""
    try:  # Lazy: config construction can fail at import time.
        from app.core.config import get_settings

        return (get_settings().SECRET_KEY or "").encode()
    except Exception:  # pragma: no cover - defensive
        return b""


def keyed_digest(value: str, *, length: int = 32) -> str:
    """Return a non-reversible, non-precomputable digest of ``value``.

    Args:
        value: The secret to digest, e.g. a raw API key. Never stored.
        length: Hex characters to return. The default 32 is 128 bits, far
            beyond collision range for an identifier namespace.

    Returns:
        A hex digest safe to use as a Redis key component or a log field.
    """
    global _warned

    key = _secret()
    if not key:
        key = _FALLBACK_SALT
        if not _warned:
            with _warn_lock:
                if not _warned:
                    _warned = True
                    logger.warning(
                        "SECRET_KEY is not configured; identity digests use a "
                        "process-random salt and will not be stable across "
                        "restarts. Configure SECRET_KEY for stable identifiers."
                    )

    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()[:length]
