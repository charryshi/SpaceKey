from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def dt_to_json(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def frozen_set(value: Any) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, str):
        return frozenset({value})
    return frozenset(str(item) for item in value if item is not None and str(item))


class GrantRole(str, Enum):
    GUEST = "guest"
    ADMIN = "admin"


@dataclass(frozen=True)
class PermissionScope:
    area_node_ids: frozenset[str] = field(default_factory=frozenset)
    include_device_ids: frozenset[str] = field(default_factory=frozenset)
    include_entity_ids: frozenset[str] = field(default_factory=frozenset)
    exclude_device_ids: frozenset[str] = field(default_factory=frozenset)
    exclude_entity_ids: frozenset[str] = field(default_factory=frozenset)
    allowed_script_entity_ids: frozenset[str] = field(default_factory=frozenset)
    allowed_scene_entity_ids: frozenset[str] = field(default_factory=frozenset)
    allowed_automation_entity_ids: frozenset[str] = field(default_factory=frozenset)
    can_read: bool = True
    can_control: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PermissionScope:
        data = data or {}
        return cls(
            area_node_ids=frozen_set(data.get("area_node_ids")),
            include_device_ids=frozen_set(data.get("include_device_ids")),
            include_entity_ids=frozen_set(data.get("include_entity_ids")),
            exclude_device_ids=frozen_set(data.get("exclude_device_ids")),
            exclude_entity_ids=frozen_set(data.get("exclude_entity_ids")),
            allowed_script_entity_ids=frozen_set(data.get("allowed_script_entity_ids")),
            allowed_scene_entity_ids=frozen_set(data.get("allowed_scene_entity_ids")),
            allowed_automation_entity_ids=frozen_set(data.get("allowed_automation_entity_ids")),
            can_read=bool(data.get("can_read", True)),
            can_control=bool(data.get("can_control", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "area_node_ids": sorted(self.area_node_ids),
            "include_device_ids": sorted(self.include_device_ids),
            "include_entity_ids": sorted(self.include_entity_ids),
            "exclude_device_ids": sorted(self.exclude_device_ids),
            "exclude_entity_ids": sorted(self.exclude_entity_ids),
            "allowed_script_entity_ids": sorted(self.allowed_script_entity_ids),
            "allowed_scene_entity_ids": sorted(self.allowed_scene_entity_ids),
            "allowed_automation_entity_ids": sorted(self.allowed_automation_entity_ids),
            "can_read": self.can_read,
            "can_control": self.can_control,
        }


@dataclass(frozen=True)
class AreaNode:
    id: str
    name: str
    parent_id: str | None = None
    ha_area_ids: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AreaNode:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            parent_id=data.get("parent_id"),
            ha_area_ids=frozen_set(data.get("ha_area_ids")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "ha_area_ids": sorted(self.ha_area_ids),
        }


@dataclass(frozen=True)
class EntityRecord:
    entity_id: str
    device_id: str | None = None
    area_id: str | None = None
    platform: str | None = None
    name: str | None = None
    entity_category: str | None = None
    disabled_by: str | None = None
    hidden_by: str | None = None

    @property
    def domain(self) -> str:
        return self.entity_id.split(".", 1)[0] if "." in self.entity_id else ""

    @property
    def is_default_visible(self) -> bool:
        return not self.entity_category and not self.disabled_by and not self.hidden_by

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityRecord:
        return cls(
            entity_id=str(data["entity_id"]),
            device_id=data.get("device_id"),
            area_id=data.get("area_id"),
            platform=data.get("platform"),
            name=data.get("name"),
            entity_category=data.get("entity_category"),
            disabled_by=data.get("disabled_by"),
            hidden_by=data.get("hidden_by"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "device_id": self.device_id,
            "area_id": self.area_id,
            "platform": self.platform,
            "name": self.name,
            "entity_category": self.entity_category,
            "disabled_by": self.disabled_by,
            "hidden_by": self.hidden_by,
        }


@dataclass(frozen=True)
class DeviceRecord:
    id: str
    area_id: str | None = None
    name: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceRecord:
        return cls(id=str(data["id"]), area_id=data.get("area_id"), name=data.get("name"))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "area_id": self.area_id, "name": self.name}


@dataclass(frozen=True)
class HaAreaRecord:
    id: str
    name: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HaAreaRecord:
        area_id = data.get("id") or data.get("area_id")
        return cls(id=str(area_id), name=data.get("name"))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "area_id": self.id, "name": self.name}


@dataclass(frozen=True)
class HaRegistrySnapshot:
    areas: dict[str, HaAreaRecord] = field(default_factory=dict)
    entities: dict[str, EntityRecord] = field(default_factory=dict)
    devices: dict[str, DeviceRecord] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> HaRegistrySnapshot:
        data = data or {}
        areas: dict[str, HaAreaRecord] = {}
        for item in data.get("areas", []):
            area_id = item.get("id") or item.get("area_id")
            if area_id:
                areas[str(area_id)] = HaAreaRecord.from_dict(item)
        return cls(
            areas=areas,
            entities={
                item["entity_id"]: EntityRecord.from_dict(item)
                for item in data.get("entities", [])
            },
            devices={item["id"]: DeviceRecord.from_dict(item) for item in data.get("devices", [])},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "areas": [record.to_dict() for record in self.areas.values()],
            "entities": [record.to_dict() for record in self.entities.values()],
            "devices": [record.to_dict() for record in self.devices.values()],
        }

    def entities_for_device(self, device_id: str) -> set[str]:
        return {
            entity_id
            for entity_id, record in self.entities.items()
            if record.device_id == device_id
        }

    def devices_for_area(self, area_id: str) -> set[str]:
        return {
            device_id
            for device_id, record in self.devices.items()
            if record.area_id == area_id
        }

    def entities_for_area(self, area_id: str) -> set[str]:
        entity_ids = {
            entity_id
            for entity_id, record in self.entities.items()
            if record.area_id == area_id
        }
        for device_id in self.devices_for_area(area_id):
            entity_ids.update(self.entities_for_device(device_id))
        return entity_ids

    def default_visible_entities_for_device(self, device_id: str) -> set[str]:
        return {
            entity_id
            for entity_id, record in self.entities.items()
            if record.device_id == device_id and record.is_default_visible
        }

    def default_visible_entities_for_area(self, area_id: str) -> set[str]:
        entity_ids = {
            entity_id
            for entity_id, record in self.entities.items()
            if record.area_id == area_id and record.is_default_visible
        }
        for device_id in self.devices_for_area(area_id):
            entity_ids.update(self.default_visible_entities_for_device(device_id))
        return entity_ids


@dataclass(frozen=True)
class QRTemplate:
    id: str
    name: str
    verification_code_hash: str
    scope: PermissionScope
    enabled: bool = True
    default_ttl_seconds: int = 86_400
    max_ttl_seconds: int = 604_800
    created_at: datetime = field(default_factory=utcnow)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRTemplate:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            verification_code_hash=str(data["verification_code_hash"]),
            scope=PermissionScope.from_dict(data.get("scope")),
            enabled=bool(data.get("enabled", True)),
            default_ttl_seconds=int(data.get("default_ttl_seconds", 86_400)),
            max_ttl_seconds=int(data.get("max_ttl_seconds", 604_800)),
            created_at=parse_dt(data.get("created_at")) or utcnow(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "verification_code_hash": self.verification_code_hash,
            "scope": self.scope.to_dict(),
            "enabled": self.enabled,
            "default_ttl_seconds": self.default_ttl_seconds,
            "max_ttl_seconds": self.max_ttl_seconds,
            "created_at": dt_to_json(self.created_at),
        }


@dataclass(frozen=True)
class Grant:
    id: str
    template_id: str | None
    app_instance_id: str
    device_public_key: str
    scope: PermissionScope
    role: GrantRole = GrantRole.GUEST
    issued_at: datetime = field(default_factory=utcnow)
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or utcnow()
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= now:
            return False
        return True

    def with_expiry(self, expires_at: datetime | None) -> Grant:
        return replace(self, expires_at=expires_at)

    def revoked(self, at: datetime | None = None) -> Grant:
        return replace(self, revoked_at=at or utcnow())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Grant:
        return cls(
            id=str(data["id"]),
            template_id=data.get("template_id"),
            app_instance_id=str(data["app_instance_id"]),
            device_public_key=str(data["device_public_key"]),
            scope=PermissionScope.from_dict(data.get("scope")),
            role=GrantRole(data.get("role", GrantRole.GUEST.value)),
            issued_at=parse_dt(data.get("issued_at")) or utcnow(),
            expires_at=parse_dt(data.get("expires_at")),
            revoked_at=parse_dt(data.get("revoked_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "app_instance_id": self.app_instance_id,
            "device_public_key": self.device_public_key,
            "scope": self.scope.to_dict(),
            "role": self.role.value,
            "issued_at": dt_to_json(self.issued_at),
            "expires_at": dt_to_json(self.expires_at),
            "revoked_at": dt_to_json(self.revoked_at),
        }


@dataclass(frozen=True)
class AuditEvent:
    id: str
    event_type: str
    actor: str
    target: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEvent:
        return cls(
            id=str(data["id"]),
            event_type=str(data["event_type"]),
            actor=str(data["actor"]),
            target=str(data["target"]),
            details=dict(data.get("details") or {}),
            created_at=parse_dt(data.get("created_at")) or utcnow(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "actor": self.actor,
            "target": self.target,
            "details": self.details,
            "created_at": dt_to_json(self.created_at),
        }
