from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    public_url: str
    frontend_public_url: str
    frontend_upstream_url: str
    signing_secret: str
    admin_token: str
    store_path: str
    home_assistant_url: str
    home_assistant_token: str
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int

    @classmethod
    def from_env(cls) -> Settings:
        public_url = os.getenv("GATEWAY_PUBLIC_URL", "http://localhost:8080").rstrip("/")
        home_assistant_url = os.getenv("HOME_ASSISTANT_URL", "http://localhost:8123").rstrip("/")
        return cls(
            public_url=public_url,
            frontend_public_url=os.getenv("FRONTEND_PUBLIC_URL", public_url).rstrip("/"),
            frontend_upstream_url=os.getenv("FRONTEND_UPSTREAM_URL", home_assistant_url).rstrip("/"),
            signing_secret=os.getenv("GATEWAY_SIGNING_SECRET", "dev-secret-change-me-32-bytes-minimum"),
            admin_token=os.getenv("GATEWAY_ADMIN_TOKEN", "dev-admin-token"),
            store_path=os.getenv("GATEWAY_STORE_PATH", "./data/gateway-store.json"),
            home_assistant_url=home_assistant_url,
            home_assistant_token=os.getenv("HOME_ASSISTANT_TOKEN", ""),
            access_token_ttl_seconds=int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "900")),
            refresh_token_ttl_seconds=int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "2592000")),
        )
