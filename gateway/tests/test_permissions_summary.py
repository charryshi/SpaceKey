from __future__ import annotations

import unittest

from permission_gateway.gateway.app import _permission_summary_with_template
from permission_gateway.gateway.models import (
    AreaNode,
    DeviceRecord,
    EntityRecord,
    Grant,
    HaRegistrySnapshot,
    PermissionScope,
    QRTemplate,
)
from permission_gateway.gateway.policy import PolicyEngine
from permission_gateway.gateway.repository import InMemoryRepository
from permission_gateway.gateway.security import hash_verification_code


class PermissionsSummaryTests(unittest.TestCase):
    def test_summary_includes_template_display_name(self) -> None:
        repository = InMemoryRepository()
        repository.upsert_area_node(
            AreaNode(id="room-1", name="Room 1", ha_area_ids=frozenset({"ha-room"}))
        )
        repository.set_registry_snapshot(
            HaRegistrySnapshot(
                devices={"dev-1": DeviceRecord(id="dev-1", area_id="ha-room")},
                entities={"light.room": EntityRecord(entity_id="light.room", device_id="dev-1")},
            )
        )
        repository.upsert_qr_template(
            QRTemplate(
                id="template-room",
                name="客房 101 授权",
                verification_code_hash=hash_verification_code("123456", salt="fixed"),
                scope=PermissionScope(area_node_ids=frozenset({"room-1"})),
            )
        )
        grant = Grant(
            id="grant-1",
            template_id="template-room",
            app_instance_id="ios-1",
            device_public_key="pub",
            scope=PermissionScope(area_node_ids=frozenset({"room-1"})),
        )
        policy = PolicyEngine(repository.list_area_nodes(), repository.get_registry_snapshot())

        summary = _permission_summary_with_template(repository, policy, grant)

        self.assertEqual(summary["template_name"], "客房 101 授权")
        self.assertEqual(summary["display_name"], "客房 101 授权")
        self.assertEqual(summary["template_id"], "template-room")


if __name__ == "__main__":
    unittest.main()

