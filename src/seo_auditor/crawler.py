"""Rastreo del sitio: robots.txt, sitemap, BFS con límites de páginas y profundidad."""

import time
import zlib
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import requests
from lxml import etree

from .fetch import MAX_BYTES, Response, fetch, new_session
from .parser import PageData, normalize_url, parse_html, site_key
from .robots import Robots

SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".pdf", ".zip", ".gz", ".mp4",
    ".mp3", ".css", ".js", ".woff", ".woff2", ".ttf", ".xml", ".json", ".txt",
)
MAX_SITEMAP_URLS = 5000
MAX_CHILD_SITEMAPS = 5
ROBOT_AGENT = "seo-auditor"


@dataclass
class Page:
    """Una URL rastreada: cómo se descubrió, su respuesta y, si es HTML del sitio, sus datos."""

    requested: str
    depth: int
    source: str  # "enlace" | "sitemap"
    fetch: Response
    data: PageData | None = None


@dataclass
class CrawlResult:
    """Todo lo observado en un rastreo; es la única entrada de las comprobaciones."""

    start_url: str
    final_start_url: str
    pages: dict[str, Page] = field(default_factory=dict)
    inlinks: dict[str, set[str]] = field(default_factory=dict)  # destino -> orígenes
    robots_status: int | None = None
    robots_text: str = ""
    sitemap_found: bool = False
    sitemap_urls: list[str] = field(default_factory=list)
    llms_txt_found: bool = False
    truncated: bool = False  # quedaron páginas sin visitar (límite de páginas o de profundidad)
    blocked_by_robots: list[str] = field(default_factory=list)


def _skip(url: str) -> bool:
    """True si la URL parece un recurso (imagen, PDF, CSS...) y no una página."""
    return urlsplit(url).path.lower().endswith(SKIP_EXTENSIONS)


def _parse_sitemap(raw: bytes) -> tuple[bool, list[str], list[str]]:
    """Devuelve (es_sitemap, urls, sitemaps_hijos). Sin entidades externas ni red."""
    if raw[:2] == b"\x1f\x8b":  # sitemap comprimido con gzip; se descomprime con tope de tamaño
        try:
            raw = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw, MAX_BYTES * 5)
        except zlib.error:
            return False, [], []
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    try:
        root = etree.fromstring(raw, parser)
    except (etree.XMLSyntaxError, ValueError):
        return False, [], []
    if root is None or not isinstance(root.tag, str):
        return False, [], []
    kind = etree.QName(root).localname
    if kind not in ("urlset", "sitemapindex"):
        return False, [], []  # p. ej. una página HTML de error servida con 200
    # Solo <loc> hijos directos de <url> o <sitemap>: <image:loc> y similares no son páginas.
    locs = [
        (el.text or "").strip()
        for el in root.iter()
        if isinstance(el.tag, str) and etree.QName(el).localname == "loc"
        and el.getparent() is not None and isinstance(el.getparent().tag, str)
        and etree.QName(el.getparent()).localname in ("url", "sitemap")
    ]
    return (True, [], locs) if kind == "sitemapindex" else (True, locs, [])


def _load_sitemap(origin: str, robots: Robots, session, allow_private: bool) -> tuple[bool, list[str]]:
    """Descarga el sitemap (el de robots.txt o /sitemap.xml). Devuelve (encontrado, urls)."""
    candidates = robots.sitemaps or [f"{origin}/sitemap.xml"]
    found = False
    urls: list[str] = []
    queue = deque(candidates[:MAX_CHILD_SITEMAPS])
    fetched = 0
    while queue and fetched < MAX_CHILD_SITEMAPS + 1 and len(urls) < MAX_SITEMAP_URLS:
        sm = fetch(queue.popleft(), session, allow_private=allow_private, force_body=True)
        fetched += 1
        if sm.status != 200 or not sm.raw:
            continue
        valid, page_urls, children = _parse_sitemap(sm.raw)
        if not valid:
            continue
        found = True
        urls.extend(page_urls)
        queue.extend(children[:MAX_CHILD_SITEMAPS])
    normalized = []
    for url in urls[:MAX_SITEMAP_URLS]:
        try:
            normalized.append(normalize_url(url))
        except ValueError:
            continue  # <loc> mal formado
    return found, normalized


