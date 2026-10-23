#!/usr/bin/env python3
"""
R.O.B.I.E. mission-control dashboard server.

Serves the dashboard on port 8080 (NOT 8082: safety_node already owns 8082).
The browser talks to ROS through rosbridge (ws://<pi>:9090) and sends STOP/RESET
straight to safety_node (http://<pi>:8082). This server only:
  * serves the page, JS, CSS and 3D model
  * offers /api/estop and /api/reset as a fallback path to safety_node
  * reports which services are reachable at /api/status

Environment overrides:
  ROBIE_WEB_PORT      (default 8080)
  ROBIE_SAFETY_URL    (default http://127.0.0.1:8082)
  ROBIE_ROSBRIDGE_PORT(default 9090)
  ROBIE_CAMERA_PORT   (default 8081)
"""
import os
import socket
import time
import urllib.error
import urllib.request

from flask import Flask, jsonify, render_template, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_PORT = int(os.environ.get("ROBIE_WEB_PORT", "8080"))
SAFETY_URL = os.environ.get("ROBIE_SAFETY_URL", "http://127.0.0.1:8082").rstrip("/")
ROSBRIDGE_PORT = int(os.environ.get("ROBIE_ROSBRIDGE_PORT", "9090"))
CAMERA_PORT = int(os.environ.get("ROBIE_CAMERA_PORT", "8081"))

if WEB_PORT == int(SAFETY_URL.rsplit(":", 1)[-1].split("/")[0]):
    raise SystemExit(f"ROBIE_WEB_PORT {WEB_PORT} clashes with safety_node at {SAFETY_URL}; pick another port.")

app = Flask(__name__,
            template_folder=os.path.join(HERE, "templates"),
            static_folder=os.path.join(HERE, "static"))


def _post_safety(path: str):
    """Forward a POST to safety_node. Short timeout: a stop that hangs is worse than one that fails loudly."""
    t0 = time.perf_counter()
    req = urllib.request.Request(f"{SAFETY_URL}{path}", data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=0.5) as r:
            body = r.read(512).decode(errors="replace")
            ok = 200 <= r.status < 300
            code = r.status
    except urllib.error.HTTPError as e:
        ok, code, body = False, e.code, str(e)
    except Exception as e:  # connection refused, timeout, DNS ...
        ok, code, body = False, None, str(e)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    return jsonify({"ok": ok, "status": code, "latency_ms": ms, "detail": body[:200]}), (200 if ok else 502)


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@app.after_request
def _no_cache_api(resp):
    resp.headers["Cache-Control"] = "no-store" if resp.mimetype == "application/json" else resp.headers.get(
        "Cache-Control", "no-cache")
    return resp


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/estop", methods=["POST"])
def estop():
    return _post_safety("/estop")


@app.route("/api/reset", methods=["POST"])
def reset():
    return _post_safety("/reset")


@app.route("/api/status")
def status():
    safety_port = int(SAFETY_URL.rsplit(":", 1)[-1].split("/")[0])
    return jsonify({
        "web": True,
        "time": time.time(),
        "safety_node": _port_open(safety_port),
        "rosbridge": _port_open(ROSBRIDGE_PORT),
        "camera": _port_open(CAMERA_PORT),
        "ports": {"web": WEB_PORT, "safety": safety_port, "rosbridge": ROSBRIDGE_PORT, "camera": CAMERA_PORT},
    })


@app.route("/models/<path:name>")
def models(name):
    return send_from_directory(os.path.join(HERE, "static", "models"), name)


if __name__ == "__main__":
    print(f"R.O.B.I.E. dashboard on http://0.0.0.0:{WEB_PORT}  (safety_node: {SAFETY_URL})")
    app.run(host="0.0.0.0", port=WEB_PORT, threaded=True)
