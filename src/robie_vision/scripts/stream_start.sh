#!/usr/bin/env bash
# Run ON THE PI. Starts a low-latency MJPEG stream on TCP 8888.
rpicam-vid -t 0 -n --codec mjpeg --width 640 --height 480 --framerate 30 \
  --quality 50 --denoise cdn_off --flush --listen -o tcp://0.0.0.0:8888
