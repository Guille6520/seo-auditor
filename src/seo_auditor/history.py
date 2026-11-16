"""Comparación de dos informes de auditoría (antes/después)."""

from .report import CATEGORY_NAMES, MD_EXAMPLES

STATES = ("resuelta", "nueva", "empeora", "mejora", "igual", "no_comparable")
_SECTIONS = (
    ("resuelta", "Resueltas"),
    ("nueva", "Nuevas"),
    ("empeora", "Empeoran"),
    ("mejora", "Mejoran"),
    ("no_comparable", "No comparables"),
)


def _delta(before: int | None, after: int | None) -> int | None:
    """Diferencia después - antes, o None si falta alguno de los dos valores."""
    return None if before is None or after is None else after - before


def _evaluated(check: dict | None) -> bool:
    """Indica si la comprobación existe en el informe y se evaluó sobre alguna página."""
    return check is not None and (check.get("evaluadas") or 0) > 0


def _urls(check: dict | None) -> set[str]:
    """Conjunto de URLs de los ejemplos de una comprobación."""
    return {ex["url"] for ex in (check or {}).get("ejemplos") or [] if ex.get("url")}


def _state(prev: dict | None, cur: dict | None) -> str:
    """Clasifica la evolución de una comprobación entre los dos informes."""
    if not _evaluated(cur):
        return "no_comparable"
    after = cur.get("fallos") or 0
    if not _evaluated(prev):
        return "nueva" if after else "no_comparable"
    before = prev.get("fallos") or 0
    if before and not after:
        return "resuelta"
    if after and not before:
        return "nueva"
    if after < before:
        return "mejora"
    if after > before:
        return "empeora"
    return "igual"


def _compare_check(check_id: str, prev: dict | None, cur: dict | None) -> dict:
    """Compara una comprobación; prev o cur es None si no existe en ese informe."""
    ref = cur or prev
    state = _state(prev, cur)
    before_urls, after_urls = _urls(prev), _urls(cur)
    return {
        "id": check_id,
        "titulo": ref.get("titulo", check_id),
        "categoria": ref.get("categoria"),
        "severidad": ref.get("severidad"),
        "estado": state,
        "presente_anterior": prev is not None,
        "presente_actual": cur is not None,
        "evaluadas_anterior": None if prev is None else prev.get("evaluadas") or 0,
        "evaluadas_actual": None if cur is None else cur.get("evaluadas") or 0,
        "fallos_anterior": None if prev is None else prev.get("fallos") or 0,
        "fallos_actual": None if cur is None else cur.get("fallos") or 0,
        "urls_corregidas": sorted(before_urls - after_urls) if _evaluated(cur) else [],
        "urls_nuevas": sorted(after_urls - before_urls),
    }


def _warnings(previous: dict, current: dict, checks: list[dict]) -> list[str]:
    """Avisos de que los dos informes pueden no ser comparables de forma homogénea."""
    out = []
    v_prev, v_cur = previous.get("version_nota"), current.get("version_nota")
    if v_prev != v_cur:
        out.append(f"La versión de la nota difiere ({v_prev} -> {v_cur}): las notas no son comparables.")
    u_prev, u_cur = previous.get("url_final"), current.get("url_final")
    if u_prev != u_cur:
        out.append(f"Los informes son de URLs distintas ({u_prev} -> {u_cur}).")
    for label, report in (("anterior", previous), ("actual", current)):
        if report.get("rastreo_incompleto"):
            out.append(f"El rastreo del informe {label} fue incompleto: hay páginas sin analizar.")
    p_prev, p_cur = previous.get("paginas_rastreadas"), current.get("paginas_rastreadas")
    if p_prev != p_cur:
        out.append(f"El número de páginas rastreadas difiere ({p_prev} -> {p_cur}): "
                   "los recuentos de fallos pueden no ser homogéneos.")
    only_prev = [c["id"] for c in checks if not c["presente_actual"]]
    only_cur = [c["id"] for c in checks if not c["presente_anterior"]]
    if only_prev:
        out.append("Comprobaciones solo en el informe anterior: " + ", ".join(only_prev) + ".")
    if only_cur:
        out.append("Comprobaciones solo en el informe actual: " + ", ".join(only_cur) + ".")
    return out


