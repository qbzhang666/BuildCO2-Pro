// BuildCO2 Pro dashboard: the pages of the Power BI report, recalculated by the Python engine on every change.
"use strict";
const COL = { Steel: "#B5452E", Aluminium: "#4F86C6", Concrete: "#9AA0A8", Glass: "#7FB7C9", Timber: "#C8871E",
  Plasterboard: "#D8C6A8", "Masonry and stone": "#7551A8", "Plastics and rubber": "#4E9A68", Other: "#5A5F68" };
const S = { project: null, token: "example", result: null, checks: [], charts: {}, timer: null };
const $ = (s) => document.querySelector(s);
const fmt = (v, d = 0) => (v == null || isNaN(v)) ? "-" : Number(v).toLocaleString("en-AU", { maximumFractionDigits: d, minimumFractionDigits: d });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function getPath(o, p) { return p.split(".").reduce((a, k) => (a == null ? a : a[k]), o); }
function setPath(o, p, v) { const ks = p.split("."); let a = o; ks.slice(0, -1).forEach((k) => (a = a[k] = a[k] || {})); a[ks.at(-1)] = v; }

async function api(url, body, raw = false) {
  const r = await fetch(url, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) { const t = await r.text(); let m = t; try { m = JSON.parse(t).detail; } catch (e) {} throw new Error(m); }
  return raw ? r.blob() : r.json();
}

// charts in a hidden tab are drawn when the tab is opened (a hidden element has no size)
const NOOP = { setOption() {}, resize() {} };
function chart(id) {
  const el = document.getElementById(id);
  if (!el.offsetWidth) return NOOP;
  if (!S.charts[id]) S.charts[id] = echarts.init(el, null, { renderer: "svg" });
  return S.charts[id];
}
function resizeVisible() { Object.entries(S.charts).forEach(([id, c]) => { if (document.getElementById(id).offsetWidth) c.resize(); }); }
window.addEventListener("resize", resizeVisible);

// ------------------------------------------------------------------ inputs
function bindInputs() {
  document.querySelectorAll("[data-k]").forEach((el) => {
    const k = el.dataset.k, v = getPath(S.project, k);
    if (el.type === "checkbox") el.checked = !!v; else el.value = v ?? "";
    el.onchange = () => {
      let v = el.type === "checkbox" ? el.checked : el.type === "number" ? parseFloat(el.value) : el.value;
      setPath(S.project, k, v); recalc();
    };
  });
  drawCranes(); drawLevers(); drawRoles();
}

function drawCranes() {
  const box = $("#cranes"); box.innerHTML = "<div class='small muted'>Cranes: name, kW, fleet hours</div>";
  S.project.cranes.forEach((c, i) => {
    const d = document.createElement("div"); d.className = "row";
    d.innerHTML = `<input value="${esc(c.name)}"><input type="number" value="${c.power_kw}" style="width:4.5em"><input type="number" value="${c.fleet_hours}" style="width:5.5em"><button class="ghost small">x</button>`;
    const [n, p, h] = d.querySelectorAll("input");
    n.onchange = () => { c.name = n.value; recalc(); }; p.onchange = () => { c.power_kw = +p.value; recalc(); };
    h.onchange = () => { c.fleet_hours = +h.value; recalc(); };
    d.querySelector("button").onclick = () => { S.project.cranes.splice(i, 1); drawCranes(); recalc(); };
    box.appendChild(d);
  });
}
$("#b-crane").onclick = () => { S.project.cranes.push({ name: "Tower crane", number: 1, power_kw: 40, fleet_hours: 1000 }); drawCranes(); recalc(); };

function drawLevers() {
  const box = $("#levers"); box.innerHTML = "";
  S.project.levers.forEach((lv, i) => {
    const d = document.createElement("div"); d.className = "row";
    const red = Object.entries(lv.reduction).map(([k, v]) => `${k}=${v}`).join(", ");
    d.innerHTML = `<input value="${esc(lv.name)}"><input value="${esc(red)}" title="group=fraction, e.g. Concrete=0.3, Steel=0.4; *=0.31 for all"><button class="ghost small">x</button>`;
    const [n, r] = d.querySelectorAll("input");
    n.onchange = () => { lv.name = n.value; recalc(); };
    r.onchange = () => { lv.reduction = Object.fromEntries(r.value.split(",").map((s) => s.split("=").map((x) => x.trim())).filter((x) => x.length === 2).map(([k, v]) => [k, +v])); recalc(); };
    d.querySelector("button").onclick = () => { S.project.levers.splice(i, 1); drawLevers(); recalc(); };
    box.appendChild(d);
  });
}
$("#b-lever").onclick = () => { S.project.levers.push({ name: "New lever", reduction: { Concrete: 0.2 }, applies_to_a4_a5: false }); drawLevers(); recalc(); };

