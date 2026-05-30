# SpaceKey Web Client

## 中文说明

这是 SpaceKey 项目的 Web 客户端，基于 Home Assistant frontend fork 开发。它只包含 Web 前端部分；权限网关和 iOS 客户端分别在独立项目中维护。

本客户端不会直连 Home Assistant Core。所有 REST、WebSocket、媒体和服务调用都必须走 SpaceKey Permission Gateway，由网关在服务端执行设备、实体、场所和服务调用权限过滤。Web 侧的改造目标是让受限用户只看到授权范围内的内容，并避免向网关主动发送明显不适用于受限用户的 HA 管理请求。

### 主要改造

- 使用权限网关登录流程替代普通 Home Assistant 登录流程。
- 支持扫码激活、验证码绑定、短期 access token 和 refresh token。
- 支持 iOS WebView external auth：
  - iOS 加载 `/?external_auth=1`
  - Web 通过 `window.webkit.messageHandlers.getExternalAuth` 获取网关 token
  - WebSocket 使用网关 token 连接 `/api/websocket`
- WebView、REST、WebSocket 均使用当前网关 origin，不直连 HA Core。
- 非管理员用户隐藏配置、开发者工具、Supervisor、长期令牌等 HA 管理入口。
- 非管理员用户的用户名称显示为网关返回的权限模板名称，例如“北楼101客人”。
- 根据网关返回的授权范围过滤：
  - states
  - entity registry display
  - device registry
  - area registry
  - floor registry
  - Lovelace dashboards
  - HA panels
- 为受限用户生成不依赖完整 registry 的默认 dashboard，避免未授权对象出现在 UI 中。
- 受限用户不会预取或发送 HA registry/config/admin 类 WebSocket 命令。
- 受限用户的无 target 或全局 target 服务调用会在 Web 侧提前拦截，最终仍由网关做服务端强制拒绝。
- 支持灯、窗帘、空调、媒体播放器、安防、传感器等常见设备类型按 HA 原有组件样式显示和控制。
- 灯类保留分组级全开/全关控制；其他类型仅在 HA 原生交互需要时显示控制能力。
- 支持中文环境下的分组标题和面板标题本地化。
- 修复受限 registry 缺失时 more-info 详情页、色温灯、虚拟灯组等场景的兼容问题。

### 权限边界

Web 只负责展示和客户端前置拦截，不承担最终安全边界。最终权限由 SpaceKey Permission Gateway 执行，包括：

- token 校验
- key 过期和吊销
- 设备绑定校验
- states 和 registry 过滤
- REST 和 WebSocket 命令过滤
- service call target 校验
- media/camera/signed path 访问校验

如果 Web 误发未授权请求，网关必须拒绝。

### 开发

```bash
cd client/web
node .yarn/releases/yarn-4.15.0.cjs install
node .yarn/releases/yarn-4.15.0.cjs test test/data/permission_gateway.test.ts
```

生产构建：

```bash
cd client/web
SKIP_FETCH_NIGHTLY_TRANSLATIONS=1 ./script/build_frontend
```

测试发布快速构建：

```bash
cd client/web
./script/build_frontend_test
```

`build_frontend_test` 仍使用 production mode 打包，但会设置 `IS_TEST=1`，跳过 source map 和预压缩文件生成，适合测试环境发布。正式生产发布仍应使用 `script/build_frontend`。

本目录下的 `deploy/permission_web_server.py` 和 `deploy/install_permission_web_service.sh` 是 Web 静态服务部署脚本，只服务 Web 前端并反代到网关；它不是权限网关实现。

## English

This is the SpaceKey Web client, forked from the Home Assistant frontend. It contains only the Web client. The Permission Gateway and iOS client are maintained in separate projects.

This client must not connect directly to Home Assistant Core. All REST, WebSocket, media, and service-call traffic must go through the SpaceKey Permission Gateway. The gateway performs server-side filtering and enforcement for devices, entities, areas, and service calls. The Web client focuses on presenting only authorized content and avoiding HA admin requests that are not valid for scoped users.

### Key Changes

- Replaces the normal Home Assistant login flow with the Permission Gateway login flow.
- Supports QR activation, verification-code binding, short-lived access tokens, and refresh tokens.
- Supports iOS WebView external auth:
  - iOS loads `/?external_auth=1`
  - Web obtains the gateway token through `window.webkit.messageHandlers.getExternalAuth`
  - WebSocket authenticates to `/api/websocket` with the gateway token
- Uses the current gateway origin for WebView, REST, and WebSocket traffic. It does not connect to HA Core directly.
- Hides HA admin surfaces for non-admin users, including Settings, Developer Tools, Supervisor, and long-lived access tokens.
- Displays the Permission Gateway template name as the scoped user's display name, for example `North Building 101 Guest`.
- Filters UI data according to the gateway permission summary:
  - states
  - entity registry display
  - device registry
  - area registry
  - floor registry
  - Lovelace dashboards
  - HA panels
- Generates a registry-independent default dashboard for scoped users so unauthorized objects are not shown.
- Prevents scoped users from prefetching or sending HA registry/config/admin WebSocket commands.
- Blocks no-target and global-target service calls on the Web side for scoped users. The gateway remains the final server-side enforcement layer.
- Keeps Home Assistant-style controls for common domains such as lights, covers, climate, media players, security, and sensors.
- Keeps group-level all-on/all-off controls for lights. Other domains only expose aggregate controls where the HA interaction model requires them.
- Adds localized group and panel titles for Chinese environments.
- Fixes compatibility issues when scoped registry data is absent, including more-info dialogs, color-temperature lights, and virtual light groups.

### Security Boundary

The Web client is not the security boundary. It only controls presentation and client-side preflight behavior. The SpaceKey Permission Gateway is responsible for authoritative enforcement, including:

- token validation
- key expiration and revocation
- device binding validation
- states and registry filtering
- REST and WebSocket command filtering
- service-call target validation
- media, camera, and signed-path access validation

If the Web client sends an unauthorized request by mistake, the gateway must reject it.

### Development

```bash
cd client/web
node .yarn/releases/yarn-4.15.0.cjs install
node .yarn/releases/yarn-4.15.0.cjs test test/data/permission_gateway.test.ts
```

Production build:

```bash
cd client/web
SKIP_FETCH_NIGHTLY_TRANSLATIONS=1 ./script/build_frontend
```

Fast test-deployment build:

```bash
cd client/web
./script/build_frontend_test
```

`build_frontend_test` still bundles in production mode, but sets `IS_TEST=1` to skip source maps and precompressed assets. Use it for test deployments. Use `script/build_frontend` for final production releases.

The files under `deploy/` provide a lightweight Web static server and reverse-proxy setup for this frontend. They are not the Permission Gateway implementation.

## License

This project is forked from Home Assistant frontend and keeps the upstream Apache 2.0 license. SpaceKey-specific changes are maintained in this repository under `client/web`.
