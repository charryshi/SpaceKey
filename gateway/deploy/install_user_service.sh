#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/ha-permission-gateway}"
PORT="${GATEWAY_PORT:-18080}"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/ha-permission-gateway.service"

cd "$APP_DIR"

python3 -m venv .venv
".venv/bin/python" -m pip install --upgrade pip
".venv/bin/python" -m pip install -e .

mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=Home Assistant Permission Gateway
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/uvicorn permission_gateway.gateway.app:build_app --factory --host 0.0.0.0 --port $PORT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
SERVICE

systemctl --user daemon-reload
systemctl --user enable --now ha-permission-gateway.service
systemctl --user --no-pager --full status ha-permission-gateway.service

