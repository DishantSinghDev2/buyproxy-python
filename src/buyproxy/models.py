"""Typed response models. Unknown fields from newer API versions are ignored, never an error."""

from __future__ import annotations

import dataclasses
import sys
import typing
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Type, TypeVar

ProductKey = Literal["residential", "premium", "isp", "mobile", "ipv4", "ipv6"]
PlanName = Literal["free", "pro", "business", "advanced", "enterprise"]
PaidPlan = Literal["pro", "business", "advanced"]
BillingInterval = Literal["month", "year"]
CustomerStatus = Literal["active", "suspended"]
TransactionStatus = Literal["pending", "succeeded", "failed"]

T = TypeVar("T")


def _convert(tp: Any, value: Any) -> Any:
    if value is None:
        return None
    origin = typing.get_origin(tp)
    if origin is typing.Union:
        inner = [a for a in typing.get_args(tp) if a is not type(None)]
        return _convert(inner[0], value) if len(inner) == 1 else value
    if origin in (list, List):
        return [_convert(typing.get_args(tp)[0], v) for v in value]
    if isinstance(tp, type) and dataclasses.is_dataclass(tp) and isinstance(value, dict):
        return from_dict(tp, value)
    return value


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:  # noqa: UP006
    """Build a dataclass from an API dict (camelCase keys), recursing into nested dataclasses and lists."""
    hints = typing.get_type_hints(cls, vars(sys.modules[cls.__module__]))
    kwargs = {
        f.name: _convert(hints[f.name], data[_camel(f.name)])
        for f in dataclasses.fields(cls)  # type: ignore[arg-type]
        if _camel(f.name) in data
    }
    return cls(**kwargs)


# --- Catalog ---------------------------------------------------------------


@dataclass(frozen=True)
class Product:
    product_key: str
    product_id: str
    name: str
    description: str
    min_gb: int
    price_per_gb_cents: Optional[int]
    currency: str


@dataclass(frozen=True)
class VolumeBonus:
    threshold_gb: int
    rate: float


@dataclass(frozen=True)
class PlanPrice:
    plan: str
    monthly_price_cents: int
    included_gb: float


@dataclass(frozen=True)
class Catalog:
    products: List[Product]
    volume_bonus: VolumeBonus
    plans: List[PlanPrice]


# --- Account ---------------------------------------------------------------


@dataclass(frozen=True)
class Account:
    email: str
    name: str
    plan: str
    plan_expires_at: Optional[str]
    #: Lifetime GB credited. Spendable per-product balances come from ``balances.list()``.
    balance_gb: float
    created_at: str


@dataclass(frozen=True)
class Balance:
    product_key: Optional[str]
    product_id: str
    #: Pass to ``plans.generate()``. ``None`` until the product has been funded once.
    plan_id: Optional[str]
    active_gb: float
    #: Paid for but still being added to the plan.
    pending_gb: float
    total_gb: float
    expires_at: Optional[str]


@dataclass(frozen=True)
class Targeting:
    country: bool
    state: bool
    city: bool
    isp: bool


@dataclass(frozen=True)
class PlanGenerateCapabilities:
    max_count: int
    #: ``0`` means this product has no sticky sessions.
    max_sticky_minutes: int
    protocols: List[str]
    targeting: Targeting


@dataclass(frozen=True)
class Plan:
    id: str
    product_id: str
    product_key: Optional[str]
    name: str
    label: Optional[str]
    data_gb_remaining: float
    data_gb_total: float
    expires_at: Optional[str]
    created_at: str
    generate: Optional[PlanGenerateCapabilities]


# --- Payments --------------------------------------------------------------


@dataclass(frozen=True)
class CardCheckout:
    #: Stripe Checkout (or the subscription settings page when switching an existing plan).
    pay_url: str
    #: ``None`` when ``pay_url`` is the subscription portal rather than a new payment.
    transaction_id: Optional[str]


@dataclass(frozen=True)
class CryptoCheckout:
    url: str
    transaction_id: str


@dataclass(frozen=True)
class Transaction:
    id: str
    kind: str
    status: str
    payment_method: str
    interval: Optional[str]
    amount_cents: int
    currency: str
    gb: Optional[float]
    product_key: Optional[str]
    plan: Optional[str]
    reseller_pool: bool
    created_at: str


# --- Reseller --------------------------------------------------------------


@dataclass(frozen=True)
class PoolEntry:
    product_key: str
    product_id: str
    label: str
    gb: float


@dataclass(frozen=True)
class ResellerSummary:
    email: str
    customer_count: int
    active_customer_count: int
    pool: List[PoolEntry]


@dataclass(frozen=True)
class Customer:
    username: str
    label: str
    status: str
    created_at: str


@dataclass(frozen=True)
class PendingAllocation:
    product_id: str
    product_key: Optional[str]
    gb: float


@dataclass(frozen=True)
class CustomerPlan(Plan):
    remaining_gb: float = 0.0


@dataclass(frozen=True)
class CustomerDetail:
    username: str
    label: str
    status: str
    created_at: str
    plans: List[CustomerPlan]
    #: GB allocated but still being added to a plan.
    pending: List[PendingAllocation]


@dataclass(frozen=True)
class UsagePlan:
    id: str
    product_id: str
    product_key: Optional[str]
    remaining_gb: float
    total_gb: float
    used_gb: float
    expires_at: Optional[str]


@dataclass(frozen=True)
class CustomerUsage:
    plans: List[UsagePlan]
    pending: List[PendingAllocation]


@dataclass(frozen=True)
class Allocation:
    product_key: str
    product_id: str
    gb: int
    #: ``True`` when this idempotency key was already used — nothing new was moved.
    already_applied: bool
    pool_remaining_gb: float


@dataclass(frozen=True)
class SignupResult:
    ok: bool
    cooldown_seconds: Optional[int] = None


@dataclass(frozen=True)
class VerifiedUser:
    email: str
    name: str


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    is_new: bool
    user: VerifiedUser
