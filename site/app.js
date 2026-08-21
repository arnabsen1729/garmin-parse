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
/* Icons — exact Lucide glyph markup from the Ledger mockup            */
/* (Garmin Viewer Direction.dc.html, "Sport palette" legend), one per   */
/* sport key rather than a collapsed category bucket.                  */
/* ------------------------------------------------------------------ */

const ICONS = {
  running:
    '<path d="M4 16v-2.38C4 11.5 2.97 10.5 3 8c.03-2.72 1.49-6 4.5-6C9.37 2 10 3.8 10 5.5c0 3.11-2 5.66-2 8.68V16a2 2 0 1 1-4 0Z"></path><path d="M20 20v-2.38c0-2.12 1.03-3.12 1-5.62-.03-2.72-1.49-6-4.5-6C14.63 6 14 7.8 14 9.5c0 3.11 2 5.66 2 8.68V20a2 2 0 1 0 4 0Z"></path><path d="M16 17h4"></path><path d="M4 13h4"></path>',
  track_running:
    '<circle cx="6" cy="19" r="3"></circle><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"></path><circle cx="18" cy="5" r="3"></circle>',
  treadmill_running: '<path d="m12 14 4-4"></path><path d="M3.34 19a10 10 0 1 1 17.32 0"></path>',
  road_biking:
    '<circle cx="18.5" cy="17.5" r="3.5"></circle><circle cx="5.5" cy="17.5" r="3.5"></circle><circle cx="15" cy="5" r="1"></circle><path d="M12 17.5V14l-3-3 4-3 2 3h2"></path>',
  indoor_cycling:
    '<path d="M15.6 2.7a10 10 0 1 0 5.7 5.7"></path><circle cx="12" cy="12" r="2"></circle><path d="M13.4 10.6 19 5"></path>',
  lap_swimming:
    '<path d="M19 5a2 2 0 0 0-2 2v11"></path><path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"></path><path d="M7 13h10"></path><path d="M7 9h10"></path><path d="M9 5a2 2 0 0 0-2 2v11"></path>',
  strength_training:
    '<path d="M17.596 12.768a2 2 0 1 0 2.829-2.829l-1.768-1.767a2 2 0 0 0 2.828-2.829l-2.828-2.828a2 2 0 0 0-2.829 2.828l-1.767-1.768a2 2 0 1 0-2.829 2.829z"></path><path d="m2.5 21.5 1.4-1.4"></path><path d="m20.1 3.9 1.4-1.4"></path><path d="M5.343 21.485a2 2 0 1 0 2.829-2.828l1.767 1.768a2 2 0 1 0 2.829-2.829l-6.364-6.364a2 2 0 1 0-2.829 2.829l1.768 1.767a2 2 0 0 0-2.828 2.829z"></path><path d="m9.6 14.4 4.8-4.8"></path>',
  badminton: '<circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle>',
  fallback:
    '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"></path>',
};

