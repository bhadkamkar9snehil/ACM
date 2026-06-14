/* ACM control panel — vanilla JS over the /api routes. No build, no CDN. */
"use strict";

const $ = (sel) => document.querySelector(sel);
const Z_COLS = ["ar1_z", "pca_spe_z", "pca_t2_z", "iforest_z", "gmm_z", "omr_z"];
const Z_LABELS = ["AR1", "PCA-SPE", "PCA-T2", "IForest", "GMM", "OMR"];
const POLL_MS = 20000;

async function api(path, opts = {}) {
  if (opts.body !== undefined) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(opts.body);
  }
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (e) { /* not json */ }
    throw new Error(msg);
  }
  return r.json();
}

// ------------------------------------------------------------ utilities --
function td(text) { const el = document.createElement("td"); el.textContent = text ?? "—"; return el; }
function tdNum(text) { const el = td(text); el.className = "num"; return el; }
function tdHtml(html, cls) { const el = document.createElement("td"); if(cls) el.className = cls; el.innerHTML = html ?? "—"; return el; }
function renderGaugeHtml(valText, ratio, colorVar, deltaHtml = "") {
  const wPct = Math.min(100, Math.max(0, ratio * 100));
  return `
    <div class="h-gauge-wrap">
      <span class="h-gauge-val">${valText}</span>
      <span class="h-gauge-delta">${deltaHtml}</span>
      <div class="h-gauge">
        <div class="h-gauge-fill" style="width: ${wPct}%; background: var(--${colorVar})"></div>
      </div>
    </div>
  `;
}

function badge(state) {
  const el = document.createElement("span");
  el.className = `badge ${state || "NEW"}`;
  el.textContent = state || "NEW";
  return el;
}
function fmtTs(ts) { return ts ? String(ts).slice(0, 16) : "—"; }
function fmtNum(v, d = 2) { return v == null || Number.isNaN(+v) ? "—" : (+v).toFixed(d); }

function fmtRelTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (isNaN(d)) return "—";
  const diffMs = Date.now() - d.getTime();
  const diffSec = Math.round(diffMs / 1000);
  const diffMin = Math.round(diffMs / 60000);
  if (diffSec < 90)  return "just now";
  if (diffMin < 60)  return `${diffMin} min ago`;
  const h = Math.floor(diffMin / 60), m = diffMin % 60;
  if (h < 6) return m ? `${h}h ${m}m ago` : `${h}h ago`;
  const now = new Date();
  const hhmm = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return hhmm;
  const yest = new Date(now); yest.setDate(now.getDate() - 1);
  const prefix = d.toDateString() === yest.toDateString()
    ? "Yesterday"
    : d.toLocaleDateString([], { month: "short", day: "numeric" });
  return `${prefix} ${hhmm}`;
}

function toast(msg, kind = "info", ms = 3500) {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  $("#toasts").append(el);
  setTimeout(() => { el.classList.add("fade"); setTimeout(() => el.remove(), 450); }, ms);
}

/* Generic modal: fields = [{name, label, type?, value?, options?, required?}] */
function openModal(title, fields, submitLabel, onSubmit) {
  $("#modal-title").textContent = title;
  const form = $("#modal-form");
  form.replaceChildren();
  for (const f of fields) {
    const label = document.createElement("label");
    label.textContent = f.label;
    let input;
    if (f.options) {
      input = document.createElement("select");
      input.replaceChildren(...f.options.map((o) => new Option(o, o)));
    } else {
      input = document.createElement("input");
      input.type = f.type || "text";
    }
    input.name = f.name;
    if (f.value !== undefined) input.value = f.value;
    if (f.required) input.required = true;
    label.append(input);
    form.append(label);
  }
  const err = document.createElement("div");
  err.className = "err";
  const row = document.createElement("div");
  row.className = "row";
  const cancel = document.createElement("button");
  cancel.type = "button"; cancel.textContent = "Cancel"; cancel.className = "btn btn-sm";
  cancel.addEventListener("click", closeModal);
  const ok = document.createElement("button");
  ok.type = "submit"; ok.textContent = submitLabel; ok.className = "btn btn-sm btn-brand";
  row.append(cancel, ok);
  form.append(err, row);
  form.onsubmit = async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(form).entries());
    try {
      await onSubmit(body);
      closeModal();
    } catch (ex) {
      err.textContent = ex.message;
    }
  };
  $("#modal-backdrop").classList.remove("hidden");
  form.querySelector("input, select")?.focus();
}
function closeModal() { $("#modal-backdrop").classList.add("hidden"); }
$("#modal-backdrop").addEventListener("click", (e) => {
  if (e.target.id === "modal-backdrop") closeModal();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

function sparkline(points, w = 150, h = 26) {
  /* points: [[day, fused_max], ...] -> coloured SVG sparkline */
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", w); svg.setAttribute("height", h);
  svg.classList.add("spark");
  const vals = points.map((p) => p[1]).filter((v) => v != null);
  if (vals.length < 2) return svg;
  const max = Math.max(4, ...vals);
  const step = w / (points.length - 1);
  let d = "";
  points.forEach((p, i) => {
    if (p[1] == null) return;
    const x = (i * step).toFixed(1);
    const y = (h - 2 - (p[1] / max) * (h - 5)).toFixed(1);
    d += (d ? " L" : "M") + `${x} ${y}`;
  });
  const peak = Math.max(...vals);
  const path = document.createElementNS(svg.namespaceURI, "path");
  path.setAttribute("d", d);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", peak >= 3 ? "var(--chart-alert)" : "var(--blue)");
  path.setAttribute("stroke-width", "1.4");
  path.setAttribute("stroke-linejoin", "round");
  svg.append(path);
  // z=3 reference line when in range
  if (max >= 3) {
    const y3 = h - 2 - (3 / max) * (h - 5);
    const ln = document.createElementNS(svg.namespaceURI, "line");
    ln.setAttribute("x1", 0); ln.setAttribute("x2", w);
    ln.setAttribute("y1", y3); ln.setAttribute("y2", y3);
    ln.setAttribute("stroke", "var(--chart-alert)");
    ln.setAttribute("stroke-opacity", "0.5");
    ln.setAttribute("stroke-dasharray", "3 3");
    svg.prepend(ln);
  }
  return svg;
}

// ---------------------------------------------------------------- tabs ----
let activeTab = "operator";
document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => {
  activeTab = b.dataset.tab;
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tabpane").forEach((p) =>
    p.classList.toggle("active", p.id === `tab-${activeTab}`));
  refresh();
}));

