"""
server.py - Flask web server for Network Pulse UI

Serves the dashboard HTML and streams live device stats
to the browser via Server-Sent Events (SSE).

Run with:
    sudo python3 main.py --ui
"""

from flask import Flask, Response, render_template_string
import json
import time
import threading

app = Flask(__name__)

# Shared reference — main.py sets this after scanning
_device_stats_map = {}
_meta = {"pulse_count": 0, "start_time": time.time()}


def set_device_stats(device_stats_map, meta):
    global _device_stats_map, _meta
    _device_stats_map = device_stats_map
    _meta = meta


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/stream")
def stream():
    """SSE endpoint — pushes JSON to the browser every second."""
    def event_generator():
        while True:
            data = build_payload()
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(1)
    return Response(event_generator(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# Custom labels set via the dashboard UI  { ip: label }
_labels = {}

@app.route("/label", methods=["POST"])
def set_label():
    from flask import request
    data = request.get_json()
    ip, label = data.get("ip"), data.get("label", "").strip()
    if ip:
        if label:
            _labels[ip] = label
        else:
            _labels.pop(ip, None)
    return {"ok": True}


def build_payload():
    devices = []
    total_rtt = []
    online = 0

    for ip, s in sorted(_device_stats_map.items()):
        rtt = s.last_rtt
        avg = s.avg_rtt
        if rtt is not None:
            online += 1
            total_rtt.append(rtt)
        devices.append({
            "ip":       ip,
            "mac":      s.mac,
            "hostname": _labels.get(ip, s.hostname),
            "vendor":   s.vendor,
            "rtt":      round(rtt, 1) if rtt is not None else None,
            "avg":      round(avg, 1) if avg is not None else None,
            "jitter":   round(s.jitter, 1),
            "loss":     s.loss_percent,
            "status":   s.status,
            "history":  list(s.rtt_history),
        })

    avg_rtt = round(sum(total_rtt) / len(total_rtt), 1) if total_rtt else 0
    avg_jitter = round(
        sum(s.jitter for s in _device_stats_map.values()) / max(len(_device_stats_map), 1), 1
    )
    avg_loss = round(
        sum(s.loss_percent for s in _device_stats_map.values()) / max(len(_device_stats_map), 1), 1
    )

    elapsed = int(time.time() - _meta.get("start_time", time.time()))

    return {
        "devices": devices,
        "summary": {
            "total": len(_device_stats_map),
            "online": online,
            "avg_rtt": avg_rtt,
            "avg_jitter": avg_jitter,
            "avg_loss": avg_loss,
            "pulses": _meta.get("pulse_count", 0),
            "uptime": elapsed,
        }
    }


def run_server(host="0.0.0.0", port=5000):
    """Start Flask in a background thread."""
    t = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
        daemon=True
    )
    t.start()
    return t


# ---------------------------------------------------------------------------
# Dashboard HTML (single-file, no external dependencies except Google Fonts)
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Network Pulse</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --green:       #00ff41;
    --green-bright:#39ff14;
    --green-dim:   #00ff4140;
    --green-faint: #00ff410d;
    --yellow:      #b3ff00;
    --orange:      #ffaa00;
    --red:         #ff3333;
    --bg:          #0a0c0a;
    --bg-card:     #0d100d;
    --border:      #00ff4120;
    --mono:        'Share Tech Mono', monospace;
    --head:        'Orbitron', monospace;
  }

  html, body { background: var(--bg); color: var(--green); font-family: var(--mono); font-size: 13px; min-height: 100vh; overflow-x: hidden; }

  /* CRT scanlines overlay */
  body::before {
    content: '';
    pointer-events: none;
    position: fixed;
    inset: 0;
    background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.04) 2px, rgba(0,0,0,0.04) 4px);
    z-index: 9999;
  }

  /* ── Header ─────────────────────────────────────── */
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 28px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .logo { font-family: var(--head); font-size: 18px; font-weight: 700; letter-spacing: 4px; color: var(--green); }
  .logo span { color: var(--green-bright); opacity: .55; }

  .live-badge {
    display: flex; align-items: center; gap: 7px;
    font-size: 11px; letter-spacing: 2px; color: var(--green-bright);
  }
  .pulse-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--green-bright);
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse { 0%,100%{ opacity:1; box-shadow: 0 0 5px var(--green-bright); } 50%{ opacity:.25; box-shadow: none; } }

  .header-stats { display: flex; gap: 28px; }
  .hstat { display: flex; flex-direction: column; align-items: flex-end; }
  .hstat-val { font-size: 16px; color: var(--green); line-height: 1; }
  .hstat-label { font-size: 9px; letter-spacing: 2px; color: var(--green-dim); margin-top: 2px; }

  /* ── Main ────────────────────────────────────────── */
  main { padding: 22px 28px; }

  /* ── KPI grid ───────────────────────────────────── */
  .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }

  .kcard {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 14px 18px;
  }
  .kcard-label { font-size: 9px; letter-spacing: 3px; color: var(--green-dim); margin-bottom: 6px; }
  .kcard-val { font-family: var(--head); font-size: 24px; color: var(--green); line-height: 1; }
  .kcard-val sup { font-size: 11px; color: rgba(0,255,65,.45); font-family: var(--mono); font-weight: 400; }
  .kbar-wrap { height: 2px; background: var(--green-faint); border-radius: 2px; margin-top: 10px; }
  .kbar { height: 2px; border-radius: 2px; transition: width .6s ease; }

  /* ── Section label ──────────────────────────────── */
  .section-label { font-size: 9px; letter-spacing: 4px; color: rgba(0,255,65,.35); margin-bottom: 10px; }

  /* ── Table ───────────────────────────────────────── */
  .table-wrap { overflow-x: auto; }

  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left; padding: 8px 14px;
    color: rgba(0,255,65,.4); font-size: 9px; letter-spacing: 2px; font-weight: 400;
    border-bottom: 1px solid var(--border);
  }
  th.r, td.r { text-align: right; }
  th.c, td.c { text-align: center; }

  td { padding: 10px 14px; border-bottom: 1px solid var(--green-faint); vertical-align: middle; }
  tr { transition: background .15s; }
  tr:hover td { background: rgba(0,255,65,.04); }

  .ip  { color: #7dffb3; font-weight: 700; letter-spacing: .5px; }
  .mac { color: rgba(0,255,65,.38); font-size: 11px; }

  .ex   { color: var(--green-bright); }
  .good { color: var(--yellow); }
  .fair { color: var(--orange); }
  .poor { color: var(--red); }
  .dim  { color: #333; }

  .badge {
    display: inline-block; padding: 2px 9px; border-radius: 2px;
    font-size: 10px; letter-spacing: 1.5px;
  }
  .badge-ex   { background: rgba(57,255,20,.08);  color: var(--green-bright); border: 1px solid rgba(57,255,20,.3);  }
  .badge-good { background: rgba(179,255,0,.08);  color: var(--yellow);       border: 1px solid rgba(179,255,0,.3); }
  .badge-fair { background: rgba(255,170,0,.08);  color: var(--orange);       border: 1px solid rgba(255,170,0,.3); }
  .badge-poor { background: rgba(255,51,51,.08);  color: var(--red);          border: 1px solid rgba(255,51,51,.3); }
  .badge-to   { background: rgba(64,64,64,.15);   color: #444;                border: 1px solid #333; }

  .spark { letter-spacing: 2px; font-size: 14px; }

  /* ── Footer ─────────────────────────────────────── */
  footer {
    margin-top: 24px; padding: 10px 28px;
    border-top: 1px solid rgba(0,255,65,.1);
    display: flex; justify-content: space-between;
    font-size: 10px; color: rgba(0,255,65,.25);
  }
  .blink { animation: blink .8s step-end infinite; }

  .label-cell { cursor: pointer; position: relative; }
  .label-cell:hover .edit-icon { opacity: 1; }
  .edit-icon { opacity: 0; font-size: 11px; margin-left: 6px; color: rgba(0,255,65,.45); transition: opacity .15s; }
  .label-input {
    background: transparent; border: none; border-bottom: 1px solid var(--green);
    color: #7dffb3; font-family: var(--mono); font-size: 13px; font-weight: 700;
    outline: none; width: 160px; padding: 0;
  }
  @keyframes blink { 50% { opacity: 0; } }

  /* ── Connection error banner ───────────────────── */
  #conn-err {
    display: none;
    background: rgba(255,51,51,.12);
    border: 1px solid rgba(255,51,51,.3);
    color: var(--red);
    padding: 10px 18px;
    margin: 16px 28px 0;
    font-size: 11px;
    letter-spacing: 1px;
  }
</style>
</head>
<body>

<header>
  <div class="logo">NET<span>WORK</span> PULSE</div>
  <div class="live-badge"><span class="pulse-dot"></span>LIVE MONITORING</div>
  <div class="header-stats">
    <div class="hstat"><span class="hstat-val" id="h-devices">—</span><span class="hstat-label">DEVICES</span></div>
    <div class="hstat"><span class="hstat-val" id="h-pulses">—</span><span class="hstat-label">PULSES</span></div>
    <div class="hstat"><span class="hstat-val" id="h-uptime">—</span><span class="hstat-label">UPTIME</span></div>
  </div>
</header>

<div id="conn-err">// CONNECTION LOST — ATTEMPTING RECONNECT...</div>

<main>
  <div class="kpi-grid">
    <div class="kcard">
      <div class="kcard-label">AVG RTT</div>
      <div class="kcard-val" id="k-rtt">—<sup>ms</sup></div>
      <div class="kbar-wrap"><div class="kbar" id="b-rtt" style="width:0%;background:var(--green-bright)"></div></div>
    </div>
    <div class="kcard">
      <div class="kcard-label">DEVICES ONLINE</div>
      <div class="kcard-val" id="k-online">—</div>
      <div class="kbar-wrap"><div class="kbar" id="b-online" style="width:0%;background:var(--green-bright)"></div></div>
    </div>
    <div class="kcard">
      <div class="kcard-label">AVG JITTER</div>
      <div class="kcard-val" id="k-jitter">—<sup>ms</sup></div>
      <div class="kbar-wrap"><div class="kbar" id="b-jitter" style="width:0%;background:var(--yellow)"></div></div>
    </div>
    <div class="kcard">
      <div class="kcard-label">PKT LOSS AVG</div>
      <div class="kcard-val" id="k-loss">—<sup>%</sup></div>
      <div class="kbar-wrap"><div class="kbar" id="b-loss" style="width:0%;background:var(--orange)"></div></div>
    </div>
  </div>

  <div class="section-label">// device heatmap</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>HOSTNAME</th>
          <th>IP ADDRESS</th>
          <th>VENDOR</th>
          <th class="r">LAST RTT</th>
          <th class="r">AVG RTT</th>
          <th class="r">JITTER</th>
          <th class="r">LOSS</th>
          <th class="c">QUALITY</th>
          <th>TREND</th>
        </tr>
      </thead>
      <tbody id="device-table">
        <tr><td colspan="8" style="color:rgba(0,255,65,.3);padding:24px 14px;">// awaiting first probe cycle...</td></tr>
      </tbody>
    </table>
  </div>
</main>

<footer>
  <span>NETWORK PULSE v1.0 // ICMP LATENCY HEATMAP</span>
  <span id="clock" class="blink">_</span>
</footer>

<script>
  const BARS = ' ▁▂▃▄▅▆▇█';

  function sparkline(history, width=10) {
    if (!history || history.length === 0) return '─'.repeat(width);
    const vals = history.slice(-width);
    const maxV = Math.max(...vals) || 1;
    let g = vals.map(v => BARS[Math.round((v / maxV) * (BARS.length - 1))]).join('');
    return g.padStart(width, '─');
  }

  function rttClass(rtt) {
    if (rtt === null) return 'dim';
    if (rtt < 20)  return 'ex';
    if (rtt < 80)  return 'good';
    if (rtt < 150) return 'fair';
    return 'poor';
  }

  function qualityLabel(rtt) {
    if (rtt === null) return ['TIMEOUT', 'badge-to'];
    if (rtt < 20)  return ['EXCELLENT', 'badge-ex'];
    if (rtt < 80)  return ['GOOD',      'badge-good'];
    if (rtt < 150) return ['FAIR',      'badge-fair'];
    return ['POOR', 'badge-poor'];
  }

  function lossClass(loss) {
    if (loss > 10) return 'poor';
    if (loss > 0)  return 'fair';
    return 'ex';
  }

  function renderDevices(devices) {
    const tbody = document.getElementById('device-table');
    if (!devices.length) return;
    tbody.innerHTML = devices.map(d => {
      const rc  = rttClass(d.rtt);
      const arc = rttClass(d.avg);
      const [ql, qb] = qualityLabel(d.rtt);
      const lc  = lossClass(d.loss);
      const sp  = sparkline(d.history);
      const rttVal = d.rtt !== null ? d.rtt.toFixed(1) : '—';
      const avgVal = d.avg !== null ? d.avg.toFixed(1) : '—';
      return `<tr>
        <td class="ip label-cell" data-ip="${d.ip}" title="Click to rename">
          <span class="label-text">${d.hostname !== d.ip ? d.hostname : d.ip}</span>
          <span class="edit-icon">✎</span>
        </td>
        <td class="ip" style="font-size:11px;opacity:.7">${d.ip}</td>
        <td style="color:rgba(0,255,65,.5);font-size:11px">${d.vendor}</td>
        <td class="r ${rc}">${rttVal}</td>
        <td class="r ${arc}">${avgVal}</td>
        <td class="r ${d.jitter > 20 ? 'poor' : d.jitter > 5 ? 'good' : 'ex'}">${d.jitter.toFixed(1)}</td>
        <td class="r ${lc}">${d.loss}%</td>
        <td class="c"><span class="badge ${qb}">${ql}</span></td>
        <td class="spark ${rc}">${sp}</td>
      </tr>`;
    }).join('');
  }

  function renderSummary(s) {
    document.getElementById('h-devices').textContent = s.total;
    document.getElementById('h-pulses').textContent  = s.pulses;
    document.getElementById('h-uptime').textContent  = s.uptime + 's';

    document.getElementById('k-rtt').innerHTML    = s.avg_rtt    + '<sup>ms</sup>';
    document.getElementById('k-online').innerHTML = s.online + '<sup>/' + s.total + '</sup>';
    document.getElementById('k-jitter').innerHTML = s.avg_jitter + '<sup>ms</sup>';
    document.getElementById('k-loss').innerHTML   = s.avg_loss   + '<sup>%</sup>';

    const rttPct    = Math.min(s.avg_rtt / 200 * 100, 100).toFixed(1);
    const onlinePct = s.total ? (s.online / s.total * 100).toFixed(1) : 0;
    const jitPct    = Math.min(s.avg_jitter / 50 * 100, 100).toFixed(1);
    const lossPct   = Math.min(s.avg_loss, 100).toFixed(1);

    document.getElementById('b-rtt').style.width    = rttPct + '%';
    document.getElementById('b-online').style.width = onlinePct + '%';
    document.getElementById('b-jitter').style.width = jitPct + '%';
    document.getElementById('b-loss').style.width   = lossPct + '%';

    // color KPI bars based on health
    const rttBar = document.getElementById('b-rtt');
    rttBar.style.background = s.avg_rtt < 20 ? 'var(--green-bright)' : s.avg_rtt < 80 ? 'var(--yellow)' : s.avg_rtt < 150 ? 'var(--orange)' : 'var(--red)';
  }

  // ── Inline label editor ─────────────────────────────
  document.getElementById('device-table').addEventListener('click', e => {
    const cell = e.target.closest('.label-cell');
    if (!cell) return;
    const ip = cell.dataset.ip;
    const span = cell.querySelector('.label-text');
    const current = span.textContent;
    const input = document.createElement('input');
    input.className = 'label-input';
    input.value = current;
    cell.innerHTML = '';
    cell.appendChild(input);
    input.focus();
    input.select();

    const save = () => {
      const newLabel = input.value.trim() || current;
      fetch('/label', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ip, label: newLabel})
      });
      cell.innerHTML = `<span class="label-text">${newLabel}</span><span class="edit-icon">✎</span>`;
    };

    input.addEventListener('blur', save);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') input.blur(); if (e.key === 'Escape') { input.value = current; input.blur(); } });
  });

  // ── SSE connection ────────────────────────────────
  let errShown = false;

  function connect() {
    const es = new EventSource('/stream');

    es.onmessage = (e) => {
      const payload = JSON.parse(e.data);
      renderDevices(payload.devices);
      renderSummary(payload.summary);
      if (errShown) {
        document.getElementById('conn-err').style.display = 'none';
        errShown = false;
      }
    };

    es.onerror = () => {
      document.getElementById('conn-err').style.display = 'block';
      errShown = true;
      es.close();
      setTimeout(connect, 3000);
    };
  }

  connect();

  // ── Clock ─────────────────────────────────────────
  setInterval(() => {
    document.getElementById('clock').textContent =
      new Date().toLocaleTimeString('en-GB', { hour12: false }) + ' // ACTIVE';
  }, 1000);
</script>
</body>
</html>
"""