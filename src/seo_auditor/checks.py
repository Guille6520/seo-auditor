"""Comprobaciones SEO. Cada una es una función pura sobre el resultado del rastreo.

Una comprobación devuelve (aplicable, fallos): cuántos elementos se evaluaron y
cuáles fallaron. La puntuación de la comprobación es 1 - fallos/aplicables; si
no se pudo evaluar (aplicable = 0) no cuenta para la nota.
"""

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from .crawler import CrawlResult, Page
from .parser import normalize_url, site_key
from .robots import Robots

THIN_WORDS = 150
TITLE_RANGE = (30, 60)
DESCRIPTION_RANGE = (70, 160)
SLOW_SECONDS = 1.5
NOINDEX_RE = re.compile(r"\b(noindex|none)\b")  # "none" equivale a noindex, nofollow
AI_AGENTS = ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Applebot-Extended")


@dataclass
class Failure:
    """Un elemento que no pasa una comprobación, con su evidencia."""

    url: str
    detail: str = ""


@dataclass
class Check:
    """Definición de una comprobación: metadatos (categoría, peso, textos) y su función."""

    id: str
    category: str
    weight: float
    title: str
    advice: str
    fn: Callable[[CrawlResult], tuple[int, list[Failure]]]

    @property
    def severity(self) -> str:
        if self.weight >= 3:
            return "alta"
        if self.weight >= 2:
            return "media"
        return "baja" if self.weight > 0 else "info"


@dataclass
class CheckResult:
    """Resultado de ejecutar una comprobación: cuántos elementos evaluó y cuáles fallaron."""

    check: Check
    applicable: int
    failures: list[Failure] = field(default_factory=list)

    @property
    def score(self) -> float | None:
        if self.applicable == 0:
            return None
        return 1 - len(self.failures) / self.applicable


REGISTRY: list[Check] = []


def check(id: str, category: str, weight: float, title: str, advice: str):
    """Decorador que registra una función como comprobación en REGISTRY."""
    def deco(fn):
        REGISTRY.append(Check(id, category, weight, title, advice, fn))
        return fn
    return deco


def _html(c: CrawlResult) -> list[Page]:
    """Páginas HTML analizables, una por URL final: varias URLs que redirigen al mismo
    documento no deben analizarse (ni penalizarse) más de una vez."""
    pages = [p for p in c.pages.values() if p.data is not None]
    unique: dict[str, Page] = {}
    # Primero las pedidas directamente; después las alcanzadas solo por redirección.
    for p in sorted(pages, key=lambda p: p.fetch.redirects > 0):
        unique.setdefault(normalize_url(p.fetch.url), p)
    return list(unique.values())


def _shown(p: Page) -> str:
    """URL que se muestra en el informe: la final, tras redirecciones."""
    return p.fetch.url


# ---------- Rastreo e indexación ----------

@check("status_ok", "indexacion", 3, "Páginas que responden con error",
       "Corrige o redirige las URLs que devuelven 4xx/5xx o no responden.")
def status_ok(c):
    """Páginas que no respondieron o devolvieron 4xx/5xx."""
    bad = [Failure(_shown(p), p.fetch.error or f"HTTP {p.fetch.status}")
           for p in c.pages.values() if p.fetch.status is None or p.fetch.status >= 400]
    return len(c.pages), bad


@check("broken_links", "indexacion", 3, "Enlaces internos rotos",
       "Actualiza o elimina los enlaces que apuntan a páginas que no existen.")
def broken_links(c):
    """Enlaces internos cuyo destino rastreado está roto."""
    targets = [t for t in c.inlinks if t in c.pages]
    bad = []
    for t in targets:
        p = c.pages[t]
        if p.fetch.status is None or p.fetch.status >= 400:
            sources = ", ".join(sorted(c.inlinks[t])[:3])
            bad.append(Failure(t, f"HTTP {p.fetch.status or 'sin respuesta'}; enlazada desde {sources}"))
    return len(targets), bad


@check("redirect_chain", "indexacion", 2, "Cadenas de redirección",
       "Enlaza directamente a la URL final para evitar saltos intermedios.")
