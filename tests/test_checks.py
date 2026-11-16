import json

from conftest import ok, page, sample_site, with_base
from seo_auditor.checks import run_checks
from seo_auditor.cli import main
from seo_auditor.crawler import crawl
from seo_auditor.report import build_report, to_markdown
from seo_auditor.scoring import overall_score


def audit(serve, routes=None, **kwargs):
    routes = routes if routes is not None else sample_site()
    base = serve(routes)
    with_base(routes, base)
    result = crawl(base + "/", delay=0, allow_private=True, **kwargs)
    return base, result, {r.check.id: r for r in run_checks(result)}


def failing_urls(res, base):
    return sorted(f.url.removeprefix(base) for f in res.failures)


def test_crawl_finds_pages_and_follows_robots_and_sitemap(serve):
    base, result, _ = audit(serve)
    paths = {p.fetch.url.removeprefix(base) for p in result.pages.values()}
    assert {"/", "/buena", "/sin-titulo", "/rota", "/dup1", "/dup2", "/huerfana"} <= paths
    assert result.sitemap_found and result.robots_status == 200
    assert not result.truncated


def test_status_and_broken_links(serve):
    base, _, res = audit(serve)
    assert failing_urls(res["status_ok"], base) == ["/rota"]
    assert failing_urls(res["broken_links"], base) == ["/rota"]
    assert "enlazada desde" in res["broken_links"].failures[0].detail


def test_redirect_single_hop_is_not_a_chain(serve):
    _, _, res = audit(serve)
    assert res["redirect_chain"].failures == []


def test_redirect_chain_detected(serve):
    routes = sample_site()
    routes["/viejo"] = (301, {"Location": "/intermedio"}, "")
    routes["/intermedio"] = (301, {"Location": "/buena"}, "")
    base, _, res = audit(serve, routes)
    assert failing_urls(res["redirect_chain"], base) == ["/viejo"]


def test_on_page_checks(serve):
    base, _, res = audit(serve)
    assert failing_urls(res["title_present"], base) == ["/sin-titulo"]
    assert failing_urls(res["meta_description_present"], base) == ["/sin-titulo"]
    assert failing_urls(res["h1_single"], base) == ["/sin-titulo"]
    assert failing_urls(res["thin_content"], base) == ["/sin-titulo"]
    assert failing_urls(res["img_alt"], base) == ["/sin-titulo"]
    assert failing_urls(res["title_unique"], base) == ["/dup1", "/dup2"]
    assert res["meta_description_unique"].failures == []


def test_orphan_page_only_in_sitemap(serve):
    base, _, res = audit(serve)
    assert failing_urls(res["orphan_pages"], base) == ["/huerfana"]


def test_orphans_not_evaluated_when_crawl_truncated(serve):
    _, result, res = audit(serve, max_pages=2)
    assert result.truncated
    assert res["orphan_pages"].applicable == 0


def test_ai_crawlers_and_llms(serve):
    _, _, res = audit(serve)
    assert [f.detail for f in res["ai_crawlers"].failures] == ["GPTBot no puede acceder a /"]
    assert len(res["llms_txt"].failures) == 1
    assert res["llms_txt"].check.severity == "info"


def test_jsonld_home_present_and_https_flagged_on_http(serve):
    _, _, res = audit(serve)
    assert res["jsonld_home"].failures == []
    assert len(res["https"].failures) == 1  # el servidor de pruebas es http


def test_hsts_not_evaluable_over_http(serve):
    _, _, res = audit(serve)
    assert res["hsts"].applicable == 0


def test_noindex_via_meta_and_header(serve):
    routes = sample_site()
    routes["/buena"] = (200, {"X-Robots-Tag": "noindex"}, page(title="Página buena con título largo suficiente aquí"))
    routes["/dup1"] = ok(page(head_extra='<meta name="robots" content="noindex">', title="Dup uno con título largo suficiente aquí"))
    base, _, res = audit(serve, routes)
    assert failing_urls(res["noindex"], base) == ["/buena", "/dup1"]


def test_score_is_deterministic_and_between_0_and_100(serve):
    _, result, _ = audit(serve)
    first = overall_score(run_checks(result))
    second = overall_score(run_checks(result))
    assert first == second
    assert 0 <= first <= 100


def test_informative_checks_do_not_change_score(serve):
    _, result, _ = audit(serve)
    results = run_checks(result)
    baseline = overall_score(results)
    for r in results:
        if r.check.weight == 0:
            r.failures = []
    assert overall_score(results) == baseline


def test_report_json_and_markdown(serve):
    _, result, _ = audit(serve)
    report = build_report(result, run_checks(result))
    json.dumps(report)
    assert report["comprobaciones"][0]["fallos"] > 0  # ordenado por prioridad
    md = to_markdown(report)
    assert md.startswith("# Informe SEO:") and "## Prioridades" in md and "## No evaluadas" in md


def test_cli_writes_reports_and_fail_under(serve, tmp_path):
    routes = sample_site()
    base = serve(routes)
    with_base(routes, base)
    args = ["audit", base + "/", "--allow-private", "--delay", "0", "--out", str(tmp_path)]
    assert main(args) == 0
    assert (tmp_path / "informe.json").exists() and (tmp_path / "informe.md").exists()
    assert main(args + ["--fail-under", "101"]) == 2


def test_cli_unreachable_site_returns_error(tmp_path):
    code = main(["audit", "http://127.0.0.1:1/", "--allow-private", "--out", str(tmp_path)])
    assert code == 1


def test_private_target_blocked_without_flag(tmp_path, capsys):
    assert main(["audit", "http://127.0.0.1:1/", "--out", str(tmp_path)]) == 1
    assert "bloqueada" in capsys.readouterr().err  # bloqueo de seguridad, no fallo de conexión
