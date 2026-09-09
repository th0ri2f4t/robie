#!/usr/bin/env python3
"""R.O.B.I.E. Stage A automated bench test."""
import sys, time, threading, datetime
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
ser = serial.Serial(PORT, 115200, timeout=0.1)

latest_T = None
lock = threading.Lock()
running = True

def reader():
    global latest_T
    while running:
        line = ser.readline().decode(errors="ignore").strip()
        if line.startswith("T,"):
            with lock:
                latest_T = line

threading.Thread(target=reader, daemon=True).start()

results = []

def record(name, ok, auto=False):
    results.append((name, ok, auto))
    print(" [%s] %s (%s)" % ("PASS" if ok else "FAIL", name, "auto" if auto else "human"))

def send(cmd, wait=0.4):
    ser.write((cmd + "\n").encode())
    ser.flush()
    time.sleep(wait)

def wait_T(expected, timeout=6):
    t0 = time.time()
    while time.time() - t0 < timeout:
        with lock:
            cur = latest_T
        if cur == expected:
            return True
        time.sleep(0.05)
    return False

def ask(msg):
    while True:
        r = input(" %s [y/n/q]: " % msg).strip().lower()
        if r in ("y", "n", "q"):
            return r

def safe_stop():
    send("M,0,0,0,0", 0.2)
    send("S,0", 0.2)
try:
    print("R.O.B.I.E. Stage A bench test")
    print("CHECK: wheels clear of bench, wall adapter plugged in.")
    input("Press Enter to start...")
    time.sleep(1.0)
    with lock:
        t = latest_T
    print(" telemetry: %s" % t)
    record("safety chain closed (T,0,0,0)", t == "T,0,0,0", auto=True)
    send("S,1")
    print(" motors armed automatically (S,1)")
    for name, i in [("FL", 0), ("FR", 1), ("RL", 2), ("RR", 3)]:
        m = [0, 0, 0, 0]
        m[i] = 1
        send("M,%d,%d,%d,%d" % tuple(m))
        r = ask("%s: spinning forward per tape arrow?" % name)
        record("%s forward" % name, r == "y")
        if r == "q":
            raise KeyboardInterrupt
        m[i] = -1
        send("M,%d,%d,%d,%d" % tuple(m))
        r = ask("%s: spinning reverse?" % name)
        record("%s reverse" % name, r == "y")
        if r == "q":
            raise KeyboardInterrupt
        send("M,0,0,0,0")
    send("M,1,1,1,1")
    record("all forward", ask("all four forward?") == "y")
    send("M,-1,-1,-1,-1")
    record("all reverse", ask("all four reverse?") == "y")
    send("M,1,1,-1,-1")
    record("spin in place", ask("spinning in place?") == "y")
    send("M,0,0,0,0")
    send("M,1,1,1,1")
    input(" NOW PULL the D4 jumper, then press Enter...")
    record("E-stop cut (T,1,0,0)", wait_T("T,1,0,0"), auto=True)
    input(" RE-INSERT D4, then press Enter...")
    record("E-stop release (T,0,0,0)", wait_T("T,0,0,0"), auto=True)
    send("M,0,0,0,0")
    send("M,1,1,1,1")
    send("S,0")
    record("software disarm stops motors", ask("motors stopped after S,0?") == "y")
    input(" PULL D5 jumper, press Enter...")
    record("front bump reports (T,0,1,0)", wait_T("T,0,1,0"), auto=True)
    input(" RE-INSERT D5, press Enter...")
    record("front bump clears", wait_T("T,0,0,0"), auto=True)
    input(" PULL D18 jumper, press Enter...")
    record("rear bump reports (T,0,0,1)", wait_T("T,0,0,1"), auto=True)
    input(" RE-INSERT D18, press Enter...")
    record("rear bump clears", wait_T("T,0,0,0"), auto=True)
finally:
    running = False
    safe_stop()
    ser.close()
    passed = sum(1 for _, ok, _ in results if ok)
    print("")
    print("RESULT: %d/%d passed" % (passed, len(results)))
    with open("bench_A_report.txt", "a") as f:
        f.write("=== %s ===\n" % datetime.datetime.now().isoformat())
        for name, ok, auto in results:
            f.write("%s %s (%s)\n" % ("PASS" if ok else "FAIL", name, "auto" if auto else "human"))
        f.write("TOTAL %d/%d\n" % (passed, len(results)))
    print("report appended to bench_A_report.txt")