def redirect_chain(c):
    """URLs que pasan por más de una redirección antes de la final."""
    bad = [Failure(p.requested, " -> ".join([u for u, _ in p.fetch.chain] + [p.fetch.url]))
           for p in c.pages.values() if p.fetch.redirects > 1]
    return len(c.pages), bad


@check("noindex", "indexacion", 2, "Páginas con noindex",
       "Confirma que cada página con noindex es intencionada; si no, quita la directiva.")
def noindex(c):
    """Páginas excluidas del índice por meta robots o X-Robots-Tag."""
    pages = _html(c)
    bad = [Failure(_shown(p), "noindex en meta robots o X-Robots-Tag") for p in pages
           if NOINDEX_RE.search(p.data.meta_robots)
           or NOINDEX_RE.search(p.fetch.headers.get("x-robots-tag", "").lower())]
    return len(pages), bad


@check("canonical_present", "indexacion", 2, "Páginas sin canonical",
       "Añade <link rel=\"canonical\"> apuntando a la URL preferida de cada página.")
def canonical_present(c):
    """Páginas HTML sin etiqueta canonical."""
    pages = _html(c)
    return len(pages), [Failure(_shown(p)) for p in pages if not p.data.canonical]


@check("canonical_other", "indexacion", 1, "Canonical que apunta a otra URL",
       "Revisa que apuntar a otra URL sea intencionado; si no, usa la propia página.")
def canonical_other(c):
    """Páginas cuyo canonical apunta a una URL distinta de la suya."""
    pages = [p for p in _html(c) if p.data.canonical]
    bad = [Failure(_shown(p), f"canonical: {p.data.canonical}") for p in pages
           if p.data.canonical != normalize_url(p.fetch.url)]
    return len(pages), bad


@check("https", "indexacion", 3, "El sitio no usa HTTPS",
       "Sirve todo el sitio por HTTPS y redirige el tráfico HTTP.")
def https(c):
    """El sitio debe terminar sirviéndose por HTTPS."""
    ok = c.final_start_url.startswith("https://")
    return 1, [] if ok else [Failure(c.final_start_url, "la URL final no es https")]


@check("robots_txt", "indexacion", 1, "Falta robots.txt",
       "Publica un robots.txt en la raíz que declare tu sitemap.")
def robots_txt(c):
    """Existe robots.txt en la raíz."""
    ok = c.robots_status == 200
    return 1, [] if ok else [Failure("/robots.txt", f"HTTP {c.robots_status}")]


@check("sitemap_xml", "indexacion", 2, "No se encontró sitemap XML",
       "Publica un sitemap.xml y decláralo en robots.txt.")
def sitemap_xml(c):
    """Se encontró un sitemap XML."""
    return 1, [] if c.sitemap_found else [Failure("/sitemap.xml", "no encontrado")]


@check("orphan_pages", "indexacion", 1, "Páginas del sitemap sin enlaces internos",
       "Enlaza estas páginas desde el resto del sitio o quítalas del sitemap.")
def orphan_pages(c):
    """URLs del sitemap que ninguna página rastreada enlaza."""
    if not c.sitemap_found or c.truncated:
        return 0, []  # no evaluable: con rastreo incompleto habría falsos positivos
    scope = site_key(c.final_start_url)
    own = {c.start_url, normalize_url(c.final_start_url)}
    urls = [u for u in dict.fromkeys(c.sitemap_urls) if site_key(u) == scope]
    linked: set[str] = set()
    for target, sources in c.inlinks.items():
        if not sources - {target}:
            continue  # solo se enlaza a sí misma: sigue siendo huérfana
        linked.add(target)
        page = c.pages.get(target)
        if page is not None and page.fetch.status is not None:
            linked.add(normalize_url(page.fetch.url))  # enlace a /blog que redirige a /blog/
    bad = [Failure(u, "está en el sitemap pero ninguna otra página rastreada la enlaza")
           for u in urls if u not in linked and u not in own]
    return len(urls), bad


# ---------- Contenido en página ----------

