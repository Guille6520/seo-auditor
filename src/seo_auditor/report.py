"""Informes en JSON y Markdown (español)."""

from datetime import UTC, datetime

from . import __version__
from .checks import CheckResult
from .crawler import CrawlResult
from .scoring import SCORE_VERSION, category_scores, overall_score, priority

CATEGORY_NAMES = {
    "indexacion": "Rastreo e indexación",
    "onpage": "Contenido en página",
    "schema": "Datos estructurados",
    "rendimiento": "Rendimiento y seguridad básicos",
    "ia": "Visibilidad en IAs",
}
MD_EXAMPLES = 5


def build_report(crawl: CrawlResult, results: list[CheckResult]) -> dict:
    """Construye el informe como diccionario serializable a JSON, ordenado por prioridad."""
    ordered = sorted(results, key=lambda r: (-priority(r), r.check.id))
    return {
        "version_auditor": __version__,
        "version_nota": SCORE_VERSION,
        "generado": datetime.now(UTC).isoformat(timespec="seconds"),
        "url": crawl.start_url,
        "url_final": crawl.final_start_url,
        "paginas_rastreadas": len(crawl.pages),
        "rastreo_incompleto": crawl.truncated,
        "bloqueadas_por_robots": len(crawl.blocked_by_robots),
        "nota": overall_score(results),
        "categorias": category_scores(results),
        "comprobaciones": [
            {
                "id": r.check.id,
                "categoria": r.check.category,
                "titulo": r.check.title,
                "peso": r.check.weight,
                "severidad": r.check.severity,
                "evaluadas": r.applicable,
                "fallos": len(r.failures),
                "puntuacion": None if r.score is None else round(r.score, 3),
                "consejo": r.check.advice,
                "ejemplos": [{"url": f.url, "detalle": f.detail} for f in r.failures],
            }
            for r in ordered
        ],
    }


def _fmt(score: int | None) -> str:
    """Formatea una nota como 'NN/100', o 'n/d' si no se pudo calcular."""
    return "n/d" if score is None else f"{score}/100"


def to_markdown(report: dict) -> str:
    """Convierte el diccionario del informe en un documento Markdown legible."""
    lines = [
        f"# Informe SEO: {report['url_final']}",
        "",
        f"**Nota: {_fmt(report['nota'])}** · {report['paginas_rastreadas']} páginas rastreadas · "
        f"generado {report['generado']}",
        "",
    ]
    if report["rastreo_incompleto"]:
        lines += ["> El rastreo no cubrió todo el sitio por el límite de páginas o de profundidad: hay páginas "
                  "sin analizar y algunas comprobaciones (p. ej. páginas huérfanas) no se evaluaron.", ""]
    if report["bloqueadas_por_robots"]:
        lines += [f"> {report['bloqueadas_por_robots']} URL(s) no se rastrearon porque robots.txt lo impide.", ""]

    lines += ["## Por categoría", "", "| Categoría | Nota |", "|---|---|"]
    for cat, score in report["categorias"].items():
        lines.append(f"| {CATEGORY_NAMES.get(cat, cat)} | {_fmt(score)} |")

    failing = [c for c in report["comprobaciones"] if c["fallos"]]
    lines += ["", "## Prioridades", ""]
    if not failing:
        lines.append("No se encontraron problemas.")
    for c in failing:
        lines += [
            f"### {c['titulo']}",
            "",
            f"Severidad **{c['severidad']}** · {c['fallos']} de {c['evaluadas']} afectadas · `{c['id']}`",
            "",
            c["consejo"],
            "",
        ]
        for ex in c["ejemplos"][:MD_EXAMPLES]:
            lines.append(f"- {ex['url']}" + (f" — {ex['detalle']}" if ex["detalle"] else ""))
        if len(c["ejemplos"]) > MD_EXAMPLES:
            lines.append(f"- ... y {len(c['ejemplos']) - MD_EXAMPLES} más (ver el JSON)")
        lines.append("")

    skipped = [c["titulo"] for c in report["comprobaciones"] if c["evaluadas"] == 0]
    if skipped:
        lines += ["## No evaluadas", ""] + [f"- {t}" for t in skipped] + [""]
    lines += ["---", "La nota se calcula en código a partir de las comprobaciones (ver docs/NOTA.md)."]
    return "\n".join(lines) + "\n"
