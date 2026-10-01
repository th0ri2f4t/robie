#!/usr/bin/env bash
# Run ON THE PI. Usage: ./scripts/capture.sh [output.jpg]
OUT="${1:-$HOME/picam-control/captures/shot_$(date +%Y%m%d_%H%M%S).jpg}"
rpicam-still -n -o "$OUT" && echo "Saved $OUT"
