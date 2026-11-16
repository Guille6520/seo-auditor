# Comparación de auditorías: http://127.0.0.1:8765/

**Nota: 60/100 -> 93/100 (+33)**

Informe anterior: 2026-11-15T09:45:36+00:00 (8 páginas)
Informe actual: 2026-11-15T09:45:37+00:00 (6 páginas)

## Avisos

- El número de páginas rastreadas difiere (8 -> 6): los recuentos de fallos pueden no ser homogéneos.

## Por categoría

| Categoría | Antes | Después | Diferencia |
|---|---|---|---|
| Visibilidad en IAs | 83/100 | 100/100 | +17 |
| Rastreo e indexación | 54/100 | 85/100 | +31 |
| Contenido en página | 75/100 | 100/100 | +25 |
| Rendimiento y seguridad básicos | n/d | n/d | n/d |
| Datos estructurados | 0/100 | 100/100 | +100 |

## Resueltas

- Rastreadores de IA bloqueados en robots.txt (`ai_crawlers`): 1 -> 0 fallos
  - Corregidas:
    - /robots.txt
- Enlaces internos rotos (`broken_links`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/ofertas
- Páginas sin canonical (`canonical_present`): 6 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/
    - http://127.0.0.1:8765/blog/como-conservar-el-pan
    - http://127.0.0.1:8765/contacto
    - http://127.0.0.1:8765/horarios
    - http://127.0.0.1:8765/pan-de-masa-madre
    - ... y 1 más
- Páginas sin un único H1 (`h1_single`): 2 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/contacto
    - http://127.0.0.1:8765/pan-de-masa-madre
- Imágenes sin atributo alt (`img_alt`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/productos
- La portada no tiene datos estructurados (`jsonld_home`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/
- JSON-LD con errores de sintaxis (`jsonld_valid`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/productos
- Falta el atributo lang en <html> (`lang_attr`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/contacto
- Páginas sin meta description (`meta_description_present`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/horarios
- Páginas con noindex (`noindex`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/blog/como-conservar-el-pan
- Cadenas de redirección (`redirect_chain`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/tienda
- No se encontró sitemap XML (`sitemap_xml`): 1 -> 0 fallos
  - Corregidas:
    - /sitemap.xml
- Páginas que responden con error (`status_ok`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/ofertas
- Páginas con muy poco texto (`thin_content`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/horarios
- Títulos demasiado cortos o largos (`title_length`): 2 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/pan-de-masa-madre
    - http://127.0.0.1:8765/productos
- Páginas sin <title> (`title_present`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/contacto
- Títulos duplicados (`title_unique`): 2 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/pan-de-masa-madre
    - http://127.0.0.1:8765/productos
- Falta la meta viewport (`viewport`): 1 -> 0 fallos
  - Corregidas:
    - http://127.0.0.1:8765/horarios

## No comparables

- Canonical que apunta a otra URL (`canonical_other`): 0 -> 0 fallos
- Falta la cabecera HSTS (`hsts`): 0 -> 0 fallos
- Páginas del sitemap sin enlaces internos (`orphan_pages`): 0 -> 0 fallos
