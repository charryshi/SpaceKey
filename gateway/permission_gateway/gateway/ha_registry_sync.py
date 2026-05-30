from __future__ import annotations

import json
from typing import Any

from .config import Settings
from .models import DeviceRecord, EntityRecord, HaAreaRecord, HaRegistrySnapshot


class RegistrySyncError(RuntimeError):
    pass


def build_snapshot_from_registries(
    *,
    areas: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    entities: list[dict[str, Any]],
) -> HaRegistrySnapshot:
    return HaRegistrySnapshot(
        areas={
            area.id: area
            for area in (_area_record(item) for item in areas)
            if area.id
        },
        devices={
            device.id: device
            for device in (_device_record(item) for item in devices)
            if device.id
        },
        entities={
            entity.entity_id: entity
            for entity in (_entity_record(item) for item in entities)
            if entity.entity_id
        },
    )


async def sync_ha_registry(settings: Settings) -> HaRegistrySnapshot:
    if not settings.home_assistant_token:
        raise RegistrySyncError("HOME_ASSISTANT_TOKEN is not configured")
    try:
        import websockets
    except ImportError as exc:
        raise RegistrySyncError("websockets dependency is not installed") from exc

    upstream_url = settings.home_assistant_url.replace("http://", "ws://").replace("https://", "wss://")
    upstream_url = f"{upstream_url}/api/websocket"
    try:
        async with websockets.connect(upstream_url, open_timeout=10) as websocket:
            await websocket.recv()
            await websocket.send(json.dumps({"type": "auth", "access_token": settings.home_assistant_token}))
            auth_response = json.loads(await websocket.recv())
            if auth_response.get("type") != "auth_ok":
                raise RegistrySyncError("Home Assistant rejected gateway token")
            areas = await _ha_command(websocket, 1, "config/area_registry/list")
            devices = await _ha_command(websocket, 2, "config/device_registry/list")
            entities = await _ha_command(websocket, 3, "config/entity_registry/list")
    except RegistrySyncError:
        raise
    except Exception as exc:
        raise RegistrySyncError(f"Home Assistant registry sync failed: {exc}") from exc
    return build_snapshot_from_registries(areas=areas, devices=devices, entities=entities)


async def _ha_command(websocket: Any, command_id: int, command_type: str) -> list[dict[str, Any]]:
    await websocket.send(json.dumps({"id": command_id, "type": command_type}))
    while True:
        message = json.loads(await websocket.recv())
        if message.get("id") != command_id:
            continue
        if not message.get("success", False):
            error = message.get("error") or {}
            raise RegistrySyncError(f"{command_type} failed: {error}")
        result = message.get("result") or []
        if not isinstance(result, list):
            raise RegistrySyncError(f"{command_type} returned unexpected payload")
        return result


def _area_record(item: dict[str, Any]) -> HaAreaRecord:
    area_id = item.get("area_id") or item.get("id")
    return HaAreaRecord(id=str(area_id or ""), name=item.get("name"))


def _device_record(item: dict[str, Any]) -> DeviceRecord:
    device_id = item.get("id") or item.get("device_id")
    name = item.get("name_by_user") or item.get("name") or item.get("original_name")
    return DeviceRecord(id=str(device_id or ""), area_id=item.get("area_id"), name=name)


def _entity_record(item: dict[str, Any]) -> EntityRecord:
    name = item.get("name") or item.get("name_by_user") or item.get("original_name")
    return EntityRecord(
        entity_id=str(item.get("entity_id") or ""),
        device_id=item.get("device_id"),
        area_id=item.get("area_id"),
        platform=item.get("platform"),
        name=name,
        entity_category=item.get("entity_category"),
        disabled_by=item.get("disabled_by"),
        hidden_by=item.get("hidden_by"),
    )
