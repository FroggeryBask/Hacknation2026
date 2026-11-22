import socket

import pytest

from autoformularz import net

V4 = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("13.39.88.122", 443))]
V6 = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 443, 0, 0))]


def fake(answers: dict[int, list]):
    """getaddrinfo that knows only the given families; records which were asked."""
    asked: list[int] = []

    def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        asked.append(family)
        if family in answers:
            return answers[family]
        raise socket.gaierror(-5, "No address associated with hostname")

    return getaddrinfo, asked


def test_combined_lookup_asks_ipv4_only():
    """An IPv4-only host (api.edenai.run): no IPv6 query, which Docker Desktop's DNS turns into a failure."""
    lookup, asked = fake({socket.AF_INET: V4})
    assert net.ipv4_first(lookup)("api.edenai.run", 443, 0, socket.SOCK_STREAM) == V4
    assert asked == [socket.AF_INET]


def test_ipv6_only_host_still_resolves():
    lookup, asked = fake({socket.AF_UNSPEC: V6})
    assert net.ipv4_first(lookup)("v6.example", 443) == V6
    assert asked == [socket.AF_INET, socket.AF_UNSPEC]


def test_explicit_family_is_kept():
    lookup, asked = fake({socket.AF_INET6: V6})
    assert net.ipv4_first(lookup)("v6.example", 443, socket.AF_INET6) == V6
    assert asked == [socket.AF_INET6]


def test_unknown_host_still_fails():
    lookup, _ = fake({})
    with pytest.raises(socket.gaierror):
        net.ipv4_first(lookup)("nope.invalid", 443)


def test_install_wraps_once(monkeypatch):
    lookup, _ = fake({socket.AF_INET: V4})
    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    net.install()
    net.install()
    assert socket.getaddrinfo.wrapped is lookup
