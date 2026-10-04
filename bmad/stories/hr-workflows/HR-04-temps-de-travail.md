---
id: HR-04-temps-de-travail
title: "Temps de travail — attendance/timesheet → validation → payroll feed"
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
**As** HR/payroll, **I want** time captured, validated and fed to payroll **so that** pay reflects actual
worked time. *(Cross-board: Finance #14.)*

## Acceptance criteria
- [ ] AC-1: Attendance / Timesheet entry → **validation** → correction loop → feeds payroll; monthly summary.
- [ ] AC-2 (fail): an unvalidated / absent record is flagged **before** payroll; corrections are audited.

## DoD
Time is captured, validated, and available to payroll.
