// Renders nav_msgs/OccupancyGrid onto a canvas, overlays the robot pose and goal,
// and converts clicks to map-frame goals when manual mode is on.

import { yawFromQuaternion } from './ros_bridge.js';

const COLORS = {        // pastel "liquid-glass DOS" palette
  unknown: [36, 28, 62],     // deep violet (not yet seen)
  free: [216, 207, 242],     // pale lavender
  occupied: [124, 77, 230],  // saturated violet: walls stand out on both
};

export class SlamMap extends EventTarget {
  constructor(canvas) {
    super();
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.grid = document.createElement('canvas');   // 1 px per cell, north up
    this.gctx = this.grid.getContext('2d');
    this.info = null;           // {width,height,resolution,ox,oy,oyaw}
    this.pose = null;           // {x,y,yaw}
    this.goal = null;           // {x,y}
    this.trail = [];
    this.scanPts = null;        // Float32Array of x,y pairs (map frame) for the live scan overlay
    this.manual = false;
    this.view = { scale: 1, x: 0, y: 0, fitted: false };
    this.followRobot = false;
    this.mapVersion = 0;
    this._dirty = true;
    this._drag = null;
    this._bind();
    new ResizeObserver(() => this._resize()).observe(canvas);
    this._resize();
    const loop = () => { if (this._dirty) this._draw(); requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  }

  // ---------- data in ----------
  setMap(msg) {
    const w = msg.info.width, h = msg.info.height;
    if (!w || !h) return;
    const o = msg.info.origin;
    this.info = { width: w, height: h, resolution: msg.info.resolution,
                  ox: o.position.x, oy: o.position.y, oyaw: yawFromQuaternion(o.orientation) };
    if (this.grid.width !== w || this.grid.height !== h) { this.grid.width = w; this.grid.height = h; }
    const img = this.gctx.createImageData(w, h);
    const d = msg.data;
    this.raw = Int8Array.from(d);
    for (let r = 0; r < h; r++) {
      const dst = (h - 1 - r) * w;      // flip rows so +y is up on screen
      for (let c = 0; c < w; c++) {
        const v = d[r * w + c];
        let col;
        if (v < 0) col = COLORS.unknown;
        else if (v >= 65) col = COLORS.occupied;
        else if (v <= 20) col = COLORS.free;
        else { const t = v / 100; col = COLORS.free.map((f, i) => Math.round(f + (COLORS.occupied[i] - f) * t)); }
        const p = (dst + c) * 4;
        img.data[p] = col[0]; img.data[p + 1] = col[1]; img.data[p + 2] = col[2]; img.data[p + 3] = 255;
      }
    }
    this.gctx.putImageData(img, 0, 0);
    this.mapVersion++;
    if (!this.view.fitted) this.fit();
    this._dirty = true;
    this.dispatchEvent(new CustomEvent('map', { detail: this.info }));
  }

  setPose(x, y, yaw) {
    this.pose = { x, y, yaw };
    const last = this.trail[this.trail.length - 1];
    if (!last || Math.hypot(last.x - x, last.y - y) > 0.05) {
      this.trail.push({ x, y });
      if (this.trail.length > 600) this.trail.shift();
    }
    if (this.followRobot && this.info) this._centreOn(x, y);
    this._dirty = true;
  }

  setGoal(goal) { this.goal = goal; this._dirty = true; }
  setScan(xy) { this.scanPts = xy; this._dirty = true; }
  setManual(on) { this.manual = on; this.canvas.classList.toggle('is-manual', on); }

  // ---------- coordinate transforms ----------
  // world (m, map frame) <-> grid cell (col,row) <-> grid image px (gx,gy) <-> canvas px
  worldToImage(wx, wy) {
    const i = this.info, dx = wx - i.ox, dy = wy - i.oy;
    const c = Math.cos(-i.oyaw), s = Math.sin(-i.oyaw);
    const col = (c * dx - s * dy) / i.resolution, row = (s * dx + c * dy) / i.resolution;
    return { gx: col, gy: i.height - row };
  }
  imageToWorld(gx, gy) {
    const i = this.info, col = gx, row = i.height - gy;
    const c = Math.cos(i.oyaw), s = Math.sin(i.oyaw);
    return { x: i.ox + (c * col - s * row) * i.resolution, y: i.oy + (s * col + c * row) * i.resolution };
  }
  imageToCanvas(gx, gy) { return { cx: gx * this.view.scale + this.view.x, cy: gy * this.view.scale + this.view.y }; }
  canvasToImage(cx, cy) { return { gx: (cx - this.view.x) / this.view.scale, gy: (cy - this.view.y) / this.view.scale }; }

  // ---------- view ----------
  fit() {
    if (!this.info) return;
    this._userMoved = false;
    const W = this.canvas.clientWidth, H = this.canvas.clientHeight;
    const s = Math.min(W / this.info.width, H / this.info.height) * 0.92;
    this.view = { scale: s, x: (W - this.info.width * s) / 2, y: (H - this.info.height * s) / 2, fitted: true };
    this._dirty = true;
  }
  _centreOn(wx, wy) {
    const { gx, gy } = this.worldToImage(wx, wy);
    this.view.x = this.canvas.clientWidth / 2 - gx * this.view.scale;
    this.view.y = this.canvas.clientHeight / 2 - gy * this.view.scale;
  }
  zoom(f, cx = this.canvas.clientWidth / 2, cy = this.canvas.clientHeight / 2) {
    this._userMoved = true;
    const s = Math.max(0.2, Math.min(60, this.view.scale * f));
    const k = s / this.view.scale;
    this.view.x = cx - (cx - this.view.x) * k;
    this.view.y = cy - (cy - this.view.y) * k;
    this.view.scale = s;
    this._dirty = true;
  }

  _resize() {
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.max(1, Math.round(this.canvas.clientWidth * dpr));
    this.canvas.height = Math.max(1, Math.round(this.canvas.clientHeight * dpr));
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (this.info && (!this.view.fitted || !this._userMoved)) this.fit();   // keep fitted until the user pans/zooms
    this._dirty = true;
  }

  _bind() {
    const cv = this.canvas;
    cv.addEventListener('wheel', (e) => {
      e.preventDefault();
      const r = cv.getBoundingClientRect();
      this.zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });
    cv.addEventListener('pointerdown', (e) => {
      cv.setPointerCapture(e.pointerId);
      this._drag = { x: e.clientX, y: e.clientY, vx: this.view.x, vy: this.view.y, moved: false };
    });
    cv.addEventListener('pointermove', (e) => {
      if (!this._drag) return;
      const dx = e.clientX - this._drag.x, dy = e.clientY - this._drag.y;
      if (Math.hypot(dx, dy) > 4) this._drag.moved = true;
      if (this._drag.moved) {
        this.followRobot = false; this._userMoved = true;
        this.view.x = this._drag.vx + dx; this.view.y = this._drag.vy + dy; this._dirty = true;
      }
    });
    cv.addEventListener('pointerup', (e) => {
      const d = this._drag; this._drag = null;
      if (!d || d.moved || !this.info) return;
      const r = cv.getBoundingClientRect();
      const { gx, gy } = this.canvasToImage(e.clientX - r.left, e.clientY - r.top);
      if (gx < 0 || gy < 0 || gx > this.info.width || gy > this.info.height) {
        this.dispatchEvent(new CustomEvent('rejected', { detail: 'Click inside the mapped area.' }));
        return;
      }
      if (!this.manual) {
        this.dispatchEvent(new CustomEvent('rejected', { detail: 'Switch to manual mode to send the robot to a point.' }));
        return;
      }
      const w = this.imageToWorld(gx, gy);
      const cell = this._cellValue(gx, gy);
      if (cell >= 65) {
        this.dispatchEvent(new CustomEvent('rejected', { detail: 'That point is an obstacle on the map.' }));
        return;
      }
      this.dispatchEvent(new CustomEvent('goal', { detail: { ...w, unknown: cell < 0 } }));
    });
  }

  _cellValue(gx, gy) {
    const i = this.info, col = Math.floor(gx), row = i.height - 1 - Math.floor(gy);
    if (!this.raw || col < 0 || row < 0 || col >= i.width || row >= i.height) return -1;
    return this.raw[row * i.width + col];
  }

  // ---------- drawing ----------
  _draw() {
    this._dirty = false;
    const ctx = this.ctx, W = this.canvas.clientWidth, H = this.canvas.clientHeight;
    ctx.clearRect(0, 0, W, H);
    if (!this.info) return;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.grid, this.view.x, this.view.y, this.info.width * this.view.scale, this.info.height * this.view.scale);
    this._drawScale(ctx, W, H);

    if (this.trail.length > 1) {
      ctx.strokeStyle = 'rgba(232, 176, 40, 0.9)'; ctx.lineWidth = 2; ctx.beginPath();
      this.trail.forEach((p, k) => {
        const { gx, gy } = this.worldToImage(p.x, p.y); const { cx, cy } = this.imageToCanvas(gx, gy);
        k ? ctx.lineTo(cx, cy) : ctx.moveTo(cx, cy);
      });
      ctx.stroke();
    }
    if (this.scanPts) {
      ctx.fillStyle = 'rgba(255, 159, 216, 0.95)';
      const s = Math.max(2, Math.min(4, this.view.scale * 0.6));
      for (let k = 0; k < this.scanPts.length; k += 2) {
        const g = this.worldToImage(this.scanPts[k], this.scanPts[k + 1]), c = this.imageToCanvas(g.gx, g.gy);
        ctx.fillRect(c.cx - s / 2, c.cy - s / 2, s, s);
      }
    }
    if (this.goal) {
      const { gx, gy } = this.worldToImage(this.goal.x, this.goal.y); const { cx, cy } = this.imageToCanvas(gx, gy);
      ctx.strokeStyle = '#3fbf8f'; ctx.fillStyle = 'rgba(159,240,208,0.35)'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(cx, cy, 10, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx - 15, cy); ctx.lineTo(cx + 15, cy); ctx.moveTo(cx, cy - 15); ctx.lineTo(cx, cy + 15); ctx.stroke();
      if (this.pose) {
        const a = this.worldToImage(this.pose.x, this.pose.y), pa = this.imageToCanvas(a.gx, a.gy);
        ctx.setLineDash([6, 6]); ctx.beginPath(); ctx.moveTo(pa.cx, pa.cy); ctx.lineTo(cx, cy); ctx.stroke(); ctx.setLineDash([]);
      }
    }
    if (this.pose) {
      const { gx, gy } = this.worldToImage(this.pose.x, this.pose.y); const { cx, cy } = this.imageToCanvas(gx, gy);
      const yawScreen = -(this.pose.yaw - this.info.oyaw);
      // footprint: 0.266 x 0.196 m shell
      const L = 0.266 / this.info.resolution * this.view.scale, Wd = 0.196 / this.info.resolution * this.view.scale;
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(yawScreen);
      ctx.fillStyle = 'rgba(255, 120, 200, 0.45)'; ctx.strokeStyle = '#d63f97'; ctx.lineWidth = 1.5;
      ctx.fillRect(-L / 2, -Wd / 2, L, Wd); ctx.strokeRect(-L / 2, -Wd / 2, L, Wd);
      const a = Math.max(12, L * 0.6);
      ctx.fillStyle = '#d63f97'; ctx.beginPath(); ctx.moveTo(a, 0); ctx.lineTo(-a * 0.45, a * 0.45); ctx.lineTo(-a * 0.2, 0); ctx.lineTo(-a * 0.45, -a * 0.45); ctx.closePath(); ctx.fill();
      ctx.restore();
    }
  }

  _drawScale(ctx, W, H) {
    const pxPerM = this.view.scale / this.info.resolution;
    const steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50];
    const m = steps.find((s) => s * pxPerM > 70) || 50;
    const len = m * pxPerM;
    ctx.fillStyle = 'rgba(27,18,54,0.8)'; ctx.fillRect(10, H - 34, len + 20, 24);
    ctx.strokeStyle = '#e3d7ff'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(20, H - 18); ctx.lineTo(20 + len, H - 18); ctx.moveTo(20, H - 23); ctx.lineTo(20, H - 13); ctx.moveTo(20 + len, H - 23); ctx.lineTo(20 + len, H - 13); ctx.stroke();
    ctx.fillStyle = '#e3d7ff'; ctx.font = '16px DOS, monospace';
    ctx.fillText(m >= 1 ? `${m} m` : `${m * 100} cm`, 26 + len / 2 - 12, H - 22);
  }
}
