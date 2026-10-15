"""Serve the existing weather workbench without exposing the internal tool bridge."""

import os
import re
import httpx
from fastapi import Request
from starlette.responses import Response, JSONResponse

PUBLIC_APIS = {
    "/api/" + name: {"GET", "HEAD"}
    for name in (
        "rain",
        "weather",
        "warnings",
        "warningInfo",
        "forecast",
        "local",
        "tides",
        "nowcast",
        "assistant/status",
        "climate/series",
        "workspace/status",
        "workspace/audit",
    )
}
PUBLIC_APIS.update(
    {
        "/api/assistant": {"POST"},
        "/api/agent/inspect": {"POST"},
        "/api/workspace": {"GET", "HEAD", "PUT"},
        "/api/mini/agent-jobs": {"POST"},
    }
)


async def weather_gateway(request: Request, transport=None):
    path = request.url.path
    request.state.weather_surface = True
    if path.startswith("/api/"):
        methods = PUBLIC_APIS.get(path)
        if re.fullmatch(r"/api/mini/agent-jobs/[A-Za-z0-9-]{1,80}", path):
            methods = {"GET", "HEAD"}
        if not methods:
            return JSONResponse({"detail": "接口不存在"}, status_code=404)
        if request.method not in methods:
            return Response(
                status_code=405, headers={"Allow": ", ".join(sorted(methods))}
            )
    elif request.method not in {"GET", "HEAD"}:
        return Response(status_code=405)
    base = os.getenv("WEATHER_SERVICE_URL", "http://127.0.0.1:8096").rstrip("/")
    headers = {
        key: request.headers[key]
        for key in ("content-type", "accept")
        if key in request.headers
    }
    if path.startswith("/api/workspace") and "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    # Enterprise cookies and internal service credentials never cross this boundary.
    try:
        async with httpx.AsyncClient(
            transport=transport,
            trust_env=False,
            timeout=httpx.Timeout(180, connect=5),
            follow_redirects=False,
        ) as client:
            upstream = await client.request(
                request.method,
                base + path,
                params=request.query_params.multi_items(),
                headers=headers,
                content=await request.body(),
            )
        return Response(
            upstream.content,
            status_code=upstream.status_code,
            headers={
                key: upstream.headers[key]
                for key in ("content-type",)
                if key in upstream.headers
            },
        )
    except httpx.RequestError:
        return JSONResponse(
            {"detail": "天气数据服务暂时不可用，请检查天气容器状态后重试。"},
            status_code=503,
        )
