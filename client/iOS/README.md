# SpaceKey iOS Client / SpaceKey iOS 客户端

## 中文说明

### 项目定位

本目录是 SpaceKey 的 iOS 客户端，基于 Home Assistant iOS 开源客户端定制。客户端不直接连接 Home Assistant Core，而是只连接 SpaceKey Permission Gateway，由网关代理 HA frontend、WebSocket、REST、媒体和服务调用，并在服务端执行设备权限过滤。

Gateway 和 Web 前端不在本目录维护，已经分别放在本仓库其他目录：

- Gateway: `gateway/`
- Web frontend: `client/web/`
- iOS client: `client/iOS/`

如果 iOS 侧发现必须调整网关协议或权限逻辑，请不要直接在本目录修改网关实现。应提交接口变更说明、原因和建议代码，交给网关项目维护者处理。

### 安全边界

权限隔离的安全边界在 Gateway，不在 iOS UI。

iOS 侧负责：

- 扫描房间/场所二维码并输入认证码。
- 通过 `/v1/activation/verify` 激活 gateway key。
- 保存 gateway access token、refresh token、grant id、设备公钥绑定信息。
- 通过 gateway 建立 WebView frontend session。
- 只加载 gateway frontend origin。
- 将 HAKit、REST、WebSocket、native WebView bridge 都指向 gateway。
- 默认关闭未完成权限适配的原生能力。

iOS 侧不能做：

- 持有 HA Core token。
- 直接连接 HA Core。
- 通过原 HA 登录、服务器发现、多服务器管理绕过 Gateway。
- 通过 Watch、Widget、CarPlay、Shortcuts、Push、Location、Sensors 等原生入口绕过 Gateway。

### 当前主要改动

#### 1. 网关扫码激活

新增 Gateway onboarding 流程：

- 路径：`Sources/App/Onboarding/Steps/Gateway/`
- 默认进入扫码激活界面。
- 二维码只提供 `qr_id` 或 gateway URL 信息。
- 用户扫码后输入认证码。
- 激活成功后创建本地 server 记录，但该 server 指向 gateway，而不是 HA Core。

相关文件：

- `PermissionGatewayActivationView.swift`
- `PermissionGatewayQRScannerView.swift`
- `PermissionGatewayClient.swift`
- `PermissionGatewayOnboardingService.swift`
- `PermissionGatewayDeviceIdentityStore.swift`
- `PermissionGatewayModels.swift`

#### 2. Gateway token 和认证续期

在 Shared API 层增加 gateway token 支持：

- `Sources/Shared/API/Authentication/TokenInfo.swift`
- `Sources/Shared/API/Authentication/TokenManager.swift`
- `Sources/Shared/API/Authentication/AuthenticationAPI.swift`
- `Sources/Shared/API/WebSocket/AuthRequestMessage.swift`

当 token 中存在 `gatewayDevicePublicKey` 时，refresh/revoke 使用 gateway API，而不是 HA OAuth 流程。

#### 3. WebView frontend session

WebView 加载 gateway frontend 前，会先调用 gateway session bootstrap：

- `POST /v1/frontend/session`
- 写入 WebView cookie
- 加载 gateway 返回或持久化的 frontend URL
- external auth bridge 只允许 gateway origin

相关文件：

- `Sources/App/Frontend/WebView/WebViewController+ProtocolConformance.swift`
- `Sources/App/Frontend/ExternalMessageBus/SafeScriptMessageHandler.swift`
- `Sources/Shared/API/Server.swift`

#### 4. Onboarding 精简

网关版不再弹出原 Home Assistant 的下列引导：

- 位置授权
- 通知授权
- 远程连接安全提示
- 原 HA 自动化/设备位置相关提示

相关文件：

- `Sources/App/Onboarding/Container/`
- `Sources/App/Frontend/Extensions/WebViewController+PostOnboarding.swift`
- `Sources/App/Frontend/WebView/WebViewController+Onboarding.swift`

#### 5. 原生能力默认关闭

本定制版加入统一开关：

- `Sources/Shared/Environment/AppConstants.swift`
- `AppConstants.isPermissionGatewayBuild = true`

当前关闭或拦截：

