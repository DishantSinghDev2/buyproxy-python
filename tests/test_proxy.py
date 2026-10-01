import pytest

from buyproxy import GeneratedProxies, ProxyEndpoint


def test_parse_keeps_at_and_colon_in_password() -> None:
    line = "user-country-us:p@ss:w0rd@gw.buyproxy.org:6969"
    p = ProxyEndpoint.parse(line)
    assert (p.host, p.port, p.username, p.password) == ("gw.buyproxy.org", 6969, "user-country-us", "p@ss:w0rd")
    assert str(p) == line


def test_url_percent_encodes_credentials() -> None:
    assert ProxyEndpoint.parse("u:p@ss@h.example:80").url == "http://u:p%40ss@h.example:80"


def test_socks5_server_and_curl() -> None:
    p = ProxyEndpoint.parse("u:p@h.example:1080", "socks5")
    assert p.server == "socks5://h.example:1080"
    assert "socks5h://" in p.to_curl()


def test_framework_helpers() -> None:
    p = ProxyEndpoint.parse("u:p@h.example:8080")
    assert p.to_requests() == {"http": "http://u:p@h.example:8080", "https": "http://u:p@h.example:8080"}
    assert p.to_playwright() == {"server": "http://h.example:8080", "username": "u", "password": "p"}
    assert p.to_scrapy_meta() == {"proxy": "http://u:p@h.example:8080"}
    assert p.to_env()["HTTPS_PROXY"] == "http://u:p@h.example:8080"


@pytest.mark.parametrize("bad", ["", "nope", "u:p@host", "u:p@host:99999", ":p@host:80", "u@host:80"])
def test_rejects_malformed_lines(bad: str) -> None:
    with pytest.raises(ValueError):
        ProxyEndpoint.parse(bad)


def test_generated_proxies_is_iterable() -> None:
    g = GeneratedProxies.from_lines(["a:b@h:1", "c:d@h:2"])
    assert len(g) == 2 and [p.port for p in g] == [1, 2] and g[0].username == "a"
