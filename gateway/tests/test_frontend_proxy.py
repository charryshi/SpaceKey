from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from permission_gateway.gateway.app import (
    _clean_frontend_url,
    _frontend_public_url,
    _frontend_upstream_url,
    _forward_frontend,
    _inject_external_auth_bootstrap,
    _is_reserved_frontend_path,
    _needs_external_auth_redirect,
    _same_origin,
    _should_redirect_to_public_frontend,
    _frontend_redirect_url,
)
from permission_gateway.gateway.config import Settings


class FrontendProxyTests(unittest.TestCase):
    def test_reserved_paths_are_not_frontend_proxied(self) -> None:
        self.assertTrue(_is_reserved_frontend_path("api/states"))
        self.assertTrue(_is_reserved_frontend_path("v1/me/permissions"))
        self.assertTrue(_is_reserved_frontend_path("admin"))
        self.assertTrue(_is_reserved_frontend_path("healthz"))
        self.assertFalse(_is_reserved_frontend_path(""))
        self.assertFalse(_is_reserved_frontend_path("lovelace/0"))

    def test_frontend_document_paths_redirect_to_external_auth(self) -> None:
        self.assertTrue(_needs_external_auth_redirect("", {}))
        self.assertTrue(_needs_external_auth_redirect("lovelace/0", {}))
        self.assertFalse(_needs_external_auth_redirect("frontend_latest/app.js", {}))
        self.assertFalse(_needs_external_auth_redirect("", {"external_auth": "1"}))

    def test_clean_frontend_url_removes_token_and_adds_external_auth(self) -> None:
        url = _clean_frontend_url(
            "",
            {
                "gateway_access_token": "secret",
                "device_public_key": "pub",
                "panel": "main",
            },
        )

        self.assertEqual(url, "/?panel=main&external_auth=1")

    def test_upstream_url_preserves_path_and_query(self) -> None:
        self.assertEqual(
            _frontend_upstream_url("http://ha.local:8123", "lovelace/0", "external_auth=1"),
            "http://ha.local:8123/lovelace/0?external_auth=1",
        )

    def test_frontend_public_url_can_point_to_custom_web_frontend(self) -> None:
        settings = Settings(
            public_url="http://gateway.local",
            frontend_public_url="https://ha.aivo.19.md",
            frontend_upstream_url="http://web-frontend.local",
            signing_secret="secret",
            admin_token="admin",
            store_path="/tmp/store.json",
            home_assistant_url="http://ha.local:8123",
            home_assistant_token="ha-token",
            access_token_ttl_seconds=900,
            refresh_token_ttl_seconds=3600,
        )

        self.assertEqual(
            _frontend_public_url(settings, "", "external_auth=1"),
            "https://ha.aivo.19.md/?external_auth=1",
        )
        self.assertFalse(_same_origin(settings.public_url, settings.frontend_public_url))
        self.assertTrue(_should_redirect_to_public_frontend(settings, "lovelace/0"))
        self.assertFalse(_should_redirect_to_public_frontend(settings, "frontend_latest/app.js"))
        self.assertEqual(
            _frontend_redirect_url(settings, "lovelace/0", {"panel": "main"}),
            "https://ha.aivo.19.md/lovelace/0?panel=main&external_auth=1",
        )

    def test_injects_external_auth_bootstrap_before_head_close(self) -> None:
        html = b"<html><head><title>HA</title></head><body></body></html>"

        injected = _inject_external_auth_bootstrap(html, access_token="token-1", expires_in=900)
        text = injected.decode("utf-8")

        self.assertIn("window.externalApp", text)
        self.assertIn("window.externalAppV2", text)
        self.assertIn('"token-1"', text)
        self.assertLess(text.index("window.externalApp"), text.index("</head>"))

    def test_frontend_head_uses_get_upstream_for_ha_compatibility(self) -> None:
        calls: list[tuple[str, str]] = []

        class FakeClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            async def __aenter__(self) -> "FakeClient":
                return self

            async def __aexit__(self, *args: object) -> None:
                return None

            async def request(self, method: str, url: str, **kwargs: object) -> object:
                calls.append((method, url))
                return object()

        class FakeURL:
            query = "external_auth=1"

        class FakeRequest:
            method = "HEAD"
            url = FakeURL()
            headers: dict[str, str] = {}

        settings = Settings(
            public_url="http://gateway.local",
            frontend_public_url="http://gateway.local",
            frontend_upstream_url="http://web-frontend.local",
            signing_secret="secret",
            admin_token="admin",
            store_path="/tmp/store.json",
            home_assistant_url="http://ha.local:8123",
            home_assistant_token="ha-token",
            access_token_ttl_seconds=900,
            refresh_token_ttl_seconds=3600,
        )

        with patch("permission_gateway.gateway.app.httpx", SimpleNamespace(AsyncClient=FakeClient)):
            asyncio.run(_forward_frontend(settings, "", FakeRequest()))

        self.assertEqual(calls, [("GET", "http://web-frontend.local/?external_auth=1")])


if __name__ == "__main__":
    unittest.main()
