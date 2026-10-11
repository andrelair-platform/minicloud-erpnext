"""
HR-04 — Temps de travail: the Timesheet validation Workflow (reproducible, idempotent).

Working-time control = an employee logs their time (Timesheet.time_logs), the line manager
validates it. Creates a Frappe **Workflow** on Timesheet with a self-submit + manager-validation +
reject-for-correction loop:

    Draft ──Submit(Employee)──▶ Submitted for Validation
    Submitted ──Validate(Timesheet Approver)──▶ Validated   (docstatus 1)
              ──Reject(Timesheet Approver)────▶ Rejected     (docstatus 0, back to employee)
    Rejected ──Submit(Employee)──▶ Submitted for Validation  (correct & resubmit)

Validation is gated to a dedicated **"Timesheet Approver"** role (parallel to Leave Approver /
Expense Approver) so the employee cannot validate their own hours. The workflow drives `docstatus`
only — it does NOT touch the native Timesheet `status` (Draft/Submitted/Billed/…), which is
billing-state managed by ERPNext itself.

Run from inside the gunicorn pod (same pattern as setup_expense_workflow.py):
  kubectl exec -n erp <gunicorn-pod> -- bash -c \
    'cd /home/frappe/frappe-bench/sites && \
     /home/frappe/frappe-bench/env/bin/python /tmp/setup_timesheet_workflow.py'

Idempotent: skips the Workflow if one for Timesheet already exists; get_or_create for the masters.
"""
# pyright: reportMissingImports=false
import frappe

SITE = "erp.devandre.sbs"
DOCTYPE = "Timesheet"
WORKFLOW = "Timesheet Validation"
APPROVER_ROLE = "Timesheet Approver"


def ensure_master(doctype: str, name_field: str, name: str, extra: dict | None = None):
    if frappe.db.exists(doctype, name):
        print(f"  = {doctype}: {name} (exists)")
        return
    frappe.get_doc({"doctype": doctype, name_field: name, **(extra or {})}).insert(
        ignore_permissions=True
    )
    print(f"  + {doctype}: {name}")


def main():
    # 0. The validation role (an employee must not validate their own hours).
    print("Role:")
    ensure_master("Role", "role_name", APPROVER_ROLE, {"desk_access": 1})

    # 1. Workflow State / Action masters.
    print("Workflow States / Actions:")
    ensure_master("Workflow State", "workflow_state_name", "Draft", {"style": "Warning"})
    ensure_master("Workflow State", "workflow_state_name", "Submitted for Validation",
                  {"style": "Primary"})
    ensure_master("Workflow State", "workflow_state_name", "Validated", {"style": "Success"})
    ensure_master("Workflow State", "workflow_state_name", "Rejected", {"style": "Danger"})
    ensure_master("Workflow Action Master", "workflow_action_name", "Submit")
    ensure_master("Workflow Action Master", "workflow_action_name", "Validate")
    ensure_master("Workflow Action Master", "workflow_action_name", "Reject")

    # 2. The Workflow (idempotent on document_type).
    existing = frappe.db.get_value("Workflow", {"document_type": DOCTYPE})
    if existing:
        print(f"= Workflow for {DOCTYPE} already exists: {existing}")
        return

    wf = frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": WORKFLOW,
        "document_type": DOCTYPE,
        "is_active": 1,
        "workflow_state_field": "workflow_state",
        "send_email_alert": 1,
        "states": [
            # state · docstatus · who may edit here  (no status mapping — status is billing-managed)
            {"state": "Draft", "doc_status": "0", "allow_edit": "Employee"},
            {"state": "Submitted for Validation", "doc_status": "0", "allow_edit": APPROVER_ROLE},
            {"state": "Validated", "doc_status": "1", "allow_edit": APPROVER_ROLE},
            {"state": "Rejected", "doc_status": "0", "allow_edit": "Employee"},
        ],
        "transitions": [
            # employee self-submits
            {"state": "Draft", "action": "Submit", "next_state": "Submitted for Validation",
             "allowed": "Employee"},
            # manager validates / rejects (distinct role — no self-validation)
            {"state": "Submitted for Validation", "action": "Validate", "next_state": "Validated",
             "allowed": APPROVER_ROLE},
            {"state": "Submitted for Validation", "action": "Reject", "next_state": "Rejected",
             "allowed": APPROVER_ROLE},
            # correct & resubmit
            {"state": "Rejected", "action": "Submit", "next_state": "Submitted for Validation",
             "allowed": "Employee"},
        ],
    })
    wf.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"+ Workflow: {wf.name}")
    print(f"  Draft →[Employee]→ Submitted →[{APPROVER_ROLE}]→ Validated (or →Rejected→ correct loop)")


if __name__ == "__main__":
    frappe.init(site=SITE)
    frappe.connect()
    try:
        main()
    finally:
        frappe.destroy()
