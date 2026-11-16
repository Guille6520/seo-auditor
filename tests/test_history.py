"""Tests de la comparación de informes (sin red)."""

import json

from seo_auditor.history import compare, compare_markdown


def make_check(check_id, fallos=0, evaluadas=10, urls=None, categoria="onpage"):
    """Construye una comprobación con la forma que genera build_report."""
    urls = urls if urls is not None else [f"https://example.com/{check_id}/{i}" for i in range(fallos)]
    return {
        "id": check_id,
        "categoria": categoria,
        "titulo": f"Título {check_id}",
        "peso": 3,
        "severidad": "media",
        "evaluadas": evaluadas,
        "fallos": fallos,
        "puntuacion": None if not evaluadas else round(1 - fallos / evaluadas, 3),
        "consejo": "Consejo",
        "ejemplos": [{"url": url, "detalle": "detalle"} for url in urls],
    }


def make_report(checks, nota=80, categorias=None, **overrides):
    """Construye un informe mínimo con la forma que genera build_report."""
    report = {
        "version_auditor": "0.1.0",
        "version_nota": 1,
        "generado": "2026-01-01T00:00:00+00:00",
        "url": "https://example.com/",
        "url_final": "https://example.com/",
        "paginas_rastreadas": 10,
        "rastreo_incompleto": False,
        "bloqueadas_por_robots": 0,
        "nota": nota,
        "categorias": categorias if categorias is not None else {"onpage": nota},
        "comprobaciones": checks,
    }
    report.update(overrides)
    return report


def by_id(diff):
    """Indexa las comprobaciones del resultado por id."""
    return {c["id"]: c for c in diff["comprobaciones"]}


def test_score_goes_up():
    diff = compare(make_report([], nota=60), make_report([], nota=75))
    assert diff["nota"] == {"anterior": 60, "actual": 75, "diferencia": 15}


def test_score_goes_down():
    diff = compare(make_report([], nota=75), make_report([], nota=60))
    assert diff["nota"]["diferencia"] == -15


def test_score_none_gives_no_difference():
    diff = compare(make_report([], nota=None), make_report([], nota=70))
    assert diff["nota"] == {"anterior": None, "actual": 70, "diferencia": None}
    assert "n/d -> 70/100 (n/d)" in compare_markdown(diff)


def test_category_differences():
    previous = make_report([], categorias={"onpage": 50, "schema": None, "ia": 90})
    current = make_report([], categorias={"onpage": 70, "schema": 40, "rendimiento": 100})
    diff = compare(previous, current)
    assert diff["categorias"] == [
        {"categoria": "ia", "anterior": 90, "actual": None, "diferencia": None},
        {"categoria": "onpage", "anterior": 50, "actual": 70, "diferencia": 20},
        {"categoria": "rendimiento", "anterior": None, "actual": 100, "diferencia": None},
        {"categoria": "schema", "anterior": None, "actual": 40, "diferencia": None},
    ]


def test_states():
    previous = make_report([
        make_check("a", fallos=3),
        make_check("b", fallos=0),
        make_check("c", fallos=5),
        make_check("d", fallos=1),
        make_check("e", fallos=2),
        make_check("f", fallos=0),
    ])
    current = make_report([
        make_check("a", fallos=0),
        make_check("b", fallos=2),
        make_check("c", fallos=2),
        make_check("d", fallos=4),
        make_check("e", fallos=2),
        make_check("f", fallos=0),
    ])
    diff = compare(previous, current)
    assert {k: v["estado"] for k, v in by_id(diff).items()} == {
        "a": "resuelta", "b": "nueva", "c": "mejora", "d": "empeora", "e": "igual", "f": "igual",
    }
    assert diff["resumen"] == {
        "resuelta": 1, "nueva": 1, "empeora": 1, "mejora": 1, "igual": 2, "no_comparable": 0,
    }
    assert by_id(diff)["a"]["fallos_anterior"] == 3
    assert by_id(diff)["a"]["fallos_actual"] == 0
    assert by_id(diff)["a"]["titulo"] == "Título a"


def test_check_missing_in_current_is_not_resolved():
    diff = compare(make_report([make_check("a", fallos=3)]), make_report([]))
    check = by_id(diff)["a"]
    assert check["estado"] == "no_comparable"
    assert check["presente_actual"] is False
    assert check["fallos_actual"] is None
    assert check["urls_corregidas"] == []
    assert "Comprobaciones solo en el informe anterior: a." in diff["avisos"]


def test_check_missing_in_previous():
    current = make_report([make_check("a", fallos=2), make_check("b", fallos=0)])
    diff = compare(make_report([]), current)
    checks = by_id(diff)
    assert checks["a"]["estado"] == "nueva"
    assert checks["a"]["fallos_anterior"] is None
    assert checks["a"]["urls_nuevas"] == ["https://example.com/a/0", "https://example.com/a/1"]
    assert checks["b"]["estado"] == "no_comparable"
    assert "Comprobaciones solo en el informe actual: a, b." in diff["avisos"]


def test_not_evaluated_is_not_resolved():
    previous = make_report([make_check("a", fallos=3), make_check("b", fallos=0, evaluadas=0)])
    current = make_report([make_check("a", fallos=0, evaluadas=0), make_check("b", fallos=0)])
    checks = by_id(compare(previous, current))
    assert checks["a"]["estado"] == "no_comparable"
    assert checks["a"]["urls_corregidas"] == []
    assert checks["b"]["estado"] == "no_comparable"


