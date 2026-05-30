from __future__ import annotations

import unittest

from permission_gateway.gateway.ha_registry_sync import build_snapshot_from_registries


class HaRegistrySyncTests(unittest.TestCase):
    def test_build_snapshot_from_ha_registry_payloads(self) -> None:
        snapshot = build_snapshot_from_registries(
            areas=[
                {"area_id": "kitchen", "name": "Kitchen"},
                {"id": "garage", "name": "Garage"},
            ],
            devices=[
                {"id": "device-1", "area_id": "kitchen", "name_by_user": "Kettle"},
                {"id": "device-2", "area_id": None, "name": "Unbound"},
            ],
            entities=[
                {
                    "entity_id": "switch.kettle",
                    "device_id": "device-1",
                    "platform": "switch",
                    "name": "Kettle Switch",
                    "entity_category": "config",
                    "disabled_by": None,
                    "hidden_by": "user",
                },
                {"entity_id": "sensor.loose", "area_id": "garage", "platform": "sensor"},
            ],
        )

        self.assertEqual(snapshot.areas["kitchen"].name, "Kitchen")
        self.assertEqual(snapshot.areas["garage"].name, "Garage")
        self.assertEqual(snapshot.devices["device-1"].name, "Kettle")
        self.assertEqual(snapshot.entities["switch.kettle"].device_id, "device-1")
        self.assertEqual(snapshot.entities["switch.kettle"].name, "Kettle Switch")
        self.assertEqual(snapshot.entities["switch.kettle"].entity_category, "config")
        self.assertEqual(snapshot.entities["switch.kettle"].hidden_by, "user")
        self.assertEqual(snapshot.entities["sensor.loose"].area_id, "garage")


if __name__ == "__main__":
    unittest.main()
