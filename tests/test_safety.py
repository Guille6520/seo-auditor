import pytest

from seo_auditor.safety import UnsafeURL, check_url


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://10.0.0.5/",
    "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",
    "http://0.0.0.0/",
])
def test_blocks_non_public_addresses(url):
    with pytest.raises(UnsafeURL):
        check_url(url)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/", "javascript:alert(1)", "http:///x"])
def test_blocks_bad_schemes_and_hosts(url):
    with pytest.raises(UnsafeURL):
        check_url(url)


def test_allows_public_literal_ip():
    check_url("http://8.8.8.8/")


def test_allow_private_flag_skips_resolution():
    check_url("http://127.0.0.1:8000/", allow_private=True)
