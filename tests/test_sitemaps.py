"""Regresiones de la lectura de sitemaps: crawler._parse_sitemap y su uso en crawl."""

import gzip
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from seo_auditor.checks import run_checks
from seo_auditor.crawler import _parse_sitemap, crawl

NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
IMAGE_NS = 'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"'
XML = {"Content-Type": "application/xml"}


class _RawHandler(BaseHTTPRequestHandler):
    """Servidor crudo: admite cuerpos binarios, no anade Content-Type y anota las peticiones."""

    routes: dict = {}
    hits: list = []

    def do_GET(self):
        self.hits.append(self.path)
        status, headers, body = self.routes.get(self.path, (404, {"Content-Type": "text/plain"}, b"no"))
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def raw_serve():
    """raw_serve(routes) -> (base, hits). Rutas: path -> (status, headers, body str|bytes)."""
    servers = []

    def start(routes):
        hits: list[str] = []
        handler = type("Handler", (_RawHandler,), {"routes": routes, "hits": hits})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}", hits

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def html(body=""):
    doc = f"<!doctype html><html lang='es'><head><title>t</title></head><body>{body}</body></html>"
    return 200, {"Content-Type": "text/html; charset=utf-8"}, doc


def urlset(*locs, extra=""):
    items = "".join(f"<url><loc>{loc}</loc>{extra}</url>" for loc in locs)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset {NS} {IMAGE_NS}>{items}</urlset>'


def sitemapindex(*locs):
    items = "".join(f"<sitemap><loc>{loc}</loc></sitemap>" for loc in locs)
    return f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex {NS}>{items}</sitemapindex>'


def site(raw_serve, build):
    """Arranca el servidor y rellena las rutas con build(base), que necesita conocer el puerto."""
    routes: dict = {}
    base, hits = raw_serve(routes)
    routes.update(build(base))
    routes.setdefault("/", html())
    return base, hits


def checks(result):
    return {r.check.id: r for r in run_checks(result)}


# ---------- _parse_sitemap (unidad) ----------

def test_parse_urlset():
    valid, urls, children = _parse_sitemap(urlset("http://example.com/", "http://example.com/a").encode())
    assert valid is True
    assert urls == ["http://example.com/", "http://example.com/a"]
    assert children == []


def test_parse_urlset_without_namespace_and_with_whitespace():
    raw = b"<urlset><url><loc>\n  http://example.com/a  \n</loc></url></urlset>"
    assert _parse_sitemap(raw) == (True, ["http://example.com/a"], [])


def test_parse_sitemapindex():
    raw = sitemapindex("http://example.com/s1.xml", "http://example.com/s2.xml.gz").encode()
    assert _parse_sitemap(raw) == (True, [], ["http://example.com/s1.xml", "http://example.com/s2.xml.gz"])


def test_parse_gzip_sitemap():
    raw = gzip.compress(urlset("http://example.com/a", "http://example.com/b").encode())
    assert raw[:2] == b"\x1f\x8b"
    assert _parse_sitemap(raw) == (True, ["http://example.com/a", "http://example.com/b"], [])


def test_parse_corrupt_gzip_is_not_a_sitemap():
    assert _parse_sitemap(b"\x1f\x8b" + b"esto no es gzip de verdad") == (False, [], [])


@pytest.mark.parametrize("raw", [
    b"",
    b"   ",
    b"esto no es xml",
    b"<urlset><url><loc>sin cerrar",
    b"<!doctype html><html><head><title>No encontrada</title></head><body><p>404</p></body></html>",
    b"<html xmlns='http://www.w3.org/1999/xhtml'><body><loc>http://example.com/x</loc></body></html>",
    b"<rss version='2.0'><channel><link>http://example.com/</link></channel></rss>",
    b"\xff\xfe\x00\x01",
], ids=["vacio", "espacios", "texto", "xml-roto", "html", "xhtml", "rss", "binario"])
def test_parse_non_sitemaps(raw):
    assert _parse_sitemap(raw) == (False, [], [])


def test_parse_image_loc_is_not_a_page():
    extra = "<image:image><image:loc>http://example.com/img/foto.jpg</image:loc></image:image>"
    valid, urls, children = _parse_sitemap(urlset("http://example.com/a", extra=extra).encode())
    assert valid is True
    assert urls == ["http://example.com/a"]
    assert children == []


