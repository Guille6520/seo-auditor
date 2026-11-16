"""Informe HTML visual y autocontenido (español)."""

from datetime import datetime, timedelta
from html import escape

from .report import CATEGORY_NAMES

GAUGE_RADIUS = 54
GAUGE_LENGTH = 2 * 3.141592653589793 * GAUGE_RADIUS
SEVERITY_CLASSES = {"alta": "sev-alta", "media": "sev-media", "baja": "sev-baja"}

CSS = """
:root {
  --bg: #f5f6f8; --surface: #ffffff; --text: #1c2330; --muted: #5d6778; --border: #dfe3ea;
  --track: #e6e9ef; --good: #1f8a4c; --mid: #b7791f; --bad: #c0392b; --none: #8a93a3;
  --link: #1d5fbf; --warn-bg: #fff7e0; --warn-border: #e2b93b; --code-bg: #eef0f4;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12151b; --surface: #1b2029; --text: #e6e9ef; --muted: #9aa4b5; --border: #2c3441;
    --track: #2c3441; --good: #4cc27f; --mid: #e0a84a; --bad: #ee6b5c; --none: #7c8698;
    --link: #7fb0f5; --warn-bg: #2e2812; --warn-border: #8a6d1c; --code-bg: #252c38;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--text); line-height: 1.5;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
main { max-width: 920px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.5rem; margin: 0 0 4px; }
h2 { font-size: 1.15rem; margin: 32px 0 12px; }
h3 { font-size: 1rem; margin: 0; }
p { margin: 0; }
a { color: var(--link); }
code { background: var(--code-bg); border-radius: 4px; padding: 1px 5px; font-size: 0.85em; }
.muted { color: var(--muted); }
.break { overflow-wrap: anywhere; word-break: break-word; }
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px;
}
.meta { color: var(--muted); font-size: 0.9rem; margin-top: 4px; }
.summary { display: flex; flex-wrap: wrap; gap: 24px; align-items: center; margin-top: 20px; }
.gauge { flex: 0 0 auto; width: 150px; height: 150px; margin: 0 auto; }
.gauge-track { fill: none; stroke: var(--track); stroke-width: 12; }
.gauge-value { fill: none; stroke-width: 12; stroke-linecap: round; }
.gauge-number { font-size: 34px; font-weight: 700; fill: var(--text); }
.gauge-unit { font-size: 12px; fill: var(--muted); }
.categories { flex: 1 1 320px; min-width: 0; list-style: none; margin: 0; padding: 0; }
.categories li { margin-bottom: 12px; }
.categories li:last-child { margin-bottom: 0; }
.cat-head { display: flex; justify-content: space-between; gap: 12px; font-size: 0.92rem; }
.cat-score { font-variant-numeric: tabular-nums; white-space: nowrap; font-weight: 600; }
.bar { height: 8px; background: var(--track); border-radius: 4px; overflow: hidden; margin-top: 4px; }
.bar span { display: block; height: 100%; border-radius: 4px; }
.good { stroke: var(--good); } .mid { stroke: var(--mid); }
.bad { stroke: var(--bad); } .none { stroke: var(--none); }
.bar .good { background: var(--good); } .bar .mid { background: var(--mid); }
.bar .bad { background: var(--bad); } .bar .none { background: var(--none); }
.notice {
  background: var(--warn-bg); border: 1px solid var(--warn-border); border-radius: 8px;
  padding: 10px 14px; margin-top: 12px; font-size: 0.93rem;
}
.check { margin-bottom: 12px; }
.check-head { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.check-meta { color: var(--muted); font-size: 0.88rem; margin: 6px 0 8px; }
.badge {
  display: inline-block; border: 1px solid currentColor; border-radius: 999px; padding: 0 9px;
  font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
  white-space: nowrap;
}
.sev-alta { color: var(--bad); } .sev-media { color: var(--mid); }
.sev-baja { color: var(--link); } .sev-info { color: var(--none); }
details { margin-top: 10px; }
summary { cursor: pointer; color: var(--link); font-size: 0.9rem; }
.examples { margin: 8px 0 0; padding-left: 20px; font-size: 0.88rem; }
.examples li { margin-bottom: 4px; }
.plain { list-style: none; margin: 0; padding: 0; }
.plain li {
  display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 12px;
  padding: 7px 0; border-bottom: 1px solid var(--border); font-size: 0.93rem;
}
.plain li:last-child { border-bottom: 0; }
footer { margin-top: 32px; color: var(--muted); font-size: 0.82rem; }
@media (max-width: 520px) {
  main { padding: 16px 12px 32px; }
  h1 { font-size: 1.25rem; }
  .gauge { width: 130px; height: 130px; }
}
@media print {
  :root {
    --bg: #ffffff; --surface: #ffffff; --text: #000000; --muted: #444444; --border: #bbbbbb;
    --track: #dddddd; --good: #1f8a4c; --mid: #946200; --bad: #b02a1d; --none: #666666;
    --link: #000000; --warn-bg: #ffffff; --warn-border: #888888; --code-bg: #eeeeee;
  }
  body { font-size: 11pt; }
  main { max-width: none; padding: 0; }
  .card, .notice { break-inside: avoid; }
  h2 { break-after: avoid; }
  .bar span, .gauge-value { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  details::details-content { content-visibility: visible; display: block; }
}
"""


