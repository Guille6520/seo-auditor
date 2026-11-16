"""Regresiones del parser, del rastreo con redirecciones, de orphan_pages y de la nota."""

import pytest

from conftest import GOOD_DESC, page
from seo_auditor.checks import REGISTRY, Check, CheckResult, Failure, run_checks
from seo_auditor.crawler import crawl
from seo_auditor.parser import normalize_url, parse_html, site_key
from seo_auditor.scoring import category_scores, overall_score, priority

BASE = "http://example.com"
XML = {"Content-Type": "application/xml"}
ONPAGE_IDS = (
    "title_present", "title_length", "title_unique", "meta_description_present",
    "meta_description_length", "meta_description_unique", "h1_single", "thin_content",
    "img_alt", "lang_attr", "viewport", "noindex", "canonical_present", "canonical_other",
    "jsonld_valid", "response_time",
)


def doc(head="", body=""):
    return f"<!doctype html><html lang='es'><head>{head}</head><body>{body}</body></html>"


def unique_page(n, **kwargs):
    """Pagina correcta con titulo y descripcion distintos para cada n."""
    return 200, {}, page(title=f"Pagina numero {n} con un titulo de longitud adecuada",
                         desc=f"{GOOD_DESC} Numero {n}.", **kwargs)


def urlset(*locs):
    items = "".join(f"<url><loc>{loc}</loc></url>" for loc in locs)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'


def audit(serve, build, **kwargs):
    """Arranca el servidor, rellena las rutas con build(base) y devuelve (base, rastreo, resultados)."""
    routes: dict = {}
    base = serve(routes)
    routes.update(build(base))
    result = crawl(base + "/", delay=0, allow_private=True, **kwargs)
    return base, result, {r.check.id: r for r in run_checks(result)}


def failing(res, base):
    return sorted(f.url.removeprefix(base) for f in res.failures)


# ---------- 20. Enlaces y canonical mal formados ----------

def test_malformed_links_do_not_raise_and_valid_links_are_kept():
    body = (
        '<a href="/antes">a</a>'
        '<a href="http://[bad/">b</a>'
        '<a href="//[x">c</a>'
        '<a href="http://example.com:abc/">d</a>'
        '<a href="http://example.com:99999/">e</a>'
        '<a href="http://[::1/roto">f</a>'
        '<a href="/despues">g</a>'
        '<a href="http://otro.example/fuera">h</a>'
    )
    data = parse_html(doc("<title>t</title>", body), BASE + "/")
    assert data.links == [BASE + "/antes", BASE + "/despues", "http://otro.example/fuera"]
    assert data.title == "t"


@pytest.mark.parametrize("href", ["http://[bad/", "//[x", "http://example.com:abc/", "http://example.com:99999/"])
def test_malformed_canonical_is_treated_as_missing(href):
    data = parse_html(doc(f'<title>t</title><link rel="canonical" href="{href}">', '<a href="/a">a</a>'), BASE + "/")
    assert data.canonical is None
    assert data.links == [BASE + "/a"]


def test_malformed_base_href_does_not_raise():
    data = parse_html(doc('<base href="http://[bad/">', '<a href="/a">a</a>'), BASE + "/x/")
    assert data.links == [BASE + "/a"]


def test_non_http_links_are_skipped_and_duplicates_collapsed():
    body = (
        '<a href="mailto:a@example.com">m</a><a href="tel:+34600000000">t</a>'
        '<a href="javascript:void(0)">j</a><a href="#ancla">f</a><a href="">v</a>'
        '<a href="ftp://example.com/f">ftp</a><a>sin href</a>'
        '<a href="/a">1</a><a href="/a#seccion">2</a><a href="HTTP://EXAMPLE.com/a">3</a>'
    )
    assert parse_html(doc(body=body), BASE + "/").links == [BASE + "/a"]


def test_crawl_survives_page_with_malformed_links_and_canonical(serve):
    def build(base):
        home = page(head_extra='<link rel="canonical" href="http://[bad/">',
                    body='<a href="http://[bad/">x</a><a href="//[x">y</a>'
                         '<a href="http://example.com:abc/">z</a><a href="/buena">ok</a>')
        return {"/": (200, {}, home), "/buena": unique_page(1)}

    base, result, res = audit(serve, build)
    assert base + "/buena" in result.pages
    assert result.pages[base + "/"].data.canonical is None
    assert failing(res["canonical_present"], base) == ["/", "/buena"]
    assert res["status_ok"].failures == []


