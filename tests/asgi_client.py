"""A ~50-line ASGI caller, so the HTTP tests need no new dependency.

`fastapi.testclient.TestClient` requires httpx, which would be a fifth package beyond the four
sanctioned for this cycle. The app is an ASGI callable and the tests only need GET and POST
with a Host header, so calling it directly is both sufficient and a smaller surface than an
HTTP client would be. Standard library only.
"""
from __future__ import annotations

import asyncio
import json as _json
from typing import Any, Dict, List, Optional, Tuple


class Response:
    def __init__(self, status_code: int, headers: List[Tuple[bytes, bytes]], body: bytes):
        self.status_code = status_code
        self.headers = {k.decode(): v.decode() for k, v in headers}
        self.content = body

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def json(self) -> Any:
        return _json.loads(self.text)


class ASGIClient:
    """Calls an ASGI app in-process. GET and POST only; that is all these tests need."""

    def __init__(self, app: Any, default_host: str = "127.0.0.1:5133") -> None:
        self.app = app
        self.default_host = default_host

    def get(self, path: str, headers: Optional[Dict[str, str]] = None) -> Response:
        return self._call("GET", path, None, headers)

    def post(self, path: str, json: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None) -> Response:
        return self._call("POST", path, json, headers)

    def _call(self, method: str, path: str, json_body: Optional[Dict[str, Any]],
              headers: Optional[Dict[str, str]]) -> Response:
        raw, _, query = path.partition("?")
        hdrs = {"host": self.default_host}
        hdrs.update({k.lower(): v for k, v in (headers or {}).items()})
        body = b"" if json_body is None else _json.dumps(json_body).encode("utf-8")
        if json_body is not None:
            hdrs["content-type"] = "application/json"
            hdrs["content-length"] = str(len(body))

        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": method, "scheme": "http",
            "path": raw, "raw_path": raw.encode(), "query_string": query.encode(),
            "root_path": "", "client": ("127.0.0.1", 50000),
            "server": tuple(hdrs["host"].split(":")[:1]) + (int(hdrs["host"].split(":")[1]),),
            "headers": [(k.encode(), v.encode()) for k, v in hdrs.items()],
        }
        out: Dict[str, Any] = {"status": 500, "headers": [], "body": bytearray()}

        async def receive() -> Dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: Dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                out["status"] = message["status"]
                out["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                out["body"] += message.get("body", b"")

        asyncio.run(self.app(scope, receive, send))
        return Response(out["status"], out["headers"], bytes(out["body"]))
