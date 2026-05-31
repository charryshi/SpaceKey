import type {
  Auth,
  HassEntities,
  HassServiceTarget,
} from "home-assistant-js-websocket";
import { computeDomain } from "../common/entity/compute_domain";
import { supportsFeature } from "../common/entity/supports-feature";
import type {
  LocalizeFunc,
  LocalizeKeys,
} from "../common/translations/localize";
import type { CurrentUser, Panels } from "../types";
import type { AreaRegistryEntry } from "./area/area_registry";
import { CoverEntityFeature, type CoverEntity } from "./cover";
import type { DeviceRegistryEntry } from "./device/device_registry";
import type { EntityRegistryDisplayEntryResponse } from "./entity/entity_registry";
import type { FloorRegistryEntry } from "./floor_registry";
import { ClimateEntityFeature } from "./climate";
import { FanEntityFeature } from "./fan";
import { lightSupportsBrightness, type LightEntity } from "./light";
import type { LovelaceCardConfig } from "./lovelace/config/card";
import type { LovelaceSectionConfig } from "./lovelace/config/section";
import { isStrategySection } from "./lovelace/config/section";
import type {
  LovelaceConfig,
  LovelaceRawConfig,
} from "./lovelace/config/types";
import type { LovelaceViewConfig } from "./lovelace/config/view";
import { isStrategyView } from "./lovelace/config/view";
import { ValveEntityFeature, type ValveEntity } from "./valve";
import { WaterHeaterEntityFeature } from "./water_heater";
import { fetchWithAuth } from "../util/fetch-with-auth";
import { handleFetchPromise } from "../util/hass-call-api";
import { isChineseLanguage } from "./panel";

export const PERMISSION_GATEWAY_DEVICE_PUBLIC_KEY_STORAGE_KEY =
  "permission_gateway_device_public_key";
export const PERMISSION_GATEWAY_SUMMARY_STORAGE_KEY =
  "permission_gateway_summary";
export const PERMISSION_GATEWAY_CLIENT_ID = "permission-gateway-web";
export const PERMISSION_GATEWAY_TOKENS_STORAGE_KEY =
  "permission_gateway_tokens";
const PERMISSION_GATEWAY_EXTERNAL_AUTH_SESSION_STORAGE_KEY =
  "permission_gateway_external_auth_session";

interface PermissionGatewayNamedRef {
  name?: string;
  display_name?: string;
  title?: string;
}

export interface PermissionGatewaySummary {
  role: "admin" | "guest" | string;
  can_read: boolean;
  can_control: boolean;
  ha_area_ids?: string[];
  area_ids?: string[];
  allowed_area_ids?: string[];
  device_ids?: string[];
  allowed_device_ids?: string[];
  entity_ids?: string[];
  allowed_entity_ids?: string[];
  grant_id?: string;
  template_id?: string;
  name?: string;
  display_name?: string;
  grant_name?: string;
  template_name?: string;
  permission_template_name?: string;
  qr_template_name?: string;
  scope_name?: string;
  qr_name?: string;
  template?: PermissionGatewayNamedRef;
  permission_template?: PermissionGatewayNamedRef;
  qr_template?: PermissionGatewayNamedRef;
  grant?: PermissionGatewayNamedRef;
}

const getStringList = (
  summary: PermissionGatewaySummary,
  keys: (keyof PermissionGatewaySummary)[]
) => {
  for (const key of keys) {
    const value = summary[key];
    if (Array.isArray(value)) {
      return value.filter((item): item is string => typeof item === "string");
    }
  }
  return [];
};

export const getPermissionGatewayEntityIds = (
  summary: PermissionGatewaySummary
) => getStringList(summary, ["entity_ids", "allowed_entity_ids"]);

export const getPermissionGatewayDeviceIds = (
  summary: PermissionGatewaySummary
) => getStringList(summary, ["device_ids", "allowed_device_ids"]);

export const getPermissionGatewayAreaIds = (
  summary: PermissionGatewaySummary
) => getStringList(summary, ["ha_area_ids", "area_ids", "allowed_area_ids"]);

export const getPermissionGatewayDevicePublicKey = () => {
  try {
    return localStorage.getItem(
      PERMISSION_GATEWAY_DEVICE_PUBLIC_KEY_STORAGE_KEY
    );
  } catch (_err: any) {
    return undefined;
  }
};