def _duplicates(pages: list[Page], getter) -> list[Failure]:
    groups: dict[str, list[Page]] = defaultdict(list)
    for p in pages:
        value = (getter(p) or "").strip().lower()
        if value:
            groups[value].append(p)
    return [Failure(_shown(p), f"compartido con {len(g) - 1} página(s) más")
            for g in groups.values() if len(g) > 1 for p in g]


@check("title_present", "onpage", 3, "Páginas sin <title>",
       "Cada página necesita un título propio y descriptivo.")
def title_present(c):
    """Páginas HTML sin <title>."""
    pages = _html(c)
    return len(pages), [Failure(_shown(p)) for p in pages if not p.data.title]


@check("title_length", "onpage", 1, "Títulos demasiado cortos o largos",
       f"Intenta que el título tenga entre {TITLE_RANGE[0]} y {TITLE_RANGE[1]} caracteres (orientativo).")
def title_length(c):
    """Títulos fuera del rango de longitud orientativo."""
    pages = [p for p in _html(c) if p.data.title]
    lo, hi = TITLE_RANGE
    bad = [Failure(_shown(p), f"{len(p.data.title)} caracteres") for p in pages
           if not lo <= len(p.data.title) <= hi]
    return len(pages), bad


@check("title_unique", "onpage", 2, "Títulos duplicados",
       "Da a cada página un título distinto.")
def title_unique(c):
    """Títulos repetidos entre páginas."""
    pages = [p for p in _html(c) if p.data.title]
    return len(pages), _duplicates(pages, lambda p: p.data.title)


@check("meta_description_present", "onpage", 2, "Páginas sin meta description",
       "Escribe una descripción única que resuma la página e invite al clic.")
def meta_description_present(c):
    """Páginas sin meta description."""
    pages = _html(c)
    return len(pages), [Failure(_shown(p)) for p in pages if not p.data.meta_description]


@check("meta_description_length", "onpage", 1, "Meta description demasiado corta o larga",
       f"Intenta que tenga entre {DESCRIPTION_RANGE[0]} y {DESCRIPTION_RANGE[1]} caracteres (orientativo).")
def meta_description_length(c):
    """Meta descriptions fuera del rango de longitud orientativo."""
    pages = [p for p in _html(c) if p.data.meta_description]
    lo, hi = DESCRIPTION_RANGE
    bad = [Failure(_shown(p), f"{len(p.data.meta_description)} caracteres") for p in pages
           if not lo <= len(p.data.meta_description) <= hi]
    return len(pages), bad


@check("meta_description_unique", "onpage", 1, "Meta descriptions duplicadas",
       "Da a cada página una descripción distinta.")
def meta_description_unique(c):
    """Meta descriptions repetidas entre páginas."""
    pages = [p for p in _html(c) if p.data.meta_description]
    return len(pages), _duplicates(pages, lambda p: p.data.meta_description)


@check("h1_single", "onpage", 2, "Páginas sin un único H1",
       "Usa exactamente un H1 por página que describa su tema.")
def h1_single(c):
    """Páginas que no tienen exactamente un H1."""
    pages = _html(c)
    bad = [Failure(_shown(p), "sin H1" if not p.data.h1s else f"{len(p.data.h1s)} H1")
           for p in pages if len(p.data.h1s) != 1]
    return len(pages), bad


@check("thin_content", "onpage", 2, "Páginas con muy poco texto",
       f"Amplía o consolida las páginas con menos de {THIN_WORDS} palabras.")
def thin_content(c):
    """Páginas con menos palabras que el mínimo."""
    pages = _html(c)
    bad = [Failure(_shown(p), f"{p.data.word_count} palabras") for p in pages
           if p.data.word_count < THIN_WORDS]
    return len(pages), bad


@check("img_alt", "onpage", 1, "Imágenes sin atributo alt",
       "Añade texto alternativo descriptivo (alt vacío solo en imágenes decorativas).")
def img_alt(c):
    """Páginas con imágenes sin atributo alt."""
    pages = [p for p in _html(c) if p.data.images_total > 0]
    bad = [Failure(_shown(p), f"{len(p.data.images_missing_alt)} de {p.data.images_total} sin alt")
           for p in pages if p.data.images_missing_alt]
    return len(pages), bad


