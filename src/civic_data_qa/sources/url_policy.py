"""URL validation and SSRF protections for outbound HTTP."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_PRIVATE_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("100::/64"),
)


def _is_blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        return True
    if addr.is_multicast or addr.is_unspecified:
        return True
    return any(addr in net for net in _PRIVATE_NETWORKS)


def resolve_host_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve host '{hostname}': {exc}") from exc
    addrs: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        ip = info[4][0]
        addrs.append(ipaddress.ip_address(ip))
    if not addrs:
        raise ValueError(f"No addresses resolved for host '{hostname}'")
    return addrs


def validate_url(
    url: str,
    *,
    allow_http: bool = False,
    allowed_hosts: set[str] | None = None,
    resolve_dns: bool = True,
) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme or '(none)'}")
    if parsed.scheme == "http" and not allow_http:
        raise ValueError("HTTP URLs require explicit opt-in (allow_http=True)")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname")
    host = parsed.hostname.lower()
    if allowed_hosts is not None and host not in allowed_hosts:
        raise ValueError(f"Host '{host}' is not in the allowed host list")
    if resolve_dns:
        for addr in resolve_host_ips(parsed.hostname):
            if _is_blocked_ip(addr):
                raise ValueError(f"URL resolves to blocked address: {addr}")
    return url


def same_origin(url: str, origin: str) -> bool:
    a = urlparse(url)
    b = urlparse(origin)
    return a.scheme == b.scheme and a.netloc.lower() == b.netloc.lower()


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"
