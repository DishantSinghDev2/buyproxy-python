"""Official BuyProxy SDK — residential, mobile, ISP and datacenter proxies over a typed Python API.

    from buyproxy import BuyProxy

    bp = BuyProxy()  # reads BUYPROXY_API_KEY
    plan = bp.plans.list()[0]
    proxy = bp.plans.generate(plan.id, country="US").proxies[0]
    requests.get("https://api.ipify.org", proxies=proxy.to_requests())
"""

from ._version import __version__
from .client import DEFAULT_BASE_URL, AsyncBuyProxy, BuyProxy
from .errors import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BuyProxyError,
    InsufficientBandwidthError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .models import (
    Account,
    Allocation,
    Balance,
    BillingInterval,
    CardCheckout,
    Catalog,
    CryptoCheckout,
    Customer,
    CustomerDetail,
    CustomerStatus,
    CustomerUsage,
    PaidPlan,
    Plan,
    PlanName,
    PoolEntry,
    Product,
    ProductKey,
    ResellerSummary,
    Transaction,
    TransactionStatus,
)
from .proxy import GeneratedProxies, ProxyEndpoint, ProxyProtocol

__all__ = [
    "__version__", "DEFAULT_BASE_URL", "BuyProxy", "AsyncBuyProxy", "ProxyEndpoint", "GeneratedProxies", "ProxyProtocol",
    "BuyProxyError", "ValidationError", "AuthenticationError", "InsufficientBandwidthError", "PermissionDeniedError",
    "NotFoundError", "RateLimitError", "ServerError", "APIConnectionError", "APITimeoutError",
    "Account", "Allocation", "Balance", "BillingInterval", "CardCheckout", "Catalog", "CryptoCheckout", "Customer",
    "CustomerDetail", "CustomerStatus", "CustomerUsage", "PaidPlan", "Plan", "PlanName", "PoolEntry", "Product",
    "ProductKey", "ResellerSummary", "Transaction", "TransactionStatus",
]
