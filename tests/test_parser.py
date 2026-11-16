from seo_auditor.parser import normalize_url, parse_html, site_key

HTML = """<!doctype html><html lang="es"><head><title> Hola  mundo </title>
<meta name="description" content=" Una descripción ">
<meta name="robots" content="NoIndex, follow">
<meta name="viewport" content="width=device-width">
<link rel="canonical" href="/pagina#frag">
<script type="application/ld+json">{"@type": "Organization"}</script>
<script type="application/ld+json">{roto</script>
</head><body><h1>Uno</h1><h1>Dos</h1>
<script>var texto = "no cuenta como contenido";</script>
<p>Palabras reales aquí</p>
<img src="/a.png"><img src="/b.png" alt="">
<a href="/x#top">x</a><a href="/x">x otra vez</a><a href="mailto:a@b.c">mail</a>
<a href="https://otro.com/y">externo</a><a href="javascript:void(0)">js</a>
</body></html>"""


def test_parse_basic_fields():
    d = parse_html(HTML, "https://ejemplo.com/base/")
    assert d.title == "Hola mundo"
    assert d.meta_description == "Una descripción"
    assert "noindex" in d.meta_robots
    assert d.viewport and d.lang == "es"
    assert d.h1s == ["Uno", "Dos"]
    assert d.canonical == "https://ejemplo.com/pagina"


def test_images_alt_empty_counts_as_present():
    d = parse_html(HTML, "https://ejemplo.com/")
    assert d.images_total == 2
    assert d.images_missing_alt == ["/a.png"]


def test_jsonld_invalid_block_is_counted():
    d = parse_html(HTML, "https://ejemplo.com/")
    assert (d.jsonld_total, d.jsonld_invalid) == (2, 1)


def test_links_are_normalized_deduplicated_and_filtered():
    d = parse_html(HTML, "https://ejemplo.com/")
    assert d.links == ["https://ejemplo.com/x", "https://otro.com/y"]


def test_word_count_ignores_scripts():
    d = parse_html(HTML, "https://ejemplo.com/")
    assert d.word_count < 20  # sin el texto del script (que tiene 5 palabras más)


def test_inline_tags_keep_word_boundaries():
    d = parse_html("<html><body><p>uno<b>dos</b> tres</p></body></html>", "https://e.com/")
    assert d.word_count == 3


def test_normalize_and_site_key():
    assert normalize_url("HTTP://Ejemplo.COM:80") == "http://ejemplo.com/"
    assert normalize_url("https://e.com:443/a?b=1#c") == "https://e.com/a?b=1"
    assert normalize_url("http://e.com:8080/a") == "http://e.com:8080/a"
    assert site_key("https://www.e.com/x") == site_key("https://e.com/y")
    assert site_key("https://e.com:8080/") != site_key("https://e.com/")
