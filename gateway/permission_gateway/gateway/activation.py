from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .models import Grant, utcnow
from .policy import PolicyEngine
from .repository import InMemoryRepository
from .security import TokenManager, TokenPair, verify_verification_code


class ActivationError(PermissionError):
    pass


@dataclass(frozen=True)
class ActivationResult:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    grant_id: str
    expires_at: str | None
    permission_summary: dict[str, Any]

    @classmethod
    def from_token_pair(
        cls,
        *,
        token_pair: TokenPair,
        grant: Grant,
        permission_summary: dict[str, Any],
    ) -> ActivationResult:
        return cls(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
            grant_id=grant.id,
            expires_at=grant.expires_at.isoformat().replace("+00:00", "Z") if grant.expires_at else None,
            permission_summary=permission_summary,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "grant_id": self.grant_id,
            "expires_at": self.expires_at,
            "permission_summary": self.permission_summary,
        }


class ActivationService:
    def __init__(self, repository: InMemoryRepository, token_manager: TokenManager) -> None:
        self.repository = repository
        self.token_manager = token_manager

    def verify_qr(
        self,
        *,
        qr_id: str,
        verification_code: str,
        device_public_key: str,
        app_instance_id: str,
        requested_ttl_seconds: int | None = None,
    ) -> ActivationResult:
        template = self.repository.get_qr_template(qr_id)
        if template is None or not template.enabled:
            raise ActivationError("QR template is not available")
        if not verify_verification_code(verification_code, template.verification_code_hash):
            self.repository.add_audit_event(
                "activation_denied",
                actor=app_instance_id,
                target=qr_id,
                details={"reason": "invalid_verification_code"},
            )
            raise ActivationError("verification code is invalid")

        ttl_seconds = (
            int(template.default_ttl_seconds)
            if requested_ttl_seconds is None
            else int(requested_ttl_seconds)
        )
        if ttl_seconds <= 0:
            raise ActivationError("requested TTL must be positive")
        ttl_seconds = min(ttl_seconds, template.max_ttl_seconds)
        now = utcnow()
        grant = Grant(
            id=str(uuid.uuid4()),
            template_id=template.id,
            app_instance_id=app_instance_id,
            device_public_key=device_public_key,
            scope=template.scope,
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self.repository.create_grant(grant)
        self.repository.add_audit_event(
            "activation_granted",
            actor=app_instance_id,
            target=grant.id,
            details={"template_id": template.id, "expires_at": grant.expires_at.isoformat()},
        )
        self.repository.add_notification(
            {
                "type": "grant_activated",
                "grant_id": grant.id,
                "template_id": template.id,
                "app_instance_id": app_instance_id,
                "expires_at": grant.expires_at.isoformat(),
            }
        )

        token_pair = self.token_manager.issue_pair(
            grant_id=grant.id,
            app_instance_id=grant.app_instance_id,
            device_public_key=grant.device_public_key,
            role=grant.role.value,
        )
        policy = PolicyEngine(self.repository.list_area_nodes(), self.repository.get_registry_snapshot())
        return ActivationResult.from_token_pair(
            token_pair=token_pair,
            grant=grant,
            permission_summary=policy.permission_summary(grant),
        )

    def refresh(self, refresh_token: str, device_public_key: str) -> ActivationResult:
        payload = self.token_manager.verify(refresh_token, expected_type="refresh")
        self.token_manager.verify_device_binding(payload, device_public_key)
        grant_id = str(payload["grant_id"])
        grant = self.repository.get_grant(grant_id)
        if grant is None or not grant.is_active():
            raise ActivationError("grant is not active")
        token_pair = self.token_manager.issue_pair(
            grant_id=grant.id,
            app_instance_id=grant.app_instance_id,
            device_public_key=grant.device_public_key,
            role=grant.role.value,
        )
        policy = PolicyEngine(self.repository.list_area_nodes(), self.repository.get_registry_snapshot())
        return ActivationResult.from_token_pair(
            token_pair=token_pair,
            grant=grant,
            permission_summary=policy.permission_summary(grant),
        )

    def revoke(self, grant_id: str, actor: str) -> Grant:
        grant = self.repository.get_grant(grant_id)
        if grant is None:
            raise ActivationError("grant not found")
        revoked = grant.revoked()
        self.repository.update_grant(revoked)
        self.repository.add_audit_event("grant_revoked", actor=actor, target=grant_id)
        return revoked


class RequestAuthenticator:
    def __init__(self, repository: InMemoryRepository, token_manager: TokenManager) -> None:
        self.repository = repository
        self.token_manager = token_manager

    def authenticate_access_token(self, token: str, device_public_key: str | None = None) -> Grant:
        payload = self.token_manager.verify(token, expected_type="access")
        grant_id = str(payload["grant_id"])
        grant = self.repository.get_grant(grant_id)
        if grant is None or not grant.is_active():
            raise ActivationError("grant is not active")
        if device_public_key is not None:
            self.token_manager.verify_device_binding(payload, device_public_key)
        return grant
