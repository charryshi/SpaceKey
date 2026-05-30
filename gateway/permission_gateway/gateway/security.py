from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any


class TokenError(ValueError):
    pass


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_verification_code(code: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        code.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return f"pbkdf2_sha256$100000${salt}${b64url_encode(digest)}"


def verify_verification_code(code: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        code.encode("utf-8"),
        salt.encode("utf-8"),
        int(rounds),
    )
    return hmac.compare_digest(b64url_encode(digest), expected)


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class TokenManager:
    def __init__(
        self,
        signing_secret: str,
        access_ttl_seconds: int = 900,
        refresh_ttl_seconds: int = 2_592_000,
    ) -> None:
        if len(signing_secret) < 24:
            raise ValueError("GATEWAY_SIGNING_SECRET must be at least 24 characters")
        self.signing_secret = signing_secret.encode("utf-8")
        self.access_ttl_seconds = access_ttl_seconds
        self.refresh_ttl_seconds = refresh_ttl_seconds

    def issue_pair(
        self,
        *,
        grant_id: str,
        app_instance_id: str,
        device_public_key: str,
        role: str,
    ) -> TokenPair:
        access = self.issue_token(
            token_type="access",
            grant_id=grant_id,
            app_instance_id=app_instance_id,
            device_public_key=device_public_key,
            role=role,
            ttl_seconds=self.access_ttl_seconds,
        )
        refresh = self.issue_token(
            token_type="refresh",
            grant_id=grant_id,
            app_instance_id=app_instance_id,
            device_public_key=device_public_key,
            role=role,
            ttl_seconds=self.refresh_ttl_seconds,
        )
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            token_type="Bearer",
            expires_in=self.access_ttl_seconds,
        )

    def issue_token(
        self,
        *,
        token_type: str,
        grant_id: str,
        app_instance_id: str,
        device_public_key: str,
        role: str,
        ttl_seconds: int,
    ) -> str:
        now = int(time.time())
        payload = {
            "typ": token_type,
            "iat": now,
            "exp": now + ttl_seconds,
            "grant_id": grant_id,
            "app_instance_id": app_instance_id,
            "device_public_key_sha256": sha256_text(device_public_key),
            "role": role,
            "jti": secrets.token_urlsafe(18),
        }
        return self._encode(payload)

    def verify(self, token: str, *, expected_type: str) -> dict[str, Any]:
        payload = self._decode(token)
        if payload.get("typ") != expected_type:
            raise TokenError("token type mismatch")
        exp = int(payload.get("exp", 0))
        if exp <= int(time.time()):
            raise TokenError("token expired")
        return payload

    def verify_device_binding(self, payload: dict[str, Any], device_public_key: str) -> None:
        expected = str(payload.get("device_public_key_sha256", ""))
        actual = sha256_text(device_public_key)
        if not hmac.compare_digest(expected, actual):
            raise TokenError("device binding mismatch")

    def _encode(self, payload: dict[str, Any]) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        header_part = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_part = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        signature = hmac.new(self.signing_secret, signing_input, hashlib.sha256).digest()
        return f"{header_part}.{payload_part}.{b64url_encode(signature)}"

    def _decode(self, token: str) -> dict[str, Any]:
        try:
            header_part, payload_part, signature_part = token.split(".", 2)
        except ValueError as exc:
            raise TokenError("malformed token") from exc
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        expected = hmac.new(self.signing_secret, signing_input, hashlib.sha256).digest()
        actual = b64url_decode(signature_part)
        if not hmac.compare_digest(expected, actual):
            raise TokenError("invalid signature")
        payload = json.loads(b64url_decode(payload_part).decode("utf-8"))
        if not isinstance(payload, dict):
            raise TokenError("invalid payload")
        return payload