@check("lang_attr", "onpage", 1, "Falta el atributo lang en <html>",
       "Declara el idioma de la página, por ejemplo <html lang=\"es\">.")
def lang_attr(c):
    """Páginas sin atributo lang en <html>."""
    pages = _html(c)
    return len(pages), [Failure(_shown(p)) for p in pages if not p.data.lang]


@check("viewport", "onpage", 2, "Falta la meta viewport",
       "Añade <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.")
def viewport(c):
    """Páginas sin meta viewport."""
    pages = _html(c)
    return len(pages), [Failure(_shown(p)) for p in pages if not p.data.viewport]


# ---------- Datos estructurados ----------

@check("jsonld_valid", "schema", 2, "JSON-LD con errores de sintaxis",
       "Corrige el JSON de los bloques application/ld+json (solo se valida que sea JSON válido).")
def jsonld_valid(c):
    """Páginas con bloques JSON-LD que no son JSON válido."""
    pages = [p for p in _html(c) if p.data.jsonld_total > 0]
    bad = [Failure(_shown(p), f"{p.data.jsonld_invalid} de {p.data.jsonld_total} bloques inválidos")
           for p in pages if p.data.jsonld_invalid]
    return len(pages), bad


@check("jsonld_home", "schema", 1, "La portada no tiene datos estructurados",
       "Añade JSON-LD (Organization o LocalBusiness, WebSite) en la portada.")
def jsonld_home(c):
    """La portada debe tener datos estructurados JSON-LD."""
    home = c.pages.get(c.start_url)
    if home is None or home.data is None:
        return 0, []
    return 1, [] if home.data.jsonld_total > 0 else [Failure(_shown(home))]


# ---------- Rendimiento y seguridad (básicos) ----------

@check("response_time", "rendimiento", 0, "Respuestas HTML lentas (informativo)",
       f"Tiempo de descarga del HTML mayor de {SLOW_SECONDS} s. No son Core Web Vitals y depende de la red, "
       "por eso no puntúa.")
def response_time(c):
    """Páginas cuyo HTML tarda más del umbral (informativo)."""
    pages = _html(c)
    return len(pages), [Failure(_shown(p), f"{p.fetch.elapsed:.2f} s") for p in pages
                        if p.fetch.elapsed > SLOW_SECONDS]


@check("hsts", "rendimiento", 1, "Falta la cabecera HSTS",
       "Envía Strict-Transport-Security para forzar HTTPS en los navegadores.")
def hsts(c):
    """La portada HTTPS debe enviar Strict-Transport-Security."""
    if not c.final_start_url.startswith("https://"):
        return 0, []
    home = c.pages.get(c.start_url)
    if home is None:
        return 0, []
    ok = "strict-transport-security" in home.fetch.headers
    return 1, [] if ok else [Failure(_shown(home), "sin Strict-Transport-Security")]


# ---------- Visibilidad en IAs ----------

@check("ai_crawlers", "ia", 1, "Rastreadores de IA bloqueados en robots.txt",
       "Si quieres aparecer en respuestas de IA, permite estos agentes. Si el bloqueo es "
       "intencionado, ignora este aviso.")
def ai_crawlers(c):
    """Agentes de IA que robots.txt no deja acceder a la raíz."""
    robots = Robots(c.robots_text)
    bad = [Failure("/robots.txt", f"{agent} no puede acceder a /") for agent in AI_AGENTS
           if not robots.can_fetch(agent, "/")]
    return len(AI_AGENTS), bad


@check("llms_txt", "ia", 0, "No hay llms.txt (informativo)",
       "llms.txt es una propuesta de formato sin efecto demostrado en las respuestas de las IAs; "
       "se informa pero no puntúa.")
def llms_txt(c):
    """Existe llms.txt (informativo)."""
    return 1, [] if c.llms_txt_found else [Failure("/llms.txt", "no encontrado")]


def run_checks(crawl_result: CrawlResult) -> list[CheckResult]:
    """Ejecuta todas las comprobaciones registradas sobre un rastreo."""
    return [CheckResult(ch, *ch.fn(crawl_result)) for ch in REGISTRY]
