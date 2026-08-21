---
id: TASK-15
title: Implement Ledger redesign of the activity viewer site
status: To Do
assignee: []
created_date: '2026-08-21 15:52'
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
