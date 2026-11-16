"""Tests del informe HTML autocontenido."""

import re
from html.parser import HTMLParser

from seo_auditor.report import CATEGORY_NAMES
from seo_auditor.report_html import to_html

VOID_TAGS = {"meta", "br", "hr", "img", "input", "link", "circle"}


def make_check(**overrides) -> dict:
    """Crea una comprobación de informe con valores por defecto."""
    check = {
        "id": "title_present",
        "categoria": "onpage",
        "titulo": "Páginas sin título",
        "peso": 3,
        "severidad": "alta",
        "evaluadas": 10,
        "fallos": 0,
        "puntuacion": 1.0,
        "consejo": "Añade un title único a cada página.",
        "ejemplos": [],
    }
    check.update(overrides)
    return check


def make_report(**overrides) -> dict:
    """Crea un informe mínimo válido con valores por defecto."""
    report = {
        "version_auditor": "0.1.0",
        "version_nota": 1,
        "generado": "2026-01-02T03:04:05+00:00",
        "url": "https://example.com/",
        "url_final": "https://example.com/",
        "paginas_rastreadas": 12,
        "rastreo_incompleto": False,
        "bloqueadas_por_robots": 0,
        "nota": 73,
        "categorias": {"indexacion": 90, "onpage": 61, "schema": 40, "rendimiento": None, "ia": 100},
        "comprobaciones": [
            make_check(
                fallos=3,
                puntuacion=0.7,
                ejemplos=[{"url": f"https://example.com/p{i}", "detalle": f"detalle {i}"} for i in range(3)],
            ),
            make_check(id="viewport", titulo="Falta meta viewport", severidad="media"),
            make_check(id="hsts", titulo="Falta HSTS", categoria="rendimiento", severidad="baja",
                       evaluadas=0, puntuacion=None),
        ],
    }
    report.update(overrides)
    return report


