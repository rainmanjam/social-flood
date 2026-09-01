"""
Outbound URL validation (SSRF defence).

Every place where this application fetches a URL supplied by a caller must run
it through :func:`validate_outbound_url` first. Two such sinks exist:

* ``google_news_api`` ``/article-details/?url=`` -- server-side article fetch.
* ``google_maps_service`` place lookup -- Playwright ``page.goto()``.

Both previously accepted any string, which made them a server-side request
forgery (SSRF) primitive: the caller chooses what the server connects to,
inside the container network, and gets the response body back.

Design
------
Defence is layered, because each layer alone is bypassable:

1. **Scheme + host allow-list.** Only ``https`` (``http`` opt-in) and only
   hosts the application actually has a reason to fetch. An allow-list is used
   rather than a private-IP deny-list because a deny-list must enumerate every
   internal range correctly, forever, and gets it wrong the first time someone
   adds IPv6 or a new cloud metadata address.

2. **DNS resolution check.** A host-name check alone is not enough: an
   attacker who controls ``evil.example.com`` can point it at ``127.0.0.1`` or
   at the cloud metadata address ``169.254.169.254``. Every address the host
   resolves to must be globally routable.

3. **IP pinning.** Between validation and the actual request, a hostile DNS
   server can change its answer from a public address to a private one (DNS
   rebinding). :func:`validate_outbound_url` therefore returns the addresses it
   validated so the caller can pin the connection to them.

Error handling
--------------
:class:`UrlNotAllowed` carries two messages: ``reason`` (detailed, for server
logs) and ``public_message`` (generic, for the HTTP response). Never put
``reason`` in a response body. Distinguishable failures -- "connection
refused" vs "timed out" vs "DNS failure" -- turn a blocked endpoint back into
an internal port-scan oracle, which is precisely how the News endpoint
behaved before this module existed.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Iterable, Sequence
from urllib.parse import urlsplit, urlunsplit

__all__ = [
    "UrlNotAllowed",
    "ValidatedUrl",
    "validate_outbound_url",
    "NEWS_ALLOWED_HOSTS",
    "MAPS_ALLOWED_HOSTS",
]


# Hosts each sink is allowed to reach. A leading dot means "this domain and any
# subdomain of it"; an entry without one must match the host exactly.
NEWS_ALLOWED_HOSTS: tuple[str, ...] = (
    "news.google.com",
    ".news.google.com",
)

MAPS_ALLOWED_HOSTS: tuple[str, ...] = (
    "www.google.com",
    "maps.google.com",
    "www.google.co.uk",
    "goo.gl",
    "maps.app.goo.gl",
)

# Ports we are willing to talk to. Anything else is almost always an attempt to
# reach an internal service (6379 redis, 5432 postgres, 9200 elasticsearch...).
_ALLOWED_PORTS: dict[str, int] = {"https": 443, "http": 80}

_GENERIC_MESSAGE = "The supplied URL is not permitted."


class UrlNotAllowed(ValueError):
    """Raised when a caller-supplied URL fails validation.

    Attributes:
        reason: Detailed cause. Safe to log server-side; never return to a
            caller -- the distinction between causes is itself an oracle.
        public_message: Generic message intended for the HTTP response body.
    """

    def __init__(self, reason: str, public_message: str = _GENERIC_MESSAGE) -> None:
        super().__init__(reason)
        self.reason = reason
        self.public_message = public_message


@dataclass(frozen=True)
class ValidatedUrl:
    """A URL that passed validation, plus the addresses it resolved to.

    Attributes:
        url: Normalised URL to request.
        host: Lower-cased host name.
        port: Resolved port number.
        ip_addresses: Every address ``host`` resolved to at validation time,
            all confirmed globally routable. Pin the connection to these to
            close the DNS-rebinding window.
    """

    url: str
    host: str
    port: int
    ip_addresses: tuple[str, ...]


def _host_allowed(host: str, allowed_hosts: Sequence[str]) -> bool:
    """Return True if ``host`` matches the allow-list.

    An entry beginning with ``.`` matches that domain's subdomains; any other
    entry must match exactly. Matching is done on the already-lower-cased host.
    """
    for entry in allowed_hosts:
        entry = entry.lower()
        if entry.startswith("."):
            # ".news.google.com" matches "a.news.google.com" but not
            # "evilnews.google.com" and not "news.google.com.attacker.tld".
            if host.endswith(entry):
                return True
        elif host == entry:
            return True
    return False


def _is_globally_routable(ip: str) -> bool:
    """Return True only for addresses safe to send an outbound request to.

    Rejects loopback, private (RFC 1918), link-local (which covers the cloud
    metadata address 169.254.169.254), multicast, reserved and unspecified
    ranges, for both IPv4 and IPv6. IPv4-mapped IPv6 addresses are unwrapped
    first, since ``::ffff:127.0.0.1`` is not otherwise flagged as loopback.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False

    # ::ffff:127.0.0.1 must be judged as 127.0.0.1, not as a global v6 address.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped

    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _resolve(host: str, port: int) -> tuple[str, ...]:
    """Resolve ``host`` to every address it maps to.

    Raises:
        UrlNotAllowed: if the name does not resolve.
    """
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        # Deliberately generic to the caller: a resolvable-vs-not distinction
        # leaks whether an internal name exists.
        raise UrlNotAllowed(f"DNS resolution failed for {host!r}: {exc}") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise UrlNotAllowed(f"{host!r} resolved to no addresses")
    return tuple(sorted(addresses))


