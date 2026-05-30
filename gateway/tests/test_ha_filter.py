from __future__ import annotations

import unittest

from permission_gateway.gateway.ha_filter import HaMessageFilter
from permission_gateway.gateway.models import (
    AreaNode,
    DeviceRecord,
    EntityRecord,
    Grant,
    GrantRole,
    HaRegistrySnapshot,
    PermissionScope,
)
from permission_gateway.gateway.policy import PermissionDenied, PolicyEngine


class HaMessageFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        policy = PolicyEngine(
            area_nodes=[
                AreaNode(id="kitchen", name="Kitchen", ha_area_ids=frozenset({"ha-kitchen"})),
            ],
            registry=HaRegistrySnapshot(
                devices={
                    "dev-kettle": DeviceRecord(id="dev-kettle", area_id="ha-kitchen"),
                    "dev-bedroom": DeviceRecord(id="dev-bedroom", area_id="ha-bedroom"),
                },
                entities={
                    "switch.kettle": EntityRecord(entity_id="switch.kettle", device_id="dev-kettle"),
                    "button.kettle_identify": EntityRecord(
                        entity_id="button.kettle_identify",
                        device_id="dev-kettle",
                        entity_category="config",
                    ),
                    "light.bedroom": EntityRecord(entity_id="light.bedroom", device_id="dev-bedroom"),
                },
            ),
        )
        self.filter = HaMessageFilter(policy)
        self.grant = Grant(
            id="grant-1",
            template_id="template-1",
            app_instance_id="ios-1",
            device_public_key="pub",
            scope=PermissionScope(area_node_ids=frozenset({"kitchen"})),
        )

    def test_filters_state_results(self) -> None:
        message = {
            "id": 7,
            "type": "result",
            "success": True,
            "result": [
                {"entity_id": "switch.kettle", "state": "off"},
                {"entity_id": "button.kettle_identify", "state": "unknown"},
                {"entity_id": "light.bedroom", "state": "on"},
            ],
        }

        filtered = self.filter.filter_server_message(self.grant, message)

        self.assertEqual(filtered["result"], [{"entity_id": "switch.kettle", "state": "off"}])

    def test_drops_unauthorized_state_event(self) -> None:
        message = {
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {
                    "entity_id": "light.bedroom",
                    "new_state": {"entity_id": "light.bedroom", "state": "on"},
                },
            },
        }

        self.assertIsNone(self.filter.filter_server_message(self.grant, message))

    def test_rejects_mutating_registry_message(self) -> None:
        with self.assertRaises(PermissionDenied):
            self.filter.validate_client_message(
                self.grant,
                {"id": 5, "type": "config/entity_registry/update", "entity_id": "switch.kettle"},
            )

    def test_rejects_guest_admin_auth_and_config_websocket_messages(self) -> None:
        blocked_types = [
            "auth/long_lived_access_token",
            "auth/refresh_tokens",
            "config/entity_registry/list",
            "config_entries/get",
            "hassio/supervisor/info",
            "cloud/status",
        ]

        for message_type in blocked_types:
            with self.subTest(message_type=message_type):
                with self.assertRaises(PermissionDenied):
                    self.filter.validate_client_message(
                        self.grant,
                        {"id": 10, "type": message_type},
                    )

    def test_admin_grant_can_use_admin_websocket_messages(self) -> None:
        admin_grant = Grant(
            id="admin-grant",
            template_id=None,
            app_instance_id="admin",
            device_public_key="pub",
            scope=PermissionScope(),
            role=GrantRole.ADMIN,
        )

        self.filter.validate_client_message(
            admin_grant,
            {"id": 10, "type": "auth/long_lived_access_token"},
        )


if __name__ == "__main__":
    unittest.main()
