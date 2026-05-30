from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import Grant, GrantRole
from .policy import PermissionDenied, PolicyEngine


BLOCKED_GUEST_WS_TYPES = {
    "auth/refresh_tokens",
    "auth/delete_refresh_token",
    "auth/delete_all_refresh_tokens",
    "auth/refresh_token_set_expiry",
    "auth/long_lived_access_token",
}

BLOCKED_GUEST_WS_PREFIXES = (
    "config/",
    "config_entries/",
    "device_registry/",
    "entity_registry/",
    "area_registry/",
    "floor_registry/",
    "repairs/",
    "automation/",
    "script/",
    "scene/",
    "hassio/",
    "cloud/",
)

MUTATING_WS_TYPES = {
    "config/entity_registry/update",
    "config/entity_registry/remove",
    "config/device_registry/update",
    "config/device_registry/remove",
    "config/area_registry/create",
    "config/area_registry/update",
    "config/area_registry/delete",
    "lovelace/config/save",
}


class HaMessageFilter:
    def __init__(self, policy: PolicyEngine) -> None:
        self.policy = policy

    def validate_client_message(self, grant: Grant, message: dict[str, Any]) -> None:
        message_type = str(message.get("type") or "")
        if grant.role != GrantRole.ADMIN and (
            message_type in BLOCKED_GUEST_WS_TYPES
            or message_type.startswith(BLOCKED_GUEST_WS_PREFIXES)
        ):
            raise PermissionDenied(f"{message_type} is not allowed for scoped grants")
        if message_type == "call_service":
            self.policy.assert_service_allowed(grant, message)
            return
        if message_type in MUTATING_WS_TYPES:
            raise PermissionDenied(f"{message_type} is not allowed for scoped grants")
        if message_type in {"camera/stream", "media_player/browse_media"}:
            entity_id = message.get("entity_id") or (message.get("media_content_id") if message_type == "media_player/browse_media" else None)
            if entity_id and not self.policy.is_entity_allowed(grant, str(entity_id)):
                raise PermissionDenied("entity is not authorized")

    def filter_server_message(self, grant: Grant, message: dict[str, Any]) -> dict[str, Any] | None:
        copied = deepcopy(message)
        message_type = str(copied.get("type") or "")
        if message_type == "event":
            return self._filter_event(grant, copied)
        if message_type == "result":
            return self._filter_result(grant, copied)
        return copied

    def filter_rest_response(self, grant: Grant, path: str, payload: Any) -> Any:
        if not isinstance(payload, list):
            return payload
        if path == "states" or path.startswith("states/"):
            return self.policy.filter_states(grant, payload)
        if "entity_registry" in path:
            return self.policy.filter_entity_registry(grant, payload)
        if "device_registry" in path:
            return self.policy.filter_device_registry(grant, payload)
        if "area_registry" in path:
            return self.policy.filter_area_registry(grant, payload)
        if path.startswith("history/period"):
            return [
                entity_history
                for entity_history in payload
                if entity_history
                and isinstance(entity_history, list)
                and self.policy.is_entity_allowed(grant, str(entity_history[0].get("entity_id")))
            ]
        return payload

    def _filter_event(self, grant: Grant, message: dict[str, Any]) -> dict[str, Any] | None:
        event = message.get("event")
        if not isinstance(event, dict):
            return message
        data = event.get("data")
        if not isinstance(data, dict):
            return message
        entity_id = data.get("entity_id")
        if entity_id and not self.policy.is_entity_allowed(grant, str(entity_id)):
            return None
        for key in ("new_state", "old_state"):
            state = data.get(key)
            if isinstance(state, dict):
                state_entity_id = state.get("entity_id")
                if state_entity_id and not self.policy.is_entity_allowed(grant, str(state_entity_id)):
                    return None
        return message

    def _filter_result(self, grant: Grant, message: dict[str, Any]) -> dict[str, Any]:
        result = message.get("result")
        if not isinstance(result, list):
            return message
        command_type = str(message.get("ha_command_type") or "")
        if result and isinstance(result[0], dict) and "entity_id" in result[0]:
            message["result"] = self.policy.filter_states(grant, result)
        elif "entity_registry" in command_type:
            message["result"] = self.policy.filter_entity_registry(grant, result)
        elif "device_registry" in command_type:
            message["result"] = self.policy.filter_device_registry(grant, result)
        elif "area_registry" in command_type:
            message["result"] = self.policy.filter_area_registry(grant, result)
        return message

    def service_payload_from_rest(
        self,
        *,
        domain: str,
        service: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        message = {
            "type": "call_service",
            "domain": domain,
            "service": service,
        }
        if "target" in payload:
            message["target"] = payload["target"]
        if "service_data" in payload:
            message["service_data"] = payload["service_data"]
        else:
            message["service_data"] = {
                key: value
                for key, value in payload.items()
                if key != "target"
            }
        return message
