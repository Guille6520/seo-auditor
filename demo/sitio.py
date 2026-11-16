"""Sitio de demostración local (una panadería ficticia) en dos versiones: 'antes' y 'despues'.

La versión 'antes' tiene fallos SEO puestos a propósito; 'despues' los corrige.
Sirve para enseñar el auditor sin depender de ninguna web real:

    python demo/sitio.py antes      # http://127.0.0.1:8765
    python demo/sitio.py despues
"""

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"

PARAGRAPH = (
    "En Panadería Ejemplo amasamos cada madrugada con harinas de molino de piedra, agua, sal y "
    "masa madre propia. Dejamos fermentar la masa en frío durante un día entero para que el pan "
    "gane sabor, se conserve tierno más tiempo y resulte más digestivo. Horneamos en horno de "
    "solera en tandas pequeñas, de modo que siempre haya pan reciente a lo largo de la mañana. "
)
LONG_TEXT = "".join(f"<p>{PARAGRAPH}</p>" for _ in range(3))
NAV = (
    '<nav><a href="/">Inicio</a> <a href="/productos">Productos</a> '
    '<a href="/pan-de-masa-madre">Masa madre</a> <a href="/horarios">Horarios</a> '
    '<a href="/blog/como-conservar-el-pan">Blog</a> <a href="/contacto">Contacto</a></nav>'
)
ORGANIZATION = (
    '<script type="application/ld+json">{"@context": "https://schema.org", "@type": "Bakery", '
    '"name": "Panadería Ejemplo", "url": "' + BASE + '/"}</script>'
)

# Contenido común: ruta -> (título, descripción, h1, cuerpo)
PAGES = {
    "/": ("Panadería Ejemplo: pan artesano de masa madre en Bilbao",
          "Pan artesano de masa madre horneado cada día en Bilbao. Hogazas, baguettes y bollería "
          "hechas con harinas de molino de piedra.",
          "Pan artesano hecho cada día", LONG_TEXT),
    "/productos": ("Nuestros panes y bollería artesana | Panadería Ejemplo",
                   "Catálogo de panes de masa madre, baguettes, pan de centeno y bollería "
                   "artesana, con ingredientes y alérgenos de cada pieza.",
                   "Productos", LONG_TEXT + '<img src="/img/hogaza.jpg" alt="Hogaza de masa madre">'),
    "/pan-de-masa-madre": ("Pan de masa madre: cómo lo hacemos | Panadería Ejemplo",
                           "Así elaboramos nuestro pan de masa madre: fermentación lenta en frío, "
                           "harinas de molino de piedra y horno de solera.",
                           "Pan de masa madre", LONG_TEXT),
    "/horarios": ("Horarios y cómo llegar a la panadería | Panadería Ejemplo",
                  "Consulta el horario de apertura de la panadería, los días festivos y cómo "
                  "llegar en metro, autobús o a pie desde el centro.",
                  "Horarios", LONG_TEXT),
    "/contacto": ("Contacto y encargos de pan | Panadería Ejemplo",
                  "Escríbenos o llámanos para encargar pan, hacer pedidos para eventos o "
                  "resolver cualquier duda sobre ingredientes y alérgenos.",
                  "Contacto", LONG_TEXT),
    "/blog/como-conservar-el-pan": ("Cómo conservar el pan para que dure más | Panadería Ejemplo",
                                    "Consejos prácticos para conservar el pan artesano varios "
                                    "días: bolsa de tela, congelado en rebanadas y cómo regenerarlo.",
                                    "Cómo conservar el pan", LONG_TEXT),
}


def _html(path, title, desc, h1, body, *, lang=True, viewport=True, canonical=True, extra_head=""):
    head = ['<meta charset="utf-8">']
    if title:
        head.append(f"<title>{title}</title>")
    if desc:
        head.append(f'<meta name="description" content="{desc}">')
    if viewport:
        head.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    if canonical:
        head.append(f'<link rel="canonical" href="{BASE}{path}">')
    head.append(extra_head)
    h1_tag = f"<h1>{h1}</h1>" if h1 else ""
    html_tag = '<html lang="es">' if lang else "<html>"
    return f"<!doctype html>{html_tag}<head>{''.join(head)}</head><body>{NAV}{h1_tag}{body}</body></html>"