- Push/APNs/Firebase Messaging
- 通知权限弹窗
- Live Activity push token
- 后台位置和后台 fetch
- Watch 通信
- Widgets 更新
- App Icon Shortcuts
- URL scheme 中的 `call_service`、`fire_event`、`send_location`、`assist`、`camera`、`createcustomwidget`、`invite`
- WebView external bus 中的 settings、NFC、Matter、Assist、Improv、原生 camera player、entity add-to
- DebugSwift 浮层
- 原 HA 多功能设置页

相关文件：

- `Sources/App/AppDelegate.swift`
- `Sources/App/Notifications/NotificationManager.swift`
- `Sources/App/Utilities/Permissions.swift`
- `Sources/App/Frontend/IncomingURLHandler.swift`
- `Sources/App/Frontend/ExternalMessageBus/WebViewExternalBusMessage.swift`
- `Sources/App/Frontend/ExternalMessageBus/WebViewExternalMessageHandler.swift`
- `Sources/App/Settings/`
- `Sources/App/Scenes/WebViewSceneDelegate.swift`

#### 6. 失败页和设置页定制

WebView 加载失败时不再展示原 HA 的设置、服务器选择、调试入口。网关版显示简化错误页：

- 标题：`网关连接失败`
- 操作：重试
- 不显示原 HA 设置和错误详情调试入口

相关文件：

- `Sources/App/Frontend/WebView/WebViewController+EmptyState.swift`
- `Sources/App/Frontend/WebView/Views/WebViewEmptyStateStyle.swift`
- `Sources/App/Frontend/WebView/Views/WebViewEmptyStateView.swift`

#### 7. 最小 entitlements 和主 App 构建

当前 iOS 主 App 不申请推送能力，也不申请未使用的高风险能力。

已从主 App entitlements 移除：

- `aps-environment`
- notification communication/time-sensitive
- App Groups
- Associated Domains
- NFC
- Siri
- Wi-Fi Info

已从主 App embed/build dependency 移除未适配 gateway 权限的扩展：

- Watch
- Widgets
- Intents
- Share
- Notification Service/Content
- Matter
- PushProvider

相关文件：

- `Configuration/Entitlements/App-ios.entitlements`
- `Configuration/Entitlements/App-catalyst.entitlements`
- `Configuration/HomeAssistant.xcconfig`
- `Configuration/HomeAssistant.debug.xcconfig`
- `HomeAssistant.xcodeproj/project.pbxproj`

### 编译环境

已验证环境：

- macOS with Xcode and iOS 26.2 platform installed
- Ruby 3.3 from Homebrew
- Bundler 2.2.2
- CocoaPods through project-local bundle

建议不要使用系统 Ruby 安装全局 gems，也不要污染 shell profile。推荐使用本地 bundle：

```bash
bundle _2.2.2_ install
bundle _2.2.2_ exec pod install --repo-update
```

如果系统 Ruby 版本太低，使用 Homebrew Ruby 3.3 执行 Bundler wrapper。

本地生成物不应提交：

- `.bundle/`
- `vendor/bundle/`
- `Pods/`
- `build/`
- `DerivedData/`
- `Configuration/HomeAssistant.overrides.xcconfig`
- `Sources/App/Resources/GoogleService-Info-*.plist`

SpaceKey iOS 已禁用 Firebase 和推送通知，不应提交 Firebase `GoogleService-Info-*.plist` 文件。

### 本地签名配置

`Configuration/HomeAssistant.overrides.xcconfig` 是本地文件，默认被忽略。可按需创建：

```xcconfig
DEVELOPMENT_TEAM = YOUR_TEAM_ID
BUNDLE_ID_PREFIX = your.bundle.prefix

ENABLE_CRITICAL_ALERTS_YOUR_TEAM_ID = 0
ENABLE_PUSH_PROVIDER_YOUR_TEAM_ID = 0
ENABLE_DEVICE_NAME_YOUR_TEAM_ID = 0
ENABLE_THREAD_NETWORK_CREDENTIALS_YOUR_TEAM_ID = 0
ENABLE_CARPLAY_YOUR_TEAM_ID = 0

PROVISIONING_PROFILE_SPECIFIER_YOUR_TEAM_ID_App =
PROVISIONING_PROFILE_SPECIFIER_YOUR_TEAM_ID_Extensions_PushProvider =
```

