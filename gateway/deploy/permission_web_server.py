from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from websockets.exceptions import ConnectionClosed


WEB_ROOT = Path(os.getenv("HA_WEB_ROOT", "./hass_frontend")).resolve()
GATEWAY_HTTP_URL = os.getenv("PERMISSION_GATEWAY_URL", "http://127.0.0.1:18080").rstrip("/")
GATEWAY_WS_URL = GATEWAY_HTTP_URL.replace("http://", "ws://").replace("https://", "wss://")

app = FastAPI(title="HA Permission Web", version="0.1.0")


def mount_if_exists(route: str, directory: str) -> None:
    path = WEB_ROOT / directory
    if path.exists():
        app.mount(route, StaticFiles(directory=path), name=directory)


mount_if_exists("/static", "static")
mount_if_exists("/frontend_latest", "frontend_latest")
mount_if_exists("/frontend_es5", "frontend_es5")


@app.api_route("/healthz", methods=["GET", "HEAD"], response_model=None)
async def healthz(request: Request) -> Any:
    if request.method == "HEAD":
        return Response(status_code=200)
    return {
        "ok": True,
        "service": "ha-permission-web",
        "web_root": str(WEB_ROOT),
        "gateway": GATEWAY_HTTP_URL,
    }


@app.api_route("/v1/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_gateway_v1(path: str, request: Request) -> Response:
    return await proxy_http(request, f"{GATEWAY_HTTP_URL}/v1/{path}")


@app.api_route("/api/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_gateway_api(path: str, request: Request) -> Response:
    return await proxy_http(request, f"{GATEWAY_HTTP_URL}/api/{path}")


@app.websocket("/api/websocket")
async def proxy_gateway_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    upstream_url = f"{GATEWAY_WS_URL}/api/websocket"
    async with websockets.connect(upstream_url) as upstream:
        async def client_to_upstream() -> None:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    return
                if "text" in message:
                    await upstream.send(message["text"])
                elif "bytes" in message:
                    await upstream.send(message["bytes"])

        async def upstream_to_client() -> None:
            while True:
                message = await upstream.recv()
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_text(message)

        tasks = [
            asyncio.create_task(client_to_upstream()),
            asyncio.create_task(upstream_to_client()),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in pending:
            with suppress(asyncio.CancelledError):
                await task
        for task in done:
            with suppress(WebSocketDisconnect, ConnectionClosed):
                task.result()


async def proxy_http(request: Request, upstream_url: str) -> Response:
    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower()
        not in {
            "host",
            "content-length",
            "connection",
            "accept-encoding",
        }
    }
    upstream_method = "GET" if request.method == "HEAD" else request.method
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as client:
        upstream_response = await client.request(
            upstream_method,
            upstream_url,
            params=request.query_params,
            content=body if body else None,
            headers=headers,
        )
    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower()
        not in {
            "content-encoding",
            "content-length",
            "connection",
            "transfer-encoding",
        }
    }
    return Response(
        content=b"" if request.method == "HEAD" else upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )


@app.api_route("/{path:path}", methods=["GET", "HEAD"], response_model=None)
async def serve_frontend(path: str, request: Request) -> Response:
    requested_path = (WEB_ROOT / path).resolve()
    if requested_path.is_file() and WEB_ROOT in requested_path.parents:
        if request.method == "HEAD":
            return Response(status_code=200)
        return FileResponse(requested_path)
    if request.method == "HEAD":
        return Response(status_code=200)
    return FileResponse(WEB_ROOT / "index.html")
