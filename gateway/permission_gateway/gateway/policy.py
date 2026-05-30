from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import AreaNode, Grant, GrantRole, HaRegistrySnapshot, PermissionScope


class PermissionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class AuthorizedResources:
    ha_area_ids: frozenset[str]
    device_ids: frozenset[str]
    entity_ids: frozenset[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ha_area_ids": sorted(self.ha_area_ids),
            "device_ids": sorted(self.device_ids),
            "entity_ids": sorted(self.entity_ids),
        }


class PolicyEngine:
    restricted_domains = {"script", "scene", "automation"}

    def __init__(
        self,
        area_nodes: list[AreaNode],
        registry: HaRegistrySnapshot,
    ) -> None:
        self.area_nodes = {node.id: node for node in area_nodes}
        self.registry = registry
        self.children: dict[str | None, list[AreaNode]] = {}
        for node in area_nodes:
            self.children.setdefault(node.parent_id, []).append(node)

    def authorized_resources(self, grant: Grant | None, scope: PermissionScope | None = None) -> AuthorizedResources:
        if grant is not None and grant.role == GrantRole.ADMIN:
            return AuthorizedResources(
                ha_area_ids=frozenset(
                    record.area_id
                    for record in self.registry.devices.values()
                    if record.area_id
                ),
                device_ids=frozenset(self.registry.devices.keys()),
                entity_ids=frozenset(self.registry.entities.keys()),
            )
        scope = scope or (grant.scope if grant is not None else PermissionScope())
        allowed_area_nodes = self._expand_area_nodes(scope.area_node_ids)
        ha_area_ids: set[str] = set()
        for node_id in allowed_area_nodes:
            node = self.area_nodes.get(node_id)
            if node:
                ha_area_ids.update(node.ha_area_ids)

        device_ids: set[str] = set(scope.include_device_ids)
        entity_ids: set[str] = set(scope.include_entity_ids)
        for ha_area_id in ha_area_ids:
            device_ids.update(self.registry.devices_for_area(ha_area_id))
            entity_ids.update(self.registry.default_visible_entities_for_area(ha_area_id))
        for device_id in list(device_ids):
            entity_ids.update(self.registry.default_visible_entities_for_device(device_id))

        device_ids.difference_update(scope.exclude_device_ids)
        for excluded_device_id in scope.exclude_device_ids:
            entity_ids.difference_update(self.registry.entities_for_device(excluded_device_id))
        entity_ids.difference_update(scope.exclude_entity_ids)

        return AuthorizedResources(
            ha_area_ids=frozenset(ha_area_ids),
            device_ids=frozenset(device_ids),
            entity_ids=frozenset(entity_ids),
        )

    def permission_summary(self, grant: Grant) -> dict[str, Any]:
        resources = self.authorized_resources(grant)
        return {
            "role": grant.role.value,
            "can_read": grant.scope.can_read or grant.role == GrantRole.ADMIN,
            "can_control": grant.scope.can_control or grant.role == GrantRole.ADMIN,
            **resources.to_dict(),
        }

    def is_entity_allowed(self, grant: Grant, entity_id: str) -> bool:
        if grant.role == GrantRole.ADMIN:
            return True
        if not grant.scope.can_read:
            return False
        return entity_id in self.authorized_resources(grant).entity_ids

    def filter_states(self, grant: Grant, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if grant.role == GrantRole.ADMIN:
            return states
        allowed = self.authorized_resources(grant).entity_ids
        return [
            state
            for state in states
            if state.get("entity_id") in allowed
        ]

    def filter_entity_registry(self, grant: Grant, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if grant.role == GrantRole.ADMIN:
            return records
        allowed = self.authorized_resources(grant).entity_ids
        return [
            record
            for record in records
            if record.get("entity_id") in allowed
        ]

    def filter_device_registry(self, grant: Grant, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if grant.role == GrantRole.ADMIN:
            return records
        allowed = self.authorized_resources(grant).device_ids
        return [
            record
            for record in records
            if record.get("id") in allowed
        ]

    def filter_area_registry(self, grant: Grant, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if grant.role == GrantRole.ADMIN:
            return records
        allowed = self.authorized_resources(grant).ha_area_ids
        return [
            record
            for record in records
            if record.get("area_id") in allowed or record.get("id") in allowed
        ]

    def assert_service_allowed(self, grant: Grant, message: dict[str, Any]) -> None:
        if grant.role == GrantRole.ADMIN:
            return
        if not grant.scope.can_control:
            raise PermissionDenied("grant cannot control devices")
        domain = str(message.get("domain") or "")
        service = str(message.get("service") or "")
        target = self._merged_target(message)
        if not domain or not service:
            raise PermissionDenied("service call must include domain and service")
        entity_ids = self._coerce_id_set(target.get("entity_id"))
        device_ids = self._coerce_id_set(target.get("device_id"))
        area_ids = self._coerce_id_set(target.get("area_id"))
        if target.get("all") is True:
            raise PermissionDenied("target all is not allowed")
        if not entity_ids and not device_ids and not area_ids:
            raise PermissionDenied("service call must include entity_id, device_id, or area_id target")

        resources = self.authorized_resources(grant)
        if domain in self.restricted_domains:
            self._assert_restricted_domain_allowed(grant.scope, domain, entity_ids, resources)
            return

        if entity_ids and not entity_ids.issubset(resources.entity_ids):
            raise PermissionDenied("service call includes unauthorized entity")
        if device_ids and not device_ids.issubset(resources.device_ids):
            raise PermissionDenied("service call includes unauthorized device")
        if area_ids and not area_ids.issubset(resources.ha_area_ids):
            raise PermissionDenied("service call includes unauthorized area")
        resolved_entity_ids = set(entity_ids)
        for device_id in device_ids:
            resolved_entity_ids.update(self._entities_for_device_and_domain(device_id, domain))
        for area_id in area_ids:
            resolved_entity_ids.update(self._entities_for_area_and_domain(area_id, domain))
        if (device_ids or area_ids) and not resolved_entity_ids:
            raise PermissionDenied("service call target has no authorized entities")
        if resolved_entity_ids and not resolved_entity_ids.issubset(resources.entity_ids):
            raise PermissionDenied("service call includes unauthorized entity")

    def _assert_restricted_domain_allowed(
        self,
        scope: PermissionScope,
        domain: str,
        entity_ids: set[str],
        resources: AuthorizedResources,
    ) -> None:
        if not entity_ids:
            raise PermissionDenied(f"{domain} calls require explicit entity targets")
        allowed_by_domain = {
            "script": scope.allowed_script_entity_ids,
            "scene": scope.allowed_scene_entity_ids,
            "automation": scope.allowed_automation_entity_ids,
        }[domain]
        allowed_entity_ids = set(resources.entity_ids).union(allowed_by_domain)
        if not entity_ids.issubset(allowed_entity_ids):
            raise PermissionDenied(f"{domain} entity is not in the authorized scope")

    def _expand_area_nodes(self, root_ids: frozenset[str]) -> set[str]:
        expanded: set[str] = set()
        stack = list(root_ids)
        while stack:
            node_id = stack.pop()
            if node_id in expanded:
                continue
            expanded.add(node_id)
            stack.extend(child.id for child in self.children.get(node_id, []))
        return expanded

    def _merged_target(self, message: dict[str, Any]) -> dict[str, Any]:
        target = dict(message.get("target") or {})
        service_data = message.get("service_data") or {}
        data = message.get("data") or {}
        if isinstance(service_data, dict):
            for key in ("entity_id", "device_id", "area_id"):
                if key in service_data and key not in target:
                    target[key] = service_data[key]
        if isinstance(data, dict):
            for key in ("entity_id", "device_id", "area_id"):
                if key in data and key not in target:
                    target[key] = data[key]
        return target

    def _entities_for_device_and_domain(self, device_id: str, domain: str) -> set[str]:
        return {
            entity_id
            for entity_id, record in self.registry.entities.items()
            if record.device_id == device_id and record.domain == domain
        }

    def _entities_for_area_and_domain(self, area_id: str, domain: str) -> set[str]:
        entity_ids = {
            entity_id
            for entity_id, record in self.registry.entities.items()
            if record.area_id == area_id and record.domain == domain
        }
        for device_id in self.registry.devices_for_area(area_id):
            entity_ids.update(self._entities_for_device_and_domain(device_id, domain))
        return entity_ids

    def _coerce_id_set(self, value: Any) -> set[str]:
        if value is None:
            return set()
        if isinstance(value, str):
            return {value}
        if isinstance(value, list | tuple | set | frozenset):
            return {str(item) for item in value if item is not None}
        return {str(value)}
