"""Protección SSRF: solo se permite rastrear direcciones públicas.

Limitación conocida: se resuelve el DNS antes de pedir la URL, así que un
atacante con control del DNS podría cambiar la respuesta entre la comprobación
y la conexión (DNS rebinding). Para un uso como servicio público habría que
fijar la IP resuelta en la conexión.
"""

import ipaddress
import socket
from urllib.parse import urlparse

# Rangos IPv6 que encapsulan una IPv4 (NAT64 y 6to4): podrían llevar a una IP privada.
_TUNNELS = (ipaddress.ip_network("64:ff9b::/96"), ipaddress.ip_network("2002::/16"))


class UnsafeURL(ValueError):
    """La URL apunta a un destino que no se debe rastrear."""


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True si la IP es enrutable en Internet y no es un túnel hacia IPv4."""
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif any(ip in net for net in _TUNNELS):
            return False
    return ip.is_global and not ip.is_multicast


def check_url(url: str, allow_private: bool = False) -> None:
    """Lanza UnsafeURL si la URL no es http(s), es ambigua o resuelve a una IP no pública."""
    # Caracteres que distintas librerías interpretan de forma distinta: con "\@" el
    # analizador de la librería estándar y el de requests no coinciden en cuál es el host.
    if "\\" in url or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in url):
        raise UnsafeURL("La URL contiene barras invertidas, espacios o caracteres de control")
    try:
        parts = urlparse(url)
        host, port = parts.hostname, parts.port
    except ValueError as exc:
        raise UnsafeURL(f"URL mal formada: {exc}") from exc
    if parts.scheme not in ("http", "https"):
        raise UnsafeURL(f"Esquema no permitido: {parts.scheme or '(vacío)'}")
    if not host:
        raise UnsafeURL("La URL no tiene host")
    if "@" in parts.netloc:
        raise UnsafeURL("No se admiten URLs con usuario o contraseña")
    if allow_private:
        return
    port = port or (443 if parts.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError) as exc:
        raise UnsafeURL(f"No se pudo resolver {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not _is_public(ip):
            raise UnsafeURL(f"{host} resuelve a una dirección no pública ({ip})")
