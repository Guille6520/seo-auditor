"""Intérprete de robots.txt según RFC 9309: comodines * y $, y gana la regla más larga.

Se usa en lugar de urllib.robotparser, que aplica la primera regla que coincide y
no entiende comodines, lo que da resultados distintos a los de los buscadores.
"""

import re
from urllib.parse import urlsplit


def _pattern(rule: str) -> re.Pattern:
    """Convierte una ruta de robots.txt (con * y $ final) en una expresión regular."""
    anchored = rule.endswith("$")
    body = rule[:-1] if anchored else rule
    regex = ".*".join(re.escape(part) for part in body.split("*"))
    return re.compile(regex + ("$" if anchored else ""))


class Robots:
    """Reglas de un robots.txt ya analizado."""

    def __init__(self, text: str = ""):
        self.sitemaps: list[str] = []
        # agente (minúsculas) -> lista de (permitido, ruta, patrón)
        self.groups: dict[str, list[tuple[bool, str, re.Pattern]]] = {}
        agents: list[str] = []
        in_rules = False
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "sitemap":
                if value:
                    self.sitemaps.append(value)
            elif key == "user-agent":
                if in_rules:  # empieza un grupo nuevo
                    agents, in_rules = [], False
                agents.append(value.lower())
                self.groups.setdefault(value.lower(), [])
            elif key in ("allow", "disallow"):
                in_rules = True
                if value:  # "Disallow:" vacío no prohíbe nada
                    for agent in agents:
                        self.groups[agent].append((key == "allow", value, _pattern(value)))

    def _rules(self, agent: str) -> list[tuple[bool, str, re.Pattern]]:
        """Reglas del grupo más específico para el agente; si no hay, las de '*'."""
        agent = agent.lower()
        matches = [name for name in self.groups if name != "*" and name in agent]
        if matches:
            return self.groups[max(matches, key=len)]
        return self.groups.get("*", [])

    def can_fetch(self, agent: str, url: str) -> bool:
        """True si el agente puede pedir la URL (o ruta). Gana la regla más larga; a igualdad, Allow."""
        parts = urlsplit(url)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        if path == "/robots.txt":
            return True
        best_len, allowed = -1, True
        for allow, rule, pattern in self._rules(agent):
            if pattern.match(path) and (len(rule) > best_len or (len(rule) == best_len and allow)):
                best_len, allowed = len(rule), allow
        return allowed