function drawRoles() {
  const box = $("#roles"); const st = (S.summary && S.summary.storeys) || [];
  box.innerHTML = st.length ? "" : "<p class='muted small'>The inventory has no storeys.</p>";
  st.forEach((s) => {
    const d = document.createElement("label"); d.className = "inline";
    const v = S.project.storeys.roles[s] || "";
    d.innerHTML = `${esc(s)} <select>${["", "foundation", "fixed", "typical", "top", "ignore"].map((o) => `<option ${o === v ? "selected" : ""}>${o}</option>`).join("")}</select>`;
    d.querySelector("select").onchange = (e) => { if (e.target.value) S.project.storeys.roles[s] = e.target.value; else delete S.project.storeys.roles[s]; recalc(); };
    box.appendChild(d);
  });
}

// ------------------------------------------------------------------ calculation
function recalc() { clearTimeout(S.timer); S.timer = setTimeout(run, 150); }
async function run() {
  try {
    const r = await api("/api/assess", { project: S.project, token: S.token });
    S.result = r.result; S.checks = r.checks; S.summary = r.summary; draw();
  } catch (e) { $("#warn").hidden = false; $("#warn").textContent = e.message; }
}

function draw() {
  const R = S.result;
  $("#k-total").textContent = fmt(R.total_t); $("#k-m2").textContent = fmt(R.per_m2_kg); $("#k-a13").textContent = fmt(R.modules_t["A1-A3"]);
  $("#k-checks").textContent = S.checks.length;
  $("#inv-sum").textContent = `${fmt(S.summary.rows)} rows, ${fmt(S.summary.classified)} with a material class; ${S.summary.storeys.length} storeys`;
  $("#warn").hidden = !R.warnings.length; $("#warn").innerHTML = R.warnings.map(esc).join("<br>");
  const bar = (id, labels, vals, color, unit = "tCO2e") => chart(id).setOption({ grid: { left: 60, right: 20, top: 20, bottom: 40 },
    tooltip: { trigger: "axis", valueFormatter: (v) => fmt(v, 1) + " " + unit }, xAxis: { type: "category", data: labels, axisLabel: { interval: 0 } },
    yAxis: { type: "value", name: unit }, series: [{ type: "bar", data: vals, itemStyle: { color }, barMaxWidth: 48 }] }, true);
  bar("c-modules", Object.keys(R.modules_t), Object.values(R.modules_t), "#5A5F68");
  chart("c-groups").setOption({ tooltip: { trigger: "item", valueFormatter: (v) => fmt(v) + " tCO2e" }, series: [{ type: "pie", radius: ["40%", "70%"],
    data: Object.entries(R.a1a3_by_group).map(([k, v]) => ({ name: k, value: +v.toFixed(1), itemStyle: { color: COL[k] || COL.Other } })),
    label: { formatter: "{b}\n{d}%" } }] }, true);
  // sankey: category -> group
  const links = Object.entries(R.a1a3_by_category_group).filter(([, v]) => v > 0.5).map(([k, v]) => { const [c, g] = k.split("|"); return { source: c, target: g, value: +v.toFixed(1) }; });
  const nodes = [...new Set(links.flatMap((l) => [l.source, l.target]))].map((n) => ({ name: n, itemStyle: { color: COL[n] || "#9AA0A8" } }));
  chart("c-sankey").setOption({ tooltip: { valueFormatter: (v) => fmt(v) + " tCO2e" }, series: [{ type: "sankey", data: nodes, links, emphasis: { focus: "adjacency" }, lineStyle: { color: "gradient", opacity: 0.35 } }] }, true);
  // elements stacked
  const cats = Object.keys(R.a1a3_by_category).slice(0, 14).reverse(); const grps = Object.keys(R.a1a3_by_group);
  chart("c-elements").setOption({ tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v) => fmt(v, 1) + " tCO2e" }, legend: { top: 0 },
    grid: { left: 170, right: 30, top: 40, bottom: 30 }, xAxis: { type: "value", name: "tCO2e" }, yAxis: { type: "category", data: cats },
    series: grps.map((g) => ({ name: g, type: "bar", stack: "a", itemStyle: { color: COL[g] || COL.Other }, data: cats.map((c) => R.a1a3_by_category_group[`${c}|${g}`] || 0) })) }, true);
  table("#tb-lines", ["Class", "Group", "Quantity", "Unit", "Factor", "Factor unit", "Mass (t)", "tCO2e", "Rows", "Source"],
    R.lines.map((l) => [l.material_class, l.group, fmt(l.quantity, 1), l.unit, l.factor, l.factor_unit, fmt(l.mass_t, 1), fmt(l.tCO2e, 1), l.rows, l.source]), [2, 4, 6, 7, 8]);
  // storeys and scenarios
  const cv = R.storey_curve || [];
  chart("c-storeys").setOption({ tooltip: { trigger: "axis", valueFormatter: (v) => fmt(v) + " tCO2e" }, legend: { top: 0 }, grid: { left: 70, right: 20, top: 30, bottom: 40 },
    xAxis: { type: "category", name: "storeys", data: cv.map((r) => r.storeys) }, yAxis: { type: "value", name: "tCO2e" },
    series: [{ name: "A1-A3", type: "line", data: cv.map((r) => r.A1A3_t), itemStyle: { color: COL.Steel } },
             { name: "A1-A3 + A4 + A5w", type: "line", data: cv.map((r) => r.total_t), itemStyle: { color: "#30343B" }, lineStyle: { type: "dashed" } }] }, true);
  const sc = [{ name: "Baseline", total_t: R.total_t }, ...R.scenarios];
  chart("c-scen").setOption({ tooltip: { trigger: "axis", valueFormatter: (v) => fmt(v) + " tCO2e" }, grid: { left: 210, right: 30, top: 10, bottom: 30 },
    xAxis: { type: "value", name: "tCO2e" }, yAxis: { type: "category", inverse: true, data: sc.map((s) => s.name.length > 34 ? s.name.slice(0, 33) + "…" : s.name) },
    series: [{ type: "bar", data: sc.map((s) => s.total_t), itemStyle: { color: "#4F86C6" }, label: { show: true, position: "right", formatter: (p) => p.dataIndex ? "−" + fmt(sc[p.dataIndex].saving_pct, 0) + "%" : "" } }] }, true);
  bar("c-a4", Object.keys(R.a4_by_group_t), Object.values(R.a4_by_group_t), "#7FB7C9");
  const a5 = { ...Object.fromEntries(Object.entries(R.a5w_by_group_t).map(([k, v]) => ["Waste: " + k, v])), ...Object.fromEntries(Object.entries(R.a5a_by_crane_t).map(([k, v]) => ["Plant: " + k, v])), "Spoil": R.modules_t.A5r };
  chart("c-a5").setOption({ tooltip: { trigger: "axis", valueFormatter: (v) => fmt(v, 1) + " tCO2e" }, grid: { left: 170, right: 30, top: 10, bottom: 30 },
    xAxis: { type: "value", name: "tCO2e" }, yAxis: { type: "category", data: Object.keys(a5) }, series: [{ type: "bar", data: Object.values(a5), itemStyle: { color: "#C8871E" } }] }, true);
  table("#tb-checks", ["Check", "Severity", "Finding", "Estimate", "Examples", "Action"],
    S.checks.map((c) => [c.check, `<span class="sev-${c.severity}">${c.severity}</span>`, c.finding, c.estimate, c.examples, c.action]), [], true);
  table("#tb-uncl", ["Category", "Material", "Reason", "Rows", "Volume (m3)"],
    Object.entries(R.unclassified).slice(0, 200).map(([k, u]) => [...k.split("|"), u.rows, fmt(u.volume_m3, 1)]), [3, 4]);
  drawRoles(); loadInventory();
}

