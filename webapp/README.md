# R.O.B.I.E. Mission Control (webapp)
Browser-based operator dashboard + SLAM map for the R.O.B.I.E. UGV.
Run:  python3 -m pip install -r requirements.txt
      python3 -m uvicorn server:app --reload --port 8000
Open: http://127.0.0.1:8000            (dashboard)
      http://127.0.0.1:8000/slam.html  (3D SLAM map, click-to-navigate)
Modes: server mock (live pill) or offline fallback (demo pill) automatically.
Commands over /ws: W,x,y (drive to point) | D,vx,vy,wz (manual) | E,0|1 (e-stop) | A,1 (auto patrol).
Scan stream: Z,<base64 of 360 uint8 ranges in decimetres> - mock lidar now,
real RPLIDAR + odometry bridge later uses the same P/Z format unchanged.
Optional: drop a GLB model at static/models/rover.glb to replace the mecanum fallback rover.