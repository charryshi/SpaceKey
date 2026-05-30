from __future__ import annotations

import unittest
from datetime import timedelta

from permission_gateway.gateway.admin_summary import build_dashboard_summary, build_ha_browser
from permission_gateway.gateway.models import (
    AreaNode,
    DeviceRecord,
    EntityRecord,
    HaAreaRecord,
    Grant,
    HaRegistrySnapshot,
    PermissionScope,
    QRTemplate,
    utcnow,
)
from permission_gateway.gateway.repository import InMemoryRepository
from permission_gateway.gateway.security import hash_verification_code


class AdminSummaryTests(unittest.TestCase):
    def test_dashboard_counts_active_expiring_and_denials(self) -> None:
        repository = InMemoryRepository()
        now = utcnow()
        repository.create_grant(
            Grant(
                id="active",
                template_id="template",
                app_instance_id="ios-1",
                device_public_key="pub",
                scope=PermissionScope(),
                expires_at=now + timedelta(days=2),
            )
        )
        repository.create_grant(
            Grant(
                id="expiring",
                template_id="template",
                app_instance_id="ios-2",
                device_public_key="pub",
                scope=PermissionScope(),
                expires_at=now + timedelta(hours=2),
            )
        )
        repository.create_grant(
            Grant(
                id="revoked",
                template_id="template",
                app_instance_id="ios-3",
                device_public_key="pub",
                scope=PermissionScope(),
                revoked_at=now,
            )
        )
        repository.add_audit_event("activation_denied", actor="ios-4", target="qr")

        summary = build_dashboard_summary(
            repository,
            home_assistant_token_configured=False,
            ha_connection_status="not_configured",
            now=now,
        )

        self.assertEqual(summary["counts"]["active_keys"], 2)
        self.assertEqual(summary["counts"]["expiring_keys"], 1)
        self.assertEqual(summary["counts"]["revoked_keys"], 1)
        self.assertEqual(summary["home_assistant"]["connection_status"], "not_configured")
        self.assertEqual(len(summary["recent_denials"]), 1)

    def test_ha_browser_marks_template_coverage_and_missing_area(self) -> None:
        repository = InMemoryRepository()
        repository.upsert_area_node(
            AreaNode(id="room-1", name="Room 1", ha_area_ids=frozenset({"ha-room"}))
        )
        repository.set_registry_snapshot(
            HaRegistrySnapshot(
                areas={"ha-empty": HaAreaRecord(id="ha-empty", name="Empty Area")},
                devices={
                    "dev-room": DeviceRecord(id="dev-room", area_id="ha-room"),
                    "dev-unbound": DeviceRecord(id="dev-unbound"),
                },
                entities={
                    "light.room": EntityRecord(entity_id="light.room", device_id="dev-room"),
                    "button.room_identify": EntityRecord(
                        entity_id="button.room_identify",
                        device_id="dev-room",
                        entity_category="config",
                    ),
                    "switch.unbound": EntityRecord(entity_id="switch.unbound", device_id="dev-unbound"),
                },
            )
        )
        repository.upsert_qr_template(
            QRTemplate(
                id="template-room",
                name="Room",
                verification_code_hash=hash_verification_code("123456", salt="fixed"),
                scope=PermissionScope(area_node_ids=frozenset({"room-1"})),
            )
        )

        browser = build_ha_browser(repository)

        room_entity = next(item for item in browser["entities"] if item["entity_id"] == "light.room")
        config_entity = next(item for item in browser["entities"] if item["entity_id"] == "button.room_identify")
        room_device = next(item for item in browser["devices"] if item["id"] == "dev-room")
        unbound_device = next(item for item in browser["devices"] if item["id"] == "dev-unbound")
        empty_area = next(item for item in browser["areas"] if item["area_id"] == "ha-empty")
        self.assertEqual(room_entity["covered_by_templates"], ["template-room"])
        self.assertEqual(config_entity["covered_by_templates"], [])
        self.assertEqual(config_entity["warnings"], ["entity_category:config"])
        self.assertEqual(room_device["default_visible_entity_count"], 1)
        self.assertEqual(unbound_device["warnings"], ["missing_area"])
        self.assertEqual(empty_area["name"], "Empty Area")


if __name__ == "__main__":
    unittest.main()
