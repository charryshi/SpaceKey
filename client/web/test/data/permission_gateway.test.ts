import { beforeEach, describe, expect, it } from "vitest";
import {
  applyPermissionGatewayUser,
  createPermissionGatewayLovelaceConfig,
  filterAreaRegistryByPermission,
  filterDeviceRegistryByPermission,
  filterEntityRegistryDisplayByPermission,
  filterFloorRegistryByPermission,
  filterLovelaceConfigByPermission,
  filterPanelsByPermission,
  filterStatesByPermission,
  getPermissionGatewayDevicePublicKey,
  getPermissionGatewayDisplayName,
  getPermissionGatewayServiceCallDeniedReason,
  isPermissionGatewaySession,
  isPermissionGatewayWSMessageAllowed,
  PERMISSION_GATEWAY_TOKENS_STORAGE_KEY,
  savePermissionGatewayDevicePublicKey,
  savePermissionGatewaySummary,
  shouldRestrictPermissionGateway,
  type PermissionGatewaySummary,
} from "../../src/data/permission_gateway";
import { parsePermissionGatewayQrId } from "../../src/data/permission_gateway_qr";
import { localizePanelTitle } from "../../src/data/panel";

const summary: PermissionGatewaySummary = {
  role: "guest",
  can_read: true,
  can_control: true,
  ha_area_ids: ["kitchen"],
  device_ids: ["device-kettle"],
  entity_ids: ["switch.kettle", "sensor.kitchen_temp"],
};

const translations: Record<string, string> = {
  "ui.panel.lovelace.strategy.areas.groups.lights": "Lights",
  "ui.panel.lovelace.strategy.areas.groups.covers": "Covers",
  "ui.panel.lovelace.strategy.areas.groups.climate": "Climate",
  "ui.panel.lovelace.strategy.areas.groups.media_players": "Media players",
  "ui.panel.lovelace.strategy.areas.groups.security": "Security",
  "ui.panel.lovelace.strategy.areas.groups.actions": "Actions",
  "ui.panel.lovelace.strategy.areas.sensors": "Sensors",
  "ui.panel.lovelace.strategy.areas.groups.others": "Others",
  "component.cover.title": "Covers",
  "ui.card.toggle-group.all_on": "All on",
  "ui.card.toggle-group.all_off": "All off",
};

const localize = (key: string) => translations[key] || key;

