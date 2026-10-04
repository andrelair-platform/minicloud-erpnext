---
id: HR-07-recrutement
title: "Recrutement — opening → applicant → interview → offer → hire (Joiner trigger)"
status: Draft
type: Story
epic: hr-workflows
milestone: "HR Workflows — process automation"
estimate: 8
labels: [erpnext, frappe, hr, iam]
priority: P2
assignee: AndreLiar
repo: andrelair-platform/minicloud-erpnext
project: 8
initiative: Insurance LOB
---

## Story
**As** a recruiter/manager, **I want** the hiring pipeline in ERPNext ending in an Employee record **so
that** an accepted offer becomes the **Joiner** trigger into the rest of the IS. *(Cross-board: ktayl-iam #17.)*

## Acceptance criteria
- [ ] AC-1: Job Opening → Job Applicant → Interview → **Job Offer**.
- [ ] AC-2: on **offer accepted** an **Employee** is created → fires the **Joiner** event (HR-12) to ktayl-iam.
- [ ] AC-3: the applicant→employee handoff carries matricule / job / dept / country / entity.
- [ ] AC-4 (fail): **no access is granted here** — that is ktayl-iam's Joiner (workspace birthright).

## DoD
A hire creates the Employee and fires the Joiner; ktayl-iam then auto-provisions the workspace birthright.