def _esc(value: object) -> str:
    """Escapa cualquier valor para interpolarlo en texto o atributos HTML."""
    return escape("" if value is None else str(value), quote=True)


def _tone(score: int | None) -> str:
    """Devuelve la clase de color según el rango de la nota."""
    if score is None:
        return "none"
    if score >= 80:
        return "good"
    return "mid" if score >= 50 else "bad"


def _fmt(score: int | None) -> str:
    """Formatea una nota como 'NN/100', o 'n/d' si no se pudo calcular."""
    return "n/d" if score is None else f"{_esc(score)}/100"


def _clamp(score: int | None) -> float:
    """Limita la nota al rango 0-100 para dibujarla; None cuenta como 0."""
    try:
        return max(0.0, min(100.0, float(score)))
    except (TypeError, ValueError):
        return 0.0


def _fmt_date(value: object) -> str:
    """Muestra una fecha ISO de forma legible, o el valor original si no lo es."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value or "")
    if parsed.utcoffset() == timedelta(0):
        return parsed.strftime("%d/%m/%Y %H:%M UTC")
    return parsed.strftime("%d/%m/%Y %H:%M")


def _url(value: object) -> str:
    """Devuelve la URL como enlace solo si es http(s); en otro caso, como texto."""
    text = "" if value is None else str(value)
    if text.lower().startswith(("http://", "https://")):
        return f'<a class="break" href="{_esc(text)}" rel="noopener noreferrer nofollow">{_esc(text)}</a>'
    return f'<span class="break">{_esc(text)}</span>'


def _gauge(score: int | None) -> str:
    """Dibuja el indicador circular de la nota global como SVG en línea."""
    filled = GAUGE_LENGTH * _clamp(score) / 100
    label = "n/d" if score is None else _esc(score)
    aria = "Nota global: n/d" if score is None else f"Nota global: {_esc(score)} de 100"
    unit = "" if score is None else '<text class="gauge-unit" x="70" y="92" text-anchor="middle">de 100</text>'
    return (
        f'<svg class="gauge" viewBox="0 0 140 140" role="img" aria-label="{aria}">'
        f'<circle class="gauge-track" cx="70" cy="70" r="{GAUGE_RADIUS}"/>'
        f'<circle class="gauge-value {_tone(score)}" cx="70" cy="70" r="{GAUGE_RADIUS}" '
        f'stroke-dasharray="{filled:.1f} {GAUGE_LENGTH:.1f}" transform="rotate(-90 70 70)"/>'
        f'<text class="gauge-number" x="70" y="76" text-anchor="middle">{label}</text>'
        f"{unit}</svg>"
    )


def _categories(scores: dict) -> str:
    """Genera las barras de nota por categoría."""
    items = []
    for cat, score in scores.items():
        items.append(
            f'<li><div class="cat-head"><span>{_esc(CATEGORY_NAMES.get(cat, cat))}</span>'
            f'<span class="cat-score">{_fmt(score)}</span></div>'
            f'<div class="bar"><span class="{_tone(score)}" style="width:{_clamp(score):.0f}%"></span></div></li>'
        )
    return f'<ul class="categories">{"".join(items)}</ul>'


def _notices(report: dict) -> str:
    """Genera los avisos de rastreo incompleto y de URLs bloqueadas por robots.txt."""
    out = []
    if report.get("rastreo_incompleto"):
        out.append(
            '<p class="notice"><strong>Rastreo incompleto.</strong> El rastreo no cubrió todo el sitio '
            "por el límite de páginas o de profundidad: hay páginas sin analizar y algunas comprobaciones "
            "(p. ej. páginas huérfanas) no se evaluaron.</p>"
        )
    blocked = report.get("bloqueadas_por_robots")
    if blocked:
        out.append(
            f'<p class="notice"><strong>Bloqueadas por robots.txt.</strong> {_esc(blocked)} URL(s) no '
            "se rastrearon porque robots.txt lo impide.</p>"
        )
    return "".join(out)


def _examples(examples: list[dict]) -> str:
    """Genera el desplegable con todos los ejemplos de una comprobación."""
    if not examples:
        return ""
    rows = []
    for ex in examples:
        detail = ex.get("detalle")
        suffix = f' <span class="muted break">— {_esc(detail)}</span>' if detail else ""
        rows.append(f"<li>{_url(ex.get('url'))}{suffix}</li>")
    return (
        f"<details><summary>Ver ejemplos ({len(examples)})</summary>"
        f'<ul class="examples">{"".join(rows)}</ul></details>'
    )


def _priority(check: dict) -> str:
    """Genera la tarjeta de una comprobación con fallos."""
    severity = str(check.get("severidad") or "")
    badge = SEVERITY_CLASSES.get(severity, "sev-info")
    return (
        '<article class="card check"><div class="check-head">'
        f'<span class="badge {badge}">{_esc(severity)}</span>'
        f'<h3 class="break">{_esc(check.get("titulo"))}</h3></div>'
        f'<p class="check-meta">{_esc(check.get("fallos"))} de {_esc(check.get("evaluadas"))} afectadas'
        f' · {_esc(CATEGORY_NAMES.get(check.get("categoria"), check.get("categoria")))}'
        f' · <code>{_esc(check.get("id"))}</code></p>'
        f'<p class="break">{_esc(check.get("consejo"))}</p>'
        f'{_examples(check.get("ejemplos") or [])}</article>'
    )


def _plain_list(checks: list[dict], with_count: bool) -> str:
    """Genera una lista sencilla de comprobaciones (superadas o no evaluadas)."""
    rows = []
    for c in checks:
        count = f'<span class="muted">{_esc(c.get("evaluadas"))} evaluadas</span>' if with_count else ""
        rows.append(f'<li><span class="break">{_esc(c.get("titulo"))}</span>{count}</li>')
    return f'<div class="card"><ul class="plain">{"".join(rows)}</ul></div>'


def to_html(report: dict) -> str:
    """Convierte el diccionario del informe en un documento HTML completo y autocontenido."""
    checks = report.get("comprobaciones") or []
    failing = [c for c in checks if c.get("fallos")]
    passed = [c for c in checks if not c.get("fallos") and (c.get("evaluadas") or 0) > 0]
    skipped = [c for c in checks if c.get("evaluadas") == 0]
    target = report.get("url_final") or report.get("url")
    score = report.get("nota")

    parts = [
        "<!DOCTYPE html>",
        '<html lang="es">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">",
        '<meta name="referrer" content="no-referrer">',
        f"<title>Informe SEO: {_esc(target)}</title>",
        f"<style>{CSS}</style>",
        "</head>",
        "<body>",
        "<main>",
        "<header>",
        "<h1>Informe SEO</h1>",
        f"<p>{_url(target)}</p>",
        f'<p class="meta">Generado: {_esc(_fmt_date(report.get("generado")))} · '
        f'{_esc(report.get("paginas_rastreadas"))} páginas rastreadas</p>',
        "</header>",
        f'<section class="card summary" aria-label="Resumen">{_gauge(score)}'
        f'{_categories(report.get("categorias") or {})}</section>',
        _notices(report),
        '<section><h2>Prioridades</h2>',
    ]
    if failing:
        parts += [_priority(c) for c in failing]
    else:
        parts.append('<p class="card">No se encontraron problemas.</p>')
    parts.append("</section>")
    if passed:
        parts.append(
            f"<section><h2>Comprobaciones superadas ({len(passed)})</h2>{_plain_list(passed, True)}</section>"
        )
    if skipped:
        parts.append(f"<section><h2>No evaluadas ({len(skipped)})</h2>{_plain_list(skipped, False)}</section>")
    parts += [
        "<footer><p>La nota se calcula en código a partir de las comprobaciones, sin intervención de "
        f'ningún modelo de lenguaje. Auditor v{_esc(report.get("version_auditor"))} · fórmula de nota '
        f'v{_esc(report.get("version_nota"))}.</p></footer>',
        "</main>",
        "</body>",
        "</html>",
    ]
    return "\n".join(p for p in parts if p) + "\n"