function table(sel, head, rows, num = [], html = false) {
  const t = $(sel);
  t.innerHTML = `<thead><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>` +
    rows.map((r) => `<tr>${r.map((c, i) => `<td class="${num.includes(i) ? "n" : ""}">${html ? (c ?? "") : esc(c)}</td>`).join("")}</tr>`).join("") + "</tbody>";
}

async function loadInventory() {
  const q = encodeURIComponent($("#q").value || ""); const u = $("#q-uncl").checked;
  const r = await api(`/api/inventory/${S.token}?q=${q}&unclassified=${u}&limit=400`);
  table("#tb-inv", ["Source", "Class", "Category", "Type", "Material", "Storey", "V (m3)", "A (m2)", "Material class", "Rule"],
    r.rows.map((x) => [x.source, x.ifc_class, x.category, x.family_type, x.material, x.storey, fmt(x.volume_m3, 3), fmt(x.area_m2, 2), x.material_class || "—", x.rule]), [6, 7]);
  $("#inv-csv").href = `/api/inventory/${S.token}.csv`;
}
$("#q").oninput = () => { clearTimeout(S.qt); S.qt = setTimeout(loadInventory, 250); };
$("#q-uncl").onchange = loadInventory;

async function loadFactors() {
  const r = await api(`/api/factors?set=${S.project.factor_set}`); $("#fac-ver").textContent = r.version;
  const t = $("#tb-fac");
  t.innerHTML = "<thead><tr><th>Key</th><th>Name</th><th>Basis</th><th>Value</th><th>Unit</th><th>Density</th><th>Tier</th><th>Source</th></tr></thead><tbody>" +
    r.materials.map((f) => `<tr><td>${f.key}</td><td>${esc(f.name)}</td><td>${f.basis}</td><td><input type="number" step="any" data-f="${f.key}" value="${S.project.factor_overrides[f.key] ?? f.value}" style="width:6em"></td><td>${f.unit}</td><td class="n">${f.density}</td><td class="n">${S.project.factor_overrides[f.key] != null ? 1 : f.tier}</td><td class="small">${esc(f.source)}</td></tr>`).join("") + "</tbody>";
  t.querySelectorAll("input[data-f]").forEach((el) => el.onchange = () => { S.project.factor_overrides[el.dataset.f] = +el.value; recalc(); loadFactors(); });
}