// Theme picker
const selTheme = document.getElementById("sel-theme");
selTheme.value = document.documentElement.dataset.theme || "dark-forge";
selTheme.addEventListener("change", (e) => {
  const next = e.target.value;
  document.body.dataset.theme = next;
  document.documentElement.dataset.theme = next;
  
  // Generate dynamic favicon from CSS vars (deferred to avoid layout thrashing)
  requestAnimationFrame(() => {
    const style = getComputedStyle(document.body);
    const bg = style.getPropertyValue('--favicon-bg').trim();
    const stroke = style.getPropertyValue('--favicon-stroke').trim();
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='25' fill='${encodeURIComponent(bg)}' stroke='${encodeURIComponent(stroke)}' stroke-width='6'/><path d='M20 65 L40 25 L60 75 L80 35' fill='none' stroke='${encodeURIComponent(stroke)}' stroke-width='12' stroke-linecap='round' stroke-linejoin='round'/></svg>`;
    document.getElementById("favicon").href = `data:image/svg+xml,${svg}`;
  });

  if (activeTab === "operator") refreshOperator(true);
  else if (activeTab === "engineer") refreshEngineer(true);
  else if (activeTab === "admin") refreshAdmin(true);
});

// --------------------------------------------------------- mode toggle ----
const btnMode = document.getElementById("btn-mode");
function applyMode(mode) {
  document.documentElement.dataset.mode = mode;
  localStorage.setItem("acm-mode", mode);
  btnMode.textContent = mode === "basic" ? "⊕ Advanced" : "⊖ Basic";
  btnMode.classList.toggle("active", mode === "advanced");
  // Charts must re-render into new grid-area widths
  if (activeTab === "engineer") refreshEngineer(true);
  else if (activeTab === "operator") refreshOperator(true);
}
(function () {
  const saved = localStorage.getItem("acm-mode") || "basic";
  // Initial boot: set mode DOM state only. The boot refresh() at the bottom
  // of this file does the first data load, so we must NOT call the refresh*
  // functions here — their cached* state (let) is still in its temporal dead
  // zone this early in module execution.
  document.documentElement.dataset.mode = saved;
  btnMode.textContent = saved === "basic" ? "⊕ Advanced" : "⊖ Basic";
  btnMode.classList.toggle("active", saved === "advanced");
})();
btnMode.addEventListener("click", () =>
  applyMode(document.documentElement.dataset.mode === "basic" ? "advanced" : "basic")
);

// ------------------------------------------------------------- service ----
let cachedServiceData = null;
async function refreshService(useCache = false) {
  if (!useCache || !cachedServiceData) cachedServiceData = await api("/api/service");
  const svc = cachedServiceData;
  const pill = $("#svc-pill");
  pill.className = "stat-cell " + (svc.tick_in_progress ? "warn" : svc.paused ? "bad" : "ok");
  $("#svc-pill-text").textContent = svc.tick_in_progress ? "TICKING" : svc.paused ? "PAUSED" : "WATCHING";
  const dur = svc.last_tick_duration_s != null ? ` · ${svc.last_tick_duration_s}s` : "";
  const tickEl = $("#svc-tick-info");
  tickEl.textContent = fmtRelTime(svc.last_tick_at) + dur;
  tickEl.title = svc.last_tick_at ? fmtTs(svc.last_tick_at) : "";
  $("#btn-pause").classList.toggle("hidden", !!svc.paused);
  $("#btn-resume").classList.toggle("hidden", !svc.paused);
  if (document.activeElement !== $("#inp-tick")) $("#inp-tick").value = svc.tick_minutes;
  window.lastTickAt = svc.last_tick_at;
  window.tickMinutes = svc.tick_minutes;
  updateCountdown();
  return svc;
}

// C1 — Next-tick countdown timer
function updateCountdown() {
  const nextEl = $("#svc-next-tick");
  if (!window.lastTickAt || !window.tickMinutes) {
    nextEl.textContent = "—";
    return;
  }
  const lastMs = typeof window.lastTickAt === "string"
    ? new Date(window.lastTickAt.replace(" ", "T")).getTime()
    : window.lastTickAt * 1000;
  const nextMs = lastMs + (window.tickMinutes * 60000);
  const nowMs = Date.now();
  const deltaMs = nextMs - nowMs;

  if (deltaMs <= 0) {
    nextEl.textContent = "now";
    nextEl.style.color = "var(--brand)";
  } else if (deltaMs < 60000) {
    const secs = Math.ceil(deltaMs / 1000);
    nextEl.textContent = `${secs}s`;
    nextEl.style.color = "var(--warn)";
  } else {
    const mins = Math.ceil(deltaMs / 60000);
    nextEl.textContent = `${mins}m`;
    nextEl.style.color = "var(--ok)";
  }
}

// Update countdown every second
setInterval(updateCountdown, 1000);

$("#btn-pause").addEventListener("click", async () => {
  await api("/api/service/pause", { method: "POST" });
  toast("Scheduler paused — no ticks until resumed", "info");
  refreshService();
});
$("#btn-resume").addEventListener("click", async () => {
  await api("/api/service/resume", { method: "POST" });
  toast("Scheduler resumed", "ok");
  refreshService();
});
$("#btn-runnow").addEventListener("click", async () => {
  await api("/api/service/run-now", { method: "POST", body: {} });
  toast("Fleet analysis triggered", "ok");
  refreshService();
});
$("#inp-tick").addEventListener("change", async (e) => {
  try {
    await api("/api/service/tick", { method: "PUT", body: { tick_minutes: +e.target.value } });
    toast(`Tick interval set to ${e.target.value} min`, "ok");
  } catch (ex) { toast(ex.message, "err"); }
});

// ------------------------------------------------------------ operator ----
const STATE_ORDER = { ALARM: 0, ERROR: 1, STALE: 2, OK: 3, MATURING: 4, NEW: 5, PAUSED: 6 };

function formatRulesForOperator(raw) {
  if (!raw || raw === "quiet") return '<span style="color:var(--ok)">Healthy Baseline</span>';
  const causes = [];
  if (raw.includes("sustained")) causes.push("Sustained Deviation");
  if (raw.includes("rate")) causes.push("Frequent Spikes");
  if (raw.includes("avail")) causes.push("Prolonged Offline");
  if (raw.includes("heads:")) causes.push("Recurring Pattern");
  if (causes.length === 0) return "Anomaly Detected";
  
  let txt = causes.join(", ");
  if (raw.includes("distrusted")) {
    txt = '<span style="color:var(--muted);font-style:italic;" title="Suppressed False Alarm">Suppressed Event</span>';
  } else {
    txt = `<span style="color:var(--bad)">${txt}</span>`;
  }
  return txt;
}

let cachedOperatorData = null;
async function refreshOperator(useCache = false) {
  if (!useCache || !cachedOperatorData) {
    const [fleet, sparks, alarms] = await Promise.all([
      api("/api/fleet"), api("/api/fleet/sparklines"), api("/api/alarms?unacked=true"),
    ]);
    cachedOperatorData = { fleet, sparks, alarms };
  }
  const { fleet, sparks, alarms } = cachedOperatorData;

  // KPI strip
  const n = fleet.length;
  const nAlarm = fleet.filter((a) => a.state === "ALARM").length;
  const nOk = fleet.filter((a) => a.state === "OK").length;
  const nAttn = fleet.filter((a) => ["ERROR", "STALE"].includes(a.state)).length;
  const setK = (k, v) => { $(`[data-kpi="${k}"] .kpi-num`).textContent = v; };
  setK("total", n); setK("ok", nOk); setK("alarm", nAlarm);
  setK("attention", nAttn); setK("unacked", alarms.length);
  $('[data-kpi="alarm"]').classList.toggle("lit", nAlarm > 0);

  // Group alarms
  const alarmsByAsset = {};
  for (const al of alarms) {
    if (!alarmsByAsset[al.asset_key]) alarmsByAsset[al.asset_key] = [];
    alarmsByAsset[al.asset_key].push(al);
  }

  const hourMs = 3600000;
  const renderTimeline = (alarmList, anchorTsStr) => {
    let html = '<div class="mega-timeline">';
    const nowTs = anchorTsStr ? new Date(anchorTsStr + (anchorTsStr.includes('Z') || anchorTsStr.includes('+') ? '' : 'Z')).getTime() : Date.now();
    for (let i = 23; i >= 0; i--) {
      const bStart = nowTs - (i + 1) * hourMs;
      const bEnd = nowTs - i * hourMs;
      let active = false, maxPeak = 0;
      for (const al of alarmList) {
        const alStart = new Date(al.start_ts + (al.start_ts.includes('Z') || al.start_ts.includes('+') ? '' : 'Z')).getTime();
        const alEnd = al.end_ts ? new Date(al.end_ts + (al.end_ts.includes('Z') || al.end_ts.includes('+') ? '' : 'Z')).getTime() : nowTs;
        if (alStart < bEnd && alEnd > bStart) { active = true; maxPeak = Math.max(maxPeak, al.peak_fused || 0); }
      }
      html += `<div class="mt-block ${active ? (maxPeak > 5.0 ? 'danger' : 'warn') : ''}"></div>`;
    }
    return html + '</div>';
  };

  // C5 — Extract farm prefix from asset key (e.g. FD_FAN_01 → "FD")
  const farmPrefix = (key) => {
    const parts = String(key).split("_");
    return parts.length >= 2 ? parts[0] : "–";
  };

  // C8 — Last-alarm badge from unacked alarms (most recent start)
  const lastAlarmBadge = (assetAlarms) => {
    if (!assetAlarms.length) return "";
    const latest = assetAlarms.reduce((a, b) =>
      new Date(b.start_ts) > new Date(a.start_ts) ? b : a);
    return `<span class="last-alarm-badge">⏱ ${fmtRelTime(latest.start_ts)}</span>`;
  };

  const mx = $("#mega-matrix");
  mx.innerHTML = `
    <div class="mega-hdr">
      <div>Asset / Episode</div>
      <div>Status / Start</div>
      <div>Trend / Hrs</div>
      <div>Fused / Peak</div>
      <div>Diagnosis</div>
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="mt-empty">-24h</span><span class="mt-empty">Timeline Matrix</span><span class="mt-empty">Now</span>
      </div>
      <div>Unack</div>
    </div>
  `;

  // C5 — Sort by (farm, state priority, asset_key) then group by farm
  fleet.sort((a, b) => {
    const fa = farmPrefix(a.asset_key), fb = farmPrefix(b.asset_key);
    if (fa !== fb) return fa.localeCompare(fb);
    const sd = (STATE_ORDER[a.state] ?? 9) - (STATE_ORDER[b.state] ?? 9);
    return sd || String(a.asset_key).localeCompare(String(b.asset_key));
  });

  let currentFarm = null;

  for (const a of fleet) {
    const farm = farmPrefix(a.asset_key);
    const assetAlarms = alarmsByAsset[a.asset_key] || [];
    
    // C5 — Farm group header when farm changes
    if (farm !== currentFarm) {
      currentFarm = farm;
      const farmAssets = fleet.filter(x => farmPrefix(x.asset_key) === farm);
      const farmAlarm = farmAssets.filter(x => x.state === "ALARM").length;
      const farmWarn = farmAssets.filter(x => x.state === "WARN").length;
      const farmHdr = document.createElement("div");
      farmHdr.className = "mega-farm-hdr";
      const dot = farmAlarm ? "var(--bad)" : farmWarn ? "var(--warn)" : "var(--ok)";
      farmHdr.innerHTML = `
        <span style="color:var(--brand);font-weight:700;letter-spacing:.06em;">${farm}</span>
        <span style="color:var(--muted);font-size:10px;margin-left:6px;">${farmAssets.length} assets</span>
        ${farmAlarm ? `<span style="color:var(--bad);font-size:10px;margin-left:8px;">● ${farmAlarm} alarm</span>` : ""}
        ${farmWarn ? `<span style="color:var(--warn);font-size:10px;margin-left:6px;">● ${farmWarn} warn</span>` : ""}
      `;
      mx.append(farmHdr);
    }

    // Asset Row
    const aRow = document.createElement("div");
    aRow.className = "mega-asset-row collapsed";
    aRow.innerHTML = `
      <div style="font-weight:bold; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${a.asset_key}">
        <span class="chevron" style="display:inline-block;width:14px;color:var(--muted);">${assetAlarms.length ? '►' : ' '}</span>
        ${a.asset_key}
        ${lastAlarmBadge(assetAlarms)}
      </div>
      <div id="mr-state-${a.asset_key}"></div>
      <div id="mr-sp-${a.asset_key}"></div>
      <div class="num">${fmtNum(a.last_fused)}</div>
      <div style="font-size:12px;font-family:'Share Tech Mono',monospace;">${formatRulesForOperator(a.rules_fired)}</div>
      <div>${renderTimeline(assetAlarms, a.last_ts)}</div>
      <div class="num" style="color:var(--warn); font-weight:bold;">${a.unacked_alarms || 0}</div>
    `;
    aRow.querySelector(`[id="mr-state-${a.asset_key}"]`).append(badge(a.state));
    aRow.querySelector(`[id="mr-sp-${a.asset_key}"]`).append(sparkline(sparks[a.asset_key] || []));
    aRow.addEventListener("click", (e) => {
      if (e.target.tagName !== 'BUTTON') {
        const isColl = aRow.classList.toggle('collapsed');
        const chev = aRow.querySelector('.chevron');
        if (chev && assetAlarms.length) chev.textContent = isColl ? '►' : '▼';
      }
    });
    // Add double click handler to open engineer view
    aRow.addEventListener("dblclick", () => openEngineer(a.asset_key));
    mx.append(aRow);

    // Alarm Rows
    if (assetAlarms.length > 0) {
      const alContainer = document.createElement("div");
      alContainer.className = "mega-alarms";
      for (const al of assetAlarms) {
        const alRow = document.createElement("div");
        alRow.className = "mega-alarm-row";
        alRow.innerHTML = `
          <div style="color:var(--muted);">└── Episode</div>
          <div>${fmtTs(al.start_ts)}</div>
          <div class="num">${fmtNum(al.duration_h, 1)} hrs</div>
          <div class="num">Peak: ${fmtNum(al.peak_fused)}</div>
          <div></div>
          <div>${renderTimeline([al], a.last_ts)}</div>
          <div id="mr-ack-${a.asset_key}-${al.start_ts.replace(/[: ]/g, '')}"></div>
        `;
        const btn = document.createElement("button");
        btn.className = "btn btn-sm btn-warn"; btn.textContent = "Ack";
        btn.addEventListener("click", () => ackAlarm(a.asset_key, al.start_ts));
        alRow.querySelector(`[id="mr-ack-${a.asset_key}-${al.start_ts.replace(/[: ]/g, '')}"]`).append(btn);
        alContainer.append(alRow);
      }
      mx.append(alContainer);
    }
  }

  $("#fleet-count").textContent = n ? `${n} assets` : "";
  $("#fleet-empty").classList.toggle("hidden", n > 0);

  // B3 — Fleet Health History (30-day stacked bar, Advanced mode)
  {
    const healthEl = $("#op-health-chart");
    healthEl.innerHTML = "";
    const getCssOp = v => getComputedStyle(document.body).getPropertyValue(v).trim();

    // Build per-day state counts from sparklines (fused_max thresholds)
    const dayMap = {};
    for (const [, points] of Object.entries(sparks)) {
      for (const [dayStr, fusedMax] of points) {
        if (!dayMap[dayStr]) dayMap[dayStr] = {ok: 0, warn: 0, alarm: 0};
        if (fusedMax >= 3.5) dayMap[dayStr].alarm++;
        else if (fusedMax >= 2.0) dayMap[dayStr].warn++;
        else dayMap[dayStr].ok++;
      }
    }

    const days = Object.keys(dayMap).sort().slice(-30);
    if (days.length === 0) {
      healthEl.style.cssText = "height:120px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:11px;";
      healthEl.textContent = "No history yet.";
    } else {
      const W_total = healthEl.clientWidth || 500;
      const H_bars = 90, GAP = 1;
      const barW = Math.max(3, Math.floor((W_total - 8) / days.length) - GAP);
      const W = days.length * (barW + GAP) - GAP;
      const maxN = Math.max(...days.map(d => dayMap[d].ok + dayMap[d].warn + dayMap[d].alarm), 1);
      const dpr = window.devicePixelRatio || 1;

      const cvs = document.createElement("canvas");
      cvs.width = W * dpr; cvs.height = H_bars * dpr;
      cvs.style.cssText = `width:${W}px;height:${H_bars}px;display:block;`;
      const ctx = cvs.getContext("2d");
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, W, H_bars);

      days.forEach((d, i) => {
        const {ok, warn, alarm} = dayMap[d];
        const x = i * (barW + GAP);
        let y = H_bars;
        for (const [cnt, cv] of [[ok,"--ok"],[warn,"--warn"],[alarm,"--bad"]]) {
          const bH = Math.round(cnt / maxN * H_bars);
          y -= bH;
          ctx.fillStyle = getCssOp(cv);
          ctx.globalAlpha = 0.78;
          ctx.fillRect(x, y, barW, bH);
          ctx.globalAlpha = 1;
        }
      });

      healthEl.style.cssText = "padding:6px 8px;display:block;";
      healthEl.append(cvs);
      const leg = document.createElement("div");
      leg.style.cssText = "display:flex;justify-content:space-between;font-size:9px;color:var(--muted);font-family:'Share Tech Mono',monospace;margin-top:3px;";
      leg.innerHTML = `<span>${days[0]}</span>
        <span style="display:flex;gap:8px;">
          <span style="color:var(--ok)">■ ok</span>
          <span style="color:var(--warn)">■ warn</span>
          <span style="color:var(--bad)">■ alarm</span>
        </span>
        <span>${days[days.length - 1]}</span>`;
      healthEl.append(leg);
    }
  }

  // B2 — Top Alarm Causes fleet-wide (Advanced mode, op-causes card)
  {
    const causesBody = $("#op-causes-body");
    const CAUSES = [
      { key: "Sustained Deviation", test: r => r?.includes("sustained") },
      { key: "Frequent Spikes",     test: r => r?.includes("rate") },
      { key: "Prolonged Offline",   test: r => r?.includes("avail") },
      { key: "Recurring Pattern",   test: r => r?.includes("heads:") },
    ];
    const counts = {};
    CAUSES.forEach(c => { counts[c.key] = 0; });
    counts["Other Anomaly"] = 0;

    for (const a of fleet) {
      const raw = a.rules_fired;
      if (!raw || raw === "quiet") continue;
      let matched = false;
      for (const c of CAUSES) {
        if (c.test(raw)) { counts[c.key]++; matched = true; }
      }
      if (!matched) counts["Other Anomaly"]++;
    }

    const sorted = Object.entries(counts)
      .filter(([, cnt]) => cnt > 0)
      .sort(([, a], [, b]) => b - a);

    if (sorted.length === 0) {
      causesBody.innerHTML = `<span style="color:var(--ok)">✓ No active alarm causes</span>`;
    } else {
      const maxCnt = sorted[0][1];
      causesBody.style.padding = "8px";
      causesBody.innerHTML = sorted.map(([cause, cnt]) => {
        const pct = fleet.length > 0 ? Math.round(cnt / fleet.length * 100) : 0;
        const barW = Math.round(cnt / maxCnt * 100);
        return `<div style="margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
            <span style="font-size:11px;color:var(--ink);">${cause}</span>
            <span style="font-size:9px;color:var(--muted);font-family:'Share Tech Mono',monospace;">${cnt}&nbsp;assets&nbsp;(${pct}%)</span>
          </div>
          <div style="background:var(--bg);height:5px;border-radius:2px;">
            <div style="background:var(--bad);width:${barW}%;height:100%;border-radius:2px;opacity:.75;transition:width .3s;"></div>
          </div>
        </div>`;
      }).join("");
    }
  }
}

function ackAlarm(assetKey, startTs) {
  openModal(`Acknowledge alarm — ${assetKey}`, [
    { name: "ack_by", label: "Acknowledged by", required: true },
    { name: "note", label: "Note (what was found / done)" },
  ], "Acknowledge", async (body) => {
    await api("/api/alarms/ack", { method: "POST",
      body: { asset_key: assetKey, start_ts: startTs, ...body } });
    toast("Alarm acknowledged", "ok");
    refresh();
  });
}

// ------------------------------------------------------------ engineer ----
let plot = null;
let selectedAsset = null;

function openEngineer(assetKey) {
  selectedAsset = assetKey;
  document.querySelector('[data-tab="engineer"]').click();
}

async function fillAssetSelectors() {
  const fleet = await api("/api/fleet");
  const keys = fleet.map((a) => a.asset_key).sort();
  for (const sel of [$("#eng-asset"), $("#adm-runs-asset")]) {
    const cur = sel.value;
    sel.replaceChildren(...keys.map((k) => new Option(k, k)));
    sel.value = keys.includes(selectedAsset) ? selectedAsset
              : keys.includes(cur) ? cur : keys[0] || "";
  }
  if (!selectedAsset) selectedAsset = $("#eng-asset").value;
}

function hexToRgb(h) {
  h = h.trim();
  if (h.startsWith("rgba")) {
    const parts = h.match(/[\d.]+/g);
    return [parseInt(parts[0]), parseInt(parts[1]), parseInt(parts[2])];
  }
  if (h.startsWith("rgb")) {
    const parts = h.match(/\d+/g);
    return [parseInt(parts[0]), parseInt(parts[1]), parseInt(parts[2])];
  }
  if (h.startsWith("#")) {
    let c = h.substring(1);
    if (c.length === 3) c = c.split('').map(x => x + x).join('');
    const num = parseInt(c, 16);
    return [num >> 16, (num >> 8) & 255, num & 255];
  }
  return [0, 0, 0];
}

function interp(c1, c2, t) {
  return [
    Math.round(c1[0] + (c2[0] - c1[0]) * t),
    Math.round(c1[1] + (c2[1] - c1[1]) * t),
    Math.round(c1[2] + (c2[2] - c1[2]) * t)
  ];
}

let currentTheme = null;
let currentPalette = [];

function updateHeatPalette() {
  const getCss = (v) => getComputedStyle(document.body).getPropertyValue(v).trim();
  const bg = hexToRgb(getCss('--bg2') || getCss('--bg'));
  const ok = hexToRgb(getCss('--blue'));
  const warn = hexToRgb(getCss('--warn'));
  const bad = hexToRgb(getCss('--bad'));
  
  // Create a 20-step palette
  currentPalette = [];
  for (let i = 0; i <= 20; i++) {
    const z = (i / 20) * 8; // map 0..20 to 0..8
    let c;
    if (z <= 2) {
      c = interp(bg, ok, z / 2);
    } else if (z <= 4) {
      c = interp(ok, warn, (z - 2) / 2);
    } else {
      c = interp(warn, bad, Math.min(1, (z - 4) / 4));
    }
    currentPalette.push(`rgb(${c.join(',')})`);
  }
  currentTheme = document.documentElement.dataset.theme;
}

function heatColor(z) {
  if (currentTheme !== document.documentElement.dataset.theme) updateHeatPalette();
  const t = Math.max(0, Math.min(1, z / 8));
  return currentPalette[Math.round(t * (currentPalette.length - 1))];
}

let cachedEngineerData = null;
async function refreshEngineer(useCache = false) {
  await fillAssetSelectors();
  const key = $("#eng-asset").value;
  if (!key) return;
  selectedAsset = key;
  const days = +$("#eng-days").value;
  
  if (!useCache || !cachedEngineerData || cachedEngineerData.key !== key || cachedEngineerData.days !== days) {
    const [s, meta, eps, daily, runs] = await Promise.all([
      api(`/api/assets/${key}/series?days=${days}`),
      api(`/api/assets/${key}`),
      api(`/api/assets/${key}/alarms`),
      api(`/api/assets/${key}/daily`),
      api(`/api/assets/${key}/runs?limit=1`),
    ]);
    cachedEngineerData = { key, days, s, meta, eps, daily, runs };
  }
  const { s, meta, eps, daily, runs } = cachedEngineerData;
  const idx = Object.fromEntries(s.columns.map((c, i) => [c, i]));
  const ts = s.rows.map((r) => new Date(String(r[idx.ts]).replace(" ", "T")).getTime() / 1000);
  const fused = s.rows.map((r) => r[idx.fused]);
  const alarm = s.rows.map((r) => r[idx.alarm]);
  const alertZ = meta.asset.alert_z;

  // status chips
  const chips = $("#eng-chips");
  chips.replaceChildren();
  const chip = (label, value) => {
    const c = document.createElement("span");
    c.className = "chip";
    c.innerHTML = `${label} <b>${value}</b>`;
    chips.append(c);
  };
  chip("state", meta.monitored?.state || meta.asset.verdict || "—");
  chip("alert_z", fmtNum(alertZ));
  chip("persist", meta.asset.persist ?? "—");
  chip("rules", meta.asset.rules_fired || "quiet");
  chip("points", `${s.rows.length}${s.stride > 1 ? ` (1/${s.stride})` : ""}`);

  // culprit banner from the latest run's notes (A4)
  const notes = runs[0]?.notes || "";
  const culprits = notes.startsWith("culprits: ") ? notes.slice(10) : null;
  $("#eng-culprits").classList.toggle("hidden", !culprits);
  if (culprits) {
    // Parse culprits string (e.g., "AR1, GMM, IForest") into detector names with colors
    const detectorMap = {
      "AR1": { color: getCss("--det-ar1"), name: "AR1" },
      "SPE": { color: getCss("--det-pca-spe"), name: "PCA-SPE" },
      "T2": { color: getCss("--det-pca-t2"), name: "PCA-T²" },
      "IForest": { color: getCss("--det-iforest"), name: "IForest" },
      "GMM": { color: getCss("--det-gmm"), name: "GMM" },
      "OMR": { color: getCss("--det-omr"), name: "OMR" },
    };

    // Parse detectors from culprits string
    const detList = culprits.split(/[,;]/g).map(s => s.trim()).filter(s => s);
    let chipsHtml = `<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">`;
    chipsHtml += `<span style="font-size:11px;color:var(--muted);">⚠ Drivers:</span>`;

    for (const det of detList) {
      const key = Object.keys(detectorMap).find(k => det.includes(k) || k === det);
      if (key) {
        const info = detectorMap[key];
        chipsHtml += `<span style="background:${info.color};color:#000;padding:2px 6px;border-radius:2px;font-size:10px;font-weight:600;">${info.name}</span>`;
      }
    }
    chipsHtml += `<span style="font-size:9px;color:var(--muted);margin-left:4px;">OMR attribution</span>`;
    chipsHtml += `</div>`;

    $("#eng-culprits").innerHTML = chipsHtml;
  }

  // fused chart with alarm shading
  const width = $("#eng-chart").clientWidth || 980;
  const cv = $("#eng-heatmap");
  cv.width = Math.max(100, width - 72);
  const rowH = cv.height / Z_COLS.length;
  const ctx = cv.getContext("2d");

  let currentI0 = 0;
  let currentI1 = s.rows.length - 1;

  const renderHeatmap = () => {
    ctx.clearRect(0, 0, cv.width, cv.height);
    const np = currentI1 - currentI0 + 1;
    if (np <= 0) return;
    const colW = cv.width / np;
    Z_COLS.forEach((z, zi) => {
      for (let j = 0; j < np; j++) {
        const v = s.rows[currentI0 + j][idx[z]];
        ctx.fillStyle = v == null ? getCss("--bg") : heatColor(v);
        ctx.fillRect(j * colW, zi * rowH, colW + 0.6, rowH - 1.5);
      }
    });
  };

  const getCss = (v) => getComputedStyle(document.body).getPropertyValue(v).trim();
  // Build detector series for Advanced mode
  const detectorSeries = [
    { label: "AR1", stroke: getCss("--det-ar1"), width: 1, points: { show: false }, value: (u, v) => fmtNum(v) },
    { label: "PCA-SPE", stroke: getCss("--det-pca-spe"), width: 1, points: { show: false }, value: (u, v) => fmtNum(v) },
    { label: "PCA-T2", stroke: getCss("--det-pca-t2"), width: 1, points: { show: false }, value: (u, v) => fmtNum(v) },
    { label: "IForest", stroke: getCss("--det-iforest"), width: 1, points: { show: false }, value: (u, v) => fmtNum(v) },
    { label: "GMM", stroke: getCss("--det-gmm"), width: 1, points: { show: false }, value: (u, v) => fmtNum(v) },
    { label: "OMR", stroke: getCss("--det-omr"), width: 1, points: { show: false }, value: (u, v) => fmtNum(v) },
  ];

  if (plot) plot.destroy();
  plot = new uPlot({
    width, height: 200,
    cursor: { y: false },
    series: [
      {},
      { label: "fused z", stroke: getCss("--chart-score"), width: 2,
        fill: getCss("--chart-score-fill"), value: (u, v) => fmtNum(v) },
      { label: "alert_z", stroke: getCss("--chart-alert"), dash: [5, 5], width: 1.5,
        points: { show: false }, value: (u, v) => fmtNum(v) },
      ...detectorSeries,
    ],
    axes: [
      { 
        stroke: getComputedStyle(document.body).getPropertyValue('--muted').trim(), 
        grid: { show: false }, 
        ticks: { stroke: getComputedStyle(document.body).getPropertyValue('--line').trim() } 
      },
      { 
        stroke: getComputedStyle(document.body).getPropertyValue('--muted').trim(), 
        grid: { stroke: getComputedStyle(document.body).getPropertyValue('--line').trim(), width: 1 }, 
        ticks: { show: false } 
      },
    ],
    hooks: {
      setScale: [(u, key) => {
        if (key === "x") {
          const minT = u.scales.x.min;
          const maxT = u.scales.x.max;
          let i0 = ts.findIndex(t => t >= minT);
          if (i0 === -1) i0 = 0;
          let i1 = ts.length - 1;
          for (let k = ts.length - 1; k >= 0; k--) {
            if (ts[k] <= maxT) { i1 = k; break; }
          }
          if (i1 < i0) i1 = i0;
          currentI0 = i0;
          currentI1 = i1;
          renderHeatmap();
        }
      }],
      draw: [(u) => {   // alarm shading
        const ctx = u.ctx;
        ctx.save();
        ctx.fillStyle = getCss("--chart-alarm-fill");
        let start = null;
        for (let i = 0; i <= alarm.length; i++) {
          const on = i < alarm.length && alarm[i];
          if (on && start === null) start = i;
          if (!on && start !== null) {
            const x0 = u.valToPos(ts[start], "x", true);
            const x1 = u.valToPos(ts[Math.max(i - 1, start)], "x", true);
            ctx.fillRect(x0, u.bbox.top, Math.max(x1 - x0, 2), u.bbox.height);
            start = null;
          }
        }
        ctx.restore();
      }],
    },
  }, [
    ts,
    fused,
    fused.map(() => alertZ),
    s.rows.map(r => r[idx["ar1_z"]]),
    s.rows.map(r => r[idx["pca_spe_z"]]),
    s.rows.map(r => r[idx["pca_t2_z"]]),
    s.rows.map(r => r[idx["iforest_z"]]),
    s.rows.map(r => r[idx["gmm_z"]]),
    s.rows.map(r => r[idx["omr_z"]]),
  ], $("#eng-chart"));

  // Detector toggle buttons (Advanced mode only)
  document.querySelectorAll(".det-toggle").forEach((btn, i) => {
    const seriesIdx = 3 + i; // Series 0=x, 1=fused, 2=alertZ, 3-8=detectors
    btn.addEventListener("click", () => {
      btn.classList.toggle("active");
      // Toggle series visibility
      const show = btn.classList.contains("active");
      plot.setSeries(seriesIdx, { show });
    });
  });

  // detector heat strip, aligned to the chart's plotted area
  const labels = $("#eng-heatlabels");
  labels.replaceChildren(...Z_LABELS.map((l) => {
    const d = document.createElement("div"); d.textContent = l; return d;
  }));

  const tooltip = $("#eng-heat-tooltip");
  cv.onmousemove = (e) => {
    const rect = cv.getBoundingClientRect();
    const np = currentI1 - currentI0 + 1;
    const colW = cv.width / np;
    const j = Math.floor((e.clientX - rect.left) / colW);
    const zi = Math.floor((e.clientY - rect.top) / rowH);
    if (j >= 0 && j < np && zi >= 0 && zi < Z_COLS.length) {
      const i = currentI0 + j;
      const zVal = s.rows[i][idx[Z_COLS[zi]]];
      tooltip.innerHTML = `
        <div style="color:var(--muted); margin-bottom:4px;">${fmtTs(ts[i] * 1000)}</div>
        <div><strong style="color:var(--brand)">${Z_LABELS[zi]}</strong> : ${zVal != null ? zVal.toFixed(2) : "—"}</div>
      `;
      tooltip.style.left = e.clientX + "px";
      tooltip.style.top = e.clientY + "px";
      tooltip.classList.remove("hidden");
    } else {
      tooltip.classList.add("hidden");
    }
  };
  cv.onmouseleave = () => tooltip.classList.add("hidden");

  // C9 — State-change lane (Advanced mode only)
  {
    const sl = $("#eng-statelane");
    const slLabel = $("#eng-statelabels");
    sl.width = Math.max(100, width - 72);
    const slCtx = sl.getContext("2d");
    slCtx.clearRect(0, 0, sl.width, sl.height);
    const slColW = sl.width / (ts.length || 1);
    for (let i = 0; i < ts.length; i++) {
      const alm = alarm[i];
      const z = fused[i];
      if (alm) slCtx.fillStyle = getCss("--bad");
      else if (z != null && z >= 2.0) slCtx.fillStyle = getCss("--warn");
      else slCtx.fillStyle = getCss("--ok");
      slCtx.globalAlpha = alm ? 0.85 : 0.45;
      slCtx.fillRect(i * slColW, 0, slColW + 0.5, sl.height);
    }
    slCtx.globalAlpha = 1;
    slLabel.innerHTML = `<div style="font-size:8px;color:var(--muted);font-family:'Barlow Condensed',sans-serif;line-height:14px;">state</div>`;
  }

  // A3 — Build per-episode detector max z from series data (Advanced mode)
  const DET_VARS = ["ar1_z", "pca_spe_z", "pca_t2_z", "iforest_z", "gmm_z", "omr_z"];
  const DET_NAMES = ["AR1", "SPE", "T2", "IF", "GMM", "OMR"];
  const DET_VARS_CSS = ["--det-ar1", "--det-pca-spe", "--det-pca-t2", "--det-iforest", "--det-gmm", "--det-omr"];

  const episodeDetContrib = (ep) => {
    const epStart = new Date(ep.start_ts.replace(" ", "T")).getTime() / 1000;
    const epEnd = ep.end_ts ? new Date(ep.end_ts.replace(" ", "T")).getTime() / 1000 : ts[ts.length - 1];
    const maxZ = DET_VARS.map(col => {
      let mx = 0;
      for (let i = 0; i < ts.length; i++) {
        if (ts[i] >= epStart && ts[i] <= epEnd) {
          const v = s.rows[i][idx[col]];
          if (v != null && v > mx) mx = v;
        }
      }
      return mx;
    });
    return maxZ;
  };

  // alarm episodes
  const eb = $("#eng-episodes tbody");
  eb.replaceChildren();
  for (const e of eps.slice(0, 30)) {
    const detMaxZ = episodeDetContrib(e);
    const overallMax = Math.max(...detMaxZ, 1);
    const topIdx = detMaxZ.indexOf(Math.max(...detMaxZ));

    // Build detector strip (A3)
    const stripTd = document.createElement("td");
    stripTd.className = "adv";
    const strip = document.createElement("div");
    strip.className = "cause-strip";
    DET_VARS_CSS.forEach((cssVar, i) => {
      const cell = document.createElement("div");
      const intensity = Math.min(1, detMaxZ[i] / overallMax);
      const alpha = 0.15 + intensity * 0.85;
      cell.className = "cause-cell";
      cell.style.background = getCss(cssVar);
      cell.style.opacity = alpha.toFixed(2);
      cell.title = `${DET_NAMES[i]}: ${fmtNum(detMaxZ[i])}`;
      strip.append(cell);
    });
    stripTd.append(strip);

    // Top detector (A3 dominant)
    const topTd = document.createElement("td");
    topTd.className = "adv";
    if (detMaxZ[topIdx] > 1) {
      topTd.innerHTML = `<span style="color:${getCss(DET_VARS_CSS[topIdx])};font-size:10px;font-weight:600;">${DET_NAMES[topIdx]}</span>`;
    } else {
      topTd.innerHTML = `<span style="color:var(--muted);font-size:10px;">—</span>`;
    }

    const tr = document.createElement("tr");
    tr.append(td(fmtTs(e.start_ts)), td(fmtTs(e.end_ts)),
              tdNum(fmtNum(e.duration_h, 1)), tdNum(fmtNum(e.peak_fused)),
              stripTd, topTd);
    const cell = td("");
    if (e.ack_at) {
      cell.textContent = `✓ ${e.ack_by}`;
      cell.title = `${fmtTs(e.ack_at)} — ${e.ack_note || ""}`;
    } else {
      const btn = document.createElement("button");
      btn.className = "btn btn-sm btn-warn";
      btn.textContent = "Ack";
      btn.addEventListener("click", () => ackAlarm(key, e.start_ts));
      cell.append(btn);
    }
    tr.append(cell);
    eb.append(tr);
  }
  $("#eng-eps-empty").classList.toggle("hidden", eps.length > 0);

  // daily stats
  const db = $("#eng-daily tbody");
  db.replaceChildren();
  
  const todayStr = new Date().toISOString().split('T')[0];
  const yesterday = new Date(Date.now() - 86400000);
  const yesterdayStr = yesterday.toISOString().split('T')[0];
  
  function formatDayStr(ds) {
    if (ds === todayStr) return "<b>Today</b>";
    if (ds === yesterdayStr) return "<b>Yesterday</b>";
    const dt = new Date(ds);
    const utcDate = new Date(dt.getTime() + dt.getTimezoneOffset() * 60000);
    return utcDate.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  }

  const sliced = daily.slice(0, 21);
  for (let i = 0; i < sliced.length; i++) {
    const d = sliced[i];
    const prev = daily[i + 1];
    
    let fMaxColor = "ok";
    if (d.fused_max >= 2.5) fMaxColor = "warn";
    if (d.fused_max >= 3.0) fMaxColor = "bad";
    
    let fMaxDelta = "";
    if (prev && prev.fused_max != null) {
       const diff = d.fused_max - prev.fused_max;
       if (diff > 0.1) fMaxDelta = `<span class="delta-up">↑ ${diff.toFixed(2)}</span>`;
       else if (diff < -0.1) fMaxDelta = `<span class="delta-down">↓ ${Math.abs(diff).toFixed(2)}</span>`;
    }
    const fMaxHtml = renderGaugeHtml(fmtNum(d.fused_max), d.fused_max / 5.0, fMaxColor, fMaxDelta);
    
    const rateColor = d.rate_z3 > 0.05 ? "bad" : (d.rate_z3 > 0 ? "warn" : "ok");
    let rateDelta = "";
    if (prev && prev.rate_z3 != null && d.rate_z3 > 0) {
       const diff = d.rate_z3 - prev.rate_z3;
       if (diff > 0.01) rateDelta = `<span class="delta-up">↑ ${(diff*100).toFixed(1)}%</span>`;
       else if (diff < -0.01) rateDelta = `<span class="delta-down">↓ ${(Math.abs(diff)*100).toFixed(1)}%</span>`;
    }
    
    let rateHtml;
    if (d.rate_z3 === 0) {
      rateHtml = `<span class="muted">—</span>`;
    } else {
      rateHtml = `<span style="font-weight:bold; color:var(--${rateColor})">${(d.rate_z3 * 100).toFixed(1)}%</span>`;
      if (rateDelta) rateHtml += ` <span style="margin-left: 8px">${rateDelta}</span>`;
    }
    
    let alarmHtml = d.alarm_samples.toString();
    if (d.alarm_samples === 0) alarmHtml = `<span class="muted">0</span>`;
    else alarmHtml = `<span class="badge ALARM">${d.alarm_samples}</span>`;
    
    const availColor = d.availability >= 0.99 ? "ok" : (d.availability >= 0.90 ? "warn" : "bad");
    let availHtml;
    if (d.availability == null) availHtml = "—";
    else if (d.availability === 0) availHtml = `<span class="badge ALARM">OFFLINE</span>`;
    else availHtml = `<span style="color:var(--${availColor}); font-weight:bold">${(d.availability * 100).toFixed(0)}%</span>`;

    const tr = document.createElement("tr");
    if (d.alarm_samples > 0) tr.className = "row-alarm";
    
    // C7 — fused_mean and sample count (Advanced mode, .adv td)
    const meanColor = (d.fused_mean ?? 0) >= 2.5 ? "warn" : "muted";
    const meanTd = tdHtml(d.fused_mean != null
      ? `<span style="color:var(--${meanColor})">${fmtNum(d.fused_mean)}</span>` : "—", "adv num");
    const nTd = tdHtml(d.n != null
      ? `<span style="color:var(--muted);font-size:9px;">${d.n}</span>` : "—", "adv num");

    tr.append(
      tdHtml(formatDayStr(d.day)),
      tdHtml(fMaxHtml, "num"),
      meanTd,
      tdHtml(rateHtml, "num"),
      tdHtml(alarmHtml, "num"),
      tdHtml(availHtml, "num"),
      nTd
    );
    db.append(tr);
  }

  // C2 — Availability trend sparkline (Advanced mode, above daily table)
  {
    const availEl = $("#eng-avail-chart");
    availEl.innerHTML = "";
    const availDays = daily.filter(d => d.availability != null).slice(0, 30).reverse();
    if (availDays.length < 2) {
      availEl.style.cssText = "padding:4px 8px 0;height:48px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:10px;";
      availEl.textContent = "No availability data yet.";
    } else {
      const W_a = availEl.parentElement?.clientWidth || 400;
      const H_a = 40, GAP_a = 1;
      const barW_a = Math.max(3, Math.floor((W_a - 16) / availDays.length) - GAP_a);
      const W_cv = availDays.length * (barW_a + GAP_a) - GAP_a;
      const dpr_a = window.devicePixelRatio || 1;
      const cvs_a = document.createElement("canvas");
      cvs_a.width = W_cv * dpr_a; cvs_a.height = H_a * dpr_a;
      cvs_a.style.cssText = `width:${W_cv}px;height:${H_a}px;display:block;`;
      const ctx_a = cvs_a.getContext("2d");
      ctx_a.scale(dpr_a, dpr_a);
      ctx_a.clearRect(0, 0, W_cv, H_a);
      availDays.forEach((d, i) => {
        const av = d.availability ?? 1;
        const bH = Math.max(2, Math.round(av * H_a));
        const x = i * (barW_a + GAP_a);
        const y = H_a - bH;
        ctx_a.fillStyle = av >= 0.99 ? getCss("--ok") : av >= 0.90 ? getCss("--warn") : getCss("--bad");
        ctx_a.globalAlpha = 0.75;
        ctx_a.fillRect(x, y, barW_a, bH);
        ctx_a.globalAlpha = 1;
      });
      availEl.style.cssText = "padding:4px 8px 2px;display:flex;flex-direction:column;gap:2px;";
      const label_a = document.createElement("div");
      label_a.style.cssText = "font-size:8px;color:var(--muted);font-family:'Barlow Condensed',sans-serif;letter-spacing:.06em;text-transform:uppercase;";
      label_a.textContent = "Availability Trend";
      availEl.append(label_a, cvs_a);
    }
  }

  // MTTD / MTTR tiles (B5)
  const mttdBody = $("#eng-mttd-body");
  if (eps.length === 0) {
    mttdBody.innerHTML = `<div style="color:var(--muted);font-size:11px;">No alarm episodes.</div>`;
  } else {
    const durations = eps.map(e => e.duration_h).filter(d => d != null);
    const mttr = durations.length > 0 ? durations.reduce((a, b) => a + b, 0) / durations.length : 0;
    // MTTD estimated as ~30-40% of MTTR (time to detection vs resolution)
    const mttd = mttr * 0.35;
    const longest = Math.max(...durations);
    const unacked = eps.filter(e => !e.ack_at).length;

    const renderKpiTile = (label, value, unit, color = "") => `
      <div class="kpi-tile" style="text-align:center;padding:8px;border:1px solid var(--line);border-radius:4px;min-width:80px;">
        <div style="font-size:9px;color:var(--muted);margin-bottom:4px;font-weight:600;text-transform:uppercase;">${label}</div>
        <div style="font-size:20px;font-weight:700;${color ? `color:var(--${color});` : ''}margin-bottom:3px;">${value}</div>
        <div style="font-size:9px;color:var(--muted);">${unit}</div>
      </div>
    `;

    mttdBody.innerHTML = `
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        ${renderKpiTile("MTTD", fmtNum(mttd, 1), "hours", "blue")}
        ${renderKpiTile("MTTR", fmtNum(mttr, 1), "hours", "warn")}
        ${renderKpiTile("Episodes", eps.length, unacked > 0 ? `${unacked} unacked` : "all acked", "")}
        ${renderKpiTile("Longest", fmtNum(longest, 1), "hours", "bad")}
      </div>
    `;
  }

  // C4 — Alarm duration histogram (Advanced mode only)
  {
    const histBody = $("#eng-histogram-body");
    histBody.innerHTML = "";
    histBody.style.padding = "8px";
    histBody.style.display = "block";

    const durations = eps.map(e => e.duration_h).filter(d => d != null && d > 0);
    if (durations.length === 0) {
      histBody.innerHTML = `<span style="color:var(--muted);font-size:11px;">No alarm episodes.</span>`;
    } else {
      // Bin into buckets: 0-2h, 2-4h, 4-8h, 8-16h, 16-32h, 32h+
      const BINS = [0, 2, 4, 8, 16, 32, Infinity];
      const BIN_LABELS = ["0-2h", "2-4h", "4-8h", "8-16h", "16-32h", "32h+"];
      const binCounts = new Array(BIN_LABELS.length).fill(0);
      for (const d of durations) {
        for (let b = 0; b < BINS.length - 1; b++) {
          if (d >= BINS[b] && d < BINS[b + 1]) { binCounts[b]++; break; }
        }
      }

      const maxCount = Math.max(...binCounts, 1);
      const BAR_H = 80, BAR_W = 32, GAP = 6, LABEL_H = 18;
      const W = BIN_LABELS.length * (BAR_W + GAP) - GAP;
      const H = BAR_H + LABEL_H + 4;
      const dpr = window.devicePixelRatio || 1;

      const cvs = document.createElement("canvas");
      cvs.width = W * dpr; cvs.height = H * dpr;
      cvs.style.width = W + "px"; cvs.style.height = H + "px";
      const ctx = cvs.getContext("2d");
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, W, H);

      binCounts.forEach((cnt, b) => {
        const barH = Math.round((cnt / maxCount) * BAR_H);
        const x = b * (BAR_W + GAP);
        const y = BAR_H - barH;
        // Color by severity: short=ok, medium=warn, long=bad
        const color = b <= 1 ? getCss("--ok") : b <= 3 ? getCss("--warn") : getCss("--bad");
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.85;
        ctx.fillRect(x, y, BAR_W, barH);
        ctx.globalAlpha = 1;

        // Count label
        if (cnt > 0) {
          ctx.fillStyle = getCss("--ink");
          ctx.font = `bold ${Math.round(9 * dpr) / dpr}px "Share Tech Mono", monospace`;
          ctx.textAlign = "center";
          ctx.fillText(cnt, x + BAR_W / 2, y - 3);
        }

        // Bin label
        ctx.fillStyle = getCss("--muted");
        ctx.font = `${Math.round(8 * dpr) / dpr}px "Barlow Condensed", sans-serif`;
        ctx.textAlign = "center";
        ctx.fillText(BIN_LABELS[b], x + BAR_W / 2, BAR_H + LABEL_H - 2);
      });

      histBody.append(cvs);
      const note = document.createElement("div");
      note.style.cssText = "font-size:9px;color:var(--muted);margin-top:6px;font-family:'Share Tech Mono',monospace;";
      note.textContent = `${durations.length} episodes · median ${fmtNum(durations.sort((a,b)=>a-b)[Math.floor(durations.length/2)], 1)}h`;
      histBody.append(note);
    }
  }

  // B6 — Co-firing matrix (Advanced mode only)
  {
    const coBody = $("#eng-cofiring-body");
    coBody.innerHTML = "";

    // Count co-fires across all alarm samples in series
    const N6 = 6;
    const THRESH = 2.0; // z ≥ 2 = "active"
    const counts = Array.from({length: N6}, () => new Array(N6).fill(0));
    const selfCounts = new Array(N6).fill(0);

    for (let i = 0; i < s.rows.length; i++) {
      if (!s.rows[i][idx.alarm]) continue; // only alarm samples
      const active = DET_VARS.map(col => (s.rows[i][idx[col]] ?? 0) >= THRESH);
      for (let r = 0; r < N6; r++) {
        if (!active[r]) continue;
        selfCounts[r]++;
        for (let c = 0; c < N6; c++) {
          if (active[c]) counts[r][c]++;
        }
      }
    }

    const totalAlarmSamples = s.rows.filter(r => r[idx.alarm]).length;
    if (totalAlarmSamples === 0) {
      coBody.innerHTML = `<span style="color:var(--muted);font-size:11px;">No alarm data.</span>`;
    } else {
      // Normalize: freq[r][c] = pct of r's active samples when c also active
      const freq = counts.map((row, r) =>
        row.map(v => selfCounts[r] > 0 ? v / selfCounts[r] : 0)
      );

      const CELL = 28, GAP = 2;
      const LABEL = 32; // left label width
      const W = LABEL + N6 * (CELL + GAP) - GAP;
      const H = LABEL + N6 * (CELL + GAP) - GAP;
      const dpr = window.devicePixelRatio || 1;

      const cvs = document.createElement("canvas");
      cvs.width = W * dpr; cvs.height = H * dpr;
      cvs.style.width = W + "px"; cvs.style.height = H + "px";
      cvs.style.imageRendering = "pixelated";
      const ctx = cvs.getContext("2d");
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, W, H);

      // Column labels (top)
      ctx.font = `bold ${Math.round(7 * dpr) / dpr}px "Barlow Condensed", sans-serif`;
      ctx.textAlign = "center";
      DET_NAMES.forEach((name, c) => {
        ctx.fillStyle = getCss(DET_VARS_CSS[c]);
        ctx.fillText(name, LABEL + c * (CELL + GAP) + CELL / 2, LABEL - 4);
      });

      // Row labels (left) + cells
      DET_NAMES.forEach((name, r) => {
        // Row label
        ctx.fillStyle = getCss(DET_VARS_CSS[r]);
        ctx.textAlign = "right";
        ctx.fillText(name, LABEL - 4, LABEL + r * (CELL + GAP) + CELL / 2 + 3);

        DET_NAMES.forEach((_, c) => {
          const v = freq[r][c];
          const x = LABEL + c * (CELL + GAP);
          const y = LABEL + r * (CELL + GAP);

          // Cell background via heatColor
          ctx.fillStyle = r === c
            ? getCss("--blue-lo")
            : heatColor(v * 10);
          ctx.fillRect(x, y, CELL, CELL);

          // Percent text
          const pct = Math.round(v * 100);
          ctx.fillStyle = v > 0.5 ? getCss("--bg") : getCss("--ink2");
          ctx.textAlign = "center";
          ctx.fillText(pct > 0 ? `${pct}%` : "—", x + CELL / 2, y + CELL / 2 + 3);
        });
      });

      coBody.style.padding = "8px";
      coBody.style.display = "flex";
      coBody.style.flexDirection = "column";
      coBody.style.gap = "6px";
      coBody.append(cvs);
      const note = document.createElement("div");
      note.style.cssText = "font-size:9px;color:var(--muted);font-family:'Share Tech Mono',monospace;";
      note.textContent = `Based on ${totalAlarmSamples} alarm samples · threshold z≥${THRESH}`;
      coBody.append(note);
    }
  }

  // B4 — Alarm Pattern Day × Hour Heatmap (Advanced mode, eng-pattern div)
  {
    const patBody = $("#eng-pattern-body");
    patBody.innerHTML = "";

    // Accumulate per (day_of_week, hour) totals and alarm counts
    const totalCnt = Array.from({length: 7}, () => new Array(24).fill(0));
    const alarmCnt = Array.from({length: 7}, () => new Array(24).fill(0));
    for (let i = 0; i < ts.length; i++) {
      const date = new Date(ts[i] * 1000);
      const dow = (date.getDay() + 6) % 7; // 0=Mon … 6=Sun
      const hr = date.getHours();
      totalCnt[dow][hr]++;
      if (alarm[i]) alarmCnt[dow][hr]++;
    }

    const DAY_LABELS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
    const dpr = window.devicePixelRatio || 1;
    const containerW = patBody.parentElement?.clientWidth || 320;
    const LABEL_W = 30, LABEL_H = 16, GAP = 1;
    const CELL_W = Math.max(8, Math.floor((containerW - LABEL_W - 12) / 24));
    const CELL_H = 20;
    const W = LABEL_W + 24 * (CELL_W + GAP) - GAP;
    const H = LABEL_H + 7 * (CELL_H + GAP) - GAP;

    const cvs = document.createElement("canvas");
    cvs.width = W * dpr; cvs.height = H * dpr;
    cvs.style.width = W + "px"; cvs.style.height = H + "px";
    const ctx2 = cvs.getContext("2d");
    ctx2.scale(dpr, dpr);
    ctx2.clearRect(0, 0, W, H);

    // Hour axis labels: 0 3 6 9 12 15 18 21
    ctx2.fillStyle = getCss("--muted");
    ctx2.font = `${8}px "Barlow Condensed", sans-serif`;
    ctx2.textAlign = "center";
    for (let h = 0; h < 24; h += 3) {
      const x = LABEL_W + h * (CELL_W + GAP) + CELL_W / 2;
      ctx2.fillText(h, x, LABEL_H - 2);
    }

    // Rows: days
    DAY_LABELS.forEach((lbl, r) => {
      const y = LABEL_H + r * (CELL_H + GAP);
      ctx2.fillStyle = getCss("--muted");
      ctx2.textAlign = "right";
      ctx2.font = `${8}px "Barlow Condensed", sans-serif`;
      ctx2.fillText(lbl, LABEL_W - 4, y + CELL_H / 2 + 3);

      for (let h = 0; h < 24; h++) {
        const tot = totalCnt[r][h];
        const al = alarmCnt[r][h];
        const frac = tot > 0 ? al / tot : 0;
        const x = LABEL_W + h * (CELL_W + GAP);
        ctx2.fillStyle = tot === 0 ? getCss("--bg3") : heatColor(frac * 8);
        ctx2.fillRect(x, y, CELL_W, CELL_H);
        if (al > 0 && CELL_W >= 12) {
          ctx2.fillStyle = frac > 0.5 ? getCss("--bg") : getCss("--ink2");
          ctx2.font = `${7}px "Share Tech Mono", monospace`;
          ctx2.textAlign = "center";
          ctx2.fillText(al, x + CELL_W / 2, y + CELL_H / 2 + 2.5);
        }
      }
    });

    patBody.style.cssText = "padding:8px;display:block;";
    patBody.append(cvs);
    const totalAlarmPts = alarm.reduce((acc, v) => acc + (v ? 1 : 0), 0);
    const patNote = document.createElement("div");
    patNote.style.cssText = "font-size:9px;color:var(--muted);margin-top:6px;font-family:'Share Tech Mono',monospace;";
    patNote.textContent = `${totalAlarmPts} alarm pts · ${ts.length} total · color = alarm fraction`;
    patBody.append(patNote);
  }
}
$("#eng-asset").addEventListener("change", (e) => { selectedAsset = e.target.value; refreshEngineer(); });
$("#eng-days").addEventListener("change", refreshEngineer);

