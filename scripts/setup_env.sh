#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/fastrtps_udp_only.xml" ~/
grep -q "FASTRTPS_DEFAULT_PROFILES_FILE" ~/.bashrc || echo 'export FASTRTPS_DEFAULT_PROFILES_FILE=$HOME/fastrtps_udp_only.xml' >> ~/.bashrc
source ~/.bashrc
rm -f /dev/shm/fastrtps_*
ros2 daemon stop && ros2 daemon start
echo "DDS UDP-only profile installed and activated."
