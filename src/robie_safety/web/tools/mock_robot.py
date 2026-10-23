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
import asyncio, io, json, math, random, threading, time
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
            STATE["x"] += (vx * math.cos(yaw) - vy * math.sin(yaw)) * dt
            STATE["y"] += (vx * math.sin(yaw) + vy * math.cos(yaw)) * dt
            STATE["yaw"] += wz * dt
            return
        if STATE["goal"]:
            gx, gy = STATE["goal"]; dx, dy = gx - STATE["x"], gy - STATE["y"]; d = math.hypot(dx, dy)
            if d < 0.05: STATE["goal"] = None; return
            target = math.atan2(dy, dx); e = math.atan2(math.sin(target - STATE["yaw"]), math.cos(target - STATE["yaw"]))
            STATE["yaw"] += max(-2 * dt, min(2 * dt, e))
            v = min(0.3, d) * (1 if abs(e) < 0.6 else 0.2)
            STATE["x"] += v * math.cos(STATE["yaw"]) * dt; STATE["y"] += v * math.sin(STATE["yaw"]) * dt
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
            elif op == "unsubscribe":
                CLIENTS[ws].pop(m["topic"], None)
            elif op == "publish":
                on_publish(m["topic"], m["msg"])
    finally:
        CLIENTS.pop(ws, None)

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
            "data": GRID}

async def publisher():
    k = 0
    while True:
        step(0.05)
        with LOCK: x, y, yaw, web = STATE["x"], STATE["y"], STATE["yaw"], STATE["web"]
        await broadcast("/robot_pose", {"header": {"stamp": stamp(), "frame_id": "map"},
                                        "pose": {"position": {"x": x, "y": y, "z": 0.0}, "orientation": quat(yaw)}})
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
        print("mock robot: rosbridge ws://0.0.0.0:9090, safety :8082, camera :8081/stream")
        await publisher()

if __name__ == "__main__":
    asyncio.run(main())
