"""Host lookups: IPv4 first.

Docker Desktop on some networks: the local DNS answers the IPv6 (AAAA) query for api.edenai.run, an
IPv4-only host, with "no such domain" instead of "no IPv6 address". Docker's resolver keeps that answer for
a few seconds, and in that time the IPv4 lookup fails too: "[Errno -5] No address associated with
hostname", so forms sent at once failed with LLM_UNAVAILABLE. httpx resolves with the combined lookup
(IPv4 + IPv6), which sends the AAAA query every time. Measured 2026-11-22 in the api container: combined
lookups failed most of the time, IPv4-first lookups 30/30 one by one and 24/24 eight at once.

So a combined lookup asks for IPv4 first and makes the combined one only when there is no IPv4 address
(an IPv6-only host still works). The API connects to Eden AI and Ollama only, both reachable over IPv4."""

import socket
from collections.abc import Callable

type Lookup = Callable[..., list]


def ipv4_first(getaddrinfo: Lookup) -> Lookup:
    def lookup(host, port, family=0, type=0, proto=0, flags=0):
        if family == socket.AF_UNSPEC:
            try:
                return getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            except socket.gaierror:
                pass
        return getaddrinfo(host, port, family, type, proto, flags)

    lookup.wrapped = getaddrinfo  # type: ignore[attr-defined]
    return lookup


def install() -> None:
    """Process-wide (httpx has no setting for the address family). Safe to call twice."""
    if not hasattr(socket.getaddrinfo, "wrapped"):
        socket.getaddrinfo = ipv4_first(socket.getaddrinfo)