# ---------- 21. <base href> ----------

def test_base_href_changes_how_relative_links_resolve():
    html = doc('<base href="/">', '<a href="contacto">c</a>')
    assert parse_html(html, BASE + "/seccion/sub/").links == [BASE + "/contacto"]


def test_without_base_relative_links_resolve_against_the_page():
    html = doc(body='<a href="contacto">c</a>')
    assert parse_html(html, BASE + "/seccion/sub/").links == [BASE + "/seccion/sub/contacto"]


def test_base_href_also_applies_to_canonical_and_absolute_base():
    html = doc('<base href="http://otro.example/dir/"><link rel="canonical" href="pagina">', '<a href="x">x</a>')
    data = parse_html(html, BASE + "/seccion/")
    assert data.canonical == "http://otro.example/dir/pagina"
    assert data.links == ["http://otro.example/dir/x"]


# ---------- 22. <svg><title> ----------

def test_svg_title_in_body_is_not_the_page_title():
    data = parse_html(doc(body="<svg><title>Icono</title></svg><p>texto</p>"), BASE + "/")
    assert data.title is None


def test_head_title_wins_over_svg_title():
    data = parse_html(doc("<title>Real</title>", "<svg><title>Icono</title></svg>"), BASE + "/")
    assert data.title == "Real"


def test_empty_title_is_none():
    assert parse_html(doc("<title>   </title>"), BASE + "/").title is None


def test_svg_title_page_fails_title_present(serve):
    def build(base):
        return {
            "/": (200, {}, page(body='<a href="/icono">i</a>')),
            "/icono": (200, {}, page(title=None, body="<svg><title>Icono</title></svg>")),
        }

    base, _, res = audit(serve, build)
    assert failing(res["title_present"], base) == ["/icono"]


# ---------- 23. rel="Canonical" ----------

@pytest.mark.parametrize("rel", ["canonical", "Canonical", "CANONICAL", "nofollow Canonical"])
def test_canonical_rel_is_case_insensitive(rel):
    data = parse_html(doc(f'<link rel="{rel}" href="/preferida">'), BASE + "/x")
    assert data.canonical == BASE + "/preferida"


def test_other_rel_is_not_canonical():
    data = parse_html(doc('<link rel="stylesheet" href="/a.css"><link rel="alternate" href="/en">'), BASE + "/")
    assert data.canonical is None


# ---------- 24. noindex ----------

def test_noindex_detected_via_none_header_and_googlebot_meta(serve):
    def build(base):
        links = "".join(f'<a href="/{p}">{p}</a>' for p in
                        ("meta-none", "cabecera-none", "googlebot", "meta-noindex", "indexable", "sin-meta"))
        return {
            "/": (200, {}, page(body=links)),
            "/meta-none": unique_page(1, head_extra='<meta name="robots" content="none">'),
            "/cabecera-none": (200, {"X-Robots-Tag": "none"}, unique_page(2)[2]),
            "/googlebot": unique_page(3, head_extra='<meta name="googlebot" content="noindex">'),
            "/meta-noindex": unique_page(4, head_extra='<meta name="ROBOTS" content="NOINDEX, follow">'),
            "/indexable": unique_page(5, head_extra='<meta name="robots" content="index, follow">'),
            "/sin-meta": unique_page(6),
        }

    base, _, res = audit(serve, build)
    assert failing(res["noindex"], base) == ["/cabecera-none", "/googlebot", "/meta-noindex", "/meta-none"]
    assert res["noindex"].applicable == 7


def test_index_follow_and_similar_words_are_not_noindex(serve):
    def build(base):
        return {
            "/": (200, {"X-Robots-Tag": "index, follow"},
                  page(head_extra='<meta name="robots" content="index, follow, max-snippet:-1">'
                                  '<meta name="googlebot" content="nonechoice">')),
        }

    _, _, res = audit(serve, build)
    assert res["noindex"].applicable == 1
    assert res["noindex"].failures == []


def test_meta_robots_collects_robots_and_googlebot():
    data = parse_html(doc('<meta name="robots" content="index"><meta name="Googlebot" content="NoIndex">'), BASE + "/")
    assert "noindex" in data.meta_robots and "index" in data.meta_robots.split(",")


