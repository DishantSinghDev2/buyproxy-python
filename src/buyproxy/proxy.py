"""A generated proxy and the shapes popular Python libraries want it in."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal
from urllib.parse import quote

ProxyProtocol = Literal["http", "socks5"]


@dataclass(frozen=True)
class ProxyEndpoint:
    """One generated proxy. The API returns ``username:password@host:port`` lines."""

    host: str
    port: int
    username: str
    password: str
    protocol: ProxyProtocol = "http"

    @classmethod
    def parse(cls, line: str, protocol: ProxyProtocol = "http") -> "ProxyEndpoint":
        """Parse a ``username:password@host:port`` line (``@`` and ``:`` are allowed inside the password)."""
        credentials, at, address = line.rpartition("@")
        username, colon, password = credentials.partition(":")
        host, _, port_text = address.rpartition(":")
        if not (at and colon and username and host and port_text.isdigit() and 0 < int(port_text) < 65536):
            raise ValueError(f"Not a proxy line (expected username:password@host:port): {line!r}")
        return cls(host, int(port_text), username, password, protocol)

    def __str__(self) -> str:
        return f"{self.username}:{self.password}@{self.host}:{self.port}"

    @property
    def server(self) -> str:
        """``http://host:port`` — no credentials."""
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def url(self) -> str:
        """Full URL with percent-encoded credentials, ready for any HTTP client."""
        return f"{self.protocol}://{quote(self.username, safe='')}:{quote(self.password, safe='')}@{self.host}:{self.port}"

    def to_requests(self) -> Dict[str, str]:
        """``requests.get(url, proxies=proxy.to_requests())``."""
        return {"http": self.url, "https": self.url}

    def to_httpx(self) -> str:
        """``httpx.Client(proxy=proxy.to_httpx())`` (httpx ≥ 0.26)."""
        return self.url

    def to_aiohttp(self) -> str:
        """``session.get(url, proxy=proxy.to_aiohttp())`` (HTTP proxies)."""
        return self.url

    def to_playwright(self) -> Dict[str, str]:
        """``browser = p.chromium.launch(proxy=proxy.to_playwright())``."""
        return {"server": self.server, "username": self.username, "password": self.password}

    def to_scrapy_meta(self) -> Dict[str, str]:
        """``yield scrapy.Request(url, meta=proxy.to_scrapy_meta())`` — works with Scrapy's built-in HttpProxyMiddleware."""
        return {"proxy": self.url}

    def to_env(self) -> Dict[str, str]:
        """Environment variables understood by curl, wget, pip, git and most CLIs."""
        return {k: self.url for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")}

    def to_curl(self, target: str = "https://api.ipify.org") -> str:
        scheme = "socks5h" if self.protocol == "socks5" else "http"
        return f"curl -x '{scheme}://{self.username}:{self.password}@{self.host}:{self.port}' {target}"


@dataclass(frozen=True)
class GeneratedProxies:
    """The result of a ``generate`` call: raw lines plus parsed endpoints."""

    lines: List[str]
    proxies: List[ProxyEndpoint] = field(default_factory=list)

    @classmethod
    def from_lines(cls, lines: List[str], protocol: ProxyProtocol = "http") -> "GeneratedProxies":
        return cls(lines=list(lines), proxies=[ProxyEndpoint.parse(line, protocol) for line in lines])

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.proxies)

    def __len__(self) -> int:
        return len(self.proxies)

    def __getitem__(self, index: int) -> ProxyEndpoint:
        return self.proxies[index]