export const savePermissionGatewayDevicePublicKey = (
  devicePublicKey: string | null | undefined
) => {
  try {
    if (devicePublicKey) {
      localStorage.setItem(
        PERMISSION_GATEWAY_DEVICE_PUBLIC_KEY_STORAGE_KEY,
        devicePublicKey
      );
    } else {
      localStorage.removeItem(PERMISSION_GATEWAY_DEVICE_PUBLIC_KEY_STORAGE_KEY);
    }
  } catch (_err: any) {
    // Ignore storage errors; the gateway still validates the access token.
  }
};

export const fetchPermissionGatewaySummary = async (
  auth: Auth
): Promise<PermissionGatewaySummary | undefined> => {
  if (!isPermissionGatewaySession(auth)) {
    return undefined;
  }
  try {
    const summary = await handleFetchPromise<PermissionGatewaySummary>(
      fetchWithAuth(
        auth,
        new URL("/v1/me/permissions", auth.data.hassUrl).toString()
      )
    );
    savePermissionGatewaySummary(summary);
    return summary;
  } catch (_err: any) {
    const cachedSummary = loadCachedPermissionGatewaySummary();
    return cachedSummary?.role === "admin" ? undefined : cachedSummary;
  }
};

export const savePermissionGatewaySummary = (
  summary: PermissionGatewaySummary | null | undefined
) => {
  try {
    if (summary) {
      localStorage.setItem(
        PERMISSION_GATEWAY_SUMMARY_STORAGE_KEY,
        JSON.stringify(summary)
      );
    } else {
      localStorage.removeItem(PERMISSION_GATEWAY_SUMMARY_STORAGE_KEY);
    }
  } catch (_err: any) {
    // Ignore storage errors; the authoritative summary still comes from gateway.
  }
};

export const loadCachedPermissionGatewaySummary = ():
  | PermissionGatewaySummary
  | undefined => {
  try {
    const raw = localStorage.getItem(PERMISSION_GATEWAY_SUMMARY_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as PermissionGatewaySummary) : undefined;
  } catch (_err: any) {
    return undefined;
  }
};

export const isPermissionGatewayAdmin = (
  summary: PermissionGatewaySummary | null | undefined
) => !summary || summary.role === "admin";

export const isPermissionGatewaySession = (auth: Auth | undefined) =>
  auth?.data.clientId === PERMISSION_GATEWAY_CLIENT_ID ||
  isStoredPermissionGatewaySession(auth) ||
  isPermissionGatewayExternalAuthSession();

const isStoredPermissionGatewaySession = (auth: Auth | undefined) => {
  if (!auth) {
    return false;
  }
  try {
    const raw = localStorage.getItem(PERMISSION_GATEWAY_TOKENS_STORAGE_KEY);
    if (!raw) {
      return false;
    }
    const stored = JSON.parse(raw) as Partial<Auth["data"]>;
    return (
      typeof stored.refresh_token === "string" &&
      stored.refresh_token === auth.data.refresh_token &&
      (!stored.hassUrl || stored.hassUrl === auth.data.hassUrl)
    );
  } catch (_err: any) {
    return false;
  }
};

export const markPermissionGatewayExternalAuthSession = () => {
  try {
    sessionStorage.setItem(
      PERMISSION_GATEWAY_EXTERNAL_AUTH_SESSION_STORAGE_KEY,
      "1"
    );
  } catch (_err: any) {
    // Ignore storage errors. The URL marker still covers initial load.
  }
};

export const isPermissionGatewayExternalAuthSession = () =>
  location.search.includes("external_auth=1") ||
  (() => {
    try {
      return (
        sessionStorage.getItem(
          PERMISSION_GATEWAY_EXTERNAL_AUTH_SESSION_STORAGE_KEY
        ) === "1"
      );
    } catch (_err: any) {
      return false;
    }
  })();

export const shouldRestrictPermissionGateway = (
  summary: PermissionGatewaySummary | null | undefined,
  auth?: Auth
) => {
  if (summary) {
    return summary.role !== "admin";
  }
  return isPermissionGatewaySession(auth);
};

export const getPermissionGatewayDisplayName = (
  summary: PermissionGatewaySummary | null | undefined
) =>
  summary?.display_name ||
  summary?.template_name ||
  summary?.permission_template_name ||
  summary?.qr_template_name ||
  summary?.template?.display_name ||
  summary?.template?.name ||
  summary?.template?.title ||
  summary?.permission_template?.display_name ||
  summary?.permission_template?.name ||
  summary?.permission_template?.title ||
  summary?.qr_template?.display_name ||
  summary?.qr_template?.name ||
  summary?.qr_template?.title ||
  summary?.grant?.display_name ||
  summary?.grant?.name ||
  summary?.scope_name ||
  summary?.qr_name ||
  summary?.grant_name ||
  summary?.name ||
  summary?.template_id ||
  summary?.grant_id ||
  "未命名权限模板";

