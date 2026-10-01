"""Sync (:class:`BuyProxy`) and async (:class:`AsyncBuyProxy`) clients."""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any, Dict, List, Optional, TypeVar

import httpx

from . import _spec as spec
from ._version import __version__
from .errors import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BuyProxyError,
    error_from_response,
)
from .models import (
    Account,
    Allocation,
    Balance,
    CardCheckout,
    Catalog,
    CryptoCheckout,
    Customer,
    CustomerDetail,
    CustomerUsage,
    Plan,
    PoolEntry,
    ResellerSummary,
    SignupResult,
    Transaction,
    VerifyResult,
)
from .proxy import GeneratedProxies

DEFAULT_BASE_URL = "https://www.buyproxy.org"
_RETRYABLE_5XX = {502, 503, 504}
T = TypeVar("T")


def _backoff(attempt: int) -> float:
    return min(0.5 * (2.0**attempt), 8.0) * (0.75 + random.random() * 0.5)


def _retry_after(response: httpx.Response) -> Optional[float]:
    raw = response.headers.get("retry-after")
    try:
        value = float(raw) if raw is not None else None
    except ValueError:
        return None
    if value is None or value < 0:
        return None
    return min(value, 30.0)


class _Base:
    def __init__(self, api_key: Optional[str], base_url: str, timeout: float, max_retries: int) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("BUYPROXY_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def key_kind(self) -> Optional[str]:
        """``"reseller"`` for ``bp_live_`` keys, ``"personal"`` for ``bp_key_`` keys, ``None`` without a key."""
        if not self.api_key:
            return None
        return "reseller" if self.api_key.startswith("bp_live_") else "personal"

    def _prepare(self, req: spec.Request[Any]) -> Dict[str, Any]:
        if req.auth and not self.api_key:
            raise AuthenticationError(
                "No API key — pass api_key= to the client or set BUYPROXY_API_KEY. "
                "Create one at https://www.buyproxy.org/dashboard/api-keys"
            )
        headers = {"Accept": "application/json", "User-Agent": f"buyproxy-python/{__version__}", **req.headers}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        kwargs: Dict[str, Any] = {"method": req.method, "url": self.base_url + req.path, "headers": headers}
        if req.query:
            kwargs["params"] = req.query
        if req.body is not None:
            kwargs["json"] = req.body
        return kwargs

    @staticmethod
    def _decide(req: spec.Request[Any], response: httpx.Response, attempt: int, max_retries: int) -> Optional[float]:
        """Seconds to wait before retrying, or ``None`` to stop and return/raise."""
        if response.is_success or attempt >= max_retries:
            return None
        if response.status_code == 429:
            retry_after = _retry_after(response)
            return retry_after if retry_after is not None else _backoff(attempt)
        if req.retry_5xx and response.status_code in _RETRYABLE_5XX:
            return _backoff(attempt)
        return None

    @staticmethod
    def _finish(req: spec.Request[T], response: httpx.Response) -> T:
        try:
            data = response.json() if response.content else None
        except ValueError:
            data = None
        if response.is_success:
            if data is None and response.content:
                raise BuyProxyError(f"BuyProxy returned a non-JSON response (HTTP {response.status_code})", response.status_code)
            return req.parse(data)
        raise error_from_response(response.status_code, data, _retry_after(response))


# --- Sync ------------------------------------------------------------------


class BuyProxy(_Base):
    """BuyProxy API client.

    >>> bp = BuyProxy(api_key="bp_key_...")
    >>> result = bp.plans.generate(plan_id, country="US", count=5)
    >>> result.proxies[0].to_requests()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 2,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        super().__init__(api_key, base_url, timeout, max_retries)
        self._http = http_client or httpx.Client(timeout=timeout)
        self._owns_http = http_client is None
        self.products = _Products(self)
        self.auth = _Auth(self)
        self.account = _Account(self)
        self.balances = _Balances(self)
        self.plans = _Plans(self)
        self.topup = _Topup(self)
        self.transactions = _Transactions(self)
        self.reseller = _Reseller(self)

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "BuyProxy":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _send(self, req: spec.Request[T]) -> T:
        kwargs = self._prepare(req)
        for attempt in range(self.max_retries + 1):
            try:
                response = self._http.request(**kwargs)
            except httpx.TimeoutException as exc:
                raise APITimeoutError(f"Request timed out after {self.timeout}s") from exc
            except httpx.TransportError as exc:
                if req.retry_5xx and attempt < self.max_retries:
                    time.sleep(_backoff(attempt))
                    continue
                raise APIConnectionError(f"Could not reach BuyProxy: {exc}") from exc
            wait = self._decide(req, response, attempt, self.max_retries)
            if wait is not None:
                time.sleep(wait)
                continue
            return self._finish(req, response)
        raise AssertionError("unreachable")  # pragma: no cover


class _Products:
    def __init__(self, c: BuyProxy) -> None:
        self._c = c

    def list(self) -> Catalog:
        """Every product with its ``product_key``, minimum GB and live price. No API key needed."""
        return self._c._send(spec.products_list())


class _Auth:
    def __init__(self, c: BuyProxy) -> None:
        self._c = c

    def signup(self, email: str, password: str, name: Optional[str] = None) -> SignupResult:
        return self._c._send(spec.signup(email, password, name))

    def verify_otp(self, email: str, code: str) -> VerifyResult:
        return self._c._send(spec.verify_otp(email, code))

    def resend_otp(self, email: str) -> None:
        self._c._send(spec.resend_otp(email))


class _Account:
    def __init__(self, c: BuyProxy) -> None:
        self._c = c

    def get(self) -> Account:
        return self._c._send(spec.account_get())


class _Balances:
    def __init__(self, c: BuyProxy) -> None:
        self._c = c

    def list(self) -> List[Balance]:
        """Spendable GB per product, including GB still being added after a payment."""
        return self._c._send(spec.balances_list())


class _Plans:
    def __init__(self, c: BuyProxy) -> None:
        self._c = c

    def list(self) -> List[Plan]:
        return self._c._send(spec.plans_list())

    def generate(
        self,
        plan_id: str,
        *,
        protocol: Optional[str] = None,
        count: Optional[int] = None,
        country: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        isp: Optional[str] = None,
        sticky_minutes: Optional[int] = None,
    ) -> GeneratedProxies:
        """Generate proxy lines against one of your plans. Lines are on-demand — don't store them.

        Omit ``sticky_minutes`` for a fresh IP per request (rotating)."""
        return self._c._send(spec.plans_generate(plan_id, protocol, count, country, state, city, isp, sticky_minutes))


class _Topup:
    def __init__(self, c: BuyProxy) -> None:
        self._c = c

    def card(
        self,
        *,
        product_key: Optional[str] = None,
        gb: Optional[int] = None,
        plan: Optional[str] = None,
        interval: Optional[str] = None,
    ) -> CardCheckout:
        """Card checkout via Stripe: ``card(product_key="residential", gb=10)`` or ``card(plan="pro", interval="year")``."""
        return self._c._send(spec.topup_card(product_key, gb, plan, interval))

    def crypto(self, *, product_key: str, gb: int) -> CryptoCheckout:
        """Crypto top-up (pay-as-you-go only)."""
        return self._c._send(spec.topup_crypto(product_key, gb))


class _Transactions:
    def __init__(self, c: BuyProxy) -> None:
        self._c = c

    def list(self, *, limit: Optional[int] = None) -> List[Transaction]:
        return self._c._send(spec.transactions_list(limit))

    def get(self, transaction_id: str) -> Transaction:
        return self._c._send(spec.transactions_get(transaction_id))

    def wait(self, transaction_id: str, *, timeout: float = 600.0, interval: float = 3.0) -> Transaction:
        """Poll until the payment settles (``succeeded`` or ``failed``)."""
        deadline = time.monotonic() + timeout
        while True:
            tx = self.get(transaction_id)
            if tx.status != "pending":
                return tx
            if time.monotonic() + interval > deadline:
                raise BuyProxyError(f"Payment {transaction_id} is still pending after waiting")
            time.sleep(interval)


class _Customers:
    def __init__(self, c: BuyProxy) -> None:
        self._c = c

    def list(self, *, status: Optional[str] = None) -> List[Customer]:
        return self._c._send(spec.customers_list(status))

    def create(self, label: str) -> Customer:
        """Creates an isolated sub-account with no bandwidth — fund it with :meth:`allocate`."""
        return self._c._send(spec.customers_create(label))

    def get(self, username: str) -> CustomerDetail:
        return self._c._send(spec.customers_get(username))

    def update(self, username: str, *, label: Optional[str] = None, status: Optional[str] = None) -> Customer:
        """Rename and/or suspend (``"suspended"``) / reactivate (``"active"``)."""
        return self._c._send(spec.customers_update(username, label, status))

    def usage(self, username: str) -> CustomerUsage:
        return self._c._send(spec.customers_usage(username))

    def allocate(self, username: str, *, product_key: str, gb: int, idempotency_key: Optional[str] = None) -> Allocation:
        """Move GB from your pool onto a customer. Pass ``idempotency_key`` to make retries safe."""
        return self._c._send(spec.customers_allocate(username, product_key, gb, idempotency_key))

    def generate(
        self,
        username: str,
        *,
        plan_id: str,
        protocol: Optional[str] = None,
        count: Optional[int] = None,
        country: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        isp: Optional[str] = None,
        sticky_minutes: Optional[int] = None,
    ) -> GeneratedProxies:
        return self._c._send(spec.customers_generate(username, plan_id, protocol, count, country, state, city, isp, sticky_minutes))


class _Pool:
    def __init__(self, c: BuyProxy) -> None:
        self._c = c

    def get(self) -> List[PoolEntry]:
        """Your unallocated bandwidth, per product."""
        return self._c._send(spec.pool_get())

    def topup_card(self, *, product_key: str, gb: int) -> CardCheckout:
        return self._c._send(spec.pool_topup_card(product_key, gb))

    def topup_crypto(self, *, product_key: str, gb: int) -> CryptoCheckout:
        return self._c._send(spec.pool_topup_crypto(product_key, gb))


class _Reseller:
    """Reseller API — needs a ``bp_live_`` key on a Business plan or higher."""

    def __init__(self, c: BuyProxy) -> None:
        self._c = c
        self.customers = _Customers(c)
        self.pool = _Pool(c)

    def me(self) -> ResellerSummary:
        return self._c._send(spec.reseller_me())


# --- Async -----------------------------------------------------------------


class AsyncBuyProxy(_Base):
    """Async twin of :class:`BuyProxy` — identical API, every call is awaitable.

    >>> async with AsyncBuyProxy() as bp:
    ...     result = await bp.plans.generate(plan_id, country="US")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 2,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        super().__init__(api_key, base_url, timeout, max_retries)
        self._http = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_http = http_client is None
        self.products = _AProducts(self)
        self.auth = _AAuth(self)
        self.account = _AAccount(self)
        self.balances = _ABalances(self)
        self.plans = _APlans(self)
        self.topup = _ATopup(self)
        self.transactions = _ATransactions(self)
        self.reseller = _AReseller(self)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> "AsyncBuyProxy":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _send(self, req: spec.Request[T]) -> T:
        kwargs = self._prepare(req)
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._http.request(**kwargs)
            except httpx.TimeoutException as exc:
                raise APITimeoutError(f"Request timed out after {self.timeout}s") from exc
            except httpx.TransportError as exc:
                if req.retry_5xx and attempt < self.max_retries:
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise APIConnectionError(f"Could not reach BuyProxy: {exc}") from exc
            wait = self._decide(req, response, attempt, self.max_retries)
            if wait is not None:
                await asyncio.sleep(wait)
                continue
            return self._finish(req, response)
        raise AssertionError("unreachable")  # pragma: no cover


class _AProducts:
    def __init__(self, c: AsyncBuyProxy) -> None:
        self._c = c

    async def list(self) -> Catalog:
        return await self._c._send(spec.products_list())


class _AAuth:
    def __init__(self, c: AsyncBuyProxy) -> None:
        self._c = c

    async def signup(self, email: str, password: str, name: Optional[str] = None) -> SignupResult:
        return await self._c._send(spec.signup(email, password, name))

    async def verify_otp(self, email: str, code: str) -> VerifyResult:
        return await self._c._send(spec.verify_otp(email, code))

    async def resend_otp(self, email: str) -> None:
        await self._c._send(spec.resend_otp(email))


class _AAccount:
    def __init__(self, c: AsyncBuyProxy) -> None:
        self._c = c

    async def get(self) -> Account:
        return await self._c._send(spec.account_get())


class _ABalances:
    def __init__(self, c: AsyncBuyProxy) -> None:
        self._c = c

    async def list(self) -> List[Balance]:
        return await self._c._send(spec.balances_list())


class _APlans:
    def __init__(self, c: AsyncBuyProxy) -> None:
        self._c = c

    async def list(self) -> List[Plan]:
        return await self._c._send(spec.plans_list())

    async def generate(
        self,
        plan_id: str,
        *,
        protocol: Optional[str] = None,
        count: Optional[int] = None,
        country: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        isp: Optional[str] = None,
        sticky_minutes: Optional[int] = None,
    ) -> GeneratedProxies:
        return await self._c._send(spec.plans_generate(plan_id, protocol, count, country, state, city, isp, sticky_minutes))


class _ATopup:
    def __init__(self, c: AsyncBuyProxy) -> None:
        self._c = c

    async def card(
        self,
        *,
        product_key: Optional[str] = None,
        gb: Optional[int] = None,
        plan: Optional[str] = None,
        interval: Optional[str] = None,
    ) -> CardCheckout:
        return await self._c._send(spec.topup_card(product_key, gb, plan, interval))

    async def crypto(self, *, product_key: str, gb: int) -> CryptoCheckout:
        return await self._c._send(spec.topup_crypto(product_key, gb))


class _ATransactions:
    def __init__(self, c: AsyncBuyProxy) -> None:
        self._c = c

    async def list(self, *, limit: Optional[int] = None) -> List[Transaction]:
        return await self._c._send(spec.transactions_list(limit))

    async def get(self, transaction_id: str) -> Transaction:
        return await self._c._send(spec.transactions_get(transaction_id))

    async def wait(self, transaction_id: str, *, timeout: float = 600.0, interval: float = 3.0) -> Transaction:
        deadline = time.monotonic() + timeout
        while True:
            tx = await self.get(transaction_id)
            if tx.status != "pending":
                return tx
            if time.monotonic() + interval > deadline:
                raise BuyProxyError(f"Payment {transaction_id} is still pending after waiting")
            await asyncio.sleep(interval)


class _ACustomers:
    def __init__(self, c: AsyncBuyProxy) -> None:
        self._c = c

    async def list(self, *, status: Optional[str] = None) -> List[Customer]:
        return await self._c._send(spec.customers_list(status))

    async def create(self, label: str) -> Customer:
        return await self._c._send(spec.customers_create(label))

    async def get(self, username: str) -> CustomerDetail:
        return await self._c._send(spec.customers_get(username))

    async def update(self, username: str, *, label: Optional[str] = None, status: Optional[str] = None) -> Customer:
        return await self._c._send(spec.customers_update(username, label, status))

    async def usage(self, username: str) -> CustomerUsage:
        return await self._c._send(spec.customers_usage(username))

    async def allocate(self, username: str, *, product_key: str, gb: int, idempotency_key: Optional[str] = None) -> Allocation:
        return await self._c._send(spec.customers_allocate(username, product_key, gb, idempotency_key))

    async def generate(
        self,
        username: str,
        *,
        plan_id: str,
        protocol: Optional[str] = None,
        count: Optional[int] = None,
        country: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        isp: Optional[str] = None,
        sticky_minutes: Optional[int] = None,
    ) -> GeneratedProxies:
        return await self._c._send(spec.customers_generate(username, plan_id, protocol, count, country, state, city, isp, sticky_minutes))


class _APool:
    def __init__(self, c: AsyncBuyProxy) -> None:
        self._c = c

    async def get(self) -> List[PoolEntry]:
        return await self._c._send(spec.pool_get())

    async def topup_card(self, *, product_key: str, gb: int) -> CardCheckout:
        return await self._c._send(spec.pool_topup_card(product_key, gb))

    async def topup_crypto(self, *, product_key: str, gb: int) -> CryptoCheckout:
        return await self._c._send(spec.pool_topup_crypto(product_key, gb))


class _AReseller:
    def __init__(self, c: AsyncBuyProxy) -> None:
        self._c = c
        self.customers = _ACustomers(c)
        self.pool = _APool(c)

    async def me(self) -> ResellerSummary:
        return await self._c._send(spec.reseller_me())