Personal Team 临时验证包可使用空或最小 entitlements。当前源码已尽量避免申请免费 Apple ID 不支持的能力。

### 构建命令示例

真机 Debug 构建示例：

```bash
xcodebuild build -workspace HomeAssistant.xcworkspace \
  -scheme App-Debug \
  -configuration Debug \
  -destination 'id=<DEVICE_ID>' \
  -derivedDataPath /tmp/spacekey-ios-dd \
  DEVELOPMENT_TEAM=<TEAM_ID> \
  BUNDLE_ID_PREFIX=<BUNDLE_PREFIX> \
  BUNDLE_ID_SUFFIX=.dev \
  CODE_SIGN_IDENTITY='Apple Development'
```

安装到设备：

```bash
xcrun devicectl device install app \
  --device <DEVICE_ID> \
  /tmp/spacekey-ios-dd/Build/Products/Debug-iphoneos/'Home Assistant Δ.app'
```

启动：

```bash
xcrun devicectl device process launch \
  --device <DEVICE_ID> \
  <BUNDLE_ID>
```

### 已验证状态

最近一次验证结果：

- `git diff --check` 通过
- `xcodebuild build` 通过
- 真机安装成功
- 真机主 App 启动成功
- 构建产物未包含 `.appex` 或 Watch 内容
- codesign entitlements 仅包含 app id、team id、get-task-allow、keychain access group

示例安装 bundle id：

```text
ai.goldoak.fresh.HomeAssistant.dev
```

### 后续整合注意事项

- 网关必须继续负责所有设备权限过滤，包括 WebSocket、REST、media、camera、signed path 和 service call。
- iOS 不应把任何 HA Core token 写入本地。
- iOS 不应恢复原 HA 登录、服务器发现、多服务器管理。
- 任何 native feature 恢复前，必须先证明它只通过 gateway token 和 gateway API 工作。
- Watch、Widget、CarPlay、Shortcuts、Assist、NFC、Matter、Push、Location、Sensors 默认保持关闭。
- 修改 gateway 协议时，请同步更新 `gateway/docs/ios-client-contract.md` 和本 README。

### 上游资料

原 Home Assistant iOS README 已保留为：

- `README.home-assistant.md`

原项目许可证和贡献说明仍保留：

- `LICENSE.md`
- `CLA.md`
- `CONTRIBUTING.md`

---

## English

### Project Scope

This directory contains the SpaceKey iOS client. It is a custom fork of the open source Home Assistant iOS client.

The iOS app must not connect directly to Home Assistant Core. It only talks to the SpaceKey Permission Gateway. The Gateway proxies HA frontend, WebSocket, REST, media, and service calls, and enforces device permissions on the server side.

Gateway and Web frontend are maintained outside this directory:

- Gateway: `gateway/`
- Web frontend: `client/web/`
- iOS client: `client/iOS/`

If an iOS change requires a Gateway protocol or permission-logic change, do not implement Gateway code in this directory. Prepare the reason, interface change, and suggested patch for the Gateway maintainers.

### Security Boundary

The security boundary is the Gateway, not the iOS UI.

The iOS app is responsible for:

- Scanning a room/place QR code and collecting the verification code.
- Activating a gateway key through `/v1/activation/verify`.
- Persisting the gateway access token, refresh token, grant id, and device public key binding.
- Creating a WebView frontend session through the Gateway.
- Loading only the Gateway frontend origin.
- Routing HAKit, REST, WebSocket, and native WebView bridge behavior to the Gateway.
- Keeping unadapted native integrations disabled by default.

The iOS app must not:

- Hold a Home Assistant Core token.
- Connect directly to Home Assistant Core.
- Re-enable the normal HA login, discovery, or multi-server management flow.
- Bypass the Gateway through Watch, Widget, CarPlay, Shortcuts, Push, Location, Sensors, or other native entry points.

### Main Changes

#### 1. Gateway QR Activation

Gateway onboarding was added under:

- `Sources/App/Onboarding/Steps/Gateway/`

The app starts from the QR activation flow. The QR code contains only `qr_id` or Gateway URL information. After the user enters the verification code, the app creates a local server record that points to the Gateway, not to HA Core.

