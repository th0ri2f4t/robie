#!/usr/bin/env python3
"""
Mock R.O.B.I.E. for testing the dashboard on a laptop (no ROS, no robot).

  pip install websockets pillow flask
  python3 tools/mock_robot.py            # fake rosbridge :9090, safety node :8082, camera :8081
  python3 server.py                      # dashboard :8080 (second terminal)
  open http://localhost:8080

The fake robot drives a loop in a small room, publishes gas and crack events,
obeys STOP / RESET, click-to-move goals and manual /cmd_vel.
"""
import asyncio, functools, io, json, math, random, threading, time
import numpy as np
print = functools.partial(print, flush=True)   # log lines appear immediately
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import websockets
from PIL import Image, ImageDraw

STATE = {"x": 1.0, "y": 1.0, "yaw": 0.0, "web": 0, "goal": None, "cmd": None, "cmd_t": 0.0, "t0": time.time()}
LOCK = threading.Lock()

# ---------------------------------------------------------------- map: 8 m x 6 m room, 5 cm cells
RES, W, H = 0.05, 160, 120
def make_map():
    g = [-1] * (W * H)
    for r in range(H):
        for c in range(W):
            x, y = c * RES, r * RES
            if 0.2 < x < 7.8 and 0.2 < y < 5.8:
                g[r * W + c] = 0
            if (0.15 < x < 0.3 or 7.7 < x < 7.85) and 0.15 < y < 5.85: g[r * W + c] = 100
            if (0.15 < y < 0.3 or 5.7 < y < 5.85) and 0.15 < x < 7.85: g[r * W + c] = 100
            if 3.0 < x < 3.2 and 0.3 < y < 3.6: g[r * W + c] = 100          # partition wall
            if 5.2 < x < 6.4 and 3.8 < y < 4.1: g[r * W + c] = 100           # pipe run
            if x > 6.5 and y < 1.4: g[r * W + c] = -1                         # unexplored corner
    return g
GRID = make_map()
GRID_NP = np.array(GRID, dtype=np.int16).reshape(H, W)
LASER = (-0.052, 0.0, 0.179)      # base_link -> laser (scan plane ~0.205 m above the floor)
BASE_Z = 0.026                    # base_link above the floor (wheel axle height)

def occupied(x, y, r=0.13):
    for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r)):
        c, rr = int((x + dx) / RES), int((y + dy) / RES)
        if c < 0 or rr < 0 or c >= W or rr >= H or GRID_NP[rr, c] >= 65:
            return True
    return False

ANG = np.linspace(-math.pi, math.pi, 360, endpoint=False)
STEPS = np.arange(0.15, 12.0, 0.02)
SEEN = np.full((H, W), -1, dtype=np.int16)    # the map the mock robot "discovers", like SLAM

def scan_msg(x, y, yaw):
    lx = x + LASER[0] * math.cos(yaw) - LASER[1] * math.sin(yaw)
    ly = y + LASER[0] * math.sin(yaw) + LASER[1] * math.cos(yaw)
    a = yaw + ANG[:, None]
    px = lx + STEPS[None, :] * np.cos(a); py = ly + STEPS[None, :] * np.sin(a)
    c = (px / RES).astype(int); r = (py / RES).astype(int)
    inside = (c >= 0) & (r >= 0) & (c < W) & (r < H)
    hit = np.zeros_like(inside)
    hit[inside] = GRID_NP[r[inside], c[inside]] >= 65
    hit |= ~inside
    first = np.where(hit.any(1), hit.argmax(1), -1)
    rng = np.where(first >= 0, STEPS[np.clip(first, 0, None)], np.inf)
    # mapping: cells before the hit are free, the hit cell is occupied
    k = np.arange(STEPS.size)[None, :]
    free = inside & (k < np.where(first >= 0, first, STEPS.size)[:, None])
    SEEN[r[free], c[free]] = np.where(SEEN[r[free], c[free]] == 100, 100, 0)
    hb = np.where(first >= 0)[0]
    hc, hr = c[hb, first[hb]], r[hb, first[hb]]
    okh = (hc >= 0) & (hr >= 0) & (hc < W) & (hr < H)
    SEEN[hr[okh], hc[okh]] = 100
    rng = rng + np.random.normal(0, 0.01, rng.shape)
    ranges = [None if not np.isfinite(v) or v > 12.0 else round(float(v), 3) for v in rng]
    return {"header": {"stamp": stamp(), "frame_id": "laser"}, "angle_min": -math.pi, "angle_max": math.pi - 2 * math.pi / 360,
            "angle_increment": 2 * math.pi / 360, "time_increment": 0.0, "scan_time": 0.1, "range_min": 0.15, "range_max": 12.0,
            "ranges": ranges, "intensities": []}

def tf_msg(parent, child, x, y, z, yaw):
    return {"header": {"stamp": stamp(), "frame_id": parent}, "child_frame_id": child,
            "transform": {"translation": {"x": x, "y": y, "z": z}, "rotation": quat(yaw)}}

