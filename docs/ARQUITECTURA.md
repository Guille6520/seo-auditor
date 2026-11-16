# Arquitectura

```
cli.py  ->  crawler.py  ->  checks.py  ->  scoring.py  ->  report.py + report_html.py
              |  ^                                            |
            fetch.py  parser.py  safety.py                  JSON + Markdown + HTML

cli.py compare  ->  history.py  (lee dos informe.json, no usa la red)
```

| Módulo | Responsabilidad |
|---|---|
| `safety.py` | Rechaza esquemas que no sean http(s) y hosts que resuelvan a IPs no públicas (privadas, loopback, link-local, multicast, IPv4 mapeada en IPv6). |
| `fetch.py` | Una petición con redirecciones **manuales** (se valida cada salto con `safety`), tope de 5 saltos, límite de 2 MB de cuerpo, timeout y registro de la cadena de redirecciones y del tiempo. Nunca lanza: los errores quedan en `Response.error`. |
| `robots.py` | Intérprete propio de `robots.txt` según RFC 9309: comodines `*` y `$`, y gana la regla más larga (como hacen los buscadores). Sustituye a `urllib.robotparser`, que aplica la primera regla que coincide y no entiende comodines. |
| `parser.py` | Extrae de un HTML: título, meta description, H1, canonical, meta robots, lang, viewport, imágenes sin `alt`, bloques JSON-LD, palabras y enlaces. También normaliza URLs. |
| `crawler.py` | Lee `robots.txt`, sitemap (con índice de sitemaps, sin entidades XML externas ni red) y `llms.txt`; rastrea en anchura desde la portada hasta `max_pages`/`max_depth`; después completa con URLs del sitemap si queda cupo. Guarda el grafo de enlaces entrantes. |
| `checks.py` | 27 comprobaciones registradas con un decorador. Cada una es una función pura `CrawlResult -> (evaluadas, fallos)`. |
| `scoring.py` | Nota global y por categoría, y orden de prioridades. |
| `report.py` | Genera el diccionario JSON y el Markdown en español. |
| `report_html.py` | Informe HTML autocontenido (CSS en línea, sin JavaScript ni recursos remotos), con todo dato del sitio escapado y una política de seguridad de contenido. |
| `history.py` | Compara dos informes JSON: diferencia de nota y de categorías, estado de cada comprobación (resuelta, nueva, mejora, empeora, igual, no comparable) y avisos de comparabilidad. |
| `cli.py` | Subcomandos `audit` y `compare`, escritura de ficheros y códigos de salida. |

Fuera del paquete, `demo/sitio.py` sirve un sitio de ejemplo en dos versiones (con fallos y corregido) y `demo/grabar_video.py` regenera el vídeo y los informes de ejemplo de `docs/`.

## Decisiones de diseño del rastreo

- **Ámbito del sitio:** mismo host sin `www.` y con el mismo puerto. Si la portada redirige (`example.com` → `www.example.com`), el ámbito se toma de la URL final.
- **Redirecciones:** cada URL se guarda con la URL que se pidió; `fetch.url` es la final. Si una URL solo redirige a otra página que también se rastreó, no se analiza el contenido dos veces (se cuenta como redirección, no como página duplicada).
- **No se rastrean** extensiones de recursos (imágenes, PDF, CSS, JS, XML, etc.).
- **robots.txt:** las URLs bloqueadas para el agente `seo-auditor` no se descargan y se cuentan aparte en el informe.
- **Rastreo incompleto:** si se alcanza `max_pages` con URLs pendientes, el informe lo avisa y las comprobaciones que darían falsos positivos (páginas huérfanas) se marcan como *no evaluadas* en vez de puntuar.
- **Sin estado entre ejecuciones:** todo vive en memoria; la salida son dos ficheros.

## Seguridad

- SSRF: `safety.check_url` en cada petición y en cada redirección. **Límite conocido:** se comprueba la resolución DNS antes de conectar, no se fija la IP en la conexión, así que un DNS malicioso podría hacer rebinding. Para exponer esto como servicio público hay que fijar la IP resuelta.
- XML: `lxml` con `resolve_entities=False`, `no_network=True`, `huge_tree=False`, y cuerpo limitado a 2 MB.
- El workflow de Actions pasa las entradas por variables de entorno (evita inyección en scripts) y solo tiene permiso de lectura.
