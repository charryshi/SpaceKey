from __future__ import annotations

import unittest
from datetime import datetime, timezone

from permission_gateway.gateway.activation import ActivationError, ActivationService
from permission_gateway.gateway.activation import RequestAuthenticator
from permission_gateway.gateway.models import (
    AreaNode,
    DeviceRecord,
    EntityRecord,
    Grant,
    HaRegistrySnapshot,
    PermissionScope,
    QRTemplate,
    parse_dt,
)
from permission_gateway.gateway.repository import InMemoryRepository
from permission_gateway.gateway.security import (
    TokenError,
    TokenManager,
    hash_verification_code,
)


class TokenTests(unittest.TestCase):
    def test_token_signature_type_and_device_binding(self) -> None:
        manager = TokenManager("secret-value-with-enough-entropy")
        pair = manager.issue_pair(
            grant_id="grant-1",
            app_instance_id="ios-1",
            device_public_key="pub-key",
            role="guest",
        )

        payload = manager.verify(pair.access_token, expected_type="access")
        self.assertEqual(payload["grant_id"], "grant-1")
        manager.verify_device_binding(payload, "pub-key")

        with self.assertRaises(TokenError):
            manager.verify(pair.access_token, expected_type="refresh")
        with self.assertRaises(TokenError):
            manager.verify_device_binding(payload, "other-key")

    def test_expired_token_is_rejected(self) -> None:
        manager = TokenManager("secret-value-with-enough-entropy")
        token = manager.issue_token(
            token_type="access",
            grant_id="grant-1",
            app_instance_id="ios-1",
            device_public_key="pub-key",
            role="guest",
            ttl_seconds=-1,
        )

        with self.assertRaises(TokenError):
            manager.verify(token, expected_type="access")


class ActivationTests(unittest.TestCase):
    def test_qr_activation_creates_clamped_grant_and_notification(self) -> None:
        repository = InMemoryRepository()
        repository.upsert_area_node(
            AreaNode(id="room-1", name="Room 1", ha_area_ids=frozenset({"ha-room-1"}))
        )
        repository.set_registry_snapshot(
            HaRegistrySnapshot(
                devices={"dev-1": DeviceRecord(id="dev-1", area_id="ha-room-1")},
                entities={"light.room": EntityRecord(entity_id="light.room", device_id="dev-1")},
            )
        )
        repository.upsert_qr_template(
            QRTemplate(
                id="qr-room-1",
                name="Guest room access",
                verification_code_hash=hash_verification_code("246810", salt="fixed"),
                scope=PermissionScope(area_node_ids=frozenset({"room-1"})),
                default_ttl_seconds=60,
                max_ttl_seconds=120,
            )
        )
        service = ActivationService(
            repository,
            TokenManager("secret-value-with-enough-entropy"),
        )

        result = service.verify_qr(
            qr_id="qr-room-1",
            verification_code="246810",
            device_public_key="pub-key",
            app_instance_id="ios-installation-1",
            requested_ttl_seconds=999,
        )

        self.assertEqual(result.permission_summary["entity_ids"], ["light.room"])
        self.assertEqual(len(repository.list_grants()), 1)
        self.assertEqual(len(repository.list_notifications()), 1)
        expires_at = parse_dt(result.expires_at)
        self.assertIsNotNone(expires_at)
        self.assertLessEqual(
            (expires_at - datetime.now(timezone.utc)).total_seconds(),
            120,
        )

    def test_invalid_verification_code_is_rejected(self) -> None:
        repository = InMemoryRepository()
        repository.upsert_qr_template(
            QRTemplate(
                id="qr-room-1",
                name="Guest room access",
                verification_code_hash=hash_verification_code("246810", salt="fixed"),
                scope=PermissionScope(),
            )
        )
        service = ActivationService(
            repository,
            TokenManager("secret-value-with-enough-entropy"),
        )

        with self.assertRaises(ActivationError):
            service.verify_qr(
                qr_id="qr-room-1",
                verification_code="000000",
                device_public_key="pub-key",
                app_instance_id="ios-installation-1",
            )

    def test_non_positive_requested_ttl_is_rejected(self) -> None:
        repository = InMemoryRepository()
        repository.upsert_qr_template(
            QRTemplate(
                id="qr-room-1",
                name="Guest room access",
                verification_code_hash=hash_verification_code("246810", salt="fixed"),
                scope=PermissionScope(),
            )
        )
        service = ActivationService(
            repository,
            TokenManager("secret-value-with-enough-entropy"),
        )

        with self.assertRaises(ActivationError):
            service.verify_qr(
                qr_id="qr-room-1",
                verification_code="246810",
                device_public_key="pub-key",
                app_instance_id="ios-installation-1",
                requested_ttl_seconds=0,
            )

    def test_websocket_style_auth_can_skip_device_public_key(self) -> None:
        repository = InMemoryRepository()
        grant = Grant(
            id="grant-1",
            template_id="template-1",
            app_instance_id="web-installation-1",
            device_public_key="web-public-key",
            scope=PermissionScope(),
        )
        repository.create_grant(grant)
        manager = TokenManager("secret-value-with-enough-entropy")
        token = manager.issue_pair(
            grant_id=grant.id,
            app_instance_id=grant.app_instance_id,
            device_public_key=grant.device_public_key,
            role=grant.role.value,
        ).access_token
        authenticator = RequestAuthenticator(repository, manager)

        authenticated = authenticator.authenticate_access_token(token, device_public_key=None)

        self.assertEqual(authenticated.id, grant.id)


if __name__ == "__main__":
    unittest.main()
