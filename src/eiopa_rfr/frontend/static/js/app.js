/*
 * Frontend EIOPA RFR Monitoring — reproduit les 5 pages du dashboard
 * Streamlit (src/eiopa_rfr/app.py) au-dessus de l'API JSON exposée par
 * src/eiopa_rfr/webapi.py. SPA sans framework, routage par hash (#overview,
 * #update, #historical, #analysis, #export), rendu par génération de HTML.
 */

const PAGES = ["overview", "update", "historical", "analysis", "export"];

const state = {
  page: "overview",
  maturities: [1, 5, 10, 20, 30],
};

/* ------------------------------------------------------------------ */
/* Utilitaires                                                         */
/* ------------------------------------------------------------------ */

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

function fmtPct(rate) {
  return `${(rate * 100).toFixed(2)}%`;
}

function fmtBps(bps) {
  return `${bps >= 0 ? "+" : ""}${bps.toFixed(1)} bps`;
}

function fmtDateFR(iso) {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (e) {
      /* pas de corps JSON exploitable */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

function statTile(label, value, delta) {
  let deltaHtml = "";
  if (delta) {
    const arrow = delta.direction === "up" ? "▲" : "▼";
    deltaHtml = `<p class="stat-delta ${delta.direction}">${arrow} ${fmtBps(delta.bps)} (M/M)</p>`;
  }
  return `<div class="stat-tile"><p class="stat-label">${escapeHtml(label)}</p><p class="stat-value">${escapeHtml(value)}</p>${deltaHtml}</div>`;
}

function alertBox(kind, glyph, message) {
  return `<div class="alert alert-${kind}">${glyph} ${message}</div>`;
}

/* ------------------------------------------------------------------ */
/* Thème                                                                */
/* ------------------------------------------------------------------ */

function initTheme() {
  const stored = localStorage.getItem("eiopa-theme");
  if (stored === "dark") document.documentElement.setAttribute("data-theme", "dark");

  document.getElementById("theme-toggle").addEventListener("click", () => {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    if (isDark) {
      document.documentElement.removeAttribute("data-theme");
      localStorage.setItem("eiopa-theme", "light");
    } else {
      document.documentElement.setAttribute("data-theme", "dark");
      localStorage.setItem("eiopa-theme", "dark");
    }
    // Les graphiques Plotly lisent les couleurs au rendu : on rejoue la
    // page active pour qu'ils reprennent les tokens du nouveau thème.
    loadPage(state.page);
  });
}

async function initLogo() {
  try {
    const res = await fetch("/assets/logo-mark.svg");
    const svg = await res.text();
    document.querySelectorAll(".brand-mark").forEach((el) => {
      el.innerHTML = svg;
    });
  } catch (e) {
    console.error("Logo introuvable", e);
  }
}

/* ------------------------------------------------------------------ */
/* Navigation                                                           */
/* ------------------------------------------------------------------ */

function renderRoute() {
  const hash = (location.hash || "#overview").slice(1);
  const page = PAGES.includes(hash) ? hash : "overview";
  state.page = page;

  document.querySelectorAll(".nav-item").forEach((a) => {
    a.classList.toggle("active", a.dataset.page === page);
  });
  document.querySelectorAll(".page").forEach((sec) => {
    sec.hidden = sec.id !== `page-${page}`;
  });

  loadPage(page);
}

function loadPage(page) {
  switch (page) {
    case "overview": return renderOverview();
    case "update": return renderUpdate();
    case "historical": return renderHistorical();
    case "analysis": return renderAnalysis();
    case "export": return renderExport();
  }
}

/* ------------------------------------------------------------------ */
/* Graphiques (Plotly)                                                  */
/* ------------------------------------------------------------------ */

function chartLayout(extra) {
  const base = {
    margin: { l: 55, r: 20, t: 10, b: 45 },
    height: 380,
    font: { family: "system-ui, -apple-system, 'Segoe UI', sans-serif", color: cssVar("--ink") },
    paper_bgcolor: cssVar("--chart-surface"),
    plot_bgcolor: cssVar("--chart-surface"),
    hovermode: "x unified",
    xaxis: { gridcolor: cssVar("--grid"), linecolor: cssVar("--axis"), zeroline: false },
    yaxis: { gridcolor: cssVar("--grid"), linecolor: cssVar("--axis"), zeroline: false },
  };
  return Object.assign(base, extra, {
    xaxis: Object.assign({}, base.xaxis, extra.xaxis || {}),
    yaxis: Object.assign({}, base.yaxis, extra.yaxis || {}),
  });
}

const PLOTLY_CONFIG = { displayModeBar: false, responsive: true };

function plotYieldCurve(containerId, curve) {
  const trace = {
    x: curve.maturities,
    y: curve.rates.map((r) => r * 100),
    mode: "lines+markers",
    line: { color: cssVar("--cat-1"), width: 2 },
    marker: { size: 8 },
    hovertemplate: "%{x}Y : %{y:.2f}%<extra></extra>",
  };
  Plotly.newPlot(containerId, [trace], chartLayout({
    xaxis: { title: "Maturité (années)" },
    yaxis: { title: "Taux (%)" },
    showlegend: false,
  }), PLOTLY_CONFIG);
}

function plotTimeSeries(containerId, series) {
  const trace = {
    x: series.dates,
    y: series.rates.map((r) => r * 100),
    mode: "lines",
    line: { color: cssVar("--cat-1"), width: 2 },
    hovertemplate: "%{x} : %{y:.2f}%<extra></extra>",
  };
  Plotly.newPlot(containerId, [trace], chartLayout({
    xaxis: { title: "Date" },
    yaxis: { title: "Taux (%)" },
    showlegend: false,
  }), PLOTLY_CONFIG);
}

function plotComparison(containerId, curr, prev) {
  const t1 = {
    x: curr.maturities,
    y: curr.rates.map((r) => r * 100),
    mode: "lines+markers",
    name: "Actuel",
    line: { color: cssVar("--cat-1"), width: 2 },
    marker: { size: 8 },
    hovertemplate: "%{x}Y : %{y:.2f}%<extra>Actuel</extra>",
  };
  const t2 = {
    x: prev.maturities,
    y: prev.rates.map((r) => r * 100),
    mode: "lines+markers",
    name: "Précédent",
    line: { color: cssVar("--cat-3"), width: 2, dash: "dash" },
    marker: { size: 8 },
    hovertemplate: "%{x}Y : %{y:.2f}%<extra>Précédent</extra>",
  };
  Plotly.newPlot(containerId, [t1, t2], chartLayout({
    xaxis: { title: "Maturité (années)" },
    yaxis: { title: "Taux (%)" },
    legend: { orientation: "h", y: 1.08, x: 1, xanchor: "right" },
  }), PLOTLY_CONFIG);
}

/* ------------------------------------------------------------------ */
/* Page : Vue d'ensemble                                                */
/* ------------------------------------------------------------------ */

async function renderOverview() {
  const el = document.getElementById("page-overview");
  el.innerHTML = `<div class="loading">Chargement…</div>`;
  try {
    const data = await api("/api/overview");
    if (data.empty) {
      el.innerHTML = alertBox("warning", "!", "Aucune donnée disponible. Effectuez une première mise à jour.");
      return;
    }

    document.getElementById("hero-sub").textContent =
      `Solvency II · Taux sans risque EIOPA · Dernière clôture : ${fmtDateFR(data.latest_date)}`;

    let html = `<p class="page-caption">Dernière mise à jour : ${fmtDateFR(data.latest_date)}</p>`;

    if (data.issues_total > 0) {
      const dates = data.issues.map((i) => fmtDateFR(i.reference_date)).join(", ");
      const suffix = data.issues_total > data.issues.length ? "…" : "";
      html += alertBox("warning", "!",
        `${data.issues_total} mois avec anomalie d'ingestion (${escapeHtml(dates)}${suffix}) — détail dans la page Historique.`);
    }

    html += `<div class="stat-grid">`;
    for (const s of data.stats) {
      html += statTile(`Taux ${s.maturity}Y`, fmtPct(s.rate), s.delta);
    }
    if (data.va) {
      html += statTile("VA", fmtPct(data.va.rate), data.va.delta);
    }
    html += `</div>`;

    html += `<h2 class="section-title">Courbe des taux actuelle</h2><div class="chart" id="chart-curve"></div>`;
    html += `<h2 class="section-title">Évolution récente (Taux 10Y)</h2><div class="chart" id="chart-10y"></div>`;

    el.innerHTML = html;

    if (data.curve.maturities.length) plotYieldCurve("chart-curve", data.curve);
    if (data.series_10y.dates.length) plotTimeSeries("chart-10y", data.series_10y);
  } catch (e) {
    el.innerHTML = alertBox("error", "✕", escapeHtml(e.message));
  }
}

/* ------------------------------------------------------------------ */
/* Page : Mise à jour                                                   */
/* ------------------------------------------------------------------ */

async function renderUpdate() {
  const el = document.getElementById("page-update");
  el.innerHTML = `<div class="loading">Récupération des fichiers disponibles sur l'EIOPA…</div>`;
  try {
    const data = await api("/api/update/available");
    if (!data.files.length) {
      el.innerHTML = alertBox("warning", "!", "Aucun fichier trouvé sur le site EIOPA.");
      return;
    }

    let html = `<h2 class="section-title">Fichiers disponibles</h2>`;
    html += `<div class="table-wrap"><table class="data-table"><thead><tr><th>Date</th><th>Fichier</th><th>Statut</th></tr></thead><tbody>`;
    for (const f of data.files) {
      const statusLabel = f.status === "done" ? "✓ Déjà traité" : "↓ À télécharger";
      html += `<tr><td>${f.label}</td><td>${escapeHtml(f.filename)}</td><td>${statusLabel}</td></tr>`;
    }
    html += `</tbody></table></div>`;

    if (data.readonly) {
      html += alertBox("warning", "!",
        "Cette instance est en lecture seule. L'ingestion de nouvelles données se fait en local " +
        "(<code>python main.py</code> ou <code>eiopa-rfr-web</code>), puis <code>historical.db</code> est poussé sur git. " +
        "Un téléchargement lancé ici serait perdu au prochain redémarrage de l'instance.");
      el.innerHTML = html;
      return;
    }

    const pending = data.files.filter((f) => f.status === "pending");
    if (!pending.length) {
      html += alertBox("success", "✓", "Tous les fichiers disponibles ont déjà été traités.");
      el.innerHTML = html;
      return;
    }

    html += `<h2 class="section-title">Sélection</h2>`;
    html += `<div class="checkbox-list" id="update-checkboxes">`;
    pending.forEach((f, idx) => {
      html += `<label class="checkbox-row"><input type="checkbox" value="${f.date}" ${idx === 0 ? "checked" : ""}> ${f.label} — ${escapeHtml(f.filename)}</label>`;
    });
    html += `</div>`;
    html += `<button class="btn btn-primary" id="run-update-btn">Lancer le téléchargement</button>`;
    html += `<div id="update-results"></div>`;

    el.innerHTML = html;

    document.getElementById("run-update-btn").addEventListener("click", async () => {
      const checked = Array.from(el.querySelectorAll("#update-checkboxes input:checked")).map((cb) => cb.value);
      if (!checked.length) {
        window.alert("Sélectionnez au moins une date.");
        return;
      }
      const items = pending.filter((f) => checked.includes(f.date));
      const btn = document.getElementById("run-update-btn");
      const resultsEl = document.getElementById("update-results");
      btn.disabled = true;
      btn.textContent = "Téléchargement en cours…";
      resultsEl.innerHTML = `<div class="loading">Traitement de ${items.length} fichier(s)…</div>`;

      try {
        const res = await api("/api/update/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ items }),
        });
        let rHtml = `<h2 class="section-title">Résultats</h2>`;
        for (const r of res.results) {
          rHtml += alertBox(r.success ? "success" : "error", r.success ? "✓" : "✕", `${r.label} — ${escapeHtml(r.message)}`);
        }
        resultsEl.innerHTML = rHtml;
      } catch (e) {
        resultsEl.innerHTML = alertBox("error", "✕", escapeHtml(e.message));
      } finally {
        btn.disabled = false;
        btn.textContent = "Lancer le téléchargement";
      }
    });
  } catch (e) {
    el.innerHTML = alertBox("error", "✕", escapeHtml(e.message));
  }
}

/* ------------------------------------------------------------------ */
/* Page : Historique                                                    */
/* ------------------------------------------------------------------ */

async function renderHistorical() {
  const el = document.getElementById("page-historical");
  el.innerHTML = `<div class="loading">Chargement…</div>`;
  try {
    const summary = await api("/api/historical/summary");
    if (summary.empty) {
      el.innerHTML = alertBox("warning", "!", "Aucune donnée historique disponible.");
      return;
    }

    let html = `<div class="stat-grid">`;
    html += statTile("Nombre d'enregistrements", String(summary.count));
    html += statTile("Première date", fmtDateFR(summary.first_date));
    html += statTile("Dernière date", fmtDateFR(summary.last_date));
    html += `</div>`;

    if (summary.issues.length) {
      html += `<details class="expander"><summary>! ${summary.issues.length} anomalie(s) d'ingestion</summary>`;
      html += `<div class="table-wrap"><table class="data-table"><thead><tr><th>Date</th><th>Statut</th><th>Fichier source</th><th>Maturités manquantes</th><th>Notes</th></tr></thead><tbody>`;
      for (const i of summary.issues) {
        html += `<tr><td>${escapeHtml(i.reference_date)}</td><td>${escapeHtml(i.status)}</td><td>${escapeHtml(i.source_file || "")}</td><td>${escapeHtml(i.missing_maturities || "")}</td><td>${escapeHtml(i.notes || "")}</td></tr>`;
      }
      html += `</tbody></table></div></details>`;
    }

    html += `<h2 class="section-title">Évolution temporelle</h2>`;
    html += `<div class="form-row">
      <label>Maturité
        <select id="hist-maturity">${state.maturities.map((m) => `<option value="${m}">${m} ans</option>`).join("")}</select>
      </label>
      <label>Date de début <input type="date" id="hist-start"></label>
      <label>Date de fin <input type="date" id="hist-end" value="${summary.last_date}" max="${summary.last_date}"></label>
    </div>`;
    html += `<div class="chart" id="chart-hist"></div>`;
    html += `<details class="expander"><summary>Voir les données</summary><div class="table-wrap" id="hist-table"></div></details>`;

    el.innerHTML = html;

    const maturitySelect = document.getElementById("hist-maturity");
    if (state.maturities.includes(10)) maturitySelect.value = "10";

    const startInput = document.getElementById("hist-start");
    const oneYearAgo = new Date(summary.last_date);
    oneYearAgo.setDate(oneYearAgo.getDate() - 365);
    startInput.value = oneYearAgo.toISOString().slice(0, 10);

    const reload = () => loadHistoricalSeries(
      Number(maturitySelect.value),
      startInput.value,
      document.getElementById("hist-end").value,
    );
    maturitySelect.addEventListener("change", reload);
    startInput.addEventListener("change", reload);
    document.getElementById("hist-end").addEventListener("change", reload);
    reload();
  } catch (e) {
    el.innerHTML = alertBox("error", "✕", escapeHtml(e.message));
  }
}

async function loadHistoricalSeries(maturity, start, end) {
  const chartEl = document.getElementById("chart-hist");
  const tableEl = document.getElementById("hist-table");
  try {
    const params = new URLSearchParams({ maturity, start, end });
    const series = await api(`/api/historical/series?${params}`);
    if (!series.dates.length) {
      chartEl.innerHTML = alertBox("warning", "!", "Aucune donnée pour la période sélectionnée.");
      tableEl.innerHTML = "";
      return;
    }
    chartEl.innerHTML = "";
    plotTimeSeries("chart-hist", series);

    let tHtml = `<table class="data-table"><thead><tr><th>Date</th><th class="num">Taux</th></tr></thead><tbody>`;
    for (let i = 0; i < series.dates.length; i++) {
      tHtml += `<tr><td>${fmtDateFR(series.dates[i])}</td><td class="num">${(series.rates[i] * 100).toFixed(4)}%</td></tr>`;
    }
    tHtml += `</tbody></table>`;
    tableEl.innerHTML = tHtml;
  } catch (e) {
    chartEl.innerHTML = alertBox("error", "✕", escapeHtml(e.message));
  }
}

/* ------------------------------------------------------------------ */
/* Page : Analyse                                                       */
/* ------------------------------------------------------------------ */

async function renderAnalysis() {
  const el = document.getElementById("page-analysis");
  el.innerHTML = `<div class="loading">Chargement…</div>`;
  try {
    const { dates } = await api("/api/analysis/dates");
    if (!dates.length) {
      el.innerHTML = alertBox("warning", "!", "Aucune donnée disponible.");
      return;
    }

    const options = dates.map((d) => `<option value="${d}">${fmtDateFR(d)}</option>`).join("");
    let html = `<div class="form-row">
      <label>Date 1 (actuelle) <select id="date1">${options}</select></label>
      <label>Date 2 (comparaison) <select id="date2">${options}</select></label>
    </div>`;
    html += `<h2 class="section-title">Comparaison des courbes</h2><div class="chart" id="chart-compare"></div>`;
    html += `<h2 class="section-title">Variations (en points de base)</h2><div class="table-wrap" id="compare-table"></div>`;
    el.innerHTML = html;

    document.getElementById("date2").value = dates[Math.min(1, dates.length - 1)];

    const reload = () => loadComparison(document.getElementById("date1").value, document.getElementById("date2").value);
    document.getElementById("date1").addEventListener("change", reload);
    document.getElementById("date2").addEventListener("change", reload);
    reload();
  } catch (e) {
    el.innerHTML = alertBox("error", "✕", escapeHtml(e.message));
  }
}

async function loadComparison(date1, date2) {
  const chartEl = document.getElementById("chart-compare");
  const tableEl = document.getElementById("compare-table");
  try {
    const params = new URLSearchParams({ date1, date2 });
    const data = await api(`/api/analysis/compare?${params}`);

    const m1 = Object.keys(data.date1.rates).map(Number).sort((a, b) => a - b);
    const m2 = Object.keys(data.date2.rates).map(Number).sort((a, b) => a - b);
    chartEl.innerHTML = "";
    plotComparison("chart-compare",
      { maturities: m1, rates: m1.map((m) => data.date1.rates[m]) },
      { maturities: m2, rates: m2.map((m) => data.date2.rates[m]) },
    );

    let tHtml = `<table class="data-table"><thead><tr><th>Maturité</th><th class="num">Date 1</th><th class="num">Date 2</th><th class="num">Variation (bps)</th><th class="num">Variation (%)</th></tr></thead><tbody>`;
    for (const v of data.variations) {
      const pct = v.change_pct === null ? "—" : `${v.change_pct >= 0 ? "+" : ""}${v.change_pct.toFixed(2)}%`;
      tHtml += `<tr><td>${v.maturity}Y</td><td class="num">${fmtPct(v.rate1)}</td><td class="num">${fmtPct(v.rate2)}</td><td class="num">${fmtBps(v.change_bps)}</td><td class="num">${pct}</td></tr>`;
    }
    tHtml += `</tbody></table>`;
    tableEl.innerHTML = tHtml;
  } catch (e) {
    chartEl.innerHTML = alertBox("error", "✕", escapeHtml(e.message));
    tableEl.innerHTML = "";
  }
}

/* ------------------------------------------------------------------ */
/* Page : Export                                                        */
/* ------------------------------------------------------------------ */

async function renderExport() {
  const el = document.getElementById("page-export");
  el.innerHTML = `<div class="loading">Chargement…</div>`;
  try {
    const { dates } = await api("/api/export/dates");

    let html = `<p>Génère les fichiers <code>RFR_[DATE]_[VA_TYPE].csv</code> (colonnes <code>Maturity,Base,Up,Down</code>) consommés par les outils ESG et Asset_PTF.</p>`;
    html += alertBox("info", "i", "Le choix NO_VA / WITH_VA à utiliser dépend de l'outil cible et de la méthodologie retenue — voir la documentation externe à ce dashboard. Cette page ne fixe aucun défaut.");

    if (!dates.length) {
      html += alertBox("warning", "!", "Aucune courbe en base. Effectuez d'abord une mise à jour.");
      el.innerHTML = html;
      return;
    }

    html += `<div class="form-row">
      <label>Date de clôture
        <select id="export-date">${dates.map((d) => `<option value="${d}">${fmtDateFR(d)}</option>`).join("")}</select>
      </label>
    </div>`;
    html += `<div class="radio-row" id="export-va-type">
      <label><input type="radio" name="va-type" value="NO_VA" checked> Sans VA (NO_VA)</label>
      <label><input type="radio" name="va-type" value="WITH_VA"> Avec VA (WITH_VA)</label>
      <label><input type="radio" name="va-type" value="BOTH"> Les deux</label>
    </div>`;
    html += `<button class="btn btn-primary" id="export-btn">Générer l'export</button>`;
    html += `<div id="export-results"></div>`;

    el.innerHTML = html;

    document.getElementById("export-btn").addEventListener("click", async () => {
      const date = document.getElementById("export-date").value;
      const choice = document.querySelector('input[name="va-type"]:checked').value;
      const vaTypes = choice === "BOTH" ? ["NO_VA", "WITH_VA"] : [choice];
      const resultsEl = document.getElementById("export-results");
      const btn = document.getElementById("export-btn");
      btn.disabled = true;
      resultsEl.innerHTML = `<div class="loading">Génération…</div>`;

      try {
        const res = await api("/api/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ date, va_types: vaTypes }),
        });
        let rHtml = "";
        for (const g of res.generated) {
          rHtml += alertBox("success", "✓", `${g.va_type} — ${escapeHtml(g.filename)}`);
          rHtml += `<a class="btn btn-secondary" href="/api/export/download/${encodeURIComponent(g.filename)}" download>↓ Télécharger ${escapeHtml(g.filename)}</a>`;
        }
        for (const err of res.errors) {
          rHtml += alertBox("error", "✕", `${err.va_type} — ${escapeHtml(err.message)}`);
        }
        resultsEl.innerHTML = rHtml;
      } catch (e) {
        resultsEl.innerHTML = alertBox("error", "✕", escapeHtml(e.message));
      } finally {
        btn.disabled = false;
      }
    });
  } catch (e) {
    el.innerHTML = alertBox("error", "✕", escapeHtml(e.message));
  }
}

/* ------------------------------------------------------------------ */
/* Démarrage                                                             */
/* ------------------------------------------------------------------ */

async function initApp() {
  initTheme();
  initLogo();
  window.addEventListener("hashchange", renderRoute);

  try {
    const cfg = await api("/api/config");
    state.maturities = cfg.maturities;
    document.getElementById("cfg-country").textContent = `Pays surveillé : ${cfg.country}`;
    document.getElementById("cfg-maturities").textContent = `Maturités : ${cfg.maturities.join(", ")}Y`;
    document.getElementById("cfg-instance").textContent = cfg.readonly
      ? "Instance hébergée — lecture seule"
      : "Instance locale — production";
  } catch (e) {
    console.error("Impossible de charger la configuration", e);
  }

  renderRoute();
}

document.addEventListener("DOMContentLoaded", initApp);