export const applyPermissionGatewayUser = (
  user: CurrentUser,
  summary: PermissionGatewaySummary | null | undefined,
  auth?: Auth
): CurrentUser => {
  const cachedSummary = isPermissionGatewaySession(auth)
    ? loadCachedPermissionGatewaySummary()
    : undefined;
  const effectiveSummary =
    summary || (cachedSummary?.role === "admin" ? undefined : cachedSummary);
  if (!shouldRestrictPermissionGateway(effectiveSummary, auth)) {
    return user;
  }
  return {
    ...user,
    id: effectiveSummary?.grant_id || user.id,
    is_admin: false,
    is_owner: false,
    name: getPermissionGatewayDisplayName(effectiveSummary),
    credentials: [],
    mfa_modules: [],
  };
};

export const hasStoredPermissionGatewayTokens = (hassUrl?: string) => {
  try {
    const raw = localStorage.getItem(PERMISSION_GATEWAY_TOKENS_STORAGE_KEY);
    if (!raw) {
      return false;
    }
    const stored = JSON.parse(raw) as Partial<Auth["data"]>;
    return Boolean(
      stored.refresh_token &&
      (!hassUrl || !stored.hassUrl || stored.hassUrl === hassUrl)
    );
  } catch (_err: any) {
    return false;
  }
};

const BLOCKED_NON_ADMIN_PANELS = new Set([
  "config",
  "developer-tools",
  "hassio",
]);

export const filterPanelsByPermission = (
  panels: Panels,
  summary: PermissionGatewaySummary | null | undefined,
  auth?: Auth
): Panels => {
  if (!shouldRestrictPermissionGateway(summary, auth)) {
    return panels;
  }
  const filtered: Panels = {};
  for (const [key, panel] of Object.entries(panels)) {
    if (
      BLOCKED_NON_ADMIN_PANELS.has(panel.url_path) ||
      panel.require_admin ||
      panel.component_name === "config"
    ) {
      continue;
    }
    filtered[key] = panel;
  }
  return filtered;
};

const BLOCKED_NON_ADMIN_WS_TYPES = new Set([
  "auth/refresh_tokens",
  "auth/delete_refresh_token",
  "auth/delete_all_refresh_tokens",
  "auth/refresh_token_set_expiry",
  "auth/long_lived_access_token",
  "frontend/update_panel",
  "frontend/remove_panel",
  "frontend/create_panel",
  "lovelace/config/save",
  "lovelace/resources",
]);

const BLOCKED_NON_ADMIN_WS_PREFIXES = [
  "config/",
  "config_entries/",
  "device_registry/",
  "entity_registry/",
  "area_registry/",
  "floor_registry/",
  "repairs/",
  "person/",
  "zone/",
  "automation/",
  "script/",
  "scene/",
  "hassio/",
  "cloud/",
  "application_credentials/",
];

export const isPermissionGatewayWSMessageAllowed = (
  msg: { type?: string },
  summary: PermissionGatewaySummary | null | undefined,
  auth?: Auth
) => {
  if (!shouldRestrictPermissionGateway(summary, auth)) {
    return true;
  }
  const type = msg.type;
  if (!type) {
    return false;
  }
  return (
    !BLOCKED_NON_ADMIN_WS_TYPES.has(type) &&
    !BLOCKED_NON_ADMIN_WS_PREFIXES.some((prefix) => type.startsWith(prefix))
  );
};

const SERVICE_TARGET_KEYS = ["entity_id", "device_id", "area_id"] as const;

const hasTargetValue = (value: unknown) =>
  Array.isArray(value)
    ? value.some(hasTargetValue)
    : typeof value === "string"
      ? value.trim() !== "" && value !== "all"
      : Boolean(value);

const hasAllTargetValue = (value: unknown) =>
  value === "all" ||
  (Array.isArray(value) && value.some((item) => item === "all"));

const hasExplicitServiceTarget = (
  value: Record<string, any> | null | undefined
) =>
  Boolean(
    value && SERVICE_TARGET_KEYS.some((key) => hasTargetValue(value[key]))
  );

const hasGlobalServiceTarget = (
  value: Record<string, any> | null | undefined
) =>
  Boolean(
    value &&
    ((value as { all?: boolean }).all === true ||
      SERVICE_TARGET_KEYS.some((key) => hasAllTargetValue(value[key])))
  );

