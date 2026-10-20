from enterprise.graph import Bridge


def test_internal_bridge_ignores_workstation_proxy(monkeypatch):
    calls = []

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {"tools": [], "result": {"sources": 44}}

    class Client:
        def __init__(self, **options):
            assert options["trust_env"] is False
            calls.append(options)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            assert url == "http://127.0.0.1:8096/api/internal/workflow/tool"
            assert kwargs["headers"]["Authorization"].startswith("Bearer ")
            return Reply()

    monkeypatch.setenv("WEATHER_SERVICE_URL", "http://127.0.0.1:8096")
    monkeypatch.setenv("INTERNAL_WORKFLOW_TOKEN", "isolated-test-token")
    monkeypatch.setattr("enterprise.graph.httpx.Client", Client)
    bridge = Bridge()
    assert bridge.catalog() == []
    assert bridge.call("knowledge_inventory", {}, "snapshot") == {"sources": 44}
    assert len(calls) == 2
