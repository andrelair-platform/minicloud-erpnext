---
id: HR-03-notes-de-frais
title: "Notes de frais — expense claim → manager → finance → reimbursement"
status: Draft
type: Story
epic: hr-workflows
milestone: "HR Workflows — process automation"
estimate: 5
labels: [erpnext, frappe, hr, finance, workflow]
priority: P1
assignee: AndreLiar
repo: andrelair-platform/minicloud-erpnext
project: 8
initiative: Insurance LOB
---

## Story
**As an** employee, **I want** to submit expenses and be reimbursed **so that** out-of-pocket costs are
paid back through a governed manager→finance chain. *(Cross-board: Finance #14.)*

## Acceptance criteria
- [ ] AC-1: **Expense Claim** Workflow: employee → **manager approve** → **finance** → Payment Entry.
- [ ] AC-2: receipts attached; reimbursement recorded against the employee.
- [ ] AC-3 (fail): finance approval is a **distinct leg** from the manager; amounts reconcile to the payment.

## DoD
An expense flows employee→manager→finance→reimbursed; the Finance #14 posting is created.
