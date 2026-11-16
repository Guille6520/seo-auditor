"""Extracción de datos SEO de una página HTML."""

import json
import re
from dataclasses import dataclass, field
from urllib.parse import quote, urldefrag, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

WORD_RE = re.compile(r"\w+", re.UNICODE)
ROBOTS_META_NAMES = ("robots", "googlebot")


def _clean(text: str) -> str:
    """Colapsa espacios y saltos de línea repetidos en un solo espacio."""
    return " ".join(text.split())


def normalize_url(url: str) -> str:
    """Forma canónica de una URL para poder compararla. Lanza ValueError si está mal formada.

    Minúsculas en esquema y host (dominios con tildes en su forma ASCII), sin fragmento
    ni puerto por defecto, ruta vacía = '/', y caracteres no ASCII codificados con %.
    """
    url, _ = urldefrag(url.strip())
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass  # host raro: se deja tal cual
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    port = parts.port
    if port and not ((parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    # quote solo codifica lo que no es ASCII seguro; los %XX ya existentes se respetan.
    path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=~-._")
    query = quote(parts.query, safe="/%:@!$&'()*+,;=~-._?")
    return urlunsplit((parts.scheme.lower(), host, path, query, ""))


def site_key(url: str) -> str:
    """Clave de sitio: host sin 'www.' y con puerto si no es el de por defecto."""
    host = urlsplit(normalize_url(url)).netloc
    return host.removeprefix("www.")


@dataclass
class PageData:
    """Datos SEO extraídos de una página HTML."""

    title: str | None = None
    meta_description: str | None = None
    h1s: list[str] = field(default_factory=list)
    canonical: str | None = None
    meta_robots: str = ""
    lang: str | None = None
    viewport: bool = False
    images_total: int = 0
    images_missing_alt: list[str] = field(default_factory=list)
    word_count: int = 0
    jsonld_total: int = 0
    jsonld_invalid: int = 0
    links: list[str] = field(default_factory=list)  # URLs absolutas normalizadas, http(s)


def _is_canonical(rel) -> bool:
    """True si el atributo rel (texto o lista, en cualquier combinación de mayúsculas) incluye canonical."""
    values = rel if isinstance(rel, list) else [rel or ""]
    return any(v.lower() == "canonical" for v in values)


def parse_html(html: str, base_url: str) -> PageData:
    """Analiza el HTML y devuelve sus datos SEO. base_url sirve para resolver enlaces relativos."""
    soup = BeautifulSoup(html, "lxml")
    data = PageData()

    # Solo cuenta el <title> de <head>: un <svg><title> del cuerpo no es el título de la página.
    title_tag = soup.head.find("title") if soup.head else None
    if title_tag:
        data.title = _clean(title_tag.get_text(" ")) or None

    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        content = meta.get("content") or ""
        if name == "description" and data.meta_description is None:
            data.meta_description = _clean(content)
        elif name in ROBOTS_META_NAMES:
            data.meta_robots = f"{data.meta_robots},{content}".strip(",").lower()
        elif name == "viewport":
            data.viewport = True

    data.h1s = [_clean(h.get_text(" ")) for h in soup.find_all("h1")]

    # <base href> cambia la base contra la que se resuelven los enlaces relativos.
    base_tag = soup.find("base", href=True)
    if base_tag:
        try:
            base_url = urljoin(base_url, base_tag["href"].strip())
        except ValueError:
            pass

    canonical = soup.find("link", rel=_is_canonical)
    if canonical and canonical.get("href"):
        try:
            data.canonical = normalize_url(urljoin(base_url, canonical["href"].strip()))
        except ValueError:
            pass  # canonical mal formado: se trata como ausente

    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        data.lang = html_tag["lang"].strip()

    for img in soup.find_all("img"):
        data.images_total += 1
        if img.get("alt") is None:
            data.images_missing_alt.append(img.get("src") or "(sin src)")

    for script in soup.find_all("script", type=lambda v: v and v.lower() == "application/ld+json"):
        data.jsonld_total += 1
        try:
            json.loads(script.string or script.get_text() or "")
        except (ValueError, TypeError):
            data.jsonld_invalid += 1

    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        try:
            absolute = urljoin(base_url, href)
            if urlsplit(absolute).scheme not in ("http", "https"):
                continue
            norm = normalize_url(absolute)
        except ValueError:
            continue  # enlace mal escrito: no debe tumbar el análisis de la página
        if norm not in seen:
            seen.add(norm)
            data.links.append(norm)

    # El recuento de palabras va el último porque elimina nodos del árbol.
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    body = soup.body or soup
    data.word_count = len(WORD_RE.findall(body.get_text(" ", strip=True)))
    return data
