#!/usr/bin/env bash
# R.O.B.I.E. dashboard installer. RUN ON THE RASPBERRY PI, from inside this robie_web folder:
#   bash install.sh
# Installs rosbridge + Flask, copies the dashboard into the ROS workspace and starts both
# as systemd services that come back after every reboot.
set -euo pipefail

ROS_DISTRO_NAME="${ROS_DISTRO_NAME:-jazzy}"
RUN_USER="${SUDO_USER:-$USER}"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
WS="${ROBIE_WS:-$RUN_HOME/robie_ws}"
DEST="$WS/src/robie_safety/web"
SRC="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing packages (rosbridge, Flask)"
sudo apt-get update -qq
sudo apt-get install -y "ros-${ROS_DISTRO_NAME}-rosbridge-server" python3-flask

echo "==> Copying dashboard to $DEST"
mkdir -p "$DEST"
if [ "$SRC" != "$DEST" ]; then
  cp -r "$SRC/." "$DEST/"
fi
chown -R "$RUN_USER":"$RUN_USER" "$DEST"

echo "==> Writing /etc/default/robie (shared ROS settings for both services)"
if [ ! -f /etc/default/robie ]; then
  sudo tee /etc/default/robie >/dev/null <<EOF
# Must match the ROS_DOMAIN_ID your other R.O.B.I.E. nodes use (default 0).
ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
ROBIE_WEB_PORT=8080
ROBIE_SAFETY_URL=http://127.0.0.1:8082
EOF
fi

echo "==> Creating systemd services"
sudo tee /etc/systemd/system/robie-rosbridge.service >/dev/null <<EOF
[Unit]
Description=R.O.B.I.E. rosbridge WebSocket (port 9090)
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
EnvironmentFile=-/etc/default/robie
ExecStart=/bin/bash -c 'source /opt/ros/${ROS_DISTRO_NAME}/setup.bash; [ -f $WS/install/setup.bash ] && source $WS/install/setup.bash; exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090'
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/robie-web.service >/dev/null <<EOF
[Unit]
Description=R.O.B.I.E. mission-control dashboard (port 8080)
After=network-online.target robie-rosbridge.service
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$DEST
EnvironmentFile=-/etc/default/robie
ExecStart=/usr/bin/python3 $DEST/server.py
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now robie-rosbridge.service robie-web.service
sleep 3

echo
echo "==> Service check"
systemctl --no-pager --lines=0 status robie-rosbridge.service robie-web.service | grep -E "●|Active" || true
curl -s --max-time 3 http://127.0.0.1:8080/api/status && echo
echo
echo "Dashboard:  http://192.168.4.1:8080   (ROBIE-NET)"
echo "            http://th0r12f4t.local:8080 (home Wi-Fi)"
echo "Logs:       journalctl -u robie-web -u robie-rosbridge -f"
