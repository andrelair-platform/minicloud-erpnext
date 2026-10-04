# Initiative — ERPNext HR Workflows (board #8)

The SAP-style **HR process automation** suite on **ERPNext (Frappe Workflow + fixtures) + n8n** — the
HR counterpart to ktayl-iam's access governance. **Greenfield** (0 HR workflow activity today).
**HR process ≠ access:** this owns leave/expense/time/recruitment/training/comp/lifecycle-admin/
documents; ktayl-iam (#17) owns access; they meet only at the **Joiner/Mover/Leaver** event (HR-12).
Full plan + cross-board map + readiness gate: [`docs/hr-workflows-initiative.md`](../../../docs/hr-workflows-initiative.md).

Board **#8** (ERPNext HR-Finance) · milestone **HR Workflows — process automation**.

| Story | Title | Pts | Sprint | Cross-board |
|---|---|---|---|---|
| HR-01 | HR foundation config + BMAD-enable the repo | 5 | 1 | — |
| HR-02 | Congés / absences (leave) | 5 | 1 | — |
| HR-03 | Notes de frais (expense) | 5 | 1 | Finance #14 |
| HR-04 | Temps de travail (time & attendance) | 5 | 1 | Finance #14 |
| HR-12 | J/M/L event emission + n8n orchestration (the seam) | 8 | 2 | IAM #17 |
| HR-09 | Offboarding (HR admin side) | 5 | 2 | IAM #17 / Finance #14 |
| HR-07 | Recrutement (→ the Joiner trigger) | 8 | 2 | IAM #17 |
| HR-10 | Changement de poste / mobilité interne (Mover) | 5 | 2 | IAM #17 |
| HR-05 | Formation (training) | 5 | 3 | — |
| HR-06 | Augmentation salariale (comp change) | 5 | 3 | Finance #14 |
| HR-08 | Onboarding (HR admin side) | 5 | 3 | IAM #17 / Workplace #10 |
| HR-11 | Documents RH (generate → sign → archive) | 5 | 3 | Workplace #10 |

**≈66 pts — a 3-sprint initiative.** Sprint 1 (HR-01..04, daily workflows) has **no** IAM dependency →
can start now. Sprints 2–3 align with **ktayl-iam v3**. Build shape = Frappe Workflow JSON (`workflows/`)
+ fixtures + n8n, **not a new app**.
