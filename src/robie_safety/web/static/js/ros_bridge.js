// Minimal rosbridge v2 client (no roslib dependency, works offline).
// Re-subscribes and re-advertises automatically after a reconnect.

export class RosBridge extends EventTarget {
  constructor(url) {
    super();
    this.url = url;
    this.ws = null;
    this.subs = new Map();        // id -> {topic, type, cb, opts}
    this.byTopic = new Map();     // topic -> Set(id)
    this.advertised = new Map();  // topic -> type
    this.nextId = 1;
    this.retryMs = 1000;
    this.timer = null;
    this.manualClose = false;
    this.state = 'idle';
    this.pending = new Map();     // service call id -> {resolve, reject, timer}
  }

  _setState(s, detail = '') {
    this.state = s;
    this.dispatchEvent(new CustomEvent('state', { detail: { state: s, detail } }));
  }

  isOpen() { return this.ws && this.ws.readyState === WebSocket.OPEN; }

  connect() {
    clearTimeout(this.timer);
    this.manualClose = false;
    this._setState('connecting');
    let ws;
    try { ws = new WebSocket(this.url); } catch (e) { this._scheduleReconnect(String(e)); return; }
    this.ws = ws;
    ws.onopen = () => {
      this.retryMs = 1000;
      this._setState('connected');
      for (const [topic, type] of this.advertised) this._send({ op: 'advertise', topic, type });
      for (const [id, s] of this.subs) this._sendSubscribe(id, s);
    };
    ws.onmessage = (ev) => {
      let m;
      try { m = JSON.parse(ev.data); } catch { return; }
      if (m.op === 'publish') {
        const ids = this.byTopic.get(m.topic);
        if (!ids) return;
        for (const id of ids) {
          const s = this.subs.get(id);
          try { s && s.cb(m.msg); } catch (e) { console.error('subscriber error', m.topic, e); }
        }
      } else if (m.op === 'service_response') {
        const p = this.pending.get(m.id);
        if (p) {
          clearTimeout(p.timer); this.pending.delete(m.id);
          if (m.result === false) p.reject(new Error(typeof m.values === 'string' ? m.values : 'service call failed'));
          else p.resolve(m.values);
        }
      } else if (m.op === 'status' && m.level === 'error') {
        console.warn('rosbridge:', m.msg);
      }
    };
    ws.onerror = () => {};   // onclose follows and handles it
    ws.onclose = (ev) => {
      if (this.ws !== ws) return;
      this._setState('disconnected', ev.reason || `code ${ev.code}`);
      if (!this.manualClose) this._scheduleReconnect();
    };
  }

  _scheduleReconnect(reason = '') {
    clearTimeout(this.timer);
    this._setState('waiting', `${reason} retry in ${Math.round(this.retryMs / 1000)} s`.trim());
    this.timer = setTimeout(() => this.connect(), this.retryMs);
    this.retryMs = Math.min(this.retryMs * 2, 10000);
  }

  reconnect() {
    this.retryMs = 1000;
    if (this.ws) { const old = this.ws; this.ws = null; try { old.close(); } catch {} }
    this.connect();
  }

  _send(obj) {
    if (!this.isOpen()) return false;
    this.ws.send(JSON.stringify(obj));
    return true;
  }

  _sendSubscribe(id, s) {
    this._send({ op: 'subscribe', id: `sub_${id}`, topic: s.topic, type: s.type,
                 throttle_rate: s.opts.throttle_rate ?? 0, queue_length: s.opts.queue_length ?? 1 });
  }

  // Returns an unsubscribe function.
  subscribe(topic, type, cb, opts = {}) {
    const id = this.nextId++;
    const s = { topic, type, cb, opts };
    this.subs.set(id, s);
    if (!this.byTopic.has(topic)) this.byTopic.set(topic, new Set());
    this.byTopic.get(topic).add(id);
    this._sendSubscribe(id, s);
    return () => {
      this.subs.delete(id);
      this.byTopic.get(topic)?.delete(id);
      this._send({ op: 'unsubscribe', id: `sub_${id}`, topic });
    };
  }

  // Call a ROS service through rosbridge. Resolves with the response fields.
  callService(service, type, args = {}, timeoutMs = 8000) {
    return new Promise((resolve, reject) => {
      const id = `call_${this.nextId++}`;
      if (!this._send({ op: 'call_service', id, service, type, args })) { reject(new Error('ROS is offline')); return; }
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error('no reply from ' + service)); }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
    });
  }

  advertise(topic, type) {
    if (this.advertised.get(topic) === type) return;
    this.advertised.set(topic, type);
    this._send({ op: 'advertise', topic, type });
  }

  // Returns false if the socket is not open (the message is dropped, never queued:
  // stale motion commands must not be replayed after a reconnect).
  publish(topic, type, msg) {
    this.advertise(topic, type);
    return this._send({ op: 'publish', topic, msg });
  }
}

export function yawFromQuaternion(q) {
  return Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
}

export function quaternionFromYaw(yaw) {
  return { x: 0, y: 0, z: Math.sin(yaw / 2), w: Math.cos(yaw / 2) };
}

export function nowStamp() {
  const t = Date.now();
  return { sec: Math.floor(t / 1000), nanosec: (t % 1000) * 1e6 };
}
