---
id: TASK-15
title: Implement Ledger redesign of the activity viewer site
status: Done
assignee: []
created_date: '2026-08-21 15:52'
updated_date: '2026-08-21 16:00'
labels: []
milestone: m-5
dependencies: []
type: feature
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rewrite site/ as the 'Ledger' direction documented in DESIGN.md (source: Claude Design project c289f723-3923-462a-8727-2f10ce5b59ee, file 'Garmin Viewer Direction.dc.html'). Replace the current marked.js-based raw viewer with: a hash router (#/ list, #/a/<path> detail), a small hand-written parser for the '- **Key:** value' + HR-zone-table format render.py produces, light/dark theme, a 900px breakpoint (mobile: list/detail single-column; desktop: 372px list column + detail pane), sport-colored icon tiles, the shared HR zone color ramp, sparse-data-aware rendering (missing fields omitted, stat grid column count adapts), sessionStorage caching of fetched activity text, and the sticky 'Copy raw Markdown' action with a toast. Must remain a pure static site: no build step, no framework, deployable as-is (e.g. Vercel with root directory 'site'). Fetch the exact SVG icon markup and literal spacing/colors from the Claude Design file directly via the DesignSync tool (get_file) rather than approximating from DESIGN.md's prose.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 List view groups activities into 'This week' + calendar-month sections with count/distance summaries, matching the Ledger visual language (2px rules, zero radius, Archivo, tabular-nums, sport-colored icon tiles)
- [ ] #2 Detail view shows the stat grid, all 5 HR zone rows (even when a zone's time is zero), training effect, and a type-specific dynamics section, with fields absent from the source file omitted rather than shown blank
- [ ] #3 Below 900px the detail view replaces the list (with a working back control); at/above 900px the list is a fixed left column beside the detail pane with the active row visually highlighted
- [ ] #4 Both #/ and #/a/<path> URLs work directly on load/reload (no client-only routing that breaks a hard refresh)
- [ ] #5 Light and dark themes both render correctly
- [ ] #6 'Copy raw Markdown' copies the untouched source Markdown and shows a brief confirmation toast; a secondary control links to the file's source on GitHub
- [ ] #7 Repeat visits to an already-fetched activity read from sessionStorage instead of re-hitting the GitHub API
- [ ] #8 No build step introduced; the site still deploys as static files (verified by opening it via a plain local static server, not just a dev server)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Rewrote site/ as the Ledger design: hash router (#/ list, #/a/<path> detail, both work on hard reload), grouped activity list (This week + calendar months, count/distance headers, sport-colored icon tiles, bold primary/muted secondary stat lines), detail view with adaptive stat grid, all-present HR zone rows with a shared color ramp, training-effect block, type-specific dynamics section (running/cycling/swimming/strength, mirroring src/garmin_parse/render.py's categories), sticky Copy raw Markdown button + toast, GitHub source link, 900px breakpoint (mobile replaces list with detail+back link; desktop shows a fixed 372px list column beside detail with active-row highlight), light/dark theme via CSS custom properties (auto + manual toggle), sessionStorage caching of fetched raw activity text keyed by path, hand-written ~150-line parser for render.py's '- **Key:** value' + HR-zone-table + type-section markdown format. Data fetching approach unchanged (GitHub tree API + raw.githubusercontent.com, unauthenticated, client-side). VERIFIED: parser traced against 3 real files (track_running with full dynamics, strength_training, badminton with sparse fields) via a throwaway node script (deleted after) — all fields extracted correctly, including a synthetic exercise-table case; index.html/app.js/styles.css read for correctness (brace balance checked, all getElementById ids cross-checked against index.html ids, node --check passed on app.js); served via python3 -m http.server and curled — /, /styles.css, /app.js all return 200, page shell structurally sound. NOT VERIFIED (no browser available): visual fidelity to the Claude Design mockup (DesignSync tool was not available in this environment, so icons/exact spacing are hand-approximated from DESIGN.md's token tables rather than pixel-matched to the canonical .dc.html — this should be checked manually), the 900px responsive breakpoint's actual rendering, copy-to-clipboard + toast interaction, hover/active states, and dark-mode/light-mode visual correctness beyond CSS review. Recommend a manual browser pass covering: reload on both #/ and a #/a/<path> URL, toggling width across 900px, copying an activity and checking the toast, and toggling the theme button.
<!-- SECTION:NOTES:END -->
