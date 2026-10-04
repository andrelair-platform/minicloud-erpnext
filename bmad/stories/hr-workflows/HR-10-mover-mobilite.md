---
id: HR-10-mover-mobilite
title: "Changement de poste / mobilité interne — promotion/transfer (Mover trigger)"
status: Draft
type: Story
epic: hr-workflows
milestone: "HR Workflows — process automation"
estimate: 5
labels: [erpnext, frappe, hr, iam]
priority: P2
assignee: AndreLiar
repo: andrelair-platform/minicloud-erpnext
project: 8
initiative: Insurance LOB
---

## Story
**As** HR, **I want** position changes and internal mobility handled in ERPNext **so that** the org
updates and the IS recomputes access accordingly. *(Cross-board: ktayl-iam #17.)*

## Acceptance criteria
- [ ] AC-1: Employee Promotion / Transfer → org change (dept / designation / entity).
- [ ] AC-2: internal-mobility candidacy approval (current manager → new manager → HR).
- [ ] AC-3: emits the **Mover** event (HR-12) → ktayl-iam S018 recompute + recert.
- [ ] AC-4 (fail): a move never breaks the employee's workspace (birthright) access.

## DoD
A transfer updates the org + fires the Mover; ktayl-iam recomputes birthright + flags old access for recert.