export const getPermissionGatewayServiceCallDeniedReason = (
  _domain: string,
  _service: string,
  serviceData: Record<string, any> | undefined,
  target: HassServiceTarget | undefined,
  summary: PermissionGatewaySummary | null | undefined,
  auth?: Auth
) => {
  if (!shouldRestrictPermissionGateway(summary, auth)) {
    return undefined;
  }
  if (summary && !summary.can_control) {
    return "Permission gateway grant cannot control devices";
  }
  const serviceDataTarget = serviceData?.target as
    | Record<string, any>
    | null
    | undefined;
  const targetRecord = target as Record<string, any> | undefined;

  if (
    hasGlobalServiceTarget(targetRecord) ||
    hasGlobalServiceTarget(serviceData) ||
    hasGlobalServiceTarget(serviceDataTarget)
  ) {
    return "Permission gateway does not allow global service targets";
  }
  if (
    hasExplicitServiceTarget(targetRecord) ||
    hasExplicitServiceTarget(serviceData) ||
    hasExplicitServiceTarget(serviceDataTarget)
  ) {
    return undefined;
  }
  return "Permission gateway service calls must include entity_id, device_id, or area_id";
};

export const filterStatesByPermission = (
  states: HassEntities,
  summary: PermissionGatewaySummary | null | undefined
): HassEntities => {
  if (!summary || isPermissionGatewayAdmin(summary) || !states) {
    return states;
  }
  const entityIds = getPermissionGatewayEntityIds(summary);
  if (entityIds.length === 0) {
    return states;
  }
  const allowedEntityIds = new Set(entityIds);
  const filtered: HassEntities = {};
  for (const [entityId, stateObj] of Object.entries(states)) {
    if (isStateAllowedByPermission(stateObj, allowedEntityIds)) {
      filtered[entityId] = stateObj;
    }
  }
  return filtered;
};

const getStateMemberEntityIds = (stateObj: HassEntities[string]) =>
  Array.isArray(stateObj.attributes?.entity_id)
    ? stateObj.attributes.entity_id.filter(
        (entityId): entityId is string => typeof entityId === "string"
      )
    : [];

const isStateAllowedByPermission = (
  stateObj: HassEntities[string],
  allowedEntityIds: Set<string>
) => {
  if (allowedEntityIds.has(stateObj.entity_id)) {
    return true;
  }
  const memberEntityIds = getStateMemberEntityIds(stateObj);
  return (
    memberEntityIds.length > 0 &&
    memberEntityIds.every((entityId) => allowedEntityIds.has(entityId))
  );
};

export const filterEntityRegistryDisplayByPermission = (
  entityReg: EntityRegistryDisplayEntryResponse,
  summary: PermissionGatewaySummary | null | undefined
): EntityRegistryDisplayEntryResponse => {
  if (!summary || isPermissionGatewayAdmin(summary)) {
    return entityReg;
  }
  const entityIds = getPermissionGatewayEntityIds(summary);
  if (entityIds.length === 0) {
    return entityReg;
  }
  const allowedEntityIds = new Set(entityIds);
  return {
    ...entityReg,
    entities: entityReg.entities.filter((entity) =>
      allowedEntityIds.has(entity.ei)
    ),
  };
};

export const filterDeviceRegistryByPermission = (
  devices: DeviceRegistryEntry[],
  summary: PermissionGatewaySummary | null | undefined
) => {
  if (!summary || isPermissionGatewayAdmin(summary)) {
    return devices;
  }
  const deviceIds = getPermissionGatewayDeviceIds(summary);
  if (deviceIds.length === 0) {
    return devices;
  }
  const allowedDeviceIds = new Set(deviceIds);
  return devices.filter((device) => allowedDeviceIds.has(device.id));
};

export const filterAreaRegistryByPermission = (
  areas: AreaRegistryEntry[],
  summary: PermissionGatewaySummary | null | undefined
) => {
  if (!summary || isPermissionGatewayAdmin(summary)) {
    return areas;
  }
  const areaIds = getPermissionGatewayAreaIds(summary);
  if (areaIds.length === 0) {
    return areas;
  }
  const allowedAreaIds = new Set(areaIds);
  return areas.filter((area) => allowedAreaIds.has(area.area_id));
};

export const filterFloorRegistryByPermission = (
  floors: FloorRegistryEntry[],
  areas: Record<string, AreaRegistryEntry> | undefined,
  summary: PermissionGatewaySummary | null | undefined
) => {
  if (!summary || isPermissionGatewayAdmin(summary)) {
    return floors;
  }
  if (!areas) {
    return [];
  }
  const allowedFloorIds = new Set(
    Object.values(areas)
      .map((area) => area.floor_id)
      .filter((floorId): floorId is string => Boolean(floorId))
  );
  return floors.filter((floor) => allowedFloorIds.has(floor.floor_id));
};

