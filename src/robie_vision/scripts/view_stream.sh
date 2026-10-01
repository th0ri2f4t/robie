#!/usr/bin/env bash
# Run ON THE LAPTOP. Usage: ./scripts/view_stream.sh [pi-ip]
PI_IP="${1:-192.168.0.80}"
ffplay -f mjpeg -fflags nobuffer -flags low_delay -probesize 32 \
  -analyzeduration 0 -framedrop "tcp://${PI_IP}:8888"