def test_not_evaluated_before_with_failures_now_is_new():
    previous = make_report([make_check("a", fallos=0, evaluadas=0)])
    current = make_report([make_check("a", fallos=1)])
    assert by_id(compare(previous, current))["a"]["estado"] == "nueva"


def test_fixed_and_new_urls():
    previous = make_report([make_check("a", fallos=3, urls=["https://e.com/3", "https://e.com/1", "https://e.com/2"])])
    current = make_report([make_check("a", fallos=2, urls=["https://e.com/9", "https://e.com/2"])])
    check = by_id(compare(previous, current))["a"]
    assert check["urls_corregidas"] == ["https://e.com/1", "https://e.com/3"]
    assert check["urls_nuevas"] == ["https://e.com/9"]


def test_no_warnings_when_comparable():
    report = make_report([make_check("a", fallos=1)])
    assert compare(report, report)["avisos"] == []


def test_comparability_warnings():
    previous = make_report([], version_nota=1, url_final="https://a.com/", paginas_rastreadas=10)
    current = make_report(
        [], version_nota=2, url_final="https://b.com/", paginas_rastreadas=25, rastreo_incompleto=True
    )
    avisos = compare(previous, current)["avisos"]
    assert len(avisos) == 4
    assert any("versión de la nota" in a and "1 -> 2" in a for a in avisos)
    assert any("URLs distintas" in a and "https://a.com/ -> https://b.com/" in a for a in avisos)
    assert any("informe actual fue incompleto" in a for a in avisos)
    assert any("páginas rastreadas difiere (10 -> 25)" in a for a in avisos)


def test_incomplete_previous_crawl_warns():
    avisos = compare(make_report([], rastreo_incompleto=True), make_report([]))["avisos"]
    assert avisos == ["El rastreo del informe anterior fue incompleto: hay páginas sin analizar."]


def test_result_is_json_serializable_and_deterministic():
    previous = make_report([make_check("b", fallos=3), make_check("a", fallos=1)])
    current = make_report([make_check("a", fallos=0), make_check("c", fallos=2), make_check("b", fallos=1)])
    first = compare(previous, current)
    shuffled = dict(current, comprobaciones=list(reversed(current["comprobaciones"])))
    assert json.dumps(first) == json.dumps(compare(previous, shuffled))
    assert json.loads(json.dumps(first)) == first
    assert [c["id"] for c in first["comprobaciones"]] == ["a", "b", "c"]
    assert compare_markdown(first) == compare_markdown(compare(previous, shuffled))


def test_compare_does_not_mutate_inputs():
    previous = make_report([make_check("a", fallos=2)])
    current = make_report([make_check("a", fallos=1)])
    snapshot = json.dumps([previous, current])
    compare(previous, current)
    assert json.dumps([previous, current]) == snapshot


def test_markdown_sections():
    previous = make_report(
        [make_check("a", fallos=3), make_check("b", fallos=0), make_check("c", fallos=5), make_check("d", fallos=1)],
        nota=60,
        categorias={"onpage": 60},
    )
    current = make_report(
        [make_check("a", fallos=0), make_check("b", fallos=2), make_check("c", fallos=2), make_check("d", fallos=4)],
        nota=72,
        categorias={"onpage": 72},
        paginas_rastreadas=12,
    )
    md = compare_markdown(compare(previous, current))
    assert "**Nota: 60/100 -> 72/100 (+12)**" in md
    assert "| Contenido en página | 60/100 | 72/100 | +12 |" in md
    for heading in ("## Resueltas", "## Nuevas", "## Empeoran", "## Mejoran", "## Avisos"):
        assert heading in md
    assert md.index("## Resueltas") < md.index("## Nuevas") < md.index("## Empeoran") < md.index("## Mejoran")
    assert "- Título a (`a`): 3 -> 0 fallos" in md
    assert "No hay cambios" not in md
    md.encode("cp1252")  # se imprime en consola: debe ser representable en cp1252


def test_markdown_omits_empty_sections():
    report = make_report([make_check("a", fallos=1)], nota=70)
    md = compare_markdown(compare(report, report))
    assert "**Nota: 70/100 -> 70/100 (=)**" in md
    for heading in ("## Resueltas", "## Nuevas", "## Empeoran", "## Mejoran", "## Avisos", "## No comparables"):
        assert heading not in md
    assert "No hay cambios en las comprobaciones comparables." in md


def test_markdown_only_resolved_section():
    md = compare_markdown(compare(make_report([make_check("a", fallos=2)]), make_report([make_check("a")])))
    assert "## Resueltas" in md
    assert "## Nuevas" not in md
    assert "## Empeoran" not in md
    assert "## Mejoran" not in md


def test_markdown_limits_url_lists():
    urls = [f"https://e.com/{i:02d}" for i in range(8)]
    previous = make_report([make_check("a", fallos=8, urls=urls)])
    md = compare_markdown(compare(previous, make_report([make_check("a", fallos=0)])))
    assert "https://e.com/04" in md
    assert "https://e.com/05" not in md
    assert "... y 3 más" in md


def test_markdown_score_drop_has_minus_sign():
    md = compare_markdown(compare(make_report([], nota=80), make_report([], nota=71)))
    assert "80/100 -> 71/100 (-9)" in md