def validate_outbound_url(
    raw_url: str,
    *,
    allowed_hosts: Iterable[str],
    allow_http: bool = False,
    resolve_dns: bool = True,
) -> ValidatedUrl:
    """Validate a caller-supplied URL before fetching it server-side.

    Args:
        raw_url: The untrusted URL.
        allowed_hosts: Hosts this sink may reach. Entries starting with ``.``
            match subdomains; others must match exactly.
        allow_http: Permit plaintext ``http://`` as well as ``https://``.
            Leave False unless the upstream genuinely does not serve TLS.
        resolve_dns: Perform the DNS-resolution and routability checks. Only
            set False in unit tests that must not touch the network.

    Returns:
        A :class:`ValidatedUrl`. Pin your connection to ``ip_addresses``.

    Raises:
        UrlNotAllowed: on any failure. Log ``.reason``; return
            ``.public_message``.
    """
    allowed = tuple(allowed_hosts)
    if not allowed:
        # An empty allow-list means "reach anything", which is the bug this
        # module exists to prevent. Fail closed and loudly.
        raise UrlNotAllowed("no allowed_hosts configured; refusing to fetch")

    if not isinstance(raw_url, str) or not raw_url.strip():
        raise UrlNotAllowed("URL is empty")

    candidate = raw_url.strip()
    try:
        parts = urlsplit(candidate)
    except ValueError as exc:
        raise UrlNotAllowed(f"URL is unparseable: {exc}") from exc

    scheme = parts.scheme.lower()
    permitted_schemes = ("https", "http") if allow_http else ("https",)
    if scheme not in permitted_schemes:
        # Blocks file://, gopher://, ftp://, dict://, and scheme-relative or
        # bare-path inputs that would otherwise be resolved against our own host.
        raise UrlNotAllowed(f"scheme {scheme!r} is not permitted")

    # `username:password@host` can be used to disguise the real host from
    # naive parsers and from humans reading logs.
    if parts.username or parts.password:
        raise UrlNotAllowed("credentials in URL are not permitted")

    try:
        host = parts.hostname
    except ValueError as exc:
        raise UrlNotAllowed(f"URL has an invalid host: {exc}") from exc

    if not host:
        raise UrlNotAllowed("URL has no host")
    host = host.lower().rstrip(".")  # trailing dot: "google.com." == "google.com"

    # A literal IP can never be on a host allow-list, but reject it explicitly
    # so the failure reason in the logs is accurate.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise UrlNotAllowed("literal IP addresses are not permitted")

    if not _host_allowed(host, allowed):
        raise UrlNotAllowed(f"host {host!r} is not on the allow-list")

    try:
        port = parts.port
    except ValueError as exc:
        raise UrlNotAllowed(f"URL has an invalid port: {exc}") from exc
    if port is None:
        port = _ALLOWED_PORTS[scheme]
    elif port != _ALLOWED_PORTS[scheme]:
        raise UrlNotAllowed(f"port {port} is not permitted for scheme {scheme!r}")

    ip_addresses: tuple[str, ...] = ()
    if resolve_dns:
        ip_addresses = _resolve(host, port)
        bad = [ip for ip in ip_addresses if not _is_globally_routable(ip)]
        if bad:
            # An allow-listed name pointing at a private address means either a
            # hijacked record or split-horizon DNS. Either way, do not connect.
            raise UrlNotAllowed(
                f"host {host!r} resolves to non-routable address(es): {', '.join(bad)}"
            )

    normalised = urlunsplit((scheme, parts.netloc.lower(), parts.path, parts.query, ""))
    return ValidatedUrl(
        url=normalised, host=host, port=port, ip_addresses=ip_addresses
    )