def quat(yaw): return {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2), "w": math.cos(yaw / 2)}
def stamp():
    t = time.time(); return {"sec": int(t), "nanosec": int((t % 1) * 1e9)}

# ---------------------------------------------------------------- motion
def step(dt):
    with LOCK:
        if STATE["web"]:
            return
        if STATE["cmd"] and time.time() - STATE["cmd_t"] < 0.5:
            c = STATE["cmd"]; yaw = STATE["yaw"]
            vx, vy, wz = c["linear"]["x"], c["linear"]["y"], c["angular"]["z"]
            nx = STATE["x"] + (vx * math.cos(yaw) - vy * math.sin(yaw)) * dt
            ny = STATE["y"] + (vx * math.sin(yaw) + vy * math.cos(yaw)) * dt
            if not occupied(nx, ny): STATE["x"], STATE["y"] = nx, ny
            STATE["yaw"] += wz * dt
            return
        if STATE["goal"]:
            gx, gy = STATE["goal"]; dx, dy = gx - STATE["x"], gy - STATE["y"]; d = math.hypot(dx, dy)
            if d < 0.05: STATE["goal"] = None; return
            target = math.atan2(dy, dx); e = math.atan2(math.sin(target - STATE["yaw"]), math.cos(target - STATE["yaw"]))
            STATE["yaw"] += max(-2 * dt, min(2 * dt, e))
            v = min(0.3, d) * (1 if abs(e) < 0.6 else 0.2)
            nx = STATE["x"] + v * math.cos(STATE["yaw"]) * dt; ny = STATE["y"] + v * math.sin(STATE["yaw"]) * dt
            if occupied(nx, ny):
                STATE["goal"] = None; print("goal blocked by a wall; stopping")
            else:
                STATE["x"], STATE["y"] = nx, ny
            return
        t = time.time() - STATE["t0"]          # patrol loop
        cx, cy, R, w = 1.6, 2.0, 1.0, 0.25
        STATE["x"], STATE["y"] = cx + R * math.cos(w * t), cy + R * math.sin(w * t)
        STATE["yaw"] = w * t + math.pi / 2

# ---------------------------------------------------------------- rosbridge
CLIENTS = {}   # ws -> {topic: (id, throttle_ms, last_sent)}

async def handler(ws):
    CLIENTS[ws] = {}
    try:
        async for raw in ws:
            m = json.loads(raw)
            op = m.get("op")
            if op == "subscribe":
                CLIENTS[ws].setdefault(m["topic"], []).append([m.get("throttle_rate", 0), 0.0])
                if m["topic"] == "/map":
                    await send(ws, "/map", map_msg())
                if m["topic"] == "/tf_static":
                    await send(ws, "/tf_static", {"transforms": [tf_msg("base_link", "laser", *LASER, 0.0)]})
            elif op == "unsubscribe":
                CLIENTS[ws].pop(m["topic"], None)
            elif op == "call_service":
                await ws.send(json.dumps(handle_service(m)))
            elif op == "publish":
                on_publish(m["topic"], m["msg"])
                if m["topic"] in ("/move_goal", "/goal_pose"):
                    await broadcast(m["topic"], m["msg"])      # a real ROS topic reaches every subscriber
    finally:
        CLIENTS.pop(ws, None)

def handle_service(m):
    """Mock of /slam_toolbox/save_map: writes <name>.pgm + <name>.yaml like SLAM Toolbox's map_saver."""
    reply = {"op": "service_response", "id": m.get("id"), "service": m.get("service")}
    if m.get("service") != "/slam_toolbox/save_map":
        reply.update(result=False, values=f"mock robot has no service {m.get('service')}"); return reply
    name = (m.get("args", {}).get("name", {}) or {}).get("data") or "robie_map"
    name = "".join(ch if ch.isalnum() or ch in "_-./~" else "_" for ch in name)
    import os
    path = os.path.expanduser(name)
    pix = bytearray()
    for r in range(H - 1, -1, -1):              # PGM rows top-down
        for c in range(W):
            v = GRID[r * W + c]
            pix.append(205 if v < 0 else (0 if v >= 65 else 254))
    with open(path + ".pgm", "wb") as f:
        f.write(f"P5\n{W} {H}\n255\n".encode()); f.write(bytes(pix))
    with open(path + ".yaml", "w") as f:
        f.write(f"image: {os.path.basename(path)}.pgm\nmode: trinary\nresolution: {RES}\norigin: [0.0, 0.0, 0.0]\n"
                "negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n")
    print(f"saved map -> {path}.pgm / {path}.yaml")
    reply.update(result=True, values={"result": 0}); return reply