function iconFor(sportKey) {
  return ICONS[sportKey] || ICONS.fallback;
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

// Only these categories have a meaningful distance figure. Garmin still
// writes a (usually tiny, GPS-drift) Distance field for things like indoor
// cycling or badminton — per the mockup, that's noise, not data, and is
// suppressed by category rather than by checking whether the value is > 0.
const DISTANCE_CATEGORIES = new Set(["running", "cycling", "swimming"]);

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

// Splits a rendered field value like "5.06 km", "16.59 km/h", "5:51 /km", or
// "366 kcal" into a leading number/duration token and a trailing unit, so the
// stat grid can show a big bold number with a small muted unit beneath it —
// matching the Ledger mockup's stat cells. Values with no unit ("29:35")
// simply return an empty unit.
function splitValueUnit(value) {
  if (value == null) return { num: "", unit: "" };
  const str = String(value).trim();
  const m = str.match(/^([\d:.,]+)\s*(.*)$/);
  if (!m) return { num: str, unit: "" };
  return { num: m[1], unit: m[2] };
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

// "Thu 20 Aug 2026 · 09:21" — the detail hero's human-readable date, per the
// mockup. The raw "Date" field ("2026-08-20 09:21") is only ever used to
// derive this, never shown directly.
function formatHeroDate(record) {
  // Built manually rather than via toLocaleString's combined formatting,
  // which (in en-US) inserts a comma and 12-hour AM/PM — the mockup's
  // format is "Thu 20 Aug 2026 · 09:21": no comma, 24-hour time.
  const when = parseActivityDate(record);
  const weekday = when.toLocaleString(undefined, { weekday: "short" });
  const month = when.toLocaleString(undefined, { month: "short" });
  const hh = String(when.getHours()).padStart(2, "0");
  const mm = String(when.getMinutes()).padStart(2, "0");
  return `${weekday} ${when.getDate()} ${month} ${when.getFullYear()} · ${hh}:${mm}`;
}

function primarySecondaryLines(record) {
  const g = record.parsed.generic;
  const category = activityCategory(record.sportKey);
  const distance = numFromField(g["Distance"]);
  const duration = g["Duration"];
  const avgHr = g["Average HR"];
  const calories = g["Calories"];
  const avgSpeed = numFromField(g["Average Speed"]);
  const hasDistance = DISTANCE_CATEGORIES.has(category) && distance != null && distance > 0;

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

  // No distance, not strength (e.g. indoor cycling, badminton): the mockup
  // keeps the primary line to just the duration — avg HR/calories are
  // secondary-line detail, not bold headline text.
  const primary = duration || "";
  const secondary = [avgHr ? `avg HR ${avgHr}` : null, calories ? `${calories}` : null]
    .filter(Boolean)
    .join(" · ");
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
  const weekdayStr = when.toLocaleString(undefined, { weekday: "short" });
  const timeStr = when.toLocaleString(undefined, { hour: "numeric", minute: "2-digit" });

  btn.innerHTML = `
    <span class="icon-tile">${iconSvg(iconFor(record.sportKey))}</span>
    <span class="row-main">
      <span class="row-sport">${escapeHtml(sportLabel)}</span>
      <span class="row-primary">${escapeHtml(primary)}</span>
      <span class="row-secondary">${escapeHtml(secondary)}</span>
    </span>
    <span class="row-when">${escapeHtml(weekdayStr)}<span class="row-when-time"><br>${escapeHtml(timeStr)}</span></span>
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
      // Terse "6 · 13.11 km" per the mockup — not "6 activities · 13.11 km".
      const distLabel = totalDistance > 0 ? ` · ${totalDistance.toFixed(2)} km` : "";
      const summary = `${group.records.length}${distLabel}`;
      header.innerHTML = `
        <span class="list-group-title">${escapeHtml(label)}</span>
        <span class="list-group-summary">${escapeHtml(summary)}</span>
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
  const { num, unit } = splitValueUnit(value);
  const unitHtml = unit ? `<span class="stat-unit"> ${escapeHtml(unit)}</span>` : "";
  return `<div class="stat-cell"><div class="stat-label">${escapeHtml(label)}</div><div class="stat-value">${escapeHtml(num)}${unitHtml}</div></div>`;
}

function buildStatGrid(g, category) {
  const distance = numFromField(g["Distance"]);
  const avgSpeed = numFromField(g["Average Speed"]);
  const hasDistance = DISTANCE_CATEGORIES.has(category) && distance != null && distance > 0;

  const cells = [];
  // Distance before Duration, per the mockup's cell order.
  if (hasDistance && g["Distance"]) cells.push(statCell("Distance", g["Distance"]));
  if (g["Duration"]) cells.push(statCell("Duration", g["Duration"]));

  if (hasDistance && category === "running" && avgSpeed) {
    cells.push(statCell("Avg Pace", paceFromSpeedKmh(avgSpeed)));
  } else if (hasDistance && g["Average Speed"]) {
    cells.push(statCell("Avg Speed", g["Average Speed"]));
  }
  if (hasDistance && g["Max Speed"]) cells.push(statCell("Max Speed", g["Max Speed"]));
  // Note: render.py already bakes the unit into these field values (e.g.
  // "775 kcal"), so it's used as-is without appending a unit.
  if (g["Calories"]) cells.push(statCell("Calories", g["Calories"]));
  // Avg/Max HR deliberately excluded here — per the mockup they appear as a
  // caption next to the "Heart Rate Zones" heading instead (see
  // buildHrZones), not as their own stat-grid cells.

  return cells.join("");
}

function buildHrZones(hrZones, avgHr, maxHr) {
  if (!hrZones || hrZones.length === 0) return "";
  // "avg 170 · max 188 bpm" — the unit appears once, on the trailing value,
  // not repeated on both ("avg 170 bpm · max 188 bpm").
  const avgNum = splitValueUnit(avgHr).num;
  const maxSplit = splitValueUnit(maxHr);
  const captionParts = [];
  if (avgNum) captionParts.push(`avg ${avgNum}`);
  if (maxSplit.num) captionParts.push(`max ${maxSplit.num}${maxSplit.unit ? " " + maxSplit.unit : ""}`);
  const caption = captionParts.length
    ? `<span class="section-caption">${escapeHtml(captionParts.join(" · "))}</span>`
    : "";
  const secsByZone = hrZones.map(({ time }) => durationToSeconds(time) || 0);
  const peakSecs = Math.max(...secsByZone);
  // Bars are scaled relative to the *busiest* zone, not the activity's total
  // duration — a zone that's 20% of total time should still read as a mostly
  // full bar if it's the dominant one, matching the mockup's visual weight
  // (its Z4 bar reads ~100% full at 22:16 of a 29:35 run).
  const rows = hrZones
    .map(({ zone, time }, i) => {
      const secs = secsByZone[i];
      const pct = peakSecs > 0 ? Math.min(100, (secs / peakSecs) * 100) : 0;
      const isPeak = peakSecs > 0 && secs === peakSecs;
      return `
        <div class="hr-row${isPeak ? " hr-row-peak" : ""}">
          <span class="hr-zone-num">Z${escapeHtml(zone)}</span>
          <span class="hr-bar-track"><span class="hr-bar-fill" style="width:${pct}%;background:${hrZoneColorVar(zone)}"></span></span>
          <span class="hr-time">${escapeHtml(time)}</span>
        </div>`;
    })
    .join("");
  return `<div class="section"><div class="section-title-row"><div class="section-title">Heart Rate Zones</div>${caption}</div>${rows}</div>`;
}

function buildTrainingEffect(g) {
  const aerobic = g["Aerobic Training Effect"];
  const anaerobic = g["Anaerobic Training Effect"];
  const label = g["Training Effect"];
  if (!aerobic && !anaerobic) return "";
  // Matches the mockup: the primary cell's own label IS "Training effect"
  // (no separate section heading above it), paired with the sport's
  // training-effect label (e.g. "Lactate threshold") in accent color next
  // to the value. The secondary cell just shows the anaerobic number.
  const primaryCell = aerobic
    ? `<div class="te-item">
         <div class="stat-label">Training Effect</div>
         <div class="te-value-row">
           <span class="te-value">${escapeHtml(aerobic)}</span>
           ${label ? `<span class="te-label te-label-accent">${escapeHtml(label)}</span>` : ""}
         </div>
       </div>`
    : "";
  const secondaryCell = anaerobic
    ? `<div class="te-item">
         <div class="stat-label">Anaerobic</div>
         <div class="te-value">${escapeHtml(anaerobic)}</div>
       </div>`
    : "";
  return `<div class="section"><div class="te-row">${primaryCell}${secondaryCell}</div></div>`;
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

const DYNAMICS_HEADING_OVERRIDES = { running: "Running Dynamics" };

function buildDynamics(g, typeFields, typeTitle, category, exerciseRows) {
  const labelMap = DYNAMICS_LABELS[category];
  const items = [];

  if (labelMap) {
    for (const [key, label] of Object.entries(labelMap)) {
      if (typeFields[key] != null) items.push([label, typeFields[key]]);
    }
  }

  if (category === "running") {
    // Elevation lives in the generic section but reads naturally alongside
    // running dynamics per the design's grouping — as one combined
    // "X / Y m" row (not two separate items) at the *end* of the list,
    // per the mockup's ordering.
    const gain = g["Elevation Gain"];
    const loss = g["Elevation Loss"];
    if (gain || loss) {
      const gainSplit = splitValueUnit(gain);
      const lossSplit = splitValueUnit(loss);
      const unit = gainSplit.unit || lossSplit.unit || "";
      const value = `${gainSplit.num || "–"} / ${lossSplit.num || "–"}${unit ? " " + unit : ""}`;
      items.push(["Elevation Gain / Loss", value]);
    }
  }

  if (items.length === 0 && exerciseRows.length === 0) return "";

  const grid = items
    .map(
      ([label, value]) =>
        `<div class="dyn-item"><span class="dyn-label">${escapeHtml(label)}</span><span class="dyn-value">${escapeHtml(value)}</span></div>`
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

  const heading = DYNAMICS_HEADING_OVERRIDES[category] || typeTitle || "Dynamics";
  return `<div class="section"><div class="section-title">${escapeHtml(heading)}</div>${grid ? `<div class="dynamics-grid">${grid}</div>` : ""}${exerciseTable}</div>`;
}

async function renderDetail(path) {
  const emptyEl = document.getElementById("detail-empty");
  const contentEl = document.getElementById("detail-content");
  const loadingEl = document.getElementById("detail-loading");
  const errorEl = document.getElementById("detail-error");
  const actionBar = document.getElementById("action-bar");
  const actionsTop = document.getElementById("detail-actions-top");

  emptyEl.hidden = true;
  contentEl.hidden = true;
  errorEl.hidden = true;
  actionBar.hidden = true;
  actionsTop.hidden = true;
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

    document.getElementById("detail-hero").innerHTML = `
      <span class="icon-tile" style="--row-accent: var(${sportColorVar(entry.sportKey || "")})">${iconSvg(iconFor(entry.sportKey || ""))}</span>
      <span>
        <div class="hero-sport" style="color: var(${sportColorVar(entry.sportKey || "")})">${escapeHtml(sportLabel)}</div>
        <div class="hero-date">${escapeHtml(formatHeroDate(record))}</div>
      </span>
    `;

    document.getElementById("detail-stats").innerHTML = buildStatGrid(g, category);
    document.getElementById("detail-hr").innerHTML = buildHrZones(hrZones, g["Average HR"], g["Max HR"]);
    document.getElementById("detail-te").innerHTML = buildTrainingEffect(g);
    document.getElementById("detail-dynamics").innerHTML = buildDynamics(
      g,
      typeFields,
      typeTitle,
      category,
      exerciseRows
    );

    actionBar.innerHTML = actionButtonsHtml();
    actionsTop.innerHTML = actionButtonsHtml();
    document.querySelectorAll(".source-link").forEach((a) => {
      a.href = githubUrl(path);
    });
    document.querySelectorAll(".copy-btn").forEach((b) => {
      b.disabled = false;
    });

    loadingEl.hidden = true;
    contentEl.hidden = false;
    actionBar.hidden = false;
    actionsTop.hidden = false;

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

const CHECK_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg>';

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.innerHTML = `<span class="toast-icon">${CHECK_ICON}</span><span>${escapeHtml(message)}</span>`;
  toast.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    toast.hidden = true;
  }, 1800);
}

// The action buttons (Copy raw Markdown + source link) are rendered twice —
// once into the mobile sticky bottom bar (#action-bar) and once inline at
// the top of the desktop detail pane (#detail-actions-top), per the Ledger
// mockup. CSS decides which is visible per breakpoint; both share this
// markup and a single delegated click handler below.
const COPY_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>';
const EXTERNAL_LINK_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"></path><path d="M10 14 21 3"></path><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path></svg>';

function actionButtonsHtml() {
  return `
    <button class="copy-btn" type="button" disabled>${COPY_ICON}Copy raw Markdown</button>
    <a class="source-link" href="#" target="_blank" rel="noopener" title="View source on GitHub" aria-label="View source on GitHub">${EXTERNAL_LINK_ICON}</a>
  `;
}

document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".copy-btn");
  if (!btn || btn.disabled || !currentRawText) return;
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
    document.getElementById("detail-actions-top").hidden = true;
    renderList();
  }
}

window.addEventListener("hashchange", route);

applyStoredTheme();
if (!location.hash) location.hash = "#/";
route();