# ---------- 25. normalize_url ----------

def test_normalize_url_non_ascii_path_equals_percent_encoded():
    assert normalize_url(BASE + "/café") == normalize_url(BASE + "/caf%C3%A9")
    assert normalize_url(BASE + "/café") == BASE + "/caf%C3%A9"
    assert normalize_url(BASE + "/b?q=café") == normalize_url(BASE + "/b?q=caf%C3%A9")


def test_normalize_url_keeps_ipv6_brackets():
    assert normalize_url("http://[::1]:8080/a") == "http://[::1]:8080/a"
    assert normalize_url("http://[::1]/a") == "http://[::1]/a"
    assert normalize_url("http://[::1]:80/a") == "http://[::1]/a"
    assert site_key("http://[::1]:8080/a") == "[::1]:8080"


def test_normalize_url_idn_host_becomes_punycode():
    expected = "españa.example".encode("idna").decode("ascii")
    assert expected.startswith("xn--")
    assert normalize_url("http://españa.example/ruta") == f"http://{expected}/ruta"
    assert normalize_url("http://ESPAÑA.example/ruta") == normalize_url(f"http://{expected}/ruta")


def test_normalize_url_basics_still_work():
    assert normalize_url("HTTP://Example.COM:80") == "http://example.com/"
    assert normalize_url("https://example.com:443/a#frag") == "https://example.com/a"
    assert normalize_url("https://example.com:8443/a?b=1&c=2") == "https://example.com:8443/a?b=1&c=2"
    assert normalize_url(" http://example.com/a/ ") == "http://example.com/a/"
    assert normalize_url(BASE + "/A") != normalize_url(BASE + "/a")  # la ruta distingue mayusculas
    assert normalize_url(normalize_url(BASE + "/café?x=ñ")) == normalize_url(BASE + "/café?x=ñ")
    assert site_key("https://www.example.com/a") == "example.com"


@pytest.mark.parametrize("url", ["http://[bad/", "http://example.com:abc/", "http://example.com:99999/"])
def test_normalize_url_malformed_raises_valueerror(url):
    with pytest.raises(ValueError):
        normalize_url(url)


# ---------- 26. Redireccion a otro host: la pagina externa no se analiza ----------

def test_page_redirecting_to_other_host_is_not_analyzed(serve):
    # Pagina externa mala a proposito: sin titulo, descripcion, H1, lang, viewport y con poco texto.
    external_html = "<html><head></head><body><img src='x.png'><a href='/mas'>mas</a></body></html>"
    other = serve({"/externa": (200, {}, external_html), "/mas": (200, {}, external_html)})

    def build(base):
        return {
            "/": (200, {}, page(body='<a href="/fuera">fuera</a> <a href="/dentro">dentro</a>')),
            "/fuera": (302, {"Location": other + "/externa"}, ""),
            "/dentro": unique_page(1),
        }

    base, result, res = audit(serve, build)
    moved = result.pages[base + "/fuera"]
    assert moved.fetch.status == 200
    assert moved.fetch.url == other + "/externa"
    assert moved.fetch.chain == [(base + "/fuera", 302)]
    assert moved.data is None
    # Sus enlaces no se siguen ni cuentan como enlaces internos.
    assert not any(url.startswith(other) for url in result.pages)
    assert not any(url.startswith(other) for url in result.inlinks)
    for check_id in ONPAGE_IDS:
        assert not any(f.url.startswith(other) for f in res[check_id].failures), check_id
    for check_id in ("title_present", "meta_description_present", "h1_single", "thin_content",
                     "lang_attr", "viewport", "noindex"):
        assert res[check_id].applicable == 2, check_id
        assert res[check_id].failures == [], check_id
    assert res["img_alt"].applicable == 0
    assert res["status_ok"].applicable == 3 and res["status_ok"].failures == []


def test_redirect_within_the_site_is_analyzed(serve):
    # Control: una redireccion dentro del mismo sitio si se analiza, con la URL final.
    def build(base):
        return {
            "/": (200, {}, page(body='<a href="/viejo">v</a>')),
            "/viejo": (302, {"Location": "/nuevo"}, ""),
            "/nuevo": (200, {}, page(title=None)),
        }

    base, result, res = audit(serve, build)
    assert result.pages[base + "/viejo"].data is not None
    assert res["title_present"].applicable == 2
    assert failing(res["title_present"], base) == ["/nuevo"]


