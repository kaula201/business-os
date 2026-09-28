"""Block SSRF targets: private, loopback, link-local, and cloud metadata addresses."""
import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import settings

# Hostnames that must never be fetched, even if DNS is down or attacker-controlled.
_BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata.google.com",
    "metadata",
    "instance-data",
    "localhost",
}

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
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
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]

_LOOPBACK_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
]


class UnsafeWebhookURL(ValueError):
    """Raised when a webhook URL is not an acceptable public HTTP(S) target."""


def _allow_loopback() -> bool:
    # Tests and local dev deliver to 127.0.0.1. Production does not.
    return settings.is_relaxed_env()


def _allowlist() -> set[str]:
    return {part.strip().lower() for part in (settings.WEBHOOK_URL_ALLOWLIST or "").split(",") if part.strip()}


def _blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    allow_loopback = _allow_loopback()
    for network in _BLOCKED_NETWORKS:
        if ip in network:
            if allow_loopback and any(ip in loop for loop in _LOOPBACK_NETWORKS):
                return False
            return True
    return False


def _iter_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        return [literal]
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeWebhookURL("Webhook ჰოსტი ვერ მოიძებნა") from exc
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        addr = info[4][0].split("%", 1)[0]
        ips.append(ipaddress.ip_address(addr))
    if not ips:
        raise UnsafeWebhookURL("Webhook ჰოსტი ვერ მოიძებნა")
    return ips


def assert_public_webhook_url(url: str) -> str:
    """Return the URL if it is safe to request. Raise UnsafeWebhookURL otherwise."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeWebhookURL("Webhook URL უნდა იყოს http ან https")
    if parsed.username or parsed.password:
        raise UnsafeWebhookURL("Webhook URL-ში ავტორიზაციის მონაცემები დაუშვებელია")
    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTS and not (host == "localhost" and _allow_loopback()):
        raise UnsafeWebhookURL("Webhook URL მიუთითებს დახურულ ან metadata მისამართზე")
    allowlist = _allowlist()
    if allowlist and host not in allowlist:
        raise UnsafeWebhookURL("Webhook ჰოსტი allowlist-ში არ არის")
    for ip in _iter_ips(host):
        if _blocked(ip):
            raise UnsafeWebhookURL("Webhook URL მიუთითებს კერძო, link-local ან metadata მისამართზე")
    return url