def on_publish(topic, msg):
    with LOCK:
        if topic == "/cmd_vel":
            STATE["cmd"], STATE["cmd_t"] = msg, time.time(); STATE["goal"] = None
        elif topic in ("/move_goal", "/goal_pose"):
            p = msg["pose"]["position"]; STATE["goal"] = (p["x"], p["y"]); print(f"goal -> {p['x']:.2f}, {p['y']:.2f}")
        elif topic == "/motor_enable" and msg.get("data") is False:
            STATE["web"] = 1; print("motor_enable false received")

async def send(ws, topic, msg):
    try: await ws.send(json.dumps({"op": "publish", "topic": topic, "msg": msg}))
    except Exception: pass

async def broadcast(topic, msg):
    now = time.time() * 1000
    for ws, subs in list(CLIENTS.items()):
        for s in subs.get(topic, []):
            if now - s[1] >= s[0]:
                s[1] = now
                await send(ws, topic, msg)
                break

def map_msg():
    return {"header": {"stamp": stamp(), "frame_id": "map"},
            "info": {"map_load_time": stamp(), "resolution": RES, "width": W, "height": H,
                     "origin": {"position": {"x": 0.0, "y": 0.0, "z": 0.0}, "orientation": quat(0.0)}},
            "data": SEEN.ravel().tolist()}

async def publisher():
    k = 0
    while True:
        step(0.05)
        with LOCK: x, y, yaw, web = STATE["x"], STATE["y"], STATE["yaw"], STATE["web"]
        await broadcast("/robot_pose", {"header": {"stamp": stamp(), "frame_id": "map"},
                                        "pose": {"position": {"x": x, "y": y, "z": 0.0}, "orientation": quat(yaw)}})
        await broadcast("/tf", {"transforms": [tf_msg("map", "odom", 0.0, 0.0, 0.0, 0.0),
                                               tf_msg("odom", "base_link", x, y, BASE_Z, yaw)]})
        if k % 2 == 0:
            await broadcast("/scan", scan_msg(x, y, yaw))
        if k % 10 == 0:
            await broadcast("/safety_state", {"data": f"wd=1 web={web} estop=0 bf=0 br=0"})
            await broadcast("/motor_enable", {"data": not web})
            await broadcast("/robie/battery", {"data": 7.6 - (time.time() - STATE['t0']) / 3600})
        if k % 20 == 0: await broadcast("/map", map_msg())
        if k % 60 == 30:
            near_pipe = x > 4.5
            await broadcast("/robie/event", {"data": f"G,{random.randint(180, 260) + (400 if near_pipe else 0)},{random.randint(90, 140)}"})
        if k % 140 == 70:
            await broadcast("/robie/event", {"data": f"C,{random.uniform(0.62, 0.93):.2f},{random.uniform(0.3, 0.7):.2f},{random.uniform(0.35, 0.65):.2f}"})
        k += 1
        await asyncio.sleep(0.05)

# ---------------------------------------------------------------- safety node (:8082)
class Safety(BaseHTTPRequestHandler):
    def do_POST(self):
        with LOCK:
            if self.path.startswith("/estop"): STATE["web"] = 1; STATE["goal"] = None
            elif self.path.startswith("/reset"): STATE["web"] = 0
        self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): print("safety:", self.path)

# ---------------------------------------------------------------- MJPEG camera (:8081/stream)
def frame():
    im = Image.new("RGB", (640, 480), (58, 62, 66)); d = ImageDraw.Draw(im)
    t = time.time()
    d.rectangle([0, 300, 640, 480], fill=(84, 82, 76))
    d.rectangle([60, 170, 600, 270], fill=(150, 120, 70), outline=(40, 40, 40), width=3)   # pipe
    d.line([(300, 190), (330, 215), (318, 238), (352, 258)], fill=(30, 25, 20), width=3)   # crack
    if int(t) % 7 < 3:
        d.rectangle([285, 180, 365, 265], outline=(214, 40, 57), width=3); d.text((288, 166), "crack 0.87", fill=(255, 90, 100))
    d.text((10, 10), time.strftime("%H:%M:%S") + "  mock camera", fill=(230, 230, 230))
    b = io.BytesIO(); im.save(b, "JPEG", quality=70); return b.getvalue()

class Cam(BaseHTTPRequestHandler):
    def do_GET(self):
        if not self.path.startswith("/stream"): self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame"); self.end_headers()
        try:
            while True:
                j = frame()
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(j)).encode() + b"\r\n\r\n" + j + b"\r\n")
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError): pass
    def log_message(self, *a): pass

async def main():
    threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", 8082), Safety).serve_forever, daemon=True).start()
    threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", 8081), Cam).serve_forever, daemon=True).start()
    async with websockets.serve(handler, "0.0.0.0", 9090, max_size=2**24):
        print("mock robot: rosbridge ws://0.0.0.0:9090 (map, pose, scan, tf), safety :8082, camera :8081/stream")
        await publisher()

if __name__ == "__main__":
    asyncio.run(main())