export const filterRecordByPermission = <T>(
  records: Record<string, T>,
  allowedIds: string[],
  summary: PermissionGatewaySummary | null | undefined
): Record<string, T> => {
  if (!summary || isPermissionGatewayAdmin(summary) || !records) {
    return records;
  }
  if (allowedIds.length === 0) {
    return records;
  }
  const allowed = new Set(allowedIds);
  const filtered: Record<string, T> = {};
  for (const [id, value] of Object.entries(records)) {
    if (allowed.has(id)) {
      filtered[id] = value;
    }
  }
  return filtered;
};

interface PermissionGatewayCardFeatureConfig {
  type: string;
}

interface PermissionGatewayEntityGroup {
  key: string;
  title: string;
  icon: string;
  entityIds: string[];
}

const GROUP_ORDER = [
  "light",
  "cover",
  "climate",
  "fan",
  "switch",
  "humidifier",
  "valve",
  "media_player",
  "security",
  "actions",
  "sensor",
  "other",
];

const GROUP_META: Record<
  string,
  {
    title: string;
    zhTitle: string;
    icon: string;
    translationKeys?: LocalizeKeys[];
  }
> = {
  light: {
    title: "Lights",
    zhTitle: "灯",
    icon: "mdi:lamps",
    translationKeys: [
      "ui.panel.lovelace.strategy.areas.groups.lights",
      "panel.light",
    ],
  },
  cover: {
    title: "Covers",
    zhTitle: "窗帘",
    icon: "mdi:blinds-horizontal",
    translationKeys: [
      "ui.panel.lovelace.strategy.areas.groups.covers",
      "component.cover.title",
    ],
  },
  climate: {
    title: "Climate",
    zhTitle: "空调",
    icon: "mdi:home-thermometer",
    translationKeys: [
      "ui.panel.lovelace.strategy.areas.groups.climate",
      "panel.climate",
      "component.climate.title",
    ],
  },
  fan: {
    title: "Fans",
    zhTitle: "风扇",
    icon: "mdi:fan",
    translationKeys: ["component.fan.title"],
  },
  switch: {
    title: "Switches",
    zhTitle: "开关",
    icon: "mdi:toggle-switch",
    translationKeys: ["component.switch.title"],
  },
  humidifier: {
    title: "Humidifiers",
    zhTitle: "加湿器",
    icon: "mdi:air-humidifier",
    translationKeys: ["component.humidifier.title"],
  },
  valve: {
    title: "Valves",
    zhTitle: "阀门",
    icon: "mdi:valve",
    translationKeys: ["component.valve.title"],
  },
  media_player: {
    title: "Media players",
    zhTitle: "媒体播放器",
    icon: "mdi:multimedia",
    translationKeys: [
      "ui.panel.lovelace.strategy.areas.groups.media_players",
      "component.media_player.title",
    ],
  },
  security: {
    title: "Security",
    zhTitle: "安防",
    icon: "mdi:security",
    translationKeys: [
      "ui.panel.lovelace.strategy.areas.groups.security",
      "panel.security",
    ],
  },
  actions: {
    title: "Actions",
    zhTitle: "操作",
    icon: "mdi:robot",
    translationKeys: ["ui.panel.lovelace.strategy.areas.groups.actions"],
  },
  sensor: {
    title: "Sensors",
    zhTitle: "传感器",
    icon: "mdi:gauge",
    translationKeys: [
      "ui.panel.lovelace.strategy.areas.sensors",
      "component.sensor.title",
    ],
  },
  other: {
    title: "Others",
    zhTitle: "其他",
    icon: "mdi:shape",
    translationKeys: ["ui.panel.lovelace.strategy.areas.groups.others"],
  },
};

const ALARM_CONTROL_PANEL_ARM_HOME = 1;
const ALARM_CONTROL_PANEL_ARM_AWAY = 2;
const ALARM_CONTROL_PANEL_ARM_NIGHT = 4;

const getEntityGroupKey = (entityId: string) => {
  const domain = computeDomain(entityId);
  if (domain === "lock" || domain === "alarm_control_panel") {
    return "security";
  }
  if (domain === "scene" || domain === "script" || domain === "automation") {
    return "actions";
  }
  if (GROUP_ORDER.includes(domain)) {
    return domain;
  }
  return "other";
};

const getGroupTitle = (
  groupKey: string,
  localize: LocalizeFunc | undefined,
  language: string | undefined
) => {
  const meta = GROUP_META[groupKey] ?? GROUP_META.other;
  if (isChineseLanguage(language)) {
    return meta.zhTitle;
  }
  if (localize) {
    for (const translationKey of meta.translationKeys || []) {
      const translated = localize(translationKey);
      if (translated) {
        return translated;
      }
    }
  }
  return meta.title;
};