describe("permission gateway frontend filters", () => {
  beforeEach(() => {
    savePermissionGatewaySummary(null);
    savePermissionGatewayDevicePublicKey(null);
    localStorage.removeItem(PERMISSION_GATEWAY_TOKENS_STORAGE_KEY);
    sessionStorage.clear();
    history.replaceState(null, "", "/");
  });

  it("filters states by authorized entities", () => {
    expect(
      Object.keys(
        filterStatesByPermission(
          {
            "switch.kettle": { entity_id: "switch.kettle" } as any,
            "light.bathroom_group": {
              entity_id: "light.bathroom_group",
              attributes: {
                entity_id: ["switch.kettle"],
              },
            } as any,
            "light.mixed_group": {
              entity_id: "light.mixed_group",
              attributes: {
                entity_id: ["switch.kettle", "light.bedroom"],
              },
            } as any,
            "light.bedroom": { entity_id: "light.bedroom" } as any,
          },
          summary
        )
      )
    ).toEqual(["switch.kettle", "light.bathroom_group"]);
  });

  it("filters compact entity registry display responses", () => {
    const filtered = filterEntityRegistryDisplayByPermission(
      {
        entities: [{ ei: "switch.kettle" }, { ei: "light.bedroom" }],
        entity_categories: {},
      } as any,
      summary
    );

    expect(filtered.entities).toEqual([{ ei: "switch.kettle" }]);
  });

  it("filters device and area registries", () => {
    expect(
      filterDeviceRegistryByPermission(
        [{ id: "device-kettle" }, { id: "device-bedroom" }] as any,
        summary
      )
    ).toEqual([{ id: "device-kettle" }]);
    expect(
      filterAreaRegistryByPermission(
        [{ area_id: "kitchen" }, { area_id: "bedroom" }] as any,
        summary
      )
    ).toEqual([{ area_id: "kitchen" }]);
  });

  it("filters floors that do not contain authorized areas", () => {
    expect(
      filterFloorRegistryByPermission(
        [{ floor_id: "first" }, { floor_id: "second" }] as any,
        {
          kitchen: { area_id: "kitchen", floor_id: "first" },
        } as any,
        summary
      )
    ).toEqual([{ floor_id: "first" }]);
  });

  it("removes Lovelace cards and rows that reference unauthorized objects", () => {
    const config = filterLovelaceConfigByPermission(
      {
        views: [
          {
            title: "Home",
            badges: ["switch.kettle", "light.bedroom"],
            cards: [
              {
                type: "entities",
                entities: ["switch.kettle", "light.bedroom"],
              },
              {
                type: "button",
                entity: "light.bedroom",
              },
              {
                type: "button",
                entity: "sensor.kitchen_temp",
              },
            ],
          },
        ],
      } as any,
      summary
    ) as any;

    expect(config.views[0].badges).toEqual(["switch.kettle"]);
    expect(config.views[0].cards).toEqual([
      {
        type: "entities",
        entities: ["switch.kettle"],
      },
      {
        type: "button",
        entity: "sensor.kitchen_temp",
      },
    ]);
  });

  it("filters admin panels for scoped users", () => {
    const panels = filterPanelsByPermission(
      {
        home: {
          component_name: "lovelace",
          config: null,
          icon: null,
          title: "Home",
          url_path: "home",
        },
        config: {
          component_name: "config",
          config: null,
          icon: null,
          title: "Settings",
          url_path: "config",
        },
        hidden_admin: {
          component_name: "custom",
          config: null,
          icon: null,
          title: "Admin",
          url_path: "hidden_admin",
          require_admin: true,
        },
      },
      summary
    );

    expect(Object.keys(panels)).toEqual(["home"]);
  });

  it("uses permission grant identity for scoped users", () => {
    const user = applyPermissionGatewayUser(
      {
        id: "ha-admin",
        is_admin: true,
        is_owner: true,
        name: "Home Assistant Admin",
        credentials: [
          { auth_provider_type: "homeassistant", auth_provider_id: "x" },
        ],
        mfa_modules: [{ id: "totp", name: "TOTP", enabled: true }],
      },
      { ...summary, template_name: "Room 101" }
    );

    expect(user).toMatchObject({
      is_admin: false,
      is_owner: false,
      name: "Room 101",
      credentials: [],
      mfa_modules: [],
    });
  });

  it("prefers gateway display name for scoped users", () => {
    expect(
      getPermissionGatewayDisplayName({
        ...summary,
        template_id: "template-101",
        template_name: "Room 101",
        display_name: "北楼101客人",
      })
    ).toBe("北楼101客人");
  });

  it("uses cached permission summary before permissions fetch completes", () => {
    savePermissionGatewaySummary({
      ...summary,
      grant_id: "grant-101",
      display_name: "北楼101客人",
    });

    const user = applyPermissionGatewayUser(
      {
        id: "ha-admin",
        is_admin: true,
        is_owner: true,
        name: "Home Assistant Admin",
        credentials: [
          { auth_provider_type: "homeassistant", auth_provider_id: "x" },
        ],
        mfa_modules: [{ id: "totp", name: "TOTP", enabled: true }],
      },
      undefined,
      { data: { clientId: "permission-gateway-web" } } as any
    );

    expect(user).toMatchObject({
      id: "grant-101",
      is_admin: false,
      is_owner: false,
      name: "北楼101客人",
      credentials: [],
      mfa_modules: [],
    });
  });

  it("does not trust cached admin summaries for gateway sessions", () => {
    savePermissionGatewaySummary({
      ...summary,
      role: "admin",
      display_name: "HA Admin",
    });

    const user = applyPermissionGatewayUser(
      {
        id: "ha-admin",
        is_admin: true,
        is_owner: true,
        name: "Home Assistant Admin",
        credentials: [
          { auth_provider_type: "homeassistant", auth_provider_id: "x" },
        ],
        mfa_modules: [{ id: "totp", name: "TOTP", enabled: true }],
      },
      undefined,
      { data: { clientId: "permission-gateway-web" } } as any
    );

    expect(user).toMatchObject({
      is_admin: false,
      is_owner: false,
      name: "未命名权限模板",
      credentials: [],
      mfa_modules: [],
    });
  });

  it("blocks admin websocket commands for scoped users", () => {
    expect(
      isPermissionGatewayWSMessageAllowed(
        { type: "auth/long_lived_access_token" },
        summary
      )
    ).toBe(false);
    expect(
      isPermissionGatewayWSMessageAllowed(
        { type: "config/entity_registry/list_for_display" },
        summary
      )
    ).toBe(false);
    expect(
      isPermissionGatewayWSMessageAllowed({ type: "get_states" }, summary)
    ).toBe(true);
  });

  it("blocks scoped service calls without explicit entity, device, or area targets", () => {
    expect(
      getPermissionGatewayServiceCallDeniedReason(
        "persistent_notification",
        "dismiss_all",
        undefined,
        undefined,
        summary
      )
    ).toBe(
      "Permission gateway service calls must include entity_id, device_id, or area_id"
    );
    expect(
      getPermissionGatewayServiceCallDeniedReason(
        "light",
        "turn_on",
        { entity_id: "light.kitchen" },
        undefined,
        summary
      )
    ).toBeUndefined();
    expect(
      getPermissionGatewayServiceCallDeniedReason(
        "light",
        "turn_on",
        {},
        { entity_id: ["light.kitchen"] },
        summary
      )
    ).toBeUndefined();
    expect(
      getPermissionGatewayServiceCallDeniedReason(
        "light",
        "turn_on",
        { entity_id: "all" },
        undefined,
        summary
      )
    ).toBe("Permission gateway does not allow global service targets");
  });

  it("recognizes legacy stored gateway tokens without a client id", () => {
    localStorage.setItem(
      PERMISSION_GATEWAY_TOKENS_STORAGE_KEY,
      JSON.stringify({
        hassUrl: "https://gateway.example",
        refresh_token: "refresh-101",
      })
    );

    const auth = {
      data: {
        hassUrl: "https://gateway.example",
        refresh_token: "refresh-101",
      },
    } as any;

    expect(isPermissionGatewaySession(auth)).toBe(true);
    expect(shouldRestrictPermissionGateway(undefined, auth)).toBe(true);
  });

  it("recognizes iOS external auth gateway sessions", () => {
    history.replaceState(null, "", "/?external_auth=1");

    expect(
      isPermissionGatewaySession({
        data: { clientId: "", hassUrl: location.origin },
      } as any)
    ).toBe(true);
    expect(
      shouldRestrictPermissionGateway(undefined, {
        data: { clientId: "", hassUrl: location.origin },
      } as any)
    ).toBe(true);
  });

  it("stores iOS bridge device public keys for gateway requests", () => {
    savePermissionGatewayDevicePublicKey("ios-device-key");

    expect(getPermissionGatewayDevicePublicKey()).toBe("ios-device-key");
  });

  it("creates a registry-independent dashboard for scoped users", () => {
    const config = createPermissionGatewayLovelaceConfig(
      {
        "switch.kettle": { entity_id: "switch.kettle" } as any,
        "light.bedroom": { entity_id: "light.bedroom" } as any,
      },
      { ...summary, display_name: "北楼101客人" },
      localize,
      "zh-Hans"
    );

    expect(config).toMatchObject({
      views: [
        {
          title: "北楼101客人",
          type: "sections",
          sections: [
            {
              type: "grid",
              cards: [
                {
                  type: "heading",
                  heading: "开关",
                  icon: "mdi:toggle-switch",
                },
                { type: "tile", entity: "switch.kettle" },
              ],
            },
          ],
        },
      ],
    });
  });

  it("uses gateway-filtered states when an area grant has no expanded entity list", () => {
    const config = createPermissionGatewayLovelaceConfig(
      {
        "switch.kettle": { entity_id: "switch.kettle" } as any,
        "sensor.kitchen_temp": { entity_id: "sensor.kitchen_temp" } as any,
      },
      { ...summary, entity_ids: [], display_name: "北楼101客人" },
      localize,
      "zh-Hans"
    );

    expect(config?.views[0].sections).toMatchObject([
      {
        cards: [
          {
            type: "heading",
            heading: "开关",
          },
          {
            type: "tile",
            entity: "switch.kettle",
          },
        ],
      },
      {
        cards: [
          {
            type: "heading",
            heading: "传感器",
          },
          {
            type: "tile",
            entity: "sensor.kitchen_temp",
          },
        ],
      },
    ]);
  });

  it("adds only light group controls for scoped dashboards", () => {
    const config = createPermissionGatewayLovelaceConfig(
      {
        "light.ceiling": {
          entity_id: "light.ceiling",
          attributes: { supported_color_modes: ["onoff"] },
        } as any,
        "light.strip": {
          entity_id: "light.strip",
          attributes: { supported_color_modes: ["brightness"] },
        } as any,
        "light.color_temp": {
          entity_id: "light.color_temp",
          attributes: { supported_color_modes: ["color_temp"] },
        } as any,
        "cover.curtain": {
          entity_id: "cover.curtain",
          attributes: {
            supported_features: 15,
            current_position: 50,
          },
        } as any,
      },
      {
        ...summary,
        entity_ids: [
          "light.ceiling",
          "light.strip",
          "light.color_temp",
          "cover.curtain",
        ],
      },
      localize,
      "en"
    );

    expect(config?.views[0].sections).toMatchObject([
      {
        cards: [
          {
            type: "heading",
            heading: "Lights",
            badges: [
              {
                type: "button",
                text: "All on",
                tap_action: {
                  perform_action: "light.turn_on",
                  target: {
                    entity_id: [
                      "light.ceiling",
                      "light.color_temp",
                      "light.strip",
                    ],
                  },
                },
              },
              {
                type: "button",
                text: "All off",
                tap_action: {
                  perform_action: "light.turn_off",
                  target: {
                    entity_id: [
                      "light.ceiling",
                      "light.color_temp",
                      "light.strip",
                    ],
                  },
                },
              },
            ],
          },
          {
            type: "tile",
            entity: "light.ceiling",
          },
          {
            type: "tile",
            entity: "light.color_temp",
            tap_action: { action: "more-info" },
            hold_action: { action: "more-info" },
            icon_hold_action: { action: "more-info" },
            features: [{ type: "light-brightness" }],
          },
          {
            type: "tile",
            entity: "light.strip",
            features: [{ type: "light-brightness" }],
          },
        ],
      },
      {
        cards: [
          {
            type: "heading",
            heading: "Covers",
          },
          {
            type: "tile",
            entity: "cover.curtain",
            features: [{ type: "cover-open-close" }],
          },
        ],
      },
    ]);
    expect(
      (config?.views[0].sections?.[0].cards as any[]).find(
        (card) => card.entity === "light.color_temp"
      )?.features
    ).not.toContainEqual({ type: "light-color-temp" });
    expect((config?.views[0].sections?.[1].cards as any[])[0].badges).toBe(
      undefined
    );
  });

  it("uses Chinese fallback titles when the bundled panel translations are English", () => {
    const config = createPermissionGatewayLovelaceConfig(
      {
        "light.ceiling": {
          entity_id: "light.ceiling",
          attributes: { supported_color_modes: ["onoff"] },
        } as any,
        "cover.curtain": {
          entity_id: "cover.curtain",
          attributes: { supported_features: 0 },
        } as any,
      },
      {
        ...summary,
        entity_ids: ["light.ceiling", "cover.curtain"],
      },
      localize,
      "zh-Hans"
    );

    expect(
      config?.views[0].sections?.map(
        (section) => (section.cards as any[])[0].heading
      )
    ).toEqual(["灯", "窗帘"]);
    expect(localizePanelTitle(localize, "zh-Hans", "light")).toBe("灯");
  });

  it("lists authorized scenes in the actions group", () => {
    const config = createPermissionGatewayLovelaceConfig(
      {
        "scene.movie": {
          entity_id: "scene.movie",
          state: "2026-05-31T10:00:00+00:00",
          attributes: { friendly_name: "Movie" },
        } as any,
        "light.ceiling": {
          entity_id: "light.ceiling",
          attributes: { supported_color_modes: ["onoff"] },
        } as any,
      },
      {
        ...summary,
        entity_ids: ["scene.movie", "light.ceiling"],
      },
      localize,
      "en"
    );

    expect(config?.views[0].sections).toMatchObject([
      {
        cards: [
          {
            type: "heading",
            heading: "Lights",
          },
          {
            type: "tile",
            entity: "light.ceiling",
          },
        ],
      },
      {
        cards: [
          {
            type: "heading",
            heading: "Actions",
            icon: "mdi:robot",
          },
          {
            type: "tile",
            entity: "scene.movie",
          },
        ],
      },
    ]);
  });

  it("accepts gateway permission aliases", () => {
    expect(
      Object.keys(
        filterStatesByPermission(
          {
            "switch.kettle": { entity_id: "switch.kettle" } as any,
            "light.bedroom": { entity_id: "light.bedroom" } as any,
          },
          {
            ...summary,
            entity_ids: undefined,
            allowed_entity_ids: ["switch.kettle"],
          }
        )
      )
    ).toEqual(["switch.kettle"]);
  });

  it("waits for states before creating scoped dashboard", () => {
    expect(
      createPermissionGatewayLovelaceConfig(null, summary)
    ).toBeUndefined();
  });
});

describe("permission gateway activation qr parsing", () => {
  it("accepts raw activation ids", () => {
    expect(parsePermissionGatewayQrId(" room-101 ")).toBe("room-101");
  });

  it("extracts ids from qr urls", () => {
    expect(
      parsePermissionGatewayQrId(
        "https://example.local/activate?template_id=room-101"
      )
    ).toBe("room-101");
    expect(
      parsePermissionGatewayQrId("https://example.local/activate?qr_id=key-7")
    ).toBe("key-7");
  });

  it("extracts ids from json payloads", () => {
    expect(parsePermissionGatewayQrId('{"qr_id":"key-7"}')).toBe("key-7");
    expect(parsePermissionGatewayQrId('{"template_id":"room-101"}')).toBe(
      "room-101"
    );
  });
});