# ---------- 27. Dos URLs que redirigen al mismo destino ----------

def test_two_urls_redirecting_to_same_page_are_not_self_duplicates(serve):
    def build(base):
        return {
            "/": (200, {}, page(body='<a href="/a">a</a> <a href="/A">A</a>')),
            "/a": (301, {"Location": "/a/"}, ""),
            "/A": (301, {"Location": "/a/"}, ""),
            "/a/": unique_page(1, words=20),
        }

    base, result, res = audit(serve, build)
    assert result.pages[base + "/a"].fetch.url == base + "/a/"
    assert result.pages[base + "/A"].fetch.url == base + "/a/"
    assert res["title_unique"].failures == []
    assert res["meta_description_unique"].failures == []
    assert res["title_unique"].applicable == 2
    assert res["title_present"].applicable == 2
    # Un problema real de esa pagina se cuenta una sola vez.
    assert failing(res["thin_content"], base) == ["/a/"]
    assert res["thin_content"].applicable == 2


def test_real_duplicate_titles_are_still_detected(serve):
    # Control: dos documentos distintos con el mismo titulo si son duplicados.
    def build(base):
        same = page(title="Titulo repetido en dos paginas distintas del sitio")
        return {
            "/": (200, {}, page(body='<a href="/uno">1</a> <a href="/dos">2</a> <a href="/tres">3</a>')),
            "/uno": (200, {}, same),
            "/dos": (200, {}, same),
            "/tres": unique_page(3),
        }

    base, _, res = audit(serve, build)
    assert failing(res["title_unique"], base) == ["/dos", "/uno"]
    assert res["title_unique"].applicable == 4


def test_directly_requested_page_and_redirect_to_it_count_once(serve):
    def build(base):
        return {
            "/": (200, {}, page(body='<a href="/viejo">v</a> <a href="/nuevo">n</a>')),
            "/viejo": (301, {"Location": "/nuevo"}, ""),
            "/nuevo": unique_page(1),
        }

    _, _, res = audit(serve, build)
    assert res["title_unique"].applicable == 2
    assert res["title_unique"].failures == []


# ---------- 28. orphan_pages ----------

def test_orphan_link_through_redirect_is_not_orphan(serve):
    def build(base):
        return {
            "/": (200, {}, page(body='<a href="/blog">blog</a>')),
            "/blog": (301, {"Location": "/blog/"}, ""),
            "/blog/": unique_page(1),
            "/sitemap.xml": (200, XML, urlset(f"{base}/", f"{base}/blog/")),
        }

    _, result, res = audit(serve, build)
    assert result.sitemap_found and not result.truncated
    assert res["orphan_pages"].applicable == 2
    assert res["orphan_pages"].failures == []


def test_orphan_page_linking_only_to_itself_is_orphan(serve):
    def build(base):
        return {
            "/": (200, {}, page(body='<a href="/enlazada">e</a>')),
            "/enlazada": unique_page(1),
            "/sola": unique_page(2, body='<a href="/sola">yo misma</a>'),
            "/sitemap.xml": (200, XML, urlset(f"{base}/", f"{base}/enlazada", f"{base}/sola")),
        }

    base, result, res = audit(serve, build)
    assert not result.truncated
    assert result.pages[base + "/sola"].source == "sitemap"
    assert res["orphan_pages"].applicable == 3
    assert failing(res["orphan_pages"], base) == ["/sola"]


def test_orphan_page_linked_from_another_sitemap_only_page_is_not_orphan(serve):
    # Control: basta con que la enlace OTRA pagina rastreada, aunque esta sea huerfana.
    def build(base):
        return {
            "/": (200, {}, page()),
            "/sola": unique_page(1, body='<a href="/hija">hija</a>'),
            "/hija": unique_page(2),
            "/sitemap.xml": (200, XML, urlset(f"{base}/", f"{base}/sola", f"{base}/hija")),
        }

    base, _, res = audit(serve, build)
    assert failing(res["orphan_pages"], base) == ["/sola"]