// --------------------------------------------------------------- admin ----
let cachedAdminData = null;
async function refreshAdmin(useCache = false) {
  const svc = await refreshService(useCache);

  const cell = (k, v) =>
    `<div class="health-cell"><div class="v">${v}</div><div class="k">${k}</div></div>`;
  $("#adm-health").innerHTML =
    `<div class="health-grid">` +
    cell("store", svc.backend) + cell("workers", svc.workers) +
    cell("tick", `${svc.tick_minutes} min`) +
    cell("last tick", `${svc.last_tick_duration_s ?? "—"}s`) +
    cell("started", fmtTs(svc.started_at)) +
    cell("assets timed", svc.runtimes.length) +
    `</div>` +
    `<div class="attn">` +
    ((svc.attention || []).map((a) =>
      `<div>⚠ ${a.asset_key}: ${a.state} — ${a.state_detail || ""}</div>`).join("")
      || `<div style="color:var(--ok)">✓ no assets need attention</div>`) +
    `</div>`;

  if (!useCache || !cachedAdminData) {
    cachedAdminData = { assets: await api("/api/monitored-assets") };
  }
  const assets = cachedAdminData.assets;
  const tb = $("#adm-assets tbody");
  tb.replaceChildren();
  for (const m of assets) {
    const tr = document.createElement("tr");
    tr.append(td(m.asset_key));
    const st = td(""); st.append(badge(m.enabled ? m.state : "PAUSED")); tr.append(st);
    const src = td(`${m.source_kind}: ${String(m.source_ref).slice(0, 36)}`);
    src.title = m.source_ref; tr.append(src);
    tr.append(td(fmtTs(m.last_run_at)));
    tr.append(tdNum(m.last_runtime_s == null ? "—" : m.last_runtime_s));
    const actions = td("");
    const mk = (label, cls, fn) => {
      const b = document.createElement("button");
      b.className = `btn btn-sm ${cls}`;
      b.textContent = label;
      b.addEventListener("click", async () => {
        try { await fn(); refreshAdmin(); } catch (e) { toast(e.message, "err"); }
      });
      actions.append(b, " ");
    };
    mk(m.enabled ? "Disable" : "Enable", "", () =>
      api(`/api/monitored-assets/${m.asset_key}`, { method: "PATCH", body: { enabled: !m.enabled } }));
    mk("Run", "", async () => {
      await api("/api/service/run-now", { method: "POST", body: { assets: [m.asset_key] } });
      toast(`Analysis triggered for ${m.asset_key}`, "ok");
    });
    mk("Retire", "btn-bad", () =>
      openModal(`Retire ${m.asset_key}?`, [
        { name: "confirm", label: `Type the asset key to confirm — results are kept`, required: true },
      ], "Retire", async (body) => {
        if (body.confirm !== m.asset_key) throw new Error("asset key does not match");
        await api(`/api/monitored-assets/${m.asset_key}`, { method: "DELETE" });
        toast(`${m.asset_key} retired`, "ok");
        refreshAdmin();
      }));
    tr.append(actions);
    tr.title = m.state_detail || "";
    tb.append(tr);
  }
  $("#adm-assets-empty").classList.toggle("hidden", assets.length > 0);

  await fillAssetSelectors();
  const key = $("#adm-runs-asset").value;
  if (key) {
    if (!useCache || !cachedAdminData[key]) {
      cachedAdminData[key] = { runs: await api(`/api/assets/${key}/runs`) };
    }
    const runs = cachedAdminData[key].runs;
    const rb = $("#adm-runs tbody");
    rb.replaceChildren();
    for (const r of runs.slice(0, 15)) {
      const tr = document.createElement("tr");
      const stc = td(""); stc.append(badge(r.status === "OK" ? "OK" : "ERROR"));
      tr.append(td(fmtTs(r.started_at)), stc, td(r.rules_fired || "—"),
                td(r.notes || "—"), tdNum(r.duration_s ?? "—"));
      rb.append(tr);
    }
    const lvl = $("#adm-log-level").value;
    if (!useCache || !cachedAdminData[key][lvl]) {
      cachedAdminData[key][lvl] = { logs: await api(`/api/assets/${key}/runlog${lvl ? `?level=${lvl}` : ""}`) };
    }
    const logs = cachedAdminData[key][lvl].logs;
    $("#adm-runlog").innerHTML = logs.slice(0, 200).map((l) =>
      `<span class="${l.level}">${fmtTs(l.ts)} [${l.level}] ${l.stage}: ` +
      `${String(l.message).replace(/</g, "&lt;")}</span>`).join("\n");
  }

  // C6 — Run duration history sparkline (Advanced mode only)
  {
    const runHistBody = $("#adm-runhist-body");
    runHistBody.innerHTML = "";
    if (!key || !cachedAdminData[key]?.runs) {
      runHistBody.innerHTML = `<span style="color:var(--muted);font-size:11px;">Select an asset.</span>`;
    } else {
      const allRuns = cachedAdminData[key].runs.slice(0, 30).reverse();
      if (allRuns.length === 0) {
        runHistBody.innerHTML = `<span style="color:var(--muted);font-size:11px;">No runs yet.</span>`;
      } else {
        const durations = allRuns.map(r => r.duration_s ?? 0);
        const statuses = allRuns.map(r => r.status);
        const maxDur = Math.max(...durations, 1);
        const getCssAdm = v => getComputedStyle(document.body).getPropertyValue(v).trim();

        const W_total = runHistBody.clientWidth || 420;
        const BAR_H = 68, LABEL_H = 14, GAP = 2;
        const barW = Math.max(5, Math.floor((W_total - 16) / allRuns.length) - GAP);
        const W = allRuns.length * (barW + GAP) - GAP;
        const H = BAR_H + LABEL_H;
        const dpr = window.devicePixelRatio || 1;

        const cvs = document.createElement("canvas");
        cvs.width = W * dpr; cvs.height = H * dpr;
        cvs.style.width = W + "px"; cvs.style.height = H + "px";
        const ctx = cvs.getContext("2d");
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, W, H);

        allRuns.forEach((r, i) => {
          const dur = durations[i];
          const bH = Math.max(2, Math.round(dur / maxDur * BAR_H));
          const x = i * (barW + GAP);
          const y = BAR_H - bH;
          ctx.fillStyle = statuses[i] === "OK" ? getCssAdm("--ok") : getCssAdm("--bad");
          ctx.globalAlpha = 0.82;
          ctx.fillRect(x, y, barW, bH);
          ctx.globalAlpha = 1;
        });

        // Y-axis hint: max duration label
        ctx.fillStyle = getCssAdm("--muted");
        ctx.font = `8px "Share Tech Mono", monospace`;
        ctx.textAlign = "left";
        ctx.fillText(`${maxDur.toFixed(1)}s`, 2, 10);

        runHistBody.style.cssText = "padding:8px;display:block;";
        runHistBody.append(cvs);
        const avgDur = durations.reduce((a, b) => a + b, 0) / durations.length;
        const rhNote = document.createElement("div");
        rhNote.style.cssText = "font-size:9px;color:var(--muted);margin-top:4px;font-family:'Share Tech Mono',monospace;";
        rhNote.textContent = `${allRuns.length} runs · avg ${avgDur.toFixed(1)}s · green=OK red=ERROR`;
        runHistBody.append(rhNote);
      }
    }
  }

  await refreshConfig(useCache);
}

