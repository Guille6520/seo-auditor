"""Línea de comandos: seo-auditor audit <url> y seo-auditor compare <antes> <después>."""

import argparse
import json
import sys
from pathlib import Path

from .checks import run_checks
from .crawler import crawl
from .history import compare, compare_markdown
from .report import build_report, to_markdown
from .report_html import to_html


def _parser() -> argparse.ArgumentParser:
    """Define los argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(prog="seo-auditor", description="Auditor SEO sencillo.")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="Rastrea un sitio y genera el informe")
    audit.add_argument("url")
    audit.add_argument("--max-pages", type=int, default=50, help="páginas máximas (50)")
    audit.add_argument("--max-depth", type=int, default=3, help="profundidad máxima (3)")
    audit.add_argument("--delay", type=float, default=0.2, help="segundos entre peticiones (0.2)")
    audit.add_argument("--out", default="reports", help="carpeta de salida (reports)")
    audit.add_argument("--fail-under", type=int, default=0,
                       help="salir con código 2 si la nota es menor que este valor")
    audit.add_argument("--allow-private", action="store_true",
                       help="permitir IPs privadas/locales (solo para pruebas)")
    comp = sub.add_parser("compare", help="Compara dos informe.json (antes y después)")
    comp.add_argument("previous", help="informe.json anterior")
    comp.add_argument("current", help="informe.json actual")
    comp.add_argument("--json", action="store_true", help="salida en JSON en vez de Markdown")
    return parser


def _audit(args: argparse.Namespace) -> int:
    """Ejecuta una auditoría y escribe los informes JSON, Markdown y HTML."""
    url = args.url if "://" in args.url else f"https://{args.url}"
    try:
        result = crawl(url, max_pages=args.max_pages, max_depth=args.max_depth,
                       delay=args.delay, allow_private=args.allow_private)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    report = build_report(result, run_checks(result))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "informe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "informe.md").write_text(to_markdown(report), encoding="utf-8")
    (out / "informe.html").write_text(to_html(report), encoding="utf-8")

    nota = report["nota"]
    print(f"Nota: {'n/d' if nota is None else nota}/100 - {report['paginas_rastreadas']} páginas - "
          f"informes en {out} (informe.html, informe.md, informe.json)")
    if nota is not None and nota < args.fail_under:
        print(f"La nota {nota} es menor que el mínimo {args.fail_under}", file=sys.stderr)
        return 2
    return 0


def _compare(args: argparse.Namespace) -> int:
    """Compara dos informes y muestra qué ha cambiado."""
    try:
        previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))
        current = json.loads(Path(args.current).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Error: no se pudo leer un informe: {exc}", file=sys.stderr)
        return 1
    diff = compare(previous, current)
    print(json.dumps(diff, ensure_ascii=False, indent=2) if args.json else compare_markdown(diff))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada. Devuelve el código de salida: 0 bien, 1 error, 2 nota por debajo del mínimo."""
    # En consolas de Windows con codificaciones antiguas, un carácter no representable
    # no debe abortar el programa: se sustituye.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = _parser().parse_args(argv)
    return _compare(args) if args.command == "compare" else _audit(args)


if __name__ == "__main__":
    sys.exit(main())
