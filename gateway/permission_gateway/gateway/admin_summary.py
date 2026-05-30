from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .models import Grant, HaRegistrySnapshot, QRTemplate, utcnow
from .policy import PolicyEngine
from .repository import InMemoryRepository


def grant_status(grant: Grant, now: datetime | None = None) -> str:
    now = now or utcnow()
    if grant.revoked_at is not None:
        return "revoked"
    if grant.expires_at is not None and grant.expires_at <= now:
        return "expired"
    return "active"


def build_dashboard_summary(
    repository: InMemoryRepository,
    *,
    home_assistant_token_configured: bool,
    ha_connection_status: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    expiring_before = now + timedelta(hours=24)
    grants = repository.list_grants()
    active_grants = [grant for grant in grants if grant_status(grant, now) == "active"]
    expiring_grants = [
        grant
        for grant in active_grants
        if grant.expires_at is not None and grant.expires_at <= expiring_before
    ]
    snapshot = repository.get_registry_snapshot()
    audit_events = repository.list_audit_events()
    denial_types = {"activation_denied", "service_call_denied", "access_denied"}

    return {
        "counts": {
            "active_keys": len(active_grants),
            "expiring_keys": len(expiring_grants),
            "revoked_keys": len([grant for grant in grants if grant_status(grant, now) == "revoked"]),
            "templates": len(repository.list_qr_templates()),
            "places": len(repository.list_area_nodes()),
            "devices": len(snapshot.devices),
            "entities": len(snapshot.entities),
        },
        "home_assistant": {
            "token_configured": home_assistant_token_configured,
            "connection_status": ha_connection_status,
            "registry_synced": bool(snapshot.devices or snapshot.entities),
            "registry_last_synced_at": _last_registry_sync_at(audit_events),
            "registry_area_count": len(snapshot.areas),
            "registry_device_count": len(snapshot.devices),
            "registry_entity_count": len(snapshot.entities),
        },
        "recent_activations": [
            event.to_dict()
            for event in audit_events
            if event.event_type == "activation_granted"
        ][:5],
        "recent_denials": [
            event.to_dict()
            for event in audit_events
            if event.event_type in denial_types
        ][:5],
        "expiring_grants": [grant.to_dict() for grant in expiring_grants[:10]],
    }


def build_ha_browser(
    repository: InMemoryRepository,
) -> dict[str, Any]:
    snapshot = repository.get_registry_snapshot()
    templates = repository.list_qr_templates()
    policy = PolicyEngine(repository.list_area_nodes(), snapshot)
    entity_coverage = _template_entity_coverage(policy, templates)
    device_coverage = _device_coverage(snapshot, entity_coverage)
    area_ids = sorted(
        {
            area_id
            for area_id in [
                *snapshot.areas.keys(),
                *(record.area_id for record in snapshot.devices.values()),
                *(record.area_id for record in snapshot.entities.values()),
            ]
            if area_id
        }
    )

    return {
        "areas": [
            {
                "area_id": area_id,
                "name": snapshot.areas[area_id].name if area_id in snapshot.areas else None,
                "device_count": len(snapshot.devices_for_area(area_id)),
                "entity_count": len(snapshot.entities_for_area(area_id)),
                "default_visible_entity_count": len(snapshot.default_visible_entities_for_area(area_id)),
            }
            for area_id in area_ids
        ],
        "devices": [
            {
                **device.to_dict(),
                "entity_count": len(snapshot.entities_for_device(device.id)),
                "default_visible_entity_count": len(snapshot.default_visible_entities_for_device(device.id)),
                "covered_by_templates": sorted(device_coverage.get(device.id, set())),
                "warnings": ["missing_area"] if not device.area_id else [],
            }
            for device in sorted(snapshot.devices.values(), key=lambda item: item.id)
        ],
        "entities": [
            {
                **entity.to_dict(),
                "display_name": entity.name or entity.entity_id,
                "effective_area_id": entity.area_id or _entity_device_area(snapshot, entity.entity_id),
                "covered_by_templates": sorted(entity_coverage.get(entity.entity_id, set())),
                "default_visible": entity.is_default_visible,
                "warnings": _entity_warnings(snapshot, entity.entity_id),
            }
            for entity in sorted(snapshot.entities.values(), key=lambda item: item.entity_id)
        ],
    }


def template_permission_preview(
    repository: InMemoryRepository,
    scope: dict[str, Any],
) -> dict[str, Any]:
    policy = PolicyEngine(repository.list_area_nodes(), repository.get_registry_snapshot())
    from .models import PermissionScope

    resources = policy.authorized_resources(None, PermissionScope.from_dict(scope))
    risky = {
        "scripts": sorted(PermissionScope.from_dict(scope).allowed_script_entity_ids),
        "scenes": sorted(PermissionScope.from_dict(scope).allowed_scene_entity_ids),
        "automations": sorted(PermissionScope.from_dict(scope).allowed_automation_entity_ids),
    }
    return {
        "ha_area_count": len(resources.ha_area_ids),
        "device_count": len(resources.device_ids),
        "entity_count": len(resources.entity_ids),
        "resources": resources.to_dict(),
        "high_risk_allowlist": risky,
        "has_high_risk_allowlist": any(risky.values()),
    }


def _template_entity_coverage(
    policy: PolicyEngine,
    templates: list[QRTemplate],
) -> dict[str, set[str]]:
    coverage: dict[str, set[str]] = {}
    for template in templates:
        resources = policy.authorized_resources(None, template.scope)
        for entity_id in resources.entity_ids:
            coverage.setdefault(entity_id, set()).add(template.id)
    return coverage


def _device_coverage(
    snapshot: HaRegistrySnapshot,
    entity_coverage: dict[str, set[str]],
) -> dict[str, set[str]]:
    coverage: dict[str, set[str]] = {}
    for entity_id, template_ids in entity_coverage.items():
        entity = snapshot.entities.get(entity_id)
        if entity and entity.device_id:
            coverage.setdefault(entity.device_id, set()).update(template_ids)
    return coverage


def _entity_device_area(snapshot: HaRegistrySnapshot, entity_id: str) -> str | None:
    entity = snapshot.entities.get(entity_id)
    if not entity or not entity.device_id:
        return None
    device = snapshot.devices.get(entity.device_id)
    return device.area_id if device else None


def _entity_warnings(snapshot: HaRegistrySnapshot, entity_id: str) -> list[str]:
    entity = snapshot.entities.get(entity_id)
    if entity is None:
        return []
    warnings: list[str] = []
    if not entity.area_id and not _entity_device_area(snapshot, entity.entity_id):
        warnings.append("missing_area")
    if entity.entity_category:
        warnings.append(f"entity_category:{entity.entity_category}")
    if entity.hidden_by:
        warnings.append("hidden")
    if entity.disabled_by:
        warnings.append("disabled")
    return warnings


def _last_registry_sync_at(audit_events: list[Any]) -> str | None:
    for event in audit_events:
        if event.event_type in {"ha_registry_synced", "ha_registry_snapshot_updated"}:
            return event.to_dict()["created_at"]
    return None