let configRows = [];
let cachedConfigData = null;
async function refreshConfig(useCache = false) {
  if (!useCache || !cachedConfigData) {
    cachedConfigData = { configRows: await api("/api/config"), audit: await api("/api/config/audit") };
  }
  configRows = cachedConfigData.configRows;
  renderConfig();
  const audit = cachedConfigData.audit;
  const ab = $("#adm-audit tbody");
  ab.replaceChildren();
  for (const a of audit.slice(0, 30)) {
    const tr = document.createElement("tr");
    tr.append(td(fmtTs(a.changed_at)), td(a.changed_by),
              td(`${a.category}.${a.param_path}`),
              td(`${a.old_value} → ${a.new_value}`), td(a.note || "—"));
    ab.append(tr);
  }
  $("#adm-audit-empty").classList.toggle("hidden", audit.length > 0);
}

function renderConfig() {
  const q = $("#cfg-filter").value.toLowerCase();
  const cb = $("#adm-config tbody");
  cb.replaceChildren();
  for (const c of configRows) {
    if (q && !(`${c.category}.${c.param_path} ${c.param_value}`.toLowerCase().includes(q))) continue;
    const tr = document.createElement("tr");
    tr.append(td(c.category), td(c.param_path), td(c.param_value), td(c.value_type));
    const cell = td("");
    const b = document.createElement("button");
    b.className = "btn btn-sm";
    b.textContent = "Edit";
    b.addEventListener("click", () =>
      openModal(`Edit ${c.category}.${c.param_path}`, [
        { name: "value", label: `Value (${c.value_type})`, value: c.param_value, required: true },
        { name: "changed_by", label: "Changed by", required: true },
        { name: "note", label: "Reason" },
      ], "Save", async (body) => {
        await api("/api/config", { method: "PUT",
          body: { category: c.category, param_path: c.param_path, ...body } });
        toast(`${c.category}.${c.param_path} updated`, "ok");
        refreshConfig();
      }));
    cell.append(b); tr.append(cell);
    cb.append(tr);
  }
}
$("#cfg-filter").addEventListener("input", renderConfig);
$("#adm-runs-asset").addEventListener("change", refreshAdmin);
$("#adm-log-level").addEventListener("change", refreshAdmin);

