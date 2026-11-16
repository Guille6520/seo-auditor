"""Regresiones de seguridad (SSRF) y robustez de la descarga: safety.check_url y fetch.fetch."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import seo_auditor.fetch as fetch_module
from seo_auditor.fetch import MAX_REDIRECTS, fetch, new_session
from seo_auditor.safety import UnsafeURL, check_url

HTML = "<!doctype html><html><head><title>t</title></head><body><p>hola</p></body></html>"


class _RawHandler(BaseHTTPRequestHandler):
    """Servidor crudo: no anade Content-Type por su cuenta y anota cada peticion recibida."""

    routes: dict = {}
    hits: list = []

    def do_GET(self):
        self.hits.append(self.path)
        status, headers, body = self.routes.get(self.path, (404, {"Content-Type": "text/plain"}, b"no"))
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def raw_serve():
    """raw_serve(routes) -> (base, hits). Rutas: path -> (status, headers, body str|bytes)."""
    servers = []

    def start(routes):
        hits: list[str] = []
        handler = type("Handler", (_RawHandler,), {"routes": routes, "hits": hits})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}", hits

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture
def session():
    s = new_session()
    yield s
    s.close()


def html_route(body=HTML, content_type="text/html; charset=utf-8"):
    return 200, {"Content-Type": content_type}, body


# ---------- 1. URLs ambiguas: barra invertida, espacios, control, usuario ----------

@pytest.mark.parametrize("allow_private", [False, True])
@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000\\@8.8.8.8/",
    "http://8.8.8.8\\@127.0.0.1/",
    "http://8.8.8.8/a b",
    "http://8.8.8.8 /",
    " http://8.8.8.8/",
    "http://8.8.8.8/\t",
    "http://8.8.8.8/\n",
    "http://8.8.8.8/\r\nHost: x",
    "http://8.8.8.8/\x00",
    "http://8.8.8.8/\x7f",
    "http://user@8.8.8.8/",
    "http://user:clave@8.8.8.8/",
    "http://@8.8.8.8/",
])
def test_check_url_rejects_ambiguous_urls(url, allow_private):
    with pytest.raises(UnsafeURL):
        check_url(url, allow_private=allow_private)


@pytest.mark.parametrize("url", [
    "ftp://8.8.8.8/",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "//8.8.8.8/",
    "http:///sin-host",
    "http://[bad/",
    "http://8.8.8.8:abc/",
])
def test_check_url_rejects_bad_scheme_host_or_port(url):
    with pytest.raises(UnsafeURL):
        check_url(url, allow_private=True)


def test_check_url_accepts_public_literal_ips():
    # Control: IP literales publicas (no necesitan DNS ni red).
    assert check_url("http://8.8.8.8/") is None
    assert check_url("https://8.8.8.8:8443/ruta?x=1") is None
    assert check_url("http://[2001:4860:4860::8888]/") is None


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://127.0.0.1:8080/",
    "http://10.0.0.1/",
    "http://192.168.1.1/",
    "http://172.16.0.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://0.0.0.0/",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",
    "http://[fe80::1]/",
    "http://[fc00::1]/",
])
def test_check_url_rejects_private_ips_and_allow_private_lets_them_through(url):
    with pytest.raises(UnsafeURL):
        check_url(url)
    assert check_url(url, allow_private=True) is None


def test_fetch_backslash_url_is_blocked_and_never_reaches_local_server(raw_serve, session):
    base, hits = raw_serve({"/": html_route()})
    port = base.rsplit(":", 1)[1]
    for allow_private in (False, True):
        result = fetch(f"http://127.0.0.1:{port}\\@8.8.8.8/", session, allow_private=allow_private)
        assert result.status is None
        assert result.error
        assert result.body == ""
    assert hits == []


@pytest.mark.parametrize("suffix", ["/a b", "/\n", "/\x00"])
def test_fetch_url_with_spaces_or_control_chars_is_blocked(raw_serve, session, suffix):
    base, hits = raw_serve({"/": html_route()})
    result = fetch(base + suffix, session, allow_private=True)
    assert result.status is None and result.error
    assert hits == []


def test_fetch_url_with_userinfo_is_blocked(raw_serve, session):
    base, hits = raw_serve({"/": html_route()})
    result = fetch(base.replace("http://", "http://user@") + "/", session, allow_private=True)
    assert result.status is None and result.error
    assert hits == []


def test_fetch_private_target_blocked_without_flag_and_allowed_with_it(raw_serve, session):
    base, hits = raw_serve({"/": html_route()})
    blocked = fetch(base + "/", session, allow_private=False)
    assert blocked.status is None and blocked.error
    assert hits == []
    # Control: con allow_private la misma URL si se descarga.
    allowed = fetch(base + "/", session, allow_private=True)
    assert allowed.status == 200 and allowed.error is None
    assert allowed.is_html and allowed.body == HTML
    assert hits == ["/"]


# ---------- 2. IPv6 de tunel y hosts invalidos ----------

@pytest.mark.parametrize("url", [
    "http://[64:ff9b::7f00:1]/",       # NAT64 -> 127.0.0.1
    "http://[64:ff9b::a00:1]/",        # NAT64 -> 10.0.0.1
    "http://[2002:7f00:1::]/",         # 6to4 -> 127.0.0.1
    "http://[2002:c0a8:101::1]/",      # 6to4 -> 192.168.1.1
])
def test_check_url_rejects_ipv6_tunnels(url):
    with pytest.raises(UnsafeURL):
        check_url(url)


@pytest.mark.parametrize("url", [
    "http://a..b.com/",
    "http://" + "a" * 64 + ".com/",
    "http://.com/",
])
def test_check_url_invalid_hosts_raise_unsafeurl_not_unicodeerror(url):
    # UnsafeURL hereda de ValueError igual que UnicodeError: se comprueba el tipo exacto.
    with pytest.raises(ValueError) as excinfo:
        check_url(url)
    assert type(excinfo.value) is UnsafeURL


@pytest.mark.parametrize("url", ["http://a..b.com/", "http://" + "a" * 64 + ".com/"])
def test_fetch_invalid_hosts_do_not_raise(session, url):
    result = fetch(url, session)
    assert result.status is None and result.error


# ---------- 3. Redireccion hacia una IP privada ----------

def test_redirect_to_private_ip_is_blocked(raw_serve, session, monkeypatch):
    routes: dict = {}
    base, hits = raw_serve(routes)
    target = "http://10.0.0.5/secreto"
    routes["/salta"] = (302, {"Location": target}, b"")
    initial = base + "/salta"
    checked = []
    real_check = check_url

    def only_initial(url, allow_private=False):
        # La URL inicial (servidor local de pruebas) se deja pasar; el resto pasa por la
        # comprobacion real, que debe rechazar el destino privado.
        checked.append((url, allow_private))
        real_check(url, allow_private=(url == initial))

    monkeypatch.setattr(fetch_module, "check_url", only_initial)
    result = fetch(initial, session, allow_private=False, timeout=2)
    assert result.status is None
    assert result.error
    assert result.url == target
    assert result.chain == [(initial, 302)]
    assert result.body == ""
    assert checked == [(initial, False), (target, False)]
    assert hits == ["/salta"]


def test_redirect_within_allowed_host_is_followed(raw_serve, session):
    # Control: una redireccion relativa normal se sigue y queda en la cadena.
    base, hits = raw_serve({
        "/viejo": (301, {"Location": "/nuevo"}, b""),
        "/nuevo": html_route(),
    })
    result = fetch(base + "/viejo", session, allow_private=True)
    assert result.status == 200 and result.error is None
    assert result.requested == base + "/viejo"
    assert result.url == base + "/nuevo"
    assert result.chain == [(base + "/viejo", 301)]
    assert result.redirects == 1
    assert hits == ["/viejo", "/nuevo"]


# ---------- 4-5. Codificaciones ----------

def test_unknown_charset_does_not_raise_and_returns_body(raw_serve, session):
    base, _ = raw_serve({"/": html_route("<html><body>Señalización</body></html>",
                                         "text/html; charset=foo-bar")})
    result = fetch(base + "/", session, allow_private=True)
    assert result.status == 200 and result.error is None
    assert result.is_html
    assert "Señalización" in result.body  # charset desconocido: se decodifica como UTF-8


def test_utf8_body_without_charset_is_not_mojibake(raw_serve, session):
    base, _ = raw_serve({"/": html_route("<html><body>Señalización</body></html>", "text/html")})
    result = fetch(base + "/", session, allow_private=True)
    assert result.status == 200 and result.error is None
    assert "Señalización" in result.body
    assert "Ã" not in result.body


def test_cp1252_body_without_charset_does_not_raise(raw_serve, session):
    raw = "<html><body>Señalización €</body></html>".encode("cp1252")
    base, _ = raw_serve({"/": html_route(raw, "text/html")})
    result = fetch(base + "/", session, allow_private=True)
    assert result.status == 200 and result.error is None
    assert result.raw == raw
    assert "Señalización €" in result.body


def test_declared_charset_is_respected(raw_serve, session):
    # Control: un charset valido en la cabecera manda sobre la deteccion.
    raw = "<html><body>Señalización</body></html>".encode("iso-8859-1")
    base, _ = raw_serve({"/": html_route(raw, 'text/html; charset="ISO-8859-1"')})
    result = fetch(base + "/", session, allow_private=True)
    assert "Señalización" in result.body


def test_invalid_bytes_for_declared_charset_do_not_raise(raw_serve, session):
    base, _ = raw_serve({"/": html_route(b"<html><body>\xff\xfe\xf1</body></html>",
                                         "text/html; charset=utf-8")})
    result = fetch(base + "/", session, allow_private=True)
    assert result.status == 200 and result.error is None
    assert result.body.startswith("<html><body>")


# ---------- 6-7. Redirecciones mal formadas y bucles ----------

@pytest.mark.parametrize("location", ["http://[bad/", "//[x", "http://[::1/"])
def test_malformed_location_does_not_raise(raw_serve, session, location):
    base, hits = raw_serve({"/salta": (302, {"Location": location}, b"")})
    result = fetch(base + "/salta", session, allow_private=True)
    assert result.status is None
    assert result.error
    assert hits == ["/salta"]


def test_location_with_bad_port_does_not_raise(raw_serve, session):
    base, _ = raw_serve({"/salta": (302, {"Location": "http://127.0.0.1:abc/"}, b"")})
    result = fetch(base + "/salta", session, allow_private=True)
    assert result.status is None and result.error


def test_redirect_loop_gives_error_and_no_status(raw_serve, session):
    base, hits = raw_serve({"/bucle": (302, {"Location": "/bucle"}, b"")})
    result = fetch(base + "/bucle", session, allow_private=True)
    assert result.status is None
    assert result.error
    assert result.body == ""
    assert len(result.chain) == MAX_REDIRECTS + 1
    assert len(hits) == MAX_REDIRECTS + 1


def test_exactly_max_redirects_is_still_followed(raw_serve, session):
    # Control: MAX_REDIRECTS saltos seguidos de una pagina 200 si se resuelven.
    routes = {f"/r{i}": (302, {"Location": f"/r{i + 1}"}, b"") for i in range(MAX_REDIRECTS)}
    routes[f"/r{MAX_REDIRECTS}"] = html_route()
    base, _ = raw_serve(routes)
    result = fetch(base + "/r0", session, allow_private=True)
    assert result.status == 200 and result.error is None
    assert result.redirects == MAX_REDIRECTS
    assert result.url == f"{base}/r{MAX_REDIRECTS}"


def test_one_redirect_too_many_fails(raw_serve, session):
    routes = {f"/r{i}": (302, {"Location": f"/r{i + 1}"}, b"") for i in range(MAX_REDIRECTS + 1)}
    routes[f"/r{MAX_REDIRECTS + 1}"] = html_route()
    base, _ = raw_serve(routes)
    result = fetch(base + "/r0", session, allow_private=True)
    assert result.status is None and result.error


def test_redirect_status_without_location_is_returned_as_is(raw_serve, session):
    base, _ = raw_serve({"/raro": (302, {"Content-Type": "text/html"}, b"")})
    result = fetch(base + "/raro", session, allow_private=True)
    assert result.status == 302 and result.error is None and result.chain == []


# ---------- 8. Limite de tamano ----------

def test_body_larger_than_max_bytes_is_truncated(raw_serve, session):
    big = b"<html><body>" + b"x" * 50_000
    base, _ = raw_serve({"/": html_route(big)})
    result = fetch(base + "/", session, allow_private=True, max_bytes=1000)
    assert result.status == 200 and result.error is None
    assert len(result.raw) == 1000
    assert result.raw == big[:1000]
    assert len(result.body) == 1000


def test_body_smaller_than_max_bytes_is_complete(raw_serve, session):
    base, _ = raw_serve({"/": html_route()})
    result = fetch(base + "/", session, allow_private=True, max_bytes=100_000)
    assert result.raw == HTML.encode("utf-8")
    assert result.body == HTML


# ---------- 9. Sin Content-Type / tipos binarios ----------

def test_html_without_content_type_is_html_and_has_body(raw_serve, session):
    base, _ = raw_serve({"/": (200, {}, HTML)})
    result = fetch(base + "/", session, allow_private=True)
    assert result.status == 200 and result.error is None
    assert "content-type" not in result.headers
    assert result.is_html is True
    assert result.body == HTML


def test_plain_text_without_content_type_is_not_html(raw_serve, session):
    base, _ = raw_serve({"/robots.txt": (200, {}, "User-agent: *\nDisallow: /privado\n")})
    result = fetch(base + "/robots.txt", session, allow_private=True)
    assert result.status == 200
    assert result.is_html is False
    assert result.body.startswith("User-agent")


def test_binary_type_body_is_skipped_unless_forced(raw_serve, session):
    base, _ = raw_serve({"/foto.png": (200, {"Content-Type": "image/png"}, b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)})
    plain = fetch(base + "/foto.png", session, allow_private=True)
    assert plain.status == 200 and plain.raw == b"" and plain.body == ""
    assert plain.is_html is False
    forced = fetch(base + "/foto.png", session, allow_private=True, force_body=True)
    assert forced.status == 200 and forced.raw.startswith(b"\x89PNG")


def test_error_status_is_reported_not_raised(raw_serve, session):
    base, _ = raw_serve({"/roto": (500, {"Content-Type": "text/html"}, "<html>error</html>")})
    for path, status in (("/roto", 500), ("/no-existe", 404)):
        result = fetch(base + path, session, allow_private=True)
        assert result.status == status and result.error is None


def test_connection_refused_does_not_raise(session):
    result = fetch("http://127.0.0.1:1/", session, allow_private=True, timeout=2)
    assert result.status is None and result.error
