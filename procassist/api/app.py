"""The replica host and the ProcAssist API in one FastAPI app, served on three ports.

Three ports because Dataset B has three portals, and `(origin, route)` is the key the whole
module map turns on (`analysis/evidence/modules.py`). Serving all three queues off one port
would have meant inventing a routing scheme and then having the panel "detect" the host from
it, which would demonstrate nothing. The app resolves the definition from the request's own
Host header and path, exactly as the telemetry analysis resolves it from the address bar.

Everything served under the replica is synthetic and is badged as such on every page.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from ..adapters.audit import EVENT_TYPES, new_trace_id
from ..core.definitions import ModuleDefinition
from ..service import Service

HERE = os.path.dirname(os.path.abspath(__file__))
REPLICA = os.path.join(HERE, os.pardir, "replica")
TEMPLATES = os.path.join(REPLICA, "templates")
STATIC = os.path.join(REPLICA, "static")
PANEL = os.path.join(HERE, os.pardir, "panel")

#: Every page carries these, always visible. This is a replica of a synthetic capture, and a
#: screenshot of it must never be mistakable for a screenshot of a production system.
BADGES = ("SYNTHETIC", "REPLICA", "PRODUCTION-UNVERIFIED")

PORTS = (5132, 5133, 5134)


class PrepareRequest(BaseModel):
    record_id: str
    origin: Optional[str] = None
    route: Optional[str] = None
    trace_id: Optional[str] = None


class EventRequest(BaseModel):
    trace_id: str
    event_type: str
    record_id: Optional[str] = None
    definition_id: Optional[str] = None
    module_id: Optional[str] = None
    suggested: Optional[str] = None
    human_action: Optional[str] = None
    detail: Dict[str, Any] = Field(default_factory=dict)


def _origin_of(request: Request) -> str:
    host = request.headers.get("host") or request.url.netloc
    return f"{request.url.scheme}://{host}"


def create_app(service: Optional[Service] = None) -> FastAPI:
    svc = service or Service()
    app = FastAPI(title="ProcAssist replica", docs_url="/_docs", redoc_url=None)
    app.state.service = svc
    templates = Jinja2Templates(directory=TEMPLATES)
    app.mount("/_static", StaticFiles(directory=STATIC), name="static")
    app.mount("/_panel", StaticFiles(directory=PANEL), name="panel")

    def definition_here(request: Request, route: str) -> ModuleDefinition:
        origin = _origin_of(request)
        d = svc.defs.for_host(origin, route)
        if d is None:
            raise HTTPException(404, f"no queue is served at {origin}{route}")
        return d

    def chrome(request: Request, definition: Optional[ModuleDefinition]) -> Dict[str, Any]:
        return {
            "request": request,
            "badges": BADGES,
            "definition": definition,
            "origin": _origin_of(request),
            "all_definitions": svc.definitions(),
            "ports": PORTS,
        }

    # -- the replica host ---------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def portal(request: Request) -> Any:
        origin = _origin_of(request)
        here = [d for d in svc.definitions() if d.host.origin == origin]
        return templates.TemplateResponse(
            request, "portal.html", {**chrome(request, None), "here": here})

    @app.get("/{route_name}", response_class=HTMLResponse)
    def queue(request: Request, route_name: str) -> Any:
        definition = definition_here(request, "/" + route_name)
        rows = svc.queue(definition.definition_id)
        return templates.TemplateResponse(
            request, "queue.html", {**chrome(request, definition), "rows": rows})

    @app.get("/{route_name}/{record_id}", response_class=HTMLResponse)
    def detail(request: Request, route_name: str, record_id: str) -> Any:
        definition = definition_here(request, "/" + route_name)
        row = svc.record(record_id)
        if row is None or row["record_prefix"] != definition.record_prefix:
            raise HTTPException(404, f"{record_id} is not a record on this queue")
        return templates.TemplateResponse(
            request, "detail.html", {**chrome(request, definition), "row": row,
                                     "route_name": route_name})

    # -- the ProcAssist API -------------------------------------------------------------------

    @app.post("/v1/prepare")
    def prepare(body: PrepareRequest) -> JSONResponse:
        try:
            result = svc.prepare_record(body.record_id, trace_id=body.trace_id or new_trace_id())
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return JSONResponse(result.model_dump(mode="json"))

    @app.post("/v1/event")
    def event(body: EventRequest) -> JSONResponse:
        if body.event_type not in EVENT_TYPES:
            raise HTTPException(400, f"{body.event_type} is not an audited event type")
        row = svc.audit.append(
            body.trace_id, body.event_type,
            definition_id=body.definition_id, module_id=body.module_id,
            record_id=body.record_id, suggested=body.suggested,
            human_action=body.human_action, detail=body.detail)
        return JSONResponse({"seq": row["seq"], "row_hash": row["row_hash"]})

    @app.get("/v1/audit/tail")
    def audit_tail(n: int = 3) -> JSONResponse:
        return JSONResponse({"rows": svc.audit.tail(n), "count": svc.audit.count(),
                             "chain_ok": svc.audit.verify_chain()})

    @app.get("/v1/source/{document_id}/{clause_id}")
    def source(document_id: str, clause_id: str) -> JSONResponse:
        excerpt = svc.documents.excerpt(document_id, clause_id, 400)
        if excerpt is None:
            raise HTTPException(404, "no such clause capture")
        return JSONResponse(excerpt)

    return app


async def _serve(app: FastAPI, ports: List[int]) -> None:  # pragma: no cover - runtime only
    import uvicorn
    servers = [uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=p, log_level="warning"))
               for p in ports]
    await asyncio.gather(*(s.serve() for s in servers))


def main() -> None:  # pragma: no cover - runtime only
    app = create_app()
    print("ProcAssist replica — SYNTHETIC · REPLICA · PRODUCTION-UNVERIFIED")
    for d in sorted(app.state.service.definitions(), key=lambda x: x.host.origin):
        print(f"  {d.module_id}  {d.host.origin}{d.host.route:<22} {d.name_ja}")
    asyncio.run(_serve(app, list(PORTS)))