const createPermissionGatewayEntityGroups = (
  entityIds: string[],
  localize: LocalizeFunc | undefined,
  language: string | undefined
): PermissionGatewayEntityGroup[] => {
  const groups = new Map<string, string[]>();
  for (const entityId of entityIds) {
    const groupKey = getEntityGroupKey(entityId);
    if (!groups.has(groupKey)) {
      groups.set(groupKey, []);
    }
    groups.get(groupKey)!.push(entityId);
  }

  return GROUP_ORDER.filter((groupKey) => groups.has(groupKey)).map(
    (groupKey) => {
      const meta = GROUP_META[groupKey] ?? GROUP_META.other;
      return {
        key: groupKey,
        title: getGroupTitle(groupKey, localize, language),
        icon: meta.icon,
        entityIds: groups.get(groupKey)!,
      };
    }
  );
};

const createPermissionGatewayTileFeatures = (
  stateObj: HassEntities[string]
): PermissionGatewayCardFeatureConfig[] => {
  const domain = computeDomain(stateObj.entity_id);
  switch (domain) {
    case "light": {
      const light = stateObj as LightEntity;
      const features: PermissionGatewayCardFeatureConfig[] = [];
      if (lightSupportsBrightness(light)) {
        features.push({ type: "light-brightness" });
      }
      return features;
    }
    case "cover": {
      const cover = stateObj as CoverEntity;
      const features: PermissionGatewayCardFeatureConfig[] = [];
      if (
        supportsFeature(cover, CoverEntityFeature.OPEN) ||
        supportsFeature(cover, CoverEntityFeature.CLOSE)
      ) {
        features.push({ type: "cover-open-close" });
      }
      return features;
    }
    case "climate":
      return supportsFeature(
        stateObj,
        ClimateEntityFeature.TARGET_TEMPERATURE
      ) ||
        supportsFeature(stateObj, ClimateEntityFeature.TARGET_TEMPERATURE_RANGE)
        ? [{ type: "target-temperature" }]
        : [];
    case "water_heater":
      return supportsFeature(
        stateObj,
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
      )
        ? [{ type: "target-temperature" }]
        : [];
    case "fan":
      return supportsFeature(stateObj, FanEntityFeature.SET_SPEED)
        ? [{ type: "fan-speed" }]
        : [];
    case "lock":
      return [{ type: "lock-commands" }];
    case "alarm_control_panel":
      return supportsFeature(stateObj, ALARM_CONTROL_PANEL_ARM_HOME) ||
        supportsFeature(stateObj, ALARM_CONTROL_PANEL_ARM_AWAY) ||
        supportsFeature(stateObj, ALARM_CONTROL_PANEL_ARM_NIGHT)
        ? [{ type: "alarm-modes" }]
        : [];
    case "humidifier":
      return [{ type: "humidifier-toggle" }];
    case "valve": {
      const valve = stateObj as ValveEntity;
      const features: PermissionGatewayCardFeatureConfig[] = [];
      if (
        supportsFeature(valve, ValveEntityFeature.OPEN) ||
        supportsFeature(valve, ValveEntityFeature.CLOSE)
      ) {
        features.push({ type: "valve-open-close" });
      }
      return features;
    }
    case "media_player":
      return [{ type: "media-player-playback" }];
    default:
      return [];
  }
};

const createPermissionGatewayEntityCard = (
  stateObj: HassEntities[string]
): LovelaceCardConfig => {
  const domain = computeDomain(stateObj.entity_id);
  if (domain === "camera") {
    return {
      type: "picture-entity",
      entity: stateObj.entity_id,
      show_state: false,
      tap_action: {
        action: "more-info",
      },
      hold_action: {
        action: "more-info",
      },
      grid_options: {
        columns: 6,
        rows: 2,
      },
    };
  }

  const features = createPermissionGatewayTileFeatures(stateObj);
  const card: LovelaceCardConfig = {
    type: "tile",
    entity: stateObj.entity_id,
    tap_action: {
      action: "more-info",
    },
    hold_action: {
      action: "more-info",
    },
    icon_hold_action: {
      action: "more-info",
    },
    grid_options: {
      columns: 6,
      rows: 1 + features.length,
    },
  };
  if (features.length > 0) {
    card.features = features;
  }
  return card;
};

interface PermissionGatewayGroupControl {
  domain: string;
  activeStates: string[];
  turnOnService: string;
  turnOffService: string;
  turnOnText: string;
  turnOffText: string;
  activeColor?: string;
}

