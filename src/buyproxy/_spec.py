"""Endpoint definitions shared by the sync and async clients, so paths, bodies and parsing live in one place."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
from urllib.parse import quote

from . import models as m
from .proxy import GeneratedProxies, ProxyProtocol

T = TypeVar("T")


def _identity(data: Any) -> Any:
    return data


@dataclass(frozen=True)
class Request(Generic[T]):
    method: str
    path: str
    query: Optional[Dict[str, Any]] = None
    body: Optional[Dict[str, Any]] = None
    headers: Dict[str, str] = field(default_factory=dict)
    #: Public endpoints (catalog, signup) work without a key.
    auth: bool = True
    #: Safe to retry on 5xx — GETs, and writes carrying an idempotency key.
    retry_5xx: bool = False
    parse: Callable[[Any], T] = _identity


def _seg(value: str) -> str:
    return quote(value, safe="")


def _compact(**fields: Any) -> Dict[str, Any]:
    """Drop unset (``None``) fields so defaults are decided by the API, not the SDK."""
    return {k: v for k, v in fields.items() if v is not None}


def _generate_body(protocol: Optional[str], count: Optional[int], country: Optional[str], state: Optional[str],
                   city: Optional[str], isp: Optional[str], sticky_minutes: Optional[int], **extra: Any) -> Dict[str, Any]:
    return _compact(**extra, protocol=protocol, count=count, country=country, state=state, city=city, isp=isp, stickyMinutes=sticky_minutes)


def _proxies(protocol: Optional[str]) -> Callable[[Any], GeneratedProxies]:
    proto: ProxyProtocol = "socks5" if protocol == "socks5" else "http"
    return lambda data: GeneratedProxies.from_lines(data["lines"], proto)


# --- Public ---------------------------------------------------------------

def products_list() -> Request[m.Catalog]:
    return Request("GET", "/v1/products", auth=False, retry_5xx=True, parse=lambda d: m.from_dict(m.Catalog, d))


def signup(email: str, password: str, name: Optional[str]) -> Request[m.SignupResult]:
    return Request("POST", "/api/auth/signup", body=_compact(email=email, password=password, name=name), auth=False,
                   parse=lambda d: m.from_dict(m.SignupResult, d))


def verify_otp(email: str, code: str) -> Request[m.VerifyResult]:
    return Request("POST", "/api/auth/verify-otp", body={"email": email, "code": code}, auth=False,
                   parse=lambda d: m.from_dict(m.VerifyResult, d))


def resend_otp(email: str) -> Request[None]:
    return Request("POST", "/api/auth/resend-otp", body={"email": email}, auth=False, parse=lambda d: None)


# --- Personal API ----------------------------------------------------------

def account_get() -> Request[m.Account]:
    return Request("GET", "/v1/account", retry_5xx=True, parse=lambda d: m.from_dict(m.Account, d))


def balances_list() -> Request[List[m.Balance]]:
    return Request("GET", "/v1/balances", retry_5xx=True, parse=lambda d: [m.from_dict(m.Balance, b) for b in d["balances"]])


def plans_list() -> Request[List[m.Plan]]:
    return Request("GET", "/v1/plans", retry_5xx=True, parse=lambda d: [m.from_dict(m.Plan, p) for p in d["plans"]])


def plans_generate(plan_id: str, protocol: Optional[str], count: Optional[int], country: Optional[str], state: Optional[str],
                   city: Optional[str], isp: Optional[str], sticky_minutes: Optional[int]) -> Request[GeneratedProxies]:
    return Request("POST", f"/v1/plans/{_seg(plan_id)}/generate",
                   body=_generate_body(protocol, count, country, state, city, isp, sticky_minutes), parse=_proxies(protocol))


def topup_card(product_key: Optional[str], gb: Optional[int], plan: Optional[str], interval: Optional[str]) -> Request[m.CardCheckout]:
    if plan is not None:
        body = _compact(kind="plan", plan=plan, interval=interval)
    elif product_key is not None and gb is not None:
        body = {"kind": "topup", "productKey": product_key, "gb": gb}
    else:
        raise ValueError("Pass either product_key and gb (a top-up) or plan (a subscription).")
    return Request("POST", "/v1/topup/card", body=body, parse=lambda d: m.from_dict(m.CardCheckout, d))


def topup_crypto(product_key: str, gb: int) -> Request[m.CryptoCheckout]:
    return Request("POST", "/v1/topup/crypto", body={"kind": "topup", "productKey": product_key, "gb": gb},
                   parse=lambda d: m.from_dict(m.CryptoCheckout, d))


def transactions_list(limit: Optional[int]) -> Request[List[m.Transaction]]:
    return Request("GET", "/v1/transactions", query=_compact(limit=limit), retry_5xx=True,
                   parse=lambda d: [m.from_dict(m.Transaction, t) for t in d["transactions"]])


def transactions_get(transaction_id: str) -> Request[m.Transaction]:
    return Request("GET", f"/v1/transactions/{_seg(transaction_id)}", retry_5xx=True, parse=lambda d: m.from_dict(m.Transaction, d))


# --- Reseller API ----------------------------------------------------------

def reseller_me() -> Request[m.ResellerSummary]:
    return Request("GET", "/v1/me", retry_5xx=True, parse=lambda d: m.from_dict(m.ResellerSummary, d))


def customers_list(status: Optional[str]) -> Request[List[m.Customer]]:
    return Request("GET", "/v1/customers", query=_compact(status=status), retry_5xx=True,
                   parse=lambda d: [m.from_dict(m.Customer, c) for c in d["customers"]])


def customers_create(label: str) -> Request[m.Customer]:
    return Request("POST", "/v1/customers", body={"label": label}, parse=lambda d: m.from_dict(m.Customer, d))


def customers_get(username: str) -> Request[m.CustomerDetail]:
    return Request("GET", f"/v1/customers/{_seg(username)}", retry_5xx=True, parse=lambda d: m.from_dict(m.CustomerDetail, d))


def customers_update(username: str, label: Optional[str], status: Optional[str]) -> Request[m.Customer]:
    return Request("PATCH", f"/v1/customers/{_seg(username)}", body=_compact(label=label, status=status),
                   parse=lambda d: m.from_dict(m.Customer, d))


def customers_usage(username: str) -> Request[m.CustomerUsage]:
    return Request("GET", f"/v1/customers/{_seg(username)}/usage", retry_5xx=True, parse=lambda d: m.from_dict(m.CustomerUsage, d))


def customers_allocate(username: str, product_key: str, gb: int, idempotency_key: Optional[str]) -> Request[m.Allocation]:
    return Request("POST", f"/v1/customers/{_seg(username)}/allocate", body={"productKey": product_key, "gb": gb},
                   headers={"Idempotency-Key": idempotency_key} if idempotency_key else {},
                   retry_5xx=idempotency_key is not None, parse=lambda d: m.from_dict(m.Allocation, d))


def customers_generate(username: str, plan_id: str, protocol: Optional[str], count: Optional[int], country: Optional[str],
                       state: Optional[str], city: Optional[str], isp: Optional[str], sticky_minutes: Optional[int]) -> Request[GeneratedProxies]:
    return Request("POST", f"/v1/customers/{_seg(username)}/generate",
                   body=_generate_body(protocol, count, country, state, city, isp, sticky_minutes, planId=plan_id),
                   parse=_proxies(protocol))


def pool_get() -> Request[List[m.PoolEntry]]:
    return Request("GET", "/v1/pool", retry_5xx=True, parse=lambda d: [m.from_dict(m.PoolEntry, p) for p in d["pool"]])


def pool_topup_card(product_key: str, gb: int) -> Request[m.CardCheckout]:
    return Request("POST", "/v1/pool/topup/card", body={"productKey": product_key, "gb": gb}, parse=lambda d: m.from_dict(m.CardCheckout, d))


def pool_topup_crypto(product_key: str, gb: int) -> Request[m.CryptoCheckout]:
    return Request("POST", "/v1/pool/topup/crypto", body={"productKey": product_key, "gb": gb}, parse=lambda d: m.from_dict(m.CryptoCheckout, d))


__all__: List[str] = [name for name in dir() if not name.startswith("_") and name not in {"annotations"}]
