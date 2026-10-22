#!/usr/bin/env python3
"""R.O.B.I.E. webapp server: static files + /ws WebSocket, UDP bridge.
Receives web_bridge telemetry datagrams on 9999, broadcasts to browsers;
forwards browser commands as datagrams to web_bridge on 9998."""
import asyncio, pathlib, socket
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

ROOT = pathlib.Path(__file__).resolve().parent / "static"
LINES, CMDS = 9999, 9998
clients = set()
cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
LOOP = None

app = FastAPI()

class TelemetryProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        print(f"[webapp] UDP telemetry listener ready on {LINES}")
    def datagram_received(self, data, addr):
        text = data.decode(errors="replace").rstrip("\r\n")
        if text: LOOP.create_task(_broadcast(text))

async def _broadcast(text):
    for ws in list(clients):
        try: await ws.send_text(text)
        except Exception: clients.discard(ws)

@app.get("/")
async def read_index():
    return FileResponse(ROOT / "index.html")

@app.get("/{file_path:path}")
async def read_static(file_path: str):
    path = ROOT / file_path
    if path.is_file(): return FileResponse(path)
    return FileResponse(ROOT / "index.html")

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept(); clients.add(ws)
    try:
        while True:
            msg = await ws.receive_text()
            try: cmd_sock.sendto((msg.rstrip("\n") + "\n").encode(), ("127.0.0.1", CMDS))
            except OSError: pass
    except WebSocketDisconnect: pass
    finally: clients.discard(ws)

@app.on_event("startup")
async def _up():
    global LOOP
    LOOP = asyncio.get_running_loop()
    await LOOP.create_datagram_endpoint(TelemetryProtocol, local_addr=("127.0.0.1", LINES))

if __name__ == "__main__":
    import uvicorn; uvicorn.run(app, host="0.0.0.0", port=8080)
