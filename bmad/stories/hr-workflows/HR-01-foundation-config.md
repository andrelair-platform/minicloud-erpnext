---
id: HR-01-foundation-config
title: "HR foundation config (fixtures) + BMAD-enable the repo"
status: Draft
type: Story
epic: hr-workflows
milestone: "HR Workflows — process automation"
estimate: 5
labels: [erpnext, frappe, hr, config]
priority: P1
assignee: AndreLiar
repo: andrelair-platform/minicloud-erpnext
project: 8
initiative: Insurance LOB
---

## Story
**As** HR, **I want** the ERPNext HR baseline configured reproducibly **so that** every HR workflow has
leave types, a work calendar, departments and approval roles to run on — and the repo is BMAD-tracked.

## Acceptance criteria
- [ ] AC-1: HR baseline — company HR settings, **French leave types** (CP / RTT / maladie / sans-solde), **holiday list + work calendar**, departments / designations, approval **roles** (Manager / HR Manager / Direction).
- [ ] AC-2: all of it committed as **Frappe fixtures** (reproducible after a rebuild, not click-ops).
- [ ] AC-3: repo BMAD-enabled (thin `bmad-sync.yml` caller → board #8).
- [ ] AC-4 (fail): no secret / PII in fixtures; re-applying is idempotent.

## DoD
A fresh ERPNext gets the HR foundation from fixtures; the #8 backlog syncs. Prereq for every workflow below.