class Collector(HTMLParser):
    """Recoge etiquetas, atributos y comprueba que las etiquetas cierran en orden."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.tags: list[tuple[str, dict]] = []
        self.balanced = True

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.balanced = False


def parse(html: str) -> Collector:
    """Analiza el HTML y devuelve el recolector."""
    collector = Collector()
    collector.feed(html)
    collector.close()
    return collector


def section(html: str, heading: str) -> str:
    """Devuelve el fragmento de la sección cuyo h2 empieza por el texto dado."""
    start = html.index(f"<h2>{heading}")
    return html[start:html.index("</section>", start)]


def test_basic_document_structure():
    html = to_html(make_report())
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="es">' in html
    assert '<meta charset="utf-8">' in html
    assert '<meta name="viewport"' in html
    assert html.rstrip().endswith("</html>")
    parsed = parse(html)
    assert parsed.balanced and parsed.stack == []


def test_shows_score_header_and_categories():
    html = to_html(make_report())
    assert 'aria-label="Nota global: 73 de 100"' in html
    assert '<text class="gauge-number" x="70" y="76" text-anchor="middle">73</text>' in html
    assert "12 páginas rastreadas" in html
    assert "02/01/2026 03:04 UTC" in html
    assert '<a class="break" href="https://example.com/"' in html
    for name in CATEGORY_NAMES.values():
        assert name in html
    assert "90/100" in html and "61/100" in html


def test_score_colour_ranges():
    assert "gauge-value good" in to_html(make_report(nota=80))
    assert "gauge-value mid" in to_html(make_report(nota=79))
    assert "gauge-value mid" in to_html(make_report(nota=50))
    assert "gauge-value bad" in to_html(make_report(nota=49))


def test_none_score_is_shown_as_nd():
    html = to_html(make_report(nota=None, categorias={"onpage": None}))
    assert 'aria-label="Nota global: n/d"' in html
    assert ">n/d</text>" in html
    assert '<span class="cat-score">n/d</span>' in html
    assert "None" not in html


def test_priorities_keep_order_and_list_all_examples():
    examples = [{"url": f"https://example.com/e{i}", "detalle": ""} for i in range(8)]
    checks = [
        make_check(id="b_check", titulo="Segunda por id", fallos=8, ejemplos=examples),
        make_check(id="a_check", titulo="Primera por id", fallos=1, severidad="baja",
                   ejemplos=[{"url": "https://example.com/x", "detalle": "algo"}]),
    ]
    html = to_html(make_report(comprobaciones=checks))
    priorities = section(html, "Prioridades")
    assert priorities.index("Segunda por id") < priorities.index("Primera por id")
    assert "8 de 10 afectadas" in priorities
    assert "Ver ejemplos (8)" in priorities
    for i in range(8):
        assert f'href="https://example.com/e{i}"' in priorities
    assert '<span class="badge sev-alta">alta</span>' in priorities
    assert '<span class="badge sev-baja">baja</span>' in priorities
    assert "<details>" in priorities
    assert "Comprobaciones superadas" not in html


def test_passed_and_not_evaluated_sections():
    html = to_html(make_report())
    assert "Falta meta viewport" in section(html, "Comprobaciones superadas")
    assert "Falta HSTS" in section(html, "No evaluadas")
    assert "Falta HSTS" not in section(html, "Comprobaciones superadas")
    assert "Falta meta viewport" not in section(html, "Prioridades")


def test_no_problems_message_and_no_empty_sections():
    html = to_html(make_report(comprobaciones=[make_check()]))
    assert "No se encontraron problemas." in html
    assert "<h2>No evaluadas" not in html


def test_notices():
    quiet = to_html(make_report())
    assert "Rastreo incompleto" not in quiet
    assert "Bloqueadas por robots.txt" not in quiet
    html = to_html(make_report(rastreo_incompleto=True, bloqueadas_por_robots=4))
    assert "Rastreo incompleto" in html
    assert "4 URL(s) no se rastrearon porque robots.txt lo impide" in html


def test_escapes_untrusted_values():
    payload = '<script>alert(1)</script>'
    attr = '"onmouseover="alert(1)'
    checks = [make_check(
        id=payload,
        titulo=payload,
        consejo=payload,
        severidad=attr,
        categoria=payload,
        fallos=2,
        ejemplos=[
            {"url": f"https://example.com/{attr}", "detalle": payload},
            {"url": payload, "detalle": attr},
        ],
    )]
    html = to_html(make_report(
        url_final=f"https://evil.example/{attr}{payload}",
        generado=payload,
        version_auditor=payload,
        categorias={payload: 10},
        comprobaciones=checks,
    ))
    assert "<script" not in html.lower()
    assert '"onmouseover=' not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&quot;onmouseover=" in html
    parsed = parse(html)
    assert parsed.balanced
    for tag, attrs in parsed.tags:
        assert tag != "script"
        assert not any(name.startswith("on") for name in attrs)


def test_non_http_urls_are_not_links():
    urls = ["javascript:alert(1)", " javascript:alert(1)", "data:text/html,x", "//evil.example/x", "/relativa"]
    checks = [make_check(fallos=len(urls), ejemplos=[{"url": u, "detalle": ""} for u in urls])]
    html = to_html(make_report(url_final="javascript:alert(1)", comprobaciones=checks))
    assert "javascript:alert(1)" in html
    hrefs = [attrs["href"] for tag, attrs in parse(html).tags if "href" in attrs]
    assert hrefs == []


def test_no_remote_resources():
    examples = [{"url": "https://example.com/a", "detalle": ""}, {"url": "http://example.com/b", "detalle": ""}]
    html = to_html(make_report(comprobaciones=[make_check(fallos=2, ejemplos=examples)]))
    parsed = parse(html)
    allowed = {"https://example.com/", "https://example.com/a", "http://example.com/b"}
    for tag, attrs in parsed.tags:
        assert tag not in {"script", "link", "img", "iframe", "object", "embed", "video", "audio", "source"}
        assert "src" not in attrs and "srcset" not in attrs
        if "href" in attrs:
            assert tag == "a" and attrs["href"] in allowed
    assert not re.search(r"url\(|@import|@font-face", html)


def test_output_is_deterministic():
    report = make_report(rastreo_incompleto=True)
    assert to_html(report) == to_html(report)
