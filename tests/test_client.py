import httpx
import pytest
import respx

from buyproxy import (
    AsyncBuyProxy,
    AuthenticationError,
    BuyProxy,
    InsufficientBandwidthError,
    NotFoundError,
    RateLimitError,
    ServerError,
)

BASE = "https://www.buyproxy.org"
ACCOUNT = {"email": "a@b.co", "name": "A", "plan": "pro", "planExpiresAt": None, "balanceGb": 4.2, "createdAt": "2026-10-01T00:00:00Z"}


@respx.mock
def test_sends_key_json_and_user_agent() -> None:
    route = respx.post(f"{BASE}/v1/plans/plan%201/generate").respond(json={"lines": ["u:p@gw.buyproxy.org:6969"]})
    out = BuyProxy("bp_key_x").plans.generate("plan 1", protocol="socks5", count=1)
    req = route.calls[0].request
    assert req.headers["x-api-key"] == "bp_key_x"
    assert req.headers["user-agent"].startswith("buyproxy-python/")
    assert req.content == b'{"protocol":"socks5","count":1}'
    assert out.proxies[0].protocol == "socks5"


@respx.mock
def test_models_are_typed_from_camel_case() -> None:
    respx.get(f"{BASE}/v1/account").respond(json=ACCOUNT)
    account = BuyProxy("bp_key_x").account.get()
    assert account.balance_gb == 4.2 and account.plan_expires_at is None and account.created_at.startswith("2026")


@respx.mock
def test_nested_models_and_unknown_fields() -> None:
    plan = {
        "id": "p", "productId": "x", "productKey": "residential", "name": "N", "label": None, "dataGbRemaining": 1.0,
        "dataGbTotal": 2.0, "expiresAt": None, "createdAt": "t", "brandNewField": 1,
        "generate": {"maxCount": 1000, "maxStickyMinutes": 60, "protocols": ["http"], "targeting": {"country": True, "state": False, "city": False, "isp": False}},
    }
    respx.get(f"{BASE}/v1/plans").respond(json={"plans": [plan]})
    [p] = BuyProxy("bp_key_x").plans.list()
    assert p.generate is not None and p.generate.max_sticky_minutes == 60 and p.generate.targeting.country is True


def test_requires_a_key_except_public_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BUYPROXY_API_KEY", raising=False)
    with respx.mock:
        respx.get(f"{BASE}/v1/products").respond(json={"products": [], "volumeBonus": {"thresholdGb": 100, "rate": 0.1}, "plans": []})
        bp = BuyProxy()
        with pytest.raises(AuthenticationError):
            bp.account.get()
        assert bp.products.list().volume_bonus.threshold_gb == 100


def test_reads_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUYPROXY_API_KEY", "bp_live_env")
    assert BuyProxy().key_kind == "reseller"


@respx.mock
@pytest.mark.parametrize("status,exc", [(401, AuthenticationError), (402, InsufficientBandwidthError), (404, NotFoundError)])
def test_status_to_exception(status: int, exc: type) -> None:
    respx.get(f"{BASE}/v1/account").respond(status, json={"error": "nope"})
    with pytest.raises(exc) as info:
        BuyProxy("bp_key_x").account.get()
    assert info.value.status == status and "nope" in str(info.value)


@respx.mock
def test_retries_429_then_succeeds() -> None:
    route = respx.get(f"{BASE}/v1/account").mock(side_effect=[httpx.Response(429, json={"error": "slow"}, headers={"retry-after": "0"}), httpx.Response(200, json=ACCOUNT)])
    assert BuyProxy("bp_key_x").account.get().plan == "pro"
    assert route.call_count == 2


@respx.mock
def test_rate_limit_error_after_retries() -> None:
    route = respx.get(f"{BASE}/v1/account").respond(429, json={"error": "slow"}, headers={"retry-after": "0"})
    with pytest.raises(RateLimitError):
        BuyProxy("bp_key_x").account.get()
    assert route.call_count == 3


@respx.mock
def test_post_not_retried_on_503_unless_idempotent() -> None:
    route = respx.post(f"{BASE}/v1/customers/c/allocate").respond(503, json={"error": "down"})
    with pytest.raises(ServerError):
        BuyProxy("bp_key_x").reseller.customers.allocate("c", product_key="premium", gb=1)
    assert route.call_count == 1

    route.mock(side_effect=[httpx.Response(503, json={"error": "down"}), httpx.Response(201, json={"productKey": "premium", "productId": "x", "gb": 1, "alreadyApplied": False, "poolRemainingGb": 0})])
    out = BuyProxy("bp_key_x").reseller.customers.allocate("c", product_key="premium", gb=1, idempotency_key="k1")
    assert out.already_applied is False and route.calls.last.request.headers["idempotency-key"] == "k1"


@respx.mock
def test_topup_card_validates_arguments() -> None:
    with pytest.raises(ValueError):
        BuyProxy("bp_key_x").topup.card()


@respx.mock
def test_wait_polls_until_settled() -> None:
    tx = {"id": "st_1", "kind": "topup", "status": "pending", "paymentMethod": "card", "interval": None, "amountCents": 1, "currency": "usd", "gb": 1, "productKey": None, "plan": None, "resellerPool": False, "createdAt": "t"}
    respx.get(f"{BASE}/v1/transactions/st_1").mock(side_effect=[httpx.Response(200, json=tx), httpx.Response(200, json={**tx, "status": "succeeded"})])
    assert BuyProxy("bp_key_x").transactions.wait("st_1", interval=0.01).status == "succeeded"


@respx.mock
async def test_async_client_matches_sync() -> None:
    respx.get(f"{BASE}/v1/account").respond(json=ACCOUNT)
    async with AsyncBuyProxy("bp_key_x") as bp:
        assert (await bp.account.get()).balance_gb == 4.2
