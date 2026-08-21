# Design: "Ledger" — mobile-friendly activity viewer

Source of truth: [Claude Design project](https://claude.ai/design/p/c289f723-3923-462a-8727-2f10ce5b59ee?file=Garmin+Viewer+Direction.dc.html)
(`Garmin Viewer Direction.dc.html`, direction "01 · Ledger"). This document
summarizes the direction for implementation; the Claude Design file itself
is the pixel-accurate reference (exact SVG icon markup, spacing, mockup
states) — read it directly via the `DesignSync` tool
(`get_file`, projectId `c289f723-3923-462a-8727-2f10ce5b59ee`) rather than
re-deriving icons/spacing from this doc.

## Concept

"One number per workout, ruled and stacked." A strict modernist grid — 2px
rules, zero border-radius, Archivo everywhere, flush-left type — held very
consistently. All warmth comes from color, not shape: each sport owns a
muted accent color that fills its icon tile, and heart-rate zones run a
shared grey-to-red ramp that's semantically the same across every sport
(the one place color means "intensity," not "sport").

## Design tokens

**Typography**: `Archivo` (400/600/800 weights, loaded via Google Fonts),
`system-ui, sans-serif` fallback. Headings and all data values use weight
800. Numeric values use `font-variant-numeric: tabular-nums` for column
alignment. Section micro-labels are 10–11px, uppercase, `.1em` letter
spacing, muted color — used constantly as the "ledger" rhythm.

**Spacing**: 4 / 8 / 12 / 16 / 24 / 32px scale. `border-radius: 0`
everywhere, no exceptions.

**Light theme**:
| Role | Value |
|---|---|
| Background | `#f3f2f2` |
| Surface (raised rows) | `#eae9e9` |
| Text | `#201e1d` |
| Divider (2px rules) | `#201e1d` at 40% |
| Divider (1px hairlines) | `#201e1d` at 18% |
| Muted text | `#7d7979` / `#605d5d` |
| Accent (buttons, links) | `#ec3013` (hover `#dd2b0f`, active `#ae1800`) |

**Dark theme**:
| Role | Value |
|---|---|
| Background | `#161514` |
| Text | `#f3f2f2` |
| Divider | `#f3f2f2` at 35% / 15% |
| Muted text | `#9b9797` / `#bab6b6` |
| Accent | `#ff563c` |

**HR zone ramp** (shared across all sports, light → dark):
Z1 `#d7d3d3`, Z2 `#9b9797`, Z3 `#ffc4b8`, Z4 `#ec3013`, Z5 `#7c1405`
(dark theme swaps Z3→`#ff9783`, Z4→`#ff563c`, Z5→`#dd2b0f`).

**Sport palette** — one muted hue per activity type, fills a square icon
tile with a white/light glyph on top:

| Type | Color |
|---|---|
| Running | `#ec3013` |
| Track running | `#a8420c` |
| Treadmill running | `#8a6a12` |
| Road biking | `#2f6b4b` |
| Indoor cycling | `#2b5c78` |
| Lap swimming | `#34508c` |
| Strength training | `#4a3d6b` |
| Badminton | `#7a2f52` |
| Anything else (fallback) | `#605d5d` |

Icons are Lucide glyphs matched per sport (footprints/shoe for running
variants, bike for cycling variants, waves for swimming, dumbbell for
strength, a generic pulse/activity glyph as fallback). Pull the exact SVG
markup from the Claude Design file rather than re-drawing.

## Layout

**Routing**: a hash router on one page — `#/` is the activity list, `#/a/<path>`
is a detail view for one activity (`path` is the file's repo-relative path,
e.g. `activities/2026/2026-08-20_track_running_24044021685.md`). A detail
URL is shareable and survives a reload.

**Breakpoint**: 900px. Below it, the detail view replaces the list
(single-column, back button to return). At or above it, the list becomes a
fixed 372px left column and the detail pane sits to its right — nothing
new is invented for desktop, the same list/detail content is just
recomposed side by side, with the active row highlighted (tinted
background + colored left border matching the sport color).

**Activity list**: grouped into sections — "This week" then subsequent
calendar months ("July 2026", etc.) — each section header shows a count +
total distance summary and sits above a 2px rule. Each row: a colored
sport-icon tile, the sport name (colored, uppercase micro-label), a bold
primary stat line (the 1–2 numbers that matter most for that sport type —
e.g. distance + duration for running, duration + set count for strength),
a muted secondary stat line, and a right-aligned day/time.

**Activity detail**: hero row (icon + sport name + full date); a stat grid
(3 columns on mobile: distance/duration/avg pace; 5 on desktop, adding max
speed/calories) with 2px top/bottom rules and 1px column dividers; a heart
rate zone breakdown (always 5 rows, bar + time, even if a zone is empty —
an empty zone is itself information, not a missing value); a
training-effect block (aerobic value + label, anaerobic value); a
type-specific "dynamics" grid below that (running: cadence, max cadence,
vertical oscillation, stride length, ground contact time, elevation
gain/loss — other sport types get their own equivalent fields, e.g.
cycling power, swimming stroke/SWOLF, strength sets/reps). A sticky
bottom bar holds the primary "Copy raw Markdown" action (copies the
untouched Markdown, unlocking the paste-into-an-LLM use case) plus a
secondary "view source on GitHub" icon button. Copying shows a brief toast
("Copied · N B of Markdown").

**Sparse data**: a field absent from a file is never rendered — no dashes,
no greyed placeholder rows. The stat grid drops to fewer columns when a
metric genuinely doesn't apply (e.g. no distance for indoor cycling,
badminton, or strength) rather than showing an empty cell.

## Technical decisions

- **No build step, no framework.** Vanilla HTML/CSS/JS, same deployability
  constraint as the current `site/index.html` (drop-in static hosting,
  e.g. Vercel with root directory `site`).
- **Replace `marked.js` with a small hand-written parser.** Every activity
  file is strict `- **Key:** value` lines plus one heart-rate-zone table
  (see `src/garmin_parse/render.py` for the generator) — a focused parser
  (well under 100 lines) can read that directly into a field map instead of
  rendering generic Markdown-to-HTML.
- **Data source is unchanged**: the GitHub tree API for the file listing,
  `raw.githubusercontent.com` for each file's content, client-side, no
  auth, no backend — same as today. Requires the repo to stay public.
- **Cache fetched activity text in `sessionStorage`** keyed by file path,
  so back-navigation is instant and the page stays well under GitHub's
  60 requests/hour unauthenticated rate limit.

## What must survive from the current site

- Chronological browsing of every synced activity.
- A per-activity detail view showing its full stats.
- One-tap "copy raw Markdown" — the primary reason this page exists.
- A link back to the file's source on GitHub (secondary, not prominent).
