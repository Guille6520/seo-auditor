"""Regresiones del interprete de robots.txt (RFC 9309) y de su uso en el rastreo."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from seo_auditor.checks import AI_AGENTS, run_checks
from seo_auditor.crawler import ROBOT_AGENT, crawl
from seo_auditor.robots import Robots


class _RawHandler(BaseHTTPRequestHandler):
    """Servidor crudo: no anade Content-Type por su cuenta y anota cada peticion recibida."""

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


def rules(text):
    return Robots(text)


# ---------- 10. Gana la regla mas larga; a igualdad, Allow ----------

@pytest.mark.parametrize("text", [
    "User-agent: *\nDisallow: /\nAllow: /blog/\n",
    "User-agent: *\nAllow: /blog/\nDisallow: /\n",  # el orden no importa
])
def test_longest_rule_wins(text):
    r = rules(text)
    assert r.can_fetch("bot", "/blog/a") is True
    assert r.can_fetch("bot", "/blog/") is True
    assert r.can_fetch("bot", "/x") is False
    assert r.can_fetch("bot", "/blog") is False  # sin barra final no coincide con /blog/
    assert r.can_fetch("bot", "/") is False


def test_longest_rule_wins_when_disallow_is_longer():
    r = rules("User-agent: *\nAllow: /blog/\nDisallow: /blog/privado/\n")
    assert r.can_fetch("bot", "/blog/a") is True
    assert r.can_fetch("bot", "/blog/privado/x") is False


@pytest.mark.parametrize("text", [
    "User-agent: *\nDisallow: /a\nAllow: /a\n",
    "User-agent: *\nAllow: /a\nDisallow: /a\n",
])
def test_tie_goes_to_allow(text):
    r = rules(text)
    assert r.can_fetch("bot", "/a") is True
    assert r.can_fetch("bot", "/a/b") is True


def test_no_matching_rule_allows():
    r = rules("User-agent: *\nDisallow: /privado\n")
    assert r.can_fetch("bot", "/publico") is True
    assert r.can_fetch("bot", "/privado") is False
    assert r.can_fetch("bot", "/privado/x") is False
    assert r.can_fetch("bot", "/privados") is False  # coincidencia por prefijo
    assert r.can_fetch("bot", "/Privado") is True  # las rutas distinguen mayusculas


def test_empty_robots_allows_everything():
    r = rules("")
    assert r.can_fetch("bot", "/") is True
    assert r.can_fetch("bot", "/cualquiera?x=1") is True
    assert r.sitemaps == []
    assert Robots().can_fetch("bot", "/x") is True


# ---------- 11. Comodines ----------

def test_wildcard_query_parameter():
    r = rules("User-agent: *\nDisallow: /*?orden=\n")
    assert r.can_fetch("bot", "/lista?orden=asc") is False
    assert r.can_fetch("bot", "/a/b/lista?orden=") is False
    assert r.can_fetch("bot", "/lista") is True
    assert r.can_fetch("bot", "/lista?pagina=2") is True
    assert r.can_fetch("bot", "/orden=asc") is True


def test_wildcard_extension_with_end_anchor():
    r = rules("User-agent: *\nDisallow: /*.php$\n")
    assert r.can_fetch("bot", "/x.php") is False
    assert r.can_fetch("bot", "/a/b/x.php") is False
    assert r.can_fetch("bot", "/x.php5") is True
    assert r.can_fetch("bot", "/x.php?a=1") is True
    assert r.can_fetch("bot", "/x.html") is True
    assert r.can_fetch("bot", "/xphp") is True  # el punto es literal, no "cualquier caracter"


def test_wildcard_in_the_middle():
    r = rules("User-agent: *\nDisallow: /priv*/\n")
    assert r.can_fetch("bot", "/privado/x") is False
    assert r.can_fetch("bot", "/priv/") is False
    assert r.can_fetch("bot", "/privadisimo/") is False
    assert r.can_fetch("bot", "/priv") is True
    assert r.can_fetch("bot", "/privado") is True
    assert r.can_fetch("bot", "/publico/") is True


def test_regex_metacharacters_in_rules_are_literal():
    r = rules("User-agent: *\nDisallow: /a+b(c)\nDisallow: /[x]\n")
    assert r.can_fetch("bot", "/a+b(c)") is False
    assert r.can_fetch("bot", "/aab(c)") is True
    assert r.can_fetch("bot", "/[x]") is False
    assert r.can_fetch("bot", "/x") is True


def test_can_fetch_accepts_full_urls_and_uses_path_and_query():
    r = rules("User-agent: *\nDisallow: /privado\nDisallow: /*?orden=\n")
    assert r.can_fetch("bot", "http://example.com/privado/x") is False
    assert r.can_fetch("bot", "http://example.com/lista?orden=asc") is False
    assert r.can_fetch("bot", "http://example.com/publico") is True
    assert r.can_fetch("bot", "http://example.com") is True


# ---------- 12. Anclas, grupos, comentarios, sitemaps ----------

def test_allow_root_only_with_end_anchor():
    r = rules("User-agent: *\nDisallow: /\nAllow: /$\n")
    assert r.can_fetch("bot", "/") is True
    assert r.can_fetch("bot", "http://example.com/") is True
    assert r.can_fetch("bot", "http://example.com") is True
    assert r.can_fetch("bot", "/x") is False
    assert r.can_fetch("bot", "/?a=1") is False


def test_empty_disallow_blocks_nothing():
    r = rules("User-agent: *\nDisallow:\n")
    assert r.can_fetch("bot", "/") is True
    assert r.can_fetch("bot", "/cualquiera") is True


def test_empty_disallow_in_specific_group_overrides_star_block():
    r = rules("User-agent: *\nDisallow: /\n\nUser-agent: buenbot\nDisallow:\n")
    assert r.can_fetch("buenbot", "/x") is True
    assert r.can_fetch("otro", "/x") is False


def test_specific_agent_group_versus_star_case_insensitive():
    r = rules("User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n")
    for agent in ("GPTBot", "gptbot", "GPTBOT", "Mozilla/5.0 (compatible; GPTBot/1.2)"):
        assert r.can_fetch(agent, "/") is False
        assert r.can_fetch(agent, "/pagina") is False
    for agent in ("ClaudeBot", "seo-auditor", "Googlebot"):
        assert r.can_fetch(agent, "/") is True


def test_specific_group_replaces_star_group_instead_of_merging():
    r = rules("User-agent: *\nDisallow: /a\n\nUser-agent: foo\nDisallow: /b\n")
    assert r.can_fetch("foo", "/a") is True
    assert r.can_fetch("foo", "/b") is False
    assert r.can_fetch("bar", "/a") is False
    assert r.can_fetch("bar", "/b") is True


def test_directive_names_are_case_insensitive():
    r = rules("USER-AGENT: *\nDISALLOW: /privado\nallow: /privado/ok\nSITEMAP: http://example.com/s.xml\n")
    assert r.can_fetch("bot", "/privado/x") is False
    assert r.can_fetch("bot", "/privado/ok") is True
    assert r.sitemaps == ["http://example.com/s.xml"]


def test_consecutive_user_agents_share_rules():
    r = rules("User-agent: uno\nUser-agent: dos\nDisallow: /privado\n\nUser-agent: *\nDisallow: /otro\n")
    for agent in ("uno", "dos"):
        assert r.can_fetch(agent, "/privado") is False
        assert r.can_fetch(agent, "/otro") is True
    assert r.can_fetch("tres", "/privado") is True
    assert r.can_fetch("tres", "/otro") is False


def test_same_agent_in_two_groups_accumulates_rules():
    r = rules("User-agent: uno\nDisallow: /a\n\nUser-agent: dos\nDisallow: /z\n\nUser-agent: uno\nDisallow: /b\n")
    assert r.can_fetch("uno", "/a") is False
    assert r.can_fetch("uno", "/b") is False
    assert r.can_fetch("uno", "/z") is True
    assert r.can_fetch("dos", "/a") is True


def test_comments_and_blank_lines_are_ignored():
    text = (
        "# comentario inicial\n"
        "\n"
        "User-agent: *   # todos\n"
        "# Disallow: /comentada\n"
        "Disallow: /privado # con comentario al final\n"
        "linea sin dos puntos\n"
    )
    r = rules(text)
    assert r.can_fetch("bot", "/privado") is False
    assert r.can_fetch("bot", "/comentada") is True
    assert r.can_fetch("bot", "/publico") is True


def test_crlf_line_endings():
    r = rules("User-agent: *\r\nDisallow: /privado\r\nSitemap: http://example.com/s.xml\r\n")
    assert r.can_fetch("bot", "/privado") is False
    assert r.sitemaps == ["http://example.com/s.xml"]


def test_robots_txt_itself_is_always_allowed():
    r = rules("User-agent: *\nDisallow: /\n")
    assert r.can_fetch("bot", "/robots.txt") is True
    assert r.can_fetch("bot", "http://example.com/robots.txt") is True
    assert r.can_fetch("bot", "/robots.txt.bak") is False


def test_sitemap_lines_are_collected_regardless_of_group():
    text = (
        "Sitemap: http://example.com/uno.xml\n"
        "User-agent: *\n"
        "Disallow: /privado\n"
        "sitemap: https://example.com/dos.xml.gz\n"
        "Sitemap:\n"
    )
    r = rules(text)
    assert r.sitemaps == ["http://example.com/uno.xml", "https://example.com/dos.xml.gz"]
    assert r.can_fetch("bot", "/privado") is False


# ---------- 13. El rastreo respeta Disallow ----------

def test_crawl_does_not_download_disallowed_path(raw_serve):
    routes = {
        "/": html('<a href="/publica">a</a> <a href="/privado/x">b</a> <a href="/lista?orden=asc">c</a>'),
        "/publica": html(),
        "/privado/x": html(),
        "/lista?orden=asc": html(),
        "/robots.txt": (200, {"Content-Type": "text/plain"},
                        "User-agent: *\nDisallow: /privado/\nDisallow: /*?orden=\n"),
    }
    base, hits = raw_serve(routes)
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.robots_status == 200
    assert sorted(result.blocked_by_robots) == [base + "/lista?orden=asc", base + "/privado/x"]
    assert base + "/privado/x" not in result.pages
    assert base + "/lista?orden=asc" not in result.pages
    assert base + "/publica" in result.pages
    assert result.pages[base + "/publica"].fetch.status == 200
    assert "/privado/x" not in hits and "/lista?orden=asc" not in hits
    assert "/publica" in hits


def test_crawl_does_not_download_disallowed_sitemap_urls(raw_serve):
    routes: dict = {}
    base, hits = raw_serve(routes)
    routes.update({
        "/": html(),
        "/privado/solo-sitemap": html(),
        "/robots.txt": (200, {"Content-Type": "text/plain"}, "User-agent: *\nDisallow: /privado/\n"),
        "/sitemap.xml": (200, {"Content-Type": "application/xml"},
                         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                         f"<url><loc>{base}/</loc></url>"
                         f"<url><loc>{base}/privado/solo-sitemap</loc></url></urlset>"),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.sitemap_found
    assert result.blocked_by_robots == [base + "/privado/solo-sitemap"]
    assert "/privado/solo-sitemap" not in hits


def test_crawl_uses_its_own_agent_group(raw_serve):
    routes = {
        "/": html('<a href="/a">a</a> <a href="/b">b</a>'),
        "/a": html(),
        "/b": html(),
        "/robots.txt": (200, {"Content-Type": "text/plain"},
                        f"User-agent: *\nDisallow: /a\n\nUser-agent: {ROBOT_AGENT.upper()}\nDisallow: /b\n"),
    }
    base, hits = raw_serve(routes)
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.blocked_by_robots == [base + "/b"]
    assert "/a" in hits and "/b" not in hits


def test_crawl_without_robots_blocks_nothing(raw_serve):
    # Control: un 404 en robots.txt no bloquea nada.
    base, hits = raw_serve({"/": html('<a href="/privado/x">b</a>'), "/privado/x": html()})
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.robots_status == 404
    assert result.robots_text == ""
    assert result.blocked_by_robots == []
    assert "/privado/x" in hits


def test_html_error_page_served_as_robots_is_ignored(raw_serve):
    # Un "soft 404" (HTML con 200 en /robots.txt) no debe interpretarse como reglas.
    soft = "<!doctype html><html><body>User-agent: *\nDisallow: /\n</body></html>"
    base, hits = raw_serve({
        "/": html('<a href="/a">a</a>'),
        "/a": html(),
        "/robots.txt": (200, {"Content-Type": "text/html"}, soft),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.robots_text == ""
    assert result.blocked_by_robots == []
    assert "/a" in hits


# ---------- 14. robots.txt con Content-Type raro o sin el ----------

ROBOTS_AI = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nDisallow: /privado\n"


@pytest.mark.parametrize("headers", [
    {"Content-Type": "application/octet-stream"},
    {},
    {"Content-Type": "text/plain; charset=utf-8"},  # control
], ids=["octet-stream", "sin-content-type", "text-plain"])
def test_robots_with_odd_content_type_is_respected(raw_serve, headers):
    routes = {
        "/": html('<a href="/publica">a</a> <a href="/privado">b</a>'),
        "/publica": html(),
        "/privado": html(),
        "/robots.txt": (200, headers, ROBOTS_AI),
    }
    base, hits = raw_serve(routes)
    result = crawl(base + "/", delay=0, allow_private=True)
    assert result.robots_status == 200
    assert result.robots_text == ROBOTS_AI
    assert result.blocked_by_robots == [base + "/privado"]
    assert "/privado" not in hits

    res = {r.check.id: r for r in run_checks(result)}
    assert res["robots_txt"].failures == []
    assert res["ai_crawlers"].applicable == len(AI_AGENTS)
    assert len(res["ai_crawlers"].failures) == 1
    blocked = [agent for agent in AI_AGENTS if not Robots(result.robots_text).can_fetch(agent, "/")]
    assert blocked == ["GPTBot"]


def test_ai_crawlers_no_failures_when_nothing_is_blocked(raw_serve):
    # Control: sin grupo para agentes de IA no hay fallos.
    base, _ = raw_serve({
        "/": html(),
        "/robots.txt": (200, {"Content-Type": "application/octet-stream"},
                        "User-agent: *\nDisallow: /privado\n"),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    res = {r.check.id: r for r in run_checks(result)}
    assert res["ai_crawlers"].applicable == len(AI_AGENTS)
    assert res["ai_crawlers"].failures == []


def test_ai_crawlers_all_blocked_by_star_disallow_root(raw_serve):
    base, _ = raw_serve({
        "/": html(),
        "/robots.txt": (200, {}, "User-agent: *\nDisallow: /\n"),
    })
    result = crawl(base + "/", delay=0, allow_private=True)
    res = {r.check.id: r for r in run_checks(result)}
    assert len(res["ai_crawlers"].failures) == len(AI_AGENTS)