const getPermissionGatewayGroupControl = (
  groupKey: string,
  localize: LocalizeFunc | undefined,
  language: string | undefined
): PermissionGatewayGroupControl | undefined => {
  const allOnText = getPermissionGatewayControlLabel(
    "ui.card.toggle-group.all_on",
    language,
    "全开",
    "All on",
    localize
  );
  const allOffText = getPermissionGatewayControlLabel(
    "ui.card.toggle-group.all_off",
    language,
    "全关",
    "All off",
    localize
  );

  switch (groupKey) {
    case "light":
      return {
        domain: "light",
        activeStates: ["on"],
        turnOnService: "turn_on",
        turnOffService: "turn_off",
        turnOnText: allOnText,
        turnOffText: allOffText,
        activeColor: "orange",
      };
    default:
      return undefined;
  }
};

const getPermissionGatewayControlLabel = (
  key: LocalizeKeys,
  language: string | undefined,
  zhFallback: string,
  fallback: string,
  localize: LocalizeFunc | undefined
) => {
  if (isChineseLanguage(language)) {
    return zhFallback;
  }
  const translated = localize?.(key);
  return translated && translated !== key ? translated : fallback;
};

const createPermissionGatewayGroupControlBadges = (
  group: PermissionGatewayEntityGroup,
  localize: LocalizeFunc | undefined,
  language: string | undefined
) => {
  if (group.entityIds.length < 2) {
    return undefined;
  }
  const control = getPermissionGatewayGroupControl(
    group.key,
    localize,
    language
  );
  if (!control) {
    return undefined;
  }

  const anyActiveCondition = {
    condition: "or" as const,
    conditions: group.entityIds.map((entityId) => ({
      condition: "state" as const,
      entity: entityId,
      state: control.activeStates,
    })),
  };

  return [
    {
      type: "button",
      icon: "mdi:power",
      text: control.turnOnText,
      tap_action: {
        action: "perform-action",
        perform_action: `${control.domain}.${control.turnOnService}`,
        target: {
          entity_id: group.entityIds,
        },
      },
      visibility: [
        {
          condition: "not",
          conditions: [anyActiveCondition],
        },
      ],
    },
    {
      type: "button",
      icon: "mdi:power",
      color: control.activeColor,
      text: control.turnOffText,
      tap_action: {
        action: "perform-action",
        perform_action: `${control.domain}.${control.turnOffService}`,
        target: {
          entity_id: group.entityIds,
        },
      },
      visibility: [anyActiveCondition],
    },
  ];
};

const createPermissionGatewayGroupCards = (
  group: PermissionGatewayEntityGroup,
  states: HassEntities,
  localize: LocalizeFunc | undefined,
  language: string | undefined
): LovelaceCardConfig[] => {
  const cards: LovelaceCardConfig[] = [
    {
      type: "heading",
      heading: group.title,
      icon: group.icon,
      badges: createPermissionGatewayGroupControlBadges(
        group,
        localize,
        language
      ),
    },
  ];

  cards.push(
    ...group.entityIds.map((entityId) =>
      createPermissionGatewayEntityCard(states[entityId])
    )
  );

  return cards;
};

export const createPermissionGatewayLovelaceConfig = (
  states: HassEntities | null | undefined,
  summary: PermissionGatewaySummary | null | undefined,
  localize?: LocalizeFunc,
  language?: string
): LovelaceConfig | undefined => {
  if (!summary || isPermissionGatewayAdmin(summary) || !states) {
    return undefined;
  }
  const filteredStates = filterStatesByPermission(states, summary);
  const entityIds = Object.keys(filteredStates).sort();
  const groups = createPermissionGatewayEntityGroups(
    entityIds,
    localize,
    language
  );
  return {
    views: [
      {
        title: getPermissionGatewayDisplayName(summary),
        path: "overview",
        icon: "mdi:home",
        type: "sections",
        sections: groups.map((group) => ({
          type: "grid",
          cards: createPermissionGatewayGroupCards(
            group,
            filteredStates,
            localize,
            language
          ),
        })),
      },
    ],
  };
};

export const createPermissionGatewayFallbackLovelaceConfig = (
  summary: PermissionGatewaySummary | null | undefined
): LovelaceConfig => ({
  views: [
    {
      title: getPermissionGatewayDisplayName(summary),
      path: "overview",
      icon: "mdi:home",
      type: "sections",
      sections: [
        {
          type: "grid",
          cards: [],
        },
      ],
    },
  ],
});

