---
id: HR-09-offboarding
title: "Offboarding (HR admin) — separation template + fire the Leaver event"
status: Draft
type: Story
epic: hr-workflows
milestone: "HR Workflows — process automation"
estimate: 5
labels: [erpnext, frappe, hr, iam, finance]
priority: P1
assignee: AndreLiar
repo: andrelair-platform/minicloud-erpnext
project: 8
initiative: Insurance LOB
---

## Story
**As** HR, **I want** a departure to run the HR closure and signal the rest of the IS **so that** exit,
clearance and settlement happen — and access is revoked. *(Cross-board: ktayl-iam #17, Finance #14.)*

## Acceptance criteria
- [ ] AC-1: **Employee Separation** template — exit interview, clearance checklist, final settlement.
- [ ] AC-2: emits the **Leaver** event on the relieve date → ktayl-iam S017 revokes all access.
- [ ] AC-3: final settlement posts to Finance #14.
- [ ] AC-4 (fail): the Leaver fires so there is **no dangling access** (the IAM counterpart proves zero residual).

## DoD
A departure runs the HR closure + fires the Leaver; access is gone, settlement booked.