$("#btn-onboard").addEventListener("click", () =>
  openModal("Onboard new asset", [
    { name: "asset_key", label: "Asset key", required: true },
    { name: "grp", label: "Group", value: "fleet" },
    { name: "source_kind", label: "Source kind", options: ["csv", "table", "query"] },
    { name: "source_ref", label: "Source (file path / table / SQL query)", required: true },
    { name: "conn_ref", label: "Connection string (table/query only)" },
    { name: "timestamp_col", label: "Timestamp column", value: "time_stamp" },
    { name: "status_col", label: "Status column (optional)" },
  ], "Onboard", async (body) => {
    for (const k of Object.keys(body)) if (body[k] === "") delete body[k];
    const r = await api("/api/monitored-assets", { method: "POST", body });
    toast(`${r.asset_key} onboarded — ${r.probe_rows} rows probed, scoring next tick`, "ok", 5000);
    refreshAdmin();
  }));

// ---------------------------------------------------------------- poll ----
async function refresh() {
  try {
    await refreshService();
    if (activeTab === "operator") await refreshOperator();
    else if (activeTab === "engineer") await refreshEngineer();
    else await refreshAdmin();
  } catch (e) {
    console.error(e);
  }
}
refresh();
setInterval(refresh, POLL_MS);

/* ═══════════════════════════════════════════════════════════
   SIMULATE TAB — Generator, Files, Replay, Output Panel
════════════════════════════════════════════════════════════ */

