---
id: HR-08-onboarding-hr-admin
title: "Onboarding (HR admin side) — employee onboarding template"
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
**As** HR, **I want** a new hire's HR tasks tracked **so that** contract, payroll setup and HR steps run
in parallel with the IAM/workplace provisioning. *(Cross-board: ktayl-iam #17, Digital Workplace #10.)*

## Acceptance criteria
- [ ] AC-1: **Employee Onboarding** template (contract to sign, payroll setup, HR task checklist).
- [ ] AC-2: emits / aligns with the **Joiner** event (HR-12).
- [ ] AC-3 (fail): the IT/access + mailbox/files side is **ktayl-iam #17 + Digital Workplace #10**, **not** duplicated here.

## DoD
A new hire has an HR onboarding checklist that runs in parallel with the IAM Joiner (workspace birthright).
