"use strict";

/* ------------------------------------------------------------------ */
/* Config                                                              */
/* ------------------------------------------------------------------ */

const OWNER = "arnabsen1729";
const REPO = "garmin-parse";
const BRANCH = "main";

const TREE_URL = `https://api.github.com/repos/${OWNER}/${REPO}/git/trees/${BRANCH}?recursive=1`;
const rawUrl = (path) => `https://raw.githubusercontent.com/${OWNER}/${REPO}/${BRANCH}/${path}`;
const githubUrl = (path) => `https://github.com/${OWNER}/${REPO}/blob/${BRANCH}/${path}`;

/* ------------------------------------------------------------------ */
/* Icons (simplified glyphs — see final report re: mockup access)      */
/* ------------------------------------------------------------------ */

const ICONS = {
  running:
    '<path d="M4 21v-4a3 3 0 0 1 3-3h1.5a2 2 0 0 1 2 2v1.2A2.8 2.8 0 0 1 7.7 20H4Z"/><path d="M13.5 13v-4a3 3 0 0 1 3-3H18a2 2 0 0 1 2 2v1.2a2.8 2.8 0 0 1-2.8 2.8H13.5Z"/><circle cx="6.5" cy="9.5" r="1"/><circle cx="16" cy="3.5" r="1"/>',
  cycling:
    '<circle cx="6" cy="17" r="3.5"/><circle cx="18" cy="17" r="3.5"/><path d="M6 17 10 8h4l3.5 5.5"/><path d="M9.5 8 8 5h3"/><path d="M13 8h5"/>',
  swimming:
    '<path d="M2 8c1 1 2 1.5 3.5 1.5S8 8 9.5 8 11 9.5 12.5 9.5 14 8 15.5 8 17 9.5 18.5 9.5 20 8 22 8"/><path d="M2 14c1 1 2 1.5 3.5 1.5S8 14 9.5 14 11 15.5 12.5 15.5 14 14 15.5 14 17 15.5 18.5 15.5 20 14 22 14"/><path d="M2 20c1 1 2 1.5 3.5 1.5S8 20 9.5 20 11 21.5 12.5 21.5 14 20 15.5 20 17 21.5 18.5 21.5 20 20 22 20"/>',
  strength:
    '<rect x="2" y="9" width="3" height="6" rx="1"/><rect x="19" y="9" width="3" height="6" rx="1"/><rect x="5.5" y="7" width="2" height="10" rx="0.5"/><rect x="16.5" y="7" width="2" height="10" rx="0.5"/><line x1="7.5" y1="12" x2="16.5" y2="12"/>',
  fallback: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
};

function iconFor(sportKey, category) {
  if (sportKey.includes("running")) return ICONS.running;
  if (sportKey.includes("cycling") || sportKey.includes("biking")) return ICONS.cycling;
  if (sportKey.includes("swimming")) return ICONS.swimming;
  if (category === "strength") return ICONS.strength;
  return ICONS.fallback;
}

