from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from .models import AreaNode, AuditEvent, Grant, HaRegistrySnapshot, QRTemplate


class RepositoryError(ValueError):
    pass


class InMemoryRepository:
    def __init__(self) -> None:
        self.area_nodes: dict[str, AreaNode] = {}
        self.qr_templates: dict[str, QRTemplate] = {}
        self.grants: dict[str, Grant] = {}
        self.audit_events: list[AuditEvent] = []
        self.notifications: list[dict[str, Any]] = []
        self.registry_snapshot = HaRegistrySnapshot()
        self._lock = threading.RLock()

    def list_area_nodes(self) -> list[AreaNode]:
        return sorted(self.area_nodes.values(), key=lambda item: (item.parent_id or "", item.name))

    def upsert_area_node(self, node: AreaNode) -> AreaNode:
        with self._lock:
            if node.parent_id and node.parent_id not in self.area_nodes:
                raise RepositoryError(f"parent area node not found: {node.parent_id}")
            self.area_nodes[node.id] = node
            self._after_change()
            return node

    def delete_area_node(self, node_id: str) -> None:
        with self._lock:
            if any(node.parent_id == node_id for node in self.area_nodes.values()):
                raise RepositoryError("cannot delete an area node with children")
            self.area_nodes.pop(node_id, None)
            self._after_change()

    def list_qr_templates(self) -> list[QRTemplate]:
        return sorted(self.qr_templates.values(), key=lambda item: item.created_at)

    def get_qr_template(self, template_id: str) -> QRTemplate | None:
        return self.qr_templates.get(template_id)

    def upsert_qr_template(self, template: QRTemplate) -> QRTemplate:
        with self._lock:
            self.qr_templates[template.id] = template
            self._after_change()
            return template

    def create_grant(self, grant: Grant) -> Grant:
        with self._lock:
            self.grants[grant.id] = grant
            self._after_change()
            return grant

    def get_grant(self, grant_id: str) -> Grant | None:
        return self.grants.get(grant_id)

    def update_grant(self, grant: Grant) -> Grant:
        with self._lock:
            if grant.id not in self.grants:
                raise RepositoryError(f"grant not found: {grant.id}")
            self.grants[grant.id] = grant
            self._after_change()
            return grant

    def list_grants(self) -> list[Grant]:
        return sorted(self.grants.values(), key=lambda item: item.issued_at, reverse=True)

    def add_audit_event(
        self,
        event_type: str,
        actor: str,
        target: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            actor=actor,
            target=target,
            details=details or {},
        )
        with self._lock:
            self.audit_events.append(event)
            self._after_change()
        return event

    def list_audit_events(self) -> list[AuditEvent]:
        return list(reversed(self.audit_events))

    def add_notification(self, notification: dict[str, Any]) -> None:
        with self._lock:
            self.notifications.append(notification)
            self._after_change()

    def list_notifications(self) -> list[dict[str, Any]]:
        return list(reversed(self.notifications))

    def set_registry_snapshot(self, snapshot: HaRegistrySnapshot) -> None:
        with self._lock:
            self.registry_snapshot = snapshot
            self._after_change()

    def get_registry_snapshot(self) -> HaRegistrySnapshot:
        return self.registry_snapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "area_nodes": [node.to_dict() for node in self.area_nodes.values()],
            "qr_templates": [template.to_dict() for template in self.qr_templates.values()],
            "grants": [grant.to_dict() for grant in self.grants.values()],
            "audit_events": [event.to_dict() for event in self.audit_events],
            "notifications": self.notifications,
            "registry_snapshot": self.registry_snapshot.to_dict(),
        }

    def load_dict(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.area_nodes = {
                item["id"]: AreaNode.from_dict(item)
                for item in data.get("area_nodes", [])
            }
            self.qr_templates = {
                item["id"]: QRTemplate.from_dict(item)
                for item in data.get("qr_templates", [])
            }
            self.grants = {
                item["id"]: Grant.from_dict(item)
                for item in data.get("grants", [])
            }
            self.audit_events = [
                AuditEvent.from_dict(item)
                for item in data.get("audit_events", [])
            ]
            self.notifications = list(data.get("notifications", []))
            self.registry_snapshot = HaRegistrySnapshot.from_dict(data.get("registry_snapshot"))

    def _after_change(self) -> None:
        pass


class JsonFileRepository(InMemoryRepository):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        super().__init__()
        if self.path.exists():
            self.load_dict(json.loads(self.path.read_text(encoding="utf-8")))

    def _after_change(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

