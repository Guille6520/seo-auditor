# Cómo se calcula la nota

```
nota = redondeo( 100 × Σ(peso × puntuación) / Σ(peso) )
```

La suma recorre solo las comprobaciones **evaluables** (`evaluadas > 0`) y con **peso > 0**. La puntuación de una comprobación es `1 − fallos / evaluadas`. La nota por categoría usa la misma fórmula con las comprobaciones de esa categoría. Con las mismas observaciones, la nota es idéntica; no interviene ningún modelo de lenguaje. La versión de la fórmula (`SCORE_VERSION`) va en el JSON para poder comparar informes entre versiones.

Las comprobaciones con peso 0 son **informativas**: salen en el informe pero no puntúan. Una comprobación no evaluable (por ejemplo HSTS en un sitio sin HTTPS) aparece en *No evaluadas* y no cuenta ni a favor ni en contra.

Severidad: peso ≥ 3 alta, ≥ 2 media, > 0 baja, 0 informativa. Las prioridades del informe se ordenan por `peso × (1 − puntuación)`.

## Comprobaciones

| Id | Categoría | Peso | Qué mide |
|---|---|---|---|
| `status_ok` | indexación | 3 | Páginas rastreadas con 4xx/5xx o sin respuesta |
| `broken_links` | indexación | 3 | Enlaces internos a páginas rotas |
| `https` | indexación | 3 | La URL final del sitio es HTTPS |
| `redirect_chain` | indexación | 2 | URLs con más de una redirección |
| `noindex` | indexación | 2 | `noindex` o `none` en meta robots (o `googlebot`) o en `X-Robots-Tag` |
| `canonical_present` | indexación | 2 | Páginas sin canonical |
| `sitemap_xml` | indexación | 2 | Existe un sitemap XML |
| `canonical_other` | indexación | 1 | Canonical que apunta a otra URL |
| `robots_txt` | indexación | 1 | Existe `robots.txt` |
| `orphan_pages` | indexación | 1 | URLs del sitemap que ninguna otra página rastreada enlaza (solo si el rastreo cubrió todo el sitio: sin corte por límite de páginas ni de profundidad) |
| `title_present` | onpage | 3 | Páginas sin `<title>` |
| `title_unique` | onpage | 2 | Títulos repetidos |
| `meta_description_present` | onpage | 2 | Sin meta description |
| `h1_single` | onpage | 2 | Páginas sin exactamente un H1 |
| `thin_content` | onpage | 2 | Menos de 150 palabras |
| `viewport` | onpage | 2 | Falta meta viewport |
| `title_length` | onpage | 1 | Fuera de 30–60 caracteres (orientativo) |
| `meta_description_length` | onpage | 1 | Fuera de 70–160 caracteres (orientativo) |
| `meta_description_unique` | onpage | 1 | Descripciones repetidas |
| `img_alt` | onpage | 1 | Imágenes sin atributo `alt` |
| `lang_attr` | onpage | 1 | Falta `lang` en `<html>` |
| `jsonld_valid` | schema | 2 | Bloques JSON-LD que no son JSON válido |
| `jsonld_home` | schema | 1 | La portada no tiene JSON-LD |
| `hsts` | rendimiento | 1 | Falta `Strict-Transport-Security` (solo HTTPS) |
| `ai_crawlers` | ia | 1 | Agentes de IA (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot, Applebot-Extended) bloqueados en robots.txt |
| `response_time` | rendimiento | 0 | HTML que tarda más de 1,5 s (informativo, depende de la red) |
| `llms_txt` | ia | 0 | Existe `llms.txt` (informativo) |

## Qué significan y qué no

- **Los pesos y umbrales son criterio propio**, no un estándar. Los rangos de longitud de título y descripción son orientativos: los buscadores recortan por píxeles, no por caracteres.
- `ai_crawlers` penaliza el bloqueo aunque sea intencionado; el consejo del informe lo indica. Si no quieres que puntúe, pon su peso a 0.
- `llms_txt` no puntúa porque no hay evidencia de que mejore la aparición en respuestas de IAs.
- `jsonld_valid` solo comprueba sintaxis JSON, no que cumpla schema.org ni que sea elegible para resultados enriquecidos.
- La nota es un resumen de higiene técnica básica, no una predicción de posiciones.
- `robots.txt` se interpreta con un analizador propio que sigue RFC 9309 (comodines `*` y `$`, gana la regla más larga), igual para decidir qué se rastrea que para `ai_crawlers`.
- Varias URLs que redirigen al mismo documento cuentan como una sola página, y una página interna que redirige a otro dominio no se analiza como propia.
