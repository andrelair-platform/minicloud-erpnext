# HR Workflow Initiative — ERPNext (board #8) — GREENFIELD

> **BMAD artefact — INITIATIVE / SPRINT PLAN + READINESS GATE.** The SAP-style **HR process
> automation** suite (leave, expense, time, recruitment, training, comp, lifecycle HR-admin, HR
> documents) on **ERPNext (Frappe Workflow + fixtures) + n8n orchestration**. **Honestly greenfield**:
> verified 2026-10-04 — ERPNext has **0** Leave/Expense/Recruitment/Attendance records and **0 Workflow
> Actions** (no HR workflow has ever run). **Status: DRAFT for review.** Board **#8** (ERPNext HR-Finance),
> home repo `minicloud-erpnext`. Stories sync to #8 on merge.

## Scope boundary (why this is NOT ktayl-iam)

ktayl-iam (#17) is the **IGA/access** product — it owns *who gets which access*. This initiative is
**HR process automation** — *is this leave approved, this expense reimbursed, this candidate hired*.
Two products, one seam: the **Joiner / Mover / Leaver** HR event. ERPNext decides the HR fact; it emits
the J/M/L event; **ktayl-iam reacts for access** (its v3). Nothing here re-implements access.

```
Event → Business Rules → Approvals → Integrations → Actions → Audit     (your SAP model)
   ERPNext Frappe Workflow + fixtures      │ n8n/Temporal orchestration │  ← THIS initiative (#8)
                                           └── J/M/L event ──► ktayl-iam (access, #17)
```

**Build shape — mostly configuration, not a new app.** Frappe ships every one of these modules; the
work is **Workflow definitions** (committed as JSON in `workflows/`, the existing convention —
cf. `sepa_invoice_to_payment.json`), **fixtures** (leave types, French holiday calendar, approval roles,
onboarding/separation templates), **notifications**, and the **cross-system wiring** (expense→finance,
documents→Docuseal, J/M/L→events). It is greenfield only in that **none of it is configured today**.

## The map — every workflow, where it lives, and its cross-board touchpoints

| HR workflow | Primary owner | Frappe building block | Cross-board touchpoints |
|---|---|---|---|
| **Congés / absences** | **#8** | Leave Application + Leave Ledger (balance check native) | — (planning/payroll internal to ERPNext) |
| **Notes de frais** | **#8** | Expense Claim → Payment Entry | **→ Finance #14** (reimbursement / payment) |
| **Temps de travail** | **#8** | Attendance / Timesheet | **→ Finance #14** (payroll feed) |
| **Formation** | **#8** | Training Program / Event / Result | — (budget check internal) |
| **Augmentation salariale** | **#8** | Salary Structure Assignment / Additional Salary + a Workflow approval chain (manager→HR→direction) | **→ Finance #14** (payroll) |
| **Recrutement** | **#8** | Job Opening → Job Applicant → Interview → Job Offer | **→ ktayl-iam #17** (offer accepted = **Joiner** trigger) |
| **Onboarding (HR admin)** | **#8** | Employee Onboarding template (contract, payroll setup, HR tasks) | **→ ktayl-iam #17** (Joiner → access) · **→ Digital Workplace #10** (mailbox/files provisioned as birthright) |
| **Offboarding (HR admin)** | **#8** | Employee Separation template (exit, clearance, final settlement) | **→ ktayl-iam #17** (Leaver → revoke) · **→ Finance #14** (settlement) |
| **Changement de poste / Mobilité interne** | **#8** | Employee Promotion / Employee Transfer | **→ ktayl-iam #17** (Mover → recompute+recert) |
| **Documents RH** (contrat/avenant → signature → archivage) | **#8** generates | Print Format / Letter → export | **→ Digital Workplace #10** (Docuseal e-sign + Nextcloud/Paperless archive) |

## Story breakdown

### HR-01 — HR foundation config + BMAD-enable the repo  · P1 · 5
- **AC** ✓ ERPNext HR baseline: company HR settings, **French leave types** (CP / RTT / maladie / sans-solde), **holiday list + work calendar**, departments/designations, the approval **roles** (Manager / HR Manager / Direction); ✓ committed as **fixtures** (reproducible, not click-ops); ✓ repo BMAD-enabled (thin `bmad-sync.yml` caller).
- **AC (fail)** ✗ all config is fixture/JSON in-repo (re-applies after a rebuild); ✗ no secret/PII in fixtures.
- **DoD** a fresh ERPNext gets the HR foundation from fixtures; the board #8 backlog syncs. Prereq for every workflow below.

### HR-02 — Congés / absences (leave)  · P1 · 5
- **AC** ✓ **Leave Application** Workflow: draft → **manager approval** → approved → ledger update → notify; ✓ native **balance + overlap check**; ✓ rejection notifies the employee.
- **AC (fail)** ✗ a request over the balance is blocked; ✗ the workflow JSON is committed in `workflows/`.
- **DoD** an employee files leave, the manager approves, the balance updates, both are notified — end to end.

### HR-03 — Notes de frais (expense)  · P1 · 5 · *cross #14*
- **AC** ✓ **Expense Claim** Workflow: employee → **manager approve** → **finance** → Payment Entry; ✓ receipts attached; ✓ reimbursement recorded.
- **AC (fail)** ✗ finance approval is a distinct leg from the manager; ✗ amounts reconcile to the payment.
- **DoD** an expense flows employee→manager→finance→reimbursed; the Finance #14 posting is created.

### HR-04 — Temps de travail (time & attendance)  · P2 · 5 · *cross #14*
- **AC** ✓ Attendance/Timesheet entry → **validation** → correction loop → feeds payroll; ✓ monthly summary.
- **AC (fail)** ✗ an unvalidated/absent record is flagged before payroll; ✗ corrections are audited.
- **DoD** time is captured, validated, and available to payroll.

### HR-05 — Formation (training)  · P2 · 5
- **AC** ✓ Training Program/Event; ✓ request → **manager approval** (+ budget check) → enrollment → **Training Result**; ✓ notifications.
- **DoD** a training request is approved, enrolled, and its result recorded.

### HR-06 — Augmentation salariale (comp change)  · P2 · 5 · *cross #14*
- **AC** ✓ a comp-change Workflow: **manager → HR → direction** approval chain → Salary Structure Assignment / Additional Salary; ✓ effective-dated; ✓ audited.
- **AC (fail)** ✗ three distinct approval legs enforced; ✗ no change reaches payroll without direction sign-off.
- **DoD** a raise flows manager→HR→direction→payroll, effective-dated, fully audited.

### HR-07 — Recrutement (recruitment → the Joiner trigger)  · P2 · 8 · *cross #17*
- **AC** ✓ Job Opening → Job Applicant → Interview → **Job Offer**; ✓ on **offer accepted** an **Employee** is created → this is the **Joiner event** emitted to ktayl-iam (S015).
- **AC (fail)** ✗ no access is granted here (that's ktayl-iam's Joiner); ✗ the applicant→employee handoff carries matricule/job/dept/country/entity.
- **DoD** a hire creates the Employee and fires the Joiner — ktayl-iam then auto-provisions the workspace birthright.

### HR-08 — Onboarding (HR admin side)  · P2 · 5 · *cross #17/#10*
- **AC** ✓ **Employee Onboarding** template (contract to sign, payroll setup, HR task checklist); ✓ emits the **Joiner** event; ✓ the IT/access + mailbox/files side is **ktayl-iam #17 + Digital Workplace #10**, not duplicated here.
- **DoD** a new hire has an HR onboarding checklist that runs in parallel with the IAM Joiner.

### HR-09 — Offboarding (HR admin side)  · P1 · 5 · *cross #17/#14*
- **AC** ✓ **Employee Separation** template (exit interview, clearance, final settlement); ✓ emits the **Leaver** event → ktayl-iam S017 revokes all access; ✓ settlement posts to Finance #14.
- **AC (fail)** ✗ the Leaver event fires on the relieve date (no dangling access — the IAM counterpart).
- **DoD** a departure runs the HR closure + fires the Leaver; access is gone, settlement booked.

### HR-10 — Changement de poste / mobilité interne (Mover)  · P2 · 5 · *cross #17*
- **AC** ✓ Employee Promotion / Transfer → org change (dept/designation/entity) → emits the **Mover** event → ktayl-iam S018 recompute+recert; ✓ internal-mobility candidacy (current→new manager) approval.
- **DoD** a transfer updates the org + fires the Mover; ktayl-iam recomputes birthright + flags old access for recert.

### HR-11 — Documents RH (generate → sign → archive)  · P3 · 5 · *cross #10*
- **AC** ✓ generate contract/avenant from an ERPNext print format; ✓ **Docuseal** e-signature; ✓ archive the signed PDF to **Nextcloud/Paperless**; ✓ link it on the Employee.
- **DoD** a contract is generated, signed, and archived, traceable from the employee record.

### HR-12 — J/M/L event emission + n8n orchestration (the seam)  · P1 · 8 · *cross #17*
The integration backbone — the ERPNext side of what ktayl-iam S015 consumes.
- **AC** ✓ ERPNext emits **signed** lifecycle events (Employee create=joiner / Promotion-Transfer=mover / relieve=leaver) via Frappe **Webhook** (or NATS); ✓ **n8n/Temporal** orchestrates the non-access fan-out (GLPI software tasks + email) — **no hardware** (BYOD); ✓ events carry matricule/job/dept/country/entity.
- **AC (fail)** ✗ ERPNext/n8n **never write Authentik** — access is ktayl-iam's job; ✗ a fan-out failure never blocks the HR transaction.
- **DoD** the three HR events reach ktayl-iam + trigger the GLPI/email fan-out; the seam is proven both ways.

## Sizing (honest)

**≈66 pts — a multi-sprint INITIATIVE, not one sprint.** Suggested cuts:
- **Sprint 1 (daily workflows, ≈20 pts):** HR-01 foundation · HR-02 congés · HR-03 notes de frais · HR-04 temps de travail. *(The everyday employee experience — highest use, lowest integration risk.)*
- **Sprint 2 (lifecycle seam, ≈23 pts):** HR-12 event seam · HR-09 offboarding · HR-07 recrutement · HR-10 mover. *(The J/M/L integration to ktayl-iam — align with IAM v3.)*
- **Sprint 3 (the rest, ≈23 pts):** HR-05 formation · HR-06 comp · HR-08 onboarding HR-admin · HR-11 documents.

## Readiness gate

| Check | Verdict |
|---|---|
| Business need grounded | ✅ the SAP HR suite is genuinely absent (0 workflow activity verified); these are the everyday HR processes |
| Scope boundary clear | ✅ HR process ≠ access; IAM (#17) owns access, this owns HR workflow; they meet only at J/M/L (HR-12) |
| Build shape | ✅ mostly Frappe Workflow JSON + fixtures (existing `workflows/` convention) + n8n — not a new app |
| Cross-board mapping | ✅ Finance #14 (expense/comp/settlement) · Digital Workplace #10 (sign/archive) · ktayl-iam #17 (J/M/L) — mapped per row above |
| Integration/boundary | ✅ HR-12 crosses the HR↔IAM boundary → governance gate; signed events, ERPNext never writes Authentik |
| Dependency | ⚠️ the J/M/L seam (HR-07/09/10/12) pairs with **ktayl-iam v3** (S015 intake); Sprint 1 (daily workflows) has **no** IAM dependency and can start immediately |
| Scope disciplined | ✅ three cuts; recert campaigns / SoD / AI assists remain later |

**Verdict: PASS as an initiative; Sprint 1 (HR-01..04) is ready to start with no external dependency.**
Sprints 2–3 align with ktayl-iam v3. The J/M/L seam (HR-12 ↔ ktayl-iam S015) is the one boundary that
routes through the governance gate.