export const filterLovelaceConfigByPermission = <T extends LovelaceRawConfig>(
  config: T,
  summary: PermissionGatewaySummary | null | undefined
): T => {
  if (!summary || isPermissionGatewayAdmin(summary) || "strategy" in config) {
    return config;
  }
  const filtered = cloneConfig(config) as LovelaceConfig;
  filtered.views = filtered.views.map((view) => {
    if (isStrategyView(view)) {
      return view;
    }
    const viewConfig = view as LovelaceViewConfig;
    return {
      ...viewConfig,
      badges: filterEntityReferenceArray(viewConfig.badges, summary),
      cards: filterArrayByPermission(viewConfig.cards, summary),
      sections: viewConfig.sections?.map((section) => {
        if (isStrategySection(section)) {
          return section;
        }
        const sectionConfig = section as LovelaceSectionConfig;
        return {
          ...sectionConfig,
          cards: filterArrayByPermission(sectionConfig.cards, summary),
        };
      }),
    };
  });
  return filtered as T;
};

const cloneConfig = <T>(config: T): T => JSON.parse(JSON.stringify(config));

const filterArrayByPermission = <T>(
  items: T[] | undefined,
  summary: PermissionGatewaySummary
): T[] | undefined => {
  if (!items) {
    return items;
  }
  return items
    .map((item) => filterConfigNode(item, summary))
    .filter((item): item is T => item !== undefined);
};

const filterConfigNode = <T>(node: T, summary: PermissionGatewaySummary) => {
  if (!isNodeAllowed(node, summary)) {
    return undefined;
  }
  if (!node || typeof node !== "object") {
    return node;
  }
  const mutableNode = node as Record<string, any>;
  for (const [key, value] of Object.entries(mutableNode)) {
    if (Array.isArray(value)) {
      const filtered =
        key === "entities"
          ? filterEntityReferenceArray(value, summary) || []
          : value
              .map((item) => filterConfigNode(item, summary))
              .filter((item) => item !== undefined);
      if (key === "entities" && filtered.length === 0) {
        return undefined;
      }
      mutableNode[key] = filtered;
    } else if (value && typeof value === "object") {
      const filtered = filterConfigNode(value, summary);
      if (filtered === undefined) {
        delete mutableNode[key];
      } else {
        mutableNode[key] = filtered;
      }
    }
  }
  return node;
};

const filterEntityReferenceArray = (
  items: any[] | undefined,
  summary: PermissionGatewaySummary
) => {
  if (!items) {
    return items;
  }
  const entityIds = getPermissionGatewayEntityIds(summary);
  if (entityIds.length === 0) {
    return items;
  }
  const allowedEntityIds = new Set(entityIds);
  return items
    .map((item) => {
      if (typeof item === "string") {
        return allowedEntityIds.has(item) ? item : undefined;
      }
      return filterConfigNode(item, summary);
    })
    .filter((item) => item !== undefined);
};

const isNodeAllowed = (
  node: any,
  summary: PermissionGatewaySummary
): boolean => {
  if (!node || typeof node !== "object") {
    return true;
  }
  const entityIds = getPermissionGatewayEntityIds(summary);
  const deviceIds = getPermissionGatewayDeviceIds(summary);
  const areaIds = getPermissionGatewayAreaIds(summary);
  const allowedEntityIds = new Set(entityIds);
  const allowedDeviceIds = new Set(deviceIds);
  const allowedAreaIds = new Set(areaIds);

  if (
    entityIds.length > 0 &&
    typeof node.entity === "string" &&
    !allowedEntityIds.has(node.entity)
  ) {
    return false;
  }
  if (
    entityIds.length > 0 &&
    typeof node.entity_id === "string" &&
    !allowedEntityIds.has(node.entity_id)
  ) {
    return false;
  }
  if (
    entityIds.length > 0 &&
    Array.isArray(node.entity_id) &&
    !node.entity_id.every((entityId) => allowedEntityIds.has(entityId))
  ) {
    return false;
  }
  if (
    deviceIds.length > 0 &&
    typeof node.device_id === "string" &&
    !allowedDeviceIds.has(node.device_id)
  ) {
    return false;
  }
  if (
    deviceIds.length > 0 &&
    Array.isArray(node.device_id) &&
    !node.device_id.every((deviceId) => allowedDeviceIds.has(deviceId))
  ) {
    return false;
  }
  if (
    areaIds.length > 0 &&
    typeof node.area_id === "string" &&
    !allowedAreaIds.has(node.area_id)
  ) {
    return false;
  }
  if (
    areaIds.length > 0 &&
    Array.isArray(node.area_id) &&
    !node.area_id.every((areaId) => allowedAreaIds.has(areaId))
  ) {
    return false;
  }
  return true;
};
