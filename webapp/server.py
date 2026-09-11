#!/usr/bin/env python3
"""R.O.B.I.E. Mission Control server (FastAPI) v3.
Dashboard + SLAM page + /ws telemetry with commands and mock LiDAR.
Source MOCK: patrol/goto/manual modes, plume events, battery, 360-deg scans.
Commands: W,x,y | E,0|1 | D,vx,vy,wz | A,1
Scan line: Z,<base64 of 360 uint8 ranges in decimetres>
"""
import asyncio
import base64
import math
import random
import time
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="R.O.B.I.E. Mission Control")

ENV = [
    (-4.0, -3.0, 4.0, -3.0),
    (4.0, -3.0, 4.0, 3.0),
    (4.0, 3.0, -4.0, 3.0),
    (-4.0, 3.0, -4.0, -3.0),
    (0.8, -1.2, 0.8, 0.6),
    (-2.2, 0.8, -1.2, 0.8),
    (-1.2, 0.8, -1.2, 1.8),
    (-1.2, 1.8, -2.2, 1.8),
    (-2.2, 1.8, -2.2, 0.8),
]

def randn():
    return (random.random() + random.random() + random.random() - 1.5) * 1.6

def ray_range(x, y, ang):
    dx = math.cos(ang)
    dy = math.sin(ang)
    best = 8.0
    for (x1, y1, x2, y2) in ENV:
        sx = x2 - x1
        sy = y2 - y1
        den = dx * sy - dy * sx
        if abs(den) < 1e-9:
            continue
        t = ((x1 - x) * sy - (y1 - y) * sx) / den
        s = ((x1 - x) * dy - (y1 - y) * dx) / den
        if t > 0.02 and 0.0 <= s <= 1.0 and t < best:
            best = t
    return best

class MockWorld:
    def __init__(self):
        self.t0 = time.time()
        self.batt = 12.6
        self.leak = False
        self.leak_until = 0.0
        self.estop = False
        self.mode = "patrol"
        self.th = 0.0
        self.x = 2.0
        self.y = 0.0
        self.target = (0.0, 0.0)
        self.vel = (0.0, 0.0, 0.0)
        self.resume_patrol = False
        self.scan_ctr = 0
    def command(self, msg):
        p = msg.split(",")
        if p[0] == "W" and len(p) == 3:
            self.target = (float(p[1]), float(p[2]))
            self.mode = "goto"
            self.resume_patrol = True
        elif p[0] == "E" and len(p) == 2:
            self.estop = p[1] == "1"
        elif p[0] == "D" and len(p) == 4:
            self.vel = (float(p[1]), float(p[2]), float(p[3]))
            self.mode = "manual"
        elif p[0] == "A" and len(p) == 2 and p[1] == "1":
            self.mode = "patrol"
            self.th = math.atan2(self.y, self.x)
    def step(self):
        t = time.time() - self.t0
        if not self.estop:
            if self.mode == "patrol":
                self.th += 0.035
                self.x = 2.0 * math.cos(self.th)
                self.y = 2.0 * math.sin(self.th)
            elif self.mode == "goto":
                dx = self.target[0] - self.x
                dy = self.target[1] - self.y
                d = math.hypot(dx, dy)
                if d < 0.08:
                    if self.resume_patrol:
                        self.mode = "patrol"
                        self.th = math.atan2(self.y, self.x)
                else:
                    s = min(0.09, d)
                    self.x += dx / d * s
                    self.y += dy / d * s
                    self.th = math.atan2(dy, dx)
            elif self.mode == "manual":
                self.x += self.vel[0] * 0.1
                self.y += self.vel[1] * 0.1
                self.th += self.vel[2] * 0.1
        self.batt = max(10.5, self.batt - 0.0004)
        if not self.leak and random.random() < 0.004:
            self.leak = True
            self.leak_until = t + 6.0
        if self.leak and t > self.leak_until:
            self.leak = False
        spike = 2200.0 if self.leak else 0.0
        g4 = int(800 + randn() * 40 + spike * (0.7 + random.random() * 0.3))
        g6 = int(650 + randn() * 35 + spike * (0.3 + random.random() * 0.3))
        bf = 1 if random.random() < 0.015 else 0
        lines = [
            "P,%.2f,%.2f,%.2f" % (self.x, self.y, self.th),
            "T,%d,%d,0" % (1 if self.estop else 0, bf),
            "B,%.2f" % self.batt,
            "H,%d" % int(t * 1000),
            "G,%d,%d" % (g4, g6),
            ]
        self.scan_ctr += 1
        if self.scan_ctr % 4 == 0:
            ranges = []
            for a in range(360):
                r = ray_range(self.x, self.y, self.th + a * math.pi / 180.0)
                r += (random.random() - 0.5) * 0.06
                ranges.append(max(1, min(80, int(r * 10))))
            lines.append("Z," + base64.b64encode(bytes(ranges)).decode())
        if self.leak and random.random() < 0.15:
            lines.append("L,%.2f,%.2f,%.2f" % (0.5 + random.random() * 0.5, self.x, self.y))
        if random.random() < 0.003:
            lines.append("C,%.2f,%.2f,%.2f" % (0.6 + random.random() * 0.39, self.x, self.y))
        return lines

@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    world = MockWorld()
    async def sender():
        try:
            while True:
                for line in world.step():
                    await sock.send_text(line)
                await asyncio.sleep(0.1)
        except Exception:
            pass
    task = asyncio.create_task(sender())
    try:
        while True:
            msg = await sock.receive_text()
            world.command(msg)
    except Exception:
        pass
    finally:
        task.cancel()

app.mount("/", StaticFiles(directory="static", html=True), name="static")