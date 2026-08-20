---
id: TASK-2
title: Add .gitignore
status: To Do
assignee: []
created_date: '2026-08-20 19:47'
labels: []
milestone: m-0
dependencies: []
type: chore
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Exclude .venv, __pycache__, *.pyc, .env, and any local garth token cache path from git.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 .venv/, __pycache__/, *.pyc, .env are ignored
- [ ] #2 git status shows no venv/cache noise after uv sync
<!-- AC:END -->
