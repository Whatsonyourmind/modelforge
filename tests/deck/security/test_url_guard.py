"""Tests for the SSRF URL guard — pre-fetch validation + connected-IP re-check.

No network: DNS is monkeypatched and the httpx response hook is exercised
with duck-typed fakes (the hook only touches ``response.extensions``).
"""

from __future__ import annotations

import socket

import pytest

from modelforge.deck.security.url_guard import (
    UnsafeURLError,
    assert_connected_ip_public,
    validate_public_url,
)


def _fake_getaddrinfo(*ips):
    def fake(host, port, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))
            for ip in ips
        ]

    return fake


class TestValidatePublicUrl:
    def test_rejects_disallowed_scheme(self):
        with pytest.raises(UnsafeURLError, match="scheme"):
            validate_public_url("file:///etc/passwd")

    def test_rejects_missing_host(self):
        with pytest.raises(UnsafeURLError, match="no host"):
            validate_public_url("http://")

    def test_rejects_private_resolution(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("10.0.0.5"))
        with pytest.raises(UnsafeURLError, match="non-public"):
            validate_public_url("http://internal.example.com/x.png")

    def test_rejects_metadata_endpoint(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("169.254.169.254"))
        with pytest.raises(UnsafeURLError, match="non-public"):
            validate_public_url("http://metadata.example.com/latest")

    def test_rejects_if_any_address_private(self, monkeypatch):
        # Multi-A-record poisoning: one public + one private => reject.
        monkeypatch.setattr(
            socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34", "127.0.0.1")
        )
        with pytest.raises(UnsafeURLError, match="non-public"):
            validate_public_url("https://rebind.example.com/img.png")

    def test_accepts_public_host(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
        url = "https://example.com/img.png"
        assert validate_public_url(url) == url


class _FakeStream:
    def __init__(self, server_addr):
        self._server_addr = server_addr

    def get_extra_info(self, name):
        if name == "server_addr":
            return self._server_addr
        return None


class _FakeResponse:
    def __init__(self, server_addr=None, with_stream=True):
        self.extensions = (
            {"network_stream": _FakeStream(server_addr)} if with_stream else {}
        )


class TestAssertConnectedIpPublic:
    """The DNS-rebinding TOCTOU hook: re-validate the ACTUAL connected IP."""

    def test_public_peer_passes(self):
        assert_connected_ip_public(_FakeResponse(("93.184.216.34", 443)))

    def test_private_peer_rejected(self):
        with pytest.raises(UnsafeURLError, match="rebinding"):
            assert_connected_ip_public(_FakeResponse(("10.0.0.5", 80)))

    def test_loopback_peer_rejected(self):
        with pytest.raises(UnsafeURLError, match="rebinding"):
            assert_connected_ip_public(_FakeResponse(("127.0.0.1", 80)))

    def test_metadata_peer_rejected(self):
        with pytest.raises(UnsafeURLError, match="rebinding"):
            assert_connected_ip_public(_FakeResponse(("169.254.169.254", 80)))

    def test_ipv6_loopback_rejected(self):
        with pytest.raises(UnsafeURLError, match="rebinding"):
            assert_connected_ip_public(_FakeResponse(("::1", 80, 0, 0)))

    def test_missing_stream_is_noop(self):
        # Mock transports / proxies don't expose the peer: pre-fetch
        # validation stands, hook must not break the request.
        assert_connected_ip_public(_FakeResponse(with_stream=False))

    def test_missing_server_addr_is_noop(self):
        assert_connected_ip_public(_FakeResponse(server_addr=None))

    def test_unparseable_address_rejected(self):
        with pytest.raises(UnsafeURLError, match="unparseable"):
            assert_connected_ip_public(_FakeResponse(("not-an-ip", 80)))
