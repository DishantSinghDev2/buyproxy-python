# BuyProxy Python SDK — Residential Proxy API Client (sync & async)

[![PyPI](https://img.shields.io/pypi/v/buyproxy?logo=pypi&logoColor=white)](https://pypi.org/project/buyproxy/)
[![Python](https://img.shields.io/pypi/pyversions/buyproxy)](https://pypi.org/project/buyproxy/)
[![CI](https://github.com/DishantSinghDev2/buyproxy-python/actions/workflows/ci.yml/badge.svg)](https://github.com/DishantSinghDev2/buyproxy-python/actions/workflows/ci.yml)
![typed](https://img.shields.io/badge/typed-mypy%20strict-blue)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

The official **Python SDK** for [BuyProxy](https://www.buyproxy.org): generate **residential, mobile, ISP and datacenter proxies**, check bandwidth, top up by card or crypto, and manage **reseller** customers — with a fully typed sync **and** async client built on `httpx`.

**Keywords:** residential proxies · rotating proxies · mobile proxies · ISP proxies · datacenter proxies · SOCKS5 · proxy API · web scraping · proxy reseller

## Features

- Sync (`BuyProxy`) and async (`AsyncBuyProxy`) clients with identical APIs
- Typed dataclass models — autocomplete everywhere, unknown fields never break you
- Automatic retries with back-off for rate limits and transient errors
- One-line helpers for **requests**, **httpx**, **aiohttp**, **Playwright** and **Scrapy**

## Installation

```bash
pip install buyproxy
# or: uv add buyproxy · poetry add buyproxy
```

Python 3.9+. Ships `py.typed`; passes `mypy --strict`.

## Quick start

```python
from buyproxy import BuyProxy

bp = BuyProxy()  # reads BUYPROXY_API_KEY — or BuyProxy(api_key="bp_key_…")

plan = bp.plans.list()[0]
result = bp.plans.generate(plan.id, country="US", city="Austin", count=5)

proxy = result.proxies[0]
print(proxy.url)  # http://user-country-us-city-austin:pass@gw.buyproxy.org:6969
```

Pass `sticky_minutes=10` to keep the same IP for ten minutes, or `protocol="socks5"` for SOCKS5.

**Async:**

```python
from buyproxy import AsyncBuyProxy

async with AsyncBuyProxy() as bp:
    plans = await bp.plans.list()
    result = await bp.plans.generate(plans[0].id, country="DE", count=3)
```

## Using the proxies with your stack

### requests

```python
import requests

print(requests.get("https://api.ipify.org", proxies=proxy.to_requests()).text)
```

### httpx

```python
import httpx

with httpx.Client(proxy=proxy.to_httpx()) as client:
    print(client.get("https://api.ipify.org").text)
```

### aiohttp

```python
async with aiohttp.ClientSession() as session:
    async with session.get("https://api.ipify.org", proxy=proxy.to_aiohttp()) as r:
        print(await r.text())
```

### Playwright

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(proxy=proxy.to_playwright())
    page = browser.new_page()
    page.goto("https://api.ipify.org")
```

### Scrapy

```python
def start_requests(self):
    yield scrapy.Request("https://api.ipify.org", meta=proxy.to_scrapy_meta())
```

## Buy bandwidth (card & crypto)

```python
# Buy 10 GB of Core Residential by card — open pay_url in a browser
checkout = bp.topup.card(product_key="residential", gb=10)
print(checkout.pay_url)

# Or subscribe to a plan (monthly or yearly)
bp.topup.card(plan="pro", interval="year")

# Crypto (pay-as-you-go top-ups only)
bp.topup.crypto(product_key="residential", gb=50)

# Wait for the payment to settle — GB appears on bp.balances.list() right after
tx = bp.transactions.wait(checkout.transaction_id)
print(tx.status)  # "succeeded"
```

Card payments run through Stripe Checkout; crypto is available for pay-as-you-go top-ups.

## Reseller API

Build a proxy product on top of BuyProxy: buy bandwidth in bulk into a **reseller pool**, create isolated **customers**, and allocate GB to them. Needs a `bp_live_` key on a Business plan or higher.

```python
reseller = BuyProxy(api_key="bp_live_…")

reseller.reseller.pool.topup_card(product_key="residential", gb=500)       # buy into your pool
customer = reseller.reseller.customers.create("Acme Inc")                  # isolated sub-account

reseller.reseller.customers.allocate(
    customer.username, product_key="residential", gb=20, idempotency_key="order-1042",  # safe to retry
)

detail = reseller.reseller.customers.get(customer.username)
result = reseller.reseller.customers.generate(customer.username, plan_id=detail.plans[0].id, country="DE")

reseller.reseller.customers.update(customer.username, status="suspended")
```

## Error handling

```python
from buyproxy import AuthenticationError, InsufficientBandwidthError, RateLimitError

try:
    bp.plans.generate(plan_id)
except InsufficientBandwidthError:
    print("Out of GB — top up first")
except RateLimitError as e:
    print(f"Slow down; retry in {e.retry_after_seconds}s")
except AuthenticationError:
    print("Check your API key")
```
Every exception extends `BuyProxyError` and carries `.status` and the parsed `.body`.

## Configuration

```python
BuyProxy(
    api_key="bp_key_…",            # default: $BUYPROXY_API_KEY
    base_url="https://www.buyproxy.org",
    timeout=30.0,
    max_retries=2,                  # 429s always; 5xx only for safe requests
    http_client=my_httpx_client,    # bring your own httpx.Client
)
```

## API overview

| Capability | Call |
|---|---|
| Catalog & prices | `bp.products.list()` |
| Account | `bp.account.get()` |
| Spendable GB per product | `bp.balances.list()` |
| Plans | `bp.plans.list()` |
| Generate proxies | `bp.plans.generate(plan_id, **params)` |
| Card checkout | `bp.topup.card(...)` |
| Crypto checkout | `bp.topup.crypto(...)` |
| Payments | `bp.transactions.list()` · `.get(id)` · `.wait(id)` |
| Create an account | `bp.auth.signup()` · `.verify_otp()` · `.resend_otp()` |
| Reseller summary | `bp.reseller.me()` |
| Customers | `bp.reseller.customers.list/create/get/update/usage/allocate/generate` |
| Reseller pool | `bp.reseller.pool.get/topup_card/topup_crypto` |

Full endpoint reference: <https://www.buyproxy.org/docs/api-reference/introduction> · OpenAPI spec: <https://www.buyproxy.org/openapi.yaml>

## FAQ

**How do I get an API key?**
Create a free account at [buyproxy.org](https://www.buyproxy.org/signup), then open **Dashboard → API keys**. Personal keys start with `bp_key_`; reseller keys (Business plan and above) start with `bp_live_`. You can create the *account* from code (`signup` + `verify otp`), but keys are issued from the dashboard.

**What's the difference between a personal and a reseller key?**
A personal key (`bp_key_…`) manages your own bandwidth: balances, plans, generating proxies, top-ups and payments. A reseller key (`bp_live_…`) manages *your customers*: create isolated sub-accounts, buy bandwidth into a pool, allocate it, suspend or reactivate, and generate proxies on their behalf.

**Which proxy types are available?**
Core Residential, Premium Residential, ISP Rotating, Mobile, Datacenter IPv4 and IPv6 — call the catalog endpoint for the live list and per-GB prices (from **$1.99/GB**).

**Do generated proxies expire, and when is bandwidth used?**
Generating a proxy is free and instant; bandwidth is only consumed when traffic flows through it. Lines are on-demand — generate fresh ones rather than storing them.

**What are the rate limits?**
60 requests per minute per API key. The SDK honours `Retry-After` and retries rate-limited requests automatically.

**Is it free to use the SDK?**
Yes — the SDK is MIT-licensed. You pay only for the proxy bandwidth you buy.

## Other BuyProxy SDKs

[Node.js](https://github.com/DishantSinghDev2/buyproxy-node) · [Python](https://github.com/DishantSinghDev2/buyproxy-python) · [Go](https://github.com/DishantSinghDev2/buyproxy-go) · [PHP](https://github.com/DishantSinghDev2/buyproxy-php) · [Ruby](https://github.com/DishantSinghDev2/buyproxy-ruby) · [Java](https://github.com/DishantSinghDev2/buyproxy-java) · [.NET](https://github.com/DishantSinghDev2/buyproxy-dotnet) · [Rust](https://github.com/DishantSinghDev2/buyproxy-rust) · [CLI](https://github.com/DishantSinghDev2/buyproxy-cli)

All SDKs are checked against the same request log, so behaviour is identical across languages — see [buyproxy-sdks](https://github.com/DishantSinghDev2/buyproxy-sdks).

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests && mypy src && pytest
```

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md).

## Links

- Website: <https://www.buyproxy.org>
- Documentation: <https://www.buyproxy.org/docs/sdks>
- Pricing: <https://www.buyproxy.org/pricing>
- Support: <support@buyproxy.org>

## License

[MIT](LICENSE) © BuyProxy
