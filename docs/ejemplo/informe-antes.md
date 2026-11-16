# Informe SEO: http://127.0.0.1:8765/

**Nota: 60/100** · 8 páginas rastreadas · generado 2026-11-15T09:45:36+00:00

## Por categoría

| Categoría | Nota |
|---|---|
| Rastreo e indexación | 54/100 |
| Contenido en página | 75/100 |
| Datos estructurados | 0/100 |
| Rendimiento y seguridad básicos | n/d |
| Visibilidad en IAs | 83/100 |

## Prioridades

### El sitio no usa HTTPS

Severidad **alta** · 1 de 1 afectadas · `https`

Sirve todo el sitio por HTTPS y redirige el tráfico HTTP.

- http://127.0.0.1:8765/ — la URL final no es https

### Páginas sin canonical

Severidad **media** · 6 de 6 afectadas · `canonical_present`

Añade <link rel="canonical"> apuntando a la URL preferida de cada página.

- http://127.0.0.1:8765/
- http://127.0.0.1:8765/productos
- http://127.0.0.1:8765/pan-de-masa-madre
- http://127.0.0.1:8765/horarios
- http://127.0.0.1:8765/blog/como-conservar-el-pan
- ... y 1 más (ver el JSON)

### JSON-LD con errores de sintaxis

Severidad **media** · 1 de 1 afectadas · `jsonld_valid`

Corrige el JSON de los bloques application/ld+json (solo se valida que sea JSON válido).

- http://127.0.0.1:8765/productos — 1 de 1 bloques inválidos

### No se encontró sitemap XML

Severidad **media** · 1 de 1 afectadas · `sitemap_xml`

Publica un sitemap.xml y decláralo en robots.txt.

- /sitemap.xml — no encontrado

### Imágenes sin atributo alt

Severidad **baja** · 1 de 1 afectadas · `img_alt`

Añade texto alternativo descriptivo (alt vacío solo en imágenes decorativas).

- http://127.0.0.1:8765/productos — 1 de 1 sin alt

### La portada no tiene datos estructurados

Severidad **baja** · 1 de 1 afectadas · `jsonld_home`

Añade JSON-LD (Organization o LocalBusiness, WebSite) en la portada.

- http://127.0.0.1:8765/

### Títulos duplicados

Severidad **media** · 2 de 5 afectadas · `title_unique`

Da a cada página un título distinto.

- http://127.0.0.1:8765/productos — compartido con 1 página(s) más
- http://127.0.0.1:8765/pan-de-masa-madre — compartido con 1 página(s) más

### Páginas sin un único H1

Severidad **media** · 2 de 6 afectadas · `h1_single`

Usa exactamente un H1 por página que describa su tema.

- http://127.0.0.1:8765/pan-de-masa-madre — 2 H1
- http://127.0.0.1:8765/contacto — sin H1

### Páginas sin <title>

Severidad **alta** · 1 de 6 afectadas · `title_present`

Cada página necesita un título propio y descriptivo.

- http://127.0.0.1:8765/contacto

### Títulos demasiado cortos o largos

Severidad **baja** · 2 de 5 afectadas · `title_length`

Intenta que el título tenga entre 30 y 60 caracteres (orientativo).

- http://127.0.0.1:8765/productos — 17 caracteres
- http://127.0.0.1:8765/pan-de-masa-madre — 17 caracteres

### Enlaces internos rotos

Severidad **alta** · 1 de 8 afectadas · `broken_links`

Actualiza o elimina los enlaces que apuntan a páginas que no existen.

- http://127.0.0.1:8765/ofertas — HTTP 404; enlazada desde http://127.0.0.1:8765/

### Páginas que responden con error

Severidad **alta** · 1 de 8 afectadas · `status_ok`

Corrige o redirige las URLs que devuelven 4xx/5xx o no responden.

- http://127.0.0.1:8765/ofertas — HTTP 404

### Páginas sin meta description

Severidad **media** · 1 de 6 afectadas · `meta_description_present`

Escribe una descripción única que resuma la página e invite al clic.

- http://127.0.0.1:8765/horarios

### Páginas con noindex

Severidad **media** · 1 de 6 afectadas · `noindex`

Confirma que cada página con noindex es intencionada; si no, quita la directiva.

- http://127.0.0.1:8765/blog/como-conservar-el-pan — noindex en meta robots o X-Robots-Tag

### Páginas con muy poco texto

Severidad **media** · 1 de 6 afectadas · `thin_content`

Amplía o consolida las páginas con menos de 150 palabras.

- http://127.0.0.1:8765/horarios — 13 palabras

### Falta la meta viewport

Severidad **media** · 1 de 6 afectadas · `viewport`

Añade <meta name="viewport" content="width=device-width, initial-scale=1">.

- http://127.0.0.1:8765/horarios

### Cadenas de redirección

Severidad **media** · 1 de 8 afectadas · `redirect_chain`

Enlaza directamente a la URL final para evitar saltos intermedios.

- http://127.0.0.1:8765/tienda — http://127.0.0.1:8765/tienda -> http://127.0.0.1:8765/catalogo -> http://127.0.0.1:8765/productos

### Rastreadores de IA bloqueados en robots.txt

Severidad **baja** · 1 de 6 afectadas · `ai_crawlers`

Si quieres aparecer en respuestas de IA, permite estos agentes. Si el bloqueo es intencionado, ignora este aviso.

- /robots.txt — GPTBot no puede acceder a /

### Falta el atributo lang en <html>

Severidad **baja** · 1 de 6 afectadas · `lang_attr`

Declara el idioma de la página, por ejemplo <html lang="es">.

- http://127.0.0.1:8765/contacto

### No hay llms.txt (informativo)

Severidad **info** · 1 de 1 afectadas · `llms_txt`

llms.txt es una propuesta de formato sin efecto demostrado en las respuestas de las IAs; se informa pero no puntúa.

- /llms.txt — no encontrado

## No evaluadas

- Canonical que apunta a otra URL
- Falta la cabecera HSTS
- Páginas del sitemap sin enlaces internos

---
La nota se calcula en código a partir de las comprobaciones (ver docs/NOTA.md).
