from __future__ import annotations

import unittest

from permission_gateway.gateway.models import (
    AreaNode,
    DeviceRecord,
    EntityRecord,
    Grant,
    HaRegistrySnapshot,
    PermissionScope,
)
from permission_gateway.gateway.policy import PermissionDenied, PolicyEngine


def sample_policy() -> PolicyEngine:
    return PolicyEngine(
        area_nodes=[
            AreaNode(id="project-a", name="Project A"),
            AreaNode(id="floor-1", name="Floor 1", parent_id="project-a"),
            AreaNode(id="kitchen", name="Kitchen", parent_id="floor-1", ha_area_ids=frozenset({"ha-kitchen"})),
            AreaNode(id="bedroom", name="Bedroom", parent_id="floor-1", ha_area_ids=frozenset({"ha-bedroom"})),
        ],
        registry=HaRegistrySnapshot(
            devices={
                "dev-kettle": DeviceRecord(id="dev-kettle", area_id="ha-kitchen"),
                "dev-lamp": DeviceRecord(id="dev-lamp", area_id="ha-bedroom"),
                "dev-garden": DeviceRecord(id="dev-garden", area_id="ha-garden"),
            },
            entities={
                "switch.kettle": EntityRecord(entity_id="switch.kettle", device_id="dev-kettle"),
                "button.kettle_identify": EntityRecord(
                    entity_id="button.kettle_identify",
                    device_id="dev-kettle",
                    entity_category="config",
                ),
                "sensor.kettle_signal": EntityRecord(
                    entity_id="sensor.kettle_signal",
                    device_id="dev-kettle",
                    entity_category="diagnostic",
                ),
                "sensor.kitchen_temp": EntityRecord(entity_id="sensor.kitchen_temp", area_id="ha-kitchen"),
                "light.bedroom": EntityRecord(entity_id="light.bedroom", device_id="dev-lamp"),
                "script.kitchen_reset": EntityRecord(entity_id="script.kitchen_reset", area_id="ha-kitchen"),
                "switch.garden": EntityRecord(entity_id="switch.garden", device_id="dev-garden"),
            },
        ),
    )


class PolicyEngineTests(unittest.TestCase):
    def test_area_grant_expands_children_and_applies_exclusions(self) -> None:
        grant = Grant(
            id="grant-1",
            template_id="template-1",
            app_instance_id="ios-1",
            device_public_key="pub",
            scope=PermissionScope(
                area_node_ids=frozenset({"floor-1"}),
                exclude_entity_ids=frozenset({"light.bedroom"}),
            ),
        )

        resources = sample_policy().authorized_resources(grant)

        self.assertEqual(resources.ha_area_ids, frozenset({"ha-kitchen", "ha-bedroom"}))
        self.assertIn("dev-kettle", resources.device_ids)
        self.assertIn("dev-lamp", resources.device_ids)
        self.assertIn("switch.kettle", resources.entity_ids)
        self.assertIn("sensor.kitchen_temp", resources.entity_ids)
        self.assertNotIn("button.kettle_identify", resources.entity_ids)
        self.assertNotIn("sensor.kettle_signal", resources.entity_ids)
        self.assertNotIn("light.bedroom", resources.entity_ids)
        self.assertNotIn("switch.garden", resources.entity_ids)

    def test_explicit_entity_include_can_authorize_non_primary_entity(self) -> None:
        grant = Grant(
            id="grant-1",
            template_id="template-1",
            app_instance_id="ios-1",
            device_public_key="pub",
            scope=PermissionScope(
                area_node_ids=frozenset({"kitchen"}),
                include_entity_ids=frozenset({"button.kettle_identify"}),
            ),
        )

        resources = sample_policy().authorized_resources(grant)

        self.assertIn("button.kettle_identify", resources.entity_ids)

    def test_device_include_and_exclude_controls_entities(self) -> None:
        grant = Grant(
            id="grant-1",
            template_id="template-1",
            app_instance_id="ios-1",
            device_public_key="pub",
            scope=PermissionScope(
                include_device_ids=frozenset({"dev-garden"}),
                exclude_device_ids=frozenset({"dev-garden"}),
            ),
        )

        resources = sample_policy().authorized_resources(grant)

        self.assertNotIn("dev-garden", resources.device_ids)
        self.assertNotIn("switch.garden", resources.entity_ids)

    def test_service_call_requires_explicit_authorized_target(self) -> None:
        grant = Grant(
            id="grant-1",
            template_id="template-1",
            app_instance_id="ios-1",
            device_public_key="pub",
            scope=PermissionScope(area_node_ids=frozenset({"kitchen"})),
        )
        policy = sample_policy()

        policy.assert_service_allowed(
            grant,
            {
                "type": "call_service",
                "domain": "switch",
                "service": "turn_on",
                "target": {"entity_id": "switch.kettle"},
            },
        )

        with self.assertRaises(PermissionDenied):
            policy.assert_service_allowed(
                grant,
                {"type": "call_service", "domain": "light", "service": "turn_on"},
            )

        with self.assertRaises(PermissionDenied):
            policy.assert_service_allowed(
                grant,
                {
                    "type": "call_service",
                    "domain": "light",
                    "service": "turn_on",
                    "target": {"entity_id": "light.bedroom"},
                },
            )

    def test_device_target_cannot_indirectly_control_non_primary_entity(self) -> None:
        policy = sample_policy()
        area_grant = Grant(
            id="grant-1",
            template_id="template-1",
            app_instance_id="ios-1",
            device_public_key="pub",
            scope=PermissionScope(area_node_ids=frozenset({"kitchen"})),
        )
        explicit_grant = Grant(
            id="grant-2",
            template_id="template-1",
            app_instance_id="ios-1",
            device_public_key="pub",
            scope=PermissionScope(
                area_node_ids=frozenset({"kitchen"}),
                include_entity_ids=frozenset({"button.kettle_identify"}),
            ),
        )

        with self.assertRaises(PermissionDenied):
            policy.assert_service_allowed(
                area_grant,
                {
                    "type": "call_service",
                    "domain": "button",
                    "service": "press",
                    "target": {"device_id": "dev-kettle"},
                },
            )

        policy.assert_service_allowed(
            explicit_grant,
            {
                "type": "call_service",
                "domain": "button",
                "service": "press",
                "target": {"device_id": "dev-kettle"},
            },
        )

    def test_script_scene_automation_allowed_when_entity_is_in_authorized_scope(self) -> None:
        policy = sample_policy()
        area_grant = Grant(
            id="grant-1",
            template_id="template-1",
            app_instance_id="ios-1",
            device_public_key="pub",
            scope=PermissionScope(area_node_ids=frozenset({"kitchen"})),
        )
        explicit_grant = Grant(
            id="grant-2",
            template_id="template-1",
            app_instance_id="ios-1",
            device_public_key="pub",
            scope=PermissionScope(allowed_script_entity_ids=frozenset({"script.unlock_room"})),
        )

        policy.assert_service_allowed(
            area_grant,
            {
                "type": "call_service",
                "domain": "script",
                "service": "turn_on",
                "target": {"entity_id": "script.kitchen_reset"},
            },
        )

        policy.assert_service_allowed(
            explicit_grant,
            {
                "type": "call_service",
                "domain": "script",
                "service": "turn_on",
                "target": {"entity_id": "script.unlock_room"},
            },
        )

        with self.assertRaises(PermissionDenied):
            policy.assert_service_allowed(
                area_grant,
                {
                    "type": "call_service",
                    "domain": "script",
                    "service": "turn_on",
                    "target": {"entity_id": "script.unlock_room"},
                },
            )


if __name__ == "__main__":
    unittest.main()
