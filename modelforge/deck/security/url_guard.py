"""SSRF guard: validate an outbound URL targets a public host before fetching.

Used by any code path that fetches a caller-supplied URL (image rendering,
webhooks). Blocks server-side request forgery to cloud metadata
(169.254.169.254), loopback, private ranges, link-local and reserved space.

TOCTOU note (DNS rebinding): ``validate_public_url`` resolves the hostname
once at validation time, but the HTTP client re-resolves at connect time —
an attacker-controlled DNS server can answer with a public address first
and a private one second. ``assert_connected_ip_public`` closes that window:
install it as an httpx ``response`` event hook and it re-validates the
address the socket ACTUALLY connected to (via the ``network_stream``
extension) before any response body is read. If the transport does not
expose the peer address (mock transports, proxies), the hook is a no-op —
it is defense-in-depth on top of the mandatory pre-fetch validation. This
path is unreachable from the certified deck pipeline (facts come from the
workbook, not URLs); it guards the generic IR image renderer.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}


class UnsafeURLError(ValueError):
    """Raised when a URL is rejected as unsafe (disallowed scheme or non-public host)."""


def _is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local  # 169.254.0.0/16 (cloud metadata) + fe80::/10
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def validate_public_url(url: str) -> str:
    """Return ``url`` if it targets a public host over http(s); else raise UnsafeURLError.

    Resolves the hostname and rejects the URL if ANY resolved address is
    non-public. Callers should also disable redirect-following so a public URL
    cannot bounce to an internal one.
    """
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"scheme not allowed: {parsed.scheme!r}")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")

    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"DNS resolution failed for host {host!r}") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise UnsafeURLError(f"no addresses resolved for host {host!r}")

    for ip in addresses:
        if not _is_public_ip(ip):
            raise UnsafeURLError(f"host {host!r} resolves to non-public address {ip}")

    return url


def assert_connected_ip_public(response) -> None:
    """httpx ``response`` event hook: re-validate the ACTUAL connected peer IP.

    Closes the validate-then-fetch DNS-rebinding TOCTOU: even if the
    hostname re-resolved to a private address between ``validate_public_url``
    and the connect, the response is rejected before its body is read.

    Usage::

        httpx.Client(event_hooks={"response": [assert_connected_ip_public]})

    Duck-typed on ``response.extensions["network_stream"]`` (httpx/httpcore);
    silently passes when the transport does not expose the peer address.
    """
    stream = getattr(response, "extensions", {}).get("network_stream")
    if stream is None:
        return  # mock transport / proxy: peer unknown, pre-fetch check stands
    try:
        server_addr = stream.get_extra_info("server_addr")
    except Exception:
        return
    if not server_addr:
        return
    ip = server_addr[0]
    try:
        if not _is_public_ip(ip):
            raise UnsafeURLError(
                f"connection landed on non-public address {ip} "
                "(possible DNS rebinding); response rejected"
            )
    except ValueError as exc:
        if isinstance(exc, UnsafeURLError):
            raise
        raise UnsafeURLError(f"unparseable connected address {ip!r}") from exc


__all__ = ["validate_public_url", "assert_connected_ip_public", "UnsafeURLError"]
