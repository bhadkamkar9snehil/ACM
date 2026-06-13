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
function badge(state) {
  const el = document.createElement("span");
  el.className = `badge ${state || "NEW"}`;
  el.textContent = state || "NEW";
  return el;
}
function fmtTs(ts) { return ts ? String(ts).slice(0, 16) : "—"; }
function fmtNum(v, d = 2) { return v == null || Number.isNaN(+v) ? "—" : (+v).toFixed(d); }

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
  path.setAttribute("stroke", peak >= 3 ? "#e05050" : "#5ba8e8");
  path.setAttribute("stroke-width", "1.4");
  path.setAttribute("stroke-linejoin", "round");
  svg.append(path);
  // z=3 reference line when in range
  if (max >= 3) {
    const y3 = h - 2 - (3 / max) * (h - 5);
    const ln = document.createElementNS(svg.namespaceURI, "line");
    ln.setAttribute("x1", 0); ln.setAttribute("x2", w);
    ln.setAttribute("y1", y3); ln.setAttribute("y2", y3);
    ln.setAttribute("stroke", "rgba(224,80,80,.35)");
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

// Theme toggle
document.getElementById("btn-theme").addEventListener("click", () => {
  const body = document.body;
  const next = body.dataset.theme === "light" ? "dark" : "light";
  body.dataset.theme = next;
  document.documentElement.dataset.theme = next;
});

// ------------------------------------------------------------- service ----
async function refreshService() {
  const svc = await api("/api/service");
  const pill = $("#svc-pill");
  pill.className = "stat-cell " + (svc.tick_in_progress ? "warn" : svc.paused ? "bad" : "ok");
  $("#svc-pill-text").textContent = svc.tick_in_progress ? "TICKING" : svc.paused ? "PAUSED" : "WATCHING";
  $("#svc-tick-info").textContent =
    `tick ${fmtTs(svc.last_tick_at)} · ${svc.last_tick_duration_s ?? "—"}s`;
  $("#btn-pause").classList.toggle("hidden", !!svc.paused);
  $("#btn-resume").classList.toggle("hidden", !svc.paused);
  if (document.activeElement !== $("#inp-tick")) $("#inp-tick").value = svc.tick_minutes;
  return svc;
}
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

async function refreshOperator() {
  const [fleet, sparks, alarms] = await Promise.all([
    api("/api/fleet"), api("/api/fleet/sparklines"), api("/api/alarms?unacked=true"),
  ]);

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

  const nowTs = Date.now();
  const hourMs = 3600000;
  const renderTimeline = (alarmList) => {
    let html = '<div class="mega-timeline">';
    for (let i = 23; i >= 0; i--) {
      const bStart = nowTs - (i + 1) * hourMs;
      const bEnd = nowTs - i * hourMs;
      let active = false, maxPeak = 0;
      for (const al of alarmList) {
        const alStart = new Date(al.start_ts).getTime();
        const alEnd = al.end_ts ? new Date(al.end_ts).getTime() : nowTs;
        if (alStart < bEnd && alEnd > bStart) { active = true; maxPeak = Math.max(maxPeak, al.peak_fused || 0); }
      }
      html += `<div class="mt-block ${active ? (maxPeak > 5.0 ? 'danger' : 'warn') : ''}"></div>`;
    }
    return html + '</div>';
  };

  const mx = $("#mega-matrix");
  mx.innerHTML = `
    <div class="mega-hdr">
      <div>Asset / Episode</div>
      <div>Status / Start</div>
      <div>Trend / Hrs</div>
      <div>Fused / Peak</div>
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="mt-empty">-24h</span><span class="mt-empty">Timeline Matrix</span><span class="mt-empty">Now</span>
      </div>
      <div>Unack</div>
    </div>
  `;

  fleet.sort((a, b) => (STATE_ORDER[a.state] ?? 9) - (STATE_ORDER[b.state] ?? 9) || String(a.asset_key).localeCompare(String(b.asset_key)));

  for (const a of fleet) {
    const assetAlarms = alarmsByAsset[a.asset_key] || [];
    
    // Asset Row
    const aRow = document.createElement("div");
    aRow.className = "mega-asset-row";
    aRow.innerHTML = `
      <div style="font-weight:bold; color:var(--text);"><span style="display:inline-block;width:14px;color:var(--muted);">${assetAlarms.length ? '▼' : '►'}</span> ${a.asset_key}</div>
      <div id="mr-state-${a.asset_key}"></div>
      <div id="mr-sp-${a.asset_key}"></div>
      <div class="num">${fmtNum(a.last_fused)}</div>
      <div>${renderTimeline(assetAlarms)}</div>
      <div class="num" style="color:var(--warn); font-weight:bold;">${a.unacked_alarms || 0}</div>
    `;
    aRow.querySelector(`[id="mr-state-${a.asset_key}"]`).append(badge(a.state));
    aRow.querySelector(`[id="mr-sp-${a.asset_key}"]`).append(sparkline(sparks[a.asset_key] || []));
    aRow.addEventListener("click", (e) => {
      if (e.target.tagName !== 'BUTTON') {
        aRow.classList.toggle('collapsed');
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
          <div>${renderTimeline([al])}</div>
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

const INFERNO = ["#000004", "#160b39", "#420a68", "#6a176e", "#932667",
                 "#bc3754", "#dd513a", "#f37819", "#fca50a", "#f6d746", "#fcffa4"];
function heatColor(z) {
  const t = Math.max(0, Math.min(1, z / 8));
  return INFERNO[Math.round(t * (INFERNO.length - 1))];
}

async function refreshEngineer() {
  await fillAssetSelectors();
  const key = $("#eng-asset").value;
  if (!key) return;
  selectedAsset = key;
  const days = +$("#eng-days").value;
  const [s, meta, eps, daily, runs] = await Promise.all([
    api(`/api/assets/${key}/series?days=${days}`),
    api(`/api/assets/${key}`),
    api(`/api/assets/${key}/alarms`),
    api(`/api/assets/${key}/daily`),
    api(`/api/assets/${key}/runs?limit=1`),
  ]);
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

  // culprit banner from the latest run's notes
  const notes = runs[0]?.notes || "";
  const culprits = notes.startsWith("culprits: ") ? notes.slice(10) : null;
  $("#eng-culprits").classList.toggle("hidden", !culprits);
  if (culprits) {
    $("#eng-culprits").innerHTML =
      `⚠ Alarm driven by: <b>${culprits}</b> — OMR residual attribution, latest run`;
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
        ctx.fillStyle = v == null ? "#1a1710" : heatColor(v);
        ctx.fillRect(j * colW, zi * rowH, colW + 0.6, rowH - 1.5);
      }
    });
  };

  if (plot) plot.destroy();
  plot = new uPlot({
    width, height: 200,
    cursor: { y: false },
    series: [
      {},
      { label: "fused z", stroke: "#5ba8e8", width: 2,
        fill: "rgba(91,168,232,.12)", value: (u, v) => fmtNum(v) },
      { label: "alert_z", stroke: "#e05050", dash: [5, 5], width: 1.5,
        points: { show: false }, value: (u, v) => fmtNum(v) },
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
        ctx.fillStyle = "rgba(224,80,80,0.14)";
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
  }, [ts, fused, fused.map(() => alertZ)], $("#eng-chart"));

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

  // alarm episodes
  const eb = $("#eng-episodes tbody");
  eb.replaceChildren();
  for (const e of eps.slice(0, 30)) {
    const tr = document.createElement("tr");
    tr.append(td(fmtTs(e.start_ts)), td(fmtTs(e.end_ts)),
              tdNum(fmtNum(e.duration_h, 1)), tdNum(fmtNum(e.peak_fused)));
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
  for (const d of daily.slice(0, 21)) {
    const tr = document.createElement("tr");
    tr.append(td(d.day), tdNum(fmtNum(d.fused_max)),
              tdNum((d.rate_z3 * 100).toFixed(1) + "%"), tdNum(d.alarm_samples),
              tdNum(d.availability == null ? "—" : (d.availability * 100).toFixed(0) + "%"));
    db.append(tr);
  }
}
$("#eng-asset").addEventListener("change", (e) => { selectedAsset = e.target.value; refreshEngineer(); });
$("#eng-days").addEventListener("change", refreshEngineer);

// --------------------------------------------------------------- admin ----
async function refreshAdmin() {
  const svc = await refreshService();

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

  const assets = await api("/api/monitored-assets");
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
    const runs = await api(`/api/assets/${key}/runs`);
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
    const logs = await api(`/api/assets/${key}/runlog${lvl ? `?level=${lvl}` : ""}`);
    $("#adm-runlog").innerHTML = logs.slice(0, 200).map((l) =>
      `<span class="${l.level}">${fmtTs(l.ts)} [${l.level}] ${l.stage}: ` +
      `${String(l.message).replace(/</g, "&lt;")}</span>`).join("\n");
  }

  await refreshConfig();
}

let configRows = [];
async function refreshConfig() {
  configRows = await api("/api/config");
  renderConfig();
  const audit = await api("/api/config/audit");
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
