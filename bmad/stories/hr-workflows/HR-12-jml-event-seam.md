---
id: HR-12-jml-event-seam
title: "J/M/L event emission + n8n orchestration — the HR↔IAM seam"
status: Draft
type: Story
epic: hr-workflows
milestone: "HR Workflows — process automation"
estimate: 8
labels: [erpnext, frappe, integration, iam]
priority: P1
assignee: AndreLiar
repo: andrelair-platform/minicloud-erpnext
project: 8
initiative: Insurance LOB
---

## Story
**As** the platform, **I want** ERPNext to emit Joiner/Mover/Leaver events + orchestrate the non-access
fan-out **so that** HR facts drive the whole IS — the ERPNext side of what ktayl-iam S015 consumes.
*(Cross-board: ktayl-iam #17; crosses the HR↔IAM boundary → governance gate.)*

## Acceptance criteria
- [ ] AC-1: ERPNext emits **signed** lifecycle events — Employee create = **joiner**, Promotion/Transfer = **mover**, relieve = **leaver** — via Frappe **Webhook** (or NATS).
- [ ] AC-2: events carry matricule / job / dept / country / entity.
- [ ] AC-3: **n8n/Temporal** orchestrates the non-access fan-out (GLPI software tasks + email) — **no hardware** (BYOD).
- [ ] AC-4 (fail): ERPNext / n8n **never write Authentik** — access is ktayl-iam's job.
- [ ] AC-5 (fail): a fan-out failure **never** blocks the HR transaction.

## DoD
The three HR events reach ktayl-iam + trigger the GLPI/email fan-out; the seam is proven both ways.
Pairs with ktayl-iam v3 S015.
