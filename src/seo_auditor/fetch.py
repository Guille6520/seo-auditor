"""Descarga de páginas: redirecciones manuales, límite de tamaño y tiempos."""

import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

import requests

from .safety import UnsafeURL, check_url

USER_AGENT = "seo-auditor/0.2"
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 5
# Tipos cuyo cuerpo no interesa descargar (salvo que se pida con force_body).
BINARY_TYPES = ("image/", "video/", "audio/", "font/", "application/pdf", "application/zip")
CHARSET_RE = re.compile(r"charset=\s*[\"']?([\w.:-]+)", re.IGNORECASE)


@dataclass
class Response:
    """Resultado de pedir una URL: estado, cabeceras, cuerpo y cadena de redirecciones."""

    requested: str
    url: str  # URL final tras redirecciones
    status: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    raw: bytes = b""  # cuerpo sin decodificar (hace falta para sitemaps comprimidos)
    chain: list[tuple[str, int]] = field(default_factory=list)  # (url, estado) de cada salto
    elapsed: float = 0.0
    error: str | None = None

    @property
    def is_html(self) -> bool:
        content_type = self.headers.get("content-type", "").lower()
        if content_type:
            return "html" in content_type
        # Sin Content-Type: se mira el principio del cuerpo.
        start = self.body.lstrip()[:300].lower()
        return start.startswith(("<!doctype html", "<html")) or "<html" in start

    @property
    def redirects(self) -> int:
        return len(self.chain)


def new_session() -> requests.Session:
    """Sesión HTTP que reutiliza conexiones y se identifica con el User-Agent del auditor."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def decode_body(raw: bytes, content_type: str) -> str:
    """Decodifica el cuerpo: charset de la cabecera si es válido; si no, UTF-8 y, en último caso, cp1252."""
    match = CHARSET_RE.search(content_type)
    if match:
        try:
            return raw.decode(match.group(1), errors="replace")
        except LookupError:
            pass  # charset desconocido: se intenta como si no viniera
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def fetch(
    url: str,
    session: requests.Session,
    *,
    allow_private: bool = False,
    timeout: float = 15.0,
    max_bytes: int = MAX_BYTES,
    force_body: bool = False,
) -> Response:
    """Pide una URL siguiendo redirecciones a mano para validar cada salto. Nunca lanza."""
    result = Response(requested=url, url=url)
    current = url
    started = time.monotonic()
    deadline = started + timeout * 4  # tope total, por si el servidor envía el cuerpo a cuentagotas
    try:
        for _ in range(MAX_REDIRECTS + 1):
            check_url(current, allow_private)
            resp = session.get(current, allow_redirects=False, stream=True, timeout=timeout)
            try:
                location = resp.headers.get("Location")
                if resp.status_code in (301, 302, 303, 307, 308) and location:
                    result.chain.append((current, resp.status_code))
                    current = urljoin(current, location)
                    continue
                result.url = current
                result.status = resp.status_code
                result.headers = {k.lower(): v for k, v in resp.headers.items()}
                content_type = result.headers.get("content-type", "").lower()
                if force_body or not content_type.startswith(BINARY_TYPES):
                    raw = b""
                    for chunk in resp.iter_content(chunk_size=65536):
                        raw += chunk
                        if len(raw) >= max_bytes or time.monotonic() > deadline:
                            raw = raw[:max_bytes]
                            break
                    result.raw = raw
                    result.body = decode_body(raw, content_type)
                break
            finally:
                resp.close()
        else:
            result.error = f"Más de {MAX_REDIRECTS} redirecciones"
            result.url = current
    except UnsafeURL as exc:
        result.error = f"URL bloqueada: {exc}"
        result.url = current
    except (requests.RequestException, ValueError, LookupError, UnicodeError) as exc:
        # ValueError y UnicodeError: URLs o cabeceras Location mal formadas.
        result.error = f"{type(exc).__name__}: {exc}"
        result.url = current
    result.elapsed = time.monotonic() - started
    return result