function iconSvg(pathMarkup) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${pathMarkup}</svg>`;
}

/* ------------------------------------------------------------------ */
/* Sport palette / category                                            */
/* ------------------------------------------------------------------ */

const SPORT_COLOR_VARS = {
  running: "--sport-running",
  track_running: "--sport-track_running",
  treadmill_running: "--sport-treadmill_running",
  road_biking: "--sport-road_biking",
  indoor_cycling: "--sport-indoor_cycling",
  lap_swimming: "--sport-lap_swimming",
  strength_training: "--sport-strength_training",
  badminton: "--sport-badminton",
};

function sportColorVar(sportKey) {
  return SPORT_COLOR_VARS[sportKey] || "--sport-fallback";
}

// Mirrors src/garmin_parse/render.py's activity_category().
function activityCategory(sportKey) {
  if (sportKey.includes("running")) return "running";
  if (sportKey.includes("cycling") || sportKey.includes("biking")) return "cycling";
  if (sportKey.includes("swimming")) return "swimming";
  if (sportKey.includes("strength")) return "strength";
  return "other";
}

/* ------------------------------------------------------------------ */
/* Markdown parser for render.py's output                              */
/*                                                                      */
/* Handles:                                                             */
/*   # Title                                                            */
/*   - **Key:** value            (generic fields)                      */
/*   ### Heart Rate Zones + table                                       */
/*   ## <Category>                                                      */
/*   - **Key:** value            (type-specific fields)                 */
/*   | Exercise | Reps | table   (strength only)                        */
/* ------------------------------------------------------------------ */

function parseActivityMarkdown(raw) {
  const lines = raw.split("\n");
  const generic = {};
  const typeFields = {};
  const hrZones = [];
  const exerciseRows = [];
  let typeTitle = null;
  let section = "generic"; // "generic" | "type"
  let tableMode = null; // null | "hr" | "exercise"

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (line === "") {
      // Note: blank lines appear both between sections and between a table
      // heading (e.g. "### Heart Rate Zones") and the table itself, so they
      // must NOT clear tableMode — only an actual heading line does that.
      continue;
    }
    if (line.startsWith("# ")) continue;
    if (line === "### Heart Rate Zones") {
      tableMode = "hr";
      continue;
    }
    if (line.startsWith("## ")) {
      typeTitle = line.slice(3).trim();
      section = "type";
      tableMode = null;
      continue;
    }
    if (line.startsWith("|")) {
      if (line.includes("---")) continue;
      const cells = line
        .split("|")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
      if (tableMode === "hr") {
        if (cells[0] && cells[0].toLowerCase() === "zone") continue;
        if (cells.length === 2) hrZones.push({ zone: cells[0], time: cells[1] });
        continue;
      }
      if (tableMode === "exercise") {
        if (cells.length === 2) exerciseRows.push({ name: cells[0], reps: cells[1] });
        continue;
      }
      // First table row encountered in the type section without a prior
      // '### Heart Rate Zones' marker is the exercise table's header row.
      if (cells[0] && cells[0].toLowerCase() === "exercise") {
        tableMode = "exercise";
        continue;
      }
      continue;
    }

    const m = line.match(/^-\s+\*\*(.+?):\*\*\s*(.*)$/);
    if (m) {
      const [, key, value] = m;
      (section === "type" ? typeFields : generic)[key] = value;
    }
  }

  return { generic, typeFields, typeTitle, hrZones, exerciseRows };
}

/* ------------------------------------------------------------------ */
/* Field/format helpers                                                */
/* ------------------------------------------------------------------ */

function numFromField(value) {
  if (value == null) return null;
  const m = String(value).match(/-?[\d.]+/);
  return m ? parseFloat(m[0]) : null;
}

function durationToSeconds(text) {
  if (!text) return null;
  const parts = text.split(":").map((p) => parseInt(p, 10));
  if (parts.some((p) => Number.isNaN(p))) return null;
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return null;
}

function paceFromSpeedKmh(speedKmh) {
  if (!speedKmh || speedKmh <= 0) return null;
  const minPerKm = 60 / speedKmh;
  const min = Math.floor(minPerKm);
  const sec = Math.round((minPerKm - min) * 60);
  const mm = sec === 60 ? min + 1 : min;
  const ss = sec === 60 ? 0 : sec;
  return `${mm}:${String(ss).padStart(2, "0")} /km`;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ------------------------------------------------------------------ */
/* Activity path parsing (from repo tree)                              */
/* ------------------------------------------------------------------ */

function parseActivityPath(path) {
  const parts = path.split("/");
  const filename = parts[parts.length - 1];
  const match = filename.match(/^(\d{4}-\d{2}-\d{2})_(.+)_(\d+)\.md$/);
  if (!match) return null;
  const [, date, sportKey, id] = match;
  return { path, year: parts[1], date, sportKey, id };
}

/* ------------------------------------------------------------------ */
/* Fetching + sessionStorage cache                                     */
/* ------------------------------------------------------------------ */

const RAW_CACHE_PREFIX = "ledger:raw:";

async function fetchRawCached(path) {
  const cacheKey = RAW_CACHE_PREFIX + path;
  try {
    const cached = sessionStorage.getItem(cacheKey);
    if (cached != null) return cached;
  } catch (_) {
    // sessionStorage unavailable (e.g. privacy mode) — fall through to fetch.
  }
  const res = await fetch(rawUrl(path));
  if (!res.ok) throw new Error(`Raw fetch returned ${res.status} for ${path}`);
  const text = await res.text();
  try {
    sessionStorage.setItem(cacheKey, text);
  } catch (_) {
    // Quota exceeded or unavailable — non-fatal, just skip caching.
  }
  return text;
}

let activityIndexPromise = null;

async function loadActivityIndex() {
  if (activityIndexPromise) return activityIndexPromise;
  activityIndexPromise = (async () => {
    const res = await fetch(TREE_URL);
    if (!res.ok) throw new Error(`GitHub API returned ${res.status}`);
    const data = await res.json();
    return data.tree
      .filter((e) => e.type === "blob" && e.path.startsWith("activities/") && e.path.endsWith(".md"))
      .map((e) => parseActivityPath(e.path))
      .filter(Boolean)
      .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
  })();
  return activityIndexPromise;
}

/* Cache of parsed activity records keyed by path, built as we fetch. */
const parsedCache = new Map();

async function loadParsedActivity(entry) {
  if (parsedCache.has(entry.path)) return parsedCache.get(entry.path);
  const raw = await fetchRawCached(entry.path);
  const parsed = parseActivityMarkdown(raw);
  const record = { ...entry, raw, parsed };
  parsedCache.set(entry.path, record);
  return record;
}

/* ------------------------------------------------------------------ */
/* List rendering                                                      */
/* ------------------------------------------------------------------ */

function startOfWeek(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = (day === 0 ? -6 : 1) - day;
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function parseActivityDate(record) {
  // "Date" field looks like "2026-08-16 08:13"; fall back to filename date.
  const dateField = record.parsed.generic["Date"];
  if (dateField) {
    const d = new Date(dateField.replace(" ", "T"));
    if (!Number.isNaN(d.getTime())) return d;
  }
  return new Date(record.date + "T00:00:00");
}

function primarySecondaryLines(record) {
  const g = record.parsed.generic;
  const category = activityCategory(record.sportKey);
  const distance = numFromField(g["Distance"]);
  const duration = g["Duration"];
  const avgHr = g["Average HR"];
  const calories = g["Calories"];
  const avgSpeed = numFromField(g["Average Speed"]);
  const hasDistance = distance != null && distance > 0;

  if (category === "strength") {
    const sets = record.parsed.typeFields["Total Sets"];
    const primary = [duration, sets ? `${sets} sets` : null].filter(Boolean).join(" · ");
    const secondary = [avgHr ? `avg HR ${avgHr}` : null, calories ? `${calories}` : null]
      .filter(Boolean)
      .join(" · ");
    return { primary, secondary };
  }

  if (hasDistance) {
    const primary = [g["Distance"], duration].filter(Boolean).join(" · ");
    let secondary;
    if (category === "running" && avgSpeed) {
      secondary = [paceFromSpeedKmh(avgSpeed), avgHr ? `avg HR ${avgHr}` : null].filter(Boolean).join(" · ");
    } else {
      secondary = [g["Average Speed"], avgHr ? `avg HR ${avgHr}` : null].filter(Boolean).join(" · ");
    }
    return { primary, secondary };
  }

  const primary = [duration, avgHr ? `avg HR ${avgHr}` : null].filter(Boolean).join(" · ");
  const secondary = calories ? `${calories}` : "";
  return { primary, secondary };
}

function renderRow(record) {
  const btn = document.createElement("a");
  btn.href = `#/a/${encodeURIComponent(record.path)}`;
  btn.className = "activity-row";
  btn.dataset.path = record.path;
  btn.style.setProperty("--row-accent", `var(${sportColorVar(record.sportKey)})`);

  const category = activityCategory(record.sportKey);
  const sportLabel = record.parsed.generic["Activity Type"] || record.sportKey.replace(/_/g, " ");
  const { primary, secondary } = primarySecondaryLines(record);
  const when = parseActivityDate(record);
  const whenStr = when.toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });

  btn.innerHTML = `
    <span class="icon-tile">${iconSvg(iconFor(record.sportKey, category))}</span>
    <span class="row-main">
      <span class="row-sport">${escapeHtml(sportLabel)}</span>
      <span class="row-primary">${escapeHtml(primary)}</span>
      <span class="row-secondary">${escapeHtml(secondary)}</span>
    </span>
    <span class="row-when">${escapeHtml(whenStr)}</span>
  `;
  return btn;
}