def compare(previous: dict, current: dict) -> dict:
    """Compara dos informes y devuelve las diferencias como diccionario serializable a JSON."""
    prev_checks = {c["id"]: c for c in previous.get("comprobaciones") or []}
    cur_checks = {c["id"]: c for c in current.get("comprobaciones") or []}
    checks = [
        _compare_check(check_id, prev_checks.get(check_id), cur_checks.get(check_id))
        for check_id in sorted(prev_checks.keys() | cur_checks.keys())
    ]
    prev_cats, cur_cats = previous.get("categorias") or {}, current.get("categorias") or {}
    return {
        "anterior": {key: previous.get(key) for key in ("url_final", "generado", "paginas_rastreadas")},
        "actual": {key: current.get(key) for key in ("url_final", "generado", "paginas_rastreadas")},
        "nota": {
            "anterior": previous.get("nota"),
            "actual": current.get("nota"),
            "diferencia": _delta(previous.get("nota"), current.get("nota")),
        },
        "categorias": [
            {
                "categoria": cat,
                "anterior": prev_cats.get(cat),
                "actual": cur_cats.get(cat),
                "diferencia": _delta(prev_cats.get(cat), cur_cats.get(cat)),
            }
            for cat in sorted(prev_cats.keys() | cur_cats.keys())
        ],
        "resumen": {state: sum(c["estado"] == state for c in checks) for state in STATES},
        "comprobaciones": checks,
        "avisos": _warnings(previous, current, checks),
    }


def _fmt(score: int | None) -> str:
    """Formatea una nota como 'NN/100', o 'n/d' si no se pudo calcular."""
    return "n/d" if score is None else f"{score}/100"


def _fmt_delta(delta: int | None) -> str:
    """Formatea una diferencia con signo, '=' si no cambia o 'n/d' si no se puede calcular."""
    if delta is None:
        return "n/d"
    return "=" if delta == 0 else f"{delta:+d}"


def _fmt_count(count: int | None) -> str:
    """Formatea un recuento de fallos, o 'n/d' si la comprobación no existe en ese informe."""
    return "n/d" if count is None else str(count)


def _url_list(label: str, urls: list[str]) -> list[str]:
    """Líneas Markdown con un máximo de MD_EXAMPLES URLs y el recuento de las restantes."""
    if not urls:
        return []
    lines = [f"  - {label}:"] + [f"    - {url}" for url in urls[:MD_EXAMPLES]]
    if len(urls) > MD_EXAMPLES:
        lines.append(f"    - ... y {len(urls) - MD_EXAMPLES} más")
    return lines


def compare_markdown(diff: dict) -> str:
    """Convierte el resultado de compare en un resumen Markdown legible."""
    score = diff["nota"]
    lines = [
        f"# Comparación de auditorías: {diff['actual']['url_final']}",
        "",
        f"**Nota: {_fmt(score['anterior'])} -> {_fmt(score['actual'])} ({_fmt_delta(score['diferencia'])})**",
        "",
        f"Informe anterior: {diff['anterior']['generado']} ({diff['anterior']['paginas_rastreadas']} páginas)",
        f"Informe actual: {diff['actual']['generado']} ({diff['actual']['paginas_rastreadas']} páginas)",
        "",
    ]
    if diff["avisos"]:
        lines += ["## Avisos", ""] + [f"- {text}" for text in diff["avisos"]] + [""]

    lines += ["## Por categoría", "", "| Categoría | Antes | Después | Diferencia |", "|---|---|---|---|"]
    for cat in diff["categorias"]:
        lines.append(
            f"| {CATEGORY_NAMES.get(cat['categoria'], cat['categoria'])} | {_fmt(cat['anterior'])} "
            f"| {_fmt(cat['actual'])} | {_fmt_delta(cat['diferencia'])} |"
        )
    lines.append("")

    for state, heading in _SECTIONS:
        checks = [c for c in diff["comprobaciones"] if c["estado"] == state]
        if not checks:
            continue
        lines += [f"## {heading}", ""]
        for c in checks:
            lines.append(
                f"- {c['titulo']} (`{c['id']}`): {_fmt_count(c['fallos_anterior'])} -> "
                f"{_fmt_count(c['fallos_actual'])} fallos"
            )
            lines += _url_list("Corregidas", c["urls_corregidas"])
            lines += _url_list("Nuevas", c["urls_nuevas"])
        lines.append("")

    if not any(c["estado"] not in ("igual", "no_comparable") for c in diff["comprobaciones"]):
        lines += ["No hay cambios en las comprobaciones comparables.", ""]
    return "\n".join(lines)
