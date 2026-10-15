import asyncio
import httpx
from fastapi.testclient import TestClient
from starlette.requests import Request
import enterprise.api as api
from enterprise.weather_gateway import weather_gateway


def test_unified_routes_keep_weather_home_and_enterprise_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "isolated-gateway-password-123")

    async def gateway(req):
        return await weather_gateway(
            req,
            httpx.MockTransport(
                lambda upstream: httpx.Response(
                    200,
                    text="original weather UI",
                    headers={"content-type": "text/html"},
                )
            ),
        )

    monkeypatch.setattr(api, "weather_gateway", gateway)
    with TestClient(
        api.create_app("sqlite:///" + str(tmp_path / "gateway.sqlite"))
    ) as client:
        home = client.get("/")
        assert home.text == "original weather UI"
        assert "'unsafe-inline'" in home.headers["content-security-policy"]
        console = client.get("/enterprise/")
        assert "loginView" in console.text
        assert 'class="workspace-switch" href="/"' in console.text
        assert "'unsafe-inline'" not in console.headers["content-security-policy"]
        assert (
            client.get("/enterprise", follow_redirects=False).headers["location"]
            == "/enterprise/"
        )
        assert client.get("/api/overview").status_code == 401
        assert client.post("/api/internal/workflow/tool", json={}).status_code == 404
        assert client.put("/api/workspace", content=b"x" * 70000).status_code == 200
        assert client.put("/api/workspace", content=b"x" * 4000001).status_code == 413
        assert (
            client.post(
                "/api/agent/inspect",
                json={},
                headers={"origin": "https://untrusted.invalid"},
            ).status_code
            == 403
        )


def request(path, method="GET", headers=(), query=b"", body=b""):
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": "http",
            "path": path,
            "query_string": query,
            "headers": headers,
            "server": ("localhost", 8100),
        },
        receive,
    )


def test_weather_proxy_preserves_query_and_isolates_credentials(monkeypatch):
    monkeypatch.setenv("WEATHER_SERVICE_URL", "http://weather:8095")

    def upstream(req):
        assert (
            str(req.url)
            == "http://weather:8095/api/climate/series?station=HKO&from=2025&to=2025"
        )
        assert "cookie" not in req.headers
        assert "authorization" not in req.headers
        assert "x-workflow-token" not in req.headers
        return httpx.Response(200, json={"records": []})

    result = asyncio.run(
        weather_gateway(
            request(
                "/api/climate/series",
                query=b"station=HKO&from=2025&to=2025",
                headers=[
                    (b"cookie", b"rg_session=private"),
                    (b"authorization", b"Bearer private"),
                    (b"x-workflow-token", b"private"),
                ],
            ),
            httpx.MockTransport(upstream),
        )
    )
    assert result.status_code == 200


def test_internal_bridge_and_unknown_api_never_forward():
    def forbidden(req):
        raise AssertionError("Private API reached weather upstream")

    for path in ("/api/internal/workflow/tool", "/api/unknown"):
        assert (
            asyncio.run(
                weather_gateway(request(path, "POST"), httpx.MockTransport(forbidden))
            ).status_code
            == 404
        )


def test_root_and_failure_are_not_replaced_with_enterprise_or_fake_data():
    result = asyncio.run(
        weather_gateway(
            request("/"),
            httpx.MockTransport(
                lambda req: httpx.Response(
                    200,
                    text="original weather UI",
                    headers={"content-type": "text/html"},
                )
            ),
        )
    )
    assert result.body == b"original weather UI"
    assert result.headers["content-type"] == "text/html"
    result = asyncio.run(
        weather_gateway(
            request("/api/rain"),
            httpx.MockTransport(
                lambda req: httpx.Response(502, json={"error": "upstream"})
            ),
        )
    )
    assert result.status_code == 502


def test_workspace_put_keeps_legacy_auth_and_body():
    def upstream(req):
        assert req.headers["authorization"] == "Bearer workspace-token"
        assert "cookie" not in req.headers
        assert "origin" not in req.headers
        assert req.content == b'{"revision":1}'
        return httpx.Response(200, json={"ok": True})

    result = asyncio.run(
        weather_gateway(
            request(
                "/api/workspace",
                "PUT",
                body=b'{"revision":1}',
                headers=[
                    (b"authorization", b"Bearer workspace-token"),
                    (b"cookie", b"rg_session=private"),
                    (b"origin", b"http://localhost:8100"),
                ],
            ),
            httpx.MockTransport(upstream),
        )
    )
    assert result.status_code == 200