def crawl(
    start_url: str,
    *,
    max_pages: int = 50,
    max_depth: int = 3,
    delay: float = 0.2,
    allow_private: bool = False,
    session: requests.Session | None = None,
) -> CrawlResult:
    """Rastrea el sitio de start_url hasta max_pages páginas y max_depth niveles de profundidad."""
    session = session or new_session()
    try:
        start = normalize_url(start_url)
    except ValueError as exc:
        raise RuntimeError(f"URL no válida: {start_url} ({exc})") from exc
    first = fetch(start, session, allow_private=allow_private)
    if first.status is None:
        raise RuntimeError(f"No se pudo acceder a {start}: {first.error}")
    result = CrawlResult(start_url=start, final_start_url=normalize_url(first.url))

    scope = site_key(result.final_start_url)
    parts = urlsplit(result.final_start_url)
    origin = f"{parts.scheme}://{parts.netloc}"

    # force_body: robots.txt y sitemaps se leen aunque el servidor declare un tipo raro.
    robots_resp = fetch(f"{origin}/robots.txt", session, allow_private=allow_private, force_body=True)
    result.robots_status = robots_resp.status
    if robots_resp.status == 200 and not robots_resp.is_html:
        result.robots_text = robots_resp.body
    robots = Robots(result.robots_text)

    result.sitemap_found, result.sitemap_urls = _load_sitemap(origin, robots, session, allow_private)
    result.llms_txt_found = fetch(f"{origin}/llms.txt", session, allow_private=allow_private).status == 200

    def register(url: str, depth: int, source: str, response: Response | None = None) -> Page:
        resp = response or fetch(url, session, allow_private=allow_private)
        page = Page(requested=url, depth=depth, source=source, fetch=resp)
        final = normalize_url(resp.url) if resp.status is not None else url
        # Si la URL redirige a otro dominio, esa página no es del sitio y no se analiza.
        if resp.status == 200 and resp.is_html and site_key(final) == scope:
            page.data = parse_html(resp.body, resp.url)
            for link in page.data.links:
                if site_key(link) == scope:
                    result.inlinks.setdefault(link, set()).add(final)
        result.pages[url] = page
        return page

    def internal_links(page: Page) -> list[str]:
        return [link for link in page.data.links if site_key(link) == scope and not _skip(link)]

    queue: deque[tuple[str, int]] = deque()
    seen = {start}
    home = register(start, 0, "enlace", first)
    if home.data:
        for link in internal_links(home):
            if link not in seen:
                seen.add(link)
                queue.append((link, 1))

    depth_limited = False
    while queue and len(result.pages) < max_pages:
        url, depth = queue.popleft()
        if not robots.can_fetch(ROBOT_AGENT, url):
            result.blocked_by_robots.append(url)
            continue
        if delay:
            time.sleep(delay)
        page = register(url, depth, "enlace")
        if not page.data:
            continue
        new_links = [link for link in internal_links(page) if link not in seen]
        if depth < max_depth:
            for link in new_links:
                seen.add(link)
                queue.append((link, depth + 1))
        elif new_links:
            depth_limited = True  # hay páginas más profundas que no se van a visitar
    result.truncated = bool(queue) or depth_limited

    for url in result.sitemap_urls:
        if site_key(url) != scope or url in result.pages or _skip(url):
            continue
        if len(result.pages) >= max_pages:
            result.truncated = True
            break
        if not robots.can_fetch(ROBOT_AGENT, url):
            result.blocked_by_robots.append(url)
            continue
        if delay:
            time.sleep(delay)
        register(url, max_depth + 1, "sitemap")
    return result
