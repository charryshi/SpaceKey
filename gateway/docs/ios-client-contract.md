# iOS Client Contract

The custom iOS app must treat the permission gateway as its Home Assistant server. It must not store or request any upstream Home Assistant token.

## Activation

The QR code payload should contain only a gateway URL and a QR template id:

```json
{
  "gateway_url": "https://gateway.example.com",
  "qr_id": "guest-room-101"
}
```

The app asks the user for the verification code and sends:

```http
POST /v1/activation/verify
Content-Type: application/json
```

```json
{
  "qr_id": "guest-room-101",
  "verification_code": "246810",
  "device_public_key": "<device-public-key>",
  "app_instance_id": "<stable-installation-id>"
}
```

The app stores:

- gateway base URL,
- grant id,
- access token,
- refresh token,
- access token expiry,
- device key pair,
- persisted gateway server settings with location upload disabled,
- persisted gateway server settings with sensor upload disabled,
- permission summary for local UX hints only.

The permission summary must not be treated as a security boundary. The gateway remains authoritative.

When the iOS app persists the gateway as a server, default privacy-sensitive companion features to off:

```json
{
  "upload_location": false,
  "upload_sensors": false
}
```

Do not request Location permission or enable sensor upload during QR activation. The user or an administrator can enable those features later through an explicit settings flow if the product requires them.

## Token Refresh

Before access token expiry, call:

```http
POST /v1/auth/refresh
Content-Type: application/json
```

```json
{
  "refresh_token": "<refresh-token>",
  "device_public_key": "<device-public-key>"
}
```

If refresh fails, the app must return to the activation screen.

## Frontend WebView Bootstrap

After activation, the iOS app should establish a gateway frontend session before loading the Home Assistant WebView:

```http
POST /v1/frontend/session
Authorization: Bearer <gateway-access-token>
X-Device-Public-Key: <device-public-key>
```

Response:

```json
{
  "ok": true,
  "grant_id": "...",
  "frontend_url": "https://ha.aivo.19.md/?external_auth=1",
  "frontend_same_origin": false,
  "requires_external_auth_bridge": true,
  "expires_in": 900
}
```

`frontend_url` may be absolute or relative. The iOS app must load this exact URL after resolving relative values against the gateway base URL. Do not hard-code the gateway root URL.

For the customized iOS/Web build, non-admin users must load the modified Web frontend, not the upstream Home Assistant frontend:

```text
https://ha.aivo.19.md/?external_auth=1
```

Reason: the upstream Home Assistant frontend can request dashboard/config payloads that are intentionally filtered for scoped users and may fail with `TypeError: Object.values requires that input parameter not be null or undefined`. The modified Web frontend owns this compatibility fallback.

When `frontend_same_origin` is `true`, the response sets a gateway frontend cookie. The iOS app should make sure this cookie is available to the `WKWebView` cookie store, then load `frontend_url`.

When `requires_external_auth_bridge` is `true`, the frontend URL is on a different origin from the gateway API. Cookies set by `/v1/frontend/session` will not cross origins. The iOS WebView must provide the external-auth bridge/token bootstrap for that WebView origin, and HAKit/REST/WebSocket calls must still target the gateway API origin.

As a fallback for early same-origin integration only, the WebView may load `/?gateway_access_token=<token>&device_public_key=<key>` once; the gateway will set the cookie and redirect to a clean `/?external_auth=1` URL. Prefer the session endpoint because URLs can be logged.

## HA REST Calls

Every REST call goes to the gateway `/api/*` path, with the original HA path preserved:

```http
GET /api/states
Authorization: Bearer <gateway-access-token>
X-Device-Public-Key: <device-public-key>
```

For Home Assistant frontend compatibility, `X-Device-Public-Key` is optional on `/api/*`. When present, the gateway validates device binding. When absent, the gateway validates the scoped access token and still enforces server-side scope filtering and service-call authorization.

The app must not call the HA Core URL discovered from any previous setup state.

## HA WebSocket

Connect to:

```text
wss://gateway.example.com/api/websocket
```

Gateway handshake:

```json
{"type": "auth_required", "ha_version": "permission-gateway"}
```

Client response:

```json
{
  "type": "auth",
  "access_token": "<gateway-access-token>",
  "device_public_key": "<device-public-key>"
}
```

For Web frontend compatibility, `device_public_key` is optional in the WebSocket auth message. Home Assistant Web frontend uses `home-assistant-js-websocket`, whose standard auth payload is:

```json
{"type": "auth", "access_token": "<gateway-access-token>"}
```

When `device_public_key` is present, the gateway verifies token device binding. When it is absent, the gateway validates only the scoped access token and still enforces server-side scope filtering and service-call authorization for every proxied HA message.

After `auth_ok`, the app can use the usual HA WebSocket command shapes. Unauthorized state events are dropped and unauthorized service calls return a `permission_denied` result.

## Home Assistant iOS Fork Touch Points

In the upstream iOS app fork, implement these changes:

- Replace onboarding server discovery with QR activation.
- Store gateway credentials in Keychain only.
- Persist the gateway server with location upload and sensor upload disabled by default.
- Establish `/v1/frontend/session`, load its returned `frontend_url`, and provide an external-auth bridge when `requires_external_auth_bridge` is true.
- Override all HAKit base URLs to the gateway URL.
- Update WebView external auth bridge to provide gateway access tokens, not HA tokens.
- Disable Watch, Widget, CarPlay, and background shortcuts unless they use the same gateway credential provider.
- On `401`, `403`, `auth_invalid`, or refresh failure, clear tokens and require reactivation.