// ------------------------------------------------------------------ tabs, files
document.querySelectorAll("#tabs button").forEach((b) => b.onclick = () => {
  document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("on", x === b));
  document.querySelectorAll(".tab").forEach((t) => (t.hidden = t.id !== "t-" + b.dataset.t));
  if (b.dataset.t === "factors") loadFactors();
  setTimeout(() => { resizeVisible(); if (S.result) draw(); }, 30);
});

$("#f-model").onchange = async (e) => {
  const fd = new FormData(); [...e.target.files].forEach((f) => fd.append("files", f));
  $("#src").textContent = "Reading " + [...e.target.files].map((f) => f.name).join(", ") + " …";
  try {
    const r = await fetch("/api/upload", { method: "POST", body: fd }); const j = await r.json();
    if (!r.ok) throw new Error(j.detail);
    S.token = j.token; S.summary = j.summary; S.project.storeys.roles = {};
    $("#src").textContent = [...e.target.files].map((f) => f.name).join(", "); run();
  } catch (err) { $("#src").textContent = "Error: " + err.message; }
};
$("#b-example").onclick = async () => { const d = await api("/api/defaults"); S.project = d.example; S.token = "example"; $("#src").textContent = "Example building (synthetic)"; bindInputs(); run(); };

function download(blob, name) { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); }
$("#b-xlsx").onclick = async () => download(await api("/api/report.xlsx", { project: S.project, token: S.token }, true), "buildco2pro_report.xlsx");
$("#b-ifc").onclick = async () => { try { download(await api("/api/tagged.ifc", { project: S.project, token: S.token }, true), "model_carbon.ifc"); } catch (e) { alert(e.message); } };
$("#b-save").onclick = () => download(new Blob([JSON.stringify(S.project, null, 1)], { type: "application/json" }), (S.project.name || "project") + ".json");
$("#f-proj").onchange = async (e) => { S.project = JSON.parse(await e.target.files[0].text()); bindInputs(); run(); };

(async () => {
  const h = await api("/api/health"); $("#ver").textContent = h.version;
  const d = await api("/api/defaults"); S.project = d.example; bindInputs(); await run();
})();
