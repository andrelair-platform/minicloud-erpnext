---
id: HR-02-conges-absences
title: "Congés / absences — leave request → manager approval → ledger"
status: Done
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

## HR-02b (completion) — leave self-service made real (2026-10-04)
Beyond the workflow: `scripts/hr/setup_leave_self_service.py` links each Employee to a login User
(owner matricule 100001 → real Authentik-SSO user; synthetic subordinates → ERPNext users), routes
`leave_approver` up the `reports_to` chain + grants the Leave Approver role, assigns the France-2026
Holiday List per employee (hrms requirement), and allocates 2026 CP(25)+RTT(10). **Proven live:**
request 2 days → manager Approve → balance 25→23 (weekends excluded), ledger updated. DONE.
