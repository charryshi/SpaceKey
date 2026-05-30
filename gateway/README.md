# Home Assistant Permission Gateway

This repository implements the first backend slice of a custom Home Assistant iOS distribution with real device permission isolation.

The iOS client must connect to this gateway, not directly to Home Assistant Core. The gateway holds the upstream Home Assistant long-lived token, issues scoped gateway tokens to the app, filters HA read APIs, and blocks unauthorized service calls before they reach HA.

## What Is Implemented

- QR-code activation with a separate verification code.
- Per-installation grants bound to `app_instance_id` and `device_public_key`.
- Short-lived access tokens and refresh tokens signed by the gateway.
- Custom place tree mapped to HA `area_id` values.
- Mixed permission scopes:
  - inherited place authorization,
  - included devices/entities,
  - excluded devices/entities,
  - explicit script/scene/automation allowlists.
- Admin API and lightweight `/admin` console.
- HA-compatible REST proxy under `/api/*`.
- HA-compatible WebSocket proxy under `/api/websocket`.
- Policy unit tests for filtering, control blocking, expiry, revocation primitives, and activation.

## Security Model

The security boundary is the gateway. A deployment is only safe when Home Assistant Core is not reachable by client devices. Put HA Core on a private network or firewall it so only the gateway host can reach `:8123`.

Client devices never receive the HA long-lived token. They receive gateway tokens only. Every API call from the iOS client must include:

```http
Authorization: Bearer <gateway_access_token>
X-Device-Public-Key: <registered_device_public_key>
```

The WebSocket auth message must include:

```json
{
  "type": "auth",
  "access_token": "<gateway_access_token>",
  "device_public_key": "<registered_device_public_key>"
}
```

## Local Run

Install runtime dependencies:

```bash
python3 -m pip install -e .
```

Create configuration:

```bash
cp .env.example .env
```

Set at least:

- `GATEWAY_SIGNING_SECRET`
- `GATEWAY_ADMIN_TOKEN`
- `HOME_ASSISTANT_URL`
- `HOME_ASSISTANT_TOKEN`

Start the service:

```bash
python3 -m uvicorn permission_gateway.gateway.app:build_app --factory --host 0.0.0.0 --port 8080
```

Open the admin console:

```text
http://localhost:8080/admin
```

## Activation Flow

1. Admin creates a place node and maps it to one or more HA Area ids.
2. Admin uploads or syncs the HA registry snapshot with devices and entities.
3. Admin creates a QR template with a verification code and permission scope.
4. iOS scans the QR code. The QR contains only a template id such as `guest-room-101`.
5. iOS sends the template id, verification code, app instance id, and device public key to `/v1/activation/verify`.
6. Gateway creates a grant, emits a notification, returns scoped access/refresh tokens, and exposes only authorized HA resources.

Example activation request:

```bash
curl -X POST http://localhost:8080/v1/activation/verify \
  -H 'Content-Type: application/json' \
  -d '{
    "qr_id": "guest-room-101",
    "verification_code": "246810",
    "device_public_key": "ios-generated-public-key",
    "app_instance_id": "ios-installation-uuid"
  }'
```

## Admin API

All admin requests require:

```http
Authorization: Bearer <GATEWAY_ADMIN_TOKEN>
```

Main endpoints:

- `POST /v1/admin/places`
- `GET /v1/admin/places`
- `POST /v1/admin/qr-templates`
- `GET /v1/admin/qr-templates`
- `PUT /v1/admin/ha-registry-snapshot`
- `GET /v1/admin/grants`
- `PATCH /v1/admin/grants/{grant_id}`
- `GET /v1/admin/audit`
- `GET /v1/admin/notifications`

## Current Limits

- The included repository is file-backed JSON for local and pilot deployments. `deploy/postgres_schema.sql` defines the intended PostgreSQL shape for production hardening.
- HA registry sync is exposed as an admin snapshot endpoint. A scheduled upstream sync worker should be added before large production use.
- iOS source is not present in this workspace, so the repo includes an iOS client contract and Swift adapter sample instead of patching the Home Assistant iOS fork directly.

## Tests

The core tests use only Python standard library modules:

```bash
python3 -m unittest discover -s tests
```

