from __future__ import annotations

import asyncio
import json
import uuid
from io import BytesIO
from typing import Any
from urllib.parse import urlencode, urlparse

from .activation import ActivationError, ActivationService, RequestAuthenticator
from .admin_summary import build_dashboard_summary, build_ha_browser, template_permission_preview
from .config import Settings
from .ha_filter import HaMessageFilter
from .ha_registry_sync import RegistrySyncError, sync_ha_registry
from .models import AreaNode, Grant, HaRegistrySnapshot, PermissionScope, QRTemplate, parse_dt
from .policy import PermissionDenied, PolicyEngine
from .repository import JsonFileRepository, RepositoryError
from .security import TokenError, TokenManager, hash_verification_code


try:
    import httpx
    import websockets
    from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
except ImportError as exc:  # pragma: no cover - exercised only without web deps installed.
    httpx = None
    websockets = None
    FastAPI = None
    HTTPException = None
    Request = None
    WebSocket = None
    WebSocketDisconnect = None
    JSONResponse = None
    HTMLResponse = None
    RedirectResponse = None
    Response = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


def build_app(settings: Settings | None = None) -> Any:
    if FastAPI is None:
        raise RuntimeError(
            "FastAPI runtime dependencies are not installed. Run `python -m pip install -e .`."
        ) from _IMPORT_ERROR

    settings = settings or Settings.from_env()
    repository = JsonFileRepository(settings.store_path)
    token_manager = TokenManager(
        settings.signing_secret,
        access_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
    )
    activation_service = ActivationService(repository, token_manager)
    authenticator = RequestAuthenticator(repository, token_manager)
    app = FastAPI(title="Home Assistant Permission Gateway", version="0.1.0")
    app.state.repository = repository
    app.state.settings = settings
    admin_session_cookie = "gateway_admin_session"
    frontend_token_cookie = "gateway_frontend_access_token"

    def policy() -> PolicyEngine:
        return PolicyEngine(repository.list_area_nodes(), repository.get_registry_snapshot())

    def message_filter() -> HaMessageFilter:
        return HaMessageFilter(policy())

    def extract_bearer(request: Request) -> str:
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        return header.removeprefix("Bearer ").strip()

    def require_admin(request: Request) -> None:
        header = request.headers.get("authorization", "")
        if header.startswith("Bearer ") and header.removeprefix("Bearer ").strip() == settings.admin_token:
            return
        cookie_token = request.cookies.get(admin_session_cookie)
        if cookie_token:
            try:
                token_manager.verify(cookie_token, expected_type="admin")
                return
            except TokenError:
                pass
        raise HTTPException(status_code=403, detail="admin session required")

    def require_grant(request: Request, *, require_device_key: bool = True) -> Grant:
        token = extract_bearer(request)
        device_public_key = request.headers.get("x-device-public-key")
        if require_device_key and not device_public_key:
            raise HTTPException(status_code=401, detail="X-Device-Public-Key header required")
        try:
            return authenticator.authenticate_access_token(
                token,
                device_public_key=device_public_key if device_public_key else None,
            )
        except (ActivationError, TokenError) as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    def set_frontend_token_cookie(response: Response, access_token: str) -> None:
        response.set_cookie(
            frontend_token_cookie,
            access_token,
            max_age=settings.access_token_ttl_seconds,
            httponly=True,
            secure=settings.public_url.startswith("https://"),
            samesite="lax",
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"ok": True, "service": "permission-gateway"}

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_console() -> str:
        from .admin_console import ADMIN_CONSOLE_HTML

        return ADMIN_CONSOLE_HTML

    @app.post("/v1/admin/session")
    async def admin_login(payload: dict[str, Any], response: Response) -> dict[str, Any]:
        if str(payload.get("admin_token") or "") != settings.admin_token:
            repository.add_audit_event("admin_login_denied", actor="admin-console", target="session")
            raise HTTPException(status_code=403, detail="invalid admin token")
        session_token = token_manager.issue_token(
            token_type="admin",
            grant_id="admin",
            app_instance_id="admin-console",
            device_public_key="admin-console",
            role="admin",
            ttl_seconds=43_200,
        )
        response.set_cookie(
            admin_session_cookie,
            session_token,
            max_age=43_200,
            httponly=True,
            secure=settings.public_url.startswith("https://"),
            samesite="lax",
        )
        repository.add_audit_event("admin_login", actor="admin-console", target="session")
        return {"ok": True}

    @app.delete("/v1/admin/session")
    async def admin_logout(response: Response) -> dict[str, Any]:
        response.delete_cookie(admin_session_cookie)
        return {"ok": True}

    @app.get("/v1/admin/session")
    async def admin_session(request: Request) -> dict[str, Any]:
        try:
            require_admin(request)
        except HTTPException:
            return {"authenticated": False}
        return {"authenticated": True}

    @app.post("/v1/activation/verify")
    async def activation_verify(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = activation_service.verify_qr(
                qr_id=str(payload["qr_id"]),
                verification_code=str(payload["verification_code"]),
                device_public_key=str(payload["device_public_key"]),
                app_instance_id=str(payload["app_instance_id"]),
                requested_ttl_seconds=payload.get("requested_ttl_seconds"),
            )
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=f"missing field: {exc.args[0]}") from exc
        except ActivationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return result.to_dict()

    @app.post("/v1/auth/refresh")
    async def auth_refresh(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = activation_service.refresh(
                refresh_token=str(payload["refresh_token"]),
                device_public_key=str(payload["device_public_key"]),
            )
        except (KeyError, ActivationError, TokenError) as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return result.to_dict()

    @app.post("/v1/auth/revoke")
    async def auth_revoke(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        grant = require_grant(request)
        requested_grant_id = str(payload.get("grant_id") or grant.id)
        if requested_grant_id != grant.id:
            raise HTTPException(status_code=403, detail="scoped grants can only revoke themselves")
        activation_service.revoke(grant.id, actor=grant.app_instance_id)
        return {"ok": True}

    @app.api_route("/v1/me/permissions", methods=["GET", "HEAD"], response_model=None)
    async def me_permissions(request: Request) -> Any:
        grant = require_grant(request)
        if request.method == "HEAD":
            return Response(status_code=200)
        return _permission_summary_with_template(repository, policy(), grant)

    @app.post("/v1/frontend/session")
    async def frontend_session(request: Request, response: Response) -> dict[str, Any]:
        grant = require_grant(request, require_device_key=False)
        access_token = extract_bearer(request)
        set_frontend_token_cookie(response, access_token)
        frontend_same_origin = _same_origin(settings.public_url, settings.frontend_public_url)
        return {
            "ok": True,
            "grant_id": grant.id,
            "frontend_url": _frontend_public_url(settings, "", "external_auth=1"),
            "frontend_same_origin": frontend_same_origin,
            "requires_external_auth_bridge": not frontend_same_origin,
            "expires_in": settings.access_token_ttl_seconds,
        }

    @app.get("/v1/admin/places")
    async def admin_list_places(request: Request) -> list[dict[str, Any]]:
        require_admin(request)
        return [node.to_dict() for node in repository.list_area_nodes()]

    @app.get("/v1/admin/dashboard")
    async def admin_dashboard(request: Request) -> dict[str, Any]:
        require_admin(request)
        return build_dashboard_summary(
            repository,
            home_assistant_token_configured=bool(settings.home_assistant_token),
            ha_connection_status=await _check_ha_connection(settings),
        )

    @app.post("/v1/admin/places")
    async def admin_upsert_place(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        require_admin(request)
        try:
            place_payload = dict(payload)
            place_payload["id"] = str(place_payload.get("id") or _generated_id("place"))
            node = AreaNode.from_dict(place_payload)
            saved = repository.upsert_area_node(node)
            repository.add_audit_event("place_upserted", actor="admin", target=saved.id)
            return saved.to_dict()
        except (KeyError, RepositoryError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete("/v1/admin/places/{node_id}")
    async def admin_delete_place(node_id: str, request: Request) -> dict[str, Any]:
        require_admin(request)
        try:
            repository.delete_area_node(node_id)
            repository.add_audit_event("place_deleted", actor="admin", target=node_id)
            return {"ok": True}
        except RepositoryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/admin/qr-templates")
    async def admin_list_qr_templates(request: Request) -> list[dict[str, Any]]:
        require_admin(request)
        return [template.to_dict() for template in repository.list_qr_templates()]

    @app.post("/v1/admin/qr-templates/preview")
    async def admin_qr_template_preview(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        require_admin(request)
        return template_permission_preview(repository, payload.get("scope") or {})

    @app.post("/v1/admin/qr-templates")
    async def admin_upsert_qr_template(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        require_admin(request)
        if "verification_code" not in payload and "verification_code_hash" not in payload:
            raise HTTPException(status_code=422, detail="verification_code is required")
        template_id = str(payload.get("id") or _generated_id("template"))
        template = QRTemplate(
            id=template_id,
            name=str(payload["name"]),
            verification_code_hash=str(
                payload.get("verification_code_hash")
                or hash_verification_code(str(payload["verification_code"]))
            ),
            scope=PermissionScope.from_dict(payload.get("scope")),
            enabled=bool(payload.get("enabled", True)),
            default_ttl_seconds=int(payload.get("default_ttl_seconds", 86_400)),
            max_ttl_seconds=int(payload.get("max_ttl_seconds", 604_800)),
        )
        saved = repository.upsert_qr_template(template)
        repository.add_audit_event("qr_template_upserted", actor="admin", target=saved.id)
        return saved.to_dict()

    @app.get("/v1/admin/qr-templates/{template_id}/qr.png")
    async def admin_qr_template_png(template_id: str, request: Request) -> Response:
        require_admin(request)
        template = repository.get_qr_template(template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="QR template not found")
        try:
            import qrcode
        except ImportError as exc:
            raise HTTPException(status_code=503, detail="qrcode dependency is not installed") from exc
        payload = json.dumps(
            {"gateway_url": settings.public_url, "qr_id": template.id},
            separators=(",", ":"),
        )
        image = qrcode.make(payload)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return Response(content=buffer.getvalue(), media_type="image/png")

    @app.get("/v1/admin/grants")
    async def admin_list_grants(request: Request) -> list[dict[str, Any]]:
        require_admin(request)
        return [grant.to_dict() for grant in repository.list_grants()]

    @app.patch("/v1/admin/grants/{grant_id}")
    async def admin_update_grant(grant_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        require_admin(request)
        grant = repository.get_grant(grant_id)
        if grant is None:
            raise HTTPException(status_code=404, detail="grant not found")
        if payload.get("revoke") is True:
            grant = grant.revoked()
        if "expires_at" in payload:
            grant = grant.with_expiry(parse_dt(payload["expires_at"]))
        repository.update_grant(grant)
        repository.add_audit_event("grant_updated", actor="admin", target=grant_id, details=payload)
        return grant.to_dict()

    @app.get("/v1/admin/audit")
    async def admin_audit(request: Request) -> list[dict[str, Any]]:
        require_admin(request)
        return [event.to_dict() for event in repository.list_audit_events()]

    @app.get("/v1/admin/notifications")
    async def admin_notifications(request: Request) -> list[dict[str, Any]]:
        require_admin(request)
        return repository.list_notifications()

    @app.get("/v1/admin/ha-browser")
    async def admin_ha_browser(request: Request) -> dict[str, Any]:
        require_admin(request)
        return build_ha_browser(repository)

    @app.post("/v1/admin/ha-registry-sync")
    async def admin_sync_ha_registry(request: Request) -> dict[str, Any]:
        require_admin(request)
        try:
            snapshot = await sync_ha_registry(settings)
        except RegistrySyncError as exc:
            repository.add_audit_event(
                "ha_registry_sync_failed",
                actor="admin",
                target="ha",
                details={"reason": str(exc)},
            )
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        repository.set_registry_snapshot(snapshot)
        details = {
            "areas": len(snapshot.areas),
            "devices": len(snapshot.devices),
            "entities": len(snapshot.entities),
        }
        repository.add_audit_event("ha_registry_synced", actor="admin", target="ha", details=details)
        return {"ok": True, "counts": details}

    @app.put("/v1/admin/ha-registry-snapshot")
    async def admin_update_registry_snapshot(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        require_admin(request)
        snapshot = HaRegistrySnapshot.from_dict(payload)
        repository.set_registry_snapshot(snapshot)
        repository.add_audit_event("ha_registry_snapshot_updated", actor="admin", target="ha")
        return snapshot.to_dict()

    @app.websocket("/api/websocket")
    async def websocket_proxy(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            await websocket.send_json({"type": "auth_required", "ha_version": "permission-gateway"})
            auth_message = await websocket.receive_json()
            access_token = str(auth_message.get("access_token") or "")
            device_public_key_value = auth_message.get("device_public_key")
            device_public_key = str(device_public_key_value) if device_public_key_value else None
            if auth_message.get("type") != "auth" or not access_token:
                await websocket.send_json({"type": "auth_invalid", "message": "gateway token required"})
                await websocket.close(code=4401)
                return
            grant = authenticator.authenticate_access_token(access_token, device_public_key=device_public_key)
            await websocket.send_json({"type": "auth_ok", "ha_version": "permission-gateway"})
            await _relay_websocket(settings, websocket, grant, message_filter(), repository)
        except (ActivationError, TokenError) as exc:
            await websocket.send_json({"type": "auth_invalid", "message": str(exc)})
            await websocket.close(code=4401)
        except WebSocketDisconnect:
            return

    @app.api_route("/api/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
    async def rest_proxy(path: str, request: Request) -> Response:
        grant = require_grant(request, require_device_key=False)
        ha_filter = message_filter()
        body = await request.body()
        json_payload: Any = None
        if body:
            try:
                json_payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                json_payload = None

        if path.startswith("states/"):
            entity_id = path.removeprefix("states/")
            if not policy().is_entity_allowed(grant, entity_id):
                raise HTTPException(status_code=404, detail="entity not found")
        if path.startswith("camera_proxy/"):
            entity_id = path.removeprefix("camera_proxy/")
            if not policy().is_entity_allowed(grant, entity_id):
                raise HTTPException(status_code=404, detail="entity not found")
        if path.startswith("services/") and request.method == "POST":
            _, domain, service = path.split("/", 2)
            payload = json_payload if isinstance(json_payload, dict) else {}
            service_message = ha_filter.service_payload_from_rest(
                domain=domain,
                service=service,
                payload=payload,
            )
            try:
                ha_filter.validate_client_message(grant, service_message)
            except PermissionDenied as exc:
                repository.add_audit_event(
                    "service_call_denied",
                    actor=grant.app_instance_id,
                    target=grant.id,
                    details={"path": path, "reason": str(exc)},
                )
                raise HTTPException(status_code=403, detail=str(exc)) from exc
        elif request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            raise HTTPException(status_code=403, detail="mutating API path is not allowed")

        upstream_response = await _forward_rest(settings, path, request, body)
        content_type = upstream_response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return Response(
                content=b"" if request.method == "HEAD" else upstream_response.content,
                status_code=upstream_response.status_code,
                media_type=content_type or None,
            )
        upstream_json = upstream_response.json()
        filtered_json = ha_filter.filter_rest_response(grant, path, upstream_json)
        if request.method == "HEAD":
            return Response(
                status_code=upstream_response.status_code,
                media_type=content_type or "application/json",
            )
        return JSONResponse(status_code=upstream_response.status_code, content=filtered_json)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"])
    async def frontend_proxy(path: str, request: Request) -> Response:
        if _is_reserved_frontend_path(path):
            raise HTTPException(status_code=404, detail="not found")

        query_token = request.query_params.get("gateway_access_token")
        if query_token:
            try:
                authenticator.authenticate_access_token(
                    query_token,
                    device_public_key=request.query_params.get("device_public_key"),
                )
            except (ActivationError, TokenError) as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc
            redirect = RedirectResponse(
                _frontend_redirect_url(settings, path, dict(request.query_params)),
                status_code=302,
            )
            set_frontend_token_cookie(redirect, query_token)
            return redirect

        if _should_redirect_to_public_frontend(settings, path):
            return RedirectResponse(
                _frontend_redirect_url(settings, path, dict(request.query_params)),
                status_code=302,
            )

        if _needs_external_auth_redirect(path, dict(request.query_params)):
            return RedirectResponse(
                _clean_frontend_url(path, dict(request.query_params)),
                status_code=302,
            )

        upstream_response = await _forward_frontend(settings, path, request)
        content_type = upstream_response.headers.get("content-type", "")
        content = upstream_response.content
        token = request.cookies.get(frontend_token_cookie)
        if token and "text/html" in content_type:
            try:
                authenticator.authenticate_access_token(token, device_public_key=None)
            except (ActivationError, TokenError):
                token = None
            if token:
                content = _inject_external_auth_bootstrap(
                    content,
                    access_token=token,
                    expires_in=settings.access_token_ttl_seconds,
                )
        return Response(
            content=b"" if request.method == "HEAD" else content,
            status_code=upstream_response.status_code,
            media_type=content_type or None,
        )

    return app


async def _forward_rest(settings: Settings, path: str, request: Any, body: bytes) -> Any:
    if httpx is None:
        raise RuntimeError("httpx is not installed")
    if not settings.home_assistant_token:
        raise HTTPException(status_code=503, detail="HOME_ASSISTANT_TOKEN is not configured")
    url = f"{settings.home_assistant_url}/api/{path}"
    headers = {
        "authorization": f"Bearer {settings.home_assistant_token}",
        "content-type": request.headers.get("content-type", "application/json"),
    }
    upstream_method = "GET" if request.method == "HEAD" else request.method
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await client.request(
            upstream_method,
            url,
            params=dict(request.query_params),
            content=body if body else None,
            headers=headers,
        )


async def _forward_frontend(settings: Settings, path: str, request: Any) -> Any:
    if httpx is None:
        raise RuntimeError("httpx is not installed")
    upstream_url = _frontend_upstream_url(settings.frontend_upstream_url, path, request.url.query)
    upstream_method = "GET" if request.method == "HEAD" else request.method
    headers = {
        "accept": request.headers.get("accept", "*/*"),
        "user-agent": request.headers.get("user-agent", "permission-gateway"),
    }
    async with httpx.AsyncClient(follow_redirects=False, timeout=20.0) as client:
        return await client.request(upstream_method, upstream_url, headers=headers)


async def _check_ha_connection(settings: Settings) -> str:
    if not settings.home_assistant_token:
        return "not_configured"
    if httpx is None:
        return "dependency_missing"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                f"{settings.home_assistant_url}/api/",
                headers={"authorization": f"Bearer {settings.home_assistant_token}"},
            )
    except Exception:
        return "error"
    return "ok" if 200 <= response.status_code < 300 else f"http_{response.status_code}"


def _is_reserved_frontend_path(path: str) -> bool:
    normalized = path.strip("/")
    if not normalized:
        return False
    return normalized == "healthz" or normalized == "admin" or normalized.startswith(
        (
            "api/",
            "v1/",
            "admin/",
            "docs",
            "openapi.json",
        )
    )


def _needs_external_auth_redirect(path: str, query: dict[str, Any]) -> bool:
    if str(query.get("external_auth") or "") == "1":
        return False
    return _is_frontend_document_path(path)


def _is_frontend_document_path(path: str) -> bool:
    if not path:
        return True
    last_segment = path.rsplit("/", 1)[-1]
    return "." not in last_segment


def _clean_frontend_url(path: str, query: dict[str, Any]) -> str:
    clean_query = {
        key: value
        for key, value in query.items()
        if key not in {"gateway_access_token", "device_public_key"}
    }
    if _is_frontend_document_path(path):
        clean_query["external_auth"] = "1"
    query_string = urlencode(clean_query)
    url = f"/{path}" if path else "/"
    return f"{url}?{query_string}" if query_string else url


def _frontend_upstream_url(home_assistant_url: str, path: str, raw_query: str) -> str:
    url = f"{home_assistant_url.rstrip('/')}/{path}"
    return f"{url}?{raw_query}" if raw_query else url


def _frontend_public_url(settings: Settings, path: str, raw_query: str) -> str:
    url = f"{settings.frontend_public_url.rstrip('/')}/{path}"
    return f"{url}?{raw_query}" if raw_query else url


def _frontend_redirect_url(settings: Settings, path: str, query: dict[str, Any]) -> str:
    clean_url = _clean_frontend_url(path, query)
    if _should_redirect_to_public_frontend(settings, path):
        return f"{settings.frontend_public_url.rstrip('/')}{clean_url}"
    return clean_url


def _should_redirect_to_public_frontend(settings: Settings, path: str) -> bool:
    return not _same_origin(settings.public_url, settings.frontend_public_url) and _is_frontend_document_path(path)


def _same_origin(first_url: str, second_url: str) -> bool:
    first = urlparse(first_url)
    second = urlparse(second_url)
    return (first.scheme, first.netloc) == (second.scheme, second.netloc)


def _inject_external_auth_bootstrap(content: bytes, *, access_token: str, expires_in: int) -> bytes:
    try:
        html = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    script = _external_auth_bootstrap_script(access_token=access_token, expires_in=expires_in)
    head_index = html.lower().find("</head>")
    if head_index >= 0:
        html = html[:head_index] + script + html[head_index:]
    else:
        html = script + html
    return html.encode("utf-8")


def _external_auth_bootstrap_script(*, access_token: str, expires_in: int) -> str:
    token_json = json.dumps(access_token)
    expires_json = json.dumps(int(expires_in))
    return f"""
<script>
(function () {{
  const token = {token_json};
  const expiresIn = {expires_json};
  function parseOptions(options) {{
    if (typeof options === "string") {{
      try {{ return JSON.parse(options); }} catch (_) {{ return {{}}; }}
    }}
    return options || {{}};
  }}
  function callCallback(options, ok) {{
    const callback = options && options.callback;
    if (!callback || typeof window[callback] !== "function") return;
    if (ok === false) {{
      window[callback](false);
      return;
    }}
    window[callback](true, {{ access_token: token, expires_in: expiresIn }});
  }}
  window.externalApp = window.externalApp || {{
    getExternalAuth: function (options) {{ callCallback(parseOptions(options), true); }},
    revokeExternalAuth: function (options) {{ callCallback(parseOptions(options), true); }}
  }};
  window.externalAppV2 = window.externalAppV2 || {{
    postMessage: function (message) {{
      const parsed = parseOptions(message);
      if (parsed.type === "getExternalAuth") callCallback(parsed.payload || {{}}, true);
      if (parsed.type === "revokeExternalAuth") callCallback(parsed.payload || {{}}, true);
    }}
  }};
  window.__gatewayExternalAuth = {{ available: true, expires_in: expiresIn }};
}})();
</script>
"""


async def _relay_websocket(
    settings: Settings,
    websocket: Any,
    grant: Grant,
    ha_filter: HaMessageFilter,
    repository: JsonFileRepository,
) -> None:
    if websockets is None:
        await websocket.send_json({"type": "auth_invalid", "message": "websockets dependency missing"})
        await websocket.close(code=1011)
        return
    if not settings.home_assistant_token:
        await websocket.send_json({"type": "auth_invalid", "message": "HOME_ASSISTANT_TOKEN is not configured"})
        await websocket.close(code=1011)
        return

    upstream_url = settings.home_assistant_url.replace("http://", "ws://").replace("https://", "wss://")
    upstream_url = f"{upstream_url}/api/websocket"
    command_types: dict[int, str] = {}

    async with websockets.connect(upstream_url) as upstream:
        await upstream.recv()
        await upstream.send(json.dumps({"type": "auth", "access_token": settings.home_assistant_token}))
        await upstream.recv()

        async def client_to_upstream() -> None:
            while True:
                raw = await websocket.receive_text()
                message = json.loads(raw)
                command_id = message.get("id")
                if isinstance(command_id, int):
                    command_types[command_id] = str(message.get("type") or "")
                try:
                    ha_filter.validate_client_message(grant, message)
                except PermissionDenied as exc:
                    repository.add_audit_event(
                        "service_call_denied",
                        actor=grant.app_instance_id,
                        target=grant.id,
                        details={
                            "message_type": str(message.get("type") or ""),
                            "reason": str(exc),
                        },
                    )
                    await websocket.send_json(
                        {
                            "id": command_id,
                            "type": "result",
                            "success": False,
                            "error": {"code": "permission_denied", "message": str(exc)},
                        }
                    )
                    continue
                await upstream.send(json.dumps(message))

        async def upstream_to_client() -> None:
            while True:
                raw = await upstream.recv()
                message = json.loads(raw)
                command_id = message.get("id")
                if isinstance(command_id, int):
                    message["ha_command_type"] = command_types.get(command_id, "")
                filtered = ha_filter.filter_server_message(grant, message)
                if filtered is None:
                    continue
                filtered.pop("ha_command_type", None)
                await websocket.send_json(filtered)

        await asyncio.gather(client_to_upstream(), upstream_to_client())


def main() -> None:
    if _IMPORT_ERROR is not None:
        raise RuntimeError("Install runtime dependencies before starting the gateway") from _IMPORT_ERROR
    import uvicorn

    uvicorn.run("permission_gateway.gateway.app:build_app", factory=True, host="0.0.0.0", port=8080)


app = build_app() if FastAPI is not None else None


def _generated_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _permission_summary_with_template(
    repository: JsonFileRepository,
    policy: PolicyEngine,
    grant: Grant,
) -> dict[str, Any]:
    summary = policy.permission_summary(grant)
    template = repository.get_qr_template(grant.template_id) if grant.template_id else None
    template_name = template.name if template else None
    summary.update(
        {
            "grant_id": grant.id,
            "template_id": grant.template_id,
            "template_name": template_name,
            "display_name": template_name or ("管理员" if grant.role.value == "admin" else "授权用户"),
        }
    )
    return summary