async function renderList() {
  const statusEl = document.getElementById("list-status");
  const groupsEl = document.getElementById("list-groups");
  statusEl.hidden = false;
  statusEl.textContent = "Loading activities…";
  groupsEl.innerHTML = "";

  try {
    const index = await loadActivityIndex();
    if (index.length === 0) {
      statusEl.textContent = "No activities found.";
      return;
    }

    const records = await Promise.all(index.map((entry) => loadParsedActivity(entry)));
    records.sort((a, b) => parseActivityDate(b) - parseActivityDate(a));

    const now = new Date();
    const weekStart = startOfWeek(now);

    const groups = new Map(); // label -> { records: [], sortKey }
    for (const record of records) {
      const when = parseActivityDate(record);
      let label;
      let sortKey;
      if (when >= weekStart) {
        label = "This week";
        sortKey = Infinity;
      } else {
        label = when.toLocaleString(undefined, { month: "long", year: "numeric" });
        sortKey = when.getFullYear() * 12 + when.getMonth();
      }
      if (!groups.has(label)) groups.set(label, { records: [], sortKey });
      groups.get(label).records.push(record);
    }

    const sortedGroups = [...groups.entries()].sort((a, b) => b[1].sortKey - a[1].sortKey);

    statusEl.hidden = true;
    groupsEl.innerHTML = "";
    for (const [label, group] of sortedGroups) {
      const totalDistance = group.records.reduce((sum, r) => {
        const d = numFromField(r.parsed.generic["Distance"]);
        return sum + (d || 0);
      }, 0);

      const section = document.createElement("div");
      section.className = "list-group";

      const header = document.createElement("div");
      header.className = "list-group-header";
      const countLabel = `${group.records.length} activit${group.records.length === 1 ? "y" : "ies"}`;
      const distLabel = totalDistance > 0 ? ` · ${totalDistance.toFixed(2)} km` : "";
      header.innerHTML = `
        <span class="list-group-title">${escapeHtml(label)}</span>
        <span class="list-group-summary">${escapeHtml(countLabel + distLabel)}</span>
      `;
      section.appendChild(header);

      for (const record of group.records) {
        section.appendChild(renderRow(record));
      }
      groupsEl.appendChild(section);
    }

    highlightActiveRow();
  } catch (err) {
    statusEl.hidden = false;
    statusEl.textContent = `Failed to load activities: ${err.message}`;
  }
}

