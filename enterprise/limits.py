from starlette.responses import JSONResponse


class BodyLimit:
    """Bound both Content-Length and chunked bodies before multipart/JSON parsing."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        limit = (
            2200000
            if b"multipart/form-data" in headers.get(b"content-type", b"")
            else 64000
        )
        if scope.get("path") == "/api/workspace":
            limit = 4000000
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                return await JSONResponse(
                    {"detail": "请求超过大小限制"}, status_code=413
                )(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body"):
                break
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {
                    "type": "http.request",
                    "body": b"".join(chunks),
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, replay, send)
