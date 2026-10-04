---
id: HR-02-conges-absences
title: "Congés / absences — leave request → manager approval → ledger"
status: Draft
type: Story
epic: hr-workflows
milestone: "HR Workflows — process automation"
estimate: 5
labels: [erpnext, frappe, hr, workflow]
priority: P1
assignee: AndreLiar
repo: andrelair-platform/minicloud-erpnext
project: 8
initiative: Insurance LOB
---

## Story
**As an** employee, **I want** to request leave and have my manager approve it **so that** my balance and
the planning update automatically — the everyday HR workflow.

## Acceptance criteria
- [ ] AC-1: **Leave Application** Workflow (committed JSON in `workflows/`): draft → **manager approval** → approved → leave-ledger update → notify.
- [ ] AC-2: native **balance + overlap check** (a request over balance / overlapping is blocked).
- [ ] AC-3: rejection notifies the employee with the reason.
- [ ] AC-4 (fail): the approver is the employee's manager (from the org), not the requester.

## DoD
An employee files leave, the manager approves, the balance updates, both are notified — end to end.
