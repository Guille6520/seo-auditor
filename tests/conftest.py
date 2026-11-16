import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

GOOD_TITLE = "Página de ejemplo con un título de longitud adecuada"
GOOD_DESC = "Descripción de ejemplo con longitud adecuada para el resultado de búsqueda, clara y única."


def page(title=GOOD_TITLE, desc=GOOD_DESC, body="", h1="Título principal", head_extra="", words=200):
    text = " ".join(["palabra"] * words)
    h1_tag = f"<h1>{h1}</h1>" if h1 else ""
    desc_tag = f'<meta name="description" content="{desc}">' if desc else ""
    title_tag = f"<title>{title}</title>" if title else ""
    return (
        f'<!doctype html><html lang="es"><head>{title_tag}{desc_tag}'
        f'<meta name="viewport" content="width=device-width">{head_extra}</head>'
        f"<body>{h1_tag}<p>{text}</p>{body}</body></html>"
    )


class _Handler(BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):
        route = self.routes.get(self.path.split("#")[0])
        if route is None:
            status, headers, body = 404, {}, "no encontrada"
        else:
            status, headers, body = route
        self.send_response(status)
        headers = {"Content-Type": "text/html; charset=utf-8", **headers}
        for key, value in headers.items():
            self.send_header(key, value)
        data = body.encode("utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def serve():
    """Levanta un servidor local con las rutas dadas: serve({'/': (200, {}, html)}) -> base URL."""
    servers = []

    def start(routes):
        handler = type("Handler", (_Handler,), {"routes": routes})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def ok(html):
    return 200, {}, html


def sample_site():
    """Sitio de prueba con problemas conocidos (ver test_checks)."""
    home = page(body=(
        '<a href="/buena">buena</a> <a href="/sin-titulo">sin título</a> '
        '<a href="/rota">rota</a> <a href="/viejo">viejo</a> <a href="/dup1">dup1</a> '
        '<a href="/dup2">dup2</a>'
    ), head_extra='<script type="application/ld+json">{"@type": "Organization"}</script>')
    return {
        "/": ok(home),
        "/buena": ok(page(title="Otra página buena con título de longitud correcta aquí",
                          desc="Otra descripción distinta de la anterior, con longitud correcta para buscadores.")),
        "/sin-titulo": ok(page(title=None, desc=None, h1=None, words=20,
                               body='<img src="/a.png"><img src="/b.png" alt="ok">')),
        "/viejo": (301, {"Location": "/buena"}, ""),
        "/dup1": ok(page(title="Título duplicado en dos páginas del sitio web", desc=GOOD_DESC + " uno")),
        "/dup2": ok(page(title="Título duplicado en dos páginas del sitio web", desc=GOOD_DESC + " dos")),
        "/huerfana": ok(page(title="Página huérfana solo presente en el sitemap del sitio",
                             desc="Descripción de la página huérfana con longitud suficiente para ser válida ok.")),
        "/robots.txt": (200, {"Content-Type": "text/plain"},
                        "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
                        "Sitemap: {base}/sitemap.xml\n"),
        "/sitemap.xml": (200, {"Content-Type": "application/xml"},
                         '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                         "<url><loc>{base}/</loc></url><url><loc>{base}/buena</loc></url>"
                         "<url><loc>{base}/huerfana</loc></url></urlset>"),
    }


def with_base(routes, base):
    """Sustituye {base} en robots.txt y sitemap una vez conocido el puerto."""
    for path in ("/robots.txt", "/sitemap.xml"):
        status, headers, body = routes[path]
        routes[path] = (status, headers, body.replace("{base}", base))