Key files:

- `PermissionGatewayActivationView.swift`
- `PermissionGatewayQRScannerView.swift`
- `PermissionGatewayClient.swift`
- `PermissionGatewayOnboardingService.swift`
- `PermissionGatewayDeviceIdentityStore.swift`
- `PermissionGatewayModels.swift`

#### 2. Gateway Token Refresh and Revoke

Gateway token support was added in the Shared API layer:

- `Sources/Shared/API/Authentication/TokenInfo.swift`
- `Sources/Shared/API/Authentication/TokenManager.swift`
- `Sources/Shared/API/Authentication/AuthenticationAPI.swift`
- `Sources/Shared/API/WebSocket/AuthRequestMessage.swift`

When `gatewayDevicePublicKey` exists in token info, refresh and revoke use Gateway APIs instead of HA OAuth.

#### 3. WebView Frontend Session

Before loading the frontend, the WebView prepares a Gateway frontend session:

- Calls `POST /v1/frontend/session`
- Writes the returned cookie into the WebView cookie store
- Loads the returned or persisted Gateway frontend URL
- Allows the external auth bridge only for Gateway origins

Key files:

- `Sources/App/Frontend/WebView/WebViewController+ProtocolConformance.swift`
- `Sources/App/Frontend/ExternalMessageBus/SafeScriptMessageHandler.swift`
- `Sources/Shared/API/Server.swift`

#### 4. Simplified Onboarding

The Gateway build skips the original HA onboarding prompts for:

- Location permission
- Notification permission
- Remote connection security
- HA automation/device-location setup

Key files:

- `Sources/App/Onboarding/Container/`
- `Sources/App/Frontend/Extensions/WebViewController+PostOnboarding.swift`
- `Sources/App/Frontend/WebView/WebViewController+Onboarding.swift`

#### 5. Native Features Disabled by Default

The custom build flag is:

- `Sources/Shared/Environment/AppConstants.swift`
- `AppConstants.isPermissionGatewayBuild = true`

Disabled or blocked by default:

- Push/APNs/Firebase Messaging
- Notification permission prompts
- Live Activity push tokens
- Background location and background fetch
- Watch communication
- Widget updates
- App Icon Shortcuts
- URL scheme actions such as `call_service`, `fire_event`, `send_location`, `assist`, `camera`, `createcustomwidget`, and `invite`
- WebView external bus features for settings, NFC, Matter, Assist, Improv, native camera player, and entity add-to
- DebugSwift overlay
- Original multi-feature HA settings UI

Key files:

- `Sources/App/AppDelegate.swift`
- `Sources/App/Notifications/NotificationManager.swift`
- `Sources/App/Utilities/Permissions.swift`
- `Sources/App/Frontend/IncomingURLHandler.swift`
- `Sources/App/Frontend/ExternalMessageBus/WebViewExternalBusMessage.swift`
- `Sources/App/Frontend/ExternalMessageBus/WebViewExternalMessageHandler.swift`
- `Sources/App/Settings/`
- `Sources/App/Scenes/WebViewSceneDelegate.swift`

#### 6. Custom Error and Settings UI

When the WebView fails to load, the app no longer exposes the original HA settings, server picker, or debug/error details entry points. The Gateway build shows a minimal error screen:

- Title: `网关连接失败`
- Action: Retry
- No original HA settings or debug details button

Key files:

- `Sources/App/Frontend/WebView/WebViewController+EmptyState.swift`
- `Sources/App/Frontend/WebView/Views/WebViewEmptyStateStyle.swift`
- `Sources/App/Frontend/WebView/Views/WebViewEmptyStateView.swift`

#### 7. Minimal Entitlements and Main-App Build

The iOS main app no longer requests push capabilities or unused high-risk capabilities.

Removed from the main app entitlements:

- `aps-environment`
- notification communication/time-sensitive entitlements
- App Groups
- Associated Domains
- NFC
- Siri
- Wi-Fi Info

Removed from the main app embed/build dependency chain until permission adaptation is implemented:

- Watch
- Widgets
- Intents
- Share
- Notification Service/Content
- Matter
- PushProvider

Key files:

- `Configuration/Entitlements/App-ios.entitlements`
- `Configuration/Entitlements/App-catalyst.entitlements`
- `Configuration/HomeAssistant.xcconfig`
- `Configuration/HomeAssistant.debug.xcconfig`
- `HomeAssistant.xcodeproj/project.pbxproj`

### Build Environment

Verified environment:

- macOS with Xcode and iOS 26.2 platform installed
- Homebrew Ruby 3.3
- Bundler 2.2.2
- CocoaPods through project-local bundle

Do not install gems into the system Ruby. Prefer the local bundle:

```bash
bundle _2.2.2_ install
bundle _2.2.2_ exec pod install --repo-update
```

If the system Ruby is too old, run the Bundler wrapper with Homebrew Ruby 3.3.

Do not commit local generated files:

- `.bundle/`
- `vendor/bundle/`
- `Pods/`
- `build/`
- `DerivedData/`
- `Configuration/HomeAssistant.overrides.xcconfig`
- `Sources/App/Resources/GoogleService-Info-*.plist`

The SpaceKey iOS build disables Firebase and push notifications. Firebase `GoogleService-Info-*.plist`
files are intentionally excluded from source control.

### Local Signing

`Configuration/HomeAssistant.overrides.xcconfig` is local-only and ignored by git. Create it when needed:

```xcconfig
DEVELOPMENT_TEAM = YOUR_TEAM_ID
BUNDLE_ID_PREFIX = your.bundle.prefix

ENABLE_CRITICAL_ALERTS_YOUR_TEAM_ID = 0
ENABLE_PUSH_PROVIDER_YOUR_TEAM_ID = 0
ENABLE_DEVICE_NAME_YOUR_TEAM_ID = 0
ENABLE_THREAD_NETWORK_CREDENTIALS_YOUR_TEAM_ID = 0
ENABLE_CARPLAY_YOUR_TEAM_ID = 0

PROVISIONING_PROFILE_SPECIFIER_YOUR_TEAM_ID_App =
PROVISIONING_PROFILE_SPECIFIER_YOUR_TEAM_ID_Extensions_PushProvider =
```

Personal Team debug builds should use empty or minimal entitlements. The current source avoids capabilities unsupported by a free Apple ID as much as possible.

### Build Commands

Device Debug build example:

```bash
xcodebuild build -workspace HomeAssistant.xcworkspace \
  -scheme App-Debug \
  -configuration Debug \
  -destination 'id=<DEVICE_ID>' \
  -derivedDataPath /tmp/spacekey-ios-dd \
  DEVELOPMENT_TEAM=<TEAM_ID> \
  BUNDLE_ID_PREFIX=<BUNDLE_PREFIX> \
  BUNDLE_ID_SUFFIX=.dev \
  CODE_SIGN_IDENTITY='Apple Development'
```

Install:

```bash
xcrun devicectl device install app \
  --device <DEVICE_ID> \
  /tmp/spacekey-ios-dd/Build/Products/Debug-iphoneos/'Home Assistant Δ.app'
```

Launch:

```bash
xcrun devicectl device process launch \
  --device <DEVICE_ID> \
  <BUNDLE_ID>
```

### Verified Status

Last verified state:

- `git diff --check` passed
- `xcodebuild build` passed
- Device install succeeded
- Main iOS app launched
- Build product contains no `.appex` or Watch content
- codesign entitlements include only app id, team id, get-task-allow, and keychain access group

Example installed bundle id:

```text
ai.goldoak.fresh.HomeAssistant.dev
```

### Integration Notes

- Gateway must keep enforcing all device permissions for WebSocket, REST, media, camera, signed paths, and service calls.
- iOS must not persist any HA Core token.
- iOS must not restore the normal HA login, discovery, or multi-server management flow.
- Any native feature must remain disabled until it is proven to work only through Gateway token and Gateway API.
- Watch, Widget, CarPlay, Shortcuts, Assist, NFC, Matter, Push, Location, and Sensors remain disabled by default.
- When the Gateway protocol changes, update `gateway/docs/ios-client-contract.md` and this README.

### Upstream References

The original Home Assistant iOS README is preserved as:

- `README.home-assistant.md`

Original license and contribution documents remain:

- `LICENSE.md`
- `CLA.md`
- `CONTRIBUTING.md`