function highlightActiveRow() {
  const rows = document.querySelectorAll(".activity-row");
  const currentPath = currentDetailPath();
  rows.forEach((row) => {
    row.classList.toggle("active", currentPath != null && row.dataset.path === currentPath);
  });
}

/* ------------------------------------------------------------------ */
/* Detail rendering                                                    */
/* ------------------------------------------------------------------ */

let currentRawText = "";
let currentPath = "";

function currentDetailPath() {
  const m = (location.hash || "").match(/^#\/a\/(.+)$/);
  return m ? decodeURIComponent(m[1]) : null;
}

function hrZoneColorVar(zoneNumber) {
  return `var(--hr-z${zoneNumber})`;
}

function statCell(label, value) {
  if (value == null || value === "") return "";
  return `<div class="stat-cell"><div class="stat-label">${escapeHtml(label)}</div><div class="stat-value">${escapeHtml(value)}</div></div>`;
}

function buildStatGrid(g, category) {
  const distance = numFromField(g["Distance"]);
  const avgSpeed = numFromField(g["Average Speed"]);
  const hasDistance = distance != null && distance > 0;

  const cells = [];
  if (g["Duration"]) cells.push(statCell("Duration", g["Duration"]));
  if (hasDistance && g["Distance"]) cells.push(statCell("Distance", g["Distance"]));

  if (hasDistance && category === "running" && avgSpeed) {
    cells.push(statCell("Avg Pace", paceFromSpeedKmh(avgSpeed)));
  } else if (hasDistance && g["Average Speed"]) {
    cells.push(statCell("Avg Speed", g["Average Speed"]));
  }
  if (hasDistance && g["Max Speed"]) cells.push(statCell("Max Speed", g["Max Speed"]));
  // Note: render.py already bakes the unit into these field values (e.g.
  // "775 kcal", "146 bpm"), so they're used as-is without appending units.
  if (g["Calories"]) cells.push(statCell("Calories", g["Calories"]));
  if (g["Average HR"]) cells.push(statCell("Avg HR", g["Average HR"]));
  if (g["Max HR"]) cells.push(statCell("Max HR", g["Max HR"]));

  return cells.join("");
}

function buildHrZones(hrZones, totalDurationSeconds) {
  if (!hrZones || hrZones.length === 0) return "";
  const rows = hrZones
    .map(({ zone, time }) => {
      const secs = durationToSeconds(time) || 0;
      const pct = totalDurationSeconds > 0 ? Math.min(100, (secs / totalDurationSeconds) * 100) : 0;
      return `
        <div class="hr-row">
          <span class="hr-zone-num">Z${escapeHtml(zone)}</span>
          <span class="hr-bar-track"><span class="hr-bar-fill" style="width:${pct}%;background:${hrZoneColorVar(zone)}"></span></span>
          <span class="hr-time">${escapeHtml(time)}</span>
        </div>`;
    })
    .join("");
  return `<div class="section"><div class="section-title">Heart Rate Zones</div>${rows}</div>`;
}

function buildTrainingEffect(g) {
  const aerobic = g["Aerobic Training Effect"];
  const anaerobic = g["Anaerobic Training Effect"];
  const label = g["Training Effect"];
  if (!aerobic && !anaerobic) return "";
  return `
    <div class="section">
      <div class="section-title">Training Effect</div>
      <div class="te-row">
        ${aerobic ? `<div class="te-item"><div class="te-value">${escapeHtml(aerobic)}</div><div class="te-label">Aerobic${label ? " · " + escapeHtml(label) : ""}</div></div>` : ""}
        ${anaerobic ? `<div class="te-item"><div class="te-value">${escapeHtml(anaerobic)}</div><div class="te-label">Anaerobic</div></div>` : ""}
      </div>
    </div>`;
}

const DYNAMICS_LABELS = {
  running: {
    "Average Cadence": "Avg Cadence",
    "Max Cadence": "Max Cadence",
    "Vertical Oscillation": "Vert. Oscillation",
    "Stride Length": "Stride Length",
    "Ground Contact Time": "Ground Contact",
    "Elevation Gain": "Elevation Gain",
    "Elevation Loss": "Elevation Loss",
  },
  cycling: {
    "Average Power": "Avg Power",
    "Max Power": "Max Power",
    "Normalized Power": "Normalized Power",
  },
  swimming: {
    "Stroke Type": "Stroke Type",
    SWOLF: "SWOLF",
    "Pool Length": "Pool Length",
    Lengths: "Lengths",
  },
  strength: {
    "Total Sets": "Total Sets",
    "Total Reps": "Total Reps",
  },
};

function buildDynamics(g, typeFields, typeTitle, category, exerciseRows) {
  const labelMap = DYNAMICS_LABELS[category];
  const items = [];

  if (category === "running") {
    // Elevation lives in the generic section but reads naturally alongside
    // running dynamics per the design's grouping.
    if (g["Elevation Gain"]) items.push(["Elevation Gain", g["Elevation Gain"]]);
    if (g["Elevation Loss"]) items.push(["Elevation Loss", g["Elevation Loss"]]);
  }

  if (labelMap) {
    for (const [key, label] of Object.entries(labelMap)) {
      if (typeFields[key] != null) items.push([label, typeFields[key]]);
    }
  }

  if (items.length === 0 && exerciseRows.length === 0) return "";

  const grid = items
    .map(
      ([label, value]) =>
        `<div class="dyn-item"><div class="stat-label">${escapeHtml(label)}</div><div class="dyn-value">${escapeHtml(value)}</div></div>`
    )
    .join("");

  const exerciseTable =
    exerciseRows.length > 0
      ? `
      <table class="exercise-table">
        <thead><tr><th>Exercise</th><th>Reps</th></tr></thead>
        <tbody>
          ${exerciseRows.map((r) => `<tr><td>${escapeHtml(r.name)}</td><td>${escapeHtml(r.reps)}</td></tr>`).join("")}
        </tbody>
      </table>`
      : "";

  const heading = typeTitle || "Dynamics";
  return `<div class="section"><div class="section-title">${escapeHtml(heading)}</div>${grid ? `<div class="dynamics-grid">${grid}</div>` : ""}${exerciseTable}</div>`;
}

async function renderDetail(path) {
  const emptyEl = document.getElementById("detail-empty");
  const contentEl = document.getElementById("detail-content");
  const loadingEl = document.getElementById("detail-loading");
  const errorEl = document.getElementById("detail-error");
  const actionBar = document.getElementById("action-bar");

  emptyEl.hidden = true;
  contentEl.hidden = true;
  errorEl.hidden = true;
  actionBar.hidden = true;
  loadingEl.hidden = false;

  try {
    const index = await loadActivityIndex();
    const entry = index.find((e) => e.path === path) || parseActivityPath(path) || { path };
    const record = await loadParsedActivity(entry);

    currentRawText = record.raw;
    currentPath = path;

    const { generic: g, typeFields, typeTitle, hrZones, exerciseRows } = record.parsed;
    const category = activityCategory(record.sportKey || "");
    const sportLabel = g["Activity Type"] || (entry.sportKey || "").replace(/_/g, " ");
    const totalDurationSeconds = durationToSeconds(g["Duration"]) || 0;

    document.getElementById("detail-hero").innerHTML = `
      <span class="icon-tile" style="--row-accent: var(${sportColorVar(entry.sportKey || "")})">${iconSvg(iconFor(entry.sportKey || "", category))}</span>
      <span>
        <div class="hero-sport" style="color: var(${sportColorVar(entry.sportKey || "")})">${escapeHtml(sportLabel)}</div>
        <div class="hero-date">${escapeHtml(g["Date"] || entry.date || "")}</div>
      </span>
    `;

    document.getElementById("detail-stats").innerHTML = buildStatGrid(g, category);
    document.getElementById("detail-hr").innerHTML = buildHrZones(hrZones, totalDurationSeconds);
    document.getElementById("detail-te").innerHTML = buildTrainingEffect(g);
    document.getElementById("detail-dynamics").innerHTML = buildDynamics(
      g,
      typeFields,
      typeTitle,
      category,
      exerciseRows
    );

    document.getElementById("source-link").href = githubUrl(path);

    loadingEl.hidden = true;
    contentEl.hidden = false;
    actionBar.hidden = false;
    document.getElementById("copy-btn").disabled = false;

    highlightActiveRow();
  } catch (err) {
    loadingEl.hidden = true;
    errorEl.hidden = false;
    errorEl.textContent = `Failed to load activity: ${err.message}`;
  }
}

/* ------------------------------------------------------------------ */
/* Copy + toast                                                        */
/* ------------------------------------------------------------------ */

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    toast.hidden = true;
  }, 1800);
}