def _ok(body, content_type="text/html; charset=utf-8"):
    return 200, {"Content-Type": content_type}, body


def site_after():
    """Versión corregida: todas las páginas completas, sitemap y robots abiertos."""
    routes = {}
    for path, (title, desc, h1, body) in PAGES.items():
        extra = ORGANIZATION if path == "/" else ""
        routes[path] = _ok(_html(path, title, desc, h1, body, extra_head=extra))
    urls = "".join(f"<url><loc>{BASE}{p}</loc></url>" for p in PAGES)
    routes["/sitemap.xml"] = _ok(
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
        "application/xml")
    routes["/robots.txt"] = _ok(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", "text/plain")
    return routes


def site_before():
    """Versión con fallos puestos a propósito (ver el README del proyecto)."""
    p = PAGES
    routes = {
        # Portada: sin canonical, sin datos estructurados, enlaza a una página rota y a una cadena.
        "/": _ok(_html("/", p["/"][0], p["/"][1], p["/"][2],
                       LONG_TEXT + '<a href="/ofertas">Ofertas</a> <a href="/tienda">Tienda</a>',
                       canonical=False)),
        # Título genérico duplicado, imagen sin alt, JSON-LD roto.
        "/productos": _ok(_html("/productos", "Panadería Ejemplo", p["/productos"][1], "Productos",
                                LONG_TEXT + '<img src="/img/hogaza.jpg">', canonical=False,
                                extra_head='<script type="application/ld+json">{"@type": "Product",}</script>')),
        # Mismo título genérico, dos H1.
        "/pan-de-masa-madre": _ok(_html("/pan-de-masa-madre", "Panadería Ejemplo",
                                        p["/pan-de-masa-madre"][1],
                                        "Pan de masa madre", "<h1>Nuestro pan</h1>" + LONG_TEXT,
                                        canonical=False)),
        # Contenido escaso, sin descripción, sin viewport.
        "/horarios": _ok(_html("/horarios", p["/horarios"][0], None, "Horarios",
                               "<p>Abrimos de lunes a sábado.</p>", viewport=False, canonical=False)),
        # Sin título, sin H1, sin idioma.
        "/contacto": _ok(_html("/contacto", None, p["/contacto"][1], None, LONG_TEXT,
                               lang=False, canonical=False)),
        # Noindex olvidado en una entrada del blog.
        "/blog/como-conservar-el-pan": _ok(_html(
            "/blog/como-conservar-el-pan", *p["/blog/como-conservar-el-pan"], canonical=False,
            extra_head='<meta name="robots" content="noindex">')),
        # Cadena de redirecciones: /tienda -> /catalogo -> /productos
        "/tienda": (301, {"Location": "/catalogo"}, ""),
        "/catalogo": (301, {"Location": "/productos"}, ""),
        # Sin sitemap y con un rastreador de IA bloqueado.
        "/robots.txt": _ok("User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n", "text/plain"),
    }
    return routes


def make_server(version: str, port: int = PORT) -> ThreadingHTTPServer:
    """Crea (sin arrancar) el servidor de la versión indicada."""
    routes = site_before() if version == "antes" else site_after()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, headers, body = routes.get(self.path, (404, {"Content-Type": "text/html"}, "No encontrada"))
            data = body.encode("utf-8")
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "antes"
    if version not in ("antes", "despues"):
        sys.exit("Uso: python demo/sitio.py [antes|despues]")
    print(f"Sitio de demostración ({version}) en {BASE}  (Ctrl+C para parar)")
    try:
        make_server(version).serve_forever()
    except KeyboardInterrupt:
        pass
