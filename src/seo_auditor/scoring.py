"""Nota 0-100 calculada en código, sin intervención de ningún modelo.

nota = 100 * suma(peso * puntuación) / suma(peso), solo sobre las comprobaciones
evaluables (aplicable > 0) y con peso > 0. Mismas observaciones, misma nota.
"""

from .checks import CheckResult

SCORE_VERSION = 1


def _weighted(results: list[CheckResult]) -> int | None:
    scored = [r for r in results if r.score is not None and r.check.weight > 0]
    total = sum(r.check.weight for r in scored)
    if not total:
        return None
    return round(100 * sum(r.check.weight * r.score for r in scored) / total)


def overall_score(results: list[CheckResult]) -> int | None:
    return _weighted(results)


def category_scores(results: list[CheckResult]) -> dict[str, int | None]:
    categories = dict.fromkeys(r.check.category for r in results)
    return {cat: _weighted([r for r in results if r.check.category == cat]) for cat in categories}


def priority(result: CheckResult) -> float:
    """Orden de prioridad: cuánto pierde la nota por este fallo (peso x proporción de fallos)."""
    if result.score is None:
        return 0.0
    return result.check.weight * (1 - result.score)