document.getElementById("copy-btn").addEventListener("click", async () => {
  if (!currentRawText) return;
  try {
    await navigator.clipboard.writeText(currentRawText);
    const bytes = new TextEncoder().encode(currentRawText).length;
    showToast(`Copied · ${bytes} B of Markdown`);
  } catch (err) {
    showToast("Copy failed");
  }
});

/* ------------------------------------------------------------------ */
/* Theme toggle                                                        */
/* ------------------------------------------------------------------ */

const THEME_KEY = "ledger:theme";

function applyStoredTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") {
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (_) {
    /* ignore */
  }
}

document.getElementById("theme-toggle").addEventListener("click", () => {
  const current =
    document.documentElement.getAttribute("data-theme") ||
    (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch (_) {
    /* ignore */
  }
});

/* ------------------------------------------------------------------ */
/* Router                                                              */
/* ------------------------------------------------------------------ */

function route() {
  const path = currentDetailPath();
  if (path) {
    document.body.dataset.route = "detail";
    renderDetail(path);
    // Also populate the list pane: needed for the >=900px side-by-side
    // layout (and for highlighting the active row) even when landing
    // directly on a detail URL. Cheap after the first load thanks to the
    // sessionStorage + in-memory caches.
    renderList();
  } else {
    document.body.dataset.route = "list";
    document.getElementById("action-bar").hidden = true;
    renderList();
  }
}

window.addEventListener("hashchange", route);

applyStoredTheme();
if (!location.hash) location.hash = "#/";
route();