def test_orphans_not_evaluable_when_depth_limit_truncates(serve):
    def build(base):
        return {
            "/": (200, {}, page(body='<a href="/p1">p1</a>')),
            "/p1": unique_page(1, body='<a href="/p2">p2</a>'),
            "/p2": unique_page(2),
            "/otra": unique_page(3),
            "/sitemap.xml": (200, XML, urlset(f"{base}/", f"{base}/otra")),
        }

    base, result, res = audit(serve, build, max_depth=1)
    assert result.sitemap_found
    assert base + "/p2" not in result.pages
    assert result.truncated is True
    assert res["orphan_pages"].applicable == 0
    assert res["orphan_pages"].failures == []
    assert res["orphan_pages"].score is None

    # Control: con profundidad suficiente el rastreo es completo y se evalua.
    base, result, res = audit(serve, build, max_depth=3)
    assert base + "/p2" in result.pages
    assert result.truncated is False
    assert res["orphan_pages"].applicable == 2
    assert failing(res["orphan_pages"], base) == ["/otra"]


def test_orphans_not_evaluable_without_sitemap(serve):
    _, result, res = audit(serve, lambda base: {"/": (200, {}, page())})
    assert not result.sitemap_found
    assert res["orphan_pages"].applicable == 0


# ---------- 29. Nota ----------

def make(weight, applicable, failures, category="c1", check_id="x"):
    check = Check(check_id, category, weight, "t", "a", lambda c: (0, []))
    return CheckResult(check, applicable, [Failure(f"u{i}") for i in range(failures)])


def test_overall_score_is_the_expected_weighted_mean():
    results = [
        make(3, 4, 1),   # 0.75
        make(1, 2, 2),   # 0.0
        make(2, 10, 0),  # 1.0
    ]
    # 100 * (3*0.75 + 1*0 + 2*1) / (3 + 1 + 2) = 70.83
    assert overall_score(results) == 71
    assert overall_score([make(3, 4, 1), make(1, 2, 2)]) == 56  # 100 * 2.25 / 4 = 56.25
    assert overall_score([make(2, 5, 0)]) == 100
    assert overall_score([make(2, 5, 5)]) == 0
    assert overall_score([make(1, 2, 1), make(1, 2, 1)]) == 50


def test_zero_weight_and_not_evaluable_checks_do_not_count():
    base = [make(3, 4, 1), make(1, 2, 2)]
    assert overall_score(base) == 56
    assert overall_score(base + [make(0, 5, 5)]) == 56   # informativa que falla en todo
    assert overall_score(base + [make(0, 5, 0)]) == 56   # informativa que pasa
    assert overall_score(base + [make(3, 0, 0)]) == 56   # no evaluable, aunque pese mucho
    assert overall_score(base + [make(0, 5, 5), make(3, 0, 0), make(0, 0, 0)]) == 56


def test_score_is_none_when_nothing_can_be_scored():
    assert overall_score([]) is None
    assert overall_score([make(3, 0, 0)]) is None
    assert overall_score([make(0, 5, 5)]) is None
    assert make(3, 0, 0).score is None
    assert make(3, 4, 1).score == 0.75


def test_category_scores_and_priority():
    results = [
        make(3, 4, 1, "a"),
        make(1, 2, 2, "a"),
        make(2, 10, 5, "b"),
        make(0, 3, 3, "c"),
        make(2, 0, 0, "d"),
    ]
    assert category_scores(results) == {"a": 56, "b": 50, "c": None, "d": None}
    assert priority(results[0]) == pytest.approx(0.75)
    assert priority(results[1]) == pytest.approx(1.0)
    assert priority(results[3]) == 0
    assert priority(results[4]) == 0


def test_registry_has_27_unique_checks():
    assert len(REGISTRY) == 27
    ids = [check.id for check in REGISTRY]
    assert len(set(ids)) == 27
    assert all(check.weight >= 0 for check in REGISTRY)
    assert sorted(check.id for check in REGISTRY if check.weight == 0) == ["llms_txt", "response_time"]
    assert {check.category for check in REGISTRY} == {"indexacion", "onpage", "schema", "rendimiento", "ia"}


def test_run_checks_returns_one_result_per_registered_check(serve):
    _, result, res = audit(serve, lambda base: {"/": (200, {}, page())})
    assert len(run_checks(result)) == 27
    assert set(res) == {check.id for check in REGISTRY}
    score = overall_score(run_checks(result))
    assert score == overall_score(run_checks(result))
    assert 0 <= score <= 100
