import base64
import asyncio
import threading

from fastapi import FastAPI, Request
import httpx

from auth import get_password_hash
from internal import OperatorAuthRateLimiter


class MutableClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def _basic(username: str, password: str) -> str:
    value = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {value}"


def _auth_test_app(internal):
    app = FastAPI()

    @app.get("/internal/customers")
    async def console(request: Request):
        operator = internal.require_platform_operator(request)
        return {"operator": operator}

    @app.get("/api/internal/customers")
    async def customers(request: Request):
        operator = internal.require_platform_operator(request)
        return {"operator": operator}

    @app.post("/api/internal/customers")
    async def mutate(request: Request):
        internal.require_internal_request(request)
        operator = internal.require_platform_operator(request)
        return {"operator": operator}

    return app


def test_internal_operator_auth_throttles_across_paths_and_recovers(monkeypatch):
    import internal

    operator = "rate-limit-operator"
    password = "DisposableOperatorPassword123!"
    monkeypatch.setenv("PLATFORM_OPERATOR_USERNAME", operator)
    monkeypatch.setenv("PLATFORM_OPERATOR_PASSWORD_HASH", get_password_hash(password))
    clock = MutableClock()
    limiter = OperatorAuthRateLimiter(
        failure_limit=5, window_seconds=600, cooldown_seconds=600,
        max_identities=32, clock=clock,
    )
    monkeypatch.setattr(internal, "operator_auth_limiter", limiter)
    async def scenario():
        transport = httpx.ASGITransport(app=_auth_test_app(internal), client=("direct-peer", 1234))
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
            assert (await client.get("/internal/customers", headers={
                "Authorization": _basic(operator, password)
            })).status_code == 200

            protected_paths = [
                "/internal/customers", "/api/internal/customers",
                "/internal/customers", "/api/internal/customers",
            ]
            for index, path in enumerate(protected_paths):
                response = await client.get(path, headers={
                    "Authorization": _basic(operator if index % 2 else "irrelevant-name", "wrong"),
                    "X-Forwarded-For": f"198.51.100.{index + 1}",
                    "X-Real-IP": f"203.0.113.{index + 1}",
                })
                assert response.status_code == 401

            # Malformed Basic credentials count as the fifth failure and cannot
            # reset the counter or evade it by switching paths/forwarding headers.
            limited = await client.get("/internal/customers", headers={
                "Authorization": "Basic !!!not-base64!!!",
                "X-Forwarded-For": "192.0.2.200",
            })
            assert limited.status_code == 429
            assert limited.headers["Retry-After"] == "600"

            still_limited = await client.get("/api/internal/customers", headers={
                "Authorization": "Bearer tenant-jwt-cannot-bypass",
                "X-Forwarded-For": "192.0.2.201",
            })
            assert still_limited.status_code == 429

            # Mutation verification remains independent and cannot clear the throttle.
            missing_header = await client.post("/api/internal/customers", headers={
                "Authorization": _basic(operator, password),
            }, json={})
            assert missing_header.status_code == 403
            assert (await client.get("/internal/customers", headers={
                "Authorization": _basic(operator, password)
            })).status_code == 429

            clock.now += 601
            recovered = await client.get("/internal/customers", headers={
                "Authorization": _basic(operator, password)
            })
            assert recovered.status_code == 200

    asyncio.run(scenario())


def test_operator_limiter_is_concurrent_and_memory_bounded():
    clock = MutableClock()
    limiter = OperatorAuthRateLimiter(
        failure_limit=5, window_seconds=600, cooldown_seconds=600,
        max_identities=8, clock=clock,
    )
    barrier = threading.Barrier(16)
    results = []

    def fail_together():
        barrier.wait()
        results.append(limiter.record_failure("same-direct-peer\0operator"))

    threads = [threading.Thread(target=fail_together) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 16
    assert sum(value > 0 for value in results) == 12
    assert limiter.retry_after("same-direct-peer\0operator") == 600

    for index in range(32):
        limiter.record_failure(f"peer-{index}\0operator")
    assert len(limiter._entries) == 8


def test_operator_credentials_are_not_logged(caplog, monkeypatch):
    import internal

    operator = "log-safety-operator"
    password = "NeverLogThisOperatorPassword123!"
    monkeypatch.setenv("PLATFORM_OPERATOR_USERNAME", operator)
    monkeypatch.setenv("PLATFORM_OPERATOR_PASSWORD_HASH", get_password_hash(password))
    monkeypatch.setattr(internal, "operator_auth_limiter", OperatorAuthRateLimiter())

    async def request_once():
        transport = httpx.ASGITransport(app=_auth_test_app(internal), client=("direct-peer", 1234))
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
            return await client.get("/internal/customers", headers={
                "Authorization": _basic(operator, password + "-wrong")
            })

    response = asyncio.run(request_once())
    assert response.status_code == 401
    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert operator not in rendered_logs
    assert password not in rendered_logs
