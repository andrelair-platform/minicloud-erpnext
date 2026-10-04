---
id: HR-06-augmentation-salariale
title: "Augmentation salariale — manager → HR → direction → payroll"
status: Draft
type: Story
epic: hr-workflows
milestone: "HR Workflows — process automation"
estimate: 5
labels: [erpnext, frappe, hr, finance, workflow]
priority: P2
assignee: AndreLiar
repo: andrelair-platform/minicloud-erpnext
project: 8
initiative: Insurance LOB
---

## Story
**As a** manager, **I want** a governed comp-change chain **so that** a raise is validated at three
levels before it reaches payroll. *(Cross-board: Finance #14.)*

## Acceptance criteria
- [ ] AC-1: a comp-change Workflow: **manager → HR → direction** approval chain → Salary Structure Assignment / Additional Salary.
- [ ] AC-2: effective-dated; fully audited.
- [ ] AC-3 (fail): three **distinct** approval legs; no change reaches payroll without direction sign-off.

## DoD
A raise flows manager→HR→direction→payroll, effective-dated, fully audited.