def test_parse_does_not_expand_entities():
    raw = (
        b'<?xml version="1.0"?><!DOCTYPE urlset [<!ENTITY x SYSTEM "file:///etc/hostname">]>'
        b"<urlset><url><loc>http://example.com/&x;</loc></url></urlset>"
    )
    valid, urls, _ = _parse_sitemap(raw)  # no debe lanzar ni leer el fichero
    assert valid is True
    assert urls in ([], ["http://example.com/"])


def test_parse_malformed_loc_is_returned_as_text_without_raising():
    valid, urls, _ = _parse_sitemap(urlset("http://[bad/", "http://example.com/a").encode())
    assert valid is True
    assert urls == ["http://[bad/", "http://example.com/a"]


# ---------- 15. Sitemap .xml.gz ----------

def test_crawl_reads_gzip_sitemap_served_as_application_gzip(raw_serve):
    base, hits = site(raw_serve, lambda base: {
        "/a": html(),
        "/robots.txt": (200, {"Content-Type": "text/plain"}, f"Sitemap: {base}/sitemap.xml.gz\n"),
        "/sitemap.xml.gz": (200, {"Content-Type": "application/gzip"},
                            gzip.compress(urlset(f"{base}/", f"{base}/a").encode())),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert result.sitemap_urls == [base + "/", base + "/a"]
    assert result.pages[base + "/a"].source == "sitemap"
    assert result.pages[base + "/a"].fetch.status == 200
    assert "/sitemap.xml.gz" in hits and "/sitemap.xml" not in hits
    assert checks(result)["sitemap_xml"].failures == []


@pytest.mark.parametrize("content_type", ["application/x-gzip", "application/octet-stream", None])
def test_crawl_reads_gzip_sitemap_with_other_content_types(raw_serve, content_type):
    headers = {"Content-Type": content_type} if content_type else {}
    base, _ = site(raw_serve, lambda base: {
        "/robots.txt": (200, {"Content-Type": "text/plain"}, f"Sitemap: {base}/sm.xml.gz\n"),
        "/sm.xml.gz": (200, headers, gzip.compress(urlset(f"{base}/").encode())),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert result.sitemap_urls == [base + "/"]


def test_crawl_corrupt_gzip_sitemap_is_not_found(raw_serve):
    base, _ = site(raw_serve, lambda base: {
        "/robots.txt": (200, {"Content-Type": "text/plain"}, f"Sitemap: {base}/sm.xml.gz\n"),
        "/sm.xml.gz": (200, {"Content-Type": "application/gzip"}, b"\x1f\x8b\x08\x00basura"),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is False
    assert result.sitemap_urls == []


# ---------- 16. /sitemap.xml que en realidad es HTML ----------

@pytest.mark.parametrize("content_type", ["text/html; charset=utf-8", "application/xml"])
def test_crawl_html_page_at_sitemap_url_is_not_a_sitemap(raw_serve, content_type):
    soft_404 = "<!doctype html><html><head><title>Portada</title></head><body><p>hola</p></body></html>"
    base, _ = site(raw_serve, lambda base: {
        "/sitemap.xml": (200, {"Content-Type": content_type}, soft_404),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is False
    assert result.sitemap_urls == []
    res = checks(result)
    assert len(res["sitemap_xml"].failures) == 1
    assert res["orphan_pages"].applicable == 0


def test_crawl_missing_sitemap_is_not_found(raw_serve):
    base, hits = site(raw_serve, lambda base: {})
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is False
    assert "/sitemap.xml" in hits


def test_crawl_plain_xml_sitemap_is_found(raw_serve):
    # Control: el caso normal.
    base, _ = site(raw_serve, lambda base: {
        "/a": html(),
        "/sitemap.xml": (200, XML, urlset(f"{base}/", f"{base}/a")),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert result.sitemap_urls == [base + "/", base + "/a"]
    assert checks(result)["sitemap_xml"].failures == []


# ---------- 17. <image:loc> ----------

def test_crawl_image_loc_is_not_in_sitemap_urls(raw_serve):
    def build(base):
        extra = (f"<image:image><image:loc>{base}/img/foto</image:loc></image:image>"
                 f"<image:image><image:loc>{base}/img/otra.jpg</image:loc></image:image>")
        return {"/sitemap.xml": (200, XML, urlset(f"{base}/", extra=extra))}

    base, hits = site(raw_serve, build)
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert result.sitemap_urls == [base + "/"]
    assert base + "/img/foto" not in result.pages
    assert "/img/foto" not in hits


# ---------- 18. Indice de sitemaps ----------

def test_crawl_sitemap_index_reads_children(raw_serve):
    base, hits = site(raw_serve, lambda base: {
        "/a": html(),
        "/b": html(),
        "/sitemap.xml": (200, XML, sitemapindex(f"{base}/sm-1.xml", f"{base}/sm-2.xml.gz")),
        "/sm-1.xml": (200, XML, urlset(f"{base}/", f"{base}/a")),
        "/sm-2.xml.gz": (200, {"Content-Type": "application/gzip"},
                         gzip.compress(urlset(f"{base}/b").encode())),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert result.sitemap_urls == [base + "/", base + "/a", base + "/b"]
    assert {"/sitemap.xml", "/sm-1.xml", "/sm-2.xml.gz"} <= set(hits)
    assert result.pages[base + "/a"].fetch.status == 200
    assert result.pages[base + "/b"].fetch.status == 200
    # Las URLs de los ficheros de sitemap no son paginas.
    assert base + "/sm-1.xml" not in result.sitemap_urls
    assert base + "/sm-1.xml" not in result.pages


def test_crawl_sitemap_index_with_broken_child_keeps_the_rest(raw_serve):
    base, _ = site(raw_serve, lambda base: {
        "/a": html(),
        "/sitemap.xml": (200, XML, sitemapindex(f"{base}/falta.xml", f"{base}/roto.xml", f"{base}/ok.xml")),
        "/roto.xml": (200, XML, "<urlset><url><loc>sin cerrar"),
        "/ok.xml": (200, XML, urlset(f"{base}/a")),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert result.sitemap_urls == [base + "/a"]


def test_crawl_self_referencing_sitemap_index_terminates(raw_serve):
    base, hits = site(raw_serve, lambda base: {
        "/sitemap.xml": (200, XML, sitemapindex(f"{base}/sitemap.xml")),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert result.sitemap_urls == []
    assert hits.count("/sitemap.xml") <= 10


def test_crawl_uses_all_sitemaps_declared_in_robots(raw_serve):
    base, hits = site(raw_serve, lambda base: {
        "/a": html(),
        "/b": html(),
        "/robots.txt": (200, {"Content-Type": "text/plain"},
                        f"Sitemap: {base}/uno.xml\nSitemap: {base}/dos.xml\n"),
        "/uno.xml": (200, XML, urlset(f"{base}/a")),
        "/dos.xml": (200, XML, urlset(f"{base}/b")),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert result.sitemap_urls == [base + "/a", base + "/b"]
    assert "/sitemap.xml" not in hits  # si robots declara sitemaps no se prueba el de por defecto


# ---------- 19. <loc> mal formado y tipos raros ----------

def test_crawl_malformed_loc_does_not_break_the_crawl(raw_serve):
    base, _ = site(raw_serve, lambda base: {
        "/a": html(),
        "/sitemap.xml": (200, XML, urlset(
            "http://[bad/", "//[x", "http://example.com:abc/", f"{base}/a", "", "http://example.com:99999/",
        )),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert base + "/a" in result.sitemap_urls
    assert not any("[bad" in url or "[x" in url or ":abc" in url or ":99999" in url
                   for url in result.sitemap_urls)
    assert result.pages[base + "/a"].fetch.status == 200
    run_checks(result)  # las comprobaciones tampoco deben lanzar con esos datos


@pytest.mark.parametrize("headers", [
    {"Content-Type": "application/octet-stream"},
    {"Content-Type": "text/plain"},
    {"Content-Type": "application/zip"},
    {},
], ids=["octet-stream", "text-plain", "zip", "sin-content-type"])
def test_crawl_sitemap_with_odd_content_type_is_read(raw_serve, headers):
    base, _ = site(raw_serve, lambda base: {
        "/a": html(),
        "/sitemap.xml": (200, headers, urlset(f"{base}/", f"{base}/a")),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert result.sitemap_urls == [base + "/", base + "/a"]


def test_crawl_external_sitemap_urls_are_not_fetched(raw_serve):
    other_routes: dict = {"/externa": html()}
    other, other_hits = raw_serve(other_routes)
    base, _ = site(raw_serve, lambda base: {
        "/sitemap.xml": (200, XML, urlset(f"{base}/", f"{other}/externa")),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found is True
    assert other + "/externa" not in result.pages
    assert other_hits == []
    # Y no cuenta para orphan_pages: solo se evaluan las URLs del propio sitio.
    assert checks(result)["orphan_pages"].applicable == 1
