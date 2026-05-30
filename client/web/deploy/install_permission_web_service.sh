#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/ha-permission-web}"
PORT="${HA_PERMISSION_WEB_PORT:-18123}"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/ha-permission-web.service"

cd "$APP_DIR"

python3 -m venv .venv
".venv/bin/python" -m pip install --upgrade pip
".venv/bin/python" -m pip install fastapi 'uvicorn[standard]' httpx websockets

mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=Home Assistant Permission Web
After=network-online.target ha-permission-gateway.service

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=HA_WEB_ROOT=$APP_DIR/hass_frontend
Environment=PERMISSION_GATEWAY_URL=http://127.0.0.1:18080
ExecStart=$APP_DIR/.venv/bin/uvicorn deploy.permission_web_server:app --host 0.0.0.0 --port $PORT
Restart=on-failure
RestartSec=5
TimeoutStopSec=5

[Install]
WantedBy=default.target
SERVICE

systemctl --user daemon-reload
systemctl --user enable --now ha-permission-web.service
systemctl --user restart ha-permission-web.service
systemctl --user --no-pager --full status ha-permission-web.service