const SIM = (() => {
  let generators = [];
  let currentSpec = null;
  let currentGenResp = null;
  let currentTagMappings = [];
  let replayRunning = false;
  let liveValPrev = {};
  let outputLines = [];
  let outputFilter = 'all';
  let outputLevel = 'all';
  let outputCollapsed = false;
  let autoScroll = true;

  function initSimTabs() {
    document.querySelectorAll('.sub-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        const pane = btn.dataset.simTab;
        document.querySelectorAll('.sub-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.sim-pane').forEach(p => p.classList.add('hidden'));
        const el = document.getElementById('sim-pane-' + pane);
        if (el) el.classList.remove('hidden');
        if (pane === 'files') refreshFiles();
        if (pane === 'replay') populateReplayFileList();
      });
    });
  }

  function log(text, src = 'sim', level = 'info') {
    const ts = new Date().toLocaleTimeString();
    outputLines.push({ ts, text, src, level });
    if (outputLines.length > 2000) outputLines.shift();
    renderOutputLog();
    const el = document.getElementById('output-line-count');
    if (el) el.textContent = outputLines.length + ' lines';
  }

  function renderOutputLog() {
    const el = document.getElementById('output-log');
    if (!el) return;
    const visible = outputLines.filter(e => {
      if (outputFilter !== 'all' && e.src !== outputFilter) return false;
      if (outputLevel === 'warn' && !['warn','error'].includes(e.level)) return false;
      if (outputLevel === 'error' && e.level !== 'error') return false;
      return true;
    });
    el.innerHTML = visible.map(e => {
      const cls = `log-${e.level === 'info' ? (e.src === 'sim' ? 'sim' : 'acm') : e.level}`;
      const pfx = e.src === 'sim' ? '[SIM]' : '[ACM]';
      return `<span class="${cls}">${e.ts} ${pfx} ${String(e.text).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</span>`;
    }).join('\n');
    if (autoScroll) el.scrollTop = el.scrollHeight;
  }

  function initOutputPanel() {
    const toggleBtn = document.getElementById('btn-output-toggle');
    const panel = document.getElementById('output-panel');
    const clearBtn = document.getElementById('btn-output-clear');
    const levelSel = document.getElementById('sel-output-level');
    const autoScrollChk = document.getElementById('chk-autoscroll');

    toggleBtn?.addEventListener('click', () => {
      outputCollapsed = !outputCollapsed;
      panel.classList.toggle('collapsed', outputCollapsed);
      toggleBtn.textContent = outputCollapsed ? '∨' : '∧';
      document.querySelector('.main').style.paddingBottom = outputCollapsed ? '40px' : '210px';
    });
    clearBtn?.addEventListener('click', () => { outputLines = []; renderOutputLog(); });
    levelSel?.addEventListener('change', () => { outputLevel = levelSel.value; renderOutputLog(); });
    autoScrollChk?.addEventListener('change', () => { autoScroll = autoScrollChk.checked; });
    document.querySelectorAll('.output-src-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        outputFilter = btn.dataset.src;
        document.querySelectorAll('.output-src-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderOutputLog();
      });
    });
  }

  async function simGet(path) {
    const r = await fetch('/api/sim' + path);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  async function simPost(path, body = {}) {
    const r = await fetch('/api/sim' + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  async function simDelete(path) {
    const r = await fetch('/api/sim' + path, { method: 'DELETE' });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  async function loadGenerators() {
    try {
      generators = await simGet('/generators');
      const sel = document.getElementById('sim-domain-sel');
      if (!sel) return;
      sel.innerHTML = generators.map(g =>
        `<option value="${g.domain_id}">${g.display_name}</option>`).join('');
      if (generators.length) await onDomainChange();
    } catch (e) { log('Failed to load generators: ' + e.message, 'sim', 'error'); }
  }

  async function onDomainChange() {
    const sel = document.getElementById('sim-domain-sel');
    if (!sel) return;
    const id = sel.value;
    const g = generators.find(x => x.domain_id === id);
    if (g) document.getElementById('sim-domain-desc').textContent = g.description || '';
    try {
      currentSpec = await simGet('/generators/' + id + '/spec');
      populateScenarios();
      populateParams();
      setDefaultFilename();
    } catch (e) { log('Failed to load spec: ' + e.message, 'sim', 'error'); }
  }

  function populateScenarios() {
    const sel = document.getElementById('sim-scenario-sel');
    if (!sel || !currentSpec) return;
    sel.innerHTML = (currentSpec.scenarios || []).map(sc =>
      `<option value="${sc.id}">${sc.label}${sc.description ? ' — ' + sc.description : ''}</option>`
    ).join('');
  }

  function populateParams() {
    const grid = document.getElementById('sim-params-grid');
    if (!grid || !currentSpec) return;
    grid.innerHTML = '';
    (currentSpec.parameters || []).forEach(p => {
      const wrap = document.createElement('div');
      const lbl = document.createElement('label');
      lbl.className = 'lbl-sm';
      lbl.textContent = p.label + (p.unit ? ' (' + p.unit + ')' : '');
      wrap.appendChild(lbl);
      const inpStyle = 'width:100%;box-sizing:border-box;font-family:"Share Tech Mono",monospace;font-size:12px;background:var(--bg2);border:1px solid var(--line);color:var(--ink);padding:5px 8px;';
      let input;
      if (p.type === 'select' && p.options) {
        input = document.createElement('select');
        input.style.cssText = inpStyle;
        p.options.forEach(opt => {
          const o = document.createElement('option');
          o.value = opt; o.textContent = opt;
          if (opt === p.default) o.selected = true;
          input.appendChild(o);
        });
      } else {
        input = document.createElement('input');
        input.style.cssText = inpStyle;
        input.type = p.type === 'number' ? 'number' : (p.type === 'datetime' ? 'datetime-local' : 'text');
        if (p.default !== null && p.default !== undefined) input.value = p.default;
        if (p.min !== null && p.min !== undefined) input.min = p.min;
        if (p.max !== null && p.max !== undefined) input.max = p.max;
        if (p.step !== null && p.step !== undefined) input.step = p.step;
      }
      input.dataset.param = p.name;
      wrap.appendChild(input);
      grid.appendChild(wrap);
    });
  }

  function setDefaultFilename() {
    const inp = document.getElementById('sim-output-filename');
    if (inp && currentSpec?.default_output_filename) inp.value = currentSpec.default_output_filename;
  }

  function collectParams() {
    const params = {};
    document.querySelectorAll('#sim-params-grid [data-param]').forEach(el => {
      const name = el.dataset.param;
      const p = (currentSpec?.parameters || []).find(x => x.name === name);
      params[name] = (p && p.type === 'number') ? (parseFloat(el.value) || 0) : el.value;
    });
    return params;
  }

  async function doGenerate() {
    const domain = document.getElementById('sim-domain-sel')?.value;
    const scenario = document.getElementById('sim-scenario-sel')?.value;
    const filename = document.getElementById('sim-output-filename')?.value.trim();
    const statusEl = document.getElementById('sim-gen-status');
    const backdate = document.getElementById('sim-backdate')?.checked;
    const backdateDays = parseInt(document.getElementById('sim-backdate-days')?.value) || 45;
    if (!filename) { if(statusEl) statusEl.textContent = 'Filename required'; return; }
    if(statusEl) statusEl.textContent = 'Generating…';
    log(`Generating ${domain}/${scenario} → ${filename}`, 'sim', 'info');
    try {
      currentGenResp = await simPost('/generators/' + domain + '/generate', {
        scenario, output_filename: filename,
        parameters: collectParams(),
        load_into_replay: false, backdate, backdate_days: backdateDays,
      });
      if(statusEl) statusEl.textContent = `✓ ${currentGenResp.row_count} rows, ${currentGenResp.column_count} columns`;
      log(`Generated: ${currentGenResp.filename} (${currentGenResp.row_count} rows)`, 'sim', 'info');
      currentTagMappings = currentGenResp.default_tag_mappings || [];
      renderPreview(currentGenResp);
    } catch (e) {
      if(statusEl) statusEl.textContent = 'Error: ' + e.message;
      log('Generate failed: ' + e.message, 'sim', 'error');
    }
  }

  function renderPreview(resp) {
    const card = document.getElementById('sim-preview-card');
    if (!card) return;
    card.classList.remove('hidden');
    const meta = document.getElementById('sim-preview-meta');
    if(meta) meta.textContent = `${resp.row_count} rows · ${resp.column_count} columns · ${resp.filename}`;
    const tbl = document.getElementById('sim-preview-table');
    if (!tbl || !resp.preview?.length) return;
    const cols = Object.keys(resp.preview[0]);
    const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    tbl.innerHTML = '<thead><tr>' + cols.map(c=>'<th>'+esc(c)+'</th>').join('') + '</tr></thead><tbody>'
      + resp.preview.map(row=>'<tr>'+cols.map(c=>'<td>'+esc(row[c]??'')+'</td>').join('')+'</tr>').join('') + '</tbody>';
    const keyInp = document.getElementById('sim-onboard-key');
    if (keyInp && !keyInp.value) {
      keyInp.value = resp.filename.replace(/\.(csv|xlsx)$/i,'').replace(/[^a-zA-Z0-9_]/g,'_').toUpperCase();
    }
  }

  async function doOnboard() {
    const assetKey = document.getElementById('sim-onboard-key')?.value.trim();
    const statusEl = document.getElementById('sim-onboard-status');
    if (!currentGenResp) { if(statusEl) statusEl.textContent = 'Generate a CSV first'; return; }
    if (!assetKey) { if(statusEl) statusEl.textContent = 'Asset key required'; return; }
    if(statusEl) statusEl.textContent = 'Onboarding…';
    log(`Onboarding ${assetKey} from ${currentGenResp.filename}`, 'sim', 'info');
    try {
      const simResp = await simPost('/onboard', {
        domain_id: document.getElementById('sim-domain-sel')?.value,
        request: { scenario: document.getElementById('sim-scenario-sel')?.value,
          output_filename: currentGenResp.filename, parameters: collectParams() },
        asset_key: assetKey,
        grp: document.getElementById('sim-onboard-grp')?.value || 'sim',
        fast_track: document.getElementById('sim-fast-track')?.checked || false,
        backdate: document.getElementById('sim-backdate')?.checked,
        backdate_days: parseInt(document.getElementById('sim-backdate-days')?.value) || 45,
      });
      const acmResp = await fetch('/api/monitored-assets', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(simResp.suggested_onboard),
      });
      if (!acmResp.ok) throw new Error(await acmResp.text());
      const acmData = await acmResp.json();
      if(statusEl) statusEl.textContent = `✓ Onboarded (${acmData.state})`;
      log(`Asset ${assetKey} onboarded (state: ${acmData.state})`, 'sim', 'info');
    } catch (e) {
      if(statusEl) statusEl.textContent = 'Error: ' + e.message;
      log('Onboard failed: ' + e.message, 'sim', 'error');
    }
  }

  async function refreshFiles() {
    const tbody = document.getElementById('sim-files-body');
    if (!tbody) return;
    try {
      const files = await simGet('/files');
      const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      tbody.innerHTML = files.map(f => `<tr>
        <td>${esc(f.filename)}</td><td>${esc(f.source)}</td>
        <td class="num">${f.row_count}</td><td class="num">${f.column_count}</td>
        <td>${esc(f.modified_at?.slice(0,16)||'—')}</td>
        <td style="white-space:nowrap;">
          <button class="btn btn-sm" onclick="SIM.previewFile('${esc(f.filename)}','${esc(f.source)}')">Preview</button>
          <button class="btn btn-sm btn-bad" onclick="SIM.deleteFile('${esc(f.filename)}','${esc(f.source)}')">Delete</button>
        </td></tr>`).join('');
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="6" style="color:var(--muted);">— error loading files —</td></tr>';
      log('Files load failed: ' + e.message, 'sim', 'error');
    }
  }

  async function previewFile(filename, source) {
    const card = document.getElementById('sim-file-preview-card');
    const tbl = document.getElementById('sim-file-preview-table');
    if (!card || !tbl) return;
    try {
      const meta = await simGet(`/files/${encodeURIComponent(filename)}/metadata?source=${source}`);
      card.classList.remove('hidden');
      document.getElementById('sim-file-preview-title').textContent = `Preview: ${filename}`;
      if (!meta.preview?.length) { tbl.innerHTML = '<tr><td>No preview</td></tr>'; return; }
      const cols = Object.keys(meta.preview[0]);
      const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      tbl.innerHTML = '<thead><tr>'+cols.map(c=>'<th>'+esc(c)+'</th>').join('')+'</tr></thead><tbody>'
        + meta.preview.map(row=>'<tr>'+cols.map(c=>'<td>'+esc(row[c]??'')+'</td>').join('')+'</tr>').join('')+'</tbody>';
    } catch (e) { log('Preview failed: ' + e.message, 'sim', 'error'); }
  }

  async function deleteFile(filename, source) {
    if (!confirm(`Delete ${filename}?`)) return;
    try {
      await simDelete(`/files/${encodeURIComponent(filename)}?source=${source}`);
      log(`Deleted: ${filename}`, 'sim', 'info');
      refreshFiles();
    } catch (e) { log('Delete failed: ' + e.message, 'sim', 'error'); }
  }

  async function handleUpload(file) {
    if (!file) return;
    log(`Uploading ${file.name}…`, 'sim', 'info');
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await fetch('/api/sim/files/upload', { method: 'POST', body: fd });
      if (!r.ok) throw new Error(await r.text());
      const meta = await r.json();
      log(`Uploaded: ${meta.filename} (${meta.row_count} rows)`, 'sim', 'info');
      refreshFiles();
    } catch (e) { log('Upload failed: ' + e.message, 'sim', 'error'); }
  }

  async function populateReplayFileList() {
    const sel = document.getElementById('sim-replay-file');
    if (!sel) return;
    try {
      const files = await simGet('/files');
      sel.innerHTML = files.map(f =>
        `<option value="${f.filename}" data-source="${f.source}">${f.filename} (${f.source})</option>`
      ).join('');
      if (files.length) {
        const src = document.getElementById('sim-replay-source');
        if (src) src.value = files[0].source;
        await loadTagPlan(files[0].filename, files[0].source);
      }
    } catch (e) { log('File list failed: ' + e.message, 'sim', 'error'); }
  }

  async function loadTagPlan(filename, source) {
    const tbody = document.getElementById('sim-tags-body');
    const countEl = document.getElementById('sim-tag-count');
    if (!tbody) return;
    try {
      const meta = await simGet(`/files/${encodeURIComponent(filename)}/metadata?source=${source}`);
      currentTagMappings = meta.default_tag_mappings || [];
      renderTagPlan();
      if (countEl) countEl.textContent = `(${currentTagMappings.filter(t=>t.enabled).length} / ${currentTagMappings.length} enabled)`;
    } catch (e) { log('Tag plan load failed: ' + e.message, 'sim', 'error'); }
  }

  function renderTagPlan() {
    const tbody = document.getElementById('sim-tags-body');
    if (!tbody) return;
    const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    tbody.innerHTML = currentTagMappings.map((t,i) => `<tr>
      <td><input type="checkbox" data-tag-idx="${i}" ${t.enabled?'checked':''}></td>
      <td>${esc(t.csv_column)}</td>
      <td><code style="font-size:11px;">${esc(t.tag_name)}</code></td>
      <td><span class="badge">${esc(t.data_type)}</span></td>
    </tr>`).join('');
    tbody.querySelectorAll('input[type=checkbox]').forEach(cb => {
      cb.addEventListener('change', () => {
        currentTagMappings[parseInt(cb.dataset.tagIdx)].enabled = cb.checked;
        const c = document.getElementById('sim-tag-count');
        if(c) c.textContent = `(${currentTagMappings.filter(t=>t.enabled).length} / ${currentTagMappings.length} enabled)`;
      });
    });
  }

  async function doConfigure() {
    const fileSel = document.getElementById('sim-replay-file');
    const srcSel = document.getElementById('sim-replay-source');
    const statusEl = document.getElementById('sim-replay-status-text');
    if (!fileSel?.value) { if(statusEl) statusEl.textContent = 'Select a file first'; return; }
    const publisherMode = document.getElementById('sim-replay-publisher')?.value || 'buffer';
    const body = {
      csv_file: fileSel.value,
      csv_source: srcSel?.value || 'generated',
      frequency_hz: parseFloat(document.getElementById('sim-replay-hz')?.value) || 1.0,
      loop_mode: document.getElementById('sim-replay-loop')?.value || 'loop_forever',
      timestamp_mode: document.getElementById('sim-replay-tsmode')?.value || 'wall_clock',
      protocol: publisherMode === 'buffer' ? 'mqtt' : publisherMode,
      publisher_mode: publisherMode,
      tags: currentTagMappings,
      start_row: 0,
    };
    if (['mqtt','both'].includes(publisherMode)) {
      body.mqtt_host = document.getElementById('sim-mqtt-host')?.value || 'localhost';
      body.mqtt_port = parseInt(document.getElementById('sim-mqtt-port')?.value) || 1883;
      body.mqtt_topic_prefix = document.getElementById('sim-mqtt-prefix')?.value || 'industrial-tag-simulator';
      body.mqtt_device_id = document.getElementById('sim-mqtt-device')?.value || 'FlowMeter01';
    }
    if(statusEl) statusEl.textContent = 'Configuring…';
    log(`Configuring replay: ${fileSel.value} @ ${body.frequency_hz}Hz via ${publisherMode}`, 'sim', 'info');
    try {
      await simPost('/replay/configure', body);
      if(statusEl) statusEl.textContent = '✓ Configured';
      log('Replay configured', 'sim', 'info');
      document.getElementById('btn-replay-start')?.classList.remove('hidden');
      document.getElementById('btn-replay-stop')?.classList.add('hidden');
      document.getElementById('btn-replay-restart')?.classList.add('hidden');
    } catch (e) {
      if(statusEl) statusEl.textContent = 'Error: ' + e.message;
      log('Configure failed: ' + e.message, 'sim', 'error');
    }
  }

  async function doStartReplay() {
    const statusEl = document.getElementById('sim-replay-status-text');
    try {
      await simPost('/replay/start');
      replayRunning = true;
      if(statusEl) statusEl.textContent = '▶ Running';
      log('Replay started', 'sim', 'info');
      document.getElementById('btn-replay-start')?.classList.add('hidden');
      document.getElementById('btn-replay-stop')?.classList.remove('hidden');
      document.getElementById('btn-replay-restart')?.classList.remove('hidden');
      document.getElementById('btn-sim-start')?.classList.add('hidden');
      document.getElementById('btn-sim-stop')?.classList.remove('hidden');
      refreshSimStatus();
    } catch (e) {
      if(statusEl) statusEl.textContent = 'Error: ' + e.message;
      log('Start failed: ' + e.message, 'sim', 'error');
    }
  }

  async function doStopReplay() {
    const statusEl = document.getElementById('sim-replay-status-text');
    try {
      await simPost('/replay/stop');
      replayRunning = false;
      if(statusEl) statusEl.textContent = '■ Stopped';
      log('Replay stopped', 'sim', 'info');
      document.getElementById('btn-replay-start')?.classList.remove('hidden');
      document.getElementById('btn-replay-stop')?.classList.add('hidden');
      document.getElementById('btn-replay-restart')?.classList.add('hidden');
      document.getElementById('btn-sim-start')?.classList.remove('hidden');
      document.getElementById('btn-sim-stop')?.classList.add('hidden');
      refreshSimStatus();
    } catch (e) { log('Stop failed: ' + e.message, 'sim', 'error'); }
  }

  async function refreshLiveValues() {
    if (!replayRunning) return;
    try {
      const resp = await simGet('/replay/current-values');
      const tbody = document.getElementById('sim-live-body');
      const updEl = document.getElementById('sim-live-updated');
      if (!tbody) return;
      if (updEl && resp.updated_at) updEl.textContent = resp.updated_at.slice(11,19) + ' UTC';
      const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      tbody.innerHTML = (resp.values||[]).map(v => {
        const changed = liveValPrev[v.node_id] !== String(v.value);
        liveValPrev[v.node_id] = String(v.value);
        return `<tr class="${changed?'val-changed':''}">
          <td><code style="font-size:11px;">${esc(v.tag_name)}</code></td>
          <td class="num" style="font-family:'Share Tech Mono',monospace;">${esc(String(v.value??'—'))}</td>
          <td>${esc(v.data_type)}</td>
          <td style="font-size:10px;color:var(--muted);">${esc(v.last_updated?.slice(11,19)||'—')}</td>
        </tr>`;
      }).join('');
    } catch (_) {}
  }

  async function refreshSimStatus() {
    try {
      const status = await simGet('/status');
      const pillText = document.getElementById('sim-pill-text');
      const fileText = document.getElementById('sim-file-text');
      if (pillText) pillText.textContent = (status.state||'IDLE').toUpperCase();
      if (fileText) {
        const f = status.csv_file || '—';
        fileText.textContent = f.length > 20 ? '…' + f.slice(-18) : f;
      }
      replayRunning = status.state === 'running';
      document.getElementById('btn-sim-start')?.classList.toggle('hidden', replayRunning);
      document.getElementById('btn-sim-stop')?.classList.toggle('hidden', !replayRunning);
    } catch (_) {}
  }

  function init() {
    initSimTabs();
    initOutputPanel();
    document.getElementById('sim-domain-sel')?.addEventListener('change', onDomainChange);
    document.getElementById('btn-generate')?.addEventListener('click', doGenerate);
    document.getElementById('btn-sim-onboard')?.addEventListener('click', doOnboard);
    document.getElementById('btn-sim-upload-open')?.addEventListener('click', () =>
      document.getElementById('sim-upload-input')?.click());
    document.getElementById('sim-upload-input')?.addEventListener('change', e => {
      const f = e.target.files?.[0]; if (f) handleUpload(f);
    });
    document.getElementById('btn-sim-files-refresh')?.addEventListener('click', refreshFiles);
    document.getElementById('sim-replay-file')?.addEventListener('change', async e => {
      const opt = e.target.selectedOptions?.[0];
      if (opt) {
        const src = document.getElementById('sim-replay-source');
        if (src && opt.dataset.source) src.value = opt.dataset.source;
        await loadTagPlan(opt.value, opt.dataset.source || 'generated');
      }
    });
    document.getElementById('sim-replay-publisher')?.addEventListener('change', e => {
      const pub = e.target.value;
      document.getElementById('sim-mqtt-card')?.classList.toggle('hidden', pub === 'buffer' || pub === 'opcua');
    });
    document.getElementById('btn-tags-all')?.addEventListener('click', () => {
      currentTagMappings.forEach(t => t.enabled = true); renderTagPlan();
    });
    document.getElementById('btn-tags-none')?.addEventListener('click', () => {
      currentTagMappings.forEach(t => t.enabled = false); renderTagPlan();
    });
    document.getElementById('btn-replay-configure')?.addEventListener('click', doConfigure);
    document.getElementById('btn-replay-start')?.addEventListener('click', doStartReplay);
    document.getElementById('btn-replay-stop')?.addEventListener('click', doStopReplay);
    document.getElementById('btn-replay-restart')?.addEventListener('click', async () => {
      try { await simPost('/replay/restart'); log('Replay restarted', 'sim', 'info'); }
      catch (e) { log('Restart failed: ' + e.message, 'sim', 'error'); }
    });
    document.getElementById('btn-sim-start')?.addEventListener('click', doStartReplay);
    document.getElementById('btn-sim-stop')?.addEventListener('click', doStopReplay);
    loadGenerators();
    setInterval(refreshSimStatus, 3000);
    setInterval(refreshLiveValues, 1000);
    log('Simulator module initialized', 'sim', 'info');
  }

  return { init, previewFile, deleteFile, log };
})();

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', SIM.init);
} else {
  SIM.init();
}
